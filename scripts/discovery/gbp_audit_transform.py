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
  - nap            HIGH    NAP mismatch vs canonical local/nap.json (one row
                           per mismatched field; GAP-A2 2026-06-10 closed the
                           declared-but-missing branch via
                           scripts/discovery/nap_consistency.compare_nap)
  - nap            MEDIUM  canonical NAP file missing
                           (projects/{slug}/local/nap.json —
                           schemas/local-nap.schema.json; single NAP source
                           of truth per rules/local-seo-discipline.md)
  - categories     HIGH    no primary category
  - categories     MEDIUM  fewer secondary categories than the competitor
                           median (only when competitors were measured)
  - photos         HIGH    < half the competitor median photo count
  - photos         MEDIUM  below the competitor median; without competitor
                           data only 0 photos is a finding
  - hours          HIGH    regular business hours missing
  - hours          MEDIUM  holiday hours missing
  - attributes     MEDIUM  profile-relevant attribute empty
  - posts          LOW     no GBP posts in last 30 days

S-22: Google publishes no photo/category counts, so fixed ">= 3 / >= 10 photos"
and ">= 2 secondary categories" were replaced by the competitor median. A field
the source did not report (DFS has no holiday hours, posts or review-response
rate) is unknown and produces no finding. The Q&A seeding rule was dropped
(Google retired Q&A on Business Profiles). DFS ``business_listings_search``
items are mapped by ``normalize_listing``.
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
from scripts.discovery import nap_consistency


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

    # Canonical NAP doc (rules/local-seo-discipline.md: single NAP source of
    # truth at projects/{slug}/local/nap.json). A present-but-corrupt file
    # fails LOUD (json.JSONDecodeError propagates — SKILL.md DURUR #9):
    # auditing against half a canonical is worse than stopping.
    nap_path = project_dir / "local" / "nap.json"
    canonical_nap: dict | None = None
    if nap_path.exists():
        canonical_nap = json.loads(nap_path.read_text("utf-8"))

    # Step 6 — pure-compute gap analysis.
    gap_rows = _analyze_gaps(listing, config, canonical_nap=canonical_nap,
                             competitors=_fetch_competitors(config))

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


def _fetch_competitors(config: dict) -> list[dict] | None:
    """Stub — production invokes ``business_listings_search`` for the same
    category + city and passes the top local competitors (S-22 medians).
    None → no relative thresholds."""
    return None


def _scrapling_fallback(config: dict) -> dict | None:
    """Stub — production invokes ``mcp__ScraplingServer__fetch`` against
    a Google Maps place URL. Returns None at module level; tests
    monkeypatch when they need the fallback path exercised."""
    return None


# ---------------------------------------------------------------------------
# Gap analysis (pure compute — no I/O)
# ---------------------------------------------------------------------------

# DFS business_listings_search item field → internal listing field (S-22).
def normalize_listing(raw: dict | None) -> dict | None:
    """Map a DFS ``business_listings_search`` item to the internal listing keys.

    Already-internal listings pass through. Only fields DFS really returns are
    set; everything else stays absent (= unknown, no finding).
    """
    if not raw:
        return raw
    if not any(k in raw for k in ("title", "total_photos", "additional_categories", "work_time")):
        return raw
    out: dict = {
        "business_name": raw.get("title"),
        "address": raw.get("address"),
        "phone": raw.get("phone"),
        "primary_category": raw.get("category"),
    }
    if "additional_categories" in raw:
        out["secondary_categories"] = list(raw.get("additional_categories") or [])
    if "total_photos" in raw:
        out["photo_count"] = raw.get("total_photos") or 0
    work_time = raw.get("work_time")
    if work_time is not None:
        out["business_hours"] = ((work_time or {}).get("work_hours") or {}).get("timetable")
    rating = raw.get("rating")
    if isinstance(rating, dict) and rating.get("value") is not None:
        out["avg_rating"] = rating["value"]
    attributes = raw.get("attributes")
    if attributes is not None:
        out["attributes"] = (attributes or {}).get("available_attributes") or {}
    return out


def _median(values: list[float]) -> float | None:
    vals = sorted(v for v in values if isinstance(v, (int, float)))
    if not vals:
        return None
    mid = len(vals) // 2
    return float(vals[mid]) if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def _competitor_medians(competitors: list[dict] | None) -> dict:
    comps = [normalize_listing(c) or {} for c in (competitors or [])]
    return {
        "photos": _median([c["photo_count"] for c in comps if "photo_count" in c]),
        "secondary": _median([len(c["secondary_categories"]) for c in comps
                              if "secondary_categories" in c]),
    }


