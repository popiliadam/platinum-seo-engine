#!/usr/bin/env python3
"""
content_decay_transform.py — pure transform: GSC enhanced_search_analytics
two-window JSON → schema-shaped rows for master.xlsx#content_decay.

Reads two raw responses of mcp__gsc__enhanced_search_analytics — one for
the RECENT window (today - 90d .. today) and one for the PREVIOUS window
of equal length (today - 180d .. today - 90d) — normalizes URLs per D-03,
aggregates clicks per page across each window, computes signed delta +
delta_pct (clamped to ±100 when previous == 0, mirrors gsc-pull's
`_delta_pct`), labels a trend (DECAY / STABLE / GROWTH / NEW / RETIRED),
infers `pillar` from the first URL path segment, and prescribes a per-
trend `action`. Output is shaped to master.xlsx#content_decay
(8 schema-locked columns; see schemas/master-excel.schema.json line 158-
170).

Pure function discipline (mirrors gsc_pull.py / quickwins_transform.py):
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - No master.xlsx writes from this module. No scripts.excel imports
    (the skill orchestrator owns transaction.append).
  - Idempotent: same inputs → byte-identical output.

CLI:
  python3 scripts/discovery/content_decay_transform.py \\
      --recent   inbox/gsc/{date}-enhanced_search_analytics-decay-recent-{slug}.json \\
      --previous inbox/gsc/{date}-enhanced_search_analytics-decay-previous-{slug}.json \\
      [--output-dir _state/transform/{run_id}/]

Stdout: JSON {"content_decay": [...], "meta": {...}}.
With --output-dir set: also writes content_decay.json into that dir
and prints the absolute path.

Refs: schemas/master-excel.schema.json#content_decay (8 required_columns),
schemas/gsc-tool-mapping.schema.json (D-03 URL normalization invariant),
spec §16.5 (raw JSON inbox + transform stage). Pattern reference:
scripts/ingestion/gsc_pull.py (delta_pct ±100 clamp, _aggregate_window).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit  # used by infer_pillar()

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
# Constants — schema-aligned column names (master-excel.schema.json#content_decay)
# ---------------------------------------------------------------------------

CONTENT_DECAY_COLUMNS = (
    "url",
    "clicks_previous",
    "clicks_recent",
    "clicks_delta",
    "delta_pct",
    "trend",
    "pillar",
    "action",
)

# Trend thresholds (delta_pct boundaries).
_DECAY_THRESHOLD = -20.0
_GROWTH_THRESHOLD = 20.0

# Per-trend deterministic action prescriptions (sheet-template friendly).
_TREND_ACTIONS = {
    "DECAY":   "investigate + refresh",
    "STABLE":  "monitor",
    "GROWTH":  "double-down",
    "NEW":     "new content tracking",
    "RETIRED": "redirect or revive review",
}

# ---------------------------------------------------------------------------
# Exceptions (DURUR-style explicit)
# ---------------------------------------------------------------------------

class ContentDecayError(ValueError):
    """Base class for explicit DURUR conditions in content_decay transform."""


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant)
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Adapter wrapping :class:`URLNormalizeError` into
    :class:`ContentDecayError` so call-site DURUR semantics stay
    backward-compatible after K-01 dedup (v1.5-Phase-1 Tier 1).
    """
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError as exc:
        raise ContentDecayError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Pillar inference
# ---------------------------------------------------------------------------

def infer_pillar(url: str) -> str:
    """
    Extract the first non-empty path segment of a normalized URL as the
    pillar (e.g. https://site.tld/blog/x → "blog";
    https://site.tld/products/y → "products"; root '/' → "").

    Empty string when the URL is root / scheme-less / unparseable.
    Deterministic and idempotent: depends only on the URL's path
    component, and only fires when a real scheme is present (so a bare
    string like "not-a-url" returns "" rather than mistakenly treating
    the whole string as a path segment).
    """
    if not isinstance(url, str) or not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    if not parts.scheme:
        return ""
    path = parts.path or "/"
    segments = [s for s in path.split("/") if s]
    if not segments:
        return ""
    return segments[0]


# ---------------------------------------------------------------------------
# Delta + trend
# ---------------------------------------------------------------------------

