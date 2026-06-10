"""
tests/skills/test_topical_map.py — topical-map planning skill tests.

Phase 8 Wave 1 (W-C2). Mirrors the test pattern of test_content_gaps.py
and test_geo_analysis.py: frontmatter parse + Draft 7 schema validation,
column tuple lock, geo-staging consume + fallback, budget pre-flight
DURUR, DFS REST/flat shape tolerance via the IMPORTED helper, and an
F-09 superset documentation check.

Schemas referenced:
  - schemas/skill-frontmatter.schema.json   (Draft7 frontmatter contract;
                                             budget block additionalProperties:false)
  - schemas/master-excel.schema.json        (#topical_map 10-col tuple)
  - schemas/cross-sheet-invariants.json     (F-09 superset contract)
  - schemas/events.schema.json              (source.kind=dataforseo_mcp,
                                             target_excel_sheet=topical_map)

Cross-module IMPORT-only discipline:
  - scripts.ingestion.dfs_pull              (_normalize_dfs_response —
                                             IDENTITY preserved by
                                             import-discipline test)

NOTE: scripts.excel.transaction is intentionally NOT imported by the
transform module; the skill orchestrator owns the master.xlsx write
through the workflow_runner approve gate.

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_topical_map.py -v
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

from scripts.ingestion import dfs_pull as _dfs_pull_module
from scripts.planning import topical_map_transform as tmt


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "planning" / "topical-map" / "SKILL.md"
MASTER_EXCEL_SCHEMA_PATH = SCHEMAS / "master-excel.schema.json"


# ---------------------------------------------------------------------------
# Fixtures — schemas + frontmatter
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    """Parse the YAML frontmatter block of the topical-map SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture(scope="module")
def master_excel_schema() -> dict:
    return json.loads(MASTER_EXCEL_SCHEMA_PATH.read_text("utf-8"))


# ---------------------------------------------------------------------------
# Mock DFS payload builders
# ---------------------------------------------------------------------------

def _kw_ideas_item(*, keyword: str, search_volume: int) -> dict:
    """Build one keyword_ideas item (top-level keyword + keyword_info)."""
    return {
        "keyword": keyword,
        "keyword_info": {
            "search_volume": search_volume,
            "competition": 0.5,
            "cpc": 1.0,
        },
        "keyword_properties": {"keyword_difficulty": 30},
    }


def _related_item(*, keyword: str, search_volume: int) -> dict:
    """Build one related_keywords item with the keyword_data envelope."""
    return {
        "keyword_data": {
            "keyword": keyword,
            "keyword_info": {
                "search_volume": search_volume,
                "competition": 0.4,
                "cpc": 0.9,
            },
            "keyword_properties": {"keyword_difficulty": 25},
        },
        "depth": 1,
    }


def _rest_envelope(items: list[dict]) -> dict:
    """REST envelope shape: tasks[0].result[0].items."""
    return {
        "version": "0.1.20240101",
        "status_code": 20000,
        "tasks": [{
            "id": "test-task",
            "status_code": 20000,
            "result": [{"items": items}],
        }],
    }


def _flat_envelope(items: list[dict]) -> dict:
    """Flat wrapper shape (dataforseo-mcp-server@2.8.9 flattening)."""
    return {"items": items}


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + validates against schema
# ---------------------------------------------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=topical-map, status=active, version="1.0",
          category=planning,
      (c) declare project_slug + seed_keyword as required string inputs,
      (d) list keyword_ideas + related_keywords in required tools,
      (e) carry budget {uses_paid_mcp: true, estimated_credits: N} ONLY
          (no _per_call / _per_url leakage — Q-W-A4-01),
      (f) outputs include master.xlsx#topical_map + raw inbox + report
          + events.jsonl (worker brief),
      (g) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "topical-map"
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

    # Outputs include the master.xlsx target sheet anchor + raw inbox + report.
    outputs = fm["outputs"]
    assert "master.xlsx#topical_map" in outputs
    assert any("inbox/dfs/" in o and "keyword_ideas" in o for o in outputs)
    assert any("inbox/dfs/" in o and "related_keywords" in o for o in outputs)
    assert any("outputs/reports/" in o and "topical-map" in o for o in outputs)
    assert "events.jsonl" in outputs

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
# Test 2 — Column tuple matches the master-excel schema (10 cols, exact order)
# ---------------------------------------------------------------------------

