"""Migration 0005 — project-config schema v1.4 → v1.5 SF MCP integration tests.

Covers ``scripts/migrations/migration_0005_project_config_1_4_to_1_5.migrate``:
  1. ``schema_version`` bumps "1.4" → "1.5" (bump_only path).
  2. ``sf`` block created from scratch with documented defaults
     (populate_defaults path).
  3. Idempotent on already-v1.5 input — no-op (idempotent_replay).
  4. Out-of-range source schema_version raises ValueError (missing_required
     guard — silent rewrite forbidden per rules/schema-versioning-discipline.md).
  5. Hand-edited sf block survives — only missing defaults are filled
     (mixed_existing_field forward-compat).

The migration is *additive* — it never deletes or mutates existing values
under sf; missing sf block on a clean v1.4 doc is created with documented
defaults so downstream sf-crawl-orchestrator + sf-import can read a stable
shape. Pattern reuse: ``tests/migrations/test_0004_project_config_1_3_to_1_4.py``
(direct ``from scripts.migrations.migration_0005_… import migrate`` per
the Python-importable naming established in Migration 0004).
"""

from __future__ import annotations

import copy

import pytest

from scripts.migrations.migration_0005_project_config_1_4_to_1_5 import (
    DEFAULT_SF_MCP,
    migrate,
)


def test_migration_bumps_schema_version() -> None:
    """bump_only — schema_version "1.4" → "1.5" on a minimal doc."""
    src = {"schema_version": "1.4", "project_id": "test", "profiles": ["ymyl"]}
    out = migrate(src)
    assert out["schema_version"] == "1.5"


def test_migration_populates_default_sf_block() -> None:
    """populate_defaults — sf.mcp.* fully populated with documented defaults
    when the source doc has no sf block."""
    src = {"schema_version": "1.4", "project_id": "test", "profiles": ["e-commerce"]}
    out = migrate(src)
    assert out["sf"] == {"mcp": dict(DEFAULT_SF_MCP)}, (
        "Migration 0005 must emit the canonical default sf.mcp.* block; "
        "DEFAULT_SF_MCP is the single source of truth shared with "
        "scripts/state/bootstrap_project.py DEFAULT_SF_MCP_BLOCK."
    )
    # Spot-check individual defaults per spec line 222 + Q-SF-MCP-11 (300s):
    mcp = out["sf"]["mcp"]
    assert mcp["enabled"] is False
    assert mcp["url"] == "http://127.0.0.1:11435/mcp"
    assert mcp["allowed_directory"] is None
    assert mcp["crawl_config_path"] is None
    assert mcp["max_wait_minutes"] == 180
    assert mcp["per_report_timeout_seconds"] == 300


def test_migration_idempotent_on_v1_5() -> None:
    """idempotent_replay — running migrate() on an already-v1.5 doc is a no-op."""
    src = {
        "schema_version": "1.5",
        "project_id": "test",
        "profiles": ["b2b-saas"],
        "sf": {"mcp": dict(DEFAULT_SF_MCP)},
    }
    out = migrate(src)
    assert out["schema_version"] == "1.5"
    # No-op preserves the doc bit-for-bit (identity is acceptable for
    # idempotent no-op per Migration 0004 paterni).
    assert out == src


def test_migration_refuses_out_of_range_version() -> None:
    """missing_required — source schema_version outside {1.4, 1.5} raises
    ValueError (silent rewrite forbidden per
    rules/schema-versioning-discipline.md)."""
    for sv in ("1.0", "1.1", "1.2", "1.3", "2.0", "draft", None):
        with pytest.raises(ValueError, match=r"schema_version"):
            migrate({"schema_version": sv, "project_id": "test"})


def test_migration_preserves_existing_sf_block_fields() -> None:
    """mixed_existing_field — operator-edited sf.mcp.* values survive;
    only MISSING sub-keys are filled with defaults (setdefault discipline
    matches Migration 0004 forward-compat pattern)."""
    src = {
        "schema_version": "1.4",
        "project_id": "test",
        "profiles": ["local-service"],
        "sf": {
            "mcp": {
                "enabled": True,
                "url": "http://my-host:9000/mcp",
                "allowed_directory": "/Users/operator/sf_scratch",
                # crawl_config_path + max_wait_minutes + per_report_timeout_seconds
                # intentionally absent — should be back-filled with defaults
            }
        },
    }
    out = migrate(src)
    mcp = out["sf"]["mcp"]
    # Operator overrides preserved verbatim.
    assert mcp["enabled"] is True
    assert mcp["url"] == "http://my-host:9000/mcp"
    assert mcp["allowed_directory"] == "/Users/operator/sf_scratch"
    # Missing keys back-filled with documented defaults.
    assert mcp["crawl_config_path"] is None
    assert mcp["max_wait_minutes"] == 180
    assert mcp["per_report_timeout_seconds"] == 300


def test_migration_does_not_mutate_input() -> None:
    """Pure function — input dict must not be modified in place
    (mirrors Migration 0004 contract)."""
    src = {
        "schema_version": "1.4",
        "project_id": "test",
        "profiles": ["ymyl"],
    }
    snapshot = copy.deepcopy(src)
    migrate(src)
    assert src == snapshot, "migrate() must not mutate its input"


def test_migration_preserves_unrelated_fields() -> None:
    """Unrelated top-level keys (project_id, profiles, content_settings,
    brand_identity) survive intact — additive policy."""
    src = {
        "schema_version": "1.4",
        "project_id": "alpha",
        "profiles": ["e-commerce", "ymyl"],
        "content_settings": {
            "experience_database": [{"id": "exp-001", "context": "10 yıl"}],
        },
        "brand_identity": {"pronoun_preference": "siz", "formality": "semi-pro"},
    }
    out = migrate(src)
    assert out["project_id"] == "alpha"
    assert out["profiles"] == ["e-commerce", "ymyl"]
    assert out["content_settings"]["experience_database"][0]["id"] == "exp-001"
    assert out["brand_identity"]["pronoun_preference"] == "siz"
    # sf block still emitted alongside the preserved fields.
    assert "sf" in out
