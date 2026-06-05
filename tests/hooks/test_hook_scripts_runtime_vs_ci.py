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
    # AMO batch-0a TEMPORARY diagnostic probe — wired (as an appended command
    # entry) into all five lifecycle events. Remove when the AMO session-binding
    # mechanism is confirmed. See scripts/hooks/README.md §3.
    "env_probe.py",
}

# NOT wired into hooks/*.json — CI/pre-commit/manual guard helpers.
GUARD_HOOK_SCRIPTS = {
    "check_append_only.sh",
    "check_excel_writer.py",
    "check_naming.py",
    "validate_before_write.py",
}

# Manual diagnostic / companion tools — NOT wired into hooks/*.json and NOT a
# rules-cited enforcement guard. An operator runs them on demand. TEMPORARY
# (AMO batch 0a); remove together with the probe. See scripts/hooks/README.md §3.
DIAGNOSTIC_HOOK_SCRIPTS = {
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
