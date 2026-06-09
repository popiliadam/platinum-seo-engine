#!/usr/bin/env python3
"""scan_pending_secret.py — PreToolUse pending-bytes secret gate (runtime hook).

Wired into ``hooks/pre-tool-use.json`` (matcher ``Edit|Write|NotebookEdit|Bash``).
It extracts the LITERAL pending content of a Write/Edit/NotebookEdit (and a
write-shaped Bash command) and pipes it to the canonical scanner
``scripts/security/check_secrets.sh --scan-stdin <file_path>``. On a scanner
FAIL it ``sys.exit(2)`` so Claude Code blocks the write BEFORE the secret lands
on disk — closing the gap the post-hoc ``--changed-since`` scan leaves open
(that scan sources its file list from git, so a not-yet-written or
gitignored-non-.env target is invisible to it; hostile-audit finding #1).

Single source of truth: this hook re-implements NO secret pattern. It delegates
to the SAME 16-class inventory in ``check_secrets.sh`` that CI and the event
redactor mirror, so the three surfaces cannot drift. The scanner's gitignored
local ``.env`` carve-out (WARN/allow) is preserved exactly by passing the
intended target as the ``--scan-stdin`` pseudo-path.

Audit ref: docs/audits/2026-06-09_hostile_audit_claude_code_prompt.md (Finding 1).

Contract (mirrors scripts/hooks/validate_content_write.py):
    * Scope — Write (``content``), Edit (``new_string``), NotebookEdit
      (``new_source``), and a write-shaped Bash command (heredoc ``<<``,
      redirect ``>``/``>>``, or ``tee``). Any other tool, or a read-shaped Bash
      command, is skipped (exit 0). The post-hoc ``--changed-since`` scan + the
      PostToolUse ``ai_disclosure_rescan`` quarantine remain as backstops for
      Bash forms this best-effort extractor cannot see.
    * Verdict — scanner exit 1 (secret) → exit 2 (BLOCK); exit 0 → allow.
    * Failure — fail-OPEN on any internal error (scanner missing, bad JSON,
      timeout): a buggy gate must not brick all edits, and the incremental scan
      backstops it. A definitive secret hit is fail-CLOSED (exit 2).
    * Security — only the scanner's REDACTED label report is forwarded; the
      matched content is never echoed (same invariant as the scanner).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
_SCANNER = Path(_PLUGIN_ROOT) / "scripts" / "security" / "check_secrets.sh"

# A Bash command "writes" if it heredocs, redirects to a file, or tees. We only
# scan write-shaped Bash (the leak surface) to avoid blocking read-only commands
# that merely mention a secret-shaped string in an argument.
_BASH_WRITE_RE = re.compile(r"<<|>>?|\btee\b")


def extract_pending(payload: object) -> tuple[str, str] | None:
    """Return ``(content, pseudo_path)`` to scan, or ``None`` to skip. Pure.

    ``pseudo_path`` is the intended write target (drives the scanner's
    gitignored-.env carve-out); it is empty for Bash, where no reliable single
    target exists, so any secret-shape in a write-shaped command is a FAIL.
    """
    if not isinstance(payload, dict):
        return None
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None

    if tool == "Write":
        content = tool_input.get("content") or ""
        path = tool_input.get("file_path") or tool_input.get("path") or ""
    elif tool == "Edit":
        content = tool_input.get("new_string") or ""
        path = tool_input.get("file_path") or tool_input.get("path") or ""
    elif tool == "NotebookEdit":
        content = tool_input.get("new_source") or ""
        path = tool_input.get("notebook_path") or ""
    elif tool == "Bash":
        command = tool_input.get("command") or ""
        if command and _BASH_WRITE_RE.search(command):
            return (str(command), "")
        return None
    else:
        return None

    if not content:
        return None
    return (str(content), str(path))


def run_scan(
    content: str,
    pseudo_path: str,
    *,
    scanner: Path = _SCANNER,
    cwd: str | None = None,
    timeout: float = 30.0,
) -> tuple[int, str, str]:
    """Run ``check_secrets.sh --scan-stdin [pseudo_path]`` over ``content``.

    Returns ``(returncode, stdout, stderr)``. cwd defaults to the hook's cwd
    (the project dir) so the scanner's ``git check-ignore`` .env carve-out
    resolves against the active repository.
    """
    args = ["bash", str(scanner), "--scan-stdin"]
    if pseudo_path:
        args.append(pseudo_path)
    proc = subprocess.run(
        args, input=content, capture_output=True, text=True, timeout=timeout, cwd=cwd
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        payload = json.loads(raw)
    except Exception as exc:  # malformed payload — never brick the write
        sys.stderr.write(
            f"[scan-pending-secret] WARNING bad payload, allowing (fail-open): {exc!r}\n"
        )
        return 0

    extracted = extract_pending(payload)
    if extracted is None:
        return 0
    content, pseudo_path = extracted

    if not _SCANNER.exists():
        sys.stderr.write(
            "[scan-pending-secret] WARNING canonical scanner not found, "
            "allowing (fail-open); --changed-since scan still applies\n"
        )
        return 0

    try:
        rc, out, _err = run_scan(content, pseudo_path)
    except Exception as exc:  # scanner exec/timeout — fail-open, backstops apply
        sys.stderr.write(
            f"[scan-pending-secret] WARNING scan error, allowing (fail-open): {exc!r}\n"
        )
        return 0

    if rc == 1:
        target = pseudo_path or "<bash command>"
        sys.stderr.write(
            f"[scan-pending-secret] BLOCKED — secret-shaped bytes in pending "
            f"write to {target}:\n"
        )
        # Forward ONLY the scanner's REDACTED label lines (never the content).
        for line in out.splitlines():
            if "FAIL pattern" in line:
                sys.stderr.write(f"  {line.strip()}\n")
        sys.stderr.write(
            "  Move the secret to a gitignored local .env (rules/secrets-management.md).\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
