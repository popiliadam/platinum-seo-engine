"""tests/reporting/test_intervention_outcome.py — GAP-M-W2 (Wave 2).

Covers the NEW pure module scripts/reporting/intervention_outcome.py, which
turns a quick-wins treated+control cohort snapshot (R-138) plus a later-dated
GSC payload into a treated-vs-control outcome verdict.

Rule authority: R-138 (intervention cohort tagging) in
rules/measurement-discipline.md — outcome claims are the treated-vs-control
DIFFERENCE (never a raw treated delta); |difference| < 10pp ⇒
``indistinguishable`` with an explicit "n<30 — directional only" caveat; no
p-values / significance theater.

All-synthetic fixtures; frozen dates passed as args (rules/time-discipline.md —
no date.today() in the module). Cohort/post shapes mirror the quick-wins Step 7b
cohort file and the GSC detect_quick_wins / search_analytics inbox payloads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reporting import intervention_outcome as io


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_SRC = REPO_ROOT / "scripts" / "reporting" / "intervention_outcome.py"


# ---------------------------------------------------------------------------
# Fixtures — synthetic cohort + post payloads
# ---------------------------------------------------------------------------

def _cohort() -> dict:
    """A 3-treated + 3-control cohort, matched same-band (R-138)."""
    return {
        "cohort_date": "2026-04-04",
        "score_version": "2.0",
        "treated": [
            {"query": "q-t1", "url": "https://ex.com/t1",
             "position": 14.0, "impressions_30d": 1000, "clicks_30d": 10},
            {"query": "q-t2", "url": "https://ex.com/t2",
             "position": 16.0, "impressions_30d": 800, "clicks_30d": 8},
            {"query": "q-t3", "url": "https://ex.com/t3",
             "position": 12.0, "impressions_30d": 1200, "clicks_30d": 12},
        ],
        "controls": [
            {"query": "q-c1", "url": "https://ex.com/c1",
             "position": 14.0, "impressions_30d": 1000, "clicks_30d": 10},
            {"query": "q-c2", "url": "https://ex.com/c2",
             "position": 16.0, "impressions_30d": 800, "clicks_30d": 8},
            {"query": "q-c3", "url": "https://ex.com/c3",
             "position": 12.0, "impressions_30d": 1200, "clicks_30d": 12},
        ],
        "matching": {"position_tolerance": 2, "impressions_ratio_max": 2.0},
    }


def _post_quickwins(rows: list[dict]) -> dict:
    """detect_quick_wins-shaped post payload."""
    return {"quickWins": rows}


# ---------------------------------------------------------------------------
# Verdict cases
# ---------------------------------------------------------------------------

def test_treated_improve_controls_flat_is_engine_positive() -> None:
    """Treated rows improve (median position −4, clicks rise) while controls
    stay flat ⇒ treated-vs-control difference far exceeds +10pp ⇒
    engine_positive (R-138). Median position delta is reported as evidence."""
    cohort = _cohort()
    post = _post_quickwins([
        # treated: position −4 each (14→10, 16→12, 12→8); clicks 30→120 (+300%)
        {"query": "q-t1", "position": 10.0, "clicks": 40},
        {"query": "q-t2", "position": 12.0, "clicks": 32},
        {"query": "q-t3", "position": 8.0, "clicks": 48},
        # controls: flat positions; clicks 30→31 (+3.33%)
        {"query": "q-c1", "position": 14.0, "clicks": 11},
        {"query": "q-c2", "position": 16.0, "clicks": 8},
        {"query": "q-c3", "position": 12.0, "clicks": 12},
    ])
    out = io.compute_outcome(cohort, post, post_date="2026-05-01")
    assert out["verdict"] == "engine_positive"
    assert out["treated"]["median_position_delta"] == -4.0
    assert out["control"]["median_position_delta"] == 0.0
    assert out["difference_pp"] > 10.0
    assert out["caveat"] == "n<30 — directional evidence only"


def test_both_improve_is_indistinguishable() -> None:
    """Treated AND controls both improve by a similar magnitude ⇒ the
    difference is < 10pp ⇒ indistinguishable (R-138 honesty: the rise is not
    attributable to the engine)."""
    cohort = _cohort()
    post = _post_quickwins([
        # treated clicks 30→60 (+100%)
        {"query": "q-t1", "position": 10.0, "clicks": 20},
        {"query": "q-t2", "position": 12.0, "clicks": 16},
        {"query": "q-t3", "position": 8.0, "clicks": 24},
        # controls clicks 30→59 (+96.67%) — difference 3.33pp < 10
        {"query": "q-c1", "position": 12.0, "clicks": 20},
        {"query": "q-c2", "position": 14.0, "clicks": 19},
        {"query": "q-c3", "position": 10.0, "clicks": 20},
    ])
    out = io.compute_outcome(cohort, post, post_date="2026-05-01")
    assert out["verdict"] == "indistinguishable"
    assert abs(out["difference_pp"]) < 10.0


def test_treated_drop_is_engine_negative() -> None:
    """Treated clicks fall while controls hold ⇒ difference ≤ −10pp ⇒
    engine_negative (the engine doesn't get to hide declines either)."""
    cohort = _cohort()
    post = _post_quickwins([
        # treated clicks 30→15 (−50%)
        {"query": "q-t1", "position": 15.0, "clicks": 5},
        {"query": "q-t2", "position": 17.0, "clicks": 4},
        {"query": "q-t3", "position": 13.0, "clicks": 6},
        # controls flat clicks 30→30 (0%)
        {"query": "q-c1", "position": 14.0, "clicks": 10},
        {"query": "q-c2", "position": 16.0, "clicks": 8},
        {"query": "q-c3", "position": 12.0, "clicks": 12},
    ])
    out = io.compute_outcome(cohort, post, post_date="2026-05-01")
    assert out["verdict"] == "engine_negative"
    assert out["difference_pp"] <= -10.0


def test_missing_control_rows_tolerated_and_counted_in_attrition() -> None:
    """A control query absent from the post payload is dropped from medians and
    counted in attrition.control_missing (never fabricated)."""
    cohort = _cohort()
    post = _post_quickwins([
        {"query": "q-t1", "position": 10.0, "clicks": 40},
        {"query": "q-t2", "position": 12.0, "clicks": 32},
        {"query": "q-t3", "position": 8.0, "clicks": 48},
        # only 2 of 3 controls present
        {"query": "q-c1", "position": 14.0, "clicks": 11},
        {"query": "q-c2", "position": 16.0, "clicks": 8},
    ])
    out = io.compute_outcome(cohort, post, post_date="2026-05-01")
    assert out["attrition"]["control_missing"] == 1
    assert out["attrition"]["treated_missing"] == 0
    # control medians/clicks computed over the 2 present rows only.
    assert out["control"]["n"] == 2


def test_no_pvalues_and_directional_caveat() -> None:
    """No significance theater: the outcome carries no p-value and an explicit
    n<30 directional caveat (R-138)."""
    cohort = _cohort()
    post = _post_quickwins([
        {"query": "q-t1", "position": 10.0, "clicks": 40},
        {"query": "q-c1", "position": 14.0, "clicks": 10},
    ])
    out = io.compute_outcome(cohort, post, post_date="2026-05-01")
    blob = json.dumps(out).lower()
    assert "p_value" not in blob and "pvalue" not in blob
    assert "significan" not in blob
    assert "n<30" in out["caveat"]


def test_deterministic_same_inputs_same_output() -> None:
    cohort = _cohort()
    post = _post_quickwins([
        {"query": "q-t1", "position": 10.0, "clicks": 40},
        {"query": "q-t2", "position": 12.0, "clicks": 32},
        {"query": "q-t3", "position": 8.0, "clicks": 48},
        {"query": "q-c1", "position": 14.0, "clicks": 11},
        {"query": "q-c2", "position": 16.0, "clicks": 8},
        {"query": "q-c3", "position": 12.0, "clicks": 12},
    ])
    a = io.compute_outcome(cohort, post, post_date="2026-05-01")
    b = io.compute_outcome(cohort, post, post_date="2026-05-01")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_search_analytics_payload_shape_supported() -> None:
    """The post payload may be a search_analytics ``rows[].keys`` shape, not
    only detect_quick_wins — the indexer tolerates both."""
    cohort = _cohort()
    post = {"rows": [
        {"keys": ["q-t1"], "position": 10.0, "clicks": 40},
        {"keys": ["q-t2"], "position": 12.0, "clicks": 32},
        {"keys": ["q-t3"], "position": 8.0, "clicks": 48},
        {"keys": ["q-c1"], "position": 14.0, "clicks": 11},
        {"keys": ["q-c2"], "position": 16.0, "clicks": 8},
        {"keys": ["q-c3"], "position": 12.0, "clicks": 12},
    ]}
    out = io.compute_outcome(cohort, post, post_date="2026-05-01")
    assert out["verdict"] == "engine_positive"
    assert out["treated"]["median_position_delta"] == -4.0


def test_select_cohort_files_by_age() -> None:
    """select_cohort_files keeps only cohorts at least ``min_age_days`` old
    relative to the ``today`` arg (frozen date; no date.today())."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        old = base / "2026-04-04-cohort.json"
        recent = base / "2026-06-05-cohort.json"
        old.write_text(json.dumps({"cohort_date": "2026-04-04"}), "utf-8")
        recent.write_text(json.dumps({"cohort_date": "2026-06-05"}), "utf-8")
        picked = io.select_cohort_files(base, today="2026-06-10",
                                        min_age_days=21)
        names = {p.name for p in picked}
        assert "2026-04-04-cohort.json" in names      # 67 days old → kept
        assert "2026-06-05-cohort.json" not in names  # 5 days old → skipped


def test_module_imports_no_stats_library() -> None:
    """Honesty/grep sentinel: the module uses stdlib statistics only — no
    scipy/numpy/statsmodels (no significance machinery)."""
    src = MODULE_SRC.read_text(encoding="utf-8")
    for banned in ("import scipy", "import numpy", "import statsmodels",
                   "p_value", "ttest", "pvalue"):
        assert banned not in src, f"banned token {banned!r} in module body"
