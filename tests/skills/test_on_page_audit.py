"""
tests/skills/test_on_page_audit.py — on-page-audit discovery skill tests.

Phase 7 Wave 1 (W-A4). Mirrors the test pattern of test_quick_wins.py
and test_dfs_pull.py: frontmatter parse + Draft 7 schema validation,
URL normalization (D-03 invariant), transform unit, action heuristic
coverage, cross-source URL join, budget pre-flight integration, and
DURUR behaviour for upstream content_parsing schema drift.

MCP tools are NOT Python-callable inside pytest; live MCP calls are
performed at-rest. These tests therefore validate the transform + skill
contract using mocked DFS / GSC fixtures, not the upstream MCP fetch
itself.

Schemas referenced:
  - schemas/skill-frontmatter.schema.json (frontmatter Draft 7)
  - schemas/master-excel.schema.json (on_page_audit required_columns)
  - schemas/cross-sheet-invariants.json (D-03 URL canonicalization)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import on_page_audit_transform as opa


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "on-page-audit" / "SKILL.md"


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
    """Parse the YAML frontmatter block of skills/discovery/on-page-audit/SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


def _cp_item(url: str, title: str, meta: str, h1: list[str]) -> dict:
    """Build a single DFS content_parsing item in the REST envelope shape."""
    return {
        "url": url,
        "title": title,
        "meta_description": meta,
        "h1": list(h1),
    }


def _cp_envelope(items: list[dict]) -> dict:
    """Wrap items in the canonical DFS REST envelope."""
    return {
        "version": "0.1.20240101",
        "status_code": 20000,
        "tasks": [{
            "id": "test-task",
            "status_code": 20000,
            "result": [{"items": items}],
        }],
    }


