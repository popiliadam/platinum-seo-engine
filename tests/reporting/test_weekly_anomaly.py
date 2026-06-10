"""tests/reporting/test_weekly_anomaly.py — GAP-M-1a (Wave 1a) anomaly stats.

Covers the NEW pure stats module scripts/reporting/weekly_anomaly.py that
replaces monitoring-weekly's 5σ/8-week placeholder with a robust median+MAD
modified z-score detector (R-141 / NIST Iglewicz–Hoaglin) gated by percent +
absolute floors and capped under calendar-overlap windows.

All-synthetic fixtures; the only "current week" identity is an ISO-week string
arg (rules/time-discipline.md — the module computes from arg values, never
date.today()/datetime.now — grep-sentinel-asserted in test 8).
"""

from __future__ import annotations

from pathlib import Path

from scripts.reporting import weekly_anomaly


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_SRC = REPO_ROOT / "scripts" / "reporting" / "weekly_anomaly.py"


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _wk(n: int) -> str:
    return f"2026-W{n:02d}"


def _record(week_n: int, *, clicks: float, impressions: float,
            ctr: float, avg_position: float) -> dict:
    return {
        "iso_week": _wk(week_n),
        "week_start": "2026-01-01",
        "week_end": "2026-01-07",
        "clicks": clicks, "impressions": impressions,
        "ctr": ctr, "avg_position": avg_position,
    }


def _flat_baseline(clicks_seq, *, weeks_start=5,
                   impressions=5000.0, ctr=0.02, avg_position=15.0) -> list[dict]:
    """Build baseline weeks from a clicks sequence; other metrics flat."""
    recs = []
    for i, c in enumerate(clicks_seq):
        recs.append(_record(weeks_start + i, clicks=c, impressions=impressions,
                            ctr=ctr, avg_position=avg_position))
    return recs


# A 12-week clicks baseline around 100 with a small, non-zero MAD (≈1.5).
_BASE12 = [98, 102, 99, 101, 100, 103, 97, 100, 102, 98, 101, 99]


# ---------------------------------------------------------------------------
# Test 1 — clear clicks drop → flagged, modified_z ≤ −3.5, direction drop, RED
# ---------------------------------------------------------------------------

def test_clicks_drop_flagged_red() -> None:
    records = _flat_baseline(_BASE12)               # weeks 5..16
    current = _record(17, clicks=40, impressions=5000.0, ctr=0.02, avg_position=15.0)
    records.append(current)

    out = weekly_anomaly.detect(records, _wk(17))
    assert out["status"] == "ok"
    assert out["points_used"] == 12
    clicks = out["metrics"]["clicks"]
    assert clicks["flagged"] is True
    assert clicks["modified_z"] <= -3.5
    assert clicks["direction"] == "drop"
    assert "clicks" in out["anomalies"]
    assert out["severity"] == "RED"

    # Flat metrics must NOT flag (constant baseline, current equal → no anomaly).
    assert out["metrics"]["impressions"]["flagged"] is False
    assert out["metrics"]["ctr"]["flagged"] is False
    assert out["metrics"]["avg_position"]["flagged"] is False


# ---------------------------------------------------------------------------
# Test 2 — within the percent floor → NOT flagged (floor suppression)
# ---------------------------------------------------------------------------

def test_percent_floor_suppression() -> None:
    records = _flat_baseline(_BASE12)
    # current clicks 88: |88-100|/100 = 12% < 25% floor, even though |M|>3.5.
    records.append(_record(17, clicks=88, impressions=5000.0, ctr=0.02, avg_position=15.0))
    out = weekly_anomaly.detect(records, _wk(17))
    clicks = out["metrics"]["clicks"]
    assert abs(clicks["modified_z"]) >= 3.5, "z should exceed k (proving the FLOOR suppresses)"
    assert clicks["flagged"] is False
    assert out["severity"] == "none"


# ---------------------------------------------------------------------------
# Test 3 — low volume: absolute-minimum floor suppresses a 50% drop
# ---------------------------------------------------------------------------

def test_low_volume_abs_floor_suppression() -> None:
    base = [7, 8, 9, 8, 7, 8, 9, 8, 7, 8, 9, 8]      # median 8, MAD 0.5
    records = _flat_baseline(base)
    records.append(_record(17, clicks=4, impressions=5000.0, ctr=0.02, avg_position=15.0))
    out = weekly_anomaly.detect(records, _wk(17))
    clicks = out["metrics"]["clicks"]
    # 50% drop, |M| big, but |4-8|=4 < abs_min 10 ⇒ suppressed.
    assert clicks["flagged"] is False


# ---------------------------------------------------------------------------
# Test 4 — MAD == 0 (constant baseline) → fallback percent rule fires
# ---------------------------------------------------------------------------

def test_mad_zero_fallback_fires() -> None:
    base = [100] * 12                                # MAD == 0
    records = _flat_baseline(base)
    records.append(_record(17, clicks=55, impressions=5000.0, ctr=0.02, avg_position=15.0))
    out = weekly_anomaly.detect(records, _wk(17))
    clicks = out["metrics"]["clicks"]
    # 45% relative change ≥ mad_zero_pct 0.40 AND abs 45 ≥ 10 ⇒ flagged.
    assert clicks["mad"] == 0
    assert clicks["flagged"] is True
    assert clicks["direction"] == "drop"
    assert out["severity"] == "RED"


