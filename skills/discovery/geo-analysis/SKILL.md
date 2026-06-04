---
name: geo-analysis
description: |
  Use when: kullanıcı "geo analysis", "GEO", "AEO", "answer engine
  optimization", "generative engine optimization", "LLM mentions",
  "ChatGPT'de görünüyor muyum", "AI Overviews", "Perplexity citation",
  "AI search visibility", "LLM'lerde markam geçiyor mu" der ya da
  /pseo-geo-analysis çağırır.
  Also use when: aktif projenin keyword listesi config'te tanımlı;
  budget pre-flight PASS; project.config display_name (project_name)
  set; cross-source D-03 normalize hem cited_url hem serp_url üstünde
  uygulanır; LLM visibility (mentions across models) + SERP organic
  baseline cross-ref'lenip AEO_NEEDED/SERP_GAP/AEO_HEALTHY/ABSENT
  etiketi üretilir.
  Do not use when: tek-URL on-page audit (on-page-audit), keyword
  volume çekme (dfs-pull), GSC quick-wins (quick-wins), cannibalization
  analizi (cannibalization), competitor crawl (scrapling-ops) — ayrı
  skill'ler. project.config display_name yokken çağırma (DURUR #10);
  budget aşılmışsa fallback YASAK (DURUR #2).
version: "1.0"
status: active
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
  queries:
    type: array
    required: true
    description: "Liste of queries (string array). DFS llm_mentions_search + serp_organic_live_advanced bunlar üstünde çalışır."
  llm_models:
    type: array
    required: false
    description: "İncelemek için LLM model listesi (örn. ['gpt-4','claude-sonnet-4','gemini-2','llama-3']). Boş → DFS default fan-out."
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
outputs:
  - "_state/staging/geo_analysis_llm_mentions_{date}_{slug}.json"
  - "_state/staging/geo_analysis_serp_organic_{date}_{slug}.json"
  - "_state/staging/geo_analysis_signals_{date}_{slug}.json"
  - "outputs/reports/{date}-geo-analysis.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-llm_mentions_search-{slug}.json"
  - "inbox/dfs/{date}-serp_organic-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "dfs-pull:_state/staging/dfs_keyword_overview_{date}_{slug}.json"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-geo-analysis"]
  natural_language: |
    "geo analysis", "GEO", "AEO", "answer engine optimization",
    "generative engine optimization", "LLM mentions", "AI Overviews",
    "ChatGPT'de görünüyor muyum", "Perplexity citation",
    "AI search visibility", "LLM'lerde markam geçiyor mu"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__ai_optimization_llm_mentions_search"
    - "mcp__dataforseo__serp_organic_live_advanced"
  optional:
    - "mcp__dataforseo__ai_optimization_llm_mentions_aggregated_metrics"
budget:
  uses_paid_mcp: true
  estimated_credits: 60
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# geo-analysis — discovery skill (Phase 7 Wave 2, paid-MCP, staging-only)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight + §11.6 LLM
mentions tooling. Raw JSON drift recovery is mandatory: every DFS
response is dropped into `inbox/dfs/` *before* any transform runs, so a
transform bug never costs us the upstream payload (which is paid;
re-fetch costs credits).

This skill follows the **convention authority** of
`skills/ingestion/dfs-pull/SKILL.md` (Phase 6 — staging-only routing,
`_normalize_dfs_response` shape adapter, paid-MCP budget pre-flight) and
the Wave 1 D-03 cross-source pattern from
`skills/discovery/on-page-audit/SKILL.md` (URL canonicalization on BOTH
sides of the cross-source join). Deviate only with an ADR.

Cross-source semantics: DFS `llm_mentions_search` supplies LLM-answer
visibility (mentions across `gpt-4` / `claude-sonnet-4` / `gemini-*` /
`llama-*` / others); DFS `serp_organic_live_advanced` supplies the
traditional SERP baseline. Each query gets a derived `geo_signal` row
that classifies the AEO/GEO posture into one of four labels:

