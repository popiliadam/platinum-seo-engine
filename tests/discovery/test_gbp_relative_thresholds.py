"""S-22 — GBP audit thresholds are relative and unknown fields stay silent.

Fixed photo (>=3 / >=10) and secondary-category (>=2) thresholds had no Google
source; DFS field names did not match, so missing keys produced fake findings;
the Q&A seeding advice was outdated; the NAP address compare was
order-sensitive.
"""
from __future__ import annotations

from scripts.discovery import gbp_audit_transform as gbp
from scripts.discovery import nap_consistency

CANON = {"business_name": "Usta Kombi", "phone": "+90 232 555 11 22",
         "address": "Atatürk Cad. No 5 Karşıyaka İzmir"}

DFS_ITEM = {  # business_listings_search item shape
    "title": "Usta Kombi", "category": "Kombi servisi",
    "additional_categories": ["Klima servisi"], "total_photos": 12,
    "address": "Karşıyaka İzmir, Atatürk Cad. No 5", "phone": "+902325551122",
    "rating": {"value": 4.7, "votes_count": 88},
    "work_time": {"work_hours": {"timetable": {"monday": [{"open": {"hour": 9}}]}}},
    "attributes": {"available_attributes": {"accessibility": ["wheelchair"]}},
    "place_id": "ChIJ123",
}


def _cats(rows):
    return [(r["category"], r["severity"]) for r in rows]


def test_dfs_item_with_missing_fields_produces_no_fake_findings() -> None:
    rows = gbp._analyze_gaps(DFS_ITEM, {}, canonical_nap=CANON)
    assert rows == [], _cats(rows)


def test_photos_relative_to_competitor_median() -> None:
    comps = [{"total_photos": n, "additional_categories": ["a", "b", "c"]} for n in (40, 60, 50)]
    rows = gbp._analyze_gaps(DFS_ITEM, {}, canonical_nap=CANON, competitors=comps)
    assert ("photos", "HIGH") in _cats(rows)  # 12 < 50 / 2
    assert ("categories", "MEDIUM") in _cats(rows)  # 1 secondary vs median 3
    few = dict(DFS_ITEM, total_photos=30)
    assert ("photos", "MEDIUM") in _cats(gbp._analyze_gaps(few, {}, canonical_nap=CANON, competitors=comps))


def test_no_competitors_only_zero_photos_is_a_finding() -> None:
    zero = dict(DFS_ITEM, total_photos=0)
    assert ("photos", "MEDIUM") in _cats(gbp._analyze_gaps(zero, {}, canonical_nap=CANON))
    two = dict(DFS_ITEM, total_photos=2)
    assert "photos" not in [c for c, _ in _cats(gbp._analyze_gaps(two, {}, canonical_nap=CANON))]


def test_qa_seeding_rule_is_gone() -> None:
    rows = gbp._analyze_gaps({"business_name": "x", "qa_count": 0}, {}, canonical_nap=CANON)
    assert "qa" not in [r["category"] for r in rows]


def test_address_compare_ignores_order() -> None:
    observed = {"business_name": "Usta Kombi", "phone": "+902325551122",
                "address": "Karşıyaka İzmir, Atatürk Cad. No 5", "source": "gbp_listing"}
    assert nap_consistency.compare_nap(CANON, observed) == []


def test_street_number_swap_still_a_mismatch() -> None:
    canon = dict(CANON, address="5 Sokak No:3 Karşıyaka İzmir")
    observed = {"business_name": "Usta Kombi", "phone": "+902325551122",
                "address": "3 Sokak No:5 Karşıyaka İzmir", "source": "gbp_listing"}
    assert [f["field"] for f in nap_consistency.compare_nap(canon, observed)] == ["address"]


def test_null_total_photos_is_unknown_not_zero() -> None:
    rows = gbp._analyze_gaps(dict(DFS_ITEM, total_photos=None), {}, canonical_nap=CANON)
    assert "photos" not in [r["category"] for r in rows]
