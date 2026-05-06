# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..029 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026: hard cap 6144B primary (ADR-022 cap-only supersede), 3 active floor (ADR-014 rotation pattern, archive).

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
| ADR-032 | active.json Field Naming: `active_project` Canonical (Hook Contract Fix) | accepted | (below) |
| ADR-033 | project.config.json Canonical Path: `projects/{slug}/project.config.json` | accepted | (below) |

---

## ADR-032 — `shared/active.json` Field Naming: `active_project` Canonical
**Date:** 2026-05-06
**Status:** accepted
**Context:** `pseo-active.md` writes `{"active_project": "<slug>"}` and `pseo-driftcheck.md:34` reads `.active_project`. Python hooks `post-tool-use.json` + `user-prompt-submit.json` were reading `.project_id` — never written. Audit append + context banner silently no-op'd; F-19 coverage could SKIP unnoticed.
**Decision:** Canonical field on `shared/active.json` is `active_project` (slug). Both Python hooks updated; `pre-tool-use.json` + `session-start.json` don't read the field. No backward-compat shim — no on-disk legacy `project_id` data exists.
**Consequences:** F-19 audit append fires live. Contract locked by `tests/hooks/test_active_project_contract.py` (both hooks must read `active_project`, must not read `project_id`). Future writers (init-project skill) MUST emit `active_project`.

---

## ADR-033 — project.config.json Canonical Path: `projects/{slug}/project.config.json`
**Date:** 2026-05-06
**Status:** accepted
**Context:** Three competing path forms: (a) `projects/{slug}/project.config.json` — written by `bootstrap_project.py:170`, read by `pseo-init.md`/`pseo-driftcheck.md`/`pseo-active.md`/`validate_invariants.py:972`/migrations 0001+0002; (b) `projects/{slug}/config/project.config.json` — workspace demo-dental pilot landed there; (c) `project/project-config.json` — `check_budget.py` default + 40 SKILL.md + test files used the hyphenated form. Drift surface = pre-flight skill load.
**Decision:** Canonical = `projects/{slug}/project.config.json` (no `config/` subfolder, no hyphenated variant). Engine sweep: `check_budget.py` default + `internal_links_transform.py` help-text + 40 files containing `project-config.json` → `project.config.json` + 9 files containing `projects/{slug}/config/project.config.json` → `projects/{slug}/project.config.json`. `excel.config.json` + `excel-source-manifest.json` remain in `projects/{slug}/config/` (separate per-project config files, distinct decision).
**Consequences:** `tests/scripts/test_path_canonical.py` regex-greps the tree — both forbidden patterns (hyphenated + `config/` subfolder for project.config.json) fail the suite. Workspace data move (`mv projects/demo-dental/config/project.config.json projects/demo-dental/`) requires Süleyman approval; engine code is now consistent regardless.
