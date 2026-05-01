---
name: weekly-summary
description: |
  Use when: kullanıcı "haftalık özet", "weekly summary", "geçen hafta",
  "bu haftaki delta", "haftalık rapor", "haftalık SEO özeti", "bu
  haftaki ne yapıldı", "haftalık task özeti", "weekly progress",
  "last week recap" der ya da haftalık rapor ister.
  Also use when: Phase 7+8 master writer skill'leri haftalık şekilde
  çalışmış; master_task SSoT son 7 günde güncellenmiş; cron tetiği
  her Pazartesi sabah haftalık özet rapor üretmek isterse; portföy
  brief'i veya monthly-report'a girdi olacak haftalık snapshot lazım.
  Do not use when: master.xlsx yokken (init-project önce çalışmalı —
  WorkbookMissingError); master_task hiç yazılmamış (önce
  master-task-sync veya bir Phase 7/8 master writer); aylık dilim
  rapor isteniyor (monthly-report kullan); portföy seviyesinde
  multi-project özet isteniyor (portfolio-overview /
  portfolio-weekly-brief kullan); ham GSC delta gerekiyor
  (monthly-report scope; weekly-summary LOCAL aggregation).
version: "1.0"
status: wip
category: reporting
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + _state/events.jsonl."
  week_end:
    type: string
    required: false
    description: "Inclusive ISO date YYYY-MM-DD for the week end. Default: today snapped to the most recent Sunday."
outputs:
  - "master.xlsx#none"
  - "outputs/reports/{date}-weekly-summary.md"
  - "inbox/local/{date}-weekly-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "master-task-sync:master.xlsx#master_task"
  - "quick-wins:master.xlsx#quick_wins"
  - "quick-wins:master.xlsx#opportunity"
  - "content-decay:master.xlsx#content_decay"
  - "events_writer:_state/events.jsonl"
produces:
  - "monthly-report"
  - "portfolio-weekly-brief"
triggers:
  manual: []
  natural_language: "haftalık özet, weekly summary, geçen hafta, bu haftaki delta, haftalık rapor, weekly recap, last week"
  hooks: []
  scheduled:
    - cron: "0 7 * * 1"
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

# weekly-summary — reporting skill (Phase 9 Wave 1)

LOCAL aggregation skill: reads `master.xlsx` + `_state/events.jsonl`,
emits a 7-day rolling-window markdown report + a drift-recovery JSON
snapshot. **No MCP**, **no DFS**, **no budget pre-flight** — purely a
local read + render skill that runs cron-safe (every Monday 07:00 UTC
by default) without human approval.

This skill follows the convention authority of
`skills/planning/master-task-sync/SKILL.md` (Phase 8 W-D1 — local
aggregation pattern + master.xlsx READ-ONLY discipline) and reuses
`scripts/reporting/render_template.py` (Phase 1 mirası — string.Template
`$var` substitution). REVIZE 1+2+3 apply: 3-entry outputs, no
events_writer reuse, no events.jsonl write.

Unlike `master-task-sync` which APPENDS auto_generated rows + MERGES the
D column on `master.xlsx#master_task`, this skill is **strictly
READ-ONLY** w.r.t. the workbook — the `outputs[0]` value
`"master.xlsx#none"` is the explicit READ-ONLY confirmation marker per
the worker brief.

## Inputs (frontmatter contract)

| Name           | Type   | Default        | Notes                                                              |
|----------------|--------|----------------|--------------------------------------------------------------------|
| `project_slug` | string | —              | Required. Resolves `projects/{slug}/master.xlsx`.                  |
| `week_end`     | string | last Sunday    | Inclusive end of the 7-day window. Snaps to Sunday if not Sunday.  |

`workspace_root` is resolved via the CLI `--workspace-root` arg or by
the skill body via `PSEO_WORKSPACE_ROOT` env (mirrors the workflow
runner discipline).

## Outputs (artifacts produced — REVIZE 1: 3 entries, NO events.jsonl)

- `master.xlsx#none` — READ-ONLY confirm. This skill does NOT write to
  any sheet on `master.xlsx`. Surfaced as an outputs entry so the
  glossary-audit dependency graph can verify the read-only contract.
- `projects/{slug}/outputs/reports/{date}-weekly-summary.md` — the
  human-readable 5-section weekly summary.
