"""End-to-end STUB harness for the new-project-setup driver (AMO batch 3c).

Mirrors ``test_audit_suite.py``: canned provenance-stamped raw inbox drops +
matching transform-output files are fed through the driver with a FAKE commit_fn
— NO live model, NO MCP, NO real workbook — and the driver's coverage record is
asserted per scenario, proven to validate against the frozen coverage.schema.json,
and tied to the Turkish ``/pseo-run setup <slug> --resume`` remediation on a
non-pass verdict.

The setup workflow has THREE ordered planning steps and NO report step: the
deliverable IS the three committed sheets (topical_map -> cluster_keywords ->
new_content_plan). ALL THREE are ``model_attested`` because every planning
transform AGGREGATES (many DFS keywords -> a structured pillar/cluster taxonomy;
new_content_plan caps to the top-N by gap_score) so each legitimately commits
<50% of its raw input — the silent-skip COUNT check would false-fail them. The
identity+content+freshness gate STILL runs (a wrong-run_id / stale / truncated
drop is ``failed``); only the silent-skip RATIO is advisory.

Because there is NO code_verified step, ``derive_verdict`` can only return 'pass'
or 'failed' for this workflow (a missing attested step never trips the 'missing'
branch, which scans code_verified steps only, and ``required_satisfied`` is
vacuously True over zero code steps). The COMPLETION GUARD (pass -> incomplete
unless every step is satisfied) is therefore load-bearing here — it alone makes a
missing planning step read 'incomplete'.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft7Validator

from scripts.orchestration import coverage
from scripts.orchestration.remediation import remediation
from scripts.orchestration.workflows import new_project_setup
from scripts.orchestration.workflows.new_project_setup import (
    STEPS,
    build_steps,
    inbox_path,
    output_path,
    run,
)

RUN_ID = "dental-2026-06-08-a1b2"
SLUG = "dental"
NOW = 1_750_000_000

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_SCHEMA = json.loads(
    (ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8")
)

ALL_STEPS = ["topical_map", "cluster_map", "new_content_plan"]


def _schema_errors(record: dict) -> list:
    return list(Draft7Validator(COVERAGE_SCHEMA).iter_errors(record))


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _rows(n: int) -> list[dict]:
    return [{"kw": f"kw{i}", "vol": 100 + i} for i in range(n)]


def _fake_commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None):
    """WriteResult-like: the driver reads only .rows_affected. No real workbook."""
    return SimpleNamespace(rows_affected=len(rows))


def _entry(name: str) -> dict:
    return next(e for e in STEPS if e["name"] == name)


def _write_drop(workspace, entry, rows, *, declared_count=None, mtime=NOW - 60,
                run_id=RUN_ID, slug=SLUG):
    """Provenance-stamped raw inbox drop. Planning is point-in-time so window is
    null; no step is GSC-primary so site_url is unpinned; new_content_plan pins
    NO tool (expected_tool None) so its provenance tool is a free label the gate
    ignores."""
    path = inbox_path(workspace, RUN_ID, SLUG, entry["name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provenance": {
            "run_id": run_id,
            "slug": slug,
            "window": None,
            "tool": entry["tool"] or "content_gaps_staging",
            "fetched_at": _iso(NOW - 60),
            "declared_count": len(rows) if declared_count is None else declared_count,
        },
        "rows": rows,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _write_output(workspace, output_file, rows, *, as_dict=False):
    """Model-produced transform OUTPUT, written at the OUTPUT-FILE-named path the
    driver's loader reads (the real CLIs write {output_file})."""
    path = output_path(workspace, RUN_ID, SLUG, output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rows": rows} if as_dict else rows), encoding="utf-8")
    return path


def _arrange_all(workspace, *, raw_n=10, out_n=10):
    for entry in STEPS:
        _write_drop(workspace, entry, _rows(raw_n))
        _write_output(workspace, entry["output_file"], _rows(out_n))


# --- step table + driver wiring -------------------------------------------

def test_step_table_is_the_three_setup_steps() -> None:
    assert [e["name"] for e in STEPS] == ["topical_map", "cluster_map", "new_content_plan"]
    assert [e["sheet"] for e in STEPS] == [
        "topical_map", "cluster_keywords", "new_content_plan",
    ]
    assert [e["output_file"] for e in STEPS] == [
        "topical_map.json", "cluster_keywords.json", "new_content_plan.json",
    ]
    assert [e["writer"] for e in STEPS] == [
        "topical-map", "cluster-map", "new-content-plan",
    ]


def test_step_table_all_steps_are_model_attested() -> None:
    """THE D classification. Every planning transform aggregates (topical_map ->
    pillar/cluster taxonomy; cluster_map skips no-cluster keywords + dedups;
    new_content_plan caps to top-N by gap_score), committing <50% of raw input by
    design, so each is model_attested — silent-skip would false-fail them. No
    setup step is per-row ingestion-shaped (unlike 3b's on_page_audit)."""
    vclass = {e["name"]: e["verification_class"] for e in STEPS}
    for name in ALL_STEPS:
        assert vclass[name] == "model_attested", name


def test_step_table_tools_and_site_url_pins() -> None:
    by = {e["name"]: e for e in STEPS}
    assert by["topical_map"]["tool"] == "mcp__dataforseo__dataforseo_labs_google_keyword_ideas"
    assert by["cluster_map"]["tool"] == "mcp__dataforseo__dataforseo_labs_google_keyword_suggestions"
    # new_content_plan consumes a FILE-based content-gaps staging drop (Phase 7
    # producer), not a fresh primary MCP call -> NO pinned tool (the schema_audit
    # 3b precedent: a file-sourced step gates identity+content+freshness only).
    assert by["new_content_plan"]["tool"] is None
    # planning is DFS-primary (cluster_map's GSC is enrichment), so NO step is
    # GSC-primary -> NO step pins a site_url.
    assert all(e["site_url"] is False for e in STEPS)


def test_build_steps_wires_one_spec_per_step(tmp_path: Path) -> None:
    specs = build_steps(RUN_ID, SLUG, tmp_path)
    assert [s.name for s in specs] == [e["name"] for e in STEPS]
    for spec, entry in zip(specs, STEPS):
        assert spec.sheet == entry["sheet"]
        assert spec.verification_class == entry["verification_class"]
        assert spec.expected_tool == entry["tool"]
        # planning is point-in-time: NO window pin on any step.
        assert spec.expected_window is None
        expected_mcp = (entry["tool"],) if entry["tool"] else ()
        assert spec.observed_mcp == expected_mcp
        # no GSC-primary step -> site_url stays None even when resolvable.
        assert spec.expected_site_url is None
        assert spec.raw_path == inbox_path(tmp_path, RUN_ID, SLUG, entry["name"])


def test_no_step_pins_site_url_even_with_project_config(tmp_path: Path) -> None:
    """Even when the project resolves a gsc.site_url, NO setup step pins it: the
    planning steps are DFS-primary (cluster_map's GSC is enrichment, not the
    gated primary drop)."""
    cfg = tmp_path / "projects" / SLUG / "project.config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"gsc": {"site_url": "https://dental.example"}}),
                   encoding="utf-8")
    specs = build_steps(RUN_ID, SLUG, tmp_path)
    assert all(s.expected_site_url is None for s in specs)


