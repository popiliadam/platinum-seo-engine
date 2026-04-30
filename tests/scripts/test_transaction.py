"""
Unit tests for scripts/excel/transaction.py.

Covers: happy-path writes, schema validation, formula policy, atomic-save
fault-injection, backup rotation, lock contention, status/severity enum
guards (ADR-018 hibrit), provenance event emission, plugin-agnostic
source check.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from scripts.excel import transaction
from scripts.excel.transaction import (
    CellValueTooLongError,
    FormulaPolicyViolation,
    LockHeldError,
    RowSchemaError,
    SchemaSheetMismatchError,
    WriteResult,
    WriterScopeError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_project(tmp_path: Path, slug: str = "test-proj") -> tuple[Path, Path]:
    """Create projects/{slug}/_state/ tree; return (project_dir, state_dir)."""
    proj = tmp_path / "projects" / slug
    state = proj / "_state"
    state.mkdir(parents=True, exist_ok=True)
    return proj, state


def _topical_row(**overrides) -> dict:
    base = {
        "pillar": "P01_sofa_sets",
        "cluster": "leather-sofas",
        "primary_keyword": "leather sofa",
        "monthly_volume": 4400,
        "data_source": "gsc",
        "assigned_url": "/leather-sofas",
        "page_type": "pillar",
        "status": "TODO",
        "priority": "HIGH",
        "note": "",
    }
    base.update(overrides)
    return base


def _master_task_row(**overrides) -> dict:
    base = {
        "task_id": "T-0001",
        "task": "fix slow page",
        "primary_source": "tech_fix",
        "related_sources": "tech_fix",
        "url": "/slow-page",
        "category": "performance",
        "priority": "HIGH",
        "impact": "speed",
        "duration_est_min": 30,
        "status": "TODO",
        "created_date": "2026-04-30",
        "done_date": None,
        "assignee": "ops",
        "note": "",
        "auto_generated": False,
        "dependencies": "",
        "effort_actual_min": None,
        "metric_impact_json": "",
        "work_log_ref": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test 1 — happy path: write topical_map rows, verify content + event
# ---------------------------------------------------------------------------

def test_happy_path_write_topical_map(tmp_path: Path) -> None:
    proj, state = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"

    rows = [_topical_row(primary_keyword=f"kw {i}") for i in range(3)]
    result = transaction.append(wb_path, "topical_map", rows, "test-proj")

    assert isinstance(result, WriteResult)
    assert result.rows_affected == 3
    assert result.backup_path.exists()
    assert wb_path.exists()

    wb = load_workbook(wb_path)
    ws = wb["topical_map"]
    # Header row + 3 data rows.
    assert ws.max_row == 4
    assert ws["A1"].value == "pillar"
    assert ws["C2"].value == "kw 0"
    assert ws["C4"].value == "kw 2"

    # Provenance event was emitted.
    events_path = state / "events.jsonl"
    assert events_path.exists()
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    ev = json.loads(lines[0])
    assert ev["event_kind"] == "provenance"
    assert ev["target_excel_sheet"] == "topical_map"
    assert ev["rows_written"] == 3
    assert ev["operation"] == "project_excel"
    assert ev["event_id"] == result.event_id


# ---------------------------------------------------------------------------
# Test 2 — atomic save: monkeypatch os.replace to raise, original intact
# ---------------------------------------------------------------------------

def test_atomic_kill_mid_write_no_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proj, state = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"

    # Seed an existing workbook with one row so we can verify it's untouched.
    transaction.append(wb_path, "topical_map", [_topical_row()], "test-proj")
    pre_mtime = wb_path.stat().st_mtime
    pre_size = wb_path.stat().st_size

    # Inject failure at os.replace inside transaction module.
    def _boom(src, dst):
        raise OSError(13, "simulated rename failure")

    monkeypatch.setattr(transaction.os, "replace", _boom)

    with pytest.raises(OSError, match="simulated rename failure"):
        transaction.append(wb_path, "topical_map",
                           [_topical_row(primary_keyword="ghost")], "test-proj")

    # Original workbook unchanged.
    assert wb_path.stat().st_size == pre_size
    # Tempfile must not leak in parent dir.
    leftovers = [p for p in proj.iterdir() if p.name.startswith(".master-") and p.name.endswith(".xlsx.tmp")]
    assert leftovers == [], f"leaked tempfile: {leftovers}"


# ---------------------------------------------------------------------------
# Test 3 — missing required column → RowSchemaError
# ---------------------------------------------------------------------------

def test_schema_validation_rejects_missing_required(tmp_path: Path) -> None:
    proj, _ = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    bad = _topical_row()
    bad.pop("pillar")
    with pytest.raises(RowSchemaError):
        transaction.append(wb_path, "topical_map", [bad], "test-proj")


# ---------------------------------------------------------------------------
# Test 4 — formula prefix '=' rejected
# ---------------------------------------------------------------------------

def test_formula_policy_rejects_equals_prefix(tmp_path: Path) -> None:
    proj, _ = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    row = _topical_row(note="=SUM(A:A)")
    with pytest.raises(FormulaPolicyViolation):
        transaction.append(wb_path, "topical_map", [row], "test-proj")


# ---------------------------------------------------------------------------
# Test 5 — backup rotation keeps 7
# ---------------------------------------------------------------------------

def test_backup_rotation_keeps_last_seven(tmp_path: Path) -> None:
    proj, state = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    backup_dir = state / "backups" / "master"

    for i in range(10):
        transaction.append(
            wb_path, "topical_map",
            [_topical_row(primary_keyword=f"kw{i}")],
            "test-proj",
        )
        time.sleep(0.001)  # ensure ISO timestamps differ at microsecond grain

    files = sorted(backup_dir.iterdir())
    assert len(files) == 7, f"expected 7 backups, got {len(files)}"


# ---------------------------------------------------------------------------
# Test 6 — lock contention (multiprocessing): second writer fails fast
# ---------------------------------------------------------------------------

def _holder_proc(lock_path: str, hold_event_path: str, release_event_path: str) -> None:
    """Subprocess: acquire lock, signal ready, hold until told to release."""
    import fcntl as _fcntl
    import os as _os
    fd = _os.open(lock_path, _os.O_WRONLY | _os.O_CREAT, 0o644)
    _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
    Path(hold_event_path).touch()
    while not Path(release_event_path).exists():
        time.sleep(0.01)
    _fcntl.flock(fd, _fcntl.LOCK_UN)
    _os.close(fd)


def test_lock_contention_second_writer_fails_fast(tmp_path: Path) -> None:
    proj, state = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    lock_path = state / "excel.lock"
    hold_event = tmp_path / "holder-up"
    release_event = tmp_path / "holder-release"

    # Pre-write the sentinel with a real PID + ts so stale-detection
    # treats it as live (not stale).
    holder = mp.Process(
        target=_holder_proc,
        args=(str(lock_path), str(hold_event), str(release_event)),
    )
    holder.start()
    try:
        # Wait until the holder has acquired flock.
        for _ in range(200):
            if hold_event.exists():
                break
            time.sleep(0.01)
        else:  # pragma: no cover
            holder.terminate()
            pytest.fail("holder process never acquired lock")

        # Pre-populate sentinel with the holder's pid so stale-check passes.
        lock_path.write_text(json.dumps({
            "pid": holder.pid,
            "ts": "2099-12-31T23:59:59.999999Z",  # future = not stale
        }), encoding="utf-8")

        with pytest.raises(LockHeldError):
            transaction.append(wb_path, "topical_map", [_topical_row()], "test-proj")
    finally:
        release_event.touch()
        holder.join(timeout=5)
        if holder.is_alive():  # pragma: no cover
            holder.terminate()


# ---------------------------------------------------------------------------
# Test 7 — statusEnum 7 values pass; "WIP" fails
# ---------------------------------------------------------------------------

def test_status_enum_validates_all_seven(tmp_path: Path) -> None:
    proj, _ = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    statuses = ["TODO", "ONGOING", "EXISTS", "DONE", "BLOCKED", "DEFERRED", "CANCELED"]
    rows = [_topical_row(status=s, primary_keyword=f"kw-{s.lower()}") for s in statuses]
    result = transaction.append(wb_path, "topical_map", rows, "test-proj")
    assert result.rows_affected == 7

    # Now invalid status:
    bad = _topical_row(status="WIP", primary_keyword="kw-wip")
    with pytest.raises(RowSchemaError):
        transaction.append(wb_path, "topical_map", [bad], "test-proj")


# ---------------------------------------------------------------------------
# Test 8 — severityEnum on tech_seo: CRITICAL/HIGH/MEDIUM/LOW pass; URGENT fails
# ---------------------------------------------------------------------------

def test_severity_enum_validates(tmp_path: Path) -> None:
    proj, _ = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"

    def _tech_row(impact: str) -> dict:
        return {
            "issue_category": "perf",
            "detail": "slow LCP",
            "affected_urls": "/page",
            "impact": impact,
            "resolution": "lazy-load",
            "priority": "P1",
        }

    rows = [_tech_row(s) for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]]
    transaction.append(wb_path, "tech_seo", rows, "test-proj")

    with pytest.raises(RowSchemaError):
        transaction.append(wb_path, "tech_seo", [_tech_row("URGENT")], "test-proj")


# ---------------------------------------------------------------------------
# Test 9 — provenance event has correct shape
# ---------------------------------------------------------------------------

def test_provenance_event_emitted_after_write(tmp_path: Path) -> None:
    proj, state = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    transaction.append(wb_path, "topical_map", [_topical_row()], "test-proj")

    events_path = state / "events.jsonl"
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    ev = json.loads(lines[0])
    assert ev["event_kind"] == "provenance"
    assert ev["target_excel_sheet"] == "topical_map"
    assert ev["operation"] == "project_excel"
    assert ev["source"]["kind"] == "tool_computed"
    assert ev["rows_written"] == 1
    assert isinstance(ev["run_id"], int)


# ---------------------------------------------------------------------------
# Test 10 — plugin-agnostic source: no slug literals in module
# ---------------------------------------------------------------------------

def test_plugin_agnostic_no_slug_leak() -> None:
    src = Path(transaction.__file__).read_text(encoding="utf-8")
    forbidden = ("demo-dental", "demo-furniture", "demo-hvac", "demo-petcare")
    hits = [name for name in forbidden if name in src.lower()]
    assert hits == [], f"slug leak in transaction.py: {hits}"


# ---------------------------------------------------------------------------
# Test 11 — sheet missing from schema → SchemaSheetMismatchError
# ---------------------------------------------------------------------------

def test_unknown_sheet_rejected(tmp_path: Path) -> None:
    proj, _ = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    with pytest.raises(SchemaSheetMismatchError):
        transaction.append(wb_path, "no_such_sheet", [], "test-proj")


# ---------------------------------------------------------------------------
# Test 12 — master_task writer scope guard
# ---------------------------------------------------------------------------

def test_master_task_requires_writer(tmp_path: Path) -> None:
    proj, _ = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    row = _master_task_row()
    # No writer → WriterScopeError
    with pytest.raises(WriterScopeError):
        transaction.append(wb_path, "master_task", [row], "test-proj")
    # Disallowed writer → WriterScopeError
    with pytest.raises(WriterScopeError):
        transaction.append(wb_path, "master_task", [row], "test-proj", writer="rogue")
    # Allowed writer → OK
    result = transaction.append(
        wb_path, "master_task", [row], "test-proj", writer="human",
    )
    assert result.rows_affected == 1


# ---------------------------------------------------------------------------
# Test 13 — cell length cap
# ---------------------------------------------------------------------------

def test_cell_value_too_long(tmp_path: Path) -> None:
    proj, _ = _setup_project(tmp_path)
    wb_path = proj / "master.xlsx"
    huge_note = "x" * 40_000
    with pytest.raises(CellValueTooLongError):
        transaction.append(
            wb_path, "topical_map",
            [_topical_row(note=huge_note)],
            "test-proj",
        )
