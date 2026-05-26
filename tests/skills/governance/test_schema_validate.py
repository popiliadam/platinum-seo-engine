"""tests/skills/governance/test_schema_validate.py — schema-validate skill (Phase 13 W-H1).

Coverage (9 tests, lesson 29 self-extending positive drift over upper bound 6-8):
  1. Frontmatter required 8-field Draft7 validity (skill-frontmatter.schema.json).
  2. Inputs/Outputs structure — 2 inputs (schema_path + strict), 2 outputs
     (events.jsonl + report markdown). master.xlsx ABSENT.
  3. natural_language ≥30-char block (lesson 8 sentinel).
  4. Schemas glob enumerate (NOT hardcoded count) — F-13.1 manager finding
     paterni: schema authority kazanır, brief authority claim drift recovery.
  5. cross-sheet-invariants `rules` key compile + 20 rule structural validate
     (NOT "invariants" key — schema-first override lesson 31+34).
  6. SKILL.md frontmatter Draft7 compliance — 40+ skill files validated.
  7. Strict + FAIL → exit 1 documented (DURUR #3).
  8. Non-strict + FAIL → AMBER report (no exit) documented.
  9. master.xlsx WRITE YOK invariant — Phase 9/12 paterni reuse
     (transaction.* + wb.save() regex 0 hit on production prose).
  10. events.jsonl audit kind compliance — schema-first override (lesson 31+34):
      event_kind=audit + audit_action=accessed + audit_target=
      schemas:bulk-validate + actor=agent:schema-validate. event_type
      WORK-only enum NOT used.
  11. Plugin-agnostic — .mcp.json byte unchanged (F-16 invariant);
      mcp_tools=[] required + optional empty.
  12. Foundational Principles 3-layer — truth-verifiable + profile-aware
      (5-enum) + AI suistimal yasağı.

Discipline:
  - Every assertion derives from a schema authority (schemas/*) or
    rules/foundational-principles.md cross-link.
  - Plugin-agnostic invariant: no project slug hardcoded in the skill.
  - READ-ONLY contract verified by grep (transaction.* + wb.save() absent).
  - Schema-first override (lesson 7+23+31+34): brief drift → schema
    authority wins.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / "skills" / "governance" / "schema-validate" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"
MCP_JSON = REPO_ROOT / ".mcp.json"


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
    """Frontmatter declares the 8 required fields per
    skill-frontmatter.schema.json (Draft7) and validates end-to-end."""
    fm = _parse_frontmatter(SKILL_PATH)
    required = ["name", "description", "version", "status", "category",
                "inputs", "outputs", "triggers"]
    for field in required:
        assert field in fm, f"Missing required field: {field}"

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

    assert fm["name"] == "schema-validate"
    assert fm["category"] == "governance"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["triggers"]["manual"] == ["/pseo-driftcheck"]
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True
    assert fm["autonomy"]["requires_approval"] is False


# ---------------------------------------------------------------------------
# Test 2 — Inputs/Outputs structure (2 inputs, 2 outputs, master.xlsx absent)
# ---------------------------------------------------------------------------

def test_inputs_outputs_structure() -> None:
    """Inputs is object<param, {type, required, default, description}> per
    schema (additionalProperties=false, 4-field whitelist). Outputs is
    array<string>, master.xlsx ABSENT."""
    fm = _parse_frontmatter(SKILL_PATH)

    assert isinstance(fm["inputs"], dict)
    assert "schema_path" in fm["inputs"]
    assert "strict" in fm["inputs"]
    assert fm["inputs"]["schema_path"]["type"] == "string"
    assert fm["inputs"]["schema_path"].get("default") == "schemas/"
    assert fm["inputs"]["strict"]["type"] == "boolean"
    assert fm["inputs"]["strict"].get("default") is True

    # additionalProperties=false enforces 4-field whitelist
    # (type, required, default, description) — no enum field
    allowed_keys = {"type", "required", "default", "description"}
    for input_name, input_def in fm["inputs"].items():
        assert set(input_def.keys()) <= allowed_keys, (
            f"input {input_name!r} has keys outside the 4-field whitelist: "
            f"{set(input_def.keys()) - allowed_keys}"
        )

    outs = fm["outputs"]
    assert isinstance(outs, list)
    assert len(outs) == 2, (
        f"outputs[] must have exactly 2 entries (events.jsonl + report); "
        f"got {len(outs)}: {outs}"
    )
    assert any("_state/events.jsonl" in o for o in outs)
    assert any(
        "outputs/reports/" in o and "schema-validate" in o for o in outs
    )

    for o in outs:
        assert "master.xlsx" not in o, (
            f"master.xlsx must NOT appear in outputs[] (Phase 9/12 "
            f"no-write paterni reuse): {o!r}"
        )


# ---------------------------------------------------------------------------
# Test 3 — natural_language ≥30-char sentinel
# ---------------------------------------------------------------------------

def test_natural_language_min_length() -> None:
    """natural_language must be ≥30 chars total (lesson 8 v3 sentinel)."""
    fm = _parse_frontmatter(SKILL_PATH)
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str)
    assert len(nl) >= 30, (
        f"natural_language too short ({len(nl)} chars; need ≥30): {nl!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 — Schemas runtime glob (F-13.1 finding: NO hardcoded count)
# ---------------------------------------------------------------------------

def test_schemas_runtime_glob_not_hardcoded() -> None:
    """F-13.1 manager finding: brief authority claim '19 schema' diverged
    from filesystem 18. The skill description and body MUST avoid
    hardcoded counts; runtime glob enumerate is the contract.

    Schema-first override (lesson 31+34): brief authority claim drift →
    schema authority kazanır, recovery in worker."""
    fm = _parse_frontmatter(SKILL_PATH)
    body = _skill_body()
    desc = fm["description"]

    # Description MUST NOT contain "19 schema" (the brief drift)
    # nor "18 schema" (would lock to current count)
    assert not re.search(r"\b1[89]\s+schema", desc, re.IGNORECASE), (
        f"description carries hardcoded schema count (F-13.1 finding): {desc!r}"
    )

    # Body MUST mention runtime glob enumerate
    assert re.search(r"glob\s*\(", body), (
        "body must reference glob() enumerate (runtime, not hardcoded count)"
    )

    # Filesystem schemas/*.schema.json count is what the skill discovers
    # at runtime; we assert >= 18 (current state) but NOT a specific
    # number, and the assertion is on the filesystem, NOT the skill.
    schema_files = sorted(SCHEMAS.glob("*.schema.json"))
    assert len(schema_files) >= 18, (
        f"unexpectedly low schemas count: {len(schema_files)} "
        f"(filesystem authority for the audit)"
    )


# ---------------------------------------------------------------------------
# Test 5 — cross-sheet-invariants `rules` key (NOT "invariants")
# ---------------------------------------------------------------------------

def test_cross_sheet_invariants_rules_key_compile() -> None:
    """cross-sheet-invariants instance document uses top-level key `rules`
    per S3.5 instance pivot. Memory drift naturally produces the typo
    `invariants`. The skill body MUST exercise the `rules` key explicitly.

    Schema-first override (lesson 31+34): document key authority wins
    over memory authority."""
    csi_path = SCHEMAS / "cross-sheet-invariants.json"
    csi = json.loads(csi_path.read_text(encoding="utf-8"))

    # Authority document: top-level key MUST be "rules"
    assert "rules" in csi, "cross-sheet-invariants.json missing 'rules' key"
    assert "invariants" not in csi, (
        "cross-sheet-invariants.json carries 'invariants' top-level key — "
        "schema drift, lesson 31+34 catch"
    )

    rules = csi["rules"]
    assert isinstance(rules, list)
    # ≥20 rule registry per spec §7 (additive growth K-02 paterni:
    # v1.5-Phase-2 Tier 1 added F-16..F-22 → 20 → 27). Per-rule
    # F-NN ↔ validate_invariants.py parity is enforced separately by
    # tests/schemas/test_cross_sheet_invariants_sync.py (bidirectional +
    # KNOWN_SCHEMA_ONLY known-deferred).
    assert len(rules) >= 20, (
        f"rules array must have ≥20 entries (F-01..F-15 + D-01..D-03 + "
        f"M-01..M-02 baseline; F-16..F-22 additive K-02); got {len(rules)}"
    )

    # Per-rule structural validate: id + severity + category + rule
    for entry in rules:
        for required_key in ("id", "severity", "category", "rule"):
            assert required_key in entry, (
                f"rule {entry.get('id', '?')} missing required key "
                f"{required_key!r}"
            )

    # Body must exercise the `rules` key (not "invariants") explicitly
    body = _skill_body()
    assert re.search(r'"rules"|`rules`', body), (
        "body must reference `rules` key (S3.5 instance pivot authority)"
    )


# ---------------------------------------------------------------------------
# Test 6 — SKILL.md frontmatter Draft7 compliance (40+ skill files)
# ---------------------------------------------------------------------------

def test_skill_frontmatter_compliance_runtime_count() -> None:
    """Every skills/**/SKILL.md frontmatter must Draft7-validate against
    skill-frontmatter.schema.json. Count is RUNTIME (glob), not hardcoded."""
    skill_files = sorted((REPO_ROOT / "skills").rglob("SKILL.md"))
    assert len(skill_files) >= 40, (
        f"unexpectedly low SKILL.md count: {len(skill_files)} "
        f"(filesystem authority for the audit)"
    )

    schema = json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )
    validator = Draft7Validator(schema)

    failures = []
    for sp in skill_files:
        text = sp.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            failures.append(f"{sp}: no frontmatter block")
            continue
        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            failures.append(f"{sp}: YAML parse error: {exc}")
            continue
        errors = sorted(
            validator.iter_errors(fm), key=lambda e: list(e.absolute_path)
        )
        if errors:
            for e in errors:
                loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
                failures.append(f"{sp.relative_to(REPO_ROOT)}: {loc}: {e.message}")

    assert not failures, (
        "skill-frontmatter Draft7 violations:\n" + "\n".join(failures[:10])
    )


# ---------------------------------------------------------------------------
# Test 7 — DURUR #3 strict + FAIL → exit 1 documented
# ---------------------------------------------------------------------------

def test_durur_3_strict_fail_exit_1_documented() -> None:
    """DURUR #3: strict=true AND any FAIL → exit 1; non-strict → AMBER.
    Body must surface this as DURUR #3 with both branches."""
    body = _skill_body()
    assert "DURUR #3" in body, "DURUR #3 sentinel missing"
    assert re.search(r"DURUR #3.{0,400}strict", body, re.DOTALL | re.IGNORECASE), (
        "DURUR #3 must mention 'strict'"
    )
    assert re.search(r"DURUR #3.{0,500}exit\s*1", body, re.DOTALL | re.IGNORECASE), (
        "DURUR #3 must declare exit 1 on strict+FAIL"
    )
    assert re.search(r"DURUR #3.{0,800}AMBER", body, re.DOTALL), (
        "DURUR #3 must declare AMBER on non-strict path"
    )


