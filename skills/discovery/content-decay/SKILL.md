---
name: content-decay
description: |
  Use when: kullanıcı "içerik decay", "content decay", "tıklama düşen sayfalar",
  "ctr düştü", "90 gün öncesine göre azalma", "trafik kaybeden sayfalar",
  "decay analizi", "content_decay sheet yenile" der ya da /pseo-content-decay
  çağırır.
  Also use when: aktif projenin GSC verisi master.xlsx'te mevcut (gsc-pull
  önce çalışmış); 90-günlük recent + previous pencere karşılaştırması
  yapılacak; pillar bazlı içerik decay haritası lazım; downstream
  content-improve / new-content-plan skill'leri bu listeyi tüketecek.
  Do not use when: quick-win opportunity scoring (quick-wins skill), GSC
  delta ingestion (gsc-pull skill), tek-URL audit (tech-audit skill),
  cannibalization analizi — ayrı discovery skill'leri. Master.xlsx
  yokken çağırma; init-project + gsc-pull önce çalışmalı (DURUR #6).
version: "1.0"
status: wip
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project-config.json."
  days_back:
    type: integer
    required: false
    default: 90
    description: "Recent window length in days; previous window has equal length."
  dimensions:
    type: array
    required: false
    description: "GSC dimensions (default: ['page'])."
outputs:
  - "master.xlsx#content_decay"
  - "outputs/reports/{date}-content-decay.md"
  - "events.jsonl"
  - "inbox/gsc/{date}-enhanced_search_analytics-decay-recent-{slug}.json"
  - "inbox/gsc/{date}-enhanced_search_analytics-decay-previous-{slug}.json"
  - "inbox/dfs/{date}-historical_rank_overview-decay-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "gsc-pull:master.xlsx#gsc_performance"
produces:
  - "content-improve"
  - "new-content-plan"
  - "drift-check"
triggers:
  manual: ["/pseo-content-decay"]
  natural_language: |
    "içerik decay", "content decay", "tıklama düşen sayfalar", "ctr düştü",
    "90 gün öncesine göre azalma", "trafik kaybeden sayfalar",
    "decay analizi", "content_decay sheet yenile"
  hooks: []
  scheduled:
    - cron: "0 7 * * 1"
      mode: "report-only"
mcp_tools:
  required:
    - "mcp__gsc__enhanced_search_analytics"
  optional:
    - "mcp__dataforseo__dataforseo_labs_google_historical_rank_overview"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# content-decay — discovery skill (Phase 7 Wave 1)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline. Raw JSON drift recovery is mandatory:
every MCP response is dropped into `inbox/gsc/` (or `inbox/dfs/` for
the optional historical-rank cross-check) *before* any transform runs,
so a transform bug never costs us the upstream payload.

This skill follows the **convention authority** established by
`skills/discovery/quick-wins/SKILL.md` + the Phase 6 GSC ingestion
paterni `skills/ingestion/gsc-pull/SKILL.md`. The 10-step protocol shape,
raw JSON inbox discipline, URL normalization (D-03), DURUR + flag rule,
and provenance event format are reused verbatim — only the domain content
(window semantics, transform script, target sheet, optional DFS branch)
changes. Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name             | Type    | Default | Notes                                                  |
|------------------|---------|---------|--------------------------------------------------------|
| `project_slug`   | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.       |
| `days_back`      | integer | 90      | Recent window end=today, start=today-N. Previous window same length. |
| `dimensions`     | array   | ['page']| GSC dimensions for enhanced_search_analytics calls.    |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#content_decay` — per-page recent vs
  previous window decay rows (8 cols, schema-locked).
- `projects/{slug}/outputs/reports/{date}-content-decay.md` — human-
  readable summary (top decayed pages, trend distribution, pillars).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=gsc_mcp`; one per MCP call, plus optionally one
  `dataforseo_mcp` entry when the optional rank cross-check fires).
- `projects/{slug}/inbox/gsc/{date}-enhanced_search_analytics-decay-recent-{slug}.json`
  — raw MCP payload for the recent 90-day window (drift recovery).
- `projects/{slug}/inbox/gsc/{date}-enhanced_search_analytics-decay-previous-{slug}.json`
  — raw MCP payload for the previous 90-day window.
- (optional) `projects/{slug}/inbox/dfs/{date}-historical_rank_overview-decay-{slug}.json`
  — raw DFS historical rank cross-check payload (only when the
  optional branch is invoked AND its budget pre-flight passes).

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021, ADR-019).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="content-decay",
    project_slug=project_slug,
    steps=[
        {"name": "fetch_recent"},
        {"name": "fetch_previous"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `fetch_recent` (MCP §16.5 step 3 — raw inbox first)

Recent window (today - days_back .. today).

```python
workflow_runner.start_step(handle.run_id, 0,
                           project_slug=project_slug)
raw_recent = mcp__gsc__enhanced_search_analytics(
    siteUrl=project_config["gsc"]["site_url"],
    startDate=(today - days_back).isoformat(),
    endDate=today.isoformat(),
    dimensions=dimensions,    # default: ["page"]
)
inbox_recent = (
    workspace_root / "projects" / project_slug
    / "inbox" / "gsc"
    / f"{today.isoformat()}-enhanced_search_analytics-decay-recent-{project_slug}.json"
)
inbox_recent.parent.mkdir(parents=True, exist_ok=True)
inbox_recent.write_text(json.dumps(raw_recent, ensure_ascii=False, indent=2))
workflow_runner.finish_step(handle.run_id, 0,
                            project_slug=project_slug,
                            output_ref=str(inbox_recent))
```

### Step 3 — `fetch_previous` (previous window for delta — MUST succeed)

`mcp__gsc__enhanced_search_analytics` covering the PREVIOUS window of
equal length (today - 2*days_back .. today - days_back). Persist to
`inbox/gsc/{date}-enhanced_search_analytics-decay-previous-{slug}.json`.

**Both windows are required.** Unlike gsc-pull (where previous-window
failure is non-fatal first-run), decay analysis has no signal without
the comparison baseline. Failure here triggers DURUR #1 (do NOT proceed
with one-window data).

### Step 4 — `transform`

Pure compute via `scripts/discovery/content_decay_transform.py`:

```bash
python3 scripts/discovery/content_decay_transform.py \
    --recent   inbox/gsc/{date}-enhanced_search_analytics-decay-recent-{slug}.json \
    --previous inbox/gsc/{date}-enhanced_search_analytics-decay-previous-{slug}.json \
    --output-dir _state/transform/{run_id}/
```

Produces a JSON array (`content_decay`) shaped to the master-excel
schema. URL normalization (D-03) is applied here, not at fetch time, so
the raw inbox copy is byte-faithful to the MCP response. The transform
is idempotent: same inputs → byte-identical output. Sort: `clicks_delta`
ascending (most decayed first), then url asc for tie-break determinism.

### Step 4b — `optional_dfs_cross_check` (only when invoked)

When the optional `mcp__dataforseo__dataforseo_labs_google_historical_rank_overview`
branch is active, **first** run the budget pre-flight via
`scripts/budget/check_budget.py` against the project's 24h DFS credit
total.

- Budget pre-flight PASS → fetch DFS historical rank, persist raw to
  `inbox/dfs/{date}-historical_rank_overview-decay-{slug}.json`,
  enrich `action` with a short note (e.g. "rank also dropped in DFS")
  for rows where the DFS series confirms the decay direction.
- Budget pre-flight FAIL → **DURUR #7** (`StopAndAwaitApproval`). Do
  NOT silently fall back to GSC-only. The skill exits with
  `awaiting_approval`; the manager must explicitly authorize either
  raising the budget cap or skipping the cross-check (recorded as an
  ADR), then resume.

```python
from scripts.budget import check_budget
budget_envelope = check_budget.preflight(
    project_config_path=project_root / "project-config.json",
    events_path=project_root / "_state" / "events.jsonl",
    estimated_credits=1,    # one DFS historical_rank_overview call
)
if budget_envelope["exceeded"]:
    workflow_runner.request_approval(
        handle.run_id, project_slug=project_slug,
        approver="user",
        subject="DFS historical_rank cross-check budget aşıldı; cap yükseltilsin mi?",
        step_index=3,
    )
    raise BudgetGateError("DFS budget pre-flight failed; awaiting_approval")
```

### Step 5 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"Content decay {len(rows)} URL hesaplandı, master.xlsx#content_decay'e yazalım mı?",
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

Single `transaction.append` call for the content_decay sheet. Goes
through the single approved write path with backup, lock, schema
validation, and post-write provenance event emission. **Note:** the
transform module itself does NOT import `scripts.excel.transaction` —
only the skill orchestrator layer does (cross-module IMPORT discipline).

```python
from scripts.excel import transaction
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="content_decay",
    rows=content_decay_rows,
    project_slug=project_slug,
    writer="content-decay",
)
```

### Step 8 — `render_report`

`render_template.py templates/reports/content-decay.template.md data.json`
→ `outputs/reports/{date}-content-decay.md`. Variables: `$project_slug`,
`$date`, `$days_back`, `$total_urls`, `$decay_count`, `$retired_count`,
`$top_decay_url`, `$top_decay_delta`, `$report_summary`.

### Step 9 — Provenance event

One provenance entry per MCP call (two for GSC, plus one DFS when the
optional branch fires).

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={"kind": "gsc_mcp", "mcp_server": "gsc",
            "mcp_tool": "gsc__enhanced_search_analytics",
            "response_bytes": len(json.dumps(raw_recent))},
    operation="project_excel",
    target_excel_sheet="content_decay",
    rows_written=len(content_decay_rows),
)
# Repeat for raw_previous (also gsc_mcp). When DFS branch ran:
# source.kind=dataforseo_mcp + cost.credits=1 + budget_key.
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "content_decay_rows":      str(len(content_decay_rows)),
    "decay_count":             str(meta["trend_counts"]["DECAY"]),
    "retired_count":           str(meta["trend_counts"]["RETIRED"]),
    "report_path":             str(report_path),
    "raw_recent":              str(inbox_recent),
    "raw_previous":            str(inbox_previous),
})
```

