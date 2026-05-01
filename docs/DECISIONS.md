# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..025 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026: hard cap 6144B primary (ADR-022 cap-only supersede), 3 active floor (ADR-014 rotation pattern, archive).

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
| ADR-020 | events.schema event_kind="workflow" + workflow_action Enum | accepted | DECISIONS_ARCHIVE.md |
| ADR-021 | events.jsonl Path: _state/ (spec §4 SSoT) | accepted | DECISIONS_ARCHIVE.md |
| ADR-022 | DECISIONS Rotation: <5120B Hard Cap, 3-ADR Active Floor (ADR-014 Clarification) | accepted | DECISIONS_ARCHIVE.md |
| ADR-023 | Engine MCP Server Kayıtları: Proje .mcp.json (Schema Constraint) | accepted | DECISIONS_ARCHIVE.md |
| ADR-024 | Phase 5 Hibrit Dispatch + skill-frontmatter Category Fix + Workspace Snapshot | accepted | DECISIONS_ARCHIVE.md |
| ADR-025 | Scrapling Output Sub-Schemas: templates/scrapling/ Dizin (Q-015) | accepted | DECISIONS_ARCHIVE.md |
| ADR-026 | DECISIONS Hard Cap: 5120→6144B (ADR-022 Cap-Only Supersede) | accepted | (below) |
| ADR-027 | Phase 7 Transform Size Policy: <1500L Hedef | accepted | (below) |
| ADR-028 | Tech Audit Schema: issue_category Enum + Web Vitals 2024 Note | accepted | (below) |
| ADR-029 | Budget Convention: per-run estimated_credits (Phase 7+) | accepted | (below) |

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
