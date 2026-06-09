---
name: master-task-sync
description: |
  Use when: kullanıcı "master task sync", "task aggregation", "master_task
  toplama", "auto task sync", "task SSoT", "tek liste", "tüm taskları
  birleştir", "master_task güncelle" der ya da /pseo-master-task-sync
  çağırır.
  Also use when: Phase 7 + Phase 8 Wave 1 master writer skill'leri (5
  discovery + 3 planning) tamamlanmış; cannibalization / content_decay /
  tech_seo / on_page_audit / schema / cluster_keywords / topical_map /
  new_content_plan sheet'leri master.xlsx'te dolu; ingestion + discovery +
  planning wave'leri sonrası tek planning pass'i olarak çalıştırılır;
  sonuç master.xlsx#master_task auto_generated rows + D-only merge.
  Do not use when: master.xlsx yokken (init-project önce çalışmalı,
  DURUR #9); upstream sheet'lerin hiçbiri doldurulmamış (önce ilgili
  discovery/planning skill'lerini çağır, DURUR #1); manuel master_task
  rows mutate edilecek (FORBIDDEN — protected_columns + auto_generated=false
  satırlara DOKUNMAZ); sadece bir tek source sheet'in task'ları lazım
  (o skill'in master writer çıktısı zaten yazıldı, bu skill SSoT
  toplaması için).
version: "1.0"
status: active
category: planning
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx."
  default_status:
    type: string
    required: false
    default: "TODO"
    description: "statusEnum seed value for new master_task rows (default TODO)."
  require_all_sheets:
    type: boolean
    required: false
    default: false
    description: "DURUR #1: raise if any of the 8 expected upstream sheets is absent. Default false (tolerant of partial Phase 7+8 state)."
outputs:
  - "master.xlsx#master_task"
  - "outputs/reports/{date}-master-task-sync.md"
  - "events.jsonl"
  - "inbox/local/{date}-master_task_sync-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "cannibalization:master.xlsx#cannibalization"
  - "content-decay:master.xlsx#content_decay"
  - "tech-audit:master.xlsx#tech_seo"
  - "on-page-audit:master.xlsx#on_page_audit"
  - "schema-audit:master.xlsx#schema"
  - "cluster-map:master.xlsx#cluster_keywords"
  - "topical-map:master.xlsx#topical_map"
  - "new-content-plan:master.xlsx#new_content_plan"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-master-task-sync"]
  natural_language: |
    "master task sync", "task aggregation", "master_task toplama",
    "auto task sync", "task SSoT", "tek liste",
    "tüm taskları birleştir", "master_task güncelle"
  hooks: []
  scheduled:
    - cron: "0 9 * * 4"
      mode: "report-only"
mcp_tools:
  required: []
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# master-task-sync — planning skill (Phase 8 Wave 2)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §8.5 master_task SSoT discipline. **No MCP**, **no DFS**, **no
budget pre-flight** — this is purely a *local aggregation* skill that
reads existing master.xlsx sheets and emits new master_task rows OR
merges the `related_sources` (D) column on existing rows.

This skill follows the **convention authority** established by
`skills/planning/internal-links/SKILL.md` (Phase 8 Wave 1 — master_task
writer pattern) and `skills/discovery/cannibalization/SKILL.md` (Phase 7
Wave 1 — 10-step protocol shape). The protocol shape, raw envelope
discipline, DURUR + flag rule, and provenance event format are reused
verbatim — only the source (8 local master.xlsx sheets instead of GSC
or SF CSV) and the writer scope (append + D-only merge instead of
full-row write) change. Deviate only with an ADR.

Unlike Phase 7 / Wave 1 skills that *produce* their own master writer
sheets, master-task-sync *aggregates* them into the master_task SSoT.
Per `master-excel.schema.json#/sheets/master_task/allowed_writers`
the writer name `master_task_sync` is whitelisted; per
`#/sheets/master_task/writer_scope` this writer is restricted verbatim to:

> "append new auto-generated rows AND merge related_sources (D);
>  forbidden to touch protected_columns"

`protected_columns` (`#/sheets/master_task/protected_columns`) are 7 columns
[B, F, G, H, I, M, N] = [task, category, priority, impact,
duration_est_min, assignee, note]. The transform raises
`ProtectedColumnsWriteAttempt` if a payload ever tries to populate any
of those — this is the schema-first defensive guard that keeps the
human / done_protocol writers' authority intact.

## Inputs (frontmatter contract)

| Name                  | Type    | Default | Notes                                                       |
|-----------------------|---------|---------|-------------------------------------------------------------|
| `project_slug`        | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.            |
| `default_status`      | string  | "TODO"  | statusEnum seed for new appended rows.                      |
| `require_all_sheets`  | boolean | false   | DURUR #1: raise if any of 8 upstream sheets is absent.       |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#master_task` — auto_generated rows
  appended (new) + `related_sources` (D) merged (existing). Protected
  columns (B/F/G/H/I/M/N) are LEFT BLANK on append; the human +
  done_protocol writers populate them later.
- `projects/{slug}/outputs/reports/{date}-master-task-sync.md` —
  human-readable summary (total tasks, append/merge stats, per-source
  breakdown, primary_source distribution).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=tool_computed`,
  `target_excel_sheet=master_task`).
- `projects/{slug}/inbox/local/{date}-master_task_sync-{slug}.json` —
  drift-recovery snapshot of the full aggregation result.

## Upstream sheets consumed (8)

| # | Sheet              | Producer skill   | Phase | primary_source emitted        |
|---|--------------------|------------------|-------|-------------------------------|
| 1 | `cannibalization`  | cannibalization  | 7 W1  | `cannibalization`             |
| 2 | `content_decay`    | content-decay    | 7 W1  | `content_decay`               |
| 3 | `tech_seo`         | tech-audit       | 7 W1  | `tech_fix`                    |
| 4 | `on_page_audit`    | on-page-audit    | 7 W1  | per-row (tech_fix/schema/manual) |
| 5 | `schema`           | schema-audit     | 7 W2  | `schema`                      |
| 6 | `cluster_keywords` | cluster-map      | 8 W1  | `pillar`                      |
| 7 | `topical_map`      | topical-map      | 8 W1  | `pillar`                      |
| 8 | `new_content_plan` | new-content-plan | 8 W1  | `pillar`                      |

The `internal-links` planning skill (Phase 8 W-C4) writes its own
master_task entries directly with `primary_source="tech_fix"` (Q-IL-1
substitute — the master_task primary_source enum has no
`internal_links` value). master-task-sync reads master_task itself when
detecting existing rows and treats those entries normally.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021, ADR-019).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="master-task-sync",
    project_slug=project_slug,
    steps=[
        {"name": "read_upstream_sheets"},
        {"name": "aggregate"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `read_upstream_sheets` (master.xlsx → row dicts)

Read the 8 upstream master writer sheets + the existing master_task
into row-dict form. No MCP call. The skill body uses
`openpyxl.load_workbook(read_only=True)` and converts each row into a
`dict` keyed by the schema column names.

```python
workflow_runner.start_step(handle.run_id, 0, project_slug=project_slug)
sources = read_master_xlsx_sheets(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheets=[s.sheet for s in SOURCE_DEFS],
)
existing_master_task = read_master_xlsx_sheets(
    workbook_path=...,
    sheets=["master_task"],
)["master_task"]
workflow_runner.finish_step(handle.run_id, 0, project_slug=project_slug,
                            output_ref="memory://upstream-rows")
```

### Step 3 — `aggregate`

Pure compute via `scripts/planning/master_task_sync.aggregate()`:

```python
from scripts.planning import master_task_sync as mts
batch = mts.aggregate(
    sources=sources,
    existing_master_task=existing_master_task,
    run_date=today_iso,
    default_status=default_status,
    expected_sheets=[s.sheet for s in mts.SOURCE_DEFS] if require_all_sheets else None,
)
```

Returns an `AggregateBatch` describing what to change:
- `appends` — list of new master_task rows (full 19-col dicts, protected
  columns blank-seeded);
- `merges` — list of `(task_id, new_related_sources)` pairs to apply to
  existing auto_generated rows (D-column only);
- `skipped_manuel` — count of auto_generated=false rows left untouched;
- `no_op_count` — count of auto rows where the related_source_key was
  already in D.

The transform is idempotent: same input → byte-identical output.

If `len(batch.appends) == 0 and len(batch.merges) == 0`, the skill
SKIPS write_excel and emits a "master_task already in sync" notice
(DURUR #4 vehicle inverted — it's a clean exit, not an error).

Drift-recovery snapshot is written immediately:

```python
snapshot = mts.build_snapshot(batch=batch, run_date=today_iso,
                              project_slug=project_slug)
inbox_path = (
    workspace_root/"projects"/project_slug/"inbox"/"local"
    / f"{today_iso}-master_task_sync-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2,
                                 sort_keys=True))
