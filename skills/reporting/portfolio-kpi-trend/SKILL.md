---
name: portfolio-kpi-trend
description: |
  Use when: kullanıcı "kpi trend", "zaman serisi", "trend analizi",
  "portföy kpi", "kpi zaman serisi", "task throughput trend",
  "work events trend", "portfolio kpi trend", "çoklu proje trend",
  "tasks done over time", "event density" der ya da N günlük (7-90)
  portföy çapında trend tablosu istediğinde tetiklenir.
  Also use when: portfolio.config.json `active_projects` doluyken
  (1-12 entry, schema maxItems=12); her aktif projenin master.xlsx +
  _state/events.jsonl ulaşılabilir; period_days 7-90 aralığında bir
  zaman pencere için günlük tasks_done axis + per event_type 12 enum
  bucket density lazım; weekly-summary ya da portfolio-weekly-brief
  öncesinde uzun pencere kıyaslama gerekiyor; LOCAL approximation
  yeterli (GSC longitudinal Phase 6+ sonrasına ertelendi).
  Do not use when: portfolio.config.json yok (init-portfolio önce
  çalışmalı, DURUR PortfolioConfigMissingError); active_projects 12'yi
  aşıyor (schema maxItems sentinel, DURUR ActiveProjectsCeilingError
  — fazla entry'leri pending_onboard'a taşı); cross_query.read_only
  != true (schema const, DURUR ReadOnlyContractViolation);
  period_days < 7 ya da > 90 (DURUR PeriodDaysOutOfRangeError —
  daily granularity için makul aralık dışında); tek bir proje detayı
  isteniyorsa (whats-next ya da master-task-sync skill'i kullan, bu
  skill çoklu proje time series üretir); workbook'a YAZILACAK bir
  şey varsa (FORBIDDEN — bu skill strict read-only aggregator).
version: "1.0"
status: active
category: reporting
inputs:
  portfolio_root:
    type: string
    required: false
    description: "Path to portfolio workspace root. Default: $PSEO_WORKSPACE_ROOT env var."
  period_days:
    type: integer
    required: false
    default: 30
    description: "Trend window length in days. Range 7-90 enforced (DURUR PeriodDaysOutOfRangeError outside range). Default 30."
outputs:
  - "master.xlsx#none"
  - "projects/_portfolio/outputs/reports/{date}-portfolio-kpi-trend.md"
  - "projects/_portfolio/inbox/local/{date}-portfolio-kpi-trend.json"
consumes:
  - "init-portfolio:projects/_portfolio/portfolio.config.json"
  - "per-project:master.xlsx#master_task"
  - "per-project:_state/events.jsonl"
produces:
  - "portfolio-monthly-roundup"
  - "portfolio-weekly-brief"
triggers:
  manual: []
  natural_language: "kpi trend, zaman serisi, trend analizi, portföy kpi, kpi zaman serisi, task throughput trend, work events trend, portfolio kpi trend, çoklu proje trend, tasks done over time, event density"
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

# portfolio-kpi-trend — reporting skill (Phase 9 Wave 2)

Multi-project READ-ONLY time series aggregator. Iterates
`projects/_portfolio/portfolio.config.json` `active_projects[]`
(max 12, schema-enforced) and for each project produces a daily
trend axis spanning `period_days` (7-90, default 30) covering:

- `tasks_done` per day (from `master.xlsx#master_task` col L
  `done_date`),
- `tasks_added` per day (col K `created_date`),
- `work_events` density bucketed by the 12-value `event_type`
  enum (from per-project `_state/events.jsonl`, `event_kind=work`).

This skill follows the **convention authority** established by
`skills/planning/master-task-sync/SKILL.md` (Phase 8 W-D1 — pure
function transform + READ-ONLY discipline + plugin-agnostik) and
the **W-E4 path convention** established by
`skills/reporting/portfolio-weekly-brief/SKILL.md` (Phase 9 W1 —
`projects/_portfolio/{outputs,inbox}/local/` literal + `PSEO_WORKSPACE_ROOT`
env). Discipline (DURUR raises, no silent fallback, schema-first,
plugin agnostik, append-only state contract) is reused verbatim.

Per `schemas/portfolio-config.schema.json#cross_query.read_only`
(`const: true`), portfolio_kpi_trend is a strict read-only
aggregator. The transform module enforces this defensively: no
`wb.save()`, no `transaction.append()`, `transaction.update()`, or
`transaction.delete()` call sites; `load_workbook(read_only=True,
data_only=True)` on every workbook read. The
`assert_read_only_module()` helper greps the source for forbidden
write tokens — used by the test suite as a schema-first guard
(W-E3 paterni reuse).

