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

Inline Python is inspected too: a heredoc fed to python or a ``python -c``
program that opens the ledger for writing (``open(…, 'a'|'w'|'x'|'+')``,
``Path(…).open('a')``, ``write_text``/``write_bytes``, ``os.open`` with write
flags) — the path resolved through literals, names, f-strings, ``+``, ``/`` and
``os.path.join``. Not inspected: a ``python <file>.py`` script, ``-m`` modules,
or a path with no literal ``events.jsonl`` anywhere in the code.

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

import ast
import json
import os
import re
import shlex
import sys
import warnings
from itertools import islice, product
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


# ---------------------------------------------------------------------------
# Inline Python: a heredoc fed to python, or `python -c CODE`
#
# 2026-08-08..08-24: 31 off-schema rows reached live ledgers through
# `python3 - <<'PY' … open('<…>/_state/events.jsonl','a') … PY` and `-c` — a
# shape the redirect/tee/sed/cp checks above never look at. The code is parsed
# (ast) and a write-mode open / Path.open / write_text whose path resolves to a
# `_state/events.jsonl` is caught; reading the ledger stays allowed.
# ---------------------------------------------------------------------------

_UNKNOWN = "<?>"
_MAX_CANDIDATES = 16
_PY_WORD = r"python(?:3(?:\.\d+)?)?"
_PY_INVOKE_RE = re.compile(r"(?:^|[\s;&|(/])" + _PY_WORD + r"(?=\s|$)")
_PY_TOKEN_RE = re.compile(_PY_WORD)
_HEREDOC_RE = re.compile(r"(?<!<)<<(-?)(?!<)\s*(['\"]?)([A-Za-z_]\w*)\2")
_C_ARG_RE = re.compile(_PY_WORD + r"(?:\s+-[A-Za-z]+)*\s+-c\s+(\"(?:[^\"\\]|\\.)*\"|'[^']*')")

_OPEN_FUNCS = frozenset({"open", "io.open", "codecs.open", "builtins.open"})
_PATH_CTORS = frozenset({"Path", "PurePath", "PosixPath", "pathlib.Path",
                         "pathlib.PurePath", "pathlib.PosixPath", "os.path.join"})
_PATH_PASSTHROUGH = frozenset({"str", "os.fspath", "os.path.expanduser", "os.path.abspath",
                               "os.path.realpath", "os.path.normpath"})
_PATH_METHOD_PASSTHROUGH = frozenset({"resolve", "expanduser", "absolute"})
_PATH_WRITE_METHODS = frozenset({"write_text", "write_bytes"})
_OS_WRITE_FLAGS = frozenset({"O_WRONLY", "O_RDWR", "O_APPEND", "O_CREAT", "O_TRUNC"})


def _python_sources(command: str) -> list[str]:
    """Bodies of heredocs fed to python, plus every `python -c CODE` argument."""
    lines = command.split("\n")
    sources: list[str] = []
    shell_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        shell_lines.append(line)
        i += 1
        for match in _HEREDOC_RE.finditer(line):
            strip_tabs, delim = match.group(1) == "-", match.group(3)
            body: list[str] = []
            while i < len(lines):
                raw = lines[i]
                i += 1
                if (raw.lstrip("\t") if strip_tabs else raw).rstrip() == delim:
                    break
                body.append(raw)
            if _PY_INVOKE_RE.search(line):
                sources.append("\n".join(body))
    return sources + _c_arguments("\n".join(shell_lines))


