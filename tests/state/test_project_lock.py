"""tests/state/test_project_lock.py — AMO batch 4b per-project NON-BLOCKING run-lock.

TDD lock for scripts/state/project_lock.py: the per-project advisory file lock
the portfolio sweep (portfolio_runner) takes around each project's owed
workflow so a project already running elsewhere (a Faz-0 bound single-project
session, or another sweep) is SKIPPED — never WAITED on.

The contract the sweep relies on:
  - try_acquire returns the held fd on success, or None when the lock is already
    held (NON-BLOCKING: fcntl.flock LOCK_EX|LOCK_NB → BlockingIOError → None).
    macOS/Linux flock treats two descriptors from separate open() calls
    independently, so a SECOND try_acquire on the same slug — same process or a
    real second process — is denied and returns None.
  - release(fd) frees it; a subsequent try_acquire succeeds.
  - different slugs never contend (independent lockfiles).
  - held_lock(ws, slug) is a context manager yielding the fd (or None → skip)
    and always releasing on exit.

Discipline: tmp_path only — the real workspace is never touched.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.state import project_lock as pl

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# path + slug validation
# ---------------------------------------------------------------------------

def test_lock_path_shape_and_mkdir(tmp_path: Path) -> None:
    """project_lock_path is .../shared/locks/{slug}.lock and creates the dir."""
    path = pl.project_lock_path(tmp_path, "alpha-1")
    assert path == tmp_path / "shared" / "locks" / "alpha-1.lock"
    assert path.parent.is_dir(), "shared/locks/ must be mkdir -p'd"


def test_invalid_slug_rejected(tmp_path: Path) -> None:
    """A slug not matching ^[a-z][a-z0-9-]*$ is refused (no path traversal)."""
    for bad in ("Alpha", "1alpha", "../escape", "a/b", "a.b", "", "a_b"):
        with pytest.raises(pl.ProjectLockError):
            pl.project_lock_path(tmp_path, bad)


# ---------------------------------------------------------------------------
# acquire / skip-if-held / release — the NON-BLOCKING core
# ---------------------------------------------------------------------------

def test_acquire_returns_fd_and_creates_lockfile(tmp_path: Path) -> None:
    fd = pl.try_acquire(tmp_path, "proj")
    try:
        assert isinstance(fd, int)
        assert (tmp_path / "shared" / "locks" / "proj.lock").exists()
    finally:
        pl.release(fd)


def test_second_acquire_same_slug_returns_none_skip(tmp_path: Path) -> None:
    """A second try_acquire on the SAME slug is DENIED (None) — skip, not wait.

    Two separate os.open calls → two open file descriptions → flock(LOCK_NB)
    on the second is refused. This is the whole point: the sweep skips a busy
    project instead of blocking on it.
    """
    fd1 = pl.try_acquire(tmp_path, "busy")
    assert isinstance(fd1, int)
    try:
        fd2 = pl.try_acquire(tmp_path, "busy")   # already held → skip
        assert fd2 is None, "a held lock must return None (skip), never block"
    finally:
        pl.release(fd1)

    # after release, the slug is acquirable again
    fd3 = pl.try_acquire(tmp_path, "busy")
    assert isinstance(fd3, int), "release must make the slug acquirable again"
    pl.release(fd3)


def test_different_slugs_do_not_contend(tmp_path: Path) -> None:
    fd_a = pl.try_acquire(tmp_path, "alpha")
    fd_b = pl.try_acquire(tmp_path, "beta")
    try:
        assert isinstance(fd_a, int) and isinstance(fd_b, int)
        assert fd_a != fd_b
    finally:
        pl.release(fd_a)
        pl.release(fd_b)


def test_release_is_error_safe_on_double_release(tmp_path: Path) -> None:
    """release tolerates being called twice (the ctxmgr's finally is idempotent)."""
    fd = pl.try_acquire(tmp_path, "proj")
    pl.release(fd)
    pl.release(fd)        # must not raise even though fd is already closed


# ---------------------------------------------------------------------------
# the REAL second-holder proof — a separate PROCESS holds the lock
# ---------------------------------------------------------------------------

_HOLDER_SRC = '''\
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])                  # repo root -> import scripts.*
from scripts.state import project_lock as pl
ws, slug = Path(sys.argv[2]), sys.argv[3]
ready, gate = Path(sys.argv[4]), Path(sys.argv[5])
fd = pl.try_acquire(ws, slug)
if fd is None:
    sys.exit(4)                                  # unexpected: could not acquire
ready.write_text("held", encoding="utf-8")       # tell parent we hold it
while not gate.exists():                          # hold until parent releases us
    time.sleep(0.003)
pl.release(fd)
sys.exit(0)
'''


def test_skip_when_held_by_another_process(tmp_path: Path) -> None:
    """While a separate process holds the slug lock, the parent's try_acquire
    returns None (skip); once the holder exits, the parent can acquire."""
    worker = tmp_path / "_holder.py"
    worker.write_text(_HOLDER_SRC, encoding="utf-8")
    ws = tmp_path / "ws"
    ready, gate = tmp_path / "_ready", tmp_path / "_go"

    holder = subprocess.Popen(
        [sys.executable, str(worker), str(REPO_ROOT), str(ws), "shared-proj",
         str(ready), str(gate)]
    )
    try:
        deadline = 0
        while not ready.exists() and deadline < 1000:   # wait until it holds
            deadline += 1
            __import__("time").sleep(0.003)
        assert ready.exists(), "holder process never acquired the lock"

        # the lock is held by another process → we must SKIP (None)
        assert pl.try_acquire(ws, "shared-proj") is None
    finally:
        gate.write_text("go", encoding="utf-8")          # release the holder
        assert holder.wait() == 0, "holder exited non-zero"

    # holder released → we can acquire now
    fd = pl.try_acquire(ws, "shared-proj")
    assert isinstance(fd, int)
    pl.release(fd)


# ---------------------------------------------------------------------------
# held_lock context manager
# ---------------------------------------------------------------------------

def test_held_lock_yields_fd_and_releases(tmp_path: Path) -> None:
    with pl.held_lock(tmp_path, "ctx") as fd:
        assert isinstance(fd, int)
        # while held, a second acquire is denied
        assert pl.try_acquire(tmp_path, "ctx") is None
    # after the block, the lock is released → acquirable again
    fd2 = pl.try_acquire(tmp_path, "ctx")
    assert isinstance(fd2, int)
    pl.release(fd2)


def test_held_lock_yields_none_when_busy(tmp_path: Path) -> None:
    """When the slug is already held, held_lock yields None (the sweep skips)."""
    fd = pl.try_acquire(tmp_path, "busy")
    try:
        with pl.held_lock(tmp_path, "busy") as inner:
            assert inner is None, "a busy slug must yield None from held_lock"
    finally:
        pl.release(fd)


# ---------------------------------------------------------------------------
# public API surface
# ---------------------------------------------------------------------------

def test_public_api_in_all() -> None:
    for name in ("project_lock_path", "try_acquire", "release", "held_lock",
                 "ProjectLockError"):
        assert name in pl.__all__, f"{name} missing from __all__"
