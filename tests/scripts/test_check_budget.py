"""Smoke tests for scripts/budget/check_budget.py."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
