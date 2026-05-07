"""tests/hooks/test_subagent_output_validate.py — SubagentStop hook coverage (Tier 3 D2).

Coverage matrix:
  - hooks/subagent-stop.json structure: matcher + command + timeout + plugin agnostik
  - no PSEO_WORKSPACE_ROOT → silent no-op, exit 0
  - workspace bound, no events.jsonl under projects/*/_state/ → silent
  - events.jsonl with valid envelope (event_kind + schema_version) → silent
  - events.jsonl missing envelope fields → WARN to stderr
  - events.jsonl with malformed JSON line → graceful (still exits 0, warns)
  - perf <1s even with 1000-entry events.jsonl (we read tail 5 only)
  - failsafe: exit 0 in all error paths
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "hooks" / "subagent_output_validate.py"
HOOK_CONFIG = REPO_ROOT / "hooks" / "subagent-stop.json"


def test_subagent_stop_hook_config_valid() -> None:
    spec = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert "SubagentStop" in spec["hooks"]
    handlers = spec["hooks"]["SubagentStop"]
    assert len(handlers) == 1
    handler = handlers[0]
    assert handler["matcher"] == ""
    assert len(handler["hooks"]) == 1
    cmd = handler["hooks"][0]
    assert cmd["type"] == "command"
    assert "subagent_output_validate.py" in cmd["command"]
    assert "CLAUDE_PLUGIN_ROOT" in cmd["command"], (
        "Plugin agnostik path resolution required (F-16)"
    )
    assert cmd["timeout"] >= 10


def test_subagent_validation_script_exists() -> None:
    assert SCRIPT.exists(), f"Expected {SCRIPT} to exist"


def _env_without_workspace() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k != "PSEO_WORKSPACE_ROOT"}


def test_no_workspace_silent_exit_zero() -> None:
    """Without PSEO_WORKSPACE_ROOT, script exits 0 with no stderr (silent no-op)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=_env_without_workspace(),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert proc.stderr == "", f"Expected silent no-op; got {proc.stderr!r}"


def test_workspace_no_events_silent(tmp_path: Path) -> None:
    """Workspace bound but no events.jsonl under projects/*/_state/ → silent."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "PSEO_WORKSPACE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert proc.stderr == ""


def _write_events(events_path: Path, lines: list[str]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")


def _valid_envelope() -> dict[str, str]:
    return {
        "schema_version": "0.5.0",
        "event_kind": "work",
        "event_id": "01HXTEST",
        "timestamp": "2026-05-07T00:00:00Z",
        "project_id": "alpha",
    }


def test_valid_events_silent(tmp_path: Path) -> None:
    """events.jsonl with valid envelope shape → no warnings."""
    events_path = tmp_path / "projects" / "alpha" / "_state" / "events.jsonl"
    _write_events(events_path, [json.dumps(_valid_envelope()) for _ in range(5)])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "PSEO_WORKSPACE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "WARN" not in proc.stderr, f"Unexpected warning: {proc.stderr!r}"


def test_missing_envelope_fields_warns(tmp_path: Path) -> None:
    """Entries missing event_kind or schema_version → WARN to stderr."""
    events_path = tmp_path / "projects" / "beta" / "_state" / "events.jsonl"
    bad = {"timestamp": "2026-05-07T00:00:00Z", "project_id": "beta"}
    _write_events(events_path, [json.dumps(bad) for _ in range(3)])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "PSEO_WORKSPACE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "WARN" in proc.stderr
    assert "schema sniff" in proc.stderr.lower() or "schema sniff" in proc.stderr


def test_malformed_json_handled_gracefully(tmp_path: Path) -> None:
    """Malformed JSON line counted as failed, but no crash."""
    events_path = tmp_path / "projects" / "gamma" / "_state" / "events.jsonl"
    valid = json.dumps(_valid_envelope())
    _write_events(events_path, [valid, "{not valid json", valid])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "PSEO_WORKSPACE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "WARN" in proc.stderr  # 1 malformed / 3 total → warn


def test_perf_budget_with_large_events(tmp_path: Path) -> None:
    """Perf <1s even with 1000-entry events.jsonl (script tails last 5 only)."""
    events_path = tmp_path / "projects" / "perf" / "_state" / "events.jsonl"
    valid = json.dumps(_valid_envelope())
    _write_events(events_path, [valid for _ in range(1000)])
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "PSEO_WORKSPACE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0
    assert elapsed < 1.0, f"SubagentStop too slow: {elapsed:.3f}s (budget <1s)"


def test_multiple_projects_each_checked(tmp_path: Path) -> None:
    """Multiple projects/<slug>/_state/events.jsonl files all inspected."""
    project_alpha = tmp_path / "projects" / "alpha" / "_state" / "events.jsonl"
    project_beta = tmp_path / "projects" / "beta" / "_state" / "events.jsonl"
    bad = {"timestamp": "2026-05-07T00:00:00Z"}  # missing envelope fields
    _write_events(project_alpha, [json.dumps(_valid_envelope())])
    _write_events(project_beta, [json.dumps(bad)])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "PSEO_WORKSPACE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "WARN" in proc.stderr
    # beta has the mismatch — relative path should mention beta
    assert "beta" in proc.stderr
