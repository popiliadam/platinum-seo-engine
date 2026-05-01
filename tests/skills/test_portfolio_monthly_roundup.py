"""tests/skills/test_portfolio_monthly_roundup.py — Phase 9 W-E5 reporting skill.

Mirrors tests/skills/test_portfolio_weekly_brief.py (Phase 9 W-E4) +
tests/skills/test_portfolio_overview.py (Phase 9 W-E3). Frontmatter
parse + Draft 7 validate against schemas/skill-frontmatter.schema.json,
cadence.monthly_roundup branch validate against
schemas/portfolio-config.schema.json v1.1, EditorialOverrides
override precedence sentinel, override_rationale minLength 10
sentinel, multi-project KPI roll-up (3-project fixture), missing
project tolerance, 30-day events filter, natural_language >= 30 char,
forbidden tokens guard (4 tokens + 8 forbidden slugs), READ-ONLY
discipline, path convention (projects/_portfolio/ literal +
PSEO_WORKSPACE_ROOT env), idempotency contract.

This is a READ-ONLY reporting skill — no MCP, no DFS, no budget
pre-flight, no master.xlsx writes, no events.jsonl writes
(Q-RP-01 defer Phase 14).
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

from scripts.reporting import portfolio_monthly_roundup as pmr


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "reporting" / "portfolio-monthly-roundup" / "SKILL.md"
TRANSFORM_PATH = REPO_ROOT / "scripts" / "reporting" / "portfolio_monthly_roundup.py"
TEMPLATE_PATH = REPO_ROOT / "templates" / "reports" / "portfolio-monthly-roundup.template.md"


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
    """Parse the YAML frontmatter block of the portfolio-monthly-roundup SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_portfolio_config() -> dict:
    """Synthetic portfolio.config.json v1.1 with 3 active projects.
    The middle project carries an EditorialOverrides block (priority +
    cadence + override_rationale) used by the precedence sentinel."""
    return {
        "schema_version": "1.1",
        "portfolio_id": "test-portfolio",
        "display_name": "Test Portfolio",
        "active_projects": [
            {
                "slug": "alpha-test",
                "workspace_path": "alpha-test",
                "profile": ["b2b-saas"],
                "priority": 5,
                "last_sync_at": "2026-04-30T10:00:00Z",
            },
            {
                "slug": "beta-test",
                "workspace_path": "beta-test",
                "profile": ["e-commerce"],
                "priority": 5,  # same as alpha; override drops it to 1
                "editorial_overrides": {
                    "priority": 1,
                    "cadence": "biweekly",
                    "sla_days": 14,
                    "override_rationale": "Q2 launch campaign — temporary cadence boost",
                    "ramp_plan": "revisit after 2026-07 launch",
                },
            },
            {
                "slug": "gamma-test",
                "workspace_path": "gamma-test",
                "profile": ["local-service"],
                "priority": 9,
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
    }


@pytest.fixture
def fixed_now() -> datetime:
    """Deterministic 'now' for reproducible test runs (UTC)."""
    return datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter validates + natural_language >= 30 char
# ---------------------------------------------------------------------------

def test_frontmatter_validates_and_natural_language_min_length(
    skill_frontmatter: dict, skill_frontmatter_schema: dict,
) -> None:
    fm = skill_frontmatter
    assert fm["name"] == "portfolio-monthly-roundup"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"
    assert fm["category"] == "reporting"

    # Manual triggers EMPTY (per worker brief: NO slash command).
    assert fm["triggers"]["manual"] == []

    # natural_language sentinel: >= 30 char.
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str)
    assert len(nl) >= 30, (
        f"natural_language must be >= 30 char, got {len(nl)}"
    )
    # Required TR + EN trigger phrases per worker brief.
    for required in (
        "aylık portföy", "portfolio monthly roundup", "tüm projeler aylık",
    ):
        assert required in nl, f"missing trigger phrase: {required!r}"

    # outputs[] — exactly 3 entries (master.xlsx#none + report + snapshot).
    outputs = fm["outputs"]
    assert "master.xlsx#none" in outputs
    assert any("portfolio-monthly-roundup.md" in o for o in outputs)
    assert any("portfolio-monthly-roundup.json" in o for o in outputs)
    # NO events.jsonl (Q-RP-01 defer).
    assert all("events.jsonl" not in o for o in outputs), (
        "Q-RP-01 defer: events.jsonl must NOT be in outputs[]"
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

    # Full Draft 7 validation.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(
        validator.iter_errors(fm), key=lambda e: list(e.absolute_path),
    )
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — cadence.monthly_roundup schema validate (day_of_month + hour)
# ---------------------------------------------------------------------------

def test_cadence_monthly_roundup_schema_validate(
    synthetic_portfolio_config: dict,
    portfolio_config_schema: dict,
) -> None:
    """The synthetic config validates against portfolio-config.schema.json
    v1.1. The transform's _validate_cadence_monthly raises on drift
    (out-of-range day_of_month, out-of-range hour)."""
    validator = Draft7Validator(portfolio_config_schema)
    errs = sorted(
        validator.iter_errors(synthetic_portfolio_config),
        key=lambda e: list(e.absolute_path),
    )
    assert not errs, (
        f"synthetic portfolio config drifted from schema: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )

    # Positive: validator accepts the synthetic shape.
    pmr._validate_cadence_monthly(synthetic_portfolio_config["cadence"])

    # Negative: out-of-range day_of_month (32) → DURUR.
    bad_dom = {
        "weekly_brief": {"day": "Friday", "hour": 9},
        "monthly_roundup": {"day_of_month": 32, "hour": 10},
    }
    with pytest.raises(pmr.PortfolioConfigSchemaError) as ei:
        pmr._validate_cadence_monthly(bad_dom)
    assert "32" in str(ei.value)

    # Negative: out-of-range day_of_month (0) → DURUR.
    with pytest.raises(pmr.PortfolioConfigSchemaError):
        pmr._validate_cadence_monthly({
            "weekly_brief": {"day": "Friday", "hour": 9},
            "monthly_roundup": {"day_of_month": 0, "hour": 10},
        })

    # Negative: out-of-range hour (24) → DURUR.
    with pytest.raises(pmr.PortfolioConfigSchemaError) as ei:
        pmr._validate_cadence_monthly({
            "weekly_brief": {"day": "Friday", "hour": 9},
            "monthly_roundup": {"day_of_month": 1, "hour": 24},
        })
    assert "24" in str(ei.value)

    # Negative: out-of-range hour (-1) → DURUR.
    with pytest.raises(pmr.PortfolioConfigSchemaError):
        pmr._validate_cadence_monthly({
            "weekly_brief": {"day": "Friday", "hour": 9},
            "monthly_roundup": {"day_of_month": 1, "hour": -1},
        })


# ---------------------------------------------------------------------------
# Test 3 — EditorialOverrides override precedence sentinel +
#          override_rationale minLength 10 sentinel (CRITICAL)
# ---------------------------------------------------------------------------

def test_editorial_overrides_precedence_and_rationale_minlen() -> None:
    """The KEY load-bearing tests for this skill:
      (a) per-project EditorialOverrides override portfolio-wide defaults
          (precedence: editorial_overrides.priority beats entry.priority,
          editorial_overrides.cadence beats default 'monthly',
          editorial_overrides.sla_days beats portfolio sla_days);
      (b) override_rationale minLength 10 — a 9-char rationale must be
          rejected with EditorialOverrideRationaleError when ANY override
          field is set; 10-char OK; missing rationale also rejected.
    """
    portfolio_default_sla = 7

    # (a-1) No editorial_overrides → all defaults flow through.
    entry_no_eo = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 7,
    }
    r = pmr.resolve_editorial_overrides(
        entry_no_eo, portfolio_sla_days=portfolio_default_sla,
    )
    assert r.has_override is False
    assert r.effective_priority == 7
    assert r.effective_cadence == pmr.DEFAULT_CADENCE == "monthly"
    assert r.effective_sla_days == 7
    assert r.override_rationale == ""
    assert r.ramp_plan == ""

    # (a-2) editorial_overrides.priority overrides entry.priority.
    entry_with_pri_override = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 7,
        "editorial_overrides": {
            "priority": 1,
            "override_rationale": "load-bearing precedence test entry",
        },
    }
    r = pmr.resolve_editorial_overrides(
        entry_with_pri_override, portfolio_sla_days=portfolio_default_sla,
    )
    assert r.has_override is True
    assert r.effective_priority == 1, (
        "editorial_overrides.priority must override entry.priority"
    )
    assert r.effective_sla_days == 7  # unchanged

    # (a-3) editorial_overrides.sla_days overrides portfolio default.
    entry_with_sla_override = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 5,
        "editorial_overrides": {
            "sla_days": 14,
            "override_rationale": "SLA override for Q2 ramp window",
        },
    }
    r = pmr.resolve_editorial_overrides(
        entry_with_sla_override, portfolio_sla_days=portfolio_default_sla,
    )
    assert r.effective_sla_days == 14, (
        "editorial_overrides.sla_days must override portfolio sla_days"
    )

    # (a-4) editorial_overrides.cadence overrides default.
    entry_with_cadence = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 5,
        "editorial_overrides": {
            "cadence": "biweekly",
            "override_rationale": "cadence reduction test entry",
        },
    }
    r = pmr.resolve_editorial_overrides(
        entry_with_cadence, portfolio_sla_days=portfolio_default_sla,
    )
    assert r.effective_cadence == "biweekly"

    # (b-1) override_rationale 9 chars → REJECTED.
    bad_rationale_short = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 5,
        "editorial_overrides": {
            "priority": 1,
            "override_rationale": "9-char-x",  # 8 chars actually but <10
        },
    }
    with pytest.raises(pmr.EditorialOverrideRationaleError):
        pmr.resolve_editorial_overrides(
            bad_rationale_short, portfolio_sla_days=portfolio_default_sla,
        )

    # (b-2) Exactly 9 chars → REJECTED (boundary sentinel).
    nine_char = "x" * 9
    assert len(nine_char) == 9
    bad_nine = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 5,
        "editorial_overrides": {
            "priority": 1,
            "override_rationale": nine_char,
        },
    }
    with pytest.raises(pmr.EditorialOverrideRationaleError):
        pmr.resolve_editorial_overrides(
            bad_nine, portfolio_sla_days=portfolio_default_sla,
        )

    # (b-3) Exactly 10 chars → ACCEPTED.
    ten_char = "x" * 10
    assert len(ten_char) == 10
    ok_ten = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 5,
        "editorial_overrides": {
            "priority": 1,
            "override_rationale": ten_char,
        },
    }
    r = pmr.resolve_editorial_overrides(
        ok_ten, portfolio_sla_days=portfolio_default_sla,
    )
    assert r.has_override is True
    assert r.override_rationale == ten_char

    # (b-4) Missing rationale + override field → REJECTED.
    missing = {
        "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
        "priority": 5,
        "editorial_overrides": {"priority": 1},
    }
    with pytest.raises(pmr.EditorialOverrideRationaleError):
        pmr.resolve_editorial_overrides(
            missing, portfolio_sla_days=portfolio_default_sla,
        )

    # (b-5) Out-of-range priority → DURUR PortfolioConfigSchemaError.
    with pytest.raises(pmr.PortfolioConfigSchemaError):
        pmr.resolve_editorial_overrides(
            {
                "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
                "priority": 5,
                "editorial_overrides": {
                    "priority": 11,  # max 10
                    "override_rationale": "out of range priority test",
                },
            },
            portfolio_sla_days=portfolio_default_sla,
        )

    # (b-6) Out-of-range sla_days → DURUR.
    with pytest.raises(pmr.PortfolioConfigSchemaError):
        pmr.resolve_editorial_overrides(
            {
                "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
                "priority": 5,
                "editorial_overrides": {
                    "sla_days": 31,  # max 30
                    "override_rationale": "out of range sla days test",
                },
            },
            portfolio_sla_days=portfolio_default_sla,
        )

    # (b-7) Bad cadence enum → DURUR.
    with pytest.raises(pmr.PortfolioConfigSchemaError):
        pmr.resolve_editorial_overrides(
            {
                "slug": "x", "workspace_path": "x", "profile": ["b2b-saas"],
                "priority": 5,
                "editorial_overrides": {
                    "cadence": "daily",  # not in [weekly, biweekly, monthly]
                    "override_rationale": "bad cadence enum test entry",
                },
            },
            portfolio_sla_days=portfolio_default_sla,
        )


