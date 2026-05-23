"""Migration 0004 — project-config schema v1.3 → v1.4 enrichment tests.

Covers ``scripts/migrations/migration_0004_project_config_1_3_to_1_4.migrate``:
  1. ``schema_version`` bumps "1.3" → "1.4".
  2. Pre-existing bank entries get four new fields injected with defaults
     while leaving existing keys intact.
  3. Idempotent on already-v1.4 input (no-op).
  4. Unrelated keys (image_model, profiles, project_id) preserved.
  5. Out-of-range source schema_version refused with ValueError.

The migration is *additive* — it never deletes or mutates existing values;
empty banks (the current state on all 9 projects) survive untouched as
empty lists with the new fields ready to receive Stage C writes from
``brand-onboarding`` (Task 3.4).
"""

from __future__ import annotations

import pytest

from scripts.migrations.migration_0004_project_config_1_3_to_1_4 import migrate


def test_migration_bumps_schema_version() -> None:
    src = {"schema_version": "1.3", "project_id": "test", "profiles": ["ymyl"]}
    out = migrate(src)
    assert out["schema_version"] == "1.4"


def test_migration_preserves_existing_bank_entries_with_new_fields() -> None:
    """Pre-existing bank entries (rare — most projects empty) survive intact;
    each entry gets four new fields injected with safe defaults."""
    src = {
        "schema_version": "1.3",
        "project_id": "test",
        "profiles": ["ymyl"],
        "content_settings": {
            "experience_database": [
                {"id": "old-001", "claim_core": "10 yıl tecrübe", "evidence_url": "https://example.com"},
            ],
        },
    }
    out = migrate(src)
    bank = out["content_settings"]["experience_database"]
    assert len(bank) == 1
    entry = bank[0]
    # Existing keys preserved verbatim
    assert entry["id"] == "old-001"
    assert entry["claim_core"] == "10 yıl tecrübe"
    assert entry["evidence_url"] == "https://example.com"
    # Four new fields injected with documented defaults
    assert entry["applicable_topics"] == []
    assert entry["phrasings"] == []
    assert entry["last_used_in_content_id"] is None
    assert entry["max_usage_per_month"] == 3


def test_migration_enriches_research_database_entries() -> None:
    """original_research_database entries get the same four-field enrichment."""
    src = {
        "schema_version": "1.3",
        "project_id": "test",
        "profiles": ["b2b-saas"],
        "content_settings": {
            "original_research_database": [
                {"id": "res-001", "title": "2026 industry survey", "url": "https://example.com/survey"},
            ],
        },
    }
    out = migrate(src)
    bank = out["content_settings"]["original_research_database"]
    assert len(bank) == 1
    entry = bank[0]
    assert entry["title"] == "2026 industry survey"
    assert entry["applicable_topics"] == []
    assert entry["max_usage_per_month"] == 3
    assert entry["last_used_in_content_id"] is None


def test_migration_idempotent_on_v1_4() -> None:
    """Running migrate() against an already-v1.4 doc is a no-op."""
    src = {"schema_version": "1.4", "project_id": "test", "profiles": ["e-commerce"]}
    out = migrate(src)
    assert out["schema_version"] == "1.4"
    # Returns the doc unchanged (identity is acceptable for idempotent no-op)
    assert out == src


def test_migration_preserves_unrelated_fields() -> None:
    """Unrelated keys (project_id, profiles, content_settings.image_model) survive."""
    src = {
        "schema_version": "1.3",
        "project_id": "test",
        "profiles": ["e-commerce"],
        "content_settings": {"image_model": "nano-banana"},
    }
    out = migrate(src)
    assert out["project_id"] == "test"
    assert out["profiles"] == ["e-commerce"]
    assert out["content_settings"]["image_model"] == "nano-banana"


def test_migration_creates_empty_banks_when_missing() -> None:
    """Project with no content_settings gets the keys created with empty arrays."""
    src = {"schema_version": "1.3", "project_id": "test", "profiles": ["ymyl"]}
    out = migrate(src)
    cs = out["content_settings"]
    assert cs["experience_database"] == []
    assert cs["original_research_database"] == []


def test_migration_refuses_out_of_range_version() -> None:
    """Source schema_version other than 1.3 or 1.4 raises ValueError
    (per rules/schema-versioning-discipline.md — silent rewrites forbidden)."""
    src = {"schema_version": "1.1", "project_id": "test"}
    with pytest.raises(ValueError, match=r"schema_version"):
        migrate(src)


def test_migration_does_not_mutate_input() -> None:
    """Pure function — input dict must not be modified in place."""
    src = {
        "schema_version": "1.3",
        "project_id": "test",
        "content_settings": {"experience_database": [{"id": "old-001"}]},
    }
    import copy
    snapshot = copy.deepcopy(src)
    migrate(src)
    assert src == snapshot, "migrate() must not mutate its input"
