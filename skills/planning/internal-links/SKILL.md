---
name: internal-links
description: |
  Use when: kullanıcı "internal links", "iç linkleme", "orphan page",
  "kayıp sayfa", "iç link kırığı", "broken internal link", "redirect
  chain", "yönlendirme zinciri", "anchor distribution", "anchor text
  dağılımı", "iç link analizi" der ya da /pseo-internal-links çağırır.
  Also use when: aktif projenin SF export'u mevcut (sf-import koşmuş);
  projects/{slug}/sf-exports/{date}/raw/ altında all_inlinks.csv +
  internal_all.csv var; orphan / broken / redirect-chain / anchor
  diversity bulguları master.xlsx#master_task'a auto_generated entry
  olarak yazılacak; quick-wins / cannibalization sonrası ek planning
  pass'i olarak çağırılır.
  Do not use when: SF import yapılmamış (önce sf-import çalıştır,
  DURUR #1); GSC quick-wins / cannibalization tetiklenecek (ayrı
  discovery skill'leri); tek-URL on-page audit (on-page-audit); DFS
  bütçesi aşılmışsa --use-dfs flag KULLANMA, default no-cost path
  yeterlidir. Master.xlsx yokken çağırma; init-project önce çalışmalı
  (DURUR #6).
version: "1.0"
status: active
category: planning
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + sf-exports/."
  sf_export_date:
    type: string
    required: false
    description: "ISO date of SF export to read (projects/{slug}/sf-exports/{date}/raw/). Default: latest folder under sf-exports/."
  default_status:
    type: string
    required: false
    default: "TODO"
    description: "statusEnum seed for new master_task rows (default TODO)."
  max_entries:
    type: integer
    required: false
    default: 500
    description: "Hard cap on auto_generated rows; DURUR #7 vehicle when exceeded."
  use_dfs:
    type: boolean
    required: false
    default: false
    description: "Optional: enrich findings via mcp__dataforseo__on_page_content_parsing. Triggers budget pre-flight (paid MCP)."
  use_sf_mcp_live:
    type: boolean
    required: false
    default: false
    description: "Opt-in (D-SF-11): when true, calls SF MCP via scripts/util/sf_mcp_client.SfMcpClient for live all_inlinks (bypasses sf-exports CSV freshness gap). Resolves the crawl id from sf_list_crawls (domain match → instanceDirName), client.load_crawl(...) (resilient), then exports all_inlinks via SF_EXPORT_DISPATCH (sf_generate_bulk_export category 'Links:All Inlinks', export_type CSV) to file_path (the >100KB inline cap is resolved by writing to disk, not a non-existent 'truncated' flag), reads the native CSV with utf-8-sig (strips SF's BOM), parses with csv.DictReader → transform(inlinks_rows=...). Requires SF GUI + MCP server running (preflight via client.health(); on FAIL / no matching crawl / SfMcpToolError / load timeout → AMBER fallback to file-based path, NEVER hard fail per R9)."
outputs:
  - "master.xlsx#master_task"
  - "outputs/reports/{date}-internal-links.md"
  - "events.jsonl"
  - "inbox/sf/{date}-internal_links-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-internal-links"]
  natural_language: |
    "internal links", "iç linkleme", "orphan page", "kayıp sayfa",
    "iç link kırığı", "broken internal link", "redirect chain",
    "yönlendirme zinciri", "anchor distribution", "anchor text dağılımı",
    "iç link analizi"
  hooks: []
  scheduled:
    - cron: "0 9 * * 3"
      mode: "report-only"
mcp_tools:
  required: []
  optional:
    - "mcp__dataforseo__on_page_content_parsing"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# internal-links — planning skill (Phase 8 Wave 1)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §6 SF ingest discipline + §16.5 raw-inbox transform discipline.
Raw CSV envelope discipline is mandatory: SF CSVs are described in a
single envelope-JSON dropped into `inbox/sf/` *before* any per-row
transform runs, so a transform bug never costs us the upstream payload.

This skill follows the **convention authority** established by
`skills/discovery/cannibalization/SKILL.md` (Phase 7 Wave 1) and
`skills/ingestion/sf-import/SKILL.md` (Phase 5 Wave 2). The 10-step
protocol shape, raw envelope discipline, URL normalization (D-03),
DURUR + flag rule, and provenance event format are reused verbatim —
only the data source (SF CSV instead of GSC MCP) and the target sheet
(master_task auto_generated rows instead of a sheet-specific layout)
change. Deviate only with an ADR.

Unlike Phase 7 discovery skills that read GSC/DFS MCP responses, this
planning skill reads **SF CSV files directly** from disk. There is NO
DFS dependency in the default path; `_normalize_dfs_response` (D-003
helper) is NOT imported here because no DFS payload is consumed. The
optional `--use-dfs` enrichment path (anchor-text quality scoring) DOES
gate behind `scripts/budget/check_budget.py` per §16.8 + ADR-016, but
the default flow burns 0 credits.

## Inputs (frontmatter contract)

| Name              | Type    | Default | Notes                                                     |
|-------------------|---------|---------|-----------------------------------------------------------|
| `project_slug`    | string  | —       | Required. Resolves `projects/{slug}/master.xlsx` + sf-exports/. |
| `sf_export_date`  | string  | latest  | Reads `projects/{slug}/sf-exports/{date}/raw/`.           |
| `default_status`  | string  | "TODO"  | statusEnum seed for new master_task rows.                 |
| `max_entries`     | integer | 500     | DURUR #7 cap; >500 entries → flag for batching.           |
| `use_dfs`         | boolean | false   | Opt-in DFS enrichment; triggers budget pre-flight.        |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#master_task` — N auto_generated rows
  (one per orphan / broken / redirect-chain / anchor finding), 19
  columns, `auto_generated=true`, `primary_source=tech_fix`.
- `projects/{slug}/outputs/reports/{date}-internal-links.md` —
  human-readable summary (orphan list + broken counts + redirect
  chains + anchor diversity flags).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entry (`source.kind=sf_csv`, `target_excel_sheet=master_task`).
- `projects/{slug}/inbox/sf/{date}-internal_links-{slug}.json` —
  drift-recovery envelope listing the SF CSVs read + finding counts.

## Output Target Decision (Option A vs C)

The brief gave three options for where internal-links findings land:

| Option | Target                                      | Schema Bump | Decision |
|--------|---------------------------------------------|-------------|----------|
| A      | `master.xlsx#master_task` auto_generated    | NONE        | **CHOSEN** |
| B      | New `master.xlsx#internal_links` sheet      | REQUIRED → ADR | OUT OF SCOPE (Wave 1, manager-only) |
| C      | staging-only (`_state/staging/...json`)     | NONE        | rejected |

**Choice: Option A — D-01 SSoT extension via master_task auto_generated entries.**

**Rationale:**
1. **Single source of truth (D-01).** `master_task` is already the
   workspace-wide task table consumed by `dashboard_refresh`,
   `done_protocol`, `whats-next`. Putting internal-links findings
   there means no downstream skill needs to learn a new sheet name —
   reuse the existing `master_task_sync` writer scope (allowed_writers
   list in master-excel.schema includes `master_task_sync`, which is
   the planning-skill writer convention).
2. **Schema-neutral.** Option B's new sheet would force a schema
   bump → ADR → manager approval, breaking Wave 1 worker scope.
   Option A uses only existing columns + existing enum values.
3. **`auto_generated=true` flag is purpose-built** (col O,
   `type: boolean`) — it tells dashboard_refresh / done_protocol that
   the row was synthesized by a planning skill and is eligible for
   bulk dismissal / batch-approve flows. The schema enforces:
   - `auto_generated` (col O) MUST be a boolean.
   - `primary_source` (col C) MUST be in the closed enum
     {content_decay, quickwin, tech_fix, schema, pillar, manual,
     sxo, cannibalization, redirect_404}. We use **`tech_fix`**
     (closest match for structural/internal-links findings; the
     enum has NO `internal_links` value, see Open Question Q-IL-1).
   - `note` carries the analysis lineage prefix `[internal-links/{kind}]`
     so glossary-audit / drift-check can find these rows by prefix.
   - `metric_impact_json` (col R) carries the per-finding diagnostic
     payload (kind, status_code, inbound_count, etc.).
4. **Volume-tolerant via DURUR #7.** If a single run produces
   >500 auto_generated entries, the transform raises
   `MaxEntriesExceededError` and the skill flags the manager to
   batch the run. Option C would silently dump everything and
   defer the volume problem to Phase 9 — not better.

Option C (staging-only) was considered as fallback when entry count
exceeds the cap; rejected because dashboard_refresh / whats-next
already speak master_task — adding a parallel staging path doubles
the surface area for Phase 9 reporting integration without any data
benefit. If volume becomes structural (every run > cap), revisit via
ADR (Option B schema bump).

**Source-field convention** for auto_generated entries:

| Column           | Value (per row)                                                  |
|------------------|------------------------------------------------------------------|
| `task_id`        | `{slug}-{date}-il-{kind}-{idx:03d}` (deterministic, slug-agnostic) |
| `task`           | Human label (e.g. "Orphan page (no internal inlinks): {url}")    |
| `primary_source` | `"tech_fix"` (enum value)                                        |
| `related_sources`| `"internal-links"` (free-text reference)                         |
| `category`       | `"internal-links"` (free-text)                                   |
| `note`           | `"[internal-links/{kind}] {detail}"` (machine-parseable prefix)  |
| `auto_generated` | `True` (boolean — col O type=boolean)                            |
| `metric_impact_json` | sorted-keys JSON of finding metrics                          |

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="internal-links",
    project_slug=project_slug,
    steps=[
        {"name": "load_sf_csvs"},
        {"name": "envelope_inbox"},
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `load_sf_csvs` (SF CSV first — drift-recoverable)

```python
from scripts.planning import internal_links_transform as ilt
raw_dir = (
    workspace_root / "projects" / project_slug
    / "sf-exports" / sf_export_date / "raw"
)
internal_rows, inlinks_rows, outlinks_rows = ilt.load_sf_csvs(raw_dir)
```

Raises `SFDataMissingError` (DURUR #1) when the dir is missing or no
SF CSVs are found, and `CSVParseError` (DURUR #2) on header mismatch
or encoding failure.

### Step 3 — `envelope_inbox` (raw → drift-recoverable JSON)

For each loaded CSV: capture filename, row count, header set, and a
sha256 of the file bytes. Drop the envelope into
`inbox/sf/{date}-internal_links-{slug}.json` BEFORE any transform
runs. The envelope is the durable witness that a given SF batch was
observed even if the Excel write fails downstream.

```python
envelope = {
    "_meta": {
        "captured_at": _utc_iso_z(),
        "tool": "screaming_frog",
        "skill": "internal-links",
        "project_slug": project_slug,
        "sf_export_path": str(raw_dir),
    },
    "files": [
        {"canonical_name": "internal_all", "row_count": len(internal_rows or [])},
        {"canonical_name": "all_inlinks", "row_count": len(inlinks_rows or [])},
        {"canonical_name": "all_outlinks", "row_count": len(outlinks_rows or [])},
    ],
}
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "sf"
    / f"{today.isoformat()}-internal_links-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(
    json.dumps(envelope, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

### Step 4 — `transform` (pure compute)

```bash
python3 scripts/planning/internal_links_transform.py \
    --raw-dir projects/{slug}/sf-exports/{date}/raw/ \
    --project-slug {slug} \
    --run-date {date} \
    --default-status TODO \
    --max-entries 500 \
    --output-dir _state/transform/{run_id}/
```

Produces a JSON array (`master_task`) shaped to the master-excel
schema (19 columns: task_id, task, primary_source, related_sources,
url, category, priority, impact, duration_est_min, status,
created_date, done_date, assignee, note, auto_generated, dependencies,
effort_actual_min, metric_impact_json, work_log_ref). URL normalization
(D-03) is applied here, not at load time, so the inbox envelope is
byte-faithful to the SF export.

The transform is idempotent: same inputs → byte-identical output.

If the result has `meta.row_count == 0`, the skill SKIPS write_excel
and emits a "no internal-links findings" notice (DURUR #8 — clean
exit, not error).

### Step 5 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(rows)} internal-links bulgu (orphan/broken/redirect/anchor); "
            "master.xlsx#master_task'a auto_generated entry yazalım mı?",
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

Single `transaction.append` call to the master_task sheet. The writer
is `master_task_sync` (allowed_writers list in master-excel.schema).
Goes through the single approved write path with backup, lock, schema
validation, and post-write provenance event emission.

```python
from scripts.excel import transaction
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="master_task",
    rows=master_task_rows,
    project_slug=project_slug,
    writer="master_task_sync",
)
```

### Step 8 — `render_report`

`render_template.py templates/reports/internal-links.template.md
data.json` → `outputs/reports/{date}-internal-links.md`. Variables:
`$project_slug`, `$date`, `$orphan_count`, `$broken_count`,
`$redirect_chain_count`, `$anchor_diversity_count`, `$top_orphan_url`,
`$top_broken_url`, `$report_summary`.

### Step 9 — Provenance event

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    source={
        "kind": "sf_csv",
        "source_folder": str(raw_dir.relative_to(workspace_root)),
        "row_count": (
            len(internal_rows or []) + len(inlinks_rows or [])
        ),
    },
    operation="project_excel",
    target_excel_sheet="master_task",
    rows_written=len(master_task_rows),
)
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED
    "row_count": str(len(master_task_rows)),
    "orphan_count": str(meta["orphan_count"]),
    "broken_count": str(meta["broken_count"]),
    "redirect_chain_count": str(meta["redirect_chain_count"]),
    "anchor_diversity_count": str(meta["anchor_diversity_count"]),
    "report_path": str(report_path),
    "envelope": str(inbox_path),
})
```

## SF MCP Live Mode (Optional, `use_sf_mcp_live=true` — D-SF-11)

**Default: `use_sf_mcp_live=false`** — file-based ingestion (SF CSV from
`projects/{slug}/sf-exports/{date}/raw/`) is the canonical contract.
The flag is opt-in only and gated by a `client.health()` preflight; on
probe failure the run AMBER-warns and continues with the file-based
path (never hard-fail per R9 mitigation).

When `use_sf_mcp_live=true`, the SKILL body branches at Step 2
(`load_sf_csvs`) to optionally pull `all_inlinks` rows inline from SF
MCP instead of reading the on-disk CSV. The default no-DFS, no-MCP
path remains 0 credits and continues to satisfy the existing SF CSV
fixtures used in the 1184+ baseline.

**This branch was rewritten (AC-13 replication) against the REAL SF MCP
API** — the same class of fix as tech-audit (landed in `6ee6fb9`,
live-proven on the aluminumstation crawl) and the sf-crawl-orchestrator
Step-5 export dispatch (`a714e43`). The engine canonical `all_inlinks`
is NOT a Screaming Frog identifier: it maps via
`sf_crawl_orchestrator.SF_EXPORT_DISPATCH` to the real
`sf_generate_bulk_export` tool with `category="Links:All Inlinks"` +
`export_type="CSV"`. There is NO `crawl_id`, `report_name`, or
`save_report` arg; the export runs on the *currently-loaded* crawl and
is written to `file_path` (relative to the SF allowed base directory).
The real SF REJECTS inline output >100KB with a tool error — and
all_inlinks is the single largest export (one row per edge), so
`file_path` (write-to-disk) is the only safe path (OQ-FILEPATH-EXPORTS),
not a non-existent `truncated` flag.

The `sf_list_crawls` result comes back through `SfMcpClient.call_tool`
as the MCP content envelope `{"isError":false,"content":[{"text":
"<JSON>"}]}`, so the crawl list is JSON-encoded inside `content[*].text`
(exactly like `sf_crawl_progress`). We decode the first JSON block, then
match on `url` → `instanceDirName`. The real entry shape (Manager-probed)
is `{"url":"https://aluminumstation.com/","instanceDirName":"fc718e3f-..."}`.

`sf_generate_bulk_export` writes a **native CSV WITH a leading UTF-8 BOM**
(live-verified) — so the written file is read with `encoding="utf-8-sig"`,
otherwise `csv.DictReader`'s first key arrives BOM-quoted
(`'﻿"Address"'`) and every row silently drops.

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

                # 3) Export "Links:All Inlinks" via the orchestrator dispatch
                #    (all_inlinks → ("sf_generate_bulk_export",
                #    {"category":"Links:All Inlinks","export_type":"CSV"})). The
                #    >100KB inline cap is resolved by writing to file_path.
                tool, call_kwargs = sf_crawl_orchestrator.SF_EXPORT_DISPATCH[
                    "all_inlinks"
                ]
                rel_path = "all_inlinks.csv"
                client.call_tool(tool, file_path=rel_path, **call_kwargs)

                # 4) Read the written CSV from the SF allowed base dir. A BULK
                #    export is NATIVE CSV → read directly (NO ndjson_to_csv).
                #    utf-8-sig strips SF's leading BOM so csv.DictReader's first
                #    key is clean "Address" (not '﻿"Address"'); without it
                #    every row would silently drop (the AC-13 BOM bug class).
                csv_path = allowed_dir / rel_path
                with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
                    inlinks_rows = list(csv.DictReader(fh))
                # The transform's per-destination aggregator (broken /
                # redirect-chain / anchor-diversity) consumes the same
                # DictReader-shaped rows whether they come from CSV or MCP.
        except (SfMcpToolError, SfMcpError) as exc:
            # R9 AMBER fallback — list/load/export failed (4xx/5xx, JSON-RPC
            # error, load_crawl settle timeout). NEVER hard fail.
            amber_warnings.append(
                f"SF MCP error: {exc}; falling back to file-based path"
            )

# Pass the parsed rows straight into the transform (default file-based
# inlinks_rows when the MCP path was skipped / fell back).
result = internal_links_transform.transform(
    internal_all_rows=internal_all_rows,
    inlinks_rows=inlinks_rows,
    project_slug=project_slug,
    run_date=run_date,
)
```

**AMBER vs RED policy (R9 contract — never hard-fail this branch):**

- `client.health()` returns False → AMBER warning, continue file-based.
- No crawl matches the project domain in `sf_list_crawls` → AMBER
  warning, continue file-based.
- `SfMcpToolError` / `SfMcpError` raised (export 4xx/5xx, JSON-RPC error,
  `load_crawl` settle timeout) → AMBER warning, continue file-based.
- A partial SF outage degrades to the file-based `all_inlinks.csv`
  (orphan/broken/redirect-chain detectors handle missing edges
  gracefully — affected_urls just understates).
- NEVER raise `SystemExit` from this branch. RED reserved for the
  existing DURUR set (SF data missing in BOTH paths, CSV parse error,
  max_entries exceeded, etc.).

**Tool naming reminder:** `call_tool(tool_name=...)` takes the **native**
SF MCP tool name (`"sf_generate_bulk_export"`, `"sf_list_crawls"`,
`"sf_load_crawl"`), NOT the registry form (`"sf__sf_generate_bulk_export"`)
or the Claude Code wrapper form (`"mcp__sf__sf_generate_bulk_export"`).
JSON-RPC `params.name` follows the native form per MCP spec. `SfMcpClient`
already speaks the MCP Streamable-HTTP transport (session handshake +
SSE), so the body only ever passes native tool names + the SF call kwargs.

`amber_warnings` is surfaced via the existing provenance event
(an additional `source.kind=sf_mcp` event is emitted alongside the
sf_csv event at Step 9) and the rendered report template variable
`$amber_warnings`.

## URL normalization (D-03 invariant)

Every URL passing through this skill is normalized via
`scripts.planning.internal_links_transform.normalize_url`. The function
is **idempotent**: `normalize_url(normalize_url(u)) == normalize_url(u)`.
Rules: lowercase scheme+host, IDN→punycode, strip default ports, strip
trailing slash (root excluded), drop fragment, drop tracking params,
sort remaining query keys.

The transform self-checks idempotency on every emitted URL (post-row
build) — drift between transform and downstream consumers is escalated
as `RowSchemaError` rather than silently masked.

## Detection rules (4 finding kinds)

| Kind             | Condition                                                       | Severity | Duration |
|------------------|-----------------------------------------------------------------|----------|----------|
| orphan-page      | status=200 + indexable + 0 inlinks                              | HIGH     | 30 min   |
| broken-link      | inlink edge destination status_code 4xx/5xx (per-dest agg)      | HIGH/CRITICAL/MEDIUM | 15 min |
| redirect-chain   | inlink edge destination status_code 3xx (per-dest agg)          | LOW/MEDIUM | 20 min |
| anchor-diversity | dest URL ≥5 inbound non-empty anchors + only 1 distinct anchor | LOW      | 25 min   |

`task_id` format: `{slug}-{run_date}-il-{kind}-{idx:03d}` —
deterministic + slug-agnostic; same input produces the same task_id
across re-runs.

## Optional DFS path (paid MCP enrichment)

When the manager passes `use_dfs=true`, the skill enriches the
findings with `mcp__dataforseo__on_page_content_parsing` (anchor-text
quality scoring, link-position weighting). Pre-flight is MANDATORY:

```python
from scripts.planning import internal_links_transform as ilt
estimate = ilt.estimate_credits(url_count=len(internal_rows), use_dfs=True)
ilt.preflight_budget(
    estimated_credits=estimate,
    project_config_path=workspace_root/"projects"/project_slug/"project.config.json",
    events_path=workspace_root/"projects"/project_slug/"_state"/"events.jsonl",
)
```

`BudgetExceededError` (DURUR #6) is raised when projected daily usage
exceeds the cap; the skill must route the workflow to
`awaiting_approval` per ADR-016 / spec §10. The default no-DFS path
burns 0 credits and skips this gate entirely.

## DURUR conditions (8)

Stop and flag the manager — do not patch, do not fall back.

1. SF data missing — `projects/{slug}/sf-exports/{date}/raw/` does
   not exist OR is empty (no `internal_all.csv` / `all_inlinks.csv` /
   `all_outlinks.csv`). STOP, point user to run `sf-import` first.
   `SFDataMissingError`.
2. `all_inlinks.csv` parse fail (header mismatch / encoding bad).
   STOP, do not silently emit empty rows. `CSVParseError`.
3. `master.xlsx#master_task` column count or names don't match
   schema (`schemas/master-excel.schema.json#master_task`,
   19 required_columns). STOP, schema-first violation. Caught at
   transform boundary as `RowSchemaError`.
4. `transaction.append` raises `RowSchemaError` (e.g.
   `auto_generated` not boolean, `status` not in statusEnum,
   `priority` not in severityEnum). STOP.
5. Output target ambivalence — manager passed Option B request
   (new sheet + schema bump). NOT in Wave 1 scope; route to manager
   for ADR draft.
6. Optional DFS path budget pre-flight FAIL (only when
   `use_dfs=true`). `BudgetExceededError` — route to
   `awaiting_approval` per ADR-016 / spec §10.
7. `MaxEntriesExceededError` — emitted entries exceed `max_entries`
   (default 500). Manager flag for batching review (split run by
   sub-folder or by finding kind).
8. Transform reports `meta.row_count == 0` (no internal-links
   findings). NOT an error — clean exit with a "no internal-links
   findings" notice; skill skips write_excel + render_report and goes
   straight to `complete` with `row_count="0"`.

## Cross-references

- Schemas: `schemas/master-excel.schema.json#master_task`
  (19 required_columns + `#/definitions/statusEnum` +
  `#/definitions/severityEnum` + `primary_source` enum),
  `schemas/events.schema.json` (`source.kind=sf_csv`,
  `target_excel_sheet=master_task`),
  `schemas/sf-required-reports.schema.json` (Tier 1 placement of
  `internal_all`, `all_inlinks`, `all_outlinks`),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`,
  `scripts/budget/check_budget.py` (only when `use_dfs=true`).
- Transform: `scripts/planning/internal_links_transform.py`.
- Tests: `tests/skills/test_internal_links.py` (≥6 cases).
- Pilot data path: `projects/{slug}/sf-exports/{export_date}/raw/`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises (exception: DURUR #8 is
      a clean no-op exit, not a fallback).
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7; master_task
      column tuple verified against `schemas/master-excel.schema.json`.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] ADR-013: Use when / Also use when / Do not use when are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` / `workflow_runner`
      / `events_writer` imported, never modified.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED, never raw ints.
- [x] Append-only state — `events.jsonl` only grows.
- [x] D-003 helper NOT applicable — no DFS payload in default path;
      `_normalize_dfs_response` is NOT imported. The transform stays pure.
