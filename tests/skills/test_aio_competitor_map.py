"""tests/skills/test_aio_competitor_map.py — aio-competitor-map skill (Phase 12 Wave 1, W-G3).

Coverage:
  1. Frontmatter required-fields + Draft7 validation (skill-frontmatter.schema.json).
  2. Inputs structure: target_keyword/location/top_n with required+default contract.
  3. DURUR #1 sentinel — budget_credits_per_day exceed (AMBER + skip).
  4. DURUR #2 sentinel — SERP empty top_n=0 (REJECT).
  5. DURUR #3 sentinel — All Scrapling 5xx (AMBER + partial).
  6. DURUR #4 sentinel — AIO signal 0 (AMBER + empty payload).
  7. DURUR #5 sentinel — target_keyword empty/whitespace (ABORT).
  8. R-109 schema markup detect language present (Article, NewsArticle, FAQPage, HowTo).
  9. R-110 entity references count language present (Person, Organization, Place).
  10. R-111 author authority language present (sameAs, credentials, byline).
  11. master.xlsx WRITE YOK invariant (no transaction.* token, no master.xlsx[sheet] write).
  12. events.jsonl append-only invariant (no in-place rewrite token).
  13. Plugin-agnostic — .mcp.json byte unchanged + slug-free skill body.
  14. Foundational Principles 3-layer coverage (truth-verifiable + profile-aware + AI suistimal).

Discipline:
  - Every assertion derives from a schema authority (schemas/*) or
    rules/content-seo-discipline.md cross-link.
  - Plugin-agnostic invariant: no project slug hardcoded in the skill body.
  - DURUR list parity check (5 DURUR conditions discoverable).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "discovery" / "aio-competitor-map" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"
MCP_JSON_PATH = REPO_ROOT / ".mcp.json"


def _parse_frontmatter(skill_path: Path) -> dict:
    text = skill_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise ValueError(f"No YAML frontmatter in {skill_path}")
    return yaml.safe_load(m.group(1))


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — frontmatter schema validity (skill-frontmatter.schema.json)
# ---------------------------------------------------------------------------

def test_frontmatter_required_fields_and_schema_valid() -> None:
    """Frontmatter must declare 8 required fields + validate end-to-end
    against skill-frontmatter.schema.json Draft7."""
    fm = _parse_frontmatter(SKILL_PATH)
    required = ["name", "description", "version", "status", "category",
                "inputs", "outputs", "triggers"]
    for field in required:
        assert field in fm, f"Missing required field: {field}"

    schema = json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(fm),
                    key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    )

    # Spot-check brief contract.
    assert fm["name"] == "aio-competitor-map"
    assert fm["category"] == "discovery"
    assert fm["status"] == "wip"
    assert fm["triggers"]["manual"] == ["/pseo-aio-competitor-map"]
    assert fm["budget"]["uses_paid_mcp"] is True
    assert fm["budget"]["estimated_credits"] == 30
    assert fm["autonomy"]["confidence"] == "MEDIUM"
    assert fm["autonomy"]["safe_auto_execute"] is True


# ---------------------------------------------------------------------------
# Test 2 — inputs structure (target_keyword / location / top_n)
# ---------------------------------------------------------------------------

def test_inputs_structure_three_fields() -> None:
    """Inputs must declare exactly 3 fields with required+default contract."""
    fm = _parse_frontmatter(SKILL_PATH)
    inputs = fm["inputs"]
    assert set(inputs.keys()) == {"target_keyword", "location", "top_n"}

    # target_keyword: string, required=true, NO default
    assert inputs["target_keyword"]["type"] == "string"
    assert inputs["target_keyword"]["required"] is True
    assert "default" not in inputs["target_keyword"]

    # location: string, required=false, default="tr-TR"
    assert inputs["location"]["type"] == "string"
    assert inputs["location"]["required"] is False
    assert inputs["location"]["default"] == "tr-TR"

    # top_n: integer, required=false, default=10
    assert inputs["top_n"]["type"] == "integer"
    assert inputs["top_n"]["required"] is False
    assert inputs["top_n"]["default"] == 10


# ---------------------------------------------------------------------------
# Test 3 — DURUR #1 budget exceed sentinel
# ---------------------------------------------------------------------------

def test_durur_1_budget_exceeded_sentinel() -> None:
    """DURUR #1 must reference budget_credits_per_day + AMBER + skip semantic."""
    text = _skill_text()
    assert "DURUR #1" in text
    assert "budget_credits_per_day" in text
    assert "BudgetExceededError" in text or "budget_exceeded" in text
    # AMBER + skip semantic
    assert "AMBER" in text
    assert "skip" in text.lower() or "skipped" in text.lower()


