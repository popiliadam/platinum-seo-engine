# BUILD SPECS — Technical SEO Infrastructure Cluster (4 gaps)

**Verified repo baseline (applies to all 4 specs — workers must re-verify nothing here, it was read from disk 2026-06-10):**

- Engine root: `/Users/apple/Documents/platinum-seo-engine` (plugin v2.0.0). Workspace resolved at runtime via `PSEO_WORKSPACE_ROOT` env (pattern: `skills/discovery/tech-audit/SKILL.md` line ~106).
- `schemas/master-excel.schema.json` — `schema_version: "1.0"`, 19 sheets: `dashboard, topical_map, cluster_keywords, cannibalization, quick_wins, new_content_plan, content_improve, gsc_performance, content_decay, on_page_audit, opportunity, tech_seo, gbp_audit, crawl_sitemap, robots_txt, schema, redirect_404, completed_work, master_task`. Relevant shapes:
  - `robots_txt`: header_row 4 / data_start_row 5, cols `A id, B level (severityEnum), C issue, D detail, E resolution`. No pattern constraint on `id`.
  - `redirect_404`: header_row 4 / data_start_row 5, cols `A url, B inlinks (int), C action, D target_url, E status (statusEnum)`.
  - `tech_seo.issue_category` is the LOCKED 5-enum `{Performance, Layout Stability, Meta Tags, Structured Data, Accessibility}` (ADR-028) — none of these 4 gaps fits it; do NOT touch it.
  - `master_task` is the ONLY sheet with `allowed_writers`; all other sheets have no writer scope restriction.
- `schemas/events.schema.json` — CLOSED enums: `event_kind {provenance, work, audit, workflow}`; work `event_type {content_new, content_revise, content_remove, tech_fix, quickwin_applied, pillar_launch, schema_fix, redirect_deployed, backlink_outreach, manual, skill_content_remediation, skill_whats_next}`; `source.kind {sf_csv, gsc_mcp, dataforseo_mcp, scrapling_local, scrapling_mcp, sf_mcp, manual, tool_computed}`; `operation {ingest, normalize, project_excel, validate, cascade_done, staging}`; `target_excel_sheet` enum CONTAINS `robots_txt`, `crawl_sitemap`, `redirect_404`, `master_task` (does NOT contain `gbp_audit`). All 4 gaps fit existing enum values — **zero events schema changes**.
- `mcp-tool-registry.json` — 4 servers. SF tools: `sf__sf_crawl, sf__sf_crawl_progress, sf__sf_generate_report, sf__sf_generate_bulk_export, sf__sf_export_seo_element_urls` (element enum includes `Hreflang`, `Pagination`, `Canonicals`, `Directives`, `Sitemaps`, `Response Codes`), `sf__sf_list_crawls, sf__sf_list_allowed_base_directory, sf__sf_load_crawl`. GSC: `search_analytics, enhanced_search_analytics, detect_quick_wins, index_inspect, list_sitemaps, submit_sitemap, get_sitemap, list_sites` (all cost 0). Scrapling skill-side tool naming is `mcp__ScraplingServer__get|fetch|...` (verified in `skills/ingestion/scrapling-ops/SKILL.md:59`).
- SF canonical reports (`schemas/sf-required-reports.schema.json`, 40-value enum): includes `hreflang_all` (Tier 2), `pagination_all` (Tier 2), `redirect_chains` (Tier 1), `canonicals_all`, `directives_all`, `indexability`, `sitemaps_all`, `response_codes_all`, `internal_all`, plus Tier-3 `urls_not_in_sitemap`, `xml_sitemap_urls_not_in_internal`, `canonical_mismatch`, `links_to_noindex`. Live-export dispatch: `scripts/ingestion/sf_crawl_orchestrator.py` `SF_EXPORT_DISPATCH` (line 279): `"hreflang_all": _seo("Hreflang")`, `"pagination_all": _seo("Pagination")`, `"redirect_chains": _report("Redirects:Redirect Chains")`.
- `scripts/util/sf_issue_taxonomy.py` — `route_sf_issue()` keywords `"hreflang", "pagination", "canonical", "robots", "indexab", "directive"` already route Issues-Overview rows to the `robots_txt` sheet; unmatched falls back to `robots_txt`. 5-value tech_seo enum is the SSOT here. **No changes needed to this file for any gap.**
- `scripts/ingestion/sf_projection.py` — projects 6 sheets (`crawl_sitemap, redirect_404, schema, on_page_audit, tech_seo, robots_txt`); `map_robots_txt` emits sequential ids `R-001..R-NNN`. **`scripts/ingestion/sf_import.py` writes all 6 via `transaction.replace` (idempotent snapshot refresh)** — any rows other writers append to `robots_txt`/`redirect_404` are WIPED on the next sf-import. This drives the write-semantics design below.
- `scripts/excel/transaction.py` — `replace`/`append`, exceptions `RowSchemaError, WriterScopeError, FormulaPolicyViolation, ...`; `scripts/orchestration/committer.py::commit` is the single idempotent commit path used by tech-audit Step 8.
- `scripts/state/events_writer.py` — `append_event, append_provenance (line 595), append_work (632), append_audit (658), append_workflow (691)`.
- Rules: 20 files in `rules/`. Numeric max is **R-122**; R-123/R-124 unused; **new rules start at R-125** (R-122+ reserved elsewhere). R-78 is duplicated (`rules/content-seo-discipline.md:215` Article Schema vs `rules/content-html-discipline.md:269` AI-Image IPTC) — do not repeat that mistake. R-58 = `rules/content-html-discipline.md:119` (Lifecycle-Aware Robots Meta). R-91 = `rules/content-update-discipline.md:107` (301/410 decision tree). Rule frontmatter allowed keys (`schemas/rules-frontmatter.schema.json`, additionalProperties:false): `schema_version, name, status, applies_to, spec_section, related, applied_to_skills, since, supersedes, source`; required: `name, status, applies_to, spec_section`; `status ∈ {enforced, deprecated, draft, experimental}`; `applies_to` items `∈ {plugin, workspace, skill}`.
- **CRITICAL test constraint:** `tests/rules/test_r_xx_resolution.py` requires every `\bR-\d+\b` token appearing anywhere under `templates/` to be defined by a `### R-NN` heading in `rules/content-*.md` ONLY. The new rule file below is NOT `content-*` prefixed ⇒ **new templates must contain ZERO bare `R-125`…`R-136` tokens** (write “per tech-seo-governance §hreflang” in template prose instead). SKILL.md / commands / rules files may cite R-numbers freely (that test scans only `templates/`).
- `tests/rules/test_frontmatter.py` parametrizes over `rules/*.md` glob — a new rule file is auto-covered, its frontmatter must validate.
- Skill frontmatter (`schemas/skill-frontmatter.schema.json`, additionalProperties:false): allowed top-level keys exactly `schema_version, name, description, version, status, category, inputs, outputs, consumes, produces, triggers, mcp_tools, budget, autonomy`; required `name, description, version, status, category, inputs, outputs, triggers`; `status ∈ {active, deprecated, wip}`; `category ∈ {discovery, governance, ingestion, meta, planning, production, publishing, reporting}`; input param objects allow ONLY `[type, required, default, description]` (enums go in description text — see `skills/production/content-remediation/SKILL.md` W-F3 D1 pattern); `budget.uses_paid_mcp` required; `autonomy {confidence, requires_approval, safe_auto_execute}` all required. Exemplar to mirror byte-for-byte in structure: `skills/discovery/tech-audit/SKILL.md` (10-step body, DURUR list, discipline checklist).
- Templates: `templates/reports/*.template.md` use **`string.Template` `$var` dialect** rendered by `scripts/reporting/render_template.py`; family membership is by glob in `templates/manifest.json` (no manifest edit needed for new report templates); `{{...}}` tokens are FORBIDDEN there (`tests/reporting/test_template_dialect.py`). `tests/scripts/test_template_refs.py`: every `templates/<dir>/<name>.template.md` string referenced from `skills/ commands/ scripts/ rules/` must exist on disk.
- Commands: `commands/pseo-<name>.md`, frontmatter keys `description` (Use when / Also use when / Do not use when), `argument-hint`, `allowed-tools`, `model` (exemplar: `commands/pseo-schema-audit.md`). `docs/WORKFLOWS.md` header line currently says “**45 skill** kataloğu” — each new skill bumps that count and adds a catalog table row.
- `schemas/project-config.schema.json` — `schema_version` **const "1.5"**, additionalProperties:false ⇒ **any new project-config property = const bump + migration script (expensive; precedent migration_0005). ALL FOUR DESIGNS AVOID project-config schema changes.** Existing fields used read-only: `language.content_locale` (BCP 47), `market`, `platform ∈ {wordpress, wordpress+woocommerce, ticimax, ideasoft, imagaza, custom}`, `profile ∈ {e-commerce, ymyl, local-service, b2b-saas, portfolio}`, `url_patterns[] {kind ∈ 8-enum, pattern}`, `domain`, `sf` block.
- content-remediation (`skills/production/content-remediation/SKILL.md`, status wip) already owns SINGLE-URL retire (R-90/R-91) writing `redirect_404 + robots_txt + completed_work`. Gap 3/4 builds must not duplicate its scope.

