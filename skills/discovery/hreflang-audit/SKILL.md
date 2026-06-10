---
name: hreflang-audit
description: |
  Use when: kullanıcı "hreflang audit", "hreflang denetimi", "i18n", "dil
  versiyonları", "uluslararası SEO", "x-default", "hreflang reciprocity",
  "tek-yönlü hreflang", "yanlış dil/bölge kodu", "en-UK" der ya da
  /pseo-hreflang-audit çağırır. Free (paid MCP yok) — SF hreflang export okur.
  Also use when: aktif projenin SF crawl export'u alındı
  (projects/{slug}/sf-exports/{date}/raw/hreflang_all.csv); çok-dilli bir müşteri
  imzalandı; bulgular master.xlsx#robots_txt'ye HF- prefix'li yazılacak. TEK DİLLİ
  portföyde (tr-TR / en-CA / en-NG) ucuz hijyen kontrolü: stray hreflang yoksa
  NOT_APPLICABLE (hreflang yokluğu doğru, kusur değil).
  Do not use when: faceted-nav / parametre denetimi (facet-nav-audit, ayrı);
  robots.txt/noindex lifecycle (robots-policy-audit, ayrı); SF export yok
  (sf-import önce, DURUR); master.xlsx yokken (init-project önce). NOT: motor
  hreflang ÜRETMEZ (çok-dilli istemci + platform write access yok) — sadece dener.
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
  use_sf_mcp_live:
    type: boolean
    required: false
    default: false
    description: "Mirror tech-audit's live SF branch (list_crawls → load_crawl → export Hreflang element); AMBER fallback to file-based on any SF MCP error. Default false (file-based)."
outputs:
  - "master.xlsx#robots_txt"
  - "outputs/reports/{date}-hreflang-audit.md"
  - "events.jsonl"
consumes:
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/hreflang_all.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/canonicals_all.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/internal_all.csv"
  - "init-project:projects/{slug}/project.config.json"
produces:
  - "drift-check"
triggers:
  manual: ["/pseo-hreflang-audit"]
  natural_language: |
    "hreflang audit", "hreflang denetimi", "i18n", "dil versiyonları",
    "x-default", "hreflang reciprocity", "tek-yönlü hreflang", "en-UK"
  hooks: []
mcp_tools:
  required: []
  optional:
    - "mcp__sf__sf_list_crawls"
    - "mcp__sf__sf_load_crawl"
    - "mcp__sf__sf_export_seo_element_urls"
    - "mcp__gsc__index_inspect"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# hreflang-audit — discovery skill (GAP-T1, FREE)

hreflang / i18n governance per `rules/tech-seo-governance.md` **R-125 (Cluster
Reciprocity)**, **R-126 (Code & x-default Validity)**, **R-127 (Locale
Consistency, config ↔ site)**. Computes the reciprocity graph from
`hreflang_all.csv`, validates codes + x-default, and joins return targets against
`internal_all` indexability + `canonicals_all` — deeper, computed findings than
SF's Issues-Overview "you have hreflang issues" (which already routes to the same
`robots_txt` sheet via `sf_issue_taxonomy` keyword `hreflang`; no taxonomy change).

**Single-language portfolio reality.** The entire current portfolio is
single-language (tr-TR / en-CA / en-NG). With zero hreflang annotations the audit
returns **`verdict: NOT_APPLICABLE`** with empty findings and a rendered report —
absence of hreflang is correct, not a defect. The skill fully validates clusters
the moment a multi-language client signs.

**Recommendation-only.** The engine emits findings (`master.xlsx#robots_txt`,
`HF-` prefix) + a report; the **operator** fixes the site (the engine has no
`<head>`/sitemap write access and ships no hreflang *generator* — there is no
multi-language client yet). The Excel write is behind the standard
`request_approval` gate. No paid MCP (GSC `index_inspect` is optional spot-check
only; there is no GSC hreflang surface).

## Outputs

- `master.xlsx#robots_txt` — `HF-NNN` findings (5-col: id/level/issue/detail/
  resolution; `level` is severityEnum). Written via
  `scripts/util/sheet_merge.merge_prefixed_rows(..., id_prefix="HF-")` — idempotent
  re-runs, preserves sf_projection `R-NNN` and facet-nav `FN-` / robots-policy `RP-`
  rows. **sf-import's `transaction.replace` wipes the sheet → re-run hreflang-audit
  after every sf-import** (it is free and reads the same export dir).
- `outputs/reports/{date}-hreflang-audit.md` — verdict + cluster count + findings
  table (+ a NOT_APPLICABLE note on single-language sites).
