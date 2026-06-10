"""
tests/skills/test_content_decay.py — content-decay discovery skill tests.

Mirrors tests/skills/test_gsc_pull.py structure (frontmatter parse, URL
idempotency, transform unit, schema column match, DURUR fired, smoke
E2E with mocked fixture, trend coverage). MCP tools are NOT Python-
callable inside pytest; live MCP calls are performed at-rest by the
manager per the §16.5 raw-inbox discipline. These tests therefore
validate the transform + skill contract, not the upstream MCP fetch
itself.

Schemas referenced:
  - schemas/master-excel.schema.json#content_decay (8 required_columns)
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

from scripts.discovery import content_decay_transform as cdt


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "content-decay" / "SKILL.md"


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
    """Parse the YAML frontmatter block of skills/discovery/content-decay/SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_recent() -> dict:
    """Recent-window enhanced_search_analytics-shape payload."""
    return {
        "rows": [
            # page-decay: previous=100, recent=40 -> -60% (DECAY)
            {"keys": ["https://example.com/blog/decay-post"], "clicks": 40,
             "impressions": 1000, "ctr": 0.04, "position": 12.0},
            # page-stable: previous=50, recent=52 -> +4% (STABLE)
            {"keys": ["https://example.com/products/stable-item"], "clicks": 52,
             "impressions": 800, "ctr": 0.065, "position": 8.0},
            # page-growth: previous=20, recent=60 -> +200% (GROWTH)
            {"keys": ["https://example.com/blog/growth-piece"], "clicks": 60,
             "impressions": 600, "ctr": 0.10, "position": 5.0},
            # page-new: not in previous, recent=25 (NEW)
            {"keys": ["https://example.com/blog/new-article"], "clicks": 25,
             "impressions": 200, "ctr": 0.125, "position": 6.0},
            # URL canonicality stress: same as page-decay but with utm + uppercase host.
            # Aggregator must merge these as a single normalized URL.
            {"keys": ["HTTPS://Example.COM:443/blog/decay-post/?utm_source=fb#top"],
             "clicks": 5, "impressions": 50, "ctr": 0.10, "position": 11.5},
        ]
    }


