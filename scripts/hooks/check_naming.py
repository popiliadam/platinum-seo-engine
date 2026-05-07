#!/usr/bin/env python3
"""check_naming.py — Pre-commit hook: slug & filename regex guard.

Per rules/naming.md (§8.6): all identifiers must obey the project's single
naming contract. Drift typically enters as inconsistent slug casing across
skill folders, command filenames, schema filenames, and schema `$id` values.
This hook scans staged file paths and rejects naming violations.

Enforced patterns (additive — only patterns where pre-commit gating
provides high signal):

  skills/<slug>/SKILL.md       → folder slug `^[a-z][a-z0-9-]*$`
  commands/<filename>.md       → must match `pseo-<slug>.md`
  schemas/<name>.schema.json   → filename slug regex AND
                                 $id `http://platinum-seo-engine/schemas/<slug>`
                                 (ADR-012 HTTP authority)

Out of scope (existing CI tests cover):
  - run_id format runtime  → workflow-run schema validate
  - Excel sheet snake_case → tests/excel/* invariants
  - Python variable naming → linters

Usage:
    check_naming.py [--staged|--working-tree]

Exit codes:
    0  GREEN — no naming violations OR no in-scope file changes
    1  RED   — naming violations detected (commit blocked)
    2        usage error

Closes: Q-V1.5-HOOK-SCRIPTS-MISSING-01 (Y-03 — final 2 of 4 hooks).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
COMMAND_STEM_RE = re.compile(r"^pseo-[a-z][a-z0-9-]*$")
SCHEMA_ID_RE = re.compile(r"^http://platinum-seo-engine/schemas/[a-z][a-z0-9-]*$")


def _git_changed_files(*, staged: bool) -> list[str]:
    """Return list of changed file paths in cwd's git index/working tree."""
    cmd = ["git", "diff", "--name-only", "--diff-filter=AMR"]
    if staged:
        cmd.append("--cached")
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _check_skill_path(path: str, parts: list[str]) -> list[str]:
    """Validate skills/<slug>/.../SKILL.md folder slugs."""
    violations: list[str] = []
    for folder in parts[1:-1]:
        if not SLUG_RE.match(folder):
            violations.append(
                f"{path}: skill folder '{folder}' violates slug regex "
                f"'^[a-z][a-z0-9-]*$' (rules/naming.md)"
            )
    return violations


def _check_command_path(path: str, filename: str) -> list[str]:
    """Validate commands/<filename>.md must be pseo-<slug>.md."""
    stem = filename[:-3]  # strip .md
    if not COMMAND_STEM_RE.match(stem):
        return [
            f"{path}: command file must match 'pseo-<slug>.md' with slug "
            f"'^[a-z][a-z0-9-]*$' (rules/naming.md slash command prefix)"
        ]
    return []


def _check_schema_path(path: str, filename: str, repo_root: Path) -> list[str]:
    """Validate schemas/<name>.schema.json filename slug and $id field."""
    violations: list[str] = []
    name = filename[: -len(".schema.json")]
    if not SLUG_RE.match(name):
        violations.append(
            f"{path}: schema filename slug '{name}' violates regex "
            f"'^[a-z][a-z0-9-]*$' (rules/naming.md)"
        )
    full_path = repo_root / path
    if not full_path.is_file():
        return violations
    try:
        schema = json.loads(full_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return violations
    if not isinstance(schema, dict):
        return violations
    schema_id = schema.get("$id")
    if isinstance(schema_id, str) and schema_id.strip():
        if not SCHEMA_ID_RE.match(schema_id):
            violations.append(
                f"{path}: $id '{schema_id}' must match "
                f"'http://platinum-seo-engine/schemas/<slug>' "
                f"(rules/naming.md, ADR-012 HTTP authority)"
            )
    return violations


def check_path(path: str, repo_root: Path) -> list[str]:
    """Return list of violation messages for a single staged path."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "skills" and parts[-1] == "SKILL.md":
        return _check_skill_path(path, parts)
    if len(parts) == 2 and parts[0] == "commands" and parts[1].endswith(".md"):
        return _check_command_path(path, parts[1])
    if (
        len(parts) == 2
        and parts[0] == "schemas"
        and parts[1].endswith(".schema.json")
    ):
        return _check_schema_path(path, parts[1], repo_root)
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check_naming.py",
        description="Pre-commit guard: slug & filename regex per "
        "rules/naming.md (§8.6). Validates skill folder slugs, command "
        "filenames, schema filenames, and schema $id format.",
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
    args = ap.parse_args(argv)

    staged = not args.working_tree
    files = _git_changed_files(staged=staged)
    if not files:
        return 0

    repo_root = Path.cwd()
    all_violations: list[str] = []
    for f in files:
        all_violations.extend(check_path(f, repo_root))

    if not all_violations:
        return 0

    for msg in all_violations:
        print(f"ERROR: {msg}", file=sys.stderr)
    print(
        f"\nTotal naming violations: {len(all_violations)}", file=sys.stderr,
    )
    print(
        "Per rules/naming.md (§8.6): all identifiers must obey the single "
        "naming contract. See rule body for slug regex and per-file-type "
        "patterns.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
