"""End-to-end STUB harness for the audit-suite driver (AMO batch 3b).

Mirrors ``test_monthly_maintenance.py``: canned provenance-stamped raw inbox drops
+ matching transform-output files are fed through the driver with a FAKE commit_fn
— NO live model, NO MCP, NO real workbook — and the driver's coverage record is
asserted per scenario, proven to validate against the frozen coverage.schema.json,
and tied to the Turkish ``/pseo-run audit <slug> --resume`` remediation on a
non-pass verdict.

The audit suite has FOUR structured steps and NO report step (unlike monthly):
the deliverable IS the four committed sheets. Three steps ANALYZE (aggregate /
reshape) so they are ``model_attested`` — the identity+content+freshness gate
STILL runs but the silent-skip count check is ADVISORY (an aggregating transform
legitimately commits <50% of its raw input). ``on_page_audit`` emits one row per
input URL so it stays ``code_verified`` with the silent-skip gate enforced.
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
from scripts.orchestration.workflows import audit_suite
from scripts.orchestration.workflows.audit_suite import (
    STEPS,
    build_steps,
    inbox_path,
    output_path,
    run,
)

RUN_ID = "demo-furniture-2026-06-08-a1b2"
SLUG = "demo-furniture"
NOW = 1_750_000_000

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_SCHEMA = json.loads(
    (ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8")
)

CODE_VERIFIED_STEP = "on_page_audit"
ATTESTED_STEPS = {"tech_audit", "schema_audit", "cannibalization"}


def _schema_errors(record: dict) -> list:
    return list(Draft7Validator(COVERAGE_SCHEMA).iter_errors(record))


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _rows(n: int) -> list[dict]:
    return [{"q": f"kw{i}", "url": f"https://demo-furniture.example/p{i}"} for i in range(n)]


def _fake_commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None):
    """WriteResult-like: the driver reads only .rows_affected. No real workbook."""
    return SimpleNamespace(rows_affected=len(rows))


def _entry(name: str) -> dict:
    return next(e for e in STEPS if e["name"] == name)


def _write_drop(workspace, entry, rows, *, declared_count=None, mtime=NOW - 60,
                run_id=RUN_ID, slug=SLUG, site_url="https://demo-furniture.example"):
    """Provenance-stamped raw inbox drop matching this step's tool. Audit drops
    pin window=null (point-in-time); schema_audit pins NO tool (expected_tool
    None), so its provenance tool is a free-form label the gate ignores."""
    path = inbox_path(workspace, RUN_ID, SLUG, entry["name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provenance": {
            "run_id": run_id,
            "slug": slug,
            "site_url": site_url,
            "window": None,
            "tool": entry["tool"] or "sf_export",
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
    driver's loader reads (the real CLIs write {output_file}, NOT {sheet}.json)."""
    path = output_path(workspace, RUN_ID, SLUG, output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rows": rows} if as_dict else rows), encoding="utf-8")
    return path


def _arrange_all(workspace, *, raw_n=10, out_n=10):
    for entry in STEPS:
        _write_drop(workspace, entry, _rows(raw_n))
        _write_output(workspace, entry["output_file"], _rows(out_n))


# --- step table + driver wiring -------------------------------------------

def test_step_table_is_the_four_audit_steps() -> None:
    assert [e["name"] for e in STEPS] == [
        "tech_audit", "schema_audit", "on_page_audit", "cannibalization",
    ]
    assert [e["sheet"] for e in STEPS] == [
        "tech_seo", "schema", "on_page_audit", "cannibalization",
    ]
    assert [e["output_file"] for e in STEPS] == [
        "tech_seo.json", "schema_audit.json",
        "on_page_audit.json", "cannibalization.json",
    ]
    assert [e["writer"] for e in STEPS] == [
        "tech-audit", "schema-audit", "on-page-audit", "cannibalization",
    ]


def test_step_table_verification_classes_encode_the_cardinality_seam() -> None:
    vclass = {e["name"]: e["verification_class"] for e in STEPS}
    # on_page_audit emits one row per input URL -> gate meaningful -> code_verified.
    assert vclass["on_page_audit"] == "code_verified"
    # the three analysis steps legitimately reshape cardinality -> model_attested.
    for name in ATTESTED_STEPS:
        assert vclass[name] == "model_attested"


def test_step_table_tools_and_site_url_pins() -> None:
    by = {e["name"]: e for e in STEPS}
    assert by["tech_audit"]["tool"] == "mcp__dataforseo__on_page_lighthouse"
    assert by["on_page_audit"]["tool"] == "mcp__dataforseo__on_page_content_parsing"
    assert by["cannibalization"]["tool"] == "mcp__gsc__search_analytics"
    # schema_audit is SF-or-file: NO pinned tool.
    assert by["schema_audit"]["tool"] is None
    # only the GSC-sourced step pins a site_url.
    assert by["cannibalization"]["site_url"] is True
    assert all(by[n]["site_url"] is False for n in
               ("tech_audit", "schema_audit", "on_page_audit"))


def test_build_steps_wires_one_spec_per_step(tmp_path: Path) -> None:
    specs = build_steps(RUN_ID, SLUG, tmp_path)
    assert [s.name for s in specs] == [e["name"] for e in STEPS]
    for spec, entry in zip(specs, STEPS):
        assert spec.sheet == entry["sheet"]
        assert spec.verification_class == entry["verification_class"]
        assert spec.expected_tool == entry["tool"]
        # audit is point-in-time: NO window pin on any step.
        assert spec.expected_window is None
        expected_mcp = (entry["tool"],) if entry["tool"] else ()
        assert spec.observed_mcp == expected_mcp
        # no project.config.json in the stub -> site_url stays None for ALL steps
        # (the driver must NOT hard-fail on an unresolved site_url).
        assert spec.expected_site_url is None
        assert spec.raw_path == inbox_path(tmp_path, RUN_ID, SLUG, entry["name"])


def test_build_steps_pins_site_url_only_for_gsc_step(tmp_path: Path) -> None:
    cfg = tmp_path / "projects" / SLUG / "project.config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"gsc": {"site_url": "https://demo-furniture.example"}}),
                   encoding="utf-8")
    specs = {s.name: s for s in build_steps(RUN_ID, SLUG, tmp_path)}
    assert specs["cannibalization"].expected_site_url == "https://demo-furniture.example"
    for name in ("tech_audit", "schema_audit", "on_page_audit"):
        assert specs[name].expected_site_url is None