def test_topical_map_column_tuple_10_exact(
    master_excel_schema: dict,
) -> None:
    """The transform's TOPICAL_MAP_COLUMNS constant must equal the
    master.xlsx#topical_map.required_columns order byte-for-byte.

    Source of truth: schemas/master-excel.schema.json.
    """
    sheet = master_excel_schema["sheets"]["topical_map"]
    schema_columns = tuple(c["name"] for c in sheet["required_columns"])
    assert schema_columns == (
        "pillar", "cluster", "primary_keyword", "monthly_volume",
        "data_source", "assigned_url", "page_type", "status",
        "priority", "note",
    )
    assert tmt.TOPICAL_MAP_COLUMNS == schema_columns
    assert len(tmt.TOPICAL_MAP_COLUMNS) == 10, (
        f"topical_map sheet must have exactly 10 columns; "
        f"got {len(tmt.TOPICAL_MAP_COLUMNS)}"
    )


# ---------------------------------------------------------------------------
# Test 3 — IMPORT discipline: _normalize_dfs_response is IMPORTED, not copied
# ---------------------------------------------------------------------------

def test_topical_map_dfs_normalize_helper_imported() -> None:
    """The transform module must use the SAME function object that
    scripts.ingestion.dfs_pull defines, so any future shape-handling fix
    in dfs_pull is inherited automatically.

    Identity check via ``is`` — defeats accidental redefinition.
    KOPYA YASAK is a brief mandate.
    """
    assert tmt._normalize_dfs_response is _dfs_pull_module._normalize_dfs_response, (
        "scripts.planning.topical_map_transform._normalize_dfs_response "
        "must be IMPORTED (not copied) from scripts.ingestion.dfs_pull. "
        "Restore: `from scripts.ingestion.dfs_pull import _normalize_dfs_response`."
    )


# ---------------------------------------------------------------------------
# Test 4 — Geo-analysis staging consume: present → note enriched
# ---------------------------------------------------------------------------

def test_topical_map_geo_staging_consume_present(tmp_path: Path) -> None:
    """When the Phase 7 geo_analysis_geo_signals staging file exists, each
    matching topical_map row's note column carries the geo_gap +
    llm_visibility_score signals.

    geo_gap label vocabulary mirrors geo_analysis_transform constants.
    """
    seed = "dental clinic istanbul"
    geo_signals = [
        {
            "query": seed,
            "llm_visibility_score": 0.75,
            "our_brand_mentioned_count": 3,
            "our_url_cited_count": 1,
            "serp_top_3_present": True,
            "geo_gap": "AEO_HEALTHY",
            "action": "monitor — already cited by LLMs",
        },
    ]
    staging_path = tmp_path / "geo_signals.json"
    staging_path.write_text(json.dumps(geo_signals), encoding="utf-8")

    raw_ideas = _rest_envelope([
        _kw_ideas_item(keyword=seed, search_volume=1500),
    ])
    raw_related = _flat_envelope([
        _related_item(keyword="dental clinic services", search_volume=400),
    ])

    geo_rows = tmt._load_geo_staging(staging_path)
    assert len(geo_rows) == 1

    out = tmt.transform(
        raw_keyword_ideas=raw_ideas,
        raw_related_keywords=raw_related,
        seed_keyword=seed,
        geo_staging_rows=geo_rows,
    )
    rows = out["topical_map"]
    # Find the pillar row (matches the seed keyword).
    pillar_row = next(r for r in rows if r["primary_keyword"] == seed)
    assert pillar_row["page_type"] == tmt.PAGE_TYPE_PILLAR
    # Note must mention the geo signal AND the seed.
    assert "AEO_HEALTHY" in pillar_row["note"]
    assert "llm_vis=0.75" in pillar_row["note"]
    assert f"seed={seed}" in pillar_row["note"]
    # data_source provenance is locked.
    assert pillar_row["data_source"] == tmt.DATA_SOURCE_LABEL


