"""End-to-end STUB harness for the monthly-maintenance driver (AMO batch 1d).

Mirrors ``test_run_step_e2e_stub.py``: canned provenance-stamped raw inbox drops
+ matching transform-output files are fed through the driver with a FAKE
commit_fn — NO live model, NO MCP, NO real workbook — and the driver's coverage
record is asserted per scenario (happy / missing-step / silent-skip / no-report),
proven to validate against the frozen coverage.schema.json, and tied to the
Turkish ``/pseo-run monthly <slug> --resume`` remediation on a non-pass verdict.

The driver uses run_step's ``transform`` as a LOADER of the model-produced
transform OUTPUT (it ignores the verified raw rows and returns the loaded output
rows); the silent-skip gate then compares raw input_count vs committed
scored_count — all WITHOUT any run_step change.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft7Validator

from scripts.orchestration import coverage
from scripts.orchestration.remediation import remediation
from scripts.orchestration.workflows import monthly_maintenance
from scripts.orchestration.workflows.monthly_maintenance import (
    STEPS,
    build_steps,
    inbox_path,
    output_path,
    run,
)

RUN_ID = "demo-furniture-2026-06-05-a1b2"
SLUG = "demo-furniture"
NOW = 1_750_000_000

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_SCHEMA = json.loads(
    (ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8")
)


def _schema_errors(record: dict) -> list:
    return list(Draft7Validator(COVERAGE_SCHEMA).iter_errors(record))


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _rows(n: int) -> list[dict]:
    return [{"q": f"kw{i}", "url": f"https://demo-furniture.example/p{i}"} for i in range(n)]


def _fake_commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None):
    """WriteResult-like: the driver reads only .rows_affected. No real workbook."""
    return SimpleNamespace(rows_affected=len(rows))


def _write_drop(workspace, entry, rows, *, declared_count=None, mtime=NOW - 60):
    """Provenance-stamped raw inbox drop matching this step's tool+window."""
    path = inbox_path(workspace, RUN_ID, SLUG, entry["name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provenance": {
            "run_id": RUN_ID,
            "slug": SLUG,
            "site_url": "https://demo-furniture.example",
            "window": entry["window"],
            "tool": entry["tool"],
            "fetched_at": _iso(NOW - 60),
            "declared_count": len(rows) if declared_count is None else declared_count,
        },
        "rows": rows,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _write_output(workspace, step_name, rows, *, as_dict=False):
    """Model-produced transform OUTPUT (master.xlsx-shaped rows)."""
    path = output_path(workspace, RUN_ID, SLUG, step_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rows": rows} if as_dict else rows), encoding="utf-8")
    return path


# --- driver wiring ---------------------------------------------------------

def test_step_table_is_the_three_structured_steps() -> None:
    assert [e["name"] for e in STEPS] == ["gsc_pull", "quick_wins", "content_decay"]
    assert [e["sheet"] for e in STEPS] == ["gsc_performance", "quick_wins", "content_decay"]


def test_build_steps_wires_one_spec_per_structured_step(tmp_path: Path) -> None:
    specs = build_steps(RUN_ID, SLUG, tmp_path)
    assert [s.name for s in specs] == [e["name"] for e in STEPS]
    for spec, entry in zip(specs, STEPS):
        assert spec.sheet == entry["sheet"]
        assert spec.verification_class == "code_verified"
        assert spec.expected_tool == entry["tool"]
        assert spec.expected_window == entry["window"]
        assert spec.observed_mcp == (entry["tool"],)
        # no project.config.json in the stub -> site_url stays unresolved (None),
        # and the driver must NOT hard-fail on that.
        assert spec.expected_site_url is None
        assert spec.raw_path == inbox_path(tmp_path, RUN_ID, SLUG, entry["name"])


def test_output_loader_ignores_raw_and_accepts_both_shapes(tmp_path: Path) -> None:
    out = output_path(tmp_path, RUN_ID, SLUG, "gsc_pull")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": [{"a": 1}]}), encoding="utf-8")
    loader = monthly_maintenance._output_loader(out)
    # IGNORES the verified raw rows; returns the loaded OUTPUT rows.
    assert loader([{"ignored": True}]) == [{"a": 1}]
    out.write_text(json.dumps([{"b": 2}]), encoding="utf-8")
    assert monthly_maintenance._output_loader(out)([]) == [{"b": 2}]


def test_output_loader_missing_file_raises(tmp_path: Path) -> None:
    loader = monthly_maintenance._output_loader(tmp_path / "nope.json")
    with pytest.raises(Exception):
        loader([])


# --- scenarios -------------------------------------------------------------

def test_happy_path_all_satisfied_verdict_pass(tmp_path: Path) -> None:
    for entry in STEPS:
        _write_drop(tmp_path, entry, _rows(10))
        _write_output(tmp_path, entry["name"], _rows(10))
    record = run(
        RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
        report_exists=True, commit_fn=_fake_commit,
    )
    assert record["verdict"] == "pass"
    assert record["required_satisfied"] is True
    assert len(record["steps"]) == 4

    code = [s for s in record["steps"] if s["verification_class"] == "code_verified"]
    attested = [s for s in record["steps"] if s["verification_class"] == "model_attested"]
    assert len(code) == 3 and all(s["status"] == "satisfied" for s in code)
    assert [s["name"] for s in attested] == ["monthly_report"]
    assert attested[0]["status"] == "satisfied"

    # the returned AND the written coverage records validate against the schema.
    assert _schema_errors(record) == []
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []

    # a passing run needs no remediation; the fake committer wrote NO real workbook.
    assert remediation(record, slug=SLUG) is None
    assert not (tmp_path / "master.xlsx").exists()


def test_missing_structured_step_is_incomplete(tmp_path: Path) -> None:
    for entry in STEPS:
        if entry["name"] == "quick_wins":
            continue  # no raw drop -> verify_raw_drop returns missing_file
        _write_drop(tmp_path, entry, _rows(10))
        _write_output(tmp_path, entry["name"], _rows(10))
    record = run(
        RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
        report_exists=True, commit_fn=_fake_commit, write=False,
    )
    statuses = {s["name"]: s["status"] for s in record["steps"]}
    assert statuses["quick_wins"] == "missing"
    assert record["verdict"] == "incomplete"

    rem = remediation(record, slug=SLUG)
    assert rem is not None
    assert "quick_wins" in rem["missing"]
    assert rem["one_line_fix_command"] == "/pseo-run monthly demo-furniture --resume"


def test_silent_skip_output_is_failed_not_pass(tmp_path: Path) -> None:
    for entry in STEPS:
        _write_drop(tmp_path, entry, _rows(10))
        # content_decay's transform output drops >50% of its raw rows (keeps 4).
        out_rows = _rows(4) if entry["name"] == "content_decay" else _rows(10)
        _write_output(tmp_path, entry["name"], out_rows)
    record = run(
        RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
        report_exists=True, commit_fn=_fake_commit, write=False,
    )
    decay = next(s for s in record["steps"] if s["name"] == "content_decay")
    assert decay["status"] == "failed"
    assert decay["input_count"] == 10 and decay["scored_count"] == 4
    assert record["verdict"] != "pass"  # silent-skip gate fired
    assert record["verdict"] == "failed"


def test_missing_report_is_not_pass(tmp_path: Path) -> None:
    for entry in STEPS:
        _write_drop(tmp_path, entry, _rows(10))
        _write_output(tmp_path, entry["name"], _rows(10))
    record = run(
        RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
        report_exists=False, commit_fn=_fake_commit, write=False,
    )
    report = next(s for s in record["steps"] if s["name"] == "monthly_report")
    assert report["verification_class"] == "model_attested"
    assert report["status"] == "missing"
    # all 3 structured steps satisfied, but the model_attested report is missing:
    # derive_verdict would read 'pass', so the driver's completion guard downgrades.
    assert record["verdict"] != "pass"
    assert remediation(record, slug=SLUG) is not None


# --- CLI boundary (clock-free: --now-epoch is required) --------------------

def test_cli_no_drops_prints_remediation_and_writes_coverage(tmp_path, capsys) -> None:
    rc = monthly_maintenance.main([
        "--workspace-root", str(tmp_path), "--slug", SLUG, "--run-id", RUN_ID,
        "--workbook", str(tmp_path / "master.xlsx"), "--now-epoch", str(NOW),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/pseo-run monthly demo-furniture --resume" in out
    assert "incomplete" in out
    # coverage written + valid; real committer never ran (every step missing).
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []
    assert not (tmp_path / "master.xlsx").exists()
