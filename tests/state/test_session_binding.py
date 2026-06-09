"""tests/state/test_session_binding.py — AMO batch 0b session-binding primitive.

TDD lock for scripts/state/session_binding.py: the pure resolver/marker R-W +
config-persistence functions plus the thin `bind` CLI. Every filesystem test
uses tmp_path / a monkeypatched HOME — never the real ~/.config or a real
workspace.

Authority: schemas/session-marker.schema.json (marker shape),
  ADR-035 PSEO_WORKSPACE_ROOT (env fallback), batch 0a cross-env probe.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.state import session_binding as sb

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _REPO_ROOT / "schemas" / "session-marker.schema.json"


# ---------------------------------------------------------------------------
# 1. resolve_session_project precedence + strict contract
# ---------------------------------------------------------------------------

def test_resolve_session_project_precedence(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "global-active"}), encoding="utf-8"
    )
    sb.write_session_binding("sess-A", "bound-proj", ws, "2026-06-05T00:00:00")

    # arg always wins (even over a marker that exists for this session)
    assert sb.resolve_session_project(ws, arg="explicit", session_id="sess-A") == "explicit"
    # marker beats active.json
    assert sb.resolve_session_project(ws, session_id="sess-A") == "bound-proj"
    # session has no marker -> active.json fallback
    assert sb.resolve_session_project(ws, session_id="sess-UNBOUND") == "global-active"

    # neither marker nor active.json -> None
    empty = tmp_path / "empty"
    empty.mkdir()
    assert sb.resolve_session_project(empty, session_id="sess-X") is None
    # strict + None -> raises (preserves dump_workspace's strict contract)
    with pytest.raises(FileNotFoundError):
        sb.resolve_session_project(empty, session_id="sess-X", strict=True)


def test_resolve_session_project_arg_does_not_need_workspace() -> None:
    # explicit arg short-circuits before any filesystem read
    assert sb.resolve_session_project(None, arg="explicit") == "explicit"


# ---------------------------------------------------------------------------
# 2. current_session_id — hook payload vs command env
# ---------------------------------------------------------------------------

def test_current_session_id_payload_wins() -> None:
    assert sb.current_session_id({"session_id": "hook-sess"}, environ={}) == "hook-sess"


def test_current_session_id_env_fallback() -> None:
    assert sb.current_session_id(None, environ={"CLAUDE_CODE_SESSION_ID": "env-sess"}) == "env-sess"
    # empty / blank payload session_id falls through to the env var
    assert sb.current_session_id({}, environ={"CLAUDE_CODE_SESSION_ID": "env-sess"}) == "env-sess"
    assert sb.current_session_id(
        {"session_id": ""}, environ={"CLAUDE_CODE_SESSION_ID": "env-sess"}
    ) == "env-sess"


def test_current_session_id_none() -> None:
    assert sb.current_session_id(None, environ={}) is None


# ---------------------------------------------------------------------------
# 3. sessions_dir + write/read round-trip
# ---------------------------------------------------------------------------

def test_sessions_dir_is_workspace_shared_sessions(tmp_path: Path) -> None:
    assert sb.sessions_dir(tmp_path) == tmp_path / "shared" / "sessions"


def test_write_read_roundtrip(tmp_path: Path) -> None:
    sb.write_session_binding("sess-1", "demo", tmp_path, "2026-06-05T00:00:00")
    assert sb.read_session_binding("sess-1", tmp_path) == "demo"


# ---------------------------------------------------------------------------
# 4. written marker is valid JSON + validates against the schema
# ---------------------------------------------------------------------------

def test_written_marker_validates_against_schema(tmp_path: Path) -> None:
    path = sb.write_session_binding("sess-xyz", "demo-proj", tmp_path, "2026-06-05T12:00:00")
    data = json.loads(path.read_text(encoding="utf-8"))  # valid JSON
    validator = Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    validator.validate(data)  # raises on schema mismatch
    assert data == {
        "active_project": "demo-proj",
        "bound_at": "2026-06-05T12:00:00",
        "session_id": "sess-xyz",
    }


# ---------------------------------------------------------------------------
# 5. persist_workspace_root writes/merges ~/.config/pseo/config.json
# ---------------------------------------------------------------------------

def test_persist_workspace_root_merges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".config" / "pseo" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"other_key": "keep"}), encoding="utf-8")

    ws = tmp_path / "workspace"
    returned = sb.persist_workspace_root(ws)

    assert returned == cfg
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["workspace_root"] == str(ws)
    assert data["other_key"] == "keep"  # merge-preserving


def test_persist_workspace_root_creates_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = tmp_path / "ws2"
    returned = sb.persist_workspace_root(ws)
    assert returned.exists()
    assert json.loads(returned.read_text(encoding="utf-8"))["workspace_root"] == str(ws)


def test_resolve_workspace_root_config_wins_via_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Audit#2 #7: a DIFFERING env vs config no longer SILENTLY prefers config —
    # that silent divergence WAS the finding (see
    # tests/scripts/test_session_binding_workspace_conflict.py for the fail-loud
    # contract). Config now "wins" only when the operator names it explicitly via
    # PSEO_WORKSPACE_ROOT_OVERRIDE=config.
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".config" / "pseo" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"workspace_root": str(tmp_path / "from_config")}), encoding="utf-8")
    got = sb.resolve_workspace_root(environ={
        "PSEO_WORKSPACE_ROOT": str(tmp_path / "from_env"),
        "PSEO_WORKSPACE_ROOT_OVERRIDE": "config",
    })
    assert got == tmp_path / "from_config"


def test_resolve_workspace_root_env_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    got = sb.resolve_workspace_root(environ={"PSEO_WORKSPACE_ROOT": str(tmp_path / "ws")})
    assert got == tmp_path / "ws"


def test_resolve_workspace_root_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    assert sb.resolve_workspace_root(environ={}) is None


# ---------------------------------------------------------------------------
# 6. read_* never raise on missing / garbage
# ---------------------------------------------------------------------------

def test_read_session_binding_graceful(tmp_path: Path) -> None:
    sd = sb.sessions_dir(tmp_path)
    sd.mkdir(parents=True)
    (sd / "s1.json").write_text("{not valid json", encoding="utf-8")
    assert sb.read_session_binding("s1", tmp_path) is None  # garbage -> None
    assert sb.read_session_binding("missing", tmp_path) is None  # absent -> None
    assert sb.read_session_binding("", tmp_path) is None  # empty id -> None


def test_read_active_project_graceful(tmp_path: Path) -> None:
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "active.json").write_text("garbage", encoding="utf-8")
    assert sb.read_active_project(tmp_path) is None  # garbage -> None
    assert sb.read_active_project(tmp_path / "nope") is None  # absent -> None


# ---------------------------------------------------------------------------
# 7. session_ids_consistent — runtime self-check helper for 0c
# ---------------------------------------------------------------------------

def test_session_ids_consistent() -> None:
    eq = {"session_id": "x"}
    assert sb.session_ids_consistent(eq, environ={"CLAUDE_CODE_SESSION_ID": "x"}) is True
    assert sb.session_ids_consistent(eq, environ={"CLAUDE_CODE_SESSION_ID": "y"}) is False
    # either side missing -> True (cannot prove inconsistency)
    assert sb.session_ids_consistent({}, environ={"CLAUDE_CODE_SESSION_ID": "y"}) is True
    assert sb.session_ids_consistent(eq, environ={}) is True
    assert sb.session_ids_consistent(None, environ={}) is True


# ---------------------------------------------------------------------------
# 8. write guards (defense-in-depth: no path traversal / bad slug)
# ---------------------------------------------------------------------------

def test_write_rejects_unsafe_session_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        sb.write_session_binding("../escape", "demo", tmp_path, "t")


def test_write_rejects_bad_slug(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        sb.write_session_binding("sess", "Bad_Slug", tmp_path, "t")


# ---------------------------------------------------------------------------
# 9. CLI `bind` — subprocess (python3 -m scripts.state.session_binding)
# ---------------------------------------------------------------------------

def _run_bind(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.state.session_binding", "bind", *args],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = str(tmp_path / "home")  # never the real ~/.config
    env.pop("PSEO_WORKSPACE_ROOT", None)
    env.pop("PSE_WORKSPACE_PATH", None)
    return env


def test_cli_bind_success(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "projects" / "demo").mkdir(parents=True)
    (ws / "projects" / "demo" / "project.config.json").write_text("{}", encoding="utf-8")

    env = _base_env(tmp_path)
    env["CLAUDE_CODE_SESSION_ID"] = "test-sess"
    result = _run_bind(["demo", "--workspace", str(ws)], env)

    assert result.returncode == 0, result.stderr
    marker = ws / "shared" / "sessions" / "test-sess.json"
    assert marker.exists()
    assert json.loads(marker.read_text(encoding="utf-8"))["active_project"] == "demo"
    assert "bound session" in result.stdout


def test_cli_bind_unknown_slug_nonzero(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "projects").mkdir(parents=True)
    env = _base_env(tmp_path)
    env["CLAUDE_CODE_SESSION_ID"] = "test-sess"
    result = _run_bind(["nonexistent", "--workspace", str(ws)], env)
    assert result.returncode != 0
    assert not (ws / "shared" / "sessions" / "test-sess.json").exists()


def test_cli_bind_missing_session_id_nonzero(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "projects" / "demo").mkdir(parents=True)
    (ws / "projects" / "demo" / "project.config.json").write_text("{}", encoding="utf-8")
    env = _base_env(tmp_path)
    env.pop("CLAUDE_CODE_SESSION_ID", None)  # force the no-session error path
    result = _run_bind(["demo", "--workspace", str(ws)], env)
    assert result.returncode != 0


def test_cli_bind_bound_at_is_utc_z(tmp_path: Path) -> None:
    """The bind CLI stamps bound_at as canonical UTC ('…Z'), not naive local time
    (finding #6). datetime.now().isoformat() emitted a tz-less LOCAL string;
    rules/time-discipline.md §8.10 fixes storage to canonical UTC '…Z'."""
    from datetime import datetime as _dt

    ws = tmp_path / "ws"
    (ws / "projects" / "demo").mkdir(parents=True)
    (ws / "projects" / "demo" / "project.config.json").write_text("{}", encoding="utf-8")
    env = _base_env(tmp_path)
    env["CLAUDE_CODE_SESSION_ID"] = "test-sess"
    result = _run_bind(["demo", "--workspace", str(ws)], env)

    assert result.returncode == 0, result.stderr
    marker = ws / "shared" / "sessions" / "test-sess.json"
    bound_at = json.loads(marker.read_text(encoding="utf-8"))["bound_at"]
    assert bound_at.endswith("Z"), bound_at
    _dt.fromisoformat(bound_at[:-1] + "+00:00")  # canonical + parseable instant
