"""
tests/skills/test_internal_links.py — internal-links planning skill tests.

Mirrors tests/skills/test_cannibalization.py + tests/skills/test_sf_import.py
structure (frontmatter parse, URL idempotency, transform unit, schema
column tuple match, DURUR fired, smoke E2E with synthetic SF CSV
fixtures). MCP tools are NOT Python-callable inside pytest; the skill
reads SF CSVs from disk, so all transform-layer behaviour is fully
testable here without mocking any MCP surface.

Schemas referenced:
  - schemas/master-excel.schema.json (master_task required_columns +
    statusEnum + severityEnum + primary_source enum)
  - schemas/skill-frontmatter.schema.json
  - schemas/events.schema.json (source.kind=sf_csv,
    target_excel_sheet=master_task)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.planning import internal_links_transform as ilt


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "planning" / "internal-links" / "SKILL.md"


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
    """Parse the YAML frontmatter block of the internal-links SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_internal_all_csv(tmp_path: Path) -> Path:
    """internal_all.csv with 4 URLs:
       /home (200, 12 inlinks)         — healthy
       /orphan-page (200, 0 inlinks)   — orphan target
       /old-page (301, 0 inlinks)      — redirect, ignored as orphan
       /broken-page (404, 0 inlinks)   — broken, ignored as orphan
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    p = raw_dir / "internal_all.csv"
    p.write_text(
        "Address,Status Code,Indexability,Inlinks\n"
        "https://example.com/home,200,Indexable,12\n"
        "https://example.com/orphan-page,200,Indexable,0\n"
        "https://example.com/old-page,301,Non-Indexable,0\n"
        "https://example.com/broken-page,404,Non-Indexable,0\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def synthetic_inlinks_csv(tmp_path: Path) -> Path:
    """all_inlinks.csv with edges that exercise broken / redirect /
    anchor-diversity detection. Designed alongside synthetic_internal_all
    so the same raw_dir picks up both files.

    Edges:
      home → home (self-link, ignored for orphan inbound count)
      home → about (200, anchor "About") — healthy
      home → contact (200, anchor "Contact") — healthy
      home → broken-page (404)            — broken (1 inbound)
      blog → broken-page (404)            — broken (2nd inbound to same dest)
      home → server-fail (500)            — broken CRITICAL
      home → old-page (301)               — redirect
      blog → old-page (301)               — redirect (2nd inbound)
      anchor-magnet × 6 inbound, all anchor "click here" — anchor-diversity flag

    Anchor-diversity destination needs >=5 inbounds with single distinct
    anchor.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    p = raw_dir / "all_inlinks.csv"
    rows = [
        "Source,Destination,Status Code,Anchor,Type,Follow,Link Position",
        "https://example.com/home,https://example.com/home,200,Home,Hyperlink,true,Navigation",
        "https://example.com/home,https://example.com/about,200,About,Hyperlink,true,Navigation",
        "https://example.com/home,https://example.com/contact,200,Contact,Hyperlink,true,Footer",
        "https://example.com/home,https://example.com/broken-page,404,Broken Link,Hyperlink,true,Content",
        "https://example.com/blog,https://example.com/broken-page,404,Click Here,Hyperlink,true,Content",
        "https://example.com/home,https://example.com/server-fail,500,Server Issue,Hyperlink,true,Content",
        "https://example.com/home,https://example.com/old-page,301,Old Page,Hyperlink,true,Sidebar",
        "https://example.com/blog,https://example.com/old-page,301,Old Page,Hyperlink,true,Sidebar",
        # 6 inbounds to anchor-magnet, all same anchor
        "https://example.com/p1,https://example.com/anchor-magnet,200,click here,Hyperlink,true,Content",
        "https://example.com/p2,https://example.com/anchor-magnet,200,click here,Hyperlink,true,Content",
        "https://example.com/p3,https://example.com/anchor-magnet,200,click here,Hyperlink,true,Content",
        "https://example.com/p4,https://example.com/anchor-magnet,200,click here,Hyperlink,true,Content",
        "https://example.com/p5,https://example.com/anchor-magnet,200,click here,Hyperlink,true,Content",
        "https://example.com/p6,https://example.com/anchor-magnet,200,click here,Hyperlink,true,Content",
    ]
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def loaded_sf_data(
    synthetic_internal_all_csv: Path,
    synthetic_inlinks_csv: Path,
) -> tuple[list[dict], list[dict]]:
    """Load both synthetic CSVs as DictReader-shaped row dicts."""
    raw_dir = synthetic_internal_all_csv.parent
    internal, inlinks, _outlinks = ilt.load_sf_csvs(raw_dir)
    assert internal is not None and inlinks is not None
    return internal, inlinks


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter validates against skill-frontmatter.schema.json
# ---------------------------------------------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=internal-links, status=wip, version="1.0",
          category=planning,
      (c) declare project_slug as a required string input,
      (d) declare 0 required mcp_tools (SF CSV path), and DFS as optional,
      (e) budget.uses_paid_mcp=false / estimated_credits=0,
      (f) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "internal-links"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "planning"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    # No required MCP tools — SF CSV path. DFS is optional.
    required_tools = fm.get("mcp_tools", {}).get("required", [])
    assert required_tools == []
    optional_tools = fm.get("mcp_tools", {}).get("optional", [])
    assert "mcp__dataforseo__on_page_content_parsing" in optional_tools

    # Outputs include master_task anchor + raw inbox + report.
    outputs = fm["outputs"]
    assert any("master.xlsx#master_task" in o for o in outputs)
    assert any("inbox/sf/" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("outputs/reports/" in o and "internal-links" in o for o in outputs)

    # Budget: 0 credits, no paid MCP (default flow).
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
# Test 2 — SF data missing fires DURUR (SFDataMissingError)
# ---------------------------------------------------------------------------

def test_internal_links_sf_data_missing_durur(tmp_path: Path) -> None:
    """DURUR #1: raw_dir missing → SFDataMissingError, NOT silent empty."""
    nonexistent = tmp_path / "nope" / "raw"
    with pytest.raises(ilt.SFDataMissingError) as ei:
        ilt.load_sf_csvs(nonexistent)
    assert "sf-exports raw_dir not found" in str(ei.value)
    # Hint to run sf-import first (per the worker brief / SKILL.md DURUR #1).
    assert "sf-import" in str(ei.value)

    # Empty raw_dir (exists but no CSVs) also fires the DURUR.
    empty_raw = tmp_path / "empty" / "raw"
    empty_raw.mkdir(parents=True)
    with pytest.raises(ilt.SFDataMissingError) as ei2:
        ilt.load_sf_csvs(empty_raw)
    assert "no SF CSVs found" in str(ei2.value)


# ---------------------------------------------------------------------------
# Test 3 — Orphan page detection (status=200, 0 inlinks)
# ---------------------------------------------------------------------------

def test_internal_links_orphan_page_detection(
    loaded_sf_data: tuple[list[dict], list[dict]],
) -> None:
    """internal_all has /orphan-page (200, 0 inlinks) → 1 orphan finding.
    /old-page (301) and /broken-page (404) MUST NOT be flagged as orphan
    even though they also report 0 inlinks (they have other higher-
    severity issues to fix first)."""
    internal_rows, inlinks_rows = loaded_sf_data

    out = ilt.transform(
        internal_all_rows=internal_rows,
        inlinks_rows=inlinks_rows,
        project_slug="testslug",
        run_date="2026-05-01",
    )
    rows = out["master_task"]
    orphans = [r for r in rows if "/orphan-page]" in r["note"] or
               r["note"].startswith(f"{ilt.NOTE_PREFIX}/{ilt.KIND_ORPHAN}]")
               and "orphan-page" in r["url"]]
    # Exactly one orphan (the /orphan-page URL).
    orphan_finding = [r for r in rows if r["url"] == "https://example.com/orphan-page"
                      and r["note"].startswith(f"{ilt.NOTE_PREFIX}/{ilt.KIND_ORPHAN}]")]
    assert len(orphan_finding) == 1
    row = orphan_finding[0]
    assert row["primary_source"] == ilt.PRIMARY_SOURCE_INTERNAL_LINKS
    assert row["impact"] == ilt.SEVERITY_HIGH
    assert row["auto_generated"] is True
    assert "Orphan page" in row["task"]

    # /old-page and /broken-page must NOT appear as orphan findings.
    bad_orphan_urls = {"https://example.com/old-page", "https://example.com/broken-page"}
    orphan_urls = {r["url"] for r in rows
                   if r["note"].startswith(f"{ilt.NOTE_PREFIX}/{ilt.KIND_ORPHAN}]")}
    assert orphan_urls.isdisjoint(bad_orphan_urls)

    assert out["meta"]["orphan_count"] == 1


# ---------------------------------------------------------------------------
# Test 4 — Broken link detection (4xx + 5xx)
# ---------------------------------------------------------------------------

def test_internal_links_broken_link_detection(
    loaded_sf_data: tuple[list[dict], list[dict]],
) -> None:
    """all_inlinks has 2× edges to /broken-page (404) and 1× to /server-fail
    (500). The transform must emit one broken finding per destination.

    /broken-page → severity HIGH (404)
    /server-fail → severity CRITICAL (5xx)
    """
    internal_rows, inlinks_rows = loaded_sf_data
    out = ilt.transform(
        internal_all_rows=internal_rows,
        inlinks_rows=inlinks_rows,
        project_slug="testslug",
        run_date="2026-05-01",
    )
    rows = out["master_task"]

    by_url = {r["url"]: r for r in rows
              if r["note"].startswith(f"{ilt.NOTE_PREFIX}/{ilt.KIND_BROKEN}]")}
    assert "https://example.com/broken-page" in by_url
    assert "https://example.com/server-fail" in by_url

    broken = by_url["https://example.com/broken-page"]
    assert broken["impact"] == ilt.SEVERITY_HIGH
    assert broken["priority"] == ilt.SEVERITY_HIGH
    # 2 inbound edges aggregated into one finding.
    metric = json.loads(broken["metric_impact_json"])
    assert metric["inbound_count"] == 2
    assert metric["status_code"] == 404

    server_fail = by_url["https://example.com/server-fail"]
    assert server_fail["impact"] == ilt.SEVERITY_CRITICAL

    assert out["meta"]["broken_count"] == 2


# ---------------------------------------------------------------------------
# Test 5 — Redirect chain detection (3xx aggregation)
# ---------------------------------------------------------------------------

def test_internal_links_redirect_chain_detection(
    loaded_sf_data: tuple[list[dict], list[dict]],
) -> None:
    """all_inlinks has 2× edges to /old-page (301). The transform must
    aggregate these into a single redirect-chain finding."""
    internal_rows, inlinks_rows = loaded_sf_data
    out = ilt.transform(
        internal_all_rows=internal_rows,
        inlinks_rows=inlinks_rows,
        project_slug="testslug",
        run_date="2026-05-01",
    )
    rows = out["master_task"]

    redirects = [r for r in rows
                 if r["note"].startswith(f"{ilt.NOTE_PREFIX}/{ilt.KIND_REDIRECT_CHAIN}]")]
    assert len(redirects) == 1
    rd = redirects[0]
    assert rd["url"] == "https://example.com/old-page"
    # 301 is a permanent redirect — flagged LOW (just update sources).
    assert rd["impact"] == ilt.SEVERITY_LOW
    metric = json.loads(rd["metric_impact_json"])
    assert metric["inbound_count"] == 2
    assert metric["status_code"] == 301

    assert out["meta"]["redirect_chain_count"] == 1


# ---------------------------------------------------------------------------
# Test 6 — master_task column tuple matches schema (Option A)
# ---------------------------------------------------------------------------

def test_internal_links_master_task_column_tuple_match(
    loaded_sf_data: tuple[list[dict], list[dict]],
    master_excel_schema: dict,
) -> None:
    """Every emitted row must carry exactly the 19 schema-locked
    master_task columns in the schema-declared order. This catches
    transform drift before it lands in master.xlsx via transaction.append.
    """
    sheet_def = master_excel_schema["sheets"]["master_task"]
    schema_cols = tuple(c["name"] for c in sheet_def["required_columns"])

    # The transform's column tuple must equal the schema's column tuple.
    assert ilt.MASTER_TASK_COLUMNS == schema_cols, (
        f"transform column tuple drifted from schema: "
        f"transform={ilt.MASTER_TASK_COLUMNS}, schema={schema_cols}"
    )

    internal_rows, inlinks_rows = loaded_sf_data
    out = ilt.transform(
        internal_all_rows=internal_rows,
        inlinks_rows=inlinks_rows,
        project_slug="testslug",
        run_date="2026-05-01",
    )
    rows = out["master_task"]
    assert rows, "expected at least one row from synthetic fixtures"
    for r in rows:
        assert tuple(r.keys()) == schema_cols, (
            f"row keys drift: got {tuple(r.keys())}, expected {schema_cols}"
        )


# ---------------------------------------------------------------------------
# Test 7 — auto_generated flag is set true on every row
# ---------------------------------------------------------------------------

def test_internal_links_auto_generated_flag_set_true(
    loaded_sf_data: tuple[list[dict], list[dict]],
) -> None:
    """The auto_generated column (col O, type=boolean per schema) must
    be set to True on every emitted row — that's the planning-skill
    convention for SSoT extension (Option A) and what dashboard_refresh
    reads to surface batch-approve flows.
    """
    internal_rows, inlinks_rows = loaded_sf_data
    out = ilt.transform(
        internal_all_rows=internal_rows,
        inlinks_rows=inlinks_rows,
        project_slug="testslug",
        run_date="2026-05-01",
    )
    rows = out["master_task"]
    assert rows, "expected at least one row from synthetic fixtures"
    for r in rows:
        assert r["auto_generated"] is True, (
            f"auto_generated must be True on row {r['task_id']}, "
            f"got {r['auto_generated']!r}"
        )
        # primary_source MUST be the closed-enum value internal_links
        # (master_task col C enum — Q-IL-1 schema bump applied Phase 8 closeout).
        assert r["primary_source"] == ilt.PRIMARY_SOURCE_INTERNAL_LINKS
        # note carries the [internal-links/...] prefix for lineage.
        assert r["note"].startswith(ilt.NOTE_PREFIX), (
            f"note prefix missing on row {r['task_id']}: {r['note']!r}"
        )
        # category carries the source module name.
        assert r["category"] == "internal-links"


# ---------------------------------------------------------------------------
# Test 8 — URL normalization is idempotent (D-03 invariant)
# ---------------------------------------------------------------------------

def test_url_normalization_idempotent() -> None:
    """normalize_url is idempotent + handles default ports, fragment,
    tracking params, trailing slash."""
    samples = [
        ("HTTPS://Example.COM:443/foo/?b=2&a=1#frag",
         "https://example.com/foo?a=1&b=2"),
        ("http://EXAMPLE.com:80/", "http://example.com/"),
        ("https://example.org/page/?utm_source=fb&utm_medium=cpc&q=tr",
         "https://example.org/page?q=tr"),
        ("https://example.org/page/#section",
         "https://example.org/page"),
        ("https://example.org/", "https://example.org/"),
    ]
    for raw, expected in samples:
        got = ilt.normalize_url(raw)
        assert got == expected, (
            f"normalize({raw!r}) → {got!r} (expected {expected!r})"
        )
        assert ilt.normalize_url(got) == got, (
            f"not idempotent: {raw!r} → {got!r}"
        )


# ---------------------------------------------------------------------------
# Test 9 — DURUR-style invalid input raises explicit errors (no silent fallback)
# ---------------------------------------------------------------------------

def test_durur_invalid_input_explicit_error() -> None:
    """Per the worker brief / convention authority: invalid input must
    raise an explicit InternalLinksError, NOT degrade silently.
    """
    # (a) project_slug must be non-empty string.
    with pytest.raises(ilt.InternalLinksError):
        ilt.transform(
            internal_all_rows=[], inlinks_rows=[],
            project_slug="", run_date="2026-05-01",
        )

    # (b) run_date must be YYYY-MM-DD.
    with pytest.raises(ilt.InternalLinksError):
        ilt.transform(
            internal_all_rows=[], inlinks_rows=[],
            project_slug="x", run_date="not-a-date",
        )

    # (c) default_status must be in statusEnum.
    with pytest.raises(ilt.InternalLinksError):
        ilt.transform(
            internal_all_rows=[], inlinks_rows=[],
            project_slug="x", run_date="2026-05-01",
            default_status="NOT-AN-ENUM",
        )

    # (d) max_entries must be a positive int.
    with pytest.raises(ilt.InternalLinksError):
        ilt.transform(
            internal_all_rows=[], inlinks_rows=[],
            project_slug="x", run_date="2026-05-01",
            max_entries=0,
        )

    # (e) URL normalization rejects empty / scheme-less / non-string.
    with pytest.raises(ilt.InternalLinksError):
        ilt.normalize_url("")
    with pytest.raises(ilt.InternalLinksError):
        ilt.normalize_url("example.com/no-scheme")
    with pytest.raises(ilt.InternalLinksError):
        ilt.normalize_url(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 10 — Optional DFS path budget pre-flight FAIL (DURUR #6)
# ---------------------------------------------------------------------------

def test_internal_links_optional_dfs_path_budget_preflight(
    tmp_path: Path,
) -> None:
    """When --use-dfs is requested and the projected credit usage exceeds
    the project's daily budget, preflight_budget raises BudgetExceededError.
    The skill is then expected to route the workflow to awaiting_approval
    per ADR-016 / spec §10.

    Mocks the subprocess call to scripts/budget/check_budget.py directly so
    the test does not depend on the script's filesystem behaviour.
    """
    cfg_path = tmp_path / "project.config.json"
    cfg_path.write_text("{}")
    events_path = tmp_path / "events.jsonl"

    # Estimate non-zero credits (use_dfs=True branch).
    estimate = ilt.estimate_credits(50, use_dfs=True)
    assert estimate == 50 * ilt.DFS_CREDITS_PER_URL  # 150

    class _ProcExceeded:
        returncode = 1
        stdout = (
            '{"budget_per_day": 100, "used_24h": 50, '
            '"remaining": 50, "exceeded": true}\n'
        )
        stderr = ""

    with patch.object(ilt.subprocess, "run", return_value=_ProcExceeded()):
        with pytest.raises(ilt.BudgetExceededError) as ei:
            ilt.preflight_budget(
                estimated_credits=estimate,
                project_config_path=cfg_path,
                events_path=events_path,
            )
    assert "budget pre-flight FAIL" in str(ei.value)
    assert "awaiting_approval" in str(ei.value)

    # Default path (use_dfs=False) burns 0 credits and never reaches preflight.
    assert ilt.estimate_credits(50, use_dfs=False) == 0


# ---------------------------------------------------------------------------
# Test 11 — Plugin-agnostik: transform accepts any slug, no hardcoded value
# ---------------------------------------------------------------------------

def test_plugin_agnostik_no_slug_dependency(
    synthetic_internal_all_csv: Path,
    synthetic_inlinks_csv: Path,
) -> None:
    """Same SF data + two different slugs must produce structurally
    identical row counts. task_ids differ by slug (plugin agnosticism)
    but row count, severity distribution, and column structure are
    purely data-driven.
    """
    internal_rows, inlinks_rows, _ = ilt.load_sf_csvs(
        synthetic_internal_all_csv.parent
    )
    out_a = ilt.transform(
        internal_all_rows=internal_rows, inlinks_rows=inlinks_rows,
        project_slug="site-alpha", run_date="2026-05-01",
    )
    out_b = ilt.transform(
        internal_all_rows=internal_rows, inlinks_rows=inlinks_rows,
        project_slug="site-beta", run_date="2026-05-01",
    )
    assert out_a["meta"]["row_count"] == out_b["meta"]["row_count"]
    assert tuple(out_a["master_task"][0].keys()) == ilt.MASTER_TASK_COLUMNS
    assert tuple(out_b["master_task"][0].keys()) == ilt.MASTER_TASK_COLUMNS
    # task_ids are slug-prefixed, so they MUST differ.
    ids_a = [r["task_id"] for r in out_a["master_task"]]
    ids_b = [r["task_id"] for r in out_b["master_task"]]
    assert all(t.startswith("site-alpha-") for t in ids_a)
    assert all(t.startswith("site-beta-") for t in ids_b)
    assert set(ids_a).isdisjoint(set(ids_b))


# ---------------------------------------------------------------------------
# Test 12 — Smoke E2E: synthetic CSVs → CLI → schema-shaped JSON output
# ---------------------------------------------------------------------------

def test_smoke_e2e_cli_output(
    tmp_path: Path,
    synthetic_internal_all_csv: Path,
    synthetic_inlinks_csv: Path,
) -> None:
    """Smoke E2E without any live MCP call: fixture CSVs already on disk,
    invoke internal_links_transform.main CLI, assert the output JSON
    parses + matches the schema-locked column structure. Idempotency is
    also asserted: a second run with the same input produces
    byte-identical output.
    """
    raw_dir = synthetic_internal_all_csv.parent
    out_dir = tmp_path / "out"

    rc = ilt.main([
        "--raw-dir", str(raw_dir),
        "--project-slug", "smoketest",
        "--run-date", "2026-05-01",
        "--output-dir", str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    out_file = out_dir / "master_task.json"
    assert out_file.exists()

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and payload
    expected_cols = set(ilt.MASTER_TASK_COLUMNS)
    for r in payload:
        assert set(r.keys()) == expected_cols
        assert r["auto_generated"] is True
        assert r["primary_source"] == ilt.PRIMARY_SOURCE_INTERNAL_LINKS

    # Idempotency: re-run with same input → byte-identical output file.
    first_bytes = out_file.read_bytes()
    rc2 = ilt.main([
        "--raw-dir", str(raw_dir),
        "--project-slug", "smoketest",
        "--run-date", "2026-05-01",
        "--output-dir", str(out_dir),
    ])
    assert rc2 == 0
    second_bytes = out_file.read_bytes()
    assert first_bytes == second_bytes, (
        "transform is not byte-idempotent under re-run"
    )


# ---------------------------------------------------------------------------
# Test 13 — primary_source uses the closed master_task enum (internal_links)
# ---------------------------------------------------------------------------

def test_primary_source_internal_links_enum_value(
    loaded_sf_data: tuple[list[dict], list[dict]],
    master_excel_schema: dict,
) -> None:
    """master_task col C `primary_source` is a closed enum. The transform
    MUST emit a value present in that enum — Phase 8 closeout Q-IL-1 schema
    bump added 'internal_links' as an explicit enum member (additive,
    schema_version unchanged, ADR-018 pattern).
    """
    sheet = master_excel_schema["sheets"]["master_task"]
    cols = sheet["required_columns"]
    primary_source_col = next(c for c in cols if c["name"] == "primary_source")
    enum = set(primary_source_col["enum"])
    assert ilt.PRIMARY_SOURCE_INTERNAL_LINKS in enum, (
        f"transform emits {ilt.PRIMARY_SOURCE_INTERNAL_LINKS!r} but it is not in the "
        f"master_task primary_source enum: {sorted(enum)}"
    )

    internal_rows, inlinks_rows = loaded_sf_data
    out = ilt.transform(
        internal_all_rows=internal_rows,
        inlinks_rows=inlinks_rows,
        project_slug="testslug",
        run_date="2026-05-01",
    )
    for r in out["master_task"]:
        assert r["primary_source"] in enum, (
            f"primary_source {r['primary_source']!r} not in master_task enum"
        )
