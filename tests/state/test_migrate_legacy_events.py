"""tests/state/test_migrate_legacy_events.py — direct tests for
``scripts/state/migrate_legacy_events.py`` (ADR-031 events.jsonl
strict + legacy partition).

Coverage (D-01 v1.5-Phase-2 Tier 2):
  Pure ``_classify_lines``:
    1. Strict + legacy rows partition correctly.
    2. JSON decode errors land in fail records (not pass).
    3. Empty / blank lines are skipped.
  ``migrate()`` end-to-end (tmp_path workspace):
    4. Strict-only events.jsonl is a no-op (exit 0, no archive write).
    5. Mixed events.jsonl produces strict + legacy + audit report.
    6. ``dry_run=True`` prints fail records without writing files.
    7. Existing legacy file gets new fail rows appended (append-only).
    8. Missing events.jsonl returns exit 2.
    9. Audit report markdown structure (header + table rows).

Fixture: synthetic ``events.schema.json``-conformant provenance events
(see ``_strict_provenance_event``); legacy fixture deliberately omits
``event_kind=audit`` allOf required fields (``audit_action`` +
``audit_target``) per Lesson 68 audit-event schema authority pattern.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATE_PATH = REPO / "scripts" / "state" / "migrate_legacy_events.py"


@pytest.fixture(scope="module")
def migrate_module():
    spec = importlib.util.spec_from_file_location("migrate_legacy_events", MIGRATE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Module under test is also importable as a script; both work.
    sys.modules["migrate_legacy_events"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Synthetic event factories
# ---------------------------------------------------------------------------

def _strict_provenance_event(event_id: str = "strict1") -> dict:
    """events.schema.json-conformant provenance event (top-level required +
    allOf branch required: run_id, source, operation; ``operation`` is an
    enum 6-value: ingest/normalize/project_excel/validate/cascade_done/staging)."""
    return {
        "schema_version": "1.0",
        "event_kind": "provenance",
        "event_id": event_id,
        "timestamp": "2026-05-07T12:00:00Z",
        "project_id": "test-proj",
        "run_id": 1,
        "source": {
            "kind": "tool_computed",
            "row_count": 1,
            "response_bytes": 100,
        },
        "operation": "cascade_done",
    }


def _legacy_audit_missing_action(event_id: str = "legacy1") -> dict:
    """audit event missing ``audit_action`` + ``audit_target`` (allOf
    branch required) — schema FAIL by design (Lesson 68 paterni)."""
    return {
        "schema_version": "1.0",
        "event_kind": "audit",
        "event_id": event_id,
        "timestamp": "2026-05-07T12:00:00Z",
        "project_id": "test-proj",
    }


def _legacy_top_level_missing(event_id: str = "legacy2") -> dict:
    """Top-level required field missing (no ``timestamp``)."""
    return {
        "schema_version": "1.0",
        "event_kind": "audit",
        "event_id": event_id,
        "project_id": "test-proj",
    }


# ---------------------------------------------------------------------------
# Workspace fixture
# ---------------------------------------------------------------------------

def _seed_events(tmp_path: Path, events: list[dict | str], project: str = "test-proj") -> Path:
    """Create ``tmp_path/workspace/projects/<project>/_state/events.jsonl``
    with one event per line. ``str`` items are written verbatim (used for
    json-decode-error fixtures)."""
    ws = tmp_path / "workspace"
    state_dir = ws / "projects" / project / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    events_path = state_dir / "events.jsonl"
    lines: list[str] = []
    for ev in events:
        if isinstance(ev, str):
            lines.append(ev)
        else:
            lines.append(json.dumps(ev))
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ws


# ---------------------------------------------------------------------------
# _classify_lines pure-function tests
# ---------------------------------------------------------------------------

def test_classify_separates_pass_and_fail(tmp_path, migrate_module) -> None:
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
        _strict_provenance_event("ev-s2"),
    ])
    events_path = ws / "projects" / "test-proj" / "_state" / "events.jsonl"
    validator = migrate_module._load_schema()
    pass_lines, fail_records = migrate_module._classify_lines(events_path, validator)
    assert len(pass_lines) == 2
    assert len(fail_records) == 1
    assert fail_records[0][0] == 2  # line number 2
    assert "audit_action" in fail_records[0][2] or "audit_target" in fail_records[0][2]


def test_classify_handles_json_decode_error(tmp_path, migrate_module) -> None:
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        "{ this is not json",
        _strict_provenance_event("ev-s2"),
    ])
    events_path = ws / "projects" / "test-proj" / "_state" / "events.jsonl"
    validator = migrate_module._load_schema()
    pass_lines, fail_records = migrate_module._classify_lines(events_path, validator)
    assert len(pass_lines) == 2
    assert len(fail_records) == 1
    assert "json-decode" in fail_records[0][2]


def test_classify_skips_blank_lines(tmp_path, migrate_module) -> None:
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        "",
        "   ",
        _strict_provenance_event("ev-s2"),
    ])
    events_path = ws / "projects" / "test-proj" / "_state" / "events.jsonl"
    validator = migrate_module._load_schema()
    pass_lines, fail_records = migrate_module._classify_lines(events_path, validator)
    assert len(pass_lines) == 2
    assert fail_records == []


# ---------------------------------------------------------------------------
# migrate() end-to-end tests
# ---------------------------------------------------------------------------

def test_no_legacy_rows_is_noop(tmp_path, migrate_module) -> None:
    """Strict-only events.jsonl: exit 0, no legacy file, no report."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _strict_provenance_event("ev-s2"),
    ])
    rc = migrate_module.migrate(ws, "test-proj")
    assert rc == 0
    project_pack = ws / "projects" / "test-proj"
    assert not (project_pack / "_state" / "events.jsonl.legacy").exists()
    reports = project_pack / "outputs" / "reports"
    if reports.exists():
        assert not list(reports.glob("*-events-archive.md"))


