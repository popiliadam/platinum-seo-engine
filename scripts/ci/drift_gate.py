#!/usr/bin/env python3
"""drift_gate.py — CI step 1: run the REAL cross-sheet invariant validator (K-01).

The old step executed the python blocks of skills/governance/drift-check/
SKILL.md, whose real check calls were commented out and whose result was a
hand-written ``{"overall": "GREEN"}`` — 0 rules evaluated, exit 0 forever.

This gate copies ``templates/master-excel.xlsx`` (and, optionally, a seeded
fixture workbook) into a throw-away workspace, runs
``validate_invariants.main --json`` on it and fails when

* the overall verdict is RED (any invariant FAILs), or
* the set of NOT_IMPLEMENTED rules differs from ``EXPECTED_NOT_IMPLEMENTED``
  (a rule silently losing its check, or one being added without updating this
  list, must be a visible change), or
* fewer rules were evaluated than ``MIN_EVALUATED``.

Usage: python3 scripts/ci/drift_gate.py [--workbook PATH]
Exit 0 = pass, 1 = gate red, 2 = could not run.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.validation import validate_invariants as vi  # noqa: E402

PROJECT = "ci-fixture"
# Declared in schemas/cross-sheet-invariants.json with no check function yet —
# the same set, with reasons, as KNOWN_SCHEMA_ONLY in
# tests/schemas/test_cross_sheet_invariants_sync.py (K-02). Changing this list is a
# deliberate, reviewed act.
EXPECTED_NOT_IMPLEMENTED = frozenset({"D-01", "D-02", "F-06", "F-07", "M-01", "M-02"})
MIN_EVALUATED = 26


def run_gate(workbook: Path) -> tuple[int, dict]:
    """(exit code, report) for one workbook evaluated in a fresh workspace."""
    with tempfile.TemporaryDirectory(prefix="drift-gate-") as tmp:
        project_dir = Path(tmp) / "projects" / PROJECT
        project_dir.mkdir(parents=True)
        shutil.copyfile(workbook, project_dir / "master.xlsx")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = vi.main(["--project", PROJECT, "--workspace-root", tmp, "--json"])
    if rc == 2:
        return 2, {"error": "validator could not run", "output": out.getvalue()[-500:]}
    try:
        data = json.loads(out.getvalue())
    except ValueError:
        return 2, {"error": "validator output is not JSON", "output": out.getvalue()[-500:]}
    summary = data["summary"]
    not_impl = set(summary.get("not_implemented") or [])
    evaluated = len(data["checks"]) - len(not_impl)
    problems: list[str] = []
    if summary["overall"] == "RED":
        failed = [c["id"] for c in data["checks"] if c.get("verdict") == "FAIL"]
        problems.append(f"overall RED — failing invariants: {', '.join(failed)}")
    if not_impl != EXPECTED_NOT_IMPLEMENTED:
        problems.append(
            "NOT_IMPLEMENTED set changed: "
            f"new={sorted(not_impl - EXPECTED_NOT_IMPLEMENTED)} "
            f"gone={sorted(EXPECTED_NOT_IMPLEMENTED - not_impl)} — update "
            "EXPECTED_NOT_IMPLEMENTED deliberately")
    if evaluated < MIN_EVALUATED:
        problems.append(f"only {evaluated} rules evaluated (< {MIN_EVALUATED})")
    report = {"workbook": str(workbook), "overall": summary["overall"],
              "evaluated": evaluated, "declared": summary.get("declared_total"),
              "not_implemented": sorted(not_impl), "problems": problems}
    return (1 if problems else 0), report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="drift_gate.py")
    ap.add_argument("--workbook", action="append", default=None,
                    help="workbook(s) to evaluate (default: templates/master-excel.xlsx)")
    args = ap.parse_args(argv)
    workbooks = [Path(p) for p in (args.workbook or [REPO / "templates" / "master-excel.xlsx"])]
    worst = 0
    for wb in workbooks:
        rc, report = run_gate(wb)
        status = {0: "PASS", 1: "RED", 2: "ERROR"}[rc]
        print(f"drift-gate {status}: {json.dumps(report, ensure_ascii=False)}")
        worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    sys.exit(main())
