"""tests/hooks/test_pseo_approve_roundtrip.py — the gate's copy-paste approval
line must actually work, in ONE step, from the session it was printed in.

Live evidence (transcripts 2026-07-20 · 2026-08-08 · 2026-09-17 · 2026-09-18):

  1. ``Unknown command: /pseo-approve`` (CLI 2.1.209 / 2.1.271) and an
     ``unknown_command_fallback`` for ``pseo-approve`` (CLI 2.1.275) — while the
     SAME session listed the command as ``platinum-seo-engine:pseo-approve``.
     A plugin command is registered under its namespaced name; the gate printed
     the bare one.
  2. ``BLOCKED: git_push → origin main 2>&1`` / ``fs_delete → $T 2>/dev/null`` —
     the gate hashed shell REDIRECTIONS as part of the target, so a consent for
     the real object (``origin main``) could never match the re-run.
  3. The hint wrapped the target in DOUBLE quotes, so a ``$T`` was expanded and
     a target carrying ``"`` broke tokenisation inside the command's block.
  4. ``consent_ledger approve`` with ``CLAUDE_CODE_SESSION_ID`` unset printed
     "consent recorded" but stamped no session — the per-session gate can never
     match such an entry (silent failure).
  5. The command was MODEL-invocable: on 2026-08-08 the model itself called
     ``Skill(platinum-seo-engine:pseo-approve, "sess-… git_push origin main")``.
     Consent must only ever come from the human.
  6. (G-01) The model could also run the recorder CLI from Bash. Consent is now
     written by the UserPromptSubmit hook from the user's own message, and the
     gate denies every model write to the ledger. The examples below use
     consent-tier actions (a plain push to main or a single file delete no
     longer needs consent at all).

Security invariant for (2): stripping redirections must leave EXACTLY the argv
the shell passes to the command — proven here against real bash — so a consent
can never be stretched over a different file / remote.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.hooks import consent_from_prompt
from scripts.hooks import outward_action_gate as gate
from scripts.state import consent_ledger as cl
from scripts.state import session_binding as sb

_ROOT = Path(__file__).resolve().parents[2]
_CMD_FILE = _ROOT / "commands" / "pseo-approve.md"

SID = "abcdef01-2345-6789-aaaa-bbbbbbbbbbbb"

def _now_iso() -> str:
    """A consent granted NOW — the gate expires consents after a few hours (G-09)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")



def _plugin_name() -> str:
    return json.loads((_ROOT / ".claude-plugin" / "plugin.json").read_text())["name"]


def _frontmatter() -> dict:
    text = _CMD_FILE.read_text(encoding="utf-8")
    end = text.find("---", 3)
    return yaml.safe_load(text[3:end])


@pytest.fixture()
def bound_ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = tmp_path / "ws"
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    (ws / "projects" / "demo" / "_state").mkdir(parents=True)
    sb.write_session_binding(SID, "demo", ws, "2026-06-06T00:00:00")
    return ws


def _deny_hint(cmd: str) -> str:
    code, msgs = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": SID}
    )
    assert code == 2, msgs
    return msgs[1]


# ---------------------------------------------------------------------------
# (1) the hint names the command the harness actually registers
# ---------------------------------------------------------------------------

def test_hint_uses_the_namespaced_plugin_command(bound_ws: Path) -> None:
    hint = _deny_hint("git push --force origin main")
    expected = f"/{_plugin_name()}:{_CMD_FILE.stem} "
    assert expected in hint, hint
    assert " /pseo-approve " not in hint, (
        "bare /pseo-approve is not a registered command (live: 'Unknown command')"
    )


def test_hint_says_chat_not_terminal(bound_ws: Path) -> None:
    # Users pasted the line into zsh 26× ("no such file or directory: /pseo-approve").
    hint = _deny_hint("git push --force origin main")
    assert "sohbet" in hint.lower()


# ---------------------------------------------------------------------------
# (5) only the human can trigger the command
# ---------------------------------------------------------------------------

def test_approve_command_is_not_model_invocable() -> None:
    assert _frontmatter().get("disable-model-invocation") is True, (
        "pseo-approve writes consent; the model must not be able to call it via "
        "the Skill tool (observed live 2026-08-08)"
    )


# ---------------------------------------------------------------------------
# (2) redirections are not part of the target — and nothing else is dropped
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd,target", [
    ("git push origin main 2>&1", "origin main"),
    ("git push origin main >/dev/null 2>&1", "origin main"),
    ("rm -rf $T 2>/dev/null", "$T"),
    ("rm -rf ~/Library/Caches/x/* 2>/dev/null", "~/Library/Caches/x/*"),
    ("2>/dev/null rm -rf build", "build"),
])
def test_redirections_are_stripped_from_target(cmd: str, target: str) -> None:
    res = gate.classify("Bash", {"command": cmd})
    assert res is not None and res[1] == target, res


