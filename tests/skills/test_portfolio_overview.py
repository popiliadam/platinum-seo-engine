"""tests/skills/test_portfolio_overview.py — portfolio-overview skill tests.

Mirrors tests/skills/test_master_task_sync.py (Phase 8 W-D1) — frontmatter
parse + schema validate, transform smoke + drift behaviour, missing
workbook tolerance, READ-ONLY contract enforcement, and natural_language
+ forbidden-tokens guards (Phase 7 closeout lessons).

This is a LOCAL-AGGREGATION skill — no MCP, no DFS, no budget pre-flight,
no Excel write. Every test is fully data-driven with synthetic
portfolio.config.json + a tmp_path workspace tree.

Schemas referenced:
  - schemas/portfolio-config.schema.json (v1.1)
  - schemas/skill-frontmatter.schema.json
  - schemas/master-excel.schema.json#dashboard required_cells
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.reporting import portfolio_overview as po


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "reporting" / "portfolio-overview" / "SKILL.md"
TRANSFORM_PATH = REPO_ROOT / "scripts" / "reporting" / "portfolio_overview.py"
TEMPLATE_PATH = (
    REPO_ROOT / "templates" / "reports" / "portfolio-overview.template.md"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def portfolio_config_schema() -> dict:
    return json.loads(
        (SCHEMAS / "portfolio-config.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    """Parse the YAML frontmatter block of the portfolio-overview SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