- `events.jsonl` — `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="robots_txt")`.

## Body protocol

Mirrors tech-audit's shape minus the budget pre-flight (this skill is free).

1. **create_run** — `workflow_runner.create_run(skill="hreflang-audit", ...)`.
2. **read inputs** — resolve latest `sf-exports/{date}/raw/`; read `hreflang_all.csv`
   (page Address + `HTML hreflang N` / `HTML hreflang N URL` columns),
   `canonicals_all.csv`, `internal_all.csv` (Indexability + Status + Canonical);
   read `project.config.json[language.content_locale]`.
3. **transform** (pure) —
   ```python
   from scripts.discovery import hreflang_audit_transform as hat
   out = hat.transform(hreflang_rows, canonical_rows, internal_rows, content_locale)
   ```
   Computes reciprocity (R-125), validates codes + x-default (R-126), checks
   config↔site locale consistency (R-127); joins return targets against
   indexability/canonical/status. Zero annotations + single locale →
   `verdict: NOT_APPLICABLE`, empty rows. The code validator is **permissive**
   (never RED on an exotic-but-valid code like `zh-Hant-TW`) but flags the
   documented `uk`→`gb` region mistake.
4. **request_approval** — `request_approval(...)` ("N hreflang finding'i
   master.xlsx#robots_txt'ye yazalım mı?"); skill EXIT awaiting_approval.
5. **write_excel** — on approve, `sheet_merge.merge_prefixed_rows(master_xlsx,
   "robots_txt", out["robots_txt_rows"], id_prefix="HF-", run_id=..., project_slug=...,
   writer="hreflang-audit")` (single idempotent committer.commit path).
6. **render_report** — `render_template.py templates/reports/hreflang-audit.template.md`
   → `outputs/reports/{date}-hreflang-audit.md`.
7. **provenance event** — `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="robots_txt", rows_written=len(rows))`.
8. **complete** — `workflow_runner.complete(...)` with string-typed outputs.

### Optional live SF mode

Mirror tech-audit's `use_sf_mcp_live` branch (`mcp__sf__sf_list_crawls` →
`sf_load_crawl` → `sf_export_seo_element_urls` for the **Hreflang** element) to
source `hreflang_all` live; AMBER fallback to file-based on any SF MCP error
(never hard fail). Default: file-based.

## DURUR conditions

Stop and flag the manager — do not patch, do not fabricate.

1. `hreflang_all.csv` missing — run sf-import first (or use live SF mode).
2. `hreflang_all.csv` has rows but no recognisable `HTML hreflang N` columns
   (`HreflangSchemaDriftError`) — re-export with default data_fields or use live mode.
3. `master.xlsx#robots_txt` row schema mismatch on write (`RowSchemaError`).
4. `PSEO_WORKSPACE_ROOT` unset and no `workspace_root` arg.

> **NOT a DURUR:** zero hreflang on a single-language site → `NOT_APPLICABLE`
> verdict with an empty finding set and a rendered report (the designed
> portfolio-wide hygiene pass).

## Cross-references

- Rules: `rules/tech-seo-governance.md` (R-125 / R-126 / R-127).
- Transform: `scripts/discovery/hreflang_audit_transform.py` (`transform`,
  `HreflangAuditError`, `HreflangSchemaDriftError`).
- Write path: `scripts/util/sheet_merge.py` (`merge_prefixed_rows`, prefix `HF-`).
- Schemas: `schemas/master-excel.schema.json#robots_txt` (5-col + severityEnum),
  `schemas/events.schema.json`.
- Template: `templates/reports/hreflang-audit.template.md`.
- Command: `commands/pseo-hreflang-audit.md`.
- Open question (report it, do not build): no `language.alternates` array exists in
  `project-config.schema.json` yet — defer until a real multi-language client signs.

## Discipline checklist

- [x] Recommendation-only — engine never deploys; ships no hreflang generator (R-125).
- [x] Free — `budget.uses_paid_mcp=false`; no DFS; GSC index_inspect optional spot-check only.
- [x] Single-language PASS-trivial — zero hreflang + single locale → NOT_APPLICABLE (R-126).
- [x] Permissive codes — never RED on exotic-but-valid (zh-Hant-TW); flags documented uk→gb mistake (R-126).
- [x] Schema-first — frontmatter validates; `HF-` rows validate against `master-excel.schema.json#robots_txt`.
- [x] Plugin-agnostik — no slug literals; pure transform.
- [x] Idempotent write — `merge_prefixed_rows` re-lands the `HF-` namespace; foreign `R-`/`FN-`/`RP-` rows preserved.
- [x] Append-only — provenance via `events_writer`.
