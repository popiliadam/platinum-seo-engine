"""
tests/skills/test_new_content_plan.py — new-content-plan planning skill tests.

Phase 8 Wave 1 (W-C3). Reads Phase 7 content-gaps staging and projects
to master.xlsx#new_content_plan; cross-references cluster_keywords
(snapshot-at-dispatch). KOPYA YASAK identity check preserves
_normalize_dfs_response + StagingSchemaError import discipline from
scripts.ingestion.dfs_pull.

Run: PYTHONPATH=. pytest tests/skills/test_new_content_plan.py -v
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

from scripts.planning import new_content_plan_transform as ncp
from scripts.ingestion import dfs_pull as _dfs_pull_module


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "planning" / "new-content-plan" / "SKILL.md"


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
    """Parse the YAML frontmatter block of the new-content-plan SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


# ---------------------------------------------------------------------------
# Fixtures — synthetic Phase 7 content-gaps staging payload
# ---------------------------------------------------------------------------

@pytest.fixture
def content_gaps_staging_payload() -> dict:
    """Mirrors content_gaps_transform._staging_table_dict shape — schema_version
    + tool + rows[] with id + content_hash + keyword + search_volume +
    gap_score + ..."""
    return {
        "schema_version": "1.0",
        "tool": "keyword_ideas",
        "project_slug": "test-project",
        "seed_keyword": "fixture-seed",
        "fetched_at": "2026-05-01T12:00:00.000000+00:00",
        "row_count": 4,
        "columns": [
            "id", "keyword", "search_volume", "keyword_difficulty",
            "competition", "cpc", "gap_score", "source", "seed_keyword",
            "content_hash", "fetched_at",
        ],
        "rows": [
            {
                "id": 1, "keyword": "modern sofa set",
                "search_volume": 12000, "keyword_difficulty": 12,
                "competition": 0.15, "cpc": 0.95, "gap_score": 1500.0,
                "source": "keyword_ideas", "seed_keyword": "fixture-seed",
                "content_hash": "sha256:aaaa", "fetched_at": "2026-05-01T12:00:00.000000+00:00",
            },
            {
                "id": 2, "keyword": "ucuz koltuk takımı",
                "search_volume": 4500, "keyword_difficulty": 30,
                "competition": 0.50, "cpc": 1.20, "gap_score": 200.0,
                "source": "keyword_ideas", "seed_keyword": "fixture-seed",
                "content_hash": "sha256:bbbb", "fetched_at": "2026-05-01T12:00:00.000000+00:00",
            },
            {
                "id": 3, "keyword": "living room ideas",
                "search_volume": 800, "keyword_difficulty": 25,
                "competition": 0.40, "cpc": 1.10, "gap_score": 50.0,
                "source": "keyword_ideas", "seed_keyword": "fixture-seed",
                "content_hash": "sha256:cccc", "fetched_at": "2026-05-01T12:00:00.000000+00:00",
            },
            {
                "id": 4, "keyword": "yatak odası takımları",
                "search_volume": 2200, "keyword_difficulty": 18,
                "competition": 0.30, "cpc": 0.80, "gap_score": 600.0,
                "source": "keyword_ideas", "seed_keyword": "fixture-seed",
                "content_hash": "sha256:dddd", "fetched_at": "2026-05-01T12:00:00.000000+00:00",
            },
        ],
    }


@pytest.fixture
def cluster_map_fixture() -> dict:
    """Synthetic cluster_keywords snapshot ({keyword_lower: cluster})."""
    return {
        "modern sofa set":      "Living Room",
        "ucuz koltuk takımı":   "Living Room",
        "living room ideas":    "Living Room",
        "yatak odası takımları": "Bedroom",
    }


@pytest.fixture
def search_intent_rest_payload() -> dict:
    """REST envelope DFS search_intent shape — main_intent per keyword."""
    return {
        "tasks": [{
            "result": [{
                "items": [
                    {"keyword": "modern sofa set",
                     "keyword_intent": {"label": "transactional"}},
                    {"keyword": "living room ideas",
                     "keyword_intent": {"label": "informational"}},
                    {"keyword": "yatak odası takımları",
                     "keyword_intent": {"label": "commercial"}},
                ],
            }],
        }],
    }


