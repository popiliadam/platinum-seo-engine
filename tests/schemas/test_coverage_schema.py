"""Instance-validation lock for schemas/coverage.schema.json (AMO batch 1a).

The coverage record is the INDEPENDENT per-run proof the AMO orchestrator
(run_step.py, batch 1b) writes to projects/{slug}/_state/coverage/{run_id}.json
and the denetçi Stop-hook (batch 2c) + correctness oracle read to decide
pass / block / paused. Lives OUTSIDE events.jsonl on purpose (event_type is a
closed exactly-12 enum, spec D3).

This test FREEZES the contract downstream batches 1b/2c key on literally:
the required[] set, the verdict + verification_class + step-status enums, the
run_id grammar (shared 1:1 with workflow-run.schema.json), and
additionalProperties:false at both the record and step levels.

Mirrors tests/schemas/test_instance_validation.py's Draft7Validator usage.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_SCHEMA_PATH = ROOT / "schemas" / "coverage.schema.json"


def _errors(instance: dict) -> list:
    """Return the (possibly empty) list of Draft7 validation errors."""
    schema = json.loads(COVERAGE_SCHEMA_PATH.read_text(encoding="utf-8"))
    return list(jsonschema.Draft7Validator(schema).iter_errors(instance))


# ---------------------------------------------------------------------------
# Valid cases
# ---------------------------------------------------------------------------

def test_fully_populated_record_validates() -> None:
    """A complete record — 2 steps (one code_verified/satisfied with observed_mcp
    + input/scored counts, one model_attested/running), required_satisfied:true,
    verdict:'pass', schema_version '1.0' — validates with ZERO errors."""
    record = {
        "schema_version": "1.0",
        "run_id": "demo-furniture-2026-06-05-a1b2",
        "project_slug": "demo-furniture",
        "engine_version": "1.9.5",
        "steps": [
            {
                "name": "fetch_gsc",
                "verification_class": "code_verified",
                "status": "satisfied",
                "observed_mcp": ["mcp__gsc__search_analytics"],
                "input_count": 120,
                "scored_count": 118,
            },
            {
                "name": "generate_blog",
                "verification_class": "model_attested",
                "status": "running",
            },
        ],
        "required_satisfied": True,
        "verdict": "pass",
        "created_at": "2026-06-05T10:00:00Z",
        "updated_at": "2026-06-05T10:05:00Z",
    }
    assert _errors(record) == []


def test_minimal_record_validates() -> None:
    """The minimal denetçi record {run_id, steps:[], required_satisfied:false,
    verdict:'incomplete'} validates — steps may be empty (minItems:0) and the
    optional metadata fields are absent."""
    record = {
        "run_id": "demo-furniture-2026-06-05-a1b2",
        "steps": [],
        "required_satisfied": False,
        "verdict": "incomplete",
    }
    assert _errors(record) == []


# ---------------------------------------------------------------------------
# Invalid cases (every other field is valid so the single defect is isolated)
# ---------------------------------------------------------------------------

def test_unknown_verification_class_rejected() -> None:
    """verification_class is a closed 2-value enum (code_verified|model_attested);
    'guessed' must be rejected — the <=5% oracle relies on this discrimination."""
    record = {
        "run_id": "demo-furniture-2026-06-05-a1b2",
        "steps": [
            {"name": "x", "verification_class": "guessed", "status": "satisfied"}
        ],
        "required_satisfied": False,
        "verdict": "incomplete",
    }
    assert _errors(record) != []


def test_unknown_verdict_rejected() -> None:
    """verdict is a closed 4-value enum (pass|incomplete|paused|failed); the
    denetçi keys on it, so 'green' is not a legal verdict."""
    record = {
        "run_id": "demo-furniture-2026-06-05-a1b2",
        "steps": [],
        "required_satisfied": True,
        "verdict": "green",
    }
    assert _errors(record) != []


def test_unknown_top_level_key_rejected() -> None:
    """additionalProperties:false — an undeclared top-level key must be rejected
    so downstream batches can trust the frozen shape."""
    record = {
        "run_id": "demo-furniture-2026-06-05-a1b2",
        "steps": [],
        "required_satisfied": True,
        "verdict": "pass",
        "surprise": "nope",
    }
    assert _errors(record) != []


def test_malformed_run_id_rejected() -> None:
    """run_id reuses workflow-run.schema.json's grammar so a coverage record
    joins 1:1 to its run; 'not-a-run-id' fails the
    {slug}-YYYY-MM-DD-{hash4} pattern."""
    record = {
        "run_id": "not-a-run-id",
        "steps": [],
        "required_satisfied": True,
        "verdict": "pass",
    }
    assert _errors(record) != []
