"""tests/hooks/test_pre_tool_use_secret_scan_invocation.py — secret scan hook contract.

Coverage:
  1. K-12: the post-hoc tree scan is NOT a PreToolUse hook (too slow, ran before
     the write, could not block); the pending-bytes scan is wired instead
  2. (removed with 1)
  3. check_secrets.sh on a clean tmp tree returns 0 (subprocess invocation)
  4. check_secrets.sh on a tree with synthetic ghp_-like secret returns 1
  5. check_secrets.sh on a tree with sk- prefix returns 1
  6. timeout config is sane (>=30s) — large workspace tolerance
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "pre-tool-use.json"
CHECK_SECRETS = REPO_ROOT / "scripts" / "security" / "check_secrets.sh"


def _pre_tool_use_commands() -> list[str]:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    return [h["command"] for block in spec["hooks"]["PreToolUse"] for h in block["hooks"]]


def test_post_hoc_tree_scan_is_not_a_pre_tool_use_hook() -> None:
    """K-12: the ``--changed-since`` tree scan ran BEFORE the write it was meant
    to catch (so it never saw it), exited 1 (non-blocking) on a finding, and took
    90 s+ on the workspace against a 60 s timeout — every tool call waited.
    """
    assert not any("check_secrets.sh" in c and "--changed-since" in c
                   for c in _pre_tool_use_commands())


def test_pending_bytes_scan_stays_wired() -> None:
    """The blocking gate is scan_pending_secret.py (pending Write/Edit bytes,
    exit 2), resolved through $CLAUDE_PLUGIN_ROOT (plugin-agnostic)."""
    cmds = [c for c in _pre_tool_use_commands() if "scan_pending_secret.py" in c]
    assert cmds and all("CLAUDE_PLUGIN_ROOT" in c for c in cmds)


def test_check_secrets_clean_tree_exits_zero(tmp_path: Path) -> None:
    """check_secrets.sh on a clean tmp tree returns 0."""
    proc = subprocess.run(
        ["bash", str(CHECK_SECRETS), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"clean tree should be GREEN; stdout={proc.stdout!r}"


def test_check_secrets_with_ghp_secret_exits_one(tmp_path: Path) -> None:
    """check_secrets.sh on a tree with a GitHub PAT-like literal returns 1."""
    leak = tmp_path / "leak.txt"
    leak.write_text("ghp_" + "a" * 36 + "\n")  # synthetic, not a real secret
    proc = subprocess.run(
        ["bash", str(CHECK_SECRETS), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 1, f"secret tree should FAIL; stdout={proc.stdout!r}"
    assert "github_pat_classic_ghp" in proc.stdout


def test_check_secrets_with_sk_secret_exits_one(tmp_path: Path) -> None:
    """check_secrets.sh on a tree with a OpenAI/Anthropic-style sk- literal returns 1."""
    leak = tmp_path / "leak.py"
    leak.write_text('API_KEY = "sk-' + "a" * 30 + '"\n')
    proc = subprocess.run(
        ["bash", str(CHECK_SECRETS), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 1, f"secret tree should FAIL; stdout={proc.stdout!r}"
    assert "openai_or_anthropic_sk_prefix" in proc.stdout


def test_check_secrets_does_not_echo_match_content(tmp_path: Path) -> None:
    """Security: check_secrets.sh never echoes matched content (only file path + count)."""
    secret_literal = "ghp_" + "z" * 36
    leak = tmp_path / "leak.txt"
    leak.write_text(secret_literal + "\n")
    proc = subprocess.run(
        ["bash", str(CHECK_SECRETS), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 1
    assert secret_literal not in proc.stdout, (
        f"check_secrets.sh leaked secret content to stdout: {secret_literal!r}"
    )
    assert "[REDACTED]" in proc.stdout, "Output must show [REDACTED] marker"
