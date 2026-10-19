"""V-06: a crash mid-write must not wipe shared/portfolio.json.

The registry was truncated in place and then rewritten; a crash or full disk in
between left a 0-byte file, which the next registration read as "new registry"
and rewrote with a single project. Now the write goes to a temp file and is
renamed over the old one, the lock lives in a separate sentinel, and an existing
empty file is an error, never a fresh start.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.state import portfolio_writer as pw
from scripts.state.portfolio_writer import PortfolioWriterError, register_project


def _registry(ws: Path) -> dict:
    return json.loads((ws / "shared" / "portfolio.json").read_text(encoding="utf-8"))


def _seed(ws: Path, n: int = 3) -> None:
    for i in range(n):
        register_project(ws, f"proj-{i}", f"https://p{i}.test", "TR",
                         created_at="2026-10-19T00:00:00Z")


def test_crash_during_write_keeps_the_old_registry(tmp_path, monkeypatch) -> None:
    _seed(tmp_path)

    def _disk_full(fd, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(pw.os, "write", _disk_full)
    with pytest.raises(OSError):
        register_project(tmp_path, "proj-new", "https://n.test", "TR",
                         created_at="2026-10-19T01:00:00Z")
    monkeypatch.undo()
    slugs = [p["slug"] for p in _registry(tmp_path)["active_projects"]]
    assert slugs == ["proj-0", "proj-1", "proj-2"]
    leftovers = [p.name for p in (tmp_path / "shared").iterdir()
                 if p.name not in ("portfolio.json", "portfolio.json.lock")]
    assert leftovers == []  # no temp file left behind


def test_existing_empty_registry_is_an_error_not_a_fresh_start(tmp_path) -> None:
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "portfolio.json").write_bytes(b"")
    with pytest.raises(PortfolioWriterError, match="empty"):
        register_project(tmp_path, "proj-x", "https://x.test", "TR",
                         created_at="2026-10-19T00:00:00Z")
    assert (tmp_path / "shared" / "portfolio.json").read_bytes() == b""


def test_write_replaces_the_file_atomically(tmp_path) -> None:
    _seed(tmp_path, 1)
    before = os.stat(tmp_path / "shared" / "portfolio.json").st_ino
    register_project(tmp_path, "proj-9", "https://9.test", "TR",
                     created_at="2026-10-19T00:00:00Z")
    after = os.stat(tmp_path / "shared" / "portfolio.json").st_ino
    assert before != after  # renamed into place, never truncated in place
    assert (tmp_path / "shared" / "portfolio.json.lock").exists()
