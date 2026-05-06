"""
tests/skills/test_dfs_pull.py — dfs-pull ingestion skill tests (D-003 staging-only).

Phase 6 Wave 1, paid-MCP authority. The TR forwarding workaround
(live test 1835229: dataforseo-mcp-server@2.8.9 returns
location_code=2840 even when 2792 is requested) is exercised via mock
fixtures — no live API needed.

Routing change (D-003): dfs_pull no longer writes to master.xlsx; it
emits SQLite-style staging JSON files at
``_state/staging/dfs_{tool}_{date}_{slug}.json`` (mirrors scrapling-ops).
The Phase 8 cluster-map skill consumes the staging JSON downstream.

Cross-module IMPORT-only discipline:
  - scripts.ingestion.dfs_pull      (transform + TR workaround helpers
                                     + write_staging + StagingSchemaError)
  - scripts.state.events_writer     (dataforseo_mcp provenance event;
                                     target_excel_sheet=null in staging-only mode)
  - scripts.budget.check_budget     (§16.8 pre-flight; FIRST paid skill)
    (imported indirectly via dfs_pull.preflight_budget)

Schemas referenced:
  - schemas/skill-frontmatter.schema.json   (frontmatter draft7)
  - schemas/events.schema.json              (source.kind=dataforseo_mcp,
                                             target_excel_sheet=null)

NOTE: scripts.excel.transaction is intentionally NOT imported — staging-
only routing means dfs_pull does not produce Excel rows. Cluster-map
(Phase 8) is the consumer that lifts staging JSON into master.xlsx.

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_dfs_pull.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.ingestion import dfs_pull
from scripts.state import events_writer


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_MD = REPO_ROOT / "skills" / "ingestion" / "dfs-pull" / "SKILL.md"


# ---------------------------------------------------------------------------
# Fixtures — schemas
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def events_schema() -> dict:
    return json.loads((SCHEMAS / "events.schema.json").read_text("utf-8"))


# ---------------------------------------------------------------------------
# Fixtures — mock DFS payloads (TR forwarding workaround test data)
# ---------------------------------------------------------------------------

@pytest.fixture
def overview_payload_us_drift() -> dict:
    """Mock keyword_overview response from the wrapper bug (1835229):
    location_code=2840 (US) returned even though 2792 (TR) was requested.
    """
    return {
        "version": "0.1.20240101",
        "status_code": 20000,
        "tasks": [{
            "id": "06241000-1535-0095-0000-7e9b3aab3bcc",
            "status_code": 20000,
            "data": {
                "location_code": 2792,    # what we *requested*
                "language_code": "tr",
            },
            "result": [{
                # what the wrapper actually served (THE BUG)
                "location_code": 2840,    # US
                "language_code": "en",
                "items": [
                    {
                        "keyword": "dis klinigi",
                        "keyword_info": {"search_volume": 9100, "competition": "MEDIUM"},
                        "search_intent_info": {"main_intent": "commercial"},
                        "language_code": "en",
                    }
                ],
            }],
        }],
    }


@pytest.fixture
def overview_payload_tr_correct() -> dict:
    """Mock keyword_overview response after workaround C (HTTP bypass):
    location_code=2792 / language_code='tr' honoured.
    """
    return {
        "version": "0.1.20240101",
        "status_code": 20000,
        "tasks": [{
            "id": "06241000-1535-0095-0000-7e9b3aab3bcc",
            "status_code": 20000,
            "data": {"location_code": 2792, "language_code": "tr"},
            "result": [{
                "location_code": 2792,
                "language_code": "tr",
                "items": [
                    {
                        "keyword": "kw-alpha",
                        "keyword_info": {
                            "search_volume": 12100,
                            "competition": 0.55,
                            "competition_level": "MEDIUM",
                            "cpc": 1.05,
                        },
                        "search_intent_info": {"main_intent": "commercial"},
                        "language_code": "tr",
                        "location_code": 2792,
                    },
                    {
                        "keyword": "kw-beta",
                        "keyword_info": {
                            "search_volume": 8100,
                            "competition": 0.85,
                            "competition_level": "HIGH",
                            "cpc": 2.30,
                        },
                        "search_intent_info": {"main_intent": "transactional"},
                        "language_code": "tr",
                        "location_code": 2792,
                    },
                    {
                        "keyword": "kw-gamma",
                        "keyword_info": {
                            "search_volume": 5400,
                            "competition": 0.20,
                            "competition_level": "LOW",
                            "cpc": 0.65,
                        },
                        "search_intent_info": {"main_intent": "informational"},
                        "language_code": "tr",
                        "location_code": 2792,
                    },
                ],
            }],
        }],
    }


@pytest.fixture
def volume_payload_tr_correct() -> dict:
    """Mock Google Ads search_volume response (workaround B alt endpoint),
    locale honoured.
    """
    return {
        "tasks": [{
            "data": {"location_code": 2792, "language_code": "tr"},
            "result": [{
                "location_code": 2792,
                "language_code": "tr",
                "items": [
                    {"keyword": "kw-alpha",
                     "search_volume": 12100, "competition": "MEDIUM",
                     "competition_level": "MEDIUM", "cpc": 1.05,
                     "language_code": "tr", "location_code": 2792},
                    {"keyword": "kw-beta",
                     "search_volume": 8100, "competition": "HIGH",
                     "competition_level": "HIGH", "cpc": 2.30,
                     "language_code": "tr", "location_code": 2792},
                    {"keyword": "kw-gamma",
                     "search_volume": 5400, "competition": "LOW",
                     "competition_level": "LOW", "cpc": 0.65,
                     "language_code": "tr", "location_code": 2792},
                ],
            }],
        }],
    }


# ---------------------------------------------------------------------------
# Test (a) — Frontmatter parse + schema validate (PRESERVED)
# ---------------------------------------------------------------------------

def test_frontmatter_validates_against_schema(
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must validate against
    schemas/skill-frontmatter.schema.json (Draft 7).
    """
    text = SKILL_MD.read_text("utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "SKILL.md must open with --- frontmatter ---"
    fm = yaml.safe_load(parts[1])

    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm),
                  key=lambda e: list(e.absolute_path))
    assert not errs, (
        "frontmatter invalid: "
        f"{[('/'.join(str(p) for p in e.absolute_path) or '<root>', e.message) for e in errs]}"
    )

    # Brief-mandated values.
    assert fm["category"] == "ingestion"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["budget"]["uses_paid_mcp"] is True
    assert fm["budget"]["estimated_credits"] > 0
    # Required MCP tools present.
    req = fm["mcp_tools"]["required"]
    assert "mcp__dataforseo__keywords_data_google_ads_search_volume" in req
    assert "mcp__dataforseo__dataforseo_labs_google_keyword_overview" in req


