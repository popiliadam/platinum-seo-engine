#!/usr/bin/env python3
"""scripts/hooks/audit_post_tool_use.py — session-aware PostToolUse audit emitter.

Extracted (AMO batch 0d) from the inline ``python3 -c`` audit command that lived
in ``hooks/post-tool-use.json``. The extraction fixes audit bug **H1**: the inline
command attributed EVERY audit event to the workspace-GLOBAL
``shared/active.json`` ``active_project``, so with 3-5 parallel Claude sessions
(one per project — the AMO goal) every session's audit events were stamped with
whichever project ``active.json`` last named → silent cross-project contamination
of the append-only ``events.jsonl`` ledgers.

The fix resolves the target project for THIS session via the batch-0b/0c binding
primitive (``scripts.state.session_binding.resolve_session_project``): the
per-session marker (``shared/sessions/<session_id>.json``) wins, falling back to
``shared/active.json`` only when the session is UNBOUND. Single-project users
(no session marker) keep today's active.json behaviour — no regression.

Everything else is byte-for-byte the legacy emission:
  * the REDACTED audit_target — Bash collapses to ``<head> [REDACTED args]`` and
    NEVER records command args (secret or otherwise); other tools use the
    file path. Always prefixed ``<ToolName>:`` and capped at 480 chars.
  * the audit_action mapping — Edit→``modified``; Write→``modified`` if the path
    already exists else ``created``; Bash/other→``normalize_audit_action``.
  * the NON-BLOCKING contract — any failure prints a WARNING to stderr and exits
    0, mirroring the old ``|| { echo 'WARNING …'; true; }``. Empty/garbage stdin
    is a clean no-op.

Wired as a runtime hook in ``hooks/post-tool-use.json`` (matcher Edit|Write|Bash);
classified RUNTIME in ``tests/hooks/test_hook_scripts_runtime_vs_ci.py`` +
``scripts/hooks/README.md``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make ``scripts.*`` importable when run as a bare hook subprocess
# (mirrors scripts/hooks/validate_content_write.py).
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from scripts.state.events_writer import (  # noqa: E402
    append_audit,
    normalize_audit_action,
)
from scripts.state.session_binding import (  # noqa: E402
    current_session_id,
    resolve_session_project,
    resolve_workspace_root,
)

_ACTOR = "claude-code:hook:PostToolUse"
_WARNING = (
    "WARNING: PSEO PostToolUse audit hook failed "
    "(non-blocking; audit event not recorded)"
)
_TARGET_CAP = 480


def _parse_payload(raw: str) -> dict:
    """Parse hook stdin → dict; empty / malformed / non-object → {} (never raises)."""
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def build_audit_fields(payload: dict) -> dict:
    """Compute ``audit_action`` + ``audit_target`` from a PostToolUse payload.

    Reproduces the legacy inline command verbatim:
      * audit_target — Bash redacts to ``<head> [REDACTED args]`` (head = first
        whitespace token, or ``<empty>``); other tools use file_path/path, or
        ``<no-target>``. Always prefixed ``<ToolName>:`` and capped at 480 chars.
      * audit_action — Edit→``modified``; Write→``modified`` if the path already
        exists else ``created``; anything else → normalize_audit_action(tool,
        command=…).
    """
    tool_name = payload.get("tool_name") or "unknown"
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command", "") or ""
    head = command.split()[0] if command.strip() else "<empty>"
    if tool_name == "Bash":
        target = f"{head} [REDACTED args]"
    else:
        target = tool_input.get("file_path") or tool_input.get("path") or "<no-target>"
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if tool_name == "Edit":
        action = "modified"
    elif tool_name == "Write":
        action = "modified" if (file_path and Path(file_path).exists()) else "created"
    else:
        action = normalize_audit_action(tool_name, command=command)
    return {
        "audit_action": action,
        "audit_target": f"{tool_name}:{target}"[:_TARGET_CAP],
    }


def main() -> int:
    """Emit one session-attributed audit event. Non-blocking: always returns 0."""
    try:
        raw = sys.stdin.read()
    except Exception:  # cannot read stdin → never break the tool chain
        return 0
    payload = _parse_payload(raw)
    if not payload.get("tool_name"):
        return 0  # empty / garbage / non-tool payload — clean no-op
    try:
        workspace_root = resolve_workspace_root()
        if workspace_root is None:
            return 0  # nothing to attribute to (legacy "no workspace" no-op)
        project_id = resolve_session_project(
            workspace_root,
            session_id=current_session_id(payload),
            strict=False,
        )
        if not project_id:
            return 0  # unbound + no active.json fallback (legacy "no pid" no-op)
        fields = build_audit_fields(payload)
        append_audit(
            project_id=project_id,
            audit_action=fields["audit_action"],
            audit_target=fields["audit_target"],
            actor=_ACTOR,
            workspace_root=workspace_root,
        )
    except Exception:  # mirror the legacy `|| { echo 'WARNING …'; true; }`
        print(_WARNING, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
