"""Shared DATA-driver machinery for the structured workflows (AMO batch 3-O4).

Faz 3 produced three DATA drivers — ``monthly_maintenance`` / ``audit_suite`` /
``new_project_setup`` — that each follow the SAME shape: for each ORDERED step the
MODEL makes the MCP call, writes a provenance-stamped raw drop to
``_state/inbox/{run_id}/{step}.json`` and runs the EXISTING transform CLI to
``_state/transform/{run_id}/{output_file}``; then the driver gates the raw drop
(``verify_raw_drop``), runs the loader-transform, commits through the INJECTABLE
committer, records coverage, derives the verdict, and writes the coverage record.
Roughly 80% of those three modules was copy-paste (and ``new_project_setup`` even
reached into ``audit_suite`` to import its dispatch). This module is the ONE shared
home for that machinery — a "light promote" (O4, Path A): NO new behaviour, NO
declarative DAG engine. Each workflow module is now a thin STEPS table + a handful
of wrappers that delegate here; the ``content_pipeline`` ARTIFACT driver is
structurally different and stays separate.

The transform impedance is resolved WITHOUT a ``run_step`` change: ``run_step``'s
``transform`` is used as a LOADER closure that IGNORES the verified raw rows and
returns the model-produced OUTPUT rows; the silent-skip gate then compares raw
``input_count`` vs committed ``scored_count``.

Output addressing is FILENAME-keyed here (``output_path(.., filename)`` joins
``.../{filename}``). The audit/setup CLIs do NOT all write ``{sheet}.json``
(schema_audit -> ``schema_audit.json`` though its sheet is ``schema``), so each
STEPS entry carries an explicit ``output_file``; the monthly module — whose CLIs
write ``{sheet}.json`` — keeps a SHEET-keyed ``output_path`` wrapper that bridges
to this canonical helper by appending the ``.json`` suffix.

The per-step dispatch (``_run_one``) routes a ``code_verified`` step to the FROZEN
spine ``run_step`` (silent-skip ENFORCED) and a ``model_attested`` step to
``_run_attested_step`` (the identity+content+freshness gate STILL runs, but the
silent-skip COUNT check is advisory so an aggregating transform that legitimately
commits <50% of its raw input is not false-failed).

This module COMPOSES the frozen spine's public modules (``run_step`` /
``verify_raw_drop`` / ``committer`` / ``coverage``) — it never edits them; the O4
move only relocates the per-workflow DUPLICATES into one place.

Pure + clock-free: ``now_epoch`` and ``run_id`` are passed IN; nothing here reads
the wall clock.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from scripts.orchestration import committer, coverage
from scripts.orchestration.run_step import StepSpec, run_step
from scripts.orchestration.verify import verify_raw_drop
from scripts.state.engine_version import engine_version as current_engine_version

Transform = Callable[[list[dict]], list[dict]]


class WorkflowError(Exception):
    """The model-produced transform output is missing or malformed."""


class EngineVersionMismatch(RuntimeError):
    """A RESUME crossed an engine-version boundary (spec §8).

    Raised at run start when a coverage record already exists for this run_id (a
    resume) and was stamped by a DIFFERENT engine version than the one now
    running — feeding OLD-shaped state to NEW code is refused (fail-loud
    "regenerate") rather than silently mixing versions.
    """


def inbox_path(workspace_root: Path | str, run_id: str, slug: str, step: str) -> Path:
    """``{workspace}/projects/{slug}/_state/inbox/{run_id}/{step}.json`` (raw drop,
    keyed by step NAME). This inbox convention is IDENTICAL across every workflow."""
    return (
        Path(workspace_root) / "projects" / slug / "_state" / "inbox" / run_id
        / f"{step}.json"
    )


def output_path(
    workspace_root: Path | str, run_id: str, slug: str, filename: str
) -> Path:
    """``{workspace}/projects/{slug}/_state/transform/{run_id}/{filename}`` (output).

    Canonical FILENAME-keyed addressing: the loader reads exactly where each CLI
    writes. Audit/setup pass each step's explicit ``output_file``; monthly passes
    ``f"{sheet}.json"`` (its SHEET-keyed wrapper bridges to this helper).
    """
    return (
        Path(workspace_root) / "projects" / slug / "_state" / "transform" / run_id
        / filename
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


def build_steps(
    steps_table: tuple[dict, ...], run_id: str, project_slug: str,
    workspace_root: Path | str,
) -> list[StepSpec]:
    """One StepSpec per ``steps_table`` entry: the raw drop is gated by
    identity+content, the loader-transform returns the committed output rows from
    the step's ``output_file``. ``expected_window`` is pinned only when the entry
    carries one (monthly); ``expected_site_url`` is pinned only for an entry flagged
    ``site_url``; a step with no pinned ``tool`` gates identity only."""
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
            expected_window=entry.get("window"),
            expected_tool=entry["tool"],
            observed_mcp=((entry["tool"],) if entry["tool"] else ()),
        )
        for entry in steps_table
    ]


def _run_attested_step(
    spec: StepSpec, *, run_id: str, project_slug: str, workbook_path: Path | str,
    now_epoch: float, max_age_seconds: float = 86_400,
    schema_path: Path | str | None = None, commit_fn=committer.commit,
) -> dict:
    """Run ONE model_attested analysis step.

    The identity+content+freshness gate (``verify_raw_drop``) STILL runs and a bad
    drop fails the step exactly like run_step. But the silent-skip COUNT check is
    ADVISORY: an analysis transform that aggregates (per-URL findings -> per-category
    rows; query x page -> per-conflict; many keywords -> a small taxonomy)
    legitimately commits <50% of its raw input, so the ratio is recorded
    (input_count/scored_count) but NEVER fails the step. Composes the frozen spine's
    public modules; run_step itself is unchanged.
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


