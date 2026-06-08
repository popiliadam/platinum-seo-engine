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
status: active
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
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
  use_sf_mcp_live:
    type: boolean
    required: false
    default: false
    description: "Opt-in (D-SF-11): when true, calls SF MCP via scripts/util/sf_mcp_client.SfMcpClient for live page_titles_all cross-check (title/meta/h1 freshness vs SF crawl truth). Resolves the crawl id from sf_list_crawls (domain match → instanceDirName), client.load_crawl(...) (resilient), then exports page_titles_all + meta_description_all + h1_all via SF_EXPORT_DISPATCH (sf_export_seo_element_urls), merged per-URL by Address, to file_path (the >100KB inline cap is resolved by writing to disk, not a non-existent 'truncated' flag; live-verified the Page Titles export has only Title columns, so meta/h1 presence must come from their own exports). Each seo-element export is NDJSON → converted via sf_crawl_orchestrator.ndjson_to_csv → csv.DictReader → transform(live_findings=...) (additive crawl-truth merge for SF-only URLs). Requires SF GUI + MCP server running (preflight via client.health(); on FAIL / no matching crawl / SfMcpToolError / load timeout → AMBER fallback to file-based path, NEVER hard fail per R9)."
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
    - "mcp__sf__sf_list_crawls"
    - "mcp__sf__sf_load_crawl"
    - "mcp__sf__sf_export_seo_element_urls"
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
    project_config_path=project_root / "project.config.json",
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
gsc_inbox.parent.mkdir(parents=True, exist_ok=True)  # DURUR #3 path-creation parity with Step 2
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

Single `committer.commit` call for the on_page_audit sheet (8 cols) — the
orchestrator's idempotent commit path (whole-block `transaction.replace`
from the schema's `data_start_row`, so re-running never duplicates rows on
the `on_page_audit` snapshot sheet). Goes through the single approved write
path (backup, lock, schema validation, post-write provenance event emission).

```python
from scripts.orchestration import committer
committer.commit(
    workspace_root/"projects"/project_slug/"master.xlsx",
    "on_page_audit",
    on_page_audit_rows,
    run_id=handle.run_id,
    project_slug=project_slug,
    writer="on-page-audit",
)
```

### Step 8 — `render_report`

`render_template.py templates/reports/on-page-audit.template.md data.json`
→ `outputs/reports/{date}-on-page-audit.md`. Variables (all 19 the
template references — render hard-fails on any missing):
`$project_slug`, `$date`, `$run_id`, `$url_count`, `$credits_used`,
`$rows_on_page_audit`, `$action_monitor`, `$action_add_meta_h1`,
`$action_rewrite`, `$action_patch`, `$action_no_gsc`, `$top_url`,
`$top_target_query`, `$top_action`, `$top_clicks`, `$top_impressions`,
`$raw_dfs_path`, `$raw_gsc_path`, `$report_summary`.

### Step 9 — Provenance event

One event per upstream call. The DFS event carries `cost.credits`; the
GSC event omits cost.

