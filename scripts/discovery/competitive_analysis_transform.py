#!/usr/bin/env python3
"""
competitive_analysis_transform.py — pure transform: Scrapling
bulk_stealthy_fetch responses (+ DataForSEO competitors_domain) →
S1 competitor_snapshot staging rows.

Phase 7 Wave 2 (W-B3) — first activation of ADR-025 per-scenario
sub-schema enforcement (templates/scrapling/S1_competitor_snapshot.schema.json).
The scrapling-ops generic helper (Phase 6) handles the §14.5 tier
ladder; this transform is the S1 *consumer* — it accepts already-fetched
content (one entry per competitor URL plus the resolved tier_attempts /
fetch_method) and projects each entry into one S1-validated staging row.

D-03 invariant: every URL is normalized through `normalize_url` before
the staging row is built. The normalizer is the same pure function
shape used by cannibalization_transform (lowercase scheme+host, strip
trailing slash on non-root, drop fragment, drop tracking params, sort
remaining query keys). Idempotent: normalize_url(normalize_url(u))==u.

Tier_escalation §14.5 invariant: this transform is *not* the orchestrator
(scrapling-ops is); but it does enforce that any caller supplied
tier_escalation override matches the canonical
['get','fetch','stealthy_fetch'] sequence. Non-canonical orderings
raise TierEscalationOrderError — DURUR.

S1 schema validation: every projected row is round-tripped through
validate_schema.build_validator(S1_SCHEMA) before being committed to the
in-memory staging payload — the strict FormatChecker ENFORCES the schema's
`format` keywords (date-time / uri), not just structure. Validation failure
raises StagingSchemaError — DURUR.

STAGING-ONLY (D-003 / ADR-025 alignment): no master.xlsx writes from
this module. No Excel writer import is allowed here. Output is a JSON
array of S1 rows under `_state/staging/competitive_analysis_{date}_{slug}.json`.

CLI:
  python3 scripts/discovery/competitive_analysis_transform.py \\
      --raw-scrapling inbox/scrapling/{date}-bulk_stealthy_fetch-competitor-{slug}.json \\
      [--raw-competitors-domain inbox/dfs/{date}-competitors_domain-{slug}.json] \\
      --project-slug {slug} \\
      [--snapshot-date 2026-05-01T00:00:00.000000+00:00] \\
      [--output-dir _state/staging/]

Refs:
  - templates/scrapling/S1_competitor_snapshot.schema.json (ADR-025 §14.2)
  - schemas/scrapling-output-mapping.schema.json (§14.5 tier sequence)
  - schemas/events.schema.json (source.kind ∈ {scrapling_mcp, dataforseo_mcp},
    target_excel_sheet=null for staging-only)
  - skills/ingestion/scrapling-ops/SKILL.md (Phase 6 generic helper)
  - scripts/util/dfs_response.py (canonical endpoint-aware DFS response
    normalize SSOT, Y-02 v1.6-Phase-3 Tier 1)
  - scripts/discovery/cannibalization_transform.py (D-03 normalize_url
    convention)
  - rules/append-only-state.md, rules/schema-first.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit  # used by domain_from_url()

# ---------------------------------------------------------------------------
# Path wiring — make `scripts.budget`, `scripts.ingestion.dfs_pull` importable
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Canonical DFS response shape adapter (Y-02 v1.6-Phase-3 Tier 1 dedup,
# was a try/except dfs_pull import + local fallback). util/dfs_response is
# import-stable (zero deps) so no soft-import wrapper required.
from scripts.util.dfs_response import (  # noqa: E402  (sys.path mutation above)
    DFSResponseError as _DFSResponseError,
    normalize_dfs_response as _normalize_dfs_response,
)

# Canonical D-03 URL normalize (K-01 dedup, v1.5-Phase-1 Tier 1).
from scripts.util.url_normalize import (  # noqa: E402  (sys.path mutation above)
    URLNormalizeError as _URLNormalizeError,
    normalize_url as _canonical_normalize_url,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical §14.5 tier ladder. Mirrors scrapling_ops.TIER_LADDER. Reordering
#: or extending is a schema violation — raise TierEscalationOrderError.
CANONICAL_TIER_ESCALATION: tuple[str, ...] = ("get", "fetch", "stealthy_fetch")

#: Path to the S1 sub-schema (ADR-025 Phase 7+ activation).
S1_SCHEMA_PATH: Path = (
    _REPO_ROOT / "templates" / "scrapling" / "S1_competitor_snapshot.schema.json"
)

#: Required keys per the S1 sub-schema. Mirrors the schema `required[]`.
S1_REQUIRED_KEYS: tuple[str, ...] = (
    "snapshot_date",
    "domain",
    "url_normalized",
    "fetch_method",
    "status_code",
)

#: All S1 properties (in column order — used for deterministic row layout).
S1_COLUMNS: tuple[str, ...] = (
    "snapshot_date",
    "domain",
    "url_normalized",
    "url_original",
    "fetch_method",
    "tier_attempts",
    "content_hash",
    "content_excerpt",
    "meta_title",
    "meta_description",
    "h1",
    "schema_org_count",
    "page_size_bytes",
    "status_code",
    "fetch_duration_ms",
)

#: DFS competitors_domain ~5 credits per call (single batched lookup).
CREDITS_PER_COMPETITORS_DOMAIN_CALL: float = 5.0

#: Default content excerpt cut-off matching the S1 maxLength constraint.
CONTENT_EXCERPT_MAX_CHARS: int = 500

#: Bulk fetch unhealthy threshold — abort the run when >50% of URLs fail
#: across all 3 tiers. Mirrors scrapling_ops orchestrator policy.
BULK_UNHEALTHY_THRESHOLD: float = 0.5


# ---------------------------------------------------------------------------
# Exceptions (DURUR-style explicit, no silent fallback)
# ---------------------------------------------------------------------------

class CompetitiveAnalysisError(Exception):
    """Base error for competitive-analysis transform failures (DURUR)."""


class TierEscalationOrderError(CompetitiveAnalysisError):
    """Caller-supplied tier_escalation order does not match the canonical
    §14.5 sequence. STOP — order is schema-locked."""


class StagingSchemaError(CompetitiveAnalysisError):
    """A projected staging row failed S1 sub-schema validation. STOP —
    schema-first violation; never silently emit a drifted row."""


class BulkUnhealthyError(CompetitiveAnalysisError):
    """Aggregate fetch failure rate exceeds BULK_UNHEALTHY_THRESHOLD —
    competitor batch is unhealthy. STOP — no partial staging accepted."""


class BudgetExceededError(CompetitiveAnalysisError):
    """Budget pre-flight failed — DataForSEO call would exceed the daily
    cap. STOP — no MCP call is dispatched."""


class StagingPathError(CompetitiveAnalysisError):
    """Staging output path cannot be created / is not writable."""


class InboxPathError(CompetitiveAnalysisError):
    """Inbox path (inbox/scrapling or inbox/dfs) cannot be created."""


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant) — convention-shared with cannibalization
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Adapter wrapping :class:`URLNormalizeError` into
    :class:`CompetitiveAnalysisError` so call-site DURUR semantics stay
    backward-compatible after K-01 dedup (v1.5-Phase-1 Tier 1).
    """
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError as exc:
        raise CompetitiveAnalysisError(str(exc)) from exc


