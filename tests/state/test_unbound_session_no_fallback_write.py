"""G-05: an UNBOUND session must not write append-only rows into shared/active.json's project.

resolve_session_project fell back to the workspace-global active.json even with
strict=True, so a session that never ran /pseo-bind wrote its consent and audit
rows into whichever project another session last made active — irreversibly
(append-only). strict now means "arg or this session's marker only"; the audit
hook skips unbound sessions and stamps session_id on what it does write.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

import scripts.hooks.audit_post_tool_use as audit_hook
from scripts.state import consent_ledger as cl
from scripts.state import session_binding as sb


def _ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    ws = tmp_path / "ws"
    for slug in ("bound-proj", "global-proj"):
        (ws / "projects" / slug / "_state").mkdir(parents=True)
    (ws / "shared").mkdir(parents=True, exist_ok=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "global-proj"}), encoding="utf-8"
    )
    return ws


# --- resolver ----------------------------------------------------------------

def test_strict_does_not_fall_back_to_active_json(tmp_path, monkeypatch) -> None:
    ws = _ws(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError, match="pseo-bind"):
        sb.resolve_session_project(ws, session_id="unbound", strict=True)


def test_strict_uses_this_sessions_marker(tmp_path, monkeypatch) -> None:
    ws = _ws(tmp_path, monkeypatch)
    sb.write_session_binding("bound", "bound-proj", ws, "2026-10-19T00:00:00")
    assert sb.resolve_session_project(ws, session_id="bound", strict=True) == "bound-proj"


def test_non_strict_still_falls_back_for_read_only_callers(tmp_path, monkeypatch) -> None:
    ws = _ws(tmp_path, monkeypatch)
    assert sb.resolve_session_project(ws, session_id="unbound") == "global-proj"


# --- consent ledger approve --------------------------------------------------

def test_approve_in_unbound_session_writes_nothing(tmp_path, monkeypatch, capsys) -> None:
    ws = _ws(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "unbound")
    rc = cl.main(["approve", "r1", "git_push", "origin main", "--workspace", str(ws)])
    assert rc != 0
    assert cl.read_entries(ws, "global-proj") == []
    assert "pseo-bind" in capsys.readouterr().err


def test_approve_names_the_project_it_wrote_to(tmp_path, monkeypatch, capsys) -> None:
    ws = _ws(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bound")
    sb.write_session_binding("bound", "bound-proj", ws, "2026-10-19T00:00:00")
    rc = cl.main(["approve", "r1", "git_push", "origin main", "--workspace", str(ws)])
    assert rc == 0
    assert "bound-proj" in capsys.readouterr().out
    assert cl.read_entries(ws, "global-proj") == []


# --- audit hook --------------------------------------------------------------

def _run_audit(monkeypatch, ws: Path, session_id: str) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(audit_hook, "append_audit", lambda **kw: calls.append(kw))
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    payload = {"session_id": session_id, "tool_name": "Edit",
               "tool_input": {"file_path": str(ws / "x.md")}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert audit_hook.main() == 0
    return calls


def test_audit_hook_skips_unbound_session(tmp_path, monkeypatch) -> None:
    ws = _ws(tmp_path, monkeypatch)
    assert _run_audit(monkeypatch, ws, "unbound") == []


def test_audit_hook_stamps_session_id(tmp_path, monkeypatch) -> None:
    ws = _ws(tmp_path, monkeypatch)
    sb.write_session_binding("bound", "bound-proj", ws, "2026-10-19T00:00:00")
    calls = _run_audit(monkeypatch, ws, "bound")
    assert len(calls) == 1
    assert calls[0]["project_id"] == "bound-proj"
    assert calls[0]["session_id"] == "bound"


def test_audit_event_with_session_id_is_schema_valid(tmp_path, monkeypatch) -> None:
    from scripts.state import events_writer

    ws = _ws(tmp_path, monkeypatch)
    events_writer.append_audit(
        project_id="bound-proj", audit_action="modified", audit_target="Edit:x",
        actor="claude-code:hook:PostToolUse", workspace_root=ws, session_id="bound",
    )
    line = (ws / "projects" / "bound-proj" / "_state" / "events.jsonl").read_text().strip()
    assert json.loads(line)["session_id"] == "bound"
