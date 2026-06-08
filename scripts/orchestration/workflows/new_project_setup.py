"""The ``setup`` workflow: topical_map -> cluster_map -> new_content_plan.

A NEW project's content-planning pipeline. After ``/pseo-init`` scaffolds the
project (the PRECONDITION — NOT part of this workflow), ``setup`` populates the
content plan IN ORDER: the pillar/cluster topical map, then the keyword clusters,
then the content-brief plan. Path A (no DAG engine): a hard-coded ORDERED step
table + the shared ``workflow_driver``. The DELIVERABLE is the three committed
sheets — there is NO model_attested report step.

All three CLIs write ``{sheet}.json`` (topical_map.json, cluster_keywords.json,
new_content_plan.json), so unlike 3b's schema_audit there is NO output_file vs
sheet impedance here. Each STEPS entry still carries an EXPLICIT ``output_file``
(consistent with audit_suite + future-proof) and the integration test locks it.

SEQUENTIAL DEPENDENCY (the wrinkle vs 3b) — the dependent transforms do NOT read
master.xlsx directly; the MODEL extracts the prior COMMITTED sheet and passes it as
an explicit CLI arg:

  * ``cluster_map`` CONSUMES ``master.xlsx#topical_map``: the model reads the
    committed topical_map ``cluster`` column (col B) and passes it as
    ``cluster_map_transform --cluster-defs-json`` (the D-02 source of truth).
  * ``new_content_plan`` CONSUMES ``master.xlsx#cluster_keywords``: the model
    builds a ``{keyword: cluster}`` map (via
    ``new_content_plan_transform.read_cluster_keywords_snapshot``) and passes it as
    ``--cluster-map``; ``assigned_cluster`` is cross-referenced from it.

Because the driver runs steps IN ORDER, each prior sheet is committed BEFORE the
dependent step runs — the ``consumes:`` frontmatter is satisfied by ORDERING, not a
driver change.

Silent-skip seam (the D15 cardinality decision) — every planning transform
AGGREGATES: topical_map collapses many DFS keywords into a small pillar/cluster
taxonomy; cluster_map dedups + drops no-cluster keywords; new_content_plan caps to
the top-N candidates by gap_score. Each legitimately commits <50% of its raw input,
so enforcing ``silent_skip`` would FALSE-FAIL them. All THREE steps are therefore
``model_attested``: the identity+content+freshness gate STILL runs (a wrong-run_id
/ stale / truncated drop is ``failed``), but the silent-skip COUNT check is advisory.
No setup step is per-row ingestion-shaped, so — unlike 3b — there is no
``code_verified`` step here. ``new_content_plan`` consumes a FILE-based content-gaps
staging drop (a Phase 7 producer), not a fresh primary MCP call, so it pins NO
``expected_tool`` (the schema_audit precedent).

The shared ``workflow_driver`` owns the D15 dispatch (``_run_one``): this module no
longer reaches into ``audit_suite`` for it (the O4 light-promote that retired the
old cross-driver import). Because every step is model_attested (which
``derive_verdict`` treats as SOFT, and ``required_satisfied`` is vacuously True over
zero code_verified steps), a missing step alone would read 'pass'. The setup
deliverable IS all three sheets, so the driver's COMPLETION GUARD downgrades
pass -> incomplete unless every step is satisfied — it is load-bearing for this
all-attested workflow.

Pure + clock-free: ``now_epoch`` and ``run_id`` are passed IN (the CLI requires
``--now-epoch``); nothing here reads the wall clock.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.orchestration import committer, workflow_driver
from scripts.orchestration.remediation import remediation, render

WORKFLOW = "setup"

# Module-level ORDERED step table (data-driven). Each entry carries an EXPLICIT
# ``output_file`` (= ``{sheet}.json`` for all three here — no 1d.1 trap — but
# explicit for consistency with audit_suite). ``writer`` preserves the identity
# each planning skill stamps today. ``verification_class`` is ``model_attested``
# for ALL THREE: every planning transform aggregates / caps, committing <50% of
# its raw input by design, so the silent-skip ratio is advisory. Planning is
# point-in-time so NO step pins a ``window``; the steps are DFS-primary
# (cluster_map's GSC is enrichment) so NO step pins a ``site_url``;
# new_content_plan is content-gaps-staging-sourced (file), so it pins NO ``tool``.
STEPS: tuple[dict, ...] = (
    {"name": "topical_map", "sheet": "topical_map", "output_file": "topical_map.json",
     "writer": "topical-map",
     "tool": "mcp__dataforseo__dataforseo_labs_google_keyword_ideas",
     "site_url": False, "verification_class": "model_attested"},
    {"name": "cluster_map", "sheet": "cluster_keywords",
     "output_file": "cluster_keywords.json", "writer": "cluster-map",
     "tool": "mcp__dataforseo__dataforseo_labs_google_keyword_suggestions",
     "site_url": False, "verification_class": "model_attested"},
    {"name": "new_content_plan", "sheet": "new_content_plan",
     "output_file": "new_content_plan.json", "writer": "new-content-plan",
     "tool": None,
     "site_url": False, "verification_class": "model_attested"},
)

# Re-export the shared helpers as module attributes (preserves the public surface
# the tests import from this module). ``output_path`` is the canonical
# OUTPUT_FILE-keyed helper (setup addresses output by its explicit output_file,
# which equals ``{sheet}.json`` for every setup step).
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
    """Run the setup workflow and return (and optionally write) its coverage record.

    A failing/missing step NEVER aborts the loop — every step is recorded and the
    verdict reflects the failure. The deliverable is all three committed sheets, so
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
        prog="python3 -m scripts.orchestration.workflows.new_project_setup",
        description="Verify + commit + record coverage for a new-project-setup run.",
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
