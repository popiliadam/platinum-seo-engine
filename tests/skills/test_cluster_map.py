"""
tests/skills/test_cluster_map.py — cluster-map planning skill tests.

Phase 8 Wave 1 (W-C1, paid-MCP DFS HEAVY + GSC enrichment, master.xlsx
#cluster_keywords write target). The transform follows the
cannibalization Excel-write pattern (NOT staging-only) since the
cluster_keywords sheet is the canonical Phase 8 keyword inventory —
content-gaps staging is consumed (D-003 staging consume), never
re-emitted.

Schemas referenced:
  - schemas/master-excel.schema.json (cluster_keywords required_columns,
    intent enum)
  - schemas/skill-frontmatter.schema.json (frontmatter contract Draft 7)
  - schemas/cross-sheet-invariants.json (D-02 invariant)

Cross-module IMPORT-only discipline:
  - scripts.ingestion.dfs_pull (_normalize_dfs_response — IDENTITY
    preserved; no copy)

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_cluster_map.py -v
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

from scripts.planning import cluster_map_transform as cmt
from scripts.ingestion import dfs_pull as _dfs_pull_module


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "planning" / "cluster-map" / "SKILL.md"


# ---------------------------------------------------------------------------
# Fixtures — schemas
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def master_excel_schema() -> dict:
    return json.loads((SCHEMAS / "master-excel.schema.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    """Parse the YAML frontmatter block of the cluster-map SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


# ---------------------------------------------------------------------------
# Fixtures — mock DFS payloads (REST envelope + flat wrapper)
# ---------------------------------------------------------------------------

@pytest.fixture
def keyword_suggestions_rest_envelope() -> dict:
    """REST envelope shape: tasks[0].result[0].items.

    Three candidates with cluster-relevant tokens so the assignment
    heuristic is non-trivial:
      - "white sneakers"     → cluster "Sneakers"
      - "leather sofa set"   → cluster "Sofa"
      - "dental clinic price" → cluster "Dental"
    """
    return {
        "tasks": [{
            "result": [{
                "location_code": 2792,
                "language_code": "tr",
                "items": [
                    {
                        "keyword": "white sneakers",
                        "keyword_info": {"search_volume": 8000},
                        "search_intent_info": {"main_intent": "commercial"},
                    },
                    {
                        "keyword": "leather sofa set",
                        "keyword_info": {"search_volume": 4500},
                        "search_intent_info": {"main_intent": "transactional"},
                    },
                    {
                        "keyword": "dental clinic price",
                        "keyword_info": {"search_volume": 2200},
                        "search_intent_info": {"main_intent": "commercial"},
                    },
                ],
            }],
        }],
    }


@pytest.fixture
def related_keywords_flat_wrapper() -> dict:
    """Flat wrapper shape: top-level items list.

    Two related-keyword candidates that overlap with the suggestions
    fixture (one duplicate keyword to exercise dedup; one new keyword
    with no good cluster match to exercise the no-cluster skip path).
    """
    return {
        "items": [
            {
                "keyword_data": {
                    "keyword": "white sneakers",     # duplicate (lower volume)
                    "keyword_info": {"search_volume": 6000},
                },
                "depth": 1,
            },
            {
                "keyword_data": {
                    "keyword": "random widget xyz",  # no cluster match
                    "keyword_info": {"search_volume": 100},
                },
                "depth": 1,
            },
        ],
    }


@pytest.fixture
def gsc_payload() -> dict:
    """GSC enhanced_search_analytics payload covering 1 of 3 clustered
    keywords (white sneakers) so the gsc_match_pct meta surfaces a
    non-trivial value."""
    return {
        "rows": [
            {
                "keys": ["white sneakers", "https://example.com/sneakers/white"],
                "clicks": 50,
                "impressions": 500,
                "ctr": 0.10,
                "position": 4.2,
            },
            {
                "keys": ["white sneakers", "https://example.com/categories/white-sneakers"],
                "clicks": 12,
                "impressions": 200,
                "ctr": 0.06,
                "position": 11.5,
            },
            {
                # query unrelated to any DFS candidate — should not match.
                "keys": ["unrelated query", "https://example.com/other"],
                "clicks": 5,
                "impressions": 50,
                "position": 8.0,
            },
        ],
    }


