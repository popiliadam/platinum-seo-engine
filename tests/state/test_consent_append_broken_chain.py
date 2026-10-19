"""V-07: never append to a broken consent chain.

append_consent looked only at the last line; the gate verifies the WHOLE chain.
Once a middle entry was damaged, every new consent printed "recorded" while the
gate refused it forever. Now the append verifies the chain under its lock and
fails with the index of the first bad entry.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.state import consent_ledger as cl


def _append(ws: Path, target: str) -> dict:
    return cl.append_consent(
        workspace_root=ws, project_slug="demo", run_id="r", action="git_push",
        target=target, granted_by="user", now_iso="2026-10-19T10:00:00Z",
        session_id="s",
    )


def test_append_to_broken_chain_raises_and_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "projects" / "demo" / "_state").mkdir(parents=True)
    for t in ("a", "b", "c"):
        _append(tmp_path, t)
    path = cl.consent_path(tmp_path, "demo")
    lines = path.read_text(encoding="utf-8").splitlines()
    damaged = json.loads(lines[1])
    damaged["granted_by"] = "someone-else"  # entry_hash no longer matches
    lines[1] = cl.canonical_json(damaged)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(cl.ConsentLedgerError, match="broken at entry 1"):
        _append(tmp_path, "d")
    assert path.read_bytes() == before


def test_append_to_intact_chain_still_works(tmp_path: Path) -> None:
    (tmp_path / "projects" / "demo" / "_state").mkdir(parents=True)
    _append(tmp_path, "a")
    entry = _append(tmp_path, "b")
    assert entry["seq"] == 1
    assert cl.verify_chain(cl.read_entries(tmp_path, "demo")) == (True, None)
