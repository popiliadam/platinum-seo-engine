"""G-11 — small gaps in the events.jsonl / master.xlsx guards and the consent ledger.

(a) events.jsonl guard: ``cd _state && >> events.jsonl``, a ``$VAR/events.jsonl``
    path, ``dd of=`` and ``perl -i`` wrote the ledger unseen.
(b) the master-write guard's escape hatch could be switched on by the model
    itself as a command prefix, and both deny messages explained how.
(d) a READ of the consent ledger (the gate's check) created the project's _state dir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.hooks import check_events_writer as events_guard
from scripts.hooks import check_master_direct_write as master_guard
from scripts.state import consent_ledger as cl

MASTER = "/w/projects/demo/master.xlsx"


def _bash(cmd: str, cwd: str | None = None) -> dict:
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    if cwd:
        payload["cwd"] = cwd
    return payload


@pytest.mark.parametrize("cmd", [
    "cd projects/demo/_state && echo '{}' >> events.jsonl",
    "echo '{}' >> \"$STATE/events.jsonl\"",
    "dd if=row.json of=projects/demo/_state/events.jsonl conv=notrunc oflag=append",
    "perl -pi -e 's/a/b/' projects/demo/_state/events.jsonl",
])
def test_events_ledger_writes_are_caught(cmd: str) -> None:
    assert events_guard.evaluate(_bash(cmd))[0] == 2, cmd


def test_bare_events_jsonl_in_a_state_cwd_is_caught() -> None:
    payload = _bash("echo '{}' >> events.jsonl", cwd="/w/projects/demo/_state")
    assert events_guard.evaluate(payload)[0] == 2


@pytest.mark.parametrize("cmd", [
    "wc -l projects/demo/_state/events.jsonl",
    "cd projects/demo/_state && tail -5 events.jsonl",
    "echo '{}' >> /tmp/events.jsonl",
])
def test_events_reads_and_other_files_stay_allowed(cmd: str) -> None:
    assert events_guard.evaluate(_bash(cmd))[0] == 0, cmd


@pytest.mark.parametrize("cmd", [
    f"PSEO_EXCEL_WRITER=transaction.py python3 -c \"openpyxl.Workbook().save('{MASTER}')\"",
    f"export PSEO_EXCEL_WRITER=transaction.py; python3 -c \"openpyxl.Workbook().save('{MASTER}')\"",
])
def test_model_cannot_switch_on_the_master_escape_hatch(cmd: str, monkeypatch) -> None:
    monkeypatch.delenv("PSEO_EXCEL_WRITER", raising=False)
    assert master_guard.evaluate(_bash(cmd))[0] == 2


def test_deny_messages_do_not_explain_the_escape_hatch(monkeypatch) -> None:
    monkeypatch.delenv("PSEO_EXCEL_WRITER", raising=False)
    monkeypatch.delenv("PSEO_EVENTS_WRITER", raising=False)
    _, master_msgs = master_guard.evaluate(
        _bash(f"python3 -c \"openpyxl.Workbook().save('{MASTER}')\""))
    _, events_msgs = events_guard.evaluate(_bash("echo x >> projects/demo/_state/events.jsonl"))
    text = "\n".join(master_msgs + events_msgs)
    assert "PSEO_EXCEL_WRITER" not in text and "PSEO_EVENTS_WRITER" not in text


def test_reading_consent_does_not_create_project_dirs(tmp_path: Path) -> None:
    assert cl.read_entries(tmp_path, "ghost-proj") == []
    assert cl.has_session_consent(tmp_path, "ghost-proj", session_id="s",
                                  action="git_push", target_hash="0" * 64) is False
    assert not (tmp_path / "projects").exists()
