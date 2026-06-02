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
    assert fm["status"] in {"active", "deprecated", "wip"}
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
    head_rows = [r for r in out["tech_seo"] if r["issue_category"] == "Meta Tags"]
    assert head_rows, "H1 count=0 must fire heading rule under Meta Tags"
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
    head_rows = [r for r in out["tech_seo"] if r["issue_category"] == "Meta Tags"]
    assert head_rows
    assert head_rows[0]["impact"] == tech_audit_transform.SEVERITY_MEDIUM


# ---------------------------------------------------------------------------
# Test 7b — heading findings carry the schema-locked "Meta Tags" enum value
# (DFS-path sibling of AC-10 Task D). "Headings" is NOT in the
# tech_seo.issue_category enum {Performance, Layout Stability, Meta Tags,
# Structured Data, Accessibility}; emitting it would raise RowSchemaError on
# transaction.append/replace. H1/H2 issues live under "Meta Tags" in both the
# human-curated master.xlsx AND scripts/util/sf_issue_taxonomy.py routing.
# ---------------------------------------------------------------------------

def test_missing_h1_routes_to_meta_tags_enum() -> None:
    """A DFS content item with a missing H1 (the aluminumstation case —
    20 pages H1-less) must produce a tech_seo row whose issue_category is
    the schema-locked 'Meta Tags', never the out-of-enum 'Headings'."""
    cp = {"items": [_content_item(
        "https://example.com/no-h1", h1_count=0,
    )]}
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=cp,
    )
    # The heading finding's row carries the H1-missing detail.
    heading_rows = [
        r for r in out["tech_seo"] if "H1 missing" in r["detail"]
    ]
    assert heading_rows, "H1 count=0 must emit a tech_seo row"
    assert heading_rows[0]["issue_category"] == "Meta Tags"
    # No row escapes the 5-value schema enum.
    valid = {
        "Performance", "Layout Stability", "Meta Tags",
        "Structured Data", "Accessibility",
    }
    for r in out["tech_seo"]:
        assert r["issue_category"] in valid, (
            f"out-of-enum issue_category: {r['issue_category']!r}"
        )


def test_no_category_constant_escapes_issue_category_enum(
    master_excel_schema: dict,
) -> None:
    """Invariant lock: EVERY module-level CATEGORY_* constant must be a
    member of the schema-locked tech_seo.issue_category enum. This guards
    against a future CATEGORY_* reintroducing the 'Headings' bug class —
    any finding function can only emit one of these constants, so if they
    are all in-enum, no finding can produce an out-of-enum row."""
    enum_col = next(
        c for c in master_excel_schema["sheets"]["tech_seo"]["required_columns"]
        if c["name"] == "issue_category"
    )
    allowed = set(enum_col["enum"])
    category_consts = {
        name: getattr(tech_audit_transform, name)
        for name in dir(tech_audit_transform)
        if name.startswith("CATEGORY_")
    }
    assert category_consts, "expected at least one CATEGORY_* constant"
    offenders = {
        name: val for name, val in category_consts.items()
        if val not in allowed
    }
    assert not offenders, (
        f"CATEGORY_* constants outside issue_category enum {allowed}: "
        f"{offenders}"
    )


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
    """Combined payload exercises HIGH (perf<50), MEDIUM (H1 anomaly,
    under Meta Tags), and LOW (commercial page missing structured data,
    under Structured Data) severities — all of severityEnum's active
    emission tiers. LOW is sourced from the Structured Data category (not
    a Meta Tags title finding) so it surfaces as a distinct row impact:
    H1 + title findings now both aggregate under the single Meta Tags row
    at its max severity (MEDIUM)."""
    cp = {"items": [_content_item(
        "https://example.com/slow-page",
        h1_count=0,                 # MEDIUM (heading anomaly → Meta Tags)
        is_commercial=True,         # LOW (Structured Data missing)
        has_structured_data=False,
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
        r"\b(dentnotion|vento|eykom|bigcattr|calitte|lastiksa|"
        r"noraninsaat|adstark)\b",
        re.IGNORECASE,
    )
    assert not forbidden.search(text), (
        "tech_audit_transform.py must not carry slug literals "
        "(plugin-agnostik 0-tolerance)"
    )


def test_no_hardcoded_slug_in_skill_md() -> None:
    text = SKILL_MD.read_text("utf-8")
    forbidden = re.compile(
        r"\b(dentnotion|vento|eykom|bigcattr|calitte|lastiksa|"
        r"noraninsaat|adstark)\b",
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


# ---------------------------------------------------------------------------
# Test 14 — v1.8 Phase 5 SF MCP consumer wiring (D-SF-11 opt-in)
# ---------------------------------------------------------------------------

def test_use_sf_mcp_live_flag_in_frontmatter(
    skill_frontmatter_schema: dict,
) -> None:
    """v1.8 Phase 5 (D-SF-11): the tech-audit SKILL.md frontmatter MUST
    declare an opt-in `use_sf_mcp_live` boolean input. Default MUST be
    False so the existing 1184+ pytest baseline (file-based fixtures)
    remains regression-clean. Required MUST be False (opt-in only).

    Regression case: default False means the new live MCP code path
    is never triggered by the existing tests in this file, and they
    all continue to pass unchanged.
    """
    text = SKILL_MD.read_text("utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "SKILL.md must open with --- frontmatter ---"
    fm = yaml.safe_load(parts[1])

    inputs = fm["inputs"]
    assert "use_sf_mcp_live" in inputs, (
        "tech-audit frontmatter must declare `use_sf_mcp_live` per "
        "v1.8 Phase 5 / D-SF-11 (opt-in SF MCP consumer wiring)"
    )
    flag = inputs["use_sf_mcp_live"]
    assert flag["type"] == "boolean"
    assert flag["required"] is False, (
        "use_sf_mcp_live MUST be optional (opt-in only); required=true "
        "would break the 1184+ baseline regression contract"
    )
    assert flag["default"] is False, (
        "use_sf_mcp_live MUST default to False (file-based path stays "
        "the canonical contract; MCP is augmentation, not replacement)"
    )
    # Description must hint at the opt-in / D-SF-11 / SfMcpClient shape.
    desc = flag["description"]
    assert "SF MCP" in desc or "sf_mcp" in desc

    # Frontmatter still validates against the canonical schema with the
    # new flag added — defensive check that the additive change does
    # not break the Draft 7 contract.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(
        validator.iter_errors(fm), key=lambda e: list(e.absolute_path),
    )
    assert not errs, (
        "frontmatter invalid after use_sf_mcp_live added: "
        f"{[('/'.join(str(p) for p in e.absolute_path) or '<root>', e.message) for e in errs]}"
    )


def test_skill_md_documents_sf_mcp_live_pattern() -> None:
    """AC-13: the tech-audit SKILL.md SF MCP live mode branch MUST document
    the CORRECT real SF MCP API pattern (same class of fix as the
    orchestrator Step-5 dispatch landed in a714e43). The previous prose
    called a non-existent ``sf_generate_report(crawl_id=, report_name=,
    save_report=)`` shape and read non-existent ``response.get("truncated"/
    "rows")`` keys. The corrected branch must document:

      (1) `SfMcpClient` import from `scripts.util.sf_mcp_client`
      (2) `client.health()` preflight check (R9 mitigation)
      (3) AMBER fallback semantics ("falling back to file-based path")
      (4) crawl-id resolution via `sf_list_crawls` (matched on domain) +
          resilient `client.load_crawl(...)`
      (5) the real `sf_generate_report` schema via the orchestrator
          dispatch: category "Issues Overview", export to `file_path`
          (the >100KB cap is resolved by writing to disk, NOT a
          non-existent `truncated` flag)
      (6) the transform's `live_findings` merge kwarg

    This is a contract lock: the runtime body branch is interpreter prose,
    but the contract is verified here so a future SKILL.md edit cannot
    silently regress back to the broken (invented-arg) pattern.

    Also asserts the NATIVE tool naming convention is enforced
    (`"sf_generate_report"`, NOT `"sf__sf_generate_report"` or
    `"mcp__sf__sf_generate_report"`) per Manager dispatch.
    """
    text = SKILL_MD.read_text("utf-8")

    # (1) Import contract.
    assert "from scripts.util.sf_mcp_client import" in text, (
        "SKILL.md body must document the SfMcpClient import path"
    )
    assert "SfMcpClient" in text

    # (2) Preflight contract (R9 mitigation).
    assert "client.health()" in text, (
        "SKILL.md body must document the client.health() preflight "
        "per R9 mitigation"
    )

    # (3) AMBER fallback contract.
    assert "falling back to file-based path" in text, (
        "SKILL.md body must document the AMBER fallback message per "
        "R9 mitigation (never hard-fail when SF MCP unreachable)"
    )
    assert "amber_warnings" in text.lower() or "AMBER" in text

    # (4) Crawl-id resolution + resilient load (the previously-undefined
    #     `sf_crawl_id` free variable is now plumbed from sf_list_crawls).
    assert "sf_list_crawls" in text, (
        "SKILL.md body must resolve the crawl id via sf_list_crawls "
        "(the old `sf_crawl_id` free variable was never plumbed)"
    )
    assert "instanceDirName" in text, (
        "SKILL.md body must pick the crawl id from the sf_list_crawls "
        "entry's instanceDirName field (real SF shape)"
    )
    assert "load_crawl" in text, (
        "SKILL.md body must call the resilient client.load_crawl(...) "
        "(tolerates the client-side timeout, polls progress)"
    )

    # (5) Real sf_generate_report schema: category "Issues Overview" +
    #     file_path export (NOT crawl_id/report_name/save_report/truncated).
    assert '"sf_generate_report"' in text, (
        "SKILL.md body must use the NATIVE SF MCP tool name "
        '("sf_generate_report"); registry / wrapper forms forbidden'
    )
    assert "Issues Overview" in text, (
        "SKILL.md body must map issues_overview_report → SF report "
        'category "Issues Overview" (engine canonical → SF category)'
    )
    assert "file_path" in text, (
        "SKILL.md body must export via file_path (resolves the >100KB "
        "inline cap by writing to disk; OQ-FILEPATH-EXPORTS)"
    )
    assert "SF_EXPORT_DISPATCH" in text, (
        "SKILL.md body must cite the orchestrator's SF_EXPORT_DISPATCH "
        "(the live-proven canonical→SF mapping) rather than re-inventing"
    )
    # tech-audit specifically exports the canonical issues_overview_report.
    assert '"issues_overview_report"' in text, (
        "tech-audit SF MCP branch must export the canonical "
        "issues_overview_report (per spec line 122)"
    )

    # (6) The transform's live_findings merge kwarg.
    assert "live_findings" in text, (
        "SKILL.md body must pass the parsed CSV rows into "
        "transform(..., live_findings=...)"
    )
    assert "csv.DictReader" in text, (
        "SKILL.md body must parse the written Issues Overview CSV with "
        "csv.DictReader to build live_findings rows"
    )

    # Regression guard: the BROKEN invented-arg pattern must be GONE.
    assert "report_name=" not in text, (
        "SKILL.md must NOT pass report_name= (no such sf_generate_report arg)"
    )
    assert "save_report=" not in text, (
        "SKILL.md must NOT pass save_report= (no such sf_generate_report arg)"
    )
    assert 'response.get("truncated"' not in text, (
        "SKILL.md must NOT read a non-existent `truncated` flag — the real "
        "SF rejects >100KB inline; file_path export is the canonical path"
    )
    assert 'response.get("rows"' not in text, (
        "SKILL.md must NOT read a non-existent `rows` key — the real result "
        "is the MCP content envelope, parsed from the written CSV instead"
    )


# ---------------------------------------------------------------------------
# Test 15 — AC-13 live_findings merge (REAL merge, not grep)
# ---------------------------------------------------------------------------

def _issues_overview_row(
    *,
    issue_name: str,
    issue_type: str = "Warning",
    priority: str = "High",
    urls: str = "10",
    pct: str = "5.0",
    description: str = "",
    how_to_fix: str = "",
    help_url: str = "https://www.screamingfrog.co.uk/seo-spider/issues/",
) -> dict:
    """Build one SF 'Issues Overview' CSV-row dict (csv.DictReader shape).

    Columns mirror the real SF Issues Overview export header:
    Issue Name | Issue Type | Issue Priority | URLs | % of Total |
    Description | How To Fix | Help URL.
    """
    return {
        "Issue Name": issue_name,
        "Issue Type": issue_type,
        "Issue Priority": priority,
        "URLs": urls,
        "% of Total": pct,
        "Description": description,
        "How To Fix": how_to_fix,
        "Help URL": help_url,
    }


def test_live_findings_none_is_identical_baseline(lh_payload_poor: dict) -> None:
    """Regression: live_findings=None (the default) yields byte-identical
    output to omitting the kwarg entirely — the existing baseline behaviour
    is preserved."""
    out_default = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
    )
    out_explicit_none = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
        live_findings=None,
    )
    assert out_default == out_explicit_none


def test_live_findings_merges_additively_increases_rowcount(
    lh_payload_poor: dict,
) -> None:
    """AC-13 core: passing SF Issues Overview rows ADDITIVELY merges them
    into the tech_seo aggregation. rowcount(with) >= rowcount(without),
    and the SF issues surface as tech_seo rows with the mapped fields.

    AC-10 Task D: the SF Issue Name is routed to the locked tech_seo enum
    category (NOT written raw). We pick two issues that route into tech_seo
    as NEW categories the lighthouse-only baseline lacks: a Meta-Description
    issue (→ Meta Tags, High) and a Structured-Data issue (→ Structured Data,
    Medium)."""
    live = [
        _issues_overview_row(
            issue_name="Meta Description: Missing",
            priority="High",
            urls="43",
            description="URLs with no meta description element.",
            how_to_fix="Add a unique meta description per page.",
        ),
        _issues_overview_row(
            issue_name="Structured Data: Validation Errors",
            priority="Medium",
            urls="7",
            description="URLs whose structured data fails validation.",
            how_to_fix="Fix the schema.org validation errors.",
        ),
    ]

    base = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
    )
    merged = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
        live_findings=live,
    )

    # Additive: never fewer rows than the no-live baseline.
    assert len(merged["tech_seo"]) >= len(base["tech_seo"])
    # The two SF issues each become a tech_seo row under the MAPPED enum
    # category (new categories the lighthouse-only baseline lacked).
    cats = {r["issue_category"] for r in merged["tech_seo"]}
    assert "Meta Tags" in cats          # Meta Description: Missing → Meta Tags
    assert "Structured Data" in cats    # Structured Data: ... → Structured Data

    # Field mapping is correct on the High-priority SF issue; the raw Issue
    # Name is preserved in the detail (no info loss through the enum mapping).
    meta_row = next(
        r for r in merged["tech_seo"] if r["issue_category"] == "Meta Tags"
    )
    assert meta_row["impact"] == tech_audit_transform.SEVERITY_HIGH  # High→HIGH
    assert meta_row["priority"] == "P0"
    assert "43" in meta_row["affected_urls"]                         # URLs col
    assert "meta description" in meta_row["resolution"].lower()      # How To Fix
    assert "Meta Description: Missing" in meta_row["detail"]         # raw name kept

    # severityEnum + issue_category enum stay strict for every merged row.
    for r in merged["tech_seo"]:
        assert r["impact"] in tech_audit_transform.SEVERITY_ENUM
        assert r["issue_category"] in _TECH_SEO_ENUM
        assert set(r.keys()) == set(tech_audit_transform.TECH_SEO_COLUMNS)

    # The baseline lighthouse Performance row still survives the merge.
    assert "Performance" in cats


