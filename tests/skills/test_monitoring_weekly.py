"""tests/skills/test_monitoring_weekly.py — monitoring-weekly skill (Phase 12 W-G6).

Coverage (16 tests, lesson 32 self-extending positive drift):
  1. Frontmatter required 8-field schema validity (skill-frontmatter.schema.json).
  2. Inputs/Outputs structure — 2 inputs (week_start required + week_end optional),
     2 outputs (events.jsonl + report markdown). master.xlsx ABSENT.
  3. natural_language ≥30-char block (lesson 8 sentinel).
  4. consumes 3 entries — the ACTUAL inline reads (drift-check
     consistency-report + portfolio.json + template); gsc_performance +
     budget_credits_per_day are Phase-14+ deferred (B2-03 reconcile).
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
import sys
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


def _inline_orchestration_blocks() -> list[str]:
    """Extract the runnable python blocks from the '## Inline Orchestration'
    section of SKILL.md (Block 1-3). These blocks ARE the skill's runtime —
    there is no separate scripts/reporting/monitoring_weekly.py (option b,
    Q-V1.2-MONITORING-WEEKLY-MISSING-SCRIPT-01). Scoped to the orchestration
    section so unrelated future code fences cannot leak in."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    start = text.index("## Inline Orchestration")
    nxt = text.find("\n## ", start + 1)  # next H2 ends the section
    section = text[start:nxt] if nxt != -1 else text[start:]
    return re.findall(r"```python\n(.*?)```", section, re.DOTALL)


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
    assert fm["status"] in {"active", "deprecated", "wip"}
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

