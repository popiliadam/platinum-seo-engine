#!/usr/bin/env python3
"""portfolio_runner.py — the portfolio sequential-sweep coordinator (AMO batch 4b).

In ONE invocation, iterate the portfolio's projects IN ORDER and run each
project's owed workflow under its OWN per-project run-lock, reserving budget from
the 4a cost ledger BEFORE each project (job-level preflight). The model-dependent
per-project run is DELEGATED via an injectable ``run_project_fn(slug, workflow)``
(mirrors ``committer.commit`` injection in ``run_step``) so ``run_sweep`` is PURE
+ unit-testable with a STUB — no live model, no MCP. ``run_sweep`` is clock-free:
``period`` + ``now_iso`` are passed in (never read from a clock).

Per project, IN ORDER:
  1. try_acquire its lock; held elsewhere → ``skipped`` (never wait) + continue.
  2. PREFLIGHT: reserve each estimated resource against its ceiling. If a reserve
     would exceed the ceiling (``CostCeilingExceeded``): RELEASE the partials
     already made for THIS project (no leak), record it ``paused`` (resumable —
     D4 external-failure verdict), release the lock, and STOP the sweep — the
     remaining projects go ``not_run``. This is the KILL-SWITCH: the global pool
     is exhausted, so we pause rather than silently under-run.
  3. else run_project_fn (guard exceptions → ``failed`` + release reservations +
     continue — a single project's failure is NOT a kill-switch). On success,
     CONFIRM each reservation (actual from the result's ``actual_cost`` if
     present, else the reserved amount) and record it ``ran``.
  4. release the lock (always, in a finally).

Every skip / pause / failure / not-run carries a Turkish one-line operator
message (mirrors ``remediation.render``'s style — spec §8). ``render_summary``
folds the result into one operator block; on a kill-switch it names the exact
resource + the resume hint.

ADDITIVE: imports ``cost_ledger`` (4a) + ``project_lock`` (4b) and reads
``shared/portfolio.json`` (0e2); it never edits the spine, the workflow drivers,
the oracle, or the ledger.

Public API:
    estimate_cost(workspace_root, workflow) -> dict[str, float]
    list_projects(workspace_root) -> list[dict]
    run_sweep(workspace_root, *, workflow, period, now_iso, run_project_fn,
              run_id_prefix="portfolio", ceilings=None) -> dict
    render_summary(result) -> str
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable, NamedTuple

from scripts.state import cost_ledger, project_lock

# Canonical resource order — mirrors cost-ledger.schema.json's resource enum.
# A DETERMINISTIC order matters: it fixes which resource reserves first (so the
# "partial" released on a kill-switch is well-defined).
_RESOURCES: tuple[str, ...] = ("gsc_calls", "dfs_credits", "image_spend")

RunProjectFn = Callable[[str, str], dict]


class PortfolioRunnerError(Exception):
    """Raised for a malformed portfolio.json / cost-estimates.json (fail-closed)."""


class _Reservation(NamedTuple):
    """One open ledger reservation made for a project during preflight."""

    resource: str
    reservation_id: str
    reserved: float


# ---------------------------------------------------------------------------
# config readers (operator-edited; absent → empty, malformed → fail-closed)
# ---------------------------------------------------------------------------

def _read_json_object(path: Path) -> dict | None:
    """Read a JSON object at ``path``; absent → None, malformed/non-object → raise."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioRunnerError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PortfolioRunnerError(f"{path.name} must be a JSON object: {path}")
    return data


