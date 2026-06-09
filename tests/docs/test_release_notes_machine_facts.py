"""Audit#2 Finding 12 + cross-cutting gap #6 (`test_release_notes_machine_facts`).

`docs/RELEASE_NOTES_v2.0.0.md` shipped with machine-checkable facts that were
wrong on the day they were written:

  * "Slash-command count -> 24"  while the filesystem has 25 commands.
  * "2312 PASS / 7 SKIP"         a pytest total that was never accurate (the
                                 audit observed 2481, the suite has since grown)
                                 and rots every release.

This test pins the ONE machine-checkable fact a release note can own forever —
the command count, derived from `commands/*.md` — and forbids the stale literals
so a future version bump cannot silently re-freeze them. The pytest total is
deliberately NOT re-pinned to a new number (it would rot again — same rationale
as `test_marketplace_no_hardcoded_pytest_count.py` and the README's count-free
suite phrasing); the release note must phrase the suite result count-free
instead of substituting another doomed number.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_RELEASE_NOTES = _ROOT / "docs" / "RELEASE_NOTES_v2.0.0.md"


def _n_commands() -> int:
    return len(list((_ROOT / "commands").glob("*.md")))


def _text() -> str:
    return _RELEASE_NOTES.read_text(encoding="utf-8")


def test_release_notes_command_count_matches_filesystem() -> None:
    text = _text()
    assert f"Slash-command count **→ {_n_commands()}**" in text, (
        "RELEASE_NOTES_v2.0.0 must cite the live command count from commands/*.md"
    )


def test_release_notes_has_no_stale_command_count() -> None:
    assert "count **→ 24**" not in _text(), "stale 'Slash-command count -> 24' must be gone"


def test_release_notes_has_no_stale_pytest_total() -> None:
    # The 2312 total was never accurate and rots every release; phrase the suite
    # result count-free (GREEN / 0 fail / see CI) instead of re-pinning a number.
    assert "2312" not in _text(), (
        "Remove the stale hardcoded '2312' pytest total — phrase the suite "
        "result count-free so it does not rot every release."
    )
