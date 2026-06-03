"""tests/hooks/test_hook_command_references_exist.py — P1-05 lock.

The session-start and user-prompt-submit hooks told users to run
``/pseo-bootstrap-project`` to scaffold a project pack — but no such command
exists (``commands/pseo-bootstrap-project.md`` is absent). The real scaffolder
is ``/pseo-init``. A user following the hint hits a dead end on their first
interaction.

This test asserts every ``/pseo-<name>`` slash command referenced in a hook
message has a backing ``commands/pseo-<name>.md`` file.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "hooks"
COMMANDS = REPO / "commands"

_SLASH_CMD = re.compile(r"/pseo-[a-z0-9-]+")


def _hook_files() -> list[Path]:
    return sorted(p for p in HOOKS.glob("*.json") if p.is_file())


def test_hooks_present() -> None:
    assert _hook_files(), f"No hook json files under {HOOKS}"


def test_hook_messages_reference_slash_commands() -> None:
    """Anchor: at least one /pseo-* reference exists (no vacuous green)."""
    blob = "".join(p.read_text(encoding="utf-8") for p in _hook_files())
    assert _SLASH_CMD.findall(blob), "no /pseo-* slash command references in hooks"


def test_hook_slash_command_references_exist() -> None:
    """Every /pseo-<name> a hook references must have commands/pseo-<name>.md."""
    missing: dict[str, list[str]] = {}
    for path in _hook_files():
        text = path.read_text(encoding="utf-8")
        for tok in sorted(set(_SLASH_CMD.findall(text))):
            name = tok[1:]  # strip leading '/'
            if not (COMMANDS / f"{name}.md").is_file():
                missing.setdefault(path.name, []).append(tok)
    assert not missing, (
        "Hook messages reference slash commands with no commands/<name>.md "
        "(use an existing command, e.g. /pseo-init):\n"
        + "\n".join(f"  {name}: {toks}" for name, toks in sorted(missing.items()))
    )
