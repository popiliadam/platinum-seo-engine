"""Regression: every R-XX cited in templates/ MUST be defined in rules/content-*.md
or marked (superseded) per ADR-038 K-01 closure clarification.

Locks K-01 audit finding (R-26 referenced 5x but never defined). Per ADR-038
gap-tolerant policy + 2026-05-07 K-01 clarification: referenced-but-undefined
R-XX = MUST-FIX (not migration miss).
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
RULES = ROOT / "rules"
TEMPLATES = ROOT / "templates"

R_XX = re.compile(r"\bR-(\d+)\b")
R_XX_DEF = re.compile(r"^### R-(\d+)\b", re.MULTILINE)
R_XX_SUPERSEDED = re.compile(r"^### R-(\d+).*\(superseded", re.MULTILINE | re.IGNORECASE)


def _all_defined():
    """Return set of R-XX numbers defined (including superseded markers) in
    rules/content-*.md and rules/content-quality.md."""
    defined = set()
    for f in sorted(RULES.glob("content-*.md")):
        text = f.read_text(encoding="utf-8")
        for m in R_XX_DEF.finditer(text):
            defined.add(int(m.group(1)))
    return defined


def _all_cited_in_templates():
    """Return set of R-XX numbers cited in templates/**/*.{md,html}."""
    cited = set()
    for pattern in ("*.md", "*.html"):
        for f in TEMPLATES.rglob(pattern):
            text = f.read_text(encoding="utf-8")
            for m in R_XX.finditer(text):
                cited.add(int(m.group(1)))
    return cited


def test_all_template_r_xx_defined():
    """Every R-XX cited in templates/ MUST be defined in rules/content-*.md.

    Per ADR-038 (gap-tolerant + 2026-05-07 K-01 clarification): undefined R-XX
    is a MUST-FIX, not migration miss. Either define the rule, mark
    `(superseded by R-YY)`, or remove the citation.
    """
    cited = _all_cited_in_templates()
    defined = _all_defined()
    undefined = cited - defined
    assert not undefined, (
        f"R-XX cited in templates/ but not defined in rules/content-*.md: "
        f"{sorted(undefined)}. Per ADR-038 K-01 clarification, every R-XX MUST "
        f"be either defined or marked (superseded)."
    )
