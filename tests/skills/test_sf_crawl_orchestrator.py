"""
tests/skills/test_sf_crawl_orchestrator.py — sf-crawl-orchestrator skill tests.

10 functional cases per v1.8 Phase 3 Worker Prompt: 1 happy path
(24 reports) + 8 DURUR cases (orch-1..orch-8) + 1 sf-import handoff
success. The skill body lives in markdown (Claude executes it
conversationally); these tests simulate the body's control flow with
mocked ``mcp__sf__sf_*`` wrappers and the real ``workflow_runner`` /
``events_writer`` / ``sf_crawl_orchestrator`` helpers, exercising the
contract: which workflow_runner transitions fire, which failure codes
land, which artifacts get written.

A bonus 11th test validates the SKILL.md frontmatter against
``schemas/skill-frontmatter.schema.json`` (spec mandate even though
Manager's prompt enumeration listed 10 functional cases — Worker Open
Question Q-PHASE-3-WORKER-01 surfaces the +1 deviation).

Cross-module IMPORT-only discipline:
  - scripts.state.workflow_runner   — real state machine, no mocks
  - scripts.state.events_writer     — real provenance emission
  - scripts.ingestion.sf_crawl_orchestrator — pure transform helpers
  - scripts.ingestion.sf_import     — only TIER1_REQUIRED frozenset
    is imported (for tier membership assertions); skill body is NOT
    invoked here (subprocess mocked in handoff test).

Schemas referenced:
  - schemas/skill-frontmatter.schema.json (frontmatter validation)
  - schemas/sf-required-reports.schema.json (24-report enumeration SSoT)

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_sf_crawl_orchestrator.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.ingestion import sf_crawl_orchestrator
from scripts.ingestion.sf_import import TIER1_REQUIRED, TIER2_RECOMMENDED
from scripts.state import events_writer, workflow_runner


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_MD = REPO_ROOT / "skills" / "ingestion" / "sf-crawl-orchestrator" / "SKILL.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Set up a minimal workspace with a single project + sf-scratch dir."""
    slug = "test-proj"
    proj_dir = tmp_path / "projects" / slug
    state_dir = proj_dir / "_state" / "workflows"
    state_dir.mkdir(parents=True, exist_ok=True)
    sf_scratch = tmp_path / "sf-scratch"
    sf_scratch.mkdir()

    config = {
        "schema_version": "1.5",
        "project_id": slug,
        "domain": "https://example.com",
        "sf": {
            "mcp": {
                "enabled": True,
                "url": "http://127.0.0.1:11435/mcp",
                "allowed_directory": str(sf_scratch),
                "crawl_config_path": None,
                "max_wait_minutes": 180,
                "per_report_timeout_seconds": 300,
            }
        },
    }
    (proj_dir / "project.config.json").write_text(json.dumps(config), "utf-8")
    return tmp_path


def _project_config(workspace: Path, slug: str = "test-proj") -> dict:
    return json.loads(
        (workspace / "projects" / slug / "project.config.json").read_text("utf-8")
    )


# ---------------------------------------------------------------------------
# Mock MCP wrappers — bound at call sites via patch where the body would
# invoke `mcp__sf__sf_*`. For these tests we expose them as plain callables.
# ---------------------------------------------------------------------------

