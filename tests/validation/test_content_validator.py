"""tests/validation/test_content_validator.py — deterministic content validator.

Covers the v1 "balanced" rule set (audit 2026-06-04 Gap 1): the AI-disclosure
ban + R-22/R-43/R-77/R-61 hard blocks + R-106/R-101/R-104 advisories, plus the
false-positive guards that keep AI-*topic* content and JSON-LD/IPTC disclosure
from tripping the gate.

Design ref: docs/superpowers/specs/2026-06-04-content-validator-design.md
"""

from __future__ import annotations

from scripts.validation.content_validator import (
    extract_visible_text,
    validate_content,
)


# --------------------------------------------------------------------------
# Visible-text extraction — the foundation the text-based rules run on.
# --------------------------------------------------------------------------

def test_extract_visible_text_strips_script_style_and_comments() -> None:
    html = (
        "<p>Görünür metin</p>"
        '<script type="application/ld+json">{"x":"gizli_script"}</script>'
        "<!-- gizli_yorum -->"
        "<style>.pse-x{color:red}</style>"
    )
    text = extract_visible_text(html)
    assert "Görünür metin" in text
    assert "gizli_script" not in text
    assert "gizli_yorum" not in text
    assert "color:red" not in text


# --------------------------------------------------------------------------
# AI-disclosure ban (🔴 RED) — the project's hardest constraint.
# --------------------------------------------------------------------------

def test_turkish_ai_disclosure_phrase_blocks() -> None:
    html = (
        '<article class="pse-blog-post"><p>Bu içerik yapay zeka tarafından '
        "yazılmıştır.</p></article>"
    )
    report = validate_content(html)
    assert report.verdict == "RED"
    assert any(f.rule == "AI-disclosure" for f in report.findings)


def test_english_ai_disclosure_phrase_blocks() -> None:
    html = (
        '<article class="pse-blog-post"><p>This article was written by AI to '
        "save time.</p></article>"
    )
    report = validate_content(html)
    assert report.verdict == "RED"
    assert any(f.rule == "AI-disclosure" for f in report.findings)


def test_as_an_ai_language_model_phrase_blocks() -> None:
    html = (
        '<article class="pse-blog-post"><p>As an AI language model, I cannot '
        "verify this.</p></article>"
    )
    report = validate_content(html)
    assert any(f.rule == "AI-disclosure" for f in report.findings)


# --------------------------------------------------------------------------
# False-positive guards — these MUST pass the AI-disclosure rule.
# --------------------------------------------------------------------------

def test_ai_topic_blog_without_disclosure_passes_disclosure_rule() -> None:
    """A blog *about* AI uses 'yapay zeka'/'AI' heavily but discloses nothing.

    The bare term must never trip the ban — only multi-word disclosure phrases.
    """
    html = (
        '<article class="pse-blog-post"><p>Yapay zeka nedir? Yapay zeka, '
        "makinelerin veriden öğrenmesini sağlayan bir alandır. AI sistemleri "
        "bugün pek çok sektörde kullanılır.</p></article>"
    )
    report = validate_content(html)
    assert not any(f.rule == "AI-disclosure" for f in report.findings)


def test_disclosure_inside_jsonld_script_is_ignored() -> None:
    """A disclosure phrase that lives only in a JSON-LD <script> (not visible
    text) must not trip the ban — schema/IPTC disclosure (R-123) is required."""
    html = (
        '<article class="pse-blog-post"><p>Kaliteli ve özgün içerik.</p>'
        '<script type="application/ld+json">'
        '{"description":"AI-generated content"}</script></article>'
    )
    report = validate_content(html)
    assert not any(f.rule == "AI-disclosure" for f in report.findings)


# --------------------------------------------------------------------------
# Structural hard blocks (🔴 RED): R-22, R-43, R-77, R-61.
# --------------------------------------------------------------------------

def test_doctype_or_document_tag_blocks_r22() -> None:
    html = (
        "<!DOCTYPE html><html><body>"
        '<article class="pse-blog-post"><p>Metin.</p></article>'
        "</body></html>"
    )
    report = validate_content(html)
    assert report.verdict == "RED"
    assert any(f.rule == "R-22" for f in report.findings)


