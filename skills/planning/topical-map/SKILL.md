---
name: topical-map
description: |
  Use when: kullanıcı "pillar", "cluster", "topical map", "konu haritası",
  "pillar/cluster taxonomy", "topical taxonomy", "konu mimarisi", "site
  içerik mimarisi", "topic map", "pillar page planı", "içerik mimarisi
  çıkar" der ya da /pseo-topical-map çağırır. DataForSEO keyword_ideas +
  related_keywords raw JSON'larını inbox/dfs/ altına persist eder, opsiyonel
  Phase 7 geo_analysis staging'i konsume ederek pillar/cluster taxonomyye
  enrich note ekler ve master.xlsx#topical_map sheet'ine yazar (workflow_runner
  approve gate'ten geçer).
  Also use when: aktif projenin seed keyword'ü tanımlı; location_code/
  language_code project.config.dataforseo'dan config-first çözülür
  (engine-level ülke varsayılanı YOK); budget pre-flight PASS; cluster-map
  (Phase 8 W-C1 sibling) F-09 cross-sheet konsume edilecek; new-content-plan
  için pillar/cluster strüktürü gerekiyor.
  Do not use when: GSC veri ingestion (gsc-pull), DFS volume lookup
  (dfs-pull), ham keyword aday havuzu üretimi (content-gaps), kümelenmiş
  keyword listesi üretimi (cluster-map), URL çakışması (cannibalization)
  gerekiyor — ayrı discovery / planning / ingestion skill'leri. Master.xlsx
  yokken çağırma; init-project önce çalışmalı (DURUR #3). Budget aşılmışsa
  fallback YASAK (DURUR #1).
version: "1.0"
status: active
category: planning
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
  seed_keyword:
    type: string
    required: true
    description: "Seed concept driving the taxonomy. Becomes pillar #1 even when absent from DFS results; embedded in every row's note for traceability."
  location_code:
    type: integer
    required: false
    description: "DFS location_code. NO engine default — resolved config-first from project.config.dataforseo.location_code. Explicit value overrides config. See '## Locale resolution'."
  language_code:
    type: string
    required: false
    description: "DFS language_code. NO engine default — resolved config-first from project.config.dataforseo.language_code (derived from language.content_locale at init). See '## Locale resolution'."
  max_pillars:
    type: integer
    required: false
    default: 5
    description: "Maximum pillar rows in the emitted topical_map (default 5)."
  max_clusters_per_pillar:
    type: integer
    required: false
    default: 6
    description: "Maximum cluster rows per pillar (default 6)."
  max_supporting_per_cluster:
    type: integer
    required: false
    default: 0
    description: "Maximum supporting rows per pillar bucket. Default 0 = OFF (keeps initial topical_map writes lean)."
  default_status:
    type: string
    required: false
    default: "TODO"
    description: "statusEnum seed for new rows (master-excel.schema.json#/definitions/statusEnum)."
  keyword_cap:
    type: integer
    required: false
    default: 5000
    description: "DoS guard: bir MCP yanıtı bu limiti geçerse DURUR (KeywordCapExceededError)."
outputs:
  - "master.xlsx#topical_map"
  - "outputs/reports/{date}-topical-map.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-keyword_ideas-topical-{slug}.json"
  - "inbox/dfs/{date}-related_keywords-topical-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "geo-analysis:_state/staging/geo_analysis_geo_signals_{date}_{slug}.json"
  - "content-gaps:_state/staging/content_gaps_keyword_ideas_{date}_{slug}.json"
produces:
  - "cluster-map"
  - "new-content-plan"
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-topical-map"]
  natural_language: |
    "pillar", "cluster", "topical map", "konu haritası", "topical taxonomy",
    "pillar/cluster taxonomy", "konu mimarisi", "site içerik mimarisi",
    "topic map", "pillar page planı", "içerik mimarisi çıkar"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__dataforseo_labs_google_keyword_ideas"
    - "mcp__dataforseo__dataforseo_labs_google_related_keywords"
  optional:
    - "mcp__dataforseo__keywords_data_google_trends_explore"
budget:
  uses_paid_mcp: true
  estimated_credits: 2
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# topical-map — planning skill (Phase 8 Wave 1)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight. Raw JSON
drift recovery is mandatory: every DFS response is dropped into
`inbox/dfs/` *before* any transform runs, so a transform bug never
costs us the upstream payload (which is paid; re-fetch costs credits).

This skill follows the **convention authority** of
`skills/discovery/cannibalization/SKILL.md` (Phase 7 Wave 1 — 10-step
protocol shape + DURUR + workflow_runner approve gate),
`skills/discovery/content-gaps/SKILL.md` (Phase 7 Wave 2 — DFS staging
+ budget pre-flight + DoS guard), and `skills/discovery/geo-analysis/SKILL.md`
(Phase 7 Wave 2 — D-003 helper IMPORT discipline + cross-source consume).
The 10-step protocol, raw JSON inbox discipline, budget pre-flight, and
provenance event format are reused verbatim — only the domain content
(target sheet, transform script, pillar/cluster heuristic, F-09 contract)
changes. Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name                          | Type    | Default | Notes                                                                  |
|-------------------------------|---------|---------|------------------------------------------------------------------------|
| `project_slug`                | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.                      |
| `seed_keyword`                | string  | —       | Required. Becomes pillar #1; anchors the taxonomy.                     |
| `location_code`               | integer | *(config)* | Config-first from `project.config.dataforseo.location_code`; no engine default. See **Locale resolution**. |
| `language_code`               | string  | *(config)* | Config-first from `project.config.dataforseo.language_code`. See **Locale resolution**.                    |
| `max_pillars`                 | integer | 5       | Upper bound on pillar rows.                                            |
| `max_clusters_per_pillar`     | integer | 6       | Upper bound on cluster rows per pillar.                                |
| `max_supporting_per_cluster`  | integer | 0       | Supporting rows per pillar bucket (0 = OFF).                           |
| `default_status`              | string  | "TODO"  | statusEnum seed for new rows.                                          |
| `keyword_cap`                 | integer | 5000    | DoS guard per MCP tool.                                                |

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

> **TR caveat.** TR projects (location 2792) are subject to the same
> dataforseo-mcp-server@2.8.9 TR-forwarding bug documented in
> `skills/ingestion/dfs-pull/SKILL.md`; the imported `_normalize_dfs_response`
> tolerates the response shapes, and TR-locale verification stays mandatory
> for TR projects (do not remove it).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#topical_map` — pillar/cluster/supporting
  rows (10 cols, schema-locked). Order: pillar row → cluster rows
  (volume desc) → supporting rows (when enabled).
- `projects/{slug}/outputs/reports/{date}-topical-map.md` — human-readable summary.
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=topical_map`).
- `projects/{slug}/inbox/dfs/{date}-keyword_ideas-topical-{slug}.json` and
  `…-related_keywords-topical-{slug}.json` — raw labs payloads (drift recovery; paid).

## Schema-locked column tuple (master.xlsx#topical_map, 10 cols)

```
pillar, cluster, primary_keyword, monthly_volume, data_source,
assigned_url, page_type, status, priority, note
```

Anchored in `schemas/master-excel.schema.json#topical_map.required_columns`.
The transform's `TOPICAL_MAP_COLUMNS` constant **must equal** this tuple
byte-for-byte; any drift raises `RowSchemaError` at row build time AND at
emit time (defensive double-check).

## Page type vocabulary (free string column, no formal schema enum)

The schema does NOT define an enum for `page_type` (free string column).
The skill commits to a small documented vocabulary so cluster-map /
new-content-plan / monthly-report can branch deterministically:

| `page_type`  | When applied                                                  |
|--------------|---------------------------------------------------------------|
| `pillar`     | Top-of-funnel anchor concept. Seed keyword always wins this.  |
| `cluster`    | Subtopic sharing ≥1 token with its pillar; volume ≥ min_cluster_volume. |
| `supporting` | Long-tail, low-volume, demoted from cluster pool. Optional.   |

New values require an ADR; the transform raises `PageTypeError` for any
value outside this set. **Open Question Q-W-C2-01** documents the lack
of a formal schema enum — promotion is a Phase 9+ governance decision.

## Invariants (cross-sheet)

### F-09 (deferred join) — `cluster_keywords.assigned_url ⊆ topical_map.assigned_url`

This `cluster_keywords ⊆ topical_map` join is a **DEFERRED design rule**
(`schemas/cross-sheet-invariants.json#/deferred_design_rules` → `F-09`,
`computed_by=consistency_check`, `status=deferred`). It is **NOT** enforced
today by `scripts/validation/validate_invariants.py` or the **drift-check**
skill — that cross-sheet join awaits the `consistency_check` tool (Phase 9+).
(Do not confuse it with the *active* `F-09` in
`schemas/cross-sheet-invariants.json#/rules`, which validates a different
thing: `master_task.task_id` uniqueness.) topical-map populates the
**superset** side: every emitted row carries `assigned_url=""` until
cluster-map (W-C1 sibling) or manual edits fill it; this skill guarantees
only that its own row writes are F-09-compatible. Downstream cross-sheet
enforcement is pending the consistency_check tool.

### D-01 — `topical_map.pillar ⊆ data/pillars.json`

CRITICAL. Pillar values must eventually round-trip through
`data/pillars.json`. In W-C2 the seed→pillar mapping is documented in
output but NOT re-keyed automatically (Phase 9 governance). Manager
confirms the seed before approving the workflow run.

### D-03 — URL idempotency

`url_normalizer(x) == x` everywhere. No-op for this skill (writes empty
`assigned_url`); D-03 hardening lives in cluster-map / new-content-plan.

## D-003 helper IMPORT discipline (mandatory, no copy)

```python
from scripts.ingestion.dfs_pull import _normalize_dfs_response
```

The function is owned by `scripts/ingestion/dfs_pull.py:178` (REST
envelope `tasks[0].result[0].items` AND flat wrapper `items` tolerance).
**Copying would silently fork the contract** on the next DFS shape
change. Identity is locked by
`tests/skills/test_topical_map.py::test_topical_map_dfs_normalize_helper_imported`
(`is`-check). KOPYA YASAK.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `preflight_budget` (§16.8, MANDATORY for paid-MCP skills)

Subprocess wrapper around `scripts/budget/check_budget.py` (W-A3/W-A4
paterni). DURUR #1 if exceeded — never silently downgrade.

```python
from scripts.planning import topical_map_transform as tmt

envelope = tmt.preflight_budget(
    project_config_path=project_root / "project.config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
# envelope == {"budget_per_day": 500, "used_24h": 15, "remaining": 485, "exceeded": false}
```

The wrapper raises `BudgetExceededError` when the subprocess exits
non-zero. Inherits from `TopicalMapError` so a single `except` handles
every DURUR class this skill emits.

### Step 2 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="topical-map",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "fetch_keyword_ideas"},
        {"name": "fetch_related_keywords"},
        {"name": "consume_geo_staging"},  # OPTIONAL
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 3 — `fetch_keyword_ideas` + Step 4 — `fetch_related_keywords` (MCP §16.5 step 3 — raw inbox first)

```python
workflow_runner.start_step(handle.run_id, 1, project_slug=project_slug)
# location_code / language_code resolved config-first (see "Locale
# resolution") — no engine-level country default.
raw_ideas = mcp__dataforseo__dataforseo_labs_google_keyword_ideas(
    keywords=[seed_keyword],
    location_code=location_code,    # from project.config.dataforseo
    language_code=language_code,    # from project.config.dataforseo
    limit=keyword_cap,
)
raw_related = mcp__dataforseo__dataforseo_labs_google_related_keywords(
    keyword=seed_keyword,
    location_code=location_code, language_code=language_code,
    depth=2, limit=keyword_cap,
)
# Persist raw → drift recovery (DFS is paid; re-fetch costs credits).
for label, payload in (("keyword_ideas", raw_ideas), ("related_keywords", raw_related)):
    inbox_path = (workspace_root / "projects" / project_slug / "inbox" / "dfs"
                  / f"{today.isoformat()}-{label}-topical-{project_slug}.json")
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
```

### Step 5 — `consume_geo_staging` (OPTIONAL, Phase 7 W-B4 cross-ref)

When `_state/staging/geo_analysis_geo_signals_{date}_{slug}.json` exists,
load it via `topical_map_transform._load_geo_staging(path)`. Each row's
`note` column is enriched with the matching `geo_gap` + `llm_visibility_score`
signals. Missing/unreadable file → graceful skip (`_load_geo_staging`
returns []) — DURUR #5 fires ONLY when the caller explicitly required
geo-staging via a CLI flag and the file is broken.

```python
from scripts.planning import topical_map_transform as tmt

geo_path = (workspace_root / "projects" / project_slug
            / "_state" / "staging"
            / f"geo_analysis_geo_signals_{today.isoformat()}_{project_slug}.json")
geo_rows = tmt._load_geo_staging(geo_path) if geo_path.exists() else []
```

### Step 6 — `transform`

Pure compute via `scripts/planning/topical_map_transform.py`:

```bash
python3 scripts/planning/topical_map_transform.py \
    --raw-keyword-ideas    inbox/dfs/{date}-keyword_ideas-topical-{slug}.json \
    --raw-related-keywords inbox/dfs/{date}-related_keywords-topical-{slug}.json \
    --seed-keyword         "{seed}" \
    --geo-staging          _state/staging/geo_analysis_geo_signals_{date}_{slug}.json \
    --max-pillars          5 \
    --max-clusters-per-pillar 6 \
    --default-status       TODO \
    --output-dir           _state/transform/{run_id}/
```

Produces a JSON object `{"topical_map": [<row>, ...], "meta": {...}}`
shaped to the 10-column master-excel schema. Idempotent: same input →
byte-identical output.

### Pillar / cluster heuristic (transform domain)

```
1. Gather DFS candidates from keyword_ideas + related_keywords. Dedupe
   by lower-case keyword; higher-volume entries win on duplicates.
2. PILLAR selection (deterministic):
     - seed_keyword is ALWAYS pillar #1 (synthetic if missing from DFS).
     - Remaining pillar slots fill with candidates that:
         (a) clear min_pillar_volume (default 100),
         (b) share ≥1 token with the seed (sub-pillar of same overall topic),
         (c) don't share their token-set with an already-selected pillar
             (avoids "dental clinic" + "dental clinics" double-pillar).
3. CLUSTER bucketing:
     - For each remaining candidate, compute Jaccard overlap against
       every pillar; assign to the pillar with the maximum overlap > 0.
       Candidates with 0 overlap to all pillars are SKIPPED (sibling
       topics, not in this taxonomy).
4. Per pillar, sort assigned candidates by volume desc, take the first
   max_clusters_per_pillar as cluster rows; below min_cluster_volume
   → demoted to supporting pool.
5. Emit rows: pillar block first (pillar row → cluster rows → supporting
   rows), in pillar order from Step 2.
```

### Geo signal cross-reference (note enrichment)

```python
note = "seed=<seed>; geo_gap=<gap>; llm_vis=<score>; pillar_vol=<n>"
```

Only fields with signal land in the note string; absent signals collapse
to nothing. The note column stays free-form; downstream parsers are
optional.

### Step 7 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=(f"{result['meta']['pillar_count']} pillar / "
             f"{result['meta']['cluster_count']} cluster bulundu, "
             f"master.xlsx#topical_map'e yazalım mı?"),
    step_index=4,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 8 — Resume (`approve` → `write_excel`)

Single `committer.commit` call — the orchestrator's idempotent commit path
(whole-block `transaction.replace` from the schema's `data_start_row`, so
re-running never duplicates rows on the `topical_map` snapshot sheet). Goes
through the single approved write path (backup + lock + schema validation +
post-write provenance event).

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug, approver="user")
from scripts.orchestration import committer
committer.commit(
    workspace_root/"projects"/project_slug/"master.xlsx",
    "topical_map",
    topical_map_rows,
    run_id=handle.run_id,
    project_slug=project_slug,
    writer="topical-map",
)
```

### Step 9 — `render_report` + Provenance event

`render_template.py templates/reports/topical-map.template.md data.json`
→ `outputs/reports/{date}-topical-map.md`. Variables: `$project_slug`,
`$date`, `$seed_keyword`, `$pillar_count`, `$cluster_count`,
`$top_pillar`, `$top_pillar_volume`, `$top_cluster`,
`$top_cluster_volume`, `$geo_gaps_summary`, `$report_summary`.

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_ideas",
            "response_bytes": len(json.dumps(raw_ideas))},
    operation="project_excel",
    target_excel_sheet="topical_map",
    rows_written=len(topical_map_rows),
    cost={"provider": "dataforseo",
          "credits": float(estimated_credits),
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
# Repeat for related_keywords (separate provenance entry per MCP call).
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "pillar_count":   str(result["meta"]["pillar_count"]),
    "cluster_count":  str(result["meta"]["cluster_count"]),
    "row_count":      str(result["meta"]["row_count"]),
    "report_path":    str(report_path),
    "raw_jsons":      ";".join([str(inbox_path), str(related_inbox)]),
    "credits_used":   str(estimated_credits),
})
```

Workflow status flips `running → done` (workflow-run schema) and a
`workflow_action=done` event lands in `events.jsonl` (ADR-020).

## DURUR conditions (≥6)

Stop and flag the manager — do not patch, do not fall back.

1. **Budget pre-flight FAIL** — `scripts/budget/check_budget.py` exits
   non-zero → `BudgetExceededError`. DFS is paid; running over budget
   is unrecoverable from this side.
2. **DFS payload unparseable** — `mcp__dataforseo__…_keyword_ideas` /
   `…_related_keywords` returns auth/network error OR a shape the
   imported `_normalize_dfs_response` refuses
   (`ValueError("Unrecognized DFS response shape")`). STOP — wrapper
   drift is an ADR-level event.
3. **Column tuple drift** — `master.xlsx#topical_map` column count or
   names don't match the 10-column schema → `RowSchemaError` at row
   build OR emit time.
4. **Row-level RowSchemaError** — `monthly_volume` not int, `status`
   not in statusEnum, `default_status` argument invalid.
5. **geo-analysis staging missing when required** — caller opted into
   `--require-geo-staging` but file missing/unreadable →
   `GeoStagingMissingError`. Default is graceful skip; this DURUR
   fires only on opt-in.
6. **page_type vocabulary violation** — `page_type` outside
   `{pillar, cluster, supporting}` → `PageTypeError`. New values
   require an ADR (Q-W-C2-01).
