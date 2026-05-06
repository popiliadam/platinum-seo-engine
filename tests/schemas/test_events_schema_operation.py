"""tests/schemas/test_events_schema_operation.py — operation enum gate.

Wave 3 Task 3.5 (Q-WAVE2-DFS-OP-STAGING-01): events.schema's
``operation`` enum is additively bumped to include ``"staging"`` so the
Phase 6 D-003 pre-Excel staging routing surface can emit valid
provenance entries (`skills/ingestion/dfs-pull/SKILL.md:299`).

This test locks the additive contract:
  - all 5 prior values remain accepted (no regression);
  - the new ``"staging"`` value is accepted;
  - no other arbitrary value is accepted (enum-closed).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "schemas" / "events.schema.json"

EXPECTED_VALUES = (
    "ingest",
    "normalize",
    "project_excel",
    "validate",
    "cascade_done",
    "staging",  # Wave 3 additive (ADR-018 paterni)
)


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _operation_enum() -> list[str]:
    schema = _load_schema()
    field = schema["properties"]["operation"]
    return list(field.get("enum", []))


def _provenance_event(operation: str) -> dict:
    """Minimal provenance event template for schema validation."""
    return {
        "schema_version": "1.0",
        "event_kind": "provenance",
        "ts": "2026-05-06T10:00:00.000Z",
        "actor": "test",
        "project_id": "test_project",
        "run_id": 1,
        "source": {
            "kind": "dataforseo_mcp",
            "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_overview",
            "response_bytes": 100,
        },
        "operation": operation,
        "target_excel_sheet": None,
        "rows_written": 0,
    }


def test_operation_enum_contains_all_expected_values() -> None:
    enum = _operation_enum()
    for v in EXPECTED_VALUES:
        assert v in enum, f"operation enum missing {v!r}; got {enum}"


def test_operation_enum_is_closed() -> None:
    """The enum is the contract — no extras leak in via additive drift."""
    enum = _operation_enum()
    assert sorted(enum) == sorted(EXPECTED_VALUES), (
        f"operation enum drift detected; expected {sorted(EXPECTED_VALUES)}, "
        f"got {sorted(enum)}"
    )


@pytest.mark.parametrize("op", EXPECTED_VALUES)
def test_each_enum_value_validates_in_provenance_event(op: str) -> None:
    """Every accepted operation value MUST produce a schema-valid event."""
    validator = Draft7Validator(_load_schema(), format_checker=FormatChecker())
    event = _provenance_event(op)
    errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
    # Some events may fail unrelated constraints; we only care that the
    # operation field itself is not the rejecter.
    op_path_errors = [e for e in errors if list(e.absolute_path) == ["operation"]]
    assert not op_path_errors, (
        f"operation={op!r} flagged as enum-invalid: "
        + "; ".join(str(e.message) for e in op_path_errors)
    )


def test_unknown_operation_value_rejected() -> None:
    validator = Draft7Validator(_load_schema(), format_checker=FormatChecker())
    event = _provenance_event("not_an_operation")
    errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
    op_path_errors = [e for e in errors if list(e.absolute_path) == ["operation"]]
    assert op_path_errors, (
        "Expected enum rejection for 'not_an_operation' on .operation; "
        f"validator returned {[str(e.message) for e in errors]}"
    )


def test_dfs_pull_skill_uses_canonical_value() -> None:
    """Lock the SKILL.md ↔ schema sync that this Wave 3 fix codifies."""
    skill_path = REPO / "skills" / "ingestion" / "dfs-pull" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    enum = _operation_enum()
    # Find every operation="..." literal and assert it's enum-valid.
    import re
    for m in re.finditer(r'operation\s*=\s*"([^"]+)"', text):
        value = m.group(1)
        assert value in enum, (
            f"dfs-pull SKILL.md uses operation={value!r} not in events.schema "
            f"enum {enum}"
        )
