---
name: gsc-pull
description: |
  Use when: kullanıcı "gsc çek", "search console verisi al", "gsc performance
  güncelle", "tıklanma gösterim delta", "son 28 gün GSC", "period delta",
  "gsc_performance sheet yenile" der ya da /pseo-gsc-pull çağırır.
  Also use when: aktif projenin master.xlsx'i mevcut; gsc_performance sheet'i
  güncellenmesi gerekiyor (recent vs previous window delta); F-08 invariant
  (quick_wins.url ⊆ (crawl_sitemap.url ∪ gsc_performance.url)) tetiklenmeden önce
  gsc_performance dolu olmalı; quick-wins / content-decay downstream skill'leri
  bu veriye bağımlı.
  Do not use when: quick-win opportunity scoring (quick-wins skill), content
  decay 90d analiz (content-decay skill), index inspection tek-URL audit
  (tech-audit skill) — ayrı ingestion / discovery skill'leri. Master.xlsx
  yokken çağırma; init-project önce çalışmalı (DURUR #6).
version: "1.0"
status: active
category: ingestion
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
  days_back:
    type: integer
    required: false
    default: 28
    description: "Recent window length in days; previous window has equal length."
  dimensions:
    type: array
    required: false
    description: "GSC dimensions (default: ['page'])."
outputs:
  - "master.xlsx#gsc_performance"
  - "outputs/reports/{date}-gsc-pull.md"
  - "events.jsonl"
  - "inbox/gsc/{date}-search_analytics-{slug}.json"
  - "inbox/gsc/{date}-enhanced_search_analytics-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
produces:
  - "quick-wins"
  - "content-decay"
  - "drift-check"
triggers:
  manual: ["/pseo-gsc-pull"]
  natural_language: |
    "gsc çek", "search console verisi al", "gsc performance güncelle",
    "tıklanma gösterim delta", "son 28 gün GSC", "period delta",
    "gsc_performance sheet yenile"
  hooks: []
  scheduled:
    - cron: "0 6 * * *"
      mode: "report-only"
mcp_tools:
  required:
    - "mcp__gsc__enhanced_search_analytics"
    - "mcp__gsc__search_analytics"
  optional:
    - "mcp__gsc__index_inspect"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# gsc-pull — ingestion skill (Phase 6 Wave 1)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline. Raw JSON drift recovery is mandatory:
every MCP response is dropped into `inbox/gsc/` *before* any transform
runs, so a transform bug never costs us the upstream payload.

This skill follows the **convention authority** established by
`skills/discovery/quick-wins/SKILL.md`. The 10-step protocol shape, raw
JSON inbox discipline, URL normalization (D-03), DURUR + flag rule, and
provenance event format are reused verbatim — only the domain content
(MCP tool, transform script, target sheet) changes. Deviate only with
an ADR.

## Inputs (frontmatter contract)

| Name             | Type    | Default | Notes                                                  |
|------------------|---------|---------|--------------------------------------------------------|
| `project_slug`   | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.      |
| `days_back`      | integer | 28      | Recent window end=today, start=today-N. Previous window same length. |
| `dimensions`     | array   | ['page']| GSC dimensions for the search_analytics call.          |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#gsc_performance` — per-page recent vs
  previous window delta rows (12 cols, schema-locked).
- `projects/{slug}/outputs/reports/{date}-gsc-pull.md` — human-readable
  summary (top-rising / top-decay pages).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=gsc_mcp`).
- `projects/{slug}/inbox/gsc/{date}-search_analytics-{slug}.json` —
  raw MCP payload for the recent window (drift recovery).
- `projects/{slug}/inbox/gsc/{date}-enhanced_search_analytics-{slug}.json`
  — raw MCP payload for the previous window (drift recovery).

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021, ADR-019).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="gsc-pull",
    project_slug=project_slug,
    steps=[
        {"name": "fetch_search_analytics"},
        {"name": "fetch_enriched"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `fetch_search_analytics` (MCP §16.5 step 3 — raw inbox first)

Recent window (today - days_back .. today).

```python
workflow_runner.start_step(handle.run_id, 0,
                           project_slug=project_slug)
raw = mcp__gsc__search_analytics(
    siteUrl=project_config["gsc"]["site_url"],
    startDate=(today - days_back).isoformat(),
    endDate=today.isoformat(),
    dimensions=dimensions,  # default: ["page"]
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "gsc"
    / f"{today.isoformat()}-search_analytics-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
workflow_runner.finish_step(handle.run_id, 0,
                            project_slug=project_slug,
                            output_ref=str(inbox_path))
```

### Step 3 — `fetch_enriched` (previous window for delta)

`mcp__gsc__enhanced_search_analytics` covering the PREVIOUS window of
equal length (today - 2*days_back .. today - days_back). Persist to
`inbox/gsc/{date}-enhanced_search_analytics-{slug}.json`. Failure is
non-fatal — the transform tolerates `enriched=None` and produces
previous-window zeros.

### Step 4 — `transform`

Pure compute via `scripts/ingestion/gsc_pull.py`:

```bash
python3 scripts/ingestion/gsc_pull.py \
    --raw  inbox/gsc/{date}-search_analytics-{slug}.json \
    --enriched inbox/gsc/{date}-enhanced_search_analytics-{slug}.json \
    --output-dir _state/transform/{run_id}/
```

Produces a JSON array (`gsc_performance`) shaped to the master-excel
schema. URL normalization (D-03) is applied here, not at fetch time, so
the raw inbox copy is byte-faithful to the MCP response. The transform
is idempotent: same inputs → byte-identical output.

### Step 5 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"GSC delta {len(rows)} URL hesaplandı, master.xlsx#gsc_performance'a yazalım mı?",
    step_index=3,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 6 — Resume (`approve` → continue)

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug,
                        approver="user")
```

### Step 7 — `write_excel` (atomic, schema-validated)

Single `transaction.append` call for the gsc_performance sheet. Goes
through the single approved write path with backup, lock, schema
validation, and post-write provenance event emission.

```python
from scripts.excel import transaction
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="gsc_performance",
    rows=gsc_performance_rows,
    project_slug=project_slug,
    writer="gsc-pull",
)
```

### Step 8 — `render_report`

`render_template.py templates/reports/gsc-pull.template.md data.json`
→ `outputs/reports/{date}-gsc-pull.md`. Variables (must match the
template's `$tokens` exactly — `render_template.main` hard-fails on any
mismatch): `$project_slug`, `$date`, `$days_back`, `$row_count_recent`,
`$row_count_previous`, `$unique_urls`, `$top_5_pages`, `$delta_summary`,
`$run_id`, `$rows_written`.

### Step 9 — Provenance event

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "gsc_mcp", "mcp_server": "gsc",
            "mcp_tool": "gsc__search_analytics",
            "response_bytes": len(json.dumps(raw))},
    operation="project_excel",
    target_excel_sheet="gsc_performance",
    rows_written=len(gsc_performance_rows),
)
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED
    "gsc_performance_rows": str(len(gsc_performance_rows)),
    "report_path": str(report_path),
    "raw_recent": str(inbox_path),
    "raw_previous": str(enriched_path),
})
```

## URL normalization (D-03 invariant)

Every URL passing through this skill is normalized via
`scripts.ingestion.gsc_pull.normalize_url`. The function is
**idempotent**: `normalize_url(normalize_url(u)) == normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports, strip
trailing slash (root excluded), drop fragment, drop tracking params,
sort remaining query keys.