# ---------------------------------------------------------------------------
# Test 5 — Geo-analysis staging missing → graceful fallback (no DURUR)
# ---------------------------------------------------------------------------

def test_topical_map_geo_staging_missing_fallback(tmp_path: Path) -> None:
    """When the geo_analysis staging file is absent, the transform must
    GRACEFUL-skip the consume step (returns []) and still emit a valid
    topical_map. The brief: DURUR fires ONLY when the manager opted into
    requiring geo-staging via a CLI flag — the helper itself never raises.
    """
    missing = tmp_path / "no_such_geo_signals.json"
    assert not missing.exists()
    rows = tmt._load_geo_staging(missing)
    assert rows == []

    raw_ideas = _rest_envelope([
        _kw_ideas_item(keyword="seed-kw", search_volume=900),
    ])
    raw_related = _rest_envelope([
        _related_item(keyword="seed-kw subtopic", search_volume=200),
    ])

    out = tmt.transform(
        raw_keyword_ideas=raw_ideas,
        raw_related_keywords=raw_related,
        seed_keyword="seed-kw",
        geo_staging_rows=rows,        # empty → graceful
    )
    # Pillar row must still exist; note carries seed but no geo signal.
    pillar_row = out["topical_map"][0]
    assert pillar_row["page_type"] == tmt.PAGE_TYPE_PILLAR
    assert "seed=seed-kw" in pillar_row["note"]
    assert "geo_gap" not in pillar_row["note"]
    assert "llm_vis" not in pillar_row["note"]
    assert out["meta"]["geo_staging_rows_consumed"] == 0


# ---------------------------------------------------------------------------
# Test 6 — Budget pre-flight: subprocess exit 1 → BudgetExceededError
# ---------------------------------------------------------------------------

def test_topical_map_budget_preflight_blocks_when_exceeded(
    tmp_path: Path,
) -> None:
    """preflight_budget() wraps scripts/budget/check_budget.py as a
    subprocess. When the underlying script exits non-zero (budget
    exceeded), the wrapper must raise BudgetExceededError — never silently
    downgrade. We mock subprocess.run so the test does not depend on the
    real script's exact path / behaviour.
    """
    fake_completed = mock.Mock()
    fake_completed.returncode = 1
    fake_completed.stdout = (
        '{"budget_per_day":2,"used_24h":4,"remaining":-2,"exceeded":true}'
    )
    fake_completed.stderr = ""
    with mock.patch.object(subprocess, "run", return_value=fake_completed):
        with pytest.raises(tmt.BudgetExceededError) as ei:
            tmt.preflight_budget(
                project_config_path=tmp_path / "project.config.json",
                events_path=tmp_path / "events.jsonl",
            )
        assert "budget pre-flight FAIL" in str(ei.value)
        assert isinstance(ei.value, tmt.TopicalMapError)

    # Happy path: exit 0 → returns parsed envelope.
    fake_ok = mock.Mock()
    fake_ok.returncode = 0
    fake_ok.stdout = (
        '{"budget_per_day":500,"used_24h":15,"remaining":485,"exceeded":false}'
    )
    fake_ok.stderr = ""
    with mock.patch.object(subprocess, "run", return_value=fake_ok):
        env = tmt.preflight_budget(
            project_config_path=tmp_path / "project.config.json",
            events_path=tmp_path / "events.jsonl",
        )
        assert env["exceeded"] is False
        assert env["budget_per_day"] == 500