def test_partial_fail_writes_legacy_and_report(tmp_path, migrate_module) -> None:
    """Mixed events.jsonl: strict rewritten, legacy archived, report emitted."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
        _strict_provenance_event("ev-s2"),
        _legacy_top_level_missing("ev-l2"),
    ])
    rc = migrate_module.migrate(ws, "test-proj")
    assert rc == 0

    project_pack = ws / "projects" / "test-proj"
    events_path = project_pack / "_state" / "events.jsonl"
    legacy_path = project_pack / "_state" / "events.jsonl.legacy"

    # Strict file: 2 pass rows
    strict_rows = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    strict_ids = {r["event_id"] for r in strict_rows}
    assert strict_ids == {"ev-s1", "ev-s2"}

    # Legacy file: 2 fail rows (raw)
    legacy_rows = [line for line in legacy_path.read_text().splitlines() if line.strip()]
    assert len(legacy_rows) == 2

    # Audit report exists with table rows
    report_files = list((project_pack / "outputs" / "reports").glob("*-events-archive.md"))
    assert len(report_files) == 1
    report_text = report_files[0].read_text(encoding="utf-8")
    assert "Events Archive Report" in report_text
    assert "Archived rows: **2**" in report_text
    assert "| Line |" in report_text


def test_dry_run_skips_writes(tmp_path, migrate_module, capsys) -> None:
    """dry_run=True: no filesystem changes, fail records logged to stderr."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
    ])
    project_pack = ws / "projects" / "test-proj"
    events_path = project_pack / "_state" / "events.jsonl"
    snapshot = events_path.read_text(encoding="utf-8")

    rc = migrate_module.migrate(ws, "test-proj", dry_run=True)
    assert rc == 0
    # Filesystem untouched
    assert events_path.read_text(encoding="utf-8") == snapshot
    assert not (project_pack / "_state" / "events.jsonl.legacy").exists()
    captured = capsys.readouterr()
    assert "would archive L2" in captured.err


def test_existing_legacy_file_appends(tmp_path, migrate_module) -> None:
    """Re-run scenario: existing legacy file gets new fail rows appended
    (append-only-state discipline preserved)."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
    ])
    project_pack = ws / "projects" / "test-proj"
    legacy_path = project_pack / "_state" / "events.jsonl.legacy"

    # First run: archives 1 fail row.
    rc1 = migrate_module.migrate(ws, "test-proj")
    assert rc1 == 0
    first_legacy = legacy_path.read_text(encoding="utf-8")
    assert first_legacy.count("\n") >= 1

    # Add a new mixed batch: 1 strict + 1 legacy.
    events_path = project_pack / "_state" / "events.jsonl"
    new_payload = events_path.read_text(encoding="utf-8")
    new_payload += json.dumps(_strict_provenance_event("ev-s2")) + "\n"
    new_payload += json.dumps(_legacy_top_level_missing("ev-l2")) + "\n"
    events_path.write_text(new_payload, encoding="utf-8")

    rc2 = migrate_module.migrate(ws, "test-proj")
    assert rc2 == 0
    second_legacy = legacy_path.read_text(encoding="utf-8")
    # Second-run legacy must be >= first run (append, not overwrite)
    assert len(second_legacy) > len(first_legacy)


def test_missing_events_jsonl_returns_2(tmp_path, migrate_module) -> None:
    """No events.jsonl at the workspace path → exit 2 (DURUR)."""
    ws = tmp_path / "empty-workspace"
    (ws / "projects" / "test-proj" / "_state").mkdir(parents=True, exist_ok=True)
    rc = migrate_module.migrate(ws, "test-proj")
    assert rc == 2


def test_audit_report_format_includes_event_id(tmp_path, migrate_module) -> None:
    """Audit report markdown row format: ``| L# | event_id | reason |``."""
    ws = _seed_events(tmp_path, [
        _legacy_audit_missing_action("legacy_evid_42"),
    ])
    rc = migrate_module.migrate(ws, "test-proj")
    assert rc == 0
    project_pack = ws / "projects" / "test-proj"
    report = next(iter((project_pack / "outputs" / "reports").glob("*-events-archive.md")))
    body = report.read_text(encoding="utf-8")
    assert "legacy_evid_42" in body
    assert "| 1 |" in body  # line number column


