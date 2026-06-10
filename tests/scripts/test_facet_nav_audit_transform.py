"""TDD lock for scripts/discovery/facet_nav_audit_transform.py (GAP-T2).

Faceted-navigation / parameter & crawl-budget governance (rules/tech-seo-governance.md
R-128..R-130). Pure transform: classify every crawled URL's query parameters into the
closed R-128 taxonomy, quantify index-bloat per class (R-129), emit FN- findings +
a recommendation-only proposed robots.txt block (R-130). No paid MCP, no slug literals.

Cases mirror spec GAP-T2 §d (1..10).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.discovery import facet_nav_audit_transform as fnt

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEVERITY = set(
    json.loads((_REPO_ROOT / "schemas" / "master-excel.schema.json").read_text())
    ["definitions"]["severityEnum"]["enum"]
)


def _internal(address, indexable=True, depth=2, canonical=""):
    """One SF internal_all.csv-style row."""
    return {
        "Address": address,
        "Indexability": "Indexable" if indexable else "Non-Indexable",
        "Indexability Status": "" if indexable else "Canonicalised",
        "Crawl Depth": depth,
        "Canonical Link Element 1": canonical,
    }


def _transform(internal_rows, **kw):
    kw.setdefault("response_rows", [])
    kw.setdefault("directives_rows", [])
    kw.setdefault("canonical_rows", [])
    kw.setdefault("pagination_rows", [])
    kw.setdefault("demand_keywords", set())
    kw.setdefault("platform", "custom")
    kw.setdefault("url_patterns", [])
    return fnt.transform(internal_rows, **kw)


# --- 1. facet_filter classification -----------------------------------------

def test_color_size_classified_facet_filter():
    rows = [_internal("https://x.test/shoes?color=red&size=42")]
    out = _transform(rows)
    classes = out["metrics"]["by_class"]
    assert classes.get("facet_filter", {}).get("url_count", 0) >= 1


# --- 2. internal_search indexable -> HIGH -----------------------------------

def test_internal_search_indexable_is_high():
    rows = [_internal("https://x.test/?s=office+chair", indexable=True)]
    out = _transform(rows)
    high = [r for r in out["robots_txt_rows"] if r["level"] == "HIGH"]
    assert high, "indexable internal-search URL must yield a HIGH finding"
    assert any("search" in r["issue"].lower() for r in high)


# --- 3. session_or_tracking classification ----------------------------------

def test_utm_classified_session_or_tracking():
    rows = [_internal("https://x.test/p?utm_source=fb&utm_medium=cpc")]
    out = _transform(rows)
    assert "session_or_tracking" in out["metrics"]["by_class"]


# --- 4. unknown >= threshold -> LOW triage ----------------------------------

def test_unknown_params_over_threshold_triage():
    rows = [_internal(f"https://x.test/p{i}?zorp={i}") for i in range(4)]
    out = _transform(rows, unknown_param_threshold=3)
    low = [r for r in out["robots_txt_rows"] if r["level"] == "LOW"]
    assert any("unknown" in r["issue"].lower() or "unclassified" in r["issue"].lower()
               for r in low)


def test_unknown_below_threshold_no_triage():
    rows = [_internal("https://x.test/p?zorp=1")]
    out = _transform(rows, unknown_param_threshold=10)
    assert not any("unclassified" in r["issue"].lower() for r in out["robots_txt_rows"])


# --- 5. demand evidence suppresses the facet MEDIUM finding -----------------

def test_demand_evidence_suppresses_facet_medium():
    rows = [_internal("https://x.test/sofas?material=leather", indexable=True)]
    with_demand = _transform(rows, demand_keywords={"leather"})
    without = _transform(rows, demand_keywords=set())
    msg = "facet_filter indexable WITHOUT demand must be MEDIUM; WITH demand suppressed"
    assert any(r["level"] == "MEDIUM" and "facet" in r["issue"].lower()
               for r in without["robots_txt_rows"]), msg
    assert not any(r["level"] == "MEDIUM" and "facet" in r["issue"].lower()
                   for r in with_demand["robots_txt_rows"]), msg


# --- 6. proposed robots block: disallow + functional allow ------------------

def test_proposed_block_disallows_search_and_allows_functional():
    rows = [_internal("https://x.test/?s=chair", indexable=True),
            _internal("https://x.test/cart?add-to-cart=99", indexable=True)]
    out = _transform(rows, policy_overrides={"classifications": {"add-to-cart": "functional"}})
    block = out["proposed_robots_block"]
    assert "/*?*s=" in block, "blocked internal-search param must appear as a Disallow"
    assert "Allow:" in block and "add-to-cart" in block, "functional param -> Allow exception"


# --- 7. policy_overrides win over seeds -------------------------------------

def test_policy_overrides_reclassify_wins():
    rows = [_internal("https://x.test/p?color=red", indexable=True)]
    out = _transform(rows, policy_overrides={"classifications": {"color": "session_or_tracking"}})
    # color is normally facet_filter (seed); override flips it to session_or_tracking
    assert "session_or_tracking" in out["metrics"]["by_class"]
    assert "color" not in out["metrics"]["by_class"].get("facet_filter", {}).get("params", [])


# --- 8. row-shape + severityEnum validation ---------------------------------

def test_emitted_rows_shape_and_severity():
    rows = [_internal("https://x.test/?s=chair", indexable=True),
            _internal("https://x.test/p?utm_source=x&sort=price", indexable=True)]
    out = _transform(rows)
    for r in out["robots_txt_rows"]:
        assert set(r) == {"id", "level", "issue", "detail", "resolution"}
        assert r["level"] in _SEVERITY
        assert len(r["detail"]) <= 300


# --- 9. Address column missing -> drift error -------------------------------

def test_address_column_missing_raises_drift():
    rows = [{"URL": "https://x.test/?s=chair", "Indexability": "Indexable"}]
    with pytest.raises(fnt.FacetSchemaDriftError):
        _transform(rows)


def test_internal_rows_none_raises_missing():
    with pytest.raises(fnt.FacetInternalMissingError):
        _transform(None)


# --- 10. URL cap DURUR -------------------------------------------------------

def test_url_cap_exceeded_raises():
    rows = [_internal(f"https://x.test/p{i}?s={i}") for i in range(5)]
    with pytest.raises(fnt.FacetUrlCapExceededError):
        _transform(rows, url_cap=4)


# --- BOM-safe header parse + verdict ----------------------------------------

def test_bom_prefixed_header_parses():
    rows = [{"﻿Address": "https://x.test/?s=chair", "Indexability": "Indexable"}]
    out = _transform(rows)
    assert out["verdict"] in {"FINDINGS", "COMPLIANT"}
    assert out["robots_txt_rows"], "BOM header must not silently drop the Address column"


def test_clean_corpus_compliant_verdict():
    rows = [_internal("https://x.test/page", indexable=True),
            _internal("https://x.test/blog/post", indexable=True)]
    out = _transform(rows)
    assert out["verdict"] == "COMPLIANT"
    assert out["robots_txt_rows"] == []
