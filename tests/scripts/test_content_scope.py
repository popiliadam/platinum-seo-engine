"""Tests for scripts.production.content_scope (CCE batch B6).

content_scope.strip() surgically removes SITE CHROME (navigation, header,
footer, aside subtrees + link-only menus) from competitor HTML BEFORE the
recon transform measures it, WITHOUT touching article content. This is the
permanent home of B5's proof-time strip_chrome.py workaround (proof finding
#1: raw fetch inflated structure_ceiling.lists to 87 with pure menu chrome).

Pure / hermetic: stdlib html.parser only, no I/O, idempotent. These tests pin
the content-preserving contract — chrome out, every word of article in.
"""

from __future__ import annotations

from scripts.production import content_scope as cs


# ---------------------------------------------------------------------------
# Rule 1 — structural chrome subtrees are dropped whole
# ---------------------------------------------------------------------------

def test_drops_nav_subtree():
    html = (
        '<nav><ul><li><a href="/">Ana</a></li>'
        '<li><a href="/blog">Blog</a></li></ul></nav>'
        "<h2>İçerik</h2><p>metin</p>"
    )
    out = cs.strip(html)
    assert "Ana" not in out and "Blog" not in out
    assert "İçerik" in out and "metin" in out


def test_drops_header_footer_aside_subtrees():
    html = (
        "<header><h1>Site Adı</h1></header>"
        "<h2>Gerçek Başlık</h2><p>gerçek gövde</p>"
        "<aside><h3>İlgili Yazılar</h3><p>başka konu</p></aside>"
        "<footer><p>E-BÜLTEN ÜYELIK</p></footer>"
    )
    out = cs.strip(html)
    assert "Site Adı" not in out
    assert "İlgili Yazılar" not in out and "başka konu" not in out
    assert "E-BÜLTEN" not in out
    assert "Gerçek Başlık" in out and "gerçek gövde" in out


def test_nested_chrome_depth_counted():
    # A <nav> nested inside a <footer>: the inner </nav> must not prematurely
    # re-enable emission while still inside the footer subtree.
    html = (
        "<footer>dış<nav>iç menü</nav>hâlâ footer</footer>"
        "<h2>Tut</h2>"
    )
    out = cs.strip(html)
    assert "dış" not in out and "iç menü" not in out and "hâlâ footer" not in out
    assert "Tut" in out


# ---------------------------------------------------------------------------
# Rule 2 — link-only menus dropped, prose-carrying content lists kept
# ---------------------------------------------------------------------------

def test_drops_link_only_menu_keeps_content_list():
    menu = '<ul><li><a href="/a">A</a></li><li><a href="/b">B</a></li></ul>'
    content = (
        "<ul><li>Haftada 2-3 kez tara, keçeleşmeyi önler</li>"
        "<li>Tüy dökme döneminde her gün tara bakım için</li></ul>"
    )
    out = cs.strip(menu + content)
    assert "/a" not in out and ">A<" not in out
    assert "keçeleşmeyi" in out and "Tüy dökme" in out


def test_content_list_with_some_links_is_kept():
    # A genuine enumeration whose items carry prose, even though one links out,
    # is content — not a navigation menu — and must survive.
    html = (
        "<ul>"
        '<li>Protein oranı yüksek mama seçin (<a href="/k">kaynak</a>)</li>'
        "<li>Su tüketimini artırmak için çeşme tercih edin</li>"
        "<li>Tüy yumağı riskine karşı düzenli tarama yapın</li>"
        "</ul>"
    )
    out = cs.strip(html)
    assert "Protein oranı" in out
    assert "Su tüketimini" in out
    assert "Tüy yumağı" in out


def test_ordered_link_only_menu_dropped():
    html = '<ol><li><a href="/1">Bir</a></li><li><a href="/2">İki</a></li></ol>'
    assert cs.strip(html).strip() == ""


def test_nested_content_list_inside_linked_outer_is_kept():
    # A list whose own <li> are links but which WRAPS a prose content sublist
    # is content, not a menu — the inner prose must survive (code-review B6
    # finding: a kept child list makes its parent content).
    html = (
        "<ul>"
        '<li><a href="/cat">Kategori</a>'
        "<ul><li>Bu uzun bir içerik açıklamasıdır ve korunmalıdır</li>"
        "<li>İkinci içerik maddesi de bakım için buradadır</li></ul>"
        "</li>"
        "</ul>"
    )
    out = cs.strip(html)
    assert "içerik açıklamasıdır" in out
    assert "İkinci içerik maddesi" in out


def test_fully_link_only_nested_menu_still_dropped():
    # Guard: a pure menu with a link-only submenu (no prose anywhere) is still
    # dropped — the fix must not over-preserve genuine navigation.
    html = (
        "<ul>"
        '<li><a href="/a">A</a>'
        '<ul><li><a href="/a1">A1</a></li><li><a href="/a2">A2</a></li></ul>'
        "</li>"
        '<li><a href="/b">B</a></li>'
        "</ul>"
    )
    assert cs.strip(html).strip() == ""


# ---------------------------------------------------------------------------
# Content faithfulness — headings / paragraphs / tables pass through verbatim
# ---------------------------------------------------------------------------

def test_content_table_heading_paragraph_pass_through():
    html = (
        "<h2>Boyut Tablosu</h2>"
        "<table><tr><th>Özellik</th><th>Değer</th></tr>"
        "<tr><td>Ağırlık</td><td>8 kilogram</td></tr></table>"
        "<p>Maine Coon iri bir ırktır ve uzun tüylüdür.</p>"
    )
    out = cs.strip(html)
    # Every content word survives — word count must NOT drop.
    for word in (
        "Boyut", "Tablosu", "Özellik", "Değer", "Ağırlık",
        "kilogram", "Maine", "Coon", "iri", "uzun", "tüylüdür",
    ):
        assert word in out, word
    assert "<table" in out and "<th" in out and "<td" in out


def test_entities_in_content_preserved():
    # Content carrying an HTML entity must keep it (faithfulness over the proof
    # workaround, which dropped charrefs under convert_charrefs=False).
    html = "<p>kedi &amp; köpek bakımı önemlidir</p>"
    out = cs.strip(html)
    assert "&amp;" in out
    assert "kedi" in out and "köpek" in out and "bakımı" in out


# ---------------------------------------------------------------------------
# Purity — idempotent, tolerant of empty / None
# ---------------------------------------------------------------------------

def test_idempotent():
    html = "<footer><p>x</p></footer><h2>K</h2><p>içerik metni burada</p>"
    once = cs.strip(html)
    assert cs.strip(once) == once


def test_idempotent_with_quotes_in_attribute_value():
    # Real sites embed nested double-quotes in attributes (Elementor
    # data-settings JSON, owl-carousel configs, style="font-family: \"...\"").
    # Re-serialising must escape them so a second strip round-trips byte-equal.
    html = (
        '<div data-settings=\'{"bg":"classic"}\'>'
        "<p style='font-family: \"Times New Roman\"'>içerik metni buradadır</p>"
        "</div>"
    )
    once = cs.strip(html)
    assert cs.strip(once) == once
    # Content still survives the escaping.
    assert "içerik metni buradadır" in once


def test_idempotent_on_content_list():
    html = (
        "<ul><li>bir uzun içerik maddesi burada yer alır</li>"
        "<li>ikinci içerik maddesi de buradadır</li>"
        "<li>üçüncü madde bakım hakkında bilgi verir</li></ul>"
    )
    once = cs.strip(html)
    assert cs.strip(once) == once


def test_empty_and_none_safe():
    assert cs.strip("") == ""
    assert cs.strip(None) == ""