# ---------------------------------------------------------------------------
# Test 8 — DURUR #1 + #2 + non-strict AMBER documented
# ---------------------------------------------------------------------------

def test_durur_sentinels_present() -> None:
    """All 3 DURUR sentinels (#1 jsonschema smoke, #2 schemas/ missing,
    #3 strict+fail) must appear in body."""
    body = _skill_body()
    for n in (1, 2, 3):
        assert f"DURUR #{n}" in body, f"DURUR #{n} sentinel missing"

    # DURUR #1: jsonschema ImportError → AMBER + exit 1
    assert re.search(r"DURUR #1.{0,400}jsonschema|DURUR #1.{0,400}ImportError",
                     body, re.DOTALL | re.IGNORECASE), (
        "DURUR #1 must mention jsonschema/ImportError"
    )

    # DURUR #2: schemas/ dir missing → exit 1
    assert re.search(r"DURUR #2.{0,400}(?:schemas|directory|missing)",
                     body, re.DOTALL | re.IGNORECASE), (
        "DURUR #2 must mention schemas/ directory missing"
    )


# ---------------------------------------------------------------------------
# Test 9 — master.xlsx WRITE YOK invariant
# ---------------------------------------------------------------------------

def test_master_xlsx_no_write_invariant() -> None:
    """Phase 9/12 reporting+governance no-write paterni reuse: production
    prose MUST NOT contain `transaction.append(`, `transaction.update(`,
    `transaction.delete(`, `wb.save(` call sites."""
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
            f"Forbidden write call site {token_re!r} found in SKILL body at "
            f"offset {m.start() if m else -1}: master.xlsx WRITE YASAK"
        )

    assert re.search(r"READ-ONLY|read-only|read.only", body, re.IGNORECASE), (
        "skill body must declare READ-ONLY discipline"
    )

    fm = _parse_frontmatter(SKILL_PATH)
    for o in fm["outputs"]:
        assert "master.xlsx" not in o


