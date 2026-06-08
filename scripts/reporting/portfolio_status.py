#!/usr/bin/env python3
"""portfolio_status.py — the READ-ONLY portfolio triage reporter (AMO batch 4c).

The portfolio-wide companion to the per-project ``/pseo-status``. Faz-4 fans the
orchestrator across the portfolio (4b sweep) under a shared budget ceiling (4a
ledger); the operator (a non-coder) then needs ONE glance to triage the whole
portfolio: which projects are healthy, which are OWED an unfinished step, which
FAILED internally (a gate rejection — fix + re-run now), and which are PAUSED on
an EXTERNAL dependency (budget exhausted / a GSC-DFS outage — resumes when the
dependency recovers) — plus how much of today's GLOBAL budget is spent.

The external-vs-internal axis IS the coverage ``verdict`` (the frozen
coverage.schema.json verdict descriptions encode it), so no workflow-run record is
read. The verdict map:
    pass        -> healthy · cause "—"        (all required steps satisfied)
    incomplete  -> owed     · cause internal  (a required step missing -> re-run)
    failed      -> failed   · cause internal  (an internal gate rejection)
    paused      -> paused   · cause external  (an external dependency failed)
    (no record) -> none     · cause "—"       (never run yet)

The budget is ONE global summary per resource (gsc_calls / dfs_credits /
image_spend): usage is portfolio-wide per (resource, period), so it is NOT
per-project.

DISCIPLINE — this module is strictly READ-ONLY. It imports ``portfolio_runner``
(enumeration), ``coverage`` (path convention), and ``cost_ledger`` (usage/ceiling)
and reads JSON files. It opens NO file for writing, mutates no ledger, and writes
no coverage/events/state — mirroring the orchestration_metrics oracle's contract.
It is also pure/clock-free: ``period`` (the ledger partition key) is PASSED IN.

Robust: a single malformed coverage file or a tampered ledger chain is surfaced
(skipped / error-marked) — it never crashes the whole triage, so one bad project
can never blank the portfolio view.

Public API:
    latest_coverage(workspace_root, slug) -> dict | None
    classify(record) -> dict
    build_triage(workspace_root, *, period) -> dict
    render_triage(triage) -> str
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from scripts.orchestration import coverage, portfolio_runner
from scripts.state import cost_ledger

# The three portfolio cost pools, in canonical order (mirrors cost_ledger /
# portfolio_runner — a deterministic order fixes the budget block's row order).
_RESOURCES: tuple[str, ...] = ("gsc_calls", "dfs_credits", "image_spend")

# verdict -> (category, cause). The external/internal axis IS the verdict (fact C).
_VERDICT_MAP: dict[str, tuple[str, str]] = {
    "pass": ("healthy", "—"),
    "incomplete": ("owed", "internal"),
    "failed": ("failed", "internal"),
    "paused": ("paused", "external"),
}

# Step statuses that explain a non-pass verdict (surfaced as missing_steps).
_MISSING_STATUSES = frozenset({"missing", "failed"})


# ---------------------------------------------------------------------------
# Coverage reading (thin IO; an unreadable file degrades to None, never raises)
# ---------------------------------------------------------------------------

def _read_record(path: Path) -> dict | None:
    """Parse one coverage JSON file; return the dict, or None if missing/corrupt.

    A non-object payload is also None (a coverage record is always an object).
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _record_sort_key(path: Path, record: dict) -> tuple[int, str]:
    """Sort key for a coverage file: (file mtime_ns, run_id).

    mtime_ns is the primary key (the most recently written run wins); run_id is the
    deterministic tie-break (falls back to the file stem if the record omits one,
    so the key is always a clean (int, str) — never compares str against None).
    """
    return (path.stat().st_mtime_ns, str(record.get("run_id") or path.stem))


def latest_coverage(workspace_root: Path | str, slug: str) -> dict | None:
    """Return the LATEST coverage record for ``slug`` by (file mtime_ns, run_id).

    Globs ``projects/{slug}/_state/coverage/*.json`` (the dir is reused from
    ``coverage.coverage_path(..).parent`` so the convention can never drift), parses
    each, and returns the record with the greatest sort key. A file that fails to
    parse is SKIPPED (robust). Missing dir / no files / all-corrupt -> None.
    """
    coverage_dir = coverage.coverage_path(workspace_root, slug, "_").parent
    if not coverage_dir.is_dir():
        return None
    best: tuple[tuple[int, str], dict] | None = None
    for record_path in coverage_dir.glob("*.json"):
        record = _read_record(record_path)
        if record is None:
            continue
        key = _record_sort_key(record_path, record)
        if best is None or key > best[0]:
            best = (key, record)
    return best[1] if best is not None else None


