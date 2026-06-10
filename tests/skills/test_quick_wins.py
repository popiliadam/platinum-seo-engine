"""
tests/skills/test_quick_wins.py — quick-wins discovery skill end-to-end tests.

Eight cases, mirroring the 10-criterion acceptance gate from the worker
brief. Test 1 is the "live MCP" smoke: it asserts that the canonical
raw-MCP fixture (captured from a real `mcp__gsc__detect_quick_wins`
call against dentnotion on 2026-04-30) is present in the workspace
inbox at the path the §16.5 step-3 protocol mandates, and that its
shape is schema-valid (`schemas/gsc-tool-mapping.schema.json`'s D-03
URL invariant + minimum row count). MCP tools are not Python-callable
inside pytest; the live call was performed at-rest and persisted by
the W-P worker per the brief's "DUR + flag (skip etme)" rule — these
tests therefore validate the live payload by way of its persisted
witness file rather than re-issuing the call inside pytest.

Tests 2-8 cover the transform/approval/provenance discipline using
self-contained tmp_path fixtures (no workspace-staging side effects).

Schemas referenced:
  - schemas/master-excel.schema.json (quick_wins, opportunity, definitions)
  - schemas/events.schema.json (event_kind=provenance, source.kind=gsc_mcp)
  - schemas/gsc-tool-mapping.schema.json (D-03 url normalization invariant)
  - schemas/skill-frontmatter.schema.json
  - schemas/workflow-run.schema.json
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.discovery import quickwins_transform
from scripts.excel import transaction
from scripts.state import events_writer, workflow_runner


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

WORKSPACE_STAGING = Path(
    os.environ.get(
        "PSEO_WORKSPACE_STAGING",
        str(Path.home() / "Documents" / "platinum-seo-workspace-staging"),
    )
)
PILOT_SLUG = "dentnotion"
PILOT_DATE = "2026-04-30"
LIVE_RAW_PATH = (
    WORKSPACE_STAGING / "projects" / PILOT_SLUG / "inbox" / "gsc"
    / f"{PILOT_DATE}-detect_quick_wins-{PILOT_SLUG}.json"
)

SCHEMAS = REPO_ROOT / "schemas"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def master_excel_schema() -> dict:
    return json.loads((SCHEMAS / "master-excel.schema.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def events_schema() -> dict:
    return json.loads((SCHEMAS / "events.schema.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads((SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8"))


@pytest.fixture
def synthetic_raw() -> dict:
    """Minimal hand-built MCP payload — exercises the transform without
    depending on the live fixture file."""
    return {
        "quickWins": [
            {
                "query": "kw-high",
                "page": "https://example.com/page-a/?utm_source=fb&b=2&a=1#frag",
                "currentPosition": 11.5,
                "impressions": 1000,
                "currentClicks": 5,
                "currentCtr": 0.5,
                "potentialClicks": 50,
            },
            {
                "query": "kw-mid",
                "page": "HTTPS://Example.COM:443/page-b/",
                "currentPosition": 15.0,
                "impressions": 400,
                "currentClicks": 2,
                "currentCtr": 0.5,
                "potentialClicks": 20,
            },
            {
                "query": "kw-low",
                "page": "https://example.com/page-c",
                "currentPosition": 19.0,
                "impressions": 150,
                "currentClicks": 0,
                "currentCtr": 0.0,
                "potentialClicks": 7,
            },
        ],
        "totalOpportunities": 3,
    }


# ---------------------------------------------------------------------------
# Test 1 — live MCP smoke (validates the captured raw payload)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not WORKSPACE_STAGING.exists(),
    reason="local-only fixture: WORKSPACE_STAGING path missing on CI runner "
           "(Q-CI-W3-04 Phase 15 audit Wave 1 kategori #5 codify aday)"
)
def test_happy_path_gsc_live() -> None:
    """
    The W-P worker performed an at-rest live `mcp__gsc__detect_quick_wins`
    call against dentnotion (site_url=https://dentnotion.com/, last 28
    days) and persisted the response to the workspace inbox per §16.5
    step 3. This test PASSes when:
      (a) that file exists,
      (b) it parses as JSON,
      (c) it carries ≥ 5 quickWins rows (smoke threshold),
      (d) every row's `page` URL passes D-03 normalization (idempotent
          and lossless except for fragment/tracking),
      (e) every row carries `currentPosition`, `impressions`, `query`.

    If any of these fail the worker did not actually capture the live
    payload (DUR + flag — do not silently skip).
    """
    assert LIVE_RAW_PATH.exists(), (
        f"live MCP capture missing at {LIVE_RAW_PATH}; "
        f"§16.5 step-3 raw-inbox discipline violated"
    )
    payload = json.loads(LIVE_RAW_PATH.read_text(encoding="utf-8"))

    rows = payload.get("quickWins") or payload.get("quick_wins") or []
    assert isinstance(rows, list), "quickWins must be a list"
    assert len(rows) >= 5, f"smoke threshold: ≥5 rows, got {len(rows)}"

    # D-03: every page URL normalizes idempotently.
    for r in rows:
        assert "query" in r and "page" in r, f"missing keys: {r}"
        assert "currentPosition" in r, f"missing currentPosition: {r}"
        assert "impressions" in r, f"missing impressions: {r}"
        norm1 = quickwins_transform.normalize_url(r["page"])
        norm2 = quickwins_transform.normalize_url(norm1)
        assert norm1 == norm2, f"D-03 idempotency broke: {r['page']!r} → {norm1!r} → {norm2!r}"

    # Captured-by metadata sanity (worker-attached envelope).
    meta = payload.get("_meta") or {}
    assert meta.get("mcp_tool") == "gsc__detect_quick_wins"
    assert meta.get("site_url") == "https://dentnotion.com/"


# ---------------------------------------------------------------------------
# Test 2 — §16.5 step-3 raw JSON inbox path discipline
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not WORKSPACE_STAGING.exists(),
    reason="local-only fixture: WORKSPACE_STAGING path missing on CI runner "
           "(Q-CI-W3-04 Phase 15 audit Wave 1 kategori #5 codify aday)"
)
def test_inbox_raw_json_saved() -> None:
    """The raw payload must live at the canonical inbox path: every
    Phase 6+ MCP-ingestion skill copies this naming scheme verbatim."""
    inbox_dir = LIVE_RAW_PATH.parent
    assert inbox_dir.is_dir(), f"missing inbox dir {inbox_dir}"

    pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}-detect_quick_wins-[a-z][a-z0-9-]*\.json$"
    )
    files = [p for p in inbox_dir.glob("*.json") if pattern.match(p.name)]
    assert files, (
        "no file matching {date}-detect_quick_wins-{slug}.json in inbox; "
        "drift recovery would be impossible"
    )
    # Specifically the dentnotion capture.
    assert LIVE_RAW_PATH in files


# ---------------------------------------------------------------------------
# Test 3 — D-03 URL normalization is idempotent + correct
# ---------------------------------------------------------------------------

def test_url_normalization_idempotent() -> None:
    samples = [
        # (input, expected)
        ("HTTPS://Example.COM:443/foo/?b=2&a=1#frag",
         "https://example.com/foo?a=1&b=2"),
        ("http://EXAMPLE.com:80/", "http://example.com/"),
        ("https://dentnotion.com/page/?utm_source=fb&utm_medium=cpc&q=tr",
         "https://dentnotion.com/page?q=tr"),
        ("https://dentnotion.com/page/#section",
         "https://dentnotion.com/page"),
        ("https://dentnotion.com/", "https://dentnotion.com/"),
    ]
    for raw, expected in samples:
        got = quickwins_transform.normalize_url(raw)
        assert got == expected, f"normalize({raw!r}) → {got!r} (expected {expected!r})"
        # Idempotency.
        assert quickwins_transform.normalize_url(got) == got, \
            f"not idempotent: {raw!r} → {got!r}"


# ---------------------------------------------------------------------------
# Test 4 — opportunity score is deterministic + monotonic
# ---------------------------------------------------------------------------

def test_opportunity_scoring_deterministic() -> None:
    s = quickwins_transform.opportunity_score
    # Determinism.
    assert s(1000, 12) == s(1000, 12)
    # Formula sanity.
    assert s(1000, 12, threshold_position_max=20) == 1000 * 8
    assert s(500, 19, threshold_position_max=20) == 500 * 1
    # Past-threshold caps at 0 (never negative).
    assert s(1000, 25, threshold_position_max=20) == 0
    # Monotonic in impressions.
    assert s(2000, 12) > s(1000, 12)
    # Monotonic in headroom (lower position → higher score).
    assert s(1000, 11) > s(1000, 19)


# ---------------------------------------------------------------------------
# Test 5 — top-N ranking respects score-desc order
# ---------------------------------------------------------------------------

def test_top_n_ranking(synthetic_raw: dict) -> None:
    out = quickwins_transform.transform(synthetic_raw, top_n=2)
    assert len(out["quick_wins"]) == 2
    # kw-high is the clear winner (1000 imp × 8.5 headroom = 8500).
    assert out["quick_wins"][0]["query"] == "kw-high"
    # kw-mid (400 × 5 = 2000) ranks above kw-low (150 × 1 = 150).
    assert out["quick_wins"][1]["query"] == "kw-mid"
    # Schema-shape: 10 columns per the master-excel.schema quick_wins sheet.
    assert set(out["quick_wins"][0].keys()) == set(quickwins_transform.QUICK_WINS_COLUMNS)
    # Opportunity sheet: one row per query, sorted desc.
    assert [r["query"] for r in out["opportunity"]] == ["kw-high", "kw-mid"]
    # URL normalization landed in the row (utm stripped, fragment dropped,
    # default port stripped).
    top = out["quick_wins"][0]
    assert top["url"] == "https://example.com/page-a?a=1&b=2"


# ---------------------------------------------------------------------------
# Test 6 — workflow_runner.request_approval pauses the run
# ---------------------------------------------------------------------------

def _setup_ws(tmp_path: Path, slug: str) -> None:
    (tmp_path / "projects" / slug / "_state" / "workflows").mkdir(parents=True, exist_ok=True)


def test_approval_gate_workflow_pause(tmp_path: Path) -> None:
    slug = "qw-test"
    _setup_ws(tmp_path, slug)
    handle = workflow_runner.create_run(
        skill="quick-wins",
        project_slug=slug,
        steps=[
            {"name": "fetch_quick_wins"},
            {"name": "fetch_enriched"},
            {"name": "transform"},
            {"name": "request_approval"},
            {"name": "write_excel"},
            {"name": "render_report"},
        ],
        workspace_root=tmp_path,
    )
    assert handle.status == "running"

    workflow_runner.request_approval(
        handle.run_id, project_slug=slug,
        approver="user",
        subject="Top-N quick-wins seçildi, master.xlsx'e yazalım mı?",
        step_index=3,
        workspace_root=tmp_path,
    )
    re_read = workflow_runner.get(
        handle.run_id, project_slug=slug, workspace_root=tmp_path,
    )
    assert re_read.status == "awaiting_approval"
    assert re_read.data["approval_meta"]["approver"] == "user"
    assert re_read.data["steps"][3]["status"] == "awaiting_approval"


# ---------------------------------------------------------------------------
# Test 7 — resume after approval continues to running → done
# ---------------------------------------------------------------------------

def test_resume_after_approval_continues(tmp_path: Path) -> None:
    slug = "qw-test"
    _setup_ws(tmp_path, slug)
    handle = workflow_runner.create_run(
        skill="quick-wins",
        project_slug=slug,
        steps=[{"name": "transform"}, {"name": "request_approval"}, {"name": "write_excel"}],
        workspace_root=tmp_path,
    )
    workflow_runner.request_approval(
        handle.run_id, project_slug=slug,
        approver="user",
        subject="Approve top-N write?",
        step_index=1,
        workspace_root=tmp_path,
    )
    workflow_runner.approve(
        handle.run_id, project_slug=slug,
        approver="user", workspace_root=tmp_path,
    )
    final = workflow_runner.complete(
        handle.run_id, project_slug=slug,
        workspace_root=tmp_path,
        outputs={"top_n_count": "5",
                 "report": "outputs/reports/2026-04-30-quickwin.md"},
    )
    assert final.status == "done"
    assert final.data["outputs"]["top_n_count"] == "5"


# ---------------------------------------------------------------------------
# Test 8 — provenance event is emitted and validates against events schema
# ---------------------------------------------------------------------------

def test_provenance_event_emitted(tmp_path: Path, events_schema: dict) -> None:
    slug = "qw-test"
    _setup_ws(tmp_path, slug)
    # Mimic what the skill emits at step 9.
    raw_bytes = 4096
    rid = events_writer.next_run_id(slug, workspace_root=tmp_path)
    result = events_writer.append_provenance(
        project_id=slug,
        run_id=rid,
        source={
            "kind": "gsc_mcp",
            "mcp_server": "gsc",
            "mcp_tool": "gsc__detect_quick_wins",
            "response_bytes": raw_bytes,
        },
        operation="project_excel",
        target_excel_sheet="quick_wins",
        rows_written=5,
        workspace_root=tmp_path,
    )
    assert result.event_id

    events_path = tmp_path / "projects" / slug / "_state" / "events.jsonl"
    lines = [json.loads(line) for line in events_path.read_text("utf-8").splitlines() if line.strip()]
    prov = [e for e in lines if e.get("event_kind") == "provenance"
            and e.get("source", {}).get("kind") == "gsc_mcp"]
    assert prov, "no provenance event_kind=provenance source.kind=gsc_mcp emitted"

    # Re-validate the emitted record against the canonical events schema.
    validator = Draft7Validator(events_schema)
    for evt in prov:
        errs = sorted(validator.iter_errors(evt), key=lambda e: e.path)
        assert not errs, f"emitted event invalid: {[(list(e.absolute_path), e.message) for e in errs]}"


# ---------------------------------------------------------------------------
# Test 9 — D-011 dedup_by_url collapses multi-query rows sharing a URL
# ---------------------------------------------------------------------------

def test_dedup_by_url_keeps_top_score() -> None:
    """D-011 fix (Phase 7 closeout): when the GSC payload returns multiple
    rows that share the same URL (different queries), dedup_by_url=True
    (default) collapses them by keeping only the highest-_score row per
    url_normalized. Phase 6 live capture surfaced 33 quick_wins rows but
    only 7 unique URLs (~26 duplicates). The opt-out path (False) preserves
    every (query, URL) pair for callers that need multi-query analysis."""
    raw = {
        "quickWins": [
            # Same URL, lower-score row (low impressions × small headroom).
            {
                "query": "alpha-low",
                "page": "https://example.com/page-x/",
                "currentPosition": 18.0,
                "impressions": 100,
                "currentClicks": 1,
                "currentCtr": 0.01,
                "potentialClicks": 5,
            },
            # Same URL, higher-score row (high impressions × big headroom).
            {
                "query": "alpha-high",
                "page": "https://example.com/page-x/",
                "currentPosition": 9.0,
                "impressions": 2000,
                "currentClicks": 10,
                "currentCtr": 0.005,
                "potentialClicks": 100,
            },
            # Different URL — should always be present.
            {
                "query": "beta",
                "page": "https://example.com/page-y/",
                "currentPosition": 14.0,
                "impressions": 250,
                "currentClicks": 0,
                "currentCtr": 0.0,
                "potentialClicks": 12,
            },
        ],
        "totalOpportunities": 3,
    }

    # Default behavior: dedup_by_url=True.
    out = quickwins_transform.transform(raw, top_n=10)
    urls = [r["url"] for r in out["quick_wins"]]
    assert len(urls) == len(set(urls)), (
        f"D-011 violated — duplicate URLs leaked into quick_wins: {urls}"
    )
    page_x_row = next(r for r in out["quick_wins"] if "page-x" in r["url"])
    assert page_x_row["query"] == "alpha-high", (
        f"dedup must keep the higher-_score row, got {page_x_row['query']}"
    )
    assert page_x_row["impressions_30d"] == 2000
    assert out["meta"]["dedup_by_url_applied"] is True

    # Opt-out: dedup_by_url=False preserves every (query, URL) pair.
    out2 = quickwins_transform.transform(raw, top_n=10, dedup_by_url=False)
    urls2 = [r["url"] for r in out2["quick_wins"]]
    page_x_count = sum(1 for u in urls2 if "page-x" in u)
    assert page_x_count == 2, (
        f"opt-out must preserve duplicates, got {page_x_count} page-x rows"
    )
    assert out2["meta"]["dedup_by_url_applied"] is False


# ---------------------------------------------------------------------------
# Tests 10+ — quick-wins SKILL.md body contract (GAP-M2/M3 + dispatch addenda)
# ---------------------------------------------------------------------------

QW_SKILL = REPO_ROOT / "skills" / "discovery" / "quick-wins" / "SKILL.md"


def _qw_text() -> str:
    return QW_SKILL.read_text(encoding="utf-8")


def _qw_frontmatter() -> dict:
    import yaml
    m = re.match(r"^---\n(.*?)\n---\n", _qw_text(), re.DOTALL)
    assert m, "no frontmatter in quick-wins SKILL.md"
    return yaml.safe_load(m.group(1))


def test_qw_trigger_band_drops_stale_8_20() -> None:
    """Dispatch addendum: the stale '8-20' band must be gone (canonical 11-20)."""
    text = _qw_text()
    assert "8-20" not in text, "stale '8-20' band must be dropped (canonical 11-20)"
    assert "11-20" in text


def test_qw_report_filename_canonical() -> None:
    """§GAP addendum: output report filename matches the template (quickwin.template.md)."""
    text = _qw_text()
    assert "{date}-quickwin.md" in text
    assert "{date}-quick-wins.md" not in text


def test_qw_aio_inputs_present() -> None:
    fm = _qw_frontmatter()
    assert fm["inputs"]["aio_check"]["type"] == "boolean"
    assert fm["inputs"]["aio_check"]["default"] is False
    assert fm["inputs"]["aio_top_k"]["type"] == "integer"
    assert fm["inputs"]["aio_top_k"]["default"] == 20


def test_qw_durur_11_ctr_curve() -> None:
    text = _qw_text()
    # quick-wins enumerates DURURs as a numbered list under a counted header
    # (its convention), not inline "DURUR #N" tokens.
    assert "DURUR conditions (11)" in text  # count bumped 10 -> 11
    assert "ctr-curve.json" in text
    assert "CurveLoadError" in text  # the DURUR mechanism (no silent fallback)


def test_qw_step4_cli_has_curve_and_aio_flags() -> None:
    text = _qw_text()
    assert "--ctr-curve" in text
    assert "--aio-presence" in text


def test_qw_opportunity_score_is_uplift_model() -> None:
    text = _qw_text()
    assert "expected_uplift_clicks" in text
    assert "R-139" in text  # versioned curve constants citation


def test_qw_aio_presence_columns_cite_r140() -> None:
    text = _qw_text()
    assert "aio_presence" in text
    assert "R-140" in text
    assert "not_detected" in text
    # honesty: MCP-sync can never assert absence
    assert not re.search(r"\babsent\b", text)


def test_qw_aio_consent_not_required_note() -> None:
    text = _qw_text().lower()
    assert "consent" in text
    assert "read-only" in text


def test_qw_r139_curve_constants_only_in_fences() -> None:
    """R-139 grep sentinel: curve constants must not appear in SKILL prose;
    only inside fenced worked-examples."""
    defenced = re.sub(r"```.*?```", "", _qw_text(), flags=re.DOTALL)
    for forbidden in ("0.398", "0.703"):
        assert forbidden not in defenced, (
            f"R-139: curve constant {forbidden} leaked into SKILL prose"
        )


def test_quickwin_template_uplift_labels() -> None:
    """GAP-M3 D3: report template surfaces the uplift model + AIO count."""
    t = (REPO_ROOT / "templates" / "reports" / "quickwin.template.md").read_text("utf-8")
    assert "$top_uplift" in t
    assert "$aio_present_count" in t
    assert "Beklenen tıklama kazanımı" in t
    # the old standalone "Opportunity score:" headline label is renamed
    assert "Opportunity score:" not in t


# ---------------------------------------------------------------------------
# GAP-M-W2 — control_cohort (R-138 intervention cohort tagging)
# ---------------------------------------------------------------------------

def _cohort_raw() -> dict:
    """6 distinct rows: 3 high-impression treated (pos 12, imp 1000) outrank 3
    candidates by uplift; two candidates are same-band (matchable), one is far
    out of position tolerance (must NOT be matched)."""
    return {
        "quickWins": [
            # treated — uplift 20 each (pos 12 → target 7 → ctr .030; 30-10)
            {"query": "t-alpha", "page": "https://example.com/t1",
             "currentPosition": 12.0, "impressions": 1000, "currentClicks": 10},
            {"query": "t-bravo", "page": "https://example.com/t2",
             "currentPosition": 12.0, "impressions": 1000, "currentClicks": 10},
            {"query": "t-charlie", "page": "https://example.com/t3",
             "currentPosition": 12.0, "impressions": 1000, "currentClicks": 10},
            # in-tolerance controls (pos diff ≤ 2, imp ratio 0.7/0.8 ∈ [0.5,2])
            {"query": "c-near1", "page": "https://example.com/c1",
             "currentPosition": 12.0, "impressions": 700, "currentClicks": 7},
            {"query": "c-near2", "page": "https://example.com/c2",
             "currentPosition": 13.0, "impressions": 800, "currentClicks": 8},
            # OUT of position tolerance (|13.. vs 19| = 7 > 2) — never matched
            {"query": "c-far", "page": "https://example.com/c3",
             "currentPosition": 19.0, "impressions": 700, "currentClicks": 7},
        ],
    }


def test_control_cohort_matched_within_tolerance() -> None:
    """transform() emits a third `control_cohort` array (R-138): matched
    same-band controls from the scored-but-not-selected tail; an out-of-
    tolerance candidate is excluded; meta.controls_matched is reported."""
    out = quickwins_transform.transform(_cohort_raw(), top_n=3, dedup_by_url=True)
    assert "control_cohort" in out, "transform must emit a control_cohort array"

    treated_q = {r["query"] for r in out["quick_wins"]}
    assert treated_q == {"t-alpha", "t-bravo", "t-charlie"}

    controls = out["control_cohort"]
    control_q = {r["query"] for r in controls}
    assert control_q == {"c-near1", "c-near2"}, (
        "in-tolerance controls only; c-far must be excluded"
    )
    assert "c-far" not in control_q
    assert out["meta"]["controls_matched"] == 2

    # Cohort row shape (matches the Step 7b cohort-file shape consumed by
    # intervention_outcome.py): query, url, position, impressions_30d, clicks_30d.
    for c in controls:
        assert set(c.keys()) == {
            "query", "url", "position", "impressions_30d", "clicks_30d"
        }

    # Disjoint from treated (no query/url overlap) — R-138 control discipline.
    treated_url = {r["url"] for r in out["quick_wins"]}
    assert control_q.isdisjoint(treated_q)
    assert {c["url"] for c in controls}.isdisjoint(treated_url)

    # Each matched control is within position tolerance ±2 of SOME treated row
    # and within the 0.5×–2× impressions band.
    treated_rows = out["quick_wins"]
    for c in controls:
        near = [
            t for t in treated_rows
            if abs(t["current_position"] - c["position"]) <= 2.0
            and 0.5 <= (c["impressions_30d"] / t["impressions_30d"]) <= 2.0
        ]
        assert near, f"control {c['query']} matched no treated row in-band"


def test_control_cohort_deterministic() -> None:
    """Same input → byte-identical control_cohort (greedy match is
    deterministic; candidate rank order breaks distance ties)."""
    a = quickwins_transform.transform(_cohort_raw(), top_n=3)
    b = quickwins_transform.transform(_cohort_raw(), top_n=3)
    assert json.dumps(a["control_cohort"], sort_keys=True) == \
        json.dumps(b["control_cohort"], sort_keys=True)


def test_qw_skill_documents_cohort_step_r138() -> None:
    """GAP-M-W2 contract lock: the quick-wins SKILL documents Step 7b
    (R-138 treated+control cohort snapshot), the cohort step name in
    create_run, the cohort output path, and cites R-138."""
    body = _qw_text()
    assert "cohort_snapshot" in body, "Step 7b step name must be in create_run"
    assert "Step 7b" in body
    assert "quickwin-cohorts" in body and "-cohort.json" in body
    assert "control_cohort" in body
    assert "R-138" in body
