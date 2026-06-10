# BUILD SPECS — Acquisition / Local / Commerce Cluster (4 gaps)

> Research date: 2026-06-10. Repo facts verified by reading; web claims cited inline.
> ⚠️ MANAGER OVERRIDE: rule numbers in this file are REMAPPED by the unified dispatch doc
> (`2026-06-10-UNIFIED-remediation-WORKER-DISPATCH.md` §R-MAP): R-125→R-142, R-126→R-143,
> R-127→R-144, R-128→R-145, R-129→R-146, R-130→R-147, R-131→R-148. Workers apply the REMAPPED ids.

### GAP-A1: Backlinks minimal monitoring (`dfs-backlinks-pull`)

#### (a) 2026 best-practice basis (web-verified)

| Claim | Verified state | Source |
|---|---|---|
| DFS Backlinks API pricing | **$0.02 per request + $0.00003 per row**, max 1,000 rows/request (a full 1,000-row pull ≈ $0.05) | https://dataforseo.com/pricing/backlinks/backlinks · https://dataforseo.com/help-center/backlinks-api-pricing-explained |
| DFS Backlinks API access | Requires a **separate sign-up with a $100/month minimum commitment** (funds land on the general account balance, spendable on any API — but the commitment is the real gate, not per-call cost) | https://dataforseo.com/help-center/backlinks-api-pricing-explained |
| Endpoints needed exist | `backlinks/summary/live`, `backlinks/timeseries_new_lost_summary/live`, `backlinks/bulk_new_lost_referring_domains/live`, referring-domains endpoints return per-domain `backlinks_spam_score` | https://docs.dataforseo.com/v3/backlinks-summary-live/ · https://docs.dataforseo.com/v3/backlinks/bulk_new_lost_referring_domains/live/ · https://docs.dataforseo.com/v3/backlinks-overview/ |
| MCP exposure | The org's pinned `dataforseo-mcp-server@2.8.10` **does expose 20 `backlinks_*` tools** (confirmed live in session MCP tool surface: `backlinks_summary`, `backlinks_timeseries_new_lost_summary`, `backlinks_referring_domains`, `backlinks_bulk_spam_score`, `backlinks_bulk_new_lost_referring_domains`, …). The TR location-forwarding bug (`feedback_dfs_wrapper_tr_bug`) is N/A here — backlinks endpoints take no location/language params, so the wrapper path is safe (no Method C needed). | session MCP tool list + `.mcp.json` pin |

Monthly cadence with referring-domain trend + new/lost + spam-score watch is the minimal viable layer; per-backlink-row crawling (the expensive part) is unnecessary for monitoring.

#### (b) Repo integration points (verified by reading)

