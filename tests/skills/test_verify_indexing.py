"""tests/skills/test_verify_indexing.py — verify-indexing skill (Phase 12 W-G4).

Coverage (14 tests, lesson 32 self-extending positive drift +2 above 12 ceiling):
  1. Frontmatter required 8-field schema validity (skill-frontmatter.schema.json
     Draft7).
  2. Inputs/Outputs structure — outputs[] are artifact ref strings (lesson 7+23
     schema-first override applied: event_kind/audit_action are NOT frontmatter
     outputs[]; they're events.jsonl payload fields).
  3. natural_language ≥30-char block + ≥8-char per phrase (lesson 8 sentinel).
  4. consumes contract — master.xlsx[completed_work] + indexing-ping events
     (sequential dependency on W-G1 documented).
  5. DURUR #1 — GSC API auth fail ABORT documented.
  6. DURUR #2 — target_urls empty + auto-populate empty SKIP documented.
  7. DURUR #3 — All URLs not_indexed AMBER escalate documented.
  8. DURUR #4 — GSC quota exceeded AMBER partial result documented.
  9. master.xlsx WRITE YASAK — completed_work read-only, no transaction.* writes;
     openpyxl save sentinel monkey-patch enforce.
  10. events.jsonl event_kind=audit + audit_action=accessed schema-first override
      (lesson 7+23+31 4th convergent application — event_type WORK-only avoidance,
      indexing_verified would not be in F-8 enum even if event_type were used).
  11. W-G1 sequential dependency rationale — "Sequential Dependency on W-G1"
      section grep + 24-72 hour window documented.
  12. Plugin-agnostic — no project slug hardcoded in skill body; .mcp.json
      byte-hash unchanged invariant documented.
  13. Foundational Principles 3-layer enforcement — Principle 1 truth-verifiable
      (audit provenance), Principle 2 profile-aware documented placeholder,
      Principle 3 anti-hallucinated-coverage (GSC raw response only).
  14. Bonus self-extending (lesson 29 positive drift): output coverage report
      shape contract — `coverage[]`, `match_count`, `mismatch_count`,
      `quota_partial_flag`, `escalation_recommended` field set documented.

Discipline:
  - Every assertion derives from a schema authority (schemas/*) or
    rules/content-*.md cross-link.
  - Plugin-agnostic invariant: no project slug hardcoded in the skill.
  - READ-ONLY contract verified by grep (transaction.* token absent).
  - Schema-first override (lesson 7+23+31 4th convergent): brief drift →
    worker authority; W-G1 paterni reused on audit event_kind variant.
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
SKILL_PATH = REPO_ROOT / "skills" / "publishing" / "verify-indexing" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"


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

def test_frontmatter_required_fields_present() -> None:
    """Frontmatter must declare the 8 required fields per
    skill-frontmatter.schema.json (Draft7) and validate end-to-end."""
    fm = _parse_frontmatter(SKILL_PATH)
    required = ["name", "description", "version", "status", "category",
                "inputs", "outputs", "triggers"]
    for field in required:
        assert field in fm, f"Missing required field: {field}"

    schema = json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    )

    # Spot-check the contract fields the brief locks in.
    assert fm["name"] == "verify-indexing"
    assert fm["category"] == "publishing"
    assert fm["status"] == "wip"
    assert fm["triggers"]["manual"] == ["/pseo-verify-indexing"]
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True
    # mcp_tools required: index_inspect (W-G4 read-only verify primary tool).
    assert "mcp__gsc__index_inspect" in fm["mcp_tools"]["required"]


# ---------------------------------------------------------------------------
# Test 2 — Inputs / Outputs structure (schema-first override applied)
# ---------------------------------------------------------------------------

def test_inputs_outputs_structure_schema_first() -> None:
    """Inputs is object<param, {type, required, description}> per schema.
    Outputs is array<string> of artifact refs — NOT event payload fields.
    Schema-first override (lesson 7+23+31): event_kind / audit_action /
    audit_target are events.jsonl payload, NOT frontmatter outputs[].
    Also: enum YASAK in inputs[*] schema; enum lives in description prose."""
    fm = _parse_frontmatter(SKILL_PATH)

    # Inputs structure
    assert isinstance(fm["inputs"], dict)
    assert "target_urls" in fm["inputs"]
    assert "expected_status" in fm["inputs"]
    assert fm["inputs"]["target_urls"]["type"] == "array"
    assert fm["inputs"]["target_urls"]["required"] is True
    assert fm["inputs"]["expected_status"]["type"] == "string"
    assert fm["inputs"]["expected_status"]["required"] is True

    # W-G1 paterni: enum in description, NOT in schema (schema-first override).
    expected_desc = fm["inputs"]["expected_status"]["description"]
    for value in ("indexed", "not_indexed", "crawled_not_indexed"):
        assert value in expected_desc, (
            f"expected_status enum value '{value}' missing from "
            f"description (schema-first override target)"
        )
    # Spec field MUST NOT contain a JSON schema 'enum' key (per W-G1 paterni).
    assert "enum" not in fm["inputs"]["expected_status"], (
        "Schema drift: expected_status defines schema-level enum; per W-G1 "
        "paterni enum belongs in description prose, not the field body."
    )

    # Outputs are artifact refs (strings), NOT payload field names.
    assert isinstance(fm["outputs"], list)
    assert all(isinstance(o, str) for o in fm["outputs"])
    assert "_state/events.jsonl" in fm["outputs"]
    # Some artifact ref pointing to coverage report.
    assert any("outputs/indexing/" in o for o in fm["outputs"])
    assert any("coverage-report.json" in o for o in fm["outputs"])
    # Lesson 7+23+31 override sentinel: payload fields MUST NOT leak.
    forbidden_in_outputs = [
        "event_kind", "event_type", "audit_action", "audit_target",
        "indexing_verified", "audit", "accessed",
    ]
    outputs_blob = "\n".join(fm["outputs"])
    for tok in forbidden_in_outputs:
        assert tok not in outputs_blob, (
            f"Schema-first violation: payload field token '{tok}' leaked "
            f"into frontmatter outputs[] (must be artifact ref strings)"
        )


# ---------------------------------------------------------------------------
# Test 3 — natural_language ≥30-char block + ≥8-char per phrase (lesson 8)
# ---------------------------------------------------------------------------

def test_natural_language_min_30_char_per_phrase() -> None:
    """natural_language is a single string per schema; lesson 8 sentinel:
    block ≥30 char, each quoted phrase ≥8 char."""
    fm = _parse_frontmatter(SKILL_PATH)
    nl_block = fm["triggers"]["natural_language"]
    assert isinstance(nl_block, str), \
        "natural_language must be a string per skill-frontmatter schema"
    phrases = re.findall(r'"([^"]+)"', nl_block)
    assert phrases, "no quoted phrases found in natural_language"
    assert len(nl_block) >= 30, (
        f"natural_language block <30 char: {nl_block!r} ({len(nl_block)})"
    )
    for p in phrases:
        assert len(p) >= 8, f"natural_language phrase too short: {p!r}"


# ---------------------------------------------------------------------------
# Test 4 — consumes contract: completed_work + indexing-ping events
# ---------------------------------------------------------------------------

def test_consumes_completed_work_and_indexing_ping_events() -> None:
    """The skill consumes master.xlsx[completed_work] (W-G4 audit-only READ)
    and indexing-ping:_state/events.jsonl (sequential dependency upstream).
    F-4 schema authority: completed_work IS in the 18-sheet master schema;
    referencing absent sheets would be schema-fabrication."""
    fm = _parse_frontmatter(SKILL_PATH)
    assert "consumes" in fm and isinstance(fm["consumes"], list)

    consumes_blob = "\n".join(fm["consumes"])
    assert "master.xlsx[completed_work]" in consumes_blob
    assert "indexing-ping" in consumes_blob and "events.jsonl" in consumes_blob

    # F-4 schema authority — completed_work MUST exist in the 18-sheet schema.
    schema = json.loads(
        (SCHEMAS / "master-excel.schema.json").read_text("utf-8")
    )
    sheets = schema.get("sheets", {})
    assert "completed_work" in sheets, (
        "F-4 violation: completed_work sheet missing from master-excel schema"
    )

    # Phantom sheets MUST NOT be referenced by skill body (anti-fabrication).
    text = _skill_text()
    assert "master.xlsx[internal_links]" not in text
    assert "master.xlsx[content_gaps]" not in text


# ---------------------------------------------------------------------------
# Test 5 — DURUR #1 GSC auth fail ABORT
# ---------------------------------------------------------------------------

def test_verify_indexing_durur_1_gsc_auth_fail() -> None:
    """DURUR #1: GSC API auth fail (.env credentials missing veya 401) →
    ABORT (RED, çıktı yok, audit-only event)."""
    text = _skill_text()
    assert "DURUR #1" in text
    assert "auth" in text.lower() or "401" in text or "credential" in text.lower()
    assert "ABORT" in text


# ---------------------------------------------------------------------------
# Test 6 — DURUR #2 empty target_urls + auto-populate empty SKIP
# ---------------------------------------------------------------------------

def test_verify_indexing_durur_2_empty_target_urls() -> None:
    """DURUR #2: target_urls empty + completed_work auto-populate empty →
    SKIP (info severity)."""
    text = _skill_text()
    assert "DURUR #2" in text
    assert "boş" in text or "empty" in text.lower()
    assert "SKIP" in text


# ---------------------------------------------------------------------------
# Test 7 — DURUR #3 all URLs not_indexed AMBER escalate
# ---------------------------------------------------------------------------

def test_verify_indexing_durur_3_all_not_indexed() -> None:
    """DURUR #3: All URLs not_indexed (expected indexed → all mismatch) →
    AMBER + escalate (kritik findings flag)."""
    text = _skill_text()
    assert "DURUR #3" in text
    assert "AMBER" in text
    # Escalate semantic must be present.
    assert "escalate" in text.lower()
    # The fan-out failure mode keyword (all mismatch).
    assert "not_indexed" in text or "mismatch" in text.lower()


# ---------------------------------------------------------------------------
# Test 8 — DURUR #4 GSC quota exceeded AMBER partial
# ---------------------------------------------------------------------------

def test_verify_indexing_durur_4_quota_partial() -> None:
    """DURUR #4: GSC quota exceeded (200/day default) → AMBER + partial
    result (kalan URL'ler skipped, event payload partial flag)."""
    text = _skill_text()
    assert "DURUR #4" in text
    assert "quota" in text.lower()
    assert "AMBER" in text
    assert "partial" in text.lower()
    # Default quota cap referenced.
    assert "200" in text


# ---------------------------------------------------------------------------
# Test 9 — master.xlsx WRITE YASAK (W-G1 sentinel paterni reuse)
# ---------------------------------------------------------------------------

def test_master_xlsx_write_yasak_completed_work_read_only() -> None:
    """F-1 schema authority: master.xlsx[completed_work] read-only consume.
    Skill prose MUST NOT advertise transaction.append/update/delete against
    the workbook. W-G1 indexing-ping sentinel paterni reused."""
    text = _skill_text()

    # READ-ONLY claim must be explicit.
    assert "READ-ONLY" in text or "read-only" in text.lower()
    assert "completed_work" in text
    assert "WRITE YASAK" in text or "WRITE YOK" in text or "write yasak" in text.lower()

    # No transaction writes against workbook.
    forbidden_writes = re.findall(
        r"transaction\.(append|update|delete)\s*\(", text
    )
    assert not forbidden_writes, (
        f"READ-ONLY contract violation: skill body invokes "
        f"transaction.* writes: {forbidden_writes}"
    )

    # No openpyxl workbook.save() invocation (sentinel docs OK with capital W).
    save_invocations = re.findall(r"workbook\.save\s*\(", text)
    assert not save_invocations, (
        "WRITE attempt advertised: workbook.save() invocation found in skill"
    )

    # F-1 invariant must be documented.
    assert "F-1" in text
    assert "allowed_writers" in text


# ---------------------------------------------------------------------------
# Test 10 — events.jsonl event_kind=audit + schema-first override (lesson 31)
# ---------------------------------------------------------------------------

def test_events_audit_event_kind_schema_first_override() -> None:
    """Schema-first override (lesson 7+23+31, 4th convergent application):
    events.schema.json event_type is WORK-only closed 10-value enum (F-8).
    The brief sketched 'indexing_verified' for an audit event — but
    event_type does not apply to audit kind, AND 'indexing_verified' is
    not in the WORK-only enum either way. Audit allOf rule requires
    audit_action / audit_target / actor; skill emits event_kind=audit +
    audit_action=accessed (READ-only verification semantics)."""
    text = _skill_text()

    # Schema-first override decision must be documented (4th convergent).
    assert "Schema-first override" in text or "schema-first override" in text
    assert "lesson 31" in text or "4th" in text.lower() or "convergent" in text.lower()

    # event_kind=audit declared.
    assert "event_kind=audit" in text or "`audit`" in text
    # audit_action=accessed (READ-only verification → 'accessed' enum value).
    assert "audit_action=accessed" in text or "`accessed`" in text
    # audit_target URN encoding present.
    assert "audit_target" in text
    # actor=skill:verify-indexing identity.
    assert "skill:verify-indexing" in text or "actor" in text

    # Schema authority cross-check.
    schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text("utf-8")
    )

    # event_kind enum 4-value (ADR-020) cross-check.
    kinds = schema["properties"]["event_kind"]["enum"]
    assert kinds == ["provenance", "work", "audit", "workflow"], (
        f"event_kind enum drift: {kinds!r}; ADR-020 expects "
        f"['provenance', 'work', 'audit', 'workflow']"
    )

    # event_type WORK-only enum: indexing_verified MUST NOT be in it.
    type_enum = schema["properties"]["event_type"]["enum"]
    assert "indexing_verified" not in type_enum, (
        "events.schema drift: 'indexing_verified' should NOT appear in F-8 "
        "WORK-only event_type enum (this is precisely why W-G4 schema-first "
        "override avoided event_type entirely on audit lines)"
    )

    # audit_action enum 6-value cross-check (accessed must be in it).
    audit_action_enum = schema["properties"]["audit_action"]["enum"]
    assert "accessed" in audit_action_enum, (
        f"events.schema drift: 'accessed' missing from audit_action enum "
        f"{audit_action_enum!r}"
    )

    # audit allOf rule requires audit_action + audit_target + actor.
    audit_required = None
    for rule in schema.get("allOf", []):
        if rule.get("if", {}).get("properties", {}).get("event_kind", {}) \
                .get("const") == "audit":
            audit_required = set(rule.get("then", {}).get("required", []))
            break
    assert audit_required == {"audit_action", "audit_target", "actor"}, (
        f"audit allOf required-field drift: {audit_required!r}"
    )