def test_live_findings_priority_maps_to_severity_enum() -> None:
    """Every SF Issue Priority string maps onto the strict severityEnum;
    unknown/blank priority degrades safely (never emits a non-enum value).

    AC-10 Task D: issue names are routed to DISTINCT tech_seo enum categories
    (one per priority tier) so the per-category aggregation keeps the rows
    separate and the priority→severity mapping is observable per row."""
    live = [
        _issues_overview_row(issue_name="PageSpeed: Reduce Unused JavaScript",
                             priority="High", urls="1", how_to_fix="fix a"),
        _issues_overview_row(issue_name="Images: Missing Size Attributes",
                             priority="Medium", urls="2", how_to_fix="fix b"),
        _issues_overview_row(issue_name="Images: Missing Alt Attribute",
                             priority="Low", urls="3", how_to_fix="fix c"),
        _issues_overview_row(issue_name="Structured Data: Validation Warnings",
                             priority="", urls="4", how_to_fix="fix d"),
    ]
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=None, live_findings=live,
    )
    by_cat = {r["issue_category"]: r for r in out["tech_seo"]}
    assert by_cat["Performance"]["impact"] == tech_audit_transform.SEVERITY_HIGH
    assert by_cat["Layout Stability"]["impact"] == tech_audit_transform.SEVERITY_MEDIUM
    assert by_cat["Accessibility"]["impact"] == tech_audit_transform.SEVERITY_LOW
    # Unknown/blank priority must still be a valid severityEnum value (degrade).
    assert by_cat["Structured Data"]["impact"] in tech_audit_transform.SEVERITY_ENUM
    for r in out["tech_seo"]:
        assert r["impact"] in tech_audit_transform.SEVERITY_ENUM
        assert r["issue_category"] in _TECH_SEO_ENUM


