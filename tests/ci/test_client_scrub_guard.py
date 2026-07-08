"""Regression guard: real client names must never re-enter the public repo.

The forbidden-name pattern lives OUTSIDE the repo (``CLIENT_SLUG_PATTERN``
env var locally, a repo secret in CI) so the guard cannot leak the very
names it guards. Unset env (fresh clones, forks) → the guard skips cleanly.

Companion to ci.yml step 5 (plugin-agnostik-grep), which enforces the same
invariant shell-side on ubuntu runners; this pytest twin runs wherever the
suite runs and uses Python ``re`` so ``\\b`` behaves identically on macOS.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_PATTERN = os.environ.get("CLIENT_SLUG_PATTERN", "")

# .mcp.json: the tracked copy is verified clean (4-server invariant, ADR-039);
# operators may carry local uncommitted server entries there, so the
# working-tree scan skips it — CI scans the committed copy via ci.yml step 5.
_ALLOWLIST = {".mcp.json"}

pytestmark = pytest.mark.skipif(
    not _PATTERN,
    reason="CLIENT_SLUG_PATTERN unset (operator/CI-only guard)",
)


def test_no_client_names_in_tracked_files():
    rx = re.compile(_PATTERN, re.IGNORECASE)
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    offenders = []
    for rel in tracked:
        if rel in _ALLOWLIST:
            continue
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binaries audited out-of-band; deleted-but-staged skip
        if rx.search(text):
            offenders.append(rel)
    assert not offenders, (
        f"forbidden client-name pattern matched {len(offenders)} tracked "
        f"file(s): {offenders[:10]}"
    )
