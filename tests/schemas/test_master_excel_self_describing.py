"""Regression: master-excel.schema.json MUST self-describe.

K-03 + K-04 from docs/audits/v1.4-rules-schemas-templates-2026-05-07.md:
- $id (added in Tier 1 Step 2 — already passing)
- title (Tier 1 Step 3)
- definitions/taskIdPattern (Tier 1 Step 3)
- master_task col A task_id field uses ref to taskIdPattern (Tier 1 Step 3)

Authority cross-refs:
- rules/master-task-id.md:30 claims master-excel.schema.json#/definitions/taskIdPattern
- rules/naming.md schema $id format (ADR-012)
"""
import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "master-excel.schema.json"


def _load():
    with SCHEMA_PATH.open() as f:
        return json.load(f)


def test_master_excel_has_id():
    """ADR-012 + naming.md: $id is mandatory."""
    data = _load()
    assert data.get("$id") == "http://platinum-seo-engine/schemas/master-excel"


def test_master_excel_has_title():
    """Self-describing: title field present (K-03)."""
    data = _load()
    title = data.get("title")
    assert title, "master-excel.schema.json: title field missing (K-03)"
    assert "Master Excel" in title, f"title={title!r} should mention 'Master Excel'"


def test_master_excel_has_task_id_pattern_definition():
    """rules/master-task-id.md:30 cross-ref: definitions/taskIdPattern MUST exist (K-04)."""
    data = _load()
    defs = data.get("definitions", {})
    assert "taskIdPattern" in defs, (
        "master-excel.schema.json definitions/taskIdPattern missing — "
        "rules/master-task-id.md:30 cross-ref broken"
    )
    pattern_def = defs["taskIdPattern"]
    assert pattern_def.get("pattern") == r"^T-[0-9]{4,}$", (
        f"taskIdPattern.pattern={pattern_def.get('pattern')!r} != ^T-[0-9]{{4,}}$"
    )


def test_master_task_task_id_uses_pattern_ref():
    """master_task col A task_id MUST reference taskIdPattern (K-04)."""
    data = _load()
    master_task = data["sheets"]["master_task"]
    cols = master_task["required_columns"]
    task_id_col = next((c for c in cols if c.get("name") == "task_id"), None)
    assert task_id_col is not None, "master_task: no col with name='task_id'"
    has_ref = task_id_col.get("ref") == "#/definitions/taskIdPattern"
    has_inline = task_id_col.get("pattern") == r"^T-[0-9]{4,}$"
    assert has_ref or has_inline, (
        f"master_task.task_id (col {task_id_col.get('col')}) MUST use "
        f"ref=#/definitions/taskIdPattern OR inline pattern. Got: {task_id_col!r}"
    )