## URL normalization (D-03 invariant)

Every URL passing through this skill is normalized via
`scripts.discovery.content_decay_transform.normalize_url`. The function
is **idempotent**: `normalize_url(normalize_url(u)) == normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports, strip
trailing slash (root excluded), drop fragment, drop tracking params,
sort remaining query keys.

The transform self-checks idempotency on every emitted URL — a drift
between transform and downstream consumers is escalated as DURUR #3
rather than silently masked.

## Period delta semantics

```
recent   window:  [today - days_back, today]            (default 90d)
previous window:  [today - 2*days_back, today - days_back]
```

Both windows must have **equal length**. The transform aggregates clicks
per normalized URL across each window, then computes:

```
clicks_delta = clicks_recent - clicks_previous
delta_pct    = (clicks_recent - clicks_previous) / clicks_previous * 100,
               rounded 2dp; clamped to ±100 when previous=0
               (mirrors gsc-pull's _delta_pct, Phase 6 paterni)
trend        = NEW       if previous=0 and recent>0
               RETIRED   if recent=0  and previous>0
               DECAY     if delta_pct ≤ -20
               GROWTH    if delta_pct ≥ +20
               STABLE    otherwise
pillar       = first non-empty path segment (e.g. /blog/x → "blog")
action       = trend → deterministic prescription
                 DECAY   → "investigate + refresh"
                 STABLE  → "monitor"
                 GROWTH  → "double-down"
                 NEW     → "new content tracking"
                 RETIRED → "redirect or revive review"
```

## DURUR conditions (9)

Stop and flag the manager — do not patch, do not fall back.

1. Either `mcp__gsc__enhanced_search_analytics` call (recent OR
   previous) returns auth/network/scope error. Decay analysis has no
   signal without both windows; STOP — do not proceed with one-window
   data.
2. Raw JSON inbox path cannot be created (workspace path missing or
   non-writable).
3. URL normalization output drifts (idempotency check fails inside
   `content_decay_transform.transform`).
4. `master.xlsx#content_decay` column count or names don't match
   schema (`schemas/master-excel.schema.json#content_decay`,
   8 required_columns).
5. `transaction.append` raises `RowSchemaError` for `content_decay`.
6. `workflow_runner.create_run` fails schema validation.
7. **Optional DFS `historical_rank_overview` invoked AND budget pre-
   flight FAILS** → STOP, transition to `awaiting_approval`. Manager
   bilgilendirilir; do NOT silently fall back to GSC-only (false-success
   failure mode the brief explicitly forbids).
8. Both windows aggregate to zero rows (`ContentDecayError: no data in
   window`). Decay-specific: there is no signal to project.
9. Window dates overlap (caller logic error; recent.start ≤
   previous.end). Decay-specific guard against silently double-counting.
   The skill orchestrator validates window arithmetic before fetch.

`PSEO_WORKSPACE_ROOT` env unset → also a STOP (inherited from
`workflow_runner` / `events_writer` discipline; folded into DURUR #2's
"workspace path missing" surface).

## Cross-references

- Schemas: `schemas/master-excel.schema.json` (content_decay sheet,
  8 required_columns at lines 158-170), `schemas/events.schema.json`
  (`source.kind=gsc_mcp` / `dataforseo_mcp`,
  `target_excel_sheet=content_decay`),
  `schemas/gsc-tool-mapping.schema.json` (D-03 invariant),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`,
  `scripts/budget/check_budget.py` (optional DFS branch only —
  not for the GSC-only path).
- Transform: `scripts/discovery/content_decay_transform.py`
  (`normalize_url`, `infer_pillar`, `transform`,
  `CONTENT_DECAY_COLUMNS`, `ContentDecayError`).
- Tests: `tests/skills/test_content_decay.py` (≥6 cases incl. trend
  coverage, ±100 clamp, sort, schema column match, smoke E2E).
- Template: `templates/reports/content-decay.template.md`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
      The optional DFS branch's budget-fail path is `awaiting_approval`,
      not a silent GSC-only fallback.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
      0-tolerance ADR-008 + D-010 Path B.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` / `check_budget` are imported,
      never modified from this skill. The transform module itself does
      NOT import `scripts.excel.transaction` (skill-orchestrator-only).
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] Append-only state — events emitted via `events_writer.append_provenance`,
      one per MCP call; workflow run JSON only forward-flips step status.
