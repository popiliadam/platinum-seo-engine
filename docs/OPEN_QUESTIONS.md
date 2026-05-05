# Open Questions

## Unresolved

### Q-W3W2C-A-LAYOUT-01: master.xlsx duplicate header row Workspace W1 bootstrap (Q-W3W2B-LAYOUT-01 paterni reuse) [MEDIUM]
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-a worker output (W-N1 drift-check post-W3-W2-C-a verify, drift-check helper schema authority dynamic + row 1 fallback ile layout'la yaşıyor)
**Context:** Workspace W1 bootstrap master.xlsx duplicate header row (row 1 + row 3/4/5 both header). W3-W2-C-a fix `validate_invariants.py` `_resolve_header_row()` helper schema authority dynamic + row 1 fallback (probe match yoksa) ile layout'la birlikte yaşıyor. 4 mekanik header-parse FAIL eliminate (F-01+F-05+F-17+F-18). Q-W3W2B-LAYOUT-01 + Q-DC-LAYOUT-01 paterni reuse — duplicate header row layout normalize ayrı scope.
**Options:**
- a) `transaction.consolidate_headers(sheet)` helper + master.xlsx normalize once-off (single header row schema metadata değer + data row +1, idempotent + .bak backup)
- b) `scripts/state/normalize_master_xlsx.py` CLI tool (Phase 15 audit run) — schema-driven layout convention enforce
- c) Mevcut layout kabul + helper logic invariant (W3-W2-C-a fix paterni production-ready, helper schema authority dynamic + row 1 fallback)
- d) Phase 15 audit Wave 1 layout normalize ADR aday formal decision Süleyman + karar verici layout migration vs helper flexibility tradeoff
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check core finding)
**Blocking Phase:** None (non-blocking, drift-check helper schema-aware production-ready, layout normalize Phase 15 audit scope)

### Q-W3W2C-A-DICTNAME-01: required_columns dict access patterni rules/schema-validation.md codify [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-a worker output (W-N1 Step 0 fix surface)
**Context:** master-excel.schema.json `required_columns` array entries dict objects (`{col, name, ref, enum}`) — string değil. Eski F-05'te `len(required)` çalışıyordu ama header set comparison kırıktı (`str(c)` literal dict string set'e giriyordu, probe match imkansızdı). W3-W2-C-a fix `_col_name()` extract ile düzeltildi → schema authority dynamic ÇALIŞIR. Future schema validators rules codify aday: schema validators'ın `required_columns` dict access patterni standart convention.
**Options:**
- a) `rules/schema-validation.md` (yeni rule R-XX yeni dosya) — schema validators dict access patterni convention single rule + Foundational Principles bağlantı
- b) Mevcut `rules/skill-description-discipline.md`'e R-XX additive bump — schema validation sub-section ek
- c) `templates/schema-validator-template.md` placeholder (her yeni schema validator başlangıçta convention scaffolding)
- d) Phase 15 audit defer (mevcut W3-W2-C-a `_col_name()` extract local pattern v1 release acceptable, post-v1 ADR aday)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check)
**Blocking Phase:** None (non-blocking, governance polish W3-W3 closure veya Phase 15 audit scope)

### Q-W3W2C-A-F13F16-01: F-13 historical non-int run_id + F-16 quick_wins URL coverage gap gerçek data drift [MEDIUM]
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-a worker output (W-N1 drift-check post-W3-W2-C-a verify RED 15/2/3, hala RED F-13+F-16 non-mekanik)
**Context:** drift-check post-W3-W2-C-a fix verdict RED 15/2/3 (4 mekanik header-parse FAIL eliminate F-01+F-05+F-17+F-18 ✓), hala RED çünkü: F-13 (5 historical non-int run_id, baseline carry-forward W3-W2-A append-only protected mop-up imkansız lesson 47 5'inci kategori) + F-16 (36 quick_wins URL not in opportunity, gerçek data drift mekanik değil). Bunlar W3-W2-C-a scope dışı — F-13 historical events.jsonl repair migration; F-16 opportunity sheet expansion (quick_wins URL coverage). Phase 14 W3-W2-C-b veya Phase 15'te addressed.
**Options:**
- a) F-13 historical events.jsonl repair migration script (`scripts/migrations/0003_events_run_id_repair.py`) — 5 manual events run_id integer field backfill, append-only YASAK (R-XX hard constraint) → migration semantik dışı, defer
- b) F-13 events.schema run_id nullable additive bump — historical state acceptable, schema_version bump (1.x patch)
- c) F-16 opportunity sheet expansion W3-W2-C-b production scope (yeni opportunity row'lar ile quick_wins URL coverage)
- d) F-16 cross-sheet-invariants F-16 rule "by-design URL divergence" exception flag (kabul markırı, drift-check F-16 status PASS yerine WAIVE)
- e) Phase 15 audit Wave 1 kategori #2 birleşik scope karar (Q-W3W2B-LAYOUT-01 + Q-DC-LAYOUT-01 + F-13/F-16 layout + data drift hepsi paralel ADR)
**Owner:** karar verici agent (Phase 14 W3-W2-C-b production scope veya Phase 15 audit Wave 1)
**Blocking Phase:** None (non-blocking, drift-check verdict RED dikkat çekici ama mekanik değil real data drift bilinçli kabul append-only protected)


