"""tests/util/test_profile_aware_defaults.py — Y-06 profile-aware default cascade.

Single canonical implementation lives in
:mod:`scripts.util.profile_aware_defaults`. Five+ transforms previously
hard-coded scalar tuning constants directly (cannibalization
MIN_IMPRESSIONS, content_decay DECAY/GROWTH thresholds, tech_audit
URL_CAP, internal_links MAX_ENTRIES, quickwins threshold_position_max).
Y-06 introduces a three-tier cascade SSOT (CLI override > profile config
> inline default).

API surface tested:

    * load_profile(workspace_root, project_slug) — workspace+slug discovery
    * cascade_default(profile, key, inline_default, override=None)
    * cascade_defaults(profile, defaults_mapping, overrides=None)
    * ProfileLoadError (extends ValueError, paterni K-01 reuse)

DURUR triggers:
    * profile config file present but malformed JSON
    * profile config file present but parses to non-dict

Backwards-compat semantics:
    * workspace_root=None → empty dict (no workspace bound)
    * workspace_root path missing → empty dict
    * project subdir missing → empty dict
    * config file missing → empty dict
    * profile_value=None or absent → fall back to inline default

Refs:
    * ADR-035 (PSEO_WORKSPACE_ROOT canonical)
    * ADR-009 (master-excel schema-driven config inheritance)
    * 2026-05-07 v1.6-Phase-3 Y-06 (this module + 5+ transform migrate)
"""

from __future__ import annotations

import json

import pytest

from scripts.util.profile_aware_defaults import (
    ProfileLoadError,
    cascade_default,
    cascade_defaults,
    load_profile,
)


# ---------------------------------------------------------------------------
# load_profile — file/path discovery + safe fallbacks
# ---------------------------------------------------------------------------


def test_load_profile_workspace_root_none():
    """No workspace bound → empty dict (don't raise)."""
    assert load_profile(None, "any-slug") == {}


def test_load_profile_workspace_missing(tmp_path):
    """Workspace path doesn't exist → empty dict."""
    assert load_profile(tmp_path / "missing", "slug") == {}


def test_load_profile_project_subdir_missing(tmp_path):
    """Workspace exists but project subdir absent → empty dict."""
    assert load_profile(tmp_path, "missing-slug") == {}


def test_load_profile_config_missing(tmp_path):
    """Project subdir exists but no config file → empty dict."""
    (tmp_path / "demo").mkdir()
    assert load_profile(tmp_path, "demo") == {}


def test_load_profile_reads_json(tmp_path):
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "project.config.json").write_text(
        json.dumps({"min_impressions": 25, "url_cap": 100}), encoding="utf-8"
    )
    profile = load_profile(tmp_path, "demo")
    assert profile["min_impressions"] == 25
    assert profile["url_cap"] == 100


def test_load_profile_custom_filename(tmp_path):
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "settings.json").write_text(
        json.dumps({"k": 1}), encoding="utf-8"
    )
    profile = load_profile(tmp_path, "demo", config_filename="settings.json")
    assert profile["k"] == 1


def test_load_profile_malformed_raises(tmp_path):
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "project.config.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    with pytest.raises(ProfileLoadError, match="malformed"):
        load_profile(tmp_path, "demo")


def test_load_profile_non_dict_raises(tmp_path):
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "project.config.json").write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(ProfileLoadError, match="must be a dict"):
        load_profile(tmp_path, "demo")


# ---------------------------------------------------------------------------
# cascade_default — three-tier resolution
# ---------------------------------------------------------------------------


def test_cascade_default_override_wins():
    profile = {"key": "profile_value"}
    assert (
        cascade_default(profile, "key", "inline_default", override="cli_value")
        == "cli_value"
    )


def test_cascade_default_profile_wins_over_inline():
    profile = {"key": "profile_value"}
    assert cascade_default(profile, "key", "inline_default") == "profile_value"


def test_cascade_default_inline_when_profile_missing():
    profile: dict = {}
    assert cascade_default(profile, "key", "inline_default") == "inline_default"


def test_cascade_default_inline_when_profile_value_none():
    profile = {"key": None}
    assert cascade_default(profile, "key", "inline_default") == "inline_default"


def test_cascade_default_override_none_ignored():
    """override=None is treated as 'no override' → fall back to profile."""
    profile = {"key": "profile_value"}
    assert (
        cascade_default(profile, "key", "inline_default", override=None)
        == "profile_value"
    )


def test_cascade_default_zero_override_is_valid_value():
    """0 is NOT 'unset' — only None is. Valid override of 0 wins."""
    assert cascade_default({}, "k", 100, override=0) == 0


def test_cascade_default_empty_string_override_is_valid_value():
    """Empty string is NOT 'unset' — only None is."""
    assert cascade_default({}, "k", "fallback", override="") == ""


# ---------------------------------------------------------------------------
# cascade_defaults — batch
# ---------------------------------------------------------------------------


def test_cascade_defaults_resolves_multiple_keys():
    profile = {"k1": "p1"}
    result = cascade_defaults(profile, {"k1": "i1", "k2": "i2", "k3": "i3"})
    assert result == {"k1": "p1", "k2": "i2", "k3": "i3"}


def test_cascade_defaults_overrides_mapping():
    profile = {"k1": "p1", "k2": "p2"}
    overrides = {"k1": "cli1", "k3": None}
    result = cascade_defaults(
        profile, {"k1": "i1", "k2": "i2", "k3": "i3"}, overrides
    )
    assert result == {"k1": "cli1", "k2": "p2", "k3": "i3"}


def test_cascade_defaults_handles_no_overrides():
    profile = {"k1": "p1"}
    result = cascade_defaults(profile, {"k1": "i1", "k2": "i2"})
    assert result == {"k1": "p1", "k2": "i2"}


def test_cascade_defaults_empty_profile():
    result = cascade_defaults({}, {"a": 1, "b": 2})
    assert result == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


def test_profile_aware_defaults_module_exports():
    """__all__ pins the public surface."""
    import scripts.util.profile_aware_defaults as mod

    expected = {
        "ProfileLoadError",
        "load_profile",
        "cascade_default",
        "cascade_defaults",
    }
    assert set(mod.__all__) == expected


def test_profile_load_error_extends_value_error():
    """Legacy callers expecting bare ValueError continue to work
    (paterni K-01 reuse)."""
    assert issubclass(ProfileLoadError, ValueError)
