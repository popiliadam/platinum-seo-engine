"""Regression tests for scripts/hooks/check_excel_writer.py

Per rules/excel-discipline.md (§8.5): master.xlsx writes MUST go through
scripts/excel/transaction.py. Direct edits via LibreOffice/Excel/openpyxl
are FORBIDDEN. Hook scans staged diff and rejects unless writer signal
(commit message ref, env var, or --allow-direct-edit) is present.

Closes Q-V1.5-HOOK-SCRIPTS-MISSING-01 (option b — hook script + test deploy).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "check_excel_writer.py"


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *cmd], cwd=str(cwd), capture_output=True, text=True, timeout=10,
    )


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Throwaway git repo for isolated diff testing."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    monkeypatch.delenv("PSEO_EXCEL_WRITER", raising=False)
    monkeypatch.delenv("PSEO_COMMIT_MSG_FILE", raising=False)
    _git(["init", "-q", "-b", "main"], tmp_path)
    return tmp_path


def _run_hook(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Invoke hook with optional args and env override."""
    actual_env = os.environ.copy()
    if env is not None:
        actual_env.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=10,
        env=actual_env,
    )


def test_hook_executable_present():
    """Sanity: hook script exists and is executable."""
    assert HOOK.is_file(), f"hook missing: {HOOK}"
    assert os.access(HOOK, os.X_OK), f"hook not executable: {HOOK}"


def test_no_xlsx_change_passes(temp_repo: Path):
    """No master.xlsx in staged diff → hook exits 0."""
    (temp_repo / "readme.md").write_text("hello\n", encoding="utf-8")
    _git(["add", "readme.md"], temp_repo)
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_master_xlsx_no_signal_fails(temp_repo: Path):
    """master.xlsx changed without writer signal → hook exits 1."""
    xlsx = temp_repo / "master.xlsx"
    xlsx.write_bytes(b"PK\x03\x04stub-xlsx-content")
    _git(["add", "master.xlsx"], temp_repo)
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "transaction.py" in result.stderr
    assert "master.xlsx" in result.stderr


def test_master_excel_legacy_basename_fails(temp_repo: Path):
    """Legacy basename master-excel.xlsx also triggers rejection."""
    xlsx = temp_repo / "master-excel.xlsx"
    xlsx.write_bytes(b"PK\x03\x04legacy-xlsx-content")
    _git(["add", "master-excel.xlsx"], temp_repo)
    result = _run_hook(temp_repo)
    assert result.returncode == 1
    assert "master-excel.xlsx" in result.stderr


def test_env_writer_signal_passes(temp_repo: Path):
    """PSEO_EXCEL_WRITER=transaction.py env var → hook accepts."""
    xlsx = temp_repo / "master.xlsx"
    xlsx.write_bytes(b"PK\x03\x04new")
    _git(["add", "master.xlsx"], temp_repo)
    result = _run_hook(temp_repo, env={"PSEO_EXCEL_WRITER": "transaction.py"})
    assert result.returncode == 0, result.stderr


def test_commit_msg_signal_passes(temp_repo: Path, tmp_path: Path):
    """Commit message containing 'transaction.py' → hook accepts."""
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text(
        "fix(workspace): regenerate master via transaction.py\n", encoding="utf-8",
    )
    xlsx = temp_repo / "master.xlsx"
    xlsx.write_bytes(b"PK\x03\x04new")
    _git(["add", "master.xlsx"], temp_repo)
    result = _run_hook(temp_repo, "--commit-msg-file", str(msg_file))
    assert result.returncode == 0, result.stderr


def test_allow_direct_edit_passes(temp_repo: Path):
    """--allow-direct-edit explicit override → hook accepts with warning."""
    xlsx = temp_repo / "master.xlsx"
    xlsx.write_bytes(b"PK\x03\x04migration")
    _git(["add", "master.xlsx"], temp_repo)
    result = _run_hook(temp_repo, "--allow-direct-edit")
    assert result.returncode == 0
    assert "WARNING" in result.stderr
    assert "--allow-direct-edit" in result.stderr


def test_other_xlsx_unaffected(temp_repo: Path):
    """Non-master xlsx (e.g. analytics.xlsx) → hook exits 0 (out of scope)."""
    xlsx = temp_repo / "analytics.xlsx"
    xlsx.write_bytes(b"PK\x03\x04analytics")
    _git(["add", "analytics.xlsx"], temp_repo)
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_master_in_subdir_detected(temp_repo: Path):
    """master.xlsx in nested path (workspace/projects/foo/master.xlsx) detected."""
    nested = temp_repo / "workspace" / "projects" / "foo"
    nested.mkdir(parents=True)
    xlsx = nested / "master.xlsx"
    xlsx.write_bytes(b"PK\x03\x04nested")
    _git(["add", str(xlsx.relative_to(temp_repo))], temp_repo)
    result = _run_hook(temp_repo)
    assert result.returncode == 1
    assert "master.xlsx" in result.stderr
