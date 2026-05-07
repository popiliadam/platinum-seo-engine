#!/usr/bin/env python3
"""
cannibalization_transform.py — pure transform: GSC search_analytics JSON →
schema-shaped rows for master.xlsx#cannibalization.

Reads the raw response of mcp__gsc__search_analytics (dimensions=['query',
'page']), normalizes URLs per D-03 (lowercase scheme+host, strip default
ports, collapse trailing slash except root, sort+filter query string,
drop fragment, IDN -> punycode), groups rows by (lowercase) query, and
emits one cannibalization row per query that maps to ≥2 distinct URLs
each with impressions ≥ K (default 10). Output rows shaped per the 7
schema-locked columns in schemas/master-excel.schema.json#cannibalization
(conflict_pair, overlapping_queries_est, total_impact, resolution, note,
status, priority).

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - Idempotent: same input -> same output. Re-running with the same
    --raw file writes byte-identical output.

CLI:
  python3 scripts/discovery/cannibalization_transform.py \
      --raw inbox/gsc/2026-04-30-search_analytics-cannibalization-{slug}.json \
      [--min-impressions 10] \
      [--output-dir .]

Stdout: JSON {"cannibalization": [...], "meta": {...}}.
With --output-dir set: also writes cannibalization.json into that dir
and prints the absolute path.

Refs: schemas/master-excel.schema.json#cannibalization (7 required_columns
+ statusEnum), schemas/gsc-tool-mapping.schema.json (D-03 URL normalization
invariant), schemas/events.schema.json (target_excel_sheet=cannibalization
+ source.kind=gsc_mcp), spec §16.5 (raw JSON inbox + transform stage).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when invoked as a CLI module.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.util.url_normalize import (  # noqa: E402  (sys.path mutation)
    URLNormalizeError as _URLNormalizeError,
    normalize_url as _canonical_normalize_url,
)

# ---------------------------------------------------------------------------
# Constants — schema-aligned column names
# (master-excel.schema.json#cannibalization required_columns)
# ---------------------------------------------------------------------------

CANNIBALIZATION_COLUMNS = (
    "conflict_pair",
    "overlapping_queries_est",
    "total_impact",
    "resolution",
    "note",
    "status",
    "priority",
)

# statusEnum allowed values (master-excel.schema.json#/definitions/statusEnum).
_STATUS_ENUM = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})

# Default K — minimum impressions per page to qualify as a real conflict.
_DEFAULT_MIN_IMPRESSIONS = 10

# ---------------------------------------------------------------------------
# Exceptions (DURUR-style explicit)
# ---------------------------------------------------------------------------

class CannibalizationError(ValueError):
    """Base class for explicit DURUR conditions in cannibalization transform."""


class RowSchemaError(CannibalizationError):
    """A produced row drifts from the master-excel cannibalization schema."""


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant)
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Adapter wrapping :class:`URLNormalizeError` into
    :class:`CannibalizationError` so call-site DURUR semantics stay
    backward-compatible after K-01 dedup (v1.5-Phase-1 Tier 1).
    """
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError as exc:
        raise CannibalizationError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _PageRow:
    """A single (query, page) GSC row after URL normalization."""
    query: str
    url: str
    clicks: int
    impressions: int
    position: float


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract_query_and_page(keys: list) -> tuple[str | None, str | None]:
    """
    Find the query and page within a GSC row's `keys` array.

    GSC search_analytics returns `keys` in the same order as the
    `dimensions` request param — but the caller controls order, so we
    locate them defensively: the page is the first http(s)://... entry,
    the query is the first remaining string entry.
    """
    if not isinstance(keys, list):
        return None, None
    page: str | None = None
    query: str | None = None
    for k in keys:
        if not isinstance(k, str):
            continue
        ks = k.strip()
        if not ks:
            continue
        if (ks[:7].lower() == "http://" or ks[:8].lower() == "https://") and page is None:
            page = ks
        elif query is None and not (ks[:7].lower() == "http://" or ks[:8].lower() == "https://"):
            query = ks
    return query, page


def _parse_rows(payload: dict) -> list[_PageRow]:
    """
    Parse a search_analytics-shape payload into normalized _PageRow list.

    Tolerates payload['rows'] OR payload['data'] envelopes. Skips entries
    missing query, page, or with un-normalizable URL. Raises
    CannibalizationError if the rows container is the wrong type.
    """
    if payload is None:
        return []
    rows = payload.get("rows") or payload.get("data") or []
    if not isinstance(rows, list):
        raise CannibalizationError(
            f"search_analytics payload 'rows' must be a list, "
            f"got {type(rows).__name__}"
        )

    out: list[_PageRow] = []
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        keys = entry.get("keys") or []
        query, page = _extract_query_and_page(keys)
        if not query or not page:
            continue
        try:
            url_n = normalize_url(page)
        except CannibalizationError:
            continue
        clicks = _safe_int(entry.get("clicks")) or 0
        impressions = _safe_int(entry.get("impressions")) or 0
        position = _safe_float(entry.get("position")) or 0.0
        out.append(_PageRow(
            query=query.strip().lower(),
            url=url_n,
            clicks=int(clicks),
            impressions=int(impressions),
            position=float(position),
        ))
    return out


