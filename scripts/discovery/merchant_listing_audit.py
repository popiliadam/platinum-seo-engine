#!/usr/bin/env python3
"""
merchant_listing_audit.py — pure merchant-listing structured-data checks
(M1–M7) over parsed JSON-LD nodes → schema-shaped rows for master.xlsx#schema.

GAP-A3 (unified dispatch GAP-A-B1). Extends the schema-audit skill with the
merchant listing experience requirements verified against Google's docs
(2026-06-10):

  - ``Offer.price`` (or ``priceSpecification.price``) > 0 and
    ``priceCurrency`` are REQUIRED for merchant listing experiences;
    ``shippingDetails`` / ``hasMerchantReturnPolicy`` are RECOMMENDED
    (annotation opportunity, not a compliance failure).
    https://developers.google.com/search/docs/appearance/structured-data/merchant-listing
  - Site-wide shipping policy markup is ``Organization`` →
    ``hasShippingService`` → ``ShippingService`` (required prop
    ``shippingConditions``); there is NO ``OrganizationShippingDetails``
    type. Per-offer ``OfferShippingDetails`` is the override path only.
    https://developers.google.com/search/docs/appearance/structured-data/shipping-policy
  - Site-wide returns: ``Organization.hasMerchantReturnPolicy``.
    https://developers.google.com/search/docs/appearance/structured-data/return-policy

Checks (each finding → one 5-col ``schema`` sheet row, statusEnum seed TODO):
  M1  price validity      — price present/parseable/> 0; priceCurrency
                            present and == project.config ``currency``.
  M2  availability        — present and a canonical ``https://schema.org/…``
                            ItemAvailability member (bare literals flagged).
  M3  offer shape         — merchant listings require a plain ``Offer``;
                            AggregateOffer-only products are flagged.
  M4  shipping coverage   — any per-offer ``shippingDetails`` OR org-level
                            ``hasShippingService``; neither → ONE site row.
  M5  returns coverage    — same pair for ``hasMerchantReturnPolicy``.
  M6  price staleness     — ``priceValidUntil`` in the past (or unparseable).
  M7  price parity sample — optional flag; compares JSON-LD price against
                            pre-fetched rendered HTML (TR formats tolerated,
                            ≤ PARITY_SAMPLE_CAP URLs). Heuristic, default off.

Severity → ``remaining_work`` text mapping (the ``schema`` sheet has NO
severity column — priority words are encoded in the row text, consistent
with existing schema-sheet usage):
  ``merchant M1/high:`` ``merchant M7/high:``       — hard eligibility/accuracy
  ``merchant M2/medium:`` ``merchant M3/medium:`` ``merchant M6/medium:``
  ``merchant M4/opportunity:`` ``merchant M5/opportunity:`` — recommended-not-
  required annotations, framed as opportunity per
  rules/merchant-structured-data.md (org-level-first).

Pure function discipline (mirrors schema_audit_transform):
  - No I/O, no clock (``today`` injected), no RNG → deterministic:
    same inputs → byte-identical ``json.dumps(..., sort_keys=True)``.
  - Does NOT import scripts.excel.transaction (orchestration layer only).
  - Coverage semantics for M4/M5 are ANY-offer: one observed per-offer
    markup means the per-offer strategy is in use site-wide (partial gaps
    stay page-level audit work); org coverage is any org node carrying the
    property. M4/M5 fire only when at least one product was seen — an empty
    catalog must never demand markup (no fabricated findings).

Errors raised:
  - MerchantAuditError: malformed inputs (wrong container types, bad
    ``today`` format, malformed JSON-LD in ``strict_parse`` mode).
  - Row drift self-check raises MerchantAuditError (5-col tuple + TODO).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when the module is exercised standalone.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discovery.schema_audit_transform import (  # noqa: E402
    SCHEMA_AUDIT_COLUMNS,
)
from scripts.util.url_normalize import (  # noqa: E402
    URLNormalizeError as _URLNormalizeError,
    normalize_url as _canonical_normalize_url,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: M7 samples at most this many product URLs (pre-fetched HTML supplied by
#: the orchestrator via free Scrapling bulk_get; never a catalog crawl).
PARITY_SAMPLE_CAP = 10

#: statusEnum members (master-excel.schema.json#/definitions/statusEnum).
#: Merchant rows are seeded TODO only; the full set is kept for the
#: row-shape self-check.
_STATUS_ENUM = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})

#: schema.org ItemAvailability members (canonical URL form required).
_ITEM_AVAILABILITY = frozenset({
    "BackOrder", "Discontinued", "InStock", "InStoreOnly",
    "LimitedAvailability", "MadeToOrder", "OnlineOnly", "OutOfStock",
    "PreOrder", "PreSale", "Reserved", "SoldOut",
})

_PRODUCT_TYPES = frozenset({"Product", "IndividualProduct", "ProductModel"})

#: Org-surface node types whose markup can carry the site-wide shipping /
#: returns properties (Organization + common subtypes seen on TR platforms).
_ORG_TYPES = frozenset({
    "Organization", "OnlineStore", "OnlineBusiness", "LocalBusiness",
    "Corporation", "Store",
})

_CHECK_PRIORITY = {
    "M1": "high", "M2": "medium", "M3": "medium", "M4": "opportunity",
    "M5": "opportunity", "M6": "medium", "M7": "high",
}

_ISO_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_AVAILABILITY_URL_RE = re.compile(r"^https?://schema\.org/([A-Za-z]+)$")

#: Same (check, schema_type, text) signature across ≥N URLs collapses into a
#: single site-wide row (mirrors schema_audit_transform._AGGREGATION_MIN_URLS).
_AGGREGATION_MIN_URLS = 3


class MerchantAuditError(ValueError):
    """Explicit DURUR-style error for merchant audit input/contract drift."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _safe_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _node_types(node: dict) -> frozenset:
    raw = node.get("@type")
    if isinstance(raw, list):
        return frozenset(_safe_str(t) for t in raw if _safe_str(t))
    s = _safe_str(raw)
    return frozenset({s}) if s else frozenset()


