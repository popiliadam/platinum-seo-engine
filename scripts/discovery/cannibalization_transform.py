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
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when invoked as a CLI module.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.util.profile_aware_defaults import (  # noqa: E402  (sys.path mutation)
    cascade_default,
)
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

# Default K — minimum impressions per page to qualify as a candidate.
_DEFAULT_MIN_IMPRESSIONS = 10

# I2 — new conflict contract (replaces the old "≥2 URLs ≥K impressions" =
# conflict rule). A query is a cannibalization CONFLICT only when ALL hold:
#   (a) non-brand query (brand tokens derived from project.config brand/domain)
#   (b) click-share dilution — no single URL holds > 70% of the query's clicks
#   (c) competition signal — top-URL flip-flop across the two most recent
#       windows OR ≥2 URLs simultaneously in positions 1-20 with spread ≤ 5
# Default recommendation = differentiate intent; a 301-consolidate is NEVER
# auto-recommended (operator-reviewed only, surfaced in the note).
_CLICK_SHARE_CAP = 0.70          # (b) max single-URL click share to be "diluted"
_POSITION_MIN = 1.0              # (c) GSC positions start at 1
_POSITION_MAX = 20.0             # (c) both URLs must be within page 1-2
_POSITION_SPREAD_CAP = 5.0       # (c) tight cluster threshold

_RESOLUTION_DIFFERENTIATE = "differentiate intent / adjust internal-link hierarchy"

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

def _tokenize(text: str) -> set[str]:
    """Unicode-aware word tokens (handles Turkish chars); excludes underscore."""
    return set(re.findall(r"[^\W_]+", text.lower(), flags=re.UNICODE))


def _is_brand_query(query: str, brand_tokens: Sequence[str] | None) -> bool:
    """I2 (a): is this query brand-dominated?

    A single-word brand token matches as a whole word in the query's token
    set; a multi-word brand token matches as a contiguous (lowercased)
    substring. Brand tokens are derived from project.config brand/domain by
    the caller — the engine stays project-agnostic (no literals here).
    """
    if not brand_tokens:
        return False
    q_lower = query.lower()
    q_tokens = _tokenize(query)
    for bt in brand_tokens:
        bt = str(bt).strip().lower()
        if not bt:
            continue
        bt_words = re.findall(r"[^\W_]+", bt, flags=re.UNICODE)
        if len(bt_words) == 1:
            if bt_words[0] in q_tokens:
                return True
        elif bt and bt in q_lower:
            return True
    return False


def _click_share_diluted(per_url_clicks: Mapping[str, int]) -> bool:
    """I2 (b): True when NO single URL holds > 70% of the query's clicks.

    A query with zero total clicks has no traffic to dilute → not diluted
    (so a zero-click query is never an active cannibalization conflict).
    """
    total = sum(per_url_clicks.values())
    if total <= 0:
        return False
    return (max(per_url_clicks.values()) / total) <= _CLICK_SHARE_CAP


def _position_cluster_signal(per_url_pos: Mapping[str, float]) -> bool:
    """I2 (c) branch 2: ≥2 URLs simultaneously in positions 1-20 with the
    in-range spread ≤ 5 (both are realistically competing on the same SERP)."""
    in_range = [p for p in per_url_pos.values() if _POSITION_MIN <= p <= _POSITION_MAX]
    if len(in_range) < 2:
        return False
    return (max(in_range) - min(in_range)) <= _POSITION_SPREAD_CAP


def _weighted_position(slot: Mapping[str, float]) -> float:
    """Impression-weighted average position for one URL slot."""
    return slot["pos_w_sum"] / max(slot["impressions"], 1)


def _top_url(url_slots: Mapping[str, dict]) -> str:
    """The query's top URL: highest clicks, tie → better (lower) weighted
    position, then alphabetical for determinism."""
    return sorted(
        url_slots.items(),
        key=lambda kv: (-kv[1]["clicks"], _weighted_position(kv[1]), kv[0]),
    )[0][0]


def _flipflop_signal(
    query: str,
    recent_grouped: Mapping[str, dict],
    previous_grouped: Mapping[str, dict],
) -> bool:
    """I2 (c) branch 1: did the top URL flip between the two most recent
    windows? Requires the previous window to carry the query (≥1 URL)."""
    prev = previous_grouped.get(query)
    cur = recent_grouped.get(query)
    if not prev or not cur:
        return False
    return _top_url(cur) != _top_url(prev)