def _delta_pct(recent: int, previous: int) -> float:
    """
    Percent change = (recent - previous) / previous * 100, rounded 2dp.

    Edge cases (mirrors scripts.ingestion.gsc_pull._delta_pct, Phase 6
    convention):
      previous == 0 and recent == 0  ->   0.0    (no change, no signal)
      previous == 0 and recent  > 0  -> +100.0   (clamp; "new arrival")
      previous == 0 and recent  < 0  -> -100.0   (defensive; clicks ≥ 0)
      previous  > 0                  -> raw pct, rounded 2dp; for
                                        recent=0 this naturally yields
                                        -100.0 (RETIRED case).
    """
    if previous == 0:
        if recent == 0:
            return 0.0
        return 100.0 if recent > 0 else -100.0
    return round((recent - previous) / float(previous) * 100.0, 2)


def _trend_label(
    *,
    delta_pct: float,
    clicks_recent: int,
    clicks_previous: int,
) -> str:
    """
    Label a row's trend deterministically. NEW / RETIRED take precedence
    over delta_pct buckets because they describe presence/absence, not
    magnitude of change.
    """
    if clicks_previous == 0 and clicks_recent > 0:
        return "NEW"
    if clicks_recent == 0 and clicks_previous > 0:
        return "RETIRED"
    if delta_pct <= _DECAY_THRESHOLD:
        return "DECAY"
    if delta_pct >= _GROWTH_THRESHOLD:
        return "GROWTH"
    return "STABLE"


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _PageMetrics:
    """Aggregated metrics for one normalized URL across one window."""
    clicks: int


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _aggregate_window(payload: dict | None) -> dict[str, _PageMetrics]:
    """
    Aggregate an enhanced_search_analytics-shaped MCP payload to per-URL
    click totals.

    Accepts payloads of the shape:
      {"rows": [{"keys": [<page>, ...], "clicks": N, ...}, ...]}
    or {"data": [...]} (alternate envelope).

    URL is taken from the first http(s) entry in `keys` (defensive:
    dimension order is caller-controlled).

    Empty / None payload -> empty dict (caller decides if fatal).
    """
    if not payload:
        return {}
    if not isinstance(payload, dict):
        raise ContentDecayError(
            f"payload must be a dict, got {type(payload).__name__}"
        )
    rows = payload.get("rows") or payload.get("data") or []
    if not isinstance(rows, list):
        raise ContentDecayError(
            f"payload 'rows' must be a list, got {type(rows).__name__}"
        )

    bucket: dict[str, int] = {}
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        keys = entry.get("keys") or []
        if not isinstance(keys, list) or not keys:
            continue
        page_raw: str | None = None
        for k in keys:
            if isinstance(k, str):
                k_stripped = k.strip()
                if (k_stripped[:7].lower() == "http://"
                        or k_stripped[:8].lower() == "https://"):
                    page_raw = k_stripped
                    break
        if page_raw is None:
            continue
        try:
            url_n = normalize_url(page_raw)
        except ContentDecayError:
            continue

        clicks = _safe_int(entry.get("clicks")) or 0
        bucket[url_n] = bucket.get(url_n, 0) + clicks

    return {url_n: _PageMetrics(clicks=int(c)) for url_n, c in bucket.items()}


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    recent: dict | None,
    previous: dict | None,
) -> dict:
    """
    Transform two GSC enhanced_search_analytics raw payloads (recent +
    previous, equal-length 90-day windows) into a schema-shaped
    content_decay row list.

    Args:
        recent:   Parsed JSON from the recent-window MCP call. Required;
                  None is acceptable (treated as empty window) so the
                  transform unit can still run, but the skill orchestrator
                  must STOP before calling transform if either fetch
                  failed (DURUR #1).
        previous: Parsed JSON from the previous-window MCP call.

    Returns:
        {"content_decay": [<row>, ...], "meta": {...}} where each row
        contains the 8 master-excel content_decay columns. Sorted by
        clicks_delta ascending (most decayed first), then url asc for
        determinism.

    DURUR triggers (raises ContentDecayError; do NOT silently fallback):
      - either payload is the wrong type (string, int, list, ...)
      - either payload's `rows` is the wrong type
      - both windows yield zero rows after aggregation (decay-specific)
    """
    if recent is not None and not isinstance(recent, dict):
        raise ContentDecayError(
            f"recent must be a dict or None, got {type(recent).__name__}"
        )
    if previous is not None and not isinstance(previous, dict):
        raise ContentDecayError(
            f"previous must be a dict or None, got {type(previous).__name__}"
        )

    recent_metrics = _aggregate_window(recent)
    previous_metrics = _aggregate_window(previous)

    if not recent_metrics and not previous_metrics:
        # Decay-specific DURUR #8: both windows empty → no signal at all.
        raise ContentDecayError(
            "no data in window: both recent and previous payloads "
            "aggregate to zero rows"
        )

    rows: list[dict] = []
    all_urls = sorted(set(recent_metrics.keys()) | set(previous_metrics.keys()))
    for url_n in all_urls:
        # D-03 idempotency self-check (defensive).
        if normalize_url(url_n) != url_n:
            raise ContentDecayError(
                f"URL normalization drift detected: {url_n!r} is not "
                f"idempotent under normalize_url; D-03 invariant broken"
            )

        rcur = recent_metrics.get(url_n)
        rprev = previous_metrics.get(url_n)

        clicks_recent = rcur.clicks if rcur else 0
        clicks_previous = rprev.clicks if rprev else 0
        clicks_delta = clicks_recent - clicks_previous
        delta_pct = _delta_pct(clicks_recent, clicks_previous)

        trend = _trend_label(
            delta_pct=delta_pct,
            clicks_recent=clicks_recent,
            clicks_previous=clicks_previous,
        )

        rows.append({
            "url": url_n,
            "clicks_previous": int(clicks_previous),
            "clicks_recent": int(clicks_recent),
            "clicks_delta": int(clicks_delta),
            "delta_pct": delta_pct,
            "trend": trend,
            "pillar": infer_pillar(url_n),
            "action": _TREND_ACTIONS[trend],
        })

    # Sort: clicks_delta asc (most decayed first), then url asc for
    # tie-break determinism.
    rows.sort(key=lambda r: (r["clicks_delta"], r["url"]))

    # Schema-locked column projection (drops any stray keys; preserves
    # column order matching master-excel.schema.json).
    content_decay_rows = [
        {k: r[k] for k in CONTENT_DECAY_COLUMNS}
        for r in rows
    ]

    return {
        "content_decay": content_decay_rows,
        "meta": {
            "recent_url_count": len(recent_metrics),
            "previous_url_count": len(previous_metrics),
            "merged_url_count": len(content_decay_rows),
            "trend_counts": _count_trends(content_decay_rows),
        },
    }


