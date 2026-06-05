#!/usr/bin/env python3
"""validate_content_write.py — PreToolUse content gate (runtime hook).

Wired into ``hooks/pre-tool-use.json`` (matcher ``Edit|Write|Bash``). On a Write
or Edit of a generated blog HTML file it runs the deterministic
``content_validator`` and, on a RED verdict, ``sys.exit(2)`` so Claude Code
blocks the write — enforcing the AI-disclosure ban + R-22/R-43/R-77/R-61 at the
one boundary that is live today (the Write tool), independent of whether the
production skills have Python runtime yet.

Audit ref: docs/audits/2026-06-04_deep_quality_security_audit.md (Gap 1).
Design:    docs/superpowers/specs/2026-06-04-content-validator-design.md §7.

Contract:
    * Scope — only ``…/outputs/{blog,content}/…/*.html`` (the published surface);
      everything else (Bash, scripts, templates, internal .md) is skipped.
    * Write — full validation of ``tool_input.content``.
    * Edit  — validation of ``tool_input.new_string`` (RED rules are presence
      checks, correct on a fragment; AMBER advisories are suppressed on edits).
    * Verdict — RED → exit 2 (block); AMBER/GREEN → exit 0 (AMBER warns on Write).
    * Failure — conservative about blocking, loud about failure: any unexpected
      error is caught and the write is ALLOWED (fail-open), because a buggy gate
      must not brick content production. A true RED finding is fail-closed.

Plugin agnostik: resolves the active project's profile via
``$PSEO_WORKSPACE_ROOT/shared/active.json`` (best-effort; never raises).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Make ``scripts.*`` importable when run as a subprocess by the hook runner.
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from scripts.validation.content_validator import validate_content  # noqa: E402
from scripts.state.session_binding import (  # noqa: E402
    current_session_id,
    resolve_session_project,
    resolve_workspace_root,
)

# Live published HTML surface: outputs/blog/ or outputs/content/ (the configured
# blog_dir), but never a *.template.html.
_CONTENT_PATH_RE = re.compile(r"(?:^|/)outputs/(?:blog|content)/")

# RED rules that are correct on an Edit fragment (presence checks). R-61
# (pse- prefix) and the AMBER density rules need the whole document, so they
# only run on a full Write (spec §4 "Fragment-safe?" column).
_FRAGMENT_SAFE_RULES = frozenset({"AI-disclosure", "R-22", "R-43", "R-77"})


def is_content_html_path(path: str) -> bool:
    """True iff ``path`` is a generated blog HTML file (the gate's scope)."""
    norm = path.replace("\\", "/")
    if not norm.endswith(".html") or norm.endswith(".template.html"):
        return False
    return bool(_CONTENT_PATH_RE.search(norm))


def evaluate(payload: dict, *, profile: str | None = None) -> tuple[int, list[str]]:
    """Return ``(exit_code, messages)`` — 2 blocks the write, 0 allows it.

    Pure: no I/O, no env reads — the caller resolves ``profile`` and does stdin.
    """
    if not isinstance(payload, dict):
        return (0, ["non-dict payload — skipping (fail-open)"])
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return (0, ["missing tool_input — skipping (fail-open)"])

    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if tool not in ("Write", "Edit") or not is_content_html_path(file_path):
        return (0, [])

    if tool == "Write":
        content = tool_input.get("content") or ""
    else:  # Edit — validate the incoming fragment
        content = tool_input.get("new_string") or ""

    report = validate_content(content, profile=profile)
    reds = [f for f in report.findings if f.severity == "RED"]
    if tool == "Edit":
        reds = [f for f in reds if f.rule in _FRAGMENT_SAFE_RULES]
    if reds:
        return (2, [f"BLOCKED {f.rule}: {f.message}" for f in reds])

    # Surface AMBER advisories on full Write only; stay quiet on Edit fragments.
    if tool == "Write":
        ambers = [f for f in report.findings if f.severity == "AMBER"]
        return (0, [f"WARN {f.rule}: {f.message}" for f in ambers])
    return (0, [])


def _resolve_profile(payload: dict | None = None) -> str | None:
    """Best-effort active-project profile for the R-104 advisory band.

    Resolves the workspace via ``resolve_workspace_root()`` (config → env; AMO
    batch 0a proved the env var alone is unreliable) and the project via the
    session marker (THIS session, keyed by the hook ``payload`` session_id) with
    a ``shared/active.json`` fallback. Never raises; returns ``None`` when no
    workspace/project/profile is bound (strict=False + the outer try/except).
    """
    workspace = resolve_workspace_root()
    if workspace is None:
        return None
    try:
        project_id = resolve_session_project(
            workspace,
            session_id=current_session_id(payload),
            strict=False,
        )
        if not project_id:
            return None
        config_path = (
            Path(workspace) / "projects" / project_id / "project.config.json"
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        profile = config.get("profile")
        if profile:
            return profile
        profiles = config.get("profiles") or []
        return profiles[0] if profiles else None
    except Exception:
        return None


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        payload = json.loads(raw)
        code, messages = evaluate(payload, profile=_resolve_profile(payload))
        for message in messages:
            sys.stderr.write(f"[content-validator] {message}\n")
        return code
    except Exception as exc:  # fail-open — never brick content production
        sys.stderr.write(
            "[content-validator] WARNING internal error, allowing write "
            f"(fail-open): {exc!r}\n"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
