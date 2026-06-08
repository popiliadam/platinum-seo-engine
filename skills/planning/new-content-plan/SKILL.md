---
name: new-content-plan
description: |
  Use when: kullanıcı "yeni içerik planı", "content plan üret", "yeni
  makale listesi", "new content plan", "içerik üretim sırası", "TIVL
  taglemesi", "hangi makaleyi yazalım" der ya da /pseo-new-content-plan
  çağırır. Phase 7 content-gaps staging JSON'ını (DFS keyword_ideas
  candidate inventory) okur, opsiyonel keyword_overview + search_intent
  enrichment ekler ve `master.xlsx#new_content_plan` sheet'ine 14-col
  schema-locked row üretir.
  Also use when: aktif projenin master.xlsx#cluster_keywords sheet'i
  cluster-map skill tarafından doldurulmuş; budget pre-flight PASS;
  content-gaps staging mevcut (`_state/staging/content_gaps_*.json`);
  TIVL tag'i (T/I/V/L) atanacak; yeni makale priority/word_count
  hedeflenecek.
  Do not use when: cluster atama (cluster-map önce), content gap discovery
  (content-gaps), tek sayfa decay analizi (content-decay), mevcut içerik
  optimizasyonu (content-improve), URL çakışması (cannibalization)
  gerekiyor — ayrı planning / discovery skill'leri. Master.xlsx
  yokken çağırma; init-project önce çalışmalı (DURUR #6). cluster_keywords
  sheet'i boşsa cluster-map önce çalışmalı (DURUR #6 CLUSTER_KEYWORDS_EMPTY).
  Budget aşılmışsa fallback YASAK (DURUR #1).
version: "1.0"
status: active
category: planning
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
  content_gaps_staging_path:
    type: string
    required: false
    description: "_state/staging/content_gaps_keyword_ideas_*.json yolu; default en yeni content_gaps_keyword_ideas_*.json glob pick."
  default_status:
    type: string
    required: false
    default: "TODO"
    description: "statusEnum seed value for new rows."
  default_tivl_tag:
    type: string
    required: false
    default: "I"
    description: "TIVL tag default (T=Transactional, I=Informational, V=Video, L=Local). Per-row override via search_intent enrichment."
  target_word_count:
    type: integer
    required: false
    default: 1500
    description: "Default target word count per row; overridden by intent heuristic."
  max_rows:
    type: integer
    required: false
    default: 50
    description: "DoS guard: en yüksek gap_score ile sıralanmış ilk N keyword projection edilir."
outputs:
  - "master.xlsx#new_content_plan"
  - "outputs/reports/{date}-new-content-plan.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-keyword_ideas-newplan-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "content-gaps:_state/staging/content_gaps_keyword_ideas_*.json"
  - "cluster-map:master.xlsx#cluster_keywords"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-new-content-plan"]
  natural_language: |
    "yeni içerik planı", "content plan üret", "yeni makale listesi",
    "new content plan", "içerik üretim sırası", "TIVL taglemesi",
    "hangi makaleyi yazalım"
  hooks: []
  scheduled:
    - cron: "0 9 * * 1"
      mode: "report-only"
mcp_tools:
  required:
    - "mcp__dataforseo__dataforseo_labs_google_keyword_ideas"
  optional:
    - "mcp__dataforseo__dataforseo_labs_google_keyword_overview"
    - "mcp__dataforseo__dataforseo_labs_search_intent"
budget:
  uses_paid_mcp: true
  estimated_credits: 6
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# new-content-plan — planning skill (Phase 8 Wave 1)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight. Raw JSON
drift recovery is mandatory: every DFS response is dropped into
`inbox/dfs/` *before* any transform runs, so a transform bug never
costs us the upstream payload (which is paid; re-fetch costs credits).

This skill follows the **convention authority** of
`skills/discovery/cannibalization/SKILL.md` (Phase 7 Wave 1 — 10-step
protocol + DURUR + URL normalization), `skills/discovery/content-gaps/SKILL.md`
(Phase 7 Wave 2 — D-003 staging consume + budget pre-flight), and
`skills/ingestion/dfs-pull/SKILL.md` (Phase 6 — REST/flat shape
tolerance via `_normalize_dfs_response`). The 10-step protocol, raw
JSON inbox discipline, budget pre-flight, and provenance event format
are reused verbatim — only the domain content (target sheet, transform
script, intent → tivl heuristic) changes. Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name                         | Type    | Default | Notes                                                                          |
|------------------------------|---------|---------|--------------------------------------------------------------------------------|
| `project_slug`               | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.                              |
| `content_gaps_staging_path`  | string  | newest  | Phase 7 staging JSON; default = newest `content_gaps_keyword_ideas_*.json`.    |
| `default_status`             | string  | "TODO"  | statusEnum seed (master-excel.schema.json#/definitions/statusEnum).             |
| `default_tivl_tag`           | string  | "I"     | TIVL tag default (T/I/V/L); per-row override via search_intent.                |
| `target_word_count`          | integer | 1500    | Default target word count; intent-heuristic override.                          |
| `max_rows`                   | integer | 50      | DoS guard: top-N rows by gap_score.                                            |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#new_content_plan` — one row per planned
  article (14 cols, schema-locked).
- `projects/{slug}/outputs/reports/{date}-new-content-plan.md` —
  human-readable summary (top planned keywords, TIVL distribution,
  cluster coverage).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=dataforseo_mcp`,
  `target_excel_sheet=new_content_plan`).
- `projects/{slug}/inbox/dfs/{date}-keyword_ideas-newplan-{slug}.json`
  — raw DFS payload (drift recovery).

## Dependencies (concurrent write awareness)

This planning skill **READS** `master.xlsx#cluster_keywords` (populated
by sibling `cluster-map` planning skill) and **WRITES** to
`master.xlsx#new_content_plan`. The two skills can be dispatched
concurrently by a manager session, but their interaction is governed
by a **snapshot-at-dispatch read pattern**:

  - new-content-plan reads `cluster_keywords.assigned_cluster` values
    at workflow_runner gate time (right before `transaction.append`),
    **NOT at transform time**. This avoids parallel-write races on the
    same workbook (`scripts/excel/transaction.py` provides atomic
    SQLite-style locking via `_acquire_lock` so concurrent writes are
    serialised at the I/O layer).
  - If `cluster_keywords` sheet is empty when this skill runs (i.e.
    cluster-map has not yet completed), the skill emits a DURUR with
    code `CLUSTER_KEYWORDS_EMPTY` and a Turkish-language message
    suggesting "önce cluster-map çalıştır". This is a **runtime
    ordering issue, not a parallel-write issue** — the manager is
    expected to dispatch cluster-map first, then new-content-plan.
  - Re-running new-content-plan after cluster-map populates the sheet
    is idempotent: the same content-gaps staging input + same
    cluster_keywords snapshot produce byte-identical row output.

## D-003 import discipline (paterni: content-gaps)

`_normalize_dfs_response` AND `StagingSchemaError` are **imported**
(never copied) from `scripts.ingestion.dfs_pull` so any future
shape-handling fix in dfs-pull is inherited automatically. The
KOPYA YASAK invariant is enforced by an identity test in
`tests/skills/test_new_content_plan.py`.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across
> runs.

### Step 1 — `preflight_budget` (§16.8, MANDATORY for paid-MCP skills)

Subprocess wrapper around `scripts/budget/check_budget.py` (W-A3/W-A4
paterni). DURUR #1 if exceeded — never silently downgrade.

```python
from scripts.planning import new_content_plan_transform as ncp

envelope = ncp.preflight_budget(
    project_config_path=project_root / "project.config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
# envelope == {"budget_per_day": 500, "used_24h": 15, "remaining": 485, "exceeded": false}
```

The wrapper raises `BudgetExceededError` when the underlying script
exits non-zero. The error inherits from `NewContentPlanError` so a
single `except` handles every DURUR class this skill emits.

### Step 2 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="new-content-plan",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "consume_content_gaps_staging"},
        {"name": "fetch_keyword_overview"},      # optional enrichment
        {"name": "fetch_search_intent"},         # optional enrichment
        {"name": "read_cluster_keywords"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 3 — `consume_content_gaps_staging`

Locate the newest `_state/staging/content_gaps_keyword_ideas_*.json`
(or use `content_gaps_staging_path` if explicitly passed). DURUR #5 if
no staging file exists AND no test fallback fixture is provided.

```python
staging_path = ncp.locate_content_gaps_staging(
    project_root=project_root,
    explicit_path=content_gaps_staging_path,
)
staging_payload = json.loads(staging_path.read_text("utf-8"))
```

### Step 4 — `fetch_keyword_overview` (OPTIONAL enrichment)

When the caller wants enriched volume + difficulty (for the keywords
that survive max_rows), pull `keyword_overview` only for the projected
subset (DoS guard: max_rows keywords). Drop the raw response into
`inbox/dfs/`.

```python
raw_overview = mcp__dataforseo__dataforseo_labs_google_keyword_overview(
    keywords=projected_keywords,           # ≤ max_rows
    location_code=location_code,
    language_code=language_code,
)
overview_inbox = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-keyword_ideas-newplan-{project_slug}.json"
)
overview_inbox.parent.mkdir(parents=True, exist_ok=True)
overview_inbox.write_text(json.dumps(raw_overview, ensure_ascii=False, indent=2))
```

### Step 5 — `fetch_search_intent` (OPTIONAL enrichment)

When intent → TIVL mapping is desired, pull `search_intent` for the
projected subset. The `_extract_intent_label` helper maps DFS intent
levels (informational/commercial/transactional/navigational) into
the master-excel `tivl_tag` enum:

```
informational    → "I"
transactional    → "T"
commercial       → "T"  (transactional umbrella for tivl_tag)
navigational     → "I"  (informational fallback — no nav tag in TIVL)
local-pack hits  → "L"
video carousel   → "V"
unknown          → default_tivl_tag (caller-provided, default "I")
```

### Step 6 — `read_cluster_keywords` (snapshot-at-dispatch)

Read `master.xlsx#cluster_keywords` immediately before `transform`
(NOT at fetch time). Build a `{keyword: cluster}` map. If sheet is
empty → DURUR #6 (`CLUSTER_KEYWORDS_EMPTY`).

```python
cluster_map = ncp.read_cluster_keywords_snapshot(
    workbook_path=workspace_root / "projects" / project_slug / "master.xlsx",
)
if not cluster_map:
    raise ncp.ClusterKeywordsEmptyError(
        "cluster_keywords sheet is empty — run cluster-map first "
        "before new-content-plan (workflow ordering issue, not a "
        "parallel-write race)."
    )
```

### Step 7 — `transform`

Pure compute via `scripts/planning/new_content_plan_transform.py`:

```bash
python3 scripts/planning/new_content_plan_transform.py \
    --staging _state/staging/content_gaps_keyword_ideas_{date}_{slug}.json \
    --cluster-map _state/transform/{run_id}/cluster_map.json \
    --raw-keyword-overview inbox/dfs/{date}-keyword_ideas-newplan-{slug}.json \
    --raw-search-intent    inbox/dfs/{date}-search_intent-newplan-{slug}.json \
    --default-status TODO \
    --default-tivl-tag I \
    --target-word-count 1500 \
    --max-rows 50 \
    --date {date} \
    --output-dir _state/transform/{run_id}/
```

Produces a JSON array (`new_content_plan`) shaped to the master-excel
schema (14 columns: id, title, url_slug, primary_keyword,
monthly_volume, assigned_cluster, target_word_count, priority,
created_date, tivl_tag, lifecycle_status, image_prompt, alt_text,
content_type). The last three (Phase-10 additive: `image_prompt`,
`alt_text`, `content_type`) default to empty string at plan time and
are materialised later by `new-blog` / `generate-images` (R-71/R-72/R-77
image discipline + content_type enum). The transform is idempotent:
same input → byte-identical output.

If `meta.row_count == 0`, the skill SKIPS write_excel and emits a
"no new content candidates" notice (clean exit, not error).

### Step 8 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(rows)} yeni içerik planı bulundu, master.xlsx#new_content_plan'a yazalım mı?",
    step_index=6,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 9 — `write_excel` (atomic, schema-validated)

Single `committer.commit` call for the new_content_plan sheet — the
orchestrator's idempotent commit path (whole-block `transaction.replace` from
the schema's `data_start_row`, so re-running never duplicates rows on the
`new_content_plan` snapshot sheet). Goes through the single approved write path
with backup, lock, schema validation, and post-write provenance event emission.

```python
from scripts.orchestration import committer
committer.commit(
    workspace_root/"projects"/project_slug/"master.xlsx",
    "new_content_plan",
    new_content_plan_rows,
    run_id=handle.run_id,
    project_slug=project_slug,
    writer="new-content-plan",
)
```

### Step 10 — Provenance event + report + complete

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__dataforseo_labs_google_keyword_ideas",
            "response_bytes": staging_path.stat().st_size},
    operation="project_excel",
    target_excel_sheet="new_content_plan",
    rows_written=len(new_content_plan_rows),
    cost={"provider": "dataforseo",
          "credits": float(estimated_credits),
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED
    "row_count": str(len(new_content_plan_rows)),
    "report_path": str(report_path),
    "staging_consumed": str(staging_path),
})
```

## TIVL tag heuristic (transform domain)

```
search_intent.main_intent (when search_intent enrichment present):
    "informational"   → "I"
    "transactional"   → "T"
    "commercial"      → "T"   (transactional umbrella)
    "navigational"    → "I"   (informational fallback)
    "local"           → "L"
    "video"           → "V"
    unknown / missing → default_tivl_tag (frontmatter input, default "I")

