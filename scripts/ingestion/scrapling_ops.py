#!/usr/bin/env python3
"""
scrapling_ops.py — Scrapling generic helper: tier-escalation state machine
                    + staging-table writer.

Generic helper for Phase 6 Scrapling integration (§14, ADR-025). Implements
the canonical tier_escalation pattern (§14.5):

    Tier 0  get             — basic HTTP GET, no JS, no anti-bot bypass.
    Tier 1  fetch           — browser-like headers, optional JS rendering.
    Tier 2  stealthy_fetch  — Cloudflare-aware anti-bot bypass.

Each URL flows through tiers in order; first success short-circuits the
ladder. If all three tiers fail the URL is recorded with tier_used=None
and status='durur' — the orchestrator (skill) decides whether the run as
a whole halts (DURUR) based on aggregate failure rate.

Bulk variant: when len(urls) > 10 the helper switches to
mcp__ScraplingServer__bulk_fetch / bulk_stealthy_fetch (per-call
batching) to amortize MCP call overhead. The escalation is still
per-URL: a single batch can land URLs at different tiers in the
resulting staging table.

Output: a SQLite-shaped staging JSON
    {workspace_root}/projects/{slug}/_state/staging/scrapling_{date}_{slug}.json
with columns: id, url, tier_used, status, content_hash, content_bytes,
fetched_at, error_message, scenario.

NO Excel write (Phase 6 staging-only per ADR-025). NO per-scenario
sub-schema validation (templates/scrapling/*.schema.json deferred to
Phase 7+ skills).

Pure-helper discipline:
  - No state mutation outside the staging file.
  - Idempotent at the row-shape level: same URL list re-run yields
    deterministically-sized rows array (HTML content may change between
    runs — content_hash drift is the caller's signal that the page moved,
    not a bug).
  - MCP clients are dependency-injected — module-level functions are
    importable and unit-testable with mocks.

CLI:
    python3 scripts/ingestion/scrapling_ops.py \
        --urls-file path/to/urls.txt \
        --output-dir _state/staging/ \
        [--max-urls 50] \
        [--scenario generic] \
        [--slug example] \
        [--date 2026-05-01]

Refs:
  - schemas/scrapling-output-mapping.schema.json (§14.5 tier_escalation)
  - schemas/events.schema.json (source.kind=scrapling_mcp,
    target_excel_sheet=null)
  - skills/ingestion/scrapling-ops/SKILL.md (10-step protocol)
  - ADR-025 (sub-schemas Phase 7+ deferred)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Constants — schema-locked tier ladder (§14.5)
# ---------------------------------------------------------------------------

#: Canonical tier sequence per schemas/scrapling-output-mapping.schema.json
#: §14.5. Order is IMMUTABLE — do not reorder, do not extend, do not add a
#: tier 3. Failure at tier 2 is the terminal DURUR signal.
TIER_LADDER: tuple[str, ...] = ("get", "fetch", "stealthy_fetch")

#: Threshold above which the helper switches to bulk MCP variants. 10 is a
#: round number tuned to amortize per-call MCP roundtrip cost; not a hard
#: schema constraint.
BULK_THRESHOLD: int = 10

#: SQLite-shaped staging table column order. Must stay aligned with the
#: SKILL.md "Staging Table" section.
STAGING_COLUMNS: tuple[str, ...] = (
    "id",
    "url",
    "tier_used",
    "status",
    "content_hash",
    "content_bytes",
    "fetched_at",
    "error_message",
    "scenario",
)

#: Default upper bound on URL count per run. Configurable via CLI / skill
#: input. Above this we DURUR rather than silently truncating.
DEFAULT_MAX_URLS: int = 50


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ScraplingOpsError(Exception):
    """Base class for scrapling_ops errors."""


class TierEscalationError(ScraplingOpsError):
    """Raised when all three tiers in TIER_LADDER fail for a single URL.

    The orchestrator (skill) decides whether a single URL DURUR halts the
    whole run or just records the failure in the staging table — see
    SKILL.md DURUR conditions.
    """

    def __init__(self, url: str, errors: Mapping[str, str]):
        self.url = url
        self.errors = dict(errors)
        msg = f"all tiers failed for {url!r}: " + "; ".join(
            f"{tier}={err}" for tier, err in errors.items()
        )
        super().__init__(msg)


class StagingPathError(ScraplingOpsError):
    """Staging directory is missing / not writable."""


class UrlBudgetExceededError(ScraplingOpsError):
    """URL list exceeds the configured max_urls cap."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierResult:
    """Outcome of a single tier attempt for a single URL."""

    tier: str
    success: bool
    content: str | None
    error: str | None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StagingRow:
    """A single SQLite-shaped staging row (one URL → one row)."""

    id: int
    url: str
    tier_used: str | None
    status: str
    content_hash: str | None
    content_bytes: int
    fetched_at: str
    error_message: str | None
    scenario: str

    def as_dict(self) -> dict[str, Any]:
        return {col: getattr(self, col) for col in STAGING_COLUMNS}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utc_iso_z() -> str:
    """UTC ISO 8601 with 'Z' suffix; microseconds preserved."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _content_hash(content: str | None) -> str | None:
    """SHA-256 hex digest of UTF-8-encoded content. None when content empty."""
    if content is None or content == "":
        return None
    digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    return f"sha256:{digest}"


def _content_bytes(content: str | None) -> int:
    """Byte length of UTF-8-encoded content. 0 when None/empty."""
    if not content:
        return 0
    return len(content.encode("utf-8", errors="replace"))


def _normalize_response(resp: Any) -> tuple[bool, str | None, str | None, dict[str, Any]]:
    """
    Normalize a heterogeneous Scrapling MCP response into a 4-tuple
    (success, content, error, metadata).

    Accepted shapes (most permissive — the MCP server may evolve):
      - dict with 'content' / 'html' / 'text' key on success.
      - dict with 'error' / 'status' >= 400 on failure.
      - bare string → success with the string as content.
      - None / empty → failure with generic error.
      - Exception subclass → failure with str(exception).

    Rationale: this helper is the only place we touch MCP response shape;
    every caller below reads the normalized form.
    """
    if resp is None:
        return False, None, "empty_response", {}

    if isinstance(resp, BaseException):
        return False, None, f"{type(resp).__name__}: {resp}", {}

    if isinstance(resp, str):
        if resp:
            return True, resp, None, {}
        return False, None, "empty_string_response", {}

    if isinstance(resp, dict):
        # Failure-discriminator first: explicit error key OR HTTP-style
        # status code field.
        err = resp.get("error") or resp.get("err")
        if err:
            return False, None, str(err), {k: v for k, v in resp.items() if k != "content"}

        status = resp.get("status_code") or resp.get("status")
        if isinstance(status, int) and status >= 400:
            return (
                False,
                None,
                f"http_{status}",
                {k: v for k, v in resp.items() if k != "content"},
            )

        content = (
            resp.get("content")
            or resp.get("html")
            or resp.get("text")
            or resp.get("body")
        )
        if content:
            meta = {k: v for k, v in resp.items() if k not in ("content", "html", "text", "body")}
            return True, str(content), None, meta
        return False, None, "no_content_in_response", {k: v for k, v in resp.items()}

    # Unknown shape — best-effort stringify.
    try:
        text = str(resp)
        if text:
            return True, text, None, {}
    except Exception as exc:  # pragma: no cover — defensive
        return False, None, f"unstringifiable_response: {exc}", {}
    return False, None, "unknown_response_shape", {}


# ---------------------------------------------------------------------------
# Tier escalation (single URL)
# ---------------------------------------------------------------------------

def tier_escalate(
    url: str,
    mcp_clients: Mapping[str, Callable[..., Any]],
    *,
    raise_on_all_fail: bool = False,
) -> tuple[str | None, str | None, dict[str, Any]]:
    """
    Walk the §14.5 tier ladder for a single URL until one tier succeeds.

    Args:
        url: Target URL. Must be a non-empty string.
        mcp_clients: Mapping of tier name → callable. Required keys: 'get',
            'fetch', 'stealthy_fetch'. Each callable accepts (url=...) and
            returns one of the shapes accepted by `_normalize_response`.
        raise_on_all_fail: If True, raise TierEscalationError when every
            tier fails. If False (default), return (None, None, {'errors':
            {...}}) so the caller can record a 'durur' staging row without
            unwinding the loop.

    Returns:
        Tuple (tier_used, content, metadata):
          - tier_used: 'get' / 'fetch' / 'stealthy_fetch' on success;
            None on all-fail (when raise_on_all_fail=False).
          - content: Raw HTML/text on success; None on all-fail.
          - metadata: Dict carrying per-tier diagnostics. Always contains
            'attempts' (list of TierResult-as-dict). On all-fail also
            contains 'errors' (tier→error string).

    The ladder is fixed by §14.5; do not subclass / monkey-patch order.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"url must be a non-empty string, got {url!r}")

    missing = [t for t in TIER_LADDER if t not in mcp_clients]
    if missing:
        raise ValueError(
            f"mcp_clients missing required tier callables: {missing}"
        )

    attempts: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    for tier in TIER_LADDER:
        client = mcp_clients[tier]
        try:
            resp = client(url=url)
        except BaseException as exc:  # noqa: BLE001 — convert to TierResult
            success, content, err, meta = False, None, f"{type(exc).__name__}: {exc}", {}
        else:
            success, content, err, meta = _normalize_response(resp)

        attempts.append({
            "tier": tier,
            "success": success,
            "error": err,
            "content_bytes": _content_bytes(content),
            "metadata_keys": sorted(meta.keys()),
        })

        if success:
            return tier, content, {
                "attempts": attempts,
                "tier_meta": dict(meta),
            }

        errors[tier] = err or "unknown_error"

    # All tiers failed.
    if raise_on_all_fail:
        raise TierEscalationError(url, errors)
    return None, None, {"attempts": attempts, "errors": errors}


