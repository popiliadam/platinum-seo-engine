#!/usr/bin/env python3
"""
gsc_pull.py — pure transform: GSC search_analytics + enhanced_search_analytics
JSON → schema-shaped rows for master.xlsx#gsc_performance.

Reads the raw response of mcp__gsc__search_analytics (recent window) plus
optionally mcp__gsc__enhanced_search_analytics (the previous window of equal
length used for delta computation), normalizes URLs per D-03 (lowercase
scheme+host, strip default ports, collapse trailing slash except root,
sort+filter query string, drop fragment, IDN -> punycode), aggregates
metrics per page across the recent and previous windows, and emits a row
list shaped for master.xlsx#gsc_performance (12 schema-locked columns
defined in schemas/master-excel.schema.json).

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - Idempotent: same input -> same output. Re-running with the same
    --raw and --enriched files writes byte-identical outputs.

CLI:
  python3 scripts/ingestion/gsc_pull.py \
      --raw inbox/gsc/2026-04-30-search_analytics-{slug}.json \
      [--enriched inbox/gsc/2026-04-30-enhanced_search_analytics-{slug}.json] \
      [--output-dir .]

Stdout: JSON {"gsc_performance": [...], "meta": {...}}.
With --output-dir set: also writes gsc_performance.json into that dir
and prints the absolute path.

Refs: schemas/master-excel.schema.json (gsc_performance sheet
required_columns), schemas/gsc-tool-mapping.schema.json (D-03 URL
normalization invariant + url_original + url_normalized staging),
spec §6 + §12.2 (raw JSON inbox + transform stage), spec §16.5
(MCP discipline).
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
# Constants — schema-aligned column names (master-excel.schema.json#gsc_performance)
# ---------------------------------------------------------------------------

GSC_PERFORMANCE_COLUMNS = (
    "url",
    "clicks_recent",
    "clicks_previous",
    "clicks_delta",
    "clicks_delta_pct",
    "impressions_recent",
    "impressions_previous",
    "impressions_delta",
    "ctr_recent",
    "position_recent",
    "position_previous",
    "note",
)

# ---------------------------------------------------------------------------
# Exceptions (DURUR-style explicit)
# ---------------------------------------------------------------------------

class GscPullError(ValueError):
    """Base class for explicit DURUR conditions in gsc_pull transform."""


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant)
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Adapter wrapping :class:`URLNormalizeError` into :class:`GscPullError`
    so call-site DURUR semantics stay backward-compatible after K-01
    dedup (v1.5-Phase-1 Tier 1).
    """
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError as exc:
        raise GscPullError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Aggregator helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _PageMetrics:
    """Aggregated metrics for one normalized URL across one window."""
    clicks: int
    impressions: int
    # ctr is recomputed downstream from clicks/impressions; we keep the raw
    # weighted-position aggregate for accurate page-level position mean.
    position_weighted_sum: float


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


def _aggregate_window(payload: dict | None) -> dict[str, _PageMetrics]:
    """
    Aggregate a search_analytics-shaped MCP payload to per-URL metrics.

    Accepts payloads of the shape:
      {"rows": [{"keys": [<page>, ...], "clicks": N, "impressions": M,
                 "ctr": x, "position": y}, ...]}

    or:
      {"data": [...]}  (alternate envelope)

    URL is taken from keys[0] (when single dimension == page) or by
    locating the first http(s) entry in keys (defensive: dimension order
    is caller-controlled).

    Empty payload -> empty dict (caller decides if this is fatal).
    """
    if not payload:
        return {}
    rows = payload.get("rows") or payload.get("data") or []
    if not isinstance(rows, list):
        raise GscPullError(
            f"search_analytics payload 'rows' must be a list, got {type(rows).__name__}"
        )

    bucket: dict[str, dict[str, float]] = {}
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        keys = entry.get("keys") or []
        if not isinstance(keys, list) or not keys:
            continue
        # Find the first key that looks like a URL (case-insensitive scheme).
        page_raw: str | None = None
        for k in keys:
            if isinstance(k, str):
                k_stripped = k.strip()
                if k_stripped[:7].lower() == "http://" or \
                   k_stripped[:8].lower() == "https://":
                    page_raw = k_stripped
                    break
        if page_raw is None:
            continue
        try:
            url_n = normalize_url(page_raw)
        except GscPullError:
            continue

        clicks = _safe_int(entry.get("clicks")) or 0
        impressions = _safe_int(entry.get("impressions")) or 0
        position = _safe_float(entry.get("position")) or 0.0

        slot = bucket.setdefault(url_n, {
            "clicks": 0,
            "impressions": 0,
            "pos_w_sum": 0.0,
        })
        slot["clicks"] += clicks
        slot["impressions"] += impressions
        # Position weighted by impressions for accurate page-level mean.
        slot["pos_w_sum"] += position * impressions

    return {
        url_n: _PageMetrics(
            clicks=int(v["clicks"]),
            impressions=int(v["impressions"]),
            position_weighted_sum=float(v["pos_w_sum"]),
        )
        for url_n, v in bucket.items()
    }


