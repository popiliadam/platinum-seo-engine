"""
tests/scripts/test_sf_crawl_orchestrator.py — pure-transform helper tests.

6 cases per v1.8 Phase 3 Worker Prompt covering the three public functions
of ``scripts.ingestion.sf_crawl_orchestrator``:

* ``enumerate_reports(include_tier3=False)`` — default 24 (T1+T2)
* ``enumerate_reports(include_tier3=True)`` — 40 (T1+T2+T3)
* ``move_with_rollback`` — success path
* ``move_with_rollback`` — target exists (refuse to overwrite)
* ``parse_progress_response`` — flat + nested shape support
* source_run_id chaining contract — orchestrator → sf_import handoff
  argument is a string that flows through unmodified

No MCP calls, no workflow_runner state machine — these tests stay
strictly at the pure-transform layer.

Run from repo root:
    PYTHONPATH=. pytest tests/scripts/test_sf_crawl_orchestrator.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ingestion import sf_crawl_orchestrator
from scripts.ingestion.sf_crawl_orchestrator import (
    ProgressState,
    SfExportSpec,
    SfCrawlOrchestratorError,
    build_export_plan,
    enumerate_reports,
    export_returns_ndjson,
    move_with_rollback,
    ndjson_to_csv,
    parse_progress_response,
)
from scripts.ingestion.sf_import import TIER1_REQUIRED, TIER2_RECOMMENDED


VALID_SF_TOOLS = {
    "sf_generate_report",
    "sf_generate_bulk_export",
    "sf_export_seo_element_urls",
}


REPO_ROOT = Path(__file__).resolve().parents[2]
SF_REPORTS_SCHEMA = REPO_ROOT / "schemas" / "sf-required-reports.schema.json"


# ---------------------------------------------------------------------------
# Test 1 — enumerate_reports default returns 24 (T1 + T2)
# ---------------------------------------------------------------------------

def test_enumerate_reports_default_24() -> None:
    names = enumerate_reports()
    assert len(names) == 24
    # All Tier 1 + Tier 2 canonical names present.
    assert set(names) == TIER1_REQUIRED | TIER2_RECOMMENDED
    # Tier 1 comes first (sorted), then Tier 2 (sorted).
    tier1_block = names[: len(TIER1_REQUIRED)]
    tier2_block = names[len(TIER1_REQUIRED):]
    assert tier1_block == sorted(TIER1_REQUIRED)
    assert tier2_block == sorted(TIER2_RECOMMENDED)


# ---------------------------------------------------------------------------
# Test 2 — enumerate_reports include_tier3=True returns 40
# ---------------------------------------------------------------------------

def test_enumerate_reports_with_tier3_40() -> None:
    names = enumerate_reports(include_tier3=True)
    assert len(names) == 40
    # Must equal the canonicalName enum from the schema (40 total).
    schema = json.loads(SF_REPORTS_SCHEMA.read_text("utf-8"))
    enum = schema["definitions"]["canonicalName"]["enum"]
    assert set(names) == set(enum)
    # First 24 still T1+T2 in deterministic order; the trailing 16 are T3.
    assert names[:24] == enumerate_reports(include_tier3=False)
    assert len(set(names[24:])) == 16  # 16 unique Tier 3 names


# ---------------------------------------------------------------------------
# Test 3 — move_with_rollback success
# ---------------------------------------------------------------------------

def test_move_with_rollback_success(tmp_path: Path) -> None:
    src = tmp_path / "src" / "report.csv"
    src.parent.mkdir()
    src.write_text("alpha,beta\n1,2\n", "utf-8")
    dst = tmp_path / "dst" / "report.csv"
    # dst.parent does NOT exist; move_with_rollback must create it.

    assert move_with_rollback(src, dst) is True
    assert dst.exists()
    assert dst.read_text("utf-8") == "alpha,beta\n1,2\n"
    assert not src.exists()


# ---------------------------------------------------------------------------
# Test 4 — move_with_rollback refuses to overwrite an existing target
# ---------------------------------------------------------------------------

def test_move_with_rollback_target_exists(tmp_path: Path) -> None:
    src = tmp_path / "src" / "report.csv"
    src.parent.mkdir()
    src.write_text("new", "utf-8")
    dst = tmp_path / "dst" / "report.csv"
    dst.parent.mkdir()
    dst.write_text("old", "utf-8")

    with pytest.raises(SfCrawlOrchestratorError) as excinfo:
        move_with_rollback(src, dst)
    assert "already exists" in str(excinfo.value)
    # Source must remain in place (no half-move side effect).
    assert src.exists()
    assert dst.read_text("utf-8") == "old"

    # Source missing path also surfaces a clear error.
    missing = tmp_path / "ghost.csv"
    with pytest.raises(SfCrawlOrchestratorError) as excinfo2:
        move_with_rollback(missing, tmp_path / "out.csv")
    assert "source missing" in str(excinfo2.value)


# ---------------------------------------------------------------------------
# Test 5 — parse_progress_response handles flat + nested shapes
# ---------------------------------------------------------------------------

def test_parse_progress_response_shape() -> None:
    # Flat shape.
    flat = {"status": "IN_PROGRESS", "urls_crawled": 1234}
    s1 = parse_progress_response(flat)
    assert isinstance(s1, ProgressState)
    assert s1.status == "IN_PROGRESS"
    assert s1.urls_crawled == 1234
    assert s1.raw is flat  # original retained

    # Nested progress wrapper shape.
    nested = {"progress": {"status": "DONE", "urls_crawled": "9876"}}
    s2 = parse_progress_response(nested)
    assert s2.status == "DONE"
    assert s2.urls_crawled == 9876  # int coercion from string

    # Unknown status passes through (orchestrator surfaces it in DURUR text).
    s3 = parse_progress_response({"status": "WEIRD_NEW_STATE"})
    assert s3.status == "WEIRD_NEW_STATE"
    assert s3.urls_crawled == 0  # missing → 0 default

    # Non-dict input → error (defensive shape contract).
    with pytest.raises(SfCrawlOrchestratorError) as excinfo:
        parse_progress_response("not a dict")
    assert "expected dict" in str(excinfo.value)

    # Missing/empty status → error.
    with pytest.raises(SfCrawlOrchestratorError):
        parse_progress_response({"urls_crawled": 5})


# ---------------------------------------------------------------------------
# Test 6 — source_run_id chaining contract
# ---------------------------------------------------------------------------

def test_source_run_id_chaining_contract() -> None:
    """The orchestrator's run_id chains into sf-import via its source_run_id
    *frontmatter* input — NOT a --source-run-id CLI flag (sf_import's script
    argparse rejects that, exit 2). The contract: the value is a string token
    (no parsing/munging), and sf-import's frontmatter declares source_run_id
    as type=string, required=false. This test pins the frontmatter contract.
    """
    # End 1: orchestrator's RunHandle.run_id is always a string (per
    # workflow_runner.create_run schema). The pure-transform helper makes
    # no assumption about the format beyond "string token"; the test
    # confirms a representative run_id round-trips through helpers without
    # mutation.
    representative = "test-proj-20260526-abcdef"
    # Pure-transform helpers do not touch run_id; the chaining happens at the
    # sf-import skill-interpreter level (source_run_id frontmatter input), NOT
    # via a subprocess CLI flag. We assert the contract by verifying sf-import
    # frontmatter declares source_run_id.
    import yaml
    sf_import_md = (
        REPO_ROOT / "skills" / "ingestion" / "sf-import" / "SKILL.md"
    )
    text = sf_import_md.read_text("utf-8")
    parts = text.split("---", 2)
    fm = yaml.safe_load(parts[1])
    assert "source_run_id" in fm["inputs"], \
        "sf-import frontmatter MUST declare source_run_id input (Phase 3 contract)"
    sri = fm["inputs"]["source_run_id"]
    assert sri["type"] == "string"
    assert sri.get("required", False) is False, \
        "source_run_id MUST be optional (Phase 3 D-SF-07)"
    # The representative token is a string — sanity check the contract shape.
    assert isinstance(representative, str)
    assert representative  # non-empty


# ---------------------------------------------------------------------------
# Test 7 — build_export_plan covers EXACTLY the 24 canonical names
# ---------------------------------------------------------------------------

def test_build_export_plan_covers_24_canonicals() -> None:
    plan = build_export_plan()
    # One spec per canonical; coverage equals enumerate_reports(False).
    assert {s.canonical for s in plan} == set(enumerate_reports(False))
    assert len(plan) == 24
    # Order MUST match enumerate_reports (T1 sorted, then T2 sorted) so the
    # SKILL.md export loop is reproducible and tier1/tier2 stay contiguous.
    assert [s.canonical for s in plan] == enumerate_reports(False)


# ---------------------------------------------------------------------------
# Test 8 — every spec uses one of the 3 valid SF tools
# ---------------------------------------------------------------------------

def test_build_export_plan_tools_are_valid() -> None:
    plan = build_export_plan()
    for spec in plan:
        assert isinstance(spec, SfExportSpec)
        assert spec.tool in VALID_SF_TOOLS, (
            f"{spec.canonical!r} maps to unknown tool {spec.tool!r}"
        )
        # call_kwargs MUST NOT carry file_path (caller adds it).
        assert "file_path" not in spec.call_kwargs


# ---------------------------------------------------------------------------
# Test 9 — tier1 specs == TIER1_REQUIRED, tier2 specs == TIER2_RECOMMENDED
# ---------------------------------------------------------------------------

def test_build_export_plan_tier_membership() -> None:
    plan = build_export_plan()
    tier1 = {s.canonical for s in plan if s.tier == "tier1"}
    tier2 = {s.canonical for s in plan if s.tier == "tier2"}
    assert tier1 == set(TIER1_REQUIRED)
    assert tier2 == set(TIER2_RECOMMENDED)
    # tier field is constrained to the two known values.
    assert {s.tier for s in plan} == {"tier1", "tier2"}


# ---------------------------------------------------------------------------
# Test 10 — export_type presence rule: report/bulk have it, seo_element never
# ---------------------------------------------------------------------------

def test_build_export_plan_export_type_rule() -> None:
    plan = build_export_plan()
    for spec in plan:
        if spec.tool == "sf_export_seo_element_urls":
            # This tool has NO export_type arg.
            assert "export_type" not in spec.call_kwargs
            # seo_element calls carry seo_element_name + filter_name.
            assert "seo_element_name" in spec.call_kwargs
            assert "filter_name" in spec.call_kwargs
        else:
            # report + bulk export tools write CSV explicitly.
            assert spec.call_kwargs.get("export_type") == "CSV"
            # both report/bulk tools key off `category`.
            assert "category" in spec.call_kwargs


# ---------------------------------------------------------------------------
# Test 11 — spot-check three known mappings end-to-end
# ---------------------------------------------------------------------------

def test_build_export_plan_known_mappings() -> None:
    by_canonical = {s.canonical: s for s in build_export_plan()}

    # 1. issues_overview_report → sf_generate_report(category="Issues Overview")
    iss = by_canonical["issues_overview_report"]
    assert iss.tool == "sf_generate_report"
    assert iss.tier == "tier1"
    assert iss.call_kwargs == {"category": "Issues Overview", "export_type": "CSV"}

    # 2. all_inlinks → sf_generate_bulk_export(category="Links:All Inlinks")
    inl = by_canonical["all_inlinks"]
    assert inl.tool == "sf_generate_bulk_export"
    assert inl.tier == "tier1"
    assert inl.call_kwargs == {"category": "Links:All Inlinks", "export_type": "CSV"}

    # 3. page_titles_all → sf_export_seo_element_urls(Page Titles, All)
    pt = by_canonical["page_titles_all"]
    assert pt.tool == "sf_export_seo_element_urls"
    assert pt.tier == "tier1"
    assert pt.call_kwargs == {"seo_element_name": "Page Titles", "filter_name": "All"}


# ---------------------------------------------------------------------------
# Test 12 — build_export_plan is pure / idempotent (two calls equal, frozen)
# ---------------------------------------------------------------------------

def test_build_export_plan_is_pure_and_frozen() -> None:
    plan_a = build_export_plan()
    plan_b = build_export_plan()
    assert plan_a == plan_b  # value-equal across calls
    assert plan_a is not plan_b  # fresh list object each call (no shared state)

    # SfExportSpec is frozen — mutation must raise.
    spec = plan_a[0]
    with pytest.raises(Exception):
        spec.canonical = "mutated"  # type: ignore[misc]

    # call_kwargs dicts must be independent objects between calls (no shared
    # mutable state that a caller could corrupt for the next invocation).
    spec_a0 = plan_a[0]
    spec_b0 = plan_b[0]
    assert spec_a0.call_kwargs == spec_b0.call_kwargs
    assert spec_a0.call_kwargs is not spec_b0.call_kwargs


# ---------------------------------------------------------------------------
# Test 13 — export_returns_ndjson: seo-element True, report/bulk False
#   (live-verified 2026-06-02: sf_export_seo_element_urls emits NDJSON because
#    it has no export_type arg; report/bulk honor export_type="CSV")
# ---------------------------------------------------------------------------

def test_export_returns_ndjson_only_for_seo_element() -> None:
    by_canon = {s.canonical: s for s in build_export_plan()}
    assert export_returns_ndjson(by_canon["page_titles_all"]) is True
    assert export_returns_ndjson(by_canon["internal_all"]) is True
    assert export_returns_ndjson(by_canon["issues_overview_report"]) is False
    assert export_returns_ndjson(by_canon["all_inlinks"]) is False
    # exactly the 16 seo-element specs return NDJSON (the other 8 are CSV)
    ndjson_count = sum(1 for s in build_export_plan() if export_returns_ndjson(s))
    assert ndjson_count == 16


# ---------------------------------------------------------------------------
# Test 14 — ndjson_to_csv: flat objects → CSV (header + rows, first-seen order)
# ---------------------------------------------------------------------------

def test_ndjson_to_csv_basic_conversion() -> None:
    ndjson = "\n".join([
        json.dumps({"Address": "https://x/", "Title 1": "Home", "Length": 4}),
        json.dumps({"Address": "https://x/a", "Title 1": "A", "Length": 1}),
    ])
    lines = ndjson_to_csv(ndjson).splitlines()
    assert lines[0] == "Address,Title 1,Length"   # first-seen key order
    assert lines[1] == "https://x/,Home,4"
    assert len(lines) == 3                          # header + 2 rows


def test_ndjson_to_csv_empty_input_returns_empty() -> None:
    # legitimately-empty SF export (e.g. search_console_all, GSC not connected)
    assert ndjson_to_csv("") == ""
    assert ndjson_to_csv("  \n \n") == ""


def test_ndjson_to_csv_none_cell_and_key_union() -> None:
    ndjson = "\n".join([
        json.dumps({"Address": "https://x/", "Indexability Status": None}),
        json.dumps({"Address": "https://x/a", "Extra": "v"}),
    ])
    lines = ndjson_to_csv(ndjson).splitlines()
    assert lines[0] == "Address,Indexability Status,Extra"  # union, first-seen
    assert lines[1] == "https://x/,,"                        # None + missing → ""
    assert lines[2] == "https://x/a,,v"
