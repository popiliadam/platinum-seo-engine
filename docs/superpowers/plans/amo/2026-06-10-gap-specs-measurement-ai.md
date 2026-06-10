### GAP-M1: Measurement design (core-update calendar, pre/post windows, intervention-vs-control)

#### (a) 2026 best-practice basis (web-verified 2026-06-10)

- **Canonical machine-readable core-update calendar source exists and is verified live:** `https://status.search.google.com/incidents.json` — a JSON **array** of incident objects with exact fields `id`, `number`, `begin`, `end`, `external_desc`, `severity`, `service_name` (`"Ranking"` | `"Serving"` | `"Indexing"`), `affected_products[{title,id}]`, `updates[]`, `most_recent_update`, `status_impact`. Verified real entry: `{"external_desc": "May 2026 core update", "begin": "2026-05-21T15:40:00+00:00", "end": "2026-06-02T12:40:00+00:00", "severity": "low", "service_name": "Ranking", "status_impact": "SERVICE_INFORMATION"}`. Filter rule for the calendar: `service_name == "Ranking"`. History is retained 5 years; RSS alternative at `https://status.search.google.com/en/feed.atom` (docs: https://developers.google.com/search/help/status-dashboard). This kills any need for hand-maintained update lists.
- **Google's own measurement guidance:** do not assess effects until an update's rollout is *complete* (the `end` field above); core updates roll out over ~2 weeks. Hence "settling buffer" below.
- **Honest attribution floor for a tool of this size:** difference vs. a matched untouched control set (treated quick-win queries vs same-band untouched queries), medians not means, no significance theater at n<30. This is the lightweight standard recommended in SEO testing practice (split/control testing); full causal inference (CausalImpact etc.) is explicitly out of scope (see f).

#### (b) Repo integration points (all VERIFIED by reading)

- `scripts/reporting/monthly_report.py` (794 lines) — `REQUIRED_SECTIONS` 10-tuple at line 33; `assemble_report()` at line 509; `FRAMING_POLICY_ENUM = {"positive_client","internal"}` line 38; CLI `--project-slug --workspace-root --period-end --framing-policy --output-formats --template --output-dir` (lines 674–696). **Known fabrication to retire:** `_build_keywords_up()` lines 318–337 invents `position_before = position_after + 3` ("transparent positive-framing approximation").
- `schemas/monthly-report.schema.json` — `sections.additionalProperties: false`, `required` = the 10 sections, `schema_version` const `"1.0"`. Adding a section ⇒ must add an **optional** property (additive; do NOT extend `required`; keep const `"1.0"` per ADR-018 additive precedent — same pattern as `new_content_plan` +3 columns and events `event_type` 10→12).
- `templates/reports/monthly-report.template.md` — 10 numbered sections + final `## Kanıt zinciri` block; `string.Template` `$var` substitution via `render_report_markdown()`.
- `mcp-tool-registry.json` (repo **root**) + `schemas/mcp-tool-registry.schema.json` — the precedent for "versioned instance data file at root + meta-schema in `schemas/`". Reuse exactly this layout for the calendar file.
- `skills/discovery/quick-wins/SKILL.md` — 10-step protocol; Step 4 transform → `scripts/discovery/quickwins_transform.py`; Step 7 writes via `scripts/orchestration/committer.py` → `transaction.replace` (whole-block snapshot replace, header rewritten in canonical schema order — verified in `scripts/excel/transaction.py` `_ensure_sheet_with_header`, lines 668–691).
- Longitudinal raw record already exists: date-stamped immutable inbox payloads `projects/{slug}/inbox/gsc/{date}-detect_quick_wins-{slug}.json` and `{date}-search_analytics-{slug}.json` (quick-wins SKILL.md Step 2, gsc-pull SKILL.md Step 2) — pre/post comparison reads two dated snapshots, no new collection needed.
- `schemas/events.schema.json` — `event_kind` enum `[provenance, work, audit, workflow]`; `event_type` is WORK-only, **closed 12-value enum**: `content_new, content_revise, content_remove, tech_fix, quickwin_applied, pillar_launch, schema_fix, redirect_deployed, backlink_outreach, manual, skill_content_remediation, skill_whats_next`; provenance requires `run_id + source + operation`; `operation` enum `[ingest, normalize, project_excel, validate, cascade_done, staging]`; `source.kind` enum `[sf_csv, gsc_mcp, dataforseo_mcp, scrapling_local, scrapling_mcp, sf_mcp, manual, tool_computed]`. **No events schema change needed**: cohort writes are `event_kind=provenance, operation=staging`; `quickwin_applied` already exists to mark interventions.
- Append-only `_state/` sidecar precedent: `scripts/state/anomaly_recorder.py` docstring documents the schema-free JSONL ledger family (`anomalies.jsonl`, `consent.jsonl`, `cost_ledger.jsonl`) at `projects/{slug}/_state/`.
- Rule IDs: repo max is **R-122**; R-122–124 reserved by another batch ⇒ this cluster starts at **R-125**. New rules file must satisfy `schemas/rules-frontmatter.schema.json` (required: `name, status, applies_to, spec_section`; validated by `tests/rules/test_frontmatter.py` glob `rules/*.md`).
- `rules/time-discipline.md` — UTC ISO-8601 storage only; naive `datetime.now()` banned in storage paths; all new functions take dates as args.

#### (c) Design

**D1. Core-update calendar — versioned data file (engine seed) + workspace overlay (runtime refresh).**

- NEW `google-update-calendar.json` at engine repo root (beside `mcp-tool-registry.json`). Format:
  ```json
  {
    "schema_version": "1.0",
    "retrieved_at": "2026-06-10T00:00:00Z",
    "source_url": "https://status.search.google.com/incidents.json",
    "updates": [
      {"id": "<dashboard id>", "name": "May 2026 core update",
       "begin": "2026-05-21T15:40:00Z", "end": "2026-06-02T12:40:00Z",
       "service_name": "Ranking", "severity": "low", "source": "google_status_dashboard"}
    ]
  }
  ```
  Seed content: worker fetches `incidents.json` once at build time, filters `service_name=="Ranking"`, keeps last 24 months. `end` is nullable (rolling updates).
- NEW `schemas/google-update-calendar.schema.json` — Draft-07, `additionalProperties: false`, `$id: "http://platinum-seo-engine/schemas/google-update-calendar"` (ADR-012 HTTP host convention, see `rules/naming.md:20`).
- **Who updates it:** (1) engine releases — maintainer downloads `incidents.json` and runs NEW `scripts/maintenance/refresh_update_calendar.py --incidents <file> --calendar google-update-calendar.json --write` (pure parse/merge, **no network in script** — orchestration-in-skills rule); (2) runtime — NEW step in `skills/reporting/monthly-report/SKILL.md` instructs the agent to fetch `https://status.search.google.com/incidents.json` via `mcp__ScraplingServer__get` (free, read-only — not consent-gated), drop raw to `projects/{slug}/inbox/calendar/{date}-google-updates.json`, then run the same refresh script with `--write-overlay {workspace}/shared/cache/google-update-calendar.json`. Plugin cache dir is never written at runtime (engine file = seed; workspace overlay = fresh).
- NEW pure module `scripts/reporting/update_calendar.py`: `load_calendar(engine_path, overlay_path=None) -> list[dict]` (union by `id`, overlay wins); `overlaps(period_start: str, period_end: str, updates: list, settle_buffer_days: int = 7) -> list[dict]` returning `{name, begin, end, overlap_days, phase}` where `phase ∈ {"rolling","rollout_in_period","settling"}` (`settling` = update `end` within `settle_buffer_days` before `period_start`).

**D2. Report annotation — `measurement_context` section in monthly report.**

- `schemas/monthly-report.schema.json`: add OPTIONAL `sections.measurement_context` property (object): `core_updates_overlap[]`, `measurement_quality` enum `["clean","update_overlap","post_update_settling","insufficient_history"]`, `intervention_outcomes[]` (D3 below), `notes`. NOT added to `required` (old reports stay valid). `schema_version` const stays `"1.0"`.
- `scripts/reporting/monthly_report.py`: new builder `_build_measurement_context(period_start, period_end, calendar_updates, cohort_results)`; wire into `assemble_report()` sections dict; extend `_flatten_for_template` + template with new section `## 11. Ölçüm Bağlamı` (overlap table + one-line verdict: "Bu dönem {name} ile çakışıyor — trafik deltaları tek başına motor çalışmasına atfedilemez"). New CLI args `--calendar-path` (default: `_REPO_ROOT / "google-update-calendar.json"`) and `--overlay-calendar-path` (optional). **Framing invariance is a hard contract:** the section is built identically for `positive_client` and `internal` (test-enforced) — facts survive framing.
- Retire the `_build_keywords_up` `position_before = position_after + 3` fabrication: when no longitudinal evidence, emit `position_before: null` and keep the field optional in the schema (check `keywords_up` item schema in `schemas/monthly-report.schema.json`; if `position_before` is required there, make it nullable — additive `["number","null"]`).

**D3. Intervention-vs-control for quick-wins — staging JSON cohorts, NO new sheet.**

- `scripts/discovery/quickwins_transform.py`: `transform()` gains a third output array `control_cohort`. Selection: from scored-but-not-selected rows (rank `top_n+1 ..`), greedy-match per treated row the nearest candidate with `|position diff| ≤ 2` and `0.5× ≤ impressions ratio ≤ 2×`; each control used once; deterministic (sort by score desc, query asc — same tiebreak discipline as existing code). Output meta gains `controls_matched`, `score_version`.
- `skills/discovery/quick-wins/SKILL.md`: new Step 7b — write `projects/{slug}/_state/metrics/quickwin-cohorts/{date}-cohort.json`:
  ```json
  {"cohort_date": "...", "score_version": "2.0",
   "treated": [{"query","url","position","impressions_30d","clicks_30d"}],
   "controls": [...same shape...],
   "matching": {"position_tolerance": 2, "impressions_ratio_max": 2.0}}
  ```
  plus a provenance event (`event_kind=provenance`, `source.kind=tool_computed`, `operation=staging`, `target_excel_sheet=null`, `target_table="quickwin_cohort"`, `notes="cohort_tagged"`).
- NEW pure module `scripts/reporting/intervention_outcome.py`: inputs = cohort file + a later dated GSC payload (`inbox/gsc/{date}-search_analytics-{slug}.json` or `detect_quick_wins` shape); per group computes median position delta and Σclicks delta %; outcome = `treated_delta − control_delta` (difference, reported in percentage points), `verdict ∈ {"engine_positive","engine_negative","indistinguishable"}` with fixed honesty threshold (|difference| < 10pp ⇒ `indistinguishable`) and `caveat: "n<30 — directional evidence only"`. No p-values.
- `skills/reporting/monthly-report/SKILL.md`: new step — locate cohort files ≥21 days old, pair with the newest GSC inbox payload, run `intervention_outcome.py`, pass results into `monthly_report.py` (new CLI arg `--cohort-results <json path>`; absent ⇒ section says "kohort verisi yok").

**D4. New rules file** `rules/measurement-discipline.md` (frontmatter: `name: Measurement Discipline`, `status: enforced`, `applies_to: [plugin]`, `spec_section: "measurement"`, `applied_to_skills: [quick-wins, monthly-report, monitoring-weekly]`):
- **R-125** — Core-update overlap annotation: every periodic report (monthly, weekly) MUST annotate overlap of its window with `service_name=="Ranking"` calendar entries (incl. 7-day settling buffer); deltas in overlapping windows MUST NOT be attributed to engine work or to the update without the annotation.
- **R-126** — Intervention cohort tagging: every quick-wins detection run MUST persist a treated+control cohort snapshot; outcome claims about quick-wins MUST be reported as treated-vs-control difference, never raw treated delta.
- **R-127** — Versioned measurement constants: CTR curves, AIO discount factors, anomaly thresholds live in versioned data files with provenance fields; literal copies in Python/SKILL bodies are banned (grep-sentinel-testable).

#### (d) Test plan (TDD, RED first; frozen dates as args; synthetic fixtures)

- NEW `tests/reporting/test_update_calendar.py`: (1) parse synthetic `incidents.json` fixture (3 entries: Ranking update, Serving outage filtered out, rolling update `end=null`); (2) `overlaps("2026-05-25","2026-06-20", ...)` → May-2026-like entry with `overlap_days=8`, phase `rollout_in_period`; settling-buffer case (period starting 2026-06-05 → `settling`); (3) overlay-wins merge; (4) bundled `google-update-calendar.json` validates against the new schema (Draft7Validator); (5) grep sentinel: `update_calendar.py` and `refresh_update_calendar.py` contain no `requests`/`urllib`/`http` import.
- NEW `tests/reporting/test_intervention_outcome.py`: synthetic cohort + post payload where treated improve (median −4 pos) and controls flat → `engine_positive`, treated and controls both improve → `indistinguishable`; missing control rows in post payload tolerated (dropped from medians, counted in `attrition`).
- EXTEND `tests/skills/test_monthly_report.py` (or NEW `tests/reporting/test_measurement_context.py`): section present and **byte-identical numbers** under both framing policies; `measurement_quality="update_overlap"` for a window straddling 2026-05-21..06-02 fixture calendar; old-shape report (no measurement_context) still validates vs schema; `keywords_up` no longer emits `pos_after+3`.
- EXTEND `tests/skills/test_quick_wins.py`: cohort array determinism (same input → same controls), matching tolerances respected, controls disjoint from treated.

#### (e) Size + dependencies + DURUR risks

- Size: ~2 new schemas/data files, 3 new modules (~150–250 lines each), monthly_report.py +~120 lines, 2 SKILL.md edits, 1 rules file, ~25 tests. One worker session.
- Dependencies: none new (stdlib + jsonschema already in `requirements.txt`). ScraplingServer MCP already wired.
- DURUR risks: (1) `schemas/monthly-report.schema.json` `additionalProperties:false` — forgetting to register the new optional property fails assembly tests; (2) **file collision** — `monthly_report.py` + `monthly-report.template.md` + `monthly-report.schema.json` are also touched by the framing-tone batch (see batching section); (3) status dashboard endpoint shape drift — mitigated: refresh script validates parsed output against the schema and DURURs on mismatch; (4) workspace `shared/cache/` dir may not exist — `mkdir(parents=True)`.

#### (f) What NOT to build

No causal-inference library (CausalImpact, DiD regressions, synthetic controls); no significance tests at n<30; no per-project custom update lists; no scraping of third-party update trackers (Semrush sensor etc.) — the Google dashboard JSON is the single source; no dashboard UI; no automatic re-fetch scheduler (refresh rides existing report skill runs).

---

### GAP-M2: AI Overview presence tracking (+ fix `aio-competitor-map` wrong premise)

#### (a) 2026 best-practice basis (web-verified)

- **DataForSEO response schema (docs-verified):** `serp/google/organic/live/advanced` returns an `items[]` entry with `"type": "ai_overview"` carrying `rank_group, rank_absolute, position, xpath, asynchronous_ai_overview, markdown`, nested `items[]` of `"ai_overview_element"` (`title, text, markdown, links, images, references`) and top-level `references[]` of `"ai_overview_reference"` (`source, domain, url, title, text`). Sources: https://docs.dataforseo.com/v3/serp-se-type-live-advanced/ and https://dataforseo.com/help-center/how-to-scrape-google-ai-overviews-with-serp-api.
- **Async caveat (load-bearing):** many AIOs load asynchronously. Without request param `load_async_ai_overview=true`, asynchronous AIOs come back as `ai_overview: null` (presence UNDERCOUNTED); cached/sync AIOs appear automatically. The param **doubles the request charge** ($0.0006 → $0.0012 for live/advanced; surcharge refunded when no async AIO exists).
- **Wrapper limitation (verified against the live MCP tool schema in this environment):** `mcp__dataforseo__serp_organic_live_advanced` (dataforseo-mcp-server@2.8.10) exposes ONLY `keyword*, language_code*, location_name (default "United States"), depth, device, max_crawl_pages, people_also_ask_click_depth, search_engine`. It does **NOT** expose `load_async_ai_overview` and does **NOT** accept `location_code`. Consequence #1: MCP-path presence detection is sync-only ⇒ record `not_detected`, never `absent`. Consequence #2: TR projects must verify served locale (known wrapper bug; engine already ships Method C machinery — see (b)).
- **Why this matters economically:** AIO presence cuts expected CTR of any future win roughly in half (Ahrefs 2026-02-04, 300K-keyword GSC study: −58% at pos 1 … −19.4% at pos 10 — https://ahrefs.com/blog/ai-overviews-reduce-clicks-update/; Pew Research 2025 panel: 8% vs 15% link-click rate — i.e. ≈−47%). Recording presence is the prerequisite for Gap-M3's discount.

#### (b) Repo integration points (all VERIFIED by reading)

- `skills/discovery/aio-competitor-map/SKILL.md` (483 lines) — **wrong premise lives here**: Step 2 (lines 154–159) extracts ONLY `item["type"] == "organic"`; Step 4 (lines 190–260) scores competitor schema markup (R-109/110/111) and the doc labels that an "AIO citation pattern" proxy. Frontmatter: `mcp_tools.required: [mcp__dataforseo__serp_organic_live_advanced, mcp__ScraplingServer__fetch]`, `estimated_credits: 30`, budget DURUR #1, staging-only output `inbox/competitor_pages/{date}-{slug}.jsonl`, master.xlsx-write banned (sentinel test `test_no_master_xlsx_write_invariant` in `tests/skills/test_aio_competitor_map.py`, ≥12 cases).
- `mcp-tool-registry.json` — `dataforseo__serp_organic_live_advanced` registered: `cost_credits_per_call: 0.0035`, `cache_ttl_hours: 24`, category `serp_scrape`. No registry change required.
- `schemas/dataforseo-endpoint-mapping.schema.json` — meta-schema only (no instance file in engine); `staging_table` pattern `^dfs_[a-z][a-z0-9_]*$`; `logicalSheet` enum already includes `quick_wins` and `opportunity`.
- Method C (direct REST) machinery to REUSE, not rebuild: `scripts/ingestion/dfs_pull.py` — `DFS_API_BASE = "https://api.dataforseo.com/v3"` (line 144), `http_credentials_from_env()` (~line 489), `build_http_payload_tr()` (~line 467), `detect_response_locale()` (~line 354), `response_honors_tr()` (~line 405).
- `schemas/master-excel.schema.json` — `quick_wins` sheet cols A–J (`query,url,current_position,impressions_30d,clicks_30d,ctr_pct,potential_clicks,opportunity,action,priority`), header_row 4 / data_start_row 5; `opportunity` sheet cols A–H, header_row 4 / data 5. **Additive-column precedent without schema_version bump:** `new_content_plan` description (lines 119) documents +3 columns "additive, ADR-018 paterni, schema_version bump değil". `transaction.replace` rewrites the full header row in canonical schema order on every write (`scripts/excel/transaction.py:688-691`) ⇒ existing project workbooks pick up new columns on the next quick-wins run, **no migration script needed**.
- `skills/discovery/quick-wins/SKILL.md` — steps list in Step 1 `create_run` (lines 100–113); Step 4 transform CLI (lines 150–157); DURUR list (10 items, lines 259–274); frontmatter `budget.uses_paid_mcp: false / estimated_credits: 0` (will change).
- `schemas/events.schema.json` — `source.kind=dataforseo_mcp` exists; `cost` object with `credits` exists (see aio-competitor-map Step 7 usage as the canonical example).

#### (c) Design

**D1. Fix `aio-competitor-map` (premise correction, additive parsing).**

- Step 2 (SERP extract): additionally scan `serp_items` for `item["type"] == "ai_overview"`; build:
  ```python
  aio_item = next((i for i in serp_items if i.get("type") == "ai_overview"), None)
  serp_aio = {
      "aio_presence": "present" if aio_item else "not_detected",   # MCP path can NOT prove absence
      "asynchronous_ai_overview": bool(aio_item.get("asynchronous_ai_overview")) if aio_item else None,
      "reference_count": len(aio_item.get("references") or []) if aio_item else 0,
      "cited_domains": sorted({r.get("domain") for r in (aio_item.get("references") or []) if r.get("domain")}),
      "own_domain_cited": project_domain in {...same set...},
      "detection_source": "dfs_mcp_sync",
  }
  ```
  (`project_domain` from `project-config[domain]`, already in `consumes`.)
- Step 5 staging record: add the `serp_aio` block once per run (top-of-file header line or replicated per row — choose ONE header JSONL line `{"record_kind":"serp_aio", ...}` followed by per-URL rows; document in SKILL.md Outputs).
- Rewrite the premise prose: R-109/R-110/R-111 stay, but re-labeled "competitor content-quality signals" — delete every claim that schema markup of organic results *is* AIO citation evidence ("AIO citation pattern empirik olarak…", Step 4 enforcement notes lines 262–272, description lines 8–15). The REAL citation evidence is `serp_aio.cited_domains` from the `references[]` payload. New comparison output: which top-10 organic URLs' domains appear in `cited_domains` (`organic_rank ∩ aio_cited` map).
- DURUR adjustments: DURUR #4 ("AIO signal 0") now triggers only when `aio_presence=="not_detected"` AND R-signals are 0 — and its report wording must say "sync-path could not detect an AIO; absence not proven (wrapper lacks load_async_ai_overview)".
- Document the **Method C upgrade path** in a new SKILL.md section "Async AIO limitation (2.8.10)": optional `aio_rest: boolean` input (default false). When true, the skill posts directly to `{DFS_API_BASE}/serp/google/organic/live/advanced` with `[{"keyword":…, "location_code":…, "language_code":…, "depth":…, "load_async_ai_overview": true}]` using `dfs_pull.http_credentials_from_env()` — `detection_source: "dfs_rest_async"`; cost doubles per call (0.0035→0.007 credit accounting; surcharge refunded by DFS when no async AIO — record the *requested* cost in events, note the refund rule). TR projects: verify served locale via `dfs_pull.detect_response_locale` (existing wrapper-TR-bug discipline).

**D2. AIO presence for quick-win queries (two-pass in quick-wins skill).**

- `skills/discovery/quick-wins/SKILL.md` frontmatter: new inputs `aio_check: {type: boolean, required: false, default: false}` and `aio_top_k: {type: integer, required: false, default: 20}`; `budget.uses_paid_mcp` becomes conditional note (`true when aio_check`), `estimated_credits: 0 (aio_check=false) / ~0.07-0.14 (aio_check=true, K=20)`. Budget pre-flight reuses the aio-competitor-map DURUR #1 pattern verbatim. Consent: NOT required (read-only SERP fetch; consent gates outward actions only) — say so explicitly in the SKILL.
- New steps (names added to Step-1 `create_run` steps list): after `transform` pass-1, `fetch_aio_presence` — for the provisional top-`aio_top_k` queries call `mcp__dataforseo__serp_organic_live_advanced(keyword=query, language_code=…, location_name=…, depth=10)`; persist consolidated raw to `projects/{slug}/inbox/dfs/{date}-aio_presence-{slug}.json` (`{query: <raw items subset or full payload per query>}`; raw-inbox-first §16.5 discipline); then `transform` pass-2 with `--aio-presence <path>` (Gap-M3 CLI). Provenance event: `event_kind=provenance, source.kind=dataforseo_mcp, operation=ingest, target_table="dfs_aio_presence", cost={"provider":"dataforseo","credits": K*0.0035, "budget_key":"project.config.budget_credits_per_day"}`.
- New transform helper in `scripts/discovery/quickwins_transform.py`: `load_aio_presence(path) -> dict[str, dict]` mapping query → `{aio_presence: "present"|"not_detected", own_domain_cited: bool, checked_date: str, detection_source: str}`; queries absent from the file → `"unchecked"`.

**D3. Sheet columns (additive, no schema_version bump — ADR-018 precedent).**

- `schemas/master-excel.schema.json` `quick_wins.required_columns` append: `K aio_presence` (`enum: ["present","not_detected","unchecked"]`), `L aio_own_cited` (`type: boolean`), `M aio_checked_date` (`type: date`), `N expected_uplift_clicks` (`type: integer`, Gap-M3). `opportunity.required_columns` append: `I aio_presence` (same enum), `J expected_uplift_clicks` (`type: integer`). Update `QUICK_WINS_COLUMNS` / `OPPORTUNITY_COLUMNS` tuples in `quickwins_transform.py` (lines 61–83) to match; transform always emits all keys (`"unchecked"`/`false`/`""`/computed when `aio_check=false`).

**D4. Rule R-128** (in `rules/measurement-discipline.md`, Gap-M1 file): AIO presence recording discipline — MCP-sync detection may only assert `present` or `not_detected` (never `absent`); `unchecked ≠ not_detected`; any CTR/uplift claim on an AIO-`present` query must carry the discount (Gap-M3); citation evidence comes only from the `references[]` payload, never from schema-markup inference.

#### (d) Test plan (TDD, RED first)

- EXTEND `tests/skills/test_aio_competitor_map.py`: (1) fixture SERP payload (built to the docs shape) with one `ai_overview` item (2 `ai_overview_reference` entries, one matching project domain) → `serp_aio` parsed: presence `present`, `reference_count==2`, `own_domain_cited True`; (2) payload without the item → `not_detected` (assert the literal string — `absent` must not appear anywhere in skill body: grep sentinel); (3) `asynchronous_ai_overview: true` flag propagated; (4) staging file contains exactly one `record_kind=="serp_aio"` line; (5) SKILL.md grep: the string "AIO citation pattern" proxy claim removed / re-worded, `load_async_ai_overview` limitation section present; (6) existing invariants stay green (no master.xlsx write, no URL fabrication).
- EXTEND `tests/skills/test_quick_wins.py`: `load_aio_presence` happy/missing-file/malformed; rows emit `unchecked` defaults when no AIO file; columns K–N present in every emitted row and aligned with the updated schema (Draft7-validate sheet contract vs row keys, mirroring existing tests).
- NEW `tests/schemas/` case: master-excel schema column letters contiguous A.. for both sheets (guard against gap typos).

#### (e) Size + dependencies + DURUR risks

- Size: aio-competitor-map SKILL.md ~80 changed lines; quick-wins SKILL.md ~60 added lines; transform +~80 lines; schema edit; ~15 tests. Shares a worker session with Gap-M3 (same files).
- Dependencies: none new. Paid budget impact documented (default OFF).
- DURUR risks: (1) wrapper undercount (async AIOs ⇒ `not_detected`) — mitigated by honest enum + documented REST path; (2) wrapper `location_name`-only signature — SKILL must pass `location_name` (e.g. `"Turkey"`), and TR projects must locale-verify (existing Method-C discipline; cite `feedback_dfs_wrapper_tr_bug` behavior); (3) committer `RowSchemaError` if transform emits old 10-key rows after the schema gains K–N — update tuples and schema in the SAME commit; (4) 24h DFS cache means re-runs within a day return cached SERPs — fine (cheaper), but `aio_checked_date` must come from the run date arg, not payload.

#### (f) What NOT to build

No AIO tracking for all `cluster_keywords` rows (only quick-win candidates top-K); no AIO content/text storage beyond domains+counts (no LLM summarization of AIO text); no `ai_mode` / `ai_summary` endpoints (separate DFS products); no new MCP server or wrapper fork to add `load_async_ai_overview` — the REST path documented in the skill suffices; no historical AIO presence time-series sheet.

---

### GAP-M3: Quick-win opportunity scoring upgrade (expected-CTR-uplift model)

#### (a) 2026 best-practice basis (web-verified)

- **Position-CTR curve source:** First Page Sage 2026 report (last updated 2025-05-28; meta-analysis incl. Backlinko/Sistrix/internal data) — per-position organic CTR for clean SERPs: P1 39.8%, P2 18.7%, P3 10.2%, P4 7.2%, P5 5.1%, P6 4.4%, P7 3.0%, P8 2.1%, P9 1.9%, P10 1.6% (https://firstpagesage.com/reports/google-click-through-rates-ctrs-by-ranking-position/). Positions 11–20 are not published there; Advanced Web Ranking maintains live monthly curves (https://www.advancedwebranking.com/free-seo-tools/google-organic-ctr) — the data file marks 11–20 values as `engine_estimate` provenance and they are *fallback-only* (current clicks are observed from GSC, so the curve is only consulted for the **target** position, which is ≤10 by design).
- **AIO discount factors (per target position):** Ahrefs study, published 2026-02-04, 300K keywords, GSC desktop CTR Dec-2023 vs Dec-2025 — CTR reduction when AIO present: P1 −58.0%, P2 −50.8%, P3 −46.4%, P4 −38.8%, P5 −32.6%, P6 −30.5%, P7 −29.7%, P8 −28.8%, P9 −29.7%, P10 −19.4% (https://ahrefs.com/blog/ai-overviews-reduce-clicks-update/). Cross-check magnitude: Pew Research 2025 — 8% vs 15% result-click rate with/without AI summary (≈−47%). Discount factor = 1 + reduction (e.g. P7 ⇒ 0.703).
- **Model form (industry standard for forecast-style scoring):** expected clicks gain = impressions × CTR(target position) × AIO factor − current clicks, with observed clicks subtracted so already-good CTR rows don't double-count. Conservative target = bottom half of page 1, never top-3.

#### (b) Repo integration points (all VERIFIED by reading)

- `skills/discovery/quick-wins/SKILL.md` §"Opportunity score" (lines 249–257): `score = impressions * max(0, threshold_position_max - position)` — no CTR anywhere, while the frontmatter description (line 6) advertises "CTR düşük yüksek impression".
- `scripts/discovery/quickwins_transform.py`: `opportunity_score()` lines 97–123 (same formula); `_opportunity_label` ≥5000/≥1500 and `_priority_label` thresholds lines 200–215 (score-unit-coupled — must be re-banded); `_row_pct` CTR unit heuristic lines 227–244 (GSC `detect_quick_wins` returns CTR as percent, `enhanced_search_analytics` as fraction — registry confirms, `mcp-tool-registry.json` gsc tool descriptions); `potential_clicks` is pass-through of the GSC MCP's own `potentialClicks` (line 309) — keep as-is, separate column from our model.
- `scripts/util/profile_aware_defaults.py` `cascade_default` — existing 3-tier override mechanism (CLI > profile config > inline default) already imported by the transform (lines 52–54, 459–468); use it for `aio_discount_default` / `target_position_floor` overrides.
- Versioned-data-file precedent: `mcp-tool-registry.json` root instance + `schemas/mcp-tool-registry.schema.json` meta-schema.
- Sheets and additive-column mechanics: see GAP-M2 (b) — `expected_uplift_clicks` columns ride the same schema edit.
- `templates/reports/quickwin.template.md` — `$top_score` variable and "Opportunity score" labels; needs wording update to "beklenen tıklama kazanımı (28g)".

#### (c) Design

**D1. NEW `ctr-curve.json` (engine root) + `schemas/ctr-curve.schema.json`.**

```json
{
  "schema_version": "1.0",
  "curve_version": "2026.06",
  "sources": [
    {"name": "first_page_sage_2026", "url": "https://firstpagesage.com/reports/google-click-through-rates-ctrs-by-ranking-position/", "retrieved": "2026-06-10", "covers": "positions 1-10"},
    {"name": "ahrefs_aio_2026_02", "url": "https://ahrefs.com/blog/ai-overviews-reduce-clicks-update/", "retrieved": "2026-06-10", "covers": "aio_discount_by_position"},
    {"name": "pew_research_2025", "url": "https://www.pewresearch.org/", "retrieved": "2026-06-10", "covers": "aio_discount_default cross-check"}
  ],
  "positions": [
    {"position": 1, "ctr": 0.398, "provenance": "first_page_sage_2026"},
    {"position": 2, "ctr": 0.187, "provenance": "first_page_sage_2026"},
    {"position": 3, "ctr": 0.102, "provenance": "first_page_sage_2026"},
    {"position": 4, "ctr": 0.072, "provenance": "first_page_sage_2026"},
    {"position": 5, "ctr": 0.051, "provenance": "first_page_sage_2026"},
    {"position": 6, "ctr": 0.044, "provenance": "first_page_sage_2026"},
    {"position": 7, "ctr": 0.030, "provenance": "first_page_sage_2026"},
    {"position": 8, "ctr": 0.021, "provenance": "first_page_sage_2026"},
    {"position": 9, "ctr": 0.019, "provenance": "first_page_sage_2026"},
    {"position": 10, "ctr": 0.016, "provenance": "first_page_sage_2026"},
    {"position": 11, "ctr": 0.010, "provenance": "engine_estimate"},
    {"position": 15, "ctr": 0.006, "provenance": "engine_estimate"},
    {"position": 20, "ctr": 0.003, "provenance": "engine_estimate"}
  ],
  "interpolation": "linear_between_listed_positions",
  "aio_discount": {
    "default": 0.5,
    "by_position": {"1": 0.420, "2": 0.492, "3": 0.536, "4": 0.612, "5": 0.674,
                     "6": 0.695, "7": 0.703, "8": 0.712, "9": 0.703, "10": 0.806},
    "fallback_11_20": 0.806
  }
}
```
Schema: Draft-07, `additionalProperties:false`, ctr ∈ (0,1), factors ∈ (0,1], positions strictly increasing, provenance enum. Updated manually per engine release when a newer study lands (`curve_version` bump = data change; R-127 forbids constants in code).

**D2. NEW loader `scripts/util/ctr_curve.py`** (pure): `load_curve(path) -> Curve`; `Curve.expected_ctr(position: float) -> float` (linear interpolation between listed positions, clamp ends); `Curve.aio_factor(position: float, aio_presence: str) -> float` (`present` → by_position/fallback; `not_detected`/`unchecked` → **1.0** — honesty: unknown is not discounted, it is flagged).

**D3. Scoring v2 in `quickwins_transform.py`.**

```python
def expected_uplift_clicks(impressions, position, clicks, curve, aio_presence="unchecked"):
    target = min(10.0, max(5.0, float(position) - 5.0))   # conservative: page-1 bottom half, never top-3
    ctr_t = curve.expected_ctr(target) * curve.aio_factor(target, aio_presence)
    return max(0, int(round(impressions * ctr_t - (clicks or 0))))   # existing-clicks subtraction
```
- Primary ranking key becomes `expected_uplift_clicks` (desc); legacy `opportunity_score` retained as deterministic tiebreaker #2 (then query asc, url asc — preserves current tiebreak discipline). `opportunity` sheet col B `opportunity_score` keeps the legacy number (no column re-semantics); new cols carry the model (GAP-M2 D3: `quick_wins.N`, `opportunity.J` = `expected_uplift_clicks`; `aio_presence` cols).
- Re-band labels on click units: `_opportunity_label` / `_priority_label` → High/HIGH ≥ 50 expected clicks/28d, Medium/MEDIUM ≥ 15, else Low/LOW (defaults; `cascade_default`-overridable keys `uplift_high_threshold`, `uplift_medium_threshold`).
- `transform()` signature gains `curve: Curve` (required) and `aio_presence: dict | None`; CLI gains `--ctr-curve` (default `_REPO_ROOT / "ctr-curve.json"`) and `--aio-presence` (optional). `meta` gains `score_version: "2.0"`, `curve_version`, `aio_checked_count`.
- `skills/discovery/quick-wins/SKILL.md` §"Opportunity score" rewritten with the formula above + worked example + provenance pointers; Step 4 CLI block updated with the two new flags; DURUR #11 added: `ctr-curve.json` missing or schema-invalid → DURUR (no silent fallback to legacy formula).
- `templates/reports/quickwin.template.md`: rename score labels; add `$top_uplift` + `$aio_present_count` variables (SKILL Step 8 variable list updated).

#### (d) Test plan (TDD, RED first; exact-value assertions)

NEW `tests/skills/test_quickwins_scoring_v2.py` (+ extend `tests/skills/test_quick_wins.py`):
1. Curve loader: bundled `ctr-curve.json` validates vs `schemas/ctr-curve.schema.json`; `expected_ctr(7) == 0.030`; interpolation `expected_ctr(12.5)` between listed 11/15 values; clamp `expected_ctr(25) == ctr(20)`.
2. Uplift math (frozen fixture curve): `impressions=1000, position=12, clicks=10, unchecked` → target `min(10,max(5,7))=7` → `1000*0.030−10 = 20`. Same row `aio_presence="present"` → `1000*0.030*0.703−10 = 11` (int round). `clicks=40` → `max(0, …) == 0` (subtraction floor).
3. Ranking: uplift desc primary, legacy score tiebreak — construct two rows with equal uplift, different legacy scores.
4. Honesty invariants: `unchecked` factor 1.0; factor never >1; R-127 grep sentinel — no literal `0.398`/`0.703` (any curve constant) in `quickwins_transform.py`/SKILL body outside the worked-example fence.
5. Determinism/idempotence: `transform(raw, curve, aio)` twice → identical output.
6. Label re-banding: uplift 60 → HIGH; 20 → MEDIUM; 5 → LOW.
7. RED-first ordering: write tests 1–6 against the not-yet-edited transform → all fail → implement.

#### (e) Size + dependencies + DURUR risks

- Size: 1 data file + 1 schema + 1 loader (~120 lines) + transform edits (~100 lines) + SKILL/template edits + ~18 tests. **Same worker session as GAP-M2** (identical files).
- Dependencies: none new.
- DURUR risks: (1) `_row_pct` percent/fraction ambiguity — uplift math uses **clicks** (unambiguous) not stored ctr_pct, keep it that way; (2) label thresholds drive `master_task` generation downstream (`master_task_sync` consumes priorities) — re-banding changes task volume; document in SKILL changelog, no code change needed there; (3) collision: another batch touches `skills/discovery/quick-wins/SKILL.md` for position-band alignment — same-file merge hazard (see batching); (4) dashboard KPI `quick_wins_count` (R52) unaffected (row count, not score).

#### (f) What NOT to build

No per-project fitted CTR curves from GSC regression (future option; needs the Gap-M4 history to mature first — note as deferred, do not stub); no device/intent-segmented curves; no Monte-Carlo/uncertainty intervals; no auto-refresh of the curve from AWR's live tool; no rescoring cron; no changes to the GSC `potential_clicks` passthrough column.

---

### GAP-M4: Weekly anomaly detection statistics (replace the 5σ/8-week placeholder)

#### (a) 2026 best-practice basis

- **Why 5σ on n=8 is meaningless:** sample SD from 8 weekly points is itself extremely noisy (and inflated by the very anomaly being tested, masking it); weekly GSC series are non-normal, trending and seasonal; with n=8 a genuine 5σ event would essentially never fire (dead alarm) or fires off SD-estimation noise. Standard lightweight remedy: **robust statistics** — median + MAD with the Iglewicz–Hoaglin modified z-score `M = 0.6745·(x − median)/MAD`, outlier at `|M| ≥ 3.5` (NIST/SEMATECH e-Handbook of Statistical Methods, §1.3.5.17, https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm). MAD has a 50% breakdown point — one bad week doesn't poison the threshold.
- **Count-noise floor:** for low-volume projects (median <~100 clicks/week) any robust z fires on trivia; accepted practice is to AND the statistical trigger with **fixed floors** (minimum % delta AND minimum absolute delta). Both together, per the brief's "or both".
- **Attribution honesty:** an anomaly overlapping a Google Ranking-update window (Gap-M1 calendar) must be annotated and not escalated as an engine regression (Google's own guidance: assess after rollout completes).

#### (b) Repo integration points (all VERIFIED by reading)

- `skills/reporting/monitoring-weekly/SKILL.md` (568 lines) — the placeholder to replace lives in: description lines 11–13 & 26–28; DURUR #5 lines 197–210 ("5σ … trailing 8-week mean"); Workflow step 4 lines 224–230; inline Block 3 `gsc_anomaly_section` deferral string lines 381–385 and `escalations` lines 390–393; Principle-1 deferral lines 466–477. **The placeholder is also unimplementable as written:** it claims to read `master.xlsx[gsc_performance]` "rows ordered by date_iso" — verified `schemas/master-excel.schema.json#gsc_performance` (cols A–L) has **no date column**, and `skills/ingestion/gsc-pull/SKILL.md` Step 7 writes it via `committer.commit` = `transaction.replace` **snapshot** (recent-vs-previous only). There is no weekly time series anywhere in master.xlsx. A history store is a hard prerequisite.
- Inline-runtime conventions to follow: monitoring-weekly is **no-MCP, strict read-only on master.xlsx**, 3 inline Python blocks, imports `scripts.state.events_writer` (Block 3 line ~417) — importing a new pure module is consistent; events via `events_writer.append_audit(audit_action="accessed", audit_target="reports:monitoring-weekly:…", actor="agent:monitoring-weekly")`.
- History-store precedent: schema-free append-only JSONL sidecars at `projects/{slug}/_state/` (`anomalies.jsonl` / `consent.jsonl` / `cost_ledger.jsonl` — `scripts/state/anomaly_recorder.py` docstring, incl. the O_APPEND+flock+fsync `_atomic_append_line` pattern to copy).
- Writer side: `skills/ingestion/gsc-pull/SKILL.md` (10 steps; Step 2 `fetch_search_analytics` raw-inbox-first; Step 4 transform = `scripts/ingestion/gsc_pull.py`; frontmatter `dimensions` input default `["page"]`; `mcp_tools.required: [mcp__gsc__enhanced_search_analytics, mcp__gsc__search_analytics]`, both free per `mcp-tool-registry.json`).
- `rules/time-discipline.md` — UTC storage; ISO week computation must be UTC-date based; frozen dates passed as args (no `date.today()` inside the stats module).
- Templates: `templates/reports/monitoring-weekly.template.md` exists (DURUR #4 inline fallback duplicated in SKILL Block 3 `INLINE_TEMPLATE` — both carry `$gsc_anomaly_section`).

#### (c) Design

**D1. Weekly history ledger (prerequisite, owned by gsc-pull).**

- NEW file per project: `projects/{slug}/_state/metrics/gsc-weekly.jsonl`, one line per ISO week:
  ```json
  {"iso_week": "2026-W23", "week_start": "2026-06-01", "week_end": "2026-06-07",
   "clicks": 412, "impressions": 18230, "ctr": 0.0226, "avg_position": 14.2,
   "source": "gsc_mcp", "written_at": "2026-06-10T06:02:11Z"}
  ```
- `skills/ingestion/gsc-pull/SKILL.md`: Step 2 additionally fetches a **site-level daily series** — `mcp__gsc__search_analytics(dimensions=["date"], startDate=today−days_back, endDate=today)` (free) → `inbox/gsc/{date}-search_analytics_daily-{slug}.json` (raw-inbox-first). New Step 7b: `python3 scripts/ingestion/gsc_pull.py --append-weekly-ledger --daily <inbox path> --ledger <ledger path> --today <ISO date>` — `gsc_pull.py` gains a pure function `aggregate_iso_weeks(daily_rows, today)` (only **complete** Mon–Sun weeks; week containing `today` excluded) and an idempotent appender: read existing `iso_week` keys, append only missing weeks via the `anomaly_recorder._atomic_append_line` pattern (O_APPEND + flock + fsync; **never rewrites** — append-only-state rule). Provenance event `operation=staging, target_table="gsc_weekly_ledger", target_excel_sheet=null`.
- Cold-start backfill: documented one-shot variant — same step with `days_back=112` (16 complete weeks, single free GSC call). One SKILL.md paragraph; no separate skill.

**D2. NEW stats module `scripts/reporting/weekly_anomaly.py`** (pure, deterministic, dates as args):

```python
detect(records, current_iso_week, *, window=13, min_points=6,
       floors={"clicks": {"pct": 0.25, "abs_min": 10},
               "impressions": {"pct": 0.25, "abs_min": 100},
               "ctr": {"abs_pp": 0.5}, "avg_position": {"abs": 1.5}},
       k_modified_z=3.5, mad_zero_pct=0.40) -> dict
```
- Trailing baseline = up to `window` (13) most recent complete weeks **before** `current_iso_week`, requiring ≥ `min_points` (6); fewer ⇒ `{"status": "insufficient_history", "points_used": k, "needed": 6}` — rendered honestly, no alarm.
- Per metric ∈ {clicks, impressions, ctr, avg_position}: `median`, `MAD = median(|x_i − median|)`, modified z of the current week `M = 0.6745·(x − median)/MAD` (NIST/Iglewicz–Hoaglin). Flag iff `|M| ≥ 3.5` **AND** floors pass (clicks/impressions: `|x − median|/median ≥ pct` AND `|x − median| ≥ abs_min`; ctr: absolute percentage-point floor; position: absolute floor). `MAD == 0` (constant baseline) ⇒ fallback rule: flag iff `|x − median|/max(median,1) ≥ mad_zero_pct` AND abs floor.
- Direction-aware severity: clicks/impressions **drop** or position **increase** (worse) ⇒ candidate `RED`; improvement directions ⇒ `INFO`. ctr drop ⇒ `AMBER`.
- Calendar interaction (Gap-M1 dependency, soft): caller passes `update_overlaps` (from `scripts/reporting/update_calendar.py.overlaps` for the week window ± 7-day settle buffer); any overlap ⇒ severity capped at `AMBER` + `attribution_caution: "<update name> rollout/settling overlaps this week"`. If calendar files are absent, proceed with `update_overlap: "calendar_unavailable"` (no crash).
- Returns full evidence: `{status, points_used, window_weeks, metrics: {clicks: {value, median, mad, modified_z, flagged, direction, floors_passed}, …}, anomalies: […], severity, update_overlap}`.

**D3. monitoring-weekly SKILL.md rewrite (placeholder → active).**

- Delete every "5σ / trailing 8-week mean / Phase 14+ deferred" passage (the six locations in (b)); description Wave-3 scope paragraph re-written: GSC anomaly is ACTIVE, sourced from `_state/metrics/gsc-weekly.jsonl` (NOT master.xlsx — fix the false `date_iso` claim).
- DURUR #5 v2: "MAD anomaly with severity=RED → CRITICAL escalation: second `append_audit` row (`audit_target="reports:monitoring-weekly:{week}:anomaly"`, notes carrying metric/magnitude/direction/modified_z), report `escalations` section populated". Insufficient history is NOT a DURUR — it renders the honest `insufficient_history k/6` string.
- Block 3 edit: read ledger lines → `from scripts.reporting import weekly_anomaly, update_calendar` → `detect(...)` with `current_iso_week` derived from `week_start/week_end` env inputs (already validated ISO) → render `gsc_anomaly_section` (per-metric table: value vs median, modified z, flag) + `escalations`; keep severity rollup logic in Block 2, now max(drift severity, anomaly severity). Template `templates/reports/monitoring-weekly.template.md` + `INLINE_TEMPLATE`: section text changes only ($var slots unchanged — no template-variable break).
- Budget-burn placeholder (DURUR #2 / step 5): OUT OF SCOPE here — leave text intact, do not implement (scope guard).
- **R-129** (in `rules/measurement-discipline.md`): weekly anomaly detection MUST use median+MAD modified z (k=3.5) with percent+absolute floors over ≥6 complete ISO weeks; σ-based thresholds on n<30 weekly aggregates are banned in skills/scripts; alerts overlapping calendar Ranking windows are capped AMBER with attribution caution.

#### (d) Test plan (TDD, RED first; all-synthetic, frozen dates)

- NEW `tests/reporting/test_weekly_anomaly.py`:
  1. 12 flat weeks (clicks 100±5) + current 40 → clicks flagged, `modified_z ≤ −3.5`, direction `drop`, severity RED.
  2. Same baseline, current 88 → |M| large-ish but pct floor 12% < 25% ⇒ NOT flagged (floor suppression).
  3. Low volume: median 8 clicks, current 4 → pct 50% but `abs_min 10` suppresses ⇒ not flagged.
  4. `MAD == 0` (constant 100s), current 55 → fallback pct rule fires.
  5. 5 baseline weeks → `insufficient_history`, `points_used == 5`.
  6. Position 12→18 (worse) flags with direction `worse`; clicks +200% flags as `INFO` not RED.
  7. Update overlap (fixture calendar with begin/end covering the week) → severity capped AMBER + `attribution_caution`.
  8. Determinism: same records twice → identical dict. No `datetime.now` in module (grep sentinel).
- EXTEND `tests/skills/test_gsc_pull.py`: `aggregate_iso_weeks` — 28 daily rows spanning a month boundary → correct Mon–Sun buckets, current partial week excluded; ledger idempotence — append twice with same payload ⇒ file byte-identical after first append (read-back dedupe by `iso_week`); existing lines never modified (prefix hash unchanged).
- EXTEND `tests/skills/test_monitoring_weekly.py`: Block-3 path renders computed section from a fixture ledger (no deferral strings left — grep SKILL.md for "5σ" must return 0 hits); RED anomaly ⇒ exactly 2 audit rows; missing ledger ⇒ `insufficient_history` render, no crash, severity unchanged from drift rollup.

#### (e) Size + dependencies + DURUR risks

- Size: stats module ~200 lines; `gsc_pull.py` +~120 lines; 2 SKILL.md edits (monitoring-weekly heavy: ~120 changed lines); template wording; ~25 tests. One worker session.
- Dependencies: none new (pure stdlib `statistics.median`). Soft dependency on Gap-M1's `update_calendar.py` (graceful if absent — build M1 first or same wave).
- DURUR risks: (1) **collision** — `skills/reporting/monitoring-weekly/SKILL.md` is also touched by the band-alignment batch; (2) ledger contention if gsc-pull runs concurrently across sessions — mitigated by the flock append pattern (copy `anomaly_recorder._atomic_append_line` exactly); (3) cold-start: every existing project starts at `insufficient_history` — expected; document the 112-day backfill in the SKILL so operators can prime it in one run; (4) GSC daily data lags ~2 days — week containing `today` is already excluded; also exclude the most recent week if its `week_end ≥ today − 2` (add to `aggregate_iso_weeks` contract + test).

#### (f) What NOT to build

No STL/Prophet/ARIMA seasonality decomposition; no per-query anomaly detection (site-level weekly only); no YoY seasonal adjustment until the ledger holds ≥53 weeks (emit `yoy_unavailable`, revisit then); no alerting transport (email/Slack) — the audit event + report section is the alarm; no master.xlsx schema change (the ledger is `_state/`-side by design); no anomaly auto-remediation routing.

---

### Priority & batching recommendation

**Build-now vs defer:** All four are build-now EXCEPT two consciously deferred internals: per-project fitted CTR curves (M3-f, needs M4's ledger to mature) and YoY seasonality (M4-f, needs ≥53 weeks). Highest leverage first: M4 (a live placeholder that is both statistically wrong and unimplementable against the real sheet) and M1's calendar (May-2026 core update just ended 2026-06-02 — every June report window overlaps its settling buffer, so reports are mis-attributing **right now**).

**Two waves, three worker sessions:**

- **Wave 1a (worker A): GAP-M4 + GAP-M1 calendar core.** Files: `schemas/google-update-calendar.schema.json` + `google-update-calendar.json` + `scripts/maintenance/refresh_update_calendar.py` + `scripts/reporting/update_calendar.py` + `scripts/reporting/weekly_anomaly.py` (all NEW); `scripts/ingestion/gsc_pull.py`, `skills/ingestion/gsc-pull/SKILL.md`, `skills/reporting/monitoring-weekly/SKILL.md`, `templates/reports/monitoring-weekly.template.md`, `rules/measurement-discipline.md` (NEW, R-125/R-127/R-129 land here; leave numbered slots for R-126/R-128 text from Wave 1b/2).
- **Wave 1b (worker B, parallel-safe with A): GAP-M2 + GAP-M3.** Files: `skills/discovery/aio-competitor-map/SKILL.md`, `skills/discovery/quick-wins/SKILL.md`, `scripts/discovery/quickwins_transform.py`, `schemas/master-excel.schema.json`, `ctr-curve.json` + `schemas/ctr-curve.schema.json` + `scripts/util/ctr_curve.py` (NEW), `templates/reports/quickwin.template.md`. Zero file overlap with Wave 1a EXCEPT `rules/measurement-discipline.md` (R-126/R-128) — have worker B append its two rule sections only after A's file exists, or hand both gaps' rule text to worker A up front (recommended: A creates the complete 5-rule file; B doesn't touch it).
- **Wave 2 (worker C, AFTER the framing batch lands): GAP-M1 report integration.** Files: `scripts/reporting/monthly_report.py`, `schemas/monthly-report.schema.json`, `templates/reports/monthly-report.template.md`, `skills/reporting/monthly-report/SKILL.md` (engine has the skill dir under `skills/reporting/monthly-report/`), `scripts/reporting/intervention_outcome.py` (NEW) + quick-wins cohort Step 7b (touches `skills/discovery/quick-wins/SKILL.md` + `quickwins_transform.py` again ⇒ sequence AFTER Wave 1b, same files).

**File-collision map for the manager (exact paths):**

| File | This cluster | Other batch |
|---|---|---|
| `scripts/reporting/monthly_report.py` | Wave 2 (measurement_context, keywords_up fabrication removal) | framing-tone batch — **serialize: framing first, Wave 2 second**; framing invariance test in Wave 2 then locks both |
| `templates/reports/monthly-report.template.md`, `schemas/monthly-report.schema.json` | Wave 2 | framing-tone batch (same order) |
| `skills/discovery/quick-wins/SKILL.md` | Wave 1b + Wave 2 | band-alignment batch (position bands) — serialize within the same wave or assign both edits to one worker |
| `skills/reporting/monitoring-weekly/SKILL.md` | Wave 1a (anomaly rewrite) | band-alignment batch — serialize |
| `schemas/master-excel.schema.json` | Wave 1b (quick_wins K–N, opportunity I–J additive) | any other sheet-touching batch — additive-only, merge-friendly but same-file |
| `rules/measurement-discipline.md` | NEW — single owner = worker A | R-122–124 batch must NOT take R-125+ (this cluster claims R-125–R-129) |

Sources: [Google Search Status Dashboard help](https://developers.google.com/search/help/status-dashboard), [status.search.google.com/incidents.json](https://status.search.google.com/incidents.json), [DataForSEO live/advanced docs](https://docs.dataforseo.com/v3/serp-se-type-live-advanced/), [DataForSEO AIO scraping guide](https://dataforseo.com/help-center/how-to-scrape-google-ai-overviews-with-serp-api), [Ahrefs AIO −58% study (2026-02-04)](https://ahrefs.com/blog/ai-overviews-reduce-clicks-update/), [Pew Research via study roundups](https://www.searchenginejournal.com/ai-overview-ctr-fell-61-but-clicks-didnt-collapse/572993/), [First Page Sage CTR by position 2026](https://firstpagesage.com/reports/google-click-through-rates-ctrs-by-ranking-position/), [AWR organic CTR](https://www.advancedwebranking.com/free-seo-tools/google-organic-ctr), [NIST modified z-score](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).
