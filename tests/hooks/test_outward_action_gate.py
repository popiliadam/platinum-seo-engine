"""tests/hooks/test_outward_action_gate.py — AMO batch 2b PreToolUse consent gate.

TDD lock for scripts/hooks/outward_action_gate.py: the READ-ONLY PreToolUse gate
that classifies an irreversible / outward action, hashes its concrete target, and
DENIES it (sys.exit 2) unless an INTACT-chain consent entry exists FOR THIS
SESSION (spec G4 + the operator-chosen per-session model). Three layers:

  * classify() — PURE (no IO): (tool_name, tool_input) -> (action, target) for a
    CLEARLY gated action, else None. CONSERVATIVE: a non-gated command is NEVER
    blocked (only a positive match can reach a deny); leading-token (rm gated,
    confirm not).
  * evaluate() — decision: gated + matching same-session consent -> allow (0);
    gated + no/other-session/tampered/unresolvable consent -> deny (2) with the
    copy-paste /pseo-approve line.
  * main() — never bricks NON-gated work; fail-CLOSED on the gated path.

Filesystem tests use tmp_path + monkeypatch HOME; the bound workspace is reached
via $PSEO_WORKSPACE_ROOT + a session marker, and consent is seeded through
consent_ledger.append_consent (so the gate and the writer hash via the SAME
consent_ledger.target_hash — writer/gate parity by construction).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks import outward_action_gate as gate
from scripts.state import consent_ledger as cl
from scripts.state import session_binding as sb

_REPO = Path(__file__).resolve().parents[2]
_GATE = _REPO / "scripts" / "hooks" / "outward_action_gate.py"

# A realistic session UUID; first-8 drives the deny message's run-label.
SID = "abcdef01-2345-6789-aaaa-bbbbbbbbbbbb"
SID8 = "abcdef01"


# ===========================================================================
# classify() matrix — PURE, no IO (the heart; fully unit-tested)
# ===========================================================================

def test_classify_mcp_submit_uses_feedpath() -> None:
    res = gate.classify(
        "mcp__gsc__submit_sitemap",
        {"feedpath": "https://x.com/sitemap.xml", "siteUrl": "https://x.com/"},
    )
    assert res == ("mcp_submit", "https://x.com/sitemap.xml")


def test_classify_rm_is_fs_delete() -> None:
    res = gate.classify("Bash", {"command": "rm -rf foo/bar"})
    assert res is not None
    assert res[0] == "fs_delete"
    assert "foo/bar" in res[1]


def test_classify_shred_unlink_rmdir_are_fs_delete() -> None:
    for tok in ("shred", "unlink", "rmdir"):
        res = gate.classify("Bash", {"command": f"{tok} target.txt"})
        assert res is not None and res[0] == "fs_delete", tok


def test_classify_leading_token_guard_confirm_and_performance() -> None:
    # leading-token, NOT substring: 'confirm'/'performance' merely START with the
    # letters of a delete token but are not gated.
    assert gate.classify("Bash", {"command": "confirm the-plan"}) is None
    assert gate.classify("Bash", {"command": "performance --report"}) is None


def test_classify_git_push_is_git_push() -> None:
    res = gate.classify("Bash", {"command": "git push origin main"})
    assert res is not None and res[0] == "git_push"
    assert "origin" in res[1]


def test_classify_git_push_bare_defaults_to_origin() -> None:
    assert gate.classify("Bash", {"command": "git push"}) == ("git_push", "origin")


def test_classify_git_push_dry_run_still_gated() -> None:
    # Conservative/fail-closed: a push invocation is gated regardless of --dry-run;
    # the flag is ignored for target derivation (it is a flag, not an exemption).
    assert gate.classify(
        "Bash", {"command": "git push --dry-run origin main"}
    ) == ("git_push", "origin main")


def test_classify_git_status_not_gated() -> None:
    assert gate.classify("Bash", {"command": "git status"}) is None
    assert gate.classify("Bash", {"command": "git log --oneline"}) is None


def test_classify_curl_post_indexnow_is_net_post() -> None:
    res = gate.classify(
        "Bash", {"command": "curl -X POST https://api.indexnow.org/IndexNow -d @body"}
    )
    assert res is not None and res[0] == "net_post"
    assert "indexnow.org" in res[1]


def test_classify_wget_post_data_is_net_post() -> None:
    res = gate.classify(
        "Bash", {"command": "wget --post-data=ping https://example.com/notify"}
    )
    assert res is not None and res[0] == "net_post"


def test_classify_curl_indexing_api_is_index_update() -> None:
    res = gate.classify(
        "Bash",
        {"command": "curl -X POST https://indexing.googleapis.com/v3/urlNotifications:publish -d @b"},
    )
    assert res is not None and res[0] == "index_update"
    assert "indexing.googleapis.com" in res[1]


def test_classify_curl_get_not_gated() -> None:
    # Only an outbound POST (or an indexing/indexnow endpoint) is gated; a plain
    # GET curl is NOT.
    assert gate.classify("Bash", {"command": "curl https://example.com"}) is None


def test_classify_benign_bash_always_none() -> None:
    for cmd in ("ls -la", "git log", "echo hi", "cat x", "grep foo bar.txt"):
        assert gate.classify("Bash", {"command": cmd}) is None, cmd


def test_classify_empty_or_missing_command_none() -> None:
    assert gate.classify("Bash", {"command": ""}) is None
    assert gate.classify("Bash", {"command": "   "}) is None
    assert gate.classify("Bash", {}) is None


def test_classify_other_tools_none() -> None:
    assert gate.classify("Read", {"file_path": "x"}) is None
    assert gate.classify("Write", {"file_path": "x", "content": "y"}) is None
    assert gate.classify("mcp__gsc__search_analytics", {"siteUrl": "x"}) is None


# ===========================================================================
# evaluate() — per-session consent decision (real resolvers via env + marker)
# ===========================================================================

@pytest.fixture
def bound_ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp workspace bound to SID -> 'demo', reachable via env + a session marker."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = tmp_path / "ws"
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    (ws / "projects" / "demo" / "_state").mkdir(parents=True)
    sb.write_session_binding(SID, "demo", ws, "2026-06-06T00:00:00")
    return ws


def _seed(ws: Path, *, action: str, target: str, session_id: str) -> None:
    cl.append_consent(
        workspace_root=ws, project_slug="demo", run_id="r-prov",
        action=action, target=target, granted_by="operator",
        now_iso="2026-06-06T10:00:00", session_id=session_id,
    )


def test_evaluate_allows_with_matching_session_consent(bound_ws: Path) -> None:
    cmd = "git push origin main"
    action, target = gate.classify("Bash", {"command": cmd})  # parity by construction
    _seed(bound_ws, action=action, target=target, session_id=SID)
    code, msgs = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": SID}
    )
    assert (code, msgs) == (0, [])


def test_evaluate_consent_from_other_session_is_denied(bound_ws: Path) -> None:
    # PER-SESSION: same action+target, but consent granted under a DIFFERENT
    # session_id, must NOT authorize THIS session.
    cmd = "git push origin main"
    action, target = gate.classify("Bash", {"command": cmd})
    _seed(bound_ws, action=action, target=target, session_id="some-other-session")
    code, _ = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": SID}
    )
    assert code == 2


def test_evaluate_no_consent_emits_copy_paste_approve_line(bound_ws: Path) -> None:
    cmd = "git push origin main"
    code, msgs = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": SID}
    )
    assert code == 2
    assert len(msgs) == 2
    assert msgs[0].startswith("BLOCKED: git_push → origin main")
    assert "(bu oturumda onay yok)" in msgs[0]
    # the operator copies THIS exact line — same action + target the gate hashed.
    assert f'/pseo-approve sess-{SID8} git_push "origin main"' in msgs[1]


def test_evaluate_tampered_chain_is_denied(bound_ws: Path) -> None:
    cmd = "git push origin main"
    action, target = gate.classify("Bash", {"command": cmd})
    _seed(bound_ws, action=action, target=target, session_id=SID)
    # tamper the genuine entry (mutate 'target' without recomputing entry_hash):
    path = cl.consent_path(bound_ws, "demo")
    lines = path.read_text(encoding="utf-8").splitlines()
    forged = json.loads(lines[0])
    forged["target"] = "hacked"
    lines[0] = cl.canonical_json(forged)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, _ = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": SID}
    )
    assert code == 2  # broken chain -> has_session_consent fail-closed


def test_evaluate_unbound_session_is_denied(bound_ws: Path) -> None:
    # a session with no marker and no shared/active.json fallback -> slug None ->
    # cannot verify -> fail-closed deny.
    code, _ = gate.evaluate(
        {"tool_name": "Bash", "tool_input": {"command": "git push origin main"},
         "session_id": "ghost-session-no-marker"}
    )
    assert code == 2


def test_evaluate_non_gated_allows_without_any_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # classify() None short-circuits BEFORE any session/workspace resolution, so a
    # plain Bash command is never bricked even with no binding at all.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("PSEO_WORKSPACE_ROOT", raising=False)
    code, msgs = gate.evaluate({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert (code, msgs) == (0, [])


# ===========================================================================
# main() — subprocess smoke (mirrors test_denetci / test_env_probe)
# ===========================================================================

def _run_gate(stdin: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ}
    env.pop("PSEO_WORKSPACE_ROOT", None)
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO)  # resolve scripts.* against THIS repo
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(_GATE)], input=stdin, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )


def test_main_gated_no_consent_exits_2_with_fix(tmp_path: Path) -> None:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"},
        "session_id": "abcdef01-deny",
    })
    proc = _run_gate(payload, {"HOME": str(tmp_path / "home")})
    assert proc.returncode == 2, proc.stderr
    assert "/pseo-approve" in proc.stderr
    assert "git_push" in proc.stderr


def test_main_non_gated_exits_0_quiet(tmp_path: Path) -> None:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    proc = _run_gate(payload, {"HOME": str(tmp_path / "home")})
    assert proc.returncode == 0
    assert proc.stderr.strip() == ""


def test_main_bogus_stdin_exits_0_no_brick(tmp_path: Path) -> None:
    proc = _run_gate("{not valid json", {"HOME": str(tmp_path / "home")})
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr
