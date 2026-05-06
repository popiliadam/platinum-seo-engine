---
name: portfolio-monthly-roundup
description: |
  Use when: kullanıcı "aylık portföy", "portfolio monthly roundup",
  "tüm projeler aylık", "aylık roundup", "monthly roundup", "portföy
  aylık özet", "active_projects aylık rapor" der ya da
  cadence.monthly_roundup.day_of_month cron tetiklenir; portföy
  çapında bir aylık KPI roll-up + EditorialOverrides notları
  istendiğinde devreye girer.
  Also use when: portfolio.config.json v1.1 mevcut + active_projects
  doluyken (1-8 entry, schema maxItems=8); her aktif proje için
  master.xlsx ulaşılabilir; aylık 30 günlük dilim üzerinden
  exec_summary + keywords_up + pages_up + tech_seo_done +
  content_revised + new_content + next_month_plan toplaması
  istenir; per-project EditorialOverrides (sla_days / priority /
  cadence / override_rationale / ramp_plan) precedence ile
  raporlanır; READ-ONLY agregasyon yeterli (yazma kapsamı YOK).
  Do not use when: portfolio.config.json yokken (init-portfolio önce
  çalışmalı, DURUR PortfolioConfigMissingError); tek proje aylık
  istenirse (monthly-report skill'ine yönlendir, bu skill PORTFÖY
  scope); haftalık dökümle karıştırma (portfolio-weekly-brief
  skill'i ayrı); master.xlsx writer çağrısı isteniyorsa (FORBIDDEN
  — bu skill 100% READ-ONLY, hiçbir master_task hücresine yazmaz).
version: "1.0"
status: active
category: reporting
inputs:
  portfolio_root:
    type: string
    required: false
    description: "Path to portfolio workspace root. Default: $PSEO_WORKSPACE_ROOT or .pse-workspace marker discovery."
  period_end:
    type: string
    required: false
    description: "ISO date override (YYYY-MM-DD). Default: most recent occurrence of cadence.monthly_roundup.day_of_month on or before today (UTC)."
outputs:
  - "master.xlsx#none"
  - "projects/_portfolio/outputs/reports/{date}-portfolio-monthly-roundup.md"
  - "projects/_portfolio/inbox/local/{date}-portfolio-monthly-roundup.json"
consumes:
  - "init-portfolio:projects/_portfolio/portfolio.config.json"
  - "per-project:master.xlsx#dashboard"
  - "per-project:master.xlsx#completed_work"
  - "per-project:master.xlsx#new_content_plan"
  - "per-project:_state/events.jsonl"
produces:
  - "portfolio-overview"
  - "portfolio-weekly-brief"
triggers:
  manual: []
  natural_language: "aylık portföy, portfolio monthly roundup, tüm projeler aylık, aylık roundup, monthly roundup, portföy aylık özet, active_projects aylık rapor"
  hooks: []
  scheduled: []
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

# portfolio-monthly-roundup — reporting skill (Phase 9 Wave 2)

Multi-project LOCAL aggregator for the **monthly** cadence. Reads
`projects/_portfolio/portfolio.config.json` v1.1, iterates
`active_projects[]`, and for each project emits a 30-day roll-up
covering the 7-section subset of `monthly-report.schema.json`
(exec_summary + keywords_up + pages_up + tech_seo_done +
content_revised + new_content + next_month_plan) plus per-project
**EditorialOverrides** (sla_days / priority / cadence /
override_rationale / ramp_plan) surfaced via precedence rules.

This skill follows the **convention authority** established by
`skills/planning/master-task-sync/SKILL.md` (Phase 8 W-D1 — pure
function transform + READ-ONLY discipline + plugin-agnostik) and
inherits the Wave 1 path convention from
`skills/reporting/portfolio-weekly-brief/SKILL.md` and the
read-only grep-guard from
`skills/reporting/portfolio-overview/SKILL.md`. The discipline
(DURUR raises, no silent fallback, schema-first, plugin agnostik,
append-only state contract) is reused verbatim. Deviate only with
an ADR.

Unlike Phase 8 master_task_sync, this skill **never writes** to any
project's `master.xlsx` or `_state/events.jsonl`. Outputs land
exclusively under the portfolio workspace
(`projects/_portfolio/outputs/reports/` + `inbox/local/`).

## Inputs (frontmatter contract)

