"""Security-review follow-up to G-06: moving protected data away is a delete.

``move_file`` was judged only on its destination, and ``mv`` was not gated at
all, so ``master.xlsx`` / a ledger / ``_state`` could be moved out of the
project. A shell/file tool missing the field the gate reads now fails closed.
"""
from __future__ import annotations

import pytest

from scripts.hooks import outward_action_gate as gate

SID = "55555555-2222-3333-4444-555555555555"


def _eval(tool: str, tool_input: dict) -> int:
    return gate.evaluate({"tool_name": tool, "tool_input": tool_input, "session_id": SID})[0]


@pytest.mark.parametrize("tool, tool_input", [
    ("mcp__Desktop_Commander__move_file",
     {"source": "/w/projects/demo/master.xlsx", "destination": "/tmp/master.xlsx"}),
    ("Bash", {"command": "mv projects/demo/master.xlsx /tmp/"}),
    ("Bash", {"command": "mv projects/demo/_state /tmp/old-state"}),
    ("mcp__Desktop_Commander__start_process", {"timeout_ms": 1}),           # no command
    ("mcp__Desktop_Commander__write_file", {"content": "x"}),               # no path
])
def test_moving_protected_data_or_malformed_calls_need_consent(tool: str, tool_input: dict) -> None:
    assert _eval(tool, tool_input) == 2


@pytest.mark.parametrize("tool, tool_input", [
    ("mcp__Desktop_Commander__move_file",
     {"source": "/tmp/a.json", "destination": "/w/outputs/a.json"}),
    ("Bash", {"command": "mv notes.md docs/notes.md"}),
])
def test_ordinary_moves_stay_free(tool: str, tool_input: dict) -> None:
    assert _eval(tool, tool_input) == 0


@pytest.mark.parametrize("cmd", [
    "mv -t /tmp projects/demo/master.xlsx",
    "mv --target-directory=/tmp projects/demo/_state",
    "/bin/mv projects/demo/master.xlsx /tmp/",
    "command mv projects/demo/master.xlsx /tmp/",
])
def test_mv_target_directory_forms_are_caught(cmd: str) -> None:
    assert _eval("Bash", {"command": cmd}) == 2
