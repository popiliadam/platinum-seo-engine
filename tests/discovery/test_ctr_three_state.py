"""S-18 — the CTR model distinguishes three AIO states and the market's AIO rate.

Before: one curve, an AIO discount only when AIO was checked (off by default),
and no difference between "AIO present and we are cited" and "AIO present and
we are not". Seer: no AIO 3.35% / AIO + cited 2.07% / AIO + not cited 0.94%.
Turkey: AIO on ~23% of searches (Seobaz, 8,282 searches), used to price an
unchecked query instead of assuming no AIO at all.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.discovery.quickwins_transform import expected_uplift_clicks
from scripts.util import ctr_curve

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def curve() -> ctr_curve.Curve:
    return ctr_curve.load_curve(ROOT / "ctr-curve.json")


def _uplift(curve, presence: str, **kw) -> int:
    return expected_uplift_clicks(20_000, 14.0, 0, curve, aio_presence=presence, **kw)


def test_three_aio_states_give_three_estimates(curve) -> None:
    absent = _uplift(curve, "not_detected")
    cited = _uplift(curve, "present", own_cited=True)
    not_cited = _uplift(curve, "present", own_cited=False)
    assert absent > cited > not_cited > 0


def test_citation_factors_follow_seer(curve) -> None:
    assert curve.aio_factor(7, "present", own_cited=True) == pytest.approx(2.07 / 3.35, abs=0.01)
    assert curve.aio_factor(7, "present", own_cited=False) == pytest.approx(0.94 / 3.35, abs=0.01)


def test_unchecked_query_in_turkey_is_priced_with_the_market_rate(curve) -> None:
    unknown_market = _uplift(curve, "unchecked")
    turkey = _uplift(curve, "unchecked", market="TR")
    absent = _uplift(curve, "not_detected")
    assert turkey < unknown_market == absent
    blended = curve.aio_factor(7, "unchecked", market="TR")
    assert blended == pytest.approx(0.77 + 0.23 * curve.aio_factor(7, "present"), abs=1e-6)


def test_curve_file_records_its_sources() -> None:
    data = json.loads((ROOT / "ctr-curve.json").read_text(encoding="utf-8"))
    names = {s["name"] for s in data["sources"]}
    assert {"seer_aio_ctr_2026", "seobaz_tr_aio_2026"} <= names
    assert data["aio_rate_by_market"]["TR"] == pytest.approx(0.23)
