# Skill Contract Audit — Platinum SEO Engine

**Date:** 2026-06-04
**Scope:** All **45** skills × **7 contract dimensions** (trigger accuracy, status accuracy, paired-test meaningfulness, autonomy consistency, capability-vs-implementation, inputs/outputs drift, cross-ref validity).
**Mode:** READ-ONLY. No code or skill was modified. This is finding #2 in the workflow-audit series (after the 2026-06-04 deep quality/security audit).
**Method:** Dynamic multi-agent workflow — one finder agent per skill, then a 3-lens adversarial verification panel per finding (literalist · intentional-design · guard-aware), confirm threshold ≥2/3.

---

## Executive Summary

The 45-skill contract surface is **structurally honest at the autonomy/safety layer but heavily drifted at the documentation/schema layer.** Of 116 raw findings, the adversarial panel **confirmed 98 and eliminated 18 as false-positives / intentional design** (a 16% rejection rate — the elimination is the point).

- **0 critical, 24 high, 25 medium, 49 low.**
- **No new external-submit-without-consent violation and no AI-disclosure violation were found** — the indexing-ping consent gate and the content validator are holding. The single autonomy finding (monthly-report) is an *append-only* breach, not a consent breach.
- The damage is concentrated in **`6-io-drift` (36)** and **`7-crossref` (34)** — i.e. SKILL.md prose and frontmatter that fell behind two real schema migrations (`active_projects` maxItems **8→12**, `event_type` enum **10→12**) and behind the actual script signatures.
- **The single most operationally urgent cluster:** five reporting skills still enforce an `active_projects` ceiling of **8** while the schema (and the live ~10-project portfolio) is at **12**. A schema-valid config now makes those transforms *raise/halt*. This is an active breakage, not theoretical.
- **15 paired tests are weak or rubber-stamp** on side-effectful skills (the pattern this audit was asked to hunt).

> The highest-value reframe: most findings are not "the code is wrong" — they are "the SKILL.md promises something the code/schema/test no longer does." Operators (and future skill authors) are being misled by the contract, even where the runtime happens to be fine.

---

## ⚠️ Methodology & Recovery Note (read this)

The workflow (`wf_583fa7c9-c2c`) ran 45 finder + 348 verifier + 1 synthesizer agents. It completed **393 of 394 agents**, then the **account session usage limit was reached**. The final synthesizer was an unprotected `await agent()`; when it received the limit message instead of a completion, its throw propagated and discarded the in-memory result (a workflow design fragility — one unprotected agent became a single point of total failure, and workflow scripts cannot persist to disk mid-run).

**No work was lost and no agent was re-run.** Every successful agent's structured output was recovered from its cached transcript. 19 verifier agents (covering 7 findings) were the ones cut off by the limit; **those 7 findings were re-verified by hand against the cited files** and all 7 held. Two headline facts (`active_projects.maxItems`, `event_type` enum size) were also spot-checked directly against the live schemas.

**Caveats on confidence:**
- This is **static analysis** (reading SKILL.md + scripts + tests). Capability findings ("function X does not exist") are grep-verifiable and high-confidence. Some io-drift findings about *emitted payloads* are inferred from code-reading, not from observing a live emission.
- The **low-severity cross-ref cluster is judgment-dependent**: near-identical "10-enum" staleness was confirmed in some skills and rejected in others by the panel. A deterministic guard test would settle that line better than per-skill LLM judgment (see Completeness Critique).

---

## Statistics

| Metric | Value |
|---|---|
| Skills audited | 45 |
| Contract dimensions per skill | 7 |
| Raw findings (finder agents) | 116 |
| Unique after dedupe | 116 |
| **Confirmed** | **98** |
| — high / medium / low | 24 / 25 / 49 |
| **Rejected as false-positive** | **18** |
| Verifier verdicts from the panel | 329 |
| Findings re-verified by hand (limit-lost) | 7 |
| Skills with zero raw findings | 1 (`tech-audit`) |

**Confirmed findings by dimension:**

| Dimension | Count | Reading |
|---|---|---|
| 6 — inputs/outputs drift | 36 | declared I/O ≠ real script signature/output |
| 7 — cross-ref validity | 34 | stale/wrong schema·rule·ADR·line refs |
| 3 — paired-test meaningfulness | 15 | rubber-stamp / hollow tests |
| 5 — capability vs implementation | 9 | undocumented stubs (promise > reality) |
| 2 — status accuracy | 2 | stale test-docstring status |
| 1 — trigger accuracy | 1 | self-contradicting trigger contract |
| 4 — autonomy consistency | 1 | append-only breach |

