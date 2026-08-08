#!/usr/bin/env python3
"""check_events_writer.py — PreToolUse guard: events.jsonl writer policy.

Per rules/append-only-state.md + ADR-031, rows in
``projects/{slug}/_state/events.jsonl`` MUST be appended by
``scripts/state/events_writer.py``, which validates against
``schemas/events.schema.json`` BEFORE it writes and raises
``EventValidationError`` instead of persisting a non-conforming row.

Why this guard exists at the TOOL boundary rather than at commit time: the
ledger is gitignored operator data, so the pre-commit guards
(``check_append_only.sh``, ``check_excel_writer.py``) never see it — and
appending a malformed row is a perfectly legal *append*, which is all
``check_append_only.sh`` looks for. Between 2026-07-09 and 2026-08-06, 93 rows
written by hand across six projects went unnoticed for a month for exactly
these two reasons.

Deliberately asymmetric: only WRITES are caught. Reading the ledger — diagnosis,
monthly reporting, the migration's own classify pass — must never be blocked, so
a read is allowed even when it names the ledger.

Escape hatch (mirrors ``check_excel_writer.py``'s ``PSEO_EXCEL_WRITER``):
set ``PSEO_EVENTS_WRITER=events_writer.py`` for an intentional
migration/recovery write.

Exit codes:
    0  ALLOW — not a direct ledger write, or the escape hatch is set
    2  DENY  — a direct write to a live events.jsonl ledger
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import PurePath

_LEDGER_NAME = "events.jsonl"
_STATE_DIR = "_state"

_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

# Shell separators — a write is caught even when it is not the leading token
# of the whole command (`cd x && echo … >> ledger`).
_SEGMENT_SEP_RE = re.compile(r"&&|\|\||;|\n|\|")

# `>`/`>>` followed by a (optionally quoted) target. `<` is deliberately absent:
# `wc -l < ledger` reads. `2>&1` captures `&1`, which is not a ledger path.
_REDIRECT_RE = re.compile(r">>?\s*(\"[^\"]+\"|'[^']+'|[^\s;|&<>]+)")

# Commands that write to an operand rather than to a redirect.
_ANY_OPERAND_WRITERS = frozenset({"tee", "truncate"})
_LAST_OPERAND_WRITERS = frozenset({"cp", "mv", "install"})


def _is_ledger(raw: str) -> bool:
    """True only for a live ``_state/events.jsonl``.

    ``events.jsonl.legacy`` and ``events.jsonl.bak`` are the migration's own
    outputs and do not end in ``events.jsonl``, so they fall out naturally.
    """
    if not isinstance(raw, str) or not raw.strip():
        return False
    p = PurePath(os.path.expanduser(raw.strip().strip("\"'")))
    return p.name == _LEDGER_NAME and p.parent.name == _STATE_DIR


def _operands(tokens: list[str]) -> list[str]:
    """Non-flag tokens after the leading command word."""
    return [t for t in tokens[1:] if not t.startswith("-")]


def _classify_segment(segment: str) -> str | None:
    for match in _REDIRECT_RE.finditer(segment):
        target = match.group(1)
        if _is_ledger(target):
            return _clean(target)

    tokens = segment.split()
    if not tokens:
        return None
    bare = tokens[0].rsplit("/", 1)[-1]
    operands = _operands(tokens)

    if bare in _ANY_OPERAND_WRITERS or (bare == "sed" and any(t.startswith("-i") for t in tokens[1:])):
        for operand in operands:
            if _is_ledger(operand):
                return _clean(operand)
        return None

    # For cp/mv the ledger is only written when it is the DESTINATION; naming it
    # first is a backup, which must stay allowed.
    if bare in _LAST_OPERAND_WRITERS and operands and _is_ledger(operands[-1]):
        return _clean(operands[-1])

    return None


def _clean(raw: str) -> str:
    return os.path.expanduser(raw.strip().strip("\"'"))


def classify(tool_name: str, tool_input: dict) -> str | None:
    """(tool_name, tool_input) -> the ledger path this call would WRITE, else None."""
    if not isinstance(tool_input, dict):
        return None

    if tool_name in _WRITE_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("path") or ""
        return _clean(target) if _is_ledger(target) else None

    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return None
        for segment in _SEGMENT_SEP_RE.split(command):
            hit = _classify_segment(segment)
            if hit is not None:
                return hit
    return None


def evaluate(payload: dict) -> tuple[int, list[str]]:
    """Return ``(exit_code, messages)`` — 0 allows the tool, 2 denies it."""
    if not isinstance(payload, dict):
        return (0, [])
    target = classify(payload.get("tool_name") or "", payload.get("tool_input"))
    if target is None:
        return (0, [])
    if os.getenv("PSEO_EVENTS_WRITER", "").strip() == "events_writer.py":
        return (0, [])
    return (2, [
        f"BLOCKED: events.jsonl'a doğrudan yazma → {target}",
        "Bu defter append-only ve şema-doğrulamalı. Satırı elle eklemek yerine "
        "scripts/state/events_writer.py kullan:",
        "  from scripts.state import events_writer",
        "  events_writer.append_work(project_id=..., event_type=..., task_id=...)",
        "events_writer append'ten ÖNCE events.schema.json'a karşı doğrular; elle "
        "yazılan satır bu kontrolü atlar (2026-07 drift'i böyle oluştu).",
        "Bilerek migration/kurtarma yapıyorsan: PSEO_EVENTS_WRITER=events_writer.py",
    ])


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0  # never brick a tool call on an unreadable payload
    code, messages = evaluate(payload)
    for message in messages:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
