#!/usr/bin/env python3
"""
events_writer.py — Atomic, schema-validated, per-project events.jsonl appender.

Foundation module for Platinum SEO Engine state layer (spec §8.4 append-only,
§3 scripts tree). Writes JSONL events to:

    {workspace_root}/projects/{project_id}/_state/events.jsonl   (ADR-021)

Discipline:
  - Atomic append: O_APPEND open + fcntl.flock(LOCK_EX) + os.write +
    os.fsync. Single write() syscall per event guarantees POSIX atomicity
    on appends ≤ PIPE_BUF; fcntl serializes higher-level concurrency.
  - Validation BEFORE append: jsonschema Draft7Validator (cached via
    functools.lru_cache) against schemas/events.schema.json. Failures
    raise EventValidationError and DO NOT touch the file.
  - Auto-populate (caller may omit): event_id (uuid4 hex),
    timestamp (UTC ISO 8601 with 'Z' suffix), schema_version ("1.0").
  - Redaction: regex value patterns (sk-, ghp_, AKIA, ...) + field-name
    patterns (*_token / *_secret / *_key / *_password) replaced with
    "***REDACTED***". Default ON. Recursive into nested dicts/lists.
    Opt-out via redact=False. Field-name match uses suffix logic that
    excludes innocuous overlaps like "cost_per_1k_tokens".
  - 64KB cap per event (json.dumps len > 65536 → EventPayloadTooLarge).
  - UTF-8: ensure_ascii=False, separators=(',',':') for compactness.
  - Plugin-agnostik: project_id parameter; no slug literals.
  - Append-only: never amends, rotates, truncates. Rotation is Phase 12+.

Public API:
    append_event(event, project_id, workspace_root=None) -> EventResult
    append_provenance(*, project_id, run_id, source, operation, **kwargs) -> EventResult
    append_work(*, project_id, event_type, task_id, **kwargs) -> EventResult
    append_audit(*, project_id, audit_action, audit_target, actor, **kwargs) -> EventResult
    append_workflow(*, project_id, workflow_action, workflow_run_id,
                    step_index=None, **kwargs) -> EventResult        (ADR-020)
    next_run_id(project_id, workspace_root=None) -> int

Spec/ADR references:
  - spec §3 (scripts/state/), §8.4 (append-only state), §16.5 (MCP),
    §16.8 (budget — events.jsonl SSoT)
  - schemas/events.schema.json (definitions, allOf conditional requireds)
  - rules/append-only-state.md, rules/schema-first.md,
    rules/single-source-of-truth.md, rules/secrets-management.md,
    rules/time-discipline.md
  - ADR-008 (plugin agnostik), ADR-012 (HTTP $schema URI),
    ADR-016 (events.jsonl SSoT), ADR-017 (schema-correct field names),
    ADR-020 (event_kind="workflow"), ADR-021 (_state/ path)

NEVER imports transaction.py or workflow_runner.py — those modules import
this one. Foundation, no circular deps.
"""

from __future__ import annotations

import fcntl
import functools
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = "1.0"
_MAX_EVENT_BYTES = 64 * 1024  # 65536, hard cap per event after JSON encode
_REDACTED = "***REDACTED***"

# Module dir: <repo>/scripts/state/events_writer.py → repo = parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SCHEMA_PATH = _REPO_ROOT / "schemas" / "events.schema.json"

# Secret VALUE patterns — match common token formats outright.
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),       # openai
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),             # anthropic
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                    # github classic PAT
    re.compile(r"github_pat_[A-Za-z0-9_]{82}"),            # github fine-grained
    re.compile(r"AKIA[0-9A-Z]{16}"),                       # aws access key id
)

# Secret FIELD-NAME suffixes — case-insensitive endswith match.
# Innocuous fields that happen to contain "token" (e.g. "cost_per_1k_tokens")
# do NOT match because they don't end with the exact suffix sentinel.
_SECRET_KEY_SUFFIXES: tuple[str, ...] = (
    "_token",
    "_secret",
    "_key",
    "_password",
    "token",      # bare "token"
    "secret",
    "apikey",
    "password",
)

