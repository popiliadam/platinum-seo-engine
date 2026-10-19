"""A gitignored local .env is a WARN in full-mode scans too (policy header).

The K-11 unquoted DataForSEO pattern matched the operator's real workspace
.env and turned a full workspace scan red; --scan-stdin already applied the
gitignored-.env carve-out, full mode did not.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "scripts" / "security" / "check_secrets.sh"
LINE = "DATAFORSEO" + "_PASSWORD=" + "a1b2c3d4e5f6g7h8" + "\n"


def _repo(tmp_path: Path, ignored: bool) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if ignored:
        (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env").write_text(LINE, encoding="utf-8")
    return tmp_path


def _scan(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCANNER), str(root)], capture_output=True, text=True, timeout=120)


def test_gitignored_env_hit_is_only_a_warning(tmp_path: Path) -> None:
    proc = _scan(_repo(tmp_path, ignored=True))
    assert proc.returncode == 0, proc.stdout
    assert "WARN: dataforseo_env_unquoted in gitignored local .env" in proc.stdout


def test_tracked_env_hit_still_fails(tmp_path: Path) -> None:
    proc = _scan(_repo(tmp_path, ignored=False))
    assert proc.returncode == 1, proc.stdout
