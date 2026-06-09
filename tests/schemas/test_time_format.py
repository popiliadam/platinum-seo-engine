"""tests/schemas/test_time_format.py — UTC time-discipline enforcement (§8.10).

rules/time-discipline.md:59 claims THIS file runs each PR and locks the storage
timestamp contract — but it did not exist (hostile-audit finding #18), so the
contract was unenforced. This file is that missing enforcement, and it doubles
as the regression test for finding #5.

Two layers are locked here:

  1. The generic ``format: date-time`` checker in
     ``scripts/validation/validate_schema.py`` (exercised through
     ``build_validator`` — the EXACT factory the CLI + drift-check use) must
     accept ONLY canonical UTC ``…Z`` timestamps and REJECT naive (tz-less),
     non-UTC-offset, and garbage values — verified against EVERY
     timestamp-bearing schema in ``schemas/`` (generic, not schema-specific).

  2. ``scripts/state/events_writer.py`` routes its validation through that same
     strict checker (finding #4), so a caller-supplied bad ``timestamp`` is
     rejected BEFORE the append ever touches ``events.jsonl`` — while the
     auto-populated ``…Z`` default keeps working.

Canonical form per the rule is ``…Z`` (UTC). ``+00:00`` is the same instant but
is NOT the rule's canonical storage form (every example + the rule's regex use a
literal ``Z``), so it is rejected too. Microseconds ARE allowed because
``events_writer._utc_iso_z()`` emits ``…S.%fZ``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.state.events_writer import (
    EventValidationError,
    append_provenance,
)
from scripts.validation.validate_schema import build_validator

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMAS_DIR = _REPO_ROOT / "schemas"

# --- sample timestamps ------------------------------------------------------
# Canonical UTC `…Z` — the only storage form the rule permits. Microsecond and
# millisecond fractional parts are allowed (events_writer emits microseconds).
_GOOD_UTC_Z = (
    "2026-06-06T10:00:00Z",          # second precision (rule example form)
    "2026-06-06T10:00:00.000Z",      # millisecond fractional + Z
    "2026-06-06T10:00:00.123456Z",   # microsecond + Z (events_writer _utc_iso_z)
)
# Each violates rules/time-discipline.md and currently slips through because the
# checker only ran `datetime.fromisoformat(value.replace("Z","+00:00"))`.
_BAD_NON_UTC = (
    "2026-06-06T10:00:00",           # NAIVE — no tz, ambiguous across regions
    "2026-06-06T10:00:00+03:00",     # Europe/Istanbul local offset — drift risk
    "2026-06-06T10:00:00+00:00",     # UTC instant but NON-canonical (rule wants …Z)
    "not-a-date",                    # garbage
    "30 Nisan 2026, 15:34",          # display-layer string — rule anti-pattern
)

_DATETIME_FIELD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {"ts": {"type": "string", "format": "date-time"}},
}


def _dt_format_errors(validator, doc, pointer):
    """date-time format errors raised at exactly `pointer` for `doc`."""
    return [
        e
        for e in validator.iter_errors(doc)
        if e.validator == "format"
        and e.validator_value == "date-time"
        and tuple(e.absolute_path) == tuple(pointer)
    ]


def _synthetic_dt_errors(value):
    validator = build_validator(_DATETIME_FIELD_SCHEMA)
    return _dt_format_errors(validator, {"ts": value}, ("ts",))


# ---------------------------------------------------------------------------
# Layer 1a — the generic checker contract (the focused finding #5 lock)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", _GOOD_UTC_Z)
def test_strict_checker_accepts_canonical_utc(value):
    assert not _synthetic_dt_errors(value), f"canonical UTC {value!r} must validate"


@pytest.mark.parametrize("value", _BAD_NON_UTC)
def test_strict_checker_rejects_non_utc(value):
    assert _synthetic_dt_errors(value), (
        f"non-canonical timestamp {value!r} must be rejected by format:date-time"
    )


# ---------------------------------------------------------------------------
# Layer 1b — EVERY timestamp-bearing schema enforces it (finding #18 breadth)
# ---------------------------------------------------------------------------

def _walk_date_time_pointers(node, prefix=()):
    """Yield key-paths to every ``format: date-time`` field reachable via the
    ``properties`` / ``items`` backbone of a JSON Schema. Array steps are the
    integer 0 (matching jsonschema's ``absolute_path``)."""
    if not isinstance(node, dict):
        return
    if node.get("format") == "date-time":
        yield prefix
    for name, sub in (node.get("properties") or {}).items():
        yield from _walk_date_time_pointers(sub, prefix + (name,))
    items = node.get("items")
    if isinstance(items, dict):
        yield from _walk_date_time_pointers(items, prefix + (0,))


def _timestamp_bearing_schemas():
    out = []
    for path in sorted(_SCHEMAS_DIR.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        for pointer in _walk_date_time_pointers(schema):
            out.append((path.name, schema, pointer))
    return out


_TS_SCHEMA_FIELDS = _timestamp_bearing_schemas()


def _build_doc(pointer, value):
    """Minimal nested dict/list so `pointer` resolves to `value` (built inside-out)."""
    node = value
    for step in reversed(pointer):
        node = [node] if isinstance(step, int) else {step: node}
    return node


def test_repo_declares_timestamp_bearing_schemas():
    # Finding #18 sanity: the contract is vacuous if nothing declares date-time.
    assert _TS_SCHEMA_FIELDS, "expected schemas/ to declare format:date-time fields"


@pytest.mark.parametrize(
    "name,schema,pointer",
    _TS_SCHEMA_FIELDS,
    ids=[f"{n}:{'.'.join(map(str, p))}" for (n, _s, p) in _TS_SCHEMA_FIELDS],
)
def test_every_schema_datetime_field_enforces_utc(name, schema, pointer):
    validator = build_validator(schema)
    # Naive value at this exact field is rejected (date-time format error here).
    naive_doc = _build_doc(pointer, "2026-06-06T10:00:00")
    assert _dt_format_errors(validator, naive_doc, pointer), (
        f"{name} field {'.'.join(map(str, pointer))}: naive ts must be rejected"
    )
    # Canonical …Z passes the date-time format check (other unrelated errors OK).
    z_doc = _build_doc(pointer, "2026-06-06T10:00:00Z")
    assert not _dt_format_errors(validator, z_doc, pointer), (
        f"{name} field {'.'.join(map(str, pointer))}: canonical …Z must pass"
    )


# ---------------------------------------------------------------------------
# Layer 2 — events_writer rejects a bad caller timestamp BEFORE append (#4)
# ---------------------------------------------------------------------------

def _provenance_kwargs(tmp_path):
    return dict(
        project_id="test-proj",
        run_id=1,  # explicit -> non-allocating path: validation precedes file open
        source={"kind": "manual"},
        operation="ingest",
        workspace_root=tmp_path,
    )


def _events_path(tmp_path):
    return tmp_path / "projects" / "test-proj" / "_state" / "events.jsonl"


@pytest.mark.parametrize(
    "bad_ts",
    [
        "not-a-date",
        "2026-06-06T10:00:00",        # naive
        "2026-06-06T10:00:00+03:00",  # local offset
    ],
)
def test_events_writer_rejects_bad_caller_timestamp(tmp_path, bad_ts):
    with pytest.raises(EventValidationError):
        append_provenance(timestamp=bad_ts, **_provenance_kwargs(tmp_path))
    # Rejected BEFORE the append: events.jsonl never created (or stays empty).
    path = _events_path(tmp_path)
    assert not path.exists() or path.read_text(encoding="utf-8").strip() == "", (
        f"bad timestamp {bad_ts!r} must not be persisted"
    )


def test_events_writer_default_timestamp_still_appends(tmp_path):
    # No caller timestamp -> auto-populated canonical …Z must still pass + append.
    result = append_provenance(**_provenance_kwargs(tmp_path))
    lines = _events_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["timestamp"].endswith("Z"), "auto timestamp must be canonical UTC …Z"
    assert result.bytes_written > 0
