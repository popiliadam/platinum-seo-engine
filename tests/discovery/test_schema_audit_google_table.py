"""S-13 / S-14 — schema-audit follows Google's structured-data requirements.

S-14: subtypes (Dentist, TravelAgency) were never checked and came out DONE;
      unknown types were DONE; a multi-type @type was BLOCKED; BreadcrumbList
      could never be DONE; LocalBusiness wrongly required telephone; 2026
      additions (Product category / hasAdultConsideration, VideoObject creator)
      were missing.
S-13: self-serving review stars on LocalBusiness / Organization and incentivised
      review wording were not flagged.
"""
from __future__ import annotations

import json

from scripts.discovery.schema_audit_transform import transform

URL = "https://x.test/page"


def _rows(*nodes: dict) -> list[dict]:
    blob = json.dumps({"@context": "https://schema.org", "@graph": list(nodes)})
    return transform({"rows": [{"Address": URL, "JSON-LD": blob}]})["schema"]


def _row(node: dict) -> dict:
    rows = _rows(node)
    assert len(rows) == 1, rows
    return rows[0]


def test_dentist_is_checked_with_local_business_rules() -> None:
    r = _row({"@type": "Dentist", "name": "Klinik"})
    assert r["status"] == "TODO" and "address" in r["remaining_work"]


def test_local_business_does_not_require_telephone() -> None:
    r = _row({"@type": "LocalBusiness", "name": "Klinik",
              "address": {"@type": "PostalAddress", "streetAddress": "x"}})
    assert r["status"] != "TODO"


def test_unknown_type_is_not_done() -> None:
    r = _row({"@type": "SpecialAnnouncement", "name": "x"})
    assert r["status"] != "DONE" and "not validated" in r["remaining_work"]


def test_multi_type_is_checked_not_blocked() -> None:
    r = _row({"@type": ["LocalBusiness", "Dentist"], "name": "Klinik"})
    assert r["status"] == "TODO" and "address" in r["remaining_work"]


def test_breadcrumb_with_positions_can_be_done() -> None:
    r = _row({"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://x.test/"},
        {"@type": "ListItem", "position": 2, "name": "Page"},
    ]})
    assert r["status"] == "DONE"


def test_product_recommends_2026_properties() -> None:
    r = _row({"@type": "Product", "name": "p", "image": "i.jpg", "offers": {},
              "aggregateRating": {}, "review": [], "brand": "b"})
    assert r["status"] == "EXISTS"
    assert "category" in r["remaining_work"] and "hasAdultConsideration" in r["remaining_work"]


def test_video_object_requirements() -> None:
    r = _row({"@type": "VideoObject", "name": "v", "thumbnailUrl": "t.jpg",
              "uploadDate": "2026-10-01"})
    assert r["status"] == "EXISTS" and "creator" in r["remaining_work"]


def test_self_serving_rating_on_local_business_is_flagged() -> None:
    rows = _rows({"@type": "LocalBusiness", "name": "Klinik",
                  "address": {"@type": "PostalAddress"},
                  "aggregateRating": {"@type": "AggregateRating", "ratingValue": 4.9}})
    hits = [r for r in rows if "self-serving" in r["remaining_work"]]
    assert hits and hits[0]["status"] == "TODO"


def test_incentivised_review_text_is_flagged() -> None:
    rows = _rows({"@type": "Product", "name": "p", "image": "i", "offers": {},
                  "review": [{"@type": "Review", "reviewBody": "Yorum yap kazan kampanyasıyla aldım"}]})
    assert any("incentiv" in r["remaining_work"] for r in rows)