| Gap            | Condition                                                      | Action heuristic                                |
|----------------|----------------------------------------------------------------|-------------------------------------------------|
| `AEO_NEEDED`   | SERP top-3 present AND brand mentioned in 0 LLMs (or <50%)     | write AEO-formatted answer content (FAQ + schema) |
| `SERP_GAP`     | Brand mentioned in ≥1 LLM AND no SERP top-3 placement          | boost SERP rank — internal links + content depth |
| `AEO_HEALTHY`  | Brand mentioned in ≥50% of queried models AND SERP top-3       | monitor — already cited by LLMs                  |
| `ABSENT`       | Neither LLM mention nor SERP top-3                             | research priority — pillar / cluster gap         |

Output sort order is gap severity (AEO_NEEDED first, AEO_HEALTHY last)
so the operator triages the most actionable gaps in the report.

## Inputs (frontmatter contract)

| Name             | Type    | Default | Notes                                                  |
|------------------|---------|---------|--------------------------------------------------------|
| `project_slug`   | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.       |
| `queries`        | array   | —       | Required. Query list driving the paid LLM-mentions + SERP calls. |
| `llm_models`     | array   | —       | LLM model fan-out; absent → DFS server-side default.    |
| `location_code`  | integer | 2792    | DFS Turkey baseline.                                    |
| `language_code`  | string  | "tr"    | DFS Turkish baseline.                                   |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

