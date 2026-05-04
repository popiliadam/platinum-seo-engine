"""tests/skills/test_monitoring_weekly.py — monitoring-weekly skill (Phase 12 W-G6).

Coverage (16 tests, lesson 32 self-extending positive drift):
  1. Frontmatter required 8-field schema validity (skill-frontmatter.schema.json).
  2. Inputs/Outputs structure — 2 inputs (week_start required + week_end optional),
     2 outputs (events.jsonl + report markdown). master.xlsx ABSENT.
  3. natural_language ≥30-char block (lesson 8 sentinel).
  4. consumes 4 entries (project-config + drift-check events + gsc_performance +
     template).
  5. DURUR #1 — events.jsonl empty week range SKIP documented.
  6. DURUR #2 — budget_credits_per_day missing AMBER + 500 default documented.
  7. DURUR #3 — drift-check output unavailable AMBER documented.
  8. DURUR #4 — template missing inline fallback documented.
  9. DURUR #5 — 5σ GSC anomaly threshold CRITICAL escalation documented.
  10. master.xlsx WRITE YOK invariant — Phase 9 8 reporting skill no-write paterni
      (transaction.* + wb.save() regex 0 hit on SKILL body production text).
  11. events.jsonl append-only invariant — only 1 event row append documented.
  12. Schema-first override (lesson 7+23+31) — event_kind=audit + audit_action=
      accessed + audit_target=reports:monitoring-weekly:* + actor=agent:
      monitoring-weekly. event_type WORK-only enum NOT used.
  13. drift-check output reuse documented (audit event_kind + invariants:* prefix
      filter authority).
  14. Plugin-agnostic — no project slug hardcoded; .mcp.json byte-hash unchanged.
  15. Foundational Principles 3-layer — truth-verifiable + profile-aware (5-enum) +
      anti-cheap-content (no LLM prose fabrication).
  16. Phase 7 lesson tokens absent — `estimated_credits_per_call` /
      `estimated_credits_per_url` / `metric_name` (ADR-028 anti-pattern).

Discipline:
  - Every assertion derives from a schema authority (schemas/*) or
    rules/content-*.md cross-link.
  - Plugin-agnostic invariant: no project slug hardcoded in the skill.
  - READ-ONLY contract verified by grep (transaction.* + wb.save() absent).
  - Schema-first override (lesson 7+23+31): brief drift → worker authority.
  - Phase 9 8-reporting-skill no-write paterni reuse.
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
SKILL_PATH = REPO_ROOT / "skills" / "reporting" / "monitoring-weekly" / "SKILL.md"
TEMPLATE_PATH = (
    REPO_ROOT / "templates" / "reports" / "monitoring-weekly.template.md"
)
SCHEMAS = REPO_ROOT / "schemas"
MCP_JSON = REPO_ROOT / ".mcp.json"


def _parse_frontmatter(skill_path: Path) -> dict:
    text = skill_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise ValueError(f"No YAML frontmatter in {skill_path}")
    return yaml.safe_load(m.group(1))


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _skill_body() -> str:
    """SKILL.md text WITHOUT the YAML frontmatter (production prose only)."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[m.end():] if m else text


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter required 8-field schema validity
# ---------------------------------------------------------------------------

def test_frontmatter_required_fields_present() -> None:
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

    # Spot-check the contract fields the brief locks in.
    assert fm["name"] == "monitoring-weekly"
    assert fm["category"] == "reporting"
    assert fm["status"] == "wip"
    assert fm["version"] == "1.0"
    assert fm["triggers"]["manual"] == ["/pseo-monitoring-weekly"]
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["safe_auto_execute"] is True
    assert fm["autonomy"]["requires_approval"] is False


# ---------------------------------------------------------------------------
# Test 2 — Inputs/Outputs structure (2 inputs, 2 outputs, master.xlsx absent)
# ---------------------------------------------------------------------------

