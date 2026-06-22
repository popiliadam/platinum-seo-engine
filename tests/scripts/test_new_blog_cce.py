"""Tests for scripts/production/new_blog.py — CCE orchestrator helpers (B4).

new_blog.py is PURE Python (the load-bearing rule, spec §3): it never calls
MCP/Claude. It hands the silahlan→yaz→kapı loop two pure helpers —

  - assemble_brief(): raw MCP JSON → full Brief Paketi (calls the 3 B1 transforms).
  - evaluate(): gate the produced HTML via quality_gates.run_all (IMPORT, not
    subprocess) + decide the loop action (PASS / REWRITE / AMBER_TERMINAL with a
    3-round cap so the loop can never spin forever, spec §8).

These tests pin the interface B5 depends on verbatim, plus the wiring (the 3
transforms are actually called) and the purity contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.production import new_blog

FIX = Path(__file__).parent / "fixtures" / "cce"

EMPTY_SERP: dict = {"tasks": [{"result": [{"items": []}]}]}
TOPIC: dict = {
    "primary_keyword": "x",
    "content_type": "guide",
    "locale": "tr-TR",
    "market": "TR",
}


# ---------------------------------------------------------------------------
# assemble_brief — verbatim contract example (B5 depends on this)
# ---------------------------------------------------------------------------

def test_assemble_brief_overrides_gsc():
    brief = new_blog.assemble_brief(
        serp_json={"tasks": [{"result": [{"items": []}]}]}, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic={"primary_keyword": "x", "content_type": "guide",
               "locale": "tr-TR", "market": "TR"},
        gsc={"real_queries": ["q1"], "current_position": 12},
        generated_at="2026-06-22T00:00:00Z")
    assert brief["gsc"]["real_queries"] == ["q1"]
    assert brief["gsc"]["current_position"] == 12
    assert brief["schema_version"] == "1.0"


def test_assemble_brief_default_gsc_when_omitted():
    # gsc not supplied → build_brief's empty default flows through unchanged.
    brief = new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=TOPIC)
    assert brief["gsc"] == {"real_queries": [], "current_position": None}


def test_assemble_brief_passes_generated_at_through():
    brief = new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=TOPIC, generated_at="2026-06-22T10:00:00Z")
    assert brief["generated_at"] == "2026-06-22T10:00:00Z"


def test_assemble_brief_schema_order_preserved_after_gsc_override():
    # Overriding gsc must keep the schema key order (gsc stays in its slot).
    brief = new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=TOPIC, gsc={"real_queries": ["q"], "current_position": 1})
    assert list(brief.keys()) == [
        "schema_version", "topic", "keyword_set", "aio", "competitors",
        "gap", "structure_ceiling", "gsc", "generated_at",
    ]


def test_assemble_brief_wires_all_three_transforms():
    """assemble_brief must call competitor_recon + keyword_aio_intel +
    build_brief so the produced Brief reflects every raw input."""
    serp = {"tasks": [{"result": [{"items": [
        {"type": "organic", "url": "https://rakip.example/", "rank_group": 1},
    ]}]}]}
    scraped = [{
        "url": "https://rakip.example/",
        "html": "<h2>Fiyatlar</h2><h3>Bakım</h3><p>bir iki üç</p>",
    }]
    suggestions = {"tasks": [{"result": [{"items": [
        {"keyword": "diş implantı fiyatı", "keyword_info": {"search_volume": 880}},
    ]}]}]}
    serp_aio = {"tasks": [{"result": [{"items": [
        {"type": "ai_overview",
         "items": [{"text": "İmplant tedavisi 3 aşamada tamamlanır."}]},
    ]}]}]}
    brief = new_blog.assemble_brief(
        serp_json=serp, scraped_pages=scraped,
        raw_overview={}, raw_suggestions=suggestions, raw_serp=serp_aio,
        our_existing=None,
        topic={"primary_keyword": "diş implantı", "content_type": "guide",
               "locale": "tr-TR", "market": "TR"})
    # competitor_recon wired:
    assert brief["competitors"][0]["h2_h3"] == ["Fiyatlar", "Bakım"]
    # keyword_aio_intel wired (keyword_set + aio):
    assert any(k["kw"] == "diş implantı fiyatı" for k in brief["keyword_set"])
    assert brief["aio"]["present"] is True
    # build_brief wired (greenfield → competitor coverage becomes the gap):
    assert "Fiyatlar" in brief["gap"]["must_cover_headings"]


def test_assemble_brief_does_not_mutate_topic_input():
    topic = dict(TOPIC)
    new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=topic)
    assert topic == TOPIC  # immutability: caller's dict untouched


# ---------------------------------------------------------------------------
# evaluate — verbatim contract examples (B5 depends on these)
# ---------------------------------------------------------------------------

def test_evaluate_red_under_cap_is_rewrite():
    brief = new_blog.assemble_brief(
        serp_json={"tasks": [{"result": [{"items": []}]}]}, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic={"primary_keyword": "x", "content_type": "guide",
               "locale": "tr-TR", "market": "TR"})
    out = new_blog.evaluate(
        "<article><p>kısa</p></article>", brief, round_num=1, max_rounds=3)
    assert out["action"] in ("REWRITE", "PASS")
    assert "gate_result" in out


def test_evaluate_red_at_cap_is_amber_terminal():
    brief = new_blog.assemble_brief(
        serp_json={"tasks": [{"result": [{"items": []}]}]}, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic={"primary_keyword": "x", "content_type": "guide",
               "locale": "tr-TR", "market": "TR"})
    out = new_blog.evaluate(
        "<article><p>kısa</p></article>", brief, round_num=3, max_rounds=3)
    # boş içerik kesin RED → cap'te AMBER_TERMINAL
    assert out["action"] == "AMBER_TERMINAL"


# ---------------------------------------------------------------------------
# evaluate — return shape + branch semantics
# ---------------------------------------------------------------------------

def test_evaluate_return_shape():
    brief = new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=TOPIC)
    out = new_blog.evaluate("<article><p>kısa</p></article>", brief)
    assert set(out.keys()) == {"gate_result", "action", "feedback"}
    assert out["action"] in {"PASS", "REWRITE", "AMBER_TERMINAL"}
    assert isinstance(out["feedback"], list)
    assert set(out["gate_result"].keys()) == {"gates", "overall", "rewrite_feedback"}


def test_evaluate_pass_on_good_article():
    html = (FIX / "good_article.html").read_text(encoding="utf-8")
    brief = json.loads((FIX / "sample_brief.json").read_text(encoding="utf-8"))
    out = new_blog.evaluate(html, brief, round_num=1, max_rounds=3)
    assert out["action"] == "PASS", out["feedback"]
    assert out["feedback"] == []
    assert out["gate_result"]["overall"] == "PASS"


def test_evaluate_rewrite_feedback_is_gate_rewrite_feedback():
    brief = new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=TOPIC)
    out = new_blog.evaluate(
        "<article><p>kısa</p></article>", brief, round_num=1, max_rounds=3)
    assert out["action"] == "REWRITE"
    assert out["feedback"] == out["gate_result"]["rewrite_feedback"]
    assert out["feedback"]  # RED gates → non-empty feedback


def test_evaluate_amber_terminal_carries_feedback_for_operator():
    brief = new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=TOPIC)
    out = new_blog.evaluate(
        "<article><p>kısa</p></article>", brief, round_num=3, max_rounds=3)
    # AMBER_TERMINAL reports the residual gate failures to the operator.
    assert out["feedback"] == out["gate_result"]["rewrite_feedback"]
    assert out["feedback"]


def test_evaluate_round_above_cap_is_amber_terminal():
    # round_num > max_rounds is still terminal (>= cap), never an infinite loop.
    brief = new_blog.assemble_brief(
        serp_json=EMPTY_SERP, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic=TOPIC)
    out = new_blog.evaluate(
        "<article><p>kısa</p></article>", brief, round_num=5, max_rounds=3)
    assert out["action"] == "AMBER_TERMINAL"


# ---------------------------------------------------------------------------
# Purity contract (the load-bearing architecture rule)
# ---------------------------------------------------------------------------

def test_new_blog_is_pure_no_mcp_no_subprocess():
    """new_blog.py must be pure Python: no MCP call sites and run_all reached by
    import — never via subprocess (spec §3 load-bearing rule). Checks real
    USAGE (call sites / imports), not prose mentions in docstrings — mirroring
    the engine's own scripts/validation/skill_mcp_usage detector philosophy."""
    import re

    src = Path(new_blog.__file__).read_text(encoding="utf-8")
    # No MCP tool CALL SITE (qualified mcp__server__tool(...)); prose is fine.
    assert not re.search(r"mcp__[a-zA-Z0-9_]+__[a-zA-Z0-9_]+\s*\(", src), (
        "new_blog must not call MCP tools (pure Python)"
    )
    # run_all reached by import — never a subprocess spawn.
    assert "import subprocess" not in src, "no subprocess import (run_all via import)"
    assert not re.search(r"\bsubprocess\.", src), (
        "no subprocess.* call (evaluate must call run_all via import)"
    )