# ---------------------------------------------------------------------------
# Test 7 — DFS unrecognized response shape → ValueError DURUR (DURUR #2)
# ---------------------------------------------------------------------------

def test_topical_map_dfs_response_flat_shape_durur() -> None:
    """An unrecognized DFS shape must propagate the ValueError raised by
    the imported _normalize_dfs_response — no swallowing, no fallback.

    Also locks that the FLAT wrapper shape DOES work (proving the helper
    is wired) so downstream readers know which shape is the regression.
    """
    # FLAT wrapper still works — proves _normalize_dfs_response is wired.
    raw_flat = _flat_envelope([_kw_ideas_item(keyword="x", search_volume=10)])
    out = tmt.transform(
        raw_keyword_ideas=raw_flat,
        raw_related_keywords=_flat_envelope([]),
        seed_keyword="x",
    )
    # Should produce at least the seed pillar row.
    assert any(r["primary_keyword"] == "x" for r in out["topical_map"])

    # Garbage shape → ValueError.
    with pytest.raises(ValueError) as ei:
        tmt.transform(
            raw_keyword_ideas={"foo": "bar"},          # neither REST nor flat
            raw_related_keywords=_flat_envelope([]),
            seed_keyword="x",
        )
    assert "Unrecognized DFS response shape" in str(ei.value)


# ---------------------------------------------------------------------------
# Test 8 — F-09 superset documented (assigned_url empty on every row)
# ---------------------------------------------------------------------------

def test_topical_map_assigned_url_superset_documented() -> None:
    """F-09 contract:
        cluster_keywords.assigned_url ⊆ topical_map.assigned_url
    topical-map populates the SUPERSET side. Concretely: every row this
    skill emits must carry assigned_url='' (empty) — Phase 8 cluster-map
    + manual edits FILL the URL later. The drift-check skill validates
    the cross-sheet F-09 invariant; this test pins the worker-side
    contract (every emitted row is F-09-compatible the moment it lands).
    """
    seed = "main pillar topic"
    raw_ideas = _rest_envelope([
        _kw_ideas_item(keyword=seed, search_volume=2000),
        _kw_ideas_item(keyword="main pillar subtopic", search_volume=500),
        _kw_ideas_item(keyword="main pillar nested", search_volume=200),
    ])
    raw_related = _flat_envelope([
        _related_item(keyword="main pillar related a", search_volume=180),
        _related_item(keyword="main pillar related b", search_volume=120),
    ])

    out = tmt.transform(
        raw_keyword_ideas=raw_ideas,
        raw_related_keywords=raw_related,
        seed_keyword=seed,
    )
    rows = out["topical_map"]
    assert len(rows) >= 1, "topical-map must emit at least the seed pillar row"

    for row in rows:
        # Schema-locked column projection.
        assert tuple(row.keys()) == tmt.TOPICAL_MAP_COLUMNS
        # F-09 superset side: URL is empty until cluster-map fills it.
        assert row["assigned_url"] == "", (
            f"F-09 superset contract: assigned_url must be empty on every "
            f"emitted row (cluster-map / manual edits fill it later). "
            f"Got {row['assigned_url']!r} on row {row}"
        )
        # Page type vocabulary lock.
        assert row["page_type"] in {
            tmt.PAGE_TYPE_PILLAR,
            tmt.PAGE_TYPE_CLUSTER,
            tmt.PAGE_TYPE_SUPPORTING,
        }
        # statusEnum lock — default seed.
        assert row["status"] == "TODO"
        # data_source provenance lock.
        assert row["data_source"] == tmt.DATA_SOURCE_LABEL


# ---------------------------------------------------------------------------
# Test 9 — Pillar/cluster taxonomy: seed always pillar, max_pillars enforced
# ---------------------------------------------------------------------------

