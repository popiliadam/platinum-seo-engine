"""tests/skills/test_mark_done.py — mark-done skill (Phase 12 W-G5).

Coverage (15 tests):
  1. Frontmatter Draft7 schema validity (skill-frontmatter.schema.json) +
     status=wip + category=meta + 8-field required.
  2. Inputs/Outputs structure — 2 inputs (task_id string + completion_evidence
     object); object key encoding via description (W-F3 D1 paterni).
  3. natural_language ≥30-char block + ≥30-char per phrase (lesson 8 sentinel).
  4. DURUR #1 — task_id not found in master_task (Principle 3 anti-fab).
  5. DURUR #2 — task already DONE idempotent fail (no 2x event write).
  6. DURUR #3 — allowed_writers gate fail (4-entity enumerate sentinel).
  7. DURUR #4 — completion_evidence missing AMBER + escalate.
  8. DURUR #5 — protected_columns YASAK touch defensive (7-col enumerate).
  9. allowed_writers 4-entity sentinel + done_protocol writer_scope.
  10. protected_columns 7-col enumeration sentinel (no write payload leak).
  11. done_protocol cross-sheet invariant compliance (F-02 + F-05; jq
      introspect cross-sheet-invariants.json + body coverage).
  12. completed_work F-12 6-col required_columns enforcement.
  13. master_task ONGOING/TODO → DONE transition + statusEnum compliance
      (ONGOING NOT in_progress; brief-drift schema-first override).
  14. events.jsonl event_type schema-first override — F-8 closed-10 enum
      compliance (event_type=manual or quickwin_applied; task_completed
      NEVER emitted, brief drift detected).
  15. Plugin-agnostik (no slug hardcode) + Foundational Principles 3-layer
      enforcement (truth-verifiable + profile-aware 5-enum + AI suistimal).

Discipline:
  - Every assertion derives from a schema authority (schemas/*) or
    rules/content-*.md cross-link.
  - Plugin-agnostik invariant: no project slug hardcoded in skill body.
  - WRITE contract verified by inspecting transaction.* call-site mentions.
  - Schema-first override (lesson 7+23+31): brief drift → worker authority,
    asserted via test_events_jsonl_schema_first_override and
    test_status_enum_schema_first_override.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "meta" / "mark-done" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"
SKILL_FRONTMATTER_SCHEMA = SCHEMAS / "skill-frontmatter.schema.json"
MASTER_EXCEL_SCHEMA = SCHEMAS / "master-excel.schema.json"
CROSS_SHEET_INVARIANTS = SCHEMAS / "cross-sheet-invariants.json"
EVENTS_SCHEMA = SCHEMAS / "events.schema.json"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _parse_frontmatter() -> dict:
    text = _skill_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise ValueError(f"No YAML frontmatter in {SKILL_PATH}")
    return yaml.safe_load(m.group(1))


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter Draft7 schema validity + 8-field required + status/category
# ---------------------------------------------------------------------------

def test_frontmatter_required_fields_and_draft7_validity() -> None:
    """Frontmatter must declare the 8 required fields and validate against
    skill-frontmatter.schema.json (Draft7); status=wip, category=meta."""
    fm = _parse_frontmatter()
    required = ["name", "description", "version", "status", "category",
                "inputs", "outputs", "triggers"]
    for field in required:
        assert field in fm, f"Missing required field: {field}"

    schema = json.loads(SKILL_FRONTMATTER_SCHEMA.read_text("utf-8"))
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    )

    assert fm["name"] == "mark-done"
    assert fm["category"] == "meta"
    assert fm["status"] == "wip"
    assert fm["triggers"]["manual"] == ["/pseo-mark-done"]
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True
    assert fm["autonomy"]["requires_approval"] is False


# ---------------------------------------------------------------------------
# Test 2 — Inputs (2 inputs: task_id string + completion_evidence object) + outputs
# ---------------------------------------------------------------------------

def test_inputs_structure_2_inputs_and_object_encoding() -> None:
    """Inputs declares exactly 2 keys: task_id (string) + completion_evidence
    (object). Object key enumeration is encoded in description per W-F3 D1
    paterni (additionalProperties=false + 4-field whitelist)."""
    fm = _parse_frontmatter()
    inputs = fm["inputs"]
    assert isinstance(inputs, dict)
    assert set(inputs.keys()) == {"task_id", "completion_evidence"}, (
        f"Expected 2 inputs (task_id + completion_evidence), got {list(inputs.keys())}"
    )

    # task_id contract
    assert inputs["task_id"]["type"] == "string"
    assert inputs["task_id"]["required"] is True
    assert "T-NNNN" in inputs["task_id"]["description"] or \
           "primary key" in inputs["task_id"]["description"].lower()

    # completion_evidence contract — object type, expected keys in description
    assert inputs["completion_evidence"]["type"] == "object"
    assert inputs["completion_evidence"]["required"] is True
    desc = inputs["completion_evidence"]["description"]
    assert "event_id" in desc, (
        f"completion_evidence.description must enumerate event_id key, got: {desc}"
    )
    assert "output_path" in desc, (
        f"completion_evidence.description must enumerate output_path key, got: {desc}"
    )
    assert "manual_note" in desc, (
        f"completion_evidence.description must enumerate manual_note key (optional), "
        f"got: {desc}"
    )

    # Outputs are artifact ref strings (lesson 7+23 schema-first)
    outputs = fm["outputs"]
    assert isinstance(outputs, list)
    outputs_str = " ".join(outputs)
    assert "_state/events.jsonl" in outputs_str, "events.jsonl output missing"
    assert "outputs/mark-done" in outputs_str, "mark-done report output missing"


# ---------------------------------------------------------------------------
# Test 3 — natural_language sentinel quality (≥30-char block + per-phrase)
# ---------------------------------------------------------------------------

def test_natural_language_sentinel_quality() -> None:
    """natural_language is a string per skill-frontmatter schema; total
    >=30 chars; each comma-delimited phrase >=30 chars (lesson 8)."""
    fm = _parse_frontmatter()
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str), (
        f"natural_language must be string per schema, got {type(nl).__name__}"
    )
    assert len(nl) >= 30, f"natural_language total <30 chars: {len(nl)}"

    phrases = [
        p.strip().strip('"').strip("'")
        for p in nl.replace("\n", " ").split(",")
        if p.strip()
    ]
    assert len(phrases) >= 5, f"Expected >=5 trigger phrases, got {len(phrases)}"
    for phrase in phrases:
        assert len(phrase) >= 30, (
            f"natural_language phrase <30 chars (lesson 8 sentinel): "
            f"{phrase!r} len={len(phrase)}"
        )


# ---------------------------------------------------------------------------
# Test 4 — DURUR #1: task_id not found in master_task REJECT
# ---------------------------------------------------------------------------

def test_durur_1_task_id_not_found_reject() -> None:
    """DURUR #1: master_task lookup miss → REJECT (Principle 3 anti-fab,
    hayali task_id mark-done YASAK; no auto-create master_task)."""
    text = _skill_text()
    assert "DURUR #1" in text, "DURUR #1 marker missing"
    assert "task_id" in text and "not found" in text.lower(), (
        "DURUR #1 task_id-not-found rejection not documented"
    )
    # event_kind=audit emit on reject
    assert "event_kind=audit" in text or "audit_action" in text, (
        "DURUR #1 must emit event_kind=audit row"
    )
    # never auto-create master_task row
    assert "auto-create" in text.lower() or "NEVER" in text, (
        "DURUR #1 must forbid auto-creating master_task row"
    )


# ---------------------------------------------------------------------------
# Test 5 — DURUR #2: task already DONE idempotent fail
# ---------------------------------------------------------------------------

def test_durur_2_already_done_idempotent_fail() -> None:
    """DURUR #2: status already DONE → idempotent fail (no 2x event write,
    no 2x completed_work row). Idempotency hash check is secondary defense."""
    text = _skill_text()
    assert "DURUR #2" in text, "DURUR #2 marker missing"
    assert "DONE" in text, "DURUR #2 DONE state reference missing"
    assert "idempotent" in text.lower(), "DURUR #2 idempotent fail keyword missing"
    assert "2x" in text or "twice" in text.lower(), (
        "DURUR #2 must explicitly forbid 2x event write"
    )
    # Idempotency hash check
    assert "evidence_hash" in text, "evidence_hash sentinel missing"
    assert "sha256" in text.lower(), "sha256 idempotency hash missing"


# ---------------------------------------------------------------------------
# Test 6 — DURUR #3: allowed_writers gate fail (4-entity enumerate)
# ---------------------------------------------------------------------------

def test_durur_3_allowed_writers_gate_fail() -> None:
    """DURUR #3: worker writer_id NOT in master_task.allowed_writers 4-entity
    list → ABORT pre-write. transaction.py raises WriterScopeError."""
    text = _skill_text()
    assert "DURUR #3" in text, "DURUR #3 marker missing"
    # 4-entity sentinel
    for entity in ["human", "dashboard_refresh", "done_protocol", "master_task_sync"]:
        assert entity in text, (
            f"allowed_writers 4-entity enumerate missing entity: {entity}"
        )
    assert "WriterScopeError" in text, "transaction.py WriterScopeError missing"
    assert "done_protocol" in text, "writer_id=done_protocol missing"


# ---------------------------------------------------------------------------
# Test 7 — DURUR #4: completion_evidence missing AMBER
# ---------------------------------------------------------------------------

def test_durur_4_completion_evidence_missing_amber() -> None:
    """DURUR #4: completion_evidence required keys missing → AMBER + escalate
    (Süleyman manual confirm). event_id not findable, output_path doesn't exist."""
    text = _skill_text()
    assert "DURUR #4" in text, "DURUR #4 marker missing"
    assert "AMBER" in text, "DURUR #4 AMBER severity missing"
    assert "manual confirm" in text.lower() or "Süleyman" in text, (
        "DURUR #4 manual confirm escalation missing"
    )
    # P1 layered defense
    assert "Layer 1" in text and "Layer 2" in text, (
        "Principle 1 layered defense (Layer 1 + Layer 2) missing"
    )
    assert "exists" in text.lower() or "Path.exists" in text, (
        "output_path file existence check missing (P1 Layer 2)"
    )


