#!/usr/bin/env python3
"""
facet_nav_audit_transform.py — pure faceted-navigation / parameter governance.

Classifies every crawled URL's query parameters into the closed R-128 taxonomy,
quantifies index-bloat per class (R-129), and emits FN- findings + a
recommendation-only proposed robots.txt block (R-130) — see
``rules/tech-seo-governance.md``. SF Issues-Overview can say "you have pagination
issues"; this transform says "38% of the crawl is ``?sirala=`` sorts and 4,200 of
them are indexable" — URL-corpus-level quantification SF cannot give.

Pure-function discipline (mirrors sf_projection / tech_audit_transform):
  - No I/O in the compute path; never mutates the parsed CSV rows.
  - No master.xlsx writes (the SKILL orchestrator commits via sheet_merge).
  - BOM-safe header reads (``_clean_key``); deterministic output.
  - No DFS / paid-MCP calls (demand evidence comes from master.xlsx, passed in).
  - No slug literals (plugin-agnostic).

Platform seed dictionaries are HEURISTIC and deliberately conservative: generic
web + WooCommerce parameter names are seeded; anything the engine cannot verify
(Ticimax/Ideasoft/imagaza/non-English vocabularies) flows to the ``unknown``
class and the operator-triage finding — that is the DESIGNED path, not a gap.
Project-specific vocabularies are supplied via the optional per-project
``facet-policy.json`` override (``schemas/facet-policy.schema.json``), which wins
over every seed.

Refs: schemas/master-excel.schema.json (robots_txt 5-col shape + severityEnum),
scripts/util/sheet_merge.py (FN- merge-write the SKILL uses),
rules/tech-seo-governance.md (R-128 taxonomy / R-129 bloat / R-130 decision tree),
https://developers.google.com/crawling/docs/faceted-navigation.
"""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import parse_qsl, urlsplit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The closed R-128 parameter taxonomy.
PARAM_CLASSES: tuple[str, ...] = (
    "facet_filter",
    "sort",
    "pagination",
    "internal_search",
    "session_or_tracking",
    "functional",
    "unknown",
)

_DETAIL_CHAR_CAP = 300  # mirrors sf_projection._DETAIL_CHAR_CAP
_DEFAULT_URL_CAP = 250_000  # DURUR #3 — surface to manager, suggest chunking
_OFFENDER_SAMPLE = 5  # how many example URLs to name in a finding's detail

#: Generic (platform-agnostic) seed dictionary — well-known web parameters +
#: Google's own faceted-nav examples (color/size). HEURISTIC.
_GENERIC_SEEDS: dict[str, str] = {
    # session / tracking
    "gclid": "session_or_tracking", "fbclid": "session_or_tracking",
    "msclkid": "session_or_tracking", "mc_cid": "session_or_tracking",
    "mc_eid": "session_or_tracking", "_ga": "session_or_tracking",
    "ref": "session_or_tracking", "session": "session_or_tracking",
    "sid": "session_or_tracking",
    # sort
    "sort": "sort", "dir": "sort", "order": "sort", "orderby": "sort",
    "sortby": "sort", "sort_by": "sort",
    # pagination
    "page": "pagination", "paged": "pagination", "p": "pagination",
    "start": "pagination", "offset": "pagination", "pg": "pagination",
    # internal search
    "q": "internal_search", "s": "internal_search", "search": "internal_search",
    "query": "internal_search", "keyword": "internal_search", "k": "internal_search",
    # facet filters (universal e-commerce facet names; Google faceted-nav uses
    # color/size as canonical examples)
    "color": "facet_filter", "colour": "facet_filter", "size": "facet_filter",
    "brand": "facet_filter", "material": "facet_filter", "price": "facet_filter",
    "min_price": "facet_filter", "max_price": "facet_filter", "style": "facet_filter",
    "fit": "facet_filter", "gender": "facet_filter", "model": "facet_filter",
    "type": "facet_filter",
    # functional
    "add-to-cart": "functional", "wishlist": "functional", "compare": "functional",
}

