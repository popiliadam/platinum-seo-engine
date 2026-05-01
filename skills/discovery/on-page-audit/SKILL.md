---
name: on-page-audit
description: |
  Use when: kullanıcı "on-page audit", "meta tag denetimi", "title meta h1
  kontrolü", "hedef sorgu sayfada var mı", "title eksik", "h1 eksik",
  "GSC ile sayfa içi kontrol" der ya da /pseo-on-page-audit çağırır.
  Also use when: aktif projenin master.xlsx'i mevcut; URL listesi config'te
  veya gsc_performance / crawl_sitemap sheet'inden geliyor; budget pre-flight
  PASS; cross-sheet invariant D-03 (URL canonicalization) sağlanmış olmalı;
  GSC verisi varsa cross-ref devreye girer (target_query her URL için top
  performans sorgusudur).
  Do not use when: tek-URL tech audit (tech-audit), keyword volume çekme
  (dfs-pull), GSC delta hesaplama (gsc-pull), content decay 90d analiz
  (content-decay) — ayrı skill'ler. Master.xlsx yokken çağırma; init-project
  önce çalışmalı (DURUR #8). Budget aşılmışsa fallback YASAK (DURUR #1).
version: "1.0"
status: wip
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project-config.json."
  urls:
    type: array
    required: true
    description: "URL listesi (string array). DFS on_page_content_parsing bu URL'ler üstünde çalışır."
  use_gsc_cross_ref:
    type: boolean
    required: false
    default: true
    description: "true ise mcp__gsc__search_analytics ile target_query/clicks/impressions çekilir; false → no-cross-ref mode."
  strict_cross_ref:
    type: boolean
    required: false
    default: false
    description: "true ise DFS/GSC URL set'leri D-03 sonrası disjoint olduğunda CrossRefMismatchError (DURUR #4); false → graceful fall-back."
outputs:
  - "master.xlsx#on_page_audit"
  - "outputs/reports/{date}-on-page-audit.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-content_parsing-onpage-{slug}.json"
  - "inbox/gsc/{date}-search_analytics-onpage-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "gsc-pull:master.xlsx#gsc_performance"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-on-page-audit"]
  natural_language: |
    "on-page audit", "meta tag denetimi", "title meta h1 kontrolü",
    "hedef sorgu sayfada var mı", "title eksik", "h1 eksik",
    "GSC ile sayfa içi kontrol"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__on_page_content_parsing"
  optional:
    - "mcp__gsc__search_analytics"
budget:
  uses_paid_mcp: true
  estimated_credits: 3
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# on-page-audit — discovery skill (Phase 7 Wave 1, paid-MCP)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight. Raw JSON
drift recovery is mandatory: every DFS / GSC response is dropped into
`inbox/dfs/` or `inbox/gsc/` *before* any transform runs, so a transform
bug never costs us the upstream payload (which is paid for DFS; re-fetch
costs credits).

This skill follows the **convention authority** of
`skills/discovery/quick-wins/SKILL.md` (10-step shape, raw inbox, D-03
URL invariant, DURUR + flag rule, provenance event format) and the
**paid-MCP authority** of `skills/ingestion/dfs-pull/SKILL.md` (budget
pre-flight at Step 1, `cost.credits` provenance fields). Deviate only
with an ADR.

Cross-source semantics: DFS supplies the on-page evidence (title /
meta_description / h1[]); GSC supplies the *target_query* per URL (top
performing query by clicks desc, impressions tie-break). Both URL
fields are normalized through the D-03 helper before the join — see
`schemas/cross-sheet-invariants.json#D-03`.

## Inputs (frontmatter contract)

| Name                    | Type    | Default | Notes                                                  |
|-------------------------|---------|---------|--------------------------------------------------------|
| `project_slug`          | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.       |
| `urls`                  | array   | —       | Required. URL list driving the paid content_parsing call. |
| `use_gsc_cross_ref`     | boolean | true    | Cross-ref against gsc_performance via search_analytics. |
| `strict_cross_ref`      | boolean | false   | DURUR #4 behaviour on URL-set disjoint after D-03.      |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#on_page_audit` — per-URL audit rows (8
  cols, schema-locked: url, target_query, impressions_30d, clicks_30d,
  in_title, in_meta, in_h1, action).
- `projects/{slug}/outputs/reports/{date}-on-page-audit.md` —
  human-readable summary (top missing-slot URLs, action histogram).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries with `cost.credits` for every DFS call (`source.kind=dataforseo_mcp`)
  and a separate entry for the GSC cross-ref (`source.kind=gsc_mcp`,
  `cost` omitted — free).
- `projects/{slug}/inbox/dfs/{date}-content_parsing-onpage-{slug}.json`
  — raw DFS payload (drift recovery, paid).
- `projects/{slug}/inbox/gsc/{date}-search_analytics-onpage-{slug}.json`
  — raw GSC payload (drift recovery, free) when cross-ref enabled.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `preflight_budget` (§16.8, MANDATORY for paid MCP)

```
estimate = url_count × 3   # CREDITS_PER_URL_CONTENT_PARSING
```

