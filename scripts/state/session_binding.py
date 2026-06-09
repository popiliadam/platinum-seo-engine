"""scripts/state/session_binding.py — AMO session→project binding primitive.

Binds ONE Claude session (keyed by its session UUID) to ONE SEO project so a
user can run 3-5 projects in parallel (one Claude session per project) without
cross-contamination. The binding is a marker file under

    {workspace_root}/shared/sessions/{session_id}.json

keyed by the session UUID, which is available identically from two sources
(AMO batch 0a cross-env probe, engine commit e4c22c0):

  * HOOK context    — the ``session_id`` field of the hook stdin JSON payload.
  * COMMAND / bash  — the ``CLAUDE_CODE_SESSION_ID`` environment variable.

Both are the SAME UUID for a given session, so a marker written by the
``/pseo-bind`` command (keyed by $CLAUDE_CODE_SESSION_ID) is found by a
SessionStart hook (keyed by the stdin session_id) in batch 0c.

Resolution falls back to the workspace-GLOBAL ``shared/active.json`` when a
session is unbound, so nothing regresses for single-project users.

Workspace root is persisted editor-independently in
``~/.config/pseo/config.json`` (the env var ``PSEO_WORKSPACE_ROOT`` only as a
fallback) because batch 0a proved the env var is absent in many sessions and
``cwd`` / ``CLAUDE_ENV_FILE`` are unreliable. ``~/.config/pseo/`` is already an
established engine location (scripts/hooks/env_probe.py logs there).

Atomic write discipline (tempfile in the same dir + fsync + os.replace + parent
dir fsync) MIRRORS scripts/excel/transaction.py::_atomic_save and the inline
recipe in commands/pseo-active.md — it is NOT a new pattern. No importable
shared JSON-atomic-writer exists in the engine today (transaction._atomic_save
is Workbook-specific and private), so the canonical recipe is replicated here
per the batch spec.

This module has NO consumers yet: batch 0c wires dump_workspace
(strict=True) and the content-gate hook (strict=False) onto
``resolve_session_project``. It writes only marker files + the user config; it
never touches active.json (that stays /pseo-active's job).

Authority: ADR-035 PSEO_WORKSPACE_ROOT, schemas/session-marker.schema.json,
  schemas/project-config.schema.json slug grammar, batch 0a probe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

# Module dir: <repo>/scripts/state/session_binding.py → repo = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Slug grammar — matches project-config.schema.json / events_writer._SLUG_RE.
_SLUG_RE = re.compile(r"[a-z][a-z0-9-]*")

_ENV_WORKSPACE = "PSEO_WORKSPACE_ROOT"
_ENV_SESSION = "CLAUDE_CODE_SESSION_ID"
_ENV_WORKSPACE_OVERRIDE = "PSEO_WORKSPACE_ROOT_OVERRIDE"


class WorkspaceRootConflictError(ValueError):
    """Both PSEO_WORKSPACE_ROOT and ~/.config/pseo/config.json declare a workspace
    root and they DIFFER (#7 fail-loud, ADR-035). A silent divergence would write
    to a different workspace than the operator believes they targeted. Resolve by
    unsetting one source, or by setting ``PSEO_WORKSPACE_ROOT_OVERRIDE=env|config``
    to name the winner explicitly. Subclasses ``ValueError`` so the bind CLI's
    existing ValueError handler surfaces it as a clean, non-zero-exit error.
    """


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _config_path() -> Path:
    """``~/.config/pseo/config.json`` with ~ expanded at call time.

    Reads $HOME via os.path.expanduser, so tests monkeypatch HOME to tmp_path
    and never touch the real ~/.config.
    """
    return Path(os.path.expanduser(os.path.join("~", ".config", "pseo", "config.json")))


def _is_safe_session_id(session_id: str) -> bool:
    """Reject ids that could escape sessions_dir (path traversal defense)."""
    return (
        isinstance(session_id, str)
        and bool(session_id)
        and not session_id.startswith(".")
        and "/" not in session_id
        and "\\" not in session_id
        and os.sep not in session_id
        and ".." not in session_id
    )


def sessions_dir(workspace_root: Path) -> Path:
    """Workspace-GLOBAL session-marker dir: ``{ws}/shared/sessions`` (beside active.json)."""
    return Path(workspace_root) / "shared" / "sessions"


# ---------------------------------------------------------------------------
# Atomic JSON write — mirrors transaction.py::_atomic_save (Workbook variant)
# ---------------------------------------------------------------------------

def _atomic_write_json(target: Path, payload: dict) -> None:
    """Atomic write: tempfile in same dir → fsync → os.replace → parent dir fsync.

    The canonical engine discipline (transaction._atomic_save / pseo-active.md),
    not a new pattern. Writes JSON through the tempfile fd, then renames over the
    target so a reader never sees a torn file. Cleans up the tempfile on failure
    without swallowing the error.
    """
    target = Path(target)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=".sb-", suffix=".json.tmp", dir=str(parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(target))
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:  # pragma: no cover
            pass
        raise
    # Parent dir fsync — durability of the rename (best-effort; not all FS support).
    try:
        dir_fd = os.open(str(parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:  # pragma: no cover
        pass


def _read_json(path: Path) -> dict | None:
    """Read+parse a JSON object; return None on any missing/invalid (never raises)."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _norm_root(raw: str) -> str:
    """Filesystem-independent normal form for conflict comparison: expanduser +
    normpath (NO symlink resolution, so a missing dir / a test tmp path compares
    cleanly and a trailing slash is not a false conflict)."""
    return os.path.normpath(os.path.expanduser(raw))


def resolve_workspace_root(environ: Mapping[str, str] = os.environ) -> Path | None:
    """Resolve the workspace root: ~/.config/pseo/config.json → env → None.

    Persisted config wins (editor-independent); the env var is only a fallback
    because batch 0a proved it is absent in many sessions.

    #7 fail-loud: when BOTH sources are set and resolve to DIFFERENT paths this
    raises :class:`WorkspaceRootConflictError` instead of silently preferring
    config — UNLESS ``PSEO_WORKSPACE_ROOT_OVERRIDE`` (``env``|``config``) names the
    winner. Every non-conflict case (config-only, env-only, both-equal, neither)
    is byte-for-byte unchanged.
    """
    data = _read_json(_config_path())
    config_raw: str | None = None
    if data:
        raw = data.get("workspace_root")
        if isinstance(raw, str) and raw:
            config_raw = raw
    env_raw = environ.get(_ENV_WORKSPACE) or None

    if config_raw and env_raw and _norm_root(config_raw) != _norm_root(env_raw):
        override = (environ.get(_ENV_WORKSPACE_OVERRIDE) or "").strip().lower()
        if override == "env":
            return Path(os.path.expanduser(env_raw))
        if override == "config":
            return Path(os.path.expanduser(config_raw))
        raise WorkspaceRootConflictError(
            f"workspace root conflict: ${_ENV_WORKSPACE}={env_raw!r} != config "
            f"{_config_path()} workspace_root={config_raw!r}. Unset one, or set "
            f"${_ENV_WORKSPACE_OVERRIDE}=env|config to choose the winner."
        )

    if config_raw:
        return Path(os.path.expanduser(config_raw))
    if env_raw:
        return Path(os.path.expanduser(env_raw))
    return None


def current_session_id(
    payload: dict | None = None, environ: Mapping[str, str] = os.environ
) -> str | None:
    """The session UUID: hook stdin payload session_id → env var → None."""
    if payload:
        sid = payload.get("session_id")
        if sid:
            return sid
    return environ.get(_ENV_SESSION) or None


def read_session_binding(session_id: str, workspace_root: Path) -> str | None:
    """Slug bound to ``session_id`` (marker active_project); None if absent/invalid."""
    if not _is_safe_session_id(session_id):
        return None
    data = _read_json(sessions_dir(workspace_root) / f"{session_id}.json")
    if not data:
        return None
    slug = data.get("active_project")
    return slug if isinstance(slug, str) and slug else None


def read_active_project(workspace_root: Path) -> str | None:
    """Workspace-global active slug (shared/active.json); None if absent/invalid."""
    data = _read_json(Path(workspace_root) / "shared" / "active.json")
    if not data:
        return None
    slug = data.get("active_project")
    return slug if isinstance(slug, str) and slug else None


def resolve_session_project(
    workspace_root: Path | None,
    *,
    arg: str | None = None,
    session_id: str | None = None,
    strict: bool = False,
) -> str | None:
    """Resolve which project THIS context targets.

    Precedence: explicit ``arg`` → session marker (needs session_id AND
    workspace_root) → shared/active.json → None. With ``strict`` a None result
    raises FileNotFoundError (dump_workspace's command contract); without it,
    None is returned (the content-gate hook's never-raise contract). Batch 0c
    wires strict=True for commands, strict=False for hooks.
    """
    result: str | None = None
    if arg:
        result = arg
    elif session_id and workspace_root is not None:
        result = read_session_binding(session_id, workspace_root)
    if result is None and workspace_root is not None:
        result = read_active_project(workspace_root)
    if result is None and strict:
        raise FileNotFoundError(
            "no project bound to this session and no shared/active.json fallback — "
            "run /pseo-bind <slug> (this session) or /pseo-active <slug> (global)"
        )
    return result


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def write_session_binding(
    session_id: str, slug: str, workspace_root: Path, now_iso: str
) -> Path:
    """Atomically write the session marker; return its path.

    Marker = {"active_project": slug, "bound_at": now_iso, "session_id": id}.
    Rejects unsafe ids (path traversal) and non-slug projects (defense in depth).
    """
    if not _is_safe_session_id(session_id):
        raise ValueError(f"unsafe session_id (path-traversal guard): {session_id!r}")
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"invalid slug (must match ^[a-z][a-z0-9-]*$): {slug!r}")
    target = sessions_dir(workspace_root) / f"{session_id}.json"
    payload = {"active_project": slug, "bound_at": now_iso, "session_id": session_id}
    _atomic_write_json(target, payload)
    return target


