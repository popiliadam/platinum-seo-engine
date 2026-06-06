#!/usr/bin/env python3
"""consent_ledger.py — append-only, hash-chained operator-consent recorder (AMO 2a).

Records operator consent for an irreversible / outward AMO action in an
append-only, tamper-evident ledger:

    {workspace_root}/projects/{slug}/_state/consent.jsonl

Each line is ONE consent entry (schemas/consent.schema.json). The ledger is
HASH-CHAINED: every entry carries the prior entry's hash (prev_hash) plus its
own entry_hash = sha256(canonical_json(entry WITHOUT entry_hash)). prev_hash is
one of the hashed fields, so the chain link is bound into entry_hash — a forged,
rewritten, or reordered line breaks the chain and verify_chain rejects it.

Discipline (rules/append-only-state.md — the events.jsonl discipline, NOT a
marker file):
  - Atomic append: os.open(O_WRONLY|O_CREAT|O_APPEND) + fcntl.flock(LOCK_EX) +
    a single os.write + os.fsync. The file's tail is read UNDER the same flock
    that guards the append (mirrors events_writer._atomic_append_allocating_run_id),
    so two concurrent appenders derive distinct seq/prev_hash and chain correctly.
  - NEVER os.replace / tempfile-rename — that inode-swaps an append-only log and
    loses concurrent writers' data. os.replace is for MUTABLE markers
    (session_binding._atomic_write_json, coverage.py); this is an append-only LOG.
  - Validation BEFORE the write: jsonschema Draft7Validator against
    schemas/consent.schema.json. A defective entry raises and DOES NOT touch the
    file.

This module is purely ADDITIVE — it imports session_binding only to resolve the
CLI's workspace/slug; it never imports or alters events_writer / coverage.

Public API:
    target_hash(target) -> str
    canonical_json(obj) -> str
    compute_entry_hash(entry_without_entry_hash) -> str
    consent_path(workspace_root, project_slug) -> Path
    read_entries(workspace_root, project_slug) -> list[dict]
    verify_chain(entries) -> tuple[bool, int | None]
    append_consent(*, workspace_root, project_slug, run_id, action, target,
                   granted_by, now_iso, session_id=None, note=None,
                   schema_path=None) -> dict
    has_consent(workspace_root, project_slug, *, run_id, action, target_hash) -> bool

CLI (mirrors session_binding's argparse main):
    python3 -m scripts.state.consent_ledger approve <run_id> <action> <target>
            [--granted-by X] [--note "..."] [--workspace <path>]

The PreToolUse outward-action gate (batch 2b) keys on this contract literally:
the required[] set, the 6-value action enum, the ^[a-f0-9]{64}$ hash patterns,
and the entry_hash / verify_chain rules above.
"""

from __future__ import annotations

import argparse
import fcntl
import functools
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError

from scripts.state import session_binding

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = "1.0"
GENESIS_HASH = "0" * 64  # prev_hash of the genesis (seq 0) line

# Module dir: <repo>/scripts/state/consent_ledger.py -> repo = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "consent.schema.json"

# The 6 gated outward-action classes (must mirror consent.schema.json action enum).
# Defensive validation in append_consent rejects anything outside this set.
_ACTIONS: frozenset[str] = frozenset({
    "git_push",
    "fs_delete",
    "net_post",
    "mcp_submit",
    "index_update",
    "dfs_oversized",
})

# Slug grammar — matches project-config.schema.json / events_writer._SLUG_RE.
_SLUG_RE = re.compile(r"[a-z][a-z0-9-]*")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConsentLedgerError(Exception):
    """Base class for all consent_ledger errors."""


