#!/usr/bin/env python3
"""Tests for scripts/ingestion/sf_projection.py — raw SF CSV → 6 master.xlsx
sheet projections.

The headline guarantee: every row of every sheet returned by
``project_all`` on the REAL staged 22-CSV crawl validates against
``schemas/master-excel.schema.json`` (via transaction._build_row_validator),
proving the projection is ``transaction.append/replace``-safe WITHOUT writing
the workbook.

Also asserts the live-proven rowcounts / presence counts / routing split, and
exercises each mapper in isolation with tiny hermetic fixtures (tmp_path).
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pytest

from scripts.excel import transaction
from scripts.ingestion import sf_projection as P
from tests._live_fixtures import live_project_dir

# Real staged SF crawl (live fixtures, 22 CSVs, under $PSEO_WORKSPACE_ROOT;
# gitignored — absent on CI / fresh clones, where the real_dir_available
# fixture skips the live-CSV tests cleanly).
_RAW_DIR = live_project_dir("aluminumstation-ca") / "sf-exports" / "2026-06-02" / "raw"

_SEVERITY_ENUM = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
_STATUS_ENUM = {"TODO", "ONGOING", "EXISTS", "DONE", "BLOCKED", "DEFERRED", "CANCELED"}
_TECH_ENUM = {"Performance", "Layout Stability", "Meta Tags",
              "Structured Data", "Accessibility"}


@pytest.fixture(scope="module")
def real_dir_available() -> bool:
    return _RAW_DIR.is_dir() and (_RAW_DIR / "internal_all.csv").exists()


@pytest.fixture(scope="module")
def projected(real_dir_available) -> dict:
    if not real_dir_available:
        pytest.skip(f"staged SF fixtures not present at {_RAW_DIR}")
    return P.project_all(_RAW_DIR)


# ---------------------------------------------------------------------------
# MANDATORY schema cross-check — every row of every sheet is write-safe
# ---------------------------------------------------------------------------

def test_every_projected_row_is_schema_valid(projected: dict) -> None:
    """For EVERY row of EVERY sheet, the row validates against the master
    schema (zero ValidationError) — proving transaction.append/replace would
    accept it without writing the workbook."""
    schema = transaction._load_schema(str(transaction._DEFAULT_SCHEMA_PATH))
    total_rows = 0
    for sheet in P.PROJECTED_SHEETS:
        validator = transaction._build_row_validator(schema, sheet)
        rows = projected[sheet]
        for idx, row in enumerate(rows):
            errors = list(validator.iter_errors(row))
            assert not errors, (
                f"{sheet}[{idx}] schema-invalid: "
                f"{[e.message for e in errors]} | row={row!r}"
            )
            total_rows += 1
    assert total_rows > 0, "expected projected rows to validate"


def test_projected_rows_pass_formula_and_length_gates(projected: dict) -> None:
    """The transaction.py formula + cell-length gates also pass (no '=' prefix,
    nothing over the 32767 cap)."""
    for sheet in P.PROJECTED_SHEETS:
        rows = projected[sheet]
        # These raise on violation; absence of an exception is the assertion.
        transaction._check_formula_policy(rows)
        transaction._check_cell_lengths(rows)


# ---------------------------------------------------------------------------
# Real-CSV rowcount expectations
# ---------------------------------------------------------------------------

def test_project_all_returns_six_sheets(projected: dict) -> None:
    assert set(projected.keys()) == set(P.PROJECTED_SHEETS)


def test_crawl_sitemap_rowcounts(projected: dict) -> None:
    cs = projected["crawl_sitemap"]
    cats = Counter(r["category"] for r in cs)
    # 7 Crawl summary metrics + 1 Sitemap summary + 66 per-URL html rows.
    assert cats["Crawl"] == 7
    assert cats["Sitemap"] == 1
    assert cats["URL"] == 66
    assert len(cs) == 74
    # Verify the live-proven summary numbers.
    by_metric = {r["metric"]: r["value"] for r in cs if r["category"] != "URL"}
    assert by_metric["total_urls_discovered"] == "1776"
    assert by_metric["html_pages"] == "66"
    assert by_metric["indexable"] == "1768"
    assert by_metric["non_indexable"] == "8"
    assert by_metric["image_assets"] == "1630"
    assert by_metric["css_files"] == "65"
    assert by_metric["js_files"] == "15"
    assert by_metric["crawled_count"] == "66"


def test_crawl_sitemap_non_indexable_status_todo(projected: dict) -> None:
    """non_indexable > 0 → TODO status (flags it for review)."""
    cs = projected["crawl_sitemap"]
    row = next(r for r in cs if r["metric"] == "non_indexable")
    assert row["status"] == "TODO"


def test_crawl_sitemap_url_rows_status_enum(projected: dict) -> None:
    cs = projected["crawl_sitemap"]
    url_rows = [r for r in cs if r["category"] == "URL"]
    for r in url_rows:
        assert r["status"] in {"EXISTS", "TODO"}
        assert r["value"].startswith("http")


def test_redirect_404_internal_only(projected: dict) -> None:
    """~8 internal 3xx/4xx rows; external hosts excluded."""
    r404 = projected["redirect_404"]
    assert len(r404) == 8
    # All rows are on the internal host (no maps.google / youtube etc).
    hosts = {P._host(r["url"]) for r in r404}
    assert hosts == {"aluminumstation.com"}
    # 7 are 3xx with a target_url, 1 (portfolio) is 4xx with empty target.
    with_target = [r for r in r404 if r["target_url"]]
    without_target = [r for r in r404 if not r["target_url"]]
    assert len(with_target) == 7
    assert len(without_target) == 1
    assert without_target[0]["url"].endswith("/portfolio/")
    for r in r404:
        assert r["status"] == "TODO"
        assert isinstance(r["inlinks"], int)


def test_redirect_404_excludes_external_hosts(projected: dict) -> None:
    """External (maps.google / youtube / fonts.googleapis) 3xx/4xx never leak."""
    r404 = projected["redirect_404"]
    for r in r404:
        assert "google.com" not in P._host(r["url"]) or P._host(r["url"]) == "aluminumstation.com"
        assert "youtube" not in P._host(r["url"])


def test_schema_two_rows_exists(projected: dict) -> None:
    sch = projected["schema"]
    assert len(sch) == 2
    by_type = {r["schema_type"]: r for r in sch}
    assert set(by_type) == {"Article", "BreadcrumbList"}
    # 0 errors in the fixture → both EXISTS.
    assert by_type["Article"]["status"] == "EXISTS"
    assert by_type["BreadcrumbList"]["status"] == "EXISTS"
    assert by_type["Article"]["scope"] == "13 occurrences"
    assert by_type["BreadcrumbList"]["scope"] == "45 occurrences"


def test_on_page_audit_presence_counts(projected: dict) -> None:
    """58 rows; in_title=58, in_meta=26, in_h1=38 (live-proven 2026-06-02)."""
    op = projected["on_page_audit"]
    assert len(op) == 58
    assert sum(1 for r in op if r["in_title"]) == 58
    assert sum(1 for r in op if r["in_meta"]) == 26
    assert sum(1 for r in op if r["in_h1"]) == 38
    # Shaped to exactly the 8 schema columns.
    from scripts.discovery.on_page_audit_transform import ON_PAGE_AUDIT_COLUMNS
    for r in op:
        assert tuple(r.keys()) == ON_PAGE_AUDIT_COLUMNS


def test_tech_seo_rowcount_and_enums(projected: dict) -> None:
    ts = projected["tech_seo"]
    assert len(ts) == 30
    for r in ts:
        assert r["issue_category"] in _TECH_ENUM
        assert r["impact"] in _SEVERITY_ENUM
        assert r["priority"] in {"P0", "P1", "P2"}
        assert r["detail"]
        assert len(r["detail"]) <= 300


def test_robots_txt_rowcount_and_ids(projected: dict) -> None:
    rt = projected["robots_txt"]
    assert len(rt) == 9
    # Sequential R-001..R-009 ids.
    ids = [r["id"] for r in rt]
    assert ids == [f"R-{i:03d}" for i in range(1, 10)]
    for r in rt:
        assert r["level"] in _SEVERITY_ENUM
        assert r["issue"]
        assert len(r["detail"]) <= 300


# ---------------------------------------------------------------------------
# Hermetic per-mapper tests (tmp_path fixtures — no live dir dependency)
# ---------------------------------------------------------------------------

def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def test_map_crawl_sitemap_counts_content_types() -> None:
    internal = [
        {"Address": "https://x.com/a", "Content Type": "text/html; charset=utf-8",
         "Indexability": "Indexable"},
        {"Address": "https://x.com/b", "Content Type": "text/html",
         "Indexability": "Non-Indexable"},
        {"Address": "https://x.com/i.jpg", "Content Type": "image/jpeg",
         "Indexability": "Indexable"},
        {"Address": "https://x.com/s.css", "Content Type": "text/css",
         "Indexability": "Indexable"},
        {"Address": "https://x.com/s.js", "Content Type": "application/javascript",
         "Indexability": "Indexable"},
    ]
    rows = P.map_crawl_sitemap(internal, sitemap_count=3)
    by_metric = {r["metric"]: r for r in rows if r["category"] != "URL"}
    assert by_metric["total_urls_discovered"]["value"] == "5"
    assert by_metric["html_pages"]["value"] == "2"
    assert by_metric["indexable"]["value"] == "4"
    assert by_metric["non_indexable"]["value"] == "1"
    assert by_metric["non_indexable"]["status"] == "TODO"
    assert by_metric["image_assets"]["value"] == "1"
    assert by_metric["css_files"]["value"] == "1"
    assert by_metric["js_files"]["value"] == "1"
    assert by_metric["crawled_count"]["value"] == "3"
    # 2 html → 2 URL rows; the non-indexable one is TODO.
    url_rows = [r for r in rows if r["category"] == "URL"]
    assert len(url_rows) == 2
    statuses = {r["value"]: r["status"] for r in url_rows}
    assert statuses["https://x.com/a"] == "EXISTS"
    assert statuses["https://x.com/b"] == "TODO"


def test_map_crawl_sitemap_zero_non_indexable_is_done() -> None:
    internal = [
        {"Address": "https://x.com/a", "Content Type": "text/html",
         "Indexability": "Indexable"},
    ]
    rows = P.map_crawl_sitemap(internal, sitemap_count=1)
    ni = next(r for r in rows if r["metric"] == "non_indexable")
    assert ni["status"] == "DONE"


def test_map_redirect_404_filters_and_classifies() -> None:
    resp = [
        {"Address": "https://site.com/ok", "Status Code": "200",
         "Inlinks": "10", "Redirect URL": ""},
        {"Address": "https://site.com/old", "Status Code": "301",
         "Inlinks": "5", "Redirect URL": "https://site.com/new"},
        {"Address": "https://site.com/gone", "Status Code": "404",
         "Inlinks": "3", "Redirect URL": ""},
        {"Address": "https://maps.google.com/x", "Status Code": "301",
         "Inlinks": "1", "Redirect URL": "https://maps.google.com/y"},
    ]
    rows = P.map_redirect_404(resp, site_host="site.com")
    urls = {r["url"] for r in rows}
    # 200 dropped, external dropped; only the internal 301 + 404 remain.
    assert urls == {"https://site.com/old", "https://site.com/gone"}
    redirect = next(r for r in rows if r["url"].endswith("/old"))
    assert redirect["target_url"] == "https://site.com/new"
    assert "3xx" in redirect["action"]
    broken = next(r for r in rows if r["url"].endswith("/gone"))
    assert broken["target_url"] == ""
    assert "4xx" in broken["action"]
    assert broken["inlinks"] == 3


def test_map_redirect_404_auto_derives_host() -> None:
    resp = [
        {"Address": "https://main.com/a", "Status Code": "301",
         "Inlinks": "1", "Redirect URL": "https://main.com/b"},
        {"Address": "https://main.com/c", "Status Code": "200",
         "Inlinks": "1", "Redirect URL": ""},
        {"Address": "https://main.com/d", "Status Code": "200",
         "Inlinks": "1", "Redirect URL": ""},
        {"Address": "https://ext.com/x", "Status Code": "404",
         "Inlinks": "1", "Redirect URL": ""},
    ]
    # No site_host → derive most common (main.com); ext.com excluded.
    rows = P.map_redirect_404(resp)
    assert {r["url"] for r in rows} == {"https://main.com/a"}


def test_map_schema_groups_and_flags_errors() -> None:
    structured = [
        {"Address": "https://x.com/1", "Type-1": "Article", "Errors": "0"},
        {"Address": "https://x.com/2", "Type-1": "Article", "Errors": "2"},
        {"Address": "https://x.com/3", "Type-1": "Product", "Errors": "0"},
        {"Address": "https://x.com/4", "Type-1": "", "Errors": "0"},  # skipped
    ]
    rows = P.map_schema(structured)
    by_type = {r["schema_type"]: r for r in rows}
    assert set(by_type) == {"Article", "Product"}
    # Article has an errored row → ONGOING + fix note.
    assert by_type["Article"]["status"] == "ONGOING"
    assert "fix validation errors" in by_type["Article"]["remaining_work"]
    assert by_type["Article"]["scope"] == "2 occurrences"
    # Product clean → EXISTS.
    assert by_type["Product"]["status"] == "EXISTS"


def test_map_on_page_audit_merges_three_exports() -> None:
    titles = [{"Address": "https://x.com/a", "Title 1": "Title A"}]
    metas = [{"Address": "https://x.com/a", "Meta Description 1": "Meta A"}]
    h1s = [{"Address": "https://x.com/a", "H1-1": "H1 A"}]
    rows = P.map_on_page_audit(titles, metas, h1s)
    assert len(rows) == 1
    row = rows[0]
    assert row["in_title"] is True
    assert row["in_meta"] is True
    assert row["in_h1"] is True


def test_map_on_page_audit_presence_from_blank_columns() -> None:
    """A URL present only in titles (blank meta/h1) → in_meta/in_h1 False."""
    titles = [{"Address": "https://x.com/a", "Title 1": "Has Title"}]
    rows = P.map_on_page_audit(titles, [], [])
    assert len(rows) == 1
    assert rows[0]["in_title"] is True
    assert rows[0]["in_meta"] is False
    assert rows[0]["in_h1"] is False


def test_map_tech_seo_and_robots_split() -> None:
    issues = [
        {"Issue Name": "PageSpeed: Reduce Unused CSS", "Issue Priority": "Medium",
         "URLs": "47", "Description": "Big CSS", "How To Fix": "Trim CSS"},
        {"Issue Name": "Security: Missing HSTS Header", "Issue Priority": "Low",
         "URLs": "1768", "Description": "No HSTS", "How To Fix": "Add header"},
        {"Issue Name": "Response Codes: Internal Redirection (3xx)",
         "Issue Priority": "Low", "URLs": "7", "Description": "x", "How To Fix": ""},
        {"Issue Name": "", "Issue Priority": "Low", "URLs": "1",
         "Description": "skip", "How To Fix": ""},  # no name → skipped both
    ]
    tech = P.map_tech_seo(issues)
    robots = P.map_robots_txt(issues)
    # PageSpeed → tech_seo Performance; response codes + security NOT in tech.
    assert len(tech) == 1
    assert tech[0]["issue_category"] == "Performance"
    assert tech[0]["impact"] == "MEDIUM"
    assert tech[0]["priority"] == "P1"
    assert tech[0]["resolution"] == "Trim CSS"
    # Security → robots_txt; response codes routed to redirect_404 (not robots).
    assert len(robots) == 1
    assert robots[0]["id"] == "R-001"
    assert robots[0]["issue"] == "Security: Missing HSTS Header"
    assert robots[0]["level"] == "LOW"


def test_map_tech_seo_resolution_fallback() -> None:
    issues = [
        {"Issue Name": "Meta Description: Missing", "Issue Priority": "Low",
         "URLs": "32", "Description": "Missing meta", "How To Fix": ""},
    ]
    tech = P.map_tech_seo(issues)
    assert tech[0]["resolution"] == "Review and remediate per SF issue report"


def test_read_csv_rows_handles_bom(tmp_path: Path) -> None:
    """A BOM-prefixed CSV reads with the first column key intact."""
    p = tmp_path / "bom.csv"
    # Write a UTF-8 BOM explicitly.
    p.write_bytes("﻿Issue Name,Issue Priority\nX,High\n".encode("utf-8"))
    rows = P.read_csv_rows(p)
    assert len(rows) == 1
    assert rows[0]["Issue Name"] == "X"
    assert rows[0]["Issue Priority"] == "High"


def test_read_csv_rows_missing_file_returns_empty(tmp_path: Path) -> None:
    assert P.read_csv_rows(tmp_path / "nope.csv") == []


def test_project_all_hermetic_end_to_end(tmp_path: Path) -> None:
    """A minimal hermetic raw_dir flows through project_all and the rows are
    schema-valid (a hermetic mirror of the real-CSV cross-check)."""
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_csv(raw / "internal_all.csv",
               ["Address", "Content Type", "Indexability"],
               [["https://h.com/a", "text/html", "Indexable"],
                ["https://h.com/i.jpg", "image/jpeg", "Indexable"]])
    _write_csv(raw / "sitemaps_all.csv", ["Address"], [["https://h.com/a"]])
    _write_csv(raw / "response_codes_all.csv",
               ["Address", "Status Code", "Inlinks", "Redirect URL"],
               [["https://h.com/old", "301", "2", "https://h.com/new"]])
    _write_csv(raw / "structured_data_all.csv",
               ["Address", "Type-1", "Errors"],
               [["https://h.com/a", "Article", "0"]])
    _write_csv(raw / "page_titles_all.csv",
               ["Address", "Title 1"], [["https://h.com/a", "T"]])
    _write_csv(raw / "meta_description_all.csv",
               ["Address", "Meta Description 1"], [["https://h.com/a", "M"]])
    _write_csv(raw / "h1_all.csv", ["Address", "H1-1"], [["https://h.com/a", "H"]])
    _write_csv(raw / "issues_overview_report.csv",
               ["Issue Name", "Issue Priority", "URLs", "Description", "How To Fix"],
               [["PageSpeed: Reduce Unused CSS", "Medium", "1", "d", "f"],
                ["Security: Missing HSTS Header", "Low", "1", "d", "f"]])

    out = P.project_all(raw)
    assert set(out.keys()) == set(P.PROJECTED_SHEETS)
    # Cross-check every hermetic row against the schema too.
    schema = transaction._load_schema(str(transaction._DEFAULT_SCHEMA_PATH))
    for sheet in P.PROJECTED_SHEETS:
        validator = transaction._build_row_validator(schema, sheet)
        for row in out[sheet]:
            assert not list(validator.iter_errors(row)), f"{sheet}: {row}"


def test_no_input_mutation() -> None:
    """Mappers never mutate their input rows."""
    internal = [{"Address": "https://x.com/a", "Content Type": "text/html",
                 "Indexability": "Indexable"}]
    snapshot = [dict(r) for r in internal]
    P.map_crawl_sitemap(internal, 1)
    assert internal == snapshot
