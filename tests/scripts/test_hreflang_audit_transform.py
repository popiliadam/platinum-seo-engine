"""TDD lock for scripts/discovery/hreflang_audit_transform.py (GAP-T1).

hreflang / i18n governance (rules/tech-seo-governance.md R-125..R-127). Pure
transform: compute the reciprocity graph from SF hreflang_all.csv, validate codes
+ x-default, join return targets against internal/canonical indexability, and
emit HF- findings into the robots_txt shape. PASS-trivial (NOT_APPLICABLE) on the
single-language portfolio; fully validates clusters when a multi-language client
arrives. No paid MCP, no slug literals.

Cases mirror spec GAP-T1 §d (1..10) + the R-126/R-127 behaviors.

Code-validity note: R-126 mandates a PERMISSIVE BCP-47-ish shape regex that must
never RED an exotic-but-valid code (zh-Hant-TW). The regex alone accepts `en-UK`
(UK is a valid-SHAPED 2-letter region), yet R-126 names `en-UK` as the canonical
INVALID example (ISO code is `gb`). So the transform also flags the one documented
region mistake R-126 names — shape regex for structure + that mistake for the
example, with no full ISO table (no false positives on real codes).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.discovery import hreflang_audit_transform as hat

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEVERITY = set(
    json.loads((_REPO_ROOT / "schemas" / "master-excel.schema.json").read_text())
    ["definitions"]["severityEnum"]["enum"]
)

A = "https://x.test/tr/"
B = "https://x.test/en/"


def _hreflang_row(address, pairs):
    """One SF hreflang_all.csv-style row: page Address + N (code, URL) pair cols."""
    row = {"Address": address}
    for i, (code, url) in enumerate(pairs, start=1):
        row[f"HTML hreflang {i}"] = code
        row[f"HTML hreflang {i} URL"] = url
    return row


def _internal(address, indexable=True, status="", canonical=""):
    return {
        "Address": address,
        "Indexability": "Indexable" if indexable else "Non-Indexable",
        "Indexability Status": status,
        "Status Code": "200",
        "Canonical Link Element 1": canonical,
    }


# --- 1. reciprocal 2-locale cluster -> 0 findings ---------------------------

def test_reciprocal_cluster_no_findings():
    rows = [
        _hreflang_row(A, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
        _hreflang_row(B, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
    ]
    out = hat.transform(rows, [], [], "tr-TR")
    assert out["robots_txt_rows"] == []
    assert out["verdict"] == "COMPLIANT"


# --- 2. one-directional pair -> HIGH ----------------------------------------

def test_one_directional_pair_is_high():
    rows = [
        _hreflang_row(A, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
        _hreflang_row(B, [("en-US", B), ("x-default", A)]),  # missing return link to A
    ]
    out = hat.transform(rows, [], [], "tr-TR")
    high = [r for r in out["robots_txt_rows"] if r["level"] == "HIGH"]
    assert high, "non-reciprocal pair must yield a HIGH finding"
    assert any("recipro" in r["issue"].lower() or "direction" in r["issue"].lower()
               for r in high)


# --- 3. missing self-reference -> MEDIUM ------------------------------------

def test_missing_self_reference_is_medium():
    rows = [
        _hreflang_row(A, [("en-US", B)]),            # A never lists itself
        _hreflang_row(B, [("tr-TR", A), ("en-US", B)]),
    ]
    out = hat.transform(rows, [], [], "tr-TR")
    assert any(r["level"] == "MEDIUM" and "self" in r["issue"].lower()
               for r in out["robots_txt_rows"])


# --- 4. relative / protocol-less URL -> MEDIUM ------------------------------

def test_relative_url_is_medium():
    rows = [
        _hreflang_row(A, [("tr-TR", "/tr/"), ("en-US", B)]),  # "/tr/" not absolute
        _hreflang_row(B, [("tr-TR", A), ("en-US", B)]),
    ]
    out = hat.transform(rows, [], [], "tr-TR")
    assert any(r["level"] == "MEDIUM" and
               ("relative" in r["issue"].lower() or "absolute" in r["issue"].lower())
               for r in out["robots_txt_rows"])


# --- 5. invalid code en-UK -> MEDIUM; valid zh-Hant-TW -> no code finding ----

def test_invalid_code_en_uk_is_medium():
    rows = [_hreflang_row(A, [("en-UK", A)])]  # UK is not the ISO region (gb is)
    out = hat.transform(rows, [], [], "en-US")
    assert any(r["level"] == "MEDIUM" and "code" in r["issue"].lower()
               for r in out["robots_txt_rows"])


def test_exotic_valid_code_zh_hant_tw_not_flagged():
    rows = [_hreflang_row(A, [("zh-Hant-TW", A)])]
    out = hat.transform(rows, [], [], "zh-TW")
    assert not any("code" in r["issue"].lower() for r in out["robots_txt_rows"]), (
        "permissive regex must NOT flag an exotic-but-valid code (R-126)"
    )


# --- 6. return target noindex -> HIGH ---------------------------------------

def test_return_target_noindex_is_high():
    internal = [_internal(B, indexable=False, status="noindex")]
    rows = [
        _hreflang_row(A, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
        _hreflang_row(B, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
    ]
    out = hat.transform(rows, [], internal, "tr-TR")
    assert any(r["level"] == "HIGH" and
               ("noindex" in (r["issue"] + r["detail"]).lower()
                or "indexable" in (r["issue"] + r["detail"]).lower())
               for r in out["robots_txt_rows"])


def test_non_self_canonical_return_target_is_high():
    canon = [{"Address": B, "Canonical Link Element 1": A}]  # B canonicalises to A
    rows = [
        _hreflang_row(A, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
        _hreflang_row(B, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
    ]
    out = hat.transform(rows, canon, [], "tr-TR")
    assert any(r["level"] == "HIGH" and "canonical" in (r["issue"] + r["detail"]).lower()
               for r in out["robots_txt_rows"])


# --- 7. zero-hreflang single-locale -> NOT_APPLICABLE + empty rows ----------

def test_zero_hreflang_single_locale_not_applicable():
    out = hat.transform([], [], [], "tr-TR")
    assert out["verdict"] == "NOT_APPLICABLE"
    assert out["robots_txt_rows"] == []


# --- 8. hreflang columns absent -> drift error ------------------------------

def test_hreflang_columns_absent_raises_drift():
    rows = [{"Address": "https://x.test/", "Title": "Home", "Status Code": "200"}]
    with pytest.raises(hat.HreflangSchemaDriftError):
        hat.transform(rows, [], [], "tr-TR")


# --- 9. emitted rows shape + severityEnum -----------------------------------

def test_emitted_rows_shape_and_severity():
    rows = [
        _hreflang_row(A, [("tr-TR", A), ("en-US", B)]),
        _hreflang_row(B, [("en-US", B)]),  # forces findings
    ]
    out = hat.transform(rows, [], [], "tr-TR")
    assert out["robots_txt_rows"], "fixture should yield findings"
    for r in out["robots_txt_rows"]:
        assert set(r) == {"id", "level", "issue", "detail", "resolution"}
        assert r["level"] in _SEVERITY
        assert len(r["detail"]) <= 300


# --- 10. BOM-prefixed header parses -----------------------------------------

def test_bom_prefixed_address_parses():
    bom_row = {
        "﻿Address": A,
        "HTML hreflang 1": "tr-TR", "HTML hreflang 1 URL": A,
        "HTML hreflang 2": "en-US", "HTML hreflang 2 URL": B,
        "HTML hreflang 3": "x-default", "HTML hreflang 3 URL": A,
    }
    rows = [bom_row, _hreflang_row(B, [("tr-TR", A), ("en-US", B), ("x-default", A)])]
    out = hat.transform(rows, [], [], "tr-TR")
    assert out["verdict"] in {"COMPLIANT", "FINDINGS"}
    assert out["summary"]["pages_with_hreflang"] == 2, "BOM Address must not silently drop"


# --- extras: x-default missing (LOW) + R-127 locale mismatch (MEDIUM) -------

def test_missing_x_default_multi_variant_is_low():
    rows = [
        _hreflang_row(A, [("tr-TR", A), ("en-US", B)]),
        _hreflang_row(B, [("tr-TR", A), ("en-US", B)]),
    ]
    out = hat.transform(rows, [], [], "tr-TR")
    assert any(r["level"] == "LOW" and "x-default" in (r["issue"] + r["detail"]).lower()
               for r in out["robots_txt_rows"])


def test_locale_mismatch_is_medium():
    rows = [
        _hreflang_row(A, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
        _hreflang_row(B, [("tr-TR", A), ("en-US", B), ("x-default", A)]),
    ]
    # declared content_locale 'de-DE' appears in NO cluster member -> MEDIUM (R-127)
    out = hat.transform(rows, [], [], "de-DE")
    assert any(r["level"] == "MEDIUM" and
               ("locale" in r["issue"].lower() or "config" in r["issue"].lower())
               for r in out["robots_txt_rows"])