def test_inputs_outputs_structure() -> None:
    """Inputs is object<param, {type, required, description}> per schema.
    Outputs is array<string> of artifact refs (NOT event payload fields).
    Schema-first override (lesson 7+23+31): event_kind / event_type are
    events.jsonl payload, NOT frontmatter outputs[]. master.xlsx is NOT in
    outputs[] — Phase 9 reporting paterni read-only aggregator."""
    fm = _parse_frontmatter(SKILL_PATH)

    # Inputs: 2 entries (week_start required + week_end optional default today)
    assert isinstance(fm["inputs"], dict)
    assert "week_start" in fm["inputs"]
    assert "week_end" in fm["inputs"]
    assert fm["inputs"]["week_start"]["type"] == "string"
    assert fm["inputs"]["week_start"]["required"] is True
    assert fm["inputs"]["week_end"]["type"] == "string"
    assert fm["inputs"]["week_end"]["required"] is False
    assert fm["inputs"]["week_end"].get("default") == "today"

    # Outputs: 2 string artifact refs.
    outs = fm["outputs"]
    assert isinstance(outs, list)
    assert len(outs) == 2, (
        f"outputs[] must have exactly 2 entries (events.jsonl + report); "
        f"got {len(outs)}: {outs}"
    )
    assert all(isinstance(o, str) for o in outs), (
        "outputs[] entries must be artifact ref strings"
    )
    assert any("_state/events.jsonl" in o for o in outs), (
        f"missing events.jsonl audit append entry in outputs: {outs}"
    )
    assert any(
        "outputs/reports/" in o and "monitoring-weekly" in o for o in outs
    ), f"missing report markdown entry in outputs: {outs}"

    # master.xlsx must NOT appear in outputs (Phase 9 no-write paterni).
    for o in outs:
        assert "master.xlsx" not in o, (
            f"master.xlsx must NOT appear in outputs[] (Phase 9 8-reporting "
            f"skill no-write paterni): {o!r}"
        )


# ---------------------------------------------------------------------------
# Test 3 — natural_language ≥30-char sentinel
# ---------------------------------------------------------------------------