```python
from scripts.state import events_writer
# run_id=None auto-allocates race-free; reuse the returned id so the optional
# GSC cross-ref event below is grouped under the same on-page-audit run.
op_run = events_writer.append_provenance(
    project_id=project_slug,
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
        run_id=op_run.run_id,    # same run as the on_page_content_parsing event
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

## SF MCP Live Mode (Optional, `use_sf_mcp_live=true` — D-SF-11)

**Default: `use_sf_mcp_live=false`** — DFS `on_page_content_parsing` is
the canonical on-page evidence source (paid; required tool). The SF MCP
live cross-check is opt-in only and gated by a `client.health()`
preflight; on probe failure the run AMBER-warns and continues without
the SF cross-check (never hard-fail per R9 mitigation).

When `use_sf_mcp_live=true`, the SKILL body branches at Step 4
(`transform`) to optionally cross-check the per-URL title/meta/h1
signals against SF MCP's `page_titles_all` report.

**This branch was rewritten (AC-13 replication) against the REAL SF MCP
API** — the same class of fix as tech-audit (landed in `6ee6fb9`,
live-proven on the aluminumstation crawl) and the sf-crawl-orchestrator
Step-5 export dispatch (`a714e43`). The engine canonical `page_titles_all`
is NOT a Screaming Frog identifier: it maps via
`sf_crawl_orchestrator.SF_EXPORT_DISPATCH` to the real
`sf_export_seo_element_urls` tool with `seo_element_name="Page Titles"` +
`filter_name="All"`. There is NO `crawl_id`, `report_name`, or
`save_report` arg; the export runs on the *currently-loaded* crawl and is
written to `file_path` (relative to the SF allowed base directory). The
real SF REJECTS inline output >100KB with a tool error — so `file_path`
(write-to-disk) is the canonical export path (OQ-FILEPATH-EXPORTS), not a
non-existent `truncated` flag.

The `sf_list_crawls` result comes back through `SfMcpClient.call_tool`
as the MCP content envelope `{"isError":false,"content":[{"text":
"<JSON>"}]}`, so the crawl list is JSON-encoded inside `content[*].text`
(exactly like `sf_crawl_progress`). We decode the first JSON block, then
match on `url` → `instanceDirName`. The real entry shape (Manager-probed)
is `{"url":"https://aluminumstation.com/","instanceDirName":"fc718e3f-..."}`.

**Critical: a seo-element export is NDJSON, not CSV.**
`sf_export_seo_element_urls` has no `export_type` arg and always writes
one flat JSON object per line (live-verified — `export_returns_ndjson`
semantics). So the written file is converted to CSV text first via
`sf_crawl_orchestrator.ndjson_to_csv(...)` (which emits a clean CSV
header — no BOM), then parsed with `csv.DictReader` and passed into the
transform's additive `live_findings` merge. The merge adds an SF
crawl-truth row for every URL the DFS content_parsing set did NOT cover
(DFS-covered URLs are never duplicated — `rowcount(with) >=
rowcount(without)`); `live_findings=None` (the default) is byte-identical
to the file-based path.

```python
import csv
import json
from pathlib import Path
from scripts.ingestion import sf_crawl_orchestrator

def _decode_sf_envelope(result: dict):
    """Decode the first JSON payload from an SfMcpClient content envelope.

    SfMcpClient.call_tool returns {"isError":..,"content":[{"text":"<JSON>"}]}.
    Returns the parsed object (list/dict) or None if no JSON block is present.
    """
    for block in (result or {}).get("content", []) or []:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            try:
                return json.loads(block["text"])
            except ValueError:
                continue
    return None

def _norm_domain(u: str) -> str:
    """Normalise a URL for domain matching: drop scheme + leading www. +
    trailing slash."""
    bare = (u or "").strip().rstrip("/").split("://", 1)[-1].lower()
    return bare[4:] if bare.startswith("www.") else bare

