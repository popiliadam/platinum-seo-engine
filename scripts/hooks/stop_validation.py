#!/usr/bin/env python3
"""Stop hook validation — runs at end of each assistant turn.

Performance budget: <1s (hook fires every turn — interaction velocity matters).

Checks (cheap, in priority order):
  1. Uncommitted git diff summary (drift hint)
  2. Open OQ count from docs/OPEN_QUESTIONS.md (governance pulse)

Output: short single-line summary to stderr (Claude Code shows it in transcript).
Failure mode: hook exits 0 even on errors — non-blocking by design.

Plugin agnostik: resolves repo via $CLAUDE_PLUGIN_ROOT (no slug literals).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or os.getcwd())


def git_drift_summary(repo: Path) -> str:
    """One-line uncommitted change summary, empty if clean or git unavailable."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
    if proc.returncode != 0:
        return ""
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return ""
    return f"git: {len(lines)} uncommitted change(s)"


def open_oq_count(repo: Path) -> int:
    """Count headers '### Q-...' that don't carry a RESOLVED marker on the same line.

    Returns 0 if file missing or unreadable. No crashes — failsafe.
    """
    oq_path = repo / "docs" / "OPEN_QUESTIONS.md"
    if not oq_path.exists():
        return 0
    try:
        text = oq_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    count = 0
    for line in text.splitlines():
        if line.startswith("### Q-") and "RESOLVED" not in line:
            count += 1
    return count


def main() -> int:
    repo = _repo_root()
    parts: list[str] = []
    drift = git_drift_summary(repo)
    if drift:
        parts.append(drift)
    oq = open_oq_count(repo)
    if oq > 0:
        parts.append(f"OQ: {oq} open")
    if parts:
        sys.stderr.write("[Stop validation] " + " | ".join(parts) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover — last-resort failsafe
        sys.stderr.write(f"[Stop validation] internal error: {exc!r}\n")
        sys.exit(0)
