---
name: dfs-pull
description: |
  Use when: kullanıcı "dataforseo keyword volume al", "TR keyword araştırması",
  "dfs keyword overview", "Türkiye için keyword volume çek", "yeni keyword
  setine volume bak" der ya da /pseo-dfs-pull çağırır. Raw DFS JSON'larını
  inbox/dfs/ altına persist eder ve `_state/staging/` altına shape-adapted
  staging table yazar (Phase 8 `cluster-map` skill konsume eder, Excel
  projection downstream).
  Also use when: aktif projenin keyword listesi config'te tanımlı;
  location_code/language_code project.config.dataforseo'dan config-first
  çözülür (engine-level ülke varsayılanı YOK); budget pre-flight PASS;
  TR projelerinde dataforseo-mcp-server@2.8.9 wrapper TR forwarding bug
  için A/B/C workaround stratejisi uygulanacak.
  Do not use when: GSC veri ingestion (gsc-pull), SF csv ingestion
  (sf-import), Scrapling competitor crawl (scrapling-ops) gerekiyor —
  ayrı ingestion skill'leri. Master.xlsx yokken çağırma; init-project
  önce çalışmalı (DURUR #6). Budget aşılmışsa fallback YASAK (DURUR #2).
version: "1.0"
status: active
category: ingestion
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
  keywords:
    type: array
    required: true
    description: "Liste of seed keywords (string array). DFS overview + Google Ads volume çağrısı bunlar üstünde yapılır."
  location_code:
    type: integer
    required: false
    description: "DFS location_code. NO engine default — resolved config-first from project.config.dataforseo.location_code. Explicit value overrides config. See '## Locale resolution'."
  language_code:
    type: string
    required: false
    description: "DFS language_code. NO engine default — resolved config-first from project.config.dataforseo.language_code (derived from language.content_locale at init). See '## Locale resolution'."
outputs:
  - "_state/staging/dfs_keyword_overview_{date}_{slug}.json"
  - "_state/staging/dfs_search_volume_{date}_{slug}.json"
  - "outputs/reports/{date}-dfs-pull.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-keyword_overview-{slug}.json"
  - "inbox/dfs/{date}-search_volume-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
produces:
  - "cluster-map"
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
| `location_code`  | integer | *(config)*       | Config-first from `project.config.dataforseo.location_code`; no engine default. See **Locale resolution**. |
| `language_code`  | string  | *(config)*       | Config-first from `project.config.dataforseo.language_code`. See **Locale resolution**.                    |

> **Removed input — `cluster`:** dfs-pull is staging-only (D-003); it never
> writes `cluster_keywords`. Cluster assignment is the Phase 8 `cluster-map`
> skill's job, which consumes the staging JSON. The old `cluster` input
> promised a sheet write the body explicitly forbids, so it was dropped.

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Locale resolution (config-first — NO engine-level country default)

`location_code` / `language_code` are resolved **config-first** from the
project's own `project.config.dataforseo` block — schema-required fields
(`schemas/project-config.schema.json`). There is **no engine-level country
default**: the engine is project-agnostic and must never assume Turkey (or
any country). Resolution order:

1. Explicit `location_code` / `language_code` input (operator override).
2. `project.config.dataforseo.location_code` + `project.config.dataforseo.language_code`.
3. Neither available → **DURUR #9** (config locale unresolvable). The skill
   STOPS before any paid MCP call; it never falls back to a country.

`language_code` is the DFS short code (`tr`, `en`), set in the config at
init from `language.content_locale` (e.g. `tr-TR`→`tr`, `en-CA`→`en`).

### Per-market reference (codes VERIFIED from live project configs)

| `market` | `content_locale` | `location_code` | `language_code` | Note |
|----------|------------------|-----------------|-----------------|------|
| TR       | tr-TR            | 2792            | tr              | Turkey (country). |
| CA       | en-CA            | 20120           | en              | "Ontario,Canada" — a **sub-country** location; a coarse country code would be wrong. |
| NG       | en-NG            | 2566            | en              | Nigeria (country). |

These are the markets currently in the portfolio; every code above is read
straight from that project's `project.config.dataforseo` (the authoritative
source — not hardcoded here). For a NEW market, resolve the DFS
`location_code` at init via a `serp_locations` lookup and persist it into
`project.config.dataforseo` — never guess a country code in skill logic.

