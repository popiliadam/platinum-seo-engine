---
name: dfs-pull
description: |
  Use when: kullanıcı "dataforseo keyword volume al", "TR keyword araştırması",
  "dfs keyword overview", "Türkiye için keyword volume çek", "yeni keyword
  setine volume bak" der ya da /pseo-dfs-pull çağırır. Master.xlsx'in
  cluster_keywords + opportunity sheet'lerine atomic write yapar; raw DFS
  JSON'larını inbox/dfs/ altına persist eder.
  Also use when: aktif projenin keyword listesi config'te tanımlı; TR
  (location_code=2792, language_code='tr') varsayılan; budget pre-flight
  PASS; dataforseo-mcp-server@2.8.9 wrapper TR forwarding bug için A/B/C
  workaround stratejisi uygulanacak.
  Do not use when: GSC veri ingestion (gsc-pull), SF csv ingestion
  (sf-import), Scrapling competitor crawl (scrapling-ops) gerekiyor —
  ayrı ingestion skill'leri. Master.xlsx yokken çağırma; init-project
  önce çalışmalı (DURUR #6). Budget aşılmışsa fallback YASAK (DURUR #2).
version: "1.0"
status: wip
category: ingestion
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project-config.json."
  keywords:
    type: array
    required: true
    description: "Liste of seed keywords (string array). DFS overview + Google Ads volume çağrısı bunlar üstünde yapılır."
  location_code:
    type: integer
    required: false
    default: 2792
    description: "DFS location_code; varsayılan 2792 = Turkey."
  language_code:
    type: string
    required: false
    default: "tr"
    description: "DFS language_code; varsayılan 'tr' = Turkish."
  cluster:
    type: string
    required: false
    default: "uncategorized"
    description: "cluster_keywords sheet'inde A sütununa yazılacak cluster ismi."
outputs:
  - "master.xlsx#cluster_keywords"
  - "master.xlsx#opportunity"
  - "outputs/reports/{date}-dfs-pull.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-keyword_overview-{slug}.json"
  - "inbox/dfs/{date}-search_volume-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
produces:
  - "quick-wins"
  - "drift-check"
triggers:
  manual: ["/pseo-dfs-pull"]
  natural_language: |
    "dataforseo keyword volume", "TR keyword araştırması", "dfs keyword overview",
    "Türkiye keyword volume", "yeni keyword setine volume bak"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__keywords_data_google_ads_search_volume"
    - "mcp__dataforseo__dataforseo_labs_google_keyword_overview"
  optional:
    - "mcp__dataforseo__dataforseo_labs_google_historical_keyword_data"
budget:
  uses_paid_mcp: true
  estimated_credits: 1.5
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# dfs-pull — ingestion skill (Phase 6 Wave 1, paid-MCP authority)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight. Raw JSON
drift recovery is mandatory: every DFS response is dropped into
`inbox/dfs/` *before* any transform runs, so a transform bug never
costs us the upstream payload (which is paid; re-fetch costs credits).

This skill is the **convention authority** for the 6 paid-MCP ingestion
skills planned in Phase 6-12 (dfs-pull, dfs-rank-tracking, dfs-serp-pull,
dfs-backlinks-pull, dfs-content-analysis, scrapling-ops-paid). Reuse
the 10-step shape verbatim and the budget pre-flight integration; only
the TR forwarding workaround block is DFS-specific.

## Inputs (frontmatter contract)

| Name             | Type    | Default          | Notes                                                  |
|------------------|---------|------------------|--------------------------------------------------------|
| `project_slug`   | string  | —                | Required. Resolves `projects/{slug}/master.xlsx`.       |
| `keywords`       | array   | —                | Required. Seed keyword list; transforms drive credits.  |
| `location_code`  | integer | 2792             | DFS Turkey. Workaround gates the response server-side.  |
| `language_code`  | string  | "tr"             | DFS Turkish.                                            |
| `cluster`        | string  | "uncategorized"  | cluster_keywords col A.                                 |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#cluster_keywords` — per-keyword volume rows (11 cols, schema-locked).
- `projects/{slug}/master.xlsx#opportunity` — APPEND only (F-09 shared writer with quick-wins; do NOT overwrite quick-wins rows).
- `projects/{slug}/outputs/reports/{date}-dfs-pull.md` — human-readable summary.
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance` entries (`source.kind=dataforseo_mcp`).
- `projects/{slug}/inbox/dfs/{date}-keyword_overview-{slug}.json` — raw labs payload (drift recovery).
- `projects/{slug}/inbox/dfs/{date}-search_volume-{slug}.json` — raw Google Ads payload.

## Drift note (read first)

The Phase 6 worker brief refers to `master.xlsx#keyword_data`. The
canonical `schemas/master-excel.schema.json` does NOT define a
`keyword_data` sheet — `keyword_data` is a DataForSEO endpoint
*category* in `dataforseo-endpoint-mapping.schema.json` (alongside
labs, serp_live, etc.), not an Excel sheet. The closest schema-locked
sheet for per-keyword volume rows is `cluster_keywords` (11 cols, A=
cluster..K=forbidden_reason). This skill writes to `cluster_keywords`
and appends to `opportunity`. **Manager: confirm before commit**, or
issue an ADR adding a `keyword_data` sheet.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="dfs-pull",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "fetch_overview"},
        {"name": "tr_workaround"},
        {"name": "fetch_volume"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `preflight_budget` (§16.8, FIRST paid-MCP skill)

Computes `estimated_credits = len(keywords) * (1.0 + 0.5)` (overview +
volume) and runs `scripts.budget.check_budget` against the project's
24h running total. DURUR #5 if exceeded — never silently downgrade.

```python
from scripts.ingestion import dfs_pull
workflow_runner.start_step(handle.run_id, 0, project_slug=project_slug)
estimate = dfs_pull.estimate_credits(len(keywords))
budget_envelope = dfs_pull.preflight_budget(
    estimated_credits=estimate,
    project_config_path=project_root / "project-config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
workflow_runner.finish_step(handle.run_id, 0, project_slug=project_slug,
                            output_ref=str(budget_envelope))
```

### Step 3 — `fetch_overview` (MCP §16.5 step 3 — raw inbox first)

```python
workflow_runner.start_step(handle.run_id, 1, project_slug=project_slug)
raw_overview = mcp__dataforseo__dataforseo_labs_google_keyword_overview(
    keywords=keywords,
    location_code=location_code,    # 2792 = Turkey
    language_code=language_code,    # "tr"
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-keyword_overview-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw_overview, ensure_ascii=False, indent=2))
workflow_runner.finish_step(handle.run_id, 1, project_slug=project_slug,
                            output_ref=str(inbox_path))
```

### Step 4 — `tr_workaround` (validates / re-fetches TR-correct data)

See **TR Forwarding Workaround** section below. Three methods (A, B, C)
attempted in sequence; first to PASS wins. All fail → DURUR #4. The
chosen method is recorded in `_state/transform/{run_id}/tr_method.json`.

### Step 5 — `fetch_volume` (optional alt-endpoint enrichment)

Google Ads `keywords_data_google_ads_search_volume` is workaround B's
primary endpoint AND an enrichment source even when overview fetched
TR-correct data. Persist to inbox/dfs/{date}-search_volume-{slug}.json.

```python
raw_volume = mcp__dataforseo__keywords_data_google_ads_search_volume(
    keywords=keywords,
    location_code=location_code,
    language_code=language_code,
)
volume_inbox = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-search_volume-{project_slug}.json"
)
volume_inbox.write_text(json.dumps(raw_volume, ensure_ascii=False, indent=2))
```

### Step 6 — `transform`

Pure compute via `scripts/ingestion/dfs_pull.py`:

```bash
python3 scripts/ingestion/dfs_pull.py \
    --raw-overview inbox/dfs/{date}-keyword_overview-{slug}.json \
    --raw-volume   inbox/dfs/{date}-search_volume-{slug}.json \
    --location-code 2792 \
    --language-code tr \
    --output-dir _state/transform/{run_id}/
```

Produces two JSON arrays (`cluster_keywords`, `opportunity`) shaped to
the master-excel schema. Volume from `keywords_data_google_ads_*` (when
present) overrides keyword_overview's keyword_info.search_volume — this
is the workaround B "alt endpoint trust" rule.

### Step 7 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(keywords)} keyword için DFS volume çekildi, master.xlsx'e yazalım mı?",
    step_index=5,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 8 — `write_excel` (atomic, schema-validated)

Two `transaction.append` calls — one per sheet. Both go through the
single approved write path with backup, lock, schema validation, and
post-write provenance event emission. **F-09 invariant**: opportunity
is shared with quick-wins; APPEND only, never overwrite.

```python
from scripts.excel import transaction
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="cluster_keywords",
    rows=cluster_keywords_rows,
    project_slug=project_slug,
    writer="dfs-pull",
)
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="opportunity",
    rows=opportunity_rows,
    project_slug=project_slug,
    writer="dfs-pull",
)
```

### Step 9 — Provenance event + report

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_overview",
            "response_bytes": len(json.dumps(raw_overview))},
    operation="project_excel",
    target_excel_sheet="cluster_keywords",
    rows_written=len(cluster_keywords_rows),
    cost={"provider": "dataforseo",
          "credits": float(estimate),
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
```

`render_template.py templates/reports/dfs-pull.template.md data.json`
→ `outputs/reports/{date}-dfs-pull.md`. Variables: `$project_slug`,
`$date`, `$keyword_count`, `$location_code`, `$language_code`,
`$tr_method`, `$credits_used`, `$top_keyword`.

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "cluster_keywords_rows": str(len(cluster_keywords_rows)),
    "opportunity_rows":      str(len(opportunity_rows)),
    "tr_method":             tr_method,           # "B" / "C" / "A+B" ...
    "credits_used":          str(estimate),
    "report_path":           str(report_path),
    "raw_jsons":             ";".join([str(inbox_path), str(volume_inbox)]),
})
```

## TR Forwarding Workaround (REQUIRED — paid-MCP correctness gate)

**Background.** Live test 1835229 confirmed: dataforseo-mcp-server@2.8.9
returns `location_code=2840` (US) and `language_code="en"` even when the
caller passes `location_code=2792 / language_code="tr"`. The wrapper's
`dataforseo_labs_google_keyword_overview` code path silently drops the
locale params before issuing the upstream REST call. **Never trust the
echoed request — always inspect the served `result[0].location_code`.**

**Strategy.** Three independent methods, attempted in order. First to
PASS wins; all fail → `TrWorkaroundFailed` DURUR #4 (we refuse to
silently emit US data into a TR project sheet — that is the false-
success failure mode the brief explicitly forbids).