```

### Step 4 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=(
        f"{len(batch.appends)} yeni task + {len(batch.merges)} D-merge "
        f"master_task'a yazılacak (manuel rows korunur, protected_columns blank). "
        "Onaylıyor musun?"
    ),
    step_index=2,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 5 — Resume (`approve` → continue)

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug,
                        approver="user")
```

### Step 6 — `write_excel` (atomic, schema-validated, writer=master_task_sync)

Single `transaction.append` for new rows + per-row `transaction.update`
for D-merges. The writer name is the schema-allowed value
`master_task_sync`. The transaction layer enforces `_check_writer_scope`
(allowed_writers gate).

```python
from scripts.excel import transaction

# Appends — new auto_generated rows.
if batch.appends:
    transaction.append(
        workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
        sheet="master_task",
        rows=batch.appends,
        project_slug=project_slug,
        writer="master_task_sync",
    )

# D-only merges — per task_id update of related_sources column ONLY.
for task_id, new_d in batch.merges:
    transaction.update(
        workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
        sheet="master_task",
        where={"task_id": task_id},
        set_={"related_sources": new_d},
        project_slug=project_slug,
        writer="master_task_sync",
    )
```

A defensive guard inside `master_task_sync._build_master_task_row`
ensures every row passes through `_ensure_no_protected_writes` BEFORE
the transaction layer ever sees it — protected_columns violations are
surfaced as `ProtectedColumnsWriteAttempt` (DURUR #6) at build time, not
at write time.

### Step 7 — `render_report`

`build_report_markdown(batch=...)` →
`outputs/reports/{date}-master-task-sync.md`. Variables auto-derived
from the batch: append/merge totals, per-source emit counts,
primary_source distribution.

### Step 8 — Provenance event

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    # source.kind MUST be a valid events.schema source.kind enum value.
    # Local aggregation is an in-process, non-external-ingest action →
    # "tool_computed" (the same kind init-project uses for bootstrap).
    # The events.schema `source` object is additionalProperties:false,
    # so `module` / `sheets_aggregated` are NOT valid keys and are
    # dropped (aggregation detail belongs in `notes`, not `source`).
    source={"kind": "tool_computed"},
    operation="project_excel",
    target_excel_sheet="master_task",
    rows_written=len(batch.appends) + len(batch.merges),
)
```

### Step 9 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED
    "appends_count":  str(len(batch.appends)),
    "merges_count":   str(len(batch.merges)),
    "skipped_manuel": str(batch.skipped_manuel),
    "report_path":    str(report_path),
    "snapshot_path":  str(inbox_path),
})
```