> **TR-only workaround scope.** The **TR Forwarding Workaround** below
> applies ONLY when the resolved location is TR (2792); CA/NG/other markets
> skip it — the dataforseo-mcp-server@2.8.9 forwarding bug is TR-specific.
> The Method-C `detect_response_locale` verification stays mandatory for TR
> projects (do not remove it).

## Outputs (artifacts produced)

- `projects/{slug}/_state/staging/dfs_keyword_overview_{date}_{slug}.json` — per-keyword volume staging table (schema-versioned, sha256 content_hash per row, ISO 8601 microsecond `fetched_at`). Columns from `dfs_pull.KEYWORD_OVERVIEW_COLUMNS`.
- `projects/{slug}/_state/staging/dfs_search_volume_{date}_{slug}.json` — Google Ads volume staging table (idempotent overwrite). Columns from `dfs_pull.SEARCH_VOLUME_COLUMNS`.
- `projects/{slug}/outputs/reports/{date}-dfs-pull.md` — human-readable summary.
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance` entries (`source.kind=dataforseo_mcp`, `target_excel_sheet=null` — staging-only).
- `projects/{slug}/inbox/dfs/{date}-keyword_overview-{slug}.json` — raw labs payload (drift recovery).
- `projects/{slug}/inbox/dfs/{date}-search_volume-{slug}.json` — raw Google Ads payload.

> **Note:** dfs-pull does NOT write to `master.xlsx`. Phase 8 `cluster-map` skill consumes the staging tables and projects to `master.xlsx#cluster_keywords` + `opportunity` downstream (F-09 shared writer disiplini orada uygulanır).

## Drift note (D-003 RESOLVED via staging-only routing)

The Phase 6 worker brief originally referred to `master.xlsx#keyword_data`,
which is not a sheet in `schemas/master-excel.schema.json` (it's a DFS
endpoint *category* in `dataforseo-endpoint-mapping.schema.json`). The
intermediate fix wrote to `cluster_keywords` + `opportunity`, but the
**final D-003 resolution** routes dfs-pull output to staging JSON only:
no Excel write from this skill. Phase 8 `cluster-map` skill consumes the
staging tables and produces the Excel-shaped rows (cluster_keywords +
opportunity) under its own F-09 shared-writer discipline. This pattern
mirrors `scrapling-ops` (Phase 6 staging-only generic helper).

**Shape adapter (`_normalize_dfs_response`):** runtime tolerates two DFS
response shapes — REST envelope `tasks[0].result[0].items` AND wrapper-
flattened `items` — so dataforseo-mcp-server version drift does not
break ingestion silently.

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
        {"name": "write_staging"},
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
    project_config_path=project_root / "project.config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
workflow_runner.finish_step(handle.run_id, 0, project_slug=project_slug,
                            output_ref=str(budget_envelope))
