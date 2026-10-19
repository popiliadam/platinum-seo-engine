"""The orchestrator spine: verify -> transform -> commit -> coverage step.

``run_step`` composes the batch-1b modules for ONE workflow step: it gates the
raw drop (verify), runs the pure transform on the verified rows, commits them
through the INJECTABLE committer, applies the silent-skip gate, and returns the
COVERAGE STEP dict. The committer is injectable (``commit_fn``) so an e2e stub
harness can drive the whole spine with a fake committer — no live model, no MCP,
no real workbook.

``run_sequence`` runs an ordered list of steps, derives the run verdict, and
writes the coverage record. A failing/missing step NEVER aborts the loop — every
step is recorded; the verdict reflects the failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from scripts.orchestration import committer, coverage
from scripts.orchestration.verify import silent_skip_exceeds, verify_raw_drop

Transform = Callable[[list[dict]], list[dict]]
CommitFn = Callable[..., object]


@dataclass(frozen=True)
class StepSpec:
    """Immutable description of one orchestrator step."""

    name: str
    raw_path: Path
    sheet: str
    transform: Transform
    verification_class: str = "code_verified"
    required: bool = True
    expected_site_url: str | None = None
    expected_window: str | None = None
    expected_tool: str | None = None
    observed_mcp: tuple[str, ...] = ()
    allow_empty: bool = False


def precommit_rejects(
    spec: StepSpec, input_count: int, rows_out: list[dict], *, enforce_ratio: bool
) -> str | None:
    """The reason ``rows_out`` must NOT be committed (V-01), or None — checked
    BEFORE the write.

    ``replace`` clears the sheet first, so the count gate has to run before it:
    an empty output is refused unless the step declares ``allow_empty``; with
    ``enforce_ratio`` a drop of more than half the input is refused too
    (model_attested steps aggregate legitimately, so they skip the ratio).
    """
    if not rows_out:
        return None if spec.allow_empty else "empty_output"
    if enforce_ratio and silent_skip_exceeds(input_count, len(rows_out)):
        return "silent_skip"
    return None


def isolated_step(spec: StepSpec, run: Callable[[], dict]) -> dict:
    """Run one step; an exception raised inside it becomes a FAILED coverage step
    with an ``exception:<Type>`` reason instead of aborting the loop (V-09)."""
    try:
        return run()
    except Exception as exc:  # any step error is recorded, never escapes the loop
        return coverage.build_step(
            spec.name, spec.verification_class, "failed",
            observed_mcp=list(spec.observed_mcp),
            reason=f"exception:{type(exc).__name__}: {exc}"[:300],
        )


def empty_commit_kwargs(rows_out: list[dict]) -> dict:
    """``allow_empty=True`` for the (already approved) empty commit, else nothing —
    so injected fake committers with the narrow signature keep working."""
    return {} if rows_out else {"allow_empty": True}


def run_step(
    spec: StepSpec,
    *,
    run_id: str,
    project_slug: str,
    workspace_root: Path | str,
    workbook_path: Path | str,
    now_epoch: float,
    max_age_seconds: float = 86_400,
    schema_path: Path | str | None = None,
    commit_fn: CommitFn = committer.commit,
) -> dict:
    """Run one step and return its coverage step dict.

    ``workspace_root`` is accepted for call-convention symmetry with
    ``run_sequence`` (which writes the coverage record); ``run_step`` itself only
    returns a step dict and does not write.
    """
    vr = verify_raw_drop(
        spec.raw_path,
        expected_run_id=run_id,
        expected_slug=project_slug,
        now_epoch=now_epoch,
        expected_site_url=spec.expected_site_url,
        expected_window=spec.expected_window,
        expected_tool=spec.expected_tool,
        max_age_seconds=max_age_seconds,
    )
    if not vr.ok:
        status = "missing" if vr.reason == "missing_file" else "failed"
        return coverage.build_step(
            spec.name,
            spec.verification_class,
            status,
            observed_mcp=list(spec.observed_mcp),
            reason=vr.reason,
        )

    rows_out = spec.transform(vr.rows)  # pure; must not mutate vr.rows
    rejected = precommit_rejects(spec, vr.input_count, rows_out, enforce_ratio=True)
    if rejected:
        return coverage.build_step(
            spec.name,
            spec.verification_class,
            "failed",
            observed_mcp=list(spec.observed_mcp),
            input_count=vr.input_count,
            scored_count=len(rows_out),
            reason=rejected,
        )
    result = commit_fn(
        workbook_path,
        spec.sheet,
        rows_out,
        run_id=run_id,
        project_slug=project_slug,
        schema_path=schema_path,
        **empty_commit_kwargs(rows_out),
    )
    scored = result.rows_affected
    skipped = silent_skip_exceeds(vr.input_count, scored)
    return coverage.build_step(
        spec.name,
        spec.verification_class,
        "failed" if skipped else "satisfied",
        observed_mcp=list(spec.observed_mcp),
        input_count=vr.input_count,
        scored_count=scored,
        reason="silent_skip" if skipped else None,
    )


def run_sequence(
    specs: Sequence[StepSpec],
    *,
    run_id: str,
    project_slug: str,
    workspace_root: Path | str,
    workbook_path: Path | str,
    now_epoch: float,
    write: bool = True,
    max_age_seconds: float = 86_400,
    schema_path: Path | str | None = None,
    commit_fn: CommitFn = committer.commit,
    coverage_schema_path: Path | str | None = None,
    engine_version: str | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict:
    """Run an ordered list of steps, derive the verdict, build + (optionally)
    write the coverage record, and return it.

    A failing/missing step does NOT abort the loop — every step is recorded and
    the verdict reflects it.
    """
    steps = [
        isolated_step(spec, lambda spec=spec: run_step(
            spec,
            run_id=run_id,
            project_slug=project_slug,
            workspace_root=workspace_root,
            workbook_path=workbook_path,
            now_epoch=now_epoch,
            max_age_seconds=max_age_seconds,
            schema_path=schema_path,
            commit_fn=commit_fn,
        ))
        for spec in specs
    ]
    required_satisfied, verdict = coverage.derive_verdict(steps)
    record = coverage.build_record(
        run_id=run_id,
        steps=steps,
        required_satisfied=required_satisfied,
        verdict=verdict,
        project_slug=project_slug,
        engine_version=engine_version,
        created_at=created_at,
        updated_at=updated_at,
    )
    if write:
        coverage.write_coverage(
            record,
            workspace_root=workspace_root,
            project_slug=project_slug,
            run_id=run_id,
            schema_path=coverage_schema_path,
        )
    return record