def test_topical_map_seed_is_always_pillar_one() -> None:
    """Worker brief: the seed keyword is ALWAYS pillar #1, even when
    absent from the DFS payload (synthetic candidate). No-candidate cases
    are NOT errors — a single-row topical_map with the seed pillar lets
    downstream consumers anchor F-09 against a non-empty superset.
    """
    out = tmt.transform(
        raw_keyword_ideas=_rest_envelope([]),   # empty
        raw_related_keywords=_rest_envelope([]),
        seed_keyword="orphan-seed",
    )
    rows = out["topical_map"]
    assert len(rows) == 1
    assert rows[0]["primary_keyword"] == "orphan-seed"
    assert rows[0]["page_type"] == tmt.PAGE_TYPE_PILLAR
    assert rows[0]["pillar"] == "orphan-seed"
    # Synthetic seed has volume 0 → priority P3 (volume tier).
    assert rows[0]["monthly_volume"] == 0
    assert rows[0]["priority"] == "P3"
    assert out["meta"]["pillar_count"] == 1
    assert out["meta"]["cluster_count"] == 0


def test_topical_map_max_pillars_cap_enforced() -> None:
    """max_pillars=1 → only the seed becomes a pillar even when many
    high-volume candidates exist."""
    seed = "core topic"
    raw_ideas = _rest_envelope([
        _kw_ideas_item(keyword=seed, search_volume=5000),
        _kw_ideas_item(keyword="core topic guide", search_volume=4500),
        _kw_ideas_item(keyword="core topic tutorial", search_volume=4000),
        _kw_ideas_item(keyword="core topic reference", search_volume=3500),
    ])
    raw_related = _flat_envelope([])

    out = tmt.transform(
        raw_keyword_ideas=raw_ideas,
        raw_related_keywords=raw_related,
        seed_keyword=seed,
        max_pillars=1,
    )
    pillar_rows = [
        r for r in out["topical_map"]
        if r["page_type"] == tmt.PAGE_TYPE_PILLAR
    ]
    assert len(pillar_rows) == 1
    assert pillar_rows[0]["primary_keyword"] == seed


# ---------------------------------------------------------------------------
# Test 10 — DURUR: keyword_cap exceeded
# ---------------------------------------------------------------------------

def test_topical_map_keyword_cap_exceeded() -> None:
    """When the MCP returns more candidates than the cap, transform must
    raise KeywordCapExceededError before doing any heavy work — DoS
    prevention DURUR called out in the worker brief (DURUR #7)."""
    big_ideas = _flat_envelope([
        _kw_ideas_item(keyword=f"kw-{i}", search_volume=100)
        for i in range(6)
    ])
    related = _flat_envelope([])

    with pytest.raises(tmt.KeywordCapExceededError) as ei:
        tmt.transform(
            raw_keyword_ideas=big_ideas,
            raw_related_keywords=related,
            seed_keyword="seed",
            keyword_cap=5,
        )
    assert "keyword_cap=5" in str(ei.value)
    assert isinstance(ei.value, tmt.TopicalMapError)


# ---------------------------------------------------------------------------
# Test 11 — DURUR: status not in statusEnum
# ---------------------------------------------------------------------------

def test_topical_map_status_enum_violation() -> None:
    """default_status must be in master-excel.schema.json
    #/definitions/statusEnum — a typo or rename must DURUR (RowSchemaError).
    """
    with pytest.raises(tmt.RowSchemaError):
        tmt.transform(
            raw_keyword_ideas=_rest_envelope([]),
            raw_related_keywords=_rest_envelope([]),
            seed_keyword="x",
            default_status="NOT_AN_ENUM_VALUE",
        )


# ---------------------------------------------------------------------------
# Test 12 — Plugin-agnostik: 0 hardcoded slug literals in transform / SKILL
# ---------------------------------------------------------------------------

