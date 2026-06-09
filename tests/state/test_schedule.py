"""tests/state/test_schedule.py — AMO batch 4d scheduler marker + O5 arming gate.

TDD lock for scripts/state/schedule.py + schemas/schedule.schema.json: the
OPTIONAL recurring-schedule primitive Faz-4 arms ONLY behind a cost gate. The
load-bearing safety property is FAIL-CLOSED arming (O5): arm() REFUSES to arm an
unattended schedule while ANY of the three cost ceilings (gsc_calls / dfs_credits
/ image_spend) is unset, and writes NOTHING when it refuses. Arming also requires
explicit per-cadence consent (consent_ack=True) and shows the projected daily
cost it was armed at. The marker is a MUTABLE pointer (armed flips true↔false)
written via the canonical atomic writer; the module is pure + clock-free (now_iso
is passed in, never read from a clock — mirrors cost_ledger / portfolio_runner).

Default OFF: an absent shared/schedule.json reads as a disarmed view and arms /
fires NOTHING. This module fires nothing — the periodic trigger is external
(documented in the 4e runbook); per D11 the operator only arms after the one
comprehensive live-acceptance run.

Authority: spec §7 Phase 4 + §8; 4a cost_ledger.read_ceiling (O5 gate source),
  4b portfolio_runner.list_projects / estimate_cost (projected-cost math),
  session_binding._atomic_write_json (the marker writer). Every filesystem test
  uses tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.state import schedule

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "schedule.schema.json"
MODULE_PATH = REPO_ROOT / "scripts" / "state" / "schedule.py"

_NOW = "2026-06-08T12:00:00Z"  # canonical UTC '…Z' (strict date-time checker rejects +00:00)
_LATER = "2026-06-09T00:00:00Z"

# A workspace fixture set where the gate would PASS: all three ceilings set, a
# 3-project portfolio, and a per-run estimate for the `monthly` workflow.
_CEILINGS = {"gsc_calls": 1000, "dfs_credits": 500, "image_spend": 50}
_ESTIMATE = {"monthly": {"gsc_calls": 10, "dfs_credits": 5, "image_spend": 2}}
_PORTFOLIO = {"active_projects": [{"slug": "alpha"}, {"slug": "beta"}, {"slug": "gamma"}]}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _shared(ws: Path) -> Path:
    d = ws / "shared"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(ws: Path, name: str, obj: dict) -> None:
    (_shared(ws) / name).write_text(json.dumps(obj), encoding="utf-8")


def _fully_armable(ws: Path) -> None:
    """A workspace where arming SUCCEEDS: all ceilings set + portfolio + estimates."""
    _write(ws, "cost-ceilings.json", _CEILINGS)
    _write(ws, "portfolio.json", _PORTFOLIO)
    _write(ws, "cost-estimates.json", _ESTIMATE)


def _marker_file(ws: Path) -> Path:
    return ws / "shared" / "schedule.json"


def _schema_errors(instance: dict) -> list:
    """Draft-07 validation errors of an instance against the real schedule schema."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return list(Draft7Validator(schema).iter_errors(instance))


# ---------------------------------------------------------------------------
# default OFF
# ---------------------------------------------------------------------------

def test_read_schedule_absent_file_is_disarmed_and_creates_no_marker(tmp_path: Path) -> None:
    """A fresh ws reads DISARMED (default OFF) without creating the marker file."""
    view = schedule.read_schedule(tmp_path)
    assert view == {"schema_version": "1.0", "armed": False}
    assert not _marker_file(tmp_path).exists()


def test_read_schedule_malformed_json_raises(tmp_path: Path) -> None:
    """A corrupt marker fails CLOSED — never silently treated as disarmed/armable."""
    _shared(tmp_path)
    _marker_file(tmp_path).write_text("{ not json", encoding="utf-8")
    with pytest.raises(schedule.ScheduleError):
        schedule.read_schedule(tmp_path)


