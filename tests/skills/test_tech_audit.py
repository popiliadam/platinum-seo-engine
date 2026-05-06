"""
tests/skills/test_tech_audit.py — tech-audit discovery skill tests.

Phase 7 Wave 1, DFS HEAVY (paid MCP). Budget pre-flight is exercised
via subprocess mock; Lighthouse + content_parsing payloads are
hand-built fixtures so no live API call is needed.

Test coverage (≥10 cases):
  1. Frontmatter parses + validates (schemas/skill-frontmatter.schema)
     — incl. budget.uses_paid_mcp = True, category = discovery.
  2. Empty input (0 URLs) → empty rows.
  3. Single URL with poor lighthouse (Performance=30, LCP=5.0) →
     Performance category HIGH severity.
  4. Single URL stellar lighthouse (Performance=95, LCP=1.5, CLS=0.05)
     → no Performance/Layout rows emitted.
  5. Multiple URLs aggregated into one row per issue_category.
  6. Title >60 chars → Meta Tags category, LOW severity.
  7. H1 missing (count=0) → Headings category, MEDIUM severity.
  8. Budget pre-flight: subprocess mock returns exit 1 → BudgetExceededError.
  9. Budget pre-flight: PASS path returns envelope with exit_code=0.
 10. DoS prevention: URL list > url_cap → URLCapExceededError.
 11. Lighthouse schema drift: missing performance + lcp + lighthouse
     blocks → LighthouseSchemaDriftError.
 12. severityEnum coverage: HIGH/MEDIUM/LOW emitted; transform never
     emits any other value for the impact column.
 13. _normalize_dfs_response shape adapter (REST envelope + flat
     wrapper + unrecognized).

Cross-module IMPORT-only discipline:
  - scripts.discovery.tech_audit_transform   (transform + budget +
                                              shape adapter + exceptions)

NOTE: scripts.excel.transaction is NOT imported — the transform module
never produces direct Excel writes (the SKILL orchestrator handles that
at step 8). Tests assert this by checking for the absence of
`from scripts.excel` imports in the transform module.

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_tech_audit.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import tech_audit_transform


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_MD = REPO_ROOT / "skills" / "discovery" / "tech-audit" / "SKILL.md"
TRANSFORM_PY = REPO_ROOT / "scripts" / "discovery" / "tech_audit_transform.py"


# ---------------------------------------------------------------------------
# Fixtures — schemas
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def master_excel_schema() -> dict:
    return json.loads((SCHEMAS / "master-excel.schema.json").read_text("utf-8"))


# ---------------------------------------------------------------------------
# Fixtures — Lighthouse payloads (mock; mirrors dataforseo-mcp-server flat
# wrapper shape)
# ---------------------------------------------------------------------------

def _lighthouse_item(
    url: str,
    *,
    perf: float | None = None,
    lcp_s: float | None = None,
    cls: float | None = None,
    fcp_s: float | None = None,
) -> dict:
    """Build a single DFS lighthouse item with optional canonical signals.

    Score is stored as 0-1 float upstream; we drop perf/100 here so the
    extractor's score normalisation is exercised.
    """
    audits: dict = {}
    if lcp_s is not None:
        audits["largest-contentful-paint"] = {"numericValue": lcp_s * 1000.0}
    if fcp_s is not None:
        audits["first-contentful-paint"] = {"numericValue": fcp_s * 1000.0}
    if cls is not None:
        audits["cumulative-layout-shift"] = {"numericValue": cls}

    categories: dict = {}
    if perf is not None:
        categories["performance"] = {"score": perf / 100.0}

    return {
        "url": url,
        "lighthouse": {
            "categories": categories,
            "audits": audits,
        },
    }


def _content_item(
    url: str,
    *,
    title: str = "Default page title",
    meta: str = "Default meta description with reasonable length to pass.",
    h1_count: int = 1,
    has_structured_data: bool = True,
    is_commercial: bool = False,
) -> dict:
    """Build a single DFS on_page_content_parsing item."""
    h1: list[str] = [f"Heading {i+1}" for i in range(h1_count)]
    item: dict = {
        "url": url,
        "meta": {"title": title, "description": meta},
        "page_content": {
            "h1": h1,
            "internal_links_count": 12,
            "images_count": 4,
            "images_without_alt": 0,
        },
    }
    if has_structured_data:
        item["schema"] = [{"@type": "WebPage"}]
    if is_commercial:
        item["page_intent"] = "commercial"
    return item


@pytest.fixture
def lh_payload_poor() -> dict:
    """One URL with Performance=30, LCP=5.2s — should fire HIGH + MEDIUM."""
    return {
        "items": [_lighthouse_item(
            "https://example.com/slow-page",
            perf=30, lcp_s=5.2, cls=0.05, fcp_s=2.1,
        )],
    }


@pytest.fixture
def lh_payload_stellar() -> dict:
    """One URL with Performance=95, LCP=1.5s, CLS=0.05 — clean."""
    return {
        "items": [_lighthouse_item(
            "https://example.com/fast-page",
            perf=95, lcp_s=1.5, cls=0.05, fcp_s=1.2,
        )],
    }


@pytest.fixture
def lh_payload_multi() -> dict:
    """Three URLs all with high LCP — aggregation test."""
    return {
        "items": [
            _lighthouse_item("https://example.com/a", perf=40, lcp_s=4.0, cls=0.05),
            _lighthouse_item("https://example.com/b", perf=45, lcp_s=4.5, cls=0.15),
            _lighthouse_item("https://example.com/c", perf=35, lcp_s=5.5, cls=0.20),
        ],
    }


@pytest.fixture
def cp_payload_clean() -> dict:
    """One URL with all on-page signals clean."""
    return {
        "items": [_content_item("https://example.com/clean")],
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + schema validates
# ---------------------------------------------------------------------------

def test_frontmatter_validates_against_schema(
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must validate against
    schemas/skill-frontmatter.schema.json (Draft 7), and must declare
    discovery category + paid-MCP budget.
    """
    text = SKILL_MD.read_text("utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "SKILL.md must open with --- frontmatter ---"
    fm = yaml.safe_load(parts[1])

    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(
        validator.iter_errors(fm),
        key=lambda e: list(e.absolute_path),
    )
    assert not errs, (
        "frontmatter invalid: "
        f"{[('/'.join(str(p) for p in e.absolute_path) or '<root>', e.message) for e in errs]}"
    )

    # Brief-mandated values.
    assert fm["category"] == "discovery"
    assert fm["status"] == "wip"
    assert fm["budget"]["uses_paid_mcp"] is True
    assert fm["budget"]["estimated_credits"] > 0

    req = fm["mcp_tools"]["required"]
    assert "mcp__dataforseo__on_page_lighthouse" in req
    assert "mcp__dataforseo__on_page_content_parsing" in req


def test_skill_md_documents_awaiting_approval_path() -> None:
    """SKILL.md must explicitly document the awaiting_approval state path
    that fires when budget pre-flight FAILs (DURUR #1)."""
    text = SKILL_MD.read_text("utf-8")
    assert "awaiting_approval" in text, (
        "SKILL.md must document the awaiting_approval state path for "
        "BudgetExceededError per ADR-016"
    )
    # And Step 1 must be the budget pre-flight (not a later step).
    assert re.search(
        r"###\s+Step\s+1\s+[-—]\s+`?preflight_budget", text,
    ), "Step 1 must be the budget pre-flight per spec §16.8"


# ---------------------------------------------------------------------------
# Test 2 — Empty input → empty rows
# ---------------------------------------------------------------------------

def test_empty_input_emits_empty_rows() -> None:
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=None,
    )
    assert out["tech_seo"] == []
    assert out["meta"]["row_count"] == 0
    assert out["meta"]["finding_count"] == 0