def _bash_argv(cmd: str, cwd: Path) -> list[str]:
    """argv the shell really hands to rm / git for ``cmd`` (stubbed, no side effect
    beyond redirect files created inside ``cwd``). The stub writes to its own file,
    so the command's own stdout/stderr redirections cannot swallow it."""
    sink = cwd / "argv.bin"
    stubs = ('rm(){ printf "%s\\0" "$@" >"$ARGV_SINK"; }; '
             'git(){ printf "%s\\0" "$@" >"$ARGV_SINK"; }; ')
    subprocess.run(
        ["bash", "-c", stubs + cmd], cwd=str(cwd), capture_output=True,
        env={"PATH": os.environ["PATH"], "ARGV_SINK": str(sink)}, check=True,
    )
    return [a.decode() for a in sink.read_bytes().split(b"\0")[:-1]]


def _target_from_argv(argv: list[str]) -> str:
    if argv and argv[0] == "push":
        ops = [a for a in argv[1:] if not a.startswith("-")]
        return " ".join(ops) if ops else "origin"
    return " ".join(a for a in argv if not a.startswith("-"))


# Expansion-free commands: the gate's target must equal what bash executes.
# The adversarial rows QUOTE or ESCAPE a redirection character — those are
# filenames, and must stay in the target (else approving "a" would also
# authorise deleting "b").
@pytest.mark.skipif(not shutil.which("bash"), reason="bash required")
@pytest.mark.parametrize("cmd", [
    "rm a 2>/dev/null",
    "rm a 2> b",
    "rm a >b c",
    "rm a>/dev/null",
    "rm x2>/dev/null",
    "rm a &>/dev/null",
    "rm a 2>&1 >/dev/null",
    "rm a < in.txt",
    "rm -f a >>log 2>&1",
    'rm a ">" b',
    "rm a '2>/dev/null'",
    "rm 'x 2>/dev/null'",
    'rm "a>b"',
    "rm a\\>b",
    "git push origin main 2>&1",
    "git push -u origin feat/x >/dev/null 2>&1",
    'git push origin ">" evil',
])
def test_target_equals_real_shell_argv(cmd: str, tmp_path: Path) -> None:
    (tmp_path / "in.txt").write_text("", encoding="utf-8")
    res = gate.classify("Bash", {"command": cmd})
    assert res is not None
    assert res[1] == _target_from_argv(_bash_argv(cmd, tmp_path)), (cmd, res)


def test_consent_for_a_does_not_cover_a_quoted_redirect_char(bound_ws: Path) -> None:
    # Approve the redirect-carrying command's object ("a")...
    _, target = gate.classify("Bash", {"command": "rm -r a 2>/dev/null"})
    cl.append_consent(
        workspace_root=bound_ws, project_slug="demo", run_id="r", action="fs_delete",
        target=target, granted_by="operator", now_iso=_now_iso(),
        session_id=SID,
    )
    allowed = {"tool_name": "Bash", "tool_input": {"command": "rm -r a 2>/dev/null"},
               "session_id": SID}
    assert gate.evaluate(allowed)[0] == 0
    # ...but NOT a command that deletes "a", ">" and "b".
    for other in ('rm -r a ">" b', "rm -r a '2>/dev/null'", "rm -r a b 2>/dev/null"):
        payload = {"tool_name": "Bash", "tool_input": {"command": other},
                   "session_id": SID}
        assert gate.evaluate(payload)[0] == 2, other


# ---------------------------------------------------------------------------
# (3)+(1)+(6) end to end: hint -> user's chat message -> hook -> ledger -> gate ALLOWS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "git push --force origin main 2>&1",
    "rm -rf $T 2>/dev/null",
    "rm -rf ~/Library/Caches/com.example/* 2>/dev/null",
    "rm -r \"My Dir/it's\"",
    'curl -sS -X POST "$U" -H \'content-type: application/json\' -d \'{"a":1}\'',
])
def test_hint_roundtrip_through_user_message(
    cmd: str, bound_ws: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    hint = _deny_hint(cmd)
    prefix = f"/{_plugin_name()}:{_CMD_FILE.stem} "
    assert prefix in hint, hint
    message = prefix + hint.split(prefix, 1)[1]  # what the user pastes into chat

    payload = {"session_id": SID, "prompt": message, "hook_event_name": "UserPromptSubmit"}
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps(payload)))
    assert consent_from_prompt.main() == 0
    assert "[onay] kaydedildi" in capsys.readouterr().out

    code, msgs = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": SID}
    )
    assert (code, msgs) == (0, []), f"approved via hint, still blocked: {msgs}"


# ---------------------------------------------------------------------------
# (4) no session id -> refuse loudly, write nothing
# ---------------------------------------------------------------------------

def test_approve_without_session_id_refuses_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    ws = tmp_path / "ws"
    (ws / "projects" / "demo" / "_state").mkdir(parents=True)
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "demo"}), encoding="utf-8"
    )
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))

    rc = cl.main(["approve", "sess-abcdef01", "git_push", "origin main"])

    assert rc != 0
    assert "CLAUDE_CODE_SESSION_ID" in capsys.readouterr().err
    assert cl.read_entries(ws, "demo") == []
