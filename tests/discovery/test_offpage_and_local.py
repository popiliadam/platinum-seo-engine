"""O-09 / O-22 / O-26 off-page lists and O-10 / O-23 / O-25 local SEO planners."""
from __future__ import annotations

from scripts.discovery import local_seo as ls
from scripts.discovery import offpage as op


def test_link_gap_excludes_domains_already_linking_to_us() -> None:
    rows = [{"referring_domain": "dergi.test", "target": "rakip1.test"},
            {"referring_domain": "dergi.test", "target": "rakip2.test"},
            {"referring_domain": "blog.test", "target": "rakip1.test"},
            {"referring_domain": "rehber.test", "target": "rakip1.test"},
            {"referring_domain": "rehber.test", "target": "rakip2.test"},
            {"referring_domain": "rehber.test", "target": "www.x.test"}]
    gap = op.link_gap(rows, ["x.test"])
    assert [g["referring_domain"] for g in gap] == ["dergi.test"]


def test_unlinked_mentions_and_dead_link_swaps() -> None:
    mentions = [{"url": "https://haber.test/a", "links": ["https://baska.test"]},
                {"url": "https://haber.test/b", "links": ["https://www.x.test/kombi"]}]
    assert [m["url"] for m in op.unlinked_mentions(mentions, "x.test")] == ["https://haber.test/a"]
    swaps = op.dead_link_swaps([{"referring_page": "https://f.test/p", "dead_target": "https://kapandi.test/kombi-bakim",
                                 "anchor": "kombi bakımı rehberi"}],
                               {"https://x.test/kombi-bakimi": "Kombi bakımı nasıl yapılır",
                                "https://x.test/klima": "Klima montajı"})
    assert swaps[0]["replacement"] == "https://x.test/kombi-bakimi"


def test_pr_queries_are_lists_not_sends() -> None:
    q = op.pr_queries("klima")
    assert "klima misafir yazı" in q and 'klima "write for us"' in q


def test_grid_and_top3_share() -> None:
    pts = ls.grid_points(38.42, 27.14, size=3, step_km=1.0)
    assert len(pts) == 9 and pts[4] == (38.42, 27.14)
    share = ls.top3_share([{"ours": 2, "leader": 1}, {"ours": 7, "leader": 1}, {"ours": None, "leader": 4}])
    assert share == {"points": 3, "top3_share": 0.333, "leader_top3_share": 0.667, "ratio_to_leader": 0.5}


def test_landing_page_seven_checks() -> None:
    nap = {"business_name": "Usta Klinik", "phone": "+90 232 555 11 22", "address": "Alsancak Mah. İzmir"}
    html = ("<title>Diş Kliniği İzmir | Usta</title><h1>İzmir Diş Kliniği</h1><h2>İmplant</h2>"
            "<iframe src=\"https://www.google.com/maps/embed?x\"></iframe><p>Hasta yorumları</p>"
            "<a href=\"tel:+902325551122\">ara</a><p>Alsancak Mah. İzmir</p>"
            '<script type="application/ld+json">{"@type": "Dentist", "name": "Usta Klinik", '
            '"address": {"streetAddress": "Alsancak Mah.", "addressLocality": "İzmir"}}</script>')
    checks = ls.landing_checks(html, category="Diş Kliniği", city="İzmir",
                               secondary_categories=["İmplant"], nap=nap)
    assert all(checks.values()), checks
    bare = ls.landing_checks("<title>x</title>", category="Diş Kliniği", city="İzmir",
                             secondary_categories=[], nap=nap)
    assert not bare["title_has_category_and_city"] and bare["secondary_categories_as_h2"] is None


def test_review_nap_and_maps_negatives() -> None:
    """Review fixes: the page's own NAP is compared (a different street number
    fails) and a plain link to Google Maps is not an embed."""
    nap = {"business_name": "Usta", "phone": "+902325551122", "address": "Atatürk Cad. No:5 İzmir"}
    html = ('<a href="https://www.google.com/maps/place/x">yol tarifi</a><a href="tel:+902325551122">ara</a>'
            '<script type="application/ld+json">{"name": "Usta", '
            '"streetAddress": "Atatürk Cad. No:15", "addressLocality": "İzmir"}</script>')
    checks = ls.landing_checks(html, category="Kombi", city="İzmir", secondary_categories=[], nap=nap)
    assert checks["nap_matches_profile"] is False and checks["google_maps_embed"] is False
    no_nap = ls.landing_checks("<p>x</p>", category="Kombi", city="İzmir", secondary_categories=[],
                               nap={**nap, "address": ""})
    assert no_nap["nap_matches_profile"] is False


def test_service_city_matrix_caps_and_requires_unique_elements() -> None:
    metrics = {"implant Karşıyaka": {"volume": 90, "cpc": 3.0}, "implant Bornova": {"volume": 50, "cpc": 2.0},
               "dolgu Karşıyaka": {"volume": 5, "cpc": 1.0}}
    m = ls.service_city_matrix(["implant", "dolgu"], ["Karşıyaka", "Bornova"], metrics, cap=1)
    assert [c["keyword"] for c in m["chosen"]] == ["implant Karşıyaka"] and m["over_cap"] == 1
    assert m["chosen"][0]["unique_elements_required"] == 3
