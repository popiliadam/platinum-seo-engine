"""G-01: consent is recorded only from the USER's own chat message.

A UserPromptSubmit hook sees the text the user typed. When it is an approval —
``/platinum-seo-engine:pseo-approve <run_id> <action> <target>`` or
``onay: <action> <target>`` — the hook writes the consent entry itself for this
session's bound project. The model never runs the writer (the gate denies it).
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from scripts.hooks import consent_from_prompt as hook
from scripts.state import consent_ledger as cl
from scripts.state import session_binding as sb

SID = "aaaaaaaa-2222-3333-4444-555555555555"


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "ws"
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(root))
    (root / "projects" / "demo" / "_state").mkdir(parents=True)
    (root / "projects" / "other" / "_state").mkdir(parents=True)
    (root / "shared" / "active.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "shared" / "active.json").write_text(json.dumps({"active_project": "other"}))
    sb.write_session_binding(SID, "demo", root, "2026-10-19T00:00:00")
    return root


def _submit(monkeypatch, prompt: str, session_id: str = SID) -> tuple[int, str]:
    payload = {"session_id": session_id, "prompt": prompt, "hook_event_name": "UserPromptSubmit"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    return hook.main(), out.getvalue()


def test_slash_approve_records_consent(ws, monkeypatch) -> None:
    rc, out = _submit(monkeypatch,
                      "/platinum-seo-engine:pseo-approve sess-aaaaaaaa git_push '--force origin main'")
    assert rc == 0
    entries = cl.read_entries(ws, "demo")
    assert [(e["action"], e["target_hash"], e["session_id"]) for e in entries] == [
        ("git_push", cl.target_hash("--force origin main"), SID)
    ]
    assert entries[0]["granted_by"] == "user-prompt"
    assert "demo" in out


def test_quoted_target_with_spaces_survives(ws, monkeypatch) -> None:
    _submit(monkeypatch, '/pseo-approve r1 fs_delete "/tmp/My Dir/x.json"')
    assert cl.read_entries(ws, "demo")[0]["target_hash"] == cl.target_hash("/tmp/My Dir/x.json")


def test_turkish_onay_form(ws, monkeypatch) -> None:
    _submit(monkeypatch, "onay: fs_delete projects/demo/master.xlsx")
    entry = cl.read_entries(ws, "demo")[0]
    assert entry["action"] == "fs_delete"
    assert entry["run_id"] == "sess-aaaaaaaa"


def test_ordinary_prompt_records_nothing(ws, monkeypatch) -> None:
    rc, out = _submit(monkeypatch, "git push --force origin main yapabilir misin? onay veriyorum")
    assert rc == 0 and out == ""
    assert cl.read_entries(ws, "demo") == []


def test_unbound_session_records_nothing_and_says_bind(ws, monkeypatch) -> None:
    rc, out = _submit(monkeypatch, "onay: git_push origin main", session_id="unbound")
    assert rc == 0
    assert cl.read_entries(ws, "other") == []  # never active.json's project
    assert "pseo-bind" in out


def test_unknown_action_is_reported_not_raised(ws, monkeypatch) -> None:
    rc, out = _submit(monkeypatch, "onay: launch_rockets moon")
    assert rc == 0
    assert "launch_rockets" in out
    assert cl.read_entries(ws, "demo") == []


def test_garbage_stdin_is_a_noop(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert hook.main() == 0