class MockSfMcp:
    """Holds the per-test mock callbacks for the SF MCP tools.

    The 24-report export fans out across the THREE real SF export tools
    (``sf_generate_report`` / ``sf_generate_bulk_export`` /
    ``sf_export_seo_element_urls``) per ``build_export_plan`` — there is no
    single ``generate_report(crawl_id, report_name)`` tool. All three default
    to a shared ``export`` callback (keyed on ``file_path=f"{canonical}.csv"``),
    so a test that only cares about success/failure sets ``export=`` once; a
    test that needs per-canonical behaviour inspects ``kw["file_path"]``.
    """

    def __init__(
        self,
        *,
        allowed_dir: Callable[..., Any] = None,
        list_crawls: Callable[..., Any] = None,
        crawl: Callable[..., Any] = None,
        crawl_progress: Callable[..., Any] = None,
        export: Callable[..., Any] = None,
        generate_report: Callable[..., Any] = None,
        generate_bulk_export: Callable[..., Any] = None,
        export_seo_element_urls: Callable[..., Any] = None,
    ) -> None:
        self.allowed_dir = allowed_dir
        self.list_crawls = list_crawls
        self.crawl = crawl
        self.crawl_progress = crawl_progress
        # Default: a tool-agnostic success keyed on file_path. The 3 real SF
        # export tools route to it unless a test overrides a specific one.
        default_export = export or (lambda **kw: {"saved_path": kw.get("file_path")})
        self.generate_report = generate_report or default_export
        self.generate_bulk_export = generate_bulk_export or default_export
        self.export_seo_element_urls = export_seo_element_urls or default_export


# ---------------------------------------------------------------------------
# Body simulator — mirrors the SKILL.md 9-step protocol with mocked MCPs.
# Returns a result dict with crawl_id, exported, amber_warnings, run_id,
# target_raw. Raises SystemExit(2) on DURUR (mirrors body's raise
# SystemExit(2) after workflow_runner.fail).
# ---------------------------------------------------------------------------

