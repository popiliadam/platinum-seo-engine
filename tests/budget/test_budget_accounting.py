"""tests/budget/test_budget_accounting.py — Wave 2 budget accounting e2e.

Round-trip kanıt: events_writer.append_provenance (mirroring
skills/ingestion/dfs-pull/SKILL.md Step 9 line 292-304) writes a
provenance event with `cost={"provider","credits","budget_key"}`,
then scripts/budget/check_budget.py reads it and reports a non-zero
``used_24h``.

Q-PHASE15-BUDGET-COST-01 SELF-RESOLVED: original audit assumed
dfs_pull.py orchestrates the event write — but Phase 6 D-003 split
made dfs_pull.py a pure transform (no side effects). The skill
orchestrator (inline Python in SKILL.md) is the writer. This test
locks the writer→reader contract end-to-end so future regressions in
either side surface immediately.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHECK_BUDGET = REPO / "scripts" / "budget" / "check_budget.py"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal workspace + project structure events_writer expects."""
    project_slug = "wave2-budget-test"
    project_dir = tmp_path / "projects" / project_slug
    (project_dir / "_state").mkdir(parents=True)
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(tmp_path))
    return project_dir


def test_append_provenance_then_check_budget_e2e(
    workspace: Path, tmp_path: Path
) -> None:
    """SKILL.md Step 9 → check_budget round trip."""
    sys.path.insert(0, str(REPO))
    from scripts.state import events_writer

    project_slug = "wave2-budget-test"
    estimate = 1.5  # mirrors dfs_pull.estimate_credits(1) = 1.0 + 0.5

    events_writer.append_provenance(
        project_id=project_slug,
        run_id=events_writer.next_run_id(project_slug),
        source={
            "kind": "dataforseo_mcp",
            "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_overview",
            "response_bytes": 1024,
        },
        operation="ingest",
        target_excel_sheet=None,
        rows_written=1,
        cost={
            "provider": "dataforseo",
            "credits": float(estimate),
            "budget_key": "project.config.dataforseo.budget_credits_per_day",
        },
    )

    cfg_path = workspace / "project.config.json"
    cfg_path.write_text(
        json.dumps({"dataforseo": {"budget_credits_per_day": 100}}),
        encoding="utf-8",
    )
    events_path = workspace / "_state" / "events.jsonl"
    assert events_path.exists(), "events_writer should have created events.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_BUDGET),
            "--project-config",
            str(cfg_path),
            "--events",
            str(events_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["used_24h"] == 1.5, (
        f"Expected used_24h=1.5 from cost.credits, got {payload['used_24h']}. "
        "Writer→reader contract broken — see rules/budget-events.md."
    )
    assert payload["budget_per_day"] == 100
    assert payload["remaining"] == 98.5
    assert payload["exceeded"] is False


def test_multiple_provenance_events_aggregate(
    workspace: Path, tmp_path: Path
) -> None:
    """Three provenance events → check_budget sums all three."""
    sys.path.insert(0, str(REPO))
    from scripts.state import events_writer

    project_slug = "wave2-budget-test"
    for credits in (10.0, 25.0, 5.5):
        events_writer.append_provenance(
            project_id=project_slug,
            run_id=events_writer.next_run_id(project_slug),
            source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
                    "mcp_tool": "x", "response_bytes": 100},
            operation="ingest",
            target_excel_sheet=None,
            rows_written=1,
            cost={"provider": "dataforseo", "credits": credits,
                  "budget_key": "project.config.dataforseo.budget_credits_per_day"},
        )

    cfg_path = workspace / "project.config.json"
    cfg_path.write_text(
        json.dumps({"dataforseo": {"budget_credits_per_day": 100}}),
        encoding="utf-8",
    )
    events_path = workspace / "_state" / "events.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_BUDGET),
            "--project-config", str(cfg_path),
            "--events", str(events_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["used_24h"] == 40.5  # 10 + 25 + 5.5
