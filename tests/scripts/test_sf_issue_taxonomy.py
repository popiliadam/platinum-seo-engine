#!/usr/bin/env python3
"""Tests for scripts/util/sf_issue_taxonomy.py — SF Issue Name routing SSOT.

Covers:
  - Each of the 13 real demo-aluminum Issue-Name PREFIXES routes per the
    locked table (read from issues_overview_report.csv).
  - Ordering: specific rules (structured data / performance / layout /
    accessibility / meta) win over the broad robots_txt keywords.
  - sf_priority_to_severity case/space-insensitivity + MEDIUM default.
  - Unmatched issue falls back to (robots_txt, None) — never crashes, never
    out-of-enum.
  - Every tech_seo-routed category is one of the schema-locked 5 values.
"""

from __future__ import annotations

import csv

import pytest

from scripts.util import sf_issue_taxonomy as tax
from tests._live_fixtures import live_project_dir, live_slug, requires_live

# Real staged SF crawl (live fixtures under $PSEO_WORKSPACE_ROOT; gitignored
# ~1GB raw crawls, never committed — present on the operator's machine, absent
# on CI / fresh clones). The hermetic routing tests above already give full
# logic coverage; the three "real-CSV" tests below guard cleanly when the
# fixture is absent (engine stays plugin-agnostic — no project data committed
# here). Matches the repo's skip-when-fixture-absent pattern (cf. SF MCP smoke).
_RAW_DIR = live_project_dir(live_slug("demo-aluminum-ca")) / "sf-exports" / "2026-06-02" / "raw"
_ISSUES_CSV = _RAW_DIR / "issues_overview_report.csv"

_requires_real_csv = requires_live(
    _ISSUES_CSV, "staged demo-aluminum-ca SF issues_overview_report.csv"
)


def _read_issue_rows() -> list[dict]:
    with _ISSUES_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return [
            {k.lstrip("﻿").strip().strip('"'): v for k, v in row.items()}
            for row in csv.DictReader(fh)
        ]


# ---------------------------------------------------------------------------
# sf_priority_to_severity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Critical", "CRITICAL"),
    ("High", "HIGH"),
    ("Medium", "MEDIUM"),
    ("Low", "LOW"),
    ("  high  ", "HIGH"),   # whitespace tolerant
    ("LOW", "LOW"),         # case-insensitive
    ("low", "LOW"),
])
def test_priority_to_severity_known(raw: str, expected: str) -> None:
    assert tax.sf_priority_to_severity(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "bogus", "P1", 0])
def test_priority_to_severity_defaults_medium(raw: object) -> None:
    """Blank / unrecognised priority degrades to MEDIUM (never out-of-enum)."""
    assert tax.sf_priority_to_severity(raw) == "MEDIUM"


def test_severity_always_in_enum() -> None:
    severity_enum = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    for raw in ["Critical", "High", "Medium", "Low", None, "weird", "  "]:
        assert tax.sf_priority_to_severity(raw) in severity_enum


# ---------------------------------------------------------------------------
# route_sf_issue — focused per-prefix routing table (13 real prefixes)
# ---------------------------------------------------------------------------
#
# One representative real Issue Name per prefix family present in the
# demo-aluminum crawl, with its locked (sheet, category) expectation.
_PREFIX_ROUTING_CASES = [
    # Structured Data — wins over the broad robots keywords.
    ("Structured Data: Validation Errors", "tech_seo", "Structured Data"),
    # Performance — PageSpeed + image weight.
    ("PageSpeed: Reduce Unused CSS", "tech_seo", "Performance"),
    ("Images: Over 100 kB", "tech_seo", "Performance"),
    # Layout Stability — missing size attributes.
    ("Images: Missing Size Attributes", "tech_seo", "Layout Stability"),
    # Accessibility — alt attribute / alt text / anchor text.
    ("Images: Missing Alt Attribute", "tech_seo", "Accessibility"),
    ("Images: Missing Alt Text", "tech_seo", "Accessibility"),
    ("Links: Internal Outlinks With No Anchor Text", "tech_seo", "Accessibility"),
    # Meta Tags — descriptions / titles / headings / content.
    ("Meta Description: Missing", "tech_seo", "Meta Tags"),
    ("Page Titles: Over 60 Characters", "tech_seo", "Meta Tags"),
    ("H1: Missing", "tech_seo", "Meta Tags"),
    ("H2: Multiple", "tech_seo", "Meta Tags"),
    ("Content: Low Content Pages", "tech_seo", "Meta Tags"),
    # robots_txt — security / url / pagination / crawl depth.
    ("Security: Missing HSTS Header", "robots_txt", None),
    ("URL: Non ASCII Characters", "robots_txt", None),
    ("Pagination: Pagination URL Not in Anchor Tag", "robots_txt", None),
    ("Links: Pages With High Crawl Depth", "robots_txt", None),
    # redirect_404 — Response Codes summary (caller SKIPS).
    ("Response Codes: Internal Redirection (3xx)", "redirect_404", None),
    ("Response Codes: Internal Client Error (4xx)", "redirect_404", None),
]


