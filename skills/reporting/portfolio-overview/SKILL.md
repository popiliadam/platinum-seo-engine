---
name: portfolio-overview
description: |
  Use when: kullanıcı "portföy özet", "tüm projeler", "tüm projelerin
  durumu", "portfolio overview", "multi-project status", "portföy
  durumu", "active projects özet" der ya da portföy genelinde KPI
  karşılaştırması istediğinde tetiklenir.
  Also use when: portfolio.config.json `active_projects` listesi
  doluyken (1-8 entry, schema maxItems=8); her aktif projenin
  master.xlsx'i mevcut (eksikler graceful skip + warning); tek bir
  pass'te tüm aktif projelerin dashboard KPI snapshot + master_task
  status karşılaştırması raporlanır; weekly-summary ya da
  portfolio-weekly-brief öncesinde portfolio-wide tablo gerekiyor.
  Do not use when: portfolio.config.json yok (portfolio init önce
  çalışmalı, DURUR PortfolioConfigMissingError); active_projects 8'i
  aşıyor (schema maxItems sentinel, DURUR ActiveProjectsCeilingError —
  fazla entry'leri pending_onboard'a taşı); cross_query.read_only !=
  true (schema const, DURUR ReadOnlyContractViolation); tek bir
  proje detayı isteniyorsa (whats-next ya da master-task-sync skill'i
  kullan, bu skill çoklu proje aggregate eder); workbook'a YAZILACAK
  bir şey varsa (FORBIDDEN — bu skill strict read-only aggregator).
version: "1.0"
status: active
category: reporting
inputs:
  portfolio_root:
    type: string
    required: false
    description: "Path to portfolio workspace root. Default: $PSEO_PORTFOLIO_ROOT, $PSEO_WORKSPACE_ROOT, or .pse-workspace marker discovery."
  filter_active:
    type: boolean
    required: false
    default: true
    description: "Iterate active_projects only (default true). pending_onboard NEVER read per schema description."
outputs:
  - "master.xlsx#none"
  - "outputs/reports/{date}-portfolio-overview.md"
  - "inbox/local/{date}-portfolio-overview.json"
consumes:
  - "portfolio-init:projects/_portfolio/portfolio.config.json"
  - "dashboard-refresh:master.xlsx#dashboard"
  - "master-task-sync:master.xlsx#master_task"
produces:
  - "weekly-summary"
  - "portfolio-weekly-brief"
  - "monthly-report"
triggers:
  manual: []
  natural_language: |
    "portföy özet", "tüm projeler", "portfolio overview",
    "multi-project status", "portföy durumu", "active projects özet",
    "tüm projelerin durumu"
  hooks: []
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

# portfolio-overview — reporting skill (Phase 9 Wave 1)

Multi-project READ-ONLY aggregator. Iterates portfolio.config.json
`active_projects` (max 8, schema-enforced) and pulls each project's
`master.xlsx#dashboard` KPI cells + locally-computed `master_task`
status counts into a single portfolio overview snapshot + markdown
report. **No MCP**, **no DFS**, **no budget pre-flight**, **no Excel
write** — strict read-only.

This skill follows the **convention authority** established by
`skills/planning/master-task-sync/SKILL.md` (Phase 8 W-D1 — local
aggregator pattern: aggregate transform module, drift-recovery JSON
snapshot, markdown report). The protocol shape, raw envelope discipline,
and DURUR + flag rule are reused — only the source (multi-project read
instead of single-project local sheets) and the output discipline (no
master.xlsx mutation, no events.jsonl) change.

Per `schemas/portfolio-config.schema.json#cross_query.read_only`
(`const: true`, schema lines 90-91), portfolio_overview is a strict
read-only aggregator. The transform module enforces this defensively:
no `wb.save()`, no `transaction.append()`, `transaction.update()`, or
`transaction.delete()` call sites; `load_workbook(read_only=True)` on
every workbook read. The `assert_read_only_module()` helper greps the
source for forbidden write tokens — used by the test suite as a
schema-first guard.

## Inputs (frontmatter contract)

| Name             | Type    | Default | Notes                                                         |
|------------------|---------|---------|---------------------------------------------------------------|
| `portfolio_root` | string  | env     | Workspace root; falls back to `$PSEO_PORTFOLIO_ROOT`, `$PSEO_WORKSPACE_ROOT`, or `.pse-workspace` marker. |
| `filter_active`  | boolean | true    | Iterate `active_projects` only. `pending_onboard` NEVER read (schema description). |

## Outputs (artifacts produced)

- `outputs/reports/{date}-portfolio-overview.md` — markdown report
  (multi-project table + aggregate totals); rendered via `string.Template`
  per `scripts/reporting/render_template.py` convention.
- `inbox/local/{date}-portfolio-overview.json` — drift-recovery snapshot
  containing every per-project KPI + status_count + warnings list.
- `master.xlsx#none` — declarative READ-ONLY confirmation (no sheet
  written across any iterated project).