@pytest.fixture
def synthetic_previous() -> dict:
    """Previous-window enhanced_search_analytics-shape payload."""
    return {
        "rows": [
            {"keys": ["https://example.com/blog/decay-post"], "clicks": 100,
             "impressions": 2000, "ctr": 0.05, "position": 9.0},
            {"keys": ["https://example.com/products/stable-item"], "clicks": 50,
             "impressions": 800, "ctr": 0.0625, "position": 7.5},
            {"keys": ["https://example.com/blog/growth-piece"], "clicks": 20,
             "impressions": 700, "ctr": 0.0286, "position": 14.0},
            # page-retired: present here, missing from recent
            {"keys": ["https://example.com/old/retired-page"], "clicks": 80,
             "impressions": 1500, "ctr": 0.053, "position": 11.0},
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
      (b) carry name=content-decay, status=active (asserted as a member of
          the valid lifecycle set {active, deprecated, wip}), version="1.0",
          category=discovery,
      (c) declare project_slug as a required string input,
      (d) list mcp__gsc__enhanced_search_analytics in required tools,
      (e) declare DFS historical_rank_overview as optional,
      (f) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "content-decay"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "discovery"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True

    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__gsc__enhanced_search_analytics" in required_tools

    optional_tools = fm["mcp_tools"].get("optional", [])
    assert any("historical_rank_overview" in t for t in optional_tools)

    outputs = fm["outputs"]
    assert any("master.xlsx#content_decay" in o for o in outputs)
    assert any("inbox/gsc/" in o and "decay-recent" in o for o in outputs)
    assert any("inbox/gsc/" in o and "decay-previous" in o for o in outputs)
    assert "events.jsonl" in outputs

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
        ("https://example.org/page/#section", "https://example.org/page"),
        ("https://example.org/", "https://example.org/"),
    ]
    for raw, expected in samples:
        got = cdt.normalize_url(raw)
        assert got == expected, (
            f"normalize({raw!r}) → {got!r} (expected {expected!r})"
        )
        assert cdt.normalize_url(got) == got, (
            f"not idempotent: {raw!r} → {got!r}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Empty input → ContentDecayError (decay-specific DURUR #8)
# ---------------------------------------------------------------------------

def test_empty_inputs_raise_durur() -> None:
    """
    Both windows empty (no rows after aggregation) is the decay-specific
    DURUR #8 ("no data in window"). MUST raise, not silently return [].
    """
    with pytest.raises(cdt.ContentDecayError):
        cdt.transform({"rows": []}, {"rows": []})

    with pytest.raises(cdt.ContentDecayError):
        cdt.transform(None, None)


# ---------------------------------------------------------------------------
# Test 4 — Trend labels: NEW, RETIRED, DECAY, STABLE, GROWTH
# ---------------------------------------------------------------------------

def test_trend_labels_cover_all_five_buckets(synthetic_recent: dict,
                                              synthetic_previous: dict) -> None:
    out = cdt.transform(synthetic_recent, synthetic_previous)
    rows = out["content_decay"]

    by_url = {r["url"]: r for r in rows}

    decay = by_url["https://example.com/blog/decay-post"]
    # 100 → 45 (40 from canonical row + 5 from utm-stripped duplicate
    # that normalizes to the same URL) = -55% → DECAY.
    assert decay["clicks_previous"] == 100
    assert decay["clicks_recent"] == 45
    assert decay["clicks_delta"] == -55
    assert decay["delta_pct"] == -55.0
    assert decay["trend"] == "DECAY"
    assert decay["pillar"] == "blog"
    assert decay["action"] == "investigate + refresh"

    stable = by_url["https://example.com/products/stable-item"]
    assert stable["trend"] == "STABLE"
    assert stable["pillar"] == "products"
    assert stable["action"] == "monitor"

    growth = by_url["https://example.com/blog/growth-piece"]
    assert growth["trend"] == "GROWTH"
    assert growth["delta_pct"] == 200.0
    assert growth["action"] == "double-down"

    new = by_url["https://example.com/blog/new-article"]
    assert new["trend"] == "NEW"
    assert new["clicks_previous"] == 0
    assert new["delta_pct"] == 100.0    # ±100 clamp on previous=0
    assert new["action"] == "new content tracking"

    retired = by_url["https://example.com/old/retired-page"]
    assert retired["trend"] == "RETIRED"
    assert retired["clicks_recent"] == 0
    assert retired["delta_pct"] == -100.0
    assert retired["action"] == "redirect or revive review"


# ---------------------------------------------------------------------------
# Test 5 — Schema column match: transform output keys == master-excel content_decay
# ---------------------------------------------------------------------------

def test_schema_column_match(master_excel_schema: dict,
                              synthetic_recent: dict,
                              synthetic_previous: dict) -> None:
    """
    The 8 keys emitted by transform for the content_decay sheet must
    match master-excel.schema.json#content_decay required_columns names
    exactly (and order, via the constant tuple CONTENT_DECAY_COLUMNS).
    """
    sheet_def = master_excel_schema["sheets"]["content_decay"]
    schema_col_names = tuple(c["name"] for c in sheet_def["required_columns"])
    assert schema_col_names == cdt.CONTENT_DECAY_COLUMNS, (
        f"CONTENT_DECAY_COLUMNS drifted from master-excel schema: "
        f"got {cdt.CONTENT_DECAY_COLUMNS}, schema {schema_col_names}"
    )

    out = cdt.transform(synthetic_recent, synthetic_previous)
    for r in out["content_decay"]:
        assert tuple(r.keys()) == schema_col_names, (
            f"row column order drift: {tuple(r.keys())}"
        )


# ---------------------------------------------------------------------------
# Test 6 — Clamp logic: previous=0 / recent=0 hit ±100 (Phase 6 paterni)
# ---------------------------------------------------------------------------

def test_delta_pct_clamps_to_pm100() -> None:
    """
    Mirrors gsc-pull's _delta_pct contract:
      previous=0, recent>0  → +100.0
      previous>0, recent=0  → -100.0 (raw arithmetic; not the clamp branch
                                       but the natural value)
      previous=0, recent=0  →    0.0
    """
    # previous=0, recent>0 → clamped to +100
    out = cdt.transform(
        {"rows": [{"keys": ["https://x.tld/a"], "clicks": 50}]},
        {"rows": []},
    )
    a = next(r for r in out["content_decay"] if r["url"].endswith("/a"))
    assert a["clicks_previous"] == 0
    assert a["clicks_recent"] == 50
    assert a["delta_pct"] == 100.0
    assert a["trend"] == "NEW"

    # previous>0, recent=0 → -100 (RETIRED)
    out = cdt.transform(
        {"rows": []},
        {"rows": [{"keys": ["https://x.tld/b"], "clicks": 50}]},
    )
    b = next(r for r in out["content_decay"] if r["url"].endswith("/b"))
    assert b["clicks_previous"] == 50
    assert b["clicks_recent"] == 0
    assert b["delta_pct"] == -100.0
    assert b["trend"] == "RETIRED"

    # previous=0, recent=0 (only relevant when URL appears in payload but
    # has no clicks; normally aggregator drops it). Use the helper directly.
    assert cdt._delta_pct(0, 0) == 0.0


# ---------------------------------------------------------------------------
# Test 7 — Pillar inference covers blog, products, multi-segment, root
# ---------------------------------------------------------------------------

def test_pillar_inference_first_segment() -> None:
    cases = [
        ("https://example.com/blog/x", "blog"),
        ("https://example.com/products/y/details", "products"),
        ("https://example.com/a/b/c", "a"),
        ("https://example.com/", ""),
        ("https://example.com", ""),
        ("not-a-url", ""),
        ("", ""),
    ]
    for url, expected in cases:
        assert cdt.infer_pillar(url) == expected, (
            f"infer_pillar({url!r}) → {cdt.infer_pillar(url)!r} "
            f"(expected {expected!r})"
        )


# ---------------------------------------------------------------------------
# Test 8 — Sort order: rows by clicks_delta asc (most decayed first)
# ---------------------------------------------------------------------------

def test_rows_sorted_by_clicks_delta_asc(synthetic_recent: dict,
                                          synthetic_previous: dict) -> None:
    out = cdt.transform(synthetic_recent, synthetic_previous)
    deltas = [r["clicks_delta"] for r in out["content_decay"]]
    assert deltas == sorted(deltas), (
        f"rows not sorted by clicks_delta asc: {deltas}"
    )
    # First row is the worst decay (RETIRED page-d at -80).
    assert out["content_decay"][0]["url"] == "https://example.com/old/retired-page"
    assert out["content_decay"][0]["clicks_delta"] == -80


# ---------------------------------------------------------------------------
# Test 9 — DURUR explicit errors (not silent fallback)
# ---------------------------------------------------------------------------

def test_durur_invalid_input_explicit_error() -> None:
    """
    Per the worker brief / quick-wins convention authority: invalid input
    must raise an explicit ContentDecayError, NOT degrade silently.
    """
    # (a) recent must be a dict.
    with pytest.raises(cdt.ContentDecayError):
        cdt.transform("not-a-dict", {"rows": []})  # type: ignore[arg-type]

    # (b) previous must be a dict.
    with pytest.raises(cdt.ContentDecayError):
        cdt.transform({"rows": []}, ["not-a-dict"])  # type: ignore[arg-type]

    # (c) recent.rows must be a list.
    with pytest.raises(cdt.ContentDecayError):
        cdt.transform({"rows": "not-a-list"}, {"rows": []})

    # (d) empty / unparseable URL.
    with pytest.raises(cdt.ContentDecayError):
        cdt.normalize_url("")
    with pytest.raises(cdt.ContentDecayError):
        cdt.normalize_url("example.com/no-scheme")
    with pytest.raises(cdt.ContentDecayError):
        cdt.normalize_url(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 10 — Smoke E2E: CLI writes byte-idempotent output
# ---------------------------------------------------------------------------

def test_smoke_e2e_cli_idempotent(tmp_path: Path,
                                    synthetic_recent: dict,
                                    synthetic_previous: dict) -> None:
    """
    Smoke E2E without any live MCP call: write fixtures to disk, invoke
    main() CLI, assert the output JSON parses, matches the schema-locked
    column structure, and a second run produces byte-identical output
    (idempotency invariant — no fetched_at-style nondeterminism).
    """
    recent_path = tmp_path / "recent.json"
    previous_path = tmp_path / "previous.json"
    recent_path.write_text(
        json.dumps(synthetic_recent, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    previous_path.write_text(
        json.dumps(synthetic_previous, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    rc = cdt.main([
        "--recent",   str(recent_path),
        "--previous", str(previous_path),
        "--output-dir", str(out_dir),
    ])
    assert rc == 0, "CLI returned non-zero exit code"

    out_file = out_dir / "content_decay.json"
    assert out_file.exists(), "CLI did not write content_decay.json"

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and payload, "empty output array"
    expected_cols = set(cdt.CONTENT_DECAY_COLUMNS)
    for r in payload:
        assert set(r.keys()) == expected_cols

    # Idempotency: re-run with same inputs → byte-identical output.
    first_bytes = out_file.read_bytes()
    rc2 = cdt.main([
        "--recent",   str(recent_path),
        "--previous", str(previous_path),
        "--output-dir", str(out_dir),
    ])
    assert rc2 == 0
    second_bytes = out_file.read_bytes()
    assert first_bytes == second_bytes, (
        "transform is not byte-idempotent under re-run"
    )


# ---------------------------------------------------------------------------
# Test 11 (I1) — R-85 multi-signal: clicks-only drop WITHOUT corroboration is
# STABLE (the explicit old→new verdict difference).
# ---------------------------------------------------------------------------

def test_r85_clicks_drop_without_corroboration_is_stable() -> None:
    """OLD logic (clicks-only, -20% threshold) → DECAY.
    NEW R-85 (clicks < -30% AND position worse) OR (impr < -40% AND rank
    worse): a -25% clicks drop is NOT < -30%, impressions are flat, and the
    position IMPROVED — no corroboration → STABLE. This is the headline
    old-vs-new verdict difference R-85 was designed to produce (single-signal
    click volatility ≠ decay)."""
    recent = {"rows": [{"keys": ["https://x.tld/page"], "clicks": 75,
                        "impressions": 1000, "position": 6.0}]}
    previous = {"rows": [{"keys": ["https://x.tld/page"], "clicks": 100,
                          "impressions": 1000, "position": 8.0}]}
    out = cdt.transform(recent, previous)
    row = next(r for r in out["content_decay"] if r["url"].endswith("/page"))
    assert row["delta_pct"] == -25.0          # clicks DID drop 25% (old=DECAY)
    assert row["trend"] == "STABLE"           # new=STABLE: no R-85 corroboration
    assert row["action"] == "monitor"


def test_r85_impressions_collapse_with_rank_drop_is_decay() -> None:
    """R-85 branch 2: clicks only -10% (NOT a clicks-branch decay) but
    impressions -45% AND ranking trend negative (position worse) → DECAY."""
    recent = {"rows": [{"keys": ["https://x.tld/imp"], "clicks": 90,
                        "impressions": 550, "position": 14.0}]}
    previous = {"rows": [{"keys": ["https://x.tld/imp"], "clicks": 100,
                          "impressions": 1000, "position": 9.0}]}
    out = cdt.transform(recent, previous)
    row = next(r for r in out["content_decay"] if r["url"].endswith("/imp"))
    assert row["trend"] == "DECAY"
    assert out["meta"]["decay_branch_counts"]["impressions+rank"] >= 1


def test_r85_clicks_and_position_drop_is_decay() -> None:
    """R-85 branch 1: clicks < -30% AND position worsened > +5 → DECAY."""
    recent = {"rows": [{"keys": ["https://x.tld/cp"], "clicks": 60,
                        "impressions": 1000, "position": 16.0}]}
    previous = {"rows": [{"keys": ["https://x.tld/cp"], "clicks": 100,
                          "impressions": 1000, "position": 9.0}]}
    out = cdt.transform(recent, previous)
    row = next(r for r in out["content_decay"] if r["url"].endswith("/cp"))
    assert row["trend"] == "DECAY"
    assert out["meta"]["decay_branch_counts"]["clicks+position"] >= 1


def test_r85_profile_aware_ymyl_flags_what_default_does_not() -> None:
    """Profile-aware thresholds (via cascade_default): same signals —
    clicks -22%, position +4, impressions flat.
      - default/other profile (-30%/+5): STABLE (neither threshold crossed).
      - YMYL profile (-20%/+3, stricter): DECAY (both crossed).
    Demonstrates the profile changes the verdict on identical data."""
    recent = {"rows": [{"keys": ["https://x.tld/ymyl"], "clicks": 78,
                        "impressions": 1000, "position": 11.0}]}
    previous = {"rows": [{"keys": ["https://x.tld/ymyl"], "clicks": 100,
                          "impressions": 1000, "position": 7.0}]}
    r_default = next(
        r for r in cdt.transform(recent, previous)["content_decay"]
        if r["url"].endswith("/ymyl")
    )
    r_ymyl = next(
        r for r in cdt.transform(
            recent, previous, profile_config={"profile": "ymyl-high"},
        )["content_decay"]
        if r["url"].endswith("/ymyl")
    )
    assert r_default["trend"] == "STABLE"
    assert r_ymyl["trend"] == "DECAY"


def test_meta_records_comparison_mode_and_thresholds(
    synthetic_recent: dict, synthetic_previous: dict,
) -> None:
    """meta records which R-85 branch fired + the resolved thresholds +
    the comparison mode (default = prior_window)."""
    out = cdt.transform(synthetic_recent, synthetic_previous)
    meta = out["meta"]
    assert meta["comparison_mode"] == "prior_window"
    assert meta["clicks_threshold"] == -30.0
    assert meta["position_threshold"] == 5.0
    assert meta["impressions_threshold"] == -40.0
    assert "decay_branch_counts" in meta
    assert set(meta["decay_branch_counts"]) == {"clicks+position", "impressions+rank"}


def test_yoy_mode_with_baseline_computes_decay() -> None:
    """--yoy comparison_mode: when the year-ago window carries data, decay is
    computed against it and meta records the mode."""
    recent = {"rows": [{"keys": ["https://x.tld/y"], "clicks": 50,
                        "impressions": 600, "position": 15.0}]}
    year_ago = {"rows": [{"keys": ["https://x.tld/y"], "clicks": 100,
                          "impressions": 1200, "position": 8.0}]}
    out = cdt.transform(recent, year_ago, comparison_mode="yoy")
    assert out["meta"]["comparison_mode"] == "yoy"
    assert out["meta"]["yoy_unavailable"] is False
    row = next(r for r in out["content_decay"] if r["url"].endswith("/y"))
    assert row["trend"] == "DECAY"   # clicks -50%, impr -50%, position +7


def test_yoy_mode_without_baseline_reports_unavailable_not_fake() -> None:
    """--yoy with NO year-ago data must NOT fabricate verdicts: emit a
    yoy_unavailable note + zero rows (recent-only data has no valid YoY
    baseline). 'never fake it.'"""
    recent = {"rows": [{"keys": ["https://x.tld/a"], "clicks": 50,
                        "impressions": 100, "position": 5.0}]}
    out = cdt.transform(recent, {"rows": []}, comparison_mode="yoy")
    assert out["meta"]["comparison_mode"] == "yoy"
    assert out["meta"]["yoy_unavailable"] is True
    assert out["content_decay"] == []
    assert "yoy" in out["meta"]["yoy_note"].lower()
