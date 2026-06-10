---
name: facet-nav-audit
description: |
  Use when: kullanıcı "faceted navigation", "facet audit", "parametre temizliği",
  "crawl budget", "index bloat", "filtre URL'leri indexleniyor", "sort/sayfalama
  parametreleri", "?sirala= / ?renk= URL'leri", "sonsuz parametre alanı" der ya da
  /pseo-facet-audit çağırır. Free (paid MCP yok) — SF export + master.xlsx okur.
  Also use when: aktif projenin SF crawl export'u alındı
  (projects/{slug}/sf-exports/{date}/raw/internal_all.csv); e-ticaret platformu
  (WooCommerce/Ticimax/Ideasoft/imagaza) parametre URL'leri üretiyor; bulgular
  master.xlsx#robots_txt sheet'ine FN- prefix'li yazılacak + önerilen robots.txt
  bloğu raporda üretilecek (recommendation-only, operator deploy eder).
  Do not use when: SF export henüz yok (sf-import önce, DURUR #1); robots.txt
  lifecycle/noindex denetimi (robots-policy-audit, ayrı); tech-audit / schema-audit
  / hreflang-audit gerekiyor; master.xlsx yokken (init-project önce).
version: "1.0"
status: wip
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json + sf-exports/."
  sf_export_date:
    type: string
    required: false
    description: "sf-exports/{date}/ dir to read; default = latest export dir."
  policy_overrides_path:
    type: string
    required: false
    description: "Per-project param taxonomy override; default projects/{slug}/config/facet-policy.json when present (schemas/facet-policy.schema.json). Overrides heuristic seeds (R-128)."
  unknown_param_threshold:
    type: integer
    required: false
    default: 10
    description: "Unknown-class URL count at/above which an operator-triage finding (LOW) fires (R-128)."
outputs:
  - "master.xlsx#robots_txt"
  - "outputs/reports/{date}-facet-nav-audit.md"
  - "events.jsonl"
consumes:
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/internal_all.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/response_codes_all.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/directives_all.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/canonicals_all.csv"
  - "init-project:projects/{slug}/project.config.json"
  - "cluster-map:master.xlsx#cluster_keywords"
  - "gsc-pull:master.xlsx#gsc_performance"
produces:
  - "drift-check"
  - "robots-policy-audit"
triggers:
  manual: ["/pseo-facet-audit"]
  natural_language: |
    "faceted navigation", "facet audit", "parametre URL", "crawl budget",
    "index bloat", "filtre URL indexleniyor", "sort parametreleri", "?sirala="
  hooks: []
mcp_tools:
  required: []
  optional:
    - "mcp__sf__sf_list_crawls"
    - "mcp__sf__sf_load_crawl"
    - "mcp__sf__sf_export_seo_element_urls"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# facet-nav-audit — discovery skill (GAP-T2, FREE)

Faceted-navigation / parameter & crawl-budget governance per
`rules/tech-seo-governance.md` **R-128 (Parameter Taxonomy)**, **R-129
(Index-Bloat Budget)**, **R-130 (Blocking-Mechanism Decision Tree)**. SF's
Issues-Overview can say "you have pagination issues"; this skill says "38% of
the crawl is `?sirala=` sorts and 4,200 of them are indexable" — URL-corpus-level
quantification SF cannot give.

**Recommendation-only (R-130).** The engine NEVER writes to client
infrastructure (robots.txt, CMS, server). It emits findings (`master.xlsx#robots_txt`,
`FN-` prefix) + a proposed robots.txt block (report text) + per-class actions; the
**operator deploys**. The Excel write is behind the standard `request_approval`
gate. No paid MCP, no DataForSEO calls (demand evidence is read from the existing
`master.xlsx#cluster_keywords` / `#gsc_performance` sheets).

## Inputs (frontmatter contract)

| Name                     | Type    | Default | Notes                                              |
|--------------------------|---------|---------|----------------------------------------------------|
| `project_slug`           | string  | —       | Required. Resolves master.xlsx + sf-exports/.      |
| `sf_export_date`         | string  | latest  | sf-exports/{date}/ dir to read.                    |
| `policy_overrides_path`  | string  | config/facet-policy.json | Per-project taxonomy override (R-128). |
| `unknown_param_threshold`| integer | 10      | Unknown-URL count → operator-triage finding.       |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` (mirrors tech-audit
§Inputs).

## Outputs

- `master.xlsx#robots_txt` — `FN-NNN` findings (5-col: id/level/issue/detail/
  resolution; `level` is severityEnum). Written via
  `scripts/util/sheet_merge.merge_prefixed_rows(..., id_prefix="FN-")` — idempotent
  re-runs, preserves sf_projection `R-NNN` and hreflang-audit `HF-` / robots-
  policy-audit `RP-` rows. **sf-import's `transaction.replace` wipes the sheet →
  re-run this audit after every sf-import** (it is free and reads the same export).
- `outputs/reports/{date}-facet-nav-audit.md` — param-class table + bloat metrics
  + the proposed robots.txt block + demand-evidence table.
- `events.jsonl` — `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="robots_txt")`.