def _assert_no_version_drift(
    *, workspace_root: Path | str, project_slug: str, run_id: str,
    current_version: str,
) -> None:
    """Run-start RESUME guard (spec §8). Raise ``EngineVersionMismatch`` ONLY when
    a coverage record already exists for this run_id (a resume) AND it carries a
    stored engine_version that DIFFERS from the one now running.

    A fresh run (no prior file), an un-stamped pre-4g prior (no engine_version
    key), or an unreadable prior is allowed — exactly as before 4g, the prior is
    treated as "unknown" and the run proceeds. The check reads but never writes,
    so a mismatch is detected BEFORE the prior record is overwritten.
    """
    prior_path = coverage.coverage_path(workspace_root, project_slug, run_id)
    if not prior_path.exists():
        return
    try:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    stored = prior.get("engine_version") if isinstance(prior, dict) else None
    if stored is not None and stored != current_version:
        raise EngineVersionMismatch(
            f"Motor sürümü uyuşmuyor: bu run ({run_id}) {stored!r} sürümüyle "
            f"üretildi, şimdiki sürüm {current_version!r}. Karışık (eski+yeni) "
            f"state üretmemek için run'ı yeniden oluşturun (regenerate); eski "
            f"coverage kaydı korundu."
        )


def _resolved_engine_version(
    engine_version: str | None, *, write: bool,
    workspace_root: Path | str, project_slug: str, run_id: str,
) -> str:
    """Resolve the producing engine version and guard a resume.

    The caller's explicit value wins; otherwise it is sourced ONCE from
    plugin.json. On a writing run, fail loud (before any step side effect) if this
    run_id resumes across a version boundary. A dry run (``write=False``) persists
    nothing, so the resume guard — a write-path concern — is not engaged.
    """
    resolved = (
        engine_version if engine_version is not None else current_engine_version()
    )
    if write:
        _assert_no_version_drift(
            workspace_root=workspace_root, project_slug=project_slug,
            run_id=run_id, current_version=resolved,
        )
    return resolved


def run_workflow(
    steps_table: tuple[dict, ...], run_id: str, project_slug: str,
    workspace_root: Path | str, workbook_path: Path | str, now_epoch: float, *,
    write: bool = True, schema_path: Path | str | None = None,
    commit_fn=committer.commit, engine_version: str | None = None,
    report_step_name: str | None = None, report_exists: bool = False,
) -> dict:
    """Run an ordered DATA workflow and return (and optionally write) its coverage
    record.

    A failing/missing step NEVER aborts the loop — every step is recorded and the
    verdict reflects the failure. When ``report_step_name`` is set, a trailing
    model_attested report step is appended (``satisfied`` iff ``report_exists``);
    its deliverable status feeds the completion guard. The COMPLETION GUARD
    downgrades ``pass -> incomplete`` when any step is not satisfied — load-bearing
    for the soft (model_attested) steps that ``derive_verdict`` treats as optional.
    """
    resolved_version = _resolved_engine_version(
        engine_version, write=write, workspace_root=workspace_root,
        project_slug=project_slug, run_id=run_id,
    )
    specs = build_steps(steps_table, run_id, project_slug, workspace_root)
    steps = [
        _run_one(
            spec, run_id=run_id, project_slug=project_slug,
            workspace_root=workspace_root, workbook_path=workbook_path,
            now_epoch=now_epoch, schema_path=schema_path, commit_fn=commit_fn,
        )
        for spec in specs
    ]
    if report_step_name is not None:
        steps = [
            *steps,
            coverage.build_step(
                report_step_name, "model_attested",
                "satisfied" if report_exists else "missing", observed_mcp=[],
            ),
        ]
    required_satisfied, verdict = coverage.derive_verdict(steps)
    if verdict == "pass" and not all(s["status"] == "satisfied" for s in steps):
        verdict = "incomplete"
    record = coverage.build_record(
        run_id=run_id, steps=steps, required_satisfied=required_satisfied,
        verdict=verdict, project_slug=project_slug, engine_version=resolved_version,
    )
    if write:
        coverage.write_coverage(
            record, workspace_root=workspace_root, project_slug=project_slug,
            run_id=run_id,
        )
    return record
