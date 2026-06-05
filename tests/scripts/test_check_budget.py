"""Smoke tests for scripts/budget/check_budget.py."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.budget import check_budget

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "budget" / "check_budget.py"


def _write_config(tmp_path: Path, budget: int) -> Path:
    cfg = {"dataforseo": {"budget_credits_per_day": budget}}
    p = tmp_path / "project.config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def _write_events(tmp_path: Path, lines: list[dict]) -> Path:
    p = tmp_path / "events.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")
    return p


def _run(config: Path, events: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project-config", str(config), "--events", str(events)],
        capture_output=True,
        text=True,
    )


def test_under_budget_returns_zero(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 500)
    now = datetime.now(timezone.utc)
    events = _write_events(tmp_path, [
        {
            "event_kind": "provenance",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "source": {"kind": "dataforseo_mcp"},
            "cost": {"credits": 50},
        },
        {
            "event_kind": "provenance",
            "timestamp": (now - timedelta(hours=30)).isoformat(),  # outside 24h window
            "source": {"kind": "dataforseo_mcp"},
            "cost": {"credits": 9999},
        },
    ])
    result = _run(cfg, events)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["budget_per_day"] == 500
    assert payload["used_24h"] == 50
    assert payload["remaining"] == 450
    assert payload["exceeded"] is False


def test_missing_events_file_treated_as_zero_usage(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 500)
    nonexistent = tmp_path / "does_not_exist.jsonl"
    result = _run(cfg, nonexistent)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["used_24h"] == 0
    assert payload["remaining"] == 500
    assert payload["exceeded"] is False


# ---------------------------------------------------------------------------
# preflight() — the importable contract content-decay Step 4b depends on
# (B6-01). Unlike main()/the CLI, preflight folds an *about-to-run* call's
# estimated_credits into trailing-24h spend and returns a projected envelope
# with no stdout / no sys.exit, so the skill can gate (raise BudgetGateError)
# instead of silently falling back to GSC-only.
# ---------------------------------------------------------------------------

def test_preflight_under_budget_envelope(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 500)
    now = datetime.now(timezone.utc)
    events = _write_events(tmp_path, [
        {
            "event_kind": "provenance",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "source": {"kind": "dataforseo_mcp"},
            "cost": {"credits": 50},
        },
    ])
    env = check_budget.preflight(
        project_config_path=cfg, events_path=events,
        estimated_credits=1, now=now,
    )
    assert env["budget_per_day"] == 500
    assert env["used_24h"] == 50
    assert env["estimated_credits"] == 1
    assert env["projected"] == 51
    assert env["remaining"] == 449  # budget - projected
    assert env["exceeded"] is False


def test_preflight_exceeded_when_projected_breaches_budget(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 100)
    now = datetime.now(timezone.utc)
    events = _write_events(tmp_path, [
        {
            "event_kind": "provenance",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "source": {"kind": "dataforseo_mcp"},
            "cost": {"credits": 100},
        },
    ])
    env = check_budget.preflight(
        project_config_path=cfg, events_path=events,
        estimated_credits=1, now=now,
    )
    assert env["projected"] == 101
    assert env["remaining"] == -1
    assert env["exceeded"] is True


def test_preflight_missing_events_is_zero_usage(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 500)
    env = check_budget.preflight(
        project_config_path=cfg,
        events_path=tmp_path / "does_not_exist.jsonl",
        estimated_credits=5,
    )
    assert env["used_24h"] == 0
    assert env["projected"] == 5
    assert env["exceeded"] is False


def test_preflight_rejects_negative_estimate(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, 500)
    events = _write_events(tmp_path, [])
    with pytest.raises(ValueError):
        check_budget.preflight(
            project_config_path=cfg, events_path=events,
            estimated_credits=-1,
        )


def test_budget_gate_error_is_exception() -> None:
    """content-decay Step 4b raises check_budget.BudgetGateError to transition
    the run to awaiting_approval rather than a silent GSC-only fallback."""
    assert issubclass(check_budget.BudgetGateError, Exception)


def test_preflight_unreadable_config_raises_not_exits(tmp_path: Path) -> None:
    """preflight() must never leak SystemExit (a process kill) to a library
    caller: _load_budget() sys.exits for the CLI, but here an unreadable
    project-config surfaces as a catchable BudgetGateError."""
    missing_config = tmp_path / "does_not_exist.json"
    events = _write_events(tmp_path, [])
    with pytest.raises(check_budget.BudgetGateError):
        check_budget.preflight(
            project_config_path=missing_config,
            events_path=events,
            estimated_credits=1,
        )
