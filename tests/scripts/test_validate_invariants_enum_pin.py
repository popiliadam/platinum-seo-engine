"""tests/scripts/test_validate_invariants_enum_pin.py — deep-audit 2026-06-04.

validate_invariants.py keeps hand-written frozenset copies of the schema's
statusEnum/severityEnum (a deliberate no-schema-dependency safety for the
read-only checker). These tests PIN those copies to the schema SSoT
(schemas/master-excel.schema.json) so the next additive enum bump
(ADR-018 paterni) fails CI here until the hardcoded copies are updated — a
drift-checker must not silently drift from the schema it guards.

Cross-reference: scripts/validation/validate_invariants.py
(_STATUS_ENUM_7, _SEVERITY_ENUM_4, check_F_01, check_F_17).
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import validate_invariants as vi

REPO = Path(__file__).resolve().parents[2]
_DEFS = json.loads(
    (REPO / "schemas" / "master-excel.schema.json").read_text(encoding="utf-8")
)["definitions"]


def test_status_enum_pinned_to_schema() -> None:
    assert set(vi._STATUS_ENUM_7) == set(_DEFS["statusEnum"]["enum"]), (
        "validate_invariants._STATUS_ENUM_7 drifted from schema statusEnum — "
        "update the hardcoded copy after an additive bump (ADR-018 paterni)."
    )


def test_severity_enum_pinned_to_schema() -> None:
    assert set(vi._SEVERITY_ENUM_4) == set(_DEFS["severityEnum"]["enum"]), (
        "validate_invariants._SEVERITY_ENUM_4 drifted from schema severityEnum — "
        "update the hardcoded copy after an additive bump."
    )
