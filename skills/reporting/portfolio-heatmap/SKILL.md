---
name: portfolio-heatmap
description: |
  Use when: kullanıcı "fırsat heatmap", "opportunity matrix", "drift
  heatmap", "portföy yoğunluk", "heatmap raporu", "yoğunluk matrisi",
  "portföy fırsat ısı haritası", "opportunity density", "drift density"
  der ya da portföy çapında hangi projede hangi sheet'in (opportunity /
  quick_wins / content_decay / cannibalization) yüklü olduğunu görmek
  istediğinde tetiklenir.
  Also use when: portfolio.config.json v1.1 mevcut + active_projects
  doldurulmuş; her aktif projenin master.xlsx'i okunabilir (eksikler
  schema-valid empty shape ile graceful skip + warning surface);
  aggregate_dimension category / priority / primary_source eksenlerinden
  birinde kırılım istenir; tek pass'te 4 sheet × N proje yoğunluk
  matrisi + drift breakdown raporlanır; portfolio-overview ya da
  portfolio-weekly-brief sonrası "hangi proje hangi alanda yoğun"
  görselleştirmesi gerekiyor.
  Do not use when: portfolio.config.json yok (init-portfolio önce
  çalışmalı, DURUR PortfolioConfigMissingError); active_projects 8'i
  aşıyor (schema maxItems sentinel, DURUR ActiveProjectsCeilingError);
  cross_query.read_only != true (schema const, DURUR
  ReadOnlyContractViolation); tek bir proje detayı isteniyorsa
  (whats-next ya da master-task-sync skill'ini kullan, bu skill çoklu
  proje aggregate eder); aggregate_dimension input enum dışındaysa
  (DURUR AggregateDimensionInvalidError); workbook'a YAZILACAK bir şey
  varsa (FORBIDDEN — bu skill 100% READ-ONLY aggregator).
version: "1.0"
status: active
category: reporting
inputs:
  portfolio_root:
    type: string
    required: false
    description: "Path to portfolio workspace root. Default: PSEO_WORKSPACE_ROOT env."
  aggregate_dimension:
    type: string
    required: false
    default: "category"
    description: "Heatmap kırılım ekseni. Enum: category | priority | primary_source. Default category. priority severityEnum (CRITICAL/HIGH/MEDIUM/LOW) üzerinden, primary_source 10-enum (master_task col C) üzerinden bucket üretir."
outputs:
  - "master.xlsx#none"
  - "projects/_portfolio/outputs/reports/{date}-portfolio-heatmap.md"
  - "projects/_portfolio/inbox/local/{date}-portfolio-heatmap.json"
consumes:
  - "init-portfolio:projects/_portfolio/portfolio.config.json"
  - "per-project:master.xlsx#master_task"
  - "per-project:master.xlsx#opportunity"
  - "per-project:master.xlsx#quick_wins"
  - "per-project:master.xlsx#content_decay"
  - "per-project:master.xlsx#cannibalization"
produces:
  - "portfolio-overview"
  - "portfolio-weekly-brief"
triggers:
  manual: []
  natural_language: "fırsat heatmap, opportunity matrix, drift heatmap, portföy yoğunluk, heatmap raporu, yoğunluk matrisi, portföy fırsat ısı haritası, opportunity density, drift density"
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

# portfolio-heatmap — reporting skill (Phase 9 Wave 2)

Multi-project READ-ONLY aggregator. Iterates `portfolio.config.json` v1.1
`active_projects[]` (max 8, schema-enforced) and for each project pulls
density counts from four "opportunity" sheets — `opportunity`,
`quick_wins`, `content_decay`, `cannibalization` — plus master_task
breakdown along the requested `aggregate_dimension` axis (category /
priority / primary_source).

This skill follows the **convention authority** established by
`skills/reporting/portfolio-overview/SKILL.md` (Phase 9 W-E3 — local
aggregator pattern: aggregate transform module, drift-recovery JSON
snapshot, markdown report) and the **path convention** proven by
`skills/reporting/portfolio-weekly-brief/SKILL.md` (Phase 9 W-E4 —
`projects/_portfolio/{outputs,inbox}/local/` literal +
`PSEO_WORKSPACE_ROOT` env). **No MCP**, **no DFS**, **no budget
pre-flight**, **no Excel write** — strict read-only.

Per `schemas/portfolio-config.schema.json#cross_query.read_only`
(`const: true`, schema lines 90-91), portfolio_heatmap is a strict
read-only aggregator. The transform module enforces this defensively:
no `wb.save()`, no `transaction.append()`, `transaction.update()`, or
`transaction.delete()` call sites; `load_workbook(read_only=True,
data_only=True)` on every workbook read. The
`assert_read_only_module()` helper greps the source for forbidden write
tokens — used by the test suite as a schema-first guard (W-E3 paterni).

## Inputs (frontmatter contract)

| Name                  | Type   | Default     | Notes                                                                                                                                                            |
|-----------------------|--------|-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `portfolio_root`      | string | env         | Workspace root; falls back to `$PSEO_WORKSPACE_ROOT`.                                                                                                            |
| `aggregate_dimension` | string | `"category"` | Enum {`category`, `priority`, `primary_source`}. `priority` uses `#/definitions/severityEnum` 4-value bucket; `primary_source` uses master_task col C 10-enum. |

