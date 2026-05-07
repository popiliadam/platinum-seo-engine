"""Smoke test for scripts/state/bootstrap_project.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "state" / "bootstrap_project.py"

WS_ROOT_FOR_TESTS = "~/Documents/platinum-seo-workspace"


def _env_with_ws_root(ws_root: str = WS_ROOT_FOR_TESTS) -> dict:
    """Return env dict with PSEO_WORKSPACE_ROOT set (Q-V1.4-BOOTSTRAP-PATHS-01:
    workspace_root env is REQUIRED — no engine repo path fallback)."""
    return {**os.environ, "PSEO_WORKSPACE_ROOT": ws_root}


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
        env=_env_with_ws_root(),
    )
    assert result.returncode == 0, result.stderr
    cfg = json.loads(result.stdout)
    assert cfg["project_id"] == "test-slug"
    assert cfg["schema_version"] == "1.3"
    assert "paths" in cfg and "gsc" in cfg and "dataforseo" in cfg
    assert cfg["profiles"] == ["local-service"]


def test_missing_project_arg_fails() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0


def test_missing_workspace_root_env_fails() -> None:
    """PSEO_WORKSPACE_ROOT env is REQUIRED — bootstrap exits 2 with clear
    error message when unset (no engine repo path fallback; F-16 invariant)."""
    env = {k: v for k, v in os.environ.items() if k != "PSEO_WORKSPACE_ROOT"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "test-slug",
         "--domain", "https://test.example/",
         "--profile", "local-service",
         "--dry-run"],
        capture_output=True, text=True, timeout=15,
        env=env,
    )
    assert result.returncode == 2, result.stderr
    assert "PSEO_WORKSPACE_ROOT" in result.stderr