def _normalize_url(url: Any) -> str:
    """Tolerant D-03 normalize (same canonical helper as the sibling
    transform); un-parseable input → empty string (row dropped, not fatal)."""
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError:
        return ""


def _parse_price(raw: Any) -> float | None:
    """Parse a price value tolerating TR/US thousand+decimal conventions.

    Strings keep only ``[0-9.,-]``; when both ``.`` and ``,`` appear the
    LAST-occurring separator is the decimal mark (``1.234,56`` → 1234.56,
    ``1,234.56`` → 1234.56); a lone ``,`` is a decimal mark. Heuristic by
    design — unparseable values return None (flagged by M1, never guessed).
    """
    if isinstance(raw, bool):  # bool is an int subclass; never a price
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = _safe_str(raw)
    if not s:
        return None
    s = re.sub(r"[^0-9.,\-]", "", s)
    if not s:
        return None
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _price_fields(offer: dict) -> tuple[Any, str]:
    """Extract (price_raw, currency) from an Offer, preferring direct props
    and falling back to the first priceSpecification carrying a price."""
    price_raw = offer.get("price")
    currency = _safe_str(offer.get("priceCurrency"))
    if price_raw is None or not currency:
        for spec in _as_list(offer.get("priceSpecification")):
            if not isinstance(spec, dict):
                continue
            if price_raw is None and spec.get("price") is not None:
                price_raw = spec.get("price")
            if not currency:
                currency = _safe_str(spec.get("priceCurrency"))
            if price_raw is not None and currency:
                break
    return price_raw, currency


def _price_display_candidates(price: float) -> list[str]:
    """Render the textual forms a price may take on a TR/intl page."""
    us = f"{price:,.2f}"                                   # 1,234.56
    tr = us.translate(str.maketrans({",": ".", ".": ","}))  # 1.234,56
    plain = f"{price:.2f}"                                 # 1234.56
    out = [us, tr, plain, plain.replace(".", ",")]
    if price == int(price):
        i = str(int(price))
        out.extend([i, f"{int(price):,}",
                    f"{int(price):,}".replace(",", ".")])
    # Order-preserving dedupe (determinism).
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------------
# JSON-LD index helpers (SF envelope → {url: [typed nodes]})
# ---------------------------------------------------------------------------

def _flatten_jsonld(node: Any) -> list[dict]:
    """Flatten bare object / ``@graph`` / top-level list into typed nodes."""
    out: list[dict] = []
    if isinstance(node, dict):
        graph = node.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                out.extend(_flatten_jsonld(child))
        if "@type" in node:
            out.append(node)
    elif isinstance(node, list):
        for child in node:
            out.extend(_flatten_jsonld(child))
    return out


