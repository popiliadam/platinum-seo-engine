"""The ``setup`` workflow: topical_map -> cluster_map -> new_content_plan.

A NEW project's content-planning pipeline. After ``/pseo-init`` scaffolds the
project (the PRECONDITION — NOT part of this workflow), ``setup`` populates the
content plan IN ORDER: the pillar/cluster topical map, then the keyword clusters,
then the content-brief plan. Path A (no DAG engine): a hard-coded ORDERED step
table + a thin driver mirroring ``audit_suite``. For each step the MODEL makes the
MCP call(s), writes a provenance-stamped raw drop to
``_state/inbox/{run_id}/{step}.json`` and runs the EXISTING planning transform CLI
to ``_state/transform/{run_id}/{output_file}``; then this driver verifies +
commits (idempotent ``transaction.replace`` via the committer) + records coverage.
The DELIVERABLE is the three committed sheets — there is NO model_attested report
step.

All three CLIs write ``{sheet}.json`` (topical_map.json, cluster_keywords.json,
new_content_plan.json), so unlike 3b's schema_audit there is NO output_file vs
sheet impedance here. Each STEPS entry still carries an EXPLICIT ``output_file``
(consistent with audit_suite + future-proof) and the integration test locks it.

SEQUENTIAL DEPENDENCY (the new wrinkle vs 3b) — the dependent transforms do NOT
read master.xlsx directly; the MODEL extracts the prior COMMITTED sheet and passes
it as an explicit CLI arg:

  * ``cluster_map`` CONSUMES ``master.xlsx#topical_map``: the model reads the
    committed topical_map ``cluster`` column (col B) and passes it as
    ``cluster_map_transform --cluster-defs-json`` (the D-02 source of truth).
  * ``new_content_plan`` CONSUMES ``master.xlsx#cluster_keywords``: the model
    builds a ``{keyword: cluster}`` map (via
    ``new_content_plan_transform.read_cluster_keywords_snapshot``) and passes it
    as ``--cluster-map``; ``assigned_cluster`` is cross-referenced from it.

Because the driver runs steps IN ORDER, each prior sheet is committed BEFORE the
dependent step runs — the ``consumes:`` frontmatter is satisfied by ORDERING, not
a driver change.

Silent-skip seam (the D15 cardinality decision) — every planning transform
AGGREGATES: topical_map collapses many DFS keywords into a small pillar/cluster
taxonomy; cluster_map dedups + drops no-cluster keywords; new_content_plan caps to
the top-N candidates by gap_score. Each legitimately commits <50% of its raw
input, so enforcing ``silent_skip`` would FALSE-FAIL them. All THREE steps are
therefore ``model_attested``: the identity+content+freshness gate
(``verify_raw_drop``) STILL runs (a wrong-run_id / stale / truncated drop is
``failed``), but the silent-skip COUNT check is advisory (recorded, never
enforced). No setup step is per-row ingestion-shaped, so — unlike 3b — there is no
``code_verified`` step here. ``new_content_plan`` consumes a FILE-based
content-gaps staging drop (a Phase 7 producer), not a fresh primary MCP call, so
it pins NO ``expected_tool`` (the schema_audit precedent).

This driver REUSES the FROZEN ``audit_suite`` D15 dispatch by IMPORTING
``_run_one`` (which transitively dispatches to ``audit_suite._run_attested_step``
for model_attested steps and the spine ``run_step`` for code_verified ones). Those
helpers take a ``StepSpec`` + run_id/slug/workbook/now_epoch and contain no
audit-specifics — they are workflow-agnostic. NB (O4 signal): the ``audit`` and
``setup`` drivers now SHARE this dispatch via import, so extracting it into a
shared module (e.g. ``run_step``) is now warranted — a future batch (it would edit
the frozen spine/audit, which is out of THIS batch's scope).

Because every step is model_attested (which ``derive_verdict`` treats as SOFT, and
``required_satisfied`` is vacuously True over zero code_verified steps), a missing
step alone would read 'pass'. The setup deliverable IS all three sheets, so the
COMPLETION GUARD downgrades pass -> incomplete unless every step is satisfied — it
is load-bearing for this all-attested workflow.

Pure + clock-free: ``now_epoch`` and ``run_id`` are passed IN (the CLI requires
``--now-epoch``); nothing here reads the wall clock.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from scripts.orchestration import committer, coverage
from scripts.orchestration.remediation import remediation, render
from scripts.orchestration.run_step import StepSpec
# REUSE the frozen audit_suite D15 dispatch (workflow-agnostic): _run_one routes
# code_verified -> run_step / model_attested -> _run_attested_step. Importing it
# avoids a third copy of the dispatch (see the O4 note in the module docstring).
from scripts.orchestration.workflows.audit_suite import _run_one

Transform = Callable[[list[dict]], list[dict]]

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


class WorkflowError(Exception):
    """The model-produced transform output is missing or malformed."""


def inbox_path(workspace_root: Path | str, run_id: str, slug: str, step: str) -> Path:
    """``{workspace}/projects/{slug}/_state/inbox/{run_id}/{step}.json`` (raw drop,
    keyed by step NAME)."""
    return (
        Path(workspace_root) / "projects" / slug / "_state" / "inbox" / run_id
        / f"{step}.json"
    )


def output_path(
    workspace_root: Path | str, run_id: str, slug: str, output_file: str
) -> Path:
    """``{workspace}/projects/{slug}/_state/transform/{run_id}/{output_file}``.

    Keyed by the step's explicit ``output_file`` (= ``{sheet}.json`` for every
    setup step). The loader reads exactly where each CLI writes.
    """
    return (
        Path(workspace_root) / "projects" / slug / "_state" / "transform" / run_id
        / output_file
    )


def _output_loader(output_file: Path | str) -> Transform:
    """A run_step transform that IGNORES the verified raw rows and returns the
    model-produced OUTPUT rows from ``output_file`` (a bare JSON list OR
    ``{"rows": [...]}``). Raises ``WorkflowError`` if missing/malformed."""

    def _load(_raw_rows: list[dict]) -> list[dict]:
        path = Path(output_file)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkflowError(f"transform output missing: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"transform output unreadable: {path}: {exc}") from exc
        rows = data.get("rows") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise WorkflowError(
                f"transform output malformed (expected list or {{'rows': [...]}}): {path}"
            )
        return rows

    return _load


def _resolve_site_url(workspace_root: Path | str, slug: str) -> str | None:
    """The project's ``gsc.site_url`` if resolvable, else None (never hard-fails).

    Kept for call-convention symmetry with audit_suite; no setup step actually
    pins a site_url (none is GSC-primary), so the resolved value is never used.
    """
    config = Path(workspace_root) / "projects" / slug / "project.config.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    gsc = data.get("gsc") if isinstance(data, dict) else None
    url = gsc.get("site_url") if isinstance(gsc, dict) else None
    return url if isinstance(url, str) and url else None


def build_steps(run_id: str, project_slug: str, workspace_root: Path | str) -> list[StepSpec]:
    """One StepSpec per STEPS entry: the raw drop is gated by identity+content,
    the loader-transform returns the committed output rows from ``output_file``.
    ``expected_window`` is None for every step (planning is point-in-time);
    ``expected_site_url`` is None for every step (none is GSC-primary);
    new_content_plan pins no ``expected_tool`` (file-sourced -> identity only)."""
    site_url = _resolve_site_url(workspace_root, project_slug)
    return [
        StepSpec(
            name=entry["name"],
            raw_path=inbox_path(workspace_root, run_id, project_slug, entry["name"]),
            sheet=entry["sheet"],
            transform=_output_loader(
                output_path(workspace_root, run_id, project_slug, entry["output_file"])
            ),
            verification_class=entry["verification_class"],
            expected_site_url=(site_url if entry["site_url"] else None),
            expected_window=None,
            expected_tool=entry["tool"],
            observed_mcp=((entry["tool"],) if entry["tool"] else ()),
        )
        for entry in STEPS
    ]


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
    'pass' (workflow-completion guard).
    """
    specs = build_steps(run_id, project_slug, workspace_root)
    steps = [
        _run_one(
            spec, run_id=run_id, project_slug=project_slug,
            workspace_root=workspace_root, workbook_path=workbook_path,
            now_epoch=now_epoch, schema_path=schema_path, commit_fn=commit_fn,
        )
        for spec in specs
    ]
    required_satisfied, verdict = coverage.derive_verdict(steps)
    # Every step is model_attested, which derive_verdict treats as SOFT (and
    # required_satisfied is vacuously True over zero code_verified steps), so a
    # missing analysis step alone would read 'pass'. The setup deliverable IS all
    # three sheets, so any non-satisfied step downgrades pass -> incomplete.
    if verdict == "pass" and not all(s["status"] == "satisfied" for s in steps):
        verdict = "incomplete"
    record = coverage.build_record(
        run_id=run_id, steps=steps, required_satisfied=required_satisfied,
        verdict=verdict, project_slug=project_slug, engine_version=engine_version,
    )
    if write:
        coverage.write_coverage(
            record, workspace_root=workspace_root, project_slug=project_slug,
            run_id=run_id,
        )
    return record


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
