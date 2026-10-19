"""K-01 / K-03 — CI step 1 runs the real invariant validator and can go red.

The old step executed SKILL.md blocks whose checks were commented out and whose
result was a hard-coded GREEN. drift_gate runs validate_invariants on a copy of
the template workbook; a broken invariant must turn it red (judge self-test).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from openpyxl import load_workbook

from scripts.ci import drift_gate as dg

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "master-excel.xlsx"


def _header_row(sheet: str) -> int:
    schema = json.loads((ROOT / "schemas" / "master-excel.schema.json").read_text(encoding="utf-8"))
    return int(schema["sheets"][sheet]["header_row"])


def test_template_passes_with_the_known_unimplemented_rules() -> None:
    rc, report = dg.run_gate(TEMPLATE, seed=True)
    assert rc == 0, report
    assert report["overall"] == "AMBER" and report["decided"] >= dg.MIN_DECIDED
    assert set(report["not_implemented"]) == dg.EXPECTED_NOT_IMPLEMENTED


def test_duplicate_task_id_turns_the_gate_red(tmp_path: Path) -> None:
    broken = tmp_path / "fixture-broken.xlsx"
    shutil.copyfile(TEMPLATE, broken)
    wb = load_workbook(broken)
    ws = wb["master_task"]
    hr = _header_row("master_task")
    headers = [c.value for c in ws[hr]]
    col = headers.index("task_id") + 1
    for offset in (1, 2):  # the same task_id twice -> F-09 FAIL
        ws.cell(row=hr + offset, column=col, value="T-00001")
    wb.save(broken)
    rc, report = dg.run_gate(broken)
    assert rc == 1 and report["overall"] == "RED", report
    assert any("F-09" in p for p in report["problems"]), report


def test_manual_triage_fail_also_turns_the_gate_red(tmp_path: Path) -> None:
    """Review of K-01: D-03 FAIL aggregates to AMBER, but on the engine's own
    fixture any FAIL is a defect — the gate must still go red."""
    broken = tmp_path / "fixture-raw-url.xlsx"
    shutil.copyfile(TEMPLATE, broken)
    wb = load_workbook(broken)
    ws = wb["gsc_performance"]
    hr = _header_row("gsc_performance")
    headers = [c.value for c in ws[hr]]
    ws.cell(row=hr + 1, column=headers.index("url") + 1, value="https://Example.test/kombi/")
    wb.save(broken)
    rc, report = dg.run_gate(broken)
    assert rc == 1 and report["overall"] == "AMBER" and "D-03" in report["problems"][0], report


def test_skipping_checks_cannot_keep_the_gate_green(monkeypatch) -> None:
    """Review of K-01: SKIP is not 'evaluated'."""
    monkeypatch.setattr(dg, "MIN_DECIDED", 99)
    rc, report = dg.run_gate(TEMPLATE, seed=True)
    assert rc == 1 and "reached PASS/FAIL" in report["problems"][-1]


def test_ci_step_1_runs_the_gate() -> None:
    cfg = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    step = next(s for s in cfg["jobs"]["ci"]["steps"] if s.get("name") == "1. drift-check")
    assert step["run"].strip() == "python3 scripts/ci/drift_gate.py"
