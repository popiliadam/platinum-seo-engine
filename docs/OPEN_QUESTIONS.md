# Open Questions

## Unresolved

### Q-W3W3β-TEST-01: test_ci_yaml.py semantic update vs name rename ayrımı [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W3-β W-Q1 worker output
**Context:** W-Q1 cascade fix `test_ci_yaml.py::test_continue_on_error_strict_mode_governance_steps` testi 3 strict+4 report-only logic'inden 7 strict logic'ine semantic update yaptı (set comparison defensive), AMA test ismi "governance_steps" suffix'i ile kaldı (artık tüm 7 step için geçerli, sadece governance değil). Diff surgical scope tutuldu. Phase 15 audit Wave 4 follow-up: rename `test_continue_on_error_all_steps_strict_mode` veya benzer.
**Options:**
- a) Phase 15 audit Wave 4 mop-up commit rename
- b) Defer indefinitely (semantic intent docstring'de açık, isim cosmetic)
- c) v1.1 polish scope
**Owner:** karar verici agent (Phase 15 audit Wave 4)
**Blocking Phase:** None (cosmetic naming, non-blocking)

### Q-W3W3β-CIHOOK-01: GitHub Actions security advisory hook false positive [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W3-β W-Q1 worker output
**Context:** W-Q1 ilk ci.yml line 52 edit denemesinde GitHub Actions security advisory hook (komut injection uyarısı) false positive olarak fired. Daha küçük context retry ile başarılı. Substring-pattern based trigger, gerçek injection riski yoktu. Phase 15 audit Wave 1 hooks/CI cross-check scope.
**Options:**
- a) Phase 15 audit Wave 1 hook trigger pattern audit (false positive minimize)
- b) Hook disable workflow (Süleyman tercihine göre)
- c) Defer (advisory only, blocking değil)
**Owner:** karar verici agent (Phase 15 audit Wave 1)
**Blocking Phase:** None (advisory only)

### Q-CI-W3-04: pytest local-only fixture marker convention codify [MEDIUM]
**Raised:** 2026-05-05 during Phase 14 W3-W3-β cascade fix (F-14W3W3β-4 manager self-failure catch transparency mode)
**Context:** Phase 14 W3-W3-β CI Run 12 Step 4 pytest 4 test fail (`test_quick_wins.py::test_happy_path_gsc_live` + `test_inbox_raw_json_saved` + `test_sf_import.py::test_tier1_14_validates` + `test_tier2_search_console_all_amber`). Root cause: testler LOCAL-ONLY fixture (workspace-staging path lokalde MEVCUT, CI ubuntu-latest YOK = environment divergence). Süleyman K3 Seçenek B onayı: `@pytest.mark.skipif(not WORKSPACE_STAGING.exists(), reason="...")` cascade fix uygulandı 4 test'e. Q-CI-W3-04 NEW: pytest local-only fixture marker convention uzun vade migration scope (Seçenek C: conftest.py 'local_only' marker register + ci.yml '-m "not local_only"' pattern, daha temiz mimari).
**Options:**
- a) Phase 15 audit Wave 1 kategori #5 test infrastructure scope codify rules/pytest-markers.md veya rules/skills.md ek section
- b) conftest.py `local_only` marker pytest.ini convention + ci.yml `-m "not local_only"` flag
- c) v1.1 polish scope (current skipif marker workable, codify ertelenir)
- d) Mevcut skipif marker pattern documentation only (no migration)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #5)
**Blocking Phase:** None (current skipif marker production-ready 7/7 GREEN, codify ertelenebilir)

### Q-W3W3α-EVENTSCHEMA-01: events.schema audit_run 10-enum cross-check yapılmadı [MEDIUM]
**Raised:** 2026-05-05 during Phase 14 W3-W3-α worker output (W-P1 rules/events-writer.md Section 4 monitoring-weekly satırı `audit_run` belirtti ama schema cross-check yapılmadı)
**Context:** W-P1 worker rules/events-writer.md Section 4 branch matrix per skill 22 row codify (event_type 10-closed-enum). monitoring-weekly satırı `event_kind=audit + event_type=audit_run` belirtti AMA events.schema.json `event_type` enum'unda `audit_run` mevcut mu doğrulanmadı (worker self-disclosure). Schema'da yoksa worker schema-first override (manual + note paterni) reuse gerekir. Phase 15 audit Wave 1 schema cross-check kategori #2 scope.
**Options:**
- a) events.schema.json event_type enum cross-check yapılır + `audit_run` yoksa schema additive bump (audit_run + content_revise_minor + ...)
- b) rules/events-writer.md Section 4 monitoring-weekly satırı `event_type=manual + note=[skill=monitoring-weekly event_type_intent=audit_run]` paterni reuse (worker schema-first override)
- c) Phase 15 audit Wave 1 schema cross-check kategori #2 scope birleşik resolve (Q-W3W2Cb-003 + Q-W3W2C-A-LAYOUT-01 paterni reuse)
- d) Phase 14 W3-W3-β closure scope schema patch ADR aday
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check core finding)
**Blocking Phase:** None (non-blocking, schema cross-check medium priority Phase 15 audit scope)

