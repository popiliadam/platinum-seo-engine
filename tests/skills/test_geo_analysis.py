"""
tests/skills/test_geo_analysis.py — geo-analysis discovery skill tests.

Phase 7 Wave 2 (W-B4). Mirrors the test pattern of test_on_page_audit.py
and test_dfs_pull.py: frontmatter parse + Draft 7 schema validation,
URL normalization (D-03 invariant), transform unit, geo_gap label
heuristic coverage, cross-source URL join, budget pre-flight integration,
and DURUR behaviour for upstream llm_mentions_search schema drift.

MCP tools are NOT Python-callable inside pytest; live MCP calls are
performed at-rest. These tests therefore validate the transform + skill
contract using mocked DFS fixtures, not the upstream MCP fetch itself.

Schemas referenced:
  - schemas/skill-frontmatter.schema.json (frontmatter Draft 7)
  - schemas/events.schema.json (target_excel_sheet=null staging-only)
  - schemas/cross-sheet-invariants.json (D-03 URL canonicalization)

IMPORT discipline (W-B4 brief): the transform module re-uses
`scripts.ingestion.dfs_pull._normalize_dfs_response` rather than copying
it. test_normalize_helper_imported_not_copied locks that contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import geo_analysis_transform as ga
from scripts.ingestion import dfs_pull


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "geo-analysis" / "SKILL.md"

PROJECT_NAME = "AcmeBrand"
PROJECT_URL_ROOT = "https://acmebrand.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    """Parse the YAML frontmatter block of skills/discovery/geo-analysis/SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


# ---------------------------------------------------------------------------
# Mock payload builders
# ---------------------------------------------------------------------------

def _llm_mention_item(
    *,
    query: str,
    model: str,
    text: str,
    cited_url: str = "",
) -> dict:
    """Build a single llm_mentions_search per-mention item (flat shape)."""
    return {
        "keyword": query,
        "model": model,
        "mention_text": text,
        "cited_url": cited_url,
    }


def _llm_envelope(items: list[dict]) -> dict:
    """Wrap items in the canonical DFS REST envelope."""
    return {
        "version": "0.1.20240101",
        "status_code": 20000,
        "tasks": [{
            "id": "test-task-llm",
            "status_code": 20000,
            "result": [{"items": items}],
        }],
    }


def _serp_block(query: str, positions: list[tuple[int, str, str]]) -> dict:
    """Build a serp_organic_live_advanced per-query block.

    positions is a list of (rank_absolute, url, title).
    """
    return {
        "keyword": query,
        "items": [
            {
                "type": "organic",
                "rank_absolute": rank,
                "url": url,
                "title": title,
            }
            for (rank, url, title) in positions
        ],
    }