# ---------------------------------------------------------------------------
# O5 gate — all_ceilings_set
# ---------------------------------------------------------------------------

def test_all_ceilings_set_all_present(tmp_path: Path) -> None:
    _write(tmp_path, "cost-ceilings.json", _CEILINGS)
    assert schedule.all_ceilings_set(tmp_path) == (True, [])


def test_all_ceilings_set_one_missing(tmp_path: Path) -> None:
    _write(tmp_path, "cost-ceilings.json", {"gsc_calls": 1000, "image_spend": 50})
    assert schedule.all_ceilings_set(tmp_path) == (False, ["dfs_credits"])


def test_all_ceilings_set_none_present(tmp_path: Path) -> None:
    assert schedule.all_ceilings_set(tmp_path) == (
        False, ["gsc_calls", "dfs_credits", "image_spend"]
    )


# ---------------------------------------------------------------------------
# projected_cost — the math the operator sees BEFORE arming
# ---------------------------------------------------------------------------

def test_projected_cost_daily_is_estimate_times_project_count(tmp_path: Path) -> None:
    _write(tmp_path, "portfolio.json", _PORTFOLIO)        # 3 projects
    _write(tmp_path, "cost-estimates.json", _ESTIMATE)    # gsc 10 / dfs 5 / image 2
    result = schedule.projected_cost(tmp_path, workflow="monthly", cadence="daily")
    assert result["project_count"] == 3
    assert result["per_sweep"] == {"gsc_calls": 30.0, "dfs_credits": 15.0, "image_spend": 6.0}
    # daily → ×1.0
    assert result["per_day"] == {"gsc_calls": 30.0, "dfs_credits": 15.0, "image_spend": 6.0}


def test_projected_cost_weekly_and_monthly_fractions(tmp_path: Path) -> None:
    _write(tmp_path, "portfolio.json", _PORTFOLIO)
    _write(tmp_path, "cost-estimates.json", _ESTIMATE)
    weekly = schedule.projected_cost(tmp_path, workflow="monthly", cadence="weekly")
    assert weekly["per_day"]["gsc_calls"] == pytest.approx(30.0 / 7.0)
    assert weekly["per_day"]["dfs_credits"] == pytest.approx(15.0 / 7.0)
    monthly = schedule.projected_cost(tmp_path, workflow="monthly", cadence="monthly")
    assert monthly["per_day"]["gsc_calls"] == pytest.approx(30.0 / 30.0)
    assert monthly["per_day"]["image_spend"] == pytest.approx(6.0 / 30.0)


def test_projected_cost_rejects_bad_cadence(tmp_path: Path) -> None:
    _write(tmp_path, "portfolio.json", _PORTFOLIO)
    _write(tmp_path, "cost-estimates.json", _ESTIMATE)
    with pytest.raises(schedule.ScheduleValidationError):
        schedule.projected_cost(tmp_path, workflow="monthly", cadence="hourly")


def test_projected_cost_rejects_bad_workflow(tmp_path: Path) -> None:
    _write(tmp_path, "portfolio.json", _PORTFOLIO)
    _write(tmp_path, "cost-estimates.json", _ESTIMATE)
    with pytest.raises(schedule.ScheduleValidationError):
        schedule.projected_cost(tmp_path, workflow="bogus", cadence="daily")


# ---------------------------------------------------------------------------
# arm — THE TEETH: fail-closed on any unset ceiling (O5)
# ---------------------------------------------------------------------------

