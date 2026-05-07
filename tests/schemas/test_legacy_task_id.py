"""Regression: events.schema.json task_id MUST accept BOTH canonical
T-NNNN format AND legacy MT-WxWyZ-NNN format via oneOf bypass.

Locks H-L audit finding: legacy task IDs (e.g. MT-W3W2B-001) reject by
strict T-NNNN pattern; rules/master-task-id.md declares "transitional
kabul" but events.schema had no bypass. Per H-L closure: schema accepts
canonical OR legacy via definitions/legacyTaskIdPattern $ref.
"""
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "events.schema.json"


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def base_work_event():
    """Minimal valid WORK event envelope for task_id testing."""
    return {
        "schema_version": "1.0",
        "event_kind": "work",
        "event_id": "content_new_T-0042_20260420T1030",
        "timestamp": "2026-04-20T10:30:00Z",
        "project_id": "demo-project",
        "event_type": "manual",
        "note": "test fixture for H-L legacy task_id bypass",
    }


def test_canonical_task_id_accepted(base_work_event):
    """Canonical T-NNNN format MUST validate."""
    schema = _load_schema()
    base_work_event["task_id"] = "T-0042"
    jsonschema.validate(base_work_event, schema)


def test_legacy_task_id_accepted(base_work_event):
    """Legacy MT-WxWyZ-NNN format MUST validate (H-L bypass)."""
    schema = _load_schema()
    base_work_event["task_id"] = "MT-W3W2B-001"
    jsonschema.validate(base_work_event, schema)


def test_legacy_task_id_no_letter_suffix_accepted(base_work_event):
    """Legacy MT-WxWy-NNN (no letter suffix) MUST validate."""
    schema = _load_schema()
    base_work_event["task_id"] = "MT-W3W2-007"
    jsonschema.validate(base_work_event, schema)


def test_invalid_task_id_rejected(base_work_event):
    """Random string MUST reject."""
    schema = _load_schema()
    base_work_event["task_id"] = "random-task-name"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(base_work_event, schema)


def test_legacy_task_id_pattern_in_definitions():
    """Schema MUST define legacyTaskIdPattern in definitions (H-L)."""
    schema = _load_schema()
    legacy = schema.get("definitions", {}).get("legacyTaskIdPattern")
    assert legacy is not None, (
        "events.schema.json definitions/legacyTaskIdPattern missing; "
        "H-L closure requires bypass for legacy MT-WxWyZ-NNN ids."
    )
    assert legacy.get("type") == "string"
    assert "MT-W" in legacy.get("pattern", ""), (
        f"legacyTaskIdPattern must match MT-WxWyZ-NNN; got {legacy.get('pattern')!r}"
    )
