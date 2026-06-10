---
name: cannibalization
description: |
  Use when: kullanıcı "cannibalization", "kannibalizasyon", "keyword
  conflict", "aynı keyword'e iki sayfa", "URL çakışması", "anahtar kelime
  çakışması", "iki sayfam aynı sorguya çıkıyor", "intent split" der ya
  da /pseo-cannibalization çağırır.
  Also use when: aktif projenin GSC verisi mevcut; aynı sorguda ≥2 URL
  ranking ediyor; quick-win / content-decay ile birlikte triage; F-08
  invariant kontrolünden sonra cannibalization sheet doldurulacak.
  Do not use when: tek sayfanın decay analizi (content-decay), pozisyon
  11-20 fırsat taraması (quick-wins), tech audit (tech-audit), yeni
  içerik planı (new-content-plan) — ayrı discovery skill'leri. Master.xlsx
  yokken çağırma; init-project önce çalışmalı (DURUR #6).
version: "1.0"
status: active
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
  days_back:
    type: integer
    required: false
    default: 28
    description: "GSC date window end=today, start=today-N."
  min_impressions:
    type: integer
    required: false
    default: 10
    description: "K threshold per page; pages below K are dropped before grouping."
  default_status:
    type: string
    required: false
    default: "TODO"
    description: "statusEnum seed value for new conflict rows."
outputs:
  - "master.xlsx#cannibalization"
  - "outputs/reports/{date}-cannibalization.md"
  - "events.jsonl"
  - "inbox/gsc/{date}-search_analytics-cannibalization-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "gsc-pull:master.xlsx#gsc_performance"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-cannibalization"]
  natural_language: |
    "cannibalization", "kannibalizasyon", "keyword conflict", "URL
    çakışması", "aynı keyword'e iki sayfa", "anahtar kelime çakışması",
    "iki sayfam aynı sorguya çıkıyor", "intent split"
  hooks: []
  scheduled:
    - cron: "0 9 * * 2"
      mode: "report-only"
mcp_tools:
  required:
    - "mcp__gsc__search_analytics"
  optional:
    - "mcp__gsc__enhanced_search_analytics"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# cannibalization — discovery skill (Phase 7 Wave 1)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline. Raw JSON drift recovery is mandatory:
the MCP response is dropped into `inbox/gsc/` *before* any transform
runs, so a transform bug never costs us the upstream payload.

This skill follows the **convention authority** established by
`skills/discovery/quick-wins/SKILL.md` (Phase 5) and
`skills/ingestion/gsc-pull/SKILL.md` (Phase 6). The 10-step protocol
shape, raw JSON inbox discipline, URL normalization (D-03), DURUR + flag
rule, and provenance event format are reused verbatim — only the domain
content (target sheet, transform script, conflict heuristic) changes.
Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name              | Type    | Default | Notes                                                  |
|-------------------|---------|---------|--------------------------------------------------------|
| `project_slug`    | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.       |
| `days_back`       | integer | 28      | GSC date window end=today, start=today-N.               |
| `min_impressions` | integer | 10      | K threshold per page; below-K pages dropped before grouping. |
| `default_status`  | string  | "TODO"  | statusEnum seed for new rows (master-excel.schema definitions). |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#cannibalization` — one row per query
  conflict (7 cols, schema-locked).
- `projects/{slug}/outputs/reports/{date}-cannibalization.md` —
  human-readable summary (top conflicts, primary URLs, resolution mix).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=gsc_mcp`, `target_excel_sheet=cannibalization`).
- `projects/{slug}/inbox/gsc/{date}-search_analytics-cannibalization-{slug}.json`
  — raw MCP payload (drift recovery).

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021, ADR-019).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="cannibalization",
    project_slug=project_slug,
    steps=[
        {"name": "fetch_search_analytics"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `fetch_search_analytics` (MCP §16.5 step 3 — raw inbox first)

Pull `query` × `page` rows over the recent window so groups can form.

```python
workflow_runner.start_step(handle.run_id, 0,
                           project_slug=project_slug)
raw = mcp__gsc__search_analytics(
    siteUrl=project_config["gsc"]["site_url"],
    startDate=(today - days_back).isoformat(),
    endDate=today.isoformat(),
    dimensions=["query", "page"],
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "gsc"
    / f"{today.isoformat()}-search_analytics-cannibalization-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
workflow_runner.finish_step(handle.run_id, 0,
                            project_slug=project_slug,
                            output_ref=str(inbox_path))
```

### Step 3 — `transform`

Pure compute via `scripts/discovery/cannibalization_transform.py`:

```bash
python3 scripts/discovery/cannibalization_transform.py \
    --raw inbox/gsc/{date}-search_analytics-cannibalization-{slug}.json \
    --min-impressions 10 \
    --default-status TODO \
    --output-dir _state/transform/{run_id}/
```

Produces a JSON array (`cannibalization`) shaped to the master-excel
schema (7 columns: conflict_pair, overlapping_queries_est, total_impact,
resolution, note, status, priority). URL normalization (D-03) is applied
here, not at fetch time, so the raw inbox copy is byte-faithful to the
MCP response. The transform is idempotent: same input → byte-identical
output.

If `meta.conflict_count == 0`, the skill SKIPS write_excel and emits a
"no cannibalization detected" notice (DURUR #7 — clean exit, not error).

### Step 4 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(rows)} cannibalization conflict bulundu, master.xlsx#cannibalization'a yazalım mı?",
    step_index=2,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 5 — Resume (`approve` → continue)

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug,
                        approver="user")
```

### Step 6 — `write_excel` (atomic, schema-validated)

Single `committer.commit` call for the cannibalization sheet — the
orchestrator's idempotent commit path (whole-block `transaction.replace`
from the schema's `data_start_row`, so re-running never duplicates rows on
the `cannibalization` snapshot sheet). Goes through the single approved write
path with backup, lock, schema validation, and post-write provenance event
emission.

```python
from scripts.orchestration import committer
committer.commit(
    workspace_root/"projects"/project_slug/"master.xlsx",
    "cannibalization",
    cannibalization_rows,
    run_id=handle.run_id,
    project_slug=project_slug,
    writer="cannibalization",
)
```

### Step 7 — `render_report`

`render_template.py templates/reports/cannibalization.template.md
data.json` → `outputs/reports/{date}-cannibalization.md`. Variables:
`$project_slug`, `$date`, `$days_back`, `$conflict_count`,
`$top_conflict_pair`, `$top_total_impact`, `$top_resolution`,
`$report_summary`.

### Step 8 — Provenance event

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "gsc_mcp", "mcp_server": "gsc",
            "mcp_tool": "gsc__search_analytics",
            "response_bytes": len(json.dumps(raw))},
    operation="project_excel",
    target_excel_sheet="cannibalization",
    rows_written=len(cannibalization_rows),
)
```

### Step 9 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED
    "conflict_count": str(len(cannibalization_rows)),
    "report_path": str(report_path),
    "raw_json": str(inbox_path),
})
```

