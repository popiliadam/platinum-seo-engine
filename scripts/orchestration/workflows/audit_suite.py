"""The ``audit`` workflow: tech_audit + schema_audit + on_page_audit + cannibalization.

The technical-SEO audit suite. Path A (no DAG engine): a hard-coded ORDERED step
table + the shared ``workflow_driver``. The DELIVERABLE is the four committed
sheets — there is NO model_attested report step (unlike monthly).

1d.1 fix — the audit CLIs do NOT all write ``{sheet}.json``: schema_audit's CLI
writes ``schema_audit.json`` though its sheet is ``schema``. So each STEPS entry
carries an EXPLICIT ``output_file`` (the committer writes ``sheet``; the shared
loader reads ``output_file`` via the canonical filename-keyed
``workflow_driver.output_path``). The integration test locks this map against drift.

Silent-skip seam (the one real design seam) — audit transforms ANALYZE: tech_audit
aggregates per-URL findings to ~5 issue-category rows; schema_audit collapses
>=3-URL signatures to one site-wide row; cannibalization groups query x page rows
to per-conflict rows — each legitimately commits <50% of its raw input, so
enforcing ``silent_skip`` would FALSE-FAIL them. Those three are ``model_attested``:
the identity+content+freshness gate STILL runs, but the silent-skip COUNT check is
advisory. ``on_page_audit`` emits one row per input URL (output >= input), so it
stays ``code_verified`` with silent_skip enforced. The shared driver's ``_run_one``
dispatch routes each class to the right runner; ``run_step`` itself is unchanged.

Pure + clock-free: ``now_epoch`` and ``run_id`` are passed IN (the CLI requires
``--now-epoch``); nothing here reads the wall clock.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.orchestration import committer, workflow_driver
from scripts.orchestration.remediation import remediation, render

WORKFLOW = "audit"

# Module-level ORDERED step table (data-driven). Each entry carries an EXPLICIT
# ``output_file`` because the audit CLIs do NOT all write ``{sheet}.json`` (the
# 1d.1 trap: schema_audit -> schema_audit.json, sheet ``schema``). ``writer``
# preserves the identity each skill stamps today. ``verification_class`` encodes
# the silent-skip seam: ``code_verified`` = per-URL ingestion (gate meaningful);
# ``model_attested`` = analysis that legitimately reshapes cardinality (the
# silent-skip ratio is advisory, never a false-fail). Audit is point-in-time so
# NO step pins a ``window``; only the GSC-sourced step pins a ``site_url``;
# schema_audit is SF-or-file so it pins NO ``tool``.
STEPS: tuple[dict, ...] = (
    {"name": "tech_audit", "sheet": "tech_seo", "output_file": "tech_seo.json",
     "writer": "tech-audit", "tool": "mcp__dataforseo__on_page_lighthouse",
     "site_url": False, "verification_class": "model_attested"},
    {"name": "schema_audit", "sheet": "schema", "output_file": "schema_audit.json",
     "writer": "schema-audit", "tool": None,
     "site_url": False, "verification_class": "model_attested"},
    {"name": "on_page_audit", "sheet": "on_page_audit",
     "output_file": "on_page_audit.json", "writer": "on-page-audit",
     "tool": "mcp__dataforseo__on_page_content_parsing",
     "site_url": False, "verification_class": "code_verified"},
    {"name": "cannibalization", "sheet": "cannibalization",
     "output_file": "cannibalization.json", "writer": "cannibalization",
     "tool": "mcp__gsc__search_analytics",
     "site_url": True, "verification_class": "model_attested"},
)

# Re-export the shared helpers as module attributes (preserves the public surface
# the tests + the oracle import from this module). ``output_path`` is the canonical
# OUTPUT_FILE-keyed helper (audit addresses output by its explicit output_file).
WorkflowError = workflow_driver.WorkflowError
inbox_path = workflow_driver.inbox_path
output_path = workflow_driver.output_path
_output_loader = workflow_driver._output_loader


def build_steps(run_id: str, project_slug: str, workspace_root: Path | str) -> list:
    """One StepSpec per STEPS entry (delegates to the shared driver)."""
    return workflow_driver.build_steps(STEPS, run_id, project_slug, workspace_root)


def run(
    run_id: str, project_slug: str, workspace_root: Path | str,
    workbook_path: Path | str, now_epoch: float, *, write: bool = True,
    schema_path: Path | str | None = None, commit_fn=committer.commit,
    engine_version: str | None = None,
) -> dict:
    """Run the audit workflow and return (and optionally write) its coverage record.

    A failing/missing step NEVER aborts the loop — every step is recorded and the
    verdict reflects the failure. The deliverable is all four committed sheets, so
    a non-satisfied step (incl. a SOFT missing model_attested step) can never read
    'pass' (the driver's completion guard).
    """
    return workflow_driver.run_workflow(
        STEPS, run_id, project_slug, workspace_root, workbook_path, now_epoch,
        write=write, schema_path=schema_path, commit_fn=commit_fn,
        engine_version=engine_version,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.orchestration.workflows.audit_suite",
        description="Verify + commit + record coverage for an audit-suite run.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--now-epoch", required=True, type=float)
    parser.add_argument("--engine-version", default=None)
    parser.add_argument("--no-write", dest="write", action="store_false")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI boundary: parse args, run the driver, surface the Turkish remediation."""
    args = _build_arg_parser().parse_args(argv)
    record = run(
        args.run_id, args.slug, Path(args.workspace_root), Path(args.workbook),
        args.now_epoch, write=args.write, engine_version=args.engine_version,
    )
    print(f"verdict: {record['verdict']}")
    fix = remediation(record, slug=args.slug, workflow=WORKFLOW)
    if fix is not None:
        print(render(fix))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
