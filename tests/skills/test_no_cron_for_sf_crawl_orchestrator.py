"""tests/skills/test_no_cron_for_sf_crawl_orchestrator.py

D-SF-09 verification: sf-crawl-orchestrator is operator-controlled, NOT
auto-scheduled. SF crawls take ≥1-2h and consume an unbounded volume of
SF license credits + disk; benefits from explicit human gating. A cron
schedule referencing sf-crawl-orchestrator anywhere in the engine
(skill SKILL.md frontmatter `triggers.scheduled`, hook JSON definitions
under `.claude/hooks/` or settings, OR the skills/**/SKILL.md
`triggers.scheduled` block of ANY OTHER skill referencing this skill)
violates the design contract.

This test is independent of the orchestrator's behavior — it asserts
the absence of any cron line tied to the skill name across the engine
prose surface. Phase 4 NEW test file per Manager Phase 4 Worker Prompt
task #11.

Cross-references
----------------
- v1.8 spec D-SF-09: "Orchestrator is operator-controlled (no cron),
  user-invoked via /pseo-sf-crawl <slug>"
- skills/ingestion/sf-crawl-orchestrator/SKILL.md (Phase 3)
- ADR-039 (controlled F-16 break + SF MCP HTTP transport)
"""

from __future__ import annotations

import re
import json
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SF_SKILL = REPO_ROOT / "skills" / "ingestion" / "sf-crawl-orchestrator" / "SKILL.md"


def _frontmatter_of(skill_md: Path) -> dict | None:
    if not skill_md.exists():
        return None
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None


def test_sf_crawl_orchestrator_frontmatter_has_no_cron() -> None:
    """The sf-crawl-orchestrator SKILL.md frontmatter
    `triggers.scheduled` MUST be empty (or absent) — D-SF-09 hard rule."""
    fm = _frontmatter_of(SF_SKILL)
    assert fm is not None, (
        f"sf-crawl-orchestrator SKILL.md missing or unparseable: {SF_SKILL}"
    )
    triggers = fm.get("triggers") or {}
    scheduled = triggers.get("scheduled")
    # `scheduled` may be: absent, None, empty list, OR a list — but the list
    # must be empty per D-SF-09. A non-empty list with any cron entry FAILS.
    if scheduled is None:
        return  # absent → contract satisfied
    assert isinstance(scheduled, list), (
        f"triggers.scheduled must be a list per skill-frontmatter.schema; "
        f"got {type(scheduled).__name__}"
    )
    assert len(scheduled) == 0, (
        f"D-SF-09 violation: sf-crawl-orchestrator must NOT declare a cron "
        f"schedule; got {scheduled!r}"
    )


def test_no_other_skill_schedules_sf_crawl_orchestrator() -> None:
    """No OTHER skill anywhere in `skills/**/SKILL.md` may schedule
    sf-crawl-orchestrator (e.g. via a `triggers.scheduled` block whose
    cron line references the orchestrator). The orchestrator must be
    operator-invoked only.

    Detection: parse every skill's frontmatter; if `triggers.scheduled`
    is non-empty, scan each entry's serialized form for the literal
    'sf-crawl-orchestrator'.
    """
    skills_root = REPO_ROOT / "skills"
    offenders: list[str] = []
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        if skill_md == SF_SKILL:
            # The orchestrator's own frontmatter is covered by the
            # dedicated test above.
            continue
        fm = _frontmatter_of(skill_md)
        if not fm:
            continue
        scheduled = (fm.get("triggers") or {}).get("scheduled") or []
        if not scheduled:
            continue
        serialized = json.dumps(scheduled, ensure_ascii=False).lower()
        if "sf-crawl-orchestrator" in serialized:
            offenders.append(
                f"{skill_md.relative_to(REPO_ROOT)}: scheduled references "
                f"sf-crawl-orchestrator"
            )
    assert not offenders, (
        "D-SF-09 violation in other skill(s):\n" + "\n".join(offenders)
    )


