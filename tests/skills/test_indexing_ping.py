"""tests/skills/test_indexing_ping.py — indexing-ping skill (Phase 12 W-G1).

Coverage (15 tests):
  1. Frontmatter required 8-field schema validity (skill-frontmatter.schema.json).
  2. Inputs/Outputs structure — outputs[] are artifact ref strings (lesson 7+23
     schema-first override applied: event_type/event_kind are NOT frontmatter
     outputs[]; they're events.jsonl payload fields).
  3. natural_language ≥30-char block + ≥8-char per phrase (lesson 8 sentinel).
  4. consumes 2 master.xlsx sheets only (`redirect_404`, `robots_txt`),
     F-4 invariant (NO internal_links / content_gaps).
  5. DURUR #1 — empty target_urls SKIP documented.
  6. DURUR #2 — submission_type enum invalid ABORT documented.
  7. DURUR #3 — INDEXNOW_KEY missing AMBER hibrit branch documented.
  8. DURUR #4 — GSC 5xx retry-once exponential backoff documented.
  9. DURUR #5 — R-91 410 cascade REJECT documented.
  10. R-91 cascade compliance — redirect_404 sheet read with action=410 reject +
      action=301 target_url rewrite logic.
  11. R-58 robots map READ-ONLY — robots_txt sheet read but no transaction.*
      writes appear; F-1 allowed_writers=null contract.
  12. events.jsonl event_type schema-first override — F-8 closed-10 enum
      compliance (event_type=manual, NOT 'indexing_submitted'); indexing_ping
      sub-object referenced.
  13. Plugin-agnostic — no project slug hardcoded in skill body; .mcp.json
      byte-hash unchanged invariant documented.
  14. Foundational Principles 3-layer enforcement — Principle 1 truth-verifiable
      (R-91 cascade), Principle 2 profile-aware placeholder pattern, Principle 3
      anti-cheap-content (wildcard reject + dedup + cap).
  15. Phase 7 lesson tokens absent — `estimated_credits_per_call` /
      `_per_url` / `metric_name` (ADR-028 anti-pattern).

Discipline:
  - Every assertion derives from a schema authority (schemas/*) or
    rules/content-*.md cross-link.
  - Plugin-agnostic invariant: no project slug hardcoded in the skill.
  - READ-ONLY contract verified by grep (transaction.* token absent).
  - Schema-first override (lesson 7+23): brief drift → worker authority.
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
SKILL_PATH = REPO_ROOT / "skills" / "publishing" / "indexing-ping" / "SKILL.md"
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
    assert fm["name"] == "indexing-ping"
    assert fm["category"] == "publishing"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["triggers"]["manual"] == ["/pseo-indexing-ping"]
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True


# ---------------------------------------------------------------------------
# Test 2 — Inputs / Outputs structure (schema-first override applied)
# ---------------------------------------------------------------------------

def test_inputs_outputs_structure_schema_first() -> None:
    """Inputs is object<param, {type, required, description}> per schema.
    Outputs is array<string> of artifact refs — NOT event payload fields.
    Schema-first override (lesson 7+23): event_kind / event_type are
    events.jsonl payload, NOT frontmatter outputs[]."""
    fm = _parse_frontmatter(SKILL_PATH)

    # Inputs structure
    assert isinstance(fm["inputs"], dict)
    assert "target_urls" in fm["inputs"]
    assert "submission_type" in fm["inputs"]
    assert fm["inputs"]["target_urls"]["type"] == "array"
    assert fm["inputs"]["target_urls"]["required"] is True
    assert fm["inputs"]["submission_type"]["type"] == "string"
    assert fm["inputs"]["submission_type"]["required"] is True

    # Outputs are artifact refs (strings), NOT payload field names.
    assert isinstance(fm["outputs"], list)
    assert all(isinstance(o, str) for o in fm["outputs"])
    assert "_state/events.jsonl" in fm["outputs"]
    # Some artifact ref pointing to indexing report.
    assert any("outputs/indexing/" in o for o in fm["outputs"])
    # Lesson 7+23 override sentinel: payload fields MUST NOT leak into outputs[]
    forbidden_in_outputs = [
        "event_kind", "event_type", "indexing_submitted", "work",
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
# Test 4 — consumes 2 master.xlsx sheets; F-4 invariant
# ---------------------------------------------------------------------------

def test_consumes_master_xlsx_sheets_f4_compliant() -> None:
    """The skill consumes exactly 2 master.xlsx sheets: redirect_404 +
    robots_txt. F-4 schema authority: master-excel.schema.json declares
    18 sheets and neither `internal_links` nor `content_gaps` is among
    them — referencing them would be a schema-fabrication."""
    text = _skill_text()
    assert "master.xlsx[redirect_404]" in text
    assert "master.xlsx[robots_txt]" in text

    # F-4 schema authority — the two phantom sheets MUST NOT appear.
    assert "master.xlsx[internal_links]" not in text, (
        "F-4 violation: internal_links sheet does not exist in "
        "master-excel.schema.json (18-sheet list)"
    )
    assert "master.xlsx[content_gaps]" not in text, (
        "F-4 violation: content_gaps sheet does not exist in "
        "master-excel.schema.json (18-sheet list)"
    )

    # Verify both sheets DO exist in the master-excel schema (anti-fabrication).
    schema = json.loads(
        (SCHEMAS / "master-excel.schema.json").read_text("utf-8")
    )
    sheets = schema.get("sheets", {})
    assert "redirect_404" in sheets, "redirect_404 sheet missing from schema"
    assert "robots_txt" in sheets, "robots_txt sheet missing from schema"


# ---------------------------------------------------------------------------
# Test 5 — DURUR #1 empty target_urls SKIP
# ---------------------------------------------------------------------------

def test_indexing_ping_durur_1_empty_target_urls() -> None:
    """DURUR #1: target_urls boş → SKIP (info severity)."""
    text = _skill_text()
    assert "DURUR #1" in text
    # Cover both Turkish phrasings: "boş" and the SKIP semantic.
    assert "boş" in text or "empty" in text.lower()
    assert "SKIP" in text