# ---------------------------------------------------------------------------
# Test 8 — DURUR #5: protected_columns YASAK touch defensive (7-col)
# ---------------------------------------------------------------------------

def test_durur_5_protected_columns_yasak_touch() -> None:
    """DURUR #5: skill code MUST NOT touch master_task protected_columns
    7-col. transaction.py guards via WriterScopeError; skill body adds
    explicit defensive contract + static grep sentinel."""
    text = _skill_text()
    assert "DURUR #5" in text, "DURUR #5 marker missing"
    # 7-col enumerate sentinel (master_task.protected_columns)
    protected_cols = ["task", "category", "priority", "impact",
                      "duration_est_min", "assignee", "note"]
    for col in protected_cols:
        assert col in text, (
            f"protected_columns 7-col enumerate missing column: {col}"
        )
    assert "YASAK" in text, "YASAK touch contract missing"
    assert "ben bunu yapmayacağım" in text or "defensive" in text.lower(), (
        "Defensive contract sentinel missing"
    )


# ---------------------------------------------------------------------------
# Test 9 — allowed_writers 4-entity sentinel + done_protocol writer_scope
# ---------------------------------------------------------------------------

def test_allowed_writers_sentinel_and_writer_scope() -> None:
    """master_task.allowed_writers 4-entity list documented + done_protocol
    writer_scope (J/L/Q/R/S only, transition-to-DONE rows only)."""
    text = _skill_text()
    # Cross-reference schema authority directly
    schema = json.loads(MASTER_EXCEL_SCHEMA.read_text("utf-8"))
    schema_writers = schema["sheets"]["master_task"]["allowed_writers"]
    assert schema_writers == ["human", "dashboard_refresh", "done_protocol",
                              "master_task_sync"], (
        f"Schema authority drift: master_task.allowed_writers changed: {schema_writers}"
    )
    for entity in schema_writers:
        assert entity in text, f"Skill body missing allowed_writers entity: {entity}"
    # done_protocol writer_scope columns J/L/Q/R/S
    for col_letter in ["J", "L", "Q", "R", "S"]:
        assert col_letter in text, (
            f"done_protocol writer_scope column letter missing: {col_letter}"
        )
    # Schema columns by name
    for col_name in ["status", "done_date", "effort_actual_min",
                     "metric_impact_json", "work_log_ref"]:
        assert col_name in text, (
            f"done_protocol writer_scope column name missing: {col_name}"
        )


