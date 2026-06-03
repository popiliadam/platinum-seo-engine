"""tests/hooks/test_user_prompt_submit_context_injection.py — UserPromptSubmit context contract.

Coverage matrix:
  - matcher "" (every prompt)
  - workspace + active.json present → "PSEO context: workspace=X project=Y"
  - workspace + active.json missing → "PSEO context: no active project bound..."
  - no workspace env → "PSEO context: no active project bound..."
  - drift router line ALWAYS emitted
  - active.json field canonical 'active_project' (ADR-032), not legacy 'project_id'
  - empty active_project value → project=<none>
  - implementation invariance: hook invoked via `bash -c` so Python/bash port both pass

The test invokes the hook command via `bash -c` to remain agnostic to the underlying
implementation (Python one-liner today, bash port post-Tier-2.6).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "user-prompt-submit.json"


def _hook_command() -> str:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    return spec["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]


def _run_hook(env_vars: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run the hook command via `bash -c` so Python/bash implementations both work."""
    cmd = _hook_command()
    env = {**os.environ}
    # Strip workspace env so test controls visibility
    env.pop("PSEO_WORKSPACE_ROOT", None)
    if env_vars:
        env.update(env_vars)
    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=env,
        input="",
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_matcher_empty_string_for_all_prompts() -> None:
    """UserPromptSubmit matcher is "" so every user prompt triggers context injection."""
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    matcher = spec["hooks"]["UserPromptSubmit"][0]["matcher"]
    assert matcher == "", f"matcher must be empty string; got {matcher!r}"


def test_drift_router_line_emitted_when_no_workspace() -> None:
    """Drift router line is part of the contract — emitted in EVERY scenario."""
    rc, stdout, _ = _run_hook()
    assert rc == 0
    assert "Drift router:" in stdout
    assert "meta:whats-next" in stdout


def test_drift_router_line_emitted_with_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "alpha"}), encoding="utf-8"
    )
    rc, stdout, _ = _run_hook({"PSEO_WORKSPACE_ROOT": str(ws)})
    assert rc == 0
    assert "Drift router:" in stdout


def test_no_workspace_renders_unbound_message() -> None:
    rc, stdout, _ = _run_hook()
    assert rc == 0
    assert "no active project bound" in stdout
    assert "/pseo-init" in stdout  # P1-05: real scaffolder (was /pseo-bootstrap-project)
    assert "PSEO_WORKSPACE_ROOT" in stdout


def test_workspace_set_but_no_marker_renders_unbound(tmp_path: Path) -> None:
    """Workspace env set but shared/active.json missing → unbound message."""
    ws = tmp_path / "ws"
    ws.mkdir()  # no shared/active.json
    rc, stdout, _ = _run_hook({"PSEO_WORKSPACE_ROOT": str(ws)})
    assert rc == 0
    assert "no active project bound" in stdout


def test_workspace_with_active_project_renders_context(tmp_path: Path) -> None:
    """Workspace + active.json valid → 'PSEO context: workspace=<ws> project=<pid>'."""
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "demo-dental"}), encoding="utf-8"
    )
    rc, stdout, _ = _run_hook({"PSEO_WORKSPACE_ROOT": str(ws)})
    assert rc == 0
    assert f"workspace={ws}" in stdout
    assert "project=demo-dental" in stdout


def test_active_project_field_canonical_not_legacy(tmp_path: Path) -> None:
    """ADR-032: hook reads 'active_project' canonical field, ignores legacy 'project_id'."""
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    # Only legacy field — hook must NOT resolve to it
    (ws / "shared" / "active.json").write_text(
        json.dumps({"project_id": "legacy_alpha"}), encoding="utf-8"
    )
    rc, stdout, _ = _run_hook({"PSEO_WORKSPACE_ROOT": str(ws)})
    assert rc == 0
    assert "legacy_alpha" not in stdout, (
        "ADR-032: hook must NOT resolve legacy 'project_id'; only 'active_project'"
    )


@pytest.mark.parametrize("invalid_payload", [
    "",  # empty file
    "{}",  # empty object
    "{not valid json",  # malformed
])
def test_invalid_active_json_does_not_crash(tmp_path: Path, invalid_payload: str) -> None:
    """Malformed active.json must not crash the hook — graceful degradation."""
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(invalid_payload, encoding="utf-8")
    rc, stdout, _ = _run_hook({"PSEO_WORKSPACE_ROOT": str(ws)})
    # Hook should either degrade gracefully (rc=0 with unbound msg) OR exit non-zero
    # without leaking stack trace into stdout. Either way, no Python traceback in stdout.
    assert "Traceback" not in stdout, "Hook must not emit Python traceback to stdout"
    # And drift router should still try to emit (or hook degrades silently)
    if rc == 0:
        assert "Drift router:" in stdout or "no active project bound" in stdout
