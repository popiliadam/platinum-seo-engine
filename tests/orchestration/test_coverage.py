"""Unit tests for scripts/orchestration/coverage.py (AMO batch 1b).

The builders emit ONLY declared keys so the frozen coverage.schema.json
(additionalProperties:false at record + step level) validates with ZERO Draft7
errors. write_coverage validates BEFORE an atomic write and writes NOTHING on an
invalid record. derive_verdict maps step statuses to the run-level verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.orchestration import coverage

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_SCHEMA = json.loads(
    (ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8")
)
RUN_ID = "vento-2026-06-05-a1b2"


def _errors(record: dict) -> list:
    return list(Draft7Validator(COVERAGE_SCHEMA).iter_errors(record))


# --- build_step ------------------------------------------------------------

def test_build_step_minimal_only_declared_keys() -> None:
    step = coverage.build_step("fetch_gsc", "code_verified", "satisfied")
    assert step == {
        "name": "fetch_gsc",
        "verification_class": "code_verified",
        "status": "satisfied",
    }


def test_build_step_includes_optionals_when_provided() -> None:
    step = coverage.build_step(
        "fetch_gsc", "code_verified", "satisfied",
        observed_mcp=["mcp__gsc__search_analytics"], input_count=120, scored_count=118,
    )
    assert step["observed_mcp"] == ["mcp__gsc__search_analytics"]
    assert step["input_count"] == 120
    assert step["scored_count"] == 118


def test_build_step_omits_empty_observed_mcp() -> None:
    step = coverage.build_step("x", "code_verified", "satisfied", observed_mcp=[])
    assert "observed_mcp" not in step


def test_build_step_does_not_alias_caller_list() -> None:
    mcp = ["a"]
    step = coverage.build_step("x", "code_verified", "satisfied", observed_mcp=mcp)
    mcp.append("b")  # mutating the caller's list must not leak into the step
    assert step["observed_mcp"] == ["a"]


def test_build_step_unknown_verification_class_raises() -> None:
    with pytest.raises(ValueError):
        coverage.build_step("x", "guessed", "satisfied")


def test_build_step_unknown_status_raises() -> None:
    with pytest.raises(ValueError):
        coverage.build_step("x", "code_verified", "green")


# --- build_record + schema validity ----------------------------------------

def test_build_record_minimal_validates() -> None:
    rec = coverage.build_record(
        run_id=RUN_ID, steps=[], required_satisfied=False, verdict="incomplete",
    )
    assert _errors(rec) == []


def test_build_record_full_validates() -> None:
    steps = [
        coverage.build_step(
            "fetch_gsc", "code_verified", "satisfied",
            observed_mcp=["mcp__gsc__search_analytics"], input_count=120, scored_count=118,
        ),
        coverage.build_step("generate_blog", "model_attested", "running"),
    ]
    rec = coverage.build_record(
        run_id=RUN_ID, steps=steps, required_satisfied=True, verdict="pass",
        project_slug="vento", engine_version="1.9.5",
        created_at="2026-06-05T10:00:00Z", updated_at="2026-06-05T10:05:00Z",
    )
    assert _errors(rec) == []


def test_build_record_omits_optionals_when_absent() -> None:
    rec = coverage.build_record(
        run_id=RUN_ID, steps=[], required_satisfied=False, verdict="incomplete",
    )
    for key in ("project_slug", "engine_version", "created_at", "updated_at"):
        assert key not in rec


# --- coverage_path ---------------------------------------------------------

def test_coverage_path_shape(tmp_path: Path) -> None:
    p = coverage.coverage_path(tmp_path, "vento", RUN_ID)
    assert p == tmp_path / "projects" / "vento" / "_state" / "coverage" / f"{RUN_ID}.json"


# --- write_coverage --------------------------------------------------------

def test_write_coverage_writes_valid_record(tmp_path: Path) -> None:
    rec = coverage.build_record(
        run_id=RUN_ID,
        steps=[coverage.build_step("fetch_gsc", "code_verified", "satisfied", input_count=3, scored_count=3)],
        required_satisfied=True, verdict="pass", project_slug="vento",
    )
    path = coverage.write_coverage(rec, workspace_root=tmp_path, project_slug="vento", run_id=RUN_ID)
    assert path.exists()
    written = json.loads(path.read_text(encoding="utf-8"))
    assert _errors(written) == []
    assert written["run_id"] == RUN_ID


def test_write_coverage_rejects_invalid_and_writes_nothing(tmp_path: Path) -> None:
    bad = {"run_id": "not-a-run-id", "steps": [], "required_satisfied": True, "verdict": "pass"}
    with pytest.raises(coverage.CoverageValidationError):
        coverage.write_coverage(bad, workspace_root=tmp_path, project_slug="vento", run_id=RUN_ID)
    assert not coverage.coverage_path(tmp_path, "vento", RUN_ID).exists()


# --- derive_verdict --------------------------------------------------------

def test_derive_verdict_all_satisfied_pass() -> None:
    steps = [coverage.build_step("a", "code_verified", "satisfied")]
    assert coverage.derive_verdict(steps) == (True, "pass")


def test_derive_verdict_missing_required_incomplete() -> None:
    steps = [
        coverage.build_step("a", "code_verified", "satisfied"),
        coverage.build_step("b", "code_verified", "missing"),
    ]
    assert coverage.derive_verdict(steps) == (False, "incomplete")


def test_derive_verdict_failed_step() -> None:
    steps = [
        coverage.build_step("a", "code_verified", "satisfied"),
        coverage.build_step("b", "code_verified", "failed"),
    ]
    assert coverage.derive_verdict(steps) == (False, "failed")


def test_derive_verdict_ignores_model_attested_for_required() -> None:
    # a model_attested step that is merely 'running' must not block required_satisfied.
    steps = [
        coverage.build_step("a", "code_verified", "satisfied"),
        coverage.build_step("blog", "model_attested", "running"),
    ]
    assert coverage.derive_verdict(steps) == (True, "pass")


# --- #19 — created_at/updated_at are strict UTC '…Z' -----------------------

def test_write_coverage_rejects_naive_created_at(tmp_path: Path) -> None:
    """created_at/updated_at carry format:date-time in coverage.schema.json.
    Routing _validate through the strict build_validator (finding #19) makes
    write_coverage reject a naive (tz-less) stamp and write NOTHING — the UTC '…Z'
    discipline is ENFORCED on the coverage marker, not merely annotated."""
    record = coverage.build_record(
        run_id=RUN_ID,
        steps=[coverage.build_step("fetch_gsc", "code_verified", "satisfied")],
        required_satisfied=True,
        verdict="pass",
        created_at="2026-06-05T12:00:00",  # naive — no 'Z'
    )
    with pytest.raises(coverage.CoverageValidationError):
        coverage.write_coverage(record, workspace_root=tmp_path,
                                project_slug="vento", run_id=RUN_ID)
    assert not coverage.coverage_path(tmp_path, "vento", RUN_ID).exists()  # nothing written
