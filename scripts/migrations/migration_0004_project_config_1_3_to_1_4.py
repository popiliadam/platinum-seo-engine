#!/usr/bin/env python3
"""Migration #0004 — project-config schema v1.3 → v1.4 (bank entry enrichment).

Additive migration for ``schemas/project-config.schema.json``:
  schema_version: "1.3" → "1.4"

Enriches every entry in ``content_settings.experience_database`` and
``content_settings.original_research_database`` with four new fields
consumed by Phase 4 R-121 (rotation + density cap):

  - ``applicable_topics: list[str]``  — topic relevance filter
  - ``phrasings: list[str]``          — rotation variants for same fact
  - ``last_used_in_content_id``       — drift detection (initial None)
  - ``max_usage_per_month: int``      — density cap (default 3)

Existing bank entries are mutated in the *output dict* only (the source
dict is never modified — pure function). Missing banks are created as
empty arrays so downstream Stage C writes (Task 3.4) have a stable
target shape.

Per ``rules/schema-versioning-discipline.md``:
  - idempotent (re-running on a 1.4 doc is a no-op)
  - strict version check (refuses to migrate sources outside {1.3, 1.4})
  - dry-run support
  - in-place writes leave a .bak backup
  - audit summary on stderr

Pattern reuse: 0001 + 0002 + 0003 — same CLI shape (flags, exit codes,
pure ``migrate()``, .bak side-effect) so the directory stays uniform.

Naming note: this file uses Python-importable naming
(``migration_0004_project_config_1_3_to_1_4``) instead of the legacy
numeric-prefix style (``0003_project_config_1.2_to_1.3.py``) so tests
can ``from scripts.migrations.migration_0004_… import migrate`` directly.
Migration ordinal (#0004) is preserved in this docstring and in
``scripts/migrations/__init__.py`` ordering.

Usage:
    python3 scripts/migrations/migration_0004_project_config_1_3_to_1_4.py \\
        --in <path-to-project.config.json> \\
        [--out PATH] [--dry-run]

Or programmatic (preferred for tests):

    from scripts.migrations.migration_0004_project_config_1_3_to_1_4 import migrate
    new_doc = migrate(old_doc)
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

#: Defaults injected into every bank entry. Safe under R-121 — empty
#: topic filter means the entry is eligible everywhere but rotation
#: cap (3/month) prevents over-use even before operator scoping.
DEFAULT_BANK_ENTRY_NEW_FIELDS: dict[str, object] = {
    "applicable_topics": [],
    "phrasings": [],
    "last_used_in_content_id": None,
    "max_usage_per_month": 3,
}

#: Bank arrays this migration enriches. Both share the same entry schema.
_BANK_KEYS = ("experience_database", "original_research_database")


def migrate(doc: dict) -> dict:
    """Idempotent additive migration 1.3 → 1.4. Returns a NEW dict.

    Raises:
        ValueError: if ``doc["schema_version"]`` is neither "1.3" nor "1.4".
    """
    sv = doc.get("schema_version")
    if sv == "1.4":
        return doc  # idempotent — no-op on already-migrated input
    if sv != "1.3":
        raise ValueError(
            f"Refusing to migrate: expected schema_version '1.3', got {sv!r}"
        )

    out = copy.deepcopy(doc)
    out["schema_version"] = "1.4"

    cs = out.setdefault("content_settings", {})
    for bank_key in _BANK_KEYS:
        bank = cs.setdefault(bank_key, [])
        for entry in bank:
            for field, default in DEFAULT_BANK_ENTRY_NEW_FIELDS.items():
                # setdefault preserves any value the operator may have
                # already set (forward-compat with hand-edited entries).
                if isinstance(default, list):
                    entry.setdefault(field, list(default))
                else:
                    entry.setdefault(field, default)
    return out


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate project.config.json schema_version 1.3 → 1.4"
    )
    parser.add_argument(
        "--in", dest="in_path", required=True, help="Input project.config.json path"
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        help="Output path (default: in-place with .bak backup)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print migrated JSON to stdout, no write",
    )
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
        f"Migrated {in_path} → schema_version 1.4 "
        f"(backup: {bak_path if bak_path else 'n/a'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
