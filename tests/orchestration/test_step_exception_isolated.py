"""V-09: an exception in one step must not abort the whole workflow.

run_workflow / run_sequence promised that a failing step never aborts the loop,
but a WorkflowError / LockHeldError / RowSchemaError raised inside a step
escaped: earlier steps had already changed sheets, later steps never ran and no
coverage record was written. Each step is now isolated and recorded as failed
with a reason.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft7Validator

from scripts.excel.transaction import RowSchemaError
from scripts.orchestration import coverage
from scripts.orchestration.run_step import StepSpec, run_sequence

RUN_ID = "demo-2026-10-19-b09a"
SLUG = "demo"
NOW = 1_750_000_000
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8"))


def _drop(path: Path) -> Path:
    rows = [{"q": f"kw{i}"} for i in range(4)]
    path.write_text(json.dumps({"provenance": {
        "run_id": RUN_ID, "slug": SLUG, "declared_count": len(rows),
        "fetched_at": datetime.fromtimestamp(NOW - 60, tz=timezone.utc).isoformat(),
    }, "rows": rows}), encoding="utf-8")
    os.utime(path, (NOW - 60, NOW - 60))
    return path


def test_middle_step_exception_is_recorded_and_the_rest_still_run(tmp_path: Path) -> None:
    committed: list[str] = []

    def _commit(workbook_path, sheet, rows, **_kw):
        if sheet == "boom_sheet":
            raise RowSchemaError("bad row 3: status must be TODO|DONE")
        committed.append(sheet)
        return SimpleNamespace(rows_affected=len(rows))

    specs = [
        StepSpec(name=n, raw_path=_drop(tmp_path / f"{n}.json"), sheet=sh,
                 transform=lambda rows: list(rows))
        for n, sh in (("one", "topical_map"), ("two", "boom_sheet"), ("three", "quick_wins"))
    ]
    record = run_sequence(specs, run_id=RUN_ID, project_slug=SLUG, workspace_root=tmp_path,
                          workbook_path=tmp_path / "master.xlsx", now_epoch=NOW,
                          commit_fn=_commit)

    assert committed == ["topical_map", "quick_wins"]
    steps = {s["name"]: s for s in record["steps"]}
    assert steps["two"]["status"] == "failed"
    assert steps["two"]["reason"].startswith("exception:RowSchemaError")
    assert steps["three"]["status"] == "satisfied"
    assert record["verdict"] == "failed"
    written = json.loads(coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text())
    assert not list(Draft7Validator(SCHEMA).iter_errors(written))


def test_rejected_drop_carries_its_reason_code(tmp_path: Path) -> None:
    spec = StepSpec(name="gone", raw_path=tmp_path / "missing.json", sheet="topical_map",
                    transform=lambda rows: rows)
    record = run_sequence([spec], run_id=RUN_ID, project_slug=SLUG, workspace_root=tmp_path,
                          workbook_path=tmp_path / "master.xlsx", now_epoch=NOW, write=False,
                          commit_fn=lambda *a, **k: SimpleNamespace(rows_affected=0))
    assert record["steps"][0]["reason"] == "missing_file"
