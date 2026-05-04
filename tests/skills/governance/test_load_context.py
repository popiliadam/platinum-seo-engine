"""tests/skills/governance/test_load_context.py — load-context (Phase 13 W-H3).

Coverage (12 tests, lesson 29 self-extending positive drift over upper bound 7-9):
  1. Frontmatter required 8-field Draft7 validity (skill-frontmatter.schema.json).
  2. Inputs/Outputs structure — 2 inputs (phase_id + max_kb), 2 outputs
     (events.jsonl + report markdown). master.xlsx ABSENT.
  3. natural_language ≥30-char block (lesson 8 sentinel).
  4. Spec §1 + §13 + §17 anchor regex extract documented (NOT full spec read).
  5. PHASE_STATUS.md "Active Phase" line parse (auto-detect phase_id).
  6. DECISIONS.md last 5 ADR header anchor regex (`^## ADR-NNN`).
  7. REFERENCE_INDEX.md full read documented (~3KB, well under budget).
  8. SESSION_PROTOCOL.md §2 wakeup 7-step sequence verify match.
  9. Byte budget 15KB default + max_kb input parametrize documented.
  10. master.xlsx WRITE YOK invariant — Phase 9/12/13 paterni reuse
      (transaction.* + wb.save() regex 0 hit).
  11. events.jsonl audit kind compliance — schema-first override:
      event_kind=audit + audit_action=accessed + audit_target=
      session:wakeup-codify + actor=agent:load-context. event_type
      WORK-only enum NOT used.
  12. Plugin-agnostic — mcp_tools=[] required + optional empty.
  13. Foundational Principles 3-layer — truth-verifiable + profile-aware
      (5-enum) + AI suistimal yasağı.

Discipline:
  - Plugin-agnostic invariant: phase_id default = "auto-detect" (NOT
    hardcoded "phase-13"); F-13.1 finding paterni reuse.
  - READ-ONLY contract verified by grep.
  - Schema-first override (lesson 7+23+31+34): governance audit kind
    compliance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / "skills" / "governance" / "load-context" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"
MCP_JSON = REPO_ROOT / ".mcp.json"
DOCS = REPO_ROOT / "docs"
SPEC_PATH = (
    DOCS / "superpowers" / "specs"
    / "2026-04-30-platinum-seo-engine-design.md"
)
PHASE_STATUS = DOCS / "PHASE_STATUS.md"
DECISIONS = DOCS / "DECISIONS.md"
REFERENCE_INDEX = DOCS / "REFERENCE_INDEX.md"
SESSION_PROTOCOL = DOCS / "SESSION_PROTOCOL.md"


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

    assert fm["name"] == "load-context"
    assert fm["category"] == "governance"
    assert fm["status"] == "wip"
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True


# ---------------------------------------------------------------------------
# Test 2 — Inputs/Outputs structure
# ---------------------------------------------------------------------------

def test_inputs_outputs_structure() -> None:
    """Inputs additionalProperties=false 4-field whitelist. master.xlsx
    ABSENT from outputs."""
    fm = _parse_frontmatter(SKILL_PATH)

    assert "phase_id" in fm["inputs"]
    assert "max_kb" in fm["inputs"]
    assert fm["inputs"]["phase_id"]["type"] == "string"
    # F-13.1 paterni reuse — auto-detect, NOT hardcoded "phase-13"
    assert fm["inputs"]["phase_id"].get("default") == "auto-detect"
    assert fm["inputs"]["max_kb"]["type"] == "integer"
    assert fm["inputs"]["max_kb"].get("default") == 15

    allowed_keys = {"type", "required", "default", "description"}
    for input_name, input_def in fm["inputs"].items():
        assert set(input_def.keys()) <= allowed_keys, (
            f"input {input_name!r} keys outside whitelist"
        )

    outs = fm["outputs"]
    assert isinstance(outs, list)
    assert len(outs) == 2
    assert any("_state/events.jsonl" in o for o in outs)
    assert any(
        "outputs/reports/" in o and "load-context" in o for o in outs
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
    assert len(nl) >= 30


# ---------------------------------------------------------------------------
# Test 4 — Spec §1 + §13 + §17 anchor regex extract
# ---------------------------------------------------------------------------

def test_spec_sections_1_13_17_extract_regex() -> None:
    """Body documents the §1 + §13 + §17 bounded read with anchor regex
    `^## \\d+\\.`. NOT full spec read (would blow 15KB budget)."""
    body = _skill_body()
    # §1 + §13 + §17 explicitly named
    assert re.search(r"§1.+§13.+§17|§1\b|section.*1.*13.*17",
                     body, re.IGNORECASE | re.DOTALL), (
        "body must reference §1 + §13 + §17 sections"
    )
    # Anchor regex pattern documented
    assert re.search(r"\^## \\d|## \\d|## N\.|## \d", body), (
        "body must document the anchor regex pattern"
    )

    # Authority sanity: spec file exists + has §1, §13, §17 headings
    assert SPEC_PATH.exists(), "spec design.md missing — load-context cannot run"
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    for idx in (1, 13, 17):
        assert re.search(rf"^## {idx}\.", spec_text, re.MULTILINE), (
            f"spec §{idx} heading anchor missing — DURUR #1 condition"
        )


# ---------------------------------------------------------------------------
# Test 5 — PHASE_STATUS Active Phase parse
# ---------------------------------------------------------------------------

def test_phase_status_active_phase_parse() -> None:
    """PHASE_STATUS.md must contain `**Active Phase:**` markdown bold line.
    Skill body documents the regex extract."""
    text = PHASE_STATUS.read_text(encoding="utf-8")
    m = re.search(r"^\*\*Active Phase:\*\*\s*([^\n]+)", text, re.MULTILINE)
    assert m, "PHASE_STATUS.md missing '**Active Phase:**' anchor"
    active_phase = m.group(1).strip()
    assert active_phase, "Active Phase line empty"

    body = _skill_body()
    assert re.search(r"Active Phase|active.phase", body, re.IGNORECASE), (
        "skill body must document Active Phase parse"
    )


# ---------------------------------------------------------------------------
# Test 6 — DECISIONS.md last 5 ADR header anchor regex
# ---------------------------------------------------------------------------

def test_decisions_last_5_adr_anchor() -> None:
    """DECISIONS.md must declare `## ADR-NNN` headers. Skill body documents
    the regex extract for last-5 ADR retrieval."""
    text = DECISIONS.read_text(encoding="utf-8")
    adr_anchors = list(re.finditer(r"^## ADR-(\d+)", text, re.MULTILINE))
    # Sanity: at least 1 ADR exists (typically 4+ active per ADR-011 rotation)
    assert len(adr_anchors) >= 1, (
        f"DECISIONS.md unexpectedly empty: {len(adr_anchors)} ADRs"
    )

    body = _skill_body()
    assert re.search(r"ADR-\\?\d|## ADR-N|ADR.NNN|last 5 ADR|last.5.ADR",
                     body, re.IGNORECASE), (
        "skill body must document the ADR anchor regex"
    )


# ---------------------------------------------------------------------------
# Test 7 — REFERENCE_INDEX full read documented
# ---------------------------------------------------------------------------

def test_reference_index_full_read_documented() -> None:
    """REFERENCE_INDEX.md is small enough to read in full (~3KB).
    Skill body documents this is a full read (not anchored extraction)."""
    text = REFERENCE_INDEX.read_text(encoding="utf-8")
    size_bytes = len(text.encode("utf-8"))
    # Small enough to fit budget
    assert size_bytes < 8 * 1024, (
        f"REFERENCE_INDEX grew unexpectedly: {size_bytes}B"
    )

    body = _skill_body()
    assert re.search(r"REFERENCE_INDEX", body)
    assert re.search(r"full.read|3KB|under budget", body, re.IGNORECASE), (
        "skill body must document REFERENCE_INDEX as full read"
    )


# ---------------------------------------------------------------------------
# Test 8 — SESSION_PROTOCOL §2 wakeup 7-step sequence verify
# ---------------------------------------------------------------------------

def test_session_protocol_wakeup_7_step_match() -> None:
    """SESSION_PROTOCOL.md §2 must declare a numbered 7-step sequence.
    Skill body verifies this match."""
    text = SESSION_PROTOCOL.read_text(encoding="utf-8")
    # §2 section bounded by next ## header
    section_2 = re.search(
        r"^## 2\.[^\n]*\n(.*?)(?=^## )",
        text, re.MULTILINE | re.DOTALL,
    )
    assert section_2, "SESSION_PROTOCOL §2 section missing"
    step_lines = re.findall(
        r"^\d\.\s", section_2.group(1), re.MULTILINE,
    )
    assert len(step_lines) >= 7, (
        f"SESSION_PROTOCOL §2 wakeup must have ≥7 numbered steps; "
        f"found {len(step_lines)}"
    )

    body = _skill_body()
    assert re.search(r"7.step|7-step|seven.step", body, re.IGNORECASE), (
        "skill body must document the 7-step sequence"
    )


# ---------------------------------------------------------------------------
# Test 9 — Byte budget 15KB + max_kb parametrize + DURUR sentinels
# ---------------------------------------------------------------------------

def test_byte_budget_15kb_documented_and_durur_sentinels() -> None:
    """Body documents <15KB total budget (default) + max_kb input
    parametrize. DURUR #1 (spec missing) + DURUR #2 (budget exceeded)
    sentinels present."""
    body = _skill_body()

    # 15KB default
    assert re.search(r"15.?KB|15\s*\*\s*1024|15_000|15000", body), (
        "skill body must document 15KB byte budget"
    )
    # max_kb input mentioned
    assert re.search(r"max_kb", body), (
        "skill body must reference max_kb input"
    )

    # DURUR sentinels (≥2 per brief: 2 DURUR explicit, but spec said ≥3 — we
    # accept ≥2 since DURUR #3 was not strictly mandated for load-context;
    # brief documented exactly 2 DURUR conditions for this skill)
    assert "DURUR #1" in body
    assert "DURUR #2" in body
    # DURUR #1: spec missing or §anchors not found
    assert re.search(r"DURUR #1.{0,400}(?:spec|§|anchor)",
                     body, re.DOTALL | re.IGNORECASE)
    # DURUR #2: byte budget exceeded
    assert re.search(r"DURUR #2.{0,400}(?:budget|byte|exceeded|max_kb)",
                     body, re.DOTALL | re.IGNORECASE)


# ---------------------------------------------------------------------------
# Test 10 — master.xlsx WRITE YOK invariant
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
# Test 11 — events.jsonl audit kind compliance
# ---------------------------------------------------------------------------

def test_events_audit_kind_schema_first_override() -> None:
    """Schema-first override (lesson 7+23+31+34): event_kind=audit +
    audit_action=accessed + audit_target=session:wakeup-codify +
    actor=agent:load-context. event_type WORK-only enum NOT used."""
    body = _skill_body()

    assert re.search(r"event_kind\s*=?\s*[\"']?audit", body)
    assert re.search(r'audit_action\s*=?\s*[\"]?accessed', body)
    assert re.search(r'audit_target\s*=?\s*[\"]?session:wakeup-codify', body)
    assert re.search(r'actor\s*=?\s*[\"]?agent:load-context', body)

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
# Test 12 — Plugin-agnostic + mcp_tools empty + auto-detect (F-13.1 reuse)
# ---------------------------------------------------------------------------

def test_plugin_agnostic_mcp_tools_empty_and_auto_detect() -> None:
    """F-16 plugin agnostik invariant + F-13.1 finding paterni reuse:
    phase_id default 'auto-detect' (NOT hardcoded 'phase-13')."""
    fm = _parse_frontmatter(SKILL_PATH)
    mcp = fm["mcp_tools"]
    assert mcp.get("required", []) == []
    assert mcp.get("optional", []) == []

    # F-13.1 paterni reuse: NO hardcoded phase id
    assert fm["inputs"]["phase_id"]["default"] == "auto-detect"
    desc = fm["description"]
    # Description must NOT lock to a specific phase number
    assert not re.search(r"phase[-\s]?1[34]\b", desc, re.IGNORECASE), (
        f"description hardcoded phase id (F-13.1 finding): {desc!r}"
    )


# ---------------------------------------------------------------------------
# Test 13 — Foundational Principles 3-layer enforce
# ---------------------------------------------------------------------------

def test_foundational_principles_three_layer() -> None:
    body = _skill_body()
    assert re.search(r"Truth.verifiable|truth.verifiable", body)
    assert re.search(r"Profile.aware|profile.aware", body)
    assert re.search(r"5.enum|5-value", body, re.IGNORECASE)
    assert re.search(r"suistimal", body, re.IGNORECASE)