def test_semantic_header_tag_does_not_trip_r22() -> None:
    """<header>/<footer> are allowed semantic HTML5; only <head>/<html>/<body>/
    doctype are forbidden. Guards the <head> vs <header> prefix collision."""
    html = (
        '<article class="pse-blog-post"><header><h2>Başlık</h2></header>'
        "<p>Metin.</p></article>"
    )
    report = validate_content(html)
    assert not any(f.rule == "R-22" for f in report.findings)


def test_faq_accordion_blocks_r43() -> None:
    html = (
        '<article class="pse-blog-post"><details><summary>Soru?</summary>'
        "<p>Cevap.</p></details></article>"
    )
    report = validate_content(html)
    assert any(f.rule == "R-43" for f in report.findings)


def test_img_without_alt_blocks_r77() -> None:
    html = (
        '<article class="pse-blog-post">'
        '<img src="hero.webp" width="1200" height="675"></article>'
    )
    report = validate_content(html)
    assert any(f.rule == "R-77" for f in report.findings)


def test_img_with_empty_alt_blocks_r77() -> None:
    html = '<article class="pse-blog-post"><img src="hero.webp" alt=""></article>'
    report = validate_content(html)
    assert any(f.rule == "R-77" for f in report.findings)


def test_img_with_descriptive_alt_passes_r77() -> None:
    html = (
        '<article class="pse-blog-post">'
        '<img src="hero.webp" alt="Ürün fotoğrafı"></article>'
    )
    report = validate_content(html)
    assert not any(f.rule == "R-77" for f in report.findings)


def test_non_pse_class_blocks_r61() -> None:
    html = (
        '<article class="pse-blog-post"><div class="container highlight">'
        "x</div></article>"
    )
    report = validate_content(html)
    assert any(f.rule == "R-61" for f in report.findings)


def test_all_pse_classes_pass_r61() -> None:
    html = '<article class="pse-blog-post"><p class="pse-lead">x</p></article>'
    report = validate_content(html)
    assert not any(f.rule == "R-61" for f in report.findings)


def test_multiple_red_findings_reported_together() -> None:
    html = '<!DOCTYPE html><article class="sloppy"><p>Metin.</p></article>'
    report = validate_content(html)
    assert report.verdict == "RED"
    rules = {f.rule for f in report.findings}
    assert "R-22" in rules
    assert "R-61" in rules


# --------------------------------------------------------------------------
# Advisory rules (🟡 AMBER): R-106 citation density, R-101 self-contained
# intro, R-104 profile-aware stats density.
# --------------------------------------------------------------------------

def test_low_citation_density_warns_r106() -> None:
    body = "kelime " * 450  # ~450 visible words, 0 citations
    html = f'<article class="pse-blog-post"><p>{body}</p></article>'
    report = validate_content(html, profile=None)
    assert report.verdict == "AMBER"
    assert any(f.rule == "R-106" for f in report.findings)


def test_adequate_citation_density_passes_r106() -> None:
    body = "kelime " * 450
    html = (
        f'<article class="pse-blog-post"><p>{body}</p>'
        '<p>Kaynak: <a href="https://x.gov" rel="external noopener">'
        "Resmî veri</a>.</p></article>"
    )
    report = validate_content(html, profile=None)
    assert not any(f.rule == "R-106" for f in report.findings)


def test_short_content_skips_citation_density_r106() -> None:
    html = '<article class="pse-blog-post"><p>Kısa bir paragraf.</p></article>'
    report = validate_content(html, profile=None)
    assert not any(f.rule == "R-106" for f in report.findings)


def test_back_reference_intro_warns_r101() -> None:
    html = (
        '<article class="pse-blog-post"><p>Bu yazıda klima montajını adım adım '
        "anlatacağız.</p></article>"
    )
    report = validate_content(html)
    assert any(f.rule == "R-101" for f in report.findings)


def test_self_contained_intro_passes_r101() -> None:
    html = (
        '<article class="pse-blog-post"><p>Klima montajı, doğru konumlandırma '
        "ve sızdırmazlık gerektirir.</p></article>"
    )
    report = validate_content(html)
    assert not any(f.rule == "R-101" for f in report.findings)


