"""FIX-RESIDUAL R1 — the corrected R-09 FAQ contract must propagate everywhere.

R-09 (``rules/content-seo-discipline.md``) was rewritten by FIX-H / FIX-H-tail
from a fixed "10 standart / 3000+ word -> 15 hard cap" mandate to a
**demand-driven 3-6 FAQ where evidence (PAA / real user questions) exists, hard
cap 10**. FIX-H aligned ``content-quality.md:14`` and the faq-optimization skill,
but several non-test-pinned files outside those scopes kept restating the retired
fixed cap — a real rule<->rule / rule<->skill contradiction.

This pins the propagation so the stale fixed-cap contract cannot silently
reappear in any file that restates the FAQ count.

Re-derived 2026-06-10 (FIX-RESIDUAL worker). Canonical source of truth:
``rules/content-seo-discipline.md`` R-09.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Every file that restates the FAQ-count contract (FIX-RESIDUAL R1 scope).
FAQ_CONTRACT_FILES = [
    "rules/content-quality.md",
    "skills/production/new-blog/SKILL.md",
    "templates/content/new-blog.template.md",
    "templates/content/new-blog.template.html",
    "templates/content/faq-block.template.html",
]

# Fixed-count fragments retired by the demand-driven R-09 rewrite. Verified to
# have NO legitimate non-FAQ use in the listed files: "3000" is FAQ-only
# (word-count ranges use 1500/4000), and "1500" never contains "15 cap" etc.
STALE_FAQ_FRAGMENTS = [
    "10 sabit",
    "10 standart",
    "10 standard",
    "10 FAQ",
    "FAQ 10",
    "15 cap",
    "15 hard cap",
    "up to 15",
    "3000",
]


@pytest.mark.parametrize("rel", FAQ_CONTRACT_FILES)
def test_no_stale_fixed_faq_cap(rel: str) -> None:
    """No file restating the FAQ contract may carry the retired fixed cap."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    found = [frag for frag in STALE_FAQ_FRAGMENTS if frag in text]
    assert not found, (
        f"{rel} still carries retired fixed-FAQ-cap language {found}; R-09 is "
        f"demand-driven 3-6 with a hard cap of 10 "
        f"(rules/content-seo-discipline.md)."
    )


@pytest.mark.parametrize("rel", FAQ_CONTRACT_FILES)
def test_demand_driven_faq_present(rel: str) -> None:
    """Each file must positively state the corrected demand-driven contract."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    low = text.lower()
    assert "3-6" in text or "3–6" in text, (
        f"{rel} must state the demand-driven FAQ range 3-6 (R-09)."
    )
    assert "hard cap" in low, (
        f"{rel} must state the FAQ hard cap of 10 (R-09)."
    )
