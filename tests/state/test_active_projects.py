#!/usr/bin/env python3
"""Tests for scripts/state/active_projects.py — the single home of the
portfolio cap (``ACTIVE_PROJECTS_MAX``), sourced from
schemas/portfolio-config.schema.json#/properties/active_projects/maxItems
(spec §8 consolidation).

Covers four contracts:
  * value equivalence — ``ACTIVE_PROJECTS_MAX == 12 == schema maxItems``
    (the value is SOURCED from the schema, not a re-typed literal);
  * fail-loud — the loader RAISES on a missing / malformed / key-absent
    schema rather than silently defaulting to 12 (committed contract);
  * no-second-definition guard — exactly ONE module under ``scripts/``
    DEFINES the constant; every reporting module now IMPORTS it. This guard
    is what keeps the copy-pasted literal from ever returning;
  * importer equivalence — each previously-copying reporting module exposes
    the SAME value (== 12) via the import.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest

from scripts.state.active_projects import (
    ACTIVE_PROJECTS_MAX,
    ActiveProjectsMaxError,
    _load_active_projects_max,
    active_projects_max,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "portfolio-config.schema.json"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

#: A DEFINITION of the module-level constant at column 0, in both the plain
#: (``NAME = ``) and annotated (``NAME: int = ``) forms. Deliberately does
#: NOT match a use site (indented), an import (``from … import NAME``), or an
#: ``__all__`` entry (``"NAME"``) — only an assignment counts.
_DEFINITION_RE = re.compile(r"^ACTIVE_PROJECTS_MAX\s*(?::[^=]*)?=")

#: Every reporting module that previously copy-pasted the literal.
_REPORTING_MODULES = (
    "scripts.reporting.portfolio_overview",
    "scripts.reporting.portfolio_monthly_roundup",
    "scripts.reporting.portfolio_heatmap",
    "scripts.reporting.portfolio_kpi_trend",
    "scripts.reporting.portfolio_task_heatmap",
)


def _schema_max_items() -> int:
    """Independent read of the schema's maxItems (the source of truth)."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["properties"]["active_projects"]["maxItems"]


# --- value equivalence ------------------------------------------------------

def test_active_projects_max_is_twelve() -> None:
    assert ACTIVE_PROJECTS_MAX == 12


def test_active_projects_max_equals_schema_maxitems() -> None:
    # Sourced from the schema, not a re-typed literal — read both, compare.
    assert ACTIVE_PROJECTS_MAX == _schema_max_items()


def test_active_projects_max_function_form_matches_constant() -> None:
    assert active_projects_max() == ACTIVE_PROJECTS_MAX == 12


def test_loader_reads_real_schema_value() -> None:
    # The committed schema loads cleanly and yields the constant's value.
    assert _load_active_projects_max(_SCHEMA_PATH) == ACTIVE_PROJECTS_MAX


# --- fail-loud (committed contract; never silently default to 12) ----------

def test_loader_raises_on_missing_schema(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(ActiveProjectsMaxError):
        _load_active_projects_max(missing)


def test_loader_raises_on_malformed_json(tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.json"
    garbage.write_text("{ this is not valid json", encoding="utf-8")
    with pytest.raises(ActiveProjectsMaxError):
        _load_active_projects_max(garbage)


def test_loader_raises_on_absent_key_path(tmp_path: Path) -> None:
    # Valid JSON, but #/properties/active_projects/maxItems is absent.
    no_key = tmp_path / "no-key.json"
    no_key.write_text(json.dumps({"properties": {}}), encoding="utf-8")
    with pytest.raises(ActiveProjectsMaxError):
        _load_active_projects_max(no_key)


def test_loader_raises_on_non_int_maxitems(tmp_path: Path) -> None:
    bad = tmp_path / "bad-type.json"
    bad.write_text(
        json.dumps({"properties": {"active_projects": {"maxItems": "twelve"}}}),
        encoding="utf-8",
    )
    with pytest.raises(ActiveProjectsMaxError):
        _load_active_projects_max(bad)


# --- no-second-definition guard --------------------------------------------

def test_exactly_one_definition_in_scripts() -> None:
    """The ONLY module under scripts/ that DEFINES ACTIVE_PROJECTS_MAX is
    scripts/state/active_projects.py — every reporting module imports it."""
    definitions: list[str] = []
    for py in sorted(_SCRIPTS_DIR.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        for lineno, line in enumerate(
            py.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _DEFINITION_RE.match(line):
                definitions.append(f"{py.relative_to(_REPO_ROOT)}:{lineno}")
    assert len(definitions) == 1, (
        f"expected EXACTLY ONE definition of ACTIVE_PROJECTS_MAX under "
        f"scripts/, found {len(definitions)}: {definitions}"
    )
    assert definitions[0].startswith("scripts/state/active_projects.py:"), (
        f"the single definition must live in the single-home module, got "
        f"{definitions[0]}"
    )


# --- importer equivalence ---------------------------------------------------

@pytest.mark.parametrize("module_name", _REPORTING_MODULES)
def test_reporting_module_exposes_same_constant(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod.ACTIVE_PROJECTS_MAX == ACTIVE_PROJECTS_MAX == 12
