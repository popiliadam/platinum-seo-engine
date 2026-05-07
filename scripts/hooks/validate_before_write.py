#!/usr/bin/env python3
"""validate_before_write.py — Pre-commit hook: schema-first paired update guard.

Per rules/schema-first.md (§8.2): a data shape must have a schema in
schemas/{name}.schema.json BEFORE the kod that writes it lands. When a
staged kod file references a schema by path
(`schemas/<slug>.schema.json`), the schema MUST also be present in the
same commit — either pre-existing AND staged for re-emission, or being
added/modified now. The hook scans staged kod files for schema path
references and rejects commits that break paired-update discipline.

"Kod" file detection (paths that emit data writes):
    scripts/state/, scripts/excel/, scripts/discovery/,
    scripts/planning/, scripts/validation/

Out of scope (intentional):
    tests/, docs/, rules/, memory/
    scripts/hooks/, scripts/util/, scripts/release/, scripts/ci/, ...
    (these don't author shape-aware writes; modifying them does not
    risk shape drift)

Usage:
    validate_before_write.py [--staged|--working-tree] [--allow-kod-only]

Escape hatch:
    --allow-kod-only — explicit bypass for non-shape refactors (rename,
    type annotations, comments). Emits documented warning.

Exit codes:
    0  GREEN — no violations OR no in-scope file changes
    1  RED   — paired-update violation (commit blocked)
    2        usage error

Closes: Q-V1.5-HOOK-SCRIPTS-MISSING-01 (Y-04 — final 2 of 4 hooks).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

KOD_PREFIXES = (
    "scripts/state/",
    "scripts/excel/",
    "scripts/discovery/",
    "scripts/planning/",
    "scripts/validation/",
)

SCHEMA_REF_RE = re.compile(r"schemas/[a-z][a-z0-9-]*\.schema\.json")


def _git_changed_files(*, staged: bool) -> list[str]:
    cmd = ["git", "diff", "--name-only", "--diff-filter=AMR"]
    if staged:
        cmd.append("--cached")
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _is_kod_path(path: str) -> bool:
    """Return True if path is a Python kod file in a write-emitting dir."""
    if not path.endswith(".py"):
        return False
    return any(path.startswith(prefix) for prefix in KOD_PREFIXES)


def _find_schema_refs(content: str) -> set[str]:
    """Return set of `schemas/<slug>.schema.json` paths referenced in content."""
    return set(SCHEMA_REF_RE.findall(content))


def collect_violations(
    files: list[str], repo_root: Path,
) -> list[tuple[str, str]]:
    """Return list of (kod_path, schema_path) violations.

    A violation is recorded when a staged kod file references a schema
    path that is not itself in the staged file set.
    """
    file_set = set(files)
    violations: list[tuple[str, str]] = []
    for f in files:
        if not _is_kod_path(f):
            continue
        full_path = repo_root / f
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for schema_path in sorted(_find_schema_refs(content)):
            if schema_path not in file_set:
                violations.append((f, schema_path))
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="validate_before_write.py",
        description="Pre-commit guard: schema-first paired update per "
        "rules/schema-first.md (§8.2). When kod modifies/adds files "
        "referencing schemas/<slug>.schema.json, the schema must be in "
        "the same commit (paired update).",
    )
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument(
        "--staged", action="store_true",
        help="Check staged diff (default).",
    )
    scope.add_argument(
        "--working-tree", action="store_true",
        help="Check unstaged working-tree diff.",
    )
    ap.add_argument(
        "--allow-kod-only", action="store_true",
        help="Bypass strict pairing for non-shape refactors only "
        "(rename, type annotations, comments). Emits stderr warning.",
    )
    args = ap.parse_args(argv)

    staged = not args.working_tree
    files = _git_changed_files(staged=staged)
    if not files:
        return 0

    repo_root = Path.cwd()
    violations = collect_violations(files, repo_root)

    if not violations:
        return 0

    if args.allow_kod_only:
        print(
            "WARNING: schema-first paired-update bypass via --allow-kod-only.",
            file=sys.stderr,
        )
        for kod_path, schema_path in violations:
            print(f"  - {kod_path} → {schema_path}", file=sys.stderr)
        print(
            "Per rules/schema-first.md: this should only be used for "
            "non-shape refactors (rename, type annotations, comments).",
            file=sys.stderr,
        )
        return 0

    for kod_path, schema_path in violations:
        print(
            f"ERROR: {kod_path}: references {schema_path} but the schema "
            f"file is not staged in this commit (paired-update required).",
            file=sys.stderr,
        )
    print(
        f"\nTotal schema-first violations: {len(violations)}",
        file=sys.stderr,
    )
    print(
        "Per rules/schema-first.md (§8.2): when kod referencing a schema "
        "lands, the schema must be in the same commit. If this is a "
        "non-shape refactor, rerun with --allow-kod-only.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