7. **`keyword_cap` exceeded** (default 5000) →
   `KeywordCapExceededError`. DoS prevention.
8. **`inbox/dfs/` path unwritable** (workspace misconfigured / readonly)
   or `workflow_runner.create_run` fails schema validation
   (`schemas/workflow-run.schema.json`).
9. **Config locale unresolvable** — `location_code` / `language_code`
   cannot be resolved (no explicit input AND `project.config.dataforseo`
   missing/unreadable). STOP before any paid MCP call; never default to a
   country (engine is project-agnostic). See **Locale resolution**.

## Cross-references

- Schemas: `master-excel.schema.json#topical_map` (10 cols +
  statusEnum), `cross-sheet-invariants.json` (F-09 + D-01),
  `events.schema.json` (`dataforseo_mcp` / `topical_map`),
  `skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `workflow_runner`, `transaction`,
  `events_writer`, `check_budget` (subprocess), `render_template`.
  From `dfs_pull`: `_normalize_dfs_response` imported (KOPYA YASAK,
  identity test).
- Transform: `scripts/planning/topical_map_transform.py` (`transform`,
  `estimate_credits`, `preflight_budget`, `_load_geo_staging`,
  `TOPICAL_MAP_COLUMNS`, `PAGE_TYPE_*`).
- Tests: `tests/skills/test_topical_map.py` (15 cases incl. import-
  identity + 10-col tuple lock).
- Phase 8 `cluster-map` (W-C1 sibling) consumes
  `master.xlsx#topical_map` as the F-09 superset before writing
  `master.xlsx#cluster_keywords`. The `cluster_keywords ⊆ topical_map`
  join is a DEFERRED design rule (computed_by=consistency_check, Phase 9+)
  — NOT yet enforced by drift-check /
  `scripts/validation/validate_invariants.py`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `skill-frontmatter.schema.json` Draft 7; budget block obeys
      `additionalProperties:false` (Q-W-A4-01).
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Budget pre-flight at Step 1 BEFORE any paid call.
- [x] Cross-module IMPORT discipline — `transaction`, `workflow_runner`,
      `events_writer` imported, not modified. `_normalize_dfs_response`
      imported from `dfs_pull` (KOPYA YASAK enforced by identity test).
- [x] DoS guard — `keyword_cap` default 5000.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` STRING-TYPED.
- [x] F-09 superset side: every emitted row carries `assigned_url=""`
      until cluster-map (Phase 8 W-C1) or manual edits fill it.
- [x] Append-only state — `events.jsonl` only grows.
