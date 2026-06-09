"""tests/hooks/test_validate_content_write.py — PreToolUse content gate.

The hook runs ``content_validator`` at the Write boundary: a RED verdict on a
generated blog HTML write exits 2 (Claude Code blocks the tool call); anything
else exits 0. Path filtering, the Write/Edit split, and fail-open behaviour are
the contract.

Design ref: docs/superpowers/specs/2026-06-04-content-validator-design.md §7.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks.validate_content_write import (
    _resolve_profile,
    evaluate,
    is_content_html_path,
)

_REPO = Path(__file__).resolve().parents[2]
_HOOK = _REPO / "scripts" / "hooks" / "validate_content_write.py"

_CONTENT_PATH = "projects/demo-hvac/outputs/blog/klima-montaji/article.html"


def _payload(tool: str, file_path: str, **content: str) -> dict:
    tool_input = {"file_path": file_path}
    tool_input.update(content)
    return {"tool_name": tool, "tool_input": tool_input}


# --------------------------------------------------------------------------
# Path classification — only the live published HTML surface is validated.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path,expected",
    [
        ("outputs/blog/x/article.html", True),
        ("/a/b/projects/foo/outputs/content/drafts/y.html", True),
        ("projects/foo/outputs/blog/z/article.html", True),
        ("scripts/foo.py", False),
        ("outputs/reports/2026-06-monthly.html", False),
        ("templates/content/new-blog.template.html", False),
        ("projects/foo/outputs/blog/z/upload-instructions.md", False),
        # codex-hostile-audit #16 — the suffix check is case-INSENSITIVE, so an
        # uppercase extension cannot bypass the gate (the whole point of the gate).
        ("outputs/blog/x/article.HTML", True),
        ("outputs/blog/x/article.Html", True),
        # … but the .template.html exclusion must SURVIVE case-folding: a template
        # with an uppercase extension stays out of scope (not a published surface).
        ("outputs/blog/x/article.template.HTML", False),
    ],
)
def test_is_content_html_path(path: str, expected: bool) -> None:
    assert is_content_html_path(path) is expected


# --------------------------------------------------------------------------
# evaluate() — (exit_code, messages); 2 = block, 0 = allow.
# --------------------------------------------------------------------------

def test_write_with_disclosure_blocks() -> None:
    code, msgs = evaluate(
        _payload(
            "Write",
            _CONTENT_PATH,
            content='<article class="pse-blog-post"><p>written by AI</p></article>',
        )
    )
    assert code == 2
    assert any("AI-disclosure" in m for m in msgs)


def test_write_disclosure_to_uppercase_html_blocks() -> None:
    """codex-hostile-audit #16 — a disclosure write to a .HTML (uppercase ext)
    path must NOT bypass the gate: case-insensitive suffix → still exit 2."""
    upper_path = "projects/demo-hvac/outputs/blog/klima-montaji/article.HTML"
    code, msgs = evaluate(
        _payload(
            "Write",
            upper_path,
            content='<article class="pse-blog-post"><p>written by AI</p></article>',
        )
    )
    assert code == 2
    assert any("AI-disclosure" in m for m in msgs)


def test_write_clean_content_allows() -> None:
    code, _ = evaluate(
        _payload(
            "Write",
            _CONTENT_PATH,
            content='<article class="pse-blog-post"><p>Temiz içerik.</p></article>',
        )
    )
    assert code == 0


def test_write_to_non_content_path_skips() -> None:
    code, msgs = evaluate(
        _payload("Write", "scripts/foo.py", content="written by AI")
    )
    assert code == 0
    assert msgs == []


def test_edit_injecting_disclosure_blocks() -> None:
    code, _ = evaluate(
        _payload("Edit", _CONTENT_PATH, new_string="<p>This was written by AI.</p>")
    )
    assert code == 2


def test_edit_with_non_pse_class_does_not_block() -> None:
    """R-61 needs the whole document; on an Edit fragment it must NOT block —
    only the fragment-safe RED rules apply (C1)."""
    code, _ = evaluate(
        _payload("Edit", _CONTENT_PATH, new_string='<div class="highlight">x</div>')
    )
    assert code == 0


def test_bash_tool_skips() -> None:
    code, msgs = evaluate(
        {"tool_name": "Bash", "tool_input": {"command": "echo written by AI"}}
    )
    assert code == 0
    assert msgs == []


def test_malformed_payload_fails_open() -> None:
    code, _ = evaluate("not a dict")  # type: ignore[arg-type]
    assert code == 0


# --------------------------------------------------------------------------
# Subprocess smoke — proves the stdin → exit-code wiring main() relies on.
# --------------------------------------------------------------------------

def test_subprocess_stdin_blocks_on_disclosure() -> None:
    payload = json.dumps(
        _payload(
            "Write",
            _CONTENT_PATH,
            content='<article class="pse-blog-post"><p>written by AI</p></article>',
        )
    )
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=payload,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 2


# --------------------------------------------------------------------------
# AMO batch 0c — _resolve_profile via the session-binding primitive.
# Precedence: session marker (this session) -> shared/active.json (global);
# workspace via resolve_workspace_root() (config -> env). Never raises.
# --------------------------------------------------------------------------

def _write_config(workspace: Path, project_id: str, **config: object) -> None:
    cfg_dir = workspace / "projects" / project_id
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "project.config.json").write_text(json.dumps(config), encoding="utf-8")


def _write_marker(workspace: Path, session_id: str, project_id: str) -> None:
    sessions = workspace / "shared" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / f"{session_id}.json").write_text(
        json.dumps({"active_project": project_id}), encoding="utf-8"
    )


def _write_active(workspace: Path, project_id: str) -> None:
    shared = workspace / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "active.json").write_text(
        json.dumps({"active_project": project_id}), encoding="utf-8"
    )


@pytest.fixture
def isolated_ws(tmp_path, monkeypatch):
    """Tmp workspace wired via $PSEO_WORKSPACE_ROOT, with $HOME pointed away from
    the real ~/.config/pseo/config.json so resolve_workspace_root() uses the env."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return ws