| Name             | Type   | Default | Notes                                                                                                  |
|------------------|--------|---------|--------------------------------------------------------------------------------------------------------|
| `portfolio_root` | string | env     | Optional. Defaults to `PSEO_WORKSPACE_ROOT` env or `.pse-workspace` marker discovery.                  |
| `period_end`     | string | —       | Optional ISO date override (YYYY-MM-DD). Default: most recent `cadence.monthly_roundup.day_of_month`.  |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or
explicit test override (mirrors workflow_runner / events_writer /
W-D1 / W-E3 / W-E4).

## Outputs (artifacts produced)

- `master.xlsx#none` — sentinel acknowledging that the skill READS
  per-project `master.xlsx#dashboard` + `#completed_work` +
  `#new_content_plan` but writes ZERO cells anywhere. The
  frontmatter `outputs[]` entry is intentional schema documentation
  (no openpyxl mutation, no transaction layer call).
- `projects/_portfolio/outputs/reports/{period_end}-portfolio-monthly-roundup.md`
  — human-readable Markdown roundup (multi-project monthly KPI
  roll-up table + EditorialOverrides notes section + totals).
- `projects/_portfolio/inbox/local/{period_end}-portfolio-monthly-roundup.json`
  — drift-recovery snapshot; full PortfolioMonthlyRoundup envelope
  including per-project rollups + override precedence + totals.

## Path convention (W-E4 reuse)

The literal `projects/_portfolio/{outputs,inbox}/local/` prefix
appears in the transform module — paths are **NEVER** synthesized
from a slug template. `workspace_root` resolution order:

1. Explicit `--workspace-root` CLI flag (test override).
2. `PSEO_WORKSPACE_ROOT` environment variable.
3. `.pse-workspace` marker walk-up from `cwd`.

If all three fail → `WorkspaceRootUnsetError` (DURUR).

## Consumed (READ-ONLY)

| # | Source                                          | Discipline                                                       |
|---|-------------------------------------------------|------------------------------------------------------------------|
| 1 | `portfolio.config.json` v1.1                    | active_projects + cadence.monthly_roundup + EditorialOverrides   |
| 2 | per-project `master.xlsx#dashboard`             | KPI cells (R10, R47-R52, R59) — `read_only=True, data_only=True` |
| 3 | per-project `master.xlsx#completed_work`        | columns A-F (id, task_or_content, url, date, category, note)     |
| 4 | per-project `master.xlsx#new_content_plan`      | columns A-K (id, title, …, lifecycle_status)                     |
| 5 | per-project `_state/events.jsonl`               | event_kind=work, last 30 days only                               |

## Schema authority

`schemas/portfolio-config.schema.json` v1.1:

- `cadence.monthly_roundup.day_of_month` — integer 1-31 (drives
  default `period_end`).
- `cadence.monthly_roundup.hour` — integer 0-23 (advisory, used by
  the scheduler — not by this transform).
- `EditorialOverrides.sla_days` — integer 1-30 (per-project
  override of `slas.weekly_sync_max_days`).
- `EditorialOverrides.priority` — integer 1-10 (per-project
  override of `priority`; precedence over `ActiveProjectEntry.priority`).
- `EditorialOverrides.cadence` — enum [weekly, biweekly, monthly]
  (per-project override of report cadence).
- `EditorialOverrides.override_rationale` — string `minLength: 10`
  (MANDATORY when any other EditorialOverrides field is set; the
  transform raises `EditorialOverrideRationaleError` on a payload
  shorter than 10 characters even if jsonschema validation is
  skipped).
- `EditorialOverrides.ramp_plan` — string (optional retirement
  plan).

`schemas/monthly-report.schema.json` v1.0 — 7-section subset reused
for the per-project roll-up:

- `exec_summary` (narrative + headlines).
- `keywords_up` (improved positions, top-N).
- `pages_up` (clicks/impressions delta gains, top-N).
- `tech_seo_done` (completed_work entries with category `tech_seo`).
- `content_revised` (completed_work entries with category `content_revise`).
- `new_content` (completed_work entries with category `content_new`).
- `next_month_plan` (priority-sorted top-10 master_task TODO).

(`gsc_positive_trends`, `competitor_snapshot`, `backlink_delta`
are intentionally excluded — they require GSC/DFS pulls that this
local-aggregation skill does not perform.)

The transform raises `PortfolioConfigSchemaError` (DURUR) if any
of these fields drift from the schema. Tests assert the cadence /
EditorialOverrides branches against the canonical Draft 7 schema.

## Transform contract

`scripts/reporting/portfolio_monthly_roundup.py` (pure function,
< 600 lines per ADR-027):

