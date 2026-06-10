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
    # All 10 required sections present, plus two optional additive sections —
    # `decliners` (FIX-K K1) and `measurement_context` (GAP-M-W2) — both always
    # emitted and present in both framings.
    assert set(mr.REQUIRED_SECTIONS).issubset(report["sections"].keys())
    assert "decliners" in report["sections"], (
        "FIX-K K1: optional decliners section must always be emitted"
    )
    assert "measurement_context" in report["sections"], (
        "GAP-M-W2: optional measurement_context section must always be emitted"
    )
    assert set(report["sections"].keys()) == (
        set(mr.REQUIRED_SECTIONS) | {"decliners", "measurement_context"}
    )
    assert len(report["sections"]) == 12
    # Both are additive — NOT members of the required-sections tuple.
    assert "decliners" not in mr.REQUIRED_SECTIONS
    assert "measurement_context" not in mr.REQUIRED_SECTIONS
    assert len(mr.REQUIRED_SECTIONS) == 10

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


# --- Test 9: B2-01 no-write contract (events.jsonl READ-ONLY) ------------

def test_skill_md_carries_no_runnable_block() -> None:
    """B2-01 regression lock: monthly-report SKILL.md must contain NO
    runnable ``python`` fence. The 'Q-RP-01 RESOLVED' block that called
    ``events_writer.append_audit(...)`` was removed — events.jsonl stays
    READ-ONLY for this skill until Q-RP-01 actually resolves (Phase 14+),
    as the frontmatter (safe_auto_execute, outputs[] excludes events.jsonl),
    the command, and events-writer.md all already encode. A runnable block
    here would make an agent append to append-only state on every autonomous
    run — the exact side effect the rest of the system forbids.
    """
    body = SKILL_PATH.read_text(encoding="utf-8")
    assert "```python" not in body, (
        "monthly-report SKILL.md must carry no runnable python block "
        "(B2-01 no-write contract; events.jsonl READ-ONLY, Q-RP-01 deferred). "
        "The append_audit mentions that remain must stay non-runnable prose."
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


# --- FIX-K K1 fixtures + tests (report honesty) --------------------------

def _inputs_with_negative_delta() -> mr.ReportInputs:
    """Inputs whose GSC totals DECLINE period-over-period (recent < previous),
    plus declining pages and a content_decay row — used to prove framing never
    hides the negative facts (FIX-K K1)."""
    return mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-04-04", period_end="2026-05-01",
        gsc_performance=[
            {"url": "https://example.com/drop-1",
             "clicks_recent": 40, "clicks_previous": 100,
             "clicks_delta": -60, "impressions_recent": 800,
             "impressions_previous": 2000, "impressions_delta": -1200,
             "position_recent": 18.0, "position_previous": 9.0},
            {"url": "https://example.com/drop-2",
             "clicks_recent": 10, "clicks_previous": 30,
             "clicks_delta": -20, "impressions_recent": 300,
             "impressions_previous": 700, "impressions_delta": -400,
             "position_recent": 22.0, "position_previous": 15.0},
        ],
        content_decay=[
            {"url": "https://example.com/decay-1", "clicks_previous": 90,
             "clicks_recent": 30, "clicks_delta": -60, "delta_pct": -0.66,
             "trend": "down", "pillar": "guides", "action": "revise"},
        ],
    )


def _fixture_calendar_overlapping() -> list[dict]:
    """A Ranking update whose rollout sits inside the 2026-04-04..05-01 test
    window — overlaps() returns rollout_in_period ⇒ measurement_quality
    'update_overlap'. (update_calendar.overlaps shape: id/name/begin/end/
    service_name.)"""
    return [{
        "id": "apr-2026-core", "name": "April 2026 core update",
        "begin": "2026-04-15T00:00:00Z", "end": "2026-04-28T00:00:00Z",
        "service_name": "Ranking", "severity": "low",
        "source": "google_status_dashboard",
    }]


