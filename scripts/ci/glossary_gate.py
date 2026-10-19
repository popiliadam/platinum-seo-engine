#!/usr/bin/env python3
"""glossary_gate.py — CI step 3: a glossary check that can go red (K-07).

The old step ran the glossary-audit SKILL.md blocks: orphan and missing terms
were computed and thrown away (``spec_terms`` was never used), so the step
could only fail if GLOSSARY.md was empty or REFERENCE_INDEX lost its link.

Red when
* a term from spec §20 is absent from docs/GLOSSARY.md (the glossary must be
  a superset of the spec's core terms), or
* docs/REFERENCE_INDEX.md no longer links GLOSSARY.md, or
* more glossary terms than ``ORPHAN_BUDGET`` are used NOWHERE else in the
  repo (skills, commands, rules, docs, scripts) — an invented or stale term
  pushes the count over the budget.

Exit 0 = pass, 1 = red. The report lists every orphan and missing term.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GLOSSARY = REPO / "docs" / "GLOSSARY.md"
SPEC = REPO / "docs" / "superpowers" / "specs" / "2026-04-30-platinum-seo-engine-design.md"
REFERENCE_INDEX = REPO / "docs" / "REFERENCE_INDEX.md"
SEARCH_DIRS = ("skills", "commands", "rules", "docs", "scripts", "templates", "hooks")
# Glossary terms used nowhere outside GLOSSARY.md today. Lower it when one is
# put to use or removed; raising it is a reviewed change.
ORPHAN_BUDGET = 1  # 'Repo Hierarchy' (2026-10-19)
# Spec §20 spelling → glossary entry, where they differ only by language.
SPEC_ALIASES = {"Pilot Proje": "Pilot Project"}

_TERM_RE = re.compile(r"^- \*\*([^\*]+)\*\*", re.MULTILINE)
_SPEC_SECTION_RE = re.compile(r"^## 20\.[^\n]*\n(.*?)(?=^## \d+\.)", re.MULTILINE | re.DOTALL)
_SPEC_TERM_RE = re.compile(r"^- \*\*([A-Z][^\*]+)\*\*", re.MULTILINE)


def glossary_terms(text: str) -> set[str]:
    return {t.strip() for t in _TERM_RE.findall(text)}


def spec_terms(text: str) -> set[str]:
    """Spec §20 writes ``- **Term:** definition`` — the colon sits inside the bold."""
    m = _SPEC_SECTION_RE.search(text)
    raw = (t.strip().rstrip(":").strip() for t in _SPEC_TERM_RE.findall(m.group(1))) if m else ()
    return {SPEC_ALIASES.get(t, t) for t in raw}


def _corpus() -> str:
    parts: list[str] = []
    for d in SEARCH_DIRS:
        for p in (REPO / d).rglob("*"):
            if (p.is_file() and p.suffix in {".md", ".py", ".json", ".sh"}
                    and p not in (GLOSSARY, Path(__file__).resolve())):  # not itself
                try:
                    parts.append(p.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
    return "\n".join(parts).casefold()


def evaluate(glossary_text: str, spec_text: str, ref_index_text: str, corpus: str) -> dict:
    terms = glossary_terms(glossary_text)
    missing = sorted(spec_terms(spec_text) - terms)
    orphans = sorted(t for t in terms if t.casefold() not in corpus)
    problems: list[str] = []
    if not terms:
        problems.append("GLOSSARY.md has no '- **Term** —' entries")
    if missing:
        problems.append(f"spec §20 terms missing from GLOSSARY.md: {missing}")
    if "GLOSSARY.md" not in ref_index_text:
        problems.append("REFERENCE_INDEX.md does not link GLOSSARY.md")
    if len(orphans) > ORPHAN_BUDGET:
        problems.append(f"{len(orphans)} orphan glossary term(s) > budget {ORPHAN_BUDGET}: {orphans}")
    return {"terms": len(terms), "missing_from_glossary": missing, "orphans": orphans,
            "problems": problems}


def main() -> int:
    report = evaluate(GLOSSARY.read_text(encoding="utf-8"), SPEC.read_text(encoding="utf-8"),
                      REFERENCE_INDEX.read_text(encoding="utf-8"), _corpus())
    status = "RED" if report["problems"] else "PASS"
    print(f"glossary-gate {status}: {json.dumps(report, ensure_ascii=False)}")
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
