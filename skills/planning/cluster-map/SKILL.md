---
name: cluster-map
description: |
  Use when: kullanıcı "cluster map", "keyword cluster", "cluster keywords",
  "cluster-keyword haritası", "anahtar kelime kümeleme", "intent cluster",
  "cluster planı", "keyword'leri cluster'lara dağıt" der ya da
  /pseo-cluster-map çağırır. DataForSEO keyword_suggestions +
  related_keywords + GSC enhanced_search_analytics raw JSON'larını
  inbox/dfs|gsc/ altına persist eder ve master.xlsx#cluster_keywords
  sheet'ini doldurur (workflow_runner approve gate üzerinden, transaction
  atomic write).
  Also use when: aktif projenin topical_map sheet'i mevcut (D-02
  invariant — cluster ⊆ topical_map.cluster); content-gaps Phase 7
  staging mevcut (seed keyword sinyali); budget pre-flight PASS;
  cluster→keyword projection gerekiyor; new-content-plan / topical-map
  aşağı akıma keyword inventory besleniyor.
  Do not use when: keyword discovery henüz yapılmadı (content-gaps önce
  çalışmalı); sadece pillar/cluster taksonomisi tanımlanacak (topical-map
  ile dene); tek sayfa decay analizi (content-decay), pozisyon 11-20
  fırsat taraması (quick-wins), URL çakışması (cannibalization)
  gerekiyor — ayrı discovery skill'leri. Master.xlsx yokken çağırma;
  init-project önce çalışmalı (DURUR #4). Topical_map sheet boşken
  çağırma; D-02 invariant violation çıkar (DURUR #7). Budget aşılmışsa
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
    description: "Seed keyword. DFS keyword_suggestions + related_keywords çağrıları bunun üstünden yapılır; cluster atama için yapay sinyal kaynağı."
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
  days_back:
    type: integer
    required: false
    default: 28
    description: "GSC enhanced_search_analytics window end=today, start=today-N."
  keyword_cap:
    type: integer
    required: false
    default: 5000
    description: "DoS guard: bir MCP yanıtı bu limiti geçerse DURUR (KeywordCapExceededError)."
  default_status:
    type: string
    required: false
    default: "TODO"
    description: "statusEnum seed value (master-excel.schema.json#/definitions/statusEnum)."
outputs:
  - "master.xlsx#cluster_keywords"
  - "outputs/reports/{date}-cluster-map.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-keyword_suggestions-cluster-{slug}.json"
  - "inbox/dfs/{date}-related_keywords-cluster-{slug}.json"
  - "inbox/gsc/{date}-enhanced_search_analytics-cluster-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "content-gaps:_state/staging/content_gaps_keyword_ideas_*.json"
  - "topical-map:master.xlsx#topical_map"
produces:
  - "new-content-plan"
  - "drift-check"
triggers:
  manual: ["/pseo-cluster-map"]
  natural_language: |
    "cluster map", "keyword cluster", "cluster keywords",
    "cluster-keyword haritası", "anahtar kelime kümeleme",
    "intent cluster", "cluster planı", "keyword'leri cluster'lara dağıt"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__dataforseo_labs_google_keyword_suggestions"
    - "mcp__dataforseo__dataforseo_labs_google_related_keywords"
    - "mcp__gsc__enhanced_search_analytics"
  optional:
    - "mcp__dataforseo__dataforseo_labs_search_intent"
budget:
  uses_paid_mcp: true
  estimated_credits: 6
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# cluster-map — planning skill (Phase 8 Wave 1, paid-MCP DFS HEAVY + GSC)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight. Raw JSON
drift recovery is mandatory: every DFS / GSC response is dropped into
`inbox/{dfs,gsc}/` *before* any transform runs, so a transform bug
never costs us the upstream payload (DFS is paid; re-fetch costs
credits).

This skill follows the **convention authority** of:

- `skills/ingestion/dfs-pull/SKILL.md` (Phase 6 — DFS staging-only D-003
  pattern + REST/flat shape tolerance via `_normalize_dfs_response`).
- `skills/discovery/cannibalization/SKILL.md` (Phase 7 Wave 1 — 10-step
  protocol shape, raw JSON inbox discipline, DURUR-vs-fallback rule,
  provenance event format).
- `skills/discovery/content-gaps/SKILL.md` (Phase 7 Wave 2 — paid-MCP
  DFS HEAVY skeleton + budget pre-flight subprocess wrapper).

The 10-step protocol shape, raw inbox discipline, budget pre-flight,
and provenance event format are reused verbatim — only the domain
content (target sheet, transform script, cluster heuristic, D-02
invariant) changes. Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name              | Type    | Default | Notes                                                                              |
|-------------------|---------|---------|------------------------------------------------------------------------------------|
| `project_slug`    | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.                                   |
| `seed_keyword`    | string  | —       | Required. Drives DFS fetches; staging join key.                                     |
| `location_code`   | integer | 2792    | DFS Turkey.                                                                         |
| `language_code`   | string  | "tr"    | DFS Turkish.                                                                        |
| `days_back`       | integer | 28      | GSC date window end=today, start=today-N.                                           |
| `keyword_cap`     | integer | 5000    | DoS guard per MCP tool.                                                             |
| `default_status`  | string  | "TODO"  | statusEnum seed for new rows (master-excel.schema definitions).                     |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#cluster_keywords` — one row per
  (cluster, keyword) pair (11 cols, schema-locked).
- `projects/{slug}/outputs/reports/{date}-cluster-map.md` —
  human-readable summary (clusters, top keywords per cluster, source
  breakdown, GSC enrichment hit rate).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=dataforseo_mcp` and `gsc_mcp`,
  `target_excel_sheet=cluster_keywords`).
- `projects/{slug}/inbox/dfs/{date}-keyword_suggestions-cluster-{slug}.json`
  — raw DFS keyword_suggestions payload (drift recovery; paid).
- `projects/{slug}/inbox/dfs/{date}-related_keywords-cluster-{slug}.json`
  — raw DFS related_keywords payload (drift recovery; paid).
- `projects/{slug}/inbox/gsc/{date}-enhanced_search_analytics-cluster-{slug}.json`
  — raw GSC payload (free; drift recovery).

## D-02 invariant (CRITICAL Phase 8 acceptance gate)

`cluster_keywords.cluster ⊆ data/cluster defs` (HIGH severity, see
`schemas/cross-sheet-invariants.json` D-02). Cluster definitions are
sourced from `master.xlsx#topical_map` column B (`cluster`) — every
emitted cluster value MUST already exist in the topical_map sheet of
the active project. Otherwise the transform raises `ClusterDefError`
(DURUR #7). The set is loaded once per run from
`projects/{slug}/master.xlsx#topical_map`, deduplicated, lowercased
for matching but emitted with the original casing carried by
topical_map (case preserved on output).

## D-003 staging consume (paterni: content-gaps)

Phase 7 W-B1 left `_state/staging/content_gaps_keyword_ideas_*.json`
under `projects/{slug}/_state/staging/` as a candidate inventory for
this skill. cluster-map prefers staging input when present — it cuts a
DFS round-trip and seeds clusters from already-paid-for keyword data.
When staging is absent (plugin-only repo, fresh workspace), the
transform falls back to live MCP keyword_suggestions + related_keywords
fetches. Staging consume is OPTIONAL not REQUIRED — the live MCP path
is the source of truth.

## Shape adapter (`_normalize_dfs_response`)

Runtime tolerates two DFS response shapes — REST envelope
`tasks[0].result[0].items` AND wrapper-flattened `items` — by
**importing** the function from `scripts.ingestion.dfs_pull` (not
copying). Any future shape fix in dfs-pull is inherited
automatically; KOPYA YASAK is enforced by the import-discipline test
(`test_cluster_map_dfs_normalize_helper_imported`).

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `preflight_budget` (§16.8, MANDATORY for paid-MCP skills)

Subprocess wrapper around `scripts/budget/check_budget.py` (W-A3/W-A4
paterni). DURUR #1 if exceeded — never silently downgrade.

```python
from scripts.planning import cluster_map_transform as cmt

envelope = cmt.preflight_budget(
    project_config_path=project_root / "project.config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
# envelope == {"budget_per_day": 500, "used_24h": 15, "remaining": 485, "exceeded": false}
```

The wrapper raises `BudgetExceededError` when the underlying script
exits non-zero. The error inherits from `ClusterMapError` so a single
`except` handles every DURUR class this skill emits.

### Step 2 — `create_run`

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="cluster-map",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "load_cluster_defs"},
        {"name": "fetch_keyword_suggestions"},
        {"name": "fetch_related_keywords"},
        {"name": "fetch_enhanced_search_analytics"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 3 — `load_cluster_defs` (D-02 source-of-truth load)

Read `master.xlsx#topical_map` column B (cluster) into a deduplicated
list. Empty topical_map → `ClusterDefError` (DURUR #7). The list is
passed to the transform as `cluster_defs=[...]`; every emitted row's
`cluster` field MUST be a member.

### Step 4 — `fetch_keyword_suggestions` (MCP §16.5 step 3 — raw inbox first)

```python
workflow_runner.start_step(handle.run_id, 2, project_slug=project_slug)
raw_sugg = mcp__dataforseo__dataforseo_labs_google_keyword_suggestions(
    keyword=seed_keyword,
    location_code=location_code,    # 2792 = Turkey
    language_code=language_code,    # "tr"
    limit=keyword_cap,
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-keyword_suggestions-cluster-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw_sugg, ensure_ascii=False, indent=2))
```

### Step 5 — `fetch_related_keywords`

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
    / f"{today.isoformat()}-related_keywords-cluster-{project_slug}.json"
)
related_inbox.write_text(json.dumps(raw_related, ensure_ascii=False, indent=2))
```

### Step 6 — `fetch_enhanced_search_analytics` (GSC, free)

```python
raw_gsc = mcp__gsc__enhanced_search_analytics(
    siteUrl=project_config["gsc"]["site_url"],
    startDate=(today - days_back).isoformat(),
    endDate=today.isoformat(),
    dimensions=["query", "page"],
)
gsc_inbox = (
    workspace_root / "projects" / project_slug
    / "inbox" / "gsc"
    / f"{today.isoformat()}-enhanced_search_analytics-cluster-{project_slug}.json"
)
gsc_inbox.write_text(json.dumps(raw_gsc, ensure_ascii=False, indent=2))
```

### Step 7 — `transform`

Pure compute via `scripts/planning/cluster_map_transform.py`. The
transform calls the imported `_normalize_dfs_response()` first to
flatten REST or wrapper shapes uniformly, then assigns each candidate
keyword to a cluster from `cluster_defs`, enriches with GSC
clicks/impressions/position when the keyword matches a GSC query, and
emits one master.xlsx row per (cluster, keyword) pair.

```bash
python3 scripts/planning/cluster_map_transform.py \
    --raw-keyword-suggestions inbox/dfs/{date}-keyword_suggestions-cluster-{slug}.json \
    --raw-related-keywords    inbox/dfs/{date}-related_keywords-cluster-{slug}.json \
    --raw-gsc                 inbox/gsc/{date}-enhanced_search_analytics-cluster-{slug}.json \
    --cluster-defs-json       /tmp/cluster_defs.json \
    --seed-keyword            "{seed}" \
    --keyword-cap             5000 \
    --default-status          TODO \
    --output-dir              _state/transform/{run_id}/
```

Produces a JSON `{"cluster_keywords": [...], "meta": {...}}` shaped to
the master-excel schema (11 columns: cluster, keyword, monthly_volume,
data_source, assigned_url, gsc_clicks, gsc_impressions, gsc_position,
intent, forbidden_kw, forbidden_reason). Idempotent: same input →
byte-identical output.

### Cluster assignment heuristic (transform domain)

```
For each candidate keyword K from DFS:
  1. Lowercase the keyword + every cluster def for matching.
  2. Pick the cluster def whose token set has the highest Jaccard
     similarity with the keyword's token set.
  3. Tie-break: prefer the cluster whose lowercase string appears as a
     substring of the keyword (specificity).
  4. Final tie-break: alphabetical order on the original-case cluster
     string (deterministic).
  5. If the best Jaccard score is 0 AND no substring match → skip
     the keyword (cannot assign without violating D-02).

For each emitted row:
  - intent: from search_intent_info on the DFS item if present
            (Title-Case enum), else "Informational" default.
  - forbidden_kw / forbidden_reason: empty by default; reserved for
    project.config blocklist enforcement (Phase 8 Wave 2).
```

### GSC enrichment (free signal)

Every emitted row's `gsc_clicks`, `gsc_impressions`, `gsc_position` are
filled from `raw_gsc` when the keyword (lowercased) matches a GSC
query (lowercased). Multiple matching queries per keyword are summed
(clicks, impressions) / impression-weighted (position). If no GSC
match: all three default to 0 / 0 / 0.0. `assigned_url` is the GSC
top-click URL for that keyword if present, else "".

### Step 8 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{seed_keyword} → {len(rows)} cluster_keywords satırı bulundu, master.xlsx#cluster_keywords'e yazalım mı?",
    step_index=6,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 9 — `write_excel` (atomic, schema-validated) + provenance

Single `committer.commit` call — the orchestrator's idempotent commit path
(whole-block `transaction.replace` from the schema's `data_start_row`, so
re-running never duplicates rows on the `cluster_keywords` snapshot sheet).
Goes through the single approved write path with backup, lock, schema
validation, and post-write provenance event emission.

```python
from scripts.orchestration import committer
committer.commit(
    workspace_root/"projects"/project_slug/"master.xlsx",
    "cluster_keywords",
    cluster_keywords_rows,
    run_id=handle.run_id,
    project_slug=project_slug,
    writer="cluster-map",
)

from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_suggestions",
            "response_bytes": len(json.dumps(raw_sugg))},
    operation="project_excel",
    target_excel_sheet="cluster_keywords",
    rows_written=len(cluster_keywords_rows),
    cost={"provider": "dataforseo",
          "credits": float(estimated_credits),
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
# Repeat with source.kind=gsc_mcp for the GSC enrichment fetch (no cost block).
```

### Step 10 — `render_report` + `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "cluster_keyword_count": str(len(cluster_keywords_rows)),
    "cluster_count":         str(len(set(r["cluster"] for r in cluster_keywords_rows))),
    "report_path":           str(report_path),
    "raw_jsons":             ";".join([str(inbox_path), str(related_inbox), str(gsc_inbox)]),
    "credits_used":          str(estimated_credits),
})
```

`render_template.py templates/reports/cluster-map.template.md data.json`
→ `outputs/reports/{date}-cluster-map.md`. Variables: `$project_slug`,
`$date`, `$seed_keyword`, `$location_code`, `$language_code`,
`$cluster_count`, `$keyword_count`, `$top_cluster`,
`$top_cluster_keywords`, `$gsc_enrichment_hit_pct`,
`$source_breakdown`, `$estimated_credits`,
`$budget_preflight_status`, `$run_id`.

## DURUR conditions (≥7)

Stop and flag the manager — do not patch, do not fall back.

1. **`scripts/budget/check_budget.py` exits non-zero** → subprocess
   wrapper raises `BudgetExceededError`. STOP, await manager approval
   to lift the cap (W-A3/W-A4 paterni).
2. `mcp__gsc__enhanced_search_analytics` returns auth/network/scope
   error or expired token. STOP, do not proceed without GSC signal
   (the schema demands gsc_clicks/impressions/position columns; a
   silent zero-fill would mask the upstream failure).
3. **REST/flat shape both fail** — imported `_normalize_dfs_response`
   raises `ValueError("Unrecognized DFS response shape")`. STOP, the
   shape adapter cannot route the payload; manager review needed.
4. master.xlsx not found / `cluster_keywords` sheet schema column
   count or names don't match `schemas/master-excel.schema.json`
   (11 cols expected). STOP, schema-first violation.
5. `transaction.append` raises `RowSchemaError` (e.g.,
   `monthly_volume` not int, `intent` not in
   {Informational, Commercial, Transactional, Navigational}). STOP.
6. Phase 7 staging consume path resolves but file is corrupt / wrong
   schema AND no live-MCP fallback fixture available. STOP.
7. **D-02 violation** — at least one candidate keyword maps to a
   cluster not present in `cluster_defs` (loaded from
   `master.xlsx#topical_map`). `ClusterDefError` raised. STOP, the
   cross-sheet invariant cannot be silently broken.
8. (optional) `keyword_cap` exceeded by any single MCP response → DoS
   guard `KeywordCapExceededError`.

## Cross-references

- Schemas: `schemas/master-excel.schema.json#cluster_keywords`
  (11 required_columns + intent enum), `schemas/events.schema.json`
  (`source.kind=dataforseo_mcp` and `gsc_mcp`,
  `target_excel_sheet=cluster_keywords`),
  `schemas/cross-sheet-invariants.json` (D-02 source-of-truth),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`,
  `scripts/ingestion/dfs_pull._normalize_dfs_response` (D-003 IDENTITY
  preserved by import-discipline test).
- Transform: `scripts/planning/cluster_map_transform.py`.
- Tests: `tests/skills/test_cluster_map.py` (≥6 cases incl. D-02
  violation, D-003 IDENTITY, budget pre-flight, shape DURUR).
- Template: `templates/reports/cluster-map.template.md` (Phase 8 W-D1
  delivers the actual template; this skill stub-references it).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` /
      `_normalize_dfs_response` are imported, never modified or copied.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] Append-only state — `events.jsonl` only grows; no in-place rewrite.
- [x] D-003 staging consume optional, live-MCP source of truth.
- [x] D-02 enforced at transform time; no silent cluster fabrication.