def _iter_envelope_rows(raw_sf: dict):
    """Yield SF rows from either envelope shape (mirrors the tolerance of
    schema_audit_transform: flat ``{"rows": [...]}`` or the sf-import
    ``files[].canonical_name == "structured_data_all"`` envelope)."""
    rows = raw_sf.get("rows")
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict):
                yield r
        return
    files = raw_sf.get("files")
    if isinstance(files, list):
        for f in files:
            if not isinstance(f, dict):
                continue
            canonical = _safe_str(f.get("canonical_name"))
            if canonical and canonical != "structured_data_all":
                continue
            for r in f.get("rows") or []:
                if isinstance(r, dict):
                    yield r


def build_jsonld_index(raw_sf: dict, *, strict_parse: bool = False) -> dict:
    """Build ``{normalized_url: [typed JSON-LD nodes]}`` from a parsed SF
    structured-data envelope. Malformed blobs are skipped (or raise
    MerchantAuditError when ``strict_parse=True``); URLs normalize per D-03
    so merchant rows join the rest of the audit bit-stably."""
    if not isinstance(raw_sf, dict):
        raise MerchantAuditError(
            f"raw_sf must be a dict, got {type(raw_sf).__name__}"
        )
    index: dict[str, list[dict]] = {}
    for row in _iter_envelope_rows(raw_sf):
        url = _normalize_url(_safe_str(
            row.get("address") or row.get("Address")
            or row.get("url") or row.get("URL")
        ))
        if not url:
            continue
        blob = _safe_str(
            row.get("json_ld") or row.get("JSON-LD")
            or row.get("jsonld_blob") or row.get("JSON-LD Blob")
            or row.get("structured_data")
        )
        if not blob:
            continue
        try:
            doc = json.loads(blob)
        except (TypeError, ValueError) as exc:
            if strict_parse:
                raise MerchantAuditError(
                    f"JSON-LD parse error at {url}: {exc}"
                ) from exc
            continue
        nodes = _flatten_jsonld(doc)
        if nodes:
            index.setdefault(url, []).extend(nodes)
    return index


def collect_org_nodes(jsonld_by_url: dict) -> list[dict]:
    """Collect the org-level markup surface from an index: nodes typed as an
    Organization (or common subtype) plus any node already carrying the
    site-wide shipping/returns properties."""
    if not isinstance(jsonld_by_url, dict):
        raise MerchantAuditError(
            f"jsonld_by_url must be a dict, got {type(jsonld_by_url).__name__}"
        )
    out: list[dict] = []
    for url in sorted(jsonld_by_url):
        for node in jsonld_by_url[url]:
            if not isinstance(node, dict):
                continue
            if (_node_types(node) & _ORG_TYPES
                    or node.get("hasShippingService") is not None
                    or node.get("hasMerchantReturnPolicy") is not None):
                out.append(node)
    return out


# ---------------------------------------------------------------------------
# Row machinery
# ---------------------------------------------------------------------------

def _make_row(check: str, schema_type: str, location: str, scope: str,
              action: str) -> dict:
    row = {
        "schema_type": schema_type,
        "status": "TODO",
        "location": location,
        "scope": scope,
        "remaining_work": f"merchant {check}/{_CHECK_PRIORITY[check]}: {action}",
    }
    if tuple(row.keys()) != SCHEMA_AUDIT_COLUMNS:
        raise MerchantAuditError(
            f"row column drift: {tuple(row.keys())} != {SCHEMA_AUDIT_COLUMNS}"
        )
    if row["status"] not in _STATUS_ENUM:
        raise MerchantAuditError(f"status drift: {row['status']!r}")
    return row


def _aggregate_url_findings(findings: dict) -> list[tuple[str, dict]]:
    """``findings`` maps (check, schema_type, action) → sorted set of URLs.
    ≥ _AGGREGATION_MIN_URLS distinct URLs → one site-wide row; else per-URL
    rows. Returns (check, row) pairs for final ordering."""
    out: list[tuple[str, dict]] = []
    for (check, schema_type, action), urls in findings.items():
        ordered = sorted(urls)
        if len(ordered) >= _AGGREGATION_MIN_URLS:
            out.append((check, _make_row(
                check, schema_type, f"{len(ordered)} URLs", "site-wide", action,
            )))
        else:
            for url in ordered:
                out.append((check, _make_row(
                    check, schema_type, url, "page-level", action,
                )))
    return out


