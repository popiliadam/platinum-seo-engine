#!/usr/bin/env python3
"""scripts/hooks/ai_disclosure_rescan.py — PostToolUse AI-disclosure surface rescan.

Süleyman's hardest constraint (memory feedback_ai_disclosure_ban): the phrase
"written by AI" — and the other AI-disclosure signals — must NEVER appear in the
VISIBLE HTML of a generated blog post. The PreToolUse gate
``validate_content_write.py`` enforces this on the Write/Edit tools, but a model
can BYPASS it by writing the HTML through Bash (a ``cat > … << 'EOF'`` heredoc,
``cp``, ``tee``, a literal path in ``python -c``), which never invokes Write/Edit
— the REAL, USED demo-furniture ``vcc-`` pattern: the engine's R-61 hook blocks ``vcc-``
classes via Write, so the operator writes the body with a Bash heredoc.

THIS module is the POST-write quarantine TWIN of ``validate_content_write``: it
REUSES the same deterministic detector (``content_validator.validate_content``)
and the same scope predicate (``validate_content_write.is_content_html_path``) —
NO duplicated disclosure detection. A PostToolUse hook fires AFTER the write, so
it cannot PREVENT — it must DETECT + REVERT (spec §3 L4 / §7 2b). On a RED finding
in a just-written blog HTML file it QUARANTINE-renames the file off the live
surface (``os.replace`` → ``<path>.BLOCKED-ai-disclosure``): the live ``.html``
no longer exists (the disclosure is OFF the visible surface), the content is
PRESERVED for operator review (not destroyed), and the model is told to rewrite.
For the blog-generation case the write is a NEW file, so removing it from its
path IS the revert (block-and-revert without a pre-write snapshot).

Closes the Bash/heredoc bypass best-effort only: a Bash ``.html`` path built from
a shell variable is NOT caught (a documented Path-A limit). The PreToolUse
Write-gate remains the primary guard for Write/Edit.

NON-BLOCKING-ON-ERROR: a buggy rescan must NEVER wedge the tool chain — any error
returns 0 (mirrors ``validate_content_write``'s fail-open-on-error). Wired as the
3rd command in ``hooks/post-tool-use.json`` (matcher ``Edit|Write|Bash``; the
audit + env_probe commands are untouched); classified RUNTIME in
``tests/hooks/test_hook_scripts_runtime_vs_ci.py`` + ``scripts/hooks/README.md``
§1. Adds no schema / command / new-hook-FILE → no D10 count-guard.

Audit ref: docs/audits/2026-06-04_deep_quality_security_audit.md (Gap 1).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# Make ``scripts.*`` importable when run as a bare hook subprocess
# (mirrors scripts/hooks/audit_post_tool_use.py — do NOT rely on cwd).
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from scripts.validation.content_validator import (  # noqa: E402
    Finding,
    validate_content,
)
from scripts.hooks.validate_content_write import (  # noqa: E402
    _resolve_profile,
    is_content_html_path,
)

_QUARANTINE_SUFFIX = ".BLOCKED-ai-disclosure"
_RECENCY_WINDOW = 60.0  # seconds: only a file written JUST NOW is a candidate

# Maximal non-shell-special run ending in ``.html`` — extracts a path token from a
# Bash command (`cat > x.html`, `>x.html`, `tee x.html`, `open('x.html'`) without
# tokenising the whole line (shlex.split can RAISE on unbalanced heredoc quotes).
_HTML_TOKEN_RE = re.compile(r"[^\s'\"<>|;&]+\.html")


# ---------------------------------------------------------------------------
# Candidate selection — PURE except the explicit mtime/exists reads
# ---------------------------------------------------------------------------

def _raw_paths(payload: dict) -> list[str]:
    """Path strings this tool plausibly WROTE — Write/Edit ``file_path`` or Bash
    ``.html`` tokens — filtered to the blog-HTML scope. No disk access yet."""
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    if tool in ("Write", "Edit"):
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        if isinstance(file_path, str) and is_content_html_path(file_path):
            return [file_path]
        return []
    if tool == "Bash":
        command = tool_input.get("command") or ""
        if not isinstance(command, str):
            return []
        return [tok for tok in _HTML_TOKEN_RE.findall(command) if is_content_html_path(tok)]
    return []


def candidate_paths(payload: dict, *, now: float, window: float = _RECENCY_WINDOW) -> list[Path]:
    """Blog-HTML paths this tool plausibly WROTE that EXIST and were modified JUST
    NOW (``now - mtime < window``); de-duplicated, order-preserving.

    The recency guard is what keeps a READ (``cat old.html``) from being
    quarantined: a read leaves mtime old, so ``now - mtime >= window`` and the
    path is dropped. ``now`` is passed in (the only clock read lives in main) so
    the decision logic is testable without the wall clock. Returns [] for any
    non-Write/Edit/Bash tool or any out-of-scope / missing / stale path.
    """
    result: list[Path] = []
    seen: set[str] = set()
    for raw in _raw_paths(payload):
        path = Path(raw)
        key = str(path)
        if key in seen:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:  # missing / unstattable → not a just-written file
            continue
        if now - mtime < window:
            seen.add(key)
            result.append(path)
    return result


def scan_red(path: Path, *, profile: str | None) -> list[Finding]:
    """RED findings from re-validating ``path``'s file content; [] if unreadable.

    REUSES ``content_validator.validate_content`` — the SAME detector the
    PreToolUse gate runs — so there is no duplicated disclosure logic. The
    AI-disclosure rule runs on visible (script/style-stripped) text.
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    report = validate_content(text, profile=profile)
    return [f for f in report.findings if f.severity == "RED"]