# ---------------------------------------------------------------------------
# Test (b) — _normalize_dfs_response: tolerate REST + flat shapes,
#                                     reject the rest. Parametrized.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "case,raw,expected",
    [
        (
            "rest_envelope",
            {"tasks": [{"result": [{"items": [{"keyword": "a"}]}]}]},
            [{"keyword": "a"}],
        ),
        (
            "flat_wrapper",
            {"items": [{"keyword": "a"}]},
            [{"keyword": "a"}],
        ),
    ],
)
def test_normalize_dfs_response_tolerates_known_shapes(
    case: str, raw: dict, expected: list,
) -> None:
    """Both the REST envelope (tasks[0].result[0].items) and the flat
    wrapper ({"items": [...]}) must normalise to the same list-of-dicts.
    Live confirmed shapes (D-003 root-cause fix).
    """
    items = dfs_pull._normalize_dfs_response(raw)
    assert items == expected, f"case={case!r} produced {items!r}"


def test_normalize_dfs_response_unrecognized_shape_raises() -> None:
    """Inputs that match neither known DFS shape must raise ValueError
    with a message containing 'Unrecognized DFS response shape'."""
    with pytest.raises(ValueError) as ei:
        dfs_pull._normalize_dfs_response({"foo": "bar"})
    assert "Unrecognized DFS response shape" in str(ei.value)


