"""V-02 / V-05: a flock sentinel must never be unlinked.

flock is held on the file's INODE. Deleting the lockfile (on release, or when
its pid/ts content looks "stale") lets the next writer create a NEW inode at the
same path and flock that one, while the old holder still owns the old inode:
two holders at once. The fix keeps the file forever (its pid/ts is informational
only — the kernel drops the flock when the owner dies), modelled on
scripts/state/project_lock.py.
"""
from __future__ import annotations

import fcntl
import json
import multiprocessing as mp
import os
import time
from pathlib import Path

import pytest

from scripts.excel import transaction
from scripts.excel.transaction import LockHeldError
from scripts.state import workflow_runner
from scripts.state.workflow_runner import ConcurrentMutationError

DEAD_PID = 2**22 + 12345  # above macOS/Linux pid_max defaults → never alive


def _hold(path: Path) -> int:
    """Flock ``path`` on a fresh open file description (a live peer)."""
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def _drop(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def _write_sentinel(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


# --- excel.lock (transaction.py) ---------------------------------------------

def test_excel_stale_looking_sentinel_does_not_evict_live_holder(tmp_path: Path) -> None:
    lock = tmp_path / "excel.lock"
    holder = _hold(lock)
    try:
        # A live holder whose sentinel LOOKS stale (dead pid, ancient ts): a long
        # write, a sleeping laptop, or a pid-namespace mismatch.
        _write_sentinel(lock, json.dumps({"pid": DEAD_PID, "ts": "2000-01-01T00:00:00.000000Z"}))
        with pytest.raises(LockHeldError):
            transaction._acquire_lock(lock)
        assert lock.exists()
    finally:
        _drop(holder)


def test_excel_release_keeps_inode_so_late_opener_still_excludes(tmp_path: Path) -> None:
    lock = tmp_path / "excel.lock"
    a = transaction._acquire_lock(lock)
    inode = os.stat(lock).st_ino
    b = os.open(str(lock), os.O_RDWR)  # B opened the path while A held it
    transaction._release_lock(a, lock)
    fcntl.flock(b, fcntl.LOCK_EX | fcntl.LOCK_NB)  # B now holds the lock
    try:
        assert lock.exists() and os.stat(lock).st_ino == inode
        with pytest.raises(LockHeldError):  # C must see B, not a fresh inode
            transaction._acquire_lock(lock)
    finally:
        _drop(b)


# --- run lock (workflow_runner.py) -------------------------------------------

def _run_lock(tmp_path: Path) -> tuple[Path, Path]:
    run = tmp_path / "run.json"
    return run, run.with_suffix(run.suffix + ".lock")


def test_run_lock_empty_sentinel_is_not_stale(tmp_path: Path) -> None:
    """A brand-new lockfile is empty until its holder writes pid/ts."""
    run, lock = _run_lock(tmp_path)
    holder = _hold(lock)  # created + flocked, payload not yet written
    try:
        with pytest.raises(ConcurrentMutationError):
            workflow_runner._acquire_run_lock(run)
    finally:
        _drop(holder)


def test_run_lock_dead_pid_sentinel_does_not_evict_live_holder(tmp_path: Path) -> None:
    run, lock = _run_lock(tmp_path)
    holder = _hold(lock)
    try:
        _write_sentinel(lock, json.dumps({"pid": DEAD_PID, "ts": "2000-01-01T00:00:00Z"}))
        with pytest.raises(ConcurrentMutationError):
            workflow_runner._acquire_run_lock(run)
    finally:
        _drop(holder)


def test_run_lock_release_keeps_inode(tmp_path: Path) -> None:
    run, lock = _run_lock(tmp_path)
    a = workflow_runner._acquire_run_lock(run)
    inode = os.stat(lock).st_ino
    b = os.open(str(lock), os.O_RDWR)
    workflow_runner._release_run_lock(a, run)
    fcntl.flock(b, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert lock.exists() and os.stat(lock).st_ino == inode
        with pytest.raises(ConcurrentMutationError):
            workflow_runner._acquire_run_lock(run)
    finally:
        _drop(b)


# --- three concurrent excel writers: never two holders ----------------------

def _writer(lock: str, log: str, rounds: int) -> None:
    for _ in range(rounds):
        fd = transaction._acquire_lock(Path(lock), acquire_blocking=True, deadline_seconds=20)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"in {os.getpid()}\n")
        time.sleep(0.002)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"out {os.getpid()}\n")
        transaction._release_lock(fd, Path(lock))


def test_three_concurrent_writers_never_overlap(tmp_path: Path) -> None:
    lock, log = tmp_path / "excel.lock", tmp_path / "holders.log"
    ctx = mp.get_context("fork")
    procs = [ctx.Process(target=_writer, args=(str(lock), str(log), 40)) for _ in range(3)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 * 40 * 2
    for enter, leave in zip(lines[::2], lines[1::2]):
        assert enter.startswith("in ") and leave == "out " + enter[3:], (
            f"two holders at once: {enter!r} then {leave!r}"
        )
