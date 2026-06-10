"""tests/hooks/test_scan_pending_secret.py — PreToolUse pending-bytes gate (#1).

Finding #1: the PreToolUse secret hook ran only ``check_secrets.sh
--changed-since HEAD`` (post-hoc, file-list sourced from git), so a Write/Edit
payload bearing a secret was ALLOWED before the file existed — and for a
gitignored / not-yet-enumerated target, possibly never caught. The scanner had
a ``--scan-stdin`` literal-bytes mode wired nowhere.

This hook (``scripts/hooks/scan_pending_secret.py``) extracts the LITERAL
pending content of a Write/Edit/NotebookEdit (and a write-shaped Bash command)
and pipes it to the canonical scanner ``--scan-stdin <file_path>`` BEFORE the
write lands — delegating to the SAME 17-class inventory (single source of
truth), never re-implementing patterns.

Contract under test:
  * extraction — Write→content, Edit→new_string, NotebookEdit→new_source,
    write-shaped Bash→command; everything else skipped.
  * verdict — scanner FAIL (secret) → exit 2 (block); clean → exit 0.
  * carve-out — a gitignored local ``.env`` stays WARN/allow (exit 0).
  * fail-open — a malformed payload never bricks the write.

Every secret is built DYNAMICALLY so neither the CI git-grep nor the canonical
full-scan (which does NOT exclude this file) sees a contiguous token on disk.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks.scan_pending_secret import extract_pending

_REPO = Path(__file__).resolve().parents[2]
_HOOK = _REPO / "scripts" / "hooks" / "scan_pending_secret.py"
_HOOK_JSON = _REPO / "hooks" / "pre-tool-use.json"


# ---------------------------------------------------------------------------
# Pure extraction — what content/pseudo-path do we scan for each tool?
# ---------------------------------------------------------------------------

def test_extract_write_returns_content_and_path() -> None:
    out = extract_pending(
        {"tool_name": "Write", "tool_input": {"file_path": "a/b.html", "content": "x"}}
    )
    assert out == ("x", "a/b.html")


def test_extract_edit_returns_new_string() -> None:
    out = extract_pending(
        {"tool_name": "Edit", "tool_input": {"file_path": "a/b.py",
                                             "old_string": "o", "new_string": "n"}}
    )
    assert out == ("n", "a/b.py")


def test_extract_notebookedit_returns_new_source() -> None:
    out = extract_pending(
        {"tool_name": "NotebookEdit",
         "tool_input": {"notebook_path": "nb.ipynb", "new_source": "src"}}
    )
    assert out == ("src", "nb.ipynb")


@pytest.mark.parametrize("cmd", [
    "cat <<EOF > out.txt\nhi\nEOF",   # heredoc
    "echo hi > out.txt",               # redirect
    "printf x >> out.txt",             # append redirect
    "echo hi | tee out.txt",           # tee
])
def test_extract_bash_write_shaped_returns_command(cmd: str) -> None:
    out = extract_pending({"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert out == (cmd, "")


@pytest.mark.parametrize("cmd", ["cat foo.txt", "grep x f.py", "ls -la", "python3 -m pytest"])
def test_extract_bash_read_shaped_skips(cmd: str) -> None:
    assert extract_pending({"tool_name": "Bash", "tool_input": {"command": cmd}}) is None


@pytest.mark.parametrize("payload", [
    {"tool_name": "Read", "tool_input": {"file_path": "x"}},
    {"tool_name": "Glob", "tool_input": {"pattern": "*"}},
    {"tool_name": "Write", "tool_input": {}},          # no content
    {},                                                  # no tool
    "not-a-dict",
])
def test_extract_non_targeted_skips(payload) -> None:
    assert extract_pending(payload) is None


# ---------------------------------------------------------------------------
# End-to-end — run the hook as Claude Code does (JSON on stdin, exit code gate).
# ---------------------------------------------------------------------------

def _run_hook(payload: dict, *, cwd: str | None = None) -> "subprocess.CompletedProcess[str]":
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO)
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True, text=True, timeout=30, cwd=cwd, env=env,
    )


def _init_git_repo(path: Path, ignored: list[str]) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True,
                   capture_output=True, timeout=30)
    (path / ".gitignore").write_text("\n".join(ignored) + "\n", encoding="utf-8")


def test_write_with_sk_blob_blocks(tmp_path: Path) -> None:
    """A Write payload with a dynamically-built sk- blob is blocked (exit 2)."""
    sk = "sk-" + "Z" * 24
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(tmp_path / "article.html"),
                              "content": f"const key = '{sk}';"}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    assert proc.returncode == 2, f"expected BLOCK; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert sk not in proc.stdout and sk not in proc.stderr, "must never echo the secret"


def test_write_to_gitignored_non_env_blocks(tmp_path: Path) -> None:
    """A secret headed for a GITIGNORED non-.env target still blocks (exit 2) —
    the carve-out is .env only."""
    _init_git_repo(tmp_path, [".env", "notes.txt"])
    gkey = "AIza" + "B" * 35
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(tmp_path / "notes.txt"),
                              "content": f"token={gkey}"}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    assert proc.returncode == 2, f"expected BLOCK; stdout={proc.stdout!r}"


def test_write_to_gitignored_dotenv_allows(tmp_path: Path) -> None:
    """The sanctioned carve-out: a secret to a gitignored local .env is WARN/
    allow (exit 0), mirroring the scanner's documented contract."""
    _init_git_repo(tmp_path, [".env", "notes.txt"])
    sk = "sk-" + "Q" * 24
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(tmp_path / ".env"),
                              "content": f"OPENAI_KEY={sk}"}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    assert proc.returncode == 0, f"gitignored .env must be allowed; stdout={proc.stdout!r}"


