# AC-10 Sheet Projection — Mapping Spec + Implementation Plan

**Date:** 2026-06-02 · **Decision owner:** Süleyman (delegated: "best + safest, meticulous, cross-checked")
**Parent hand-off:** `docs/superpowers/plans/2026-06-02-ac10-sheet-projection-handoff.md`

## DECISION (locked)
**Enum approach = Option (a): ROUTING, no schema change.** `tech_seo.issue_category`
stays the locked 5-value enum (ADR-028). SF issues that fit one of the 5 → `tech_seo`;
directive/security/crawl issues → `robots_txt`; response-code issues → `redirect_404`
(per-URL). The specific SF Issue Name is preserved in the `detail`/`issue` text → zero
data loss. **Evidence:** the 2026-05-14 human-curated import already did exactly this
(tech_seo = only 5-enum issues; security headers + pagination + non-ASCII in robots_txt).
No ADR, no drift-check realignment, no cross-sheet test churn → safest. Honored by both
the projection AND the Task-D tech_audit_transform enum fix (single-source helper).

## ARCHITECTURE (Manager engineering decisions)
- **`scripts/util/sf_issue_taxonomy.py`** (NEW, neutral util) — single source of the
  SF-Issue-Name → (target_sheet, tech_seo issue_category) routing + `sf_priority_to_severity`.
  Imported by BOTH `sf_projection` (ingestion) and `tech_audit_transform` (discovery) so the
  enum fix is single-sourced (no cross-layer coupling: util ← both).
- **`scripts/ingestion/sf_projection.py`** (NEW) — 6 pure mappers, BOM-safe (`utf-8-sig`),
  reuse orchestrator `_clean_key`. No DFS dependency. on_page_audit reuses the live-proven
  `on_page_audit_transform` SF helpers.
- **`scripts/excel/transaction.py`** — ADD `mode="replace"` to `_write_or_append` (today it
  raises on anything but "append"). Replace = clear data rows (data_start_row..max_row,
  preserve header rows) then write, inside the SAME atomic path (backup/lock/validate/
  provenance). Public `replace()` wrapper. Idempotent: re-running yields the same rowcount.
- **`scripts/ingestion/sf_import.py`** Step 6 — replace the stub print with real projection
  calls using `transaction.replace`; Step 7 `sf_csv` provenance event.
- `staging-to-excel-map.json` instance DEFERRED — keyword routing is more expressive as code
  than a static column-map; the JSON-schema artifact remains a future formalization.

## ROUTING TABLE — issues_overview_report.csv (the tech_seo/robots_txt source)
Each row of `issues_overview_report.csv` (one row per issue, pre-aggregated, has a `URLs`
count + `Issue Priority`) routes by Issue-Name keyword. `impact`/`level` ← Issue Priority
(High→HIGH, Medium→MEDIUM, Low→LOW). `detail` ← "{Issue Name} — {Description}". `resolution`
← How To Fix. `affected_urls` ← URLs count.

| SF Issue-Name match (keyword) | → sheet | tech_seo issue_category | demo-aluminum examples |
|---|---|---|---|
| `PageSpeed:` , `Over 100 kB` (large images), `page weight`, `LCP`, `Reduce Unused`, `Speed Index` | tech_seo | **Performance** | PageSpeed Reduce Unused CSS/JS; Images Over 100 kB |
| `Size Attributes`, `Layout Shift`, `CLS` | tech_seo | **Layout Stability** | Images: Missing Size Attributes |
| `Structured Data:` | tech_seo | **Structured Data** | Validation Errors / Warnings |
| `Meta Description:`, `Page Titles:`, `H1:`, `H2:`, `Title`, `Content:` (low content/readability) | tech_seo | **Meta Tags** | Meta Description Missing; H1 Missing; Content Low Content Pages |
| `Alt` (alt attr/text), `Anchor Text`, `Accessibility`, `aria`, `contrast` | tech_seo | **Accessibility** | Images Missing Alt; Links No Anchor Text |
| `Security:`, `URL:` (non-ASCII/encoding), `Pagination:`, `High Crawl Depth`, `Canonical`, `Robots`, `Hreflang`, `Indexab` | robots_txt | — (level←priority) | Security Missing HSTS/CSP; URL Non ASCII; Pagination Not in Anchor; Links High Crawl Depth |
| `Response Codes:` | **SKIP** | — | covered per-URL by redirect_404 (response_codes_all) |
| *(unmatched / future SF issue)* | robots_txt | — (fallback, level←priority) | guarantees schema-valid + no data loss |

**Cross-check requirement:** the implementer MUST add a test asserting all 42 demo-aluminum
issues route to a sheet (none crash, none produce an out-of-enum issue_category). Expected
split ≈ tech_seo 30 / robots_txt 9 / skipped(Response Codes) 3.

## 6 MAPPINGS (source cols → master-excel.schema row)