### Step 10 — Done

Workflow status flips `running → done` (workflow-run schema) and a
`workflow_action=done` event lands in `events.jsonl` (ADR-020).

## task_id heuristic

```
task_id = sha256("{primary_source}|{url}|{task_signature}")[:16]
```

The hex prefix length is **16 characters (64 bits)** — picked for
collision-resistance over typical row volumes (< 5000 / project).
`scripts/planning/master_task_sync.TaskIdCollisionError` (DURUR #3)
fires if two distinct payloads ever hash to the same prefix.

The per-source `task_signature` is declared in `SOURCE_DEFS`
(`scripts/planning/master_task_sync.py`):

| Sheet              | url_col       | signature_cols                          |
|--------------------|---------------|-----------------------------------------|
| `cannibalization`  | (none)        | `(conflict_pair,)`                      |
| `content_decay`    | `url`         | `(url,)`                                |
| `tech_seo`         | (none)        | `(issue_category, detail)`              |
| `on_page_audit`    | `url`         | `(url, target_query)`                   |
| `schema`           | (none)        | `(schema_type, location)`               |
| `cluster_keywords` | `assigned_url`| `(cluster, keyword)`                    |
| `topical_map`      | `assigned_url`| `(pillar, cluster, primary_keyword)`    |
| `new_content_plan` | (none)        | `(url_slug, primary_keyword)`           |

Each tuple entry is `_safe_str()`-coerced and joined with `|` before
being fed into the sha256 input. Empty signature columns produce empty
fingerprint segments — the row is skipped (None signature) only when
ALL signature columns are blank.

## Aggregation logic (revised semantic)

```
1. Read upstream sheets + existing master_task.
2. For each upstream row of each sheet:
     - extract (primary_source, url, signature) → task_id (sha256[:16]).
     - lookup task_id in existing_master_task index.
     - new task_id (no match):
         APPEND full row (19 cols), protected cols blank-seeded.
     - existing task_id, auto_generated=true:
         MERGE related_sources (D) ONLY. Other cols UNTOUCHED.
         (split-by-pipe → append source-key → dedupe → sort → rejoin.)
     - existing task_id, auto_generated=false:
         SKIP entirely. Manuel entries are sacrosanct.
3. Schema validate every appended row (19-col tuple +
   primary_source enum + protected_columns sentinel).
4. Sort appends deterministically by (primary_source, url, task_id) and
   merges by task_id, so re-runs produce byte-stable output order.
```

## Idempotency contract

> **Re-run with identical Phase 7+8 state → identical master_task state.
> Re-run after new sheet rows → new task appends OR D-merges only.**

Mechanically:
1. `task_id` derivation is deterministic (sha256 with no salt / clock
   dependency / slug dependency). Same input → same output.
2. After the first run, the second run finds every task_id already in
   `existing_master_task` with `auto_generated=true`. The merge step
   resolves to a no-op because the related_source_key is already
   present in D (`merge_related_sources` is itself idempotent).
3. The smoke test `test_master_task_sync_idempotent_rerun_state_identical`
   asserts: 2× consecutive aggregate() runs produce identical
   AggregateBatch shapes (0 appends + 0 actual merges on the second
   pass).

`assert_idempotent_state(first_state, second_state)` is the public
helper that wraps this assertion (used by the test + can be invoked
defensively by the skill body).

## protected_columns guard (`#/sheets/master_task/protected_columns`)

The 7 protected columns are owned by the human + done_protocol writers:

| Col | Name                | Owner                                |
|-----|---------------------|--------------------------------------|
| B   | `task`              | human (free-text task description)    |
| F   | `category`          | human (e.g. "internal-links")        |
| G   | `priority`          | human (severityEnum)                  |
| H   | `impact`            | human                                 |
| I   | `duration_est_min`  | human (integer)                       |
| M   | `assignee`          | human                                 |
| N   | `note`              | human                                 |

`master_task_sync` is FORBIDDEN from writing to any of those. The
defensive guard `_ensure_no_protected_writes(payload)` raises
`ProtectedColumnsWriteAttempt` (DURUR #6) if a payload ever populates
one of these columns with a non-blank value. Empty-string seeds (used
to pad a new row to its full 19-col shape) are tolerated — the Excel
write layer treats blank seeds as no-ops at the cell level.

## writer_scope semantic (`#/sheets/master_task/writer_scope` — verbatim)

> "append new auto-generated rows AND merge related_sources (D);
>  forbidden to touch protected_columns"

The `merge_column(column_name, ...)` helper enforces D-only merges:
calling it with any other column raises `WriterScopeViolation`
(DURUR #7).

## DURUR conditions (≥9)

Stop and flag the manager — do not patch, do not fall back.

1. **SheetMissingError** — `require_all_sheets=true` and one of the 8
   expected sheets (`cannibalization`, `content_decay`, `tech_seo`,
   `on_page_audit`, `schema`, `cluster_keywords`, `topical_map`,
   `new_content_plan`) is absent from `master.xlsx`. STOP, run the
   prior skill first.
2. **ColumnTupleDriftError** — emitted master_task row column tuple
   drifts from the schema 19-col tuple. STOP, schema-first violation.
3. **TaskIdCollisionError** — two distinct (primary_source, url,
   signature) payloads produced the same sha256[:16] task_id. STOP,
   bump `TASK_ID_PREFIX_LEN` and rebuild.
4. **IdempotencyDriftError** — `assert_idempotent_state` detected
   divergence between two consecutive `aggregate()` runs. STOP, the
   transform is not deterministic.
5. **PrimarySourceEnumViolation** — aggregator emitted a
   `primary_source` value not in the closed schema enum. STOP.
6. **ProtectedColumnsWriteAttempt** — payload row tries to populate a
   protected_columns field (B/F/G/H/I/M/N). STOP, schema-first violation
   per writer_scope + protected_columns
   (`#/sheets/master_task/writer_scope` + `#/sheets/master_task/protected_columns`).
7. **WriterScopeViolation** — merge attempted on a column other than
   `related_sources` (D). STOP, only D is mergeable for
   master_task_sync.
8. **WorkflowRunnerSchemaError** — `workflow_runner.create_run` failed
   schema validation. STOP, state init drift.
9. **WorkspaceRootUnsetError** — `PSEO_WORKSPACE_ROOT` env var unset
   AND no explicit `workspace_root` arg passed; cannot resolve
   `projects/{slug}/`. STOP, surface to manager.

## Cross-references

- Schemas: `schemas/master-excel.schema.json#/sheets/master_task`
  (`required_columns` 19 cols +
  `#/sheets/master_task/allowed_writers` +
  `#/sheets/master_task/writer_scope` +
  `#/sheets/master_task/protected_columns` +
  `#/definitions/statusEnum` + `#/definitions/severityEnum`),
  `schemas/events.schema.json` (`source.kind=tool_computed`,
  `target_excel_sheet=master_task`), `schemas/skill-frontmatter.schema.json`
  (this frontmatter), `schemas/cross-sheet-invariants.json` (D-01 is
  topical_map.pillar — *not* a master_task invariant; master_task
  authority is intra-sheet via allowed_writers + writer_scope +
  protected_columns).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py` (or
  `master_task_sync.build_report_markdown` directly).
- Transform: `scripts/planning/master_task_sync.py`.
- Tests: `tests/skills/test_master_task_sync.py` (≥10 cases incl.
  smoke + idempotency + protected_columns guard + writer_scope guard).
- Pattern reference: `scripts/planning/internal_links_transform.py`
  (Phase 8 W-C4 master_task writer pattern).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Every
      `primary_source` write checked against the closed enum.
      Every appended row checked against `protected_columns`.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` are imported, never modified
      from this skill. The transform module has 0 imports from
      `scripts.excel.transaction` (skill body does the writes).
- [x] D-003 helper IMPORT NOT applicable — local aggregation, no DFS
      payload is consumed (intentionally absent — documented in
      module docstring).
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] Append-only state — `events.jsonl` only grows; no in-place
      rewrite. master_task itself is mutated only via
      `transaction.append` (new rows) + `transaction.update`
      (D-only merge); no row deletions.
- [x] Idempotency contract: re-run with identical state → byte-stable
      output (asserted by smoke test).
- [x] Q-IL-1 substitute: internal-links rows live as
      `primary_source="tech_fix"` per W-C4; this skill reads them
      through the master_task index and merges D normally.