### Q-W3W2B-EVENTTYPE-01: events.schema event_type 10-closed-enum vs 13 skill-named ihtiyaç [MEDIUM]
**Raised:** 2026-05-05 during Phase 14 W3-W2-B manager pre-dispatch finding F-14W3W2B-1 + worker output (W-M1 schema-first override 11'inci uygulama)
**Context:** Brief Section 3 Step 1-13 `event_kind=work + event_type=<skill_name>` literal yazılmıştı 13 farklı value (cannibalization → content_revise + tech_audit + on_page_audit + content_gaps + schema_audit + competitive_analysis + geo_analysis + cluster_map + topical_map + new_content_plan + internal_links + master_task_sync), AMA events.schema.json event_type 10-closed-enum (content_new + content_revise + content_improve + content_remove + template_apply + scrape_run + audit_run + budget_event + sync_run + manual). Manager pre-dispatch 14-boyutlu Section 8 boyut #5 enum kontrol etti master_task primary_source 10-enum + content_type 6-enum AMA events event_type 10-enum cross-check ATLANDI = lesson 28 v3 4'üncü kategori "manager self-failure catch" 2'inci uygulama. Worker schema-first override 11'inci uygulama: 14 work event `event_type=manual` + note=`[skill=X] event_type_intent=Y` + task_id auto-allocated `T-1001..T-1014` (`^T-[0-9]{4,}$` pattern). W3-W3 schema patch veya rules/events-writer.md codify Q-DC-RUNID-01 birleşik scope.
**Options:**
- a) events.schema event_type enum additive bump (+13 skill-named values: cannibalization + content_decay + tech_audit + on_page_audit + content_gaps + schema_audit + competitive_analysis + geo_analysis + cluster_map + topical_map + new_content_plan + internal_links + master_task_sync) — Phase 14 W3-W3 schema patch ADR, schema_version bump, mevcut 10 enum geri uyumlu
- b) `rules/events-writer.md` (yeni rule R-XX yeni dosya) codify — `event_type=manual + note[skill=X] event_type_intent=Y` paterni mandatory skill-level work events için (W3-W2-B run paterni convention authority) + `next_run_id` helper Q-DC-RUNID-01 birleşik scope
- c) Hybrid: schema event_type genişletme + rules/events-writer.md codify (her iki layer)
- d) Phase 15 audit defer (W3-W2-B run paterni acceptable, post-v1 ADR aday)
**Owner:** karar verici agent (Phase 14 W3-W3 closeout scope, Q-DC-RUNID-01 birleşik resolution)
**Blocking Phase:** None (non-blocking, governance polish W3-W3 closure)

