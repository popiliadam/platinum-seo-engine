#!/usr/bin/env python3
"""
portfolio_writer.py — flock-guarded registrar for shared/portfolio.json.

Single writer of `{workspace_root}/shared/portfolio.json`, the append-only
portfolio registry that lists every bootstrapped project (slug, domain, market,
created_at). Extracted from the inline read-modify-write in
`skills/meta/init-project/SKILL.md` Step 6, which was lock-free and lost updates
when two parallel `init-project` runs raced: each read the same pre-state, each
appended only its own slug, and the second write clobbered the first.

Discipline:
  - The ENTIRE read-modify-write runs under ONE blocking exclusive flock on a
    separate, never-unlinked sentinel ``shared/portfolio.json.lock``, so
    concurrent registrars serialize and no update is ever lost. Each call opens
    its own fd → its own open file description → flock conflicts even across
    threads in one process.
  - Crash-safe (V-06): the new JSON goes to a temp file in ``shared/`` (fsync),
    then ``os.replace`` swaps it in and the dir is fsynced. This is a mutable
    registry, not a log, so a rename is right here — the old in-place
    truncate+rewrite left a 0-byte file on a crash/full disk.
  - A MISSING file is a first registration; an EXISTING empty file is an error
    (it means a crash ate the registry — re-registering one project would
    silently drop every other one).
  - Immutability: a NEW portfolio dict is built each time; the parsed structure
    is never mutated in place.
  - Idempotent dedup on slug: an absent slug is appended; an already-present
    slug is a no-op (first write wins — created_at is preserved).
  - Exact shape preserved for all readers (e.g. monitoring-weekly):
    {"schema_version": "1.0", "active_projects": [{slug, domain, market, created_at}, …]},
    json.dumps(..., ensure_ascii=False, indent=2) + trailing newline.

Public API:
    register_project(workspace_root, slug, domain, market, *, created_at) -> Path

CLI (optional convenience; the skill imports register_project directly):
    python3 -m scripts.state.portfolio_writer register <slug> \
        --domain <url> --market <cc> --workspace <root> [--created-at <iso>]

Plugin-agnostik: slug/domain/market are parameters; no project literals.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_SCHEMA_VERSION = "1.0"


class PortfolioWriterError(Exception):
    """Raised when shared/portfolio.json exists but is not a valid registry."""


def _empty_portfolio() -> dict[str, Any]:
    """The canonical empty registry written on first registration."""
    return {"schema_version": _SCHEMA_VERSION, "active_projects": []}


def _parse(raw: bytes) -> dict[str, Any]:
    """Parse the existing registry. Raise on empty or malformed content rather
    than silently replacing it with a one-project registry."""
    text = raw.decode("utf-8").strip()
    if not text:
        raise PortfolioWriterError(
            "portfolio.json exists but is empty — restore it from a backup "
            "before registering (an empty file is never treated as a new registry)"
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PortfolioWriterError(f"portfolio.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("active_projects"), list):
        raise PortfolioWriterError(
            "portfolio.json must be an object with an 'active_projects' array"
        )
    return data


def _with_project(
    data: dict[str, Any], slug: str, domain: str, market: str, created_at: str
) -> dict[str, Any]:
    """Return a NEW registry dict with `slug` registered (no mutation of `data`).
    Idempotent: if the slug is already present, returns `data` unchanged so the
    original entry — including its created_at — is preserved (first write wins)."""
    if slug in {p["slug"] for p in data["active_projects"]}:
        return data
    entry = {"slug": slug, "domain": domain, "market": market, "created_at": created_at}
    return {**data, "active_projects": [*data["active_projects"], entry]}


def register_project(
    workspace_root: str | os.PathLike[str],
    slug: str,
    domain: str,
    market: str,
    *,
    created_at: str,
) -> Path:
    """Register `slug` in {workspace_root}/shared/portfolio.json, append-only.

    The whole read-modify-write — read current registry, dedup, append, write —
    runs while holding fcntl.flock(LOCK_EX) on the lock sentinel, so two concurrent
    registrations can never observe the same pre-state and lose an update.
    Creates the shared/ dir and the file if missing. Returns the registry path.

    created_at is passed in (not computed) so the function is pure/testable; the
    skill supplies a UTC ISO-8601 timestamp at the call site.
    """
    shared_dir = Path(workspace_root) / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    path = shared_dir / "portfolio.json"

    lock_fd = os.open(str(shared_dir / "portfolio.json.lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = _parse(path.read_bytes()) if path.exists() else _empty_portfolio()
            new_data = _with_project(data, slug, domain, market, created_at)
            payload = (
                json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            _atomic_replace(path, payload)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)
    return path


def _atomic_replace(path: Path, payload: bytes) -> None:
    """temp file in the same dir → fsync → os.replace → dir fsync. On any failure
    the temp file is removed and the old registry is untouched."""
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=".portfolio-", suffix=".tmp", dir=str(path.parent))
    try:
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(tmp_fd, view):]
            os.fsync(tmp_fd)
        finally:
            os.close(tmp_fd)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


# ---------------------------------------------------------------------------
# CLI (optional convenience)
# ---------------------------------------------------------------------------

def _utc_iso_z() -> str:
    """UTC ISO 8601 with 'Z' suffix — the CLI default when --created-at omitted."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.state.portfolio_writer",
        description="Register a project in shared/portfolio.json (flock-guarded).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register", help="append-only register a project slug")
    reg.add_argument("slug", help="project slug (kebab-case)")
    reg.add_argument("--domain", required=True, help="project root URL")
    reg.add_argument("--market", required=True, help="ISO 3166-1 alpha-2 code")
    reg.add_argument("--workspace", required=True, help="workspace root directory")
    reg.add_argument(
        "--created-at", default=None,
        help="UTC ISO-8601 timestamp (default: now)",
    )
    args = parser.parse_args(argv)

    path = register_project(
        args.workspace, args.slug, args.domain, args.market,
        created_at=args.created_at or _utc_iso_z(),
    )
    print(str(path))
    return 0


__all__: Iterable[str] = (
    "register_project",
    "PortfolioWriterError",
)


if __name__ == "__main__":
    sys.exit(_main())
