"""tests/commands/test_driftcheck_invariant_counts.py — F11 lock (Audit #2).

``/pseo-driftcheck`` hardcoded "28 invariant rules" — stale. Ground truth (the
same source tests/docs/test_count_consistency.py pins):

  - DECLARED cross-sheet rules  = len(cross-sheet-invariants.json["rules"]) = 32
  - IMPLEMENTED invariant rules = len(validate_invariants._RULE_FUNCTIONS) = 25
    partitioned 5 CRITICAL + 14 HIGH + 6 MEDIUM.

The command meant to DETECT drift must not itself be drifted. Both counts are
DERIVED here, so when a future rule lands (declared++) or is implemented
(implemented++), the command text must track it or these tests fail.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import validate_invariants

REPO = Path(__file__).resolve().parents[2]
DRIFTCHECK = REPO / "commands" / "pseo-driftcheck.md"


def _declared() -> int:
    data = json.loads((REPO / "schemas" / "cross-sheet-invariants.json").read_text("utf-8"))
    return len(data["rules"])


def _implemented() -> int:
    return len(validate_invariants._RULE_FUNCTIONS)


def test_ground_truth_is_32_declared_25_implemented() -> None:
    """Anchor: pin the source-of-truth counters (mirror test_count_consistency)."""
    assert _declared() == 32
    assert _implemented() == 25


def test_driftcheck_cites_declared_and_implemented_counts() -> None:
    text = DRIFTCHECK.read_text(encoding="utf-8")
    assert str(_declared()) in text, (
        f"driftcheck must cite the {_declared()} declared cross-sheet rules"
    )
    assert str(_implemented()) in text, (
        f"driftcheck must cite the {_implemented()} implemented invariant rules"
    )


def test_driftcheck_has_no_stale_28() -> None:
    text = DRIFTCHECK.read_text(encoding="utf-8")
    for stale in ("28 invariant", "28 cross-sheet", "28 governance"):
        assert stale not in text, f"stale invariant-count cite remains: {stale!r}"


def test_driftcheck_tier_breakdown_sums_to_implemented() -> None:
    """The CRITICAL/HIGH/MEDIUM split must match validate_invariants (5+14+6=25)."""
    text = DRIFTCHECK.read_text(encoding="utf-8")
    assert "5 CRITICAL + 14 HIGH + 6 MEDIUM" in text, (
        "driftcheck must cite the implemented tier split (5 CRITICAL + 14 HIGH "
        "+ 6 MEDIUM), which sums to the 25 implemented rules"
    )
