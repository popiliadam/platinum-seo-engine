"""tests/hooks/test_check_events_writer.py — PreToolUse events.jsonl writer guard.

TDD lock for scripts/hooks/check_events_writer.py.

Why it exists: between 2026-07-09 and 2026-08-06, agent sessions appended 93 rows
straight into projects/*/_state/events.jsonl instead of calling
scripts/state/events_writer.py — which validates against events.schema.json
BEFORE appending and would have rejected every one of them. Nothing in the
pre-commit layer could see it (the ledger is gitignored operator data), and the
compliance test skips when no workspace is bound, so the drift sat unseen for a
month. This guard closes the write boundary itself.

Shape mirrors outward_action_gate:

  * classify() — PURE (no IO): (tool_name, tool_input) -> the ledger path the
    call would WRITE, else None. CONSERVATIVE in the direction that matters
    here: READING the ledger must never be blocked, because diagnosis, reporting
    and the migration all read it constantly.
  * evaluate() — (0, []) allow / (2, messages) deny, message naming the writer.
  * main() — stdin JSON payload, exit 2 on deny.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks import check_events_writer as guard

_REPO = Path(__file__).resolve().parents[2]
_GUARD = _REPO / "scripts" / "hooks" / "check_events_writer.py"

LEDGER = "/ws/projects/vento/_state/events.jsonl"


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ===========================================================================
# classify() — writes are caught
# ===========================================================================

def test_write_tool_targeting_the_ledger_is_caught():
    assert guard.classify("Write", {"file_path": LEDGER}) == LEDGER


def test_edit_tool_targeting_the_ledger_is_caught():
    assert guard.classify("Edit", {"file_path": LEDGER}) == LEDGER


def test_bash_append_redirect_is_caught():
    assert guard.classify(*_bash(f"echo '{{}}' >> {LEDGER}").values()) == LEDGER


def test_bash_overwrite_redirect_is_caught():
    assert guard.classify(*_bash(f"printf '' > {LEDGER}").values()) == LEDGER


def test_bash_redirect_to_a_quoted_path_is_caught():
    assert guard.classify(*_bash(f'echo x >> "{LEDGER}"').values()) == LEDGER


def test_bash_tee_into_the_ledger_is_caught():
    assert guard.classify(*_bash(f"echo x | tee -a {LEDGER}").values()) == LEDGER


def test_bash_in_place_edit_is_caught():
    assert guard.classify(*_bash(f"sed -i '' 's/a/b/' {LEDGER}").values()) == LEDGER


def test_bash_copy_ONTO_the_ledger_is_caught():
    assert guard.classify(*_bash(f"cp /tmp/rows.jsonl {LEDGER}").values()) == LEDGER


def test_a_write_in_a_later_segment_is_caught():
    """`cd x && echo … >> ledger` — the write is not the leading token."""
    cmd = f"cd /ws && echo '{{}}' >> {LEDGER}"
    assert guard.classify(*_bash(cmd).values()) == LEDGER


# ===========================================================================
# classify() — reads and legitimate writers are NOT caught
#
# This half matters more than the half above: a guard that blocks reading the
# ledger would brick diagnosis, monthly reporting and the migration itself.
# ===========================================================================

@pytest.mark.parametrize("command", [
    f"cat {LEDGER}",
    f"grep work_completed {LEDGER}",
    f"wc -l < {LEDGER}",
    f"tail -5 {LEDGER}",
    f"python3 -c \"print(open('{LEDGER}').read())\"",
    f"jq -r .event_kind {LEDGER}",
])
def test_reading_the_ledger_is_allowed(command):
    assert guard.classify(*_bash(command).values()) is None


def test_copying_the_ledger_AWAY_is_allowed():
    """The ledger is the SOURCE here — a backup, not a write."""
    assert guard.classify(*_bash(f"cp {LEDGER} /tmp/backup.jsonl").values()) is None


def test_the_sanctioned_migration_is_allowed():
    cmd = ("python3 scripts/state/migrate_legacy_events.py "
           "--workspace /ws --project vento")
    assert guard.classify(*_bash(cmd).values()) is None


def test_the_sanctioned_writer_is_allowed():
    cmd = ("python3 -c \"from scripts.state import events_writer; "
           "events_writer.append_work(project_id='vento', event_type='tech_fix', "
           "task_id='T-01621')\"")
    assert guard.classify(*_bash(cmd).values()) is None


@pytest.mark.parametrize("path", [
    "/ws/projects/vento/_state/events.jsonl.legacy",
    "/ws/projects/vento/_state/events.jsonl.bak",
])
def test_the_archives_are_not_the_live_ledger(path):
    """.legacy and .bak are the migration's own outputs, not the strict ledger."""
    assert guard.classify("Write", {"file_path": path}) is None
    assert guard.classify(*_bash(f"echo x >> {path}").values()) is None


