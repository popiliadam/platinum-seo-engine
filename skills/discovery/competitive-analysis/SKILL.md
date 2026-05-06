---
name: competitive-analysis
description: |
  Use when: kullanıcı "rakip analizi", "competitive analysis", "competitor
  monitoring", "rakip site snapshot", "rakip içerik takibi", "competitor
  diff", "rakip keyword'leri", "weekly competitor" der ya da
  /pseo-competitive-analysis çağırır.
  Also use when: hedef alan adı için DFS competitors_domain ile rakip
  listesi çekilecek; rakip URL'leri Scrapling tier-escalation §14.5 ile
  fetch edilecek; ADR-025 Phase 7+ S1_competitor_snapshot sub-schema
  enforcement gerekiyor; weekly cadence (S1 senaryosu) cron tetikliyor;
  sf-import / gsc-pull veri çekiminden bağımsız rakip izleme talep edildi.
  Do not use when: kendi sitemizin on-page kontrolü (on-page-audit), kendi
  GSC verisi (gsc-pull), keyword volume/ideas (dfs-pull / cluster-map),
  cannibalization (cannibalization), tech audit (tech-audit) — ayrı
  skill'ler. Master.xlsx yokken çağırma; init-project önce çalışmalı.
  Budget pre-flight FAIL ise fallback YASAK (DURUR #2). >50% URL all-tiers
  fail ise batch unhealthy → DURUR #4. Tier_escalation override §14.5
  canonical sequence dışındaysa STOP (DURUR #7).
version: "1.0"
status: active
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json + _state/staging/."
  target_domain:
    type: string
    required: true
    description: "Hedef domain (rakip listesi DFS competitors_domain ile bu domain için çekilir)."
  competitor_urls:
    type: array
    required: false
    description: "Doğrudan fetch edilecek rakip URL listesi. Boşsa DFS competitors_domain çıktısından domain başına 1 anasayfa türetilir."
  max_urls:
    type: integer
    required: false
    default: 50
    description: "URL count budget; aşılırsa scrapling-ops upstream DURUR (UrlBudgetExceededError)."
  bulk_threshold:
    type: number
    required: false
    default: 0.5
    description: "Bulk fetch unhealthy oranı; bu eşiği aşan all-tiers-fail → BulkUnhealthyError (DURUR #4)."
outputs:
  - "_state/staging/competitive_analysis_{date}_{slug}.json"
  - "outputs/reports/{date}-competitive-analysis.md"
  - "events.jsonl"
  - "inbox/scrapling/{date}-bulk_stealthy_fetch-competitor-{slug}.json"
  - "inbox/dfs/{date}-competitors_domain-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "scrapling-ops:projects/{slug}/_state/staging/scrapling_{date}_{slug}.json"
produces: []
triggers:
  manual: ["/pseo-competitive-analysis"]
  natural_language: |
    "rakip analizi", "competitive analysis", "competitor monitoring",
    "rakip site snapshot", "rakip içerik takibi", "competitor diff",
    "rakip keyword'leri", "weekly competitor"
  hooks: []
  scheduled:
    - cron: "0 9 * * 1"
      mode: "report-only"
mcp_tools:
  required:
    - "mcp__ScraplingServer__bulk_stealthy_fetch"
    - "mcp__dataforseo__dataforseo_labs_google_competitors_domain"
  optional:
    - "mcp__dataforseo__dataforseo_labs_google_domain_rank_overview"
    - "mcp__dataforseo__backlinks_competitors"
    - "mcp__ScraplingServer__bulk_fetch"
    - "mcp__ScraplingServer__bulk_get"
budget:
  uses_paid_mcp: true
  estimated_credits: 5
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# competitive-analysis — discovery skill (Phase 7 Wave 2 / W-B3)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight + §14.5
canonical tier ladder. Raw JSON drift recovery is mandatory: every DFS /
Scrapling response is dropped into `inbox/dfs/` or `inbox/scrapling/`
*before* any transform runs, so a transform bug never costs us the
upstream payload (DFS competitors_domain is paid; re-fetch costs credits).

This skill follows the **convention authority** of:

- `skills/ingestion/scrapling-ops/SKILL.md` — Phase 6 generic helper;
  authoritative for the §14.5 tier_escalation invariant + bulk URL
  routing + `inbox/scrapling/` raw-recovery discipline.
- `skills/ingestion/dfs-pull/SKILL.md` — paid-MCP authority; budget
  pre-flight at Step 1, `cost.credits` provenance fields,
  `_normalize_dfs_response` for REST envelope vs flat wrapper.
- `skills/discovery/quick-wins/SKILL.md` (Phase 5) and
  `skills/discovery/cannibalization/SKILL.md` (Phase 7 Wave 1) — 10-step
  shape, raw inbox, D-03 URL invariant, DURUR + flag rule, provenance
  event format.

**ADR-025 Phase 7+ activation (NEW):** this skill is the first concrete
consumer of `templates/scrapling/S1_competitor_snapshot.schema.json`.
Every projected staging row passes Draft7 validation against that
sub-schema before it lands on disk; failure raises `StagingSchemaError`
(DURUR #3). The S1 schema is locked alongside this skill — do not
modify either side without an ADR.

## Inputs (frontmatter contract)

| Name               | Type    | Default | Notes                                                              |
|--------------------|---------|---------|--------------------------------------------------------------------|
| `project_slug`     | string  | —       | Required. Resolves `projects/{slug}/master.xlsx` + staging dir.    |
| `target_domain`    | string  | —       | Required. Used for DFS competitors_domain lookup.                  |
| `competitor_urls`  | array   | —       | Optional. Direct override; otherwise derived from competitors_domain. |
| `max_urls`         | integer | 50      | Hard cap; scrapling-ops `UrlBudgetExceededError` upstream.         |
| `bulk_threshold`   | number  | 0.5     | Above-threshold all-tiers-fail rate → `BulkUnhealthyError`.        |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/_state/staging/competitive_analysis_{date}_{slug}.json`
  — JSON array of S1-validated competitor snapshot rows. **NO Excel
  write** — Phase 7+ S1 path is staging-only per ADR-025.
- `projects/{slug}/inbox/scrapling/{date}-bulk_stealthy_fetch-competitor-{slug}.json`
  — raw Scrapling response envelope (drift recovery).
- `projects/{slug}/inbox/dfs/{date}-competitors_domain-{slug}.json`
  — raw DataForSEO competitors_domain response (drift recovery; paid).
- `projects/{slug}/outputs/reports/{date}-competitive-analysis.md`
  — human-readable summary (top competitors, content_hash deltas vs prior
  snapshot, tier distribution, durur list).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance` entries
  with `source.kind` ∈ `{scrapling_mcp, dataforseo_mcp}` and
  `target_excel_sheet=null` (staging-only).

## Tier Escalation (canonical, schema-locked §14.5)

The state machine is fixed by `schemas/scrapling-output-mapping.schema
.json` (`tierEscalation` definition: `["get", "fetch", "stealthy_fetch"]`,
`minItems=3`, `maxItems=3`, const-equal). This skill enforces the same
invariant on the transform side via
`competitive_analysis_transform.assert_canonical_tier_order` — any
caller who supplies a custom `tier_escalation` parameter that diverges
from the canonical sequence raises `TierEscalationOrderError` (DURUR #7).

```
Tier 0  get             — basic HTTP GET, no JS, no anti-bot.
                          Cheapest tier; tries first per-URL.
Tier 1  fetch           — browser-like headers, optional JS render.
Tier 2  stealthy_fetch  — anti-bot bypass (Cloudflare-aware,
                          fingerprint randomization).
                          Failure modes: still blocked → DURUR
                          (do not invent tier 3).
```

**Fixed sequence:** `['get', 'fetch', 'stealthy_fetch']`. Order is
canonical (cheap → expensive). Each tier failure escalates to the next.
All 3 fail → DURUR (the URL is recorded in `events.jsonl` with
`source.kind=scrapling_mcp` and excluded from staging; if the aggregate
failure rate exceeds `bulk_threshold` the whole run halts via
`BulkUnhealthyError`).

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run` + `preflight_budget`

```python
from scripts.state import workflow_runner
from scripts.discovery import competitive_analysis_transform as ca
handle = workflow_runner.create_run(
    skill="competitive-analysis",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "fetch_competitors_domain"},
        {"name": "fetch_scrapling_bulk"},
        {"name": "persist_inbox"},
        {"name": "transform_and_validate"},
        {"name": "request_approval"},
        {"name": "write_staging"},
        {"name": "render_report"},
    ],
)

# §16.8 budget pre-flight — DURUR #2 on FAIL.
ca.preflight_budget(
    estimated_credits=ca.estimate_credits(1),     # competitors_domain ~5 credits
    project_config_path=str(workspace_root / "projects" / project_slug / "project.config.json"),
    events_path=str(workspace_root / "projects" / project_slug / "_state" / "events.jsonl"),
)
```

### Step 2 — `fetch_competitors_domain` (DFS, paid)

```python
raw_competitors = mcp__dataforseo__dataforseo_labs_google_competitors_domain(
    target=target_domain,
    location_code=2792,           # TR; reuse dfs_pull DEFAULTS
    language_code="tr",
    limit=20,
)
```

Parse via `competitive_analysis_transform.extract_competitor_domains`
(tolerant of both REST envelope AND flat wrapper, identical to
dfs_pull's `_normalize_dfs_response`).

### Step 3 — `fetch_scrapling_bulk` (Scrapling, free, tier 2)

For weekly competitor monitoring (S1) we go directly to
`bulk_stealthy_fetch` — competitor sites typically gate at tier 1.
The **§14.5 invariant still applies**: a per-URL run that ascends the
ladder records `tier_attempts` honestly (`get` success → 1, `fetch` →
2, `stealthy_fetch` → 3). Callers wanting full ladder traversal use
`scripts.ingestion.scrapling_ops.bulk_tier_escalate` upstream and
hand `FetchEntry` instances to this transform.

```python
raw_scrapling = mcp__ScraplingServer__bulk_stealthy_fetch(
    urls=competitor_urls,
)
```

### Step 4 — `persist_inbox` (raw drift recovery, §16.5 step 3)

```python
ca.write_inbox_raw(
    raw_competitors,
    workspace_root / "projects" / project_slug / "inbox" / "dfs"
    / f"{date}-competitors_domain-{project_slug}.json",
)
ca.write_inbox_raw(
    raw_scrapling,
    workspace_root / "projects" / project_slug / "inbox" / "scrapling"
    / f"{date}-bulk_stealthy_fetch-competitor-{project_slug}.json",
)
```

Inbox path failure → `InboxPathError` (DURUR #6).

### Step 5 — `transform_and_validate`

Pure compute via `scripts/discovery/competitive_analysis_transform.py`:

```python
entries = ca.fetch_entries_from_scrapling_envelope(raw_scrapling)
result = ca.transform(
    entries,
    project_slug=project_slug,
    snapshot_date=snapshot_iso_utc,
    raw_competitors_domain=raw_competitors,
    bulk_threshold=bulk_threshold,
)
```

Each row goes through `validate_s1_row(row)` — **Draft7 validation
against `templates/scrapling/S1_competitor_snapshot.schema.json`**.
Failure raises `StagingSchemaError` (DURUR #3). All-tiers-fail entries
are excluded from `result["rows"]` and surface in `result["durur_urls"]`
for the events.jsonl + report layers.

If `result["rows"]` is empty AND `result["durur_urls"]` is empty (no
input), the skill exits as a clean no-op (recorded in events.jsonl,
no staging file written).

### Step 6 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{result['meta']['row_count']} rakip URL snapshot alındı, "
            f"_state/staging'e yazalım mı?",
    step_index=4,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 7 — `write_staging` (NO Excel — staging-only per ADR-025)

```python
output_path = (
    workspace_root / "projects" / project_slug
    / "_state" / "staging"
    / ca.staging_filename(date=date, project_slug=project_slug)
)
ca.write_staging_json(result["rows"], output_path)
```

Staging path failure → `StagingPathError` (DURUR #5). The writer
re-validates every row against S1 immediately before flushing the tmp
file to its final name — never persists a drifted row.

Note: `transaction.append` is **NOT** called — there is no Excel target
for the S1 path. Phase 8 may project staging → master.xlsx in a separate
skill (parallel to dfs-pull → cluster-map). The transform module imports
nothing from `scripts.excel` — enforced by `test_transform_does_not_
import_transaction`.

### Step 8 — `render_report`

`render_template.py templates/reports/competitive-analysis.template.md
data.json` → `outputs/reports/{date}-competitive-analysis.md`. Variables:
`$project_slug`, `$date`, `$target_domain`, `$row_count`, `$durur_count`,
`$competitor_domain_count`, `$top_competitors`, `$tier_distribution`,
`$staging_path`, `$run_id`.

### Step 9 — Provenance events (TWO emits — one per source)

```python
from scripts.state import events_writer

# Scrapling — free, target_excel_sheet=null per staging-only.
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        "kind": "scrapling_mcp",
        "mcp_server": "ScraplingServer",
        "mcp_tool": "ScraplingServer__bulk_stealthy_fetch",
        "response_bytes": len(json.dumps(raw_scrapling)),
    },
    operation="ingest",
    target_excel_sheet=None,
    target_table="scrapling_competitor_snapshot",
    rows_written=result["meta"]["row_count"],
)

