"""tests/state/test_consent_ledger.py — AMO batch 2a consent ledger recorder.

TDD lock for scripts/state/consent_ledger.py: the append-only, hash-chained
operator-consent recorder + verify_chain + has_consent + the `approve` CLI.
Every filesystem test uses tmp_path; CLI tests also monkeypatch HOME +
CLAUDE_CODE_SESSION_ID so nothing touches the real workspace/config.

The ledger mirrors events_writer's append discipline (O_APPEND + flock +
single os.write + fsync; read the tail UNDER the lock) — it is NEVER an
os.replace marker. See rules/append-only-state.md.

Authority: schemas/consent.schema.json (entry shape), batch 0b
  session_binding (CLI slug/workspace resolution).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.state import consent_ledger as cl
from scripts.state import session_binding as sb

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _REPO_ROOT / "schemas" / "consent.schema.json"


def _append(ws: Path, slug: str = "demo", *, run_id: str = "demo-furniture-2026-06-06-ab12",
            action: str = "index_update", target: str = "https://x/sitemap.xml",
            granted_by: str = "operator", now_iso: str = "2026-06-06T10:00:00",
            **kw) -> dict:
    return cl.append_consent(
        workspace_root=ws, project_slug=slug, run_id=run_id, action=action,
        target=target, granted_by=granted_by, now_iso=now_iso, **kw,
    )


# ---------------------------------------------------------------------------
# 6. append once -> read back, schema-valid, genesis fields, target_hash
# ---------------------------------------------------------------------------

def test_append_once_roundtrip(tmp_path: Path) -> None:
    entry = _append(tmp_path, target="https://x/sitemap.xml")
    entries = cl.read_entries(tmp_path, "demo")
    assert len(entries) == 1
    assert entries[0] == entry
    # the entry validates against the schema
    Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))).validate(entry)
    assert entry["seq"] == 0
    assert entry["prev_hash"] == cl.GENESIS_HASH
    expected = hashlib.sha256("https://x/sitemap.xml".encode("utf-8")).hexdigest()
    assert entry["target_hash"] == expected
    assert entry["target_hash"] == cl.target_hash("https://x/sitemap.xml")


# ---------------------------------------------------------------------------
# 7. three entries -> verify_chain True; prev_hash links; seq 0,1,2
# ---------------------------------------------------------------------------

def test_three_entries_chain(tmp_path: Path) -> None:
    _append(tmp_path, target="t0")
    _append(tmp_path, target="t1")
    _append(tmp_path, target="t2")
    entries = cl.read_entries(tmp_path, "demo")
    assert [e["seq"] for e in entries] == [0, 1, 2]
    assert cl.verify_chain(entries) == (True, None)
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert entries[2]["prev_hash"] == entries[1]["entry_hash"]


# ---------------------------------------------------------------------------
# 8. TAMPER: rewrite middle line's target_hash -> (False, 1) + has_consent False
# ---------------------------------------------------------------------------

def test_tamper_breaks_chain_and_consent(tmp_path: Path) -> None:
    _append(tmp_path, target="t0", run_id="r0", action="git_push")
    _append(tmp_path, target="t1", run_id="r1", action="net_post")
    _append(tmp_path, target="t2", run_id="r2", action="fs_delete")

    path = cl.consent_path(tmp_path, "demo")
    lines = path.read_text(encoding="utf-8").splitlines()
    forged = json.loads(lines[1])
    forged["target_hash"] = "f" * 64  # rewrite the middle entry's matchable key
    lines[1] = cl.canonical_json(forged)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    entries = cl.read_entries(tmp_path, "demo")
    assert cl.verify_chain(entries) == (False, 1)
    # tamper => no consent, even for the forged claim
    assert cl.has_consent(
        tmp_path, "demo", run_id="r1", action="net_post", target_hash="f" * 64
    ) is False


# ---------------------------------------------------------------------------
# 9. has_consent exact-match semantics on an intact chain
# ---------------------------------------------------------------------------

def test_has_consent_exact_match(tmp_path: Path) -> None:
    th = cl.target_hash("https://x/sitemap.xml")
    _append(tmp_path, target="https://x/sitemap.xml", run_id="r1", action="index_update")

    assert cl.has_consent(
        tmp_path, "demo", run_id="r1", action="index_update", target_hash=th
    ) is True
    # non-matching target_hash -> False
    assert cl.has_consent(
        tmp_path, "demo", run_id="r1", action="index_update", target_hash="0" * 64
    ) is False
    # same run_id+action but a DIFFERENT target_hash -> False
    other = cl.target_hash("https://y/other.xml")
    assert cl.has_consent(
        tmp_path, "demo", run_id="r1", action="index_update", target_hash=other
    ) is False
    # matching target_hash but wrong action -> False
    assert cl.has_consent(
        tmp_path, "demo", run_id="r1", action="git_push", target_hash=th
    ) is False


# ---------------------------------------------------------------------------
# 10. append rejects an action outside the enum -> ValueError, nothing written
# ---------------------------------------------------------------------------

def test_append_rejects_unknown_action(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _append(tmp_path, action="publish")
    assert cl.read_entries(tmp_path, "demo") == []


# ---------------------------------------------------------------------------
# 11. APPEND-ONLY proof: the first line's bytes are unchanged after a 2nd append
# ---------------------------------------------------------------------------

def test_append_only_first_line_immutable(tmp_path: Path) -> None:
    _append(tmp_path, target="t0")
    path = cl.consent_path(tmp_path, "demo")
    raw1 = path.read_bytes()
    _append(tmp_path, target="t1")
    raw2 = path.read_bytes()
    # the ENTIRE prior content is a prefix of the new file -> O_APPEND, not rewrite
    assert raw2.startswith(raw1)
    assert raw2.splitlines()[0] == raw1.splitlines()[0]


# ---------------------------------------------------------------------------
# 12. two sequential appends -> a valid 2-entry chain (lock + tail-read ordering)
# ---------------------------------------------------------------------------

def test_two_sequential_appends_valid_chain(tmp_path: Path) -> None:
    _append(tmp_path, target="t0")
    _append(tmp_path, target="t1")
    entries = cl.read_entries(tmp_path, "demo")
    assert len(entries) == 2
    assert cl.verify_chain(entries) == (True, None)


def test_verify_chain_empty_is_true(tmp_path: Path) -> None:
    assert cl.verify_chain([]) == (True, None)


def test_read_entries_missing_file_is_empty(tmp_path: Path) -> None:
    assert cl.read_entries(tmp_path, "demo") == []


def test_optional_fields_recorded(tmp_path: Path) -> None:
    entry = _append(tmp_path, session_id="sess-9", note="hello")
    assert entry["session_id"] == "sess-9"
    assert entry["note"] == "hello"
    # absent when not provided
    bare = _append(tmp_path, target="t-bare")
    assert "session_id" not in bare
    assert "note" not in bare


# ---------------------------------------------------------------------------
# CLI smoke — main(["approve", ...]) with a tmp workspace + a session marker
# ---------------------------------------------------------------------------

def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME at a tmp dir + clear PSEO_WORKSPACE_ROOT so the CLI never
    touches the real ~/.config or workspace. Returns the tmp workspace root."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    return tmp_path / "ws"


def test_cli_approve_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-1")
    (ws / "projects" / "demo" / "_state").mkdir(parents=True)
    sb.write_session_binding("sess-1", "demo", ws, "2026-06-06T00:00:00")

    rc = cl.main(["approve", "demo-furniture-2026-06-06-ab12", "git_push", "origin main",
                  "--workspace", str(ws)])
    assert rc == 0
    entries = cl.read_entries(ws, "demo")
    assert len(entries) == 1
    assert entries[0]["action"] == "git_push"
    assert entries[0]["session_id"] == "sess-1"
    assert cl.verify_chain(entries) == (True, None)


def test_cli_approve_bad_action_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-1")
    (ws / "projects" / "demo").mkdir(parents=True)
    sb.write_session_binding("sess-1", "demo", ws, "t")

    rc = cl.main(["approve", "r1", "bogus_action", "tgt", "--workspace", str(ws)])
    assert rc != 0
    assert cl.read_entries(ws, "demo") == []


def test_cli_approve_unbound_session_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-unbound")
    (ws / "projects").mkdir(parents=True)  # no marker, no active.json

    rc = cl.main(["approve", "r1", "git_push", "tgt", "--workspace", str(ws)])
    assert rc != 0


# ---------------------------------------------------------------------------
# has_session_consent (batch 2b) — keys on session_id, not run_id
# ---------------------------------------------------------------------------

def test_has_session_consent_matches_same_session(tmp_path: Path) -> None:
    th = cl.target_hash("origin main")
    _append(tmp_path, target="origin main", run_id="r1", action="git_push",
            session_id="sess-A")
    assert cl.has_session_consent(
        tmp_path, "demo", session_id="sess-A", action="git_push", target_hash=th
    ) is True
    # wrong action / wrong target_hash -> False
    assert cl.has_session_consent(
        tmp_path, "demo", session_id="sess-A", action="net_post", target_hash=th
    ) is False
    assert cl.has_session_consent(
        tmp_path, "demo", session_id="sess-A", action="git_push", target_hash="0" * 64
    ) is False


def test_has_session_consent_different_session_is_false(tmp_path: Path) -> None:
    # PER-SESSION: a consent granted under sess-A does NOT authorize sess-B even
    # for the identical action + target.
    th = cl.target_hash("origin main")
    _append(tmp_path, target="origin main", run_id="r1", action="git_push",
            session_id="sess-A")
    assert cl.has_session_consent(
        tmp_path, "demo", session_id="sess-B", action="git_push", target_hash=th
    ) is False


def test_has_session_consent_tampered_chain_is_false(tmp_path: Path) -> None:
    _append(tmp_path, target="t0", run_id="r0", action="git_push", session_id="s")
    _append(tmp_path, target="t1", run_id="r1", action="net_post", session_id="s")
    _append(tmp_path, target="t2", run_id="r2", action="fs_delete", session_id="s")
    path = cl.consent_path(tmp_path, "demo")
    lines = path.read_text(encoding="utf-8").splitlines()
    forged = json.loads(lines[1])
    forged["target_hash"] = "f" * 64
    lines[1] = cl.canonical_json(forged)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    th = cl.target_hash("t0")
    assert cl.has_session_consent(
        tmp_path, "demo", session_id="s", action="git_push", target_hash=th
    ) is False


def test_has_session_consent_in_all() -> None:
    assert "has_session_consent" in cl.__all__
