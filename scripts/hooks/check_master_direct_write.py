#!/usr/bin/env python3
"""check_master_direct_write.py — PreToolUse guard: master.xlsx is written only by transaction.py.

Per rules/excel-discipline.md (§8.5) a project's ``master.xlsx`` MUST be written through
``scripts/excel/transaction.py`` (flock sentinel + load-inside-lock + atomic replace +
backup). Agent sessions nevertheless wrote it with ad-hoc openpyxl snippets (measured:
``projects/miningaa-com/_state/staging/textile_research/fix_f05.py``). Such a write takes
no lock, so a parallel transaction writer's sheet is silently reverted from a stale
in-memory workbook.

Why a TOOL-boundary guard: ``check_excel_writer.py`` runs at commit time and master.xlsx is
gitignored operator data, so it never sees these writes.

Deny when a Bash command — or a ``python <file>.py`` script it runs — would WRITE a master
workbook:
  * ``.save('<…master….xlsx>')`` or ``to_excel('<…master….xlsx>')`` with a literal path, or
  * a master path literal + ``load_workbook(`` + ``.save(`` in the same code.
Deliberately allowed: reading (no save), ``python -m scripts.excel.transaction``, running
``scripts/excel/transaction.py`` itself, non-master workbooks, non-Bash tools.

Known limits (documented, not silently assumed): a path built dynamically without any
``master….xlsx`` literal, or a script run via ``-m <module>``, is not inspected.

Escape hatch (mirrors check_excel_writer's PSEO_EXCEL_WRITER): set
``PSEO_EXCEL_WRITER=transaction.py`` in the environment or as a command prefix for an
intentional migration/recovery write.

Exit codes:
    0  ALLOW
    2  DENY
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_ESCAPE_ENV = "PSEO_EXCEL_WRITER"
_ESCAPE_VALUE = "transaction.py"
_SAFE_WRITER = ("scripts", "excel", "transaction.py")
_MAX_SCRIPT_BYTES = 1_000_000

_MASTER = r"[^\"'\s]*master(?:-excel)?\.xlsx"
_MASTER_LITERAL_RE = re.compile(_MASTER, re.IGNORECASE)
_LITERAL_WRITE_RE = re.compile(
    r"(?:\.save|to_excel)\s*\(\s*[rRbBuUfF]{0,2}[\"'][^\"']*master(?:-excel)?\.xlsx",
    re.IGNORECASE,
)
_LOAD_RE = re.compile(r"\bload_workbook\s*\(")
_SAVE_RE = re.compile(r"\.save\s*\(")
_SCRIPT_RE = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?((?:\s+-[A-Za-z]+)*)\s+([\"']?)([^\s;&|<>\"']+\.py)\2"
)


def _code_writes_master(code: str) -> bool:
    if _LITERAL_WRITE_RE.search(code):
        return True
    return bool(_MASTER_LITERAL_RE.search(code) and _LOAD_RE.search(code) and _SAVE_RE.search(code))


def _is_safe_writer(path: Path) -> bool:
    return tuple(path.parts[-3:]) == _SAFE_WRITER


def _script_paths(command: str, cwd: str) -> list[Path]:
    paths = []
    for match in _SCRIPT_RE.finditer(command):
        flags = match.group(1).split()
        if any(flag in ("-m", "-c") for flag in flags):
            continue
        raw = Path(os.path.expanduser(match.group(3)))
        paths.append(raw if raw.is_absolute() else Path(cwd) / raw)
    return paths


def _script_writes_master(path: Path) -> bool:
    try:
        if _is_safe_writer(path.resolve()) or not path.is_file():
            return False
        if path.stat().st_size > _MAX_SCRIPT_BYTES:
            return False
        return _code_writes_master(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False


def classify(tool_name: str, tool_input: object, cwd: str | None = None) -> str | None:
    """Reason string when the call would write a master workbook outside transaction.py."""
    if tool_name != "Bash" or not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    if f"{_ESCAPE_ENV}={_ESCAPE_VALUE}" in command:
        return None
    if _code_writes_master(command):
        return "inline Python saves a master workbook"
    for script in _script_paths(command, cwd or os.getcwd()):
        if _script_writes_master(script):
            return f"script {script} saves a master workbook"
    return None


def evaluate(payload: dict) -> tuple[int, list[str]]:
    """Return ``(exit_code, messages)`` — 0 allows the tool, 2 denies it."""
    if not isinstance(payload, dict):
        return (0, [])
    if os.getenv(_ESCAPE_ENV, "").strip() == _ESCAPE_VALUE:
        return (0, [])
    reason = classify(payload.get("tool_name") or "", payload.get("tool_input"), payload.get("cwd"))
    if reason is None:
        return (0, [])
    return (2, [
        f"BLOCKED: master.xlsx'e transaction.py dışından yazım → {reason}",
        "Bu yazım excel.lock almaz; paralel bir transaction yazıcısının sheet'ini bayat kopyayla geri alır.",
        "Güvenli yol — scripts/excel/transaction.py:",
        "  from scripts.excel import transaction",
        "  transaction.append(wb_path, sheet, rows, project_slug)   # veya update()/replace()",
        "Bilerek migration/kurtarma yapıyorsan: PSEO_EXCEL_WRITER=transaction.py",
    ])


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0  # never brick a tool call on an unreadable payload
    try:
        code, messages = evaluate(payload)
    except Exception as exc:  # pragma: no cover — fail open on an internal bug
        print(f"WARN check_master_direct_write internal error, allowing: {exc!r}", file=sys.stderr)
        return 0
    for message in messages:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