def test_live_findings_detail_falls_back_to_issue_type() -> None:
    """When an SF row has no Description, the detail label falls back to Issue
    Type (never empty — the detail column carries something descriptive).

    AC-10 Task D: "Page Titles: Over 60 Characters" routes to the Meta Tags
    enum category; the raw Issue Name is preserved in the detail alongside the
    Issue Type fallback."""
    live = [
        _issues_overview_row(
            issue_name="Page Titles: Over 60 Characters",
            issue_type="Opportunity",
            priority="Low",
            urls="12",
            description="",                 # no description
            how_to_fix="Shorten the title.",
        ),
    ]
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=None, live_findings=live,
    )
    row = next(
        r for r in out["tech_seo"]
        if r["issue_category"] == "Meta Tags"
    )
    assert "Opportunity" in row["detail"]   # Issue Type fallback
    # The original SF Issue Name is preserved in the detail (no info loss).
    assert "Page Titles: Over 60 Characters" in row["detail"]


def test_live_findings_dedupes_against_existing_category() -> None:
    """If an SF Issue Name routes to a category that an existing DFS finding
    already populates, the merge de-dupes by issue_category (one row, max
    severity wins) — the transform's existing per-category aggregation handles
    it.

    AC-10 Task D: the SF issue name routes to the Performance enum category
    (PageSpeed: ...) rather than being written raw, so it genuinely collides
    with the lighthouse-derived Performance row."""
    # lighthouse_poor fires a 'Performance' HIGH row; feed an SF PageSpeed
    # issue at LOW priority — both route to 'Performance' and must collapse to
    # ONE row at HIGH.
    lh = {"items": [_lighthouse_item(
        "https://example.com/slow", perf=30, lcp_s=5.0,
    )]}
    live = [
        _issues_overview_row(
            issue_name="PageSpeed: Reduce Unused CSS", priority="Low",
            urls="https://example.com/other", how_to_fix="tune it",
        ),
    ]
    out = tech_audit_transform.transform(
        lighthouse_raw=lh, content_parsing_raw=None, live_findings=live,
    )
    perf_rows = [r for r in out["tech_seo"] if r["issue_category"] == "Performance"]
    assert len(perf_rows) == 1, "same-category SF issue must de-dupe, not duplicate"
    # Max severity wins (HIGH from the lighthouse rule beats LOW from SF).
    assert perf_rows[0]["impact"] == tech_audit_transform.SEVERITY_HIGH


