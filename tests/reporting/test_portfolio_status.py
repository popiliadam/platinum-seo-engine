"""tests/reporting/test_portfolio_status.py — AMO portfolio triage (batch 4c).

TDD lock for scripts/reporting/portfolio_status.py: the READ-ONLY portfolio-wide
triage reporter. For each project it reads the LATEST coverage record and maps the
coverage ``verdict`` to a triage row (healthy / owed / failed / paused / none),
then summarizes the GLOBAL 4a budget (usage vs ceiling per resource). It WRITES
NOTHING — it only READS coverage records + the cost ledger + portfolio.json, the
read-only companion to the per-project ``/pseo-status``.

Fixtures seed a tmp workspace at the REAL paths:
  - shared/portfolio.json via the real ``portfolio_writer`` (order = registration order),
  - per-project coverage records via the real ``coverage.write_coverage`` (so the
    reader is proven against the writer) or a direct write for the corrupt cases,
  - the GLOBAL ledger via real ``cost_ledger.reserve``/``confirm`` (test setup —
    NOT the module writing) + a hand-tampered chain for the fail-closed case,
  - shared/cost-ceilings.json by a direct write.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from scripts.orchestration import coverage
from scripts.reporting import portfolio_status as ps
from scripts.state import cost_ledger, portfolio_writer

# Fixed mtime stamps (ns) — no clock; T2 is strictly newer than T1.
_T1 = 1_000_000_000_000_000_000
_T2 = 2_000_000_000_000_000_000
_PERIOD = "2026-06-08"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _register(ws: Path, slug: str) -> None:
    """Register a project in shared/portfolio.json (real flock-guarded writer)."""
    portfolio_writer.register_project(
        ws, slug, f"https://{slug}.test", "us", created_at="2026-06-08T00:00:00Z"
    )


def _write_cov(ws: Path, slug: str, run_id: str, *, verdict: str, steps, required) -> dict:
    """Write a schema-valid coverage record via the REAL writer; return the record."""
    rec = coverage.build_record(
        run_id=run_id, steps=list(steps), required_satisfied=required,
        verdict=verdict, project_slug=slug,
    )
    coverage.write_coverage(rec, workspace_root=ws, project_slug=slug, run_id=run_id)
    return rec


def _ok_step(name: str = "fetch_gsc", status: str = "satisfied") -> dict:
    return coverage.build_step(name, "code_verified", status)


def _seed_usage(ws: Path, resource: str, period: str, amount: float, ceiling: float) -> None:
    """Populate global ledger usage for (resource, period) via reserve+confirm.

    This is TEST SETUP using the real ledger writer — the module under test never
    writes the ledger; it only reads it.
    """
    entry = cost_ledger.reserve(
        ws, resource=resource, period=period, amount=amount, ceiling=ceiling,
        run_id="seed", project_id="seed", now_iso="2026-06-08T00:00:00Z",
    )
    cost_ledger.confirm(
        ws, reservation_id=entry["reservation_id"], amount=amount,
        run_id="seed", project_id="seed", now_iso="2026-06-08T00:00:00Z",
    )


def _write_ceilings(ws: Path, mapping: dict) -> None:
    path = Path(ws) / "shared" / "cost-ceilings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping), encoding="utf-8")


def _tamper_ledger(ws: Path) -> None:
    """Break the hash chain: mutate entry 0's amount but leave its stale entry_hash
    so verify_chain rejects it and ``usage`` fails closed."""
    path = cost_ledger.cost_ledger_path(ws)
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["amount"] = first["amount"] + 999
    lines[0] = json.dumps(first)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _budget_row(triage: dict, resource: str) -> dict:
    return next(b for b in triage["budget"] if b["resource"] == resource)


# ---------------------------------------------------------------------------
# classify() — one case per verdict + missing_steps + defensive unknown
# ---------------------------------------------------------------------------

def test_classify_pass_is_healthy():
    out = ps.classify({"run_id": "r-2026-06-08-aaaa", "verdict": "pass", "steps": []})
    assert out["category"] == "healthy"
    assert out["cause"] == "—"
    assert out["run_id"] == "r-2026-06-08-aaaa"
    assert out["verdict"] == "pass"
    assert out["missing_steps"] == []


def test_classify_incomplete_is_owed_internal():
    out = ps.classify({"run_id": "r", "verdict": "incomplete", "steps": []})
    assert out["category"] == "owed"
    assert out["cause"] == "internal"


def test_classify_failed_is_failed_internal():
    out = ps.classify({"run_id": "r", "verdict": "failed", "steps": []})
    assert out["category"] == "failed"
    assert out["cause"] == "internal"


def test_classify_paused_is_paused_external():
    out = ps.classify({"run_id": "r", "verdict": "paused", "steps": []})
    assert out["category"] == "paused"
    assert out["cause"] == "external"


def test_classify_missing_steps_collects_missing_and_failed():
    steps = [
        {"name": "a", "verification_class": "code_verified", "status": "satisfied"},
        {"name": "b", "verification_class": "code_verified", "status": "missing"},
        {"name": "c", "verification_class": "model_attested", "status": "failed"},
        {"name": "d", "verification_class": "code_verified", "status": "pending"},
    ]
    out = ps.classify({"run_id": "r", "verdict": "failed", "steps": steps})
    assert out["missing_steps"] == ["b", "c"]  # in record order, {missing,failed} only


def test_classify_unknown_verdict_is_defensive():
    out = ps.classify({"run_id": "r", "verdict": "weird", "steps": []})
    assert out["category"] == "weird"  # verdict string echoed, never crashes
    assert out["cause"] == "—"
    assert out["missing_steps"] == []


# ---------------------------------------------------------------------------
# latest_coverage() — robust selection by (mtime_ns, run_id)
# ---------------------------------------------------------------------------

def test_latest_coverage_missing_dir_is_none(tmp_path):
    assert ps.latest_coverage(tmp_path / "ws", "nope") is None


def test_latest_coverage_single_record(tmp_path):
    ws = tmp_path / "ws"
    rec = _write_cov(ws, "demo", "demo-2026-06-08-aaaa", verdict="pass",
                     steps=[_ok_step()], required=True)
    assert ps.latest_coverage(ws, "demo") == rec


def test_latest_coverage_returns_newer_by_mtime(tmp_path):
    ws = tmp_path / "ws"
    # older file has the LEXICALLY-GREATER run_id; the newer mtime must still win.
    _write_cov(ws, "demo", "demo-2026-06-08-ffff", verdict="pass",
               steps=[_ok_step()], required=True)
    newer = _write_cov(ws, "demo", "demo-2026-06-08-aaaa", verdict="incomplete",
                       steps=[_ok_step(status="missing")], required=False)
    os.utime(coverage.coverage_path(ws, "demo", "demo-2026-06-08-ffff"), ns=(_T1, _T1))
    os.utime(coverage.coverage_path(ws, "demo", "demo-2026-06-08-aaaa"), ns=(_T2, _T2))
    assert ps.latest_coverage(ws, "demo") == newer


def test_latest_coverage_mtime_tie_breaks_by_run_id(tmp_path):
    ws = tmp_path / "ws"
    _write_cov(ws, "demo", "demo-2026-06-08-aaaa", verdict="pass",
               steps=[_ok_step()], required=True)
    bbbb = _write_cov(ws, "demo", "demo-2026-06-08-bbbb", verdict="failed",
                      steps=[_ok_step(status="failed")], required=False)
    pa = coverage.coverage_path(ws, "demo", "demo-2026-06-08-aaaa")
    pb = coverage.coverage_path(ws, "demo", "demo-2026-06-08-bbbb")
    os.utime(pa, ns=(_T1, _T1))
    os.utime(pb, ns=(_T1, _T1))  # SAME mtime -> tie broken by larger run_id (bbbb)
    assert ps.latest_coverage(ws, "demo") == bbbb


def test_latest_coverage_all_corrupt_is_none(tmp_path):
    ws = tmp_path / "ws"
    cov_dir = coverage.coverage_path(ws, "demo", "_").parent
    cov_dir.mkdir(parents=True, exist_ok=True)
    (cov_dir / "a.json").write_text("{ not json", encoding="utf-8")
    (cov_dir / "b.json").write_text("also broken", encoding="utf-8")
    assert ps.latest_coverage(ws, "demo") is None


def test_latest_coverage_skips_corrupt_keeps_valid(tmp_path):
    ws = tmp_path / "ws"
    rec = _write_cov(ws, "demo", "demo-2026-06-08-aaaa", verdict="pass",
                     steps=[_ok_step()], required=True)
    cov_dir = coverage.coverage_path(ws, "demo", "_").parent
    (cov_dir / "corrupt.json").write_text("{ broken", encoding="utf-8")
    # corrupt file is NEWER — proves it is skipped, not just out-sorted.
    os.utime(coverage.coverage_path(ws, "demo", "demo-2026-06-08-aaaa"), ns=(_T1, _T1))
    os.utime(cov_dir / "corrupt.json", ns=(_T2, _T2))
    assert ps.latest_coverage(ws, "demo") == rec


# ---------------------------------------------------------------------------
# build_triage() — rows in portfolio order
# ---------------------------------------------------------------------------

def test_build_triage_rows_in_portfolio_order(tmp_path):
    ws = tmp_path / "ws"
    _register(ws, "proj-alpha")
    _register(ws, "proj-beta")
    _register(ws, "proj-gamma")
    _write_cov(ws, "proj-alpha", "proj-alpha-2026-06-08-aaaa", verdict="pass",
               steps=[_ok_step()], required=True)
    _write_cov(ws, "proj-beta", "proj-beta-2026-06-08-bbbb", verdict="incomplete",
               steps=[_ok_step(status="missing")], required=False)
    # proj-gamma intentionally has NO coverage record.
    triage = ps.build_triage(ws, period=_PERIOD)

    assert triage["period"] == _PERIOD
    assert [r["slug"] for r in triage["rows"]] == ["proj-alpha", "proj-beta", "proj-gamma"]
    alpha, beta, gamma = triage["rows"]
    assert alpha["category"] == "healthy" and alpha["cause"] == "—"
    assert alpha["run_id"] == "proj-alpha-2026-06-08-aaaa" and alpha["missing_steps"] == []
    assert beta["category"] == "owed" and beta["cause"] == "internal"
    assert beta["verdict"] == "incomplete" and beta["missing_steps"] == ["fetch_gsc"]
    assert gamma == {"slug": "proj-gamma", "run_id": None, "verdict": None,
                     "missing_steps": [], "cause": "—", "category": "none"}


def test_build_triage_empty_portfolio_rows_empty(tmp_path):
    triage = ps.build_triage(tmp_path / "ws", period=_PERIOD)
    assert triage["rows"] == []


# ---------------------------------------------------------------------------
# build_triage() — budget block (used / ceiling / remaining / error)
# ---------------------------------------------------------------------------

def test_build_triage_budget_used_ceiling_remaining(tmp_path):
    ws = tmp_path / "ws"
    _write_ceilings(ws, {"gsc_calls": 100})
    _seed_usage(ws, "gsc_calls", _PERIOD, 12, 100)
    triage = ps.build_triage(ws, period=_PERIOD)
    row = _budget_row(triage, "gsc_calls")
    assert row["used"] == 12.0
    assert row["ceiling"] == 100.0
    assert row["remaining"] == 88.0
    assert row["error"] is None
    # the three pools appear in canonical order.
    assert [b["resource"] for b in triage["budget"]] == [
        "gsc_calls", "dfs_credits", "image_spend"]


def test_build_triage_budget_unset_ceiling_remaining_none(tmp_path):
    ws = tmp_path / "ws"
    triage = ps.build_triage(ws, period=_PERIOD)
    row = _budget_row(triage, "image_spend")
    assert row["ceiling"] is None
    assert row["remaining"] is None  # no cap -> remaining undefined
    assert row["used"] == 0.0
    assert row["error"] is None


def test_build_triage_budget_broken_chain_surfaces_error_no_crash(tmp_path):
    ws = tmp_path / "ws"
    _register(ws, "proj-alpha")
    _write_cov(ws, "proj-alpha", "proj-alpha-2026-06-08-aaaa", verdict="pass",
               steps=[_ok_step()], required=True)
    _seed_usage(ws, "gsc_calls", _PERIOD, 5, 1000)
    _tamper_ledger(ws)
    triage = ps.build_triage(ws, period=_PERIOD)
    # The triage STILL returns the project rows — one broken ledger never blanks it.
    assert [r["slug"] for r in triage["rows"]] == ["proj-alpha"]
    row = _budget_row(triage, "gsc_calls")
    assert row["used"] is None
    assert row["remaining"] is None
    assert row["error"]  # surfaced, not silently dropped


# ---------------------------------------------------------------------------
# render_triage() — Turkish operator block, deterministic
# ---------------------------------------------------------------------------

def _sample_triage() -> dict:
    return {
        "period": _PERIOD,
        "rows": [
            {"slug": "alpha", "run_id": "alpha-2026-06-08-aaaa", "verdict": "pass",
             "missing_steps": [], "cause": "—", "category": "healthy"},
            {"slug": "beta", "run_id": "beta-2026-06-08-bbbb", "verdict": "incomplete",
             "missing_steps": ["fetch_gsc"], "cause": "internal", "category": "owed"},
            {"slug": "gamma", "run_id": None, "verdict": None,
             "missing_steps": [], "cause": "—", "category": "none"},
        ],
        "budget": [
            {"resource": "gsc_calls", "used": 12.0, "ceiling": 100.0,
             "remaining": 88.0, "error": None},
            {"resource": "dfs_credits", "used": 5.0, "ceiling": None,
             "remaining": None, "error": None},
            {"resource": "image_spend", "used": None, "ceiling": None,
             "remaining": None, "error": "cost ledger chain broken at entry 0"},
        ],
    }


def test_render_triage_contains_period_slugs_and_labels():
    out = ps.render_triage(_sample_triage())
    assert _PERIOD in out
    for slug in ("alpha", "beta", "gamma"):
        assert slug in out
    assert "sağlıklı" in out   # healthy label (Turkish)
    assert "eksik" in out      # owed label (Turkish)
    assert "fetch_gsc" in out  # the missing step is surfaced


def test_render_triage_budget_lines_and_markers():
    out = ps.render_triage(_sample_triage())
    for resource in ("gsc_calls", "dfs_credits", "image_spend"):
        assert resource in out
    assert "sınırsız" in out  # unset ceiling marker
    assert "HATA" in out      # usage-error marker
    assert "cost ledger chain broken at entry 0" in out  # the error message itself


def test_render_triage_non_healthy_row_gets_next_action_hint():
    out = ps.render_triage(_sample_triage())
    assert "/pseo-run" in out  # generic resume hint (no invented workflow name)
    assert "<workflow>" in out  # placeholder, not a concrete workflow


def test_render_triage_is_deterministic():
    triage = _sample_triage()
    assert ps.render_triage(triage) == ps.render_triage(triage)


# ---------------------------------------------------------------------------
# READ-ONLY proof — the module source contains NO write primitive
# ---------------------------------------------------------------------------

def test_module_has_zero_write_primitives():
    src = Path(ps.__file__).read_text(encoding="utf-8")
    forbidden = [
        "os.replace", ".write_coverage", "cost_ledger.reserve",
        ".reserve(", ".confirm(", ".release(",
        ".write_text(", ".write_bytes(", "json.dump(",
    ]
    for token in forbidden:
        assert token not in src, f"read-only violation: {token!r} present in module"
    # no file opened in a write/append mode
    assert re.search(r"open\([^)]*['\"][wax]", src) is None
