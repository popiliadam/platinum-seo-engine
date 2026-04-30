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

### Q-015: scrapling-output-mapping pattern dependency
**Raised:** 2026-04-30 during Phase 1.2 (Worker W-F → OQ-WF-01)
**Context:** `scrapling-output-mapping.schema.json` içinde `output_schema_file` pattern: `^templates/scrapling/[a-z_]+\.schema\.json$`. Yeni repo'da `templates/scrapling/` dizini yok (drift, taşınmadı — Q-014). Pattern runtime registry validation için (per-scenario sub-schema yolu), `$ref` değil.
**Options:**
- a) `templates/scrapling/` dizini yarat + Phase 6'da per-scenario sub-schemas oraya
- b) Pattern'i `^schemas/scrapling/[a-z_]+\.schema\.json$` olarak güncelle (validator-side fix)
- c) Pattern'i config-relative yap (esneklik, runtime resolve)
**Owner:** karar verici agent (Phase 6 dispatch öncesi karar)
**Blocking Phase:** Phase 6 (scrapling-ops skill)


## Resolved (last 10 — moved to DECISIONS)
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