- `build_portfolio_roundup(portfolio_config, workspace_root, now,
  period_end=None) -> PortfolioMonthlyRoundup` — top-level
  idempotent aggregator.
- `aggregate_project(...)  -> ProjectRollup` — one project's
  30-day rollup including override-resolved priority + cadence.
- `resolve_editorial_overrides(entry, portfolio_priority) ->
  ResolvedOverrides` — isolated precedence logic (test sentinel).
- `read_events_in_window(events_path, ...)` — fault-tolerant
  events.jsonl reader (last 30 days).
- `read_dashboard_kpis(workbook_path)` — openpyxl thin wrapper,
  `read_only=True`, INLINE (no shared excel helper imported).
- `read_completed_work_window(workbook_path, window_start,
  window_end)` — same READ-ONLY discipline.
- `render_roundup_markdown(roundup, template_path)` —
  string.Template `$var` substitution, matches
  `scripts/reporting/render_template.py` engine.
- `assert_read_only_module()` — source-grep helper that fails when
  any forbidden write call site appears (W-E3 paterni reuse).

## Template

`templates/reports/portfolio-monthly-roundup.template.md` —
Markdown with YAML frontmatter (`period_start`, `period_end`,
`generated_at`, `scope`, `projects_count`). Body includes:

- `$totals_summary` — single-line rollup sentence.
- `$projects_kpi_table` — multi-row Markdown table with columns
  `slug | priority | cadence | tasks_done | new_content |
  content_revised | tech_seo_done | next_month_priority`.
- `$editorial_overrides_notes` — per-project override rationale
  block (only renders projects with active overrides).
- Totals breakdown table (tasks_done / new_content /
  content_revised / tech_seo_done).

`string.Template` engine (NOT jinja2) — same as
`scripts/reporting/render_template.py` (Phase 1 mirası). All
variables are stringified by `build_template_vars()` so the
template engine never sees a non-string value.

## EditorialOverrides precedence semantics

```
For each active_projects entry:
  effective_priority  = entry.editorial_overrides.priority
                        if isset else entry.priority
  effective_cadence   = entry.editorial_overrides.cadence
                        if isset else "monthly"
  effective_sla_days  = entry.editorial_overrides.sla_days
                        if isset else slas.weekly_sync_max_days

Constraint: any EditorialOverrides override field set =>
            override_rationale required + minLength 10.
            Schema validates; transform raises
            EditorialOverrideRationaleError on a 9-char rationale.
```

The per-project overrides are surfaced in the
`$editorial_overrides_notes` section of the markdown report and in
`overrides_resolved` of the JSON snapshot.

## DURUR conditions

Stop and flag the manager — do not patch, do not fall back.

1. **PortfolioConfigMissingError** — `portfolio.config.json` absent
   / unreadable. Run portfolio init first.
2. **PortfolioConfigInvalidError** — payload failed Draft 7
   validation against `schemas/portfolio-config.schema.json`.
3. **ActiveProjectsCeilingError** — `active_projects` > 8 (schema
   `maxItems` sentinel). Move surplus to `pending_onboard`.
4. **ReadOnlyContractViolation** — `cross_query.read_only != true`
   (schema `const: true`) OR transform module contains a forbidden
   write call site (`assert_read_only_module()` grep guard).
5. **WorkspaceRootUnsetError** — `PSEO_WORKSPACE_ROOT` env unset
   AND no explicit `workspace_root` passed AND no `.pse-workspace`
   marker discoverable from cwd.

(Per-project missing `master.xlsx` is **NOT** a DURUR — graceful
skip with warning, snapshot still emitted.)

## Idempotency contract

> **Re-run with identical workbook + events.jsonl + portfolio
> config + same `now` → byte-identical snapshot + report.**

Mechanically:

1. Project ordering is deterministic — sort by
   `(effective_priority, slug)`.
2. JSON output uses `sort_keys=True` + `indent=2`.
3. `generated_at` is microsecond-truncated to second precision.
4. Template substitution is purely positional (no current-time
   reads inside the template).

## READ-ONLY discipline

- NO `transaction.append` / `transaction.update` /
  `transaction.delete` calls anywhere.
- NO `events_writer.append_*` calls anywhere (Q-RP-01 governance
  refinement deferred to Phase 14 — this skill DOES NOT write
  events.jsonl).
- `openpyxl.load_workbook(read_only=True, data_only=True)` for
  every workbook open.
- `master.xlsx#none` outputs[] entry documents the READ-ONLY
  contract: no logical sheet is touched.