def _run_orchestrator(
    *,
    project_slug: str,
    workspace_root: Path,
    mcp: MockSfMcp,
    project_config: dict,
    include_tier3: bool = False,
    create_real_csvs: bool = True,
    subprocess_returncode: int = 0,
    subprocess_stderr: str = "",
) -> dict:
    """Walk the orchestrator body protocol with mocked MCP wrappers.

    NOTE: this simulator INTENTIONALLY does not invoke the real subprocess
    call to sf_import — the handoff test patches subprocess.run separately.
    Step 5 drives the REAL export contract: build_export_plan() + the 3-tool
    dispatch (sf_generate_report / sf_generate_bulk_export /
    sf_export_seo_element_urls) with NDJSON→CSV conversion, no crawl_id/
    report_name kwargs. It approximates the body's control flow rather than
    reproducing every line verbatim.
    """
    import time as _time

    # Step 1 — create_run (no resume in these tests).
    handle = workflow_runner.create_run(
        skill="sf-crawl-orchestrator",
        project_slug=project_slug,
        steps=[
            {"name": "preflight"},
            {"name": "crawl_trigger"},
            {"name": "poll"},
            {"name": "export_24_reports"},
            {"name": "atomic_move"},
            {"name": "invoke_sf_import"},
            {"name": "emit_provenance_and_report"},
        ],
        workspace_root=workspace_root,
    )

    # Step 2 — preflight (orch-1, orch-2, orch-4, orch-7).
    workflow_runner.start_step(handle.run_id, 0,
                               project_slug=project_slug,
                               workspace_root=workspace_root)
    try:
        allowed_resp = mcp.allowed_dir()
    except Exception as exc:
        tag = "DURUR-orch-2" if "IllegalStateException" in str(exc) else "DURUR-orch-1"
        workflow_runner.fail(
            handle.run_id, project_slug=project_slug,
            code="mcp_error",
            message=f"{tag} allowed_base_directory probe failed: {exc}",
            step_index=0, workspace_root=workspace_root,
        )
        raise SystemExit(2)

    mcp_allowed = (
        allowed_resp.get("allowed_directory")
        if isinstance(allowed_resp, dict)
        else str(allowed_resp)
    )
    expected_allowed = project_config["sf"]["mcp"]["allowed_directory"]
    if expected_allowed and mcp_allowed != expected_allowed:
        workflow_runner.fail(
            handle.run_id, project_slug=project_slug,
            code="validation_error",
            message=f"DURUR-orch-4 mismatch mcp={mcp_allowed} expected={expected_allowed}",
            step_index=0, workspace_root=workspace_root,
        )
        raise SystemExit(2)

    list_resp = mcp.list_crawls()
    in_progress = [
        c for c in list_resp.get("crawls", [])
        if c.get("status") == "IN_PROGRESS"
    ]
    if in_progress:
        workflow_runner.fail(
            handle.run_id, project_slug=project_slug,
            code="mcp_error",
            message=f"DURUR-orch-7 IN_PROGRESS crawls: {[c.get('crawl_id') for c in in_progress]}",
            step_index=0, workspace_root=workspace_root,
        )
        raise SystemExit(2)

    workflow_runner.finish_step(handle.run_id, 0,
                                project_slug=project_slug,
                                workspace_root=workspace_root,
                                output_ref=f"allowed_directory={mcp_allowed}")

    # Step 3 — crawl_trigger.
    workflow_runner.start_step(handle.run_id, 1,
                               project_slug=project_slug,
                               workspace_root=workspace_root)
    crawl_resp = mcp.crawl(url=project_config["domain"])
    crawl_id = crawl_resp["crawl_id"]
    workflow_runner.finish_step(handle.run_id, 1,
                                project_slug=project_slug,
                                workspace_root=workspace_root,
                                output_ref=f"crawl_id={crawl_id}")

    # Step 4 — poll (orch-3 timeout / failed terminal).
    workflow_runner.start_step(handle.run_id, 2,
                               project_slug=project_slug,
                               workspace_root=workspace_root)
    max_wait_sec = int(project_config["sf"]["mcp"]["max_wait_minutes"]) * 60
    poll_interval = 60
    elapsed = 0
    final_state = None
    with patch.object(_time, "sleep", lambda _x: None):
        while elapsed <= max_wait_sec:
            raw = mcp.crawl_progress(crawl_id=crawl_id)
            state = sf_crawl_orchestrator.parse_progress_response(raw)
            if state.status in ("DONE", "FAILED"):
                final_state = state
                break
            _time.sleep(poll_interval)
            elapsed += poll_interval

    if final_state is None or final_state.status == "FAILED":
        # DURUR-orch-3: timeout variant vs terminal-failed variant.
        code = "timeout" if final_state is None else "mcp_error"
        tag = "timeout" if final_state is None else "FAILED"
        workflow_runner.fail(
            handle.run_id, project_slug=project_slug,
            code=code,
            message=f"DURUR-orch-3 poll ended with state={tag}",
            step_index=2, workspace_root=workspace_root,
        )
        raise SystemExit(2)

    workflow_runner.finish_step(handle.run_id, 2,
                                project_slug=project_slug,
                                workspace_root=workspace_root,
                                output_ref=f"urls_crawled={final_state.urls_crawled}")

    # Step 5 — export_24_reports: drive from build_export_plan() and dispatch
    # each spec to one of the THREE real SF export tools (no crawl_id /
    # report_name kwargs — that single-tool form does not exist). seo-element
    # exports arrive as NDJSON and are converted to CSV in place before the
    # atomic move, so sf_import sees a uniform CSV raw/ set. orch-8: a Tier 1
    # export failure rolls back the temp staging.
    import shutil
    workflow_runner.start_step(handle.run_id, 3,
                               project_slug=project_slug,
                               workspace_root=workspace_root)
    export_plan = sf_crawl_orchestrator.build_export_plan(include_tier3=include_tier3)
    temp_staging = (
        workspace_root / "projects" / project_slug / "_state" / "staging"
        / f"sf-crawl-{handle.run_id}"
    )
    temp_staging.mkdir(parents=True, exist_ok=True)

    amber_warnings: list[str] = []
    exported: list[str] = []
    sf_scratch = Path(mcp_allowed)
    # spec.tool → the mock's wrapper (mirrors the body's SF_EXPORT_TOOLS map).
    tool_fns = {
        "sf_generate_report": mcp.generate_report,
        "sf_generate_bulk_export": mcp.generate_bulk_export,
        "sf_export_seo_element_urls": mcp.export_seo_element_urls,
    }

    for spec in export_plan:
        rel_path = f"{spec.canonical}.csv"
        try:
            tool_fn = tool_fns[spec.tool]
            tool_fn(file_path=rel_path, **spec.call_kwargs)  # NO crawl_id/report_name
            if create_real_csvs:
                src = sf_scratch / rel_path
                if sf_crawl_orchestrator.export_returns_ndjson(spec):
                    # seo-element tool writes NDJSON even to a .csv path;
                    # convert in place so raw/ is uniform CSV (body Step 5).
                    src.write_text(
                        f'{{"address": "https://example.com/{spec.canonical}", '
                        f'"status_code": 200}}\n',
                        encoding="utf-8",
                    )
                    src.write_text(
                        sf_crawl_orchestrator.ndjson_to_csv(src.read_text("utf-8")),
                        encoding="utf-8",
                    )
                else:
                    src.write_text(f"col_a,col_b\n{spec.canonical},ok\n", "utf-8")
                dst = temp_staging / rel_path
                sf_crawl_orchestrator.move_with_rollback(src, dst)
            exported.append(spec.canonical)
        except Exception as exc:
            if spec.tier == "tier1":
                shutil.rmtree(temp_staging, ignore_errors=True)
                workflow_runner.fail(
                    handle.run_id, project_slug=project_slug,
                    code="mcp_error",
                    message=f"DURUR-orch-8 Tier 1 {spec.canonical!r} failed: {exc}",
                    step_index=3, workspace_root=workspace_root,
                )
                raise SystemExit(2)  # D-SF-16 atomic rollback
            amber_warnings.append(f"Tier 2 {spec.canonical!r}: {exc}")

    workflow_runner.finish_step(handle.run_id, 3,
                                project_slug=project_slug,
                                workspace_root=workspace_root,
                                output_ref=f"exported={len(exported)}")

    # Step 6 — atomic_move (orch-5 conflict / orch-6 move fail).
    import datetime
    workflow_runner.start_step(handle.run_id, 4,
                               project_slug=project_slug,
                               workspace_root=workspace_root)
    today = datetime.date.today().isoformat()
    target_raw = (
        workspace_root / "projects" / project_slug / "sf-exports"
        / today / "raw"
    )
    if target_raw.exists():
        workflow_runner.fail(
            handle.run_id, project_slug=project_slug,
            code="validation_error",
            message=f"DURUR-orch-5 already exists: {target_raw}",
            step_index=4, workspace_root=workspace_root,
        )
        raise SystemExit(2)

    target_raw.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(temp_staging), str(target_raw))
    except Exception as exc:
        workflow_runner.fail(
            handle.run_id, project_slug=project_slug,
            code="internal_error",
            message=f"DURUR-orch-6 shutil.move failed: {exc}",
            step_index=4, workspace_root=workspace_root,
        )
        raise SystemExit(2)

    workflow_runner.finish_step(handle.run_id, 4,
                                project_slug=project_slug,
                                workspace_root=workspace_root,
                                output_ref=str(target_raw))

    # Step 7 — invoke_sf_import (mocked subprocess via test setup).
    workflow_runner.start_step(handle.run_id, 5,
                               project_slug=project_slug,
                               workspace_root=workspace_root)
    result = subprocess.run(
        ["python3", "-m", "scripts.ingestion.sf_import",
         "--project", project_slug,
         "--sf-export-path", str(target_raw.parent)],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        workflow_runner.fail(
            handle.run_id, project_slug=project_slug,
            code="internal_error",
            message=f"sf-import exit {result.returncode}: {result.stderr[:500]}",
            step_index=5, workspace_root=workspace_root,
        )
        raise SystemExit(2)
    workflow_runner.finish_step(handle.run_id, 5,
                                project_slug=project_slug,
                                workspace_root=workspace_root,
                                output_ref=f"sf_import_exit=0")

    # Step 8 — provenance + report.
    workflow_runner.start_step(handle.run_id, 6,
                               project_slug=project_slug,
                               workspace_root=workspace_root)
    events_writer.append_provenance(
        project_id=project_slug,
        run_id=events_writer.next_run_id(project_slug, workspace_root=workspace_root),
        source={
            "kind": "sf_mcp", "mcp_server": "sf",
            "mcp_tool": "sf__sf_generate_report",
            "response_bytes": 1024,  # representative; envelope size in body
            "row_count": len(exported),
        },
        operation="ingest",
        rows_written=len(exported),
        workspace_root=workspace_root,
    )
    workflow_runner.finish_step(handle.run_id, 6,
                                project_slug=project_slug,
                                workspace_root=workspace_root,
                                output_ref="provenance_emitted")

    # Step 9 — complete.
    workflow_runner.complete(handle.run_id,
                             project_slug=project_slug,
                             workspace_root=workspace_root,
                             outputs={
                                 "crawl_id": crawl_id,
                                 "reports_exported": str(len(exported)),
                                 "amber_warnings": str(len(amber_warnings)),
                             })

    return {
        "run_id": handle.run_id,
        "crawl_id": crawl_id,
        "exported": exported,
        "amber_warnings": amber_warnings,
        "target_raw": target_raw,
    }


# ---------------------------------------------------------------------------
# Helper to inspect workflow state after a DURUR raise
# ---------------------------------------------------------------------------

def _latest_workflow(workspace: Path, slug: str = "test-proj") -> dict:
    """Return the most recent workflow_runner state JSON for the project."""
    wf_dir = workspace / "projects" / slug / "_state" / "workflows"
    files = sorted(wf_dir.glob("*.json"))
    assert files, f"no workflow runs found under {wf_dir}"
    return json.loads(files[-1].read_text("utf-8"))


# ---------------------------------------------------------------------------
# Test 1 — happy path: 24 reports exported, sf-import handoff PASS
# ---------------------------------------------------------------------------

def test_happy_path_24_reports(workspace: Path) -> None:
    cfg = _project_config(workspace)
    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": cfg["sf"]["mcp"]["allowed_directory"]},
        list_crawls=lambda: {"crawls": []},
        crawl=lambda **kw: {"crawl_id": "happy-001"},
        crawl_progress=lambda **kw: {"progress": {"status": "DONE", "urls_crawled": 250}},
        # The 3 SF export tools default to success (keyed on file_path).
    )
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        result = _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    assert result["crawl_id"] == "happy-001"
    assert len(result["exported"]) == 24, f"expected 24, got {len(result['exported'])}"
    assert not result["amber_warnings"]
    assert result["target_raw"].is_dir(), "atomic move target must exist"
    # All 14 Tier 1 + 10 Tier 2 CSVs must be in the target raw dir.
    csvs = sorted(p.stem for p in result["target_raw"].iterdir() if p.suffix == ".csv")
    assert set(csvs) >= TIER1_REQUIRED
    assert set(csvs) >= TIER2_RECOMMENDED
    # raw/ must be UNIFORM CSV: the 16 seo-element reports SF emits as NDJSON
    # were converted (ndjson_to_csv) before the atomic move. A skipped
    # conversion would leave a bare JSON object line — assert none survive.
    import csv as _csv
    for p in result["target_raw"].iterdir():
        if p.suffix != ".csv":
            continue
        text = p.read_text("utf-8")
        assert not text.lstrip().startswith("{"), (
            f"{p.name} is raw NDJSON — ndjson_to_csv conversion was skipped"
        )
        parsed = list(_csv.reader(text.splitlines()))
        assert parsed and parsed[0], f"{p.name} has no CSV header row"
    # Final workflow status = done.
    state = _latest_workflow(workspace)
    assert state["status"] == "done"
    assert state["outputs"]["reports_exported"] == "24"


