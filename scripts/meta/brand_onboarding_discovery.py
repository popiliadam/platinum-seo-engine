"""Brand onboarding Stage A — Auto discovery via DFS + Scrapling.

⚠️  STAGING-ONLY (P1-12) — real discovery deferred.
    Every ``_fetch_*`` below is a *stub* that returns ``None`` / ``[]``; this
    module performs NO live discovery today. The stub→live-MCP wiring lands in
    Phase 11 Wave 2, and the full staging→canonical flow only goes live at
    Phase 14 (workspace bring-up). Until then the module is non-destructive:
    it never spends paid MCP credits (F-16 budget pre-flight) and never writes
    project state — it only shapes draft candidates for operator review.

Pipeline (per the plan/2026-05-21 G-AI-05 hybrid spec):
    1. DFS ``domain_analytics_whois_overview``     — domain creation
       date (founding-year proxy).
    2. DFS ``on_page_content_parsing``             — /hakkimizda,
       /ekibimiz, /case-studies, /portfolio.
    3. DFS ``business_data_business_listings_search`` — GBP-style
       listing (categories, founded year, hours) for local-service
       profiles.
    4. DFS ``dataforseo_labs_google_keywords_for_site`` — top-20
       keywords → applicable_topics candidates.
    5. Scrapling ``fetch``                         — case-study /
       reference pages (HTML extraction).
    6. Output: draft_experience_entries + draft_research_entries +
       topic_candidates — Stage B (Task 3.3) consumes the drafts and
       lets the operator approve / edit / reject each.

Plugin-agnostic discipline:
    - **No autonomous spend (F-16 budget pre-flight):** if the DFS
      daily budget is exhausted, ``discover()`` returns
      ``status='awaiting_approval'`` and exits without calling the
      paid MCPs.
    - **No submission (per memory ``feedback_indexing_api_consent``):**
      this skill is read-only. No GBP / Indexing API / Merchant Center
      write happens — Stage B/C continue toward bank-write only.

Runtime MCP calls are stubbed at module level (``_fetch_*``,
``_budget_preflight``) so unit tests can monkeypatch them to inject
canned values per scenario. The production wiring (Phase 11 Wave 2)
replaces the stubs with actual MCP ``mcp__dataforseo__*`` calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _current_year() -> int:
    """Live UTC year — module-level so the experience-claim math stays
    dynamic (P1-12: no hardcoded founding-year baseline) and tests can
    monkeypatch it to assert the 'X+ yıl' computation tracks the calendar."""
    return datetime.now(timezone.utc).year


def discover(
    project_slug: str, workspace_root: Path | str | None = None
) -> dict[str, Any]:
    """Run Stage A — auto-discover bank candidates from public sources.

    Returns:
        ``{"status": "success", "draft_experience_entries": [...],
            "draft_research_entries": [...], "topic_candidates": [...],
            "project_slug": ...}`` on a normal pass.

        ``{"status": "awaiting_approval", "reason": "<budget message>"}``
        when the DFS budget pre-flight rejects the call (F-16 plugin-
        agnostic invariant).
    """
    if not _budget_preflight():
        return {
            "status": "awaiting_approval",
            "reason": "DFS budget exhausted (F-16 pre-flight); operator must top up or wait",
        }

    workspace_root = Path(workspace_root or os.environ["PSEO_WORKSPACE_ROOT"])
    project_dir = workspace_root / "projects" / project_slug
    config = json.loads((project_dir / "project.config.json").read_text(encoding="utf-8"))

    domain = config.get("domain", "").rstrip("/")
    profiles = config.get("profiles", [])

    draft_experience: list[dict] = []
    draft_research: list[dict] = []

    # 1. WHOIS — founding year
    founding_year = _fetch_whois_creation_year(domain)
    if founding_year:
        draft_experience.append(
            {
                "hint": "founding_year",
                "claim_core": (
                    f"{_current_year() - founding_year}+ yıl sektör tecrübesi "
                    f"(domain {founding_year} kuruluş)"
                ),
                "evidence_url": domain,
                "source": "whois",
                "needs_review": True,
            }
        )

    # 2. About page — about-text extraction
    about_data = _fetch_about_page(domain)
    if about_data:
        draft_experience.extend(_extract_from_about(about_data))

    # 3. GBP listing (local-service profile only)
    if "local-service" in profiles:
        gbp_data = _fetch_business_listing(domain, config)
        if gbp_data:
            draft_experience.extend(_extract_from_gbp(gbp_data))

    # 4. Case-study pages (Scrapling)
    case_studies = _fetch_case_study_pages(domain)
    if case_studies:
        draft_experience.extend(_extract_case_studies(case_studies))

    # 5. Top-20 keywords → topic_candidates
    topic_candidates = _fetch_top_keywords(domain, config)

    return {
        "status": "success",
        "draft_experience_entries": draft_experience,
        "draft_research_entries": draft_research,
        "topic_candidates": topic_candidates,
        "project_slug": project_slug,
    }


# ---------------------------------------------------------------------------
# MCP call stubs — monkeypatched in unit tests, replaced by real MCP wiring
# in Phase 11 Wave 2 (production).
# ---------------------------------------------------------------------------

def _budget_preflight() -> bool:
    """Check DFS daily budget. Production: calls scripts/budget/check_budget.py.

    Stub returns True (budget available) so tests opt-in to scarcity via
    ``mock_dfs_budget_exhausted`` fixture.
    """
    return True


def _fetch_whois_creation_year(domain: str) -> int | None:
    """Stub — production calls ``mcp__dataforseo__domain_analytics_whois_overview``
    and parses the ``created`` date's year."""
    return None


def _fetch_about_page(domain: str) -> dict | None:
    """Stub — production calls ``mcp__dataforseo__on_page_content_parsing``
    for ``/hakkimizda`` / ``/about`` and returns the parsed text dict."""
    return None


def _extract_from_about(about_data: dict) -> list[dict]:
    """Parse about-page text — pull certifications, years in business,
    partner mentions, BDDK / TÜRK PATENT lisans references, etc."""
    # Phase 11 Wave 2 — heuristic extractors land here. Stub returns
    # empty so the generic mock_dfs fixture exercises the empty path.
    return []


def _fetch_business_listing(domain: str, config: dict) -> dict | None:
    """Stub — production calls ``mcp__dataforseo__business_data_business_listings_search``
    with the domain's brand name + city derived from ``config['market']``."""
    return None


def _extract_from_gbp(gbp_data: dict) -> list[dict]:
    """Parse GBP categories, hours, year founded, attributes
    (accessibility, payment methods, service-area markers)."""
    return []


def _fetch_case_study_pages(domain: str) -> list[dict]:
    """Stub — production tries ``/case-studies``, ``/musteriler``,
    ``/portfolio``, ``/referanslar`` via Scrapling ``fetch`` then
    ``stealthy_fetch`` if the first hits 403/429."""
    return []


def _extract_case_studies(pages: list[dict]) -> list[dict]:
    """Extract titled case-story headings + summary text per page."""
    return []


def _fetch_top_keywords(domain: str, config: dict) -> list[str]:
    """Stub — production calls
    ``mcp__dataforseo__dataforseo_labs_google_keywords_for_site``
    with the project's ``dataforseo.location_code`` /
    ``dataforseo.language_code`` and returns the top-20 keyword strings."""
    return []
