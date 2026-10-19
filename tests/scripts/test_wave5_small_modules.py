"""O-13 feed audit, O-14 crawl log, O-20 secondary queries, O-15 preferred sources, O-08 IndexNow key."""
from __future__ import annotations

from scripts.discovery import crawl_log as cl
from scripts.discovery import merchant_feed_audit as mf
from scripts.production import brief_signals as bs


def test_feed_audit_required_rich_and_markup() -> None:
    good = {"id": "1", "title": "Kedi kumu", "description": "d", "link": "l", "image_link": "i",
            "price": "199.90 TRY", "availability": "in_stock", "brand": "B", "gtin": "869",
            "product_highlight": ["toz yok"]}
    bad = {"id": "2", "title": "x", "price": "50 TRY"}
    rep = mf.audit_feed([good, bad], {"1": {"price": "189.90", "availability": "InStock"}})
    assert rep["complete_required_share"] == 0.5 and rep["markup_mismatch_items"] == ["1"]
    assert mf.audit_item(good, {"price": "199.90", "availability": "https://schema.org/InStock"})["markup_mismatch"] == []
    assert "gtin_or_mpn" in rep["worst"][0]["missing_required"]


def test_crawl_log_breakdown() -> None:
    ua_g = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    lines = [f'1.2.3.4 - - [19/Oct/2026:10:00:00 +0300] "GET {p} HTTP/1.1" {s} 512 "-" "{ua}"'
             for p, s, ua in [("/lastik/yaz", 200, ua_g), ("/lastik?marka=x&sort=price", 200, ua_g),
                              ("/lastik?sayfa=2", 200, ua_g), ("/x", 200, "curl/8")]]
    rep = cl.googlebot_breakdown(lines)
    assert rep["googlebot_requests"] == 3 and rep["by_type"]["facet_or_filter"] == 1
    assert rep["by_type"]["pagination"] == 1 and rep["parameter_share"] == 0.333


def test_secondary_queries_of_the_top_url() -> None:
    rows = [{"keyword": "kedi kumu", "url": "https://r.test/kum/", "rank_absolute": 1, "search_volume": 9000},
            {"keyword": "topaklanan kedi kumu", "url": "https://r.test/kum", "rank_absolute": 3, "search_volume": 800},
            {"keyword": "kedi kumu fiyat", "url": "https://r.test/kum", "rank_absolute": 9, "search_volume": 2000},
            {"keyword": "kedi maması", "url": "https://r.test/mama", "rank_absolute": 2, "search_volume": 5000}]
    q = bs.secondary_queries(rows, "https://r.test/kum", primary="kedi kumu")
    assert [r["keyword"] for r in q] == ["topaklanan kedi kumu"]


def test_preferred_sources_and_indexnow_key() -> None:
    assert bs.preferred_sources_task(["e-commerce"], has_blog=True)["primary_source"] == "manual"
    assert bs.preferred_sources_task(["local-service"], has_blog=False) is None
    key = "a1b2c3d4"
    ok, _ = bs.indexnow_key_live("x.test", key, lambda u: (200, key + "\n", {}))
    bad, why = bs.indexnow_key_live("x.test", key, lambda u: (404, "", {}))
    assert ok and not bad and "404" in why
