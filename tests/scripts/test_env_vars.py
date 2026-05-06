"""tests/scripts/test_env_vars.py — ADR-035 workspace env var resolver.

Locks the contract for ``scripts/state/env.py::get_workspace_root()``:
canonical wins over alias, alias triggers DeprecationWarning, both unset
returns None. v2.0 will drop the alias branch — this file flips with it.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from scripts.state import env


def test_canonical_set_returns_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(env.CANONICAL, str(tmp_path))
    monkeypatch.delenv(env.DEPRECATED_ALIAS, raising=False)
    result = env.get_workspace_root()
    assert result == tmp_path


def test_canonical_wins_over_alias(monkeypatch, tmp_path: Path) -> None:
    canonical_dir = tmp_path / "canonical"
    alias_dir = tmp_path / "alias"
    monkeypatch.setenv(env.CANONICAL, str(canonical_dir))
    monkeypatch.setenv(env.DEPRECATED_ALIAS, str(alias_dir))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = env.get_workspace_root()
    assert result == canonical_dir


def test_alias_only_emits_deprecation_warning(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(env.CANONICAL, raising=False)
    monkeypatch.setenv(env.DEPRECATED_ALIAS, str(tmp_path))
    with pytest.warns(DeprecationWarning, match=env.DEPRECATED_ALIAS):
        result = env.get_workspace_root()
    assert result == tmp_path


def test_both_unset_returns_none(monkeypatch) -> None:
    monkeypatch.delenv(env.CANONICAL, raising=False)
    monkeypatch.delenv(env.DEPRECATED_ALIAS, raising=False)
    assert env.get_workspace_root() is None


def test_tilde_expansion(monkeypatch) -> None:
    monkeypatch.setenv(env.CANONICAL, "~/some-workspace")
    result = env.get_workspace_root()
    assert result is not None
    assert "~" not in str(result)
    assert str(result).endswith("some-workspace")


def test_deadline_constant_documented() -> None:
    """ADR-035 1-year shim: deadline 2027-05-06 (mirrors ADR-030 pattern).

    When the deadline is reached, the alias branch + this file's tests are
    pruned in a v2.0 commit.
    """
    assert env.DEPRECATION_DEADLINE == "2027-05-06"
