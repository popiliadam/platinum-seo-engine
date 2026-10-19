"""Security-review follow-ups to G-01.

1. A delete path is judged after normalisation: ``outputs/../..`` is not "temp",
   and an operand the gate cannot resolve (``$VAR``, backticks, ``~``) is never
   temp either.
2. Forgery through a script FILE: writing a helper that appends to the ledger
   and then running it is caught by scanning the script the interpreter runs.
3. The installed plugin (the gate and its policy) cannot be edited by the model.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.hooks import outward_action_gate as gate


def _tier(cmd: str) -> str:
    return gate.assess("Bash", {"command": cmd}).tier


@pytest.mark.parametrize("cmd", [
    "rm -rf outputs/../../other-project",
    "rm -rf /tmp/../Users/someone/work",
    "rm -rf scratchpad/../../..",
    "rm -rf $OUT/x",
    "rm -rf `pwd`/outputs",
    "rm -rf ~/outputs-like",
])
def test_unresolvable_or_escaping_paths_are_not_temp(cmd: str) -> None:
    assert _tier(cmd) == "onayli"


def test_plain_outputs_path_is_still_free() -> None:
    assert _tier("rm -rf outputs/run1/../run2") == "serbest"


def test_script_file_that_writes_the_ledger_is_forgery(tmp_path: Path) -> None:
    script = tmp_path / "helper.py"
    script.write_text(
        "from scripts.state.consent_ledger import append_consent\n"
        "append_consent(workspace_root='w', project_slug='p', run_id='r',"
        " action='git_push', target='x', granted_by='me', now_iso='t')\n",
        encoding="utf-8",
    )
    assert gate.is_consent_forgery("Bash", {"command": f"python3 {script}"})
    assert gate.is_consent_forgery("Bash", {"command": f"cd /x && PYTHONPATH=. python3 {script} --go"})


def test_ordinary_script_is_not_forgery(tmp_path: Path) -> None:
    script = tmp_path / "report.py"
    script.write_text("print('hello')\n", encoding="utf-8")
    assert not gate.is_consent_forgery("Bash", {"command": f"python3 {script}"})


def test_editing_the_installed_plugin_is_denied(tmp_path: Path, monkeypatch) -> None:
    installed = tmp_path / "plugins" / "cache" / "platinum-seo-engine" / "2.1.4"
    (installed / "scripts" / "hooks").mkdir(parents=True)
    monkeypatch.setattr(gate, "_PLUGIN_ROOT", str(installed))
    for path in (installed / "scripts" / "hooks" / "consent_policy.json",
                 installed / "scripts" / "hooks" / "outward_action_gate.py"):
        assert gate.is_consent_forgery("Edit", {"file_path": str(path)})
    assert not gate.is_consent_forgery("Edit", {"file_path": str(tmp_path / "repo" / "x.py")})
