"""Regression: workspace-bound instance files (events.jsonl, master.xlsx
sheets) MUST validate against their schema.

Locks Q-V1.4-AUDIT-GOVERNANCE-01 instance file validation gap (brief T4
Step 2; previously deferred per audit "Doğrulanmadı" list).

Skipped on plugin-only CI runs where PSEO_WORKSPACE_ROOT is unset (no
workspace state to validate). Plugin agnostiklik (ADR-008) preserved:
test only fires when an env-bound workspace is present.
"""
import json
import os
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).parent.parent.parent
EVENTS_SCHEMA_PATH = ROOT / "schemas" / "events.schema.json"

WORKSPACE_ROOT = os.environ.get("PSEO_WORKSPACE_ROOT")
WORKSPACE_PATH = Path(WORKSPACE_ROOT) if WORKSPACE_ROOT else None


def _events_jsonl_paths():
    """Discover all events.jsonl files under workspace projects."""
    if not WORKSPACE_PATH or not WORKSPACE_PATH.exists():
        return []
    return sorted(WORKSPACE_PATH.glob("projects/*/_state/events.jsonl"))


@pytest.mark.skipif(
    not WORKSPACE_PATH or not WORKSPACE_PATH.exists(),
    reason="PSEO_WORKSPACE_ROOT unset or workspace missing — plugin-only run",
)
@pytest.mark.parametrize("events_path", _events_jsonl_paths())
def test_events_jsonl_validates(events_path):
    """Each non-empty line in events.jsonl MUST validate vs events.schema.json."""
    schema = json.loads(EVENTS_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for lineno, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{events_path}:{lineno} invalid JSON: {exc.msg}")
        errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
        assert not errors, (
            f"{events_path}:{lineno} schema validation errors:\n"
            + "\n".join(f"  - {e.message}" for e in errors[:5])
        )