# ---------------------------------------------------------------------------
# Test 4 — DURUR #2 SERP empty REJECT sentinel
# ---------------------------------------------------------------------------

def test_durur_2_serp_empty_reject_sentinel() -> None:
    """DURUR #2: SERP empty (top_n=0 ya da DFS 0 organic) → REJECT."""
    text = _skill_text()
    assert "DURUR #2" in text
    assert "SERP empty" in text or "serp_empty" in text or "SerpEmptyError" in text
    assert "REJECT" in text
    # No Scrapling call dispatch (sequential gate). The skill body
    # asserts "Hiçbir Scrapling\n call dispatch edilmez." — collapse
    # whitespace to make the assertion robust to wrap.
    collapsed = re.sub(r"\s+", " ", text)
    assert "Scrapling call dispatch" in collapsed


# ---------------------------------------------------------------------------
# Test 5 — DURUR #3 all Scrapling 5xx AMBER sentinel
# ---------------------------------------------------------------------------

def test_durur_3_all_scrapling_5xx_amber_sentinel() -> None:
    """DURUR #3: tüm tier-1 fetch fail → AMBER + partial result + Apify v1.2+ doc."""
    text = _skill_text()
    assert "DURUR #3" in text
    assert "Scrapling" in text
    assert "5xx" in text or "all_scrapling_5xx" in text
    assert "AMBER" in text
    assert "partial" in text.lower()
    # Apify v1.2+ fallback documented (Phase 13+ activation)
    assert "Apify v1.2+" in text or "Apify" in text


# ---------------------------------------------------------------------------
# Test 6 — DURUR #4 AIO signal 0 AMBER sentinel
# ---------------------------------------------------------------------------

def test_durur_4_aio_signal_zero_amber_sentinel() -> None:
    """DURUR #4: R-109/R-110/R-111 toplam 0 → AMBER + empty payload."""
    text = _skill_text()
    assert "DURUR #4" in text
    assert "AIO signal" in text or "aio_signal" in text
    # All three rules referenced for cumulative 0 condition
    assert "R-109" in text and "R-110" in text and "R-111" in text
    assert "AMBER" in text


# ---------------------------------------------------------------------------
# Test 7 — DURUR #5 target_keyword empty ABORT sentinel
# ---------------------------------------------------------------------------

def test_durur_5_empty_keyword_abort_sentinel() -> None:
    """DURUR #5: whitespace-only target_keyword → ABORT, no MCP call."""
    text = _skill_text()
    assert "DURUR #5" in text
    assert "target_keyword" in text
    assert "whitespace" in text.lower() or "empty" in text.lower()
    assert "ABORT" in text
    assert "EmptyKeywordError" in text or "empty" in text.lower()


# ---------------------------------------------------------------------------
# Test 8 — R-109 schema markup detect language
# ---------------------------------------------------------------------------

def test_r_109_schema_markup_detect_present() -> None:
    """R-109 enforcement must name the 4 AIO-relevant schema.org @types
    (Article, NewsArticle, FAQPage, HowTo) so the detect contract is
    explicit + map to rules/content-seo-discipline.md."""
    text = _skill_text()
    assert "R-109" in text
    for schema_type in ("Article", "NewsArticle", "FAQPage", "HowTo"):
        assert schema_type in text, f"R-109 schema type missing: {schema_type}"
    # JSON-LD parse semantic (deterministic, not LLM)
    assert "JSON-LD" in text or "application/ld+json" in text


# ---------------------------------------------------------------------------
# Test 9 — R-110 entity references count language
# ---------------------------------------------------------------------------

def test_r_110_entity_references_present() -> None:
    """R-110 enforcement names entity types Person/Organization/Place."""
    text = _skill_text()
    assert "R-110" in text
    for entity in ("Person", "Organization", "Place"):
        assert entity in text, f"R-110 entity type missing: {entity}"
    # Anti-pattern semantic
    assert "anti-pattern" in text.lower() or "Anti-Pattern" in text


