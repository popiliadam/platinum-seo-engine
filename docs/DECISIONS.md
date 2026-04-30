# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..019 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-014 (rotation kuralı, archive): <5120B primary (ADR-022 numerik clarification), 3 active floor.

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
| ADR-019 | workflow-run.schema Additive Bump (retry_count + schema_version) | accepted | DECISIONS_ARCHIVE.md |
| ADR-020 | events.schema event_kind="workflow" + workflow_action Enum | accepted | (below) |
| ADR-021 | events.jsonl Path: _state/ (spec §4 SSoT) | accepted | (below) |
| ADR-022 | DECISIONS Rotation: <5120B Hard Cap, 3-ADR Active Floor (ADR-014 Clarification) | accepted | (below) |

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
**Context:** ADR-014 numerik ambiguity (5000 dec vs 5120 KiB) Phase 3.1+3.2'de kıl payı yarattı. Detay CONTEXT_LEDGER.
**Decision:** Hard cap = 5120 bytes (binary KiB). Trigger: `stat -f '%z' docs/DECISIONS.md > 5120` → en eski active ADR archive'a. Floor: 3 active ADR (ADR-014 alt sınır geçerli).
**Consequences:** ADR-014 rotation pattern'i geçerli kalır; sadece numerik ambiguity kapandı. Phase 4+ DECISIONS yönetimi deterministic.