def estimate_cost(workspace_root: Path | str, workflow: str) -> dict[str, float]:
    """Per-resource budget estimate for ``workflow`` from shared/cost-estimates.json.

    Shape: ``{ "<workflow>": { "gsc_calls": n, "dfs_credits": n, "image_spend": n } }``.
    Absent file/workflow → ``{}`` (reserve nothing). A missing resource key is
    omitted (= 0 = reserve nothing for it). A present but non-numeric/negative
    value fails closed. Operator-tuned (O5) — no dedicated schema (fact C).
    """
    data = _read_json_object(Path(workspace_root) / "shared" / "cost-estimates.json")
    if data is None:
        return {}
    wf = data.get(workflow)
    if wf is None:
        return {}
    if not isinstance(wf, dict):
        raise PortfolioRunnerError(
            f"cost-estimates.json[{workflow!r}] must be an object"
        )
    out: dict[str, float] = {}
    for resource in _RESOURCES:
        value = wf.get(resource)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise PortfolioRunnerError(
                f"estimate {workflow}/{resource} must be a non-negative number "
                f"(got {value!r})"
            )
        out[resource] = float(value)
    return out


def list_projects(workspace_root: Path | str) -> list[dict]:
    """Read shared/portfolio.json's ``active_projects`` list IN ORDER. Missing → [].

    ``active_projects`` is the canonical key per portfolio-config.schema.json
    (#/required) and every reporting reader (portfolio_overview, _heatmap, …).
    """
    data = _read_json_object(Path(workspace_root) / "shared" / "portfolio.json")
    if data is None:
        return []
    projects = data.get("active_projects")
    if not isinstance(projects, list):
        raise PortfolioRunnerError(
            "portfolio.json must have an 'active_projects' array"
        )
    return list(projects)


# ---------------------------------------------------------------------------
# ceiling resolution + reserve / confirm / release helpers
# ---------------------------------------------------------------------------

def _resolve_ceilings(
    workspace_root: Path | str, ceilings: dict | None
) -> dict[str, float | None]:
    """Per-resource ceiling map. Default: read each via cost_ledger.read_ceiling."""
    if ceilings is not None:
        return {r: ceilings.get(r) for r in _RESOURCES}
    return {r: cost_ledger.read_ceiling(workspace_root, r) for r in _RESOURCES}


def _ceiling_for(ceilings: dict[str, float | None], resource: str) -> float:
    """Resolve a resource's ceiling; an unset ceiling means NO cap (treated ∞),
    matching 4a's "ceiling: unset" semantics (never treat absent as 0)."""
    value = ceilings.get(resource)
    return float("inf") if value is None else float(value)


def _reserve_for_project(
    workspace_root: Path | str,
    *,
    estimate: dict[str, float],
    ceilings: dict[str, float | None],
    period: str,
    run_id: str,
    slug: str,
    now_iso: str,
) -> tuple[list[_Reservation], cost_ledger.CostCeilingExceeded | None]:
    """Reserve every estimated resource (amount > 0) IN ORDER.

    Returns ``(reservations_made, kill_exc_or_None)``. On a ceiling hit the
    exception is RETURNED (not raised) alongside the partial reservations already
    made, so the caller can release them cleanly — no partial state is lost to a
    propagating exception.
    """
    reservations: list[_Reservation] = []
    for resource in _RESOURCES:
        amount = estimate.get(resource, 0.0)
        if amount <= 0:
            continue
        try:
            entry = cost_ledger.reserve(
                workspace_root, resource=resource, period=period, amount=amount,
                ceiling=_ceiling_for(ceilings, resource), run_id=run_id,
                project_id=slug, now_iso=now_iso,
            )
        except cost_ledger.CostCeilingExceeded as exc:
            return reservations, exc
        reservations.append(
            _Reservation(resource, entry["reservation_id"], amount)
        )
    return reservations, None


def _release_all(
    workspace_root: Path | str, reservations: list[_Reservation], *,
    run_id: str, slug: str, now_iso: str,
) -> None:
    """Best-effort release of every open reservation (cleanup path — a single
    release error must not mask the kill-switch / failure being handled)."""
    for res in reservations:
        try:
            cost_ledger.release(
                workspace_root, reservation_id=res.reservation_id,
                run_id=run_id, project_id=slug, now_iso=now_iso,
            )
        except cost_ledger.CostLedgerError:
            pass