#: Platform-specific seeds layered ON TOP of the generic set (HEURISTIC, only
#: where the parameter names are publicly documented for the platform).
_PLATFORM_SEEDS: dict[str, dict[str, str]] = {
    "wordpress": {"s": "internal_search", "paged": "pagination"},
    "wordpress+woocommerce": {
        "orderby": "sort", "min_price": "facet_filter", "max_price": "facet_filter",
        "add-to-cart": "functional", "product-page": "pagination",
        "rating_filter": "facet_filter", "s": "internal_search", "paged": "pagination",
    },
    # ticimax / ideasoft / imagaza / custom: NO verified platform vocabulary →
    # generic seeds only; unmatched params route to unknown-triage by design.
}

#: Classes whose indexable URLs are crawl-budget / index-bloat liabilities and
#: are therefore RECOMMENDED for a robots.txt disallow (R-129/R-130).
_BLOCKED_CLASSES = ("internal_search", "sort", "session_or_tracking")


# ---------------------------------------------------------------------------
# Exceptions (mirror tech_audit_transform's DURUR hierarchy)
# ---------------------------------------------------------------------------

class FacetNavAuditError(Exception):
    """Base class for facet-nav-audit transform errors."""


class FacetInternalMissingError(FacetNavAuditError):
    """internal_all.csv was not provided (DURUR #1)."""


class FacetSchemaDriftError(FacetNavAuditError):
    """Address column absent, or zero usable URLs parsed (DURUR #2 / #4)."""


class FacetUrlCapExceededError(FacetNavAuditError):
    """URL corpus exceeds the cap — chunk the crawl (DURUR #3)."""


# ---------------------------------------------------------------------------
# BOM-safe key handling
# ---------------------------------------------------------------------------

def _clean_key(key: Any) -> str:
    """Strip a leading UTF-8 BOM + surrounding quotes; lowercase. Mirrors
    sf_projection._clean_key so a BOM-keyed first column never silently drops."""
    return str(key or "").lstrip("﻿").strip().strip('"').lower()


def _normalize_row(row: dict) -> dict:
    """Return a copy of ``row`` with BOM/case-normalized keys (never mutates)."""
    return {_clean_key(k): v for k, v in row.items()}


def _truncate(text: str, cap: int = _DETAIL_CHAR_CAP) -> str:
    text = str(text or "")
    return text if len(text) <= cap else text[: cap - 1] + "…"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify_param(name: str, *, platform: str, overrides: dict[str, str]) -> str:
    """Classify one parameter name into the R-128 taxonomy (override → prefix →
    platform seed → generic seed → unknown)."""
    n = (name or "").strip().lower()
    if not n:
        return "unknown"
    if n in overrides:
        cls = overrides[n]
        return cls if cls in PARAM_CLASSES else "unknown"
    if n.startswith("utm_"):
        return "session_or_tracking"
    if n.startswith("filter_") or n.startswith("f_"):
        return "facet_filter"
    pseed = _PLATFORM_SEEDS.get(platform, {})
    if n in pseed:
        return pseed[n]
    if n in _GENERIC_SEEDS:
        return _GENERIC_SEEDS[n]
    return "unknown"


def _demand_tokens(params: list[tuple[str, str]]) -> set[str]:
    """Candidate demand tokens from a URL's params: names + values, lowercased
    and split on non-alphanumerics (so ``material=leather-brown`` yields
    {material, leather, brown, leather-brown})."""
    tokens: set[str] = set()
    for name, value in params:
        for piece in (name, value):
            p = (piece or "").strip().lower()
            if not p:
                continue
            tokens.add(p)
            for part in _split_alnum(p):
                tokens.add(part)
    return tokens


def _split_alnum(text: str) -> list[str]:
    out, cur = [], []
    for ch in text:
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


# ---------------------------------------------------------------------------
# Row reading helpers
# ---------------------------------------------------------------------------

def _is_indexable(nrow: dict) -> bool:
    """SF Indexability column == 'Indexable' (BOM/case-tolerant)."""
    return str(nrow.get("indexability") or "").strip().lower() == "indexable"


def _address(nrow: dict) -> str:
    return str(nrow.get("address") or "").strip()


# ---------------------------------------------------------------------------
# Public transform
# ---------------------------------------------------------------------------