# ---------------------------------------------------------------------------
# Bulk escalation
# ---------------------------------------------------------------------------

def _split_bulk_response(
    resp: Any,
    urls: Sequence[str],
) -> dict[str, Any]:
    """
    Index a bulk MCP response by URL.

    Accepted shapes:
      - list aligned with urls (positional): item i belongs to urls[i].
      - dict {url: response} keyed by URL.
      - dict {'results': [...]} mirroring the list form.
      - dict {'errors': [...]} carrying batch-level failure.

    Unknown shapes degrade to per-URL fallback (single-call mode).
    """
    if isinstance(resp, list):
        return {urls[i]: resp[i] if i < len(resp) else None for i in range(len(urls))}

    if isinstance(resp, dict):
        # Direct URL keying.
        if any(u in resp for u in urls):
            return {u: resp.get(u) for u in urls}
        results = resp.get("results") or resp.get("data")
        if isinstance(results, list):
            return {urls[i]: results[i] if i < len(results) else None for i in range(len(urls))}
        # Batch-level error: every URL inherits the error.
        if resp.get("error"):
            return {u: resp for u in urls}

    # Unknown shape — return empty dict so the caller falls back to
    # per-URL escalation.
    return {}


def bulk_tier_escalate(
    urls: Sequence[str],
    mcp_clients: Mapping[str, Callable[..., Any]],
    *,
    bulk_clients: Mapping[str, Callable[..., Any]] | None = None,
) -> list[tuple[str, str | None, str | None, dict[str, Any]]]:
    """
    Tier-escalate a list of URLs. Uses bulk MCP variants when available
    and len(urls) > BULK_THRESHOLD; otherwise falls back to per-URL
    `tier_escalate`.

    Args:
        urls: Target URL list.
        mcp_clients: Single-URL callables (required: 'get', 'fetch',
            'stealthy_fetch').
        bulk_clients: Optional bulk callables (keys: 'fetch',
            'stealthy_fetch'); when provided AND len(urls) > BULK_THRESHOLD
            the helper batches at tiers 1+2.

    Returns:
        List of (url, tier_used, content, metadata) tuples in the input
        URL order. tier_used is None when all tiers fail for that URL.
    """
    use_bulk = bulk_clients is not None and len(urls) > BULK_THRESHOLD

    if not use_bulk:
        return [
            (u, *tier_escalate(u, mcp_clients, raise_on_all_fail=False))
            for u in urls
        ]

    # Bulk path. Walk the ladder per-tier, batching per-tier across all
    # still-pending URLs. Tier 0 (get) is intentionally NOT batched — get
    # is the cheapest tier and the per-URL form keeps logic identical to
    # the small-list path.
    pending = list(urls)
    results: dict[str, tuple[str | None, str | None, dict[str, Any]]] = {}

    # Tier 0 (always per-URL).
    next_pending: list[str] = []
    for u in pending:
        tier, content, meta = _attempt_single_tier(u, "get", mcp_clients)
        if tier:
            results[u] = (tier, content, meta)
        else:
            next_pending.append(u)
    pending = next_pending

    # Tiers 1 and 2 — bulk.
    for tier in ("fetch", "stealthy_fetch"):
        if not pending:
            break
        bulk_fn = bulk_clients.get(tier) if bulk_clients else None
        if bulk_fn is None:
            # No bulk variant for this tier → per-URL fallback.
            next_pending = []
            for u in pending:
                t, c, m = _attempt_single_tier(u, tier, mcp_clients)
                if t:
                    existing = results.get(u, (None, None, {"attempts": []}))
                    merged_attempts = list(existing[2].get("attempts", []))
                    merged_attempts.extend(m.get("attempts", []))
                    results[u] = (t, c, {**m, "attempts": merged_attempts})
                else:
                    existing = results.get(u, (None, None, {"attempts": []}))
                    merged_attempts = list(existing[2].get("attempts", []))
                    merged_attempts.extend(m.get("attempts", []))
                    results[u] = (None, None, {**m, "attempts": merged_attempts,
                                                "errors": {**existing[2].get("errors", {}),
                                                           **m.get("errors", {})}})
                    next_pending.append(u)
            pending = next_pending
            continue

        # Bulk call.
        try:
            bulk_resp = bulk_fn(urls=list(pending))
        except BaseException as exc:  # noqa: BLE001
            indexed: dict[str, Any] = {u: f"bulk_error: {type(exc).__name__}: {exc}" for u in pending}
        else:
            indexed = _split_bulk_response(bulk_resp, pending)
            if not indexed:
                # Unknown shape → per-URL fallback for this tier.
                indexed = {u: mcp_clients[tier](url=u) for u in pending}

        next_pending = []
        for u in pending:
            resp_item = indexed.get(u)
            success, content, err, meta_kv = _normalize_response(resp_item)
            existing = results.get(u, (None, None, {"attempts": [], "errors": {}}))
            merged_attempts = list(existing[2].get("attempts", []))
            merged_attempts.append({
                "tier": tier,
                "success": success,
                "error": err,
                "content_bytes": _content_bytes(content),
                "metadata_keys": sorted(meta_kv.keys()),
            })
            if success:
                results[u] = (tier, content, {
                    "attempts": merged_attempts,
                    "tier_meta": dict(meta_kv),
                })
            else:
                merged_errors = dict(existing[2].get("errors", {}))
                merged_errors[tier] = err or "unknown_error"
                results[u] = (None, None, {
                    "attempts": merged_attempts,
                    "errors": merged_errors,
                })
                next_pending.append(u)
        pending = next_pending

    return [(u, *results.get(u, (None, None, {"attempts": [], "errors": {}}))) for u in urls]