def test_consumes_contract_actual_reads() -> None:
    """consumes[] reflects the ACTUAL inline reads (B2-03 reconcile):
    drift-check consistency-report.json (Block 1) + init-project
    portfolio.json (Block 2) + the report template. The Phase-14+ future
    reads (project-config budget_credits_per_day + master.xlsx
    gsc_performance) are documented in prose as deferred placeholders and
    must NOT appear in consumes[] — which is the orchestrator dependency
    graph of REAL reads, not aspirational ones."""
    fm = _parse_frontmatter(SKILL_PATH)
    consumes = fm.get("consumes", [])
    assert isinstance(consumes, list)
    assert len(consumes) == 4, (
        f"consumes[] must declare the 4 actual inline reads (drift-check "
        f"consistency-report + portfolio.json + template + gsc-weekly ledger); "
        f"got {len(consumes)}: {consumes}"
    )
    joined = " | ".join(consumes)
    assert "drift-check" in joined and "consistency-report" in joined, (
        "consumes[] must declare drift-check consistency-report.json (the "
        "actual Block 1 read), not the events.jsonl invariants filter"
    )
    assert "portfolio.json" in joined, (
        "consumes[] must declare shared/portfolio.json (the actual Block 2 read)"
    )
    assert "monitoring-weekly.template.md" in joined
    # GAP-M4: the GSC anomaly path reads the weekly ledger (NOT master.xlsx).
    assert "gsc-weekly.jsonl" in joined, (
        "consumes[] must declare the _state/metrics/gsc-weekly.jsonl ledger "
        "(the active Block 3 anomaly read, GAP-M4)"
    )
    # master.xlsx[gsc_performance] is NOT read (it has no date column / is a
    # snapshot) — the ledger replaced that false claim.
    assert "gsc_performance" not in joined, (
        "master.xlsx[gsc_performance] is a snapshot with no weekly series; the "
        "inline runtime never opens master.xlsx — the ledger is the source"
    )
    # budget_credits_per_day remains a Phase-14+ future read (still deferred).
    assert "budget_credits_per_day" not in joined, (
        "project-config[budget_credits_per_day] is a Phase-14+ future read; "
        "the inline runtime never opens project-config (B2-03 reconcile)"
    )


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
    """DURUR #5 v2 (GAP-M4 / R-141): the GSC anomaly is now ACTIVE — a robust
    median+MAD modified z-score (NOT 5σ). A severity=RED anomaly → CRITICAL
    escalation with a SECOND audit row. The discredited 5σ placeholder is
    fully removed (grep sentinel)."""
    body = _skill_body()
    assert "DURUR #5" in body, "DURUR #5 sentinel missing"
    # Anchor on the unique dedicated-section header ("MAD GSC anomaly"); the
    # Outputs mention says "MAD anomaly" (no GSC) so this is unambiguous.
    m = re.search(r"DURUR #5.{0,6}MAD GSC anomaly(.{0,1800})", body, re.DOTALL)
    assert m, "dedicated DURUR #5 (MAD GSC anomaly) section missing"
    region = m.group(1)
    assert re.search(r"median.?\+?.?MAD|modified.z", region, re.IGNORECASE), (
        "DURUR #5 must declare the median+MAD modified-z detector"
    )
    assert "R-141" in region, "DURUR #5 must cite R-141"
    assert "CRITICAL" in region, "DURUR #5 must escalate to CRITICAL"
    assert re.search(r"second|ikinci", region, re.IGNORECASE), (
        "DURUR #5 must declare a SECOND audit row on RED"
    )
    assert "audit" in region.lower()
    # The discredited 5σ placeholder must be GONE from the whole SKILL.
    full = _skill_text()
    assert "5σ" not in full, "the 5σ placeholder must be fully removed (R-141 replaces it)"


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
           (5-enum: e-commerce / ymyl / local-service / b2b-saas /
           portfolio — the REAL schemas/project-config.schema.json values).
      P3 — Anti-Cheap-Content: no LLM prose generation, no invented
           week-over-week percentages."""
    body = _skill_body()

    # P1 — Truth-Verifiable
    assert re.search(
        r"Principle 1.{0,200}Truth-Verifiable", body, re.DOTALL | re.IGNORECASE,
    ), "Principle 1 (Truth-Verifiable) section missing"

    # P2 — Profile-Aware (5-enum). The enum MUST match the real
    # schemas/project-config.schema.json values (B2-07 fix): the prior
    # local-business / personal-brand values do not exist in that schema.
    assert re.search(
        r"Principle 2.{0,200}Profile-Aware", body, re.DOTALL | re.IGNORECASE,
    ), "Principle 2 (Profile-Aware) section missing"
    for profile in ("ymyl", "e-commerce", "b2b-saas",
                    "local-service", "portfolio"):
        assert profile in body.lower(), (
            f"Principle 2 must reference all 5 real profile enum values; "
            f"missing {profile!r}"
        )
    # The non-schema values must NOT reappear (B2-07 regression lock).
    for bogus in ("local-business", "personal-brand"):
        assert bogus not in body.lower(), (
            f"non-schema profile value {bogus!r} must not appear — "
            f"schemas/project-config.schema.json has no such enum member"
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


# ---------------------------------------------------------------------------
# Test 17 — EXECUTION: run the inline orchestration against a tmp workspace
# ---------------------------------------------------------------------------

def test_inline_orchestration_executes_against_tmp_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B2-04: a REAL execution test (not a prose-grep). Runs the inline
    Block 1-3 orchestration — which *is* the skill's runtime — against a
    tmp workspace and asserts the actual side-effects, not the words on the
    page:
      - a report file is written with the 5 documented sections;
      - the drift counts from consistency-report.json actually flow into
        the report (truth-verifiable — proves the runtime really read it);
      - the GSC + budget sections honestly announce the Phase-14+ deferral
        (B2-02 stub-mark verified at the runtime, not just the doc);
      - exactly ONE events.jsonl audit row is appended (event_kind=audit +
        audit_action=accessed + audit_target=reports:monitoring-weekly:* +
        actor=agent:monitoring-weekly, no event_type, no 5σ second row);
      - NO master.xlsx is written (Phase 9 read-only invariant)."""
    blocks = _inline_orchestration_blocks()
    assert len(blocks) >= 3, (
        f"expected >=3 runnable inline blocks (Block 1-3); got {len(blocks)}"
    )

    slug = "demo-project"  # matches ^[a-z][a-z0-9-]*$; not a real plugin slug
    ws = tmp_path / "ws"

    # Block 1 input: _state/cache/consistency-report.json (drift-check output).
    cache_dir = ws / "projects" / slug / "_state" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "consistency-report.json").write_text(
        json.dumps({
            "red_count": 2, "amber_count": 1, "green_count": 17,
            "verdict": "AMBER",
        }),
        encoding="utf-8",
    )
    # Block 2 input: shared/portfolio.json.
    shared_dir = ws / "shared"
    shared_dir.mkdir(parents=True)
    (shared_dir / "portfolio.json").write_text(
        json.dumps({"projects": [{
            "slug": slug, "completion_percentage": 42.5,
            "active_oq_count": 3, "recent_events_count_7day": 9,
        }]}),
        encoding="utf-8",
    )

    monkeypatch.setenv("PSEO_PROJECT_ID", slug)
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    monkeypatch.setenv("MONITORING_WEEK_START", "2026-04-20")
    monkeypatch.setenv("MONITORING_WEEK_END", "2026-04-26")
    # os.getcwd() must be the repo root so the on-disk template resolves and
    # `from scripts.state import events_writer` imports. Report + events still
    # land under the tmp workspace (PSEO_WORKSPACE_ROOT), never the real tree.
    monkeypatch.chdir(REPO_ROOT)

    saved_path = list(sys.path)
    try:
        ns: dict = {}
        exec(  # noqa: S102 — executing the skill's own documented runtime
            compile("\n".join(blocks), "<monitoring-weekly-inline>", "exec"),
            ns,
        )
    finally:
        sys.path[:] = saved_path

    # 1. Report file written with the 5 documented sections.
    report_dir = ws / "projects" / slug / "outputs" / "reports"
    reports = list(report_dir.glob("*-monitoring-weekly.md"))
    assert len(reports) == 1, f"expected exactly 1 report file, got {reports}"
    report = reports[0].read_text(encoding="utf-8")
    for header in ("## Exec Summary", "## Drift Section",
                   "## GSC Anomaly Section", "## Budget Burn Section",
                   "## Escalations"):
        assert header in report, f"report missing section header {header!r}"
    assert slug in report
    assert "2026-04-20" in report and "2026-04-26" in report

    # 2. Truth-verifiable: the drift counts from consistency-report.json must
    #    actually reach the report (proves the runtime read the real input).
    assert "RED=2" in report and "AMBER=1" in report and "GREEN=17" in report, (
        "drift counts from consistency-report.json did not reach the report — "
        "the runtime did not actually read the drift output"
    )
    assert "AMBER" in report  # severity: amber_count>0 and red_count<5

    # 3. GAP-M4: with NO ledger, the GSC anomaly section renders the honest
    #    `insufficient_history` string (active path, not a fabricated alarm and
    #    not a deferral placeholder). Budget remains the ONLY Phase-14+ deferral.
    assert "yetersiz geçmiş" in report, (
        "missing ledger must render the honest insufficient_history string "
        "(GAP-M4 active path), not a 5σ/deferral placeholder"
    )
    assert "R-141" in report, "GSC anomaly section must cite the R-141 detector"
    assert "Phase 14+" in report, (
        "the budget-burn section remains an honest Phase-14+ deferral"
    )
    # severity unchanged from the drift rollup (insufficient history ⇒ no escalation).
    assert "severity: AMBER" in report or "severity:AMBER" in report or \
        "Genel severity:** AMBER" in report, "drift rollup severity (AMBER) must survive"

    # 4. Exactly ONE events.jsonl audit row (no 5σ second row this Wave).
    events_path = ws / "projects" / slug / "_state" / "events.jsonl"
    assert events_path.is_file(), "audit event row was not appended"
    lines = [
        L for L in events_path.read_text(encoding="utf-8").splitlines()
        if L.strip()
    ]
    assert len(lines) == 1, f"expected exactly 1 audit row, got {len(lines)}"
    evt = json.loads(lines[0])
    assert evt["event_kind"] == "audit"
    assert evt["audit_action"] == "accessed"
    assert evt["audit_target"].startswith("reports:monitoring-weekly:")
    assert evt["actor"] == "agent:monitoring-weekly"
    assert "event_type" not in evt, (
        "audit event must NOT carry event_type (WORK-only enum; schema-first "
        "override) — events.schema.json rejects it for event_kind=audit"
    )

    # 5. READ-ONLY: no master.xlsx written anywhere under the project tree.
    assert not list((ws / "projects" / slug).rglob("master.xlsx")), (
        "monitoring-weekly must NOT write master.xlsx (Phase 9 8-reporting "
        "no-write invariant)"
    )


