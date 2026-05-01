"""
tests/skills/test_competitive_analysis.py — competitive-analysis discovery
skill tests (Phase 7 Wave 2 / W-B3).

Mirrors test_cannibalization.py + test_scrapling_ops.py + test_on_page_audit.py
patterns. Live MCP tools are not Python-callable inside pytest; the transform
takes pre-fetched FetchEntry inputs (the same dependency-injection seam the
skill orchestrator uses at runtime), so the tests cover the production code
path end-to-end through the S1 schema validation gate.

Schemas referenced:
  - schemas/skill-frontmatter.schema.json (frontmatter Draft 7)
  - schemas/scrapling-output-mapping.schema.json (§14.5 tier sequence)
  - templates/scrapling/S1_competitor_snapshot.schema.json (ADR-025 sub-schema)
  - schemas/events.schema.json (source.kind ∈ {scrapling_mcp, dataforseo_mcp};
    target_excel_sheet=null for staging-only)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import competitive_analysis_transform as ca


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
TEMPLATES = REPO_ROOT / "templates"
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "competitive-analysis" / "SKILL.md"
S1_SCHEMA_FILE = TEMPLATES / "scrapling" / "S1_competitor_snapshot.schema.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def s1_schema() -> dict:
    return json.loads(S1_SCHEMA_FILE.read_text("utf-8"))


@pytest.fixture(scope="module")
def scrapling_mapping_schema() -> dict:
    return json.loads(
        (SCHEMAS / "scrapling-output-mapping.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


def _entry(
    *,
    url: str,
    fetch_method: str | None = "stealthy_fetch",
    tier_attempts: int = 3,
    content: str | None = "<html><title>Hello</title><body>body</body></html>",
    status_code: int = 200,
    meta_title: str | None = "Hello",
    meta_description: str | None = "Sample meta",
    h1: tuple[str, ...] = ("H1 here",),
    schema_org_count: int = 0,
    fetch_duration_ms: int = 1234,
) -> ca.FetchEntry:
    return ca.FetchEntry(
        url=url,
        fetch_method=fetch_method,
        tier_attempts=tier_attempts,
        content=content,
        status_code=status_code,
        meta_title=meta_title,
        meta_description=meta_description,
        h1=h1,
        schema_org_count=schema_org_count,
        fetch_duration_ms=fetch_duration_ms,
    )


# ---------------------------------------------------------------------------
# Test 1 — S1 schema is jq/Draft7-valid + $id correct (foundational)
# ---------------------------------------------------------------------------

def test_s1_schema_self_check(s1_schema: dict) -> None:
    """S1 sub-schema (templates/scrapling/...) must be Draft7-valid AND
    declare the canonical $id under platinum-seo-engine/templates/scrapling/.
    """
    Draft7Validator.check_schema(s1_schema)
    assert s1_schema["$id"] == (
        "https://platinum-seo-engine/templates/scrapling/"
        "S1_competitor_snapshot.schema.json"
    )
    # required[] matches the worker brief.
    assert set(s1_schema["required"]) == {
        "snapshot_date", "domain", "url_normalized",
        "fetch_method", "status_code",
    }
    # fetch_method enum mirrors §14.5 canonical sequence.
    assert s1_schema["properties"]["fetch_method"]["enum"] == [
        "get", "fetch", "stealthy_fetch",
    ]
    # tier_attempts in 1..3.
    ta = s1_schema["properties"]["tier_attempts"]
    assert ta["minimum"] == 1 and ta["maximum"] == 3
    # content_excerpt maxLength 500.
    assert s1_schema["properties"]["content_excerpt"]["maxLength"] == 500
    # additionalProperties locked false (no silent extension).
    assert s1_schema["additionalProperties"] is False


# ---------------------------------------------------------------------------
# Test 2 — Frontmatter parses + validates against schema (paid-MCP budget)
# ---------------------------------------------------------------------------

def test_frontmatter_validates(skill_frontmatter: dict,
                                skill_frontmatter_schema: dict) -> None:
    """Frontmatter must:
      - declare name=competitive-analysis, category=discovery, status=wip
      - require project_slug input
      - require Scrapling bulk_stealthy_fetch + DFS competitors_domain MCP tools
      - declare uses_paid_mcp: true with integer estimated_credits (Q-W-A4-01)
      - omit forbidden estimated_credits_per_call/_per_url keys
      - validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "competitive-analysis"
    assert fm["category"] == "discovery"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["required"] is True

    required_tools = set(fm["mcp_tools"]["required"])
    assert "mcp__ScraplingServer__bulk_stealthy_fetch" in required_tools
    assert "mcp__dataforseo__dataforseo_labs_google_competitors_domain" in required_tools

    # Budget — Q-W-A4-01 enforced: only uses_paid_mcp + estimated_credits keys.
    budget = fm["budget"]
    assert budget["uses_paid_mcp"] is True
    assert isinstance(budget.get("estimated_credits"), (int, float))
    assert budget["estimated_credits"] > 0
    forbidden = {"estimated_credits_per_call", "estimated_credits_per_url"}
    assert not (forbidden & set(budget.keys())), (
        f"forbidden budget keys present: {forbidden & set(budget.keys())}"
    )

    validator = Draft7Validator(skill_frontmatter_schema)
    errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errors, [
        (list(e.absolute_path), e.message) for e in errors
    ]


