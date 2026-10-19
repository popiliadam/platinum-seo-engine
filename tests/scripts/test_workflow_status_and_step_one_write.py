"""V-08: fail() / request_approval() change the run status and the step in ONE write.

They used to write the status, then patch the step in a second locked write. A
bad step_index made the second write raise after the run was already "failed",
so the workflow event (and any anomaly) was never recorded.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.state import workflow_runner as wr

SLUG = "test-proj"


def _run(tmp_path: Path):
    (tmp_path / "projects" / SLUG / "_state" / "workflows").mkdir(parents=True)
    return wr.create_run(skill="s", project_slug=SLUG,
                         steps=[{"name": "fetch"}, {"name": "write"}],
                         workspace_root=tmp_path)


def _workflow_events(tmp_path: Path) -> list[dict]:
    p = tmp_path / "projects" / SLUG / "_state" / "events.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return [e for e in rows if e["event_kind"] == "workflow"]


def test_fail_with_bad_step_index_changes_nothing(tmp_path: Path) -> None:
    handle = _run(tmp_path)
    events_before = _workflow_events(tmp_path)
    with pytest.raises(wr.ValidationError, match="step_index"):
        wr.fail(handle.run_id, project_slug=SLUG, code="internal_error", message="m",
                step_index=7, workspace_root=tmp_path)
    assert wr.get(handle.run_id, project_slug=SLUG, workspace_root=tmp_path).status == "running"
    assert _workflow_events(tmp_path) == events_before


def test_fail_updates_status_and_step_together(tmp_path: Path) -> None:
    handle = _run(tmp_path)
    wr.fail(handle.run_id, project_slug=SLUG, code="internal_error", message="m",
            step_index=1, error_details="boom", workspace_root=tmp_path)
    data = wr.get(handle.run_id, project_slug=SLUG, workspace_root=tmp_path).data
    assert data["status"] == "failed"
    assert data["steps"][1]["status"] == "failed"
    assert data["steps"][1]["error"] == "boom"
    assert _workflow_events(tmp_path)[-1]["workflow_action"] == "failed"


def test_request_approval_with_bad_step_index_changes_nothing(tmp_path: Path) -> None:
    handle = _run(tmp_path)
    with pytest.raises(wr.ValidationError, match="step_index"):
        wr.request_approval(handle.run_id, project_slug=SLUG, approver="u",
                            subject="s", step_index=-1, workspace_root=tmp_path)
    assert wr.get(handle.run_id, project_slug=SLUG, workspace_root=tmp_path).status == "running"
