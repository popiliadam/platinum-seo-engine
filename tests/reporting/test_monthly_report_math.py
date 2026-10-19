"""D-03 — site position is impression-weighted; 0 -> N is "new", not +50,000 %."""
from __future__ import annotations

from scripts.reporting import monthly_report as mr


def _row(clicks, imps, pos, *, prev=(0, 0, 0.0)):
    return {"clicks_recent": clicks, "impressions_recent": imps, "position_recent": pos,
            "clicks_previous": prev[0], "impressions_previous": prev[1], "position_previous": prev[2]}


def test_position_is_impression_weighted() -> None:
    rows = [_row(5000, 100000, 2.0), _row(0, 10, 80.0)]
    assert mr._gsc_totals(rows, "recent")["avg_position"] == 2.0078


def test_zero_to_n_is_new_not_huge_percentage() -> None:
    trends = mr._build_gsc_positive_trends([_row(500, 9000, 5.0)])
    assert trends["deltas"]["clicks_delta_pct"] is None
    assert mr._fmt_pct(trends["deltas"]["clicks_delta_pct"]) == "yeni"


def test_regular_change_still_a_percentage() -> None:
    trends = mr._build_gsc_positive_trends([_row(150, 3000, 5.0, prev=(100, 2000, 6.0))])
    assert trends["deltas"]["clicks_delta_pct"] == 50.0
