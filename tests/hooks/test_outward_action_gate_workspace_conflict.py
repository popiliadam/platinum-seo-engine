"""tests/hooks/test_outward_action_gate_workspace_conflict.py — Audit#2 #7 integration.

The #7 fix makes session_binding.resolve_workspace_root RAISE on an env-vs-config
workspace conflict. The gate invokes it as ``workspace_fn()``. That raise must NOT
escape evaluate() into main()'s fail-OPEN ``except`` (which would ALLOW a gated
action under a workspace MISCONFIGURATION). A gated action whose workspace cannot
be resolved cannot have its consent verified -> it must fail-CLOSED (deny). A plain
non-gated command must still never be bricked.
"""
from __future__ import annotations

from scripts.hooks import outward_action_gate as gate
from scripts.state import session_binding as sb


def _boom() -> object:
    raise sb.WorkspaceRootConflictError("env vs config workspace conflict")


def test_gated_action_denied_when_workspace_resolution_raises() -> None:
    code, _msgs = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": "git push origin main"},
         "session_id": "sess-conflict"},
        workspace_fn=_boom,
    )
    assert code == 2, (
        "a gated action under an unresolvable workspace must fail-CLOSED (deny), "
        "not slip through main()'s fail-open except"
    )


def test_non_gated_action_still_allowed_when_workspace_raises() -> None:
    # a NON-gated command short-circuits before workspace resolution, so it is
    # never bricked even if resolution would raise.
    code, msgs = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": "ls -la"},
         "session_id": "sess-conflict"},
        workspace_fn=_boom,
    )
    assert (code, msgs) == (0, [])
