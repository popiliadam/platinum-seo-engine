#!/usr/bin/env python3
"""scripts/hooks/denetci.py — AMO L3 Stop-hook denetçi (auditor).

AMO's engagement guarantee (spec §3 L3 / G1-G2): when an operator states a KNOWN
intent ("alpha'da aylık bakım yap"), the declared workflow is GUARANTEED to run
and be verified — or the turn does NOT silently end. The L1 router (batch 1c)
writes the intent marker; the orchestrator (batch 1a/1b) writes the per-run
coverage record. THIS is the L3 half: a Stop hook that, at turn end, audits "did
the workflow this turn OWED actually run and pass?" and:

  * never ran      → BLOCK the turn end with a Turkish one-line fix command;
  * ran but failed/incomplete → BLOCK with the remediation fix command;
  * PAUSED on an external dependency (GSC/DFS outage) → ALLOW the turn to end but
    flag it RED (an outage is not the operator's fault; ``--resume`` retries);
  * passed, or no intent declared this turn → allow the turn to end silently.

Contracts honoured (NOT re-derived — confirmed against the code 2026-06-06):
  * Stop-hook block contract — block by writing {"decision":"block","reason":…}
    to STDOUT and exiting 0; empty stdout + exit 0 ALLOWS the turn to end. When
    the payload's ``stop_hook_active`` is true the model is ALREADY continuing
    from a PRIOR block, so the denetçi MUST NOT re-block (that would loop).
  * Wired into hooks/stop.json as the 2nd Stop command — stop_validation.py STAYS
    FIRST; env_probe.py (batch 0a) stays alongside. Classified RUNTIME in
    tests/hooks/test_hook_scripts_runtime_vs_ci.py + scripts/hooks/README.md §1.

This module is READ-ONLY on existing state: it READS the intent marker (1c,
intent_router.intent_marker_path) + the freshest coverage record (1a,
coverage.coverage_path) and REUSES the remediation surface (1d,
remediation.remediation / render) — it writes neither and adds no schema/command.
Freshness is a FILE-mtime gate, not an id correlation: the marker is rewritten at
turn start, so a coverage record produced THIS turn has mtime >= the marker's
mtime; a stale prior-run record (mtime <) is ignored — a week-old pass can never
satisfy a fresh intent. NON-BLOCKING-ON-ERROR: any internal failure → allow the
turn to end (return 0); it must NEVER wedge the session.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make ``scripts.*`` importable when run as a bare hook subprocess
# (mirrors scripts/hooks/intent_router.py — do NOT rely on cwd).
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from scripts.hooks.intent_router import intent_marker_path  # noqa: E402
from scripts.orchestration.coverage import coverage_path  # noqa: E402
from scripts.orchestration.remediation import remediation, render  # noqa: E402
from scripts.state.session_binding import (  # noqa: E402
    current_session_id,
    resolve_workspace_root,
)

_DEFAULT_WORKFLOW = "monthly"


# ---------------------------------------------------------------------------
# Readers (the only IO; never raise)
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict | None:
    """Parse a JSON object at ``path``; None on missing/invalid (never raises)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_intent_marker(workspace_root: Path, session_id: str) -> dict | None:
    """The current-turn intent marker for ``session_id`` (None if absent/invalid)."""
    return _read_json(intent_marker_path(workspace_root, session_id))


def coverage_dir(workspace_root: Path, slug: str) -> Path:
    """``{ws}/projects/{slug}/_state/coverage/`` — parent of any coverage record."""
    return coverage_path(workspace_root, slug, "x").parent


def freshest_fresh_coverage(
    workspace_root: Path, slug: str, since_mtime: float
) -> dict | None:
    """JSON of the newest coverage record written THIS turn, else None.

    THE freshness gate: the intent marker is (re)written at turn start, so a
    coverage record produced THIS turn has file mtime >= the marker's mtime; a
    stale prior-run record has mtime < it and is correctly ignored. Among fresh
    records the one with the GREATEST mtime wins (name breaks an exact tie for
    determinism). Compares FILE mtimes only — never parses ``declared_at``.
    """
    directory = coverage_dir(workspace_root, slug)
    if not directory.is_dir():
        return None
    fresh: list[tuple[float, Path]] = []
    for path in directory.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
        except OSError:  # pragma: no cover - racing unlink
            continue
        if mtime >= since_mtime:
            fresh.append((mtime, path))
    if not fresh:
        return None
    fresh.sort(key=lambda item: (item[0], item[1].name))
    return _read_json(fresh[-1][1])