### Q-W3W2B-WRITER-01: non-master_task sheets writer registry codify [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W2-B worker output (W-M1 transaction.update writer surface)
**Context:** master_task.allowed_writers includes `master_task_sync` exact string — orchestrator passes `writer="master_task_sync"` correctly. Other sheets (cannibalization/content-decay/tech-audit/etc.) pass arbitrary writer strings which `transaction._check_writer_scope` ignores when `allowed_writers is None`. Cross-sheet-invariants 20 rule registry'de allowed_writers field ardından non-master_task sheets için writer registry tanımı eksik — convention kayboluyor. Phase 15 audit Wave 2 kategori #9 (workspace data integrity) writer registry codify aday.
**Options:**
- a) `master-excel.schema.json` her sheet için `allowed_writers` array additive bump (cannibalization, content_decay, tech_audit, etc. her biri kendi skill-name string'ini hold) — Phase 15 audit ADR
- b) Mevcut `cross-sheet-invariants.json` `rules` array'a per-sheet writer registry rule additive bump
- c) `transaction.update` API hardening: allowed_writers None'sa warning emit (skill writer convention discovery)
- d) Phase 15 audit defer (mevcut skill-name string'leri events.jsonl provenance trail'de kayıt ediliyor + W3-W2-B run paterni acceptable, low priority)
**Owner:** karar verici agent (Phase 15 audit Wave 2 kategori #9)
**Blocking Phase:** None (non-blocking, low priority writer registry)

### Q-DFS-MCP-01: DataForSEO MCP wrapper `location_name` field reject (TR market gap, v1 release blocker aday) [HIGH]
**Raised:** 2026-05-05 during Phase 14 W3-W2-A worker output (W-L1 surface, dfs-pull skill execution)
**Context:** DataForSEO MCP wrapper `location_name` field reject `dataforseo_labs_google_keyword_ideas` + `dataforseo_labs_google_ranked_keywords` çağrılarında, schema declarative ama wrapper ihlali. Sonuç: keyword_ideas US default (English) döndü TR market keyword'ları gelmedi + ranked_keywords empty. Pilot demo-dental (TR-tr) için kritik data quality gap. Workaround: `location_code 2792` + `language_code "tr"` parametre kombinasyonu denendi ama wrapper consume etmedi. Phase 14 W3-W2-A 4 ingest skill arasında dfs-pull bu nedenle eksik TR market coverage ile shipped (cluster_keywords + opportunity 300+150 row populate ama TR specificity belirsiz).
**Options:**
- a) `schemas/` repo `dataforseo-mcp.schema.json` patch — `location_name` field schema declarative ama wrapper accept ediyor olduğunu validate, runtime test add
- b) MCP wrapper kendisinde patch (engine'in kontrolünde değilse: paket-spec env naming convention veya GitHub issue raise upstream)
- c) Skill `dfs-pull` body Python block `location_name` removal + `location_code 2792` + `language_code "tr"` zorunlu workaround
- d) Phase 14 W3-W3 closure'da TR market keyword reset + dfs-pull re-run (W3-W2-A data partial valid kabul)
**Owner:** karar verici agent (Phase 14 W3-W3 v1 release blocker triage, Süleyman onayı kritik)
**Blocking Phase:** Phase 14 W3-W3 v1 release blocker aday (TR market data quality v1 release tag öncesi resolve)

### Q-DC-RUNID-01: Manual events `run_id` field eksik convention codify
**Raised:** 2026-05-05 during Phase 14 W3-W2-A worker output (W-L1 drift-check F-13 surface)
**Context:** Phase 14 W3-W2-A 4 ingest skill execution sırasında 5 manual events.jsonl direct dict construction yapıldı, `run_id` integer field eksik bırakıldı. transaction.append auto-emit edilen event'lerde `run_id` mevcut (lesson 21 paterni), ama manuel events_writer çağrısında `next_run_id(project_slug)` helper kullanılmamış. Drift-check F-13 5 event run_id missing fail. Mop-up imkansız: events.jsonl mutate = R-XX append-only state Süleyman global feedback_hard_constraints ihlali (lesson 28 v3 5'inci kategori "append-only invariant protected drift defer" doğum belgesi). Convention codify gerekli future skill execution'larında prevention.
**Options:**
- a) `rules/events-writer.md` (yeni rule R-XX yeni dosya) — manual events `next_run_id` helper kullanımı zorunlu single rule + 4 event_kind (work/audit/provenance/workflow) için per-kind run_id semantic
- b) Mevcut `rules/append-only-state.md`'ye R-XX additive bump — events run_id sub-section ek
- c) `scripts/state/events_writer.py` API hardening — `append()` veya `add_event()` direct dict construction yerine helper-only path enforce (raises if run_id missing)
- d) Phase 15 audit'a defer (mevcut 5 manual event drift kabul edilir, future skill writers convention discover edecek)
**Owner:** karar verici agent (Phase 14 W3-W3 backlog non-blocking)
**Blocking Phase:** None (non-blocking, drift-check F-13 sonuç bilinçli kabul)