# ---------------------------------------------------------------------------
# Test 5 — insufficient history (< min_points)
# ---------------------------------------------------------------------------

def test_insufficient_history() -> None:
    records = _flat_baseline([100, 101, 99, 100, 102])   # 5 baseline weeks
    records.append(_record(11, clicks=40, impressions=5000.0, ctr=0.02, avg_position=15.0))
    out = weekly_anomaly.detect(records, _wk(11))
    assert out["status"] == "insufficient_history"
    assert out["points_used"] == 5
    assert out["needed"] == 6
    assert out["severity"] == "none"
    # No crash, no fabricated anomalies.
    assert out["anomalies"] == []


# ---------------------------------------------------------------------------
# Test 6 — direction-aware severity (position worse → RED; clicks rise → INFO)
# ---------------------------------------------------------------------------

def test_position_worse_flags_red() -> None:
    base = [12, 12, 13, 12, 11, 12, 13, 12, 11, 12, 13, 12]   # median 12
    records = []
    for i, p in enumerate(base):
        records.append(_record(5 + i, clicks=100, impressions=5000.0, ctr=0.02, avg_position=p))
    records.append(_record(17, clicks=100, impressions=5000.0, ctr=0.02, avg_position=18.0))
    out = weekly_anomaly.detect(records, _wk(17))
    pos = out["metrics"]["avg_position"]
    assert pos["flagged"] is True
    assert pos["direction"] == "worse"      # higher position number = worse
    assert out["severity"] == "RED"


def test_clicks_rise_flags_info_not_red() -> None:
    records = _flat_baseline(_BASE12)
    records.append(_record(17, clicks=300, impressions=5000.0, ctr=0.02, avg_position=15.0))
    out = weekly_anomaly.detect(records, _wk(17))
    clicks = out["metrics"]["clicks"]
    assert clicks["flagged"] is True
    assert clicks["direction"] == "rise"
    assert out["severity"] == "INFO", "improvement is INFO, never RED"


def test_ctr_drop_flags_amber() -> None:
    base_ctr = 0.05
    records = []
    for i in range(12):
        records.append(_record(5 + i, clicks=100, impressions=5000.0,
                               ctr=base_ctr, avg_position=15.0))
    # ctr collapses to 0.01 (4 pp drop ≥ 0.5pp floor); MAD==0 baseline ⇒ fallback.
    records.append(_record(17, clicks=100, impressions=5000.0, ctr=0.01, avg_position=15.0))
    out = weekly_anomaly.detect(records, _wk(17))
    ctr = out["metrics"]["ctr"]
    assert ctr["flagged"] is True
    assert ctr["direction"] == "drop"
    assert out["severity"] == "AMBER"


# ---------------------------------------------------------------------------
# Test 7 — calendar overlap caps RED → AMBER + attribution caution
# ---------------------------------------------------------------------------

def test_update_overlap_caps_severity_amber() -> None:
    records = _flat_baseline(_BASE12)
    records.append(_record(17, clicks=40, impressions=5000.0, ctr=0.02, avg_position=15.0))
    overlaps = [{"name": "May 2026 core update", "phase": "rollout_in_period",
                 "overlap_days": 8}]
    out = weekly_anomaly.detect(records, _wk(17), update_overlaps=overlaps)
    assert out["severity"] == "AMBER", "RED must be capped to AMBER under overlap"
    assert "attribution_caution" in out
    assert "May 2026 core update" in out["attribution_caution"]
    assert out["update_overlap"] == overlaps


def test_calendar_unavailable_marker() -> None:
    records = _flat_baseline(_BASE12)
    records.append(_record(17, clicks=40, impressions=5000.0, ctr=0.02, avg_position=15.0))
    out = weekly_anomaly.detect(records, _wk(17), update_overlaps=None)
    assert out["update_overlap"] == "calendar_unavailable"
    # No calendar ⇒ no cap: the clicks drop stays RED.
    assert out["severity"] == "RED"


# ---------------------------------------------------------------------------
# Test 8 — determinism + no wall-clock import (purity / time-discipline)
# ---------------------------------------------------------------------------

def test_determinism_same_input_same_output() -> None:
    records = _flat_baseline(_BASE12)
    records.append(_record(17, clicks=40, impressions=5000.0, ctr=0.02, avg_position=15.0))
    a = weekly_anomaly.detect(records, _wk(17))
    b = weekly_anomaly.detect(records, _wk(17))
    assert a == b


def test_no_wall_clock_in_module() -> None:
    """R-141 / time-discipline: the stats module is pure — no datetime.now /
    date.today (dates flow in as the current_iso_week arg)."""
    text = MODULE_SRC.read_text(encoding="utf-8")
    assert "datetime.now" not in text, "weekly_anomaly must not call datetime.now"
    assert "date.today" not in text, "weekly_anomaly must not call date.today"
