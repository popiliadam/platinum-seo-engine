"""tests/hooks/test_pre_tool_use_secret_scan_invocation.py — secret scan hook contract.

Coverage:
  1. Second hook entry must invoke ${CLAUDE_PLUGIN_ROOT}/scripts/security/check_secrets.sh
  2. Hook arg is ${CLAUDE_PROJECT_DIR:-.} (plugin agnostik path resolution)
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


def _secret_scan_handler() -> dict:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    handlers = spec["hooks"]["PreToolUse"][0]["hooks"]
    assert len(handlers) >= 2, "PreToolUse must have at least 2 hooks (Excel lock + secret scan)"
    return handlers[1]


def test_secret_scan_hook_present() -> None:
    handler = _secret_scan_handler()
    assert handler["type"] == "command"
    assert "check_secrets.sh" in handler["command"]


def test_secret_scan_uses_plugin_root_path() -> None:
    """Plugin agnostik discipline (F-16): hook resolves script via $CLAUDE_PLUGIN_ROOT."""
    handler = _secret_scan_handler()
    assert "CLAUDE_PLUGIN_ROOT" in handler["command"], (
        "Plugin agnostik path resolution required (F-16 invariant)"
    )


def test_secret_scan_passes_project_dir_arg() -> None:
    """Hook passes ${CLAUDE_PROJECT_DIR:-.} so scan scope follows project boundary."""
    handler = _secret_scan_handler()
    assert "CLAUDE_PROJECT_DIR" in handler["command"]


def test_secret_scan_timeout_sane() -> None:
    """Timeout must allow large workspace scan (>=30s)."""
    handler = _secret_scan_handler()
    assert handler.get("timeout", 0) >= 30, (
        f"timeout must be >=30s for large workspace tolerance; got {handler.get('timeout')}"
    )


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