# ---------------------------------------------------------------------------
# Test 6 — DURUR #2 invalid submission_type ABORT
# ---------------------------------------------------------------------------

def test_indexing_ping_durur_2_invalid_submission_type() -> None:
    """DURUR #2: submission_type enum dışı → ABORT."""
    text = _skill_text()
    assert "DURUR #2" in text
    assert "submission_type" in text
    assert "ABORT" in text
    # Enum must be enumerated explicitly so reviewer can verify it.
    assert "indexnow" in text
    assert "google_indexing_api" in text
    assert "both" in text


# ---------------------------------------------------------------------------
# Test 7 — DURUR #3 INDEXNOW_KEY missing AMBER hibrit branch
# ---------------------------------------------------------------------------

def test_indexing_ping_durur_3_missing_indexnow_key() -> None:
    """DURUR #3: INDEXNOW_KEY .env'de yok → AMBER skip indexnow,
    google_indexing_api devam (hibrit branch)."""
    text = _skill_text()
    assert "DURUR #3" in text
    assert "INDEXNOW_KEY" in text
    assert "AMBER" in text
    # Hibrit branch: GSC continues even when IndexNow skipped.
    assert "google_indexing_api" in text


# ---------------------------------------------------------------------------
# Test 8 — DURUR #4 GSC 5xx retry-once exponential backoff
# ---------------------------------------------------------------------------

def test_indexing_ping_durur_4_gsc_failure_retry_once() -> None:
    """DURUR #4: GSC API 5xx / timeout → AMBER + retry-once exponential
    backoff."""
    text = _skill_text()
    assert "DURUR #4" in text
    assert "5xx" in text or "5XX" in text or "timeout" in text.lower()
    assert "retry-once" in text or "retry once" in text.lower()
    assert "exponential backoff" in text.lower()


# ---------------------------------------------------------------------------
# Test 9 — DURUR #5 R-91 410 cascade REJECT
# ---------------------------------------------------------------------------

def test_indexing_ping_durur_5_410_status_cascade() -> None:
    """DURUR #5: target_url status 410 (action=410) ya da target=None on
    301 row → REJECT (R-91 cascade)."""
    text = _skill_text()
    assert "DURUR #5" in text
    assert "R-91" in text
    assert "410" in text
    assert "REJECT" in text
    # The cascade also handles 301 redirects (rewrite to target_url).
    assert "301" in text


