---
name: portfolio-weekly-brief
description: |
  Use when: kullanıcı "haftalık portföy", "portfolio weekly", "tüm
  projeler haftalık", "haftalık brief", "weekly brief", "portföy
  haftalık raporu", "active_projects haftalık özet" der ya da
  cadence.weekly_brief.day cron tetiklenir.
  Also use when: portfolio.config.json v1.1 mevcut + active_projects
  doldurulmuş; her proje için master.xlsx + _state/events.jsonl
  ulaşılabilir; haftalık 7 günlük delta + last_sync_at freshness
  rapor olarak istenir; tek bir slug değil PORTFÖY ÇAPINDA özet
  beklenir; READ-ONLY agregasyon yeterli (yazma kapsamı YOK).
  Do not use when: portfolio.config.json yokken (init-portfolio önce
  çalışmalı, DURUR PortfolioConfigSchemaError); tek proje weekly
  istenirse (weekly-summary skill'ine yönlendir, bu skill PORTFÖY
  scope); aylık dökümle karıştırma (monthly-report skill'i ayrı);
  master.xlsx writer çağrısı isteniyorsa (FORBIDDEN — bu skill 100%
  READ-ONLY, hiçbir master_task hücresine yazmaz).
version: "1.0"
status: wip
category: reporting
inputs:
  portfolio_root:
    type: string
    required: false
    description: "Optional path override; defaults to projects/_portfolio/ under PSEO_WORKSPACE_ROOT."
  week_end:
    type: string
    required: false
    description: "ISO date override (YYYY-MM-DD). Default: cadence.weekly_brief.day's most recent occurrence on or before today (UTC)."
outputs:
  - "master.xlsx#none"
  - "outputs/reports/{date}-portfolio-weekly-brief.md"
  - "inbox/local/{date}-portfolio-weekly-brief.json"
consumes:
  - "init-portfolio:projects/_portfolio/portfolio.config.json"
  - "per-project:master.xlsx#master_task"
  - "per-project:_state/events.jsonl"
produces:
  - "monthly-report"
  - "portfolio-overview"
triggers:
  manual: []
  natural_language: "haftalık portföy, portfolio weekly, tüm projeler haftalık, haftalık brief, weekly brief, portföy haftalık raporu, active_projects haftalık özet"
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

# portfolio-weekly-brief — reporting skill (Phase 9 Wave 1)

Multi-project LOCAL aggregator. Reads `projects/_portfolio/portfolio.config.json`
v1.1, iterates `active_projects[]`, and for each project emits a 7-day
delta (`tasks_added`, `tasks_done`, `work_events`) plus a
`freshness_flag` (`fresh` | `stale`) computed from `last_sync_at`
versus `slas.weekly_sync_max_days`.

This skill follows the **convention authority** established by
`skills/planning/master-task-sync/SKILL.md` (Phase 8 Wave 2 — pure
function transform + READ-ONLY discipline + plugin-agnostik). The
discipline (DURUR raises, no silent fallback, schema-first, plugin
agnostik, append-only state contract) is reused verbatim. Deviate
only with an ADR.

Unlike Phase 8 master_task_sync, this skill **never writes** to any
project's `master.xlsx` or `_state/events.jsonl`. Outputs land
exclusively under the portfolio workspace
(`projects/_portfolio/outputs/reports/` + `inbox/local/`).

## Inputs (frontmatter contract)

| Name             | Type   | Default | Notes                                                             |
|------------------|--------|---------|-------------------------------------------------------------------|
| `portfolio_root` | string | —       | Optional. Defaults to `projects/_portfolio/` under workspace root. |
| `week_end`       | string | —       | Optional ISO date override (YYYY-MM-DD).                          |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer / W-D1).

## Outputs (artifacts produced)

- `master.xlsx#none` — sentinel acknowledging that the skill READS
  `master.xlsx#master_task` from each active project but writes
  ZERO cells anywhere. The frontmatter outputs[] entry is intentional
  schema documentation (no openpyxl mutation, no transaction layer
  call).