## Body protocol

Mirrors tech-audit's shape minus the budget pre-flight (this skill is free).

1. **create_run** — `workflow_runner.create_run(skill="facet-nav-audit", ...)`.
2. **read inputs** — resolve latest `sf-exports/{date}/raw/`; read `internal_all.csv`
   (Address + Indexability + Crawl Depth + Canonical columns), `response_codes_all.csv`,
   `directives_all.csv`, `canonicals_all.csv`; read `master.xlsx#cluster_keywords`
   + `#gsc_performance` (openpyxl, read-only) → `demand_keywords` (terms with
   volume/impressions > 0); load `policy_overrides_path` if present (validate
   against `schemas/facet-policy.schema.json`).
3. **transform** (pure) —
   ```python
   from scripts.discovery import facet_nav_audit_transform as fnt
   out = fnt.transform(
       internal_rows, response_rows, directives_rows, canonical_rows,
       pagination_rows, demand_keywords, platform, url_patterns,
       policy_overrides=overrides, unknown_param_threshold=threshold,
   )
   ```
   Classifies every URL's params into the R-128 closed set
   `{facet_filter, sort, pagination, internal_search, session_or_tracking, functional, unknown}`,
   quantifies per-class index-bloat (R-129), emits `FN-` findings + a deterministic
   `proposed_robots_block` (R-130). Platform seeds are HEURISTIC and conservative:
   generic web + WooCommerce param names only; Ticimax/Ideasoft/imagaza and
   non-English vocabularies route to the `unknown`-triage finding by design —
   the operator classifies them in `facet-policy.json` (this is the designed path,
   not a gap). **v1 limitation:** zero-result/soft-404 facet detection and
   path-segment facets are DEFERRED (the SF export does not carry the content
   signal needed) — noted here so no fake finding is emitted.
4. **request_approval** — `request_approval(...)` ("N facet finding'i
   master.xlsx#robots_txt'ye yazalım mı?"); skill EXIT awaiting_approval.
5. **write_excel** — on approve, `sheet_merge.merge_prefixed_rows(master_xlsx,
   "robots_txt", out["robots_txt_rows"], id_prefix="FN-", run_id=..., project_slug=...,
   writer="facet-nav-audit")` (single idempotent committer.commit path).
6. **render_report** — `render_template.py templates/reports/facet-nav-audit.template.md`
   → `outputs/reports/{date}-facet-nav-audit.md` (includes the proposed robots.txt
   block as recommendation text).
7. **provenance event** — `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="robots_txt", rows_written=len(rows))`.
8. **complete** — `workflow_runner.complete(...)` with string-typed outputs.

### Optional live SF mode

Mirror tech-audit's `use_sf_mcp_live` branch (`mcp__sf__sf_list_crawls` →
`sf_load_crawl` → `sf_export_seo_element_urls` for the Internal element) to source
`internal_all` live; AMBER fallback to file-based on any SF MCP error (never hard
fail). Default: file-based.

## DURUR conditions

Stop and flag the manager — do not patch, do not fabricate.

1. `internal_all.csv` missing (`FacetInternalMissingError`) — run sf-import first.
2. Address column absent in `internal_all.csv` (`FacetSchemaDriftError`) — re-export
   with default data_fields or use live SF mode.
3. URL corpus > 250k rows (`FacetUrlCapExceededError`) — surface to manager, suggest
   chunking the crawl.
4. Zero usable URLs parsed (`FacetSchemaDriftError`).
5. `master.xlsx#robots_txt` row schema mismatch on write (`RowSchemaError`).
6. `PSEO_WORKSPACE_ROOT` unset and no `workspace_root` arg.

## Cross-references

- Rules: `rules/tech-seo-governance.md` (R-128 / R-129 / R-130).
- Transform: `scripts/discovery/facet_nav_audit_transform.py` (pure;
  `transform`, `FacetNavAuditError` hierarchy, `PARAM_CLASSES`).
- Write path: `scripts/util/sheet_merge.py` (`merge_prefixed_rows`, prefix `FN-`).
- Schemas: `schemas/master-excel.schema.json#robots_txt` (5-col + severityEnum),
  `schemas/facet-policy.schema.json` (optional override), `schemas/events.schema.json`.
- Template: `templates/reports/facet-nav-audit.template.md`.
- Command: `commands/pseo-facet-audit.md`.

## Discipline checklist

- [x] Recommendation-only — engine never deploys to client infra (R-130).
- [x] Free — `budget.uses_paid_mcp=false`; demand evidence from master.xlsx, no DFS.
- [x] Schema-first — frontmatter validates against `skills/skill-frontmatter.schema.json`;
      `FN-` rows validate against `master-excel.schema.json#robots_txt`.
- [x] Plugin-agnostik — no slug literals; pure transform; platform seeds heuristic,
      unknowns → operator-triage (no invented platform params).
- [x] Idempotent write — `sheet_merge.merge_prefixed_rows` re-lands the `FN-`
      namespace in place; foreign `R-`/`HF-`/`RP-` rows preserved.
- [x] Append-only — provenance via `events_writer`.
