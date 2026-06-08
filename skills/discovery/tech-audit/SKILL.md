---
name: tech-audit
description: |
  Use when: kullanıcı "teknik SEO audit", "lighthouse skoru", "core web
  vitals", "LCP / CLS / FCP düşür", "page speed", "performans audit",
  "title meta H1 kontrol", "structured data eksik mi", "tech seo issues",
  "site hızı problemleri" der ya da /pseo-tech-audit çağırır. DFS HEAVY
  ingestion (paid MCP); budget pre-flight ZORUNLU.
  Also use when: aktif projenin URL listesi config'te tanımlı; Phase 7
  Wave 1 discovery; on_page_lighthouse + on_page_content_parsing tier
  çalıştırılacak; bulgular master.xlsx#tech_seo'ya schema-locked 6-kolon
  formatta yazılacak.
  Do not use when: GSC veri ingestion (gsc-pull), SF csv ingestion
  (sf-import), keyword research (dfs-pull), quick-wins fırsat skoru,
  cannibalization, content decay analizi gerekiyor — ayrı skill'ler.
  Master.xlsx yokken çağırma; init-project önce çalışmalı (DURUR #6).
  Budget pre-flight FAIL ise asla bypass etme — workflow_runner
  awaiting_approval state'ine route et (DURUR #1).
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
    description: "Audit edilecek URL listesi. Plugin-agnostik — slug literal yok; project-config'den geliyor."
  url_cap:
    type: integer
    required: false
    default: 50
    description: "DoS prevention; üstüne çıkılırsa DURUR #3. project-config'de override edilebilir."
  device:
    type: string
    required: false
    default: "desktop"
    description: "Lighthouse cihaz profili (desktop|mobile)."
  use_sf_mcp_live:
    type: boolean
    required: false
    default: false
    description: "Opt-in (D-SF-11): when true, calls SF MCP via scripts/util/sf_mcp_client.SfMcpClient to enrich tech_seo with the live SF 'Issues Overview' report before the transform aggregates. Resolves the crawl id from sf_list_crawls (domain match → instanceDirName), client.load_crawl(...) (resilient), then exports issues_overview_report via SF_EXPORT_DISPATCH (sf_generate_report category 'Issues Overview', export_type CSV) to file_path (the >100KB inline cap is resolved by writing to disk, not a non-existent 'truncated' flag), parses the CSV with csv.DictReader → transform(..., live_findings=...). Requires SF GUI + MCP server running (preflight via client.health(); on FAIL / no matching crawl / SfMcpToolError / load timeout → AMBER fallback to file-based path, NEVER hard fail per R9)."
outputs:
  - "master.xlsx#tech_seo"
  - "outputs/reports/{date}-tech-audit.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-lighthouse-{slug}.json"
  - "inbox/dfs/{date}-content_parsing-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "sf-import:master.xlsx#crawl_sitemap"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-tech-audit"]
  natural_language: |
    "tech seo audit", "lighthouse skoru", "core web vitals", "LCP düşür",
    "CLS yüksek", "FCP yavaş", "title meta H1 kontrol", "structured data
    eksik", "site hızı problemleri", "performans audit"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__on_page_lighthouse"
    - "mcp__dataforseo__on_page_content_parsing"
  optional:
    - "mcp__dataforseo__on_page_instant_pages"
    - "mcp__sf__sf_list_crawls"
    - "mcp__sf__sf_load_crawl"
    - "mcp__sf__sf_generate_report"
budget:
  uses_paid_mcp: true
  estimated_credits: 13
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# tech-audit — discovery skill (Phase 7 Wave 1, DFS HEAVY)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline + §16.8 budget pre-flight + ADR-016
cost-tracking. Raw JSON drift recovery is mandatory: every DFS response
is dropped into `inbox/dfs/` *before* any transform runs, so a transform
bug never costs us the upstream payload (which is paid; re-fetch costs
credits — and Lighthouse is the most expensive on_page endpoint at up
to 10 credits per URL).

This skill mirrors the Phase 6 `dfs-pull` 10-step shape verbatim and
adapts the Phase 5 `quick-wins` discovery aggregation pattern to the
6-column tech_seo schema. Reuse the structure; deviate only with an ADR.

## Inputs (frontmatter contract)

| Name           | Type    | Default     | Notes                                                         |
|----------------|---------|-------------|---------------------------------------------------------------|
| `project_slug` | string  | —           | Required. Resolves `projects/{slug}/master.xlsx`.             |
| `urls`         | array   | —           | Required. URL list — drives credit cost AND DoS cap.          |
| `url_cap`      | integer | 50          | DoS prevention; raise via project-config or arg if needed.    |
| `device`       | string  | "desktop"   | `desktop` or `mobile` Lighthouse profile.                     |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#tech_seo` — schema-locked 6 cols
  (`issue_category | detail | affected_urls | impact | resolution | priority`).
  `impact` is severityEnum (CRITICAL/HIGH/MEDIUM/LOW); `priority` is
  P0/P1/P2 (CRITICAL+HIGH→P0, MEDIUM→P1, LOW→P2).
- `projects/{slug}/outputs/reports/{date}-tech-audit.md` — human-readable
  summary (perf score histogram + per-category top issues).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance` entries
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=tech_seo`,
  `cost.credits` populated per ADR-016 — every DFS call adds an event).
