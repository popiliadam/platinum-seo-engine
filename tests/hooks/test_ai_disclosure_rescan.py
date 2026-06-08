"""tests/hooks/test_ai_disclosure_rescan.py — AMO batch 2e PostToolUse rescan.

Süleyman's hardest constraint: the phrase "written by AI" (and the other
AI-disclosure signals) must NEVER appear in the VISIBLE HTML of a generated blog
post (memory feedback_ai_disclosure_ban). The PreToolUse gate
``validate_content_write.py`` enforces this on Write/Edit — but a model can
BYPASS it by writing the HTML through Bash (a ``cat > … << 'EOF'`` heredoc,
``cp``, ``tee``, a literal path in ``python -c``), which never invokes Write/Edit
(the REAL, USED demo-furniture ``vcc-`` pattern). ``ai_disclosure_rescan`` closes that
bypass: a PostToolUse hook that, AFTER any Edit/Write/Bash, re-scans the
blog-HTML file's SURFACE and, on a RED content finding, QUARANTINE-renames it off
the live ``.html`` path (block-and-revert) and tells the model to rewrite.

Contract under test:
  1. candidate_paths — Write/Edit file_path + Bash ``.html`` tokens that EXIST and
     were modified JUST NOW (recency window); a non-blog path is ignored and a
     READ (``cat old.html``, mtime old) is NOT a candidate (no false-positive).
  2. scan_red — REUSES ``content_validator.validate_content`` (no duplicated
     disclosure detection); a disclosed file → RED ``AI-disclosure`` Finding.
  3. quarantine — ``os.replace`` to ``…/article.html.BLOCKED-ai-disclosure``
     (live ``.html`` gone, content preserved).
  4. main — a Bash-heredoc / Write of a disclosed blog HTML → STDOUT block
     decision + the file quarantined; a clean / non-blog / bogus payload → no-op;
     always exit 0 (non-blocking).
  5. wiring — added as the 3rd post-tool-use command (other two intact),
     classified RUNTIME + documented.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks.ai_disclosure_rescan import (
    block_reason,
    candidate_paths,
    quarantine,
    scan_red,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "hooks" / "ai_disclosure_rescan.py"
HOOK_PATH = REPO_ROOT / "hooks" / "post-tool-use.json"
_QSUFFIX = ".BLOCKED-ai-disclosure"

# A KNOWN AI-disclosure phrase the content_validator RED rule fires on
# (English pattern: r"written\s+by\s+(?:an?\s+)?ai\b"). Only AI-disclosure is
# tripped — no R-22/R-43/R-77/R-61 RED triggers (fragment, pse- class, no img).
_DISCLOSED_HTML = (
    '<article class="pse-post"><h1>Widget Care Guide</h1>'
    "<p>This article was written by AI to help you maintain widgets.</p></article>"
)
# Clean post: no AI phrase, no other RED triggers.
_CLEAN_HTML = (
    '<article class="pse-post"><h1>Widget Care Guide</h1>'
    "<p>Regular maintenance keeps your equipment running smoothly for years.</p>"
    "</article>"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blog_html(
    tmp_path: Path, content: str, *, slug: str = "widget-care", name: str = "article.html"
) -> Path:
    """Create ``…/outputs/blog/<slug>/<name>`` with ``content``; return its path."""
    path = tmp_path / "proj" / "outputs" / "blog" / slug / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _fresh_now(path: Path) -> float:
    """A wall-clock 'now' just after ``path``'s mtime (inside the recency window)."""
    return path.stat().st_mtime + 1.0


