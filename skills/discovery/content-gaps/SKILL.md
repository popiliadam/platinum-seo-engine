---
name: content-gaps
description: |
  Use when: kullanıcı "content gap", "içerik açığı", "rakip keyword bulalım",
  "yeni keyword fırsatı", "konu açığı analizi", "competitor keyword discovery",
  "yeni içerik için keyword araştırması", "ilgili keyword'leri çıkar" der ya
  da /pseo-content-gaps çağırır. DataForSEO keyword_ideas + related_keywords
  (+ optional content_analysis_search) raw JSON'larını inbox/dfs/ altına
  persist eder ve `_state/staging/` altına shape-adapted staging table yazar
  (Phase 8 cluster-map / new-content-plan konsume eder).
  Also use when: aktif projenin seed keyword listesi config'te tanımlı; TR
  (location_code=2792, language_code='tr') varsayılan; budget pre-flight
  PASS; yeni içerik planı (new-content-plan) için aday havuzu gerekiyor;
  cluster-map için keyword inventory besleniyor.
  Do not use when: GSC veri ingestion (gsc-pull), DFS volume lookup
  (dfs-pull), tek sayfa decay analizi (content-decay), pozisyon 11-20
  fırsat taraması (quick-wins), URL çakışması (cannibalization) gerekiyor —
  ayrı discovery / ingestion skill'leri. Master.xlsx yokken çağırma; init-
  project önce çalışmalı (DURUR #4). Budget aşılmışsa fallback YASAK
  (DURUR #2).
version: "1.0"
status: wip
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project-config.json."
  seed_keyword:
    type: string
    required: true
    description: "Seed keyword. DFS keyword_ideas + related_keywords çağrıları bunun üstünden yapılır; her staging satırına embed edilir (cluster-map join key)."
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
  keyword_cap:
    type: integer
    required: false
    default: 5000
    description: "DoS guard: bir MCP yanıtı bu limiti geçerse DURUR (KeywordCapExceededError)."
  use_content_analysis_search:
    type: boolean
    required: false
    default: false
    description: "Optional content_analysis_search üçüncü kaynak; default kapalı (paid credit tasarrufu)."
outputs:
  - "_state/staging/content_gaps_keyword_ideas_{date}_{slug}.json"
  - "_state/staging/content_gaps_related_keywords_{date}_{slug}.json"
  - "_state/staging/content_gaps_content_analysis_search_{date}_{slug}.json"
  - "outputs/reports/{date}-content-gaps.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-keyword_ideas-gaps-{slug}.json"
  - "inbox/dfs/{date}-related_keywords-gaps-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
produces:
  - "cluster-map"
  - "new-content-plan"
  - "drift-check"
triggers:
  manual: ["/pseo-content-gaps"]
  natural_language: |
    "content gap", "içerik açığı", "rakip keyword bulalım", "yeni keyword
    fırsatı", "konu açığı analizi", "competitor keyword discovery",
    "yeni içerik için keyword araştırması", "ilgili keyword'leri çıkar"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__dataforseo_labs_google_keyword_ideas"
    - "mcp__dataforseo__dataforseo_labs_google_related_keywords"
  optional:
    - "mcp__dataforseo__content_analysis_search"
    - "mcp__dataforseo__dataforseo_labs_google_keywords_for_site"
budget:
  uses_paid_mcp: true
  estimated_credits: 5
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# content-gaps — discovery skill (Phase 7 Wave 2, paid-MCP DFS HEAVY)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight. Raw JSON
drift recovery is mandatory: every DFS response is dropped into
`inbox/dfs/` *before* any transform runs, so a transform bug never
costs us the upstream payload (which is paid; re-fetch costs credits).

This skill follows the **convention authority** of
`skills/ingestion/dfs-pull/SKILL.md` (Phase 6 — staging-only D-003
pattern + REST/flat shape tolerance via `_normalize_dfs_response`) and
`skills/discovery/cannibalization/SKILL.md` (Wave 1 structural shape).
The 10-step protocol, raw JSON inbox discipline, budget pre-flight, and
provenance event format are reused verbatim — only the domain content
(target sources, transform script, gap_score heuristic) changes.
Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name                          | Type    | Default | Notes                                                                             |
|-------------------------------|---------|---------|-----------------------------------------------------------------------------------|
| `project_slug`                | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.                                 |
| `seed_keyword`                | string  | —       | Required. Drives DFS fetches; embedded in every staging row (cluster-map join key). |
| `location_code`               | integer | 2792    | DFS Turkey.                                                                       |
| `language_code`               | string  | "tr"    | DFS Turkish.                                                                      |
| `keyword_cap`                 | integer | 5000    | DoS guard per MCP tool.                                                           |
| `use_content_analysis_search` | boolean | false   | Optional third source.                                                            |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/_state/staging/content_gaps_keyword_ideas_{date}_{slug}.json`
  — keyword_ideas candidate staging table (schema-versioned, sha256
  content_hash per row, ISO 8601 microsecond `fetched_at`). Columns from
  `content_gaps_transform.CONTENT_GAPS_COLUMNS`.
- `projects/{slug}/_state/staging/content_gaps_related_keywords_{date}_{slug}.json`
  — related_keywords candidate staging table.
- `projects/{slug}/_state/staging/content_gaps_content_analysis_search_{date}_{slug}.json`
  — optional content_analysis_search staging table (only when input
  `use_content_analysis_search=true`).
- `projects/{slug}/outputs/reports/{date}-content-gaps.md` — human-readable
  summary (top gap_score keywords, source breakdown).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance` entries
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=null` — staging-only).
- `projects/{slug}/inbox/dfs/{date}-keyword_ideas-gaps-{slug}.json` — raw labs payload (drift recovery).
- `projects/{slug}/inbox/dfs/{date}-related_keywords-gaps-{slug}.json` — raw labs payload.

> **Note:** content-gaps does NOT write to `master.xlsx`. Phase 8
> `cluster-map` and `new-content-plan` skills consume the staging tables
> and project to `master.xlsx#cluster_keywords` / `new_content_plan`
> downstream (F-09 shared writer disiplini orada uygulanır).

## D-003 staging-only routing (paterni: dfs-pull)

The Phase 6 D-003 lesson is enforced verbatim here:

  - Discovery skills that produce **candidate inventory** route to
    `_state/staging/` only. No `transaction.append`. No master.xlsx write.
  - Phase 8 planning skills (`cluster-map`, `new-content-plan`) consume
    staging tables and project the chosen subset into Excel — they own
    the F-09 shared-writer discipline for sheets with multiple writers.
  - Re-running content-gaps does NOT touch master.xlsx; only the staging
    JSON is overwritten (idempotent: same input → byte-stable file).

**Shape adapter (`_normalize_dfs_response`):** runtime tolerates two DFS
response shapes — REST envelope `tasks[0].result[0].items` AND wrapper-
flattened `items` — by **importing** the function from
`scripts.ingestion.dfs_pull` (not copying). Any future shape fix in
dfs-pull is inherited automatically; KOPYA YASAK is enforced by the
import-discipline test.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `preflight_budget` (§16.8, MANDATORY for paid-MCP skills)

Subprocess wrapper around `scripts/budget/check_budget.py` (W-A3/W-A4
paterni). DURUR #2 if exceeded — never silently downgrade.

```python
from scripts.discovery import content_gaps_transform as cgt

envelope = cgt.preflight_budget(
    project_config_path=project_root / "project-config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
# envelope == {"budget_per_day": 500, "used_24h": 15, "remaining": 485, "exceeded": false}
```

The wrapper raises `BudgetExceededError` when the underlying script
exits non-zero. The error inherits from `ContentGapsError` so a single
`except` handles every DURUR class this skill emits.

### Step 2 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="content-gaps",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "fetch_keyword_ideas"},
        {"name": "fetch_related_keywords"},
        {"name": "fetch_content_analysis_search"},  # optional
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_staging"},
        {"name": "render_report"},
    ],
)
```

### Step 3 — `fetch_keyword_ideas` (MCP §16.5 step 3 — raw inbox first)

```python
workflow_runner.start_step(handle.run_id, 1, project_slug=project_slug)
raw_ideas = mcp__dataforseo__dataforseo_labs_google_keyword_ideas(
    keywords=[seed_keyword],
    location_code=location_code,    # 2792 = Turkey
    language_code=language_code,    # "tr"
    limit=keyword_cap,
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-keyword_ideas-gaps-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw_ideas, ensure_ascii=False, indent=2))
workflow_runner.finish_step(handle.run_id, 1, project_slug=project_slug,
                            output_ref=str(inbox_path))
