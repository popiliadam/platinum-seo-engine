---
name: portfolio-task-heatmap
description: |
  Use when: kullanıcı "task heatmap", "task yoğunluk", "task density",
  "category priority dağılım", "task heatmap raporu", "portföy task
  yoğunluğu", "kategori bazlı task dağılımı", "öncelik bazlı task
  dağılımı", "portfolio task heatmap" der ya da portföy çapında her
  proje için master_task'ların kategori × priority kırılımını talep
  ettiğinde tetiklenir.
  Also use when: portfolio.config.json v1.1 mevcut + active_projects
  doldurulmuş; her aktif projenin master.xlsx#master_task'ında col F
  (category) + col G (priority severityEnum 4 değer) + col J (status
  statusEnum 7 değer) okunabilir; portföy çapında project × category ×
  priority matris + per-project + per-category + per-priority toplam
  dağılımı raporlanır; yalnızca READ-ONLY agregasyon yeterli (yazma
  kapsamı YOK); status_check_drift varsa WARNING surface (DURUR değil,
  transform devam eder).
  Do not use when: portfolio.config.json yokken (init-portfolio önce
  çalışmalı, DURUR PortfolioConfigMissingError); active_projects 8'i
  aşıyor (schema maxItems sentinel, DURUR ActiveProjectsCeilingError —
  fazla entry'leri pending_onboard'a taşı); cross_query.read_only !=
  true (schema const, DURUR ReadOnlyContractViolation); tek proje task
  detayı isteniyorsa (whats-next ya da master-task-sync skill'i kullan,
  bu skill PORTFÖY scope çoklu proje aggregate eder); workbook'a
  YAZILACAK bir şey varsa (FORBIDDEN — bu skill strict read-only
  aggregator); KPI snapshot isteniyorsa portfolio-overview kullan.
version: "1.0"
status: active
category: reporting
inputs:
  portfolio_root:
    type: string
    required: false
    description: "Optional path override; defaults to PSEO_WORKSPACE_ROOT env var. Workspace root containing projects/_portfolio/portfolio.config.json."
  reference_date:
    type: string
    required: false
    description: "ISO date override (YYYY-MM-DD). Default: UTC today. Used for the report filename + frontmatter generated_at field."
outputs:
  - "master.xlsx#none"
  - "projects/_portfolio/outputs/reports/{date}-portfolio-task-heatmap.md"
  - "projects/_portfolio/inbox/local/{date}-portfolio-task-heatmap.json"
consumes:
  - "init-portfolio:projects/_portfolio/portfolio.config.json"
  - "per-project:master.xlsx#master_task"
  - "per-project:master.xlsx#consistency-report"
produces:
  - "portfolio-overview"
  - "portfolio-weekly-brief"
triggers:
  manual: []
  natural_language: "task heatmap, task yoğunluk, task density, category priority dağılım, portföy task yoğunluğu, portfolio task heatmap, kategori bazlı task dağılımı, öncelik bazlı task dağılımı"
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

# portfolio-task-heatmap — reporting skill (Phase 9 Wave 2)

Multi-project READ-ONLY aggregator that builds a **project × category ×
priority** density matrix across all `active_projects` in
`projects/_portfolio/portfolio.config.json` v1.1. For each project,
reads `master.xlsx#master_task`:

- col F (`category`, free-form string) — row dimension component
- col G (`priority`, references `#/definitions/severityEnum` 4 values:
  `CRITICAL` / `HIGH` / `MEDIUM` / `LOW`) — column dimension component
- col J (`status`, references `#/definitions/statusEnum` 7 values:
  `TODO` / `ONGOING` / `EXISTS` / `DONE` / `BLOCKED` / `DEFERRED` /
  `CANCELED`) — open-task filter (open = not in `{DONE, CANCELED}`)