# ---------------------------------------------------------------------------
# Classification (pure)
# ---------------------------------------------------------------------------

def _missing_steps(record: dict) -> list[str]:
    """Names of steps whose status is 'missing' or 'failed' (in record order)."""
    steps = record.get("steps") or []
    return [
        step.get("name")
        for step in steps
        if isinstance(step, dict) and step.get("status") in _MISSING_STATUSES
    ]


def classify(record: dict) -> dict:
    """Map a coverage record to its triage row fields.

    Returns a NEW dict ``{run_id, verdict, missing_steps, cause, category}`` using
    the verdict map. ``missing_steps`` is computed for EVERY record (empty for a
    healthy one). Defensive: an unexpected verdict -> ``category`` = the verdict
    string, ``cause`` = "—" (never raises).
    """
    verdict = record.get("verdict")
    category, cause = _VERDICT_MAP.get(verdict, (verdict, "—"))
    return {
        "run_id": record.get("run_id"),
        "verdict": verdict,
        "missing_steps": _missing_steps(record),
        "cause": cause,
        "category": category,
    }


# ---------------------------------------------------------------------------
# Budget (READ-ONLY ledger summary, GLOBAL per resource)
# ---------------------------------------------------------------------------

def _budget_for(workspace_root: Path | str, resource: str, period: str) -> dict:
    """One budget row for (resource, period): used / ceiling / remaining / error.

    ``used`` via ``cost_ledger.usage`` — a broken/tampered chain raises
    ``CostLedgerError``, which is CAUGHT and surfaced as ``used=None`` + ``error``
    (fail-closed, never crashing the triage). ``ceiling`` via ``read_ceiling`` (None
    = unset = no cap; a malformed ceilings file is likewise surfaced, not raised).
    ``remaining`` = ceiling - used ONLY when both are real numbers. NEW dict; no
    mutation.
    """
    error: str | None = None
    try:
        used: float | None = cost_ledger.usage(
            workspace_root, resource=resource, period=period
        )
    except cost_ledger.CostLedgerError as exc:
        used, error = None, str(exc)
    try:
        ceiling: float | None = cost_ledger.read_ceiling(workspace_root, resource)
    except cost_ledger.CostLedgerError as exc:
        ceiling = None
        error = error or str(exc)
    remaining: float | None = None
    if isinstance(used, (int, float)) and isinstance(ceiling, (int, float)):
        remaining = ceiling - used
    return {
        "resource": resource,
        "used": used,
        "ceiling": ceiling,
        "remaining": remaining,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Triage builder
# ---------------------------------------------------------------------------

def _row_for_project(workspace_root: Path | str, slug: str) -> dict:
    """One triage row for a project: its classified latest record, or a 'none' row
    when it has no coverage record yet."""
    record = latest_coverage(workspace_root, slug)
    if record is None:
        return {
            "slug": slug, "run_id": None, "verdict": None,
            "missing_steps": [], "cause": "—", "category": "none",
        }
    return {"slug": slug, **classify(record)}


def build_triage(workspace_root: Path | str, *, period: str) -> dict:
    """Build the READ-ONLY portfolio triage for ``period`` (passed in; no clock).

    ``rows``: one per project from ``portfolio_runner.list_projects`` IN ORDER (a
    project with no coverage -> category 'none'). ``budget``: one global row per
    resource. Returns ``{period, rows, budget}`` (all NEW structures).
    """
    rows = [
        _row_for_project(workspace_root, project["slug"])
        for project in portfolio_runner.list_projects(workspace_root)
    ]
    budget = [_budget_for(workspace_root, resource, period) for resource in _RESOURCES]
    return {"period": period, "rows": rows, "budget": budget}


# ---------------------------------------------------------------------------
# Render — ONE deterministic Turkish operator block (mirrors render_summary style)
# ---------------------------------------------------------------------------

_DURUM: dict[str, str] = {
    "healthy": "✅ sağlıklı",
    "owed": "📋 eksik",
    "failed": "❌ başarısız",
    "paused": "⏸️ duraklatıldı",
    "none": "➖ kayıt yok",
}
_NEDEN: dict[str, str] = {"—": "—", "internal": "iç", "external": "dış"}

# Generic next-action hints — workflow-AGNOSTIC (coverage records carry no workflow
# name), so the hint uses a ``<workflow>`` placeholder and never invents one.
_HINTS: dict[str, str] = {
    "owed": "eksik adım(lar) var → `/pseo-run <workflow> {slug}` ile tamamla",
    "failed": "iç geçit reddetti → düzelt + `/pseo-run <workflow> {slug}` ile yeniden çalıştır",
    "paused": "dış bağımlılık/bütçe bekliyor → yenilenince kaldığı yerden devam eder",
    "none": "henüz çalıştırılmadı → `/pseo-run <workflow> {slug}` ile başlat",
}


def _fmt_num(value: float) -> str:
    """Render a numeric budget value; an integer-valued float drops its '.0'."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _durum_label(row: dict) -> str:
    """Turkish status label for a row's category (defensive for an unknown one)."""
    category = row.get("category")
    return _DURUM.get(category, f"❔ {category}")


def _row_line(row: dict) -> str:
    """One pipe-delimited project triage line (slug · run_id · durum · eksik · neden)."""
    run_id = row.get("run_id") or "—"
    missing = ", ".join(row.get("missing_steps") or []) or "—"
    neden = _NEDEN.get(row.get("cause"), row.get("cause") or "—")
    return f"| {row.get('slug')} | {run_id} | {_durum_label(row)} | {missing} | {neden} |"


def _next_action(row: dict) -> str | None:
    """Generic Turkish next-action line for a non-healthy row, else None."""
    template = _HINTS.get(row.get("category"))
    if template is None:
        return None
    slug = row.get("slug")
    return f"- {slug}: " + template.format(slug=slug)


def _budget_line(budget_row: dict) -> str:
    """One pipe-delimited budget line; an unset ceiling -> 'sınırsız', a usage error
    -> 'HATA' + the error message."""
    if budget_row.get("error") and budget_row.get("used") is None:
        return f"| {budget_row['resource']} | HATA | — | {budget_row['error']} |"
    used = _fmt_num(budget_row["used"]) if budget_row.get("used") is not None else "—"
    ceiling = (
        _fmt_num(budget_row["ceiling"])
        if budget_row.get("ceiling") is not None
        else "sınırsız"
    )
    remaining = (
        _fmt_num(budget_row["remaining"])
        if budget_row.get("remaining") is not None
        else "—"
    )
    return f"| {budget_row['resource']} | {used} | {ceiling} | {remaining} |"


def _render_rows(rows: list) -> list[str]:
    """The project-triage table + the next-action list (deterministic, in order)."""
    lines = [
        "Proje durumları:",
        "| proje | run_id | durum | eksik adımlar | neden |",
        "|---|---|---|---|---|",
        *[_row_line(row) for row in rows],
    ]
    actions = [action for action in (_next_action(row) for row in rows) if action]
    if actions:
        lines += ["", "Yapılacaklar:", *actions]
    return lines


def render_triage(triage: dict) -> str:
    """Render the triage as ONE deterministic Turkish operator block.

    A period header, the per-project triage table (+ a generic next-action line for
    every non-healthy row), then the global budget table. Stable ordering and no
    clock, so calling twice yields an identical string.
    """
    period = triage.get("period")
    rows = triage.get("rows") or []
    budget = triage.get("budget") or []
    lines = [f"📊 Portföy Durum Triyajı — dönem: {period}", ""]
    if rows:
        lines += _render_rows(rows)
    else:
        lines.append("Portföyde proje yok — `/pseo-init` ile bir proje başlat.")
    lines += [
        "",
        f"Bütçe (global, dönem: {period}):",
        "| kaynak | kullanım | tavan | kalan |",
        "|---|---|---|---|",
        *[_budget_line(budget_row) for budget_row in budget],
    ]
    return "\n".join(lines)


__all__: Iterable[str] = (
    "latest_coverage",
    "classify",
    "build_triage",
    "render_triage",
)
