#!/usr/bin/env python3
"""
weekly_anomaly.py — robust weekly GSC anomaly detection (median + MAD).

Replaces monitoring-weekly's 5σ/trailing-8-week-mean placeholder (which was both
statistically meaningless on n≈8 and unimplementable against the snapshot
gsc_performance sheet) with the NIST/Iglewicz–Hoaglin modified z-score:

    M = 0.6745 · (x − median) / MAD          (MAD = median(|x_i − median|))

flagged at |M| ≥ 3.5, AND gated by percent + absolute floors so low-volume
projects don't fire on trivia. MAD has a 50% breakdown point, so one bad week
cannot poison the threshold (unlike a sample SD). See rules/measurement-discipline.md
R-141.

Honesty rails:
  - 0.6745 is the modified-z normalizing constant Φ⁻¹(0.75) — a fixed
    mathematical constant, NOT a tunable anomaly threshold. The tunable
    parameters (k, floors, window) are kwargs defaults, overridable per call /
    via profile cascade (distinct from the CTR/AIO discount *curves*, which
    R-139 requires to live in versioned data files).
  - Pure & deterministic: operates on ISO-week strings + numeric metrics only.
    The "current week" is the current_iso_week argument — never read from the
    system clock (rules/time-discipline.md; wall-clock-import grep-sentinel-asserted).
  - < min_points complete weeks ⇒ honest `insufficient_history`, never a
    fabricated alarm.
  - An anomaly whose week overlaps a Google Ranking-update window (R-137 calendar)
    is capped at AMBER with an attribution caution — Google's own guidance is to
    not attribute movement during/just-after a rollout.

Refs: GAP-M4 D2 (measurement spec), NIST e-Handbook §1.3.5.17.
"""

from __future__ import annotations

from statistics import median
from typing import Iterable

# Metrics evaluated, with their "worse" direction semantics.
_METRICS = ("clicks", "impressions", "ctr", "avg_position")
# Higher value = worse for position; lower value = worse for the rest.
_WORSE_WHEN_HIGHER = ("avg_position",)

_MODIFIED_Z_CONST = 0.6745  # Φ⁻¹(0.75): NIST modified z-score constant (not a threshold)

_DEFAULT_FLOORS = {
    "clicks": {"pct": 0.25, "abs_min": 10},
    "impressions": {"pct": 0.25, "abs_min": 100},
    "ctr": {"abs_pp": 0.5},          # absolute percentage-points (ctr stored as fraction)
    "avg_position": {"abs": 1.5},
}

_SEVERITY_RANK = {"none": 0, "INFO": 1, "AMBER": 2, "RED": 3}


def _floors_pass(value: float, med: float, fl: dict) -> bool:
    """Whether the per-metric floor(s) pass for a candidate deviation."""
    diff = abs(value - med)
    ok = True
    if "pct" in fl:
        ok = ok and (diff / max(abs(med), 1e-9) >= fl["pct"])
    if "abs_min" in fl:
        ok = ok and (diff >= fl["abs_min"])
    if "abs" in fl:
        ok = ok and (diff >= fl["abs"])
    if "abs_pp" in fl:
        ok = ok and (diff * 100.0 >= fl["abs_pp"])
    return ok


def _direction(metric: str, value: float, med: float) -> str:
    if metric in _WORSE_WHEN_HIGHER:
        return "worse" if value > med else "better"
    return "drop" if value < med else "rise"


def _is_worse(metric: str, value: float, med: float) -> bool:
    if metric in _WORSE_WHEN_HIGHER:
        return value > med
    return value < med


def _metric_severity(metric: str, worse: bool) -> str:
    """RED for a worsening clicks/impressions/position; AMBER for a ctr drop;
    INFO for any improvement direction."""
    if not worse:
        return "INFO"
    if metric == "ctr":
        return "AMBER"
    return "RED"


