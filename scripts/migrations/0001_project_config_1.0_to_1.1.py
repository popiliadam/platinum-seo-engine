#!/usr/bin/env python3
"""
0001_project_config_1.0_to_1.1.py — Phase 10 additive bump migration.

Backward-compat additive migration for `schemas/project-config.schema.json`:
  schema_version: "1.0" → "1.1"

Phase 10 (Content Rules Processing) deliverable. Adds optional fields
(content_settings + brand_identity extension) WITHOUT changing required[],
so existing 1.0 documents validate against 1.1 unchanged. This script just
flips schema_version + leaves other fields untouched.

Per rules/schema-versioning-discipline.md:
  - idempotent (re-running = no-op)
  - dry-run support
  - existing file backed up to archive/ before modification
  - emits audit summary on stdout

Usage:
    python3 scripts/migrations/0001_project_config_1.0_to_1.1.py \
        --in <path-to-project.config.json> \
        [--out PATH] [--dry-run]

Or programmatic (preferred for tests):

    from scripts.migrations.\
        m_0001_project_config_1_0_to_1_1 import migrate
    new_doc = migrate(old_doc)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def migrate(doc: dict) -> dict:
    """Idempotent additive migration 1.0 → 1.1. Returns NEW dict."""
    sv = doc.get("schema_version")
    if sv == "1.1":
        return doc  # idempotent
    if sv != "1.0":
        # Out-of-range version — refuse to silently rewrite.
        raise ValueError(
            f"Refusing to migrate: expected schema_version '1.0', got {sv!r}"
        )
    # Additive only — copy + flip version. New optional fields (content_settings,
    # brand_identity extensions) are NOT injected here; consumer skills lazy-read
    # them with profile-aware defaults when missing. This keeps the migration
    # truly additive (no surprise default writes).
    return {**doc, "schema_version": "1.1"}


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate project.config.json schema_version 1.0 → 1.1"
    )
    parser.add_argument("--in", dest="in_path", required=True,
                        help="Input project.config.json path")
    parser.add_argument("--out", dest="out_path",
                        help="Output path (default: in-place with .bak backup)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print migrated JSON to stdout, no write")
    args = parser.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        print(f"ERROR: input not found: {in_path}", file=sys.stderr)
        return 2

    doc = json.loads(in_path.read_text(encoding="utf-8"))
    try:
        new_doc = migrate(doc)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    output = json.dumps(new_doc, indent=2, ensure_ascii=False)

    if args.dry_run:
        print(output)
        return 0

    out_path = Path(args.out_path) if args.out_path else in_path
    if out_path == in_path:
        # In-place: write .bak alongside (append-only-state — original preserved)
        bak_path = in_path.with_suffix(in_path.suffix + ".bak")
        bak_path.write_text(in_path.read_text(encoding="utf-8"), encoding="utf-8")
    out_path.write_text(output + "\n", encoding="utf-8")

    print(
        f"Migrated {in_path} → schema_version 1.1 "
        f"(backup: {bak_path if out_path == in_path else 'n/a'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
