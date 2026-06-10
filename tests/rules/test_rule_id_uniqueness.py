"""H1 (FIX-H): every ``### R-NN`` heading across rules/content-*.md MUST be unique.

R-78 was defined twice — Article Schema (rules/content-seo-discipline.md) and
AI-Image IPTC (rules/content-html-discipline.md). The IPTC rule was renumbered
to R-123 (ADR-038 history-stable: the old id is deprecated-in-place via a
``supersedes`` note, never silently reused). This invariant prevents a
recurrence and catches any future duplicate rule-id heading.
"""
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
RULES = ROOT / "rules"
R_XX_DEF = re.compile(r"^### R-(\d+)\b", re.MULTILINE)


def test_rule_id_headings_unique_across_content_rules():
    """No R-NN number may head more than one ``### R-NN`` block across all
    rules/content-*.md files. (Superseded/deprecated rules still count as a
    single definition of their id.)"""
    seen = defaultdict(list)
    for f in sorted(RULES.glob("content-*.md")):
        text = f.read_text(encoding="utf-8")
        for m in R_XX_DEF.finditer(text):
            seen[int(m.group(1))].append(f.name)
    dups = {n: files for n, files in seen.items() if len(files) > 1}
    assert not dups, (
        f"Duplicate `### R-NN` headings across rules/content-*.md: {dups}. "
        f"Per ADR-038, renumber the newer rule and leave a supersedes note; "
        f"never reuse a rule id."
    )