# ---------------------------------------------------------------------------
# Test 4 — Multi-project KPI roll-up (3-project fixture, deterministic)
# ---------------------------------------------------------------------------

def test_multi_project_kpi_rollup(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """3-project fixture with an EditorialOverrides on the middle project.
    Asserts:
      - all 3 projects surfaced (no silent skip);
      - deterministic ordering by (effective_priority, slug);
      - beta-test (override priority=1) sorts FIRST despite slug 'b';
      - alpha-test (priority=5) sorts SECOND;
      - gamma-test (priority=9) sorts LAST.
    """
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / "projects" / slug / "_state").mkdir(parents=True)
        (ws / "projects" / slug / "_state" / "events.jsonl").write_text(
            "", encoding="utf-8",
        )

    roundup = pmr.build_portfolio_roundup(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws, now=fixed_now, period_end="2026-05-01",
    )

    slugs_in_order = [r.slug for r in roundup.projects]
    assert len(slugs_in_order) == 3, (
        "all 3 projects must be surfaced (no silent skip)"
    )
    # Effective priority order: beta(1) < alpha(5) < gamma(9).
    assert slugs_in_order == ["beta-test", "alpha-test", "gamma-test"], (
        f"expected beta-test FIRST due to override priority=1, got "
        f"{slugs_in_order}"
    )

    # The middle project's overrides_resolved is populated correctly.
    by_slug = {r.slug: r for r in roundup.projects}
    beta = by_slug["beta-test"]
    assert beta.overrides.has_override is True
    assert beta.overrides.effective_priority == 1
    assert beta.overrides.effective_cadence == "biweekly"
    assert beta.overrides.effective_sla_days == 14
    assert "Q2 launch campaign" in beta.overrides.override_rationale
    assert "revisit after" in beta.overrides.ramp_plan

    # alpha + gamma have no overrides.
    assert by_slug["alpha-test"].overrides.has_override is False
    assert by_slug["alpha-test"].overrides.effective_cadence == "monthly"
    assert by_slug["gamma-test"].overrides.has_override is False

    # Period window: 30 days ending 2026-05-01.
    assert roundup.period_end == "2026-05-01"
    assert roundup.period_start == "2026-04-02"
    assert (datetime.fromisoformat(roundup.period_end)
            - datetime.fromisoformat(roundup.period_start)).days == 29

    # Render Markdown smoke — multi-project table + EditorialOverrides
    # notes section both render.
    rendered = pmr.render_roundup_markdown(
        roundup=roundup, template_path=TEMPLATE_PATH,
    )
    assert "alpha-test" in rendered
    assert "beta-test" in rendered
    assert "gamma-test" in rendered
    assert "biweekly" in rendered, (
        "EditorialOverrides cadence override must surface in markdown"
    )
    assert "Q2 launch campaign" in rendered, (
        "override_rationale must surface in EditorialOverrides notes"
    )
    # Snapshot is JSON-serialisable + idempotent.
    snap1 = json.dumps(pmr.build_snapshot(roundup), sort_keys=True)
    roundup2 = pmr.build_portfolio_roundup(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws, now=fixed_now, period_end="2026-05-01",
    )
    snap2 = json.dumps(pmr.build_snapshot(roundup2), sort_keys=True)
    assert snap1 == snap2, "build_portfolio_roundup must be idempotent"