```

### Step 4 — `fetch_related_keywords`

```python
raw_related = mcp__dataforseo__dataforseo_labs_google_related_keywords(
    keyword=seed_keyword,
    location_code=location_code,
    language_code=language_code,
    depth=2,
    limit=keyword_cap,
)
related_inbox = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-related_keywords-gaps-{project_slug}.json"
)
related_inbox.write_text(json.dumps(raw_related, ensure_ascii=False, indent=2))
```

### Step 5 — `fetch_content_analysis_search` (OPTIONAL)

Only when the caller passes `use_content_analysis_search=true`.

```python
raw_cas = None
if use_content_analysis_search:
    raw_cas = mcp__dataforseo__content_analysis_search(
        keyword=seed_keyword,
        location_code=location_code,
        language_code=language_code,
    )
    cas_inbox = (
        workspace_root / "projects" / project_slug / "inbox" / "dfs"
        / f"{today.isoformat()}-content_analysis_search-gaps-{project_slug}.json"
    )
    cas_inbox.write_text(json.dumps(raw_cas, ensure_ascii=False, indent=2))
```

### Step 6 — `transform`

Pure compute via `scripts/discovery/content_gaps_transform.py`
(staging-only output). The transform calls the imported
`_normalize_dfs_response()` first to flatten REST or wrapper shapes
uniformly, then builds one staging payload per source:

```bash
python3 scripts/discovery/content_gaps_transform.py \
    --raw-keyword-ideas    inbox/dfs/{date}-keyword_ideas-gaps-{slug}.json \
    --raw-related-keywords inbox/dfs/{date}-related_keywords-gaps-{slug}.json \
    --seed-keyword         "{seed}" \
    --keyword-cap          5000 \
    --staging-dir          _state/staging/ \
    --project-slug         {slug}
