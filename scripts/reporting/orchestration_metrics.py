#!/usr/bin/env python3
"""orchestration_metrics.py — the AMO INDEPENDENT correctness oracle (spec G5).

AMO claims "<=5% error on structured workflows" (spec G5). That number is
worthless if it is read back from the run's OWN self-reported status: a run can
write ``verdict="pass"`` while silently committing wrong/short data. This module
is the independent auditor. For each run it RE-DERIVES the truth from the actual
on-disk artifacts — the raw provenance drop the model wrote, the transform
output, and the COMMITTED ``master.xlsx`` — and reports whether they reconcile,
WITHOUT trusting the coverage record's ``verdict`` / ``scored_count``.

Headline number: the structured-error rate = (runs whose committed workbook does
NOT reconcile with their provenance) / (total reconcilable runs). The dangerous
catch is ``fake_green``: a run whose self-reported ``verdict == "pass"`` but whose
committed data does NOT reconcile — success was reported while the data is wrong.

The expected committed-row count is the length of the transform OUTPUT, NOT the
raw row count: steps like ``quick_wins`` legitimately FILTER their input, so
comparing committed-vs-raw would false-flag every filtering step. Reconcile
compares committed-vs-output (the transform output is the bridge); the raw->output
drop is surfaced separately as an advisory silent-skip signal (reusing
``verify.silent_skip_exceeds`` so the threshold cannot drift).

READ-ONLY: this module opens artifacts + the workbook (openpyxl read_only) and
writes NO state — it adds no hook, schema, or command and never blocks anything.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from openpyxl import load_workbook

from scripts.orchestration.coverage import coverage_path
from scripts.orchestration.verify import silent_skip_exceeds
from scripts.orchestration.workflows.monthly_maintenance import (
    STEPS,
    inbox_path,
    output_path,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SCHEMA_PATH = _REPO_ROOT / "schemas" / "master-excel.schema.json"

# Stable reason codes — a report keys on these strings, so a mismatch is always
# explainable (which of R1-R5 failed).
RAW_MISSING = "raw_missing"               # R1: raw drop absent / unparseable
IDENTITY_MISMATCH = "identity_mismatch"   # R1: provenance run_id/slug disagree
TRUNCATED = "truncated"                   # R2: declared_count != len(raw.rows)
OUTPUT_MISSING = "output_missing"         # R3: transform output absent / not a list
WORKBOOK_MISMATCH = "workbook_mismatch"   # R4: committed rows != len(output)
SCORED_COUNT_MISMATCH = "scored_count_mismatch"  # R5: scored_count != committed
WORKBOOK_ABSENT = "workbook_absent"       # no committed workbook to check R4/R5


# ---------------------------------------------------------------------------
# Artifact readers (thin IO; never raise for an expected-missing artifact)
# ---------------------------------------------------------------------------

def _read_json(path: Path | str) -> Any:
    """Parse JSON at ``path``; return the object, or None if missing/unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _output_rows(payload: Any) -> list | None:
    """Extract the row list from a transform-output payload.

    The transform output is a bare JSON list OR ``{"rows": [...]}`` (the two
    shapes monthly_maintenance._output_loader accepts). Returns the list, or None
    if the shape is neither.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return None


# ---------------------------------------------------------------------------
# Workbook reads (openpyxl read_only; degrade to None/False, never crash)
# ---------------------------------------------------------------------------

def committed_row_count(
    workbook_path: Path | str, sheet: str, data_start_row: int
) -> int | None:
    """Count CONTIGUOUS non-empty rows from ``data_start_row`` down.

    Reads the workbook read_only/data_only and, for worksheet ``sheet``, counts
    rows from ``data_start_row`` that have at least one non-None cell, stopping at
    the first all-empty row. This mirrors exactly how ``transaction.replace`` lands
    a single contiguous data block from ``data_start_row``, so the count is an
    independent re-derivation of what was committed (not a guess). Returns None if
    the workbook or sheet is missing/unreadable — the caller treats None as
    ``workbook_absent`` for that sheet (a reporting tool must never crash a build).
    """
    path = Path(workbook_path)
    if not path.exists():
        return None
    try:
        wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 — any read defect ⇒ "absent", never raise
        return None
    try:
        if sheet not in wb.sheetnames:
            return None
        ws = wb[sheet]
        count = 0
        for row in ws.iter_rows(min_row=data_start_row):
            if all(cell.value is None for cell in row):
                break
            count += 1
        return count
    finally:
        wb.close()


def _workbook_present(workbook_path: Path | str) -> bool:
    """True iff the workbook file exists and openpyxl can open it (read_only)."""
    path = Path(workbook_path)
    if not path.exists():
        return False
    try:
        wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 — unreadable ⇒ treated as absent
        return False
    wb.close()
    return True


def data_start_row_for(sheet: str, schema_path: Path | str | None = None) -> int:
    """Return ``sheets[sheet].data_start_row`` from master-excel.schema.json.

    Raises ``KeyError`` (clear message) if the sheet is unknown or declares no
    integer ``data_start_row`` — fail loud rather than silently miscount.
    """
    path = Path(schema_path) if schema_path else _DEFAULT_SCHEMA_PATH
    sheets = (json.loads(path.read_text(encoding="utf-8")).get("sheets") or {})
    if sheet not in sheets:
        raise KeyError(f"sheet {sheet!r} not in master-excel.schema.json")
    dsr = sheets[sheet].get("data_start_row")
    if not isinstance(dsr, int):
        raise KeyError(f"sheet {sheet!r} declares no integer data_start_row")
    return dsr


# ---------------------------------------------------------------------------
# Reconcile core (pure) + IO wrapper
# ---------------------------------------------------------------------------

def _reconcile_step_data(
    *,
    run_id: str,
    slug: str,
    step_name: str,
    sheet: str,
    raw: Any,
    output_rows: list | None,
    committed_count: int | None,
    scored_count: int | None,
    has_workbook: bool,
) -> dict:
    """Apply R1-R5 to already-read data; build a NEW result dict (no mutation).

    R4/R5 are evaluated ONLY when ``has_workbook`` is True; otherwise they are
    skipped (committed_count stays None) and the run layer marks the run absent.
    ``high_silent_skip`` is ADVISORY ONLY (reuses verify.silent_skip_exceeds) and
    never affects ``independent_ok`` — a step may legitimately drop >50% of its
    raw input (filtering) yet still reconcile.
    """
    failed: list[str] = []

    prov = raw.get("provenance") if isinstance(raw, dict) else None
    raw_rows = raw.get("rows") if isinstance(raw, dict) else None
    raw_count = len(raw_rows) if isinstance(raw_rows, list) else None

    # R1 identity + R2 untruncated — only when the raw drop is structurally sound.
    if not isinstance(prov, dict) or not isinstance(raw_rows, list):
        failed.append(RAW_MISSING)
    else:
        if prov.get("run_id") != run_id or prov.get("slug") != slug:
            failed.append(IDENTITY_MISMATCH)
        if prov.get("declared_count") != len(raw_rows):
            failed.append(TRUNCATED)

    # R3 output present + a list.
    output_count = len(output_rows) if isinstance(output_rows, list) else None
    if output_count is None:
        failed.append(OUTPUT_MISSING)

    # R4 committed-vs-OUTPUT + R5 self-report-vs-committed (workbook only).
    if has_workbook:
        if committed_count is None:
            failed.append(WORKBOOK_ABSENT)
        else:
            if output_count is not None and committed_count != output_count:
                failed.append(WORKBOOK_MISMATCH)
            if scored_count != committed_count:
                failed.append(SCORED_COUNT_MISMATCH)

    high_silent_skip = bool(
        raw_count is not None
        and committed_count is not None
        and silent_skip_exceeds(raw_count, committed_count)
    )
    return {
        "step": step_name,
        "sheet": sheet,
        "independent_ok": not failed,
        "failed_checks": failed,
        "raw_count": raw_count,
        "output_count": output_count,
        "committed_count": committed_count,
        "scored_count": scored_count,
        "high_silent_skip": high_silent_skip,
    }


def reconcile_step(
    *,
    workspace_root: Path | str,
    slug: str,
    run_id: str,
    step_name: str,
    sheet: str,
    coverage_step: dict,
    workbook_path: Path | str | None = None,
    schema_path: Path | str | None = None,
) -> dict:
    """Read this step's artifacts (raw drop, transform output, committed rows) and
    reconcile them via R1-R5. Returns a NEW result dict."""
    raw = _read_json(inbox_path(workspace_root, run_id, slug, step_name))
    output_rows = _output_rows(
        _read_json(output_path(workspace_root, run_id, slug, sheet))
    )
    scored_count = (
        coverage_step.get("scored_count") if isinstance(coverage_step, dict) else None
    )
    has_workbook = workbook_path is not None
    committed_count = None
    if has_workbook:
        committed_count = committed_row_count(
            workbook_path, sheet, data_start_row_for(sheet, schema_path)
        )
    return _reconcile_step_data(
        run_id=run_id, slug=slug, step_name=step_name, sheet=sheet, raw=raw,
        output_rows=output_rows, committed_count=committed_count,
        scored_count=scored_count, has_workbook=has_workbook,
    )


def reconcile_run(
    *,
    workspace_root: Path | str,
    slug: str,
    run_id: str,
    workbook_path: Path | str | None = None,
    schema_path: Path | str | None = None,
    steps: Sequence[dict] = STEPS,
    coverage_record: dict | None = None,
) -> dict:
    """Reconcile every code_verified step of one run; derive the independent verdict.

    Loads the coverage record (coverage_path) if not passed. Reconciles each
    ``steps`` entry whose coverage step is ``verification_class == "code_verified"``.
    The run is:
      - ``workbook_absent`` if no readable workbook was given (reported, NOT scored),
      - else ``reconciled`` if EVERY code_verified step independent_ok, else ``mismatch``.
    ``fake_green`` = self-reported verdict == "pass" AND independent verdict ==
    "mismatch" (success claimed while the committed data disagrees).
    """
    if coverage_record is None:
        coverage_record = _read_json(coverage_path(workspace_root, slug, run_id)) or {}
    self_verdict = coverage_record.get("verdict")
    cov_by_name = {
        s.get("name"): s
        for s in (coverage_record.get("steps") or [])
        if isinstance(s, dict)
    }

    wb_present = workbook_path is not None and _workbook_present(workbook_path)
    effective_wb = workbook_path if wb_present else None

    results: list[dict] = []
    for entry in steps:
        cov_step = cov_by_name.get(entry["name"])
        if not (
            isinstance(cov_step, dict)
            and cov_step.get("verification_class") == "code_verified"
        ):
            continue
        results.append(
            reconcile_step(
                workspace_root=workspace_root, slug=slug, run_id=run_id,
                step_name=entry["name"], sheet=entry["sheet"], coverage_step=cov_step,
                workbook_path=effective_wb, schema_path=schema_path,
            )
        )

    if not wb_present or not results:
        # No readable workbook (or no code_verified step to score) ⇒ not scored.
        independent_verdict = "workbook_absent"
    elif all(r["independent_ok"] for r in results):
        independent_verdict = "reconciled"
    else:
        independent_verdict = "mismatch"

    return {
        "run_id": run_id,
        "slug": slug,
        "independent_verdict": independent_verdict,
        "self_reported_verdict": self_verdict,
        "steps": results,
        "fake_green": self_verdict == "pass" and independent_verdict == "mismatch",
    }


# ---------------------------------------------------------------------------
# Aggregation + project-wide enumeration
# ---------------------------------------------------------------------------

def structured_error_rate(run_reconciliations: Iterable[dict]) -> dict:
    """Aggregate reconcile_run dicts into the headline structured-error metrics.

    ``reconcilable`` EXCLUDES workbook_absent runs (they were never scored).
    ``error_rate`` = mismatched / reconcilable (0.0 when reconcilable == 0).
    ``workbook_absent`` is surfaced as its own count — NEVER silently dropped or
    treated as a pass.
    """
    runs = list(run_reconciliations)
    verdicts = [r.get("independent_verdict") for r in runs]
    reconciled = verdicts.count("reconciled")
    mismatched = verdicts.count("mismatch")
    workbook_absent = verdicts.count("workbook_absent")
    reconcilable = reconciled + mismatched
    return {
        "total": len(runs),
        "reconcilable": reconcilable,
        "reconciled": reconciled,
        "mismatched": mismatched,
        "workbook_absent": workbook_absent,
        "error_rate": (mismatched / reconcilable) if reconcilable else 0.0,
        "fake_green_count": sum(1 for r in runs if r.get("fake_green")),
        "mismatched_run_ids": [
            r.get("run_id") for r in runs
            if r.get("independent_verdict") == "mismatch"
        ],
    }


def oracle_report(
    *,
    workspace_root: Path | str,
    slug: str,
    workbook_path: Path | str | None = None,
    schema_path: Path | str | None = None,
) -> dict:
    """Reconcile EVERY coverage run under ``slug`` and aggregate the metrics.

    Enumerates ``{run_id}.json`` under the slug's coverage dir (the parent of
    ``coverage_path``), reconcile_run each, and returns
    ``{slug, runs:[...], metrics: structured_error_rate(...)}``.
    """
    coverage_dir = coverage_path(workspace_root, slug, "_").parent
    runs: list[dict] = []
    if coverage_dir.is_dir():
        for record_path in sorted(coverage_dir.glob("*.json")):
            runs.append(
                reconcile_run(
                    workspace_root=workspace_root, slug=slug, run_id=record_path.stem,
                    workbook_path=workbook_path, schema_path=schema_path,
                )
            )
    return {"slug": slug, "runs": runs, "metrics": structured_error_rate(runs)}


# ---------------------------------------------------------------------------
# CLI (READ-ONLY report; exit 0 always — it never fails the build)
# ---------------------------------------------------------------------------

def _format_report(report: dict) -> str:
    """Render the compact human report (pure: returns the string)."""
    m = report["metrics"]
    lines = [
        f"AMO oracle — slug={report['slug']} "
        f"(READ-ONLY; independent of coverage.verdict)",
        f"  structured error rate: {m['error_rate'] * 100:.1f}%  "
        f"({m['mismatched']}/{m['reconcilable']} reconcilable runs mismatched)",
        f"  reconciled={m['reconciled']}  mismatched={m['mismatched']}  "
        f"workbook_absent={m['workbook_absent']}  total={m['total']}",
    ]
    if m["fake_green_count"]:
        loud = ", ".join(r["run_id"] for r in report["runs"] if r["fake_green"])
        lines.append(
            f"  *** FAKE-GREEN ({m['fake_green_count']}): {loud} — "
            f"verdict=pass but committed data does NOT reconcile ***"
        )
    else:
        lines.append("  fake-green: none")
    for r in report["runs"]:
        flag = "  [FAKE-GREEN]" if r["fake_green"] else ""
        lines.append(
            f"    {r['run_id']}: {r['independent_verdict']} "
            f"(self={r['self_reported_verdict']}){flag}"
        )
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.reporting.orchestration_metrics",
        description="AMO independent oracle: reconcile the committed master.xlsx "
                    "against raw provenance for every run of a project (READ-ONLY).",
    )
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument(
        "--workbook", default=None,
        help="committed master.xlsx; omit to skip R4/R5 (runs marked "
             "workbook_absent — no silent degradation)",
    )
    parser.add_argument(
        "--schema", default=None,
        help="override path to master-excel.schema.json (data_start_row source)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI boundary: enumerate + reconcile + print the report. Exit 0 always."""
    args = _build_arg_parser().parse_args(argv)
    if args.workbook is None:
        print(
            "note: --workbook not given → R4/R5 skipped, runs marked "
            "workbook_absent (no silent degradation)."
        )
    report = oracle_report(
        workspace_root=args.workspace_root, slug=args.slug,
        workbook_path=args.workbook, schema_path=args.schema,
    )
    print(_format_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
