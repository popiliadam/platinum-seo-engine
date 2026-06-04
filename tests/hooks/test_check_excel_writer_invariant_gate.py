"""codex-audit finding 14: check_excel_writer's commit-message writer signal is
spoofable (any commit mentioning 'transaction.py' was accepted). The fix keeps
that signal ADVISORY but adds an AUTHORITATIVE artifact gate — a staged
master.xlsx that is invariant-RED is rejected even WITH the signal. The gate is
fail-safe: unloadable / non-workspace workbooks fall through to the advisory path.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "scripts" / "hooks" / "check_excel_writer.py"

_spec = importlib.util.spec_from_file_location("check_excel_writer", HOOK)
cew = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cew)


def _red_workbook(path: Path) -> None:
    """A master.xlsx whose master_task has the wrong column count -> F-05
    CRITICAL -> overall RED (verified independently)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "master_task"
    ws.append(["task_id", "status", "foo"])
    ws.append(["t-1", "TODO", "x"])
    wb.save(path)


def test_helper_flags_red_workbook(tmp_path):
    wb = tmp_path / "projects" / "demo" / "master.xlsx"
    _red_workbook(wb)
    assert cew._workbook_invariant_red(str(wb)) is True


def test_helper_failsafe_on_missing_or_non_project_paths(tmp_path):
    # missing file -> False (fail-safe)
    assert cew._workbook_invariant_red(str(tmp_path / "nope.xlsx")) is False
    # real workbook but NOT under a projects/<slug>/ tree -> slug unresolvable -> False
    flat = tmp_path / "master.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["a"])
    wb.save(flat)
    assert cew._workbook_invariant_red(str(flat)) is False


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_red_workbook_blocked_despite_commit_signal(tmp_path):
    _git(["init", "-q", "-b", "main"], tmp_path)
    _git(["config", "user.email", "t@t"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)
    _red_workbook(tmp_path / "projects" / "demo" / "master.xlsx")
    _git(["add", "projects/demo/master.xlsx"], tmp_path)
    msg = tmp_path / "msg.txt"
    msg.write_text("ingest via transaction.py\n")  # the spoofable advisory signal

    res = subprocess.run(
        [sys.executable, str(HOOK), "--staged", "--commit-msg-file", str(msg)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert res.returncode == 1, (
        "RED workbook must be blocked despite the commit-message signal:\n"
        f"{res.stdout}\n{res.stderr}"
    )
    assert "invariant-RED" in res.stderr
