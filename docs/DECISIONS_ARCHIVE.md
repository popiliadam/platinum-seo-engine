# Architecture Decision Records — Archive

ADR-011 rotation kararıyla `DECISIONS.md`'den taşınmış eski kararlar. Append-only — buradan da silme yok. Yeni rotation cycle'ları en eski ADR'leri buraya taşır.

**Bu dosyadaki ADR aralığı:**
- ADR-001..ADR-005 (Phase 0 closeout paketi, 2026-04-30 — ilk rotation)
- ADR-006..ADR-008 (Phase 1 closeout paketi, 2026-04-30 — ikinci rotation)
- ADR-009..ADR-010 (Phase 2 closeout paketi, 2026-04-30 — üçüncü rotation, ADR-014 eşik revizyonu)
- ADR-011 (Phase 2 closeout final, 2026-04-30 — dördüncü rotation, ADR-014'ün ilk uygulaması; ADR-014 partial supersede)

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

## ADR-003 — Pilot Proje: demo-dental
**Date:** 2026-04-30
**Status:** accepted
**Context:** Q-003 — Phase 5 GO/NO-GO gateway smoke test'i ve v1 acceptance (Phase 14) hangi pilot proje üzerinden doğrulanacak?
**Decision:** Pilot proje **demo-dental**. Sebep: Eski `~/Documents/platinum-premium-seo/` repo'sunda en olgun klasör; SF, GSC, içerik dataları en kapsamlı.
**Consequences:** Phase 5+ smoke test'leri demo-dental datasıyla çalışır. Discovery / Planning / Reporting / Production / Publishing skill'lerinin her biri demo-dental verisi üzerinde happy-path test edilir. Diğer projeler (demo-furniture, demo-hvac, demo-petcare) v1 sonrası onboard edilir.

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
**Consequences:** Plugin Phase 14'e kadar workspace repo'su olmadan test edilir. Phase 14 deliverable'larına workspace bootstrap + ilk proje (demo-dental) onboard dahil. `.env`'deki `PSE_WORKSPACE_PATH` Phase 5'ten itibaren `~/Documents/platinum-premium-seo/` (veya alt klasörü) gösterir; Phase 14'te yeni workspace path'ine taşınır.

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