- `projects/{slug}/inbox/dfs/{date}-lighthouse-{slug}.json` — raw
  Lighthouse payload (drift recovery; per-URL bundle).
- `projects/{slug}/inbox/dfs/{date}-content_parsing-{slug}.json` — raw
  on_page_content_parsing payload.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `preflight_budget` (§16.8 + ADR-016, MANDATORY before any DFS call)

The skill MUST estimate credits BEFORE any paid MCP call and run
`scripts/budget/check_budget.py` against the project's 24h running total.
Estimate formula:

```
estimated_credits = url_count * 10  (lighthouse, conservative MAX of 5-10)
                  + url_count * 3   (content_parsing, conservative MAX of 2-3)
                  = url_count * 13
```

Invocation (subprocess; the script is the SSoT for budget arithmetic per
ADR-016):

```python
from scripts.discovery import tech_audit_transform
estimate = tech_audit_transform.estimate_credits(len(urls))
envelope = tech_audit_transform.preflight_budget(
    estimated_credits=estimate,
    project_config_path=project_root / "project.config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
```

Exit code 0 (or `envelope["exceeded"] is False`) → proceed.
Exit code 1 OR projected_used > budget → `BudgetExceededError`.
The skill MUST then route the workflow to `awaiting_approval`:

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"Budget pre-flight FAIL: estimated={estimate} credits would "
            f"exceed daily cap. Approve override?",
    step_index=0,
)
# Skill exits here. Manager surface → §10.
```

NEVER silently downgrade the estimate or skip the check (DURUR #1).

### Step 2 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="tech-audit",
    project_slug=project_slug,
    steps=[
        {"name": "preflight_budget"},
        {"name": "fetch_lighthouse"},
        {"name": "fetch_content_parsing"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 3 — `fetch_lighthouse` (MCP §16.5 step 3 — raw inbox first)

Per-URL fan-out OR batched call (depends on wrapper); persist the FULL
response set into `inbox/dfs/` BEFORE any transform runs. ADR-016
requires per-call cost tracking, so each Lighthouse call also emits a
provenance event with `cost.credits` populated:

```python
workflow_runner.start_step(handle.run_id, 1, project_slug=project_slug)
raw_lighthouse = mcp__dataforseo__on_page_lighthouse(
    target=urls,
    for_mobile=(device == "mobile"),
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-lighthouse-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw_lighthouse, ensure_ascii=False, indent=2))

