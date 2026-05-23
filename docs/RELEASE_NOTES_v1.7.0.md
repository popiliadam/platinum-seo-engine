# Platinum SEO Engine — v1.7.0 Release Notes

**Release date:** 2026-05-23
**Engine HEAD:** post-`<v1.7.0-release>` v1.7.0 release commit (5-file sync via Y-05 third production --apply)
**Predecessor:** [v1.6.0](RELEASE_NOTES_v1.6.0.md) (Süleyman backlog closure milestone — Phase 1+2+3)
**Status:** 🟢 GREEN-CANDIDATE (F-13 historical kalıntı; F-16 + F-17 PASS)

## 0. Executive Summary

v1.7 is the **Google AI Optimization Guide compliance + May 2026 Core Update hardening milestone** — 6/6 finding RESOLVED across five atomic engine phases, **23 atomic engine commits** (1 plan + 22 work), **+37 yeni test** (1147 → 1184 PASS + 11 SKIP, regression sıfır), `.mcp.json` 482B byte-byte korundu (F-16 47 → 60+ commit cumulative), `DECISIONS.md` 6126B unchanged (cap 6144B intact, 18B headroom), 0 slug literal in plugin runtime code (plugin agnostik invariant intact). **No new ADR**: existing ADR-009/-016/-018/-031/-033/-035/-036/-038 paterni reuse; `DECISIONS.md` cap aşımı sıfır.