def test_driver_keys_output_file(tmp_path: Path) -> None:
    """Each step's loader reads its explicit output_file (= {sheet}.json here, but
    carried explicitly for consistency with audit_suite + future-proofing)."""
    _write_output(tmp_path, "cluster_keywords.json", [{"cluster": "implants"}])
    specs = {s.name: s for s in build_steps(RUN_ID, SLUG, tmp_path)}
    assert specs["cluster_map"].transform([{"ignored": True}]) == [
        {"cluster": "implants"}
    ]


def test_output_loader_ignores_raw_and_accepts_both_shapes(tmp_path: Path) -> None:
    out = output_path(tmp_path, RUN_ID, SLUG, "topical_map.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": [{"a": 1}]}), encoding="utf-8")
    loader = new_project_setup._output_loader(out)
    assert loader([{"ignored": True}]) == [{"a": 1}]
    out.write_text(json.dumps([{"b": 2}]), encoding="utf-8")
    assert new_project_setup._output_loader(out)([]) == [{"b": 2}]


def test_output_loader_missing_file_raises(tmp_path: Path) -> None:
    loader = new_project_setup._output_loader(tmp_path / "nope.json")
    with pytest.raises(Exception):
        loader([])


# --- scenarios -------------------------------------------------------------

def test_happy_path_all_satisfied_verdict_pass(tmp_path: Path) -> None:
    _arrange_all(tmp_path)
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit)
    assert record["verdict"] == "pass"
    assert record["required_satisfied"] is True
    assert len(record["steps"]) == 3
    assert all(s["status"] == "satisfied" for s in record["steps"])

    attested = [s for s in record["steps"] if s["verification_class"] == "model_attested"]
    assert {s["name"] for s in attested} == set(ALL_STEPS)
    # no code_verified step -> required_satisfied is vacuously True; the
    # completion guard (not derive_verdict) is what enforces completeness.

    assert _schema_errors(record) == []
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []
    assert remediation(record, slug=SLUG, workflow="setup") is None
    assert not (tmp_path / "master.xlsx").exists()