events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__on_page_lighthouse",
            "response_bytes": len(json.dumps(raw_lighthouse))},
    operation="ingest",
    target_excel_sheet=None,             # ingest: no Excel write yet
    rows_written=0,
    cost={"provider": "dataforseo",
          "credits": float(len(urls) * 10),   # conservative MAX
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
workflow_runner.finish_step(handle.run_id, 1, project_slug=project_slug,
                            output_ref=str(inbox_path))
```

If the wrapper auth/networking fails → DURUR #2.

### Step 4 — `fetch_content_parsing`

Same shape as step 3, against `mcp__dataforseo__on_page_content_parsing`.
Per-call cost = `len(urls) * 3` credits (conservative MAX). Persist to
`inbox/dfs/{date}-content_parsing-{slug}.json` and emit a provenance
event with `cost.credits` populated.

### Step 5 — `transform` (pure compute, severityEnum strict)

```bash
python3 scripts/discovery/tech_audit_transform.py \
    --lighthouse      inbox/dfs/{date}-lighthouse-{slug}.json \
    --content-parsing inbox/dfs/{date}-content_parsing-{slug}.json \
    --url-cap         50 \
    --output-dir      _state/transform/{run_id}/
```

The transform applies the `_normalize_dfs_response` shape adapter (REST
envelope OR flat wrapper — same pattern as `dfs_pull.py`), validates
each item against the upstream schema (DURUR #4 / #5 on drift), then
runs the per-URL findings rules:

| Signal                     | Threshold        | Severity | Category           |
|----------------------------|------------------|----------|--------------------|
| Performance score          | < 50             | HIGH     | Performance        |
| LCP                        | > 2.5s           | MEDIUM   | Performance        |
| FCP                        | > 1.8s           | LOW      | Performance        |
| CLS                        | > 0.1            | MEDIUM   | Layout Stability   |
| Title length               | > 60 chars       | LOW      | Meta Tags          |
| Meta description missing   | empty            | MEDIUM   | Meta Tags          |
| Meta description length    | > 160 chars      | MEDIUM   | Meta Tags          |
| H1 count                   | != 1             | MEDIUM   | Headings           |
| Structured data absent     | commercial page  | LOW      | Structured Data    |

Findings are aggregated per `issue_category`; `impact` = max severity
across that category's findings; `priority` = P0/P1/P2 mapping.
`affected_urls` is comma-joined (capped at ~480 chars; collapses to
"N URLs (sample: ...)" past the cap).

### Step 6 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(rows)} tech_seo finding kategorisi tespit edildi, "
            f"master.xlsx#tech_seo'ya yazalım mı?",
    step_index=4,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 7 — Resume (`approve` → continue)

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug,
                        approver="user")
```

### Step 8 — `write_excel` (atomic, schema-validated)

One `transaction.append` call. Schema validation (RowSchemaError →
DURUR #8) happens inside the transaction; the transform also runs a
defensive `_validate_row` pass before returning, so drift is caught
twice.

```python
from scripts.excel import transaction
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="tech_seo",
    rows=tech_seo_rows,
    project_slug=project_slug,
    writer="tech-audit",
)
```

### Step 9 — `render_report` + final provenance event

`render_template.py templates/reports/tech-audit.template.md data.json`
→ `outputs/reports/{date}-tech-audit.md`.

Final provenance event (Excel-write phase) — links the project_excel
operation to the tech_seo target sheet and carries the SUM of credits
billed across both DFS calls (per ADR-016 the cost field MUST be
populated):

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__on_page_lighthouse+content_parsing",
            "response_bytes": len(json.dumps(raw_lighthouse))
                              + len(json.dumps(raw_content_parsing))},
    operation="project_excel",
    target_excel_sheet="tech_seo",
    rows_written=len(tech_seo_rows),
    cost={"provider": "dataforseo",
          "credits": float(len(urls) * 13),
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "tech_seo_rows": str(len(tech_seo_rows)),
    "lighthouse_url_count": str(meta["lighthouse_url_count"]),
    "content_parsing_url_count": str(meta["content_parsing_url_count"]),
    "credits_used": str(len(urls) * 13),
    "report_path": str(report_path),
    "raw_jsons": ";".join([str(lh_inbox), str(cp_inbox)]),
})
```

## SF MCP Live Mode (Optional, `use_sf_mcp_live=true` — D-SF-11)

**Default: `use_sf_mcp_live=false`** — file-based ingestion path is the
canonical contract (1184+ pytest regression baseline). MCP is augmentation,
not replacement. The flag is opt-in only and gated by a `client.health()`
preflight; on probe failure the run AMBER-warns and continues file-based
(never hard-fail per R9 mitigation).

When `use_sf_mcp_live=true`, the SKILL body branches at Step 5 (transform)
to optionally enrich the tech_seo rows with the live SF "Issues Overview"
report before the transform aggregates per `issue_category`.

**This branch was rewritten (AC-13) against the REAL SF MCP API** — the
same class of fix as the sf-crawl-orchestrator Step-5 export dispatch
(landed in `a714e43`, live-proven on the demo-aluminum 1822-URL crawl).
The engine canonical `issues_overview_report` is NOT a Screaming Frog
identifier: it maps via `sf_crawl_orchestrator.SF_EXPORT_DISPATCH` to the
real `sf_generate_report` tool with `category="Issues Overview"` +
`export_type="CSV"`. There is NO `crawl_id`, `report_name`, or
`save_report` arg; the report runs on the *currently-loaded* crawl and is
written to `file_path` (relative to the SF allowed base directory). The
real SF REJECTS inline output >100KB with a tool error — so `file_path`
(write-to-disk) is the canonical export path (OQ-FILEPATH-EXPORTS), not a
non-existent `truncated` flag. issues_overview is small (~43 rows on
demo-aluminum) so it would fit inline, but `file_path` is the safe
canonical path regardless and matches the orchestrator dispatch contract.

The `sf_list_crawls` result comes back through `SfMcpClient.call_tool` as
the MCP content envelope `{"isError":false,"content":[{"text":"<JSON>"}]}`,
so the crawl list is JSON-encoded inside `content[*].text` (exactly like
`sf_crawl_progress`). We decode the first JSON block, then match on
`url` → `instanceDirName`. The real entry shape (Manager-probed) is
`{"url":"https://demo-aluminum.example/","instanceDirName":"fc718e3f-..."}`.

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
    """Normalise a URL for domain matching: drop scheme + trailing slash."""
    return (u or "").strip().rstrip("/").split("://", 1)[-1].lower()

amber_warnings: list[str] = []
live_findings: list[dict] = []   # parsed SF "Issues Overview" CSV rows
if use_sf_mcp_live:
    from scripts.util.sf_mcp_client import (
        SfMcpClient, SfMcpToolError, SfMcpError,
    )
    sf_cfg = project_config["sf"]["mcp"]
    client = SfMcpClient(base_url=sf_cfg["url"])
    allowed_dir = Path(sf_cfg["allowed_directory"])  # SF write base (D-SF-10)
    if not client.health():
        # R9 AMBER fallback — SF MCP unreachable, continue file-based.
        amber_warnings.append(
            "SF MCP unavailable (health probe failed); "
            "falling back to file-based path"
        )
    else:
        try:
            # 1) Resolve the crawl id: pick the crawl whose `url` matches the
            #    project domain (normalise scheme + trailing slash), then take
            #    its `instanceDirName` (the real saved-crawl id).
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

                # 3) Export "Issues Overview" via the orchestrator dispatch
                #    (issues_overview_report → ("sf_generate_report",
                #    {"category":"Issues Overview","export_type":"CSV"})). The
                #    >100KB inline cap is resolved by writing to file_path.
                tool, call_kwargs = sf_crawl_orchestrator.SF_EXPORT_DISPATCH[
                    "issues_overview_report"
                ]
                rel_path = "tech_audit_issues_overview.csv"
                client.call_tool(tool, file_path=rel_path, **call_kwargs)

                # 4) Read the written CSV from the SF allowed base dir and parse
                #    it into live_findings rows. issues_overview is a REPORT →
                #    CSV already (no NDJSON conversion). If a future enrichment
                #    wires a seo-element export instead, run
                #    sf_crawl_orchestrator.ndjson_to_csv(...) first (that tool
                #    has no export_type arg and always emits NDJSON).
                csv_path = allowed_dir / rel_path
                # utf-8-sig strips SF's leading BOM so csv.DictReader's first
                # key is clean "Issue Name" (not '﻿"Issue Name"'); the transform
                # also normalizes keys defensively (live-caught 2026-06-02).
                with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
                    live_findings = list(csv.DictReader(fh))
        except (SfMcpToolError, SfMcpError) as exc:
            # R9 AMBER fallback — list/load/export failed (4xx/5xx, JSON-RPC
            # error, load_crawl settle timeout). NEVER hard fail.
            amber_warnings.append(
                f"SF MCP error: {exc}; falling back to file-based path"
            )

# Pass the parsed rows straight into the transform (default [] / None →
# byte-identical file-based behaviour). The transform merges them
# additively into the per-issue_category tech_seo aggregation.
result = tech_audit_transform.transform(
    lighthouse_raw=raw_lighthouse,
    content_parsing_raw=raw_content_parsing,
    url_cap=url_cap,
    live_findings=(live_findings or None),
)
```

