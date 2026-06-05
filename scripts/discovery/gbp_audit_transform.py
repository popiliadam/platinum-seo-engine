"""gbp-audit — discovery skill transforming DFS business listings into a gap report.

G-AI-02 finding closure (v1.7 Phase 5). Sister module of
`scripts/discovery/tech_audit_transform.py` but lighter (single DFS
endpoint, ~3 credits/run vs tech-audit's ~13) and profile-gated at
step 1 (local-service required).

Hard-constraint compliance:
  - feedback_indexing_api_consent — NO autonomous GBP API submit. The
    only paid call (``business_data_business_listings_search``) is a
    QUERY endpoint, not a write endpoint. Operator does the GBP
    dashboard work manually based on the report.
  - feedback_hard_constraints — `.mcp.json` byte-byte unchanged (this
    module imports nothing from the MCP config; only references tool
    names by string).
  - Schema-first — emitted rows match `schemas/master-excel.schema.
    json#sheets.gbp_audit` (7 cols, severityEnum + statusEnum reuse).

Severity matrix (per category, applied in `_analyze_gaps`):
  - nap            HIGH    GBP listing not found (DFS + Scrapling both empty)
  - nap            HIGH    NAP mismatch with project.config domain (Phase 11)
  - categories     HIGH    no primary category
  - categories     MEDIUM  < 2 secondary categories
  - photos         HIGH    < 3 photos
  - photos         MEDIUM  < 10 photos (but >= 3)
  - hours          HIGH    regular business hours missing
  - hours          MEDIUM  holiday hours missing
  - attributes     MEDIUM  profile-relevant attribute empty
  - posts          LOW     no GBP posts in last 30 days
  - qa             LOW     no Q&A engagement
  - reviews        MEDIUM  response rate < 50%
  - reviews        MEDIUM  average rating < 4.0

The MCP fetchers (`_fetch_listing`, `_scrapling_fallback`) and the
budget pre-flight (`_budget_preflight`) are stubs at this layer — the
production skill orchestrator wires them to the real MCP surface.
Tests monkeypatch them.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from scripts.budget import check_budget


# ---------------------------------------------------------------------------
# Exception hierarchy (mirrors tech_audit_transform's TechAuditError tree)
# ---------------------------------------------------------------------------

class GbpAuditError(Exception):
    """Base for gbp-audit transform errors."""


class BudgetExceededError(GbpAuditError):
    """Projected DFS credits exceed the per-day cap — the run MUST route to
    ``awaiting_approval`` (DURUR #1), never silently downgrade or skip."""


def preflight_budget(
    *,
    estimated_credits: int,
    project_config_path: str | Path,
    events_path: str | Path,
) -> dict:
    """§16.8 budget pre-flight for the single paid DFS call (SKILL.md Step 2).

    Mirrors ``tech_audit_transform.preflight_budget``'s contract — keyword-only
    args, an envelope keyed ``projected_used`` / ``remaining_after`` (the
    codebase-standard the sibling transforms + the SKILL.md DURUR #1 read),
    ``BudgetExceededError`` on overage — but routes through the importable
    ``check_budget.preflight`` SSoT (ADR-016) rather than re-subprocessing.
    Raises ``BudgetExceededError`` when projected usage (trailing-24h spend +
    ``estimated_credits``) breaches the cap, so the skill routes the run to
    ``awaiting_approval`` per spec §10 instead of a silent downgrade.
    """
    raw = check_budget.preflight(
        project_config_path=project_config_path,
        events_path=events_path,
        estimated_credits=estimated_credits,
    )
    envelope = {
        "budget_per_day": raw["budget_per_day"],
        "used_24h": raw["used_24h"],
        "estimated_credits": raw["estimated_credits"],
        "projected_used": raw["projected"],
        "remaining_after": raw["remaining"],
        "exceeded": raw["exceeded"],
    }
    if envelope["exceeded"]:
        raise BudgetExceededError(
            f"DFS budget pre-flight FAIL: projected={envelope['projected_used']} "
            f"> budget={envelope['budget_per_day']} "
            f"(used_24h={envelope['used_24h']}, estimate={estimated_credits}). "
            "Route workflow to awaiting_approval per spec §10 (DURUR #1)."
        )
    return envelope


def run(
    project_slug: str, workspace_root: Path | str | None = None
) -> dict[str, Any]:
    """Run the GBP audit for a single project.

    Returns a result envelope:
      - status="skipped":              profile gate not satisfied
      - status="awaiting_approval":    budget pre-flight FAIL
      - status="success" + gap_rows:   audit completed, gaps identified
    """
    workspace_root = Path(workspace_root or os.environ["PSEO_WORKSPACE_ROOT"])
    project_dir = workspace_root / "projects" / project_slug
    config = json.loads((project_dir / "project.config.json").read_text("utf-8"))

    # Step 1 — profile gate (early exit before any paid call).
    profiles = config.get("profiles", [])
    if "local-service" not in profiles:
        return {
            "status": "skipped",
            "reason": (
                "Profile 'local-service' missing from project.profiles "
                "(found: " + ", ".join(profiles) + ")"
            ),
            "project_slug": project_slug,
        }

    # Step 2 — budget pre-flight (MANDATORY before paid call).
    if not _budget_preflight(config):
        return {
            "status": "awaiting_approval",
            "reason": (
                "DFS budget pre-flight FAIL — projected credits exceed "
                "project.config.dataforseo.budget_credits_per_day cap. "
                "Approve override via manager surface."
            ),
            "project_slug": project_slug,
        }

    # Step 4 — fetch listing (DFS first).
    listing = _fetch_listing(config)

    # Step 5 — Scrapling fallback (only if DFS empty).
    if not listing:
        listing = _scrapling_fallback(config)

    # Step 6 — pure-compute gap analysis.
    gap_rows = _analyze_gaps(listing, config)

    return {
        "status": "success",
        "project_slug": project_slug,
        "gap_rows": gap_rows,
    }


# ---------------------------------------------------------------------------
# Stubs (production wires these to MCP / budget surface)
# ---------------------------------------------------------------------------

def _budget_preflight(config: dict) -> bool:
    """Stub — production invokes ``scripts.budget.check_budget`` via
    subprocess (ADR-016 SSoT). Returns True (PASS) at module level so
    a default run does not block; the mock_gbp_budget_exhausted fixture
    monkeypatches this to False to drive the awaiting_approval path."""
    return True


def _fetch_listing(config: dict) -> dict | None:
    """Stub — production invokes ``mcp__dataforseo__business_data_
    business_listings_search``. Returns None at module level; tests
    monkeypatch to inject a canned listing dict."""
    return None


def _scrapling_fallback(config: dict) -> dict | None:
    """Stub — production invokes ``mcp__ScraplingServer__fetch`` against
    a Google Maps place URL. Returns None at module level; tests
    monkeypatch when they need the fallback path exercised."""
    return None


# ---------------------------------------------------------------------------
# Gap analysis (pure compute — no I/O)
# ---------------------------------------------------------------------------

def _analyze_gaps(listing: dict | None, config: dict) -> list[dict]:
    """Per-category gap analysis returning master.xlsx[gbp_audit] rows.

    Each row is a dict with exactly the 7 columns the schema requires:
    audit_id, audit_date, category, gap_description, severity,
    recommended_action, status.

    The matrix is documented in the module docstring above. Severity
    values are codebase severityEnum strict ({CRITICAL, HIGH, MEDIUM,
    LOW}); CRITICAL is reserved for future emission tiers and is not
    produced by the current rule set.
    """
    rows: list[dict] = []

    if not listing:
        rows.append(_row(
            "nap", "HIGH",
            "GBP listing not found",
            "Create or claim a Google Business Profile listing for the business",
        ))
        return rows

    # categories
    if not listing.get("primary_category"):
        rows.append(_row(
            "categories", "HIGH",
            "Primary category missing",
            "Set the primary GBP category from the GBP dashboard",
        ))
    if len(listing.get("secondary_categories", [])) < 2:
        rows.append(_row(
            "categories", "MEDIUM",
            "Fewer than 2 secondary categories",
            "Add at least 2 relevant secondary categories",
        ))

    # photos
    photo_count = listing.get("photo_count", 0)
    if photo_count < 3:
        rows.append(_row(
            "photos", "HIGH",
            f"Only {photo_count} photos",
            "Add at least 3 high-quality photos (exterior, interior, team)",
        ))
    elif photo_count < 10:
        rows.append(_row(
            "photos", "MEDIUM",
            f"Only {photo_count} photos",
            "Add photos to reach 10+ for a healthy GBP listing",
        ))

    # hours
    if not listing.get("business_hours"):
        rows.append(_row(
            "hours", "HIGH",
            "Regular business hours missing",
            "Add regular business hours in the GBP dashboard",
        ))
    if not listing.get("holiday_hours"):
        rows.append(_row(
            "hours", "MEDIUM",
            "No holiday hours configured",
            "Add holiday hours for upcoming holidays",
        ))

    # attributes
    if listing.get("attributes") in (None, [], {}):
        rows.append(_row(
            "attributes", "MEDIUM",
            "Profile-relevant attributes empty",
            "Fill profile-relevant GBP attributes (parking, accessibility, etc.)",
        ))

    # posts
    if listing.get("post_count_30d", 0) == 0:
        rows.append(_row(
            "posts", "LOW",
            "No GBP posts in last 30 days",
            "Publish at least 1 GBP post (update / offer / event)",
        ))

    # qa
    if listing.get("qa_count", 0) == 0:
        rows.append(_row(
            "qa", "LOW",
            "No Q&A engagement",
            "Seed Q&A with FAQ-aligned questions and authoritative answers",
        ))

    # reviews
    review_response_rate = listing.get("review_response_rate")
    if review_response_rate is not None and review_response_rate < 0.5:
        rows.append(_row(
            "reviews", "MEDIUM",
            f"Review response rate {int(review_response_rate * 100)}%",
            "Respond to outstanding reviews; target 100% response rate",
        ))
    avg_rating = listing.get("avg_rating")
    if avg_rating is not None and avg_rating < 4.0:
        rows.append(_row(
            "reviews", "MEDIUM",
            f"Average rating {avg_rating:.1f}",
            "Address negative-review themes via service operations",
        ))

    return rows


def _row(category: str, severity: str, gap: str, action: str) -> dict:
    """Build a single master.xlsx[gbp_audit] row. Schema-locked 7 cols.

    audit_id format `gbp-<uuid8>` matches the SKILL.md spec; the
    transform owns ID generation so the operator does not need to
    pre-allocate IDs.
    """
    return {
        "audit_id": f"gbp-{uuid4().hex[:8]}",
        "audit_date": date.today().isoformat(),
        "category": category,
        "gap_description": gap,
        "severity": severity,
        "recommended_action": action,
        "status": "TODO",
    }
