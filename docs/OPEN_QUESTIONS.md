# Open Questions

## Unresolved

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



## Resolved (last 10 — moved to DECISIONS)
- **Q-015 → ADR-025** — scrapling-output-mapping pattern dependency → templates/scrapling/.gitkeep yaratıldı, schema pattern korundu, sub-schemas Phase 7+ skill'lerle.

- **Q-001 → ADR-001** — Plugin repo yeri → `~/Documents/platinum-seo-engine/` rename.
- **Q-002 → ADR-002** — GitHub repo timing → Phase 0 sonu, user manuel açar.
- **Q-003 → ADR-003** — Pilot proje → **dentnotion**.
- **Q-004 → ADR-004** — Eski repo silme → v1 acceptance + 1 hafta soak.
- **Q-005 → ADR-005** — Workspace repo timing → Phase 14, user-created.
- **Q-006 → ADR-006** — LICENSE → **MIT** (Worker C default onaylandı).
- **Q-007 → ADR-007** — plugin.json baseline kabul; optional alanlar Phase 4'te validate.
- **Q-008 → ADR-008** — `state/`, `outputs/`, `inbox/` plugin repo'da YOK (workspace runtime sahibi).
- **Q-009 → ADR-009** — `templates/master-excel.xlsx` Phase 1'de `bootstrap_excel.py` ile schema'dan üretilir.
- **Q-010 → ADR-010** — Python 3.10+ onaylandı; Node bağımlılığı yok (INSTALL.md Phase 4'te düzeltilir).