**Shared foundation built once (referenced by all 4 specs):**

1. **New rule file `rules/tech-seo-governance.md`** — frontmatter:
```yaml
---
name: Tech SEO Governance
status: enforced
applies_to: [plugin, skill]
applied_to_skills: [hreflang-audit, facet-nav-audit, robots-policy-audit, migration-map, content-remediation, sf-import]
source: 2026-06-10 technical-SEO infrastructure cluster build (GAP-T1..T4) + Google Search Central 2024-2026 guidance
spec_section: "Tech SEO Governance — hreflang / faceted nav / robots-noindex lifecycle / migration"
---
```
Contains ALL 12 new rules `### R-125:` … `### R-136:` (statements given per gap below, each with Statement / Rationale / Enforcement / Failure mode subsections mirroring `rules/content-update-discipline.md`). Whichever batch runs FIRST creates the complete file including sections for gaps not yet built (the rules are policy text; skills land later).
2. **Shared idempotent sheet-merge util `scripts/util/sheet_merge.py`** (fully spec'd in GAP-T2 §c; other gaps import it; if absent when a later batch starts, build it from GAP-T2's contract). Purpose: survive sf-import's `transaction.replace` snapshot semantics without duplicating rows.
3. All new skills ship `status: wip` (contract + tests locked, runtime promotion to `active` is an operator decision after first live run — same convention as the 5 production skills per `docs/WORKFLOWS.md` header).
4. All new transforms are pure functions (no I/O in compute path, no slug literals, BOM-safe CSV reads via the `_clean_key` pattern from `scripts/ingestion/sf_projection.py:98`) — grep-gate: forbidden-slug regex 0-tolerance, mirroring tech-audit discipline checklist.

---

### GAP-T1: hreflang / i18n governance

#### (a) 2026 best-practice basis

- Google supports exactly **three hreflang methods**: HTML `<link rel="alternate" hreflang>` in `<head>`, HTTP `Link:` headers (non-HTML assets), and XML sitemap `xhtml:link` annotations. Every version must list **itself plus all alternates (bidirectional/return-link requirement)**; URLs must be **fully-qualified absolute**; codes are **ISO 639-1 language + optional ISO 3166-1 Alpha-2 region**; `x-default` covers unmatched users. Google ignores hreflang/`lang` for language *detection* — hreflang only maps equivalent variants. Source: [Localized Versions of your Pages](https://developers.google.com/search/docs/specialty/international/localized-versions); [Managing multi-regional/multilingual sites](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites).
- Load-bearing validation consequences: (1) a one-directional pair is IGNORED by Google → reciprocity is the #1 check; (2) hreflang targets must be indexable, 200, self-canonical — a noindexed or non-canonical return target breaks the cluster; (3) `x-default` recommended but optional; (4) invalid codes (e.g. `tr-tr` region lowercase is tolerated by Google but `en-UK` is invalid — `gb` is the ISO code) are silent failures.
- Portfolio reality: all current projects are single-language (tr-TR, en-CA, en-NG). The skill must be **PASS-trivial on single-language sites** (cheap portfolio-wide hygiene check: assert NO stray hreflang exists, or that any present hreflang is self-consistent) and fully validate clusters when a multi-language client arrives.

#### (b) Repo integration points (VERIFIED)

- Input data: `projects/{slug}/sf-exports/{date}/raw/hreflang_all.csv` — canonical `hreflang_all` is Tier 2 in `schemas/sf-required-reports.schema.json` and live-exportable via `SF_EXPORT_DISPATCH["hreflang_all"] = _seo("Hreflang")` (`scripts/ingestion/sf_crawl_orchestrator.py:299`). Supporting inputs (same dir): `canonicals_all.csv`, `internal_all.csv` (carries Indexability columns — dispatch maps `indexability` to the Internal element), `sitemaps_all.csv`.
- Declared locale: `project.config.json` → `language.content_locale` (BCP 47) + `market` (read-only; no schema change).
- Issues-Overview rows mentioning hreflang ALREADY land in `robots_txt` sheet via `scripts/util/sf_issue_taxonomy.py` keyword `"hreflang"` — the new skill produces *deeper, computed* findings into the same sheet (consistent routing; no taxonomy change).
- Output sheet: `master.xlsx#robots_txt` (id/level/issue/detail/resolution — exact fit). Events: `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="robots_txt")` — all enum-legal today.
- Optional live SF path: mirror tech-audit's `use_sf_mcp_live` branch (`skills/discovery/tech-audit/SKILL.md` §SF MCP Live Mode) using `scripts/util/sf_mcp_client.SfMcpClient` + `SF_EXPORT_DISPATCH["hreflang_all"]`.
- No GSC hreflang surface exists in `mcp-tool-registry.json` (verified) — GSC is NOT an integration point; `gsc__index_inspect` optional for spot checks only.

#### (c) Design

**Rules (add to `rules/tech-seo-governance.md`):**
- `### R-125: Hreflang Cluster Reciprocity` — Statement: every hreflang annotation set must form a closed cluster: each member lists itself + all members; targets must be 200, indexable, self-canonical, absolute URLs. One-directional pairs = HIGH finding (Google ignores them). Enforcement: `hreflang-audit` skill computes reciprocity graph from `hreflang_all.csv`. Failure mode: AMBER (findings written, nothing blocked).
- `### R-126: Hreflang Code & x-default Validity` — Statement: codes must be ISO 639-1 (+ optional ISO 3166-1 Alpha-2 region, e.g. `tr-TR`, `en-CA`) or `x-default`; unknown/invalid codes = MEDIUM; missing x-default on multi-language clusters = LOW (recommended, not required). Single-language project with zero hreflang = COMPLIANT (explicit not-applicable verdict). Failure mode: AMBER.
- `### R-127: Locale Consistency (config ↔ site)` — Statement: when hreflang exists, at least one cluster member's hreflang code must be compatible with `project.config.json[language.content_locale]` (language subtag match); declared-locale absence from a cluster = MEDIUM (site claims variants the engine doesn't know → flag for operator: extend portfolio config or fix site). Failure mode: AMBER.