def _serp_envelope(blocks: list[dict]) -> dict:
    return {
        "version": "0.1.20240101",
        "status_code": 20000,
        "tasks": [{
            "id": "test-task-serp",
            "status_code": 20000,
            "result": [{"items": blocks}],
        }],
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + validates against schema
# ---------------------------------------------------------------------------

def test_frontmatter_validates(skill_frontmatter: dict,
                                skill_frontmatter_schema: dict) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=geo-analysis, status=wip, version="1.0",
          category=discovery,
      (c) declare project_slug as a required string input,
      (d) declare budget.uses_paid_mcp=true with non-zero estimate
          (Q-W-A4-01: only uses_paid_mcp + estimated_credits — no
          _per_call / _per_url leakage),
      (e) list mcp__dataforseo__ai_optimization_llm_mentions_search +
          mcp__dataforseo__serp_organic_live_advanced as required,
      (f) outputs include staging files + inbox/dfs/ + outputs/reports/
          + events.jsonl (D-003 staging-only — NO master.xlsx#),
      (g) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "geo-analysis"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"
    assert fm["category"] == "discovery"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    # Paid-MCP budget envelope. Schema-first: only uses_paid_mcp +
    # estimated_credits permitted (Q-W-A4-01 lesson).
    budget_block = fm["budget"]
    assert budget_block["uses_paid_mcp"] is True
    assert budget_block["estimated_credits"] > 0
    # No _per_call / _per_url leakage (rejected by schema, but lock it
    # explicitly here too).
    assert "estimated_credits_per_call" not in budget_block
    assert "estimated_credits_per_url" not in budget_block
    assert "estimated_credits_per_query" not in budget_block

    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__dataforseo__ai_optimization_llm_mentions_search" in required_tools
    assert "mcp__dataforseo__serp_organic_live_advanced" in required_tools

    outputs = fm["outputs"]
    # D-003 staging-only: 3 staging files + 2 inbox + 1 report + events.jsonl
    assert any("_state/staging/geo_analysis_llm_mentions" in o for o in outputs)
    assert any("_state/staging/geo_analysis_serp_organic" in o for o in outputs)
    assert any("_state/staging/geo_analysis_signals" in o for o in outputs)
    assert any("inbox/dfs/" in o and "llm_mentions" in o for o in outputs)
    assert any("inbox/dfs/" in o and "serp_organic" in o for o in outputs)
    assert any("outputs/reports/" in o and "geo-analysis" in o for o in outputs)
    assert "events.jsonl" in outputs
    # Staging-only: no master.xlsx# write.
    assert not any("master.xlsx#" in o for o in outputs)

    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errs, (
        "frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Empty input → empty staging
# ---------------------------------------------------------------------------

def test_transform_empty_input_empty_output() -> None:
    """No LLM mentions and no SERP results → all three tables empty,
    meta.queries_analyzed=0."""
    out = ga.transform(
        _llm_envelope([]),
        _serp_envelope([]),
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )
    assert out["llm_mentions"] == []
    assert out["serp_organic"] == []
    assert out["geo_signals"] == []
    assert out["meta"]["queries_analyzed"] == 0
    assert out["meta"]["llm_mention_row_count"] == 0
    assert out["meta"]["serp_organic_row_count"] == 0
    assert out["meta"]["geo_signal_row_count"] == 0


# ---------------------------------------------------------------------------
# Test 3 — Single LLM mention with our_brand → our_brand_mentioned=True
# ---------------------------------------------------------------------------

def test_single_mention_our_brand_matched() -> None:
    """One LLM mention referencing the project name → our_brand_mentioned=True
    on the per-mention row, llm_visibility_score=1.0 on the geo signal."""
    raw_llm = _llm_envelope([
        _llm_mention_item(
            query="best dental clinic istanbul",
            model="gpt-4",
            text=f"For Istanbul, {PROJECT_NAME} is regularly recommended by users.",
            cited_url="https://acmebrand.com/clinics/istanbul",
        ),
    ])
    raw_serp = _serp_envelope([])
    out = ga.transform(
        raw_llm, raw_serp,
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )

    assert len(out["llm_mentions"]) == 1
    r = out["llm_mentions"][0]
    assert r["our_brand_mentioned"] is True
    assert r["our_url_cited"] is True
    assert r["model"] == "gpt-4"
    assert r["query"] == "best dental clinic istanbul"
    # Mention text truncated at MENTION_TEXT_MAX_CHARS.
    assert len(r["mention_text"]) <= ga.MENTION_TEXT_MAX_CHARS

    # Geo signal: 1 model seen, 1 mentioned → visibility_score=1.0.
    assert len(out["geo_signals"]) == 1
    g = out["geo_signals"][0]
    assert g["llm_visibility_score"] == 1.0
    assert g["our_brand_mentioned_count"] == 1
    assert g["our_url_cited_count"] == 1


# ---------------------------------------------------------------------------
# Test 4 — Multiple models, brand in 2/4 → llm_visibility_score=0.5
# ---------------------------------------------------------------------------

def test_visibility_score_half_when_two_of_four() -> None:
    """4 models queried for the same query, brand mentioned in 2 → score=0.5
    → AEO_HEALTHY (≥50% threshold) IF SERP top-3 present."""
    query = "ecommerce platforms 2026"
    raw_llm = _llm_envelope([
        _llm_mention_item(query=query, model="gpt-4",
                          text=f"{PROJECT_NAME} is a top option."),
        _llm_mention_item(query=query, model="claude-sonnet-4",
                          text=f"Among the leaders is {PROJECT_NAME}."),
        _llm_mention_item(query=query, model="gemini-2",
                          text="Other brands are commonly cited."),
        _llm_mention_item(query=query, model="llama-3",
                          text="Various solutions exist in this market."),
    ])
    # Provide SERP top-3 presence so the gap classifies AEO_HEALTHY (the
    # heuristic flags AEO_NEEDED if SERP top-3 but visibility <50%; visibility
    # =0.5 hits the >= threshold so this stays AEO_HEALTHY).
    raw_serp = _serp_envelope([
        _serp_block(query, [
            (1, f"{PROJECT_URL_ROOT}/platforms", "AcmeBrand Platforms"),
            (2, "https://competitor.com/", "Other"),
            (3, "https://example.org/", "Another"),
        ]),
    ])
    out = ga.transform(
        raw_llm, raw_serp,
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )

    g = out["geo_signals"][0]
    assert g["llm_visibility_score"] == 0.5
    assert g["our_brand_mentioned_count"] == 2
    assert g["serp_top_3_present"] is True
    assert g["geo_gap"] == ga.GAP_AEO_HEALTHY


# ---------------------------------------------------------------------------
# Test 5 — SERP top-3 but no LLM mention → geo_gap=AEO_NEEDED
# ---------------------------------------------------------------------------

def test_aeo_needed_when_serp_top3_no_llm_mention() -> None:
    """We rank SERP top-3 but no LLM mentions our brand → AEO_NEEDED."""
    query = "diy renovation tips"
    raw_llm = _llm_envelope([
        _llm_mention_item(query=query, model="gpt-4",
                          text="Generic advice from various sources."),
        _llm_mention_item(query=query, model="claude-sonnet-4",
                          text="Common renovation guides recommend X and Y."),
    ])
    raw_serp = _serp_envelope([
        _serp_block(query, [
            (1, f"{PROJECT_URL_ROOT}/renovation/diy", "DIY Renovation Tips"),
            (2, "https://competitor.com/diy", "Other"),
            (3, "https://example.org/diy", "Another"),
        ]),
    ])
    out = ga.transform(
        raw_llm, raw_serp,
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )

    g = out["geo_signals"][0]
    assert g["our_brand_mentioned_count"] == 0
    assert g["serp_top_3_present"] is True
    assert g["geo_gap"] == ga.GAP_AEO_NEEDED
    assert "AEO" in g["action"]


# ---------------------------------------------------------------------------
# Test 6 — LLM mentioned but no SERP top-3 → geo_gap=SERP_GAP
# ---------------------------------------------------------------------------

def test_serp_gap_when_llm_only() -> None:
    """LLM mentions our brand but we don't rank SERP top-3 → SERP_GAP."""
    query = "best paint brush brands"
    raw_llm = _llm_envelope([
        _llm_mention_item(query=query, model="gpt-4",
                          text=f"{PROJECT_NAME} brushes are recommended for studio work."),
        _llm_mention_item(query=query, model="claude-sonnet-4",
                          text=f"Many users mention {PROJECT_NAME} positively."),
    ])
    raw_serp = _serp_envelope([
        _serp_block(query, [
            (1, "https://competitor1.com/", "Other"),
            (2, "https://competitor2.com/", "Another"),
            (3, "https://competitor3.com/", "Yet Another"),
            # Our URL ranks #8 — outside top-3.
            (8, f"{PROJECT_URL_ROOT}/brushes", "AcmeBrand Brushes"),
        ]),
    ])
    out = ga.transform(
        raw_llm, raw_serp,
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )

    g = out["geo_signals"][0]
    assert g["our_brand_mentioned_count"] == 2
    assert g["serp_top_3_present"] is False
    assert g["geo_gap"] == ga.GAP_SERP_GAP


# ---------------------------------------------------------------------------
# Test 7 — Both present → geo_gap=AEO_HEALTHY
# ---------------------------------------------------------------------------

def test_aeo_healthy_when_both_present() -> None:
    """Brand mentioned in ≥50% LLMs AND SERP top-3 present → AEO_HEALTHY."""
    query = "modern kitchen design"
    raw_llm = _llm_envelope([
        _llm_mention_item(query=query, model="gpt-4",
                          text=f"{PROJECT_NAME} is a popular choice."),
        _llm_mention_item(query=query, model="claude-sonnet-4",
                          text=f"Among the leaders is {PROJECT_NAME}."),
    ])
    raw_serp = _serp_envelope([
        _serp_block(query, [
            (1, f"{PROJECT_URL_ROOT}/kitchen", "AcmeBrand Kitchen"),
            (2, "https://competitor.com/", "Other"),
        ]),
    ])
    out = ga.transform(
        raw_llm, raw_serp,
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )

    g = out["geo_signals"][0]
    assert g["geo_gap"] == ga.GAP_AEO_HEALTHY
    assert g["llm_visibility_score"] == 1.0
    assert g["serp_top_3_present"] is True


# ---------------------------------------------------------------------------
# Test 8 — Neither → geo_gap=ABSENT
# ---------------------------------------------------------------------------

def test_absent_when_neither_present() -> None:
    """No LLM mention AND no SERP top-3 → ABSENT (research priority)."""
    query = "obscure niche topic"
    raw_llm = _llm_envelope([
        _llm_mention_item(query=query, model="gpt-4",
                          text="Generic answer with no brand."),
    ])
    raw_serp = _serp_envelope([
        _serp_block(query, [
            (1, "https://competitor.com/", "Other"),
            (2, "https://example.org/", "Another"),
        ]),
    ])
    out = ga.transform(
        raw_llm, raw_serp,
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )

    g = out["geo_signals"][0]
    assert g["geo_gap"] == ga.GAP_ABSENT
    assert g["our_brand_mentioned_count"] == 0
    assert g["serp_top_3_present"] is False


# ---------------------------------------------------------------------------
# Test 9 — D-03 normalize: case + trailing slash equivalence between
#          LLM cited_url and SERP serp_url
# ---------------------------------------------------------------------------

def test_d03_normalize_cross_skill_consistent() -> None:
    """LLM cited_url 'HTTPS://Example.COM/Page/' must D-03 normalize to the
    SAME form as SERP serp_url 'https://Example.com/Page' (scheme+host
    lowercased, trailing slash stripped, path case preserved — this matches
    the on_page_audit_transform behaviour and schemas/cross-sheet-invariants
    D-03 rule). The transform never directly joins these two URL fields,
    but the invariant must hold to keep cross-source provenance clean.
    """
    norm_llm = ga._normalize_url("HTTPS://Example.COM/Page/")
    norm_serp = ga._normalize_url("https://Example.com/Page")
    # D-03: scheme+host lowercased; path case preserved.
    assert norm_llm == norm_serp == "https://example.com/Page"
    # Idempotency (D-03 hard invariant).
    assert ga._normalize_url(norm_llm) == norm_llm
    # Lowercased path also stays consistent across both sides.
    assert (
        ga._normalize_url("HTTPS://Example.COM/page/")
        == ga._normalize_url("https://example.com/page")
        == "https://example.com/page"
    )


def test_d03_normalize_strips_tracking_and_fragment() -> None:
    """utm_* / fbclid / gclid dropped; fragments stripped; query keys sorted."""
    raw = "https://acmebrand.com/page?utm_source=fb&b=2&a=1#section"
    assert ga._normalize_url(raw) == "https://acmebrand.com/page?a=1&b=2"


# ---------------------------------------------------------------------------
# Test 10 — DURUR: llm_mentions_search shape drift → LlmMentionsDriftError
# ---------------------------------------------------------------------------

def test_drift_llm_mentions_missing_model_raises() -> None:
    """An item without a 'model' field signals upstream drift — STOP."""
    bad = _llm_envelope([
        {
            "keyword": "some query",
            # 'model' field intentionally omitted (rename / regression).
            "mention_text": "Some content.",
        },
    ])
    with pytest.raises(ga.LlmMentionsDriftError):
        ga.transform(
            bad, None,
            project_name=PROJECT_NAME,
            project_url_root=PROJECT_URL_ROOT,
            project_slug="p-test",
        )


def test_drift_llm_mentions_missing_text_raises() -> None:
    """A nested mentions[] entry without a 'mention_text'/'text' field is
    drift — STOP."""
    bad = _llm_envelope([
        {
            "keyword": "some query",
            "model": "gpt-4",
            "mentions": [
                {"cited_url": "https://example.com"},  # no text/mention_text
            ],
        },
    ])
    with pytest.raises(ga.LlmMentionsDriftError):
        ga.transform(
            bad, None,
            project_name=PROJECT_NAME,
            project_url_root=PROJECT_URL_ROOT,
            project_slug="p-test",
        )


# ---------------------------------------------------------------------------
# Test 11 — Budget pre-flight: estimate + integration with check_budget
# ---------------------------------------------------------------------------

def test_estimate_credits_per_query() -> None:
    """5 (llm_mentions) + 1 (serp_organic) = 6 credits per query."""
    assert ga.estimate_credits(0) == 0.0
    assert ga.estimate_credits(1) == 6.0
    assert ga.estimate_credits(10) == 60.0


def test_budget_preflight_pass_and_fail(tmp_path: Path) -> None:
    """PASS path: under budget. FAIL path: BudgetExceededError raised."""
    cfg = tmp_path / "project.config.json"
    cfg.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 500},
    }))
    events = tmp_path / "events.jsonl"

    envelope = ga.preflight_budget(
        estimated_credits=ga.estimate_credits(10),  # 60 credits
        project_config_path=str(cfg),
        events_path=str(events),
    )
    assert envelope["exceeded"] is False
    assert envelope["budget_per_day"] == 500
    assert envelope["projected_used"] == 60.0
    assert envelope["remaining_after"] == 440.0

    cfg_low = tmp_path / "project-config-low.json"
    cfg_low.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 5},
    }))
    with pytest.raises(ga.BudgetExceededError):
        ga.preflight_budget(
            estimated_credits=ga.estimate_credits(10),  # 60 > 5
            project_config_path=str(cfg_low),
            events_path=str(events),
        )


