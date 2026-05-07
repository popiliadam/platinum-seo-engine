"""Regression tests for scripts/hooks/check_append_only.sh

Per rules/append-only-state.md: events.jsonl + workflows/{run_id}.json files
MUST NOT have lines mutated/deleted; only new lines may be appended.
The hook scans staged .jsonl diffs and rejects non-append commits.

Closes Q-V1.5-HOOK-SCRIPTS-MISSING-01 (option b — hook script + test deploy).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "check_append_only.sh"


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in cwd; return CompletedProcess."""
    return subprocess.run(
        ["git", *cmd], cwd=str(cwd), capture_output=True, text=True, timeout=10,
    )


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Initialize a throwaway git repo in tmp_path; isolate config."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    _git(["init", "-q", "-b", "main"], tmp_path)
    return tmp_path


def _run_hook(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run check_append_only.sh in cwd with optional args."""
    return subprocess.run(
        ["bash", str(HOOK), *args], cwd=str(cwd),
        capture_output=True, text=True, timeout=10,
    )


def test_hook_executable_present():
    """Sanity: hook script exists and is executable."""
    assert HOOK.is_file(), f"hook missing: {HOOK}"
    assert os.access(HOOK, os.X_OK), f"hook not executable: {HOOK}"


def test_help_flag(temp_repo: Path):
    """--help prints usage to stderr and exits 0."""
    result = _run_hook(temp_repo, "--help")
    assert result.returncode == 0
    assert "check_append_only.sh" in result.stderr


def test_usage_error_unknown_flag(temp_repo: Path):
    """Unknown flag exits 2 with usage message."""
    result = _run_hook(temp_repo, "--bogus")
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_no_jsonl_change_passes(temp_repo: Path):
    """Hook exits 0 when no .jsonl file is staged (nothing to enforce)."""
    (temp_repo / "readme.md").write_text("hello\n", encoding="utf-8")
    _git(["add", "readme.md"], temp_repo)
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_pure_append_passes(temp_repo: Path):
    """New jsonl lines appended → hook exits 0 (append-only valid)."""
    events = temp_repo / "events.jsonl"
    events.write_text('{"event_id":"a","kind":"work"}\n', encoding="utf-8")
    _git(["add", "events.jsonl"], temp_repo)
    _git(["commit", "-q", "-m", "initial"], temp_repo)
    # Append new lines (pure append — no existing line modified).
    with events.open("a", encoding="utf-8") as f:
        f.write('{"event_id":"b","kind":"work"}\n')
        f.write('{"event_id":"c","kind":"work"}\n')
    _git(["add", "events.jsonl"], temp_repo)
    result = _run_hook(temp_repo, "--staged")
    assert result.returncode == 0, (
        f"pure append should pass; stdout={result.stdout} stderr={result.stderr}"
    )


def test_line_modification_fails(temp_repo: Path):
    """Modifying an existing jsonl line → hook exits 1 (rejection)."""
    events = temp_repo / "events.jsonl"
    events.write_text(
        '{"event_id":"a","kind":"work"}\n'
        '{"event_id":"b","kind":"work"}\n',
        encoding="utf-8",
    )
    _git(["add", "events.jsonl"], temp_repo)
    _git(["commit", "-q", "-m", "initial"], temp_repo)
    # Mutate existing line.
    events.write_text(
        '{"event_id":"a-MUTATED","kind":"work"}\n'
        '{"event_id":"b","kind":"work"}\n',
        encoding="utf-8",
    )
    _git(["add", "events.jsonl"], temp_repo)
    result = _run_hook(temp_repo, "--staged")
    assert result.returncode == 1
    assert "non-append diff" in result.stderr
    assert "events.jsonl" in result.stderr


def test_line_deletion_fails(temp_repo: Path):
    """Deleting an existing jsonl line → hook exits 1 (rejection)."""
    events = temp_repo / "events.jsonl"
    events.write_text(
        '{"event_id":"a"}\n'
        '{"event_id":"b"}\n'
        '{"event_id":"c"}\n',
        encoding="utf-8",
    )
    _git(["add", "events.jsonl"], temp_repo)
    _git(["commit", "-q", "-m", "initial"], temp_repo)
    # Delete middle line.
    events.write_text(
        '{"event_id":"a"}\n'
        '{"event_id":"c"}\n',
        encoding="utf-8",
    )
    _git(["add", "events.jsonl"], temp_repo)
    result = _run_hook(temp_repo, "--staged")
    assert result.returncode == 1
    assert "non-append diff" in result.stderr


def test_non_jsonl_change_ignored(temp_repo: Path):
    """Editing .json (NOT .jsonl) → hook exits 0 (out of scope)."""
    cfg = temp_repo / "config.json"
    cfg.write_text('{"a": 1}\n', encoding="utf-8")
    _git(["add", "config.json"], temp_repo)
    _git(["commit", "-q", "-m", "initial"], temp_repo)
    # Mutate .json (rule applies to .jsonl, not .json).
    cfg.write_text('{"a": 999}\n', encoding="utf-8")
    _git(["add", "config.json"], temp_repo)
    result = _run_hook(temp_repo, "--staged")
    assert result.returncode == 0


def test_working_tree_mode(temp_repo: Path):
    """--working-tree checks unstaged diff (modified jsonl in working dir)."""
    events = temp_repo / "events.jsonl"
    events.write_text('{"event_id":"a"}\n', encoding="utf-8")
    _git(["add", "events.jsonl"], temp_repo)
    _git(["commit", "-q", "-m", "initial"], temp_repo)
    # Mutate but DO NOT stage.
    events.write_text('{"event_id":"a-MUTATED"}\n', encoding="utf-8")
    result = _run_hook(temp_repo, "--working-tree")
    assert result.returncode == 1, result.stderr
    assert "non-append diff" in result.stderr
