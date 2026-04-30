# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..018 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-014 (rotation kuralı, archive): <5KB primary, 3-5 active.

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
| ADR-009 | templates/master-excel.xlsx Phase 1'de Schema'dan Üretilir | accepted | DECISIONS_ARCHIVE.md |
| ADR-010 | Runtime Versions: Python 3.10+, Node Gerekmez | accepted | DECISIONS_ARCHIVE.md |
| ADR-011 | DECISIONS_ARCHIVE Rotation Stratejisi | accepted | DECISIONS_ARCHIVE.md |
| ADR-012 | JSON Schema Meta-Schema URI: HTTP (History-Stable) | accepted | DECISIONS_ARCHIVE.md |
| ADR-013 | Phase 1.4 Schema Yazım Kararları (3 Sub-Decision) | accepted | DECISIONS_ARCHIVE.md |
| ADR-014 | DECISIONS Rotation Eşiği: <5KB Primary, ADR Sayısı Flexible | accepted | DECISIONS_ARCHIVE.md |
| ADR-016 | Budget Tracking: events.jsonl SSoT (Spec §16.8 Supersede) | accepted | DECISIONS_ARCHIVE.md |
| ADR-017 | events.schema Field Naming: Schema-Correct Primary, Fallback Cleanup | accepted | DECISIONS_ARCHIVE.md |
| ADR-018 | master-excel.schema definitions Block (Phase 1.1 Migration Miss) | accepted | DECISIONS_ARCHIVE.md |
| ADR-019 | workflow-run.schema Additive Bump (retry_count + schema_version) | accepted | (below) |
| ADR-020 | events.schema event_kind="workflow" + workflow_action Enum | accepted | (below) |
| ADR-021 | events.jsonl Path: _state/ (spec §4 SSoT) | accepted | (below) |

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
**Context:** Mevcut event_kind enum 3 değer (provenance/work/audit). Workflow lifecycle event'leri (started/paused/resumed/approved/rejected/retried/done/failed) için doğal yer yoktu. Subagent #3 önerisi audit routing workaround'du; drift bırakma + semantik doğruluk prensibi gereği temiz çözüm: yeni event_kind. **Schema integrity sürprizi:** Brief "run_id zaten var" dedi ama events.run_id integer/PROVENANCE-only declared (line 30); workflow-run.run_id string pattern. Type collision riski.
**Decision:** event_kind enum genişletildi 4 değer ("provenance", "work", "audit", "workflow"). workflow_action enum 8 değer eklendi. **workflow_run_id (string, workflow-run.run_id pattern aynası)** eklendi — events.run_id integer/provenance-only kalır, type-correct ayrım. step_index optional. allOf conditional: event_kind="workflow" iken workflow_action + workflow_run_id zorunlu.
**Consequences:** workflow_runner.py state transition'ları semantik-doğru `event_kind="workflow"` ile log'lanır. events.jsonl reader'lar (check_budget.py vb.) workflow event'lerini doğal filter ile ayırır. Type discipline (rules/schema-first.md) korundu — events.run_id integer kalmaya devam eder, workflow_run_id ayrı string field.

---

## ADR-021 — events.jsonl Path: _state/ (spec §4 SSoT)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 3.1 W-M `check_budget.py` yazımında events.jsonl path olarak `state/events.jsonl` (underscore'suz) kullanıldı. Spec §4 line 254 dir tree `_state/` (underscore'lu). Subagent #2 tespit etti; ADR-016 budget store'u kapatsa da path konvansiyonu spec §4 SSoT.
**Decision:** Spec §4 authoritative. `_state/` standartı uygulanır. `check_budget.py` line 14 docstring + line 119 default arg fix (`state/events.jsonl` → `_state/events.jsonl`). Tüm runtime state path'leri `_state/` prefix.
**Consequences:** check_budget.py path drift kapatıldı (replace_all 2 hit). Phase 3.3 W-L (events_writer.py + workflow_runner.py) yazımında `_state/` standartına uyacak. Phase 5 smoke test'te path mismatch hatası önlendi.
