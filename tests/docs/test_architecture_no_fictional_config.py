"""Guard: ARCHITECTURE.md must not cite project.config.json fields that the
schema does not define (additionalProperties:false would reject them anyway).

Codex P1-05: 'plugin_version_constraint' is fictional — never in schema, never
in any of the 10 workspace configs, referenced only in docs. The real field
projects carry is 'schema_version'.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_architecture_does_not_cite_plugin_version_constraint() -> None:
    arch = (ROOT / "docs/ARCHITECTURE.md").read_text()
    schema = json.loads((ROOT / "schemas/project-config.schema.json").read_text())
    allowed = set(schema.get("properties", {}).keys())
    assert "plugin_version_constraint" not in allowed  # sanity: still fictional
    assert "plugin_version_constraint" not in arch, (
        "ARCHITECTURE.md cites 'plugin_version_constraint', which is not a real "
        "project.config.json field (not in schema; additionalProperties:false). "
        "Cite 'schema_version' (the field configs actually carry) instead."
    )
