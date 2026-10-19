"""S-05 — FAQPage is no longer added automatically or recommended.

The FAQ rich result stopped showing for all sites on 2026-05-07 and Google
removed its documentation on 2026-06-15. A visible, demand-driven FAQ section
stays (when it helps users); FAQPage JSON-LD is not generated, and quick-wins /
GEO no longer recommend "FAQ schema". Existing markup on live pages is harmless
and is left alone.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.discovery import geo_analysis_transform as geo
from scripts.discovery import quickwins_transform as qw

ROOT = Path(__file__).resolve().parents[2]
FAQPAGE_NODE = re.compile(r'"@type"\s*:\s*"FAQPage"')


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_templates_do_not_emit_faqpage_jsonld() -> None:
    for rel in ("templates/content/new-blog.template.html",
                "templates/content/faq-block.template.html"):
        assert not FAQPAGE_NODE.search(_read(rel)), rel


def test_templates_keep_the_visible_faq_section() -> None:
    assert "pse-faq-item" in _read("templates/content/faq-block.template.html")


def test_recommenders_do_not_suggest_faq_schema() -> None:
    assert "schema" not in qw._action_text(19.0).lower()
    assert "schema" not in geo._action_for_gap(geo.GAP_AEO_NEEDED).lower()


def test_r79_says_faqpage_is_not_auto_added() -> None:
    text = _read("rules/content-seo-discipline.md")
    block = text[text.index("### R-79"):]
    block = block[: block.index("\n### ", 5)]
    assert "2026-05-07" in block and "2026-06-15" in block
    assert "otomatik eklenmez" in block


def test_new_blog_entity_list_has_no_faqpage() -> None:
    for rel in ("commands/pseo-new-blog.md", "skills/production/new-blog/SKILL.md"):
        text = _read(rel)
        assert "+ FAQPage" not in text and "FAQPage)" not in text, rel