def test_resolve_profile_session_marker_binds_profile(isolated_ws):
    sid = "sess-aaaa"
    _write_marker(isolated_ws, sid, "proj-a")
    _write_config(isolated_ws, "proj-a", profile="ymyl")
    # a DIFFERENT global active.json must NOT win over the session marker
    _write_active(isolated_ws, "proj-b")
    _write_config(isolated_ws, "proj-b", profile="local-service")

    assert _resolve_profile({"session_id": sid}) == "ymyl"


def test_resolve_profile_no_marker_falls_back_to_active_json(isolated_ws):
    _write_active(isolated_ws, "proj-b")
    _write_config(isolated_ws, "proj-b", profile="local-service")

    # session present but unbound (no marker) -> active.json profile (unchanged)
    assert _resolve_profile({"session_id": "unbound-sess"}) == "local-service"


def test_resolve_profile_profiles_list_first_element(isolated_ws):
    _write_active(isolated_ws, "proj-b")
    _write_config(isolated_ws, "proj-b", profiles=["b2b-saas", "ymyl"])

    assert _resolve_profile({"session_id": "unbound"}) == "b2b-saas"


def test_resolve_profile_no_workspace_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)

    assert _resolve_profile({"session_id": "x"}) is None


def test_resolve_profile_bad_config_returns_none(isolated_ws):
    sid = "sess-bad"
    _write_marker(isolated_ws, sid, "proj-a")
    cfg_dir = isolated_ws / "projects" / "proj-a"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "project.config.json").write_text("{not json", encoding="utf-8")

    assert _resolve_profile({"session_id": sid}) is None


def test_resolve_profile_garbage_payload_never_raises(isolated_ws):
    # workspace resolves, but a non-dict payload must never crash the gate
    for garbage in (["not", "a", "dict"], "a string", 42):
        assert _resolve_profile(garbage) is None  # type: ignore[arg-type]


def test_resolve_profile_none_payload_returns_none(isolated_ws):
    # no marker, no active.json, no session -> None (never raises)
    assert _resolve_profile(None) is None
