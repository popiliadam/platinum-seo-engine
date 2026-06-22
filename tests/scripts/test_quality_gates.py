"""Tests for scripts/production/quality_gates.py — CCE Gate Engine (B2).

Hermetic golden tests: a known-good article passes all 8 gates; a known-bad
(thin / generic / AI-signature) article fails. Each gate has at least one
dedicated test. No live MCP — fixtures only.

Contract under test (B4 orchestrator depends on it verbatim):
  - GateResult dataclass: gate / status / detail / missing
  - run_all(content_html: str, brief: dict) -> dict with keys
    {"gates":[...], "overall":"PASS"|"RED", "rewrite_feedback":[...]}
  - overall == PASS iff no gate is RED; P0 RED forces overall RED (above gap).
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.production import quality_gates as qg

FIX = Path(__file__).parent / "fixtures" / "cce"

# Filler ≥40-word body so a section is never thin by accident in inline HTML.
BODY = "kelime " * 60


def _brief() -> dict:
    return json.loads((FIX / "sample_brief.json").read_text(encoding="utf-8"))


def _gate(res: dict, name: str) -> dict:
    return next(g for g in res["gates"] if g["gate"] == name)


# ---------------------------------------------------------------------------
# Golden end-to-end (worker-prompt example tests)
# ---------------------------------------------------------------------------

def test_bad_article_fails_overall():
    res = qg.run_all((FIX / "bad_article.html").read_text(encoding="utf-8"), _brief())
    assert res["overall"] == "RED"
    assert any(g["gate"] == "depth" and g["status"] == "RED" for g in res["gates"])


def test_good_article_passes_overall():
    res = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), _brief())
    assert res["overall"] == "PASS", res["rewrite_feedback"]


def test_p0_beats_gap_honest_skip():
    # kaynaksız gap maddesi dürüstçe atlanmış → gap PASS (uydurma değil)
    brief = _brief()
    brief["gap"]["must_cover_headings"] = ["Bizde-kaynak-yok-konu"]
    html = (
        '<article><!-- gap-skipped: kaynak yok --><h2>Bir konu</h2><p>'
        + BODY
        + "</p></article>"
    )
    g = _gate(qg.run_all(html, brief), "gap")
    assert g["status"] == "PASS"


# ---------------------------------------------------------------------------
# Contract shape
# ---------------------------------------------------------------------------

def test_run_all_contract_shape():
    res = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), _brief())
    assert set(res.keys()) == {"gates", "overall", "rewrite_feedback"}
    assert res["overall"] in {"PASS", "RED"}
    assert isinstance(res["rewrite_feedback"], list)
    expected_gates = {
        "p0_truthfulness", "gap", "structure", "depth",
        "aeo", "voice", "originality", "schema_visual",
    }
    assert {g["gate"] for g in res["gates"]} == expected_gates
    for g in res["gates"]:
        assert set(g.keys()) == {"gate", "status", "detail", "missing"}
        assert g["status"] in {"PASS", "RED", "AMBER"}
        assert isinstance(g["missing"], list)
    # P0 is evaluated/listed first.
    assert res["gates"][0]["gate"] == "p0_truthfulness"


def test_red_gates_produce_rewrite_feedback():
    res = qg.run_all((FIX / "bad_article.html").read_text(encoding="utf-8"), _brief())
    assert res["rewrite_feedback"]  # non-empty when something is RED
    # PASS run carries no feedback
    ok = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), _brief())
    assert ok["rewrite_feedback"] == []


# ---------------------------------------------------------------------------
# Gate 0 — P0 truthfulness (absolute, above gap)
# ---------------------------------------------------------------------------

def test_p0_red_on_uncited_stat():
    html = "<article><p>Hastaların %92'si bu yöntemden memnun kaldı.</p></article>"
    g = _gate(qg.run_all(html, _brief()), "p0_truthfulness")
    assert g["status"] == "RED"
    assert g["missing"]


def test_p0_pass_with_parenthetical_citation():
    html = "<article><p>Hastaların %92'si memnun kaldı (Sağlık Bakanlığı, 2024).</p></article>"
    g = _gate(qg.run_all(html, _brief()), "p0_truthfulness")
    assert g["status"] == "PASS"


def test_p0_pass_with_anchor_citation():
    html = '<article><p>Başarı oranı yaklaşık %97 olarak <a href="/k">raporlanmıştır</a>.</p></article>'
    g = _gate(qg.run_all(html, _brief()), "p0_truthfulness")
    assert g["status"] == "PASS"


def test_p0_red_forces_overall_red():
    html = "<article><p>Tedavi %200 oranında etkilidir.</p></article>"
    res = qg.run_all(html, _brief())
    assert _gate(res, "p0_truthfulness")["status"] == "RED"
    assert res["overall"] == "RED"


# ---------------------------------------------------------------------------
# Gate 1 — Gap
# ---------------------------------------------------------------------------

def test_gap_red_on_uncovered_sourced_item():
    brief = _brief()
    brief["gap"]["must_cover_headings"] = ["Tamamen kapsanmamış benzersiz konu"]
    html = "<article><h2>İlgisiz başlık</h2><p>" + BODY + "</p></article>"
    g = _gate(qg.run_all(html, brief), "gap")
    assert g["status"] == "RED"
    assert "Tamamen kapsanmamış benzersiz konu" in g["missing"]


def test_gap_pass_when_all_categories_covered():
    brief = _brief()
    brief["gap"] = {
        "must_cover_headings": ["İyileşme süreci"],
        "must_answer_questions": ["implant sonrası iyileşme süresi ne kadar"],
        "must_mention_entities": ["titanyum"],
    }
    res = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), brief)
    assert _gate(res, "gap")["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate 2 — Structure (count vs ceiling+1, and >200-word H2 needs >=2 H3)
# ---------------------------------------------------------------------------

def test_structure_red_below_ceiling_plus_one():
    # ceiling tables+lists = 2 → required 3 meaningful structures; supply only 1.
    html = (
        "<article><h2>Bölüm</h2><p>" + BODY + "</p>"
        "<ul><li>bir</li><li>iki</li></ul></article>"
    )
    g = _gate(qg.run_all(html, _brief()), "structure")
    assert g["status"] == "RED"


def test_structure_long_h2_requires_two_h3():
    brief = _brief()
    brief["structure_ceiling"] = {"tables": 0, "lists": 0, "h2": 1}
    long_body = "kelime " * 220  # > 200 words
    html = (
        "<article><h2>Uzun bölüm</h2><p>" + long_body + "</p>"
        "<ul><li>bir</li><li>iki</li></ul></article>"
    )
    g = _gate(qg.run_all(html, brief), "structure")
    assert g["status"] == "RED"
    assert "H3" in g["detail"]


# ---------------------------------------------------------------------------
# Gate 3 — Depth
# ---------------------------------------------------------------------------

def test_depth_red_on_shallow_h2():
    html = "<article><h2>Sığ bölüm</h2><p>Çok kısa.</p></article>"
    g = _gate(qg.run_all(html, _brief()), "depth")
    assert g["status"] == "RED"
    assert g["missing"]


def test_depth_pass_on_substantial_h2():
    html = "<article><h2>Dolu bölüm</h2><p>" + BODY + "</p></article>"
    g = _gate(qg.run_all(html, _brief()), "depth")
    assert g["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate 4 — AEO
# ---------------------------------------------------------------------------

def test_aeo_red_when_intro_not_answer_first():
    html = "<article><p>Bu yazıda her şeyi merak edenler için topladık.</p></article>"
    g = _gate(qg.run_all(html, _brief()), "aeo")
    assert g["status"] == "RED"


def test_aeo_red_when_answer_point_missing():
    brief = _brief()
    brief["aio"] = {
        "present": True,
        "answer_points": ["kuantum bilgisayar fiyat performans karşılaştırması"],
        "cited_sources": [],
    }
    res = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), brief)
    assert _gate(res, "aeo")["status"] == "RED"


def test_aeo_relaxes_when_aio_absent():
    brief = _brief()
    brief["aio"] = {"present": False, "answer_points": ["alakasız xyzzy noktası"], "cited_sources": []}
    res = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), brief)
    # AIO yok → yalnız intro şartı; iyi intro → PASS
    assert _gate(res, "aeo")["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate 5 — Voice (AI-signature blocklist density + cliché opening)
# ---------------------------------------------------------------------------

def test_voice_red_on_ai_signature_density():
    html = (
        "<article><p>Diş implantı tedavisi kalıcı bir çözümdür.</p>"
        "<h2>Bölüm</h2><p>Aslında bu doğru. Sonuç olarak böyle. Özetle budur. Bilindiği gibi öyle.</p></article>"
    )
    g = _gate(qg.run_all(html, _brief()), "voice")
    assert g["status"] == "RED"


def test_voice_pass_when_clean():
    res = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), _brief())
    assert _gate(res, "voice")["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate 6 — Originality
# ---------------------------------------------------------------------------

def test_originality_red_without_original_block():
    html = "<article><h2>Bölüm</h2><p>" + BODY + "</p></article>"
    g = _gate(qg.run_all(html, _brief()), "originality")
    assert g["status"] == "RED"


def test_originality_pass_with_data_original_novelty():
    html = (
        '<article><div data-original="true"><p>Kendi kohort analizimiz '
        "benzersiz bir bulgu ortaya koydu.</p></div></article>"
    )
    g = _gate(qg.run_all(html, _brief()), "originality")
    assert g["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate 7 — Schema / Visual
# ---------------------------------------------------------------------------

def test_schema_visual_red_without_jsonld():
    html = '<article><img src="/h.jpg" alt="x"><h2>Bölüm</h2><p>' + BODY + "</p></article>"
    g = _gate(qg.run_all(html, _brief()), "schema_visual")
    assert g["status"] == "RED"


def test_schema_visual_red_on_invalid_jsonld():
    html = (
        '<article><img src="/h.jpg" alt="x">'
        '<script type="application/ld+json">{bozuk json,,}</script></article>'
    )
    g = _gate(qg.run_all(html, _brief()), "schema_visual")
    assert g["status"] == "RED"


def test_schema_visual_pass_with_jsonld_and_hero():
    res = qg.run_all((FIX / "good_article.html").read_text(encoding="utf-8"), _brief())
    assert _gate(res, "schema_visual")["status"] == "PASS"


# ---------------------------------------------------------------------------
# Robustness — malformed brief must not crash
# ---------------------------------------------------------------------------

def test_run_all_tolerates_minimal_brief():
    res = qg.run_all("<article><p>kısa</p></article>", {})
    assert res["overall"] in {"PASS", "RED"}
    assert len(res["gates"]) == 8
