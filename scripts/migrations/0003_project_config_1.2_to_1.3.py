#!/usr/bin/env python3
"""
0003_project_config_1.2_to_1.3.py — v1.1 P0 brand_identity field rename forward.

Backward-compat additive migration for `schemas/project-config.schema.json`:
  schema_version: "1.2" → "1.3"

ADR-030: brand_identity tone/hitap → formality/pronoun_preference forward
rename. The new field NAMES are canonical; the old names are retained as
deprecated aliases (1-year shim, removable in v1.3+ only after Q-PHASE15-
BRAND-CONFIG-01 RESOLVED soak window).

Per brief constraint "workspace pronoun_preference/formality KORUNUR":
the new enums match the old enums byte-for-byte —
  pronoun_preference: ["sen", "siz"]  (was hitap)
  formality:          ["semi-pro", "conversational", "formal", "casual"]  (was tone)
— so this migration is a pure key rename, NOT a value remap. Existing
1.2 documents with `hitap`/`tone` set get their value copied verbatim
into the canonical `pronoun_preference`/`formality` field; the legacy
key is left in place under additionalProperties: false (the schema
retains both spellings during the deprecation window).

Per rules/schema-versioning-discipline.md:
  - idempotent (re-running on a 1.3 doc is a no-op)
  - dry-run support
  - existing file backed up to .bak before in-place modification
  - emits audit summary on stderr
  - refuses to migrate out-of-range source versions (silent rewrites
    forbidden)

Pattern reuse: 0001 + 0002 — same CLI shape (flags, exit codes, idempotent
pure migrate(), bak side-effect) to keep the migrations directory uniform.

Usage:
    python3 scripts/migrations/0003_project_config_1.2_to_1.3.py \\
        --in <path-to-project.config.json> \\
        [--out PATH] [--dry-run]

Or programmatic (preferred for tests):

    from scripts.migrations.\\
        m_0003_project_config_1_2_to_1_3 import migrate
    new_doc = migrate(old_doc)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def migrate(doc: dict) -> dict:
    """Idempotent additive migration 1.2 → 1.3. Returns NEW dict."""
    sv = doc.get("schema_version")
    if sv == "1.3":
        return doc  # idempotent
    if sv != "1.2":
        raise ValueError(
            f"Refusing to migrate: expected schema_version '1.2', got {sv!r}"
        )

    new_doc = dict(doc)
    new_doc["schema_version"] = "1.3"

    # brand_identity block is optional; absent → nothing to rename.
    bi = new_doc.get("brand_identity")
    if not isinstance(bi, dict):
        return new_doc

    new_bi = dict(bi)
    # Pure key rename — values preserved verbatim. ADR-030 §"KORUNUR".
    if "hitap" in new_bi and "pronoun_preference" not in new_bi:
        new_bi["pronoun_preference"] = new_bi["hitap"]
    if "tone" in new_bi and "formality" not in new_bi:
        new_bi["formality"] = new_bi["tone"]

    new_doc["brand_identity"] = new_bi
    return new_doc


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate project.config.json schema_version 1.2 → 1.3"
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
    bak_path: Path | None = None
    if out_path == in_path:
        bak_path = in_path.with_suffix(in_path.suffix + ".bak")
        bak_path.write_text(in_path.read_text(encoding="utf-8"), encoding="utf-8")
    out_path.write_text(output + "\n", encoding="utf-8")

    print(
        f"Migrated {in_path} → schema_version 1.3 "
        f"(backup: {bak_path if bak_path else 'n/a'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
