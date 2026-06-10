"""
tests/discovery/test_merchant_listing_audit.py — merchant-side structured-data
checks (GAP-A3, unified dispatch GAP-A-B1).

Locks the contract of scripts/discovery/merchant_listing_audit.py: a PURE
module (no I/O, no clock — `today` injected) that runs the 7 merchant-listing
checks M1–M7 against parsed JSON-LD nodes and emits rows shaped for the
master.xlsx `schema` sheet (5 locked columns, statusEnum seed TODO).

Verified bases (re-derived 2026-06-10):
  - schemas/master-excel.schema.json#schema — 5 required_columns
    (schema_type, status, location, scope, remaining_work), statusEnum 7
    values; merchant rows ride this sheet, NO sheet change.
  - Google merchant listing: Offer.price > 0 + priceCurrency REQUIRED;
    shippingDetails / hasMerchantReturnPolicy RECOMMENDED; Offer (not
    AggregateOffer) required for merchant listings.
  - Org-level coverage: Organization.hasShippingService → ShippingService
    (Nov 2025 launch) and Organization.hasMerchantReturnPolicy satisfy
    M4/M5 site-wide (there is NO `OrganizationShippingDetails` type).
  - Rules R-147 (offer accuracy) + R-148 (org-level-first) per the unified
    dispatch §R-MAP remap (spec'd R-130/R-131 — remapped ids are canonical).

No live fetches anywhere: M7 price-parity consumes pre-fetched HTML passed
in by the orchestrator (canned strings here).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.discovery import merchant_listing_audit as mla
from scripts.discovery.schema_audit_transform import SCHEMA_AUDIT_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixture helpers — synthetic JSON-LD nodes (TR-platform flavored)
# ---------------------------------------------------------------------------

CONFIG = {"currency": "TRY", "profiles": ["e-commerce"]}
TODAY = "2026-06-10"


def _offer(price="149.90", currency="TRY",
           availability="https://schema.org/InStock", **extra) -> dict:
    o: dict = {"@type": "Offer"}
    if price is not None:
        o["price"] = price
    if currency is not None:
        o["priceCurrency"] = currency
    if availability is not None:
        o["availability"] = availability
    o.update(extra)
    return o


def _product(name="Klima X", offers=None, **extra) -> dict:
    node: dict = {
        "@type": "Product",
        "name": name,
        "image": "https://shop.example/i.jpg",
    }
    node["offers"] = offers if offers is not None else _offer()
    node.update(extra)
    return node


ORG_PLAIN = [{"@type": "Organization", "name": "Shop",
              "url": "https://shop.example"}]
ORG_WITH_SHIPPING = [{
    "@type": "Organization", "name": "Shop", "url": "https://shop.example",
    "hasShippingService": {
        "@type": "ShippingService",
        "shippingConditions": {"@type": "ShippingConditions"},
    },
}]
ORG_WITH_RETURNS = [{
    "@type": "Organization", "name": "Shop",
    "hasMerchantReturnPolicy": {"@type": "MerchantReturnPolicy"},
}]


def _audit(jsonld_by_url, org=None, config=None, **kw) -> dict:
    return mla.audit_merchant_listings(
        jsonld_by_url,
        ORG_PLAIN if org is None else org,
        CONFIG if config is None else config,
        today=TODAY,
        **kw,
    )


def _rows_for(result: dict, check: str) -> list[dict]:
    """Rows for one check id; remaining_work is prefixed `merchant M<n>/<prio>:`."""
    return [r for r in result["rows"]
            if r["remaining_work"].startswith(f"merchant {check}/")]


# ---------------------------------------------------------------------------
# M1 — price validity
# ---------------------------------------------------------------------------

def test_m1_zero_price_flagged():
    """Ticimax-flavored Product+Offer with price '0' → M1 row (price must be > 0)."""
    idx = {"https://shop.example/p1": [_product(offers=_offer(price="0"))]}
    result = _audit(idx)
    rows = _rows_for(result, "M1")
    assert len(rows) == 1
    assert rows[0]["status"] == "TODO"
    assert rows[0]["location"] == "https://shop.example/p1"
    assert "price" in rows[0]["remaining_work"]


def test_m1_currency_mismatch_flagged():
    """priceCurrency USD vs project.config currency TRY → M1 row naming both."""
    idx = {"https://shop.example/p1": [_product(offers=_offer(currency="USD"))]}
    result = _audit(idx)
    rows = _rows_for(result, "M1")
    assert len(rows) == 1
    assert "USD" in rows[0]["remaining_work"]
    assert "TRY" in rows[0]["remaining_work"]


def test_m1_missing_currency_flagged():
    idx = {"https://shop.example/p1": [_product(offers=_offer(currency=None))]}
    rows = _rows_for(_audit(idx), "M1")
    assert len(rows) == 1
    assert "priceCurrency" in rows[0]["remaining_work"]


def test_m1_price_specification_path_clean():
    """price via priceSpecification.price (valid, TRY) → no M1 row."""
    offer = {
        "@type": "Offer",
        "availability": "https://schema.org/InStock",
        "priceSpecification": {
            "@type": "UnitPriceSpecification",
            "price": "199.90", "priceCurrency": "TRY",
        },
    }
    idx = {"https://shop.example/p1": [_product(offers=offer)]}
    assert _rows_for(_audit(idx), "M1") == []


# ---------------------------------------------------------------------------
# M2 — availability
# ---------------------------------------------------------------------------

def test_m2_availability_literal_flagged_as_non_canonical():
    """Bare literal 'InStock' (not the URL form) → M2 row flags non-canonical."""
    idx = {"https://shop.example/p1": [_product(offers=_offer(availability="InStock"))]}
    rows = _rows_for(_audit(idx), "M2")
    assert len(rows) == 1
    assert "https://schema.org/InStock" in rows[0]["remaining_work"]


def test_m2_availability_url_form_clean():
    idx = {"https://shop.example/p1": [_product()]}  # default https://schema.org/InStock
    assert _rows_for(_audit(idx), "M2") == []


def test_m2_availability_missing_flagged():
    idx = {"https://shop.example/p1": [_product(offers=_offer(availability=None))]}
    rows = _rows_for(_audit(idx), "M2")
    assert len(rows) == 1
    assert "availability" in rows[0]["remaining_work"]


def test_m2_availability_unknown_value_flagged():
    idx = {"https://shop.example/p1": [
        _product(offers=_offer(availability="https://schema.org/NotAThing"))]}
    rows = _rows_for(_audit(idx), "M2")
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# M3 — offer shape (AggregateOffer-only)
# ---------------------------------------------------------------------------

def test_m3_aggregate_offer_only_flagged():
    agg = {"@type": "AggregateOffer", "lowPrice": "100",
           "highPrice": "200", "priceCurrency": "TRY"}
    idx = {"https://shop.example/p1": [_product(offers=agg)]}
    result = _audit(idx)
    rows = _rows_for(result, "M3")
    assert len(rows) == 1
    assert rows[0]["schema_type"] == "AggregateOffer"
    assert "Offer" in rows[0]["remaining_work"]


def test_m3_mixed_offer_and_aggregate_clean():
    """A plain Offer alongside AggregateOffer satisfies merchant-listing shape."""
    offers = [
        {"@type": "AggregateOffer", "lowPrice": "100", "highPrice": "200"},
        _offer(),
    ]
    idx = {"https://shop.example/p1": [_product(offers=offers)]}
    assert _rows_for(_audit(idx), "M3") == []


# ---------------------------------------------------------------------------
# M4 / M5 — shipping & returns coverage (org-level OR per-offer)
# ---------------------------------------------------------------------------

def test_m4_org_level_shipping_satisfies():
    """No per-offer shippingDetails but Organization.hasShippingService present
    → NO M4 row (org-level coverage satisfies)."""
    idx = {"https://shop.example/p1": [_product()]}
    result = _audit(idx, org=ORG_WITH_SHIPPING)
    assert _rows_for(result, "M4") == []
    assert result["summary"]["org_shipping_covered"] is True


def test_m4_neither_emits_one_site_level_row():
    """Neither per-offer nor org-level shipping → exactly ONE site-level row
    (not per-product spam), recommending Organization.hasShippingService."""
    idx = {
        f"https://shop.example/p{i}": [_product(name=f"P{i}")]
        for i in range(1, 4)
    }
    result = _audit(idx, org=ORG_PLAIN)
    rows = _rows_for(result, "M4")
    assert len(rows) == 1
    assert rows[0]["scope"] == "site-wide"
    assert "hasShippingService" in rows[0]["remaining_work"]
    assert "ShippingService" in rows[0]["remaining_work"]


def test_m4_per_offer_shipping_satisfies():
    offer = _offer(shippingDetails={"@type": "OfferShippingDetails"})
    idx = {"https://shop.example/p1": [_product(offers=offer)]}
    assert _rows_for(_audit(idx, org=ORG_PLAIN), "M4") == []


def test_m4_m5_org_not_observable_wording():
    """org_jsonld empty → site rows carry the 'not observable' wording
    (org markup may exist but was not in the crawl surface)."""
    idx = {"https://shop.example/p1": [_product()]}
    result = _audit(idx, org=[])
    m4 = _rows_for(result, "M4")
    m5 = _rows_for(result, "M5")
    assert len(m4) == 1 and len(m5) == 1
    assert "not observable" in m4[0]["remaining_work"]
    assert "not observable" in m5[0]["remaining_work"]


def test_m5_org_level_returns_satisfies():
    idx = {"https://shop.example/p1": [_product()]}
    result = _audit(idx, org=ORG_WITH_RETURNS)
    assert _rows_for(result, "M5") == []
    assert result["summary"]["org_returns_covered"] is True


def test_m5_neither_emits_one_site_level_row():
    idx = {"https://shop.example/p1": [_product()],
           "https://shop.example/p2": [_product(name="P2")]}
    rows = _rows_for(_audit(idx, org=ORG_PLAIN), "M5")
    assert len(rows) == 1
    assert rows[0]["scope"] == "site-wide"
    assert "hasMerchantReturnPolicy" in rows[0]["remaining_work"]


def test_m5_per_offer_returns_satisfies():
    offer = _offer(hasMerchantReturnPolicy={"@type": "MerchantReturnPolicy"})
    idx = {"https://shop.example/p1": [_product(offers=offer)]}
    assert _rows_for(_audit(idx, org=ORG_PLAIN), "M5") == []


# ---------------------------------------------------------------------------
# M6 — priceValidUntil staleness (today injected, no clock)
# ---------------------------------------------------------------------------

def test_m6_expired_price_valid_until_flagged():
    idx = {"https://shop.example/p1": [
        _product(offers=_offer(priceValidUntil="2025-01-01"))]}
    rows = _rows_for(_audit(idx), "M6")
    assert len(rows) == 1
    assert "2025-01-01" in rows[0]["remaining_work"]


def test_m6_future_price_valid_until_clean():
    idx = {"https://shop.example/p1": [
        _product(offers=_offer(priceValidUntil="2027-01-01"))]}
    assert _rows_for(_audit(idx), "M6") == []


def test_m6_unparseable_price_valid_until_flagged():
    idx = {"https://shop.example/p1": [
        _product(offers=_offer(priceValidUntil="yarın"))]}
    rows = _rows_for(_audit(idx), "M6")
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# M7 — price parity sample (flag-gated, pre-fetched HTML, cap 10)
# ---------------------------------------------------------------------------

def test_m7_default_off_no_rows_even_with_html():
    idx = {"https://shop.example/p1": [_product(offers=_offer(price="1234.56"))]}
    html = {"https://shop.example/p1": "<span>999,00 TL</span>"}
    result = _audit(idx, rendered_html_by_url=html)  # price_parity_sample omitted
    assert _rows_for(result, "M7") == []
    assert result["summary"]["parity_sampled"] == 0


def test_m7_tr_formatted_price_match_clean():
    """JSON-LD 1234.56 rendered as TR '1.234,56' → parity OK, no row."""
    idx = {"https://shop.example/p1": [_product(offers=_offer(price="1234.56"))]}
    html = {"https://shop.example/p1": "<b>1.234,56 TL</b> sepette"}
    result = _audit(idx, rendered_html_by_url=html, price_parity_sample=True)
    assert _rows_for(result, "M7") == []
    assert result["summary"]["parity_sampled"] == 1


def test_m7_mismatch_flagged_high():
    idx = {"https://shop.example/p1": [_product(offers=_offer(price="1234.56"))]}
    html = {"https://shop.example/p1": "<b>999,00 TL</b>"}
    result = _audit(idx, rendered_html_by_url=html, price_parity_sample=True)
    rows = _rows_for(result, "M7")
    assert len(rows) == 1
    assert rows[0]["remaining_work"].startswith("merchant M7/high:")


def test_m7_sample_capped_at_10():
    idx = {}
    html = {}
    for i in range(1, 13):  # 12 candidate URLs
        url = f"https://shop.example/p{i:02d}"
        idx[url] = [_product(name=f"P{i}", offers=_offer(price="100.00"))]
        html[url] = "<b>100,00 TL</b>"
    result = _audit(idx, rendered_html_by_url=html, price_parity_sample=True)
    assert result["summary"]["parity_sampled"] == mla.PARITY_SAMPLE_CAP == 10


# ---------------------------------------------------------------------------
# Row contract + aggregation + determinism + GREEN control
# ---------------------------------------------------------------------------

def test_rows_conform_to_5col_schema_sheet_contract():
    """Every emitted row: exact 5-col tuple, status in the master-excel
    statusEnum (seeded TODO)."""
    schema = json.loads(
        (REPO_ROOT / "schemas" / "master-excel.schema.json").read_text("utf-8")
    )
    sheet_cols = tuple(
        c["name"] for c in schema["sheets"]["schema"]["required_columns"]
    )
    status_enum = set(schema["definitions"]["statusEnum"]["enum"])

    idx = {
        "https://shop.example/p1": [_product(offers=_offer(price="0"))],
        "https://shop.example/p2": [_product(
            name="P2", offers=_offer(availability="InStock",
                                     priceValidUntil="2024-01-01"))],
    }
    result = _audit(idx, org=[])
    assert result["rows"], "expected findings from a defective fixture"
    for row in result["rows"]:
        assert tuple(row.keys()) == sheet_cols == SCHEMA_AUDIT_COLUMNS
        assert row["status"] in status_enum
        assert row["status"] == "TODO"


def test_same_signature_rows_aggregate_site_wide():
    """≥3 URLs sharing one (check, issue) signature collapse to a single
    site-wide row (mirrors the schema-audit transform aggregation rule)."""
    idx = {
        f"https://shop.example/p{i}": [
            _product(name=f"P{i}", offers=_offer(availability=None))
        ]
        for i in range(1, 5)  # 4 URLs, same M2-missing signature
    }
    rows = _rows_for(_audit(idx), "M2")
    assert len(rows) == 1
    assert rows[0]["scope"] == "site-wide"
    assert "4 URLs" in rows[0]["location"]


def test_determinism_byte_identical():
    idx = {
        "https://shop.example/p1": [_product(offers=_offer(price="0"))],
        "https://shop.example/p2": [_product(name="P2",
                                             offers=_offer(currency="USD"))],
    }
    a = mla.audit_merchant_listings(idx, ORG_PLAIN, CONFIG, today=TODAY)
    b = mla.audit_merchant_listings(idx, ORG_PLAIN, CONFIG, today=TODAY)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_empty_inputs_no_crash():
    result = _audit({}, org=[])
    assert result["rows"] == []
    assert result["summary"]["products_seen"] == 0


def test_woocommerce_clean_fixture_green_control():
    """Well-formed wc-flavored Product (URL-form availability, price>0, TRY,
    per-offer shipping+returns) + org coverage → ZERO merchant rows."""
    offer = _offer(
        price="2499.00",
        shippingDetails={"@type": "OfferShippingDetails"},
        hasMerchantReturnPolicy={"@type": "MerchantReturnPolicy"},
    )
    legacy_ok = _offer(price="100.00",
                       availability="http://schema.org/OutOfStock")
    idx = {
        "https://shop.example/p1": [_product(offers=offer)],
        "https://shop.example/p2": [_product(name="P2", offers=legacy_ok)],
    }
    result = _audit(idx, org=ORG_WITH_SHIPPING + ORG_WITH_RETURNS)
    assert result["rows"] == []
    assert result["summary"]["products_seen"] == 2


# ---------------------------------------------------------------------------
# build_jsonld_index / collect_org_nodes helpers (SF envelope → index)
# ---------------------------------------------------------------------------

def test_build_jsonld_index_normalizes_urls_d03():
    blob = json.dumps(_product())
    raw_sf = {"rows": [{"address": "https://Shop.Example/p1/", "json_ld": blob}]}
    idx = mla.build_jsonld_index(raw_sf)
    assert list(idx.keys()) == ["https://shop.example/p1"]
    assert idx["https://shop.example/p1"][0]["@type"] == "Product"


def test_build_jsonld_index_flattens_graph():
    blob = json.dumps({"@graph": [_product(), ORG_PLAIN[0]]})
    raw_sf = {"rows": [{"address": "https://shop.example/", "json_ld": blob}]}
    idx = mla.build_jsonld_index(raw_sf)
    types = {n["@type"] for n in idx["https://shop.example/"]}
    assert types == {"Product", "Organization"}


def test_build_jsonld_index_malformed_default_skip_strict_raises():
    raw_sf = {"rows": [{"address": "https://shop.example/x",
                        "json_ld": "{not valid"}]}
    assert mla.build_jsonld_index(raw_sf) == {}
    with pytest.raises(mla.MerchantAuditError):
        mla.build_jsonld_index(raw_sf, strict_parse=True)


def test_collect_org_nodes_pulls_org_surface():
    idx = {
        "https://shop.example/": ORG_PLAIN + [_product()],
        "https://shop.example/p1": [_product(name="P1")],
    }
    nodes = mla.collect_org_nodes(idx)
    assert len(nodes) == 1
    assert nodes[0]["@type"] == "Organization"


# ---------------------------------------------------------------------------
# render_merchant_findings_md — report block ($merchant_findings_md)
# ---------------------------------------------------------------------------

def test_render_md_has_counts_and_no_bare_rule_tokens():
    idx = {"https://shop.example/p1": [_product(offers=_offer(price="0"))]}
    result = _audit(idx, org=[])
    md = mla.render_merchant_findings_md(result)
    assert "M1" in md
    assert str(result["summary"]["products_seen"]) in md
    # §0.13 / tests/rules/test_r_xx_resolution.py: this text lands inside a
    # template-rendered report — it must never carry bare R-NNN tokens.
    assert not re.search(r"\bR-\d+\b", md)


def test_render_md_clean_state():
    md = mla.render_merchant_findings_md(_audit({}, org=ORG_WITH_SHIPPING))
    assert md.strip()
    assert not re.search(r"\bR-\d+\b", md)


# ---------------------------------------------------------------------------
# Input validation (explicit typed errors, DURUR-style)
# ---------------------------------------------------------------------------

def test_invalid_inputs_raise_typed_error():
    with pytest.raises(mla.MerchantAuditError):
        mla.audit_merchant_listings("nope", [], CONFIG, today=TODAY)  # type: ignore[arg-type]
    with pytest.raises(mla.MerchantAuditError):
        mla.audit_merchant_listings({}, "nope", CONFIG, today=TODAY)  # type: ignore[arg-type]
    with pytest.raises(mla.MerchantAuditError):
        mla.audit_merchant_listings({}, [], "nope", today=TODAY)  # type: ignore[arg-type]
    with pytest.raises(mla.MerchantAuditError):
        mla.audit_merchant_listings({}, [], CONFIG, today="10/06/2026")
