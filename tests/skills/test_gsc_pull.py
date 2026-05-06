"""
tests/skills/test_gsc_pull.py — gsc-pull ingestion skill end-to-end tests.

Mirrors tests/skills/test_quick_wins.py structure (frontmatter parse,
URL idempotency, transform unit, schema column match, DURUR fired,
smoke E2E with mocked fixture). MCP tools are NOT Python-callable
inside pytest; live MCP calls are performed at-rest by Süleyman per
the §16.5 raw-inbox discipline. These tests therefore validate the
transform + skill contract, not the upstream MCP fetch itself.

Schemas referenced:
  - schemas/master-excel.schema.json (gsc_performance required_columns)
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

from scripts.ingestion import gsc_pull


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "ingestion" / "gsc-pull" / "SKILL.md"


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
    """Parse the YAML frontmatter block of skills/ingestion/gsc-pull/SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    # Frontmatter delimited by leading and trailing '---' lines.
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_recent() -> dict:
    """Recent-window mcp__gsc__search_analytics-shape payload."""
    return {
        "rows": [
            {
                "keys": ["https://example.com/page-a/?utm_source=fb&b=2&a=1#frag"],
                "clicks": 100,
                "impressions": 1000,
                "ctr": 0.10,
                "position": 5.2,
            },
            {
                "keys": ["HTTPS://Example.COM:443/page-b/"],
                "clicks": 20,
                "impressions": 500,
                "ctr": 0.04,
                "position": 12.5,
            },
            {
                "keys": ["https://example.com/page-c"],
                "clicks": 0,
                "impressions": 30,
                "ctr": 0.0,
                "position": 80.0,
            },
        ]
    }


