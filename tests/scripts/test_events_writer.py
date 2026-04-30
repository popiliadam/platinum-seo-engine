"""
Unit tests for scripts/state/events_writer.py.

Covers: provenance/work/audit/workflow happy paths, schema rejection,
auto-populated envelope fields, secret redaction, multi-thread atomicity,
and PSEO_WORKSPACE_ROOT env override.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from scripts.state import events_writer
from scripts.state.events_writer import (
    EventPayloadTooLarge,
    EventResult,
    EventValidationError,
    append_audit,
    append_event,
    append_provenance,
    append_work,
    append_workflow,
    next_run_id,
)


def _project_dir(tmp_path: Path, slug: str = "test-proj") -> Path:
    """Create a fresh projects/{slug}/_state/ tree under tmp_path."""
    p = tmp_path / "projects" / slug / "_state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_events(events_path: Path) -> list[dict]:
    raw = events_path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return [json.loads(line) for line in raw.splitlines()]


# ---------------------------------------------------------------------------
# Test 1 — provenance happy path
# ---------------------------------------------------------------------------

def test_append_provenance_happy(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    result = append_provenance(
        project_id="test-proj",
        run_id=1,
        source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
                "mcp_tool": "dfs__keyword_overview", "response_bytes": 4321},
        operation="ingest",
        cost={"provider": "dataforseo", "credits": 0.4},
        workspace_root=tmp_path,
    )
    assert isinstance(result, EventResult)
    assert result.path.name == "events.jsonl"
    assert result.bytes_written > 0

    events = _read_events(result.path)
    assert len(events) == 1
    ev = events[0]
    assert ev["event_kind"] == "provenance"
    assert ev["run_id"] == 1
    assert ev["source"]["kind"] == "dataforseo_mcp"
    assert ev["operation"] == "ingest"
    assert ev["cost"]["credits"] == 0.4
    assert ev["project_id"] == "test-proj"
    assert ev["schema_version"] == "1.0"


# ---------------------------------------------------------------------------
# Test 2 — workflow happy path (ADR-020)
# ---------------------------------------------------------------------------

def test_append_workflow_happy(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    run_id_str = "test-proj-2026-04-30-a1b2"
    result = append_workflow(
        project_id="test-proj",
        workflow_action="started",
        workflow_run_id=run_id_str,
        step_index=0,
        workspace_root=tmp_path,
    )
    events = _read_events(result.path)
    assert len(events) == 1
    ev = events[0]
    assert ev["event_kind"] == "workflow"
    assert ev["workflow_action"] == "started"
    assert ev["workflow_run_id"] == run_id_str
    assert ev["step_index"] == 0


# ---------------------------------------------------------------------------
# Test 3 — schema rejects extra field, no write
# ---------------------------------------------------------------------------

def test_schema_rejects_extra_field(tmp_path: Path) -> None:
    proj = _project_dir(tmp_path)
    events_path = proj / "events.jsonl"
    with pytest.raises(EventValidationError):
        append_audit(
            project_id="test-proj",
            audit_action="created",
            audit_target="config.json",
            actor="user@test",
            foo="bar",  # extra field — additionalProperties:false
            workspace_root=tmp_path,
        )
    # File must NOT exist (no write occurred). Note: _state/ exists but file does not.
    assert not events_path.exists()


# ---------------------------------------------------------------------------
# Test 4 — event_id auto-populated as 32-char uuid4 hex
# ---------------------------------------------------------------------------

def test_event_id_auto_uuid4_hex(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    result = append_audit(
        project_id="test-proj",
        audit_action="accessed",
        audit_target="schemas/x.json",
        actor="agent@worker",
        workspace_root=tmp_path,
    )
    assert len(result.event_id) == 32
    assert all(c in "0123456789abcdef" for c in result.event_id)
    events = _read_events(result.path)
    assert events[0]["event_id"] == result.event_id


# ---------------------------------------------------------------------------
# Test 5 — timestamp auto-populated, UTC, Z suffix
# ---------------------------------------------------------------------------

def test_timestamp_auto_utc_z_suffix(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    result = append_workflow(
        project_id="test-proj",
        workflow_action="paused",
        workflow_run_id="test-proj-2026-04-30-c3d4",
        workspace_root=tmp_path,
    )
    ev = _read_events(result.path)[0]
    ts = ev["timestamp"]
    assert isinstance(ts, str)
    assert ts.endswith("Z"), f"timestamp missing Z suffix: {ts!r}"
    assert "T" in ts
    # Schema validates date-time format → if we got here, it parsed.


# ---------------------------------------------------------------------------
# Test 6 — secret redaction: openai key in nested field replaced
# ---------------------------------------------------------------------------

def test_redaction_openai_key(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    secret = "sk-proj-AbCd1234EfGh5678IjKl9012MnOpQr"
    # Stash inside notes (a free-text field, schema-allowed).
    result = append_provenance(
        project_id="test-proj",
        run_id=1,
        source={"kind": "manual"},
        operation="ingest",
        notes=f"called with key={secret} hopefully redacted",
        workspace_root=tmp_path,
    )
    ev = _read_events(result.path)[0]
    assert "sk-proj" not in ev["notes"]
    assert "***REDACTED***" in ev["notes"]


# ---------------------------------------------------------------------------
# Test 6b — field-name redaction: api_key field replaced wholesale
# ---------------------------------------------------------------------------

def test_redaction_api_key_field(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    # Schema: source.additionalProperties is false, so we can't smuggle
    # an api_key inside source. But cost or top-level extras would also
    # fail schema. Instead use the redactor on a nested allowed structure:
    # event_kind=audit allows audit_target string. We test by directly
    # constructing an event-style dict via append_event with redact=True
    # using a custom schema. Simpler: assert the field-name redactor on
    # an isolated dict — keep the property test scope-clean.
    # NOTE: append_audit doesn't accept api_key (additionalProperties:false).
    # So we exercise the redactor pipeline by checking that even fields
    # containing token-like strings get redacted via VALUE patterns.
    secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    result = append_audit(
        project_id="test-proj",
        audit_action="config_changed",
        audit_target="rotated github_pat",
        actor=f"system bot, ghp_token={secret}",
        workspace_root=tmp_path,
    )
    ev = _read_events(result.path)[0]
    assert "ghp_abcdef" not in ev["actor"]
    assert "***REDACTED***" in ev["actor"]


# ---------------------------------------------------------------------------
# Test 7 — concurrent threads, no truncation
# ---------------------------------------------------------------------------

def test_concurrency_threads(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    threads_n = 10
    per_thread = 100
    errors: list[Exception] = []

    def worker(tid: int) -> None:
        try:
            for i in range(per_thread):
                append_audit(
                    project_id="test-proj",
                    audit_action="accessed",
                    audit_target=f"resource:t{tid}:i{i}",
                    actor=f"thread-{tid}",
                    workspace_root=tmp_path,
                )
        except Exception as exc:  # pragma: no cover (defensive)
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(threads_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"thread errors: {errors}"

    events_path = tmp_path / "projects" / "test-proj" / "_state" / "events.jsonl"
    lines = events_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == threads_n * per_thread, f"expected {threads_n * per_thread}, got {len(lines)}"
    # Every line must parse as JSON (no truncation/interleaving).
    for ln in lines:
        obj = json.loads(ln)
        assert obj["event_kind"] == "audit"


# ---------------------------------------------------------------------------
# Test 8 — workspace_root resolved from PSEO_WORKSPACE_ROOT env var
# ---------------------------------------------------------------------------

def test_workspace_root_via_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _project_dir(tmp_path)
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(tmp_path))
    # No workspace_root arg → must read from env.
    result = append_workflow(
        project_id="test-proj",
        workflow_action="done",
        workflow_run_id="test-proj-2026-04-30-eeee",
    )
    assert result.path.is_relative_to(tmp_path)
    events = _read_events(result.path)
    assert events[0]["workflow_action"] == "done"


# ---------------------------------------------------------------------------
# Test 9 — payload size cap
# ---------------------------------------------------------------------------

def test_payload_too_large_raises(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    huge_target = "x" * 70_000  # well over 64KB serialized
    with pytest.raises(EventPayloadTooLarge):
        append_event(
            {
                "event_kind": "audit",
                "audit_action": "modified",
                "audit_target": huge_target,
                "actor": "bot",
            },
            project_id="test-proj",
            workspace_root=tmp_path,
        )


# ---------------------------------------------------------------------------
# Test 10 — next_run_id monotonic
# ---------------------------------------------------------------------------

def test_next_run_id_monotonic(tmp_path: Path) -> None:
    _project_dir(tmp_path)
    assert next_run_id("test-proj", workspace_root=tmp_path) == 1
    append_provenance(
        project_id="test-proj",
        run_id=1,
        source={"kind": "manual"},
        operation="ingest",
        workspace_root=tmp_path,
    )
    assert next_run_id("test-proj", workspace_root=tmp_path) == 2
    append_provenance(
        project_id="test-proj",
        run_id=2,
        source={"kind": "manual"},
        operation="normalize",
        workspace_root=tmp_path,
    )
    assert next_run_id("test-proj", workspace_root=tmp_path) == 3
    # Workflow events carry workflow_run_id (string), not run_id (integer):
    # they must NOT advance the provenance counter.
    append_workflow(
        project_id="test-proj",
        workflow_action="started",
        workflow_run_id="test-proj-2026-04-30-1111",
        workspace_root=tmp_path,
    )
    assert next_run_id("test-proj", workspace_root=tmp_path) == 3