@pytest.fixture
def keyword_overview_flat_payload() -> dict:
    """Flat wrapper DFS keyword_overview — volume refresh on a subset."""
    return {
        "items": [
            {
                "keyword": "modern sofa set",
                "keyword_info": {"search_volume": 13500, "competition": 0.18},
            },
        ],
    }


# ---------------------------------------------------------------------------
# Test 1 — D-003 import discipline IDENTITY check (mandatory)
# ---------------------------------------------------------------------------

def test_new_content_plan_dfs_normalize_helper_imported() -> None:
    """KOPYA YASAK. transform module MUST use the SAME function object that
    scripts.ingestion.dfs_pull defines — identity check via `is`."""
    assert ncp._normalize_dfs_response is _dfs_pull_module._normalize_dfs_response
    assert ncp.StagingSchemaError is _dfs_pull_module.StagingSchemaError


# ---------------------------------------------------------------------------
# Test 2 — Schema-first: new_content_plan column tuple matches master-excel
# ---------------------------------------------------------------------------

def test_new_content_plan_column_tuple_14_exact(
    master_excel_schema: dict,
) -> None:
    """transform NEW_CONTENT_PLAN_COLUMNS == master-excel schema column tuple
    in order. NOTE: Phase 8 worker brief said 10 cols; live schema declared 11
    (lifecycle_status); Phase 10 additive bump pushes this to 14 (image_prompt
    + alt_text + content_type — R-71/R-72/R-77 image discipline + content_type
    enum widening, Q-IL-1 + Q-W-C2-01 paterni reuse). Schema-first wins; brief
    drift surfaced upstream."""
    sheet_def = master_excel_schema["sheets"]["new_content_plan"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    # 14 cols, exact order match.
    assert len(schema_col_names) == 14
    assert schema_col_names == ncp.NEW_CONTENT_PLAN_COLUMNS, (
        f"transform NEW_CONTENT_PLAN_COLUMNS drift from master-excel schema: "
        f"transform={ncp.NEW_CONTENT_PLAN_COLUMNS} vs schema={schema_col_names}"
    )
    # tivl_tag enum is locked at the schema level too.
    tivl_col = next(c for c in sheet_def["required_columns"] if c["name"] == "tivl_tag")
    assert set(tivl_col["enum"]) == {"T", "I", "V", "L"}
    lifecycle_col = next(
        c for c in sheet_def["required_columns"] if c["name"] == "lifecycle_status"
    )
    assert set(lifecycle_col["enum"]) == {"GREEN", "RED", "ON_HOLD", "REMOVED"}
    # Phase 10 additive bump — content_type enum locked at schema level.
    content_type_col = next(
        c for c in sheet_def["required_columns"] if c["name"] == "content_type"
    )
    assert set(content_type_col["enum"]) == {
        "listicle", "guide", "comparison", "research", "tutorial", "review",
    }


# ---------------------------------------------------------------------------
# Test 3 — Frontmatter parses + validates against schema (Q-W-A4-01 lesson)
# ---------------------------------------------------------------------------

def test_new_content_plan_frontmatter_validates(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    """Frontmatter parses, name/status/version/category locked,
    keyword_ideas required + overview/intent optional, budget block
    additionalProperties:false (Q-W-A4-01), Draft 7 validation passes."""
    fm = skill_frontmatter
    assert fm["name"] == "new-content-plan"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "planning"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__dataforseo__dataforseo_labs_google_keyword_ideas" in required_tools
    optional_tools = fm["mcp_tools"]["optional"]
    assert "mcp__dataforseo__dataforseo_labs_google_keyword_overview" in optional_tools
    assert "mcp__dataforseo__dataforseo_labs_search_intent" in optional_tools

    # Q-W-A4-01: budget block contains ONLY uses_paid_mcp + estimated_credits.
    budget = fm["budget"]
    assert budget["uses_paid_mcp"] is True
    assert isinstance(budget.get("estimated_credits"), (int, float))
    assert budget["estimated_credits"] > 0
    assert set(budget.keys()) <= {"uses_paid_mcp", "estimated_credits"}, (
        f"budget contains forbidden keys (additionalProperties:false); "
        f"got {sorted(budget.keys())}"
    )

    # Outputs include master.xlsx#new_content_plan + raw inbox + report.
    outputs = fm["outputs"]
    assert any("master.xlsx#new_content_plan" in o for o in outputs)
    assert any("inbox/dfs/" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("outputs/reports/" in o and "new-content-plan" in o for o in outputs)

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
# Test 4 — Cluster_keywords empty → CLUSTER_KEYWORDS_EMPTY DURUR
# ---------------------------------------------------------------------------

def test_new_content_plan_cluster_xref_empty_durur(
    content_gaps_staging_payload: dict,
) -> None:
    """Empty cluster_map → ClusterKeywordsEmptyError (CLUSTER_KEYWORDS_EMPTY).
    Workflow ordering issue, not parallel-write race."""
    with pytest.raises(ncp.ClusterKeywordsEmptyError) as ei:
        ncp.transform(
            content_gaps_staging_payload,
            cluster_map={},        # empty → DURUR
        )
    assert "cluster-map" in str(ei.value).lower()
    # The error inherits from NewContentPlanError so a single except covers it.
    assert isinstance(ei.value, ncp.NewContentPlanError)

    # read_cluster_keywords_snapshot also DURURs on empty rows.
    with pytest.raises(ncp.ClusterKeywordsEmptyError):
        ncp.read_cluster_keywords_snapshot(rows=[])
    with pytest.raises(ncp.ClusterKeywordsEmptyError):
        # Only blank rows → empty map → DURUR.
        ncp.read_cluster_keywords_snapshot(
            rows=[{"keyword": "", "cluster": ""}, {"keyword": "  "}],
        )


# ---------------------------------------------------------------------------
# Test 5 — Phase 7 staging consume present → rows projected correctly
# ---------------------------------------------------------------------------

def test_new_content_plan_staging_consume_content_gaps_present(
    content_gaps_staging_payload: dict,
    cluster_map_fixture: dict,
    master_excel_schema: dict,
) -> None:
    """Phase 7 W-B1 staging consume: rows sorted by gap_score desc, capped
    at max_rows, each row matches master-excel column tuple."""
    out = ncp.transform(
        content_gaps_staging_payload,
        cluster_map=cluster_map_fixture,
        max_rows=10,
    )
    rows = out["new_content_plan"]
    # All 4 staging rows survive (max_rows=10 >= 4).
    assert len(rows) == 4
    assert out["meta"]["row_count"] == 4
    assert out["meta"]["input_staging_rows"] == 4

    # Schema column match.
    sheet_def = master_excel_schema["sheets"]["new_content_plan"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    for r in rows:
        assert tuple(r.keys()) == schema_col_names

    # Sort order: gap_score desc → 1500, 600, 200, 50.
    primary_keywords = [r["primary_keyword"] for r in rows]
    assert primary_keywords[0] == "modern sofa set"          # gap 1500
    assert primary_keywords[1] == "yatak odası takımları"    # gap 600
    assert primary_keywords[2] == "ucuz koltuk takımı"       # gap 200
    assert primary_keywords[3] == "living room ideas"        # gap 50

    # ids monotonic from 1.
    assert [r["id"] for r in rows] == [1, 2, 3, 4]

    # cluster cross-ref applied.
    assert rows[0]["assigned_cluster"] == "Living Room"
    assert rows[1]["assigned_cluster"] == "Bedroom"

    # tivl_tag default ("I") propagates when no search_intent enrichment.
    assert all(r["tivl_tag"] == "I" for r in rows)

    # lifecycle_status default GREEN for every new row.
    assert all(r["lifecycle_status"] == "GREEN" for r in rows)

    # url_slug idempotent + Turkish-folded.
    assert rows[0]["url_slug"] == "modern-sofa-set"
    assert rows[1]["url_slug"] == "yatak-odasi-takimlari"

    # priority via gap_score: 1500 → P1, 600 → P2, 200 → P2, 50 → P3.
    assert rows[0]["priority"] == "P1"
    assert rows[1]["priority"] == "P2"
    assert rows[2]["priority"] == "P2"
    assert rows[3]["priority"] == "P3"

    # max_rows cap exercised — top-N projection.
    capped = ncp.transform(
        content_gaps_staging_payload,
        cluster_map=cluster_map_fixture,
        max_rows=2,
    )
    assert capped["meta"]["row_count"] == 2
    assert [r["primary_keyword"] for r in capped["new_content_plan"]] == [
        "modern sofa set",
        "yatak odası takımları",
    ]


# ---------------------------------------------------------------------------
# Test 6 — Search intent → tivl_tag mapping + keyword_overview volume refresh
# ---------------------------------------------------------------------------

def test_new_content_plan_intent_and_overview_enrichment(
    content_gaps_staging_payload: dict,
    cluster_map_fixture: dict,
    search_intent_rest_payload: dict,
    keyword_overview_flat_payload: dict,
) -> None:
    """search_intent → tivl_tag (transactional→T, informational→I,
    commercial→T). Missing keywords fall back to default_tivl_tag.
    keyword_overview refreshes monthly_volume on its subset only."""
    out = ncp.transform(
        content_gaps_staging_payload,
        cluster_map=cluster_map_fixture,
        raw_search_intent=search_intent_rest_payload,
        raw_keyword_overview=keyword_overview_flat_payload,
        default_tivl_tag="I",
        max_rows=10,
    )
    rows = {r["primary_keyword"]: r for r in out["new_content_plan"]}

    # tivl_tag per intent map.
    assert rows["modern sofa set"]["tivl_tag"] == "T"
    assert rows["living room ideas"]["tivl_tag"] == "I"
    # commercial → T (transactional umbrella in TIVL).
    assert rows["yatak odası takımları"]["tivl_tag"] == "T"
    # Keyword absent from intent payload → default_tivl_tag "I".
    assert rows["ucuz koltuk takımı"]["tivl_tag"] == "I"

    # keyword_overview volume refresh on the covered subset.
    assert rows["modern sofa set"]["monthly_volume"] == 13500
    # Uncovered keywords retain staging volume.
    assert rows["living room ideas"]["monthly_volume"] == 800
    assert rows["yatak odası takımları"]["monthly_volume"] == 2200

    # tivl_tag=T overrides target_word_count to 1200.
    assert rows["modern sofa set"]["target_word_count"] == 1200
    # tivl_tag=I uses the input default (1500).
    assert rows["ucuz koltuk takımı"]["target_word_count"] == 1500

    # meta carries enrichment provenance.
    assert out["meta"]["intent_enrichment_present"] is True
    assert out["meta"]["overview_enrichment_present"] is True


# ---------------------------------------------------------------------------
# Test 7 — Budget pre-flight subprocess: exit 1 → BudgetExceededError
# ---------------------------------------------------------------------------

def test_new_content_plan_budget_preflight_blocks_when_exceeded(
    tmp_path: Path,
) -> None:
    """Subprocess wrapper exit non-zero → BudgetExceededError. Happy path
    exit 0 → parsed envelope. subprocess.run mocked for hermeticity."""
    fake_completed = mock.Mock()
    fake_completed.returncode = 1
    fake_completed.stdout = '{"budget_per_day":10,"used_24h":12,"remaining":-2,"exceeded":true}'
    fake_completed.stderr = ""
    with mock.patch.object(subprocess, "run", return_value=fake_completed):
        with pytest.raises(ncp.BudgetExceededError) as ei:
            ncp.preflight_budget(
                project_config_path=tmp_path / "project.config.json",
                events_path=tmp_path / "events.jsonl",
            )
        assert "budget pre-flight FAIL" in str(ei.value)
        assert isinstance(ei.value, ncp.NewContentPlanError)

    # Happy path: exit 0 → returns parsed envelope.
    fake_ok = mock.Mock()
    fake_ok.returncode = 0
    fake_ok.stdout = '{"budget_per_day":500,"used_24h":15,"remaining":485,"exceeded":false}'
    fake_ok.stderr = ""
    with mock.patch.object(subprocess, "run", return_value=fake_ok):
        env = ncp.preflight_budget(
            project_config_path=tmp_path / "project.config.json",
            events_path=tmp_path / "events.jsonl",
        )
        assert env["exceeded"] is False
        assert env["budget_per_day"] == 500


# ---------------------------------------------------------------------------
# Test 8 — DFS unrecognized shape propagates from _normalize_dfs_response
# ---------------------------------------------------------------------------

def test_new_content_plan_dfs_response_flat_shape_durur(
    content_gaps_staging_payload: dict,
    cluster_map_fixture: dict,
) -> None:
    """Unrecognized DFS shape → ValueError propagates from imported
    _normalize_dfs_response (no swallow, no fallback). Tests both
    search_intent and keyword_overview paths."""
    bad_intent = {"foo": "bar"}    # neither REST nor flat
    with pytest.raises(ValueError) as ei:
        ncp.transform(
            content_gaps_staging_payload,
            cluster_map=cluster_map_fixture,
            raw_search_intent=bad_intent,
            max_rows=5,
        )
    assert "Unrecognized DFS response shape" in str(ei.value)

    # Same applies to keyword_overview path.
    bad_overview = {"unknown_envelope": []}
    with pytest.raises(ValueError):
        ncp.transform(
            content_gaps_staging_payload,
            cluster_map=cluster_map_fixture,
            raw_keyword_overview=bad_overview,
            max_rows=5,
        )


# ---------------------------------------------------------------------------
# Test 9 — url_slug idempotency + uniqueness within batch
# ---------------------------------------------------------------------------

def test_new_content_plan_url_slug_uniqueness_within_batch(
    cluster_map_fixture: dict,
) -> None:
    """url_slug deterministic + idempotent; collision within batch →
    UrlSlugUniquenessError (DURUR #8)."""
    # Idempotency.
    samples = [
        ("Modern Sofa Set",        "modern-sofa-set"),
        ("modern sofa set!",       "modern-sofa-set"),
        ("Yatak Odası Takımları",  "yatak-odasi-takimlari"),
        ("ÇOK güzel ÜRÜNLER",      "cok-guzel-urunler"),
        ("   leading-trailing  ",  "leading-trailing"),
    ]
    for raw, expected in samples:
        got = ncp.make_url_slug(raw)
        assert got == expected, f"slug({raw!r}) → {got!r} (expected {expected!r})"
        assert ncp.make_url_slug(got) == got, f"not idempotent: {raw!r}"

    # Uniqueness violation: two distinct keywords reduce to same slug.
    staging_collision = {
        "schema_version": "1.0",
        "tool": "keyword_ideas",
        "rows": [
            {"id": 1, "keyword": "Modern Sofa Set", "search_volume": 1000,
             "gap_score": 500.0},
            {"id": 2, "keyword": "modern sofa, set!!", "search_volume": 800,
             "gap_score": 400.0},
        ],
    }
    extended_cluster_map = {
        **cluster_map_fixture,
        "modern sofa, set!!": "Living Room",
    }
    with pytest.raises(ncp.UrlSlugUniquenessError) as ei:
        ncp.transform(
            staging_collision,
            cluster_map=extended_cluster_map,
            max_rows=10,
        )
    assert "url_slug uniqueness violation" in str(ei.value)
    # RowSchemaError subclass — caller can catch broader.
    assert isinstance(ei.value, ncp.RowSchemaError)


# ---------------------------------------------------------------------------
# Test 10 — tivl_tag enum drift → TivlTagDriftError
# ---------------------------------------------------------------------------

def test_new_content_plan_tivl_tag_enum_drift_durur(
    content_gaps_staging_payload: dict,
    cluster_map_fixture: dict,
) -> None:
    """default_tivl_tag must be one of T/I/V/L. Anything else → TivlTagDriftError."""
    with pytest.raises(ncp.TivlTagDriftError):
        ncp.transform(
            content_gaps_staging_payload,
            cluster_map=cluster_map_fixture,
            default_tivl_tag="X",   # not in enum
        )

    # Also DURUR: default_status not in statusEnum.
    with pytest.raises(ncp.NewContentPlanError):
        ncp.transform(
            content_gaps_staging_payload,
            cluster_map=cluster_map_fixture,
            default_status="NOT-AN-ENUM",
        )

    # Also DURUR: max_rows <= 0.
    with pytest.raises(ncp.NewContentPlanError):
        ncp.transform(
            content_gaps_staging_payload,
            cluster_map=cluster_map_fixture,
            max_rows=0,
        )


# ---------------------------------------------------------------------------
# Test 11 — Phase 7 content_gaps staging locator (file-based + fallback)
# ---------------------------------------------------------------------------

def test_new_content_plan_locate_staging_fallback_and_durur(
    tmp_path: Path,
    content_gaps_staging_payload: dict,
) -> None:
    """locate_content_gaps_staging: (a) newest match wins, (b) nothing +
    no fallback → StagingNotFoundError, (c) fallback dict returned,
    (d) explicit missing path → DURUR."""
    project_root = tmp_path / "projects" / "p-test"
    staging_dir = project_root / "_state" / "staging"
    staging_dir.mkdir(parents=True)

    # (b) nothing on disk, no fallback → DURUR.
    with pytest.raises(ncp.StagingNotFoundError):
        ncp.locate_content_gaps_staging(project_root=project_root)

    # (c) fallback dict.
    got_dict = ncp.locate_content_gaps_staging(
        project_root=project_root,
        fallback_payload=content_gaps_staging_payload,
    )
    assert got_dict is content_gaps_staging_payload

    # (a) newest file wins.
    older = staging_dir / "content_gaps_keyword_ideas_2026-04-01_p-test.json"
    older.write_text(json.dumps({"rows": []}))
    newer = staging_dir / "content_gaps_keyword_ideas_2026-05-01_p-test.json"
    newer.write_text(json.dumps(content_gaps_staging_payload))
    # bump newer mtime to ensure ordering even on filesystems with second resolution.
    import os
    import time
    os.utime(older, (time.time() - 100, time.time() - 100))
    os.utime(newer, (time.time(), time.time()))

    got = ncp.locate_content_gaps_staging(project_root=project_root)
    assert isinstance(got, Path)
    assert got.name == newer.name

    # (d) explicit path that doesn't exist → DURUR.
    with pytest.raises(ncp.StagingNotFoundError):
        ncp.locate_content_gaps_staging(
            project_root=project_root,
            explicit_path=staging_dir / "does-not-exist.json",
        )


# ---------------------------------------------------------------------------
# Test 12 — Plugin-agnostik: transform accepts any slug, no hardcoded value
# ---------------------------------------------------------------------------

def test_new_content_plan_plugin_agnostik_no_slug_dependency(
    content_gaps_staging_payload: dict,
) -> None:
    """Transform is data-driven; two cluster_maps with different cluster
    name values produce identical row shape (only cluster strings differ)."""
    cluster_map_a = {k: f"site-a-{v.lower().split()[0]}"
                     for k, v in {
                         "modern sofa set": "Living", "ucuz koltuk takımı": "Living",
                         "living room ideas": "Living", "yatak odası takımları": "Bedroom",
                     }.items()}
    cluster_map_b = {k: v.replace("site-a", "site-b")
                     for k, v in cluster_map_a.items()}
    out_a = ncp.transform(content_gaps_staging_payload,
                          cluster_map=cluster_map_a, max_rows=10)
    out_b = ncp.transform(content_gaps_staging_payload,
                          cluster_map=cluster_map_b, max_rows=10)
    assert out_a["meta"]["row_count"] == out_b["meta"]["row_count"]
    for ra, rb in zip(out_a["new_content_plan"], out_b["new_content_plan"]):
        assert tuple(ra.keys()) == ncp.NEW_CONTENT_PLAN_COLUMNS
        assert tuple(rb.keys()) == ncp.NEW_CONTENT_PLAN_COLUMNS
        assert ra["primary_keyword"] == rb["primary_keyword"]
        assert ra["url_slug"] == rb["url_slug"]
        assert ra["monthly_volume"] == rb["monthly_volume"]
        assert ra["assigned_cluster"] != rb["assigned_cluster"]


# ---------------------------------------------------------------------------
# Test 13 — Smoke E2E: CLI → schema-shaped JSON output, byte-idempotent
# ---------------------------------------------------------------------------

def test_new_content_plan_smoke_e2e_cli_output(
    tmp_path: Path,
    content_gaps_staging_payload: dict,
    cluster_map_fixture: dict,
) -> None:
    """E2E smoke: fixture → main CLI → schema-shaped JSON. Re-run produces
    byte-identical output (idempotency lock)."""
    staging_path = tmp_path / "staging.json"
    staging_path.write_text(
        json.dumps(content_gaps_staging_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cluster_path = tmp_path / "cluster_map.json"
    cluster_path.write_text(
        json.dumps(cluster_map_fixture, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    rc = ncp.main([
        "--staging", str(staging_path),
        "--cluster-map", str(cluster_path),
        "--max-rows", "10",
        "--date", "2026-05-01",
        "--output-dir", str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    out_file = out_dir / "new_content_plan.json"
    assert out_file.exists(), "CLI did not write new_content_plan.json"

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and payload, "empty output array"
    expected_cols = set(ncp.NEW_CONTENT_PLAN_COLUMNS)
    for r in payload:
        assert set(r.keys()) == expected_cols
        # tivl_tag enum lock.
        assert r["tivl_tag"] in {"T", "I", "V", "L"}
        # lifecycle_status enum lock.
        assert r["lifecycle_status"] in {"GREEN", "RED", "ON_HOLD", "REMOVED"}
        # created_date pinned by --date.
        assert r["created_date"] == "2026-05-01"

    # Idempotency: re-run with same input → byte-identical output file.
    first_bytes = out_file.read_bytes()
    rc2 = ncp.main([
        "--staging", str(staging_path),
        "--cluster-map", str(cluster_path),
        "--max-rows", "10",
        "--date", "2026-05-01",
        "--output-dir", str(out_dir),
    ])
    assert rc2 == 0
    second_bytes = out_file.read_bytes()
    assert first_bytes == second_bytes, (
        "transform is not byte-idempotent under re-run"
    )


# ---------------------------------------------------------------------------
# Test 14 — FIX-L L4: word-count clamp (profile floor) + R-08 override
# ---------------------------------------------------------------------------

def test_word_count_clamp_profile_floor_and_r08_override() -> None:
    """FIX-L L4: the TIVL word-count targets (T=1200/L=1000/V=800/I=1500)
    are an intent-based BASE that must be clamped UP to the project's
    profile word-count floor — ``target = max(TIVL_base, profile_floor)`` —
    so YMYL / b2b-saas content never falls below its Principle-2 minimum
    (YMYL floor 1500). When R-08 SERP-analysis data exists it OVERRIDES the
    TIVL/clamp entirely. Canonical floor source: rules/content-quality.md;
    resolution via scripts/util/profile_aware_defaults.cascade_default.
    """
    body = SKILL_PATH.read_text("utf-8").split("---", 2)[2]
    bl = body.lower()

    # (a) Clamp expression + profile-floor concept documented.
    assert "max(" in body, (
        "word-count section must document the max(base, profile_floor) clamp"
    )
    assert "profile floor" in bl, "profile floor concept must be named"

    # (b) YMYL floor 1500 (Principle-2) cited as the binding case.
    assert "1500" in body
    assert "principle" in bl and "ymyl" in bl

    # (c) Canonical floor source + resolution mechanism cited (no re-stated
    #     divergent numbers — single source of truth).
    assert "content-quality.md" in body
    assert "profile_aware_defaults" in body

    # (d) R-08 SERP analysis OVERRIDES the TIVL/clamp entirely.
    assert "R-08" in body
    assert "override" in bl

    # (e) A worked example shows the clamp actually binding (b2b-saas floor
    #     1800 lifts every TIVL base; or YMYL 1500 lifts the T=1200 base).
    assert ("max(1200, 1500)" in body) or ("1800" in body), (
        "worked example must demonstrate the floor binding above a TIVL base"
    )
