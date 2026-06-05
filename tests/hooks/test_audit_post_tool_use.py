"""tests/hooks/test_audit_post_tool_use.py — AMO batch 0d audit bug H1 fix.

The PostToolUse audit emitter was an inline ``python3 -c`` command in
``hooks/post-tool-use.json`` that read the workspace-GLOBAL ``shared/active.json``
to decide which project to attribute an audit event to. With 3-5 parallel Claude
sessions (one per project — the AMO goal) every session's audit events were
stamped with whichever project active.json last named → silent cross-project
contamination of the append-only ``events.jsonl`` ledgers.

``scripts/hooks/audit_post_tool_use.py`` extracts that logic and attributes the
event to THIS session's bound project via the batch-0b/0c binding primitive
(session marker → ``shared/active.json`` fallback), preserving every other
behaviour byte-for-byte: the REDACTED audit_target, the audit_action mapping, and
the NON-BLOCKING contract (always exit 0).

Contract under test:
  1. session marker beats active.json (the H1 fix) — and the legacy emission
     fields (action / actor / workspace_root) are unchanged;
  2. an UNBOUND session falls back to active.json (single-project: no regression);
  3. Bash targets stay REDACTED (no command args, secret or otherwise, leak);
  4. empty / garbage stdin is non-blocking (exit 0, no event, no traceback);
  5. no workspace, or unbound + no active.json, is a clean no-op (no event, no raise).

Capture is via monkeypatched ``append_audit`` (no real ledger writes); HOME + env
are monkeypatched so the suite never touches the real ``~/.config`` or workspace.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

import scripts.hooks.audit_post_tool_use as mod


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def capture(monkeypatch):
    """Record every append_audit kwargs dict; no real ledger I/O."""
    calls: list[dict] = []

    def _fake_append_audit(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(mod, "append_audit", _fake_append_audit)
    return calls


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    return ws


def _write_marker(ws: Path, session_id: str, slug: str) -> None:
    d = ws / "shared" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{session_id}.json").write_text(
        json.dumps({"active_project": slug, "session_id": session_id}),
        encoding="utf-8",
    )


def _write_active(ws: Path, slug: str) -> None:
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": slug}), encoding="utf-8"
    )


def _run_main(monkeypatch, payload_text: str, *, home: Path, workspace) -> int:
    """Drive main() with controlled stdin + an isolated HOME/env."""
    monkeypatch.setenv("HOME", str(home))  # ~/.config/pseo never the real one
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    if workspace is None:
        monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    else:
        monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    return mod.main()


# ---------------------------------------------------------------------------
# 1. The H1 fix: session marker wins over active.json
# ---------------------------------------------------------------------------

def test_session_marker_attribution_beats_active_json(tmp_path, monkeypatch, capture):
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    _write_marker(ws, "S", "alpha")
    _write_active(ws, "beta")  # global says beta — must be ignored for session S
    payload = {
        "session_id": "S",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "f.md")},
    }
    rc = _run_main(monkeypatch, json.dumps(payload), home=home, workspace=ws)
    assert rc == 0
    assert len(capture) == 1
    call = capture[0]
    assert call["project_id"] == "alpha"  # NOT "beta" — the H1 fix
    assert call["audit_action"] == "modified"  # Edit → modified (parity)
    assert call["actor"] == "claude-code:hook:PostToolUse"  # actor parity
    assert Path(call["workspace_root"]) == ws  # ws passed through


# ---------------------------------------------------------------------------
# 2. Unbound session → active.json fallback (single-project: no regression)
# ---------------------------------------------------------------------------

def test_unbound_session_falls_back_to_active_json(tmp_path, monkeypatch, capture):
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    _write_active(ws, "beta")  # no session marker on disk
    payload = {
        "session_id": "S",  # present, but unbound (no marker)
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "f.md")},
    }
    rc = _run_main(monkeypatch, json.dumps(payload), home=home, workspace=ws)
    assert rc == 0
    assert len(capture) == 1
    assert capture[0]["project_id"] == "beta"  # today's behaviour preserved


# ---------------------------------------------------------------------------
# 3. Bash redaction parity (no command args leak)
# ---------------------------------------------------------------------------

def test_bash_target_is_redacted(tmp_path, monkeypatch, capture):
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    _write_marker(ws, "S", "alpha")
    secret = "ghp_" + "z" * 36  # synthetic GitHub-PAT-shaped arg
    payload = {
        "session_id": "S",
        "tool_name": "Bash",
        "tool_input": {"command": f"git push --token {secret}"},
    }
    rc = _run_main(monkeypatch, json.dumps(payload), home=home, workspace=ws)
    assert rc == 0
    assert len(capture) == 1
    target = capture[0]["audit_target"]
    assert secret not in target  # the secret arg is gone
    assert "push" not in target  # ALL args dropped, not just the secret
    assert target == "Bash:git [REDACTED args]"  # head preserved + redaction marker


def test_bash_audit_action_classified(tmp_path, monkeypatch, capture):
    """Bash action still flows through normalize_audit_action (rm → deleted)."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    _write_marker(ws, "S", "alpha")
    payload = {
        "session_id": "S",
        "tool_name": "Bash",
        "tool_input": {"command": "rm secret-notes.txt"},
    }
    _run_main(monkeypatch, json.dumps(payload), home=home, workspace=ws)
    assert capture[0]["audit_action"] == "deleted"
    assert "secret-notes.txt" not in capture[0]["audit_target"]


