# UNIFIED Remediation + Gaps — Worker Dispatch Plan (2026-06-10)

> **Manager:** Claude (Fable 5, 1M) — this session verifies, commits, pushes. **Workers:** fresh Opus 4.8 (1M) sessions, one batch each, NO commits.
> **Sources merged into this plan:**
> 1. Codex hostile-audit remediation — `2026-06-09-codex-hostile-audit-remediation-WORKER-PROMPT.md` (batches A–G, 20 findings, 18 real)
> 2. Manager full-repo audit 2026-06-10 — ~53 verified findings across skills/hooks/python/schemas/tests/SEO-methodology/docs/CI (evidence inline below)
> 3. Gap build-specs (researched + web-verified 2026-06-10):
>    `2026-06-10-gap-specs-technical-seo.md` (GAP-T1..T4) · `2026-06-10-gap-specs-measurement-ai.md` (GAP-M1..M4) · `2026-06-10-gap-specs-acquisition-local-commerce.md` (GAP-A1..A4)
> **Baseline at plan creation:** `2716 passed / 7 skipped / 0 failed` (after env_probe stub + stale plugin-cache cleanup, 2026-06-10). The suite GROWS every wave — each worker records its OWN start-N at dispatch and must end ≥ start-N with 0 new failures.

---

## §0 — HARD RULES (every batch, non-negotiable — supersedes the codex doc §0 baseline number)

1. **NO `Task`/`Agent` tools — work INLINE.** Subagents fail here ("Prompt too long").
2. **Baseline-first:** run the full suite at session start, record exact N. End **≥ N, 0 new failures** (exceptions only where your batch section explicitly lists a tolerated cross-batch redness — none currently).
3. **TDD:** RED → GREEN → REFACTOR. Regression test FIRST, watch it fail for the right reason.
4. **Scope-locked** to your batch's named files. Anything else → STOP + report. `git status` may show sibling-batch files mid-wave — IGNORE them, report only YOUR files.
5. **No commit, no push** — the manager commits after independent re-derivation.
6. **Secrets in tests:** construct dynamically (`"sk-" + "A"*24`); never paste a real secret.
7. **Don't weaken gates** to make a test pass. Preserve style, contracts, schemas, CLI UX.
8. **Re-derive evidence yourself** — quote real `file:line` in your report; manager line refs may have drifted.
9. ⚠️ `scripts/hooks/outward_action_gate.py` classifies any Bash command **containing** `rm`/`unlink`/`rmtree`/`mkdir` tokens as `fs_delete` — even inside grep patterns. Grep via Python/subprocess or avoid the literals.
10. **`.mcp.json` is byte-locked** (F-16/ADR-040, 565B, md5 `634c8ed5b7cf3c852d9b41e1c0e1d3b5`) — never touch it.
11. **Additive-only schema changes**; sheet additions to master-excel are FORBIDDEN in this plan (none is needed).
12. **Rule numbering is history-stable (ADR-038):** never delete/renumber an existing rule id; deprecate with status note. New ids ONLY per §R-MAP.
13. **Templates may not contain bare `R-NNN` tokens** unless that rule lives in `rules/content-*.md` (`tests/rules/test_r_xx_resolution.py`). Write "per <rulefile> §<topic>" in template prose instead.
14. **Verify with your OWN scoped tests** during the wave (`pytest tests/<area>`); the manager runs the combined full suite per wave.
15. Engine stays **project-agnostic** — no client names in logic (audit docs exempt).

## §R-MAP — Global rule-number allocation (collision resolution; spec files were drafted independently)

| Range | Owner batch | File | Notes |
|---|---|---|---|
| R-123 | FIX-H | `rules/content-html-discipline.md` | renumbered duplicate R-78 (AI-Image IPTC) |
| R-124 | FIX-H | `rules/content-eeat-discipline.md` | NEW: YMYL expert-review sign-off |
| R-125–R-136 | GAP-T1 + GAP-T2 | `rules/tech-seo-governance.md` | exactly as written in the technical-seo spec ✅ |
| R-137–R-141 | GAP-M-1a | `rules/measurement-discipline.md` | spec remap: R-125→**R-137** (core-update overlap), R-126→**R-138** (cohort tagging), R-127→**R-139** (versioned constants), R-128→**R-140** (AIO presence), R-129→**R-141** (MAD anomaly) |
| R-142–R-143 | GAP-A-B3 | `rules/backlink-discipline.md` | spec remap: R-125→**R-142**, R-126→**R-143** |
| R-144–R-146 | GAP-A-B2 | `rules/local-seo-discipline.md` | spec remap: R-127→**R-144**, R-128→**R-145**, R-129→**R-146** |
| R-147–R-148 | GAP-A-B1 | `rules/merchant-structured-data.md` | spec remap: R-130→**R-147**, R-131→**R-148** |

Workers on gap batches: apply the REMAPPED ids everywhere (rule headings, SKILL.md citations, test grep-sentinels). The spec files carry a header note repeating this.

## §D — Manager rulings on the codex §1 operator decisions (veto window open; default = these)