```

### Step 3 — `fetch_overview` (MCP §16.5 step 3 — raw inbox first)

```python
workflow_runner.start_step(handle.run_id, 1, project_slug=project_slug)
# location_code / language_code resolved config-first (see "Locale
# resolution") — no engine-level country default.
raw_overview = mcp__dataforseo__dataforseo_labs_google_keyword_overview(
    keywords=keywords,
    location_code=location_code,    # from project.config.dataforseo
    language_code=language_code,    # from project.config.dataforseo
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

Pure compute via `scripts/ingestion/dfs_pull.py` (staging-only output).
The transform calls `_normalize_dfs_response()` first to flatten REST
or wrapper shapes uniformly, then builds two staging payloads:

```bash
python3 scripts/ingestion/dfs_pull.py \
    --raw-overview  inbox/dfs/{date}-keyword_overview-{slug}.json \
    --raw-volume    inbox/dfs/{date}-search_volume-{slug}.json \
    --location-code {location_code} \
    --language-code {language_code} \
    --staging-dir   _state/staging/ \
    --project-slug  {project_slug}
```

Produces two staging JSON files (`dfs_keyword_overview_*.json` and
`dfs_search_volume_*.json`) — each with `schema_version`, `tool`,
`fetched_at` (ISO 8601 µs UTC), `row_count`, `columns`, `rows[]` (1-
indexed `id` + sha256 `content_hash`). Volume from
`keywords_data_google_ads_*` (when present) overrides keyword_overview's
keyword_info.search_volume — workaround B "alt endpoint trust" rule
applies inside the row builders.

### Step 7 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(keywords)} keyword için DFS volume çekildi, _state/staging/'e yazalım mı?",
    step_index=5,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 8 — `write_staging` (atomic, schema-validated)

One `dfs_pull.write_staging()` call persists both DFS tools in a single
pass from the `transform()` `result` dict. Each non-`None` tool is
written to its own self-contained staging JSON (overwrite-idempotent)
under the `staging_dir`, named `dfs_{tool}_{date}_{slug}.json` (the
function calls `dfs_pull.staging_filename(tool=…, date=…, project_slug=…)`
internally). Schema validated by `_validate_staging_payload()` before
write — `StagingSchemaError` on drift. NO `transaction.append` here;
staging-only. The call returns a `{tool: path}` dict; tools whose payload
is `None` are skipped (no key).

```python
from scripts.ingestion import dfs_pull
# `result` is the transform() output:
#   {"keyword_overview": <staging|None>, "search_volume": <staging|None>, "meta": {…}}
staging_paths = dfs_pull.write_staging(
    result,
    staging_dir=workspace_root / "projects" / project_slug / "_state" / "staging",
    project_slug=project_slug,
    date=today.isoformat(),
)
overview_path = staging_paths.get("keyword_overview")
volume_path = staging_paths.get("search_volume")
```

**No F-09 entanglement at this stage** — opportunity-sheet shared-writer
discipline applies in Phase 8 `cluster-map` (which projects staging
rows into `opportunity` alongside quick-wins).

### Step 9 — Provenance event + report

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_overview",
            "response_bytes": len(json.dumps(raw_overview))},
    operation="staging",
    target_excel_sheet=None,    # staging-only; Phase 8 cluster-map projects to Excel
    rows_written=overview_staging_payload["row_count"],
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
    "overview_staging_rows": str(overview_staging_payload["row_count"]),
    "volume_staging_rows":   str(volume_staging_payload["row_count"]),
    "staging_files":         ";".join([str(overview_path), str(volume_path)]),
    "tr_method":             tr_method,           # "B" / "C" / "A+B" ...
    "credits_used":          str(estimate),
    "report_path":           str(report_path),
    "raw_jsons":             ";".join([str(inbox_path), str(volume_inbox)]),
})
```

## TR Forwarding Workaround (REQUIRED — paid-MCP correctness gate)

**Background.** This workaround is **TR-market-specific** (it runs only when
the config-resolved location is TR — `2792`, per the Locale resolution
reference table). Live test 1835229 confirmed: dataforseo-mcp-server@2.8.9
returns `location_code=2840` (US) and `language_code="en"` even when the
caller passes the TR locale (`2792` / `"tr"`). The wrapper's
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
                                     expected_location=location_code,   # TR=2792 (config)
                                     expected_language=language_code)    # TR="tr" (config)
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
    location_code=location_code,  # TR=2792 (config-resolved)
    language_code=language_code,  # TR="tr" (config-resolved)
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
    location_code=location_code,   # TR=2792 (config-resolved)
    language_code=language_code,   # TR="tr" (config-resolved)
)
resp = requests.post(
    "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_overview/live",
    auth=HTTPBasicAuth(user, pwd),
    json=body,
    timeout=30,
)
resp.raise_for_status()
raw_overview = resp.json()
assert dfs_pull.response_honors_tr(raw_overview, expected_location=location_code)
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

## DURUR conditions (9)

Stop and flag the manager — do not patch, do not fall back.

1. `mcp__dataforseo__dataforseo_labs_google_keyword_overview` returns
   auth/network/scope error.
2. Budget pre-flight `BudgetError`: estimated credits would push 24h
   usage past `project.config.dataforseo.budget_credits_per_day`.
3. `inbox/dfs/` path cannot be created (workspace path missing).
4. **TR forwarding workaround all-method fail**: A, B, AND C return
   non-TR locale → `TrWorkaroundFailed`. DO NOT silently emit US data.
5. Staging payload column count/names don't match
   `dfs_pull.KEYWORD_OVERVIEW_COLUMNS` or `SEARCH_VOLUME_COLUMNS`
   (`StagingSchemaError` from `_validate_staging_payload`).
6. `dfs_pull.write_staging` raises `StagingSchemaError` (id drift,
   content_hash drift, or invalid `fetched_at` shape).
7. `_state/staging/` path cannot be created under `projects/{slug}/`
   (workspace path missing or read-only).
8. `DATAFORSEO_USERNAME` / `DATAFORSEO_PASSWORD` env unset when method
   C is the only remaining option (`CredentialError`).
9. **Config locale unresolvable** — `location_code` / `language_code`
   cannot be resolved (no explicit input AND `project.config.dataforseo`
   missing/unreadable). STOP before any paid MCP call; never default to a
   country (the engine is project-agnostic). `project.config` schema
   *requires* these fields, so this fires only on a malformed/legacy
   config — surface it, do not paper over it.

## Cross-references

- Schemas: `schemas/dataforseo-endpoint-mapping.schema.json` (DFS
  contract; cost.credits_per_call), `schemas/events.schema.json`
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=null` for
  staging-only ops), `schemas/skill-frontmatter.schema.json`
  (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/state/events_writer.py`, `scripts/budget/check_budget.py`.
  **Note:** `scripts/excel/transaction.py` is NOT imported (staging-only).
- Transform: `scripts/ingestion/dfs_pull.py` (`_normalize_dfs_response`,
  `transform`, `write_staging`, `staging_filename`,
  `_staging_table_dict`, `_validate_staging_payload`,
  `KEYWORD_OVERVIEW_COLUMNS`, `SEARCH_VOLUME_COLUMNS`).
- Tests: `tests/skills/test_dfs_pull.py` (TR workaround + budget pre-
  flight integration + 3 `_normalize_dfs_response` shape adapter cases).
- Phase 8 `cluster-map` skill consumes `_state/staging/dfs_*.json` and
  applies F-09 shared-writer discipline when projecting to
  `master.xlsx#opportunity` alongside quick-wins.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] Budget pre-flight integration — `scripts.budget.check_budget`
      invoked at step 2 BEFORE any paid call.
- [x] Append-only — all events via `events_writer`; staging JSON is
      overwrite-idempotent (re-run produces stable id/content_hash);
      F-09 opportunity discipline deferred to Phase 8 `cluster-map`.
- [x] Cross-module IMPORT discipline — `workflow_runner` /
      `events_writer` / `check_budget` are imported, never modified
      from this skill. `scripts.excel.transaction` is NOT imported
      (staging-only — D-003 resolution).
- [x] No hardcoded credentials — `DATAFORSEO_USERNAME` /
      `DATAFORSEO_PASSWORD` resolved from env at runtime.
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
