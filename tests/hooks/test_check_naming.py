"""Regression tests for scripts/hooks/check_naming.py

Per rules/naming.md (§8.6): all identifiers (slug, filename, skill, schema $id,
slash command, run_id) MUST follow the project's single naming contract.
The hook scans staged file paths and rejects naming violations.

Coverage scope:
- skills/<slug>/SKILL.md          → folder slug regex `^[a-z][a-z0-9-]*$`
- commands/<filename>.md          → must match `pseo-<slug>.md`
- schemas/<name>.schema.json      → name slug regex + $id content check
                                    ($id must be `http://platinum-seo-engine/schemas/<slug>`)

Out of scope (existing CI tests cover):
- Excel sheet snake_case (test_excel_*)
- Python variable snake_case (linters)
- run_id format runtime (workflow-run schema validate)

Closes Q-V1.5-HOOK-SCRIPTS-MISSING-01 (final 2 of 4 — Y-03).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "check_naming.py"


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in cwd; return CompletedProcess."""
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
    _git(["init", "-q", "-b", "main"], tmp_path)
    return tmp_path


def _run_hook(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke hook with optional args."""
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=10,
    )


def _stage(cwd: Path, rel_path: str, content: str = "") -> None:
    """Create file at rel_path in cwd, stage it."""
    full = cwd / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    _git(["add", rel_path], cwd)


def test_hook_executable_present():
    """Sanity: hook script exists and is executable."""
    assert HOOK.is_file(), f"hook missing: {HOOK}"
    assert os.access(HOOK, os.X_OK), f"hook not executable: {HOOK}"


def test_help_flag(temp_repo: Path):
    """--help prints usage and exits 0."""
    result = _run_hook(temp_repo, "--help")
    assert result.returncode == 0
    assert "check_naming" in (result.stdout + result.stderr).lower()


def test_no_files_changed_passes(temp_repo: Path):
    """No staged files → hook exits 0 (nothing to enforce)."""
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_unrelated_file_passes(temp_repo: Path):
    """File outside enforcement scope (e.g., docs/README.md) → exits 0."""
    _stage(temp_repo, "docs/README.md", "# README\n")
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_valid_skill_folder_passes(temp_repo: Path):
    """skills/<valid-slug>/SKILL.md → exits 0."""
    _stage(temp_repo, "skills/init-project/SKILL.md", "---\nname: init-project\n---\n")
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_invalid_skill_folder_uppercase_fails(temp_repo: Path):
    """skills/Init-Project/SKILL.md → exits 1 (CamelCase)."""
    _stage(temp_repo, "skills/Init-Project/SKILL.md", "---\n---\n")
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "Init-Project" in result.stderr
    assert "rules/naming.md" in result.stderr


def test_invalid_skill_folder_underscore_fails(temp_repo: Path):
    """skills/init_project/SKILL.md → exits 1 (snake_case not allowed; kebab-case only)."""
    _stage(temp_repo, "skills/init_project/SKILL.md", "---\n---\n")
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "init_project" in result.stderr


def test_valid_command_md_passes(temp_repo: Path):
    """commands/pseo-init-project.md → exits 0."""
    _stage(temp_repo, "commands/pseo-init-project.md", "command body\n")
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_invalid_command_md_no_pseo_prefix_fails(temp_repo: Path):
    """commands/init-project.md → exits 1 (must have pseo- prefix)."""
    _stage(temp_repo, "commands/init-project.md", "")
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "pseo-" in result.stderr
    assert "init-project.md" in result.stderr


def test_invalid_command_md_uppercase_fails(temp_repo: Path):
    """commands/pseo-InitProject.md → exits 1 (CamelCase in slug)."""
    _stage(temp_repo, "commands/pseo-InitProject.md", "")
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "InitProject" in result.stderr


def test_valid_schema_filename_passes(temp_repo: Path):
    """schemas/master-excel.schema.json with valid $id → exits 0."""
    schema = {
        "$id": "http://platinum-seo-engine/schemas/master-excel",
        "type": "object",
    }
    _stage(temp_repo, "schemas/master-excel.schema.json", json.dumps(schema))
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_invalid_schema_filename_uppercase_fails(temp_repo: Path):
    """schemas/MasterExcel.schema.json → exits 1 (CamelCase filename)."""
    schema = {
        "$id": "http://platinum-seo-engine/schemas/MasterExcel",
        "type": "object",
    }
    _stage(temp_repo, "schemas/MasterExcel.schema.json", json.dumps(schema))
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "MasterExcel" in result.stderr


def test_invalid_schema_id_wrong_host_fails(temp_repo: Path):
    """schemas/foo.schema.json with $id wrong host → exits 1."""
    schema = {
        "$id": "https://example.com/x",
        "type": "object",
    }
    _stage(temp_repo, "schemas/foo.schema.json", json.dumps(schema))
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "$id" in result.stderr
    # ADR-012: HTTP host must be platinum-seo-engine
    assert "platinum-seo-engine" in result.stderr


def test_invalid_schema_id_https_fails(temp_repo: Path):
    """ADR-012: $id MUST be http (not https). https://platinum-seo-engine/... → exits 1."""
    schema = {
        "$id": "https://platinum-seo-engine/schemas/foo",
        "type": "object",
    }
    _stage(temp_repo, "schemas/foo.schema.json", json.dumps(schema))
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "$id" in result.stderr


def test_multiple_violations_reported(temp_repo: Path):
    """Multiple naming violations across files → all reported, exit 1."""
    _stage(temp_repo, "skills/Bad-Folder/SKILL.md", "---\n---\n")
    _stage(temp_repo, "commands/no-prefix.md", "")
    schema = {"$id": "https://example.com/x"}
    _stage(temp_repo, "schemas/Bad.schema.json", json.dumps(schema))
    result = _run_hook(temp_repo)
    assert result.returncode == 1
    # All three violations should surface
    assert "Bad-Folder" in result.stderr
    assert "no-prefix.md" in result.stderr
    assert "Bad.schema.json" in result.stderr


def test_working_tree_mode(temp_repo: Path):
    """--working-tree checks unstaged diff."""
    # Commit a baseline file first.
    _stage(temp_repo, "docs/README.md", "# README\n")
    _git(["commit", "-q", "-m", "initial"], temp_repo)
    # Create unstaged invalid file.
    bad = temp_repo / "skills" / "Bad-Folder" / "SKILL.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\n---\n", encoding="utf-8")
    # Use git add -N (intent-to-add) so the path appears in working-tree diff.
    _git(["add", "-N", "skills/Bad-Folder/SKILL.md"], temp_repo)
    result = _run_hook(temp_repo, "--working-tree")
    assert result.returncode == 1, result.stderr
    assert "Bad-Folder" in result.stderr