- `assert_read_only_module()` greps the transform source for the
  forbidden token set: `transaction.*`, `events_writer.*`,
  `.save()`, `.delete()`, `.append(`. Test suite invokes this
  helper as gate #11.

## Plugin agnostik

- Project slugs flow in via
  `portfolio.config.json.active_projects[].slug`.
- Zero hardcoded slug literals in the transform module (asserted
  by the worker brief acceptance gate #9 + the skill test suite's
  base64-obfuscated grep guard against the 8-slug forbidden list).

## Audit Event Emit (Q-RP-01 RESOLVED 2026-05-06 Phase B post-closeout)

Schema-first override Section 4c paterni reuse (drift-check Phase 5 doğum belgesi). `event_kind=audit` row append per `rules/events-writer.md` Section 4c — `event_type` field YASAK per Section 6 disambiguation.

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

project_slug = os.environ.get("PSEO_PROJECT_ID")
if not project_slug:
    print("PSEO_PROJECT_ID not set — audit event skip")
    sys.exit(0)
report_date = os.environ.get("REPORT_DATE", "2026-05-06")

workspace_root_env = os.environ.get("PSEO_WORKSPACE_ROOT")
workspace_root = (
    Path(workspace_root_env) if workspace_root_env
    else Path.home() / "Documents" / "platinum-seo-workspace"
)

from scripts.state import events_writer
events_writer.append_audit(
    project_id=project_slug,
    audit_action="accessed",
    audit_target=f"reports:portfolio-monthly-roundup:{report_date}",
    actor="agent:portfolio-monthly-roundup",
    workspace_root=workspace_root,
    notes=f"local_aggregation report-only (portfolio-monthly-roundup; date={report_date})",
)
```

## Cross-references

- Schemas: `schemas/portfolio-config.schema.json` v1.1
  (cadence.monthly_roundup branch + EditorialOverrides
  precedence), `schemas/monthly-report.schema.json` v1.0 (7-section
  subset reuse), `schemas/skill-frontmatter.schema.json` (this
  frontmatter validates against it).
- Cross-modules (IMPORT-only): `scripts/reporting/render_template.py`
  (`string.Template` $var rendering convention — re-instantiated
  inline in `render_roundup_markdown` for purity). NO
  `transaction.py`, NO `events_writer.py`, NO `workflow_runner.py`
  imports.
- Transform: `scripts/reporting/portfolio_monthly_roundup.py`.
- Template: `templates/reports/portfolio-monthly-roundup.template.md`.
- Tests: `tests/skills/test_portfolio_monthly_roundup.py` (8-10
  cases incl. cadence schema validate, EditorialOverrides
  precedence sentinel, override_rationale minLength 10 sentinel,
  multi-project KPI roll-up, missing project tolerance, 30-day
  events filter, natural_language min length, forbidden tokens
  guard, READ-ONLY grep guard, path convention).
- Pattern reference: `scripts/reporting/portfolio_weekly_brief.py`
  (Phase 9 W-E4 — path convention + workspace_root resolver) +
  `scripts/reporting/portfolio_overview.py` (Phase 9 W-E3 —
  assert_read_only_module helper + 5 DURUR exception classes).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently
      downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7; cadence +
      EditorialOverrides branches validated against
      `portfolio-config.schema.json` v1.1.
- [x] Plugin-agnostik — no slug literals; slugs flow from
      portfolio.config.json.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when`
      are STRING content inside `description`, not separate fields.
- [x] READ-ONLY — zero `transaction.*` / `events_writer.*`
      imports in the transform module (W-E3 helper grep guard).
- [x] Append-only state — events.jsonl is READ-only consumed; this
      skill does NOT append (Q-RP-01 defer Phase 14).
- [x] Idempotency contract — same inputs + same `now` → byte-stable
      output (asserted by smoke test).
- [x] Forbidden tokens (4 grep CLEAN): the four Phase 7+ lesson
      tokens and the 8-slug forbidden list are absent; transform
      contains no leftover task markers in code.
- [x] natural_language phrases >= 30 char (min length sentinel
      asserted by test).
- [x] line count gate < 600 (transform).
- [x] W-E4 path convention compliance:
      `projects/_portfolio/{outputs,inbox}/local/` literal in
      transform + `PSEO_WORKSPACE_ROOT` env resolution + per-skill
      `test_path_convention` sentinel.
- [x] EditorialOverrides override_rationale `minLength 10`
      sentinel test — rejects 9-char payload.