# ---------------------------------------------------------------------------
# Test 10 — events.jsonl audit kind compliance (schema-first override)
# ---------------------------------------------------------------------------

def test_events_audit_kind_schema_first_override() -> None:
    """Schema-first override (lesson 7+23+31+34): events.schema.json
    declares event_kind=audit allOf rule: audit_action + audit_target +
    actor required triple. event_type (WORK-only enum) is NOT used here."""
    body = _skill_body()

    # Audit kind triple present
    assert re.search(r"event_kind\s*=?\s*[\"']?audit", body), (
        "body must declare event_kind=audit"
    )
    assert re.search(r'audit_action\s*=?\s*[\"]?accessed', body), (
        "body must declare audit_action=accessed"
    )
    assert re.search(r'audit_target\s*=?\s*[\"]?schemas:bulk-validate', body), (
        "body must declare audit_target=schemas:bulk-validate"
    )
    assert re.search(r'actor\s*=?\s*[\"]?agent:schema-validate', body), (
        "body must declare actor=agent:schema-validate"
    )

    # Authority schema cross-check: audit allOf rule
    events_schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text("utf-8")
    )
    audit_allof_branches = [
        b for b in events_schema["allOf"]
        if b.get("if", {}).get("properties", {}).get("event_kind", {}).get("const") == "audit"
    ]
    assert audit_allof_branches, "events.schema audit allOf branch missing"
    audit_required = audit_allof_branches[0]["then"]["required"]
    assert set(audit_required) == {"audit_action", "audit_target", "actor"}, (
        f"audit allOf required triple drift: {audit_required}"
    )


