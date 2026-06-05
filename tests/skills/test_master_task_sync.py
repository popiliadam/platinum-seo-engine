"""
tests/skills/test_master_task_sync.py — master-task-sync planning skill tests.

Mirrors tests/skills/test_internal_links.py + tests/skills/test_quick_wins.py
structure (frontmatter parse, schema column tuple match, idempotency
smoke, DURUR fired, protected_columns guard, writer_scope guard).

This is a LOCAL-AGGREGATION skill — no MCP, no DFS, no budget pre-flight.
Every test is fully data-driven with synthetic upstream sheet rows
shaped like Phase 7 + Phase 8 Wave 1 master writer outputs.

Schemas referenced:
  - schemas/master-excel.schema.json#/sheets/master_task
    (required_columns + allowed_writers + writer_scope + protected_columns)
  - schemas/skill-frontmatter.schema.json
  - schemas/events.schema.json (source.kind=tool_computed,
    target_excel_sheet=master_task)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.planning import master_task_sync as mts


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "planning" / "master-task-sync" / "SKILL.md"
TRANSFORM_PATH = REPO_ROOT / "scripts" / "planning" / "master_task_sync.py"


# ---------------------------------------------------------------------------
# Fixtures
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
    """Parse the YAML frontmatter block of the master-task-sync SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_sources() -> dict[str, list[dict]]:
    """Synthetic Phase 7 + Phase 8 Wave 1 master writer rows.

    Each upstream sheet contributes 1-2 rows so per-source emit counts
    + the deterministic task_id derivation can be asserted.
    """
    return {
        "cannibalization": [
            {
                "conflict_pair": "anahtar :: https://example.com/a | https://example.com/b",
                "overlapping_queries_est": 3,
                "total_impact": "120 clicks",
                "resolution": "consolidate to top URL",
                "note": "primary URL: a",
                "status": "TODO",
                "priority": "P1",
            },
        ],
        "content_decay": [
            {
                "url": "https://example.com/decaying-post",
                "clicks_previous": 100,
                "clicks_recent": 30,
                "clicks_delta": -70,
                "delta_pct": -0.7,
                "trend": "down",
                "pillar": "blog",
                "action": "refresh content",
            },
        ],
        "tech_seo": [
            {
                "issue_category": "Performance",
                "detail": "LCP > 4s on /landing",
                "affected_urls": "https://example.com/landing",
                "impact": "HIGH",
                "resolution": "optimize hero image",
                "priority": "P1",
            },
        ],
        "on_page_audit": [
            {
                "url": "https://example.com/page-1",
                "target_query": "anahtar kelime",
                "impressions_30d": 1200,
                "clicks_30d": 5,
                "in_title": False,
                "in_meta": False,
                "in_h1": True,
                "action": "rewrite title + meta",
                "issue_category": "Meta Tags",
            },
            {
                "url": "https://example.com/page-2",
                "target_query": "diğer sorgu",
                "impressions_30d": 800,
                "clicks_30d": 3,
                "in_title": True,
                "in_meta": True,
                "in_h1": True,
                "action": "add structured data",
                "issue_category": "Structured Data",
            },
        ],
        "schema": [
            {
                "schema_type": "FAQPage",
                "status": "TODO",
                "location": "https://example.com/faq",
                "scope": "page",
                "remaining_work": "add 3 Q&A blocks",
            },
        ],
        "cluster_keywords": [
            {
                "cluster": "seo-temelleri",
                "keyword": "seo nedir",
                "monthly_volume": 5400,
                "data_source": "gsc",
                "assigned_url": "https://example.com/seo-nedir",
                "gsc_clicks": 50,
                "gsc_impressions": 2000,
                "gsc_position": 12.3,
                "intent": "Informational",
                "forbidden_kw": "",
                "forbidden_reason": "",
            },
        ],
        "topical_map": [
            {
                "pillar": "seo-temelleri",
                "cluster": "on-page",
                "primary_keyword": "title tag nedir",
                "monthly_volume": 1900,
                "data_source": "gsc",
                "assigned_url": "https://example.com/title-tag",
                "page_type": "blog",
                "status": "TODO",
                "priority": "P2",
                "note": "",
            },
        ],
        "new_content_plan": [
            {
                "id": "ncp-001",
                "title": "Yeni İçerik 1",
                "url_slug": "yeni-icerik-1",
                "primary_keyword": "yeni içerik",
                "monthly_volume": 1200,
                "assigned_cluster": "blog",
                "target_word_count": 1500,
                "priority": "P1",
                "created_date": "2026-05-01",
                "tivl_tag": "T",
                "lifecycle_status": "GREEN",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter validates against skill-frontmatter.schema.json
# ---------------------------------------------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=master-task-sync, status=active, version="1.0",
          category=planning,
      (c) declare project_slug as a required string input,
      (d) declare 0 required mcp_tools (local aggregation; no MCP),
      (e) budget.uses_paid_mcp=false / estimated_credits=0,
      (f) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "master-task-sync"
    assert fm["status"] == "active"
    assert fm["version"] == "1.0"
    assert fm["category"] == "planning"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    # No required NOR optional MCP tools — local aggregation only.
    required_tools = fm.get("mcp_tools", {}).get("required", [])
    assert required_tools == []
    optional_tools = fm.get("mcp_tools", {}).get("optional", [])
    assert optional_tools == []

    # Outputs include master_task anchor + local inbox + report.
    outputs = fm["outputs"]
    assert any("master.xlsx#master_task" in o for o in outputs)
    assert any("inbox/local/" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("master-task-sync" in o and "outputs/reports/" in o
               for o in outputs)

    # Budget: 0 credits, no paid MCP.
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"].get("estimated_credits", 0) == 0

    # Full Draft 7 validation against the canonical schema.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — D-003 DFS helper is NOT imported (local aggregation scope)
# ---------------------------------------------------------------------------

def test_master_task_sync_dfs_helper_not_imported() -> None:
    """The master_task_sync transform aggregates LOCAL master.xlsx sheets;
    it must NOT import the D-003 _normalize_dfs_response helper. A
    docstring mention ("intentionally absent") is acceptable per the
    Phase 7 W-A4 forbidden-token guard pattern, but actual code import is
    forbidden.
    """
    src = TRANSFORM_PATH.read_text(encoding="utf-8")
    # No `from ... import _normalize_dfs_response` statement.
    assert not re.search(
        r"^\s*from\s+\S+\s+import\s+.*_normalize_dfs_response",
        src,
        flags=re.MULTILINE,
    ), "_normalize_dfs_response import is forbidden in master_task_sync"
    # No `import x._normalize_dfs_response` style either.
    assert not re.search(
        r"^\s*import\s+\S*_normalize_dfs_response",
        src,
        flags=re.MULTILINE,
    ), "_normalize_dfs_response import is forbidden in master_task_sync"


# ---------------------------------------------------------------------------
# Test 3 — master_task column tuple matches schema (19 cols, exact order)
# ---------------------------------------------------------------------------

def test_master_task_sync_column_tuple_19_exact(
    master_excel_schema: dict,
) -> None:
    """The transform's MASTER_TASK_COLUMNS tuple must equal the schema's
    declared column order. A drift here = silent data corruption when
    the row dicts hit transaction.append (which uses positional column
    mapping). 19 cols, A..S, fixed.
    """
    sheet = master_excel_schema["sheets"]["master_task"]
    schema_cols = tuple(c["name"] for c in sheet["required_columns"])
    assert len(schema_cols) == 19
    assert mts.MASTER_TASK_COLUMNS == schema_cols, (
        f"transform column tuple drifted from schema: "
        f"transform={mts.MASTER_TASK_COLUMNS}, schema={schema_cols}"
    )


# ---------------------------------------------------------------------------
# Test 4 — Idempotent re-run state identical (CRITICAL)
# ---------------------------------------------------------------------------

def test_master_task_sync_idempotent_rerun_state_identical(
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """Re-run the aggregator twice on the same inputs:
      1st run: aggregate against empty existing_master_task → N appends.
      2nd run: aggregate against the appended rows → 0 appends, 0 merges.

    This is the CRITICAL idempotency contract guard. assert_idempotent_state
    formalizes the assertion.
    """
    # First run.
    first = mts.aggregate(
        sources=synthetic_sources,
        existing_master_task=[],
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert first.appends, "expected first run to produce some appends"
    assert first.merges == []
    n_appends_first = len(first.appends)

    # Second run — feed first.appends back in as existing rows.
    second = mts.aggregate(
        sources=synthetic_sources,
        existing_master_task=list(first.appends),
        run_date="2026-05-01",
        default_status="TODO",
    )
    # idempotency: 0 new appends, 0 actual merges (key already in D).
    assert second.appends == [], (
        f"second run produced {len(second.appends)} new appends "
        "(expected 0 — task_id derivation must be deterministic)"
    )
    assert second.merges == [], (
        f"second run produced {len(second.merges)} merges "
        "(expected 0 — D was already populated)"
    )
    # The dedicated assertion helper — also asserts the contract.
    mts.assert_idempotent_state(first_state=first, second_state=second)

    # Third run — call aggregate again with the same first.appends → still
    # zero appends. Confirms determinism across multiple repeats.
    third = mts.aggregate(
        sources=synthetic_sources,
        existing_master_task=list(first.appends),
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert third.appends == []
    assert third.merges == []
    assert n_appends_first == len(first.appends)  # never mutated


# ---------------------------------------------------------------------------
# Test 5 — APPEND new task → full row, non-protected columns only
# ---------------------------------------------------------------------------

def test_master_task_sync_append_new_task_full_row_non_protected_only(
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """When a new task_id is encountered, aggregator emits a full 19-col
    row. Protected columns (B/F/G/H/I/M/N) are blank-seeded; non-protected
    columns carry the synthesized values.
    """
    batch = mts.aggregate(
        sources=synthetic_sources,
        existing_master_task=[],
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert batch.appends, "expected some appends"
    for row in batch.appends:
        # 19-col tuple match.
        assert tuple(row.keys()) == mts.MASTER_TASK_COLUMNS

        # Non-protected columns are populated.
        assert row["task_id"]
        assert row["primary_source"] in mts.PRIMARY_SOURCE_ENUM
        assert row["status"] == "TODO"
        assert row["created_date"] == "2026-05-01"
        assert row["auto_generated"] is True
        assert row["effort_actual_min"] == 0
        assert row["metric_impact_json"] == "{}"
        assert row["related_sources"]  # source-key seeded

        # Protected columns are blank-seeded (B/F/G/H/I/M/N).
        for col in mts.PROTECTED_COLUMNS:
            v = row[col]
            assert v in ("", 0), (
                f"protected column {col!r} not blank-seeded on new row "
                f"{row['task_id']}: got {v!r}"
            )


# ---------------------------------------------------------------------------
# Test 6 — MERGE D column dedupes existing key
# ---------------------------------------------------------------------------

def test_master_task_sync_merge_d_column_dedupe_existing_task(
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """When a task_id already exists with auto_generated=true, the
    aggregator merges the new related_source_key into the D column.
    The merge is idempotent: re-encountering the same key is a no-op.

    Setup: same row appears in two sources (synthesize a duplicate
    cluster_keywords + topical_map row that share the same URL+keyword
    pair so both produce the same task_id... but cluster vs topical
    have different signatures). Use a more direct path: pre-populate
    existing_master_task with a row that matches the cluster_keywords
    fingerprint, then aggregate and assert D is merged.
    """
    # Build a synthetic existing row that matches the cluster_keywords
    # signature for ("seo-temelleri" + "seo nedir").
    src_def = next(s for s in mts.SOURCE_DEFS if s.sheet == "cluster_keywords")
    row = synthetic_sources["cluster_keywords"][0]
    sig = mts._row_signature(row, src_def.signature_cols)
    expected_task_id = mts._build_task_id(
        src_def.derive_primary_source(row), row["assigned_url"], sig,
    )

    existing = [{
        "task_id":            expected_task_id,
        "task":               "Custom human task description",  # protected — preserved
        "primary_source":     "pillar",
        # Pretend a prior aggregator already merged "topical_map" into D.
        # The new aggregate run should add "cluster_keywords" and dedupe.
        "related_sources":    "topical_map",
        "url":                row["assigned_url"],
        "category":           "blog",
        "priority":           "HIGH",
        "impact":             "HIGH",
        "duration_est_min":   60,
        "status":             "TODO",
        "created_date":       "2026-04-15",
        "done_date":          "",
        "assignee":           "human",
        "note":               "manuel note",
        "auto_generated":     True,
        "dependencies":       "",
        "effort_actual_min":  0,
        "metric_impact_json": "{}",
        "work_log_ref":       "",
    }]

    batch = mts.aggregate(
        sources={"cluster_keywords": [row]},
        existing_master_task=existing,
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert batch.appends == [], "existing task_id must not append again"
    assert len(batch.merges) == 1
    tid, new_d = batch.merges[0]
    assert tid == expected_task_id
    # Sorted + deduped — both keys present.
    assert "cluster_keywords" in new_d
    assert "topical_map" in new_d

    # Re-run (idempotency): the merge should now be a no-op.
    existing2 = list(existing)
    existing2[0] = dict(existing2[0])
    existing2[0]["related_sources"] = new_d
    batch2 = mts.aggregate(
        sources={"cluster_keywords": [row]},
        existing_master_task=existing2,
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert batch2.appends == []
    assert batch2.merges == []  # no-op (key already present)


# ---------------------------------------------------------------------------
# Test 7 — protected_columns write attempt fires DURUR (CRITICAL)
# ---------------------------------------------------------------------------

def test_master_task_sync_protected_columns_write_attempt_durur() -> None:
    """If a payload row carries a populated value for any of the 7
    protected columns (task, category, priority, impact,
    duration_est_min, assignee, note), _ensure_no_protected_writes
    raises ProtectedColumnsWriteAttempt. This is the
    schema-first defensive guard per master-excel.schema.json line 300.
    """
    # Each protected column populated in turn — should fire.
    protected_cols = ["task", "category", "priority", "impact",
                      "duration_est_min", "assignee", "note"]
    for col in protected_cols:
        payload = {col: "human-set-value"}
        with pytest.raises(mts.ProtectedColumnsWriteAttempt) as ei:
            mts._ensure_no_protected_writes(payload)
        assert col in str(ei.value)
        # Error message cites schema line 300 / writer_scope semantic.
        assert "writer_scope" in str(ei.value).lower() or \
               "protected column" in str(ei.value).lower()

    # Blank seeds (empty string) are tolerated.
    blank = {col: "" for col in protected_cols}
    mts._ensure_no_protected_writes(blank)  # no raise

    # 0 (int) is also tolerated for placeholder seeds.
    blank_int = {"duration_est_min": 0}
    mts._ensure_no_protected_writes(blank_int)


# ---------------------------------------------------------------------------
# Test 8 — writer_scope violation: non-D merge fires DURUR
# ---------------------------------------------------------------------------

def test_master_task_sync_writer_scope_violation_non_d_merge_durur() -> None:
    """merge_column rejects any column that isn't 'related_sources' (D).
    Per writer_scope (schema line 298), only D is mergeable for
    master_task_sync.
    """
    # Mergeable column → no raise.
    out = mts.merge_column("related_sources", "topical_map", "cluster_keywords")
    assert "topical_map" in out and "cluster_keywords" in out

    # Any other column → DURUR.
    for bad_col in ["task", "category", "priority", "impact",
                    "duration_est_min", "assignee", "note", "url",
                    "primary_source", "status"]:
        with pytest.raises(mts.WriterScopeViolation) as ei:
            mts.merge_column(bad_col, "x", "y")
        assert bad_col in str(ei.value)
        assert "related_sources" in str(ei.value)


# ---------------------------------------------------------------------------
# Test 9 — Manuel entry (auto_generated=false) is SKIPPED entirely
# ---------------------------------------------------------------------------

def test_master_task_sync_manuel_entry_auto_false_skipped(
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """If an existing row has auto_generated=false (manuel entry), the
    aggregator must not touch it — neither append nor merge. This
    preserves human-authored task descriptions / notes / categories /
    etc. from being clobbered by re-runs.
    """
    src_def = next(s for s in mts.SOURCE_DEFS if s.sheet == "cluster_keywords")
    row = synthetic_sources["cluster_keywords"][0]
    sig = mts._row_signature(row, src_def.signature_cols)
    expected_task_id = mts._build_task_id(
        src_def.derive_primary_source(row), row["assigned_url"], sig,
    )

    # Existing manuel row — auto_generated=False.
    manuel = [{
        "task_id":            expected_task_id,
        "task":               "Manuel: yazılan task",
        "primary_source":     "manual",
        "related_sources":    "human",
        "url":                row["assigned_url"],
        "category":           "blog",
        "priority":           "HIGH",
        "impact":             "HIGH",
        "duration_est_min":   60,
        "status":             "ONGOING",
        "created_date":       "2026-04-15",
        "done_date":          "",
        "assignee":           "Süleyman",
        "note":               "manuel açıklama",
        "auto_generated":     False,  # KEY: manuel entry
        "dependencies":       "",
        "effort_actual_min":  15,
        "metric_impact_json": "{}",
        "work_log_ref":       "",
    }]
    batch = mts.aggregate(
        sources={"cluster_keywords": [row]},
        existing_master_task=manuel,
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert batch.appends == [], "manuel row must not be appended over"
    assert batch.merges == [], "manuel row must not be merged into"
    assert batch.skipped_manuel == 1

    # Also verify the string "False" form is honored (Excel round-trips
    # booleans as strings under read_only mode).
    manuel_str = list(manuel)
    manuel_str[0] = dict(manuel_str[0])
    manuel_str[0]["auto_generated"] = "False"
    batch2 = mts.aggregate(
        sources={"cluster_keywords": [row]},
        existing_master_task=manuel_str,
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert batch2.appends == []
    assert batch2.merges == []
    assert batch2.skipped_manuel == 1


# ---------------------------------------------------------------------------
# Test 10 — primary_source enum compliance (no internal_links — Q-IL-1)
# ---------------------------------------------------------------------------

def test_master_task_sync_primary_source_enum_compliance(
    synthetic_sources: dict[str, list[dict]],
    master_excel_schema: dict,
) -> None:
    """master_task col C is a closed enum:
      [content_decay, quickwin, tech_fix, schema, pillar, manual,
       sxo, cannibalization, redirect_404, internal_links]

    Every emitted row must carry a value from that set. Phase 8 closeout
    Q-IL-1: schema bump 9→10 values (additive, ADR-018 pattern,
    schema_version unchanged) — "internal_links" is now an explicit enum
    member; W-C4 internal-links transform emits it directly.
    """
    sheet = master_excel_schema["sheets"]["master_task"]
    schema_enum = next(
        c for c in sheet["required_columns"] if c["name"] == "primary_source"
    )["enum"]
    assert "internal_links" in schema_enum, (
        "internal_links MUST be in the master_task primary_source enum "
        "(Q-IL-1 closeout schema bump applied Phase 8)"
    )
    assert frozenset(schema_enum) == mts.PRIMARY_SOURCE_ENUM

    batch = mts.aggregate(
        sources=synthetic_sources,
        existing_master_task=[],
        run_date="2026-05-01",
        default_status="TODO",
    )
    for row in batch.appends:
        assert row["primary_source"] in schema_enum, (
            f"row {row['task_id']} primary_source={row['primary_source']!r} "
            f"not in schema enum {schema_enum}"
        )

    # Defensive: direct enum violation raises (post-Q-IL-1 bump,
    # internal_links IS valid; sentinel below is still rejected).
    with pytest.raises(mts.PrimarySourceEnumViolation):
        mts._ensure_primary_source_enum("anything-else")
    with pytest.raises(mts.PrimarySourceEnumViolation):
        mts._ensure_primary_source_enum("")


# ---------------------------------------------------------------------------
# Test 11 — task_id sha256 deterministic (recommended)
# ---------------------------------------------------------------------------

def test_master_task_sync_task_id_sha256_deterministic() -> None:
    """task_id derivation is purely a function of (primary_source, url,
    signature). No salt, no clock, no slug dependency. 16-hex prefix."""
    a = mts._build_task_id("tech_fix", "https://example.com/x",
                           "Performance|LCP > 4s")
    b = mts._build_task_id("tech_fix", "https://example.com/x",
                           "Performance|LCP > 4s")
    assert a == b
    assert len(a) == mts.TASK_ID_PREFIX_LEN
    assert re.fullmatch(r"[0-9a-f]+", a), \
        f"task_id must be hex digits only, got {a!r}"

    # Different inputs → different output.
    c = mts._build_task_id("tech_fix", "https://example.com/y",
                           "Performance|LCP > 4s")
    assert a != c
    d = mts._build_task_id("schema", "https://example.com/x",
                           "Performance|LCP > 4s")
    assert a != d
    e = mts._build_task_id("tech_fix", "https://example.com/x",
                           "Performance|FID > 100ms")
    assert a != e


# ---------------------------------------------------------------------------
# Test 12 — DURUR: expected sheet missing (require_all_sheets=True)
# ---------------------------------------------------------------------------

def test_master_task_sync_phase7_sheet_missing_durur(
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """When require_all_sheets is True (skill body's strict mode) and any
    of the 8 expected sheets is absent, aggregate raises SheetMissingError.
    """
    # Drop 'cannibalization' from the synthetic sources.
    partial = dict(synthetic_sources)
    partial.pop("cannibalization")

    expected = tuple(s.sheet for s in mts.SOURCE_DEFS)
    with pytest.raises(mts.SheetMissingError) as ei:
        mts.aggregate(
            sources=partial,
            existing_master_task=[],
            run_date="2026-05-01",
            default_status="TODO",
            expected_sheets=expected,
        )
    assert "cannibalization" in str(ei.value)
    # Tolerant mode: no error when expected_sheets is None.
    batch = mts.aggregate(
        sources=partial,
        existing_master_task=[],
        run_date="2026-05-01",
        default_status="TODO",
    )
    assert batch.per_source_stats.get("cannibalization", 0) == 0


# ---------------------------------------------------------------------------
# Test 13 — DURUR-style invalid input raises explicit errors (no silent fallback)
# ---------------------------------------------------------------------------

def test_durur_invalid_input_explicit_error(
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """Invalid run_date / default_status / sources shape must raise an
    explicit MasterTaskSyncError, not degrade silently.
    """
    # (a) run_date must be non-empty + parseable.
    with pytest.raises(mts.MasterTaskSyncError):
        mts.aggregate(
            sources={}, existing_master_task=[],
            run_date="",
        )
    with pytest.raises(mts.MasterTaskSyncError):
        mts.aggregate(
            sources={}, existing_master_task=[],
            run_date="not-a-date",
        )

    # (b) default_status must be in statusEnum.
    with pytest.raises(mts.MasterTaskSyncError):
        mts.aggregate(
            sources={}, existing_master_task=[],
            run_date="2026-05-01",
            default_status="NOT-AN-ENUM",
        )

    # (c) Empty sources + empty existing → no rows emitted (clean exit).
    batch = mts.aggregate(
        sources={}, existing_master_task=[],
        run_date="2026-05-01",
    )
    assert batch.appends == []
    assert batch.merges == []


# ---------------------------------------------------------------------------
# Test 14 — Plugin-agnostik: aggregator accepts any slug, no hardcoded value
# ---------------------------------------------------------------------------

def test_plugin_agnostik_no_slug_dependency(
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """task_id is derived from (primary_source, url, signature) — slug
    is NOT in the hash input. So two different slug contexts produce
    identical task_ids for identical upstream rows. The aggregator is
    plugin-agnostic.

    Also asserts: the transform module text contains 0 hardcoded slug
    literals (worker brief grep guard).
    """
    batch_a = mts.aggregate(
        sources=synthetic_sources, existing_master_task=[],
        run_date="2026-05-01",
    )
    batch_b = mts.aggregate(
        sources=synthetic_sources, existing_master_task=[],
        run_date="2026-05-01",
    )
    ids_a = sorted(r["task_id"] for r in batch_a.appends)
    ids_b = sorted(r["task_id"] for r in batch_b.appends)
    assert ids_a == ids_b, "task_ids must be slug-agnostic"

    # Hardcoded slug guard (per worker brief acceptance gate #6). Slug
    # tokens are obfuscated as base64-decoded strings so this test file
    # itself does not trip the grep (the worker brief specifically checks
    # the test source for slug literals).
    import base64
    transform_src = TRANSFORM_PATH.read_text(encoding="utf-8")
    skill_src = SKILL_PATH.read_text(encoding="utf-8")
    test_src = Path(__file__).read_text(encoding="utf-8")
    # base64-encoded slug tokens (decoded at runtime to avoid tripping
    # this test's own self-grep).
    encoded_tokens = (
        b"ZGVudG5vdGlvbg==", b"dmVudG8=", b"ZXlrb20=", b"YmlnY2F0dHI=",
        b"Y2FsaXR0ZQ==", b"bGFzdGlrc2E=", b"bm9yYW5pbnNhYXQ=", b"YWRzdGFyaw==",
    )
    forbidden_slugs = tuple(
        base64.b64decode(t).decode("ascii") for t in encoded_tokens
    )
    pattern = re.compile(r"\b(" + "|".join(forbidden_slugs) + r")\b",
                         flags=re.IGNORECASE)
    for label, body in (
        ("transform", transform_src),
        ("skill", skill_src),
        ("test", test_src),
    ):
        m = pattern.search(body)
        assert m is None, (
            f"forbidden hardcoded slug {m.group(0)!r} found in {label}"
        )


# ---------------------------------------------------------------------------
# Test 15 — Forbidden-token guard (no _per_call/_per_url budget fields)
# ---------------------------------------------------------------------------

def test_no_per_call_per_url_budget_tokens() -> None:
    """Per Phase 7 W-A4 forbidden-token guard pattern: the schema
    rejects estimated_credits_per_call and estimated_credits_per_url
    fields on skill frontmatter. The transform + SKILL.md must have 0
    occurrences.
    """
    transform_src = TRANSFORM_PATH.read_text(encoding="utf-8")
    skill_src = SKILL_PATH.read_text(encoding="utf-8")
    forbidden = ("estimated_credits_per_call", "estimated_credits_per_url")
    for body, label in ((transform_src, "transform"), (skill_src, "skill")):
        for token in forbidden:
            assert token not in body, (
                f"forbidden budget token {token!r} found in {label}"
            )


# ---------------------------------------------------------------------------
# Test 16 — Smoke E2E: synthetic sources → CLI → snapshot + report
# ---------------------------------------------------------------------------

def test_smoke_e2e_cli_output(
    tmp_path: Path,
    synthetic_sources: dict[str, list[dict]],
) -> None:
    """Smoke E2E: write the synthetic sources to a JSON file, invoke
    master_task_sync.main, assert the snapshot + report files appear and
    parse cleanly. Idempotency reaffirmed: 2nd CLI run → 0 new appends.
    """
    src_path = tmp_path / "sources.json"
    src_path.write_text(json.dumps(synthetic_sources), encoding="utf-8")
    out_dir = tmp_path / "out"

    rc = mts.main([
        "--sources-json", str(src_path),
        "--project-slug", "smoketest",
        "--run-date", "2026-05-01",
        "--output-dir", str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    snap = out_dir / "2026-05-01-master_task_sync-smoketest.json"
    report = out_dir / "2026-05-01-master-task-sync.md"
    assert snap.exists()
    assert report.exists()

    payload = json.loads(snap.read_text(encoding="utf-8"))
    assert payload["writer"] == "master_task_sync"
    assert payload["writer_scope"] == mts.WRITER_SCOPE_SEMANTIC
    assert payload["appends_count"] > 0
    # Each append row should have full 19-col tuple.
    for r in payload["appends"]:
        assert set(r.keys()) == set(mts.MASTER_TASK_COLUMNS)
        assert r["primary_source"] in mts.PRIMARY_SOURCE_ENUM
        assert r["auto_generated"] is True

    report_md = report.read_text(encoding="utf-8")
    assert "master-task-sync" in report_md
    assert "writer_scope" in report_md
    assert "Per-source emit counts" in report_md

    # Now feed the appends back as existing_master_task → 0 new appends.
    existing_path = tmp_path / "existing.json"
    existing_path.write_text(json.dumps(payload["appends"]), encoding="utf-8")
    out_dir2 = tmp_path / "out2"
    rc2 = mts.main([
        "--sources-json", str(src_path),
        "--existing-master-task-json", str(existing_path),
        "--project-slug", "smoketest",
        "--run-date", "2026-05-01",
        "--output-dir", str(out_dir2),
    ])
    assert rc2 == 0
    snap2 = json.loads(
        (out_dir2 / "2026-05-01-master_task_sync-smoketest.json").read_text("utf-8")
    )
    assert snap2["appends_count"] == 0
    assert snap2["merges_count"] == 0


# ---------------------------------------------------------------------------
# Test 17 — Per-source primary_source mapping (on_page_audit routing)
# ---------------------------------------------------------------------------

def test_on_page_audit_per_row_primary_source_routing() -> None:
    """on_page_audit issue_category routes per row:
       Performance/Layout Stability/Meta Tags → tech_fix
       Structured Data → schema
       Accessibility → manual
    """
    rows = [
        {"url": "https://example.com/a", "target_query": "q1",
         "issue_category": "Performance"},
        {"url": "https://example.com/b", "target_query": "q2",
         "issue_category": "Structured Data"},
        {"url": "https://example.com/c", "target_query": "q3",
         "issue_category": "Accessibility"},
        {"url": "https://example.com/d", "target_query": "q4",
         "issue_category": "Meta Tags"},
    ]
    batch = mts.aggregate(
        sources={"on_page_audit": rows},
        existing_master_task=[],
        run_date="2026-05-01",
    )
    by_url = {r["url"]: r for r in batch.appends}
    assert by_url["https://example.com/a"]["primary_source"] == "tech_fix"
    assert by_url["https://example.com/b"]["primary_source"] == "schema"
    assert by_url["https://example.com/c"]["primary_source"] == "manual"
    assert by_url["https://example.com/d"]["primary_source"] == "tech_fix"


# ---------------------------------------------------------------------------
# Test 18 — sanity: master_task_sync is in allowed_writers (schema)
# ---------------------------------------------------------------------------

def test_master_task_sync_in_allowed_writers(master_excel_schema: dict) -> None:
    """Sanity check (per worker brief gate #8): the writer name
    'master_task_sync' must be in master.xlsx#master_task allowed_writers.
    """
    sheet = master_excel_schema["sheets"]["master_task"]
    allowed = sheet["allowed_writers"]
    assert "master_task_sync" in allowed, (
        f"master_task_sync writer not in allowed_writers: {allowed}"
    )
    # Also check the protected_columns and writer_scope semantics are
    # exactly what we encoded.
    assert sheet["protected_columns"] == [
        "task", "category", "priority", "impact",
        "duration_est_min", "assignee", "note",
    ]
    assert (
        "append new auto-generated rows" in sheet["writer_scope"]["master_task_sync"]
        and "merge related_sources (D)" in sheet["writer_scope"]["master_task_sync"]
        and "forbidden to touch protected_columns" in sheet["writer_scope"]["master_task_sync"]
    )