This skill follows the **convention authority** established by
`scripts/reporting/portfolio_overview.py` (Phase 9 W-E3 — strict
read-only multi-project aggregator + `assert_read_only_module()` helper
+ `status_check_drift` advisory pattern) and `portfolio_weekly_brief.py`
(Phase 9 W-E4 — `projects/_portfolio/{outputs,inbox}/local/` path
convention + `PSEO_WORKSPACE_ROOT` env resolution + idempotency
contract).

Per `schemas/portfolio-config.schema.json#cross_query.read_only`
(`const: true`, schema lines 90-91), this transform is a strict
read-only aggregator. The transform module enforces this defensively:
no `wb.save()`, no `transaction.append()`, `transaction.update()`, or
`transaction.delete()` call sites; `load_workbook(read_only=True,
data_only=True)` on every workbook read. The
`assert_read_only_module()` helper greps the source for forbidden
write tokens — used by the test suite as a schema-first guard
(W-E3 helper reuse).

## Inputs (frontmatter contract)

| Name             | Type   | Default | Notes                                                             |
|------------------|--------|---------|-------------------------------------------------------------------|
| `portfolio_root` | string | env     | Optional path override; defaults to `$PSEO_WORKSPACE_ROOT`.       |
| `reference_date` | string | today   | Optional ISO date override (YYYY-MM-DD). Default: UTC today.      |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env (mirrors
W-E4 surface). Missing env var + missing arg → DURUR
`WorkspaceRootUnsetError`.

## Outputs (artifacts produced)

- `master.xlsx#none` — sentinel acknowledging that the skill READS
  `master.xlsx#master_task` from each active project but writes
  ZERO cells anywhere. The frontmatter `outputs[]` entry is
  intentional schema documentation (no openpyxl mutation, no
  transaction layer call).
- `projects/_portfolio/outputs/reports/{date}-portfolio-task-heatmap.md`
  — human-readable Markdown report (project × category × priority
  matrix + per-project + per-category + per-priority totals).
- `projects/_portfolio/inbox/local/{date}-portfolio-task-heatmap.json`
  — drift-recovery snapshot; full HeatmapBatch envelope with every
  per-project density cell + warnings list.

**No `events.jsonl`** entry. Phase 9 Wave 2 convention; portfolio-wide
provenance governance refinement is deferred to Q-RP-01 (closeout).

## Consumed (READ-ONLY)

| # | Source                                    | Discipline                                |
|---|-------------------------------------------|-------------------------------------------|
| 1 | `portfolio.config.json` v1.1              | active_projects iterate (maxItems=8)      |
| 2 | per-project `master.xlsx#master_task` col F | category (free-form string)             |
| 3 | per-project `master.xlsx#master_task` col G | priority (`severityEnum` 4 values)      |
| 4 | per-project `master.xlsx#master_task` col J | status (`statusEnum` 7 values, OPEN filter) |
| 5 | per-project consistency-report (OPTIONAL) | verdict GREEN/AMBER/RED → `status_check_drift` advisory |

## Schema authority

`schemas/master-excel.schema.json`:

- `master_task` col F (`category`, free-form string) — row dimension
  raw value; transform passes through verbatim (no normalization,
  per worker brief).
- `master_task` col G (`priority`, references
  `#/definitions/severityEnum`) — enum 4 values `CRITICAL` / `HIGH`
  / `MEDIUM` / `LOW`. Out-of-enum → `OTHER` bucket + warning.
- `master_task` col J (`status`, references
  `#/definitions/statusEnum`) — enum 7 values; open-task = not in
  `{DONE, CANCELED}`. Out-of-enum → counted but warned.

`schemas/portfolio-config.schema.json` v1.1:

- `active_projects[].slug` + `workspace_path` + `priority` drive
  iteration; `maxItems = 8` enforced (DURUR
  `ActiveProjectsCeilingError`).
- `cross_query.read_only` = `true` const (DURUR
  `ReadOnlyContractViolation`).

