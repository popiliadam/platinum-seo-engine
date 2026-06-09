#!/usr/bin/env python3
"""cost_ledger.py — GLOBAL append-only, hash-chained cost/quota ledger (AMO 4a).

The portfolio-wide reserve→confirm→release budget substrate Faz-4 uses so 3-5
parallel project runs never blow a real budget (GSC daily call quota, DataForSEO
credit pool, image-generation spend). ONE shared file for the whole portfolio:

    {workspace_root}/shared/cost_ledger.jsonl

(GLOBAL, under shared/ — NOT per-project like consent_ledger; the ceiling is
portfolio-wide. run_id + project_id are provenance FIELDS, not path segments.)

Model (the genuinely new bit vs consent):
  - reserve  — hold an estimate against a HARD ceiling. Mints a reservation_id
    derived from the under-lock seq ('r'+seq), so it is unique WITHOUT a clock
    or RNG (both banned — this module is pure/clock-free; timestamps + period
    are passed IN). Under the flock it replays the WHOLE chain to current
    usage(resource, period); if usage + amount > ceiling it raises
    CostCeilingExceeded and writes NOTHING; else it appends the reserve.
  - confirm  — record the ACTUAL spend (amount <= the reservation's reserved
    amount) for an open reservation.
  - release  — free an open reservation (effective amount 0).
  USAGE(resource, period) = sum over reservation_ids of each reservation's
  EFFECTIVE amount: confirmed -> the actual; released -> 0; still-open -> the
  reserved amount. Replayed from the INTACT chain (fail-closed on tamper).

The atomic reserve (read → replay → ceiling-check → append, ALL inside one
fcntl.flock(LOCK_EX) critical section) is the whole point: two parallel project
runs can never both pass the check and both spend the last credits.

Discipline (rules/append-only-state.md — an append-only LOG, NOT a marker):
  - Atomic append: os.open(O_WRONLY|O_CREAT|O_APPEND) + fcntl.flock(LOCK_EX) +
    a single os.write + os.fsync. The chain is replayed UNDER the same flock
    that guards the append (mirrors consent_ledger / events_writer), so
    concurrent appenders serialize and chain correctly.
  - NEVER os.replace / tempfile-rename — that inode-swaps an append-only log and
    loses concurrent writers' data.
  - Validation BEFORE the write: jsonschema Draft7Validator against
    schemas/cost-ledger.schema.json. A defective entry raises and never touches
    the file.

The hash-chain primitives (canonical_json, compute_entry_hash, GENESIS_HASH,
verify_chain) are REPLICATED from consent_ledger (batch 2a), not imported — they
key a frozen contract there; this module owns its own copy. Purely ADDITIVE: it
imports session_binding only to resolve the read-only CLI's workspace.

Public API:
    canonical_json(obj) -> str
    compute_entry_hash(entry_without_entry_hash) -> str
    cost_ledger_path(workspace_root) -> Path
    read_entries(workspace_root) -> list[dict]
    verify_chain(entries) -> tuple[bool, int | None]
    usage(workspace_root, *, resource, period) -> float
    read_ceiling(workspace_root, resource) -> float | None
    reserve(workspace_root, *, resource, period, amount, ceiling, run_id,
            project_id, now_iso, note=None, schema_path=None) -> dict
    confirm(workspace_root, *, reservation_id, amount, run_id, project_id,
            now_iso, note=None, schema_path=None) -> dict
    release(workspace_root, *, reservation_id, run_id, project_id, now_iso,
            note=None, schema_path=None) -> dict

CLI (read-only — the orchestrator writes via the API; the operator edits
shared/cost-ceilings.json by hand):
    python3 -m scripts.state.cost_ledger usage <resource> <period>
            [--workspace <path>]
"""

from __future__ import annotations

import argparse
import fcntl
import functools
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Iterable

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError

from scripts.state import session_binding
from scripts.validation.validate_schema import build_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = "1.0"
GENESIS_HASH = "0" * 64  # prev_hash of the genesis (seq 0) line

# Module dir: <repo>/scripts/state/cost_ledger.py -> repo = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "cost-ledger.schema.json"

# The three portfolio cost pools (must mirror cost-ledger.schema.json resource enum).
_RESOURCES: frozenset[str] = frozenset({"gsc_calls", "dfs_credits", "image_spend"})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CostLedgerError(Exception):
    """Base class for all cost_ledger errors."""


