#!/usr/bin/env python3
"""
portfolio_writer.py — flock-guarded registrar for shared/portfolio.json.

Single writer of `{workspace_root}/shared/portfolio.json`, the append-only
portfolio registry that lists every bootstrapped project (slug, domain, market,
created_at). Extracted from the inline read-modify-write in
`skills/meta/init-project/SKILL.md` Step 6, which was lock-free and lost updates
when two parallel `init-project` runs raced: each read the same pre-state, each
appended only its own slug, and the second write clobbered the first.

Discipline (mirrors scripts/state/events_writer.py's fcntl.flock contract):
  - The ENTIRE read-modify-write runs under ONE blocking exclusive lock
    (fcntl.flock LOCK_EX) on the file, so concurrent registrars serialize and
    no update is ever lost. Each call opens its own fd → its own open file
    description → flock conflicts even across threads in one process.
  - Open O_RDWR|O_CREAT (not O_APPEND — this is a read-modify-write, not an
    append): read the whole JSON, rebuild it immutably, ftruncate + rewrite.
  - Immutability: a NEW portfolio dict is built each time; the parsed structure
    is never mutated in place.
  - Idempotent dedup on slug: an absent slug is appended; an already-present
    slug is a no-op (first write wins — created_at is preserved).
  - Exact shape preserved for all readers (e.g. monitoring-weekly):
    {"schema_version": "1.0", "projects": [{slug, domain, market, created_at}, …]},
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_SCHEMA_VERSION = "1.0"
_READ_CHUNK = 65536


class PortfolioWriterError(Exception):
    """Raised when shared/portfolio.json exists but is not a valid registry."""


def _empty_portfolio() -> dict[str, Any]:
    """The canonical empty registry written on first registration."""
    return {"schema_version": _SCHEMA_VERSION, "projects": []}


def _read_all(fd: int) -> bytes:
    """Read the whole file behind `fd`, starting from offset 0."""
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, _READ_CHUNK)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_or_empty(raw: bytes) -> dict[str, Any]:
    """Parse the existing registry, or return a fresh empty one when the file is
    empty/whitespace (the O_CREAT first-write case). Raise on malformed content
    rather than silently dropping a corrupt registry."""
    text = raw.decode("utf-8").strip()
    if not text:
        return _empty_portfolio()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PortfolioWriterError(f"portfolio.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
        raise PortfolioWriterError(
            "portfolio.json must be an object with a 'projects' array"
        )
    return data


def _with_project(
    data: dict[str, Any], slug: str, domain: str, market: str, created_at: str
) -> dict[str, Any]:
    """Return a NEW registry dict with `slug` registered (no mutation of `data`).
    Idempotent: if the slug is already present, returns `data` unchanged so the
    original entry — including its created_at — is preserved (first write wins)."""
    if slug in {p["slug"] for p in data["projects"]}:
        return data
    entry = {"slug": slug, "domain": domain, "market": market, "created_at": created_at}
    return {**data, "projects": [*data["projects"], entry]}


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
    runs while holding fcntl.flock(LOCK_EX) on the file, so two concurrent
    registrations can never observe the same pre-state and lose an update.
    Creates the shared/ dir and the file if missing. Returns the registry path.

    created_at is passed in (not computed) so the function is pure/testable; the
    skill supplies a UTC ISO-8601 timestamp at the call site.
    """
    shared_dir = Path(workspace_root) / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    path = shared_dir / "portfolio.json"

    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            data = _parse_or_empty(_read_all(fd))
            new_data = _with_project(data, slug, domain, market, created_at)
            payload = (
                json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    return path


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