def test_live_findings_empty_list_is_noop(lh_payload_poor: dict) -> None:
    """An empty live_findings list behaves like None (no extra rows)."""
    base = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
    )
    merged = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
        live_findings=[],
    )
    assert merged["tech_seo"] == base["tech_seo"]


def test_live_findings_bom_prefixed_first_key_still_merges(
    lh_payload_poor: dict,
) -> None:
    """Live-caught regression (2026-06-02): SF's CSV export writes a UTF-8 BOM
    before the first header field, so ``csv.DictReader``'s first key arrives as
    ``'﻿"Issue Name"'`` (the BOM precedes the opening quote, defeating
    csv's quote-stripping). The transform normalizes keys (``_clean_key``) so
    the row is NOT silently dropped — without it, every SF row would map to a
    ``None`` Issue Name and the merge would yield zero rows.

    AC-10 Task D: the issue name here routes INTO tech_seo (Meta Description:
    Missing → Meta Tags) so the BOM-recovery is observable as a real tech_seo
    row + live_findings_count == 1."""
    clean = _issues_overview_row(
        issue_name="Meta Description: Missing", priority="High", urls="43",
    )
    bom_row = {'﻿"Issue Name"': clean["Issue Name"]}
    bom_row.update({k: v for k, v in clean.items() if k != "Issue Name"})

    base = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
    )
    live = tech_audit_transform.transform(
        lighthouse_raw=lh_payload_poor, content_parsing_raw=None,
        live_findings=[bom_row],
    )
    assert len(live["tech_seo"]) > len(base["tech_seo"])
    # The BOM-keyed row is recovered, routed (Meta Tags), and counted.
    assert any(r["issue_category"] == "Meta Tags" for r in live["tech_seo"])
    assert live["meta"]["live_findings_count"] == 1
    # The row never leaks an out-of-enum category into the tech_seo sheet.
    for r in live["tech_seo"]:
        assert r["issue_category"] in _TECH_SEO_ENUM


