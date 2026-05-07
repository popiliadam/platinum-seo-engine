"""Regression: events.schema.json MUST expose central pattern definitions.

H-C from docs/audits/v1.4-rules-schemas-templates-2026-05-07.md:
"Pattern duplication (no central $ref) — T-NNNN 3 yerde, sha256 5 yerde,
kebab slug 6 yerde, pillar 2 yerde, workflow_run_id 2 yerde literal kopya."

Tier 1 Step 6 fix: events.schema.json definitions block exposes 5 canonical
patterns. Bare-pattern uses (no description sibling) are migrated to $ref;
description-bearing uses (5 instances) preserve their literals because
Draft-07 ignores siblings to $ref.
"""
import json
from pathlib import Path

import pytest

EVENTS = Path(__file__).parent.parent.parent / "schemas" / "events.schema.json"


def _load():
    with EVENTS.open() as f:
        return json.load(f)


@pytest.mark.parametrize(
    "name,pattern",
    [
        ("taskIdPattern", r"^T-[0-9]{4,}$"),
        ("sha256Hash", r"^sha256:[a-f0-9]{64}$"),
        ("slugKebab", r"^[a-z][a-z0-9-]*$"),
        ("pillarPattern", r"^P[0-9]+_[a-z_]+$"),
        ("workflowRunIdPattern", r"^[a-z][a-z0-9-]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{4}$"),
    ],
)
def test_definition_exists(name, pattern):
    """events.schema.json definitions/<name> MUST exist with correct pattern."""
    data = _load()
    defs = data.get("definitions", {})
    assert name in defs, f"events.schema.json definitions/{name} missing"
    assert defs[name].get("pattern") == pattern, (
        f"definitions/{name}.pattern={defs[name].get('pattern')!r} != {pattern!r}"
    )
    assert defs[name].get("type") == "string"


def test_bare_sha256_uses_ref():
    """Bare sha256 properties (no description sibling) MUST use $ref."""
    text = EVENTS.read_text()
    # Bare pattern: { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" }
    # After fix: { "$ref": "#/definitions/sha256Hash" }
    bare_lit = '{ "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" }'
    assert bare_lit not in text, (
        f"Bare sha256 literal still present in events.schema.json. "
        f"Expected migration to $ref: #/definitions/sha256Hash."
    )
