"""tests/schemas/test_local_nap_schema.py — canonical NAP document schema lock.

GAP-A2 (2026-06-10 acquisition spec; unified dispatch batch GAP-A-B2): the
canonical NAP (Name / Address / Phone) source of truth for local-SEO projects
lives at ``projects/{slug}/local/nap.json`` and validates against
``schemas/local-nap.schema.json``. A STANDALONE schema deliberately avoids the
project-config v1.5 -> v1.6 const bump + migration_0006 + live-config
migration cascade (the schema's own description records it as a fold-in
candidate at the next scheduled const bump).

Locked here:
  1. Draft-07 self-validation + ADR-012 $id format
     (http://platinum-seo-engine/schemas/local-nap).
  2. Minimal valid single-location doc PASSES.
  3. Missing required ``phone`` FAILS.
  4. Non-E.164 ``phone`` FAILS — the canonical doc stores strict E.164;
     looser observed surface forms are normalized at COMPARE time by
     ``scripts/discovery/nap_consistency.normalize_phone``, never stored.
  5. Multi-location doc (``locations[]`` keyed by ``location_id``) PASSES —
     multi-location is first-class (multi-branch local-service portfolio
     reality; engine stays project-agnostic).
  6. Unknown top-level AND nested keys FAIL (``additionalProperties: false``
     everywhere — nested-AP discipline per the 2026-06-10 unified plan).

Run from repo root:
    PYTHONPATH=. pytest tests/schemas/test_local_nap_schema.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "local-nap.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _minimal() -> dict:
    """Smallest doc the schema MUST accept (single location, TR project)."""
    return {
        "schema_version": "1.0",
        "business_name": "Örnek Klima Servisi",
        "phone": "+902121234567",
        "address": {"street": "Atatürk Caddesi Numara 5", "city": "İstanbul"},
    }


def test_schema_self_validates_draft7_and_id_format() -> None:
    schema = _schema()
    Draft7Validator.check_schema(schema)
    assert "draft-07" in schema["$schema"]
    assert schema["$id"] == "http://platinum-seo-engine/schemas/local-nap"
    # schema_version is an instance-doc contract field -> const (strict),
    # per rules/schema-versioning-discipline.md.
    assert schema["properties"]["schema_version"] == {
        "const": "1.0",
    } or schema["properties"]["schema_version"].get("const") == "1.0"


def test_minimal_valid_doc_passes() -> None:
    Draft7Validator(_schema()).validate(_minimal())


def test_missing_phone_fails() -> None:
    doc = _minimal()
    del doc["phone"]
    with pytest.raises(ValidationError):
        Draft7Validator(_schema()).validate(doc)


def test_non_e164_phone_fails() -> None:
    doc = _minimal()
    doc["phone"] = "0 (212) 123 45 67"  # valid surface form, NOT canonical E.164
    with pytest.raises(ValidationError):
        Draft7Validator(_schema()).validate(doc)


def test_multi_location_doc_passes() -> None:
    doc = _minimal()
    doc["locations"] = [
        {
            "location_id": "kadikoy",
            "name": "Örnek Klima Kadıköy",
            "phone": "+902165554433",
            "address": {"street": "Bağdat Caddesi Numara 12", "city": "İstanbul"},
            "gbp_place_id": "ChIJexample123",
        },
        # phone/address omitted -> fall back to top-level NAP at compare time
        {"location_id": "izmir", "name": "Örnek Klima İzmir"},
    ]
    doc["source_pages"] = ["https://example.com/iletisim"]
    Draft7Validator(_schema()).validate(doc)


def test_unknown_top_level_key_fails() -> None:
    doc = _minimal()
    doc["UNKNOWN_FIELD"] = "x"
    with pytest.raises(ValidationError):
        Draft7Validator(_schema()).validate(doc)


def test_unknown_nested_address_key_fails() -> None:
    doc = _minimal()
    doc["address"]["UNKNOWN_FIELD"] = "x"
    with pytest.raises(ValidationError):
        Draft7Validator(_schema()).validate(doc)


def test_location_entry_requires_id_and_name() -> None:
    doc = _minimal()
    doc["locations"] = [{"phone": "+902165554433"}]  # no location_id, no name
    with pytest.raises(ValidationError):
        Draft7Validator(_schema()).validate(doc)