def test_write_existing_modified_new_created(tmp_path, monkeypatch, capture):
    """Write action parity: existing path → modified, missing path → created."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    _write_marker(ws, "S", "alpha")
    existing = tmp_path / "exists.md"
    existing.write_text("x", encoding="utf-8")
    missing = tmp_path / "missing.md"
    _run_main(
        monkeypatch,
        json.dumps({"session_id": "S", "tool_name": "Write", "tool_input": {"file_path": str(existing)}}),
        home=home,
        workspace=ws,
    )
    _run_main(
        monkeypatch,
        json.dumps({"session_id": "S", "tool_name": "Write", "tool_input": {"file_path": str(missing)}}),
        home=home,
        workspace=ws,
    )
    assert [c["audit_action"] for c in capture] == ["modified", "created"]


# ---------------------------------------------------------------------------
# 4. Empty / garbage stdin is non-blocking
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["", "   ", "not json {{{", "[1, 2, 3]", "null"])
def test_empty_or_garbage_stdin_is_nonblocking(tmp_path, monkeypatch, capture, raw):
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    _write_marker(ws, "S", "alpha")  # binding exists, but the payload is unusable
    _write_active(ws, "beta")
    rc = _run_main(monkeypatch, raw, home=home, workspace=ws)
    assert rc == 0  # never breaks the tool chain
    assert capture == []  # nothing attributed for a non-tool payload


# ---------------------------------------------------------------------------
# 5. No workspace / unbound + no active.json → clean no-op
# ---------------------------------------------------------------------------

def test_no_workspace_is_noop(tmp_path, monkeypatch, capture):
    home = tmp_path / "home"
    home.mkdir()  # empty: no ~/.config/pseo/config.json
    payload = {"session_id": "S", "tool_name": "Edit", "tool_input": {"file_path": "/x.md"}}
    rc = _run_main(monkeypatch, json.dumps(payload), home=home, workspace=None)
    assert rc == 0
    assert capture == []


def test_unbound_and_no_active_json_is_noop(tmp_path, monkeypatch, capture):
    ws = _workspace(tmp_path)  # ws exists, but no marker AND no active.json
    home = tmp_path / "home"
    home.mkdir()
    payload = {"session_id": "S", "tool_name": "Edit", "tool_input": {"file_path": "/x.md"}}
    rc = _run_main(monkeypatch, json.dumps(payload), home=home, workspace=ws)
    assert rc == 0
    assert capture == []