### Q-W3W3α-W2: events_writer.py::next_run_id helper module path doğrulanmadı [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W3-α worker output (W-P1 rules/events-writer.md Section 2 next_run_id helper invocation doğrulanmadı)
**Context:** W-P1 worker rules/events-writer.md Section 2 `scripts/state/events_writer.py::next_run_id(project_slug)` helper invocation codify etti ama module path doğrulanmadı (worker self-disclosure). Helper module workspace repo'da mevcut mı engine repo'da mı? Phase 14 W3-W3-β workspace scope verify aday — workspace `~/Documents/platinum-seo-workspace/scripts/state/events_writer.py` veya engine `scripts/state/events_writer.py` resolve gerek.
**Options:**
- a) workspace `~/Documents/platinum-seo-workspace/scripts/state/events_writer.py` mevcut mu verify + path doğru ise rules/events-writer.md korunur
- b) engine `scripts/state/events_writer.py` mevcut mu verify + workspace'te yok ise plugin invocation pattern path expansion
- c) Phase 14 W3-W3-β workspace scope smoke test (helper exec doğru module path resolve)
- d) Phase 15 audit defer (low priority module path verification post-launch acceptable)
**Owner:** karar verici agent (Phase 14 W3-W3-β workspace scope verify)
**Blocking Phase:** None (non-blocking, low priority module path verification W3-W3-β workspace scope)

### Q-W3W2Cb-003: master_task task_id pattern (MT-W3W2B-001) does NOT match events.schema regex [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-b worker output (W-O1 Step 7 mark-done schema-first override branch surface)
**Context:** Existing master_task task_id values (e.g. `MT-W3W2B-001`, `MT-W3W2B-002`) created during Phase 14 W3-W2-B do NOT match the events.schema `^T-[0-9]{4,}$` regex pattern that mark-done expects. Worker created new task_id values `T-10001..T-10004` matching the schema, but pre-existing W3-W2-B drift remains. Convention codify aday: rules/master-task-id.md or master-excel.schema task_id pattern reference.
**Options:**
- a) `rules/master-task-id.md` (yeni rule R-XX yeni dosya) — task_id pattern convention codify single rule + master-excel.schema task_id field reference
- b) Mevcut `master-excel.schema.json` master_task.task_id "pattern" field additive (additive bump, schema_version) — `^T-[0-9]{4,}$|^MT-[A-Z0-9]+-[0-9]{3,}$` 2-pattern union (transitional)
- c) Bulk migration script — `MT-W3W2B-XXX` task_ids → `T-NNNNN` rename (master_task + master_task_sync history events.jsonl reference cascade fix)
- d) Phase 15 audit Wave 1 layout normalize ADR aday (cumulative pre-existing drift catch)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check)
**Blocking Phase:** None (non-blocking, low priority pre-existing drift)