**AMBER vs RED policy (R9 contract — never hard-fail this branch):**

- `client.health()` returns False → AMBER warning, continue file-based.
- No crawl matches the project domain in `sf_list_crawls` → AMBER
  warning, continue file-based.
- `SfMcpToolError` / `SfMcpError` raised (export 4xx/5xx, JSON-RPC error,
  `load_crawl` settle timeout) → AMBER warning, continue file-based.
- The transform tolerates an empty / absent `live_findings` gracefully
  (no extra rows), so any partial SF outage degrades to the file-based
  result with `rowcount(with) >= rowcount(without)` preserved.
- NEVER raise `SystemExit` from this branch. RED is reserved for the
  existing DURUR set (budget, schema drift, etc.).

**Tool naming reminder (per Manager dispatch):** `call_tool(tool_name=...)`
takes the **native** SF MCP tool name (`"sf_generate_report"`,
`"sf_list_crawls"`, `"sf_load_crawl"`), NOT the registry form
(`"sf__sf_generate_report"`) or the Claude Code wrapper form
(`"mcp__sf__sf_generate_report"`). JSON-RPC `params.name` follows the
native form per MCP spec. `SfMcpClient` already speaks the MCP
Streamable-HTTP transport (session handshake + SSE), so the body only
ever passes native tool names + the SF call kwargs.

