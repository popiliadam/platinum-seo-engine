---
name: sf-import
description: |
  Use when: kullanıcı "screaming frog import", "SF csv yükle", "sf-export al",
  "site crawl ingest", "yeni SF batch geldi" der ya da bir projenin
  sf-exports/{date}/raw/ dizinine yeni CSV'ler düştüğünde manager bu
  skill'i tetikler. Master.xlsx'in 6 SF-türevi sheet'ine (crawl_sitemap,
  redirect_404, schema, on_page_audit, tech_seo, robots_txt) atomic write
  yapar; raw CSV'leri inbox/sf/ altına envelope-li JSON olarak persist
  eder.
  Also use when: pilot dentnotion sf-exports/2026-04-27/raw/ dizini hazır;
  Tier 1 14/14 zorunlu rapor mevcut; Tier 2 search_console_all eksik AMBER
  warning üretilmesi gerek; mcp__gsc__list_sitemaps ile cross-check
  yapılacak; sf_imported provenance event yazılacak.
  Do not use when: GSC (gsc-pull), DataForSEO (dfs-pull), Scrapling
  (scrapling-ops) verisi geliyor — ayrı ingestion skill'leri. Master.xlsx
  yokken çağırma; init-project önce çalışmalı (DURUR #6). Tier 1 < 14
  ise FAIL et, fallback YASAK (DURUR #2).
version: "1.0"
status: wip
category: ingestion
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/sf-exports/ + master.xlsx."
  sf_export_path:
    type: string
    required: true
    description: "SF export dizini path (mutlak veya workspace-relative). raw/ subfolder zorunlu."
outputs:
  - "master.xlsx#crawl_sitemap"
  - "master.xlsx#redirect_404"
  - "master.xlsx#schema"
  - "master.xlsx#on_page_audit"
  - "master.xlsx#tech_seo"
  - "master.xlsx#robots_txt"
  - "events.jsonl"
  - "inbox/sf/{date}-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
produces:
  - "quick-wins"
  - "drift-check"
triggers:
  manual: []
  natural_language: |
    "screaming frog import", "SF csv yükle", "sf-export al",
    "site crawl ingest", "yeni SF batch geldi"
  hooks: []
mcp_tools:
  required:
    - "mcp__gsc__list_sitemaps"
    - "mcp__gsc__get_sitemap"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: false
  safe_auto_execute: true
---

# sf-import — ingestion skill (Phase 5 Wave 2)

8-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §6 Stage 1-3 ingest discipline. Raw CSV envelope discipline is
mandatory: every SF batch is described in a single envelope-JSON dropped
into `inbox/sf/` *before* any per-sheet projection runs, so a projection
bug never costs us the upstream filename → tier mapping.

This skill is the **convention authority** for the 3 ingestion skills
(sf-import, gsc-pull, dfs-pull). The 5-stage tier validation + envelope
inbox + per-sheet `transaction.append` pattern repeats verbatim across
all three. Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name              | Type   | Default | Notes                                                              |
|-------------------|--------|---------|--------------------------------------------------------------------|
| `project_slug`    | string | —       | Required. Resolves `projects/{slug}/master.xlsx`.                  |
| `sf_export_path`  | string | —       | Required. Path to a SF export dir; `raw/` subfolder enforced.      |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#crawl_sitemap` — sitemap-vs-crawl summary rows.
- `projects/{slug}/master.xlsx#redirect_404` — 404 + redirect chain rows.
- `projects/{slug}/master.xlsx#schema` — structured-data audit rows.
- `projects/{slug}/master.xlsx#on_page_audit` — title/meta/h1 coverage rows.
- `projects/{slug}/master.xlsx#tech_seo` — tech issue summary rows.
- `projects/{slug}/master.xlsx#robots_txt` — robots/directive issue rows.
- `projects/{slug}/_state/events.jsonl` — provenance entries (`source.kind=sf_csv`).
- `projects/{slug}/inbox/sf/{date}-{slug}.json` — envelope JSON listing every
  CSV (filename, tier, row_count, file_hash) for drift recovery.

## 8-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="sf-import",
    project_slug=project_slug,
    steps=[
        {"name": "validate_export_path"},
        {"name": "validate_tier1"},
        {"name": "envelope_inbox"},
        {"name": "sitemap_xcheck"},
        {"name": "write_excel"},
    ],
)
```

### Step 2 — `validate_export_path`

```python
workflow_runner.start_step(handle.run_id, 0, project_slug=project_slug)
sf_root = Path(sf_export_path)
raw_dir = sf_root / "raw" if (sf_root / "raw").is_dir() else sf_root
if not raw_dir.is_dir():
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="validation_error",
        message=f"sf_export_path missing or no raw/ subfolder: {sf_root}",
        step_index=0,
    )
    raise SystemExit(2)  # DURUR #1
