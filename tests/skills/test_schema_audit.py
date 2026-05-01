"""
tests/skills/test_schema_audit.py — schema-audit discovery skill tests.

Mirrors tests/skills/test_cannibalization.py + test_on_page_audit.py
structure (frontmatter parse, transform unit, schema column match, DURUR
fired, budget pre-flight, smoke E2E with synthetic fixture). MCP tools
are NOT Python-callable inside pytest; live MCP / SF reads are performed
at-rest by the manager per the §16.5 raw-inbox discipline. These tests
therefore validate the transform + skill contract, not the upstream
MCP fetch itself.

Schemas referenced:
  - schemas/master-excel.schema.json (schema sheet 5 required_columns +
    statusEnum)
  - schemas/skill-frontmatter.schema.json
  - schemas/events.schema.json (target_excel_sheet=schema)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import schema_audit_transform as sat


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "schema-audit" / "SKILL.md"


# ---------------------------------------------------------------------------
# Fixtures — schemas + frontmatter
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
    """Parse the YAML frontmatter block of the schema-audit SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


# ---------------------------------------------------------------------------
# Fixtures — synthetic SF payloads (small inline JSON-LD strings)
# ---------------------------------------------------------------------------

def _sf_row(url: str, jsonld: str | None = None,
            types_field: str | None = None) -> dict:
    """Build a minimal SF structured-data row."""
    row: dict = {"address": url}
    if jsonld is not None:
        row["json_ld"] = jsonld
    if types_field is not None:
        row["schema_types"] = types_field
    return row


@pytest.fixture
def empty_sf_payload() -> dict:
    return {"rows": []}


@pytest.fixture
def article_done_payload() -> dict:
    """Single Article with all required props → status=DONE."""
    blob = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Example Headline",
        "author": {"@type": "Person", "name": "Jane"},
        "datePublished": "2026-04-01",
        "image": "https://example.com/img.jpg",
        "publisher": {"@type": "Organization", "name": "Example"},
    })
    return {"rows": [_sf_row("https://example.com/post-1", blob)]}


@pytest.fixture
def product_missing_aggregate_rating_payload() -> dict:
    """Product with required props present but no aggregateRating → EXISTS,
    remaining_work names aggregateRating."""
    blob = json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Sample Product",
        "image": "https://example.com/p.jpg",
        "offers": {"@type": "Offer", "price": "9.99"},
        "brand": "Acme",
    })
    return {"rows": [_sf_row("https://example.com/products/sample", blob)]}


@pytest.fixture
def product_missing_required_payload() -> dict:
    """Product missing `offers` (required) → status=TODO."""
    blob = json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Broken Product",
        "image": "https://example.com/x.jpg",
    })
    return {"rows": [_sf_row("https://example.com/products/broken", blob)]}


@pytest.fixture
def conflicting_types_payload() -> dict:
    """Mixed top-level @type list → status=BLOCKED."""
    blob = json.dumps({
        "@context": "https://schema.org",
        "@type": ["Product", "Article"],
        "name": "Confused",
    })
    return {"rows": [_sf_row("https://example.com/confused", blob)]}


@pytest.fixture
def aggregation_payload() -> dict:
    """5 URLs all with the same Product gap (missing offers) → 1 aggregated row."""
    rows = []
    for i in range(1, 6):
        blob = json.dumps({
            "@context": "https://schema.org",
            "@type": "Product",
            "name": f"Item {i}",
            "image": f"https://example.com/i{i}.jpg",
        })
        rows.append(_sf_row(f"https://example.com/cat/item-{i}", blob))
    return {"rows": rows}


@pytest.fixture
def malformed_jsonld_payload() -> dict:
    """One row with broken JSON; non-strict mode drops, strict mode raises."""
    return {
        "rows": [
            _sf_row("https://example.com/broken",
                    "{ this is not valid JSON-LD"),
        ]
    }


