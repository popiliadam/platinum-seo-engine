"""tests/commands/test_new_blog_command_skill_parity.py — F3 lock (Audit #2).

``/pseo-new-blog`` contradicted ``skills/production/new-blog/SKILL.md``:

  - called the skill "aktif/active" — skill frontmatter is ``status: wip`` and
    the runtime (``scripts/production/new_blog.py``) does not yet exist;
  - listed outputs ``article.{md,html,jsonld}`` — the skill emits
    ``article.HTML`` + ``schema.jsonld`` + ``meta-tags.json`` +
    ``upload-instructions.md`` (no ``.md`` article, no top-level ``.jsonld``);
  - promised ``--mode publish`` writes ``master.xlsx[new_content_plan]``
    lifecycle ``PLANNED -> DONE`` via ``transaction.update`` — but the skill is
    READ-ONLY vs ``master.xlsx`` and never calls append/update/delete; its only
    mutation is the ``events.jsonl`` audit append.

new-blog is a DRAFT-ONLY artifact generator. These tests pin the command to the
skill contract: output basenames are READ FROM the skill frontmatter so the
command tracks the skill, and the false write/status claims must stay gone.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CMD = REPO / "commands" / "pseo-new-blog.md"
SKILL = REPO / "skills" / "production" / "new-blog" / "SKILL.md"

_OUTPUT = re.compile(r"outputs/blog/\{slug\}/([A-Za-z0-9_.-]+)")


def _skill_output_basenames() -> set[str]:
    """The article-artifact basenames the skill declares (frontmatter + body)."""
    return set(_OUTPUT.findall(SKILL.read_text(encoding="utf-8")))


def test_skill_contract_source_is_wip_and_readonly() -> None:
    """Anchor: confirm the contract we pin the command to (skill is the source)."""
    skill = SKILL.read_text(encoding="utf-8")
    assert re.search(r"^status:\s*wip\s*$", skill, re.MULTILINE), "skill must be wip"
    assert "READ-ONLY" in skill, "skill must declare it is read-only vs master.xlsx"
    # The 4 article artifacts the skill emits (no .md article).
    assert _skill_output_basenames() >= {
        "article.html",
        "schema.jsonld",
        "meta-tags.json",
        "upload-instructions.md",
    }


def test_command_cites_every_skill_output() -> None:
    """The command must document exactly the skill's output artifacts."""
    cmd = CMD.read_text(encoding="utf-8")
    missing = sorted(b for b in _skill_output_basenames() if b not in cmd)
    assert not missing, (
        f"pseo-new-blog.md omits skill-declared outputs {missing}; it must match "
        "the new-blog SKILL.md outputs contract."
    )


def test_command_does_not_claim_md_article_output() -> None:
    """The skill emits article.html only — the .md article form is fictional."""
    cmd = CMD.read_text(encoding="utf-8")
    assert "article.md" not in cmd, "pseo-new-blog.md still cites a fictional article.md"
    assert "article.{md" not in cmd, (
        "pseo-new-blog.md still cites the article.{md,html,jsonld} brace form "
        "(skill emits article.html + schema.jsonld separately, no .md article)"
    )


def test_command_makes_no_master_xlsx_write_claim() -> None:
    """new-blog is READ-ONLY vs master.xlsx — no lifecycle/transaction write."""
    cmd = CMD.read_text(encoding="utf-8")
    assert "PLANNED → DONE" not in cmd and "PLANNED -> DONE" not in cmd, (
        "pseo-new-blog.md still promises a master.xlsx lifecycle PLANNED->DONE "
        "transition; the skill is read-only and never writes the workbook."
    )
    assert "transaction.update" not in cmd, (
        "pseo-new-blog.md still cites transaction.update; new-blog never calls "
        "transaction append/update/delete against master.xlsx."
    )
    # transaction.py must not be listed as a new-blog script dependency at all
    # (the skill's only state mutation is the events.jsonl audit append).
    assert "transaction.py" not in cmd, (
        "pseo-new-blog.md still lists scripts/excel/transaction.py as a "
        "dependency; new-blog does not touch the workbook."
    )


def test_command_status_matches_skill_wip() -> None:
    """The command must not advertise the wip skill as aktif/active."""
    cmd = CMD.read_text(encoding="utf-8")
    assert "wip" in cmd, "pseo-new-blog.md must mark the new-blog skill status as wip"
    for stale in ("Phase 11 W1, aktif", "Phase 11 W1, active"):
        assert stale not in cmd, (
            f"pseo-new-blog.md still calls the wip new-blog skill {stale!r}"
        )
