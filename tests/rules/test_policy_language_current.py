"""S-10 / S-11 — rule rationales use Google's current policy language.

S-10: R-32 called a client publishing on Medium/LinkedIn "parasite SEO". Google's
      site reputation policy (rewritten 2026-08-28) is about THIRD-PARTY content
      hosted on the site's own domain without sufficient editorial oversight.
S-11: "Helpful Content Update penalty" — that system joined core ranking in
      March 2024; there is no separate update or penalty to cite.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _blocks() -> list[tuple[str, str]]:
    out = []
    for folder in ("rules", "skills", "templates", "commands"):
        for path in sorted((ROOT / folder).rglob("*.md")) + sorted((ROOT / folder).rglob("*.html")):
            out.append((str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")))
    return out


def test_no_helpful_content_update_penalty_language() -> None:
    offenders = [rel for rel, text in _blocks()
                 if "helpful content update" in text.lower() or " HCU" in text]
    assert offenders == []


def test_r32_describes_the_site_reputation_policy() -> None:
    text = (ROOT / "rules" / "content-quality.md").read_text(encoding="utf-8")
    block = text[text.index("### R-32"):]
    block = block[: block.index("\n### ", 5)]
    assert "2026-08-28" in block
    assert "spam-policies#site-reputation" in block
    assert "editoryal denetim" in block
    assert "Medium" not in block.split("**Statement.**")[1].split("**Rationale.**")[0]