`project_name` is resolved from `projects/{slug}/project.config.json`
`display_name` field. The transform raises `ProjectNameMissingError`
(DURUR #10) when this field is empty/missing — `our_brand_mentioned`
substring matching cannot run without it.

## Outputs (artifacts produced — D-003 staging-only)

- `projects/{slug}/_state/staging/geo_analysis_llm_mentions_{date}_{slug}.json`
  — per-mention rows (6 cols: query, model, mention_text, cited_url,
  our_brand_mentioned, our_url_cited).
- `projects/{slug}/_state/staging/geo_analysis_serp_organic_{date}_{slug}.json`
  — per-position rows (4 cols: query, serp_position, serp_url,
  serp_title).
- `projects/{slug}/_state/staging/geo_analysis_signals_{date}_{slug}.json`
  — cross-ref derived rows (7 cols: query, llm_visibility_score,
  our_brand_mentioned_count, our_url_cited_count, serp_top_3_present,
  geo_gap, action).
- `projects/{slug}/outputs/reports/{date}-geo-analysis.md` — human
  summary (top AEO_NEEDED gaps, visibility histogram, action queue).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries with `cost.credits` for each DFS call (`source.kind=
  dataforseo_mcp`, `target_excel_sheet=null` — staging-only).
- `projects/{slug}/inbox/dfs/{date}-llm_mentions_search-{slug}.json`
  — raw LLM mentions payload (drift recovery, paid).
- `projects/{slug}/inbox/dfs/{date}-serp_organic-{slug}.json`
  — raw SERP payload (drift recovery, paid).

> **Note:** geo-analysis does NOT write to `master.xlsx`. The three
> staging tables feed downstream skills (Phase 8+ `cluster-map` for
> opportunity projection; `monthly-report` for AEO trend dashboards).
> This mirrors the dfs-pull staging-only paterni (D-003 resolution).

## D-03 URL canonicalization (cross-source invariant)

Every URL passing through this skill is normalized via
`scripts.discovery.geo_analysis_transform._normalize_url`. The function
is **idempotent**: `_normalize_url(_normalize_url(u)) == _normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports
(:80/:443), strip trailing slash (root excluded), drop fragment, drop
tracking params (utm_*, gclid, fbclid, mc_*, msclkid), sort remaining
query keys.

Canonicalization is applied to BOTH `cited_url` (LLM payload, when
present) AND `serp_url` (SERP payload) before any cross-source check
(`our_url_cited`, `serp_top_3_present`). The rule mirrors
`schemas/cross-sheet-invariants.json#D-03` and the helper logic from
`scripts.discovery.on_page_audit_transform._normalize_url`.

**Empty / scheme-less input tolerance:** unlike on-page-audit (which
raises on empty), geo-analysis returns `""` for missing or scheme-less
URLs because LLM citations sometimes reference a brand name without a
URL. The empty string never matches `our_url_cited` or `serp_top_3_present`,
so the downstream signal is correctly False.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `preflight_budget` (§16.8, MANDATORY for paid MCP)

```
estimate = query_count × (5 + 1)   # llm_mentions + serp_organic per-query
```

Run `scripts.budget.check_budget` against the project's 24h running
total. Exit code 0 → proceed. Exit code 1 → DURUR #2
(`BudgetExceededError`); skill exits `awaiting_approval` and never
silently downgrades.

```python
from scripts.discovery import geo_analysis_transform as ga
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="geo-analysis",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "fetch_llm_mentions"},
        {"name": "fetch_serp_organic"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_staging"},
        {"name": "render_report"},
    ],
)
workflow_runner.start_step(handle.run_id, 0, project_slug=project_slug)
estimate = ga.estimate_credits(len(queries))
envelope = ga.preflight_budget(
    estimated_credits=estimate,
    project_config_path=project_root / "project.config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
workflow_runner.finish_step(handle.run_id, 0, project_slug=project_slug,
                            output_ref=str(envelope))
```

### Step 2 — `fetch_llm_mentions` (MCP §16.5 step 3 — raw inbox FIRST)

```python
raw_llm = mcp__dataforseo__ai_optimization_llm_mentions_search(
    keywords=queries,
    models=llm_models,        # optional fan-out; absent → DFS default
    location_code=location_code,
    language_code=language_code,
)
inbox_llm = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-llm_mentions_search-{project_slug}.json"
)
inbox_llm.parent.mkdir(parents=True, exist_ok=True)
inbox_llm.write_text(json.dumps(raw_llm, ensure_ascii=False, indent=2))
```

### Step 3 — `fetch_serp_organic` (paid baseline, raw inbox FIRST)

```python
raw_serp = mcp__dataforseo__serp_organic_live_advanced(
    keywords=queries,
    location_code=location_code,
    language_code=language_code,
    depth=10,                  # cover top-10 organic positions
)
inbox_serp = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-serp_organic-{project_slug}.json"
)
inbox_serp.write_text(json.dumps(raw_serp, ensure_ascii=False, indent=2))
```

### Step 4 — `transform`

Pure compute via `scripts/discovery/geo_analysis_transform.py`:

```bash
python3 scripts/discovery/geo_analysis_transform.py \
    --raw-llm-mentions inbox/dfs/{date}-llm_mentions_search-{slug}.json \
    --raw-serp         inbox/dfs/{date}-serp_organic-{slug}.json \
    --project-name     "{display_name from project.config}" \
    --project-url-root "{domain from project.config}" \
    --project-slug     {project_slug} \
    --output-dir       _state/transform/{run_id}/
```

Produces three JSON arrays (`llm_mentions`, `serp_organic`,
`geo_signals`). URL canonicalization (D-03) is applied here on BOTH the
LLM `cited_url` and the SERP `serp_url` before any cross-ref, not at
fetch time, so the raw inbox copies are byte-faithful to the upstream
payloads. The transform is idempotent: same inputs → byte-identical
output (modulo `meta.fetched_at`).

The transform calls `_normalize_dfs_response` (IMPORTED from
`scripts.ingestion.dfs_pull` — never copied) on both raw payloads first,
so the dataforseo-mcp-server REST envelope vs flat wrapper drift is
tolerated uniformly.

`mention_text` is truncated at 500 chars (geo-analysis brief mandate)
before any matching to keep downstream artifacts bounded.

### Step 5 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(queries)} sorgu için GEO/AEO analizi hesaplandı, "
            f"_state/staging/'a yazalım mı?",
    step_index=4,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 6 — Resume (`approve` → continue)

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug,
                        approver="user")
```

### Step 7 — `write_staging` (atomic, schema-validated, NO Excel write)

Three staging JSON files — one per derived table. Each file follows the
canonical naming `geo_analysis_{table}_{date}_{slug}.json` under
`projects/{slug}/_state/staging/`. NO `transaction.append` here;
staging-only.

```python
import json
from pathlib import Path
date = today.isoformat()
staging_dir = workspace_root / "projects" / project_slug / "_state" / "staging"
staging_dir.mkdir(parents=True, exist_ok=True)

