"""Guard: marketplace.json must not embed a hardcoded 'pytest NNNN passed'
count.

Codex P2-07: the description claimed 'pytest 1427 passed' while the real suite
was ~1582. tests/scripts/test_version_bump.py preserves the description body
verbatim across releases, so any embedded count is never reconciled and rots
every release. Structural counts (skills/commands/schemas) ARE test-locked by
test_count_consistency.py; the volatile pytest count should not be hardcoded.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_hardcoded_pytest_count() -> None:
    mp = (ROOT / ".claude-plugin/marketplace.json").read_text()
    assert not re.search(r"pytest\s+\d{3,}\s+passed", mp), (
        "Remove the hardcoded 'pytest NNNN passed' string from marketplace.json "
        "— version-bump preserves the body verbatim so the count rots every "
        "release. Use a count-free phrasing."
    )
