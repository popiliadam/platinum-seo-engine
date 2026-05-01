---
name: monthly-report
description: |
  Use when: kullanıcı "aylık rapor", "monthly report", "ay sonu özet",
  "geçen ay neler oldu", "ay raporu üret", "aylık müşteri raporu",
  "monthly client report" der ya da /pseo-monthly çağırır.
  Also use when: ayın son iş gününde aktif proje için
  outputs/reports/{date}-monthly.md üretilecek; master.xlsx'te
  master_task / completed_work / gsc_performance / opportunity /
  content_decay / tech_seo / schema / new_content_plan /
  content_improve sheet'leri ay boyunca dolmuş; monthly-report.schema.json
  v1.0 formatında 10 zorunlu section + framing_policy "positive_client"
  default + output_formats subset of html|pdf|notion isteniyor; Phase 9
  reporting suite parçası, LOCAL aggregation (no MCP, no DFS).
  Do not use when: haftalık özet (weekly-summary), portföy genel raporu
  (portfolio-overview), portföy haftalık brief (portfolio-weekly-brief),
  drift kontrol (drift-check), tek-seferlik analiz isteniyorsa — bunların
  ayrı skill ve komutları vardır; master.xlsx yokken (DURUR
  WorkbookMissingError, init-project önce çalışmalı); paid MCP credit
  harcanması bekleniyorsa (bu skill 0 credit; DFS backlinks Phase 10+'ta
  ayrı skill üzerinden).
version: "1.0"
status: wip
category: reporting
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + events.jsonl."
  period_end:
    type: string
    required: false
    description: "ISO YYYY-MM-DD; default last business day of current month."
outputs:
  - "master.xlsx#none"
  - "outputs/reports/{date}-monthly.md"
  - "inbox/local/{date}-monthly-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "master-task-sync:master.xlsx#master_task"
  - "done-protocol:master.xlsx#completed_work"
  - "content-decay:master.xlsx#content_decay"
  - "tech-audit:master.xlsx#tech_seo"
  - "schema-audit:master.xlsx#schema"
  - "new-content-plan:master.xlsx#new_content_plan"
  - "gsc-pull:master.xlsx#gsc_performance"
  - "quick-wins:master.xlsx#opportunity"
produces:
  - "weekly-summary"
  - "portfolio-overview"
triggers:
  manual: ["/pseo-monthly"]
  natural_language: |
    "aylık rapor", "monthly report", "ay sonu özet",
    "geçen ay neler oldu", "ay raporu üret",
    "aylık müşteri raporu", "monthly client report"
  hooks: []
  scheduled:
    - cron: "0 9 28-31 * 1-5"
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

# monthly-report — reporting skill (Phase 9 Wave 1)

LOCAL aggregator: reads master.xlsx logical sheets + last-28-day events.jsonl
context (READ-ONLY) → emits a JSON report conforming to
`schemas/monthly-report.schema.json` v1.0 (10 required sections,
framing_policy default `positive_client`, output_formats subset of
`[html, pdf, notion]`, data_sources provenance).

This skill follows the **convention authority** established by
`skills/planning/master-task-sync/SKILL.md` (Phase 8 W-D1 — local
aggregation pattern). Per the Phase 9 W-E1 worker brief (REVIZE 1+2+3):

- `outputs[]` has exactly **3 entries** — `master.xlsx#none` (READ-ONLY
  confirm), `outputs/reports/{date}-monthly.md`, and
  `inbox/local/{date}-monthly-{slug}.json`. **No `events.jsonl` write.**
- `events.jsonl` is **READ-ONLY** for last-28-day work-event context;
  whether reporting runs are themselves audit-worthy events is
  **Q-RP-01**, deferred to Phase 14 governance refinement (manager OQ
  append at closeout).
- `master_task` is **READ-ONLY**; this skill never writes back. The
  `next_month_plan` section reads top-10 TODO rows.
- `mcp_tools.required = []` and `mcp_tools.optional = []`. The
  `mcp__gsc__search_analytics` tool MAY be invoked opportunistically by
  a future skill body for cross-check, but is not declared here because
  the LOCAL pipeline must run end-to-end without it (HIGH autonomy +
  cron-ready).
- `budget.uses_paid_mcp = false` and `estimated_credits = 0` (no DFS, no
  paid MCP, no Scrapling cloud).

## Inputs (frontmatter contract)

| Name           | Type   | Default                                | Notes                                                    |
|----------------|--------|----------------------------------------|----------------------------------------------------------|
| `project_slug` | string | —                                      | Required. Resolves `projects/{slug}/master.xlsx`.        |
| `period_end`   | string | last business day of current month     | ISO `YYYY-MM-DD`. `period_start = period_end - 27 days`. |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env var or an
explicit override (mirrors workflow_runner / events_writer / sibling
reporting skills).

## Outputs (artifacts produced)

- `master.xlsx#none` — declarative READ-ONLY confirmation. The transform
  contains zero `transaction.append` / `transaction.update` calls
  against `master_task` (or any other sheet); see acceptance gate #8.
