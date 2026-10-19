"""D-02 / D-08 — DataForSEO: no foreign-country rows stamped as TR, no silent task failures.

D-02: only tasks[0] was locale-checked and items without a location_code got
the requested 2792/tr stamped on them, so a US task could be stored as Turkey.
D-08: HTTP 200 can carry task status_code != 20000; a failed task was dropped
silently (multi-task) or reported as "unrecognised shape" (e.g. 40200).
"""
from __future__ import annotations

import pytest

from scripts.ingestion import dfs_pull as dp
from scripts.util import dfs_response as dr


def _task(loc: int, lang: str, keywords: list[str], *, code: int = 20000, msg: str = "Ok.") -> dict:
    return {"status_code": code, "status_message": msg,
            "data": {"location_code": loc, "language_code": lang},
            "result": [{"location_code": loc, "language_code": lang,
                        "items": [{"keyword": k, "search_volume": 100} for k in keywords]}]}


def test_second_task_served_for_us_fails_the_tr_check() -> None:
    raw = {"tasks": [_task(2792, "tr", ["kombi"]), _task(2840, "en", ["boiler"])]}
    assert not dp.response_honors_tr(raw)
    with pytest.raises(dp.TrWorkaroundFailed):
        dp.transform(raw, project_slug="demo")


def test_volume_with_a_us_task_is_not_stored_as_tr() -> None:
    raw_volume = {"tasks": [_task(2792, "tr", ["kombi"]), _task(2840, "en", ["boiler"])]}
    with pytest.raises(dp.TrWorkaroundFailed):
        dp.transform(None, raw_volume=raw_volume, project_slug="demo")


def test_item_explicitly_for_another_country_is_dropped() -> None:
    raw = {"tasks": [_task(2792, "tr", ["kombi"])]}
    raw["tasks"][0]["result"][0]["items"].append(
        {"keyword": "boiler", "search_volume": 900, "location_code": 2840, "language_code": "en"})
    out = dp.transform(raw, project_slug="demo")
    kws = [r["keyword"] for r in out["keyword_overview"]["rows"]]
    assert kws == ["kombi"]


def test_payment_required_task_is_a_clear_error() -> None:
    raw = {"status_code": 20000, "tasks": [_task(2792, "tr", [], code=40200, msg="Payment Required.")]}
    with pytest.raises(dr.DFSTaskError, match="40200.*payment required"):
        dr.normalize_dfs_response(raw)
    with pytest.raises(dr.DFSTaskError):
        dp.transform(raw, project_slug="demo", skip_tr_check=True)


def test_one_failed_task_among_many_is_not_dropped_silently() -> None:
    raw = {"tasks": [_task(2792, "tr", ["kombi"]), _task(2792, "tr", [], code=50000, msg="Internal Error.")]}
    with pytest.raises(dr.DFSTaskError, match="50000"):
        dr.normalize_dfs_response(raw)
