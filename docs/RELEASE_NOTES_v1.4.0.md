# Platinum SEO Engine v1.4.0 — Release Notes

**Release date:** 2026-05-07
**Tag:** _(no annotated tag — repo PRIVATE, Wave 4 deferred Süleyman karar 2026-05-07)_
**Repos:** `popiliadam/platinum-seo-engine` (PRIVATE) + `popiliadam/platinum-seo-workspace` (PRIVATE)
**Predecessor:** [v1.3.0](RELEASE_NOTES_v1.3.0.md) (2026-05-07)

---

## Section 1 — Overview

v1.4.0 is a hook-coverage + path-modernization + deep-audit + governance-regression
release built on top of v1.3.0. Four workstream categories: (1) **hooks overhaul**
(post-v1.3.0 hygiene — 3-Tier scope, audit redaction + matcher coverage + Stop /
SubagentStop event coverage + 4-hook unit test matrix), (2) **bootstrap paths
modernization** (`scripts/state/bootstrap_project.py` 7 path field default modern
workspace convention sync, env-required workspace_root, multi-project e2e smoke
test), (3) **deep audit fix** (rules + schemas + templates engine self-violation:
9 CRITICAL + 11/12 HIGH theme RESOLVED + 6 governance regression test deployed +
drift-check skill F-23..F-28 expansion), (4) **cleanup batch** (2 of 4 unqualified
hook scripts authored: `check_append_only.sh` + `check_excel_writer.py`;
`bootstrap_project.py` default --out PSEO_WORKSPACE_ROOT-aware).

The drift-check verdict held **AMBER** throughout (F-16 + F-17 PASS post-v1.1
hygiene; F-13 historical 5 row kalıntı baseline carry append-only). pytest CI
baseline transition: **676 PASS + 8 skip → 970 PASS + 11 skip** (+294 PASS,
+3 skip cumulative across 4 phases). DECISIONS.md **6112B → 6126B** (cap 6144B
intact, 18B headroom; +14B from ADR-038 K-01 clarification post-deep-audit-fix
T2 Step 2). 2 active ADR (ADR-037 Data Hygiene + ADR-038 R-XX Numbering),
ADR-036 sync invariant **6'ıncı uygulama** cumulative (this release).

**Repo visibility deferred PRIVATE** per Süleyman karar 2026-05-07 — engine + workspace
both kalır PRIVATE. PUBLIC publication ileri tarihte ek session (Wave 3 marketplace
metadata + Wave 4 visibility toggle + git tag + GitHub release).

---

## Section 2 — Wave Summary (v1.3.0 → v1.4.0)