def test_driver_keys_output_file_not_sheet(tmp_path: Path) -> None:
    """schema_audit's CLI writes schema_audit.json though its sheet is `schema`.
    The loader build_steps wires MUST read schema_audit.json (output_file), NOT
    schema.json (the 1d.1 trap)."""
    _write_output(tmp_path, "schema_audit.json", [{"schema_type": "Product"}])
    specs = {s.name: s for s in build_steps(RUN_ID, SLUG, tmp_path)}
    # loads schema_audit.json (ignores raw rows, returns the output rows)
    assert specs["schema_audit"].transform([{"ignored": True}]) == [
        {"schema_type": "Product"}
    ]
    # nothing was written to schema.json -> a loader keyed on {sheet}.json would
    # have raised; confirm that path is genuinely absent.
    assert not output_path(tmp_path, RUN_ID, SLUG, "schema.json").exists()


def test_output_loader_ignores_raw_and_accepts_both_shapes(tmp_path: Path) -> None:
    out = output_path(tmp_path, RUN_ID, SLUG, "tech_seo.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": [{"a": 1}]}), encoding="utf-8")
    loader = audit_suite._output_loader(out)
    assert loader([{"ignored": True}]) == [{"a": 1}]
    out.write_text(json.dumps([{"b": 2}]), encoding="utf-8")
    assert audit_suite._output_loader(out)([]) == [{"b": 2}]


def test_output_loader_missing_file_raises(tmp_path: Path) -> None:
    loader = audit_suite._output_loader(tmp_path / "nope.json")
    with pytest.raises(Exception):
        loader([])


# --- scenarios -------------------------------------------------------------

def test_happy_path_all_satisfied_verdict_pass(tmp_path: Path) -> None:
    _arrange_all(tmp_path)
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit)
    assert record["verdict"] == "pass"
    assert record["required_satisfied"] is True
    assert len(record["steps"]) == 4
    assert all(s["status"] == "satisfied" for s in record["steps"])

    code = [s for s in record["steps"] if s["verification_class"] == "code_verified"]
    attested = [s for s in record["steps"] if s["verification_class"] == "model_attested"]
    assert [s["name"] for s in code] == [CODE_VERIFIED_STEP]
    assert {s["name"] for s in attested} == ATTESTED_STEPS

    assert _schema_errors(record) == []
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []
    # a passing run needs no remediation; the fake committer wrote NO real workbook.
    assert remediation(record, slug=SLUG, workflow="audit") is None
    assert not (tmp_path / "master.xlsx").exists()


def test_missing_code_verified_step_is_incomplete(tmp_path: Path) -> None:
    for entry in STEPS:
        if entry["name"] == CODE_VERIFIED_STEP:
            continue  # no raw drop -> verify_raw_drop returns missing_file
        _write_drop(tmp_path, entry, _rows(10))
        _write_output(tmp_path, entry["output_file"], _rows(10))
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    statuses = {s["name"]: s["status"] for s in record["steps"]}
    assert statuses[CODE_VERIFIED_STEP] == "missing"
    assert record["verdict"] == "incomplete"

    rem = remediation(record, slug=SLUG, workflow="audit")
    assert rem is not None
    assert CODE_VERIFIED_STEP in rem["missing"]
    assert rem["one_line_fix_command"] == "/pseo-run audit demo-furniture --resume"