def test_arm_refused_when_a_ceiling_is_unset_writes_nothing(tmp_path: Path) -> None:
    """O5 fail-closed: an unset ceiling REFUSES arming AND writes nothing.

    Portfolio + estimates present and consent given — the ONLY blocker is the
    missing dfs_credits ceiling. arm() must raise ScheduleArmRefused(.missing)
    and leave the workspace DISARMED with no marker on disk.
    """
    _write(tmp_path, "portfolio.json", _PORTFOLIO)
    _write(tmp_path, "cost-estimates.json", _ESTIMATE)
    _write(tmp_path, "cost-ceilings.json", {"gsc_calls": 1000, "image_spend": 50})

    with pytest.raises(schedule.ScheduleArmRefused) as excinfo:
        schedule.arm(tmp_path, workflow="monthly", cadence="daily",
                     now_iso=_NOW, consent_ack=True)

    assert excinfo.value.missing == ["dfs_credits"]
    # FAIL-CLOSED — nothing written: the marker file does not exist...
    assert not _marker_file(tmp_path).exists()
    # ...and a fresh read still reports DISARMED (default OFF).
    assert schedule.read_schedule(tmp_path)["armed"] is False


def test_arm_refused_when_no_ceilings_at_all_writes_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "portfolio.json", _PORTFOLIO)
    _write(tmp_path, "cost-estimates.json", _ESTIMATE)  # NO cost-ceilings.json
    with pytest.raises(schedule.ScheduleArmRefused) as excinfo:
        schedule.arm(tmp_path, workflow="monthly", cadence="daily",
                     now_iso=_NOW, consent_ack=True)
    assert excinfo.value.missing == ["gsc_calls", "dfs_credits", "image_spend"]
    assert not _marker_file(tmp_path).exists()


# ---------------------------------------------------------------------------
# arm — consent gate
# ---------------------------------------------------------------------------

def test_arm_refused_without_consent_ack_writes_nothing(tmp_path: Path) -> None:
    """consent_ack must be exactly True; the gate would otherwise PASS here."""
    _fully_armable(tmp_path)
    with pytest.raises(schedule.ScheduleConsentError):
        schedule.arm(tmp_path, workflow="monthly", cadence="daily",
                     now_iso=_NOW, consent_ack=False)
    assert not _marker_file(tmp_path).exists()
    assert schedule.read_schedule(tmp_path)["armed"] is False


def test_arm_rejects_unknown_workflow_writes_nothing(tmp_path: Path) -> None:
    _fully_armable(tmp_path)
    with pytest.raises(schedule.ScheduleValidationError):
        schedule.arm(tmp_path, workflow="bogus", cadence="daily",
                     now_iso=_NOW, consent_ack=True)
    assert not _marker_file(tmp_path).exists()


def test_arm_rejects_non_utc_armed_at_writes_nothing(tmp_path: Path) -> None:
    """armed_at's format:date-time is enforced via the strict build_validator
    (finding #19): a naive (tz-less) now_iso and an explicit non-UTC/zero offset
    are rejected, and the marker is NEVER written (fail-closed, like every other
    arm refusal)."""
    _fully_armable(tmp_path)
    for bad in ("2026-06-08T12:00:00", "2026-06-08T12:00:00+03:00", "2026-06-08T12:00:00+00:00"):
        with pytest.raises(schedule.ScheduleValidationError):
            schedule.arm(tmp_path, workflow="monthly", cadence="daily",
                         now_iso=bad, consent_ack=True)
        assert not _marker_file(tmp_path).exists()


# ---------------------------------------------------------------------------
# arm — success
# ---------------------------------------------------------------------------

def test_arm_success_writes_armed_marker_that_round_trips(tmp_path: Path) -> None:
    _fully_armable(tmp_path)
    marker = schedule.arm(tmp_path, workflow="monthly", cadence="daily",
                          now_iso=_NOW, consent_ack=True)
    assert marker["armed"] is True
    assert marker["workflow"] == "monthly"
    assert marker["cadence"] == "daily"
    assert marker["consent_ack"] is True
    assert marker["armed_at"] == _NOW
    assert marker["projected_daily_cost"] == {
        "gsc_calls": 30.0, "dfs_credits": 15.0, "image_spend": 6.0,
    }
    # round-trips through disk and validates against the real schema
    assert schedule.read_schedule(tmp_path) == marker
    assert _schema_errors(marker) == []


# ---------------------------------------------------------------------------
# disarm — rewrite (not delete), idempotent
# ---------------------------------------------------------------------------

