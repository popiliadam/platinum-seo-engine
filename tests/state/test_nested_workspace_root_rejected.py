"""V-14: no events.jsonl may land under projects/<slug>/projects/<slug>/_state/.

transaction derived the workspace root as three levels above the workbook's
_state dir. A workbook kept deeper inside a project folder (an outputs/ copy, a
scratch dir) made that "root" the project folder itself, and events_writer
happily created projects/<slug>/projects/<slug>/_state/events.jsonl — 185 rows
across four projects that no report or drift check ever read.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.excel import transaction
from scripts.state import events_writer
from scripts.state.events_writer import EventPathError

SLUG = "demo-proj"


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    proj = ws / "projects" / SLUG
    (proj / "_state").mkdir(parents=True)
    (proj / "project.config.json").write_text("{}", encoding="utf-8")
    return ws


def _audit(workspace_root: Path) -> None:
    events_writer.append_audit(
        project_id=SLUG, audit_action="modified", audit_target="x",
        actor="test", workspace_root=workspace_root,
    )


def test_events_writer_rejects_a_project_folder_as_workspace_root(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    with pytest.raises(EventPathError, match="inside project"):
        _audit(ws / "projects" / SLUG)
    assert not (ws / "projects" / SLUG / "projects").exists()


def test_events_writer_rejects_a_root_deeper_inside_a_project(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    deep = ws / "projects" / SLUG / "outputs" / "run1"
    deep.mkdir(parents=True)
    with pytest.raises(EventPathError, match="inside project"):
        _audit(deep)
    assert not (deep / "projects").exists()


def test_workspace_under_a_folder_named_projects_is_fine(tmp_path: Path) -> None:
    """~/projects/seo-workspace is a normal place to keep a workspace."""
    ws = tmp_path / "projects" / "seo-workspace"
    (ws / "projects" / SLUG / "_state").mkdir(parents=True)
    _audit(ws)
    assert (ws / "projects" / SLUG / "_state" / "events.jsonl").exists()


def _topical_row() -> dict:
    return {
        "pillar": "P01", "cluster": "c", "primary_keyword": "kw", "monthly_volume": 1,
        "data_source": "gsc", "assigned_url": "/u", "page_type": "pillar",
        "status": "TODO", "priority": "HIGH", "note": "",
    }


def test_deep_workbook_provenance_lands_in_the_real_project_log(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    deep_wb = ws / "projects" / SLUG / "outputs" / "copy" / "master.xlsx"
    deep_wb.parent.mkdir(parents=True)
    result = transaction.append(deep_wb, "topical_map", [_topical_row()], SLUG)
    assert result.event_id  # emitted, not swallowed into an anomaly
    real_log = ws / "projects" / SLUG / "_state" / "events.jsonl"
    events = [json.loads(line) for line in real_log.read_text().splitlines()]
    assert [e["target_excel_sheet"] for e in events] == ["topical_map"]
    assert not list((ws / "projects" / SLUG).rglob("projects"))