# Innocuous field whitelist — even if the suffix matches, do not redact these.
_SECRET_KEY_WHITELIST: frozenset[str] = frozenset({
    "cost_per_1k_tokens",
    "params_hash",
    "file_hash",
    "intake_hash",
    "staging_hash",
    "post_hash",
    "pre_hash",
    "primary_key",   # common DB term, not a secret
    "foreign_key",
    "schema_key",    # internal addressing
    "budget_key",
    "rows_written",
    "cells_written",
})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EventWriterError(Exception):
    """Base class for all events_writer errors."""


class EventValidationError(EventWriterError):
    """Raised when an event fails events.schema.json validation."""


class EventPathError(EventWriterError):
    """Workspace root or project _state directory missing / unwritable."""


class EventPayloadTooLarge(EventWriterError):
    """Single serialized event exceeds 64 KiB cap."""


class EventLockError(EventWriterError):
    """fcntl.flock acquisition failed (rare; e.g. EBADF, ENOLCK)."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EventResult:
    """Outcome of a successful append. Returned by all append_*() entry points."""

    event_id: str
    path: Path
    bytes_written: int


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Stderr logger — stdout is reserved for data output."""
    print(msg, file=sys.stderr)


@functools.lru_cache(maxsize=4)
def _get_validator(schema_path: str) -> Draft7Validator:
    """Cache one Draft7Validator per schema path (lru_cache hashes the str key)."""
    p = Path(schema_path)
    with p.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    return Draft7Validator(schema)


def _resolve_workspace_root(workspace_root: Path | None) -> Path:
    """Resolve workspace_root from arg → env PSEO_WORKSPACE_ROOT → fail."""
    if workspace_root is not None:
        return Path(workspace_root)
    env = os.getenv("PSEO_WORKSPACE_ROOT")
    if env:
        return Path(env)
    raise EventPathError(
        "workspace_root not provided and PSEO_WORKSPACE_ROOT not set"
    )


def _events_path(project_id: str, workspace_root: Path | None) -> Path:
    """Build the events.jsonl path: {ws}/projects/{project_id}/_state/events.jsonl."""
    if not isinstance(project_id, str) or not project_id:
        raise EventPathError(f"project_id must be a non-empty string, got {project_id!r}")
    ws = _resolve_workspace_root(workspace_root)
    state_dir = ws / "projects" / project_id / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "events.jsonl"