class ConsentValidationError(ConsentLedgerError):
    """Raised when a consent entry fails consent.schema.json validation."""


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def canonical_json(obj: dict) -> str:
    """Deterministic JSON encoding used for hashing AND the on-disk line.

    sort_keys makes the byte sequence independent of insertion order; the
    compact separators + ensure_ascii=False keep it minimal UTF-8. The gate
    (batch 2b) recomputes entry_hash over THIS exact encoding, so it must never
    drift.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def target_hash(target: str) -> str:
    """sha256 hex of the canonical target string (UTF-8).

    The single hashing function shared by the writer and the batch-2b gate — the
    gate hashes a pending action's concrete target with THIS function and looks
    the result up, so writer and gate hash identically.
    """
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


def compute_entry_hash(entry_without_entry_hash: dict) -> str:
    """sha256 hex over canonical_json of the entry with entry_hash REMOVED.

    Builds a NEW dict (no mutation of the caller's entry) excluding the
    entry_hash key, then hashes its canonical encoding. prev_hash IS one of the
    hashed fields, so the chain link is bound into entry_hash.
    """
    payload = {k: v for k, v in entry_without_entry_hash.items() if k != "entry_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Paths + validation
# ---------------------------------------------------------------------------

def consent_path(workspace_root: Path | str, project_slug: str) -> Path:
    """Build {ws}/projects/{slug}/_state/consent.jsonl (mkdir -p the _state dir).

    Validates the slug against ^[a-z][a-z0-9-]*$ before any mkdir so a bad
    marker / typo cannot create a ghost project tree and an id with '..' or '/'
    cannot escape projects/ (mirrors events_writer._events_path).
    """
    if not isinstance(project_slug, str) or not _SLUG_RE.fullmatch(project_slug):
        raise ConsentLedgerError(
            f"project_slug must match ^[a-z][a-z0-9-]*$ (got {project_slug!r})"
        )
    state_dir = Path(workspace_root) / "projects" / project_slug / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "consent.jsonl"


@functools.lru_cache(maxsize=4)
def _get_validator(schema_path: str) -> Draft7Validator:
    """Cache one Draft7Validator per schema path (lru_cache hashes the str key)."""
    with Path(schema_path).open("r", encoding="utf-8") as fh:
        return Draft7Validator(json.load(fh))


def _validate_entry(entry: dict, schema_path: Path | None = None) -> None:
    """Draft7 validation. Raises ConsentValidationError aggregating all errors."""
    try:
        validator = _get_validator(str(schema_path or _SCHEMA_PATH))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConsentValidationError(f"failed to load consent schema: {exc}") from exc
    errors: list[_JSValidationError] = sorted(
        validator.iter_errors(entry), key=lambda e: list(e.path)
    )
    if errors:
        msgs = []
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            msgs.append(f"{loc}: {err.message}")
        raise ConsentValidationError("; ".join(msgs))


# ---------------------------------------------------------------------------
# Read + verify
# ---------------------------------------------------------------------------

def _read_last_entry(path: Path) -> dict | None:
    """Return the last non-blank JSON entry, or None for a missing/empty file.

    Called UNDER the append flock to learn the prior (seq, entry_hash). Raises
    ConsentLedgerError on a corrupt tail line (the chain cannot be extended over
    unparseable data).
    """
    if not path.exists():
        return None
    last: str | None = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last = stripped
    if last is None:
        return None
    try:
        obj = json.loads(last)
    except json.JSONDecodeError as exc:
        raise ConsentLedgerError(f"corrupt consent ledger tail in {path}: {exc}") from exc
    return obj if isinstance(obj, dict) else None


def read_entries(workspace_root: Path | str, project_slug: str) -> list[dict]:
    """Parse every non-blank line of consent.jsonl into a list of dicts.

    A missing file returns [] (never raises). An existing-but-corrupt line
    raises ConsentLedgerError.
    """
    path = consent_path(workspace_root, project_slug)
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
                raise ConsentLedgerError(
                    f"corrupt JSON at line {lineno} in {path}: {exc}"
                ) from exc
    return entries


def verify_chain(entries: list[dict]) -> tuple[bool, int | None]:
    """Re-walk the hash chain. Returns (True, None) if intact, else (False, idx).

    For each entry i (in order):
      * seq must equal i (monotonic, +1 each line),
      * prev_hash must equal GENESIS_HASH (i==0) or entries[i-1].entry_hash,
      * compute_entry_hash(entry) must reproduce entry.entry_hash.
    The first violation returns its index. An empty list is intact.
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


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------

def append_consent(
    *,
    workspace_root: Path | str,
    project_slug: str,
    run_id: str,
    action: str,
    target: str,
    granted_by: str,
    now_iso: str,
    session_id: str | None = None,
    note: str | None = None,
    schema_path: Path | None = None,
) -> dict:
    """Append ONE consent entry under a flock and return it.

    Defensive: action must be one of the 6 enum values (else ValueError, nothing
    written). The whole critical section — read the tail to learn prior
    (seq, entry_hash), build + hash + validate the entry, write it — runs while
    holding fcntl.flock(LOCK_EX), so concurrent appenders chain correctly. Uses
    O_APPEND + a single os.write + os.fsync; NEVER os.replace.
    """
    if action not in _ACTIONS:
        raise ValueError(
            f"unknown action {action!r}; valid: {', '.join(sorted(_ACTIONS))}"
        )

    path = consent_path(workspace_root, project_slug)

    fd = -1
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    except OSError as exc:
        raise ConsentLedgerError(f"cannot open {path}: {exc}") from exc

    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError as exc:
            raise ConsentLedgerError(f"flock failed on {path}: {exc}") from exc
        try:
            # Read the tail UNDER the lock so concurrent appenders never collide.
            last = _read_last_entry(path)
            if last is None:
                seq = 0
                prev_hash = GENESIS_HASH
            else:
                seq = int(last["seq"]) + 1
                prev_hash = last["entry_hash"]

            entry: dict = {
                "schema_version": _SCHEMA_VERSION,
                "seq": seq,
                "run_id": run_id,
                "action": action,
                "target": target,
                "target_hash": target_hash(target),
                "granted_at": now_iso,
                "granted_by": granted_by,
                "prev_hash": prev_hash,
            }
            if session_id is not None:
                entry["session_id"] = session_id
            if note is not None:
                entry["note"] = note
            entry["entry_hash"] = compute_entry_hash(entry)

            # Validate BEFORE writing — a defective entry never touches the file.
            _validate_entry(entry, schema_path)

            payload = (canonical_json(entry) + "\n").encode("utf-8")
            written = os.write(fd, payload)
            if written != len(payload):
                raise ConsentLedgerError(
                    f"short write on {path}: wrote {written} of {len(payload)} bytes"
                )
            os.fsync(fd)
            return entry
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass


def has_consent(
    workspace_root: Path | str,
    project_slug: str,
    *,
    run_id: str,
    action: str,
    target_hash: str,
) -> bool:
    """True iff an INTACT chain holds an entry matching (run_id, action, target_hash).

    A broken chain (tamper) returns False — no consent. The match is EXACT on all
    three keys. (`target_hash` here is the precomputed hex digest the gate passes
    in, not the module-level target_hash() function.)
    """
    entries = read_entries(workspace_root, project_slug)
    intact, _ = verify_chain(entries)
    if not intact:
        return False
    return any(
        e.get("run_id") == run_id
        and e.get("action") == action
        and e.get("target_hash") == target_hash
        for e in entries
    )


def has_session_consent(
    workspace_root: Path | str,
    project_slug: str,
    *,
    session_id: str,
    action: str,
    target_hash: str,
) -> bool:
    """True iff an INTACT chain holds an entry with this session_id + action + target_hash.

    Per-session consent (the operator-chosen model, batch 2b): a consent only
    authorizes within the session that granted it. The 2a `/pseo-approve` writer
    stamps each entry with the granting session_id, so a consent from a DIFFERENT
    session simply does not match here. A broken chain (tamper) returns False —
    fail-closed. Mirrors has_consent but keys on session_id instead of run_id;
    run_id is NOT used (it is audit provenance only). (`target_hash` here is the
    precomputed hex digest the gate passes in, not the module-level
    target_hash() function.)
    """
    entries = read_entries(workspace_root, project_slug)
    intact, _ = verify_chain(entries)
    if not intact:
        return False
    return any(
        e.get("session_id") == session_id
        and e.get("action") == action
        and e.get("target_hash") == target_hash
        for e in entries
    )


# ---------------------------------------------------------------------------
# CLI — `approve` subcommand (mirrors session_binding's argparse main)
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="consent_ledger.py",
        description="Record operator consent for a gated outward action (AMO batch 2a).",
    )
    sub = parser.add_subparsers(dest="cmd")
    ap = sub.add_parser(
        "approve",
        help="Append a hash-chained consent entry for THIS session's bound project.",
    )
    ap.add_argument("run_id", help="Run (or manual token) the consent is scoped to.")
    ap.add_argument(
        "action",
        help="One of: " + ", ".join(sorted(_ACTIONS)),
    )
    ap.add_argument("target", help="Concrete target (URL / path / sitemap / command).")
    ap.add_argument("--granted-by", default="operator", help="Provenance (default: operator).")
    ap.add_argument("--note", default=None, help="Optional free-text operator note.")
    ap.add_argument(
        "--workspace",
        default=None,
        help="Workspace root; persisted to ~/.config/pseo/config.json (pass once).",
    )
    return parser


