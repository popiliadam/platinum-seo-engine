#!/usr/bin/env python3
"""merchant_feed_audit.py — product feed readiness for AI shopping surfaces (O-13).

Google AI Mode checkout and Merchant Center "conversational attributes", and
ChatGPT shopping (reviews, rich media), reward complete product data; the
Content API for Shopping closed 2026-08-18 (Merchant API v1). For the
e-commerce projects this audits a feed export (list of product dicts, Merchant
field names) and the page's Product markup:

* required identity: id, title, description, link, image_link, price,
  availability, brand, and gtin or mpn;
* conversational / rich: product_highlight, product_detail,
  additional_image_link, review data (product_rating / review_count);
* consistency: the page's Product JSON-LD price / availability equal the feed.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

REQUIRED = ("id", "title", "description", "link", "image_link", "price", "availability", "brand")
RICH = ("product_highlight", "product_detail", "additional_image_link", "product_rating")


def _present(v: Any) -> bool:
    return v not in (None, "", [], {})


def audit_item(item: Mapping[str, Any], page_offer: Mapping[str, Any] | None = None) -> dict:
    missing = [f for f in REQUIRED if not _present(item.get(f))]
    if not (_present(item.get("gtin")) or _present(item.get("mpn"))):
        missing.append("gtin_or_mpn")
    rich_missing = [f for f in RICH if not _present(item.get(f))]
    mismatch = []
    if page_offer:
        for field in ("price", "availability"):
            norm = lambda v: str(v or "").split(" ")[0].lower().replace("_", "").rsplit("/", 1)[-1]  # noqa: E731
            a, b = norm(item.get(field)), norm(page_offer.get(field))  # in_stock == InStock == schema.org/InStock
            if a and b and a not in b and b not in a:
                mismatch.append(field)
    return {"id": item.get("id"), "missing_required": missing, "missing_rich": rich_missing,
            "markup_mismatch": mismatch}


def audit_feed(items: Iterable[Mapping[str, Any]],
               page_offers: Mapping[str, Mapping[str, Any]] | None = None) -> dict:
    rows = [audit_item(i, (page_offers or {}).get(str(i.get("id")))) for i in items]
    n = len(rows)
    share = lambda pred: round(sum(1 for r in rows if pred(r)) / n, 3) if n else None  # noqa: E731
    return {"items": n,
            "complete_required_share": share(lambda r: not r["missing_required"]),
            "has_rich_attributes_share": share(lambda r: len(r["missing_rich"]) < len(RICH)),
            "markup_mismatch_items": [r["id"] for r in rows if r["markup_mismatch"]],
            "worst": sorted(rows, key=lambda r: -len(r["missing_required"]))[:20]}


__all__ = ("audit_item", "audit_feed", "REQUIRED", "RICH")