# ---------------------------------------------------------------------------
# Test (c) — Transform unit: TR-correct fixture → keyword_overview staging
# ---------------------------------------------------------------------------

def test_transform_tr_correct_payload(
    overview_payload_tr_correct: dict,
    volume_payload_tr_correct: dict,
    tmp_path: Path,
) -> None:
    """Happy path: payload honors TR, transform emits a keyword_overview
    staging payload AND a search_volume staging payload. write_staging
    persists each to ``_state/staging/dfs_{tool}_{date}_{slug}.json``.
    """
    project_slug = "p-test"
    out = dfs_pull.transform(
        overview_payload_tr_correct,
        raw_volume=volume_payload_tr_correct,
        project_slug=project_slug,
        location_code=2792,
        language_code="tr",
    )

    # In-memory shape: keyword_overview AND search_volume staging tables.
    ov = out["keyword_overview"]
    vol = out["search_volume"]
    assert ov is not None and vol is not None
    assert ov["row_count"] == 3
    assert vol["row_count"] == 3
    assert ov["schema_version"] == dfs_pull.STAGING_SCHEMA_VERSION
    assert ov["tool"] == "keyword_overview"
    assert vol["tool"] == "search_volume"
    assert ov["project_slug"] == project_slug
    # Columns lock — no extra/missing keys.
    assert tuple(ov["columns"]) == dfs_pull.KEYWORD_OVERVIEW_COLUMNS
    assert tuple(vol["columns"]) == dfs_pull.SEARCH_VOLUME_COLUMNS

    # Per-row invariants: id monotonic from 1, content_hash sha256:hex.
    for idx, row in enumerate(ov["rows"], start=1):
        assert row["id"] == idx
        assert isinstance(row["content_hash"], str)
        assert row["content_hash"].startswith("sha256:")
        # exact column projection — staging-shape lock.
        assert set(row.keys()) == set(dfs_pull.KEYWORD_OVERVIEW_COLUMNS)
        # locale honoured.
        assert row["language_code"] == "tr"
        assert row["location_code"] == 2792

    # Persist to staging directory under tmp_path/_state/staging/.
    staging_dir = tmp_path / "_state" / "staging"
    written = dfs_pull.write_staging(
        out,
        staging_dir=staging_dir,
        project_slug=project_slug,
        date="2026-05-01",
    )
    assert "keyword_overview" in written
    assert "search_volume" in written

    ov_path = Path(written["keyword_overview"])
    assert ov_path.exists()
    assert ov_path.name == dfs_pull.staging_filename(
        tool="keyword_overview", date="2026-05-01", project_slug=project_slug,
    )
    # File round-trip: bytes match the in-memory payload.
    on_disk = json.loads(ov_path.read_text("utf-8"))
    assert on_disk == ov

    vol_path = Path(written["search_volume"])
    assert vol_path.exists()
    assert json.loads(vol_path.read_text("utf-8")) == vol

    # IMPORTANT: no master.xlsx written.
    assert not (tmp_path / "master.xlsx").exists()


# ---------------------------------------------------------------------------
# Test (d) — Staging columns are the SSoT for dfs-pull (NOT master schema).
#            (Renamed semantics: D-003 staging-only.)
# ---------------------------------------------------------------------------

def test_transform_columns_match_master_schema(
    overview_payload_tr_correct: dict,
) -> None:
    """Under D-003 (staging-only), the column SSoT is the dfs_pull module
    constants (KEYWORD_OVERVIEW_COLUMNS / SEARCH_VOLUME_COLUMNS) — these
    are the contract the cluster-map skill consumes from staging JSON.

    Test name preserved for diff-traceability; semantics updated: we no
    longer cross-check master-excel.schema (cluster_keywords/opportunity
    are produced downstream by cluster-map, not by dfs-pull).
    """
    out = dfs_pull.transform(
        overview_payload_tr_correct,
        project_slug="p-test",
        location_code=2792,
        language_code="tr",
    )

    ov = out["keyword_overview"]
    assert ov is not None

    # Module constants are sealed: id + content_hash + envelope fields
    # mirror scrapling-ops staging-table conventions.
    expected_overview = {
        "id", "keyword", "search_volume", "cpc", "competition",
        "competition_level", "search_intent", "language_code",
        "location_code", "content_hash", "fetched_at",
    }
    assert set(dfs_pull.KEYWORD_OVERVIEW_COLUMNS) == expected_overview

    expected_volume = {
        "id", "keyword", "search_volume", "cpc", "competition",
        "competition_level", "language_code", "location_code",
        "content_hash", "fetched_at",
    }
    assert set(dfs_pull.SEARCH_VOLUME_COLUMNS) == expected_volume

    # Each emitted row carries exactly the staging columns, nothing more.
    for row in ov["rows"]:
        assert set(row.keys()) == set(dfs_pull.KEYWORD_OVERVIEW_COLUMNS)


