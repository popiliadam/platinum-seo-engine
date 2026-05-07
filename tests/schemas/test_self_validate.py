"""Regression: every schemas/*.json MUST be a valid JSON Schema Draft-07.

Locks Q-V1.4-AUDIT-GOVERNANCE-01 jsonschema runtime self-validate gap
(brief T4 Step 1; previously deferred per audit "Doğrulanmadı" list).
Catches structural schema authoring mistakes (missing required, invalid
enum types, malformed $ref, etc.) BEFORE they hit instance validation.
"""
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = ROOT / "schemas"


@pytest.mark.parametrize("schema_path", sorted(SCHEMAS_DIR.glob("*.json")))
def test_schema_self_validates_draft7(schema_path):
    """Each schemas/*.json MUST pass Draft7Validator.check_schema."""
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(data)
