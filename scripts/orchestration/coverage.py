"""Coverage-record builders + validation + atomic write for the AMO spine.

The coverage record (``schemas/coverage.schema.json``, frozen in batch 1a) is the
INDEPENDENT per-run proof ``run_step`` writes to
``projects/{slug}/_state/coverage/{run_id}.json`` and the denetçi Stop-hook (2c)
+ correctness oracle read. ``additionalProperties:false`` holds at BOTH the
record and step level, so these builders emit ONLY declared keys (an optional key
is omitted when absent rather than written as null).

The record is a MUTABLE marker file (rewritten as the run progresses), so the
os.replace-based atomic write reused from ``session_binding`` is CORRECT here —
this is NOT an append-only events.jsonl log.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

# Sanctioned reuse of the canonical atomic JSON writer (tempfile -> fsync ->
# os.replace -> dir fsync) rather than inventing a subtly different one.
from scripts.state.session_binding import _atomic_write_json
# build_validator (not a raw Draft7Validator) so coverage.schema.json's
# created_at/updated_at format:date-time is ENFORCED with the strict UTC '…Z'
# checker (P1-02 / time-discipline §8.10).
from scripts.validation.validate_schema import build_validator

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_COVERAGE_SCHEMA = _ROOT / "schemas" / "coverage.schema.json"

_VERIFICATION_CLASSES = frozenset({"code_verified", "model_attested"})
_STEP_STATUSES = frozenset(
    {"pending", "running", "satisfied", "missing", "failed", "skipped"}
)


class CoverageError(Exception):
    """Base error for coverage-record assembly / validation."""


class CoverageValidationError(CoverageError):
    """A record failed schema validation; nothing was written."""


def build_step(
    name: str,
    verification_class: str,
    status: str,
    *,
    observed_mcp: Iterable[str] | None = None,
    input_count: int | None = None,
    scored_count: int | None = None,
) -> dict:
    """Build ONE coverage step dict with only the declared keys present.

    Validates the two enums defensively (raise ``ValueError`` on an unknown value
    — fail loud rather than emit a record the frozen schema will reject). Optional
    keys are included only when provided / non-empty; ``observed_mcp`` is COPIED
    so the caller's list cannot leak into the step.
    """
    if verification_class not in _VERIFICATION_CLASSES:
        raise ValueError(
            f"unknown verification_class {verification_class!r} "
            f"(expected one of {sorted(_VERIFICATION_CLASSES)})"
        )
    if status not in _STEP_STATUSES:
        raise ValueError(
            f"unknown step status {status!r} (expected one of {sorted(_STEP_STATUSES)})"
        )
    step: dict[str, Any] = {
        "name": name,
        "verification_class": verification_class,
        "status": status,
    }
    if observed_mcp:
        step["observed_mcp"] = list(observed_mcp)
    if input_count is not None:
        step["input_count"] = input_count
    if scored_count is not None:
        step["scored_count"] = scored_count
    return step


def build_record(
    *,
    run_id: str,
    steps: Sequence[dict],
    required_satisfied: bool,
    verdict: str,
    project_slug: str | None = None,
    engine_version: str | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
    schema_version: str | None = "1.0",
) -> dict:
    """Assemble a coverage record from its required fields plus any optionals.

    Optional metadata is included only when provided, so
    ``additionalProperties:false`` holds and the shape stays minimal. ``steps`` is
    copied into a new list (the caller's sequence is not retained).
    """
    record: dict[str, Any] = {
        "run_id": run_id,
        "steps": list(steps),
        "required_satisfied": required_satisfied,
        "verdict": verdict,
    }
    if schema_version is not None:
        record["schema_version"] = schema_version
    if project_slug is not None:
        record["project_slug"] = project_slug
    if engine_version is not None:
        record["engine_version"] = engine_version
    if created_at is not None:
        record["created_at"] = created_at
    if updated_at is not None:
        record["updated_at"] = updated_at
    return record


def coverage_path(workspace_root: Path | str, project_slug: str, run_id: str) -> Path:
    """``{workspace_root}/projects/{slug}/_state/coverage/{run_id}.json``."""
    return (
        Path(workspace_root)
        / "projects"
        / project_slug
        / "_state"
        / "coverage"
        / f"{run_id}.json"
    )


def _validate(record: dict, schema_path: Path) -> None:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    errors = list(build_validator(schema).iter_errors(record))
    if errors:
        msgs = "; ".join(e.message for e in errors)
        raise CoverageValidationError(f"invalid coverage record: {msgs}")


def write_coverage(
    record: dict,
    *,
    workspace_root: Path | str,
    project_slug: str,
    run_id: str,
    schema_path: Path | str | None = None,
) -> Path:
    """Validate, then atomically write the coverage record; return its path.

    Validation runs BEFORE the write, so an invalid record raises
    ``CoverageValidationError`` and writes NOTHING.
    """
    _validate(record, Path(schema_path) if schema_path else _DEFAULT_COVERAGE_SCHEMA)
    path = coverage_path(workspace_root, project_slug, run_id)
    _atomic_write_json(path, record)
    return path


def derive_verdict(steps: Sequence[dict]) -> tuple[bool, str]:
    """Map step statuses to ``(required_satisfied, verdict)``.

    ``required_satisfied`` = every code_verified step reached status 'satisfied'.
    ``verdict`` = 'failed' if ANY step failed; else 'incomplete' if a required
    (code_verified) step is missing; else 'pass' if required_satisfied; else
    'incomplete' (required steps not yet all satisfied). 'paused' is set by the
    denetçi (batch 2c), never here.
    """
    code_steps = [s for s in steps if s.get("verification_class") == "code_verified"]
    required_satisfied = all(s.get("status") == "satisfied" for s in code_steps)
    if any(s.get("status") == "failed" for s in steps):
        return required_satisfied, "failed"
    if any(s.get("status") == "missing" for s in code_steps):
        return required_satisfied, "incomplete"
    if required_satisfied:
        return required_satisfied, "pass"
    return required_satisfied, "incomplete"
