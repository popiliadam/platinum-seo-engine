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
  Also use when: pilot project sf-exports/{export_date}/raw/ dizini hazır;
  Tier 1 14/14 zorunlu rapor mevcut; Tier 2 search_console_all eksik AMBER
  warning üretilmesi gerek; sf_imported provenance event yazılacak. (Opsiyonel
  mcp__gsc__list_sitemaps sitemap cross-check Phase-X'e ertelendi — core ingest
  GSC'siz, sadece disk CSV'leriyle çalışır.)
  Do not use when: GSC (gsc-pull), DataForSEO (dfs-pull), Scrapling
  (scrapling-ops) verisi geliyor — ayrı ingestion skill'leri. Master.xlsx
  yokken çağırma; init-project önce çalışmalı (DURUR #6). Tier 1 < 14
  ise FAIL et, fallback YASAK (DURUR #2).
version: "1.0"
status: active
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
  source_run_id:
    type: string
    required: false
    description: "v1.8 Phase 3 D-SF-07: optional upstream run_id from sf-crawl-orchestrator. When present, chained into the provenance event so drift-check can correlate the orchestrator MCP crawl with this file-based ingest. Body 8-step protocol UNCHANGED."
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
  # sf-import's deterministic core (scripts/ingestion/sf_import.py) reads SF
  # CSVs from disk and writes Excel — it invokes NO MCP tool. The GSC sitemap
  # tools power the OPTIONAL sitemap cross-check (Step 5), which is Phase-X
  # deferred (not wired into the shipped implementation), so they are optional.
  required: []
  optional:
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

Deterministic CLI (`scripts/ingestion/sf_import.py`), **not** a
`workflow_runner` run shell. The stages below run in a single `main(argv)`
pass: each DURUR is a `print("ERROR: … (DURUR #N)", file=sys.stderr)` plus
a distinct non-zero **exit code** (no `{run_id}.json` state file, no
`workflow_runner.create_run`/`complete`, no string-typed `outputs`). Raw
CSV envelope discipline is mandatory: every SF batch is described in a
single envelope-JSON dropped into `inbox/sf/` *before* any per-sheet
projection runs, so a projection bug never costs us the upstream
filename → tier mapping.

The 6 SF-derived sheets are written via **`transaction.replace`** (an
idempotent refresh — clears each sheet's data block, then re-lands the
rows), so re-running a batch *refreshes* rather than duplicates. The
tier-validation + envelope-inbox + per-sheet-write shape is shared with
the other ingestion skills, but the write mechanism differs per skill
(gsc-pull appends; dfs-pull is staging-only). Deviate only with an ADR.

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

## CLI protocol (6 stages, one `main()` pass)

> Invocation (manager, or `sf-crawl-orchestrator` subprocess):
>
> ```bash
> python3 -m scripts.ingestion.sf_import \
>     --project <slug> \
>     --sf-export-path projects/<slug>/sf-exports/<date>/ \
>     [--workspace-root <root>]  [--dry-run]
> ```
>
> `--workspace-root` defaults to `$PSEO_WORKSPACE_ROOT`. There are no other
> flags — in particular `--source-run-id` does NOT exist (the `source_run_id`
> *frontmatter* input carries provenance correlation, not a CLI flag).

### Stage A — workspace + path resolution (DURUR #5)

`main(argv)` resolves `--workspace-root` (or `$PSEO_WORKSPACE_ROOT`). Unset →
`print("ERROR: … required (DURUR #5)", file=sys.stderr)` and `return 5`. A
relative `--sf-export-path` is joined onto `workspace_root`.

### Stage B — `validate_export_path` (DURUR #1)

```python
raw_dir = sf_root / "raw" if (sf_root / "raw").is_dir() else sf_root
if not raw_dir.is_dir():
    print(f"ERROR: raw_dir not found at {sf_root} or {sf_root}/raw (DURUR #1)",
          file=sys.stderr)
    return 1
```

### Stage C — `validate_tier1` (sf-required-reports.schema Tier 1 14/14, DURUR #2)

`match_tiers` lives in **`scripts.ingestion.sf_import`** itself (there is no
separate `sf_validate` module). It walks `raw/`, normalizes filenames (lower,
strip `de_` / `v_` / `p_` / `bi_` prefixes, strip `(N)` / `-copy` / `_old`
suffixes, fold Turkish `ı→i`), and matches each canonical_name against
`schemas/sf-required-reports.schema.json` `definitions.canonicalName`. Tier 1
missing → RED FAIL (exit 2). Tier 2 missing → AMBER warn, NOT a fail
(`search_console_all` is the canonical Tier 2 exemption surfaced in pilot
validation).

```python
matched, missing_t1, missing_t2 = match_tiers(raw_dir)   # defined in this module
if missing_t1:
    print(f"ERROR: Tier 1 missing: {sorted(missing_t1)} (DURUR #2)", file=sys.stderr)
    return 2
amber: list[str] = []
if missing_t2:
    amber.append(f"Tier 2 missing (AMBER): {sorted(missing_t2)}")
```

### Stage D — `envelope_inbox` (raw → drift-recoverable JSON, DURUR #6)

First confirm the write target exists; a missing `master.xlsx` → DURUR #6
(exit 6 — `init-project` must have run). Then the `build_envelope` helper
writes a single envelope JSON to `inbox/sf/{date}-{slug}.json` BEFORE any
projection runs — for every matched CSV it captures sha256, row_count,
filename_original + filename_normalized + tier. The envelope is the durable
witness that a given SF batch was observed even if the Excel write fails
downstream.

```python
master_xlsx = workspace_root / "projects" / args.project / "master.xlsx"
if not master_xlsx.exists():
    print(f"ERROR: master.xlsx missing at {master_xlsx} (DURUR #6)", file=sys.stderr)
    return 6
inbox_path = build_envelope(args.project, sf_root, raw_dir, matched, amber, workspace_root)
```

Envelope shape (written by `build_envelope`):

```json
{
  "_meta": { "captured_at": "…Z", "tool": "screaming_frog",
             "project_slug": "<slug>", "sf_export_path": "…",
             "raw_dir": "…", "amber_warnings": ["Tier 2 missing (AMBER): …"] },
  "files": [
    { "canonical_name": "internal_all", "tier": "required",
      "filename_original": "internal_all.csv", "filename_normalized": "internal_all.csv",
      "file_hash": "sha256:…", "row_count": 192 }
  ]
}
```

### Stage E — `sitemap_xcheck` — **Phase-X DEFERRED (not wired)**

> **Status: deferred capability, not part of the shipped contract.** The
> intended cross-check — compare the SF-discovered URL list against the GSC
> submitted sitemaps and log discrepancies into `crawl_sitemap` as a
> diagnostic — is NOT implemented. `main()` goes straight from the envelope
> (Stage D) to the projection write (Stage F); it never calls
> `mcp__gsc__list_sitemaps`, and there is **no `sf_sitemap_xcheck` module**.
> The GSC sitemap tools are therefore `optional` in the frontmatter, and
> DURUR #4 is a deferred-condition placeholder (see DURUR conditions below).
> When this lands (a future Wave) it belongs at the manager/caller layer —
> sf-import's core stays GSC-free, disk-CSV only.

### Stage F — `write_excel` (per-sheet, idempotent replace)

Six `transaction.replace` calls — one per sheet — over the projections
returned by `sf_projection.project_all(raw_dir)`. `replace` (NOT `append`)
clears each sheet's data block then re-lands the rows, so **re-importing the
same batch refreshes rather than duplicates** (idempotent). Each call goes
through the single approved write path with backup, lock, schema validation,
and post-write `tool_computed` provenance emission. The 6 sheets and their
CSV → row projections (inline mapping; the formal `staging-to-excel-map.json`
arrives in Phase 6):

| Logical sheet     | Source CSV(s)                                      | Row shape (master-excel.schema)                                 |
|-------------------|----------------------------------------------------|------------------------------------------------------------------|
| `crawl_sitemap`   | `internal_all`, `sitemaps_all`, `crawl_depth`      | category / metric / value / status / action                       |
| `redirect_404`    | `response_codes_all`, `redirect_chains`            | url / inlinks / action / target_url / status                      |
| `schema`          | `structured_data_all`                              | schema_type / status / location / scope / remaining_work          |
| `on_page_audit`   | `page_titles_all`, `meta_description_all`, `h1_all`| url / target_query / impressions_30d / clicks_30d / in_title /... |
| `tech_seo`        | `issues_overview_report`, `directives_all`         | issue_category / detail / affected_urls / impact / resolution / ... |
| `robots_txt`      | `directives_all`, `indexability`                   | id / level / issue / detail / resolution                          |

In `sf_import.py` this is the `project_and_write` helper:

```python
from scripts.excel import transaction
from scripts.ingestion import sf_projection
projections = sf_projection.project_all(raw_dir)
counts: dict[str, int] = {}
for sheet, rows in projections.items():
    result = transaction.replace(
        master_xlsx, sheet, rows, project_slug, writer="sf-import",
    )
    counts[sheet] = result.rows_affected
```

`transaction.replace` itself emits a `tool_computed` provenance event per
write. Stage F then supplements that with a single `sf_csv` source provenance
record (below) so the data lineage is `sf_csv → tool_computed`. **Idempotency:**
a re-run with the same CSVs replaces the prior rows in place — no duplicate
rows accumulate across re-imports.

### Stage F (cont.) — `sf_csv` source provenance

A single `sf_csv` source-provenance event records the lineage. `source_folder`
is the raw dir relative to the workspace root (via `_rel_to_workspace`, which
falls back to an absolute string for an out-of-tree path rather than crashing);
`row_count` and `rows_written` are the total rows projected across the 6 sheets.
The `run_id` is auto-allocated race-free under the append flock (P1-11).

```python
from scripts.state import events_writer
total_rows = sum(counts.values())
events_writer.append_provenance(
    project_id=project_slug,
    source={
        "kind": "sf_csv",
        "source_folder": _rel_to_workspace(Path(raw_dir), workspace_root),
        "row_count": total_rows,
    },
    operation="ingest",
    rows_written=total_rows,
    workspace_root=workspace_root,
)
```

### Stage G — completion (stdout summary + exit 0)

There is **no `workflow_runner.complete`** and **no string-typed `outputs`
dict** — `main()` prints a human-readable summary to stdout and returns 0 on
success. `--dry-run` stops after the envelope (Stage D), before any Excel write.

```python
print(f"OK: matched {len(matched)} files (Tier1 {t1}/14, Tier2 {t2}/10)")
print(f"Envelope: {inbox_path}")
for w in amber:
    print(f"WARN: {w}")
if args.dry_run:
    print("DRY-RUN: skipping Excel projection.")
    return 0
counts = project_and_write(raw_dir, master_xlsx, args.project,
                           workspace_root=workspace_root)
for sheet, n in counts.items():
    print(f"OK: {sheet} ← {n} rows")
return 0
```

**Exit codes** — the DURUR signalling channel (there is no run-state file):

| Outcome | Exit |
|---------|------|
| Success / `--dry-run` | 0 |
| DURUR #1 — no `raw/` subfolder | 1 |
| DURUR #2 — Tier 1 < 14/14 | 2 |
| DURUR #3 — `RowSchemaError` during projection | non-zero (uncaught traceback) |
| DURUR #5 — no `--workspace-root` / `$PSEO_WORKSPACE_ROOT` | 5 |
| DURUR #6 — no `master.xlsx` | 6 |

## Filename normalization (Tier 1 matching)

The pilot project export ships every Tier 1 file twice: once with the
canonical name (`internal_all.csv`) and once with a `de_` prefix (German
locale shadow `de_internal_all.csv`). Plus a third Turkish-i variant
(`de_ınternal_all.csv`). Normalization rules, applied in order:

1. Lowercase the basename.
2. Drop extension (`.csv`).
3. Strip leading locale shadow prefix `de_` (defensive — pilot artifact).
4. Strip leading export-mode prefix `v_` / `p_` / `bi_` (SF visualization /
   page / bulk-import mode).
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

Stop and flag the manager — do not patch, do not fall back. Each is a
`print(… DURUR #N)` + a distinct exit code (DURUR #3 surfaces as an uncaught
`RowSchemaError` traceback).

1. `sf_export_path` missing or no readable `raw/` subfolder. → exit 1
2. Tier 1 < 14/14 — RED FAIL, do not proceed to projection. → exit 2
3. `transaction.replace` raises `RowSchemaError` for any sheet — the exception
   is NOT swallowed, so the batch aborts with a non-zero (traceback) exit;
   `replace` schema-validates BEFORE clearing, so a rejected sheet is left
   untouched.
4. **(Phase-X deferred, not wired)** — `mcp__gsc__list_sitemaps` sitemap
   cross-check is not implemented in `sf_import.py`; the GSC tools are
   `optional`. When the cross-check lands, a `list_sitemaps` failure becomes
   the DURUR #4 hard stop. Today this condition never fires.
5. `PSEO_WORKSPACE_ROOT` env unset and no `--workspace-root` arg. → exit 5
6. `master.xlsx` missing under `projects/{slug}/` — `init-project`
   must have run first. → exit 6

## Cross-references

- Schemas: `schemas/sf-required-reports.schema.json` (Tier 1 14, Tier 2
  10, canonicalName enum), `schemas/sf-export-mapping.schema.json`
  (filename_alias normalization), `schemas/master-excel.schema.json`
  (6 sheet column structures + statusEnum + severityEnum),
  `schemas/events.schema.json` (`source.kind=sf_csv`),
  `schemas/gsc-tool-mapping.schema.json` (`gsc__list_sitemaps` enum — used by
  the deferred Stage E cross-check, not the shipped core),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/excel/transaction.py` (`replace`),
  `scripts/ingestion/sf_projection.py` (`project_all`),
  `scripts/state/events_writer.py` (`append_provenance`). **NOT**
  `workflow_runner` — sf-import is a plain CLI, not a run shell.
- Tests: `tests/skills/test_sf_import.py` (10 cases: 6-criterion acceptance
  gate incl. live SF batch + `source_run_id` handoff pair + frontmatter
  validation + required-tools parity).
- Pilot data path: `projects/{slug}/sf-exports/{export_date}/raw/`
  (Tier 1 14/14 + Tier 2 9/10 with `search_console_all` AMBER).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7.
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` / `sf_projection` /
      `events_writer` are imported, never modified from this skill.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped). The
      legacy `demo-dental_MASTER.xlsx` (Turkish-emoji) is DOKUNULMAZ.
- [x] Idempotent writes — `transaction.replace` refreshes each sheet's data
      block (re-import does not duplicate); DURUR signalling is exit-code
      based (no `workflow_runner` run shell, no string-typed `outputs`).