## Inputs (frontmatter contract)

| Name             | Type    | Default | Notes                                                         |
|------------------|---------|---------|---------------------------------------------------------------|
| `portfolio_root` | string  | env     | Workspace root; falls back to `$PSEO_WORKSPACE_ROOT`.         |
| `period_days`    | integer | 30      | Trend window length. Range 7-90 enforced; outside → DURUR.    |

## Outputs (artifacts produced)

- `projects/_portfolio/outputs/reports/{date}-portfolio-kpi-trend.md`
  — markdown trend report (per-project mini time series tables +
  per-project work_events density per event_type + portfolio-wide
  totals), rendered via `string.Template` per
  `scripts/reporting/render_template.py` convention.
- `projects/_portfolio/inbox/local/{date}-portfolio-kpi-trend.json`
  — drift-recovery snapshot containing every per-project daily
  series + per-event_type buckets + warnings list.
- `master.xlsx#none` — declarative READ-ONLY confirmation (no
  sheet written across any iterated project).

**No `events.jsonl`** entry. Phase 9 Wave 2 convention
(Q-RP-01 governance refinement deferred to Phase 14).

## Sources consumed (per active project)

| # | Source                                  | Read mode                       |
|---|------------------------------------------|---------------------------------|
| 1 | `portfolio.config.json` (root)           | json                            |
| 2 | `master.xlsx#master_task` cols K + L     | openpyxl read_only=True         |
| 3 | `_state/events.jsonl`                    | jsonl, event_kind=work, in-window filter |

## Schema authority

`schemas/master-excel.schema.json#master_task`:

- col K = `created_date` (`type: date`) — drives `tasks_added` per day.
- col L = `done_date` (`type: date`) — drives `tasks_done` per day.
- col J = `status` (`#/definitions/statusEnum`) — only DONE rows
  count toward `tasks_done` (cross-validated with `done_date`).

`schemas/events.schema.json#event_type` — closed 12-value enum.
Each event_type gets its own density bucket per project per period:

- `content_new`, `content_revise`, `content_remove`, `tech_fix`,
  `quickwin_applied`, `pillar_launch`, `schema_fix`,
  `redirect_deployed`, `backlink_outreach`, `manual`,
  `skill_content_remediation`, `skill_whats_next`.

`schemas/portfolio-config.schema.json` v1.1:

- `active_projects[].slug` + `workspace_path` drive iteration.
- `active_projects.maxItems = 12` enforced
  (DURUR `ActiveProjectsCeilingError`).
- `cross_query.read_only = true` const enforced
  (DURUR `ReadOnlyContractViolation`).

`schemas/monthly-report.schema.json#gscTotals` subset — clicks /
impressions / avg_position / ctr stub kept as `0` sentinel until
GSC longitudinal data lands (Phase 6+); see "LOCAL approximation"
below.

## LOCAL approximation pattern (W-E1 + W-E2 reuse)

GSC longitudinal data integration ships in Phase 6+. Until then,
this skill reports **work-event-derived** density rather than
clicks/impressions. The transform exposes a `gsc_totals_stub`
field on each project with all four monthly-report.schema.json
gscTotals keys present and set to `0` so the JSON schema shape
holds; the markdown report annotates the stub with the
`(LOCAL approximation — GSC longitudinal Phase 6+)` note inline
so consumers know the limitation. This mirrors the
`gsc_weekly_delta` + `keywords_up` position-approximation pattern
established by `monthly_report.py` (W-E1) and `weekly_summary.py`
(W-E2).

## Aggregation logic

```
1. Resolve workspace_root (arg → PSEO_WORKSPACE_ROOT env).
2. Read portfolio.config.json + jsonschema validate (Draft 7).
3. Validate period_days ∈ [7, 90] → DURUR PeriodDaysOutOfRangeError.
4. Compute period_start = today - period_days + 1, period_end = today.
5. For each active_projects entry:
     - resolve master.xlsx + _state/events.jsonl paths.
     - if missing: emit warning, append empty trend (graceful skip).
     - else: scan master_task col K + L for in-window dates;
       scan events.jsonl for in-window event_kind=work events.
     - bucket events by event_type (12 enum), tally per day.
     - bucket tasks_done by done_date, tasks_added by created_date.
6. Sort projects by (priority asc, slug asc) — deterministic.
7. Build per-project daily series (no gaps in the date axis).
8. Render markdown report via string.Template substitution.
9. Write snapshot.json + report.md (no master.xlsx writes).
```

## Idempotency contract

> **Re-run with identical workbook state + identical events.jsonl
> + identical now → byte-identical snapshot + report.**

