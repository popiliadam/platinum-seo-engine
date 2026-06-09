"""tests/hooks/test_post_tool_use_bash_classification.py — P1-06.

The PostToolUse audit hook hardcoded audit_action="accessed" for ALL Bash
commands, so a destructive `rm`/redirect/`cp` was logged as a mere access — and
events_writer.normalize_audit_action(command=...) (which already classifies
rm-family -> deleted, write/redirect -> modified, read -> accessed) was unused.

These are END-TO-END tests: they run the real hook command and read back the
audit_action ACTUALLY recorded in events.jsonl, exercising the whole chain
(stdin payload -> classification -> append_audit -> events.schema validation).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "post-tool-use.json"
SLUG = "test-proj"


def _hook_command() -> str:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    return spec["hooks"]["PostToolUse"][0]["hooks"][0]["command"]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "shared").mkdir(parents=True, exist_ok=True)
    (tmp_path / "shared" / "active.json").write_text(
        json.dumps({"active_project": SLUG}), encoding="utf-8"
    )
    (tmp_path / "projects" / SLUG / "_state").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _run_hook(workspace: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    # Use the running interpreter (has jsonschema) instead of bare `python3`.
    cmd = _hook_command().replace("python3", shlex.quote(sys.executable), 1)
    env = {
        **os.environ,
        # Isolate HOME so the hook's resolve_workspace_root() cannot read the
        # operator's real ~/.config/pseo/config.json (which WINS over the env var
        # by design — D9). Without this, the 4 end-to-end assertions fail on ANY
        # machine that has bound a workspace (config.json present) — they passed
        # only on a clean CI home. The tmp workspace has no .config/, so the
        # resolver correctly falls back to PSEO_WORKSPACE_ROOT below.
        "HOME": str(workspace),
        "PSEO_WORKSPACE_ROOT": str(workspace),
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
    }
    proc = subprocess.run(
        cmd, shell=True, input=json.dumps(payload),
        capture_output=True, text=True, timeout=30, env=env,
    )
    # The hook is non-blocking: it must always exit 0.
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    return proc


def _last_audit_action(workspace: Path) -> str:
    p = workspace / "projects" / SLUG / "_state" / "events.jsonl"
    assert p.exists(), "hook did not write events.jsonl"
    events = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    audits = [e for e in events if e.get("event_kind") == "audit"]
    assert audits, f"no audit event recorded; events={events!r}"
    return audits[-1]["audit_action"]


def test_bash_rm_recorded_as_deleted(workspace: Path) -> None:
    _run_hook(workspace, {"tool_name": "Bash", "tool_input": {"command": "rm foo.txt"}})
    assert _last_audit_action(workspace) == "deleted"


def test_bash_redirect_recorded_as_modified(workspace: Path) -> None:
    _run_hook(workspace, {"tool_name": "Bash", "tool_input": {"command": "echo x > out.txt"}})
    assert _last_audit_action(workspace) == "modified"


def test_bash_cp_recorded_as_modified(workspace: Path) -> None:
    _run_hook(workspace, {"tool_name": "Bash", "tool_input": {"command": "cp a.txt b.txt"}})
    assert _last_audit_action(workspace) == "modified"


def test_bash_read_still_accessed(workspace: Path) -> None:
    # Read-only commands stay 'accessed' (no regression for the common case).
    _run_hook(workspace, {"tool_name": "Bash", "tool_input": {"command": "ls /tmp"}})
    assert _last_audit_action(workspace) == "accessed"
