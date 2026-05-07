#!/usr/bin/env python3
"""check_excel_writer.py — Pre-commit hook: master.xlsx writer policy guard.

Per rules/excel-discipline.md (§8.5): `master-excel.xlsx` (or modern
lowercase `master.xlsx`) writes MUST go through `scripts/excel/transaction.py`
(atomic write + backup + invariant check). Direct manual edits via
LibreOffice/Excel/openpyxl bypass are FORBIDDEN.

Detection: scan staged diff for *.xlsx changes whose basename matches
`master.xlsx` (current canonical) or `master-excel.xlsx` (legacy alias).
Reject unless any of these "writer signals" are present:
  1. Commit message contains "transaction.py" string.
  2. Env var PSEO_EXCEL_WRITER=transaction.py (set by workspace runtime).
  3. --allow-direct-edit flag (escape hatch for migration/recovery only).

Usage:
    check_excel_writer.py [--staged|--working-tree] [--allow-direct-edit]
    check_excel_writer.py --commit-msg-file <path>      # override .git/COMMIT_EDITMSG

Exit codes:
    0  GREEN — no master.xlsx change OR change carries valid writer signal
    1  RED   — master.xlsx direct edit detected (rejection)
    2  Usage error

Closes: Q-V1.5-HOOK-SCRIPTS-MISSING-01 (option b — unqualified gap closure).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

MASTER_BASENAMES = {"master.xlsx", "master-excel.xlsx"}


def _git_diff_master_xlsx(*, staged: bool) -> list[str]:
    """Return list of master.xlsx-like paths in current git diff."""
    cmd = ["git", "diff", "--name-only", "--diff-filter=AMR"]
    if staged:
        cmd.append("--cached")
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    matches: list[str] = []
    for line in out.splitlines():
        name = Path(line.strip()).name.lower()
        if name in MASTER_BASENAMES:
            matches.append(line.strip())
    return matches


def _writer_signal_present(*, commit_msg_file: str | None) -> bool:
    """Detect any of the configured writer signals."""
    if os.getenv("PSEO_EXCEL_WRITER", "").strip() == "transaction.py":
        return True
    msg_path = Path(commit_msg_file or os.getenv(
        "PSEO_COMMIT_MSG_FILE", ".git/COMMIT_EDITMSG"))
    if msg_path.is_file():
        try:
            msg_text = msg_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            msg_text = ""
        if "transaction.py" in msg_text:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Pre-commit guard: master.xlsx writes must originate from "
                    "scripts/excel/transaction.py (rules/excel-discipline.md).",
    )
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--staged", action="store_true",
                       help="Check staged diff (default).")
    scope.add_argument("--working-tree", action="store_true",
                       help="Check unstaged working-tree diff.")
    ap.add_argument("--allow-direct-edit", action="store_true",
                    help="Bypass writer policy (migration/recovery only). "
                         "Documented warning emitted on stderr.")
    ap.add_argument("--commit-msg-file", default=None,
                    help="Override commit message file path "
                         "(default: $PSEO_COMMIT_MSG_FILE or .git/COMMIT_EDITMSG).")
    args = ap.parse_args(argv)

    staged = not args.working_tree  # default to staged
    matches = _git_diff_master_xlsx(staged=staged)
    if not matches:
        return 0

    if args.allow_direct_edit:
        print(
            "WARNING: master.xlsx direct edit allowed via --allow-direct-edit "
            "(rules/excel-discipline.md cross-link).",
            file=sys.stderr,
        )
        for path in matches:
            print(f"  - {path}", file=sys.stderr)
        return 0

    if _writer_signal_present(commit_msg_file=args.commit_msg_file):
        return 0

    print(
        "ERROR: master.xlsx change detected but no transaction.py writer signal.",
        file=sys.stderr,
    )
    for path in matches:
        print(f"  - {path}", file=sys.stderr)
    print(
        "Per rules/excel-discipline.md: master.xlsx writes MUST go through "
        "scripts/excel/transaction.py (atomic + backup + invariant check).",
        file=sys.stderr,
    )
    print(
        "If this is intentional (migration/recovery), rerun with "
        "--allow-direct-edit OR set PSEO_EXCEL_WRITER=transaction.py.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