@pytest.fixture
def synthetic_previous() -> dict:
    """Previous-window enhanced_search_analytics-shape payload.

    Uses the same canonical query-bearing form for page-a so it
    normalizes to the same URL as the recent fixture (real-world MCP
    payloads carry full URLs including query params).
    """
    return {
        "rows": [
            {
                "keys": ["https://example.com/page-a?b=2&a=1"],
                "clicks": 50,
                "impressions": 800,
                "ctr": 0.0625,
                "position": 6.8,
            },
            {
                "keys": ["https://example.com/page-b"],
                "clicks": 25,
                "impressions": 600,
                "ctr": 0.0417,
                "position": 11.0,
            },
            # page-c absent → previous-window zeros for it.
            # page-d present in previous only → must still appear in output.
            {
                "keys": ["https://example.com/page-d"],
                "clicks": 5,
                "impressions": 50,
                "ctr": 0.10,
                "position": 22.0,
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
      (b) carry name=gsc-pull, status=wip, version="1.0", category=ingestion,
      (c) declare project_slug as a required string input,
      (d) list the two required MCP tools per the worker brief,
      (e) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "gsc-pull"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "ingestion"

    # Required project_slug input.
    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    # MCP tools required per brief.
    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__gsc__enhanced_search_analytics" in required_tools
    assert "mcp__gsc__search_analytics" in required_tools

    # Optional index_inspect.
    optional_tools = fm["mcp_tools"].get("optional", [])
    assert "mcp__gsc__index_inspect" in optional_tools

    # Outputs include the gsc_performance sheet anchor.
    outputs = fm["outputs"]
    assert any("master.xlsx#gsc_performance" in o for o in outputs)
    assert any("inbox/gsc/" in o and "search_analytics" in o for o in outputs)
    assert any("inbox/gsc/" in o and "enhanced_search_analytics" in o for o in outputs)
    assert "events.jsonl" in outputs
    assert any("outputs/reports/" in o and "gsc-pull" in o for o in outputs)

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
        # (input, expected)
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
        got = gsc_pull.normalize_url(raw)
        assert got == expected, (
            f"normalize({raw!r}) → {got!r} (expected {expected!r})"
        )
        # Idempotency: D-03 invariant.
        assert gsc_pull.normalize_url(got) == got, (
            f"not idempotent: {raw!r} → {got!r}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Transform unit: row count + column structure
# ---------------------------------------------------------------------------

def test_transform_row_count_and_columns(synthetic_recent: dict,
                                          synthetic_previous: dict) -> None:
    out = gsc_pull.transform(synthetic_recent, enriched=synthetic_previous)
    rows = out["gsc_performance"]

    # Union of recent (3 unique URLs after normalization) and previous (3) =
    # page-a, page-b, page-c (recent only), page-d (previous only) = 4 rows.
    urls = sorted(r["url"] for r in rows)
    assert urls == [
        "https://example.com/page-a?a=1&b=2",
        "https://example.com/page-b",
        "https://example.com/page-c",
        "https://example.com/page-d",
    ], f"unexpected URL set: {urls}"

    # Every row has exactly the 12 schema columns.
    expected_cols = set(gsc_pull.GSC_PERFORMANCE_COLUMNS)
    for r in rows:
        assert set(r.keys()) == expected_cols, (
            f"row column mismatch: {set(r.keys())} != {expected_cols}"
        )

    # Specific delta sanity: page-a went from 50 → 100 clicks (+100%).
    page_a = next(r for r in rows if r["url"].startswith("https://example.com/page-a"))
    assert page_a["clicks_recent"] == 100
    assert page_a["clicks_previous"] == 50
    assert page_a["clicks_delta"] == 50
    assert page_a["clicks_delta_pct"] == 100.0
    assert page_a["note"] == "rising"

    # page-c is recent-only (previous=0) but recent has clicks=0 and
    # impressions=30 → no-clicks (zero recent clicks).
    page_c = next(r for r in rows if r["url"] == "https://example.com/page-c")
    assert page_c["clicks_recent"] == 0
    assert page_c["clicks_previous"] == 0
    assert page_c["note"] == "no-clicks"

    # page-d is previous-only (recent=0) → decay (-100%).
    page_d = next(r for r in rows if r["url"] == "https://example.com/page-d")
    assert page_d["clicks_recent"] == 0
    assert page_d["clicks_previous"] == 5
    assert page_d["clicks_delta"] == -5
    assert page_d["clicks_delta_pct"] == -100.0
    assert page_d["note"] == "decay"


# ---------------------------------------------------------------------------
# Test 4 — Schema column match: transform output keys == master-excel schema
# ---------------------------------------------------------------------------

def test_schema_column_match(master_excel_schema: dict,
                              synthetic_recent: dict) -> None:
    """
    The 12 keys emitted by gsc_pull.transform for the gsc_performance
    sheet must match the master-excel.schema.json#gsc_performance
    required_columns names exactly (order included via the constant
    tuple GSC_PERFORMANCE_COLUMNS).
    """
    sheet_def = master_excel_schema["sheets"]["gsc_performance"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    assert schema_col_names == gsc_pull.GSC_PERFORMANCE_COLUMNS, (
        f"GSC_PERFORMANCE_COLUMNS drifted from master-excel schema: "
        f"got {gsc_pull.GSC_PERFORMANCE_COLUMNS}, schema {schema_col_names}"
    )

    # And the transform actually emits rows with those keys.
    out = gsc_pull.transform(synthetic_recent, enriched=None)
    for r in out["gsc_performance"]:
        assert tuple(r.keys()) == schema_col_names, (
            f"row column order drift: {tuple(r.keys())}"
        )


# ---------------------------------------------------------------------------
# Test 5 — DURUR fired: invalid input triggers explicit error (not silent fallback)
# ---------------------------------------------------------------------------

def test_durur_invalid_input_explicit_error() -> None:
    """
    Per the worker brief / quick-wins convention authority: invalid input
    must raise an explicit GscPullError, NOT degrade silently. Three
    surfaces tested here:
      (a) raw is not a dict
      (b) raw['rows'] is the wrong type
      (c) normalize_url on empty string
    """
    # (a) raw must be a dict.
    with pytest.raises(gsc_pull.GscPullError):
        gsc_pull.transform("not-a-dict")  # type: ignore[arg-type]

    # (b) rows must be a list.
    with pytest.raises(gsc_pull.GscPullError):
        gsc_pull.transform({"rows": "not-a-list"})

    # (c) empty string URL.
    with pytest.raises(gsc_pull.GscPullError):
        gsc_pull.normalize_url("")

    # (d) URL missing scheme.
    with pytest.raises(gsc_pull.GscPullError):
        gsc_pull.normalize_url("example.com/no-scheme")

    # (e) URL not a string.
    with pytest.raises(gsc_pull.GscPullError):
        gsc_pull.normalize_url(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 6 — Smoke E2E: mocked fixture file → CLI → schema-shaped JSON output
# ---------------------------------------------------------------------------

def test_smoke_e2e_cli_output(tmp_path: Path,
                               synthetic_recent: dict,
                               synthetic_previous: dict) -> None:
    """
    Smoke E2E without any live MCP call: write fixtures to disk, invoke
    the gsc_pull.main CLI entry point, assert the output JSON parses and
    matches the schema-locked column structure. Idempotency is also
    asserted: a second run with the same inputs produces byte-identical
    output.
    """
    raw_path = tmp_path / "search_analytics.json"
    enr_path = tmp_path / "enhanced_search_analytics.json"
    raw_path.write_text(
        json.dumps(synthetic_recent, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    enr_path.write_text(
        json.dumps(synthetic_previous, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    rc = gsc_pull.main([
        "--raw", str(raw_path),
        "--enriched", str(enr_path),
        "--output-dir", str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    out_file = out_dir / "gsc_performance.json"
    assert out_file.exists(), "CLI did not write gsc_performance.json"

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and payload, "empty output array"
    expected_cols = set(gsc_pull.GSC_PERFORMANCE_COLUMNS)
    for r in payload:
        assert set(r.keys()) == expected_cols

    # Idempotency: re-run with same inputs → byte-identical output file.
    first_bytes = out_file.read_bytes()
    rc2 = gsc_pull.main([
        "--raw", str(raw_path),
        "--enriched", str(enr_path),
        "--output-dir", str(out_dir),
    ])
    assert rc2 == 0
    second_bytes = out_file.read_bytes()
    assert first_bytes == second_bytes, (
        "transform is not byte-idempotent under re-run"
    )


# ---------------------------------------------------------------------------
# Test 7 — Transform tolerates absent enrichment (previous=None)
# ---------------------------------------------------------------------------

def test_transform_without_enrichment(synthetic_recent: dict) -> None:
    """
    First-run scenario: no previous window data available. Transform
    must produce rows with previous=0 and delta=clicks_recent (per the
    100% / -100% clamping in _delta_pct).
    """
    out = gsc_pull.transform(synthetic_recent, enriched=None)
    assert out["meta"]["enriched_used"] is False
    rows = out["gsc_performance"]
    assert len(rows) == 3  # only recent-window URLs
    for r in rows:
        assert r["clicks_previous"] == 0
        assert r["impressions_previous"] == 0
        assert r["position_previous"] == 0.0