### Method A — heuristic post-fetch filter (cheap, partial coverage)

Pure function; always runs as a sanity gate. Reads the served
`location_code/language_code` from the response envelope and drops
rows whose serp_info top-3 results are *all* non-`.tr` TLDs. Use:

```python
from scripts.ingestion import dfs_pull
# Detect served locale.
loc, lang = dfs_pull.detect_response_locale(raw_overview)
honors = dfs_pull.response_honors_tr(raw_overview,
                                     expected_location=2792,
                                     expected_language="tr")
if not honors:
    # A's filter is unreliable on its own when locale is wrong (the
    # whole payload is US); proceed to B.
    pass
```

**Failure mode.** False negatives on global-brand TR queries (e.g. a
.com domain ranking in Turkey). Document in run note when the filter
drops > 30% of rows.

### Method B — alt endpoint (preferred fast path)

`mcp__dataforseo__keywords_data_google_ads_search_volume` lives in a
different wrapper code path (keywords_data, not labs) and DOES forward
location_code/language_code in 2.8.9 (verified by re-running the same
request shape and inspecting served locale; the keywords_data path
wraps the upstream Google Ads SOAP-style endpoint which mandates
loc+lang as required body fields, so the wrapper cannot drop them).

When B's response honors TR, treat its `search_volume` as the
authoritative value and merge into the overview rows by lowercase
keyword. The transform's `--raw-volume` argument enables this:

```python
result = dfs_pull.transform(
    raw_overview,
    raw_volume=raw_volume,        # honored TR data
    location_code=2792,
    language_code="tr",
    skip_tr_check=True,           # B has signed off; skip overview check
)
```

**Failure mode.** Google Ads search_volume is monthly average over the
last 12 months and rounds to bucketed values (10, 50, 100, 500, …);
labs/keyword_overview returns finer integers. Treat the volume column
as bucket-precision when B is the source.

### Method C — direct HTTP API (wrapper bypass, last resort)

POST to `https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_overview/live`
with HTTPBasicAuth from `DATAFORSEO_USERNAME` / `DATAFORSEO_PASSWORD`
env vars (loaded via `.mcp.json` bash wrapper at MCP runtime; the
skill reads them from env directly here, NOT from a file). Body shape:

```python
import requests
from requests.auth import HTTPBasicAuth
from scripts.ingestion import dfs_pull

user, pwd = dfs_pull.http_credentials_from_env()        # CredentialError if missing
body = dfs_pull.build_http_payload_tr(
    keywords=keywords,
    location_code=2792,
    language_code="tr",
)
resp = requests.post(
    "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_overview/live",
    auth=HTTPBasicAuth(user, pwd),
    json=body,
    timeout=30,
)
resp.raise_for_status()
raw_overview = resp.json()
assert dfs_pull.response_honors_tr(raw_overview, expected_location=2792)
```