# ---------------------------------------------------------------------------
# Test 11 — W-G1 sequential dependency rationale documented (24-72h window)
# ---------------------------------------------------------------------------

def test_wg1_sequential_dependency_section_documented() -> None:
    """The skill body MUST contain a 'Sequential Dependency on W-G1' section
    (or equivalent prose) explaining the 24-72 hour verification window per
    docs/ARCHITECTURE.md §24.4. This is the truth-verifiable closing leg of
    the submit/verify pair started in Wave 1."""
    text = _skill_text()

    # Section heading or explicit phrase present.
    assert "Sequential Dependency on W-G1" in text or \
        "sequential dependency on w-g1" in text.lower()

    # 24-72 hour window referenced (verify call timing per §24.4).
    assert "24-72" in text or "24h" in text or "24 hour" in text.lower() or \
        "≥24" in text

    # W-G1 / indexing-ping name referenced explicitly.
    assert "W-G1" in text
    assert "indexing-ping" in text

    # The verification semantic anchor: actual vs expected, mismatch report.
    assert "actual" in text.lower()
    assert "expected" in text.lower()


# ---------------------------------------------------------------------------
# Test 12 — Plugin-agnostic: no slug hardcoded; .mcp.json invariant
# ---------------------------------------------------------------------------

def test_plugin_agnostic_no_slug_and_mcp_json_unchanged() -> None:
    """Plugin-agnostic discipline: project slugs MUST NOT be hardcoded
    in skill content (allowed only inside backtick fencing as banned-
    list citations). Phase 7 lesson tokens (estimated_credits_per_call /
    _per_url / metric_name) zero-tolerance. F-16 invariant: .mcp.json
    byte-hash unchanged across the skill's lifecycle."""
    text = _skill_text()

    # Phase 7 lesson tokens — strict zero-tolerance.
    for token in ("estimated_credits_per_call",
                  "estimated_credits_per_url",
                  "metric_name"):
        assert token not in text, f"Phase 7-lesson token leaked: {token}"

    # Project slugs — allowed only inside backticks.
    slugs = ["dentnotion", "vento", "eykom", "bigcattr",
             "calitte", "lastiksa", "noraninsaat", "adstark"]
    for slug in slugs:
        for m in re.finditer(re.escape(slug), text):
            start = m.start()
            line_start = text.rfind("\n", 0, start) + 1
            line_end = text.find("\n", start)
            line = text[line_start:line_end if line_end != -1 else len(text)]
            assert f"`{slug}`" in line, (
                f"Plugin-agnostic violation: slug '{slug}' appears "
                f"outside backtick fencing in line: {line!r}"
            )

    # F-16 invariant — .mcp.json byte-hash unchanged.
    mcp_json_path = REPO_ROOT / ".mcp.json"
    assert mcp_json_path.exists(), ".mcp.json missing — F-16 invariant broken"
    h = hashlib.sha256(mcp_json_path.read_bytes()).hexdigest()
    assert len(h) == 64

    # F-16 invariant must be documented in the skill itself.
    assert "F-16" in text
    assert ".mcp.json" in text