The transform self-checks idempotency on every emitted URL — a drift
between transform and downstream consumers is escalated as DURUR #3
rather than silently masked.

## Period delta semantics

```
recent   window:  [today - days_back, today]
previous window:  [today - 2*days_back, today - days_back]
```

Both windows must have **equal length**. The transform aggregates
metrics per normalized URL across each window, then computes:

```
clicks_delta      = clicks_recent - clicks_previous
clicks_delta_pct  = (clicks_recent - clicks_previous) / clicks_previous * 100
impressions_delta = impressions_recent - impressions_previous
position_recent   = impression-weighted mean position in recent window
position_previous = impression-weighted mean position in previous window
ctr_recent        = clicks_recent / impressions_recent * 100
note              = rising | stable | decay | no-clicks (deterministic from delta_pct)
```

`clicks_delta_pct` clamps to ±100 when `previous == 0` to avoid
division-by-zero amplification.

## DURUR conditions (8)

Stop and flag the manager — do not patch, do not fall back.

1. `mcp__gsc__search_analytics` returns auth/network/scope error
   (recent or previous window). The recent fetch is required;
   previous-window failure is non-fatal but logged.
2. Raw JSON inbox path cannot be created (workspace path missing or
   non-writable).
3. URL normalization output drifts (idempotency check fails inside
   `gsc_pull.transform`).
4. `master.xlsx#gsc_performance` column count or names don't match
   schema (`schemas/master-excel.schema.json#gsc_performance`).
5. `transaction.append` raises `RowSchemaError` for `gsc_performance`.
6. `workflow_runner.create_run` fails schema validation.
7. `PSEO_WORKSPACE_ROOT` env unset and no explicit `workspace_root` arg
   passed to `workflow_runner` / `events_writer`.
8. `project.config.json` missing `gsc.site_url` (or file absent under
   `projects/{slug}/`).

## Cross-references

- Schemas: `schemas/master-excel.schema.json` (gsc_performance sheet,
  12 required_columns), `schemas/events.schema.json`
  (`source.kind=gsc_mcp`), `schemas/gsc-tool-mapping.schema.json`
  (D-03 invariant + url_original/url_normalized staging),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`.
- Transform: `scripts/ingestion/gsc_pull.py`.
- Tests: `tests/skills/test_gsc_pull.py` (≥6 cases incl. smoke E2E).
- Template: `templates/reports/gsc-pull.template.md` (Phase 6 Wave 2).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` are imported, never modified
      from this skill.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] F-08 unblock: gsc_performance population satisfies the
      quick_wins.url ⊆ (crawl_sitemap.url ∪ gsc_performance.url) invariant
      precondition (the active F-08 rule enforced by check_F_08; the deferred
      `target_url` form is disclaimed in cross-sheet-invariants.json).
