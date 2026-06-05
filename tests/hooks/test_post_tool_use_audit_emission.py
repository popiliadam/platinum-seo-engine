"""tests/hooks/test_post_tool_use_audit_emission.py — A1+A3 regression coverage.

Originally these tests regex-extracted the inline ``python3 -c`` audit command
from ``hooks/post-tool-use.json`` and ran it as a subprocess. AMO batch 0d
EXTRACTED that command to ``scripts/hooks/audit_post_tool_use.py`` (fixing audit
bug H1: per-session project attribution instead of the workspace-global
``shared/active.json``). The A1 (Bash redaction — no secret leak) and A3
(audit_action mapping) coverage now targets the extracted PURE function
``build_audit_fields(payload)`` directly, plus the script's non-blocking contract
and the hook wiring — same behaviour, cleaner call site.

Coverage matrix (behaviour unchanged from the inline command):
  - matcher "Edit|Write|Bash"
  - hook wires the extracted script (plugin-agnostic); script calls append_audit
    with the canonical actor + resolved workspace_root + 480-capped target
  - A1: Bash command audit_target redacted to head word + " [REDACTED args]"
  - A1: ghp_/sk-/AKIA secret literals do NOT appear in audit_target
  - A1 edge: empty/whitespace command, missing command field → "<empty> [REDACTED args]"
  - A1: head word preservation (git, python3, ls, rm, curl) — semantic audit value
  - A3: Edit → modified; Write existing → modified; Write new → created
  - A3: Bash → accessed (default); Unknown tool → accessed (default)
  - non-blocking: an append_audit failure prints a WARNING to stderr but exits 0
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

import scripts.hooks.audit_post_tool_use as mod
from scripts.hooks.audit_post_tool_use import build_audit_fields

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "post-tool-use.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "hooks" / "audit_post_tool_use.py"


def _audit_handler() -> dict:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    return spec["hooks"]["PostToolUse"][0]


def _fields(payload: dict) -> dict:
    """The extracted pure emitter logic (formerly an inline `python3 -c` subprocess)."""
    return build_audit_fields(payload)


# --- wiring / integration contract ---------------------------------------

def test_matcher_covers_edit_write_bash() -> None:
    assert _audit_handler()["matcher"] == "Edit|Write|Bash"


def test_hook_wires_extracted_audit_script() -> None:
    """The PostToolUse audit command invokes the extracted script, not an inline -c."""
    cmd = _audit_handler()["hooks"][0]["command"]
    assert "audit_post_tool_use.py" in cmd
    assert "${CLAUDE_PLUGIN_ROOT}" in cmd  # plugin-agnostic (F-16)
    assert "python3 -c" not in cmd  # inline command fully extracted


def test_script_calls_append_audit_with_actor_and_ws() -> None:
    """events_writer integration: the script appends with the canonical actor, a
    480-capped target, and the resolved workspace_root (signature preserved)."""
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "from scripts.state.events_writer import" in src
    assert "append_audit(" in src
    assert '"claude-code:hook:PostToolUse"' in src  # canonical actor value
    assert "actor=_ACTOR" in src  # …passed to the append_audit call
    assert "workspace_root=workspace_root" in src
    assert "[:_TARGET_CAP]" in src  # 480-char audit_target cap retained


def test_append_audit_failure_is_nonblocking(tmp_path: Path, monkeypatch, capsys) -> None:
    """P1-06 preserved: an emit failure prints a visible WARNING to stderr but the
    hook still exits 0 (non-blocking) — it surfaces instead of breaking the tool."""
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "alpha"}), encoding="utf-8"
    )
    home = tmp_path / "home"
    home.mkdir()

    def _boom(**kwargs):
        raise RuntimeError("ledger exploded")

    monkeypatch.setattr(mod, "append_audit", _boom)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "/x.md"}})),
    )
    assert mod.main() == 0  # non-blocking
    assert "WARNING" in capsys.readouterr().err  # visible, not silently swallowed


# --- A1: Bash redaction ---------------------------------------------------

def test_bash_redaction_ghp_leak() -> None:
    """A1 KRİTİK: GitHub PAT-like secret in a Bash command must NOT appear in audit_target."""
    secret = "ghp_" + "b" * 36  # synthetic (concatenated so the literal isn't in source)
    out = _fields({"tool_name": "Bash", "tool_input": {"command": f"echo TEST_API_KEY={secret}"}})
    assert secret not in out["audit_target"], f"Secret leaked: {out!r}"
    assert out["audit_target"] == "Bash:echo [REDACTED args]"


def test_bash_redaction_sk_leak() -> None:
    """A1: Anthropic/OpenAI sk- prefix secret redacted; head=curl preserved."""
    secret = "sk-" + "c" * 30
    out = _fields({"tool_name": "Bash", "tool_input": {"command": f'curl -H "Authorization: Bearer {secret}"'}})
    assert secret not in out["audit_target"]
    assert out["audit_target"] == "Bash:curl [REDACTED args]"


def test_bash_redaction_aws_leak() -> None:
    """A1: AWS access key (AKIA prefix) redacted; head=aws preserved.

    NOTE: synthesize via concatenation so the literal does not appear in source
    text (avoids check_secrets.sh `aws_akia_key_literal` regex match on grep -r).
    """
    fake_key = "AKIA" + "I" * 16  # synthetic, regex-format-valid, source-text-safe
    out = _fields({"tool_name": "Bash", "tool_input": {"command": f"aws s3 ls --access-key {fake_key}"}})
    assert fake_key not in out["audit_target"]
    assert out["audit_target"] == "Bash:aws [REDACTED args]"


def test_bash_empty_command_redacted() -> None:
    assert _fields({"tool_name": "Bash", "tool_input": {"command": ""}})["audit_target"] == "Bash:<empty> [REDACTED args]"


def test_bash_whitespace_command_redacted() -> None:
    assert _fields({"tool_name": "Bash", "tool_input": {"command": "   "}})["audit_target"] == "Bash:<empty> [REDACTED args]"


def test_bash_missing_command_field_redacted() -> None:
    assert _fields({"tool_name": "Bash", "tool_input": {}})["audit_target"] == "Bash:<empty> [REDACTED args]"


@pytest.mark.parametrize(
    "cmd,expected_head",
    [
        ("git push origin main", "git"),
        ("python3 -c 'print(1)'", "python3"),
        ("ls /tmp", "ls"),
        ("rm -rf /tmp/x", "rm"),
        ("curl https://example.com", "curl"),
    ],
)
def test_bash_head_word_preserved(cmd: str, expected_head: str) -> None:
    """A1 design intent: head word retained for semantic audit value."""
    out = _fields({"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert out["audit_target"] == f"Bash:{expected_head} [REDACTED args]"


# --- A3: audit_action mapping --------------------------------------------

def test_edit_audit_action_modified(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi")
    out = _fields({"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    assert out["audit_action"] == "modified"
    assert out["audit_target"] == f"Edit:{f}"


def test_edit_nonexistent_path_still_modified(tmp_path: Path) -> None:
    """A3: Edit semantic always 'modified' (target may pre/post-exist; semantic is mutation)."""
    nonexist = tmp_path / "nope.txt"
    out = _fields({"tool_name": "Edit", "tool_input": {"file_path": str(nonexist)}})
    assert out["audit_action"] == "modified"


def test_write_existing_modified(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi")
    out = _fields({"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert out["audit_action"] == "modified"


def test_write_new_created(tmp_path: Path) -> None:
    nonexist = tmp_path / "new.txt"
    out = _fields({"tool_name": "Write", "tool_input": {"file_path": str(nonexist)}})
    assert out["audit_action"] == "created"


def test_bash_audit_action_accessed() -> None:
    assert _fields({"tool_name": "Bash", "tool_input": {"command": "ls /tmp"}})["audit_action"] == "accessed"


def test_unknown_tool_audit_action_accessed() -> None:
    assert _fields({"tool_name": "Glob", "tool_input": {"pattern": "*.py"}})["audit_action"] == "accessed"


def test_audit_target_truncated_to_480(tmp_path: Path) -> None:
    """audit_target truncate budget: events.jsonl line size sanity (480 char hard limit)."""
    long_path = tmp_path / ("x" * 500 + ".txt")
    out = _fields({"tool_name": "Edit", "tool_input": {"file_path": str(long_path)}})
    assert len(out["audit_target"]) <= 480