def test_a_jsonl_outside_state_is_not_the_ledger():
    """Only _state/events.jsonl is the ledger; a same-named file elsewhere isn't."""
    assert guard.classify("Write", {"file_path": "/tmp/events.jsonl"}) is None


def test_an_unrelated_file_is_allowed():
    assert guard.classify("Write", {"file_path": "/ws/projects/vento/master.xlsx"}) is None


def test_a_non_writing_tool_is_allowed():
    assert guard.classify("Read", {"file_path": LEDGER}) is None


# ===========================================================================
# evaluate() — decision + remediation
# ===========================================================================

def test_a_caught_write_is_denied():
    code, messages = guard.evaluate({"tool_name": "Write", "tool_input": {"file_path": LEDGER}})
    assert code == 2
    assert messages


def test_the_denial_names_the_writer_to_use_instead():
    """A block that doesn't say what to do instead just gets worked around."""
    _code, messages = guard.evaluate({"tool_name": "Write", "tool_input": {"file_path": LEDGER}})
    assert any("events_writer" in m for m in messages)


def test_an_allowed_call_produces_no_message():
    assert guard.evaluate(_bash(f"cat {LEDGER}")) == (0, [])


def test_the_escape_hatch_allows_an_intentional_direct_write(monkeypatch):
    """Migration/recovery needs a documented way through — mirrors
    check_excel_writer's PSEO_EXCEL_WRITER signal."""
    monkeypatch.setenv("PSEO_EVENTS_WRITER", "events_writer.py")
    assert guard.evaluate({"tool_name": "Write", "tool_input": {"file_path": LEDGER}}) == (0, [])


def test_a_malformed_payload_never_bricks_the_tool():
    assert guard.evaluate("not-a-dict") == (0, [])
    assert guard.evaluate({}) == (0, [])


# ===========================================================================
# main() — the hook as the harness actually runs it
# ===========================================================================

def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_GUARD)],
        input=json.dumps(payload), text=True, capture_output=True, cwd=str(_REPO),
    )


def test_hook_exits_2_and_explains_on_a_direct_write():
    proc = _run({"tool_name": "Write", "tool_input": {"file_path": LEDGER}})
    assert proc.returncode == 2
    assert "events_writer" in proc.stderr


def test_hook_exits_0_on_a_read():
    proc = _run(_bash(f"cat {LEDGER}"))
    assert proc.returncode == 0


# ===========================================================================
# classify() — Python writing the ledger directly (2026-10-02 diagnosis)
#
# Between 2026-08-08 and 08-24, 31 off-schema rows reached live ledgers through
# inline Python — a heredoc or `-c` that open()s the ledger in append mode —
# a shape the redirect/tee/sed/cp checks above never look at. Each case below
# reproduces one of the measured forms with a demo slug.
# ===========================================================================

DEMO = "/ws/projects/demo-acme/_state/events.jsonl"
DEMO_DIR = "/ws/projects/demo-acme"


def _hit(command: str) -> str | None:
    return guard.classify("Bash", {"command": command})


@pytest.mark.parametrize("command", [
    # heredoc, absolute literal bound to a name, then `with open(P,'a') as f: f.write`
    "python3 - <<'PY'\n"
    "import json, uuid\n"
    f"P='{DEMO}'\n"
    "ev={'event_kind':'provenance','event_id':uuid.uuid4().hex}\n"
    "with open(P,'a') as f: f.write(json.dumps(ev,ensure_ascii=False)+\"\\n\")\n"
    "PY",
    # heredoc, RELATIVE literal after a cd
    f"cd {DEMO_DIR}\n"
    "python3 - <<'PY'\n"
    "import json\n"
    "ev={'event_kind':'provenance'}\n"
    "with open('_state/events.jsonl','a') as f: f.write(json.dumps(ev)+\"\\n\")\n"
    "PY",
    # unquoted delimiter + env prefix (shell expands $P inside the body)
    f"P={DEMO_DIR}\n"
    "PYTHONPATH=/engine python3 - <<PYEOF\n"
    "import json\n"
    "open('$P/_state/events.jsonl', mode='a', encoding='utf-8').write('{}\\n')\n"
    "PYEOF",
    # f-string path
    "python3 - <<'PY'\n"
    f"P='{DEMO_DIR}'\n"
    "with open(f\"{P}/_state/events.jsonl\", \"a\", encoding=\"utf-8\") as f:\n"
    "    f.write('{}\\n')\n"
    "PY",
    # Path(...).open('a')
    "python3 - <<'PY'\n"
    "from pathlib import Path\n"
    f"Path('{DEMO}').open('a').write('{{}}\\n')\n"
    "PY",
    # pathlib division built from parts
    "python3 - <<'PY'\n"
    "from pathlib import Path\n"
    "ws = Path('/ws')\n"
    "ledger = ws / 'projects' / 'demo-acme' / '_state' / 'events.jsonl'\n"
    "with ledger.open(mode='a') as fh:\n"
    "    fh.write('{}\\n')\n"
    "PY",
    # os.path.join
    "python3 - <<'PY'\n"
    "import os\n"
    f"P='{DEMO_DIR}'\n"
    "open(os.path.join(P, '_state', 'events.jsonl'), 'a').write('{}\\n')\n"
    "PY",
    # overwrite rather than append is a write too
    "python3 - <<'PY'\n"
    f"open('{DEMO}', 'w').write('')\n"
    "PY",
    # write_text replaces the whole ledger
    "python3 - <<'PY'\n"
    "from pathlib import Path\n"
    "Path('_state/events.jsonl').write_text('')\n"
    "PY",
    # `-c`, absolute
    f"python3 -c \"open('{DEMO}','a').write('{{}}\\n')\"",
    # `-c`, relative, in a later shell segment
    f"cd {DEMO_DIR} && python3 -c \"import json; open('_state/events.jsonl','a').write(json.dumps({{}}))\"",
    # `-c` with single quotes around the code
    f"python -c 'with open(\"{DEMO}\", \"a\") as f: f.write(\"x\")'",
])
def test_inline_python_writing_the_ledger_is_caught(command):
    hit = _hit(command)
    assert hit is not None
    assert hit.endswith("events.jsonl")