def _run_script(
    payload_text: str, *, home: Path, workspace: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Drive ai_disclosure_rescan.py as a real subprocess (mirrors denetci tests).

    HOME is isolated so ``_resolve_profile`` never reads the real ~/.config/pseo;
    CLAUDE_CODE_SESSION_ID is cleared so the session id comes only from stdin.
    """
    env = {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
    }
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if workspace is None:
        env.pop("PSEO_WORKSPACE_ROOT", None)
    else:
        env["PSEO_WORKSPACE_ROOT"] = str(workspace)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=payload_text,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


# ---------------------------------------------------------------------------
# 1. candidate_paths — selection + recency + scope
# ---------------------------------------------------------------------------

def test_candidate_write_blog_html_fresh(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(p)}}
    assert candidate_paths(payload, now=_fresh_now(p)) == [p]


def test_candidate_edit_blog_html_fresh(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(p)}}
    assert candidate_paths(payload, now=_fresh_now(p)) == [p]


def test_candidate_non_blog_audits_path_ignored(tmp_path):
    """An outputs/audits/*.html that EXISTS (with disclosure) is OUT of scope."""
    audit = tmp_path / "proj" / "outputs" / "audits" / "x.html"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(_DISCLOSED_HTML, encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(audit)}}
    assert candidate_paths(payload, now=_fresh_now(audit)) == []


def test_candidate_tmp_path_ignored(tmp_path):
    f = tmp_path / "x.html"
    f.write_text(_DISCLOSED_HTML, encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(f)}}
    assert candidate_paths(payload, now=_fresh_now(f)) == []


def test_candidate_template_html_ignored(tmp_path):
    p = _blog_html(tmp_path, _CLEAN_HTML, name="layout.template.html")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(p)}}
    assert candidate_paths(payload, now=_fresh_now(p)) == []


def test_candidate_non_target_tool_ignored(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(p)}}
    assert candidate_paths(payload, now=_fresh_now(p)) == []


def test_candidate_nonexistent_file_ignored(tmp_path):
    p = tmp_path / "proj" / "outputs" / "blog" / "s" / "ghost.html"  # never created
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(p)}}
    assert candidate_paths(payload, now=1.0e12) == []


def test_candidate_bash_heredoc_token_fresh(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    cmd = f"cat > {p} << 'EOF'\n{_DISCLOSED_HTML}\nEOF"
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    assert candidate_paths(payload, now=_fresh_now(p)) == [p]


def test_candidate_bash_cp_token_fresh(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    cmd = f"cp /tmp/staging.html {p}"
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    assert candidate_paths(payload, now=_fresh_now(p)) == [p]


def test_candidate_bash_tee_token_fresh(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    cmd = f"echo x | tee {p}"
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    assert candidate_paths(payload, now=_fresh_now(p)) == [p]


def test_candidate_bash_read_old_file_not_a_candidate(tmp_path):
    """A ``cat <blog.html>`` READ (mtime old → now-mtime > window) is NOT caught.

    This is the recency guard: a mere read leaves mtime unchanged/old, so it never
    triggers a quarantine — only a fresh WRITE does.
    """
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    cmd = f"cat {p}"
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    old_now = p.stat().st_mtime + 3600.0  # an hour after the file's mtime
    assert candidate_paths(payload, now=old_now) == []


def test_candidate_bash_non_blog_token_ignored(tmp_path):
    """A Bash .html token outside outputs/{blog,content}/ is ignored even if fresh."""
    audit = tmp_path / "proj" / "outputs" / "audits" / "r.html"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(_DISCLOSED_HTML, encoding="utf-8")
    payload = {"tool_name": "Bash", "tool_input": {"command": f"cp a {audit}"}}
    assert candidate_paths(payload, now=_fresh_now(audit)) == []


# ---------------------------------------------------------------------------
# 2. scan_red — REUSES content_validator (no duplicated detection)
# ---------------------------------------------------------------------------

def test_scan_red_detects_ai_disclosure(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    reds = scan_red(p, profile=None)
    assert [f.rule for f in reds] == ["AI-disclosure"]
    assert all(f.severity == "RED" for f in reds)


def test_scan_red_clean_post_empty(tmp_path):
    p = _blog_html(tmp_path, _CLEAN_HTML)
    assert scan_red(p, profile=None) == []


def test_scan_red_unreadable_file_empty(tmp_path):
    missing = tmp_path / "nope.html"
    assert scan_red(missing, profile=None) == []


# ---------------------------------------------------------------------------
# 3. quarantine — os.replace off the live surface, content preserved
# ---------------------------------------------------------------------------

def test_quarantine_renames_off_live_path(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    qpath = quarantine(p)
    assert qpath == Path(str(p) + _QSUFFIX)
    assert not p.exists()  # live .html gone
    assert qpath.exists()
    assert qpath.read_text(encoding="utf-8") == _DISCLOSED_HTML  # content preserved


def test_quarantine_overwrites_prior_quarantine(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    qpath = Path(str(p) + _QSUFFIX)
    qpath.write_text("a stale earlier quarantine", encoding="utf-8")
    assert quarantine(p) == qpath
    assert qpath.read_text(encoding="utf-8") == _DISCLOSED_HTML  # overwritten
    assert not p.exists()


# ---------------------------------------------------------------------------
# block_reason — Turkish, names file + rule + quarantine path + the fix
# ---------------------------------------------------------------------------

def test_block_reason_names_file_rule_qpath_and_fix(tmp_path):
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    reds = scan_red(p, profile=None)
    qpath = Path(str(p) + _QSUFFIX)
    reason = block_reason([(p, reds, qpath)])
    assert str(p) in reason
    assert "AI-disclosure" in reason
    assert str(qpath) in reason
    assert "BLOKLANDI" in reason  # Turkish, operator-visible
    assert "YASAK" in reason  # the fix instruction


# ---------------------------------------------------------------------------
# 4. main() — subprocess, the real enforcement path
# ---------------------------------------------------------------------------

def test_main_bash_heredoc_disclosed_quarantined_and_blocked(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    cmd = f"cat > {p} << 'EOF'\n{_DISCLOSED_HTML}\nEOF"
    payload = {"session_id": "S", "tool_name": "Bash", "tool_input": {"command": cmd}}
    proc = _run_script(json.dumps(payload), home=home)
    assert proc.returncode == 0, proc.stderr
    decision = json.loads(proc.stdout)
    assert decision["decision"] == "block"
    assert str(p) in decision["reason"]
    assert "AI-disclosure" in decision["reason"]
    assert not p.exists()  # live surface cleared
    assert Path(str(p) + _QSUFFIX).exists()  # content preserved for review


def test_main_write_disclosed_blog_also_caught(tmp_path):
    """Belt-and-suspenders: the PreToolUse gate would block this Write, but the
    PostToolUse net catches it too (defense in depth)."""
    home = tmp_path / "home"
    home.mkdir()
    p = _blog_html(tmp_path, _DISCLOSED_HTML)
    payload = {
        "session_id": "S",
        "tool_name": "Write",
        "tool_input": {"file_path": str(p), "content": _DISCLOSED_HTML},
    }
    proc = _run_script(json.dumps(payload), home=home)
    assert proc.returncode == 0, proc.stderr
    decision = json.loads(proc.stdout)
    assert decision["decision"] == "block"
    assert not p.exists()
    assert Path(str(p) + _QSUFFIX).exists()


def test_main_clean_blog_write_no_block(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    p = _blog_html(tmp_path, _CLEAN_HTML)
    payload = {
        "session_id": "S",
        "tool_name": "Write",
        "tool_input": {"file_path": str(p), "content": _CLEAN_HTML},
    }
    proc = _run_script(json.dumps(payload), home=home)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""  # no block decision
    assert p.exists()  # untouched
    assert p.read_text(encoding="utf-8") == _CLEAN_HTML
    assert not Path(str(p) + _QSUFFIX).exists()


def test_main_non_blog_write_ignored(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    audit = tmp_path / "proj" / "outputs" / "audits" / "report.html"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(_DISCLOSED_HTML, encoding="utf-8")  # disclosure, but out of scope
    payload = {
        "session_id": "S",
        "tool_name": "Write",
        "tool_input": {"file_path": str(audit), "content": _DISCLOSED_HTML},
    }
    proc = _run_script(json.dumps(payload), home=home)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""
    assert audit.exists()  # not quarantined (path out of the gate's scope)


@pytest.mark.parametrize("raw", ["", "   ", "not json {{{", "[1, 2, 3]", "null"])
def test_main_bogus_or_empty_stdin_nonblocking(tmp_path, raw):
    home = tmp_path / "home"
    home.mkdir()
    proc = _run_script(raw, home=home)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_main_internal_error_is_nonblocking(monkeypatch, capsys):
    """A rescan bug mid-processing must NOT wedge the tool chain: the outer
    fail-open ``except`` returns 0 even if an internal helper raises."""
    import io

    import scripts.hooks.ai_disclosure_rescan as mod

    def _boom(*args, **kwargs):
        raise RuntimeError("rescan exploded")

    monkeypatch.setattr(mod, "candidate_paths", _boom)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "x"}})),
    )
    assert mod.main() == 0  # fail-open: never propagates, never wedges
    assert capsys.readouterr().out.strip() == ""  # no spurious block decision


# ---------------------------------------------------------------------------
# 5. Wiring — 3rd post-tool-use command (other two intact) + registration
# ---------------------------------------------------------------------------

def test_rescan_wired_as_third_post_tool_use_command():
    spec = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    handlers = spec["hooks"]["PostToolUse"]
    assert len(handlers) == 1
    block = handlers[0]
    assert block["matcher"] == "Edit|Write|Bash"  # matcher unchanged
    cmds = [h["command"] for h in block["hooks"]]
    # the two existing commands are intact …
    assert any("audit_post_tool_use.py" in c for c in cmds)
    assert any("env_probe.py" in c for c in cmds)
    # … and ours is added, plugin-agnostic (F-16 CLAUDE_PLUGIN_ROOT discipline).
    rescan = [c for c in cmds if "ai_disclosure_rescan.py" in c]
    assert rescan, "ai_disclosure_rescan.py not wired into post-tool-use.json"
    assert "${CLAUDE_PLUGIN_ROOT}" in rescan[0]


def test_rescan_classified_runtime_and_documented():
    runtime_test = (
        REPO_ROOT / "tests" / "hooks" / "test_hook_scripts_runtime_vs_ci.py"
    ).read_text(encoding="utf-8")
    assert "ai_disclosure_rescan.py" in runtime_test  # in RUNTIME_HOOK_SCRIPTS
    readme = (REPO_ROOT / "scripts" / "hooks" / "README.md").read_text(encoding="utf-8")
    assert "ai_disclosure_rescan.py" in readme