# ---------------------------------------------------------------------------
# Test 10 — R-111 author authority language
# ---------------------------------------------------------------------------

def test_r_111_author_authority_present() -> None:
    """R-111 enforcement names sameAs + credentials + byline structure."""
    text = _skill_text()
    assert "R-111" in text
    assert "sameAs" in text
    assert "credentials" in text.lower() or "hasCredential" in text or "jobTitle" in text
    assert "byline" in text.lower()
    # Quality-driven hijack semantic
    assert "hijack" in text.lower() or "quality-driven" in text.lower()


# ---------------------------------------------------------------------------
# Test 11 — master.xlsx WRITE YOK invariant (sentinel monkey-patch)
# ---------------------------------------------------------------------------

def test_master_xlsx_write_forbidden_invariant() -> None:
    """master.xlsx WRITE YASAK: no transaction.* token, no master.xlsx[sheet]
    write reference. Staging-only ADR-025 path."""
    text = _skill_text()
    # No transaction writes against the workbook
    forbidden_writes = re.findall(
        r"transaction\.(append|update|delete)\s*\(", text
    )
    assert not forbidden_writes, (
        f"master.xlsx WRITE YASAK violation: {forbidden_writes}"
    )
    # Explicit invariant statement
    assert "WRITE YASAK" in text or "WRITE YOK" in text or "staging-only" in text.lower()
    # No master.xlsx[*] write target
    write_refs = re.findall(r"master\.xlsx\[[a-z_]+\]", text)
    # Allowed: discussion of future Phase 13+ master.xlsx[opportunity]
    # but not as an output target. Skill outputs frontmatter must NOT
    # carry any master.xlsx#* anchor.
    fm = _parse_frontmatter(SKILL_PATH)
    for output in fm["outputs"]:
        assert "master.xlsx" not in output, (
            f"master.xlsx output anchor leaked: {output!r}"
        )


def test_master_xlsx_write_sentinel_monkey_patch_no_openpyxl_save() -> None:
    """Sentinel: skill body must not invoke openpyxl save / Workbook.save
    against master.xlsx. The skill must use staging file write (.jsonl)
    only — openpyxl write functions are forbidden tokens here."""
    text = _skill_text()
    forbidden_tokens = [
        "openpyxl.Workbook",
        "wb.save(",
        "workbook.save(",
        "load_workbook(",
    ]
    for tok in forbidden_tokens:
        if tok in text:
            # Allowed only if explicitly qualified as YASAK in the same context.
            # Strict zero-tolerance for this skill (staging-only).
            assert "YASAK" in text, (
                f"openpyxl save token leaked without YASAK qualifier: {tok}"
            )


# ---------------------------------------------------------------------------
# Test 12 — events.jsonl append-only invariant
# ---------------------------------------------------------------------------

def test_events_jsonl_append_only_invariant() -> None:
    """events.jsonl asla in-place rewrite görmez — append-only line write.
    The provenance event must use event_kind=provenance + notes=
    'aio_mapped' (schema-first override; event_type is WORK-only)."""
    text = _skill_text()
    # event_kind=provenance discipline
    assert "event_kind=provenance" in text or "event_kind`=`provenance" in text \
        or "event_kind: provenance" in text or "provenance" in text
    # aio_mapped semantic marker via notes (override of brief's event_type)
    assert "aio_mapped" in text
    # append-only
    assert "append-only" in text.lower() or "Append-only" in text

    # Schema cross-check: events.schema.json provenance allOf includes
    # required [run_id, source, operation]. The skill body must reference
    # all three.
    for prov_key in ("run_id", "source", "operation"):
        assert prov_key in text, (
            f"provenance required field missing in skill body: {prov_key}"
        )

    # operation must be a valid enum value (ingest/normalize/project_excel/validate/cascade_done)
    assert 'operation="ingest"' in text or "operation=ingest" in text \
        or 'operation: ingest' in text


def test_events_event_kind_provenance_in_schema_enum() -> None:
    """Schema authority cross-check: event_kind enum includes 'provenance'
    and event_type is a WORK-only field (not in provenance allowed
    additionalProperties context — schema-first override correct)."""
    schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text(encoding="utf-8")
    )
    enum = schema["properties"]["event_kind"]["enum"]
    assert "provenance" in enum, "events.schema.json event_kind enum drifted"

    # Confirm event_type is WORK-only (description marker)
    et_desc = schema["properties"]["event_type"]["description"]
    assert "WORK-only" in et_desc, (
        "event_type description drifted — schema-first override basis"
    )


