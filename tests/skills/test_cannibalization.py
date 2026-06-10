"""
tests/skills/test_cannibalization.py — cannibalization discovery skill tests.

Mirrors tests/skills/test_quick_wins.py + tests/skills/test_gsc_pull.py
structure (frontmatter parse, URL idempotency, transform unit, schema
column match, DURUR fired, smoke E2E with synthetic fixture). MCP tools
are NOT Python-callable inside pytest; live MCP calls are performed
at-rest by Süleyman per the §16.5 raw-inbox discipline. These tests
therefore validate the transform + skill contract, not the upstream
MCP fetch itself.

Schemas referenced:
  - schemas/master-excel.schema.json (cannibalization required_columns +
    statusEnum)
  - schemas/skill-frontmatter.schema.json
  - schemas/gsc-tool-mapping.schema.json (D-03 url normalization invariant)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.discovery import cannibalization_transform as cnz


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "cannibalization" / "SKILL.md"


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
    """Parse the YAML frontmatter block of the cannibalization SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def empty_payload() -> dict:
    return {"rows": []}


@pytest.fixture
def single_url_payload() -> dict:
    """One query, one URL → no cannibalization (filtered out)."""
    return {
        "rows": [
            {
                "keys": ["only-keyword", "https://example.com/only-page"],
                "clicks": 50,
                "impressions": 500,
                "ctr": 0.10,
                "position": 4.2,
            },
        ]
    }


@pytest.fixture
def two_url_conflict_payload() -> dict:
    """One query, two URLs that QUALIFY under the new I2 contract: clicks are
    diluted (neither URL holds >70% — 30/50=60%) AND both rank in positions
    1-20 with spread ≤5 (4.0 & 7.0 → spread 3) → exactly 1 conflict row.
    (Under the OLD detector ANY two URLs ≥10 impressions were a conflict.)"""
    return {
        "rows": [
            {
                "keys": ["white sneakers", "https://example.com/sneakers/white"],
                "clicks": 30,
                "impressions": 300,
                "ctr": 0.10,
                "position": 4.0,
            },
            {
                "keys": ["white sneakers", "https://example.com/categories/white-sneakers"],
                "clicks": 20,
                "impressions": 200,
                "ctr": 0.10,
                "position": 7.0,
            },
        ]
    }


@pytest.fixture
def multi_query_payload() -> dict:
    """
    Multi-query payload exercising:
      - q1 (high-impact): 2 URLs, total 200 clicks → P1, spread > 5
        → 'consolidate to top URL'
      - q2 (medium): 2 URLs both top-10 → 'intent split investigation'
      - q3 (low): 2 URLs both above K, modest spread, total < 20 → P3,
        'topical merge candidate'
      - q4 (single URL): no conflict, filtered out
      - q5 (one URL above K, one below K): filtered down to 1 URL → no conflict
    """
    return {
        "rows": [
            # q1 — clear consolidate-to-top case (spread 4 → 17 = 13).
            {
                "keys": ["sofa set", "https://example.com/sofa-sets/modern"],
                "clicks": 150,
                "impressions": 1200,
                "ctr": 0.125,
                "position": 4.0,
            },
            {
                "keys": ["sofa set", "https://example.com/blog/sofa-set-guide"],
                "clicks": 50,
                "impressions": 600,
                "ctr": 0.083,
                "position": 17.0,
            },
            # q2 — both top-10 → intent split.
            {
                "keys": ["dental clinic", "https://example.com/clinics/dental"],
                "clicks": 25,
                "impressions": 400,
                "ctr": 0.0625,
                "position": 5.5,
            },
            {
                "keys": ["dental clinic", "https://example.com/services/dental-care"],
                "clicks": 18,
                "impressions": 350,
                "ctr": 0.0514,
                "position": 8.2,
            },
            # q3 — modest spread, low impact (total 12 → P3).
            {
                "keys": ["coffee table", "https://example.com/tables/coffee"],
                "clicks": 7,
                "impressions": 80,
                "ctr": 0.0875,
                "position": 13.0,
            },
            {
                "keys": ["coffee table", "https://example.com/blog/coffee-tables"],
                "clicks": 5,
                "impressions": 60,
                "ctr": 0.0833,
                "position": 16.0,
            },
            # q4 — single URL, no conflict.
            {
                "keys": ["unique-keyword", "https://example.com/only-here"],
                "clicks": 9,
                "impressions": 200,
                "ctr": 0.045,
                "position": 7.0,
            },
            # q5 — second URL falls below K=10 threshold → filtered out.
            {
                "keys": ["below-threshold-kw", "https://example.com/big-page"],
                "clicks": 5,
                "impressions": 100,
                "ctr": 0.05,
                "position": 9.0,
            },
            {
                "keys": ["below-threshold-kw", "https://example.com/tiny-page"],
                "clicks": 0,
                "impressions": 3,
                "ctr": 0.0,
                "position": 88.0,
            },
        ]
    }


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter parses + validates against skill-frontmatter.schema.json
# ---------------------------------------------------------------------------