# ---------------------------------------------------------------------------
# Per-offer checks (M1 / M2 / M6)
# ---------------------------------------------------------------------------

def _m1_actions(offer: dict, currency_expected: str) -> list[str]:
    actions: list[str] = []
    price_raw, currency = _price_fields(offer)
    if price_raw is None:
        actions.append(
            "add Offer.price (or priceSpecification.price) — required for "
            "merchant listing eligibility"
        )
    else:
        price = _parse_price(price_raw)
        if price is None:
            actions.append(
                f"unparseable price value '{_safe_str(price_raw)}' — use a "
                "plain decimal number"
            )
        elif price <= 0:
            actions.append(
                f"non-positive Offer.price ({_safe_str(price_raw)}) — "
                "merchant listings require price > 0"
            )
    if not currency:
        actions.append(
            "add priceCurrency (ISO 4217) — required for merchant listing "
            "eligibility"
        )
    elif currency_expected and currency.upper() != currency_expected:
        actions.append(
            f"priceCurrency {currency.upper()} does not match project.config "
            f"currency {currency_expected} — fix the markup or the config"
        )
    return actions


def _m2_actions(offer: dict) -> list[str]:
    raw = offer.get("availability")
    if raw is None:
        return [
            "add Offer.availability (canonical URL form, e.g. "
            "https://schema.org/InStock)"
        ]
    value = _safe_str(raw)
    m = _AVAILABILITY_URL_RE.match(value)
    if m:
        if m.group(1) in _ITEM_AVAILABILITY:
            return []
        return [
            f"unknown availability value '{value}' — use a schema.org "
            "ItemAvailability member"
        ]
    if value in _ITEM_AVAILABILITY:
        return [
            f"use the canonical URL form https://schema.org/{value} instead "
            f"of the bare literal '{value}'"
        ]
    return [
        f"invalid availability value '{value}' — use a canonical "
        "https://schema.org/ ItemAvailability URL"
    ]