# ---------------------------------------------------------------------------
# Test 2 — DURUR-orch-1: GUI not responsive (allowed_dir raises)
# ---------------------------------------------------------------------------

def test_durur_orch_1_gui_not_responsive(workspace: Path) -> None:
    cfg = _project_config(workspace)

    def _raise(): raise ConnectionError("SF MCP unreachable")
    mcp = MockSfMcp(allowed_dir=_raise)

    with pytest.raises(SystemExit):
        _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "mcp_error"
    assert "DURUR-orch-1" in state["failure_reason"]["message"]
    assert "SF MCP unreachable" in state["failure_reason"]["message"]


# ---------------------------------------------------------------------------
# Test 3 — DURUR-orch-2: IllegalStateException (modal dialog)
# ---------------------------------------------------------------------------

def test_durur_orch_2_illegal_state_modal(workspace: Path) -> None:
    cfg = _project_config(workspace)

    def _raise(): raise RuntimeError("IllegalStateException: modal dialog open")
    mcp = MockSfMcp(allowed_dir=_raise)

    with pytest.raises(SystemExit):
        _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "mcp_error"
    # Body distinguishes orch-2 by inspecting the exception text for the
    # IllegalStateException token (SF GUI modal dialog signal).
    assert "DURUR-orch-2" in state["failure_reason"]["message"]
    assert "IllegalStateException" in state["failure_reason"]["message"]


