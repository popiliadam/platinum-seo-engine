"""S-04 — rules must not tell writers to vary structure to hide a mechanical trace.

"Don't repeat the same cadence across posts — avoid a mechanical fingerprint"
adds no value for readers; it disguises a template, which is what Google's
spam policy covers. The principle instead: every page is structured around its
own user question; variety is a result, not a goal.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIDING = re.compile(r"parmak[ -]?izi|fingerprint|post'lar arası|mekanik (imza|kadans)", re.IGNORECASE)


def test_no_rule_justifies_structure_by_hiding_a_pattern() -> None:
    offenders = []
    for path in sorted((ROOT / "rules").glob("*.md")):
        for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if HIDING.search(line):
                offenders.append(f"{path.name}:{n}: {line[:90]}")
    assert offenders == []


def test_craft_rules_state_the_question_first_principle() -> None:
    text = (ROOT / "rules" / "content-craft-discipline.md").read_text(encoding="utf-8")
    assert "kendi kullanıcı sorusuna" in text
    assert "çeşitlilik amaç değil" in text
