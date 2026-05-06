---
name: scrapling-ops
description: |
  Use when: kullanıcı "scrapling fetch", "URL listesi çek", "competitor
  snapshot", "rakip site içeriği indir", "stealth fetch", "anti-bot
  bypass", "Cloudflare aşımı", "tier escalation" der ya da
  /pseo-scrape çağırır. Phase 6 generic helper — staging-only,
  Excel'e yazmaz; raw HTML inbox + SQLite-shaped staging JSON üretir.
  Also use when: bir başka skill ('S1_competitor_snapshot' gibi
  scenario consumer'ı) bu helper'ı tier_escalation orkestrasyonu için
  kullanmak istediğinde; mcp__ScraplingServer__ tool'ları aktif ve
  fetch sırasında 403/429/Cloudflare challenge bekleniyor; kullanıcı
  paid Scrapling MCP yerine ücretsiz katmanı kullanmak istiyor.
  Do not use when: GSC verisi geliyor (gsc-pull), DataForSEO çağrısı
  yapılacak (dfs-pull), Screaming Frog CSV import (sf-import) — ayrı
  ingestion skill'leri. Per-scenario sub-schema validation gerekiyorsa
  ADR-025 gereği Phase 7+ scenario skill'ini bekle (templates/scrapling/
  altındaki şemalar bu skill içinde HENÜZ enforce edilmiyor). Excel'e
  doğrudan yazılması istenirse YASAK — Phase 6 staging-only.
version: "1.0"
status: active
category: ingestion
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/_state + inbox/scrapling/."
  urls:
    type: array
    required: true
    description: "URL listesi. >50 ise DURUR (max_urls ayarı), ≤10 ise single MCP, >10 ise bulk MCP."
  scenario:
    type: string
    required: false
    default: "generic"
    description: "Free-form scenario etiketi (örn. 'generic' / 's1_competitor_snapshot'). Staging row'larında saklanır; Phase 7+ sub-schema enforcement bu alana göre yönlenir."
  max_urls:
    type: integer
    required: false
    default: 50
    description: "URL count budget. Üzerine çıkarsa DURUR (no silent truncation)."
outputs:
  - "inbox/scrapling/{date}-{tier}-{slug}.json"
  - "_state/staging/scrapling_{date}_{slug}.json"
  - "outputs/reports/{date}-scrapling-ops.md"
  - "events.jsonl"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
produces: []
triggers:
  manual: ["/pseo-scrape"]
  natural_language: |
    "scrapling fetch", "URL listesi çek", "competitor snapshot",
    "rakip site içeriği indir", "stealth fetch", "anti-bot bypass",
    "Cloudflare aşımı", "tier escalation"
  hooks: []
mcp_tools:
  required:
    - "mcp__ScraplingServer__fetch"
    - "mcp__ScraplingServer__bulk_fetch"
    - "mcp__ScraplingServer__stealthy_fetch"
    - "mcp__ScraplingServer__bulk_stealthy_fetch"
  optional:
    - "mcp__ScraplingServer__open_session"
    - "mcp__ScraplingServer__close_session"
    - "mcp__ScraplingServer__get"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# scrapling-ops — ingestion skill (Phase 6, generic Scrapling helper)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + the §14.5 canonical tier ladder.
Raw HTML drift recovery is mandatory: every successful tier response is
dropped into `inbox/scrapling/` *before* the staging projection runs,
so a staging bug never costs us the upstream payload.

This skill is the **generic Scrapling helper**. It does NOT enforce
per-scenario sub-schemas (`templates/scrapling/[scenario].schema.json`)
— those belong to Phase 7+ scenario consumer skills (S1 competitor
snapshot, S2 external mentions, etc.) per ADR-025. The
`templates/scrapling/.gitkeep` placeholder must remain untouched until
those skills land.

## Inputs (frontmatter contract)

| Name           | Type    | Default     | Notes                                                                  |
|----------------|---------|-------------|------------------------------------------------------------------------|
| `project_slug` | string  | —           | Required. Resolves `projects/{slug}/_state/staging/`.                  |
| `urls`         | array   | —           | Required. URL list. ≤10 → single MCP, >10 → bulk MCP.                  |
| `scenario`     | string  | `generic`   | Stored on every staging row; downstream filter key.                    |
| `max_urls`     | integer | 50          | DURUR threshold; do not silently truncate (DURUR #6).                  |

## Outputs (artifacts produced)

- `projects/{slug}/inbox/scrapling/{date}-{tier}-{slug}.json` — raw
  per-tier MCP response envelopes (drift recovery; one file per tier
  that produced ≥1 successful response).
- `projects/{slug}/_state/staging/scrapling_{date}_{slug}.json` —
  SQLite-shaped staging table (rows array, columns array). NO Excel
  write in Phase 6 — staging-only per ADR-025.
- `projects/{slug}/outputs/reports/{date}-scrapling-ops.md` —
  human-readable summary (per-tier success counts, DURUR list).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=scrapling_mcp`, `target_excel_sheet=null`).

## Tier Escalation (canonical, schema-locked §14.5)

The state machine is fixed by `schemas/scrapling-output-mapping.schema
.json` (`tierEscalation` definition: `["get", "fetch",
"stealthy_fetch"]`, `minItems=3`, `maxItems=3`, const-equal). Each URL
flows through tiers in order; first success short-circuits. All-fail
records the URL in the staging table with `tier_used=null` and
`status='durur'` — the orchestrator decides whether to halt the
whole run (DURUR #1) based on aggregate failure rate.

```
Tier 0  get             — basic HTTP GET, no JS, no anti-bot.
                          Failure modes: 403, 429, captcha_detected, timeout.
Tier 1  fetch           — browser-like headers, optional JS render.
                          Failure modes: persistent 403, captcha,
                                         Cloudflare challenge.
Tier 2  stealthy_fetch  — anti-bot bypass (Cloudflare-aware,
                          fingerprint randomization).
                          Failure modes: still blocked → DURUR
                          (do not invent tier 3).
```

Bulk URL lists (>10) use `mcp__ScraplingServer__bulk_fetch` and
`mcp__ScraplingServer__bulk_stealthy_fetch`. Tier 0 (`get`) always
runs per-URL — it is the cheapest tier and per-URL form keeps logic
identical to the small-list path. The escalation is per-URL: a
partial-success batch can have URLs at different tiers in the same
staging table.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021, ADR-019).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="scrapling-ops",
    project_slug=project_slug,
    steps=[
        {"name": "validate_inputs"},
        {"name": "open_session"},
        {"name": "tier_escalate"},
        {"name": "persist_inbox"},
        {"name": "request_approval"},
        {"name": "write_staging"},
        {"name": "render_report"},
        {"name": "close_session"},
    ],
)
```

### Step 2 — `validate_inputs`

Validate `len(urls) <= max_urls` and project workspace exists. URL
count over budget → DURUR #6 immediately, no MCP call wasted.

```python
from scripts.ingestion import scrapling_ops
if len(urls) > max_urls:
    raise scrapling_ops.UrlBudgetExceededError(
        f"url count {len(urls)} exceeds max_urls={max_urls}"
    )
```

### Step 3 — `open_session` (optional)

If the MCP server exposes session lifecycle (`open_session`,
`close_session`), open one and bind it to the tier callables. Session
imbalance — open without matching close, or close without prior open
— is DURUR #5.

### Step 4 — `tier_escalate` (canonical §14.5 ladder)

Drive the state machine via the helper:

```python
from scripts.ingestion import scrapling_ops
mcp_clients = {
    "get":            mcp__ScraplingServer__get,            # or fetch fallback
    "fetch":          mcp__ScraplingServer__fetch,
    "stealthy_fetch": mcp__ScraplingServer__stealthy_fetch,
}
bulk_clients = {
    "fetch":          mcp__ScraplingServer__bulk_fetch,
    "stealthy_fetch": mcp__ScraplingServer__bulk_stealthy_fetch,
}
results = scrapling_ops.bulk_tier_escalate(
    urls, mcp_clients, bulk_clients=bulk_clients,
)
```

If aggregate failure rate exceeds 50% the orchestrator halts → DURUR #2.

### Step 5 — `persist_inbox` (raw drift recovery, §16.5 step 3)

For every tier that produced ≥1 success, persist its raw response
envelope to:

```
projects/{slug}/inbox/scrapling/{date}-{tier}-{slug}.json
```

Inbox path creation failure → DURUR #3.

### Step 6 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(urls)} URL fetch tamamlandı, staging'e yazalım mı?",
    step_index=4,
)
```

Skill exits here. The user replies in a fresh session; resume below.

### Step 7 — `write_staging` (NO Excel — Phase 6 staging-only)

Build SQLite-shaped staging rows and write to disk. Schema drift —
column count or order mismatch with `STAGING_COLUMNS` — is DURUR #4.

```python
output_path = (
    workspace_root / "projects" / project_slug
    / "_state" / "staging"
    / f"scrapling_{date}_{project_slug}.json"
)
rows = scrapling_ops.build_staging_rows(results, scenario=scenario)
scrapling_ops.write_staging_json(rows, output_path)
```

Note: `transaction.append` is **NOT** called — there is no Excel
target in Phase 6. The staging file is the durable artifact.

### Step 8 — `render_report`

`render_template.py templates/reports/scrapling-ops.template.md
data.json` → `outputs/reports/{date}-scrapling-ops.md`. Variables:
`$project_slug`, `$date`, `$url_count`, `$ok_count`, `$durur_count`,
`$tier_counts`, `$scenario`, `$staging_path`.

### Step 9 — Provenance event (`source.kind=scrapling_mcp`)

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        "kind": "scrapling_mcp",
        "mcp_server": "ScraplingServer",
        "mcp_tool": "ScraplingServer__bulk_fetch",
        "response_bytes": total_bytes,
    },
    operation="ingest",
    target_excel_sheet=None,   # staging-only — no Excel projection
    target_table=f"scrapling_staging_{scenario}",
    rows_written=len(rows),
)
```

