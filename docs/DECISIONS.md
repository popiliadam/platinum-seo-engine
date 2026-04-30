# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation (ADR-011):** Phase 1 closeout'ta toplu rotation uygulandı. ADR-001..ADR-008 archive'da. Eski ADR'ler için: [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md).
> Bu dosya sadece son 5 ADR'i tutar; >5KB sınırına yaklaşırsa rotation tekrar tetiklenir.

## Summary Table

| ADR | Title | Status | Location |
|---|---|---|---|
| ADR-001 | Plugin Repo Yeri: platinum-seo-engine olarak Rename | accepted | DECISIONS_ARCHIVE.md |
| ADR-002 | GitHub Repo Timing: Phase 0 Sonu, User-Created | accepted | DECISIONS_ARCHIVE.md |
| ADR-003 | Pilot Proje: demo-dental | accepted | DECISIONS_ARCHIVE.md |
| ADR-004 | Eski Repo Silme: v1 Acceptance + 1 Hafta Soak | accepted | DECISIONS_ARCHIVE.md |
| ADR-005 | Workspace Repo Timing: Phase 14, User-Created | accepted | DECISIONS_ARCHIVE.md |
| ADR-006 | LICENSE: MIT | accepted | DECISIONS_ARCHIVE.md |
| ADR-007 | plugin.json Baseline Schema, Optional Alanlar Phase 4'te Validate | accepted | DECISIONS_ARCHIVE.md |
| ADR-008 | state/outputs/inbox Plugin Repo'da YOK | accepted | DECISIONS_ARCHIVE.md |
| ADR-009 | templates/master-excel.xlsx Phase 1'de Schema'dan Üretilir | accepted | (below) |
| ADR-010 | Runtime Versions: Python 3.10+, Node Gerekmez | accepted | (below) |
| ADR-011 | DECISIONS_ARCHIVE Rotation Stratejisi | accepted | (below) |
| ADR-012 | JSON Schema Meta-Schema URI: HTTP (History-Stable) | accepted | (below) |
| ADR-013 | Phase 1.4 Schema Yazım Kararları (3 Sub-Decision) | accepted | (below) |

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
**Status:** accepted
**Context:** DECISIONS.md Phase 0 closeout sonu 8942 byte (10 ADR, doğal birikme); spec §13 ve memory'deki <5KB hard cap aşıldı. Append-only prensip korunmalı, ama disiplin koruması da şart — büyük DECISIONS.md fresh session wakeup sequence'ını şişirir, manager bağlamını kötü etkiler.
**Decision:** ADR-001..ADR-005 (Phase 0 closeout paketi) `docs/DECISIONS_ARCHIVE.md` dosyasına taşındı. DECISIONS.md sadece son 6 ADR (006..011) + üstte özet tablo (ADR no, title, status, archive link) tutar. Manuel rotation Phase 1.0'da yapıldı; Phase 3'te `scripts/state/rotate_decisions.py` ile otomatize edilir (>5KB trigger).
**Consequences:** DECISIONS.md ~5KB altına iner; archive ~4KB. Trigger: her phase sonu manager rotation check; >5KB ise en eski 5 ADR archive'a taşınır. ADR numaraları monotonic — re-numbering YOK; archive'da gap'ler kabul. Fresh session her zaman summary table'ı görür, full ADR'i archive'da bulur. REFERENCE_INDEX.md'ye archive entry eklendi.

---

## ADR-012 — JSON Schema Meta-Schema URI: HTTP (History-Stable)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 1.1 dispatch brief'inde HTTPS varyantı (`https://json-schema.org/draft-07/schema#`) kullanılmıştı, 13 schema dosyasına yansıdı. JSON Schema resmi standardı (RFC) HTTP varyantını öngörür (`http://json-schema.org/draft-07/schema#`). HTTPS bazı validator'larda (ajv strict, Python jsonschema) "unknown meta-schema" warning'i tetikler. Hata karar verici agent'in dispatch direktifinde, worker disiplinli flag etti — doğru worker davranışı.
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
