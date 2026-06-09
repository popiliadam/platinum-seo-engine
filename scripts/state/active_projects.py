#!/usr/bin/env python3
"""active_projects.py — single source of the portfolio cap, sourced from
schemas/portfolio-config.schema.json#/properties/active_projects/maxItems
(spec §8 consolidation).

The portfolio cap (how many projects the system manages in active rotation)
has ONE home here. Reporting modules import ``ACTIVE_PROJECTS_MAX`` from this
module instead of copy-pasting the literal, so a schema-first bump of the
schema's ``maxItems`` updates every consumer at once — a migration cannot
silently miss a stray copy.

Pure: a single schema read at import time; no clock, no RNG, no other I/O.
Fail-loud: a missing file, malformed JSON, or an absent key path raises
``ActiveProjectsMaxError`` rather than silently defaulting to 12 — the cap is
a committed contract and must always be present.

Repo root is anchored ``Path(__file__).resolve().parents[2]`` (the same way
the reporting scripts do), NOT ``CLAUDE_PLUGIN_ROOT`` — so an installed-plugin
copy cannot shadow the working tree's schema.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "portfolio-config.schema.json"


class ActiveProjectsMaxError(RuntimeError):
    """Raised when the portfolio cap cannot be sourced from the schema."""


def _load_active_projects_max(schema_path: Path = _SCHEMA_PATH) -> int:
    """Read ``#/properties/active_projects/maxItems`` from the portfolio
    config schema and return it.

    Fail-loud: a missing file, malformed JSON, an absent key path, or a
    non-integer value raises :class:`ActiveProjectsMaxError`. The cap is a
    committed contract — it is never silently defaulted to 12.

    A ``schema_path`` parameter keeps the read testable (point it at a
    missing / garbage file to exercise the failure path) without breaking the
    module-level read.
    """
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ActiveProjectsMaxError(
            f"portfolio-config schema not found at {schema_path}: {exc}"
        ) from exc
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ActiveProjectsMaxError(
            f"portfolio-config schema at {schema_path} is not valid JSON: {exc}"
        ) from exc
    try:
        value = schema["properties"]["active_projects"]["maxItems"]
    except (KeyError, TypeError) as exc:
        raise ActiveProjectsMaxError(
            f"portfolio-config schema at {schema_path} is missing "
            "#/properties/active_projects/maxItems"
        ) from exc
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActiveProjectsMaxError(
            "#/properties/active_projects/maxItems must be an integer, got "
            f"{value!r}"
        )
    return value


#: Maximum number of active projects the portfolio manages — the single home
#: of the cap, read once at import from the schema's ``maxItems`` (spec §8).
#: This is the primary API: importers read THIS name.
ACTIVE_PROJECTS_MAX: int = _load_active_projects_max()


def active_projects_max() -> int:
    """Return the portfolio cap (function form of ``ACTIVE_PROJECTS_MAX``)."""
    return ACTIVE_PROJECTS_MAX


__all__ = [
    "ACTIVE_PROJECTS_MAX",
    "active_projects_max",
    "ActiveProjectsMaxError",
]