workflow_runner.finish_step(handle.run_id, 0, project_slug=project_slug,
                            output_ref=str(raw_dir))
```

### Step 3 — `validate_tier1` (sf-required-reports.schema Tier 1 14/14)

Cross-references `schemas/sf-required-reports.schema.json` definitions.canonicalName
+ aliases. Walks `raw/`, normalizes filenames (lower, strip `de_` /
`v_` / `p_` prefixes, strip `(1)` suffixes, fold Turkish `ı→i`), and
matches each canonical_name. Tier 1 missing → RED FAIL. Tier 2 missing →
AMBER warn, NOT a fail (search_console_all is the canonical Tier 2
exemption surfaced in the dentnotion pilot).

```python
matched, missing_t1, missing_t2 = scripts.ingestion.sf_validate.match_tiers(raw_dir)
if missing_t1:
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="validation_error",
        message=f"Tier 1 missing: {sorted(missing_t1)}",
        step_index=1,
    )
    raise SystemExit(2)  # DURUR #2
amber_warnings: list[str] = []
if missing_t2:
    amber_warnings.append(f"Tier 2 missing (AMBER, not fatal): {sorted(missing_t2)}")
workflow_runner.finish_step(handle.run_id, 1, project_slug=project_slug,
                            output_ref=f"matched={len(matched)} missing_t1={len(missing_t1)} missing_t2={len(missing_t2)}")
```

### Step 4 — `envelope_inbox` (raw → drift-recoverable JSON)

For every matched CSV: compute sha256, count rows, capture
filename_original + filename_normalized + tier. Drop the envelope into
`inbox/sf/{date}-{slug}.json` BEFORE any projection runs. The envelope
is the durable witness that a given SF batch was observed even if the
Excel write fails downstream.

```python
envelope = {
    "_meta": {
        "captured_at": _utc_iso_z(),
        "tool": "screaming_frog",
        "project_slug": project_slug,
        "sf_export_path": str(sf_root),
        "raw_dir": str(raw_dir),
        "amber_warnings": amber_warnings,
    },
    "files": [
        {
            "canonical_name": m.canonical_name,
            "tier": m.tier,                       # "required" | "recommended"
            "filename_original": m.filename_original,
            "filename_normalized": m.filename_normalized,
            "file_hash": f"sha256:{m.sha256}",
            "row_count": m.row_count,
        }
        for m in matched
    ],
}
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "sf"
    / f"{today.isoformat()}-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2),
                      encoding="utf-8")
```

### Step 5 — `sitemap_xcheck` (mcp__gsc__list_sitemaps cross-check)

Cross-check the SF-discovered URL list against the GSC submitted
sitemaps. Discrepancies are LOGGED (added to crawl_sitemap rows as a
diagnostic metric), not fatal — a missing sitemap entry for a crawled
URL is a warning the project can act on, not an ingest failure.

```python
sitemaps = mcp__gsc__list_sitemaps(siteUrl=project_config["gsc"]["site_url"])
xcheck_metrics = scripts.ingestion.sf_sitemap_xcheck.compare(
    sf_internal_csv=raw_dir / "internal_all.csv",
    submitted_sitemaps=sitemaps,
)  # → {"submitted_count": N, "crawled_count": M, "in_both": K, ...}
```

If `mcp__gsc__list_sitemaps` raises → DURUR #4: the cross-check is a
required input to crawl_sitemap; do not silently skip.

### Step 6 — `write_excel` (per-sheet, atomic)

Six `transaction.append` calls — one per sheet. Each goes through the
single approved write path with backup, lock, schema validation, and
post-write provenance event emission. The 6 sheets and their CSV → row
projections (inline mapping; the formal `staging-to-excel-map.json`
arrives in Phase 6):

| Logical sheet     | Source CSV(s)                                      | Row shape (master-excel.schema)                                 |
|-------------------|----------------------------------------------------|------------------------------------------------------------------|
| `crawl_sitemap`   | `internal_all`, `sitemaps_all`, `crawl_depth`      | category / metric / value / status / action                       |
| `redirect_404`    | `response_codes_all`, `redirect_chains`            | url / inlinks / action / target_url / status                      |
| `schema`          | `structured_data_all`                              | schema_type / status / location / scope / remaining_work          |
| `on_page_audit`   | `page_titles_all`, `meta_description_all`, `h1_all`| url / target_query / impressions_30d / clicks_30d / in_title /... |
| `tech_seo`        | `issues_overview_report`, `directives_all`         | issue_category / detail / affected_urls / impact / resolution / ... |
| `robots_txt`      | `directives_all`, `indexability`                   | id / level / issue / detail / resolution                          |

```python
from scripts.excel import transaction
for sheet, rows in projections.items():
    transaction.append(
        workbook_path=master_xlsx,
        sheet=sheet,
        rows=rows,
        project_slug=project_slug,
        writer="sf-import",
    )
