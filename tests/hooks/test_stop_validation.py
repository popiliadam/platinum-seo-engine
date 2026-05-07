"""tests/hooks/test_stop_validation.py — Stop hook coverage (Tier 3 D1).

Coverage matrix:
  - hooks/stop.json structure: matcher + command + timeout + plugin agnostik path
  - clean tree (no git, no OQ) → silent stderr, exit 0
  - git uncommitted changes → 'git: N uncommitted change(s)' in stderr
  - OPEN_QUESTIONS.md with open Q-NN headers → 'OQ: N open' in stderr
  - resolved Q-NN headers (RESOLVED on same line) NOT counted
  - perf budget <1s (hook fires every turn — interaction velocity)
  - failsafe: bogus CLAUDE_PLUGIN_ROOT → still exits 0 (non-blocking by design)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "hooks" / "stop_validation.py"
HOOK_CONFIG = REPO_ROOT / "hooks" / "stop.json"


def test_stop_hook_config_valid() -> None:
    """stop.json structure must include matcher + command + timeout + plugin agnostik path."""
    spec = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert "Stop" in spec["hooks"]
    handlers = spec["hooks"]["Stop"]
    assert len(handlers) == 1
    handler = handlers[0]
    assert handler["matcher"] == ""
    assert len(handler["hooks"]) == 1
    cmd = handler["hooks"][0]
    assert cmd["type"] == "command"
    assert "stop_validation.py" in cmd["command"]
    assert "CLAUDE_PLUGIN_ROOT" in cmd["command"], (
        "Plugin agnostik path resolution required (F-16 invariant)"
    )
    assert cmd["timeout"] >= 10, f"timeout must allow git+OQ scan; got {cmd.get('timeout')}"


def test_stop_validation_script_exists() -> None:
    assert SCRIPT.exists(), f"Expected {SCRIPT} to exist"
    assert SCRIPT.is_file()


def test_stop_validation_clean_tree(tmp_path: Path) -> None:
    """No git, no OQ file → script silent (no parts to report)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0
    assert proc.stderr == "", f"Expected silent stderr; got {proc.stderr!r}"


def _init_git_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True, timeout=5)
    subprocess.run(
        ["git", "config", "user.email", "test@test.local"],
        cwd=str(tmp_path), check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True
    )


def test_stop_validation_with_git_drift(tmp_path: Path) -> None:
    """Modified file in git tree → stderr contains 'git: ... uncommitted change(s)'."""
    _init_git_repo(tmp_path)
    (tmp_path / "x.txt").write_text("hi")
    subprocess.run(["git", "add", "x.txt"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=str(tmp_path), check=True, timeout=5,
    )
    (tmp_path / "x.txt").write_text("modified")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0
    assert "git:" in proc.stderr
    assert "uncommitted" in proc.stderr


def test_stop_validation_open_oq_count(tmp_path: Path) -> None:
    """OPEN_QUESTIONS.md with 2 open + 1 resolved → 'OQ: 2 open' (resolved excluded)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "OPEN_QUESTIONS.md").write_text(
        "# Open Questions\n\n"
        "### Q-001: open question one\n"
        "body\n\n"
        "### Q-002: open question two\n"
        "body\n\n"
        "### Q-003: resolved question ✅ RESOLVED 2026-05-07\n"
        "body\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "OQ: 2 open" in proc.stderr, f"stderr={proc.stderr!r}"


def test_stop_validation_perf_budget(tmp_path: Path) -> None:
    """Perf <1s for typical scenario (hook fires every turn — UX velocity)."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(tmp_path),
    )
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0
    assert elapsed < 1.0, f"Stop validation too slow: {elapsed:.3f}s (budget <1s)"


def test_stop_validation_failsafe_bogus_root(tmp_path: Path) -> None:
    """Even with non-existent CLAUDE_PLUGIN_ROOT, hook exits 0 (non-blocking design)."""
    bogus = tmp_path / "does_not_exist_anywhere_xyz"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(bogus)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, "Hook must be non-blocking even on env errors"


def test_stop_validation_combined_drift_and_oq(tmp_path: Path) -> None:
    """Both git drift AND open OQ → both reported in single stderr line."""
    _init_git_repo(tmp_path)
    (tmp_path / "y.txt").write_text("staged")
    subprocess.run(["git", "add", "y.txt"], cwd=str(tmp_path), check=True)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "OPEN_QUESTIONS.md").write_text(
        "### Q-001: open\n", encoding="utf-8"
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0
    assert "git:" in proc.stderr
    assert "OQ: 1 open" in proc.stderr
    # Single line: parts joined with " | "
    assert "|" in proc.stderr, f"Expected combined output with separator; got {proc.stderr!r}"
