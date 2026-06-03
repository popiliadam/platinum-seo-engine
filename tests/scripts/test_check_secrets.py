"""Smoke test for scripts/security/check_secrets.sh."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "security" / "check_secrets.sh"


def test_script_exists_and_executable() -> None:
    assert SCRIPT.exists(), f"missing: {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, "script not executable"


def test_bash_syntax_check() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_runs_clean_on_empty_dir(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GREEN" in result.stdout


def _header() -> str:
    """The leading comment block, before `set -euo pipefail`."""
    return SCRIPT.read_text(encoding="utf-8").split("set -euo pipefail", 1)[0]


def test_header_states_committed_policy_not_on_disk() -> None:
    """P2-07: the script WARNs (not fails) on a gitignored .env (see section 3:
    git check-ignore -> WARN, exit stays 0), so the policy is 'zero COMMITTED/
    tracked secrets', NOT 'zero secrets on disk'. The header must say so."""
    header = _header()
    assert "Zero-secrets-on-disk" not in header, (
        "header still claims 'Zero-secrets-on-disk' but a gitignored local .env "
        "only WARNs (exit 0) — the policy is zero COMMITTED/tracked secrets"
    )
    assert ("committed" in header.lower()) or ("tracked" in header.lower()), (
        "header must state the committed/tracked-secrets policy"
    )
    assert ("WARN" in header) and ("gitignore" in header.lower()), (
        "header must document the gitignored-.env WARN allowance so the wording "
        "and the code agree"
    )
