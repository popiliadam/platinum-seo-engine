"""Regression: ADR-012 + naming.md → schema $id MUST be:
- HTTP scheme (not HTTPS) — history-stable URI
- /schemas/ path (not /templates/) — file location authoritative
- slug-only (no .schema.json suffix) — naming.md example

Source: rules/naming.md "Schema $id: http://platinum-seo-engine/schemas/<name> (HTTP, ADR-012)"
Audit: docs/audits/v1.4-rules-schemas-templates-2026-05-07.md K-02
Brief: docs/superpowers/plans/v1.4-deep-audit-fix-brief.md Tier 1 Step 2
"""
import json
import re
from pathlib import Path

import pytest

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"
EXPECTED_PATTERN = re.compile(r"^http://platinum-seo-engine/schemas/[a-z][a-z0-9-]*$")


@pytest.mark.parametrize(
    "schema_path",
    sorted(SCHEMAS_DIR.glob("*.schema.json")),
    ids=lambda p: p.name,
)
def test_schema_id_format(schema_path):
    """Each *.schema.json file MUST have $id matching ADR-012 + naming.md format."""
    with schema_path.open() as f:
        data = json.load(f)
    schema_id = data.get("$id")
    assert schema_id is not None, (
        f"{schema_path.name}: $id field missing (rules/schema-first.md + naming.md ADR-012)"
    )
    assert EXPECTED_PATTERN.match(schema_id), (
        f"{schema_path.name}: $id={schema_id!r} does not match "
        f"ADR-012 + naming.md format http://platinum-seo-engine/schemas/<slug>"
    )