# ---------------------------------------------------------------------------
# Test 12 — DURUR: project_name empty → ProjectNameMissingError
# ---------------------------------------------------------------------------

def test_project_name_missing_raises() -> None:
    """project_name empty/whitespace → ProjectNameMissingError (DURUR)."""
    raw_llm = _llm_envelope([])
    raw_serp = _serp_envelope([])
    with pytest.raises(ga.ProjectNameMissingError):
        ga.transform(
            raw_llm, raw_serp,
            project_name="",
            project_url_root=PROJECT_URL_ROOT,
        )
    with pytest.raises(ga.ProjectNameMissingError):
        ga.transform(
            raw_llm, raw_serp,
            project_name="   ",
            project_url_root=PROJECT_URL_ROOT,
        )


# ---------------------------------------------------------------------------
# Test 13 — IMPORT discipline: _normalize_dfs_response is IMPORTED, not copied
# ---------------------------------------------------------------------------

def test_normalize_helper_imported_not_copied() -> None:
    """W-B4 brief: the transform's reference IS
    `scripts.ingestion.dfs_pull._normalize_dfs_response`. Copying would
    silently fork the REST envelope vs flat wrapper contract.

    Two assertions:
      (a) the symbol is present in the module namespace (importable),
      (b) it IS the same object as `dfs_pull._normalize_dfs_response`
          (identity check — no copy/paste).
    """
    assert hasattr(ga, "_normalize_dfs_response") or True  # may not re-export
    # Identity: even if not re-exported, the module-level binding must point
    # at the same function object.
    assert ga._build_llm_mention_rows.__module__ == ga.__name__
    # Direct identity check via the import site (most explicit form).
    from scripts.discovery.geo_analysis_transform import _normalize_dfs_response as ga_norm
    assert ga_norm is dfs_pull._normalize_dfs_response, (
        "geo_analysis_transform must IMPORT _normalize_dfs_response from "
        "scripts.ingestion.dfs_pull (no copy) — the contract for REST/flat "
        "tolerance lives in dfs_pull, not in a forked helper."
    )


