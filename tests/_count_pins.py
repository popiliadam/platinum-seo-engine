"""Canonical capability + invariant count pins — single source of truth.

Before this module the count literals (49 skills, 29 commands, 32 declared /
25 implemented invariants, the CRITICAL/HIGH/MEDIUM tier triplet) were copy-
pasted across three pin-site test modules (``test_count_consistency``,
``test_capability_coverage``, ``test_readme_counts_match_filesystem``). A
capability bump (a skill, command, schema, or invariant landing) meant hunting
every literal by hand. Now there is ONE place to reconcile.

The drift-guard property is PRESERVED, not replaced: each ``*_COUNT`` constant
is the canonical expected value, and the matching ``count_*`` helper re-derives
it from the live filesystem / registry. The keystone reconciliation test
(``tests/docs/test_count_consistency.py``) asserts ``constant == helper`` for
every pin — so a pin can never silently drift from reality. Add a 50th skill
on disk and ``count_skills()`` returns 50 while ``SKILL_COUNT`` is still 49 →
the reconciliation test fails until this file is bumped.

Usage::

    from tests._count_pins import SKILL_COUNT, count_skills
    assert f"{SKILL_COUNT} skills" in some_doc   # cite the pin
    assert SKILL_COUNT == count_skills()         # pin == reality (keystone)
"""
from __future__ import annotations

import json
from pathlib import Path

# tests/_count_pins.py  ->  repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Canonical FINAL values — reconcile HERE (only here) on any capability or
# invariant bump. Verified against the filesystem 2026-06-10 after the W1–W5
# gap waves (GAP-T1/T2 brought skills 45 -> 49, commands 25 -> 29).
# ---------------------------------------------------------------------------
SKILL_COUNT = 49          # skills/**/SKILL.md
COMMAND_COUNT = 29        # commands/*.md
SCHEMA_FILE_COUNT = 31    # schemas/*.schema.json
SCHEMA_JSON_COUNT = 32    # schemas/*.json (= SCHEMA_FILE_COUNT + cross-sheet-invariants.json)
CSR_DECLARED = 32         # len(cross-sheet-invariants.json["rules"])
CSR_IMPLEMENTED = 25      # len(validate_invariants._RULE_FUNCTIONS)
TIER_COUNTS = {"CRITICAL": 5, "HIGH": 14, "MEDIUM": 6}  # sum == CSR_IMPLEMENTED


# ---------------------------------------------------------------------------
# Live re-derivation (ground truth) — a pin is correct iff it equals these.
# ---------------------------------------------------------------------------
def count_skills(root: Path = _REPO_ROOT) -> int:
    return len(list((root / "skills").rglob("SKILL.md")))


def count_commands(root: Path = _REPO_ROOT) -> int:
    return len(list((root / "commands").glob("*.md")))


def count_schema_files(root: Path = _REPO_ROOT) -> int:
    return len(list((root / "schemas").glob("*.schema.json")))


def count_schema_json(root: Path = _REPO_ROOT) -> int:
    return len(list((root / "schemas").glob("*.json")))


def count_declared_invariants(root: Path = _REPO_ROOT) -> int:
    data = json.loads(
        (root / "schemas" / "cross-sheet-invariants.json").read_text(encoding="utf-8")
    )
    return len(data["rules"])


def count_implemented_invariants() -> int:
    # Lazy import: only callers (tests) have ``scripts`` on sys.path.
    from scripts.validation import validate_invariants

    return len(validate_invariants._RULE_FUNCTIONS)