## Outputs (artifacts produced)

- `projects/_portfolio/outputs/reports/{date}-portfolio-heatmap.md` —
  markdown heatmap report (project × {opportunity, quick_wins,
  content_decay, cannibalization} density matrix +
  aggregate_dimension breakdown table); rendered via
  `string.Template` per `scripts/reporting/render_template.py`
  convention.
- `projects/_portfolio/inbox/local/{date}-portfolio-heatmap.json` —
  drift-recovery snapshot with per-project sheet counts + density
  scores + aggregate_dimension bucket counts + warnings list.
- `master.xlsx#none` — declarative READ-ONLY confirmation (no sheet
  written across any iterated project).

**No `events.jsonl`** entry. Phase 9 Wave 2 convention; portfolio-wide
provenance governance refinement is deferred to Q-RP-01.

## Sources consumed (per active project)

| # | Source                                | Read mode (openpyxl)             |
|---|---------------------------------------|----------------------------------|
| 1 | `portfolio.config.json` (root)        | json                             |
| 2 | `master.xlsx#master_task` cols B+C+F+G | read_only=True, data_only=True   |
| 3 | `master.xlsx#opportunity` col B       | read_only=True, data_only=True   |
| 4 | `master.xlsx#quick_wins` col J        | read_only=True, data_only=True   |
| 5 | `master.xlsx#content_decay` col E     | read_only=True, data_only=True   |
| 6 | `master.xlsx#cannibalization` col F   | read_only=True, data_only=True   |

## Schema authority

- `schemas/portfolio-config.schema.json` v1.1 — `active_projects.maxItems
  = 8`, `cross_query.read_only = true` const.
- `schemas/master-excel.schema.json#master_task`:
  - col B `task` (free text)
  - col C `primary_source` enum 10 values
    `[content_decay, quickwin, tech_fix, schema, pillar, manual, sxo,
    cannibalization, redirect_404, internal_links]` (Q-IL-1 closure
    added `internal_links`)
  - col F `category` (free text)
  - col G `priority` `#/definitions/severityEnum` 4 values
    `[CRITICAL, HIGH, MEDIUM, LOW]`
- `schemas/master-excel.schema.json#opportunity` — header_row=4,
  data_start_row=5, 8 cols.
- `schemas/master-excel.schema.json#quick_wins` — header_row=4,
  data_start_row=5, 10 cols.
- `schemas/master-excel.schema.json#content_decay` — header_row=5,
  data_start_row=6, 8 cols.
- `schemas/master-excel.schema.json#cannibalization` — header_row=4,
  data_start_row=5, 7 cols.

## Aggregation logic

```
1. Resolve portfolio_root (arg → PSEO_WORKSPACE_ROOT env).
2. Read portfolio.config.json + jsonschema validate (Draft 7).
3. Validate aggregate_dimension input (DURUR enum guard).
4. For each active_projects entry:
     - resolve master.xlsx path
       (workspace_root/projects/{slug}/master.xlsx).
     - if missing master.xlsx: emit warning, append schema-valid empty
       project shape (graceful skip, NOT crash — W-E1 paterni).
     - else: open read-only, scan each of the 4 opportunity sheets;
       missing-sheet → empty shape (NOT crash, warning surface);
       master_task → scan cols B+C+F+G into the 8-col project tally.
5. Compute per-cell density score = count / max(global_count_per_sheet,
   1) → [0.0, 1.0]. Tie-broken stable.
6. Bucket by aggregate_dimension:
     category       → free-text cardinality buckets
     priority       → severityEnum 4-bucket (CRITICAL/HIGH/MEDIUM/LOW)
     primary_source → 10-enum bucket (each value gets a deterministic
                       bucket even at zero count)
7. Sort projects by (priority asc, slug asc) — deterministic.
8. Render markdown report + JSON snapshot. Idempotent.
```

## Density semantics

`density(project, sheet) = row_count(project, sheet) / max_row_count_across_active_projects(sheet)`.

Per cell. Empty sheet → 0.0. Single project at maximum → 1.0. The
maximum is per-sheet (not portfolio-wide) so a project with 50 opportunity
rows + 0 cannibalization doesn't bias the cannibalization scale. Stored
as a float rounded to 4 decimals in the snapshot; rendered as a `▁▂▃▅▇`
sparkline-bar in the markdown table.

## Aggregate dimension semantics

```
aggregate_dimension="category"        → free-text cardinality buckets
                                        from master_task col F
aggregate_dimension="priority"        → fixed severityEnum 4 buckets
                                        (CRITICAL, HIGH, MEDIUM, LOW)
aggregate_dimension="primary_source"  → fixed 10-enum buckets from
                                        master_task col C; every enum
                                        value surfaces a bucket
                                        (count 0 included)
```

The `primary_source` mode is the strict coverage mode — every enum
value gets a row even at zero count, so reviewers can verify nothing is
silently missing. The 10 enum values are `[content_decay, quickwin,
tech_fix, schema, pillar, manual, sxo, cannibalization, redirect_404,
internal_links]` (Q-IL-1 closure added the `internal_links` value).

