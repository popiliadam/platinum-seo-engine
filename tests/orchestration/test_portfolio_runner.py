"""tests/orchestration/test_portfolio_runner.py — AMO batch 4b portfolio sweep.

TDD lock for scripts/orchestration/portfolio_runner.py: the sequential-sweep
coordinator that, in ONE invocation, iterates the portfolio's projects IN ORDER
and runs each project's owed workflow under its OWN run-lock, reserving budget
from the 4a cost ledger BEFORE each project (job-level preflight).

The model-dependent per-project run is DELEGATED via an injectable
``run_project_fn(slug, workflow) -> dict`` (mirrors committer.commit injection
in run_step) so ``run_sweep`` is PURE + unit-testable with a STUB — no live
model, no MCP. ``run_sweep`` is clock-free: ``period`` + ``now_iso`` are passed
in (never read from a clock).

THE CORE SAFETY (kill-switch): if a project's budget reserve would exceed the
global ceiling, that project (and the remaining ones) go ``paused`` /
``not_run`` (resumable) and the sweep STOPS — never a silent under-run. A
partial reserve for the kill-switched project is RELEASED (no leak); the prior
project's reservation stays CONFIRMED (no overspend).

Authority: scripts/state/cost_ledger.py (4a ledger), scripts/state/project_lock.py
  (4b lock), shared/portfolio.json (0e2 registry shape). tmp_path only.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.state import cost_ledger as cl
from scripts.state import project_lock as pl
from scripts.orchestration import portfolio_runner as pr

_NOW = "2026-06-08T00:00:00+00:00"
_DAY = "2026-06-08"
_CREATED = "2026-06-05T00:00:00.000000Z"


# ---------------------------------------------------------------------------
# fixtures — a tmp workspace with portfolio.json + ceilings + estimates
# ---------------------------------------------------------------------------

def _shared(ws: Path) -> Path:
    d = ws / "shared"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_portfolio(ws: Path, slugs: list[str]) -> None:
    projects = [
        {"slug": s, "domain": f"https://{s}.example/", "market": "TR",
         "created_at": _CREATED}
        for s in slugs
    ]
    (_shared(ws) / "portfolio.json").write_text(
        json.dumps({"schema_version": "1.0", "projects": projects}),
        encoding="utf-8",
    )


def _write_estimates(ws: Path, mapping: dict) -> None:
    (_shared(ws) / "cost-estimates.json").write_text(
        json.dumps(mapping), encoding="utf-8")


def _write_ceilings(ws: Path, mapping: dict) -> None:
    (_shared(ws) / "cost-ceilings.json").write_text(
        json.dumps(mapping), encoding="utf-8")


def _stub(calls: list, *, actual_cost: dict | None = None,
          raises_for: str | None = None):
    """A pure stub run_project_fn: records (slug, workflow), optionally raises
    for one slug, optionally returns an actual_cost the sweep CONFIRMS."""
    def fn(slug: str, workflow: str) -> dict:
        calls.append((slug, workflow))
        if raises_for is not None and slug == raises_for:
            raise RuntimeError(f"boom in {slug}")
        result = {"run_id": f"portfolio-{slug}", "verdict": "pass"}
        if actual_cost is not None:
            result["actual_cost"] = dict(actual_cost)
        return result
    return fn


# ---------------------------------------------------------------------------
# estimate_cost / list_projects
# ---------------------------------------------------------------------------

def test_estimate_cost_reads_per_workflow(tmp_path: Path) -> None:
    _write_estimates(tmp_path, {
        "monthly": {"gsc_calls": 10, "dfs_credits": 5},
        "audit": {"dfs_credits": 100},
    })
    assert pr.estimate_cost(tmp_path, "monthly") == {"gsc_calls": 10.0, "dfs_credits": 5.0}
    assert pr.estimate_cost(tmp_path, "audit") == {"dfs_credits": 100.0}
    assert pr.estimate_cost(tmp_path, "content") == {}, "absent workflow → {}"


def test_estimate_cost_absent_file_is_empty(tmp_path: Path) -> None:
    assert pr.estimate_cost(tmp_path, "monthly") == {}, "absent file → reserve nothing"


def test_estimate_cost_missing_resource_key_omitted(tmp_path: Path) -> None:
    """A workflow with only one resource key → only that resource is reserved
    (a missing key is 0 = reserve nothing for it)."""
    _write_estimates(tmp_path, {"monthly": {"gsc_calls": 10}})
    assert pr.estimate_cost(tmp_path, "monthly") == {"gsc_calls": 10.0}


def test_list_projects_in_order_and_missing(tmp_path: Path) -> None:
    assert pr.list_projects(tmp_path) == [], "missing portfolio.json → []"
    _write_portfolio(tmp_path, ["a", "b", "c"])
    rows = pr.list_projects(tmp_path)
    assert [p["slug"] for p in rows] == ["a", "b", "c"], "must preserve order"


# ---------------------------------------------------------------------------
# happy sweep — all ran, ledger reflects confirmed actuals
# ---------------------------------------------------------------------------

def test_happy_sweep_all_ran_and_confirmed(tmp_path: Path) -> None:
    _write_portfolio(tmp_path, ["a", "b", "c"])
    _write_estimates(tmp_path, {"monthly": {"gsc_calls": 10, "dfs_credits": 5}})
    _write_ceilings(tmp_path, {"gsc_calls": 1000, "dfs_credits": 1000})
    calls: list = []
    fn = _stub(calls, actual_cost={"gsc_calls": 8, "dfs_credits": 4})

    result = pr.run_sweep(
        tmp_path, workflow="monthly", period=_DAY, now_iso=_NOW,
        run_project_fn=fn,
    )

    assert [r["slug"] for r in result["ran"]] == ["a", "b", "c"]
    assert result["skipped"] == [] and result["paused"] == []
    assert result["failed"] == [] and result["not_run"] == []
    assert result["stopped_by_kill_switch"] is False
    assert calls == [("a", "monthly"), ("b", "monthly"), ("c", "monthly")]
    # ledger reflects the CONFIRMED actuals (8 and 4 per project), not the estimate
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 24
    assert cl.usage(tmp_path, resource="dfs_credits", period=_DAY) == 12


# ---------------------------------------------------------------------------
# skip-if-locked — a project already running elsewhere is skipped, not waited on
# ---------------------------------------------------------------------------

def test_skip_if_locked(tmp_path: Path) -> None:
    _write_portfolio(tmp_path, ["a", "b", "c"])
    _write_estimates(tmp_path, {"monthly": {"gsc_calls": 1}})
    _write_ceilings(tmp_path, {"gsc_calls": 1000})
    calls: list = []

    held = pl.try_acquire(tmp_path, "b")        # B is "already running elsewhere"
    assert isinstance(held, int)
    try:
        result = pr.run_sweep(
            tmp_path, workflow="monthly", period=_DAY, now_iso=_NOW,
            run_project_fn=_stub(calls),
        )
    finally:
        pl.release(held)

    assert [r["slug"] for r in result["ran"]] == ["a", "c"]
    assert [s["slug"] for s in result["skipped"]] == ["b"]
    assert result["skipped"][0]["reason"] == "already running"
    assert result["stopped_by_kill_switch"] is False
    # the skipped project's run_project_fn was NEVER invoked
    assert ("b", "monthly") not in calls
    assert calls == [("a", "monthly"), ("c", "monthly")]


# ---------------------------------------------------------------------------
# THE KILL-SWITCH — the core safety proof
# ---------------------------------------------------------------------------

def test_kill_switch_pauses_stops_releases_partial_no_overspend(tmp_path: Path) -> None:
    """Project B's dfs reserve exceeds the ceiling → B is paused, C is not_run,
    the sweep STOPS, B's PARTIAL gsc reservation is RELEASED (no leak), and A's
    reservation stays CONFIRMED (no overspend).

    Resource order is (gsc_calls, dfs_credits, ...). With dfs ceiling 50:
      A: reserve gsc 10 (ok) + dfs 30 (ok) → run → confirm 10/30  ⇒ dfs usage 30
      B: reserve gsc 10 (ok, the PARTIAL) + dfs 30 → 30+30=60 > 50 → CEILING
         → release B's gsc 10 (partial) → paused(dfs_credits) → STOP
      C: not_run
    Final ledger: gsc usage 10 (A confirmed 10; B's partial 10 RELEASED → 0),
    dfs usage 30 (A confirmed 30; B's dfs reserve wrote NOTHING).
    """
    _write_portfolio(tmp_path, ["a", "b", "c"])
    _write_estimates(tmp_path, {"monthly": {"gsc_calls": 10, "dfs_credits": 30}})
    calls: list = []
    fn = _stub(calls, actual_cost={"gsc_calls": 10, "dfs_credits": 30})

    result = pr.run_sweep(
        tmp_path, workflow="monthly", period=_DAY, now_iso=_NOW,
        run_project_fn=fn,
        ceilings={"dfs_credits": 50},   # gsc_calls absent → no cap (treated ∞)
    )

    assert [r["slug"] for r in result["ran"]] == ["a"]
    assert [p["slug"] for p in result["paused"]] == ["b"]
    assert result["paused"][0]["resource"] == "dfs_credits"
    assert [n["slug"] for n in result["not_run"]] == ["c"]
    assert result["stopped_by_kill_switch"] is True
    # B's run_project_fn was NEVER invoked (reserve failed during preflight);
    # C never reached.
    assert calls == [("a", "monthly")]
    # NO LEAK: B's partial gsc reservation was released → only A's 10 remains.
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 10
    # NO OVERSPEND: A's 30 confirmed; B's dfs reserve wrote nothing.
    assert cl.usage(tmp_path, resource="dfs_credits", period=_DAY) == 30


# ---------------------------------------------------------------------------
# a single project's failure does NOT kill-switch — sweep CONTINUES
# ---------------------------------------------------------------------------

def test_run_project_failure_releases_and_continues(tmp_path: Path) -> None:
    _write_portfolio(tmp_path, ["a", "b", "c"])
    _write_estimates(tmp_path, {"monthly": {"dfs_credits": 5}})
    _write_ceilings(tmp_path, {"dfs_credits": 1000})
    calls: list = []
    fn = _stub(calls, raises_for="b")           # B's per-project run blows up

    result = pr.run_sweep(
        tmp_path, workflow="monthly", period=_DAY, now_iso=_NOW,
        run_project_fn=fn,
    )

    assert [r["slug"] for r in result["ran"]] == ["a", "c"]
    assert [f["slug"] for f in result["failed"]] == ["b"]
    assert result["not_run"] == [], "a single failure must NOT stop the sweep"
    assert result["stopped_by_kill_switch"] is False
    assert calls == [("a", "monthly"), ("b", "monthly"), ("c", "monthly")]
    # B's reservation was RELEASED (not leaked): usage = A(5) + C(5), B → 0.
    assert cl.usage(tmp_path, resource="dfs_credits", period=_DAY) == 10


# ---------------------------------------------------------------------------
# confirm-actual: actual < reserved frees the unspent estimate
# ---------------------------------------------------------------------------

def test_confirm_actual_less_than_reserved_frees_remainder(tmp_path: Path) -> None:
    _write_portfolio(tmp_path, ["a"])
    _write_estimates(tmp_path, {"monthly": {"gsc_calls": 10}})
    _write_ceilings(tmp_path, {"gsc_calls": 1000})

    result = pr.run_sweep(
        tmp_path, workflow="monthly", period=_DAY, now_iso=_NOW,
        run_project_fn=_stub([], actual_cost={"gsc_calls": 4}),
    )

    assert [r["slug"] for r in result["ran"]] == ["a"]
    # confirmed the ACTUAL 4, not the reserved 10 — the unspent 6 returns to pool
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 4


def test_no_actual_cost_confirms_the_reserved_amount(tmp_path: Path) -> None:
    """When run_project_fn returns no actual_cost, the sweep confirms the
    reserved estimate."""
    _write_portfolio(tmp_path, ["a"])
    _write_estimates(tmp_path, {"monthly": {"gsc_calls": 7}})
    _write_ceilings(tmp_path, {"gsc_calls": 1000})

    pr.run_sweep(tmp_path, workflow="monthly", period=_DAY, now_iso=_NOW,
                 run_project_fn=_stub([]))      # no actual_cost
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 7


def test_no_estimate_reserves_nothing_but_still_runs(tmp_path: Path) -> None:
    """No cost-estimates.json → reserve nothing, but every project still runs."""
    _write_portfolio(tmp_path, ["a", "b"])
    calls: list = []
    result = pr.run_sweep(tmp_path, workflow="monthly", period=_DAY, now_iso=_NOW,
                          run_project_fn=_stub(calls))
    assert [r["slug"] for r in result["ran"]] == ["a", "b"]
    assert calls == [("a", "monthly"), ("b", "monthly")]
    assert cl.read_entries(tmp_path) == [], "nothing reserved when no estimates"


# ---------------------------------------------------------------------------
# render_summary — Turkish operator surface, names the kill-switch resource
# ---------------------------------------------------------------------------

def test_render_summary_names_killswitch_resource(tmp_path: Path) -> None:
    result = {
        "workflow": "monthly", "period": _DAY,
        "ran": [{"slug": "a"}], "skipped": [],
        "paused": [{"slug": "b", "resource": "dfs_credits", "ceiling": 50,
                    "requested": 30, "current": 30, "message": "x"}],
        "failed": [], "not_run": [{"slug": "c"}],
        "stopped_by_kill_switch": True,
    }
    s = pr.render_summary(result)
    assert isinstance(s, str)
    assert "dfs_credits" in s, "must name the kill-switch resource"
    assert "b" in s, "must name the paused project"
    assert "monthly" in s
    # a resume hint pointing back at the portfolio recipe
    assert "/pseo-run-portfolio" in s


def test_render_summary_happy_has_counts_no_killswitch(tmp_path: Path) -> None:
    result = {
        "workflow": "monthly", "period": _DAY,
        "ran": [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}],
        "skipped": [], "paused": [], "failed": [], "not_run": [],
        "stopped_by_kill_switch": False,
    }
    s = pr.render_summary(result)
    assert "3" in s, "ran count surfaced"
    assert "bütçe tavanı" not in s.lower(), "no kill-switch banner on a clean sweep"


# ---------------------------------------------------------------------------
# public API surface
# ---------------------------------------------------------------------------

def test_public_api_in_all() -> None:
    for name in ("estimate_cost", "list_projects", "run_sweep", "render_summary",
                 "PortfolioRunnerError"):
        assert name in pr.__all__, f"{name} missing from __all__"