# ---------------------------------------------------------------------------
# Test 16 — AC-10 Task D: SF issue names route to the locked tech_seo
# issue_category 5-enum via sf_issue_taxonomy (out-of-enum bug fix)
# ---------------------------------------------------------------------------

#: The schema-locked tech_seo issue_category enum (master-excel.schema.json
#: tech_seo sheet, col A). The SF live-merge MUST only ever emit these.
_TECH_SEO_ENUM = frozenset({
    "Performance", "Layout Stability", "Meta Tags",
    "Structured Data", "Accessibility",
})

#: Real SF "Issues Overview" export captured from a live aluminumstation-ca
#: crawl (2026-06-02). 42 issues spanning every routing branch — the canonical
#: regression fixture for the out-of-enum bug.
_REAL_ISSUES_CSV = Path(
    "/Users/apple/Documents/platinum-seo-workspace/projects/"
    "aluminumstation-ca/sf-exports/2026-06-02/raw/issues_overview_report.csv"
)


def _load_real_issue_rows() -> list[dict]:
    """Read the live SF Issues Overview CSV as csv.DictReader row dicts.

    utf-8-sig strips the SF-written BOM. Skipped (not failed) when the
    workspace export is absent so the engine repo's suite stays runnable
    in isolation.
    """
    import csv

    if not _REAL_ISSUES_CSV.exists():
        pytest.skip(f"live SF export not present: {_REAL_ISSUES_CSV}")
    with _REAL_ISSUES_CSV.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_live_finding_never_emits_out_of_enum_category() -> None:
    """AC-10 Task D regression: feeding the REAL SF issues_overview_report.csv
    through the live-merge must yield ONLY in-enum tech_seo categories.

    Before the fix, ``_live_finding_to_finding`` wrote the raw SF Issue Name
    (e.g. ``"Pagination: Pagination URL Not in Anchor Tag"``, ``"H1: Missing"``)
    straight into ``issue_category`` — 42/42 rows out-of-enum, which would
    raise RowSchemaError at the transaction write step. After the fix every
    surviving tech_seo row's ``issue_category`` is one of the locked 5 values.
    """
    rows = _load_real_issue_rows()
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=None, live_findings=rows,
    )
    assert out["tech_seo"], "real SF export must produce at least one tech_seo row"
    offenders = [
        r["issue_category"] for r in out["tech_seo"]
        if r["issue_category"] not in _TECH_SEO_ENUM
    ]
    assert offenders == [], (
        "live SF merge emitted out-of-enum issue_category value(s): "
        f"{sorted(set(offenders))}"
    )