def detect(
    records: Iterable[dict],
    current_iso_week: str,
    *,
    window: int = 13,
    min_points: int = 6,
    floors: dict | None = None,
    k_modified_z: float = 3.5,
    mad_zero_pct: float = 0.40,
    update_overlaps: list | None = None,
) -> dict:
    """Detect anomalies in the current ISO week vs a trailing robust baseline.

    Args:
        records: weekly ledger dicts ({iso_week, clicks, impressions, ctr,
            avg_position, ...}); must include the current week. Order-agnostic.
        current_iso_week: ISO week string ("YYYY-Www", zero-padded) to evaluate.
        window: max trailing complete weeks to use as baseline (most recent).
        min_points: minimum baseline weeks required; fewer ⇒ insufficient_history.
        floors: per-metric floor config (defaults to _DEFAULT_FLOORS).
        k_modified_z: |modified z| flag threshold (NIST default 3.5).
        mad_zero_pct: relative-change trigger when MAD==0 (constant baseline).
        update_overlaps: list of calendar overlap hits for this week (caps RED→
            AMBER), [] for clean, or None when the calendar is unavailable.

    Returns a fully-evidenced dict (see module docstring / tests). Never raises
    on sparse data — returns an honest status instead.
    """
    fl = floors or _DEFAULT_FLOORS
    recs = list(records)

    # Baseline = complete weeks strictly BEFORE current_iso_week (lexical sort is
    # correct for zero-padded ISO-week strings), most-recent `window` of them.
    baseline = sorted(
        (r for r in recs if str(r.get("iso_week", "")) < current_iso_week),
        key=lambda r: str(r.get("iso_week", "")),
    )
    baseline = baseline[-window:] if len(baseline) > window else baseline

    overlap_marker = _resolve_overlap(update_overlaps)

    if len(baseline) < min_points:
        out = {
            "status": "insufficient_history",
            "points_used": len(baseline),
            "needed": min_points,
            "window_weeks": window,
            "metrics": {},
            "anomalies": [],
            "severity": "none",
            "update_overlap": overlap_marker,
        }
        return out

    current = next((r for r in recs if str(r.get("iso_week", "")) == current_iso_week), None)
    if current is None:
        return {
            "status": "current_week_missing",
            "points_used": len(baseline),
            "window_weeks": window,
            "metrics": {},
            "anomalies": [],
            "severity": "none",
            "update_overlap": overlap_marker,
        }

    metrics_out: dict[str, dict] = {}
    anomalies: list[str] = []
    severity = "none"

    for metric in _METRICS:
        value = current.get(metric)
        series = [r.get(metric) for r in baseline if r.get(metric) is not None]
        if value is None or len(series) < min_points:
            continue
        value = float(value)
        med = float(median(series))
        mad = float(median([abs(float(x) - med) for x in series]))

        if mad > 0:
            mz = round(_MODIFIED_Z_CONST * (value - med) / mad, 4)
            stat_trigger = abs(mz) >= k_modified_z
        else:
            mz = None  # undefined when the baseline is constant
            # True relative change; the per-metric ABSOLUTE floor (abs_min/abs/
            # abs_pp) below does the trivia-suppression, so the denominator must
            # not be floored at 1 (that breaks fractional metrics like ctr).
            rel = abs(value - med) / max(abs(med), 1e-9)
            stat_trigger = rel >= mad_zero_pct

        floors_passed = _floors_pass(value, med, fl.get(metric, {}))
        flagged = bool(stat_trigger and floors_passed)
        direction = _direction(metric, value, med)

        metrics_out[metric] = {
            "value": value,
            "median": med,
            "mad": mad,
            "modified_z": mz,
            "flagged": flagged,
            "direction": direction,
            "floors_passed": floors_passed,
        }

        if flagged:
            anomalies.append(metric)
            sev = _metric_severity(metric, _is_worse(metric, value, med))
            if _SEVERITY_RANK[sev] > _SEVERITY_RANK[severity]:
                severity = sev

    out = {
        "status": "ok",
        "points_used": len(baseline),
        "window_weeks": window,
        "metrics": metrics_out,
        "anomalies": anomalies,
        "severity": severity,
        "update_overlap": overlap_marker,
    }

    # Calendar interaction (R-137 soft dependency): cap RED → AMBER under overlap.
    if isinstance(overlap_marker, list) and overlap_marker:
        if severity == "RED":
            out["severity"] = "AMBER"
        names = ", ".join(
            str(o.get("name")) for o in overlap_marker if o.get("name")
        ) or "a Google Ranking update"
        out["attribution_caution"] = (
            f"{names} rollout/settling overlaps this week — movement must not be "
            f"attributed to engine work without the overlap annotation"
        )

    return out


def _resolve_overlap(update_overlaps: list | None):
    if update_overlaps is None:
        return "calendar_unavailable"
    return list(update_overlaps)


__all__ = ("detect",)