def test_benign_write_allows(tmp_path: Path) -> None:
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(tmp_path / "article.html"),
                              "content": "<h1>Hello</h1>\n<p>no secrets here</p>"}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    assert proc.returncode == 0, f"benign write must pass; stdout={proc.stdout!r}"


def test_malformed_stdin_fails_open() -> None:
    """A buggy/garbage payload must NOT brick all writes (fail-open, exit 0)."""
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO)
    proc = subprocess.run(
        [sys.executable, str(_HOOK)], input="not json at all",
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert proc.returncode == 0


def test_bash_heredoc_with_secret_blocks(tmp_path: Path) -> None:
    """A Bash heredoc that writes a secret-bearing file is caught pre-write."""
    ghp = "ghp_" + "a" * 36
    cmd = f"cat > out.txt <<EOF\nGITHUB_TOKEN={ghp}\nEOF"
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    assert proc.returncode == 2, f"expected BLOCK; stdout={proc.stdout!r}"
    assert ghp not in proc.stdout and ghp not in proc.stderr


def test_bash_read_command_allows(tmp_path: Path) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "grep -r foo ."}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    assert proc.returncode == 0


# ---------------------------------------------------------------------------
# S3 (codex-F extension) — on a hit, ALSO emit a {"decision":"block",...} JSON
# line to STDOUT (consistency with ai_disclosure_rescan.py / denetci.py), while
# KEEPING the existing exit-2 + stderr-text contract and never leaking content.
# ---------------------------------------------------------------------------

def test_block_emits_decision_json_to_stdout(tmp_path: Path) -> None:
    """A secret hit emits a parseable block decision on STDOUT carrying the
    scanner's pattern LABEL (never the matched bytes), and still exits 2 with the
    BLOCKED stderr text."""
    sk = "sk-" + "Y" * 24
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(tmp_path / "x.html"),
                              "content": f"key = '{sk}'"}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    # existing contract preserved
    assert proc.returncode == 2, f"exit-code contract broken: {proc.stderr!r}"
    assert "BLOCKED" in proc.stderr, f"stderr text contract broken: {proc.stderr!r}"
    # NEW: stdout carries exactly a block-decision JSON object
    decision = json.loads(proc.stdout.strip())
    assert decision["decision"] == "block"
    # reason is derived from the scanner's REDACTED pattern label, not hardcoded
    assert "openai_or_anthropic_sk_prefix" in decision["reason"], (
        f"reason should carry the scanner pattern label: {decision!r}"
    )
    # never leak the matched secret in either stream (incl. the new JSON)
    assert sk not in proc.stdout and sk not in proc.stderr


def test_clean_write_emits_no_decision_json(tmp_path: Path) -> None:
    """A benign write stays allow (exit 0) and writes NOTHING to stdout — the
    block JSON is emitted ONLY on a definitive hit."""
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(tmp_path / "x.html"),
                              "content": "<h1>no secrets</h1>"}}
    proc = _run_hook(payload, cwd=str(tmp_path))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "", f"clean write must not emit decision JSON: {proc.stdout!r}"


def test_failopen_emits_no_decision_json() -> None:
    """A malformed payload fails open (exit 0) and emits no block JSON to stdout
    (a buggy gate must not masquerade as a deterministic block)."""
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO)
    proc = subprocess.run(
        [sys.executable, str(_HOOK)], input="not json at all",
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "", f"fail-open must not emit decision JSON: {proc.stdout!r}"


# ---------------------------------------------------------------------------
# Wiring — the hook must be registered in hooks/pre-tool-use.json and the
# matcher must cover the pending-write tools.
# ---------------------------------------------------------------------------

def _pre_tool_use() -> dict:
    return json.loads(_HOOK_JSON.read_text(encoding="utf-8"))


def test_hook_wired_into_pre_tool_use() -> None:
    spec = _pre_tool_use()
    blob = json.dumps(spec)
    assert "scan_pending_secret.py" in blob, (
        "scan_pending_secret.py not wired into hooks/pre-tool-use.json"
    )


def test_changed_since_scan_retained_as_additional() -> None:
    """#1 expected fix: keep --changed-since as an ADDITIONAL incremental scan,
    not replace it."""
    blob = json.dumps(_pre_tool_use())
    assert "--changed-since" in blob, "post-hoc --changed-since scan was dropped"


def test_matcher_covers_pending_write_tools() -> None:
    """The PreToolUse block that runs the pending scan must fire on Write, Edit,
    NotebookEdit and Bash."""
    spec = _pre_tool_use()
    matcher = None
    for block in spec["hooks"]["PreToolUse"]:
        if "scan_pending_secret.py" in json.dumps(block):
            matcher = block["matcher"]
            break
    assert matcher is not None, "no PreToolUse block runs scan_pending_secret.py"
    for tool in ("Write", "Edit", "NotebookEdit", "Bash"):
        assert tool in matcher, f"matcher {matcher!r} does not cover {tool}"