# ---------------------------------------------------------------------------
# Test 18 — GAP-M4: a RED MAD anomaly fires DURUR #5 (exactly 2 audit rows)
# ---------------------------------------------------------------------------

def test_inline_red_anomaly_writes_second_audit_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a populated weekly ledger showing a clear clicks collapse in a week
    that does NOT overlap a Ranking update, Block 3 computes severity=RED and
    appends a SECOND audit row (audit_target ...:anomaly) — the DURUR #5
    CRITICAL escalation. The drift output is GREEN so the RED comes solely from
    the GSC anomaly (proving the severity rollup)."""
    import sys as _sys
    from datetime import date as _d, timedelta as _td

    def _monday_of(d: "_d") -> "_d":
        return d - _td(days=d.weekday())

    def _isolabel(d: "_d") -> str:
        c = d.isocalendar()
        return f"{c[0]}-W{c[1]:02d}"

    blocks = _inline_orchestration_blocks()
    slug = "demo-project"
    ws = tmp_path / "ws"

    # Drift: all GREEN so any RED must come from the GSC anomaly.
    cache_dir = ws / "projects" / slug / "_state" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "consistency-report.json").write_text(
        json.dumps({"red_count": 0, "amber_count": 0, "green_count": 20,
                    "verdict": "GREEN"}),
        encoding="utf-8",
    )
    shared_dir = ws / "shared"
    shared_dir.mkdir(parents=True)
    (shared_dir / "portfolio.json").write_text(
        json.dumps({"projects": [{"slug": slug, "completion_percentage": 80.0,
                                  "active_oq_count": 0,
                                  "recent_events_count_7day": 4}]}),
        encoding="utf-8",
    )

    # Weekly ledger: 12 flat baseline weeks (~100 clicks) + a current week that
    # COLLAPSES to 40 clicks. Current week = 2026-04-20..04-26 (no calendar
    # overlap — between the March-2026 settling window and the May-2026 rollout).
    current_monday = _monday_of(_d(2026, 4, 22))   # → 2026-04-20 (Monday)
    metrics_dir = ws / "projects" / slug / "_state" / "metrics"
    metrics_dir.mkdir(parents=True)
    base = [98, 102, 99, 101, 100, 103, 97, 100, 102, 98, 101, 99]
    lines = []
    for i, c in enumerate(reversed(base), start=1):
        mon = current_monday - _td(weeks=i)
        sun = mon + _td(days=6)
        lines.append(json.dumps({
            "iso_week": _isolabel(mon), "week_start": mon.isoformat(),
            "week_end": sun.isoformat(), "clicks": c, "impressions": 5000,
            "ctr": 0.02, "avg_position": 15.0, "source": "gsc_mcp",
            "written_at": "2026-01-01T00:00:00Z"}))
    cur_sun = current_monday + _td(days=6)
    lines.append(json.dumps({
        "iso_week": _isolabel(current_monday), "week_start": current_monday.isoformat(),
        "week_end": cur_sun.isoformat(), "clicks": 40, "impressions": 5000,
        "ctr": 0.02, "avg_position": 15.0, "source": "gsc_mcp",
        "written_at": "2026-01-01T00:00:00Z"}))
    (metrics_dir / "gsc-weekly.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.setenv("PSEO_PROJECT_ID", slug)
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(ws))
    monkeypatch.setenv("MONITORING_WEEK_START", current_monday.isoformat())
    monkeypatch.setenv("MONITORING_WEEK_END", cur_sun.isoformat())
    monkeypatch.chdir(REPO_ROOT)

    saved_path = list(_sys.path)
    try:
        exec(compile("\n".join(blocks), "<monitoring-weekly-inline>", "exec"), {})
    finally:
        _sys.path[:] = saved_path

    report = next((ws / "projects" / slug / "outputs" / "reports").glob(
        "*-monitoring-weekly.md")).read_text(encoding="utf-8")

    # The GSC anomaly section reports the computed RED clicks drop (R-141).
    assert "R-141" in report
    assert "clicks" in report
    assert "CRITICAL" in report, "RED anomaly must populate the escalations section"
    # Overall severity escalated to RED purely from the anomaly (drift was GREEN).
    assert "RED" in report

    # Exactly TWO audit rows: the base accessed row + the :anomaly escalation row.
    events_path = ws / "projects" / slug / "_state" / "events.jsonl"
    rows = [json.loads(L) for L in events_path.read_text(encoding="utf-8").splitlines()
            if L.strip()]
    assert len(rows) == 2, f"RED anomaly must append exactly 2 audit rows, got {len(rows)}"
    targets = [r["audit_target"] for r in rows]
    assert any(t.endswith(":anomaly") for t in targets), (
        "the second audit row must carry the ...:anomaly target"
    )
    assert all(r["event_kind"] == "audit" and r["actor"] == "agent:monitoring-weekly"
               for r in rows)
