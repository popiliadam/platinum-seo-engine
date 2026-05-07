"""Regression: every scripts/hooks/* path cited in rules/*.md MUST exist
OR be tracked under EXPECTED_DEFERRED set with Q-XXX reference.

Locks Q-V1.4-AUDIT-GOVERNANCE-01 hook script existence gap (brief T4
Step 3; previously deferred per audit "Doğrulanmadı" list).

History:
- Audit (2026-05-07) found 4 cited hook scripts not authored. All 4 routed
  to Q-V1.5-HOOK-SCRIPTS-MISSING-01.
- Cleanup batch (2026-05-07, post-v1.4-deep-audit-fix) applied option (b):
  authored 2 unqualified-gap hooks (check_append_only.sh +
  check_excel_writer.py). EXPECTED_DEFERRED reduced 4 → 2.
- Remaining 2 ("Phase 13'te otomatize" qualifier in rule body — deferred
  by-design): check_naming.py + validate_before_write.py. v1.5+ session
  to author when the rule's stated Phase 13 timeline finalizes.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
RULES_DIR = ROOT / "rules"
HOOKS_DIR = ROOT / "scripts" / "hooks"

HOOK_PATH_RE = re.compile(r"`scripts/hooks/([a-zA-Z0-9_]+\.(?:sh|py))`")

# Per Q-V1.5-HOOK-SCRIPTS-MISSING-01 + cleanup batch closure (option b):
# 2 hook scripts remain deferred — both carry "Phase 13'te otomatize"
# qualifier in rule body, so the rule itself documents the gap as
# by-design. Authoring waits on Phase 13 timeline finalization.
EXPECTED_DEFERRED = {
    "check_naming.py",          # rules/naming.md:43 "Phase 13'te otomatize"
    "validate_before_write.py", # rules/schema-first.md:36 "Phase 13'te otomatize"
}


def _all_cited_hook_scripts():
    """Enumerate scripts/hooks/<file> paths cited in rules/*.md."""
    cited = set()
    for f in sorted(RULES_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        for m in HOOK_PATH_RE.finditer(text):
            cited.add(m.group(1))
    return cited


def test_no_unexpected_missing_hook_scripts():
    """Cited hook scripts MUST exist OR be in EXPECTED_DEFERRED set.

    If a NEW citation appears in rules/ without the corresponding script in
    scripts/hooks/ AND not in EXPECTED_DEFERRED, this test fails — forcing
    either authoring of the script or explicit deferred tracking.
    """
    cited = _all_cited_hook_scripts()
    missing = {name for name in cited if not (HOOKS_DIR / name).exists()}
    unexpected_missing = missing - EXPECTED_DEFERRED
    assert not unexpected_missing, (
        f"Hook scripts cited in rules/ but not authored AND not in "
        f"EXPECTED_DEFERRED (Q-V1.5-HOOK-SCRIPTS-MISSING-01): "
        f"{sorted(unexpected_missing)}. Either author the script or add to "
        f"EXPECTED_DEFERRED with deferred Q-XXX reference."
    )


def test_expected_deferred_set_complete():
    """EXPECTED_DEFERRED set MUST cover all currently-missing cited scripts.

    If a deferred script is later authored, this test fails — prompting the
    EXPECTED_DEFERRED entry to be removed.
    """
    cited = _all_cited_hook_scripts()
    missing = {name for name in cited if not (HOOKS_DIR / name).exists()}
    stale_deferred = EXPECTED_DEFERRED - missing
    assert not stale_deferred, (
        f"Scripts in EXPECTED_DEFERRED that NOW EXIST in scripts/hooks/: "
        f"{sorted(stale_deferred)}. Remove from EXPECTED_DEFERRED — they are "
        f"no longer deferred."
    )