# ---------------------------------------------------------------------------
# Test 4 — DURUR-orch-3: max_wait timeout
# ---------------------------------------------------------------------------

def test_durur_orch_3_poll_timeout(workspace: Path) -> None:
    cfg = _project_config(workspace)
    # Force the poll loop to spin past max_wait by always returning IN_PROGRESS.
    cfg["sf"]["mcp"]["max_wait_minutes"] = 1  # 60s; one iteration then timeout.
    # Patch the file so the body picks up the override.
    proj_cfg_path = workspace / "projects" / "test-proj" / "project.config.json"
    proj_cfg_path.write_text(json.dumps(cfg), "utf-8")

    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": cfg["sf"]["mcp"]["allowed_directory"]},
        list_crawls=lambda: {"crawls": []},
        crawl=lambda **kw: {"crawl_id": "timeout-001"},
        crawl_progress=lambda **kw: {"progress": {"status": "IN_PROGRESS", "urls_crawled": 10}},
    )

    with pytest.raises(SystemExit):
        _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "timeout"
    assert "DURUR-orch-3" in state["failure_reason"]["message"]


# ---------------------------------------------------------------------------
# Test 5 — DURUR-orch-4: allowed_directory mismatch
# ---------------------------------------------------------------------------

def test_durur_orch_4_allowed_dir_mismatch(workspace: Path) -> None:
    cfg = _project_config(workspace)
    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": "/wrong/path"},
        list_crawls=lambda: {"crawls": []},
    )

    with pytest.raises(SystemExit):
        _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "validation_error"
    assert "DURUR-orch-4" in state["failure_reason"]["message"]