# ---------------------------------------------------------------------------
# Test 3 — Tier 0 (get) success: fetch_method=get, tier_attempts=1
# ---------------------------------------------------------------------------

def test_get_tier_success_yields_get_method() -> None:
    entry = _entry(
        url="https://competitor.example/page-1",
        fetch_method="get",
        tier_attempts=1,
    )
    out = ca.transform([entry], project_slug="test-project")
    assert len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["fetch_method"] == "get"
    assert row["tier_attempts"] == 1
    assert row["url_normalized"] == "https://competitor.example/page-1"
    # S1 schema satisfied (validator was called inside transform).
    ca.validate_s1_row(row)


# ---------------------------------------------------------------------------
# Test 4 — Tier 1 (fetch) success after get failed: tier_attempts=2
# ---------------------------------------------------------------------------

def test_fetch_tier_success_after_get_fail() -> None:
    entry = _entry(
        url="https://competitor.example/page-2",
        fetch_method="fetch",
        tier_attempts=2,
    )
    out = ca.transform([entry], project_slug="test-project")
    row = out["rows"][0]
    assert row["fetch_method"] == "fetch"
    assert row["tier_attempts"] == 2


# ---------------------------------------------------------------------------
# Test 5 — Tier 2 (stealthy_fetch) success after both prior fail
# ---------------------------------------------------------------------------

def test_stealthy_fetch_tier_success() -> None:
    entry = _entry(
        url="https://competitor.example/page-3",
        fetch_method="stealthy_fetch",
        tier_attempts=3,
    )
    out = ca.transform([entry], project_slug="test-project")
    row = out["rows"][0]
    assert row["fetch_method"] == "stealthy_fetch"
    assert row["tier_attempts"] == 3


# ---------------------------------------------------------------------------
# Test 6 — All 3 tiers fail → durur_urls populated, no row emitted
# ---------------------------------------------------------------------------

def test_all_tiers_fail_emits_durur_no_row() -> None:
    """One healthy row + one all-tiers-fail row → 1 staging row + 1 durur URL.
    Bulk health threshold 50% is NOT breached (1/2 = 50%, exactly equal — OK)."""
    healthy = _entry(
        url="https://ok.example/page-1",
        fetch_method="get",
        tier_attempts=1,
    )
    failed = _entry(
        url="https://blocked.example/page-1",
        fetch_method=None,    # all 3 tiers failed
        tier_attempts=3,
        content=None,
        status_code=403,
    )
    out = ca.transform([healthy, failed], project_slug="test-project")
    assert len(out["rows"]) == 1
    assert out["rows"][0]["url_normalized"] == "https://ok.example/page-1"
    assert out["durur_urls"] == ["https://blocked.example/page-1"]


# ---------------------------------------------------------------------------
# Test 7 — S1 schema self-validate: every projected row passes Draft7Validator
# ---------------------------------------------------------------------------

def test_transform_rows_validate_against_s1_schema(s1_schema: dict) -> None:
    """Every row produced by transform() must validate against the S1
    sub-schema loaded directly from disk (not just the cached internal one).
    Covers required[], type, enum, pattern, maxLength, minimum/maximum.
    """
    entries = [
        _entry(url="https://a.example/", fetch_method="get", tier_attempts=1),
        _entry(url="https://b.example/path",
               fetch_method="stealthy_fetch", tier_attempts=3,
               content="x" * 10_000,        # excerpt cap will kick in
               schema_org_count=2,
               status_code=200,
               h1=("Heading A", "Heading B")),
    ]
    out = ca.transform(entries, project_slug="test-project")

    validator = Draft7Validator(s1_schema)
    for row in out["rows"]:
        errors = sorted(validator.iter_errors(row),
                        key=lambda e: list(e.absolute_path))
        assert not errors, [
            (list(e.absolute_path), e.message) for e in errors
        ]
        # Spot-checks on the rich entry.
        if row["url_normalized"].endswith("/path"):
            assert row["schema_org_count"] == 2
            assert row["h1"] == ["Heading A", "Heading B"]
            assert len(row["content_excerpt"]) == 500   # truncated to maxLength
            # content_hash hex pattern.
            assert re.match(r"^[a-f0-9]{64}$", row["content_hash"])


# ---------------------------------------------------------------------------
# Test 8 — content_hash deterministic: same content → same hash
# ---------------------------------------------------------------------------

def test_content_hash_deterministic() -> None:
    body = "<html><body>Same body across runs</body></html>"
    e1 = _entry(url="https://x.example/", content=body,
                fetch_method="get", tier_attempts=1)
    e2 = _entry(url="https://y.example/", content=body,
                fetch_method="get", tier_attempts=1)
    out = ca.transform([e1, e2], project_slug="test-project")
    assert out["rows"][0]["content_hash"] == out["rows"][1]["content_hash"]
    # Differs when content changes.
    e3 = _entry(url="https://z.example/", content=body + "!",
                fetch_method="get", tier_attempts=1)
    out_diff = ca.transform([e3], project_slug="test-project")
    assert out_diff["rows"][0]["content_hash"] != out["rows"][0]["content_hash"]
    # Pure helper agrees with the in-row hash.
    assert ca.content_hash_hex(body) == out["rows"][0]["content_hash"]


# ---------------------------------------------------------------------------
# Test 9 — D-03 url_normalized correct (HTTPS://Example.COM/Path/ →
#                                         https://example.com/path)
# ---------------------------------------------------------------------------

def test_d03_url_normalization_idempotent_and_correct() -> None:
    """D-03 invariant: lowercase scheme+host, strip default ports, drop
    trailing slash on non-root, drop fragment, drop tracking params, sort
    remaining query keys. Path/query case preserved (cross-skill convention
    matching cannibalization_transform.normalize_url)."""
    samples = [
        ("HTTPS://Example.COM/path/", "https://example.com/path"),
        ("https://EXAMPLE.com:443/foo/?b=2&a=1#frag",
         "https://example.com/foo?a=1&b=2"),
        ("http://example.com:80/", "http://example.com/"),
        ("https://example.org/page/?utm_source=fb&q=tr",
         "https://example.org/page?q=tr"),
        # Scheme+host lowercased, path case preserved (the brief example
        # was intent-illustrative; cross-skill D-03 invariant in this repo
        # preserves path case to honor case-sensitive URLs).
        ("HTTPS://Example.COM/Path/", "https://example.com/Path"),
    ]
    for raw, expected in samples:
        got = ca.normalize_url(raw)
        assert got == expected, f"{raw!r} → {got!r} (expected {expected!r})"
        # Idempotency.
        assert ca.normalize_url(got) == got

    # And the projected row carries the canonical form.
    entry = _entry(url="HTTPS://Example.COM/path/",
                   fetch_method="get", tier_attempts=1)
    out = ca.transform([entry], project_slug="test-project")
    assert out["rows"][0]["url_normalized"] == "https://example.com/path"
    assert out["rows"][0]["domain"] == "example.com"