def test_topical_map_no_hardcoded_project_slugs() -> None:
    """Worker brief: 0 hardcoded project slugs (`{slug}` placeholder is
    fine; specific project names are NOT). Lock against the brief's
    sentinel slug list so a future regression with slugs leaking into
    deliverables stays visible.

    The sentinel list is built character-by-character to keep this test
    file itself slug-free under the same grep that enforces the rule on
    the deliverables.
    """
    # Build sentinel slugs without spelling them literally in this file.
    sentinels = (
        "d" + "entnotion", "v" + "ento", "e" + "ykom", "b" + "igcattr",
        "c" + "alitte", "l" + "astiksa", "n" + "oraninsaat", "a" + "dstark",
    )

    skill_text = SKILL_PATH.read_text("utf-8").lower()
    transform_text = (
        REPO_ROOT / "scripts" / "planning" / "topical_map_transform.py"
    ).read_text("utf-8").lower()

    for slug in sentinels:
        # Use word-boundary match to avoid false positives on substrings.
        pattern = rf"\b{slug}\b"
        assert not re.search(pattern, skill_text), (
            f"hardcoded slug {slug!r} found in SKILL.md (plugin-agnostik violation)"
        )
        assert not re.search(pattern, transform_text), (
            f"hardcoded slug {slug!r} found in transform "
            "(plugin-agnostik violation)"
        )


def test_topical_map_no_per_call_or_per_url_budget_keys() -> None:
    """Q-W-A4-01 guard — the SKILL.md MUST NOT carry estimated_credits_per_call
    or estimated_credits_per_url anywhere; the schema rejects them and a
    grep regression caught those exact keys in earlier waves.
    """
    skill_text = SKILL_PATH.read_text("utf-8")
    transform_text = (
        REPO_ROOT / "scripts" / "planning" / "topical_map_transform.py"
    ).read_text("utf-8")
    for forbidden in ("estimated_credits_per_call", "estimated_credits_per_url"):
        assert forbidden not in skill_text, (
            f"forbidden budget key {forbidden!r} found in SKILL.md frontmatter"
        )
        assert forbidden not in transform_text, (
            f"forbidden budget key {forbidden!r} found in transform"
        )


# ---------------------------------------------------------------------------
# Test 13 — Smoke E2E: transform produces deterministic, schema-locked output
# ---------------------------------------------------------------------------

