"""tests/scripts/test_transaction_lock_identity.py — the excel.lock belongs to the WORKBOOK.

``transaction.update`` / ``_write_or_append`` used to derive the lock sentinel from
``_state_dir(state_root, ...)``. A caller passing an explicit ``state_root`` (sheet_merge,
committer and orchestration code thread it through) therefore locked a DIFFERENT file
than a caller relying on the default ``projects/{slug}/_state``. Two such writers on the
same master.xlsx never contended: both loaded the workbook, both saved, and the later
save silently reverted the earlier writer's sheet — the "lock held, rows_affected=N,
data gone" failure seen with parallel refresh workers.

Contract locked here:
  * the lock sentinel is ALWAYS ``<workbook dir>/_state/excel.lock``, whatever state_root is;
  * sidecars (backups) still honour the caller's state_root.
"""
from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.excel import transaction
from scripts.excel.transaction import LockHeldError

SLUG = "test-proj"


def _row(keyword: str) -> dict:
    return {
        "pillar": "P01_sofa_sets",
        "cluster": "leather-sofas",
        "primary_keyword": keyword,
        "monthly_volume": 4400,
        "data_source": "gsc",
        "assigned_url": f"/{keyword.replace(' ', '-')}",
        "page_type": "pillar",
        "status": "TODO",
        "priority": "HIGH",
        "note": "",
    }


def _hold(lock_path: Path) -> int:
    """Hold the sentinel like a live peer writer: flock + fresh pid/ts (not stale)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    os.ftruncate(fd, 0)
    os.write(fd, json.dumps({"pid": os.getpid(), "ts": stamp}).encode("utf-8"))
    return fd


def _release(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    project = tmp_path / "projects" / SLUG
    (project / "_state").mkdir(parents=True)
    wb = project / "master.xlsx"
    transaction.append(wb, "topical_map", [_row("seed")], SLUG)
    return wb


def test_append_with_foreign_state_root_contends_on_workbook_lock(workbook: Path, tmp_path: Path) -> None:
    fd = _hold(workbook.parent / "_state" / "excel.lock")
    try:
        with pytest.raises(LockHeldError):
            transaction.append(workbook, "topical_map", [_row("peer")], SLUG, state_root=tmp_path / "elsewhere" / "_state")
    finally:
        _release(fd)


def test_update_with_foreign_state_root_contends_on_workbook_lock(workbook: Path, tmp_path: Path) -> None:
    fd = _hold(workbook.parent / "_state" / "excel.lock")
    try:
        with pytest.raises(LockHeldError):
            transaction.update(
                workbook, "topical_map",
                where={"primary_keyword": "seed"}, set_={"note": "peer"},
                project_slug=SLUG, state_root=tmp_path / "elsewhere" / "_state",
            )
    finally:
        _release(fd)


def test_every_state_root_resolves_to_the_same_lock_file(workbook: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Path] = []
    real = transaction._acquire_lock

    def spy(lock_path, *args, **kwargs):
        seen.append(Path(lock_path))
        return real(lock_path, *args, **kwargs)

    monkeypatch.setattr(transaction, "_acquire_lock", spy)
    transaction.append(workbook, "topical_map", [_row("one")], SLUG, state_root=tmp_path / "s1")
    transaction.update(workbook, "topical_map", where={"primary_keyword": "one"}, set_={"note": "x"},
                       project_slug=SLUG, state_root=tmp_path / "s2")
    transaction.append(workbook, "topical_map", [_row("two")], SLUG)
    assert seen == [workbook.parent / "_state" / "excel.lock"] * 3


def test_backups_still_follow_the_callers_state_root(workbook: Path, tmp_path: Path) -> None:
    custom = tmp_path / "custom-state"
    transaction.append(workbook, "topical_map", [_row("backup-probe")], SLUG, state_root=custom)
    assert any((custom / "backups" / "master").glob("master-*.xlsx"))