def test_missing_attested_step_is_not_pass(tmp_path: Path) -> None:
    """A missing model_attested step is SOFT in derive_verdict, but the deliverable
    is all four sheets, so the completion guard downgrades pass -> incomplete."""
    for entry in STEPS:
        if entry["name"] == "tech_audit":
            continue  # attested step with no drop
        _write_drop(tmp_path, entry, _rows(10))
        _write_output(tmp_path, entry["output_file"], _rows(10))
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    statuses = {s["name"]: s["status"] for s in record["steps"]}
    assert statuses["tech_audit"] == "missing"
    assert record["verdict"] != "pass"
    assert record["verdict"] == "incomplete"
    assert remediation(record, slug=SLUG, workflow="audit") is not None


def test_wrong_run_id_is_failed_identity(tmp_path: Path) -> None:
    _arrange_all(tmp_path)
    # corrupt the cannibalization drop's provenance run_id -> identity mismatch.
    _write_drop(tmp_path, _entry("cannibalization"), _rows(10), run_id="other-run")
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    cann = next(s for s in record["steps"] if s["name"] == "cannibalization")
    assert cann["status"] == "failed"
    assert record["verdict"] == "failed"


def test_stale_drop_is_failed(tmp_path: Path) -> None:
    _arrange_all(tmp_path)
    # age the on_page_audit drop past the 24h freshness window.
    _write_drop(tmp_path, _entry(CODE_VERIFIED_STEP), _rows(10),
                mtime=NOW - 90_000)
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    op = next(s for s in record["steps"] if s["name"] == CODE_VERIFIED_STEP)
    assert op["status"] == "failed"
    assert record["verdict"] == "failed"


def test_truncated_drop_is_failed(tmp_path: Path) -> None:
    _arrange_all(tmp_path)
    # declared_count != len(rows) -> truncated gate fires on a model_attested step
    # too (the identity+content gate is NOT advisory; only silent-skip is).
    _write_drop(tmp_path, _entry("tech_audit"), _rows(10), declared_count=99)
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    tech = next(s for s in record["steps"] if s["name"] == "tech_audit")
    assert tech["status"] == "failed"
    assert record["verdict"] == "failed"


def test_cardinality_attested_drop_over_50pct_is_not_false_failed(tmp_path: Path) -> None:
    """THE D classification proof. tech_audit (model_attested) commits 2 rows from
    a 10-row raw drop (80% reshaped) and stays SATISFIED — silent-skip is advisory
    for an aggregating step. on_page_audit (code_verified) commits 4 rows from 10
    and is FAILED — silent-skip is enforced for the ingestion-shaped step."""
    for entry in STEPS:
        _write_drop(tmp_path, entry, _rows(10))
        if entry["name"] == "tech_audit":
            _write_output(tmp_path, entry["output_file"], _rows(2))   # 80% reshape
        elif entry["name"] == CODE_VERIFIED_STEP:
            _write_output(tmp_path, entry["output_file"], _rows(4))   # 60% silent skip
        else:
            _write_output(tmp_path, entry["output_file"], _rows(10))
    record = run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
                 commit_fn=_fake_commit, write=False)
    steps = {s["name"]: s for s in record["steps"]}

    tech = steps["tech_audit"]
    assert tech["status"] == "satisfied"          # NOT false-failed
    assert tech["input_count"] == 10 and tech["scored_count"] == 2

    op = steps[CODE_VERIFIED_STEP]
    assert op["status"] == "failed"               # silent-skip enforced
    assert op["input_count"] == 10 and op["scored_count"] == 4

    assert record["verdict"] == "failed"          # the code_verified step fails


def test_attested_step_commits_scored_count(tmp_path: Path) -> None:
    """A model_attested step still COMMITS its output (rows_affected recorded as
    scored_count) — the gate is advisory only for the silent-skip RATIO, not the
    write."""
    committed: list[tuple] = []

    def _spy_commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None):
        committed.append((sheet, len(rows)))
        return SimpleNamespace(rows_affected=len(rows))

    _arrange_all(tmp_path, raw_n=10, out_n=3)
    run(RUN_ID, SLUG, tmp_path, tmp_path / "master.xlsx", NOW,
        commit_fn=_spy_commit, write=False)
    by_sheet = dict(committed)
    # every audit sheet was committed via the injected commit_fn, attested or not.
    assert by_sheet["tech_seo"] == 3
    assert by_sheet["schema"] == 3
    assert by_sheet["cannibalization"] == 3
    assert by_sheet["on_page_audit"] == 3


# --- CLI boundary (clock-free: --now-epoch is required) --------------------

def test_cli_no_drops_prints_audit_remediation_and_writes_coverage(tmp_path, capsys) -> None:
    rc = audit_suite.main([
        "--workspace-root", str(tmp_path), "--slug", SLUG, "--run-id", RUN_ID,
        "--workbook", str(tmp_path / "master.xlsx"), "--now-epoch", str(NOW),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/pseo-run audit demo-furniture --resume" in out
    assert "incomplete" in out
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []
    assert not (tmp_path / "master.xlsx").exists()