# ---------------------------------------------------------------------------
# Test 10 — protected_columns 7-col enumeration: only in YASAK block
# ---------------------------------------------------------------------------

def test_protected_columns_only_in_yasak_block() -> None:
    """Cross-reference schema's protected_columns 7-col list with skill body.
    All 7 column names must appear (Test 8 already enforces). Additionally,
    schema authority must remain at exactly 7 entries (drift sentinel)."""
    schema = json.loads(MASTER_EXCEL_SCHEMA.read_text("utf-8"))
    protected = schema["sheets"]["master_task"]["protected_columns"]
    expected = ["task", "category", "priority", "impact",
                "duration_est_min", "assignee", "note"]
    assert protected == expected, (
        f"Schema authority drift: master_task.protected_columns changed: {protected}"
    )
    text = _skill_text()
    for col in expected:
        assert col in text, f"Skill body missing protected_columns entry: {col}"
    # The skill must explicitly reference the 7-col count
    assert "7" in text, "protected_columns count (7) sentinel missing"


# ---------------------------------------------------------------------------
# Test 11 — done_protocol cross-sheet invariant compliance (F-02 + F-05)
# ---------------------------------------------------------------------------

def test_done_protocol_cross_sheet_invariant_compliance() -> None:
    """F-02 (master_task DONE count == dashboard.R48) + F-05 (completed_work
    .task_id ⊆ master_task WHERE status=DONE) — mark-done is the enforcement
    point. Both invariant IDs must be referenced in skill body."""
    invariants = json.loads(CROSS_SHEET_INVARIANTS.read_text("utf-8"))
    rule_ids = {r["id"] for r in invariants["rules"]}
    # Authority: F-02 + F-05 must exist in invariants
    assert "F-02" in rule_ids, "F-02 invariant missing in cross-sheet-invariants.json"
    assert "F-05" in rule_ids, "F-05 invariant missing in cross-sheet-invariants.json"
    # F-05 rule text targets completed_work + master_task DONE
    f05 = next(r for r in invariants["rules"] if r["id"] == "F-05")
    assert "completed_work" in f05["rule"]
    assert "master_task" in f05["rule"]
    assert "DONE" in f05["rule"]
    # Skill body coverage
    text = _skill_text()
    assert "F-02" in text, "F-02 cross-sheet invariant reference missing in skill"
    assert "F-05" in text, "F-05 cross-sheet invariant reference missing in skill"
    assert "done_protocol" in text, "done_protocol writer identity reference missing"


