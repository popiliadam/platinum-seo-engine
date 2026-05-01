"""
tests/skills/test_portfolio_weekly_brief.py — Phase 9 W-E4 reporting skill.

Mirrors tests/skills/test_master_task_sync.py shape:
  - frontmatter parse + Draft 7 validate against
    schemas/skill-frontmatter.schema.json
  - cadence/sla branches validate against
    schemas/portfolio-config.schema.json v1.1
  - freshness flag stale/fresh sentinel (8-day-old + 7-day SLA → stale)
  - empty events.jsonl tolerance (project skipped without crashing)
  - cross-project delta merge (3 projects, mixed last_sync_at)
  - natural_language min length (≥ 30 char) sentinel
  - forbidden tokens guard (4 tokens, transform + skill, grep CLEAN)
  - plugin agnostik (no hardcoded slug literal in transform / skill)

This is a READ-ONLY reporting skill — no MCP, no DFS, no budget
pre-flight, no master.xlsx writes, no events.jsonl writes (REVIZE 3).
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

from scripts.reporting import portfolio_weekly_brief as pwb


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "reporting" / "portfolio-weekly-brief" / "SKILL.md"
TRANSFORM_PATH = REPO_ROOT / "scripts" / "reporting" / "portfolio_weekly_brief.py"
TEMPLATE_PATH = REPO_ROOT / "templates" / "reports" / "portfolio-weekly-brief.template.md"


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
    """Parse the YAML frontmatter block of the portfolio-weekly-brief SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_portfolio_config() -> dict:
    """Synthetic portfolio.config.json v1.1 with 3 active projects in
    different freshness bands. Slugs are intentionally generic test
    fixtures (NOT real client slugs)."""
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
                # 1-day-old → fresh against 7-day SLA.
                "last_sync_at": "2026-04-30T10:00:00Z",
            },
            {
                "slug": "beta-test",
                "workspace_path": "beta-test",
                "profile": ["e-commerce"],
                "priority": 2,
                # 8-day-old → stale against 7-day SLA (KEY sentinel).
                "last_sync_at": "2026-04-23T10:00:00Z",
            },
            {
                "slug": "gamma-test",
                "workspace_path": "gamma-test",
                "profile": ["local-service"],
                "priority": 3,
                # null → never synced → stale.
                "last_sync_at": None,
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
    """A deterministic 'now' for reproducible test runs (UTC)."""
    return datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter validates against skill-frontmatter.schema.json
#          + carries the natural_language ≥ 30 char sentinel
# ---------------------------------------------------------------------------

def test_frontmatter_validates_and_natural_language_min_length(
    skill_frontmatter: dict,
    skill_frontmatter_schema: dict,
) -> None:
    fm = skill_frontmatter
    assert fm["name"] == "portfolio-weekly-brief"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"
    assert fm["category"] == "reporting"

    # Manual triggers EMPTY (per worker brief: NO slash command).
    assert fm["triggers"]["manual"] == []

    # natural_language sentinel: ≥ 30 char.
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str)
    assert len(nl) >= 30, (
        f"natural_language must be ≥ 30 char, got {len(nl)}"
    )
    # Required TR + EN trigger phrases per worker brief.
    for required in (
        "haftalık portföy", "portfolio weekly",
        "tüm projeler haftalık", "haftalık brief",
    ):
        assert required in nl, f"missing trigger phrase: {required!r}"

    # outputs[] — exactly 3 entries (REVIZE 1: events.jsonl REMOVED).
    outputs = fm["outputs"]
    assert len(outputs) == 3, (
        f"REVIZE 1 contract: outputs must be 3 entries, got {outputs}"
    )
    assert "master.xlsx#none" in outputs
    assert any("portfolio-weekly-brief.md" in o for o in outputs)
    assert any("portfolio-weekly-brief.json" in o for o in outputs)
    assert "events.jsonl" not in outputs, (
        "REVIZE 3: events.jsonl must NOT be in outputs[]"
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
        validator.iter_errors(fm), key=lambda e: list(e.absolute_path)
    )
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — cadence.weekly_brief schema validate (day enum + hour range)
#          + sla.weekly_sync_max_days range 1-30
# ---------------------------------------------------------------------------

