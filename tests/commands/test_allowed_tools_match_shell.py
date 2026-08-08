"""tests/commands/test_allowed_tools_match_shell.py — P0-05 lock.

Every shell program invoked in a slash-command body (inside ``!`...` `` inline
blocks or ```bash fenced blocks) MUST be declared in that command's
``allowed-tools`` frontmatter as ``Bash(<prog>:*)`` (or a bare ``Bash``
catch-all). Codex audit **P0-05** found 7 commands invoking programs
(``mkdir``, ``grep``, ``head``, ``sort``, ``curl``, ``tail``, ``xargs``,
``find``) absent from their frontmatter — at runtime Claude Code would prompt
for permission or refuse, breaking the command.

Tokenizer (mirrors the audit's allowed-tools-vs-usage analyzer):
  - Extract ``!`...` `` inline blocks and ```bash fenced blocks only — prose
    inline-code (single backticks, no leading ``!``) is documentation, not
    executed, so it is ignored.
  - Collect the first word of every ``$(...)`` command substitution; these are
    command-position even when nested inside double quotes
    (e.g. ``"${ENGINE:-$(find ...)}"``).
  - Blank quoted strings (jq filters, ``python3 -c`` source) so their internal
    tokens never count as programs. Double quotes are blanked before single
    quotes (a ``"..."`` body may legally contain ``'``).
  - Split the remainder on ``;`` / ``|`` / ``&`` / newline and take the first
    real word of each segment, dropping leading ``VAR=`` assignment prefixes
    (``PYTHONPATH=... python3`` -> ``python3``).
  - Keep only lowercase program-name tokens (``^[a-z][a-z0-9_-]*$``); this
    shape excludes shell builtins/keywords (also subtracted explicitly),
    ALL-CAPS env vars, slash-commands (``/pseo-x``), and jq/python internals
    (anything carrying ``.`` / ``(`` / ``$`` / ``/``).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMANDS = REPO / "commands"

# Shell builtins / keywords that are never external programs (brief §5 list,
# plus a few obvious siblings). Subtracted after the program-name filter.
BUILTINS = {
    "cd", "echo", "then", "else", "elif", "fi", "do", "done", "for", "if",
    "while", "until", "case", "esac", "in", "set", "exit", "true", "false",
    "read", "local", "export", "return", "test", "printf", "source", "eval",
    "shift", "unset", "trap", "wait", "function", "time",
    # Loop-control builtins — siblings of the `for`/`do`/`done` already listed.
    # Their absence flagged `break` inside a plugin-root resolver loop as an
    # undeclared external program (2026-08-08).
    "break", "continue",
}

_PROGRAM = re.compile(r"^[a-z][a-z0-9_-]*$")
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Keywords that introduce a command on the SAME segment (``then grep ...``);
# skip them like assignment prefixes so the real command word is reached.
_PREFIX_KW = {"then", "else", "elif", "do", "if", "while", "until"}
_INLINE_BANG = re.compile(r"!`([^`]*)`")              # !`...`  (body may span lines)
_BASH_FENCE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)
_CMDSUB = re.compile(r"\$\(\s*([A-Za-z_][A-Za-z0-9_-]*)")   # first word after $(
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_ALLOWED = re.compile(r"^allowed-tools:\s*(.+)$", re.MULTILINE)
_BASH_DECL = re.compile(r"Bash\(\s*([^():*]+?)\s*[:)]")
_BASH_CATCHALL = re.compile(r"\bBash\b(?!\()")


def _command_files() -> list[Path]:
    return sorted(p for p in COMMANDS.glob("*.md") if p.is_file())


def _shell_snippets(text: str) -> list[str]:
    """All executed-shell bodies: !`...` inline blocks + ```bash fences."""
    snippets = [m.group(1) for m in _INLINE_BANG.finditer(text)]
    snippets += [m.group(1) for m in _BASH_FENCE.finditer(text)]
    return snippets


def _blank_quotes(s: str) -> str:
    """Replace quoted-string bodies with spaces.

    Double quotes first: a ``"..."`` body may legally contain single quotes
    (Turkish text like ``marker'ı``); blanking it first prevents those stray
    ``'`` from mis-pairing. ``[^"]`` / ``[^']`` span newlines, so a multi-line
    ``python3 -c "..."`` heredoc collapses to a single space.
    """
    s = re.sub(r'"[^"]*"', " ", s)
    s = re.sub(r"'[^']*'", " ", s)
    return s


def _first_word(segment: str) -> str | None:
    """First command word of a pipeline segment, or None.

    Skips leading ``VAR=`` assignment prefixes (``PYTHONPATH=... python3``) and
    leading command-introducing keywords (``then grep ...``) so the actual
    program word is returned.
    """
    words = segment.split()
    idx = 0
    while idx < len(words) and (_ASSIGN.match(words[idx]) or words[idx] in _PREFIX_KW):
        idx += 1
    return words[idx] if idx < len(words) else None


def programs_used(text: str) -> set[str]:
    """Set of external shell programs invoked by a command body."""
    used: set[str] = set()
    for raw in _shell_snippets(text):
        # (1) command substitutions — caught even inside double quotes.
        for prog in _CMDSUB.findall(raw):
            if _PROGRAM.match(prog) and prog not in BUILTINS:
                used.add(prog)
        # (2) command-position first words.
        for segment in re.split(r"[;&|\n]+", _blank_quotes(raw)):
            word = _first_word(segment)
            if word and _PROGRAM.match(word) and word not in BUILTINS:
                used.add(word)
    return used


def declared_programs(text: str) -> tuple[set[str], bool]:
    """(declared Bash(<prog>) set, has-bare-Bash-catch-all) from frontmatter."""
    fm = _FRONTMATTER.search(text)
    if not fm:
        return set(), False
    m = _ALLOWED.search(fm.group(1))
    if not m:
        return set(), False
    value = m.group(1)
    catchall = bool(_BASH_CATCHALL.search(value))
    progs = {p.strip() for p in _BASH_DECL.findall(value)}
    return progs, catchall


def test_commands_directory_populated() -> None:
    assert _command_files(), f"No command files under {COMMANDS}"


def test_parser_detects_known_programs() -> None:
    """Anchor: the extractor must actually see real programs (no green-by-vacuity)."""
    used = programs_used((COMMANDS / "pseo-active.md").read_text(encoding="utf-8"))
    assert {"mkdir", "python3"} <= used, used


def test_all_used_shell_programs_are_declared() -> None:
    """Every shell program a command runs must be declared in allowed-tools."""
    violations: dict[str, list[str]] = {}
    for path in _command_files():
        text = path.read_text(encoding="utf-8")
        declared, catchall = declared_programs(text)
        if catchall:
            continue
        missing = sorted(programs_used(text) - declared)
        if missing:
            violations[path.name] = missing
    assert not violations, (
        "Command bodies invoke shell programs absent from their allowed-tools "
        "frontmatter (declare Bash(<prog>:*)):\n"
        + "\n".join(f"  {name}: {progs}" for name, progs in sorted(violations.items()))
    )
