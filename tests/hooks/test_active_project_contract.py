"""tests/hooks/test_active_project_contract.py — active.json field-name contract (ADR-032).

Coverage:
  1. user-prompt-submit.json reads `active_project` (canonical, written by
     /pseo-active and pseo-init.md), not the legacy `project_id` placeholder.
  2. That direct reader resolves the project id when the file contains
     `{"active_project": "..."}` and silently no-ops when the field is absent / file missing.
  3. Implementation-agnostic: the hook command may be Python or bash — invoked via `bash -c`
     to ride either implementation (Python one-liner pre-Tier-2.6, bash port post-Tier-2.6).
  4. post-tool-use.json no longer reads active.json INLINE — AMO batch 0d extracted its
     audit emitter to scripts/hooks/audit_post_tool_use.py, which resolves the project via
     scripts.state.session_binding (session marker → canonical `active_project`). The
     delegation keeps the ADR-032 field contract; test_post_tool_use_delegates_* locks it.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"

# Hooks that read the active.json marker INLINE (the direct-reader contract surface).
# post-tool-use.json is NO LONGER here: batch 0d delegates its resolution to the
# audit script + session_binding (see test_post_tool_use_delegates_* below).
ACTIVE_READERS = ("user-prompt-submit.json",)


def _active_project_command(hook_filename: str) -> str:
    """Return the hook command string that references active.json (impl-agnostic)."""
    spec = json.loads((HOOKS_DIR / hook_filename).read_text(encoding="utf-8"))
    events = list(spec["hooks"].values())
    for handlers in events:
        for handler in handlers:
            for h in handler["hooks"]:
                if h["type"] == "command" and "active.json" in h["command"]:
                    return h["command"]
    raise AssertionError(f"{hook_filename}: no active.json reader found")


@pytest.mark.parametrize("hook_filename", ACTIVE_READERS)
def test_hook_reads_active_project_field(hook_filename: str) -> None:
    """Hook command must reference the canonical 'active_project' field, not 'project_id'."""
    cmd = _active_project_command(hook_filename)
    assert '"active_project"' in cmd, (
        f"{hook_filename}: must reference canonical 'active_project' field (ADR-032). "
        f"Found: {cmd!r}"
    )
    assert '"project_id"' not in cmd, (
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

    cmd = _active_project_command("user-prompt-submit.json")
    env = {**os.environ, "PSEO_WORKSPACE_ROOT": str(ws), "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, f"hook exited nonzero: {proc.stderr!r}"
    assert "project=alpha" in proc.stdout, (
        f"hook did not resolve active_project=alpha; stdout={proc.stdout!r}"
    )


def test_no_workspace_silent_skip() -> None:
    """Without PSEO_WORKSPACE_ROOT, the hook prints the unbound-context message and exits 0."""
    cmd = _active_project_command("user-prompt-submit.json")
    env = {k: v for k, v in os.environ.items() if k != "PSEO_WORKSPACE_ROOT"}
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "no active project bound" in proc.stdout


def test_post_tool_use_delegates_active_project_to_session_binding() -> None:
    """post-tool-use.json no longer reads active.json inline; it invokes the batch-0d
    audit script, which resolves the project via session_binding — the canonical
    `active_project` field, never legacy `project_id`. ADR-032 contract preserved."""
    spec = json.loads((HOOKS_DIR / "post-tool-use.json").read_text(encoding="utf-8"))
    commands = [
        h["command"]
        for handlers in spec["hooks"].values()
        for handler in handlers
        for h in handler["hooks"]
        if h.get("type") == "command"
    ]
    assert any("audit_post_tool_use.py" in c for c in commands), (
        "post-tool-use.json must wire the batch-0d audit script"
    )
    # No command reads active.json inline anymore (resolution is delegated).
    assert not any("active.json" in c for c in commands), (
        "post-tool-use.json should delegate active.json resolution to the script, "
        "not read it inline"
    )

    script = (REPO_ROOT / "scripts" / "hooks" / "audit_post_tool_use.py").read_text(encoding="utf-8")
    assert "resolve_session_project" in script, "audit script must delegate to session_binding"

    session_binding = (REPO_ROOT / "scripts" / "state" / "session_binding.py").read_text(encoding="utf-8")
    assert '"active_project"' in session_binding, "session_binding must read canonical active_project"
    assert '"project_id"' not in session_binding, (
        "session_binding must not read the legacy project_id field from active.json (ADR-032)"
    )