`schemas/consistency-report.schema.json` (OPTIONAL):

- `verdict` enum `GREEN` / `AMBER` / `RED`; surfaces a
  `status_check_drift` ADVISORY when present and not GREEN
  (NOT a DURUR — the transform proceeds, the warning is
  rendered in the report).

## Transform contract

`scripts/reporting/portfolio_task_heatmap.py` (pure function, < 600
lines per ADR-027):

- `aggregate(portfolio_root, config, run_date) -> HeatmapBatch` —
  top-level idempotent aggregator.
- `_build_project_heatmap(...) -> ProjectHeatmap` — one project's
  category × priority density.
- `_read_master_task_density(workbook_path) -> tuple[dict, dict]` —
  openpyxl thin wrapper, `read_only=True`, INLINE (no shared excel
  helper imported); returns (density_cells, status_distribution).
- `_read_consistency_verdict(workbook_path) -> str | None` —
  OPTIONAL consistency-report read; missing or unreadable → None
  (advisory only).
- `build_report_markdown(batch, template_text) -> str` —
  `string.Template` `$var` substitution, matches
  `scripts/reporting/render_template.py` engine.
- `assert_read_only_module()` — grep self-check; raises
  `ReadOnlyContractViolation` on any forbidden write token.

## Template

`templates/reports/portfolio-task-heatmap.template.md` — Markdown
with YAML frontmatter (`generated_at`, `portfolio_id`,
`project_count`, `scope`). Body includes:

- `$totals_summary` — single-line rollup (active projects, open
  tasks total, top-3 categories).
- `$projects_matrix` — per-project category × priority matrix
  (Markdown table, one section per project).
- `$category_totals_table` — per-category breakdown (rows =
  categories, cols = severityEnum 4 values + total).
- `$priority_totals_table` — per-priority breakdown (rows =
  severityEnum 4 values, cols = projects + total).
- `$advisory_block` — status_check_drift warnings (one line per
  project that surfaces drift).

`string.Template` engine (NOT jinja2) — same as
`scripts/reporting/render_template.py` (Phase 1 mirası). All
variables are stringified by the transform so the template engine
never sees a non-string value.

## DURUR conditions

Stop and flag the manager — do not patch, do not fall back.

1. **PortfolioConfigMissingError** — `portfolio.config.json` absent /
   unreadable. Run portfolio init first.
2. **PortfolioConfigInvalidError** — payload failed Draft 7
   validation against `schemas/portfolio-config.schema.json`.
   Schema-first violation.
3. **ActiveProjectsCeilingError** — `active_projects` > 8 (schema
   `maxItems` sentinel). Move surplus to `pending_onboard`.
4. **ReadOnlyContractViolation** — `cross_query.read_only != true`
   (schema `const: true`). The aggregator cannot run with
   read-only disabled.
5. **WorkspaceRootUnsetError** — `PSEO_WORKSPACE_ROOT` env var
   unset AND no explicit `portfolio_root` passed.

(Per-project missing `master.xlsx` is **NOT** a DURUR — graceful
skip with warning, snapshot still emitted with empty density cells.
Per-project missing consistency-report is also NOT a DURUR — the
status_check_drift advisory simply remains absent.)

## status_check_drift advisory pattern

(W-E3 paterni reuse — non-DURUR signal.)

When per-project consistency-report exists AND `verdict != GREEN`,
the project's heatmap row carries a `status_check_drift = true`
flag and a warning (`status_check_drift: consistency-report verdict
= {AMBER|RED}`). The transform PROCEEDS — the advisory is rendered
inline in the report's `$advisory_block`. The flag does NOT block
heatmap generation; downstream consumers (manager, weekly brief)
decide how to react.

This mirrors W-E3's status_check_drift surfacing: locally-computed
counts vs dashboard cells mismatch → WARNING, NOT DURUR.

## Idempotency contract

