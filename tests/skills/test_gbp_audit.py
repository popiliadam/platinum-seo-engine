"""tests/skills/test_gbp_audit.py — gbp-audit discovery skill tests.

Phase 5 Wave 1, G-AI-02 finding closure. DFS LIGHT (~3 credits/run) +
optional Scrapling fallback. Profile-gated at Step 1 (local-service
required, e-commerce/b2b-saas/portfolio skip with status=skipped).

Test coverage (6 cases):
  1. Frontmatter parses + validates (schemas/skill-frontmatter.schema)
     — incl. budget.uses_paid_mcp = True, category = discovery.
  2. Profile gate skip — profiles=[e-commerce] → status=skipped, no
     paid call, reason references local-service.
  3. Gap rows emitted per missing field — partial DFS listing with
     missing categories + photos → gap_rows include "categories" and
     "photos" entries.
  4. Severity assignment — every emitted severity is in
     {CRITICAL, HIGH, MEDIUM, LOW} (codebase severityEnum strict).
  5. Budget pre-flight — exhausted budget → status=awaiting_approval
     with reason referencing budget.
  6. Listing not found — DFS empty AND Scrapling fallback empty →
     "nap" gap with HIGH severity and "GBP listing not found"
     description.

Cross-module IMPORT-only discipline:
  - scripts.discovery.gbp_audit_transform (run, transform helpers,
    severity matrix, gap analysis).

Hard-constraint compliance (asserted indirectly):
  - feedback_indexing_api_consent — no autonomous GBP submit; only
    audit + report. The transform never calls a submit endpoint;
    tests never assert "submit was called" because the transform
    never invokes one.

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_gbp_audit.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import gbp_audit_transform


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_MD = REPO_ROOT / "skills" / "discovery" / "gbp-audit" / "SKILL.md"


# ---------------------------------------------------------------------------
# Fixtures — module-local (gbp-audit-specific, not shared via conftest)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_dfs_business_data_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    """DFS returns a partial business listing: primary category missing,
    only 2 photos, no holiday hours, no posts last 30d. Drives gap rows
    in categories / photos / hours / posts."""
    monkeypatch.setattr(
        gbp_audit_transform,
        "_fetch_listing",
        lambda config: {
            "business_name": config.get("brand_identity", {}).get(
                "business_name", "Test Business"
            ),
            "primary_category": None,
            "secondary_categories": ["Service A"],   # only 1 secondary
            "photo_count": 2,                        # < 3 → HIGH
            "business_hours": {"mon": "9-17"},
            "holiday_hours": None,                   # → MEDIUM
            "post_count_30d": 0,                     # → LOW
        },
    )


@pytest.fixture
def mock_dfs_listing_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """DFS returns no listing AND Scrapling fallback returns None.
    Drives the 'GBP listing not found' HIGH-severity nap row."""
    monkeypatch.setattr(gbp_audit_transform, "_fetch_listing", lambda config: None)
    monkeypatch.setattr(
        gbp_audit_transform, "_scrapling_fallback", lambda config: None
    )


@pytest.fixture
def mock_gbp_budget_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Budget pre-flight returns False — skill DURUR #1 awaiting_approval."""
    monkeypatch.setattr(
        gbp_audit_transform, "_budget_preflight", lambda config: False
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_skill_frontmatter_validates_against_schema() -> None:
    """SKILL.md frontmatter parses and validates against skill-frontmatter.schema.json."""
    body = SKILL_MD.read_text("utf-8")
    assert body.startswith("---\n"), "SKILL.md missing frontmatter block"
    _, fm, _ = body.split("---", 2)
    data = yaml.safe_load(fm)

    assert data["name"] == "gbp-audit"
    assert data["category"] == "discovery"
    assert data["budget"]["uses_paid_mcp"] is True
    assert data["budget"]["estimated_credits"] == 3
    assert "mcp__dataforseo__business_data_business_listings_search" in (
        data["mcp_tools"]["required"]
    )

    schema = json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )
    Draft7Validator(schema).validate(data)


def test_profile_gate_skips_non_local_service(tmp_workspace_factory) -> None:
    """e-commerce-only project must skip cleanly — no paid call, no Excel write."""
    tmp_workspace_factory(slug="ecom-only", profiles=["e-commerce"])
    result = gbp_audit_transform.run(project_slug="ecom-only")
    assert result["status"] == "skipped"
    assert "local-service" in result["reason"]
    assert "gap_rows" not in result or result.get("gap_rows", []) == []


def test_gap_rows_emitted_per_missing_field(
    mock_dfs_business_data_partial, tmp_workspace_factory
) -> None:
    """Partial DFS listing → gap rows in expected categories."""
    tmp_workspace_factory(slug="local-test", profiles=["local-service"])
    result = gbp_audit_transform.run(project_slug="local-test")
    assert result["status"] == "success"
    gap_categories = {row["category"] for row in result["gap_rows"]}
    assert "categories" in gap_categories  # primary missing → HIGH
    assert "photos" in gap_categories      # 2 < 3 → HIGH
    assert "hours" in gap_categories       # holiday missing → MEDIUM
    assert "posts" in gap_categories       # none last 30d → LOW


def test_severity_assignment_within_severity_enum(
    mock_dfs_business_data_partial, tmp_workspace_factory
) -> None:
    """Every emitted severity is in the codebase severityEnum
    (CRITICAL/HIGH/MEDIUM/LOW); active emission tier excludes CRITICAL."""
    tmp_workspace_factory(slug="local-test", profiles=["local-service"])
    result = gbp_audit_transform.run(project_slug="local-test")
    assert result["status"] == "success"
    severities = {row["severity"] for row in result["gap_rows"]}
    # severityEnum strict
    assert severities <= {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    # active emission tier (no row hits CRITICAL on the partial-listing path)
    assert severities <= {"HIGH", "MEDIUM", "LOW"}


def test_budget_preflight_awaiting_approval(
    mock_gbp_budget_exhausted, tmp_workspace_factory
) -> None:
    """Exhausted budget → status=awaiting_approval, reason references budget."""
    tmp_workspace_factory(slug="local-test", profiles=["local-service"])
    result = gbp_audit_transform.run(project_slug="local-test")
    assert result["status"] == "awaiting_approval"
    assert "budget" in result["reason"].lower()


def test_listing_not_found_emits_high_severity_nap(
    mock_dfs_listing_empty, tmp_workspace_factory
) -> None:
    """DFS empty + Scrapling empty → nap row with HIGH severity."""
    tmp_workspace_factory(slug="local-test", profiles=["local-service"])
    result = gbp_audit_transform.run(project_slug="local-test")
    assert result["status"] == "success"
    nap_rows = [r for r in result["gap_rows"] if r["category"] == "nap"]
    assert len(nap_rows) == 1
    assert nap_rows[0]["severity"] == "HIGH"
    assert "listing not found" in nap_rows[0]["gap_description"].lower()
    assert nap_rows[0]["status"] == "TODO"
    assert nap_rows[0]["audit_id"].startswith("gbp-")
