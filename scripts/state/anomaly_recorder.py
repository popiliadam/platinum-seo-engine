#!/usr/bin/env python3
"""
anomaly_recorder.py — durable sidecar for emit-failure reconciliation (D-B).

When a state write SUCCEEDS but its follow-on audit/event emit into events.jsonl
FAILS, operator decision D-B rules: keep the state write, do NOT hard-block, and
record a DURABLE ANOMALY into a SEPARATE sidecar so the missing audit event is
later reconcilable. This module is that sidecar.

Why a separate file (NOT events.jsonl): the emit that just failed targets
events.jsonl through events_writer's jsonschema validator + flock; if THAT path
is the failure mode (schema-load error, lock, ENOSPC mid-events, a redaction
regex blowing up), re-using the same path/validator for the fallback could fail
identically. anomalies.jsonl is a dedicated, schema-free, fsync-durable append
living next to events.jsonl:

    {workspace_root}/projects/{slug}/_state/anomalies.jsonl

It deliberately carries NO jsonschema dependency (a validator could be the very
thing that failed) and NO secret redaction (the two call sites — transaction.py
and workflow_runner.py — author tightly-scoped, non-secret detail: sheet name,
row count, run_id, workflow_action, the stringified exception). This mirrors the
schema-free ledger precedent of consent.jsonl / cost_ledger.jsonl.

Discipline (mirrors events_writer._atomic_append_line): O_APPEND open +
fcntl.flock(LOCK_EX) + single os.write + os.fsync. Append-only — never amends,
rotates, or truncates.

Reconciliation (drift-check surfacing these records so an operator can replay or
acknowledge them) is a FOLLOW-UP — this module guarantees only the durable write.

Leaf module: NEVER imports events_writer / transaction / workflow_runner (those
import this one, in their emit-failure handlers). No circular deps.

Refs: spec §8.4 (append-only state); rules/append-only-state, time-discipline;
ADR-021 (_state/ path). Operator decision D-B (durable anomaly + reconcile, no
hard-block, no roll-back).
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANOMALIES_FILENAME = "anomalies.jsonl"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AnomalyRecordError(Exception):
    """The durable anomaly write itself could not be completed.

    Callers live in an emit-failure path that must stay non-blocking (D-B), so
    they wrap record_anomaly() in their own try/except and downgrade this to a
    WARNING — a fallback failure must never re-brick an already-committed write.
    Raised (not swallowed here) so the recorder stays unit-testable both ways.
    """


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnomalyResult:
    path: Path
    bytes_written: int


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Stderr logger — stdout is reserved for data output."""
    print(msg, file=sys.stderr)


def _utc_iso_z() -> str:
    """UTC ISO 8601 with 'Z' suffix — preserves microseconds (time-discipline)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _atomic_append_line(path: Path, payload: bytes) -> int:
    """Append one line to `path` atomically; return bytes written.

    O_APPEND (kernel append-seek) + fcntl.flock (cross-process serialization) +
    single os.write + os.fsync (durability). Identical envelope to
    events_writer._atomic_append_line; any failure raises AnomalyRecordError.
    """
    fd = -1
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    except OSError as exc:
        raise AnomalyRecordError(f"cannot open {path}: {exc}") from exc
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError as exc:
            raise AnomalyRecordError(f"flock failed on {path}: {exc}") from exc
        try:
            written = os.write(fd, payload)
            if written != len(payload):
                raise AnomalyRecordError(
                    f"short write on {path}: wrote {written} of {len(payload)} bytes"
                )
            os.fsync(fd)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:  # pragma: no cover (fd about to close)
                pass
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:  # pragma: no cover
                pass
    return len(payload)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_anomaly(
    state_dir: Path | str,
    *,
    kind: str,
    detail: dict | None = None,
    error: str | None = None,
) -> AnomalyResult:
    """Append one durable anomaly record to {state_dir}/anomalies.jsonl.

    Args:
        state_dir: the project's `_state` directory. Passed EXPLICITLY (rather
            than re-resolved from project_id + workspace_root) so the fallback is
            decoupled from whatever path/root resolution may have caused the emit
            failure — the caller already holds a known-good `_state` dir.
        kind: short machine tag classifying the failure, e.g.
            'provenance_emit_failed' / 'workflow_event_emit_failed'.
        detail: structured, non-secret context (sheet, rows_written, run_id,
            workflow_action, step_index, ...). Defaults to {}.
        error: stringified original exception (omitted from the record if None).

    Returns:
        AnomalyResult(path, bytes_written) on success.

    Raises:
        AnomalyRecordError if `kind` is empty/non-string, or the durable write
        cannot be completed (the emit-failure call sites wrap this so a fallback
        failure still never hard-blocks the already-committed state write).
    """
    if not isinstance(kind, str) or not kind:
        raise AnomalyRecordError(f"kind must be a non-empty string, got {kind!r}")

    sd = Path(state_dir)
    try:
        sd.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AnomalyRecordError(f"cannot create state dir {sd}: {exc}") from exc

    path = sd / ANOMALIES_FILENAME
    record: dict[str, Any] = {
        "timestamp": _utc_iso_z(),
        "kind": kind,
        "detail": detail or {},
    }
    if error is not None:
        record["error"] = error

    text = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    payload = text.encode("utf-8") + b"\n"
    nbytes = _atomic_append_line(path, payload)
    return AnomalyResult(path=path, bytes_written=nbytes)


# ---------------------------------------------------------------------------
# Module export list
# ---------------------------------------------------------------------------

__all__: Iterable[str] = (
    "AnomalyResult",
    "AnomalyRecordError",
    "ANOMALIES_FILENAME",
    "record_anomaly",
)