# ---------------------------------------------------------------------------
# Test 6 — DURUR-orch-5: target sf-exports/{date}/raw/ already exists
# ---------------------------------------------------------------------------

def test_durur_orch_5_target_dir_conflict(workspace: Path) -> None:
    cfg = _project_config(workspace)
    # Pre-create the target directory so the body's check trips orch-5.
    import datetime
    today = datetime.date.today().isoformat()
    target = workspace / "projects" / "test-proj" / "sf-exports" / today / "raw"
    target.mkdir(parents=True)
    (target / "old_file.csv").write_text("stale", "utf-8")

    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": cfg["sf"]["mcp"]["allowed_directory"]},
        list_crawls=lambda: {"crawls": []},
        crawl=lambda **kw: {"crawl_id": "conflict-001"},
        crawl_progress=lambda **kw: {"progress": {"status": "DONE", "urls_crawled": 100}},
        # The 3 SF export tools default to success (keyed on file_path).
    )

    with pytest.raises(SystemExit):
        _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "validation_error"
    assert "DURUR-orch-5" in state["failure_reason"]["message"]


# ---------------------------------------------------------------------------
# Test 7 — DURUR-orch-6: file move failure (mocked shutil.move raises)
# ---------------------------------------------------------------------------

def test_durur_orch_6_file_move_fail(workspace: Path) -> None:
    cfg = _project_config(workspace)
    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": cfg["sf"]["mcp"]["allowed_directory"]},
        list_crawls=lambda: {"crawls": []},
        crawl=lambda **kw: {"crawl_id": "movefail-001"},
        crawl_progress=lambda **kw: {"progress": {"status": "DONE", "urls_crawled": 100}},
        # The 3 SF export tools default to success (keyed on file_path).
    )

    # We need the move from temp_staging → target_raw (Step 6) to fail, NOT
    # the per-report move in Step 5. Patch shutil.move only after the
    # 24 per-report moves succeed: target the body's Step 6 shutil.move call.
    real_move = __import__("shutil").move
    move_count = {"n": 0}

    def fake_move(src: str, dst: str) -> str:
        move_count["n"] += 1
        # The Step 5 per-report moves go through sf_crawl_orchestrator
        # .move_with_rollback (which calls shutil.move). Step 6's single
        # final move is the 25th invocation (after 24 per-report). Fail it.
        if move_count["n"] >= 25:
            raise OSError("simulated disk full")
        return real_move(src, dst)

    with patch("shutil.move", side_effect=fake_move):
        with pytest.raises(SystemExit):
            _run_orchestrator(
                project_slug="test-proj",
                workspace_root=workspace,
                mcp=mcp,
                project_config=cfg,
            )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "internal_error"
    assert "DURUR-orch-6" in state["failure_reason"]["message"]