`amber_warnings` is surfaced via the existing provenance event payload
(Step 9 — `events_writer.append_provenance` accepts a `notes` field
when present) and the rendered report (Step 9 — render_template
template variable `$amber_warnings`).

## Issue detection rules — severityEnum coverage

Every emitted row's `impact` is one of `{CRITICAL, HIGH, MEDIUM, LOW}`
(strict — see `tech_audit_transform.SEVERITY_ENUM` and
`schemas/master-excel.schema.json` `$defs/severityEnum`).

CRITICAL is reserved for findings the rule set does not currently emit
(e.g. site-wide outage, robots.txt blocks all). HIGH/MEDIUM/LOW are the
active emission tiers — they map to P0/P1/P2 priority via
`_PRIORITY_BY_SEVERITY`.

## DURUR conditions (10)

Stop and flag the manager — do not patch, do not fall back.

1. **Budget pre-flight FAIL** (`check_budget.py` exit 1 OR
   `projected_used > budget`) → `BudgetExceededError` → workflow routed
   to `awaiting_approval` per spec §10. NEVER silently downgrade.
2. `mcp__dataforseo__on_page_lighthouse` or
   `mcp__dataforseo__on_page_content_parsing` returns auth/network/scope
   error → STOP.
3. **DoS prevention**: URL list count > `url_cap` (default 50) →
   `URLCapExceededError`. Surface to manager; manager raises cap or
   splits the run.