def test_frontmatter_validates(skill_frontmatter: dict,
                                skill_frontmatter_schema: dict) -> None:
    """
    SKILL.md frontmatter must:
      (a) parse as YAML,
      (b) carry name=cannibalization, status=active (asserted as a member of
          the valid lifecycle set {active, deprecated, wip}), version="1.0",
          category=discovery,
      (c) declare project_slug as a required string input,
      (d) list mcp__gsc__search_analytics in required tools,
      (e) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "cannibalization"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "discovery"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__gsc__search_analytics" in required_tools

    # Outputs include the cannibalization sheet anchor + raw inbox + report.
    outputs = fm["outputs"]
    assert any("master.xlsx#cannibalization" in o for o in outputs)
    assert any("inbox/gsc/" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("outputs/reports/" in o and "cannibalization" in o for o in outputs)

    # Budget: 0 credits, no paid MCP (GSC-only).
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"].get("estimated_credits", 0) == 0

    # Full Draft 7 validation against the canonical schema.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — URL normalization is idempotent + correct (D-03 invariant)
# ---------------------------------------------------------------------------

def test_url_normalization_idempotent() -> None:
    samples = [
        ("HTTPS://Example.COM:443/foo/?b=2&a=1#frag",
         "https://example.com/foo?a=1&b=2"),
        ("http://EXAMPLE.com:80/", "http://example.com/"),
        ("https://example.org/page/?utm_source=fb&utm_medium=cpc&q=tr",
         "https://example.org/page?q=tr"),
        ("https://example.org/page/#section",
         "https://example.org/page"),
        ("https://example.org/", "https://example.org/"),
    ]
    for raw, expected in samples:
        got = cnz.normalize_url(raw)
        assert got == expected, (
            f"normalize({raw!r}) → {got!r} (expected {expected!r})"
        )
        assert cnz.normalize_url(got) == got, (
            f"not idempotent: {raw!r} → {got!r}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Empty input → empty output
# ---------------------------------------------------------------------------

def test_empty_input_no_rows(empty_payload: dict) -> None:
    """Empty payload returns an empty cannibalization list, not an error."""
    out = cnz.transform(empty_payload)
    assert out["cannibalization"] == []
    assert out["meta"]["conflict_count"] == 0
    assert out["meta"]["queries_seen"] == 0
    assert out["meta"]["input_row_count"] == 0


# ---------------------------------------------------------------------------
# Test 4 — Single query / single URL → no cannibalization (filtered out)
# ---------------------------------------------------------------------------

def test_single_url_no_conflict(single_url_payload: dict) -> None:
    """A query with only one URL must NOT produce a conflict row."""
    out = cnz.transform(single_url_payload)
    assert out["cannibalization"] == []
    assert out["meta"]["conflict_count"] == 0
    # The query was seen but did not qualify as a conflict.
    assert out["meta"]["queries_seen"] == 1


# ---------------------------------------------------------------------------
# Test 5 — Two URLs above K → exactly 1 conflict row, schema-shape correct
# ---------------------------------------------------------------------------

def test_two_url_conflict_emits_one_row(two_url_conflict_payload: dict,
                                          master_excel_schema: dict) -> None:
    """
    A query with 2 URLs both above K must produce exactly 1 cannibalization
    row. The row's column set must equal the master-excel schema column
    set for the cannibalization sheet exactly.
    """
    out = cnz.transform(two_url_conflict_payload)
    rows = out["cannibalization"]
    assert len(rows) == 1
    row = rows[0]

    # Schema column match.
    sheet_def = master_excel_schema["sheets"]["cannibalization"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    assert schema_col_names == cnz.CANNIBALIZATION_COLUMNS
    assert tuple(row.keys()) == schema_col_names

    # Specific assertions.
    assert "white sneakers" in row["conflict_pair"]
    assert "https://example.com/sneakers/white" in row["conflict_pair"]
    assert "https://example.com/categories/white-sneakers" in row["conflict_pair"]
    # Total impact = 30 + 20 = 50 clicks → "50 clicks", priority=P2 (>=20).
    assert row["total_impact"] == "50 clicks"
    assert row["priority"] == "P2"
    # New contract: default recommendation is differentiate-intent, NOT an
    # auto 301-consolidate (which is operator-reviewed only).
    assert row["resolution"] == "differentiate intent / adjust internal-link hierarchy"
    # Default status must be a valid statusEnum value.
    assert row["status"] == "TODO"
    # Note carries primary URL hint (the higher-clicks URL).
    assert "https://example.com/sneakers/white" in row["note"]
    # overlapping_queries_est is an int.
    assert isinstance(row["overlapping_queries_est"], int)
    assert row["overlapping_queries_est"] >= 1


# ---------------------------------------------------------------------------
# Test 6 — Multi-query payload sorted by total_impact desc
# ---------------------------------------------------------------------------

def test_multi_query_sorted_by_impact(multi_query_payload: dict) -> None:
    """
    Multi-query input emits conflict rows ordered by total_impact desc.
    Under the NEW I2 contract:
      - q1 'sofa set': URL1 holds 150/200 = 75% of clicks (> 70%) → NO
        click-share dilution → NOT a conflict (filtered).
      - q2 'dental clinic': 25/43 = 58% diluted + positions 5.5/8.2 (both
        1-20, spread 2.7 ≤ 5) → conflict.
      - q3 'coffee table': 7/12 = 58% diluted + positions 13/16 (both 1-20,
        spread 3 ≤ 5) → conflict.
      - q4 singleton / q5 sub-K → filtered.
    So exactly 2 conflicts, NOT the old 3.
    """
    out = cnz.transform(multi_query_payload)
    rows = out["cannibalization"]

    assert len(rows) == 2

    # Sorted by total_impact desc: dental clinic (43) before coffee table (12).
    assert rows[0]["conflict_pair"].startswith("dental clinic ::")
    assert rows[0]["total_impact"] == "43 clicks"
    assert rows[0]["priority"] == "P2"

    assert rows[1]["conflict_pair"].startswith("coffee table ::")
    assert rows[1]["total_impact"] == "12 clicks"
    assert rows[1]["priority"] == "P3"

    # q1 (click-share dominated), q4 (singleton), q5 (one URL above K) absent.
    pairs = " ".join(r["conflict_pair"] for r in rows)
    assert "sofa set" not in pairs
    assert "unique-keyword" not in pairs
    assert "below-threshold-kw" not in pairs
    # meta records WHY sofa set was dropped (click-share dilution failed).
    assert out["meta"]["share_excluded"] >= 1


# ---------------------------------------------------------------------------
# Test 7 — Default resolution is differentiate-intent; 301-consolidate is
# never auto-recommended (operator-reviewed only).
# ---------------------------------------------------------------------------

def test_default_resolution_is_differentiate_intent(multi_query_payload: dict) -> None:
    """The new contract drops the old spread-based 'consolidate to top URL'
    auto-recommendation. Every auto-emitted conflict carries the differentiate-
    intent recommendation; consolidation (301) is only ever surfaced as an
    operator-reviewed caveat in the note, never as the resolution value."""
    out = cnz.transform(multi_query_payload)
    for row in out["cannibalization"]:
        assert row["resolution"] == "differentiate intent / adjust internal-link hierarchy"
        # consolidate is never the auto resolution.
        assert "consolidate to top url" not in row["resolution"].lower()
        # the operator-review caveat lives in the note.
        assert "operator" in row["note"].lower()


# ---------------------------------------------------------------------------
# Test 8 — DURUR / RowSchemaError fired on bad input
# ---------------------------------------------------------------------------

def test_durur_invalid_input_explicit_error() -> None:
    """
    Per the worker brief / quick-wins convention authority: invalid input
    must raise an explicit CannibalizationError, NOT degrade silently.
    """
    # (a) raw must be a dict.
    with pytest.raises(cnz.CannibalizationError):
        cnz.transform("not-a-dict")  # type: ignore[arg-type]

    # (b) rows must be a list.
    with pytest.raises(cnz.CannibalizationError):
        cnz.transform({"rows": "not-a-list"})

    # (c) empty string URL.
    with pytest.raises(cnz.CannibalizationError):
        cnz.normalize_url("")

    # (d) URL missing scheme.
    with pytest.raises(cnz.CannibalizationError):
        cnz.normalize_url("example.com/no-scheme")

    # (e) URL not a string.
    with pytest.raises(cnz.CannibalizationError):
        cnz.normalize_url(None)  # type: ignore[arg-type]

    # (f) default_status must be in statusEnum.
    with pytest.raises(cnz.CannibalizationError):
        cnz.transform({"rows": []}, default_status="NOT-AN-ENUM")

    # (g) min_impressions cannot be negative.
    with pytest.raises(cnz.CannibalizationError):
        cnz.transform({"rows": []}, min_impressions=-1)


# ---------------------------------------------------------------------------
# Test 9 — Plugin-agnostik: transform accepts any slug, no hardcoded value
# ---------------------------------------------------------------------------

def test_plugin_agnostik_no_slug_dependency() -> None:
    """
    The transform is purely data-driven: it does not read project slug
    from anywhere. Two synthetic payloads with different fake slugs
    embedded in URLs must produce structurally identical row counts and
    schemas — proving the function does not branch on slug content.
    """
    payload_a = {
        "rows": [
            {"keys": ["kw", "https://site-a.example/page-1"],
             "clicks": 30, "impressions": 200, "position": 4.0},
            {"keys": ["kw", "https://site-a.example/page-2"],
             "clicks": 20, "impressions": 150, "position": 8.0},
        ]
    }
    payload_b = {
        "rows": [
            {"keys": ["kw", "https://site-b.example/page-1"],
             "clicks": 30, "impressions": 200, "position": 4.0},
            {"keys": ["kw", "https://site-b.example/page-2"],
             "clicks": 20, "impressions": 150, "position": 8.0},
        ]
    }
    out_a = cnz.transform(payload_a)
    out_b = cnz.transform(payload_b)
    assert len(out_a["cannibalization"]) == len(out_b["cannibalization"]) == 1
    # Same column set, same metric magnitudes; only URL strings differ.
    assert tuple(out_a["cannibalization"][0].keys()) == cnz.CANNIBALIZATION_COLUMNS
    assert tuple(out_b["cannibalization"][0].keys()) == cnz.CANNIBALIZATION_COLUMNS
    assert out_a["cannibalization"][0]["total_impact"] == \
           out_b["cannibalization"][0]["total_impact"] == "50 clicks"


# ---------------------------------------------------------------------------
# Test 10 — Smoke E2E: synthetic fixture → CLI → schema-shaped JSON output
# ---------------------------------------------------------------------------

def test_smoke_e2e_cli_output(tmp_path: Path,
                                multi_query_payload: dict) -> None:
    """
    Smoke E2E without any live MCP call: write fixture to disk, invoke
    cannibalization_transform.main CLI, assert the output JSON parses and
    matches the schema-locked column structure. Idempotency is also
    asserted: a second run with the same input produces byte-identical
    output.
    """
    raw_path = tmp_path / "search_analytics.json"
    raw_path.write_text(
        json.dumps(multi_query_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    rc = cnz.main([
        "--raw", str(raw_path),
        "--output-dir", str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    out_file = out_dir / "cannibalization.json"
    assert out_file.exists(), "CLI did not write cannibalization.json"

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and payload, "empty output array"
    expected_cols = set(cnz.CANNIBALIZATION_COLUMNS)
    for r in payload:
        assert set(r.keys()) == expected_cols

    # Idempotency: re-run with same input → byte-identical output file.
    first_bytes = out_file.read_bytes()
    rc2 = cnz.main([
        "--raw", str(raw_path),
        "--output-dir", str(out_dir),
    ])
    assert rc2 == 0
    second_bytes = out_file.read_bytes()
    assert first_bytes == second_bytes, (
        "transform is not byte-idempotent under re-run"
    )


# ---------------------------------------------------------------------------
# Test 11 (I2) — click-share dominance: one URL holding >70% of clicks is NOT
# cannibalization (the explicit old→new verdict difference).
# ---------------------------------------------------------------------------

def test_click_share_dominant_url_not_conflict() -> None:
    """OLD detector: any 2 URLs ≥10 impressions on a query = conflict.
    NEW I2 (b): no conflict unless click-share is DILUTED (no single URL >70%
    of the query's clicks). 80/95 = 84% → dominant → NOT a conflict."""
    payload = {"rows": [
        {"keys": ["running shoes", "https://example.com/shoes/running"],
         "clicks": 80, "impressions": 1000, "position": 4.0},
        {"keys": ["running shoes", "https://example.com/blog/running-shoes"],
         "clicks": 15, "impressions": 400, "position": 6.0},
    ]}
    out = cnz.transform(payload)
    assert out["cannibalization"] == []           # old=1 conflict, new=0
    assert out["meta"]["conflict_count"] == 0
    assert out["meta"]["share_excluded"] >= 1


def test_position_spread_gt5_single_window_not_conflict() -> None:
    """NEW I2 (c): diluted clicks but the two URLs are NOT a tight position
    cluster (spread > 5) and there is no second window for flip-flop → no
    competition signal → NOT a conflict."""
    payload = {"rows": [
        {"keys": ["office chair", "https://example.com/chairs/office"],
         "clicks": 30, "impressions": 500, "position": 3.0},
        {"keys": ["office chair", "https://example.com/blog/office-chairs"],
         "clicks": 25, "impressions": 400, "position": 15.0},
    ]}
    out = cnz.transform(payload)
    assert out["cannibalization"] == []
    assert out["meta"]["signal_excluded"] >= 1


def test_brand_query_excluded() -> None:
    """NEW I2 (a): brand-dominated queries are excluded (brand tokens derived
    from project.config brand/domain, passed in — engine stays agnostic). A
    non-brand query in the same payload still emits."""
    payload = {"rows": [
        # brand query — would otherwise qualify (diluted + tight cluster).
        {"keys": ["acme sneakers", "https://example.com/sneakers/acme-a"],
         "clicks": 30, "impressions": 400, "position": 4.0},
        {"keys": ["acme sneakers", "https://example.com/sneakers/acme-b"],
         "clicks": 25, "impressions": 350, "position": 6.0},
        # non-brand query — qualifies and must still emit.
        {"keys": ["leather boots", "https://example.com/boots/leather-a"],
         "clicks": 30, "impressions": 400, "position": 4.0},
        {"keys": ["leather boots", "https://example.com/boots/leather-b"],
         "clicks": 25, "impressions": 350, "position": 6.0},
    ]}
    out = cnz.transform(payload, brand_tokens=["acme"])
    pairs = " ".join(r["conflict_pair"] for r in out["cannibalization"])
    assert "acme sneakers" not in pairs
    assert "leather boots" in pairs
    assert out["meta"]["brand_excluded"] >= 1


def test_flipflop_across_windows_is_conflict() -> None:
    """NEW I2 (c) flip-flop branch: even with a WIDE position spread (no tight
    cluster), a top-URL flip-flop between the two most recent windows is a
    competition signal → conflict (only when the previous window is given)."""
    recent = {"rows": [
        {"keys": ["garden hose", "https://example.com/hose/a"],
         "clicks": 30, "impressions": 500, "position": 4.0},
        {"keys": ["garden hose", "https://example.com/hose/b"],
         "clicks": 25, "impressions": 450, "position": 18.0},   # spread 14 > 5
    ]}
    previous = {"rows": [
        {"keys": ["garden hose", "https://example.com/hose/a"],
         "clicks": 10, "impressions": 400, "position": 18.0},
        {"keys": ["garden hose", "https://example.com/hose/b"],
         "clicks": 40, "impressions": 600, "position": 4.0},    # was the top URL
    ]}
    # Single window: spread > 5, no flip-flop data → NOT a conflict.
    assert cnz.transform(recent)["cannibalization"] == []
    # Two windows: top URL flipped (b→a) → conflict.
    out = cnz.transform(recent, previous=previous)
    assert len(out["cannibalization"]) == 1
    assert "garden hose" in out["cannibalization"][0]["conflict_pair"]
    assert "flip" in out["cannibalization"][0]["note"].lower()


def test_zero_click_query_not_conflict() -> None:
    """Edge: a query whose URLs have impressions but zero clicks has no
    traffic to dilute → not an active cannibalization conflict."""
    payload = {"rows": [
        {"keys": ["niche term", "https://example.com/a"],
         "clicks": 0, "impressions": 50, "position": 4.0},
        {"keys": ["niche term", "https://example.com/b"],
         "clicks": 0, "impressions": 40, "position": 6.0},
    ]}
    out = cnz.transform(payload)
    assert out["cannibalization"] == []