def _photo_rows(listing: dict, medians: dict) -> list[dict]:
    if "photo_count" not in listing:
        return []
    count, median = listing.get("photo_count") or 0, medians.get("photos")
    if median is None:
        if count == 0:
            return [_row("photos", "MEDIUM", "No photos (competitor median not measured)",
                         "Add real photos of the premises, team and work")]
        return []
    if count < median / 2:
        return [_row("photos", "HIGH", f"{count} photos vs competitor median {median:.0f}",
                     "Add real photos to reach at least the competitor median")]
    if count < median:
        return [_row("photos", "MEDIUM", f"{count} photos vs competitor median {median:.0f}",
                     "Add real photos to reach the competitor median")]
    return []


def _analyze_gaps(
    listing: dict | None,
    config: dict,
    canonical_nap: dict | None = None,
    competitors: list[dict] | None = None,
) -> list[dict]:
    """Per-category gap analysis returning master.xlsx[gbp_audit] rows.

    Each row is a dict with exactly the 7 columns the schema requires:
    audit_id, audit_date, category, gap_description, severity,
    recommended_action, status.

    ``canonical_nap`` is the parsed ``projects/{slug}/local/nap.json``
    (schemas/local-nap.schema.json) or None when the file is absent.
    Absent canonical → one MEDIUM "canonical NAP file missing" row;
    present → per-field NAP comparison via
    ``scripts.discovery.nap_consistency.compare_nap`` (each mismatch is a
    HIGH row). The listing-not-found early return stays nap-comparison-free:
    without a listing there is nothing to compare, and the not-found row is
    already the blocking finding.

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

    listing = normalize_listing(listing) or {}
    medians = _competitor_medians(competitors)

    # nap — canonical source of truth comparison (GAP-A2; the matrix
    # declared this branch since v1.7 Phase 5 without implementing it).
    if canonical_nap is None:
        rows.append(_row(
            "nap", "MEDIUM",
            "Canonical NAP file missing (projects/{slug}/local/nap.json)",
            "Create local/nap.json per schemas/local-nap.schema.json — the "
            "single NAP source of truth (rules/local-seo-discipline.md); "
            "then re-run gbp-audit for the field-level comparison",
        ))
    else:
        observed = {
            "business_name": listing.get("business_name") or listing.get("title"),
            "phone": listing.get("phone"),
            "address": listing.get("address"),
            "source": "gbp_listing",
        }
        if listing.get("location_id") is not None:
            observed["location_id"] = listing["location_id"]
        for finding in nap_consistency.compare_nap(canonical_nap, observed):
            rows.append(_row(
                "nap", "HIGH",
                (
                    f"NAP mismatch ({finding['field']}): canonical "
                    f"'{finding['canonical_value']}' vs "
                    f"{finding['observed_source']} '{finding['observed_value']}'"
                ),
                (
                    f"Sync {finding['field']} across GBP listing + site footer "
                    "+ LocalBusiness JSON-LD to match local/nap.json — never "
                    "'fix' the canonical to match a drifted surface"
                ),
            ))

    # categories
    if not listing.get("primary_category"):
        rows.append(_row(
            "categories", "HIGH",
            "Primary category missing",
            "Set the primary GBP category from the GBP dashboard",
        ))
    secondary_median = medians.get("secondary")
    if ("secondary_categories" in listing and secondary_median is not None
            and len(listing["secondary_categories"]) < secondary_median):
        rows.append(_row(
            "categories", "MEDIUM",
            f"{len(listing['secondary_categories'])} secondary categories vs "
            f"competitor median {secondary_median:.0f}",
            "Add the relevant secondary categories competitors use",
        ))

    # photos — relative to competitors (S-22)
    rows.extend(_photo_rows(listing, medians))

    # hours
    if "business_hours" in listing and not listing.get("business_hours"):
        rows.append(_row(
            "hours", "HIGH",
            "Regular business hours missing",
            "Add regular business hours in the GBP dashboard",
        ))
    if "holiday_hours" in listing and not listing.get("holiday_hours"):
        rows.append(_row(
            "hours", "MEDIUM",
            "No holiday hours configured",
            "Add holiday hours for upcoming holidays",
        ))

    # attributes
    if "attributes" in listing and listing.get("attributes") in (None, [], {}):
        rows.append(_row(
            "attributes", "MEDIUM",
            "Profile-relevant attributes empty",
            "Fill profile-relevant GBP attributes (parking, accessibility, etc.)",
        ))

    # posts
    if "post_count_30d" in listing and listing.get("post_count_30d") == 0:
        rows.append(_row(
            "posts", "LOW",
            "No GBP posts in last 30 days",
            "Publish at least 1 GBP post (update / offer / event)",
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
