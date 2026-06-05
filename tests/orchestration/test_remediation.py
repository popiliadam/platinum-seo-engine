"""TDD for the operator-remediation surface (AMO batch 1d).

``remediation(coverage_record, *, slug, workflow="monthly")`` returns None on a
``pass`` verdict, else a structured dict naming the unsatisfied steps + the
copy-pasteable Turkish one-line fix command. ``render()`` turns that dict into a
compact, operator-visible block that always ENDS with the fix command — so a
non-coder in the Mac app always has exactly ONE next action.

Pure functions over a coverage record: no IO, no clock, no workspace.
"""
from __future__ import annotations

from scripts.orchestration import coverage
from scripts.orchestration.remediation import remediation, render

RUN_ID = "vento-2026-06-05-a1b2"


def _record(verdict: str, steps: list[tuple[str, str, str]]) -> dict:
    """Build a coverage record from (name, verification_class, status) triples."""
    built = [coverage.build_step(n, vc, st) for (n, vc, st) in steps]
    required_satisfied = all(
        s["status"] == "satisfied"
        for s in built
        if s["verification_class"] == "code_verified"
    )
    return coverage.build_record(
        run_id=RUN_ID,
        steps=built,
        required_satisfied=required_satisfied,
        verdict=verdict,
        project_slug="vento",
    )


def test_pass_verdict_yields_no_remediation() -> None:
    record = _record("pass", [("gsc_pull", "code_verified", "satisfied")])
    assert remediation(record, slug="vento") is None


def test_incomplete_names_missing_step_and_resume_command() -> None:
    record = _record(
        "incomplete",
        [
            ("gsc_pull", "code_verified", "satisfied"),
            ("quick_wins", "code_verified", "missing"),
            ("content_decay", "code_verified", "satisfied"),
        ],
    )
    rem = remediation(record, slug="vento")
    assert rem is not None
    assert rem["verdict"] == "incomplete"
    assert "quick_wins" in rem["missing"]
    assert "gsc_pull" not in rem["missing"]  # satisfied steps are excluded
    assert rem["one_line_fix_command"] == "/pseo-run monthly vento --resume"
    assert "quick_wins" in rem["why_turkish"]  # the Turkish 'why' names it


def test_paused_mentions_external_dependency_and_resume() -> None:
    record = _record("paused", [("gsc_pull", "code_verified", "missing")])
    rem = remediation(record, slug="vento")
    assert rem is not None
    assert rem["verdict"] == "paused"
    low = rem["why_turkish"].lower()
    assert "harici" in low or "dış" in low  # external dependency (TR)
    assert "--resume" in rem["why_turkish"]


def test_failed_names_failed_step() -> None:
    record = _record(
        "failed",
        [
            ("gsc_pull", "code_verified", "failed"),
            ("quick_wins", "code_verified", "satisfied"),
        ],
    )
    rem = remediation(record, slug="vento")
    assert rem is not None
    assert rem["verdict"] == "failed"
    assert "gsc_pull" in rem["missing"]


def test_render_contains_fix_command_and_is_nonempty() -> None:
    record = _record("incomplete", [("gsc_pull", "code_verified", "missing")])
    rem = remediation(record, slug="vento")
    out = render(rem)
    assert out.strip()  # non-empty
    assert "/pseo-run monthly vento --resume" in out
    assert rem["why_turkish"] in out  # the Turkish 'why' is surfaced
    # The copy-pasteable fix command is the LAST non-empty line (one next action).
    assert out.rstrip().splitlines()[-1].strip().endswith("/pseo-run monthly vento --resume")


def test_workflow_arg_flows_into_fix_command() -> None:
    record = _record("incomplete", [("x", "code_verified", "missing")])
    rem = remediation(record, slug="acme", workflow="monthly")
    assert rem["one_line_fix_command"] == "/pseo-run monthly acme --resume"
