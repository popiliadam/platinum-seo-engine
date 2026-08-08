"""tests/hooks/test_check_events_writer.py — PreToolUse events.jsonl writer guard.

TDD lock for scripts/hooks/check_events_writer.py.

Why it exists: between 2026-07-09 and 2026-08-06, agent sessions appended 93 rows
straight into projects/*/_state/events.jsonl instead of calling
scripts/state/events_writer.py — which validates against events.schema.json
BEFORE appending and would have rejected every one of them. Nothing in the
pre-commit layer could see it (the ledger is gitignored operator data), and the
compliance test skips when no workspace is bound, so the drift sat unseen for a
month. This guard closes the write boundary itself.

Shape mirrors outward_action_gate:

  * classify() — PURE (no IO): (tool_name, tool_input) -> the ledger path the
    call would WRITE, else None. CONSERVATIVE in the direction that matters
    here: READING the ledger must never be blocked, because diagnosis, reporting
    and the migration all read it constantly.
  * evaluate() — (0, []) allow / (2, messages) deny, message naming the writer.
  * main() — stdin JSON payload, exit 2 on deny.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks import check_events_writer as guard

_REPO = Path(__file__).resolve().parents[2]
_GUARD = _REPO / "scripts" / "hooks" / "check_events_writer.py"

LEDGER = "/ws/projects/vento/_state/events.jsonl"


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ===========================================================================
# classify() — writes are caught
# ===========================================================================

def test_write_tool_targeting_the_ledger_is_caught():
    assert guard.classify("Write", {"file_path": LEDGER}) == LEDGER


def test_edit_tool_targeting_the_ledger_is_caught():
    assert guard.classify("Edit", {"file_path": LEDGER}) == LEDGER


def test_bash_append_redirect_is_caught():
    assert guard.classify(*_bash(f"echo '{{}}' >> {LEDGER}").values()) == LEDGER


def test_bash_overwrite_redirect_is_caught():
    assert guard.classify(*_bash(f"printf '' > {LEDGER}").values()) == LEDGER


def test_bash_redirect_to_a_quoted_path_is_caught():
    assert guard.classify(*_bash(f'echo x >> "{LEDGER}"').values()) == LEDGER


def test_bash_tee_into_the_ledger_is_caught():
    assert guard.classify(*_bash(f"echo x | tee -a {LEDGER}").values()) == LEDGER


def test_bash_in_place_edit_is_caught():
    assert guard.classify(*_bash(f"sed -i '' 's/a/b/' {LEDGER}").values()) == LEDGER


def test_bash_copy_ONTO_the_ledger_is_caught():
    assert guard.classify(*_bash(f"cp /tmp/rows.jsonl {LEDGER}").values()) == LEDGER


def test_a_write_in_a_later_segment_is_caught():
    """`cd x && echo … >> ledger` — the write is not the leading token."""
    cmd = f"cd /ws && echo '{{}}' >> {LEDGER}"
    assert guard.classify(*_bash(cmd).values()) == LEDGER


# ===========================================================================
# classify() — reads and legitimate writers are NOT caught
#
# This half matters more than the half above: a guard that blocks reading the
# ledger would brick diagnosis, monthly reporting and the migration itself.
# ===========================================================================

@pytest.mark.parametrize("command", [
    f"cat {LEDGER}",
    f"grep work_completed {LEDGER}",
    f"wc -l < {LEDGER}",
    f"tail -5 {LEDGER}",
    f"python3 -c \"print(open('{LEDGER}').read())\"",
    f"jq -r .event_kind {LEDGER}",
])
def test_reading_the_ledger_is_allowed(command):
    assert guard.classify(*_bash(command).values()) is None


def test_copying_the_ledger_AWAY_is_allowed():
    """The ledger is the SOURCE here — a backup, not a write."""
    assert guard.classify(*_bash(f"cp {LEDGER} /tmp/backup.jsonl").values()) is None


def test_the_sanctioned_migration_is_allowed():
    cmd = ("python3 scripts/state/migrate_legacy_events.py "
           "--workspace /ws --project vento")
    assert guard.classify(*_bash(cmd).values()) is None


def test_the_sanctioned_writer_is_allowed():
    cmd = ("python3 -c \"from scripts.state import events_writer; "
           "events_writer.append_work(project_id='vento', event_type='tech_fix', "
           "task_id='T-01621')\"")
    assert guard.classify(*_bash(cmd).values()) is None


@pytest.mark.parametrize("path", [
    "/ws/projects/vento/_state/events.jsonl.legacy",
    "/ws/projects/vento/_state/events.jsonl.bak",
])
def test_the_archives_are_not_the_live_ledger(path):
    """.legacy and .bak are the migration's own outputs, not the strict ledger."""
    assert guard.classify("Write", {"file_path": path}) is None
    assert guard.classify(*_bash(f"echo x >> {path}").values()) is None


def test_a_jsonl_outside_state_is_not_the_ledger():
    """Only _state/events.jsonl is the ledger; a same-named file elsewhere isn't."""
    assert guard.classify("Write", {"file_path": "/tmp/events.jsonl"}) is None


def test_an_unrelated_file_is_allowed():
    assert guard.classify("Write", {"file_path": "/ws/projects/vento/master.xlsx"}) is None


def test_a_non_writing_tool_is_allowed():
    assert guard.classify("Read", {"file_path": LEDGER}) is None


# ===========================================================================
# evaluate() — decision + remediation
# ===========================================================================

def test_a_caught_write_is_denied():
    code, messages = guard.evaluate({"tool_name": "Write", "tool_input": {"file_path": LEDGER}})
    assert code == 2
    assert messages


def test_the_denial_names_the_writer_to_use_instead():
    """A block that doesn't say what to do instead just gets worked around."""
    _code, messages = guard.evaluate({"tool_name": "Write", "tool_input": {"file_path": LEDGER}})
    assert any("events_writer" in m for m in messages)


def test_an_allowed_call_produces_no_message():
    assert guard.evaluate(_bash(f"cat {LEDGER}")) == (0, [])


def test_the_escape_hatch_allows_an_intentional_direct_write(monkeypatch):
    """Migration/recovery needs a documented way through — mirrors
    check_excel_writer's PSEO_EXCEL_WRITER signal."""
    monkeypatch.setenv("PSEO_EVENTS_WRITER", "events_writer.py")
    assert guard.evaluate({"tool_name": "Write", "tool_input": {"file_path": LEDGER}}) == (0, [])


def test_a_malformed_payload_never_bricks_the_tool():
    assert guard.evaluate("not-a-dict") == (0, [])
    assert guard.evaluate({}) == (0, [])


# ===========================================================================
# main() — the hook as the harness actually runs it
# ===========================================================================

def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_GUARD)],
        input=json.dumps(payload), text=True, capture_output=True, cwd=str(_REPO),
    )


def test_hook_exits_2_and_explains_on_a_direct_write():
    proc = _run({"tool_name": "Write", "tool_input": {"file_path": LEDGER}})
    assert proc.returncode == 2
    assert "events_writer" in proc.stderr


def test_hook_exits_0_on_a_read():
    proc = _run(_bash(f"cat {LEDGER}"))
    assert proc.returncode == 0