**New skill `skills/discovery/hreflang-audit/SKILL.md`** — frontmatter: `name: hreflang-audit`, `version: "1.0"`, `status: wip`, `category: discovery`; inputs: `project_slug (string, required)`, `sf_export_date (string, optional — default latest sf-exports/{date}/ dir)`, `use_sf_mcp_live (boolean, default false)`; outputs: `["master.xlsx#robots_txt", "outputs/reports/{date}-hreflang-audit.md", "events.jsonl"]`; consumes: `["sf-import:projects/{slug}/sf-exports/{date}/raw/hreflang_all.csv", "init-project:projects/{slug}/project.config.json"]`; produces: `["drift-check"]`; triggers.manual: `["/pseo-hreflang-audit"]`; mcp_tools: required `[]`, optional `["mcp__sf__sf_list_crawls", "mcp__sf__sf_load_crawl", "mcp__sf__sf_export_seo_element_urls", "mcp__gsc__index_inspect"]`; budget `{uses_paid_mcp: false, estimated_credits: 0}`; autonomy `{confidence: MEDIUM, requires_approval: true, safe_auto_execute: false}`. Body mirrors tech-audit's 10-step protocol minus budget pre-flight (free): create_run → read CSVs → transform → request_approval → write_excel (merge semantics below) → render_report → provenance event → complete.

**New transform `scripts/discovery/hreflang_audit_transform.py`** (pure; mirrors `sf_projection.py` discipline):
- `transform(hreflang_rows, canonical_rows, internal_rows, content_locale, *, detail_cap=300) -> {"robots_txt_rows": [...], "summary": {...}, "verdict": "COMPLIANT|FINDINGS|NOT_APPLICABLE"}`.
- Header-tolerant parsing: detect hreflang value/URL column pairs generically (SF emits `HTML hreflang N` / `HTML hreflang N URL`-style columns; exact headers vary by SF version). If NO recognizable hreflang columns AND rows exist → raise `HreflangSchemaDriftError` (DURUR — tells operator to re-export `hreflang_all` with default data_fields or use live mode).
- Checks (each finding → robots_txt row, id prefix **`HF-NNN`**, `level` = severityEnum): reciprocity (HIGH), missing self-reference (MEDIUM), relative/protocol-less URL (MEDIUM), invalid code per permissive BCP-47-ish regex `^[a-z]{2,3}(-[A-Za-z]{4})?(-[A-Z]{2})?$|^x-default$` (MEDIUM — permissive: never RED on exotic-but-valid codes), return-target noindex/non-canonical/non-200 via join on internal/canonicals rows (HIGH), missing x-default on multi-variant clusters (LOW), R-127 locale mismatch (MEDIUM).
- Single-language short-circuit: zero hreflang rows + single `content_locale` → `verdict: NOT_APPLICABLE`, empty rows, report still rendered.

**Template `templates/reports/hreflang-audit.template.md`** (`$var` dialect; NO bare R-NNN tokens — prose “per tech-seo-governance hreflang rules”): `$project_slug, $date, $verdict, $cluster_count, $findings_total, $findings_table, $not_applicable_note, $amber_warnings`.

**Command `commands/pseo-hreflang-audit.md`** mirroring `commands/pseo-schema-audit.md` shape (active-project resolution via `shared/active.json`, latest sf-export discovery, skill chain summary, DURUR list).

**Write semantics:** robots_txt rows written via `scripts/util/sheet_merge.py::merge_prefixed_rows` (see GAP-T2) with prefix `HF-` — idempotent re-runs, preserves `R-NNN` (sf_projection) and `RP-/FN-` rows. Note in SKILL: sf-import `transaction.replace` wipes the sheet → **re-run hreflang-audit after every sf-import** (it is free and reads the same export dir).

#### (d) Test plan (TDD, RED first)

- `tests/scripts/test_hreflang_audit_transform.py`: (1) reciprocal 2-locale cluster → 0 findings; (2) one-directional pair → HIGH HF- row; (3) missing self-ref → MEDIUM; (4) relative URL → MEDIUM; (5) invalid code `en-UK` → MEDIUM, valid `zh-Hant-TW`-style → no finding (permissive regex); (6) return target noindex → HIGH; (7) zero-hreflang single-locale → NOT_APPLICABLE + empty rows; (8) drift: hreflang columns absent → `HreflangSchemaDriftError`; (9) every emitted row validates against `robots_txt` 5-col shape + severityEnum (reuse validator pattern from `tests/scripts/test_sf_projection.py`); (10) BOM-prefixed CSV headers parse.
- `tests/skills/test_hreflang_audit.py`: frontmatter validates against `schemas/skill-frontmatter.schema.json` (Draft 7, mirror existing skill tests); outputs `#robots_txt` anchor matches master-excel sheet name; template referenced exists; merge-write idempotency (run twice → same row count); DURUR on missing export dir.
- Regression: `tests/rules/test_frontmatter.py` + `test_r_xx_resolution.py` + `tests/scripts/test_template_refs.py` + `tests/reporting/test_template_dialect.py` must stay green.

#### (e) Size + dependencies + DURUR risks

- **Size: S-M** (~1 transform ≈250 lines, 1 SKILL.md, 1 template, 1 command, ~12 tests).
- Depends on: `rules/tech-seo-governance.md` + `scripts/util/sheet_merge.py` existing (built in batch 1 / GAP-T2). Nothing else.
- Worker STOPS and reports if: (1) `hreflang_all.csv` real-world columns can't be made to support reciprocity computation from the `All` filter export (then: reduce v1 scope to presence/code/self-ref lint + flag reciprocity as live-mode-only, report back); (2) any verified fact above mismatches disk; (3) merge util contract conflicts with `transaction.replace` writer behavior in tests.

#### (f) What NOT to build

- NO hreflang *generator* / sitemap-annotation writer (no multi-language client exists; engine has no platform write access anyway).
- NO new master.xlsx sheet (e.g. `hreflang`) — robots_txt rows + report suffice; a sheet = schema bump + migration + events enum gap (gbp_audit precedent shows the enum pain).
- NO project-config schema change (no `language.alternates` array yet — defer until a real multi-language client signs; record as an open question in the report instead).
- NO GSC integration (no hreflang API surface exists in the registry).

---

### GAP-T2: Faceted navigation / parameter & crawl-budget governance

#### (a) 2026 best-practice basis