Run `scripts.budget.check_budget` against the project's 24h running
total. Exit code 0 → proceed. Exit code 1 → DURUR #1
(`BudgetExceededError`); skill exits `awaiting_approval` and never
silently downgrades.

```python
from scripts.discovery import on_page_audit_transform as opa
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="on-page-audit",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "fetch_content_parsing"},
        {"name": "fetch_gsc_cross_ref"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
workflow_runner.start_step(handle.run_id, 0, project_slug=project_slug)
estimate = opa.estimate_credits(len(urls))
envelope = opa.preflight_budget(
    estimated_credits=estimate,
    project_config_path=project_root / "project-config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
workflow_runner.finish_step(handle.run_id, 0, project_slug=project_slug,
                            output_ref=str(envelope))
```

### Step 2 — `fetch_content_parsing` (MCP §16.5 step 3 — raw inbox FIRST)

```python
raw_cp = mcp__dataforseo__on_page_content_parsing(
    urls=urls,    # list[str]
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-content_parsing-onpage-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw_cp, ensure_ascii=False, indent=2))
```

### Step 3 — `fetch_gsc_cross_ref` (optional, free, dimensions=['page','query'])

When `use_gsc_cross_ref=true`:

```python
raw_gsc = mcp__gsc__search_analytics(
    siteUrl=project_config["gsc"]["site_url"],
    startDate=(today - 30).isoformat(),
    endDate=today.isoformat(),
    dimensions=["page", "query"],
)
gsc_inbox = (
    workspace_root / "projects" / project_slug
    / "inbox" / "gsc"
    / f"{today.isoformat()}-search_analytics-onpage-{project_slug}.json"
)
gsc_inbox.write_text(json.dumps(raw_gsc, ensure_ascii=False, indent=2))
```

GSC failure is **non-fatal**: graceful degrade to no-cross-ref mode —
`target_query=""`, `impressions_30d=0`, `clicks_30d=0`, action set to
`"no GSC available for this URL"` (DURUR #9 documents this design choice).

### Step 4 — `transform`

Pure compute via `scripts/discovery/on_page_audit_transform.py`:

```bash
python3 scripts/discovery/on_page_audit_transform.py \
    --raw-content-parsing inbox/dfs/{date}-content_parsing-onpage-{slug}.json \
    --raw-gsc             inbox/gsc/{date}-search_analytics-onpage-{slug}.json \
    --output-dir          _state/transform/{run_id}/
```

Produces a single JSON array (`on_page_audit`) shaped to the master-excel
schema. URL canonicalization (D-03) is applied here on BOTH the DFS URL
and the GSC URL before the join, not at fetch time, so the raw inbox
copies are byte-faithful to the upstream payloads. The transform is
idempotent: same inputs → byte-identical output. Output sorted by
`impressions_30d` desc (stable url asc tie-break).

Action heuristic:

| Condition                                              | action                                  |
|--------------------------------------------------------|-----------------------------------------|
| target_query empty (no GSC for URL)                    | "no GSC data — investigate target intent" |
| in_title + in_meta + in_h1, clicks_30d > 0             | "monitor"                               |
| in_title only                                          | "add to meta + H1"                      |
| missing all three                                      | "rewrite meta cluster"                  |
| mixed (some present, some missing)                     | "patch missing slots"                   |
| cross-ref attempted but URL unmatched                  | "no GSC available for this URL"         |

### Step 5 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(rows)} URL on-page audit hesaplandı, master.xlsx#on_page_audit'a yazalım mı?",
    step_index=4,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 6 — Resume (`approve` → continue)

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug,
                        approver="user")
```

### Step 7 — `write_excel` (atomic, schema-validated)

Single `transaction.append` call for the on_page_audit sheet (8 cols).
Goes through the single approved write path (backup, lock, schema
validation, post-write provenance event emission).

```python
from scripts.excel import transaction
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="on_page_audit",
    rows=on_page_audit_rows,
    project_slug=project_slug,
    writer="on-page-audit",
)
```

### Step 8 — `render_report`

`render_template.py templates/reports/on-page-audit.template.md data.json`
→ `outputs/reports/{date}-on-page-audit.md`. Variables:
`$project_slug`, `$date`, `$url_count`, `$credits_used`,
`$action_monitor`, `$action_add_meta_h1`, `$action_rewrite`,
`$action_patch`, `$action_no_gsc`, `$top_url`, `$top_impressions`.

### Step 9 — Provenance event

One event per upstream call. The DFS event carries `cost.credits`; the
GSC event omits cost.

```python
from scripts.state import events_writer
rid = events_writer.next_run_id(project_slug)
events_writer.append_provenance(
    project_id=project_slug,
    run_id=rid,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__on_page_content_parsing",
            "response_bytes": len(json.dumps(raw_cp))},
    operation="project_excel",
    target_excel_sheet="on_page_audit",
    rows_written=len(on_page_audit_rows),
    cost={"provider": "dataforseo",
          "credits": float(estimate),
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
if use_gsc_cross_ref:
    events_writer.append_provenance(
        project_id=project_slug,
        run_id=rid,
        source={"kind": "gsc_mcp", "mcp_server": "gsc",
                "mcp_tool": "gsc__search_analytics",
                "response_bytes": len(json.dumps(raw_gsc))},
        operation="project_excel",
        target_excel_sheet="on_page_audit",
        rows_written=0,    # GSC contributed cross-ref, not new rows
    )
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "on_page_audit_rows": str(len(on_page_audit_rows)),
    "credits_used":       str(estimate),
    "report_path":        str(report_path),
    "raw_dfs":            str(inbox_path),
    "raw_gsc":            str(gsc_inbox) if use_gsc_cross_ref else "",
})
```

## URL canonicalization (D-03 invariant)

Every URL passing through this skill is normalized via
`scripts.discovery.on_page_audit_transform._normalize_url`. The function
is **idempotent**: `_normalize_url(_normalize_url(u)) == _normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports
(:80/:443), strip trailing slash (root excluded), drop fragment, drop
tracking params (utm_*, gclid, fbclid, mc_*, msclkid), sort remaining
query keys.

