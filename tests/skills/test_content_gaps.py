"""
tests/skills/test_content_gaps.py — content-gaps discovery skill tests.

Phase 7 Wave 2 (W-B1, paid-MCP DFS HEAVY discovery). The transform
follows the dfs-pull staging-only routing pattern (D-003): no
master.xlsx write — staging JSON only, Phase 8 cluster-map / new-
content-plan skill consumes downstream.

Schemas referenced:
  - schemas/skill-frontmatter.schema.json   (Draft7 frontmatter contract;
                                             budget block additionalProperties:false)
  - schemas/events.schema.json              (source.kind=dataforseo_mcp,
                                             target_excel_sheet=null)

Cross-module IMPORT-only discipline:
  - scripts.ingestion.dfs_pull              (_normalize_dfs_response +
                                             StagingSchemaError — IDENTITY
                                             preserved by import-discipline test)

NOTE: scripts.excel.transaction is intentionally NOT imported — staging-
only routing means content_gaps_transform does not produce Excel rows.
Cluster-map / new-content-plan (Phase 8) is the consumer that lifts
staging JSON into master.xlsx.

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_content_gaps.py -v
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from unittest import mock

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import content_gaps_transform as cgt
from scripts.ingestion import dfs_pull as _dfs_pull_module


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "content-gaps" / "SKILL.md"


# ---------------------------------------------------------------------------
# Fixtures — schemas
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    """Parse the YAML frontmatter block of the content-gaps SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


# ---------------------------------------------------------------------------
# Fixtures — mock DFS payloads (REST envelope + flat wrapper)
# ---------------------------------------------------------------------------

@pytest.fixture
def keyword_ideas_rest_envelope() -> dict:
    """REST envelope shape: tasks[0].result[0].items.

    Three candidates with varied volume + difficulty + competition so the
    gap_score sort order is non-trivial.
    """
    return {
        "tasks": [{
            "result": [{
                "location_code": 2792,
                "language_code": "tr",
                "items": [
                    {
                        "keyword": "kw-low-comp-high-vol",
                        "keyword_info": {
                            "search_volume": 12000,
                            "competition": 0.15,        # LOW-ish
                            "competition_level": "LOW",
                            "cpc": 0.95,
                        },
                        "keyword_properties": {
                            "keyword_difficulty": 12,
                        },
                    },
                    {
                        "keyword": "kw-high-comp-high-vol",
                        "keyword_info": {
                            "search_volume": 12000,
                            "competition": 0.92,
                            "competition_level": "HIGH",
                            "cpc": 3.40,
                        },
                        "keyword_properties": {
                            "keyword_difficulty": 75,
                        },
                    },
                    {
                        "keyword": "kw-mid",
                        "keyword_info": {
                            "search_volume": 4500,
                            "competition": 0.50,
                            "competition_level": "MEDIUM",
                            "cpc": 1.20,
                        },
                        "keyword_properties": {
                            "keyword_difficulty": 30,
                        },
                    },
                ],
            }],
        }],
    }


@pytest.fixture
def related_keywords_flat_wrapper() -> dict:
    """Flat wrapper shape: top-level items list (dataforseo-mcp-server@2.8.9
    flattening confirmed live). Items contain ``keyword_data`` envelope per
    related_keywords' own response shape.
    """
    return {
        "items": [
            {
                "keyword_data": {
                    "keyword": "related-kw-1",
                    "keyword_info": {
                        "search_volume": 800,
                        "competition": "LOW",
                        "cpc": 0.50,
                    },
                    "keyword_properties": {"keyword_difficulty": 8},
                },
                "depth": 1,
            },
            {
                "keyword_data": {
                    "keyword": "related-kw-2",
                    "keyword_info": {
                        "search_volume": 2200,
                        "competition": "MEDIUM",
                        "cpc": 1.10,
                    },
                    "keyword_properties": {"keyword_difficulty": 25},
                },
                "depth": 1,
            },
        ],
    }