### Q-DC-VERDICT-01: drift-check `aggregate_verdicts` UNKNOWN behavior when FAILs > 0 [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W2-A worker output (W-L1 drift-check report inspect)
**Context:** drift-check skill `aggregate_verdicts` overall_verdict=UNKNOWN when FAILs > 0 (Phase 14 W3-W2-A consistency-report.json verdict field=RED but aggregate UNKNOWN). Implementation behavior question: UNKNOWN when AMBER mix vs FAIL when any critical FAIL? Phase 14 W3-W1 governance skill body refactor production-ready ama bu specific behavior dokümante değil. Phase 15 audit implementation question.
**Options:**
- a) drift-check skill `aggregate_verdicts` logic change — FAILs > 0 → overall_verdict=FAIL (strict)
- b) UNKNOWN korunur — domain natural ("incomplete picture" semantik, partial PASS mix kabul)
- c) Verdict enum bump — `aggregate_unknown` separate value
- d) Phase 15 audit document — implementation existing behavior + rationale codify (no code change)
**Owner:** karar verici agent (Phase 15 audit implementation question)
**Blocking Phase:** None (non-blocking, low priority semantic)

### Q-016: audit_action enum mapping (Edit/Write/Bash → modified/accessed)
**Raised:** 2026-04-30 during Phase 4 W-N (post-tool-use.json hook)
**Context:** events.schema audit_action enum 6 değer (created, modified, deleted, accessed, permission_changed, config_changed). post-tool-use hook tüm tool'larda (Edit/Write/Bash) `accessed` flatten ediyor — semantik kayıp (Edit/Write → `modified` olmalı). One-liner sıkışıklığı tradeoff.
**Options:**
- a) Tool isimine göre per-tool mapping (Edit/Write → modified, Bash → accessed) — hook one-liner büyür
- b) audit_action enum'a `tool_invoked` jenerik değer ekle — schema bump
- c) Phase 14+ governance refinement'a defer (mevcut audit trail completeness yeterli, semantik upgrade later)
**Owner:** karar verici agent (Phase 14+ pre-dispatch)
**Blocking Phase:** None (non-blocking, governance polish)

### Q-RP-01: reporting events.jsonl audit-worthiness (rapor üretme audit-worthy event mi?)
**Raised:** 2026-05-01 during Phase 9 Wave 1 closeout (W-D1 fiili pattern + operation enum constraint cross-check sırasında ortaya çıktı)
**Context:** 4 reporting skill (monthly-report + weekly-summary + portfolio-overview + portfolio-weekly-brief) Wave 1'de events.jsonl YAZMAMA paterni ile shipped — W-D1 master-task-sync (1095L scan-confirmed) fiili paterni reuse. operation field schema enum 5 değer ("PROVENANCE-only" description: ingest/normalize/project_excel/validate/cascade_done) + reporting bunlardan hiçbirine semantik tam karşılık değil. Karar: events.jsonl write atla (Seçenek C), Phase 14 governance refinement'a defer. Sorun: "rapor üretme" eylemi audit trail'de görünmüyor — gelecek pilot smoke test sonucu işe yarar mı (re-run dedup, kim ne zaman rapor çekti) sorusu açık.
**Options:**
- a) events.jsonl event_kind=audit + audit_action="read" + audit_target="master.xlsx" + actor="reporting-skill:{name}" — schema-pure, governance kategorisi semantik doğru, Wave 2 + sonraki reporting skill'ler için convention lock
- b) events.schema operation enum additive bump (+ "report_generation" veya + "aggregate") — Phase 14 ADR-aday, schema_version bump, mevcut 5 enum geri uyumlu
- c) Phase 14+ governance refinement'a defer mevcut karar (LOCAL aggregation audit trail'e değmez assumption)
- d) Reporting-specific audit log (outputs/reports/_audit.jsonl ayrı dosya) — events.jsonl scope'u dışı, ayrı convention
**Owner:** karar verici agent (Phase 14+ pre-dispatch, pilot smoke test deneyimi sonrası)
**Blocking Phase:** None (non-blocking, governance polish; Wave 2 + Phase 9 closeout aynı paterni reuse — defer kararı geçerli)