@pytest.fixture
def mixed_status_payload() -> dict:
    """Mixed payload exercising DONE / TODO / EXISTS / BLOCKED in one go."""
    article_ok = json.dumps({
        "@type": "Article",
        "headline": "h",
        "author": {"name": "a"},
        "datePublished": "2026-01-01",
        "image": "x",
        "publisher": {"name": "p"},
    })
    product_todo = json.dumps({
        "@type": "Product",
        "name": "p1",
        "image": "x",
        # Missing offers (required) → TODO.
    })
    product_exists = json.dumps({
        "@type": "Product",
        "name": "p2",
        "image": "x",
        "offers": {"price": "1.00"},
        # Missing aggregateRating (recommended) → EXISTS.
    })
    blocked = json.dumps({
        "@type": ["Article", "Product"],
        "name": "Conflict",
    })
    return {
        "rows": [
            _sf_row("https://example.com/article-1", article_ok),
            _sf_row("https://example.com/p-todo", product_todo),
            _sf_row("https://example.com/p-exists", product_exists),
            _sf_row("https://example.com/conflict-1", blocked),
        ]
    }


@pytest.fixture
def dfs_payload_confirms_article() -> dict:
    """DFS payload that confirms an Article schema at the same URL."""
    return {
        "tasks": [{
            "result": [{
                "items": [{
                    "url": "https://example.com/post-1",
                    "schema_org": [
                        {"type": "Article", "name": "Example Headline"},
                    ],
                }]
            }]
        }]
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + validates against skill-frontmatter.schema.json
# ---------------------------------------------------------------------------

def test_frontmatter_validates(skill_frontmatter: dict,
                                skill_frontmatter_schema: dict) -> None:
    """SKILL.md frontmatter must parse, declare discovery category, declare
    project_slug as required string, default budget=free, validate Draft 7."""
    fm = skill_frontmatter
    assert fm["name"] == "schema-audit"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"
    assert fm["category"] == "discovery"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    # Outputs include the schema sheet anchor + raw inbox + report + events.
    outputs = fm["outputs"]
    assert any("master.xlsx#schema" in o for o in outputs)
    assert any("inbox/sf/" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("outputs/reports/" in o and "schema-audit" in o for o in outputs)

    # Budget: 0 credits, no paid MCP — DFS optional path documented but
    # default declaration is free (Q-W-A4-01 enforced).
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"].get("estimated_credits", 0) == 0
    # Forbidden keys must NOT appear (Q-W-A4-01 lesson).
    assert "estimated_credits_per_call" not in fm["budget"]
    assert "estimated_credits_per_url" not in fm["budget"]

    # Full Draft 7 validation against the canonical schema.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Empty SF data → empty rows
# ---------------------------------------------------------------------------

def test_empty_sf_no_rows(empty_sf_payload: dict) -> None:
    out = sat.transform(empty_sf_payload)
    assert out["schema"] == []
    assert out["meta"]["row_count"] == 0
    assert out["meta"]["sf_row_count"] == 0
    assert out["meta"]["instance_count"] == 0
    assert out["meta"]["dfs_used"] is False


# ---------------------------------------------------------------------------
# Test 3 — Article with all required props → status=DONE
# ---------------------------------------------------------------------------

def test_article_all_required_done(article_done_payload: dict,
                                    master_excel_schema: dict) -> None:
    out = sat.transform(article_done_payload)
    rows = out["schema"]
    assert len(rows) == 1
    row = rows[0]

    # Schema column match.
    sheet_def = master_excel_schema["sheets"]["schema"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    assert schema_col_names == sat.SCHEMA_AUDIT_COLUMNS
    assert tuple(row.keys()) == schema_col_names

    assert row["schema_type"] == "Article"
    assert row["status"] == "DONE"
    assert row["location"] == "https://example.com/post-1"
    assert row["scope"] == "page-level"
    assert "complete" in row["remaining_work"].lower()


# ---------------------------------------------------------------------------
# Test 4 — Product missing required prop → status=TODO
# ---------------------------------------------------------------------------

def test_product_missing_required_todo(
    product_missing_required_payload: dict,
) -> None:
    out = sat.transform(product_missing_required_payload)
    rows = out["schema"]
    assert len(rows) == 1
    row = rows[0]
    assert row["schema_type"] == "Product"
    assert row["status"] == "TODO"
    # remaining_work names the missing required prop.
    assert "offers" in row["remaining_work"]


# ---------------------------------------------------------------------------
# Test 5 — Product with required but missing recommended → EXISTS,
#          remaining_work mentions aggregateRating
# ---------------------------------------------------------------------------

def test_product_missing_aggregate_rating_exists(
    product_missing_aggregate_rating_payload: dict,
) -> None:
    out = sat.transform(product_missing_aggregate_rating_payload)
    rows = out["schema"]
    assert len(rows) == 1
    row = rows[0]
    assert row["schema_type"] == "Product"
    assert row["status"] == "EXISTS"
    assert "aggregateRating" in row["remaining_work"]


# ---------------------------------------------------------------------------
# Test 6 — Conflicting top-level types → status=BLOCKED
# ---------------------------------------------------------------------------

def test_conflicting_types_blocked(conflicting_types_payload: dict) -> None:
    out = sat.transform(conflicting_types_payload)
    rows = out["schema"]
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "BLOCKED"
    # remaining_work mentions the conflict.
    assert "conflicting" in row["remaining_work"].lower() \
        or "@type" in row["remaining_work"]


# ---------------------------------------------------------------------------
# Test 7 — Aggregation: 5 URLs with same Product gap → 1 site-wide row
# ---------------------------------------------------------------------------

def test_aggregation_collapses_site_wide(aggregation_payload: dict) -> None:
    out = sat.transform(aggregation_payload)
    rows = out["schema"]
    # All 5 URLs share the same (schema_type, status, remaining_work)
    # signature (Product / TODO / "missing offers"). Collapses to 1 row.
    assert len(rows) == 1
    row = rows[0]
    assert row["schema_type"] == "Product"
    assert row["status"] == "TODO"
    assert row["scope"] == "site-wide"
    assert "5 URLs" in row["location"]
    assert "offers" in row["remaining_work"]


# ---------------------------------------------------------------------------
# Test 8 — JSON-LD parse error: strict raises, default drops
# ---------------------------------------------------------------------------

def test_jsonld_parse_error_strict_vs_default(
    malformed_jsonld_payload: dict,
) -> None:
    # Default mode: malformed blob is silently dropped.
    out = sat.transform(malformed_jsonld_payload, strict_parse=False)
    assert out["schema"] == []
    assert out["meta"]["parse_errors"] == 1

    # Strict mode: explicit error.
    with pytest.raises(sat.JsonLdParseError):
        sat.transform(malformed_jsonld_payload, strict_parse=True)


# ---------------------------------------------------------------------------
# Test 9 — statusEnum coverage: DONE/TODO/EXISTS/BLOCKED all observed
# ---------------------------------------------------------------------------

def test_status_enum_coverage(mixed_status_payload: dict) -> None:
    out = sat.transform(mixed_status_payload)
    rows = out["schema"]
    statuses = {r["status"] for r in rows}
    assert {"DONE", "TODO", "EXISTS", "BLOCKED"}.issubset(statuses)
    # Every emitted status must be in the canonical 7-value enum.
    allowed = {"TODO", "ONGOING", "EXISTS", "DONE",
               "BLOCKED", "DEFERRED", "CANCELED"}
    assert statuses.issubset(allowed)


# ---------------------------------------------------------------------------
# Test 10 — DFS optional path: cross-validate confirms SF detection,
#           remaining_work decorated
# ---------------------------------------------------------------------------

def test_dfs_cross_validate_confirms(article_done_payload: dict,
                                      dfs_payload_confirms_article: dict) -> None:
    out = sat.transform(article_done_payload, dfs_payload_confirms_article)
    rows = out["schema"]
    assert len(rows) == 1
    assert out["meta"]["dfs_used"] is True
    assert out["meta"]["dfs_url_count"] >= 1
    assert "DFS confirmed live" in rows[0]["remaining_work"]


# ---------------------------------------------------------------------------
# Test 11 — DURUR / SchemaAuditError fired on bad input
# ---------------------------------------------------------------------------

def test_durur_invalid_input_explicit_error() -> None:
    with pytest.raises(sat.SchemaAuditError):
        sat.transform("not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(sat.SchemaAuditError):
        sat.transform({}, "not-a-dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 12 — Plugin-agnostik: transform reads no slug from anywhere
# ---------------------------------------------------------------------------

def test_plugin_agnostik_no_slug_dependency() -> None:
    """Two synthetic payloads with different fake slugs in URLs must produce
    structurally identical row counts and schemas."""
    blob = json.dumps({
        "@type": "Organization",
        "name": "Example",
        "url": "https://site-a.example",
    })
    payload_a = {"rows": [_sf_row("https://site-a.example/about", blob)]}
    blob_b = json.dumps({
        "@type": "Organization",
        "name": "Example",
        "url": "https://site-b.example",
    })
    payload_b = {"rows": [_sf_row("https://site-b.example/about", blob_b)]}

    out_a = sat.transform(payload_a)
    out_b = sat.transform(payload_b)
    assert len(out_a["schema"]) == len(out_b["schema"]) == 1
    assert tuple(out_a["schema"][0].keys()) == sat.SCHEMA_AUDIT_COLUMNS
    assert tuple(out_b["schema"][0].keys()) == sat.SCHEMA_AUDIT_COLUMNS


# ---------------------------------------------------------------------------
# Test 13 — Budget pre-flight: PASS + FAIL paths
# ---------------------------------------------------------------------------

def test_estimate_credits_per_url() -> None:
    assert sat.estimate_credits(0) == 0.0
    assert sat.estimate_credits(1) == 3.0
    assert sat.estimate_credits(10) == 30.0


def test_budget_preflight_pass_and_fail(tmp_path: Path) -> None:
    cfg = tmp_path / "project-config.json"
    cfg.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 500},
    }))
    events = tmp_path / "events.jsonl"

    envelope = sat.preflight_budget(
        estimated_credits=sat.estimate_credits(10),  # 30
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
    with pytest.raises(sat.BudgetExceededError):
        sat.preflight_budget(
            estimated_credits=sat.estimate_credits(10),  # 30 > 5
            project_config_path=str(cfg_low),
            events_path=str(events),
        )


# ---------------------------------------------------------------------------
# Test 14 — Schema column match: transform output ↔ master-excel schema
# ---------------------------------------------------------------------------

def test_schema_column_match(master_excel_schema: dict) -> None:
    sheet_def = master_excel_schema["sheets"]["schema"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    assert schema_col_names == sat.SCHEMA_AUDIT_COLUMNS
    assert len(schema_col_names) == 5  # NOT 6


# ---------------------------------------------------------------------------
# Test 15 — Smoke E2E: synthetic SF fixture → CLI → schema-shaped JSON
# ---------------------------------------------------------------------------

def test_smoke_e2e_cli_output(tmp_path: Path,
                                mixed_status_payload: dict) -> None:
    raw_path = tmp_path / "sf-structured.json"
    raw_path.write_text(
        json.dumps(mixed_status_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    rc = sat.main([
        "--raw-sf", str(raw_path),
        "--output-dir", str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    out_file = out_dir / "schema_audit.json"
    assert out_file.exists(), "CLI did not write schema_audit.json"

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and payload, "empty output array"
    expected_cols = set(sat.SCHEMA_AUDIT_COLUMNS)
    for r in payload:
        assert set(r.keys()) == expected_cols

    # Idempotency: re-run with same input → byte-identical output file.
    first_bytes = out_file.read_bytes()
    rc2 = sat.main([
        "--raw-sf", str(raw_path),
        "--output-dir", str(out_dir),
    ])
    assert rc2 == 0
    second_bytes = out_file.read_bytes()
    assert first_bytes == second_bytes, (
        "transform is not byte-idempotent under re-run"
    )
