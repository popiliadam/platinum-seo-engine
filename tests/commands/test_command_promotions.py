"""tests/commands/test_command_promotions.py — STUB note YASAK invariant.

Slash commands under ``commands/`` MUST NOT contain "STUB" notes after
Wave 3 promotion (v1.1.0).  Skills referenced by these commands are now
active (Phase 5+ written, Phase 9+ written), so any
"(Phase X STUB)" title suffix, "STUB davranış" body section, or stray
``stub`` parenthetical is stale narrative drift.

Canonical pattern: command body invokes the skill directly via
``${CLAUDE_PLUGIN_ROOT}/skills/.../SKILL.md`` reference plus runtime
guards (PSEO_WORKSPACE_ROOT env, active.json read, --dry-run).

Forbidden patterns (regex per line, case-insensitive):
  - ``\\bSTUB\\b`` / ``\\bstub\\b`` — any standalone marker.

Exempt:
  - This test file (the patterns are inside the regex strings).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMMANDS = REPO / "commands"

FORBIDDEN_PATTERN = re.compile(r"\bstub\b", re.IGNORECASE)
PHASE_STUB_TITLE = re.compile(r"\(Phase \s*\d+\s*STUB\)", re.IGNORECASE)


def _command_files() -> list[Path]:
    return sorted(p for p in COMMANDS.glob("*.md") if p.is_file())


def test_commands_directory_populated() -> None:
    """Sanity: commands directory exists and is non-empty."""
    files = _command_files()
    assert files, f"No command files under {COMMANDS}"


def test_commands_no_stub_marker() -> None:
    """No command file may contain a STUB / stub marker after v1.1.0 promotion."""
    hits: list[str] = []
    for path in _command_files():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_PATTERN.search(line):
                rel = path.relative_to(REPO)
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, (
        "Command STUB note detected — promote command body to production.\n"
        + "\n".join(hits[:20])
        + ("\n...(truncated)" if len(hits) > 20 else "")
    )


def test_commands_titles_no_phase_stub_suffix() -> None:
    """No command title (markdown H1) may carry a '(Phase X STUB)' suffix."""
    hits: list[str] = []
    for path in _command_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("# /") and PHASE_STUB_TITLE.search(line):
                rel = path.relative_to(REPO)
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, (
        "Command title contains '(Phase X STUB)' suffix — remove on promotion.\n"
        + "\n".join(hits)
    )