def test_disarm_after_arm_rewrites_marker_disarmed(tmp_path: Path) -> None:
    _fully_armable(tmp_path)
    schedule.arm(tmp_path, workflow="monthly", cadence="daily",
                 now_iso=_NOW, consent_ack=True)
    marker = schedule.disarm(tmp_path, now_iso=_LATER)
    assert marker["armed"] is False
    assert marker["disarmed_at"] == _LATER
    assert "workflow" not in marker  # the armed fields are gone
    # the file is REWRITTEN, not deleted
    assert _marker_file(tmp_path).exists()
    assert schedule.read_schedule(tmp_path)["armed"] is False
    assert _schema_errors(marker) == []


def test_disarm_is_idempotent_on_absent_schedule(tmp_path: Path) -> None:
    first = schedule.disarm(tmp_path, now_iso=_LATER)
    assert first["armed"] is False
    again = schedule.disarm(tmp_path, now_iso="2026-06-10T00:00:00Z")
    assert again["armed"] is False
    assert schedule.read_schedule(tmp_path)["armed"] is False


# ---------------------------------------------------------------------------
# schema TEETH — the if/then armed-requirements
# ---------------------------------------------------------------------------

def test_schema_accepts_well_formed_armed_record() -> None:
    armed = {
        "schema_version": "1.0", "armed": True, "workflow": "monthly",
        "cadence": "daily", "consent_ack": True,
        "projected_daily_cost": {"gsc_calls": 30.0},
        "armed_at": _NOW,
    }
    assert _schema_errors(armed) == []


def test_schema_accepts_minimal_disarmed_record() -> None:
    assert _schema_errors({"schema_version": "1.0", "armed": False}) == []


def test_schema_rejects_armed_record_missing_consent_ack() -> None:
    armed = {
        "schema_version": "1.0", "armed": True, "workflow": "monthly",
        "cadence": "daily",
        "projected_daily_cost": {"gsc_calls": 30.0},
        "armed_at": _NOW,
    }
    assert _schema_errors(armed)  # if/then requires consent_ack when armed


def test_schema_rejects_armed_record_missing_projected_daily_cost() -> None:
    armed = {
        "schema_version": "1.0", "armed": True, "workflow": "monthly",
        "cadence": "daily", "consent_ack": True, "armed_at": _NOW,
    }
    assert _schema_errors(armed)


def test_schema_rejects_armed_record_missing_workflow() -> None:
    armed = {
        "schema_version": "1.0", "armed": True, "cadence": "daily",
        "consent_ack": True, "projected_daily_cost": {"gsc_calls": 30.0},
        "armed_at": _NOW,
    }
    assert _schema_errors(armed)


def test_schema_rejects_consent_ack_false_on_armed_record() -> None:
    armed = {
        "schema_version": "1.0", "armed": True, "workflow": "monthly",
        "cadence": "daily", "consent_ack": False,
        "projected_daily_cost": {"gsc_calls": 30.0},
        "armed_at": _NOW,
    }
    assert _schema_errors(armed)  # consent_ack is const true


def test_schema_rejects_unknown_top_level_property() -> None:
    rec = {"schema_version": "1.0", "armed": False, "surprise": 1}
    assert _schema_errors(rec)  # additionalProperties:false


# ---------------------------------------------------------------------------
# clock-free + exception hierarchy
# ---------------------------------------------------------------------------

def test_module_is_clock_free() -> None:
    """arm/disarm take now_iso; the module reads no clock and no RNG."""
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "datetime.now" not in src
    assert "time.time" not in src
    assert "random" not in src
    assert "now_iso" in src


def test_exception_hierarchy() -> None:
    assert issubclass(schedule.ScheduleValidationError, schedule.ScheduleError)
    assert issubclass(schedule.ScheduleConsentError, schedule.ScheduleError)
    assert issubclass(schedule.ScheduleArmRefused, schedule.ScheduleError)
