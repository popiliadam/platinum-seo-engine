"""Smoke test for scripts/security/check_secrets.sh."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "security" / "check_secrets.sh"


def test_script_exists_and_executable() -> None:
    assert SCRIPT.exists(), f"missing: {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, "script not executable"


def test_bash_syntax_check() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_runs_clean_on_empty_dir(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GREEN" in result.stdout


def _header() -> str:
    """The leading comment block, before `set -euo pipefail`."""
    return SCRIPT.read_text(encoding="utf-8").split("set -euo pipefail", 1)[0]


def test_header_states_committed_policy_not_on_disk() -> None:
    """P2-07: the script WARNs (not fails) on a gitignored .env (see section 3:
    git check-ignore -> WARN, exit stays 0), so the policy is 'zero COMMITTED/
    tracked secrets', NOT 'zero secrets on disk'. The header must say so."""
    header = _header()
    assert "Zero-secrets-on-disk" not in header, (
        "header still claims 'Zero-secrets-on-disk' but a gitignored local .env "
        "only WARNs (exit 0) — the policy is zero COMMITTED/tracked secrets"
    )
    assert ("committed" in header.lower()) or ("tracked" in header.lower()), (
        "header must state the committed/tracked-secrets policy"
    )
    assert ("WARN" in header) and ("gitignore" in header.lower()), (
        "header must document the gitignored-.env WARN allowance so the wording "
        "and the code agree"
    )


# ---------------------------------------------------------------------------
# --scan-stdin mode (literal pending bytes) — AMO Faz-3 governance.
#   Scans the LITERAL bytes on stdin (gitignore-UNAWARE) so a secret headed for
#   a gitignored target is caught — EXCEPT a gitignored local .env, a sanctioned
#   local-secrets store, which only WARNs (exit 0), mirroring section 3.
#
# Every secret-shaped fixture below is built by RUNTIME concatenation
# ("AIza" + "B" * 35), never as a committed literal: on disk the bytes read
# `AIza"` (the quote breaks the run), so neither the CI wrapper (git grep HEAD)
# nor the full-mode scanner (filesystem grep, which does NOT exclude this test
# file) ever sees a contiguous watched token. The secret exists only in memory
# at runtime. See worker-prompt rule D.
# ---------------------------------------------------------------------------
def _run_scan_stdin(
    payload: str, pseudo_path: str | None = None, cwd: str | None = None
) -> "subprocess.CompletedProcess[str]":
    args = ["bash", str(SCRIPT), "--scan-stdin"]
    if pseudo_path is not None:
        args.append(pseudo_path)
    return subprocess.run(
        args,
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )


def _init_git_repo(path: Path, ignored: list[str]) -> None:
    subprocess.run(
        ["git", "init", "-q", str(path)],
        check=True, capture_output=True, timeout=30,
    )
    (path / ".gitignore").write_text("\n".join(ignored) + "\n", encoding="utf-8")


def test_scan_stdin_fails_on_google_key_shape_without_pseudo_path() -> None:
    """T1: a Google-API-key-shaped blob on stdin (no pseudo-path) is a FAIL,
    and the matched content is REDACTED — only the pattern label is printed."""
    gkey = "AIza" + "B" * 35  # synthetic Google-API-key shape, not a real token
    result = _run_scan_stdin(f"config:\n  api_key: {gkey}\n")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "google_api_key_AIza" in result.stdout
    assert gkey not in result.stdout, "matched secret must never be echoed"
    assert gkey not in result.stderr, "matched secret must never be echoed"