# DataForSEO — paid, cost.credits populated.
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        "kind": "dataforseo_mcp",
        "mcp_server": "dataforseo",
        "mcp_tool": "dataforseo__dataforseo_labs_google_competitors_domain",
        "response_bytes": len(json.dumps(raw_competitors)),
    },
    operation="ingest",
    target_excel_sheet=None,
    target_table="dfs_competitors_domain",
    rows_written=result["meta"]["competitor_domain_count"],
    cost={
        "provider": "dataforseo",
        "credits": ca.estimate_credits(1),
        "budget_key": "project.config.dataforseo.budget_credits_per_day",
    },
)
```

Per-URL all-tiers-fail entries in `result["durur_urls"]` ALSO get one
`source.kind=scrapling_mcp` provenance event each (operation=ingest,
rows_written=0, validation_status=fail) so drift-check can audit them
without scanning the staging file.

`target_excel_sheet=null` is intentional and supported by
`schemas/events.schema.json` (oneOf: logicalSheet | null).

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "row_count": str(result["meta"]["row_count"]),
    "durur_count": str(result["meta"]["durur_count"]),
    "competitor_domain_count": str(result["meta"]["competitor_domain_count"]),
    "staging_path": str(output_path),
    "report_path": str(report_path),
})
```

Workflow status flips `running → done` (workflow-run schema) and a
`workflow_action=done` event lands in `events.jsonl` (ADR-020).

## S1 Staging Row Shape (templates/scrapling/S1_competitor_snapshot.schema.json)

| Field              | Type            | Notes                                                              |
|--------------------|-----------------|--------------------------------------------------------------------|
| `snapshot_date`    | string (date-time) | Shared across all rows of a batch (snapshot identity).             |
| `domain`           | string          | Competitor root domain (lowercase, no scheme).                      |
| `url_normalized`   | string (uri)    | D-03 canonical form; cross-skill join key.                          |
| `url_original`     | string (uri)    | URL as fetched, pre-normalization.                                  |
| `fetch_method`     | enum            | `get` / `fetch` / `stealthy_fetch` (§14.5).                         |
| `tier_attempts`    | int 1..3        | Tiers attempted before success.                                     |
| `content_hash`     | string `[a-f0-9]{64}` | SHA-256 hex (no `sha256:` prefix on this sub-schema).               |
| `content_excerpt`  | string ≤500     | First 500 chars; for diff visibility.                               |
| `meta_title`       | string \| null  | Page `<title>`.                                                     |
| `meta_description` | string \| null  | `<meta name="description">`.                                        |
| `h1`               | string[]        | All H1 headings (document order).                                   |
| `schema_org_count` | int ≥0          | JSON-LD schema.org block count.                                     |
| `page_size_bytes`  | int ≥0          | Body byte count.                                                    |
| `status_code`      | int 100..599    | HTTP status code.                                                   |
| `fetch_duration_ms`| int ≥0          | End-to-end fetch wall time.                                         |

