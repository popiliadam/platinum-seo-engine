"""
Unit tests for scripts/state/anomaly_recorder.py.

The anomaly recorder is the DURABLE SIDECAR that backs operator decision D-B:
when a state write succeeds but its follow-on audit/event emit into events.jsonl
fails, we keep the write, do NOT hard-block, and record a durable, reconcilable
anomaly into a SEPARATE file (anomalies.jsonl) — never the events.jsonl whose
emit just failed.

Covers: durable append, multi-append accumulation, UTC-'Z' timestamp, state-dir
auto-creation, hard-failure raises AnomalyRecordError, empty-kind guard.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.state import anomaly_recorder
from scripts.state.anomaly_recorder import AnomalyRecordError, AnomalyResult


def _read_lines(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Test 1 — a single record lands as one durable JSON line with all fields
# ---------------------------------------------------------------------------

def test_record_anomaly_writes_durable_jsonl_line(tmp_path: Path) -> None:
    state_dir = tmp_path / "projects" / "demo" / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)

    result = anomaly_recorder.record_anomaly(
        state_dir,
        kind="provenance_emit_failed",
        detail={"sheet": "quick_wins", "rows_written": 3},
        error="EventValidationError: boom",
    )

    assert isinstance(result, AnomalyResult)
    path = state_dir / "anomalies.jsonl"
    assert result.path == path
    assert path.exists()
    assert result.bytes_written > 0

    lines = _read_lines(path)
    assert len(lines) == 1
    rec = lines[0]
    assert rec["kind"] == "provenance_emit_failed"
    assert rec["detail"] == {"sheet": "quick_wins", "rows_written": 3}
    assert rec["error"] == "EventValidationError: boom"
    assert "timestamp" in rec


# ---------------------------------------------------------------------------
# Test 2 — append-only: a second record adds a line, never truncates the first
# ---------------------------------------------------------------------------

def test_record_anomaly_appends_not_truncates(tmp_path: Path) -> None:
    state_dir = tmp_path / "_state"
    anomaly_recorder.record_anomaly(state_dir, kind="provenance_emit_failed",
                                    detail={"n": 1})
    anomaly_recorder.record_anomaly(state_dir, kind="workflow_event_emit_failed",
                                    detail={"n": 2})

    lines = _read_lines(state_dir / "anomalies.jsonl")
    assert len(lines) == 2
    assert [rec["kind"] for rec in lines] == [
        "provenance_emit_failed",
        "workflow_event_emit_failed",
    ]


# ---------------------------------------------------------------------------
# Test 3 — timestamp is UTC with a 'Z' suffix (rules/time-discipline.md §8.10)
# ---------------------------------------------------------------------------

def test_record_anomaly_timestamp_is_utc_z(tmp_path: Path) -> None:
    state_dir = tmp_path / "_state"
    anomaly_recorder.record_anomaly(state_dir, kind="provenance_emit_failed")

    rec = _read_lines(state_dir / "anomalies.jsonl")[0]
    ts = rec["timestamp"]
    assert ts.endswith("Z")
    # Parses as an aware UTC instant.
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.utcoffset().total_seconds() == 0


# ---------------------------------------------------------------------------
# Test 4 — the _state dir is created if missing (robust fallback path)
# ---------------------------------------------------------------------------

def test_record_anomaly_creates_state_dir_if_missing(tmp_path: Path) -> None:
    state_dir = tmp_path / "projects" / "demo" / "_state"  # does NOT exist yet
    assert not state_dir.exists()

    anomaly_recorder.record_anomaly(state_dir, kind="provenance_emit_failed")

    assert (state_dir / "anomalies.jsonl").exists()


# ---------------------------------------------------------------------------
# Test 5 — error is omitted from the record when not supplied
# ---------------------------------------------------------------------------

def test_record_anomaly_omits_error_when_absent(tmp_path: Path) -> None:
    state_dir = tmp_path / "_state"
    anomaly_recorder.record_anomaly(state_dir, kind="provenance_emit_failed",
                                    detail={"sheet": "schema"})

    rec = _read_lines(state_dir / "anomalies.jsonl")[0]
    assert "error" not in rec
    assert rec["detail"] == {"sheet": "schema"}


# ---------------------------------------------------------------------------
# Test 6 — a hard write failure raises AnomalyRecordError (testable contract)
# ---------------------------------------------------------------------------

def test_record_anomaly_raises_when_dir_unwritable(tmp_path: Path) -> None:
    # A regular FILE stands where the parent dir would be → mkdir(parents=True)
    # raises NotADirectoryError (an OSError) which the recorder surfaces.
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a dir", encoding="utf-8")
    state_dir = blocker / "_state"

    with pytest.raises(AnomalyRecordError):
        anomaly_recorder.record_anomaly(state_dir, kind="provenance_emit_failed")


# ---------------------------------------------------------------------------
# Test 7 — empty / non-string kind is rejected (records must be classifiable)
# ---------------------------------------------------------------------------

def test_record_anomaly_rejects_empty_kind(tmp_path: Path) -> None:
    state_dir = tmp_path / "_state"
    with pytest.raises(AnomalyRecordError):
        anomaly_recorder.record_anomaly(state_dir, kind="")