**Failure mode.** Doubles credit cost (one billable call to the wrapper
at step 3 + one to HTTP here). Use only when B is unavailable. Surface
the duplicate-spend in the provenance event's `cost.notes`.

### Decision matrix

| A honors TR | B honors TR | C honors TR | Action                          | tr_method |
|-------------|-------------|-------------|----------------------------------|-----------|
| yes         | n/a         | n/a         | use overview as-is               | A         |
| no          | yes         | n/a         | use overview rows + B's volumes  | A+B       |
| no          | no          | yes         | replace overview with HTTP fetch | C         |
| no          | no          | no          | DURUR #4 (TrWorkaroundFailed)    | —         |

## Opportunity score (DFS-derived)

```
score = monthly_volume × competition_factor

competition_factor:  LOW=1.0, MEDIUM=0.6, HIGH=0.3
```

Coarse but deterministic. Lacking real GSC position (DFS is a forward-
looking signal, not a current-rank signal), this proxy ranks by
volume-weighted competition headroom. Quick-wins later overrides with
GSC-derived `impressions × headroom` once the URL is assigned.

## DURUR conditions (8)

Stop and flag the manager — do not patch, do not fall back.

1. `mcp__dataforseo__dataforseo_labs_google_keyword_overview` returns
   auth/network/scope error.
2. Budget pre-flight `BudgetError`: estimated credits would push 24h
   usage past `project.config.dataforseo.budget_credits_per_day`.
3. `inbox/dfs/` path cannot be created (workspace path missing).
4. **TR forwarding workaround all-method fail**: A, B, AND C return
   non-TR locale → `TrWorkaroundFailed`. DO NOT silently emit US data.
5. `master.xlsx#cluster_keywords` column count or names don't match
   schema (drift recovery flag — also possible if manager added
   `keyword_data` sheet without ADR).
6. `transaction.append` raises `RowSchemaError`.
7. `master.xlsx` missing under `projects/{slug}/` — `init-project`
   must have run first.
8. `DATAFORSEO_USERNAME` / `DATAFORSEO_PASSWORD` env unset when method
   C is the only remaining option (`CredentialError`).

## Cross-references

- Schemas: `schemas/master-excel.schema.json` (cluster_keywords,
  opportunity, definitions), `schemas/dataforseo-endpoint-mapping.schema.json`
  (DFS contract; cost.credits_per_call), `schemas/events.schema.json`
  (`source.kind=dataforseo_mcp`), `schemas/skill-frontmatter.schema.json`
  (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/budget/check_budget.py`.
- Transform: `scripts/ingestion/dfs_pull.py`.
- Tests: `tests/skills/test_dfs_pull.py` (7 cases incl. TR workaround +
  budget pre-flight integration).
- F-09 invariant: opportunity is shared between quick-wins and dfs-pull;
  both APPEND, never overwrite. Provenance event distinguishes by
  `source.kind=gsc_mcp` (quick-wins) vs `dataforseo_mcp` (dfs-pull).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] Budget pre-flight integration — `scripts.budget.check_budget`
      invoked at step 2 BEFORE any paid call.
- [x] Append-only — all events via `events_writer`; opportunity is
      append-only per F-09; no row deletion in `cluster_keywords`.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` / `check_budget` are imported,
      never modified from this skill.
- [x] No hardcoded credentials — `DATAFORSEO_USERNAME` /
      `DATAFORSEO_PASSWORD` resolved from env at runtime.
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