def test_live_finding_drops_non_tech_seo_issues() -> None:
    """Security-header and Response-Code issues do NOT belong in tech_seo —
    they route to robots_txt / redirect_404 via sf_issue_taxonomy, so
    ``_live_finding_to_finding`` returns None and they never appear in the
    tech_seo output."""
    hsts = _issues_overview_row(
        issue_name="Security: Missing HSTS Header",
        priority="High", urls="120",
        description="Pages served without an HSTS response header.",
        how_to_fix="Add Strict-Transport-Security to the response.",
    )
    resp4xx = _issues_overview_row(
        issue_name="Response Codes: Internal Client Error (4xx)",
        priority="High", urls="3",
        description="Internal URLs returning a 4xx status.",
        how_to_fix="Fix or remove the broken links.",
    )

    # Unit level: the mapper drops each.
    assert tech_audit_transform._live_finding_to_finding(hsts) is None
    assert tech_audit_transform._live_finding_to_finding(resp4xx) is None

    # Transform level: neither surfaces as a tech_seo row.
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=None,
        live_findings=[hsts, resp4xx],
    )
    assert out["tech_seo"] == [], (
        "security / response-code issues must not produce tech_seo rows"
    )


@pytest.mark.parametrize(
    "issue_name,expected_category",
    [
        ("Images: Over 100 kB", "Performance"),
        ("Structured Data: Validation Errors", "Structured Data"),
        ("H1: Missing", "Meta Tags"),
        ("Images: Missing Alt Attribute", "Accessibility"),
        ("Images: Missing Size Attributes", "Layout Stability"),
    ],
)
def test_live_finding_maps_known_issues(
    issue_name: str, expected_category: str,
) -> None:
    """Known SF issues map to the correct locked tech_seo category, AND the
    original SF Issue Name is preserved in the detail/label (no info loss)."""
    row = _issues_overview_row(
        issue_name=issue_name, priority="Medium", urls="9",
        description="A real SF description for the issue.",
        how_to_fix="Remediate per SF guidance.",
    )
    finding = tech_audit_transform._live_finding_to_finding(row)
    assert finding is not None, f"{issue_name!r} should route to tech_seo"
    assert finding.category == expected_category
    # The original Issue Name survives in the label (prepended to detail).
    assert issue_name in finding.label, (
        f"original Issue Name {issue_name!r} must be preserved in the label"
    )

    # End-to-end: the category surfaces on the aggregated row, in-enum, and the
    # Issue Name is still visible in the row detail.
    out = tech_audit_transform.transform(
        lighthouse_raw=None, content_parsing_raw=None, live_findings=[row],
    )
    cats = {r["issue_category"] for r in out["tech_seo"]}
    assert expected_category in cats
    assert cats <= _TECH_SEO_ENUM
    row_out = next(
        r for r in out["tech_seo"] if r["issue_category"] == expected_category
    )
    assert issue_name in row_out["detail"]


def test_live_finding_real_csv_routing_counts() -> None:
    """The 42 real SF issues split deterministically: 30 flow into tech_seo
    (every one of the 5 enum categories represented), 12 route out
    (security / non-ascii / pagination / crawl-depth → robots_txt;
    response-codes → redirect_404) and are dropped from the tech_seo sheet.
    """
    rows = _load_real_issue_rows()
    assert len(rows) == 42, "fixture drift — expected the 42-issue live export"

    kept = [
        f for f in (
            tech_audit_transform._live_finding_to_finding(r) for r in rows
        )
        if f is not None
    ]
    dropped = len(rows) - len(kept)
    assert len(kept) == 30, f"expected 30 tech_seo issues, got {len(kept)}"
    assert dropped == 12, f"expected 12 dropped issues, got {dropped}"

    # All five enum categories are exercised by the real export.
    kept_cats = {f.category for f in kept}
    assert kept_cats == _TECH_SEO_ENUM, (
        f"real export should cover all 5 enum categories, got {sorted(kept_cats)}"
    )
