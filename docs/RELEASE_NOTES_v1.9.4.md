# Platinum SEO Engine — v1.9.4 Release Notes

**Release date:** 2026-06-02
**Engine HEAD:** v1.9.4 release commit (5-file sync via Y-05 seventh production `--apply`)
**Predecessor:** [v1.9.3](RELEASE_NOTES_v1.9.3.md) (SF MCP live-hardening — transport + retry + orchestrator export + resilient load)
**Status:** 🟢 GREEN — AC-10 sheet projection (sf-import Step 6) is now **live-proven** against the real demo-aluminum 1822-URL crawl: a live `sf_import` repopulates master.xlsx's 6 SF-derived sheets, schema-valid + idempotent. F-16 `.mcp.json` 543B/md5 `93523d41e14f90916fefb86d346bd702` UNCHANGED. `schemas/master-excel.schema.json` UNCHANGED (the enum decision required no schema change).

## 0. Executive Summary

v1.9.4 completes the **last deferred piece of the SF MCP integration**: the per-sheet projection (`sf-import` Step 6 `write_excel`). Before this release, `scripts/ingestion/sf_import.py` did Tier-validation + envelope only and printed *"Run per-sheet projection separately"* — so a live SF import left the 6 SF sheets unchanged (the `OQ-SHEET-PROJECTION` open question). This release builds the raw-SF-CSV → master.xlsx row projection and wires it into the live chain.

**The deep lesson, again:** *code-ready ≠ live-proven.* The independent Manager live cross-check (running the projection against the **real** workbook + real crawl, not mocks) caught two latent defects that 1400+ passing tests had not exercised:
1. **`transaction` had no replace mode** — only `append`. The hand-off assumed `write(mode=…)` already supported replacement; it did not (it raised on any non-`"append"` mode). A blind append onto sheets that already hold prior-run data would have **duplicated** every row.
2. **`tech_audit_transform._heading_findings` emitted `category="Headings"`** — an out-of-enum value on the DFS path (sibling of the known SF-path bug). It would raise `RowSchemaError` on the real schema-validated write, yet slipped through every mock test because the findings were never written to a real workbook.

### The central decision — `tech_seo.issue_category` enum (no schema change)
SF's `issues_overview_report` carries ~13 issue families (Images, Security, Pagination, Response Codes, …) but `tech_seo.issue_category` is a **schema-locked 5-value enum** (Performance / Layout Stability / Meta Tags / Structured Data / Accessibility, ADR-028). Rather than expand the enum (a schema change → new ADR + drift-check realignment), v1.9.4 **routes** issues: the 5-enum-fitting ones → `tech_seo`; security/directive/crawl issues → `robots_txt`; response-code issues → `redirect_404` (per-URL). The specific SF Issue Name is preserved in `detail`/`issue` → **zero data loss, zero schema change**. This is exactly what the 2026-05-14 human-curated import already did — the routing is evidence-grounded, not invented.

**pytest 1338 → 1427 PASS / 11 SKIP / 0 FAIL** (+89 across the cycle; regression sıfır). `.mcp.json` UNCHANGED 543B/md5 (F-16). `schemas/master-excel.schema.json` UNCHANGED. `DECISIONS.md` UNCHANGED; NO new ADR.

## 1. transaction.replace — idempotent sheet refresh (`6db5551`)
`scripts/excel/transaction.py` gains `mode="replace"` + a public `replace()` wrapper. Replace clears a sheet's data block (preserving the header rows `1..data_start_row-1`) then re-lands rows at the schema's `data_start_row`, inside the SAME atomic path (backup → lock → schema-validate → save → provenance). Append stays byte-identical. Idempotent: re-running `sf_import` refreshes, never duplicates. +5 tests using realistic template-seeded fixtures (header_row 3 AND 4), incl. a "validate-before-clear" guard (a bad payload raises before any `delete_rows`).

## 2. sf_projection + sf_issue_taxonomy (`294f0db`)
- **`scripts/util/sf_issue_taxonomy.py`** (NEW) — single-source `route_sf_issue(issue_name) → (sheet, tech_seo_category)` + `sf_priority_to_severity`. Keyword routing, first-match-wins, specific-before-broad; unmatched → `robots_txt` (safe fallback, never out-of-enum).
- **`scripts/ingestion/sf_projection.py`** (NEW) — 6 pure, BOM-safe mappers (`crawl_sitemap`, `redirect_404`, `schema`, `on_page_audit`, `tech_seo`, `robots_txt`) + `project_all(raw_dir)`. `on_page_audit` reuses the live-proven `on_page_audit_transform` SF-merge path (3-export per-URL merge of page_titles + meta_description + h1). +67 tests, incl. a schema-validation cross-check asserting every projected row passes `transaction`'s validator.

## 3. sf_import Step 6 + Step 7 wiring (`cb6dc0b`)
`main()` now calls `project_and_write(...)`: `project_all` → `transaction.replace` per sheet → one `sf_csv` source-provenance event (lineage `sf_csv → tool_computed`). `--dry-run` unchanged. +7 tests incl. the idempotency AC (run twice → identical rowcounts) and provenance assertions.

## 4. tech_audit enum fixes (`9cf5dd3` + `000ed40`)
- `_live_finding_to_finding` now routes SF Issue Names through `sf_issue_taxonomy` → only valid 5-enum `tech_seo` rows (non-tech_seo issues dropped; they belong to robots_txt/redirect_404). 42 real demo-aluminum issues: was 42/42 out-of-enum → now 30 in tech_seo (0 out-of-enum), 12 routed away.
- `_heading_findings` now emits `Meta Tags` (was the out-of-enum `Headings`). `CATEGORY_HEADINGS` removed. A **guard test** reads the live schema enum and asserts every `CATEGORY_*` constant ∈ it — locking the bug class shut.

## 5. Live cross-check (demo-aluminum, 2026-06-02)
A real `sf_import` CLI run against the 22 staged raw CSVs + the real master.xlsx:
| sheet | rows written | schema errors |
|---|---|---|
| crawl_sitemap | 74 | 0 |
| redirect_404 | 8 | 0 |
| schema | 2 | 0 |
| on_page_audit | 58 (in_title 58 / in_meta 26 / in_h1 38) | 0 |
| tech_seo | 30 (all 5-enum) | 0 |
| robots_txt | 9 | 0 |

**0 total schema errors · idempotent (2nd run identical, no growth) · `sf_csv` provenance event emitted · drift-check 23/24 PASS** (the lone non-PASS = F-15 cannibalization manual-triage AMBER, by-design and unrelated to the SF sheets; F-08 — the crawl_sitemap-dependent cross-sheet invariant — PASSES, confirming cross-sheet integrity).

## 6. Invariants held
- 🔴 F-16 `.mcp.json` 543B/md5 `93523d41e14f90916fefb86d346bd702` UNCHANGED.
- `schemas/master-excel.schema.json` UNCHANGED — the routing decision deliberately avoided a schema/enum change.
- pytest 1427 PASS / 11 SKIP / 0 FAIL. `DECISIONS.md` UNCHANGED; NO new ADR.

## 7. Known limitations
- `schema` sheet projection is shallow by nature: raw SF `structured_data_all` exposes only `Type-1` (Article + BreadcrumbList for demo-aluminum). The deeper multi-type + "missing schema" gap-analysis remains a DFS/human-enrichment concern (`schema_audit_transform`), not raw-CSV-derivable.
- `detail` text is capped (~300 chars) — the full SF Description tail may truncate; the SF Issue Name is always preserved at the front.
