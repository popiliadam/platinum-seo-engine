#!/usr/bin/env python3
"""schedule.py — the OPTIONAL recurring-schedule marker + O5 fail-closed arming gate (AMO 4d).

The final Faz-4 autonomy step. Faz-4 lets the operator sweep the whole portfolio
(`/pseo-run-portfolio`, 4b) under a shared budget ceiling (4a). The last step is an
OPTIONAL recurring schedule — but autonomy that can spend money unattended is
dangerous, so the scheduler is **default OFF**, armed only behind a cost gate, and
fires NOTHING itself (the periodic trigger is EXTERNAL — see the 4e runbook). Per
D11 the operator only arms after the one comprehensive live-acceptance run.

The marker lives at the GLOBAL (portfolio-wide) path

    {workspace_root}/shared/schedule.json

beside active.json + portfolio.json + cost_ledger.jsonl — no slug in the path.
DEFAULT OFF = the file is ABSENT (read returns a disarmed view); arming CREATES
it, disarming REWRITES it with armed=false (it is NEVER deleted). It is a MUTABLE
POINTER (armed flips true↔false), NOT an append-only log, so it is written with
the canonical atomic marker writer `session_binding._atomic_write_json`
(tempfile → fsync → os.replace), the SAME one `coverage.write_coverage` uses.
os.replace is CORRECT here — this is a marker, NOT events.jsonl / consent.jsonl /
cost_ledger.jsonl (append-only logs that must NEVER os.replace).

Arming is gated three ways (the whole point of this batch):
  - O5 FAIL-CLOSED — `all_ceilings_set` must be (True, []): EVERY cost pool
    (gsc_calls / dfs_credits / image_spend) has a non-None ceiling. 4b's
    "unset ceiling → ∞ (no cap)" is fine for a human-watched MANUAL sweep but
    UNACCEPTABLE for an armed unattended schedule, so `arm` REFUSES (raises
    `ScheduleArmRefused`, writes NOTHING) if any ceiling is unset. There is no
    override flag — this is the load-bearing safety property.
  - CONSENT — `arm` requires `consent_ack is True` (the operator confirmed THIS
    cadence + cost); else `ScheduleConsentError`. Changing the cadence/workflow
    is a fresh `arm` (a new explicit consent), never a silent re-arm.
  - TRANSPARENCY — the marker records the `projected_daily_cost` the operator saw
    (per-sweep cost × the cadence's sweeps-per-day; per-sweep = the workflow's
    per-run estimate × the ACTUAL on-disk project count).

Pure + clock-free: `now_iso` is PASSED IN (never read from a clock — mirrors
cost_ledger / portfolio_runner); the module reads no clock and no RNG.

ADDITIVE: imports cost_ledger (read_ceiling), portfolio_runner (list_projects /
estimate_cost), and session_binding (_atomic_write_json); reads/writes ONLY
shared/schedule.json. It never edits the spine, the workflow drivers, the ledger,
the gates, or /pseo-run-portfolio, and it fires nothing.

Public API:
    schedule_path(workspace_root) -> Path
    read_schedule(workspace_root) -> dict
    all_ceilings_set(workspace_root) -> tuple[bool, list[str]]
    projected_cost(workspace_root, *, workflow, cadence) -> dict
    arm(workspace_root, *, workflow, cadence, now_iso, consent_ack) -> dict
    disarm(workspace_root, *, now_iso) -> dict
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from scripts.orchestration import portfolio_runner
from scripts.state import cost_ledger
from scripts.state.session_binding import _atomic_write_json
from scripts.validation.validate_schema import build_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = "1.0"

# Module dir: <repo>/scripts/state/schedule.py -> repo = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "schedule.schema.json"

# The three portfolio cost pools, canonical order (mirrors cost-ledger.schema.json
# + portfolio_runner). The O5 gate requires a ceiling for EVERY one of these.
_RESOURCES: tuple[str, ...] = ("gsc_calls", "dfs_credits", "image_spend")

# The per-project workflows a sweep may run (the /pseo-run-portfolio set).
_WORKFLOWS: frozenset[str] = frozenset({"monthly", "audit", "setup", "content"})

# Cadences and how many sweeps each implies per day (for the projected-daily math).
_CADENCE_SWEEPS_PER_DAY: dict[str, float] = {
    "daily": 1.0,
    "weekly": 1.0 / 7.0,
    "monthly": 1.0 / 30.0,
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ScheduleError(Exception):
    """Base class for all schedule-marker errors."""


class ScheduleValidationError(ScheduleError):
    """Raised on an unknown workflow/cadence or a marker that fails schema validation."""


class ScheduleConsentError(ScheduleError):
    """Raised when `arm` is called without explicit consent_ack=True (nothing written)."""


class ScheduleArmRefused(ScheduleError):
    """Raised when arming is refused because a cost ceiling is unset (O5 fail-closed).

    Carries `.missing` = the unset ceiling resource names (canonical order) so the
    recipe can name them in the Turkish refuse message. NOTHING is written when
    this is raised — this is the load-bearing safety property of batch 4d.
    """

    def __init__(self, missing: Iterable[str]) -> None:
        self.missing = list(missing)
        super().__init__(
            "cannot arm an unattended schedule while a cost ceiling is unset "
            f"(O5 fail-closed); unset: {', '.join(self.missing)}. Set them in "
            "shared/cost-ceilings.json before arming."
        )


# ---------------------------------------------------------------------------
# Enum guards
# ---------------------------------------------------------------------------

def _check_workflow(workflow: str) -> None:
    if workflow not in _WORKFLOWS:
        raise ScheduleValidationError(
            f"unknown workflow {workflow!r}; valid: {', '.join(sorted(_WORKFLOWS))}"
        )


def _check_cadence(cadence: str) -> None:
    if cadence not in _CADENCE_SWEEPS_PER_DAY:
        raise ScheduleValidationError(
            f"unknown cadence {cadence!r}; valid: "
            f"{', '.join(sorted(_CADENCE_SWEEPS_PER_DAY))}"
        )


# ---------------------------------------------------------------------------
# Path + validation + read
# ---------------------------------------------------------------------------

def schedule_path(workspace_root: Path | str) -> Path:
    """Build {workspace_root}/shared/schedule.json (mkdir -p shared/).

    GLOBAL — one file for the whole portfolio, no slug in the path (the schedule
    is portfolio-wide). shared/ already holds active.json + portfolio.json +
    cost_ledger.jsonl.
    """
    shared_dir = Path(workspace_root) / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    return shared_dir / "schedule.json"


def _validate(marker: dict) -> None:
    """Draft-07 validation against schemas/schedule.schema.json (raises, writes nothing).

    Mirrors coverage._validate: validation runs BEFORE any write, so an invalid
    marker raises ScheduleValidationError and never touches the file.
    """
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScheduleValidationError(f"cannot load schedule schema: {exc}") from exc
    # build_validator (not a raw Draft7Validator) so armed_at/disarmed_at's
    # format:date-time is ENFORCED with the strict UTC '…Z' checker — a naive or
    # non-UTC stamp is rejected before the marker is written (time-discipline §8.10).
    errors = list(build_validator(schema).iter_errors(marker))
    if errors:
        msgs = "; ".join(e.message for e in errors)
        raise ScheduleValidationError(f"invalid schedule marker: {msgs}")


def read_schedule(workspace_root: Path | str) -> dict:
    """Return the current marker; an ABSENT file is a DISARMED view (default OFF).

    Malformed JSON / a non-object marker fails CLOSED (raises ScheduleError) — a
    corrupt marker is NEVER silently treated as disarmed-and-armable.
    """
    path = schedule_path(workspace_root)
    if not path.exists():
        return {"schema_version": _SCHEMA_VERSION, "armed": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScheduleError(f"cannot read schedule marker {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ScheduleError(f"schedule marker must be a JSON object: {path}")
    return data


# ---------------------------------------------------------------------------
# O5 gate + projected cost
# ---------------------------------------------------------------------------

def all_ceilings_set(workspace_root: Path | str) -> tuple[bool, list[str]]:
    """O5 gate: (True, []) iff every cost pool has a non-None ceiling.

    Else (False, [the unset resource names in canonical order]). Reads each
    ceiling via cost_ledger.read_ceiling (None == UNSET).
    """
    missing = [
        resource
        for resource in _RESOURCES
        if cost_ledger.read_ceiling(workspace_root, resource) is None
    ]
    return (not missing, missing)


def projected_cost(
    workspace_root: Path | str, *, workflow: str, cadence: str
) -> dict:
    """The cost the operator sees BEFORE arming, for (workflow, cadence).

    Returns {"project_count", "per_sweep": {resource: cost}, "per_day": {...}}.
    One sweep runs the workflow on EVERY project, so per-sweep cost for a resource
    = the workflow's per-run estimate × the ACTUAL on-disk project count; the
    projected DAILY cost = per-sweep × the cadence's sweeps-per-day (daily→1,
    weekly→1/7, monthly→1/30). A resource with no estimate is omitted (not zero).
    """
    _check_workflow(workflow)
    _check_cadence(cadence)
    project_count = len(portfolio_runner.list_projects(workspace_root))
    estimate = portfolio_runner.estimate_cost(workspace_root, workflow)
    sweeps_per_day = _CADENCE_SWEEPS_PER_DAY[cadence]
    per_sweep = {res: amount * project_count for res, amount in estimate.items()}
    per_day = {res: cost * sweeps_per_day for res, cost in per_sweep.items()}
    return {"project_count": project_count, "per_sweep": per_sweep, "per_day": per_day}


# ---------------------------------------------------------------------------
# arm (the gate + the write) / disarm
# ---------------------------------------------------------------------------

def arm(
    workspace_root: Path | str,
    *,
    workflow: str,
    cadence: str,
    now_iso: str,
    consent_ack: bool,
) -> dict:
    """Arm the recurring schedule — the O5 gate + the marker write.

    Order: (1) validate workflow + cadence enums (ScheduleValidationError);
    (2) require consent_ack is True (ScheduleConsentError); (3) O5 GATE — refuse
    with ScheduleArmRefused(missing) and write NOTHING if any ceiling is unset
    (fail-closed, the load-bearing safety property); (4) compute the projected
    daily cost; (5) build the armed marker, validate it, atomically write it,
    return it. Clock-free: now_iso is passed in.
    """
    _check_workflow(workflow)
    _check_cadence(cadence)
    if consent_ack is not True:
        raise ScheduleConsentError(
            "arming requires explicit consent_ack=True — the operator must confirm "
            "THIS cadence + projected cost (no silent re-arm, no override flag)."
        )
    ok, missing = all_ceilings_set(workspace_root)
    if not ok:
        raise ScheduleArmRefused(missing)
    projected = projected_cost(
        workspace_root, workflow=workflow, cadence=cadence
    )["per_day"]
    marker = {
        "schema_version": _SCHEMA_VERSION,
        "armed": True,
        "workflow": workflow,
        "cadence": cadence,
        "consent_ack": True,
        "projected_daily_cost": projected,
        "armed_at": now_iso,
    }
    _validate(marker)
    _atomic_write_json(schedule_path(workspace_root), marker)
    return marker


def disarm(workspace_root: Path | str, *, now_iso: str) -> dict:
    """Disarm the schedule by REWRITING the marker armed=false (never deleting it).

    Idempotent — disarming an absent / already-disarmed schedule is fine. The
    minimal disarmed marker carries disarmed_at=now_iso (clock-free). Validates
    before the atomic write; returns the written marker.
    """
    marker = {
        "schema_version": _SCHEMA_VERSION,
        "armed": False,
        "disarmed_at": now_iso,
    }
    _validate(marker)
    _atomic_write_json(schedule_path(workspace_root), marker)
    return marker


__all__: Iterable[str] = (
    "ScheduleError",
    "ScheduleValidationError",
    "ScheduleConsentError",
    "ScheduleArmRefused",
    "schedule_path",
    "read_schedule",
    "all_ceilings_set",
    "projected_cost",
    "arm",
    "disarm",
)
