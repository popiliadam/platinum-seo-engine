#!/usr/bin/env python3
"""outward_log.py — append-only log of "kayıtlı" (logged) outward actions (G-01).

The consent gate lets a logged-tier action run without asking, and records ONE
line for it in the bound project's ``_state/outward.jsonl`` so it can be traced
later (a push to main, a DataForSEO POST, a single project-file delete).

Discipline mirrors consent_ledger / events_writer: O_APPEND + flock + a single
os.write + fsync; never os.replace (an append-only log, not a marker). The line
is stdlib-JSON only, so the gate can write it without jsonschema.

Public API:
    outward_log_path(workspace_root, project_slug) -> Path
    append_outward(workspace_root, project_slug, *, session_id, action, target,
                   now_iso) -> dict
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path


def outward_log_path(workspace_root: Path | str, project_slug: str) -> Path:
    """``{ws}/projects/{slug}/_state/outward.jsonl`` (the project's _state must exist)."""
    return Path(workspace_root) / "projects" / project_slug / "_state" / "outward.jsonl"


def append_outward(
    workspace_root: Path | str,
    project_slug: str,
    *,
    session_id: str,
    action: str,
    target: str,
    now_iso: str,
) -> dict:
    """Append one logged-tier action line and return it.

    Refuses (FileNotFoundError) when the project's ``_state`` dir is absent rather
    than creating a ghost project tree.
    """
    path = outward_log_path(workspace_root, project_slug)
    if not path.parent.is_dir():
        raise FileNotFoundError(f"no project state dir at {path.parent}")
    row = {
        "ts": now_iso,
        "tier": "kayitli",
        "action": action,
        "target": target,
        "session_id": session_id,
    }
    payload = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    return row


__all__ = ("outward_log_path", "append_outward")
