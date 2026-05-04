"""Tests for generate-images skill (Phase 11 Wave 2 W-F5).

Coverage: frontmatter validation, plugin agnostik MCP boundary
(F-16 `.mcp.json` Higgsfield server entry YASAK), R-71..R-76 sentinel
enforcement (8K ultra realistic + nano-banana default + 1200x675 hero
size + R-74 manual upload Section B + R-75 LCP `<picture>` + R-76
format cascade WebP+AVIF+JPG), profile-aware image_style switch (F-13
5-enum), events.jsonl F-9 + F-14 compliance, Higgsfield runtime
fallback (DURUR #5 default_hero_url), forbidden tokens grep,
READ-ONLY contract, WCAG accessibility.

Schema authority note:
- skill-frontmatter.schema.json `triggers.natural_language` is a STRING
  type (comma-separated phrases per skill-frontmatter spec). Tests
  parse the string and validate per-phrase sentinel quality (each
  comma-delimited phrase >= 30 chars), preserving Wave 1 W-F1+W-F2
  precedent reuse.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "production" / "generate-images" / "SKILL.md"
MCP_JSON_PATH = REPO_ROOT / ".mcp.json"


def _read_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _parse_frontmatter(text: str | None = None) -> dict:
    text = text if text is not None else _read_skill_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter delimiter pair in {SKILL_PATH}")
    return yaml.safe_load(match.group(1))


# --- Test 1: Frontmatter required-field set + Higgsfield mcp_tools.required ---
def test_frontmatter_required_fields_and_higgsfield_required():
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
    assert fm["name"] == "generate-images"
    assert fm["category"] == "production"
    assert fm["status"] in {"active", "deprecated", "wip"}
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str), (
        f"natural_language must be string per skill-frontmatter schema, "
        f"got {type(nl).__name__}"
    )
    assert len(nl) >= 30, f"natural_language total <30 char: {len(nl)}"
    # Higgsfield mcp_tools.required reference (user-level VS Code MCP advisory)
    required_tools = fm["mcp_tools"]["required"]
    assert "mcp__higgsfield__generate_image" in required_tools, (
        f"mcp__higgsfield__generate_image missing from required: {required_tools}"
    )


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


# --- Test 3: R-71 8K ultra realistic prompt enrichment ---
def test_r71_8k_ultra_realistic():
    text = _read_skill_text()
    assert "R-71" in text, "R-71 rule reference missing"
    assert "8K" in text, "8K phrase missing (R-71 prompt enrichment)"
    assert "ultra realistic" in text.lower(), "ultra realistic phrase missing"
    assert "no anime" in text.lower() or "no low-res" in text.lower(), (
        "AI suistimal preempt directive missing (anime/low-res)"
    )


# --- Test 4: R-72 image_model default nano-banana + override ---
def test_r72_image_model_default_nano_banana():
    text = _read_skill_text()
    assert "R-72" in text, "R-72 rule reference missing"
    assert "nano-banana" in text, "nano-banana default model missing"
    assert "image_model" in text, "image_model field reference missing"
    # plugin agnostik override discipline (serbest string)
    assert (
        "override edilebilir" in text.lower()
        or "serbest string" in text.lower()
        or "plugin agnostik" in text.lower()
    ), "R-72 plugin agnostik override semantic missing"


# --- Test 5: R-73 1200x675 hero only size enforce ---
def test_r73_1200x675_hero_size():
    text = _read_skill_text()
    assert "R-73" in text, "R-73 rule reference missing"
    assert "1200" in text, "1200 width missing"
    assert "675" in text, "675 height missing"
    assert "hero" in text.lower(), "hero kind reference missing"
    assert "DURUR #4" in text, "DURUR #4 (1200x675 size violation) gate missing"


# --- Test 6: R-74 manuel upload workflow (Section B append) ---
def test_r74_manual_upload_workflow():
    text = _read_skill_text()
    assert "R-74" in text, "R-74 rule reference missing"
    assert "upload-instructions" in text, "upload-instructions doc reference missing"
    assert "Section B" in text, "Section B (multi-skill collaborative output) missing"
    assert "Manual Upload" in text or "manual upload" in text.lower(), (
        "manual upload workflow phrase missing"
    )


# --- Test 7: R-75 LCP optimization (<picture> tag + fetchpriority + loading) ---
def test_r75_lcp_optimization():
    text = _read_skill_text()
    assert "R-75" in text, "R-75 rule reference missing"
    assert "<picture>" in text, "<picture> tag reference missing"
    assert "fetchpriority" in text.lower(), "fetchpriority hint missing"
    assert 'loading="eager"' in text or "loading=\"eager\"" in text, (
        'loading="eager" directive missing (LCP above-fold)'
    )


# --- Test 8: R-76 format cascade (webp + avif + jpg) ---
def test_r76_image_format_cascade():
    text = _read_skill_text()
    assert "R-76" in text, "R-76 rule reference missing"
    assert "webp" in text.lower(), "webp format missing"
    assert "avif" in text.lower(), "avif format missing"
    assert "jpg" in text.lower() or "jpeg" in text.lower(), (
        "jpg/jpeg fallback format missing"
    )
    # 3 format cascade outputs in frontmatter
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    for ext in [".webp", ".avif", ".jpg"]:
        assert ext in outputs_str, f"Format extension {ext} missing in outputs"


# --- Test 9: F-13 image_style profile-aware switch (5-enum) ---
def test_f13_image_style_profile_aware():
    text = _read_skill_text()
    image_styles = [
        "clean-illustration",
        "product-photo",
        "diagram-screenshot",
        "location-photo",
        "esnek",
    ]
    for style in image_styles:
        assert style in text, f"image_style enum value missing: {style}"
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    found = sum(1 for p in profile_enum if p in text)
    assert found >= 4, f"Profile enum coverage too low: {found}/5"
    assert "Principle 2" in text, "Principle 2 (Profile-Aware) header missing"


# --- Test 10: events.jsonl F-9 (event_kind=work) + F-14 (event_type, project_id) ---
def test_events_jsonl_compliance():
    text = _read_skill_text()
    # F-9 event_kind=work (ADR-020 production output enum)
    assert "event_kind" in text, "event_kind field missing"
    assert "work" in text, "work enum value missing (F-9 ADR-020)"
    # F-14 event_type 10-enum
    assert "event_type" in text, "event_type field missing"
    assert "content_new" in text, "content_new enum value missing (F-14 success)"
    assert "manual" in text, "manual enum value missing (F-14 DURUR #5 fallback)"
    # F-14 5-required-field
    assert "schema_version" in text, "schema_version field missing (F-14)"
    assert "project_id" in text, "project_id field missing (F-14)"
    fm = _parse_frontmatter(text)
    outputs_str = " ".join(fm.get("outputs", []))
    assert "events.jsonl" in outputs_str, (
        f"events.jsonl not declared in outputs: {fm.get('outputs')}"
    )


# --- Test 11: 🔴 KRİTİK — Plugin agnostik MCP boundary (F-16 Süleyman Seçenek D) ---
def test_plugin_agnostic_mcp_boundary_higgsfield_not_in_mcp_json():
    """F-16 + Süleyman Seçenek D: Higgsfield MCP user-level VS Code
    config; plugin agnostik korunur. Worker DOES NOT write Higgsfield
    server entry into `.mcp.json`. Beklenen 3 server intact:
    `gsc`, `dataforseo`, `ScraplingServer`."""
    mcp = json.loads(MCP_JSON_PATH.read_text(encoding="utf-8"))
    servers = list(mcp.get("mcpServers", {}).keys())
    assert "higgsfield" not in [s.lower() for s in servers], (
        f"Plugin agnostik violation (F-16): Higgsfield `.mcp.json`'da "
        f"bulunmamalı (Süleyman Seçenek D). Mevcut servers: {servers}"
    )
    expected = {"gsc", "dataforseo", "ScraplingServer"}
    assert set(servers) == expected, (
        f"Beklenmeyen `.mcp.json` mcpServers (F-16 boundary drift): {servers}"
    )


# --- Test 12: Higgsfield MCP runtime call documented + DURUR #5 fallback ---
def test_higgsfield_runtime_fallback():
    text = _read_skill_text()
    assert "DURUR #5" in text, "DURUR #5 (Higgsfield unavailable) gate missing"
    assert "default_hero_url" in text, "default_hero_url fallback missing"
    assert "AMBER" in text, "AMBER warning level missing for DURUR #5"
    assert "tool registry" in text.lower() or "runtime" in text.lower(), (
        "Claude tool registry / runtime call documentation missing"
    )
    # F-16 plugin agnostik boundary explicit in body
    assert "F-16" in text, "F-16 schema authority reference missing"
    assert ".mcp.json" in text, ".mcp.json boundary discussion missing"


# --- Test 13: Forbidden tokens grep CLEAN (plugin-agnostik + drift) ---
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
    # The plugin-agnostic discipline section legitimately ENUMERATES
    # forbidden slugs as documentation. Strip the YASAK enumeration
    # block before scanning so the test catches real leaks elsewhere.
    discipline_marker = "FORBIDDEN tokens"
    if discipline_marker in text:
        # Remove the line that documents the FORBIDDEN list
        scrub_pattern = re.compile(
            r"\(`dentnotion`.*?are FORBIDDEN tokens.*?\)\.",
            re.DOTALL,
        )
        text = scrub_pattern.sub("(FORBIDDEN_TOKEN_LIST_DOCUMENTED)", text, count=1)
    for token in forbidden:
        assert token not in text, f"Forbidden token leaked into SKILL.md: {token!r}"


# --- Test 14: READ-ONLY contract (F-1 — no transaction.* call sites) ---
def test_read_only_contract():
    """Detect actual transaction.* call sites (write operations), not
    documentation prose mentioning the YASAK ban itself."""
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
    assert "READ-ONLY" in text, "READ-ONLY contract assertion missing in body"


# --- Test 15: WCAG 2.1 AA accessibility (alt text + width/height + focus-visible) ---
def test_wcag_accessibility():
    text = _read_skill_text()
    assert "WCAG" in text, "WCAG accessibility reference missing"
    assert "alt_text" in text, "alt_text reference missing (R-77 truth-verifiable)"
    assert "width" in text and "height" in text, (
        "explicit width/height (CLS preempt R-62) reference missing"
    )
    assert "focus-visible" in text, "focus-visible CSS hint reference missing"


# --- Test 16: consumes 1 master.xlsx sheet + project-config 3 nested + 6 rules + 1 template ---
def test_consumes_contract():
    fm = _parse_frontmatter()
    consumes = fm.get("consumes", [])
    # 1 master.xlsx sheet (new_content_plan READ-ONLY)
    sheets_found = sum(1 for c in consumes if "new_content_plan" in c)
    assert sheets_found >= 1, f"new_content_plan sheet not in consumes: {consumes}"
    # project-config 3 nested keys
    pc_keys = ["image_model", "image_style", "default_hero_url"]
    for key in pc_keys:
        assert any(key in c for c in consumes), (
            f"project-config nested key {key!r} missing in consumes"
        )
    # 6 rules (rules:rules/...)
    rule_count = sum(1 for c in consumes if c.startswith("rules:"))
    assert rule_count == 6, f"Expected 6 rules in consumes, got {rule_count}: {consumes}"
    # 1 template
    template_count = sum(1 for c in consumes if c.startswith("templates:"))
    assert template_count == 1, (
        f"Expected 1 template in consumes, got {template_count}"
    )
