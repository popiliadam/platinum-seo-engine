"""Regression: every *.schema.json MUST have schema_version coverage.

Per rules/schema-versioning-discipline.md, every schema MUST expose
schema_version (either as top-level metadata for instance documents,
or under properties for validating schemas).

H-B from docs/audits/v1.4-rules-schemas-templates-2026-05-07.md:
- project-memory + skill-frontmatter: schema_version field HİÇ YOK (FAIL)
- portfolio-config: properties.schema_version uses pattern (loose) — should be const

Note: schema_version is NOT enforced as required[] for validating schemas
(would break 28 existing SKILL.md instances). The field is OPTIONAL in
properties, MANDATORY in const definition. Future major bump may require it.
"""
import json
from pathlib import Path

import pytest

SCHEMAS = Path(__file__).parent.parent.parent / "schemas"


@pytest.mark.parametrize(
    "schema_path",
    sorted(SCHEMAS.glob("*.schema.json")),
    ids=lambda p: p.name,
)
def test_schema_version_coverage(schema_path):
    """schema_version MUST appear either top-level (instance doc) or in properties."""
    with schema_path.open() as f:
        data = json.load(f)
    has_top_level = "schema_version" in data and not isinstance(data.get("properties"), dict) is None
    has_top_data = isinstance(data.get("schema_version"), str)
    has_property = "schema_version" in data.get("properties", {})
    assert has_top_data or has_property, (
        f"{schema_path.name}: schema_version coverage missing. "
        f"Per rules/schema-versioning-discipline.md, every schema MUST "
        f"expose schema_version (top-level for instance docs, "
        f"or under properties for validating schemas)."
    )


@pytest.mark.parametrize(
    "schema_path",
    sorted(SCHEMAS.glob("*.schema.json")),
    ids=lambda p: p.name,
)
def test_schema_version_uses_const(schema_path):
    """If properties.schema_version exists, it MUST use const (not pattern) for strict validation."""
    with schema_path.open() as f:
        data = json.load(f)
    sv = data.get("properties", {}).get("schema_version")
    if sv is None:
        pytest.skip("Top-level schema_version metadata (no instance constraint)")
    assert "const" in sv, (
        f"{schema_path.name}: properties.schema_version uses non-const validation "
        f"({list(sv.keys())}). Use const for strict version match per ADR-018."
    )