### Q-W3W2Cb-004: drift-check F-17 regression — redirect_404.action='301' value not in severityEnum 4-value (rule scope collision) [LOW]
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-b worker output (W-O1 Step 9 drift-check post-W3-W2-C-b verify surface)
**Context:** drift-check post-W3-W2-C-b verdict regressed from RED 15/2/3 → RED 14/2/4 (Δ -1 PASS, +1 FAIL F-17 mechanical regression). F-17 rule scans `severity` columns for 4-value enum (LOW/MEDIUM/HIGH/CRITICAL), but `redirect_404.action` column was scanned (value '301' fails enum check). Schema authority cross-check needed: F-17 rule scope is per-sheet specific or generic-column-name? Rule scope kolizyonu, gerçek data drift değil — mekanik regression.
**Options:**
- a) `validate_invariants.py` F-17 rule scope tightening — per-sheet `severity` column allow-list (cannibalization.severity + on_page_audit.severity + redirect_404 EXCLUDED) — rule scope explicit
- b) `cross-sheet-invariants.json` F-17 rule clarification — schema authority `severity` column reference list explicit (master-excel.schema.json severityEnum referans sheets only)
- c) `redirect_404` schema rename action column → `http_status` (semantik doğru, action confusing) — schema_version bump
- d) Phase 15 audit Wave 1 implementation question codify (drift-check rule scope semantic codify aday)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #5 schema cross-check + drift-check implementation)
**Blocking Phase:** None (non-blocking, mekanik regression bilinçli kabul, gerçek data drift değil)

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
- **Q-W3W3α-W1 LOW → Phase 14 W3-W3-β in-wave RESOLVED via W-Q1 worker proaktif cascade (engine `568f9bb`)** — `tests/ci/test_ci_yaml.py::test_continue_on_error_strict_mode_governance_steps` 3 strict+4 report-only conditional logic → 7 strict set comparison defensive logic redesign. Lesson 21 9'uncu ardışık production-ready cross-skill convention worker proaktif scope expansion (brief minimum scope ÖTESİ Q-W3W3α-W1 pre-authorize'dan yararlanan cascade). Test ismi semantic update yapıldı, name rename ertelenir Q-W3W3β-TEST-01 LOW (Phase 15 audit Wave 4 follow-up).
- **Q-DFS-MCP-01 HIGH → Phase 14 W3-W3-α RESOLVED via documentation engine `ba23eae` (schemas/dataforseo-endpoint-mapping.schema.json description note + dfs_pull.py 1073 satır INTACT live test 1835229 confirmed K3 minimal scope)** — TR market gap dataforseo-mcp-server@2.8.9 wrapper limitation kalıcı codify schema description note + workaround dfs_pull.py line 10 docstring + 331-347 detection logic + 412 retry + 470 _enforce_tr canonical paterni reference. schema_version 1.0 UNCHANGED additive text-only ADR-018 paterni reuse. dfs_pull.py 1073 satır INTACT regression riski 0.
- **Q-DC-RUNID-01 + Q-W3W2B-EVENTTYPE-01 birleşik → Phase 14 W3-W3-α RESOLVED engine `ba23eae` (rules/events-writer.md NEW 143 satır 5 section + worked example JSON)** — append-only invariant R-XX hard constraint + next_run_id helper enforcement + event_kind 4-enum ADR-020 + event_type 10-closed-enum branch matrix per skill 22 row + workflow_action 8-enum lifecycle ADR-019. Worker schema-first override 11'inci uygulama paterni codified (event_type=manual + note=[skill=X event_type_intent=Y] enum-dışı skill için).
- **Q-CI-W3-01 → Phase 14 W3-W3-α RESOLVED K1 engine `ba23eae` (rules/skills.md NEW 109 satır 4 section single-purpose lesson 21 4'üncü uygulama codify)** — Skill body 1. Python block ZORUNLU prefix paterni + standalone-executable convention helper run_skill_python.py concat exec compatibility + multi-line format spec KRİTİK semicolon-tek-satır kaçın substring-key detection respect + cross-references W3-W1 governance refactor 4 skill paterni reuse. Foundational Principles 3-layer bağlantı.
- **Q-CI-W3-02 → Phase 14 W3-W3-α RESOLVED engine `ba23eae` (scripts/ci/run_skill_python.py extract_python_blocks +10 satır substring-key auto-prepend)** — sys_path_marker = "sys.path.insert(0, os.getcwd())" multi-line format respect F-14W3W3α-4 manager pre-dispatch catch + duplicate prevention. test_run_skill_python.py 4 yeni test (test_auto_prepend_skips_when_marker_exists + test_auto_prepend_when_marker_missing + test_auto_prepend_multi_line_format_respect + test_no_prepend_for_empty_skill comprehensive coverage 610 PASS).
- **Q-CI-W3-03 → Phase 14 W3-W3-α SCOPE EXCLUDE arka plan resolved (W3-W2-A+B+Ca+Cb 4 phase boyunca runtime kanıt pytest -k "quick_wins or sf_import" → 16 passed 0 failed)** — Brief 4 pytest fail iddiası FROZEN ASSUMPTION manager pre-dispatch catch (lesson 28 v3 kategori 2 pre-emptive prevention 10'uncu uygulama). conftest.py skip GEREKSIZ scope exclude. Lesson 38 v2 5'inci ardışık enforcement reinforce frozen assumption YASAK runtime cross-check ZORUNLU.
- **Q-W3W2Cb-002 → Phase 14 W3-W3-α RESOLVED via documentation K2 engine `ba23eae` (skills/production/content-remediation/SKILL.md +45 satır "Canonical Drift Resolution" section)** — URL canonical mismatch detection GSC index_inspect coverage state DUPLICATE_REDIRECT/MOVED_PERMANENTLY + resolution branch matrix a/b/c (a duplicate via canonical action=redirect_deployed target=canonical_url Q-W3W2Cb-001 W3-W2-C-b in-wave RESOLVED paterni reuse + b canonical drift redirect target=primary_url R-91 Senaryo 1+3 + c manual review improve_routing event_type=manual) + cross-skill convention revise-content + verify-indexing + content-remediation cooperative resolution intra-wave investigation paterni.
- **Q-W3W2Cb-001 → Phase 14 W3-W2-C-b in-wave RESOLVED workspace 3bb7258 (Step 6 verify-indexing GSC inspect /main-page Google canonical = https://demo-dental.example/, page is duplicate redirect to homepage)** — Step 3 revise-content surfaced legitimacy question (-90% click drop /main-page), Step 6 verify-indexing index_inspect confirmed page is duplicate of homepage with Google-determined canonical = `/`. Step 3 revise-content plan rerouted to content-remediation skill next wave (action=redirect target=/). Lesson 21 7'inci ardışık production-ready cross-skill convention same-wave self-resolve positive drift paterni (intra-wave cross-skill investigation positive drift, 7 phase consecutive convergent invariant).
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