def test_empty_items_arrays_emit_no_rows() -> None:
    """Both payloads carry zero items → still empty output (no drift)."""
    out = tech_audit_transform.transform(
        lighthouse_raw={"items": []},
        content_parsing_raw={"items": []},
    )
    assert out["tech_seo"] == []


# ---------------------------------------------------------------------------
# Test 3 — Poor lighthouse → HIGH severity row
# ---------------------------------------------------------------------------

def test_poor_lighthouse_emits_high_severity(lh_payload_poor: dict) -> None:
    out = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor,
        content_parsing_raw=None,
    )
    rows = out["tech_seo"]
    perf_rows = [r for r in rows if r["issue_category"] == "Performance"]
    assert perf_rows, "Performance category must fire for score < 50"
    perf = perf_rows[0]
    # HIGH wins when score < 50 AND LCP > 2.5 (LCP is MEDIUM).
    assert perf["impact"] == tech_audit_transform.SEVERITY_HIGH
    assert perf["priority"] == "P0"
    # affected_urls populated with the single URL.
    assert "https://example.com/slow-page" in perf["affected_urls"]
    # Row column lock.
    assert set(perf.keys()) == set(tech_audit_transform.TECH_SEO_COLUMNS)


# ---------------------------------------------------------------------------
# Test 4 — Stellar lighthouse → no Performance/Layout rows
# ---------------------------------------------------------------------------

