#!/usr/bin/env python3
"""
sf_issue_taxonomy.py — single-source routing for Screaming Frog
"Issues Overview" issue names into the master.xlsx logical sheets.

A live SF crawl emits an `issues_overview_report.csv` whose `Issue Name`
column carries free-text issue labels (e.g. ``Images: Over 100 kB``,
``Security: Missing HSTS Header``, ``Response Codes: Internal Redirection
(3xx)``). Two consumers need to project those issues into master.xlsx:

  - scripts/ingestion/sf_projection.py (this task) — bulk projection.
  - scripts/discovery/tech_audit_transform.py (Task D) — live-merge.

To keep the routing decision in ONE place (so the tech_seo
``issue_category`` enum can never drift out of the schema-locked 5 values),
both consumers import :func:`route_sf_issue` and :func:`sf_priority_to_severity`
from here.

ENUM CONTRACT (locked, NO schema change): master.xlsx#tech_seo
``issue_category`` is the 5-value enum
``{Performance, Layout Stability, Meta Tags, Structured Data,
Accessibility}``. SF issues that do not fit one of those five route to
``robots_txt`` (security / directive / crawl-structure issues) or
``redirect_404`` (Response-Codes issues, which the caller usually SKIPS
because redirect_404 is sourced per-URL from response_codes_all.csv, not
from the issue summary). An UNMATCHED issue falls back to ``robots_txt`` so
routing never crashes and never emits an out-of-enum tech_seo category.

Pure function discipline: no state, no I/O, idempotent, no slug literals.

Refs: schemas/master-excel.schema.json (tech_seo issue_category enum +
severityEnum $defs), scripts/discovery/tech_audit_transform.py
(_SF_PRIORITY_TO_SEVERITY pattern this module supersedes as the SSOT).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# severityEnum mapping (master-excel.schema.json $defs.severityEnum)
# ---------------------------------------------------------------------------

#: SF "Issue Priority" string (case-insensitive) → severityEnum. SF emits
#: High/Medium/Low (occasionally Critical); a blank/unrecognised priority
#: degrades to the default tier so a projection never emits a value outside
#: severityEnum.
_SF_PRIORITY_TO_SEVERITY: dict[str, str] = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}

#: severityEnum a blank / unrecognised Issue Priority degrades to.
_DEFAULT_SEVERITY = "MEDIUM"

# ---------------------------------------------------------------------------
# tech_seo issue_category enum (schema-locked 5 values)
# ---------------------------------------------------------------------------

CATEGORY_PERFORMANCE = "Performance"
CATEGORY_LAYOUT = "Layout Stability"
CATEGORY_META = "Meta Tags"
CATEGORY_STRUCTURED_DATA = "Structured Data"
CATEGORY_ACCESSIBILITY = "Accessibility"

TECH_SEO_CATEGORIES: tuple[str, ...] = (
    CATEGORY_PERFORMANCE,
    CATEGORY_LAYOUT,
    CATEGORY_META,
    CATEGORY_STRUCTURED_DATA,
    CATEGORY_ACCESSIBILITY,
)

# ---------------------------------------------------------------------------
# Target sheet labels
# ---------------------------------------------------------------------------

SHEET_TECH_SEO = "tech_seo"
SHEET_ROBOTS_TXT = "robots_txt"
SHEET_REDIRECT_404 = "redirect_404"

# ---------------------------------------------------------------------------
# Routing table — keyword → (sheet, tech_seo category). FIRST MATCH WINS, so
# specific rules (structured data / performance / layout / accessibility /
# meta) are checked BEFORE the broad robots_txt keywords; e.g. "Images: Over
# 100 kB" must hit Performance, not the "robots/canonical/..." catch-all.
# Each entry: (tuple-of-substrings, target_sheet, tech_seo_category_or_None).
# ---------------------------------------------------------------------------

_ROUTING_RULES: tuple[tuple[tuple[str, ...], str, str | None], ...] = (
    # Structured Data — most specific, checked first.
    (("structured data",), SHEET_TECH_SEO, CATEGORY_STRUCTURED_DATA),
    # Performance — PageSpeed / weight / LCP / speed / size savings.
    (
        ("pagespeed", "reduce unused", "page weight", "lcp",
         "speed index", "over 100 kb", "100 kb", "100kb"),
        SHEET_TECH_SEO, CATEGORY_PERFORMANCE,
    ),
    # Layout Stability — CLS / image dimensions / size attributes.
    (("size attribute", "layout shift", "cls"),
     SHEET_TECH_SEO, CATEGORY_LAYOUT),
    # Accessibility — alt text / anchor text / aria / contrast.
    (("alt attribute", "alt text", "anchor text",
      "accessibility", "aria", "contrast"),
     SHEET_TECH_SEO, CATEGORY_ACCESSIBILITY),
    # Meta Tags — titles / descriptions / headings / on-page content.
    (("meta description", "page title", "h1", "h2", "title",
      "content:", "low content", "readability"),
     SHEET_TECH_SEO, CATEGORY_META),
    # robots_txt — security / crawl-structure / directive issues.
    (("security", "non ascii", "non-ascii", "url:", "pagination",
      "crawl depth", "canonical", "robots", "hreflang", "indexab",
      "directive"),
     SHEET_ROBOTS_TXT, None),
    # redirect_404 — Response Codes summary (caller usually SKIPS — sourced
    # per-URL from response_codes_all.csv).
    (("response code",), SHEET_REDIRECT_404, None),
)


def sf_priority_to_severity(priority: object) -> str:
    """Map an SF ``Issue Priority`` value to the strict severityEnum.

    Case- and whitespace-insensitive. ``None`` / blank / unrecognised
    degrades to :data:`_DEFAULT_SEVERITY` (``"MEDIUM"``) so a projection can
    never emit a value outside ``{CRITICAL, HIGH, MEDIUM, LOW}``.
    """
    if priority is None:
        return _DEFAULT_SEVERITY
    key = str(priority).strip().lower()
    return _SF_PRIORITY_TO_SEVERITY.get(key, _DEFAULT_SEVERITY)


def route_sf_issue(issue_name: str) -> tuple[str | None, str | None]:
    """Route an SF ``Issue Name`` to a target master.xlsx sheet.

    Returns a ``(target_sheet, tech_seo_category)`` tuple:

      - ``("tech_seo", "<one of the 5 enum values>")`` for an issue that fits
        the locked tech_seo ``issue_category`` enum.
      - ``("robots_txt", None)`` for security / directive / crawl-structure
        issues AND for any UNMATCHED issue (safe fallback — never crashes,
        never emits an out-of-enum tech_seo category).
      - ``("redirect_404", None)`` for ``Response Codes:`` issues. The caller
        typically SKIPS these because redirect_404 is sourced per-URL from
        ``response_codes_all.csv``, not from the issue summary.

    Matching is case-insensitive substring; FIRST matching rule wins
    (rule order in :data:`_ROUTING_RULES` is significant — see module
    docstring). A blank issue name routes to ``("robots_txt", None)``.
    """
    name = (issue_name or "").strip().lower()
    if not name:
        return SHEET_ROBOTS_TXT, None
    for keywords, sheet, category in _ROUTING_RULES:
        if any(kw in name for kw in keywords):
            return sheet, category
    # Unmatched → safe fallback (robots_txt). Never out-of-enum tech_seo.
    return SHEET_ROBOTS_TXT, None


__all__ = (
    "sf_priority_to_severity",
    "route_sf_issue",
    "TECH_SEO_CATEGORIES",
    "CATEGORY_PERFORMANCE",
    "CATEGORY_LAYOUT",
    "CATEGORY_META",
    "CATEGORY_STRUCTURED_DATA",
    "CATEGORY_ACCESSIBILITY",
    "SHEET_TECH_SEO",
    "SHEET_ROBOTS_TXT",
    "SHEET_REDIRECT_404",
)
