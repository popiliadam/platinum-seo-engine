#!/usr/bin/env python3
"""
new_blog.py — CCE (Competitive Content Engine) orchestrator helpers (batch B4).

THE LOAD-BEARING RULE (spec §3):
    This module is PURE Python. It NEVER calls MCP or Claude. The orchestrator
    is "both code AND Claude": the silahlan → yaz → kapı → re-write LOOP is
    driven by Claude inside skills/production/new-blog/SKILL.md, which calls the
    DataForSEO / Scrapling / GSC MCP tools, writes the raw JSON to disk, asks
    Claude to write the article, and re-writes on gate feedback. This module
    gives that loop the two PURE helpers it cannot express in a skill:

      1. assemble_brief() — stitch the raw MCP JSON into the full Brief Paketi
         by calling the three B1 transforms in order.
      2. evaluate()       — gate the produced HTML against the Brief (B2's
         quality_gates.run_all, reached by IMPORT — not subprocess) and return
         the loop's next action (PASS / REWRITE / AMBER_TERMINAL).

    Putting an MCP/Claude call in this file would break the architecture: the
    skill owns the MCP boundary, this module owns the deterministic glue.

Purity discipline (mirrors the B1 transforms):
    - No MCP, no network, no Claude. Raw JSON arrives as parameters.
    - No mutation of caller inputs; idempotent.
    - run_all reached by import, not subprocess (a function call, not a process).

Refs: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md
(§3 mimari, §6 kapılar, §8 döngü), docs/superpowers/plans/2026-06-22-
competitive-content-engine.md (Brief Paketi şeması — B1↔B2↔B4↔B5 contract).
"""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ is a namespace package; ensure repo root on sys.path so the absolute
# sibling imports below resolve regardless of how this module is loaded.
# ScriptDir = scripts/production → repo_root = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The B1 arming transforms + the B2 gate engine — all pure-Python siblings.
# IMPORT (not subprocess): evaluate() calls run_all in-process.
from scripts.production import build_brief  # noqa: E402
from scripts.production import competitor_recon_transform  # noqa: E402
from scripts.production import keyword_aio_intel_transform  # noqa: E402
from scripts.production import quality_gates  # noqa: E402


# ---------------------------------------------------------------------------
# Brief assembly (silahlan → Brief Paketi)
# ---------------------------------------------------------------------------

def assemble_brief(
    *,
    serp_json: dict,
    scraped_pages: list[dict],
    raw_overview: dict,
    raw_suggestions: dict,
    raw_serp: dict,
    our_existing: dict | None,
    topic: dict,
    gsc: dict | None = None,
    generated_at: str | None = None,
) -> dict:
    """Assemble the full Brief Paketi from raw MCP JSON by running the three B1
    transforms in order. PURE — calls no MCP; the skill (Claude) fetches the raw
    payloads and passes them in.

    Pipeline:
      1. competitor_recon_transform.transform(serp_json, scraped_pages,
         market=topic["market"]) → competitors[]
      2. keyword_aio_intel_transform.transform(raw_overview, raw_suggestions,
         raw_serp, market=topic["market"]) → {keyword_set, aio}
      3. build_brief.build(competitors, keyword_aio, our_existing, topic=topic,
         generated_at=generated_at) → the Brief Paketi

    Args:
        serp_json: raw DFS serp_organic_live_advanced (top-10 organic ordering).
        scraped_pages: [{"url": str, "html": str}, ...] — Scrapling DOM per
            competitor.
        raw_overview: raw DFS keyword_overview (volume + intent enrichment).
        raw_suggestions: raw DFS keyword_suggestions (primary keyword_set source).
        raw_serp: raw DFS serp_organic_live_advanced for the AI-Overview block.
        our_existing: {"headings", "questions", "entities"} of our current
            content, or None (greenfield → all competitor coverage is gap).
        topic: {primary_keyword, content_type, locale, market}.
        gsc: optional {"real_queries", "current_position"} the skill pulled from
            GSC / master.xlsx. When given, OVERRIDES build_brief's empty default;
            when None, build_brief's {real_queries: [], current_position: None}
            default stays.
        generated_at: ISO-8601 timestamp, injected for idempotency (or None).

    Returns:
        The full Brief Paketi dict (schema_version "1.0"), keys in schema order.
    """
    market = topic["market"]

    competitors = competitor_recon_transform.transform(
        serp_json, scraped_pages, market=market
    )
    keyword_aio = keyword_aio_intel_transform.transform(
        raw_overview, raw_suggestions, raw_serp, market=market
    )
    brief = build_brief.build(
        competitors, keyword_aio, our_existing,
        topic=topic, generated_at=generated_at,
    )

    if gsc is not None:
        # Override the empty default build_brief emits. Build a NEW dict (no
        # mutation); re-assigning an existing key keeps its schema slot/order.
        brief = {**brief, "gsc": gsc}
    return brief


# ---------------------------------------------------------------------------
# Gate + loop decision (kapı → PASS | REWRITE | AMBER_TERMINAL)
# ---------------------------------------------------------------------------

def evaluate(
    content_html: str,
    brief: dict,
    *,
    round_num: int = 1,
    max_rounds: int = 3,
) -> dict:
    """Gate the produced article against the Brief and decide the loop's action.

    Runs quality_gates.run_all (IMPORT — not subprocess) and maps its overall
    verdict to the orchestrator's next move:

      - overall == "PASS"                            → "PASS"  (ship it)
      - overall == "RED" and round_num < max_rounds  → "REWRITE" (feed
        rewrite_feedback back to Claude and write again)
      - overall == "RED" and round_num >= max_rounds → "AMBER_TERMINAL"
        (the 3-round cap, spec §8 — never an infinite loop; the residual gate
        failures are carried back to the operator as the "missing" report)

    AMBER lives ONLY here, in the orchestrator. The gates themselves stay binary
    PASS/RED; AMBER_TERMINAL is the loop giving up after the cap.

    Args:
        content_html: the article HTML Claude just wrote.
        brief: the Brief Paketi from assemble_brief (or any gate-compatible dict).
        round_num: 1-based current re-write round.
        max_rounds: cap on re-write rounds (default 3, spec §8).

    Returns:
        {"gate_result": <run_all output>, "action": str, "feedback": [str]}.
    """
    gate_result = quality_gates.run_all(content_html, brief)

    if gate_result["overall"] == "PASS":
        return {"gate_result": gate_result, "action": "PASS", "feedback": []}

    # overall == "RED" → re-write while rounds remain, else terminal AMBER.
    # Copy the feedback list (no aliasing of run_all's internal list).
    feedback = list(gate_result.get("rewrite_feedback", []))
    action = "REWRITE" if round_num < max_rounds else "AMBER_TERMINAL"
    return {"gate_result": gate_result, "action": action, "feedback": feedback}


__all__ = (
    "assemble_brief",
    "evaluate",
)
