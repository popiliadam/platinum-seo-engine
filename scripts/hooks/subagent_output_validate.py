#!/usr/bin/env python3
"""SubagentStop hook validation — runs at end of each subagent task.

Performance budget: <1s.

Checks (lightweight schema sniff, NOT full jsonschema validation):
  1. Last 5 entries of workspace events.jsonl parse as valid JSON
  2. Each entry carries `event_kind` and `schema_version` fields (envelope shape)

Failure mode: non-blocking (always exits 0). Mismatch warned to stderr.
This hook does NOT block subagent dispatch on validation failure — it surfaces
hints so the schema-first override pattern (ADR-031, Phase 9+) stays observable.

Plugin agnostik: resolves workspace via $PSEO_WORKSPACE_ROOT; events.jsonl path
follows ADR-021 canonical (projects/<slug>/_state/events.jsonl).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _workspace_root() -> Path | None:
    ws = os.environ.get("PSEO_WORKSPACE_ROOT")
    return Path(ws) if ws else None


def _candidate_events_files(ws: Path) -> list[Path]:
    """Return events.jsonl files under any active project (ADR-021 canonical)."""
    return sorted(ws.glob("projects/*/_state/events.jsonl"))


def last_events_schema_sniff(events_path: Path, limit: int = 5) -> tuple[int, int]:
    """Return (parsed_ok, total_inspected) for the last `limit` lines.

    Schema sniff = JSON parse OK AND envelope fields present (event_kind + schema_version).
    Full schema validation deferred to drift-check / CI.
    """
    try:
        with events_path.open("r", encoding="utf-8") as fh:
            tail = [line for line in fh.readlines()[-limit:] if line.strip()]
    except OSError:
        return (0, 0)
    ok = 0
    for line in tail:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "event_kind" in obj and "schema_version" in obj:
            ok += 1
    return (ok, len(tail))


def main() -> int:
    ws = _workspace_root()
    if ws is None:
        # No workspace bound — silently no-op (mirrors PostToolUse pattern)
        return 0
    candidates = _candidate_events_files(ws)
    if not candidates:
        return 0
    # Iterate every project's events.jsonl tail; report any mismatch
    warnings: list[str] = []
    for events_path in candidates:
        ok, total = last_events_schema_sniff(events_path)
        if total > 0 and ok < total:
            try:
                rel = events_path.relative_to(ws)
            except ValueError:
                rel = events_path
            warnings.append(f"{rel}: {total - ok}/{total} entries failed schema sniff")
    if warnings:
        sys.stderr.write(
            "[SubagentStop validation] WARN: schema-first envelope mismatch — "
            + "; ".join(warnings)
            + "\n"
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover — last-resort failsafe
        sys.stderr.write(f"[SubagentStop validation] internal error: {exc!r}\n")
        sys.exit(0)