- `projects/_portfolio/outputs/reports/{week_end}-portfolio-weekly-brief.md`
  — human-readable Markdown brief (multi-project delta table +
  freshness flag column + totals).
- `projects/_portfolio/inbox/local/{week_end}-portfolio-weekly-brief.json`
  — drift-recovery snapshot; full PortfolioBrief envelope including
  per-project deltas + totals + sla band.

## Consumed (READ-ONLY)

| # | Source                                    | Discipline                          |
|---|-------------------------------------------|-------------------------------------|
| 1 | `portfolio.config.json` v1.1              | active_projects + cadence + slas    |
| 2 | per-project `master.xlsx#master_task`     | created_date / done_date in window  |
| 3 | per-project `_state/events.jsonl`         | event_kind=work, last 7 days        |
| 4 | per-project `last_sync_at` (config field) | freshness vs `weekly_sync_max_days` |

## Schema authority

`schemas/portfolio-config.schema.json` v1.1:

- `cadence.weekly_brief.day` — enum [Monday..Sunday] (drives default
  `week_end`).
- `cadence.weekly_brief.hour` — integer 0-23 (advisory, used by the
  scheduler — not by this transform).
- `slas.weekly_sync_max_days` — integer 1-30 (drives the freshness
  threshold).
- `active_projects[].last_sync_at` — ISO timestamp expected; null →
  always `stale`.
- `editorial_overrides.sla_days` — per-project SLA override (1-30);
  takes precedence over `slas.weekly_sync_max_days`.

The transform raises `PortfolioConfigSchemaError` (DURUR) if any of
these fields drift from the schema. Tests assert the cadence/sla
branches against the canonical Draft 7 schema.

## Transform contract

`scripts/reporting/portfolio_weekly_brief.py` (pure function, < 600
lines per ADR-027):

- `build_portfolio_brief(portfolio_config, workspace_root, now,
  week_end=None) -> PortfolioBrief` — top-level idempotent aggregator.
- `aggregate_project(...)  -> ProjectDelta` — one project's 7-day
  rollup.
- `compute_freshness_flag(last_sync_at, sla_days, now) -> str` —
  isolated freshness logic (test sentinel).
- `read_events_in_window(events_path, ...)` — fault-tolerant
  events.jsonl reader.
- `read_master_task_delta(workbook_path, window_start, window_end)` —
  openpyxl thin wrapper, `read_only=True`, INLINE (no shared excel
  helper imported).
- `render_brief_markdown(brief, template_path)` — string.Template
  `$var` substitution, matches `scripts/reporting/render_template.py`
  engine.

## Template

`templates/reports/portfolio-weekly-brief.template.md` — Markdown with
YAML frontmatter (`week_start`, `week_end`, `generated_at`,
`scope`, `sla_weekly_sync_max_days`, `projects_count`). Body
includes:

- `$totals_summary` — single-line rollup sentence.
- `$projects_delta_table` — multi-row Markdown table with columns
  `slug | tasks_added | tasks_done | last_sync_at | freshness_flag`.
- Totals breakdown table (tasks_added / tasks_done / work_events /
  fresh / stale projects).

`string.Template` engine (NOT jinja2) — same as
`scripts/reporting/render_template.py` (Phase 1 mirası). All variables
are stringified by `build_template_vars()` so the template engine
never sees a non-string value.

## Freshness flag semantics

```
last_sync_at = None or "":          → "stale"  (never synced)
sla_days < 1 or > 30:               → FreshnessFlagInputError (DURUR)
now - last_sync_at > sla_days:      → "stale"
otherwise:                          → "fresh"
```

`now` is passed in (UTC, timezone-aware) so the computation is
reproducible across machines + test harnesses. The acceptance gate
sentinel: `last_sync_at = (now - 8 days), sla = 7 → flag == "stale"`
is asserted by `tests/skills/test_portfolio_weekly_brief.py`.

## DURUR conditions

Stop and flag the manager — do not patch, do not fall back.