@pytest.mark.parametrize("issue_name,sheet,category", _PREFIX_ROUTING_CASES)
def test_route_real_prefix(issue_name: str, sheet: str, category) -> None:
    assert tax.route_sf_issue(issue_name) == (sheet, category)


def test_ordering_structured_data_beats_robots() -> None:
    """'Structured Data' contains no robots keyword, but assert it is checked
    before robots so a future 'Structured Data: ... canonical ...' label can
    not be mis-routed."""
    sheet, cat = tax.route_sf_issue("Structured Data: Missing canonical hint")
    assert (sheet, cat) == ("tech_seo", "Structured Data")


def test_ordering_image_weight_beats_robots() -> None:
    """'Images: Over 100 kB' must hit Performance, not robots."""
    assert tax.route_sf_issue("Images: Over 100 kB") == ("tech_seo", "Performance")


def test_unmatched_falls_back_to_robots() -> None:
    """A totally unknown issue never crashes and never returns out-of-enum."""
    sheet, cat = tax.route_sf_issue("Totally Novel SF Issue 9000")
    assert sheet == "robots_txt"
    assert cat is None


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_issue_name_routes_robots(blank) -> None:
    assert tax.route_sf_issue(blank) == ("robots_txt", None)


def test_route_case_insensitive() -> None:
    assert tax.route_sf_issue("PAGESPEED: REDUCE UNUSED CSS") == (
        "tech_seo", "Performance",
    )


# ---------------------------------------------------------------------------
# Real-CSV: every row routes, split matches expectations, no out-of-enum
# ---------------------------------------------------------------------------

@_requires_real_csv
def test_all_real_issues_route_without_crash() -> None:
    rows = _read_issue_rows()
    assert len(rows) == 42, "expected 42 real SF issues in the staged fixture"
    for r in rows:
        sheet, cat = tax.route_sf_issue(r["Issue Name"])
        assert sheet in {"tech_seo", "robots_txt", "redirect_404"}
        if sheet == "tech_seo":
            assert cat in tax.TECH_SEO_CATEGORIES
        else:
            assert cat is None


@_requires_real_csv
def test_real_routing_split_matches_expectation() -> None:
    """tech_seo=30, robots_txt=9, redirect_404=3 across the 42 rows."""
    rows = _read_issue_rows()
    split = {"tech_seo": 0, "robots_txt": 0, "redirect_404": 0}
    for r in rows:
        sheet, _cat = tax.route_sf_issue(r["Issue Name"])
        split[sheet] += 1
    assert split == {"tech_seo": 30, "robots_txt": 9, "redirect_404": 3}


@_requires_real_csv
def test_real_tech_seo_categories_all_in_enum() -> None:
    rows = _read_issue_rows()
    cats = set()
    for r in rows:
        sheet, cat = tax.route_sf_issue(r["Issue Name"])
        if sheet == "tech_seo":
            cats.add(cat)
    assert cats <= set(tax.TECH_SEO_CATEGORIES)
    assert cats, "expected at least one tech_seo-routed category"