# ---------------------------------------------------------------------------
# Crash-safety + concurrency hardening (deep-audit HIGH findings, 2026-06-04)
#
# events.jsonl is the append-only ledger / SSoT. The original migration:
#   (1) renamed strict (lossy) BEFORE legacy (preserving) — a crash between the
#       two renames lost the failing rows permanently; and
#   (2) read+rewrote the file with no flock — a concurrent append by the
#       events_writer path could be silently dropped by the truncating rewrite.
# These three tests lock in the hardened behavior.
# ---------------------------------------------------------------------------

def test_migrate_backs_up_original_events_before_overwrite(tmp_path, migrate_module) -> None:
    """The COMPLETE original events.jsonl is backed up to events.jsonl.bak before
    the in-place overwrite, so the pre-migration ledger is always recoverable."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
        _strict_provenance_event("ev-s2"),
    ])
    project_pack = ws / "projects" / "test-proj"
    events_path = project_pack / "_state" / "events.jsonl"
    original = events_path.read_text(encoding="utf-8")

    rc = migrate_module.migrate(ws, "test-proj")
    assert rc == 0

    backup_path = project_pack / "_state" / "events.jsonl.bak"
    assert backup_path.exists(), "migration must back up the original events.jsonl"
    # The backup holds the WHOLE original ledger (all 3 rows), not the strict subset.
    assert backup_path.read_text(encoding="utf-8") == original


def test_migrate_preserving_writes_complete_before_lossy_rewrite(
    tmp_path, migrate_module, monkeypatch
) -> None:
    """The legacy archive AND the .bak backup are durable BEFORE the lossy
    in-place rewrite of events.jsonl, so a failure of that rewrite loses no
    data: the fail rows are already archived and events.jsonl is recoverable
    from the backup."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
        _legacy_top_level_missing("ev-l2"),
    ])
    project_pack = ws / "projects" / "test-proj"
    legacy_path = project_pack / "_state" / "events.jsonl.legacy"
    backup_path = project_pack / "_state" / "events.jsonl.bak"
    original = (project_pack / "_state" / "events.jsonl").read_text(encoding="utf-8")

    # Simulate a crash during the lossy in-place strict rewrite (the LAST step).
    # raising=False so the spy is set even on the RED run where the helper does
    # not exist yet (the test then fails cleanly on the missing OSError).
    def _boom(fd, content):
        raise OSError(5, "simulated crash during in-place strict rewrite")

    monkeypatch.setattr(migrate_module, "_rewrite_locked_file", _boom, raising=False)

    with pytest.raises(OSError, match="simulated crash"):
        migrate_module.migrate(ws, "test-proj")

    # Preserving writes already landed before the lossy rewrite was attempted:
    legacy_rows = [l for l in legacy_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(legacy_rows) == 2                       # fail rows archived
    assert backup_path.read_text(encoding="utf-8") == original  # full original recoverable


def test_migrate_rewrites_events_in_place_preserving_inode(tmp_path, migrate_module) -> None:
    """events.jsonl must be rewritten IN PLACE (same inode), not replaced. The
    events_writer append path flocks the data file itself, so an inode-swapping
    rename would orphan a concurrent appender's lock and drop its write."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
        _strict_provenance_event("ev-s2"),
    ])
    events_path = ws / "projects" / "test-proj" / "_state" / "events.jsonl"
    inode_before = events_path.stat().st_ino

    rc = migrate_module.migrate(ws, "test-proj")
    assert rc == 0
    assert events_path.stat().st_ino == inode_before, (
        "events.jsonl must be rewritten in place (stable inode), not replaced"
    )
    strict_ids = {
        json.loads(l)["event_id"]
        for l in events_path.read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert strict_ids == {"ev-s1", "ev-s2"}


def test_migrate_serializes_appends_with_exclusive_flock(
    tmp_path, migrate_module, monkeypatch
) -> None:
    """The migration takes the same exclusive flock the events_writer append path
    uses, so a concurrent append cannot be dropped by the truncating rewrite."""
    ws = _seed_events(tmp_path, [
        _strict_provenance_event("ev-s1"),
        _legacy_audit_missing_action("ev-l1"),
    ])
    # RED-friendly: the migration must import fcntl to lock the append-only ledger.
    assert hasattr(migrate_module, "fcntl"), "migration must import fcntl to serialize appends"

    ops: list[int] = []
    real_flock = migrate_module.fcntl.flock

    def _flock_spy(fd, operation):
        ops.append(operation)
        return real_flock(fd, operation)

    monkeypatch.setattr(migrate_module.fcntl, "flock", _flock_spy)

    rc = migrate_module.migrate(ws, "test-proj")
    assert rc == 0
    assert migrate_module.fcntl.LOCK_EX in ops, "migration must acquire LOCK_EX on events.jsonl"
