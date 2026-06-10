"""TDD lock for schemas/facet-policy.schema.json (GAP-T2).

A NEW standalone, additive Draft-07 schema validating the OPTIONAL per-project
override file ``projects/{slug}/config/facet-policy.json`` (absence = engine
defaults). It lets an operator pin project-specific / non-English parameter
vocabularies the engine cannot verify (Ticimax/Ideasoft/imagaza) into the R-128
taxonomy, winning over the transform's heuristic seeds. No existing schema is
touched; no migration.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "facet-policy.schema.json"


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_valid_draft07() -> None:
    schema = _schema()
    assert "draft-07" in schema.get("$schema", "")
    Draft7Validator.check_schema(schema)
    assert schema.get("schema_version") == "1.0"
    assert schema.get("additionalProperties") is False


def test_valid_override_doc_passes() -> None:
    doc = {
        "schema_version": "1.0",
        "classifications": {
            "sirala": "sort",
            "arama": "internal_search",
            "renk": "facet_filter",
        },
        "indexable_facets": ["renk"],
        "notes": "Turkish Ticimax vocabulary, operator-confirmed 2026-06-10.",
    }
    assert Draft7Validator(_schema()).is_valid(doc)


def test_minimal_override_doc_passes() -> None:
    assert Draft7Validator(_schema()).is_valid({"schema_version": "1.0"})


def test_invalid_class_value_rejected() -> None:
    doc = {"schema_version": "1.0", "classifications": {"sirala": "NOT_A_CLASS"}}
    assert not Draft7Validator(_schema()).is_valid(doc)


def test_wrong_schema_version_rejected() -> None:
    assert not Draft7Validator(_schema()).is_valid({"schema_version": "9.9"})


def test_unknown_top_level_key_rejected() -> None:
    doc = {"schema_version": "1.0", "bogus_key": True}
    assert not Draft7Validator(_schema()).is_valid(doc)