4. Lighthouse response schema drift (e.g. `categories.performance.score`
   field renamed, `audits` block missing) → `LighthouseSchemaDriftError`.
5. `content_parsing` response schema drift (meta block missing AND
   page_content missing AND no flat title) →
   `ContentParsingSchemaDriftError`.
6. `inbox/dfs/` path cannot be created (workspace path missing /
   read-only).
7. tech_seo column count or names mismatch the schema-locked
   `TECH_SEO_COLUMNS` tuple → `RowSchemaError` (defensive — should never
   fire for module-built rows; fires if a future patch adds a column
   without updating the schema).
8. `transaction.append` raises `RowSchemaError` (severityEnum violation,
   row column drift).
9. `workflow_runner.create_run` fails schema validation
   (workflow-run.schema.json).
10. `PSEO_WORKSPACE_ROOT` env unset and no `workspace_root` arg passed.

## Awaiting-approval state path (Budget DURUR routing, ADR-016)

When DURUR #1 fires the skill MUST:

1. Catch `BudgetExceededError` raised by `preflight_budget()`.
2. `workflow_runner.request_approval(...)` with the budget envelope
   serialized into the `subject` (so manager sees projected vs cap).
3. EXIT — do NOT continue to step 3. The workflow state is now
   `awaiting_approval` and the manager session decides between
   (a) raise `dataforseo.budget_credits_per_day` in project-config,
   (b) split the URL list and re-run, (c) defer the audit.

This contract is identical to `dfs-pull` and is the convention for all
paid-MCP discovery skills (Phase 7+).

## Cross-references

- Schemas: `schemas/master-excel.schema.json` (tech_seo sheet, 6 cols;
  severityEnum $defs), `schemas/events.schema.json`
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=tech_seo`,
  `cost.credits` per ADR-016), `schemas/skill-frontmatter.schema.json`
  (this frontmatter), `schemas/dataforseo-endpoint-mapping.schema.json`
  (DFS contract; cost.credits_per_call).
- Cross-modules (IMPORT-only, not modified): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/budget/check_budget.py`, `scripts/reporting/render_template.py`.
- Transform: `scripts/discovery/tech_audit_transform.py`
  (`_normalize_dfs_response`, `estimate_credits`, `preflight_budget`,
  `transform`, severity/category constants, exception hierarchy).
- Tests: `tests/skills/test_tech_audit.py` (≥10 cases incl. budget
  pre-flight mock + DoS cap + lighthouse/content-parsing schema drift +
  severityEnum coverage).
- Template: `templates/reports/tech-audit.template.md`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7;
      tech_seo rows validate against `master-excel.schema.json` 6 cols.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; verified by the forbidden-slug regex grep documented
      in the worker brief (0-tolerance gate).
- [x] Budget pre-flight integration — `scripts.budget.check_budget`
      invoked via subprocess at step 1 BEFORE any paid call (ADR-016
      SSoT for cost arithmetic).
- [x] Append-only — all events via `events_writer`; per-DFS-call
      provenance event carries `cost.credits` (ADR-016).
- [x] Cross-module IMPORT discipline — `workflow_runner` /
      `events_writer` / `check_budget` are imported (subprocess for
      check_budget; module reuse pattern from dfs-pull).
      `scripts.excel.transaction` is called only from the SKILL
      orchestrator at step 8 — the transform module never imports it.
- [x] severityEnum strict — every emitted row's `impact` is in
      {CRITICAL, HIGH, MEDIUM, LOW}; defensive `_validate_row` runs
      twice (transform + transaction.append).
- [x] DoS prevention — URL count capped at `url_cap` (default 50);
      `URLCapExceededError` is DURUR #3.
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