### Step 10 — Done

Workflow status flips `running → done` (workflow-run schema) and a
`workflow_action=done` event lands in `events.jsonl` (ADR-020).

## URL normalization (D-03 invariant)

Every URL passing through this skill is normalized via
`scripts.discovery.cannibalization_transform.normalize_url`. The function
is **idempotent**: `normalize_url(normalize_url(u)) == normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports, strip
trailing slash (root excluded), drop fragment, drop tracking params,
sort remaining query keys.

The transform self-checks idempotency on every emitted URL — a drift
between transform and downstream consumers is escalated as DURUR rather
than silently masked.

## Cannibalization detection logic (I2 contract)

A query with ≥2 distinct URLs above K is only a **candidate**; it becomes a
**conflict** only when **ALL THREE** signals hold (so single-keyword
volatility and brand SERPs are not mislabelled as cannibalization):

```
1. Parse rows: each entry contributes (query_lower, url_normalized,
   clicks, impressions, position).
2. Drop rows with impressions < min_impressions (default 10).
3. Group by query_lower; collapse same (query, url) pairs by summing;
   position is impression-weighted.
4. Candidate = query with ≥2 distinct URLs after the K filter.
5. Candidate → CONFLICT only when ALL hold:
     (a) NON-BRAND query — brand tokens (from project.config brand/domain,
         passed as --brand-token / brand_tokens) exclude brand-dominated
         queries.
     (b) CLICK-SHARE DILUTION — no single URL holds > 70% of the query's
         clicks (a query with zero clicks has no traffic to dilute → not a
         conflict).
     (c) COMPETITION SIGNAL — top-URL flip-flop between the two most recent
         windows (needs the optional --previous window) OR ≥2 URLs
         simultaneously in positions 1-20 with spread ≤ 5.