def test_cadence_and_sla_branches_schema_validate(
    synthetic_portfolio_config: dict,
    portfolio_config_schema: dict,
) -> None:
    """The synthetic config validates against portfolio-config.schema.json
    v1.1. The transform's _validate_cadence + _validate_sla raise on
    drift (out-of-enum day, out-of-range hour, out-of-range sla_days)."""
    validator = Draft7Validator(portfolio_config_schema)
    errs = sorted(
        validator.iter_errors(synthetic_portfolio_config),
        key=lambda e: list(e.absolute_path),
    )
    assert not errs, (
        f"synthetic portfolio config drifted from schema: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )

    # Positive: validators accept the synthetic shape.
    pwb._validate_cadence(synthetic_portfolio_config["cadence"])
    sla_days = pwb._validate_sla(synthetic_portfolio_config["slas"])
    assert sla_days == 7

    # Negative: out-of-enum day → DURUR.
    bad_cadence_day = {
        "weekly_brief": {"day": "Funday", "hour": 9},
        "monthly_roundup": {"day_of_month": 1, "hour": 10},
    }
    with pytest.raises(pwb.PortfolioConfigSchemaError) as ei:
        pwb._validate_cadence(bad_cadence_day)
    assert "Funday" in str(ei.value)

    # Negative: out-of-range hour → DURUR.
    bad_cadence_hour = {
        "weekly_brief": {"day": "Friday", "hour": 25},
        "monthly_roundup": {"day_of_month": 1, "hour": 10},
    }
    with pytest.raises(pwb.PortfolioConfigSchemaError) as ei:
        pwb._validate_cadence(bad_cadence_hour)
    assert "25" in str(ei.value)

    # Negative: out-of-range SLA days (>30) → DURUR.
    with pytest.raises(pwb.PortfolioConfigSchemaError):
        pwb._validate_sla({"weekly_sync_max_days": 31, "monthly_roundup_target_dom": 1})
    # Negative: out-of-range SLA days (<1) → DURUR.
    with pytest.raises(pwb.PortfolioConfigSchemaError):
        pwb._validate_sla({"weekly_sync_max_days": 0, "monthly_roundup_target_dom": 1})


# ---------------------------------------------------------------------------
# Test 3 — Freshness flag stale/fresh sentinel (CRITICAL)
# ---------------------------------------------------------------------------

def test_freshness_flag_stale_fresh_sentinel(fixed_now: datetime) -> None:
    """Worker brief acceptance gate — additional skill-specific gate:
    last_sync_at = (now - 8 days), sla = 7 → flag MUST = "stale".
    last_sync_at = (now - 1 day),  sla = 7 → flag MUST = "fresh".
    last_sync_at = None,            sla = 7 → flag MUST = "stale".
    """
    eight_days_ago = (fixed_now - timedelta(days=8)).isoformat().replace("+00:00", "Z")
    one_day_ago = (fixed_now - timedelta(days=1)).isoformat().replace("+00:00", "Z")

    # 8-day-old + 7-day SLA → stale (the load-bearing assertion).
    flag = pwb.compute_freshness_flag(
        last_sync_at=eight_days_ago, sla_days=7, now=fixed_now,
    )
    assert flag == pwb.FRESHNESS_STALE == "stale", (
        f"8-day-old vs 7-day SLA must be 'stale', got {flag!r}"
    )

    # 1-day-old + 7-day SLA → fresh.
    flag = pwb.compute_freshness_flag(
        last_sync_at=one_day_ago, sla_days=7, now=fixed_now,
    )
    assert flag == pwb.FRESHNESS_FRESH == "fresh", (
        f"1-day-old vs 7-day SLA must be 'fresh', got {flag!r}"
    )

    # None → stale (never synced).
    assert pwb.compute_freshness_flag(
        last_sync_at=None, sla_days=7, now=fixed_now,
    ) == "stale"

    # "" → stale (empty string treated as never synced).
    assert pwb.compute_freshness_flag(
        last_sync_at="", sla_days=7, now=fixed_now,
    ) == "stale"

    # Boundary: exactly 7 days → fresh (NOT > 7d).
    flag = pwb.compute_freshness_flag(
        last_sync_at=(fixed_now - timedelta(days=7)).isoformat().replace("+00:00", "Z"),
        sla_days=7, now=fixed_now,
    )
    assert flag == "fresh"

    # Negative: bad sla_days → DURUR.
    with pytest.raises(pwb.FreshnessFlagInputError):
        pwb.compute_freshness_flag(last_sync_at=one_day_ago, sla_days=0, now=fixed_now)
    with pytest.raises(pwb.FreshnessFlagInputError):
        pwb.compute_freshness_flag(last_sync_at=one_day_ago, sla_days=31, now=fixed_now)

    # Negative: naive `now` → DURUR.
    naive_now = datetime(2026, 5, 1, 10, 0, 0)  # no tzinfo
    with pytest.raises(pwb.FreshnessFlagInputError):
        pwb.compute_freshness_flag(
            last_sync_at=one_day_ago, sla_days=7, now=naive_now,
        )

    # Negative: malformed last_sync_at → DURUR.
    with pytest.raises(pwb.FreshnessFlagInputError):
        pwb.compute_freshness_flag(
            last_sync_at="not-a-timestamp", sla_days=7, now=fixed_now,
        )


# ---------------------------------------------------------------------------
# Test 4 — Empty events.jsonl tolerance (project zero-deltas, not crash)
# ---------------------------------------------------------------------------

def test_empty_events_jsonl_tolerance(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """When per-project events.jsonl is missing OR empty OR contains no
    work events in the 7-day window, the project must surface as a
    zero-delta entry — NOT crash, NOT skip silently."""
    # Build a fake workspace_root with: alpha (missing events file),
    # beta (empty events file), gamma (events file with 0 work events
    # in window).
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / "projects" / slug / "_state").mkdir(parents=True)
    # alpha-test: NO events.jsonl file at all.
    # beta-test: empty events.jsonl.
    (ws / "projects" / "beta-test" / "_state" / "events.jsonl").write_text("", encoding="utf-8")
    # gamma-test: events.jsonl with one work event OUTSIDE the window.
    out_of_window = {
        "schema_version": "1.0",
        "event_kind": "work",
        "event_id": "work_T-9999_20250101T0000",
        "timestamp": "2025-01-01T00:00:00Z",
        "project_id": "gamma-test",
    }
    (ws / "projects" / "gamma-test" / "_state" / "events.jsonl").write_text(
        json.dumps(out_of_window) + "\n", encoding="utf-8",
    )

    brief = pwb.build_portfolio_brief(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        week_end="2026-05-01",
    )
    by_slug = {p.slug: p for p in brief.projects}
    assert set(by_slug.keys()) == {"alpha-test", "beta-test", "gamma-test"}
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        p = by_slug[slug]
        assert p.tasks_added == 0
        assert p.tasks_done == 0
        assert p.work_events == 0, (
            f"{slug} should have 0 in-window work events, got {p.work_events}"
        )

    # The brief still surfaces every project (no silent skip).
    assert len(brief.projects) == 3
    # Totals reflect the zero-delta tolerance.
    assert brief.totals_tasks_added == 0
    assert brief.totals_tasks_done == 0
    assert brief.totals_work_events == 0


# ---------------------------------------------------------------------------
# Test 5 — Cross-project delta merge (3 projects, mixed last_sync_at,
#          deterministic order, totals correct)
# ---------------------------------------------------------------------------

def test_cross_project_delta_merge_with_freshness_flags(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """3 projects with different last_sync_at — expected merged output:
       alpha-test  → fresh (1-day-old vs 7-day SLA)
       beta-test   → stale (8-day-old vs 7-day SLA)  *** KEY sentinel ***
       gamma-test  → stale (last_sync_at=None)
    Deterministic project ordering by slug.
    """
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / "projects" / slug / "_state").mkdir(parents=True)
        (ws / "projects" / slug / "_state" / "events.jsonl").write_text("", encoding="utf-8")

    brief = pwb.build_portfolio_brief(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        week_end="2026-05-01",
    )

    # Deterministic order — by slug alphabetic.
    slugs_in_order = [p.slug for p in brief.projects]
    assert slugs_in_order == sorted(slugs_in_order), (
        f"projects must be sorted by slug for byte-stable output, "
        f"got {slugs_in_order}"
    )
    assert slugs_in_order == ["alpha-test", "beta-test", "gamma-test"]

    by_slug = {p.slug: p for p in brief.projects}
    # Freshness flag merge — the key cross-project assertion.
    assert by_slug["alpha-test"].freshness_flag == "fresh"
    assert by_slug["beta-test"].freshness_flag == "stale"
    assert by_slug["gamma-test"].freshness_flag == "stale"

    # Totals: 1 fresh, 2 stale.
    assert brief.totals_fresh_projects == 1
    assert brief.totals_stale_projects == 2
    assert brief.sla_weekly_sync_max_days == 7
    # Window = 7 days ending 2026-05-01.
    assert brief.week_end == "2026-05-01"
    assert brief.week_start == "2026-04-25"

    # Idempotency: re-run with identical inputs → byte-stable output.
    brief2 = pwb.build_portfolio_brief(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        week_end="2026-05-01",
    )
    snap1 = json.dumps(pwb.build_snapshot(brief), sort_keys=True)
    snap2 = json.dumps(pwb.build_snapshot(brief2), sort_keys=True)
    assert snap1 == snap2, "build_portfolio_brief must be idempotent"

    # Render Markdown smoke — template substitutes cleanly + renders the
    # multi-row delta table with the freshness column.
    rendered = pwb.render_brief_markdown(brief=brief, template_path=TEMPLATE_PATH)
    assert "alpha-test" in rendered
    assert "beta-test" in rendered
    assert "gamma-test" in rendered
    assert "freshness_flag" in rendered
    # Stale/fresh sentinels appear in the table column.
    assert "| stale |" in rendered
    assert "| fresh |" in rendered


# ---------------------------------------------------------------------------
# Test 6 — Forbidden tokens guard (4 tokens × multiple files, grep CLEAN)
#          + plugin-agnostik (no slug literal in transform/skill)
# ---------------------------------------------------------------------------

def test_no_forbidden_tokens_in_skill() -> None:
    """Per worker brief acceptance gate #6: transform + SKILL.md +
    template + test must contain ZERO occurrences of:
      1. estimated_credits_per_call (Phase 7 lesson)
      2. estimated_credits_per_url  (Phase 7 lesson)
      3. metric_name                (Phase 7 closeout Q-CO-01 lesson)
      4. hardcoded project slug     (OK in test fixtures, NOT elsewhere)
      5. TODO comment in code

    Slug tokens are obfuscated as base64-decoded strings so this test
    file itself doesn't trip the grep guard (mirrors W-D1 pattern)."""
    transform_src = TRANSFORM_PATH.read_text(encoding="utf-8")
    skill_src = SKILL_PATH.read_text(encoding="utf-8")
    template_src = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Tokens 1-3: literal grep CLEAN across transform / SKILL.md / template.
    forbidden_literal = (
        "estimated_credits_per_call",
        "estimated_credits_per_url",
        "metric_name",
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

    # Token 5: TODO comment in CODE (transform). Markdown skill prose
    # may use the word legitimately ("TODO/fallback YASAK" discipline
    # checklist), but the transform .py must be free of TODO comments.
    # Allow the literal string "TODO" only when it is part of a known
    # statusEnum value (e.g. "TODO" as a default seed) — the transform
    # currently has none, so a strict scan is fine.
    todo_in_transform = re.findall(r"#\s*TODO\b", transform_src)
    assert not todo_in_transform, (
        f"TODO comment(s) found in transform: {todo_in_transform}"
    )

    # Token 4: hardcoded project slug. The transform module should
    # have ZERO references to known real-client slugs. Slugs are
    # base64-encoded here so the grep doesn't trip on this test file
    # itself.
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
# Test 7 — READ-ONLY discipline (no transaction.* / events_writer.* import)
# ---------------------------------------------------------------------------

def test_read_only_discipline_no_writer_imports() -> None:
    """The transform must not import scripts.excel.transaction or
    scripts.state.events_writer — both are write-side modules. This is
    the worker brief acceptance gate #8 + REVIZE 3 enforcement."""
    src = TRANSFORM_PATH.read_text(encoding="utf-8")
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
# Test 8 — Smoke E2E: synthetic config → CLI-equivalent pipeline →
#          snapshot + report files appear and parse cleanly
# ---------------------------------------------------------------------------

def test_smoke_e2e_pipeline(
    tmp_path: Path,
    synthetic_portfolio_config: dict,
    fixed_now: datetime,
) -> None:
    """Smoke E2E mirroring the CLI flow: build a brief, render Markdown,
    write the snapshot JSON, re-load both, assert the contracts."""
    ws = tmp_path / "workspace"
    for slug in ("alpha-test", "beta-test", "gamma-test"):
        (ws / "projects" / slug / "_state").mkdir(parents=True)
        (ws / "projects" / slug / "_state" / "events.jsonl").write_text(
            "", encoding="utf-8",
        )

    brief = pwb.build_portfolio_brief(
        portfolio_config=synthetic_portfolio_config,
        workspace_root=ws,
        now=fixed_now,
        week_end="2026-05-01",
    )

    # Snapshot is JSON-serialisable + round-trips.
    snap = pwb.build_snapshot(brief)
    snap_text = json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True)
    snap_round = json.loads(snap_text)
    assert snap_round["writer"] == pwb.WRITER_NAME == "portfolio_weekly_brief"
    assert snap_round["week_end"] == "2026-05-01"
    assert snap_round["week_start"] == "2026-04-25"
    assert snap_round["sla_weekly_sync_max_days"] == 7
    assert snap_round["totals"]["fresh_projects"] == 1
    assert snap_round["totals"]["stale_projects"] == 2
    assert {p["slug"] for p in snap_round["projects"]} == {
        "alpha-test", "beta-test", "gamma-test",
    }
    # Snapshot project order matches PortfolioBrief.projects (sorted).
    assert [p["slug"] for p in snap_round["projects"]] == [
        "alpha-test", "beta-test", "gamma-test",
    ]

    # Markdown render — no missing template variables.
    rendered = pwb.render_brief_markdown(brief=brief, template_path=TEMPLATE_PATH)
    assert "Portföy Haftalık Brief" in rendered
    assert "2026-04-25 → 2026-05-01" in rendered
    # Frontmatter scope/week fields populated.
    assert "scope: portfolio" in rendered
    assert "week_end: 2026-05-01" in rendered
    assert "sla_weekly_sync_max_days: 7" in rendered
    # Multi-row delta table renders all 3 projects + freshness column.
    assert "| alpha-test |" in rendered
    assert "| beta-test |" in rendered
    assert "| gamma-test |" in rendered
    assert "freshness_flag" in rendered