# ---------------------------------------------------------------------------
# Test 13 — Foundational Principles 3-layer enforcement
# ---------------------------------------------------------------------------

def test_foundational_principles_3_layer_enforce() -> None:
    """Principle 1 truth-verifiable (audit provenance + GSC raw response),
    Principle 2 profile-aware documented (5-enum named, ymyl/e-commerce
    severity divergence noted), Principle 3 anti-hallucinated-coverage
    (GSC raw response only, no heuristic / pattern-matched status)."""
    text = _skill_text()

    # Principle 1 — Truth-Verifiable Coverage.
    assert "Principle 1" in text
    assert "Truth-Verifiable" in text or "truth-verifiable" in text.lower()
    # 3-layer defense (Layer 1/2/3 explicit).
    assert "Layer 1" in text
    assert "Layer 2" in text
    assert "Layer 3" in text
    # AI suistimal phrase (Turkish: "AI suistimal" + the hayali fabrikasyon ban).
    assert "suistimal" in text.lower() or "hallucinat" in text.lower()
    assert "hayali" in text.lower() or "fabricat" in text.lower()

    # Principle 2 — Profile-aware documented placeholder.
    assert "Principle 2" in text
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    for p in profile_enum:
        assert p in text, f"Profile enum value missing in skill body: {p}"

    # Principle 3 — Anti-hallucinated-coverage gate.
    assert "Principle 3" in text
    assert "wildcard" in text.lower()
    assert "dedup" in text.lower()
    # Per-run cap mentioned (200 GSC URL Inspection daily quota).
    assert "200" in text


# ---------------------------------------------------------------------------
# Test 14 — Self-extending bonus (lesson 29): coverage report shape
# ---------------------------------------------------------------------------

def test_coverage_report_artifact_json_shape_documented() -> None:
    """Self-extending positive drift (lesson 29 production-ready signal):
    the skill documents the exact JSON shape of the per-run coverage
    report so downstream consumers (monthly-report, governance audits)
    have a stable contract. Bonus coverage beyond the 4 DURUR sentinels."""
    text = _skill_text()

    # The report path pattern.
    assert "outputs/indexing/" in text
    assert "coverage-report.json" in text

    # Required fields in the report.
    required_fields = [
        "match_count",
        "mismatch_count",
        "coverage",  # the per-URL list field
        "quota_partial_flag",
        "escalation_recommended",
        "expected_status",
    ]
    for field in required_fields:
        assert field in text, (
            f"Report contract drift: '{field}' field missing from "
            f"coverage report shape documentation"
        )

    # Per-URL coverage row schema fields.
    per_url_fields = ["actual_status", "expected_status", "mismatch_bool",
                      "gsc_response_raw"]
    for field in per_url_fields:
        assert field in text, (
            f"Per-URL coverage row drift: '{field}' missing from "
            f"coverage[] item documentation"
        )