### Q-CI-W3-01: skill-body-executability Convention Codify (sys.path.insert pattern rules/skills.md)
**Raised:** 2026-05-05 during Phase 14 W3-W1 worker output (W-K1 surface, lesson 21 4'üncü uygulama)
**Context:** Phase 14 W3-W1 worker proaktif decision: `sys.path.insert(0, os.getcwd())` 4 governance SKILL.md 1. Python block injection brief'te öngörülmemişti (helper subprocess tempfile cwd vs PYTHONPATH gap → `from scripts.state import events_writer` ModuleNotFoundError fix). Worker 4 skill identik convention uyguladı (drift-check + schema-validate + glossary-audit + load-context). Currently 4-skill local pattern, future skill authors re-discover edecek riski → cross-skill convention codify aday.
**Options:**
- a) `rules/skills.md` (yeni rule R-XX yeni dosya) — skill-body-executability convention single rule + Foundational Principles bağlantı (truth-verifiable üst-prensip alt-katmanı)
- b) Mevcut `rules/skill-description-discipline.md`'e R-XX additive bump — skill body executability sub-section ek
- c) `templates/skill-body-template.md` placeholder (her yeni skill başlangıçta convention scaffolding)
- d) Phase 14 W3-W3 v1 release closure'a defer (mevcut 4-skill local pattern v1 release acceptable, post-v1 ADR-aday)
**Owner:** karar verici agent (Phase 14 W3-W2 brief writing, pilot E2E sırasında yeni skill türetilmiyorsa W3-W3 defer aday)
**Blocking Phase:** None (non-blocking, governance polish)

### Q-CI-W3-02: Helper Auto-Prepend sys.path.insert (Boilerplate Eliminate)
**Raised:** 2026-05-05 during Phase 14 W3-W1 worker output (W-K1 surface, helper refactor scope)
**Context:** Phase 14 W3-W1 sonrası 4 SKILL.md 1.blokta `import os; import sys; sys.path.insert(0, os.getcwd())` boilerplate. Eğer helper `scripts/ci/run_skill_python.py` concat öncesi otomatik prepend yaparsa skill author boilerplate yazmaz (DRY). Trade-off: helper karmaşık + sihirli prepend implicit behavior; skill body explicit sys.path.insert açık + reader-friendly + skill-author-aware.
**Options:**
- a) Helper auto-prepend (DRY, helper karmaşık, ~5 satır eklenir, magic prepend) — skill author boilerplate yazmaz
- b) Skill body explicit korunur (mevcut state, 4 skill 5 satır toplam boilerplate) — magic-free, reader-friendly
- c) Hibrit: helper auto-prepend + skill body opt-out flag (`# helper:no-auto-sys-path`) — esneklik
- d) Phase 14 W3-W3 v1 release closure'a defer (mevcut state v1 release acceptable)
**Owner:** karar verici agent (Phase 14 W3-W2/W3-W3 helper refactor scope)
**Blocking Phase:** None (non-blocking, helper polish)

### Q-WS-02: README "Quick Start" engine plugin invocation convention (workspace → engine plugin nasıl invoke edilir?)
**Raised:** 2026-05-04 during Phase 14 W1 worker output (W-I1 surface)
**Context:** Workspace repo `README.md` "Quick Start" bölümünde "Engine plugin skill çalıştır" yazıyor, ancak workspace → engine plugin invocation convention v1 release closure'da netleşecek. Workspace pwd'si `~/Documents/platinum-seo-workspace/projects/demo-dental/` iken engine plugin skill'leri (`~/Documents/platinum-seo-engine/skills/...`) nasıl çağrılır? Plugin path lookup, env var (`PLATINUM_SEO_ENGINE_ROOT`?), Claude Code plugin auto-discovery, manuel invocation pattern'leri arasında karar gerek.
**Options:**
- a) Plugin path lookup env var (`PLATINUM_SEO_ENGINE_ROOT=~/Documents/platinum-seo-engine`) — workspace `.env` template'e eklenir, skill invocation `${PLATINUM_SEO_ENGINE_ROOT}/skills/...` (12-factor app convention, Higgsfield MCP user-level paterni reuse)
- b) Claude Code plugin auto-discovery — engine plugin user-level kayıt (`~/.claude/plugins/platinum-seo-engine/`), skill'ler global lookup (workspace pwd-agnostic) — Phase 4 plugin.json baseline schema'da `${CLAUDE_PLUGIN_ROOT}` placeholder paterni reuse
- c) Workspace `.claude/settings.json` plugin path explicit (`{"plugins": {"platinum-seo-engine": "~/Documents/platinum-seo-engine"}}`) — workspace-spesifik shared settings, repo-level
- d) Phase 14 W2 CI yaml domain'inde resolve (CI runner workspace + engine paths absolute, README quick start CI runner reference)
**Owner:** karar verici agent (Phase 14 W2 brief writing, CI yaml convention paralel)
**Blocking Phase:** Phase 14 W2 (CI pipeline) + Phase 14 W3 (pilot E2E smoke test) — non-blocking W1 deliverable, defer W2-W3 resolve