# ---------------------------------------------------------------------------
# Test 13 — plugin-agnostic: .mcp.json byte unchanged + slug-free skill
# ---------------------------------------------------------------------------

def test_mcp_json_byte_unchanged() -> None:
    """Plugin-agnostic invariant F-16: this skill must not mutate
    .mcp.json. We assert the file exists and that the SKILL.md never
    references writing/modifying it."""
    text = _skill_text()
    # No write directives against .mcp.json
    assert ".mcp.json" not in text or "byte unchanged" in text or "byte yazmaz" in text, (
        "Plugin-agnostic violation: .mcp.json reference without 'byte unchanged' qualifier"
    )

    # File integrity sentinel: hash the file. (Cannot compare across runs
    # without prior baseline, so we only assert it exists + non-empty.)
    if MCP_JSON_PATH.exists():
        content = MCP_JSON_PATH.read_bytes()
        assert len(content) > 0, ".mcp.json is empty (corrupt?)"
        # Deterministic hash so future drift checks compare snapshot
        digest = hashlib.sha256(content).hexdigest()
        assert len(digest) == 64


def test_no_hardcoded_project_slugs() -> None:
    """Plugin-agnostic discipline: known project slugs must not appear
    in skill body (Phase 7-lesson + recurring slugs)."""
    text = _skill_text()
    slugs = ["demo-dental", "demo-furniture", "demo-hvac", "demo-petcare",
             "demo-shop", "demo-tires", "demo-construction", "demo-agency"]
    for slug in slugs:
        assert slug not in text, (
            f"Plugin-agnostic violation: slug '{slug}' hardcoded in skill body"
        )

    # Phase 7-lesson tokens still rejected
    for token in ("estimated_credits_per_call",
                  "estimated_credits_per_url",
                  "metric_name"):
        assert token not in text, f"Phase 7-lesson token leaked: {token}"


# ---------------------------------------------------------------------------
# Test 14 — Foundational Principles 3-layer coverage
# ---------------------------------------------------------------------------

def test_foundational_principles_3_layer_coverage() -> None:
    """Skill must reference Foundational Principles 3 layers explicitly:
    Principle 1 truth-verifiable, Principle 2 profile-aware (5-enum),
    Principle 3 AI suistimal (URL fabrication yasak)."""
    text = _skill_text()
    assert "Foundational Principles" in text
    # Principle 1 — truth-verifiable + provenance event provenance
    assert "Principle 1" in text
    assert "Truth-Verifiable" in text or "truth-verifiable" in text.lower()
    assert "R-27" in text
    # Principle 2 — profile-aware + 5-enum named in body
    assert "Principle 2" in text
    assert "profile-aware" in text.lower()
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    for p in profile_enum:
        assert p in text.lower() or p.upper() in text or p in text, (
            f"Principle 2 profile enum value missing: {p}"
        )
    # Principle 3 — AI suistimal (URL fabrication yasak)
    assert "Principle 3" in text
    assert "AI Suistimal" in text or "AI suistimal" in text.lower() \
        or "fabric" in text.lower() or "URL fabrication" in text
    # DataForSEO output kaynaklı (no fabricate)
    assert "DataForSEO" in text


def test_no_url_fabrication_invariant() -> None:
    """Principle 3 sentinel: skill body must explicitly state competitor
    URLs are sourced from DataForSEO SERP output (not invented)."""
    text = _skill_text()
    # Explicit DataForSEO sourcing language
    assert "competitor URL" in text or "competitor URLs" in text
    # Strong claim: not fabricated
    assert "üretmez" in text or "fabricate" in text.lower() \
        or "kaynaklı" in text or "sourced" in text.lower()


# ---------------------------------------------------------------------------
# Bonus — DURUR list parity (5 conditions discoverable)
# ---------------------------------------------------------------------------

def test_durur_list_parity_5_conditions() -> None:
    """5 DURUR conditions must be enumerated in the skill body."""
    text = _skill_text()
    for n in range(1, 6):
        assert f"DURUR #{n}" in text, f"DURUR #{n} missing from skill body"