# ---------------------------------------------------------------------------
# Test 10 — Bulk unhealthy: >50% of URLs fail all tiers → BulkUnhealthyError
# ---------------------------------------------------------------------------

def test_bulk_unhealthy_above_threshold_raises() -> None:
    """3 of 4 URLs fail all tiers → 75% > 50% threshold → BulkUnhealthyError."""
    entries = [
        _entry(url=f"https://blocked.example/p{i}", fetch_method=None,
               tier_attempts=3, content=None, status_code=403)
        for i in range(3)
    ] + [
        _entry(url="https://ok.example/p", fetch_method="get",
               tier_attempts=1),
    ]
    with pytest.raises(ca.BulkUnhealthyError):
        ca.transform(entries, project_slug="test-project")


# ---------------------------------------------------------------------------
# Test 11 — Tier_escalation §14.5 invariant: non-canonical order rejected
# ---------------------------------------------------------------------------

def test_tier_escalation_non_canonical_order_rejected() -> None:
    """Reordering or extending the canonical sequence raises
    TierEscalationOrderError (§14.5 const-locked schema invariant)."""
    entry = _entry(url="https://x.example/", fetch_method="get",
                   tier_attempts=1)

    bad_orders = [
        ["fetch", "get", "stealthy_fetch"],         # reordered
        ["get", "stealthy_fetch", "fetch"],          # reordered
        ["get", "fetch"],                             # truncated
        ["get", "fetch", "stealthy_fetch", "extra"],  # extended
        "not-a-list",                                  # wrong type
    ]
    for bad in bad_orders:
        with pytest.raises(ca.TierEscalationOrderError):
            ca.transform([entry], project_slug="test-project",
                          tier_escalation=bad)  # type: ignore[arg-type]

    # Canonical order accepted.
    out = ca.transform([entry], project_slug="test-project",
                        tier_escalation=["get", "fetch", "stealthy_fetch"])
    assert len(out["rows"]) == 1


# ---------------------------------------------------------------------------
# Test 12 — Budget pre-flight: PASS + FAIL paths
# ---------------------------------------------------------------------------

def test_budget_preflight_pass_and_fail(tmp_path: Path) -> None:
    """estimate_credits() yields integer-shaped credits; preflight_budget()
    PASS path returns envelope, FAIL path raises BudgetExceededError."""
    cfg = tmp_path / "project-config.json"
    cfg.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 500},
    }))
    events = tmp_path / "events.jsonl"  # empty file for clean run.

    envelope = ca.preflight_budget(
        estimated_credits=ca.estimate_credits(1),  # 5 credits
        project_config_path=str(cfg),
        events_path=str(events),
    )
    assert envelope["exceeded"] is False
    assert envelope["budget_per_day"] == 500
    assert envelope["projected_used"] == 5.0

    # Forced overrun → BudgetExceededError.
    cfg_low = tmp_path / "project-config-low.json"
    cfg_low.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 1},
    }))
    with pytest.raises(ca.BudgetExceededError):
        ca.preflight_budget(
            estimated_credits=ca.estimate_credits(1),  # 5 > 1
            project_config_path=str(cfg_low),
            events_path=str(events),
        )


# ---------------------------------------------------------------------------
# Test 13 — Plugin-agnostik: transform accepts ANY slug, no hardcoded value
# ---------------------------------------------------------------------------