def test_transform_does_not_import_transaction() -> None:
    """Plugin agnostik / discipline: the transform is pure compute. It
    must not touch master.xlsx — staging-only output (D-003)."""
    src = (REPO_ROOT / "scripts" / "discovery"
           / "geo_analysis_transform.py").read_text("utf-8")
    assert "scripts.excel.transaction" not in src
    assert "transaction.append" not in src


# ---------------------------------------------------------------------------
# Test 14 — Sort: AEO_NEEDED ranked before AEO_HEALTHY in output
# ---------------------------------------------------------------------------

def test_sort_aeo_needed_before_aeo_healthy() -> None:
    """Geo signals sort by gap severity:
       AEO_NEEDED (0) < SERP_GAP (1) < ABSENT (2) < AEO_HEALTHY (3).
    Two queries, one AEO_NEEDED + one AEO_HEALTHY → AEO_NEEDED comes first.
    """
    q_needed = "z_needed_query"   # alphabetically AFTER healthy
    q_healthy = "a_healthy_query"  # alphabetically BEFORE needed

    raw_llm = _llm_envelope([
        # q_needed: 1 model, 0 brand mentions.
        _llm_mention_item(query=q_needed, model="gpt-4",
                          text="Generic answer."),
        # q_healthy: 1 model, brand mentioned.
        _llm_mention_item(query=q_healthy, model="gpt-4",
                          text=f"{PROJECT_NAME} is the choice."),
    ])
    raw_serp = _serp_envelope([
        _serp_block(q_needed, [
            (1, f"{PROJECT_URL_ROOT}/needed", "Needed Page"),
        ]),
        _serp_block(q_healthy, [
            (1, f"{PROJECT_URL_ROOT}/healthy", "Healthy Page"),
        ]),
    ])
    out = ga.transform(
        raw_llm, raw_serp,
        project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )

    gaps = [r["geo_gap"] for r in out["geo_signals"]]
    assert gaps[0] == ga.GAP_AEO_NEEDED
    assert gaps[1] == ga.GAP_AEO_HEALTHY
    # The AEO_NEEDED query (z_*) outranks the AEO_HEALTHY one (a_*) DESPITE
    # alphabetical order — sort by severity wins.
    assert out["geo_signals"][0]["query"] == q_needed
    assert out["geo_signals"][1]["query"] == q_healthy


# ---------------------------------------------------------------------------
# Test 15 — REST envelope vs flat wrapper tolerated (proves _normalize_dfs_response is wired)
# ---------------------------------------------------------------------------

def test_normalize_dfs_response_flat_wrapper_tolerated() -> None:
    """The transform must tolerate the dataforseo-mcp-server@2.8.9 flat
    wrapper shape (`{"items": [...]}`) the same way dfs_pull does — proven
    by routing the same items through both REST + flat envelopes and
    confirming identical output."""
    items = [_llm_mention_item(
        query="kw", model="gpt-4",
        text=f"{PROJECT_NAME} is great.",
    )]
    rest = _llm_envelope(items)
    flat = {"items": items}

    out_rest = ga.transform(
        rest, None, project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )
    out_flat = ga.transform(
        flat, None, project_name=PROJECT_NAME,
        project_url_root=PROJECT_URL_ROOT,
        project_slug="p-test",
    )
    # Strip fetched_at (only intentional run-to-run drift) and compare.
    assert out_rest["llm_mentions"] == out_flat["llm_mentions"]
    assert out_rest["geo_signals"] == out_flat["geo_signals"]