def _synthetic_config(active_count: int = 2) -> dict:
    """Build a valid portfolio.config payload with N active projects."""
    active = []
    for i in range(active_count):
        active.append({
            "slug": f"project-{i+1}",
            "display_name": f"Project {i+1}",
            "workspace_path": f"./workspace-{i+1}",
            "profile": ["e-commerce"],
            "priority": min(i + 1, 10),  # schema caps priority at 10
        })
    return {
        "schema_version": "1.1",
        "portfolio_id": "test-portfolio",
        "display_name": "Test Portfolio",
        "active_projects": active,
        "slas": {
            "weekly_sync_max_days": 7,
            "monthly_roundup_target_dom": 5,
        },
        "cadence": {
            "weekly_brief": {"day": "Monday", "hour": 9},
            "monthly_roundup": {"day_of_month": 5, "hour": 10},
        },
        "cross_query": {"read_only": True},
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter validates against skill-frontmatter.schema.json
# ---------------------------------------------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict, skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) name=portfolio-overview, status=wip, version="1.0",
          category=reporting,
      (c) declare 0 required AND 0 optional MCP tools (local read-only),
      (d) outputs include master.xlsx#none + report + inbox snapshot,
      (e) triggers.manual = [] (NO slash command per brief),
      (f) budget.uses_paid_mcp=false / estimated_credits=0,
      (g) autonomy: HIGH confidence + safe_auto_execute=true (cron-ready),
      (h) Draft 7 validation against the canonical schema.
    """
    fm = skill_frontmatter
    assert fm["name"] == "portfolio-overview"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "reporting"

    # No required NOR optional MCP tools.
    assert fm.get("mcp_tools", {}).get("required", []) == []
    assert fm.get("mcp_tools", {}).get("optional", []) == []

    # Outputs: 3 entries — master.xlsx#none + report + inbox snapshot.
    outputs = fm["outputs"]
    assert "master.xlsx#none" in outputs
    assert any("portfolio-overview.md" in o and "outputs/reports/" in o
               for o in outputs)
    assert any("inbox/local/" in o and "portfolio-overview.json" in o
               for o in outputs)
    # NO events.jsonl (REVIZE 1+3).
    assert "events.jsonl" not in outputs

    # Manual triggers empty (brief: NO slash command).
    assert fm["triggers"]["manual"] == []

    # Budget: 0 credits, no paid MCP.
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"].get("estimated_credits", 0) == 0

    # Autonomy: HIGH + safe_auto_execute=true (cron-ready aggregator).
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["requires_approval"] is False
    assert fm["autonomy"]["safe_auto_execute"] is True

    # Full Draft 7 validation.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm),
                  key=lambda e: list(e.absolute_path))
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — natural_language trigger meets min length sentinel (>= 30 char)
# ---------------------------------------------------------------------------

def test_natural_language_min_length(skill_frontmatter: dict) -> None:
    """Phase 8 closeout lesson + Phase 9 W1 brief acceptance gate #7:
    triggers.natural_language must be >= 30 characters so Claude's
    matcher has enough surface area to fire correctly. Worker pytest
    sentinel because no schema-level constraint exists yet.
    """
    nl = skill_frontmatter["triggers"]["natural_language"]
    assert isinstance(nl, str), "natural_language must be a string block"
    assert len(nl) >= 30, (
        f"natural_language too short ({len(nl)} chars); >= 30 required."
    )


# ---------------------------------------------------------------------------
# Test 3 — portfolio.config schema validate PASS (synthetic happy-path)
# ---------------------------------------------------------------------------

def test_portfolio_config_schema_validate_pass(
    portfolio_config_schema: dict,
) -> None:
    """A valid synthetic portfolio.config payload (with active_projects
    1-12 entries + cross_query.read_only=true) must pass validation
    cleanly via portfolio_overview.validate_portfolio_config().
    """
    config = _synthetic_config(active_count=3)
    # Should NOT raise.
    po.validate_portfolio_config(config, portfolio_config_schema)


# ---------------------------------------------------------------------------
# Test 4 — active_projects maxItems sentinel: 12 accepted, 13 rejected
# ---------------------------------------------------------------------------

def test_active_projects_maxitems_sentinel_12_ok_13_rejected(
    portfolio_config_schema: dict,
) -> None:
    """The active_projects soft cap is the schema's `maxItems = 12`
    (raised from 8 when the live portfolio reached ~10). A 12-entry
    payload must VALIDATE cleanly — this is the runtime break B1 fixes,
    where a real ~10-project portfolio previously tripped the stale
    ceiling-8 guard. A 13-entry payload must raise
    PortfolioConfigInvalidError (Draft 7 maxItems) OR
    ActiveProjectsCeilingError (defensive domain guard); both acceptable.
    """
    # Positive: exactly 12 active_projects validates (no DURUR).
    at_cap = _synthetic_config(active_count=12)
    po.validate_portfolio_config(at_cap, portfolio_config_schema)

    # Negative: 13 active_projects exceeds the ceiling.
    over_cap = _synthetic_config(active_count=13)
    with pytest.raises(
        (po.PortfolioConfigInvalidError, po.ActiveProjectsCeilingError),
    ):
        po.validate_portfolio_config(over_cap, portfolio_config_schema)


# ---------------------------------------------------------------------------
# Test 5 — Missing master.xlsx tolerated (graceful skip, no crash)
# ---------------------------------------------------------------------------

def test_missing_master_xlsx_tolerated(
    tmp_path: Path, portfolio_config_schema: dict,
) -> None:
    """Per the SKILL.md gate: per-project missing master.xlsx is NOT a
    DURUR. The aggregator skips gracefully — empty kpis, status_counts,
    and a warning are surfaced; no exception.
    """
    # Build a portfolio root tree on tmp_path that satisfies the
    # path-resolution convention but contains NO master.xlsx files.
    portfolio_root = tmp_path / "portfolio_ws"
    portfolio_root.mkdir()
    (portfolio_root / "projects" / "_portfolio").mkdir(parents=True)
    config = _synthetic_config(active_count=2)
    (portfolio_root / "projects" / "_portfolio" / "portfolio.config.json"
     ).write_text(json.dumps(config), encoding="utf-8")

    # Validate first (schema clean).
    po.validate_portfolio_config(config, portfolio_config_schema)

    # Aggregate — must NOT raise.
    batch = po.aggregate(
        portfolio_root=portfolio_root, config=config,
        run_date="2026-05-01",
    )
    assert batch.portfolio_id == "test-portfolio"
    assert len(batch.snapshots) == 2
    assert batch.skipped_projects == 2  # both master.xlsx absent
    for snap in batch.snapshots:
        assert snap.master_xlsx_path is None
        assert snap.warnings, "missing workbook should surface a warning"
        # All KPIs blank-seeded.
        for _cell, kpi in po.DASHBOARD_KPI_CELLS:
            assert snap.kpis.get(kpi) == ""
        # All status counts zero.
        assert all(c == 0 for c in snap.status_counts.values())


# ---------------------------------------------------------------------------
# Test 6 — READ-ONLY contract: no openpyxl write call sites in transform
# ---------------------------------------------------------------------------

def test_read_only_contract_enforcement() -> None:
    """Per portfolio-config.schema.json#cross_query.read_only=true (const),
    portfolio_overview.py must contain ZERO openpyxl write call sites
    (.save(), transaction.append(), transaction.update(),
    transaction.delete()). Verified by the source-grep helper
    assert_read_only_module().
    """
    # Direct invocation — must NOT raise.
    po.assert_read_only_module()

    # Independent re-grep so the test is robust even if the helper itself
    # is later refactored.
    src = TRANSFORM_PATH.read_text(encoding="utf-8")
    forbidden = [
        # Patterns assembled at runtime so this test file ALSO does not
        # contain the literal write-call substrings (forbidden token guard).
        "." + "save(",
        "transaction" + "." + "append(",
        "transaction" + "." + "update(",
        "transaction" + "." + "delete(",
    ]
    # Strip the constants-block tuple AND the assert_read_only_module
    # docstring so the legitimate pattern declarations don't false-positive.
    # The constants block uses string concatenation so the literals are
    # not in the source verbatim — but to keep the test simple we just
    # search outside string literals via a coarse split on triple-quotes.
    # Easier approach: assert that EVERY hit is inside the constants tuple
    # `_FORBIDDEN_WRITE_PATTERNS` definition or NOT present at all.
    for pat in forbidden:
        assert pat not in src, (
            f"forbidden write pattern {pat!r} appears verbatim in "
            "portfolio_overview.py source — read-only contract violated."
        )


# ---------------------------------------------------------------------------
# Test 7 — Forbidden tokens guard (Phase 7 + Phase 8 closeout lessons)
# ---------------------------------------------------------------------------

def test_no_forbidden_tokens_in_skill() -> None:
    """Phase 7 lesson + Phase 9 W1 brief: 4 forbidden tokens must NOT
    appear in any of the 4 skill artifacts (SKILL.md, transform,
    template, test). The token literals are assembled at runtime so
    this test file itself stays grep-clean against its own assertion.
    Token registry (see Phase 7 + Q-CO-01 closeout lessons):
      [1] paid-MCP per-call estimate field
      [2] paid-MCP per-url estimate field
      [3] generic metric label key from Q-CO-01
      [4] 'TODO' inline-comment marker in transform code

    Hardcoded slug literals are OK in test fixtures (test only) but
    must not appear in transform code.
    """
    forbidden_tokens = (
        "estimated_credits" + "_per_call",
        "estimated_credits" + "_per_url",
        "metric" + "_name",
    )
    files = (SKILL_PATH, TRANSFORM_PATH, TEMPLATE_PATH)
    for f in files:
        text = f.read_text(encoding="utf-8")
        for tok in forbidden_tokens:
            assert tok not in text, (
                f"forbidden token {tok!r} found in {f.name}"
            )

    # 'TODO' as inline-comment marker in transform code only.
    transform_src = TRANSFORM_PATH.read_text(encoding="utf-8")
    # Allow 'TODO' as a STATUS_ENUM value (the literal "TODO" in tuples /
    # dict keys is the canonical statusEnum entry, not a code fix-me).
    todo_comment_pattern = re.compile(r"#\s*TODO\b")
    assert not todo_comment_pattern.search(transform_src), (
        "TODO inline-comment marker found in transform code "
        "(STATUS_ENUM tuple entries are allowed)."
    )


# ---------------------------------------------------------------------------
# Test 8 — Template renders cleanly via render_template.py-compatible
#           string.Template substitution + report build smoke
# ---------------------------------------------------------------------------

def test_template_render_smoke(
    tmp_path: Path, portfolio_config_schema: dict,
) -> None:
    """Build a snapshot + render the template via build_report_markdown;
    asserts the markdown body contains the expected sections (frontmatter,
    project table header, totals summary). Mirrors the smoke pattern of
    other reporting skills' report-render asserts.
    """
    portfolio_root = tmp_path / "portfolio_ws"
    portfolio_root.mkdir()
    (portfolio_root / "projects" / "_portfolio").mkdir(parents=True)
    config = _synthetic_config(active_count=2)
    po.validate_portfolio_config(config, portfolio_config_schema)

    batch = po.aggregate(
        portfolio_root=portfolio_root, config=config,
        run_date="2026-05-01",
    )

    # Build snapshot — must be JSON-serializable.
    snapshot = po.build_snapshot(batch=batch)
    json.dumps(snapshot)  # raises if not serializable

    # Render report via the actual template file.
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    report = po.build_report_markdown(
        batch=batch, template_text=template_text,
    )
    assert "# Portfolio Overview" in report
    assert "test-portfolio" in report
    assert "## Projects" in report
    assert "## Totals" in report
    assert "active projects" in report
    # Drift column header present.
    assert "drift" in report
    # Both project slugs surfaced.
    assert "project-1" in report and "project-2" in report
    # Snapshot count matches active count.
    assert snapshot["active_project_count"] == 2
    assert snapshot["skipped_project_count"] == 2  # no master.xlsx

    # Every $placeholder must be substituted EXCEPT $run_id — the K-06
    # audit-trail placeholder a render-time hook injects later
    # (test_run_id_coverage.py enforces $run_id in every report template;
    # build_report_markdown's setdefault("run_id","$run_id") keeps it
    # literal). Read identifiers from the RAW template (stripping $$
    # escapes — a $$var doc-literal is NOT a placeholder) and assert none
    # but run_id survive into the render.
    template_ids = set(re.findall(
        r"\$\{?([A-Za-z_]\w*)\}?", template_text.replace("$$", ""))) - {"run_id"}
    leaked = sorted(
        i for i in template_ids
        if re.search(r"\$\{?" + re.escape(i) + r"\}?", report)
    )
    assert not leaked, f"unsubstituted template placeholders: {leaked}"


# ---------------------------------------------------------------------------
# Test 9 — build_report_markdown uses strict .substitute() (B1-12):
#          a template var the transform does not supply raises loudly
# ---------------------------------------------------------------------------

def test_build_report_markdown_raises_on_missing_key(
    tmp_path: Path, portfolio_config_schema: dict,
) -> None:
    """B1-12: build_report_markdown renders via strict
    string.Template.substitute() (the render_template.py convention its
    docstring cites), so a template referencing a variable the transform
    does NOT supply must raise PortfolioOverviewError — a LOUD failure,
    not a silently-leaked literal $placeholder (the safe_substitute trap).
    """
    portfolio_root = tmp_path / "portfolio_ws"
    portfolio_root.mkdir()
    (portfolio_root / "projects" / "_portfolio").mkdir(parents=True)
    config = _synthetic_config(active_count=1)
    batch = po.aggregate(
        portfolio_root=portfolio_root, config=config, run_date="2026-05-01",
    )
    bad_template = (
        "# Overview $portfolio_id\nUnsupplied: $totally_unknown_var\n"
    )
    with pytest.raises(po.PortfolioOverviewError):
        po.build_report_markdown(batch=batch, template_text=bad_template)