### v1.3-Hooks-Overhaul (post-v1.3.0 hygiene, 6 atomic + 2 closeout, 2026-05-07)
- `daa19c3` — brief authoring: 3-Tier scope (14 finding fix + 2 yeni hook)
- `0376341` — fix: brief authoring drift `ghp_` literal redact (Lesson 38 v2
  self-check 19'uncu uygulama)
- `9ef90e4` — Tier 1 (3 KRİTİK risk fix): Bash audit redaction +
  matcher Bash coverage + audit_action semantic mapping
- `a3e6b87` — Tier 2: 4-hook unit test matrix + perf polish
- `c33dcda` — Tier 3: Stop + SubagentStop event coverage
- `a40598a` — closeout: banner advance + memory finalize
- `7665d4a` — fix: closeout PHASE_STATUS AKIA literal redact
  (Lesson 38 v2 self-check 21'inci uygulama, meta-recursion catch)

**Outcome:** Post-v1.3.0 hooks layer hardening. 14 finding fix + 2 yeni hook
(Stop + SubagentStop) deployed. 4-hook unit test matrix Bash coverage genişletildi.
Engine HEAD `7665d4a` PUSHED. pytest 743 PASS + 9 skip post-Hooks-Overhaul.
Lesson 38 v2 19'uncu + 21'inci self-check (meta-recursion: brief authoring kendi
secret-grep hook'unu trigger etti).

### v1.4-Bootstrap-Paths-Fix (4 atomic + closeout, 2026-05-07)
- `df4aa3f` — Q-V1.4-BOOTSTRAP-PATHS-01 raised: eykom onboarding kanıt
- `da166c8` — brief authoring: 4 Tier scope (~120-150 dk)
- `658a29e` — Tier 1: `bootstrap_project.py` 7 path field default'ı modern
  workspace convention'a güncelle + workspace_root env-required
  (PSEO_WORKSPACE_ROOT missing → sys.exit(2))
- `6a42fb1` — Tier 2: `tests/state/test_bootstrap_project.py` +11 path
  regression-lock test EXTEND
- `d6ad192` — Tier 3: multi-project e2e smoke test (eykom + dentnotion
  parallel onboarding)

**Outcome:** Q-V1.4-BOOTSTRAP-PATHS-01 RESOLVED. 7 path default modernize:
- `excel_filename`: `master.xlsx` (lowercase F1 workbook policy)
- `sf_exports_dir`: `inbox/sf` (was `sf-exports/`)
- `staging_dir`: `_state/cache` (was `staging/`)
- `reports_dir`: `outputs/reports` (was `reports/`)
- `blog_dir`: `outputs/content/drafts` (was `blog/`)
- `backups_dir`: `_state/backups` (was `_backups/`)
- `workspace_root`: env-required (no engine repo path fallback; F-16 invariant)

Eykom onboarding case zafer: 2'inci proje portfolio scaffold modern conv ile
drift sıfır. pytest 825 PASS + 11 skip post-Tier-3 (+82 yeni test).

### v1.4-Deep-Audit-Fix (14 atomic + closeout, 2026-05-07)
- `e9b9532` — audit artifact: rules/+schemas/+templates/ deep audit
  (78 finding, 9 CRITICAL + 12 HIGH tema)
- `77ed6be` — brief authoring: 4 Tier + closeout, ~15 atomic commit, ~9 gün
- `148f68b` — 3-bundle Q raised: Q-V1.4-AUDIT-CRITICAL-01 + HIGH-01 +
  GOVERNANCE-01

**Tier 1 — Schema Integrity (5 commits, 2026-05-07):**
- `3a08d80` — K-02: 14 schema `$id` HTTP/path/suffix mass-fix
  (ADR-012 + naming.md enforce)
- `48553f5` — K-03 + K-04: master-excel.schema.json `$id` + `title` field +
  `definitions/taskIdPattern` + `master_task` col A `task_id` ref
- `de1efb0` — K-05: events.primary_source enum sync to master_task
  (additive 9 → 11; `internal_links` + `new_content_plan`)
- `99b9d08` — H-B: schema_version coverage — additive add (project-memory +
  skill-frontmatter) + portfolio-config const enforcement
- `29fe513` — H-C: central pattern $ref consolidation in events.schema
  (5 patterns extracted to definitions: T-NNNN, sha256, kebab slug, pillar,
  workflow_run_id)

**Tier 2 — Rules Discipline (4 commits, 2026-05-07):**
- `4112cdd` — fresh-session resume prompts (T2 + T3 + T4 + Closeout)
- `475bec4` — H-A + K-09 alt: `rules-frontmatter.schema.json` NEW + 7 rule
  frontmatter normalize
- `07f317b` — K-01: R-26 (CTA Zorunlu) definition + ADR-038 K-01 clarification
- `7d16651` — H-D: R-22/R-57 + R-50/R-115 dedupe per ADR-038
- `5412827` — K-09 + H-I + H-J + H-K: misc cleanup — broken URL +
  GLOSSARY anchor + lesson counters + ADR-022 chain

**Tier 3 — Templates + Documentation (4 commits, 2026-05-07):**
- `b20b58b` — K-06 + K-07: 11/27 reports `$run_id` placeholder +
  7/27 reports `## Kanıt zinciri` H2 (audit trail coverage)
- `efbfba6` — H-F: reports source_rules + frontmatter policy
  (single-source-of-truth.md new section + 17 reports HTML comment block)
- `b42a1b9` — H-H: profile/profiles cascade documentation
  (content-quality.md Principle 2 + new-blog.template.md frontmatter)
- `08f0787` — H-L: events.schema legacy task_id oneOf bypass
  (definitions/legacyTaskIdPattern)

**Tier 4 — Governance Regression Tests (1 commit, 2026-05-07):**
- `b35bc62` — Q-V1.4-AUDIT-GOVERNANCE-01: 6 regression test deployed
  (test_id_format + test_version_field + test_cross_schema_enums +
  test_r_xx_resolution + test_run_id_coverage + test_frontmatter) +
  3 ek pass (test_self_validate jsonschema runtime + test_instance_validation
  events.jsonl + test_hook_scripts_exist) + drift-check skill F-23..F-28
  expansion (Engine Self-Governance subsection)

**Closeout:**
- `40fe42d` — closeout: 3 Q-XXX RESOLVED + Q-V1.5-HOOK-SCRIPTS-MISSING-01 raise +
  banner advance + audit footer

**Outcome:** **3/3 v1.4 audit findings RESOLVED:**
- Q-V1.4-AUDIT-CRITICAL-01 — 9/9 CRITICAL closed (Option a — full milestone scope)
- Q-V1.4-AUDIT-HIGH-01 — 11/12 HIGH closed (Option b — H-E `event_type` enum
  bump DEFER v1.5; remaining 11 themes resolved)
- Q-V1.4-AUDIT-GOVERNANCE-01 — 6 regression tests + 3 ek pass deployed
  (Option a — combined T4 commit)

**+1 Q-V1.5 raised:** Q-V1.5-HOOK-SCRIPTS-MISSING-01 (4 cited scripts/hooks/*
not authored — yan-discovery from T4 `test_hook_scripts_exist.py` codification).

pytest 825 → 949 PASS + 11 SKIP cumulative (+124 yeni test cumulative). .mcp.json
482B byte-byte korundu (F-16 28+ commit cumulative). DECISIONS.md
6112 → 6126B (cap 6144B intact, 18B headroom). plugin.json 1.3.0 unchanged
(ADR-036 5-file sync intact). Brief premise revize 5x (Lesson 38 v2 24-28th
cumulative catches: json round-trip drift T1, file structure varsayımı T1,
R-25/R-27 yer iddiası T2, lesson counter line :31 → lesson 8 not 38 T2,
F-19..F-24 numbering çakışma T4 → F-23..F-28 next available).

### v1.4-Cleanup-Batch (2 atomic + closeout, 2026-05-07)
- `baecb91` — Q-V1.4-BOOTSTRAP-DEFAULT-OUT-01 P3: `bootstrap_project.py`
  default --out PSEO_WORKSPACE_ROOT-aware (4-step chain `args.out >
  PSEO_PROJECTS_DIR > PSEO_WORKSPACE_ROOT/projects`) + 3 yeni regression test
  (cwd-pollution explicit not-exists assertion; Lesson 38 v2 29th catch —
  ilk test tasarımı `cwd=tmp_path` + env aynı dizine settled tautological
  PASS; düzeltme separate cwd vs ws_root)
- `3f00902` — Q-V1.5-HOOK-SCRIPTS-MISSING-01 P2 (option b — partial 2 of 4):
  `scripts/hooks/check_append_only.sh` NEW (jsonl non-append guard, 3 modes:
  --staged / --working-tree / --rev-range) + `scripts/hooks/check_excel_writer.py`
  NEW (master.xlsx writer policy guard, 3 writer signals: commit msg ref /
  PSEO_EXCEL_WRITER env / --allow-direct-edit override) + 18 yeni test
  [9 append-only scenarios + 9 excel-writer scenarios] + EXPECTED_DEFERRED
  set 4 → 2 (Lesson 38 v2 30th catch — macOS `/bin/bash` 3.2.57 `mapfile`
  builtin yok → portable explicit while-read loop refactor)
- `61f4c3c` — closeout: Q-V1.4-BOOTSTRAP-DEFAULT-OUT-01 + Q-V1.5-HOOK-SCRIPTS-MISSING-01
  RESOLVED + banner advance

**Outcome:** **2 Q kapatıldı:**
- Q-V1.4-BOOTSTRAP-DEFAULT-OUT-01 (P3) — RESOLVED option a
- Q-V1.5-HOOK-SCRIPTS-MISSING-01 (P2) — RESOLVED partial 2 of 4 (option b);
  remaining 2 (`check_naming.py` + `validate_before_write.py`) preserved
  by-design (rule body explicitly "Phase 13'te otomatize" qualifier-rules)

pytest 952 → 970 PASS + 11 SKIP (+18 new test cumulative). DURUR ✓ all
(.mcp.json 482B + DECISIONS 6126B + plugin 1.3.0). Atomic phase paterni
**51'inci kanıt 55 phase consecutive convergent invariant intact**.

### v1.4-Marketplace-Publication-Wave-1 (this release, 1 atomic, 2026-05-07)
- This commit — version sync (ADR-036): `plugin.json` 1.3.0 → 1.4.0 +
  `marketplace.json` 1.3.0 → 1.4.0 + description sync (19→20 schemas,
  18→20 rules, 4→6 hooks, 676→970 pytest baseline) +
  `README.md` `**Status:**` banner v1.3.0 → v1.4.0 + `INSTALL.md` `Status:`
  banner v1.3.0 → v1.4.0 + this `RELEASE_NOTES_v1.4.0.md` (NEW) + 1 doc-fix
  (skills/reporting/monitoring-weekly/SKILL.md phantom path —
  `INLINE_TEMPLATE` lives in Block 3 of SKILL.md inline orchestration,
  not in non-existent `scripts/reporting/monitoring_weekly.py`).

**Outcome:** ADR-036 5-file sync 1.4.0 uniform; test_version_sync invariant
GREEN. Audit finding doc-drift batch closure (K-03 + O-01 + O-02 from
2026-05-07 audit — version + hook count + monitoring-weekly phantom).

---

## Section 3 — Architectural Decisions

**No new ADR added in v1.4.0** (active 2 unchanged: ADR-037 + ADR-038).
DECISIONS.md **6112B → 6126B** (+14B from ADR-038 K-01 clarification post-
deep-audit-fix T2 Step 2 — ADR-038 metnine "K-01 closure 2026-05-07: undefined
R-XX cited in templates = MUST-FIX (test_r_xx_resolution.py lock; R-26
inserted)" 14B addition). 6126/6144B held (18B headroom under hard cap
ADR-026).

### ADR-036 sync invariant uygulama
v1.4.0'da **6'ıncı uygulama** kümülatif:
1. v1.1.0 ilk tam uygulama (`27b6010` Wave 3 Task 3.4)
2. v1.3 ergonomi marketplace.json description sync
3. v1.3 audit-fix-wave-0 marketplace.json description sync
4. v1.3 audit-fix-wave-2 marketplace.json description sync
5. v1.3.0 release: plugin.json + marketplace.json + README + INSTALL +
   RELEASE_NOTES_v1.3.0.md uniform 1.3.0
6. **This release: plugin.json + marketplace.json + README + INSTALL +
   RELEASE_NOTES_v1.4.0.md uniform 1.4.0**

---

## Section 4 — Test + Invariant Delta

| Property | v1.3.0 | v1.4.0 | Delta |
|---|---|---|---|
| pytest baseline | 676 PASS + 8 skip | **970 PASS + 11 skip** | +294 PASS, +3 skip |
| CI strict mode | 7/7 steps | 7/7 steps | unchanged |
| drift-check verdict | AMBER (final) | **AMBER held** | unchanged |
| .mcp.json | 482B (Wave 3 baseline) | **482B byte-byte korundu** | unchanged (28+ commit cumulative) |
| DECISIONS.md | 6112/6144B held | **6126/6144B held** | +14B (ADR-038 K-01 clarification) |
| Slash commands | 15 (production) | 15 (production) | unchanged |
| Skills | 43 (`status: active`) | 43 (`status: active`) | unchanged |
| Schemas | 19 (description claim) | **20** (rules-frontmatter.schema.json NEW T2 Step 1) | +1 (additive) |
| Rules | 18 (description claim) | **20** (drift catch — was 20 actual; description was stale) | +2 (description sync) |
| Hooks | 4 (description claim) | **6** (drift catch — was 6 actual; description was stale) | +2 (description sync) |
| MCP servers | 3 plugin + 1 user-level | 3 plugin + 1 user-level | unchanged |
| F-16 invariant cumulative | 26+ commit | **30+ commit cumulative** | +4 commit |
| Plugin agnostik | 0 slug literal | 0 slug literal | unchanged |

**F-16 invariant** (.mcp.json byte-byte): **30+ commit cumulative korundu** v1.4
milestone boyunca. Plugin agnostik discipline: **0 slug literal grep** v1.4
milestone boyunca.

**Lesson 38 v2 stacked enforcement** v1.4 milestone: **30 cumulative catches**
(19'uncu hooks-overhaul brief drift → 30th cleanup-batch macOS bash 3.2 mapfile
incompatibility). Atomic phase paterni: **51'inci kanıt 55 phase consecutive
convergent invariant intact**.

---

## Section 5 — Upgrade Notes

For users on v1.3.0:

1. `git pull` engine.
2. Re-run `/plugin add` (plugin.json version bumped 1.3.0 → 1.4.0; same 15
   command palette, same 43 skill, but 6 hook coverage instead of 4
   description-claim).
3. **No env var migration required** — all v1.3 contracts intact;
   `PSEO_WORKSPACE_ROOT` canonical, `PSE_WORKSPACE_PATH` 1y shim active until
   2027-05-06.
4. **No schema migration required** — all v1.3 schemas backwards-compatible
   additive only:
   - `events.primary_source` enum 9 → 11 (additive; existing 9 values intact)
   - `master-excel.schema.json` `definitions/taskIdPattern` NEW + col A ref
     (additive; legacy task_id'ler `definitions/legacyTaskIdPattern` oneOf
     bypass via H-L)
   - `rules-frontmatter.schema.json` NEW (additive — 7 rule normalize already
     applied)
   - `project-memory.schema.json` + `skill-frontmatter.schema.json` `schema_version`
     field NEW (additive const)
   - `events.schema.json` 5 central pattern $ref consolidation (refactor only;
     wire-format identical)
5. **`bootstrap_project.py` paths breaking change** for users on PRE-v1.4
   workspaces: 7 path field default'ı modernize. **Mitigation:** existing
   workspaces are untouched (paths are written into `project.config.json`
   at bootstrap time; live workspaces use the values from their own config,
   not the script defaults). New project bootstrap (`/pseo-init`) emits
   modern convention by default. Eski workspace'leri kullanan kullanıcılar
   etkilenmez.

**No breaking changes** for skill / command / script callers (additive only).
v1.4 hooks expansion carried out via post-v1.3.0 `v1.3-hooks-overhaul` work
+ deep audit fix governance test deploy + cleanup batch script authoring;
all backwards-compatible additive.

---

## Section 6 — Outstanding (deferred)

### Wave 3+ marketplace publication (deferred Süleyman karar 2026-05-07)
- **Wave 3:** marketplace install snippet + metadata
- **Wave 4:** repo visibility PRIVATE → PUBLIC + v1.4.0 git tag + GitHub release page

These deferred — Süleyman PRIVATE kalsın kararı engine + workspace ikisi de.
Brief baseline (`8ff8b88` 371 satır + this release notes) hazır. PUBLIC
açıldığında ek session ~20 dk (Wave 3+4 atomic).

### v1.5 candidates (raised in v1.4 milestone)

- **H-E events.schema event_type enum bump 1.0 → 1.1** (Q-V1.4-AUDIT-HIGH-01
  Option b deferred): 16-skill `event_type=manual + note=[skill=X]` workaround
  DSL deprecate; major schema_version bump (ADR-018 paterni); migration
  script `scripts/migrations/0004_events_1_0_to_1_1.py`. Estimated ~60-90 dk.
- **`check_naming.py` + `validate_before_write.py`** (Q-V1.5-HOOK-SCRIPTS-MISSING-01
  remaining 2 of 4): rule body "Phase 13'te otomatize" qualifier — preserve
  by-design until Phase 13 timeline finalizes.
- **Multi-project capability test** — yeni proje onboard pipeline e2e (~120 dk
  ayrı session); Tier 3 d6ad192 covered partial (eykom + dentnotion smoke);
  full N-project parallel onboarding test deferred.
- **2026-05-07 scripts audit findings** (this audit pass):
  - K-01: `normalize_url` 10-file dedup → `scripts/util/url_normalize.py`
    extract (~620 satır siler; ~30-45 dk)
  - K-02: `cross-sheet-invariants.json` schema sync F-16..F-22 (~20-30 dk)
  - O-03: `_normalize_dfs_response` tech_audit + competitive_analysis import
    discipline (~15 dk)
  - Y-01..Y-07: 7 yeni script önerisi (release tooling, util consolidation,
    profile-aware defaults, dump_workspace, etc.)
- **Süleyman ek feature backlog** — TBD
- Q-PHASE15-CTXLEDGER-01 (CONTEXT_LEDGER size compression strategy, LOW)

---

## Section 7 — Acknowledgments

Süleyman feedback enforce throughout v1.4 milestone: **"çok titiz çalışmanı
istiyorum cross checksiz ilerleme"** — sürekli runtime cross-check her edit'te
enforce default; her wave-end'de runtime grep verify zorunlu.

**Lesson 38 v2 + Lesson 67 stacked enforcement** (cumulative v1.4 milestone):
- 19'uncu ardışık vaka (hooks-overhaul brief authoring `ghp_` literal redact —
  meta-recursion brief authoring kendi secret-grep hook'unu trigger etti)
- 21'inci ardışık vaka (hooks-overhaul closeout PHASE_STATUS AKIA literal
  redact — closeout dokümanı kendi yeni gate'i trigger etti)
- 22'inci ardışık vaka (bootstrap-paths-fix brief premise — "mevcut
  assertion'lar" iddiası invalidate, runtime grep ile doğrulandı:
  test_bootstrap_project.py YOK)
- 24-28th cumulative catches (deep-audit-fix brief premise revize 5x:
  json round-trip drift T1, file structure varsayımı T1, R-25/R-27 yer
  iddiası T2, lesson counter line :31 → lesson 8 not 38 T2, F-19..F-24
  numbering çakışma T4 → F-23..F-28 next available)
- 29'uncu ardışık vaka (cleanup-batch P3 — `cwd=tmp_path` + env aynı dizine
  settled tautological PASS; düzeltme separate cwd vs ws_root)
- **30'uncu ardışık vaka** (cleanup-batch P2 — macOS `/bin/bash` 3.2.57
  `mapfile` builtin yok → portable explicit while-read loop refactor)

**Atomic phase paterni 51'inci kanıt 55 phase consecutive convergent invariant
intact:**
Phase 7..15 + v1.1-Wave-1+2+3 + v1.1-Integration-Audit + v1.1-Audit-Followup-Phase-A +
v1.2-Phase-B + Cleanup 1+2 + Status Promote + #2 schema + #1 F-16 + ADR closure +
Q-RP-01 + v1.3-ergonomi + v1.3-audit-fix-wave-0 + v1.3-marketplace-brief +
v1.3-audit-fix-wave-2 + v1.3-marketplace-publication-wave-1 +
**v1.3-hooks-overhaul** (3-Tier T1+T2+T3 + closeout) +
**v1.4-bootstrap-paths-fix** (T1+T2+T3 + closeout) +
**v1.4-deep-audit-fix** (T1+T2+T3+T4 + closeout, 14 atomic) +
**v1.4-cleanup-batch** (P2+P3 + closeout) +
**v1.4-marketplace-publication-wave-1** (this release).

**Cross-Audit Metodoloji** (Codex + Opus 4.7) v1.3.0'dan v1.4.0'a kümülatif:
- External fresh-eye audit (Codex paralel) — v1.1.0 baseline
- Internal cross-verification (Opus 4.7) — v1.1.0+
- Manager pre-dispatch full-file inspect (Lesson 38 v2) — 30 ardışık vaka
- Manager self-correction (Lesson 67) — 30 stacked enforcement
- 4 paralel general-purpose agent dispatch (deep-audit-fix audit) +
  manager runtime cross-check 10/78 finding doğrulandı, 2 finding düzeltildi

**Audit artifact:** `docs/audits/v1.4-rules-schemas-templates-2026-05-07.md`
(78 finding source-of-truth).

**Plan briefs:** `docs/superpowers/plans/v1.4-bootstrap-paths-fix-brief.md` +
`docs/superpowers/plans/v1.4-deep-audit-fix-brief.md` +
`docs/superpowers/plans/v1.4-deep-audit-fix-resume-prompts.md`.

Future v1.5+ release cycle template intact.