6. For each conflict emit one row:
     conflict_pair             "{query} :: {url1} | {url2} | ..."  (sorted)
     overlapping_queries_est   #conflict queries with the same URL set
     total_impact              "{sum_clicks} clicks"
     resolution                ALWAYS "differentiate intent / adjust
                               internal-link hierarchy" (default)
     note                      "primary URL: {top}; signal: {...};
                               consolidate (301) only if intent overlap
                               confirmed — operator review"
     status                    statusEnum (default "TODO")
     priority                  P1 (>=100) / P2 (>=20) / P3 otherwise
7. Sort rows by total_impact desc, then by conflict_pair for determinism.
   meta records brand_excluded / share_excluded / signal_excluded so a
   non-empty input that yields zero conflicts is explainable.
```

### Resolution policy (no auto-consolidate)

The default recommendation is **"differentiate intent / adjust internal-link
hierarchy"**. A **301-consolidate is NEVER auto-recommended** — duplicate
intent must be explicitly confirmed by a human, and consolidation is ALWAYS
operator-reviewed (the note carries this caveat). This replaces the old
position-spread heuristic ("consolidate to top URL" / "intent split
investigation" / "topical merge candidate"), which over-flagged
consolidation off rank spread alone.

### F-15 stays AMBER-by-design

A non-empty `cannibalization` sheet correctly drives the F-15 drift check to
**AMBER** (not GREEN, not RED) — cannibalization conflicts are
production-ready findings that require operator triage, so AMBER is the
intended terminal state. Do NOT delete rows or force GREEN to clear F-15
(see `feedback_f15_amber_terminal`).

Optional CLI flags wiring the new signals (Step 3 transform):
`--previous inbox/gsc/{prior-date}-search_analytics-cannibalization-{slug}.json`
(top-URL flip-flop) and `--brand-token <token>` (repeatable; from
project.config brand/domain — engine stays agnostic).

## DURUR conditions (8)

Stop and flag the manager — do not patch, do not fall back.

1. `mcp__gsc__search_analytics` returns auth/network/scope error or an
   empty/malformed payload. STOP, do not write to master.xlsx.
2. Raw JSON inbox path cannot be created (workspace path missing or
   non-writable, e.g. `PSEO_WORKSPACE_ROOT` misconfigured). STOP,
   request manager check.
3. `master.xlsx#cannibalization` column count or names don't match
   schema (`schemas/master-excel.schema.json#cannibalization`). STOP,
   schema-first violation.
4. `transaction.append` raises `RowSchemaError` (e.g.,
   `overlapping_queries_est` not int, `status` not in statusEnum). STOP.
5. `workflow_runner.create_run` fails schema validation
   (`schemas/workflow-run.schema.json`). STOP.
6. `PSEO_WORKSPACE_ROOT` env var unset and no explicit `workspace_root`
   arg passed to `workflow_runner` / `events_writer`. STOP, surface to
   manager.
7. Transform reports `meta.conflict_count == 0` (no candidate query
   survived the (a)/(b)/(c) predicate — either none had ≥2 URLs above K,
   or all were brand/share/signal-excluded; see meta.*_excluded). NOT an
   error — clean exit with a "no cannibalization detected" notice; skill
   skips write_excel + render_report and goes straight to `complete` with
   `conflict_count="0"`.
8. URL normalization output drifts (idempotency check fails inside
   `cannibalization_transform.transform`). STOP, D-03 invariant broken.

## Cross-references

- Schemas: `schemas/master-excel.schema.json`
  (cannibalization sheet, 7 required_columns + `#/definitions/statusEnum`),
  `schemas/events.schema.json` (`source.kind=gsc_mcp`,
  `target_excel_sheet=cannibalization`),
  `schemas/gsc-tool-mapping.schema.json` (D-03 invariant),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`.
- Transform: `scripts/discovery/cannibalization_transform.py`.
- Tests: `tests/skills/test_cannibalization.py` (≥6 cases incl. smoke).
- Template: `templates/reports/cannibalization.template.md`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade
      (exception: DURUR #7 is a clean no-op exit, not a fallback).
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` are imported, never modified
      from this skill. Transform has 0 imports from
      `scripts.excel.transaction`.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] Append-only state — `events.jsonl` only grows; no in-place rewrite.
