"""Slash-command preload blocks must resolve the project the way the engine does.

``scripts/state/session_binding.resolve_session_project`` resolves a project as
explicit arg → THIS session's ``shared/sessions/<session-id>.json`` marker →
``shared/active.json``. The Python consumers (consent ledger, content-write hook,
audit hook, intent router) already follow it. The slash-command ``!`…`` blocks did
NOT: they read ``shared/active.json`` inline, so with 2-4 parallel sessions each
bound via ``/pseo-bind`` a command without an explicit slug ran against whichever
project some OTHER session last made globally active.

These tests lock the shell blocks to the same precedence:

* static  — every block that resolves PROJECT from active.json consults the session
            marker first;
* runtime — the real ``/pseo-status`` block, executed under text substitution
            (the actual Claude Code mechanism, see test_command_quoted_arg_parsing.py),
            picks arg → marker → active.json and degrades safely when the marker is
            absent, corrupt or the session id is unset.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "commands"

# The ONLY command allowed to read active.json without the marker: it is the
# writer/viewer of the global pointer itself.
GLOBAL_POINTER_OWNERS = {"pseo-active.md"}

_ACTIVE_READ_RE = re.compile(r"jq -r '\.active_project // empty' \"[^\"]*shared/active\.json\"")
_MARKER_READ = "shared/sessions/${CLAUDE_CODE_SESSION_ID"


def _resolver_lines() -> list[tuple[str, int, str]]:
    found = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        if path.name in GLOBAL_POINTER_OWNERS:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _ACTIVE_READ_RE.search(line):
                found.append((path.name, lineno, line))
    return found


def test_resolver_lines_exist() -> None:
    """Guard against a vacuous pass: the static test below must see real blocks."""
    assert len(_resolver_lines()) >= 20


@pytest.mark.parametrize("name,lineno,line", _resolver_lines(), ids=lambda v: str(v)[:40])
def test_every_active_json_read_consults_session_marker_first(name: str, lineno: int, line: str) -> None:
    marker_at = line.find(_MARKER_READ)
    active_at = _ACTIVE_READ_RE.search(line).start()
    assert marker_at != -1, f"{name}:{lineno} reads shared/active.json without the session marker"
    assert marker_at < active_at, f"{name}:{lineno} must read the session marker BEFORE active.json"


@pytest.mark.parametrize("name,lineno,line", _resolver_lines(), ids=lambda v: str(v)[:40])
def test_positional_argument_is_validated_as_a_slug_before_use(name: str, lineno: int, line: str) -> None:
    """A flag (`--resume`, `--days-back`) or a number (`28`) in the slug position must not become the
    project: every resolver validates the positional arg against the slug grammar first
    (session_binding._SLUG_RE ``^[a-z][a-z0-9-]*$``) instead of `${N:-$(jq …)}` pass-through."""
    assert '${1:-$(jq' not in line and '${2:-$(jq' not in line, (
        f"{name}:{lineno} passes the raw positional arg through as the project"
    )
    assert 'case "$ARG_SLUG" in' in line or 'case "$SLUG" in' in line, (
        f"{name}:{lineno} does not validate the positional arg as a slug"
    )


def _status_block() -> str:
    text = (COMMANDS_DIR / "pseo-status.md").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("Aktif marker: !`"))
    return line[len("Aktif marker: !`"):line.rindex("`")]


def _run_block(args: str, workspace: Path, session_id: str | None) -> str:
    source = _status_block().replace("$ARGUMENTS", args)
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "PSEO_WORKSPACE_ROOT": str(workspace)}
    if session_id is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    proc = subprocess.run(["bash", "-c", source], capture_output=True, text=True, env=env, timeout=20)
    return proc.stdout.strip()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    shared = tmp_path / "shared"
    (shared / "sessions").mkdir(parents=True)
    (shared / "active.json").write_text(json.dumps({"active_project": "global-proj"}), encoding="utf-8")
    return tmp_path


SID = "11111111-2222-3333-4444-555555555555"


def _bind(workspace: Path, slug_payload: str) -> None:
    (workspace / "shared" / "sessions" / f"{SID}.json").write_text(slug_payload, encoding="utf-8")


pytestmark_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")


@pytestmark_jq
def test_explicit_argument_wins(workspace: Path) -> None:
    _bind(workspace, json.dumps({"active_project": "bound-proj"}))
    assert _run_block("arg-proj", workspace, SID) == "active=arg-proj"


@pytestmark_jq
@pytest.mark.parametrize("args", ["--days-back 28", "28", "Bad_Slug", "-x"])
def test_non_slug_argument_falls_through_to_session_marker(workspace: Path, args: str) -> None:
    _bind(workspace, json.dumps({"active_project": "bound-proj"}))
    assert _run_block(args, workspace, SID) == "active=bound-proj"


@pytestmark_jq
def test_session_marker_beats_global_pointer(workspace: Path) -> None:
    _bind(workspace, json.dumps({"active_project": "bound-proj"}))
    assert _run_block("", workspace, SID) == "active=bound-proj"


@pytestmark_jq
def test_unbound_session_falls_back_to_global_pointer(workspace: Path) -> None:
    assert _run_block("", workspace, SID) == "active=global-proj"


@pytestmark_jq
@pytest.mark.parametrize("payload", ["{broken json", "{}", json.dumps({"active_project": ""})])
def test_corrupt_or_empty_marker_falls_back_to_global_pointer(workspace: Path, payload: str) -> None:
    _bind(workspace, payload)
    assert _run_block("", workspace, SID) == "active=global-proj"


@pytestmark_jq
def test_missing_session_id_falls_back_to_global_pointer(workspace: Path) -> None:
    _bind(workspace, json.dumps({"active_project": "bound-proj"}))
    assert _run_block("", workspace, None) == "active=global-proj"


def _run_block_line(filename: str, needle: str, args: str, workspace: Path, session_id: str | None) -> str:
    text = (COMMANDS_DIR / filename).read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("!`") and needle in l)
    source = line[2:line.rindex("`")].replace("$ARGUMENTS", args)
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "PSEO_WORKSPACE_ROOT": str(workspace)}
    if session_id is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    return subprocess.run(["bash", "-c", source], capture_output=True, text=True, env=env, timeout=20).stdout.strip()


@pytestmark_jq
@pytest.mark.parametrize("args,expected", [
    ("monthly --resume", "workflow=monthly project=bound-proj"),
    ("monthly arg-proj", "workflow=monthly project=arg-proj"),
    ("monthly arg-proj --resume", "workflow=monthly project=arg-proj"),
    ("monthly", "workflow=monthly project=bound-proj"),
])
def test_pseo_run_resume_flag_is_not_taken_as_the_project(workspace: Path, args: str, expected: str) -> None:
    """`/pseo-run <workflow> [slug] [--resume]`: a bare `--resume` in the slug position must fall
    through to the session marker, not become a project named "--resume" (review 2026-09-14)."""
    _bind(workspace, json.dumps({"active_project": "bound-proj"}))
    assert _run_block_line("pseo-run.md", 'WF="${1:-monthly}"', args, workspace, SID) == expected


@pytestmark_jq
def test_nothing_resolvable_reports_no_active_project(workspace: Path) -> None:
    (workspace / "shared" / "active.json").unlink()
    assert _run_block("", workspace, SID) == "NO_ACTIVE_PROJECT"