# ---------------------------------------------------------------------------
# Test 5 — Missing project tolerance (graceful skip, not crash)
# ---------------------------------------------------------------------------

def test_missing_project_tolerance(
    tmp_path: Path, synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """When per-project master.xlsx + events.jsonl are absent, the
    project surfaces as a warning entry (NOT crash, NOT silent skip).
    skipped_projects total reflects the count of projects without
    master.xlsx."""
    # Only create alpha-test; beta + gamma have no project root at all.
    ws = tmp_path / "workspace"
    (ws / "projects" / "alpha-test" / "_state").mkdir(parents=True)
    (ws / "projects" / "alpha-test" / "_state" / "events.jsonl"
     ).write_text("", encoding="utf-8")

    roundup = pmr.build_portfolio_roundup(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws, now=fixed_now, period_end="2026-05-01",
    )
    # Still 3 projects surfaced.
    assert len(roundup.projects) == 3
    # All 3 are skipped (no master.xlsx).
    assert roundup.skipped_projects == 3
    by_slug = {r.slug: r for r in roundup.projects}
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        r = by_slug[slug]
        assert r.master_xlsx_path is None
        assert r.warnings, (
            f"{slug} should surface a warning when master.xlsx is missing"
        )
        # Empty completed counts.
        for k in ("tech_seo_done", "content_revised", "new_content"):
            assert r.completed_counts.get(k, 0) == 0


# ---------------------------------------------------------------------------
# Test 6 — 30-day events.jsonl filter sentinel (in-window vs out-of-window)
# ---------------------------------------------------------------------------

def test_thirty_day_events_filter_sentinel(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """events.jsonl entries OUTSIDE the 30-day window must NOT be counted
    in work_events. Entries INSIDE the window are counted.

    Window for period_end=2026-05-01: 2026-04-02 .. 2026-05-01 inclusive.
    Sentinel:
      - in-window timestamp (2026-04-15) → COUNTED
      - out-of-window timestamp (2026-01-01, 4 months back) → SKIPPED
    """
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / "projects" / slug / "_state").mkdir(parents=True)

    in_window = {
        "schema_version": "1.0",
        "event_kind": "work",
        "event_id": "work_T-0001_20260415T0000",
        "timestamp": "2026-04-15T00:00:00Z",
        "project_id": "alpha-test",
    }
    out_of_window = {
        "schema_version": "1.0",
        "event_kind": "work",
        "event_id": "work_T-9999_20260101T0000",
        "timestamp": "2026-01-01T00:00:00Z",
        "project_id": "alpha-test",
    }
    other_kind = {
        "schema_version": "1.0",
        "event_kind": "provenance",  # NOT work-kind
        "event_id": "prov_T-0002_20260415T0000",
        "timestamp": "2026-04-15T00:00:00Z",
        "project_id": "alpha-test",
    }

    (ws / "projects" / "alpha-test" / "_state" / "events.jsonl").write_text(
        json.dumps(in_window) + "\n"
        + json.dumps(out_of_window) + "\n"
        + json.dumps(other_kind) + "\n",
        encoding="utf-8",
    )
    # beta + gamma: empty events.jsonl
    (ws / "projects" / "beta-test" / "_state" / "events.jsonl").write_text(
        "", encoding="utf-8",
    )
    (ws / "projects" / "gamma-test" / "_state" / "events.jsonl").write_text(
        "", encoding="utf-8",
    )

    roundup = pmr.build_portfolio_roundup(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws, now=fixed_now, period_end="2026-05-01",
    )
    by_slug = {r.slug: r for r in roundup.projects}
    # alpha-test: 1 in-window work event, 0 from out-of-window or non-work.
    assert by_slug["alpha-test"].work_events == 1, (
        "out-of-window or non-work events must be excluded"
    )
    assert by_slug["beta-test"].work_events == 0
    assert by_slug["gamma-test"].work_events == 0
    assert roundup.totals_work_events == 1


# ---------------------------------------------------------------------------
# Test 7 — Forbidden tokens guard (4 tokens + 8 forbidden slugs)
# ---------------------------------------------------------------------------

def test_no_forbidden_tokens_in_skill() -> None:
    """Per worker brief gate #6: transform + SKILL.md + template + test
    must contain ZERO occurrences of:
      1. estimated_credits_per_call (Phase 7 lesson)
      2. estimated_credits_per_url  (Phase 7 lesson)
      3. metric_name                (Phase 7 closeout Q-CO-01 lesson)
      4. TODO comment in transform code (drift signature)

    Plus 8-slug forbidden plugin-agnostik list (OK in test fixtures,
    NOT in transform / SKILL.md / template).
    """
    transform_src = TRANSFORM_PATH.read_text(encoding="utf-8")
    skill_src = SKILL_PATH.read_text(encoding="utf-8")
    template_src = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Tokens 1-3: literal grep CLEAN across transform / SKILL.md / template.
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

    # Token 4: TODO inline-comment marker in transform code only.
    todo_pattern = re.compile(r"#\s*TODO\b")
    assert not todo_pattern.search(transform_src), (
        "TODO inline-comment marker found in transform code"
    )

    # 8 forbidden slugs (base64-encoded so this test file itself does not
    # trip the grep). Slugs OK in test fixtures only — they appear here
    # in encoded form, decoded for the search, and absent from
    # transform/skill/template.
    encoded_slug_tokens = (
        b"ZGVudG5vdGlvbg==", b"dmVudG8=", b"ZXlrb20=", b"YmlnY2F0dHI=",
        b"Y2FsaXR0ZQ==", b"bGFzdGlrc2E=", b"bm9yYW5pbnNhYXQ=", b"YWRzdGFyaw==",
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


# ---------------------------------------------------------------------------
# Test 8 — assert_read_only_module() helper grep guard (Gate #11)
# ---------------------------------------------------------------------------

def test_assert_read_only_module_grep_guard() -> None:
    """Per worker brief gate #11 (W-E3 paterni reuse): transform module
    must NOT contain any of: transaction.append( / transaction.update( /
    transaction.delete( / .save( / .delete( / events_writer.append.
    The helper greps the file's own source; tests invoke it directly +
    independently re-grep for robustness."""
    # Direct invocation — must NOT raise.
    pmr.assert_read_only_module()

    src = TRANSFORM_PATH.read_text(encoding="utf-8")
    forbidden = [
        # Patterns assembled at runtime so this test file ALSO does not
        # contain the literal write-call substrings (avoid self-trip).
        "." + "save(",
        "." + "delete(",
        "transaction" + "." + "append(",
        "transaction" + "." + "update(",
        "transaction" + "." + "delete(",
        "events_writer" + "." + "append",
    ]
    for pat in forbidden:
        assert pat not in src, (
            f"forbidden write pattern {pat!r} appears verbatim in "
            "portfolio_monthly_roundup.py source — read-only contract violated."
        )

    # Independent: no transaction / events_writer module imports.
    forbidden_imports = (
        r"^\s*from\s+scripts\.excel\.transaction\b",
        r"^\s*import\s+scripts\.excel\.transaction\b",
        r"^\s*from\s+scripts\.state\.events_writer\b",
        r"^\s*import\s+scripts\.state\.events_writer\b",
    )
    for pattern in forbidden_imports:
        assert not re.search(pattern, src, flags=re.MULTILINE), (
            f"forbidden import pattern matched in transform: {pattern}"
        )


# ---------------------------------------------------------------------------
# Test 9 — W-E4 path convention compliance: projects/_portfolio/ literal +
#          PSEO_WORKSPACE_ROOT env resolution (Gate #10)
# ---------------------------------------------------------------------------

def test_path_convention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per worker brief gate #10: SKILL.md outputs[] must reference
    'projects/_portfolio/{outputs,inbox}/local/' literal paths AND the
    transform must resolve workspace_root via PSEO_WORKSPACE_ROOT env.

    Asserts:
      (a) SKILL.md outputs[] contain the literal 'projects/_portfolio/'
          prefix for both report and snapshot;
      (b) _resolve_workspace_root respects explicit arg first;
      (c) _resolve_workspace_root falls back to PSEO_WORKSPACE_ROOT env;
      (d) _resolve_workspace_root falls back to .pse-workspace marker;
      (e) absent all 3 → WorkspaceRootUnsetError (DURUR).
    """
    skill_src = SKILL_PATH.read_text(encoding="utf-8")
    assert "projects/_portfolio/outputs/" in skill_src, (
        "SKILL.md outputs[] must declare projects/_portfolio/outputs/ literal"
    )
    assert "projects/_portfolio/inbox/" in skill_src, (
        "SKILL.md outputs[] must declare projects/_portfolio/inbox/ literal"
    )

    # (b) Explicit arg wins.
    explicit = tmp_path / "explicit-ws"
    explicit.mkdir()
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(tmp_path / "env-ws"))
    resolved = pmr._resolve_workspace_root(explicit)
    assert resolved == explicit.resolve()

    # (c) PSEO_WORKSPACE_ROOT env fallback.
    env_ws = tmp_path / "env-ws"
    env_ws.mkdir()
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(env_ws))
    resolved = pmr._resolve_workspace_root(None)
    assert resolved == env_ws.resolve()

    # (d) .pse-workspace marker fallback (env unset).
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    marker_ws = tmp_path / "marker-ws"
    marker_ws.mkdir()
    (marker_ws / ".pse-workspace").touch()
    sub = marker_ws / "sub" / "deeper"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    resolved = pmr._resolve_workspace_root(None)
    assert resolved == marker_ws.resolve()

    # (e) All 3 absent → DURUR.
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    bare = tmp_path / "no-marker"
    bare.mkdir()
    monkeypatch.chdir(bare)
    # Walk-up may still find a marker if tmp_path itself or parents have
    # one. Guard: only run the assertion when no marker is reachable.
    found_marker = any(
        (parent / ".pse-workspace").exists()
        for parent in (bare.resolve(), *bare.resolve().parents)
    )
    if not found_marker:
        with pytest.raises(pmr.WorkspaceRootUnsetError):
            pmr._resolve_workspace_root(None)


# ---------------------------------------------------------------------------
# Test 10 — Smoke E2E: synthetic config → CLI-equivalent pipeline →
#           snapshot + report + idempotency (byte-identical re-render)
# ---------------------------------------------------------------------------

def test_smoke_e2e_idempotent_pipeline(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """Smoke E2E mirroring the CLI flow: build a roundup, render Markdown,
    write the snapshot JSON, re-load both, assert the contracts.
    Idempotency: same inputs → byte-identical snapshot+report on re-run."""
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / "projects" / slug / "_state").mkdir(parents=True)
        (ws / "projects" / slug / "_state" / "events.jsonl").write_text(
            "", encoding="utf-8",
        )

    roundup = pmr.build_portfolio_roundup(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws, now=fixed_now, period_end="2026-05-01",
    )

    # Snapshot is JSON-serialisable + round-trips.
    snap = pmr.build_snapshot(roundup)
    snap_text = json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True)
    snap_round = json.loads(snap_text)
    assert snap_round["writer"] == pmr.WRITER_NAME == "portfolio_monthly_roundup"
    assert snap_round["period_end"] == "2026-05-01"
    assert snap_round["period_start"] == "2026-04-02"
    assert snap_round["totals"]["work_events"] == 0
    assert {p["slug"] for p in snap_round["projects"]} == {
        "alpha-test", "beta-test", "gamma-test",
    }
    # Snapshot project order matches PortfolioMonthlyRoundup.projects.
    assert [p["slug"] for p in snap_round["projects"]] == [
        "beta-test", "alpha-test", "gamma-test",
    ]
    # monthly_sections_subset is the 7-section list.
    assert snap_round["monthly_sections_subset"] == [
        "exec_summary", "keywords_up", "pages_up",
        "tech_seo_done", "content_revised", "new_content",
        "next_month_plan",
    ]
    # overrides_resolved present + correctly populated for beta-test.
    beta_snap = next(p for p in snap_round["projects"]
                     if p["slug"] == "beta-test")
    assert beta_snap["overrides_resolved"]["has_override"] is True
    assert beta_snap["overrides_resolved"]["effective_priority"] == 1
    assert beta_snap["overrides_resolved"]["effective_cadence"] == "biweekly"
    assert (
        len(beta_snap["overrides_resolved"]["override_rationale"])
        >= pmr.OVERRIDE_RATIONALE_MIN_LEN
    )

    # Markdown render — no missing template variables, frontmatter populated.
    rendered = pmr.render_roundup_markdown(
        roundup=roundup, template_path=TEMPLATE_PATH,
    )
    assert "Portföy Aylık Roundup" in rendered
    assert "2026-04-02 → 2026-05-01" in rendered
    # Multi-row KPI table renders all 3 projects + EditorialOverrides notes.
    assert "| alpha-test |" in rendered
    assert "| beta-test |" in rendered
    assert "| gamma-test |" in rendered
    # EditorialOverrides notes section renders override_rationale.
    assert "Q2 launch campaign" in rendered

    # Idempotency: re-run with identical inputs → byte-identical
    # snapshot AND report.
    roundup2 = pmr.build_portfolio_roundup(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws, now=fixed_now, period_end="2026-05-01",
    )
    snap_text2 = json.dumps(
        pmr.build_snapshot(roundup2), ensure_ascii=False, indent=2,
        sort_keys=True,
    )
    rendered2 = pmr.render_roundup_markdown(
        roundup=roundup2, template_path=TEMPLATE_PATH,
    )
    assert snap_text == snap_text2, (
        "snapshot must be byte-identical on re-run with identical inputs"
    )
    assert rendered == rendered2, (
        "report markdown must be byte-identical on re-run"
    )
