"""Contract lock — reference-workflow skills commit snapshots via the committer.

WHY: ``gsc_performance`` / ``quick_wins`` / ``opportunity`` / ``content_decay``
are all SNAPSHOT sheets — a recent-vs-previous window delta or a current-window
quick-win list. NONE carries a date/run/timestamp column to disambiguate runs
(see schemas/master-excel.schema.json). So ``transaction.append`` silently
DUPLICATES every row on each re-run. ``committer.commit`` wraps
``transaction.replace`` (clear the sheet's data block, then write), so re-running
a step REFRESHES the snapshot instead of duplicating it — and it routes the
standalone skill path through the same idempotent, orchestrator-owned committer
built in AMO batch 1b. This test pins that wiring so the duplicate bug cannot
regress and the two write paths cannot diverge.

Robust by design: it greps the rendered SKILL.md body for the call-site token
``committer.commit(`` and the ABSENCE of ``transaction.append(``. The paren form
is deliberate — the DURUR / failure-mode prose mentions ``transaction.append``
WITHOUT a trailing paren, so it must not false-trip. This mirrors the same idiom
already used by tests/skills/governance/test_schema_validate.py and
tests/skills/test_monitoring_weekly.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"


# (SKILL.md path, sheet name(s) whose write must survive the relocation)
REFERENCE_SKILLS = [
    pytest.param(
        SKILLS / "ingestion" / "gsc-pull" / "SKILL.md",
        ("gsc_performance",),
        id="gsc-pull",
    ),
    pytest.param(
        SKILLS / "discovery" / "quick-wins" / "SKILL.md",
        ("quick_wins", "opportunity"),
        id="quick-wins",
    ),
    pytest.param(
        SKILLS / "discovery" / "content-decay" / "SKILL.md",
        ("content_decay",),
        id="content-decay",
    ),
]


@pytest.mark.parametrize("skill_path, sheets", REFERENCE_SKILLS)
def test_reference_skill_commits_via_committer(
    skill_path: Path, sheets: tuple[str, ...]
) -> None:
    """Each reference skill's master.xlsx write routes through committer.commit
    (replace, idempotent), never transaction.append (which dup'd the snapshot)."""
    body = skill_path.read_text(encoding="utf-8")

    # 1. The write now goes through the orchestrator-owned committer.
    assert "committer.commit(" in body, (
        f"{skill_path.name}: master.xlsx write must route through "
        "committer.commit( (orchestrator-owned idempotent replace)"
    )

    # 2. No transaction.append( call-site survives -> the snapshot dup bug
    #    cannot regress. Paren-form only: the DURUR failure-mode prose names
    #    `transaction.append` WITHOUT a paren and must not false-trip.
    assert "transaction.append(" not in body, (
        f"{skill_path.name}: a transaction.append( call-site remains — snapshot "
        "sheets must commit via committer.commit (replace), never append"
    )

    # 3. The relocation did not silently drop a write: each target snapshot
    #    sheet is still named in the body.
    for sheet in sheets:
        assert sheet in body, (
            f"{skill_path.name}: expected sheet {sheet!r} missing — a write may "
            "have been dropped during the committer migration"
        )