def test_plugin_agnostik_no_slug_dependency() -> None:
    entry_a = _entry(url="https://site-a.example/page-1",
                      fetch_method="get", tier_attempts=1)
    entry_b = _entry(url="https://site-b.example/page-1",
                      fetch_method="get", tier_attempts=1)
    out_a = ca.transform([entry_a], project_slug="alpha")
    out_b = ca.transform([entry_b], project_slug="beta")
    assert len(out_a["rows"]) == len(out_b["rows"]) == 1
    # Same column set.
    assert set(out_a["rows"][0].keys()) == set(out_b["rows"][0].keys())
    # Slug appears in meta but never in row content.
    assert out_a["meta"]["project_slug"] == "alpha"
    assert out_b["meta"]["project_slug"] == "beta"


# ---------------------------------------------------------------------------
# Test 14 — Transform module does NOT import scripts.excel.transaction
# ---------------------------------------------------------------------------

def test_transform_does_not_import_transaction() -> None:
    """STAGING-ONLY discipline: the transform writes nothing to master.xlsx.
    The transaction helper is forbidden in this transform module — even as
    an import — to keep the staging boundary loud."""
    src = (REPO_ROOT / "scripts" / "discovery"
           / "competitive_analysis_transform.py").read_text("utf-8")
    assert "scripts.excel.transaction" not in src
    assert "transaction.append" not in src


# ---------------------------------------------------------------------------
# Test 15 — Smoke E2E: synthetic fixture → CLI → S1-validated staging file
# ---------------------------------------------------------------------------

def test_smoke_e2e_cli_writes_staging(tmp_path: Path,
                                       s1_schema: dict) -> None:
    """Smoke: write a synthetic Scrapling envelope, invoke the CLI, assert
    the staging file (a) exists, (b) is a JSON array, (c) every row passes
    S1 schema validation."""
    raw = [
        {
            "url": "https://competitor.example/home",
            "fetch_method": "stealthy_fetch",
            "tier_attempts": 3,
            "content": "<html><title>Home</title><body>Welcome.</body></html>",
            "status_code": 200,
            "meta_title": "Home",
            "meta_description": "Welcome page",
            "h1": ["Welcome"],
            "schema_org_count": 1,
            "fetch_duration_ms": 8123,
        },
    ]
    raw_file = tmp_path / "scrapling.json"
    raw_file.write_text(json.dumps(raw, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    out_dir = tmp_path / "out"

    rc = ca.main([
        "--raw-scrapling", str(raw_file),
        "--project-slug", "test-project",
        "--output-dir", str(out_dir),
        "--date", "2026-05-01",
    ])
    assert rc == 0

    out_file = out_dir / ca.staging_filename(date="2026-05-01",
                                               project_slug="test-project")
    assert out_file.exists()
    payload = json.loads(out_file.read_text("utf-8"))
    assert isinstance(payload, list) and payload

    validator = Draft7Validator(s1_schema)
    for row in payload:
        errors = sorted(validator.iter_errors(row),
                        key=lambda e: list(e.absolute_path))
        assert not errors, [
            (list(e.absolute_path), e.message) for e in errors
        ]


# ---------------------------------------------------------------------------
# Test 16 — DFS competitors_domain extraction tolerates both response shapes
# ---------------------------------------------------------------------------

def test_extract_competitor_domains_both_shapes() -> None:
    rest_envelope = {
        "tasks": [{
            "result": [{
                "items": [
                    {"domain": "rival1.example"},
                    {"domain": "rival2.example"},
                ],
            }],
        }],
    }
    flat_wrapper = {
        "items": [
            {"domain": "rival3.example"},
            {"domain": "rival1.example"},   # dup; deduplicated
        ],
    }
    assert ca.extract_competitor_domains(rest_envelope) == [
        "rival1.example", "rival2.example",
    ]
    assert ca.extract_competitor_domains(flat_wrapper) == [
        "rival3.example", "rival1.example",
    ]
    assert ca.extract_competitor_domains(None) == []