---

## Cross-Cutting Themes

### Theme 1 — `active_projects` ceiling 8→12 never propagated  ·  **HIGH · operational break**
Schema `portfolio-config.schema.json#active_projects.maxItems` was raised **8→12** (description: *"raised 8→12 when the active portfolio reached 10"*). Five reporting skills + their transforms still hardcode/cite **8** and `DURUR`-halt on 9–12 projects. With the live portfolio at ~10, **a schema-valid config now makes these transforms raise/halt.**
`portfolio-heatmap`, `portfolio-kpi-trend`, `portfolio-monthly-roundup`, `portfolio-overview`, `portfolio-task-heatmap`. → **Fix as one lockstep change** (constant + SKILL.md refs + test fixtures), ideally reading `maxItems` from the loaded schema rather than re-hardcoding.

### Theme 2 — Undocumented capability stubs  ·  **HIGH · would crash or silently no-op**
SKILL.md presents as wired things the code does not provide. Contrast: `brand-onboarding` honestly frames its stubs as "PLANNED (Phase 14)"; these do not.
- `content-decay` → `check_budget.preflight()` + `BudgetGateError` (neither symbol exists)
- `sf-crawl-orchestrator` → `render_template.render()` (would `AttributeError`)
- `sf-import` → `mcp__gsc__list_sitemaps` + DURUR #4 sitemap-xcheck (not implemented); `workflow_runner` run-shell declared, never used
- `init-project` → cascade "auto-runner" + `cascade: brand-onboarding` event mechanism (does not exist)
- `mark-done` → `transaction.py` `WriterScopeError` hard-guard for `protected_columns` (only `allowed_writers` membership is checked; column-scope guard is absent)
- `monitoring-weekly` → headline capabilities (drift-via-events, 5σ GSC anomaly, budget burn) documented active, stubbed "Phase 14+"

### Theme 3 — events.jsonl schema violations  ·  **HIGH · runtime validation failure / append-only breach**
- `revise-content` — `event_kind=production` invalid (must be `work`)
- `master-task-sync` — `source.kind=local_aggregation` not a valid enum value
- `generate-images` — success-path `event_type=content_new` but the skill emits (and must emit) `manual`
- `new-blog` — R-121 prescribes a `master.xlsx[completed_work]` write, but F-1 sets `completed_work.allowed_writers=null` and the skill claims READ-ONLY
- `monthly-report` *(dimension 4)* — a "Q-RP-01 RESOLVED" block mutates **append-only** `events.jsonl`, contradicting the skill's own READ-ONLY + `safe_auto_execute` basis. **Most safety-relevant finding** (breaches the append-only hard rule); the frontmatter, paired test, command, and `events-writer.md` all already encode the deferral — the body block is the outlier.

### Theme 4 — Report-template variables not supplied → literal `$var` in published output  ·  io-drift
- `$run_id` is referenced by four report templates the builder never populates → published Markdown shows a literal `$run_id`: `portfolio-heatmap`, `portfolio-monthly-roundup`, `portfolio-weekly-brief`, `portfolio-task-heatmap`.
- Step-8 render-variable lists in SKILL.md don't match the actual template tokens → render **hard-fails if followed literally**: `gsc-pull` (HIGH), `on-page-audit`, `scrapling-ops`, `content-decay`.

### Theme 5 — Rubber-stamp / hollow paired tests  ·  the pattern this audit hunted
Side-effectful skills whose tests assert prose/shape but never exercise the contract: `glossary-audit` (asserts whitelist is *mentioned*, never runs detection), `sf-crawl-orchestrator` (simulates a fictional Step-5 export the body says never happens), `brand-onboarding` (Stage-C write test never validates the written config against the schema), `monitoring-weekly` (prose-grep, never executes runtime), `portfolio-overview` (sentinel test passes only via a stale constant), `weekly-summary` (zero DURUR/error-path assertions).