```

Produces 2-3 staging JSON files (`content_gaps_keyword_ideas_*.json`,
`content_gaps_related_keywords_*.json`, optionally
`content_gaps_content_analysis_search_*.json`) — each with
`schema_version`, `tool`, `seed_keyword`, `fetched_at` (ISO 8601 µs
UTC), `row_count`, `columns`, `rows[]` (1-indexed `id` + sha256
`content_hash`).

### Gap score formula (transform domain)

```
gap_score = (search_volume / (1 + keyword_difficulty)) * (1 - competition_norm)

competition_norm:
    numeric  → clipped to [0, 1] (DFS competition_index sometimes 0..100;
                                  collapsed by /100)
    LOW      → 0.20
    MEDIUM   → 0.55
    HIGH     → 0.90
    unknown  → 0.50  (mid-band default)
```

Coarse but deterministic. Higher volume → higher score; higher
difficulty / higher competition → lower score. Pluggable: callers may
substitute a custom scorer; the staging column stays `gap_score`
regardless. Result is rounded to 4 decimals for staging idempotency.

Rows are sorted by `gap_score` desc, ties broken by keyword asc.

### Step 7 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{seed_keyword} için {total_candidates} aday keyword bulundu, _state/staging/'e yazalım mı?",
    step_index=5,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 8 — `write_staging` (atomic, schema-validated)

`content_gaps_transform.write_staging()` writes one self-contained
staging JSON per source (overwrite-idempotent) under
`projects/{slug}/_state/staging/`. Schema validated by
`_validate_staging_payload()` before write — `StagingSchemaError`
(IDENTITY-shared with dfs-pull) on drift. **NO `transaction.append`
here; staging-only.**

```python
from scripts.discovery import content_gaps_transform as cgt
written = cgt.write_staging(
    result,
    staging_dir=workspace_root / "projects" / project_slug / "_state" / "staging",
    project_slug=project_slug,
    date=today.isoformat(),
)
# written == {"keyword_ideas": "...", "related_keywords": "...", ["content_analysis_search": "..."]}
```

### Step 9 — Provenance event + report

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_ideas",
            "response_bytes": len(json.dumps(raw_ideas))},
    operation="ingest",
    target_table="content_gaps_keyword_ideas",
    target_excel_sheet=None,    # staging-only; Phase 8 cluster-map projects to Excel
    rows_written=0,             # staging-only: no Excel rows yet
    cost={"provider": "dataforseo",
          "credits": float(estimated_credits),
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
# Repeat for related_keywords (and content_analysis_search when used).
```