### crawl_sitemap (category/metric/value/status[statusEnum]/action) — header_row 3
From `internal_all.csv` (+ `sitemaps_all.csv`):
- **Summary (category="Crawl"):** total_urls_discovered, html_pages (Content Type text/html),
  indexable / non_indexable (Indexability col), image_assets (Content Type image/*),
  css_files, js_files. value=count, status=DONE (non_indexable→TODO if >0).
- **Summary (category="Sitemap"):** crawled_count (sitemaps_all rowcount); status=DONE.
- **Summary (category="Depth"):** max_crawl_depth (max Crawl Depth), depth_0/depth_1 counts.
- **Per-URL (category="URL"):** one per HTML page → metric="html_page", value=Address,
  status=EXISTS (Indexable) / TODO (Non-Indexable), action=indexability note.
- demo-aluminum expect: ~13 summary + 66 URL ≈ 79 rows.

### redirect_404 (url/inlinks[int]/action/target_url/status[statusEnum]) — header_row 4
From `response_codes_all.csv`, filter Status Code 3xx OR 4xx AND Address internal (site host):
- url←Address, inlinks←int(Inlinks), target_url←Redirect URL (3xx) / "" (4xx),
  status=TODO, action=templated ("4xx broken: fix or 301 to valid URL; linked {inlinks}× " /
  "3xx: point internal links directly to {target_url}").
- demo-aluminum expect: ~8 internal rows (7 /services/ 301 + portfolio 404; exclude
  external maps.google 301 + 0xx). redirect_chains.csv is header-only (no chains).

### schema (schema_type/status[statusEnum]/location/scope/remaining_work) — header_row 3
From `structured_data_all.csv`, group by `Type-1`:
- schema_type←type, status=EXISTS (0 errors) / ONGOING (Errors>0), location="global (N occurrences)",
  scope="N occurrences", remaining_work="Validate against Schema.org" (+"; fix N validation errors").
- demo-aluminum expect: 2 rows (Article 13, BreadcrumbList 45; 0 errors).
- **Documented limit:** raw SF gives only Type-1 → shallow vs the human's 17-row gap-analysis
  (missing-type rows = DFS/human enrichment, not raw-CSV-derivable).

### on_page_audit (url/target_query/impressions_30d[int]/clicks_30d[int]/in_title[bool]/in_meta[bool]/in_h1[bool]/action) — header_row 4
REUSE `scripts/discovery/on_page_audit_transform.py` SF-merge path (`_sf_row_to_audit_row` +
`_merge_live_findings`, live-proven 2026-06-02). Feed live_findings = merged `page_titles_all`
+ `meta_description_all` + `h1_all` (per-URL), empty content_parsing + gsc_rows.
- impressions_30d/clicks_30d = 0 (no GSC), target_query = "" (or page title token), in_*=presence.
- demo-aluminum expect: 58 rows (in_title 58 / in_meta 26 / in_h1 38 — matches the live consumer).

### tech_seo (issue_category[5-enum]/detail/affected_urls/impact[severityEnum]/resolution/priority) — header_row 3
From `issues_overview_report.csv` via ROUTING TABLE (rows routed to tech_seo only):
- issue_category←routing, detail←"{Issue Name} — {Description}"[trim], affected_urls←URLs,
  impact←priority→severity, resolution←How To Fix, priority←band ("P0" HIGH/"P1" MEDIUM/"P2" LOW)
  or reuse the severity word (free-form col — match existing convention "P0".."P3").
- demo-aluminum expect: ~30 rows (granular, 1:1 with SF issues; human had 20 via manual merges).

### robots_txt (id/level[severityEnum]/issue/detail/resolution) — header_row 4
From `issues_overview_report.csv` routed to robots_txt (Security/URL/Pagination/crawl-depth +
fallback). Also directive/indexability signals from `directives_all.csv` if surfaced:
- id←sequential ("R-001"… free-form; NOT taskIdPattern), level←priority→severity,
  issue←Issue Name, detail←Description[trim], resolution←How To Fix.
- demo-aluminum expect: ~9 rows (6 Security + URL non-ASCII + Pagination + high-crawl-depth).

## TASK BREAKDOWN (subagent-driven; Manager live-validates each)
- **A. transaction.replace mode** (TDD; regression-risk core path) — append byte-identical, replace clears+writes, idempotent, schema still enforced.
- **B. sf_issue_taxonomy.py + sf_projection.py** (TDD; fixtures = real staged CSVs) — 6 mappers + routing helper; all 42 issues route; every row schema-valid.
- **C. wire sf_import.py Step 6 + Step 7** — projection calls via transaction.replace + sf_csv provenance.
- **D. fix tech_audit_transform `_live_finding_to_finding`** to use sf_issue_taxonomy (Task-4 enum bug; single-source).
- **E. LIVE cross-check (Manager)** — run projection on 22 staged CSVs → replace 6 sheets → assert no RowSchemaError, sane rowcounts, provenance event; fresh master.xlsx backup first.
- **F. full pytest green + release v1.9.4** (operator-gated: Y-05 --apply + RELEASE_NOTES + tag + push).

## INVARIANTS
- 🔴 F-16 `.mcp.json` 543B / md5 `93523d41e14f90916fefb86d346bd702` — never touch.
- master-excel.schema.json UNCHANGED (the whole point of Option a).
- pytest baseline 1338 PASS / 11 SKIP / 0 FAIL (local SF-up) — new tests additive.
- Atomic commits; push + workspace-repo writes operator-gated.
