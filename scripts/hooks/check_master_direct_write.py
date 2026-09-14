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
  * ``.save(<target>)`` / ``to_excel(<target>)`` where the target is a ``…master….xlsx``
    literal or a name bound to one (``MASTER = ".../master.xlsx"``,
    ``path = os.path.join(..., "master.xlsx")``); or
  * ``<wb>.save(<anything but an unrelated string literal>)`` where ``<wb>`` was loaded with
    ``load_workbook(<master literal or bound name>)`` without ``read_only=True``.
Deliberately allowed: reading (read-only load, or no save of the loaded object), saving an
UNRELATED workbook or to an unrelated literal path, ``python -m scripts.excel.transaction``,
running this engine's own ``scripts/excel/transaction.py``, non-Bash tools.

Known limits (documented, not silently assumed): a path built with no ``master….xlsx``
literal anywhere, aliasing a loaded workbook to another name, or a script run via
``-m <module>`` is not inspected.

Escape hatch (mirrors check_excel_writer's PSEO_EXCEL_WRITER): ``PSEO_EXCEL_WRITER=transaction.py``
set in the hook environment, or as a real shell assignment (command prefix / ``export``) in the
command — a mention inside an echoed string does not count.

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
_SAFE_WRITER = (Path(__file__).resolve().parents[2] / "scripts" / "excel" / "transaction.py").resolve()
_MAX_SCRIPT_BYTES = 1_000_000

_MASTER_RE = re.compile(r"master(?:-excel)?\.xlsx", re.IGNORECASE)
_STR_LITERAL = r"[rRbBuUfF]{0,2}(?:\"[^\"\n]*\"|'[^'\n]*')"
# NAME = <rhs containing a master….xlsx literal on the same line>
_BOUND_NAME_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.*)$", re.MULTILINE)
# WB = [openpyxl.]load_workbook(ARGS)
_LOAD_ASSIGN_RE = re.compile(r"([A-Za-z_]\w*)\s*=\s*(?:[\w.]+\.)?load_workbook\s*\(([^)]*)\)")
# <obj>.save(ARG) / to_excel(ARG)
_SAVE_CALL_RE = re.compile(r"(?:([A-Za-z_]\w*)\s*\.\s*)?save\s*\(\s*([^,)]*)")
_TO_EXCEL_RE = re.compile(r"to_excel\s*\(\s*([^,)]*)")
_READ_ONLY_RE = re.compile(r"read_only\s*=\s*True")
_ESCAPE_ASSIGN_RE = re.compile(
    r"(?:^|[;&|\n(]\s*|\bexport\s+|\benv\s+)" + re.escape(f"{_ESCAPE_ENV}={_ESCAPE_VALUE}") + r"(?=\s|;|$)"
)
_SCRIPT_RE = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?((?:\s+-[A-Za-z]+)*)\s+([\"']?)([^\s;&|<>\"']+\.py)\2"
)


def _master_names(code: str) -> set[str]:
    return {name for name, rhs in _BOUND_NAME_RE.findall(code) if _MASTER_RE.search(rhs)}


def _refers_to_master(expr: str, names: set[str]) -> bool:
    expr = expr.strip()
    return bool(_MASTER_RE.search(expr)) or expr in names


def _is_unrelated_literal(expr: str) -> bool:
    expr = expr.strip()
    return bool(re.fullmatch(_STR_LITERAL, expr)) and not _MASTER_RE.search(expr)


def _code_writes_master(code: str) -> bool:
    if not _MASTER_RE.search(code):
        return False
    names = _master_names(code)
    for target in _TO_EXCEL_RE.findall(code):
        if _refers_to_master(target, names):
            return True
    loaded = {
        var for var, args in _LOAD_ASSIGN_RE.findall(code)
        if _refers_to_master(args.split(",")[0], names) and not _READ_ONLY_RE.search(args)
    }
    for obj, target in _SAVE_CALL_RE.findall(code):
        if _refers_to_master(target, names):
            return True
        if obj in loaded and not _is_unrelated_literal(target):
            return True
    return False


def _is_safe_writer(path: Path) -> bool:
    try:
        return path.resolve() == _SAFE_WRITER
    except OSError:
        return False


def _script_paths(command: str, cwd: str) -> list[Path]:
    paths = []
    for match in _SCRIPT_RE.finditer(command):
        if any(flag in ("-m", "-c") for flag in match.group(1).split()):
            continue
        raw = Path(os.path.expanduser(match.group(3)))
        paths.append(raw if raw.is_absolute() else Path(cwd) / raw)
    return paths


def _script_writes_master(path: Path) -> bool:
    try:
        if _is_safe_writer(path) or not path.is_file() or path.stat().st_size > _MAX_SCRIPT_BYTES:
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
    if _ESCAPE_ASSIGN_RE.search(command):
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
