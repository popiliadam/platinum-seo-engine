"""Tests for revise-content skill (Phase 11 Wave 1 W-F2).

Coverage: frontmatter validation, natural_language sentinel (schema string
form, comma-split phrase quality), R-87 section-targeted enforcement,
R-88 freshness theater detect, R-89 canonical preserve, R-103 version
increment, profile-aware revise (Principle 2), forbidden tokens grep,
READ-ONLY contract, F-2/F-6/F-8 schema authority compliance.

Schema authority note:
- skill-frontmatter.schema.json `triggers.natural_language` is a STRING
  type (comma-separated phrases per skill-frontmatter spec), NOT an
  array. Tests therefore parse the string and validate per-phrase
  sentinel quality (each comma-delimited phrase >= 30 chars), preserving
  the brief's intent under schema-first authority.
"""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "production" / "revise-content" / "SKILL.md"
SKILL_FRONTMATTER_SCHEMA = REPO_ROOT / "schemas" / "skill-frontmatter.schema.json"


def _read_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _parse_frontmatter(text: str | None = None) -> dict:
    text = text if text is not None else _read_skill_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter delimiter pair in {SKILL_PATH}")
    return yaml.safe_load(match.group(1))


# --- Test 1: Frontmatter required-field set (skill-frontmatter.schema.json) ---
def test_frontmatter_required_fields():
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
    assert fm["name"] == "revise-content"
    assert fm["category"] == "production"
    assert fm["status"] in {"active", "deprecated", "wip"}


# --- Test 2: natural_language phrase quality (>= 30 chars per phrase) ---
def test_natural_language_phrase_quality():
    """Schema declares natural_language as a STRING; we split on commas
    and validate each phrase carries enough sentinel signal (>= 30
    chars) — equivalent to the brief's per-item >= 30 char intent."""
    fm = _parse_frontmatter()
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str), (
        f"natural_language must be string per skill-frontmatter schema, "
        f"got {type(nl).__name__}"
    )
    # Strip outer whitespace and split on top-level commas; quoted-phrase
    # tolerant via shlex with posix=False to retain quote tokens.
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


# --- Test 3: consumes content_decay + master_task (F-2 + F-6 READ-ONLY) ---
def test_consumes_decay_master_task():
    text = _read_skill_text()
    assert "master.xlsx#content_decay" in text, "content_decay consume missing"
    assert "master.xlsx#master_task" in text, "master_task consume missing"
    fm = _parse_frontmatter(text)
    consumes = fm.get("consumes", [])
    has_decay = any("content_decay" in c for c in consumes)
    has_master_task = any("master_task" in c for c in consumes)
    assert has_decay, f"consumes missing content_decay: {consumes}"
    assert has_master_task, f"consumes missing master_task: {consumes}"


# --- Test 4: R-87 section-targeted enforcement (full overhaul DURUR gate) ---
def test_r87_section_targeted_enforced():
    text = _read_skill_text()
    assert "R-87" in text, "R-87 rule reference missing"
    assert "section-targeted" in text, "section-targeted phrase missing"
    # full-overhaul DURUR gate must exist
    assert "DURUR #5" in text, "DURUR #5 (scope=full) gate missing"
    assert "scope=full" in text or 'scope == "full"' in text, (
        "scope=full reference missing in routing"
    )


# --- Test 5: R-88 freshness theater detect (delta=0 → RED) ---
def test_r88_freshness_theater_enforced():
    text = _read_skill_text()
    assert "R-88" in text, "R-88 rule reference missing"
    assert "freshness theater" in text, "freshness theater phrase missing"
    assert "DURUR #4" in text, "DURUR #4 (R-88 freshness theater) gate missing"
    assert "delta" in text.lower(), "delta concept missing"
    assert "RED" in text, "RED failure mode missing"


# --- Test 6: R-89 canonical preserve (URL change reject) ---
def test_r89_canonical_preserve():
    text = _read_skill_text()
    assert "R-89" in text, "R-89 rule reference missing"
    assert "canonical" in text.lower(), "canonical concept missing"
    assert "preserve" in text.lower() or "immutable" in text.lower(), (
        "preserve/immutable enforcement language missing"
    )
    assert "DURUR #6" in text, "DURUR #6 (R-89 canonical change) gate missing"


# --- Test 7: R-103 content version increment (major revise → version bump) ---
def test_r103_version_increment():
    text = _read_skill_text()
    assert "R-103" in text, "R-103 rule reference missing"
    assert "version" in text.lower(), "version concept missing"
    assert "increment" in text.lower() or "bump" in text.lower(), (
        "increment/bump verb missing"
    )
    # Major-vs-minor distinction documented
    assert "Major revise" in text, "Major revise classification missing"


# --- Test 8: change_summary.md format (section-targeted diff) ---
def test_change_summary_format():
    text = _read_skill_text()
    assert "change_summary" in text, "change_summary artifact missing"
    assert "Word Delta" in text, "Word Delta line missing in change_summary spec"
    assert "Claim Delta" in text, "Claim Delta line missing"
    # outputs[] declares the file
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "change_summary.md" in outputs_str, (
        f"change_summary.md not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 9: events.jsonl content_revise + schema-valid event_kind=work ---
def test_events_event_type_content_revise():
    text = _read_skill_text()
    assert "content_revise" in text, "content_revise event_type missing (F-8)"
    assert "event_type" in text, "event_type field missing in routing"
    # B5-03: event_kind MUST be the schema-valid `work` — `production` is NOT
    # a member of the events.schema event_kind enum, and content_revise is a
    # WORK event (events.schema allOf content_revise coupling); mirror
    # new-blog SKILL.md.
    assert not re.search(r"event_kind`?\s*=\s*`?production", text), (
        "revise-content documents an invalid event_kind=production; "
        "content_revise must be event_kind=work (events.schema enum)"
    )
    assert re.search(r"event_kind`?\s*=\s*`?work\b", text), (
        "revise-content must document event_kind=work for content_revise"
    )
    # Schema-valid cross-check: work is in the events.schema event_kind enum.
    schema = json.loads(
        (REPO_ROOT / "schemas" / "events.schema.json").read_text("utf-8")
    )
    assert "work" in schema["properties"]["event_kind"]["enum"], (
        "events.schema event_kind enum drifted: 'work' missing"
    )
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "events.jsonl" in outputs_str, (
        f"events.jsonl not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 10: profile-aware revise (Principle 2 enum 5-value) ---
def test_profile_aware_principle_2():
    text = _read_skill_text()
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    found = sum(1 for p in profile_enum if p in text)
    assert found >= 3, (
        f"Profile enum referenced too few values: {found}/5; expected >= 3"
    )
    assert "Principle 2" in text, "Principle 2 (Profile-Aware) header missing"
    assert "profile" in text.lower(), "profile concept missing"


# --- Test 11: Forbidden tokens grep CLEAN (plugin-agnostik + frontmatter drift) ---
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