**No `events.jsonl`** entry. Phase 9 Wave 1 convention; portfolio-wide
provenance governance refinement is deferred to Q-RP-01 (closeout).

## Sources consumed (per active project)

| # | Source                              | Read mode |
|---|-------------------------------------|-----------|
| 1 | `portfolio.config.json` (root)      | json      |
| 2 | `master.xlsx#dashboard` (R10, R47-R52, R59) | openpyxl read_only=True |
| 3 | `master.xlsx#master_task` (col J)   | openpyxl read_only=True |

The 8 dashboard KPI cells are pulled verbatim per
`schemas/master-excel.schema.json#dashboard required_cells` (lines 32-41):
`R10=total_pillars`, `R47=master_task_total`, `R48=master_task_done`,
`R49=master_task_todo`, `R50=master_task_ongoing`,
`R51=cannibalization_count`, `R52=quick_wins_count`,
`R59=last_audit_date`. master_task statusEnum counts are computed
locally by scanning column J — used for a drift cross-check against
R47-R50.

## Aggregation logic

```
1. Resolve portfolio_root (arg → env → .pse-workspace).
2. Read portfolio.config.json + jsonschema validate (Draft 7).
3. For each active_projects entry:
     - resolve master.xlsx path (workspace_path/projects/slug/master.xlsx).
     - if missing: emit warning, append empty snapshot (graceful skip).
     - else: read 8 dashboard cells + scan master_task col J.
     - cross-check dashboard R47-R50 vs locally-computed totals;
       set status_check_drift=True on mismatch.
4. Sort snapshots by (priority asc, slug asc) — deterministic.
5. Sum per-project KPIs into batch.totals.
6. Render markdown report via string.Template substitution.
7. Write snapshot.json + report.md (no master.xlsx writes).
```

## Idempotency contract

> **Re-run with identical workbook state → byte-identical snapshot
> + report.**

Mechanically:
1. Snapshot ordering is deterministic (priority, slug).
2. Totals tuple is fixed at module scope.
3. JSON output uses `sort_keys=True` + `indent=2`.
4. Markdown template substitution is idempotent.

## DURUR conditions

Stop and flag the manager — do not patch, do not fall back.

1. **PortfolioConfigMissingError** — `portfolio.config.json` absent /
   unreadable. Run portfolio init first.
2. **PortfolioConfigInvalidError** — payload failed Draft 7 validation
   against `schemas/portfolio-config.schema.json`. Schema-first violation.
3. **ActiveProjectsCeilingError** — `active_projects` > 8 (schema
   `maxItems` sentinel). Move surplus to `pending_onboard`.
4. **ReadOnlyContractViolation** — `cross_query.read_only != true`
   (schema `const: true`). The aggregator cannot run with read-only
   disabled.
5. **WorkspaceRootUnsetError** — could not resolve `portfolio_root`
   from arg / env / `.pse-workspace` marker.

(Per-project missing `master.xlsx` is **NOT** a DURUR — graceful skip
with warning, snapshot still emitted.)

## Cross-references

- Schemas: `schemas/portfolio-config.schema.json` (v1.1 —
  ActiveProjectEntry required fields slug + workspace_path + profile +
  priority; `active_projects.maxItems = 8`;
  `cross_query.read_only = true` const),
  `schemas/master-excel.schema.json#dashboard` (lines 32-41 —
  `required_cells` 8 KPI cells + `forbidden_patterns` no-formula rule),
  `schemas/master-excel.schema.json#master_task` (lines 269-303 —
  `required_columns` 19 cols + `#/definitions/statusEnum` line 20),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/reporting/render_template.py`
  (`string.Template` $var rendering convention).
- Transform: `scripts/reporting/portfolio_overview.py`.
- Template: `templates/reports/portfolio-overview.template.md`.
- Tests: `tests/skills/test_portfolio_overview.py` (6-8 cases incl.
  schema validate + maxItems sentinel + missing workbook tolerance +
  read-only enforcement + natural_language length + forbidden tokens
  guard).
- Pattern reference: `scripts/planning/master_task_sync.py` (Phase 8
  W-D1 local aggregator pattern).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Every config
      payload checked against `portfolio-config.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `active_projects` iteration
      drives every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when` are
      STRING content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `render_template.py` convention
      reused via `string.Template` inline; no module imported / mutated.
- [x] D-003 helper IMPORT NOT applicable — local aggregation, no DFS
      payload consumed.
- [x] F1: write target is **NOTHING** (read-only aggregator).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] Append-only state — `events.jsonl` NOT written (Phase 9 W1
      convention; Q-RP-01 deferred). Snapshot JSON is overwrite-safe
      because filename includes `{date}`.
- [x] READ-ONLY contract — no `.save(`, no `transaction.append(`,
      no `transaction.update(`, no `transaction.delete(` call sites
      in the transform module (verified by `assert_read_only_module()`).
- [x] cross_query.read_only=true (schema const) honored.
