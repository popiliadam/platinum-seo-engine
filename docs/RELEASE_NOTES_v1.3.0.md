# Platinum SEO Engine v1.3.0 — Release Notes

**Release date:** 2026-05-07
**Tag:** _(no annotated tag — repo PRIVATE, Wave 4 deferred Süleyman karar 2026-05-07)_
**Repos:** `popiliadam/platinum-seo-engine` (PRIVATE) + `popiliadam/platinum-seo-workspace` (PRIVATE)
**Predecessor:** [v1.1.0](RELEASE_NOTES_v1.1.0.md) (2026-05-06)

---

## Section 1 — Overview

v1.3.0 is a feature expansion + drift hygiene + publication readiness release built
on top of v1.1.0. Three workstream categories: (1) **ergonomi expansion** (9 → 15
slash commands for VS Code Claude Code palette), (2) **audit-driven drift sync**
(3 critical runtime drift fix Wave 0 + 5 sub-critical drift sync Wave 2), (3)
**pre-publication security audit** (Wave 1 marketplace publication readiness).

The drift-check verdict held **AMBER** throughout (F-16 + F-17 PASS post-v1.1
hygiene; F-13 historical 5 row kalıntı baseline carry append-only). pytest CI
baseline transition: **676 PASS + 8 skip → 675 PASS + 9 skip** post-Wave-2
plugin.json 1.1.0 → 1.3.0 bump (expected: `test_git_tag_matches_plugin_json_when_present`
SKIPS because v1.3.0 git tag deferred Wave 4 Süleyman karar PRIVATE; ADR-036
invariant test guards by-design). DECISIONS.md **6112B unchanged** (no new ADR
added in v1.3 — ADR-036 sync invariant 5'inci uygulama; 32B headroom remaining
under 6144B hard cap ADR-026).

**Repo visibility deferred PRIVATE** per Süleyman karar 2026-05-07 — engine + workspace
both kalır PRIVATE. PUBLIC publication ileri tarihte ek session (Wave 3 marketplace
metadata + Wave 4 visibility toggle + git tag + GitHub release).

---

## Section 2 — Wave Summary (v1.1.0 → v1.3.0)

### v1.1-Integration-Audit (read-only, 2026-05-06)
- 0 atomic engine commit; 8 workspace deliverable in
  `outputs/audits/v1.1-integration-audit/` (~74KB total)
- 4-Wave methodology (manifest scan + MCP coverage + cross-reference + executability)
- 28 raw findings (26 unique post-deduplication) → 5 P1 OQ filed + 4 P2 + 2 P3 +
  15 INFO
- pytest 673 PASS UNCHANGED (audit read-only)

### v1.2-Phase-A (audit followup, 1 atomic, 2026-05-06)
- `6497ef4` — 4 trivial v1.1 audit findings RESOLVED

### v1.2-Phase-B (audit followup, 4 atomic, 2026-05-06)
- `b1c64dc` — Wave 1: 3 fix combined (generate-images events_writer +
  schema-validate cite + rules canonical example)
- `64c7177` — Wave 2: events-writer Section 4 expand 47% → 100% coverage
  (3 sub-table 4a/4b/4c filesystem-true)
- `6ba6aaa` — Wave 3: monitoring-weekly inline orchestration audit-event
- `b321a0f` — closeout: 3 OQ RESOLVED + ledger advance

**Outcome:** 10/11 findings RESOLVED. pytest 673 PASS + 3 skip stable.

### Cleanup + F-16 + Q-RP-01 batch (8 atomic, 2026-05-06)
- `5f9226c` — 6 audit briefs archive (Phase 15 W1-W5 + v1.1-integration-audit)
- `82d9476` — 43 skill status promote `wip` → `active`
- `d94ae9c` — master_task primary_source enum 10 → 11 (+`new_content_plan`,
  Q-V1.2-MASTER-TASK-PRIMARY-SOURCE-01 RESOLVED)
