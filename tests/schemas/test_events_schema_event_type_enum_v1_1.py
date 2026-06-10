"""tests/schemas/test_events_schema_event_type_enum_v1_1.py — event_type
enum additive bump 10→12 (H-E v1.6-Phase-2 Tier 1).

Lock the additive contract for event_type enum extension:
  - 10 prior canonical values remain accepted (no regression)
  - 2 new ``skill_<name>`` canonical values accepted: skill_content_remediation
    + skill_whats_next (replace legacy DSL workaround
    ``event_type=manual + note=[skill=X]``)
  - allOf branch (line 322-328) enum extension: note required for new
    canonical entries (data quality preserved)
  - description cite consistent ("12 closed event_type subtypes")
  - schema_version const "1.0" UNCHANGED (operation enum Wave 3 staging
    additive precedent — schema_version bump not required for additive
    enum extension; ADR-018 paterni reuse)

Brief premise revize per Lesson 38 v2 #46-52 (Süleyman onay 2026-05-07):
  - "16 skill DSL workaround" iddiası runtime'da false (47 SKILL.md total)
  - 2 skill DSL workaround (content-remediation:421 + whats-next:209-227)
  - 2 skill bilinçli semantic-correct (indexing-ping=manual+sub-object F-8
    compliance + monitoring-weekly=audit kind) — workaround DEĞİL
  - schema_version bump iptal (operation enum staging Wave 3 prior art:
    schema_version const "1.0" KAL, sadece enum extension)

Mirror precedent: tests/schemas/test_events_schema_operation.py paterni reuse.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "schemas" / "events.schema.json"

LEGACY_EVENT_TYPES = (
    "content_new",
    "content_revise",
    "content_remove",
    "tech_fix",
    "quickwin_applied",
    "pillar_launch",
    "schema_fix",
    "redirect_deployed",
    "backlink_outreach",
    "manual",
)

CANONICAL_SKILL_EVENT_TYPES = (
    "skill_content_remediation",
    "skill_whats_next",
)

EXPECTED_EVENT_TYPES = LEGACY_EVENT_TYPES + CANONICAL_SKILL_EVENT_TYPES


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _event_type_enum() -> list[str]:
    schema = _load_schema()
    field = schema["properties"]["event_type"]
    return list(field.get("enum", []))


def _work_event(event_type: str, *, note: str | None = "test note") -> dict:
    """Minimal work event template for schema validation. Includes
    task_id (canonical T-NNNN) + url + url_normalized to satisfy
    URL-bearing event_type allOf branches when relevant. note is
    populated by default — pass note=None to test note-required branches."""
    event: dict = {
        "schema_version": "1.0",
        "event_kind": "work",
        "event_id": "test_evt_20260507T120000",
        "timestamp": "2026-05-07T12:00:00.000Z",
        "project_id": "test-project",
        "event_type": event_type,
        "task_id": "T-0042",
        "url": "https://example.com/page",
        "url_normalized": "https://example.com/page",
    }
    if note is not None:
        event["note"] = note
    return event


# --- Test 1: Canonical skill event_types present ---
def test_canonical_skill_event_types_present() -> None:
    """skill_content_remediation + skill_whats_next MUST be in enum
    after additive bump (Tier 1 H-E)."""
    enum = _event_type_enum()
    for canonical in CANONICAL_SKILL_EVENT_TYPES:
        assert canonical in enum, (
            f"event_type enum missing canonical {canonical!r}; got {enum}"
        )


# --- Test 2: Legacy event_types preserved (additive contract) ---
def test_legacy_event_types_preserved() -> None:
    """All 10 legacy values MUST remain accepted (additive bump = no
    breaking removal). ADR-018 paterni reuse."""
    enum = _event_type_enum()
    for legacy in LEGACY_EVENT_TYPES:
        assert legacy in enum, (
            f"event_type enum dropped legacy value {legacy!r}; got {enum}"
        )


# --- Test 3: Total enum count exactly 12 ---
def test_event_type_enum_total_12_values() -> None:
    """Enum is the contract — 10 legacy + 2 canonical = 12, no extras."""
    enum = _event_type_enum()
    assert sorted(enum) == sorted(EXPECTED_EVENT_TYPES), (
        f"event_type enum drift detected; expected {sorted(EXPECTED_EVENT_TYPES)}, "
        f"got {sorted(enum)}"
    )


# --- Test 4: Description cite consistent ("12 closed") ---
def test_event_type_description_cite_consistent() -> None:
    """event_type description MUST cite '12' enum count post-bump
    (cite drift catch — Lesson 38 v2 paterni: rules + schema cite
    sync per Wave 1 K-02 prior art)."""
    schema = _load_schema()
    desc = schema["properties"]["event_type"]["description"]
    assert "12" in desc and "closed" in desc.lower(), (
        f"event_type description must cite '12 closed' enum count; got {desc!r}"
    )


# --- Test 5: Top-level description cite consistent ---
def test_top_level_description_event_type_count_consistent() -> None:
    """Top-level schema description MUST cite '12 closed event_type'
    (Wave 1 K-02 paterni: cite drift surface area Tier 1 same-wave fix)."""
    schema = _load_schema()
    top_desc = schema["description"]
    assert "12 closed event_type" in top_desc, (
        f"Top-level description must cite '12 closed event_type'; "
        f"description preamble: {top_desc[:200]!r}"
    )


# --- Test 6: skill_X canonical entries require note (allOf branch) ---
def test_skill_canonical_event_types_require_note() -> None:
    """allOf branch line 322-328 MUST be extended to require note for
    new canonical skill_X entries (data quality discipline — DSL workaround
    note alanına meta-data sıkıştırıyor; canonical paterni'nde note hala
    önemli structured data taşıyıcı)."""
    schema = _load_schema()
    branches = schema["allOf"]
    note_branch = None
    for br in branches:
        if br.get("then", {}).get("required") == ["note"]:
            then_required = br["then"]["required"]
            if then_required == ["note"]:
                note_branch = br
                break
    assert note_branch is not None, (
        "allOf note-required branch missing (line ~322 'manual + content_remove + "
        "backlink_outreach + redirect_deployed require note')"
    )
    # Verify the branch's if-condition includes new canonical entries
    if_clauses = note_branch["if"]["allOf"]
    enum_clause = next(
        (c for c in if_clauses if "event_type" in c.get("properties", {})),
        None,
    )
    assert enum_clause is not None, "if branch missing event_type clause"
    branch_enum = enum_clause["properties"]["event_type"]["enum"]
    for canonical in CANONICAL_SKILL_EVENT_TYPES:
        assert canonical in branch_enum, (
            f"allOf note-required branch missing canonical {canonical!r}; "
            f"got branch enum {branch_enum}"
        )


# --- Test 7: skill_X canonical with note validates ---
@pytest.mark.parametrize("event_type", CANONICAL_SKILL_EVENT_TYPES)
def test_skill_canonical_with_note_validates(event_type: str) -> None:
    """Full work event with skill_X event_type + note MUST validate
    against schema (additive contract: new canonical accepted in
    work events)."""
    validator = Draft7Validator(_load_schema(), format_checker=FormatChecker())
    event = _work_event(event_type, note="test canonical note")
    errors = list(validator.iter_errors(event))
    # Filter event_type path errors specifically (other unrelated allOf
    # branches may flag URL/before/after constraints — we only assert
    # event_type itself is enum-valid + note required is satisfied)
    et_errors = [
        e for e in errors
        if list(e.absolute_path) == ["event_type"]
        or (e.message.startswith("'note' is a required property"))
    ]
    assert not et_errors, (
        f"event_type={event_type!r} with note rejected: "
        + "; ".join(str(e.message) for e in et_errors)
    )


# --- Test 8: skill_X canonical without note rejects (allOf enforce) ---
@pytest.mark.parametrize("event_type", CANONICAL_SKILL_EVENT_TYPES)
def test_skill_canonical_without_note_rejects(event_type: str) -> None:
    """Work event with skill_X event_type but missing note MUST be
    rejected (allOf branch line 322-328 enforce)."""
    validator = Draft7Validator(_load_schema(), format_checker=FormatChecker())
    event = _work_event(event_type, note=None)
    errors = list(validator.iter_errors(event))
    note_required_errors = [
        e for e in errors
        if "note" in str(e.message) and "required" in str(e.message)
    ]
    assert note_required_errors, (
        f"event_type={event_type!r} without note should be rejected by "
        f"allOf note-required branch; validator returned: "
        + "; ".join(str(e.message) for e in errors[:3])
    )


# --- Test 9: Unknown skill_X event_type rejected (enum-closed) ---
def test_unknown_skill_event_type_rejected() -> None:
    """Arbitrary skill_<unknown> values MUST be rejected — enum is
    closed (additive bump != open enum). Future canonical entries
    require explicit schema bump."""
    validator = Draft7Validator(_load_schema(), format_checker=FormatChecker())
    event = _work_event("skill_unknown_future", note="test")
    errors = list(validator.iter_errors(event))
    et_errors = [e for e in errors if list(e.absolute_path) == ["event_type"]]
    assert et_errors, (
        f"Expected enum rejection for 'skill_unknown_future' on .event_type; "
        f"validator returned: "
        + "; ".join(str(e.message) for e in errors[:3])
    )
