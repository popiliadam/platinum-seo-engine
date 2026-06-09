"""tests/hooks/test_env_probe.py — AMO batch 0a cross-environment hook probe.

The probe is temporary diagnostic instrumentation: it records, per hook event,
the SAFE shape of the stdin payload (keys only — never message/prompt/tool_input
VALUES) plus a small set of env-var presence flags, one JSON line per fire. The
manager later runs ``env_probe_report.py`` across VSCode / Mac-app / CLI to learn
whether a stable ``session_id`` reaches hooks (the AMO per-session binding key).

Contract under test:
  * ``extract_probe_record`` is PURE — payload+environ+cwd+now_iso in, safe dict
    out, no I/O, no mutation, and CANNOT echo a secret carried in a VALUE.
  * ``env_probe.py`` main is NON-BLOCKING — always exit 0, tolerates empty and
    malformed stdin (records ``_stdin_parse_error``), appends exactly one line.
  * ``env_probe_report.py`` groups by ``session_id`` and emits an N/5 stability
    verdict per session.

NOTE (codex-hostile-audit #17): the probe has been UNWIRED from all five
lifecycle events — the AMO batch-0a session-binding question it existed to answer
is settled. The two wiring assertions (probe-in-all-five / plugin-agnostic-as-
wired) were therefore removed; the remaining behaviour tests still pass because
``env_probe.py`` + ``env_probe_report.py`` are still present, now ORPHANED on
disk. Those two scripts AND this test file are a deletion bundle the manager
removes with consent at integration — a bare ``rm`` here trips the engine's own
outward-action fs_delete consent gate (the unwired guarantee is locked by
``tests/hooks/test_hook_scripts_runtime_vs_ci.py``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.hooks.env_probe import extract_probe_record

_REPO = Path(__file__).resolve().parents[2]
_PROBE = _REPO / "scripts" / "hooks" / "env_probe.py"
_REPORT = _REPO / "scripts" / "hooks" / "env_probe_report.py"

# The five lifecycle events the probe must fire on -> their hooks/*.json file.
_EVENT_FILES = {
    "SessionStart": "session-start.json",
    "UserPromptSubmit": "user-prompt-submit.json",
    "PreToolUse": "pre-tool-use.json",
    "PostToolUse": "post-tool-use.json",
    "Stop": "stop.json",
}


# --------------------------------------------------------------------------
# File presence
# --------------------------------------------------------------------------

def test_probe_and_report_scripts_exist() -> None:
    assert _PROBE.is_file(), f"missing probe script: {_PROBE}"
    assert _REPORT.is_file(), f"missing report script: {_REPORT}"


# --------------------------------------------------------------------------
# extract_probe_record — pure, safe extraction
# --------------------------------------------------------------------------

def test_extract_full_payload_carries_safe_fields() -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "abc-123",
        "transcript_path": "/Users/x/.claude/projects/p/abc-123.jsonl",
        "cwd": "/Users/x/proj",
        "tool_name": "Read",
        "tool_input": {"file_path": "/tmp/x"},
        "request_id": "req-7",
    }
    environ = {"CLAUDE_PLUGIN_ROOT": "/plugin", "CLAUDECODE": "1"}

    rec = extract_probe_record(payload, environ, "/os/cwd", "2026-06-05T00:00:00")

    assert rec["ts"] == "2026-06-05T00:00:00"
    assert rec["hook_event_name"] == "PreToolUse"
    assert rec["session_id"] == "abc-123"
    assert rec["transcript_path"] == payload["transcript_path"]
    assert rec["cwd_payload"] == "/Users/x/proj"
    assert rec["cwd_os"] == "/os/cwd"
    # structure only — the FULL sorted key list, including value-bearing keys.
    assert rec["stdin_keys"] == sorted(payload.keys())
    # other id-bearing keys are captured by key (short scalar values only),
    # but session_id is NOT duplicated here.
    assert rec["other_id_keys"] == {"request_id": "req-7"}
    assert "session_id" not in rec["other_id_keys"]
    # env presence + non-secret values
    assert rec["env_present"]["CLAUDE_PLUGIN_ROOT"] is True
    assert rec["env_present"]["CLAUDECODE"] is True
    assert rec["env_present"]["PSEO_WORKSPACE_ROOT"] is False
    assert rec["env_present"]["CLAUDE_PROJECT_DIR"] is False
    assert rec["env_values"]["CLAUDE_PLUGIN_ROOT"] == "/plugin"
    assert rec["env_values"]["CLAUDE_ENV_FILE"] is None


def test_extract_missing_session_id_is_none_no_exception() -> None:
    payload = {"hook_event_name": "Stop"}
    rec = extract_probe_record(payload, {}, "/c", "t")
    assert rec["session_id"] is None
    assert rec["transcript_path"] is None
    assert rec["cwd_payload"] is None
    assert rec["stdin_keys"] == ["hook_event_name"]
    assert rec["other_id_keys"] == {}


def test_extract_does_not_call_input_a_mutation() -> None:
    """Purity: extract must not mutate the payload it is handed."""
    payload = {"hook_event_name": "Stop", "session_id": "s", "tool_input": {"a": 1}}
    before = json.dumps(payload, sort_keys=True)
    extract_probe_record(payload, {}, "/c", "t")
    assert json.dumps(payload, sort_keys=True) == before


def test_extract_never_leaks_secret_values() -> None:
    """SECURITY: a secret in a VALUE must never appear in the record; the KEY
    that carried it must still show up in stdin_keys (structure is recorded)."""
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "Bash",
        "tool_input": {"command": "export SECRET=sk-LEAKME"},
        "tool_response": {"stdout": "sk-LEAKME on stdout"},
        "prompt": "please run sk-LEAKME",
        # a long id-like value must NOT be captured (>120 chars guard)
        "trace_id": "x" * 200,
    }
    rec = extract_probe_record(payload, {}, "/c", "t")
    blob = json.dumps(rec)
    assert "sk-LEAKME" not in blob
    assert "tool_input" in rec["stdin_keys"]
    assert "tool_response" in rec["stdin_keys"]
    assert "prompt" in rec["stdin_keys"]
    # the oversized trace_id value is dropped from other_id_keys
    assert "trace_id" not in rec["other_id_keys"]


# --------------------------------------------------------------------------
# main() — append-one-line, non-blocking, fault-tolerant
# --------------------------------------------------------------------------

def _run_probe(stdin: str, log: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_PROBE)],
        input=stdin,
        env={**os.environ, "PSEO_PROBE_LOG": str(log)},
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_main_appends_exactly_one_valid_json_line(tmp_path: Path) -> None:
    log = tmp_path / "probe.jsonl"
    payload = {"hook_event_name": "SessionStart", "session_id": "sess-1", "cwd": "/x"}
    proc = _run_probe(json.dumps(payload), log)

    assert proc.returncode == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])  # round-trips
    assert rec["session_id"] == "sess-1"
    assert rec["hook_event_name"] == "SessionStart"
    assert rec["cwd_payload"] == "/x"
    assert "_stdin_parse_error" not in rec


def test_main_appends_are_additive(tmp_path: Path) -> None:
    log = tmp_path / "probe.jsonl"
    _run_probe(json.dumps({"hook_event_name": "PreToolUse", "session_id": "s"}), log)
    _run_probe(json.dumps({"hook_event_name": "Stop", "session_id": "s"}), log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(x)["hook_event_name"] for x in lines] == ["PreToolUse", "Stop"]


def test_main_empty_stdin_exits_zero_marks_parse_error(tmp_path: Path) -> None:
    log = tmp_path / "probe.jsonl"
    proc = _run_probe("", log)
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["_stdin_parse_error"] is True
    assert rec["session_id"] is None


def test_main_malformed_stdin_exits_zero_marks_parse_error(tmp_path: Path) -> None:
    log = tmp_path / "probe.jsonl"
    proc = _run_probe("{not valid json", log)
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["_stdin_parse_error"] is True


def test_main_creates_parent_dir(tmp_path: Path) -> None:
    log = tmp_path / "nested" / "deep" / "probe.jsonl"
    proc = _run_probe(json.dumps({"hook_event_name": "Stop", "session_id": "s"}), log)
    assert proc.returncode == 0
    assert log.is_file()


# --------------------------------------------------------------------------
# env_probe_report.py — per-session N/5 stability verdict
# --------------------------------------------------------------------------

def test_report_two_sessions_prints_verdicts(tmp_path: Path) -> None:
    log = tmp_path / "probe.jsonl"
    rows: list = []
    # sess-A: all five events -> 5/5, present -> YES
    for event in _EVENT_FILES:
        rows.append({"session_id": "sess-A", "hook_event_name": event})
    # sess-B: two events -> 2/5, present -> YES
    rows.append({"session_id": "sess-B", "hook_event_name": "PreToolUse"})
    rows.append({"session_id": "sess-B", "hook_event_name": "Stop"})
    # null bucket: session_id absent -> NO
    rows.append({"session_id": None, "hook_event_name": "Stop"})

    serialized = [json.dumps(r) for r in rows]
    serialized.append("{ this line is not json")  # must be skipped + counted
    log.write_text("\n".join(serialized) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(_REPORT), str(log)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "sess-A" in out
    assert "sess-B" in out
    assert "5/5" in out
    assert "2/5" in out
    assert "YES" in out
    assert "NO" in out  # the null-session bucket
    assert "1" in out  # one unparseable line reported as skipped


def test_report_missing_log_is_graceful(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(_REPORT), str(tmp_path / "does-not-exist.jsonl")],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr
