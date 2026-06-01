# Architecture Decision Records — Archive

ADR-011 rotation kararıyla `DECISIONS.md`'den taşınmış eski kararlar. Append-only — buradan da silme yok. Yeni rotation cycle'ları en eski ADR'leri buraya taşır.

**Bu dosyadaki ADR aralığı:**
- ADR-001..ADR-005 (Phase 0 closeout paketi, 2026-04-30 — ilk rotation)
- ADR-006..ADR-008 (Phase 1 closeout paketi, 2026-04-30 — ikinci rotation)
- ADR-009..ADR-010 (Phase 2 closeout paketi, 2026-04-30 — üçüncü rotation, ADR-014 eşik revizyonu)
- ADR-011 (Phase 2 closeout final, 2026-04-30 — dördüncü rotation, ADR-014'ün ilk uygulaması; ADR-014 partial supersede)
- ADR-012 (Phase 3.1 closeout, 2026-04-30 — beşinci rotation cycle, ADR-016/017 eklendikten sonra >5KB tetikleyince)
- ADR-013 (Phase 3.1 closeout cycle 5+, 2026-04-30 — ADR-014 <5KB hard cap enforced; ADR-012 cut yetmediği için ek rotation)
- ADR-014/016/017/018 (Phase 3.2 PRE-FIX closeout, 2026-04-30 — altıncı rotation cycle, ADR-018..021 ekleme ile DECISIONS.md ~9.9KB tetiklenmesi sonrası agresif cut; gap-015 protected)
- ADR-019 (Phase 4 ADIM 3, 2026-04-30 — yedinci rotation cycle, ADR-022 numerik clarification ekleme ile DECISIONS.md 6368B tetiklenmesi sonrası en eski active cut)
- ADR-020 (Phase 5 önü, 2026-04-30 — sekizinci rotation cycle, ADR-023 .mcp.json kararı ekleme ile DECISIONS.md 6330B tetiklenmesi sonrası en eski active cut)
- ADR-021 (Phase 5 Wave 0, 2026-04-30 — dokuzuncu rotation cycle, ADR-024 hibrit dispatch + schema fix ekleme ile DECISIONS.md 6350B tetiklenmesi sonrası en eski active cut)
- ADR-022 (Phase 6, 2026-04-30 — onuncu rotation cycle, ADR-025 Q-015 templates/scrapling/ ekleme ile DECISIONS.md >6144B tetiklenmesi sonrası en eski active cut; ADR-026 cap-only supersede ile uyumlu, body byte-byte korunur)
- ADR-023 (Phase 7 closeout, 2026-05-01 — onbirinci rotation cycle, Phase 7 closeout ADR-027/028/029 ekleme ile DECISIONS.md hard cap tetiklenmesi sonrası en eski active cut)
- ADR-024 (Phase 7 closeout, 2026-05-01 — onikinci rotation cycle, ADR-027 transform size policy ekleme sonrası en eski active cut)
- ADR-025 (Phase 7 closeout, 2026-05-01 — onüçüncü rotation cycle, ADR-028+ADR-029 ekleme sonrası en eski active cut; templates/scrapling/S1_competitor_snapshot.schema.json W-B3 yarattı, ADR-025 implementation realize)
- ADR-026..028 (v1.1 P0 Wave 1, 2026-05-06 — ondördüncü rotation cycle, ADR-030..033 ekleme ile DECISIONS.md hard cap tetiklenmesi sonrası 3 en eski active cut; ADR-026 cap-only supersede entry korunur byte-byte)
- ADR-029 (v1.1 P0 Wave 1 Task 1.2, 2026-05-06 — onbeşinci rotation cycle, ADR-033 ekleme ile DECISIONS.md 6549B tetiklemesi sonrası en eski active cut)
- ADR-030 (v1.1 P0 Wave 1 Task 1.4, 2026-05-06 — onaltıncı rotation cycle, ADR-031 ekleme ile DECISIONS.md 6968B tetiklemesi sonrası en eski active cut; brand_identity rename detayı engine commit `7dc67ba` body'sinde de korunur)
- ADR-031..032 (v1.1 P1 Wave 2 Task 2.2, 2026-05-06 — onyedinci rotation cycle, ADR-034 ekleme ile DECISIONS.md 7367B tetiklemesi sonrası 2 en eski active cut; events.jsonl legacy archive detayı workspace commit `f8d8663` + active.json canonical detayı engine commit `3bec210` body'sinde de korunur)
- ADR-033 (v1.1 P1 Wave 2 Task 2.3, 2026-05-06 — onsekizinci rotation cycle, ADR-035 ekleme ile DECISIONS.md 7078B tetiklemesi sonrası en eski active cut; project.config.json canonical path detayı engine commit `5d01d59` + workspace commit `e85407f` body'sinde de korunur; 3-active floor 1 cycle altında — ADR-034+035 active)
- ADR-034 (v1.1 P2+P3 Wave 3 Task 3.3, 2026-05-06 — ondokuzuncu rotation cycle, ADR-036 version sync invariant ekleme ile DECISIONS.md 6562B tetiklemesi sonrası en eski active cut; check_secrets.sh policy detayı `tests/ci/test_check_secrets_sh.py` body'sinde de korunur)
- ADR-035 (v1.1 P2+P3 Wave 3 Task 3.4, 2026-05-06 — yirminci rotation cycle, ADR-037 data hygiene policy ekleme ile DECISIONS.md 6799B tetiklemesi sonrası en eski active cut; PSEO_WORKSPACE_ROOT canonical detayı `scripts/state/env.py` + `tests/scripts/test_env_vars.py` body'sinde de korunur, 1y shim deadline 2027-05-06 unchanged)
- ADR-036 (v1.1 P2+P3 Wave 3 Task 3.6, 2026-05-06 — yirmibirinci rotation cycle, ADR-038 R-XX numbering policy ekleme ile DECISIONS.md 6895B tetiklemesi sonrası en eski active cut; version sync invariant detayı `tests/ci/test_version_sync.py` + RELEASE_NOTES_v1.1.0.md body'sinde de korunur)

**Active ADR'ler için:** [DECISIONS.md](DECISIONS.md)

---

## ADR-001 — Plugin Repo Yeri: platinum-seo-engine olarak Rename
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-001 — Plugin repo'su mevcut `~/Documents/platinum-seo-workflow-os/` dizininde mi açılsın yoksa yeni bir dizin mi yaratılsın? "workflow-os" geçici bir isim; final plugin adı `platinum-seo-engine` (spec §1, §2).
**Decision:** Mevcut `~/Documents/platinum-seo-workflow-os/` dizini `~/Documents/platinum-seo-engine/` olarak rename edildi (`mv` ile). Mevcut `docs/superpowers/specs/*.md` ve diğer tüm dosyalar otomatik olarak yeni repo'ya taşındı; ek kopyalama yapılmadı.
**Consequences:** GitHub repo adı `platinum-seo-engine` olacak (ADR-002). Tüm sonraki worker dispatch'leri ve commit'ler yeni path'i kullanır. VS Code workspace yeniden açılması gerekebilir.

---

## ADR-002 — GitHub Repo Timing: Phase 0 Sonu, User-Created
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-002 — GitHub repo açma timing'i ve kim açacak? Manager session'ın GitHub erişimi yok ve kullanıcı zaten "ben açacağım" dedi.
**Decision:** Phase 0 sonunda local `git init` + initial commit yapılır (manager hazırlar). Kullanıcı GitHub üzerinde repo'yu `platinum-seo-engine` adıyla manuel olarak açar; manager session sonrasında `git remote add` + `git push` komutlarını sunar, kullanıcı uygular. Phase 1+ her phase sonu **atomic phase commit** (her phase tek commit veya küçük bir grup commit).
**Consequences:** Phase 0 deliverable'larına `git init` + initial commit dahil. `.gitignore` (Worker C çıktısı) initial commit'te olur. Worker'lar git komutlarına dokunmaz; sadece manager git operasyonlarını koordine eder.

---

## ADR-003 — Pilot Proje: dentnotion
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-003 — Phase 5 GO/NO-GO gateway smoke test'i ve v1 acceptance (Phase 14) hangi pilot proje üzerinden doğrulanacak?
**Decision:** Pilot proje **dentnotion**. Sebep: Eski `~/Documents/platinum-premium-seo/` repo'sunda en olgun klasör; SF, GSC, içerik dataları en kapsamlı.
**Consequences:** Phase 5+ smoke test'leri dentnotion datasıyla çalışır. Discovery / Planning / Reporting / Production / Publishing skill'lerinin her biri dentnotion verisi üzerinde happy-path test edilir. Diğer projeler (vento, eykom, bigcattr) v1 sonrası onboard edilir.

---

## ADR-004 — Eski Repo Silme: v1 Acceptance + 1 Hafta Soak
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-004 — `~/Documents/platinum-seo-core/` (Python paketi + MCP server) ve `~/Documents/platinum-premium-seo/` (4. tasarım iterasyonu) ne zaman silinecek? Drift kaynakları ama referans değeri var.
**Decision:** v1 acceptance (Phase 14 tamamlanması) sonrası **1 hafta soak süresi** beklenir. Bu süre içinde production bug surface ederse referans için eski repo'lara dönülebilir. Soak sonu eski repo'lar silinir. Soak boyunca ve öncesinde READ-ONLY referans (spec §13 + bootstrap §kritik kurallar). Worker'lar eski dosyaları sadece `cp` ile kopyalar; orijinal dosyaları mutate etmez.
**Consequences:** Tahmini silme tarihi ≈ Phase 14 bitiş + 7 gün. Phase 5–13 boyunca eski dosyalar safe referans olarak elimizde. Migration phase'lerinde (Phase 1, 2, 3) worker'lar SADECE kopyalama operasyonu yapar.
**Closed:** 2026-06-01 — soak window expired (>14 days post-2026-05-12 deadline; ~20 days at closure); v1.4 eski repo silme acceptance criteria met (engine + workspace eski repo silinmiş, ~1.6GB recovered per memory feedback_decisions_workflow.md); v1.9 Phase 6 LC-4.

---

## ADR-005 — Workspace Repo Timing: Phase 14, User-Created
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-005 — `platinum-seo-workspace` repo'su ne zaman ve nerede açılacak? Plugin'le aynı timing'de olmalı mı?
**Decision:** Workspace repo (`~/Documents/platinum-seo-workspace/`) **Phase 14**'te yaratılır. Kullanıcı GitHub repo'sunu `platinum-seo-workspace` adıyla manuel açar. Phase 5–13 boyunca pilot test için mevcut `~/Documents/platinum-premium-seo/` workspace olarak READ-ONLY kullanılır (path detection eski premium klasörünü gösterir).
**Consequences:** Plugin Phase 14'e kadar workspace repo'su olmadan test edilir. Phase 14 deliverable'larına workspace bootstrap + ilk proje (dentnotion) onboard dahil. `.env`'deki `PSE_WORKSPACE_PATH` Phase 5'ten itibaren `~/Documents/platinum-premium-seo/` (veya alt klasörü) gösterir; Phase 14'te yeni workspace path'ine taşınır.
**Closed:** 2026-06-01 — Phase 14 workspace repo timing condition met (workspace bootstrap'landı + ilk proje onboard); ADR-004 ile birlikte idari kapanış (>14 days post-2026-05-12); v1.9 Phase 6 LC-4.

---

## ADR-006 — LICENSE: MIT
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-006 — Worker C `LICENSE` dosyasını MIT olarak yarattı (alpha plugin için yaygın default). Final lisans seçimi user onayı bekliyordu.
**Decision:** MIT lisansı onaylandı; mevcut `LICENSE` dosyası korundu. Permissive lisans — türev/ticari kullanım serbest. Patent grant yok (Apache 2'nin tersine), ama bu v1 alpha için kabul edilebilir tradeoff.
**Consequences:** Plugin'i fork eden/kullanan herkes MIT şartlarına tabi. `plugin.json` `"license": "MIT"` field'i ve README badge'i tutarlı kalır. v1 sonrası lisans değişimi mümkün ama mevcut commit history MIT olarak donar.

---

## ADR-007 — plugin.json Baseline Schema, Optional Alanlar Phase 4'te Validate
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-007 — Worker C `plugin.json`'ı baseline schema ile yarattı (`name, version, description, author, license, skills, commands, hooks`). `repository`, `homepage`, `keywords` gibi optional alanlar şimdilik eklenmedi; spec §3 sadece zorunlu alanları listeliyor.
**Decision:** Baseline kabul. Optional alanlar **Phase 4** (`plugin-loads-claude-code`) sırasında plugin Claude Code'a yüklenirken Claude Code resmî plugin manifest schema'sına karşı doğrulanacak; eksiklik varsa o phase'de eklenir, gerekirse yeni ADR yazılır.
**Consequences:** Phase 4 worker plugin.json validation görevini üstlenir. GitHub repo URL (`repository.url`) ADR-002 sonrası elimizde olduğu için Phase 4'te kolayca eklenebilir. Phase 0–3 boyunca plugin.json üzerinde manuel düzenleme yapılmaz.

---

## ADR-008 — state/outputs/inbox Plugin Repo'da YOK
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-008 — Bootstrap brief "If §3 lists more (e.g., `state/`, `validation/`, `reporting/` at top level — bootstrap hints these), include them" diyordu. Ama spec §3 plugin repo top-level'da `state/`, `outputs/`, `inbox/` listelemiyor — bunlar §4 workspace tarafında. Worker C bunları plugin repo'ya eklemedi.
**Decision:** Worker C kararı onaylandı — `state/`, `outputs/`, `inbox/` plugin repo'da YOK. Plugin = read-only tooling (skill/komut/hook); workspace = runtime state sahibi. Bu ayrım plugin-agnostic hard constraint'iyle uyumlu: plugin tek başına stateless, workspace path'i değiştirildiğinde plugin değişmez.
**Consequences:** Smoke test (Phase 5+) `PSE_WORKSPACE_PATH` env var'ından okur; eski premium repo (ADR-005) bu yolu sağlar. Hooks/scripts dosya yazarken hep workspace path'ini hedefler — plugin dizinine ASLA yazmaz. Bu disiplin Phase 5 acceptance criteria'sına eklenecek.

---

## ADR-009 — templates/master-excel.xlsx Phase 1'de Schema'dan Üretilir
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-009 — `.gitignore` `*.xlsx` ignore eder ama `!templates/master-excel.xlsx` whitelist ile bu dosyayı izler. Phase 0'da dosya yok; `templates/` altında `.gitkeep` placeholder.
**Decision:** Phase 1 worker `scripts/excel/bootstrap_excel.py` script'ini yazar; `schemas/master-excel.schema.json`'dan Excel binary'sini deterministik olarak üretir. `templates/master-excel.xlsx` ilk kez bu script ile yaratılır; aynı commit'te `templates/.gitkeep` silinir (template dosyası placeholder rolünü devralır).
**Consequences:** Excel binary single-source-of-truth schema'dan üretildiği için drift kaynağı olmaz — schema değişirse script'i tekrar koşturup binary regenerate edilir. Phase 0 commit'inde `templates/.gitkeep` görünür; Phase 1 atomic commit'i `.gitkeep` siliniş + `master-excel.xlsx` ekleniş kombinasyonu.

---

## ADR-010 — Runtime Versions: Python 3.10+, Node Gerekmez
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-010 — INSTALL.md placeholder'ı Python 3.10+ ve Node 18+ varsaymıştı. Plugin script'leri tamamen Python tabanlı (`scripts/excel/`, `scripts/`, `hooks/`); JS/TS bağımlılığı yok. `claude /plugin add` komut syntax'ı doğrulanmadı.
**Decision:** **Python 3.10+** onaylandı — match-case ve PEP 604 union types serbest. **Node bağımlılığı yok** — INSTALL.md'deki Node 18+ satırı **Phase 4**'te silinir. `claude /plugin add` syntax'ı Phase 4 plugin yükleme worker'ı tarafından doğrulanır; eksiklik/hata varsa INSTALL.md o zaman düzeltilir.
**Consequences:** Phase 1+ tüm Python script'leri 3.10+ syntax kullanabilir. CI workflow (Phase 14) Python 3.10/3.11/3.12 matrix'iyle test eder. INSTALL.md Phase 4'te iki düzeltme alır: (a) Node satırı silme, (b) plugin install komut syntax doğrulama.

---

## ADR-011 — DECISIONS_ARCHIVE Rotation Stratejisi
**Date:** 2026-04-30
**Status:** accepted (eşik kuralı ADR-014 ile partial supersede; rotation pattern korundu)
**Context:** DECISIONS.md Phase 0 closeout sonu 8942 byte (10 ADR, doğal birikme); spec §13 ve memory'deki <5KB hard cap aşıldı. Append-only prensip korunmalı, ama disiplin koruması da şart — büyük DECISIONS.md fresh session wakeup sequence'ını şişirir, manager bağlamını kötü etkiler.
**Decision:** ADR-001..ADR-005 (Phase 0 closeout paketi) `docs/DECISIONS_ARCHIVE.md` dosyasına taşındı. Manuel rotation Phase 1.0'da yapıldı; Phase 3'te `scripts/state/rotate_decisions.py` ile otomatize edilir. Eşik kuralı (ADR-014 ile revize): primary metric <5KB, ADR sayısı flexible 3-5.
**Consequences:** Trigger: her phase sonu manager rotation check; >5KB ise en eski 1-2 ADR archive'a taşınır. ADR numaraları monotonic — re-numbering YOK; archive'da gap'ler kabul. Fresh session her zaman summary table'ı görür, full ADR'i archive'da bulur. REFERENCE_INDEX.md'ye archive entry eklendi.

---

## ADR-012 — JSON Schema Meta-Schema URI: HTTP (History-Stable)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 1.1 dispatch brief'inde HTTPS varyantı (`https://json-schema.org/draft-07/schema#`) kullanılmıştı, 13 schema dosyasına yansıdı. JSON Schema resmi standardı (RFC) HTTP varyantını öngörür. HTTPS bazı validator'larda (ajv strict, Python jsonschema) "unknown meta-schema" warning'i tetikler. Hata karar verici agent'in dispatch direktifinde, worker disiplinli flag etti — doğru worker davranışı.
**Decision:** Tüm schema dosyalarında `$schema` HTTP. Phase 1.1'de yazılan 13 dosya sed ile toplu düzeltildi. Phase 1.2+ schema yazımlarında HTTP zorunlu; ihlal durumunda worker DURUR ve manager'a sorar.
**Consequences:** Validator uyarıları kaybolur. Karar verici agent dispatch direktiflerinde dış standart referansları için kanıt-tabanlı doğrulama (RFC/resmi spec) zorunlu hale gelir.

---

## ADR-013 — Phase 1.4 Schema Yazım Kararları (3 Sub-Decision)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 1.4 W-G dispatch'inde 3 yeni schema yazıldı (workflow-run, skill-frontmatter, project-memory). Worker spec authority'yi manager brief'inin üstünde tuttu, 3 tasarım kararı çıktı:
**Decision:**
1. **Skill frontmatter use_when/also_use_when/do_not_use_when** ayrı field değil, description string'i içinde (spec §9 birebir uygulandı). Drift kapısı kapalı, spec authoritative.
2. **project-memory v1 minimum 6 field**: project_slug, domain, target_audience, kpis, mcp_scope, last_updated. Spec §14 exact field listesi vermiyor; v1 baseline kabul. Phase 5+ skill'lerinde yetersiz çıkarsa yeni ADR ile genişletilir.
3. **workflow-run updated_at required** (manager mini-fix sonrası). Audit trail için kritik — her step değişiminde güncelleniyor. created_at opsiyonel (started_at ile genelde aynı).
**Consequences:** Schema yazım disiplinine "spec authority > manager brief" kuralı pekişti. Worker bu prensibi koruduğu için drift kapısı kapandı. Phase 1.5 schema-validate test'lerinde 3 schema bu kararla validate edilir.

---

## ADR-014 — DECISIONS Rotation Eşiği: <5KB Primary, ADR Sayısı Flexible
**Date:** 2026-04-30
**Status:** accepted (supersedes ADR-011 partial — eşik kuralı bölümü)
**Context:** ADR-011 iki hedef koymuştu: "5 ADR + <5KB". Phase 1 closeout'ta çakıştı (5 ADR korundu ama 6.7KB). Uzun ADR'ler (sub-decision'lı) sayıyı kalın yapıyor — örneğin ADR-013 üç sub-decision içeriyor.
**Decision:** Primary metric **<5KB**. ADR sayısı flexible (3-5 active aralığı). Rotation tetiği: boyut >5KB. Phase closeout'ta agresif rotation ile (en eski 1-2 ADR archive'a) <5KB sağlanır. ADR-011'in rotation pattern'i (manuel Phase 1.0; otomatize Phase 3 `rotate_decisions.py`) korunur — sadece eşik metriği ADR-014 ile revize.
**Consequences:** Phase 2 closeout'ta DECISIONS.md (~7-8KB ADR-014 sonrası) tetiklenir; ADR-009 ve ADR-010 archive'a taşınır → DECISIONS.md ~5KB altı kalır. Phase 3 otomatik rotation script'i bu metrikle çalışacak. ADR-011'in "5 ADR" kısmı artık guideline (hard cap değil); boyut hard cap.

---

## ADR-016 — Budget Tracking: events.jsonl SSoT (Spec §16.8 Supersede)
**Date:** 2026-04-30
**Status:** accepted (supersedes spec §16.8 storage path)
**Context:** Spec §16.8, daily budget tracking için ayrı `_state/budget/{date}.json` UTC midnight rollover öngörüyordu. Phase 3.1 W-M dispatch'inde SSoT (rules/single-source-of-truth.md) + append-only-state (rules/append-only-state.md) disiplinleriyle çakıştığı tespit edildi: budget kullanımı zaten events.jsonl'de loglanıyor (`cost.credits`, `event_kind=provenance`, `source.kind=dataforseo_mcp`). Ayrı budget store ikinci state store yaratır → SSoT ihlali.
**Decision:** Budget tracking primary kaynağı events.jsonl. `check_budget.py` rolling 24h scan ile `cost.credits` toplar (`event_kind=provenance` + `source.kind=dataforseo_mcp` filter). Ayrı `_state/budget/{date}.json` YOK. Spec §16.8 storage path bölümü ADR-016 ile supersede edilir.
**Consequences:** SSoT + append-only-state disiplinleri korundu. Performance: events.jsonl büyüdükçe scan yavaşlar; v1'de kabul edilebilir, Phase 14+ optimization (monthly archive aday). Spec dokümanı IMMUTABLE — ADR'ler revize eder.

---

## ADR-017 — events.schema Field Naming: Schema-Correct Primary, Fallback Cleanup
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 3.1 W-M dispatch brief'inde karar verici agent yanlış field shape kullanmıştı (`credits` + `event_type=dataforseo_call`). Schema gerçeği (events.schema.json): `cost.credits` + `event_kind=provenance` + `source.kind=dataforseo_mcp`. Worker schema-correct path primary, brief shape fallback implementasyonu yapmıştı (forward-compat). Fallback gereksiz drift — rules/schema-first.md authoritative.
**Decision:** Schema-correct path primary; fallback path TEMIZLENİR. Manager brief drift'leri Phase 4+ pre-tool-use hook ile schema'ya karşı pre-flight check edilecek (Phase 4 task).
**Consequences:** `check_budget.py` kod sadeleşti, drift kapısı kapandı. ADR-013 "spec authority > manager brief" disiplini pekişti. Phase 4'te schema-validate hook devreye girince benzer drift'ler dispatch öncesinde yakalanır.

---

## ADR-018 — master-excel.schema definitions Block (Phase 1.1 Migration Miss)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 1.1 W-D dispatch'inde master-excel.schema.json migrate edilirken `definitions/{statusEnum, severityEnum}` block taşınmadı. 9 `ref` field'ı (master_task.status, opportunity, schema, redirect_404 vb.) resolve edilemez halde idi (custom `ref` notation, draft-07 validator silent-pass). 3 paralel subagent research keşfetti (Phase 3.2 PRE-FIX).
**Decision:** definitions block eklendi: statusEnum 7 değer (TODO, ONGOING, EXISTS, DONE, BLOCKED, DEFERRED, CANCELED) — eski sistemden ONGOING + EXISTS korundu (Phase 1 migration disiplini, eski Excel stored values backward compat), brief'ten BLOCKED + DEFERRED + CANCELED eklendi (Phase 8 planning skill'leri için workflow expressivity). severityEnum 4 değer (CRITICAL, HIGH, MEDIUM, LOW) standart. Sample row validation PASS.
**Consequences:** master_task, opportunity, schema, redirect_404, cannibalization, tech_seo, robots_txt, crawl_sitemap, topical_map sheet'lerinde status/severity field'ları runtime validate edilebilir. Phase 1.1 closeout retroactive fix; Phase 5 GO/NO-GO öncesi şart. Backward compat: Phase 5 GO/NO-GO smoke test'te eski premium repo'dan migrate edilecek master.xlsx satırlarında ONGOING/EXISTS değerleri schema-valid kalır (rename veya migration script gerekmez).

---

## ADR-019 — workflow-run.schema Additive Bump (retry_count + schema_version)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 1.4 W-G workflow-run.schema yazımında `retry_count` (retry mechanism field) ve `schema_version` (version drift detection) atlandı. Subagent #3 W-L research'ünde tespit etti; `retry()` API method'u şu an retry_count'a refer ediyor ama schema'da yer yoktu.
**Decision:** Additive bump — required'a EKLENMEDİ (default 0/missing kabul, backward compat). `retry_count`: integer >=0, default 0. `schema_version`: const "1.0".
**Consequences:** workflow_runner.py retry() method retry_count'u inkremente eder (failed → running transition). schema_version Phase 14+ migrasyonlarda version skew detection için. Mevcut workflow-run.json yok (yeni özellik), backward compat sorunsuz.

---

## ADR-020 — events.schema event_kind="workflow" + workflow_action Enum
**Date:** 2026-04-30
**Status:** accepted
**Context:** event_kind enum 3 değer (provenance/work/audit) workflow lifecycle event'leri için yetersiz. Workaround (audit routing) drift kabul; detay CONTEXT_LEDGER. Schema integrity sürprizi: events.run_id integer/PROVENANCE-only vs workflow-run.run_id string pattern → type collision riski (workflow_run_id ayrı field çözümü).
**Decision:** event_kind enum genişletildi 4 değer ("provenance", "work", "audit", "workflow"). workflow_action enum 8 değer eklendi. **workflow_run_id (string, workflow-run.run_id pattern aynası)** eklendi — events.run_id integer/provenance-only kalır, type-correct ayrım. step_index optional. allOf conditional: event_kind="workflow" iken workflow_action + workflow_run_id zorunlu.
**Consequences:** workflow_runner.py state transition'ları semantik-doğru `event_kind="workflow"` ile log'lanır. events.jsonl reader'lar (check_budget.py vb.) workflow event'lerini doğal filter ile ayırır. Type discipline (rules/schema-first.md) korundu — events.run_id integer kalmaya devam eder, workflow_run_id ayrı string field.

---

## ADR-021 — events.jsonl Path: _state/ (spec §4 SSoT)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 3.1 W-M `check_budget.py` events.jsonl path `state/` (underscore'suz) kullandı. Spec §4 line 254 dir tree `_state/` (underscore'lu) — path konvansiyonu spec §4 SSoT.
**Decision:** Spec §4 authoritative. `_state/` standartı uygulanır. `check_budget.py` line 14 docstring + line 119 default arg fix (`state/events.jsonl` → `_state/events.jsonl`). Tüm runtime state path'leri `_state/` prefix.
**Consequences:** check_budget.py path drift kapatıldı (replace_all 2 hit). Phase 3.3 W-L (events_writer.py + workflow_runner.py) yazımında `_state/` standartına uyacak. Phase 5 smoke test'te path mismatch hatası önlendi.

---

## ADR-022 — DECISIONS Rotation: <5120B Hard Cap, 3-ADR Active Floor (ADR-014 Clarification)
**Date:** 2026-04-30
**Status:** accepted (clarifies ADR-014 in archive; no supersede)
**Context:** ADR-014 numerik ambiguity (5000 vs 5120 KiB) Phase 3.1+3.2'de drift yarattı. Detay CONTEXT_LEDGER.
**Decision:** Hard cap = 5120 bytes (binary KiB). Trigger: `stat -f '%z' docs/DECISIONS.md > 5120` → en eski active ADR archive'a. Floor: 3 active ADR (ADR-014 alt sınır geçerli).
**Consequences:** ADR-014 rotation pattern korunur; numerik ambiguity kapandı. Phase 4+ DECISIONS yönetimi deterministic.

---

## ADR-023 — Engine MCP Server Kayıtları: Proje .mcp.json (Schema Constraint)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 5 GSC MCP: ~/.claude/settings.json mcpServers reddedildi (Claude Desktop format). Doğru: proje-root .mcp.json. enableAllProjectMcpServers:true otomatik onay.
**Decision:** Engine repo'suna ait MCP server kayıtları (.mcp.json) `/Users/apple/Documents/platinum-seo-engine/.mcp.json` dosyasında yaşar. Phase 5: gsc. Phase 6: dataforseo + scrapling aynı dosyaya append. SA path absolute şu an; Phase 6'da env var refactor (${GSC_SA_PATH}, ${DFS_API_TOKEN}). SA depolama: `/Users/apple/.config/seo-core/secrets/` agnostik klasör (proje-spesifik path YASAK).
**Consequences:** Plugin agnostik prensip (ADR-008) korunur — başka makinelerde aynı .mcp.json + farklı env var değerleri. enableAllProjectMcpServers:true sayesinde kullanıcı prompt çıkmadan aktif. Phase 6 öncesi ek ADR: env var standartı + secrets klasör konvansiyonu.

---

## ADR-024 — Phase 5 Hibrit Dispatch + skill-frontmatter Category Fix + Workspace Snapshot
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 5 3 PRE-FIX: (1) skill-frontmatter category enum 6 değer, gerçek 8 dizin (Phase 1.4 W-G drift); (2) eski premium READ-ONLY ama Phase 5 yazma; (3) 5 skill convention drift Phase 6-12 compound.
**Decision:** (1) Category enum 8 değer (skills/{category}/ layout). (2) Workspace snapshot ~/Documents/platinum-seo-workspace-staging (PSEO_WORKSPACE_ROOT, Phase 14'te kalıcıya cp). (3) Hibrit dispatch: Wave 1 quick-wins SERI + Wave 2 4-paralel (init-project, sf-import, drift-check, whats-next).
**Consequences:** Schema fix Phase 1.4 drift kapandı. Workspace snapshot ADR-004+005 korundu. Hibrit dispatch Phase 6+ drift minimize.

---

## ADR-025 — templates/scrapling/ Dizin (Q-015 Resolution)
**Date:** 2026-04-30
**Status:** accepted
**Context:** scrapling-output-mapping.schema `output_schema_file` pattern S1-S4 yolu bekliyor. Dizin yok (W-F OQ-WF-01 drift).
**Decision:** templates/scrapling/.gitkeep yaratılır. Schema pattern mutate yok. Sub-schemas (S1-S4) Phase 7+ skill'lerle (competitive-analysis P7, content-improve P9). Phase 6 scrapling-ops generic helper.
**Consequences:** Q-015 closed. templates/ agnostik. Schema-First korunur. Phase 6 dispatch bloke değil.

---

## ADR-026 — DECISIONS Hard Cap: 5120→6144B (ADR-022 Cap-Only Supersede)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 4+5 3 ardışık tightening turu 5120B cap'i pratik FROZEN ettiğini kanıtladı (3-floor × ~800B body + header ≈ 5000B+ taban). ADR-025 + Phase 6-9 RE-EVAL'lar sığmıyor.
**Decision:** Hard cap 5120→6144 bytes (1KB hava, ~+2 ADR). Trigger: `stat -f '%z' docs/DECISIONS.md > 6144`. 3-ADR floor korunur. Supersedes ADR-022 cap clause; rotation clause unchanged.
**Consequences:** Phase 6+ deterministic. ADR-022 entry mutate yok. ADR-014 pattern korunur, sadece numerik cap revize.

---

## ADR-027 — Phase 7 Transform Size Policy: <1500L Hedef
**Date:** 2026-05-01
**Status:** accepted
**Context:** Phase 3 W-L <800L hedefliyordu (events_writer 550, transaction 785, workflow_runner 793). Phase 7 discovery 5/8 transform >800L (W-A3 1011, W-B1 851, W-B2 915, W-B3 1047, W-B4 973) — cross-source join + scoring + budget + multi-DURUR.
**Decision:** Phase 7+ transform <1500L hedef. Helper extract OPTIONAL (maturity); tek modül per skill <1500L'de korunur (split YASAK). D-003 cross-skill helper sahibi modülde (identity import zorunlu).
**Consequences:** Phase 8+ skill bu policy ile değerlendirilir. Phase 14 v1 transform CI gate aday (DEFER).

---

## ADR-028 — Tech Audit Schema: issue_category Enum + Web Vitals 2024 Note
**Date:** 2026-05-01
**Status:** accepted
**Context:** Q-W-A3-01 (FID deprecated 2024+, INP modern) + Q-W-A3-02 (a11y category eksik) W-A3 surfaced. Brief drift Q-CO-01: tech_seo metric_name field yok (6 col); issue_category constraint'siz.
**Decision:** sheets.tech_seo additive: (1) issue_category enum ["Performance","Layout Stability","Meta Tags","Structured Data","Accessibility"]; (2) description "Web Vitals 2024: INP supersedes FID, transform-owned thresholds". ADR-018 paterni; schema_version YOK.
**Consequences:** tech-audit output validate; future enum ADR-018. Q-W-A3-01 transform domain (INP Phase 7+).

---

## ADR-029 — Budget Convention: per-run estimated_credits (Phase 7+)
**Date:** 2026-05-01
**Status:** accepted
**Context:** Q-W-A3-03: Phase 7 paid skill budget.estimated_credits convention belirsiz (per-URL×count vs per-run total?). schema sadece estimated_credits (number ≥0).
**Decision:** Phase 7+ standart: budget.estimated_credits = per-run total tahmin (skill run credit). Per-URL skill internal logic; expose tek değer per-run. ADR-016 events.jsonl cost.credits SSoT compatible.
**Consequences:** Paid skill pre-flight tek değerle check_budget query. Phase 14 budget reporting per-skill granularity.

---

## ADR-030 — brand_identity Rename: pronoun_preference + formality (Migration 0003)
**Date:** 2026-05-06
**Status:** accepted
**Context:** Workspace `eca13c5` renamed `brand_identity.hitap`→`pronoun_preference`, `tone`→`formality` (canonical Principle 2 vocab). Schema 1.2 had `additionalProperties: false` + only legacy keys → workspace failed `validate_schema`. Q-PHASE15-BRAND-CONFIG-01 was prematurely closed without engine fix.
**Decision:** Schema 1.2→1.3 additive. Add `pronoun_preference` enum `["sen","siz"]` + `formality` enum `["semi-pro","conversational","formal","casual"]`. Legacy `hitap`+`tone` retained as deprecated aliases (1-yr shim). Migration 0003 = pure key rename, values KORUNUR (no remap). brand-onboarding 18→20 fields; required[] unchanged.
**Consequences:** Workspace validates EXIT 0 post-migrate. Skills can still read legacy keys until v2.0. Idempotency: 8 cases in `test_migration_0003.py`. Legacy removal scheduled v2.0.

---

## ADR-031 — events.jsonl Legacy Archive
**Date:** 2026-05-06
**Status:** accepted
**Context:** Workspace dentnotion events.jsonl (88 rows) had 15 schema violations: skill names used as `event_type` (gsc_pull/dfs_pull/etc) instead of 10-enum; audit events missing `event_id`; extra fields (`credits_used`/`fail_count`). Append-only-state forbids in-place edit; F-13/15/16/17 couldn't surface real drift.
**Decision:** Two-file split. `events.jsonl` — strict, schema-PASS (CI gate). `events.jsonl.legacy` — READ-ONLY archive. `scripts/state/migrate_legacy_events.py` atomic-partitions (`.tmp` rename pair), idempotent, emits `outputs/reports/{date}-events-archive.md` audit trail. Future writers MUST produce strict rows; `tests/state/test_events_schema_compliance.py` enforces.
**Consequences:** Workspace 88 → 73 strict + 15 legacy. F-13/15/16/17 re-eval clears mechanical noise. CI Step 4a keeps schema validity visible; per-row gate fires in workspace-bound runs.

---

## ADR-032 — `shared/active.json` Field: `active_project` Canonical
**Date:** 2026-05-06
**Status:** accepted
**Context:** `pseo-active.md` writes `{"active_project": "<slug>"}`; `pseo-driftcheck.md:34` reads `.active_project`. Python hooks `post-tool-use.json`+`user-prompt-submit.json` were reading `.project_id` — never written. Audit append + context banner silently no-op; F-19 SKIP unnoticed.
**Decision:** Canonical = `active_project`. Both hooks fixed. No backward-compat shim (no legacy data on disk).
**Consequences:** F-19 audit fires live. Contract locked by `tests/hooks/test_active_project_contract.py`. Future writers MUST emit `active_project`.

---

## ADR-033 — project.config.json Canonical Path
**Date:** 2026-05-06
**Status:** accepted
**Context:** Three competing forms: (a) `projects/{slug}/project.config.json` (engine canon); (b) `projects/{slug}/config/...` (workspace pilot); (c) hyphenated `project-config.json` (check_budget + 40 SKILL.md).
**Decision:** Canonical = `projects/{slug}/project.config.json`. Engine sweep: 40 hyphen→dot + 9 strip `config/` + check_budget/internal_links defaults. `excel.config.json`/`excel-source-manifest.json` stay in `config/` (separate).
**Consequences:** `test_path_canonical.py` regex-guards both forbidden forms. Workspace mv applied (`e85407f`). Aligned.

---

## ADR-034 — check_secrets.sh Scope Policy
**Date:** 2026-05-06
**Status:** accepted
**Context:** v1.1 polish (`bc9391c`) gave `scripts/ci/check_secrets.sh` 7 exclude paths + 4 patterns as code comment, no policy authority. FP risk surfaced via test-fixture tokens, negative-assertion CI tests, doc placeholders.
**Decision:** Patterns + exclude paths are policy. New entries require ADR-034 amendment. `tests/ci/test_check_secrets_sh.py` locks the round trip: clean EXIT 0 + 7-path policy assertion + 4-pattern policy assertion.
**Consequences:** Test fixtures with secret-shaped values must live in the 2 whitelisted files; new test files with credentials extend the exclude list via amendment.

---

## ADR-035 — Workspace Env Var: PSEO_WORKSPACE_ROOT Canonical (1-Year Shim)
**Date:** 2026-05-06
**Status:** accepted
**Context:** `PSEO_WORKSPACE_ROOT` used by 20+ scripts/hooks/tests since Phase 14; `PSE_WORKSPACE_PATH` lived in `.env.example`+INSTALL+README+ARCHITECTURE. Asymmetry → onboarding confusion.
**Decision:** Canonical = `PSEO_WORKSPACE_ROOT`. `PSE_WORKSPACE_PATH` deprecated alias, 1-year shim (removal 2027-05-06, mirrors ADR-030). `scripts/state/env.py::get_workspace_root()` reads canonical first, falls back with `DeprecationWarning`. Docs aligned. Existing 20+ scripts that read canonical directly stay unchanged (no risky sweep).
**Consequences:** New users set canonical only. Legacy `.env` works via helper until deadline. `tests/scripts/test_env_vars.py` locks the contract. v2.0 removes alias.

---

## ADR-036 — Version Sync Invariant
**Date:** 2026-05-06
**Status:** accepted
**Context:** v1.0.0 release left `.claude-plugin/plugin.json` at `0.1.0-alpha`; README banner read `v1.0.0`; git tag was `v1.0.0`. Three-way drift risks "which one is canonical" confusion at install time and breaks Claude Code's `/plugin add` discovery surface.
**Decision:** plugin.json `version`, README banner semver, latest `docs/RELEASE_NOTES_v*.md` filename, and the most recent annotated git tag MUST agree exactly. v1.1.0 release synchronizes all four. `tests/ci/test_version_sync.py` enforces three-way parity (plugin.json + README + RELEASE_NOTES file presence); git-tag parity asserted at release time only (CI skip when tag absent).
**Consequences:** Future bumps require coordinated edit + matching RELEASE_NOTES file + tag. Pre-release tags (e.g., `1.2.0-rc1`) must follow the same trio.

---

## ADR-037 — Data Hygiene Policy: code-driven script + dry-run + audit trail
**Date:** 2026-05-06
**Status:** accepted
**Context:** Wave 3 surfaced F-17 drift (4 `master_task.priority` cells = legacy P1/P2 outside severityEnum). Manual Excel edit forfeits provenance + breaks `rules/append-only-state.md`. Validator's `_resolve_header_row` (Phase 14 W3-W2-C-a) already handles dup-header artifacts.
**Decision:** Pilot data fixes via `scripts/maintenance/*.py` ONLY (transaction.py sole writer). Each run: `--dry-run` → audit trail `outputs/reports/{date}-data-hygiene-*.md` → Süleyman approval → `--apply`. Idempotent. F-17 mapping: P1→HIGH, P2→MEDIUM, P3→LOW. F-16 36-URL coverage deferred v1.2 (Q-V1.2-OPP-COVERAGE-01, SEO domain). Validator behavior regression-locked: `tests/scripts/test_header_echo_defense.py`.
**Consequences:** `tests/maintenance/test_data_hygiene_master_xlsx.py` enforces idempotency + audit emission + dry-run/apply parity. Workspace commits: `fix(data): ...(ADR-037)`.
**Archived:** 2026-05-26 — v1.8 Phase 2 rotation cycle 22 (ADR-039 v1.8 SF MCP integration ekleme ile DECISIONS.md cap tetiklemesi sonrası en eski active cut; data hygiene policy detayı `tests/maintenance/test_data_hygiene_master_xlsx.py` + `scripts/maintenance/*.py` body'sinde de korunur).