def persist_workspace_root(workspace_root: Path) -> Path:
    """Atomically write ~/.config/pseo/config.json["workspace_root"], merge-preserving."""
    cfg = _config_path()
    existing = _read_json(cfg) or {}
    merged = {**existing, "workspace_root": str(workspace_root)}
    _atomic_write_json(cfg, merged)
    return cfg


# ---------------------------------------------------------------------------
# Runtime self-check (consumed by a SessionStart hook in 0c)
# ---------------------------------------------------------------------------

def session_ids_consistent(
    payload: dict | None, environ: Mapping[str, str] = os.environ
) -> bool:
    """True iff hook payload session_id == env CLAUDE_CODE_SESSION_ID, OR either is missing.

    A missing side cannot prove inconsistency, so it returns True (advisory check).
    """
    hook_id = (payload or {}).get("session_id")
    env_id = environ.get(_ENV_SESSION)
    if not hook_id or not env_id:
        return True
    return hook_id == env_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session_binding.py",
        description="AMO session→project binding primitive (batch 0b).",
    )
    sub = parser.add_subparsers(dest="cmd")
    bind = sub.add_parser("bind", help="Bind THIS Claude session to a project slug.")
    bind.add_argument("slug", help="Project slug (projects/<slug>/project.config.json must exist).")
    bind.add_argument(
        "--workspace",
        default=None,
        help="Workspace root; persisted to ~/.config/pseo/config.json (pass once).",
    )
    return parser


