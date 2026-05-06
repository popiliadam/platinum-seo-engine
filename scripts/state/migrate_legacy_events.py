#!/usr/bin/env python3
"""
migrate_legacy_events.py — split events.jsonl into strict + legacy (ADR-031).

Append-only state (rules/append-only-state.md) forbids in-place edits to
events.jsonl. Pre-Phase-14 events were written with conventions that
diverged from the current `events.schema.json` (e.g. event_type used as
a skill-name label rather than the closed 10-enum, audit events missing
`event_id`, extra fields like `credits_used`/`fail_count`).

This migration partitions the workspace events.jsonl into two files:

  events.jsonl          — schema-passing rows only (strict)
  events.jsonl.legacy   — schema-failing rows (READ-ONLY archive)

Both files are append-only going forward. Future writers (events_writer)
must produce strict rows; CI gate `tests/state/test_events_schema_compliance.py`
fails if a non-conforming row lands in events.jsonl after this migration.

Atomic write discipline (rules/excel-discipline.md mirror):
  - read input line by line
  - validate each row against events.schema.json
  - PASS rows → events.jsonl.tmp
  - FAIL rows → events.jsonl.legacy.tmp
  - rename .tmp pair atomically once both are written successfully

Outputs an audit-trail markdown report at outputs/reports/{date}-events-archive.md
documenting every legacy row with its line number and reason for archival.

Usage:
    python3 scripts/state/migrate_legacy_events.py \\
        --workspace ~/Documents/platinum-seo-workspace \\
        --project dentnotion \\
        [--dry-run]

Idempotent: re-running on a workspace whose events.jsonl is already 100%
strict (and events.jsonl.legacy already exists) is a no-op (exit 0,
"no migration needed" log).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "events.schema.json"


def _load_schema() -> jsonschema.Draft7Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft7Validator(schema)


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


def migrate(workspace: Path, project: str, dry_run: bool = False) -> int:
    project_pack = workspace / "projects" / project
    events_path = project_pack / "_state" / "events.jsonl"
    legacy_path = project_pack / "_state" / "events.jsonl.legacy"
    if not events_path.exists():
        print(f"ERROR: events.jsonl not found at {events_path}", file=sys.stderr)
        return 2

    validator = _load_schema()
    pass_lines, fail_records = _classify_lines(events_path, validator)

    print(
        f"PASS={len(pass_lines)} FAIL={len(fail_records)} "
        f"(input lines={len(pass_lines) + len(fail_records)})",
        file=sys.stderr,
    )

    if not fail_records:
        print("no legacy rows — events.jsonl already strict, no migration needed", file=sys.stderr)
        return 0

    if dry_run:
        for lineno, _raw, reason in fail_records:
            print(f"would archive L{lineno}: {reason[:120]}", file=sys.stderr)
        return 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    legacy_lines = [raw for _ln, raw, _reason in fail_records]

    # Atomic write: write both .tmp files first, then rename in pair.
    strict_tmp = events_path.with_suffix(events_path.suffix + ".tmp")
    legacy_tmp = legacy_path.with_suffix(legacy_path.suffix + ".tmp")
    strict_tmp.write_text("\n".join(pass_lines) + "\n", encoding="utf-8")

    # If legacy exists, append; else create.
    existing_legacy = legacy_path.read_text(encoding="utf-8") if legacy_path.exists() else ""
    legacy_payload = existing_legacy + ("\n" if existing_legacy and not existing_legacy.endswith("\n") else "")
    legacy_payload += "\n".join(legacy_lines) + "\n"
    legacy_tmp.write_text(legacy_payload, encoding="utf-8")

    strict_tmp.replace(events_path)
    legacy_tmp.replace(legacy_path)

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
    parser.add_argument("--project", required=True, help="Project slug (e.g. dentnotion)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be archived without writing")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser()
    return migrate(workspace, args.project, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(_cli())
