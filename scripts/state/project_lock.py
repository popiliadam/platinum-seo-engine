#!/usr/bin/env python3
"""project_lock.py — per-project NON-BLOCKING run-lock (AMO batch 4b).

The portfolio sweep (``scripts/orchestration/portfolio_runner.run_sweep``)
iterates the portfolio's projects in order and runs each project's owed workflow.
A project may ALSO be running in a bound single-project session (Faz-0: one
session ↔ one project) or in another sweep. To make the sweep safe alongside any
of those, each per-project run is guarded by its OWN advisory file lock:

    {workspace_root}/shared/locks/{slug}.lock

The lock is NON-BLOCKING (``fcntl.flock(LOCK_EX | LOCK_NB)``): if the project is
already running elsewhere, ``try_acquire`` returns ``None`` and the sweep SKIPS
that project — it NEVER waits. A sweep that blocked on a busy project would stall
the whole portfolio, so "skip, don't wait" is the load-bearing property.

Each ``try_acquire`` does its own ``os.open`` → its own open file description, so
``flock`` conflicts even across two acquires in one process (macOS/Linux flock is
keyed on the open file description, not the pid). This mirrors the independent-fd
discipline in ``portfolio_writer`` / ``events_writer``.

Discipline (rules/append-only-state.md — a lock is a transient advisory marker,
NOT a data log): the lockfile is opened, flocked, and closed; it is NEVER
``os.replace``'d (an inode swap would silently drop the advisory lock another
holder relies on) and carries no payload that must survive. The lock lives in
``shared/`` (portfolio-wide), alongside ``active.json`` / ``sessions/`` /
``cost_ledger.jsonl``.

Public API:
    project_lock_path(workspace_root, slug) -> Path
    try_acquire(workspace_root, slug) -> int | None
    release(fd) -> None
    held_lock(workspace_root, slug) -> contextmanager yielding (int | None)
"""

from __future__ import annotations

import fcntl
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

# Slug grammar (mirrors session_binding / pseo-active): start with a letter, then
# lowercase alphanumerics + hyphen. Anchored so it can never contain a path
# separator or traversal segment ("../").
_SLUG_RE = re.compile(r"[a-z][a-z0-9-]*")


class ProjectLockError(Exception):
    """Raised for an invalid slug (the only hard error this module raises)."""


def project_lock_path(workspace_root: Path | str, slug: str) -> Path:
    """Build {workspace_root}/shared/locks/{slug}.lock (mkdir -p shared/locks/).

    Validates the slug against ``^[a-z][a-z0-9-]*$`` BEFORE composing the path, so
    a malicious slug can never escape ``shared/locks/``.
    """
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
        raise ProjectLockError(
            f"invalid slug {slug!r}; must match ^[a-z][a-z0-9-]*$"
        )
    locks_dir = Path(workspace_root) / "shared" / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    return locks_dir / f"{slug}.lock"


def try_acquire(workspace_root: Path | str, slug: str) -> int | None:
    """Try to take the per-project lock WITHOUT blocking.

    Returns the held fd on success, or ``None`` when the lock is already held
    elsewhere (``BlockingIOError`` from the non-blocking flock) — the caller
    SKIPS that project. Never waits.
    """
    path = project_lock_path(workspace_root, slug)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # already held by another fd / process (EWOULDBLOCK) → skip, never wait
        os.close(fd)
        return None
    return fd


def release(fd: int | None) -> None:
    """Release a held lock fd (flock LOCK_UN + close). Error-safe / idempotent.

    Tolerates a None fd (the held_lock "skip" case) and a double-release (the
    context manager's finally re-calling on an already-closed fd).
    """
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


@contextmanager
def held_lock(workspace_root: Path | str, slug: str) -> Iterator[int | None]:
    """Context manager around the per-project lock.

    Yields the held fd, or ``None`` when the project is already running elsewhere
    (the caller treats ``None`` as "skip this project"). Always releases on exit.
    """
    fd = try_acquire(workspace_root, slug)
    try:
        yield fd
    finally:
        release(fd)


__all__: Iterable[str] = (
    "ProjectLockError",
    "project_lock_path",
    "try_acquire",
    "release",
    "held_lock",
)