# ---------------------------------------------------------------------------
# Test (e) — TR workaround method tests (the 1835229 bug fixture)  PRESERVED
# ---------------------------------------------------------------------------

def test_tr_workaround_detects_us_drift(
    overview_payload_us_drift: dict,
    overview_payload_tr_correct: dict,
) -> None:
    """The wrapper bug returns location_code=2840/lang='en' even when
    2792/'tr' was requested. response_honors_tr() must:
      - return False for the drifted (US) payload,
      - return True for the workaround-C HTTP-bypass payload.
    """
    served_loc, served_lang = dfs_pull.detect_response_locale(overview_payload_us_drift)
    assert served_loc == 2840
    assert served_lang == "en"

    assert dfs_pull.response_honors_tr(
        overview_payload_us_drift,
        expected_location=2792, expected_language="tr",
    ) is False

    assert dfs_pull.response_honors_tr(
        overview_payload_tr_correct,
        expected_location=2792, expected_language="tr",
    ) is True

    # Workaround C HTTP body builder.
    body = dfs_pull.build_http_payload_tr(
        keywords=["kw-alpha"], location_code=2792, language_code="tr",
    )
    assert isinstance(body, list) and len(body) == 1
    assert body[0]["location_code"] == 2792
    assert body[0]["language_code"] == "tr"

    # Workaround A heuristic filter: drops obviously-non-TR rows.
    rows = [
        {"keyword": "kw-tr",  "language_code": "tr"},
        {"keyword": "kw-en",  "language_code": "en"},   # filtered out
        {"keyword": "kw-no-evidence"},                  # kept (no neg evidence)
    ]
    kept = dfs_pull.filter_to_tr_heuristic(rows)
    kept_kw = {r["keyword"] for r in kept}
    assert "kw-tr" in kept_kw
    assert "kw-no-evidence" in kept_kw
    assert "kw-en" not in kept_kw


# ---------------------------------------------------------------------------
# Test (f) — Budget pre-flight integration (FIRST paid skill)  PRESERVED
# ---------------------------------------------------------------------------

def test_budget_preflight_integration(tmp_path: Path) -> None:
    """estimate_credits() > 0 triggers preflight_budget(). When projected
    usage stays under budget → returns envelope. When projected > budget →
    BudgetError DURUR.
    """
    # Estimate: 10 keywords × (1.0 + 0.5) = 15 credits.
    est = dfs_pull.estimate_credits(10)
    assert est == 15.0

    # PASS path: budget=500, no prior usage, estimate=15 → projected=15.
    cfg_path = tmp_path / "project.config.json"
    cfg_path.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 500}
    }))
    events_path = tmp_path / "events.jsonl"
    envelope = dfs_pull.preflight_budget(
        estimated_credits=est,
        project_config_path=cfg_path,
        events_path=events_path,
    )
    assert envelope["exceeded"] is False
    assert envelope["budget_per_day"] == 500
    assert envelope["projected_used"] == 15.0
    assert envelope["remaining_after"] == 485.0

    # FAIL path: budget=10, estimate=15 → projected=15 > 10.
    cfg_low = tmp_path / "project-config-low.json"
    cfg_low.write_text(json.dumps({
        "dataforseo": {"budget_credits_per_day": 10}
    }))
    with pytest.raises(dfs_pull.BudgetError):
        dfs_pull.preflight_budget(
            estimated_credits=est,
            project_config_path=cfg_low,
            events_path=events_path,
        )


