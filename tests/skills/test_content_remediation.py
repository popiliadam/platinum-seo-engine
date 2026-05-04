"""Tests for content-remediation skill (Phase 11 Wave 2 W-F4).

Coverage: frontmatter validation, natural_language sentinel (schema string
form, comma-split phrase quality), R-85 multi-signal threshold, R-90 manual
approve gate (autonomy MEDIUM), R-91 301/410 decision tree (4 senaryo), 3
sheet writer (F-10/F-11/F-12 skill-level enforcement), events.jsonl
compliance (F-9 event_kind=work + F-14 event_type enum), R-118 humanize
scope-out (revise-content domain leakage detect), profile-aware approve
gate (Principle 2 enum 5-value), forbidden tokens grep, plugin agnostik.

Schema authority note:
- skill-frontmatter.schema.json `triggers.natural_language` is a STRING
  type (comma-separated phrases per skill-frontmatter spec), NOT an
  array. Tests therefore parse the string and validate per-phrase
  sentinel quality (each comma-delimited phrase >= 30 chars), preserving
  the brief's intent under schema-first authority.
- master.xlsx[redirect_404 + robots_txt + completed_work] schema-level
  allowed_writers=null → skill-level enforcement intact (transaction.
  update OK, governance Phase 14+ defer). WRITE contract is positively
  asserted in routing body; tests verify presence of writer references.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "production" / "content-remediation" / "SKILL.md"
SKILL_FRONTMATTER_SCHEMA = REPO_ROOT / "schemas" / "skill-frontmatter.schema.json"


def _read_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _parse_frontmatter(text: str | None = None) -> dict:
    text = text if text is not None else _read_skill_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter delimiter pair in {SKILL_PATH}")
    return yaml.safe_load(match.group(1))


# --- Test 1: Frontmatter required-field set + natural_language phrase quality ---
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
    assert fm["name"] == "content-remediation"
    assert fm["category"] == "production"
    assert fm["status"] in {"active", "deprecated", "wip"}

    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str), (
        f"natural_language must be string per skill-frontmatter schema, "
        f"got {type(nl).__name__}"
    )
    assert len(nl) >= 30, (
        f"natural_language total length must be >= 30 chars, got {len(nl)}"
    )
    # Per-phrase sentinel quality (lesson 8 sentinel: each phrase >= 30 chars)
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


# --- Test 2: R-85 multi-signal threshold test ---
def test_r85_multi_signal_threshold():
    text = _read_skill_text()
    assert "R-85" in text, "R-85 rule reference missing"
    assert "multi-signal" in text or "multi_signal" in text, (
        "multi-signal phrase missing"
    )
    # 5 signal references (clicks, position, impressions, delta_pct, trend)
    lower = text.lower()
    assert "clicks_delta" in text or "clicks delta" in lower
    assert "position" in lower, "position signal missing"
    assert "impressions" in lower, "impressions signal missing"
    assert "delta_pct" in text or "delta pct" in lower, "delta_pct signal missing"
    assert "trend" in lower, "trend signal missing"
    # Threshold: minimum 3/5 satisfied
    assert "3/5" in text or "minimum 3" in lower, "3/5 threshold missing"


# --- Test 3: R-90 manual approve gate test (autonomy MEDIUM) ---
def test_r90_manual_approve_gate():
    fm = _parse_frontmatter()
    text = _read_skill_text()
    assert "R-90" in text, "R-90 rule reference missing"
    assert fm["autonomy"]["confidence"] == "MEDIUM", (
        "autonomy.confidence must be MEDIUM (R-90 manual approve gate)"
    )
    assert fm["autonomy"]["requires_approval"] is True, (
        "autonomy.requires_approval must be True"
    )
    assert fm["autonomy"]["safe_auto_execute"] is False, (
        "autonomy.safe_auto_execute must be False"
    )
    assert "DURUR #2" in text, "DURUR #2 (R-90 manuel approve YOK) missing"


# --- Test 4: R-91 301/410 decision tree (4 senaryo) ---
def test_r91_decision_tree_4_scenarios():
    text = _read_skill_text()
    assert "R-91" in text, "R-91 rule reference missing"
    assert "decision tree" in text.lower(), "decision tree phrase missing"
    assert "301" in text, "301 redirect missing"
    assert "410" in text, "410 Gone missing"
    # 4 senaryo keywords
    lower = text.lower()
    assert "senaryo 1" in lower, "Senaryo 1 (prune + traffic) missing"
    assert "senaryo 2" in lower, "Senaryo 2 (prune + no traffic) missing"
    assert "senaryo 3" in lower, "Senaryo 3 (redirect) missing"
    assert "senaryo 4" in lower, "Senaryo 4 (delete) missing"
    # Action enum 3-value
    assert "prune" in lower, "prune action missing"
    assert "redirect" in lower, "redirect action missing"
    assert "delete" in lower, "delete action missing"
    # DURUR #3 (target_url=null reject)
    assert "DURUR #3" in text, "DURUR #3 (target_url null) missing"


# --- Test 5: redirect_404 writer test (F-10 schema column compliance) ---
def test_redirect_404_writer():
    text = _read_skill_text()
    assert "redirect_404" in text, "redirect_404 sheet reference missing"
    assert "F-10" in text, "F-10 schema authority reference missing"
    # F-10 5 col reference
    assert "target_url" in text, "target_url column missing"
    assert "transaction.update" in text, (
        "transaction.update writer call-site missing for redirect_404"
    )
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "redirect_404" in outputs_str, (
        f"redirect_404 not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 6: robots_txt writer test (F-11) ---
def test_robots_txt_writer():
    text = _read_skill_text()
    assert "robots_txt" in text, "robots_txt sheet reference missing"
    assert "F-11" in text, "F-11 schema authority reference missing"
    # F-11 5 col reference
    lower = text.lower()
    assert "level" in lower or "severity" in lower, "level/severity column missing"
    assert "disallow" in lower, "disallow resolution missing"
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "robots_txt" in outputs_str, (
        f"robots_txt not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 7: completed_work entry test (F-12 6 col compliance) ---
def test_completed_work_entry():
    text = _read_skill_text()
    assert "completed_work" in text, "completed_work sheet reference missing"
    assert "F-12" in text, "F-12 schema authority reference missing"
    # F-12 6 col reference (id, task_or_content, url, date, category, note)
    assert "task_or_content" in text, "task_or_content column missing"
    assert "category" in text.lower(), "category column missing"
    assert "note" in text.lower(), "note column missing"
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "completed_work" in outputs_str, (
        f"completed_work not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 8: events.jsonl event_kind=work + event_type enum (F-9 + F-14) ---
def test_events_jsonl_compliance():
    text = _read_skill_text()
    assert "event_kind" in text, "event_kind field missing"
    assert "work" in text, "event_kind=work value missing (F-9 ADR-020 enum)"
    # F-14 event_type enum 10-value: prune/delete → content_remove; redirect → redirect_deployed
    assert "content_remove" in text, "event_type=content_remove missing (F-14 prune/delete)"
    assert "redirect_deployed" in text, (
        "event_type=redirect_deployed missing (F-14 redirect)"
    )
    assert "project_id" in text, "project_id field missing (F-14 required)"
    assert "schema_version" in text, "schema_version field missing (F-14 required)"
    assert "F-9" in text, "F-9 schema authority reference missing"
    assert "F-14" in text, "F-14 schema authority reference missing"
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "events.jsonl" in outputs_str, (
        f"events.jsonl not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 9: R-118 humanize scope-out test (revise-content domain cross-check) ---
def test_r118_humanize_scope_out():
    text = _read_skill_text()
    assert "R-118" in text, "R-118 rule reference missing"
    assert "humanize" in text.lower(), "humanize concept missing"
    # Scope-out: revise-content domain leakage detect
    assert "revise-content" in text.lower(), (
        "revise-content domain reference missing (scope-out detection)"
    )
    assert "scope-out" in text.lower() or "RETIRE scope" in text, (
        "scope-out / RETIRE scope sentinel missing"
    )


# --- Test 10: Profile-aware approve gate (Principle 2 enum 5-value) ---
def test_profile_aware_principle_2():
    text = _read_skill_text()
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    found = sum(1 for p in profile_enum if p in text)
    assert found >= 4, (
        f"Profile enum coverage too low: {found}/5; expected >= 4"
    )
    assert "Principle 2" in text or "profile-aware" in text.lower(), (
        "Principle 2 / profile-aware header missing"
    )
    # ymyl R-90 daha sıkı (irreversible 410 = lost authority)
    lower = text.lower()
    assert "ymyl" in lower, "ymyl profile mention missing"
    assert "daha sıkı" in lower or "stricter" in lower or "ek belge" in lower, (
        "ymyl profile stricter gate language missing"
    )


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


# --- Test 12: Plugin agnostik (no slug hardcode in skill content) ---
def test_plugin_agnostic():
    text = _read_skill_text()
    # Distinct check from forbidden_tokens — narrower set, semantic plugin-slug detection
    slug_tokens = [
        "dentnotion",
        "vento",
        "eykom",
        "bigcattr",
        "calitte",
        "lastiksa",
        "noraninsaat",
        "adstark",
    ]
    for slug in slug_tokens:
        assert slug not in text, f"Plugin agnostik violation (slug hardcode): {slug!r}"
    # Positive sentinel: runtime input placeholders used
    assert "{input.project_slug}" in text or "{slug}" in text, (
        "runtime input placeholder missing — plugin-agnostik resolution unclear"
    )
