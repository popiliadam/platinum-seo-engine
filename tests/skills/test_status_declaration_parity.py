"""Guard: a skill's frontmatter ``status:`` must match any lifecycle status it
self-declares in its body (the backtick ``status: active|wip|deprecated`` form).

Source: 2026-06-04 deep audit — 8 skills carried frontmatter ``status: active``
while their body still said ``status: wip`` ("promote to active after Phase X
Wave Y acceptance gate"). The v1.3 ``82d9476`` mass wip→active promote set the
frontmatter but left the honest body lifecycle lines, so the declaration drifted.
This locks FM↔body status agreement so the contradiction can't silently return.

Scope note: a sibling guard, test_trigger_declaration_parity.py, deliberately
covers only triggers; status parity lives here as its own concern.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml  # pyyaml is already a dependency

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

# The body lifecycle self-declaration is always written backtick-wrapped, e.g.
# "This skill is `status: wip` until Phase 11..." — distinct from prose like
# "`active` bump deferred" (no "status:") or master_task "status=DONE".
_BODY_STATUS_RE = re.compile(r"`status:\s*(active|wip|deprecated)`")
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def _skill_files() -> list[Path]:
    return sorted(SKILLS.glob("**/SKILL.md"))


def test_frontmatter_status_matches_body_self_declaration() -> None:
    mismatches: list[str] = []
    for path in _skill_files():
        match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if not match:
            continue
        frontmatter = yaml.safe_load(match.group(1)) or {}
        fm_status = frontmatter.get("status")
        for declared in _BODY_STATUS_RE.findall(match.group(2)):
            if declared != fm_status:
                rel = path.relative_to(ROOT)
                mismatches.append(
                    f"{rel}: frontmatter status={fm_status!r} but body "
                    f"declares `status: {declared}`"
                )
    assert not mismatches, (
        "Skill frontmatter `status:` contradicts a body self-declaration "
        "(align them — the frontmatter is the source of truth):\n"
        + "\n".join(mismatches)
    )
