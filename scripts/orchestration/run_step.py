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
        )

    rows_out = spec.transform(vr.rows)  # pure; must not mutate vr.rows
    result = commit_fn(
        workbook_path,
        spec.sheet,
        rows_out,
        run_id=run_id,
        project_slug=project_slug,
        schema_path=schema_path,
    )
    scored = result.rows_affected
    status = "failed" if silent_skip_exceeds(vr.input_count, scored) else "satisfied"
    return coverage.build_step(
        spec.name,
        spec.verification_class,
        status,
        observed_mcp=list(spec.observed_mcp),
        input_count=vr.input_count,
        scored_count=scored,
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
        run_step(
            spec,
            run_id=run_id,
            project_slug=project_slug,
            workspace_root=workspace_root,
            workbook_path=workbook_path,
            now_epoch=now_epoch,
            max_age_seconds=max_age_seconds,
            schema_path=schema_path,
            commit_fn=commit_fn,
        )
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