# ---------------------------------------------------------------------------
# Test 8 — DURUR-orch-7: concurrent crawl detected (R13 mitigation)
# ---------------------------------------------------------------------------

def test_durur_orch_7_concurrent_crawl(workspace: Path) -> None:
    cfg = _project_config(workspace)
    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": cfg["sf"]["mcp"]["allowed_directory"]},
        list_crawls=lambda: {"crawls": [{"crawl_id": "other-running", "status": "IN_PROGRESS"}]},
    )

    with pytest.raises(SystemExit):
        _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "mcp_error"
    assert "DURUR-orch-7" in state["failure_reason"]["message"]


# ---------------------------------------------------------------------------
# Test 9 — DURUR-orch-8: Tier 1 export fail → atomic rollback (D-SF-16)
# ---------------------------------------------------------------------------

def test_durur_orch_8_tier1_export_fail_rollback(workspace: Path) -> None:
    cfg = _project_config(workspace)

    # Pick a deterministic Tier 1 canonical to fail. The 3-tool dispatch passes
    # file_path=f"{canonical}.csv" + call_kwargs — there is NO report_name arg,
    # so the mock keys the failure on file_path.
    fail_target = sorted(TIER1_REQUIRED)[0]
    fail_rel = f"{fail_target}.csv"

    def failing_export(**kw: Any) -> dict:
        if kw.get("file_path") == fail_rel:
            raise RuntimeError(f"SF MCP rejected {fail_target}")
        return {"saved_path": kw.get("file_path")}

    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": cfg["sf"]["mcp"]["allowed_directory"]},
        list_crawls=lambda: {"crawls": []},
        crawl=lambda **kw: {"crawl_id": "rollback-001"},
        crawl_progress=lambda **kw: {"progress": {"status": "DONE", "urls_crawled": 100}},
        export=failing_export,
    )

    with pytest.raises(SystemExit):
        _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    state = _latest_workflow(workspace)
    assert state["status"] == "failed"
    assert state["failure_reason"]["code"] == "mcp_error"
    assert "DURUR-orch-8" in state["failure_reason"]["message"]
    # D-SF-16 atomic rollback: temp staging must be deleted.
    staging_root = (
        workspace / "projects" / "test-proj" / "_state" / "staging"
    )
    if staging_root.exists():
        leftovers = list(staging_root.iterdir())
        assert not leftovers, f"D-SF-16 rollback violated: {leftovers}"


