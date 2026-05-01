#!/usr/bin/env python3
"""
on_page_audit_transform.py — pure transform: DFS content_parsing JSON
(+ optional GSC search_analytics) → master.xlsx#on_page_audit rows.

Reads the raw response of mcp__dataforseo__on_page_content_parsing (per
URL: title, meta_description, h1[]), optionally cross-references the raw
mcp__gsc__search_analytics payload to determine the top performing query
per URL (by clicks desc, impressions tie-break), and emits 8-column rows
shaped for master.xlsx#on_page_audit (see schemas/master-excel.schema.json
required_columns: url, target_query, impressions_30d, clicks_30d,
in_title, in_meta, in_h1, action).

URL canonicalization (D-03 invariant): both DFS and GSC URL fields run
through `_normalize_url()` before joining, so a trailing slash, a
fragment, or a tracking param doesn't desync the cross-source merge.

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - Idempotent: same inputs → same output.

Errors raised:
  - ContentParsingDriftError: DFS payload missing required fields
    (title / meta_description / h1) → upstream schema drift; STOP.
  - OnPageAuditError: malformed input (not a dict, etc.).
  - BudgetExceededError: subprocess `check_budget.py --check` exited 1.
    The skill caller invokes the budget pre-flight; this module exposes
    the helper so tests can mock the boundary cleanly.

Refs: schemas/master-excel.schema.json (on_page_audit sheet),
schemas/cross-sheet-invariants.json (D-03 URL canonicalization),
schemas/events.schema.json (source.kind=dataforseo_mcp + gsc_mcp,
cost.credits), spec §16.5 (raw inbox + transform), §16.8 (budget).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import (
    parse_qsl,
    quote,
    urlencode,
    urlsplit,
    urlunsplit,
)

# ---------------------------------------------------------------------------
# Constants — schema-aligned column names (master-excel.schema.json#on_page_audit)
# ---------------------------------------------------------------------------

ON_PAGE_AUDIT_COLUMNS = (
    "url",
    "target_query",
    "impressions_30d",
    "clicks_30d",
    "in_title",
    "in_meta",
    "in_h1",
    "action",
)

# DFS content_parsing per-URL credit estimate (paid).
CREDITS_PER_URL_CONTENT_PARSING = 3.0

# Default scheme ports we strip from netloc (D-03).
_DEFAULT_PORTS = {"http": "80", "https": "443"}

# Tracking-style query params we drop entirely (D-03 cleanup).
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid", "msclkid",
})


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class OnPageAuditError(Exception):
    """Base error for on-page-audit transform failures (DURUR)."""


class ContentParsingDriftError(OnPageAuditError):
    """DFS on_page_content_parsing payload missing required fields."""


class BudgetExceededError(OnPageAuditError):
    """Budget pre-flight (`check_budget.py --check`) exited non-zero."""


class CrossRefMismatchError(OnPageAuditError):
    """DFS and GSC URL sets are disjoint after D-03 normalization — likely
    drift signal. Caller decides whether to escalate or fall back to
    'no cross-ref' mode (documented design choice — see SKILL.md DURUR #4).
    """


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant)
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """
    Normalize a URL per D-03 invariant.

    Rules (deterministic, idempotent):
      1. Trim surrounding whitespace.
      2. Lowercase scheme + host (path/query case-preserved).
      3. IDN host → punycode (idna ascii) when non-ASCII.
      4. Strip default port (:80 for http, :443 for https).
      5. Trailing slash on path: keep root '/' as-is, strip on others.
      6. Drop fragment (everything after '#').
      7. Drop tracking params (utm_*, gclid, fbclid, ...).
      8. Sort remaining query params by key, stable for equal keys.

    Raises OnPageAuditError on completely unparseable input (empty, no
    scheme, non-string).
    """
    if not isinstance(url, str):
        raise OnPageAuditError(
            f"url must be a string, got {type(url).__name__}"
        )
    raw = url.strip()
    if not raw:
        raise OnPageAuditError("url is empty")

    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if not scheme:
        raise OnPageAuditError(f"url missing scheme: {url!r}")

    host = parts.hostname or ""
    if host:
        try:
            host_ascii = host.encode("idna").decode("ascii").lower()
        except (UnicodeError, UnicodeDecodeError):
            host_ascii = host.lower()
    else:
        host_ascii = ""

    port = parts.port
    if port is not None and str(port) != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host_ascii}:{port}"
    else:
        netloc = host_ascii

    if parts.username is not None:
        user = quote(parts.username, safe="")
        if parts.password is not None:
            user = f"{user}:{quote(parts.password, safe='')}"
        netloc = f"{user}@{netloc}"

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
        if not path:
            path = "/"

    qs_pairs = parse_qsl(parts.query, keep_blank_values=True)
    cleaned = [
        (k, v) for (k, v) in qs_pairs
        if k.lower() not in _TRACKING_PARAMS
    ]
    cleaned.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(cleaned, doseq=False)

    return urlunsplit((scheme, netloc, path, query, ""))


# ---------------------------------------------------------------------------
# Cross-source data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentParsingRow:
    url_normalized: str
    title: str
    meta_description: str
    h1: tuple[str, ...]


@dataclass(frozen=True)
class GscRow:
    url_normalized: str
    query: str
    clicks: int
    impressions: int


# ---------------------------------------------------------------------------
# DFS content_parsing parsing
# ---------------------------------------------------------------------------

def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _safe_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return 0


def _extract_content_parsing_items(raw: dict) -> list[dict]:
    """Tolerate two DFS shapes — REST envelope and flat wrapper."""
    if not isinstance(raw, dict):
        raise OnPageAuditError(
            f"raw must be a dict, got {type(raw).__name__}"
        )
    tasks = raw.get("tasks")
    if isinstance(tasks, list) and tasks:
        result = (tasks[0] or {}).get("result")
        if isinstance(result, list) and result:
            items = (result[0] or {}).get("items")
            if isinstance(items, list):
                return items
            # Single page_content envelope — wrap into a one-item list so
            # downstream loop handles it uniformly.
            page_content = (result[0] or {}).get("page_content")
            if isinstance(page_content, dict):
                return [{"url": (result[0] or {}).get("url", ""),
                         "page_content": page_content,
                         "meta": (result[0] or {}).get("meta", {})}]
    items = raw.get("items")
    if isinstance(items, list):
        return items
    if isinstance(raw.get("page_content"), dict):
        return [raw]
    return []


def _parse_content_parsing(raw: dict) -> list[ContentParsingRow]:
    """Parse DFS on_page_content_parsing into ContentParsingRow per URL.

    Drift detection is strict: an item missing url/title/meta/h1 raises
    ContentParsingDriftError so the caller cannot silently emit empty
    audit rows from a broken upstream.
    """
    items = _extract_content_parsing_items(raw)
    out: list[ContentParsingRow] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue

        url_raw = entry.get("url") or entry.get("page_url") or ""
        if not url_raw:
            raise ContentParsingDriftError(
                "content_parsing item missing 'url' field"
            )

        meta_block = entry.get("meta") or {}
        page_content = entry.get("page_content") or {}

        title = entry.get("title")
        if title is None:
            title = meta_block.get("title")
        if title is None:
            title = page_content.get("title")
        if title is None:
            raise ContentParsingDriftError(
                f"content_parsing item missing 'title' field for {url_raw!r}"
            )

        meta_description = entry.get("meta_description")
        if meta_description is None:
            meta_description = meta_block.get("description")
        if meta_description is None:
            meta_description = page_content.get("meta_description")
        if meta_description is None:
            raise ContentParsingDriftError(
                f"content_parsing item missing 'meta_description' for {url_raw!r}"
            )

        h1_raw = entry.get("h1")
        if h1_raw is None:
            h1_raw = page_content.get("h1")
        if h1_raw is None:
            htags = (page_content.get("htags") or {})
            if isinstance(htags, dict):
                h1_raw = htags.get("h1")
        if h1_raw is None:
            raise ContentParsingDriftError(
                f"content_parsing item missing 'h1' for {url_raw!r}"
            )

        if isinstance(h1_raw, str):
            h1_list = (h1_raw,) if h1_raw else tuple()
        elif isinstance(h1_raw, (list, tuple)):
            h1_list = tuple(_safe_str(h) for h in h1_raw)
        else:
            h1_list = tuple()

        out.append(ContentParsingRow(
            url_normalized=_normalize_url(url_raw),
            title=_safe_str(title),
            meta_description=_safe_str(meta_description),
            h1=h1_list,
        ))
    return out


# ---------------------------------------------------------------------------
# GSC search_analytics parsing (cross-ref)
# ---------------------------------------------------------------------------

def _parse_gsc_rows(raw: dict | None) -> dict[str, GscRow]:
    """Index GSC search_analytics rows by normalized URL → top query.

    Top query = max(clicks), tie-break impressions desc, then query asc
    (deterministic). Returns {} if raw is None or malformed (graceful
    degrade — see SKILL.md DURUR #9).
    """
    if not raw or not isinstance(raw, dict):
        return {}
    rows = raw.get("rows") or raw.get("data") or []
    if not isinstance(rows, list):
        return {}

    # Group by normalized URL → list of (query, clicks, impressions).
    by_url: dict[str, list[tuple[str, int, int]]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        keys = r.get("keys") or []
        if not keys or len(keys) < 1:
            continue
        # Convention: dimensions=['page', 'query'] OR ['page'] only.
        # We accept either: keys[0]=url ALWAYS, keys[1]=query if present.
        url_raw = keys[0]
        try:
            url_n = _normalize_url(str(url_raw))
        except OnPageAuditError:
            continue
        query = str(keys[1]) if len(keys) > 1 else ""
        clicks = _safe_int(r.get("clicks"))
        impressions = _safe_int(r.get("impressions"))
        by_url.setdefault(url_n, []).append((query, clicks, impressions))

    out: dict[str, GscRow] = {}
    for url_n, candidates in by_url.items():
        # Sort: clicks desc, impressions desc, query asc.
        candidates.sort(key=lambda c: (-c[1], -c[2], c[0]))
        query, clicks, impressions = candidates[0]
        out[url_n] = GscRow(
            url_normalized=url_n,
            query=query,
            clicks=clicks,
            impressions=impressions,
        )
    return out


# ---------------------------------------------------------------------------
# Audit detection
# ---------------------------------------------------------------------------

def _detect_presence(target_query: str, haystack: str) -> bool:
    """Case-insensitive substring presence; empty target → False."""
    if not target_query:
        return False
    return target_query.lower() in (haystack or "").lower()


def _detect_in_h1(target_query: str, h1_list: Iterable[str]) -> bool:
    if not target_query:
        return False
    needle = target_query.lower()
    return any(needle in (h or "").lower() for h in h1_list)


def _action_for(
    target_query: str,
    in_title: bool,
    in_meta: bool,
    in_h1: bool,
    clicks_30d: int,
) -> str:
    """Heuristic action recommendation per the brief."""
    if not target_query:
        return "no GSC data — investigate target intent"
    if in_title and in_meta and in_h1 and clicks_30d > 0:
        return "monitor"
    if in_title and not in_meta and not in_h1:
        return "add to meta + H1"
    if not in_title and not in_meta and not in_h1:
        return "rewrite meta cluster"
    return "patch missing slots"


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    raw_content_parsing: dict,
    *,
    raw_gsc: dict | None = None,
    strict_cross_ref: bool = False,
) -> dict:
    """
    Build master.xlsx#on_page_audit rows from a DFS content_parsing
    payload, optionally cross-referenced with GSC search_analytics.

    Args:
        raw_content_parsing: parsed JSON of mcp__dataforseo__on_page_content_parsing.
        raw_gsc: optional parsed JSON of mcp__gsc__search_analytics
                 (dimensions=['page','query'] or ['page']).
        strict_cross_ref: if True and GSC payload provided but URL sets
                          disjoint after normalization → CrossRefMismatchError.
                          If False (default), fall back to no-cross-ref
                          mode (documented design choice — DURUR #4).

    Returns:
        {"on_page_audit": [...], "meta": {...}}.
    """
    if not isinstance(raw_content_parsing, dict):
        raise OnPageAuditError(
            f"raw_content_parsing must be a dict, "
            f"got {type(raw_content_parsing).__name__}"
        )

    cp_rows = _parse_content_parsing(raw_content_parsing)
    gsc_index = _parse_gsc_rows(raw_gsc)

    cross_ref_used = bool(gsc_index)
    cross_ref_mismatch = False

    if cross_ref_used:
        cp_url_set = {r.url_normalized for r in cp_rows}
        gsc_url_set = set(gsc_index.keys())
        if cp_url_set and gsc_url_set and cp_url_set.isdisjoint(gsc_url_set):
            cross_ref_mismatch = True
            if strict_cross_ref:
                raise CrossRefMismatchError(
                    "DFS content_parsing URL set is disjoint from GSC "
                    "search_analytics URL set after D-03 normalization — "
                    "possible upstream drift (e.g. www vs non-www host)."
                )
            # Graceful fall-back to no-cross-ref mode.
            gsc_index = {}
            cross_ref_used = False

    out_rows: list[dict] = []
    for cp in cp_rows:
        gsc = gsc_index.get(cp.url_normalized)
        if gsc:
            target_query = gsc.query
            impressions_30d = gsc.impressions
            clicks_30d = gsc.clicks
        else:
            target_query = ""
            impressions_30d = 0
            clicks_30d = 0

        in_title = _detect_presence(target_query, cp.title)
        in_meta = _detect_presence(target_query, cp.meta_description)
        in_h1 = _detect_in_h1(target_query, cp.h1)

        # If cross-ref was attempted but no GSC for this URL, mark the
        # action accordingly so the operator can disambiguate "no data
        # available" from "data exists, query missing on page".
        if cross_ref_used and gsc is None and target_query == "":
            action = "no GSC available for this URL"
        else:
            action = _action_for(
                target_query, in_title, in_meta, in_h1, clicks_30d,
            )

        out_rows.append({
            "url": cp.url_normalized,
            "target_query": target_query,
            "impressions_30d": int(impressions_30d),
            "clicks_30d": int(clicks_30d),
            "in_title": bool(in_title),
            "in_meta": bool(in_meta),
            "in_h1": bool(in_h1),
            "action": action,
        })

    # Sort: impressions_30d desc, then url asc for determinism.
    out_rows.sort(key=lambda r: (-r["impressions_30d"], r["url"]))

    # Schema-shape projection — drop any incidental keys, lock column order.
    on_page_audit_rows = [
        {k: r[k] for k in ON_PAGE_AUDIT_COLUMNS}
        for r in out_rows
    ]

    return {
        "on_page_audit": on_page_audit_rows,
        "meta": {
            "input_url_count": len(cp_rows),
            "row_count": len(on_page_audit_rows),
            "cross_ref_used": cross_ref_used,
            "cross_ref_mismatch": cross_ref_mismatch,
            "gsc_url_count": len(gsc_index),
        },
    }


# ---------------------------------------------------------------------------
# Budget pre-flight (subprocess boundary; tests mock this)
# ---------------------------------------------------------------------------

def estimate_credits(url_count: int) -> float:
    """Estimate DFS credits for a content_parsing run.

    on_page_content_parsing: ~3 credits per URL (paid).
    """
    if url_count <= 0:
        return 0.0
    return float(url_count) * CREDITS_PER_URL_CONTENT_PARSING


def preflight_budget(
    *,
    estimated_credits: float,
    project_config_path: str,
    events_path: str,
) -> dict:
    """Run the §16.8 budget pre-flight via the in-process check_budget
    helpers and DURUR if exceeded.

    Returns the parsed budget envelope on PASS. Raises BudgetExceededError
    on FAIL (estimate + 24h usage > daily cap).

    Mirrors `scripts.ingestion.dfs_pull.preflight_budget` (same boundary
    semantics: exit 0 → pass; exit 1 → BudgetExceededError; module
    unavailable → DURUR — pre-flight is mandatory for paid MCPs).
    """
    try:
        from scripts.budget import check_budget as _cb
    except ImportError as exc:
        raise BudgetExceededError(
            "scripts.budget.check_budget unavailable — pre-flight "
            f"integration is mandatory for paid MCPs ({exc})"
        ) from exc

    from datetime import datetime, timezone

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
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="on_page_audit_transform.py",
        description=(
            "Transform DFS on_page_content_parsing JSON (+ optional GSC "
            "search_analytics) → master.xlsx#on_page_audit rows."
        ),
    )
    p.add_argument(
        "--raw-content-parsing", required=True,
        help="Path to raw mcp__dataforseo__on_page_content_parsing JSON.",
    )
    p.add_argument(
        "--raw-gsc", default=None,
        help="Optional path to mcp__gsc__search_analytics JSON (cross-ref).",
    )
    p.add_argument(
        "--strict-cross-ref", action="store_true",
        help="Raise CrossRefMismatchError when DFS/GSC URL sets disjoint.",
    )
    p.add_argument(
        "--output-dir", default=None,
        help="If set, write on_page_audit.json here.",
    )
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    cp_path = Path(args.raw_content_parsing)
    if not cp_path.exists():
        print(f"raw content_parsing JSON not found: {cp_path}", file=sys.stderr)
        return 2
    raw_cp = _read_json(cp_path)

    raw_gsc: dict | None = None
    if args.raw_gsc:
        gsc_path = Path(args.raw_gsc)
        if gsc_path.exists():
            try:
                raw_gsc = _read_json(gsc_path)
            except (OSError, json.JSONDecodeError):
                raw_gsc = None

    try:
        result = transform(
            raw_cp,
            raw_gsc=raw_gsc,
            strict_cross_ref=args.strict_cross_ref,
        )
    except OnPageAuditError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "on_page_audit.json"
        out_path.write_text(
            json.dumps(result["on_page_audit"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "on_page_audit_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "ON_PAGE_AUDIT_COLUMNS",
    "CREDITS_PER_URL_CONTENT_PARSING",
    "OnPageAuditError",
    "ContentParsingDriftError",
    "BudgetExceededError",
    "CrossRefMismatchError",
    "_normalize_url",
    "transform",
    "estimate_credits",
    "preflight_budget",
    "main",
)