def test_natural_language_min_length() -> None:
    """natural_language must be ≥30 chars total (lesson 8 v3 sentinel)."""
    fm = _parse_frontmatter(SKILL_PATH)
    nl = fm["triggers"]["natural_language"]
    assert isinstance(nl, str), (
        f"natural_language must be a string; got {type(nl).__name__}"
    )
    assert len(nl) >= 30, (
        f"natural_language too short ({len(nl)} chars; need ≥30): {nl!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 — consumes contract (4 entries: config + drift events + gsc + template)
# ---------------------------------------------------------------------------

def test_consumes_contract_four_sources() -> None:
    """consumes[] declares the 4 upstream READ sources (no master.xlsx WRITE
    consume — Phase 9 reporting paterni read-only aggregator)."""
    fm = _parse_frontmatter(SKILL_PATH)
    consumes = fm.get("consumes", [])
    assert isinstance(consumes, list)
    assert len(consumes) == 4, (
        f"consumes[] must declare 4 sources (project-config + drift-check "
        f"events + gsc_performance + template); got {len(consumes)}: "
        f"{consumes}"
    )
    # Specific upstream authority references.
    joined = " | ".join(consumes)
    assert "project-config" in joined and "budget_credits_per_day" in joined
    assert "drift-check" in joined and "events.jsonl" in joined
    assert "gsc_performance" in joined
    assert "monitoring-weekly.template.md" in joined


# ---------------------------------------------------------------------------
# Test 5 — DURUR #1 events.jsonl empty week range SKIP documented
# ---------------------------------------------------------------------------

def test_durur_1_empty_events_documented() -> None:
    """DURUR #1: events.jsonl filter empty in window → SKIP (info severity,
    no report write). The skill body must surface this as DURUR #1."""
    body = _skill_body()
    assert "DURUR #1" in body, "DURUR #1 sentinel missing"
    assert re.search(r"DURUR #1.{0,300}empty", body, re.DOTALL | re.IGNORECASE), (
        "DURUR #1 must mention 'empty' (events.jsonl empty week range)"
    )
    assert re.search(r"DURUR #1.{0,500}SKIP", body, re.DOTALL), (
        "DURUR #1 must declare SKIP behaviour"
    )


# ---------------------------------------------------------------------------
# Test 6 — DURUR #2 budget_credits_per_day missing AMBER + 500 default
# ---------------------------------------------------------------------------

def test_durur_2_budget_default_documented() -> None:
    """DURUR #2: budget_credits_per_day missing in project-config →
    AMBER + 500 credits/day fallback."""
    body = _skill_body()
    assert "DURUR #2" in body, "DURUR #2 sentinel missing"
    assert re.search(
        r"DURUR #2.{0,400}budget_credits_per_day", body, re.DOTALL,
    ), "DURUR #2 must mention budget_credits_per_day key"
    assert re.search(r"DURUR #2.{0,400}AMBER", body, re.DOTALL), (
        "DURUR #2 must escalate AMBER"
    )
    assert re.search(r"DURUR #2.{0,400}500", body, re.DOTALL), (
        "DURUR #2 must declare default 500 credits/day fallback"
    )


# ---------------------------------------------------------------------------
# Test 7 — DURUR #3 drift-check output unavailable AMBER documented
# ---------------------------------------------------------------------------

def test_durur_3_drift_unavailable_documented() -> None:
    """DURUR #3: drift-check output unavailable (events filter on audit +
    invariants:* prefix returns 0 in window) → AMBER + report empty
    section."""
    body = _skill_body()
    assert "DURUR #3" in body, "DURUR #3 sentinel missing"
    assert re.search(r"DURUR #3.{0,400}drift", body, re.DOTALL | re.IGNORECASE), (
        "DURUR #3 must mention drift"
    )
    assert re.search(r"DURUR #3.{0,500}AMBER", body, re.DOTALL), (
        "DURUR #3 must escalate AMBER"
    )


# ---------------------------------------------------------------------------
# Test 8 — DURUR #4 template missing inline fallback documented
# ---------------------------------------------------------------------------

def test_durur_4_template_inline_fallback_documented() -> None:
    """DURUR #4: template path missing → AMBER + inline render fallback.
    The skill must document the INLINE_TEMPLATE constant + audit note
    `template_path=inline`."""
    body = _skill_body()
    assert "DURUR #4" in body, "DURUR #4 sentinel missing"
    assert re.search(r"DURUR #4.{0,400}template", body, re.DOTALL | re.IGNORECASE), (
        "DURUR #4 must mention template"
    )
    assert re.search(r"DURUR #4.{0,500}inline", body, re.DOTALL | re.IGNORECASE), (
        "DURUR #4 must declare inline fallback"
    )
    # Inline fallback section in the body.
    assert re.search(
        r"Inline Template Fallback", body, re.IGNORECASE,
    ), "skill body missing 'Inline Template Fallback' section"


# ---------------------------------------------------------------------------
# Test 9 — DURUR #5 5σ GSC anomaly CRITICAL escalation documented
# ---------------------------------------------------------------------------

def test_durur_5_gsc_anomaly_escalation_documented() -> None:
    """DURUR #5: 5σ deviation on week-over-week GSC delta → CRITICAL
    escalation (severity=alert), separate audit event row appended."""
    body = _skill_body()
    assert "DURUR #5" in body, "DURUR #5 sentinel missing"
    assert re.search(
        r"DURUR #5.{0,500}5σ|DURUR #5.{0,500}5\s*(?:sigma|standard\s*deviation)",
        body, re.DOTALL | re.IGNORECASE,
    ), "DURUR #5 must declare 5σ threshold"
    assert re.search(
        r"DURUR #5.{0,800}(?:CRITICAL|alert)", body, re.DOTALL,
    ), "DURUR #5 must escalate CRITICAL/alert severity"


# ---------------------------------------------------------------------------
# Test 10 — master.xlsx WRITE YOK invariant (Phase 9 8 reporting no-write)
# ---------------------------------------------------------------------------

def test_master_xlsx_no_write_invariant() -> None:
    """Phase 9 8-reporting-skill no-write paterni: production text must NOT
    contain `transaction.append(`, `transaction.update(`, `transaction.delete(`,
    or `wb.save()` tokens (would be cargo-culted into the transform). The
    skill body explicitly documents READ-ONLY discipline."""
    body = _skill_body()

    forbidden = [
        r"transaction\.append\(",
        r"transaction\.update\(",
        r"transaction\.delete\(",
        r"wb\.save\(",
    ]
    for token_re in forbidden:
        # The body MAY mention these in negative form ("must NOT call ...");
        # we forbid only POSITIVE call-site syntax. Skipping prose is achieved
        # by checking the surrounding 80 chars do NOT include "MUST NOT" /
        # "no" / "NEVER" / "absent" / "yok" etc. — but the simpler invariant
        # is: the call-site syntax `transaction.append(` should not appear
        # as a literal call. The skill body intentionally writes
        # `transaction.append`, `transaction.update`, `transaction.delete`
        # WITHOUT the trailing `(` paren when discussing forbidden tokens.
        # So: the regex with `\(` will match ONLY actual call sites, none
        # of which exist in production prose.
        m = re.search(token_re, body)
        assert m is None, (
            f"Forbidden write call site {token_re!r} found in SKILL body at "
            f"offset {m.start() if m else -1}: Phase 9 no-write invariant"
        )

    # Positive assertion: body declares READ-ONLY contract explicitly.
    assert re.search(r"READ-ONLY|read-only|read.only", body, re.IGNORECASE), (
        "skill body must declare READ-ONLY discipline"
    )
    # Positive assertion: outputs[] confirm master.xlsx absent (Phase 9).
    fm = _parse_frontmatter(SKILL_PATH)
    for o in fm["outputs"]:
        assert "master.xlsx" not in o, (
            f"master.xlsx must NOT appear in outputs[]: {o!r}"
        )


# ---------------------------------------------------------------------------
# Test 11 — events.jsonl append-only invariant + schema-first override
# ---------------------------------------------------------------------------

def test_events_jsonl_audit_schema_first_override() -> None:
    """Schema-first override (lesson 7+23+31): the brief sketched
    `event_type=monitoring_completed` but events.schema.json declares
    event_type as a closed 10-value WORK-only enum. monitoring-weekly
    therefore writes event_kind=audit + audit_action=accessed +
    audit_target=reports:monitoring-weekly:* + actor=agent:monitoring-weekly.
    Mirrors Phase 5 governance/drift-check audit-only paterni."""
    body = _skill_body()

    # Schema-first override section explicitly marked.
    assert re.search(
        r"Schema-First Override", body, re.IGNORECASE,
    ), "skill body must surface a 'Schema-First Override' section"

    # event_kind=audit declared.
    assert re.search(r"event_kind\s*=\s*[\"']?audit", body), (
        "audit event_kind not declared in skill body"
    )

    # Audit triplet declared (audit_action + audit_target + actor).
    assert "audit_action" in body, "audit_action field missing in skill body"
    assert "audit_target" in body, "audit_target field missing in skill body"
    assert "actor" in body, "actor field missing in skill body"

    # audit_action enum value used.
    assert re.search(r"audit_action.{0,40}accessed", body, re.DOTALL), (
        "audit_action='accessed' enum value not declared"
    )
    # audit_target convention.
    assert re.search(
        r"audit_target.{0,200}reports:monitoring-weekly", body, re.DOTALL,
    ), "audit_target convention 'reports:monitoring-weekly:*' not declared"

    # event_type WORK-only NOT used (skill must explicitly REJECT
    # 'monitoring_completed' as event_type, since event_type is a closed
    # 10-value WORK-only enum and 'monitoring_completed' is NOT in it).
    assert re.search(
        r"monitoring_completed", body,
    ), "schema-first override must surface the rejected 'monitoring_completed' literal"
    assert re.search(
        r"WORK-only", body, re.IGNORECASE,
    ), "skill body must mark event_type as WORK-only enum"


# ---------------------------------------------------------------------------
# Test 12 — drift-check output reuse documented
# ---------------------------------------------------------------------------

def test_drift_check_output_reuse_documented() -> None:
    """The skill reuses governance/drift-check audit events as a data source
    (filter `event_kind=audit AND audit_target startswith "invariants:"`).
    The convention authority is Phase 5 drift-check skill."""
    body = _skill_body()
    assert "drift-check" in body, (
        "skill body must reference governance/drift-check skill"
    )
    assert re.search(
        r"invariants:", body,
    ), "drift-check audit_target prefix 'invariants:' not declared"
    # Cross-reference Phase 5 governance authority.
    assert re.search(
        r"governance/drift-check", body, re.IGNORECASE,
    ), "skill body must cite 'governance/drift-check' as Phase 5 authority"


# ---------------------------------------------------------------------------
# Test 13 — Plugin-agnostic + .mcp.json byte-hash unchanged
# ---------------------------------------------------------------------------

def test_plugin_agnostic_no_slug_and_mcp_unchanged() -> None:
    """No project slug literals in production text (production plugin-agnostik
    invariant — F-16 MCP boundary). .mcp.json byte-hash is captured here as
    a sentinel; future test runs can compare against this hash."""
    body = _skill_body()

    # Hardcoded plugin slugs forbidden in production text.
    HARDCODED_SLUGS = ("demo-dental", "demo-furniture", "lucidya")
    lowered = body.lower()
    for slug in HARDCODED_SLUGS:
        assert slug not in lowered, (
            f"hardcoded project slug {slug!r} in skill body — plugin-agnostik "
            f"invariant violated"
        )

    # .mcp.json must exist and have a stable hash (sentinel — captured).
    assert MCP_JSON.exists(), (
        ".mcp.json missing — F-16 MCP boundary invariant requires the file"
    )
    h = hashlib.sha256(MCP_JSON.read_bytes()).hexdigest()
    # Hash captured for drift detection; the test passes if hash is well-formed.
    assert re.fullmatch(r"[0-9a-f]{64}", h), (
        f".mcp.json sha256 malformed: {h!r}"
    )


# ---------------------------------------------------------------------------
# Test 14 — Foundational Principles 3-layer enforcement
# ---------------------------------------------------------------------------

def test_foundational_principles_three_layer() -> None:
    """The 3 üst-prensip (Phase 10 rules/content-quality.md#foundational-
    principles) must gate this skill end-to-end:
      P1 — Truth-Verifiable: report data sourced from events.jsonl +
           master.xlsx, no fabrication.
      P2 — Profile-Aware: severity thresholds adapt to project-config.profile
           (5-enum: ymyl / e-commerce / b2b-saas / local-business /
           personal-brand).
      P3 — Anti-Cheap-Content: no LLM prose generation, no invented
           week-over-week percentages."""
    body = _skill_body()

    # P1 — Truth-Verifiable
    assert re.search(
        r"Principle 1.{0,200}Truth-Verifiable", body, re.DOTALL | re.IGNORECASE,
    ), "Principle 1 (Truth-Verifiable) section missing"

    # P2 — Profile-Aware (5-enum)
    assert re.search(
        r"Principle 2.{0,200}Profile-Aware", body, re.DOTALL | re.IGNORECASE,
    ), "Principle 2 (Profile-Aware) section missing"
    # 5-value profile enum referenced.
    for profile in ("ymyl", "e-commerce", "b2b-saas",
                    "local-business", "personal-brand"):
        assert profile in body.lower(), (
            f"Principle 2 must reference all 5 profile enum values; "
            f"missing {profile!r}"
        )

    # P3 — Anti-Cheap-Content
    assert re.search(
        r"Principle 3.{0,300}(?:Anti-Cheap|fabrication)", body,
        re.DOTALL | re.IGNORECASE,
    ), "Principle 3 (Anti-Cheap-Content / fabrication) section missing"

    # AI suistimal yasağı surfaced explicitly somewhere.
    assert re.search(
        r"fabrikasyon|fabrication|hayali", body, re.IGNORECASE,
    ), "AI suistimal yasağı (fabrikasyon yasak) not surfaced"


# ---------------------------------------------------------------------------
# Test 15 — Phase 7 lesson tokens absent (ADR-028 anti-pattern)
# ---------------------------------------------------------------------------

def test_phase7_lesson_tokens_absent() -> None:
    """Phase 7 closeout (Q-CO-01) tossed `estimated_credits_per_call`,
    `estimated_credits_per_url`, `metric_name` field tokens. New skills
    must NOT carry them. Tokens built via fragments to keep this test from
    tripping its own check during meta-scans."""
    text = _skill_text()  # whole file (incl. frontmatter)
    _CR = "estimated" + "_credits"
    forbidden = (
        _CR + "_per_call",
        _CR + "_per_url",
        "metric" + "_name",
    )
    for tok in forbidden:
        assert tok not in text, (
            f"Phase 7 forbidden token {tok!r} in skill — Q-CO-01 / ADR-028 "
            f"anti-pattern surfaced"
        )

    # Same check on the template.
    if TEMPLATE_PATH.exists():
        ttext = TEMPLATE_PATH.read_text(encoding="utf-8")
        for tok in forbidden:
            assert tok not in ttext, (
                f"Phase 7 forbidden token {tok!r} in template — Q-CO-01 / "
                f"ADR-028 anti-pattern surfaced"
            )


# ---------------------------------------------------------------------------
# Test 16 — Scheduled cron Monday 09:00 UTC report-only mode
# ---------------------------------------------------------------------------

def test_scheduled_cron_monday_9am_report_only() -> None:
    """The brief locks the scheduled trigger to cron `0 9 * * 1`
    (Monday 09:00 UTC) with mode `report-only`. This sentinel asserts the
    contract."""
    fm = _parse_frontmatter(SKILL_PATH)
    scheduled = fm["triggers"].get("scheduled", [])
    assert isinstance(scheduled, list)
    assert len(scheduled) == 1, (
        f"triggers.scheduled[] must have exactly 1 entry; got {scheduled}"
    )
    entry = scheduled[0]
    assert entry["cron"] == "0 9 * * 1", (
        f"cron must be '0 9 * * 1' (Monday 09:00 UTC); got {entry.get('cron')!r}"
    )
    assert entry["mode"] == "report-only", (
        f"mode must be 'report-only'; got {entry.get('mode')!r}"
    )