def _count_trends(rows: list[dict]) -> dict[str, int]:
    """Count rows per trend label for the meta block."""
    counts: dict[str, int] = {
        "DECAY": 0, "STABLE": 0, "GROWTH": 0, "NEW": 0, "RETIRED": 0,
    }
    for r in rows:
        t = r.get("trend")
        if t in counts:
            counts[t] += 1
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="content_decay_transform.py",
        description=(
            "Transform two GSC enhanced_search_analytics JSON files "
            "(recent + previous 90-day windows) -> content_decay rows."
        ),
    )
    p.add_argument(
        "--recent", required=True,
        help="Path to raw enhanced_search_analytics JSON for recent window.",
    )
    p.add_argument(
        "--previous", required=True,
        help="Path to raw enhanced_search_analytics JSON for previous window.",
    )
    p.add_argument(
        "--output-dir", default=None,
        help="If set, write content_decay.json here.",
    )
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    recent_path = Path(args.recent)
    previous_path = Path(args.previous)
    if not recent_path.exists():
        print(f"recent JSON not found: {recent_path}", file=sys.stderr)
        return 2
    if not previous_path.exists():
        print(f"previous JSON not found: {previous_path}", file=sys.stderr)
        return 2

    recent = _read_json(recent_path)
    previous = _read_json(previous_path)

    try:
        result = transform(recent, previous)
    except ContentDecayError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "content_decay.json"
        out_path.write_text(
            json.dumps(result["content_decay"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "content_decay_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "CONTENT_DECAY_COLUMNS",
    "ContentDecayError",
    "normalize_url",
    "infer_pillar",
    "transform",
    "main",
)