@pytest.fixture
def cluster_defs() -> list[str]:
    """D-02 source of truth — populated from master.xlsx#topical_map
    column B in production. Synthetic for unit tests."""
    return ["Sneakers", "Sofa", "Dental"]


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + validates against skill-frontmatter.schema.json
# ---------------------------------------------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=cluster-map, status=wip, version="1.0",
          category=planning,
      (c) declare project_slug + seed_keyword as required string inputs,
      (d) list keyword_suggestions + related_keywords +
          enhanced_search_analytics in required tools,
      (e) carry budget {uses_paid_mcp: true, estimated_credits: N} ONLY
          (no _per_call / _per_url leakage — Q-W-A4-01 lesson),
      (f) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "cluster-map"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "planning"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True
    assert "seed_keyword" in inputs
    assert inputs["seed_keyword"]["required"] is True

    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__dataforseo__dataforseo_labs_google_keyword_suggestions" in required_tools
    assert "mcp__dataforseo__dataforseo_labs_google_related_keywords" in required_tools
    assert "mcp__gsc__enhanced_search_analytics" in required_tools

    # budget block contains ONLY uses_paid_mcp + estimated_credits.
    budget = fm["budget"]
    assert budget["uses_paid_mcp"] is True
    assert isinstance(budget.get("estimated_credits"), (int, float))
    assert budget["estimated_credits"] > 0
    assert set(budget.keys()) <= {"uses_paid_mcp", "estimated_credits"}, (
        f"budget contains forbidden keys (additionalProperties:false); "
        f"got {sorted(budget.keys())}"
    )

    # Outputs include master.xlsx#cluster_keywords + raw inboxes + report.
    outputs = fm["outputs"]
    assert any("master.xlsx#cluster_keywords" in o for o in outputs)
    assert any("inbox/dfs/" in o and "keyword_suggestions" in o for o in outputs)
    assert any("inbox/dfs/" in o and "related_keywords" in o for o in outputs)
    assert any("inbox/gsc/" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("outputs/reports/" in o and "cluster-map" in o for o in outputs)

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
# Test 2 — Schema column tuple (11 cols, exact order) matches master-excel
# ---------------------------------------------------------------------------

def test_cluster_map_column_tuple_11_exact(master_excel_schema: dict) -> None:
    """The transform CLUSTER_KEYWORDS_COLUMNS tuple MUST match
    schemas/master-excel.schema.json#cluster_keywords required_columns
    exactly: 11 columns, stable order. Schema-first discipline."""
    sheet = master_excel_schema["sheets"]["cluster_keywords"]
    schema_col_names = tuple(c["name"] for c in sheet["required_columns"])
    assert len(schema_col_names) == 11, (
        f"schema col count drift: got {len(schema_col_names)}"
    )
    assert schema_col_names == cmt.CLUSTER_KEYWORDS_COLUMNS, (
        f"transform tuple drift: got {cmt.CLUSTER_KEYWORDS_COLUMNS}, "
        f"expected {schema_col_names}"
    )


# ---------------------------------------------------------------------------
# Test 3 — D-003 IDENTITY: _normalize_dfs_response is the SAME function
# ---------------------------------------------------------------------------

def test_cluster_map_dfs_normalize_helper_imported() -> None:
    """KOPYA YASAK. The transform module must use the SAME function object
    that scripts.ingestion.dfs_pull defines, so any future shape-handling
    fix in dfs_pull is inherited automatically.

    Identity check via ``is`` — defeats accidental redefinition.
    """
    assert cmt._normalize_dfs_response is _dfs_pull_module._normalize_dfs_response, (
        "scripts.planning.cluster_map_transform._normalize_dfs_response "
        "must be IMPORTED (not copied) from scripts.ingestion.dfs_pull. "
        "Restore: `from scripts.ingestion.dfs_pull import _normalize_dfs_response`."
    )


# ---------------------------------------------------------------------------
# Test 4 — D-02 invariant: cluster outside cluster_defs → ClusterDefError
# ---------------------------------------------------------------------------

def test_cluster_map_d02_invariant_violation_raises(
    keyword_suggestions_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
    gsc_payload: dict,
) -> None:
    """If cluster_defs is empty, transform MUST raise ClusterDefError —
    D-02 invariant cannot be silently fabricated. Also: the assignment
    heuristic must NEVER emit a cluster outside cluster_defs (covered
    by the defensive ClusterDefError raise inside the projection loop).
    """
    # (a) Empty cluster_defs → DURUR.
    with pytest.raises(cmt.ClusterDefError) as ei_empty:
        cmt.transform(
            raw_keyword_suggestions=keyword_suggestions_rest_envelope,
            raw_related_keywords=related_keywords_flat_wrapper,
            raw_gsc=gsc_payload,
            cluster_defs=[],
            project_slug="p-test",
            seed_keyword="seed",
        )
    assert "cluster_defs is empty" in str(ei_empty.value)
    assert isinstance(ei_empty.value, cmt.ClusterMapError)

    # (b) cluster_defs not a list → DURUR.
    with pytest.raises(cmt.ClusterDefError):
        cmt.transform(
            raw_keyword_suggestions=keyword_suggestions_rest_envelope,
            raw_related_keywords=related_keywords_flat_wrapper,
            raw_gsc=gsc_payload,
            cluster_defs="not-a-list",  # type: ignore[arg-type]
            project_slug="p-test",
            seed_keyword="seed",
        )

    # (c) cluster_defs only-whitespace strings → still empty after dedup → DURUR.
    with pytest.raises(cmt.ClusterDefError):
        cmt.transform(
            raw_keyword_suggestions=keyword_suggestions_rest_envelope,
            raw_related_keywords=related_keywords_flat_wrapper,
            raw_gsc=gsc_payload,
            cluster_defs=["", "   ", "\t"],
            project_slug="p-test",
            seed_keyword="seed",
        )


# ---------------------------------------------------------------------------
# Test 5 — DFS unrecognized shape → ValueError propagates from helper
# ---------------------------------------------------------------------------

def test_cluster_map_dfs_response_flat_shape_durur(
    cluster_defs: list[str],
    gsc_payload: dict,
) -> None:
    """An unrecognized DFS shape must propagate the ValueError raised by
    the imported _normalize_dfs_response — no swallowing, no fallback.
    """
    with pytest.raises(ValueError) as ei:
        cmt.transform(
            raw_keyword_suggestions={"foo": "bar"},   # neither REST nor flat
            raw_related_keywords={"items": []},
            raw_gsc=gsc_payload,
            cluster_defs=cluster_defs,
            project_slug="p-test",
            seed_keyword="seed",
        )
    assert "Unrecognized DFS response shape" in str(ei.value)


# ---------------------------------------------------------------------------
# Test 6 — Phase 7 staging consume happy path (content-gaps staging fixture)
# ---------------------------------------------------------------------------

def test_cluster_map_staging_consume_content_gaps_present(
    tmp_path: Path,
    cluster_defs: list[str],
    gsc_payload: dict,
) -> None:
    """When a Phase 7 content_gaps staging file is present,
    consume_content_gaps_staging() must project rows into
    DFS-keyword_suggestions-shaped items, which the transform then
    treats identically to a live MCP fetch.
    """
    staging_payload = {
        "schema_version": "1.0",
        "tool": "keyword_ideas",
        "project_slug": "p-test",
        "seed_keyword": "shoes",
        "fetched_at": "2026-05-01T00:00:00.000000+00:00",
        "row_count": 2,
        "columns": [
            "id", "keyword", "search_volume", "keyword_difficulty",
            "competition", "cpc", "gap_score", "source", "seed_keyword",
            "content_hash", "fetched_at",
        ],
        "rows": [
            {
                "id": 1, "keyword": "white sneakers", "search_volume": 9000,
                "keyword_difficulty": 12.0, "competition": 0.2,
                "cpc": 0.5, "gap_score": 12.34, "source": "keyword_ideas",
                "seed_keyword": "shoes", "content_hash": "sha256:deadbeef",
                "fetched_at": "2026-05-01T00:00:00.000000+00:00",
            },
            {
                "id": 2, "keyword": "leather sofa set", "search_volume": 4500,
                "keyword_difficulty": 30.0, "competition": 0.5,
                "cpc": 1.2, "gap_score": 5.67, "source": "keyword_ideas",
                "seed_keyword": "shoes", "content_hash": "sha256:cafef00d",
                "fetched_at": "2026-05-01T00:00:00.000000+00:00",
            },
        ],
    }
    staging_path = tmp_path / "content_gaps_keyword_ideas_2026-05-01_p-test.json"
    staging_path.write_text(
        json.dumps(staging_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    items = cmt.consume_content_gaps_staging(staging_path)
    assert len(items) == 2
    keywords = {it["keyword"] for it in items}
    assert keywords == {"white sneakers", "leather sofa set"}
    # Each projected item carries DFS-shape keyword_info.search_volume.
    for it in items:
        assert "keyword_info" in it
        assert isinstance(it["keyword_info"]["search_volume"], int)

    # Feed the staging-derived items into the transform via the flat
    # wrapper shape — proves end-to-end consume → transform works.
    raw_sugg = {"items": items}
    raw_related = {"items": []}
    out = cmt.transform(
        raw_keyword_suggestions=raw_sugg,
        raw_related_keywords=raw_related,
        raw_gsc=gsc_payload,
        cluster_defs=cluster_defs,
        project_slug="p-test",
        seed_keyword="shoes",
    )
    assert out["meta"]["row_count"] == 2
    rows = out["cluster_keywords"]
    # white sneakers → "Sneakers", leather sofa set → "Sofa".
    by_kw = {r["keyword"]: r for r in rows}
    assert by_kw["white sneakers"]["cluster"] == "Sneakers"
    assert by_kw["leather sofa set"]["cluster"] == "Sofa"

    # Missing staging file → FileNotFoundError DURUR.
    with pytest.raises(FileNotFoundError):
        cmt.consume_content_gaps_staging(tmp_path / "does-not-exist.json")


# ---------------------------------------------------------------------------
# Test 7 — Budget pre-flight subprocess: exit 1 → BudgetExceededError
# ---------------------------------------------------------------------------

def test_cluster_map_budget_preflight_blocks_when_exceeded(
    tmp_path: Path,
) -> None:
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
        with pytest.raises(cmt.BudgetExceededError) as ei:
            cmt.preflight_budget(
                project_config_path=tmp_path / "project.config.json",
                events_path=tmp_path / "events.jsonl",
            )
        assert "budget pre-flight FAIL" in str(ei.value)
        assert isinstance(ei.value, cmt.ClusterMapError)

    # Happy path: exit 0 → returns parsed envelope.
    fake_ok = mock.Mock()
    fake_ok.returncode = 0
    fake_ok.stdout = '{"budget_per_day":500,"used_24h":15,"remaining":485,"exceeded":false}'
    fake_ok.stderr = ""
    with mock.patch.object(subprocess, "run", return_value=fake_ok):
        env = cmt.preflight_budget(
            project_config_path=tmp_path / "project.config.json",
            events_path=tmp_path / "events.jsonl",
        )
        assert env["exceeded"] is False
        assert env["budget_per_day"] == 500


# ---------------------------------------------------------------------------
# Test 8 — Two-shape parse + GSC enrichment merged correctly
# ---------------------------------------------------------------------------

def test_cluster_map_gsc_signal_merged_correctly(
    keyword_suggestions_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
    gsc_payload: dict,
    cluster_defs: list[str],
    master_excel_schema: dict,
) -> None:
    """Both DFS shapes parse, GSC enrichment merges per-keyword, the
    no-cluster keyword is skipped, dedup keeps the highest-volume entry,
    and every emitted row matches the schema-locked column tuple.
    """
    out = cmt.transform(
        raw_keyword_suggestions=keyword_suggestions_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        raw_gsc=gsc_payload,
        cluster_defs=cluster_defs,
        project_slug="p-test",
        seed_keyword="seed",
    )
    rows = out["cluster_keywords"]

    # Schema column lock — every row matches the master-excel tuple exactly.
    sheet = master_excel_schema["sheets"]["cluster_keywords"]
    schema_col_names = tuple(c["name"] for c in sheet["required_columns"])
    for r in rows:
        assert tuple(r.keys()) == schema_col_names

    # 3 candidates × dedup × cluster filter:
    #   - "white sneakers" → kept once (volume 8000 wins over 6000)
    #   - "leather sofa set" → kept (Sofa)
    #   - "dental clinic price" → kept (Dental)
    #   - "random widget xyz" → SKIPPED (no cluster match)
    assert out["meta"]["candidate_count"] == 4    # before cluster filter
    assert out["meta"]["row_count"] == 3
    assert out["meta"]["skipped_no_cluster"] == 1

    by_kw = {r["keyword"]: r for r in rows}
    assert set(by_kw.keys()) == {"white sneakers", "leather sofa set", "dental clinic price"}

    # white sneakers → cluster Sneakers, dedup kept volume=8000.
    ws = by_kw["white sneakers"]
    assert ws["cluster"] == "Sneakers"
    assert ws["monthly_volume"] == 8000
    # GSC enrichment present (62 clicks, 700 impressions, weighted pos).
    assert ws["gsc_clicks"] == 62
    assert ws["gsc_impressions"] == 700
    assert ws["data_source"] == cmt.DS_DFS_PLUS_GSC
    # Top-click URL surfaced as assigned_url.
    assert ws["assigned_url"] == "https://example.com/sneakers/white"
    # Intent enum present.
    assert ws["intent"] in {"Informational", "Commercial", "Transactional", "Navigational"}
    assert ws["intent"] == "Commercial"
    # forbidden_kw / forbidden_reason default empty.
    assert ws["forbidden_kw"] == ""
    assert ws["forbidden_reason"] == ""

    # leather sofa set → no GSC match, defaults to 0/0/0.0 + DFS-only.
    sofa = by_kw["leather sofa set"]
    assert sofa["cluster"] == "Sofa"
    assert sofa["gsc_clicks"] == 0
    assert sofa["gsc_impressions"] == 0
    assert sofa["gsc_position"] == 0.0
    assert sofa["data_source"] == cmt.DS_DFS_ONLY
    assert sofa["assigned_url"] == ""
    assert sofa["intent"] == "Transactional"

    # Sort discipline: cluster asc → monthly_volume desc → keyword asc.
    clusters_seen = [r["cluster"] for r in rows]
    assert clusters_seen == sorted(clusters_seen, key=str.lower)

    # Meta: gsc_match_pct in [0, 1]; gsc_match_count == 1.
    assert out["meta"]["gsc_match_count"] == 1
    assert 0.0 <= out["meta"]["gsc_match_pct"] <= 1.0


# ---------------------------------------------------------------------------
# Test 9 — Plugin-agnostik: transform accepts any slug; no hardcoded value
# ---------------------------------------------------------------------------

def test_cluster_map_plugin_agnostik(
    keyword_suggestions_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
    gsc_payload: dict,
    cluster_defs: list[str],
) -> None:
    """The transform is purely data-driven. Two synthetic invocations
    with different fake slugs must produce structurally identical row
    counts and column shape — proving the function does not branch on
    slug content.
    """
    out_a = cmt.transform(
        raw_keyword_suggestions=keyword_suggestions_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        raw_gsc=gsc_payload,
        cluster_defs=cluster_defs,
        project_slug="site-a",
        seed_keyword="seed",
    )
    out_b = cmt.transform(
        raw_keyword_suggestions=keyword_suggestions_rest_envelope,
        raw_related_keywords=related_keywords_flat_wrapper,
        raw_gsc=gsc_payload,
        cluster_defs=cluster_defs,
        project_slug="site-b",
        seed_keyword="seed",
    )
    assert out_a["meta"]["row_count"] == out_b["meta"]["row_count"]
    # Project slug carried in meta only.
    assert out_a["meta"]["project_slug"] == "site-a"
    assert out_b["meta"]["project_slug"] == "site-b"


# ---------------------------------------------------------------------------
# Test 10 — Smoke E2E: CLI runs end-to-end with on-disk fixtures
# ---------------------------------------------------------------------------

def test_cluster_map_smoke_e2e_cli(
    tmp_path: Path,
    keyword_suggestions_rest_envelope: dict,
    related_keywords_flat_wrapper: dict,
    gsc_payload: dict,
    cluster_defs: list[str],
) -> None:
    """E2E without any live MCP call: write fixtures to disk, invoke
    cluster_map_transform.main CLI, assert the output JSON parses and
    matches the schema-locked column structure.
    """
    sugg_path = tmp_path / "keyword_suggestions.json"
    sugg_path.write_text(
        json.dumps(keyword_suggestions_rest_envelope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    related_path = tmp_path / "related_keywords.json"
    related_path.write_text(
        json.dumps(related_keywords_flat_wrapper, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    gsc_path = tmp_path / "gsc.json"
    gsc_path.write_text(
        json.dumps(gsc_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    defs_path = tmp_path / "cluster_defs.json"
    defs_path.write_text(
        json.dumps(cluster_defs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    rc = cmt.main([
        "--raw-keyword-suggestions", str(sugg_path),
        "--raw-related-keywords",    str(related_path),
        "--raw-gsc",                 str(gsc_path),
        "--cluster-defs-json",       str(defs_path),
        "--seed-keyword",            "seed",
        "--project-slug",            "p-test",
        "--output-dir",              str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    out_file = out_dir / "cluster_keywords.json"
    assert out_file.exists()
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and payload
    expected_cols = set(cmt.CLUSTER_KEYWORDS_COLUMNS)
    for r in payload:
        assert set(r.keys()) == expected_cols


# ---------------------------------------------------------------------------
# Test 11 — KeywordCapExceededError when MCP returns more than the cap
# ---------------------------------------------------------------------------

def test_cluster_map_keyword_cap_exceeded(
    cluster_defs: list[str],
    gsc_payload: dict,
) -> None:
    """When the MCP returns more candidates than the cap, transform must
    raise KeywordCapExceededError before doing any heavy work. DoS
    guard, mirrors content-gaps Phase 7 W-B1 paterni.
    """
    big = {
        "items": [
            {"keyword": f"kw-{i}", "keyword_info": {"search_volume": 10}}
            for i in range(10)
        ]
    }
    with pytest.raises(cmt.KeywordCapExceededError) as ei:
        cmt.transform(
            raw_keyword_suggestions=big,
            raw_related_keywords={"items": []},
            raw_gsc=gsc_payload,
            cluster_defs=cluster_defs,
            project_slug="p-test",
            seed_keyword="seed",
            keyword_cap=5,
        )
    assert "keyword_cap=5" in str(ei.value)
    assert isinstance(ei.value, cmt.ClusterMapError)
