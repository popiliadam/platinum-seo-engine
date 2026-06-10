"""Tests for faq-optimization skill (Phase 11 Wave 2 W-F3).

Coverage: frontmatter validation, natural_language sentinel (schema string
form, comma-split phrase quality), R-09 FAQ count cap, R-43 accordion
forbidden, R-29 pasaj alıntılanabilirlik, R-79 FAQPage @graph schema,
R-109/R-110/R-111 AIO citation pattern, profile-aware FAQ disclaimer
(Principle 2), events.jsonl F-9 + F-14 compliance, forbidden tokens grep,
WCAG accessibility, READ-ONLY contract.

Schema authority note:
- skill-frontmatter.schema.json `triggers.natural_language` is a STRING
  type (comma-separated phrases per skill-frontmatter spec), NOT an
  array. Tests therefore parse the string and validate per-phrase
  sentinel quality (each comma-delimited phrase >= 30 chars), preserving
  the brief's intent under schema-first authority (Wave 1 W-F1+W-F2
  precedent reuse).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "production" / "faq-optimization" / "SKILL.md"


def _read_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _parse_frontmatter(text: str | None = None) -> dict:
    text = text if text is not None else _read_skill_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter delimiter pair in {SKILL_PATH}")
    return yaml.safe_load(match.group(1))


# --- Test 1: Frontmatter required-field set + natural_language string ---
def test_frontmatter_required_fields_and_natural_language():
    fm = _parse_frontmatter()
    required = [
        "name",
        "description",
        "version",
        "status",
        "category",
        "inputs",
        "outputs",
        "triggers",
    ]
    for field in required:
        assert field in fm, f"Missing required frontmatter field: {field}"
    assert fm["name"] == "faq-optimization"
    assert fm["category"] == "production"
    assert fm["status"] in {"active", "deprecated", "wip"}
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str), (
        f"natural_language must be string per skill-frontmatter schema, "
        f"got {type(nl).__name__}"
    )
    assert len(nl) >= 30, f"natural_language total <30 char: {len(nl)}"


# --- Test 2: natural_language phrase quality (>= 30 chars per phrase) ---
def test_natural_language_phrase_quality():
    """Schema declares natural_language as a STRING; we split on commas
    and validate each phrase carries enough sentinel signal (>= 30
    chars) — Wave 1 W-F2 paterni reuse."""
    fm = _parse_frontmatter()
    nl = fm["triggers"]["natural_language"]
    phrases = [
        p.strip().strip('"').strip("'")
        for p in nl.replace("\n", " ").split(",")
        if p.strip()
    ]
    assert len(phrases) >= 5, f"Expected >= 5 trigger phrases, got {len(phrases)}"
    for phrase in phrases:
        assert len(phrase) >= 30, (
            f"natural_language phrase < 30 chars (lesson 8 sentinel): "
            f"{phrase!r} len={len(phrase)}"
        )


# --- Test 3: R-09 FAQ count cap (talep-güdümlü 3-6, hard cap 10) ---
def test_r09_faq_count_cap():
    """R-09 corrected 2026-06-10 (FIX-H H7): FAQ is demand-driven
    (talep-güdümlü) — 3-6 where evidence exists (PAA presence, real
    user questions), hard cap 10 independent of word count. The old
    '10 standart / 15 cap 3000+ word' contract is retired and must
    not resurface in the SKILL body."""
    text = _read_skill_text()
    assert "R-09" in text, "R-09 rule reference missing"
    assert "talep-güdümlü" in text, (
        "R-09 demand-driven (talep-güdümlü) framing missing"
    )
    assert "3-6" in text, "R-09 demand band (3-6 FAQ) missing"
    assert "hard cap 10" in text, "R-09 hard cap 10 missing"
    assert "PAA" in text, "R-09 evidence source (PAA) missing"
    assert "DURUR #2" in text, "DURUR #2 (R-09 cap aşımı) gate missing"
    assert "faq_count > 10" in text, (
        "DURUR #2 must reject above the hard cap (faq_count > 10)"
    )
    # Retired pre-2026-06-10 contract tokens must be gone:
    assert "3000" not in text, (
        "old 3000+ word threshold must be retired — R-09 cap is "
        "word-count independent"
    )
    assert "max 15" not in text and "15 cap" not in text, (
        "old 15-FAQ cap must be retired (hard cap is 10)"
    )
    assert "faq_count >= 16" not in text, (
        "old 16+ REJECT threshold must be retired (DURUR #2 fires > 10)"
    )


# --- Test 4: R-43 accordion forbidden (`<details>`, `<summary>` YASAK) ---
def test_r43_accordion_forbidden():
    text = _read_skill_text()
    assert "R-43" in text, "R-43 rule reference missing"
    assert "<details>" in text, "<details> ban reference missing"
    assert "<summary>" in text, "<summary> ban reference missing"
    assert "YASAK" in text, "YASAK enforcement language missing"
    assert "DURUR #3" in text, "DURUR #3 (R-43 accordion) gate missing"


# --- Test 5: R-29 pasaj alıntılanabilirlik (cevap-önce + TL;DR) ---
def test_r29_passage_citation():
    text = _read_skill_text()
    assert "R-29" in text, "R-29 rule reference missing"
    assert "cevap-önce" in text, "cevap-önce phrase missing"
    assert "TL;DR" in text, "TL;DR phrase missing"
    assert "self-contained" in text.lower(), "self-contained concept missing"


# --- Test 6: R-79 FAQPage @graph schema valid ---
def test_r79_faqpage_schema():
    text = _read_skill_text()
    assert "R-79" in text, "R-79 rule reference missing"
    assert "FAQPage" in text, "FAQPage entity reference missing"
    assert "@graph" in text, "@graph JSON-LD reference missing"
    assert "mainEntity" in text, "mainEntity array reference missing"
    assert "DURUR #4" in text, "DURUR #4 (R-79 schema validate) gate missing"


# --- Test 7: R-109/R-110/R-111 AIO citation pattern + 500 word density ---
def test_aio_citation_pattern():
    text = _read_skill_text()
    aio_rules = ["R-109", "R-110", "R-111"]
    for rule in aio_rules:
        assert rule in text, f"AIO rule missing: {rule}"
    assert "500" in text, "500 word citation density threshold missing"
    assert "AIO" in text, "AIO concept reference missing"
    assert "DURUR #6" in text, "DURUR #6 (AIO over-citation) gate missing"


# --- Test 8: Profile-aware FAQ disclaimer (Principle 2 enum 5-value) ---
def test_profile_aware_principle_2():
    text = _read_skill_text()
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    found = sum(1 for p in profile_enum if p in text)
    assert found >= 4, (
        f"Profile enum referenced too few values: {found}/5; expected >= 4"
    )
    assert "Principle 2" in text, "Principle 2 (Profile-Aware) header missing"
    # YMYL disclaimer enforcement (R-51)
    assert "R-51" in text, "R-51 (YMYL disclaimer) reference missing"
    assert "disclaimer" in text.lower(), "disclaimer concept missing"


# --- Test 9: events.jsonl F-9 (event_kind=work) + F-14 (event_type) ---
def test_events_jsonl_compliance():
    text = _read_skill_text()
    # F-9 event_kind=work (ADR-020 production output enum)
    assert "event_kind" in text, "event_kind field missing"
    assert "work" in text, "work enum value missing (ADR-020)"
    # F-14 event_type=content_revise (10-enum compliance)
    assert "event_type" in text, "event_type field missing"
    assert "content_revise" in text, "content_revise enum value missing (events.schema)"
    # F-14 5-required-field
    assert "schema_version" in text, "schema_version field missing (events.schema)"
    assert "project_id" in text, "project_id field missing (events.schema)"
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "events.jsonl" in outputs_str, (
        f"events.jsonl not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 10: Forbidden tokens grep CLEAN (plugin-agnostik + drift) ---
def test_forbidden_tokens_clean():
    text = _read_skill_text()
    forbidden = [
        # plugin-specific slugs (plugin-agnostik enforcement)
        "dentnotion",
        "vento",
        "eykom",
        "bigcattr",
        "calitte",
        "lastiksa",
        "noraninsaat",
        "adstark",
        # legacy/stale frontmatter field names (drift sentinels)
        "estimated_credits_per_call",
        "estimated_credits_per_url",
        "metric_name",
    ]
    for token in forbidden:
        assert token not in text, f"Forbidden token leaked into SKILL.md: {token!r}"


# --- Test 11: WCAG 2.1 AA accessibility (h3 + focus-visible) ---
def test_wcag_accessibility():
    text = _read_skill_text()
    assert "WCAG" in text, "WCAG accessibility reference missing"
    assert "h3" in text.lower(), "h3 heading hierarchy reference missing"
    assert "focus-visible" in text, "focus-visible CSS reference missing"


# --- Test 12: READ-ONLY contract (F-6 — no transaction.* call sites) ---
def test_read_only_contract():
    """Detect actual transaction.* call sites (write operations), not
    documentation prose mentioning the YASAK ban itself. Match patterns
    that look like code invocations: transaction.append(, transaction.
    update(, transaction.delete( — the trailing paren disambiguates
    call sites from descriptive ban prose like
    'transaction.append/update/delete YASAK'."""
    text = _read_skill_text()
    call_patterns = [
        r"transaction\.append\s*\(",
        r"transaction\.update\s*\(",
        r"transaction\.delete\s*\(",
    ]
    for pattern in call_patterns:
        assert not re.search(pattern, text), (
            f"READ-ONLY violation: call-site pattern matched: {pattern}"
        )
    # Positive READ-ONLY contract assertion documented in body
    assert "READ-ONLY" in text, "READ-ONLY contract assertion missing in body"


# --- Test 13: consumes 3 master.xlsx sheets + project-config + 6 rules ---
def test_consumes_three_master_sheets():
    text = _read_skill_text()
    assert "master.xlsx#new_content_plan" in text, "new_content_plan consume missing"
    assert "master.xlsx#content_decay" in text, "content_decay consume missing"
    assert "master.xlsx#content_improve" in text, "content_improve consume missing"
    fm = _parse_frontmatter(text)
    consumes = fm.get("consumes", [])
    sheets_found = sum(
        1 for sheet in ["new_content_plan", "content_decay", "content_improve"]
        if any(sheet in c for c in consumes)
    )
    assert sheets_found == 3, (
        f"consumes missing one of 3 master.xlsx sheets: {consumes}"
    )
    # 6 rules + 1 template
    rule_count = sum(1 for c in consumes if c.startswith("rules:"))
    assert rule_count == 6, f"Expected 6 rules in consumes, got {rule_count}"
    template_count = sum(1 for c in consumes if c.startswith("templates:"))
    assert template_count == 1, (
        f"Expected 1 template in consumes, got {template_count}"
    )
