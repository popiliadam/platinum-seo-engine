#!/usr/bin/env python3
"""
workflow_runner.py — Multi-step skill state machine (JSON-only, no FSM lib).

Persists workflow run state to
{workspace_root}/projects/{project_slug}/_state/workflows/{run_id}.json
(ADR-021). Spec §10: "State machine kütüphanesi yok — sadece JSON yazma
disiplini". No `transitions` / `python-statemachine` / `automat` — just a
literal allowed-transition set and JSON I/O. Every write is schema-
validated against schemas/workflow-run.schema.json (allOf conditionals
enforce awaiting_approval→approval_meta, failed→failure_reason,
done|failed→ended_at, paused→paused_at). Atomic write: tempfile +
fsync + os.replace + parent dir fsync. Lock: fcntl.flock(LOCK_EX|LOCK_NB)
on sidecar `{run_id}.json.lock`. retry_count starts 0 (ADR-019),
increments only on failed→running. Append-only: paused_at survives
resume. run_id pattern (workflow-run.schema): {slug}-YYYY-MM-DD-{4 hex};
generated via secrets.token_hex(2), 5 collision retries. Top-level
transitions emit event_kind=workflow events into events.jsonl (ADR-020);
start_step/finish_step are internal-only (no event).

Refs: spec §3 + §10; schemas/workflow-run + events; rules/append-only-
state, schema-first, time-discipline; ADR-019 / ADR-020 / ADR-021.
Imports events_writer + anomaly_recorder one-way; never imported by them. A
failed workflow-event emit keeps the run state and records a durable anomaly to
the _state/anomalies.jsonl sidecar (operator decision D-B: no roll-back, no
hard-block); reconciliation is a follow-up.
"""

from __future__ import annotations

import fcntl
import functools
import json
import os
import re
import secrets
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError

from scripts.state import anomaly_recorder, events_writer
from scripts.validation.validate_schema import build_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SCHEMA_PATH = _REPO_ROOT / "schemas" / "workflow-run.schema.json"

_SCHEMA_VERSION = "1.0"
_RUN_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9-]*-\d{4}-\d{2}-\d{2}-[a-f0-9]{4}$"
)
_LOCK_STALE_SECONDS = 5 * 60
_RUN_ID_COLLISION_TRIES = 5


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WorkflowError(Exception):
    """Base class for workflow_runner errors."""


class IllegalTransitionError(WorkflowError):
    """The requested (from_status → to_status) is not in the dispatch table."""


class ValidationError(WorkflowError):
    """Validation failed (schema, missing arg, run_id pattern, etc.)."""


class ConcurrentMutationError(WorkflowError):
    """Another process holds the run lock."""


class RunIdCollisionError(WorkflowError):
    """5 consecutive token_hex(2) draws collided with existing files."""


class RunNotFoundError(WorkflowError):
    """No {run_id}.json exists under workflows/."""


class CorruptStateError(WorkflowError):
    """workflow run JSON could not be parsed."""


class SchemaVersionMismatchError(WorkflowError):
    """run JSON schema_version is unexpected."""


