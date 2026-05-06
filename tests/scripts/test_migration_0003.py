"""tests/scripts/test_migration_0003.py — Migration 0003 (project.config.json
1.2 → 1.3) — ADR-030 brand_identity field rename forward.

Coverage:
  1. Pure 1.2 doc with hitap + tone → 1.3 with pronoun_preference + formality
     copied verbatim (values preserved per "workspace KORUNUR").
  2. Partial-migration state (workspace eca13c5: pronoun_preference + formality
     already present) → version bump only, no key remap.
  3. Idempotent — re-running on a 1.3 doc returns it unchanged.
  4. Out-of-range schema_version raises ValueError (silent rewrite forbidden).
  5. Missing brand_identity block → version bump only, no error.
  6. Workspace dentnotion fixture validates against schema 1.3 after migration.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO / "scripts" / "migrations" / "0003_project_config_1.2_to_1.3.py"
SCHEMA_PATH = REPO / "schemas" / "project-config.schema.json"


@pytest.fixture(scope="module")
def migration_module():
    spec = importlib.util.spec_from_file_location("m_0003", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def schema_v13() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_pure_1_2_doc_renames_hitap_and_tone(migration_module) -> None:
    """A 1.2 doc with hitap + tone gets pronoun_preference + formality
    populated verbatim while the legacy keys are retained as deprecated
    aliases."""
    doc = {
        "schema_version": "1.2",
        "brand_identity": {
            "logo_url": "https://example.com/logo.png",
            "hitap": "siz",
            "tone": "semi-pro",
        },
    }
    out = migration_module.migrate(doc)
    assert out["schema_version"] == "1.3"
    bi = out["brand_identity"]
    # Canonical fields populated.
    assert bi["pronoun_preference"] == "siz"
    assert bi["formality"] == "semi-pro"
    # Legacy aliases retained — deprecation, not removal.
    assert bi["hitap"] == "siz"
    assert bi["tone"] == "semi-pro"


def test_partial_migration_state_only_bumps_version(migration_module) -> None:
    """Workspace eca13c5 state: canonical keys present with old values.
    Migration 0003 only bumps schema_version; values are preserved."""
    doc = {
        "schema_version": "1.2",
        "brand_identity": {
            "pronoun_preference": "siz",
            "formality": "semi-pro",
        },
    }
    out = migration_module.migrate(doc)
    assert out["schema_version"] == "1.3"
    assert out["brand_identity"]["pronoun_preference"] == "siz"
    assert out["brand_identity"]["formality"] == "semi-pro"
    # No legacy alias injected (schema-first, only rename old → new).
    assert "hitap" not in out["brand_identity"]
    assert "tone" not in out["brand_identity"]


def test_idempotent_on_1_3(migration_module) -> None:
    """Re-running on a 1.3 doc returns it unchanged."""
    doc = {
        "schema_version": "1.3",
        "brand_identity": {"pronoun_preference": "siz", "formality": "professional"},
    }
    out = migration_module.migrate(doc)
    assert out == doc


def test_refuses_out_of_range_version(migration_module) -> None:
    """1.0 / 1.1 / 2.0 / unknown — silent rewrite forbidden."""
    for sv in ("1.0", "1.1", "2.0", "draft", None):
        with pytest.raises(ValueError):
            migration_module.migrate({"schema_version": sv})


def test_missing_brand_identity_block(migration_module) -> None:
    """A 1.2 doc without a brand_identity block bumps version only."""
    doc = {"schema_version": "1.2", "project_id": "alpha"}
    out = migration_module.migrate(doc)
    assert out["schema_version"] == "1.3"
    assert "brand_identity" not in out


def test_partial_keys_only_hitap(migration_module) -> None:
    """Only hitap set (no tone) → pronoun_preference populated, formality
    untouched (key absent)."""
    doc = {
        "schema_version": "1.2",
        "brand_identity": {"hitap": "sen"},
    }
    out = migration_module.migrate(doc)
    bi = out["brand_identity"]
    assert bi["pronoun_preference"] == "sen"
    assert bi["hitap"] == "sen"
    assert "formality" not in bi
    assert "tone" not in bi


def test_no_overwrite_when_canonical_already_present(migration_module) -> None:
    """If both legacy and canonical keys exist, canonical wins (skill
    intent: legacy is being phased out)."""
    doc = {
        "schema_version": "1.2",
        "brand_identity": {
            "hitap": "sen",
            "pronoun_preference": "siz",
            "tone": "casual",
            "formality": "professional",
        },
    }
    out = migration_module.migrate(doc)
    bi = out["brand_identity"]
    assert bi["pronoun_preference"] == "siz", "canonical must NOT be overwritten"
    assert bi["formality"] == "professional"


def test_workspace_fixture_validates_after_migration(
    migration_module, schema_v13: dict
) -> None:
    """End-to-end smoke: a doc shaped like the dentnotion workspace
    (post-eca13c5) migrates to 1.3 and validates clean against the
    bumped schema."""
    fixture = {
        "schema_version": "1.2",
        "project_id": "dentnotion",
        "domain": "https://dentnotion.com/",
        "market": "TR",
        "language": {"content_locale": "tr-TR"},
        "currency": "TRY",
        "platform": "wordpress",
        "profiles": ["ymyl", "local-service"],
        "paths": {
            "workspace_root": "~/Documents/platinum-seo-workspace/projects/dentnotion",
            "excel_filename": "master.xlsx",
            "sf_exports_dir": "inbox/sf",
            "staging_dir": "_state/cache",
            "reports_dir": "outputs/reports",
            "blog_dir": "outputs/content/drafts",
            "backups_dir": "_state/backups",
        },
        "gsc": {"site_url": "https://dentnotion.com/"},
        "dataforseo": {"location_code": 2792, "language_code": "tr"},
        "brand_identity": {
            "pronoun_preference": "siz",
            "formality": "semi-pro",
        },
    }
    migrated = migration_module.migrate(fixture)
    errors = list(Draft7Validator(schema_v13).iter_errors(migrated))
    assert not errors, (
        "post-migration doc must validate against schema 1.3:\n"
        + "\n".join(f"  - {e.message}" for e in errors)
    )