### Theme 6 — `event_type` enum 10→12 stale cross-refs  ·  **LOW · cosmetic but widespread**
~10 skills describe `event_type` as a "10-enum" / "closed 10-value enum"; the schema holds **12**. No runtime impact (skills emit valid values) — pure doc staleness. A single sweep fixes the whole cluster: `faq-optimization`, `generate-images`, `new-blog`, `revise-content`, `indexing-ping`, `verify-indexing`, `portfolio-kpi-trend`, `mark-done`, …

### Theme 7 — Stale test-docstrings claiming `status=wip`  ·  **LOW**
~7 test files carry docstrings saying `status=wip` while the frontmatter is `active` (legacy of the v1.3 wip→active mass promote). Assertions are loose membership so tests pass; only the prose is stale. **Out of scope of the `test_status_declaration_parity` guard** (which checks SKILL.md FM↔body, not test files) — hence legitimately new. `cannibalization`, `content-decay`, `content-gaps`, `internal-links`, `master-task-sync`, `topical-map`, `weekly-summary`.

> Note on the consent surface: `indexing-ping` (medium) mislabels `mcp__gsc__submit_sitemap` as the "Google Indexing API per-URL `URL_UPDATED`" path. `submit_sitemap` submits *sitemaps*, not per-URL indexing requests. This is a capability mislabel, not a consent breach — but it muddies the consent surface and should be corrected.

---

## HIGH-Severity Findings (24)