class StepNameDuplicateError(WorkflowError):
    """Two steps in steps[] share the same name."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunHandle:
    run_id: str
    project_slug: str
    status: str
    path: Path
    data: dict


# ---------------------------------------------------------------------------
# Internals — schema, IO, locking
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


@functools.lru_cache(maxsize=2)
def _validator(schema_path: str) -> Draft7Validator:
    # build_validator (not a raw Draft7Validator) so the many date-time fields in
    # workflow-run.schema.json (started_at/updated_at/created_at/ended_at/…) are
    # ENFORCED with the strict UTC '…Z' checker — a naive/non-UTC stamp is rejected
    # before the run state is persisted (P1-02 / time-discipline §8.10).
    with Path(schema_path).open("r", encoding="utf-8") as fh:
        return build_validator(json.load(fh))


def _utc_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _resolve_workspace_root(workspace_root: Path | None) -> Path:
    if workspace_root is not None:
        return Path(workspace_root)
    env = os.getenv("PSEO_WORKSPACE_ROOT")
    if env:
        return Path(env)
    raise ValidationError(
        "workspace_root not provided and PSEO_WORKSPACE_ROOT not set"
    )


def _workflows_dir(project_slug: str, workspace_root: Path | None) -> Path:
    # Validate at the write boundary: the slug composes the on-disk path, so a
    # traversal / separator / absolute value must not be able to escape projects/
    # (matches the project_id slug contract in project-config.schema.json).
    if not isinstance(project_slug, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", project_slug):
        raise ValidationError(
            f"project_slug must match ^[a-z][a-z0-9-]*$, got {project_slug!r}"
        )
    ws = _resolve_workspace_root(workspace_root)
    d = ws / "projects" / project_slug / "_state" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_path(run_id: str, project_slug: str, workspace_root: Path | None) -> Path:
    if not _RUN_ID_PATTERN.match(run_id):
        raise ValidationError(f"run_id pattern mismatch: {run_id!r}")
    return _workflows_dir(project_slug, workspace_root) / f"{run_id}.json"


def _read_run(path: Path) -> dict:
    if not path.exists():
        raise RunNotFoundError(f"no run state at {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise CorruptStateError(f"cannot parse {path}: {exc}") from exc
    sv = data.get("schema_version")
    if sv is not None and sv != _SCHEMA_VERSION:
        raise SchemaVersionMismatchError(
            f"{path}: schema_version {sv!r} != expected {_SCHEMA_VERSION!r}"
        )
    return data


def _validate(data: dict, schema_path: Path) -> None:
    validator = _validator(str(schema_path))
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = []
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            msgs.append(f"{loc}: {err.message}")
        raise ValidationError("; ".join(msgs))


def _atomic_write_json(data: dict, path: Path) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=".run-", suffix=".json.tmp", dir=str(parent))
    tmp_path = Path(tmp_name)
    try:
        os.close(tmp_fd)
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, separators=(",", ": "))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:  # pragma: no cover
            pass
        raise
    try:
        dir_fd = os.open(str(parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:  # pragma: no cover
        pass


def _is_stale_lock(lock_path: Path) -> bool:
    if not lock_path.exists():
        return False
    try:
        obj = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    pid = obj.get("pid")
    ts = obj.get("ts")
    if not isinstance(pid, int) or not isinstance(ts, str):
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - when).total_seconds() > _LOCK_STALE_SECONDS


def _acquire_run_lock(path: Path) -> int:
    lock_path = path.with_suffix(path.suffix + ".lock")
    if _is_stale_lock(lock_path):
        try:
            lock_path.unlink()
        except FileNotFoundError:  # pragma: no cover
            pass
    fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise ConcurrentMutationError(f"another writer holds {lock_path}") from exc
    except OSError as exc:
        os.close(fd)
        raise ConcurrentMutationError(f"flock failed on {lock_path}: {exc}") from exc

    payload = json.dumps({
        "pid": os.getpid(),
        "ts": _utc_iso_z(),
    }, separators=(",", ":")).encode("utf-8") + b"\n"
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, payload)
        os.fsync(fd)
    except OSError:  # pragma: no cover
        pass
    return fd


def _release_run_lock(fd: int, path: Path) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:  # pragma: no cover
        pass
    try:
        os.close(fd)
    except OSError:  # pragma: no cover
        pass
    lock_path = path.with_suffix(path.suffix + ".lock")
    try:
        lock_path.unlink()
    except FileNotFoundError:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# Internals — run_id generation + step bookkeeping
# ---------------------------------------------------------------------------

def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _generate_run_id(project_slug: str, workspace_root: Path | None) -> str:
    wf_dir = _workflows_dir(project_slug, workspace_root)
    today = _today_utc()
    last_exc: Exception | None = None
    for _ in range(_RUN_ID_COLLISION_TRIES):
        token = secrets.token_hex(2)
        candidate = f"{project_slug}-{today}-{token}"
        if not _RUN_ID_PATTERN.match(candidate):
            # This shouldn't happen unless project_slug is malformed.
            raise ValidationError(
                f"generated run_id {candidate!r} does not match required pattern"
            )
        path = wf_dir / f"{candidate}.json"
        if not path.exists():
            return candidate
        last_exc = FileExistsError(str(path))
    raise RunIdCollisionError(
        f"5 token_hex(2) draws collided in {wf_dir}; last={last_exc}"
    )


def _validate_step_names(steps: list[dict]) -> None:
    seen: set[str] = set()
    for s in steps:
        n = s.get("name")
        if n in seen:
            raise StepNameDuplicateError(f"duplicate step name: {n!r}")
        seen.add(n)


# ---------------------------------------------------------------------------
# Internals — transition table (literal dispatch, no FSM library — spec §10)
# ---------------------------------------------------------------------------
# Each operation below has its own argument signature, so the dispatch is
# expressed as a frozenset of allowed (from_status, to_status) pairs that
# every mutator consults BEFORE writing. Anything not listed is illegal.
_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    # create_run
    ("__init__", "running"),
    ("__init__", "awaiting_approval"),  # rare: runs that start gated
    # request_approval
    ("running", "awaiting_approval"),
    # approve
    ("awaiting_approval", "running"),
    # reject (terminal)
    ("awaiting_approval", "failed"),
    # reject (non-terminal)
    ("awaiting_approval", "paused"),
    # pause
    ("running", "paused"),
    ("awaiting_approval", "paused"),
    # resume
    ("paused", "running"),
    # fail
    ("running", "failed"),
    ("awaiting_approval", "failed"),
    ("paused", "failed"),
    # retry
    ("failed", "running"),
    # complete
    ("running", "done"),
})


def _check_transition(from_status: str, to_status: str) -> None:
    if (from_status, to_status) not in _ALLOWED_TRANSITIONS:
        raise IllegalTransitionError(
            f"illegal transition: {from_status!r} → {to_status!r}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_run(
    skill: str,
    project_slug: str,
    steps: list[dict],
    *,
    initial_status: str = "running",
    approval_meta: dict | None = None,
    total_steps: int | None = None,
    workspace_root: Path | None = None,
    schema_path: Path | None = None,
) -> RunHandle:
    """Persist a new workflow run. steps: list of {"name": str, ...}, names
    unique. initial_status: 'running' (default) or 'awaiting_approval'
    (requires approval_meta)."""
    if not isinstance(skill, str) or not skill:
        raise ValidationError("skill must be a non-empty string")
    if not isinstance(steps, list) or not steps:
        raise ValidationError("steps must be a non-empty list")
    _check_transition("__init__", initial_status)

    schema_p = schema_path or _DEFAULT_SCHEMA_PATH
    run_id = _generate_run_id(project_slug, workspace_root)
    path = _run_path(run_id, project_slug, workspace_root)

    now = _utc_iso_z()

    norm_steps: list[dict] = []
    for s in steps:
        if not isinstance(s, dict) or "name" not in s:
            raise ValidationError(f"step must be dict with 'name': {s!r}")
        new_step = {"name": s["name"], "status": s.get("status", "pending")}
        # Allow approval_prompt or other defined fields to pass through.
        for k in ("approval_prompt", "output_ref", "started_at", "ended_at",
                  "approval_decision", "error"):
            if k in s:
                new_step[k] = s[k]
        norm_steps.append(new_step)
    _validate_step_names(norm_steps)

    data: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "run_id": run_id,
        "skill": skill,
        "project_slug": project_slug,
        "status": initial_status,
        "started_at": now,
        "updated_at": now,
        "created_at": now,
        "current_step": 0,
        "total_steps": total_steps if total_steps is not None else len(norm_steps),
        "steps": norm_steps,
        "retry_count": 0,
    }
    if initial_status == "awaiting_approval":
        if approval_meta is None:
            raise ValidationError("approval_meta required when initial_status='awaiting_approval'")
        data["approval_meta"] = approval_meta

    fd = _acquire_run_lock(path)
    try:
        _validate(data, schema_p)
        _atomic_write_json(data, path)
    finally:
        _release_run_lock(fd, path)

    _emit_workflow_event(
        project_slug=project_slug,
        workflow_action="started",
        workflow_run_id=run_id,
        workspace_root=workspace_root,
    )
    return RunHandle(run_id=run_id, project_slug=project_slug,
                     status=initial_status, path=path, data=data)


def transition(
    run_id: str,
    new_status: str,
    *,
    project_slug: str,
    workspace_root: Path | None = None,
    schema_path: Path | None = None,
    **context: Any,
) -> RunHandle:
    """Low-level transition: validates (from→to) and merges `context` into
    the run dict before schema-validating + atomic write."""
    schema_p = schema_path or _DEFAULT_SCHEMA_PATH
    path = _run_path(run_id, project_slug, workspace_root)

    fd = _acquire_run_lock(path)
    try:
        data = _read_run(path)
        _check_transition(data["status"], new_status)
        # Append-only merge: never delete existing keys (paused_at survives
        # resume per rules/append-only-state.md).
        for k, v in context.items():
            if v is None and k in data:
                continue
            data[k] = v
        data["status"] = new_status
        data["updated_at"] = _utc_iso_z()
        if new_status in ("done", "failed") and "ended_at" not in data:
            data["ended_at"] = data["updated_at"]
        _validate(data, schema_p)
        _atomic_write_json(data, path)
    finally:
        _release_run_lock(fd, path)

    return RunHandle(run_id=run_id, project_slug=project_slug,
                     status=new_status, path=path, data=data)


def request_approval(
    run_id: str,
    *,
    project_slug: str,
    approver: str,
    subject: str,
    prompt: str | None = None,
    deadline: str | None = None,
    step_index: int | None = None,
    workspace_root: Path | None = None,
    schema_path: Path | None = None,
) -> RunHandle:
    """Move a running run to awaiting_approval; populate approval_meta."""
    if not approver:
        raise ValidationError("approver is required for request_approval")
    if not subject:
        raise ValidationError("subject is required for request_approval")
    meta: dict[str, Any] = {"approver": approver, "subject": subject}
    if deadline:
        meta["deadline"] = deadline

    handle = transition(
        run_id, "awaiting_approval",
        project_slug=project_slug,
        workspace_root=workspace_root,
        schema_path=schema_path,
        approval_meta=meta,
    )
    # Also flip the named step to awaiting_approval if requested.
    if step_index is not None:
        _patch_step(
            run_id, project_slug, step_index,
            patch={"status": "awaiting_approval", "approval_prompt": prompt or subject},
            workspace_root=workspace_root, schema_path=schema_path,
        )
    return handle


def _do(run_id: str, new_status: str, action: str, *,
        project_slug: str, workspace_root: Path | None,
        schema_path: Path | None, event_notes: str | None = None,
        **context: Any) -> RunHandle:
    """Shared transition+emit. action = workflow_action enum string.

    event_notes (P1-10): optional free-text mirrored into the emitted workflow
    event's `notes` metadata (e.g. pause reason / approve notes). The same text
    is persisted into the run JSON by the caller via `context`.
    """
    handle = transition(
        run_id, new_status,
        project_slug=project_slug,
        workspace_root=workspace_root,
        schema_path=schema_path,
        **context,
    )
    _emit_workflow_event(
        project_slug=project_slug, workflow_action=action,
        workflow_run_id=run_id, workspace_root=workspace_root,
        notes=event_notes,
    )
    return handle


def approve(run_id: str, *, project_slug: str, approver: str,
            notes: str | None = None, workspace_root: Path | None = None,
            schema_path: Path | None = None) -> RunHandle:
    """Resume awaiting_approval → running. notes (P1-10): persisted into the run
    JSON and mirrored into the emitted workflow event metadata."""
    if not approver:
        raise ValidationError("approver is required for approve()")
    context: dict[str, Any] = {"resumed_at": _utc_iso_z()}
    if notes:
        context["notes"] = notes
    return _do(run_id, "running", "approved",
               project_slug=project_slug, workspace_root=workspace_root,
               schema_path=schema_path, event_notes=notes, **context)


def reject(run_id: str, *, project_slug: str, approver: str, reason: str,
           terminal: bool = True, workspace_root: Path | None = None,
           schema_path: Path | None = None) -> RunHandle:
    """Reject approval. terminal=True → failed; False → paused."""
    if not approver:
        raise ValidationError("approver is required for reject()")
    if not reason:
        raise ValidationError("reason is required for reject()")
    if terminal:
        return _do(run_id, "failed", "rejected",
                   project_slug=project_slug, workspace_root=workspace_root,
                   schema_path=schema_path,
                   failure_reason={"code": "user_rejected", "message": reason})
    return _do(run_id, "paused", "rejected",
               project_slug=project_slug, workspace_root=workspace_root,
               schema_path=schema_path, paused_at=_utc_iso_z())


def pause(run_id: str, *, project_slug: str, reason: str | None = None,
          workspace_root: Path | None = None,
          schema_path: Path | None = None) -> RunHandle:
    """Pause running or awaiting_approval → paused. reason (P1-10): persisted
    into the run JSON and mirrored into the emitted workflow event metadata."""
    context: dict[str, Any] = {"paused_at": _utc_iso_z()}
    if reason:
        context["reason"] = reason
    return _do(run_id, "paused", "paused",
               project_slug=project_slug, workspace_root=workspace_root,
               schema_path=schema_path, event_notes=reason, **context)


def resume(run_id: str, *, project_slug: str,
           workspace_root: Path | None = None,
           schema_path: Path | None = None) -> RunHandle:
    """Resume paused → running. paused_at preserved (append-only)."""
    return _do(run_id, "running", "resumed",
               project_slug=project_slug, workspace_root=workspace_root,
               schema_path=schema_path, resumed_at=_utc_iso_z())


def fail(run_id: str, *, project_slug: str, code: str, message: str,
         step_index: int | None = None, error_details: str | None = None,
         external: bool = False,
         workspace_root: Path | None = None,
         schema_path: Path | None = None) -> RunHandle:
    """Move a running run → failed; record failure_reason.

    external (AMO 1a, spec D4): when True, set failure_reason.external=true to
    flag an EXTERNAL dependency failure (GSC/DFS outage, quota, network) the
    denetçi maps onto the existing `paused` state. Default False leaves the key
    absent, so the persisted JSON of every existing fail() call is unchanged.
    """
    failure: dict[str, Any] = {"code": code, "message": message}
    if step_index is not None:
        failure["step_index"] = step_index
    if external:
        failure["external"] = True
    handle = transition(run_id, "failed", project_slug=project_slug,
                        workspace_root=workspace_root, schema_path=schema_path,
                        failure_reason=failure)
    if step_index is not None:
        _patch_step(
            run_id, project_slug, step_index,
            patch={"status": "failed", "ended_at": _utc_iso_z(),
                   **({"error": error_details} if error_details else {})},
            workspace_root=workspace_root, schema_path=schema_path,
        )
    _emit_workflow_event(
        project_slug=project_slug, workflow_action="failed",
        workflow_run_id=run_id, workspace_root=workspace_root,
        step_index=step_index,
    )
    return handle


def retry(run_id: str, *, project_slug: str,
          workspace_root: Path | None = None,
          schema_path: Path | None = None) -> RunHandle:
    """failed → running, retry_count++ (ADR-019). Failed step entries kept."""
    schema_p = schema_path or _DEFAULT_SCHEMA_PATH
    path = _run_path(run_id, project_slug, workspace_root)
    fd = _acquire_run_lock(path)
    try:
        data = _read_run(path)
        _check_transition(data["status"], "running")
        data["status"] = "running"
        data["retry_count"] = int(data.get("retry_count", 0)) + 1
        data["updated_at"] = _utc_iso_z()
        # P1-10: preserve the prior terminal timing before clearing ended_at —
        # otherwise the ended_at of each failed attempt is lost forever.
        prior: dict[str, Any] = {}
        if "ended_at" in data:
            prior["ended_at"] = data["ended_at"]
        if "failure_reason" in data:
            prior["failure_reason"] = data["failure_reason"]
        if prior:
            history = list(data.get("retry_history", []))
            history.append(prior)
            data["retry_history"] = history
        # Clear ended_at; keep failure_reason as historical evidence.
        if "ended_at" in data:
            del data["ended_at"]
        _validate(data, schema_p)
        _atomic_write_json(data, path)
    finally:
        _release_run_lock(fd, path)
    _emit_workflow_event(
        project_slug=project_slug, workflow_action="retried",
        workflow_run_id=run_id, workspace_root=workspace_root,
    )
    return RunHandle(run_id=run_id, project_slug=project_slug,
                     status="running", path=path, data=data)


def complete(run_id: str, *, project_slug: str, outputs: dict | None = None,
             workspace_root: Path | None = None,
             schema_path: Path | None = None) -> RunHandle:
    """running → done; optional outputs map."""
    extra: dict[str, Any] = {}
    if outputs is not None:
        extra["outputs"] = outputs
    return _do(run_id, "done", "done",
               project_slug=project_slug, workspace_root=workspace_root,
               schema_path=schema_path, **extra)


def start_step(run_id: str, step_index: int, *, project_slug: str,
               workspace_root: Path | None = None,
               schema_path: Path | None = None) -> RunHandle:
    """Mark steps[i] running + started_at; bump current_step. No event emit."""
    return _patch_step(
        run_id, project_slug, step_index,
        patch={"status": "running", "started_at": _utc_iso_z()},
        workspace_root=workspace_root, schema_path=schema_path,
        also_update={"current_step": step_index},
    )


def finish_step(run_id: str, step_index: int, *, project_slug: str,
                output_ref: str | None = None, error: str | None = None,
                status: str = "done",
                workspace_root: Path | None = None,
                schema_path: Path | None = None) -> RunHandle:
    """Mark steps[i] done/failed/skipped + ended_at. No event emit."""
    if status not in ("done", "failed", "skipped"):
        raise ValidationError(f"finish_step status must be done|failed|skipped, got {status!r}")
    patch: dict[str, Any] = {"status": status, "ended_at": _utc_iso_z()}
    if output_ref:
        patch["output_ref"] = output_ref
    if error:
        patch["error"] = error
    return _patch_step(run_id, project_slug, step_index, patch=patch,
                       workspace_root=workspace_root, schema_path=schema_path)


def get(run_id: str, *, project_slug: str,
        workspace_root: Path | None = None) -> RunHandle:
    """Read run handle from disk."""
    path = _run_path(run_id, project_slug, workspace_root)
    data = _read_run(path)
    return RunHandle(run_id=run_id, project_slug=project_slug,
                     status=data["status"], path=path, data=data)


def list_runs(project_slug: str, *, workspace_root: Path | None = None,
              status_filter: str | None = None) -> list[RunHandle]:
    """List runs for a project; optional status filter."""
    wf_dir = _workflows_dir(project_slug, workspace_root)
    out: list[RunHandle] = []
    for p in sorted(wf_dir.glob("*.json")):
        try:
            data = _read_run(p)
        except (CorruptStateError, SchemaVersionMismatchError):
            continue
        if status_filter and data.get("status") != status_filter:
            continue
        out.append(RunHandle(
            run_id=data["run_id"], project_slug=project_slug,
            status=data["status"], path=p, data=data,
        ))
    return out


# ---------------------------------------------------------------------------
# Internals — step patcher
# ---------------------------------------------------------------------------

def _patch_step(
    run_id: str,
    project_slug: str,
    step_index: int,
    *,
    patch: dict,
    workspace_root: Path | None,
    schema_path: Path | None,
    also_update: dict | None = None,
) -> RunHandle:
    schema_p = schema_path or _DEFAULT_SCHEMA_PATH
    path = _run_path(run_id, project_slug, workspace_root)

    fd = _acquire_run_lock(path)
    try:
        data = _read_run(path)
        steps = data.get("steps") or []
        if step_index < 0 or step_index >= len(steps):
            raise ValidationError(
                f"step_index {step_index} out of bounds (steps={len(steps)})"
            )
        step = dict(steps[step_index])
        step.update(patch)
        steps[step_index] = step
        data["steps"] = steps
        if also_update:
            data.update(also_update)
        data["updated_at"] = _utc_iso_z()
        _validate(data, schema_p)
        _atomic_write_json(data, path)
    finally:
        _release_run_lock(fd, path)

    return RunHandle(run_id=run_id, project_slug=project_slug,
                     status=data["status"], path=path, data=data)


# ---------------------------------------------------------------------------
# Internals — event emission
# ---------------------------------------------------------------------------

def _emit_workflow_event(*, project_slug: str, workflow_action: str,
                         workflow_run_id: str, workspace_root: Path | None,
                         step_index: int | None = None,
                         notes: str | None = None) -> None:
    """Emit event_kind=workflow (ADR-020). Failure does NOT undo the run JSON
    write — emission is non-blocking by design. P1-10: a failed emit is no
    longer swallowed silently; it surfaces a visible WARNING on stderr. The
    catch is broad (any exception) so an event-writer hiccup can never roll back
    a transition that already committed to disk. `notes` (when given) is mirrored
    into the event's free-text metadata (pause reason / approve notes).

    #9 / operator decision D-B: a failed emit ALSO writes a DURABLE ANOMALY into
    the _state/anomalies.jsonl sidecar — a SEPARATE path from the events.jsonl
    whose emit just failed — so a transition that lands a run-state change WITHOUT
    its audit event stays reconcilable. The run state is kept (no roll-back) and
    the caller is never hard-blocked. Recording the anomaly is itself best-effort:
    a fallback failure is downgraded to a WARNING, never re-raised."""
    extra: dict[str, Any] = {}
    if notes:
        extra["notes"] = notes
    try:
        events_writer.append_workflow(
            project_id=project_slug, workflow_action=workflow_action,
            workflow_run_id=workflow_run_id, step_index=step_index,
            workspace_root=workspace_root, **extra,
        )
    except Exception as exc:
        _log(
            f"WARNING: workflow event emit failed (non-blocking) "
            f"({workflow_action} {workflow_run_id}): {exc}"
        )
        try:
            # _workflows_dir already validated the slug + resolved the workspace
            # root when the run JSON was written moments ago; its parent is the
            # project's _state dir where anomalies.jsonl lives beside events.jsonl.
            state_dir = _workflows_dir(project_slug, workspace_root).parent
            anomaly_recorder.record_anomaly(
                state_dir,
                kind="workflow_event_emit_failed",
                detail={
                    "workflow_run_id": workflow_run_id,
                    "workflow_action": workflow_action,
                    "step_index": step_index,
                },
                error=f"{type(exc).__name__}: {exc}",
            )
        except Exception as rec_exc:  # never re-brick on a fallback failure
            _log(
                f"WARNING: anomaly record ALSO failed for workflow "
                f"{workflow_run_id} ({workflow_action}), unreconcilable: {rec_exc}"
            )


# ---------------------------------------------------------------------------
# Module export list
# ---------------------------------------------------------------------------

__all__: Iterable[str] = (
    "RunHandle",
    "WorkflowError",
    "IllegalTransitionError",
    "ValidationError",
    "ConcurrentMutationError",
    "RunIdCollisionError",
    "RunNotFoundError",
    "CorruptStateError",
    "SchemaVersionMismatchError",
    "StepNameDuplicateError",
    "create_run",
    "transition",
    "approve",
    "reject",
    "request_approval",
    "pause",
    "resume",
    "fail",
    "retry",
    "complete",
    "start_step",
    "finish_step",
    "get",
    "list_runs",
)
