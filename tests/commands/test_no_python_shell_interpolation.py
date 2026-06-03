"""tests/commands/test_no_python_shell_interpolation.py — P1-08 lock.

pseo-active.md and pseo-status.md built their inline ``python3 -c`` source by
interpolating a shell variable straight into a Python string literal
(``slug = '$SLUG'`` / ``slug = '$PROJECT'``). Because the heredoc is
shell-double-quoted, the shell expands ``$SLUG`` *into the Python source* before
Python runs: a slug containing a quote breaks the source, and a crafted slug
injects arbitrary Python.

The safe pattern (already used in these same blocks for the workspace root)
passes the value through the **environment** — ``os.environ['SLUG']`` — and
validates the slug against ``^[a-z0-9][a-z0-9-]*$`` before use.

Guard: no command's ``python3 -c`` block may contain the interpolation
signature ``'$`` (a single quote immediately followed by a shell ``$``).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMANDS = REPO / "commands"

_INLINE_BANG = re.compile(r"!`([^`]*)`")
_BASH_FENCE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)
_INJECT = re.compile(r"'\$")  # single quote directly followed by a shell '$var'


def _command_files() -> list[Path]:
    return sorted(p for p in COMMANDS.glob("*.md") if p.is_file())


def _python_c_blocks(text: str) -> list[str]:
    blocks = [m.group(1) for m in _INLINE_BANG.finditer(text)]
    blocks += [m.group(1) for m in _BASH_FENCE.finditer(text)]
    return [b for b in blocks if "python3 -c" in b]


def test_python_c_blocks_exist() -> None:
    """Anchor: there ARE python3 -c blocks to guard (no vacuous green)."""
    found = {
        p.name for p in _command_files() if _python_c_blocks(p.read_text(encoding="utf-8"))
    }
    assert {"pseo-active.md", "pseo-status.md"} <= found, found


def test_no_shell_var_interpolated_into_python_source() -> None:
    """No python3 -c block may interpolate a shell var into Python source."""
    offenders: dict[str, int] = {}
    for path in _command_files():
        for block in _python_c_blocks(path.read_text(encoding="utf-8")):
            hits = _INJECT.findall(block)
            if hits:
                offenders[path.name] = offenders.get(path.name, 0) + len(hits)
    assert not offenders, (
        "python3 -c blocks interpolate a shell var into Python source — pass it "
        "via os.environ + validate the slug instead. Offending files (count of "
        "'$ signatures):\n"
        + "\n".join(f"  {name}: {n}" for name, n in sorted(offenders.items()))
    )