class CostValidationError(CostLedgerError):
    """Raised when an entry fails schema validation or a confirm/release guard."""


class CostCeilingExceeded(CostLedgerError):
    """Raised when a reserve would exceed the ceiling (NOTHING is written).

    Carries the numbers the caller needs for a `paused` message (batch 4b
    kill-switch): which resource/period, how much was requested, the ceiling,
    and the current usage at the time of refusal.
    """

    def __init__(self, *, resource: str, period: str, requested: float,
                 ceiling: float, current: float) -> None:
        self.resource = resource
        self.period = period
        self.requested = requested
        self.ceiling = ceiling
        self.current = current
        super().__init__(
            f"reserve refused: {resource} [{period}] usage {current} + "
            f"{requested} > ceiling {ceiling}"
        )


# ---------------------------------------------------------------------------
# Hash helpers (replicated verbatim from consent_ledger — generic chain-log primitives)
# ---------------------------------------------------------------------------

def canonical_json(obj: dict) -> str:
    """Deterministic JSON encoding used for hashing AND the on-disk line.

    sort_keys makes the byte sequence independent of insertion order; compact
    separators + ensure_ascii=False keep it minimal UTF-8. verify_chain
    recomputes entry_hash over THIS exact encoding, so it must never drift.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(entry_without_entry_hash: dict) -> str:
    """sha256 hex over canonical_json of the entry with entry_hash REMOVED.

    Builds a NEW dict (no mutation of the caller's entry) excluding entry_hash,
    then hashes its canonical encoding. prev_hash IS one of the hashed fields,
    so the chain link is bound into entry_hash.
    """
    payload = {k: v for k, v in entry_without_entry_hash.items() if k != "entry_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Paths + validation
# ---------------------------------------------------------------------------

def cost_ledger_path(workspace_root: Path | str) -> Path:
    """Build {workspace_root}/shared/cost_ledger.jsonl (mkdir -p shared/).

    GLOBAL — one file for the whole portfolio, no slug in the path (the ceiling
    is portfolio-wide). shared/ already holds active.json + sessions/<uuid>.json.
    """
    shared_dir = Path(workspace_root) / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    return shared_dir / "cost_ledger.jsonl"


@functools.lru_cache(maxsize=4)
def _get_validator(schema_path: str) -> Draft7Validator:
    """Cache one Draft7Validator per schema path (lru_cache hashes the str key).

    Routes through validate_schema.build_validator so recorded_at's
    format:date-time is ENFORCED with the strict UTC '…Z' checker (P1-02 /
    time-discipline §8.10) — a plain Draft7Validator treats `format` as a bare
    annotation and would let a naive/non-UTC recorded_at into the ledger.
    """
    with Path(schema_path).open("r", encoding="utf-8") as fh:
        return build_validator(json.load(fh))


def _validate_entry(entry: dict, schema_path: Path | None = None) -> None:
    """Draft7 validation. Raises CostValidationError aggregating all errors."""
    try:
        validator = _get_validator(str(schema_path or _SCHEMA_PATH))
    except (OSError, json.JSONDecodeError) as exc:
        raise CostValidationError(f"failed to load cost-ledger schema: {exc}") from exc
    errors: list[_JSValidationError] = sorted(
        validator.iter_errors(entry), key=lambda e: list(e.path)
    )
    if errors:
        msgs = []
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            msgs.append(f"{loc}: {err.message}")
        raise CostValidationError("; ".join(msgs))


def _coerce_amount(amount: object) -> float | int:
    """Require a non-negative real number; preserve int-ness (gsc_calls counts).

    bool is rejected (it is an int subclass but never a valid amount).
    """
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise CostValidationError(f"amount must be a number (got {amount!r})")
    if amount < 0:
        raise CostValidationError(f"amount must be >= 0 (got {amount})")
    return amount


def _check_resource(resource: str) -> None:
    if resource not in _RESOURCES:
        raise CostValidationError(
            f"unknown resource {resource!r}; valid: {', '.join(sorted(_RESOURCES))}"
        )


# ---------------------------------------------------------------------------
# Read + verify + replay
# ---------------------------------------------------------------------------

def _parse_lines(path: Path) -> list[dict]:
    """Parse every non-blank line into a list of dicts (missing file -> [])."""
    if not path.exists():
        return []
    entries: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise CostLedgerError(
                    f"corrupt JSON at line {lineno} in {path}: {exc}"
                ) from exc
    return entries


def read_entries(workspace_root: Path | str) -> list[dict]:
    """Parse every non-blank line of cost_ledger.jsonl. Missing file -> []."""
    return _parse_lines(cost_ledger_path(workspace_root))


def verify_chain(entries: list[dict]) -> tuple[bool, int | None]:
    """Re-walk the hash chain. Returns (True, None) if intact, else (False, idx).

    For each entry i: seq must equal i; prev_hash must equal GENESIS_HASH (i==0)
    or entries[i-1].entry_hash; compute_entry_hash(entry) must reproduce
    entry.entry_hash. The first violation returns its index. Empty list is intact.
    """
    for i, entry in enumerate(entries):
        if entry.get("seq") != i:
            return (False, i)
        expected_prev = GENESIS_HASH if i == 0 else entries[i - 1].get("entry_hash")
        if entry.get("prev_hash") != expected_prev:
            return (False, i)
        if compute_entry_hash(entry) != entry.get("entry_hash"):
            return (False, i)
    return (True, None)


def _replay(entries: list[dict]) -> dict[str, dict]:
    """reservation_id -> {resource, period, reserved, state, effective}.

    reserve sets state 'open' / effective = reserved; confirm -> state
    'confirmed' / effective = the actual; release -> state 'released' /
    effective 0. Builds NEW dicts on transition (no in-place mutation). The
    chain is append-only and guards forbid orphan/double ops, so order is always
    reserve-then-(confirm|release) and each reservation resolves cleanly.
    """
    state: dict[str, dict] = {}
    for entry in entries:
        rid = entry.get("reservation_id")
        op = entry.get("op")
        if op == "reserve":
            state[rid] = {
                "resource": entry.get("resource"),
                "period": entry.get("period"),
                "reserved": entry.get("amount"),
                "state": "open",
                "effective": entry.get("amount"),
            }
        elif op == "confirm" and rid in state:
            state[rid] = {**state[rid], "state": "confirmed",
                          "effective": entry.get("amount")}
        elif op == "release" and rid in state:
            state[rid] = {**state[rid], "state": "released", "effective": 0}
    return state


def _usage_from(entries: list[dict], resource: str, period: str) -> float:
    """Sum the effective amount of every reservation matching (resource, period)."""
    state = _replay(entries)
    return float(sum(
        r["effective"] for r in state.values()
        if r["resource"] == resource and r["period"] == period
    ))


def usage(workspace_root: Path | str, *, resource: str, period: str) -> float:
    """Current usage for (resource, period). RAISES on a broken chain (fail-closed).

    Replays the INTACT chain — never silently under-reports usage over tampered
    data (which would let a real budget be overspent).
    """
    _check_resource(resource)
    entries = read_entries(workspace_root)
    intact, idx = verify_chain(entries)
    if not intact:
        raise CostLedgerError(
            f"cost ledger chain broken at entry {idx}; refusing to report usage"
        )
    return _usage_from(entries, resource, period)


def read_ceiling(workspace_root: Path | str, resource: str) -> float | None:
    """Read shared/cost-ceilings.json[resource]. Absent file/key -> None.

    A plain operator-edited config (O5: the operator enters real quotas before
    the scheduler is armed) — validated lightly here, no dedicated schema.
    """
    path = Path(workspace_root) / "shared" / "cost-ceilings.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CostLedgerError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CostLedgerError(f"cost-ceilings.json must be a JSON object: {path}")
    val = data.get(resource)
    if val is None:
        return None
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise CostLedgerError(f"ceiling for {resource!r} must be a number (got {val!r})")
    return float(val)


# ---------------------------------------------------------------------------
# Append (the flock critical section)
# ---------------------------------------------------------------------------

def _open_locked(path: Path) -> int:
    """Open the log O_APPEND and take an exclusive flock. Returns the held fd."""
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    except OSError as exc:
        raise CostLedgerError(f"cannot open {path}: {exc}") from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError as exc:
        os.close(fd)
        raise CostLedgerError(f"flock failed on {path}: {exc}") from exc
    return fd


def _unlock_close(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def _locked_read_verify(path: Path) -> list[dict]:
    """Parse + verify the chain UNDER the held flock; raise on tamper (fail-closed).

    Reads via a separate read-fd while we hold LOCK_EX on the write-fd, so no
    other writer is in its critical section — the content is stable.
    """
    entries = _parse_lines(path)
    intact, idx = verify_chain(entries)
    if not intact:
        raise CostLedgerError(f"cost ledger chain broken at entry {idx}")
    return entries


def _next_links(entries: list[dict]) -> tuple[int, str]:
    """(seq, prev_hash) for the next entry given the verified chain so far."""
    if not entries:
        return 0, GENESIS_HASH
    return len(entries), entries[-1]["entry_hash"]


def _make_entry(*, op: str, seq: int, resource: str, period: str,
                amount: float | int, reservation_id: str, run_id: str,
                project_id: str, now_iso: str, prev_hash: str,
                note: str | None) -> dict:
    """Build one entry dict and seal it with entry_hash (prev_hash is hashed in)."""
    entry: dict = {
        "schema_version": _SCHEMA_VERSION,
        "seq": seq,
        "op": op,
        "resource": resource,
        "period": period,
        "amount": amount,
        "reservation_id": reservation_id,
        "run_id": run_id,
        "project_id": project_id,
        "recorded_at": now_iso,
        "prev_hash": prev_hash,
    }
    if note is not None:
        entry["note"] = note
    entry["entry_hash"] = compute_entry_hash(entry)
    return entry


def _append_entry(fd: int, entry: dict, schema_path: Path | None) -> dict:
    """Validate BEFORE writing, then atomically append the line under the flock."""
    _validate_entry(entry, schema_path)
    payload = (canonical_json(entry) + "\n").encode("utf-8")
    written = os.write(fd, payload)
    if written != len(payload):
        raise CostLedgerError(
            f"short write: wrote {written} of {len(payload)} bytes"
        )
    os.fsync(fd)
    return entry


def reserve(
    workspace_root: Path | str,
    *,
    resource: str,
    period: str,
    amount: float | int,
    ceiling: float | int,
    run_id: str,
    project_id: str,
    now_iso: str,
    note: str | None = None,
    schema_path: Path | None = None,
) -> dict:
    """Atomically reserve `amount` of (resource, period) under a HARD ceiling.

    The whole critical section — read+verify the chain, replay to current usage,
    ceiling-check, append — runs while holding fcntl.flock(LOCK_EX), so two
    parallel runs can never both pass the check. Boundary: usage + amount ==
    ceiling is ALLOWED; only strictly-greater raises CostCeilingExceeded (and
    writes NOTHING). Returns the written reserve entry (incl. its reservation_id).
    """
    _check_resource(resource)
    amount = _coerce_amount(amount)
    path = cost_ledger_path(workspace_root)
    fd = _open_locked(path)
    try:
        entries = _locked_read_verify(path)
        current = _usage_from(entries, resource, period)
        if current + amount > ceiling:
            raise CostCeilingExceeded(
                resource=resource, period=period, requested=amount,
                ceiling=float(ceiling), current=current,
            )
        seq, prev_hash = _next_links(entries)
        entry = _make_entry(
            op="reserve", seq=seq, resource=resource, period=period,
            amount=amount, reservation_id=f"r{seq}", run_id=run_id,
            project_id=project_id, now_iso=now_iso, prev_hash=prev_hash, note=note,
        )
        return _append_entry(fd, entry, schema_path)
    finally:
        _unlock_close(fd)


def _resolve_open(entries: list[dict], reservation_id: str) -> dict:
    """Return the OPEN reservation for reservation_id, else raise (unknown/closed)."""
    reservation = _replay(entries).get(reservation_id)
    if reservation is None:
        raise CostValidationError(f"unknown reservation_id {reservation_id!r}")
    if reservation["state"] != "open":
        raise CostValidationError(
            f"reservation {reservation_id!r} already {reservation['state']}"
        )
    return reservation


def confirm(
    workspace_root: Path | str,
    *,
    reservation_id: str,
    amount: float | int,
    run_id: str,
    project_id: str,
    now_iso: str,
    note: str | None = None,
    schema_path: Path | None = None,
) -> dict:
    """Record the ACTUAL spend (amount <= reserved) for an OPEN reservation.

    Raises CostValidationError (nothing written) if the reservation is unknown,
    already confirmed/released, or amount exceeds the reserved amount. Carries
    the reservation's resource/period so replay needs no back-reference.
    """
    amount = _coerce_amount(amount)
    path = cost_ledger_path(workspace_root)
    fd = _open_locked(path)
    try:
        entries = _locked_read_verify(path)
        reservation = _resolve_open(entries, reservation_id)
        if amount > reservation["reserved"]:
            raise CostValidationError(
                f"confirm amount {amount} exceeds reserved "
                f"{reservation['reserved']} for {reservation_id!r}"
            )
        seq, prev_hash = _next_links(entries)
        entry = _make_entry(
            op="confirm", seq=seq, resource=reservation["resource"],
            period=reservation["period"], amount=amount,
            reservation_id=reservation_id, run_id=run_id, project_id=project_id,
            now_iso=now_iso, prev_hash=prev_hash, note=note,
        )
        return _append_entry(fd, entry, schema_path)
    finally:
        _unlock_close(fd)


def release(
    workspace_root: Path | str,
    *,
    reservation_id: str,
    run_id: str,
    project_id: str,
    now_iso: str,
    note: str | None = None,
    schema_path: Path | None = None,
) -> dict:
    """Free an OPEN reservation (effective amount 0).

    Raises CostValidationError (nothing written) if the reservation is unknown or
    already confirmed/released — a release does NOT double-free.
    """
    path = cost_ledger_path(workspace_root)
    fd = _open_locked(path)
    try:
        entries = _locked_read_verify(path)
        reservation = _resolve_open(entries, reservation_id)
        seq, prev_hash = _next_links(entries)
        entry = _make_entry(
            op="release", seq=seq, resource=reservation["resource"],
            period=reservation["period"], amount=0,
            reservation_id=reservation_id, run_id=run_id, project_id=project_id,
            now_iso=now_iso, prev_hash=prev_hash, note=note,
        )
        return _append_entry(fd, entry, schema_path)
    finally:
        _unlock_close(fd)


# ---------------------------------------------------------------------------
# CLI — read-only `usage` subcommand (mirrors consent_ledger's argparse main)
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cost_ledger.py",
        description="Inspect the portfolio cost/quota ledger (AMO batch 4a, read-only).",
    )
    sub = parser.add_subparsers(dest="cmd")
    up = sub.add_parser("usage", help="Print usage / ceiling / remaining for a (resource, period).")
    up.add_argument("resource", help="One of: " + ", ".join(sorted(_RESOURCES)))
    up.add_argument("period", help="Partition key (UTC date '2026-06-08' or a constant 'total').")
    up.add_argument(
        "--workspace",
        default=None,
        help="Workspace root; persisted to ~/.config/pseo/config.json (pass once).",
    )
    return parser


def _cmd_usage(resource: str, period: str, workspace: str | None) -> int:
    if resource not in _RESOURCES:
        print(f"error: unknown resource {resource!r}. valid: "
              f"{', '.join(sorted(_RESOURCES))}", file=sys.stderr)
        return 4
    if workspace:
        ws: Path | None = Path(os.path.expanduser(workspace))
        session_binding.persist_workspace_root(ws)
    else:
        ws = session_binding.resolve_workspace_root()
    if ws is None:
        print("error: no workspace root — pass --workspace <path> once to persist it "
              "(or set $PSEO_WORKSPACE_ROOT)", file=sys.stderr)
        return 2
    try:
        used = usage(ws, resource=resource, period=period)
    except CostLedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    ceiling = read_ceiling(ws, resource)
    remaining = None if ceiling is None else ceiling - used
    print(f"usage: {used}")
    print(f"ceiling: {ceiling if ceiling is not None else 'unset'}")
    print(f"remaining: {remaining if remaining is not None else 'unset'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "usage":
        return _cmd_usage(args.resource, args.period, args.workspace)
    parser.print_help(sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__: Iterable[str] = (
    "GENESIS_HASH",
    "CostLedgerError",
    "CostValidationError",
    "CostCeilingExceeded",
    "canonical_json",
    "compute_entry_hash",
    "cost_ledger_path",
    "read_entries",
    "verify_chain",
    "usage",
    "read_ceiling",
    "reserve",
    "confirm",
    "release",
    "main",
)


if __name__ == "__main__":
    sys.exit(main())