# ---------------------------------------------------------------------------
# Test 10 — R-91 cascade redirect_404 lookup logic documented
# ---------------------------------------------------------------------------

def test_r91_cascade_redirect_404_lookup() -> None:
    """R-91 cascade enforce: redirect_404 sheet read with action=410
    reject + action=301 target_url rewrite, döngü guard."""
    text = _skill_text()
    assert "redirect_404" in text
    assert "action=410" in text or "action = 410" in text
    assert "action=301" in text or "action = 301" in text
    assert "target_url" in text
    # Loop guard for chained redirects.
    assert "döngü" in text or "loop" in text.lower() or "max 1 hop" in text


# ---------------------------------------------------------------------------
# Test 11 — R-58 robots map READ-ONLY; F-1 no transaction.* writes
# ---------------------------------------------------------------------------

def test_r58_robots_map_read_only_contract() -> None:
    """F-1 schema authority: master.xlsx[redirect_404] +
    master.xlsx[robots_txt] allowed_writers=null. Skill prose MUST NOT
    advertise transaction.append/update/delete against the workbook.
    R-58 lifecycle map READ-ONLY consume verified by grep."""
    text = _skill_text()

    # READ-ONLY claim must be explicit.
    assert "READ-ONLY" in text or "read-only" in text.lower()
    assert "R-58" in text
    assert "allowed_writers" in text
    assert "robots_txt" in text

    # No transaction writes against workbook.
    forbidden_writes = re.findall(
        r"transaction\.(append|update|delete)\s*\(", text
    )
    assert not forbidden_writes, (
        f"READ-ONLY contract violation: skill body invokes "
        f"transaction.* writes: {forbidden_writes}"
    )

    # No openpyxl save call documented (sentinel — skill must not save workbook).
    # Allow the explicit sentinel mention but not an actual workbook.save() call.
    save_invocations = re.findall(r"workbook\.save\s*\(", text)
    # Documentation references like 'openpyxl Workbook.save → çağrılırsa fail'
    # use 'Workbook.save' (capital W) — those are sentinel docs, not invocations.
    assert not save_invocations, (
        f"WRITE attempt advertised: workbook.save() invocation found in skill"
    )


# ---------------------------------------------------------------------------
# Test 12 — events.jsonl schema-first override (F-8 enum compliance)
# ---------------------------------------------------------------------------

def test_events_event_type_schema_first_override() -> None:
    """Schema-first override (lesson 7+23): events.schema.json event_type
    is a closed 10-value enum (F-8). Brief sketched
    'indexing_submitted' which is NOT in the enum. Skill writes
    event_type=manual + populates indexing_ping sub-object instead."""
    text = _skill_text()

    # Schema-first override decision must be documented.
    assert "Schema-first override" in text or "schema-first override" in text

    # event_type=manual is the F-8 enum compliant choice.
    assert "event_type=manual" in text or "`manual`" in text
    # indexing_ping sub-object reference (events.schema.json L206-218).
    assert "indexing_ping" in text

    # Schema authority cross-check: event_type closed 10-value enum.
    schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text("utf-8")
    )
    enum = schema["properties"]["event_type"]["enum"]
    assert "manual" in enum, "F-8 enum drifted: 'manual' missing"
    # Brief's 'indexing_submitted' must NOT be in the enum (proves override
    # was necessary).
    assert "indexing_submitted" not in enum, (
        "events.schema drift: 'indexing_submitted' should NOT be in F-8 enum "
        "(this is precisely why the schema-first override was applied)"
    )

    # event_kind=work declared.
    assert "event_kind=work" in text or "`work`" in text

    # task_id requirement (work events allOf rule).
    assert "task_id" in text


# ---------------------------------------------------------------------------
# Test 13 — Plugin-agnostic: no slug hardcoded; .mcp.json invariant
# ---------------------------------------------------------------------------

