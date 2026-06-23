"""Tests for scripts.production.competitor_recon_transform (CCE batch B1).

Hermetic: no live MCP. SERP payloads + scraped-page HTML are inline fixtures.
The transform is pure (no I/O on import, idempotent) — these tests pin the
contract that batches B2 (quality_gates) and B4 (orchestrator) depend on.
"""

from __future__ import annotations

from scripts.production import competitor_recon_transform as cr

# An organic-empty SERP envelope (REST shape). No organic URLs → competitors
# keep their input order; the HTML parse is exercised in isolation.
EMPTY_SERP: dict = {"tasks": [{"result": [{"items": []}]}]}


# ---------------------------------------------------------------------------
# Contract tests (verbatim from the B1 worker brief)
# ---------------------------------------------------------------------------

def test_counts_meaningful_table_only():
    html = (
        "<h2>Fiyat Karşılaştırması</h2>"
        "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        "<table><tr><td>tek hücre</td></tr></table>"  # 2. tablo anlamsız
    )
    out = cr.transform(
        {"tasks": [{"result": [{"items": []}]}]},
        [{"url": "https://x.example/p", "html": html}],
        market="TR",
    )
    assert out[0]["tables"] == 1  # sadece anlamlı tablo
    assert "Fiyat Karşılaştırması" in out[0]["h2_h3"]


def test_question_heading_detected():
    html = "<h3>İmplant ağrır mı?</h3><p>...</p>"
    out = cr.transform(
        {"tasks": [{"result": [{"items": []}]}]},
        [{"url": "https://x.example/p", "html": html}],
        market="TR",
    )
    assert "İmplant ağrır mı?" in out[0]["questions"]


# ---------------------------------------------------------------------------
# Meaningful table / list discipline
# ---------------------------------------------------------------------------

def test_table_needs_two_rows_and_two_cols():
    # 2 rows but only 1 column → not meaningful.
    one_col = "<table><tr><td>a</td></tr><tr><td>b</td></tr></table>"
    # 2 cols but only 1 row → not meaningful.
    one_row = "<table><tr><th>a</th><th>b</th></tr></table>"
    out = cr.transform(
        EMPTY_SERP,
        [
            {"url": "u1", "html": one_col},
            {"url": "u2", "html": one_row},
        ],
        market="TR",
    )
    assert out[0]["tables"] == 0
    assert out[1]["tables"] == 0


def test_list_requires_three_li():
    two_li = "<ul><li>a</li><li>b</li></ul>"
    three_li = "<ul><li>a</li><li>b</li><li>c</li></ul>"
    three_ol = "<ol><li>1</li><li>2</li><li>3</li></ol>"
    out = cr.transform(
        EMPTY_SERP,
        [
            {"url": "u1", "html": two_li},
            {"url": "u2", "html": three_li},
            {"url": "u3", "html": three_ol},
        ],
        market="TR",
    )
    assert out[0]["lists"] == 0
    assert out[1]["lists"] == 1
    assert out[2]["lists"] == 1


def test_nested_list_counts_each_list_by_its_own_li():
    # Outer ul has 3 direct li (one of which nests a 2-li ul). Outer is
    # meaningful; the nested 2-li list is not.
    html = (
        "<ul><li>a</li><li>b<ul><li>x</li><li>y</li></ul></li><li>c</li></ul>"
    )
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    assert out[0]["lists"] == 1


# ---------------------------------------------------------------------------
# Heading tree / questions / entities
# ---------------------------------------------------------------------------

def test_h2_h3_excludes_other_heading_levels():
    html = "<h1>H1</h1><h2>H2</h2><h3>H3</h3><h4>H4</h4>"
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    assert out[0]["h2_h3"] == ["H2", "H3"]


def test_entities_from_headings_and_strong_deduped_case_insensitive():
    html = (
        "<h2>İmplant</h2><h3>Fiyat</h3>"
        "<p><strong>İmplant</strong> ve <b>Zirkonyum</b></p>"
    )
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    # h2/h3 candidates first, then <strong>/<b>; "İmplant" deduped.
    assert out[0]["entities"] == ["İmplant", "Fiyat", "Zirkonyum"]


def test_faq_jsonld_questions_extracted():
    html = (
        "<h2>SSS</h2>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"FAQPage","mainEntity":'
        '[{"@type":"Question","name":"Garanti var mı?",'
        '"acceptedAnswer":{"@type":"Answer","text":"Evet."}}]}'
        "</script>"
    )
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    assert "Garanti var mı?" in out[0]["questions"]


def test_questions_deduped_when_heading_and_faq_match():
    html = (
        "<h3>Garanti var mı?</h3>"
        '<script type="application/ld+json">'
        '{"@type":"FAQPage","mainEntity":[{"@type":"Question",'
        '"name":"Garanti var mı?"}]}'
        "</script>"
    )
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    assert out[0]["questions"].count("Garanti var mı?") == 1


# ---------------------------------------------------------------------------
# Word count — visible text only
# ---------------------------------------------------------------------------

def test_word_count_excludes_script_and_style():
    html = (
        "<h2>Başlık</h2><p>bir iki üç</p>"
        '<script>var gizli = "kelime kelime kelime";</script>'
        "<style>.x{content:'gizli'}</style>"
    )
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    # "Başlık" + "bir" "iki" "üç" = 4 visible words.
    assert out[0]["word_count"] == 4


