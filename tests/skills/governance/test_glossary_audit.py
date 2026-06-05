"""tests/skills/governance/test_glossary_audit.py — glossary-audit (Phase 13 W-H2).

Coverage (10 tests, lesson 29 self-extending positive drift over upper bound 5-7):
  1. Frontmatter required 8-field Draft7 validity (skill-frontmatter.schema.json).
  2. Inputs/Outputs structure — 2 inputs (glossary_path + spec_path),
     2 outputs (events.jsonl + report markdown). master.xlsx ABSENT.
  3. natural_language ≥30-char block (lesson 8 sentinel).
  4. Glossary alphabetical bullet pattern parse (~20 terms, manager kanıt #12 = 23 line).
  5. Spec §20 section bold-pattern extract regex documented.
  6. REFERENCE_INDEX glossary anchor cross-ref valid (heading link integrity).
  7. Acronym whitelist documented (defensive false-positive guard for JSON,
     URL, API, HTML, etc.) — covers AMBER orphan + missing both directions.
  8. Orphan + missing surfaces as AMBER (NOT RED) — Disiplin #8 enforcement
     paterni.
  9. master.xlsx WRITE YOK invariant — Phase 9/12 paterni reuse
     (transaction.* + wb.save() regex 0 hit).
  10. events.jsonl audit kind compliance — schema-first override:
      event_kind=audit + audit_action=accessed + audit_target=
      docs:glossary-audit + actor=agent:glossary-audit. event_type
      WORK-only enum NOT used.
  11. Plugin-agnostic — mcp_tools=[] required + optional empty.
  12. Foundational Principles 3-layer — truth-verifiable + profile-aware
      (5-enum) + AI suistimal yasağı.

Discipline:
  - Plugin-agnostic invariant: no project slug hardcoded.
  - READ-ONLY contract verified by grep (transaction.* + wb.save() absent).
  - Schema-first override (lesson 7+23+31+34): governance signals routed
    to event_kind=audit, NOT event_type WORK enum.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / "skills" / "governance" / "glossary-audit" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"
MCP_JSON = REPO_ROOT / ".mcp.json"
GLOSSARY_PATH = REPO_ROOT / "docs" / "GLOSSARY.md"
SPEC_PATH = (
    REPO_ROOT / "docs" / "superpowers" / "specs"
    / "2026-04-30-platinum-seo-engine-design.md"
)
REFERENCE_INDEX = REPO_ROOT / "docs" / "REFERENCE_INDEX.md"


def _parse_frontmatter(skill_path: Path) -> dict:
    text = skill_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise ValueError(f"No YAML frontmatter in {skill_path}")
    return yaml.safe_load(m.group(1))


def _skill_body() -> str:
    text = SKILL_PATH.read_text(encoding="utf-8")
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[m.end():] if m else text


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter required 8-field Draft7 validity
# ---------------------------------------------------------------------------

def test_frontmatter_required_fields_draft7_valid() -> None:
    fm = _parse_frontmatter(SKILL_PATH)
    required = ["name", "description", "version", "status", "category",
                "inputs", "outputs", "triggers"]
    for field in required:
        assert field in fm

    schema = json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )
    validator = Draft7Validator(schema)
    errors = sorted(
        validator.iter_errors(fm), key=lambda e: list(e.absolute_path)
    )
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: "
        f"{e.message}"
        for e in errors
    )

    assert fm["name"] == "glossary-audit"
    assert fm["category"] == "governance"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True


# ---------------------------------------------------------------------------
# Test 2 — Inputs/Outputs structure
# ---------------------------------------------------------------------------

def test_inputs_outputs_structure() -> None:
    """Inputs is object<param, {type, required, default, description}>
    additionalProperties=false 4-field whitelist. Outputs is array<string>,
    master.xlsx ABSENT."""
    fm = _parse_frontmatter(SKILL_PATH)

    assert isinstance(fm["inputs"], dict)
    assert "glossary_path" in fm["inputs"]
    assert "spec_path" in fm["inputs"]
    assert fm["inputs"]["glossary_path"]["type"] == "string"
    assert fm["inputs"]["glossary_path"].get("default") == "docs/GLOSSARY.md"
    assert fm["inputs"]["spec_path"]["type"] == "string"

    allowed_keys = {"type", "required", "default", "description"}
    for input_name, input_def in fm["inputs"].items():
        assert set(input_def.keys()) <= allowed_keys, (
            f"input {input_name!r} keys outside whitelist: "
            f"{set(input_def.keys()) - allowed_keys}"
        )

    outs = fm["outputs"]
    assert isinstance(outs, list)
    assert len(outs) == 2
    assert any("_state/events.jsonl" in o for o in outs)
    assert any(
        "outputs/reports/" in o and "glossary-audit" in o for o in outs
    )

    for o in outs:
        assert "master.xlsx" not in o


# ---------------------------------------------------------------------------
# Test 3 — natural_language ≥30 chars
# ---------------------------------------------------------------------------

def test_natural_language_min_length() -> None:
    fm = _parse_frontmatter(SKILL_PATH)
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str)
    assert len(nl) >= 30, f"natural_language too short: {len(nl)} chars"


# ---------------------------------------------------------------------------
# Test 4 — Glossary alphabetical bullet pattern parse (~20 terms)
# ---------------------------------------------------------------------------

def test_glossary_alphabetical_bullet_parse() -> None:
    """GLOSSARY.md follows the alphabetical bullet pattern. Manager kanıt
    #12 = 23 line including header. Skill body must reference the parse
    pattern."""
    text = GLOSSARY_PATH.read_text(encoding="utf-8")
    term_pattern = re.compile(r"^- \*\*([^\*]+)\*\*", re.MULTILINE)
    glossary_terms = term_pattern.findall(text)

    # Sanity: glossary has at least 10 terms
    assert len(glossary_terms) >= 10, (
        f"GLOSSARY.md unexpectedly small: {len(glossary_terms)} terms"
    )

    # Body must document the pattern
    body = _skill_body()
    assert re.search(r"alphabetical|bullet|`-\s*\*\*`|term_pattern",
                     body, re.IGNORECASE), (
        "skill body must document the glossary parse pattern"
    )


# ---------------------------------------------------------------------------
# Test 5 — Spec §20 section bold-pattern extract regex documented
# ---------------------------------------------------------------------------

def test_spec_section_20_extract_regex_documented() -> None:
    """Spec §20 (Glossary) extract by bold pattern `^- \\*\\*[A-Z][^\\*]+\\*\\*`.
    Skill body must reference this pattern."""
    body = _skill_body()
    # The body documents the spec §20 cross-ref + bold pattern
    assert re.search(r"§20|spec.*20|section.*20", body, re.IGNORECASE), (
        "skill body must reference spec §20"
    )
    # Body documents the bold-pattern regex (escaped or unescaped)
    assert re.search(r"\\\*\\\*|\*\*[A-Z]|bold.pattern", body), (
        "skill body must document the bold-pattern extraction regex"
    )


# ---------------------------------------------------------------------------
# Test 6 — REFERENCE_INDEX glossary anchor cross-ref valid
# ---------------------------------------------------------------------------

def test_reference_index_glossary_anchor_valid() -> None:
    """REFERENCE_INDEX.md must contain GLOSSARY.md heading link
    (link integrity verification authority)."""
    text = REFERENCE_INDEX.read_text(encoding="utf-8")
    assert "GLOSSARY.md" in text, (
        "REFERENCE_INDEX missing GLOSSARY.md anchor — Disiplin #8 break"
    )

    # Body must document the cross-ref check
    body = _skill_body()
    assert re.search(r"REFERENCE_INDEX", body), (
        "skill body must reference REFERENCE_INDEX cross-ref"
    )


# ---------------------------------------------------------------------------
# Test 7 — Acronym whitelist documented (false-positive guard)
# ---------------------------------------------------------------------------

def test_acronym_whitelist_no_false_positive() -> None:
    """Body must declare a defensive acronym whitelist (JSON, URL, API,
    HTML, CSS, SEO, MCP, GSC, DFS, AIO, FAQ, JSON-LD, XML, HTTP, CSV,
    CLI, CI, ADR, R-XX, F-XX, D-XX, M-XX) to prevent missing-term false
    positives.

    Without this guard, every skill body would surface dozens of
    capitalized acronyms as "missing" — making the audit useless."""
    body = _skill_body()
    # Whitelist sentinel
    assert re.search(r"whitelist|WHITELIST", body), (
        "skill body must document an acronym whitelist"
    )
    # Sample acronyms must appear in the whitelist context
    for acronym in ("JSON", "URL", "API", "HTML", "MCP", "GSC", "ADR"):
        assert acronym in body, (
            f"whitelist must mention {acronym!r} (defensive guard)"
        )

    # Rule ID prefixes (R-XX, F-XX, D-XX, M-XX) — at least one mentioned
    assert re.search(r"R-\d|F-\d|D-\d|M-\d|R-XX|F-XX|D-XX|M-XX", body), (
        "skill body must mention rule ID prefixes (R-XX/F-XX/D-XX/M-XX) "
        "in whitelist context"
    )


# ---------------------------------------------------------------------------
# Test 7b — BEHAVIORAL missing-term detection (B6-02). The test above only
# rubber-stamps that the whitelist is *mentioned*; this one actually RUNS the
# documented Step 4 + Step 6 algorithm over a controlled fixture and asserts
# the flagged vs allowed terms. The Step 4 candidate regex is sourced verbatim
# from the live SKILL.md, so a revert of the 2+ token quantifier (B6-17,
# `)+` → `)*`) makes single-token acronyms candidates and fails this test.
# ---------------------------------------------------------------------------

# Mirrors the documented Step 6 ACRONYM_WHITELIST (a representative subset).
_FIXTURE_WHITELIST = frozenset({"JSON", "URL", "API", "HTML", "MCP", "GSC", "ADR"})


def _candidate_regex_from_skill() -> re.Pattern[str]:
    """Pull the Step 4 candidate-extraction pattern verbatim out of the
    SKILL.md so this test exercises the documented heuristic (not a copy that
    could silently drift from it)."""
    m = re.search(r'candidates = re\.findall\(r"(.+?)", body\)', _skill_body())
    assert m, "Step 4 candidate-extraction regex not found in SKILL.md"
    return re.compile(m.group(1))


def _is_rule_id(term: str) -> bool:
    return bool(re.match(r"^[FDMR]-\d+$", term))


def test_missing_term_detection_behavioral() -> None:
    """Run the documented detection over a fixture; assert exact flagged set."""
    pattern = _candidate_regex_from_skill()
    glossary = {"Content Decay"}  # one known glossary term in the fixture
    fixture_body = "\n".join([
        "we run Quick Wins to rank pages",    # 'Quick Wins'   — 2-token, NOT in glossary
        "the Content Decay sheet refreshes",  # 'Content Decay'— 2-token, IN glossary
        "it emits JSON over an API here",     # single-token acronyms — NOT candidates
        "a single Step token stands alone",   # 'Step'         — single token, NOT a candidate
        "see rule F-01 for the detail",       # 'F-01'         — not a Title-Case span
    ])
    candidates = set(pattern.findall(fixture_body))

    # Step 4 — the 2+ token requirement (B6-17): single tokens never qualify.
    assert "Quick Wins" in candidates
    assert "Content Decay" in candidates
    for single in ("JSON", "API", "Step", "F-01"):
        assert single not in candidates, (
            f"{single!r} is a single token — the 2+ token heuristic must not "
            f"flag it (B6-17 regex must require '+', not '*')"
        )

    # Step 6 — glossary membership + whitelist + rule-id filters.
    missing = {
        t for t in candidates
        if t not in glossary
        and t not in _FIXTURE_WHITELIST
        and not _is_rule_id(t)
    }
    assert missing == {"Quick Wins"}, (
        "missing-term detection should flag exactly 'Quick Wins' (the 2-token "
        f"span absent from glossary), got {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# Test 8 — Orphan + missing → AMBER (NOT RED) Disiplin #8 paterni
# ---------------------------------------------------------------------------

def test_orphan_and_missing_amber_not_red() -> None:
    """Orphan (in glossary but unused in skills) and missing (in skills
    but absent from glossary) both surface as AMBER warn — Disiplin #8
    is curation discipline, not hard schema rule."""
    body = _skill_body()

    # DURUR #2 = orphan; DURUR #3 = missing; both must be AMBER
    assert "DURUR #2" in body
    assert "DURUR #3" in body
    assert re.search(r"DURUR #2.{0,500}AMBER", body, re.DOTALL), (
        "DURUR #2 orphan must be AMBER"
    )
    assert re.search(r"DURUR #3.{0,500}AMBER", body, re.DOTALL), (
        "DURUR #3 missing must be AMBER"
    )
    # NOT RED for these two classes
    assert re.search(r"AMBER\s*\(NOT RED\)|NOT.RED|AMBER.*not.*RED",
                     body, re.IGNORECASE), (
        "body must explicitly state AMBER (NOT RED) for orphan/missing"
    )

    # DURUR #1 sentinel also present (glossary missing/unparseable)
    assert "DURUR #1" in body


# ---------------------------------------------------------------------------
# Test 9 — master.xlsx WRITE YOK invariant
# ---------------------------------------------------------------------------

def test_master_xlsx_no_write_invariant() -> None:
    body = _skill_body()
    forbidden = [
        r"transaction\.append\(",
        r"transaction\.update\(",
        r"transaction\.delete\(",
        r"wb\.save\(",
    ]
    for token_re in forbidden:
        m = re.search(token_re, body)
        assert m is None, (
            f"Forbidden write call site {token_re!r} found at "
            f"offset {m.start() if m else -1}: master.xlsx WRITE YASAK"
        )

    assert re.search(r"READ-ONLY|read-only|read.only", body, re.IGNORECASE)

    fm = _parse_frontmatter(SKILL_PATH)
    for o in fm["outputs"]:
        assert "master.xlsx" not in o


# ---------------------------------------------------------------------------
# Test 10 — events.jsonl audit kind compliance
# ---------------------------------------------------------------------------

def test_events_audit_kind_schema_first_override() -> None:
    """Schema-first override (lesson 7+23+31+34): events.schema.json
    audit allOf rule: audit_action + audit_target + actor required triple.
    event_type WORK-only enum NOT used."""
    body = _skill_body()

    assert re.search(r"event_kind\s*=?\s*[\"']?audit", body)
    assert re.search(r'audit_action\s*=?\s*[\"]?accessed', body)
    assert re.search(r'audit_target\s*=?\s*[\"]?docs:glossary-audit', body)
    assert re.search(r'actor\s*=?\s*[\"]?agent:glossary-audit', body)

    # Cross-check schema authority
    events_schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text("utf-8")
    )
    audit_branches = [
        b for b in events_schema["allOf"]
        if b.get("if", {}).get("properties", {}).get("event_kind", {}).get("const") == "audit"
    ]
    assert audit_branches
    audit_required = audit_branches[0]["then"]["required"]
    assert set(audit_required) == {"audit_action", "audit_target", "actor"}


# ---------------------------------------------------------------------------
# Test 11 — Plugin-agnostic + mcp_tools empty
# ---------------------------------------------------------------------------

def test_plugin_agnostic_mcp_tools_empty() -> None:
    fm = _parse_frontmatter(SKILL_PATH)
    mcp = fm["mcp_tools"]
    assert mcp.get("required", []) == []
    assert mcp.get("optional", []) == []
    assert MCP_JSON.exists()


# ---------------------------------------------------------------------------
# Test 12 — Foundational Principles 3-layer enforce
# ---------------------------------------------------------------------------

def test_foundational_principles_three_layer() -> None:
    body = _skill_body()
    assert re.search(r"Truth.verifiable|truth.verifiable", body)
    assert re.search(r"Profile.aware|profile.aware", body)
    assert re.search(r"5.enum|5-value", body, re.IGNORECASE)
    assert re.search(r"suistimal", body, re.IGNORECASE)
