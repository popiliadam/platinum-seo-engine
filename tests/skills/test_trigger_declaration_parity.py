"""Guard: the two trigger-declaration mismatches from Codex P1-04 stay fixed.

This is a TARGETED regression guard, NOT a broad trigger-parity framework. The
2026-06-04 investigation showed `triggers.hooks` / `triggers.manual` carry
skill-specific semantics that a generic rule cannot separate without false
positives:
  * ~19 skills declare a manual "/pseo-X" trigger with NO commands/X.md (the
    slash command is conceptual / natural-language) — legitimate.
  * /pseo-driftcheck is shared by drift-check + glossary-audit + schema-validate
    (orchestrator + sub-checks) — legitimate, not a conflict.
  * drift-check declares hooks:[PostToolUse] though the PostToolUse hook never
    names it — different `hooks` semantics than whats-next's advisory routing.
So we lock exactly the two VERIFIED findings, each with its rationale.
"""
import json
import re
from pathlib import Path

import yaml  # pyyaml is already a dependency

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks"


def _triggers(skill_rel: str) -> dict:
    text = (ROOT / skill_rel).read_text(encoding="utf-8")
    fm = yaml.safe_load(re.match(r"^---\n(.*?)\n---", text, re.DOTALL).group(1))
    return fm.get("triggers", {}) or {}


def _a_hook_binds_event_and_names(event: str, needle: str) -> bool:
    """True iff some hooks/*.json binds `event` (key under top-level "hooks")
    AND that file's command text mentions `needle`."""
    for hj in HOOKS.glob("*.json"):
        raw = hj.read_text(encoding="utf-8")
        data = json.loads(raw)
        if event in (data.get("hooks", {}) or {}) and needle in raw:
            return True
    return False


def test_whats_next_hook_points_at_a_hook_that_references_it() -> None:
    """P1-04A: whats-next is an advisory router — its declared triggers.hooks
    event must be bound by a hook whose command actually NAMES whats-next, so
    the declaration is truthful. The SessionStart hook does NOT reference
    whats-next; the advisory pointer lives in the UserPromptSubmit hook."""
    hooks = _triggers("skills/meta/whats-next/SKILL.md").get("hooks", []) or []
    assert hooks, "whats-next must declare the hook event that surfaces it"
    for ev in hooks:
        assert _a_hook_binds_event_and_names(ev, "whats-next"), (
            f"whats-next declares hooks:[{ev}] but no hooks/*.json binds {ev} "
            f"AND references 'whats-next' — misleading (the real advisory "
            f"pointer is the UserPromptSubmit hook, not SessionStart)"
        )


def test_load_context_does_not_claim_pseo_active() -> None:
    """P1-04B: /pseo-active is the active-project SWITCH command (writes
    shared/active.json) — distinct from loading governance context. load-context
    must rely on its natural_language triggers, not piggyback on /pseo-active,
    which would give that one command two conflicting meanings."""
    trig = _triggers("skills/governance/load-context/SKILL.md")
    manual = trig.get("manual", []) or []
    assert "/pseo-active" not in manual, (
        "load-context must not claim /pseo-active as a manual trigger — that "
        "command switches the active project, not load governance context. Rely "
        "on load-context's natural_language triggers instead."
    )
    assert trig.get("natural_language"), (
        "load-context still needs at least one trigger surface (natural_language)"
    )