@pytest.mark.parametrize("command", [
    # reading: open() with no mode, 'r', 'rb', json.loads per line
    "python3 - <<'PY'\n"
    "import json\n"
    f"P='{DEMO}'\n"
    "rows=[json.loads(l) for l in open(P)]\n"
    "print(len(rows))\n"
    "PY",
    f"python3 -c \"import json; print(sum(1 for _ in open('{DEMO}', 'r')))\"",
    f"python3 -c \"print(len(open('{DEMO}', 'rb').read()))\"",
    "python3 - <<'PY'\n"
    "from pathlib import Path\n"
    f"print(Path('{DEMO}').read_text().count('\\n'))\n"
    f"with Path('{DEMO}').open(encoding='utf-8') as fh:\n"
    "    print(fh.readline())\n"
    "PY",
    # read the ledger, write an UNRELATED file
    "python3 - <<'PY'\n"
    "import json\n"
    f"line=open('{DEMO}').readlines()[-1]\n"
    "json.dump(json.loads(line), open('/tmp/ev.json','w'))\n"
    "PY",
    # the sanctioned writer, plus an append to a different _state file
    "PYTHONPATH=/engine python3 - <<'PYEOF'\n"
    "import json\n"
    "from pathlib import Path\n"
    "from scripts.state.events_writer import append_provenance\n"
    f"P=Path('{DEMO_DIR}')\n"
    "m=P/'_state/metrics/refresh-audit.jsonl'\n"
    "with open(m,'a',encoding='utf-8') as f: f.write(json.dumps({'run_id':1})+'\\n')\n"
    "append_provenance(project_id='demo-acme', run_id=1, source={'kind':'tool_computed'},\n"
    "                  operation='validate', workspace_root=Path('/ws'))\n"
    "PYEOF",
    # two `-c` programs in a row: the first READS the ledger, the `;` right after
    # its closing quote must not glue onto the code (replay false positive)
    f"cd {DEMO_DIR} && python3 -c \"\nimport json\n"
    "ls=[json.loads(l) for l in open('_state/events.jsonl') if l.strip()]\n"
    "json.dump(ls, open('_state/staging/link.json','w'))\n"
    "\"; python3 -c \"print('ok')\"",
    # running the test suite
    "PSEO_WORKSPACE_ROOT=/ws python3 -m pytest -p no:cacheprovider tests/state -q",
    # the migration's own archives are not the live ledger
    f"python3 -c \"open('{DEMO}.legacy','a').write('x')\"",
    f"python3 -c \"open('{DEMO}.bak','w').write('x')\"",
    "python3 - <<'PY'\n"
    f"open('{DEMO_DIR}/_state/archive/events-2026-08.jsonl','a').write('x')\n"
    f"open('{DEMO_DIR}/archive/events.jsonl','a').write('x')\n"
    "PY",
    # a non-Python heredoc that merely QUOTES ledger-writing code (a doc/note)
    "cat > /tmp/notes.md <<'MD'\n"
    "never do: with open('_state/events.jsonl','a') as f: f.write(x)\n"
    "MD",
])
def test_inline_python_that_does_not_write_the_ledger_is_allowed(command):
    assert _hit(command) is None


def test_inline_python_write_is_denied_by_the_hook():
    proc = _run(_bash(f"python3 -c \"open('{DEMO}','a').write('x')\""))
    assert proc.returncode == 2
    assert "events_writer" in proc.stderr