def _cmd_bind(slug: str, workspace: str | None) -> int:
    if not _SLUG_RE.fullmatch(slug or ""):
        print(f"error: invalid slug (must match ^[a-z][a-z0-9-]*$): {slug!r}", file=sys.stderr)
        return 4
    # 1. Workspace root: explicit --workspace (persist it) else resolve.
    if workspace:
        ws = Path(os.path.expanduser(workspace))
        persist_workspace_root(ws)
    else:
        ws = resolve_workspace_root()
    if ws is None:
        print(
            "error: no workspace root — pass --workspace <path> once to persist it "
            f"(or set ${_ENV_WORKSPACE})",
            file=sys.stderr,
        )
        return 2
    # 2. Session id (command context → env var).
    session_id = current_session_id()
    if not session_id:
        print(f"error: no ${_ENV_SESSION} in environment — run from a Claude session", file=sys.stderr)
        return 3
    # 3. Validate the project exists (mirror /pseo-active's slug check).
    cfg = ws / "projects" / slug / "project.config.json"
    if not cfg.exists():
        print(f"error: {cfg} not found — run /pseo-init {slug} first (marker NOT written)", file=sys.stderr)
        return 4
    # 4. Write the marker + one-line confirmation banner. Canonical UTC '…Z'
    #    (rules/time-discipline.md §8.10; mirrors events_writer._utc_iso_z) —
    #    datetime.now().isoformat() emitted a naive LOCAL stamp.
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    path = write_session_binding(session_id, slug, ws, now_iso)
    print(f"bound session {session_id[:8]} → {slug}  ({path})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "bind":
        try:
            return _cmd_bind(args.slug, args.workspace)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 5
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
