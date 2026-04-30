# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..011 archive'da → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-014 eşik kuralı: <5KB primary, ADR sayısı flexible (3-5 active).

## Summary Table

| ADR | Title | Status | Location |
|---|---|---|---|
| ADR-001 | Plugin Repo Yeri: platinum-seo-engine olarak Rename | accepted | DECISIONS_ARCHIVE.md |
| ADR-002 | GitHub Repo Timing: Phase 0 Sonu, User-Created | accepted | DECISIONS_ARCHIVE.md |
| ADR-003 | Pilot Proje: dentnotion | accepted | DECISIONS_ARCHIVE.md |
| ADR-004 | Eski Repo Silme: v1 Acceptance + 1 Hafta Soak | accepted | DECISIONS_ARCHIVE.md |
| ADR-005 | Workspace Repo Timing: Phase 14, User-Created | accepted | DECISIONS_ARCHIVE.md |
| ADR-006 | LICENSE: MIT | accepted | DECISIONS_ARCHIVE.md |
| ADR-007 | plugin.json Baseline Schema, Optional Alanlar Phase 4'te Validate | accepted | DECISIONS_ARCHIVE.md |
| ADR-008 | state/outputs/inbox Plugin Repo'da YOK | accepted | DECISIONS_ARCHIVE.md |
| ADR-009 | templates/master-excel.xlsx Phase 1'de Schema'dan Üretilir | accepted | DECISIONS_ARCHIVE.md |
| ADR-010 | Runtime Versions: Python 3.10+, Node Gerekmez | accepted | DECISIONS_ARCHIVE.md |
| ADR-011 | DECISIONS_ARCHIVE Rotation Stratejisi | accepted | DECISIONS_ARCHIVE.md |
| ADR-012 | JSON Schema Meta-Schema URI: HTTP (History-Stable) | accepted | (below) |
| ADR-013 | Phase 1.4 Schema Yazım Kararları (3 Sub-Decision) | accepted | (below) |
| ADR-014 | DECISIONS Rotation Eşiği: <5KB Primary, ADR Sayısı Flexible | accepted | (below) |

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
