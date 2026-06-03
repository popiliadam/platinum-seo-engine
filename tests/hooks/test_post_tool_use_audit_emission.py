"""tests/hooks/test_post_tool_use_audit_emission.py — Tier 1 A1+A3 fix kalıcı pytest coverage.

Coverage matrix:
  - matcher "Edit|Write|Bash"
  - append_audit invocation intact (events_writer integration)
  - A1: Bash command audit_target redacted to head word + " [REDACTED args]"
  - A1: ghp_/sk-/AKIA secret literals do NOT appear in audit_target
  - A1 edge: empty/whitespace command, missing command field → "<empty> [REDACTED args]"
  - A1: head word preservation (git, python3, ls, rm) — semantic audit value
  - A3: Edit → audit_action="modified"
  - A3: Write existing → audit_action="modified"
  - A3: Write new → audit_action="created"
  - A3: Bash → audit_action="accessed" (default)
  - A3: Unknown tool → audit_action="accessed" (default)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "post-tool-use.json"

# The early-exit chain that must be replaced for unit-level invocation
# (avoiding the events_writer append side-effect; we only assert tgt +
# audit_action). P1-06: audit_action is now computed AFTER the import (Bash is
# classified via normalize_audit_action), so the debug replacement does the
# import + computes audit_action itself before printing.
_EARLY_EXIT_CHAIN = (
    '(sys.exit(0)) if not (ws and pid) else None; '
    'sys.path.insert(0, os.environ["CLAUDE_PLUGIN_ROOT"]); '
    'from scripts.state.events_writer import append_audit, normalize_audit_action; '
    'audit_action=("modified" if tn=="Edit" else (("modified" if (fp and pathlib.Path(fp).exists()) '
    'else "created") if tn=="Write" else normalize_audit_action(tn, command=cmd))); '
    'append_audit(project_id=pid, audit_action=audit_action, '
    'audit_target=(tn+":"+str(tgt))[:480], actor="claude-code:hook:PostToolUse", '
    'workspace_root=pathlib.Path(ws)); sys.exit(0)'
)
_DEBUG_REPLACEMENT = (
    'sys.path.insert(0, os.environ["CLAUDE_PLUGIN_ROOT"]); '
    'from scripts.state.events_writer import normalize_audit_action; '
    'audit_action=("modified" if tn=="Edit" else (("modified" if (fp and pathlib.Path(fp).exists()) '
    'else "created") if tn=="Write" else normalize_audit_action(tn, command=cmd))); '
    'print(json.dumps({"audit_target": (tn+":"+str(tgt))[:480], '
    '"audit_action": audit_action})); sys.exit(0)'
)


def _audit_command() -> str:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    return spec["hooks"]["PostToolUse"][0]["hooks"][0]["command"]


def _inline_python_debug(cmd: str) -> str:
    """Extract inline python and replace early-exit + append_audit with debug print."""
    m = re.search(r"python3 -c '([^']+(?:'\\\\''[^']*)*)'", cmd)
    assert m, "Could not extract inline python from hook command"
    inline = m.group(1)
    debug = inline.replace(_EARLY_EXIT_CHAIN, _DEBUG_REPLACEMENT)
    assert debug != inline, (
        "Inline early-exit pattern shape changed; update _EARLY_EXIT_CHAIN to match hook"
    )
    return debug


@pytest.fixture
def debug_inline() -> str:
    return _inline_python_debug(_audit_command())


def _run(inline: str, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", inline],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        # P1-06: the debug replacement imports normalize_audit_action via
        # sys.path.insert(CLAUDE_PLUGIN_ROOT), so the env var must be present.
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)},
    )
    assert proc.returncode == 0, f"rc={proc.returncode}, stderr={proc.stderr!r}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_matcher_covers_edit_write_bash() -> None:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    matcher = spec["hooks"]["PostToolUse"][0]["matcher"]
    assert matcher == "Edit|Write|Bash"


def test_append_audit_invocation_intact() -> None:
    """events_writer integration: append_audit signature + actor + workspace_root passed."""
    cmd = _audit_command()
    assert "from scripts.state.events_writer import append_audit" in cmd
    assert "audit_action=audit_action" in cmd
    assert 'audit_target=(tn+":"+str(tgt))[:480]' in cmd
    assert 'actor="claude-code:hook:PostToolUse"' in cmd
    assert "workspace_root=pathlib.Path(ws)" in cmd


def test_audit_failure_wrap_is_visible_and_nonblocking() -> None:
    """P1-06: the blanket `|| true` (silent swallow) is replaced with a wrap that
    prints a visible WARNING to stderr but still exits 0 (non-blocking) — an
    audit-emit failure surfaces instead of vanishing, without blocking the tool."""
    cmd = _audit_command()
    assert "|| true" not in cmd, "blanket `|| true` must be gone — it silently swallowed failures"
    assert "WARNING" in cmd, "hook must print a visible WARNING when the audit emit fails"
    assert cmd.rstrip().endswith("; }"), "warning wrap must still exit 0 (non-blocking)"


def test_bash_redaction_ghp_leak(debug_inline: str) -> None:
    """A1 KRİTİK: GitHub PAT-like secret in Bash command must NOT appear in audit_target."""
    secret = "ghp_" + "b" * 36  # synthetic
    out = _run(debug_inline, {
        "tool_name": "Bash",
        "tool_input": {"command": f"echo TEST_API_KEY={secret}"},
    })
    assert secret not in out["audit_target"], f"Secret leaked: {out!r}"
    assert out["audit_target"] == "Bash:echo [REDACTED args]"


def test_bash_redaction_sk_leak(debug_inline: str) -> None:
    """A1: Anthropic/OpenAI sk- prefix secret redacted; head=curl preserved."""
    secret = "sk-" + "c" * 30
    out = _run(debug_inline, {
        "tool_name": "Bash",
        "tool_input": {"command": f'curl -H "Authorization: Bearer {secret}"'},
    })
    assert secret not in out["audit_target"]
    assert out["audit_target"] == "Bash:curl [REDACTED args]"


def test_bash_redaction_aws_leak(debug_inline: str) -> None:
    """A1: AWS access key (AKIA prefix) redacted; head=aws preserved.

    NOTE: synthesize via concatenation so the literal does not appear in source
    text (avoids check_secrets.sh `aws_akia_key_literal` regex match on grep -r).
    """
    fake_key = "AKIA" + "I" * 16  # synthetic, regex-format-valid, source-text-safe
    out = _run(debug_inline, {
        "tool_name": "Bash",
        "tool_input": {"command": f"aws s3 ls --access-key {fake_key}"},
    })
    assert fake_key not in out["audit_target"]
    assert out["audit_target"] == "Bash:aws [REDACTED args]"


def test_bash_empty_command_redacted(debug_inline: str) -> None:
    out = _run(debug_inline, {"tool_name": "Bash", "tool_input": {"command": ""}})
    assert out["audit_target"] == "Bash:<empty> [REDACTED args]"


def test_bash_whitespace_command_redacted(debug_inline: str) -> None:
    out = _run(debug_inline, {"tool_name": "Bash", "tool_input": {"command": "   "}})
    assert out["audit_target"] == "Bash:<empty> [REDACTED args]"


def test_bash_missing_command_field_redacted(debug_inline: str) -> None:
    out = _run(debug_inline, {"tool_name": "Bash", "tool_input": {}})
    assert out["audit_target"] == "Bash:<empty> [REDACTED args]"


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
def test_bash_head_word_preserved(debug_inline: str, cmd: str, expected_head: str) -> None:
    """A1 design intent: head word retained for semantic audit value."""
    out = _run(debug_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert out["audit_target"] == f"Bash:{expected_head} [REDACTED args]"


def test_edit_audit_action_modified(debug_inline: str, tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi")
    out = _run(debug_inline, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    assert out["audit_action"] == "modified"
    assert out["audit_target"] == f"Edit:{f}"


def test_edit_nonexistent_path_still_modified(debug_inline: str, tmp_path: Path) -> None:
    """A3: Edit semantic always 'modified' (target may pre/post-exist; semantic is mutation)."""
    nonexist = tmp_path / "nope.txt"
    out = _run(debug_inline, {"tool_name": "Edit", "tool_input": {"file_path": str(nonexist)}})
    assert out["audit_action"] == "modified"


def test_write_existing_modified(debug_inline: str, tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi")
    out = _run(debug_inline, {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert out["audit_action"] == "modified"


def test_write_new_created(debug_inline: str, tmp_path: Path) -> None:
    nonexist = tmp_path / "new.txt"
    out = _run(debug_inline, {"tool_name": "Write", "tool_input": {"file_path": str(nonexist)}})
    assert out["audit_action"] == "created"


def test_bash_audit_action_accessed(debug_inline: str) -> None:
    out = _run(debug_inline, {"tool_name": "Bash", "tool_input": {"command": "ls /tmp"}})
    assert out["audit_action"] == "accessed"


def test_unknown_tool_audit_action_accessed(debug_inline: str) -> None:
    out = _run(debug_inline, {"tool_name": "Glob", "tool_input": {"pattern": "*.py"}})
    assert out["audit_action"] == "accessed"


def test_audit_target_truncated_to_480(debug_inline: str, tmp_path: Path) -> None:
    """audit_target truncate budget: events.jsonl line size sanity (480 char hard limit)."""
    long_path = tmp_path / ("x" * 500 + ".txt")
    out = _run(debug_inline, {"tool_name": "Edit", "tool_input": {"file_path": str(long_path)}})
    assert len(out["audit_target"]) <= 480
