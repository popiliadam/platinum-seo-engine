"""codex-audit finding 7: the PreToolUse secret scan runs in --changed-since
incremental mode, which built its file list from `git diff --name-only HEAD`.
That command lists tracked changes only — a brand-new UNTRACKED file (the exact
shape of a freshly-created service-account.json or a file with an AKIA/AIza
token) is invisible to it, so a secret could pass the gate until committed.
The fix unions in `git ls-files --others --exclude-standard` (still honors
.gitignore, so a gitignored local .env stays on its WARN-only path).
"""
import subprocess
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2]
SCRIPT = ENGINE / "scripts" / "security" / "check_secrets.sh"

# Split so this source file never contains a contiguous AKIA[0-9A-Z]{16} literal
# (else check_secrets.sh would flag its own test). The temp file written at
# runtime still receives the full, well-known AWS example key.
_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def test_incremental_scan_detects_untracked_secret(tmp_path):
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "t@t"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)
    (tmp_path / "ok.txt").write_text("hello\n")
    _git(["add", "ok.txt"], tmp_path)
    _git(["commit", "-qm", "init"], tmp_path)
    # brand-new UNTRACKED file carrying an AWS access-key id (matches AKIA pattern)
    (tmp_path / "leak.txt").write_text(_SECRET + "\n")

    res = subprocess.run(
        ["bash", str(SCRIPT), "--changed-since", "HEAD", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert res.returncode != 0, (
        "untracked secret slipped through the incremental gate:\n"
        f"{res.stdout}\n{res.stderr}"
    )


def test_incremental_scan_ignores_gitignored_env(tmp_path):
    """A gitignored local .env must NOT trip the incremental gate (it can never
    be committed) — --exclude-standard keeps the WARN-only policy intact."""
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "t@t"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)
    (tmp_path / ".gitignore").write_text(".env\n")
    _git(["add", ".gitignore"], tmp_path)
    _git(["commit", "-qm", "init"], tmp_path)
    (tmp_path / ".env").write_text(_SECRET + "\n")  # gitignored

    res = subprocess.run(
        ["bash", str(SCRIPT), "--changed-since", "HEAD", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert res.returncode == 0, (
        "gitignored .env should not fail the incremental gate:\n"
        f"{res.stdout}\n{res.stderr}"
    )