# ---------------------------------------------------------------------------
# Test 12 — completed_work F-12 6-col required_columns enforcement
# ---------------------------------------------------------------------------

def test_completed_work_required_columns_6() -> None:
    """master.xlsx[completed_work] required_columns = 6: id, task_or_content,
    url, date, category, note. All 6 must appear in skill body where the
    append payload is documented."""
    schema = json.loads(MASTER_EXCEL_SCHEMA.read_text("utf-8"))
    cw_cols = [c["name"] for c in
               schema["sheets"]["completed_work"]["required_columns"]]
    expected = ["id", "task_or_content", "url", "date", "category", "note"]
    assert cw_cols == expected, (
        f"Schema authority drift: completed_work required_columns changed: {cw_cols}"
    )
    text = _skill_text()
    for col in expected:
        assert col in text, (
            f"Skill body missing completed_work column: {col}"
        )
    # transaction.append call-site reference
    assert "transaction.append" in text, (
        "transaction.append('completed_work', ...) call-site missing"
    )


# ---------------------------------------------------------------------------
# Test 13 — master_task ONGOING/TODO → DONE transition (statusEnum compliance)
# ---------------------------------------------------------------------------

def test_master_task_status_enum_schema_first_override() -> None:
    """master-excel.schema.json[definitions/statusEnum] declares 7-value
    [TODO, ONGOING, EXISTS, DONE, BLOCKED, DEFERRED, CANCELED]. Brief used
    'in_progress' but schema authority is 'ONGOING'. Skill must use ONGOING."""
    schema = json.loads(MASTER_EXCEL_SCHEMA.read_text("utf-8"))
    status_enum = schema["definitions"]["statusEnum"]["enum"]
    assert "ONGOING" in status_enum, (
        "Schema authority: ONGOING must be in statusEnum"
    )
    assert "in_progress" not in status_enum, (
        "Schema authority: in_progress is NOT in statusEnum (brief drift)"
    )
    text = _skill_text()
    # ONGOING/TODO accept transition language
    assert "ONGOING" in text, "ONGOING (schema authority) missing in skill body"
    assert "TODO" in text, "TODO prior-state acceptance missing"
    assert "DONE" in text, "DONE target state missing"
    # transaction.update for status DONE
    assert "transaction.update" in text, (
        "transaction.update('master_task', ...) call-site missing"
    )
    assert "status" in text and "done_date" in text, (
        "status + done_date column updates missing"
    )


