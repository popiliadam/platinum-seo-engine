"""S-26 / S-16 — project voice & experience kit, the experience gate, real bylines.

S-26: generated text carried none of the business's own experience (real
      customer stories, its own numbers, the owner's opinions) and nothing
      stopped stock phrases. Each project now has a voice kit
      (projects/<slug>/voice/) and the CCE gate requires at least one sourced
      experience element — or an honest "experience missing" marker when the kit
      has none — and zero banned phrases.
S-16: the byline + Person node rendered only for YMYL. Every blog post now names
      a real author from voice/authors.json; no author → no fabricated one.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.production import quality_gates as qg
from scripts.production import voice_kit as vk

ROOT = Path(__file__).resolve().parents[2]


def _kit_dir(tmp_path: Path, *, facts=None, stories=None, banned="", authors=None) -> Path:
    d = tmp_path / "projects" / "demo" / "voice"
    d.mkdir(parents=True)
    (d / "voice.md").write_text("Samimi, kısa cümleler.", encoding="utf-8")
    (d / "opinions.md").write_text("Ucuz kombi uzun vadede pahalıya gelir.", encoding="utf-8")
    (d / "facts.json").write_text(json.dumps(facts or []), encoding="utf-8")
    (d / "stories.json").write_text(json.dumps(stories or []), encoding="utf-8")
    (d / "banned-phrases.txt").write_text(banned, encoding="utf-8")
    (d / "authors.json").write_text(json.dumps(authors or []), encoding="utf-8")
    return tmp_path / "projects" / "demo"


FACT = {"claim": "2014'ten beri 3.200 kombi montajı", "source": "firma kayıtları 2026"}
AUTHOR = {"name": "Mehmet Kaya", "role": "Usta / kurucu", "url": "https://x.test/hakkimizda",
          "sameAs": ["https://www.linkedin.com/in/mehmetkaya"]}


# --- voice kit loader -------------------------------------------------------------

def test_kit_loads_all_files(tmp_path: Path) -> None:
    kit = vk.load_voice_kit(_kit_dir(tmp_path, facts=[FACT], banned="kısacası\n\n", authors=[AUTHOR]))
    assert kit.facts == (FACT,) and kit.authors[0]["name"] == "Mehmet Kaya"
    assert kit.banned_phrases == ("kısacası",)
    assert kit.missing == ()


def test_missing_kit_files_are_listed_not_invented(tmp_path: Path) -> None:
    kit = vk.load_voice_kit(tmp_path / "projects" / "nope")
    assert set(kit.missing) == set(vk.KIT_FILES)
    assert kit.facts == () and kit.authors == ()


def test_brief_block_carries_facts_stories_and_banned(tmp_path: Path) -> None:
    kit = vk.load_voice_kit(_kit_dir(tmp_path, facts=[FACT], banned="kısacası"))
    block = kit.brief_block()
    assert block["facts"] == [FACT] and "kısacası" in block["banned_phrases"]


# --- experience gate -----------------------------------------------------------------

def _html(body: str) -> str:
    return f"<article><p>Giriş.</p>{body}</article>"


def _gate(html: str, experience: dict | None) -> dict:
    brief = {} if experience is None else {"experience": experience}
    res = qg.run_all(html, brief)
    return next(g for g in res["gates"] if g["gate"] == "experience")


def test_sourced_experience_element_passes() -> None:
    html = _html('<p data-experience="fact" data-source="firma kayıtları 2026">2014\'ten beri 3.200 kombi montajı yaptık.</p>')
    assert _gate(html, {"facts": [FACT], "stories": [], "banned_phrases": []})["status"] == "PASS"


def test_kit_has_material_but_article_uses_none_is_red() -> None:
    assert _gate(_html("<p>Genel bilgi.</p>"), {"facts": [FACT], "stories": [], "banned_phrases": []})["status"] == "RED"


def test_experience_element_without_source_is_red() -> None:
    html = _html('<p data-experience="fact">3.200 montaj.</p>')
    assert _gate(html, {"facts": [FACT], "stories": [], "banned_phrases": []})["status"] == "RED"


def test_empty_kit_needs_an_honest_missing_marker() -> None:
    empty = {"facts": [], "stories": [], "banned_phrases": []}
    assert _gate(_html("<p>x</p>"), empty)["status"] == "RED"
    marked = _html("<!-- experience-missing: müşteri henüz vaka paylaşmadı --><p>x</p>")
    assert _gate(marked, empty)["status"] == "PASS"


def test_banned_phrases_are_red() -> None:
    html = _html('<p data-experience="fact" data-source="kayıt">Kısacası 3.200 montaj.</p>')
    assert _gate(html, {"facts": [FACT], "stories": [], "banned_phrases": ["kısacası"]})["status"] == "RED"
    stock = _html('<p>Günümüzün hızlı dünyasında</p><p data-experience="fact" data-source="kayıt">3.200</p>')
    assert _gate(stock, {"facts": [FACT], "stories": [], "banned_phrases": []})["status"] == "RED"


def test_experience_is_a_registered_gate() -> None:
    assert "experience" in qg.GATE_ORDER


def test_golden_article_still_passes_overall() -> None:
    fix = ROOT / "tests" / "scripts" / "fixtures" / "cce"
    brief = json.loads((fix / "sample_brief.json").read_text(encoding="utf-8"))
    res = qg.run_all((fix / "good_article.html").read_text(encoding="utf-8"), brief)
    assert res["overall"] == "PASS", res["rewrite_feedback"]


# --- S-16 byline -----------------------------------------------------------------------

def test_template_renders_byline_and_person_for_every_real_author() -> None:
    tpl = (ROOT / "templates" / "content" / "new-blog.template.html").read_text(encoding="utf-8")
    byline = tpl[tpl.index('<address class="pse-author">') - 80: tpl.index("</address>")]
    assert "{{#IF_AUTHOR}}" in byline and "IF_PROFILE_YMYL" not in byline
    person = tpl[tpl.index('"@type": "Person"') - 120: tpl.index('"@type": "Person"')]
    assert "{{#IF_AUTHOR}}" in person and "IF_PROFILE_YMYL" not in person


def test_story_without_consent_is_not_used(tmp_path: Path) -> None:
    ok = {"summary": "Kombi 1 günde değişti", "source": "Google yorumu", "consent": True}
    no = {"summary": "Gizli vaka", "source": "e-posta", "consent": False}
    kit = vk.load_voice_kit(_kit_dir(tmp_path, stories=[ok, no]))
    assert kit.stories == (ok,)


def test_non_utf8_kit_file_is_reported_missing(tmp_path: Path) -> None:
    d = _kit_dir(tmp_path)
    (d / "voice" / "voice.md").write_bytes(b"\xff\xfe\x00bad")
    assert "voice.md" in vk.load_voice_kit(d).missing
