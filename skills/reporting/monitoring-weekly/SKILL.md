---
name: monitoring-weekly
description: |
  Use when: kullanıcı "weekly check", "haftalık monitoring", "drift check
  + GSC anomaly + budget burn", "weekly health report", "haftalık sağlık
  raporu", "haftalık monitoring özeti" der ya da /pseo-monitoring-weekly
  çağırır; week range filter events.jsonl + drift-check output reuse +
  GSC week-over-week delta + budget burn rate aggregation →
  outputs/reports/{date}-monitoring-weekly.md.
  Also use when: cron scheduled weekly run her Pazartesi 09:00 UTC
  report-only mode; reporting suite extension Phase 9 8 reporting skill
  no-write paterni reuse; Foundational Principle 1 truth-verifiable
  enforcement audit-only (events.jsonl + master.xlsx kaynaklı,
  fabrikasyon yok); manager portfolio-overview öncesi tek-proje haftalık
  sağlık özeti istediğinde.
  Do not use when: ad-hoc daily check (out of scope, daily skill ayrı —
  bu skill rolling 7-day window aggregator); events.jsonl empty week
  range (DURUR #1 SKIP, no report write); GSC api auth fail (out of
  scope, gsc-bootstrap skill önce çalışmalı); template path missing →
  inline fallback (DURUR #4 AMBER, manuel inceleme); 5σ anomaly
  threshold hit ise CRITICAL escalation severity=alert (DURUR #5,
  manager onayı Phase 14+ governance); master.xlsx WRITE talep edilirse
  YASAK (Phase 9 reporting paterni: 8 skill no-write invariant).
version: "1.0"
status: wip
category: reporting
inputs:
  week_start:
    type: string
    required: true
    description: "YYYY-MM-DD format week start date (inclusive). Window kapsamı: week_start..week_end. Geçersiz format → DURUR validation hata."
  week_end:
    type: string
    required: false
    default: "today"
    description: "YYYY-MM-DD format week end (inclusive). Default 'today' (run-time date.today() ile çözülür). week_start sonrası olmalı."
outputs:
  - "_state/events.jsonl"
  - "outputs/reports/{date}-monitoring-weekly.md"
consumes:
  - "init-project:project-config[budget_credits_per_day]"
  - "drift-check:_state/events.jsonl"
  - "init-project:master.xlsx[gsc_performance]"
  - "templates/reports/monitoring-weekly.template.md"
produces: []
triggers:
  manual: ["/pseo-monitoring-weekly"]
  natural_language: |
    "weekly check", "haftalık monitoring", "drift check + GSC anomaly +
    budget burn", "weekly health report", "haftalık sağlık raporu",
    "monitoring weekly", "haftalık health check"
  hooks: []
  scheduled:
    - cron: "0 9 * * 1"
      mode: "report-only"
mcp_tools:
  required: []
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: false
  safe_auto_execute: true
---

# monitoring-weekly — reporting skill (Phase 12 Wave 2, W-G6)

Weekly health check aggregator. Reads `_state/events.jsonl` filtered to
the `week_start..week_end` window, reuses `governance/drift-check`
output (events filter on `event_kind=audit AND audit_action=accessed
AND audit_target=invariants:*`), pulls week-over-week GSC delta from
`master.xlsx[gsc_performance]` via `openpyxl read_only=True`, computes
budget burn rate (events.jsonl `cost.credits` aggregation per day vs
`project-config.budget_credits_per_day` baseline), then renders
`outputs/reports/{date}-monitoring-weekly.md`. **No MCP**, **no DFS**,
**no budget pre-flight**, **no master.xlsx WRITE** — strict read-only.

This skill follows the Phase 9 reporting **convention authority**
established by `skills/reporting/weekly-summary/SKILL.md` (W-E2 — local
aggregation, READ-ONLY contract on `master.xlsx`) and
`skills/reporting/portfolio-overview/SKILL.md` (W-E5 — multi-project
no-write aggregator). The 8 Phase 9 reporting skills share the
no-write invariant — `transaction.append`, `transaction.update`,
`transaction.delete` and `wb.save` MUST NOT appear anywhere in
production paths. The test suite enforces this with a grep sentinel
(the call-site syntax with the trailing `(` paren is the actual
forbidden token; prose mentions without parens are allowed).

## Schema-First Override (Lesson 7+23+31, W-G1+W-G2+W-G3+W-G4 paterni)

The brief sketched `event_kind=audit + event_type=monitoring_completed`.
Per `schemas/events.schema.json`:

1. `event_type` is **WORK-only** (closed 10-value enum):
   `content_new, content_revise, content_remove, tech_fix,
   quickwin_applied, pillar_launch, schema_fix, redirect_deployed,
   backlink_outreach, manual` (F-8 invariant). `monitoring_completed`
   is NOT in the enum.
2. `event_kind=audit` requires `audit_action` + `audit_target` +
   `actor` (allOf if/then conditional, lines per schema). It does
   **not** carry `event_type`.

Therefore the worker writes:
- `event_kind=audit`
- `audit_action="accessed"` (enum: created/modified/deleted/accessed/
  permission_changed/config_changed)
- `audit_target="reports:monitoring-weekly:{week_start}_{week_end}"`
- `actor="agent:monitoring-weekly"`
- `schema_version="1.0"`, `event_id`, `timestamp`, `project_id`
  (envelope required across all kinds).

This mirrors the Phase 5 `governance/drift-check` pattern
(`audit_action="accessed"`, `audit_target="invariants:20"`,
`actor="drift-check"`) — drift-check's audit-only convention is the
authority this skill reuses. Diverges from W-G1 (indexing-ping)
which used `event_kind=work + event_type=manual + indexing_ping
sub-object`; that path requires a `task_id` mint and is reserved for
work-bearing skills. monitoring-weekly does **no work** — it only
reads + reports — so the `audit` kind is the semantic-correct choice.

## Inputs (frontmatter contract)

| Name         | Type   | Default | Notes                                                       |
|--------------|--------|---------|-------------------------------------------------------------|
| `week_start` | string | —       | Required. YYYY-MM-DD inclusive window start.                |
| `week_end`   | string | today   | Inclusive window end. Default = run-time `date.today()`.    |

Both inputs are validated as ISO-8601 dates before any I/O. Invalid
format raises `MonitoringWeeklyValidationError` (DURUR #0 envelope).

## Outputs (artifacts produced — 2 entries, master.xlsx ABSENT)

- `_state/events.jsonl` — single-row audit append (or 2 rows if
  DURUR #5 5σ anomaly fires; the second row carries
  `audit_action="accessed"` + an additional `note` field flagged as
  alert via the report; severity is encoded report-side, not via a
  schema field).
- `outputs/reports/{date}-monitoring-weekly.md` — human-readable
  health check report with 5 sections (exec_summary, drift_section,
  gsc_anomaly_section, budget_burn_section, escalations).

`master.xlsx` is **NOT** in `outputs[]` — Phase 9 8-reporting-skill
no-write paterni reuse (cf. `weekly-summary` outputs[0]
`master.xlsx#none` confirm marker; this skill instead omits the entry
because R-WAVE-2 brief requires only 2 outputs).

## DURUR (no fall-back) conditions — 5 sentinels

Stop and surface to the manager — do not patch, do not silently
swallow.

1. **DURUR #1 — events.jsonl empty week range** → SKIP.
   When the events.jsonl filter for the window returns 0 rows, the
   skill writes a single `severity=info` audit event with
   `audit_action="accessed"` + `audit_target="reports:monitoring-
   weekly:{week_start}_{week_end}:empty"` and **does NOT write the
   markdown report**. Report path resolves to a sentinel "empty window"
   marker that the test suite asserts.

2. **DURUR #2 — `budget_credits_per_day` absent in project-config**
   → AMBER + default 500 credits/day fallback.
   The report's `budget_burn_section` carries the AMBER badge and a
   note that the baseline came from the hard-coded fallback. The audit
   event records this in the report (severity=amber).

3. **DURUR #3 — drift-check output unavailable** (events filter on
   `event_kind=audit AND audit_target ~ invariants:*` returns empty
   in the window) → AMBER + report empty section.
   The `drift_section` shows "drift-check henüz çalıştırılmamış" and
   the report severity escalates to AMBER.

4. **DURUR #4 — template path
   `templates/reports/monitoring-weekly.template.md` not on disk** →
   AMBER + inline render fallback. The skill embeds an inline template
   string as a defensive fallback (the body of this SKILL.md carries
   the inline template definition under "Inline Template Fallback"
   section below). The report renders, and the audit event records
   the fallback path was used.

5. **DURUR #5 — 5σ GSC anomaly threshold hit** → CRITICAL escalation.
   When week-over-week delta on any of `clicks`, `impressions`,
   `ctr`, `position` exceeds 5 standard deviations from the trailing
   8-week mean (computed locally from `master.xlsx[gsc_performance]`
   rows ordered by date_iso), the report's `escalations` section
   carries severity=alert and a separate audit event row is appended
   with `note` flagging the metric, magnitude, and direction. The
   manager is expected to act on this in Phase 14+ governance.

## Workflow (8 step)

1. **Read project-config** for `budget_credits_per_day` baseline + GSC
   `siteUrl`. Missing key → DURUR #2 (default 500).
2. **Read events.jsonl** with week range filter
   (`week_start..week_end` inclusive). 0 rows → DURUR #1 SKIP.
3. **drift-check output reuse** — filter events on
   `event_kind=audit AND audit_target startswith "invariants:"`.
   0 rows in window → DURUR #3 AMBER.
4. **GSC anomaly detect** — read `master.xlsx[gsc_performance]` via
   `openpyxl.load_workbook(read_only=True, data_only=True)`. Compute
   week-over-week delta against the previous 7-day window; if any
   metric delta exceeds 5σ of the trailing 8-week mean, fire DURUR
   #5 escalation.
5. **Budget burn rate** — sum `cost.credits` from events.jsonl in
   window per day; compute `daily_mean / budget_credits_per_day`
   ratio. Ratio > 1.0 emits AMBER badge; ratio > 2.0 emits RED badge.
6. **Report render** — `templates/reports/monitoring-weekly.template.md`
   via `string.Template` `$var` substitution (Phase 1 mirası
   `scripts/reporting/render_template.py` paterni reuse). Missing
   template → DURUR #4 inline fallback.
7. **NO master.xlsx update** — read-only aggregation. Phase 9 8
   reporting skill no-write paterni reuse. The transform module never
   imports `scripts.excel.transaction` and never calls `wb.save`.
8. **events.jsonl append** — single audit row (or 2 if DURUR #5
   fires). Schema-first override applied per the section above.

## Foundational Principles Enforcement (3-Layer)

The 3 üst-prensip (Phase 10 `rules/content-quality.md#foundational-
principles`) gate this skill end-to-end. No alt-rule (R-01..R-122)
overrides them.

### Principle 1 — Truth-Verifiable Health Report

Every datum in the report is sourced from a tangible artifact:
- `drift_section` ← events.jsonl rows with
  `event_kind=audit AND audit_target=invariants:*` (Phase 5
  `drift-check` audit appends).
- `gsc_anomaly_section` ← `master.xlsx[gsc_performance]` rows
  (Phase 6 GSC ingestion writer authority).
- `budget_burn_section` ← events.jsonl `cost.credits` aggregation
  (Phase 7+8 work events).
- `exec_summary` ← computed roll-up of the above three; no
  free-form fabrication.

The skill never invents GSC delta values; if `gsc_performance` is
empty for the window, the section flags "GSC veri yok" and the
report severity escalates to AMBER. AI suistimal yasağı: hayali
delta fabrikasyonu YASAK — hep `master.xlsx[gsc_performance]` read.

### Principle 2 — Profile-Aware Severity

The severity thresholds adapt to `project-config.profile`:
- `ymyl` (Your Money Your Life): drift-check FAIL → CRITICAL
  escalation immediately (compliance burst alert; one FAIL is one
  too many for medical/legal/financial sites).
- `e-commerce`: GSC clicks delta < -20% week-over-week → AMBER
  (conversion-loss signal); drift-check FAIL → AMBER.
- `b2b-saas`: GSC impressions delta < -30% AND signup_velocity
  proxy (events.jsonl `event_type=content_new` count) drop → AMBER
  (top-of-funnel signal).
- `local-business` / `personal-brand`: drift-check FAIL only →
  AMBER (lower volume, lower stakes).

The 5-value `profile` enum lives in
`schemas/project-config.schema.json` (Phase 11 W-A1 v1.2 cascade
authority).

### Principle 3 — Anti-Cheap-Content (no fabrication)

The skill renders ONLY counts + factual deltas. It does NOT generate
prose summaries via LLM, does NOT invent week-over-week percentages,
and does NOT guess at root causes. The `exec_summary` is a
rule-based 1-2 sentence Turkish rollup composed from the section
counts (template `string.Template` substitution).

## Inline Template Fallback (DURUR #4)

When `templates/reports/monitoring-weekly.template.md` is absent, the
transform falls back to an inline template string defined in
`scripts/reporting/monitoring_weekly.py` as `INLINE_TEMPLATE`. The
fallback template carries the same 5 sections + same `$var` slots as
the on-disk template. The audit event records `template_path=inline`
in the `note` field. The test suite asserts both render paths
produce structurally equivalent output.

## Cross-references

- Schemas: `schemas/events.schema.json` (audit event_kind required
  fields: audit_action + audit_target + actor),
  `schemas/master-excel.schema.json` (`gsc_performance` sheet
  read-only access), `schemas/skill-frontmatter.schema.json` (this
  frontmatter).
- Cross-modules (READ-only, IMPORT pattern):
  `scripts/reporting/render_template.py` (`string.Template` $var
  rendering reuse).
- Reference SKILL.md: `skills/reporting/weekly-summary/SKILL.md`
  (Phase 9 weekly aggregation paterni — local aggregator + READ-ONLY
  contract on master.xlsx) and
  `skills/reporting/portfolio-overview/SKILL.md` (Phase 9 8
  reporting skill no-write paterni — strict read-only aggregator).
- Reference governance skill: `skills/governance/drift-check/SKILL.md`
  (Phase 5 audit event_kind paterni: `audit_action=accessed +
  audit_target=invariants:20 + actor=drift-check`).
- Template: `templates/reports/monitoring-weekly.template.md`
  (DURUR #4 fallback to inline string if absent).
- Tests: `tests/skills/test_monitoring_weekly.py`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises a typed exception or
      writes a sentinel audit event; no silent swallow.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` (Draft 7); audit event
      validates against `schemas/events.schema.json` allOf if/then
      conditional for `event_kind=audit`.
- [x] Plugin-agnostik — no slug literals in transform; no hardcoded
      `.mcp.json` writes; F-16 MCP boundary intact.
- [x] ADR-013 — `Use when` / `Also use when` / `Do not use when`
      are STRING content inside `description`, not separate fields.
- [x] Append-only state — this skill writes ONLY to
      `outputs/reports/` + `_state/events.jsonl` (audit append).
      NEVER mutates `master.xlsx`.
- [x] Phase 9 no-write paterni — no `transaction.append`,
      `transaction.update`, `transaction.delete`, `wb.save`
      tokens in production paths (test enforces grep sentinel; the
      forbidden call-site is the workbook save method invocation
      with trailing paren — prose mentions without parens are
      allowed for documentation discussion).
- [x] Forbidden tokens (3): grep CLEAN of the per-call/per-url
      credit field tokens (Phase 7 schema-field uydurma marker) +
      hardcoded project slugs (test enforces).
- [x] natural_language sentinel: ≥30 char (test enforces).
- [x] .mcp.json byte unchanged (Phase 11 F-16 invariant — test
      enforces SHA-256 stability across the worker run).