def _attempt_single_tier(
    url: str,
    tier: str,
    mcp_clients: Mapping[str, Callable[..., Any]],
) -> tuple[str | None, str | None, dict[str, Any]]:
    """Single-tier attempt; mirrors the per-URL path inside `tier_escalate`."""
    client = mcp_clients[tier]
    try:
        resp = client(url=url)
    except BaseException as exc:  # noqa: BLE001
        success, content, err, meta = False, None, f"{type(exc).__name__}: {exc}", {}
    else:
        success, content, err, meta = _normalize_response(resp)

    attempt = {
        "tier": tier,
        "success": success,
        "error": err,
        "content_bytes": _content_bytes(content),
        "metadata_keys": sorted(meta.keys()),
    }
    if success:
        return tier, content, {"attempts": [attempt], "tier_meta": dict(meta)}
    return None, None, {"attempts": [attempt], "errors": {tier: err or "unknown_error"}}


# ---------------------------------------------------------------------------
# Staging table
# ---------------------------------------------------------------------------

def build_staging_rows(
    escalation_results: Iterable[tuple[str, str | None, str | None, Mapping[str, Any]]],
    *,
    scenario: str = "generic",
    fetched_at: str | None = None,
    start_id: int = 1,
) -> list[StagingRow]:
    """
    Convert tier-escalation tuples into SQLite-shaped staging rows.

    Args:
        escalation_results: Iterable of (url, tier_used, content, metadata)
            as returned by `bulk_tier_escalate` (or a list of
            `tier_escalate` returns prefixed with the URL).
        scenario: Free-form scenario label (e.g. 'generic', 's1_competitor_snapshot').
            Stored on every row for downstream filtering.
        fetched_at: ISO timestamp; defaults to now (UTC).
        start_id: First row id; ids are 1-based and contiguous.

    Returns:
        List of StagingRow.
    """
    ts = fetched_at or _utc_iso_z()
    rows: list[StagingRow] = []
    for i, (url, tier_used, content, metadata) in enumerate(escalation_results, start=start_id):
        if tier_used:
            status = "ok"
            err_msg = None
            chash = _content_hash(content)
            cbytes = _content_bytes(content)
        else:
            status = "durur"
            errors = (metadata or {}).get("errors") or {}
            err_msg = "; ".join(f"{t}={e}" for t, e in errors.items()) or "all_tiers_failed"
            chash = None
            cbytes = 0

        rows.append(StagingRow(
            id=i,
            url=url,
            tier_used=tier_used,
            status=status,
            content_hash=chash,
            content_bytes=cbytes,
            fetched_at=ts,
            error_message=err_msg,
            scenario=scenario,
        ))
    return rows


