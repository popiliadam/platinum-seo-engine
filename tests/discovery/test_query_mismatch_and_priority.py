"""O-16 / O-17 — target-vs-actual query mismatch and business-value ranking."""
from __future__ import annotations

from scripts.discovery import commercial_priority as cp
from scripts.discovery import query_mismatch as qm


def _row(q, page, imp, clicks, pos):
    return {"keys": [q, page], "impressions": imp, "clicks": clicks, "position": pos}


GSC = [
    _row("kombi bakımı fiyat", "https://x.test/kombi-bakim/", 900, 9, 11.0),
    _row("kombi bakımı nasıl yapılır", "https://x.test/kombi-bakim/", 300, 6, 7.0),
    _row("klima montajı", "https://x.test/klima/", 2000, 20, 2.0),
    _row("İzmir klima servisi", "https://x.test/servis/", 500, 40, 3.0),
]


def test_mismatch_in_rewrite_band_gets_a_rewrite_task() -> None:
    rows = qm.find_mismatches({"https://x.test/kombi-bakim": "kombi bakımı nasıl yapılır"}, GSC)
    assert rows[0]["top_query"] == "kombi bakımı fiyat" and rows[0]["action"] == "rewrite"
    assert "kombi bakımı fiyat" in rows[0]["suggestion"]


def test_top3_with_low_ctr_checks_aio_first() -> None:
    rows = qm.find_mismatches({"https://x.test/klima": "klima fiyatları"}, GSC)
    assert rows[0]["action"] == "check_aio" and "dokunma" in rows[0]["suggestion"]


def test_matching_query_is_not_reported_turkish_case_aware() -> None:
    assert qm.find_mismatches({"https://x.test/servis": "izmir klima servisi"}, GSC) == []


def test_page_types_and_serp_intent() -> None:
    assert cp.page_type("https://x.test/kategori/kombi") == "category"
    assert cp.page_type("https://x.test/blog/kombi-nasil") == "blog"
    assert cp.page_type("https://x.test/hizmetler/kombi-servisi") == "service"
    assert cp.serp_intent(["https://a.test/kategori/k", "https://b.test/urun/u", "https://c.test/blog/b"]) == "commercial"
    assert cp.serp_intent(["https://a.test/blog/1", "https://b.test/rehber/2", "https://c.test/"]) == "informational"


def test_rank_prefers_commercial_value_over_traffic() -> None:
    rows = cp.rank([
        {"keyword": "kombi nedir", "position": 4, "cpc": 0.2,
         "top_urls": ["https://a.test/blog/1", "https://b.test/blog/2", "https://c.test/rehber/3"]},
        {"keyword": "kombi fiyatları", "position": 9, "cpc": 2.5,
         "top_urls": ["https://a.test/kategori/k", "https://b.test/urun/u", "https://c.test/kategori/x"]},
    ])
    assert rows[0]["keyword"] == "kombi fiyatları" and rows[0]["intent"] == "commercial"
    assert rows[1]["intent"] == "informational"