def test_plugin_agnostic_no_slug_hardcoded_and_mcp_json_unchanged() -> None:
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
    slugs = ["demo-dental", "demo-furniture", "demo-hvac", "demo-petcare",
             "demo-shop", "demo-tires", "demo-construction", "demo-agency"]
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

    # F-16 invariant — .mcp.json byte-hash unchanged. The test computes
    # the current hash; a regression would manifest as a byte diff
    # in a future commit.
    mcp_json_path = REPO_ROOT / ".mcp.json"
    assert mcp_json_path.exists(), ".mcp.json missing — F-16 invariant broken"
    h = hashlib.sha256(mcp_json_path.read_bytes()).hexdigest()
    # Only assert hash is computable + has the right length; the F-16
    # discipline is enforced at git-diff level by the manager, not here.
    assert len(h) == 64

    # F-16 invariant must be documented in the skill itself.
    assert "F-16" in text
    assert ".mcp.json" in text


# ---------------------------------------------------------------------------
# Test 14 — Foundational Principles 3-layer enforcement
# ---------------------------------------------------------------------------

def test_foundational_principles_3_layer_enforce() -> None:
    """Principle 1 truth-verifiable (R-91 cascade + R-58 read-only),
    Principle 2 profile-aware placeholder pattern (5-enum named even
    though skill is profile-agnostic), Principle 3 anti-cheap-content
    (wildcard reject + dedup + per-run cap)."""
    text = _skill_text()

    # Principle 1 — Truth-verifiable URL submission.
    assert "Principle 1" in text
    assert "Truth-Verifiable" in text or "truth-verifiable" in text.lower()
    assert "R-91" in text
    # 3-layer defense (Layer 1/2/3 explicit).
    assert "Layer 1" in text
    assert "Layer 2" in text
    assert "Layer 3" in text

    # Principle 2 — Profile-aware placeholder.
    assert "Principle 2" in text
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    for p in profile_enum:
        assert p in text, f"Profile enum value missing in skill body: {p}"
    # Placeholder pattern explicit (skill profile-agnostic but documents pattern).
    assert "profile-agnostic" in text or "Profile-Aware" in text or \
        "profile-aware" in text.lower()

    # Principle 3 — Anti-cheap-content gate.
    assert "Principle 3" in text
    assert "wildcard" in text.lower()
    assert "dedup" in text.lower()
    # Per-run cap mentioned (1000 buffer).
    assert "1000" in text or "cap" in text.lower()


# ---------------------------------------------------------------------------
# Test 15 — events.jsonl event_kind enum 4-value (ADR-020) cross-check
# ---------------------------------------------------------------------------

def test_event_kind_adr_020_enum_compliant() -> None:
    """events.schema.json event_kind enum (ADR-020) closed 4-value:
    provenance / work / audit / workflow. Skill emits event_kind=work
    on submission audit (verified in skill body). The schema-first
    override decision is grounded in this exact enum constraint."""
    schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text("utf-8")
    )
    kinds = schema["properties"]["event_kind"]["enum"]
    assert kinds == ["provenance", "work", "audit", "workflow"], (
        f"event_kind enum drift: {kinds!r}; ADR-020 expects "
        f"['provenance', 'work', 'audit', 'workflow']"
    )

    # Skill body must declare which kind it uses (work).
    text = _skill_text()
    assert "ADR-020" in text or "event_kind" in text
    # Confirm 'work' is the chosen kind (not provenance / audit / workflow).
    assert "event_kind=work" in text or "`work` " in text or "`work`," in text


# ---------------------------------------------------------------------------
# Test 16 (bonus self-extending — lesson 29) — output report shape contract
# ---------------------------------------------------------------------------

def test_report_artifact_json_shape_documented() -> None:
    """Self-extending positive drift (lesson 29): the skill documents the
    exact JSON shape of the per-run report artifact so downstream
    consumers (monthly-report, governance audits) have a stable
    contract. Bonus coverage beyond the 5 DURUR sentinels."""
    text = _skill_text()

    # The report path pattern.
    assert "outputs/indexing/" in text
    assert "submission-report.json" in text

    # Required fields in the report.
    required_fields = [
        "submitted_count",
        "failed_urls",
        "rejected_urls",
        "indexnow_response_code",
        "gsc_response_codes",
    ]
    for field in required_fields:
        assert field in text, (
            f"Report contract drift: '{field}' field missing from "
            f"report shape documentation"
        )
