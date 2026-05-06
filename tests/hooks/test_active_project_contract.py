"""tests/hooks/test_active_project_contract.py — active.json field-name contract (ADR-032).

Coverage:
  1. post-tool-use.json + user-prompt-submit.json read `active_project` (canonical, written
     by /pseo-active and pseo-init.md), not the legacy `project_id` placeholder.
  2. The two hooks that DO read active.json resolve the project id when the file contains
     `{"active_project": "..."}` and silently no-op when the field is absent / file missing.
  3. The other two hooks (pre-tool-use.json + session-start.json) do not depend on the
     active.json field naming and are not regressed by the rename.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"

# Hooks that read the active.json marker via Python (the contract surface).
PYTHON_ACTIVE_READERS = ("post-tool-use.json", "user-prompt-submit.json")


def _python_command(hook_filename: str) -> str:
    """Extract the python3 -c command body from a hook file."""
    spec = json.loads((HOOKS_DIR / hook_filename).read_text(encoding="utf-8"))
    # All hook files are { hooks: { <Event>: [ { hooks: [ { type:"command", command:"..." } ] } ] } }
    events = list(spec["hooks"].values())
    commands = []
    for handlers in events:
        for handler in handlers:
            for h in handler["hooks"]:
                if h["type"] == "command":
                    commands.append(h["command"])
    # Find the python3 -c invocation (there may be multiple; pick the one referencing active.json).
    for cmd in commands:
        if "active.json" in cmd and "python3" in cmd:
            return cmd
    raise AssertionError(f"{hook_filename}: no python3 active.json reader found")


@pytest.mark.parametrize("hook_filename", PYTHON_ACTIVE_READERS)
def test_hook_reads_active_project_field(hook_filename: str) -> None:
    """Hook command must reference the canonical 'active_project' field, not 'project_id'."""
    cmd = _python_command(hook_filename)
    assert 'get("active_project")' in cmd, (
        f"{hook_filename}: must read .active_project from active.json (ADR-032). "
        f"Found: {cmd!r}"
    )
    assert 'get("project_id")' not in cmd, (
        f"{hook_filename}: legacy 'project_id' field must not be read from active.json "
        f"(ADR-032 supersedes; pseo-active.md writes 'active_project')."
    )


def test_active_project_pid_resolution(tmp_path: Path) -> None:
    """End-to-end: with PSEO_WORKSPACE_ROOT set + shared/active.json present, the
    UserPromptSubmit hook resolves the active project id and emits a context line.
    """
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "alpha"}), encoding="utf-8"
    )

    cmd = _python_command("user-prompt-submit.json")
    # Strip the shell wrapper: extract the inline python source between the first single
    # quote following `python3 -c ` and the matching closing single quote.
    m = re.search(r"python3 -c '([^']+(?:'\\\\''[^']*)*)'", cmd)
    assert m, "Could not extract inline python from hook command"
    inline = m.group(1)

    env = dict(os.environ)
    env["PSEO_WORKSPACE_ROOT"] = str(ws)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", inline],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, f"hook exited nonzero: {proc.stderr!r}"
    assert "project=alpha" in proc.stdout, (
        f"hook did not resolve active_project=alpha; stdout={proc.stdout!r}"
    )


def test_no_workspace_silent_skip(tmp_path: Path) -> None:
    """Without PSEO_WORKSPACE_ROOT, the hook prints the unbound-context message and exits 0."""
    cmd = _python_command("user-prompt-submit.json")
    m = re.search(r"python3 -c '([^']+(?:'\\\\''[^']*)*)'", cmd)
    assert m
    inline = m.group(1)

    env = {k: v for k, v in os.environ.items() if k != "PSEO_WORKSPACE_ROOT"}
    proc = subprocess.run(
        [sys.executable, "-c", inline],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "no active project bound" in proc.stdout
