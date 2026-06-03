"""tests/hooks/test_pre_tool_use_owner_lock_paths.py — P1-07.

The PreToolUse Excel owner-lock Bash-branch regex [\\w/.-]+...\\.xlsx misses
master paths that are double-quoted (with spaces), single-quoted, or ~-prefixed:
the char class can't span a space and excludes '~', so the sidecar check ran
against a wrong/relative path and failed to block. With a ~$ owner-lock sidecar
present, those path forms MUST still block (exit 2). The Edit/Write branch already
parses file_path correctly and is left unchanged.
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
HOOK_PATH = REPO_ROOT / "hooks" / "pre-tool-use.json"


def _excel_lock_command() -> str:
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    return spec["hooks"]["PreToolUse"][0]["hooks"][0]["command"]


def _inline_python(cmd: str) -> str:
    m = re.search(r"python3 -c '([^']+(?:'\\\\''[^']*)*)'", cmd)
    assert m, f"Could not extract inline python from: {cmd!r}"
    return m.group(1)


@pytest.fixture
def hook_inline() -> str:
    return _inline_python(_excel_lock_command())


def _run(inline: str, payload: dict, env: dict | None = None) -> int:
    full_env = {**os.environ}
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, "-c", inline],
        input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=full_env,
    )
    return proc.returncode


def _master_with_sidecar(d: Path) -> Path:
    """Create d/master.xlsx + its ~$master.xlsx owner-lock sidecar."""
    d.mkdir(parents=True, exist_ok=True)
    master = d / "master.xlsx"
    master.write_bytes(b"\x00")
    (d / "~$master.xlsx").write_bytes(b"\x00")
    return master


def test_double_quoted_spaced_path_blocks(tmp_path: Path, hook_inline: str) -> None:
    master = _master_with_sidecar(tmp_path / "my sheets")
    cmd = f'libreoffice "{master}"'
    rc = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 2, "double-quoted master path with a space must block when sidecar present"


def test_single_quoted_spaced_path_blocks(tmp_path: Path, hook_inline: str) -> None:
    master = _master_with_sidecar(tmp_path / "my sheets")
    cmd = f"cat '{master}'"
    rc = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 2, "single-quoted master path with a space must block when sidecar present"


def test_tilde_prefixed_path_blocks(tmp_path: Path, hook_inline: str) -> None:
    home = tmp_path / "home"
    _master_with_sidecar(home / "sheets")
    cmd = "cat ~/sheets/master.xlsx"
    rc = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}},
              env={"HOME": str(home)})
    assert rc == 2, "~-prefixed master path must expand and block when sidecar present"


def test_quoted_spaced_path_without_sidecar_allows(tmp_path: Path, hook_inline: str) -> None:
    d = tmp_path / "my sheets"
    d.mkdir(parents=True)
    master = d / "master.xlsx"
    master.write_bytes(b"\x00")  # no sidecar → not locked
    cmd = f'libreoffice "{master}"'
    rc = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 0, "no sidecar → allow even for a quoted/spaced master path"
