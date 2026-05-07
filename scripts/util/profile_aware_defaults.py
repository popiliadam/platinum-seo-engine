"""scripts/util/profile_aware_defaults.py — Y-06 profile-aware default cascade.

Five+ transforms previously hard-coded scalar tuning constants directly
(cannibalization MIN_IMPRESSIONS, content_decay DECAY/GROWTH thresholds,
tech_audit URL_CAP, internal_links MAX_ENTRIES, quickwins
threshold_position_max). This module collapses the lookup pattern into
one canonical SSOT that supports a three-tier cascade:

    CLI override > project-config profile > inline default

The transforms call :func:`cascade_default` (or :func:`cascade_defaults`
for batches) instead of binding inline constants directly at the
resolution point. When a profile lacks a key, the inline default is
used (backwards-compat with current behavior). When project-config
schema later adds tuning fields, no transform code needs to change —
the cascade automatically picks them up.

API surface:

    load_profile(workspace_root, project_slug, *, config_filename=...) → dict
        Read the profile config for the named project (canonical filename
        is `project.config.json` per ADR-033; PSEO_WORKSPACE_ROOT paterni
        per ADR-035). Returns empty dict on every "not found" branch
        (workspace missing, subdir missing, file missing, explicit None)
        so callers can keep their inline defaults intact. Raises
        :class:`ProfileLoadError` only when the file exists but is
        malformed JSON or parses to a non-dict.

    cascade_default(profile, key, inline_default, override=None) → value
        Single-key three-tier cascade. ``override`` (CLI / call-site
        explicit) wins when not ``None``; otherwise ``profile[key]`` if
        present and non-None; otherwise ``inline_default``. ``None`` is
        treated as "unset" — empty string and zero are valid values.

    cascade_defaults(profile, defaults_mapping, overrides=None) → dict
        Batch wrapper for multiple keys. ``overrides`` mapping is
        optional; missing keys receive their inline defaults.

Refs:
    * ADR-035 (PSEO_WORKSPACE_ROOT canonical workspace path)
    * ADR-009 (master-excel schema-driven defaults / config inheritance)
    * 2026-05-07 v1.6-Phase-3 Y-06 (this module + 5+ transform migrate)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "ProfileLoadError",
    "load_profile",
    "cascade_default",
    "cascade_defaults",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ProfileLoadError(ValueError):
    """Raised when a profile config file is present but malformed.

    Extends :class:`ValueError` so legacy callers that expected a bare
    ``ValueError`` continue to work (paterni K-01 reuse). Caller-side
    domain wrappers may adapt-wrap into their own exception class.
    """


# ---------------------------------------------------------------------------
# Profile loader (workspace + slug discovery, PSEO_WORKSPACE_ROOT paterni)
# ---------------------------------------------------------------------------


def load_profile(
    workspace_root: str | Path | None,
    project_slug: str,
    *,
    config_filename: str = "project.config.json",
) -> dict:
    """Load the profile configuration for a project.

    Args:
        workspace_root: workspace directory (PSEO_WORKSPACE_ROOT canonical).
            ``None`` short-circuits to empty dict (no workspace bound).
        project_slug: project subdirectory name under ``workspace_root``.
        config_filename: profile filename (default ``project.config.json``
            per ADR-033 canonical).

    Returns:
        Parsed profile dict, or empty dict if ``workspace_root`` is
        ``None``, the workspace path doesn't exist, the project subdir
        is absent, or the config file isn't present.

    Raises:
        ProfileLoadError: file exists but malformed JSON or parses to
            a non-dict.
    """
    if workspace_root is None:
        return {}
    root = Path(workspace_root)
    if not root.exists():
        return {}
    config_path = root / project_slug / config_filename
    if not config_path.exists():
        return {}
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileLoadError(
            f"profile config malformed at {config_path}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise ProfileLoadError(
            f"profile config must be a dict, got {type(loaded).__name__} "
            f"at {config_path}"
        )
    return loaded


# ---------------------------------------------------------------------------
# Cascade — three-tier resolution (CLI override > profile > inline default)
# ---------------------------------------------------------------------------


def cascade_default(
    profile: Mapping[str, Any],
    key: str,
    inline_default: Any,
    override: Any = None,
) -> Any:
    """Three-tier single-key cascade.

    Resolution order:

        1. ``override`` (CLI / call-site explicit) — wins when not ``None``
        2. ``profile[key]`` — wins when present and not ``None``
        3. ``inline_default`` — fallback

    ``None`` is the only sentinel for "unset" — empty string, zero, and
    empty containers are valid values that override the next tier down.
    """
    if override is not None:
        return override
    if isinstance(profile, Mapping):
        profile_value = profile.get(key)
        if profile_value is not None:
            return profile_value
    return inline_default


def cascade_defaults(
    profile: Mapping[str, Any],
    defaults: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict:
    """Batch wrapper for :func:`cascade_default`.

    Apply over a ``{key: inline_default}`` mapping, optionally with an
    ``{key: cli_value}`` overrides mapping.

    Args:
        profile: profile config dict (output of :func:`load_profile`).
        defaults: ``{key: inline_default}`` mapping.
        overrides: ``{key: cli_value}`` mapping; ``None`` values are
            treated as "no override" and ignored.

    Returns:
        Resolved ``{key: value}`` dict with one entry per key in
        ``defaults``.
    """
    overrides = overrides or {}
    return {
        key: cascade_default(profile, key, default, overrides.get(key))
        for key, default in defaults.items()
    }
