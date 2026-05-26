#!/usr/bin/env python3
"""Migration #0005 — project-config schema v1.4 → v1.5 (SF MCP integration).

Additive migration for ``schemas/project-config.schema.json``:
  schema_version: "1.4" → "1.5"

Adds an OPTIONAL ``sf`` block to every project.config.json with sane
defaults for the Screaming Frog 24 native MCP integration (v1.8 Phase 1
D-SF-12, D-SF-18 path parameterization):

  - ``sf.mcp.enabled``: bool (default False)               — opt-in flag
  - ``sf.mcp.url``: uri (default http://127.0.0.1:11435/mcp) — D-SF-01 HTTP
  - ``sf.mcp.allowed_directory``: str | None (default None) — SF default
  - ``sf.mcp.crawl_config_path``: str | None (default None) — SF default
  - ``sf.mcp.max_wait_minutes``: int (default 180)        — DURUR-orch cap
  - ``sf.mcp.per_report_timeout_seconds``: int (default 300) — Q-11

Existing project.config keys are mutated in the *output dict* only (the
source dict is never modified — pure function). When ``sf`` is already
present (forward-compat with hand-edited configs) the migration leaves
nested values intact and only fills missing defaults via ``setdefault``.

Per ``rules/schema-versioning-discipline.md``:
  - idempotent (re-running on a 1.5 doc is a no-op)
  - strict version check (refuses to migrate sources outside {1.4, 1.5})
  - dry-run support
  - in-place writes leave a .bak backup
  - audit summary on stderr

Pattern reuse: 0001 + 0002 + 0003 + 0004 — same CLI shape (flags, exit
codes, pure ``migrate()``, .bak side-effect) so the directory stays
uniform. Test pattern mirrors tests/migrations/test_0004_*.py (direct
``from scripts.migrations.migration_0005_… import migrate`` per the
Python-importable naming established in Migration 0004).

Usage:
    python3 scripts/migrations/migration_0005_project_config_1_4_to_1_5.py \\
        --in <path-to-project.config.json> \\
        [--out PATH] [--dry-run]

Or programmatic (preferred for tests):

    from scripts.migrations.migration_0005_project_config_1_4_to_1_5 import migrate
    new_doc = migrate(old_doc)
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

#: Defaults injected into the sf.mcp block. Safe under D-SF-18 — operator
#: overrides any field per-project; F-15 governance (path isolation)
#: preserved via allowed_directory (kept null here so SF's own default
#: applies until the operator sets a path).
DEFAULT_SF_MCP: dict[str, object] = {
    "enabled": False,
    "url": "http://127.0.0.1:11435/mcp",
    "allowed_directory": None,
    "crawl_config_path": None,
    "max_wait_minutes": 180,
    "per_report_timeout_seconds": 300,
}


def migrate(doc: dict) -> dict:
    """Idempotent additive migration 1.4 → 1.5. Returns a NEW dict.

    Raises:
        ValueError: if ``doc["schema_version"]`` is neither "1.4" nor "1.5".
    """
    sv = doc.get("schema_version")
    if sv == "1.5":
        return doc  # idempotent — no-op on already-migrated input
    if sv != "1.4":
        raise ValueError(
            f"Refusing to migrate: expected schema_version '1.4', got {sv!r}"
        )

    out = copy.deepcopy(doc)
    out["schema_version"] = "1.5"

    sf = out.setdefault("sf", {})
    mcp = sf.setdefault("mcp", {})
    for field, default in DEFAULT_SF_MCP.items():
        # setdefault preserves any value the operator may have already set
        # (forward-compat with hand-edited sf blocks).
        mcp.setdefault(field, default)
    return out


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate project.config.json schema_version 1.4 → 1.5"
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
        f"Migrated {in_path} → schema_version 1.5 "
        f"(backup: {bak_path if bak_path else 'n/a'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