def staging_table_dict(rows: Sequence[StagingRow]) -> dict[str, Any]:
    """Render rows as a SQLite-shaped JSON dict (columns + rows arrays)."""
    return {
        "schema_version": "1.0",
        "table": "scrapling_staging",
        "columns": list(STAGING_COLUMNS),
        "rows": [r.as_dict() for r in rows],
        "row_count": len(rows),
    }


def write_staging_json(
    rows: Sequence[StagingRow],
    output_path: Path,
) -> Path:
    """
    Write the staging-table dict to disk as JSON. Creates the parent
    directory if missing. Atomic-ish: writes to a tmp file then renames.
    """
    output_path = Path(output_path)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StagingPathError(
            f"cannot create staging directory {output_path.parent}: {exc}"
        ) from exc

    payload = staging_table_dict(rows)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Orchestrator (CLI-friendly)
# ---------------------------------------------------------------------------

def run_scrapling_ops(
    urls: Sequence[str],
    mcp_clients: Mapping[str, Callable[..., Any]],
    *,
    output_path: Path,
    scenario: str = "generic",
    max_urls: int = DEFAULT_MAX_URLS,
    bulk_clients: Mapping[str, Callable[..., Any]] | None = None,
) -> dict[str, Any]:
    """
    Top-level orchestrator: validate URL count → escalate → build rows →
    write staging JSON. Returns a small summary dict suitable for
    embedding in a workflow_runner output_ref.

    Raises:
        UrlBudgetExceededError: len(urls) > max_urls (DURUR upstream).
        StagingPathError: cannot write the staging file.
    """
    if not isinstance(urls, (list, tuple)):
        raise ValueError(f"urls must be a list/tuple, got {type(urls).__name__}")
    if len(urls) > max_urls:
        raise UrlBudgetExceededError(
            f"url count {len(urls)} exceeds max_urls={max_urls}; DURUR per skill brief"
        )

    if not urls:
        # Empty list is a no-op success — the skill records it but does
        # not DURUR; the caller decides whether emptiness is meaningful.
        rows: list[StagingRow] = []
    else:
        results = bulk_tier_escalate(urls, mcp_clients, bulk_clients=bulk_clients)
        rows = build_staging_rows(results, scenario=scenario)

    written = write_staging_json(rows, Path(output_path))

    ok_count = sum(1 for r in rows if r.status == "ok")
    durur_count = sum(1 for r in rows if r.status == "durur")
    tier_counts: dict[str, int] = {}
    for r in rows:
        if r.tier_used:
            tier_counts[r.tier_used] = tier_counts.get(r.tier_used, 0) + 1

    return {
        "staging_path": str(written),
        "row_count": len(rows),
        "ok_count": ok_count,
        "durur_count": durur_count,
        "tier_counts": tier_counts,
        "scenario": scenario,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="scrapling_ops.py",
        description="Scrapling tier-escalation helper + staging writer.",
    )
    p.add_argument("--urls-file", required=True,
                   help="Newline-delimited URL list (one URL per line; # comments allowed).")
    p.add_argument("--output-dir", required=True,
                   help="Staging output directory; the file is named scrapling_{date}_{slug}.json.")
    p.add_argument("--max-urls", type=int, default=DEFAULT_MAX_URLS,
                   help=f"DURUR if URL count exceeds this (default: {DEFAULT_MAX_URLS}).")
    p.add_argument("--scenario", default="generic",
                   help="Scenario label stored on every row (default: 'generic').")
    p.add_argument("--slug", default="run",
                   help="Project slug used in the output filename (default: 'run').")
    p.add_argument("--date", default=None,
                   help="ISO date for the output filename; defaults to today (UTC).")
    return p.parse_args(list(argv))