# ---------------------------------------------------------------------------
# Test 10 — sf-import handoff success (subprocess returns 0)
# ---------------------------------------------------------------------------

def test_sf_import_handoff_success(workspace: Path) -> None:
    cfg = _project_config(workspace)
    mcp = MockSfMcp(
        allowed_dir=lambda: {"allowed_directory": cfg["sf"]["mcp"]["allowed_directory"]},
        list_crawls=lambda: {"crawls": []},
        crawl=lambda **kw: {"crawl_id": "handoff-001"},
        crawl_progress=lambda **kw: {"progress": {"status": "DONE", "urls_crawled": 100}},
        # The 3 SF export tools default to success (keyed on file_path).
    )

    with patch("subprocess.run") as mock_sub:
        # Simulate sf-import subprocess returning success. The orchestrator must
        # invoke sf_import with ONLY the real CLI flags — NO --source-run-id
        # (sf_import argparse would exit 2); provenance chains via sf-import's
        # source_run_id *frontmatter* input, not a script flag.
        def _run_side_effect(*args, **kwargs):
            call_args = args[0]
            assert "--source-run-id" not in call_args, \
                "orchestrator must NOT pass --source-run-id (sf_import CLI rejects it, argparse exit 2; provenance chains via sf-import's source_run_id frontmatter input)"
            assert "--project" in call_args and "--sf-export-path" in call_args, \
                "orchestrator must invoke sf_import with --project + --sf-export-path"
            return subprocess.CompletedProcess(
                args=call_args,
                returncode=0,
                stdout="sf-import OK",
                stderr="",
            )
        mock_sub.side_effect = _run_side_effect

        result = _run_orchestrator(
            project_slug="test-proj",
            workspace_root=workspace,
            mcp=mcp,
            project_config=cfg,
        )

    # Verify the subprocess was invoked with the REAL sf_import CLI contract:
    # no --source-run-id (provenance is a frontmatter input, not a script flag).
    args_list = mock_sub.call_args.args[0]
    assert "--source-run-id" not in args_list
    assert args_list[args_list.index("--project") + 1] == "test-proj"

    state = _latest_workflow(workspace)
    assert state["status"] == "done"


# ---------------------------------------------------------------------------
# Bonus — SKILL.md frontmatter validates against skill-frontmatter.schema.json
# (spec mandate; Worker Open Question Q-PHASE-3-WORKER-01 surfaces the +1)
# ---------------------------------------------------------------------------

def test_frontmatter_validates_against_schema(
    skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must validate against
    schemas/skill-frontmatter.schema.json (Draft 7). Plus the F5 invariant:
    no `outputs.*` int values may leak in the body protocol example.
    """
    text = SKILL_MD.read_text("utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "SKILL.md must open with --- frontmatter ---"
    fm = yaml.safe_load(parts[1])

    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errs, (
        "frontmatter invalid: "
        f"{[('/'.join(str(p) for p in e.absolute_path) or '<root>', e.message) for e in errs]}"
    )

    # F5: in the body, every outputs.* example value must be a string.
    body = parts[2]
    import re
    m = re.search(r"workflow_runner\.complete\([^)]*outputs=\{(.+?)\}\s*\)",
                  body, re.DOTALL)
    assert m, "expected an outputs={...} example in the body protocol"
    outputs_block = m.group(1)
    bad = re.findall(r":\s*(\d+)\s*[,}]", outputs_block)
    assert not bad, (
        f"F5 violation: outputs.* example carries int literals {bad!r}; "
        "must be string-typed"
    )

    # Q-SF-MCP-02 lock: requires_approval=true.
    assert fm["autonomy"]["requires_approval"] is True
    # Q-SF-MCP-10 lock: 24 reports default (no Tier 3).
    assert fm["inputs"]["include_tier3"]["default"] is False
