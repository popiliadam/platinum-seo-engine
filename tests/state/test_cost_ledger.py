"""tests/state/test_cost_ledger.py — AMO batch 4a portfolio cost/quota ledger.

TDD lock for scripts/state/cost_ledger.py: the GLOBAL (portfolio-wide),
append-only, hash-chained reserve→confirm→release cost ledger with a HARD,
atomic ceiling. The substrate Faz-4 uses so 3-5 parallel project runs never
blow a real budget (GSC daily call quota, DataForSEO credit pool, image spend).

The ledger replicates consent_ledger's hash-chain primitives (canonical_json,
compute_entry_hash, GENESIS_HASH, verify_chain) and its O_APPEND + flock +
single os.write + fsync discipline — NEVER an os.replace marker. The genuinely
new bit is the reserve/confirm/release model + the atomic ceiling check: under
ONE flock critical section the writer replays the WHOLE chain, computes current
usage(resource, period), and refuses (CostCeilingExceeded, nothing written) if
the reservation would exceed the ceiling — so two parallel projects can never
both pass the check and both spend the last credits.

Authority: schemas/cost-ledger.schema.json (entry shape), batch 0b
  session_binding (CLI workspace resolution). Every filesystem test uses
tmp_path; the CLI test monkeypatches HOME so nothing touches the real config.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.state import cost_ledger as cl

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "cost-ledger.schema.json"
_NOW = "2026-06-08T00:00:00+00:00"
_DAY = "2026-06-08"


def _reserve(ws: Path, *, resource: str = "gsc_calls", period: str = _DAY,
             amount: float = 10, ceiling: float = 100, run_id: str = "run-1",
             project_id: str = "proj", **kw) -> dict:
    return cl.reserve(
        ws, resource=resource, period=period, amount=amount, ceiling=ceiling,
        run_id=run_id, project_id=project_id, now_iso=_NOW, **kw,
    )


# ---------------------------------------------------------------------------
# hash-chain primitives (replicated from consent_ledger)
# ---------------------------------------------------------------------------

def test_hash_chain_intact_then_tamper_detected(tmp_path: Path) -> None:
    """A few reserves chain cleanly; flipping a byte/seq makes verify_chain
    return the index of the first broken entry."""
    _reserve(tmp_path, run_id="r0")
    _reserve(tmp_path, run_id="r1")
    _reserve(tmp_path, run_id="r2")
    entries = cl.read_entries(tmp_path)
    assert len(entries) == 3
    assert [e["seq"] for e in entries] == [0, 1, 2]
    assert entries[0]["prev_hash"] == cl.GENESIS_HASH
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert cl.verify_chain(entries) == (True, None)

    # flip a hashed field on entry 1 -> entry_hash no longer reproduces
    tampered = [dict(e) for e in entries]
    tampered[1] = {**tampered[1], "amount": tampered[1]["amount"] + 1}
    assert cl.verify_chain(tampered) == (False, 1)

    # rewrite a seq -> monotonicity broken at that index
    reseq = [dict(e) for e in entries]
    reseq[2] = {**reseq[2], "seq": 5}
    assert cl.verify_chain(reseq) == (False, 2)


def test_reserve_mints_deterministic_reservation_id(tmp_path: Path) -> None:
    """reservation_id is derived from the under-lock seq (clock/RNG-free)."""
    e0 = _reserve(tmp_path, run_id="r0")
    e1 = _reserve(tmp_path, run_id="r1")
    assert e0["reservation_id"] == "r0"
    assert e1["reservation_id"] == "r1"


# ---------------------------------------------------------------------------
# reserve / confirm / release usage model
# ---------------------------------------------------------------------------

def test_reserve_happy_path(tmp_path: Path) -> None:
    entry = _reserve(tmp_path, amount=10, ceiling=100)
    assert entry["op"] == "reserve"
    assert entry["reservation_id"]
    Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))).validate(entry)
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 10


def test_reserve_then_confirm_less_frees_the_difference(tmp_path: Path) -> None:
    """Confirm the ACTUAL (<= reserved); the unspent remainder returns to pool."""
    r = _reserve(tmp_path, amount=10, ceiling=100)
    cl.confirm(tmp_path, reservation_id=r["reservation_id"], amount=4,
               run_id="run-1", project_id="proj", now_iso=_NOW)
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 4


def test_reserve_then_release_frees_all(tmp_path: Path) -> None:
    r = _reserve(tmp_path, amount=10, ceiling=100)
    cl.release(tmp_path, reservation_id=r["reservation_id"],
               run_id="run-1", project_id="proj", now_iso=_NOW)
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 0


# ---------------------------------------------------------------------------
# THE CORE INVARIANT — ceiling boundary (== allowed, > rejected, nothing written)
# ---------------------------------------------------------------------------

def test_ceiling_boundary_equal_allowed_over_rejected(tmp_path: Path) -> None:
    # bring usage to 95 (ceiling 100)
    _reserve(tmp_path, amount=95, ceiling=100, run_id="r-base")
    before = cl.read_entries(tmp_path)
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 95

    # > ceiling -> refused, NOTHING written, usage unchanged
    with pytest.raises(cl.CostCeilingExceeded) as ei:
        _reserve(tmp_path, amount=10, ceiling=100, run_id="r-over")
    assert ei.value.current == 95
    assert ei.value.ceiling == 100
    assert ei.value.requested == 10
    assert cl.read_entries(tmp_path) == before          # nothing written
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 95

    # == ceiling boundary -> ALLOWED (only strictly-greater rejects)
    _reserve(tmp_path, amount=5, ceiling=100, run_id="r-edge")
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 100


# ---------------------------------------------------------------------------
# isolation: period (daily reset) + resource (independent pools)
# ---------------------------------------------------------------------------

def test_period_isolation(tmp_path: Path) -> None:
    _reserve(tmp_path, amount=10, period="2026-06-08", run_id="d1")
    _reserve(tmp_path, amount=10, period="2026-06-09", run_id="d2")
    assert cl.usage(tmp_path, resource="gsc_calls", period="2026-06-08") == 10
    assert cl.usage(tmp_path, resource="gsc_calls", period="2026-06-09") == 10


def test_resource_isolation(tmp_path: Path) -> None:
    _reserve(tmp_path, amount=10, resource="gsc_calls", run_id="a")
    _reserve(tmp_path, amount=7, resource="dfs_credits", run_id="b")
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 10
    assert cl.usage(tmp_path, resource="dfs_credits", period=_DAY) == 7


# ---------------------------------------------------------------------------
# confirm / release guards (validate-before-write; no double-free)
# ---------------------------------------------------------------------------

def test_confirm_over_reserved_raises_nothing_written(tmp_path: Path) -> None:
    r = _reserve(tmp_path, amount=10, ceiling=100)
    before = cl.read_entries(tmp_path)
    with pytest.raises(cl.CostValidationError):
        cl.confirm(tmp_path, reservation_id=r["reservation_id"], amount=11,
                   run_id="run-1", project_id="proj", now_iso=_NOW)
    assert cl.read_entries(tmp_path) == before
    # the reservation is still OPEN -> effective stays the reserved 10
    assert cl.usage(tmp_path, resource="gsc_calls", period=_DAY) == 10


def test_confirm_unknown_reservation_raises(tmp_path: Path) -> None:
    _reserve(tmp_path, amount=10, ceiling=100)
    with pytest.raises(cl.CostValidationError):
        cl.confirm(tmp_path, reservation_id="r999", amount=1,
                   run_id="run-1", project_id="proj", now_iso=_NOW)


def test_double_confirm_and_double_release_raise(tmp_path: Path) -> None:
    r = _reserve(tmp_path, amount=10, ceiling=100)
    rid = r["reservation_id"]
    cl.confirm(tmp_path, reservation_id=rid, amount=4,
               run_id="run-1", project_id="proj", now_iso=_NOW)
    with pytest.raises(cl.CostValidationError):                    # double confirm
        cl.confirm(tmp_path, reservation_id=rid, amount=3,
                   run_id="run-1", project_id="proj", now_iso=_NOW)
    with pytest.raises(cl.CostValidationError):                    # release after confirm
        cl.release(tmp_path, reservation_id=rid,
                   run_id="run-1", project_id="proj", now_iso=_NOW)


def test_double_release_raises(tmp_path: Path) -> None:
    r = _reserve(tmp_path, amount=10, ceiling=100)
    rid = r["reservation_id"]
    cl.release(tmp_path, reservation_id=rid,
               run_id="run-1", project_id="proj", now_iso=_NOW)
    with pytest.raises(cl.CostValidationError):
        cl.release(tmp_path, reservation_id=rid,
                   run_id="run-1", project_id="proj", now_iso=_NOW)


# ---------------------------------------------------------------------------
# ATOMICITY — the parallel-safety proof (REAL flock across REAL processes)
# ---------------------------------------------------------------------------

_WORKER_SRC = '''\
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])               # repo root -> import scripts.*
from scripts.state import cost_ledger as cl
ws, idx, gate = Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
while not gate.exists():                       # barrier: all fire together
    time.sleep(0.003)
try:
    cl.reserve(ws, resource="gsc_calls", period="2026-06-08", amount=10,
               ceiling=50, run_id="run-" + idx, project_id="proj",
               now_iso="2026-06-08T00:00:00+00:00")
    sys.exit(0)                                # reservation fit
except cl.CostCeilingExceeded:
    sys.exit(3)                                # refused
'''


def test_concurrent_reserve_ceiling_is_atomic_no_overspend(tmp_path: Path) -> None:
    """10 REAL processes each reserve 10 against ceiling 50, released together by
    a file gate to maximize flock contention. The hard invariant: EXACTLY 5 fit
    (5*10==50), the other 5 are refused, the ledger holds EXACTLY 5 intact lines,
    and final usage is EXACTLY 50 — never 60. A check-outside-the-lock impl would
    let >5 through and overspend; the flock critical section forbids it."""
    worker = tmp_path / "_reserve_worker.py"
    worker.write_text(_WORKER_SRC, encoding="utf-8")
    ws = tmp_path / "ws"
    gate = tmp_path / "_go"
    n = 10
    procs = [
        subprocess.Popen([sys.executable, str(worker), str(REPO_ROOT),
                          str(ws), str(i), str(gate)])
        for i in range(n)
    ]
    gate.write_text("go", encoding="utf-8")     # release the barrier
    codes = [p.wait() for p in procs]

    assert codes.count(0) == 5, f"exactly 5 should fit ceiling 50; codes={codes}"
    assert codes.count(3) == 5, f"exactly 5 should be refused; codes={codes}"
    entries = cl.read_entries(ws)
    assert len(entries) == 5, "a refused reserve must write NOTHING"
    assert cl.verify_chain(entries) == (True, None), "concurrent writes tore the chain"
    assert cl.usage(ws, resource="gsc_calls", period=_DAY) == 50, "overspend!"


# ---------------------------------------------------------------------------
# fail-closed: a tampered chain makes usage() RAISE (never under-report)
# ---------------------------------------------------------------------------

def test_usage_fails_closed_on_broken_chain(tmp_path: Path) -> None:
    _reserve(tmp_path, amount=10, ceiling=100, run_id="r0")
    _reserve(tmp_path, amount=10, ceiling=100, run_id="r1")
    path = cl.cost_ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    # corrupt the first line's amount WITHOUT fixing the hash -> chain breaks
    first = json.loads(lines[0])
    first["amount"] = 999
    lines[0] = cl.canonical_json(first)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(cl.CostLedgerError):
        cl.usage(tmp_path, resource="gsc_calls", period=_DAY)
    # a reserve on top of a broken chain must ALSO fail closed
    with pytest.raises(cl.CostLedgerError):
        _reserve(tmp_path, amount=1, ceiling=100, run_id="r2")


# ---------------------------------------------------------------------------
# schema: a malformed entry fails Draft7 validation before any write
# ---------------------------------------------------------------------------

def test_valid_entry_passes_malformed_entry_rejected(tmp_path: Path) -> None:
    good = _reserve(tmp_path, amount=10, ceiling=100)
    cl._validate_entry(good)                              # no raise

    bad_op = {**good, "op": "spend"}                      # not in op enum
    with pytest.raises(cl.CostValidationError):
        cl._validate_entry(bad_op)

    missing = {k: v for k, v in good.items() if k != "resource"}
    with pytest.raises(cl.CostValidationError):
        cl._validate_entry(missing)

    extra = {**good, "surprise": 1}                       # additionalProperties:false
    with pytest.raises(cl.CostValidationError):
        cl._validate_entry(extra)


# ---------------------------------------------------------------------------
# read_ceiling — plain operator-edited shared/cost-ceilings.json
# ---------------------------------------------------------------------------

def test_read_ceiling_absent_file_and_key_is_none(tmp_path: Path) -> None:
    assert cl.read_ceiling(tmp_path, "gsc_calls") is None         # no file
    (tmp_path / "shared").mkdir(parents=True, exist_ok=True)
    (tmp_path / "shared" / "cost-ceilings.json").write_text(
        json.dumps({"gsc_calls": 1000}), encoding="utf-8")
    assert cl.read_ceiling(tmp_path, "gsc_calls") == 1000
    assert cl.read_ceiling(tmp_path, "dfs_credits") is None       # absent key


# ---------------------------------------------------------------------------
# CLI smoke — read-only `usage <resource> <period>` prints usage/ceiling/remaining
# ---------------------------------------------------------------------------

def test_cli_usage_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    ws = tmp_path / "ws"
    _reserve(ws, amount=30, ceiling=1000, run_id="r0")
    (ws / "shared" / "cost-ceilings.json").write_text(
        json.dumps({"gsc_calls": 1000}), encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "scripts.state.cost_ledger", "usage",
         "gsc_calls", _DAY, "--workspace", str(ws)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "HOME": str(tmp_path / "home")},
    )
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    assert "30" in res.stdout      # usage
    assert "1000" in res.stdout    # ceiling
    assert "970" in res.stdout     # remaining


# ---------------------------------------------------------------------------
# public API surface
# ---------------------------------------------------------------------------

def test_public_api_in_all() -> None:
    for name in ("reserve", "confirm", "release", "usage", "read_ceiling",
                 "verify_chain", "compute_entry_hash", "canonical_json",
                 "GENESIS_HASH", "cost_ledger_path", "read_entries",
                 "CostLedgerError", "CostValidationError", "CostCeilingExceeded",
                 "main"):
        assert name in cl.__all__, f"{name} missing from __all__"