`target_excel_sheet=None` is intentional and supported by
`schemas/events.schema.json` (oneOf: logicalSheet | null) — Phase 6
staging operations carry no Excel sheet.

### Step 10 — `complete` (+ `close_session`)

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    "row_count": len(rows),
    "staging_path": str(output_path),
    "report_path": str(report_path),
    "tier_counts": tier_counts,
})
```

If a session was opened in Step 3, close it here; imbalance → DURUR #5.

## Staging Table (SQLite-shaped JSON)

Columns (`scripts.ingestion.scrapling_ops.STAGING_COLUMNS`):

| Column          | Type            | Notes                                                              |
|-----------------|-----------------|--------------------------------------------------------------------|
| `id`            | integer         | 1-based contiguous; row order = input URL order.                   |
| `url`           | string          | Original URL as supplied.                                          |
| `tier_used`     | string \| null  | `get` / `fetch` / `stealthy_fetch`; null when all 3 failed.        |
| `status`        | string          | `ok` (tier_used set) or `durur` (all tiers failed).                |
| `content_hash`  | string \| null  | `sha256:<hex64>` of UTF-8 content; null on failure.                |
| `content_bytes` | integer         | Byte length of content; 0 on failure.                              |
| `fetched_at`    | string          | ISO 8601 UTC, microsecond, 'Z'-suffixed.                           |
| `error_message` | string \| null  | `; `-joined per-tier errors on durur; null on ok.                  |
| `scenario`      | string          | Carried from input; downstream filter key.                         |

The container envelope is `{"schema_version": "1.0", "table":
"scrapling_staging", "columns": [...], "rows": [...], "row_count": N}`.

Idempotency note: re-running the same URL list yields the **same row
shape** (id sequence, columns) but `content_hash` may drift if the
target page has changed between runs. This is intentional —
content drift is a signal, not a bug.

## DURUR conditions (6+)

Stop and flag the manager — do not patch, do not fall back.

1. **Tier escalation all-3 fail** for a URL the orchestrator considers
   load-bearing (e.g. all URLs in a single-URL run, or aggregate
   `durur_count / total > 0.5` in a batch).
2. **Bulk fetch >50% URL error** rate at tier 1 or 2 (per-batch).
3. **Inbox path creation fail** — `inbox/scrapling/` not writable
   (workspace path missing, permission denied).
4. **Staging JSON schema drift** — `STAGING_COLUMNS` mismatch (column
   added/removed without ADR), staging row missing required key, or
   id sequence not contiguous-1-based.
5. **Session open/close imbalance** — `open_session` succeeded but
   `close_session` skipped/failed, or `close_session` called without
   prior open (resource leak).
6. **URL count > `max_urls`** — refuse rather than silently truncate
   (raises `UrlBudgetExceededError` upstream of any MCP call).

## Cross-references

- Schemas: `schemas/scrapling-output-mapping.schema.json` (§14.5
  tierEscalation const-locked sequence; `scenarios.*` deferred to
  Phase 7+ per **ADR-025**), `schemas/events.schema.json`
  (`source.kind=scrapling_mcp`, `target_excel_sheet=null`),
  `schemas/skill-frontmatter.schema.json`.
- Cross-modules: `scripts/state/workflow_runner.py`,
  `scripts/state/events_writer.py`, `scripts/reporting/render_template.py`.
  Note: `scripts/excel/transaction.py` is **NOT** consumed —
  Phase 6 has no Excel target.
- Helper: `scripts/ingestion/scrapling_ops.py` (tier state machine,
  bulk variants, staging writer).
- Tests: `tests/skills/test_scrapling_ops.py` (≥6 cases incl. all-fail
  DURUR, bulk threshold, max_urls budget).
- Templates: `templates/scrapling/.gitkeep` placeholder kept untouched
  per ADR-025 — per-scenario sub-schemas land with Phase 7+ skills.
- ADR: ADR-025 (Phase 7+ defer), ADR-026 (Q-015 hard cap).