def _fixture_cohort_results() -> list[dict]:
    """An intervention_outcome.compute_outcome-shaped result list (R-138) —
    embedded verbatim into measurement_context.intervention_outcomes."""
    return [{
        "cohort_date": "2026-04-04", "score_version": "2.0",
        "post_date": "2026-05-01",
        "treated": {"n": 3, "median_position_delta": -4.0,
                    "clicks_before": 30, "clicks_after": 120,
                    "clicks_delta_pct": 300.0},
        "control": {"n": 3, "median_position_delta": 0.0,
                    "clicks_before": 30, "clicks_after": 31,
                    "clicks_delta_pct": 3.33},
        "difference_pp": 296.67, "verdict": "engine_positive",
        "caveat": "n<30 — directional evidence only",
        "attrition": {"treated_missing": 0, "control_missing": 0},
    }]


# --- Test 11: K1(a) — exec narrative ALWAYS states the net delta ----------

def test_exec_narrative_always_states_net_delta_both_framings() -> None:
    """FIX-K K1(a): a NEGATIVE net clicks delta must appear in the exec
    narrative under BOTH framings — positive_client may soften the tone but
    must never omit the number. (Pre-fix, positive_client dropped it entirely:
    monthly_report.py only surfaced a negative delta when framing=='internal'.)"""
    inputs = _inputs_with_negative_delta()
    pinned = "2026-05-01T09:00:00Z"
    for fp in ("positive_client", "internal"):
        report = mr.assemble_report(
            inputs=inputs, framing_policy=fp, output_formats=("html",),
            generated_at=pinned,
        )
        delta_pct = report["sections"]["gsc_positive_trends"]["deltas"][
            "clicks_delta_pct"
        ]
        assert delta_pct < 0, "fixture must produce a negative net delta"
        narrative = report["sections"]["exec_summary"]["narrative"]
        assert str(delta_pct) in narrative, (
            f"framing={fp}: net delta {delta_pct} omitted from exec narrative "
            f"(K1 honesty violation): {narrative!r}"
        )


# --- Test 12: K1(b) keystone — decliners byte-identical across framings ----

def test_decliners_section_byte_identical_across_framings(
    monthly_report_schema: dict,
) -> None:
    """FIX-K K1(b) keystone, GAP-M-W2 EXTENDED: BOTH the decliners section AND
    the new measurement_context section are framing INVARIANT — positive_client
    and internal produce byte-identical content (only the surrounding narrative
    tone/order may differ). Facts (declines, core-update overlap, intervention
    outcomes) survive framing (R-137/R-138)."""
    inputs = _inputs_with_negative_delta()
    pinned = "2026-05-01T09:00:00Z"
    cal = _fixture_calendar_overlapping()
    cohort = _fixture_cohort_results()
    pc = mr.assemble_report(inputs=inputs, framing_policy="positive_client",
                            output_formats=("html",), generated_at=pinned,
                            calendar_updates=cal, cohort_results=cohort)
    intl = mr.assemble_report(inputs=inputs, framing_policy="internal",
                              output_formats=("html",), generated_at=pinned,
                              calendar_updates=cal, cohort_results=cohort)
    # --- decliners (FIX-K K1b) byte-identical ---
    dec_pc = pc["sections"]["decliners"]
    dec_int = intl["sections"]["decliners"]
    assert json.dumps(dec_pc, sort_keys=True, ensure_ascii=False) == \
        json.dumps(dec_int, sort_keys=True, ensure_ascii=False), (
        "FIX-K K1(b): decliners section must be byte-identical across framings"
    )
    # It must actually carry the declines (non-empty for this fixture).
    assert dec_pc["pages_down"], "declining pages must be listed"
    assert dec_pc["decaying_content"], "decaying content must be listed"
    assert dec_pc["net_clicks_delta_pct"] < 0
    # --- measurement_context (GAP-M-W2 R-137/R-138) byte-identical ---
    mc_pc = pc["sections"]["measurement_context"]
    mc_int = intl["sections"]["measurement_context"]
    assert json.dumps(mc_pc, sort_keys=True, ensure_ascii=False) == \
        json.dumps(mc_int, sort_keys=True, ensure_ascii=False), (
        "GAP-M-W2: measurement_context section must be byte-identical across framings"
    )
    assert mc_pc["measurement_quality"] == "update_overlap"
    assert mc_pc["core_updates_overlap"], "the overlapping update must be annotated"
    assert mc_pc["intervention_outcomes"] == cohort, (
        "intervention outcomes embedded verbatim (framing-invariant)"
    )
    # Schema still validates with BOTH additive sections present (both framings).
    Draft7Validator(monthly_report_schema).validate(pc)
    Draft7Validator(monthly_report_schema).validate(intl)


