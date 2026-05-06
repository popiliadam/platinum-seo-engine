"""
tests/skills/test_monthly_report.py — monthly-report reporting skill tests.

Phase 9 Wave 1 W-E1. Mirrors tests/skills/test_master_task_sync.py
structure (frontmatter parse, schema validation, idempotency smoke,
DURUR fired, forbidden-token guard, plugin-agnostik guard).

This is a LOCAL-AGGREGATION skill — no MCP, no DFS, no budget pre-flight.
Every test is fully data-driven with synthetic master.xlsx-shaped rows
+ synthetic events.

Schemas referenced:
  - schemas/monthly-report.schema.json (10 required sections,
    framing_policy enum, output_formats enum, data_sources enum)
  - schemas/skill-frontmatter.schema.json
  - schemas/master-excel.schema.json (consumed sheet shapes; READ-ONLY)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.reporting import monthly_report as mr


# --- Constants — paths ---------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "reporting" / "monthly-report" / "SKILL.md"
TRANSFORM_PATH = REPO_ROOT / "scripts" / "reporting" / "monthly_report.py"
TEMPLATE_PATH = REPO_ROOT / "templates" / "reports" / "monthly-report.template.md"


# --- Fixtures ------------------------------------------------------------

@pytest.fixture(scope="module")
def monthly_report_schema() -> dict:
    return json.loads(
        (SCHEMAS / "monthly-report.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    """Parse the YAML frontmatter block of monthly-report SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_inputs() -> mr.ReportInputs:
    """Synthetic master.xlsx-shaped rows for all 9 consumed sheets +
    a small work-events list. Designed to exercise every section
    builder with non-trivial values."""
    return mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-04-04",
        period_end="2026-05-01",
        master_task=[
            {
                "task_id": "T-0001", "task": "Title revize",
                "primary_source": "tech_fix",
                "url": "https://example.com/page-1",
                "priority": "HIGH", "impact": "MEDIUM",
                "duration_est_min": 30, "status": "TODO",
                "auto_generated": True,
            },
            {
                "task_id": "T-0002", "task": "Schema ekle",
                "primary_source": "schema",
                "url": "https://example.com/page-2",
                "priority": "MEDIUM", "duration_est_min": 45,
                "status": "TODO", "auto_generated": True,
            },
            {
                "task_id": "T-0003", "task": "Kapatildi",
                "primary_source": "tech_fix",
                "status": "DONE", "auto_generated": True,
            },
        ],
        completed_work=[
            {"id": "T-1001", "task_or_content": "LCP fix",
             "url": "https://example.com/page-1",
             "date": "2026-04-15", "category": "tech-fix",
             "note": "rel-001"},
            {"id": "T-1002", "task_or_content": "Içerik revize 1",
             "url": "https://example.com/blog-1",
             "date": "2026-04-20", "category": "content-revised",
             "note": "rel-002"},
            {"id": "T-1003", "task_or_content": "Yeni sayfa",
             "url": "https://example.com/new-1",
             "date": "2026-04-22", "category": "new-content",
             "note": "rel-003"},
        ],
        content_improve=[],
        new_content_plan=[],
        gsc_performance=[
            {"url": "https://example.com/page-1",
             "clicks_recent": 200, "clicks_previous": 150,
             "clicks_delta": 50, "clicks_delta_pct": 0.33,
             "impressions_recent": 5000, "impressions_previous": 4000,
             "impressions_delta": 1000,
             "ctr_recent": 0.04, "position_recent": 8.5,
             "position_previous": 11.0},
            {"url": "https://example.com/page-2",
             "clicks_recent": 80, "clicks_previous": 60,
             "clicks_delta": 20, "impressions_recent": 1500,
             "impressions_previous": 1200, "impressions_delta": 300,
             "position_recent": 14.0, "position_previous": 16.0},
        ],
        opportunity=[
            {"query": "seo nedir", "current_position": 8.5,
             "impressions_30d": 1200, "clicks_30d": 50,
             "ctr_pct": 0.04},
            {"query": "title tag", "current_position": 12.0,
             "impressions_30d": 800, "clicks_30d": 20},
        ],
        content_decay=[],
        tech_seo=[],
        schema_findings=[],
        work_events=[],
    )


