#!/usr/bin/env python3
"""env_probe_report.py — summarise the batch-0a hook probe log.

Reads the JSONL written by ``env_probe.py`` and prints a per-session summary
answering the AMO binding question: does a stable, non-null ``session_id`` reach
hooks across the five lifecycle events? It reports only what the log contains —
it draws no cross-environment conclusions (the manager does that).

Usage:
    python3 scripts/hooks/env_probe_report.py [LOG_PATH]
    LOG_PATH default: ~/.config/pseo/hook-probe.jsonl

stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

_DEFAULT_LOG = "~/.config/pseo/hook-probe.jsonl"

# The five lifecycle events the probe is wired into.
CANONICAL_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
)


def load_records(path: str) -> tuple[list, int]:
    """Return ``(records, skipped)``. Missing/unreadable file -> ([], 0).

    Unparseable or non-dict lines are skipped and counted; never raises.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return ([], 0)
    records: list = []
    skipped = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            skipped += 1
            continue
        if isinstance(obj, dict):
            records.append(obj)
        else:
            skipped += 1
    return (records, skipped)


def _distinct(recs: list, field: str) -> list:
    return sorted({r.get(field) for r in recs if r.get(field)})


def _merge_env_present(recs: list) -> dict:
    names = sorted({n for r in recs for n in (r.get("env_present") or {})})
    return {n: any((r.get("env_present") or {}).get(n) for r in recs) for n in names}


def _merge_env_values(recs: list) -> dict:
    out: dict = defaultdict(set)
    for rec in recs:
        for name, value in (rec.get("env_values") or {}).items():
            if value is not None:
                out[name].add(value)
    return {name: sorted(values) for name, values in sorted(out.items())}


def _summarize_bucket(session_id, recs: list) -> dict:
    events_seen = _distinct(recs, "hook_event_name")
    canonical_present = [e for e in CANONICAL_EVENTS if e in events_seen]
    present = session_id is not None
    identical = len({r.get("session_id") for r in recs}) == 1
    return {
        "session_id": session_id,
        "event_count": len(recs),
        "events_seen": events_seen,
        "canonical_present": canonical_present,
        "n_of_5": len(canonical_present),
        "stable": present and identical,
        "transcript_paths": _distinct(recs, "transcript_path"),
        "cwd_payloads": _distinct(recs, "cwd_payload"),
        "cwd_os": _distinct(recs, "cwd_os"),
        "env_present": _merge_env_present(recs),
        "env_values": _merge_env_values(recs),
    }


def summarize(records: list) -> list:
    """Group records by ``session_id`` (None is its own bucket) and summarise
    each. Pure — order follows first appearance of each session_id."""
    buckets: dict = defaultdict(list)
    for rec in records:
        buckets[rec.get("session_id")].append(rec)
    return [_summarize_bucket(sid, recs) for sid, recs in buckets.items()]


def render(summaries: list, skipped: int) -> str:
    lines = [
        "=== PSEO hook-probe report ===",
        f"sessions: {len(summaries)} | unparseable lines skipped: {skipped}",
        "",
    ]
    for summary in summaries:
        sid = summary["session_id"]
        label = sid if sid is not None else "<none>"
        seen = ", ".join(summary["canonical_present"]) or "(none)"
        other = [e for e in summary["events_seen"] if e not in CANONICAL_EVENTS]
        verdict = "YES" if summary["stable"] else "NO"
        lines.append(f"--- session_id: {label} ---")
        lines.append(f"  events recorded: {summary['event_count']}")
        lines.append(f"  lifecycle events seen ({summary['n_of_5']}/5): {seen}")
        if other:
            lines.append(f"  other events seen: {', '.join(other)}")
        lines.append(
            f"  transcript_path(s): {', '.join(summary['transcript_paths']) or '(none)'}"
        )
        lines.append(
            f"  cwd (payload): {', '.join(summary['cwd_payloads']) or '(none)'}"
        )
        lines.append(f"  cwd (os.getcwd): {', '.join(summary['cwd_os']) or '(none)'}")
        lines.append(f"  env_present: {summary['env_present']}")
        lines.append(f"  env_values: {summary['env_values']}")
        lines.append(
            f"  VERDICT: session_id stable & present across "
            f"{summary['n_of_5']}/5 events: {verdict}"
        )
        lines.append("")
    return "\n".join(lines)


def main(argv: list) -> int:
    path = argv[1] if len(argv) > 1 else os.path.expanduser(_DEFAULT_LOG)
    records, skipped = load_records(path)
    sys.stdout.write(render(summarize(records), skipped) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # report tool must not traceback on bad input
        sys.stderr.write(f"[env_probe_report] error: {exc!r}\n")
        sys.exit(0)