def _confirm_amount(actual_cost: dict, resource: str, reserved: float) -> float:
    """Confirm amount for a resource: the result's actual if a valid number in
    [0, reserved], else the reserved estimate (confirm can never exceed reserved)."""
    value = actual_cost.get(resource)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return reserved
    return min(float(value), reserved)


def _confirm_all(
    workspace_root: Path | str, reservations: list[_Reservation], *,
    actual_cost: dict, run_id: str, slug: str, now_iso: str,
) -> None:
    """Confirm every reservation with its actual spend (else the reserved amount)."""
    for res in reservations:
        cost_ledger.confirm(
            workspace_root, reservation_id=res.reservation_id,
            amount=_confirm_amount(actual_cost, res.resource, res.reserved),
            run_id=run_id, project_id=slug, now_iso=now_iso,
        )


def _actual_cost_of(result: object) -> dict:
    """Extract a result's ``actual_cost`` dict (absent / non-dict → {})."""
    if isinstance(result, dict):
        ac = result.get("actual_cost")
        if isinstance(ac, dict):
            return ac
    return {}


# ---------------------------------------------------------------------------
# Turkish operator messages (mirror remediation.render's style — spec §8)
# ---------------------------------------------------------------------------

def _skip_message(slug: str) -> str:
    return (f"⏭️  {slug}: zaten başka bir oturumda çalışıyor — atlandı "
            f"(kilit serbest kalınca tekrar denenebilir).")


def _failure_message(slug: str, exc: Exception) -> str:
    return (f"❌ {slug}: proje çalışması hata verdi ({exc}); bütçe serbest "
            f"bırakıldı, tarama sonraki projeyle devam etti.")


def _pause_message(slug: str, exc: cost_ledger.CostCeilingExceeded) -> str:
    return (f"⏸️  {slug}: bütçe tavanı aşıldı ({exc.resource}: "
            f"{exc.current}+{exc.requested} > {exc.ceiling}). Portföy taraması "
            f"durduruldu; bütçe yenilenince kaldığı yerden devam eder.")


def _not_run_message(slug: str) -> str:
    return (f"⏳ {slug}: portföy taraması bütçe tavanı nedeniyle durdu — "
            f"çalıştırılmadı (bütçe yenilenince taranır).")


# ---------------------------------------------------------------------------
# the sweep coordinator
# ---------------------------------------------------------------------------

def _process_project(
    workspace_root: Path | str,
    *,
    slug: str,
    workflow: str,
    estimate: dict[str, float],
    ceilings: dict[str, float | None],
    period: str,
    now_iso: str,
    run_id_prefix: str,
    run_project_fn: RunProjectFn,
) -> tuple[str, dict]:
    """Run ONE project end-to-end under its lock. Returns ``(category, entry)``;
    category ∈ {"skipped","paused","failed","ran"} ("paused" = KILL-SWITCH → the
    caller STOPS). Lock always released (finally); partials released on the
    kill-switch AND the run-failure path (no leak)."""
    fd = project_lock.try_acquire(workspace_root, slug)
    if fd is None:                                    # busy elsewhere → SKIP
        return "skipped", {"slug": slug, "reason": "already running",
                           "message": _skip_message(slug)}
    run_id = f"{run_id_prefix}-{slug}"
    try:
        reservations, kill_exc = _reserve_for_project(
            workspace_root, estimate=estimate, ceilings=ceilings, period=period,
            run_id=run_id, slug=slug, now_iso=now_iso,
        )
        if kill_exc is not None:                      # KILL-SWITCH
            _release_all(workspace_root, reservations, run_id=run_id, slug=slug,
                         now_iso=now_iso)
            return "paused", {
                "slug": slug, "reason": "budget_ceiling",
                "resource": kill_exc.resource, "ceiling": kill_exc.ceiling,
                "requested": kill_exc.requested, "current": kill_exc.current,
                "message": _pause_message(slug, kill_exc),
            }
        try:
            result = run_project_fn(slug, workflow)
        except Exception as exc:                      # one failure ≠ kill-switch
            _release_all(workspace_root, reservations, run_id=run_id, slug=slug,
                         now_iso=now_iso)
            return "failed", {"slug": slug, "reason": "run_error",
                              "error": str(exc),
                              "message": _failure_message(slug, exc)}
        _confirm_all(workspace_root, reservations,
                     actual_cost=_actual_cost_of(result), run_id=run_id,
                     slug=slug, now_iso=now_iso)
        return "ran", {"slug": slug, "result": result}
    finally:
        project_lock.release(fd)


