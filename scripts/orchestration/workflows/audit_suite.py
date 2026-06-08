"""The ``audit`` workflow: tech_audit + schema_audit + on_page_audit + cannibalization.

The technical-SEO audit suite. Path A (no DAG engine): a hard-coded ORDERED step
table + a thin driver mirroring ``monthly_maintenance``. For each step the MODEL
makes the MCP call(s), writes a provenance-stamped raw drop to
``_state/inbox/{run_id}/{step}.json`` and runs the EXISTING transform CLI to
``_state/transform/{run_id}/{output_file}``; then this driver verifies + commits
(idempotent ``transaction.replace`` via the committer) + records coverage. The
DELIVERABLE is the four committed sheets — there is NO model_attested report step.

1d.1 fix — the audit CLIs do NOT all write ``{sheet}.json``: schema_audit's CLI
writes ``schema_audit.json`` though its sheet is ``schema``. So each STEPS entry
carries an EXPLICIT ``output_file`` (the committer writes ``sheet``; the loader
reads ``output_file``). The integration test locks this map against drift.

Silent-skip seam (the one real design seam) — monthly's steps are INGESTION-shaped
(raw rows ~= committed rows) so the >50%-drop ``silent_skip`` gate fits. AUDIT
transforms ANALYZE: tech_audit aggregates per-URL findings to ~5 issue-category
rows; schema_audit collapses >=3-URL signatures to one site-wide row;
cannibalization groups query x page rows to per-conflict rows — each legitimately
commits <50% of its raw input, so enforcing ``silent_skip`` would FALSE-FAIL them.
Those three are ``model_attested``: the identity+content+freshness gate
(``verify_raw_drop``) STILL runs, but the silent-skip COUNT check is advisory (the
counts are recorded, the ratio is not enforced). ``on_page_audit`` emits one row
per input URL (output >= input), so it stays ``code_verified`` with silent_skip
enforced. This composes the FROZEN spine's public modules (verify_raw_drop +
committer + coverage); ``run_step`` itself is unchanged.

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
from scripts.orchestration.run_step import StepSpec, run_step
from scripts.orchestration.verify import verify_raw_drop

Transform = Callable[[list[dict]], list[dict]]

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

    Keyed by the step's explicit ``output_file`` — NOT ``{sheet}.json`` like
    monthly — because schema_audit's CLI writes ``schema_audit.json`` while its
    sheet is ``schema``. The loader reads exactly where each CLI writes.
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
    """One StepSpec per STEPS entry: the raw drop is gated by identity+content,
    the loader-transform returns the committed output rows from ``output_file``.
    ``expected_window`` is None for every step (audit is point-in-time, not a date
    window); ``expected_site_url`` is pinned only for the GSC-sourced step; a step
    with no pinned tool (schema_audit) gates identity only."""
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


def _run_attested_step(
    spec: StepSpec, *, run_id: str, project_slug: str, workbook_path: Path | str,
    now_epoch: float, max_age_seconds: float = 86_400,
    schema_path: Path | str | None = None, commit_fn=committer.commit,
) -> dict:
    """Run ONE model_attested analysis step.

    The identity+content+freshness gate (``verify_raw_drop``) STILL runs and a bad
    drop fails the step exactly like run_step. But the silent-skip COUNT check is
    ADVISORY: an audit transform that aggregates (per-URL findings -> per-category
    rows; query x page -> per-conflict) legitimately commits <50% of its raw input,
    so the ratio is recorded (input_count/scored_count) but NEVER fails the step.
    Composes the frozen spine's public modules; run_step itself is unchanged.
    """
    vr = verify_raw_drop(
        spec.raw_path, expected_run_id=run_id, expected_slug=project_slug,
        now_epoch=now_epoch, expected_site_url=spec.expected_site_url,
        expected_window=spec.expected_window, expected_tool=spec.expected_tool,
        max_age_seconds=max_age_seconds,
    )
    if not vr.ok:
        status = "missing" if vr.reason == "missing_file" else "failed"
        return coverage.build_step(
            spec.name, spec.verification_class, status,
            observed_mcp=list(spec.observed_mcp),
        )
    rows_out = spec.transform(vr.rows)  # loader: model-produced output rows
    result = commit_fn(
        workbook_path, spec.sheet, rows_out,
        run_id=run_id, project_slug=project_slug, schema_path=schema_path,
    )
    return coverage.build_step(
        spec.name, spec.verification_class, "satisfied",
        observed_mcp=list(spec.observed_mcp),
        input_count=vr.input_count, scored_count=result.rows_affected,
    )


def _run_one(
    spec: StepSpec, *, run_id: str, project_slug: str, workspace_root: Path | str,
    workbook_path: Path | str, now_epoch: float,
    schema_path: Path | str | None, commit_fn,
) -> dict:
    """Dispatch one step: code_verified -> run_step (silent-skip ENFORCED);
    model_attested -> _run_attested_step (silent-skip ADVISORY)."""
    if spec.verification_class == "model_attested":
        return _run_attested_step(
            spec, run_id=run_id, project_slug=project_slug,
            workbook_path=workbook_path, now_epoch=now_epoch,
            schema_path=schema_path, commit_fn=commit_fn,
        )
    return run_step(
        spec, run_id=run_id, project_slug=project_slug,
        workspace_root=workspace_root, workbook_path=workbook_path,
        now_epoch=now_epoch, schema_path=schema_path, commit_fn=commit_fn,
    )


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
    # derive_verdict treats model_attested steps as SOFT, so a missing analysis
    # step alone would read 'pass'. The audit deliverable IS all four sheets, so
    # any non-satisfied step downgrades pass -> incomplete (completion guard).
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