amber_warnings: list[str] = []
live_findings: list[dict] = []   # parsed SF "Page Titles" rows (crawl truth)
if use_sf_mcp_live:
    from scripts.util.sf_mcp_client import (
        SfMcpClient, SfMcpToolError, SfMcpError,
    )
    sf_cfg = project_config["sf"]["mcp"]
    client = SfMcpClient(base_url=sf_cfg["url"])
    allowed_dir = Path(sf_cfg["allowed_directory"])  # SF write base (D-SF-10)
    if not client.health():
        # R9 AMBER fallback — SF MCP unreachable, continue without the SF
        # cross-check (DFS evidence is still authoritative).
        amber_warnings.append(
            "SF MCP unavailable (health probe failed); "
            "falling back to file-based path"
        )
    else:
        try:
            # 1) Resolve the crawl id: pick the crawl whose `url` matches the
            #    project domain (normalise scheme + leading www. + trailing
            #    slash), then take its `instanceDirName` (the real crawl id).
            list_resp = client.call_tool("sf_list_crawls")
            decoded = _decode_sf_envelope(list_resp)
            crawls = decoded if isinstance(decoded, list) else (
                decoded.get("crawls", []) if isinstance(decoded, dict) else []
            )
            target = _norm_domain(project_config["domain"])
            match = next(
                (c for c in crawls if _norm_domain(c.get("url", "")) == target),
                None,
            )
            if match is None:
                # R9 AMBER fallback — no crawl for this domain; do NOT hard fail.
                amber_warnings.append(
                    f"No SF crawl found for domain {project_config['domain']!r} "
                    "in sf_list_crawls; falling back to file-based path"
                )
            else:
                crawl_id = match["instanceDirName"]
                # 2) Ensure it is the active loaded crawl (resilient: tolerates
                #    the client-side load timeout, polls progress to confirm).
                client.load_crawl(crawl_id)

                # 3) Export the THREE on-page seo-element reports via the
                #    orchestrator dispatch — Page Titles + Meta Description + H1.
                #    page_titles_all carries ONLY 'Title 1' columns (live-verified
                #    2026-06-02: the Page Titles export has NO 'Meta Description 1'
                #    / 'H1-1' columns), so in_meta / in_h1 presence MUST come from
                #    their own exports — else every SF-only URL would be falsely
                #    flagged missing-meta / missing-h1. The >100KB inline cap is
                #    resolved by writing each to file_path.
                # 4) Each seo-element export is NDJSON (no export_type arg) →
                #    convert to clean CSV (ndjson_to_csv emits a BOM-free header)
                #    → DictReader → merge each export's columns per URL (Address).
                by_url: dict[str, dict] = {}
                for canonical, rel_path in (
                    ("page_titles_all", "page_titles_all.ndjson"),
                    ("meta_description_all", "meta_description_all.ndjson"),
                    ("h1_all", "h1_all.ndjson"),
                ):
                    tool, call_kwargs = sf_crawl_orchestrator.SF_EXPORT_DISPATCH[
                        canonical
                    ]
                    client.call_tool(tool, file_path=rel_path, **call_kwargs)
                    csv_text = sf_crawl_orchestrator.ndjson_to_csv(
                        (allowed_dir / rel_path).read_text(encoding="utf-8")
                    )
                    for row in csv.DictReader(csv_text.splitlines()):
                        addr = (row.get("Address") or "").strip()
                        if addr:
                            by_url.setdefault(addr, {"Address": addr}).update(row)
                live_findings = list(by_url.values())
        except (SfMcpToolError, SfMcpError) as exc:
            # R9 AMBER fallback — list/load/export failed (4xx/5xx, JSON-RPC
            # error, load_crawl settle timeout). NEVER hard fail.
            amber_warnings.append(
                f"SF MCP error: {exc}; falling back to file-based path"
            )

# Pass the parsed rows into the transform's additive merge (default
# None / [] → byte-identical file-based behaviour; DFS stays authoritative
# and SF-only URLs are surfaced as crawl-truth cross-check rows).
result = on_page_audit_transform.transform(
    raw_content_parsing,
    raw_gsc=raw_gsc,
    live_findings=(live_findings or None),
)
```

**AMBER vs RED policy (R9 contract — never hard-fail this branch):**

- `client.health()` returns False → AMBER warning, continue without
  the SF cross-check (DFS evidence remains the on_page_audit truth).
- No crawl matches the project domain in `sf_list_crawls` → AMBER
  warning, continue without SF.
- `SfMcpToolError` / `SfMcpError` raised (export 4xx/5xx, JSON-RPC error,
  `load_crawl` settle timeout) → AMBER warning, continue without SF.
- The transform tolerates an empty / absent `live_findings` gracefully
  (no extra rows), so any partial SF outage degrades to the DFS-only
  result with `rowcount(with) >= rowcount(without)` preserved.
- NEVER raise `SystemExit` from this branch. RED reserved for the
  existing DURUR set (budget, DFS schema drift, etc.).

**Tool naming reminder:** `call_tool(tool_name=...)` takes the **native**
SF MCP tool name (`"sf_export_seo_element_urls"`, `"sf_list_crawls"`,
`"sf_load_crawl"`), NOT the registry form
(`"sf__sf_export_seo_element_urls"`) or the Claude Code wrapper form
(`"mcp__sf__sf_export_seo_element_urls"`). JSON-RPC `params.name` follows
the native form per MCP spec. `SfMcpClient` already speaks the MCP
Streamable-HTTP transport (session handshake + SSE), so the body only
ever passes native tool names + the SF call kwargs.

`amber_warnings` is surfaced via the existing provenance event
(an additional `source.kind=sf_mcp` event is emitted alongside the
DFS+GSC events at Step 9). It is NOT a report template variable — the
on-page-audit template renders no `$amber_warnings` field.

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