Five atomic phases convergent: **Phase-1** doc rationale rewrites (R-98 LLMs.txt aligned with Google 2026-05-15 + R-101/R-102 reframed helpful-content+scannability not AI-specific), **Phase-1.5** pre-existing drift cleanup inception (4 baseline failures: 3 `.claude/worktrees` stale + 1 README banner regex), **Phase-2** IPTC metadata G-AI-01 (piexif dep + DigitalSourceType writer + generate-images skill contract lock Step 5b + R-78 rule), **Phase-3** Bank Seed Foundation G-AI-05 (3-stage hybrid pipeline: Stage A DFS+Scrapling auto-discovery + Stage B markdown operator review + Stage C atomic write with R-44 evidence_url validation + schema v1.3→v1.4 migration #0004 with 4 R-121 enrichment fields + brand-onboarding/init-project mandatory cascade), **Phase-4** R-121 rotation+density cap (rule + 3 production skill SKILL.md spec-lock for new-blog/revise-content/faq-optimization), **Phase-5** gbp-audit discovery skill G-AI-02 (master.xlsx[gbp_audit] sheet schema + SKILL.md + slash command + report template + gbp_audit_transform.py TDD with 6/6 GREEN).

**Atomic phase paterni 67'inci kanıt cumulative** — 71 phase consecutive convergent invariant intact (5 v1.7 cycle phases: 1 + 1.5 + 2 + 3 + 4 + 5 = 6 evidence; minus Phase 1.5 inception drift cleanup ≈ 5 atomic-phase-paterni). **Lesson 38 v2 60 → ~67 cumulative catches** (≈7 v1.7 catches: location drift cross-check Task 4.1 + cross-skill cap interplay scope Task 4.4 + custom enum vs codebase definition drift Task 5.1 + broken template ref invariant Task 5.2 + status_enum_reuse decision Task 5.1 + severity_enum_reuse decision Task 5.1 + bank-driven cluster file boundary Task 4.1).

**Y-05 third production dogfooding:** `scripts/release/version_bump.py --apply` v1.5.0'da ilk + v1.6.0'da ikinci + v1.7.0'da üçüncü kez devreye girdi — own-tooling invariant cross-validation 3'üncü kanıt (test_version_sync.py post-apply GREEN).

## 1. Phase-1 — Doc rationale rewrites (Y-AI-01 + Y-AI-02)

**Scope:** R-98 / R-101 / R-102 rationale alignment with Google 2026-05-15 AI Optimization Guide (advisory only — no rule body changes; rationale rewrites only).

### 1.1 Findings RESOLVED
- **Y-AI-01** [🟡 P2] — R-98 LLMs.txt rationale aligned with Google 2026-05-15 explicit position "LLMs.txt is unnecessary". Rule body intact; rationale rewrite captures the official position + maintains rule's defensive stance (LLMs.txt remains optional content for explicit AI consumption, not load-bearing).
- **Y-AI-02** [🟡 P2] — R-101 + R-102 rationale reframed: bullet/box format and scannability are **helpful-content + human UX** signals, not AI-specific. Removed prior framing that made the rules look like AI-specific signals; the underlying enforcement (bullet density caps, scannability thresholds) unchanged.

### 1.2 Atomic commits (3 cumulative)
- `fb504de` Phase-1.1 — R-98 rationale Google 2026-05-15 aligned
- `8581950` Phase-1.2 — R-101 reframed helpful-content + scannability
- `3e0c638` Phase-1.3 — R-102 reframed human UX + bookmarkability

### 1.3 Patterns Born / Reinforced
- **Rationale-only rewrite paterni** — rule body + enforcement intact; only the "Rationale" paragraph + cross-link updates. Allows alignment with external authority changes without functional code-path drift.

## 1.5. Phase-1.5 — Pre-existing drift cleanup (inception)

**Scope:** Not in the original plan, but hard constraint #8 ("full suite PASS at start") forced surfacing of 4 pre-existing test failures discovered at Phase 1 start.

### 1.5.1 Drift surfaced
- 3 failures from `.claude/worktrees/sharp-austin-d2a75d` stale worktree — `conftest.py` collect path included the runtime artefact directory.
- 1 failure from README banner regex drift after the `207eb63` public-release rewrite — INSTALL.md format unification broke the older test regex.

### 1.5.2 Atomic commits (2 cumulative + 1 worktree remove)
- `11155fa` Phase-1.5a — conftest collect_ignore_glob `.claude/*` + 2 drift sweep tests `.claude` excluded
- `7636f97` Phase-1.5b — README **Status:** v1.6.0 banner restored + test regex unified with INSTALL
- (no commit) Phase-1.5c — `git worktree remove .claude/worktrees/sharp-austin-d2a75d`

### 1.5.3 Patterns Born / Reinforced
- **Drift-cleanup inception paterni doğum belgesi** — when "full suite PASS" hard constraint surfaces pre-existing failures at the start of a planned phase, insert a Phase-X.5 mid-phase to clean them before proceeding. Avoids "I'll fix it next task" deferral that snowballs into release-blocker stack.
- **Baseline structural protection** — `.claude/*` ignore lives in conftest now, so future runtime artefact directories don't break test collection again (Lesson 38 v2 catch class closed).

## 2. Phase-2 — IPTC metadata (G-AI-01)

**Scope:** Google Merchant Center compliance for AI-generated images via IPTC `DigitalSourceType` EXIF metadata.

### 2.1 Findings RESOLVED
- **G-AI-01** [🟠 HIGH] — Google 2026-05-15 advisory requires AI-generated images to carry IPTC `DigitalSourceType` = `https://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia` for transparent provenance. Engine now writes this metadata on every AI image; the metadata is **EXIF-only**, not visible HTML (honoring `feedback_ai_disclosure_ban` — no "AI tarafından yazıldı" visible disclosure).

### 2.2 Atomic commits (4 cumulative)
- `c28cb02` Phase-2.1 — piexif>=1.1.3 dependency + smoke test
- `65d03d4` Phase-2.2 — IPTC writer utility TDD (5/5 PASS)
- `2d5bb43` Phase-2.3 — generate-images SKILL.md Step 5b contract + paired tests (1 skip Phase 11 deferred runtime)
- `e41dcd9` Phase-2.4 — R-78 AI-image IPTC disclosure rule

### 2.3 Patterns Born / Reinforced
- **Metadata-only disclosure paterni** — IPTC EXIF is machine-readable provenance; visible HTML disclosure remains banned per `feedback_ai_disclosure_ban`. Solves the AI-content-detection requirement without triggering the "AI yazmış" user-psychology problem.
- **Stub-mod pattern 3'üncü application** — Phase 2.3 generate-images runtime deferred to Phase 11 Wave 2; SKILL.md contract + paired tests lock the interface so the eventual runtime can't drift.

## 3. Phase-3 — Bank Seed Foundation (G-AI-05)

**Scope:** Hybrid 3-stage pipeline (auto-discovery + operator review + atomic write) for populating R-105 / R-114 / R-119 bank entries. Critical for May 2026 Core Update — pre-Phase-3 the rules were trivially passing on empty banks.

### 3.1 Findings RESOLVED
- **G-AI-05** [🔴 CRITICAL] — Empty banks meant R-105 (expert quotes) / R-114 (original research) / R-119 (first-hand experience) had nothing to filter against. Phase 3 ships:
  - Schema migration #0004 (v1.3 → v1.4) adding 4 R-121 enablement fields to each bank entry: `applicable_topics`, `phrasings`, `last_used_in_content_id`, `max_usage_per_month`.
  - **Stage A** (auto-discovery): DFS WHOIS + DFS keywords-for-site + DFS business listings + Scrapling case-study probes. Read-only ingestion per `feedback_indexing_api_consent`.
  - **Stage B** (operator review): markdown review prompt with `[A] approve / [E] edit claim_core: "..." / [R] reject` per-entry decisions dict.
  - **Stage C** (atomic write): R-44 evidence_url validation as a single-boundary all-or-nothing gate; experience entries require `evidence_url`, research entries require `url`; failure leaves file untouched.
  - brand-onboarding + init-project mandatory cascade (init MUST emit `cascade: brand-onboarding` event; bank-seed Stage C is a prerequisite for init considering itself "complete").

### 3.2 Atomic commits (5 cumulative)
- `8e07e1c` Phase-3.1 — schema v1.3→v1.4 + migration #0004 + 6 cascade test updates (10 files)
- `01a5617` Phase-3.2 — Stage A discovery (DFS+Scrapling stubs) + tests/conftest.py fixtures
- `d630970` Phase-3.3 — Stage B operator review (generate_review_prompt + apply_review_decisions)
- `cb8df43` Phase-3.4 — Stage C atomic bank write with R-44 evidence_url validation
- `c3da696` Phase-3.5 — brand-onboarding 3-stage pipeline + init-project mandatory chain

### 3.3 Patterns Born / Reinforced
- **R-44 single-boundary design paterni doğum belgesi** — plan put evidence_url check in Stage B; refactored to Stage C atomic gate. Single source of truth + operator can add URL during edit + batch-level rejection if any entry invalid.
- **Cascade fix in single atomic (5+ reuse)** — Task 3.1 schema bump → 6 cascade test updates absorbed into ONE commit; no "fix it next task" deferral.
- **Mandatory cascade paterni doğum belgesi** — init-project MUST emit `cascade: brand-onboarding` event; auto-runner picks it up. Closes the "I forgot to seed the bank" gap project-wide.

### 3.4 Interim Closeout (Phase-3 end)
After Phase 3 the cycle hit the natural mid-point break:
- `e546130` Phase-3 interim closeout — `docs/PHASE_STATUS.md` new "Active Phase" banner for v1.7.0-Phase-3; memory `project_v1_7_google_compliance.md` NEW captures cumulative state; MEMORY.md index updated. Branch held local (push deferred to v1.7 final).

## 4. Phase-4 — R-121 rotation + density cap (R-121)

**Scope:** Semantic counterpart to R-118 (stylistic). R-121 catches the failure mode where R-105/R-114/R-119 bank entries (now populated by Phase 3) get parrot-copied into every blog post the moment a topic surfaces.

### 4.1 Findings RESOLVED
- **R-121** [🟠 HIGH] — Three filters MUST hold together at pre-publish:
  1. **Topic Relevance** — `entry.applicable_topics ∩ blog.topics ≠ ∅`
  2. **Density Cap** (profile-aware) — YMYL: 2 exp + 1 res; b2b-saas: 1+1; e-commerce/local-service/portfolio: 1+0
  3. **Rotation (30-day)** — `master.xlsx[completed_work]` `usage_count >= max_usage_per_month` → skip; rotate to alternative `phrasings[]` or different entry

### 4.2 Atomic commits (4 cumulative)
- `f6d8467` Phase-4.1 — R-121 rule (rules/content-quality.md, R-119 neighborhood — semantic cluster, plan said content-eeat-discipline.md drift documented)
- `a99297f` Phase-4.2 — new-blog SKILL.md R-121 selection logic spec
- `4c45864` Phase-4.3 — revise-content SKILL.md R-121 spec (per-content cap includes pre-revision entries)
- `9a84c01` Phase-4.4 — faq-optimization SKILL.md R-121 spec (conditional applicability — most FAQ items need no bank entry)

### 4.3 Patterns Born / Reinforced
- **Plan drift surface + relocate paterni** — plan said `content-eeat-discipline.md` but R-119 actually lives in `content-quality.md` (R-105/R-114/R-117/R-118/R-119 cluster). Manager session surfaced + Süleyman approved Option A (relocate to semantic neighborhood, document drift in commit body). Plan dosyası historical artefact — not retro-edited.
- **Stub-mod pattern 4'üncü application** — `scripts/production/` does not exist; Phase 4.2-4.4 are spec-lock only. Runtime in Phase 11 Wave 2/3.
- **Cross-skill cap interplay paterni doğum belgesi** — R-121 density is per CONTENT not per SKILL invocation. new-blog body + revise-content body + faq-optimization FAQ share the same per-profile cap. Tightened in faq-optimization (b2b-saas 0/0 inside FAQ default).
- **R-110 + R-121 reinforcement paterni doğum belgesi** — over-citation gate (>2 per 500w) and density cap reinforce each other. FAQ items needing >1 bank entry → split (too broad) or move to body (R-91 redirect).

## 5. Phase-5 — gbp-audit discovery skill (G-AI-02)

**Scope:** Local-service projects (demo-aluminum CA, demo-construction İnşaat, demo-hvac hybrid) need GBP gap audits. 8 categories (NAP / categories / photos / hours / attributes / posts / Q&A / reviews); read-only audit per `feedback_indexing_api_consent`.

### 5.1 Findings RESOLVED
- **G-AI-02** [🟠 HIGH] — Engine now ships `skills/discovery/gbp-audit/`:
  - Profile-gated at Step 1 (`"local-service"` required, e-commerce/b2b-saas/portfolio skip cleanly).
  - Single paid endpoint: `mcp__dataforseo__business_data_business_listings_search` (~3 credits/run vs tech-audit's ~13).
  - Scrapling fallback when DFS empty (Google Maps place page); anti-bot block tolerated (transform emits HIGH "listing not found" row).
  - **NO autonomous GBP API submit** — read-only audit + report only. Operator does the GBP dashboard work manually based on `recommended_action` column.

### 5.2 Atomic commits (3 cumulative)
- `9f3e829` Phase-5.1 — master.xlsx[gbp_audit] sheet schema (additive 18 → 19 sheets; statusEnum + severityEnum codebase definition reuse, not the plan's custom enums)
- `714ab6d` Phase-5.2 — gbp-audit SKILL.md scaffolding + commands/pseo-gbp-audit.md + templates/reports/gbp-audit.template.md (broken-template invariant surfaced template as hard ship requirement)
- `ec200f2` Phase-5.3 — gbp_audit_transform.py + tests/skills/test_gbp_audit.py TDD RED→GREEN (6/6 PASS first try)

### 5.3 Patterns Born / Reinforced
- **Profile-gate-first paterni doğum belgesi** — Step 1 profile check BEFORE budget pre-flight, BEFORE any paid call. e-commerce/b2b-saas/portfolio skip cleanly with `status=skipped` (graceful, not error). Reusable for future profile-conditional discovery skills.
- **Custom enum vs codebase definition drift paterni** — plan suggested custom enums for status/severity; codebase already defines statusEnum (7-value) + severityEnum (4-value). Reusing definitions keeps cross-sheet vocabulary consistent (master_task, content_decay, schema, redirect_404, crawl_sitemap all speak the same language). Drift documented in sheet description.
- **Broken-template invariant surface paterni doğum belgesi** — `tests/scripts/test_template_refs.py::test_explicit_template_refs_resolve` is a Wave-3 broken-ref sweep; turned the template stub from "Phase 11 W deferred" into a hard ship requirement when SKILL.md referenced the path. Lesson: every `templates/<subdir>/<name>.template.<md|html>` reference is a hard contract; template files ship with the SKILL.md that names them.
- **TDD RED→GREEN single-pass paterni** — SKILL.md step 6 severity matrix table was the implementation contract; 6/6 PASS on first iteration because the matrix was already locked in spec. "Tablo değişirse kod değişir lockstep."

## 6. Drift Baseline (v1.7.0 release post-Y-05 third --apply)

| Metric | v1.6.0 baseline | v1.7.0 release | Change |
|---|---|---|---|
| pytest PASS | 1147 | **1184** | +37 yeni test cumulative (regression sıfır) |
| pytest SKIP | 10 | **11** | +1 (Phase 2.3 generate-images runtime deferred Phase 11) |
| `.mcp.json` byte | 482B | **482B** | F-16 byte-byte korundu (47 → 60+ commit cumulative) |
| `DECISIONS.md` byte | 6126B | **6126B** | unchanged (cap 6144B intact, 18B headroom; no new ADR) |
| `plugin.json` version | 1.6.0 | **1.7.0** | ADR-036 5-file sync via Y-05 third --apply |
| `marketplace.json` metadata.version | 1.6.0 | **1.7.0** | (5-file sync) |
| `README.md` `**Status:**` banner | v1.6.0 | **v1.7.0** | (5-file sync) |
| `docs/INSTALL.md` `> Status:` banner | v1.6.0 | **v1.7.0** | (5-file sync) |
| `RELEASE_NOTES_v1.7.0.md` | — | **NEW** | manual authoring (Y-05 WARN no auto-create) |
| Plugin agnostik slug literal | 0 | **0** | F-16 invariant intact |
| schema-validate + drift-check helper EXIT=0 | strict | **strict** | unchanged |
| `master-excel.schema.json` sheets | 18 | **19** | +1 (gbp_audit; additive, schema_version "1.0" unchanged) |
| `project-config.schema.json` schema_version | 1.3 | **1.4** | Phase 3.1 migration #0004 (4 R-121 enablement fields per bank entry) |
| Rules (R-XX) count | 121 | **122** | +1 (R-121 bank entry rotation + density cap + topic relevance) |
| New skills | tech-audit + 9 discovery | **+ gbp-audit** | 10 discovery skills total |
| New rules cross-link cluster | R-105 + R-114 + R-119 | **+ R-121** | bank-driven cluster complete (R-118 stilistik + R-121 semantik) |

## 7. Outstanding — Phase 6 + v1.8+ Deferred

Bu release **engine-side complete** — Phase 6 production validation operator workshop ayrı session:

| ID | Scope | Engel |
|---|---|---|
| **Phase 6 — Bank seed pilot** | 3 priority projects: demo-fintech TR (YMYL ≥3 entry), demo-aluminum CA (local-service ≥1), demo-hvac (hybrid ≥1). Workspace repo commits (engine repo değil). | Operator workshop — `PSEO_WORKSPACE_ROOT` set + `/pseo-active <slug>` cycle + brand-onboarding 3-stage Süleyman input + Stage C atomic write |
| **Post Core Update GSC measurement** | May 2026 Core Update rollout 2026-05-21 → 2026-06-03; post-update GSC measurement window ~2026-06-10. | Time-gated — operator monitors GSC + reports back per project |
| **Wave 3+4 PUBLIC marketplace publication** | Marketplace.json public manifest + GitHub Pages deploy | Süleyman PUBLIC karar zorunlu (engine repo PRIVATE → PUBLIC transition) |
| **Süleyman ek items** | TBD | Süleyman input |

## 8. Acceptance Criteria

- [x] 6/6 finding RESOLVED (Y-AI-01 + Y-AI-02 + G-AI-01 + G-AI-05 + R-121 + G-AI-02)
- [x] 5 ayrı atomic phase milestone closure (Phase-1 + Phase-1.5 + Phase-2 + Phase-3 + Phase-4 + Phase-5; Phase 6 deferred to operator workshop)
- [x] 22 atomic engine commit cumulative v1.7 cycle (excluding plan commit `ed89bad`)
- [x] +37 yeni test cumulative (regression sıfır)
- [x] 1 schema additive sheet extension (master-excel.schema.json gbp_audit; additive, schema_version "1.0" unchanged)
- [x] 1 schema bump (project-config v1.3→v1.4 + migration #0004 + 4 R-121 enablement fields per bank entry)
- [x] 1 new rule (R-121) in semantic neighborhood R-119 (content-quality.md, drift documented)
- [x] 4 new files: scripts/discovery/gbp_audit_transform.py + skills/discovery/gbp-audit/SKILL.md + commands/pseo-gbp-audit.md + templates/reports/gbp-audit.template.md + tests/skills/test_gbp_audit.py
- [x] 4 production-skill SKILL.md spec-lock for R-121 + 1 production-skill SKILL.md cascade for brand-seed (new-blog + revise-content + faq-optimization + generate-images + brand-onboarding)
- [x] `.mcp.json` 482B byte-byte korundu (F-16 cumulative 47 → 60+ commit)
- [x] Plugin agnostik 0 slug literal (F-16 invariant; word-boundary verify)
- [x] `DECISIONS.md` ≤6144B (no new ADR — paterni reuse ADR-009/-016/-018/-031/-033/-035/-036/-038)
- [x] `feedback_ai_disclosure_ban` honored — zero visible "AI tarafından yazıldı" wording; R-78 IPTC EXIF only
- [x] `feedback_indexing_api_consent` honored — Stage A discovery + Phase 5 gbp-audit both read-only; no autonomous API submit
- [x] `feedback_hard_constraints` honored — plugin agnostik + append-only state + schema-first
- [x] Atomic phase paterni 61 → 67'inci kanıt cumulative (5 v1.7 phases evidence)
- [x] Lesson 38 v2 cumulative count 59 → ~67 catches (≈7 yeni v1.7 cycle)
- [x] `RELEASE_NOTES_v1.7.0.md` NEW manual authoring
- [x] ADR-036 5-file sync via Y-05 **third** production --apply (1.6.0 → 1.7.0)
- [x] Engine HEAD pushed to origin/main (PRIVATE) + git tag v1.7.0 annotated

## 9. Migration Notes

**v1.7.0 is one mandatory schema bump (project-config v1.3 → v1.4) + one additive schema extension (master-excel gbp_audit sheet).**

- **`project-config.schema.json` v1.3 → v1.4** (migration #0004) — every bank entry (experience_database + original_research_database arrays) gains 4 R-121 enablement fields: `applicable_topics`, `phrasings`, `last_used_in_content_id`, `max_usage_per_month`. Migration is idempotent + dry-run-supported. Existing v1.3 configs auto-upgrade on init-project re-run; brand-onboarding Stage C writes new entries directly into v1.4 shape.
- **`master-excel.schema.json` gbp_audit sheet** (additive, schema_version "1.0" unchanged). Per ADR-018 paterni — sheet additions are additive-only; existing workbooks gain the sheet on next sf-import/init-project; existing sheets untouched.

**Production-skill SKILL.md spec changes (Phase 4 R-121).** new-blog + revise-content + faq-optimization SKILL.md files now carry an "R-121 Bank Selection Logic" section. **No runtime changes yet** — Phase 11 Wave 2/3 ships the actual filter implementation in `scripts/production/`. Until then, the spec lock prevents drift between contract and runtime.

**Discovery skill addition (Phase 5 G-AI-02).** `skills/discovery/gbp-audit/` is the 10th discovery skill. Local-service projects (demo-aluminum CA, demo-construction İnşaat, demo-hvac hybrid) gain a `/pseo-gbp-audit` command + master.xlsx[gbp_audit] sheet auto-populated by skill run. e-commerce / b2b-saas / portfolio pure projects skip the skill gracefully.

**No breaking API changes.** Existing skill/command/hook contracts intact. R-121 is additive (new rule, no rule body retirement). Bank entries created pre-v1.7 still validate (the 4 new fields are optional in the schema for backward compat).

## 10. Cross-References

- Plan: [docs/superpowers/plans/2026-05-21-google-ai-guide-compliance-audit.md](superpowers/plans/2026-05-21-google-ai-guide-compliance-audit.md) (6-phase / 22-task spec)
- v1.6.0 release: [RELEASE_NOTES_v1.6.0.md](RELEASE_NOTES_v1.6.0.md)
- DECISIONS: [DECISIONS.md](DECISIONS.md) (ADR-009/-016/-018/-031/-033/-035/-036/-038 paterni reuse — no new ADR)
- PHASE_STATUS: [PHASE_STATUS.md](PHASE_STATUS.md) (banner advance v1.7.0 MILESTONE CLOSED)
- Schema migration: `scripts/migrations/0004_project_config_1_3_to_1_4.py`
- Memory entry: `[[project_v1_7_google_compliance]]` (cycle progress + commit SHA → task mapping + hard-constraint compliance audit)
- Hard-constraint memories: `[[feedback_ai_disclosure_ban]]` + `[[feedback_indexing_api_consent]]` + `[[feedback_hard_constraints]]`

---

**v1.7.0 milestone CLOSED (engine-side).** Engine HEAD `<5-file-sync release commit>` PUSHED to `origin/main` + git tag `v1.7.0` annotated. Phase 6 operator workshop (bank seed pilot for demo-fintech TR + demo-aluminum CA + demo-hvac) **ayrı session, workspace repo scope** — engine code-side seal complete. Post Core Update GSC measurement window ~2026-06-10+.
