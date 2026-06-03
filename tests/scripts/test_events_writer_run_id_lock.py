"""Concurrency test for race-free provenance run_id allocation (P1-11).

next_run_id() scanned events.jsonl for the max run_id OUTSIDE the append flock,
so two concurrent callers could both read the same max and allocate a DUPLICATE
run_id (read-read-write-write race). The fix allocates the run_id INSIDE the same
fcntl.flock that guards the append (lock -> read max -> write next), so
append_provenance(run_id=None, ...) is guaranteed a unique id under contention.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from scripts.state.events_writer import append_provenance


def _state_dir(tmp_path: Path, slug: str = "race-proj") -> None:
    (tmp_path / "projects" / slug / "_state").mkdir(parents=True, exist_ok=True)


def _run_ids_on_disk(tmp_path: Path, slug: str = "race-proj") -> list[int]:
    p = tmp_path / "projects" / slug / "_state" / "events.jsonl"
    if not p.exists():
        return []
    return [
        json.loads(line)["run_id"]
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_concurrent_auto_allocation_yields_unique_run_ids(tmp_path: Path) -> None:
    slug = "race-proj"
    _state_dir(tmp_path, slug)
    n = 40
    barrier = threading.Barrier(n)
    allocated: list[int] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def worker() -> None:
        try:
            barrier.wait()  # release all threads at once → maximal contention
            result = append_provenance(
                project_id=slug,
                source={"kind": "tool_computed"},
                operation="ingest",
                workspace_root=tmp_path,
            )
            with guard:
                allocated.append(result.run_id)
        except BaseException as exc:  # noqa: BLE001 — surface in the assertion
            with guard:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"worker errors: {errors!r}"
    # Race-free: every returned id is unique and contiguous 1..n.
    assert sorted(allocated) == list(range(1, n + 1))
    # ... and so is the events.jsonl on disk (the source of truth).
    disk = _run_ids_on_disk(tmp_path, slug)
    assert len(disk) == n
    assert sorted(disk) == list(range(1, n + 1))


def test_auto_allocation_starts_at_one_and_increments(tmp_path: Path) -> None:
    slug = "race-proj"
    _state_dir(tmp_path, slug)
    r1 = append_provenance(project_id=slug, source={"kind": "manual"},
                           operation="ingest", workspace_root=tmp_path)
    r2 = append_provenance(project_id=slug, source={"kind": "manual"},
                           operation="normalize", workspace_root=tmp_path)
    assert r1.run_id == 1
    assert r2.run_id == 2
    # Explicit run_id is still honoured (backward compatibility preserved).
    r3 = append_provenance(project_id=slug, run_id=99, source={"kind": "manual"},
                           operation="validate", workspace_root=tmp_path)
    assert r3.run_id == 99
