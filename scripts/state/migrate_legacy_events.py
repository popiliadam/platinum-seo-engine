#!/usr/bin/env python3
"""
migrate_legacy_events.py — split events.jsonl into strict + legacy (ADR-031).

Append-only state (rules/append-only-state.md) forbids in-place edits to
events.jsonl for normal writers — this one-time operator migration is the
narrow exception, performed under the exclusive append flock with a .bak
backup first (see the crash-safety section below). Pre-Phase-14 events were
written with conventions that diverged from the current `events.schema.json`
(e.g. event_type used as a skill-name label rather than the closed 10-enum,
audit events missing `event_id`, extra fields like `credits_used`/`fail_count`).

This migration partitions the workspace events.jsonl into two files:

  events.jsonl          — schema-passing rows only (strict)
  events.jsonl.legacy   — schema-failing rows (READ-ONLY archive)

Both files are append-only going forward. Future writers (events_writer)
must produce strict rows; CI gate `tests/state/test_events_schema_compliance.py`
fails if a non-conforming row lands in events.jsonl after this migration.

Crash-safety + concurrency discipline (rules/append-only-state.md):
  - hold an exclusive fcntl.flock on events.jsonl across the whole
    read → classify → write section (the SAME lock the events_writer
    append path takes — it flocks the data file's own fd), so a concurrent
    append cannot be silently dropped.
  - back up the complete original events.jsonl to events.jsonl.bak first
    (this is what makes the non-atomic in-place rewrite below crash-safe).
  - commit the PRESERVING write (FAIL rows → events.jsonl.legacy via
    tmp+fsync+replace, a separate file) FIRST; then rewrite the LOSSY strict
    ledger (PASS rows) IN PLACE on the locked inode + fsync. os.replace is
    deliberately NOT used for events.jsonl: swapping the inode would orphan a
    concurrent appender's lock (which is held on the data file itself) and
    drop its write. A crash before the rewrite loses nothing; a crash during
    it leaves a partial events.jsonl recoverable from .bak — never lost rows.

Outputs an audit-trail markdown report at outputs/reports/{date}-events-archive.md
documenting every legacy row with its line number and reason for archival.

Usage:
    python3 scripts/state/migrate_legacy_events.py \\
        --workspace ~/Documents/platinum-seo-workspace \\
        --project demo-dental \\
        [--dry-run]

Idempotent: re-running on a workspace whose events.jsonl is already 100%
strict (and events.jsonl.legacy already exists) is a no-op (exit 0,
"no migration needed" log).
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[2]
# Allow the bare-script invocation `python3 scripts/state/migrate_legacy_events.py`
# (this one-shot ADR-031 migration is run directly, not only via `python -m`):
# ensure the repo root is importable so `scripts.*` resolves the same way it does
# under `python -m` / pytest.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation.validate_schema import build_validator  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schemas" / "events.schema.json"


def _load_schema() -> jsonschema.Draft7Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    # build_validator (not a raw Draft7Validator) so events.schema.json's
    # timestamp format:date-time is ENFORCED with the strict UTC '…Z' checker —
    # the migration then partitions EXACTLY like the events_writer append path
    # (P1-02 / time-discipline §8.10), instead of admitting a naive row as strict.
    return build_validator(schema)


def _classify_lines(events_path: Path, validator: jsonschema.Draft7Validator):
    """Return (pass_lines, fail_records) where each fail_record is
    (line_number, original_line, joined_error_messages)."""
    pass_lines: list[str] = []
    fail_records: list[tuple[int, str, str]] = []
    for lineno, raw in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            fail_records.append((lineno, raw, f"json-decode: {exc.msg}"))
            continue
        errors = list(validator.iter_errors(event))
        if errors:
            joined = "; ".join(e.message[:140] for e in errors[:3])
            fail_records.append((lineno, raw, joined))
        else:
            pass_lines.append(raw)
    return pass_lines, fail_records


def _write_archive_report(
    project_pack: Path,
    fail_records: list[tuple[int, str, str]],
    today: str,
) -> Path:
    reports_dir = project_pack / "outputs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"{today}-events-archive.md"

    lines = [
        f"# Events Archive Report — {today}",
        "",
        f"Migration: `scripts/state/migrate_legacy_events.py` (ADR-031)",
        f"Source: `{project_pack}/_state/events.jsonl`",
        f"Archived rows: **{len(fail_records)}**",
        "",
        "| Line | event_id (truncated) | Reason |",
        "|---:|---|---|",
    ]
    for lineno, raw, reason in fail_records:
        try:
            ev = json.loads(raw)
            eid = ev.get("event_id") or "<missing>"
        except Exception:
            eid = "<unparsable>"
        lines.append(f"| {lineno} | `{eid[:40]}` | {reason[:140]} |")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _fsync_path(path: Path) -> None:
    """Best-effort fsync of a file or directory for crash durability.

    Mirrors the durability discipline of transaction._atomic_save /
    workflow_runner._atomic_write_json. Never raises — durability is a
    hardening guarantee, not a correctness precondition, and some platforms
    reject directory fsync.
    """
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_commit(tmp: Path, dst: Path) -> None:
    """fsync ``tmp``, atomically rename it over ``dst``, then fsync the parent dir.

    os.replace cannot make a *pair* of files atomic, so callers commit the
    PRESERVING write before the LOSSY one (see ``migrate``); this helper makes
    each individual rename crash-durable.
    """
    _fsync_path(tmp)
    tmp.replace(dst)
    _fsync_path(dst.parent)


def _rewrite_locked_file(fd: int, content: str) -> None:
    """Rewrite an flock-held file IN PLACE on its existing inode, then fsync.

    os.replace would swap the inode and orphan the lock that the events_writer
    append path holds on the data file ITSELF (events_writer flocks events.jsonl
    directly, not a separate sentinel the way transaction.py uses excel.lock).
    A concurrent appender blocked on that lock would wake after the rename and
    write into the unlinked old inode, losing its row. Rewriting in place keeps
    the inode stable so the lock stays meaningful. This is NOT crash-atomic on
    its own — callers MUST back up the original first (see migrate's .bak).
    """
    data = content.encode("utf-8")
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    off = 0
    while off < len(data):
        off += os.write(fd, data[off:])
    os.fsync(fd)


def migrate(workspace: Path, project: str, dry_run: bool = False) -> int:
    project_pack = workspace / "projects" / project
    events_path = project_pack / "_state" / "events.jsonl"
    legacy_path = project_pack / "_state" / "events.jsonl.legacy"
    if not events_path.exists():
        print(f"ERROR: events.jsonl not found at {events_path}", file=sys.stderr)
        return 2

    validator = _load_schema()

    # dry-run is read-only: classify + report what would happen, touch nothing.
    if dry_run:
        pass_lines, fail_records = _classify_lines(events_path, validator)
        print(
            f"PASS={len(pass_lines)} FAIL={len(fail_records)} "
            f"(input lines={len(pass_lines) + len(fail_records)})",
            file=sys.stderr,
        )
        if not fail_records:
            print("no legacy rows — events.jsonl already strict, no migration needed", file=sys.stderr)
            return 0
        for lineno, _raw, reason in fail_records:
            print(f"would archive L{lineno}: {reason[:120]}", file=sys.stderr)
        return 0

    # Mutating path. Hold the SAME exclusive flock the events_writer append path
    # acquires on events.jsonl (it flocks the data file's own fd), across the whole
    # read → classify → write critical section, so a concurrent append to the
    # append-only ledger cannot be silently dropped. The fd is O_RDWR because the
    # strict ledger is rewritten IN PLACE on this very inode (see below).
    lock_fd = os.open(str(events_path), os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        original_text = events_path.read_text(encoding="utf-8")
        pass_lines, fail_records = _classify_lines(events_path, validator)
        print(
            f"PASS={len(pass_lines)} FAIL={len(fail_records)} "
            f"(input lines={len(pass_lines) + len(fail_records)})",
            file=sys.stderr,
        )
        if not fail_records:
            print("no legacy rows — events.jsonl already strict, no migration needed", file=sys.stderr)
            return 0

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        legacy_lines = [raw for _ln, raw, _reason in fail_records]

        # Back up the COMPLETE original ledger before any overwrite, so the
        # pre-migration state is always recoverable (append-only-state). This is
        # what makes the non-atomic in-place rewrite below safe against a crash.
        backup_path = events_path.with_suffix(events_path.suffix + ".bak")
        backup_path.write_text(original_text, encoding="utf-8")
        _fsync_path(backup_path)

        # Commit the PRESERVING write (legacy archive — a separate file, safe to
        # rename-replace) FIRST, then rewrite the LOSSY strict ledger IN PLACE
        # last. Ordering + the .bak above are the crash-safety contract: a crash
        # before the in-place rewrite loses nothing; a crash during it leaves a
        # partial events.jsonl that is recoverable from .bak — never lost rows.
        existing_legacy = legacy_path.read_text(encoding="utf-8") if legacy_path.exists() else ""
        legacy_payload = existing_legacy + ("\n" if existing_legacy and not existing_legacy.endswith("\n") else "")
        legacy_payload += "\n".join(legacy_lines) + "\n"
        legacy_tmp = legacy_path.with_suffix(legacy_path.suffix + ".tmp")
        legacy_tmp.write_text(legacy_payload, encoding="utf-8")
        _atomic_commit(legacy_tmp, legacy_path)

        # Rewrite the strict ledger in place on the locked inode (NOT os.replace,
        # which would swap the inode and orphan a concurrent appender's lock).
        _rewrite_locked_file(lock_fd, "\n".join(pass_lines) + "\n")
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(lock_fd)

    report_path = _write_archive_report(project_pack, fail_records, today)
    print(f"archived {len(fail_records)} rows → {legacy_path}", file=sys.stderr)
    print(f"audit report: {report_path}", file=sys.stderr)
    return 0


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Partition events.jsonl into strict + legacy (ADR-031)"
    )
    parser.add_argument("--workspace", required=True,
                        help="Path to workspace root (e.g. ~/Documents/platinum-seo-workspace)")
    parser.add_argument("--project", required=True, help="Project slug (e.g. demo-dental)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be archived without writing")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser()
    return migrate(workspace, args.project, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(_cli())
