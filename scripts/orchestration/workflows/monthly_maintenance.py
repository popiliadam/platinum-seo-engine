"""The ``monthly`` workflow: gsc_pull -> (quick_wins + content_decay) -> report.

Path A (no DAG engine): a hard-coded ORDERED step table + the shared
``workflow_driver``. The three STRUCTURED steps are ``code_verified`` (per-row
ingestion: the silent-skip gate is meaningful); the trailing monthly-report step is
MODEL_ATTESTED — the driver records that it RAN (its artifact exists), it does NOT
verify report quality (the honest <=5% scope split).

Transform impedance (the monthly-specific wrinkle): the EXISTING transform CLIs
write ``{sheet}.json`` (gsc_pull -> gsc_performance.json, quick_wins ->
quick_wins.json, content_decay -> content_decay.json), so monthly addresses its
transform output BY SHEET. ``output_path`` below is therefore a SHEET-keyed wrapper
that bridges to the canonical filename-keyed ``workflow_driver.output_path`` by
appending ``.json``; each STEPS entry's ``output_file`` is ``f"{sheet}.json"`` so
the shared ``build_steps`` reads exactly where the CLI writes.

Pure + clock-free: ``now_epoch`` and ``run_id`` are passed IN (the CLI boundary
requires ``--now-epoch``); nothing here reads the wall clock.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.orchestration import committer, workflow_driver
from scripts.orchestration.remediation import remediation, render

# Module-level ORDERED step table (data-driven). One entry per STRUCTURED
# (code_verified) step. quick_wins ALSO writes an `opportunity` sheet, but its
# coverage step is keyed on its PRIMARY sheet `quick_wins` (the secondary write is
# the skill's own concern). ``output_file`` is ``{sheet}.json`` for every step (the
# CLIs write there); ``window`` is pinned because monthly is window-scoped.
STEPS: tuple[dict, ...] = (
    {"name": "gsc_pull", "sheet": "gsc_performance",
     "output_file": "gsc_performance.json", "writer": "gsc-pull",
     "site_url": True, "window": "recent", "tool": "mcp__gsc__search_analytics",
     "verification_class": "code_verified"},
    {"name": "quick_wins", "sheet": "quick_wins", "output_file": "quick_wins.json",
     "writer": "quick-wins", "site_url": True, "window": "30d",
     "tool": "mcp__gsc__detect_quick_wins", "verification_class": "code_verified"},
    {"name": "content_decay", "sheet": "content_decay",
     "output_file": "content_decay.json", "writer": "content-decay",
     "site_url": True, "window": "recent",
     "tool": "mcp__gsc__enhanced_search_analytics",
     "verification_class": "code_verified"},
)

REPORT_STEP_NAME = "monthly_report"

# Re-export the shared helpers as module attributes (preserves the public surface
# the tests + the oracle import from this module).
WorkflowError = workflow_driver.WorkflowError
inbox_path = workflow_driver.inbox_path
_output_loader = workflow_driver._output_loader


def output_path(workspace_root: Path | str, run_id: str, slug: str, sheet: str) -> Path:
    """``{workspace}/projects/{slug}/_state/transform/{run_id}/{sheet}.json``.

    SHEET-keyed (preserved): the monthly transform CLIs write ``{sheet}.json``, so
    monthly addresses its transform output by sheet. Bridges to the canonical
    filename-keyed ``workflow_driver.output_path`` by appending the ``.json`` suffix.
    """
    return workflow_driver.output_path(workspace_root, run_id, slug, f"{sheet}.json")


def build_steps(run_id: str, project_slug: str, workspace_root: Path | str) -> list:
    """One StepSpec per STEPS entry (delegates to the shared driver)."""
    return workflow_driver.build_steps(STEPS, run_id, project_slug, workspace_root)


def run(
    run_id: str, project_slug: str, workspace_root: Path | str,
    workbook_path: Path | str, now_epoch: float, *, write: bool = True,
    report_exists: bool | None = None, schema_path: Path | str | None = None,
    commit_fn=committer.commit, engine_version: str | None = None,
) -> dict:
    """Run the monthly workflow and return (and optionally write) its coverage record.

    The model_attested report step is appended after the structured steps; a
    non-satisfied report can never read 'pass' (the driver's completion guard).
    """
    return workflow_driver.run_workflow(
        STEPS, run_id, project_slug, workspace_root, workbook_path, now_epoch,
        write=write, schema_path=schema_path, commit_fn=commit_fn,
        engine_version=engine_version, report_step_name=REPORT_STEP_NAME,
        report_exists=bool(report_exists),
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.orchestration.workflows.monthly_maintenance",
        description="Verify + commit + record coverage for a monthly-maintenance run.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--now-epoch", required=True, type=float)
    parser.add_argument("--report-exists", action="store_true")
    parser.add_argument("--engine-version", default=None)
    parser.add_argument("--no-write", dest="write", action="store_false")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI boundary: parse args, run the driver, surface the Turkish remediation."""
    args = _build_arg_parser().parse_args(argv)
    record = run(
        args.run_id, args.slug, Path(args.workspace_root), Path(args.workbook),
        args.now_epoch, write=args.write, report_exists=args.report_exists,
        engine_version=args.engine_version,
    )
    print(f"verdict: {record['verdict']}")
    fix = remediation(record, slug=args.slug)
    if fix is not None:
        print(render(fix))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
