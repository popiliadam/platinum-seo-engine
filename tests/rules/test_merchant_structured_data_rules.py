"""GAP-A-B1 (GAP-A3 merchant structured data): rules/merchant-structured-data.md
content sentinels + the schema-audit template R-token lock.

Rule ids are the REMAPPED ones per the unified dispatch §R-MAP:
R-147 (offer accuracy) + R-148 (shipping/returns org-level-first). The
acquisition spec drafted them as R-130/R-131 — those ids belong to other
batches and must NOT appear here (collision guard).

Frontmatter validity of the new rules file is covered by the existing
tests/rules/test_frontmatter.py glob; these tests lock the CONTENT contract.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
RULES_FILE = ROOT / "rules" / "merchant-structured-data.md"
TEMPLATE = ROOT / "templates" / "reports" / "schema-audit.template.md"
SKILL = ROOT / "skills" / "discovery" / "schema-audit" / "SKILL.md"


def _rules_text() -> str:
    assert RULES_FILE.exists(), (
        "rules/merchant-structured-data.md missing (GAP-A-B1 deliverable)"
    )
    return RULES_FILE.read_text(encoding="utf-8")


def test_r147_r148_headings_present_and_spec_ids_absent():
    """Remapped ids R-147/R-148 are canonical; the spec-draft ids R-130/R-131
    are allocated elsewhere by §R-MAP and must not leak in."""
    text = _rules_text()
    headings = re.findall(r"^### R-(\d+)\b", text, flags=re.MULTILINE)
    assert headings == ["147", "148"], (
        f"expected exactly R-147 + R-148 headings, got {headings}"
    )
    assert not re.search(r"\bR-130\b", text)
    assert not re.search(r"\bR-131\b", text)


def test_r147_offer_accuracy_contract():
    text = _rules_text()
    assert "priceCurrency" in text
    assert "project.config" in text and "currency" in text
    assert "priceValidUntil" in text
    # The engine must never invent offer data it cannot observe.
    assert "never fabricate" in text.lower() or "asla uydur" in text.lower()


def test_r148_org_level_first_contract():
    text = _rules_text()
    # The correct 2025/2026 org-level markup chain.
    assert "hasShippingService" in text
    assert "ShippingService" in text
    assert "shippingConditions" in text
    assert "hasMerchantReturnPolicy" in text
    # Per-offer markup is the override path, not the default.
    assert "OfferShippingDetails" in text
    # Framing: recommended-not-required → opportunity, never compliance failure.
    assert "recommended" in text.lower()
    assert "opportunity" in text.lower() or "fırsat" in text.lower()
    # The invented type must be explicitly warned against.
    assert "OrganizationShippingDetails" in text  # "...does NOT exist" warning
    # Official sources, not third-party summaries.
    assert "developers.google.com/search/docs/appearance/structured-data/merchant-listing" in text
    assert "developers.google.com/search/docs/appearance/structured-data/shipping-policy" in text
    assert "developers.google.com/search/docs/appearance/structured-data/return-policy" in text


def test_schema_audit_template_has_merchant_block_and_no_bare_r_tokens():
    """The report template gains $merchant_findings_md; it must stay free of
    bare R-NNN tokens (tests/rules/test_r_xx_resolution.py only resolves
    rules/content-*.md ids — merchant rules live elsewhere, so the template
    must cite the rule FILE in prose, never a bare id)."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "$merchant_findings_md" in text
    assert not re.search(r"\bR-\d+\b", text), (
        "schema-audit template must not carry bare R-NNN tokens (§0.13)"
    )


def test_skill_cites_merchant_rules_file():
    text = SKILL.read_text(encoding="utf-8")
    assert "rules/merchant-structured-data.md" in text
