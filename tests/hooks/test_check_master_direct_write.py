"""tests/hooks/test_check_master_direct_write.py — PreToolUse master.xlsx direct-write guard.

TDD lock for scripts/hooks/check_master_direct_write.py.

Why it exists: ``scripts/excel/transaction.py`` is the only safe writer of a project's
``master.xlsx`` (flock sentinel + load-inside-lock + atomic replace + backup). Agent
sessions nevertheless write it with ad-hoc openpyxl snippets (measured example:
``projects/miningaa-com/_state/staging/textile_research/fix_f05.py``). Such a write takes
no lock, so a parallel ``transaction`` writer's sheet is silently reverted from a stale
in-memory workbook. ``check_excel_writer.py`` cannot see it: it runs at commit time and
master.xlsx is gitignored operator data.

Shape mirrors check_events_writer:

  * classify() — (tool_name, tool_input, cwd) -> reason string when the call would WRITE
    a master workbook outside transaction.py, else None. READING must never be blocked.
  * evaluate() — (0, []) allow / (2, messages) deny.
  * main() — stdin JSON payload; unreadable payload fails OPEN.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks import check_master_direct_write as guard

_REPO = Path(__file__).resolve().parents[2]
_GUARD = _REPO / "scripts" / "hooks" / "check_master_direct_write.py"

MASTER = "/ws/projects/vento/master.xlsx"


def _bash(command: str, cwd: str | None = None) -> dict:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def _deny(payload: dict) -> bool:
    return guard.evaluate(payload)[0] == 2


# ===========================================================================
# DENY — direct writes of a master workbook
# ===========================================================================

def test_heredoc_load_then_save_is_denied():
    cmd = (
        "python3 - <<'EOF'\n"
        "from openpyxl import load_workbook\n"
        f"wb = load_workbook('{MASTER}')\n"
        "wb['topical_map']['A2'] = 'x'\n"
        "wb.save(p)\n"
        "EOF"
    )
    assert _deny(_bash(cmd))


def test_inline_python_c_save_to_master_literal_is_denied():
    cmd = f"python3 -c \"import openpyxl; wb=openpyxl.Workbook(); wb.save('{MASTER}')\""
    assert _deny(_bash(cmd))


def test_pandas_to_excel_into_master_is_denied():
    cmd = f"python3 -c \"import pandas as pd; pd.DataFrame().to_excel('{MASTER}')\""
    assert _deny(_bash(cmd))


def test_legacy_and_suffixed_master_names_are_denied():
    for name in ("master-excel.xlsx", "vento_MASTER.xlsx", "site-master.xlsx"):
        cmd = f"python3 -c \"import openpyxl; openpyxl.Workbook().save('/ws/projects/v/{name}')\""
        assert _deny(_bash(cmd)), name


def test_script_file_that_saves_master_is_denied(tmp_path: Path):
    script = tmp_path / "fix_f05.py"
    script.write_text(
        "from openpyxl import load_workbook\n"
        f"MASTER = '{MASTER}'\n"
        "wb = load_workbook(MASTER)\n"
        "wb.save(MASTER)\n",
        encoding="utf-8",
    )
    assert _deny(_bash(f"python3 {script}"))


def test_relative_script_path_is_resolved_against_payload_cwd(tmp_path: Path):
    (tmp_path / "fix.py").write_text(
        f"from openpyxl import load_workbook\nwb = load_workbook('{MASTER}')\nwb.save('{MASTER}')\n",
        encoding="utf-8",
    )
    assert _deny(_bash("cd x && python3 fix.py", cwd=str(tmp_path)))


def test_deny_message_names_the_safe_writer_and_escape_hatch():
    code, messages = guard.evaluate(_bash(f"python3 -c \"openpyxl.Workbook().save('{MASTER}')\""))
    text = "\n".join(messages)
    assert code == 2
    assert "scripts/excel/transaction.py" in text
    assert "PSEO_EXCEL_WRITER=transaction.py" in text


# ===========================================================================
# ALLOW — reads, the safe writer, unrelated files, escape hatch, non-Bash tools
# ===========================================================================

def test_read_only_load_is_allowed():
    cmd = f"python3 -c \"from openpyxl import load_workbook; wb=load_workbook('{MASTER}', read_only=True); print(wb.sheetnames)\""
    assert not _deny(_bash(cmd))


def test_copying_master_for_backup_is_allowed():
    assert not _deny(_bash(f"cp {MASTER} /tmp/master-backup.xlsx"))


def test_saving_an_unrelated_workbook_is_allowed():
    cmd = "python3 -c \"import openpyxl; openpyxl.Workbook().save('/tmp/report.xlsx')\""
    assert not _deny(_bash(cmd))


def test_transaction_module_invocation_is_allowed():
    cmd = f"python3 -m scripts.excel.transaction append {MASTER} topical_map rows.json vento"
    assert not _deny(_bash(cmd))


def test_running_transaction_py_itself_is_allowed():
    script = _REPO / "scripts" / "excel" / "transaction.py"
    assert not _deny(_bash(f"python3 {script} --help"))


def test_command_prefixed_escape_hatch_is_allowed():
    cmd = f"PSEO_EXCEL_WRITER=transaction.py python3 -c \"openpyxl.Workbook().save('{MASTER}')\""
    assert not _deny(_bash(cmd))


def test_environment_escape_hatch_is_allowed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PSEO_EXCEL_WRITER", "transaction.py")
    assert not _deny(_bash(f"python3 -c \"openpyxl.Workbook().save('{MASTER}')\""))


def test_non_bash_tools_are_out_of_scope():
    assert not _deny({"tool_name": "Write", "tool_input": {"file_path": "/tmp/x.py", "content": f"wb.save('{MASTER}')"}})


def test_missing_script_file_is_allowed():
    assert not _deny(_bash("python3 /nonexistent/definitely_missing.py"))


def test_malformed_tool_input_is_allowed():
    assert not _deny({"tool_name": "Bash", "tool_input": "not-a-dict"})
    assert not _deny({"tool_name": "Bash", "tool_input": {"command": None}})


# ===========================================================================
# main() — real subprocess contract
# ===========================================================================

def _run_main(stdin: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PSEO_EXCEL_WRITER"}
    return subprocess.run([sys.executable, str(_GUARD)], input=stdin, capture_output=True, text=True, env=env, timeout=20)


def test_main_denies_with_exit_2():
    proc = _run_main(json.dumps(_bash(f"python3 -c \"openpyxl.Workbook().save('{MASTER}')\"")))
    assert proc.returncode == 2
    assert "BLOCKED" in proc.stderr


def test_main_fails_open_on_unreadable_payload():
    assert _run_main("{not json").returncode == 0


def test_guard_is_registered_as_a_pretooluse_bash_hook():
    spec = json.loads((_REPO / "hooks" / "pre-tool-use.json").read_text(encoding="utf-8"))
    commands = [
        (entry.get("matcher", ""), hook.get("command", ""))
        for entry in spec["hooks"]["PreToolUse"]
        for hook in entry["hooks"]
    ]
    assert any("check_master_direct_write.py" in cmd and "Bash" in matcher for matcher, cmd in commands)
