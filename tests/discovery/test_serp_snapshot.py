"""O-04 / O-12 / O-21 — AI visibility, SERP feature history and list-page presence."""
from __future__ import annotations

from scripts.discovery import serp_snapshot as ss

ITEMS = [
    {"type": "ai_overview", "references": [{"domain": "x.test"}, {"domain": "rakip.test"}]},
    {"type": "local_pack", "items": [{"domain": "rakip.test"}, {"domain": "diger.test"}]},
    {"type": "organic", "rank_group": 1, "url": "https://rakip.test/en-iyi-kombi", "title": "En iyi 10 kombi 2026"},
    {"type": "organic", "rank_group": 3, "url": "https://www.x.test/kombi", "title": "Kombi servisi"},
]


def test_snapshot_reads_aio_features_rank_and_lists() -> None:
    s = ss.snapshot("kombi", ITEMS, "x.test")
    assert s["aio_present"] and s["aio_cited"] and s["aio_cited_competitors"] == ["rakip.test"]
    assert s["organic_rank"] == 3 and s["features"]["local_pack"] == ["diger.test", "rakip.test"]
    assert s["list_pages"][0]["url"] == "https://rakip.test/en-iyi-kombi"


def test_ai_visibility_rates() -> None:
    rows = [ss.snapshot("a", ITEMS, "x.test"), ss.snapshot("b", ITEMS[2:], "x.test"),
            ss.snapshot("c", [{"type": "ai_overview", "references": [{"domain": "r.test"}]}], "x.test")]
    assert ss.ai_visibility(rows) == {"keywords": 3, "aio_rate": 0.667, "cited_rate": 0.5,
                                      "aio_keywords": 2, "cited_keywords": 1}


def test_feature_history_gained_and_lost() -> None:
    h = ss.feature_history({
        "2026-08": [{"keyword": "otel", "features": {"local_pack": []}}],
        "2026-09": [{"keyword": "otel", "features": {"hotels_pack": [], "local_pack": []}}],
        "2026-10": [{"keyword": "otel", "features": {"hotels_pack": []}}]})
    assert h["otel"][1]["gained"] == ["hotels_pack"] and h["otel"][2]["lost"] == ["local_pack"]


def test_fanout_and_listing_marks() -> None:
    q = ss.fanout_queries("diş kliniği", city="İzmir")
    assert "en iyi diş kliniği 2026" in q and "diş kliniği İzmir" in q
    s = ss.mark_client_listed(ss.snapshot("kombi", ITEMS, "x.test"), [])
    assert s["list_pages"][0]["client_listed"] is False