# ---------------------------------------------------------------------------
# Test 11 — Plugin-agnostic + .mcp.json byte unchanged
# ---------------------------------------------------------------------------

def test_plugin_agnostic_mcp_tools_empty() -> None:
    """F-16 plugin agnostik MCP boundary invariant: schema-validate is
    pure stdlib, mcp_tools required + optional empty arrays. .mcp.json
    untouched (byte hash identity assertion is out of scope here, but
    the contract is enforced via mcp_tools=[])."""
    fm = _parse_frontmatter(SKILL_PATH)
    mcp = fm["mcp_tools"]
    assert mcp.get("required", []) == [], (
        f"mcp_tools.required must be empty (F-16): {mcp.get('required')}"
    )
    assert mcp.get("optional", []) == [], (
        f"mcp_tools.optional must be empty (F-16): {mcp.get('optional')}"
    )

    # Sanity: .mcp.json exists and is non-empty
    assert MCP_JSON.exists()
    assert MCP_JSON.stat().st_size > 0


# ---------------------------------------------------------------------------
# Test 12 — Foundational Principles 3-layer enforce
# ---------------------------------------------------------------------------

def test_foundational_principles_three_layer() -> None:
    """Body must reference all 3 Foundational Principles explicitly:
    truth-verifiable + profile-aware (5-enum) + AI suistimal yasağı."""
    body = _skill_body()
    assert re.search(r"Truth.verifiable|truth.verifiable", body), (
        "body must reference Truth-verifiable principle"
    )
    assert re.search(r"Profile.aware|profile.aware", body), (
        "body must reference Profile-aware principle"
    )
    assert re.search(r"5.enum|5-value", body, re.IGNORECASE), (
        "body must reference 5-enum profile (solo/agency/inhouse/enterprise/pilot)"
    )
    assert re.search(r"suistimal|AI suistimal", body, re.IGNORECASE), (
        "body must reference AI suistimal yasağı"
    )