## DURUR conditions

Stop and flag the manager — do not patch, do not fall back.

1. **PortfolioConfigMissingError** — `portfolio.config.json` absent /
   unreadable. Run init-portfolio first.
2. **PortfolioConfigInvalidError** — payload failed Draft 7 validation
   against `schemas/portfolio-config.schema.json`. Schema-first violation.
3. **ActiveProjectsCeilingError** — `active_projects` > 8 (schema
   `maxItems` sentinel). Move surplus to `pending_onboard`.
4. **ReadOnlyContractViolation** — `cross_query.read_only != true`
   (schema `const: true`). The aggregator cannot run with read-only
   disabled.
5. **WorkspaceRootUnsetError** — could not resolve `portfolio_root`
   from arg / `PSEO_WORKSPACE_ROOT` env.
6. **AggregateDimensionInvalidError** *(per-skill)* —
   `aggregate_dimension` argument outside the 3-value enum {`category`,
   `priority`, `primary_source`}.

(Per-project missing `master.xlsx` and per-project missing individual
sheet are **NOT** DURURs — schema-valid empty shape with warning
surface, snapshot still emitted. W-E1 paterni reuse.)

## Idempotency contract

> **Re-run with identical workbook state → byte-identical snapshot
> + report.**

Mechanically:
1. Project ordering is deterministic (priority asc, slug asc).
2. `primary_source` bucket order pinned to schema enum order.
3. `priority` bucket order pinned to severityEnum order.
4. `category` bucket order alphabetic.
5. `generated_at` microsecond-truncated to second precision.
6. JSON output uses `sort_keys=True` + `indent=2`.

## READ-ONLY discipline

- NO `transaction.append` / `transaction.update` calls anywhere.
- NO `events_writer.append_*` calls anywhere (Q-RP-01 defer).
- `openpyxl.load_workbook(read_only=True, data_only=True)` for every
  master.xlsx open.
- `master.xlsx#none` outputs[] entry documents the READ-ONLY contract:
  no logical sheet is touched.
- `assert_read_only_module()` greps the source for `transaction.*`,
  `events_writer.*`, `.save(`, `.delete(`, `.append(` write tokens.

## Plugin agnostik

- Project slugs flow in via `portfolio.config.json.active_projects[].slug`.
- Zero hardcoded slug literals in the transform module (asserted by
  the worker brief acceptance gate #9 + the skill test suite's
  base64-obfuscated 8-slug grep guard).

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
    audit_target=f"reports:portfolio-heatmap:{report_date}",
    actor="agent:portfolio-heatmap",
    workspace_root=workspace_root,
    notes=f"local_aggregation report-only (portfolio-heatmap; date={report_date})",
)
```

## Cross-references

- Schemas: `schemas/portfolio-config.schema.json` v1.1
  (active_projects + cross_query.read_only),
  `schemas/master-excel.schema.json` (master_task col B/C/F/G,
  opportunity, quick_wins, content_decay, cannibalization),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/reporting/render_template.py`
  (`string.Template` `$$var` rendering convention reused inline).
- Transform: `scripts/reporting/portfolio_heatmap.py`.
- Template: `templates/reports/portfolio-heatmap.template.md`.
- Tests: `tests/skills/test_portfolio_heatmap.py` (≥6 cases incl.
  aggregate_dimension enum 3-sentinel, missing sheet schema-valid empty
  shape, multi-project merge, density normalization,
  primary_source 10-enum coverage, natural_language min length,
  forbidden tokens guard, READ-ONLY enforcement, path convention).
- Pattern reference: `scripts/reporting/portfolio_overview.py`
  (W-E3 — `assert_read_only_module()` helper),
  `scripts/reporting/portfolio_weekly_brief.py` (W-E4 — path
  convention + `PSEO_WORKSPACE_ROOT` env),
  `scripts/reporting/monthly_report.py` (W-E1 — schema-valid empty
  shape pattern).

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
- [x] F1: write target is **NOTHING** (read-only aggregator).
- [x] F5: `outputs.*` values are STRING-TYPED artifact paths.
- [x] Append-only state — `events.jsonl` NOT written (Phase 9 W2
      convention; Q-RP-01 deferred). Snapshot JSON is overwrite-safe
      because filename includes `{date}`.
- [x] READ-ONLY contract — no `.save(`, no `transaction.append(`,
      no `transaction.update(`, no `transaction.delete(` call sites
      in the transform module (verified by `assert_read_only_module()`).
- [x] cross_query.read_only=true (schema const) honored.
- [x] Path convention — `projects/_portfolio/{outputs,inbox}/local/`
      literal + `PSEO_WORKSPACE_ROOT` env (W-E4 paterni).
- [x] Schema-valid empty shape — missing sheet → empty bucket / 0.0
      density, NOT crash (W-E1 paterni reuse).
- [x] Forbidden tokens (4 + 8 slug grep CLEAN).
- [x] natural_language ≥ 30 char (worker pytest sentinel).
- [x] line count gate < 600 (transform).
