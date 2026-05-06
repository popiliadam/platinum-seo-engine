# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..028 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026: hard cap 6144B primary (ADR-022 cap-only supersede), 3 active floor (ADR-014 rotation pattern, archive).

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
| ADR-026 | DECISIONS Hard Cap: 5120→6144B (ADR-022 Cap-Only Supersede) | accepted | DECISIONS_ARCHIVE.md |
| ADR-027 | Phase 7 Transform Size Policy: <1500L Hedef | accepted | DECISIONS_ARCHIVE.md |
| ADR-028 | Tech Audit Schema: issue_category Enum + Web Vitals 2024 Note | accepted | DECISIONS_ARCHIVE.md |
| ADR-029 | Budget Convention: per-run estimated_credits (Phase 7+) | accepted | (below) |
| ADR-032 | active.json Field Naming: `active_project` Canonical (Hook Contract Fix) | accepted | (below) |

---

## ADR-029 — Budget Convention: per-run estimated_credits (Phase 7+)
**Date:** 2026-05-01
**Status:** accepted
**Context:** Q-W-A3-03: Phase 7 paid skill budget.estimated_credits convention belirsiz (per-URL×count vs per-run total?). schema sadece estimated_credits (number ≥0).
**Decision:** Phase 7+ standart: budget.estimated_credits = per-run total tahmin (skill run credit). Per-URL skill internal logic; expose tek değer per-run. ADR-016 events.jsonl cost.credits SSoT compatible.
**Consequences:** Paid skill pre-flight tek değerle check_budget query. Phase 14 budget reporting per-skill granularity.

---

## ADR-032 — active.json Field Naming: `active_project` Canonical (Hook Contract Fix)
**Date:** 2026-05-06
**Status:** accepted
**Context:** Workspace `shared/active.json` is the cross-session marker for the bound project. `commands/pseo-active.md` writes it as `{"active_project": "<slug>"}` and `commands/pseo-driftcheck.md:34` reads `.active_project` via `jq`. The two Python hooks that consume the marker (`hooks/post-tool-use.json` for audit append, `hooks/user-prompt-submit.json` for the context banner) were reading `(active or {}).get("project_id")` — a field that nothing writes. Result: silent no-op. F-19 audit-event coverage invariant could SKIP without surfacing the contract break.
**Decision:** Canonical field name on `shared/active.json` is `active_project` (slug string). Both Python hooks updated to `(active or {}).get("active_project")`. Workspace data is immutable under append-only-state; the fix lives entirely in plugin hook code. The other two hooks (`pre-tool-use.json`, `session-start.json`) do not depend on the field naming and are unchanged.
**Consequences:** Audit append fires for every PostToolUse Edit/Write/Bash when a workspace is bound (F-19 enforced live). Contract is now lockable via `tests/hooks/test_active_project_contract.py` — both hook commands must reference `active_project` and must not reference legacy `project_id`. Future writers (init-project skill, pseo-active command) MUST emit `active_project` only; any new consumer reads the same key. Backwards compatibility shim is intentionally NOT added — there is no on-disk legacy `project_id` data to support.
