"""Regression LOCK: docs + schemas + validator all agree on JSON Schema Draft 7.

Closes Codex audit P1-01. Three independent sources declare the JSON Schema
draft the engine targets, and nothing forces them to agree:

  1. every ``schemas/*.schema.json`` ``$schema`` URI,
  2. the validator class used in ``scripts/validation/validate_schema.py``,
  3. the prose in ``README.md``.

They are currently all Draft 7. If any one drifts (e.g. a new schema authored
against 2020-12, or the validator bumped to ``Draft202012Validator`` without
updating the docs / schemas), instance validation silently changes semantics.
This test fails the moment the three disagree.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
VALIDATOR_SRC = ROOT / "scripts" / "validation" / "validate_schema.py"
README = ROOT / "README.md"

# Draft markers that would indicate a drift away from Draft 7.
_WRONG_DRAFT_URIS = ("draft/2020-12", "draft/2019-09", "draft-06", "draft-04")
_WRONG_VALIDATOR_CLASSES = ("Draft202012Validator", "Draft201909Validator", "Draft6Validator", "Draft4Validator")
_WRONG_README_PHRASES = ("Draft 2020-12", "Draft 2019-09", "2019-09", "Draft 6", "Draft 4")


@pytest.mark.parametrize("schema_path", sorted(SCHEMAS_DIR.glob("*.schema.json")))
def test_every_schema_declares_draft07(schema_path: Path) -> None:
    """(1) Each schemas/*.schema.json must declare $schema = draft-07."""
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    declared = data.get("$schema", "")
    assert "draft-07" in declared, (
        f"{schema_path.name} declares $schema={declared!r}; expected a draft-07 URI"
    )
    for wrong in _WRONG_DRAFT_URIS:
        assert wrong not in declared, f"{schema_path.name} declares a non-Draft-7 $schema: {declared!r}"


def test_schemas_count_matches_lock_set() -> None:
    """Sanity: the parametrized lock actually covers the full schema set.

    History: 26 by AMO batch 4d (schemas/schedule.schema.json, D10 count-guard);
    bumped 26 -> 28 by the 2026-06-10 unified remediation — GAP-M-1a adds
    schemas/google-update-calendar.schema.json and GAP-A-B2 adds
    schemas/local-nap.schema.json. (Number-free name: FIX-MFIN consolidates the
    expected value into tests/_count_pins.py at W6; until then this tracks the
    live filesystem count.)"""
    count = len(list(SCHEMAS_DIR.glob("*.schema.json")))
    # 28 -> 29: GAP-M-1b adds schemas/ctr-curve.schema.json (2026-06-10);
    # 29 -> 30: GAP-T1 adds schemas/facet-policy.schema.json (2026-06-10);
    # 30 -> 31: GAP-T2 adds schemas/migration-mapping.schema.json (2026-06-10).
    assert count == 31, f"expected 31 *.schema.json files, found {count}"


def test_validator_pins_draft7() -> None:
    """(2) validate_schema.py must use Draft7Validator and no other draft class."""
    src = VALIDATOR_SRC.read_text(encoding="utf-8")
    assert "Draft7Validator" in src, "validate_schema.py must use Draft7Validator"
    for wrong in _WRONG_VALIDATOR_CLASSES:
        assert wrong not in src, f"validate_schema.py references {wrong}; expected Draft7Validator only"


def test_readme_says_draft7() -> None:
    """(3) README.md must describe the schema draft as Draft 7 and nothing else."""
    text = README.read_text(encoding="utf-8")
    assert "Draft 7" in text, "README.md must state 'Draft 7'"
    for wrong in _WRONG_README_PHRASES:
        assert wrong not in text, f"README.md mentions {wrong!r}; expected only 'Draft 7'"