def _m6_actions(offer: dict, today: str) -> list[str]:
    raw = offer.get("priceValidUntil")
    if raw is None:
        return []
    value = _safe_str(raw)
    m = _ISO_DATE_RE.match(value)
    if not m:
        return [
            f"invalid priceValidUntil format '{value}' — use an ISO 8601 date"
        ]
    if m.group(1) < today:
        return [
            f"expired priceValidUntil ({m.group(1)}) — refresh or remove "
            "(price-accuracy signal)"
        ]
    return []


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def audit_merchant_listings(
    jsonld_by_url: dict,
    org_jsonld: list,
    config: dict,
    *,
    today: str,
    rendered_html_by_url: dict | None = None,
    price_parity_sample: bool = False,
) -> dict:
    """Run the M1–M7 merchant-listing checks.

    Args:
        jsonld_by_url: ``{normalized_url: [typed JSON-LD nodes]}`` (see
            :func:`build_jsonld_index`).
        org_jsonld: org-level markup surface nodes (see
            :func:`collect_org_nodes`); EMPTY list means org markup was not
            observable in the crawl — M4/M5 say so instead of asserting
            absence on the live site.
        config: project.config.json dict; reads ``currency`` (ISO 4217).
            Profile gating (e-commerce) is the SKILL's job, not this module's.
        today: ISO date ``YYYY-MM-DD`` (injected — determinism, no clock).
        rendered_html_by_url: optional pre-fetched HTML for M7 (orchestrator
            fetches via free Scrapling; this module does NO I/O).
        price_parity_sample: M7 flag (default off; heuristic sample,
            ≤ PARITY_SAMPLE_CAP URLs).

    Returns:
        ``{"rows": [<5-col schema-sheet row>, ...], "summary": {...}}`` —
        rows are TODO-seeded; summary is JSON-plain (deterministic).
    """
    if not isinstance(jsonld_by_url, dict):
        raise MerchantAuditError(
            f"jsonld_by_url must be a dict, got {type(jsonld_by_url).__name__}"
        )
    if not isinstance(org_jsonld, list):
        raise MerchantAuditError(
            f"org_jsonld must be a list, got {type(org_jsonld).__name__}"
        )
    if not isinstance(config, dict):
        raise MerchantAuditError(
            f"config must be a dict, got {type(config).__name__}"
        )
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _safe_str(today)):
        raise MerchantAuditError(
            f"today must be an ISO date YYYY-MM-DD, got {today!r}"
        )
    if rendered_html_by_url is not None and not isinstance(
            rendered_html_by_url, dict):
        raise MerchantAuditError(
            "rendered_html_by_url must be a dict or None, got "
            f"{type(rendered_html_by_url).__name__}"
        )

    currency_expected = _safe_str(config.get("currency")).upper()

    # (check, schema_type, action) → set of URLs (aggregation input).
    findings: dict[tuple, set] = {}

    def _add(check: str, schema_type: str, url: str, action: str) -> None:
        findings.setdefault((check, schema_type, action), set()).add(url)

    products_seen = 0
    plain_offers_seen = 0
    aggregate_only_products = 0
    offers_with_shipping = 0
    offers_with_returns = 0
    product_price_by_url: dict[str, float] = {}

    for url in sorted(jsonld_by_url):
        nodes = jsonld_by_url[url]
        if not isinstance(nodes, list):
            raise MerchantAuditError(
                f"jsonld_by_url[{url!r}] must be a list of nodes"
            )
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if not (_node_types(node) & _PRODUCT_TYPES):
                continue
            products_seen += 1
            offers = [o for o in _as_list(node.get("offers"))
                      if isinstance(o, dict)]
            if not offers:
                # Missing `offers` is already a base schema-audit finding
                # (required Product prop) — no duplicate merchant row.
                continue
            # Untyped offer objects are treated as plain Offers (lenient
            # JSON-LD reality on TR platforms).
            plain = [o for o in offers
                     if not _node_types(o) or "Offer" in _node_types(o)]
            aggregate = [o for o in offers
                         if "AggregateOffer" in _node_types(o)]
            if aggregate and not plain:
                aggregate_only_products += 1
                _add("M3", "AggregateOffer", url,
                     "merchant listing eligibility requires a plain Offer "
                     "(merchant is the seller) — replace or accompany the "
                     "AggregateOffer with per-variant Offer markup")
                continue
            for offer in plain:
                plain_offers_seen += 1
                for action in _m1_actions(offer, currency_expected):
                    _add("M1", "Offer", url, action)
                for action in _m2_actions(offer):
                    _add("M2", "Offer", url, action)
                for action in _m6_actions(offer, today):
                    _add("M6", "Offer", url, action)
                if offer.get("shippingDetails") is not None:
                    offers_with_shipping += 1
                if offer.get("hasMerchantReturnPolicy") is not None:
                    offers_with_returns += 1
                if url not in product_price_by_url:
                    price = _parse_price(_price_fields(offer)[0])
                    if price is not None and price > 0:
                        product_price_by_url[url] = price

    # --- M4/M5 — site-level coverage (only meaningful when products exist) --
    org_shipping_covered = any(
        isinstance(n, dict) and n.get("hasShippingService") is not None
        for n in org_jsonld
    )
    org_returns_covered = any(
        isinstance(n, dict) and n.get("hasMerchantReturnPolicy") is not None
        for n in org_jsonld
    )
    org_observed = len(org_jsonld) > 0
    not_observable = (
        "org-level markup not observable in the crawl surface (no "
        "Organization JSON-LD seen — verify the homepage/policy pages "
        "before deploying); "
    )

    site_rows: list[tuple[str, dict]] = []
    if products_seen and not org_shipping_covered and not offers_with_shipping:
        prefix = "" if org_observed else not_observable
        site_rows.append(("M4", _make_row(
            "M4", "ShippingService", "org-level", "site-wide",
            prefix + "shipping markup missing — deploy org-level "
            "Organization.hasShippingService → ShippingService (with "
            "shippingConditions) on the shipping-policy page (platform-safe "
            "single script); recommended-not-required (annotation "
            "opportunity)",
        )))
    if products_seen and not org_returns_covered and not offers_with_returns:
        prefix = "" if org_observed else not_observable
        site_rows.append(("M5", _make_row(
            "M5", "MerchantReturnPolicy", "org-level", "site-wide",
            prefix + "returns markup missing — deploy org-level "
            "Organization.hasMerchantReturnPolicy on the returns-policy page; "
            "recommended-not-required (annotation opportunity)",
        )))

    # --- M7 — optional price-parity sample over pre-fetched HTML ------------
    parity_sampled = 0
    parity_mismatches = 0
    if price_parity_sample and rendered_html_by_url:
        sample = sorted(
            set(rendered_html_by_url) & set(product_price_by_url)
        )[:PARITY_SAMPLE_CAP]
        parity_sampled = len(sample)
        for url in sample:
            html = _safe_str(rendered_html_by_url.get(url))
            price = product_price_by_url[url]
            if not any(c in html for c in _price_display_candidates(price)):
                parity_mismatches += 1
                _add("M7", "Offer", url,
                     f"JSON-LD price {price:.2f} not found in the rendered "
                     "page text — verify live price vs markup (heuristic "
                     "token match; TR formats tolerated)")

    # --- Assemble rows: aggregate per-URL findings, append site rows --------
    tagged = _aggregate_url_findings(findings) + site_rows
    tagged.sort(key=lambda t: (t[0], t[1]["schema_type"], t[1]["location"]))
    rows = [row for _check, row in tagged]

    check_counts = {f"M{i}": 0 for i in range(1, 8)}
    for check, _row in tagged:
        check_counts[check] += 1

    summary = {
        "products_seen": products_seen,
        "offers_seen": plain_offers_seen,
        "aggregate_only_products": aggregate_only_products,
        "checks": check_counts,
        "org_nodes_seen": len(org_jsonld),
        "org_shipping_covered": org_shipping_covered,
        "org_returns_covered": org_returns_covered,
        "offers_with_shipping": offers_with_shipping,
        "offers_with_returns": offers_with_returns,
        "parity_sampled": parity_sampled,
        "parity_mismatches": parity_mismatches,
        "currency_expected": currency_expected,
        "today": today,
        "row_count": len(rows),
    }
    return {"rows": rows, "summary": summary}


