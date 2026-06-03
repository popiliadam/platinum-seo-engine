"""P1-04: a legacy event missing event_kind must yield a CLEAN root error.

The events schema's allOf conditionals key off event_kind via
``if: {properties: {event_kind: {const: ...}}}``. JSON Schema ``properties``
does not constrain ABSENT keys, so when event_kind is missing every ``if`` is
vacuously satisfied and every ``then`` fires — flooding the caller with
branch-specific "'X' is a required property" errors (run_id, task_id,
audit_action, workflow_action, ...) that are all irrelevant. The single real
problem is the missing discriminator itself (root ``required``).

Locks: (a) a missing-event_kind event produces ONLY the root event_kind error,
no branch noise; (b) the schema description names FOUR kinds (the enum is
provenance/work/audit/workflow), not "Three".
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "schemas" / "events.schema.json"

# Fields that only a *branch* (then) would require — none should be complained
# about when the discriminator itself is what's missing.
BRANCH_FIELDS = (
    "run_id", "source", "operation",          # provenance
    "event_type", "task_id",                  # work
    "audit_action", "audit_target", "actor",  # audit
    "workflow_action", "workflow_run_id",     # workflow
    "url", "url_normalized", "before", "after", "pillar", "cluster", "note",  # work sub-conditionals
)

# A valid common envelope EXCEPT the missing event_kind discriminator.
LEGACY_EVENT = {
    "schema_version": "1.0",
    "event_id": "evt-001",
    "timestamp": "2026-06-03T00:00:00Z",
    "project_id": "demo",
}


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _errors(event: dict) -> list:
    return list(Draft7Validator(_load_schema()).iter_errors(event))


def test_missing_event_kind_is_the_only_error() -> None:
    errors = _errors(LEGACY_EVENT)
    messages = [e.message for e in errors]
    assert any("event_kind" in m for m in messages), f"expected an event_kind required error; got {messages}"
    # No branch-specific field may be complained about when event_kind is absent.
    for field in BRANCH_FIELDS:
        offending = [m for m in messages if f"'{field}'" in m]
        assert not offending, f"branch noise for {field!r}: {offending}"
    # The single real problem is the missing discriminator — nothing else.
    assert len(errors) == 1, f"expected exactly one (clean) error, got {len(errors)}: {messages}"


def test_valid_event_per_kind_still_validates() -> None:
    """Guard: adding required:[event_kind] to the ifs must NOT break well-formed
    events of each kind (the branches must still fire when event_kind is present)."""
    validator = Draft7Validator(_load_schema())
    work = {
        "schema_version": "1.0", "event_kind": "work", "event_id": "content_new_T-0001",
        "timestamp": "2026-06-03T00:00:00Z", "project_id": "demo",
        "event_type": "tech_fix", "task_id": "T-0001",
        "url": "https://example.com/p", "url_normalized": "https://example.com/p",
    }
    assert not list(validator.iter_errors(work)), "well-formed work event must validate"
    workflow = {
        "schema_version": "1.0", "event_kind": "workflow", "event_id": "wf-001",
        "timestamp": "2026-06-03T00:00:00Z", "project_id": "demo",
        "workflow_action": "started", "workflow_run_id": "demo-2026-06-03-ab12",
    }
    assert not list(validator.iter_errors(workflow)), "well-formed workflow event must validate"


def test_description_says_four_kinds() -> None:
    desc = _load_schema()["description"]
    assert "Three kinds" not in desc, "description still says 'Three kinds'"
    assert "Four kinds" in desc, "description must say 'Four kinds'"
    assert "workflow" in desc, "description must mention the 4th kind 'workflow'"