## Resolved (last 10 — moved to DECISIONS)
- **Q-W3W2B-LAYOUT-01 → Phase 14 W3-W2-C-a fix engine 7c83d30 (drift-check helper schema authority dynamic header_row resolve)** — 4 mekanik header-parse FAIL eliminate (F-01+F-05+F-17+F-18). validate_invariants.py `_resolve_header_row()` helper schema authority compile + row 1 fallback. Master.xlsx layout normalize ayrı scope (Q-W3W2C-A-LAYOUT-01 paterni reuse, Phase 15 audit Wave 1 ADR aday).
- **Q-DC-LAYOUT-01 → Phase 14 W3-W2-C-a fix engine 7c83d30 (drift-check helper schema authority dynamic + row 1 fallback)** — W3-W2-A surface + W3-W2-B reinforce + W3-W2-C-a resolve. drift-check skill body schema-aware production-ready. Layout normalize Phase 15 audit Wave 1 kategori #2 ayrı scope.
- **Q-CI-W2-01 → atomic commit ed6a40d (Phase 14 W3-W1)** — Governance skill body executability defer scope RESOLVED. 4 SKILL.md body refactor standalone-executable (drift-check 8 + schema-validate 7 + glossary-audit 7 + load-context 8 = 30 Python block helper concat exec EXIT=0 4/4 skill). Lesson 21 4'üncü uygulama worker proaktif `sys.path.insert(0, os.getcwd())` cross-skill convention. GitHub Actions Run 4 14/14 step SUCCESS Phase 14 ilk %100 GREEN run (W2 Run 2/3 Step 1+2+3 AMBER continue-on-error masks → W3-W1 sonrası gerçek runtime PASS). Strict mode (`continue-on-error: false`) geçiş W3-W3 closeout artık kanıtlanmış zemin. Q-CI-W3-01 + Q-CI-W3-02 yeni surface (sys.path convention codify + helper auto-prepend) Phase 14 W3-W2/W3-W3 backlog.
- **Q-CI-W2-06 → fix commit c522e9f** — Phase 14 W2 post-push CI runtime fix `requirements.txt` 4-line manifest (jsonschema + pytest + openpyxl + pyyaml). `actions/setup-python@v5 cache: pip` cache hash için manifest dosyası gerektirir. Lesson 8 v6 candidate doğum belgesi boyut #12 brief CI runtime requirements cross-check Phase 14 W3+ enforce 12-boyutlu.
- **Q-015 → ADR-025** — scrapling-output-mapping pattern dependency → templates/scrapling/.gitkeep yaratıldı, schema pattern korundu, sub-schemas Phase 7+ skill'lerle.

- **Q-001 → ADR-001** — Plugin repo yeri → `~/Documents/platinum-seo-engine/` rename.
- **Q-002 → ADR-002** — GitHub repo timing → Phase 0 sonu, user manuel açar.
- **Q-003 → ADR-003** — Pilot proje → **demo-dental**.
- **Q-004 → ADR-004** — Eski repo silme → v1 acceptance + 1 hafta soak.
- **Q-005 → ADR-005** — Workspace repo timing → Phase 14, user-created.
- **Q-006 → ADR-006** — LICENSE → **MIT** (Worker C default onaylandı).
- **Q-007 → ADR-007** — plugin.json baseline kabul; optional alanlar Phase 4'te validate.
- **Q-008 → ADR-008** — `state/`, `outputs/`, `inbox/` plugin repo'da YOK (workspace runtime sahibi).
- **Q-009 → ADR-009** — `templates/master-excel.xlsx` Phase 1'de `bootstrap_excel.py` ile schema'dan üretilir.
- **Q-010 → ADR-010** — Python 3.10+ onaylandı; Node bağımlılığı yok (INSTALL.md Phase 4'te düzeltilir).
