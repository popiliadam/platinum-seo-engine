"""Smoke test for scripts/security/check_secrets.sh."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "security" / "check_secrets.sh"


def test_script_exists_and_executable() -> None:
    assert SCRIPT.exists(), f"missing: {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, "script not executable"


def test_bash_syntax_check() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_runs_clean_on_empty_dir(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GREEN" in result.stdout