> **Re-run with identical workbook state + same `reference_date` →
> byte-identical snapshot + report.**

Mechanically:
1. Snapshot ordering is deterministic — projects sorted by
   `(priority asc, slug asc)`.
2. Category rows sorted alphabetically; priority columns sorted
   per `severityEnum` order (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`,
   `OTHER`).
3. JSON output uses `sort_keys=True` + `indent=2`.
4. `generated_at` is microsecond-truncated to second precision.
5. Markdown template substitution is idempotent.

## Plugin agnostik

- Project slugs flow in via `portfolio.config.json.active_projects[].slug`.
- Zero hardcoded slug literals in the transform module (asserted
  by the worker brief acceptance gate #9 + the skill test suite's
  base64-obfuscated grep guard against the 8 known real-client
  slugs).

## Cross-references

- Schemas: `schemas/portfolio-config.schema.json` v1.1
  (active_projects iterate + cross_query.read_only=true const),
  `schemas/master-excel.schema.json#master_task` (col F + col G
  severityEnum + col J statusEnum + `#/definitions/severityEnum` +
  `#/definitions/statusEnum`),
  `schemas/consistency-report.schema.json` (OPTIONAL verdict
  GREEN/AMBER/RED for advisory surfacing),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/reporting/render_template.py`
  (`string.Template` `$var` engine reused inline). NO
  `scripts.excel.transaction`, NO `scripts.state.events_writer`,
  NO `scripts.workflow_runner` imports.
- Transform: `scripts/reporting/portfolio_task_heatmap.py`.
- Template: `templates/reports/portfolio-task-heatmap.template.md`.
- Tests: `tests/skills/test_portfolio_task_heatmap.py` (6-8 cases
  incl. statusEnum 7 + severityEnum 4 sentinels, missing
  master_task tolerance, empty cell heatmap density,
  status_check_drift advisory non-DURUR, natural_language min
  length, forbidden tokens guard, assert_read_only_module guard,
  path convention sentinel).
- Pattern reference: `scripts/reporting/portfolio_overview.py`
  (Phase 9 W-E3 — `assert_read_only_module()` helper at line 475
  + status_check_drift advisory) and
  `scripts/reporting/portfolio_weekly_brief.py` (Phase 9 W-E4 —
  path convention + PSEO_WORKSPACE_ROOT env).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently
      downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Every
      config payload validated against
      `portfolio-config.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `active_projects`
      iteration drives every path.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when`
      are STRING content inside `description`, not separate
      fields.
- [x] Cross-module IMPORT discipline — `render_template.py`
      convention reused via `string.Template` inline; no module
      imported / mutated.
- [x] D-003 helper IMPORT NOT applicable — local aggregation,
      no DFS payload consumed.
- [x] F1: write target is **NOTHING** (read-only aggregator).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] Append-only state — `events.jsonl` NOT written (Phase 9
      Wave 2 convention; Q-RP-01 deferred). Snapshot JSON is
      overwrite-safe because filename includes `{date}`.
- [x] READ-ONLY contract — no `.save(`, no
      `transaction.append(`, no `transaction.update(`, no
      `transaction.delete(` call sites in the transform module
      (verified by `assert_read_only_module()` — W-E3 helper
      reuse).
- [x] cross_query.read_only=true (schema const) honored.
- [x] Forbidden tokens (4 + 8 slug grep CLEAN): the four Phase
      7+ lesson tokens (per-call / per-url credit-cost-per-X
      fields, the Q-CO-01 metric naming token, TODO inline
      comments) are absent in transform; the 8 known real-client
      slugs are absent in transform / SKILL.md / template.
- [x] natural_language phrases ≥ 30 char (min length sentinel
      asserted by test).
- [x] line count gate < 600 (transform).
- [x] W-E4 path convention — `projects/_portfolio/{outputs,inbox}/local/`
      literal in transform + `PSEO_WORKSPACE_ROOT` env resolution.
