"""The ``monthly`` workflow: gsc_pull -> (quick_wins + content_decay) -> report.

Path A (no DAG engine): a hard-coded ORDERED step table + a thin driver. For each
STRUCTURED step the MODEL makes the MCP call, writes a provenance-stamped raw drop
to ``_state/inbox/{run_id}/{step}.json`` and runs the EXISTING transform CLI to
``_state/transform/{run_id}/{sheet}.json``; then this driver verifies + commits +
records coverage. The monthly-report step is MODEL_ATTESTED — the driver records
that it RAN (its artifact exists), it does NOT verify report quality (the honest
<=5% scope split). The denetçi that ENFORCES completion is a later batch (2c).

The transform impedance is resolved WITHOUT a run_step change: run_step's
``transform`` is used as a LOADER closure that IGNORES the verified raw rows and
returns the model-produced OUTPUT rows. The committer writes those (scored_count);
the silent-skip gate then compares raw input_count vs committed scored_count.

Pure + clock-free: ``now_epoch`` and ``run_id`` are passed IN (the CLI boundary
requires ``--now-epoch``); nothing here reads the wall clock.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from scripts.orchestration import committer, coverage
from scripts.orchestration.remediation import remediation, render
from scripts.orchestration.run_step import StepSpec, run_step

Transform = Callable[[list[dict]], list[dict]]

# Module-level ORDERED step table (data-driven). One entry per STRUCTURED
# (code_verified) step. quick_wins ALSO writes an `opportunity` sheet, but its
# coverage step is keyed on its PRIMARY sheet `quick_wins` (the secondary write
# is the skill's own concern); the step name stays stable across runs.
STEPS: tuple[dict, ...] = (
    {"name": "gsc_pull", "sheet": "gsc_performance", "writer": "gsc-pull",
     "site_url": True, "window": "recent", "tool": "mcp__gsc__search_analytics"},
    {"name": "quick_wins", "sheet": "quick_wins", "writer": "quick-wins",
     "site_url": True, "window": "30d", "tool": "mcp__gsc__detect_quick_wins"},
    {"name": "content_decay", "sheet": "content_decay", "writer": "content-decay",
     "site_url": True, "window": "recent", "tool": "mcp__gsc__enhanced_search_analytics"},
)

REPORT_STEP_NAME = "monthly_report"


class WorkflowError(Exception):
    """The model-produced transform output is missing or malformed."""


def inbox_path(workspace_root: Path | str, run_id: str, slug: str, step: str) -> Path:
    """``{workspace}/projects/{slug}/_state/inbox/{run_id}/{step}.json`` (raw drop)."""
    return (
        Path(workspace_root) / "projects" / slug / "_state" / "inbox" / run_id
        / f"{step}.json"
    )


def output_path(workspace_root: Path | str, run_id: str, slug: str, sheet: str) -> Path:
    """``{workspace}/projects/{slug}/_state/transform/{run_id}/{sheet}.json`` (output).

    Keyed by the step's SHEET, not its step name: the EXISTING transform CLIs
    write ``{sheet}.json`` (gsc_pull -> gsc_performance.json, quick_wins ->
    quick_wins.json, content_decay -> content_decay.json), so the loader reads
    exactly where the CLI writes. The RAW inbox drop stays keyed by step name.
    """
    return (
        Path(workspace_root) / "projects" / slug / "_state" / "transform" / run_id
        / f"{sheet}.json"
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
    """The project's ``gsc.site_url`` if resolvable, else None (never hard-fails)."""
    config = Path(workspace_root) / "projects" / slug / "project.config.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    gsc = data.get("gsc") if isinstance(data, dict) else None
    url = gsc.get("site_url") if isinstance(gsc, dict) else None
    return url if isinstance(url, str) and url else None


def build_steps(run_id: str, project_slug: str, workspace_root: Path | str) -> list[StepSpec]:
    """One StepSpec per STEPS entry: raw drop gated by identity+content, the
    loader-transform returns the committed output rows."""
    site_url = _resolve_site_url(workspace_root, project_slug)
    return [
        StepSpec(
            name=entry["name"],
            raw_path=inbox_path(workspace_root, run_id, project_slug, entry["name"]),
            sheet=entry["sheet"],
            transform=_output_loader(
                # output keyed by SHEET (the CLI writes {sheet}.json); raw drop
                # above stays keyed by step name.
                output_path(workspace_root, run_id, project_slug, entry["sheet"])
            ),
            verification_class="code_verified",
            expected_site_url=site_url,
            expected_window=entry["window"],
            expected_tool=entry["tool"],
            observed_mcp=(entry["tool"],),
        )
        for entry in STEPS
    ]


def _code_verified_steps(
    specs: list[StepSpec], *, run_id, project_slug, workspace_root, workbook_path,
    now_epoch, schema_path, commit_fn,
) -> list[dict]:
    """Run every structured spec through the spine; a failed/missing step never
    aborts the loop (mirrors run_sequence's no-abort contract)."""
    return [
        run_step(
            spec, run_id=run_id, project_slug=project_slug,
            workspace_root=workspace_root, workbook_path=workbook_path,
            now_epoch=now_epoch, schema_path=schema_path, commit_fn=commit_fn,
        )
        for spec in specs
    ]


def run(
    run_id: str, project_slug: str, workspace_root: Path | str,
    workbook_path: Path | str, now_epoch: float, *, write: bool = True,
    report_exists: bool | None = None, schema_path: Path | str | None = None,
    commit_fn=committer.commit, engine_version: str | None = None,
) -> dict:
    """Run the monthly workflow and return (and optionally write) its coverage record."""
    specs = build_steps(run_id, project_slug, workspace_root)
    steps = _code_verified_steps(
        specs, run_id=run_id, project_slug=project_slug,
        workspace_root=workspace_root, workbook_path=workbook_path,
        now_epoch=now_epoch, schema_path=schema_path, commit_fn=commit_fn,
    )
    report = coverage.build_step(
        REPORT_STEP_NAME, "model_attested",
        "satisfied" if report_exists else "missing", observed_mcp=[],
    )
    all_steps = [*steps, report]
    required_satisfied, verdict = coverage.derive_verdict(all_steps)
    # derive_verdict treats model_attested steps as SOFT, so an unsatisfied report
    # would read 'pass'. The monthly report IS the workflow's deliverable, so a
    # non-satisfied report can never be 'pass' (workflow-completion guard).
    if verdict == "pass" and report["status"] != "satisfied":
        verdict = "incomplete"
    record = coverage.build_record(
        run_id=run_id, steps=all_steps, required_satisfied=required_satisfied,
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