# ---------------------------------------------------------------------------
# Pure decision (no IO; builds new objects)
# ---------------------------------------------------------------------------

def _nonstart_reason(marker: dict) -> str:
    """Turkish 2-line block for an owed workflow that never ran this turn.

    ``marker['command']`` already encodes the exact ``/pseo-run`` line (incl.
    ``<slug>`` when the session is unbound), so the operator gets one copy-paste
    action.
    """
    command = marker.get("command") or "/pseo-run <workflow> <slug>"
    return (
        f"⚠️  Niyet algılandı ({marker.get('workflow')}) ama bu turda workflow çalışmadı.\n"
        f"Tamamlamak için çalıştır:\n{command}"
    )


def decide(
    marker: dict | None, coverage_record: dict | None
) -> tuple[str, str | None]:
    """Map (marker, coverage_record) → (action, reason). PURE; no IO.

    action ∈ {"allow", "block", "flag"}; reason is the model/operator text (None
    for allow). Matrix:
      * no marker / not 'declared'  → allow            (nothing owed)
      * coverage_record None        → block            (non-start gate)
      * verdict 'pass'              → allow
      * verdict 'paused'            → flag             (external dep: allow + RED)
      * incomplete / failed / other → block            (remediation fix command)
    """
    if marker is None or marker.get("status") != "declared":
        return ("allow", None)  # nothing owed this turn
    if coverage_record is None:
        return ("block", _nonstart_reason(marker))  # owed workflow never ran
    verdict = coverage_record.get("verdict")
    if verdict == "pass":
        return ("allow", None)
    slug = marker.get("slug")
    workflow = marker.get("workflow") or _DEFAULT_WORKFLOW
    # remediation() returns None only for verdict=='pass' (handled above), so
    # render() always receives a dict here.
    reason = render(remediation(coverage_record, slug=slug, workflow=workflow))
    if verdict == "paused":
        return ("flag", reason)  # external dependency — allow turn-end, flag RED
    return ("block", reason)  # incomplete / failed / unknown — force completion


# ---------------------------------------------------------------------------
# Never-crashing main (the only place that reads stdin / emits a decision)
# ---------------------------------------------------------------------------

def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:  # cannot read stdin → allow turn-end
        return ""


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
    """Audit the owed workflow at turn end; block / flag / allow accordingly.

    NEVER wedges the Stop chain: any error → return 0 (allow turn-end). Blocks
    ONLY by writing the {"decision":"block","reason":…} JSON to STDOUT; flags by
    a stderr note (turn still ends); allows silently.
    """
    try:
        payload = _parse_payload(_read_stdin())
        if bool(payload.get("stop_hook_active")):
            return 0  # already continuing from a prior block — never re-block
        session_id = current_session_id(payload)
        workspace_root = resolve_workspace_root()
        if not session_id or workspace_root is None:
            return 0  # cannot resolve context → allow
        marker = load_intent_marker(workspace_root, session_id)
        if not marker or marker.get("status") != "declared":
            return 0  # nothing owed → allow
        slug = marker.get("slug")
        record = None
        if slug:  # unbound intents have no slug → no coverage dir → non-start
            since = intent_marker_path(workspace_root, session_id).stat().st_mtime
            record = freshest_fresh_coverage(workspace_root, slug, since)
        action, reason = decide(marker, record)
        if action == "block":
            print(json.dumps({"decision": "block", "reason": reason}))
        elif action == "flag":
            sys.stderr.write("[denetçi] " + (reason or "") + "\n")
        return 0
    except Exception:  # never wedge the Stop chain
        return 0


if __name__ == "__main__":
    sys.exit(main())