def _c_arguments(shell_text: str) -> list[str]:
    lexer = shlex.shlex(shell_text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True  # `"CODE";` must not glue the `;` onto CODE
    try:
        tokens = list(lexer)
    except ValueError:
        return [_unquote(m.group(1)) for m in _C_ARG_RE.finditer(shell_text)]
    return [
        tokens[i + 1] for i, tok in enumerate(tokens[:-1])
        if tok == "-c" and any(_PY_TOKEN_RE.fullmatch(t.rsplit("/", 1)[-1])
                               for t in tokens[max(0, i - 4):i])
    ]


def _unquote(quoted: str) -> str:
    inner = quoted[1:-1]
    return re.sub(r'\\(["\\$`])', r"\1", inner) if quoted[0] == '"' else inner


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else ""
    return ""


def _bindings(tree: ast.AST) -> dict[str, list[ast.expr]]:
    """name -> every expression assigned to it (flow-insensitive on purpose)."""
    env: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        pairs: list[tuple[ast.expr, ast.expr]] = []
        if isinstance(node, ast.Assign):
            pairs = [(t, node.value) for t in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            pairs = [(node.target, node.value)]
        for target, value in pairs:
            if isinstance(target, ast.Name):
                env.setdefault(target.id, []).append(value)
            elif (isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)
                  and len(target.elts) == len(value.elts)):
                for t, v in zip(target.elts, value.elts):
                    if isinstance(t, ast.Name):
                        env.setdefault(t.id, []).append(v)
    return env


def _combine(parts: list[list[str]], sep: str) -> list[str]:
    return [sep.join(combo) for combo in islice(product(*parts), _MAX_CANDIDATES)]


class _PathResolver:
    """Every path string an expression may evaluate to; unknown parts → ``<?>``.

    Names resolve through ALL their assignments (flow-insensitive on purpose),
    each name once — a name met again while resolving itself is unknown.
    """

    def __init__(self, env: dict[str, list[ast.expr]]) -> None:
        self._env = env
        self._cache: dict[str, list[str]] = {}

    def paths(self, node: ast.AST) -> list[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.Name):
            return self._name(node.id)
        if isinstance(node, ast.FormattedValue):
            return self.paths(node.value)
        if isinstance(node, ast.JoinedStr):
            return _combine([self.paths(v) for v in node.values], "")
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
            sep = "/" if isinstance(node.op, ast.Div) else ""
            return _combine([self.paths(node.left), self.paths(node.right)], sep)
        if isinstance(node, ast.Call):
            return self._call(node)
        return [_UNKNOWN]

    def _name(self, name: str) -> list[str]:
        if name not in self._cache:
            self._cache[name] = [_UNKNOWN]  # cycle guard while resolving
            values = [s for e in self._env.get(name, []) for s in self.paths(e)]
            self._cache[name] = values[:_MAX_CANDIDATES] or [_UNKNOWN]
        return self._cache[name]

    def _call(self, node: ast.Call) -> list[str]:
        name = _dotted(node.func)
        if name in _PATH_CTORS and node.args:
            return _combine([self.paths(a) for a in node.args], "/")
        if name in _PATH_PASSTHROUGH and node.args:
            return self.paths(node.args[0])
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in _PATH_METHOD_PASSTHROUGH:
                return self.paths(node.func.value)
            if node.func.attr == "joinpath":
                return _combine([self.paths(a) for a in (node.func.value, *node.args)], "/")
        return [_UNKNOWN]


def _is_python_ledger(path: str) -> bool:
    """`_state/events.jsonl` — or `events.jsonl` under a directory we cannot resolve."""
    parts = path.replace("\\", "/").rstrip("/").split("/")
    if len(parts) < 2 or parts[-1] != _LEDGER_NAME:
        return False
    return parts[-2] in (_STATE_DIR, _UNKNOWN)


def _mode_writes(mode: ast.expr | None) -> bool:
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(ch in mode.value for ch in "awx+")
    return True  # a computed mode cannot be proven read-only


def _arg(node: ast.Call, index: int, keyword: str) -> ast.expr | None:
    if len(node.args) > index:
        return node.args[index]
    return next((kw.value for kw in node.keywords if kw.arg == keyword), None)


def _write_target(node: ast.Call) -> ast.expr | None:
    """The path a call opens for WRITING, else None."""
    name = _dotted(node.func)
    if name in _OPEN_FUNCS:
        return node.args[0] if node.args and _mode_writes(_arg(node, 1, "mode")) else None
    if name == "os.open":
        flags = {n.attr for n in ast.walk(node.args[1]) if isinstance(n, ast.Attribute)} \
            if len(node.args) > 1 else set()
        return node.args[0] if flags & _OS_WRITE_FLAGS else None
    if not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr in _PATH_WRITE_METHODS:
        return node.func.value
    if node.func.attr == "open" and _mode_writes(_arg(node, 0, "mode")):
        return node.func.value
    return None


_LEDGER_LITERAL_RE = re.compile(r"[^\s'\"]*_state/events\.jsonl(?![\w.])")
_PY_WRITE_RE = re.compile(
    r"""open\s*\([^)]*['"][rbt]*[awx+][rwabxt+]*['"]|\.write_(?:text|bytes)\s*\(|mode\s*=\s*['"][^'"]*[awx+]"""
)


def _python_ledger_write(code: str) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # hook stderr is not for SyntaxWarnings
            tree = ast.parse(code)
    except (SyntaxError, ValueError):
        literal = _LEDGER_LITERAL_RE.search(code)
        return literal.group(0) if literal and _PY_WRITE_RE.search(code) else None
    resolver = _PathResolver(_bindings(tree))
    for node in ast.walk(tree):
        target = _write_target(node) if isinstance(node, ast.Call) else None
        for path in resolver.paths(target) if target is not None else ():
            if _is_python_ledger(path):
                return path
    return None


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
        for source in _python_sources(command):
            hit = _python_ledger_write(source)
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