# --- GAP-M-W2: keywords_up position_before fabrication retirement ---------

def test_keywords_up_no_position_before_fabrication(
    monthly_report_schema: dict,
) -> None:
    """GAP-M-W2 (measurement honesty): retire the
    `position_before = position_after + 3` fabrication in _build_keywords_up.

    With no longitudinal source wired, position_before MUST be null (honest
    "unknown"), never a synthetic pos_after+3 approximation. position_after
    stays the real current_position. Schema accepts the nullable field."""
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-04-04", period_end="2026-05-01",
        opportunity=[
            {"query": "seo nedir", "current_position": 8.5,
             "impressions_30d": 1200, "clicks_30d": 50},
            {"query": "title tag", "current_position": 12.0,
             "impressions_30d": 800, "clicks_30d": 20},
        ],
    )
    report = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-05-01T09:00:00Z",
    )
    kw = report["sections"]["keywords_up"]
    assert kw, "keywords_up must still list the opportunity rows"
    by_q = {i["query"]: i for i in kw}
    # The retired fabrication produced 8.5+3=11.5 / 12.0+3=15.0.
    assert by_q["seo nedir"]["position_before"] is None, (
        "GAP-M-W2: position_before must be null, not the retired pos_after+3 "
        f"fabrication: {by_q['seo nedir']!r}"
    )
    assert by_q["seo nedir"]["position_after"] == 8.5
    assert by_q["title tag"]["position_before"] is None
    assert by_q["title tag"]["position_after"] == 12.0
    for item in kw:
        assert item["position_before"] is None
    # Schema validates the nullable position_before (additive widening).
    Draft7Validator(monthly_report_schema).validate(report)


def test_keywords_up_passes_through_stored_position_before(
    monthly_report_schema: dict,
) -> None:
    """When a longitudinal source DOES store a prior position on the opportunity
    row, _build_keywords_up passes it through verbatim (no fabrication, but no
    discarding real data either)."""
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-04-04", period_end="2026-05-01",
        opportunity=[
            {"query": "seo nedir", "current_position": 8.5,
             "position_before": 20.0,  # real stored prior position
             "impressions_30d": 1200, "clicks_30d": 50},
        ],
    )
    report = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-05-01T09:00:00Z",
    )
    kw = report["sections"]["keywords_up"][0]
    assert kw["position_before"] == 20.0  # passed through, NOT fabricated 11.5
    assert kw["position_after"] == 8.5
    Draft7Validator(monthly_report_schema).validate(report)


def test_keywords_up_renders_unknown_before_honestly() -> None:
    """The retired fabrication must not leak a literal 'None' into the rendered
    markdown — an unknown before-position renders as '?' (honest unknown)."""
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-04-04", period_end="2026-05-01",
        opportunity=[
            {"query": "seo nedir", "current_position": 8.5,
             "impressions_30d": 1200, "clicks_30d": 50},
        ],
    )
    report = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-05-01T09:00:00Z",
    )
    template = (
        TEMPLATE_PATH.read_text(encoding="utf-8")
    )
    rendered = mr.render_report_markdown(report=report, template_text=template)
    assert "pozisyon ?→8.5" in rendered, (
        "unknown position_before must render as '?', not 'None': "
        f"{[ln for ln in rendered.splitlines() if 'seo nedir' in ln]}"
    )
    assert "None→" not in rendered, "literal 'None' leaked into rendered report"


# --- GAP-M-W2: measurement_context section (R-137 core-update overlap) -----

def _may_2026_calendar() -> list[dict]:
    return [{
        "id": "wdAXJk6LRRihEjpzEeWE", "name": "May 2026 core update",
        "begin": "2026-05-21T15:40:00Z", "end": "2026-06-02T12:40:00Z",
        "service_name": "Ranking", "severity": "low",
        "source": "google_status_dashboard",
    }]