When search_intent enrichment is absent, every row gets default_tivl_tag.
```

## Priority heuristic (transform domain)

Priority tier from gap_score (sourced from content-gaps staging):

```
gap_score >= 1000   → P1
gap_score >=  100   → P2
otherwise           → P3
```

Falls back to monthly_volume when gap_score is 0 (search_intent-only
fixtures): volume >= 1000 → P1, >= 100 → P2, else P3.

## Target word count heuristic (transform domain)

```
tivl_tag == "T"  → 1200  (transactional landing pages — concise + CTA-heavy)
tivl_tag == "L"  → 1000  (local listings — short, scannable)
tivl_tag == "V"  →  800  (video page — supporting copy only)
tivl_tag == "I"  → target_word_count input (default 1500)
```

## URL slug generation (idempotent + plugin-agnostik)

`make_url_slug(keyword)` lowercases, ASCII-folds Turkish characters
(ğ→g, ş→s, ı→i, ü→u, ö→o, ç→c), strips non-alphanum, collapses runs
of "-". The function is **idempotent**: `make_url_slug(make_url_slug(k)) == make_url_slug(k)`.

Within-batch uniqueness is enforced: if two keywords reduce to the same
slug, the transform raises `RowSchemaError` (DURUR #8 — caller can
re-run with disambiguating max_rows or alternate keyword set).

## DURUR conditions (8)

Stop and flag the manager — do not patch, do not fall back.

1. **`scripts/budget/check_budget.py` exits non-zero** → subprocess
   wrapper raises `BudgetExceededError`. STOP, await manager approval
   to lift the cap (W-A3/W-A4 paterni).
2. **REST/flat shape both fail** — imported `_normalize_dfs_response`
   raises `ValueError("Unrecognized DFS response shape")`. STOP, the
   wrapper version drift is an ADR-level event.
3. `master.xlsx#new_content_plan` column count or names don't match
   schema (`schemas/master-excel.schema.json#new_content_plan`, 14
   columns). STOP, schema-first violation.