def test_no_hook_json_targets_sf_crawl_orchestrator_via_cron() -> None:
    """Hook JSON files (engine settings + .claude hooks) MUST NOT reference
    sf-crawl-orchestrator with a cron-shaped trigger.

    Searches:
      - .claude/hooks/*.json (per-user hook configs, if any)
      - settings.json / settings.local.json at repo root or .claude/
      - any *.hook.json convention file under the repo

    Detection: for each JSON file, if its serialized contents include
    BOTH the literal 'sf-crawl-orchestrator' AND a cron-shaped key
    ('cron' / 'schedule' / 'scheduled' / 'interval'), surface the
    finding.
    """
    cron_keys = re.compile(
        r'"(cron|schedule|scheduled|interval|hourly|daily|weekly|monthly)"',
        re.IGNORECASE,
    )
    candidates: list[Path] = []
    for pattern in ("*.json", "*.hook.json"):
        for p in REPO_ROOT.rglob(pattern):
            # Stay engine-only: skip node_modules / .git / .venv / templates.
            if any(part.startswith(".") and part not in {".claude"} for part in p.parts):
                continue
            if any(part in {"node_modules", ".git", ".venv", "venv"} for part in p.parts):
                continue
            if "hook" in p.name.lower() or "settings" in p.name.lower() \
                    or ".claude" in str(p):
                candidates.append(p)

    offenders: list[str] = []
    for p in candidates:
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "sf-crawl-orchestrator" not in raw:
            continue
        if not cron_keys.search(raw):
            continue
        offenders.append(
            f"{p.relative_to(REPO_ROOT)}: contains both "
            f"sf-crawl-orchestrator and a cron-shaped key"
        )
    assert not offenders, (
        "D-SF-09 violation in hook/settings JSON file(s):\n"
        + "\n".join(offenders)
    )


def test_spec_d_sf_09_documented() -> None:
    """The D-SF-09 no-cron decision must be evidenced in the orchestrator
    SKILL.md. Acceptable surfaces (any one is sufficient):
      (a) explicit 'D-SF-09' cite, OR
      (b) 'operator-controlled' / 'operator-invoked' / 'no cron' / 'no
          schedule' language anywhere in the body, OR
      (c) a `manual` trigger declaration AND `requires_approval=true`
          + `safe_auto_execute=false` autonomy config — the structural
          contract of an operator-controlled skill, even without the
          literal D-SF-09 cite.

    The fallback (c) keeps the test resilient against a Phase 4 Worker
    who must NOT touch the Phase 3 SKILL.md body — the structural
    evidence (manual trigger + non-autonomous) IS the contract.
    """
    text = SF_SKILL.read_text(encoding="utf-8")
    has_dsf09_cite = bool(re.search(r"\bD[- ]?SF[- ]?09\b", text))
    has_operator_controlled = bool(re.search(
        r"operator.controlled|operator.invoked|no\s+cron|no\s+schedule",
        text, re.IGNORECASE,
    ))
    if has_dsf09_cite or has_operator_controlled:
        return

    # Structural fallback: parse frontmatter.
    fm = _frontmatter_of(SF_SKILL)
    assert fm, "SF orchestrator frontmatter unparseable"
    triggers = fm.get("triggers") or {}
    autonomy = fm.get("autonomy") or {}
    manual_triggers = triggers.get("manual") or []
    requires_approval = bool(autonomy.get("requires_approval"))
    safe_auto = bool(autonomy.get("safe_auto_execute"))
    assert manual_triggers, (
        "sf-crawl-orchestrator must declare at least one manual trigger "
        "(D-SF-09 structural evidence): no manual trigger AND no D-SF-09 "
        "cite AND no operator-controlled language found."
    )
    assert requires_approval and not safe_auto, (
        f"sf-crawl-orchestrator autonomy block must lock the no-cron "
        f"contract (requires_approval=true, safe_auto_execute=false). "
        f"Got requires_approval={requires_approval!r}, "
        f"safe_auto_execute={safe_auto!r}."
    )