def run_sweep(
    workspace_root: Path | str,
    *,
    workflow: str,
    period: str,
    now_iso: str,
    run_project_fn: RunProjectFn,
    run_id_prefix: str = "portfolio",
    ceilings: dict | None = None,
) -> dict:
    """Sweep the portfolio's projects IN ORDER under per-project locks + budget.

    PURE except the ledger/lock IO; clock-free (``period`` + ``now_iso`` passed
    in). See the module docstring for the per-project algorithm. Returns the
    sweep result dict (``ran`` / ``skipped`` / ``paused`` / ``failed`` /
    ``not_run`` + ``stopped_by_kill_switch``).
    """
    estimate = estimate_cost(workspace_root, workflow)
    resolved_ceilings = _resolve_ceilings(workspace_root, ceilings)
    buckets: dict[str, list[dict]] = {
        "ran": [], "skipped": [], "paused": [], "failed": [], "not_run": [],
    }
    stopped = False

    for project in list_projects(workspace_root):
        slug = project["slug"]
        if stopped:                                   # kill-switch already fired
            buckets["not_run"].append({"slug": slug, "reason": "kill-switch",
                                       "message": _not_run_message(slug)})
            continue
        category, entry = _process_project(
            workspace_root, slug=slug, workflow=workflow, estimate=estimate,
            ceilings=resolved_ceilings, period=period, now_iso=now_iso,
            run_id_prefix=run_id_prefix, run_project_fn=run_project_fn,
        )
        buckets[category].append(entry)
        if category == "paused":                      # STOP the sweep
            stopped = True

    return {"workflow": workflow, "period": period, **buckets,
            "stopped_by_kill_switch": stopped}


def render_summary(result: dict) -> str:
    """One Turkish operator block summarizing a sweep.

    Counts ran/skipped/paused/failed/not-run; on a kill-switch, names the exact
    resource + the copy-pasteable resume command (mirrors remediation.render —
    the operator always sees one next action).
    """
    workflow = result.get("workflow", "?")
    lines = [
        f"📊 Portföy taraması — workflow: {workflow} ({result.get('period', '?')})",
        f"   ✅ çalıştırıldı: {len(result.get('ran', []))}",
        f"   ⏭️  atlandı (kilitli): {len(result.get('skipped', []))}",
        f"   ⏸️  duraklatıldı (bütçe): {len(result.get('paused', []))}",
        f"   ❌ başarısız: {len(result.get('failed', []))}",
        f"   ⏳ çalıştırılmadı: {len(result.get('not_run', []))}",
    ]
    paused = result.get("paused", [])
    if result.get("stopped_by_kill_switch") and paused:
        p = paused[0]
        lines += [
            "",
            f"⚠️  Bütçe tavanı aşıldı: {p.get('resource')} (kill-switch) — "
            f"duraklatılan proje: {p.get('slug')}.",
            "Bütçe yenilenince kaldığın yerden devam et:",
            f"/pseo-run-portfolio {workflow}",
        ]
    return "\n".join(lines)


__all__: Iterable[str] = (
    "PortfolioRunnerError",
    "estimate_cost",
    "list_projects",
    "run_sweep",
    "render_summary",
)
