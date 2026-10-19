"""O-01 — finished tasks get a before/after GSC measurement against a control group."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.reporting import task_outcome as to

TODAY = date(2026, 10, 19)
TASKS = [
    {"task_id": "T-00001", "url": "https://x.test/kombi/", "primary_source": "quickwin",
     "status": "DONE", "done_date": "2026-08-01"},
    {"task_id": "T-00002", "url": "https://x.test/klima", "primary_source": "tech_fix",
     "status": "DONE", "done_date": "2026-10-10"},
    {"task_id": "T-00003", "url": "https://x.test/petek", "primary_source": "quickwin",
     "status": "TODO", "done_date": None},
]
GSC = ["https://x.test/kombi", "https://x.test/klima", "https://x.test/a", "https://x.test/b",
       "https://x.test/c"]


def test_windows_are_28_days_and_do_not_overlap() -> None:
    b = to.window_bounds(date(2026, 8, 1), "before")
    a = to.window_bounds(date(2026, 8, 1), "after_28")
    a2 = to.window_bounds(date(2026, 8, 1), "after_56")
    assert b == (date(2026, 7, 4), date(2026, 7, 31))
    assert a == (date(2026, 8, 2), date(2026, 8, 29)) and a2[0] == date(2026, 8, 30)


def test_control_excludes_urls_touched_near_the_task() -> None:
    ctrl = to.control_urls(GSC, TASKS, task_id="T-00001", done=date(2026, 8, 1))
    assert "https://x.test/kombi" not in ctrl            # the task's own page
    # klima was done 70 days later — outside the ±60-day quiet window, so it may control
    assert set(ctrl) == {"https://x.test/a", "https://x.test/b", "https://x.test/c", "https://x.test/klima"}
    near = to.control_urls(GSC, TASKS, task_id="T-00002", done=date(2026, 10, 10))
    assert "https://x.test/klima" not in near
    assert ctrl == to.control_urls(GSC, TASKS, task_id="T-00001", done=date(2026, 8, 1))


def test_only_due_windows_of_done_tasks_are_planned() -> None:
    reqs = to.due_requests(TASKS, GSC, [], today=TODAY)
    keys = {(r.task_id, r.group, r.window) for r in reqs}
    assert ("T-00001", "treated", "after_56") in keys
    assert ("T-00002", "treated", "before") in keys
    assert ("T-00002", "treated", "after_28") not in keys        # not over yet
    assert not any(r.task_id == "T-00003" for r in reqs)          # not done


def test_recorded_measurements_are_not_planned_again(tmp_path: Path) -> None:
    first = to.due_requests(TASKS, GSC, [], today=TODAY)
    rows = [to.measurement_row(r.__dict__, {"rows": [{"clicks": 3, "impressions": 90, "position": 8}]},
                               measured_at="t") for r in first]
    ledger = tmp_path / "task_outcomes.jsonl"
    to.append_rows(ledger, rows)
    assert to.due_requests(TASKS, GSC, to.read_ledger(ledger), today=TODAY) == []


def _row(task, url, group, window, clicks, pos=8.0, src="quickwin"):
    return {"task_id": task, "url": url, "group": group, "window": window, "clicks": clicks,
            "impressions": clicks * 30, "position": pos, "primary_source": src}


def test_summary_compares_with_control_and_stays_honest() -> None:
    ledger = [
        _row("T1", "u1", "treated", "before", 100), _row("T1", "u1", "treated", "after_28", 150, 6.0),
        _row("T1", "c1", "control", "before", 100), _row("T1", "c1", "control", "after_28", 105),
    ]
    s = to.summarize(ledger)[0]
    assert s["primary_source"] == "quickwin" and s["difference_pp"] == 45.0
    assert s["verdict"] == "engine_positive" and s["caveat"] == "directional only (n<30)"
    assert s["median_position_delta"] == -2.0


def test_small_differences_are_indistinguishable() -> None:
    ledger = [
        _row("T1", "u1", "treated", "before", 100), _row("T1", "u1", "treated", "after_28", 108),
        _row("T1", "c1", "control", "before", 100), _row("T1", "c1", "control", "after_28", 102),
    ]
    assert to.summarize(ledger)[0]["verdict"] == "indistinguishable"


def test_coverage_counts_measured_done_tasks() -> None:
    ledger = [_row("T-00001", "https://x.test/kombi", "treated", "before", 1),
              _row("T-00001", "https://x.test/kombi", "treated", "after_28", 2)]
    cov = to.coverage(TASKS, ledger, today=TODAY)
    assert cov == {"eligible": 1, "measured": 1, "share": 1.0}


def test_one_fetch_per_window_and_missing_windows_are_not_zeroed() -> None:
    reqs = to.due_requests(TASKS, GSC, [], today=TODAY)
    windows = to.fetch_windows(reqs)
    assert len(windows) == len({(r.start, r.end) for r in reqs}) < len(reqs)
    first = windows[0]
    payload = {"rows": [{"keys": ["https://X.test/kombi/"], "clicks": 7, "impressions": 70, "position": 9.0}]}
    rows = to.rows_from_window_payloads(reqs, {(first["startDate"], first["endDate"]): payload},
                                        measured_at="t")
    assert rows and all((r["start"], r["end"]) == (first["startDate"], first["endDate"]) for r in rows)
    kombi = [r for r in rows if r["url"] == "https://x.test/kombi"]
    assert kombi and kombi[0]["clicks"] == 7


def test_monthly_report_carries_task_outcomes_and_validates() -> None:
    import json as _json
    from jsonschema import Draft7Validator
    from scripts.reporting import monthly_report as mr
    ctx = mr._build_measurement_context(
        "2026-09-01", "2026-09-30", [], None,
        task_outcomes=to.summarize([
            _row("T1", "u1", "treated", "before", 100), _row("T1", "u1", "treated", "after_28", 150),
            _row("T1", "c1", "control", "before", 100), _row("T1", "c1", "control", "after_28", 105)]),
        task_outcome_coverage={"eligible": 2, "measured": 1, "share": 0.5})
    schema = _json.loads((Path(__file__).resolve().parents[2] / "schemas" / "monthly-report.schema.json")
                         .read_text(encoding="utf-8"))
    mc_schema = schema["properties"]["sections"]["properties"]["measurement_context"]
    assert not list(Draft7Validator(mc_schema).iter_errors(ctx))
    assert ctx["task_outcomes"][0]["verdict"] == "engine_positive"


def test_truncated_window_is_not_recorded_as_zero() -> None:
    reqs = to.due_requests(TASKS, GSC, [], today=TODAY)
    w = to.fetch_windows(reqs)[0]
    assert w["rowLimit"] == 25000 and w["dimensions"] == "page"
    capped = {"rows": [{"keys": [f"https://x.test/p{i}"], "clicks": 1, "impressions": 1} for i in range(1000)]}
    assert to.rows_from_window_payloads(reqs, {(w["startDate"], w["endDate"]): capped}, measured_at="t") == []