Required: `snapshot_date`, `domain`, `url_normalized`, `fetch_method`,
`status_code`. The remaining columns are optional in the schema but
written deterministically by the transform (defaults used when the
fetched envelope omits them).

## URL normalization (D-03 invariant)

Every URL passing through this skill is normalized via
`competitive_analysis_transform.normalize_url`. The function is
**idempotent**: `normalize_url(normalize_url(u)) == normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports, strip
trailing slash on non-root, drop fragment, drop tracking params, sort
remaining query keys. Same shape as cannibalization / quick-wins —
cross-skill drift would break the join key contract.

## DURUR conditions (9)

Stop and flag the manager — do not patch, do not fall back.

1. **All 3 Scrapling tiers fail** for a URL (recorded in events.jsonl
   with `source.kind=scrapling_mcp`; excluded from staging file). The
   batch as a whole halts only when `durur_count / total > bulk_threshold`
   — see DURUR #4.
2. **Budget pre-flight FAIL** — `preflight_budget` raises
   `BudgetExceededError`. STOP, awaiting_approval; no DFS or Scrapling
   call is dispatched.
3. **S1 schema validate fail** on a transform staging row — raises
   `StagingSchemaError`. Caused by sub-schema drift; STOP, manager
   confirms before re-run.
4. **Bulk fetch >50% URL fail** rate (across all 3 tiers) — raises
   `BulkUnhealthyError`. Competitor batch unhealthy; STOP, no partial
   staging accepted. Override via `bulk_threshold` input only with
   manager sign-off.
5. **`_state/staging/` path** cannot be created / not writable —
   `StagingPathError`. STOP, surface to manager.
6. **`inbox/scrapling/` or `inbox/dfs/` path** cannot be created —
   `InboxPathError`. STOP; without inbox the raw payload cannot be
   recovered on transform-bug re-runs.
7. **tier_escalation non-canonical order** — caller-supplied sequence
   diverges from `['get','fetch','stealthy_fetch']`; raises
   `TierEscalationOrderError`. §14.5 invariant locked.
8. **`workflow_runner.create_run` fails schema validation**
   (`schemas/workflow-run.schema.json`). STOP.
9. **`PSEO_WORKSPACE_ROOT` env var unset** and no explicit
   `workspace_root` arg passed to `workflow_runner` / `events_writer`.
   STOP, surface to manager.

## Cross-references

- Schemas: `templates/scrapling/S1_competitor_snapshot.schema.json` (this
  skill's S1 sub-schema, ADR-025 Phase 7+ activation),
  `schemas/scrapling-output-mapping.schema.json` (§14.5 const-locked
  tier ladder; §14.2 S1 scenario contract),
  `schemas/events.schema.json` (`source.kind ∈ {scrapling_mcp,
  dataforseo_mcp}`, `target_excel_sheet=null`),
  `schemas/skill-frontmatter.schema.json` (this frontmatter,
  Q-W-A4-01 budget block lock).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/state/events_writer.py`, `scripts/reporting/render_template.py`,
  `scripts/budget/check_budget.py` (via `preflight_budget` helper),
  `scripts/ingestion/dfs_pull.py` (`_normalize_dfs_response` re-use for
  competitors_domain envelope tolerance),
  `scripts/ingestion/scrapling_ops.py` (`TIER_LADDER`, `bulk_tier_escalate`
  for full-ladder runs).