def test_stellar_lighthouse_emits_no_rows(lh_payload_stellar: dict) -> None:
    out = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_stellar,
        content_parsing_raw=None,
    )
    rows = out["tech_seo"]
    perf_rows = [r for r in rows if r["issue_category"] == "Performance"]
    layout_rows = [r for r in rows if r["issue_category"] == "Layout Stability"]
    assert perf_rows == [], "score=95 + LCP=1.5 + FCP=1.2 should be clean"
    assert layout_rows == [], "CLS=0.05 should not fire layout rule"


# ---------------------------------------------------------------------------
# Test 5 — Multi-URL aggregation
# ---------------------------------------------------------------------------

def test_multi_url_aggregation_by_category(lh_payload_multi: dict) -> None:
    out = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_multi,
        content_parsing_raw=None,
    )
    rows = out["tech_seo"]
    cat_set = {r["issue_category"] for r in rows}
    assert "Performance" in cat_set
    assert "Layout Stability" in cat_set
    perf = next(r for r in rows if r["issue_category"] == "Performance")
    # All three URLs landed in affected_urls (poor scores 40/45/35).
    for slug in ("/a", "/b", "/c"):
        assert slug in perf["affected_urls"]
    # Highest severity wins (HIGH from score<50).
    assert perf["impact"] == tech_audit_transform.SEVERITY_HIGH


# ---------------------------------------------------------------------------
# Test 6 — Title too long → Meta Tags LOW
# ---------------------------------------------------------------------------

def test_title_too_long_emits_meta_low() -> None:
    long_title = "x" * 65   # 65 > 60
    cp = {"items": [_content_item(
        "https://example.com/long-title", title=long_title,
    )]}
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=cp,
    )
    meta_rows = [r for r in out["tech_seo"] if r["issue_category"] == "Meta Tags"]
    assert meta_rows
    # Row's impact is LOW (title-too-long is the only finding).
    assert meta_rows[0]["impact"] == tech_audit_transform.SEVERITY_LOW
    assert meta_rows[0]["priority"] == "P2"
    assert "Title too long" in meta_rows[0]["detail"]


# ---------------------------------------------------------------------------
# Test 7 — H1 anomaly → Headings MEDIUM
# ---------------------------------------------------------------------------

def test_missing_h1_emits_headings_medium() -> None:
    cp = {"items": [_content_item(
        "https://example.com/no-h1", h1_count=0,
    )]}
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=cp,
    )
    head_rows = [r for r in out["tech_seo"] if r["issue_category"] == "Headings"]
    assert head_rows, "H1 count=0 must fire Headings rule"
    assert head_rows[0]["impact"] == tech_audit_transform.SEVERITY_MEDIUM
    assert head_rows[0]["priority"] == "P1"
    assert "H1 missing" in head_rows[0]["detail"]


def test_multiple_h1_emits_headings_medium() -> None:
    cp = {"items": [_content_item(
        "https://example.com/two-h1", h1_count=2,
    )]}
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=cp,
    )
    head_rows = [r for r in out["tech_seo"] if r["issue_category"] == "Headings"]
    assert head_rows
    assert head_rows[0]["impact"] == tech_audit_transform.SEVERITY_MEDIUM


# ---------------------------------------------------------------------------
# Test 8 — Budget pre-flight FAIL (subprocess mock exit 1)
# ---------------------------------------------------------------------------

def test_preflight_budget_exit_1_raises(tmp_path: Path) -> None:
    """When check_budget.py exits 1 (or projected_used > budget), the
    pre-flight raises BudgetExceededError. The skill is then expected to
    route the workflow to awaiting_approval per ADR-016."""

    cfg_path = tmp_path / "project.config.json"
    cfg_path.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 10},
    }))
    events_path = tmp_path / "events.jsonl"

    # 50 URLs × 13 credits = 650 credits >> budget 10.
    estimate = tech_audit_transform.estimate_credits(50)
    assert estimate == 650

    with pytest.raises(tech_audit_transform.BudgetExceededError) as ei:
        tech_audit_transform.preflight_budget(
            estimated_credits=estimate,
            project_config_path=cfg_path,
            events_path=events_path,
        )
    assert "budget pre-flight FAIL" in str(ei.value)
    # awaiting_approval routing hint surfaced in the exception message.
    assert "awaiting_approval" in str(ei.value)