# ---------------------------------------------------------------------------
# Test (g) — DURUR fired: TR workaround all-fail + missing creds + drift
# ---------------------------------------------------------------------------

def test_durur_conditions_fire(
    overview_payload_us_drift: dict,
    overview_payload_tr_correct: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DURUR coverage (D-003 staging-only):
      #4: TR workaround all-fail → TrWorkaroundFailed when transform sees
          a non-TR payload and skip_tr_check=False.
      #5: Staging payload drift → StagingSchemaError.
      #8: DATAFORSEO_USERNAME / DATAFORSEO_PASSWORD missing →
          CredentialError on http_credentials_from_env().
      Subclass invariant: every raised error inherits from DfsPullError.
    """
    # #4 — transform refuses to silently emit US data.
    with pytest.raises(dfs_pull.TrWorkaroundFailed) as ei4:
        dfs_pull.transform(
            overview_payload_us_drift,
            project_slug="p-test",
            location_code=2792, language_code="tr",
            skip_tr_check=False,
        )
    assert isinstance(ei4.value, dfs_pull.DfsPullError)

    # Caller can opt in via skip_tr_check=True after running A/B/C — then
    # transform proceeds with what's in the (drifted) payload.
    out = dfs_pull.transform(
        overview_payload_us_drift,
        project_slug="p-test",
        location_code=2792, language_code="tr",
        skip_tr_check=True,
    )
    assert out["keyword_overview"]["row_count"] == 1   # one item in drift fixture

    # #5 — StagingSchemaError when handing a malformed payload to
    # write_staging (defensive re-validation must catch drift before disk).
    bad_payload = {
        "keyword_overview": {
            "schema_version": "1.0",
            "tool": "keyword_overview",
            "project_slug": "p-test",
            "fetched_at": "2026-05-01T00:00:00.000000+00:00",
            "row_count": 1,
            # Drift: columns don't match KEYWORD_OVERVIEW_COLUMNS.
            "columns": ["id", "keyword"],
            "rows": [{"id": 1, "keyword": "kw"}],
        },
        "search_volume": None,
    }
    with pytest.raises(dfs_pull.StagingSchemaError) as ei5:
        dfs_pull.write_staging(
            bad_payload,
            staging_dir=tmp_path / "_state" / "staging",
            project_slug="p-test",
            date="2026-05-01",
        )
    assert isinstance(ei5.value, dfs_pull.DfsPullError)

    # #8 — credentials missing.
    monkeypatch.delenv("DATAFORSEO_USERNAME", raising=False)
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)
    with pytest.raises(dfs_pull.CredentialError) as ei8:
        dfs_pull.http_credentials_from_env()
    assert isinstance(ei8.value, dfs_pull.DfsPullError)

    # #8 happy: both set.
    monkeypatch.setenv("DATAFORSEO_USERNAME", "test@example.com")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "redacted")
    user, pwd = dfs_pull.http_credentials_from_env()
    assert user == "test@example.com"
    assert pwd == "redacted"


# ---------------------------------------------------------------------------
# Test (h) — Smoke E2E: staging file written + provenance event (null sheet)
# ---------------------------------------------------------------------------

def test_smoke_e2e_with_mock(
    tmp_path: Path,
    overview_payload_tr_correct: dict,
    volume_payload_tr_correct: dict,
    events_schema: dict,
) -> None:
    """End-to-end smoke (staging-only flow):
      1. transform() mock TR payload → keyword_overview + search_volume
         staging dicts.
      2. write_staging() persists each to
         tmp_path/_state/staging/dfs_{tool}_{date}_{slug}.json.
      3. _validate_staging_payload accepts each on-disk file (no drift).
      4. events_writer.append_provenance emits a dataforseo_mcp event
         with target_excel_sheet=null (staging-only mode).
      5. The emitted event validates against schemas/events.schema.json.
    """
    project_slug = "p-test"
    date_str = "2026-05-01"

    # Step 1+2 — transform → staging payload → write to disk.
    out = dfs_pull.transform(
        overview_payload_tr_correct,
        raw_volume=volume_payload_tr_correct,
        project_slug=project_slug,
        location_code=2792,
        language_code="tr",
    )

    project_dir = tmp_path / "projects" / project_slug
    state_dir = project_dir / "_state"
    staging_dir = state_dir / "staging"
    state_dir.mkdir(parents=True, exist_ok=True)

    written = dfs_pull.write_staging(
        out,
        staging_dir=staging_dir,
        project_slug=project_slug,
        date=date_str,
    )

    ov_path = Path(written["keyword_overview"])
    vol_path = Path(written["search_volume"])
    assert ov_path.exists()
    assert vol_path.exists()
    # Filename convention.
    assert ov_path.name == f"dfs_keyword_overview_{date_str}_{project_slug}.json"
    assert vol_path.name == f"dfs_search_volume_{date_str}_{project_slug}.json"
    # Files live under the canonical staging path.
    assert staging_dir in ov_path.parents

    # Step 3 — re-validate on-disk JSON shape (defensive — should not raise).
    on_disk_ov = json.loads(ov_path.read_text("utf-8"))
    dfs_pull._validate_staging_payload(
        on_disk_ov, columns=dfs_pull.KEYWORD_OVERVIEW_COLUMNS,
    )
    on_disk_vol = json.loads(vol_path.read_text("utf-8"))
    dfs_pull._validate_staging_payload(
        on_disk_vol, columns=dfs_pull.SEARCH_VOLUME_COLUMNS,
    )

    # IMPORTANT: no master.xlsx written. Cluster-map (Phase 8) is the
    # downstream consumer that lifts staging JSON into Excel.
    assert not (project_dir / "master.xlsx").exists()

    # Step 4 — provenance event with source.kind=dataforseo_mcp and
    # target_excel_sheet=null (staging-only ⇒ no Excel write).
    rid = events_writer.next_run_id(project_slug, workspace_root=tmp_path)
    response_bytes = len(json.dumps(overview_payload_tr_correct))
    result = events_writer.append_provenance(
        project_id=project_slug,
        run_id=rid,
        source={
            "kind": "dataforseo_mcp",
            "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_overview",
            "response_bytes": response_bytes,
            "row_count": out["keyword_overview"]["row_count"],
        },
        operation="ingest",
        target_table="dfs_keyword_overview",
        target_excel_sheet=None,
        rows_written=0,         # staging-only: no Excel rows yet.
        cost={
            "provider": "dataforseo",
            "credits": 4.5,     # 3 keywords × 1.5 (overview + volume)
            "budget_key": "project.config.dataforseo.budget_credits_per_day",
        },
        workspace_root=tmp_path,
    )
    assert result.event_id

    # Read back events.jsonl and pick the dataforseo_mcp provenance entry.
    events_path = state_dir / "events.jsonl"
    lines = [
        json.loads(line)
        for line in events_path.read_text("utf-8").splitlines()
        if line.strip()
    ]
    dfs_provs = [
        e for e in lines
        if e.get("event_kind") == "provenance"
        and e.get("source", {}).get("kind") == "dataforseo_mcp"
    ]
    assert dfs_provs, (
        "no provenance event_kind=provenance source.kind=dataforseo_mcp emitted"
    )

    evt = dfs_provs[-1]
    # Staging-only invariants.
    assert evt["target_excel_sheet"] is None, (
        "staging-only: target_excel_sheet must be null until cluster-map runs"
    )
    assert evt["source"]["kind"] == "dataforseo_mcp"
    assert evt["operation"] == "ingest"

    # Step 5 — re-validate against the canonical events schema (Draft 7).
    validator = Draft7Validator(events_schema)
    for e in dfs_provs:
        errs = sorted(validator.iter_errors(e),
                      key=lambda err: list(err.absolute_path))
        assert not errs, (
            "emitted dataforseo_mcp provenance event invalid: "
            f"{[(list(err.absolute_path), err.message) for err in errs]}"
        )