- `22cba80` — F-16 defensive URL extraction
  (Q-V1.2-OPP-COVERAGE-01 RESOLVED, schema-first override 17'inci uygulama)
- `767652e` — ADR-004 + ADR-005 closure post-soak (2 eski repo silindi ~1.6GB)
- `da9653f` — Q-RP-01 RESOLVED — 8 reporting skills audit event emit

**Outcome:** **13/13 v1.x audit findings RESOLVED** + 1/14 deferred (P3 catalog
Phase 16+). 2 ADR closed post-soak. pytest 681 PASS + 3 skip workspace-bound dev.

### v1.3-Ergonomi-Batch (1 atomic + closeout, 2026-05-06)
- `bc7b909` — 6 yeni commands: `/pseo-new-blog` + `/pseo-monitoring-weekly` +
  `/pseo-whats-next` + `/pseo-schema-audit` + `/pseo-cannibalization` +
  `/pseo-content-decay` + marketplace.json description sync
- 9 → 15 slash commands transition (palette ergonomi expansion)

**Outcome:** Süleyman ergonomi VS Code Claude Code kısa yol; 6 en sık kullanılan
skill'e doğrudan erişim. pytest 676 PASS + 8 skip CI baseline.

### v1.3-Audit-Fix-Wave-0 (1 atomic + closeout, 2026-05-06)
- `08e181d` — 3 KRİTİK runtime drift fix:
  - F-1: `pseo-driftcheck.md` broken `drift_report.py` ref →
    `validate_invariants.build_consistency_report()` + `render_template.py`
  - F-2: `scrapling-ops/SKILL.md` `/pseo-scrapling` → `/pseo-scrape`
    (description + manual 2-satır)
  - F-3: `pseo-monthly.md` Section 2 4-sheet → 9-sheet sync skill consumes ile
    birebir + events.jsonl write iddiası kaldır + READ-ONLY note

**Outcome:** Audit cross-check (Lesson 38 v2 + Lesson 67 stacked enforcement
15'inci ardışık vaka) → 3 KRİTİK runtime FAIL risk yakalandı + fix.

### v1.3-Marketplace-Publication-Brief-Authoring (1 atomic, 2026-05-06)
- `8ff8b88` — `docs/superpowers/plans/v1.3-marketplace-publication-brief.md`
  (371 satır, 5-wave methodology)

### v1.3-Audit-Fix-Wave-2 (1 atomic + closeout, 2026-05-07)
- `bd70477` — 5 sub-critical drift sync:
  - F-4: `pseo-quickwin.md` defaults 90/8-20 → 28/11-20 skill canonical +
    Section 2 sheet sync `gsc_landing_query` → `gsc_performance` + opportunity
    10 col schema-locked
  - F-5: `pseo-dfs-pull.md` argument-hint genişlet (`--cluster` + `--location-code`
    + `--language-code`)
  - F-6: `pseo-scrape.md` argument-hint (`--scenario` + `--max-urls` Phase 7+
    routing tag)
  - F-7: 3 command Section 4 optional MCP listele (`mcp__gsc__list_sites` init +
    `mcp__gsc__index_inspect` gsc-pull + `mcp__dataforseo__historical_keyword_data`
    dfs-pull)
  - F-8: `pseo-quickwin.md` Section 4 MCP isim açık (detect_quick_wins +
    enhanced_search_analytics + index_inspect explicit)

**Outcome:** **8/8 v1.3 audit finding RESOLVED** (3 KRİTİK Wave 0 + 5 sub-critical
Wave 2). Lesson 38 v2 + Lesson 67 stacked 16'ıncı ardışık vaka.

### v1.3-Marketplace-Publication-Wave-1 (this release, 1 atomic, 2026-05-07)
- `1b8e61d` — pre-publication security audit:
  - `check_secrets.sh` 3 FP exclude path eklendi
    (test_events_writer.py + test_ci_yaml.py + OPEN_QUESTIONS.md)
  - `check_secrets.sh` ENV_FILES gitignore-aware logic refactor
    (.env gitignored ise WARN, değilse FAIL)
  - `tests/skills/test_{sf_import,quick_wins,init_project}.py`:
    `WORKSPACE_STAGING` absolute path → env-aware
    (`PSEO_WORKSPACE_STAGING` env var fallback `Path.home()`)
  - `.gitignore`: `.claude/settings.local.json` defensive entry
  - Q-PHASE15-SECRETS-FP-01 RE-OPENED + RE-RESOLVED
    (2026-05-06 closure documentation drift catch)

**Outcome:** drift sıfır pre-publication state hijyen. check_secrets.sh EXIT 0 +
pytest 676 PASS + 8 skip baseline UNCHANGED + tests/skills/ absolute path leak
0 grep hit. Lesson 38 v2 + Lesson 67 stacked 17'inci ardışık vaka.

---

## Section 3 — Architectural Decisions

**No new ADR added in v1.3.0** (governance polish only). DECISIONS.md **6112B
unchanged**, **6112/6144B held** (32B headroom; memory drift caught Wave 1 Lesson
38 v2 17'inci ardışık vaka — banner stale claim 6027B invalidated by `wc -c`
runtime). Active 2 (ADR-037 + ADR-038).

### ADR closures post-v1.1.0
- **ADR-004** (Eski repo silme: v1 acceptance + 1 hafta soak) — closed
  2026-05-06 post-soak; 2 eski repo silindi (~1.6GB)
- **ADR-005** (Workspace repo timing: Phase 14, user-created) — closed
  2026-05-06; Phase 14 condition met

### ADR-036 sync invariant uygulama
v1.3.0'da **5'inci uygulama** kümülatif:
1. v1.1.0 ilk tam uygulama (`27b6010` Wave 3 Task 3.4)
2. v1.3 ergonomi marketplace.json description sync
3. v1.3 audit-fix-wave-0 marketplace.json description sync
4. v1.3 audit-fix-wave-2 marketplace.json description sync
5. **This release: plugin.json + marketplace.json + README + INSTALL +
   RELEASE_NOTES_v1.3.0.md uniform 1.3.0**

---

## Section 4 — Test + Invariant Delta

| Property | v1.1.0 | v1.3.0 | Delta |
|---|---|---|---|
| pytest baseline | 673 PASS + 3 skip | **675 PASS + 9 skip** (post-Wave-2 plugin.json bump) | +2 PASS, +6 skip |
| CI strict mode | 7/7 steps | **8/8 steps** (events-schema-sanity added) | +1 step |
| drift-check verdict | AMBER (final) | **AMBER held** | unchanged |
| .mcp.json | 469B (Wave 3 baseline) | **482B byte-byte korundu** | +13B (npm pin baseline post-Phase-15) |
| DECISIONS.md | 6027/6144B (cycle 19+20+21 claim) | **6112/6144B held** (memory drift caught Wave 1) | runtime correction |
| Slash commands | 9 (production) | **15** (9 + 6 ergonomi) | +6 |
| Skills | 43 (`status: active`) | 43 (status sweep stable) | unchanged |
| MCP servers | 3 plugin + 1 user-level | 3 plugin + 1 user-level | unchanged |

**F-16 invariant** (.mcp.json byte-byte): **26+ commit cumulative korundu** v1.3
milestone boyunca. Plugin agnostik discipline: **0 slug literal grep** v1.3
milestone boyunca.

---

## Section 5 — Upgrade Notes

For users on v1.1.0:

1. `git pull` engine.
2. Re-run `/plugin add` (plugin.json version bumped 1.1.0 → 1.3.0; 6 yeni
   command palette'de görünür).
3. **No env var migration required** — all v1.1 contracts intact;
   `PSEO_WORKSPACE_ROOT` canonical, `PSE_WORKSPACE_PATH` 1y shim active until
   2027-05-06.
4. **No schema migration required** — all v1.1 schemas backwards-compatible
   additive only.
5. **Optional:** `PSEO_WORKSPACE_STAGING` env var (Wave 1 introduced) for test
   suite local-only fixtures; defaults to
   `~/Documents/platinum-seo-workspace-staging` if unset.

**No breaking changes** for skill / command / script callers. v1.3 ergonomi
expansion adds 6 new commands but does not modify existing 9.

---

## Section 6 — Outstanding (deferred)

### Wave 3+ marketplace publication (deferred Süleyman karar 2026-05-07)
- **Wave 3:** marketplace install snippet + metadata
- **Wave 4:** repo visibility PRIVATE → PUBLIC + v1.3.0 git tag + GitHub release page

These deferred — Süleyman PRIVATE kalsın kararı engine + workspace ikisi de.
Brief baseline (`8ff8b88` 371 satır) + this release notes hazır. PUBLIC açıldığında
ek session ~20 dk (Wave 3+4 atomic).

### Other deferred (v1.4+ candidate)
- **Multi-project capability test** — yeni proje onboard pipeline e2e (~120 dk
  ayrı session)
- **Süleyman ek feature backlog** — TBD
- Q-PHASE15-CTXLEDGER-01 (CONTEXT_LEDGER size compression strategy, LOW)

---

## Section 7 — Acknowledgments

Süleyman feedback enforce throughout v1.3 milestone: **"çok titiz çalışmanı
istiyorum cross checksiz ilerleme"** — sürekli runtime cross-check her edit'te
enforce default; her wave-end'de runtime grep verify zorunlu.

**Lesson 38 v2 + Lesson 67 stacked enforcement** (cumulative):
- 15'inci ardışık vaka post-v1.3-ergonomi (Wave 0 audit cross-check)
- 16'ıncı ardışık vaka post-Wave-0 (Wave 2 audit cross-check)
- **17'inci ardışık vaka** post-Wave-2 (this Wave 1 marketplace-publication —
  OQ closure regression catch via runtime grep)

**Atomic phase paterni 36'ıncı kanıt** 39 phase consecutive convergent invariant
intact:
Phase 7..15 + v1.1-Wave-1+2+3 + v1.1-Integration-Audit +
v1.1-Audit-Followup-Phase-A + v1.2-Phase-B + Cleanup 1+2 + Status Promote +
#2 schema + #1 F-16 + ADR closure + Q-RP-01 + v1.3-ergonomi +
v1.3-audit-fix-wave-0 + v1.3-marketplace-brief + v1.3-audit-fix-wave-2 +
**v1.3-marketplace-publication-wave-1**.

**Cross-Audit Metodoloji** (Codex + Opus 4.7) v1.1.0'dan v1.3.0'a kümülatif:
- External fresh-eye audit (Codex paralel) — v1.1.0
- Internal cross-verification (Opus 4.7) — v1.1.0+
- Manager pre-dispatch full-file inspect (Lesson 38 v2) — 17 ardışık vaka
- Manager self-correction (Lesson 67) — 17 stacked enforcement

Future v1.4+ release cycle template intact.
