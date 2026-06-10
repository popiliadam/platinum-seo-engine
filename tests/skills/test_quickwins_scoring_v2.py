"""tests/skills/test_quickwins_scoring_v2.py — GAP-M3 expected-CTR-uplift scoring.

Covers (GAP-M3 spec §d, GAP-M2 D2/D3, measurement-discipline R-139/R-140):
  1. Curve loader: bundled ctr-curve.json validates vs schema; expected_ctr,
     interpolation, end-clamp; aio_factor honesty (unchecked → 1.0; never > 1).
  2. expected_uplift_clicks math (frozen curve, exact values + AIO discount +
     existing-clicks subtraction floor).
  3. Ranking: uplift desc primary, legacy opportunity_score tiebreak.
  4. R-139 grep sentinel: no curve constant literal in quickwins_transform.py
     (and only inside fenced worked-examples in the SKILL body).
  5. Determinism / idempotence of transform under the v2 scorer.
  6. Label re-banding on click units (HIGH≥50 / MEDIUM≥15 / LOW).
  7. load_aio_presence + AIO presence columns K–N (GAP-M2 D2/D3).

Frozen synthetic data only; no network, no workspace side effects.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.util import ctr_curve

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
CTR_CURVE_JSON = REPO_ROOT / "ctr-curve.json"
CTR_CURVE_SCHEMA = SCHEMAS / "ctr-curve.schema.json"


# ---------------------------------------------------------------------------
# Frozen curve fixture — exact values mirror the build-spec table.
# (Curve constants here are test fixtures, NOT engine-body literals — the
#  R-139 grep-sentinel only targets quickwins_transform.py + SKILL bodies.)
# ---------------------------------------------------------------------------

def _frozen_curve_dict() -> dict:
    return {
        "schema_version": "1.0",
        "curve_version": "test.2026.06",
        "sources": [
            {"name": "first_page_sage_2026", "url": "https://example.test/fps",
             "retrieved": "2026-06-10", "covers": "positions 1-10"},
        ],
        "positions": [
            {"position": 1, "ctr": 0.398, "provenance": "first_page_sage_2026"},
            {"position": 2, "ctr": 0.187, "provenance": "first_page_sage_2026"},
            {"position": 3, "ctr": 0.102, "provenance": "first_page_sage_2026"},
            {"position": 4, "ctr": 0.072, "provenance": "first_page_sage_2026"},
            {"position": 5, "ctr": 0.051, "provenance": "first_page_sage_2026"},
            {"position": 6, "ctr": 0.044, "provenance": "first_page_sage_2026"},
            {"position": 7, "ctr": 0.030, "provenance": "first_page_sage_2026"},
            {"position": 8, "ctr": 0.021, "provenance": "first_page_sage_2026"},
            {"position": 9, "ctr": 0.019, "provenance": "first_page_sage_2026"},
            {"position": 10, "ctr": 0.016, "provenance": "first_page_sage_2026"},
            {"position": 11, "ctr": 0.010, "provenance": "engine_estimate"},
            {"position": 15, "ctr": 0.006, "provenance": "engine_estimate"},
            {"position": 20, "ctr": 0.003, "provenance": "engine_estimate"},
        ],
        "interpolation": "linear_between_listed_positions",
        "aio_discount": {
            "default": 0.5,
            "by_position": {"1": 0.420, "2": 0.492, "3": 0.536, "4": 0.612,
                            "5": 0.674, "6": 0.695, "7": 0.703, "8": 0.712,
                            "9": 0.703, "10": 0.806},
            "fallback_11_20": 0.806,
        },
    }


@pytest.fixture
def frozen_curve():
    return ctr_curve.build_curve(_frozen_curve_dict())


# ---------------------------------------------------------------------------
# Test 1 — curve loader + schema validity
# ---------------------------------------------------------------------------

def test_bundled_ctr_curve_validates_against_schema() -> None:
    assert CTR_CURVE_JSON.exists(), "engine-root ctr-curve.json missing"
    assert CTR_CURVE_SCHEMA.exists(), "schemas/ctr-curve.schema.json missing"
    data = json.loads(CTR_CURVE_JSON.read_text("utf-8"))
    schema = json.loads(CTR_CURVE_SCHEMA.read_text("utf-8"))
    errors = sorted(Draft7Validator(schema).iter_errors(data),
                    key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    )


def test_bundled_ctr_curve_loads() -> None:
    curve = ctr_curve.load_curve(CTR_CURVE_JSON)
    assert curve.curve_version  # non-empty provenance string
    # First Page Sage 2026 anchor.
    assert curve.expected_ctr(7) == pytest.approx(0.030)


def test_expected_ctr_listed_and_interpolated(frozen_curve) -> None:
    c = frozen_curve
    assert c.expected_ctr(7) == pytest.approx(0.030)
    assert c.expected_ctr(1) == pytest.approx(0.398)
    # Interpolated strictly between listed 11 (0.010) and 15 (0.006).
    mid = c.expected_ctr(12.5)
    assert 0.006 < mid < 0.010
    assert mid == pytest.approx(0.0085, abs=1e-6)


def test_expected_ctr_clamps_at_ends(frozen_curve) -> None:
    c = frozen_curve
    assert c.expected_ctr(25) == pytest.approx(c.expected_ctr(20))  # 0.003
    assert c.expected_ctr(0.5) == pytest.approx(c.expected_ctr(1))  # 0.398


def test_aio_factor_honesty(frozen_curve) -> None:
    c = frozen_curve
    # present → discounted by position
    assert c.aio_factor(7, "present") == pytest.approx(0.703)
    # 11-20 fallback
    assert c.aio_factor(13, "present") == pytest.approx(0.806)
    # unknown is NOT discounted — honesty: flag, don't penalise
    assert c.aio_factor(7, "unchecked") == 1.0
    assert c.aio_factor(7, "not_detected") == 1.0
    # factor never exceeds 1.0
    for p in range(1, 21):
        for state in ("present", "not_detected", "unchecked"):
            assert c.aio_factor(p, state) <= 1.0


def test_load_curve_durur_on_missing(tmp_path) -> None:
    with pytest.raises(ValueError):
        ctr_curve.load_curve(tmp_path / "nope.json")


def test_load_curve_durur_on_schema_invalid(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "1.0", "positions": []}),
                   encoding="utf-8")
    with pytest.raises(ValueError):
        ctr_curve.load_curve(bad)


# ---------------------------------------------------------------------------
# Test 2 — expected_uplift_clicks math (frozen curve, exact values)
# ---------------------------------------------------------------------------

from scripts.discovery import quickwins_transform  # noqa: E402


def test_expected_uplift_math(frozen_curve) -> None:
    f = quickwins_transform.expected_uplift_clicks
    # impressions=1000, position=12, clicks=10, unchecked:
    #   target = min(10, max(5, 12-5)) = 7 ; ctr(7)=0.030 ; factor=1.0
    #   1000*0.030 - 10 = 20
    assert f(1000, 12, 10, frozen_curve) == 20
    # same row, AIO present: factor(7)=0.703 -> 1000*0.030*0.703 - 10 = 11
    assert f(1000, 12, 10, frozen_curve, aio_presence="present") == 11
    # existing-clicks subtraction floors at 0 (never negative)
    assert f(1000, 12, 40, frozen_curve) == 0
    # unchecked == not_detected (no discount)
    assert f(1000, 12, 10, frozen_curve, aio_presence="not_detected") == 20


# ---------------------------------------------------------------------------
# Test 3 — ranking: uplift desc primary, legacy opportunity_score tiebreak
# ---------------------------------------------------------------------------

def _raw(rows: list[dict]) -> dict:
    return {"quickWins": rows, "totalOpportunities": len(rows)}


def test_ranking_uplift_primary_legacy_tiebreak(frozen_curve) -> None:
    raw = _raw([
        # uplift = 1000*ctr(7)=30 ; legacy = 1000*(20-12) = 8000
        {"query": "a", "page": "https://e.com/a", "currentPosition": 12,
         "impressions": 1000, "currentClicks": 0, "currentCtr": 0.0,
         "potentialClicks": 0},
        # uplift = round(1579*ctr(9)=30.0)=30 ; legacy = 1579*(20-14)=9474
        {"query": "b", "page": "https://e.com/b", "currentPosition": 14,
         "impressions": 1579, "currentClicks": 0, "currentCtr": 0.0,
         "potentialClicks": 0},
    ])
    out = quickwins_transform.transform(raw, curve=frozen_curve, top_n=10)
    uplifts = {r["query"]: r["expected_uplift_clicks"] for r in out["quick_wins"]}
    assert uplifts == {"a": 30, "b": 30}, uplifts
    # Tie on uplift -> higher legacy opportunity_score wins (b 9474 > a 8000)
    assert [r["query"] for r in out["quick_wins"]] == ["b", "a"]


# ---------------------------------------------------------------------------
# Test 4 — R-139 grep sentinel: no curve constant literal in transform body
# ---------------------------------------------------------------------------

def test_r139_no_curve_constant_in_transform_source() -> None:
    src = (REPO_ROOT / "scripts" / "discovery" / "quickwins_transform.py").read_text("utf-8")
    # Curve/discount constants must live in ctr-curve.json, not the Python body.
    for forbidden in ("0.398", "0.703", "0.187", "0.102", "0.072",
                      "0.051", "0.044", "0.021", "0.019", "0.016", "0.806"):
        assert forbidden not in src, (
            f"R-139 violation: curve constant {forbidden!r} leaked into "
            f"quickwins_transform.py (must be sourced from ctr-curve.json)"
        )


# ---------------------------------------------------------------------------
# Test 5 — determinism / idempotence under the v2 scorer
# ---------------------------------------------------------------------------

def test_transform_v2_determinism(frozen_curve) -> None:
    raw = _raw([
        {"query": "kw-a", "page": "https://e.com/a", "currentPosition": 12,
         "impressions": 1000, "currentClicks": 5, "currentCtr": 0.01,
         "potentialClicks": 5},
        {"query": "kw-b", "page": "https://e.com/b", "currentPosition": 15,
         "impressions": 600, "currentClicks": 2, "currentCtr": 0.01,
         "potentialClicks": 3},
    ])
    out1 = quickwins_transform.transform(raw, curve=frozen_curve, top_n=10)
    out2 = quickwins_transform.transform(raw, curve=frozen_curve, top_n=10)
    assert out1 == out2


# ---------------------------------------------------------------------------
# Test 6 — label re-banding on click units (HIGH>=50 / MEDIUM>=15 / LOW)
# ---------------------------------------------------------------------------

def test_label_rebanding_on_click_units() -> None:
    pl = quickwins_transform._priority_label
    ol = quickwins_transform._opportunity_label
    assert pl(60) == "HIGH" and pl(50) == "HIGH"
    assert pl(20) == "MEDIUM" and pl(15) == "MEDIUM"
    assert pl(14) == "LOW" and pl(5) == "LOW"
    assert ol(60) == "High"
    assert ol(20) == "Medium"
    assert ol(5) == "Low"


# ---------------------------------------------------------------------------
# Test 7 — load_aio_presence + AIO presence columns K-N (GAP-M2 D2/D3)
# ---------------------------------------------------------------------------

def test_load_aio_presence_happy(tmp_path) -> None:
    p = tmp_path / "aio.json"
    p.write_text(json.dumps({
        "kw-a": {"aio_presence": "present", "own_domain_cited": True,
                 "checked_date": "2026-06-10", "detection_source": "dfs_mcp_sync"},
        "kw-b": {"aio_presence": "not_detected", "own_domain_cited": False,
                 "checked_date": "2026-06-10", "detection_source": "dfs_mcp_sync"},
    }), encoding="utf-8")
    m = quickwins_transform.load_aio_presence(p)
    assert m["kw-a"]["aio_presence"] == "present"
    assert m["kw-a"]["own_domain_cited"] is True
    assert m["kw-b"]["aio_presence"] == "not_detected"


def test_load_aio_presence_missing_and_malformed(tmp_path) -> None:
    assert quickwins_transform.load_aio_presence(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert quickwins_transform.load_aio_presence(bad) == {}


def test_transform_aio_columns_populated(frozen_curve) -> None:
    raw = _raw([
        {"query": "kw-a", "page": "https://e.com/a", "currentPosition": 12,
         "impressions": 1000, "currentClicks": 10, "currentCtr": 0.01,
         "potentialClicks": 5},
    ])
    aio = {"kw-a": {"aio_presence": "present", "own_domain_cited": True,
                    "checked_date": "2026-06-10", "detection_source": "dfs_mcp_sync"}}
    out = quickwins_transform.transform(
        raw, curve=frozen_curve, aio_presence=aio, top_n=10,
    )
    row = out["quick_wins"][0]
    assert row["aio_presence"] == "present"
    assert row["aio_own_cited"] is True
    assert row["aio_checked_date"] == "2026-06-10"
    assert row["expected_uplift_clicks"] == 11  # discounted
    assert set(row.keys()) == set(quickwins_transform.QUICK_WINS_COLUMNS)
    opp = out["opportunity"][0]
    assert opp["aio_presence"] == "present"
    assert opp["expected_uplift_clicks"] == 11
    assert set(opp.keys()) == set(quickwins_transform.OPPORTUNITY_COLUMNS)
    assert out["meta"]["score_version"] == "2.0"
    assert out["meta"]["curve_version"] == frozen_curve.curve_version
    assert out["meta"]["aio_checked_count"] == 1


def test_transform_aio_defaults_when_no_file(frozen_curve) -> None:
    raw = _raw([
        {"query": "kw-a", "page": "https://e.com/a", "currentPosition": 12,
         "impressions": 1000, "currentClicks": 10, "currentCtr": 0.01,
         "potentialClicks": 5},
    ])
    out = quickwins_transform.transform(raw, curve=frozen_curve, top_n=10)
    row = out["quick_wins"][0]
    assert row["aio_presence"] == "unchecked"
    assert row["aio_own_cited"] is False
    assert row["aio_checked_date"] == ""
    assert row["expected_uplift_clicks"] == 20  # no discount on unchecked
    assert out["meta"]["aio_checked_count"] == 0
