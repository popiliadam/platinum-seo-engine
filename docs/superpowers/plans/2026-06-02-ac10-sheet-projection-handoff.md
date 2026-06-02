# PSEO — AC-10 Sheet Projection (sf-import Step 6) — Fresh-Session Hand-off

Operator = Süleyman (non-coder, SEO expert, Turkish; tables + ★ insights + 2-3 option+recommendation; evidence-based; HE decides; push/destructive ops operator-gated). Repo: `/Users/apple/Documents/platinum-seo-engine` (branch main). Workspace (separate repo): `/Users/apple/Documents/platinum-seo-workspace`.

## WHAT'S ALREADY DONE (do NOT redo)
- **v1.9.3 SHIPPED + PUSHED** (tag `v1.9.3` @ `ae27ac2`): SF MCP live-hardening — MCP Streamable-HTTP transport + retry-on-busy + 29/29 tools live-proven + sf-crawl-orchestrator export dispatch (24→SF-tool mapping + NDJSON→CSV) + resilient `load_crawl`.
- **Consumer live-mode COMPLETE + live-proven + PUSHED** (HEAD `6c6c814`): AC-13 tech-audit live merge (`6ee6fb9`) + 3 consumers internal-links/schema-audit/on-page-audit (`c193ec0`). OQ-FILEPATH-EXPORTS RESOLVED (all 4 consumers + orchestrator use `file_path`).
- **2 live-caught bugs fixed** (mock tests missed both): (1) SF native-CSV exports carry a UTF-8 BOM → `csv.DictReader` first key `'﻿"Col"'` drops rows → fix = `utf-8-sig` read + transform `_clean_key`; (2) on-page-audit `page_titles_all` has ONLY Title columns → meta/h1 falsely missing → fix = export all 3 (page_titles + meta_description + h1) merged per-URL.
- pytest **1338 PASS / 11 SKIP / 0 FAIL** (local SF-up; the live smoke runs). CI (SF down): smoke skips → 1337/12. F-16 `.mcp.json` 543B / md5 `93523d41e14f90916fefb86d346bd702` UNCHANGED throughout.
- **Workspace prep done:** `demo-aluminum-ca/project.config.json` migrated 1.3→1.5 + `sf.mcp.enabled=true` + `allowed_directory=/Users/apple/seo_spider_mcp_server` (UNCOMMITTED in workspace repo — operator's data repo). **22 raw SF CSVs already staged:** `/Users/apple/Documents/platinum-seo-workspace/projects/demo-aluminum-ca/sf-exports/2026-06-02/raw/` (the live AC-10 orchestrator run output).

## THE REMAINING TASK: AC-10 sheet projection (sf-import Step 6 `write_excel`)
**Goal:** complete the live chain so a fresh SF crawl populates master.xlsx's 6 SF-derived sheets. Today `scripts/ingestion/sf_import.py` does Tier-validation + envelope ONLY — it prints `"Run per-sheet projection separately (SKILL.md Step 6 transaction.append calls)"`. The per-sheet projection (raw CSV → master.xlsx rows) is **`skills/ingestion/sf-import/SKILL.md` Step 6 PROSE** ("inline mapping; formal `staging-to-excel-map.json` arrives in Phase 6"). **This is the deferred Phase-6 work.** The 6 sheets currently hold prior-run data (e.g. crawl_sitemap 82 rows) — a live import must REFRESH them.

### The 6 sheets — CSV sources → row shape (master-excel.schema, EXACT)
| Sheet | Source CSV(s) | Row shape (col→name[type/enum]) |
|---|---|---|
| `crawl_sitemap` | internal_all, sitemaps_all, crawl_depth | category / metric / value / status[statusEnum] / action |
| `redirect_404` | response_codes_all, redirect_chains | url / inlinks[int] / action / target_url / status[statusEnum] |
| `schema` | structured_data_all | schema_type / status[statusEnum] / location / scope / remaining_work |
| `on_page_audit` | page_titles_all, meta_description_all, h1_all | url / target_query / impressions_30d[int] / clicks_30d[int] / in_title[bool] / in_meta[bool] / in_h1[bool] / action |
| `tech_seo` | issues_overview_report, directives_all | issue_category[**enum: Performance, Layout Stability, Meta Tags, Structured Data, Accessibility**] / detail / affected_urls / impact[severityEnum] / resolution / priority |
| `robots_txt` | directives_all, indexability | id / level[severityEnum] / issue / detail / resolution |

- `statusEnum` = TODO, ONGOING, EXISTS, DONE, BLOCKED, DEFERRED, CANCELED
- `severityEnum` = CRITICAL, HIGH, MEDIUM, LOW

### 🔴 THE CENTRAL CHALLENGE (judgment-heavy — this is why it's a dedicated session)
`transaction.append(workbook_path, sheet, rows, project_slug, schema_path=, ...)` (`scripts/excel/transaction.py:612`) **VALIDATES every row against master-excel.schema** → `RowSchemaError` on any enum/type violation. So the projection MUST map raw SF CSV columns → SCHEMA-VALID rows. The hard parts:
1. **`tech_seo.issue_category` is a closed 5-value enum** (Performance/Layout Stability/Meta Tags/Structured Data/Accessibility) — but SF `issues_overview_report` has DOZENS of categories ("Images: Missing Size Attributes", "Pagination: …", "Canonicals: …"). **⚠️ KNOWN ISSUE:** the AC-13 tech-audit live merge (`tech_audit_transform._live_finding_to_finding`) maps SF `Issue Name`→`issue_category` directly → produces OUT-OF-ENUM values (live-confirmed e.g. "Pagination: Pagination URL Not in Anchor Tag"). That passes the transform (no enum check there) but would FAIL `transaction.append`. **The fresh session must decide + fix:** (a) map SF issue categories → one of the 5 enum values (keyword/Issue-Type heuristic; put the specific SF name in `detail`), OR (b) expand the schema enum (schema change → drift-check + ADR implications), OR (c) a `csr`-style normalization. This affects BOTH the projection's tech_seo mapping AND the AC-13/consumer master.xlsx WRITE step (currently stub-mod prose, not yet run — that's why it wasn't caught). Verify the same for `schema.status`/`robots_txt.level`/etc.
2. **Idempotency:** `transaction.append` APPENDS. Re-projecting onto sheets that already hold prior data DUPLICATES. Design a replace/clear-then-write (transaction has `write(mode=…)` + `update(where=, set_=)`) so a re-import refreshes rather than duplicates.
3. **Semantic mapping** for the 3 sheets WITHOUT an obvious transform (crawl_sitemap, redirect_404, robots_txt) — e.g. crawl_sitemap as category/metric/value summary rows from internal_all+sitemaps; redirect_404 from response_codes 3xx/4xx rows.

### Relationship to existing transforms (INVESTIGATE — possible reuse)
The discovery transforms already produce 3 of these sheet shapes (from DFS + optional SF live): `tech_audit_transform`→tech_seo, `schema_audit_transform`→schema, `on_page_audit_transform`→on_page_audit (all live-validated this session). But sf-import's projection is a SEPARATE raw-SF-CSV path (no DFS input). Decide: reuse the transforms (feed SF rows as `live_findings`/`raw_sf` with empty DFS) vs author dedicated sf-import projection mappings. `internal_links_transform`→master_task is a 4th existing one (not a target sheet). The schema artifact home exists: `schemas/staging-to-excel-map.schema.json` (author the instance `staging-to-excel-map.json`).

## CRITICAL TECHNICAL REFERENCE (so you don't rediscover — save context)
- **SF MCP server** http://127.0.0.1:11435/mcp (operator runs it in the Screaming Frog GUI; keep SF idle on its MAIN window, NO Settings/modal dialog or every tool errors `IllegalStateException "Tool cannot be called currently"`). THIS Claude session is NOT MCP-connected to `sf` — talk to SF via the ENGINE CLIENT in Bash:
  `cd /Users/apple/Documents/platinum-seo-engine && PYTHONPATH=. python3 -c "from scripts.util.sf_mcp_client import SfMcpClient; c=SfMcpClient('http://127.0.0.1:11435/mcp', timeout_seconds=60, busy_retry_max=6); print(c.health())"`
- **Proven reusable pieces** (all live-validated this session): `scripts/ingestion/sf_crawl_orchestrator.py` → `SF_EXPORT_DISPATCH` (canonical→SF tool/category), `build_export_plan()`, `ndjson_to_csv()`, `export_returns_ndjson()`, `_clean_key()`. `scripts/util/sf_mcp_client.SfMcpClient.load_crawl(crawl_id)` (resilient — tolerates the client-side timeout that large crawls reliably cause; polls progress; live-proven 15.1s on demo-aluminum).
- **Encoding rule (live-verified, MUST follow):** `sf_generate_report`/`sf_generate_bulk_export` write **native CSV WITH a BOM** → read `encoding="utf-8-sig"`. `sf_export_seo_element_urls` writes **NDJSON** (no export_type arg) → `ndjson_to_csv(...)` first (its output is clean, no BOM). Use `export_returns_ndjson(spec)`.
- **demo-aluminum crawl** `crawl_id=fc718e3f-b44e-49e7-a848-0a355a3e1868` (1822 URLs, complete) — the pilot. domain `https://demo-aluminum.example/`. The 22 raw CSVs are already in the workspace (above); you can also re-export any canonical live via the dispatch.
- **transaction.append** validates rows vs `schemas/master-excel.schema.json`. master.xlsx = `/Users/apple/Documents/platinum-seo-workspace/projects/demo-aluminum-ca/master.xlsx` (a `master.xlsx.pre-ac10-bak` safety copy exists). MAKE A BACKUP before any write.

## BOOTSTRAP READING (read in order, then DUR)
1. `docs/PHASE_STATUS.md` line 4 (current state + "SOLE REMAINING Task C: AC-10 sheet projection")
2. `docs/CONTEXT_LEDGER.md` tail — the AC-13 + 3-consumer + "SOLE REMAINING" entries (full session history)
3. `docs/OPEN_QUESTIONS.md` — `OQ-SHEET-PROJECTION`
4. `skills/ingestion/sf-import/SKILL.md` Step 6 `write_excel` (lines ~230-262) + the projection mapping table
5. `scripts/excel/transaction.py` `append`/`write`/`update` (the validated write path)
6. `schemas/master-excel.schema.json` (the 6 sheet definitions + statusEnum/severityEnum) + `schemas/staging-to-excel-map.schema.json`
7. The 3 existing transforms that produce 3 of the sheets: `scripts/discovery/{tech_audit,schema_audit,on_page_audit}_transform.py`

## REMAINING WORK (prioritized)
**Task 1 — design the 6 mappings** (the judgment core). Per sheet: SF CSV columns → schema-valid row shape, respecting enums/types. Resolve the tech_seo issue_category enum problem (decide a/b/c above — recommend mapping SF→one of 5 enum values + SF specifics in `detail`, no schema change; confirm with operator if a schema/enum change is needed). Decide reuse-transform vs dedicated mapping per sheet. Author `staging-to-excel-map.json` (validates vs its schema) OR a pure projection module (mirror the orchestrator's `build_export_plan` pure-helper pattern).
**Task 2 — implement** the projection (pure functions + TDD; reuse transforms where clean) + idempotent write (clear/replace, not blind append). Manager/Worker: dispatch Workers for code, Manager live-validates.
**Task 3 — live cross-check** on demo-aluminum: run the projection on the 22 staged raw CSVs (or a fresh `/pseo-sf-crawl`) → `transaction.append` the 6 sheets → verify master.xlsx 6 sheets repopulated (rowcounts sane, all schema-valid, no RowSchemaError) + an `sf_csv`/`sf_mcp` provenance event. Back up master.xlsx first.
**Task 4 — fix the AC-13/consumer WRITE-step enum** (same issue_category problem) so the consumer live-mode → master.xlsx write is schema-valid.
**Task 5 — release** v1.9.4 once green: Y-05 `version_bump.py --to 1.9.4 --apply` + RELEASE_NOTES + tag + push (operator-gated). Also decide the workspace-repo commit (demo-aluminum config migration + sf-exports + master.xlsx) — operator's data repo.

## DISCIPLINE / INVARIANTS (non-negotiable)
- 🔴 F-16: `.mcp.json` MUST stay 543B / md5 `93523d41e14f90916fefb86d346bd702` — NEVER edit.
- Atomic commits (one logical unit); end commit msgs with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Manager/Worker: dispatch fresh Workers (Agent tool, general-purpose) for implementation; Manager independently **live-validates against the real SF server** (mock-only is what hid every bug this cycle: transport, BOM, on-page columns, and likely the enum). **Cross-check EVERY transform output by actually writing/validating, not just in-memory.**
- Operator-gated: `git push`, destructive SF tools, and any workspace-repo commit/master.xlsx write — get explicit OK.
- pytest baseline = 1338 PASS / 11 SKIP / 0 FAIL (local SF-up).
- ★ Insight blocks + simple Turkish + tables for Süleyman; HE decides; surface findings, recommend, proceed.

## START
Read the bootstrap files, confirm SF healthy (`health()` + `sf_list_crawls`) + the 22 raw CSVs exist, then present Süleyman the projection plan (the 6 mappings + the enum decision + reuse-vs-new) with a recommendation, and tackle Task 1. **The deep lesson of the prior cycle: code-ready ≠ live-proven — validate every mapping by actually appending to master.xlsx + checking schema-valid, on real demo-aluminum data.**
