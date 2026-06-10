"""TDD lock for schemas/migration-mapping.schema.json (GAP-T4).

A NEW standalone, additive Draft-07 schema validating the OPTIONAL operator file
``projects/{slug}/migration/{date}-mapping-rules.json`` (absence = explicit pairs
only). It lets an operator express ordered regex redirect rules (old-URL pattern →
new-URL template) that the migration-map skill expands over the full crawl
inventory. No existing schema is touched; no migration (mirrors the GAP-T2
facet-policy.schema.json precedent). See rules/tech-seo-governance.md R-134.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "migration-mapping.schema.json"


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_valid_draft07() -> None:
    schema = _schema()
    assert "draft-07" in schema.get("$schema", "")
    Draft7Validator.check_schema(schema)
    assert schema.get("schema_version") == "1.0"
    assert schema.get("additionalProperties") is False


def test_valid_rule_doc_passes() -> None:
    doc = {
        "schema_version": "1.0",
        "rules": [
            {"match": "^/old-blog/(.*)$", "replace": "/blog/$1", "action": "301", "order": 1},
            {"match": "^/discontinued/.*$", "replace": "", "action": "410", "order": 2},
        ],
        "defaults": {"unmatched": "flag"},
    }
    assert Draft7Validator(_schema()).is_valid(doc)


def test_minimal_doc_passes() -> None:
    assert Draft7Validator(_schema()).is_valid({"schema_version": "1.0"})


def test_invalid_action_value_rejected() -> None:
    doc = {"schema_version": "1.0",
           "rules": [{"match": "^/x$", "replace": "/y", "action": "302", "order": 1}]}
    assert not Draft7Validator(_schema()).is_valid(doc)


def test_rule_missing_required_field_rejected() -> None:
    # a rule without `action` is incomplete
    doc = {"schema_version": "1.0", "rules": [{"match": "^/x$", "replace": "/y", "order": 1}]}
    assert not Draft7Validator(_schema()).is_valid(doc)


def test_invalid_unmatched_default_rejected() -> None:
    doc = {"schema_version": "1.0", "defaults": {"unmatched": "bogus"}}
    assert not Draft7Validator(_schema()).is_valid(doc)


def test_wrong_schema_version_rejected() -> None:
    assert not Draft7Validator(_schema()).is_valid({"schema_version": "9.9"})


def test_unknown_top_level_key_rejected() -> None:
    assert not Draft7Validator(_schema()).is_valid({"schema_version": "1.0", "bogus_key": True})