def _utc_iso_z() -> str:
    """UTC ISO 8601 with 'Z' suffix — preserves microseconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _is_redacting_key(key: str) -> bool:
    """Return True if a field name suggests sensitive data."""
    if not isinstance(key, str):
        return False
    lk = key.lower()
    if lk in _SECRET_KEY_WHITELIST:
        return False
    return any(lk.endswith(suf) for suf in _SECRET_KEY_SUFFIXES)


def _redact_value(value: Any) -> Any:
    """Redact secret-like substrings inside a string value (regex patterns)."""
    if not isinstance(value, str):
        return value
    out = value
    for pat in _SECRET_VALUE_PATTERNS:
        out = pat.sub(_REDACTED, out)
    return out


def _redact_recursive(obj: Any) -> Any:
    """Recursively redact dicts/lists. Returns a new structure (no mutation)."""
    if isinstance(obj, dict):
        new: dict[str, Any] = {}
        for k, v in obj.items():
            if _is_redacting_key(k) and isinstance(v, str):
                new[k] = _REDACTED
            else:
                new[k] = _redact_recursive(v)
        return new
    if isinstance(obj, list):
        return [_redact_recursive(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_redact_recursive(x) for x in obj)
    return _redact_value(obj)


def _validate_event(event: dict, schema_path: Path) -> None:
    """Draft7 validation. Raises EventValidationError aggregating all errors."""
    try:
        validator = _get_validator(str(schema_path))
    except (OSError, json.JSONDecodeError) as exc:
        raise EventValidationError(f"failed to load schema {schema_path}: {exc}") from exc
    errors: list[_JSValidationError] = sorted(validator.iter_errors(event), key=lambda e: e.path)
    if errors:
        msgs = []
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            msgs.append(f"{loc}: {err.message}")
        raise EventValidationError("; ".join(msgs))


def _atomic_append_line(path: Path, payload: bytes) -> None:
    """
    Append a single JSON line to events.jsonl atomically.

    Uses O_APPEND (kernel-level append seek) + fcntl.flock for cross-process
    serialization + os.write (single syscall) + os.fsync for durability.
    """
    fd = -1
    try:
        # 0o644 — owner rw, others r. Created on first write.
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    except OSError as exc:
        raise EventPathError(f"cannot open {path}: {exc}") from exc

    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError as exc:
            raise EventLockError(f"flock failed on {path}: {exc}") from exc
        try:
            written = os.write(fd, payload)
            if written != len(payload):
                # Extremely unlikely with O_APPEND on regular files; treat as fatal.
                raise EventPathError(
                    f"short write on {path}: wrote {written} of {len(payload)} bytes"
                )
            os.fsync(fd)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                # Unlock failure on close is non-fatal — the fd is about to die.
                pass
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass


def _serialize(event: dict) -> bytes:
    """JSON-encode an event to a UTF-8 bytes buffer with trailing newline."""
    text = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) > _MAX_EVENT_BYTES:
        raise EventPayloadTooLarge(
            f"event size {len(text)} chars exceeds {_MAX_EVENT_BYTES} byte cap"
        )
    return text.encode("utf-8") + b"\n"


def _populate_envelope(event: dict, project_id: str) -> dict:
    """Auto-fill schema_version / event_id / timestamp / project_id."""
    out = dict(event)  # shallow copy; do not mutate caller's dict
    out.setdefault("schema_version", _SCHEMA_VERSION)
    out.setdefault("event_id", uuid.uuid4().hex)
    out.setdefault("timestamp", _utc_iso_z())
    # project_id is REQUIRED by schema; force it in to avoid caller drift.
    if "project_id" in out and out["project_id"] != project_id:
        raise EventValidationError(
            f"project_id mismatch: event has {out['project_id']!r}, "
            f"caller passed {project_id!r}"
        )
    out["project_id"] = project_id
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def append_event(
    event: dict,
    project_id: str,
    workspace_root: Path | None = None,
    *,
    redact: bool = True,
    schema_path: Path | None = None,
) -> EventResult:
    """
    Validate, redact, and atomically append a single event to events.jsonl.

    Caller MUST supply event_kind plus per-kind required fields (provenance
    needs run_id+source+operation; work needs event_type+task_id; audit
    needs audit_action+audit_target+actor; workflow needs workflow_action
    +workflow_run_id). schema_version, event_id, timestamp are auto-filled
    if missing.

    Args:
        event: Raw event dict. Will be deep-copied before mutation.
        project_id: Project slug (matches projects/{slug}/ + project-config).
        workspace_root: Override env PSEO_WORKSPACE_ROOT. None → env or fail.
        redact: If True (default), apply secret redaction recursively.
        schema_path: Override events.schema.json location (test-only).

    Returns:
        EventResult(event_id, path, bytes_written).
    """
    if not isinstance(event, dict):
        raise EventValidationError(f"event must be a dict, got {type(event).__name__}")

    schema_p = schema_path or _DEFAULT_SCHEMA_PATH

    # 1. Envelope auto-populate.
    populated = _populate_envelope(event, project_id)

    # 2. Redaction (before validation so schema sees redacted shape).
    if redact:
        populated = _redact_recursive(populated)

    # 3. Schema validation.
    _validate_event(populated, schema_p)

    # 4. Serialize + size check.
    payload = _serialize(populated)

    # 5. Path + atomic append.
    path = _events_path(project_id, workspace_root)
    _atomic_append_line(path, payload)

    return EventResult(
        event_id=populated["event_id"],
        path=path,
        bytes_written=len(payload),
    )


def append_provenance(
    *,
    project_id: str,
    run_id: int,
    source: dict,
    operation: str,
    workspace_root: Path | None = None,
    redact: bool = True,
    schema_path: Path | None = None,
    **kwargs: Any,
) -> EventResult:
    """Convenience wrapper for event_kind='provenance'. Passes kwargs through."""
    event: dict[str, Any] = {
        "event_kind": "provenance",
        "run_id": run_id,
        "source": source,
        "operation": operation,
    }
    event.update(kwargs)
    return append_event(
        event,
        project_id=project_id,
        workspace_root=workspace_root,
        redact=redact,
        schema_path=schema_path,
    )


def append_work(
    *,
    project_id: str,
    event_type: str,
    task_id: str,
    workspace_root: Path | None = None,
    redact: bool = True,
    schema_path: Path | None = None,
    **kwargs: Any,
) -> EventResult:
    """Convenience wrapper for event_kind='work' (DONE protocol §21.4)."""
    event: dict[str, Any] = {
        "event_kind": "work",
        "event_type": event_type,
        "task_id": task_id,
    }
    event.update(kwargs)
    return append_event(
        event,
        project_id=project_id,
        workspace_root=workspace_root,
        redact=redact,
        schema_path=schema_path,
    )


def append_audit(
    *,
    project_id: str,
    audit_action: str,
    audit_target: str,
    actor: str,
    workspace_root: Path | None = None,
    redact: bool = True,
    schema_path: Path | None = None,
    **kwargs: Any,
) -> EventResult:
    """Convenience wrapper for event_kind='audit' (governance, Phase 14+)."""
    event: dict[str, Any] = {
        "event_kind": "audit",
        "audit_action": audit_action,
        "audit_target": audit_target,
        "actor": actor,
    }
    event.update(kwargs)
    return append_event(
        event,
        project_id=project_id,
        workspace_root=workspace_root,
        redact=redact,
        schema_path=schema_path,
    )


def append_workflow(
    *,
    project_id: str,
    workflow_action: str,
    workflow_run_id: str,
    step_index: int | None = None,
    workspace_root: Path | None = None,
    redact: bool = True,
    schema_path: Path | None = None,
    **kwargs: Any,
) -> EventResult:
    """
    Convenience wrapper for event_kind='workflow' (ADR-020).

    Used by workflow_runner.py to log every state-machine transition. The
    workflow_run_id field is a STRING (matches workflow-run.schema.run_id
    pattern); distinct from the integer run_id used by provenance events.
    """
    event: dict[str, Any] = {
        "event_kind": "workflow",
        "workflow_action": workflow_action,
        "workflow_run_id": workflow_run_id,
    }
    if step_index is not None:
        event["step_index"] = step_index
    event.update(kwargs)
    return append_event(
        event,
        project_id=project_id,
        workspace_root=workspace_root,
        redact=redact,
        schema_path=schema_path,
    )


def next_run_id(
    project_id: str,
    workspace_root: Path | None = None,
) -> int:
    """
    Return the next monotonic provenance run_id for a project.

    Scans events.jsonl, finds max integer run_id (provenance events only),
    and returns max+1. Returns 1 if file is missing or empty.
    """
    path = _events_path(project_id, workspace_root)
    if not path.exists():
        return 1
    max_run = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                rid = obj.get("run_id")
                if isinstance(rid, int) and rid > max_run:
                    max_run = rid
    except OSError as exc:
        raise EventPathError(f"cannot read {path}: {exc}") from exc
    return max_run + 1


# ---------------------------------------------------------------------------
# Module export list (helps grep/imports stay tight)
# ---------------------------------------------------------------------------

__all__: Iterable[str] = (
    "EventResult",
    "EventWriterError",
    "EventValidationError",
    "EventPathError",
    "EventPayloadTooLarge",
    "EventLockError",
    "append_event",
    "append_provenance",
    "append_work",
    "append_audit",
    "append_workflow",
    "next_run_id",
)
