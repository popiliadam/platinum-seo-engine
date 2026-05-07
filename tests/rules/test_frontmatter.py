"""Regression: every rules/*.md MUST have valid frontmatter per
schemas/rules-frontmatter.schema.json (H-A v1.4-deep-audit-fix Tier 2).

Locks the four-pattern drift discovered in audit
docs/audits/v1.4-rules-schemas-templates-2026-05-07.md (H-A):
- status enum (enforced vs Active mix)
- applies_to vs applied_to typo
- spec_section presence
- applied_to_skills (optional alias of legacy applied_to)
"""
import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).parent.parent.parent
RULES_DIR = ROOT / "rules"
SCHEMA_PATH = ROOT / "schemas" / "rules-frontmatter.schema.json"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _load_frontmatter(rule_path: Path):
    text = rule_path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    return yaml.safe_load(m.group(1))


@pytest.mark.parametrize("rule_path", sorted(RULES_DIR.glob("*.md")))
def test_rule_has_frontmatter(rule_path):
    """Every rules/*.md MUST start with --- YAML --- frontmatter block."""
    fm = _load_frontmatter(rule_path)
    assert fm is not None, f"{rule_path.name}: no YAML frontmatter found"


@pytest.mark.parametrize("rule_path", sorted(RULES_DIR.glob("*.md")))
def test_rule_frontmatter_valid(rule_path):
    """Every rules/*.md frontmatter MUST validate against
    schemas/rules-frontmatter.schema.json."""
    fm = _load_frontmatter(rule_path)
    assert fm is not None, f"{rule_path.name}: no frontmatter"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(fm, schema)


def test_schema_self_validates():
    """rules-frontmatter.schema.json itself MUST be a valid Draft-07 schema."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