def test_missing_attested_step_is_incomplete_via_completion_guard(tmp_path: Path) -> None:
    """ALL setup steps are model_attested (SOFT in derive_verdict), so a missing
    one alone would read 'pass' (required_satisfied is vacuously True). The
    deliverable is all THREE sheets, so the completion guard downgrades pass ->
    incomplete. This is the load-bearing guard for an all-attested workflow."""
    for entry in STEPS:
        if entry["name"] == "topical_map":
            continue  # no raw drop -> verify_raw_drop returns missing_file
        _write_drop(tmp_path, entry, _rows(10))
        _write_output(tmp_path, entry["output_file"], _rows(10))
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    statuses = {s["name"]: s["status"] for s in record["steps"]}
    assert statuses["topical_map"] == "missing"
    assert record["verdict"] != "pass"
    assert record["verdict"] == "incomplete"

    rem = remediation(record, slug=SLUG, workflow="setup")
    assert rem is not None
    assert "topical_map" in rem["missing"]
    assert rem["one_line_fix_command"] == "/pseo-run setup dental --resume"


def test_wrong_run_id_is_failed_identity(tmp_path: Path) -> None:
    _arrange_all(tmp_path)
    # corrupt the cluster_map drop's provenance run_id -> identity mismatch.
    _write_drop(tmp_path, _entry("cluster_map"), _rows(10), run_id="other-run")
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    cm = next(s for s in record["steps"] if s["name"] == "cluster_map")
    assert cm["status"] == "failed"
    assert record["verdict"] == "failed"


def test_stale_drop_is_failed(tmp_path: Path) -> None:
    _arrange_all(tmp_path)
    # age the topical_map drop past the 24h freshness window.
    _write_drop(tmp_path, _entry("topical_map"), _rows(10), mtime=NOW - 90_000)
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    tm = next(s for s in record["steps"] if s["name"] == "topical_map")
    assert tm["status"] == "failed"
    assert record["verdict"] == "failed"


def test_truncated_drop_is_failed_even_for_no_tool_step(tmp_path: Path) -> None:
    """declared_count != len(rows) -> truncated gate fires on new_content_plan
    (the model_attested step with expected_tool=None) too: the identity+content
    gate is NOT advisory; only the silent-skip ratio is."""
    _arrange_all(tmp_path)
    _write_drop(tmp_path, _entry("new_content_plan"), _rows(10), declared_count=99)
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    ncp = next(s for s in record["steps"] if s["name"] == "new_content_plan")
    assert ncp["status"] == "failed"
    assert record["verdict"] == "failed"


def test_cardinality_attested_drop_over_50pct_is_not_false_failed(tmp_path: Path) -> None:
    """THE D classification proof. topical_map (model_attested) commits 2 rows from
    a 10-row raw drop (80% reshaped) and stays SATISFIED — silent-skip is advisory
    for an aggregating planning step. Every setup step is model_attested, so the
    gate is uniformly advisory (no code_verified counterexample, unlike 3b)."""
    for entry in STEPS:
        _write_drop(tmp_path, entry, _rows(10))
        out_n = 2 if entry["name"] == "topical_map" else 10
        _write_output(tmp_path, entry["output_file"], _rows(out_n))
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    steps = {s["name"]: s for s in record["steps"]}

    tm = steps["topical_map"]
    assert tm["status"] == "satisfied"            # NOT false-failed
    assert tm["input_count"] == 10 and tm["scored_count"] == 2
    assert record["verdict"] == "pass"            # all three satisfied


def test_attested_step_commits_scored_count(tmp_path: Path) -> None:
    """Every model_attested step still COMMITS its output via the injected
    commit_fn (rows_affected recorded as scored_count); only the silent-skip
    RATIO is advisory, not the write."""
    committed: list[tuple] = []

    def _spy_commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None):
        committed.append((sheet, len(rows)))
        return SimpleNamespace(rows_affected=len(rows))

    _arrange_all(tmp_path, raw_n=10, out_n=3)
    run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
        commit_fn=_spy_commit, write=False)
    by_sheet = dict(committed)
    assert by_sheet["topical_map"] == 3
    assert by_sheet["cluster_keywords"] == 3
    assert by_sheet["new_content_plan"] == 3


def test_steps_run_in_dependency_order(tmp_path: Path) -> None:
    """The driver commits sheets in declared order topical_map -> cluster_keywords
    -> new_content_plan. ORDER is what satisfies the sequential dependency: each
    prior sheet is committed before the dependent step's transform runs."""
    order: list[str] = []

    def _spy_commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None):
        order.append(sheet)
        return SimpleNamespace(rows_affected=len(rows))

    _arrange_all(tmp_path)
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_spy_commit, write=False)
    assert order == ["topical_map", "cluster_keywords", "new_content_plan"]
    assert [s["name"] for s in record["steps"]] == ALL_STEPS


# --- CLI boundary (clock-free: --now-epoch is required) --------------------

def test_cli_no_drops_prints_setup_remediation_and_writes_coverage(tmp_path, capsys) -> None:
    rc = new_project_setup.main([
        "--workspace-root", str(tmp_path), "--slug", SLUG, "--run-id", RUN_ID,
        "--workbook", str(tmp_path / "master.xlsx"), "--now-epoch", str(NOW),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/pseo-run setup dental --resume" in out
    assert "incomplete" in out
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []
    assert not (tmp_path / "master.xlsx").exists()