def domain_from_url(url: str) -> str:
    """Extract the bare host (no scheme, no trailing slash) from a URL."""
    if not isinstance(url, str) or not url.strip():
        raise CompetitiveAnalysisError("cannot derive domain from empty url")
    parts = urlsplit(url.strip())
    host = parts.hostname or ""
    if not host:
        raise CompetitiveAnalysisError(f"url has no host: {url!r}")
    return host.lower()


# ---------------------------------------------------------------------------
# Tier_escalation enforcement (§14.5 invariant)
# ---------------------------------------------------------------------------

def assert_canonical_tier_order(sequence: Sequence[str]) -> None:
    """Reject any tier_escalation sequence that diverges from the canonical
    `['get','fetch','stealthy_fetch']`. The §14.5 invariant is const-locked
    on the schema side; this is the matching transform-side enforcement.
    """
    if not isinstance(sequence, (list, tuple)):
        raise TierEscalationOrderError(
            f"tier_escalation must be a list/tuple, got {type(sequence).__name__}"
        )
    if tuple(sequence) != CANONICAL_TIER_ESCALATION:
        raise TierEscalationOrderError(
            f"tier_escalation order drift: expected {list(CANONICAL_TIER_ESCALATION)}, "
            f"got {list(sequence)} — §14.5 invariant locked"
        )