- `mcp-tool-registry.json` — dataforseo server (pin 2.8.10) registers **only 2 backlinks tools**: `dataforseo__backlinks_summary` and `dataforseo__backlinks_competitors`, both `cost_credits_per_call: 0.0002`. **Found discrepancy:** 0.0002 under-prices the verified $0.02/request base by ~100× (the registry's unit elsewhere ≈ USD: `serp_organic_live_advanced` 0.0035). Fix both to `0.02` in this batch (upward correction = budget-safe). Tools to ADD: `dataforseo__backlinks_timeseries_new_lost_summary` (0.021), `dataforseo__backlinks_referring_domains` (0.023, limit=100), `dataforseo__backlinks_bulk_spam_score` (0.023, optional). `category: "backlinks"` already exists in `schemas/mcp-tool-registry.schema.json:180`.
- `.mcp.json` — 565B / 4 servers, **F-16 byte-locked (ADR-040, md5 `634c8ed5b7cf3c852d9b41e1c0e1d3b5`) + ci.yml 4-server invariant. DO NOT TOUCH** — not needed: the dataforseo server already serves backlinks tools.
- `schemas/dataforseo-endpoint-mapping.schema.json` — endpointGroup key `"backlinks"` already in the 7-key vocabulary (line 59); endpoints must declare `output_fields_keep`/`output_fields_drop` + `cost.credits_per_call` + `staging_table` matching `^dfs_[a-z][a-z0-9_]*$`.
- `schemas/master-excel.schema.json` — schema_version "1.0", 19 sheets; **no backlink sheet exists and none is added** (see c).
- Skill conventions: `skills/ingestion/dfs-pull/SKILL.md:84` explicitly reserves the name **`dfs-backlinks-pull`** and declares dfs-pull the convention authority ("Reuse the 10-step shape verbatim"). Raw-inbox-first discipline: `inbox/dfs/` before transform; staging at `_state/staging/dfs_*_{date}_{slug}.json`; transform is staging-only (D-003: transform never writes events; orchestrator does).
- Budget: `scripts/budget/check_budget.py` verified — importable `preflight(project_config_path, events_path, estimated_credits)` → envelope `{budget_per_day, used_24h, estimated_credits, projected, remaining, exceeded}` + `BudgetGateError`; sums provenance events with `source.kind=="dataforseo_mcp"` `cost.credits` trailing 24h. `scripts/state/cost_ledger.py` **exists** (641 lines): global `shared/cost_ledger.jsonl`, hash-chained `reserve/confirm/release`; resource enum locked `["gsc_calls","dfs_credits","image_spend"]` in `schemas/cost-ledger.schema.json` — backlink calls charge `dfs_credits`, **zero schema change**.
- Monthly report hook: `scripts/reporting/monthly_report.py:406` `_build_backlink_delta()` returns hardcoded zero shape; `templates/reports/monthly-report.template.md:57-59` section 9 is a static stub; `schemas/monthly-report.schema.json` `sections.backlink_delta` already defines `{new_count, lost_count, toxic_count, top_new≤10, top_lost≤10}` with no required inner fields — **no schema change needed**.
- Events: `schemas/events.schema.json` — `source.kind` enum already has `dataforseo_mcp`; work `event_type` already has `backlink_outreach` (line 159; `rules/events-writer.md:116` marks the outreach skill "Placeholder — SKILL.md henüz yok" — stays a placeholder, see f). **Zero events-schema change.**
- Rules: highest in use is **R-122** (`rules/content-quality.md:6`). (Manager: this batch's rules are R-142/R-143 per the unified R-MAP.)
- Count locks (cascade for any new skill/command): `tests/docs/test_count_consistency.py:68,75,171-174` (45 skills, plugin.json description match), `tests/reporting/test_capability_coverage.py:87,356,375,428` (45 asserts), `tests/docs/test_readme_counts_match_filesystem.py:69`, `.github/workflows/ci.yml:93` (comment "45 SKILL.md"), `README.md:8,46,59,136-137`, `.claude-plugin/plugin.json` description ("45 skill, 25 slash command"). Commands dir currently has exactly 25 files. (Manager: counts will have moved by the time this batch runs — bump from CURRENT values, see unified doc wave order.)

#### (c) Design (minimal-but-complete)

**No new master.xlsx sheet.** Trend data lives in monthly staging JSON + report; a sheet would cost: `master-excel.schema.json` additive entry + `scripts/excel/transaction.py` WRITER_REGISTRY + `templates/master-excel.xlsx` physical template + bootstrap + drift-check expectations + cascade tests (gbp_audit precedent footprint = 8 files) — not justified for monitor-only data.

Deliverables:
1. **`skills/ingestion/dfs-backlinks-pull/SKILL.md`** — category `ingestion`, `status: active`, `version: "1.0"`. Frontmatter mirrors gbp-audit/dfs-pull exactly: `budget: {uses_paid_mcp: true, estimated_credits: 1}`; `autonomy: {confidence: MEDIUM, requires_approval: true, safe_auto_execute: false}`; `mcp_tools.required: [mcp__dataforseo__backlinks_summary, mcp__dataforseo__backlinks_timeseries_new_lost_summary, mcp__dataforseo__backlinks_referring_domains]`, `optional: [mcp__dataforseo__backlinks_bulk_spam_score]`; `triggers.manual: ["/pseo-backlinks"]`, `triggers.scheduled: [{cron: "0 7 1 * *", mode: "report-only"}]`. Inputs: `project_slug` (required), `spam_score_threshold` (integer, default 50), `refdomains_limit` (integer, default 100), `deep_spam_check` (boolean, default false → gates the optional bulk_spam_score call). 10-step dfs-pull shape: preflight_budget (MANDATORY, `check_budget.preflight`) → create_run → 3 MCP calls (each raw payload to `inbox/dfs/{date}-backlinks-{slug}.json` FIRST) → transform → write staging → render report → provenance events with `cost.credits` per call (ADR-016) → complete. First-run = baseline mode (no delta, note in report).
2. **`scripts/ingestion/backlinks_pull.py`** (NEW, ~300 lines) — pure transform, staging-only. Contract: `build_staging(raw_summary: dict, raw_timeseries: dict, raw_refdomains: dict, *, previous_staging: dict | None, spam_score_threshold: int, fetched_at: str) -> dict` → `{schema_version: "1.0", period: "YYYY-MM", target, summary: {referring_domains, backlinks, rank}, trend: [{month, new_refdomains, lost_refdomains}...], new_lost: {new_count, lost_count}, toxic: [{domain, spam_score, first_seen}...] (spam_score >= threshold), top_new: [...≤10], top_lost: [...≤10], delta_vs_previous: {...} | null}`. Deterministic: no clock (fetched_at passed in), no RNG, no I/O. Output written by orchestrator to `_state/staging/dfs_backlinks_watch_{YYYY-MM}_{slug}.json` (idempotent overwrite per month, dfs-pull convention).
3. **`mcp-tool-registry.json`** — add 3 tools + correct the 2 existing backlinks costs to 0.02 (see b).
4. **`scripts/reporting/monthly_report.py`** — `_build_backlink_delta()` gains a `project_dir` param: read the latest `_state/staging/dfs_backlinks_watch_*.json` if present, map to the existing schema fields; absent → current zero shape (backward compatible; monthly-report stays 0-credit/LOCAL-only, preserving its SKILL.md claim at `skills/reporting/monthly-report/SKILL.md:20`). Template: replace the static stub at `templates/reports/monthly-report.template.md:57-59` with a prerendered `$backlink_delta_md` block (mirrors `$tech_done_md` pattern; string.Template family per `templates/manifest.json` — glob already covers it, no manifest edit).
5. **`templates/reports/backlinks-watch.template.md`** (NEW, string.Template dialect).
6. **`commands/pseo-backlinks.md`** (NEW) — mirrors `commands/pseo-gbp-audit.md` shape.
7. **`rules/backlink-discipline.md`** (NEW; frontmatter per `schemas/rules-frontmatter.schema.json`, mirror `rules/budget-events.md`): **R-142** (spec'd as R-125) — backlink monitoring is monthly-cadence, cost-gated (budget preflight mandatory; cache 168h per registry; never per-backlink full crawls; `refdomains_limit` ≤ 1000 hard cap). **R-143** (spec'd as R-126) — monitoring is READ-ONLY: engine never automates outreach, never auto-generates/uploads disavow files; disavow is advisory text in the report only, flagged for operator decision with explicit consent (consistent with `feedback_indexing_api_consent` posture).
8. Count-lock cascade: bump skills/commands counts in every location listed in (b) from their CURRENT values at dispatch time.

#### (d) Test plan (TDD, RED-first, synthetic fixtures only)

- `tests/ingestion/test_backlinks_pull_transform.py` (NEW, ~10 cases): (1) RED: `build_staging` with canned DFS summary+timeseries+refdomains fixtures (inline dicts mirroring DFS v3 envelope `tasks[0].result[0]`) produces the staging contract keys; (2) toxic filter respects threshold boundary (49 excluded, 50 included); (3) `previous_staging=None` → `delta_vs_previous is null` + baseline flag; (4) delta computed vs previous month fixture; (5) top_new/top_lost capped at 10; (6) determinism: same inputs → byte-identical `json.dumps(sort_keys=True)`; (7) malformed DFS envelope → typed `BacklinksSchemaDriftError`; (8) empty refdomains result → empty toxic, no crash.
- `tests/skills/test_dfs_backlinks_pull.py` (NEW, ≥5 cases, mirror `tests/skills/test_gbp_audit.py` pattern): frontmatter parses + validates against `schemas/skill-frontmatter.schema.json` Draft7 (incl. `uses_paid_mcp=true`, category=ingestion, scheduled cron); budget-exhausted monkeypatch → `awaiting_approval`; declared `mcp_tools` exist in registry (also enforced repo-wide by `tests/schemas/test_skill_mcp_tools_exist_in_registry.py` — registry additions must land in the same commit or that suite goes RED).
- `tests/reporting/test_monthly_report_backlink_delta.py` (NEW): RED first — staging file present → section 9 populated from it; staging absent → zero shape unchanged (regression guard for projects without backlink data).
- No live API in tests anywhere (repo norm: stubs/monkeypatch, gbp-audit precedent).

#### (e) Size + dependencies + DURUR risks

- Size: ~1 worker batch. SKILL.md ~350 lines, transform ~300, tests ~350, registry/report/template/rules edits small. Touches 6 count-lock files (mechanical).
- **Per-project monthly DFS cost estimate (load-bearing):** `summary` $0.0200 + `timeseries_new_lost_summary` (13 monthly rows) $0.0204 + `referring_domains` (limit 100) $0.0230 ≈ **$0.065/project/month**; 12-project portfolio ≈ **$0.78/month**. With optional `deep_spam_check` +$0.023. In engine budget units: declare `estimated_credits: 1` upper bound (pool default 500/day per `project-config.schema.json`) — negligible.
- **DURUR #0 (decision, before any code runs live):** the DFS **Backlinks API product requires a separate $100/month minimum commitment**. MCP tool visibility ≠ account product enabled; first live call may return a payment/permission error. Süleyman must confirm/enable Backlinks API on the org account — this is the real cost gate, not per-call credits. Wire DURUR: auth/4xx on first call → STOP, do not retry-burn credits.
- Other DURUR: budget preflight FAIL → awaiting_approval (never silent skip); DFS envelope drift → typed error; F-16: never touch `.mcp.json`.
- Dependency: none on other gaps. Collision: `monthly_report.py` + `monthly-report.template.md` + count-lock files (see unified doc wave order).

#### (f) What NOT to build

No link-building/outreach product (no prospecting, no email, no `backlink-outreach` SKILL — leave the events-writer placeholder as-is). No disavow file generation/upload. No anchor-text optimization advisor. No per-backlink row archive (1,000-row pulls monthly = cost with no monitoring value). No new master.xlsx sheet. No competitor backlink-gap module (`backlinks_competitors`/`domain_intersection` stay registered-but-unused until a real client need).

---

### GAP-A2: Local SEO depth (NAP consistency + review policy + location pages)

#### (a) 2026 best-practice basis (web-verified)

- **Incentivized reviews are prohibited; review gating is prohibited.** Maps UGC policy: no payment/discounts/free goods for posting, revising, or removing reviews; businesses must not "discourage or prohibit negative reviews, or selectively solicit positive reviews" — any sentiment-based filtering of who gets asked violates policy. Asking all customers for honest reviews (no incentive, no filter) is allowed. Violations now carry profile-level restrictions (review intake frozen / existing reviews unpublished). Sources: https://support.google.com/contributionpolicy/answer/7400114 · https://support.google.com/business/answer/14114287. Note: multiple industry write-ups report an **April 2026 review-policy enforcement tightening** (e.g. https://launchcodex.com/blog/seo-geo-ai/google-business-profile-review-policy-update/) — the policy template below must carry the two official URLs, not third-party summaries.
- **Location pages vs doorway policy.** Google's spam policy prohibits "multiple pages targeted at specific regions or cities that funnel users to one page" (https://developers.google.com/search/docs/essentials/spam-policies#doorway-pages). Practitioner consensus on the compliant pattern: per-location pages need location-unique substance (the specific office/service area, local case studies/jobs, staff, local FAQs, embedded map/NAP, photos taken there) — "city-swap boilerplate where two pages are ~90% identical" is the red flag (e.g. https://ricketyroo.com/blog/location-page-spam/). NAP representation authority: GBP "Guidelines for representing your business on Google" — https://support.google.com/business/answer/3038177.
- Citation/NAP consistency remains a hygiene factor (consistency across GBP, site footer, contact page, and major directories); for the TR market there is no reliable citations API — directory data beyond Google is operator work.

#### (b) Repo integration points (verified by reading)

- `skills/discovery/gbp-audit/SKILL.md` — read-only GBP gap audit, profile-gated (`local-service`), 8 categories incl. `nap` and `reviews`, budget ~3 credits, consent `requires_approval: true`. **Verified gap:** `scripts/discovery/gbp_audit_transform.py:21` declares `nap HIGH NAP mismatch with project.config domain (Phase 11)` in the severity matrix **but `_analyze_gaps` never implements it** — and SKILL.md Step 4 reads `config["brand_identity"]["business_name"]` / `["primary_location"]`, **which do not exist in `schemas/project-config.schema.json#brand_identity` (additionalProperties: false)** — a latent contract bug this gap closes.
- `schemas/master-excel.schema.json#gbp_audit` — 7-col sheet already exists with `category` enum `["nap","categories","photos","hours","attributes","posts","qa","reviews"]`; **NAP findings land here, no sheet change**. Writer registered: `scripts/excel/transaction.py:122` `"gbp_audit": frozenset({"gbp-audit"})`.
- `schemas/dataforseo-endpoint-mapping.schema.json` `projectionMode` enum already contains `nap_consistency_audit` (line 78) — pre-existing vocabulary, usable as-is.
- `project-config.schema.json` — schema_version `"1.5"` (const), migrations through `migration_0005`; bumping it for NAP would force a migration script + 12 live workspace configs + cascade tests. Avoided (see c).
- `templates/manifest.json` — `templates/content/*` family uses `{{UPPER_SNAKE}}` double-brace dialect (skill-side render), `templates/reports/*` uses string.Template; new templates auto-covered by globs.
- Scrapling MCP free (`mcp__ScraplingServer__fetch` already `optional` in gbp-audit frontmatter).

#### (c) Design — what is rule/skill-worthy vs template/checklist

**Decision matrix:** NAP consistency check → **code** (deterministic, repeatable, closes a declared-but-missing transform branch). Review acquisition → **rule + operator policy template** (engine must never automate review solicitation; policy compliance is a document, not code). Location-page methodology → **rule + content template + checklist** (production guidance; the doorway signal already has a data source — SF `near_duplicates_report` is an existing canonical export — so no new audit code). Citation building across TR directories → **checklist only** (no API; operator work).

**No new skill** (deliberately avoids the skill-count cascade) and **no new sheet**. Deliverables:

1. **`schemas/local-nap.schema.json`** (NEW standalone schema — avoids the project-config v1.5→v1.6 const bump + migration_0006 + live-config migration): canonical NAP doc at `projects/{slug}/local/nap.json`. Shape: `{schema_version: "1.0", business_name, phone (E.164 string), address: {street, district, city, postal_code, country}, locations: [{location_id, name, phone, address{...}, gbp_place_id?}], source_pages: [uri...]}`. Required: `schema_version, business_name, phone, address`. Multi-location support is first-class (portfolio reality: 13-unit STK precedent). Note in the schema description: candidate for folding into project.config at the next scheduled const bump.
2. **`scripts/discovery/nap_consistency.py`** (NEW, ~200 lines, pure): `normalize_phone(raw, default_country="TR") -> str` (E.164-ish; tolerate `0 (212) 123 45 67`, `+90...`, spaces/dashes), `normalize_address_tokens(raw) -> list[str]` (casefold, Turkish İ/ı fold, abbreviation map: `cad./caddesi`, `mah./mahallesi`, `no:/numara`), `compare_nap(canonical: dict, observed: dict) -> list[dict]` → mismatch findings `{field, canonical_value, observed_value, observed_source}`. Deterministic, no I/O.
3. **`scripts/discovery/gbp_audit_transform.py`** — implement the declared nap branch: `_analyze_gaps(listing, config, canonical_nap=None)` gains NAP comparison via `nap_consistency.compare_nap` (listing name/phone/address vs `local/nap.json`); each mismatch emits a `category="nap", severity=HIGH` row (existing 7-col `_row` helper). `canonical_nap` absent → emit one `category="nap", severity=MEDIUM, "Canonical NAP file missing (projects/{slug}/local/nap.json)"` row. Also fix the SKILL.md Step-4 contract: read `business_name` from `local/nap.json` (fallback: `config["display_name"]`), **not** the nonexistent `brand_identity.business_name` (update `skills/discovery/gbp-audit/SKILL.md` Step 4 + new optional input `nap_source` accordingly; additive frontmatter edit, version `"1.0"`→`"1.1"`).
4. **`rules/local-seo-discipline.md`** (NEW): **R-144** (spec'd R-127) — NAP single source of truth: `projects/{slug}/local/nap.json` is the only canonical NAP; every skill/report that prints NAP reads it; mismatches found anywhere (GBP, site footer, schema LocalBusiness) are HIGH findings, never silently "fixed" in copy. **R-145** (spec'd R-128) — review acquisition white-hat: engine and operator assets must never offer incentives for reviews, never gate/filter by sentiment, never draft incentive copy; ask-everyone post-service flows with the direct GBP review link are the only sanctioned pattern (cite both support.google.com URLs verbatim in the rule). Production skills must not emit incentive phrases (TR patterns: "yorum karşılığı indirim", "puan karşılığı hediye") — listed as forbidden patterns so `scripts/validation/content_validator.py` can adopt them later (adoption itself out of scope). **R-146** (spec'd R-129) — location-page anti-doorway: a location page ships only with ≥3 location-unique elements (location-specific service detail, local proof/case/photo, location FAQ, embedded map + per-location NAP from nap.json), no city-swap boilerplate (pairwise near-duplicate vs sibling location pages must stay under the SF near-duplicate threshold — signal already available via the existing `near_duplicates_report` canonical export), every location page in nav/sitemap (no orphans), one page per real serviced location only — no page for cities without genuine service presence.
5. **`templates/content/location-page.template.html`** (NEW, double-brace dialect): skeleton with `{{LOCATION_NAME}}`, `{{LOCATION_UNIQUE_INTRO}}`, `{{LOCAL_PROOF_BLOCK}}`, `{{LOCATION_FAQ}}`, `{{NAP_BLOCK}}`, `{{MAP_EMBED}}`, plus a `LocalBusiness` JSON-LD block fed from nap.json fields. (NO bare R-NNN tokens in templates — `tests/rules/test_r_xx_resolution.py` constraint.)
6. **`templates/content/review-acquisition-policy.template.md`** (NEW, double-brace): operator-facing TR policy handout per client — what staff may/may not say, the two official policy URLs, the GBP review-link QR flow, response-rate targets (ties into the existing gbp-audit `reviews` category thresholds). (NO bare R-NNN tokens.)

#### (d) Test plan (TDD, RED-first)

- `tests/discovery/test_nap_consistency.py` (NEW, ~12 cases): phone normalization TR variants (`0 212 123 45 67` ≡ `+902121234567`), İ/ı casefold, abbreviation equivalence (`Atatürk Cad. No:5` ≡ `ataturk caddesi numara 5`), true mismatch detected (different street number), multi-location matching by `location_id`, determinism.
- `tests/skills/test_gbp_audit_nap.py` (NEW, ≥6 cases, fixtures mirror `tests/skills/test_gbp_audit.py`): RED first — canonical nap.json + listing with mismatched phone → `category="nap"` HIGH row with both values in `gap_description`; nap.json missing → MEDIUM "canonical NAP file missing" row; matching NAP → zero nap mismatch rows; emitted rows still validate against the 7-col gbp_audit contract (severityEnum/statusEnum strict); existing cases in `tests/skills/test_gbp_audit.py` stay green (regression).
- `tests/schemas/test_local_nap_schema.py` (NEW): Draft7 self-validates; minimal valid doc passes; missing phone fails.
- Template dialect lock: `tests/reporting/test_template_dialect.py` already enforces family membership — new templates must satisfy it.

#### (e) Size + dependencies + DURUR risks

- Size: ~1 worker batch (2 new modules ~350 lines, 1 schema, 1 rules file, 2 templates, ~20 tests, SKILL.md additive edit). Zero new paid calls (reuses gbp-audit's existing ~3-credit run; Scrapling free).
- DURUR risks: gbp-audit SKILL.md edit must stay additive — its frontmatter is validated by CI Draft7 frontmatter-compile, and `tests/skills/test_gbp_audit.py` re-validates it; the Step-4 `brand_identity.business_name` fix is a behavior change to document in the SKILL changelog block. Multi-location NAP at 13-unit scale means `compare_nap` must not assume single location — covered in tests. No consent change: skill remains read-only.
- Dependency: none on other gaps. Files touched are disjoint from GAP-A1 and GAP-A3.

#### (f) What NOT to build

No review-management/solicitation automation, no review-request UI or email/SMS flows (policy + operator handout only). No review-response generator (operator voice). No TR citation-directory submission automation (no APIs; submission is outward → would need consent gates for near-zero value). No GBP write/API integration of any kind (hard constraint). No new `local_citations` master.xlsx sheet — findings ride the existing `gbp_audit` sheet. No programmatic location-page generator (that IS the doorway machine; engine provides template + rules, content production stays through new-blog/revise-content discipline).

---

### GAP-A3: Merchant-side structured data (listing experience requirements)

#### (a) 2026 best-practice basis (web-verified)

- **Merchant listing required vs recommended (verified against the official doc):** for merchant listing experiences, `Offer.price` (or `priceSpecification.price`) **> 0** and `priceCurrency` are **required**; `shippingDetails` (`OfferShippingDetails`) and `hasMerchantReturnPolicy` (`MerchantReturnPolicy`) are **recommended, not required** — they unlock shipping/returns annotations in results. Merchant listings require `Offer` (not `AggregateOffer`) and the merchant must be the seller. https://developers.google.com/search/docs/appearance/structured-data/merchant-listing
- **Organization-level shipping (Nov 12, 2025):** site-wide shipping policy markup is `Organization` → **`hasShippingService`** → **`ShippingService`** (required prop: `shippingConditions` of type `ShippingConditions`; recommended: `fulfillmentType`, `handlingTime`, `shippingRate`, `transitTime`, `shippingDestination`…), recommended placement = the site's shipping-policy page; **no Merchant Center account required**; per-offer `OfferShippingDetails` overrides it and should be used *only* when a product's policy differs from the global one. ⚠️ **There is no `OrganizationShippingDetails` type** — workers must use `Organization.hasShippingService`/`ShippingService`. Sources: https://developers.google.com/search/blog/2025/11/more-ways-to-share-shipping · https://developers.google.com/search/docs/appearance/structured-data/shipping-policy
- **Organization-level returns** (launched 2024, complemented by the 2025 shipping launch): `Organization` → `hasMerchantReturnPolicy` → `MerchantReturnPolicy`. https://developers.google.com/search/docs/appearance/structured-data/return-policy
- Search Console's "Shipping and returns" settings panel is now open to all merchant-classified sites without Merchant Center (alternative to markup; settings/Merchant Center override markup). https://searchengineland.com/google-shipping-and-returns-policies-in-search-console-or-using-new-markup-464560
- Practical TR-platform angle: Ticimax/Ideasoft/imagaza give limited template control, but all allow site-wide header/footer script injection — **org-level markup on one policy page is exactly the low-touch mechanism these platforms can deploy**, vs per-product Offer edits which are often impossible. This drives the org-level-first rule below.

#### (b) Repo integration points (verified by reading)

- `skills/discovery/schema-audit/SKILL.md` (636 lines) — status active, budget 0 credits, consumes SF `structured_data_all.csv` via sf-import envelope, optional paid DFS `on_page_content_parsing` cross-validate (`cross_validate_dfs`, ~3 credits/URL) and opt-in SF MCP live path (D-SF-11). Writes `master.xlsx#schema` (writer registered `transaction.py` `"schema": frozenset({"schema-audit"})`).
- `schemas/master-excel.schema.json#schema` sheet — 5 cols `schema_type | status | location | scope | remaining_work` (statusEnum). Merchant findings fit as rows (`schema_type` is free text). **No sheet change.**
- `project-config.schema.json` — `platform` enum `["wordpress","wordpress+woocommerce","ticimax","ideasoft","imagaza","custom"]`, `profiles` incl. `e-commerce`, `currency` ISO-4217 required. Profile gate mirrors gbp-audit Step 1.
- Scrapling tools free + already optional in skills; `mcp__ScraplingServer__fetch`/`bulk_get` registered in `mcp-tool-registry.json`.
- Portfolio fit: 5 e-commerce clients across imagaza/ticimax/ideasoft/woocommerce platforms.

#### (c) Design (minimal-but-complete)

**No new skill, no new sheet, no new MCP tools, 0 credits default.** Extend schema-audit with a merchant module:

1. **`scripts/discovery/merchant_listing_audit.py`** (NEW, ~300 lines, pure): entrypoint `audit_merchant_listings(jsonld_by_url: dict[str, list[dict]], org_jsonld: list[dict], config: dict, *, today: str) -> list[dict]` returning `schema`-sheet rows + a summary dict. Checks (each → one row, statusEnum seed `TODO`):
   - **M1 price-validity**: `Offer.price` present, numeric, > 0; `priceCurrency` present and == `config["currency"]` (TRY mismatches are a real TR-platform failure mode).
   - **M2 availability**: `Offer.availability` present and a valid `https://schema.org/…` enum value (`InStock`, `OutOfStock`, `PreOrder`, …).
   - **M3 offer-shape**: merchant-listing eligibility requires `Offer` (flag `AggregateOffer`-only products).
   - **M4 shipping coverage**: per-offer `shippingDetails` present **OR** org-level `Organization.hasShippingService` found in `org_jsonld`; neither → one site-level row "shipping markup missing — deploy org-level ShippingService on the shipping-policy page (platform-safe single script)".
   - **M5 returns coverage**: per-offer `hasMerchantReturnPolicy` **OR** org-level `Organization.hasMerchantReturnPolicy`; neither → site-level row.
   - **M6 staleness**: `priceValidUntil` in the past → row (price-accuracy signal).
   - **M7 (optional, flag `price_parity_sample`, default false)**: Scrapling `bulk_get` of N≤10 product URLs; compare JSON-LD price vs rendered price token (TR number formats `1.234,56`); mismatch → HIGH-equivalent row. Heuristic — default off, documented as such.
   - Severity-to-`remaining_work` text mapping documented in the module docstring (sheet has no severity col — encode priority words in `remaining_work`, consistent with current schema-sheet usage).
2. **`skills/discovery/schema-audit/SKILL.md`** — additive: new input `merchant_checks` (boolean, default: auto-on when `"e-commerce" ∈ project.config.profiles`, off otherwise — profile gate, no paid calls), new body step "Step 6b — merchant_listing_audit (pure compute)", outputs unchanged (`master.xlsx#schema` + report), `version: "1.0"`→`"1.1"`. Org JSON-LD source: homepage + policy pages already present in the SF structured-data export (same envelope); if absent → optional single Scrapling fetch of `/` (free), else M4/M5 emit "org markup not observable" rows.
3. **`rules/merchant-structured-data.md`** (NEW): **R-147** (spec'd R-130) — offer accuracy: schema price/availability/currency must mirror the live page; `priceCurrency` must equal `project.config.currency`; expired `priceValidUntil` must be removed or refreshed; engine never fabricates offer data it cannot observe. **R-148** (spec'd R-131) — shipping/returns org-level-first: on limited-template TR platforms (ticimax/ideasoft/imagaza) recommend `Organization.hasShippingService` + `Organization.hasMerchantReturnPolicy` on a single policy page; per-offer `OfferShippingDetails`/`hasMerchantReturnPolicy` only when a product genuinely deviates (quotes the Google doc's own "only if…override" guidance); markup is recommended-not-required for merchant listings — frame findings as opportunity, never as compliance failure.
4. **`templates/reports/schema-audit.template.md`** — add a `$merchant_findings_md` section (string.Template, existing file; small additive edit; NO bare R-NNN tokens).

#### (d) Test plan (TDD, RED-first)

- `tests/discovery/test_merchant_listing_audit.py` (NEW, ~14 cases): synthetic JSON-LD fixtures — (1) RED: ticimax-flavored `Product+Offer` with `price: "0"` → M1 row; (2) `priceCurrency: "USD"` vs config currency TRY → M1 row; (3) availability literal `"InStock"` (not URL form) → M2 row flags non-canonical value; (4) AggregateOffer-only → M3 row; (5) no per-offer shipping + org_jsonld contains `hasShippingService` → NO M4 row (org-level satisfies); (6) neither → one site-level M4 row (not per-product spam); (7) same pair for returns M5; (8) `priceValidUntil: "2025-01-01"` with `today="2026-06-10"` → M6; (9) rows conform to the 5-col schema-sheet contract; (10) determinism (today injected, no clock); (11) empty product set → empty findings, no crash; (12) woocommerce-flavored fixture passes clean (GREEN control).
- `tests/skills/test_schema_audit.py` (existing — verify exact name at build time) — regression: existing cases stay green; add frontmatter re-validation after the additive input.
- No live fetches in tests; M7 Scrapling path covered via monkeypatched fetch returning canned HTML with TR-formatted price.

#### (e) Size + dependencies + DURUR risks

- Size: ~1 worker batch (~300-line module + ~350-line tests + 2 doc edits + 1 rules file). 0 credits default; M7 optional and free (Scrapling).
- DURUR risks: schema-audit SKILL.md is large (636 lines) and frontmatter-locked by CI — additive edits only; its existing test suite re-validates frontmatter, so run the full `tests/skills/` scope. The `schema` sheet has only 5 columns — resist adding severity columns (that WOULD be a sheet change + cascade); encode priority in `remaining_work`. AMO parallel-worktree caution applies.
- Dependency: none. Disjoint from GAP-A1/A2 files.

#### (f) What NOT to build

No Merchant Center API integration, no feed generation/submission (Ticimax/Ideasoft have native GMC feeds; not our layer). No auto-injection of markup into client sites (engine is audit + deliverable-spec; deployment is the developer-brief path). No Search Console settings automation (it's a UI panel; mention it in `remaining_work` text as the no-code alternative). No full schema.org validator re-implementation (only the 7 merchant checks above; generic JSON-LD validity is already schema-audit's existing job). No per-product crawling of 30K-product catalogs (M7 capped at N≤10 sample).

---

### GAP-A4: Log-file analysis — FEASIBILITY VERDICT: SPEC-ONLY DEFERRAL

#### (a) 2026 best-practice basis (web-verified) + honest feasibility

- **GSC Crawl Stats has NO API in 2026.** Verified directly against the official Search Console API reference: exposed resources are exactly `searchanalytics.query`, `sitemaps.{delete,get,list,submit}`, `sites.{add,delete,get,list}`, `urlInspection.index.inspect` — no crawl-requests/host-status/crawl-budget endpoint. Crawl Stats remains a UI-only report (Settings → Crawl stats; manual export possible). Sources: https://developers.google.com/webmaster-tools/v1/api_reference_index (fetched and confirmed) · https://support.google.com/webmasters/answer/9679690 (UI report doc).
- **Raw server logs:** Ticimax / Ideasoft / imagaza are hosted TR SaaS platforms — no documented raw access-log export in their panels; clients cannot grant what the platform doesn't expose. That covers the e-commerce majority. WordPress clients are host-dependent (cPanel/awstats sometimes available) — but no client has provided log access to date, and chasing per-host access for a portfolio of small/mid TR sites has poor effort/value vs existing signals (GSC quick-wins + SF crawls already cover indexability triage).
- What a log analysis would uniquely add (crawl-budget waste, bot-hit frequency per template, 304/404 hit ratios) is partially approximable for free: `urlInspection` returns `lastCrawlTime` per URL (the engine's `gsc__index_inspect` MCP tool is already registered, 0 credits, quota ~2,000/property/day), and SF crawl snapshots give the "what exists" side of the SF-pages vs server-hits gap.

**Verdict: do NOT build. Ship a deferral spec with explicit build triggers.**

#### (b) Repo integration points (verified — relevant to the deferral doc only)

- `mcp-tool-registry.json` gsc server: `gsc__index_inspect` (category `index_inspect`, 0 credits, cache 168h) — the only crawl-adjacent primitive available today. The pinned `mcp-server-gsc@0.3.0` (`.mcp.json`) exposes no crawl-stats tool (none exists upstream to wrap).
- `skills/publishing/verify-indexing/SKILL.md` — existing consumer of `index_inspect`; the natural future home for a `lastCrawlTime`-sampling micro-feature (NOT built now).
- `skills/ingestion/sf-import/SKILL.md` — the manual file-drop ingestion pattern a future Crawl-Stats-UI-export path would mirror.
- Deferral doc home: `docs/superpowers/specs/` (existing dir precedent).

#### (c) Design — the deferral deliverable

One file: **`docs/superpowers/specs/2026-06-10-log-file-analysis-feasibility.md`** containing:
1. The verdict + evidence above (API reference snapshot, platform constraints per client class, dated).
2. **Build triggers (re-open conditions):** T1 — any client delivers ≥30 days of raw access logs; T2 — Google ships a Crawl Stats API endpoint; T3 — a concrete crawl-budget incident (e.g. faceted-URL explosion on a 30K-product hosted-platform site) that GSC UI + SF cannot diagnose.
3. **Pre-designed Phase-2 sketch** (so the future build is a worker prompt, not a research project): (i) *crawl-freshness sampling* — extend verify-indexing: sample N=50 priority URLs (from `quick_wins` + `topical_map` sheets) monthly via `gsc__index_inspect`, persist `{url, lastCrawlTime, coverageState}` to `_state/staging/crawl_freshness_{YYYY-MM}_{slug}.json`, report stale-crawl deltas (0 credits, no new MCP); (ii) *Crawl-Stats UI manual export file-drop* — `inbox/gsc-crawl-stats/{date}/*.csv` mirroring sf-import, only if an operator actually commits to the monthly UI export ritual; (iii) *raw-log path* (T1 only) — single deterministic parser to staging JSON, explicitly NOT a streaming pipeline.
4. What was deliberately not built and why (cost/value table).

#### (d) Test plan

None (no code). The doc itself is the artifact; if Phase-2(i) is ever triggered, its spec section must include RED-first tests for the sampling transform (synthetic index_inspect payloads, stale-vs-fresh classification boundary).

#### (e) Size + dependencies + DURUR risks

- Size: 1 doc, ~150-250 lines. Zero runtime risk, zero credits.
- Risk if skipped entirely: the monthly template's crawl story stays GSC/SF-only — acceptable; record the decision so future audits see a written rationale instead of a "gap".

#### (f) What NOT to build

No log ingestion pipeline, no log-storage schema, no new sheet, no log-analyzer product, no per-host cPanel scraping automation, no speculative Crawl Stats UI scraping via browser automation (fragile, ToS-gray, and the data is shallow).

---

### Priority & batching recommendation

| Batch | Gap | Verdict | Why this order |
|---|---|---|---|
| **B1** | GAP-A3 merchant | **build now** | Highest client surface (5 e-commerce clients), 0 credits, no count cascade, no consent decision needed. |
| **B2** | GAP-A2 local | **build now** | 4+ local-service clients; closes a verified declared-but-unimplemented contract in gbp-audit; 0 new credits. |
| **B3** | GAP-A1 backlinks | **build after consent** | Code is small, but **DURUR #0 (DFS Backlinks API $100/month minimum commitment) is a Süleyman decision that must precede dispatch**. |
| **B0** | GAP-A4 log files | **defer with spec** | Doc-only; can ride along any batch or ship standalone. |

**Parallelization & file-collision map:**
- **B1 ∥ B2 are safe in parallel** — fully disjoint files. Only shared risk: shared-worktree full-suite runs — apply the AMO contention discipline (scope-verify own dirs, attribute sibling failures).
- **B3 must run LAST and alone**: it is the only A-batch touching the **count-lock cluster** and the **monthly-report files** — sequence after every other monthly-report-touching batch.
- **R-number allocation: see unified doc §R-MAP** (R-142/143 backlinks · R-144-146 local · R-147/148 merchant). Each batch creates its own new rules file; none edits an existing one.
- Shared invariants every batch must respect: `.mcp.json` byte-untouched (F-16/ADR-040 + ci.yml 4-server invariant); additive-only schema edits; transforms deterministic and event-silent (D-003 — orchestrator writes provenance + `cost.credits`); consent posture unchanged (all three built gaps are read-only audits/ingestions; `requires_approval: true`, `safe_auto_execute: false`).

**Two found-and-flagged repo bugs folded into the batches:** (1) `mcp-tool-registry.json` under-prices `backlinks_summary`/`backlinks_competitors` ~100× vs verified DFS pricing → corrected in B3; (2) gbp-audit SKILL.md Step 4 reads `brand_identity.business_name`/`primary_location`, which `project-config.schema.json#brand_identity` (`additionalProperties: false`) does not permit → fixed by B2's canonical `local/nap.json`. Also note for workers: there is no `OrganizationShippingDetails` type — the correct markup is `Organization.hasShippingService` → `ShippingService` (+required `ShippingConditions`).
