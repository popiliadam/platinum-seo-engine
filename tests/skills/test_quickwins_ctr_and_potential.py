"""tests/skills/test_quickwins_ctr_and_potential.py — T-10690 iki sistemik defekt.

Defekt 1: ctr_pct 100x sisik. `_row_pct` "deger <= 1.0 ise kesirdir" sezgisi
kullaniyor; oysa quick-win satirlarinin CTR'i ZATEN %1'in altinda, yani
"kesir 0,0023" ile "yuzde 0,23" ayirt edilemiyor. Ust kaynak yuzde gonderdiginde
100 ile bir kez daha carpiliyor: 7 tik / 3.102 gosterim = %0,2256 -> sheet %22,56.

Defekt 2: potential_clicks ust kaynagin `potentialClicks` degerini oldugu gibi
aliyor; o deger gosterim x %5 sabiti (SERP'ten bagimsiz). Transform DOGRU degeri
(CTR egrisi x AIO faktoru) zaten `expected_uplift_clicks` olarak hesapliyor.

Kanit: portfoyde 169 satirin 167'sinde potential = gosterim x 0,05.
"""

from __future__ import annotations

import pytest

from scripts.discovery import quickwins_transform
from tests.skills.test_quickwins_scoring_v2 import _frozen_curve_dict
from scripts.util import ctr_curve


@pytest.fixture()
def curve():
    return ctr_curve.build_curve(_frozen_curve_dict())


def _raw(rows: list[dict]) -> dict:
    return {"quickWins": rows, "totalOpportunities": len(rows)}


# --- Defekt 1: ctr_pct -------------------------------------------------------

def test_ctr_pct_derived_from_clicks_and_impressions(curve) -> None:
    """7 tik / 3.102 gosterim = %0,2256 — girdi CTR'i hangi birimde gelirse gelsin."""
    out = quickwins_transform.transform(_raw([
        {"query": "dis kaplama cesitleri", "page": "https://e.com/a",
         "currentPosition": 12, "impressions": 3102, "currentClicks": 7,
         "currentCtr": 0.2256, "potentialClicks": 0},
    ]), curve=curve, top_n=10)
    assert out["quick_wins"][0]["ctr_pct"] == pytest.approx(0.2256, abs=0.001)


def test_ctr_pct_same_answer_for_fractional_input(curve) -> None:
    """Ayni satir, CTR kesir olarak gelirse de AYNI sonuc — belirsizlik bitmeli."""
    out = quickwins_transform.transform(_raw([
        {"query": "dis kaplama cesitleri", "page": "https://e.com/a",
         "currentPosition": 12, "impressions": 3102, "currentClicks": 7,
         "currentCtr": 0.002256, "potentialClicks": 0},
    ]), curve=curve, top_n=10)
    assert out["quick_wins"][0]["ctr_pct"] == pytest.approx(0.2256, abs=0.001)


def test_ctr_pct_zero_impressions_does_not_crash(curve) -> None:
    """Gosterim 0 ise CTR 0 — ZeroDivisionError degil."""
    out = quickwins_transform.transform(_raw([
        {"query": "q", "page": "https://e.com/z", "currentPosition": 12,
         "impressions": 0, "currentClicks": 0, "currentCtr": None,
         "potentialClicks": 0},
    ]), curve=curve, top_n=10)
    if out["quick_wins"]:
        assert out["quick_wins"][0]["ctr_pct"] == 0.0


# --- Defekt 2: potential_clicks ---------------------------------------------

def test_potential_clicks_uses_serp_aware_uplift_not_5pct_constant(curve) -> None:
    """potential_clicks == expected_uplift_clicks; ust kaynagin %5 sabiti YOK SAYILIR.

    impressions=1000, position=12, clicks=10, unchecked -> uplift 20.
    Ust kaynak potentialClicks=50 (=1000 x %5) gonderiyor; yazilmamali.
    """
    out = quickwins_transform.transform(_raw([
        {"query": "a", "page": "https://e.com/a", "currentPosition": 12,
         "impressions": 1000, "currentClicks": 10, "currentCtr": 0.01,
         "potentialClicks": 50},
    ]), curve=curve, top_n=10)
    row = out["quick_wins"][0]
    assert row["potential_clicks"] == 20
    assert row["potential_clicks"] == row["expected_uplift_clicks"]


def test_potential_clicks_reflects_aio_discount(curve) -> None:
    """AIO varsa potansiyel DUSER — SERP-bagimsiz sabit bunu yapamazdi."""
    rows = [{"query": "a", "page": "https://e.com/a", "currentPosition": 12,
             "impressions": 1000, "currentClicks": 10, "currentCtr": 0.01,
             "potentialClicks": 50}]
    plain = quickwins_transform.transform(_raw(rows), curve=curve, top_n=10)
    aio = quickwins_transform.transform(
        _raw(rows), curve=curve, top_n=10,
        aio_presence={"a": {"aio_presence": "present", "own_domain_cited": False,
                            "checked_date": "2026-08-20"}},
    )
    assert aio["quick_wins"][0]["potential_clicks"] < plain["quick_wins"][0]["potential_clicks"]


# --- Kartin 2. maddesi: MUTLAK SIRA (organik sira DEGIL) --------------------

def test_uplift_uses_absolute_rank_when_known(curve) -> None:
    """Organik 7 ama mutlak 12 ise model MUTLAK siraya gore hesaplamali.

    Kart: "Organik 7 ama mutlak 10 olan bir sayfa 'top-10'da' sayilmamali."
    SERP ozellikleri (AIO/PAA/video) organik sirayi asagi ittiginde kullanicinin
    gordugu konum mutlak siradir; CTR egrisi de onu izlemeli.
    """
    f = quickwins_transform.expected_uplift_clicks
    organic_only = f(1000, 7, 10, curve)
    with_absolute = f(1000, 7, 10, curve, absolute_position=12)
    assert with_absolute < organic_only


def test_uplift_absolute_rank_none_keeps_organic_behaviour(curve) -> None:
    """Mutlak sira bilinmiyorsa davranis DEGISMEZ (geriye donuk uyum)."""
    f = quickwins_transform.expected_uplift_clicks
    assert f(1000, 12, 10, curve, absolute_position=None) == f(1000, 12, 10, curve)


def test_transform_reads_absolute_rank_from_aio_file(curve) -> None:
    """aio_presence dosyasindaki rank_absolute transform'a kadar tasinmali.

    Boylece quick_wins sheet'ine YENI KOLON eklemek gerekmiyor (sema katiligi:
    kolon eklemek additive degil, F-05 exact-count kirar).
    """
    rows = [{"query": "a", "page": "https://e.com/a", "currentPosition": 7,
             "impressions": 1000, "currentClicks": 10, "currentCtr": 0.01,
             "potentialClicks": 50}]
    plain = quickwins_transform.transform(_raw(rows), curve=curve, top_n=10)
    with_abs = quickwins_transform.transform(
        _raw(rows), curve=curve, top_n=10,
        aio_presence={"a": {"aio_presence": "not_detected", "own_domain_cited": False,
                            "checked_date": "2026-08-20", "rank_absolute": 12}},
    )
    assert with_abs["quick_wins"][0]["potential_clicks"] < plain["quick_wins"][0]["potential_clicks"]
