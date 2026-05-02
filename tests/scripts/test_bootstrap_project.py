"""Smoke test for scripts/state/bootstrap_project.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "state" / "bootstrap_project.py"


def test_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "--project" in result.stdout


def test_dry_run_emits_valid_json() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "test-slug",
         "--domain", "https://test.example/",
         "--profile", "local-service",
         "--dry-run"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    cfg = json.loads(result.stdout)
    assert cfg["project_id"] == "test-slug"
    assert cfg["schema_version"] == "1.1"
    assert "paths" in cfg and "gsc" in cfg and "dataforseo" in cfg
    assert cfg["profiles"] == ["local-service"]


def test_missing_project_arg_fails() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
