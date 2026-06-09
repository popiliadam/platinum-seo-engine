"""tests/scripts/test_session_binding_workspace_conflict.py — Audit#2 #7.

#7: resolve_workspace_root resolved config-first (~/.config/pseo/config.json) and
SILENTLY ignored a DIFFERENT PSEO_WORKSPACE_ROOT env value (ADR-035). A silent
divergence is a foot-gun — the operator believes they target workspace A (the env
they exported) while the engine writes to workspace B (the persisted config).

Operator decision: FAIL-LOUD when both sources are set AND differ, unless an
explicit override (PSEO_WORKSPACE_ROOT_OVERRIDE=env|config) names the winner.
Every NON-conflict case (config-only, env-only, both-equal, neither) is UNCHANGED.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.state import session_binding as sb


def _write_config(home: Path, workspace_root: str) -> None:
    cfg = home / ".config" / "pseo" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"workspace_root": workspace_root}), encoding="utf-8")


# ---- conflict: both set + differ -> fail-loud --------------------------------

def test_conflict_both_set_and_differ_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "from_config"))
    with pytest.raises(sb.WorkspaceRootConflictError):
        sb.resolve_workspace_root(
            environ={"PSEO_WORKSPACE_ROOT": str(tmp_path / "from_env")}
        )


def test_conflict_error_message_names_both_sources_and_the_fix(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "from_config"))
    with pytest.raises(sb.WorkspaceRootConflictError) as exc:
        sb.resolve_workspace_root(
            environ={"PSEO_WORKSPACE_ROOT": str(tmp_path / "from_env")}
        )
    msg = str(exc.value)
    assert "from_config" in msg and "from_env" in msg, (
        "the fail-loud message must name BOTH conflicting paths"
    )
    assert "PSEO_WORKSPACE_ROOT_OVERRIDE" in msg, (
        "the message must tell the operator how to resolve the conflict"
    )


def test_conflict_error_is_value_error_subclass() -> None:
    # callers that catch ValueError (e.g. the bind CLI's main) still handle it.
    assert issubclass(sb.WorkspaceRootConflictError, ValueError)


# ---- override resolves the conflict deterministically ------------------------

def test_override_env_wins(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "from_config"))
    got = sb.resolve_workspace_root(environ={
        "PSEO_WORKSPACE_ROOT": str(tmp_path / "from_env"),
        "PSEO_WORKSPACE_ROOT_OVERRIDE": "env",
    })
    assert got == tmp_path / "from_env"


def test_override_config_wins(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "from_config"))
    got = sb.resolve_workspace_root(environ={
        "PSEO_WORKSPACE_ROOT": str(tmp_path / "from_env"),
        "PSEO_WORKSPACE_ROOT_OVERRIDE": "config",
    })
    assert got == tmp_path / "from_config"


def test_override_is_case_insensitive(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "from_config"))
    got = sb.resolve_workspace_root(environ={
        "PSEO_WORKSPACE_ROOT": str(tmp_path / "from_env"),
        "PSEO_WORKSPACE_ROOT_OVERRIDE": "ENV",
    })
    assert got == tmp_path / "from_env"


def test_invalid_override_still_raises(tmp_path, monkeypatch) -> None:
    # an override naming neither side cannot resolve the conflict -> still fail-loud.
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "from_config"))
    with pytest.raises(sb.WorkspaceRootConflictError):
        sb.resolve_workspace_root(environ={
            "PSEO_WORKSPACE_ROOT": str(tmp_path / "from_env"),
            "PSEO_WORKSPACE_ROOT_OVERRIDE": "banana",
        })


# ---- non-conflict passthrough (behavior UNCHANGED) ---------------------------

def test_no_conflict_config_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "ws"))
    assert sb.resolve_workspace_root(environ={}) == tmp_path / "ws"


def test_no_conflict_env_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    assert sb.resolve_workspace_root(
        environ={"PSEO_WORKSPACE_ROOT": str(tmp_path / "ws")}
    ) == tmp_path / "ws"


def test_no_conflict_both_equal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    same = str(tmp_path / "ws")
    _write_config(tmp_path, same)
    assert sb.resolve_workspace_root(
        environ={"PSEO_WORKSPACE_ROOT": same}
    ) == tmp_path / "ws"


def test_no_conflict_both_equal_after_normalization(tmp_path, monkeypatch) -> None:
    # a trailing-slash / non-normalized form of the SAME path is NOT a conflict.
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_config(tmp_path, str(tmp_path / "ws"))
    got = sb.resolve_workspace_root(
        environ={"PSEO_WORKSPACE_ROOT": str(tmp_path / "ws") + "/"}
    )
    assert got == tmp_path / "ws"


def test_no_conflict_neither_set(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    assert sb.resolve_workspace_root(environ={}) is None