Mechanically:
1. Project ordering is deterministic (priority, slug).
2. Date axis is fully populated (no missing days).
3. event_type bucket order is the schema enum order.
4. JSON output uses `sort_keys=True` + `indent=2`.
5. `generated_at` is microsecond-truncated to second precision.
6. Markdown template substitution is idempotent.

## DURUR conditions

Stop and flag the manager — do not patch, do not fall back.

1. **PortfolioConfigMissingError** — `portfolio.config.json` absent
   or unreadable. Run init-portfolio first.
2. **PortfolioConfigInvalidError** — payload failed Draft 7
   validation against `schemas/portfolio-config.schema.json`.
3. **ActiveProjectsCeilingError** — `active_projects` > 12 (schema
   `maxItems` sentinel). Move surplus to `pending_onboard`.
4. **ReadOnlyContractViolation** — `cross_query.read_only != true`
   (schema `const: true`). The aggregator cannot run with read-only
   disabled.
5. **WorkspaceRootUnsetError** — could not resolve `workspace_root`
   from arg / `PSEO_WORKSPACE_ROOT` env.
6. **PeriodDaysOutOfRangeError** — `period_days < 7` or
   `period_days > 90`. Daily granularity is meaningless outside
   the [7, 90] band; weekly-summary handles 7d, monthly-report
   handles 28d, longer windows belong to Phase 6+ longitudinal
   GSC integration.

(Per-project missing `master.xlsx` or `events.jsonl` is **NOT** a
DURUR — graceful skip with warning, snapshot still emitted.)

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
    audit_target=f"reports:portfolio-kpi-trend:{report_date}",
    actor="agent:portfolio-kpi-trend",
    workspace_root=workspace_root,
    notes=f"local_aggregation report-only (portfolio-kpi-trend; date={report_date})",
)
```

## Cross-references

- Schemas: `schemas/portfolio-config.schema.json` v1.1
  (`active_projects.maxItems = 12`; `cross_query.read_only = true`
  const), `schemas/master-excel.schema.json#master_task` cols K +
  L (date-typed columns; `#/definitions/statusEnum`),
  `schemas/events.schema.json#event_type` (12 enum),
  `schemas/monthly-report.schema.json#gscTotals` (stub subset),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/reporting/render_template.py`
  (`string.Template` $var rendering convention). NO `transaction.py`,
  NO `events_writer.py` imports.
- Transform: `scripts/reporting/portfolio_kpi_trend.py`.
- Template: `templates/reports/portfolio-kpi-trend.template.md`.
- Tests: `tests/skills/test_portfolio_kpi_trend.py` (≥6 cases incl.
  schema validate + period_days range sentinel + multi-project
  time series merge + empty events tolerance + trend line
  continuity + event_type 12 enum coverage + natural_language min
  length + forbidden tokens guard + read-only enforcement + path
  convention).
- Pattern reference: `scripts/reporting/portfolio_overview.py`
  (W-E3 — `assert_read_only_module()` helper),
  `scripts/reporting/portfolio_weekly_brief.py` (W-E4 — path
  convention + PSEO_WORKSPACE_ROOT env), `scripts/reporting/monthly_report.py`
  (W-E1 — LOCAL approximation pattern), `scripts/reporting/weekly_summary.py`
  (W-E2 — gsc_weekly_delta LOCAL approximation).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently
      downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Every config
      payload checked against `portfolio-config.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `active_projects`
      iteration drives every path; transform has 0 hardcoded slug
      words.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when`
      are STRING content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `render_template.py`
      convention reused via `string.Template` inline; no module
      imported / mutated.
- [x] F1: write target is **NOTHING** (read-only aggregator).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths),
      never raw ints.
- [x] Append-only state — `events.jsonl` NOT written (Phase 9 W2
      convention; Q-RP-01 deferred). Snapshot JSON is overwrite-safe
      because filename includes `{date}`.
- [x] READ-ONLY contract — no `.save(`, no `transaction.append(`,
      no `transaction.update(`, no `transaction.delete(` call sites
      in the transform module (verified by `assert_read_only_module()`).
- [x] cross_query.read_only=true (schema const) honored.
- [x] W-E4 path convention — `projects/_portfolio/{outputs,inbox}/local/`
      literal; `PSEO_WORKSPACE_ROOT` env resolution.
- [x] period_days range 7-90 sentinel (PeriodDaysOutOfRangeError).
- [x] LOCAL approximation transparent — gscTotals stub annotated
      inline + in this SKILL.md (W-E1 + W-E2 paterni reuse).
- [x] event_type 12 enum coverage — every enum value gets a bucket
      (assert in test).
- [x] natural_language phrases ≥ 30 char (min length sentinel
      asserted by test).
- [x] line count gate < 600 (transform).