def test_preflight_budget_pass_returns_envelope(tmp_path: Path) -> None:
    """Happy path: 1 URL × 13 credits, budget 500 → envelope, no raise."""
    cfg_path = tmp_path / "project.config.json"
    cfg_path.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 500},
    }))
    events_path = tmp_path / "events.jsonl"

    estimate = tech_audit_transform.estimate_credits(1)
    assert estimate == 13

    envelope = tech_audit_transform.preflight_budget(
        estimated_credits=estimate,
        project_config_path=cfg_path,
        events_path=events_path,
    )
    assert envelope["exceeded"] is False
    assert envelope["budget_per_day"] == 500.0
    assert envelope["estimated_credits"] == 13
    assert envelope["projected_used"] == 13.0
    assert envelope["exit_code"] == 0


def test_preflight_budget_subprocess_mocked_exit_1(tmp_path: Path) -> None:
    """Direct subprocess mock — guarantees DURUR #1 fires when the script
    returns exit code 1 with `exceeded=true` envelope (the canonical
    over-budget shape)."""
    cfg_path = tmp_path / "project.config.json"
    cfg_path.write_text("{}")  # content irrelevant — mock intercepts
    events_path = tmp_path / "events.jsonl"

    class _Proc:
        returncode = 1
        stdout = '{"budget_per_day":500,"used_24h":499,"remaining":1,"exceeded":true}\n'
        stderr = ""

    with patch.object(
        tech_audit_transform.subprocess, "run", return_value=_Proc(),
    ):
        with pytest.raises(tech_audit_transform.BudgetExceededError):
            tech_audit_transform.preflight_budget(
                estimated_credits=10,
                project_config_path=cfg_path,
                events_path=events_path,
            )


# ---------------------------------------------------------------------------
# Test 9 — DoS prevention: URL list > url_cap → URLCapExceededError
# ---------------------------------------------------------------------------

def test_url_cap_exceeded_raises() -> None:
    items = [
        _lighthouse_item(f"https://example.com/p{i}", perf=80, lcp_s=2.0)
        for i in range(60)
    ]
    payload = {"items": items}
    with pytest.raises(tech_audit_transform.URLCapExceededError) as ei:
        tech_audit_transform.transform(
            lighthouse_raw=payload,
            content_parsing_raw=None,
            url_cap=50,
        )
    assert "exceeds cap" in str(ei.value)
    # Subclass invariant.
    assert isinstance(ei.value, tech_audit_transform.TechAuditError)


# ---------------------------------------------------------------------------
# Test 10 — Lighthouse schema drift → LighthouseSchemaDriftError
# ---------------------------------------------------------------------------

def test_lighthouse_schema_drift_raises() -> None:
    """Item carries no performance score / lcp / lighthouse block →
    schema renamed upstream → DURUR #4."""
    drifted = {"items": [{
        "url": "https://example.com/x",
        # No 'lighthouse', no 'performance_score', no 'lcp' — drift.
        "score": 50,
    }]}
    with pytest.raises(tech_audit_transform.LighthouseSchemaDriftError):
        tech_audit_transform.transform(
            lighthouse_raw=drifted,
            content_parsing_raw=None,
        )


def test_lighthouse_missing_url_raises() -> None:
    drifted = {"items": [{
        "lighthouse": {"categories": {"performance": {"score": 0.8}}},
    }]}
    with pytest.raises(tech_audit_transform.LighthouseSchemaDriftError):
        tech_audit_transform.transform(
            lighthouse_raw=drifted,
            content_parsing_raw=None,
        )


def test_content_parsing_schema_drift_raises() -> None:
    drifted = {"items": [{
        "url": "https://example.com/x",
        # Missing meta + page_content + title — drift.
        "foo": "bar",
    }]}
    with pytest.raises(tech_audit_transform.ContentParsingSchemaDriftError):
        tech_audit_transform.transform(
            lighthouse_raw=None,
            content_parsing_raw=drifted,
        )


# ---------------------------------------------------------------------------
# Test 11 — severityEnum coverage (HIGH/MEDIUM/LOW emitted)
# ---------------------------------------------------------------------------