# ---------------------------------------------------------------------------
# Report block ($merchant_findings_md)
# ---------------------------------------------------------------------------

def render_merchant_findings_md(result: dict) -> str:
    """Render the prerendered markdown block the schema-audit report template
    consumes as ``$merchant_findings_md``. NEVER emits bare R-NNN tokens
    (template R-token lock) — the rule file is cited by path instead."""
    if not isinstance(result, dict) or "summary" not in result:
        raise MerchantAuditError("result must be an audit_merchant_listings() dict")
    rows = result.get("rows") or []
    s = result["summary"]
    var_yok = lambda b: "VAR" if b else "YOK"  # noqa: E731 — tiny label helper

    lines = []
    if rows:
        lines.append(
            f"**Merchant listing kontrolleri (M1–M7):** {len(rows)} bulgu / "
            f"{s['products_seen']} ürün sayfası tarandı."
        )
    else:
        lines.append(
            "**Merchant listing kontrolleri (M1–M7):** temiz — "
            f"{s['products_seen']} ürün sayfasında bulgu yok."
        )
    lines.append(
        f"- Org-level kargo markup'ı: {var_yok(s['org_shipping_covered'])} · "
        f"org-level iade markup'ı: {var_yok(s['org_returns_covered'])} "
        f"(org düğümü: {s['org_nodes_seen']})"
    )
    c = s["checks"]
    lines.append(
        f"- Dağılım: M1 fiyat {c['M1']} · M2 stok {c['M2']} · "
        f"M3 teklif şekli {c['M3']} · M4 kargo {c['M4']} · "
        f"M5 iade {c['M5']} · M6 bayat fiyat {c['M6']} · "
        f"M7 fiyat eşleşmesi {c['M7']}"
    )
    if s["parity_sampled"]:
        lines.append(
            f"- Fiyat eşleşme örneklemi: {s['parity_sampled']} URL, "
            f"{s['parity_mismatches']} uyumsuz (sezgisel kontrol)"
        )
    for row in rows[:5]:
        lines.append(f"- `{row['location']}` — {row['remaining_work']}")
    if len(rows) > 5:
        lines.append(f"- … (+{len(rows) - 5} satır master.xlsx#schema'da)")
    lines.append(
        "- Kural kaynağı: rules/merchant-structured-data.md (offer accuracy "
        "+ shipping/returns org-level-first)."
    )
    return "\n".join(lines)


__all__ = (
    "PARITY_SAMPLE_CAP",
    "MerchantAuditError",
    "audit_merchant_listings",
    "build_jsonld_index",
    "collect_org_nodes",
    "render_merchant_findings_md",
)
