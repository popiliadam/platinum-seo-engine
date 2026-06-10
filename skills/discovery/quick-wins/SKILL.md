---
name: quick-wins
description: |
  Use when: kullanıcı "quick win", "hızlı kazanım", "kolay yükselebilecek
  sayfalar", "low-hanging fruit", "pozisyon 11-20",
  "CTR düşük yüksek impression" der ya da /pseo-quickwin çağırır.
  Also use when: aktif projenin GSC verisi master.xlsx'te mevcut; opportunity
  scoring yapılacak; kullanıcı sıralamada yükselebilecek fırsatlar arıyor.
  Do not use when: yeni içerik planı (new-content-plan), içerik decay
  (content-decay), tech audit (tech-audit), cannibalization analizi
  gerekiyor — ayrı discovery skill'leri.
version: "1.0"
status: active
category: discovery
inputs:
  project_slug: { type: string, required: true }
  days_back: { type: integer, required: false, default: 28 }
  threshold_position_min: { type: integer, required: false, default: 11 }
  threshold_position_max: { type: integer, required: false, default: 20 }
  threshold_impressions: { type: integer, required: false, default: 100 }
  top_n: { type: integer, required: false, default: 50 }
  aio_check: { type: boolean, required: false, default: false }
  aio_top_k: { type: integer, required: false, default: 20 }
outputs:
  - "master.xlsx#quick_wins"
  - "master.xlsx#opportunity"
  - "outputs/reports/{date}-quickwin.md"
  - "events.jsonl"
  - "inbox/gsc/{date}-detect_quick_wins-{slug}.json"
  - "inbox/gsc/{date}-enhanced_search_analytics-{slug}.json"
  - "inbox/dfs/{date}-aio_presence-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "sf-import:master.xlsx#crawl_sitemap"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-quickwin"]
  natural_language: |
    "quick win", "hızlı kazanım", "low-hanging fruit", "pozisyon 11-20",
    "kolay yükselebilir keyword", "CTR düşük yüksek impression"
  hooks: []
  scheduled:
    - cron: "0 9 * * 1"
      mode: "report-only"
mcp_tools:
  required:
    - "mcp__gsc__detect_quick_wins"
    - "mcp__gsc__enhanced_search_analytics"
  optional:
    - "mcp__gsc__search_analytics"
    # GAP-M2: paid, used ONLY when aio_check=true (default false ⇒ free path).
    - "mcp__dataforseo__serp_organic_live_advanced"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# quick-wins — discovery skill (Phase 5 Wave 1, convention authority)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline. Raw JSON drift recovery is mandatory:
every MCP response is dropped into `inbox/gsc/` *before* any transform
runs, so a transform bug never costs us the upstream payload.

This skill is the **convention authority** for the 12+ ingestion-style
discovery skills planned in Phase 6-12. Reuse the structure verbatim;
deviate only with an ADR.

## Inputs (frontmatter contract)

| Name                       | Type    | Default | Notes                                                  |
|----------------------------|---------|---------|--------------------------------------------------------|
| `project_slug`             | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.       |
| `days_back`                | integer | 28      | GSC date window end=today, start=today-N.               |
| `threshold_position_min`   | integer | 11      | Lower bound on `currentPosition` for inclusion.         |
| `threshold_position_max`   | integer | 20      | Upper bound; also the scoring ceiling (D-03 invariant). |
| `threshold_impressions`    | integer | 100     | Minimum `impressions` per row to qualify.               |
| `top_n`                    | integer | 50      | Cap on rows written into `quick_wins`.                  |
| `aio_check`                | boolean | false   | When true, fetch AI-Overview presence for the top `aio_top_k` queries (GAP-M2). |
| `aio_top_k`                | integer | 20      | How many provisional top queries to AIO-check (only when `aio_check`).  |

### Budget + consent (aio_check)

