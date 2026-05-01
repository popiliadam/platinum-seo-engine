"""tests/skills/test_portfolio_kpi_trend.py — Phase 9 W-E7 reporting skill.

Mirrors test_portfolio_weekly_brief.py shape (path convention + READ-ONLY
discipline + plugin-agnostik + frontmatter + forbidden tokens) and adds
KPI-trend-specific gates:

  - period_days range 7-90 sentinel (reject 6, reject 91, accept 7/30/90)
  - multi-project time series merge (3 projects, mixed master.xlsx /
    events.jsonl presence)
  - empty events.jsonl tolerance (zero-event project, graceful)
  - trend line continuity (no gaps in date axis — every day from
    period_start..period_end appears exactly once)
  - event_type 10 enum coverage (every enum value gets a bucket)
  - natural_language min length (≥ 30 char) sentinel
  - forbidden tokens guard (4 tokens + 8 obfuscated slugs, grep CLEAN)
  - assert_read_only_module helper (W-E3 paterni reuse)
  - W-E4 path convention (projects/_portfolio/{outputs,inbox}/local/ +
    PSEO_WORKSPACE_ROOT env)

This is a READ-ONLY reporting skill — no MCP, no DFS, no budget
pre-flight, no master.xlsx writes, no events.jsonl writes.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.reporting import portfolio_kpi_trend as pkt


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = (
    REPO_ROOT / "skills" / "reporting" / "portfolio-kpi-trend" / "SKILL.md"
)
TRANSFORM_PATH = (
    REPO_ROOT / "scripts" / "reporting" / "portfolio_kpi_trend.py"
)
TEMPLATE_PATH = (
    REPO_ROOT / "templates" / "reports" / "portfolio-kpi-trend.template.md"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def portfolio_config_schema() -> dict:
    return json.loads(
        (SCHEMAS / "portfolio-config.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_portfolio_config() -> dict:
    """Synthetic portfolio.config.json v1.1 with 3 active projects.
    Slugs are intentionally generic test fixtures (NOT real client slugs)."""
    return {
        "schema_version": "1.1",
        "portfolio_id": "test-portfolio",
        "display_name": "Test Portfolio",
        "active_projects": [
            {
                "slug": "alpha-test",
                "workspace_path": "alpha-test",
                "profile": ["b2b-saas"],
                "priority": 1,
            },
            {
                "slug": "beta-test",
                "workspace_path": "beta-test",
                "profile": ["e-commerce"],
                "priority": 2,
            },
            {
                "slug": "gamma-test",
                "workspace_path": "gamma-test",
                "profile": ["local-service"],
                "priority": 3,
            },
        ],
        "slas": {
            "weekly_sync_max_days": 7,
            "monthly_roundup_target_dom": 1,
        },
        "cadence": {
            "weekly_brief": {"day": "Friday", "hour": 9},
            "monthly_roundup": {"day_of_month": 1, "hour": 10},
        },
        "cross_query": {"read_only": True},
    }


@pytest.fixture
def fixed_now() -> datetime:
    """Deterministic 'now' for reproducible test runs (UTC)."""
    return datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter validates + natural_language ≥ 30 char + Gate 1, 7
# ---------------------------------------------------------------------------

def test_frontmatter_validates_and_natural_language_min_length(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    fm = skill_frontmatter
    assert fm["name"] == "portfolio-kpi-trend"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"
    assert fm["category"] == "reporting"

    # Manual triggers EMPTY (per worker brief: NO slash command).
    assert fm["triggers"]["manual"] == []

    # natural_language sentinel: ≥ 30 char (Gate 7).
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str)
    assert len(nl) >= 30, (
        f"natural_language must be ≥ 30 char, got {len(nl)}"
    )
    # Required TR + EN trigger phrases per worker brief.
    for required in (
        "kpi trend", "zaman serisi", "trend analizi", "portföy kpi",
    ):
        assert required in nl, f"missing trigger phrase: {required!r}"

    # outputs[] — 3 entries (master.xlsx#none + report.md + snapshot.json).
    outputs = fm["outputs"]
    assert "master.xlsx#none" in outputs
    assert any(
        "portfolio-kpi-trend.md" in o and "outputs/reports/" in o
        for o in outputs
    ), f"report .md missing from outputs: {outputs}"
    assert any(
        "portfolio-kpi-trend.json" in o and "inbox/local/" in o
        for o in outputs
    ), f"snapshot .json missing from outputs: {outputs}"
    assert "events.jsonl" not in outputs, (
        "events.jsonl must NOT be in outputs[] (Q-RP-01 defer)"
    )

    # No MCP tools required NOR optional — pure local aggregator.
    assert fm["mcp_tools"]["required"] == []
    assert fm["mcp_tools"]["optional"] == []

    # Budget: 0 credits, no paid MCP. Autonomy: HIGH + cron-ready.
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"].get("estimated_credits", 0) == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["requires_approval"] is False
    assert fm["autonomy"]["safe_auto_execute"] is True

    # Full Draft 7 validation (Gate 1).
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(
        validator.iter_errors(fm), key=lambda e: list(e.absolute_path)
    )
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — period_days range 7-90 sentinel (reject 6 + 91, accept 7/30/90)
# ---------------------------------------------------------------------------

def test_period_days_range_7_to_90_sentinel(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """Per worker brief: period_days < 7 OR > 90 → DURUR
    PeriodDaysOutOfRangeError. Boundaries 7 + 30 + 90 must succeed."""
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / slug / "_state").mkdir(parents=True)
        (ws / slug / "_state" / "events.jsonl").write_text(
            "", encoding="utf-8",
        )

    # Negative: 6 → DURUR.
    with pytest.raises(pkt.PeriodDaysOutOfRangeError):
        pkt.build_kpi_trend_batch(
            portfolio_config=synthetic_portfolio_config,
            workspace_root=ws,
            now=fixed_now,
            period_days=6,
        )
    # Negative: 91 → DURUR.
    with pytest.raises(pkt.PeriodDaysOutOfRangeError):
        pkt.build_kpi_trend_batch(
            portfolio_config=synthetic_portfolio_config,
            workspace_root=ws,
            now=fixed_now,
            period_days=91,
        )
    # Negative: 0 → DURUR.
    with pytest.raises(pkt.PeriodDaysOutOfRangeError):
        pkt._validate_period_days(0)
    # Negative: -1 → DURUR.
    with pytest.raises(pkt.PeriodDaysOutOfRangeError):
        pkt._validate_period_days(-1)
    # Negative: not int-coercible → DURUR.
    with pytest.raises(pkt.PeriodDaysOutOfRangeError):
        pkt._validate_period_days("not-a-number")

    # Positive boundaries: 7, 30, 90 must succeed.
    for n in (7, 30, 90):
        batch = pkt.build_kpi_trend_batch(
            portfolio_config=synthetic_portfolio_config,
            workspace_root=ws,
            now=fixed_now,
            period_days=n,
        )
        assert batch.period_days == n
        # daily axis length == period_days for every project.
        for t in batch.projects:
            assert len(t.daily) == n, (
                f"period_days={n} expected {n} daily buckets, "
                f"got {len(t.daily)}"
            )


# ---------------------------------------------------------------------------
# Test 3 — Multi-project time series merge (3 projects, mixed master.xlsx +
#          events.jsonl presence, deterministic order, totals correct)
# ---------------------------------------------------------------------------

def test_multi_project_time_series_merge(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """3 projects with different created_date / done_date / events
    distributions. Aggregation must merge cleanly + sort deterministically
    by (priority, slug)."""
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / slug / "_state").mkdir(parents=True)

    # alpha-test: 1 work event in window.
    in_window_evt = {
        "schema_version": "1.0",
        "event_kind": "work",
        "event_id": "work_T-0001_20260420T1030",
        "timestamp": "2026-04-20T10:30:00Z",
        "project_id": "alpha-test",
        "event_type": "content_new",
    }
    (ws / "alpha-test" / "_state" / "events.jsonl").write_text(
        json.dumps(in_window_evt) + "\n", encoding="utf-8",
    )
    # beta-test: 2 work events of different types in window.
    beta_evts = [
        {
            "schema_version": "1.0",
            "event_kind": "work",
            "event_id": "work_T-0010_20260425T0900",
            "timestamp": "2026-04-25T09:00:00Z",
            "project_id": "beta-test",
            "event_type": "tech_fix",
        },
        {
            "schema_version": "1.0",
            "event_kind": "work",
            "event_id": "work_T-0011_20260427T1100",
            "timestamp": "2026-04-27T11:00:00Z",
            "project_id": "beta-test",
            "event_type": "quickwin_applied",
        },
    ]
    (ws / "beta-test" / "_state" / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in beta_evts) + "\n",
        encoding="utf-8",
    )
    # gamma-test: events.jsonl contains a single OUT-of-window event.
    out_evt = {
        "schema_version": "1.0",
        "event_kind": "work",
        "event_id": "work_T-9999_20250101T0000",
        "timestamp": "2025-01-01T00:00:00Z",
        "project_id": "gamma-test",
        "event_type": "manual",
    }
    (ws / "gamma-test" / "_state" / "events.jsonl").write_text(
        json.dumps(out_evt) + "\n", encoding="utf-8",
    )

    batch = pkt.build_kpi_trend_batch(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        period_days=30,
    )

    # Deterministic order — by (priority, slug).
    slugs_in_order = [t.slug for t in batch.projects]
    assert slugs_in_order == ["alpha-test", "beta-test", "gamma-test"], (
        f"projects must sort by (priority, slug), got {slugs_in_order}"
    )

    by_slug = {t.slug: t for t in batch.projects}
    # alpha-test: 1 in-window event of type content_new.
    assert by_slug["alpha-test"].event_type_buckets["content_new"] == 1
    # beta-test: 1 tech_fix + 1 quickwin_applied in-window.
    assert by_slug["beta-test"].event_type_buckets["tech_fix"] == 1
    assert by_slug["beta-test"].event_type_buckets["quickwin_applied"] == 1
    # gamma-test: 0 in-window (the only event is dated 2025-01-01).
    for k in pkt.EVENT_TYPE_ENUM:
        assert by_slug["gamma-test"].event_type_buckets[k] == 0

    # Portfolio-wide totals.
    assert batch.totals_work_events == 3
    assert batch.totals_event_type_buckets["content_new"] == 1
    assert batch.totals_event_type_buckets["tech_fix"] == 1
    assert batch.totals_event_type_buckets["quickwin_applied"] == 1

    # Idempotency: re-run with identical inputs → byte-stable output.
    batch2 = pkt.build_kpi_trend_batch(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        period_days=30,
    )
    snap1 = json.dumps(pkt.build_snapshot(batch), sort_keys=True)
    snap2 = json.dumps(pkt.build_snapshot(batch2), sort_keys=True)
    assert snap1 == snap2, "build_kpi_trend_batch must be idempotent"


# ---------------------------------------------------------------------------
# Test 4 — Empty events.jsonl tolerance + trend line continuity (no gaps)
# ---------------------------------------------------------------------------

def test_empty_events_tolerance_and_trend_line_continuity(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """When events.jsonl is missing OR empty, project must surface as a
    zero-events entry — NOT crash, NOT skip silently. The daily axis
    must still be fully populated (no gaps between period_start and
    period_end)."""
    ws = tmp_path / "workspace"
    # alpha-test: NO events.jsonl file at all.
    (ws / "alpha-test" / "_state").mkdir(parents=True)
    # beta-test: empty events.jsonl.
    (ws / "beta-test" / "_state").mkdir(parents=True)
    (ws / "beta-test" / "_state" / "events.jsonl").write_text(
        "", encoding="utf-8",
    )
    # gamma-test: events.jsonl with malformed lines (defensive parse).
    (ws / "gamma-test" / "_state").mkdir(parents=True)
    (ws / "gamma-test" / "_state" / "events.jsonl").write_text(
        "{not-json\n\n", encoding="utf-8",
    )

    batch = pkt.build_kpi_trend_batch(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        period_days=30,
    )
    assert len(batch.projects) == 3

    # Trend line continuity — every project has a contiguous date axis
    # of exactly period_days entries with no gaps.
    period_start = (fixed_now.date() - timedelta(days=29)).isoformat()
    period_end = fixed_now.date().isoformat()
    assert batch.period_start == period_start
    assert batch.period_end == period_end

    for t in batch.projects:
        assert len(t.daily) == 30
        # Days are strictly sequential (no gaps, no duplicates).
        days_seen = [b.day for b in t.daily]
        assert days_seen[0] == period_start
        assert days_seen[-1] == period_end
        # Each step is +1 day.
        for i in range(1, len(days_seen)):
            prev = datetime.fromisoformat(days_seen[i - 1]).date()
            cur = datetime.fromisoformat(days_seen[i]).date()
            assert (cur - prev).days == 1, (
                f"trend line gap between {prev} and {cur}"
            )
        # All counts zero (no in-window events anywhere).
        assert all(b.tasks_added == 0 for b in t.daily)
        assert all(b.tasks_done == 0 for b in t.daily)
        assert all(b.work_events_total == 0 for b in t.daily)

    # Totals reflect the zero-events tolerance.
    assert batch.totals_tasks_added == 0
    assert batch.totals_tasks_done == 0
    assert batch.totals_work_events == 0


# ---------------------------------------------------------------------------
# Test 5 — event_type 10 enum coverage (every enum value gets a bucket)
# ---------------------------------------------------------------------------

def test_event_type_10_enum_coverage(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """Worker brief Gate: every event_type in the closed 10 enum must
    appear as a bucket key in per-project + portfolio-wide totals."""
    ws = tmp_path / "workspace"
    # Use only alpha-test; emit one event of EACH event_type IN-window.
    (ws / "alpha-test" / "_state").mkdir(parents=True)
    in_window_day = (fixed_now - timedelta(days=5)).date()
    lines = []
    for i, et in enumerate(pkt.EVENT_TYPE_ENUM):
        lines.append(json.dumps({
            "schema_version": "1.0",
            "event_kind": "work",
            "event_id": f"work_T-{i:04d}_inwindow",
            "timestamp": (
                datetime.combine(
                    in_window_day,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ).isoformat().replace("+00:00", "Z")
            ),
            "project_id": "alpha-test",
            "event_type": et,
        }))
    (ws / "alpha-test" / "_state" / "events.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8",
    )
    # beta-test, gamma-test: empty events.jsonl.
    for slug in ("beta-test", "gamma-test"):
        (ws / slug / "_state").mkdir(parents=True)
        (ws / slug / "_state" / "events.jsonl").write_text(
            "", encoding="utf-8",
        )

    batch = pkt.build_kpi_trend_batch(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        period_days=30,
    )
    by_slug = {t.slug: t for t in batch.projects}

    # Every enum value present as a bucket key on alpha-test (count=1).
    for et in pkt.EVENT_TYPE_ENUM:
        assert et in by_slug["alpha-test"].event_type_buckets, (
            f"event_type {et!r} bucket missing on alpha-test"
        )
        assert by_slug["alpha-test"].event_type_buckets[et] == 1

    # Every enum value present on beta-test + gamma-test (count=0).
    for slug in ("beta-test", "gamma-test"):
        for et in pkt.EVENT_TYPE_ENUM:
            assert et in by_slug[slug].event_type_buckets
            assert by_slug[slug].event_type_buckets[et] == 0

    # Portfolio-wide totals: every enum value present, count = 1.
    for et in pkt.EVENT_TYPE_ENUM:
        assert et in batch.totals_event_type_buckets
        assert batch.totals_event_type_buckets[et] == 1

    # 10 enum coverage assertion at the schema-authority level: the
    # transform's EVENT_TYPE_ENUM constant matches the events.schema.json
    # event_type enum verbatim.
    events_schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text("utf-8")
    )
    schema_enum = events_schema["properties"]["event_type"]["enum"]
    assert tuple(schema_enum) == pkt.EVENT_TYPE_ENUM, (
        f"transform EVENT_TYPE_ENUM drifted from events.schema.json: "
        f"transform={pkt.EVENT_TYPE_ENUM} schema={tuple(schema_enum)}"
    )

    # Totals bucket count exactly 10 (no extras, no missing).
    assert len(
        [k for k in batch.totals_event_type_buckets
         if k in pkt.EVENT_TYPE_ENUM]
    ) == 10

    # Render smoke — markdown surfaces the event_type density table.
    rendered = pkt.render_report_markdown(
        batch=batch, template_path=TEMPLATE_PATH,
    )
    for et in pkt.EVENT_TYPE_ENUM:
        assert f"`{et}`" in rendered, (
            f"event_type {et!r} missing from rendered markdown"
        )
    # Report header surfaces the period.
    assert batch.period_start in rendered
    assert batch.period_end in rendered
    # LOCAL approximation transparency note in markdown.
    assert "LOCAL approximation" in rendered


# ---------------------------------------------------------------------------
# Test 6 — Forbidden tokens guard (4 tokens + 8 obfuscated slugs) +
#          assert_read_only_module helper (W-E3 paterni reuse) +
#          plugin agnostik
# ---------------------------------------------------------------------------

def test_no_forbidden_tokens_and_read_only_module() -> None:
    """Per worker brief Gates 6 + 11: transform + SKILL.md + template
    must contain ZERO occurrences of the 4 forbidden tokens AND ZERO
    real-client slug literals. assert_read_only_module() must NOT
    raise (W-E3 helper grep guard reuse)."""
    transform_src = TRANSFORM_PATH.read_text(encoding="utf-8")
    skill_src = SKILL_PATH.read_text(encoding="utf-8")
    template_src = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Tokens 1-3: literal grep CLEAN. Assembled at runtime so this
    # test file itself stays grep-clean against its own assertion.
    forbidden_literal = (
        "estimated_credits" + "_per_call",
        "estimated_credits" + "_per_url",
        "metric" + "_name",
    )
    for body, label in (
        (transform_src, "transform"),
        (skill_src, "skill"),
        (template_src, "template"),
    ):
        for tok in forbidden_literal:
            assert tok not in body, (
                f"forbidden token {tok!r} found in {label}"
            )

    # Token 4: TODO inline-comment marker in CODE (transform). The
    # markdown skill prose may use the word legitimately ("TODO/fallback
    # YASAK"), but the transform .py must be free of TODO comments.
    todo_in_transform = re.findall(r"#\s*TODO\b", transform_src)
    assert not todo_in_transform, (
        f"TODO comment(s) found in transform: {todo_in_transform}"
    )

    # 8 obfuscated client slug literals (base64-encoded so this test
    # doesn't trip its own grep guard). Mirrors W-E4 paterni.
    encoded_slug_tokens = (
        b"ZGVudG5vdGlvbg==", b"dmVudG8=", b"ZXlrb20=", b"YmlnY2F0dHI=",
        b"Y2FsaXR0ZQ==", b"bGFzdGlrc2E=", b"bm9yYW5pbnNhYXQ=",
        b"YWRzdGFyaw==",
    )
    forbidden_slugs = tuple(
        base64.b64decode(t).decode("ascii") for t in encoded_slug_tokens
    )
    pattern = re.compile(
        r"\b(" + "|".join(forbidden_slugs) + r")\b",
        flags=re.IGNORECASE,
    )
    for body, label in (
        (transform_src, "transform"),
        (skill_src, "skill"),
        (template_src, "template"),
    ):
        m = pattern.search(body)
        assert m is None, (
            f"forbidden hardcoded slug {m.group(0)!r} found in {label}"
        )

    # Gate 11: assert_read_only_module() helper must NOT raise (W-E3
    # paterni reuse). Independently re-grep so the test is robust if
    # the helper itself is later refactored.
    pkt.assert_read_only_module()
    write_call_patterns = [
        "." + "save(",
        "transaction" + "." + "append(",
        "transaction" + "." + "update(",
        "transaction" + "." + "delete(",
        "events_writer" + "." + "append_",
    ]
    for pat in write_call_patterns:
        assert pat not in transform_src, (
            f"forbidden write pattern {pat!r} appears verbatim in "
            "portfolio_kpi_trend.py — read-only contract violated."
        )

    # No `scripts.excel.transaction` or `scripts.state.events_writer`
    # imports either (writer-side modules).
    forbidden_imports = (
        r"^\s*from\s+scripts\.excel\.transaction\b",
        r"^\s*import\s+scripts\.excel\.transaction\b",
        r"^\s*from\s+scripts\.state\.events_writer\b",
        r"^\s*import\s+scripts\.state\.events_writer\b",
    )
    for pat in forbidden_imports:
        assert not re.search(pat, transform_src, flags=re.MULTILINE), (
            f"forbidden import pattern matched in transform: {pat}"
        )


# ---------------------------------------------------------------------------
# Test 7 — W-E4 path convention compliance: outputs[] entries declare
#          projects/_portfolio/{outputs,inbox}/local/ + the transform
#          honours PSEO_WORKSPACE_ROOT env var
# ---------------------------------------------------------------------------

def test_path_convention_and_pseo_workspace_root_env(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
    monkeypatch: pytest.MonkeyPatch,
    skill_frontmatter: dict,
) -> None:
    """Per worker brief Gate 10: outputs[] entries must declare the
    projects/_portfolio/ literal path; transform must resolve
    PSEO_WORKSPACE_ROOT env var when no explicit arg is passed."""
    # Outputs path convention.
    outputs = skill_frontmatter["outputs"]
    report_outputs = [o for o in outputs if "portfolio-kpi-trend.md" in o]
    snap_outputs = [o for o in outputs if "portfolio-kpi-trend.json" in o]
    assert report_outputs, f"report output missing: {outputs}"
    assert snap_outputs, f"snapshot output missing: {outputs}"
    assert report_outputs[0].startswith("projects/_portfolio/"), (
        f"report path must start with projects/_portfolio/: "
        f"{report_outputs[0]!r}"
    )
    assert "outputs/reports/" in report_outputs[0]
    assert snap_outputs[0].startswith("projects/_portfolio/"), (
        f"snapshot path must start with projects/_portfolio/: "
        f"{snap_outputs[0]!r}"
    )
    assert "inbox/local/" in snap_outputs[0]

    # PSEO_WORKSPACE_ROOT env var resolution.
    ws = tmp_path / "workspace"
    ws.mkdir()
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / slug / "_state").mkdir(parents=True)
        (ws / slug / "_state" / "events.jsonl").write_text(
            "", encoding="utf-8",
        )

    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    resolved = pkt._resolve_workspace_root(None)
    assert resolved == ws.resolve()

    # When env var is unset AND no arg → DURUR.
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    with pytest.raises(pkt.WorkspaceRootUnsetError):
        pkt._resolve_workspace_root(None)

    # Re-set the env var and run an end-to-end build using it.
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    batch = pkt.build_kpi_trend_batch(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=pkt._resolve_workspace_root(None),
        now=fixed_now,
        period_days=14,
    )
    assert batch.period_days == 14
    assert len(batch.projects) == 3


# ---------------------------------------------------------------------------
# Test 8 — Smoke E2E: synthetic config → snapshot + report files, parse +
#          schema validation cleanly + portfolio-config schema validate
# ---------------------------------------------------------------------------

def test_smoke_e2e_pipeline_and_portfolio_config_validate(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    portfolio_config_schema: dict,
    fixed_now: datetime,
) -> None:
    """End-to-end smoke: schema validation pass, build batch, snapshot
    JSON-serialisable, render markdown, ActiveProjectsCeilingError
    surfaces on > 8 entries."""
    # Portfolio config schema validate (positive).
    pkt.validate_portfolio_config(
        synthetic_portfolio_config, portfolio_config_schema,
    )

    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / slug / "_state").mkdir(parents=True)
        (ws / slug / "_state" / "events.jsonl").write_text(
            "", encoding="utf-8",
        )

    batch = pkt.build_kpi_trend_batch(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        period_days=30,
    )

    # Snapshot is JSON-serialisable + round-trips.
    snap = pkt.build_snapshot(batch)
    snap_text = json.dumps(
        snap, ensure_ascii=False, indent=2, sort_keys=True,
    )
    snap_round = json.loads(snap_text)
    assert snap_round["writer"] == pkt.WRITER_NAME == "portfolio_kpi_trend"
    assert snap_round["period_days"] == 30
    assert {p["slug"] for p in snap_round["projects"]} == {
        "alpha-test", "beta-test", "gamma-test",
    }
    # Each project snapshot has the gscTotals stub keys (LOCAL
    # approximation transparency).
    for p in snap_round["projects"]:
        for k in ("clicks", "impressions", "avg_position", "ctr"):
            assert k in p["gsc_totals_stub"], (
                f"gsc_totals_stub missing key {k!r} on {p['slug']}"
            )
        # All stub values are zero (sentinel).
        assert p["gsc_totals_stub"]["clicks"] == 0
        assert p["gsc_totals_stub"]["impressions"] == 0

    # Markdown render — no missing template variables.
    rendered = pkt.render_report_markdown(
        batch=batch, template_path=TEMPLATE_PATH,
    )
    assert "Portföy KPI Trend" in rendered
    assert "scope: portfolio-kpi-trend" in rendered
    assert "period_days: 30" in rendered
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        assert f"`{slug}`" in rendered

    # Negative: > 8 active_projects triggers ActiveProjectsCeilingError.
    over_capacity = dict(synthetic_portfolio_config)
    over_capacity["active_projects"] = [
        {
            "slug": f"proj-{i}",
            "workspace_path": f"proj-{i}",
            "profile": ["b2b-saas"],
            "priority": i,
        }
        for i in range(1, 10)  # 9 entries > 8 ceiling
    ]
    with pytest.raises(
        (pkt.ActiveProjectsCeilingError, pkt.PortfolioConfigInvalidError),
    ):
        pkt.validate_portfolio_config(over_capacity, portfolio_config_schema)

    # build_kpi_trend_batch also surfaces ActiveProjectsCeilingError
    # (defensive even if jsonschema disabled).
    with pytest.raises(pkt.ActiveProjectsCeilingError):
        pkt.build_kpi_trend_batch(
            portfolio_config=over_capacity,
            workspace_root=ws,
            now=fixed_now,
            period_days=30,
        )

    # Naive `now` (no tzinfo) → DURUR.
    naive_now = datetime(2026, 5, 1, 10, 0, 0)
    with pytest.raises(pkt.PortfolioKpiTrendError):
        pkt.build_kpi_trend_batch(
            portfolio_config=synthetic_portfolio_config,
            workspace_root=ws,
            now=naive_now,
            period_days=30,
        )

    # Transform line count gate (< 600 per ADR-027).
    n_lines = TRANSFORM_PATH.read_text(encoding="utf-8").count("\n")
    assert n_lines < 600, (
        f"transform line count {n_lines} exceeds ADR-027 ceiling of 600"
    )