@pytest.fixture
def empty_rest_envelope() -> dict:
    return {
        "tasks": [{"result": [{"items": []}]}],
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + validates against schema (Q-W-A4-01 lesson)
# ---------------------------------------------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=content-gaps, status=wip, version="1.0",
          category=discovery,
      (c) declare project_slug + seed_keyword as required string inputs,
      (d) list keyword_ideas + related_keywords in required tools,
      (e) carry budget {uses_paid_mcp: true, estimated_credits: N} ONLY
          (no _per_call / _per_url leakage — Q-W-A4-01),
      (f) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "content-gaps"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"
    assert fm["category"] == "discovery"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True
    assert "seed_keyword" in inputs
    assert inputs["seed_keyword"]["required"] is True

    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__dataforseo__dataforseo_labs_google_keyword_ideas" in required_tools
    assert "mcp__dataforseo__dataforseo_labs_google_related_keywords" in required_tools

    # Q-W-A4-01: budget block contains ONLY uses_paid_mcp + estimated_credits.
    budget = fm["budget"]
    assert budget["uses_paid_mcp"] is True
    assert isinstance(budget.get("estimated_credits"), (int, float))
    assert budget["estimated_credits"] > 0
    assert set(budget.keys()) <= {"uses_paid_mcp", "estimated_credits"}, (
        f"budget contains forbidden keys (additionalProperties:false); "
        f"got {sorted(budget.keys())}"
    )

    # Outputs include staging anchors + raw inbox + report. Staging-only
    # routing → no master.xlsx# anchor in outputs.
    outputs = fm["outputs"]
    assert any("_state/staging/" in o and "content_gaps" in o for o in outputs)
    assert any("inbox/dfs/" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("outputs/reports/" in o and "content-gaps" in o for o in outputs)

    # Full Draft 7 validation against the canonical schema.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(
        validator.iter_errors(fm), key=lambda e: list(e.absolute_path),
    )
    assert not errs, (
        "frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Empty response → empty staging rows (no error)
# ---------------------------------------------------------------------------

def test_empty_response_emits_empty_rows(empty_rest_envelope: dict) -> None:
    """Both required tools return empty items → NoCandidatesError DURUR
    (we refuse to silently emit empty staging when there are no
    candidates). Verifies the gate AND that an isolated empty payload
    on its own (with the OTHER tool absent) projects an empty staging
    table cleanly."""
    # Both tools empty → DURUR.
    with pytest.raises(cgt.NoCandidatesError):
        cgt.transform(
            raw_keyword_ideas=empty_rest_envelope,
            raw_related_keywords=empty_rest_envelope,
            project_slug="p-test",
            seed_keyword="seed",
        )

    # Only keyword_ideas non-None and empty; related absent → empty staging
    # for ideas, no DURUR (the gate requires BOTH to be present + empty).
    out = cgt.transform(
        raw_keyword_ideas=empty_rest_envelope,
        raw_related_keywords=None,
        project_slug="p-test",
        seed_keyword="seed",
    )
    assert out[cgt.SOURCE_KEYWORD_IDEAS] is not None
    assert out[cgt.SOURCE_KEYWORD_IDEAS]["row_count"] == 0
    assert out[cgt.SOURCE_KEYWORD_IDEAS]["rows"] == []
    assert out[cgt.SOURCE_RELATED_KEYWORDS] is None
    assert out["meta"][f"{cgt.SOURCE_KEYWORD_IDEAS}_row_count"] == 0


# ---------------------------------------------------------------------------
# Test 3 — REST envelope shape parsed correctly
# ---------------------------------------------------------------------------

def test_rest_envelope_shape_parsed(
    keyword_ideas_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
) -> None:
    """REST envelope ``tasks[0].result[0].items`` must surface 3 rows in
    the keyword_ideas staging payload."""
    out = cgt.transform(
        raw_keyword_ideas=keyword_ideas_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        project_slug="p-test",
        seed_keyword="seed",
    )
    ideas = out[cgt.SOURCE_KEYWORD_IDEAS]
    assert ideas is not None
    assert ideas["row_count"] == 3
    assert ideas["tool"] == cgt.SOURCE_KEYWORD_IDEAS
    assert ideas["seed_keyword"] == "seed"
    assert ideas["project_slug"] == "p-test"
    assert tuple(ideas["columns"]) == cgt.CONTENT_GAPS_COLUMNS

    # Per-row invariants: id monotonic from 1, content_hash sha256:hex.
    for idx, row in enumerate(ideas["rows"], start=1):
        assert row["id"] == idx
        assert isinstance(row["content_hash"], str)
        assert row["content_hash"].startswith("sha256:")
        # exact column projection — staging-shape lock.
        assert set(row.keys()) == set(cgt.CONTENT_GAPS_COLUMNS)
        # source label projected.
        assert row["source"] == cgt.SOURCE_KEYWORD_IDEAS
        # seed_keyword embedded for traceability.
        assert row["seed_keyword"] == "seed"


# ---------------------------------------------------------------------------
# Test 4 — Flat envelope shape parsed correctly (D-003 lesson)
# ---------------------------------------------------------------------------

def test_flat_envelope_shape_parsed(
    keyword_ideas_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
) -> None:
    """Flat wrapper ``{"items": [...]}`` (dataforseo-mcp-server@2.8.9
    flattening) must also normalise to the same staging shape — proving
    the imported _normalize_dfs_response handles both shapes.
    """
    out = cgt.transform(
        raw_keyword_ideas=keyword_ideas_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        project_slug="p-test",
        seed_keyword="seed",
    )
    related = out[cgt.SOURCE_RELATED_KEYWORDS]
    assert related is not None
    assert related["row_count"] == 2
    assert related["tool"] == cgt.SOURCE_RELATED_KEYWORDS
    keywords = {r["keyword"] for r in related["rows"]}
    assert keywords == {"related-kw-1", "related-kw-2"}
    # related_keywords' "keyword_data" nesting was unwrapped.
    for row in related["rows"]:
        assert row["source"] == cgt.SOURCE_RELATED_KEYWORDS
        assert row["seed_keyword"] == "seed"


# ---------------------------------------------------------------------------
# Test 5 — gap_score formula sanity + sort order (high vol, low diff = top)
# ---------------------------------------------------------------------------

def test_gap_score_sanity_and_sort(
    keyword_ideas_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
) -> None:
    """gap_score = (volume / (1 + difficulty)) * (1 - competition_norm).

    The fixture has three candidates with the same volume (12000 vs 12000)
    but radically different (difficulty, competition). The LOW-comp +
    low-difficulty row must score highest, HIGH-comp + high-difficulty
    must score lowest. Mid sits between.
    """
    # Direct formula sanity.
    high_score = cgt.gap_score(
        search_volume=12000, keyword_difficulty=12, competition=0.15,
    )
    low_score = cgt.gap_score(
        search_volume=12000, keyword_difficulty=75, competition=0.92,
    )
    assert high_score > low_score > 0
    # Volume==0 → score==0.
    assert cgt.gap_score(search_volume=0, keyword_difficulty=10, competition=0.5) == 0.0
    # Negative / None volume → 0.
    assert cgt.gap_score(search_volume=None, keyword_difficulty=10, competition=0.5) == 0.0

    out = cgt.transform(
        raw_keyword_ideas=keyword_ideas_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        project_slug="p-test",
        seed_keyword="seed",
    )
    ideas_rows = out[cgt.SOURCE_KEYWORD_IDEAS]["rows"]
    # First row must be the LOW-comp high-vol candidate.
    assert ideas_rows[0]["keyword"] == "kw-low-comp-high-vol"
    # gap_score strictly descending.
    scores = [r["gap_score"] for r in ideas_rows]
    assert scores == sorted(scores, reverse=True)
    # ids stay monotonic 1..N regardless of sort.
    assert [r["id"] for r in ideas_rows] == list(range(1, len(ideas_rows) + 1))


# ---------------------------------------------------------------------------
# Test 6 — Budget pre-flight subprocess: exit 1 → BudgetExceededError
# ---------------------------------------------------------------------------

def test_budget_preflight_exit_1_raises(tmp_path: Path) -> None:
    """preflight_budget() wraps scripts/budget/check_budget.py as a
    subprocess. When the underlying script exits non-zero (budget
    exceeded), the wrapper must raise BudgetExceededError — never
    silently downgrade. We mock subprocess.run so the test does not
    depend on the real script's exact path / behaviour."""
    fake_completed = mock.Mock()
    fake_completed.returncode = 1
    fake_completed.stdout = '{"budget_per_day":10,"used_24h":12,"remaining":-2,"exceeded":true}'
    fake_completed.stderr = ""
    with mock.patch.object(subprocess, "run", return_value=fake_completed):
        with pytest.raises(cgt.BudgetExceededError) as ei:
            cgt.preflight_budget(
                project_config_path=tmp_path / "project.config.json",
                events_path=tmp_path / "events.jsonl",
            )
        assert "budget pre-flight FAIL" in str(ei.value)
        assert isinstance(ei.value, cgt.ContentGapsError)

    # Happy path: exit 0 → returns parsed envelope.
    fake_ok = mock.Mock()
    fake_ok.returncode = 0
    fake_ok.stdout = '{"budget_per_day":500,"used_24h":15,"remaining":485,"exceeded":false}'
    fake_ok.stderr = ""
    with mock.patch.object(subprocess, "run", return_value=fake_ok):
        env = cgt.preflight_budget(
            project_config_path=tmp_path / "project.config.json",
            events_path=tmp_path / "events.jsonl",
        )
        assert env["exceeded"] is False
        assert env["budget_per_day"] == 500


# ---------------------------------------------------------------------------
# Test 7 — Keyword cap (DoS guard) → KeywordCapExceededError
# ---------------------------------------------------------------------------

def test_keyword_cap_exceeded() -> None:
    """When the MCP returns more candidates than the cap, transform must
    raise KeywordCapExceededError before doing any heavy work. This is the
    DoS-prevention DURUR called out in the worker brief."""
    # Build a fixture with 6 items and cap=5.
    big_ideas = {
        "items": [
            {"keyword": f"kw-{i}",
             "keyword_info": {"search_volume": 100, "competition": 0.5,
                              "cpc": 0.0},
             "keyword_properties": {"keyword_difficulty": 10}}
            for i in range(6)
        ],
    }
    related = {"items": []}
    with pytest.raises(cgt.KeywordCapExceededError) as ei:
        cgt.transform(
            raw_keyword_ideas=big_ideas,
            raw_related_keywords=related,
            project_slug="p-test",
            seed_keyword="seed",
            keyword_cap=5,
        )
    assert "keyword_cap=5" in str(ei.value)
    assert isinstance(ei.value, cgt.ContentGapsError)


# ---------------------------------------------------------------------------
# Test 8 — Drift / unrecognized DFS shape propagates from _normalize_dfs_response
# ---------------------------------------------------------------------------

def test_unrecognized_shape_propagates() -> None:
    """An unrecognized DFS shape must propagate the ValueError raised by
    the imported _normalize_dfs_response — no swallowing, no fallback.
    """
    with pytest.raises(ValueError) as ei:
        cgt.transform(
            raw_keyword_ideas={"foo": "bar"},        # neither REST nor flat
            raw_related_keywords={"items": []},
            project_slug="p-test",
            seed_keyword="seed",
        )
    assert "Unrecognized DFS response shape" in str(ei.value)


# ---------------------------------------------------------------------------
# Test 9 — IMPORT discipline: identity preserved, _normalize_dfs_response
#                              is the SAME function as scripts.ingestion.dfs_pull's
# ---------------------------------------------------------------------------

def test_import_discipline_normalize_is_imported_not_copied() -> None:
    """The brief is explicit: KOPYA YASAK. The transform module must use
    the SAME function object that scripts.ingestion.dfs_pull defines, so
    any future shape-handling fix in dfs_pull is inherited automatically.

    Identity check via ``is`` — defeats accidental redefinition.
    """
    assert cgt._normalize_dfs_response is _dfs_pull_module._normalize_dfs_response, (
        "scripts.discovery.content_gaps_transform._normalize_dfs_response "
        "must be IMPORTED (not copied) from scripts.ingestion.dfs_pull. "
        "Restore: `from scripts.ingestion.dfs_pull import _normalize_dfs_response`."
    )

    # Same identity for StagingSchemaError — re-export contract.
    assert cgt.StagingSchemaError is _dfs_pull_module.StagingSchemaError, (
        "scripts.discovery.content_gaps_transform.StagingSchemaError "
        "must be the SAME class as scripts.ingestion.dfs_pull.StagingSchemaError"
    )


# ---------------------------------------------------------------------------
# Test 10 — Smoke E2E: transform → write_staging → on-disk shape lock
# ---------------------------------------------------------------------------

def test_smoke_e2e_write_staging(
    tmp_path: Path,
    keyword_ideas_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
) -> None:
    """End-to-end smoke (staging-only flow):
      1. transform() mock TR payloads → keyword_ideas + related_keywords
         staging dicts.
      2. write_staging() persists each to
         tmp_path/_state/staging/content_gaps_{tool}_{date}_{slug}.json.
      3. _validate_staging_payload accepts each on-disk file (no drift).
      4. NO master.xlsx written.
    """
    project_slug = "p-test"
    date_str = "2026-05-01"

    out = cgt.transform(
        raw_keyword_ideas=keyword_ideas_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        project_slug=project_slug,
        seed_keyword="seed",
    )

    project_dir = tmp_path / "projects" / project_slug
    staging_dir = project_dir / "_state" / "staging"

    written = cgt.write_staging(
        out,
        staging_dir=staging_dir,
        project_slug=project_slug,
        date=date_str,
    )

    ideas_path = Path(written[cgt.SOURCE_KEYWORD_IDEAS])
    related_path = Path(written[cgt.SOURCE_RELATED_KEYWORDS])
    assert ideas_path.exists()
    assert related_path.exists()
    # Filename convention.
    assert ideas_path.name == f"content_gaps_keyword_ideas_{date_str}_{project_slug}.json"
    assert related_path.name == f"content_gaps_related_keywords_{date_str}_{project_slug}.json"
    # Files live under the canonical staging path.
    assert staging_dir in ideas_path.parents

    # Re-validate on-disk JSON shape (defensive — should not raise).
    on_disk_ideas = json.loads(ideas_path.read_text("utf-8"))
    cgt._validate_staging_payload(
        on_disk_ideas, columns=cgt.CONTENT_GAPS_COLUMNS,
    )
    on_disk_related = json.loads(related_path.read_text("utf-8"))
    cgt._validate_staging_payload(
        on_disk_related, columns=cgt.CONTENT_GAPS_COLUMNS,
    )

    # IMPORTANT: no master.xlsx written. Phase 8 cluster-map is the
    # downstream consumer that lifts staging JSON into Excel.
    assert not (project_dir / "master.xlsx").exists()


# ---------------------------------------------------------------------------
# Test 11 — Plugin-agnostik: no slug literals; transform accepts any slug
# ---------------------------------------------------------------------------

def test_plugin_agnostik_no_slug_dependency(
    keyword_ideas_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
) -> None:
    """The transform is purely data-driven. Two synthetic invocations
    with different fake slugs must produce structurally identical row
    counts and column shape — proving the function does not branch on
    slug content.
    """
    out_a = cgt.transform(
        raw_keyword_ideas=keyword_ideas_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        project_slug="site-a",
        seed_keyword="seed",
    )
    out_b = cgt.transform(
        raw_keyword_ideas=keyword_ideas_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        project_slug="site-b",
        seed_keyword="seed",
    )
    assert out_a[cgt.SOURCE_KEYWORD_IDEAS]["row_count"] \
        == out_b[cgt.SOURCE_KEYWORD_IDEAS]["row_count"]
    assert out_a[cgt.SOURCE_RELATED_KEYWORDS]["row_count"] \
        == out_b[cgt.SOURCE_RELATED_KEYWORDS]["row_count"]
    # Project slug is the only structural difference.
    assert out_a[cgt.SOURCE_KEYWORD_IDEAS]["project_slug"] == "site-a"
    assert out_b[cgt.SOURCE_KEYWORD_IDEAS]["project_slug"] == "site-b"