def test_severity_enum_coverage(
    lh_payload_poor: dict,
) -> None:
    """Combined payload exercises HIGH (perf<50), MEDIUM (LCP>2.5 AND
    H1 anomaly), and LOW (title>60) severities — all of severityEnum's
    active emission tiers."""
    cp = {"items": [_content_item(
        "https://example.com/slow-page",
        title="x" * 70,             # LOW
        h1_count=0,                 # MEDIUM (Headings)
    )]}
    out = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor,
        content_parsing_raw=cp,
    )
    impacts = {r["impact"] for r in out["tech_seo"]}
    assert tech_audit_transform.SEVERITY_HIGH in impacts
    assert tech_audit_transform.SEVERITY_MEDIUM in impacts
    assert tech_audit_transform.SEVERITY_LOW in impacts
    # Strict severityEnum: no row carries a non-enum value.
    for r in out["tech_seo"]:
        assert r["impact"] in tech_audit_transform.SEVERITY_ENUM


def test_rows_match_master_schema_columns(master_excel_schema: dict) -> None:
    """Every emitted row carries exactly the 6 columns named in
    schemas/master-excel.schema.json's tech_seo sheet definition."""
    schema_cols = tuple(
        c["name"]
        for c in master_excel_schema["sheets"]["tech_seo"]["required_columns"]
    )
    assert tech_audit_transform.TECH_SEO_COLUMNS == schema_cols, (
        f"Column drift: module={tech_audit_transform.TECH_SEO_COLUMNS}, "
        f"schema={schema_cols}"
    )
    # Build a multi-finding payload and verify every row's keys.
    cp = {"items": [_content_item(
        "https://example.com/x", title="x" * 70, h1_count=0,
    )]}
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=cp,
    )
    for r in out["tech_seo"]:
        assert set(r.keys()) == set(schema_cols)


# ---------------------------------------------------------------------------
# Test 12 — _normalize_dfs_response shape adapter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "case,raw,expected_count",
    [
        (
            "rest_envelope",
            {"tasks": [{"result": [{"items": [{"url": "u1"}]}]}]},
            1,
        ),
        (
            "flat_wrapper",
            {"items": [{"url": "u1"}, {"url": "u2"}]},
            2,
        ),
    ],
)
def test_normalize_dfs_response_known_shapes(
    case: str, raw: dict, expected_count: int,
) -> None:
    items = tech_audit_transform._normalize_dfs_response(raw)
    assert len(items) == expected_count, f"case={case!r}"


def test_normalize_dfs_response_unrecognized_raises() -> None:
    with pytest.raises(ValueError) as ei:
        tech_audit_transform._normalize_dfs_response({"foo": "bar"})
    assert "Unrecognized DFS response shape" in str(ei.value)


# ---------------------------------------------------------------------------
# Test 13 — Plugin agnostik + transform discipline
# ---------------------------------------------------------------------------

def test_no_hardcoded_slug_in_transform() -> None:
    """0-tolerance plugin agnostik — no project slug literals anywhere."""
    text = TRANSFORM_PY.read_text("utf-8")
    forbidden = re.compile(
        r"\b(demo-dental|demo-furniture|demo-hvac|demo-petcare|demo-shop|demo-tires|"
        r"demo-construction|demo-agency)\b",
        re.IGNORECASE,
    )
    assert not forbidden.search(text), (
        "tech_audit_transform.py must not carry slug literals "
        "(plugin-agnostik 0-tolerance)"
    )


def test_no_hardcoded_slug_in_skill_md() -> None:
    text = SKILL_MD.read_text("utf-8")
    forbidden = re.compile(
        r"\b(demo-dental|demo-furniture|demo-hvac|demo-petcare|demo-shop|demo-tires|"
        r"demo-construction|demo-agency)\b",
        re.IGNORECASE,
    )
    assert not forbidden.search(text)


def test_transform_does_not_import_excel_transaction() -> None:
    """transform module must NOT import scripts.excel.transaction —
    Excel writes belong to the SKILL orchestrator (step 8), not the
    transform. Mirrors dfs_pull staging-only discipline."""
    text = TRANSFORM_PY.read_text("utf-8")
    assert "scripts.excel.transaction" not in text
    assert "from scripts.excel" not in text
    # And no direct transaction.append calls in the transform.
    assert "transaction.append" not in text