- `projects/{slug}/inbox/local/{date}-weekly-{slug}.json` —
  drift-recovery snapshot with the full batch payload.

## Output sections (5 — monthly-report SUBSET, NO schema this Wave)

1. `exec_summary` — 1-2 sentence Turkish rollup of the week (n_done,
   n_added, drift_total).
2. `gsc_weekly_delta` — LOCAL approximation: count of work events in
   window + open quick_wins / opportunity / content_decay rows.
   Wave 1 does NOT call MCP; the full GSC-based delta lives in the
   `monthly-report` skill (which pulls from cached `inbox/gsc/`).
3. `tasks_done` — `master_task` rows where `status=DONE` AND
   `done_date` ∈ window.
4. `tasks_added` — `master_task` rows where `created_date` ∈ window.
5. `drift_signals` — counts of `opportunity`, `quick_wins`,
   `content_decay` rows present in the workbook (proxy for "open
   drift items"; true drift-check is `governance/drift-check`).

The 5-section tuple is the structural contract this Wave (no schema
file). The transform exposes `WEEKLY_SUMMARY_SECTIONS` and the test
suite asserts `WeeklySummaryBatch.as_dict()` carries every key.

## Upstream sources consumed (READ-ONLY)

| # | Source                          | Purpose                                  |
|---|---------------------------------|------------------------------------------|
| 1 | `master.xlsx#master_task`       | task_done / task_added filters           |
| 2 | `master.xlsx#opportunity`       | drift_signals.opportunity_rows           |
| 3 | `master.xlsx#quick_wins`        | drift_signals.quick_wins_rows            |
| 4 | `master.xlsx#content_decay`     | drift_signals.content_decay_rows         |
| 5 | `_state/events.jsonl`           | gsc_weekly_delta.work_events_in_window   |

## Window logic

- `week_end` defaults to `date.today()` snapped to the most recent
  Sunday (inclusive). Sundays remain unchanged.
- `week_start = week_end - 6 days`. Window is inclusive on both ends
  (7 days total).
- `tasks_done` filters on `done_date`; `tasks_added` filters on
  `created_date`; events filter on `timestamp`.

## DURUR conditions

Stop and surface to the manager — do not patch, do not silently swallow.

1. **WorkbookMissingError** — `projects/{slug}/master.xlsx` absent.
   Run `init-project` first.
2. **WorkspaceRootUnsetError** — workspace_root unresolvable via
   env or arg.
3. **TemplateMissingError** — `templates/reports/weekly-summary.template.md`
   not on disk.
4. **WeeklySummaryError** — generic envelope (bad project_slug shape,
   etc.).

(No schema enum DURUR this Wave — the output shape has no schema.)

## Cross-references

- Schemas: `schemas/master-excel.schema.json` (master_task / opportunity
  / quick_wins / content_decay sheet shapes for read-only access),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (READ-only, IMPORT pattern):
  `scripts/reporting/render_template.py` (string.Template $var rendering
  reuse; this skill calls `string.Template` directly inside
  `build_report_markdown`).
- Transform: `scripts/reporting/weekly_summary.py`.
- Template: `templates/reports/weekly-summary.template.md`.
- Tests: `tests/skills/test_weekly_summary.py`.
- Pattern reference: `skills/planning/master-task-sync/SKILL.md`
  (Phase 8 W-D1 — local aggregation skill convention).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises a typed exception.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` (Draft 7). Output sections
      have NO schema this Wave (deliberate; brief-defer per worker
      brief).
- [x] Plugin-agnostik — no slug literals in transform; `project_slug`
      flows through every path.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `render_template` is reused via
      `string.Template` direct call (no monkey-patching).
- [x] Append-only state — this skill writes ONLY to
      `outputs/reports/` + `inbox/local/`. NEVER mutates `master.xlsx`
      or `events.jsonl` (REVIZE 3 — Q-RP-01 deferred to Phase 14
      governance refinement).
- [x] Idempotency: same workbook + frozen events + frozen clock →
      byte-stable report + snapshot.
- [x] Forbidden tokens (4): grep CLEAN of the per-call / per-url credit
      tokens, the legacy metric-naming field tossed in Phase 7 closeout,
      hardcoded project slugs, and orphan code-comment markers
      (test enforces).
- [x] natural_language sentinel: ≥30 char (test enforces).
