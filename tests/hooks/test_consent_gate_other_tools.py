"""G-06: other shell / file tools must reach the same gate as Bash / Write / Edit.

Desktop Commander (start_process, interact_with_process, write_file, edit_block,
move_file) and the terminal panel (run_in_terminal) ran commands and wrote
files without any hook seeing them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.hooks import outward_action_gate as gate

SID = "77777777-2222-3333-4444-555555555555"
ROOT = Path(__file__).resolve().parents[2]


def _eval(tool: str, tool_input: dict) -> int:
    return gate.evaluate({"tool_name": tool, "tool_input": tool_input, "session_id": SID})[0]


@pytest.mark.parametrize("tool, tool_input", [
    ("mcp__Desktop_Commander__start_process", {"command": "git push --force origin main", "timeout_ms": 1}),
    ("mcp__terminal__run_in_terminal", {"command": "rm -rf projects/demo/_state"}),
    ("mcp__Desktop_Commander__interact_with_process",
     {"pid": 1, "input": "import shutil; shutil.rmtree('projects/demo/_state')"}),
    ("mcp__Desktop_Commander__write_file",
     {"path": "/w/projects/demo/_state/consent.jsonl", "content": "{}"}),
    ("mcp__Desktop_Commander__edit_block",
     {"file_path": "/w/projects/demo/_state/consent.jsonl", "old_string": "a", "new_string": "b"}),
    ("mcp__Desktop_Commander__move_file",
     {"source": "/tmp/forged.jsonl", "destination": "/w/projects/demo/_state/consent.jsonl"}),
])
def test_other_tools_are_gated(tool: str, tool_input: dict) -> None:
    assert _eval(tool, tool_input) == 2


def test_free_command_through_other_tool_still_runs() -> None:
    assert _eval("mcp__Desktop_Commander__start_process",
                 {"command": "git push origin feat/x", "timeout_ms": 1}) == 0
    assert _eval("mcp__Desktop_Commander__start_process",
                 {"command": "python3 -i", "timeout_ms": 1}) == 0


def test_hook_matcher_covers_the_other_tools() -> None:
    spec = json.loads((ROOT / "hooks" / "pre-tool-use.json").read_text(encoding="utf-8"))
    matchers = [b["matcher"] for b in spec["hooks"]["PreToolUse"]
                if any("outward_action_gate.py" in h["command"] for h in b["hooks"])]
    import re
    for tool in ("mcp__Desktop_Commander__start_process", "mcp__terminal__run_in_terminal",
                 "mcp__Desktop_Commander__interact_with_process",
                 "mcp__Desktop_Commander__write_file", "mcp__Desktop_Commander__edit_block",
                 "mcp__Desktop_Commander__move_file"):
        assert any(re.fullmatch(m, tool) for m in matchers), tool