# ---------------------------------------------------------------------------
# SERP ordering
# ---------------------------------------------------------------------------

def test_competitors_ordered_by_serp_rank():
    serp = {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {"type": "organic", "url": "https://b.example/", "rank_group": 1},
                            {"type": "organic", "url": "https://a.example/", "rank_group": 2},
                        ]
                    }
                ]
            }
        ]
    }
    pages = [
        {"url": "https://a.example/", "html": "<h2>A</h2>"},
        {"url": "https://b.example/", "html": "<h2>B</h2>"},
    ]
    out = cr.transform(serp, pages, market="TR")
    assert [c["url"] for c in out] == ["https://b.example/", "https://a.example/"]


def test_malformed_serp_falls_back_to_input_order():
    # Unrecognisable SERP shape must NOT crash the competitor analysis —
    # SERP is only used for ordering, the HTML parse is the deliverable.
    pages = [
        {"url": "u1", "html": "<h2>One</h2>"},
        {"url": "u2", "html": "<h2>Two</h2>"},
    ]
    out = cr.transform({"garbage": True}, pages, market="TR")
    assert [c["url"] for c in out] == ["u1", "u2"]


# ---------------------------------------------------------------------------
# Content-scoping (B6) — site chrome must not inflate the structure ceiling
# ---------------------------------------------------------------------------

def test_recon_ignores_site_chrome():
    """B6 proof finding #1: a menu-heavy competitor page must have its
    structure measured on the ARTICLE only. The nav/aside/footer subtrees and
    a bare link-only menu (5 chrome lists total) collapse, leaving exactly the
    one real content list; chrome headings/anchors are not counted as
    competitor entities."""
    html = (
        # nav menu — link-only ul (4 li)
        "<nav><ul>"
        '<li><a href="/">Ana Sayfa</a></li>'
        '<li><a href="/kedi">Kedi</a></li>'
        '<li><a href="/kopek">Köpek</a></li>'
        '<li><a href="/iletisim">İletişim</a></li>'
        "</ul></nav>"
        # aside related-posts — heading + link-only ul (3 li)
        "<aside><h2>İlgili Yazılar</h2><ul>"
        '<li><a href="/a">Hamster sesleri</a></li>'
        '<li><a href="/b">Köpek pati yalama</a></li>'
        '<li><a href="/c">Bernese dağ köpeği</a></li>'
        "</ul></aside>"
        # bare link-only tag menu (3 li, NOT inside a chrome tag → Rule 2)
        "<ul>"
        '<li><a href="/x">Etiket1</a></li>'
        '<li><a href="/y">Etiket2</a></li>'
        '<li><a href="/z">Etiket3</a></li>'
        "</ul>"
        # real article content — heading + prose content list (3 li)
        "<h2>Maine Coon Bakımı</h2>"
        "<ul><li>Haftada birkaç kez tarama keçeleşmeyi önler</li>"
        "<li>Tüy dökme döneminde günlük tarama gerekir</li>"
        "<li>Düzenli tırnak bakımı yapılmalıdır</li></ul>"
        # footer menu — link-only ul (3 li)
        "<footer><ul>"
        '<li><a href="/gizlilik">Gizlilik</a></li>'
        '<li><a href="/kvkk">KVKK</a></li>'
        '<li><a href="/sss">SSS</a></li>'
        "</ul></footer>"
    )
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    # Only the article's content list survives the 5 chrome menus.
    assert out[0]["lists"] == 1
    # Chrome headings are not mistaken for competitor entities.
    assert "İlgili Yazılar" not in out[0]["h2_h3"]
    assert "Maine Coon Bakımı" in out[0]["h2_h3"]


def test_clean_html_unaffected_by_content_scoping():
    """The strip must be a no-op on chrome-free markup — a genuine content
    list and table still count exactly as before B6."""
    html = (
        "<h2>Karşılaştırma</h2>"
        "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        "<ul><li>birinci madde</li><li>ikinci madde</li><li>üçüncü madde</li></ul>"
    )
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": html}], market="TR")
    assert out[0]["tables"] == 1
    assert out[0]["lists"] == 1
    assert out[0]["h2_h3"] == ["Karşılaştırma"]


# ---------------------------------------------------------------------------
# Output shape / edge cases / purity
# ---------------------------------------------------------------------------

def test_record_has_exact_contract_keys_in_order():
    out = cr.transform(EMPTY_SERP, [{"url": "u", "html": "<h2>x</h2>"}], market="TR")
    assert list(out[0].keys()) == [
        "url",
        "h2_h3",
        "questions",
        "entities",
        "tables",
        "lists",
        "word_count",
    ]


def test_empty_scraped_pages_returns_empty_list():
    assert cr.transform(EMPTY_SERP, [], market="TR") == []


def test_idempotent_same_input_same_output():
    html = (
        "<h2>Fiyat</h2><table><tr><th>A</th><th>B</th></tr>"
        "<tr><td>1</td><td>2</td></tr></table><ul><li>a</li><li>b</li><li>c</li></ul>"
    )
    pages = [{"url": "u", "html": html}]
    first = cr.transform(EMPTY_SERP, pages, market="TR")
    second = cr.transform(EMPTY_SERP, pages, market="TR")
    assert first == second


def test_empty_market_raises():
    import pytest

    with pytest.raises(ValueError):
        cr.transform(EMPTY_SERP, [{"url": "u", "html": "<h2>x</h2>"}], market="")