def _group_by_query(
    page_rows: Sequence[_PageRow], min_impressions: int,
) -> dict[str, dict[str, dict[str, float]]]:
    """Group (query → url → {clicks, impressions, pos_w_sum}) after the K
    impressions filter. Same (query, url) rows collapse by summing; position
    is impression-weighted."""
    grouped: dict[str, dict[str, dict[str, float]]] = {}
    for r in page_rows:
        if r.impressions < min_impressions:
            continue
        bucket = grouped.setdefault(r.query, {})
        slot = bucket.setdefault(
            r.url, {"clicks": 0.0, "impressions": 0.0, "pos_w_sum": 0.0},
        )
        slot["clicks"] += r.clicks
        slot["impressions"] += r.impressions
        slot["pos_w_sum"] += r.position * max(r.impressions, 1)
    return grouped


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
    previous: dict | None = None,
    brand_tokens: Sequence[str] | None = None,
    min_impressions: int = _DEFAULT_MIN_IMPRESSIONS,
    default_status: str = "TODO",
) -> dict:
    """
    Transform GSC search_analytics raw payload into schema-shaped
    cannibalization row list under the I2 conflict contract.

    A query with ≥2 distinct URLs above K is only a CONFLICT when ALL hold:
      (a) non-brand query (brand tokens passed via ``brand_tokens``),
      (b) click-share dilution — no single URL holds > 70% of the clicks,
      (c) competition signal — top-URL flip-flop across the two most recent
          windows (needs ``previous``) OR ≥2 URLs in positions 1-20 with
          spread ≤ 5.
    The default recommendation is "differentiate intent / adjust internal-
    link hierarchy"; a 301-consolidate is NEVER auto-recommended (it is an
    operator-reviewed decision, surfaced only as a caveat in the note).

    Args:
        raw: Parsed JSON from mcp__gsc__search_analytics (query + page dims).
        previous: OPTIONAL parsed JSON for the immediately-preceding window
             of equal length — enables the (c) top-URL flip-flop signal. When
             None, only the position-cluster branch of (c) can fire.
        brand_tokens: OPTIONAL list of brand tokens (from project.config
             brand/domain) — brand-dominated queries are excluded per (a).
             The engine stays project-agnostic: no literals are baked in.
        min_impressions: K threshold per page (default 10). Pages below K are
             dropped before grouping; queries with ≥2 distinct pages above K
             become CANDIDATES (then filtered by (a)/(b)/(c)).
        default_status: statusEnum seed for the 'status' column.

    Returns:
        {"cannibalization": [<row>, ...], "meta": {...}}. meta records why
        candidates were rejected (brand_excluded / share_excluded /
        signal_excluded) so a non-empty input that yields zero conflicts is
        explainable.

    Cannibalization row shape (master-excel.schema.json#cannibalization):
      conflict_pair             str   "{query} :: {url1} | {url2} | ..."
      overlapping_queries_est   int   #conflict queries sharing the URL set
      total_impact              str   "{N} clicks"
      resolution                str   always the differentiate-intent default
      note                      str   "primary URL: {top}; signal: {...};
                                       consolidate (301) only if intent
                                       overlap confirmed — operator review"
      status                    str   statusEnum (default 'TODO')
      priority                  str   "P1" / "P2" / "P3"

    DURUR triggers (raise CannibalizationError, do NOT silently fallback):
      - raw / previous is not a dict (previous may be None)
      - raw['rows'] is the wrong type
      - default_status not in statusEnum
      - brand_tokens is not a sequence of strings
      - URL normalization output drifts (idempotency check fails)
      - emitted row column set drifts from CANNIBALIZATION_COLUMNS

    Empty/no-conflict cases are NOT errors — they return a valid result with
    cannibalization=[] and meta.conflict_count=0 (SKILL.md DURUR #7).
    """
    if not isinstance(raw, dict):
        raise CannibalizationError(
            f"raw must be a dict, got {type(raw).__name__}"
        )
    if previous is not None and not isinstance(previous, dict):
        raise CannibalizationError(
            f"previous must be a dict or None, got {type(previous).__name__}"
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
    if brand_tokens is not None and not all(
        isinstance(t, str) for t in brand_tokens
    ):
        raise CannibalizationError(
            "brand_tokens must be a sequence of strings or None"
        )

    page_rows = _parse_rows(raw)
    grouped = _group_by_query(page_rows, min_impressions)
    previous_grouped = (
        _group_by_query(_parse_rows(previous), min_impressions)
        if previous is not None else {}
    )

    # Candidate queries — ≥2 distinct URLs after the K filter.
    candidate_queries: dict[str, list[tuple[str, dict[str, float]]]] = {
        q: sorted(urls.items()) for q, urls in grouped.items() if len(urls) >= 2
    }

    # D-03 idempotency self-check — every URL in every candidate group must
    # round-trip through normalize_url unchanged. Drift = DURUR.
    for q, items in candidate_queries.items():
        for (url_n, _) in items:
            if normalize_url(url_n) != url_n:
                raise CannibalizationError(
                    f"URL normalization drift detected: {url_n!r} is not "
                    f"idempotent under normalize_url; D-03 invariant broken"
                )

    # Apply the I2 conflict predicate (a) ∧ (b) ∧ (c) to each candidate.
    brand_excluded = 0
    share_excluded = 0
    signal_excluded = 0
    conflict_items: dict[str, list[tuple[str, dict[str, float]]]] = {}
    conflict_signals: dict[str, list[str]] = {}
    for q, items in candidate_queries.items():
        if _is_brand_query(q, brand_tokens):                       # (a)
            brand_excluded += 1
            continue
        per_url_clicks = {u: int(round(s["clicks"])) for (u, s) in items}
        if not _click_share_diluted(per_url_clicks):               # (b)
            share_excluded += 1
            continue
        per_url_pos = {u: round(_weighted_position(s), 2) for (u, s) in items}
        cluster = _position_cluster_signal(per_url_pos)            # (c) branch 2
        flip = _flipflop_signal(q, grouped, previous_grouped)      # (c) branch 1
        if not (cluster or flip):
            signal_excluded += 1
            continue
        signals: list[str] = []
        if cluster:
            signals.append("position cluster (1-20, spread ≤5)")
        if flip:
            signals.append("top-URL flip-flop across windows")
        conflict_items[q] = items
        conflict_signals[q] = signals

    # overlapping_queries_est — #conflict queries sharing the same URL set.
    url_set_counts: dict[frozenset, int] = {}
    for q, items in conflict_items.items():
        key = frozenset(u for (u, _) in items)
        url_set_counts[key] = url_set_counts.get(key, 0) + 1

    rows: list[dict] = []
    for q, items in conflict_items.items():
        urls = [u for (u, _) in items]
        url_set = frozenset(urls)
        per_url_clicks = {u: int(round(s["clicks"])) for (u, s) in items}
        per_url_pos = {u: round(_weighted_position(s), 2) for (u, s) in items}
        total_clicks = sum(per_url_clicks.values())

        # Primary URL = highest clicks; ties → lower position, then alpha.
        primary_url = sorted(
            urls,
            key=lambda u: (-per_url_clicks[u], per_url_pos[u], u),
        )[0]

        note = (
            f"primary URL: {primary_url}; "
            f"signal: {' + '.join(conflict_signals[q])}; "
            "consolidate (301) only if intent overlap confirmed — "
            "operator review"
        )

        row = {
            "conflict_pair": _format_conflict_pair(q, urls),
            "overlapping_queries_est": int(url_set_counts.get(url_set, 1)),
            "total_impact": f"{total_clicks} clicks",
            "resolution": _RESOLUTION_DIFFERENTIATE,
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
            "candidate_count": len(candidate_queries),
            "conflict_count": len(cannibalization_rows),
            "brand_excluded": brand_excluded,
            "share_excluded": share_excluded,
            "signal_excluded": signal_excluded,
            "previous_window_provided": previous is not None,
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
        "--previous", default=None,
        help="OPTIONAL path to the prior-window search_analytics JSON — "
             "enables the top-URL flip-flop competition signal.",
    )
    p.add_argument(
        "--brand-token", action="append", default=None, dest="brand_tokens",
        help="Brand token to exclude brand-dominated queries (repeatable). "
             "Derived from project.config brand/domain by the caller.",
    )
    p.add_argument(
        "--min-impressions", type=int, default=None,
        help=(
            f"Minimum impressions per page to qualify as a conflict "
            f"contributor (inline default: {_DEFAULT_MIN_IMPRESSIONS}; "
            f"profile override via Y-06 cascade_default)."
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

    previous = None
    if args.previous:
        previous_path = Path(args.previous)
        if not previous_path.exists():
            print(f"previous JSON not found: {previous_path}", file=sys.stderr)
            return 2
        previous = _read_json(previous_path)

    # Y-06 three-tier cascade: CLI override > profile config > inline default.
    # Profile dict is empty pending project-config schema field for
    # min_impressions; load_profile wiring is opt-in for future v1.7+.
    min_impressions = cascade_default(
        {}, "min_impressions", _DEFAULT_MIN_IMPRESSIONS,
        override=args.min_impressions,
    )

    try:
        result = transform(
            raw,
            previous=previous,
            brand_tokens=args.brand_tokens,
            min_impressions=min_impressions,
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