`budget.uses_paid_mcp`/`estimated_credits` in the frontmatter describe the
DEFAULT path (`aio_check=false` ⇒ free, 0 credits). When `aio_check=true` the
skill additionally calls the paid `mcp__dataforseo__serp_organic_live_advanced`
for the top `aio_top_k` queries: estimated **~0.07–0.14 credits** (K=20 ×
0.0035, AIO discount honesty per measurement-discipline R-140). The runtime
budget pre-flight applies (reuse the aio-competitor-map DURUR #1 pattern).
**Consent is NOT required** for `aio_check`: it is a read-only SERP fetch, and
consent gates outward/irreversible actions only — say so to the operator
rather than blocking.

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#quick_wins` — top-N quick-win rows (10 cols, schema-locked).
- `projects/{slug}/master.xlsx#opportunity` — aggregated per-query opportunity scores.
- `projects/{slug}/outputs/reports/{date}-quickwin.md` — human-readable summary.
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance` entries (`source.kind=gsc_mcp`).
- `projects/{slug}/inbox/gsc/{date}-detect_quick_wins-{slug}.json` — raw MCP payload (drift recovery).
- `projects/{slug}/inbox/gsc/{date}-enhanced_search_analytics-{slug}.json` — raw enrichment payload.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021, ADR-019).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="quick-wins",
    project_slug=project_slug,
    steps=[
        {"name": "fetch_quick_wins"},
        {"name": "fetch_enriched"},
        {"name": "transform"},
        {"name": "fetch_aio_presence"},  # GAP-M2 — only runs when aio_check=true
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `fetch_quick_wins` (MCP §16.5 step 3 — raw inbox first)

```python
workflow_runner.start_step(handle.run_id, 0,
                           project_slug=project_slug)
raw = mcp__gsc__detect_quick_wins(
    siteUrl=project_config["gsc"]["site_url"],
    startDate=(today - days_back).isoformat(),
    endDate=today.isoformat(),
    positionRangeMin=threshold_position_min,
    positionRangeMax=threshold_position_max,
    minImpressions=threshold_impressions,
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "gsc"
    / f"{today.isoformat()}-detect_quick_wins-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
workflow_runner.finish_step(handle.run_id, 0,
                            project_slug=project_slug,
                            output_ref=str(inbox_path))
```

### Step 3 — `fetch_enriched` (optional enrichment)

`mcp__gsc__enhanced_search_analytics` with the same date window. Persist
to `inbox/gsc/{date}-enhanced_search_analytics-{slug}.json`. Failure is
non-fatal — the transform tolerates `enriched=None`.

### Step 4 — `transform`

Pure compute via `scripts/discovery/quickwins_transform.py`:

```bash
python3 scripts/discovery/quickwins_transform.py \
    --raw  inbox/gsc/{date}-detect_quick_wins-{slug}.json \
    --enriched inbox/gsc/{date}-enhanced_search_analytics-{slug}.json \
    --top-n 50 \
    --threshold-position-max 20 \
    --ctr-curve ctr-curve.json \
    --aio-presence inbox/dfs/{date}-aio_presence-{slug}.json \
    --output-dir _state/transform/{run_id}/
```

Produces two JSON arrays (`quick_wins`, `opportunity`) shaped to the
master-excel schema. URL normalization (D-03) is applied here, not at
fetch time, so the raw inbox copy is byte-faithful to the MCP response.
`--ctr-curve` defaults to the engine-root `ctr-curve.json`; `--aio-presence`
is omitted on pass-1 (no `aio_check`) and supplied on pass-2 after
`fetch_aio_presence` writes the consolidated presence map.

### Step 4b — `fetch_aio_presence` (optional; only when `aio_check=true`)

Two-pass discipline (GAP-M2). After the pass-1 `transform`, for the
provisional top-`aio_top_k` queries call
`mcp__dataforseo__serp_organic_live_advanced(keyword=query,
language_code=…, location_name=…, depth=10)`. Persist the consolidated raw
to `projects/{slug}/inbox/dfs/{date}-aio_presence-{slug}.json` (raw-inbox-
first), keyed by query, each value `{aio_presence, own_domain_cited,
checked_date, detection_source}` (derive presence via the
aio-competitor-map `build_serp_aio` contract — `references[]` only, R-140;
MCP-sync may record `present`/`not_detected`, never asserting absence). Then re-run
the pass-2 `transform` with `--aio-presence <that path>`. Provenance event:
`event_kind=provenance, source.kind=dataforseo_mcp, operation=ingest,
target_table="dfs_aio_presence", cost={"provider":"dataforseo",
"credits": K*0.0035}`. The transform helper `load_aio_presence(path)` maps
query → presence-info; queries missing from the file stay `unchecked`
(`unchecked ≠ not_detected`, R-140).

### Step 5 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"Top-{top_n} quick-wins seçildi, master.xlsx'e yazalım mı?",
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

Two idempotent `committer.commit` calls — one per sheet (replace — re-running
refreshes the snapshot, never duplicates rows; routes through transaction.py:
backup + lock + schema validation + provenance).

```python
from scripts.orchestration import committer
committer.commit(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="quick_wins",
    rows=quick_wins_rows,
    run_id=handle.run_id,
    project_slug=project_slug,
    writer="quick-wins",
)
committer.commit(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="opportunity",
    rows=opportunity_rows,
    run_id=handle.run_id,
    project_slug=project_slug,
    writer="quick-wins",
)
```

### Step 8 — `render_report`

`render_template.py templates/reports/quickwin.template.md data.json`
→ `outputs/reports/{date}-quickwin.md`. Variables: `$project_slug`,
`$date`, `$top_n`, `$total_opportunities`, `$top_query`, `$top_url`,
`$top_uplift` (GAP-M3 expected_uplift_clicks), `$top_score` (legacy headroom
tiebreak), `$aio_present_count` (GAP-M2), `$top_position`, `$top_action`,
`$report_summary`.

### Step 9 — Provenance event

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "gsc_mcp", "mcp_server": "gsc",
            "mcp_tool": "gsc__detect_quick_wins",
            "response_bytes": len(json.dumps(raw))},
    operation="project_excel",
    target_excel_sheet="quick_wins",
    rows_written=len(quick_wins_rows),
)
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    "top_n": len(quick_wins_rows),
    "report_path": str(report_path),
    "raw_jsons": [str(inbox_path), str(enriched_path)],
})
```

## URL normalization (D-03 invariant)

Every URL passing through this skill is normalized via
`scripts.discovery.quickwins_transform.normalize_url`. The function is
**idempotent**: `normalize_url(normalize_url(u)) == normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports, strip
trailing slash (root excluded), drop fragment, drop tracking params,
sort remaining query keys.

## Opportunity score (GAP-M3 — expected-CTR-uplift model)

Rows are ranked by **`expected_uplift_clicks`** (28-day): the modelled click
gain from moving a page-2 query onto page 1, discounted when an AI Overview
is present. The formula + a worked example (all curve constants live inside
this fence — R-139):

```text
target = min(10, max(5, position - 5))     # page-1 bottom half, never top-3
ctr_t  = curve.expected_ctr(target) * curve.aio_factor(target, aio_presence)
expected_uplift_clicks = max(0, round(impressions * ctr_t - current_clicks))

# Worked example (frozen curve):
#   pos 12, 1000 impressions, 10 clicks, aio unchecked:
#     target=7 -> ctr(7)=0.030 -> 1000*0.030 - 10 = 20
#   same row, AIO present (position-7 discount factor 0.703):
#     1000*0.030*0.703 - 10 = 11
#   (unchecked / not_detected -> factor 1.0, NO discount — R-140 honesty)
```

All CTR/discount numbers come from the versioned `ctr-curve.json` +
`schemas/ctr-curve.schema.json` (loader `scripts/util/ctr_curve.py`), never
literal copies in the transform/SKILL body — **R-139** (grep-sentinel-tested).
Observed clicks are subtracted so an already-converting row does not
double-count. The legacy headroom score
`impressions * max(0, threshold_position_max - position)` is RETAINED as the
deterministic ranking tiebreaker #2 (then query asc, url asc) and as the
`opportunity` sheet's `opportunity_score` column (no column re-semantics).

**AIO presence columns (R-140).** `quick_wins` gains K `aio_presence`
(`present`/`not_detected`/`unchecked`; absence is never asserted),
L `aio_own_cited`,
M `aio_checked_date`, N `expected_uplift_clicks`; `opportunity` gains I
`aio_presence`, J `expected_uplift_clicks`. With `aio_check=false` every row
is `unchecked` / `false` / `""` plus the computed uplift; `unchecked ≠
not_detected`.

## DURUR conditions (11)

Stop and flag the manager — do not patch, do not fall back.

1. `mcp__gsc__detect_quick_wins` returns auth/network/scope error.
2. Raw JSON inbox path cannot be created (workspace path missing).
3. URL normalization output drifts from schema (mismatch invariant).
4. `master.xlsx#quick_wins` column count or names don't match schema.
5. `committer.commit` raises `RowSchemaError`.
6. `workflow_runner.create_run` fails schema validation.
7. `PSEO_WORKSPACE_ROOT` env unset and no `workspace_root` arg passed.
8. `project.config.json` missing `gsc.site_url`.
9. `quickwins_transform.py` output is not schema-shaped.
10. F-08 (quick_wins.url ⊆ crawl_sitemap.url ∪ gsc_performance.url) fails
    — flag Wave 2 `drift-check` to expect a RED.
11. `ctr-curve.json` missing or schema-invalid (GAP-M3) — the scorer DURURs;
    no silent fallback to the legacy headroom formula (`load_curve` raises
    `CurveLoadError`). Cite R-139.

## Cross-references

- Schemas: `schemas/master-excel.schema.json` (quick_wins K–N, opportunity
  I–J, definitions), `schemas/events.schema.json`,
  `schemas/cross-sheet-invariants.json` (D-03 + F-08 invariants),
  `schemas/skill-frontmatter.schema.json`, `schemas/ctr-curve.schema.json`.
- Data: `ctr-curve.json` (engine-root versioned CTR/AIO curve — R-139).
- Rules: `rules/measurement-discipline.md` R-139 (versioned measurement
  constants), R-140 (AIO presence recording — `present`/`not_detected` only).
- Cross-modules: `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`, `scripts/util/ctr_curve.py`.
- Transform: `scripts/discovery/quickwins_transform.py`.
- Tests: `tests/skills/test_quick_wins.py` (8 cases incl. live MCP).
- Template: `templates/reports/quickwin.template.md`.