def _delta_pct(recent: int, previous: int) -> float:
    """
    Percent change = (recent - previous) / previous * 100, rounded 2dp.

    Edge cases:
      previous == 0 and recent == 0  -> 0.0    (no change, no signal)
      previous == 0 and recent > 0   -> 100.0  (capped, "new arrival")
      previous == 0 and recent < 0   -> -100.0 (defensive; clicks can't be neg)
    """
    if previous == 0:
        if recent == 0:
            return 0.0
        return 100.0 if recent > 0 else -100.0
    return round((recent - previous) / float(previous) * 100.0, 2)


def _avg_position(metrics: _PageMetrics) -> float:
    if metrics.impressions <= 0:
        return 0.0
    return round(metrics.position_weighted_sum / metrics.impressions, 2)


def _avg_ctr_pct(metrics: _PageMetrics) -> float:
    if metrics.impressions <= 0:
        return 0.0
    return round(metrics.clicks / float(metrics.impressions) * 100.0, 4)


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    raw: dict,
    *,
    enriched: dict | None = None,
) -> dict:
    """
    Transform GSC search_analytics raw payloads into schema-shaped
    gsc_performance row list.

    Args:
        raw:      Parsed JSON from mcp__gsc__search_analytics for the
                  RECENT window (today - days_back .. today). Must be a
                  dict with a 'rows' (or 'data') list.
        enriched: Optional parsed JSON from
                  mcp__gsc__enhanced_search_analytics (or a second
                  search_analytics call) for the PREVIOUS window of equal
                  length. Used to compute per-URL deltas. None means the
                  transform produces previous-window zeros (acceptable
                  for first-run).

    Returns:
        {"gsc_performance": [<row>, ...], "meta": {...}}.

    DURUR triggers (raises GscPullError, do NOT silently fallback):
      - raw is not a dict
      - raw['rows'] is present but not a list
      - URL normalization output drifts (idempotency check fails)
    """
    if not isinstance(raw, dict):
        raise GscPullError(f"raw must be a dict, got {type(raw).__name__}")

    recent = _aggregate_window(raw)
    previous = _aggregate_window(enriched)

    rows: list[dict] = []
    # Stable URL ordering: union of both windows, sorted asc for determinism.
    all_urls = sorted(set(recent.keys()) | set(previous.keys()))
    for url_n in all_urls:
        # D-03 idempotency self-check (defensive — raises if drift slips
        # into the schema-shaped output).
        if normalize_url(url_n) != url_n:
            raise GscPullError(
                f"URL normalization drift detected: {url_n!r} is not "
                f"idempotent under normalize_url; D-03 invariant broken"
            )

        rcur = recent.get(url_n)
        rprev = previous.get(url_n)

        clicks_recent = rcur.clicks if rcur else 0
        clicks_previous = rprev.clicks if rprev else 0
        clicks_delta = clicks_recent - clicks_previous
        clicks_delta_pct = _delta_pct(clicks_recent, clicks_previous)

        impressions_recent = rcur.impressions if rcur else 0
        impressions_previous = rprev.impressions if rprev else 0
        impressions_delta = impressions_recent - impressions_previous

        ctr_recent = _avg_ctr_pct(rcur) if rcur else 0.0
        position_recent = _avg_position(rcur) if rcur else 0.0
        position_previous = _avg_position(rprev) if rprev else 0.0

        # Note column carries a short trend hint; deterministic from the
        # delta values, no creativity, sheet-template friendly.
        if clicks_delta_pct > 20:
            note = "rising"
        elif clicks_delta_pct < -20:
            note = "decay"
        elif clicks_recent == 0 and clicks_previous == 0:
            note = "no-clicks"
        else:
            note = "stable"

        rows.append({
            "url": url_n,
            "clicks_recent": clicks_recent,
            "clicks_previous": clicks_previous,
            "clicks_delta": clicks_delta,
            "clicks_delta_pct": clicks_delta_pct,
            "impressions_recent": impressions_recent,
            "impressions_previous": impressions_previous,
            "impressions_delta": impressions_delta,
            "ctr_recent": ctr_recent,
            "position_recent": position_recent,
            "position_previous": position_previous,
            "note": note,
        })

    # Stable sort: clicks_recent desc, then url asc for determinism.
    rows.sort(key=lambda r: (-r["clicks_recent"], r["url"]))

    # Schema-locked column projection (drops any stray keys).
    gsc_perf_rows = [
        {k: r[k] for k in GSC_PERFORMANCE_COLUMNS}
        for r in rows
    ]

    return {
        "gsc_performance": gsc_perf_rows,
        "meta": {
            "recent_url_count": len(recent),
            "previous_url_count": len(previous),
            "merged_url_count": len(gsc_perf_rows),
            "enriched_used": enriched is not None,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="gsc_pull.py",
        description="Transform GSC search_analytics JSON -> gsc_performance rows.",
    )
    p.add_argument("--raw", required=True,
                   help="Path to raw mcp__gsc__search_analytics JSON (recent window).")
    p.add_argument("--enriched", default=None,
                   help="Optional path to enhanced_search_analytics JSON (previous window).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write gsc_performance.json here.")
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

    enriched: dict | None = None
    if args.enriched:
        enriched_path = Path(args.enriched)
        if enriched_path.exists():
            enriched = _read_json(enriched_path)

    try:
        result = transform(raw, enriched=enriched)
    except GscPullError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "gsc_performance.json"
        out_path.write_text(
            json.dumps(result["gsc_performance"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "gsc_performance_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "GSC_PERFORMANCE_COLUMNS",
    "GscPullError",
    "normalize_url",
    "transform",
    "main",
)