def _cmd_approve(
    run_id: str,
    action: str,
    target: str,
    granted_by: str,
    note: str | None,
    workspace: str | None,
) -> int:
    # 1. Validate the action up front (friendly error listing the 6 valid values).
    if action not in _ACTIONS:
        print(
            f"error: unknown action {action!r}. valid: {', '.join(sorted(_ACTIONS))}",
            file=sys.stderr,
        )
        return 4
    # 2. Workspace root: explicit --workspace (persist it) else resolve.
    if workspace:
        ws = Path(os.path.expanduser(workspace))
        session_binding.persist_workspace_root(ws)
    else:
        ws = session_binding.resolve_workspace_root()
    if ws is None:
        print(
            "error: no workspace root — pass --workspace <path> once to persist it "
            "(or set $PSEO_WORKSPACE_ROOT)",
            file=sys.stderr,
        )
        return 2
    # 3. Slug bound to THIS session (marker -> shared/active.json -> raise).
    session_id = session_binding.current_session_id()
    try:
        slug = session_binding.resolve_session_project(
            ws, session_id=session_id, strict=True
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    # 4. Append the consent entry.
    try:
        entry = append_consent(
            workspace_root=ws,
            project_slug=slug,
            run_id=run_id,
            action=action,
            target=target,
            granted_by=granted_by,
            now_iso=datetime.now().isoformat(),
            session_id=session_id,
            note=note,
        )
    except (ConsentLedgerError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    shown = target if len(target) <= 48 else target[:48]
    print(f"consent recorded: {action} on {shown} for {run_id}  (seq {entry['seq']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "approve":
        return _cmd_approve(
            args.run_id, args.action, args.target,
            args.granted_by, args.note, args.workspace,
        )
    parser.print_help(sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__: Iterable[str] = (
    "GENESIS_HASH",
    "ConsentLedgerError",
    "ConsentValidationError",
    "canonical_json",
    "target_hash",
    "compute_entry_hash",
    "consent_path",
    "read_entries",
    "verify_chain",
    "append_consent",
    "has_consent",
    "has_session_consent",
    "main",
)


if __name__ == "__main__":
    sys.exit(main())