# --- Test 1: Frontmatter validates ---------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict, skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must validate against
    schemas/skill-frontmatter.schema.json (Draft 7) and carry the
    expected name / status / category / inputs / outputs shape."""
    fm = skill_frontmatter
    assert fm["name"] == "monthly-report"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "reporting"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    # No required NOR optional MCP tools — local aggregation only.
    assert fm.get("mcp_tools", {}).get("required", []) == []
    assert fm.get("mcp_tools", {}).get("optional", []) == []

    # REVIZE 1: outputs[] has exactly 3 entries; events.jsonl REMOVED.
    outputs = fm["outputs"]
    assert len(outputs) == 3, (
        f"REVIZE 1: outputs must have 3 entries, got {len(outputs)}"
    )
    assert any("master.xlsx#none" in o for o in outputs)
    assert any("outputs/reports/" in o and "monthly" in o for o in outputs)
    assert any("inbox/local/" in o and "monthly" in o for o in outputs)
    assert "events.jsonl" not in outputs
    assert not any(o == "events.jsonl" for o in outputs)

    # Budget: 0 credits, no paid MCP.
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"].get("estimated_credits", 0) == 0

    # Autonomy: HIGH confidence + safe_auto_execute=True (cron-ready).
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True

    # Manual trigger registers the slash command.
    assert "/pseo-monthly" in fm["triggers"]["manual"]

    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm),
                  key=lambda e: list(e.absolute_path))
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# --- Test 2: natural_language min length sentinel ------------------------

def test_natural_language_min_length(skill_frontmatter: dict) -> None:
    """REVIZE 1 / Gate #7 sentinel — natural_language must be >= 30 chars
    so the description matcher has enough phrases to trigger on."""
    nl = skill_frontmatter["triggers"]["natural_language"]
    assert isinstance(nl, str)
    assert len(nl) >= 30, (
        f"natural_language length {len(nl)} < 30 (Gate #7 sentinel)"
    )


# --- Test 3: 10-section schema validation (CRITICAL) ---------------------

def test_assemble_report_validates_10_sections(
    synthetic_inputs: mr.ReportInputs, monthly_report_schema: dict,
) -> None:
    """assemble_report output MUST validate against
    schemas/monthly-report.schema.json (Draft 7) with all 10 required
    sections present and framing_policy default = positive_client."""
    report = mr.assemble_report(
        inputs=synthetic_inputs,
        framing_policy="positive_client",
        output_formats=("html",),
        data_sources=[
            {"source": "master_task", "run_ids": [1]},
            {"source": "completed_work", "run_ids": [1]},
            {"source": "work_log", "run_ids": [1]},
        ],
        generated_at="2026-05-01T09:00:00Z",
    )
    # All 10 required sections present.
    assert set(report["sections"].keys()) == set(mr.REQUIRED_SECTIONS)
    assert len(report["sections"]) == 10

    # exec_summary has narrative.
    assert report["sections"]["exec_summary"]["narrative"]

    # gsc_positive_trends shape sound.
    gpt = report["sections"]["gsc_positive_trends"]
    assert gpt["current_period"]["clicks"] == 280  # 200+80
    assert "deltas" in gpt

    # next_month_plan: 2 TODO rows, sorted by priority.
    nmp = report["sections"]["next_month_plan"]
    assert len(nmp) == 2
    assert nmp[0]["priority"] == "HIGH"
    assert nmp[1]["priority"] == "MEDIUM"

    # framing_policy default = positive_client (per schema line 207).
    assert report["framing_policy"] == "positive_client"

    # Full Draft 7 validation.
    validator = Draft7Validator(monthly_report_schema)
    errs = sorted(validator.iter_errors(report),
                  key=lambda e: list(e.absolute_path))
    assert not errs, (
        f"report fails monthly-report.schema.json: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# --- Test 4: framing_policy invalid value reject (sentinel) --------------

def test_framing_policy_invalid_value_reject(
    synthetic_inputs: mr.ReportInputs,
) -> None:
    """Sentinel: framing_policy not in enum {positive_client, internal}
    raises FramingPolicyEnumViolation (subclass of MonthlyReportError /
    ValueError-style behavior). Per worker brief acceptance Gate #4."""
    with pytest.raises(mr.FramingPolicyEnumViolation):
        mr.assemble_report(
            inputs=synthetic_inputs,
            framing_policy="invalid-value",
            output_formats=("html",),
        )
    # Empty string also rejected.
    with pytest.raises(mr.FramingPolicyEnumViolation):
        mr.assemble_report(
            inputs=synthetic_inputs,
            framing_policy="",
            output_formats=("html",),
        )
    # The enum members both pass.
    for ok in ("positive_client", "internal"):
        report = mr.assemble_report(
            inputs=synthetic_inputs, framing_policy=ok,
            output_formats=("html",),
        )
        assert report["framing_policy"] == ok


# --- Test 5: empty events.jsonl edge case (graceful degrade) -------------