- **D-A (#7) workspace-root precedence → (c) fail-loud on conflict.** If `PSEO_WORKSPACE_ROOT` and `~/.config/pseo/config.json` disagree, CLIs/hooks abort with a clear message unless `--workspace-override` is passed. Rationale: silent wrong-workspace writes are the cross-contamination hard-constraint's worst case.
- **D-B (#8,#9) emit-failure contract → (b) durable anomaly record + reconciliation.** Emit stays non-blocking; on failure write a hash-chained record via the EXISTING `scripts/state/anomaly_recorder.py` ledger (`_state/anomalies.jsonl`) including enough context to reconcile (run_id, target, backup path); drift-check/report surfaces unreconciled anomalies. Rationale: rolling back an Excel save on a transient emit bug is worse than a tracked anomaly.
- **D-C (#11) interpreter net-writes → gate conservatively.** Classify `python/python3/node/ruby/perl` one-liners (`-c`/`-e` payloads) containing obvious net-write signatures (`urlopen(` with `data=`, `requests.post(`, `http.client` + `POST`, `fetch(` + `method` + `POST`) as `net_post`. Loopback carve-out from #12 applies equally. False-negative-tolerant by design (read-only one-liners must not be blocked).
- **D-D (#20) SF redirect policy → (b) restricted follow.** `follow_redirects` only within loopback + same port; anything else surfaces as an explicit error.
- **OPEN — Süleyman only:** GAP-A-B3 backlinks requires enabling the **DataForSEO Backlinks API product ($100/month minimum commitment)**. Batch is fully spec'd but **GATED** until he rules. Everything else proceeds.

## §W — WAVE PLAN (workers within a wave touch DISJOINT files; manager verifies + commits + pushes per wave)

| Wave | Parallel workers | Batches | Key sequencing reason |
|---|---|---|---|
| **W1** | ×2 | FIX-I · FIX-L | (CODEX-A/D/E cancelled — already shipped, see §CODEX.) I=discovery transforms; L=locale skills. Disjoint. |
| **W2** | ×3 | FIX-H · GAP-M-1a · FIX-S | H=rules/content-* + GLOSSARY + pseo-quickwin.md; M-1a=anomaly/calendar core; S=approve/bind arg-parsing residual + secret leftovers (commands/pseo-approve.md, pseo-bind.md, scan_pending_secret.py, check_secrets.sh, rules/secrets-management.md — disjoint from H's command file). |
| **W3** | ×2 | FIX-K · GAP-M-1b | K=production+monthly framing (after H sets canonical numbers); M-1b=quick-wins/AIO/ctr-curve. |
| **W4** | ×3 | GAP-T1 · GAP-A-B1 · GAP-A-B2 | T1 is the ONLY count-lock toucher this wave (45→47 skills, 25→27 commands) + adds the R-58 cross-link line (after H's edits to the same file in W2). Merchant/local add no skills. |
| **W5** | ×2 | GAP-T2 · GAP-M-W2 | T2 bumps counts 47→49/27→29 (alone on count-locks); M-W2 = monthly measurement_context + cohorts (after K and M-1b on the same files). |
| **W6** | ×4 | FIX-MFIN · FIX-R · FIX-N · FIX-J | MFIN=test infra + count-pin consolidation (counts now stable at 49/29); R=.github only; N=misc hygiene; J=schema tightening over the FINAL schema set. |
| **W7** | ×1 (conditional) | GAP-A-B3 (if Süleyman approves $100/mo) | B3 bumps 49→50/29→30 + last monthly_report toucher. (CODEX-B2 cancelled — shipped in `bdf064f`.) |
| **W8** | manager only | Closeout: version bump → v2.1.0 (5-file Y-05 sync), RELEASE_NOTES_v2.1.0.md, annotated tag, final full suite, push. Plus the F2 decision with the operator: README "production-ready" wording vs 9 wip skills (demote-to-honest precedent from audit#2). | |

> Worker hygiene addenda (all waves): (1) `export PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace` BEFORE running pytest — without it the collected-test count drops (~2703 vs ~2723) and live-fixture tests skip, making baselines incomparable. (2) If your baseline shows exactly one failure in `tests/hooks/test_hook_scripts_runtime_vs_ci.py::test_every_hook_script_is_classified` caused by an UNTRACKED `scripts/hooks/env_probe.py`, delete that stub file (it is a dead recovery artifact from a pre-2026-06-10-restart session) and note it in your report.

Dispatch prompt to paste into each worker session (fill the batch id):

```
You are the <BATCH-ID> worker — fresh Opus 4.8 (1M context) session. Repo: /Users/apple/Documents/platinum-seo-engine (workspace context: PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace).
Read docs/superpowers/plans/amo/2026-06-10-UNIFIED-remediation-WORKER-DISPATCH.md — follow §0 hard rules exactly, then execute YOUR section §<BATCH-ID> (including any codex/spec doc sections it references). TDD, scope-locked, NO commit/push. When done, report back using §REPORT.
```

---

## §CODEX — ⛔ CANCELLED 2026-06-10: ALL codex batches were ALREADY SHIPPED on 2026-06-09 (manager-verified at W1)

**Do NOT dispatch or execute any CODEX-* batch.** Verified at Wave-1 integration (the CODEX-A worker discovered it; manager re-derived the full set):

| Batch | Shipped commit | Findings |
|---|---|---|
| A | `7d33400` | #4,#5,#18 (+`__all__` ext already in `ae5f6ad`) |
| D | `cf06e10` | #10,#12 |
| E | `55c180d` | #13,#14,#15 |
| C | `9893e2a` | #1,#2,#3 |
| B | `8f1b713` + tail `1d01c03` | #6,#19 |
| F | `7b5712f` | #16,#17 |
| G | `c6d0dd5` | #8,#9 (durable anomaly record — matches ruling D-B(b)) |
| B2 (#7,#11,#20) | `bdf064f` (audit#2 SKILLS batch) | ws-conflict fail-loud + interpreter-net gate + SF redirect-off |

The 12-finding audit#2 (F1–F12) also shipped: `b7fe35c` (DOCS) + `648ed73` (COMMANDS) + `bdf064f` (SKILLS). The manager's 2026-06-10 full-repo audit ran on the POST-fix tree, so every FIX-*/GAP-* batch in this plan remains valid and non-duplicative.

**Residual items extracted from the codex extensions → re-homed into §FIX-S (Wave 2):**
1. `/pseo-approve` quoted-arg parsing is **STILL broken with the batch-E fix in place** — live repro 2026-06-10: `/pseo-approve sess-df6de1a6 git_push "origin main"` → `error: unknown action 'origin main'` (cache==repo verified byte-identical; the `$ARGUMENTS` textual substitution inside a double-quoted shell context breaks when the argument itself contains quotes).
2. base64 secret-pattern heuristic (ex CODEX-C ext).
3. `scan_pending_secret.py` JSON `{"decision":"block"}` stdout output (ex CODEX-F ext).

---

## §FIX-H — SEO rule-pack corrections (rules/ + GLOSSARY) — Wave 2

**Why:** the rule pack contradicts itself and, in places, Google's documented behavior. Full-repo audit evidence inline.
**Scope (ONLY these):** `rules/content-seo-discipline.md`, `rules/content-eeat-discipline.md`, `rules/content-html-discipline.md`, `rules/content-llm-discipline.md`, `rules/content-update-discipline.md`, `rules/content-quality.md`, `docs/GLOSSARY.md`, `commands/pseo-quickwin.md`, + the tests that pin the texts you change (update expectations TDD-first). Do NOT touch the R-58 section beyond reading it (GAP-T1 adds its cross-link later); do NOT renumber anything except H1 below.

1. **H1 — R-78 duplicate (ADR-038-safe renumber).** R-78 exists twice: Article Schema (`content-seo-discipline.md:215`) and AI-Image IPTC (`content-html-discipline.md:269`). Keep the seo-discipline R-78 (older); rename the IPTC rule heading to **R-123** with a `supersedes: R-78 (duplicate id, renumbered 2026-06-10)` frontmatter/body note; fix its mislabeled cross-links (it cites "R-73 (1200x675)" and "R-74 (manual upload)" — verify actual R-73/R-74 subjects and correct); update every repo-wide reference to the IPTC rule (grep `R-78` and disambiguate by context: skills/generate-images, tests, docs); fix `rules/content-quality.md:14` "Çakışma yok" claim and add a uniqueness test (`tests/rules/`): all `### R-NN` headings across rules/ are unique.
2. **H2 — NEW R-124 (YMYL expert-review sign-off)** in `content-eeat-discipline.md` next to R-28/R-82: a YMYL byline (R-28) is valid ONLY with a recorded human review — reviewer name, date, content version (hash or revision id) — captured as an `events.jsonl` audit row before publish; missing review record → RED. Rationale: a named author on machine-drafted YMYL text without documented review is a fabricated-authorship signal (rater-guideline "Lowest"). Enforcement contract lands in FIX-K (new-blog/revise-content steps); this batch writes the rule + failure mode only.
3. **H3 — R-06 + R-25 phantom sheet.** Both mandate link decisions from `master.xlsx[internal_links]` — that sheet does not exist (19-sheet schema). Repoint to the implemented reality: `topical_map` hub/spoke relations + `master_task` rows tagged `[internal-links/*]` (Option A per `skills/planning/internal-links/SKILL.md:141-189`). Adjust wording only; no behavior code here.
4. **H4 — one canonical title/description standard.** Today: R-35 (`content-html-discipline.md:83-91`) says ≤580px/≤990px; new-blog SKILL says ≤540px/≤680px-mobile; tech-audit transform uses 60/160 chars. Make **R-35 the single authority**: title ≤580px desktop, description ≤990px desktop, with an explicit note that char counts (60/160) are only a tech-audit *approximation heuristic* and that production skills must cite R-35. (FIX-K aligns new-blog SKILL.md numbers; tech-audit wording handled in FIX-I's SKILL touch-ups if needed — your change is rule-side only.)
5. **H5 — stats-density single source.** R-104 (`content-eeat-discipline.md:76-89`, min+max caps) is canonical; add a sentence that production skills must not restate divergent numbers (FIX-K fixes new-blog's "min 3/1000w, no caps" variant).
6. **H6 — R-99 Google-Extended correction** (`content-llm-discipline.md:39`): Google-Extended governs Gemini-app/Vertex training+grounding; it does NOT affect Search ranking or AI Overview inclusion (AIO follows Googlebot + snippet controls). Rewrite the rationale; remove the "AIO citation şansı düşer" claim.
7. **H7 — R-09 FAQ mandate → demand-driven.** Replace "10 FAQ standard (15 cap)" with: 3–6 FAQs where evidence exists (PAA presence, real user questions), hard cap 10; FAQPage schema stays (R-79) but fix its date (rich-result restriction was **August 2023**, not December) and delete the invented "domain trust signal" benefit.
8. **H8 — mechanical-cadence fingerprint.** R-13 (bold a keyword every ~250 words) → **deprecate** (status: deprecated + rationale: not a ranking signal; portfolio-wide mechanical pattern risk). R-06 link cadence, R-106 citation cadence, R-07 list/table-per-1000w, R-30 H2-keyword 40-60% → convert fixed cadences to **ranges with explicit per-post variation instruction** ("sample within range; do not produce identical structural cadence across posts"). Keep the underlying intents (internal linking, citations, scannability).
9. **H9 — uncited multipliers.** R-01 "3x citation", R-107 "snippet 8x traffic", R-113 "3-5x", R-109 "empirik" → relabel as **heuristic, uncited** ("sıralama/trafik çarpanı kanıtlanmamış sezgisel") or attach a real citation if you can find one in the existing docs (do NOT invent). The rule pack's own Principle 1 (uydurma yasak) is the authority.
10. **H10 — R-37/R-44 authority score scale.** "Otorite skoru ≥60/40/50/30" names no metric (Moz DA ≠ Ahrefs DR). Re-anchor: primary mechanism = curated per-project source allowlist; numeric gates optional and explicitly "Ahrefs DR" if used. Wording-only.
11. **H11 — quick-win band + filename.** `docs/GLOSSARY.md` says "pozisyon 8-20", `commands/pseo-quickwin.md:3` says "8-20"; the skill defaults are 11-20 and the uplift model targets page-2 → canonical = **11-20**. Fix GLOSSARY + command text; also align the command's output filename text to `{date}-quickwin.md` (template is `quickwin.template.md`).
12. **Tests:** every text you change is likely pinned somewhere (`tests/rules/`, `tests/skills/` grep-style contract tests, `tests/docs/`). TDD: update the pin to the new canonical text FIRST (RED), then edit the rule (GREEN). Add the H1 uniqueness test.

**DONE-when:** suite ≥ start-N/0; R-NN headings unique; no repo reference to the old IPTC "R-78" remains ambiguous. **DURUR-if:** a rule text you must change is load-bearing in >10 test files (report blast radius before editing), or you find a THIRD definition of any rule id.

---

## §FIX-I — Discovery transform correctness (scripts/discovery + 5 SKILL.md) — Wave 1

**Scope (ONLY):** `scripts/discovery/content_decay_transform.py`, `scripts/discovery/tech_audit_transform.py`, `scripts/discovery/on_page_audit_transform.py`, the cannibalization transform if one exists under `scripts/discovery/` (verify; else contract-only), `skills/discovery/{content-decay,cannibalization,tech-audit,on-page-audit}/SKILL.md`, `skills/planning/internal-links/SKILL.md` (one finding label), their tests. Do NOT touch `scripts/util/sf_issue_taxonomy.py` enum (ADR-028 locked) — see I4.

1. **I1 — decay implements R-85 as written + YoY mode.** Evidence: `content_decay_transform.py:77` `_DECAY_THRESHOLD = -20.0`, clicks-only, no position, no profile; R-85 (`rules/content-update-discipline.md:42-49`) requires (clicks < −30% AND position > +5) OR (impressions < −40% AND negative rank trend), profile-aware YMYL −20%/+3. Implement the combined signal; profile thresholds via `scripts/util/profile_aware_defaults.cascade_default`; add `--yoy` mode comparing the same window one year earlier when input data carries it (else emit `yoy_unavailable` note — never fake it); meta records which rule branch fired. SKILL.md decay-criteria text updated to cite R-85 as single source.
2. **I2 — cannibalization detector rewrite.** Evidence: `skills/discovery/cannibalization/SKILL.md:275-301` — ≥2 URLs ≥10 impressions = "conflict"; spread>5 → "consolidate to top URL". New contract — a query is a cannibalization CONFLICT only when ALL hold: (a) non-brand query (brand token list derived from project.config brand/domain; brand-dominated queries excluded), (b) click-share dilution (no single URL holds >70% of the query's clicks), (c) competition signal: URL flip-flop across periods (top URL changed between the two most recent windows) OR both URLs simultaneously in positions 1–20 with spread ≤5. Default recommendation becomes **"differentiate intent / adjust internal-link hierarchy"**; "consolidate (301)" may only be recommended when intent overlap is explicitly confirmed and is ALWAYS operator-reviewed. If detection lives in a transform script, implement there; if SKILL-body only, rewrite the contract + add a small pure helper module + tests. Note in SKILL: F-15 stays AMBER-by-design (non-empty sheet ⇒ AMBER is correct).
3. **I3 — responsiveness metric (TBT proxy; INP honesty).** Evidence: `tech_audit_transform.py:583-625` checks perf/LCP/FCP/CLS; `tbt_ms` parsed but unused; INP absent though `schemas/master-excel.schema.json:214` documents "INP supersedes FID". Add a TBT rule: `tbt_ms > 600` → HIGH "poor responsiveness (TBT — lab proxy for INP)"; `200 < tbt_ms ≤ 600` → MEDIUM. Finding text must state INP field data (CrUX) is not collected by this audit — no fake INP claims. SKILL findings table updated. (CrUX API integration is explicitly out of scope — record as a deferred note in the SKILL.)
4. **I4 — indexability routing verification (NO enum change).** ADR-028 locks the tech_seo 5-enum; `route_sf_issue()` already routes `canonical|hreflang|robots|indexab|directive` keywords to `robots_txt`. Add a TEST (`tests/scripts/`) locking that routing (canonical-mismatch style issues land in robots_txt, never silently dropped) — closes the "demo-hvac canonical bug has no category" audit finding without violating the ADR.
5. **I5 — on-page keyword match: Turkish + brand handling.** Evidence: `on_page_audit_transform.py:312-319` `target_query.lower() in haystack.lower()`. Replace with: locale-aware fold (for `tr*` locales map `İ→i, I→ı` before casefold; else plain casefold), token-based matching (all query tokens present, any order) instead of substring, and a brand-query exclusion (brand tokens from config → brand-dominated queries don't generate "rewrite meta" actions; emit `skipped_brand` count in meta).
6. **I6 — multiple-H1 severity.** In `_heading_findings`: multiple-H1 downgraded MEDIUM → LOW with wording "house-style/structure hygiene — not a Google ranking defect".
7. **I7 — internal-links finding label.** `skills/planning/internal-links/SKILL.md:578`: the "redirect chain" finding detects a single-hop redirected internal link — rename to "redirected internal link (single hop)" and note that real multi-hop chains come from SF `redirect_chains` (consumed by GAP-T4 later).
8. **Tests:** RED-first for each behavior change; keep existing fixtures passing where behavior intentionally unchanged; update SKILL-pinning tests.

**DONE-when:** suite ≥ start-N/0; decay/cannibalization fixtures demonstrate old-vs-new verdict differences explicitly in tests. **DURUR-if:** cannibalization logic turns out to live in a >500-line transform needing structural surgery (report a decomposition plan instead of doing it).

---

## §FIX-L — Locale de-hardcoding + planning clamps (4 SKILL.md) — Wave 1

**Scope (ONLY):** `skills/ingestion/dfs-pull/SKILL.md`, `skills/discovery/competitive-analysis/SKILL.md`, `skills/planning/topical-map/SKILL.md`, `skills/planning/new-content-plan/SKILL.md`, their tests.

1. **L1 —** `dfs-pull` defaults `location_code=2792`/`language_code="tr"` (SKILL.md:30-39). Remove engine-level country defaults: resolve **config-first** from `project.config.json` → `dataforseo.location_code` + `dataforseo.language_code` (both **schema-REQUIRED** per `project-config.schema.json:83` — every project already carries its authoritative code, so direct-read beats a market→code mapping table; a flat country table cannot express sub-country codes). ✅ **DONE in `7c487a3` — manager-verified live codes: TR=2792, CA=20120 (Ontario,Canada sub-country), NG=2566. The earlier draft's CA=2124/NG=2434 were WRONG — do not reuse them anywhere.** Config locale missing → DURUR (never silently default to any country). Keep a per-market reference table for operators + grep-gate.
2. **L2 —** `competitive-analysis` body hardcodes `location_code=2792, # TR` (~line 205) — same fix, read from config.
3. **L3 —** `topical-map` locale defaults — same fix.
4. **L4 —** `new-content-plan` TIVL word-count targets (T=1200/L=1000/V=800/I=1500, SKILL.md:405-410) can fall below profile floors (YMYL floor 1500 per Principle-2). Clamp: `target = max(TIVL_target, profile_floor)`; when R-08 SERP analysis data exists it overrides TIVL entirely. Update the worked examples.
5. Existing Method-C TR-verification discipline (`detect_response_locale`) stays mandatory for TR projects — do not remove any of it.
6. **Tests:** SKILL contract tests pin the new resolution order (config-first, no engine default) + the clamp.

**DONE-when:** grep for `2792` in skills/ returns only the mapping-table lines (with per-market context), never a bare default. **DURUR-if:** DFS location codes for CA/NG cannot be verified from repo fixtures or docs.

---

## §FIX-K — Production contracts + report honesty — Wave 3

**Scope (ONLY):** `scripts/reporting/monthly_report.py`, `templates/reports/monthly-report.template.md`, `schemas/monthly-report.schema.json` (additive-optional only), `skills/production/new-blog/SKILL.md`, `skills/production/revise-content/SKILL.md`, `templates/content/new-blog.template.html`, `skills/meta/mark-done/SKILL.md`, `skills/publishing/indexing-ping/SKILL.md`, their tests. (GAP-M-W2 will edit the monthly files AFTER you — keep your changes minimal and well-fenced.)

1. **K1 — framing changes tone, never facts.** Evidence: `monthly_report.py:38,455-462` — `framing_policy="positive_client"` default omits negative click deltas from the exec narrative; template has only "Yükselen" sections. Fix: (a) the exec narrative ALWAYS includes the net delta (positive or negative); (b) add a "Düşenler" (declining keywords/pages) section present in BOTH framings — `positive_client` may order it after wins and use constructive tone, but the rows and numbers are identical (add the invariance test: section content byte-identical across framings); (c) schema: add the optional `sections.decliners` property (additive; NOT in `required`).
2. **K2 — YMYL review sign-off enforcement (pairs with H2/R-124).** `new-blog` + `revise-content` SKILL.md: for YMYL profiles, add a mandatory pre-publish step — operator names the human reviewer; the skill emits an `events_writer.append_audit` row (action per existing audit-action enum — verify and reuse; target `content:{slug}:{post-slug}`, notes carrying reviewer + content hash/revision); missing reviewer → DURUR. Cite R-124.
3. **K3 — title/desc + stats-density alignment.** new-blog SKILL.md:94-96,397-399 (540px/680px) → cite R-35 canonical numbers (580/990 desktop, per FIX-H4); stats-density table at SKILL.md:173 → R-104's min+max caps verbatim (per FIX-H5).
4. **K4 — microdata strip (engine's own R-83 violation).** `templates/content/new-blog.template.html:18-37` carries `itemscope/itemtype/itemprop` while R-83 bans microdata and the skill emits JSON-LD. Remove all microdata attributes; keep semantic HTML; ensure the template still passes the content validator and template-dialect tests.
5. **K5 — mark-done autonomy contradiction.** `skills/meta/mark-done/SKILL.md:63-64` declares `safe_auto_execute: true` while line ~22 requires manual confirm on suspicious evidence. Set `safe_auto_execute: false` (keep `requires_approval` consistent); reconcile the body text.
6. **K6 — Indexing API eligibility gate (policy-critical).** `skills/publishing/indexing-ping/SKILL.md:79-84,262-272` frames per-URL `URL_UPDATED` as a future generic channel. Per Google's documented restriction (Indexing API = JobPosting/BroadcastEvent pages only; spam policies apply), add a HARD eligibility gate to the contract: before any future `URL_UPDATED`, a deterministic pre-check must confirm the target page carries JobPosting or BroadcastEvent JSON-LD; ineligible → refuse with explanation; sitemap-submit + IndexNow remain the generic channels. Keep the existing Süleyman-consent gate (it is necessary but not sufficient). Rewrite the misleading "post-Wave-2 legitimate channel" framing. Tests pin the gate text + the refusal path.
7. **Tests:** TDD all; the framing-invariance test is the keystone (GAP-M-W2 will extend it).

**DONE-when:** suite ≥ start-N/0; both framings produce identical decliners data. **DURUR-if:** monthly-report schema's `required` would need editing (it must not — additive only).

---

## §FIX-S — Command arg-parsing residual + secret leftovers — Wave 2

**Scope (ONLY):** `commands/pseo-approve.md`, `commands/pseo-bind.md` (+ any other command file using the `eval "set -- $(python3 -c 'import shlex...' "$ARGUMENTS")"` idiom — grep for it), optionally a NEW tiny helper `scripts/state/parse_command_args.py`, `scripts/hooks/scan_pending_secret.py`, `scripts/security/check_secrets.sh`, `rules/secrets-management.md`, their tests.

> ⚠️ **S1 SUPERSEDED — DONE by CODEX-E `8ae4d03`** (the original W1 CODEX-E worker, dispatched before this batch existed, root-caused it independently: `$ARGUMENTS` is TEXT-SUBSTITUTED, fix = forward it UNQUOTED to argparse; see [[project_slash_command_arg_textsub]]). **FIX-S worker: SKIP S1 entirely — do NOT touch `commands/pseo-approve.md`, `commands/pseo-bind.md`, or `tests/docs/test_command_quoted_arg_parsing.py` (already committed). Execute ONLY S2 + S3 below.** The manager will take only your `scan_pending_secret.py` / `check_secrets.sh` / `secrets-management.md` + their tests.

1. **S1 — quoted-arg parsing is still broken (batch-E residual; LIVE repro 2026-06-10).** [✅ DONE by CODEX-E — see banner above; left here for the record.] `/pseo-approve sess-df6de1a6 git_push "origin main"` failed with `error: unknown action 'origin main'` — on the FIXED code (`commands/pseo-approve.md:32,38`, cache verified byte-identical to repo). Root cause: Claude Code substitutes `$ARGUMENTS` TEXTUALLY into the command line; the current idiom embeds it inside a double-quoted shell word (`'...' "$ARGUMENTS"`), so an argument value that itself contains double quotes splits the shell word and corrupts positional mapping. shlex downstream cannot repair what the shell already mis-tokenized. Fix approach (worker chooses, must prove with the live repro as a test case): avoid embedding `$ARGUMENTS` inside quotes — e.g. write it to a temp file / heredoc with a quoted delimiter, or use a single-quoted wrapper with safe escaping, or parse `$1..$N` positionals directly where Claude Code provides them. The fix must survive: plain args, args with double quotes, args with single quotes, args with spaces, empty target. Apply the same idiom to EVERY command file using the pattern.
2. **S2 — base64 secret heuristic (ex CODEX-C extension).** Add a high-entropy base64 pattern to the canonical inventory in `scripts/security/check_secrets.sh` ONLY if implementable with low false positives (≥24-char base64 value assigned to a secret-ish key name: `key|token|secret|password|credential`); otherwise document the limitation explicitly in `rules/secrets-management.md`. Report which path you took and why.
3. **S3 — `scan_pending_secret.py` block-decision JSON (ex CODEX-F extension).** On a hit, additionally emit `{"decision":"block","reason":"<label>"}` to stdout (consistency with `ai_disclosure_rescan.py`/`denetci.py`); keep current stderr text + exit-code contract (tests assert both).

**DONE-when:** suite ≥ start-N/0; the exact live-repro invocation round-trips correctly (test simulates the textual `$ARGUMENTS` substitution, not just shlex in isolation). **DURUR-if:** Claude Code's substitution semantics make in-command parsing provably unfixable for embedded quotes — then document the constraint in both command files' argument-hint ("do not quote; use %20 or pass via file") + add defensive MISSING_ARGS errors, and report.

---

## §FIX-N — Hygiene pack — Wave 6

**Scope (ONLY):** `scripts/state/dump_workspace.py`, `.gitignore`, `.env.example`, `requirements-lock.txt` (header comment), root `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md` (move), `docs/RELEASE_NOTES_*` (gap stubs), NEW `docs/superpowers/specs/2026-06-10-log-file-analysis-feasibility.md`, their tests.

1. `dump_workspace.py:81` and `:104` — wrap `read_text` calls per the module's own "graceful" contract: catch `(OSError, UnicodeDecodeError)` (and keep `json.JSONDecodeError`) → return the documented None/[] shapes. Tests: unreadable/garbage-encoded file fixtures.
2. `.gitignore`: add `.claude/` (runtime cache visible to git today; conftest already excludes it from pytest).
3. `.env.example`: add the source-URL comment line for `HIGGSFIELD_API_KEY` (match the style of the other entries).
4. `requirements-lock.txt` header: drop the stale rpds-py example; keep the generic "regenerate on python3.10" guidance.
5. `git mv AUDIT_FINDINGS_FOR_CLAUDE_CODE.md docs/audits/2026-06-03_codex_cross_repo_audit_handoff.md`; grep + fix references.
6. Release-notes gaps: check `git tag` — if v1.2.0 / v1.9.1 / v1.9.2 tags exist, write minimal factual stubs from `git log <prev>..<tag>` (one page each); if a version was never tagged, write ONE consolidated `docs/RELEASE_NOTES_gap-note.md` explaining the numbering jump. Never invent content.
7. Write the GAP-A4 deferral spec exactly per `2026-06-10-gap-specs-acquisition-local-commerce.md` §GAP-A4(c).

**DONE-when:** suite ≥ start-N/0 (the moved audit file must not break any path-pinned test — grep first).

---

## §FIX-R — CI hardening (.github only) — Wave 6

**Scope (ONLY):** `.github/workflows/ci.yml`, NEW `.github/CODEOWNERS`, NEW `.github/dependabot.yml`, + `tests/ci/` updates.

1. Pin `actions/checkout` and `actions/setup-python` by **full commit SHA** (comment the human tag next to it). Resolve the SHA for the CURRENTLY USED major version from the action's repo tags — do not guess; if you cannot resolve a SHA offline, DURUR and report (manager will fetch).
2. `pytest --tb=no -q` → `--tb=short -q` (CI failures currently hide tracebacks).
3. `CODEOWNERS`: `* @popiliadam` plus explicit lines for `scripts/security/` and `.github/workflows/`.
4. `dependabot.yml`: weekly `pip` + weekly `github-actions`, with grouped minor/patch updates.
5. Update `tests/ci/test_ci_yaml.py` expectations (it pins ci.yml content — TDD-first). Do NOT touch the `.mcp.json` 4-server invariant step or the skill-count comment (other batches own counts).
6. Coverage gate: **deliberately deferred** (needs a measured baseline first) — add one ci.yml comment noting it.

---

## §FIX-J — Schema hardening (nested additionalProperties) — Wave 6

**Scope (ONLY):** `schemas/*.schema.json` (NOT `cross-sheet-invariants.json`), `tests/schemas/`, `docs/ARCHITECTURE.md` (one §20.2 note).

1. Audit evidence: 13+ schemas accept unknown fields in NESTED objects (verified live: `portfolio-config.schema.json::cadence.weekly_brief` accepted `UNKNOWN_FIELD`). Named offenders: consistency-report, dataforseo-endpoint-mapping, excel-config, excel-source-manifest, gsc-tool-mapping, monthly-report, portfolio-config, project-config, scrapling-output-mapping, sf-export-mapping, sf-mcp-tool-mapping, sf-required-reports, staging-to-excel-map (+ re-scan ALL schemas including ones added by earlier waves).
2. **Procedure per schema (safety-first):** (a) enumerate nested object nodes lacking `additionalProperties`; (b) validate every available instance against the TIGHTENED draft — engine-side instances (templates/, mcp-tool-registry.json, google-update-calendar.json, ctr-curve.json) AND workspace instances via `PSEO_WORKSPACE_ROOT` (project.config.json ×N, portfolio.json, consent/session markers); (c) only where all instances pass → set `additionalProperties: false`; (d) where a live instance violates → DO NOT tighten; record in your report (schema, node, offending file, field) for an operator decision.
3. Add `tests/schemas/test_nested_additional_properties.py`: walks every schema, asserts every `type: object` node declares `additionalProperties` explicitly (allowlist file for intentionally-open nodes, each with a one-line justification).
4. Add `tests/schemas/test_master_template_matches_schema.py`: openpyxl-read `templates/master-excel.xlsx` — sheet names + header rows match `master-excel.schema.json` (incl. the columns added by GAP-M-1b).
5. `docs/ARCHITECTURE.md` §20.2 (or nearest section): one paragraph documenting that the events `event_type` enum is forward-declared (12 values, currently ~2 emitted) — by design, not drift.

**DURUR-if:** more than 3 schemas have live-instance violations (stop, report the full list — that's an operator data-cleanup decision, not a worker call).

---

## §FIX-MFIN — Test infra + count-pin consolidation — Wave 6

**Scope (ONLY):** `tests/**` (listed below), NEW root `pytest.ini`, NEW `tests/_count_pins.py`, README/plugin.json/marketplace.json/WORKFLOWS.md/ci-comment count lines (final reconciliation), `tests/docs/test_count_consistency.py`, `tests/reporting/test_capability_coverage.py`, `tests/docs/test_readme_counts_match_filesystem.py`.

1. **Machine-path de-hardcoding:** `tests/scripts/test_sf_issue_taxonomy.py:25`, `test_sf_projection.py:27`, `test_sf_import_wiring.py:41`, `tests/skills/test_tech_audit.py:1137` (hardcoded `/Users/apple/...demo-aluminum-ca/sf-exports/...`), `tests/smoke/test_multi_project_bootstrap.py:97` (`Path.home()` demo-hvac config). Route all through ONE helper (e.g. `tests/_live_fixtures.py`: root = `os.environ.get("PSEO_WORKSPACE_ROOT")`, skip cleanly when unset or fixture absent). Behavior on this machine unchanged; portable elsewhere.
2. **SF MCP smoke opt-in:** `tests/smoke/test_sf_mcp_smoke.py:44` probes `http://127.0.0.1:11435/mcp` at COLLECTION time — gate behind `PSEO_SF_SMOKE=1` (skip otherwise; no network at collection).
3. **Dead skips:** the 5 tests skipping on the deleted `~/Documents/platinum-seo-workspace-staging` (`tests/skills/test_sf_import.py:190,219`, `test_quick_wins.py:125,175`, `test_init_project.py:538`) — delete or re-point to current workspace fixtures; reword reasons honestly.
4. **Optional-dep posture inversion:** `tests/util/test_piexif_smoke.py:13-14` hard-imports piexif/PIL (collection error if missing) while jsonschema is `importorskip`'d at `tests/scripts/test_bootstrap_project.py:222` + `tests/smoke/test_multi_project_bootstrap.py:148`. Invert: importorskip the imaging deps; hard-import jsonschema (core dep).
5. **Count-pin consolidation + final reconciliation:** create `tests/_count_pins.py` (SKILL_COUNT, COMMAND_COUNT, SCHEMA_FILE_COUNT, CSR_DECLARED, CSR_IMPLEMENTED, tier triplet) imported by the three pin sites; reconcile FINAL values everywhere (after W5: skills 49, commands 29 — VERIFY by `find`, don't trust this doc) including `README.md` status line, `.claude-plugin/plugin.json` + `marketplace.json` descriptions, `docs/WORKFLOWS.md` header, the ci.yml count comment. Fix the misnamed tests (`test_declared_invariant_count_is_31...` asserts 32; `..._24...` asserts 25) — drop numbers from test NAMES.
6. **pytest.ini** (root): `[pytest]` with `testpaths = tests`, `addopts = -ra`. Nothing else (CI flags live in ci.yml — FIX-R).
7. Portfolio fixture dedup (6 files × ~70 duplicated lines): **deferred** — note it, don't do it.

**DONE-when:** full suite green with `PSEO_WORKSPACE_ROOT` set AND with it unset (collection count may differ only via documented skips, never via hardcoded paths); `pytest -q` from a bare clone collects nothing outside `tests/`.

---

## §GAP dispatch — pointers + overrides (read your spec section, then §0 here)

| Batch | Wave | Spec to execute | Manager overrides |
|---|---|---|---|
| **GAP-T1** | W4 | technical-seo spec **Batch 1** (= GAP-T2 faceted + GAP-T3 robots + shared `rules/tech-seo-governance.md` COMPLETE R-125–R-136 + `scripts/util/sheet_merge.py`) | Counts: bump skills 45→47, commands 25→27 across ALL count-lock files (README:8 + counts lines, plugin.json + marketplace.json descriptions, `docs/WORKFLOWS.md` header + 2 catalog rows, the 3 test pin sites, ci.yml comment) — verify current values first. R-58 cross-link one-liner lands here (FIX-H already edited that file in W2 — re-read it fresh). Baseline = your session start-N. |
| **GAP-A-B1** (merchant) | W4 | acquisition spec **GAP-A3** | Rules = **R-147/R-148** (remap). No count changes. No bare R-tokens in the template edit. |
| **GAP-A-B2** (local) | W4 | acquisition spec **GAP-A2** | Rules = **R-144/R-145/R-146** (remap). No count changes. Templates: no bare R-tokens. |
| **GAP-T2** | W5 | technical-seo spec **Batch 2** (= GAP-T4 migration + GAP-T1 hreflang) | Counts: 47→49 / 27→29 (same lock-file list). `sheet_merge.py` + rule file exist from W4 — import, don't recreate. |
| **GAP-M-1a** | W2 | measurement spec **Wave 1a** (= GAP-M4 anomaly + GAP-M1 calendar core) | Create `rules/measurement-discipline.md` COMPLETE with ALL FIVE rules under REMAPPED ids R-137–R-141 (§R-MAP) — including the two (R-138 cohort, R-140 AIO) whose code lands later; take their statement text from the spec's R-126/R-128 sections. All cross-references in SKILL.md/tests use the new ids. |
| **GAP-M-1b** | W3 | measurement spec **Wave 1b** (= GAP-M2 AIO + GAP-M3 scoring) | Do NOT touch `rules/measurement-discipline.md` (M-1a owns it; cite R-140/R-139). Grep-sentinels use remapped ids. Addendum: while in `skills/discovery/quick-wins/SKILL.md`, align the output-report filename to `{date}-quickwin.md` (canonical, matches the template name). |
| **GAP-M-W2** | W5 | measurement spec **Wave 2** (= GAP-M1 report integration + cohorts) | Runs AFTER FIX-K (framing) and GAP-M-1b (same files) — re-read both files fresh; extend (don't rewrite) FIX-K's framing-invariance test to cover `measurement_context`. Cite R-137/R-138 (remapped). |
| **GAP-A-B3** (backlinks) | W7 — **GATED on Süleyman's $100/mo DFS Backlinks decision** | acquisition spec **GAP-A1** | Rules = **R-142/R-143** (remap). Counts: bump from current (expected 49→50 / 29→30). Last monthly_report.py toucher — re-read it fresh (K + M-W2 + B3 ordering). DURUR #0 applies: first live call 4xx → STOP. |
| **GAP-A-B0** (log deferral doc) | folded into FIX-N | acquisition spec **GAP-A4(c)** | Doc-only. |

---

## §REPORT — Per-batch report-back (paste to the manager)

1. Start-N → end-N (full suite), 0 new failures confirmed. Scoped-test results for your area.
2. Full file list touched (must ⊆ your §Scope) + the diff summary per file.
3. Per finding/spec item: the evidence you RE-DERIVED (confirm or correct this doc's line refs) + what you changed + RED→GREEN proof (test names).
4. Confirmations: scope-locked · no commit · secrets-dynamic · no gate weakened · TDD followed · rule-ids per §R-MAP · no bare R-tokens in templates.
5. Any DURUR hit (what, where, why) + anything you saw out-of-scope (report, don't fix).

## §MGR — Manager verification protocol (per wave)

1. Scope check: `git status` files ⊆ union of the wave's batch scopes; anything else → reject batch (qa-loop retry, max 3, then escalate/reassign).
2. Run each batch's scoped tests, then the FULL suite on the combined tree (with and without `PSEO_WORKSPACE_ROOT` from W6 on).
3. Re-derive 2–3 randomly chosen findings per batch against the diff (D11 lesson: never trust inherited derivations).
4. Commit per batch (`fix|feat(<area>): unified-<BATCH-ID> — <summary>` + Co-Authored-By), push per wave to `origin/main`.
5. Wave gate = all batches PASS + full suite green + zero out-of-scope diffs. Then dispatch the next wave.
6. W8 closeout: version bump 2.0.0 → **2.1.0** (Y-05 5-file sync), `RELEASE_NOTES_v2.1.0.md`, annotated tag, final suite, push.
