"""tests/hooks/test_hook_scripts_runtime_vs_ci.py — P2-06 wiring classification.

scripts/hooks/ holds two classes of helper that the audit found undocumented:

  * RUNTIME session hooks — referenced by a hooks/*.json event handler, so
    Claude Code runs them automatically in the tool lifecycle.
  * GUARD helpers (CI / pre-commit / manual) — NOT wired into any hooks/*.json.
    They are cited by rules/*.md as the enforcement mechanism for a discipline
    and validated by their own pytest unit tests; they do NOT auto-run in a
    live session.

scripts/hooks/README.md documents the split; these tests lock it so a helper
cannot silently change class (a guard wired into a live hook, or a runtime hook
dropped from its json) without the docs + tests flagging it.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_HOOKS_JSON_DIR = _REPO / "hooks"
_HOOK_SCRIPTS_DIR = _REPO / "scripts" / "hooks"
_RULES_DIR = _REPO / "rules"

# Wired into a hooks/*.json — run automatically by Claude Code.
RUNTIME_HOOK_SCRIPTS = {
    "stop_validation.py",
    "subagent_output_validate.py",
    "validate_content_write.py",
    # codex-hostile-audit #1 PreToolUse pending-bytes secret gate — wired into
    # hooks/pre-tool-use.json (matcher "Edit|Write|NotebookEdit|Bash") as the
    # command right AFTER the post-hoc check_secrets.sh --changed-since scan
    # (which it keeps as an ADDITIONAL incremental backstop). It extracts a
    # Write/Edit/NotebookEdit payload's literal pending content (and a
    # write-shaped Bash command) and pipes it to check_secrets.sh --scan-stdin
    # <file_path>, blocking (exit 2) BEFORE a secret-bearing write lands on disk.
    # Re-implements NO pattern — delegates to the canonical 16-class inventory
    # (single source of truth). See scripts/hooks/README.md §1.
    "scan_pending_secret.py",
    # AMO batch-0d session-aware audit emitter — wired into hooks/post-tool-use.json
    # (replaces the legacy inline `python3 -c` audit command). Attributes each
    # Edit/Write/Bash audit event to THIS session's bound project (session marker
    # → shared/active.json fallback). See scripts/hooks/README.md §1.
    "audit_post_tool_use.py",
    # AMO batch-1c intent router — wired into hooks/user-prompt-submit.json
    # (replaces the legacy inline static-bash advisory command, so there is ONE
    # voice per prompt). Classifies the prompt: a Tier-1 canonical match injects a
    # one-line `/pseo-run <workflow> <slug>` instruction + writes the
    # intent_declared marker; Tier-2 falls back to the whats-next advisory and
    # supersedes any stale intent. Re-emits the `PSEO context:` line.
    # See scripts/hooks/README.md §1.
    "intent_router.py",
    # AMO batch-2c Stop denetçi — wired into hooks/stop.json as the 2nd Stop
    # command (stop_validation.py stays FIRST). At turn end it READS the intent
    # marker (1c) + the freshest coverage record (1a) and, if a declared workflow
    # did not run/pass, BLOCKS the turn end with a Turkish `/pseo-run … --resume`
    # fix (paused/external → allow + flag). READ-ONLY, non-blocking-on-error.
    # See scripts/hooks/README.md §1.
    "denetci.py",
    # AMO batch-2b PreToolUse outward-action consent gate — wired into
    # hooks/pre-tool-use.json as a SECOND PreToolUse block (matcher
    # "Bash|mcp__gsc__submit_sitemap"); the existing block is untouched. Before a
    # gated action (git_push / fs_delete / net_post / mcp_submit / index_update)
    # runs, it classifies + hashes the concrete target and BLOCKS (exit 2) unless
    # THIS session's bound project consented (consent_ledger.has_session_consent).
    # READ-ONLY; fail-closed on the gated path, fail-open on the non-gated path.
    # See scripts/hooks/README.md §1.
    "outward_action_gate.py",
    # AMO batch-2e PostToolUse AI-disclosure surface rescan — wired into
    # hooks/post-tool-use.json as the 2nd command (after audit_post_tool_use.py;
    # matcher "Edit|Write|Bash"). AFTER any Edit/Write/Bash
    # it re-scans a just-written blog-HTML file's surface via content_validator and,
    # on a RED AI-disclosure finding, QUARANTINE-renames it off the live .html path
    # (os.replace → .BLOCKED-ai-disclosure) and emits a {"decision":"block"} stdout
    # JSON — closing the Bash/heredoc bypass of the PreToolUse Write-gate. REUSES
    # content_validator + validate_content_write.is_content_html_path (no duplicated
    # detection); recency-guarded (a read never triggers); non-blocking-on-error.
    # See scripts/hooks/README.md §1.
    "ai_disclosure_rescan.py",
}

# NOT wired into hooks/*.json — CI/pre-commit/manual guard helpers.
GUARD_HOOK_SCRIPTS = {
    "check_append_only.sh",
    "check_excel_writer.py",
    "check_naming.py",
    "validate_before_write.py",
}

# Orphaned / companion tools — NOT wired into hooks/*.json and NOT a rules-cited
# enforcement guard. TEMPORARY (AMO batch 0a): env_probe was UNWIRED from all five
# lifecycle events (codex-hostile-audit #17) once the session-binding question it
# answered was settled, so env_probe.py is now an ORPHAN on disk (no longer
# runtime); env_probe_report.py was always operator-run. Both remain on disk
# pending the manager's consent-gated deletion at integration (a bare `rm` trips
# the engine's own fs_delete consent gate). See scripts/hooks/README.md §3.
DIAGNOSTIC_HOOK_SCRIPTS = {
    "env_probe.py",
    "env_probe_report.py",
}


def _hooks_json_blob() -> str:
    return "".join(
        p.read_text(encoding="utf-8")
        for p in sorted(_HOOKS_JSON_DIR.glob("*.json"))
    )


def _rules_blob() -> str:
    return "".join(
        p.read_text(encoding="utf-8") for p in sorted(_RULES_DIR.glob("*.md"))
    )


def test_runtime_hook_scripts_exist_and_are_wired() -> None:
    """Each runtime hook exists AND is referenced by a hooks/*.json."""
    blob = _hooks_json_blob()
    for name in sorted(RUNTIME_HOOK_SCRIPTS):
        assert (_HOOK_SCRIPTS_DIR / name).is_file(), f"runtime hook missing: {name}"
        assert name in blob, (
            f"runtime hook {name} not referenced by any hooks/*.json — wire it "
            f"or reclassify as a guard helper"
        )


def test_guard_hook_scripts_exist_unwired_and_rules_cited() -> None:
    """Each guard helper exists, is NOT wired into any hooks/*.json (it runs in
    CI/pre-commit/manual, not the live session), and is cited by a rules/*.md
    as its enforcement home."""
    hooks_blob = _hooks_json_blob()
    rules_blob = _rules_blob()
    for name in sorted(GUARD_HOOK_SCRIPTS):
        assert (_HOOK_SCRIPTS_DIR / name).is_file(), f"guard helper missing: {name}"
        assert name not in hooks_blob, (
            f"guard helper {name} IS referenced by a hooks/*.json — it was meant "
            f"to be CI/pre-commit-only; unwire it or reclassify as runtime"
        )
        assert name in rules_blob, (
            f"guard helper {name} not cited by any rules/*.md — a non-runtime "
            f"helper must declare its enforcement home"
        )


def test_diagnostic_hook_scripts_exist_and_are_unwired() -> None:
    """Each diagnostic/companion tool exists and is NOT wired into a hooks/*.json
    (it is run manually by an operator, not by the tool lifecycle)."""
    hooks_blob = _hooks_json_blob()
    for name in sorted(DIAGNOSTIC_HOOK_SCRIPTS):
        assert (_HOOK_SCRIPTS_DIR / name).is_file(), f"diagnostic tool missing: {name}"
        assert name not in hooks_blob, (
            f"diagnostic tool {name} IS referenced by a hooks/*.json — it is meant "
            f"to be manual-only; unwire it or reclassify"
        )


def test_every_hook_script_is_classified() -> None:
    """Every .py/.sh under scripts/hooks/ belongs to exactly one class, so no
    unclassified helper can hide (the P2-06 root cause)."""
    on_disk = {
        p.name for p in _HOOK_SCRIPTS_DIR.iterdir()
        if p.suffix in {".py", ".sh"}
    }
    unclassified = on_disk - (
        RUNTIME_HOOK_SCRIPTS | GUARD_HOOK_SCRIPTS | DIAGNOSTIC_HOOK_SCRIPTS
    )
    assert not unclassified, (
        f"scripts/hooks/ helpers not classified runtime/guard/diagnostic: "
        f"{sorted(unclassified)} — add to the right set + scripts/hooks/README.md"
    )


def test_readme_documents_both_classes() -> None:
    """scripts/hooks/README.md must exist and name every helper in all
    classes — runtime, guard, AND diagnostic (P2-06 documentation requirement)."""
    readme = _HOOK_SCRIPTS_DIR / "README.md"
    assert readme.is_file(), "scripts/hooks/README.md (P2-06 wiring doc) is missing"
    text = readme.read_text(encoding="utf-8")
    for name in sorted(
        RUNTIME_HOOK_SCRIPTS | GUARD_HOOK_SCRIPTS | DIAGNOSTIC_HOOK_SCRIPTS
    ):
        assert name in text, f"{name} not documented in scripts/hooks/README.md"


def test_no_hook_references_a_temporary_diagnostic_probe() -> None:
    """codex-hostile-audit #17 guard — a TEMPORARY diagnostic probe must never be
    wired into a live hook again.

    The AMO batch-0a env_probe shipped wired into all five lifecycle events with
    the statusMessage 'AMO batch-0a env probe (temporary diagnostic)…'; it has
    been UNWIRED. Assert no hooks/*.json references a 'temporary diagnostic' probe
    or env_probe.py, so a re-introduction — or any NEW temporary-diagnostic hook —
    trips CI rather than silently shipping diagnostic instrumentation into the
    live tool lifecycle."""
    blob = _hooks_json_blob().lower()
    assert "temporary diagnostic" not in blob, (
        "a hooks/*.json wires a 'temporary diagnostic' probe — temporary "
        "diagnostic instrumentation must not ship in a live hook (audit #17)"
    )
    assert "env_probe" not in blob, (
        "env_probe.py is wired into a hooks/*.json again — it is an orphaned "
        "AMO batch-0a probe pending consent-gated deletion; do not re-wire it"
    )