# ---------------------------------------------------------------------------
# Resolution + priority heuristics
# ---------------------------------------------------------------------------

def _resolution_label(positions: list[float]) -> str:
    """
    Heuristic for the cannibalization resolution column:

      - position spread (max - min) > 5  → "consolidate to top URL"
        (one URL clearly outranks; merge weaker into it)
      - all positions < 10               → "intent split investigation"
        (multiple URLs all in top-10 → likely intent fragmentation)
      - otherwise                        → "topical merge candidate"
        (modest overlap; consider topical consolidation)
    """
    if not positions:
        return "topical merge candidate"
    spread = max(positions) - min(positions)
    if spread > 5:
        return "consolidate to top URL"
    if all(p < 10 for p in positions):
        return "intent split investigation"
    return "topical merge candidate"


def _priority_label(total_clicks: int) -> str:
    """
    Priority tier from total_impact (sum of clicks across conflicting URLs).

      total >= 100  → P1
      total >=  20  → P2
      otherwise     → P3
    """
    if total_clicks >= 100:
        return "P1"
    if total_clicks >= 20:
        return "P2"
    return "P3"


def _format_conflict_pair(query: str, urls: list[str]) -> str:
    """
    Render the conflict_pair column: '{query} :: {url1} | {url2} | ...'.

    Multi-URL join is sorted alphabetically for determinism so re-running
    the transform produces byte-identical output.
    """
    return f"{query} :: " + " | ".join(sorted(urls))


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    raw: dict,
    *,
    min_impressions: int = _DEFAULT_MIN_IMPRESSIONS,
    default_status: str = "TODO",
) -> dict:
    """
    Transform GSC search_analytics raw payload into schema-shaped
    cannibalization row list.

    Args:
        raw: Parsed JSON from mcp__gsc__search_analytics with dimensions
             including query + page. Must be a dict with a 'rows' (or
             'data') list.
        min_impressions: K threshold per page (default 10). Pages with
             fewer impressions are dropped before grouping; queries that
             retain ≥2 distinct pages above K become conflict groups.
        default_status: statusEnum value to seed the 'status' column
             (default 'TODO'). Must be in master-excel.schema.json
             #/definitions/statusEnum.

    Returns:
        {"cannibalization": [<row>, ...], "meta": {...}}.

    Cannibalization row shape (master-excel.schema.json#cannibalization):
      conflict_pair             str   "{query} :: {url1} | {url2} | ..."
      overlapping_queries_est   int   number of conflict queries shared
                                      by the same URL set on this site
      total_impact              str   "{N} clicks"
      resolution                str   heuristic label (see _resolution_label)
      note                      str   "primary URL: {top}, position
                                       spread: {min}-{max}"
      status                    str   statusEnum (default 'TODO')
      priority                  str   "P1" / "P2" / "P3"

    DURUR triggers (raise CannibalizationError, do NOT silently fallback):
      - raw is not a dict
      - raw['rows'] is the wrong type
      - default_status not in statusEnum
      - URL normalization output drifts (idempotency check fails)
      - emitted row column set drifts from CANNIBALIZATION_COLUMNS

    Empty/no-conflict cases are NOT errors — they return a valid result
    with cannibalization=[] and meta.conflict_count=0. The skill layer
    decides whether to surface this as a "no cannibalization detected"
    notice (see SKILL.md DURUR #7).
    """
    if not isinstance(raw, dict):
        raise CannibalizationError(
            f"raw must be a dict, got {type(raw).__name__}"
        )
    if default_status not in _STATUS_ENUM:
        raise CannibalizationError(
            f"default_status must be one of {sorted(_STATUS_ENUM)}, "
            f"got {default_status!r}"
        )
    if min_impressions is None or min_impressions < 0:
        raise CannibalizationError(
            f"min_impressions must be >= 0, got {min_impressions!r}"
        )

    page_rows = _parse_rows(raw)

    # Group by query (already lowercased in _parse_rows). Within each group
    # collapse multiple rows for the same URL by summing — defensive against
    # GSC payloads that include extra dimensions beyond query+page.
    grouped: dict[str, dict[str, dict[str, float]]] = {}
    for r in page_rows:
        if r.impressions < min_impressions:
            continue
        bucket = grouped.setdefault(r.query, {})
        slot = bucket.setdefault(r.url, {
            "clicks": 0.0,
            "impressions": 0.0,
            "pos_w_sum": 0.0,
        })
        slot["clicks"] += r.clicks
        slot["impressions"] += r.impressions
        slot["pos_w_sum"] += r.position * max(r.impressions, 1)

    # Identify queries with ≥2 distinct URLs after the K filter.
    conflict_queries: dict[str, list[tuple[str, dict[str, float]]]] = {}
    for q, urls in grouped.items():
        if len(urls) >= 2:
            conflict_queries[q] = sorted(urls.items())

    # For each conflict, count how many other conflict queries share the
    # SAME url set (as overlapping_queries_est). Approximation: same URL
    # multiset → same site-level ambiguity pattern.
    url_set_counts: dict[frozenset, int] = {}
    for q, items in conflict_queries.items():
        key = frozenset(u for (u, _) in items)
        url_set_counts[key] = url_set_counts.get(key, 0) + 1

    # D-03 idempotency self-check — every URL in every conflict group
    # must round-trip through normalize_url unchanged. Drift = DURUR.
    for q, items in conflict_queries.items():
        for (url_n, _) in items:
            if normalize_url(url_n) != url_n:
                raise CannibalizationError(
                    f"URL normalization drift detected: {url_n!r} is not "
                    f"idempotent under normalize_url; D-03 invariant broken"
                )

    rows: list[dict] = []
    for q, items in conflict_queries.items():
        urls = [u for (u, _) in items]
        url_set = frozenset(urls)
        # Per-URL aggregates.
        per_url_clicks = {u: int(round(s["clicks"])) for (u, s) in items}
        per_url_imp = {u: int(round(s["impressions"])) for (u, s) in items}
        per_url_pos = {
            u: round(s["pos_w_sum"] / max(s["impressions"], 1), 2)
            for (u, s) in items
        }

        total_clicks = sum(per_url_clicks.values())
        positions = list(per_url_pos.values())

        # Primary URL = highest clicks; ties broken by lower position, then alpha.
        primary_url = sorted(
            urls,
            key=lambda u: (-per_url_clicks[u], per_url_pos[u], u),
        )[0]

        note = (
            f"primary URL: {primary_url}, "
            f"position spread: {min(positions):.2f}-{max(positions):.2f}"
        )

        row = {
            "conflict_pair": _format_conflict_pair(q, urls),
            "overlapping_queries_est": int(url_set_counts.get(url_set, 1)),
            "total_impact": f"{total_clicks} clicks",
            "resolution": _resolution_label(positions),
            "note": note,
            "status": default_status,
            "priority": _priority_label(total_clicks),
        }

        # Schema-shape self-check (defensive — catches any future drift in
        # the row literal above before it lands in the workbook).
        if tuple(row.keys()) != CANNIBALIZATION_COLUMNS:
            raise RowSchemaError(
                f"row column drift: got {tuple(row.keys())}, "
                f"expected {CANNIBALIZATION_COLUMNS}"
            )
        if not isinstance(row["overlapping_queries_est"], int):
            raise RowSchemaError(
                f"overlapping_queries_est must be int, "
                f"got {type(row['overlapping_queries_est']).__name__}"
            )
        if row["status"] not in _STATUS_ENUM:
            raise RowSchemaError(
                f"status must be in statusEnum, got {row['status']!r}"
            )

        # Stash sort key alongside the row for ordering; stripped before return.
        row["_sort_total_clicks"] = total_clicks
        rows.append(row)

    # Sort by total_impact (clicks) desc, then by conflict_pair for determinism.
    rows.sort(key=lambda r: (-r["_sort_total_clicks"], r["conflict_pair"]))
    cannibalization_rows = [
        {k: r[k] for k in CANNIBALIZATION_COLUMNS}
        for r in rows
    ]

    return {
        "cannibalization": cannibalization_rows,
        "meta": {
            "input_row_count": len(page_rows),
            "queries_seen": len(grouped),
            "conflict_count": len(cannibalization_rows),
            "min_impressions": int(min_impressions),
            "default_status": default_status,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cannibalization_transform.py",
        description=(
            "Transform GSC search_analytics JSON -> cannibalization rows."
        ),
    )
    p.add_argument(
        "--raw", required=True,
        help="Path to raw mcp__gsc__search_analytics JSON (query+page dims).",
    )
    p.add_argument(
        "--min-impressions", type=int, default=_DEFAULT_MIN_IMPRESSIONS,
        help=(
            f"Minimum impressions per page to qualify as a conflict "
            f"contributor (default: {_DEFAULT_MIN_IMPRESSIONS})."
        ),
    )
    p.add_argument(
        "--default-status", default="TODO",
        help="statusEnum seed value for new rows (default: TODO).",
    )
    p.add_argument(
        "--output-dir", default=None,
        help="If set, write cannibalization.json into this directory.",
    )
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    raw_path = Path(args.raw)
    if not raw_path.exists():
        print(f"raw JSON not found: {raw_path}", file=sys.stderr)
        return 2
    raw = _read_json(raw_path)

    try:
        result = transform(
            raw,
            min_impressions=args.min_impressions,
            default_status=args.default_status,
        )
    except CannibalizationError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "cannibalization.json"
        out_path.write_text(
            json.dumps(result["cannibalization"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "cannibalization_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "CANNIBALIZATION_COLUMNS",
    "CannibalizationError",
    "RowSchemaError",
    "normalize_url",
    "transform",
    "main",
)