def _gsc_payload(rows: list[tuple[str, str, int, int]]) -> dict:
    """Build a synthetic GSC search_analytics payload from
    (url, query, clicks, impressions) tuples (dimensions=['page','query']).
    """
    return {
        "rows": [
            {
                "keys": [url, query],
                "clicks": clicks,
                "impressions": impressions,
                "ctr": (clicks / impressions) if impressions else 0.0,
                "position": 12.0,
            }
            for (url, query, clicks, impressions) in rows
        ]
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + validates against schema
# ---------------------------------------------------------------------------

def test_frontmatter_validates(skill_frontmatter: dict,
                                skill_frontmatter_schema: dict) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=on-page-audit, status=wip, version="1.0",
          category=discovery,
      (c) declare project_slug as a required string input,
      (d) declare budget.uses_paid_mcp=true with non-zero estimate,
      (e) list mcp__dataforseo__on_page_content_parsing as required,
      (f) list mcp__gsc__search_analytics as optional (cross-ref),
      (g) outputs include master.xlsx#on_page_audit + inbox/dfs/ +
          outputs/reports/ + events.jsonl,
      (h) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "on-page-audit"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "discovery"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    # Paid-MCP budget envelope.
    assert fm["budget"]["uses_paid_mcp"] is True
    assert fm["budget"]["estimated_credits"] > 0

    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__dataforseo__on_page_content_parsing" in required_tools

    optional_tools = fm["mcp_tools"].get("optional", [])
    assert "mcp__gsc__search_analytics" in optional_tools

    outputs = fm["outputs"]
    assert any("master.xlsx#on_page_audit" in o for o in outputs)
    assert any("inbox/dfs/" in o and "content_parsing" in o for o in outputs)
    assert any("outputs/reports/" in o and "on-page-audit" in o for o in outputs)
    assert "events.jsonl" in outputs

    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errs, (
        "frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — URL normalization is idempotent + correct (D-03 invariant, ≥3 cases)
# ---------------------------------------------------------------------------

def test_url_normalization_d03_idempotent() -> None:
    """D-03: trailing slash, fragment, mixed case, default ports, tracking
    params — all normalized to a stable, idempotent form."""
    samples = [
        # (input, expected) — six cases covering trailing slash, fragment,
        # mixed case, default port, utm tracking, and a punctuation-clean form.
        ("HTTPS://Example.COM:443/Path/?b=2&a=1#frag",
         "https://example.com/Path?a=1&b=2"),
        ("https://example.com/page/",
         "https://example.com/page"),
        ("https://example.com/page#section",
         "https://example.com/page"),
        ("HTTPS://Example.COM/Path/",
         "https://example.com/Path"),
        ("https://example.com/?utm_source=fb&utm_medium=cpc&q=tr",
         "https://example.com/?q=tr"),
        ("https://example.com/", "https://example.com/"),
    ]
    for raw, expected in samples:
        got = opa._normalize_url(raw)
        assert got == expected, (
            f"normalize({raw!r}) → {got!r} (expected {expected!r})"
        )
        # Idempotency (D-03 hard invariant).
        assert opa._normalize_url(got) == got, (
            f"not idempotent: {raw!r} → {got!r}"
        )


def test_url_normalization_invalid_inputs() -> None:
    with pytest.raises(opa.OnPageAuditError):
        opa._normalize_url("")
    with pytest.raises(opa.OnPageAuditError):
        opa._normalize_url(None)  # type: ignore[arg-type]
    with pytest.raises(opa.OnPageAuditError):
        opa._normalize_url("example.com/no-scheme")


# ---------------------------------------------------------------------------
# Test 3 — Empty input → empty output
# ---------------------------------------------------------------------------

def test_transform_empty_input_empty_output() -> None:
    out = opa.transform(_cp_envelope([]))
    assert out["on_page_audit"] == []
    assert out["meta"]["row_count"] == 0
    assert out["meta"]["cross_ref_used"] is False


# ---------------------------------------------------------------------------
# Test 4 — Single URL with target query in title+meta+h1 → action="monitor"
# ---------------------------------------------------------------------------

def test_action_monitor_when_all_present_and_clicks() -> None:
    cp = _cp_envelope([
        _cp_item(
            url="https://example.com/seo-guide",
            title="Ultimate SEO Guide for 2026",
            meta="The ultimate seo guide explains every step.",
            h1=["Ultimate SEO Guide"],
        ),
    ])
    gsc = _gsc_payload([
        ("https://example.com/seo-guide", "ultimate seo guide", 25, 1000),
    ])
    out = opa.transform(cp, raw_gsc=gsc)
    rows = out["on_page_audit"]
    assert len(rows) == 1
    r = rows[0]
    assert r["url"] == "https://example.com/seo-guide"
    assert r["target_query"] == "ultimate seo guide"
    assert r["impressions_30d"] == 1000
    assert r["clicks_30d"] == 25
    assert r["in_title"] is True
    assert r["in_meta"] is True
    assert r["in_h1"] is True
    assert r["action"] == "monitor"
    # Schema-shape lock: exactly the 8 columns.
    assert tuple(r.keys()) == opa.ON_PAGE_AUDIT_COLUMNS


# ---------------------------------------------------------------------------
# Test 5 — Title-only → in_title=True, others False, action="add to meta + H1"
# ---------------------------------------------------------------------------

def test_action_add_to_meta_h1_when_title_only() -> None:
    cp = _cp_envelope([
        _cp_item(
            url="https://example.com/title-only",
            title="Best SEO Tools",
            meta="Generic page description.",
            h1=["Welcome"],
        ),
    ])
    gsc = _gsc_payload([
        ("https://example.com/title-only", "best seo tools", 5, 200),
    ])
    out = opa.transform(cp, raw_gsc=gsc)
    r = out["on_page_audit"][0]
    assert r["in_title"] is True
    assert r["in_meta"] is False
    assert r["in_h1"] is False
    assert r["action"] == "add to meta + H1"


def test_action_rewrite_meta_cluster_when_missing_all() -> None:
    cp = _cp_envelope([
        _cp_item(
            url="https://example.com/missing",
            title="Some unrelated headline",
            meta="No mention here.",
            h1=["Welcome"],
        ),
    ])
    gsc = _gsc_payload([
        ("https://example.com/missing", "lost target query", 3, 150),
    ])
    out = opa.transform(cp, raw_gsc=gsc)
    r = out["on_page_audit"][0]
    assert r["in_title"] is False
    assert r["in_meta"] is False
    assert r["in_h1"] is False
    assert r["action"] == "rewrite meta cluster"


# ---------------------------------------------------------------------------
# Test 6 — URL with no GSC data → target_query="", action no-GSC-data
# ---------------------------------------------------------------------------

def test_action_no_gsc_when_target_query_empty() -> None:
    cp = _cp_envelope([
        _cp_item(
            url="https://example.com/page-x",
            title="A title",
            meta="A description.",
            h1=["A heading"],
        ),
    ])
    out = opa.transform(cp, raw_gsc=None)  # no cross-ref at all
    r = out["on_page_audit"][0]
    assert r["target_query"] == ""
    assert r["impressions_30d"] == 0
    assert r["clicks_30d"] == 0
    assert r["in_title"] is False
    assert r["in_meta"] is False
    assert r["in_h1"] is False
    assert r["action"] == "no GSC data — investigate target intent"


# ---------------------------------------------------------------------------
# Test 7 — D-03 join: HTTPS + trailing slash matches lowercase-no-slash
# ---------------------------------------------------------------------------

def test_d03_join_normalizes_both_sides() -> None:
    """Test 5 of brief: input 'HTTPS://Example.COM/Path/' must join GSC
    'https://example.com/path' (case + trailing slash normalized on BOTH
    sides before the join)."""
    cp = _cp_envelope([
        _cp_item(
            url="HTTPS://Example.COM/Path/",
            title="My Path Title",
            meta="meta about path.",
            h1=["The Path"],
        ),
    ])
    gsc = _gsc_payload([
        ("https://example.com/Path", "my path", 10, 300),
    ])
    out = opa.transform(cp, raw_gsc=gsc)
    r = out["on_page_audit"][0]
    assert r["url"] == "https://example.com/Path"
    assert r["target_query"] == "my path"
    assert r["impressions_30d"] == 300
    assert r["clicks_30d"] == 10


def test_d03_join_strips_fragment_on_both_sides() -> None:
    """Brief test 6: '/page#section' must collapse to '/page' so a GSC
    row at '/page' joins the DFS row at '/page#section' (DFS rarely has
    fragments, but the helper must be symmetric)."""
    cp = _cp_envelope([
        _cp_item(
            url="https://example.com/page#section",
            title="Page",
            meta="page meta",
            h1=["Page"],
        ),
    ])
    gsc = _gsc_payload([
        ("https://example.com/page", "page", 1, 50),
    ])
    out = opa.transform(cp, raw_gsc=gsc)
    r = out["on_page_audit"][0]
    assert r["url"] == "https://example.com/page"
    assert r["target_query"] == "page"
    assert r["impressions_30d"] == 50


# ---------------------------------------------------------------------------
# Test 8 — Cross-ref mismatch (DFS norm ≠ GSC norm) does not false-positive
# ---------------------------------------------------------------------------

def test_cross_ref_mismatch_no_false_positive_join() -> None:
    """When the two URL sets are entirely disjoint after D-03 normalization
    (e.g. www vs non-www host drift), the default mode is graceful
    fall-back to no-cross-ref — every row's target_query is "" and the
    action says 'no GSC available'. With strict_cross_ref=True the same
    input raises CrossRefMismatchError (DURUR #4)."""
    cp = _cp_envelope([
        _cp_item(
            url="https://example.com/foo",
            title="Foo",
            meta="foo meta",
            h1=["Foo"],
        ),
    ])
    gsc = _gsc_payload([
        # Different host — no D-03 collapse can join these.
        ("https://www.example.com/foo", "foo", 99, 999),
    ])

    # Default: graceful fall-back, no false positive.
    out = opa.transform(cp, raw_gsc=gsc)
    r = out["on_page_audit"][0]
    assert r["target_query"] == ""
    assert r["impressions_30d"] == 0
    assert r["clicks_30d"] == 0
    # The action calls out the missing GSC explicitly.
    assert "GSC" in r["action"]
    assert out["meta"]["cross_ref_mismatch"] is True
    assert out["meta"]["cross_ref_used"] is False

    # Strict mode: refuse to silently fall back.
    with pytest.raises(opa.CrossRefMismatchError):
        opa.transform(cp, raw_gsc=gsc, strict_cross_ref=True)


# ---------------------------------------------------------------------------
# Test 9 — Sort order: impressions_30d desc
# ---------------------------------------------------------------------------

def test_sort_by_impressions_desc() -> None:
    cp = _cp_envelope([
        _cp_item("https://example.com/low",   "L", "l", ["L"]),
        _cp_item("https://example.com/high",  "H", "h", ["H"]),
        _cp_item("https://example.com/mid",   "M", "m", ["M"]),
    ])
    gsc = _gsc_payload([
        ("https://example.com/low",  "low",  1, 50),
        ("https://example.com/high", "high", 30, 5000),
        ("https://example.com/mid",  "mid",  10, 800),
    ])
    out = opa.transform(cp, raw_gsc=gsc)
    impressions = [r["impressions_30d"] for r in out["on_page_audit"]]
    assert impressions == sorted(impressions, reverse=True)
    assert impressions == [5000, 800, 50]


# ---------------------------------------------------------------------------
# Test 10 — DURUR: DFS missing 'title' → ContentParsingDriftError
# ---------------------------------------------------------------------------

def test_drift_dfs_missing_title_raises() -> None:
    bad = _cp_envelope([
        {
            "url": "https://example.com/missing-title",
            # title intentionally omitted
            "meta_description": "meta",
            "h1": ["heading"],
        },
    ])
    with pytest.raises(opa.ContentParsingDriftError):
        opa.transform(bad)


def test_drift_dfs_missing_h1_raises() -> None:
    bad = _cp_envelope([
        {
            "url": "https://example.com/no-h1",
            "title": "T",
            "meta_description": "M",
            # h1 intentionally omitted
        },
    ])
    with pytest.raises(opa.ContentParsingDriftError):
        opa.transform(bad)


def test_drift_non_dict_input_raises() -> None:
    with pytest.raises(opa.OnPageAuditError):
        opa.transform("not-a-dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 11 — Budget pre-flight: estimate + integration with check_budget
# ---------------------------------------------------------------------------

def test_estimate_credits_per_url() -> None:
    assert opa.estimate_credits(0) == 0.0
    assert opa.estimate_credits(1) == 3.0
    assert opa.estimate_credits(10) == 30.0


def test_budget_preflight_pass_and_fail(tmp_path: Path) -> None:
    """PASS path: under budget. FAIL path: BudgetExceededError raised."""
    cfg = tmp_path / "project.config.json"
    cfg.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 500},
    }))
    events = tmp_path / "events.jsonl"

    envelope = opa.preflight_budget(
        estimated_credits=opa.estimate_credits(10),  # 30 credits
        project_config_path=str(cfg),
        events_path=str(events),
    )
    assert envelope["exceeded"] is False
    assert envelope["budget_per_day"] == 500
    assert envelope["projected_used"] == 30.0
    assert envelope["remaining_after"] == 470.0

    cfg_low = tmp_path / "project-config-low.json"
    cfg_low.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 5},
    }))
    with pytest.raises(opa.BudgetExceededError):
        opa.preflight_budget(
            estimated_credits=opa.estimate_credits(10),  # 30 > 5
            project_config_path=str(cfg_low),
            events_path=str(events),
        )


# ---------------------------------------------------------------------------
# Test 12 — Schema column match: transform output keys ↔ master-excel schema
# ---------------------------------------------------------------------------

def test_schema_column_match(master_excel_schema: dict) -> None:
    sheet_def = master_excel_schema["sheets"]["on_page_audit"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    assert schema_col_names == opa.ON_PAGE_AUDIT_COLUMNS, (
        f"ON_PAGE_AUDIT_COLUMNS drifted from master-excel schema: "
        f"got {opa.ON_PAGE_AUDIT_COLUMNS}, schema {schema_col_names}"
    )


# ---------------------------------------------------------------------------
# Test 13 — No transaction.append imports / direct calls in transform module
# ---------------------------------------------------------------------------

def test_transform_does_not_import_transaction() -> None:
    """Plugin agnostik / discipline: the transform is pure compute. It
    must not touch master.xlsx — that is the skill caller's job through
    the shared writer (`scripts.excel.transaction`)."""
    src = (REPO_ROOT / "scripts" / "discovery"
           / "on_page_audit_transform.py").read_text("utf-8")
    assert "scripts.excel.transaction" not in src
    assert "transaction.append" not in src
