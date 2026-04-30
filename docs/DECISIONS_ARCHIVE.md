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

---

## ADR-005 — Workspace Repo Timing: Phase 14, User-Created
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-005 — `platinum-seo-workspace` repo'su ne zaman ve nerede açılacak? Plugin'le aynı timing'de olmalı mı?
**Decision:** Workspace repo (`~/Documents/platinum-seo-workspace/`) **Phase 14**'te yaratılır. Kullanıcı GitHub repo'sunu `platinum-seo-workspace` adıyla manuel açar. Phase 5–13 boyunca pilot test için mevcut `~/Documents/platinum-premium-seo/` workspace olarak READ-ONLY kullanılır (path detection eski premium klasörünü gösterir).
**Consequences:** Plugin Phase 14'e kadar workspace repo'su olmadan test edilir. Phase 14 deliverable'larına workspace bootstrap + ilk proje (dentnotion) onboard dahil. `.env`'deki `PSE_WORKSPACE_PATH` Phase 5'ten itibaren `~/Documents/platinum-premium-seo/` (veya alt klasörü) gösterir; Phase 14'te yeni workspace path'ine taşınır.

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