4. `transaction.append` raises `RowSchemaError` (e.g.,
   `monthly_volume` not int, `status` not in statusEnum, `tivl_tag`
   not in `["T", "I", "V", "L"]`, `lifecycle_status` not in
   `["GREEN", "RED", "ON_HOLD", "REMOVED"]`). STOP.
5. `_state/staging/content_gaps_keyword_ideas_*.json` not found AND no
   explicit fallback fixture passed → `StagingNotFoundError`. STOP,
   request manager run content-gaps first.
6. **`master.xlsx#cluster_keywords` sheet empty at workflow_runner
   gate** → `ClusterKeywordsEmptyError` (code `CLUSTER_KEYWORDS_EMPTY`).
   STOP, run cluster-map before new-content-plan. Runtime ordering
   issue, not parallel-write.
7. `tivl_tag` value drift — produced row has tivl_tag not in the
   master-excel enum `["T", "I", "V", "L"]`. STOP, schema-first
   violation. Defensive: also enforced upstream by frontmatter input
   range check on `default_tivl_tag`.
8. **`url_slug` uniqueness violation within batch** — two keywords
   reduce to the same slug. STOP; re-run with disambiguating
   max_rows or alternate keyword set. (RowSchemaError subclass.)

## Cross-references

- Schemas: `schemas/master-excel.schema.json`
  (new_content_plan sheet, 14 required_columns + statusEnum +
  tivl_tag enum + lifecycle_status enum + content_type enum),
  `schemas/events.schema.json`
  (`source.kind=dataforseo_mcp`,
  `target_excel_sheet=new_content_plan`),
  `schemas/skill-frontmatter.schema.json` (this frontmatter; budget
  block additionalProperties:false enforced).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`,
  `scripts/budget/check_budget.py` (subprocess wrapper). **From
  `scripts/ingestion/dfs_pull.py`: `_normalize_dfs_response` AND
  `StagingSchemaError` are imported — KOPYA YASAK; identity preserved
  by the import-discipline test.**
- Transform: `scripts/planning/new_content_plan_transform.py`
  (`transform`, `read_cluster_keywords_snapshot`,
  `locate_content_gaps_staging`, `make_url_slug`,
  `NEW_CONTENT_PLAN_COLUMNS`, `preflight_budget`).
- Tests: `tests/skills/test_new_content_plan.py` (≥6 cases incl.
  D-003 import-discipline identity check).
- Template: `templates/reports/new-content-plan.template.md` (created
  alongside this skill).
- Phase 7 producer: `skills/discovery/content-gaps/SKILL.md` provides
  the `_state/staging/content_gaps_keyword_ideas_*.json` consumed
  here.
- Sibling planning skill: `skills/planning/cluster-map/SKILL.md`
  populates `master.xlsx#cluster_keywords` whose `assigned_cluster`
  values this skill cross-references.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against Draft 7 schema; budget
      block additionalProperties:false (Q-W-A4-01); new_content_plan row
      shape locked to 14-col master-excel tuple.
- [x] Plugin-agnostik — no slug literals; transform has 0 hardcoded slug.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Budget pre-flight integration — `scripts/budget/check_budget.py`
      invoked at Step 1 (subprocess wrapper) BEFORE any paid call.
- [x] Cross-module IMPORT discipline — `transaction` / `workflow_runner` /
      `events_writer` imported, never modified. From `dfs_pull`:
      `_normalize_dfs_response` + `StagingSchemaError` imported (KOPYA
      YASAK enforced by identity test).
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED (paths / stringified counts).
- [x] Append-only state — `events.jsonl` only grows.
- [x] Cross-ref snapshot-at-dispatch — `cluster_keywords` read right
      before `transaction.append`; concurrent W-C1 writes serialised
      by `transaction._acquire_lock`.