def test_stats_density_is_profile_aware_r104() -> None:
    """Same content: AMBER for YMYL (min 1/500w) but GREEN for local-service
    (min 1/1000w). ~1003 words, 1 stat."""
    body = "kelime " * 1000
    html = f'<article class="pse-blog-post"><p>{body}</p><p>Oran %50 oldu.</p></article>'
    ymyl = validate_content(html, profile="ymyl")
    local = validate_content(html, profile="local-service")
    assert any(f.rule == "R-104" for f in ymyl.findings)
    assert not any(f.rule == "R-104" for f in local.findings)


def test_clean_content_is_green() -> None:
    html = (
        '<article class="pse-blog-post">'
        '<p class="pse-lead">Klima bakımı, verimli soğutma için düzenli '
        "temizlik ve gaz kontrolü gerektirir.</p>"
        '<img src="bakim.webp" alt="Klima bakımı yapan teknisyen" '
        'width="1200" height="675">'
        "<p>Filtreleri ayda bir temizleyin.</p></article>"
    )
    report = validate_content(html, profile="local-service")
    assert report.verdict == "GREEN"
    assert report.findings == []


# --------------------------------------------------------------------------
# CLI entrypoint (CI / manual): exit 1 on RED, 0 otherwise.
# --------------------------------------------------------------------------

def test_cli_returns_1_on_red(tmp_path) -> None:
    from scripts.validation.content_validator import main

    path = tmp_path / "article.html"
    path.write_text(
        '<article class="pse-blog-post"><p>This was written by AI.</p></article>',
        encoding="utf-8",
    )
    assert main([str(path)]) == 1


def test_cli_returns_0_on_clean(tmp_path) -> None:
    from scripts.validation.content_validator import main

    path = tmp_path / "article.html"
    path.write_text(
        '<article class="pse-blog-post"><p>Temiz ve özgün içerik.</p></article>',
        encoding="utf-8",
    )
    assert main([str(path)]) == 0


# --------------------------------------------------------------------------
# Review-hardening (code review 2026-06-04): false-negatives / false-positives.
# --------------------------------------------------------------------------

def test_turkish_ai_disclosure_kullanilarak_blocks() -> None:
    """'using AI' phrasing (kullanılarak/yardımıyla) must also block (C2)."""
    html = (
        '<article class="pse-blog-post"><p>Bu içerik yapay zeka kullanılarak '
        "hazırlanmıştır.</p></article>"
    )
    report = validate_content(html)
    assert report.verdict == "RED"
    assert any(f.rule == "AI-disclosure" for f in report.findings)


def test_inline_svg_classes_do_not_trip_r61() -> None:
    """Third-party classes inside an inline <svg> icon must not false-trip R-61
    and block a legitimate article (C3)."""
    html = (
        '<article class="pse-blog-post"><p class="pse-lead">Metin.</p>'
        '<svg class="icon" viewBox="0 0 24 24">'
        '<path class="fill-current" d="M0 0"/></svg></article>'
    )
    report = validate_content(html)
    assert not any(f.rule == "R-61" for f in report.findings)


def test_unclosed_style_does_not_hide_disclosure() -> None:
    """A malformed unclosed <style> must not silence the AI-disclosure check on
    text that follows it (H1 — silent fail-open on the hard constraint)."""
    html = (
        '<article class="pse-blog-post"><style>.pse-x{color:red}'
        "<p>This was written by AI.</p></article>"
    )
    report = validate_content(html)
    assert any(f.rule == "AI-disclosure" for f in report.findings)


def test_jsonld_paragraph_does_not_trigger_false_r101() -> None:
    """A <p> encoded inside a JSON-LD <script> before the real intro must not
    be mistaken for the intro paragraph (H2)."""
    html = (
        '<script type="application/ld+json">'
        '{"articleBody":"<p>bu yazıda anlatılanlar</p>"}</script>'
        '<article class="pse-blog-post"><p>Klima montajı dikkat ister.</p>'
        "</article>"
    )
    report = validate_content(html)
    assert not any(f.rule == "R-101" for f in report.findings)
