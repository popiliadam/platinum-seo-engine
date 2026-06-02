#!/usr/bin/env python3
"""
sf_projection.py — pure-function projection of raw Screaming Frog CSV
exports into the six master.xlsx logical sheets sourced by an SF crawl.

A live SF crawl writes ~22 raw CSVs into
``{ws}/projects/{slug}/sf-exports/{date}/raw/``. ``sf_import.py`` projects a
subset of them into six schema-locked sheets:

  - crawl_sitemap  ← internal_all.csv (+ sitemaps_all.csv summary count)
  - redirect_404   ← response_codes_all.csv (internal 3xx/4xx only)
  - schema         ← structured_data_all.csv (grouped by Type-1)
  - on_page_audit  ← page_titles_all + meta_description_all + h1_all (merged
                     per-URL, then projected via the live-proven
                     on_page_audit_transform.transform(live_findings=...))
  - tech_seo       ← issues_overview_report.csv (routed via sf_issue_taxonomy)
  - robots_txt     ← issues_overview_report.csv (routed via sf_issue_taxonomy)

EVERY row this module emits is shaped for direct
``scripts.excel.transaction.append/replace`` — i.e. schema-valid against
``schemas/master-excel.schema.json`` — so the projection is verifiable
WITHOUT writing the workbook (see the schema cross-check test).

Pure-function discipline (mirrors tech_audit_transform / on_page_audit_transform):
  - No state mutation; never mutates the parsed CSV rows.
  - No master.xlsx writes; no scripts.excel imports.
  - Idempotent: same raw_dir → same output.
  - BOM-safe CSV reads (SF prefixes a UTF-8 BOM on some exports).
  - No DFS dependency; no paid-MCP calls.
  - No slug literals (plugin-agnostic).

Refs: schemas/master-excel.schema.json (six sheet shapes + statusEnum /
severityEnum $defs), scripts/util/sf_issue_taxonomy.py (issue routing SSOT),
scripts/discovery/on_page_audit_transform.py (on_page_audit projection
reuse), scripts/discovery/tech_audit_transform.py::_clean_key (BOM-safe key
pattern), scripts/excel/transaction.py (write contract these rows satisfy).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when invoked as a CLI module or imported in tests.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discovery import on_page_audit_transform as _opa  # noqa: E402
from scripts.util.sf_issue_taxonomy import (  # noqa: E402
    SHEET_TECH_SEO,
    SHEET_ROBOTS_TXT,
    route_sf_issue,
    sf_priority_to_severity,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The six logical sheets this projection produces (stable key order).
PROJECTED_SHEETS: tuple[str, ...] = (
    "crawl_sitemap",
    "redirect_404",
    "schema",
    "on_page_audit",
    "tech_seo",
    "robots_txt",
)

#: statusEnum values (master-excel.schema.json $defs.statusEnum) used here.
_STATUS_TODO = "TODO"
_STATUS_DONE = "DONE"
_STATUS_EXISTS = "EXISTS"
_STATUS_ONGOING = "ONGOING"

#: severity → priority bucket for tech_seo (CRITICAL/HIGH→P0, MEDIUM→P1, LOW→P2).
_PRIORITY_BY_SEVERITY: dict[str, str] = {
    "CRITICAL": "P0",
    "HIGH": "P0",
    "MEDIUM": "P1",
    "LOW": "P2",
}

#: Cap on free-text detail cells (Excel friendliness; SF Descriptions can be
#: very long). 300 chars is plenty for an operator-readable summary.
_DETAIL_CHAR_CAP = 300


# ---------------------------------------------------------------------------
# BOM-safe CSV reading
# ---------------------------------------------------------------------------

def _clean_key(key: Any) -> str:
    """Normalize a CSV-parsed column key: strip a leading UTF-8 BOM and any
    surrounding double-quotes.

    SF writes a BOM before the first header field on some exports
    (issues_overview_report.csv, redirect_chains.csv), so ``csv.DictReader``'s
    first key can arrive as ``'\\ufeff"Issue Name"'`` — the BOM precedes the
    opening quote, defeating csv's quote-stripping, so a naive
    ``row.get("Issue Name")`` returns ``None`` and the row silently drops.
    Reading with ``utf-8-sig`` avoids the BOM, but we normalize here too so a
    BOM-keyed row can never silently drop every field (live-caught 2026-06-02,
    reused from tech_audit_transform._clean_key).
    """
    return str(key or "").lstrip("﻿").strip().strip('"')


def read_csv_rows(path: Path) -> list[dict]:
    """Read a CSV file into a list of dicts with BOM-normalized keys.

    Uses ``utf-8-sig`` so a leading BOM is stripped, and additionally
    normalizes every key via :func:`_clean_key` so a BOM-prefixed first column
    can never silently drop a field. Returns ``[]`` for a missing or empty
    file (an absent optional CSV is not a projection error).
    """
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{_clean_key(k): v for k, v in row.items()} for row in reader]


def _s(v: Any) -> str:
    """Trimmed string of a CSV value (``None`` → '')."""
    if v is None:
        return ""
    return str(v).strip()


def _to_int(v: Any) -> int:
    """Parse an int from a CSV cell; blank / unparseable → 0."""
    s = _s(v)
    if not s:
        return 0
    try:
        return int(round(float(s)))
    except (TypeError, ValueError):
        return 0


def _content_type(row: dict) -> str:
    """Bare lower-cased content type (drops any ``; charset=...`` suffix)."""
    return _s(row.get("Content Type")).split(";")[0].strip().lower()


def _truncate(text: str, cap: int = _DETAIL_CHAR_CAP) -> str:
    """Trim a long free-text cell to ``cap`` chars (no mid-word ellipsis —
    a hard slice keeps it deterministic and well under the Excel limit)."""
    if len(text) <= cap:
        return text
    return text[:cap]


# ---------------------------------------------------------------------------
# Mapper 1 — crawl_sitemap (from internal_all.csv + sitemaps_all.csv count)
# ---------------------------------------------------------------------------

def map_crawl_sitemap(
    internal_rows: Sequence[dict],
    sitemap_count: int,
) -> list[dict]:
    """Project internal_all.csv rows → crawl_sitemap rows.

    Emits Crawl summary rows (total / html / indexable / non_indexable /
    image / css / js counts), a Sitemap summary row (crawled sitemap-URL
    count), and one URL row per text/html page. Schema columns:
    ``{category, metric, value, status, action}``.
    """
    total = len(internal_rows)
    html_rows = [r for r in internal_rows if "text/html" in _s(r.get("Content Type")).lower()]
    html = len(html_rows)
    indexable = sum(1 for r in internal_rows if _s(r.get("Indexability")) == "Indexable")
    non_indexable = sum(
        1 for r in internal_rows if _s(r.get("Indexability")) == "Non-Indexable"
    )
    image_assets = sum(1 for r in internal_rows if _content_type(r).startswith("image/"))
    css_files = sum(1 for r in internal_rows if "text/css" in _content_type(r))
    js_files = sum(1 for r in internal_rows if "javascript" in _content_type(r))

    rows: list[dict] = [
        _crawl_summary("total_urls_discovered", total, _STATUS_DONE,
                       "Total URLs discovered by the crawl"),
        _crawl_summary("html_pages", html, _STATUS_DONE,
                       "HTML pages (text/html content type)"),
        _crawl_summary("indexable", indexable, _STATUS_DONE,
                       "URLs marked Indexable by SF"),
        _crawl_summary(
            "non_indexable", non_indexable,
            _STATUS_TODO if non_indexable > 0 else _STATUS_DONE,
            "Non-indexable URLs — review noindex/canonical/redirect cause"
            if non_indexable > 0 else "No non-indexable URLs",
        ),
        _crawl_summary("image_assets", image_assets, _STATUS_DONE,
                       "Image assets (image/* content type)"),
        _crawl_summary("css_files", css_files, _STATUS_DONE,
                       "CSS files (text/css content type)"),
        _crawl_summary("js_files", js_files, _STATUS_DONE,
                       "JavaScript files (javascript content type)"),
        {
            "category": "Sitemap",
            "metric": "crawled_count",
            "value": str(sitemap_count),
            "status": _STATUS_DONE,
            "action": "Sitemap URLs crawled from sitemaps_all.csv",
        },
    ]

    for r in html_rows:
        address = _s(r.get("Address"))
        is_indexable = _s(r.get("Indexability")) == "Indexable"
        rows.append({
            "category": "URL",
            "metric": "html_page",
            "value": address,
            "status": _STATUS_EXISTS if is_indexable else _STATUS_TODO,
            "action": (
                "Indexable page"
                if is_indexable
                else "Non-indexable — review crawl/index directives"
            ),
        })
    return rows


def _crawl_summary(metric: str, count: int, status: str, action: str) -> dict:
    """Build one Crawl-category summary row."""
    return {
        "category": "Crawl",
        "metric": metric,
        "value": str(count),
        "status": status,
        "action": action,
    }


# ---------------------------------------------------------------------------
# Mapper 2 — redirect_404 (from response_codes_all.csv)
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    """Network location (host) of a URL; '' if unparseable."""
    try:
        return urlparse(url).netloc.lower()
    except (ValueError, TypeError):
        return ""


def _derive_site_host(response_rows: Sequence[dict]) -> str | None:
    """Most common Address host across response_codes rows (the internal
    site host). Returns ``None`` when no host can be derived."""
    counts: dict[str, int] = {}
    for r in response_rows:
        h = _host(_s(r.get("Address")))
        if h:
            counts[h] = counts.get(h, 0) + 1
    if not counts:
        return None
    # Highest count wins; tie-break by host string for determinism.
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def map_redirect_404(
    response_rows: Sequence[dict],
    *,
    site_host: str | None = None,
) -> list[dict]:
    """Project response_codes_all.csv rows → redirect_404 rows.

    Keeps only internal (host == site_host) rows whose Status Code starts
    with ``3`` or ``4``. External hosts (e.g. maps.google) and 2xx rows are
    excluded. ``site_host`` defaults to the most common Address host. Schema
    columns: ``{url, inlinks, action, target_url, status}``.
    """
    host = site_host or _derive_site_host(response_rows)
    rows: list[dict] = []
    for r in response_rows:
        code = _s(r.get("Status Code"))
        if not code or code[0] not in ("3", "4"):
            continue
        address = _s(r.get("Address"))
        if host is not None and _host(address) != host:
            continue
        inlinks = _to_int(r.get("Inlinks"))
        is_3xx = code.startswith("3")
        target_url = _s(r.get("Redirect URL")) if is_3xx else ""
        if is_3xx:
            action = (
                f"3xx — point internal links directly to {target_url}"
                if target_url
                else "3xx redirect — point internal links directly to the target"
            )
        else:
            action = (
                "4xx broken — fix or 301 to a valid URL; "
                f"linked {inlinks}x internally"
            )
        rows.append({
            "url": address,
            "inlinks": inlinks,
            "action": action,
            "target_url": target_url,
            "status": _STATUS_TODO,
        })
    return rows


# ---------------------------------------------------------------------------
# Mapper 3 — schema (from structured_data_all.csv)
# ---------------------------------------------------------------------------

def _has_errors(value: Any) -> bool:
    """True when an SF Errors cell carries a non-zero error count."""
    return _s(value) not in ("", "0")


def map_schema(structured_rows: Sequence[dict]) -> list[dict]:
    """Project structured_data_all.csv rows → schema rows (grouped by Type-1).

    Per distinct Type-1 (blank skipped): one row with occurrence count and
    a status of ``ONGOING`` when any row of that type carries validation
    errors, else ``EXISTS``. Schema columns:
    ``{schema_type, status, location, scope, remaining_work}``.
    """
    by_type: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in structured_rows:
        t = _s(r.get("Type-1"))
        if not t:
            continue
        if t not in by_type:
            by_type[t] = []
            order.append(t)
        by_type[t].append(r)

    rows: list[dict] = []
    for t in order:
        group = by_type[t]
        n = len(group)
        has_err = any(_has_errors(r.get("Errors")) for r in group)
        remaining = "Validate against Schema.org"
        if has_err:
            remaining += "; fix validation errors"
        rows.append({
            "schema_type": t,
            "status": _STATUS_ONGOING if has_err else _STATUS_EXISTS,
            "location": f"global ({n} occurrences)",
            "scope": f"{n} occurrences",
            "remaining_work": remaining,
        })
    return rows


# ---------------------------------------------------------------------------
# Mapper 4 — on_page_audit (reuse on_page_audit_transform)
# ---------------------------------------------------------------------------

def _merge_on_page_rows(
    title_rows: Sequence[dict],
    meta_rows: Sequence[dict],
    h1_rows: Sequence[dict],
) -> list[dict]:
    """Merge the three single-column SF exports into per-URL dicts shaped for
    ``on_page_audit_transform``'s ``_sf_row_to_audit_row`` reader.

    Each staged file (page_titles_all / meta_description_all / h1_all) holds
    only its own column for a URL, but the transform reads ``Title 1`` /
    ``Meta Description 1`` / ``H1-1`` from ONE row — so we group by Address and
    build a single merged row carrying all three columns.
    """
    titles = {_s(r.get("Address")): _s(r.get("Title 1")) for r in title_rows}
    metas = {_s(r.get("Address")): _s(r.get("Meta Description 1")) for r in meta_rows}
    h1s = {_s(r.get("Address")): _s(r.get("H1-1")) for r in h1_rows}

    addresses: list[str] = []
    seen: set[str] = set()
    for src in (title_rows, meta_rows, h1_rows):
        for r in src:
            addr = _s(r.get("Address"))
            if addr and addr not in seen:
                seen.add(addr)
                addresses.append(addr)

    return [
        {
            "Address": addr,
            "Title 1": titles.get(addr, ""),
            "Meta Description 1": metas.get(addr, ""),
            "H1-1": h1s.get(addr, ""),
        }
        for addr in addresses
    ]


def map_on_page_audit(
    title_rows: Sequence[dict],
    meta_rows: Sequence[dict],
    h1_rows: Sequence[dict],
) -> list[dict]:
    """Project the three SF on-page exports → on_page_audit rows.

    Merges the per-column exports per-URL, then delegates to the live-proven
    ``on_page_audit_transform.transform({}, live_findings=merged)`` consumer
    (empty content_parsing → 0 DFS rows; every SF URL surfaces as an additive
    crawl-truth row). Schema columns: the 8 on_page_audit columns. Returns the
    schema-shaped row list (transform locks column order + drops extras).
    """
    merged = _merge_on_page_rows(title_rows, meta_rows, h1_rows)
    result = _opa.transform({}, live_findings=merged)
    return list(result["on_page_audit"])


# ---------------------------------------------------------------------------
# Mappers 5 + 6 — tech_seo + robots_txt (from issues_overview_report.csv)
# ---------------------------------------------------------------------------

def _issue_fields(row: dict) -> tuple[str, str, str, str, str]:
    """Extract (name, description, how_to_fix, urls, priority) from an SF
    Issues Overview row."""
    return (
        _s(row.get("Issue Name")),
        _s(row.get("Description")),
        _s(row.get("How To Fix")),
        _s(row.get("URLs")),
        _s(row.get("Issue Priority")),
    )


def map_tech_seo(issue_rows: Sequence[dict]) -> list[dict]:
    """Project issues_overview_report.csv rows → tech_seo rows.

    Keeps only rows that :func:`route_sf_issue` routes to ``tech_seo``; each
    becomes one row whose ``issue_category`` is one of the locked 5 enum
    values. Schema columns:
    ``{issue_category, detail, affected_urls, impact, resolution, priority}``.
    """
    rows: list[dict] = []
    for r in issue_rows:
        name, description, how_to_fix, urls, priority = _issue_fields(r)
        if not name:
            continue
        sheet, category = route_sf_issue(name)
        if sheet != SHEET_TECH_SEO or category is None:
            continue
        impact = sf_priority_to_severity(priority)
        detail = _truncate(f"{name} — {description}".strip(" —"))
        resolution = how_to_fix or "Review and remediate per SF issue report"
        rows.append({
            "issue_category": category,
            "detail": detail,
            "affected_urls": urls,
            "impact": impact,
            "resolution": resolution,
            "priority": _PRIORITY_BY_SEVERITY[impact],
        })
    return rows


def map_robots_txt(issue_rows: Sequence[dict]) -> list[dict]:
    """Project issues_overview_report.csv rows → robots_txt rows.

    Keeps only rows that :func:`route_sf_issue` routes to ``robots_txt``
    (security / directive / crawl-structure + unmatched fallback). Each gets a
    sequential ``R-NNN`` id over the robots-routed rows. Schema columns:
    ``{id, level, issue, detail, resolution}``.
    """
    rows: list[dict] = []
    seq = 0
    for r in issue_rows:
        name, description, how_to_fix, _urls, priority = _issue_fields(r)
        if not name:
            continue
        sheet, _category = route_sf_issue(name)
        if sheet != SHEET_ROBOTS_TXT:
            continue
        seq += 1
        resolution = how_to_fix or "Review and remediate per SF issue report"
        rows.append({
            "id": f"R-{seq:03d}",
            "level": sf_priority_to_severity(priority),
            "issue": name,
            "detail": _truncate(description),
            "resolution": resolution,
        })
    return rows


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def project_all(
    raw_dir: Path,
    *,
    site_host: str | None = None,
) -> dict[str, list[dict]]:
    """Project a directory of raw SF CSV exports → six master.xlsx sheets.

    Args:
        raw_dir: path to the SF crawl's ``.../raw/`` export directory.
        site_host: optional internal host for redirect_404 filtering. When
            ``None`` (default) it is auto-derived as the most common Address
            host in response_codes_all.csv.

    Returns:
        ``{"crawl_sitemap": [...], "redirect_404": [...], "schema": [...],
           "on_page_audit": [...], "tech_seo": [...], "robots_txt": [...]}`` —
        every row schema-valid for direct ``transaction.append/replace``.
    """
    raw = Path(raw_dir)

    internal_rows = read_csv_rows(raw / "internal_all.csv")
    sitemap_rows = read_csv_rows(raw / "sitemaps_all.csv")
    response_rows = read_csv_rows(raw / "response_codes_all.csv")
    structured_rows = read_csv_rows(raw / "structured_data_all.csv")
    title_rows = read_csv_rows(raw / "page_titles_all.csv")
    meta_rows = read_csv_rows(raw / "meta_description_all.csv")
    h1_rows = read_csv_rows(raw / "h1_all.csv")
    issue_rows = read_csv_rows(raw / "issues_overview_report.csv")

    return {
        "crawl_sitemap": map_crawl_sitemap(internal_rows, len(sitemap_rows)),
        "redirect_404": map_redirect_404(response_rows, site_host=site_host),
        "schema": map_schema(structured_rows),
        "on_page_audit": map_on_page_audit(title_rows, meta_rows, h1_rows),
        "tech_seo": map_tech_seo(issue_rows),
        "robots_txt": map_robots_txt(issue_rows),
    }


__all__: Iterable[str] = (
    "PROJECTED_SHEETS",
    "read_csv_rows",
    "map_crawl_sitemap",
    "map_redirect_404",
    "map_schema",
    "map_on_page_audit",
    "map_tech_seo",
    "map_robots_txt",
    "project_all",
)