- `projects/{slug}/outputs/reports/{period_end}-monthly.md` — rendered
  markdown via `string.Template` ($variable substitution; mirrors
  `scripts/reporting/render_template.py` contract).
- `projects/{slug}/inbox/local/{period_end}-monthly-{project_slug}.json`
  — drift-recovery snapshot of the full schema-shaped report dict.

## Sheets consumed (READ-ONLY)

| Sheet              | Producer skill         | Section feed                            |
|--------------------|------------------------|-----------------------------------------|
| `master_task`      | master-task-sync       | next_month_plan (top-10 TODO)           |
| `completed_work`   | done-protocol          | tech_seo_done / content_revised / new_content |
| `content_improve`  | content-decay          | pages_up auxiliary                      |
| `new_content_plan` | new-content-plan       | new_content auxiliary                   |
| `gsc_performance`  | gsc-pull               | gsc_positive_trends + pages_up          |
| `opportunity`      | quick-wins             | keywords_up                             |
| `content_decay`    | content-decay          | content_revised auxiliary               |
| `tech_seo`         | tech-audit             | tech_seo_done auxiliary                 |
| `schema`           | schema-audit           | content_revised auxiliary               |

`events.jsonl` (last 28 days) is read for contextual work-event
enrichment; never written.

## 10 Required Sections (schemas/monthly-report.schema.json line 31-42)

1. `exec_summary` — auto-generated from sections 2-7 headlines
2. `gsc_positive_trends` — current vs prior 28-day deltas
3. `keywords_up` — top-20 queries with positive position delta
4. `pages_up` — top-10 pages with positive clicks_delta
5. `tech_seo_done` — completed_work filtered by category prefix "tech"
6. `content_revised` — completed_work filtered by category prefix "revis"
7. `new_content` — completed_work filtered by category prefix "new"
8. `competitor_snapshot` — Phase 10+ Scrapling S1/S3 (empty shape now)
9. `backlink_delta` — paid DFS MCP (zero shape; this skill = LOCAL only)
10. `next_month_plan` — top-10 TODO rows from master_task by priority

`framing_policy` defaults to `positive_client` (§22.3): wins
foregrounded; declining metrics routed into `next_month_plan` action
list rather than broken out as a negative section. The `internal`
framing surfaces both sides (used by manager / engineering review).

## DURUR conditions (8 + base)

Stop and flag the manager — do not patch, do not fall back.

1. **FramingPolicyEnumViolation** — value not in `{positive_client, internal}`.
2. **OutputFormatEnumViolation** — value not in `{html, pdf, notion}`.
3. **DataSourceEnumViolation** — value not in 7-value enum.
4. **MissingSectionError** — assembler dropped a required section.
5. **ProjectIdShapeError** — `project_id` fails `^[a-z][a-z0-9-]*$`.
6. **WorkbookMissingError** — `projects/{slug}/master.xlsx` not found.
7. **TemplateRenderError** — `string.Template.substitute` raised
   KeyError (missing `$key`) or ValueError (bad syntax).
8. **MonthlyReportError** (base) — invalid `period_end`, openpyxl
   missing, etc. Always surfaced with a descriptive message.

## Cross-references

- Schemas: `schemas/monthly-report.schema.json` (10 required sections +
  framing_policy enum + output_formats enum + data_sources enum),
  `schemas/master-excel.schema.json` (sheet shapes for the 9 consumed
  sheets), `schemas/skill-frontmatter.schema.json` (this frontmatter),
  `schemas/events.schema.json` (events.jsonl shape; READ-ONLY contract).
- Cross-modules (IMPORT-only): `scripts/reporting/render_template.py`
  (Phase 1 mirası, `string.Template` substitution).
- Transform: `scripts/reporting/monthly_report.py`.
- Template: `templates/reports/monthly-report.template.md`.
- Tests: `tests/skills/test_monthly_report.py` (8-10 tests; schema
  validate output JSON + sentinel + edge case + forbidden-token grep).
- Pattern reference: `scripts/planning/master_task_sync.py` (Phase 8
  W-D1 local aggregation pure-transform pattern; reused verbatim).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Output JSON
      validates against `schemas/monthly-report.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when` are
      STRING content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `render_template.py` is
      referenced by contract (string.Template), not modified.
- [x] D-003 helper IMPORT NOT applicable — local aggregation, no DFS
      payload is consumed (intentionally absent — documented above).
- [x] F1: artifact paths use `master.xlsx` (lowercase, schema-shaped);
      this skill writes ZERO sheets — `master.xlsx#none` is declarative.
- [x] F5: any string-typed CLI outputs are stringified explicitly.
- [x] Append-only state — `events.jsonl` is READ-ONLY here. Q-RP-01
      defers the "are reports audit-worthy" question to Phase 14.
- [x] Idempotency — same inputs (modulo `generated_at`) → byte-identical
      report dict (asserted by test_monthly_report.py smoke test).
- [x] LOCAL aggregation budget envelope: `uses_paid_mcp=false`,
      `estimated_credits=0`, `safe_auto_execute=true` (cron-ready).
