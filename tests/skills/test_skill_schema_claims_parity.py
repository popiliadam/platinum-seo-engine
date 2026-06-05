"""Guard: every skill's numeric claim about a schema-governed enum / maxItems
size must match the LIVE schema authority — so a stale count (the Theme 1 & 6
failure class from the 2026-06-04 skill-contract audit: ``active_projects 8``
when the schema says 12, ``event_type 10-value enum`` when it grew to 12) can
never silently return.

Source: the audit found skill bodies that hard-coded counts which had drifted
from their governing schema (additive enum growth, a maxItems bump). Cross-refs
like that read as authoritative but rot the moment the schema changes. This
test re-derives each authority from the schema at runtime and asserts the
documented in-body claims still agree, so a future schema bump that isn't
mirrored into the prose fails here instead of misleading an operator.

Pinned authorities (read live; a schema change updates the expected value, so
any unmirrored prose claim then fails — exactly the lock we want):

  * ``event_type`` enum size — ``schemas/events.schema.json``
    ``#/properties/event_type/enum``. Currently 12. The WORK-only **legacy
    subset** (the enum minus the two ``skill_*`` meta values) is *also*
    accepted: several skills that only emit legacy work events legitimately
    call that subset "the N-value enum". Both numbers are schema-derived
    (``full`` and ``full - len(skill_*)``), so neither is a magic constant.
  * ``active_projects.maxItems`` — ``schemas/portfolio-config.schema.json``
    ``#/properties/active_projects/maxItems``. Currently 12. Scoped to
    ``active_projects`` lines so the unrelated ``minItems=3/maxItems=3``
    const arrays (mcp_tools / fetch-mode tuples) don't false-positive.
  * ``primary_source`` enum size — ``schemas/events.schema.json``
    ``#/properties/primary_source/enum`` (mirrored as ``master_task`` col C in
    ``master-excel.schema.json``). Currently 11.

Scope note: sibling guards ``test_status_declaration_parity.py`` and
``test_trigger_declaration_parity.py`` pin their own narrow concerns the same
way (verified mappings + documented exclusions, no LLM). Rule-ID prefixes
(``F-14``, ``F-8`` …) are excluded by a lookbehind so an invariant ID whose
trailing digits abut the word ``enum`` is not misread as a size.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
SCHEMAS = ROOT / "schemas"


def _skill_files() -> list[Path]:
    return sorted(SKILLS.glob("**/SKILL.md"))


# A number claimed as an enum size: "12-value enum", "12 enum", "12-enum",
# "closed 12-value enum". The (?<![FDMR0-9]-) lookbehind rejects rule-/batch-ID
# prefixes (F-14, F-08, D-03, B6-02 …) whose digits abut "enum" but denote the
# ID, not a size (e.g. "F-14 enum" = the F-14-governed enum, no size claimed).
# Including 0-9 covers two-token IDs like "B6-02" (digit before the dash);
# space-preceded sizes ("12-value enum", "10-enum") are unaffected.
_ENUM_SIZE = re.compile(
    r"(?<![FDMR0-9]-)\b(\d{1,3})[\s-]?(?:value[\s-]?)?enum\b", re.IGNORECASE
)

# A maxItems / ceiling number asserted for active_projects, e.g.
# "maxItems = 12", "max 12", "active_projects > 12", "active_projects 12'yi".
_MAXITEMS = re.compile(
    r"(?:maxItems|max(?:imum)?|>|≤|<=|ceiling)\s*[=:]?\s*(\d{1,3})"
    r"|active_projects[\s'’]{0,4}(\d{1,3})",
    re.IGNORECASE,
)


def _event_type_enum() -> list[str]:
    ev = json.loads((SCHEMAS / "events.schema.json").read_text("utf-8"))
    return ev["properties"]["event_type"]["enum"]


def _primary_source_enum() -> list[str]:
    ev = json.loads((SCHEMAS / "events.schema.json").read_text("utf-8"))
    return ev["properties"]["primary_source"]["enum"]


def _active_projects_maxitems() -> int:
    pc = json.loads((SCHEMAS / "portfolio-config.schema.json").read_text("utf-8"))
    return pc["properties"]["active_projects"]["maxItems"]


def test_event_type_enum_size_claims_match_schema() -> None:
    enum = _event_type_enum()
    full = len(enum)  # live authority (currently 12)
    legacy = len([v for v in enum if not v.startswith("skill_")])  # WORK subset (10)
    accept = {full, legacy}

    mismatches: list[str] = []
    for path in _skill_files():
        for lineno, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if "event_type" not in line:
                continue
            for m in _ENUM_SIZE.finditer(line):
                n = int(m.group(1))
                if n not in accept:
                    mismatches.append(
                        f"{path.relative_to(ROOT)}:{lineno} claims event_type "
                        f"{n}-value enum; live authority is {full} (legacy WORK "
                        f"subset {legacy} also OK) — {line.strip()[:80]}"
                    )
    assert not mismatches, (
        "Stale event_type enum-size claim(s) — re-derive from "
        "schemas/events.schema.json#/properties/event_type/enum:\n"
        + "\n".join(mismatches)
    )


def test_active_projects_maxitems_claims_match_schema() -> None:
    expected = _active_projects_maxitems()  # live authority (currently 12)

    mismatches: list[str] = []
    for path in _skill_files():
        for lineno, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if "active_projects" not in line:
                continue  # scope: ignore unrelated maxItems=3 const arrays
            for m in _MAXITEMS.finditer(line):
                n = int(next(g for g in m.groups() if g))
                if n != expected:
                    mismatches.append(
                        f"{path.relative_to(ROOT)}:{lineno} claims "
                        f"active_projects ceiling {n}; live authority "
                        f"(portfolio-config.schema.json maxItems) is {expected} "
                        f"— {line.strip()[:80]}"
                    )
    assert not mismatches, (
        "Stale active_projects.maxItems claim(s) — re-derive from "
        "schemas/portfolio-config.schema.json:\n" + "\n".join(mismatches)
    )


def test_primary_source_enum_size_claims_match_schema() -> None:
    expected = len(_primary_source_enum())  # live authority (currently 11)

    mismatches: list[str] = []
    for path in _skill_files():
        for lineno, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if "primary_source" not in line:
                continue
            for m in _ENUM_SIZE.finditer(line):
                n = int(m.group(1))
                if n != expected:
                    mismatches.append(
                        f"{path.relative_to(ROOT)}:{lineno} claims primary_source "
                        f"{n}-value enum; live authority is {expected} — "
                        f"{line.strip()[:80]}"
                    )
    assert not mismatches, (
        "Stale primary_source enum-size claim(s) — re-derive from "
        "schemas/events.schema.json#/properties/primary_source/enum:\n"
        + "\n".join(mismatches)
    )


def test_pinned_authorities_are_what_this_guard_expects() -> None:
    """Tripwire: if the schema authorities themselves move, this names the new
    values so a maintainer updates the skill prose (and this docstring), rather
    than the size scanners silently re-baselining."""
    assert len(_event_type_enum()) == 12
    assert _active_projects_maxitems() == 12
    assert len(_primary_source_enum()) == 11
