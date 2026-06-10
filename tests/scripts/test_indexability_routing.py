"""
tests/scripts/test_indexability_routing.py — FIX-I item I4 routing lock.

Regression lock for the "canonical-mismatch issue has no tech_seo category"
audit finding WITHOUT touching the ADR-028-locked tech_seo issue_category
5-enum.

Background: indexability-class Screaming Frog issues (canonical mismatch,
hreflang, robots directives, indexability, meta directives) do NOT fit the
tech_seo issue_category enum {Performance, Layout Stability, Meta Tags,
Structured Data, Accessibility}. The single-source router
`scripts.util.sf_issue_taxonomy.route_sf_issue` MUST send them to the
`robots_txt` sheet (a real home), never to `tech_seo` with an out-of-enum
category, and never silently drop them into the void. The tech-audit live
merge (`tech_audit_transform._live_finding_to_finding`) correspondingly
declines them (returns None) so a canonical issue can never produce an
out-of-enum tech_seo row.

This test characterises + locks that contract. It does NOT change the enum
(ADR-028) — it freezes the existing-correct routing so a future edit that
re-points an indexability issue into tech_seo (re-opening the out-of-enum
bug class) fails loudly.

Refs: scripts/util/sf_issue_taxonomy.py (route_sf_issue SSOT, ADR-028 enum),
scripts/discovery/tech_audit_transform.py (_live_finding_to_finding drop
path), schemas/master-excel.schema.json#tech_seo (locked 5-enum).
"""

from __future__ import annotations

import pytest

from scripts.util import sf_issue_taxonomy as tax
from scripts.discovery import tech_audit_transform as ta


# The indexability / directive issue classes the audit flagged as "no
# category" — each is a real SF Issue Name shape (prefix : detail).
INDEXABILITY_ISSUES = [
    "Canonical: Missing",
    "Canonicals: Canonicalised",
    "Canonical Link Element: Multiple Conflicting",
    "Hreflang: Missing Return Links",
    "Hreflang: Non-Canonical",
    "Directives: Noindex",
    "Directives: Nofollow",
    "Robots.txt: Blocked URL",
    "Indexability: Non-Indexable",
]


@pytest.mark.parametrize("issue_name", INDEXABILITY_ISSUES)
def test_indexability_issue_routes_to_robots_txt(issue_name: str) -> None:
    """Every indexability-class issue routes to the robots_txt sheet with a
    None tech_seo category — a real home, never an out-of-enum tech_seo row."""
    sheet, category = tax.route_sf_issue(issue_name)
    assert sheet == tax.SHEET_ROBOTS_TXT, (
        f"{issue_name!r} routed to {sheet!r}, expected robots_txt "
        "(canonical-bug-no-category regression)"
    )
    assert category is None, (
        f"{issue_name!r} produced tech_seo category {category!r}; "
        "indexability issues must carry NO tech_seo category"
    )


@pytest.mark.parametrize("issue_name", INDEXABILITY_ISSUES)
def test_indexability_issue_never_routes_to_tech_seo(issue_name: str) -> None:
    """The out-of-enum guard: an indexability issue must NEVER land in
    tech_seo (that is exactly the bug — a canonical issue with no valid
    issue_category enum value)."""
    sheet, _category = tax.route_sf_issue(issue_name)
    assert sheet != tax.SHEET_TECH_SEO


@pytest.mark.parametrize("issue_name", INDEXABILITY_ISSUES)
def test_indexability_issue_not_silently_dropped(issue_name: str) -> None:
    """'No category' must NOT mean 'lost'. The router always returns a real
    target sheet (robots_txt / redirect_404 / tech_seo), never (None, None)."""
    sheet, _category = tax.route_sf_issue(issue_name)
    assert sheet in {
        tax.SHEET_TECH_SEO, tax.SHEET_ROBOTS_TXT, tax.SHEET_REDIRECT_404,
    }, f"{issue_name!r} routed to an unknown/None sheet {sheet!r}"


@pytest.mark.parametrize("issue_name", INDEXABILITY_ISSUES)
def test_tech_audit_live_merge_declines_indexability(issue_name: str) -> None:
    """The tech-audit live-merge maps one SF Issues-Overview row → a tech_seo
    _Finding ONLY when the router says tech_seo. For an indexability issue it
    must return None (declined) so the row never becomes an out-of-enum
    tech_seo category."""
    row = {
        "Issue Name": issue_name,
        "Issue Type": "Warning",
        "Issue Priority": "High",
        "URLs": "https://example.com/page",
        "Description": "indexability signal",
        "How To Fix": "review directive",
    }
    assert ta._live_finding_to_finding(row) is None


def test_tech_audit_transform_never_emits_out_of_enum_from_indexability() -> None:
    """End-to-end lock: feeding ONLY indexability issues as live_findings to
    the transform produces zero tech_seo rows (all declined) — and every row
    that IS produced stays within the schema-locked 5-enum."""
    live = [
        {
            "Issue Name": name,
            "Issue Priority": "High",
            "URLs": "https://example.com/p",
            "How To Fix": "fix",
        }
        for name in INDEXABILITY_ISSUES
    ]
    out = ta.transform(
        lighthouse_raw=None, content_parsing_raw=None, live_findings=live,
    )
    assert out["tech_seo"] == [], (
        "indexability-only live_findings must yield zero tech_seo rows "
        "(they route to robots_txt, not tech_seo)"
    )
    for r in out["tech_seo"]:  # defensive: none, but lock the invariant
        assert r["issue_category"] in tax.TECH_SEO_CATEGORIES
