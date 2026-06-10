"""FIX-H rule-pack corrections (H1-H10): lock the NEW canonical rule text.

Each test asserts the corrected (post-FIX-H) wording and FAILS on the pre-fix
text — genuine RED->GREEN regression locks for documentation corrections that
were previously unpinned. Evidence/line refs re-derived from the rule files
2026-06-10 (full-repo audit). See
docs/superpowers/plans/amo/2026-06-10-UNIFIED-remediation-WORKER-DISPATCH.md
section FIX-H.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
RULES = ROOT / "rules"


def _read(name: str) -> str:
    return (RULES / name).read_text(encoding="utf-8")


def _rule_block(text: str, rid: str) -> str:
    """Return the body of a single ``### R-NN ...`` block (heading -> next
    ``### ``/``## ``/end-of-file). Empty string if the rule is undefined."""
    m = re.search(
        rf"^### {re.escape(rid)}\b.*?(?=^### |^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(0) if m else ""


# --- H1: R-78 IPTC renumbered to R-123 (ADR-038-safe) ----------------------
def test_h1_iptc_rule_is_r123_not_r78():
    html = _read("content-html-discipline.md")
    assert "### R-123:" in html, "IPTC rule heading must be renumbered to R-123"
    assert "IPTC" in _rule_block(html, "R-123"), "R-123 must be the AI-Image IPTC rule"
    assert "### R-78:" not in html, (
        "content-html-discipline.md must no longer use the duplicate id R-78 "
        "(R-78 belongs to Article Schema in content-seo-discipline.md)"
    )
    block = _rule_block(html, "R-123")
    assert "supersedes" in block.lower() and "R-78" in block, (
        "R-123 must carry a supersedes note pointing back to the old R-78 id"
    )


def test_h1_iptc_crosslinks_corrected():
    block = _rule_block(_read("content-html-discipline.md"), "R-123")
    assert block, "R-123 block must exist"
    # Stale labels: R-73 is 'Image Manual Upload' (not '1200x675');
    # R-74 is 'Multi-Skill Collaborative Output' (not bare 'manual upload').
    assert "1200x675" not in block, "stale 'R-73 (1200x675)' cross-link must be corrected"
    assert "R-73 (manual upload)" in block, "R-73 cross-link must read 'manual upload'"


def test_h1_content_quality_collision_note_fixed():
    cq = _read("content-quality.md")
    assert "Çakışma yok" not in cq, (
        "the 'Çakışma yok' claim was false — R-78 WAS a collision until the "
        "2026-06-10 R-123 renumber; the note must record the disambiguation"
    )
    assert "R-123" in cq, "content-quality.md must reference the R-78->R-123 renumber"


# --- H2: NEW R-124 YMYL expert-review sign-off -----------------------------
def test_h2_r124_ymyl_review_signoff_exists():
    block = _rule_block(_read("content-eeat-discipline.md"), "R-124")
    assert block, "R-124 (YMYL expert-review sign-off) must be defined in content-eeat-discipline.md"
    low = block.lower()
    assert "ymyl" in low
    assert "events.jsonl" in low, "review record must be captured as an events.jsonl audit row"
    assert "inceleyen" in low or "reviewer" in low, "reviewer name must be required"
    assert ("sürüm" in low or "revision" in low or "hash" in low or "version" in low), (
        "content version (hash/revision id) must be required"
    )
    assert "RED" in block, "missing review record must be a RED failure mode"


# --- H3: R-06 + R-25 phantom internal_links sheet repointed ----------------
def test_h3_r06_no_phantom_internal_links_sheet():
    block = _rule_block(_read("content-seo-discipline.md"), "R-06")
    assert "master.xlsx[internal_links]" not in block, (
        "internal_links sheet does not exist (19-sheet schema); repoint to "
        "topical_map + master_task auto_generated rows (Option A)"
    )
    assert "master_task" in block or "topical_map" in block


def test_h3_r25_no_phantom_internal_links_sheet():
    block = _rule_block(_read("content-update-discipline.md"), "R-25")
    assert "master.xlsx[internal_links]" not in block
    assert "master_task" in block or "topical_map" in block


# --- H4: R-35 single canonical title/desc authority ------------------------
def test_h4_r35_single_authority_with_heuristic_note():
    block = _rule_block(_read("content-html-discipline.md"), "R-35")
    assert "580" in block and "990" in block, "R-35 canonical px caps: title 580 / desc 990"
    low = block.lower()
    assert "tek otorite" in low or "single authority" in low, "R-35 must declare itself the single authority"
    assert "60/160" in block, "char counts (60/160) must be named as the tech-audit heuristic"
    assert "tahmin" in low or "heuristic" in low or "yaklaşık" in low, "char counts are only an approximation"
    assert "tech-audit" in low, "the 60/160 char heuristic belongs to tech-audit, not production skills"


# --- H5: R-104 single source for stats density -----------------------------
def test_h5_r104_single_source_note():
    block = _rule_block(_read("content-eeat-discipline.md"), "R-104")
    low = block.lower()
    assert "tek kaynak" in low or "single source" in low or "tek otorite" in low, (
        "R-104 must declare itself the single source for stats-density numbers"
    )
    assert "production skill" in low or "üretim skill" in low, (
        "production skills must not restate divergent numbers"
    )


# --- H6: R-99 Google-Extended correction -----------------------------------
def test_h6_r99_google_extended_corrected():
    block = _rule_block(_read("content-llm-discipline.md"), "R-99")
    assert "AIO citation şansı düşer" not in block, (
        "false claim: Google-Extended does NOT govern Search ranking or AI Overview inclusion"
    )
    low = block.lower()
    assert "gemini" in low or "vertex" in low, "rationale must scope Google-Extended to Gemini/Vertex"
    assert "googlebot" in low or "snippet" in low, "AIO follows Googlebot + snippet controls"


# --- H7: R-09 demand-driven FAQ + R-79 date/benefit fix --------------------
def test_h7_r09_demand_driven_faq():
    block = _rule_block(_read("content-seo-discipline.md"), "R-09")
    assert "10 adet FAQ" not in block, "fixed '10 FAQ standard' replaced by demand-driven 3-6"
    assert "3-6" in block or "3–6" in block, "FAQ count is demand-driven 3-6 where evidence exists"
    assert "PAA" in block, "evidence = PAA presence / real user questions"
    assert "10" in block, "hard cap remains 10"


def test_h7_r79_august_2023_no_trust_signal():
    block = _rule_block(_read("content-seo-discipline.md"), "R-79")
    assert "Aralık 2023" not in block, "FAQ rich-result restriction was August 2023, not December"
    assert "Ağustos 2023" in block or "August 2023" in block
    assert "domain trust signal" not in block, "the 'domain trust signal' benefit was invented"


# --- H8: R-13 deprecated + cadence ranges with per-post variation ----------
def test_h8_r13_bold_cadence_deprecated():
    block = _rule_block(_read("content-seo-discipline.md"), "R-13")
    assert "deprecated" in block.lower(), (
        "R-13 (bold every ~250 words) is a mechanical fingerprint, not a ranking "
        "signal — deprecate (ADR-038: keep the id, mark deprecated)"
    )


def test_h8_cadence_variation_instruction():
    seo = _read("content-seo-discipline.md")
    llm = _read("content-llm-discipline.md")
    for rid, src in [("R-06", seo), ("R-07", seo), ("R-30", seo), ("R-106", llm)]:
        block = _rule_block(src, rid)
        low = block.lower()
        assert ("varyasyon" in low or "örnekle" in low or "birebir" in low or "identical" in low), (
            f"{rid} must convert its fixed cadence to a range with an explicit "
            f"per-post variation instruction (no identical structural cadence across posts)"
        )


# --- H9: uncited multipliers relabeled as heuristic ------------------------
def test_h9_multipliers_relabeled_uncited():
    seo = _read("content-seo-discipline.md")
    assert "citation şansı 3x artırır" not in seo, "R-01 3x multiplier is uncited"
    assert "trafik 8x" not in seo, "R-107 8x multiplier is uncited"
    assert "kanıtlanmamış sezgisel" in seo.lower(), (
        "uncited multipliers (R-01/R-107/R-109/R-113) must be relabeled "
        "'kanıtlanmamış sezgisel' per Principle 1 (uydurma yasak)"
    )


# --- H10: R-37 / R-44 authority-score scale re-anchored --------------------
def test_h10_r37_authority_allowlist_anchored():
    block = _rule_block(_read("content-eeat-discipline.md"), "R-37")
    low = block.lower()
    assert "allowlist" in low or "küratör" in low, (
        "primary mechanism = curated per-project source allowlist (not an unnamed 0-60 score)"
    )
    assert "ahrefs dr" in low, "if a numeric gate is used it must be explicitly Ahrefs DR"


def test_h10_r44_authority_allowlist_anchored():
    block = _rule_block(_read("content-quality.md"), "R-44")
    low = block.lower()
    assert "allowlist" in low or "küratör" in low or "ahrefs dr" in low, (
        "R-44 source verification must re-anchor the otorite-skoru to a curated "
        "allowlist / explicit Ahrefs DR, not an unnamed metric"
    )