- Google's December-2024 dedicated doc (current): if faceted URLs need NO indexing, **block crawling via robots.txt patterns** (e.g. `disallow: /*?*products=` with targeted `allow:` exceptions) or move filters behind **URL fragments** (`#` — Google generally doesn't crawl/index fragments). `rel=canonical` to the unfiltered page reduces crawl only *gradually*; `nofollow` is “generally less effective”. If facets SHOULD be indexed: standard `&` separator, consistent parameter order, **HTTP 404 for zero-result filter combinations**. Sources: [Managing crawling of faceted navigation URLs](https://developers.google.com/crawling/docs/faceted-navigation) (mirrored at [Search Central](https://developers.google.com/search/docs/crawling-indexing/crawling-managing-faceted-navigation)); [Crawling December: faceted navigation blog](https://developers.google.com/search/blog/2024/12/crawling-december-faceted-nav).
- Crawl budget (large/auto-generated sites): manage URL inventory; robots.txt-disallow “truly useless” infinite spaces (sort params, infinite scroll endpoints); long redirect chains burn budget. Source: [Crawl budget management](https://developers.google.com/crawling/docs/crawl-budget).
- Internal search results pages: classic crawl-budget sink; **robots.txt disallow saves crawl, but robots.txt is NOT a de-indexing tool** — a disallowed URL can still be indexed from external links; de-indexing requires crawlable `noindex`. Sources: [robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro); [Block indexing with noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing). (This disallow-vs-noindex tension is codified as R-133 in GAP-T3 — the two gaps share the rule file.)
- The GSC “URL parameters tool” is long dead — parameter governance is now robots.txt + canonicals + URL design only. No tooling assumption beyond that.

#### (b) Repo integration points (VERIFIED)

- Input data (file-based canonical path): `projects/{slug}/sf-exports/{date}/raw/internal_all.csv` (Tier 1; carries Address + Indexability + Indexability Status + Canonical Link Element + Crawl Depth columns — dispatch maps `indexability` and `crawl_depth` to the same Internal element), `response_codes_all.csv` (Tier 1), `directives_all.csv` (Tier 1), `canonicals_all.csv` (Tier 1), `pagination_all.csv` (Tier 2, dispatch `_seo("Pagination")`), optional `urls_not_in_sitemap.csv` (Tier 3).
- Platform awareness: `project.config.json[platform]` enum `{wordpress, wordpress+woocommerce, ticimax, ideasoft, imagaza, custom}` + `url_patterns[]` regexes (read-only).
- Demand evidence for “should this facet be indexable?” (R-129): EXISTING master.xlsx data — `cluster_keywords` cols `keyword/monthly_volume/gsc_impressions` and `gsc_performance` (read-only via openpyxl) — **zero paid calls**.
- Outputs: `master.xlsx#robots_txt` rows (prefix `FN-`), report. Events enum-legal as in GAP-T1.
- Existing related logic to NOT duplicate: `sf_issue_taxonomy` already routes SF's own “URL: …/pagination/canonical” summary issues to robots_txt; this skill adds *URL-corpus-level quantification* (SF Issues Overview cannot tell you “38% of crawled URLs are `?sirala=` sorts and 4,200 of them are indexable”).

#### (c) Design

**Rules (add to `rules/tech-seo-governance.md`):**
- `### R-128: Parameter Taxonomy` — Statement: every query parameter / facet path segment observed in a crawl is classified into the closed set `{facet_filter, sort, pagination, internal_search, session_or_tracking, functional, unknown}`; classification source order: (1) per-project override file, (2) platform seed dictionary, (3) behavioral heuristics (cardinality, canonical-target collapse, indexability mix). `unknown` ≥ threshold → operator triage finding. Failure mode: AMBER.
- `### R-129: Index-Bloat Budget` — Statement: `internal_search` URLs must NEVER be indexable (Google: block crawling; de-index via noindex path per R-133). `sort`/`session_or_tracking` URLs: crawl-blocked or canonicalized, never in sitemap. `facet_filter` URLs may be indexable ONLY with demand evidence (matching query in `cluster_keywords`/`gsc_performance` with volume/impressions > 0) — otherwise recommend block/canonical. Zero-result facet combos must 404 (Google faceted-nav doc). Failure mode: AMBER (recommendations only).
- `### R-130: Blocking-Mechanism Decision Tree` — Statement: (never indexed + crawl waste) → robots.txt `disallow` pattern; (currently indexed + must be removed) → crawlable `noindex` FIRST, robots.txt disallow only after de-indexing confirmed (cross-link R-133); (duplicate-ish but consolidating signals) → `rel=canonical`; (new build) → fragment-based filters. Engine emits RECOMMENDED robots.txt blocks + per-class actions; **operator deploys — engine never writes to client infrastructure**. Failure mode: AMBER.

**New skill `skills/discovery/facet-nav-audit/SKILL.md`** — `status: wip`, `category: discovery`; inputs: `project_slug (required)`, `sf_export_date (optional)`, `policy_overrides_path (string, optional — default projects/{slug}/config/facet-policy.json when present)`, `unknown_param_threshold (integer, default 10)`; outputs `["master.xlsx#robots_txt", "outputs/reports/{date}-facet-nav-audit.md", "events.jsonl"]`; consumes sf-import raw CSVs + project.config + master.xlsx#cluster_keywords + #gsc_performance; produces `["drift-check", "robots-policy-audit"]`; triggers.manual `["/pseo-facet-audit"]`; mcp_tools required `[]`, optional `["mcp__sf__sf_list_crawls", "mcp__sf__sf_load_crawl", "mcp__sf__sf_export_seo_element_urls"]`; budget `{uses_paid_mcp: false, estimated_credits: 0}`; autonomy `{confidence: MEDIUM, requires_approval: true, safe_auto_execute: false}`.

**New transform `scripts/discovery/facet_nav_audit_transform.py`** (pure):
- `transform(internal_rows, response_rows, directives_rows, canonical_rows, pagination_rows, demand_keywords, platform, url_patterns, policy_overrides=None, *, unknown_param_threshold=10) -> {"robots_txt_rows": [...], "metrics": {...}, "proposed_robots_block": "...", "verdict": ...}`.
- Step 1 parameter inventory: parse every Address with `urllib.parse`; bucket by param name (and path-segment facets matched via `url_patterns` + platform seeds). Platform seed dictionaries shipped as module data marked HEURISTIC (e.g. wordpress/woocommerce: `s, orderby, filter_*, min_price, max_price, add-to-cart, paged`; generic: `utm_*, gclid, fbclid, sort, dir, page, q, search`; Ticimax/Ideasoft/imagaza: seed with conservative generic sets + `unknown` routing — **worker must NOT invent platform-specific parameter names it cannot verify; unknowns flow to the unknown-triage finding, that is the designed path**).
- Step 2 per-class metrics: URL count, % of crawl, indexable count (Indexability column), canonicalized-away count, in-sitemap count (optional input), crawl-depth>5 count.
- Step 3 findings → robots_txt rows (`FN-NNN`): indexable internal_search URLs (HIGH), indexable sort/tracking (MEDIUM), facet_filter indexable without demand evidence (MEDIUM, list top offenders), unknown params ≥ threshold (LOW triage), zero-result-combo signal if response rows show soft-404 patterns (LOW).
- Step 4 `proposed_robots_block`: deterministic generation following the Google doc's pattern style (`disallow: /*?*<param>=` + explicit `allow:` exceptions for the `functional` class), emitted as TEXT inside the report — recommendation only.
- DURUR: missing `internal_all.csv` (#1); Address column absent (#2 schema drift); >250k URL rows (#3 cap — surface to manager, suggest chunking); zero parsed URLs (#4).

**Shared util `scripts/util/sheet_merge.py`** (BUILT HERE, used by T1/T3/T4):
- `merge_prefixed_rows(xlsx_path, sheet, new_rows, *, id_prefix, id_column="id", schema_path=<repo>/schemas/master-excel.schema.json, run_id, project_slug, writer) -> WriteResult` — reads current sheet rows (openpyxl, values-only, from the sheet's `data_start_row` per schema), drops rows whose id_column startswith `id_prefix`, appends `new_rows` (ids generated `f"{id_prefix}{seq:03d}"`), writes the union via `scripts/orchestration/committer.commit` (single idempotent commit path → `transaction.replace` under the hood). For sheets without an id column (`redirect_404`), overload `merge_keyed_rows(..., key_column="url")` replacing rows whose key matches new rows' keys.
- Contract tests FIRST: idempotent double-run; preserves foreign-prefix rows; schema-validates output rows (RowSchemaError propagates); refuses unknown sheet.

**Template `templates/reports/facet-nav-audit.template.md`** (`$var`; no bare R-tokens): `$project_slug, $date, $platform, $param_class_table, $bloat_metrics, $proposed_robots_block, $demand_evidence_table, $unknown_params, $verdict`.

**Optional per-project override schema `schemas/facet-policy.schema.json`** (NEW, small, Draft-07, additive — validates the optional workspace file `projects/{slug}/config/facet-policy.json`): `{schema_version: const "1.0", classifications: {<param_name>: enum[7 classes]}, indexable_facets: [param names], notes}`. Validated via existing `scripts/validation/validate_schema.py` CLI when present; absence = defaults. (This is a NEW standalone schema file — no existing schema touched, no migration.)

**Command `commands/pseo-facet-audit.md`.**

#### (d) Test plan

- `tests/scripts/test_sheet_merge.py` (RED first — this is the foundation): the 4 contract cases above + lock behavior passthrough.
- `tests/scripts/test_facet_nav_audit_transform.py`: (1) URL corpus with `?color=&size=` facets classified facet_filter; (2) `?s=` → internal_search, indexable → HIGH row; (3) `utm_` → session_or_tracking; (4) unknown param count ≥ threshold → LOW triage row; (5) demand evidence: facet param matching a cluster_keywords row with volume>0 suppresses the MEDIUM finding; (6) proposed_robots_block contains `disallow: /*?*s=`-style lines for blocked classes and an `allow:` exception when overrides mark a param functional; (7) policy_overrides reclassification wins over seeds; (8) row-shape/severityEnum validation; (9) Address column missing → drift error; (10) URL cap DURUR.
- `tests/skills/test_facet_nav_audit.py`: frontmatter schema-valid; template exists; consumes/outputs anchors valid; idempotent write.
- `tests/schemas/` add `test_facet_policy_schema.py`: valid/invalid override docs.

#### (e) Size + dependencies + DURUR risks

- **Size: M** (transform ≈350-400 lines + shared util ≈150 + skill + template + command + ~20 tests).
- Must land first: `rules/tech-seo-governance.md` (created in this batch), `sheet_merge.py` (created here, FIRST — T3 in the same batch depends on it).
- Worker STOPS if: (1) openpyxl read of populated workspace sheets reveals `data_start_row` mismatches vs schema (report, don't patch); (2) committer.commit signature doesn't accept the row payload shape (verify `scripts/orchestration/committer.py::commit` signature before wiring); (3) platform seed dictionaries would require unverifiable platform facts to be useful — ship generic + unknown-triage and SAY SO in the completion report.

#### (f) What NOT to build

- NO live crawler / no Scrapling sampling of facet pages in v1 (SF export already enumerates the URL corpus).
- NO automatic robots.txt deployment, no per-URL noindex injection — recommendations + validation only (platform write access does not exist).
- NO new master.xlsx sheet for parameter inventory (report tables + FN- rows suffice).
- NO DataForSEO calls for demand evidence (master.xlsx already holds volumes/impressions; keep it free).
- NO changes to `sf_issue_taxonomy.py` or the tech_seo 5-enum.

---

### GAP-T3: robots.txt / noindex lifecycle governance

#### (a) 2026 best-practice basis

- **`noindex` in robots.txt is unsupported.** De-indexing requires a crawlable `<meta name="robots" content="noindex">` OR `X-Robots-Tag: noindex` HTTP header; **a robots.txt-disallowed page can never see its noindex** and may still be indexed from external links (the classic trap → mutual-exclusion rule). Sources: [Block indexing with noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing); [Robots meta tag & X-Robots-Tag specs](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag); [robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro).
- Every meta-robots rule has an exact X-Robots-Tag equivalent → for platforms where `<head>` is untouchable (the engine's body-fragment pipeline, closed e-commerce panels), the **server/CDN header path is the documented alternative** ([robots-meta-tag spec](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)).
- robots.txt is for crawl management (admin areas, internal search, infinite spaces), not index removal ([robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro)).
- Repo-internal premise verified: R-58 (`rules/content-html-discipline.md:119`) maps lifecycle → meta robots and says “Skill `<meta name="robots">` lifecycle map'ten render eder”, but the content pipeline emits body fragments (R-22 header/footer untouchable) → R-58 is undeployable as written; failure mode AMBER (silent fallback `index,follow`) — i.e., ON_HOLD content is silently indexable today.

#### (b) Repo integration points (VERIFIED)

- `master.xlsx#robots_txt` today = SF-issue dump via `sf_projection.map_robots_txt` (sequential `R-NNN` ids, `transaction.replace` on each sf-import) — the governance layer ADDS `RP-`-prefixed computed findings via `sheet_merge`, it does not change projection.
- Live robots.txt + sample header fetch: `mcp__ScraplingServer__get` (Tier 1, free — naming verified in `skills/ingestion/scrapling-ops/SKILL.md:59`); robots.txt parse via stdlib `urllib.robotparser` + custom line-lint (no new dependency — `requirements.txt` discipline).
- Directives ground truth: `projects/{slug}/sf-exports/{date}/raw/directives_all.csv` (Tier 1) — per-URL meta-robots/X-Robots-Tag columns; `internal_all.csv` Indexability columns; Tier-3 `links_to_noindex.csv` optional.
- Lifecycle source: `master.xlsx#new_content_plan` col K `lifecycle_status ∈ {GREEN, RED, ON_HOLD, REMOVED}` + col C `url_slug` (schema verified) — R-58 enforcement data.
- Platform for deployment instructions: `project.config.json[platform]` (6-value enum) + `platform_seo_plugin` (exists as a top-level property; read-only).
- content-remediation already writes robots_txt rows for single-URL retires — the new skill VALIDATES outcomes, never re-issues retire actions (scope fence).

#### (c) Design

**Rules (add to `rules/tech-seo-governance.md`):**
- `### R-131: Governed robots.txt Policy (Recommendation-Only)` — Statement: the engine maintains a per-project EXPECTED robots.txt policy (derived from R-128..R-130 classes + profile); the live file is fetched + parsed each audit; diffs = findings; the engine emits a full proposed robots.txt artifact; **deployment is ALWAYS operator-executed** (no client-site writes exist). Sitemap directive must be present and point at the live sitemap. Failure mode: AMBER.
- `### R-132: Noindex Deployment Path (R-58 Deployability)` — Statement: lifecycle noindex (R-58 map: `ON_HOLD → noindex,follow`) deploys via the platform-appropriate channel, in priority order: (1) CMS/SEO-plugin per-page robots control (e.g. WordPress + Rank Math per-post robots meta), (2) `X-Robots-Tag` HTTP header via server/CDN config snippet, (3) theme-level `<head>` template edit instruction. The engine renders the INSTRUCTION + exact value, never the page itself (body-fragment pipeline has no `<head>` access — this rule is the deployment path R-58 lacks). Cross-link: R-58. Failure mode: AMBER.
- `### R-133: Noindex/Disallow Mutual Exclusion` — Statement: a URL that must LEAVE the index must NOT be robots.txt-disallowed until its removal is confirmed (noindex requires crawlability); ordering: deploy noindex → verify de-indexed (directives/index data) → only then optionally disallow for crawl savings. Any URL simultaneously (a) disallowed by live robots.txt and (b) carrying noindex / lifecycle ON_HOLD = HIGH finding. Failure mode: AMBER.
- Plus ONE one-line additive edit to `rules/content-html-discipline.md` R-58 entry (after line 127): `**Cross-link:** R-132 (tech-seo-governance — deployment path).` (history-stable: no statement rewrite).

**New skill `skills/discovery/robots-policy-audit/SKILL.md`** — `status: wip`, `category: discovery`; inputs: `project_slug (required)`, `sf_export_date (optional)`, `fetch_live (boolean, default true — Scrapling GET of https://{domain}/robots.txt)`, `sample_header_urls (integer, default 5 — per-lifecycle-state URL sampling for X-Robots-Tag spot check)`; outputs `["master.xlsx#robots_txt", "outputs/reports/{date}-robots-policy-audit.md", "outputs/robots/{date}-robots.proposed.txt", "events.jsonl"]`; consumes: sf-import directives/internal CSVs, `master.xlsx#new_content_plan`, `facet-nav-audit:outputs/reports/{date}-facet-nav-audit.md` (optional — proposed block feed-in), project.config; produces `["drift-check", "content-remediation"]`; triggers.manual `["/pseo-robots-policy"]`; mcp_tools: required `[]`, optional `["mcp__ScraplingServer__get"]`; budget `{uses_paid_mcp: false, estimated_credits: 0}`; autonomy `{confidence: MEDIUM, requires_approval: true, safe_auto_execute: false}`. Consent note in body: the live fetch is a READ of a public file (no consent gate); ALL outward changes remain operator-deployed; Excel write behind the standard `request_approval` step.

**New transform `scripts/discovery/robots_policy_transform.py`** (pure):
- `transform(robots_txt_text, directives_rows, internal_rows, lifecycle_rows, platform, domain, facet_block=None) -> {"robots_txt_rows": [...], "proposed_robots_txt": "...", "deployment_instructions": "...", "summary": {...}}`.
- Checks → `RP-NNN` rows: robots.txt syntax lint (unknown directives, `noindex:` lines present = HIGH “unsupported by Google”, missing `Sitemap:` = MEDIUM, disallow-all catastrophes = CRITICAL); R-133 conflict scan (live disallow rules × directives_all noindex URLs × lifecycle ON_HOLD slugs); R-58 drift (ON_HOLD slug whose live page is `index` per directives_all → HIGH “lifecycle noindex undeployed”; REMOVED slug still 200 → cross-ref to content-remediation, MEDIUM); important-page protection (any URL whose `url_patterns.kind ∈ {product, category, blog, hub}` match is disallowed → HIGH).
- `proposed_robots_txt`: deterministic merge of (live file − lint violations) + facet-nav-audit's proposed block when supplied + Sitemap line. Emitted BOTH inside the report and as the plain artifact `outputs/robots/{date}-robots.proposed.txt` (plain Write, no template; new `outputs/robots/` subdir under the project — workspace data, no engine schema impact).
- `deployment_instructions`: rendered from a module-level platform matrix keyed by the 6-value platform enum. Each entry has `robots_txt_channel`, `per_page_noindex_channel`, `header_channel`, `verified: bool`. Worker fills ONLY mechanisms it can verify from official platform docs (WordPress/Rank Math, WooCommerce, nginx/Apache header snippets); for `ticimax/ideasoft/imagaza` set `verified: false` with the generic instruction “platform panel or support ticket; exact menu path to be confirmed by operator” — **fabricating panel paths is forbidden**.
- DURUR: live fetch enabled but domain unreachable (#1 → AMBER continue file-only, mirror tech-audit R9 never-hard-fail pattern — i.e. this one is AMBER not DURUR); `directives_all.csv` missing (#2 DURUR); lifecycle sheet unreadable (#3 DURUR); proposed file would disallow `/` (#4 DURUR — never propose a site-wide block).

**Template `templates/reports/robots-policy-audit.template.md`** (`$var`; no bare R-tokens): `$project_slug, $date, $live_robots_status, $lint_table, $conflict_table, $lifecycle_drift_table, $proposed_robots_txt, $deployment_instructions, $amber_warnings`.

**Command `commands/pseo-robots-policy.md`.**

#### (d) Test plan

- `tests/scripts/test_robots_policy_transform.py` (RED first): (1) robots.txt with `noindex:` line → HIGH RP- row; (2) missing Sitemap → MEDIUM; (3) `Disallow: /` → CRITICAL + proposed-file DURUR; (4) R-133: URL disallowed + noindexed → HIGH conflict; (5) ON_HOLD lifecycle slug live-indexable → HIGH R-58-drift; (6) REMOVED slug still 200 → MEDIUM; (7) disallow matching a `url_patterns kind=category` regex → HIGH; (8) proposed file round-trips through `urllib.robotparser` without error and preserves allow/disallow semantics for sampled paths; (9) platform matrix: every enum value has an entry, unverified entries carry `verified: false`; (10) row shape/severityEnum validation; (11) empty robots.txt (404) → findings set “missing robots.txt” MEDIUM, not crash.
- `tests/skills/test_robots_policy_audit.py`: frontmatter valid; both output artifacts declared; template + proposed-txt path conventions; AMBER (not fail) on fetch-down; idempotent RP- merge.

#### (e) Size + dependencies + DURUR risks

- **Size: M** (transform ≈350 lines incl. platform matrix + lint, skill, template, command, ~16 tests).
- Must land first: `rules/tech-seo-governance.md`, `scripts/util/sheet_merge.py` (same batch as GAP-T2 — see batching).
- Worker STOPS if: (1) `directives_all.csv` column names for meta-robots values can't be confirmed from a real export fixture — then build against a synthetic fixture, mark the header-map as drift-guarded (`RobotsDirectivesSchemaDriftError`) and report; (2) tempted to edit `sf_issue_taxonomy.py` routing or rename existing `R-NNN` sheet ids — forbidden, stop; (3) tempted to modify R-58's statement text — forbidden (ADR-038 history-stable numbering), only the one-line cross-link append is allowed.

#### (f) What NOT to build

- NO robots.txt generator-from-scratch as a standalone product — validation + diff + ONE proposed artifact is the deliverable (the instruction layer suffices; operator deploys).
- NO automated GSC removal-tool calls, no Indexing API `URL_DELETED` (consent-walled domain of indexing-ping skill; memory: Indexing API consent is mandatory).
- NO PreToolUse hook enforcement of R-131..R-133 (these are client-site advisory rules, not engine-write gates — hooks are for engine I/O discipline).
- NO live header crawling beyond the tiny `sample_header_urls` spot check (SF directives export already covers the corpus).
- NO X-Robots-Tag middleware/plugin code for client platforms — config SNIPPETS in the instruction section only.

---

### GAP-T4: Site-migration / redirect-map playbook

#### (a) 2026 best-practice basis

- Google site-move doc: prepare a **one-to-one URL mapping** old→new; **do NOT mass-redirect to the homepage** (topical signals collapse); use **server-side 301**; keep redirects **for as long as possible — generally at least 1 year** (and 180 days as the hard floor), monitor traffic to old URLs before retiring them. Source: [Site moves and migrations](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes).
- Redirect mechanics: Googlebot follows up to 10 hops but Google advises redirecting to the FINAL destination — keep chains ideally ≤3; permanent server-side redirect is the strongest canonicalization signal. Source: [Redirects and Google Search](https://developers.google.com/search/docs/crawling-indexing/301-redirects).
- Domain-level moves additionally use Search Console's **Change of Address tool** (domain moves only, not path/CMS restructures). Source: [Change of Address tool](https://support.google.com/webmasters/answer/9370220).
- Repo-internal premise verified: R-91 covers only single-URL prune/sunset 301/410 (content-update-discipline.md:107, enforced by content-remediation); SF `redirect_chains` is a Tier 1 canonical already exported on every crawl but consumed by nothing.

#### (b) Repo integration points (VERIFIED)

- `master.xlsx#redirect_404` (url / inlinks / action / target_url / status) — exact container for the migration map (action carries `301`/`410` per R-91 convention; status = statusEnum `TODO→DONE`).
- SF inputs: `internal_all.csv` (old-site URL inventory + inlink counts via `all_inlinks.csv` Tier 1 if needed), `redirect_chains.csv` (Tier 1, dispatch `_report("Redirects:Redirect Chains")`), `response_codes_all.csv` (Tier 1) — verify mode crawls the NEW site and reads these.
- GSC protection data: `master.xlsx#gsc_performance` (url/clicks/impressions — read-only) ranks which old URLs are traffic-critical; optional `mcp__gsc__list_sitemaps` / `mcp__gsc__get_sitemap` for sitemap state; `mcp__gsc__submit_sitemap` exists but is OUTWARD → recommendation-only in v1 (consent precedent: `feedback_indexing_api_consent`).
- Events: deployment confirmation uses EXISTING work enum `event_type: "redirect_deployed"` (verified in events.schema.json) — emitted only after operator confirms deployment (manual approve), `event_kind=work`.
- master_task: optional follow-up rows route through existing `primary_source: "redirect_404"` enum value (verified, 11-value enum) via the existing `master-task-sync` planning skill — NO enum change.
- Operator mapping seed: workspace file `projects/{slug}/migration/{date}-url-mapping.csv` (new conventional dir; columns `old_url,new_url,action` — `action ∈ {301, 410}`) + optional `projects/{slug}/migration/{date}-mapping-rules.json` (regex rules, validated by NEW small schema `schemas/migration-mapping.schema.json`).

#### (c) Design

**Rules (add to `rules/tech-seo-governance.md`):**
- `### R-134: Migration Redirect-Map Contract` — Statement: every old URL in the crawl inventory must resolve to exactly one disposition: `301 → mapped target` (one-to-one wherever possible) or `410`. Homepage-collapse guard: >5% of 301 targets being the homepage = HIGH finding; chains in the deployed map ≤3 hops, loops forbidden; redirects retained ≥1 year (180-day hard floor) — retirement only with traffic evidence. Failure mode: RED for loops/unmapped-silent-drop, AMBER otherwise.
- `### R-135: Migration Phase Gate` — Statement: phases are `plan → freeze → deploy (operator) → verify`; the engine produces the map and verification, the OPERATOR deploys (htaccess/nginx/platform snippets are recommendations); domain-level moves additionally get a Change-of-Address checklist item (GSC UI, operator-executed); old sitemap kept temporarily live alongside the new one to accelerate redirect discovery. Failure mode: AMBER.
- `### R-136: Post-Migration Verification & Rollback Watch` — Statement: verify mode must confirm per map row: old URL → single-hop 301 → 200 target; findings: chain>3, 302-instead-of-301, 404 regressions, redirect-to-homepage drift; verification cadence T+1d / T+7d / T+30d; unresolved CRITICALs → rollback recommendation in report. Failure mode: AMBER.

**New skill `skills/planning/migration-map/SKILL.md`** — `status: wip`, `category: planning` (it produces a plan artifact; verify mode is still read-only analysis); inputs: `project_slug (required)`, `mode (string, required — "plan" | "verify"; enum in description per W-F3 D1)`, `mapping_csv_path (string, optional — default latest projects/{slug}/migration/*-url-mapping.csv)`, `sf_export_date (optional — plan mode: old-site crawl; verify mode: post-launch crawl)`, `homepage_collapse_pct (number, default 5)`; outputs `["master.xlsx#redirect_404", "outputs/reports/{date}-migration-map.md", "events.jsonl"]`; consumes: sf-import CSVs, `master.xlsx#gsc_performance`, migration seed files, project.config; produces `["drift-check", "master-task-sync", "indexing-ping"]`; triggers.manual `["/pseo-migration-map"]`; mcp_tools required `[]`, optional `["mcp__gsc__list_sitemaps", "mcp__gsc__get_sitemap", "mcp__gsc__index_inspect"]`; budget `{uses_paid_mcp: false, estimated_credits: 0}`; autonomy `{confidence: MEDIUM, requires_approval: true, safe_auto_execute: false}`.
- Body: plan mode → read inventory + seed → transform → `request_approval` (“N rows yazılsın mı?”) → `merge_keyed_rows` into `redirect_404` (key=url) → render report (map stats + server-config snippet section + phase-gate checklist incl. Change-of-Address when `mode=plan` and domain changes) → provenance event. Verify mode → read `redirect_chains.csv` + `response_codes_all.csv` from the post-launch export → transform(verify) → update matching `redirect_404` rows' `status` (`DONE` for verified, stays `TODO`/`ONGOING` otherwise) → report. Deployment confirmation (operator says “deployed”) → `events_writer.append_work(event_type="redirect_deployed", ...)` — explicitly gated on the approval step, never autonomous.

**New transform `scripts/planning/migration_map_transform.py`** (pure; naming mirrors `scripts/planning/*_transform.py`):
- `build_map(inventory_rows, mapping_pairs, mapping_rules, gsc_rows, *, homepage_collapse_pct=5.0) -> {"redirect_rows": [...], "unmapped": [...], "lint": {...}}` — expands explicit pairs + ordered regex rules over the full inventory; lints: unmapped URLs (every one listed — silent drops are RED), loops/self-redirects (RED), chain depth via map-internal resolution (≤3), homepage-collapse %, traffic-critical unmapped (old URL present in gsc_rows with clicks>0 and unmapped → HIGH), duplicate targets fan-in stats. Emits `redirect_404`-shaped rows `{url, inlinks, action, target_url, status:"TODO"}` (inlinks from inventory when available, else 0).
- `verify_map(redirect_rows, redirect_chain_rows, response_rows) -> {"verified": [...], "violations": [...], "summary": {...}}` — per R-136 checks; header-tolerant on SF redirect_chains columns with `RedirectChainsSchemaDriftError` guard.

**New schema `schemas/migration-mapping.schema.json`** (small, standalone, additive): `{schema_version: const "1.0", rules: [{match: regex, replace: template, action: enum["301","410"], order: int}], defaults: {unmatched: enum["flag","410"]}}`.

**Template `templates/reports/migration-map.template.md`** (`$var`; no bare R-tokens): `$project_slug, $date, $mode, $map_stats_table, $unmapped_table, $lint_findings, $server_config_snippets, $phase_checklist, $verification_table, $rollback_recommendation`.

**Command `commands/pseo-migration-map.md`** (argument-hint: `<project-slug> --mode plan|verify [--mapping-csv path] [--sf-export-date YYYY-MM-DD]`).

#### (d) Test plan

- `tests/scripts/test_migration_map_transform.py` (RED first): (1) explicit pair expands to redirect_404 row shape; (2) regex rule maps `/old-blog/(.*)` → `/blog/$1`; (3) unmapped URL → listed, never dropped; (4) loop A→B→A → RED lint; (5) chain A→B→C→D depth>3 → violation; (6) homepage-collapse 6% > 5% threshold → HIGH; (7) gsc-traffic URL unmapped → HIGH; (8) 410 action row has empty target_url and passes sheet shape; (9) verify: single-hop 301→200 marks verified; (10) verify: 302 found → violation; (11) verify: chain export column drift → `RedirectChainsSchemaDriftError`; (12) statusEnum/row-shape validation against master-excel schema.
- `tests/skills/test_migration_map.py`: frontmatter valid; mode enum rejection (`mode="x"` → DURUR); approval-before-write contract; `redirect_deployed` event emitted ONLY on confirm path (mock events_writer); template exists.
- `tests/schemas/test_migration_mapping_schema.py`: valid/invalid rule docs.

#### (e) Size + dependencies + DURUR risks

- **Size: M-L** (two-mode transform ≈400-450 lines, skill with two body flows, schema, template, command, ~20 tests).
- Must land first: `rules/tech-seo-governance.md` + `scripts/util/sheet_merge.py` (from batch 1). Independent of T1/T2/T3 logic otherwise.
- Worker STOPS if: (1) `redirect_404` populated-workbook reality (existing rows from sf_projection with `status` values) conflicts with merge-by-url semantics — report before overwriting anything; (2) SF `redirect_chains.csv` fixture columns can't be sourced — build synthetic fixture + drift guard, note it; (3) any temptation to call `mcp__gsc__submit_sitemap` inside the skill — forbidden in v1 (recommendation text only); (4) scope creep into content-remediation's single-URL retire path — the fence is: migration-map handles BULK maps, content-remediation handles lifecycle retires.

#### (f) What NOT to build

- NO automatic redirect deployment, no htaccess file pushed anywhere — snippets inside the report only.
- NO auto Change-of-Address (no API exists; GSC UI is operator-only) — checklist line only.
- NO similarity-ML auto-mapping in v1 (token-overlap suggestion column can be a later enhancement; v1 = explicit pairs + regex rules + unmapped triage. An LLM session can DRAFT the seed CSV — that's orchestration, not engine code).
- NO new sheet (redirect_404 fits) and NO master_task direct writes (route via existing master-task-sync if tasks are wanted).
- NO crawl-scheduling logic for T+1/7/30 cadence (the cadence is a checklist in the report; `/pseo-schedule` infrastructure already exists if the operator wants automation later).

---

### Priority & batching recommendation

| Gap | Value now (portfolio 2026-06) | Size | Build when |
|---|---|---|---|
| T2 faceted/crawl-budget | HIGH — 4+ e-commerce clients (Ticimax/Ideasoft/imagaza/WooCommerce) mass-generating parameter URLs today; Eykom 1717-URL head-ordering + /arama redirect symptoms are this class | M | **Now — Batch 1** |
| T3 robots/noindex lifecycle | HIGH — R-58 is silently undeployable (ON_HOLD content indexable); robots_txt sheet is dump-only; unblocks content-remediation correctness | M | **Now — Batch 1** |
| T4 migration/redirect map | MEDIUM-HIGH — CMS-change-prone client base, redirect_chains Tier-1 data already collected unused; no active migration this week | M-L | **Next — Batch 2** |
| T1 hreflang/i18n | LOW-MEDIUM today — portfolio is 100% single-language; PASS-trivial hygiene value only until a multi-language client signs | S-M | **Batch 2 (or defer to first multi-language signing)** |

**Two worker batches, sequential (not parallel):**

- **Batch 1 = GAP-T2 + GAP-T3, ONE Opus worker.** Rationale: they co-create the two shared files (`rules/tech-seo-governance.md` — created COMPLETE with all 12 rule sections R-125..R-136 verbatim from these specs — and `scripts/util/sheet_merge.py`), both write `FN-`/`RP-` rows to the same `robots_txt` sheet via the same merge util, and T3 consumes T2's proposed robots block. Build order inside the batch: rule file → sheet_merge (RED-first) → T2 transform/skill → T3 transform/skill → both commands + `docs/WORKFLOWS.md` (45→47 + 2 table rows) in one commit each per atomic-phase convention.
- **Batch 2 = GAP-T4 + GAP-T1, ONE Opus worker, dispatched only after Batch 1 is merged** (it imports `sheet_merge` and appends nothing to the rule file — all 12 sections already exist). T4 and T1 share zero files with each other beyond `docs/WORKFLOWS.md` (47→49); same-worker sequencing avoids even that.
- Why not one mega-batch: 4 skills + 4 transforms + 1 util + 12 rules + 4 templates + 4 commands + ~70 tests ≈ exceeds the safe single-session change budget (AMO ≤5% structural discipline + context limits); why not 4 parallel workers: guaranteed collisions on `rules/tech-seo-governance.md`, `docs/WORKFLOWS.md`, `sheet_merge.py`, and the shared-worktree contention pattern already bit AMO batches (1b/1c precedent).
- Both batches end with the standard gate: full `pytest` green (baseline ~2458 pass / 0 fail as of `35c2e16`), forbidden-slug grep 0-hit, `tests/rules/` + `tests/reporting/test_template_dialect.py` + `tests/scripts/test_template_refs.py` explicitly re-run, no edits to `tests/rules/test_r_xx_resolution.py`, no `.mcp.json` byte changes (F-16 baseline), commit-per-deliverable, push only on operator instruction.

Sources: [Localized versions (hreflang)](https://developers.google.com/search/docs/specialty/international/localized-versions) · [Multi-regional sites](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites) · [Faceted navigation crawling](https://developers.google.com/crawling/docs/faceted-navigation) · [Crawling December: faceted nav](https://developers.google.com/search/blog/2024/12/crawling-december-faceted-nav) · [Crawl budget management](https://developers.google.com/crawling/docs/crawl-budget) · [robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro) · [Block indexing with noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing) · [Robots meta tag / X-Robots-Tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag) · [Site moves](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes) · [Redirects and Google Search](https://developers.google.com/search/docs/crawling-indexing/301-redirects) · [Change of Address](https://support.google.com/webmasters/answer/9370220)