```

`transaction.append` itself emits a `tool_computed` provenance event per
write. Step 7 supplements that with a single `sf_csv` source provenance
record so the data lineage is `sf_csv → tool_computed`.

### Step 7 — Provenance event (`sf_csv` source, `sf_imported` operation)

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        "kind": "sf_csv",
        "source_folder": str(raw_dir.relative_to(workspace_root)),
        "row_count": sum(m.row_count for m in matched),
    },
    operation="ingest",
    rows_written=sum(len(rs) for rs in projections.values()),
)
```

### Step 8 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED (artifact paths, not ints)
    "envelope": str(inbox_path),
    "crawl_sitemap_rows": str(len(projections["crawl_sitemap"])),
    "redirect_404_rows": str(len(projections["redirect_404"])),
    "schema_rows": str(len(projections["schema"])),
    "on_page_audit_rows": str(len(projections["on_page_audit"])),
    "tech_seo_rows": str(len(projections["tech_seo"])),
    "robots_txt_rows": str(len(projections["robots_txt"])),
    "amber_warnings": ";".join(amber_warnings) or "none",
})
```

## Filename normalization (Tier 1 matching)

The pilot dentnotion export ships every Tier 1 file twice: once with the
canonical name (`internal_all.csv`) and once with a `de_` prefix (German
locale shadow `de_internal_all.csv`). Plus a third Turkish-i variant
(`de_ınternal_all.csv`). Normalization rules, applied in order:

1. Lowercase the basename.
2. Drop extension (`.csv`).
3. Strip leading locale shadow prefix `de_` (defensive — pilot artifact).
4. Strip leading export-mode prefix `v_` / `p_` (SF visualization vs page mode).
5. Fold Turkish dotless `ı` → ASCII `i` (Turkish-locale filename collision).
6. Drop `(N)` and `-copy` / `_old` version suffixes.

The first matching canonical_name (per `sf-required-reports.schema`)
wins. Ambiguous matches (two canonical names matching the same file)
abort the import — no silent picks.

## Tier policy

| Tier        | Missing → | Pilot exemption                                  |
|-------------|-----------|--------------------------------------------------|
| Required    | RED FAIL  | none (all 14 enforced)                           |
| Recommended | AMBER     | `search_console_all` (pilot ships 9/10, OK)      |
| Optional    | SILENT    | full set silent                                  |

## DURUR conditions (6)

Stop and flag the manager — do not patch, do not fall back.

1. `sf_export_path` missing or no readable `raw/` subfolder.
2. Tier 1 < 14/14 — RED FAIL, do not proceed to projection.
3. `transaction.append` raises `RowSchemaError` for any sheet — abort
   the entire batch (atomicity is per-call, but the brief enforces
   all-or-nothing across the 6 sheets at the manager layer).
4. `mcp__gsc__list_sitemaps` raises (auth/network/scope) — sitemap
   x-check is a required input.
5. `PSEO_WORKSPACE_ROOT` env unset and no explicit `workspace_root` arg
   passed to `workflow_runner` / `events_writer`.
6. `master.xlsx` missing under `projects/{slug}/` — `init-project`
   must have run first.

## Cross-references

- Schemas: `schemas/sf-required-reports.schema.json` (Tier 1 14, Tier 2
  10, canonicalName enum), `schemas/sf-export-mapping.schema.json`
  (filename_alias normalization), `schemas/master-excel.schema.json`
  (6 sheet column structures + statusEnum + severityEnum),
  `schemas/events.schema.json` (`source.kind=sf_csv`),
  `schemas/gsc-tool-mapping.schema.json` (`gsc__list_sitemaps` enum),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/validation/validate_schema.py`.
- Tests: `tests/skills/test_sf_import.py` (6 cases incl. live SF batch).
- Pilot data: `projects/dentnotion/sf-exports/2026-04-27/raw/`
  (Tier 1 14/14 + Tier 2 9/10 with `search_console_all` AMBER).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` are imported, never modified
      from this skill.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped). The
      legacy `Dentnotion_MASTER.xlsx` (Turkish-emoji) is DOKUNULMAZ.
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