def test_empty_events_jsonl_graceful_degrade(tmp_path: Path) -> None:
    """When events.jsonl is missing OR empty, read_events_jsonl returns
    [] without raising. This is the cron-ready edge case (a fresh
    project may not have any work events yet)."""
    # Missing file → [].
    out = mr.read_events_jsonl(
        events_path=tmp_path / "no-such.jsonl",
        period_start="2026-04-01", period_end="2026-05-01",
    )
    assert out == []

    # Empty file → [].
    empty = tmp_path / "events.jsonl"
    empty.write_text("", encoding="utf-8")
    out = mr.read_events_jsonl(
        events_path=empty,
        period_start="2026-04-01", period_end="2026-05-01",
    )
    assert out == []

    # File with mixed valid + invalid + out-of-range lines.
    mixed = tmp_path / "events2.jsonl"
    mixed.write_text("\n".join([
        '{"ts": "2026-04-15", "kind": "work_log", "url": "x"}',  # in range
        '{"ts": "2026-01-01", "kind": "work_log"}',              # out of range
        'not-json-line',                                          # malformed
        '',                                                       # blank
        '{"timestamp": "2026-04-20T12:00:00Z", "kind": "work_log"}',  # in range
    ]), encoding="utf-8")
    out = mr.read_events_jsonl(
        events_path=mixed,
        period_start="2026-04-01", period_end="2026-05-01",
    )
    assert len(out) == 2  # only the in-range, well-formed entries
    # And, defensive: the assembler tolerates an empty work_events list.
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-04-04", period_end="2026-05-01",
        work_events=[],
    )
    report = mr.assemble_report(inputs=inputs, output_formats=("html",))
    assert "exec_summary" in report["sections"]


# --- Test 6: multi-source data_sources merge -----------------------------

def test_multi_source_data_sources_merge(
    synthetic_inputs: mr.ReportInputs, monthly_report_schema: dict,
) -> None:
    """data_sources is a provenance array — each item is
    {source: enum, run_ids: [int+]}. The assembler must accept multiple
    sources, validate each one's enum, and round-trip them into the
    output unchanged."""
    sources = [
        {"source": "master_task", "run_ids": [1, 2]},
        {"source": "completed_work", "run_ids": [3]},
        {"source": "gsc_mcp", "run_ids": [4, 5, 6]},
        {"source": "work_log", "run_ids": [7]},
    ]
    report = mr.assemble_report(
        inputs=synthetic_inputs, framing_policy="positive_client",
        output_formats=("html", "pdf"),
        data_sources=sources, generated_at="2026-05-01T09:00:00Z",
    )
    assert report["data_sources"] == sources
    # Schema-validate the merged shape.
    Draft7Validator(monthly_report_schema).validate(report)

    # An invalid source value → DataSourceEnumViolation.
    bad = sources + [{"source": "not-a-source", "run_ids": [99]}]
    with pytest.raises(mr.DataSourceEnumViolation):
        mr.assemble_report(
            inputs=synthetic_inputs, framing_policy="positive_client",
            output_formats=("html",), data_sources=bad,
        )

    # An invalid output_format value → OutputFormatEnumViolation.
    with pytest.raises(mr.OutputFormatEnumViolation):
        mr.assemble_report(
            inputs=synthetic_inputs, framing_policy="positive_client",
            output_formats=("html", "xml"),  # "xml" not in enum
        )


# --- Test 7: Forbidden tokens grep CLEAN (16 grep total) -----------------

def test_no_forbidden_tokens_in_skill() -> None:
    """Per worker brief Gate #6 + Phase 7+8 lessons: 3 forbidden field
    tokens (per_call, per_url, schema-uydurma) plus the slug-literal
    family checked in the sibling test = 4 token classes × 4 files = 16
    grep checks must all be CLEAN.

    The literal token strings are base64-decoded at runtime so this
    self-grep does not trip its own check (sibling pattern: see
    test_plugin_agnostik_no_slug_literal).
    """
    import base64
    encoded_forbidden = (
        b"ZXN0aW1hdGVkX2NyZWRpdHNfcGVyX2NhbGw=",  # _per_call
        b"ZXN0aW1hdGVkX2NyZWRpdHNfcGVyX3VybA==",  # _per_url
        b"bWV0cmljX25hbWU=",                       # m-name
    )
    forbidden = tuple(
        base64.b64decode(t).decode("ascii") for t in encoded_forbidden
    )
    files = (TRANSFORM_PATH, SKILL_PATH, TEMPLATE_PATH, Path(__file__))
    for fp in files:
        body = fp.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in body, (
                f"forbidden token {token!r} found in {fp.name}"
            )


# --- Test 8: plugin-agnostik (no slug hardcode in transform) -------------

