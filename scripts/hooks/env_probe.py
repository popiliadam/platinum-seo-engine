#!/usr/bin/env python3
"""env_probe.py — AMO batch 0a cross-environment hook diagnostic probe.

TEMPORARY diagnostic instrumentation. Wired ADDITIVELY into SessionStart /
UserPromptSubmit / PreToolUse / PostToolUse / Stop, it appends ONE JSON line per
fire describing the SAFE shape of the hook stdin payload (KEYS only) plus a few
env-var presence flags. The operator runs it across VSCode / Mac-app / CLI and
the manager analyses the log via ``env_probe_report.py`` — see that file's
RUNBOOK and the batch-0a report for how to collect data and how to remove this.

Why it exists: the AMO initiative binds one Claude session to one SEO project via
a per-session marker file keyed by the ``session_id`` the harness passes to hooks
on stdin (env vars are unsettable per-session in the Mac app). Before writing
that binding we must EMPIRICALLY confirm a stable ``session_id`` reaches hooks in
every environment and which env vars are present. This probe gathers that
evidence; it draws NO conclusions.

SAFETY (non-negotiable):
  * NEVER record message/prompt/tool_input/tool_response VALUES — they can carry
    secrets or content. Only KEYS (structure) are captured.
  * NEVER block the hook chain: the whole of ``main()`` is wrapped so it ALWAYS
    exits 0, even on empty/malformed stdin or an unwritable log.
  * Does NOT read or require ``PSEO_WORKSPACE_ROOT`` (that may be exactly what is
    missing in a given environment).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

# Non-secret env vars whose PRESENCE answers the AMO binding question.
_ENV_PRESENCE = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_ENV_FILE",
    "CLAUDECODE",
    "PSEO_WORKSPACE_ROOT",
)
# Subset whose VALUES are safe to record (non-secret filesystem paths).
_ENV_VALUES = ("CLAUDE_PLUGIN_ROOT", "CLAUDE_ENV_FILE")

_DEFAULT_LOG = "~/.config/pseo/hook-probe.jsonl"
_MAX_ID_VALUE_LEN = 120


def extract_probe_record(
    payload: dict, environ: dict, cwd: str, now_iso: str
) -> dict:
    """Build the SAFE probe record (pure: no I/O, no mutation of inputs).

    Captures structure (sorted stdin keys) and the session-identifying
    candidates, but NEVER the VALUES of content/secret-bearing keys. Short
    scalar id-like values (other than ``session_id``) are kept by key as
    secondary binding candidates.
    """
    other_id_keys = {
        key: value
        for key, value in payload.items()
        if "id" in key.lower()
        and key != "session_id"
        and isinstance(value, (str, int))
        and not isinstance(value, bool)
        and len(str(value)) <= _MAX_ID_VALUE_LEN
    }
    return {
        "ts": now_iso,
        "hook_event_name": payload.get("hook_event_name"),
        "stdin_keys": sorted(payload.keys()),
        "session_id": payload.get("session_id"),
        "transcript_path": payload.get("transcript_path"),
        "cwd_payload": payload.get("cwd"),
        "cwd_os": cwd,
        "other_id_keys": other_id_keys,
        "env_present": {name: (name in environ) for name in _ENV_PRESENCE},
        "env_values": {name: environ.get(name) for name in _ENV_VALUES},
    }


def _resolve_log_path() -> str:
    return os.environ.get("PSEO_PROBE_LOG") or os.path.expanduser(_DEFAULT_LOG)


def _parse_stdin(raw: str) -> tuple[dict, bool]:
    """Return ``(payload, parse_error)``. Empty / malformed / non-dict -> ({}, True)."""
    try:
        parsed = json.loads(raw)
    except Exception:
        return ({}, True)
    if isinstance(parsed, dict):
        return (parsed, False)
    return ({}, True)


def main() -> int:
    try:
        payload, parse_error = _parse_stdin(sys.stdin.read())
        record = extract_probe_record(
            payload, os.environ, os.getcwd(), datetime.now().isoformat()
        )
        if parse_error:
            record = {**record, "_stdin_parse_error": True}
        log_path = _resolve_log_path()
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
            handle.flush()
    except Exception:  # diagnostic probe must NEVER break the hook chain
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
