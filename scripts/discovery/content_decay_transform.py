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
from scripts.util.profile_aware_defaults import (  # noqa: E402
    cascade_default,
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

# Trend thresholds.
# R-85 (rules/content-update-discipline.md) — single source for decay:
#   DECAY when  (clicks Δ% < clicks_threshold AND position Δ > position_threshold)
#           OR  (impressions Δ% < impressions_threshold AND ranking trend negative)
# Profile-aware (clicks/position branch only; the impressions branch is fixed):
#   YMYL        : -20% clicks, +3 position (stricter)
#   e-commerce  : -30% clicks, +5 position
#   other/default: -30% clicks, +5 position
# These are the inline DEFAULTS; cascade_default lets a project.config tuning
# key (decay_clicks_threshold / decay_position_threshold) or a CLI override
# win over the profile-derived value.
_DEFAULT_CLICKS_THRESHOLD = -30.0
_DEFAULT_POSITION_THRESHOLD = 5.0
_YMYL_CLICKS_THRESHOLD = -20.0
_YMYL_POSITION_THRESHOLD = 3.0
# Impressions branch is NOT profile-varied per R-85 ("Impressions delta < -40%
# AND ranking trend negative").
_IMPRESSIONS_THRESHOLD = -40.0
_GROWTH_THRESHOLD = 20.0

# Decay-rule branch labels (recorded in meta so the operator sees WHY a row
# was flagged — R-85 is a two-branch OR).
_BRANCH_CLICKS_POSITION = "clicks+position"
_BRANCH_IMPRESSIONS_RANK = "impressions+rank"

# Comparison modes for the two-window delta.
_MODE_PRIOR_WINDOW = "prior_window"   # recent 90d vs prior 90d (default)
_MODE_YOY = "yoy"                     # recent window vs same window one year ago

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


def _resolve_thresholds(
    profile_config: Any,
    *,
    clicks_override: float | None = None,
    position_override: float | None = None,
) -> tuple[float, float]:
    """Resolve R-85 (clicks_threshold, position_threshold), profile-aware.

    Profile name comes from ``profile_config["profile"]`` (a project.config
    dict, or None). A name containing ``ymyl`` selects the stricter YMYL
    pair; ``commerce`` selects the e-commerce pair (same as default today);
    anything else falls to the default pair. The Y-06 ``cascade_default``
    SSOT then lets an explicit override (CLI / call-site) OR a project.config
    tuning key (``decay_clicks_threshold`` / ``decay_position_threshold``)
    win over the profile-derived value.
    """
    cfg = profile_config if isinstance(profile_config, dict) else {}
    pname = str(cfg.get("profile") or "").strip().lower()
    if "ymyl" in pname:
        base_clicks, base_pos = _YMYL_CLICKS_THRESHOLD, _YMYL_POSITION_THRESHOLD
    elif "commerce" in pname:           # "e-commerce" / "ecommerce"
        base_clicks, base_pos = _DEFAULT_CLICKS_THRESHOLD, _DEFAULT_POSITION_THRESHOLD
    else:
        base_clicks, base_pos = _DEFAULT_CLICKS_THRESHOLD, _DEFAULT_POSITION_THRESHOLD
    clicks_thr = float(cascade_default(
        cfg, "decay_clicks_threshold", base_clicks, override=clicks_override,
    ))
    position_thr = float(cascade_default(
        cfg, "decay_position_threshold", base_pos, override=position_override,
    ))
    return clicks_thr, position_thr


def _trend_label(
    *,
    clicks_delta_pct: float,
    clicks_recent: int,
    clicks_previous: int,
    impressions_delta_pct: float | None,
    position_delta: float | None,
    clicks_threshold: float,
    position_threshold: float,
) -> tuple[str, str | None]:
    """
    Label a row's trend per R-85's multi-signal contract. Returns
    ``(trend, decay_branch)`` where ``decay_branch`` names which R-85 branch
    fired (``clicks+position`` / ``impressions+rank``) or ``None``.

    Precedence:
      1. NEW / RETIRED — presence/absence, not magnitude.
      2. GROWTH — clicks rose ≥ +20% (unchanged taxonomy; not an R-85 signal).
      3. DECAY — R-85 multi-signal:
           (clicks Δ% < clicks_threshold AND position worsened > position_threshold)
        OR (impressions Δ% < impressions_threshold AND ranking trend negative)
         A clicks-only drop with no position/impression corroboration is
         STABLE — single-signal volatility is NOT decay (R-85 rationale).
      4. STABLE — everything else.
    """
    if clicks_previous == 0 and clicks_recent > 0:
        return "NEW", None
    if clicks_recent == 0 and clicks_previous > 0:
        return "RETIRED", None
    if clicks_delta_pct >= _GROWTH_THRESHOLD:
        return "GROWTH", None
    # R-85 branch 1 — clicks AND position both deteriorate.
    if (position_delta is not None
            and clicks_delta_pct < clicks_threshold
            and position_delta > position_threshold):
        return "DECAY", _BRANCH_CLICKS_POSITION
    # R-85 branch 2 — impressions collapse AND ranking trend negative (the
    # position got worse; flat/improved rank is NOT a negative trend).
    if (impressions_delta_pct is not None and position_delta is not None
            and impressions_delta_pct < _IMPRESSIONS_THRESHOLD
            and position_delta > 0):
        return "DECAY", _BRANCH_IMPRESSIONS_RANK
    return "STABLE", None


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _PageMetrics:
    """Aggregated metrics for one normalized URL across one window.

    ``position`` is the impression-weighted average position, or ``None``
    when the window carried no position signal for this URL (so R-85's
    position-dependent branches can stay honest and not invent a rank).
    """
    clicks: int
    impressions: int
    position: float | None


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
    Aggregate an enhanced_search_analytics-shaped MCP payload to per-URL
    clicks + impressions + impression-weighted position.

    Accepts payloads of the shape:
      {"rows": [{"keys": [<page>, ...], "clicks": N, "impressions": M,
                 "position": P}, ...]}
    or {"data": [...]} (alternate envelope).

    URL is taken from the first http(s) entry in `keys` (defensive:
    dimension order is caller-controlled). Position is weighted by
    impressions (weight = max(impressions, 1)) so a high-traffic row
    dominates the blended rank; a URL with no position field in any of its
    rows yields position=None.

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

    # Per-URL accumulators: clicks, impressions, position-weight numerator,
    # position-weight denominator, and whether any position was seen.
    bucket: dict[str, dict[str, float]] = {}
    has_pos: dict[str, bool] = {}
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
        impressions = _safe_int(entry.get("impressions")) or 0
        position = _safe_float(entry.get("position"))

        slot = bucket.setdefault(
            url_n, {"clicks": 0.0, "impressions": 0.0,
                    "pos_w_sum": 0.0, "weight_sum": 0.0},
        )
        slot["clicks"] += clicks
        slot["impressions"] += impressions
        if position is not None:
            weight = float(max(impressions, 1))
            slot["pos_w_sum"] += position * weight
            slot["weight_sum"] += weight
            has_pos[url_n] = True
        else:
            has_pos.setdefault(url_n, False)

    out: dict[str, _PageMetrics] = {}
    for url_n, slot in bucket.items():
        if has_pos.get(url_n) and slot["weight_sum"] > 0:
            pos: float | None = round(slot["pos_w_sum"] / slot["weight_sum"], 4)
        else:
            pos = None
        out[url_n] = _PageMetrics(
            clicks=int(round(slot["clicks"])),
            impressions=int(round(slot["impressions"])),
            position=pos,
        )
    return out


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    recent: dict | None,
    previous: dict | None,
    *,
    profile_config: Any = None,
    comparison_mode: str = _MODE_PRIOR_WINDOW,
    clicks_threshold: float | None = None,
    position_threshold: float | None = None,
) -> dict:
    """
    Transform two GSC enhanced_search_analytics raw payloads (recent +
    comparison window) into a schema-shaped content_decay row list, applying
    R-85's multi-signal decay contract.

    Args:
        recent:   Parsed JSON from the recent-window MCP call. None is
                  acceptable (treated as empty window) for unit testing, but
                  the skill orchestrator STOPs before calling transform if a
                  fetch failed (DURUR #1).
        previous: Parsed JSON from the comparison-window MCP call. In
                  ``prior_window`` mode this is the immediately-preceding
                  equal-length window; in ``yoy`` mode it is the same window
                  one year earlier.
        profile_config: optional project.config dict. Its ``profile`` field
                  selects R-85's profile-aware (clicks, position) thresholds
                  (YMYL stricter at -20%/+3); cascade_default lets a config
                  tuning key or an explicit override win.
        comparison_mode: ``prior_window`` (default) or ``yoy``. In ``yoy``
                  mode, if the year-ago window carries NO data the transform
                  refuses to fabricate verdicts — it returns zero rows with a
                  ``yoy_unavailable`` note (never fakes a YoY baseline).
        clicks_threshold / position_threshold: explicit R-85 overrides
                  (CLI / call-site) — win over profile + config per Y-06.

    Returns:
        {"content_decay": [<row>, ...], "meta": {...}} where each row carries
        the 8 master-excel content_decay columns (delta_pct is the CLICKS
        delta — position/impressions feed the DECISION only, never new
        columns). Sorted by clicks_delta ascending (most decayed first), then
        url asc. meta records the resolved thresholds, comparison_mode, and a
        per-branch decay count so the operator sees WHICH R-85 branch fired.

    DURUR triggers (raises ContentDecayError; do NOT silently fallback):
      - either payload is the wrong type (string, int, list, ...)
      - either payload's `rows` is the wrong type
      - both windows yield zero rows after aggregation (decay-specific)
      - comparison_mode is not a recognised value
    """
    if recent is not None and not isinstance(recent, dict):
        raise ContentDecayError(
            f"recent must be a dict or None, got {type(recent).__name__}"
        )
    if previous is not None and not isinstance(previous, dict):
        raise ContentDecayError(
            f"previous must be a dict or None, got {type(previous).__name__}"
        )
    if comparison_mode not in (_MODE_PRIOR_WINDOW, _MODE_YOY):
        raise ContentDecayError(
            f"comparison_mode must be one of "
            f"{(_MODE_PRIOR_WINDOW, _MODE_YOY)!r}, got {comparison_mode!r}"
        )

    clicks_thr, position_thr = _resolve_thresholds(
        profile_config,
        clicks_override=clicks_threshold,
        position_override=position_threshold,
    )

    recent_metrics = _aggregate_window(recent)
    previous_metrics = _aggregate_window(previous)

    if not recent_metrics and not previous_metrics:
        # Decay-specific DURUR #8: both windows empty → no signal at all.
        raise ContentDecayError(
            "no data in window: both recent and previous payloads "
            "aggregate to zero rows"
        )

    base_meta = {
        "comparison_mode": comparison_mode,
        "clicks_threshold": clicks_thr,
        "position_threshold": position_thr,
        "impressions_threshold": _IMPRESSIONS_THRESHOLD,
        "recent_url_count": len(recent_metrics),
        "previous_url_count": len(previous_metrics),
    }

    # YoY honesty gate: a year-ago comparison needs the year-ago window. If
    # it carries no data we refuse to fabricate decay/NEW verdicts off a
    # missing baseline — report yoy_unavailable + zero rows (never fake it).
    if comparison_mode == _MODE_YOY and not previous_metrics:
        return {
            "content_decay": [],
            "meta": {
                **base_meta,
                "merged_url_count": 0,
                "trend_counts": _count_trends([]),
                "decay_branch_counts": {
                    _BRANCH_CLICKS_POSITION: 0, _BRANCH_IMPRESSIONS_RANK: 0,
                },
                "yoy_unavailable": True,
                "yoy_note": (
                    "YoY comparison requested but the same-window-one-year-"
                    "earlier payload carried no data; decay not computed "
                    "(no fabricated YoY baseline)."
                ),
            },
        }

    rows: list[dict] = []
    branch_counts = {_BRANCH_CLICKS_POSITION: 0, _BRANCH_IMPRESSIONS_RANK: 0}
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

        imp_recent = rcur.impressions if rcur else 0
        imp_previous = rprev.impressions if rprev else 0
        impressions_delta_pct = _delta_pct(imp_recent, imp_previous)

        pos_recent = rcur.position if rcur else None
        pos_previous = rprev.position if rprev else None
        position_delta = (
            round(pos_recent - pos_previous, 4)
            if (pos_recent is not None and pos_previous is not None)
            else None
        )

        trend, branch = _trend_label(
            clicks_delta_pct=delta_pct,
            clicks_recent=clicks_recent,
            clicks_previous=clicks_previous,
            impressions_delta_pct=impressions_delta_pct,
            position_delta=position_delta,
            clicks_threshold=clicks_thr,
            position_threshold=position_thr,
        )
        if branch is not None:
            branch_counts[branch] += 1

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

    meta = {
        **base_meta,
        "merged_url_count": len(content_decay_rows),
        "trend_counts": _count_trends(content_decay_rows),
        "decay_branch_counts": branch_counts,
    }
    if comparison_mode == _MODE_YOY:
        meta["yoy_unavailable"] = False
    return {
        "content_decay": content_decay_rows,
        "meta": meta,
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
        help="Path to raw enhanced_search_analytics JSON for the comparison "
             "window (prior 90d, or same window one year earlier with --yoy).",
    )
    p.add_argument(
        "--profile", default=None,
        help="Profile name (e.g. ymyl-high, e-commerce) selecting R-85 "
             "decay thresholds; YMYL is stricter (-20%%/+3).",
    )
    p.add_argument(
        "--yoy", action="store_true",
        help="Year-over-year mode: --previous is the same window one year "
             "earlier. If it carries no data, emit a yoy_unavailable note "
             "(never fabricates a YoY baseline).",
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

    profile_config = {"profile": args.profile} if args.profile else None
    comparison_mode = _MODE_YOY if args.yoy else _MODE_PRIOR_WINDOW

    try:
        result = transform(
            recent, previous,
            profile_config=profile_config,
            comparison_mode=comparison_mode,
        )
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