def transform(
    internal_rows: Iterable[dict] | None,
    response_rows: Iterable[dict] | None = None,
    directives_rows: Iterable[dict] | None = None,
    canonical_rows: Iterable[dict] | None = None,
    pagination_rows: Iterable[dict] | None = None,
    demand_keywords: Iterable[str] | None = None,
    platform: str = "custom",
    url_patterns: list[dict] | None = None,
    policy_overrides: dict | None = None,
    *,
    unknown_param_threshold: int = 10,
    url_cap: int = _DEFAULT_URL_CAP,
) -> dict:
    """Classify the crawl's parameter space and emit FN- findings.

    ``response_rows`` / ``directives_rows`` / ``canonical_rows`` /
    ``pagination_rows`` / ``url_patterns`` are accepted for the documented v1
    contract and reserved for v1.1 enrichment (zero-result/soft-404 detection,
    path-segment facets); v1 classification is query-parameter-driven from
    ``internal_rows`` + ``demand_keywords`` (read from master.xlsx, zero paid
    calls). Returns ``{"robots_txt_rows", "metrics", "proposed_robots_block",
    "verdict"}``.
    """
    if internal_rows is None:
        raise FacetInternalMissingError(
            "internal_all.csv not provided — run sf-import or use live SF mode (DURUR #1)"
        )
    rows = list(internal_rows)
    if len(rows) > url_cap:
        raise FacetUrlCapExceededError(
            f"{len(rows)} URLs > cap {url_cap} — chunk the crawl (DURUR #3)"
        )

    norm = [_normalize_row(r) for r in rows]
    if rows and not any("address" in r for r in norm):
        raise FacetSchemaDriftError(
            "internal_all.csv has no 'Address' column — re-export with default "
            "data_fields or use live SF mode (DURUR #2)"
        )

    overrides = {
        str(k).strip().lower(): str(v).strip()
        for k, v in ((policy_overrides or {}).get("classifications") or {}).items()
    }
    indexable_facets = {
        str(p).strip().lower()
        for p in ((policy_overrides or {}).get("indexable_facets") or [])
    }
    demand = {str(t).strip().lower() for t in (demand_keywords or set()) if str(t).strip()}

    # --- per-URL classification + metric accumulation -----------------------
    total_urls = 0
    by_class: dict[str, dict] = {
        c: {"url_count": 0, "indexable": 0, "params": set()} for c in PARAM_CLASSES
    }
    unknown_offenders: list[str] = []
    facet_offenders: list[str] = []   # indexable facet URLs without demand
    blocked_param_names: set[str] = set()
    functional_param_names: set[str] = set()
    search_or_sort_tracking_offenders: list[str] = []

    for nrow in norm:
        addr = _address(nrow)
        if not addr:
            continue
        split = urlsplit(addr)
        if not (split.netloc or split.path):
            continue
        total_urls += 1
        indexable = _is_indexable(nrow)
        params = parse_qsl(split.query, keep_blank_values=True)
        if not params:
            continue

        url_classes: set[str] = set()
        for name, _value in params:
            cls = _classify_param(name, platform=platform, overrides=overrides)
            url_classes.add(cls)
            by_class[cls]["params"].add(name.strip().lower())
            if cls in _BLOCKED_CLASSES:
                blocked_param_names.add(name.strip().lower())
            elif cls == "functional":
                functional_param_names.add(name.strip().lower())

        for cls in url_classes:
            by_class[cls]["url_count"] += 1
            if indexable:
                by_class[cls]["indexable"] += 1

        # finding accumulation (indexable URLs only)
        if indexable:
            if "internal_search" in url_classes or "sort" in url_classes \
                    or "session_or_tracking" in url_classes:
                search_or_sort_tracking_offenders.append(addr)
            if "facet_filter" in url_classes:
                tokens = _demand_tokens(params)
                facet_names = {
                    n.strip().lower() for n, _ in params
                    if _classify_param(n, platform=platform, overrides=overrides) == "facet_filter"
                }
                demand_backed = bool(tokens & demand) or bool(facet_names & indexable_facets)
                if not demand_backed:
                    facet_offenders.append(addr)
        if "unknown" in url_classes:
            unknown_offenders.append(addr)

    if total_urls == 0:
        raise FacetSchemaDriftError(
            "zero usable URLs parsed from internal_all.csv (DURUR #4)"
        )

    # --- findings (FN- rows; id assigned by sheet_merge) --------------------
    findings: list[dict] = []

    # split the blocked-indexable offenders by class for honest severities
    high_search = [a for a in search_or_sort_tracking_offenders
                   if "internal_search" in _classes_for(a, platform, overrides)]
    med_sort_track = [a for a in search_or_sort_tracking_offenders
                      if a not in high_search]

    if high_search:
        findings.append(_finding(
            "HIGH",
            "Indexable internal search results (crawl-budget sink)",
            f"{len(high_search)} indexable internal-search URL(s). robots.txt does "
            f"not de-index — block crawling AND noindex per tech-seo-governance "
            f"R-129/R-130. Examples: {_sample(high_search)}",
            "Disallow internal-search params in robots.txt; for already-indexed "
            "pages deploy crawlable noindex first (R-133).",
        ))
    if med_sort_track:
        findings.append(_finding(
            "MEDIUM",
            "Indexable sort / session / tracking parameters",
            f"{len(med_sort_track)} indexable sort/session/tracking URL(s) — never "
            f"belong in the index or a sitemap. Examples: {_sample(med_sort_track)}",
            "Canonicalize to the unfiltered page or disallow the param (R-129).",
        ))
    if facet_offenders:
        findings.append(_finding(
            "MEDIUM",
            "Indexable facet_filter URLs without demand evidence",
            f"{len(facet_offenders)} indexable facet_filter URL(s) with no matching "
            f"search demand (cluster_keywords/gsc_performance). Examples: "
            f"{_sample(facet_offenders)}",
            "Index a facet only with demand evidence; otherwise block/canonicalize "
            "(R-129). Zero-result combos must 404.",
        ))
    if len(unknown_offenders) >= unknown_param_threshold:
        unknown_names = sorted(by_class["unknown"]["params"])
        findings.append(_finding(
            "LOW",
            "Unclassified (unknown) parameters — operator triage",
            f"{len(unknown_offenders)} URL(s) carry unclassified parameter(s): "
            f"{', '.join(unknown_names[:20])}. Classify them in "
            f"projects/{{slug}}/config/facet-policy.json (R-128).",
            "Add each to facet-policy.json classifications; re-run the audit.",
        ))

    proposed = _proposed_robots_block(blocked_param_names, functional_param_names)

    metrics = {
        "total_urls": total_urls,
        "by_class": {
            cls: {
                "url_count": d["url_count"],
                "indexable": d["indexable"],
                "pct_of_crawl": round(100.0 * d["url_count"] / total_urls, 1),
                "params": sorted(d["params"]),
            }
            for cls, d in by_class.items()
            if d["url_count"] > 0
        },
    }
    verdict = "FINDINGS" if findings else "COMPLIANT"
    return {
        "robots_txt_rows": findings,
        "metrics": metrics,
        "proposed_robots_block": proposed,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Finding + proposed-block helpers
# ---------------------------------------------------------------------------

def _finding(level: str, issue: str, detail: str, resolution: str) -> dict:
    """A robots_txt-shaped finding row (id=None — sheet_merge assigns FN-NNN)."""
    return {
        "id": None,
        "level": level,
        "issue": _truncate(issue),
        "detail": _truncate(detail),
        "resolution": _truncate(resolution),
    }


def _sample(urls: list[str]) -> str:
    head = urls[:_OFFENDER_SAMPLE]
    suffix = "" if len(urls) <= _OFFENDER_SAMPLE else f" (+{len(urls) - _OFFENDER_SAMPLE} more)"
    return ", ".join(head) + suffix


def _classes_for(addr: str, platform: str, overrides: dict[str, str]) -> set[str]:
    params = parse_qsl(urlsplit(addr).query, keep_blank_values=True)
    return {_classify_param(n, platform=platform, overrides=overrides) for n, _ in params}


def _proposed_robots_block(blocked: set[str], functional: set[str]) -> str:
    """Deterministic recommendation-only robots.txt block (R-130). Disallows the
    blocked-class params; Allows functional params as exceptions."""
    lines = [
        "# facet-nav-audit proposed robots.txt block — RECOMMENDATION ONLY (operator deploys)",
        "# per rules/tech-seo-governance.md R-130 (blocking-mechanism decision tree)",
        "User-agent: *",
    ]
    for name in sorted(blocked):
        lines.append(f"Disallow: /*?*{name}=")
    for name in sorted(functional):
        lines.append(f"Allow: /*?*{name}=")
    return "\n".join(lines) + "\n"


__all__ = (
    "transform",
    "PARAM_CLASSES",
    "FacetNavAuditError",
    "FacetInternalMissingError",
    "FacetSchemaDriftError",
    "FacetUrlCapExceededError",
)