Canonicalization is applied to BOTH the DFS URL field AND the GSC URL
field (`keys[0]`) before the cross-source join, so a trailing slash or
a fragment cannot desync the merge. See
`schemas/cross-sheet-invariants.json#D-03` for the project-wide rule.

## DURUR conditions (9)

Stop and flag the manager — do not patch, do not fall back.

1. `check_budget.py --check` exit 1 (or `preflight_budget()` raises
   `BudgetExceededError`) → STOP, awaiting_approval; never silently
   skip the paid call.
2. DFS `on_page_content_parsing` payload has schema drift (item missing
   `title`, `meta_description`, or `h1`) → `ContentParsingDriftError`.
3. `inbox/dfs/` (or `inbox/gsc/`) path cannot be created (workspace
   path missing or non-writable).
4. Cross-source URL normalization mismatch: DFS and GSC URL sets are
   disjoint after D-03 normalization. **Default behaviour:** graceful
   fall-back to no-cross-ref mode (every row → `target_query=""`,
   action=`"no GSC available for this URL"`) and the run logs an
   explicit `cross_ref_mismatch=true` flag. **Strict mode**
   (`strict_cross_ref=true`): raise `CrossRefMismatchError` and stop —
   used when the operator wants to surface upstream drift loudly
   (e.g. www-vs-non-www host mismatch) rather than emit silent zeros.
5. `master.xlsx#on_page_audit` column count or names don't match
   `schemas/master-excel.schema.json#on_page_audit` (8 cols).
6. `transaction.append` raises `RowSchemaError` for `on_page_audit`.
7. `workflow_runner.create_run` fails schema validation.
8. `PSEO_WORKSPACE_ROOT` env unset and no explicit `workspace_root` arg
   passed to `workflow_runner` / `events_writer`.
9. Optional GSC call invoked but fails (auth/network/scope) →
   **non-fatal**: graceful degrade to no-cross-ref mode. Action column
   says `"no GSC available for this URL"`. The skill DOES NOT stop —
   the DFS audit is still actionable on its own. (Documented design
   choice; the operator sees the degraded mode in the report.)

## Cross-references

- Schemas: `schemas/master-excel.schema.json#on_page_audit` (8 cols),
  `schemas/events.schema.json` (`source.kind=dataforseo_mcp` +
  `gsc_mcp`, `cost.credits` field, `target_excel_sheet=on_page_audit`),
  `schemas/skill-frontmatter.schema.json` (this frontmatter),
  `schemas/cross-sheet-invariants.json#D-03` (URL canonicalization),
  `schemas/dataforseo-endpoint-mapping.schema.json` (DFS contract;
  `cost.credits_per_call` for `on_page_content_parsing`).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/budget/check_budget.py`, `scripts/reporting/render_template.py`.
- Transform: `scripts/discovery/on_page_audit_transform.py`
  (`_normalize_url`, `transform`, `estimate_credits`,
  `preflight_budget`, `OnPageAuditError`, `ContentParsingDriftError`,
  `BudgetExceededError`, `CrossRefMismatchError`).
- Tests: `tests/skills/test_on_page_audit.py` (≥10 cases incl. URL
  normalization edge cases, action heuristic coverage, budget
  pre-flight integration, cross-ref mismatch, schema drift DURUR).
- Template: `templates/reports/on-page-audit.template.md`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises explicitly; only the
      documented graceful-degrade modes (DURUR #4 default, #9) carry on.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7;
      `master-excel.schema.json#on_page_audit` defines the 8-col contract.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] Budget pre-flight integration — `scripts.budget.check_budget`
      invoked at step 1 BEFORE any paid DFS call (paid-MCP gate).
- [x] Append-only — all events via `events_writer`; raw inbox JSON is
      write-once per (date, slug, tool).
- [x] Cross-module IMPORT discipline — `workflow_runner` /
      `transaction` / `events_writer` / `check_budget` are imported,
      never modified from this skill.
- [x] D-03 URL canonicalization applied BOTH sides of the cross-source
      join (DFS + GSC).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