def test_plugin_agnostik_no_slug_literal() -> None:
    """The transform.py + SKILL.md must contain 0 occurrences of any
    real-project slug literal. The slug tokens are obfuscated as base64
    so this test file does not trip its own self-grep.

    Per acceptance Gate #9 + worker brief plugin-agnostik hard
    constraint; tolerated in test fixtures only (synthetic 'demo-project'
    is used in tests but is not a real plugin slug, so it's fine)."""
    import base64
    encoded_tokens = (
        b"ZGVudG5vdGlvbg==", b"dmVudG8=", b"ZXlrb20=", b"YmlnY2F0dHI=",
        b"Y2FsaXR0ZQ==", b"bGFzdGlrc2E=", b"bm9yYW5pbnNhYXQ=", b"YWRzdGFyaw==",
    )
    forbidden_slugs = tuple(
        base64.b64decode(t).decode("ascii") for t in encoded_tokens
    )
    pattern = re.compile(
        r"\b(" + "|".join(forbidden_slugs) + r")\b", flags=re.IGNORECASE,
    )
    transform_src = TRANSFORM_PATH.read_text(encoding="utf-8")
    skill_src = SKILL_PATH.read_text(encoding="utf-8")
    template_src = TEMPLATE_PATH.read_text(encoding="utf-8")
    for label, body in (
        ("transform", transform_src),
        ("skill", skill_src),
        ("template", template_src),
    ):
        m = pattern.search(body)
        assert m is None, (
            f"forbidden hardcoded slug {m.group(0)!r} found in {label}"
        )


# --- Test 9: master_task READ-ONLY + REVIZE 3 (no events.jsonl write) ----

def test_master_task_read_only_no_openpyxl_write() -> None:
    """Per acceptance Gate #8 + REVIZE 3: this skill is a LOCAL
    READ-ONLY aggregator. The transform must NOT contain any
    transaction-layer writes against master.xlsx, must NOT call
    workbook.save(), and must NOT import the events.jsonl writer module
    or invoke its provenance-append helper.

    Token literals are base64-decoded at runtime so this self-grep does
    not trip its own check.
    """
    import base64
    src = TRANSFORM_PATH.read_text(encoding="utf-8")
    # No master.xlsx mutation calls.
    enc_writes = (
        b"dHJhbnNhY3Rpb24uYXBwZW5k",  # transaction.append
        b"dHJhbnNhY3Rpb24udXBkYXRl",  # transaction.update
    )
    for t in enc_writes:
        decoded = base64.b64decode(t).decode("ascii")
        assert decoded not in src, (
            f"transform.py contains {decoded!r} — Gate #8 violation"
        )
    # openpyxl opened in read-only mode.
    assert "read_only=True" in src, (
        "openpyxl load_workbook must use read_only=True (Gate #8)"
    )
    # No workbook .save() call.
    assert ".save(" not in src, (
        "transform.py contains workbook .save() — Gate #8 violation"
    )
    # REVIZE 3: no events.jsonl writer reuse.
    enc_evt = (
        b"ZXZlbnRzX3dyaXRlcg==",        # writer module name
        b"YXBwZW5kX3Byb3ZlbmFuY2U=",    # provenance helper
    )
    for t in enc_evt:
        decoded = base64.b64decode(t).decode("ascii")
        assert decoded not in src, (
            f"REVIZE 3: forbidden symbol {decoded!r} in transform"
        )


# --- Test 10: Idempotency + template render smoke ------------------------

def test_idempotent_assembly_and_template_render(
    synthetic_inputs: mr.ReportInputs,
) -> None:
    """Re-run assemble_report twice with identical inputs + pinned
    generated_at → byte-identical reports. Then render the bundled
    template against the report and assert all required headings
    appear in the rendered markdown."""
    pinned = "2026-05-01T09:00:00Z"
    a = mr.assemble_report(
        inputs=synthetic_inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at=pinned,
    )
    b = mr.assemble_report(
        inputs=synthetic_inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at=pinned,
    )
    assert a == b, "assemble_report not idempotent across runs"

    # Render the bundled template — smoke for $variable substitution.
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = mr.render_report_markdown(report=a, template_text=template_text)
    # Required headings appear.
    for heading in (
        "Aylık Rapor", "Yönetici Özeti", "GSC Pozitif Trendler",
        "Yükselen Anahtar Kelimeler", "Yükselen Sayfalar",
        "Tamamlanan Tech SEO İşleri", "Revize Edilen İçerikler",
        "Yeni Yayınlanan İçerikler", "Rakip Snapshot",
        "Backlink Delta", "Önümüzdeki Ay Planı",
    ):
        assert heading in rendered, f"missing heading {heading!r} in rendered output"
    # No leftover unsubstituted $key tokens.
    assert "$project_id" not in rendered  # was substituted
    assert "demo-project" in rendered     # synthetic id reached the output

    # Snapshot wraps the report dict.
    snap = mr.build_snapshot(report=a)
    assert snap["writer"] == "monthly_report"
    assert snap["report"] == a

    # Template render error path: missing key → TemplateRenderError.
    bad_template = "Hello $missing_key"
    with pytest.raises(mr.TemplateRenderError):
        mr.render_report_markdown(report=a, template_text=bad_template)