for table in ("llm_mentions", "serp_organic", "signals"):
    payload_key = "geo_signals" if table == "signals" else table
    out_path = staging_dir / f"geo_analysis_{table}_{date}_{project_slug}.json"
    out_path.write_text(
        json.dumps(result[payload_key], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

### Step 8 — `render_report`

`render_template.py templates/reports/geo-analysis.template.md data.json`
→ `outputs/reports/{date}-geo-analysis.md`. Variables: `$project_slug`,
`$date`, `$query_count`, `$credits_used`, `$gap_aeo_needed`,
`$gap_serp_gap`, `$gap_aeo_healthy`, `$gap_absent`, `$top_query`,
`$top_action`.

### Step 9 — Provenance event

Two events — one per upstream paid call. Each carries `cost.credits`;
`target_excel_sheet=null` because output is staging-only.

```python
from scripts.state import events_writer
# run_id=None auto-allocates race-free inside the append flock; reuse the
# returned id to group both provenance events under one geo-analysis run.
geo_run = events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__ai_optimization_llm_mentions_search",
            "response_bytes": len(json.dumps(raw_llm))},
    operation="ingest",
    target_excel_sheet=None,    # staging-only — Phase 8+ projects to Excel
    rows_written=result["meta"]["llm_mention_row_count"],
    cost={"provider": "dataforseo",
          "credits": float(query_count) * 5.0,
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
events_writer.append_provenance(
    project_id=project_slug,
    run_id=geo_run.run_id,    # same run as the llm_mentions event above
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__serp_organic_live_advanced",
            "response_bytes": len(json.dumps(raw_serp))},
    operation="ingest",
    target_excel_sheet=None,
    rows_written=result["meta"]["serp_organic_row_count"],
    cost={"provider": "dataforseo",
          "credits": float(query_count) * 1.0,
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "llm_mention_rows":    str(result["meta"]["llm_mention_row_count"]),
    "serp_organic_rows":   str(result["meta"]["serp_organic_row_count"]),
    "geo_signal_rows":     str(result["meta"]["geo_signal_row_count"]),
    "credits_used":        str(estimate),
    "report_path":         str(report_path),
    "raw_llm":             str(inbox_llm),
    "raw_serp":            str(inbox_serp),
})
```

## llm_visibility_score formula

```
llm_visibility_score = brand_mentioned_models / total_models_queried   (0.0–1.0)
```

Counted at the model level (NOT per-mention) — a single model
mentioning the brand 5 times still contributes 1 to the numerator. The
denominator is the count of distinct `model` values seen for the query
in the response, so a partial-fan-out response (some models timed out
upstream) is reported truthfully.

`AEO_HEALTHY_THRESHOLD = 0.5` — brand must surface in at least half of
queried models for the gap label to be `AEO_HEALTHY`. Score below the
threshold with SERP top-3 still falls under `AEO_NEEDED` (the AEO
surface area is the bigger lever when the brand isn't already a
default LLM citation).

## DURUR conditions (10)

Stop and flag the manager — do not patch, do not fall back.

1. `mcp__dataforseo__ai_optimization_llm_mentions_search` returns
   auth/network/scope error.
2. `check_budget.py --check` exit 1 (or `preflight_budget()` raises
   `BudgetExceededError`) → STOP, awaiting_approval; never silently
   skip the paid call.
3. `_normalize_dfs_response` raises `ValueError` (REST envelope AND
   flat wrapper both fail to parse) → STOP, upstream shape drift.
4. `_state/staging/` path cannot be created (workspace path missing or
   read-only).
5. `inbox/dfs/` path cannot be created.
6. `PSEO_WORKSPACE_ROOT` env unset and no explicit `workspace_root`
   passed to `workflow_runner` / `events_writer`.
7. `workflow_runner.create_run` fails schema validation
   (`schemas/workflow-run.schema.json`).
8. **D-03 cross-source URL normalization mismatch** between LLM
   `cited_url` and SERP `serp_url` for any cross-ref derivation.
   **Default behaviour:** the geo signal row is computed normally
   (since `our_url_cited` and `serp_top_3_present` use *project root*
   prefix matching, not paired URL equality, the mismatch surfaces as
   False rather than silently joining the wrong URL). This is a
   documented design choice — geo-analysis does NOT do
   per-row URL joins; it does presence checks against `project_url_root`,
   so a www-vs-non-www host drift between LLM citations and SERP rows is
   handled by D-03 normalization on both sides without a join. Strict
   mode is unnecessary here (unlike on-page-audit DURUR #4 which DOES
   join paired URLs).
9. **`llm_mentions_search` response shape drift** — `model` field
   renamed/missing, OR `mention_text`/`text` missing on a per-mention
   row → `LlmMentionsDriftError` (DURUR — surface to manager, refuse
   to silently emit empty rows from a broken upstream).
10. **`project.config display_name` empty/missing** — geo-analysis
    needs the project name for `our_brand_mentioned` substring matching
    (case-insensitive). Raise `ProjectNameMissingError` and surface
    "configure project_name first" to the operator.

## Cross-references

- Schemas: `schemas/skill-frontmatter.schema.json` (this frontmatter),
  `schemas/events.schema.json` (`source.kind=dataforseo_mcp`,
  `target_excel_sheet=null` for staging-only ops, `cost.credits` field),
  `schemas/cross-sheet-invariants.json#D-03` (URL canonicalization),
  `schemas/dataforseo-endpoint-mapping.schema.json` (DFS contract;
  `cost.credits_per_call` for `ai_optimization_llm_mentions_search` +
  `serp_organic_live_advanced`).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/state/events_writer.py`, `scripts/budget/check_budget.py`,
  `scripts/reporting/render_template.py`,
  **`scripts/ingestion/dfs_pull.py`** (`_normalize_dfs_response`
  IMPORTED — never copied; the REST envelope vs flat wrapper contract
  lives in dfs_pull and any drift fix propagates to all DFS-consuming
  skills via this single import). **Note:**
  `scripts/excel/transaction.py` is NOT imported (staging-only — D-003).
- Transform: `scripts/discovery/geo_analysis_transform.py`
  (`_normalize_url`, `transform`, `estimate_credits`,
  `preflight_budget`, `GeoAnalysisError`, `LlmMentionsDriftError`,
  `BudgetExceededError`, `ProjectNameMissingError`,
  `LLM_MENTIONS_COLUMNS`, `SERP_ORGANIC_COLUMNS`, `GEO_SIGNALS_COLUMNS`).
- Tests: `tests/skills/test_geo_analysis.py` (≥15 cases incl. URL
  normalization, gap-label heuristic coverage, IMPORT discipline lock,
  budget pre-flight integration, drift DURUR).
- Template: `templates/reports/geo-analysis.template.md`.
- Phase 8+ consumers: `cluster-map` (opportunity projection),
  `monthly-report` (AEO trend dashboards) — both consume the three
  staging JSON files.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises explicitly; no silent
      degrade. Empty cited_url returns "" (documented design choice).
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Budget block
      uses ONLY `uses_paid_mcp` + `estimated_credits`
      (Q-W-A4-01: NO `_per_call` / `_per_url`).
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
      Phase 6 forbidden-slug regex (per worker brief) verified absent
      on all 3 files (SKILL.md + transform + test).
- [x] Budget pre-flight integration — `scripts.budget.check_budget`
      invoked at step 1 BEFORE any paid DFS call (paid-MCP gate).
- [x] Append-only — all events via `events_writer`; raw inbox JSON is
      write-once per (date, slug, tool); staging files are
      overwrite-idempotent (same input → byte-stable).
- [x] **IMPORT discipline (W-B4 brief)** — `_normalize_dfs_response`
      IMPORTED from `scripts.ingestion.dfs_pull` (never copied).
      Locked by `tests/skills/test_geo_analysis.py::
      test_normalize_helper_imported_not_copied` identity check.
- [x] Cross-module IMPORT discipline — `workflow_runner` /
      `events_writer` / `check_budget` / `render_template` are imported,
      never modified from this skill. `scripts.excel.transaction` is
      NOT imported (staging-only — D-003).
- [x] D-03 URL canonicalization applied on BOTH `cited_url` (LLM) and
      `serp_url` (SERP) before any presence check. Idempotency held.
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
