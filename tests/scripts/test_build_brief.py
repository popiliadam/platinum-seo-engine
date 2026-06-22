"""Tests for scripts.production.build_brief (CCE batch B1).

build_brief assembles the competitor inventory + keyword/AIO intel + our
existing coverage into the Brief Paketi — the single source of truth the
writer (B4) and the quality gates (B2) consume. These tests pin the gap math
(competitor − ours), the structure ceiling (max), and the exact schema shape.
"""

from __future__ import annotations

import pytest

from scripts.production import build_brief

TOPIC = {
    "primary_keyword": "implant tedavisi",
    "content_type": "guide",
    "locale": "tr-TR",
    "market": "TR",
}
EMPTY_KA = {
    "keyword_set": [],
    "aio": {"present": False, "answer_points": [], "cited_sources": []},
}


def _competitor(**over) -> dict:
    base = {
        "url": "u",
        "h2_h3": [],
        "questions": [],
        "entities": [],
        "tables": 0,
        "lists": 0,
        "word_count": 0,
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# Gap = competitor coverage − ours (the load-bearing contract)
# ---------------------------------------------------------------------------

def test_gap_is_competitor_minus_ours():
    comps = [{
        "url": "u", "h2_h3": ["A", "B"], "questions": ["Q1?"], "entities": ["E1"],
        "tables": 2, "lists": 1, "word_count": 900,
    }]
    brief = build_brief.build(
        comps, EMPTY_KA, {"headings": ["A"], "questions": [], "entities": []},
        topic=TOPIC,
    )
    assert "B" in brief["gap"]["must_cover_headings"]       # rakipte var, bizde yok
    assert "A" not in brief["gap"]["must_cover_headings"]   # bizde var → gap değil
    assert brief["structure_ceiling"]["tables"] == 2
    assert brief["schema_version"] == "1.0"


def test_gap_is_all_coverage_when_our_existing_none():
    comps = [_competitor(h2_h3=["A", "B"], questions=["Q1?"], entities=["E1"])]
    brief = build_brief.build(comps, EMPTY_KA, None, topic=TOPIC)
    assert brief["gap"]["must_cover_headings"] == ["A", "B"]
    assert brief["gap"]["must_answer_questions"] == ["Q1?"]
    assert brief["gap"]["must_mention_entities"] == ["E1"]


def test_gap_subtraction_is_case_insensitive():
    comps = [_competitor(h2_h3=["Fiyat", "Garanti"])]
    brief = build_brief.build(
        comps, EMPTY_KA, {"headings": ["fiyat"], "questions": [], "entities": []},
        topic=TOPIC,
    )
    assert brief["gap"]["must_cover_headings"] == ["Garanti"]  # "fiyat"≈"Fiyat" removed


def test_gap_union_dedupes_across_competitors():
    comps = [
        _competitor(h2_h3=["Fiyat", "Süreç"]),
        _competitor(h2_h3=["fiyat", "Bakım"]),  # "fiyat" dup (CI)
    ]
    brief = build_brief.build(comps, EMPTY_KA, None, topic=TOPIC)
    assert brief["gap"]["must_cover_headings"] == ["Fiyat", "Süreç", "Bakım"]


# ---------------------------------------------------------------------------
# Structure ceiling = max over competitors
# ---------------------------------------------------------------------------

def test_structure_ceiling_is_max_over_competitors():
    comps = [
        _competitor(tables=1, lists=4, word_count=800, h2_h3=["A"]),
        _competitor(tables=3, lists=2, word_count=1200, h2_h3=["A", "B", "C"]),
    ]
    brief = build_brief.build(comps, EMPTY_KA, None, topic=TOPIC)
    sc = brief["structure_ceiling"]
    assert sc["tables"] == 3
    assert sc["lists"] == 4
    assert sc["best_competitor_word_count"] == 1200


def test_structure_ceiling_h2_is_max_heading_count():
    # The competitor record flattens h2+h3 into one list (semantic split is
    # deferred to B4), so "h2" ceiling = max heading count.
    comps = [
        _competitor(h2_h3=["A", "B"]),
        _competitor(h2_h3=["A", "B", "C", "D"]),
    ]
    brief = build_brief.build(comps, EMPTY_KA, None, topic=TOPIC)
    assert brief["structure_ceiling"]["h2"] == 4


def test_structure_ceiling_zero_when_no_competitors():
    brief = build_brief.build([], EMPTY_KA, None, topic=TOPIC)
    assert brief["structure_ceiling"] == {
        "tables": 0, "lists": 0, "h2": 0, "best_competitor_word_count": 0,
    }


# ---------------------------------------------------------------------------
# Passthrough + topic validation
# ---------------------------------------------------------------------------

def test_keyword_set_and_aio_passthrough():
    ka = {
        "keyword_set": [{"kw": "implant fiyat", "volume": 50, "intent": "Commercial",
                         "source": "dfs_suggestions"}],
        "aio": {"present": True, "answer_points": ["3-6 ay"], "cited_sources": ["https://a.example/"]},
    }
    brief = build_brief.build([], ka, None, topic=TOPIC)
    assert brief["keyword_set"] == ka["keyword_set"]
    assert brief["aio"] == ka["aio"]


def test_topic_passthrough_exact_keys():
    brief = build_brief.build([], EMPTY_KA, None, topic=TOPIC)
    assert brief["topic"] == TOPIC


def test_invalid_content_type_raises():
    bad = dict(TOPIC, content_type="blogpost")
    with pytest.raises(ValueError):
        build_brief.build([], EMPTY_KA, None, topic=bad)


def test_missing_topic_key_raises():
    bad = {"primary_keyword": "x", "content_type": "guide", "locale": "tr-TR"}  # no market
    with pytest.raises(ValueError):
        build_brief.build([], EMPTY_KA, None, topic=bad)


# ---------------------------------------------------------------------------
# Competitor projection (defensive shape)
# ---------------------------------------------------------------------------

def test_partial_competitor_is_projected_with_defaults():
    brief = build_brief.build([{"url": "u", "h2_h3": ["A"]}], EMPTY_KA, None, topic=TOPIC)
    comp = brief["competitors"][0]
    assert list(comp.keys()) == [
        "url", "h2_h3", "questions", "entities", "tables", "lists", "word_count",
    ]
    assert comp["tables"] == 0 and comp["questions"] == []


# ---------------------------------------------------------------------------
# generated_at injection (idempotency)
# ---------------------------------------------------------------------------

def test_generated_at_injected_when_provided():
    stamp = "2026-06-22T10:00:00+00:00"
    brief = build_brief.build([], EMPTY_KA, None, topic=TOPIC, generated_at=stamp)
    assert brief["generated_at"] == stamp


def test_generated_at_is_null_by_default():
    brief = build_brief.build([], EMPTY_KA, None, topic=TOPIC)
    assert brief["generated_at"] is None


# ---------------------------------------------------------------------------
# Schema shape + purity
# ---------------------------------------------------------------------------

def test_top_level_keys_in_schema_order():
    brief = build_brief.build([], EMPTY_KA, None, topic=TOPIC)
    assert list(brief.keys()) == [
        "schema_version",
        "topic",
        "keyword_set",
        "aio",
        "competitors",
        "gap",
        "structure_ceiling",
        "gsc",
        "generated_at",
    ]


def test_gsc_default_block_present():
    brief = build_brief.build([], EMPTY_KA, None, topic=TOPIC)
    assert brief["gsc"] == {"real_queries": [], "current_position": None}


def test_idempotent_same_input_and_arg():
    comps = [_competitor(h2_h3=["A", "B"], tables=2, word_count=900)]
    stamp = "2026-06-22T10:00:00+00:00"
    first = build_brief.build(comps, EMPTY_KA, None, topic=TOPIC, generated_at=stamp)
    second = build_brief.build(comps, EMPTY_KA, None, topic=TOPIC, generated_at=stamp)
    assert first == second