def _read_urls_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"urls file not found: {path}")
    raw = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    try:
        urls = _read_urls_file(Path(args.urls_file))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_path = Path(args.output_dir) / f"scrapling_{date_str}_{args.slug}.json"

    # The CLI variant cannot perform real MCP calls without a live MCP
    # client; this entry point is intentionally a thin scaffold for skill
    # invocation and tests. We refuse to fabricate fake responses here.
    print(
        json.dumps({
            "ok": False,
            "reason": "cli_requires_mcp_clients_injection",
            "hint": "Call scripts.ingestion.scrapling_ops.run_scrapling_ops(...) "
                    "from the skill orchestrator with bound MCP client callables.",
            "would_write_to": str(output_path.resolve()),
            "url_count": len(urls),
            "max_urls": args.max_urls,
        }, ensure_ascii=False, indent=2),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "TIER_LADDER",
    "BULK_THRESHOLD",
    "STAGING_COLUMNS",
    "DEFAULT_MAX_URLS",
    "ScraplingOpsError",
    "TierEscalationError",
    "StagingPathError",
    "UrlBudgetExceededError",
    "TierResult",
    "StagingRow",
    "tier_escalate",
    "bulk_tier_escalate",
    "build_staging_rows",
    "staging_table_dict",
    "write_staging_json",
    "run_scrapling_ops",
    "main",
)
