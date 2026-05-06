# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..030 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026: hard cap 6144B primary (ADR-022 cap-only supersede), 3 active floor (ADR-014 rotation pattern, archive).

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
| ADR-029 | Budget Convention: per-run estimated_credits (Phase 7+) | accepted | DECISIONS_ARCHIVE.md |
| ADR-032 | active.json Field: `active_project` Canonical (Hook Contract Fix) | accepted | (below) |
| ADR-030 | brand_identity Rename: pronoun_preference + formality (Migration 0003) | accepted | DECISIONS_ARCHIVE.md |
| ADR-031 | events.jsonl Legacy Archive: events.jsonl.legacy (READ-ONLY) | accepted | (below) |
| ADR-033 | project.config.json Canonical Path | accepted | (below) |

---

## ADR-031 — events.jsonl Legacy Archive
**Date:** 2026-05-06
**Status:** accepted
**Context:** Workspace demo-dental events.jsonl (88 rows) had 15 schema violations: skill names used as `event_type` (gsc_pull/dfs_pull/etc) instead of 10-enum; audit events missing `event_id`; extra fields (`credits_used`/`fail_count`). Append-only-state forbids in-place edit; F-13/15/16/17 couldn't surface real drift.
**Decision:** Two-file split. `events.jsonl` — strict, schema-PASS (CI gate). `events.jsonl.legacy` — READ-ONLY archive. `scripts/state/migrate_legacy_events.py` atomic-partitions (`.tmp` rename pair), idempotent, emits `outputs/reports/{date}-events-archive.md` audit trail. Future writers MUST produce strict rows; `tests/state/test_events_schema_compliance.py` enforces.
**Consequences:** Workspace 88 → 73 strict + 15 legacy. F-13/15/16/17 re-eval clears mechanical noise. CI Step 4a keeps schema validity visible; per-row gate fires in workspace-bound runs.

---

## ADR-032 — `shared/active.json` Field: `active_project` Canonical
**Date:** 2026-05-06
**Status:** accepted
**Context:** `pseo-active.md` writes `{"active_project": "<slug>"}`; `pseo-driftcheck.md:34` reads `.active_project`. Python hooks `post-tool-use.json`+`user-prompt-submit.json` were reading `.project_id` — never written. Audit append + context banner silently no-op; F-19 SKIP unnoticed.
**Decision:** Canonical = `active_project`. Both hooks fixed. No backward-compat shim (no legacy data on disk).
**Consequences:** F-19 audit fires live. Contract locked by `tests/hooks/test_active_project_contract.py`. Future writers MUST emit `active_project`.

---

## ADR-033 — project.config.json Canonical Path
**Date:** 2026-05-06
**Status:** accepted
**Context:** Three competing forms: (a) `projects/{slug}/project.config.json` (engine canon); (b) `projects/{slug}/config/...` (workspace pilot); (c) hyphenated `project-config.json` (check_budget + 40 SKILL.md).
**Decision:** Canonical = `projects/{slug}/project.config.json`. Engine sweep: 40 hyphen→dot + 9 strip `config/` + check_budget/internal_links defaults. `excel.config.json`/`excel-source-manifest.json` stay in `config/` (separate).
**Consequences:** `test_path_canonical.py` regex-guards both forbidden forms. Workspace mv applied (`e85407f`). Aligned.