def quarantine(path: Path) -> Path:
    """Rename ``path`` off the live surface → ``<path>.BLOCKED-ai-disclosure``.

    ``os.replace`` removes the live ``.html`` (the disclosure leaves the visible
    surface) while PRESERVING the content for operator review, and overwrites any
    prior quarantine of the same file. This is the "revert": for a freshly-written
    blog file, removing it from its path IS the revert (block-and-revert).
    """
    path = Path(path)
    qpath = Path(str(path) + _QUARANTINE_SUFFIX)
    os.replace(str(path), str(qpath))
    return qpath


def block_reason(blocked: list[tuple[Path, list[Finding], Path]]) -> str:
    """Turkish, model+operator-visible block message: each quarantined file, its
    RED rule(s), the quarantine path, and the fix (rewrite without the phrase)."""
    lines: list[str] = []
    for path, reds, qpath in blocked:
        rules = ", ".join(sorted({f.rule for f in reds}))
        lines.append(
            f"🔴 BLOKLANDI: {path} görünür HTML'de AI-disclosure sinyali taşıyor "
            f"(kural: {rules}). "
            f"Dosya canlı yüzeyden kaldırıldı (karantina: {qpath}). "
            f"Açıklamayı kaldırıp yeniden yaz — görünür 'AI tarafından yazıldı' "
            f"ifadesi YASAK (R-28/R-45/R-89/R-105/R-119 'self-evident' sinyalleri "
            f"yeterli)."
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Never-crashing main — the only stdin read / clock read / decision emit
# ---------------------------------------------------------------------------

def _parse_payload(raw: str) -> dict:
    """Parse hook stdin → dict; empty / malformed / non-object → {} (never raises)."""
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def main() -> int:
    """Re-scan just-written blog HTML; quarantine + block on a RED finding.

    NON-BLOCKING: any error → return 0 (never wedge the tool chain). Signals the
    model ONLY by writing ``{"decision":"block","reason":…}`` to STDOUT (the tool
    already ran); also echoes the reason to stderr so the operator sees it.
    """
    try:
        payload = _parse_payload(sys.stdin.read())
        if not payload.get("tool_name"):
            return 0  # empty / garbage / non-tool payload — clean no-op
        profile = _resolve_profile(payload)  # best-effort; never raises
        now = time.time()
        blocked: list[tuple[Path, list[Finding], Path]] = []
        for path in candidate_paths(payload, now=now):
            reds = scan_red(path, profile=profile)
            if reds:
                blocked.append((path, reds, quarantine(path)))
        if blocked:
            reason = block_reason(blocked)
            print(json.dumps({"decision": "block", "reason": reason}))  # → model
            sys.stderr.write(f"[ai-disclosure-rescan] {reason}\n")  # → operator
        return 0
    except Exception:  # a buggy rescan must not brick the tool chain (fail-open)
        return 0


if __name__ == "__main__":
    sys.exit(main())