`render_template.py templates/reports/content-gaps.template.md data.json`
→ `outputs/reports/{date}-content-gaps.md`. Variables: `$project_slug`,
`$date`, `$seed_keyword`, `$location_code`, `$language_code`,
`$total_candidates`, `$top_keyword`, `$top_gap_score`,
`$source_breakdown`, `$top1_*` … `$top3_*`, `$estimated_credits`,
`$budget_preflight_status`, `$staging_path_ideas`,
`$staging_path_related`, `$run_id`.

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "ideas_staging_rows":   str(result["keyword_ideas"]["row_count"]),
    "related_staging_rows": str(result["related_keywords"]["row_count"]),
    "staging_files":        ";".join(written.values()),
    "seed_keyword":         seed_keyword,
    "credits_used":         str(estimated_credits),
    "report_path":          str(report_path),
    "raw_jsons":            ";".join([str(inbox_path), str(related_inbox)]),
})
```

## DURUR conditions (9)

Stop and flag the manager — do not patch, do not fall back.

1. `mcp__dataforseo__dataforseo_labs_google_keyword_ideas` OR
   `…_related_keywords` returns auth/network/scope error.
2. **`scripts/budget/check_budget.py` exits non-zero** → subprocess
   wrapper raises `BudgetExceededError`. STOP, await manager approval
   to lift the cap (W-A3/W-A4 paterni).
3. **REST/flat shape both fail** — imported `_normalize_dfs_response`
   raises `ValueError("Unrecognized DFS response shape")`. STOP, the
   wrapper version drift is an ADR-level event.
4. `_state/staging/` path cannot be created under `projects/{slug}/`
   (workspace path missing or read-only).
5. **Keyword count from MCP > `keyword_cap`** (default 5000) →
   `KeywordCapExceededError`. DoS prevention; never project a runaway
   payload.
6. `inbox/dfs/` path cannot be created (workspace path missing or
   non-writable).
7. `PSEO_WORKSPACE_ROOT` env var unset and no explicit `workspace_root`
   arg passed to `workflow_runner` / `events_writer`. STOP, surface to
   manager.
8. `workflow_runner.create_run` fails schema validation
   (`schemas/workflow-run.schema.json`).
9. **Both required MCPs return 0 candidate rows** for the seed →
   `NoCandidatesError`. The skill refuses to silently emit empty staging
   — surfaces "no content gaps found for seed=…" so the manager can
   pick a different seed.

(Defensive #5 mirror: `StagingSchemaError` from imported dfs-pull
re-validation also DURURs the run if a row drifts before disk write.)

## Cross-references

- Schemas: `schemas/dataforseo-endpoint-mapping.schema.json` (DFS
  contract; cost.credits_per_call), `schemas/events.schema.json`
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=null` for
  staging-only ops), `schemas/skill-frontmatter.schema.json`
  (this frontmatter; `budget.additionalProperties:false` enforced).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/state/events_writer.py`, `scripts/budget/check_budget.py`
  (subprocess wrapper). **From `scripts/ingestion/dfs_pull.py`:
  `_normalize_dfs_response` AND `StagingSchemaError` are imported —
  KOPYA YASAK; identity preserved by the import-discipline test.**
  **Note:** `scripts/excel/transaction.py` is NOT imported (staging-only).
- Transform: `scripts/discovery/content_gaps_transform.py`
  (`gap_score`, `transform`, `write_staging`, `staging_filename`,
  `_staging_table_dict`, `_validate_staging_payload`,
  `CONTENT_GAPS_COLUMNS`, `preflight_budget`).
- Tests: `tests/skills/test_content_gaps.py` (≥6 cases incl. import-
  discipline identity check).
- Template: `templates/reports/content-gaps.template.md`.
- Phase 8 `cluster-map` skill consumes
  `_state/staging/content_gaps_*.json` and applies F-09 shared-writer
  discipline when projecting to `master.xlsx#cluster_keywords` /
  `new_content_plan` alongside dfs-pull staging.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Budget block
      conforms to `additionalProperties:false` (Q-W-A4-01: only
      `uses_paid_mcp` + `estimated_credits`; no `_per_call` / `_per_url`
      leakage).
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Budget pre-flight integration — `scripts/budget/check_budget.py`
      invoked at Step 1 (subprocess wrapper) BEFORE any paid call.
- [x] Append-only — all events via `events_writer`; staging JSON is
      overwrite-idempotent (re-run produces stable id/content_hash);
      Phase 8 owns the F-09 shared-writer discipline downstream.
- [x] Cross-module IMPORT discipline — `workflow_runner` /
      `events_writer` are imported, never modified. From `dfs_pull`:
      `_normalize_dfs_response` AND `StagingSchemaError` are imported
      (KOPYA YASAK enforced by identity test).
      `scripts.excel.transaction` is NOT imported (staging-only —
      D-003 resolution).
- [x] DoS guard — `keyword_cap` default 5000 (configurable per-run);
      MCP responses larger than the cap → `KeywordCapExceededError`.
- [x] F1: write target is `_state/staging/` (no master.xlsx from this
      skill — Phase 8 cluster-map / new-content-plan owns the projection).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
