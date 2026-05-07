"""Regression tests for scripts/hooks/validate_before_write.py

Per rules/schema-first.md (§8.2): a data shape must have a schema in
schemas/{name}.schema.json BEFORE the kod that writes it lands. The hook
scans staged kod files for `schemas/<slug>.schema.json` path references
and rejects commits where the referenced schema is not also staged in
the same commit (paired-update discipline).

"Kod" = staged Python files under:
  - scripts/state/
  - scripts/excel/
  - scripts/discovery/
  - scripts/planning/
  - scripts/validation/

Out of scope (intentional):
  - tests/, docs/, rules/, memory/
  - scripts/hooks/, scripts/ci/, scripts/util/, scripts/release/, etc.
    (these don't emit data writes; modifying them doesn't risk shape drift)

Escape hatch:
  --allow-kod-only — explicit override for non-shape-changing refactors
  (e.g., import cleanup, type annotations, comments).

Closes Q-V1.5-HOOK-SCRIPTS-MISSING-01 (Y-04 — final 2 of 4 hooks).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "validate_before_write.py"


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *cmd], cwd=str(cwd), capture_output=True, text=True, timeout=10,
    )


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    _git(["init", "-q", "-b", "main"], tmp_path)
    return tmp_path


def _run_hook(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=10,
    )


def _write(cwd: Path, rel_path: str, content: str) -> Path:
    """Write content at rel_path under cwd, ensuring parents exist."""
    full = cwd / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def _stage(cwd: Path, rel_path: str, content: str) -> None:
    _write(cwd, rel_path, content)
    _git(["add", rel_path], cwd)


def _commit_initial(cwd: Path) -> None:
    _stage(cwd, "README.md", "# initial\n")
    _git(["commit", "-q", "-m", "initial"], cwd)


def _schema_content(name: str) -> str:
    return json.dumps(
        {"$id": f"http://platinum-seo-engine/schemas/{name}", "type": "object"},
    )


def test_hook_executable_present():
    """Sanity: hook script exists and is executable."""
    assert HOOK.is_file(), f"hook missing: {HOOK}"
    assert os.access(HOOK, os.X_OK), f"hook not executable: {HOOK}"


def test_help_flag(temp_repo: Path):
    """--help prints usage and exits 0."""
    result = _run_hook(temp_repo, "--help")
    assert result.returncode == 0
    assert "validate_before_write" in (result.stdout + result.stderr).lower()


def test_no_files_changed_passes(temp_repo: Path):
    """No staged files → exits 0."""
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_schema_only_modified_passes(temp_repo: Path):
    """Only schemas/foo.schema.json staged → exits 0 (schema PR before kod)."""
    _stage(temp_repo, "schemas/foo.schema.json", _schema_content("foo"))
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_kod_only_when_no_schema_reference_passes(temp_repo: Path):
    """Kod file with NO schemas/* reference → exits 0 (out of scope)."""
    _stage(
        temp_repo,
        "scripts/state/helper.py",
        "def helper():\n    return 42\n",
    )
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_kod_modified_without_schema_change_when_schema_referenced_rejects(
    temp_repo: Path,
):
    """Kod references schemas/X.schema.json but X NOT staged → exits 1."""
    # First commit a baseline schema (already on disk, NOT in this commit).
    _stage(temp_repo, "schemas/foo.schema.json", _schema_content("foo"))
    _git(["commit", "-q", "-m", "schema baseline"], temp_repo)
    # Stage a kod file that references the existing schema.
    _stage(
        temp_repo,
        "scripts/state/writer.py",
        'from pathlib import Path\n'
        'SCHEMA = Path("schemas/foo.schema.json")\n',
    )
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "schemas/foo.schema.json" in result.stderr
    assert "scripts/state/writer.py" in result.stderr
    assert "rules/schema-first.md" in result.stderr


def test_schema_modified_with_kod_change_passes(temp_repo: Path):
    """Both schema + kod staged in same commit → exits 0 (paired update)."""
    _stage(temp_repo, "schemas/foo.schema.json", _schema_content("foo"))
    _stage(
        temp_repo,
        "scripts/state/writer.py",
        'SCHEMA = "schemas/foo.schema.json"\n',
    )
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_test_only_modified_passes(temp_repo: Path):
    """Only tests/ files staged → exits 0 (out of scope)."""
    _stage(
        temp_repo, "tests/state/test_writer.py",
        'SCHEMA = "schemas/foo.schema.json"\n',  # schema ref in tests is fine
    )
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_doc_only_modified_passes(temp_repo: Path):
    """Only docs/rules/memory files staged → exits 0 (out of scope)."""
    _stage(
        temp_repo, "docs/RELEASE_NOTES.md",
        "Schema: schemas/foo.schema.json\n",  # mention is fine in docs
    )
    _stage(temp_repo, "rules/some-rule.md", "## body\n")
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_partial_schema_pair_rejects(temp_repo: Path):
    """Kod references both A.schema.json + B.schema.json, only A staged → exits 1."""
    _stage(temp_repo, "schemas/aaa.schema.json", _schema_content("aaa"))
    _stage(temp_repo, "schemas/bbb.schema.json", _schema_content("bbb"))
    _git(["commit", "-q", "-m", "schemas baseline"], temp_repo)
    # Now in a new commit, stage A + kod, but NOT B.
    _stage(temp_repo, "schemas/aaa.schema.json", _schema_content("aaa") + "\n")
    _stage(
        temp_repo,
        "scripts/discovery/foo_transform.py",
        'A = "schemas/aaa.schema.json"\n'
        'B = "schemas/bbb.schema.json"\n',
    )
    result = _run_hook(temp_repo)
    assert result.returncode == 1, result.stderr
    assert "schemas/bbb.schema.json" in result.stderr
    # A should NOT be in the violation list (it IS staged).
    # We assert by counting "ERROR:" prefixed lines.
    error_lines = [
        line for line in result.stderr.splitlines()
        if line.startswith("ERROR:")
    ]
    assert len(error_lines) == 1, error_lines


def test_allow_kod_only_escape_hatch(temp_repo: Path):
    """--allow-kod-only bypass for non-shape refactors → exits 0 with warning."""
    _stage(temp_repo, "schemas/foo.schema.json", _schema_content("foo"))
    _git(["commit", "-q", "-m", "schema baseline"], temp_repo)
    _stage(
        temp_repo,
        "scripts/state/writer.py",
        '# refactor: rename only\nSCHEMA = "schemas/foo.schema.json"\n',
    )
    result = _run_hook(temp_repo, "--allow-kod-only")
    assert result.returncode == 0
    assert "WARNING" in result.stderr
    assert "--allow-kod-only" in result.stderr


def test_kod_in_excel_dir_detected(temp_repo: Path):
    """scripts/excel/ recognized as kod directory."""
    _stage(temp_repo, "schemas/foo.schema.json", _schema_content("foo"))
    _git(["commit", "-q", "-m", "schema baseline"], temp_repo)
    _stage(
        temp_repo,
        "scripts/excel/transaction.py",
        'SCHEMA = "schemas/foo.schema.json"\n',
    )
    result = _run_hook(temp_repo)
    assert result.returncode == 1
    assert "scripts/excel/transaction.py" in result.stderr


def test_non_kod_script_dir_passes(temp_repo: Path):
    """scripts/util/ is OUT of scope even with schema reference (utility code)."""
    _stage(temp_repo, "schemas/foo.schema.json", _schema_content("foo"))
    _git(["commit", "-q", "-m", "schema baseline"], temp_repo)
    _stage(
        temp_repo,
        "scripts/util/helper.py",
        'SCHEMA = "schemas/foo.schema.json"\n',
    )
    result = _run_hook(temp_repo)
    assert result.returncode == 0, result.stderr


def test_working_tree_mode(temp_repo: Path):
    """--working-tree checks unstaged diff (intent-to-add new file)."""
    _stage(temp_repo, "schemas/foo.schema.json", _schema_content("foo"))
    _git(["commit", "-q", "-m", "schema baseline"], temp_repo)
    # Create unstaged kod file with reference.
    _write(
        temp_repo,
        "scripts/state/writer.py",
        'SCHEMA = "schemas/foo.schema.json"\n',
    )
    _git(["add", "-N", "scripts/state/writer.py"], temp_repo)
    result = _run_hook(temp_repo, "--working-tree")
    assert result.returncode == 1, result.stderr
    assert "scripts/state/writer.py" in result.stderr
