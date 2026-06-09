"""tests/hooks/test_pre_tool_use_excel_lock.py — Excel lock check coverage (Tier 2 B1).

Coverage matrix:
  - matcher includes Bash (Tier 1 A2 fix)
  - Edit/Write file_path master.xlsx + sidecar present → EXIT 2 BLOCKED
  - Edit/Write file_path master.xlsx + sidecar absent → EXIT 0 ALLOW
  - Bash command master.xlsx mention + sidecar present → EXIT 2 BLOCKED (Tier 1 A2)
  - Bash command master.xlsx mention + sidecar absent → EXIT 0 ALLOW
  - Bash command non-Excel → EXIT 0 ALLOW
  - Path varyasyonları: master.xlsx + _MASTER.xlsx + -master.xlsx
  - Edge: Bash empty command, non-master xlsx (regex non-match), Edit non-master file
"""

from __future__ import annotations

import json
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


def _run(inline: str, payload: dict) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-c", inline],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode, proc.stderr


def test_matcher_includes_bash() -> None:
    """Tier 1 A2 fix: matcher 'Edit|Write' → 'Edit|Write|Bash'. codex-hostile-
    audit #1 additionally added NotebookEdit so the pending-bytes secret gate
    fires on notebook writes too. Assert membership (not exact equality) so the
    matcher can grow as new write-shaped tools are gated."""
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    matcher = spec["hooks"]["PreToolUse"][0]["matcher"]
    tools = matcher.split("|")
    for tool in ("Edit", "Write", "Bash", "NotebookEdit"):
        assert tool in tools, f"matcher must include {tool}; got {matcher!r}"


def test_edit_master_xlsx_with_sidecar_blocks(tmp_path: Path, hook_inline: str) -> None:
    locked = tmp_path / "master.xlsx"
    locked.write_bytes(b"\x00")
    sidecar = tmp_path / "~$master.xlsx"
    sidecar.write_bytes(b"\x00")
    rc, stderr = _run(hook_inline, {"tool_name": "Edit", "tool_input": {"file_path": str(locked)}})
    assert rc == 2, f"Expected BLOCK; rc={rc}, stderr={stderr!r}"
    assert "BLOCKED" in stderr


def test_edit_master_xlsx_no_sidecar_allows(tmp_path: Path, hook_inline: str) -> None:
    f = tmp_path / "master.xlsx"
    f.write_bytes(b"\x00")
    rc, _ = _run(hook_inline, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    assert rc == 0


def test_write_master_xlsx_with_sidecar_blocks(tmp_path: Path, hook_inline: str) -> None:
    locked = tmp_path / "master.xlsx"
    locked.write_bytes(b"\x00")
    sidecar = tmp_path / "~$master.xlsx"
    sidecar.write_bytes(b"\x00")
    rc, _ = _run(hook_inline, {"tool_name": "Write", "tool_input": {"file_path": str(locked)}})
    assert rc == 2


def test_bash_master_xlsx_with_sidecar_blocks(tmp_path: Path, hook_inline: str) -> None:
    """Tier 1 A2 fix kalıcı: Bash command master.xlsx mention + sidecar → BLOCK."""
    locked = tmp_path / "master.xlsx"
    locked.write_bytes(b"\x00")
    sidecar = tmp_path / "~$master.xlsx"
    sidecar.write_bytes(b"\x00")
    cmd = f"python3 -c 'import openpyxl; openpyxl.load_workbook(\"{locked}\")'"
    rc, stderr = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 2, f"Expected BLOCK; rc={rc}, stderr={stderr!r}"
    assert "BLOCKED" in stderr


def test_bash_master_xlsx_no_sidecar_allows(tmp_path: Path, hook_inline: str) -> None:
    f = tmp_path / "master.xlsx"
    f.write_bytes(b"\x00")
    cmd = f"head {f}"
    rc, _ = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 0


def test_bash_non_excel_allows(hook_inline: str) -> None:
    rc, _ = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": "ls /tmp"}})
    assert rc == 0


def test_bash_underscore_master_variant_blocks(tmp_path: Path, hook_inline: str) -> None:
    """Path varyasyon: <prefix>_MASTER.xlsx + sidecar → BLOCK."""
    locked = tmp_path / "alpha_MASTER.xlsx"
    locked.write_bytes(b"\x00")
    sidecar = tmp_path / "~$alpha_MASTER.xlsx"
    sidecar.write_bytes(b"\x00")
    cmd = f"cp {locked} /tmp/x.xlsx"
    rc, _ = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 2


def test_bash_dash_master_variant_blocks(tmp_path: Path, hook_inline: str) -> None:
    """Path varyasyon: <prefix>-master.xlsx + sidecar → BLOCK."""
    locked = tmp_path / "beta-master.xlsx"
    locked.write_bytes(b"\x00")
    sidecar = tmp_path / "~$beta-master.xlsx"
    sidecar.write_bytes(b"\x00")
    cmd = f"echo X >> {locked}"
    rc, _ = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 2


def test_bash_empty_command_allows(hook_inline: str) -> None:
    rc, _ = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": ""}})
    assert rc == 0


def test_bash_other_xlsx_no_match_allows(tmp_path: Path, hook_inline: str) -> None:
    """Regex master pattern non-match: 'other.xlsx' (no _MASTER/-master/master suffix)."""
    f = tmp_path / "other.xlsx"
    f.write_bytes(b"\x00")
    cmd = f"head {f}"
    rc, _ = _run(hook_inline, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert rc == 0


def test_edit_non_master_file_allows(tmp_path: Path, hook_inline: str) -> None:
    f = tmp_path / "foo.txt"
    f.write_text("hello")
    rc, _ = _run(hook_inline, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    assert rc == 0