def test_scan_stdin_green_on_benign_text() -> None:
    """T2: benign bytes on stdin scan clean (exit 0, GREEN). The banner assertion
    proves the verdict came from the stdin-scan path, not a positional
    fall-through (which would also exit GREEN on a non-existent root)."""
    result = _run_scan_stdin("hello world\nno secrets here\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GREEN" in result.stdout
    assert "stdin pending bytes" in result.stdout


def test_scan_stdin_warns_on_gitignored_dotenv(tmp_path: Path) -> None:
    """T3: the carve-out — a secret headed for a GITIGNORED local .env is a
    sanctioned local-secrets store, so WARN (exit 0), never FAIL."""
    _init_git_repo(tmp_path, [".env", "notes.txt"])
    gkey = "AIza" + "C" * 35
    env_path = tmp_path / ".env"
    result = _run_scan_stdin(
        f"SECRET={gkey}\n", pseudo_path=str(env_path), cwd=str(tmp_path)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN" in result.stdout
    assert gkey not in result.stdout, "matched secret must never be echoed"
    assert gkey not in result.stderr, "matched secret must never be echoed"


def test_scan_stdin_fails_on_gitignored_non_dotenv(tmp_path: Path) -> None:
    """T4: only .env gets the carve-out. A secret headed for ANY other
    gitignored target (notes.txt) still FAILs (exit 1)."""
    _init_git_repo(tmp_path, [".env", "notes.txt"])
    gkey = "AIza" + "D" * 35
    notes_path = tmp_path / "notes.txt"
    result = _run_scan_stdin(
        f"token: {gkey}\n", pseudo_path=str(notes_path), cwd=str(tmp_path)
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "google_api_key_AIza" in result.stdout
    assert gkey not in result.stdout, "matched secret must never be echoed"


def test_scan_stdin_fails_on_openai_sk_shape() -> None:
    """T5: a second, distinct pattern (sk- shape) also fires — proves the full
    PATTERNS loop runs in the new mode, not just the first entry."""
    sk = "sk-" + "E" * 24  # synthetic OpenAI/Anthropic key shape
    result = _run_scan_stdin(f"OPENAI_KEY={sk}\n")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "openai_or_anthropic_sk_prefix" in result.stdout
    assert sk not in result.stdout, "matched secret must never be echoed"
    assert sk not in result.stderr, "matched secret must never be echoed"


# ---------------------------------------------------------------------------
# S2 (codex-C extension) — generic high-entropy base64 secret heuristic.
#   Contract: a secret-ish key (key|token|secret|password|credential) assigned a
#   QUOTED, PADDED base64 value (>=24 base64 chars ending in '=' / '==') FAILs.
#   Padding is the precision anchor — hex hashes / git SHAs / identifiers / paths
#   never carry '=', so it sidesteps the false-positive surface a bare
#   [A-Za-z0-9+/]{24,} run hits (a loose variant matched 195 benign repo paths).
#   Fixtures are built by RUNTIME split-concatenation so no contiguous match lands
#   on disk (the full-mode scanner does NOT exclude this test file).
# ---------------------------------------------------------------------------

def test_scan_stdin_fails_on_padded_base64_secret() -> None:
    """A padded base64 blob assigned to a secret-ish key is caught (exit 1),
    REDACTED, and labelled base64_high_entropy_secret_assignment."""
    padded = "QUJDREVGR0hJSktMTU5P" + "UFFSU1RVVldYWVo="  # 32 b64 chars + '=' pad
    result = _run_scan_stdin(f'api_key = "{padded}"\n')
    assert result.returncode == 1, result.stdout + result.stderr
    assert "base64_high_entropy_secret_assignment" in result.stdout
    assert padded not in result.stdout, "matched secret must never be echoed"
    assert padded not in result.stderr, "matched secret must never be echoed"


def test_scan_stdin_base64_no_fp_on_hex_hash() -> None:
    """A quoted hex hash (md5/sha shape) under a key field must NOT trip the
    heuristic — hex ⊂ base64 but has no '=' padding. The repo is built on
    hash-chained ledgers; a false-block here would be intolerable."""
    hexhash = "634c8ed5b7cf3c85" + "2d9b41e1c0e1d3b5"  # 32 hex chars, no padding
    result = _run_scan_stdin(f'baseline_key: "{hexhash}"\n')
    assert result.returncode == 0, result.stdout + result.stderr


def test_scan_stdin_base64_no_fp_on_quoted_path() -> None:
    """A quoted path under a 'key' field (the 195-match false-positive class the
    loose pattern hit) must NOT trip the heuristic — paths carry '-'/'.' and no
    '=' padding."""
    result = _run_scan_stdin('"key": "skills/discovery/content-decay/x.md"\n')
    assert result.returncode == 0, result.stdout + result.stderr


def test_scan_stdin_base64_recall_gap_unpadded_not_flagged() -> None:
    """Documented boundary (rules/secrets-management.md): an UNPADDED
    all-alphanumeric base64 value is regex-indistinguishable from an identifier/
    hash, so it is intentionally NOT flagged (flagging it reintroduces the
    hash/path false positives). A dedicated entropy scanner is the right tool."""
    unpadded = "QUJDREVGR0hJSktM" + "TU5PUFFSU1RV"  # 28 alnum b64 chars, no padding
    result = _run_scan_stdin(f'api_key = "{unpadded}"\n')
    assert result.returncode == 0, result.stdout + result.stderr


def test_base64_heuristic_registered_in_inventory() -> None:
    """The base64 label is registered in the canonical inventory so a future edit
    cannot silently drop the heuristic (the behavioural tests prove it fires)."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "base64_high_entropy_secret_assignment" in body, (
        "base64 high-entropy heuristic label missing from canonical inventory"
    )


def test_secrets_management_documents_base64_boundary() -> None:
    """S2 (implement-AND-document): the base64 heuristic's coverage AND its
    deliberate recall boundary (unpadded all-alphanumeric base64 not flagged)
    are documented in the rule file, so the limitation is explicit, not silent."""
    rule = (REPO_ROOT / "rules" / "secrets-management.md").read_text(encoding="utf-8")
    low = rule.lower()
    assert "base64" in low, "secrets-management.md must document the base64 heuristic"
    assert ("padding" in low) or ("padded" in low), (
        "must document the '=' padding precision anchor / recall boundary"
    )
