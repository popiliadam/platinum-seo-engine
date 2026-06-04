"""tests/scripts/test_validate_invariants_F12.py — deep-audit HIGH (2026-06-04).

F-12 is the engine's only enforcement of the append-only rule on the
events.jsonl ledger: it FAILs when the line count drops below a recorded
baseline in ``_state/events.snapshot.json``. The audit found the FAIL branch
unreachable in practice because NO component ever wrote the snapshot — so
``prev_lines`` was permanently 0 and the invariant always passed vacuously.

The fix makes ``check_F_12`` itself record/advance the baseline (a monotonic
high-water mark, as its own docstring always promised), so a later truncation
of the ledger is detectable.

Cross-references:
- scripts/validation/validate_invariants.py::check_F_12
- scripts/validation/validate_invariants.py::_write_events_snapshot
- rules/append-only-state.md
- docs/audits/2026-06-04_deep_quality_security_audit.md (F-12 finding)
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validation.validate_invariants import check_F_12


def _seed_events(tmp_path: Path, n_lines: int, slug: str = "test-proj") -> Path:
    """Create {ws}/projects/{slug}/_state/events.jsonl with n non-blank lines."""
    state = tmp_path / "projects" / slug / "_state"
    state.mkdir(parents=True, exist_ok=True)
    events = state / "events.jsonl"
    events.write_text(
        "".join(f'{{"event_id":"e{i}"}}\n' for i in range(n_lines)),
        encoding="utf-8",
    )
    return events


def test_F12_records_baseline_so_guard_is_not_vacuous(tmp_path: Path) -> None:
    """check_F_12 must WRITE events.snapshot.json — without a producer the FAIL
    branch can never fire (the vacuous-no-op finding)."""
    _seed_events(tmp_path, 3)
    snap = tmp_path / "projects" / "test-proj" / "_state" / "events.snapshot.json"
    assert not snap.exists()

    result = check_F_12(None, "test-proj", workspace_root=tmp_path)

    assert result["verdict"] == "PASS"
    assert snap.exists(), "F-12 must record the events.snapshot.json baseline"
    assert json.loads(snap.read_text(encoding="utf-8"))["lines"] == 3


def test_F12_detects_truncation_after_baseline_recorded(tmp_path: Path) -> None:
    """Once the baseline exists, a subsequent shrink of the append-only ledger
    FAILs F-12 (the guard is now reachable)."""
    events = _seed_events(tmp_path, 3)

    first = check_F_12(None, "test-proj", workspace_root=tmp_path)
    assert first["verdict"] == "PASS"

    # Simulate truncation / row-loss of the append-only ledger.
    events.write_text('{"event_id":"e0"}\n', encoding="utf-8")
    second = check_F_12(None, "test-proj", workspace_root=tmp_path)

    assert second["verdict"] == "FAIL"
    assert second["affected_rows"] == 2  # 3 -> 1


def test_F12_high_water_mark_keeps_failing_until_restored(tmp_path: Path) -> None:
    """The baseline is a monotonic high-water mark: a shrink keeps FAILing on
    later runs (it is not silently reset downward to mask the loss)."""
    events = _seed_events(tmp_path, 3)
    check_F_12(None, "test-proj", workspace_root=tmp_path)  # record hwm=3

    events.write_text('{"event_id":"e0"}\n', encoding="utf-8")  # shrink to 1
    check_F_12(None, "test-proj", workspace_root=tmp_path)      # FAIL, hwm stays 3
    third = check_F_12(None, "test-proj", workspace_root=tmp_path)

    assert third["verdict"] == "FAIL"

    # Restoring the rows clears the failure.
    events.write_text(
        "".join(f'{{"event_id":"e{i}"}}\n' for i in range(3)),
        encoding="utf-8",
    )
    restored = check_F_12(None, "test-proj", workspace_root=tmp_path)
    assert restored["verdict"] == "PASS"


def test_F12_missing_events_jsonl_skips_and_writes_no_snapshot(tmp_path: Path) -> None:
    """No ledger yet → SKIP, and no snapshot is produced (early return)."""
    (tmp_path / "projects" / "test-proj" / "_state").mkdir(parents=True, exist_ok=True)
    result = check_F_12(None, "test-proj", workspace_root=tmp_path)
    assert result["verdict"] == "SKIP"
    snap = tmp_path / "projects" / "test-proj" / "_state" / "events.snapshot.json"
    assert not snap.exists()