1. **PortfolioConfigSchemaError** — `portfolio.config.json` missing
   `cadence` or `slas`, or `cadence.weekly_brief.day` not in the
   weekday enum, or `slas.weekly_sync_max_days` out of [1, 30], or
   `active_projects` empty / missing slug.
2. **WeekEndParseError** — caller-supplied `week_end` is not a valid
   ISO date OR the cadence-derived week_end could not be computed.
3. **WorkspaceRootUnsetError** — `PSEO_WORKSPACE_ROOT` env var unset
   AND no explicit `workspace_root` passed.
4. **FreshnessFlagInputError** — `last_sync_at` malformed, OR
   `sla_days` out of range, OR `now` is naive (timezone-unaware).

## Idempotency contract

Same `portfolio.config.json` + same per-project `master.xlsx`
snapshot + same per-project `events.jsonl` snapshot + same `now` →
byte-identical PortfolioBrief tuple → byte-identical Markdown + JSON
output. `deltas.sort(key=lambda d: d.slug)` enforces deterministic
project order; `generated_at` is microsecond-truncated to second
precision.

## READ-ONLY discipline

- NO `transaction.append` / `transaction.update` calls anywhere.
- NO `events_writer.append_*` calls anywhere (REVIZE 3 of the Phase 9
  brief; Q-RP-01 governance refinement deferred to Phase 14).
- `openpyxl.load_workbook(read_only=True, data_only=True)` for every
  master.xlsx open.
- `master.xlsx#none` outputs[] entry documents the READ-ONLY
  contract: no logical sheet is touched.

## Plugin agnostik

- Project slugs flow in via `portfolio.config.json.active_projects[].slug`.
- Zero hardcoded slug literals in the transform module (asserted by
  the worker brief acceptance gate #9 + the skill test suite's
  base64-obfuscated grep guard).

## Cross-references

- Schemas: `schemas/portfolio-config.schema.json` v1.1
  (cadence/slas/active_projects branches), `schemas/skill-frontmatter.schema.json`
  (this frontmatter validates against it), `schemas/events.schema.json`
  (READ-only awareness; event_kind="work" filter).
- Cross-modules (IMPORT-only): `scripts/reporting/render_template.py`
  (string.Template engine reuse — actually re-instantiated locally
  in `render_brief_markdown` for purity). NO `transaction.py`, NO
  `events_writer.py`, NO `workflow_runner.py` imports.
- Transform: `scripts/reporting/portfolio_weekly_brief.py`.
- Template: `templates/reports/portfolio-weekly-brief.template.md`.
- Tests: `tests/skills/test_portfolio_weekly_brief.py` (≥6 cases incl.
  cadence/sla schema validate, freshness sentinel, empty events
  tolerance, cross-project delta merge, natural_language min length,
  forbidden tokens guard).
- Pattern reference: `skills/planning/master-task-sync/SKILL.md`
  (Phase 8 W-D1 — local aggregation + plugin-agnostik discipline).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently
      downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7; cadence + sla
      branches validated against `portfolio-config.schema.json` v1.1.
- [x] Plugin-agnostik — no slug literals; slugs flow from
      portfolio.config.json.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when` are
      STRING content inside `description`, not separate fields.
- [x] READ-ONLY — zero `transaction.*` / `events_writer.*` imports
      in the transform module.
- [x] Append-only state — events.jsonl is READ-only consumed; this
      skill does NOT append (REVIZE 3, Q-RP-01 defer Phase 14).
- [x] Idempotency contract — same inputs + same `now` → byte-stable
      output (asserted by smoke test).
- [x] Forbidden tokens (4 grep CLEAN): the four Phase 7+ lesson
      tokens (per-call / per-url credit-cost-per-X fields, the
      Q-CO-01 metric naming token, hardcoded slugs) are absent;
      transform contains no leftover task markers in code.
- [x] natural_language phrases ≥ 30 char (min length sentinel
      asserted by test).
- [x] line count gate < 600 (transform).
