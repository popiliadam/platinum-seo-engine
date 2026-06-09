#!/usr/bin/env python3
"""Tests for scripts/state/engine_version.py — the single source of the engine
version, read from ``.claude-plugin/plugin.json#/version`` (spec §8 self-upgrade
versioning).

Covers three contracts (mirrors the active_projects.py shape):
  * value equivalence — ``engine_version()`` returns the version SOURCED from
    plugin.json, NOT a re-typed literal (asserted against an independent read);
  * single source — ``ENGINE_VERSION`` (read once at import) equals the function;
  * fail-loud — the loader RAISES ``EngineVersionError`` on a missing / malformed
    / key-absent / non-string / empty plugin.json rather than silently defaulting
    (a committed contract). The ``path`` param makes the failure branches testable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.state.engine_version import (
    ENGINE_VERSION,
    EngineVersionError,
    engine_version,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_JSON = _REPO_ROOT / ".claude-plugin" / "plugin.json"


# --- value equivalence (sourced, not hardcoded) ----------------------------

def test_engine_version_sources_from_plugin_json() -> None:
    """The returned version equals the value read INDEPENDENTLY from plugin.json
    (proves it is sourced from the file, not a hardcoded literal)."""
    independent = json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))["version"]
    assert engine_version() == independent
    assert isinstance(engine_version(), str) and engine_version()


def test_module_constant_equals_function() -> None:
    """``ENGINE_VERSION`` (read once at import) is the same single source the
    function returns."""
    assert ENGINE_VERSION == engine_version()


# --- testable path param ---------------------------------------------------

def test_engine_version_reads_given_path(tmp_path: Path) -> None:
    """A ``path`` argument is read fresh — returns THAT file's version."""
    plugin = tmp_path / "plugin.json"
    plugin.write_text(json.dumps({"version": "1.2.3-test"}), encoding="utf-8")
    assert engine_version(plugin) == "1.2.3-test"


# --- fail-loud branches ----------------------------------------------------

def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(EngineVersionError):
        engine_version(tmp_path / "does-not-exist.json")


def test_malformed_json_raises(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin.json"
    plugin.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(EngineVersionError):
        engine_version(plugin)


def test_missing_version_key_raises(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin.json"
    plugin.write_text(json.dumps({"name": "x"}), encoding="utf-8")
    with pytest.raises(EngineVersionError):
        engine_version(plugin)


def test_non_string_version_raises(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin.json"
    plugin.write_text(json.dumps({"version": 200}), encoding="utf-8")
    with pytest.raises(EngineVersionError):
        engine_version(plugin)


def test_empty_string_version_raises(tmp_path: Path) -> None:
    """An empty version would breach the coverage schema's minLength:1 — reject
    it at the source rather than emit an invalid record downstream."""
    plugin = tmp_path / "plugin.json"
    plugin.write_text(json.dumps({"version": ""}), encoding="utf-8")
    with pytest.raises(EngineVersionError):
        engine_version(plugin)
