#!/usr/bin/env python3
"""engine_version.py — single source of the engine version, read from
``.claude-plugin/plugin.json#/version`` (spec §8 self-upgrade versioning).

The engine version has ONE home here. Orchestration stamps each coverage record
with it (so an artifact knows which engine produced it) and refuses to resume a
run across a version boundary. Because plugin.json is already file #1 of the
``version_bump`` 5-file set, a release bump updates THIS source automatically —
there is no second place to keep in sync.

Pure: a single plugin.json read at import time into ``ENGINE_VERSION``; no clock,
no RNG, no other I/O. Fail-loud: a missing file, malformed JSON, an absent
``version`` key, or a non-string / empty value raises ``EngineVersionError``
rather than silently defaulting — the version is a committed contract and must
always be present (the same discipline as ``active_projects.py``).

Repo root is anchored ``Path(__file__).resolve().parents[2]`` (the same way
``active_projects.py`` does), NOT ``CLAUDE_PLUGIN_ROOT`` — so an installed-plugin
copy cannot shadow the working tree's plugin.json.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_JSON = _REPO_ROOT / ".claude-plugin" / "plugin.json"


class EngineVersionError(RuntimeError):
    """Raised when the engine version cannot be sourced from plugin.json."""


def _load_engine_version(path: Path = _PLUGIN_JSON) -> str:
    """Read and validate ``#/version`` from plugin.json at ``path``.

    Fail-loud: a missing file, malformed JSON, an absent ``version`` key, or a
    non-string / empty value raises :class:`EngineVersionError`. The version is a
    committed contract — it is never silently defaulted.

    A ``path`` parameter keeps the read testable (point it at a missing / garbage
    / key-absent file to exercise the failure branches) without breaking the
    module-level read.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EngineVersionError(f"plugin.json not found at {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EngineVersionError(
            f"plugin.json at {path} is not valid JSON: {exc}"
        ) from exc
    try:
        value = data["version"]
    except (KeyError, TypeError) as exc:
        raise EngineVersionError(
            f"plugin.json at {path} is missing #/version"
        ) from exc
    if not isinstance(value, str) or not value:
        raise EngineVersionError(
            f"plugin.json #/version must be a non-empty string, got {value!r}"
        )
    return value


#: The engine version — read ONCE at import from plugin.json ``#/version``
#: (spec §8). This is the primary API: callers read THIS value (or call the
#: function form below).
ENGINE_VERSION: str = _load_engine_version()


def engine_version(path: Path | str | None = None) -> str:
    """Return the engine version (plugin.json ``#/version``).

    Default (no ``path``): the value read ONCE at import — the cached single
    source. A ``path`` is read fresh (uncached) so tests can exercise the
    fail-loud branches against a fixture plugin.json.
    """
    if path is None:
        return ENGINE_VERSION
    return _load_engine_version(Path(path))


__all__ = [
    "ENGINE_VERSION",
    "engine_version",
    "EngineVersionError",
]
