"""O-06 index rotation and O-24 post-publish sitemap check."""
from __future__ import annotations

from datetime import date

from scripts.discovery import index_rotation as ir
from scripts.production import post_publish_check as ppc

TODAY = date(2026, 10, 19)


def test_pick_orders_new_money_changed_and_skips_fresh() -> None:
    urls = [{"url": "https://x.test/blog/a"}, {"url": "https://x.test/kategori/kombi"},
            {"url": "https://x.test/yeni", "kind": "new"}, {"url": "https://x.test/degisen", "kind": "changed"},
            {"url": "https://x.test/taze"}]
    ledger = [{"url": "https://x.test/taze", "inspected_on": "2026-10-15", "status": "indexed"}]
    picked = ir.pick(urls, ledger, today=TODAY, quota=10)
    assert [p["url"] for p in picked] == ["https://x.test/yeni", "https://x.test/kategori/kombi",
                                          "https://x.test/degisen", "https://x.test/blog/a"]
    assert len(ir.pick(urls, ledger, today=TODAY, quota=2)) == 2


def test_ledger_row_uses_the_classifier_and_freshness_counts() -> None:
    raw = {"inspectionResult": {"indexStatusResult": {"verdict": "NEUTRAL",
                                                      "coverageState": "Crawled - currently not indexed"}}}
    row = ir.ledger_row("https://x.test/blog/a", raw, today=TODAY)
    assert row["status"] == "crawled_not_indexed"
    fr = ir.freshness(["https://x.test/blog/a", "https://x.test/b"], [row], today=TODAY)
    assert fr == {"urls": 2, "fresh": 1, "share": 0.5}


def test_not_indexed_urls_become_clusters() -> None:
    ledger = [{"url": f"https://x.test/etiket/{i}", "inspected_on": "2026-10-18",
               "status": "crawled_not_indexed"} for i in range(3)]
    ledger.append({"url": "https://x.test/blog/z", "inspected_on": "2026-10-18", "status": "indexed"})
    clusters = ir.not_indexed_clusters(ledger)
    assert clusters[0]["path_segment"] == "etiket" and clusters[0]["count"] == 3


SITEMAP_INDEX = "<sitemapindex><sitemap><loc>https://x.test/post-sitemap.xml</loc></sitemap></sitemapindex>"
POSTS = ("<urlset><url><loc>https://x.test/yeni-yazi/</loc><lastmod>2026-10-18T10:00:00+00:00</lastmod></url>"
         "<url><loc>https://x.test/eski/</loc><lastmod>2026-01-01</lastmod></url></urlset>")


def _fetch(url):
    return {"https://x.test/sitemap_index.xml": (200, SITEMAP_INDEX, {}),
            "https://x.test/post-sitemap.xml": (200, POSTS, {})}.get(url, (404, "", {}))


def test_post_publish_check() -> None:
    sm = ppc.load_sitemap("https://x.test/sitemap_index.xml", _fetch)
    assert ppc.check("https://x.test/yeni-yazi", 200, sm, published_on=date(2026, 10, 18)) == []
    assert "not in the sitemap" in ppc.check("https://x.test/kayip", 200, sm, published_on=TODAY)[0]
    issues = ppc.check("https://x.test/eski", 404, sm, published_on=date(2026, 10, 18))
    assert issues[0].startswith("HTTP 404") and "older than the publish date" in issues[1]
