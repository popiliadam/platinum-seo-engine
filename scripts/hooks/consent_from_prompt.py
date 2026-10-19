#!/usr/bin/env python3
"""consent_from_prompt.py — record consent ONLY from the user's own chat message (G-01).

UserPromptSubmit hook. The text it receives is what the USER typed, so it is the
one place a consent can come from without the model being able to write it (the
outward gate denies every model attempt to touch the consent ledger). When the
message is an approval, this hook appends the consent entry itself:

    /platinum-seo-engine:pseo-approve <run_id> <action> <target>
    /pseo-approve <run_id> <action> <target>
    onay: <action> <target>                 (run_id = sess-<first 8 of session id>)

Only the FIRST line counts, and only when the message starts with it — a quoted
approval inside a longer message, or an agent report pasted back, records nothing.
The consent goes to THIS session's bound project only (strict: never
shared/active.json, G-05). Whatever happens, the hook exits 0 and prints one line
(UserPromptSubmit stdout becomes context, so the model sees the outcome).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from scripts.state.consent_ledger import append_consent  # noqa: E402
from scripts.state.session_binding import (  # noqa: E402
    current_session_id,
    resolve_session_project,
    resolve_workspace_root,
)

_SLASH_RE = re.compile(r"/(?:platinum-seo-engine:)?pseo-approve\s+(?P<args>.+)")
_ONAY_RE = re.compile(r"onay\s*:\s*(?P<args>.+)", re.IGNORECASE)
_GRANTED_BY = "user-prompt"


def parse_approval(prompt: str, session_id: str) -> tuple[str, str, str] | None:
    """(run_id, action, target) when the message IS an approval, else None.

    Raises ValueError for an approval line whose arguments cannot be parsed.
    """
    stripped = prompt.lstrip()
    first_line = stripped.splitlines()[0] if stripped else ""
    slash = _SLASH_RE.fullmatch(first_line.strip())
    if slash:
        args = shlex.split(slash.group("args"))
        if len(args) < 3:
            raise ValueError("kullanım: /pseo-approve <run_id> <action> <target>")
        return args[0], args[1], " ".join(args[2:])
    onay = _ONAY_RE.fullmatch(first_line.strip())
    if onay:
        args = shlex.split(onay.group("args"))
        if len(args) < 2:
            raise ValueError("kullanım: onay: <action> <target>")
        return f"sess-{session_id[:8]}", args[0], " ".join(args[1:])
    return None


def _record(payload: dict) -> str | None:
    """The one-line outcome to print, or None when the message is not an approval."""
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return None
    session_id = current_session_id(payload) or ""
    try:
        parsed = parse_approval(prompt, session_id)
    except ValueError as exc:
        return f"[onay] KAYDEDİLMEDİ: {exc}"
    if parsed is None:
        return None
    run_id, action, target = parsed
    if not session_id:
        return "[onay] KAYDEDİLMEDİ: oturum kimliği yok."
    workspace = resolve_workspace_root()
    if workspace is None:
        return "[onay] KAYDEDİLMEDİ: workspace bulunamadı (/pseo-bind <slug> --workspace <yol>)."
    try:
        slug = resolve_session_project(workspace, session_id=session_id, strict=True)
    except FileNotFoundError:
        return "[onay] KAYDEDİLMEDİ: bu oturum bir projeye bağlı değil — önce /pseo-bind <slug>."
    try:
        entry = append_consent(
            workspace_root=workspace, project_slug=slug, run_id=run_id,
            action=action, target=target, granted_by=_GRANTED_BY,
            now_iso=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            session_id=session_id,
        )
    except ValueError as exc:
        return f"[onay] KAYDEDİLMEDİ: {exc}"
    return (
        f"[onay] kaydedildi: {action} → {target}  (proje {slug}, seq {entry['seq']}). "
        f"Eylem artık bu oturumda çalıştırılabilir."
    )


def main() -> int:
    """Never blocks the prompt: any failure prints a line (or nothing) and exits 0."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (OSError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        line = _record(payload)
    except Exception as exc:  # a ledger failure must not swallow the user's message
        line = f"[onay] KAYDEDİLMEDİ: {type(exc).__name__}: {exc}"
    if line:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