# ---------------------------------------------------------------------------
# Test 13 — v1.8 Phase 4: sf-mcp-tool-mapping.schema.json picked up by sweep
# ---------------------------------------------------------------------------

def test_sf_mcp_tool_mapping_in_sweep() -> None:
    """v1.8 Phase 4 verification (sf-mcp-tool-mapping additive Phase 1):
    (a) the schema file exists under schemas/ so the runtime glob picks
        it up automatically (no enumeration code change required —
        F-13.1 schema-first override);
    (b) it Draft7-validates as a valid meta-schema;
    (c) the sample instance at templates/sf-mcp/use-case-example.json
        validates against it cleanly (positive instance gate).
    """
    sf_mcp_schema_path = SCHEMAS / "sf-mcp-tool-mapping.schema.json"
    assert sf_mcp_schema_path.exists(), (
        f"v1.8 Phase 1 schema missing: {sf_mcp_schema_path}"
    )

    # The runtime glob would discover it.
    discovered = sorted(SCHEMAS.glob("*.schema.json"))
    assert sf_mcp_schema_path in discovered, (
        "sf-mcp-tool-mapping.schema.json not in glob() enumerate set"
    )

    # (a)/(b): Draft7 meta-schema sanity.
    sf_schema = json.loads(sf_mcp_schema_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(sf_schema)  # raises SchemaError on bad meta

    # (c): positive-instance gate.
    instance_path = REPO_ROOT / "templates" / "sf-mcp" / "use-case-example.json"
    assert instance_path.exists(), (
        f"Phase 1 sample instance missing: {instance_path}"
    )
    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft7Validator(sf_schema).iter_errors(instance),
        key=lambda e: list(e.absolute_path),
    )
    assert not errors, (
        "templates/sf-mcp/use-case-example.json fails its own schema: "
        + "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: "
            f"{e.message}"
            for e in errors
        )
    )


# ---------------------------------------------------------------------------
# Test 14 — v1.8 Phase 4: F-23 declared in cross-sheet-invariants.json
# ---------------------------------------------------------------------------

def test_f23_invariant_registered_in_cross_sheet_json() -> None:
    """v1.8 Phase 4: cross-sheet-invariants.json carries F-23 entry with
    the canonical SF MCP cross-sheet rule body + HIGH severity (RED
    verdict on FAIL per the severity_to_verdict_map at the document
    root). schema-first override discipline lock — schema authority is
    the SoT for the rule registry."""
    csi = json.loads(
        (SCHEMAS / "cross-sheet-invariants.json").read_text(encoding="utf-8")
    )
    rules_by_id = {r["id"]: r for r in csi["rules"]}
    assert "F-23" in rules_by_id, (
        "F-23 (v1.8 Phase 4 SF MCP cross-sheet) missing from registry"
    )
    f23 = rules_by_id["F-23"]
    assert f23["severity"] == "HIGH"
    assert f23["category"] == "csr_mcp"
    rule_text = f23["rule"]
    assert "sf-crawl-orchestrator" in rule_text
    assert "mcp-tool-registry" in rule_text
    assert "sf" in rule_text.lower()