- Transform: `scripts/discovery/competitive_analysis_transform.py`.
- Tests: `tests/skills/test_competitive_analysis.py` (≥7 cases incl.
  S1 schema self-validate, tier_escalation §14.5 order rejection,
  bulk-unhealthy threshold, budget pre-flight PASS/FAIL).
- Template: `templates/reports/competitive-analysis.template.md`.
- ADR: ADR-025 (Phase 7+ sub-schema activation; this skill is the first
  consumer), ADR-026 (Q-015 hard cap on URL count).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7;
      every row validates against
      `templates/scrapling/S1_competitor_snapshot.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `workflow_runner` / `events_writer`
      / `dfs_pull._normalize_dfs_response` / `scrapling_ops` are imported
      where helpful, never modified. `scripts.excel.transaction` is NOT
      imported (staging-only).
- [x] Q-W-A4-01: `budget` block carries only `uses_paid_mcp` and
      `estimated_credits` — schema rejects `_per_call`/`_per_url` keys.
- [x] §14.5 invariant: `assert_canonical_tier_order` enforces
      `['get','fetch','stealthy_fetch']` const-locked sequence.
- [x] Append-only state — `events.jsonl` only grows; no in-place rewrite.
- [x] STAGING-ONLY: no `transaction.append`; output path is
      `_state/staging/competitive_analysis_{date}_{slug}.json`.