# ---------------------------------------------------------------------------
# Test 14 — events.jsonl event_type schema-first override (F-8 closed-10)
# ---------------------------------------------------------------------------

def test_events_jsonl_event_type_schema_first_override() -> None:
    """events.schema.json declares event_type as closed 10-value enum (F-8
    WORK-only). Brief suggested 'task_completed' but it's NOT in the enum.
    Skill must branch event_type=quickwin_applied (if primary_source=quickwin
    + cluster+before+after) OR event_type=manual (default fallback W-G1
    paterni reuse). 'task_completed' MUST NEVER be emitted."""
    events_schema = json.loads(EVENTS_SCHEMA.read_text("utf-8"))
    # Find event_type enum definition (look in properties)
    schema_text = EVENTS_SCHEMA.read_text("utf-8")
    # Validate the closed 10-value enum is present in events.schema.json source
    expected_enum_values = ["content_new", "content_revise", "content_remove",
                            "tech_fix", "quickwin_applied", "pillar_launch",
                            "schema_fix", "redirect_deployed",
                            "backlink_outreach", "manual"]
    for val in expected_enum_values:
        assert val in schema_text, (
            f"event_type enum value missing in events.schema.json: {val}"
        )
    # task_completed MUST NOT be in enum (drift detection)
    # Look for it as an enum value (heuristic — appears as quoted token in enum
    # array context). If 'task_completed' appears anywhere as an enum literal
    # in events.schema.json, our override premise is wrong.
    # We tolerate prose mentions only inside descriptions; check it's not a
    # standalone enum entry by scanning JSON-loaded structure.
    def _walk_for_enum(obj, hits):
        if isinstance(obj, dict):
            if "enum" in obj and isinstance(obj["enum"], list):
                if "task_completed" in obj["enum"]:
                    hits.append(obj["enum"])
            for v in obj.values():
                _walk_for_enum(v, hits)
        elif isinstance(obj, list):
            for v in obj:
                _walk_for_enum(v, hits)
    hits = []
    _walk_for_enum(events_schema, hits)
    assert not hits, (
        f"task_completed unexpectedly present as enum value: {hits} — "
        "schema-first override premise broken; brief drift may now be valid"
    )

    text = _skill_text()
    # Skill must reference both branch values
    assert "manual" in text, "event_type=manual fallback missing"
    assert "quickwin_applied" in text, "event_type=quickwin_applied branch missing"
    # task_completed is brief drift; skill must explicitly reject it
    assert "task_completed" in text, (
        "Skill must document task_completed as brief drift (override decision)"
    )
    # The rejection language must be present
    assert ("NOT in" in text or "NEVER" in text or "not be emitted" in text.lower()
            or "never emitted" in text.lower() or "never emitted" in text.lower()
            or "never be emitted" in text.lower()), (
        "Skill must explicitly state task_completed is NEVER emitted"
    )
    # F-8 + lesson 7+23+31 references
    assert "F-8" in text, "F-8 enum invariant reference missing"
    assert "lesson 7" in text.lower() or "lesson 7+23" in text.lower(), (
        "lesson 7+23 worker schema-first override authority reference missing"
    )
    # event_kind=work
    assert "event_kind" in text and "work" in text, (
        "event_kind=work declaration missing"
    )