def test_measurement_context_update_overlap_straddling_may_2026(
    monthly_report_schema: dict,
) -> None:
    """R-137: a report window straddling the 2026-05-21..06-02 May core update
    is flagged measurement_quality='update_overlap' and names the update — so
    deltas in this window are not silently attributed to engine work."""
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-05-20", period_end="2026-06-16",
    )
    report = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-06-16T09:00:00Z",
        calendar_updates=_may_2026_calendar(),
    )
    mc = report["sections"]["measurement_context"]
    assert mc["measurement_quality"] == "update_overlap"
    assert "May 2026 core update" in [
        o["name"] for o in mc["core_updates_overlap"]
    ]
    assert mc["intervention_outcomes"] == []  # no cohort passed → empty
    assert mc["notes"], "a one-line attribution verdict must be present"
    Draft7Validator(monthly_report_schema).validate(report)


def test_measurement_context_clean_vs_insufficient_history(
    monthly_report_schema: dict,
) -> None:
    """A non-overlapping window with a populated calendar → 'clean'; an empty
    calendar (none loaded) → 'insufficient_history' (overlap undeterminable —
    NEVER fabricated as clean)."""
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-01-01", period_end="2026-01-28",
    )
    clean = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-01-28T09:00:00Z",
        calendar_updates=_may_2026_calendar(),
    )
    assert clean["sections"]["measurement_context"]["measurement_quality"] == "clean"

    insufficient = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-01-28T09:00:00Z",
    )
    assert insufficient["sections"]["measurement_context"][
        "measurement_quality"
    ] == "insufficient_history"
    Draft7Validator(monthly_report_schema).validate(clean)
    Draft7Validator(monthly_report_schema).validate(insufficient)


def test_measurement_context_post_update_settling() -> None:
    """A window starting within the 7-day settle buffer after an update ends
    → 'post_update_settling' (R-137 — Google: assess only after rollout)."""
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-06-05", period_end="2026-07-02",
    )
    report = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-07-02T09:00:00Z",
        calendar_updates=_may_2026_calendar(),
    )
    assert report["sections"]["measurement_context"][
        "measurement_quality"
    ] == "post_update_settling"


def test_measurement_context_is_additive_optional(
    monthly_report_schema: dict,
) -> None:
    """An old-shape report WITHOUT the additive sections still validates —
    measurement_context is NOT in sections.required (additive precedent)."""
    inputs = _inputs_with_negative_delta()
    report = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-05-01T09:00:00Z",
    )
    del report["sections"]["measurement_context"]
    del report["sections"]["decliners"]
    Draft7Validator(monthly_report_schema).validate(report)
    required = monthly_report_schema["properties"]["sections"]["required"]
    assert "measurement_context" not in required
    assert "decliners" not in required


def test_measurement_context_renders_in_template() -> None:
    """The rendered markdown carries the Ölçüm Bağlamı section + the overlap
    verdict line (template var wired; no unsubstituted $token)."""
    inputs = mr.ReportInputs(
        project_id="demo-project",
        period_start="2026-05-20", period_end="2026-06-16",
    )
    report = mr.assemble_report(
        inputs=inputs, framing_policy="positive_client",
        output_formats=("html",), generated_at="2026-06-16T09:00:00Z",
        calendar_updates=_may_2026_calendar(),
        cohort_results=_fixture_cohort_results(),
    )
    rendered = mr.render_report_markdown(
        report=report, template_text=TEMPLATE_PATH.read_text(encoding="utf-8"),
    )
    assert "Ölçüm Bağlamı" in rendered
    assert "May 2026 core update" in rendered
    assert "$measurement_context_md" not in rendered  # var substituted


def test_monthly_skill_documents_measurement_context() -> None:
    """GAP-M-W2 contract lock: the monthly-report SKILL documents the
    measurement_context section (R-137/R-138) + the intervention_outcome wiring
    (--cohort-results), and stays READ-ONLY (no runnable python block — the
    wiring is shown as bash)."""
    body = SKILL_PATH.read_text(encoding="utf-8")
    assert "measurement_context" in body
    assert "R-137" in body and "R-138" in body
    assert "--cohort-results" in body
    assert "intervention_outcome.py" in body
    assert "update_calendar.py" in body
    assert "```python" not in body, (
        "monthly-report SKILL must stay READ-ONLY — wiring shown as bash, "
        "not a runnable python block (B2-01 contract)"
    )
