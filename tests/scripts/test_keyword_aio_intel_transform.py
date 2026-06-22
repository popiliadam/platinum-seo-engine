"""Tests for scripts.production.keyword_aio_intel_transform (CCE batch B1).

Hermetic: inline DFS fixtures (keyword_overview / keyword_suggestions /
serp_organic_live_advanced). Proves the dual-shape tolerance is inherited from
scripts.ingestion.dfs_pull._normalize_dfs_response and pins the keyword_set +
aio contract that build_brief (and downstream B2/B4) depend on.
"""

from __future__ import annotations

import pytest

from scripts.production import keyword_aio_intel_transform as ka


# --- fixture builders (REST envelope shape) --------------------------------

def _overview(items: list) -> dict:
    return {"tasks": [{"result": [{"items": items}]}]}


def _suggestions(items: list) -> dict:
    return {"tasks": [{"result": [{"items": items}]}]}


def _serp(items: list) -> dict:
    return {"tasks": [{"result": [{"items": items}]}]}


# ---------------------------------------------------------------------------
# keyword_set
# ---------------------------------------------------------------------------

def test_keyword_set_from_suggestions():
    sugg = _suggestions([
        {"keyword": "implant fiyat", "keyword_info": {"search_volume": 50}},
        {"keyword": "implant marka", "keyword_info": {"search_volume": 30}},
    ])
    out = ka.transform(None, sugg, None, market="TR")
    ks = out["keyword_set"]
    assert {e["kw"] for e in ks} == {"implant fiyat", "implant marka"}
    assert all(e["source"] == "dfs_suggestions" for e in ks)
    e0 = next(e for e in ks if e["kw"] == "implant fiyat")
    assert e0["volume"] == 50
    assert e0["intent"] == "Informational"  # default when no intent data


def test_overview_enriches_volume_and_intent():
    sugg = _suggestions([
        {"keyword": "implant fiyat", "keyword_info": {"search_volume": 50}},
    ])
    ov = _overview([
        {"keyword": "implant fiyat", "keyword_info": {"search_volume": 999},
         "search_intent_info": {"main_intent": "commercial"}},
    ])
    out = ka.transform(ov, sugg, None, market="TR")
    e = out["keyword_set"][0]
    assert e["volume"] == 999          # overview volume wins
    assert e["intent"] == "Commercial"  # overview intent wins


def test_overview_only_keyword_is_included_after_suggestions():
    sugg = _suggestions([
        {"keyword": "implant fiyat", "keyword_info": {"search_volume": 50}},
    ])
    ov = _overview([
        {"keyword": "klima montaj", "keyword_info": {"search_volume": 120},
         "search_intent_info": {"main_intent": "transactional"}},
    ])
    out = ka.transform(ov, sugg, None, market="TR")
    kws = [e["kw"] for e in out["keyword_set"]]
    assert kws == ["implant fiyat", "klima montaj"]  # suggestions first
    e = next(e for e in out["keyword_set"] if e["kw"] == "klima montaj")
    assert e["volume"] == 120
    assert e["intent"] == "Transactional"


def test_keyword_set_deduped_case_insensitive_first_wins():
    sugg = _suggestions([
        {"keyword": "implant fiyat", "keyword_info": {"search_volume": 50}},
        {"keyword": "Implant Fiyat", "keyword_info": {"search_volume": 80}},
    ])
    out = ka.transform(None, sugg, None, market="TR")
    assert len(out["keyword_set"]) == 1
    assert out["keyword_set"][0]["kw"] == "implant fiyat"
    assert out["keyword_set"][0]["volume"] == 50  # first seen wins


def test_keyword_set_entry_key_order():
    sugg = _suggestions([{"keyword": "x", "keyword_info": {"search_volume": 1}}])
    out = ka.transform(None, sugg, None, market="TR")
    assert list(out["keyword_set"][0].keys()) == ["kw", "volume", "intent", "source"]


def test_dual_shape_flat_wrapper_tolerated():
    # Flat-wrapper shape (dataforseo-mcp flattening) must normalise identically
    # — proves _normalize_dfs_response is imported, not reimplemented.
    sugg_flat = {"items": [{"keyword": "implant fiyat", "keyword_info": {"search_volume": 50}}]}
    out = ka.transform(None, sugg_flat, None, market="TR")
    assert [e["kw"] for e in out["keyword_set"]] == ["implant fiyat"]


# ---------------------------------------------------------------------------
# AI Overview
# ---------------------------------------------------------------------------

def test_aio_present_extracts_answer_points_and_sources():
    serp = _serp([
        {"type": "organic", "url": "https://x.example/", "rank_group": 1},
        {"type": "ai_overview", "asynchronous_ai_overview": False,
         "items": [
             {"type": "ai_overview_element", "text": "İmplant tedavisi 3-6 ay sürer."},
             {"type": "ai_overview_element", "text": "Fiyat markaya göre değişir."},
         ],
         "references": [
             {"type": "ai_overview_reference", "url": "https://a.example/", "domain": "a.example"},
             {"type": "ai_overview_reference", "url": "https://b.example/", "domain": "b.example"},
         ]},
    ])
    out = ka.transform(None, None, serp, market="TR")
    aio = out["aio"]
    assert aio["present"] is True
    assert aio["answer_points"] == [
        "İmplant tedavisi 3-6 ay sürer.",
        "Fiyat markaya göre değişir.",
    ]
    assert aio["cited_sources"] == ["https://a.example/", "https://b.example/"]


def test_aio_absent_when_no_ai_overview_item():
    serp = _serp([{"type": "organic", "url": "https://x.example/", "rank_group": 1}])
    out = ka.transform(None, None, serp, market="TR")
    assert out["aio"] == {"present": False, "answer_points": [], "cited_sources": []}


def test_aio_dedupes_repeated_sources():
    serp = _serp([
        {"type": "ai_overview",
         "items": [{"type": "ai_overview_element", "text": "Tek nokta.",
                    "references": [{"url": "https://a.example/"}]}],
         "references": [
             {"url": "https://a.example/"},
             {"url": "https://a.example/"},
         ]},
    ])
    out = ka.transform(None, None, serp, market="TR")
    assert out["aio"]["cited_sources"] == ["https://a.example/"]


# ---------------------------------------------------------------------------
# Shape / edges / purity
# ---------------------------------------------------------------------------

def test_all_none_inputs_yield_empty_set_and_absent_aio():
    out = ka.transform(None, None, None, market="TR")
    assert out == {
        "keyword_set": [],
        "aio": {"present": False, "answer_points": [], "cited_sources": []},
    }


def test_output_top_level_keys():
    out = ka.transform(None, None, None, market="TR")
    assert set(out.keys()) == {"keyword_set", "aio"}
    assert set(out["aio"].keys()) == {"present", "answer_points", "cited_sources"}


def test_idempotent_same_input_same_output():
    sugg = _suggestions([{"keyword": "x", "keyword_info": {"search_volume": 1}}])
    serp = _serp([
        {"type": "ai_overview", "items": [{"text": "a"}], "references": [{"url": "u"}]},
    ])
    first = ka.transform(None, sugg, serp, market="TR")
    second = ka.transform(None, sugg, serp, market="TR")
    assert first == second


def test_empty_market_raises():
    with pytest.raises(ValueError):
        ka.transform(None, None, None, market="")