| # | Skill | Dim | Title | Location | Votes |
|---|---|---|---|---|---|
| H1 | content-decay | 5 | Step 4b calls `check_budget.preflight()` + raises `BudgetGateError` — neither symbol exists | `skills/discovery/content-decay/SKILL.md:211-226` | 3/3 |
| H2 | gsc-pull | 6 | Step 8 documents a template-variable set that cannot render the actual report template | `skills/ingestion/gsc-pull/SKILL.md:222-225` | 3/3 |
| H3 | sf-crawl-orchestrator | 5 | Step 8 calls `render_template.render()` — function does not exist (`AttributeError`) | `skills/ingestion/sf-crawl-orchestrator/SKILL.md:540-554` | 3/3 |
| H4 | sf-import | 5 | Required `mcp__gsc__list_sitemaps` + DURUR #4 sitemap-xcheck never implemented | `scripts/ingestion/sf_import.py:237-264` | 3/3 |
| H5 | sf-import | 5 | `workflow_runner` run-shell (Steps 1/2/3/8, DURUR #1/#2/#5) declared but never used | `scripts/ingestion/sf_import.py:267-328` | 3/3 |
| H6 | brand-onboarding | 1 | STAGING-ONLY self-contradiction: Step 6 + DURUR #5 say `project.config.json` is never written, but Stage C writes exactly that | `skills/meta/brand-onboarding/SKILL.md:176-180,266-272,315` | 3/3 |
| H7 | brand-onboarding | 6 | Stage-C bank-write produces entries the consumed schema rejects (`additionalProperties:false`); `evidence_url`/R-44 fields are not schema fields | `scripts/meta/brand_onboarding_write.py:106-149` | 3/3 |
| H8 | init-project | 5 | Cascade promises a live "auto-runner" + `cascade: brand-onboarding` event mechanism that does not exist | `skills/meta/init-project/SKILL.md:303-305` | 3/3 |
| H9 | init-project | 3 | "Init not complete until Stage C writes" contradicts Step 10 + paired test (treats `status==done` as terminal, no cascade gate) | `skills/meta/init-project/SKILL.md:311-312` | 2/3 |
| H10 | mark-done | 5 | Claims `transaction.py` hard-guards `protected_columns` via `WriterScopeError` — empirically false; only `allowed_writers` is checked | `skills/meta/mark-done/SKILL.md:263-269` | 3/3 |
| H11 | master-task-sync | 7 | Step 8 prescribes `source.kind=local_aggregation`, not a valid events.schema enum → fails validation | `skills/planning/master-task-sync/SKILL.md:320-329` | 3/3 |
| H12 | new-content-plan | 6 | Body claims 11-col output but impl + schema + test lock **14** cols (Phase-10 image_prompt/alt_text/content_type drift) | `skills/planning/new-content-plan/SKILL.md:308-310` | 3/3 |
| H13 | generate-images | 6 | Success-path `event_type` documented `content_new` but skill emits (and must emit) `manual` | `skills/production/generate-images/SKILL.md:113,428,532` | 3/3 |
| H14 | new-blog | 6 | R-121 "post-publish mutation" specifies `master.xlsx[completed_work]` write — contradicts READ-ONLY + F-1 (`allowed_writers=null`) | `skills/production/new-blog/SKILL.md:227-232` | 2/3 |
| H15 | revise-content | 6 | `event_kind=production` is invalid vs the F-8 events schema it cites (`content_revise` must be `event_kind=work`) | `skills/production/revise-content/SKILL.md:407` | 3/3 |
| H16 | monitoring-weekly | 5 | Headline capabilities (drift-via-events, 5σ GSC anomaly, budget burn) documented active but inline-stubbed "Phase 14+" | `skills/reporting/monitoring-weekly/SKILL.md:352-364` | 3/3 |
| H17 | monitoring-weekly | 6 | `consumes[]` declares `drift-check:events.jsonl` + `master.xlsx[gsc_performance]` but impl reads `consistency-report.json` + `portfolio.json` (neither declared) | `skills/reporting/monitoring-weekly/SKILL.md:40-44` | 3/3 |
| H18 | monthly-report | 4 | "Q-RP-01 RESOLVED" audit-emit block mutates **append-only** `events.jsonl`, contradicting READ-ONLY + `safe_auto_execute` | `skills/reporting/monthly-report/SKILL.md:174-210` | 3/3 |
| H19 | portfolio-heatmap | 6 | `primary_source` declared 10-enum but schema has 11; `new_content_plan` silently dropped, breaking the "nothing silently missing" promise | `scripts/reporting/portfolio_heatmap.py:33-36` | 3/3 |
| H20 | portfolio-heatmap | 7 | `active_projects` ceiling claimed "schema maxItems = 8" but schema is **12** | `skills/reporting/portfolio-heatmap/SKILL.md:135-136` | 3/3 |
| H21 | portfolio-kpi-trend | 6 | `active_projects` ceiling hardcoded 8 — schema raised to 12; skill DURUR-halts on the live 10-project portfolio | `scripts/reporting/portfolio_kpi_trend.py:41` | 3/3 |
| H22 | portfolio-kpi-trend | 7 | SKILL.md cites `active_projects.maxItems = 8` four times — authority is **12** | `skills/reporting/portfolio-kpi-trend/SKILL.md:150` | 3/3 |
| H23 | portfolio-monthly-roundup | 7 | Hard-codes `active_projects` ceiling 8 — schema raised maxItems to 12 (stale ref + over-strict DURUR) | `skills/reporting/portfolio-monthly-roundup/SKILL.md:11,254-255` | 3/3 |
| H24 | portfolio-overview | 7 | Hard-pins `active_projects` ceiling 8 — schema-valid 9–12 portfolios are wrongly hard-stopped (P0-04) | `skills/reporting/portfolio-overview/SKILL.md:9,15-16,69,165-166,214` | 3/3 |

*Full `description`, verbatim `evidence`, and `suggested_fix` for every finding are in the companion `.findings.json`.*

---

## MEDIUM-Severity Findings (25)

| Skill | Dim | Title | Location |
|---|---|---|---|
| gbp-audit | 6 | Step 6 documents a CLI invocation the impl does not provide | `SKILL.md:233-237` |
| gbp-audit | 6 | Step 2 calls a public `preflight_budget()` signature that does not exist | `SKILL.md:145-150` |
| on-page-audit | 6 | Step 8 template-variable contract incomplete; render hard-fails if followed literally | `SKILL.md:275-278` |
| schema-audit | 6 | Declared input `default_status` is inert — never consumed by transform/CLI/body | `SKILL.md:31-35` |
| drift-check | 6 | `events.snapshot.json` workspace write (F-12) undisclosed in SKILL.md outputs | `scripts/validation/validate_invariants.py:664-704` |
| glossary-audit | 3 | Paired test rubber-stamps detection: asserts whitelist is *mentioned*, never runs it | `test_glossary_audit.py:214-237` |
| glossary-audit | 5 | Missing-term detection over-promises: whitelist leaves ~1,393 false positives | `SKILL.md:235-238` |
| dfs-pull | 6 | `cluster` input declares a `cluster_keywords` write the skill explicitly disclaims | `SKILL.md:40-44` |
| dfs-pull | 6 | Step 8 calls `write_staging`/`staging_filename` with signatures that don't exist | `SKILL.md:273-282` |
| scrapling-ops | 6 | Step 8 render-variable list does not match the actual template | `SKILL.md:256-259` |
| sf-crawl-orchestrator | 3 | Paired test simulates a fictional Step-5 export the body says never happens | `test_sf_crawl_orchestrator.py:284-292` |
| sf-import | 6 | Cites `scripts.ingestion.sf_validate`/`sf_sitemap_xcheck` — neither module exists | `SKILL.md:156` |
| sf-import | 6 | Body + test use `transaction.append`; impl uses `transaction.replace` | `sf_import.py:241-248` |
| brand-onboarding | 3 | Stage-C write test asserts field presence but never validates against the project-config schema | `test_brand_onboarding_write.py:40-53` |
| mark-done | 6 | Claims `event_type` is a "closed 10-value enum" + lists 10 — canonical enum is 12 | `SKILL.md:108-113` |
| generate-images | 7 | Cross-ref misattribution: `F-9` cited for `event_kind=work` / ADR-020 authority | `SKILL.md:112-113,422,427` |
| generate-images | 7 | Cross-ref misattribution: `F-13` cited for `image_style` 5-enum profile switch | `SKILL.md:186,194,242,262,436,490,530,549` |
| indexing-ping | 6 | Frontmatter + body name `mcp__gsc__submit_sitemap` as the Google Indexing API `URL_UPDATED` path (it submits sitemaps, not URLs) | `SKILL.md:50-52,75-79,253-259` |
| monitoring-weekly | 3 | Paired test is a prose-grep rubber stamp; never executes the inline runtime | `test_monitoring_weekly.py:206-294` |
| monitoring-weekly | 7 | Principle-2 profile enum cites two values (`local-business`, `personal-brand`) that don't exist | `SKILL.md:446-462` |
| portfolio-overview | 3 | maxItems sentinel test has a false docstring; passes only via the stale code constant | `test_portfolio_overview.py:192-204` |
| portfolio-task-heatmap | 7 | `active_projects` ceiling 8 vs schema 12 (config with 9-12 validates but transform raises) | `SKILL.md:154,218-219` |
| portfolio-weekly-brief | 6 | Template emits literal `$run_id` into every published brief — transform never provides it | `portfolio-weekly-brief.template.md:39` |
| weekly-summary | 3 | Paired test exercises **zero** DURUR conditions; doesn't verify the idempotency/byte-stability guarantee | `test_weekly_summary.py` |
| weekly-summary | 5 | DURUR #2 `WorkspaceRootUnsetError` declared + documented but **never raised** (unreachable stop) | `weekly_summary.py:67-68` |

---

## LOW-Severity Findings (49)

Mostly cosmetic doc-drift. **Two cheap sweeps clear ~32 of them:**
- **`event_type` "10-enum" → "12"** across ~10 skills (`faq-optimization`, `generate-images`, `new-blog`, `revise-content`, `indexing-ping` ×2, `verify-indexing` ×2, `portfolio-kpi-trend`, `mark-done`, `content-decay`, `whats-next`, `new-blog` …).
- **Stale test-docstring `status=wip` → `active`** across 8 test files (`cannibalization`, `content-decay`, `content-gaps`, `internal-links`, `master-task-sync`, `topical-map`, `on-page-audit`, `weekly-summary`).

Remaining low items (stale line-numbers, `F-8`/`F-09` ID-format drift, `v1.2`→`v1.5` schema-version refs, dangling paths like `docs/ARCHITECTURE.md §24.4`, `$run_id` template leaks on heatmap/roundup, `load-context` unread `CONTEXT_LEDGER.md` consume, `init-project --schema-version=1.5` ghost flag, etc.) are enumerated in full in `.findings.json` (`severity:"low"`).

---

## What Was Eliminated (18 False-Positives)

The adversarial panel rejected these — they are documented here so the elimination rationale is auditable. Most are **"factually accurate but not a contract / intentional design / already-guarded."**

| Skill | Dim | Why rejected |
|---|---|---|
| init-project | 7 | "DURUR #9" finding misread a fixed 6-item DURUR list; the cited stop does exist conceptually elsewhere |
| aio-competitor-map | 7 | R-109/R-110 are **intentionally** redefined in-skill as schema.org/entity-detection signals; not a misattribution |
| aio-competitor-map | 3 | Token-presence test is acceptable for this detection skill; not a rubber-stamp on a side effect |
| sf-import | 3 | Real contract is covered by `test_sf_import_wiring.py`; the per-skill test isn't the whole picture |
| mark-done | 3 | Behavioral writes are covered by `test_transaction.py`; not hollow once siblings are counted |
| faq-optimization | 7 | F-code mapping is intentional, documented, and test-locked design |
| generate-images | 7 | `F-14` citation is correct in context (×2 such rejections) |
| geo-analysis | 3 | status-docstring is stale but assertion is correct; below the actionable bar here |
| on-page-audit | 7 | DataForSEO endpoint-mapping cross-ref is correctly attributed |
| on-page-audit | 3 | status-docstring stale but inert; guard holds |
| gbp-audit | 5 | `run()` orchestration side-effects are intentionally caller-layer, documented |
| competitive-analysis | 3 | stale status-docstring, assertion unaffected — below bar |
| load-context | 6 | "7 reads vs 5-file budget" is an accurate but inert prose count, not a contract |
| drift-check | 3 | docstring "Eleven cases" stale (30 actual) but the suite is real and passing — informational |
| cluster-map | 3 | stale status-docstring; assertion correct |
| faq-optimization | 6 | payload sketch omits snapshots but the schema-required fields are produced at runtime |
| content-remediation | 7 | "10-enum" prose stale but judged informational, not actionable (panel drew the line here) |
| generate-images | 7 | `F-1` citation correct for `new_content_plan` READ-ONLY authority |

> The `content-remediation` / `generate-images` "10-enum" rejections sit right next to confirmed "10-enum" findings elsewhere — the same staleness was judged *actionable* in some skills and *informational* in others. That inconsistency is itself a signal: see the Completeness Critique.

---

## Completeness Critique — What This Audit May Have Missed

1. **Cross-skill cascade / producer-consumer contracts.** Each finder audited one skill in isolation. The *handshakes between* skills — `init-project → brand-onboarding`, `new-blog → indexing-ping`, every `consumes`/`produces` pair — were only incidentally checked. A dedicated pass over the cascade graph would catch mismatches a per-skill view structurally cannot.
2. **Shared-script contracts vs. all callers.** `transaction.py`, `events_writer.py`, `workflow_runner.py`, `render_template.py`, `check_budget.py` are touched by many skills. The audit found symptoms (mark-done, sf-import, content-decay) but never systematically audited each shared module against the union of its callers.
3. **Stub skills are under-exercisable.** Where the runtime is deferred (`monitoring-weekly`, parts of `init-project`/`brand-onboarding`), some io-drift/capability claims cannot be fully validated until Phase 11/14. Those findings are "documented-vs-stub", not "documented-vs-runtime".
4. **The low-severity cross-ref line is LLM-judgment-dependent.** The enum-staleness inconsistency above shows it. A **deterministic guard test** — grep every SKILL.md for "N-value enum" / "maxItems = N" and assert against the live schema — would convert this whole class from subjective findings into a CI check (and would have caught Themes 1 & 6 mechanically).
5. **No live execution.** Static read only; no skill was run. Capability findings are grep-solid; emitted-payload findings are inferred.
6. **No independent completeness-critic agent ran.** The session limit killed the synthesizer; this critique is the lead's after-the-fact pass, not a fresh adversarial agent.

---

## Recommended Remediation Order (for discussion — nothing changed yet)

1. **Theme 1 (active_projects 8→12)** — *first.* It's an active runtime halt on the live portfolio. One lockstep change across 5 skills + transforms + fixtures; prefer reading `maxItems` from the schema.
2. **Theme 3 / H18 (monthly-report append-only breach)** — safety/hard-rule; remove the contradicting emit block (the deferral is already encoded everywhere else).
3. **Theme 2 (capability stubs)** — per skill, decide *implement* vs *honestly mark as Phase-14 stub-mod* (reuse brand-onboarding's framing).
4. **Theme 3 remainder + Theme 4** — events.jsonl enum/kind fixes and template `$run_id`/Step-8 variable reconciliation (prevents render crashes and garbage in published reports).
5. **Theme 5 (rubber-stamp tests)** — upgrade the 6 hollow tests to exercise real DURUR/side-effects (this is also TDD debt).
6. **Themes 6 & 7 + low cross-refs** — two mechanical sweeps; consider the deterministic guard test from Critique #4 so they can't silently return.

Per the workflow-audit protocol, **fixes are a separate, approval-gated effort** (TDD + Dev-QA loop), one theme at a time.