# ---------------------------------------------------------------------------
# Helpers — content extraction
# ---------------------------------------------------------------------------

def content_hash_hex(content: str | bytes | None) -> str | None:
    """SHA-256 hex digest of body content (lowercase, no prefix). None for
    empty / missing content. Matches the S1 schema pattern `^[a-f0-9]{64}$`.
    """
    if content is None:
        return None
    if isinstance(content, str):
        if not content:
            return None
        data = content.encode("utf-8", errors="replace")
    elif isinstance(content, (bytes, bytearray)):
        if not content:
            return None
        data = bytes(content)
    else:
        return None
    return hashlib.sha256(data).hexdigest()


def content_excerpt(content: str | None, *, limit: int = CONTENT_EXCERPT_MAX_CHARS) -> str:
    """First `limit` chars of the cleaned body. Empty string when missing."""
    if not content or not isinstance(content, str):
        return ""
    if len(content) <= limit:
        return content
    return content[:limit]


def page_size_bytes(content: str | bytes | None) -> int:
    """Byte count of the response body (UTF-8 when text). 0 when missing."""
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.encode("utf-8", errors="replace"))
    if isinstance(content, (bytes, bytearray)):
        return len(content)
    return 0


def _get(d: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if d is None:
        return default
    return d.get(key, default) if isinstance(d, Mapping) else default


def _safe_str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return str(v)


def _safe_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return default


def _normalize_h1_list(raw_h1: Any) -> list[str]:
    """Coerce H1 input into a list[str]. Accepts string, list[str], or None."""
    if raw_h1 is None:
        return []
    if isinstance(raw_h1, str):
        s = raw_h1.strip()
        return [s] if s else []
    if isinstance(raw_h1, (list, tuple)):
        out: list[str] = []
        for h in raw_h1:
            if isinstance(h, str):
                hs = h.strip()
                if hs:
                    out.append(hs)
        return out
    return []


# ---------------------------------------------------------------------------
# Fetch entry shape (caller contract)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FetchEntry:
    """A single competitor URL fetch result, as the transform expects.

    The Scrapling MCP responses can be massaged into this shape by the
    skill orchestrator before calling `transform()`. Tests build these
    directly via from_dict / from_scrapling_envelope.
    """
    url: str
    fetch_method: str | None  # 'get'/'fetch'/'stealthy_fetch' on success; None on all-fail
    tier_attempts: int        # 1..3 on success; 3 on all-fail
    content: str | None
    status_code: int | None
    meta_title: str | None = None
    meta_description: str | None = None
    h1: tuple[str, ...] = ()
    schema_org_count: int = 0
    fetch_duration_ms: int = 0


def fetch_entry_from_dict(data: Mapping[str, Any]) -> FetchEntry:
    """Build a FetchEntry from a permissive dict (used by tests + the skill
    orchestrator after it normalizes Scrapling envelopes).
    """
    if not isinstance(data, Mapping):
        raise CompetitiveAnalysisError(
            f"fetch entry must be a dict, got {type(data).__name__}"
        )
    url = data.get("url") or data.get("url_original")
    if not isinstance(url, str) or not url.strip():
        raise CompetitiveAnalysisError("fetch entry missing 'url'")

    method = data.get("fetch_method")
    if method is not None and method not in CANONICAL_TIER_ESCALATION:
        raise CompetitiveAnalysisError(
            f"fetch_method must be one of {list(CANONICAL_TIER_ESCALATION)}, "
            f"got {method!r}"
        )

    attempts = data.get("tier_attempts")
    attempts_int = _safe_int(attempts, default=1 if method else 3)
    if attempts_int < 1 or attempts_int > 3:
        raise CompetitiveAnalysisError(
            f"tier_attempts must be 1..3, got {attempts_int}"
        )

    return FetchEntry(
        url=url.strip(),
        fetch_method=method,
        tier_attempts=attempts_int,
        content=data.get("content") if isinstance(data.get("content"), str) else None,
        status_code=_safe_int(data.get("status_code"), default=0) or None,
        meta_title=_safe_str_or_none(data.get("meta_title")),
        meta_description=_safe_str_or_none(data.get("meta_description")),
        h1=tuple(_normalize_h1_list(data.get("h1"))),
        schema_org_count=_safe_int(data.get("schema_org_count"), default=0),
        fetch_duration_ms=_safe_int(data.get("fetch_duration_ms"), default=0),
    )


# ---------------------------------------------------------------------------
# Row builder + S1 schema validation
# ---------------------------------------------------------------------------

def _load_s1_schema() -> dict:
    """Load and Draft7-self-check the S1 sub-schema. Cached after first
    successful load (module-level)."""
    global _S1_SCHEMA_CACHE
    try:
        cached = _S1_SCHEMA_CACHE
    except NameError:
        cached = None
    if cached is not None:
        return cached

    if not S1_SCHEMA_PATH.exists():
        raise StagingSchemaError(
            f"S1 sub-schema missing at {S1_SCHEMA_PATH} — ADR-025 activation broken"
        )
    try:
        from jsonschema import Draft7Validator  # noqa: F401 (validate later)
    except ImportError as exc:
        raise StagingSchemaError(
            f"jsonschema not importable — required for S1 validation: {exc}"
        ) from exc

    schema = json.loads(S1_SCHEMA_PATH.read_text("utf-8"))
    Draft7Validator.check_schema(schema)
    _S1_SCHEMA_CACHE = schema  # type: ignore[name-defined,assignment]
    return schema


_S1_SCHEMA_CACHE: dict | None = None  # type: ignore[assignment]


def build_s1_row(
    entry: FetchEntry,
    *,
    snapshot_date: str,
    domain: str | None = None,
) -> dict:
    """Project a FetchEntry into one S1 staging row.

    Args:
        entry: FetchEntry — the fetched competitor URL outcome.
        snapshot_date: ISO 8601 UTC timestamp shared across the batch.
        domain: Optional override; defaults to the host portion of `url`.

    Returns:
        Dict with exactly S1_COLUMNS keys (deterministic order). Raises
        CompetitiveAnalysisError on missing fetch_method (= all-3-fail row;
        the skill orchestrator must NOT call this on durur entries — those
        are excluded from the staging payload, recorded in events.jsonl).
    """
    if entry.fetch_method is None:
        raise CompetitiveAnalysisError(
            "build_s1_row called with fetch_method=None (all-tiers-failed); "
            "exclude durur entries before projection"
        )

    url_n = normalize_url(entry.url)
    dom = (domain or domain_from_url(url_n)).lower()

    chash = content_hash_hex(entry.content)
    excerpt = content_excerpt(entry.content)
    psize = page_size_bytes(entry.content)

    status = entry.status_code if entry.status_code is not None else 200

    row: dict[str, Any] = {
        "snapshot_date": snapshot_date,
        "domain": dom,
        "url_normalized": url_n,
        "url_original": entry.url,
        "fetch_method": entry.fetch_method,
        "tier_attempts": entry.tier_attempts,
        "content_hash": chash if chash is not None else "0" * 64,
        "content_excerpt": excerpt,
        "meta_title": entry.meta_title,
        "meta_description": entry.meta_description,
        "h1": list(entry.h1),
        "schema_org_count": int(entry.schema_org_count),
        "page_size_bytes": int(psize),
        "status_code": int(status),
        "fetch_duration_ms": int(entry.fetch_duration_ms),
    }

    # Project to canonical column order (deterministic; jq-friendly).
    return {k: row[k] for k in S1_COLUMNS}


def validate_s1_row(row: Mapping[str, Any]) -> None:
    """Validate `row` against the S1 sub-schema. Raises StagingSchemaError
    on the FIRST validation error (with absolute path + message).

    Routes through :func:`scripts.validation.validate_schema.build_validator`
    so the S1 schema's 3 `format` keywords — `snapshot_date` (date-time) and
    `url_normalized` / `url_original` (uri) — are ENFORCED with the strict
    UTC '…Z' / scheme-ful checkers (P1-02 / rules/time-discipline.md §8.10).
    A plain `Draft7Validator(schema)` treats `format` as a bare annotation
    and would let a naive/non-UTC snapshot_date or a scheme-less URL into the
    staging payload (codex-audit #19, Batch-B-tail)."""
    schema = _load_s1_schema()
    try:
        from scripts.validation.validate_schema import build_validator
    except ImportError as exc:  # pragma: no cover
        raise StagingSchemaError(
            f"validate_schema.build_validator unavailable: {exc}"
        ) from exc
    validator = build_validator(schema)
    errors = sorted(validator.iter_errors(row), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        raise StagingSchemaError(
            f"S1 row schema fail at {list(first.absolute_path) or '<root>'}: "
            f"{first.message}"
        )


# ---------------------------------------------------------------------------
# Competitors_domain helper (DFS)
# ---------------------------------------------------------------------------

def extract_competitor_domains(raw_competitors_domain: dict | None) -> list[str]:
    """Pull the competitor `domain` strings out of a DFS competitors_domain
    response. Tolerates both REST envelope (tasks[0].result[0].items) and
    flat wrapper (top-level items) via the canonical
    :func:`scripts.util.dfs_response.normalize_dfs_response` helper.
    Returns deduplicated lowercase domains in input order. Adapt-wraps
    :class:`DFSResponseError` into :class:`CompetitiveAnalysisError`
    so callers see a domain-specific exception (paterni K-01 reuse).
    """
    if raw_competitors_domain is None:
        return []
    try:
        items = _normalize_dfs_response(
            raw_competitors_domain,
            endpoint_type="keyword",
            expected_endpoint="dataforseo_labs_google_competitors_domain",
        )
    except _DFSResponseError as exc:
        raise CompetitiveAnalysisError(str(exc)) from exc
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        d = it.get("domain") or it.get("competitor_domain")
        if isinstance(d, str) and d.strip():
            ds = d.strip().lower()
            if ds not in seen:
                seen.add(ds)
                out.append(ds)
    return out


# ---------------------------------------------------------------------------
# Budget pre-flight (mandatory for paid MCPs)
# ---------------------------------------------------------------------------

def estimate_credits(competitor_domain_calls: int) -> float:
    """Estimate DataForSEO credits for a competitive-analysis run.

    competitors_domain ~ 5 credits per call (one batched lookup typically
    suffices per target domain). Scrapling is free.
    """
    if competitor_domain_calls <= 0:
        return 0.0
    return float(competitor_domain_calls) * CREDITS_PER_COMPETITORS_DOMAIN_CALL


def preflight_budget(
    *,
    estimated_credits: float,
    project_config_path: str,
    events_path: str,
) -> dict:
    """Run the §16.8 budget pre-flight via the in-process check_budget
    helpers and DURUR if exceeded. Mirrors on_page_audit / dfs_pull
    pattern — exit 0 → pass; exit 1 / module unavailable → BudgetExceededError.
    """
    try:
        from scripts.budget import check_budget as _cb
    except ImportError as exc:
        raise BudgetExceededError(
            "scripts.budget.check_budget unavailable — pre-flight "
            f"integration is mandatory for paid MCPs ({exc})"
        ) from exc

    cfg_path = Path(project_config_path)
    evt_path = Path(events_path)

    try:
        budget = _cb._load_budget(cfg_path)  # type: ignore[attr-defined]
    except SystemExit as exc:
        raise BudgetExceededError(
            f"budget pre-flight: project-config unreadable ({cfg_path}): "
            f"exit={exc.code}"
        ) from exc

    used = _cb._sum_last_24h(  # type: ignore[attr-defined]
        evt_path, datetime.now(timezone.utc),
    )
    projected = float(used) + float(estimated_credits)
    payload = {
        "budget_per_day": int(budget),
        "used_24h": used,
        "estimated_credits": float(estimated_credits),
        "projected_used": projected,
        "remaining_after": float(budget) - projected,
        "exceeded": projected > float(budget),
    }
    if payload["exceeded"]:
        raise BudgetExceededError(
            f"budget pre-flight FAIL: projected={projected:.2f} > "
            f"budget={budget} (used_24h={used}, estimate={estimated_credits})"
        )
    return payload


# ---------------------------------------------------------------------------
# Bulk health check
# ---------------------------------------------------------------------------

def assert_bulk_healthy(
    entries: Sequence[FetchEntry],
    *,
    threshold: float = BULK_UNHEALTHY_THRESHOLD,
) -> None:
    """DURUR if more than `threshold` of the entries failed all 3 tiers.

    A FetchEntry with fetch_method=None is treated as all-fail. The
    threshold is exclusive — exactly half is acceptable, more than half
    is not. Empty input is accepted (0/0 → ratio 0.0).
    """
    total = len(entries)
    if total == 0:
        return
    failed = sum(1 for e in entries if e.fetch_method is None)
    ratio = failed / total
    if ratio > threshold:
        raise BulkUnhealthyError(
            f"competitor batch unhealthy: {failed}/{total} ({ratio:.0%}) "
            f"failed all tiers — threshold {threshold:.0%}"
        )


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    entries: Sequence[FetchEntry | Mapping[str, Any]],
    *,
    project_slug: str,
    snapshot_date: str | None = None,
    raw_competitors_domain: dict | None = None,
    tier_escalation: Sequence[str] = CANONICAL_TIER_ESCALATION,
    bulk_threshold: float = BULK_UNHEALTHY_THRESHOLD,
) -> dict:
    """Project Scrapling fetch outcomes into S1-validated staging rows.

    Args:
        entries: Iterable of FetchEntry instances OR permissive dicts
            (each dict is run through `fetch_entry_from_dict`).
        project_slug: Project slug; embedded in the meta block.
        snapshot_date: ISO 8601 UTC timestamp shared across the batch
            (defaults to now). Microsecond + +00:00 offset preferred.
        raw_competitors_domain: Optional DFS competitors_domain raw JSON;
            used to populate `meta.competitor_domains`.
        tier_escalation: Caller-supplied tier sequence; MUST equal the
            canonical §14.5 order or TierEscalationOrderError is raised.
        bulk_threshold: Override the 50% bulk-unhealthy threshold.

    Returns:
        {
          "rows": [<S1 row>, ...],     # only successful (fetch_method≠None) entries
          "durur_urls": [<url>, ...],  # all-fail entries excluded from rows
          "meta": {...},
        }

    Raises:
        TierEscalationOrderError: tier_escalation order drift.
        StagingSchemaError:       any projected row fails S1 validation.
        BulkUnhealthyError:       >threshold of entries are all-tiers-fail.
        CompetitiveAnalysisError: malformed inputs.
    """
    if not isinstance(project_slug, str) or not project_slug.strip():
        raise CompetitiveAnalysisError("project_slug must be a non-empty string")

    # §14.5 invariant guard — refuse non-canonical sequences early.
    assert_canonical_tier_order(tier_escalation)

    ts = snapshot_date or _utc_iso_microseconds()

    # Coerce permissive dicts into FetchEntry.
    coerced: list[FetchEntry] = []
    for e in entries:
        if isinstance(e, FetchEntry):
            coerced.append(e)
        elif isinstance(e, Mapping):
            coerced.append(fetch_entry_from_dict(e))
        else:
            raise CompetitiveAnalysisError(
                f"entry must be FetchEntry or dict, got {type(e).__name__}"
            )

    # Bulk health gate — DURUR before any S1 projection.
    assert_bulk_healthy(coerced, threshold=bulk_threshold)

    rows: list[dict] = []
    durur_urls: list[str] = []
    for entry in coerced:
        if entry.fetch_method is None:
            # All-3-tiers-fail; recorded as durur_urls and excluded from
            # staging. The skill orchestrator emits a separate events.jsonl
            # entry per durur URL (per the brief).
            durur_urls.append(normalize_url(entry.url))
            continue
        row = build_s1_row(entry, snapshot_date=ts)
        validate_s1_row(row)   # DURUR on schema fail (StagingSchemaError)
        rows.append(row)

    competitor_domains = extract_competitor_domains(raw_competitors_domain)

    return {
        "rows": rows,
        "durur_urls": durur_urls,
        "meta": {
            "project_slug": project_slug,
            "snapshot_date": ts,
            "row_count": len(rows),
            "durur_count": len(durur_urls),
            "competitor_domain_count": len(competitor_domains),
            "competitor_domains": competitor_domains,
            "tier_escalation": list(CANONICAL_TIER_ESCALATION),
            "schema_id": "https://platinum-seo-engine/templates/scrapling/"
                          "S1_competitor_snapshot.schema.json",
        },
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def staging_filename(*, date: str, project_slug: str) -> str:
    """Canonical filename: `competitive_analysis_{date}_{slug}.json`
    (mirrors scrapling_/dfs_ staging conventions)."""
    return f"competitive_analysis_{date}_{project_slug}.json"


def write_staging_json(
    rows: Sequence[Mapping[str, Any]],
    output_path: Path,
) -> Path:
    """Write the S1 rows array to disk. Atomic-ish: tmp + rename. Validates
    every row against S1 again before write (defensive — never persists a
    drifted row)."""
    output_path = Path(output_path)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StagingPathError(
            f"cannot create staging directory {output_path.parent}: {exc}"
        ) from exc

    for r in rows:
        validate_s1_row(r)

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(list(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(output_path)
    return output_path


def write_inbox_raw(
    payload: Any,
    inbox_path: Path,
) -> Path:
    """Persist a raw MCP envelope to an inbox path. Creates parent dir
    on-demand. Inbox path failure → InboxPathError (DURUR)."""
    inbox_path = Path(inbox_path)
    try:
        inbox_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise InboxPathError(
            f"cannot create inbox directory {inbox_path.parent}: {exc}"
        ) from exc
    inbox_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return inbox_path


# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------

def _utc_iso_microseconds() -> str:
    """UTC ISO 8601 with microsecond precision and the canonical '…Z' suffix.

    Storage-layer canonical form per rules/time-discipline.md §8.10 (mirrors
    events_writer._utc_iso_z / scrapling_ops). The S1 sub-schema's
    `snapshot_date` declares `format: date-time`, now ENFORCED by the strict
    UTC checker in :func:`validate_s1_row`; a '+00:00' offset (the prior
    isoformat() output) is rejected there, so the producer emits '…Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Scrapling envelope adapter
# ---------------------------------------------------------------------------

def fetch_entries_from_scrapling_envelope(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    default_fetch_method: str = "stealthy_fetch",
) -> list[FetchEntry]:
    """Adapt a Scrapling bulk_stealthy_fetch envelope into FetchEntry list.

    Tolerates the per-URL-list shape used by mcp__ScraplingServer__bulk_
    stealthy_fetch (our primary input):
      [{ "url": "...", "content": "...", "status_code": 200, "meta_title":
         "...", "h1": [...], ... }, ...]
    OR a wrapped envelope `{"results": [...]}` / `{"items": [...]}`.

    Each item supplies fetch_method/tier_attempts. When absent we default
    to (default_fetch_method, attempts=1) — reflecting the bulk_stealthy_
    fetch reality (tier 2 directly).
    """
    items: list[Mapping[str, Any]]
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, Mapping)]
    elif isinstance(payload, Mapping):
        cand = (
            payload.get("results")
            or payload.get("items")
            or payload.get("data")
        )
        if isinstance(cand, list):
            items = [x for x in cand if isinstance(x, Mapping)]
        else:
            # Single-URL envelope — wrap as one-item list.
            items = [payload] if "url" in payload else []
    else:
        raise CompetitiveAnalysisError(
            f"scrapling envelope must be dict/list, got {type(payload).__name__}"
        )

    out: list[FetchEntry] = []
    for it in items:
        method = it.get("fetch_method") or default_fetch_method
        if method not in CANONICAL_TIER_ESCALATION and method is not None:
            method = default_fetch_method
        out.append(fetch_entry_from_dict({**it, "fetch_method": method}))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="competitive_analysis_transform.py",
        description=(
            "Transform Scrapling bulk_stealthy_fetch (+ optional DFS "
            "competitors_domain) raw JSON → S1-validated staging rows."
        ),
    )
    p.add_argument(
        "--raw-scrapling", required=True,
        help="Path to Scrapling bulk_stealthy_fetch raw JSON envelope.",
    )
    p.add_argument(
        "--raw-competitors-domain", default=None,
        help="Optional path to DFS competitors_domain raw JSON.",
    )
    p.add_argument(
        "--project-slug", required=True,
        help="Project slug embedded in staging meta + filename.",
    )
    p.add_argument(
        "--snapshot-date", default=None,
        help="ISO 8601 UTC snapshot timestamp; defaults to now.",
    )
    p.add_argument(
        "--output-dir", default=None,
        help="If set, write competitive_analysis_{date}_{slug}.json here.",
    )
    p.add_argument(
        "--date", default=None,
        help="Filename date (YYYY-MM-DD); defaults to today UTC.",
    )
    return p.parse_args(list(argv))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    scr_path = Path(args.raw_scrapling)
    if not scr_path.exists():
        print(f"raw scrapling JSON not found: {scr_path}", file=sys.stderr)
        return 2
    raw_scr = _read_json(scr_path)

    raw_comp: dict | None = None
    if args.raw_competitors_domain:
        cd_path = Path(args.raw_competitors_domain)
        if cd_path.exists():
            raw_comp = _read_json(cd_path)

    try:
        entries = fetch_entries_from_scrapling_envelope(raw_scr)
        result = transform(
            entries,
            project_slug=args.project_slug,
            snapshot_date=args.snapshot_date,
            raw_competitors_domain=raw_comp,
        )
    except (
        CompetitiveAnalysisError,
    ) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    summary: dict[str, Any] = {"meta": result["meta"]}
    if args.output_dir:
        date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_dir = Path(args.output_dir)
        out_path = out_dir / staging_filename(date=date_str, project_slug=args.project_slug)
        try:
            written = write_staging_json(result["rows"], out_path)
        except (StagingSchemaError, StagingPathError) as exc:
            print(f"staging write failed: {exc}", file=sys.stderr)
            return 1
        summary["staging_path"] = str(written.resolve())
    else:
        summary["rows"] = result["rows"]
        summary["durur_urls"] = result["durur_urls"]

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "CANONICAL_TIER_ESCALATION",
    "S1_SCHEMA_PATH",
    "S1_REQUIRED_KEYS",
    "S1_COLUMNS",
    "CREDITS_PER_COMPETITORS_DOMAIN_CALL",
    "BULK_UNHEALTHY_THRESHOLD",
    "CompetitiveAnalysisError",
    "TierEscalationOrderError",
    "StagingSchemaError",
    "BulkUnhealthyError",
    "BudgetExceededError",
    "StagingPathError",
    "InboxPathError",
    "FetchEntry",
    "normalize_url",
    "domain_from_url",
    "assert_canonical_tier_order",
    "content_hash_hex",
    "content_excerpt",
    "page_size_bytes",
    "fetch_entry_from_dict",
    "fetch_entries_from_scrapling_envelope",
    "build_s1_row",
    "validate_s1_row",
    "extract_competitor_domains",
    "estimate_credits",
    "preflight_budget",
    "assert_bulk_healthy",
    "transform",
    "staging_filename",
    "write_staging_json",
    "write_inbox_raw",
    "main",
)
