"""Brand onboarding Stage A — Auto Discovery via DFS + Scrapling.

Covers ``scripts/meta/brand_onboarding_discovery.discover``:
  1. Returns the documented draft entries / topic candidates structure.
  2. WHOIS founding year proxy seeds an experience entry.
  3. Top-20 keywords from DFS labs become topic_candidates.
  4. DFS budget exhaustion short-circuits with DURUR awaiting_approval
     (F-16 plugin-agnostic boundary preserved — no autonomous spend).

The runtime MCP calls are stubbed at module level (``_fetch_*``,
``_budget_preflight``); test fixtures monkeypatch the stubs to return
canned values per scenario. This isolates Stage A logic from any
network or paid-MCP dependency.
"""

from __future__ import annotations

from scripts.meta.brand_onboarding_discovery import discover


def test_discover_returns_draft_entries_structure(
    mock_dfs, mock_scrapling, tmp_workspace_factory
) -> None:
    """Discover returns a dict with the three documented top-level keys."""
    tmp_workspace_factory(slug="test", profiles=["e-commerce"], domain="https://example.com/")
    result = discover(project_slug="test")
    assert result["status"] == "success"
    assert "draft_experience_entries" in result
    assert "draft_research_entries" in result
    assert "topic_candidates" in result
    assert isinstance(result["draft_experience_entries"], list)
    assert isinstance(result["draft_research_entries"], list)
    assert isinstance(result["topic_candidates"], list)


def test_discover_extracts_founding_year_from_whois(
    mock_dfs_whois_2018, mock_scrapling, tmp_workspace_factory
) -> None:
    """WHOIS creation 2018 → experience entry with founding_year hint
    and a claim_core mentioning the year."""
    tmp_workspace_factory(slug="test", profiles=["b2b-saas"])
    result = discover(project_slug="test")
    founding_entries = [
        e for e in result["draft_experience_entries"]
        if "founding" in e.get("hint", "")
    ]
    assert len(founding_entries) >= 1
    assert "2018" in founding_entries[0]["claim_core"]
    assert founding_entries[0]["source"] == "whois"
    assert founding_entries[0]["needs_review"] is True


def test_discover_returns_topic_candidates_from_keywords_for_site(
    mock_dfs_keywords_top20, mock_scrapling, tmp_workspace_factory
) -> None:
    """Top-20 keywords from DFS labs surface as topic_candidates."""
    tmp_workspace_factory(slug="test", profiles=["e-commerce"])
    result = discover(project_slug="test")
    assert len(result["topic_candidates"]) == 20
    assert all(isinstance(t, str) for t in result["topic_candidates"])
    assert "keyword-1" in result["topic_candidates"]


def test_discover_skips_paid_mcp_when_budget_exhausted(
    mock_dfs_budget_exhausted, tmp_workspace_factory
) -> None:
    """When DFS budget is exhausted, discovery DURURs awaiting_approval
    instead of silently spending (F-16 plugin-agnostic boundary)."""
    tmp_workspace_factory(slug="test", profiles=["e-commerce"])
    result = discover(project_slug="test")
    assert result["status"] == "awaiting_approval"
    assert "budget" in result["reason"].lower()


def test_discover_founding_year_uses_live_utc_year_not_hardcoded(
    mock_dfs_whois_2018, mock_scrapling, tmp_workspace_factory, monkeypatch
) -> None:
    """P1-12: the experience-claim 'X+ yıl' math must subtract founding_year
    from the LIVE UTC year, never a hardcoded constant. Pin the year to 2030
    and assert the claim reflects 2030-2018=12 (it would read 8 if 2026 were
    still hardcoded). This keeps the auto-discovery claim truthful every year
    without a code edit."""
    from scripts.meta import brand_onboarding_discovery as d

    monkeypatch.setattr(d, "_current_year", lambda: 2030, raising=False)
    tmp_workspace_factory(slug="test", profiles=["b2b-saas"])
    result = discover(project_slug="test")

    founding = [
        e for e in result["draft_experience_entries"]
        if "founding" in e.get("hint", "")
    ]
    assert len(founding) >= 1
    assert "12+ yıl" in founding[0]["claim_core"], (
        f"expected dynamic 2030-2018=12 yıl, got: {founding[0]['claim_core']!r}"
    )