# ---------------------------------------------------------------------------
# Test 15 — Plugin-agnostik + Foundational Principles 3-layer + forbidden tokens
# ---------------------------------------------------------------------------

def test_plugin_agnostic_and_foundational_principles_and_forbidden_tokens() -> None:
    """Plugin-agnostik (no slug hardcode), Foundational Principles 3-layer
    (truth-verifiable + profile-aware 5-enum + AI suistimal), forbidden
    tokens absent (lesson 8/Phase 7 anti-pattern + slug leakage)."""
    text = _skill_text()
    # Plugin-agnostik: no slug hardcode
    forbidden_slugs = ["dentnotion", "vento", "eykom", "bigcattr", "calitte",
                       "lastiksa", "noraninsaat", "adstark"]
    for slug in forbidden_slugs:
        assert slug not in text, (
            f"Plugin agnostik violation (slug hardcode): {slug!r}"
        )
    # Legacy/stale frontmatter field names (drift sentinels)
    legacy = ["estimated_credits_per_call", "estimated_credits_per_url",
              "metric_name"]
    for token in legacy:
        assert token not in text, f"Forbidden token leaked: {token!r}"

    # Foundational Principles 3-layer
    assert "Principle 1" in text, "Principle 1 (truth-verifiable) header missing"
    assert "Principle 2" in text, "Principle 2 (profile-aware) header missing"
    assert "Principle 3" in text, "Principle 3 (AI suistimal) header missing"

    # P1 truth-verifiable: completion_evidence event_id reference + output_path
    # file existence check
    assert "Truth-Verifiable" in text or "truth-verifiable" in text.lower()
    assert "event_id" in text and "output_path" in text
    # P2 profile-aware 5-enum awareness
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    found = sum(1 for p in profile_enum if p in text)
    assert found >= 4, (
        f"Profile enum 5-value coverage too low: {found}/5; expected >=4"
    )
    # P3 AI suistimal anti-fabrication + idempotency 2x
    assert "anti-fabrication" in text.lower() or "hayali" in text.lower(), (
        "P3 anti-fabrication/hayali sentinel missing"
    )
    assert "Idempotency" in text or "idempotent" in text.lower()

    # .mcp.json byte unchanged contract — skill mcp_tools required[] empty
    fm = _parse_frontmatter()
    assert fm["mcp_tools"]["required"] == [], (
        "mcp_tools.required must be empty (.mcp.json byte-unchanged contract)"
    )
    assert fm["mcp_tools"]["optional"] == [], (
        "mcp_tools.optional must be empty (.mcp.json byte-unchanged contract)"
    )
