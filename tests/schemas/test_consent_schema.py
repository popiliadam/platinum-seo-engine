"""Instance-validation lock for schemas/consent.schema.json (AMO batch 2a).

The consent entry is ONE line of projects/{slug}/_state/consent.jsonl — the
append-only, hash-chained ledger recording operator consent for an
irreversible/outward action. The recorder (scripts/state/consent_ledger.py,
batch 2a) appends one entry per `/pseo-approve`; the PreToolUse outward-action
gate (batch 2b) hashes a pending action's concrete target and calls
has_consent(run_id, action, target_hash) before allowing it.

This test FREEZES the contract batches 2b key on literally: the required[] set,
the 6-value `action` enum, and the ^[a-f0-9]{64}$ hash patterns
(target_hash / prev_hash / entry_hash) + additionalProperties:false.

Mirrors tests/schemas/test_coverage_schema.py's Draft7Validator usage.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
CONSENT_SCHEMA_PATH = ROOT / "schemas" / "consent.schema.json"


def _errors(instance: dict) -> list:
    """Return the (possibly empty) list of Draft7 validation errors."""
    schema = json.loads(CONSENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    return list(jsonschema.Draft7Validator(schema).iter_errors(instance))


# A fully-populated, valid genesis entry. Each invalid case below is this dict
# with exactly ONE defect so the single failure is isolated.
_VALID = {
    "schema_version": "1.0",
    "seq": 0,
    "run_id": "demo-furniture-2026-06-06-ab12",
    "action": "index_update",
    "target": "https://demo-furniture.example/sitemap.xml",
    "target_hash": "a" * 64,
    "granted_at": "2026-06-06T10:00:00",
    "granted_by": "operator",
    "session_id": "abcd-1234",
    "note": "approved during monthly run",
    "prev_hash": "0" * 64,
    "entry_hash": "b" * 64,
}


# ---------------------------------------------------------------------------
# Valid case
# ---------------------------------------------------------------------------

def test_fully_populated_valid_entry_validates() -> None:
    """A complete genesis entry (seq 0, prev_hash 64 zeros, 64-hex target_hash +
    entry_hash, action 'index_update', ISO granted_at, granted_by 'operator')
    validates with ZERO errors."""
    assert _errors(_VALID) == []


# ---------------------------------------------------------------------------
# Invalid cases
# ---------------------------------------------------------------------------

def test_action_not_in_enum_rejected() -> None:
    """action is a closed 6-value enum; 'publish' is not a gated class — batch
    2b maps each gate matcher onto exactly one of the 6 values."""
    bad = {**_VALID, "action": "publish"}
    assert _errors(bad) != []


def test_bad_target_hash_rejected() -> None:
    """target_hash must match ^[a-f0-9]{64}$ — the gate looks consent up by this
    key, so a non-sha256 value 'xyz' must be rejected."""
    bad = {**_VALID, "target_hash": "xyz"}
    assert _errors(bad) != []


def test_missing_entry_hash_rejected() -> None:
    """entry_hash is REQUIRED (tamper-evidence anchor) — an entry without it is
    invalid."""
    bad = {k: v for k, v in _VALID.items() if k != "entry_hash"}
    assert _errors(bad) != []


def test_unknown_extra_key_rejected() -> None:
    """additionalProperties:false — an undeclared top-level key must be rejected
    so batch 2b can trust the frozen shape."""
    bad = {**_VALID, "surprise": "nope"}
    assert _errors(bad) != []