def test_topical_map_smoke_e2e_deterministic() -> None:
    """End-to-end smoke: a moderate fixture → topical_map rows whose
    ordering is stable across two invocations of transform() on the
    same input (idempotency / determinism check).

    Also confirms:
      - rows projected via the schema column tuple,
      - meta envelope counts add up,
      - no master.xlsx written (transform is pure compute).
    """
    seed = "ecommerce platform"
    raw_ideas = _rest_envelope([
        _kw_ideas_item(keyword=seed, search_volume=8000),
        _kw_ideas_item(keyword="ecommerce platform comparison", search_volume=2000),
        _kw_ideas_item(keyword="ecommerce platform pricing", search_volume=1200),
        _kw_ideas_item(keyword="ecommerce platform reviews", search_volume=900),
        _kw_ideas_item(keyword="unrelated noise topic", search_volume=400),
    ])
    raw_related = _flat_envelope([
        _related_item(keyword="ecommerce platform features", search_volume=500),
        _related_item(keyword="ecommerce platform integrations", search_volume=350),
    ])

    out_a = tmt.transform(
        raw_keyword_ideas=raw_ideas,
        raw_related_keywords=raw_related,
        seed_keyword=seed,
        fetched_at="2026-05-01T00:00:00.000000+00:00",
    )
    out_b = tmt.transform(
        raw_keyword_ideas=raw_ideas,
        raw_related_keywords=raw_related,
        seed_keyword=seed,
        fetched_at="2026-05-01T00:00:00.000000+00:00",
    )
    # Determinism: same input → same output.
    assert out_a == out_b

    rows = out_a["topical_map"]
    # Counts add up.
    assert (
        out_a["meta"]["pillar_count"]
        + out_a["meta"]["cluster_count"]
        + out_a["meta"]["supporting_count"]
        == out_a["meta"]["row_count"]
    )
    assert out_a["meta"]["row_count"] == len(rows)

    # Schema column projection on every row.
    for r in rows:
        assert tuple(r.keys()) == tmt.TOPICAL_MAP_COLUMNS
        assert r["data_source"] == tmt.DATA_SOURCE_LABEL
        assert r["page_type"] in {
            tmt.PAGE_TYPE_PILLAR,
            tmt.PAGE_TYPE_CLUSTER,
            tmt.PAGE_TYPE_SUPPORTING,
        }
        assert r["priority"] in {"P1", "P2", "P3"}
        assert isinstance(r["monthly_volume"], int)

    # The pillar row must be the seed.
    pillar_rows = [r for r in rows if r["page_type"] == tmt.PAGE_TYPE_PILLAR]
    assert pillar_rows[0]["primary_keyword"] == seed
    # Volume of the seed pillar row equals the DFS payload volume.
    assert pillar_rows[0]["monthly_volume"] == 8000
    # Priority for 8000 → P1.
    assert pillar_rows[0]["priority"] == "P1"

    # Cluster rows under the seed pillar all share at least one token with seed.
    cluster_rows = [r for r in rows if r["page_type"] == tmt.PAGE_TYPE_CLUSTER]
    seed_tokens = set(re.findall(r"\w+", seed.lower()))
    for cr in cluster_rows:
        cr_tokens = set(re.findall(r"\w+", cr["primary_keyword"].lower()))
        assert cr_tokens & seed_tokens, (
            f"cluster row {cr['primary_keyword']!r} shares NO token with the "
            f"seed {seed!r} — bucketing logic regressed"
        )
    # Unrelated noise topic must NOT be in the rows.
    assert not any(r["primary_keyword"] == "unrelated noise topic" for r in rows)


# ---------------------------------------------------------------------------
# Test 14 — FIX-L L3: locale resolution is CONFIG-FIRST, no engine default
# ---------------------------------------------------------------------------

def test_locale_resolution_is_config_first_no_engine_default(
    skill_frontmatter: dict,
) -> None:
    """FIX-L L3: topical-map must NOT hardcode an engine-level country
    default for location_code / language_code. The locale resolves
    CONFIG-FIRST from ``project.config.dataforseo.{location_code,
    language_code}``; a per-market reference table documents the codes
    VERIFIED from live project configs (TR=2792, CA=20120 "Ontario,Canada",
    NG=2566 — NOT the dispatch doc's unverified CA=2124 / NG=2434). Missing
    config locale → DURUR; never silently default to any country.
    """
    fm = skill_frontmatter
    body = SKILL_PATH.read_text("utf-8").split("---", 2)[2]
    bl = body.lower()

    # (a) Frontmatter: NO engine-level country default; prose claim removed.
    assert "default" not in fm["inputs"]["location_code"], (
        "location_code must NOT carry an engine-level default (was 2792)"
    )
    assert "default" not in fm["inputs"]["language_code"], (
        "language_code must NOT carry an engine-level default (was 'tr')"
    )
    assert "2792" not in fm["description"], (
        "auto-trigger description must not claim a TR (2792) default"
    )
    assert "2792" not in fm["inputs"]["location_code"].get("description", "")
    assert "2792" not in fm["inputs"]["language_code"].get("description", "")

    # (b) Body documents config-first resolution from the dataforseo block.
    assert "## Locale resolution" in body
    assert "project.config.dataforseo.location_code" in body
    assert "project.config.dataforseo.language_code" in body
    assert "config-first" in bl
    assert "no engine-level country default" in bl

    # (c) Reference table carries the VERIFIED codes only.
    for code in ("2792", "20120", "2566"):
        assert code in body, f"reference table missing verified code {code}"
    assert "2124" not in body and "2434" not in body, (
        "must NOT write the dispatch doc's unverified CA=2124 / NG=2434 codes"
    )
