# Release Notes — v2.1.0 (2026-06-10)

**Engine HEAD:** v2.1.0 release commit (5-file sync via `version_bump --apply`)
**Suite:** 3221 passed / 7 skipped / 0 failed (was 2716 at v2.0.0 → **+505 tests**)
**Theme:** *Unified remediation + capability gaps* — one day, one plan, 20 worker batches (Opus 4.8 1M workers, Fable 5 manager session), every batch independently re-derived, committed in isolation, and shipped through a clean-worktree push gate. Origin stayed green the entire time.

## Why this release exists

A hostile full-repo audit (8 parallel agents, 2026-06-10) found that while the engine's *technical* layers had been repeatedly audited, the **SEO methodology layer never had been** — and it carried real rule↔code drift plus 2026-currency gaps. This release fixes every confirmed finding and builds the 11 highest-value capability gaps from web-verified specs.

## SEO correctness (the audit's red findings)

- **Content decay now implements its own rule (R-85):** two-branch combined signal (clicks Δ AND position Δ) OR (impressions Δ AND negative trend), profile-aware (YMYL −20%/+3), plus a `--yoy` window mode for seasonal portfolios. The old clicks-only −20% heuristic is gone.
- **Cannibalization detector rewritten:** a conflict now requires a non-brand query AND click-share dilution (<70% single-URL) AND a real competition signal (top-URL flip-flop / tight cluster). Default recommendation is *differentiate intent*; a 301-consolidate is never auto-emitted.
- **Responsiveness finally measured:** tech-audit gains a TBT rule (>600 ms HIGH / 200–600 MEDIUM) as an honest lab proxy, with the CrUX/INP field-data gap stated, not papered over.
- **Rule pack corrections (FIX-H):** duplicate R-78 resolved (IPTC rule → **R-123** with full cross-subsystem reference completion), one canonical title/description standard (R-35: ≤580 px / ≤990 px), stats-density single source (R-104), Google-Extended rationale corrected (it governs Gemini training, not Search/AIO ranking), FAQ contract → demand-driven 3–6 (hard cap 10) swept across every skill/template, mechanical cadences converted to ranges, uncited "3×/8×" multipliers relabeled as heuristics.
- **New R-124 — YMYL expert-review sign-off:** a named byline on YMYL content now requires a recorded human review (reviewer + date + content version → append-only audit event) before publish, enforced in new-blog + revise-content.
- **Indexing API eligibility hard-gate:** per-URL `URL_UPDATED` is contractually restricted to JobPosting/BroadcastEvent pages (Google's documented allowed use); operator consent is necessary but no longer sufficient. Sitemap submit + IndexNow remain the generic channels.
- **Report honesty:** monthly report's exec narrative always states the signed net clicks delta in both framings; a new "Düşenler" (decliners) section is byte-identical across framings; the `position_before = position_after + 3` fabrication is retired (now `null`/"?").
- **Locale de-hardcoding:** engine-level `location_code=2792` defaults removed; DFS locale resolves config-first from each project's schema-required `dataforseo` block (live-verified codes: TR 2792, CA 20120, NG 2566).

## New capabilities (gap builds, web-verified specs)

- **Measurement discipline (R-137–R-141):** Google core-update calendar (live-seeded from the Search Status Dashboard) + `measurement_context` report section with update-overlap annotation; quick-win **intervention-vs-control cohorts** (treated-minus-control in pp; |diff| < 10 pp ⇒ indistinguishable; "n<30 — directional only"); weekly anomaly detection rebuilt on **median + MAD modified z-score** (the statistically meaningless 5σ/8-week placeholder is gone).
- **AI Overview tracking:** quick-wins can record real AIO presence per query (opt-in, two-pass DFS); aio-competitor-map's false premise corrected — citation evidence now comes from the actual `ai_overview.references[]` payload, never schema-markup inference.
- **CTR-uplift scoring v2:** `expected_uplift_clicks = impressions × ctr(target) × aio_factor − clicks` from a versioned, sourced `ctr-curve.json` (First Page Sage positions + Ahrefs AIO discounts); legacy score retained as tiebreaker.
- **4 new skills (wip, contract-locked):** `facet-nav-audit` (parameter taxonomy + index-bloat governance, R-128–130), `robots-policy-audit` (robots lint + noindex/disallow mutual-exclusion + R-58 lifecycle drift, R-131–133), `hreflang-audit` (reciprocity graph + return-target indexability, R-125–127), `migration-map` (1:1 redirect map build + post-launch verify, R-134–136). Shared `sheet_merge` util survives sf-import snapshot semantics.
- **Merchant structured data (R-147/R-148):** schema-audit gains M1–M7 merchant listing checks (price/currency/availability/Offer-shape/shipping/returns/staleness) with org-level-first guidance for limited-template TR platforms.
- **Local SEO (R-144–R-146):** canonical NAP single source (`local/nap.json`, multi-location), Turkish-aware NAP consistency engine wired into gbp-audit (closing its declared-but-unimplemented branch), white-hat review policy + anti-doorway location-page rules and operator templates.

## Hardening & infrastructure

- **Schema lock made real:** 63 nested object nodes across 13 schemas now declare `additionalProperties: false` (the audit's live repro — `portfolio-config::cadence.weekly_brief` accepting unknown fields — now rejects). 8,762 instance objects validated before closure; a 9-node audited allowlist covers polymorphic descriptors. Master template ↔ schema lock test added; `gbp_audit` sheet added to the template.
- **Security residuals:** base64 secret heuristic (padding-anchored, 0 false positives repo-wide) across all 3 inventory surfaces (scanner / CI / event redactor, 16→17 classes); `scan_pending_secret` emits the standard block-decision JSON; interpreter-net loopback carve-out completes the D-C gate ruling; `$ARGUMENTS` text-substitution arg-parsing fixed for quoted targets (`/pseo-approve` live-repro).
- **Test hermeticity:** machine-path hardcodes removed (env-derived live fixtures; suite is 0-failed with `PSEO_WORKSPACE_ROOT` unset), SF MCP smoke is opt-in (`PSEO_SF_SMOKE=1`, zero network at collection), dead staging skips repointed, count pins consolidated into `tests/_count_pins.py` with a pin==filesystem keystone, root `pytest.ini` (`testpaths=tests`).
- **CI supply chain:** GitHub Actions pinned by full commit SHA (v5.0.1 / v6.2.0, cross-verified), `--tb=short`, CODEOWNERS, weekly Dependabot (pip + actions).

## Counts at release

49 skills · 29 commands · 32 schemas (31 `*.schema.json` + invariants) · 24 rule files · rule-id ceiling **R-148** (R-142/R-143 reserved for the deferred backlinks module) · 6 hooks · 4 MCP servers.

## Deliberately deferred

- **GAP-A-B3 backlinks monitoring** — operator ruling 2026-06-10: postponed (DFS Backlinks API requires a separate $100/month commitment). Spec is shelf-ready; R-142/R-143 reserved.
- **Log-file analysis** — SPEC-ONLY deferral with re-open triggers (`docs/superpowers/specs/2026-06-10-log-file-analysis-feasibility.md`): GSC Crawl Stats has no API; hosted TR platforms expose no raw logs.
- Coverage gate in CI (needs a measured baseline), portfolio test-fixture dedup, per-project fitted CTR curves, YoY seasonality (needs ≥53 ledger weeks).

## Honesty note

The status line now reads "production-ready **core**": the production/publishing suites and the four new tech-SEO skills are `wip` — contracts and tests locked, runtime deliberately deferred (the same demote-to-honest principle ratified in the 2026-06-09 audit cycle).
