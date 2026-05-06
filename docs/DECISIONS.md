# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..033 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026: hard cap 6144B primary (ADR-022 cap-only supersede), 3 active floor (ADR-014 rotation pattern, archive). Wave 2 Task 2.3 cycle 18 floor 1 alt (ADR-034+035 active) — cap önce, floor recover Wave 3+ ADR ekleme ile.

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
| ADR-032 | active.json Field: `active_project` Canonical (Hook Contract Fix) | accepted | DECISIONS_ARCHIVE.md |
| ADR-030 | brand_identity Rename: pronoun_preference + formality (Migration 0003) | accepted | DECISIONS_ARCHIVE.md |
| ADR-031 | events.jsonl Legacy Archive: events.jsonl.legacy (READ-ONLY) | accepted | DECISIONS_ARCHIVE.md |
| ADR-033 | project.config.json Canonical Path | accepted | DECISIONS_ARCHIVE.md |
| ADR-034 | check_secrets.sh Scope Policy: 4 patterns + 7 exclude paths | accepted | (below) |
| ADR-035 | Workspace Env Var: PSEO_WORKSPACE_ROOT Canonical (1-Year Shim) | accepted | (below) |

---

## ADR-034 — check_secrets.sh Scope Policy
**Date:** 2026-05-06
**Status:** accepted
**Context:** v1.1 polish (`bc9391c`) gave `scripts/ci/check_secrets.sh` 7 exclude paths + 4 patterns as code comment, no policy authority. FP risk surfaced via test-fixture tokens, negative-assertion CI tests, doc placeholders.
**Decision:** Patterns + exclude paths are policy. New entries require ADR-034 amendment. `tests/ci/test_check_secrets_sh.py` locks the round trip: clean EXIT 0 + 7-path policy assertion + 4-pattern policy assertion.
**Consequences:** Test fixtures with secret-shaped values must live in the 2 whitelisted files; new test files with credentials extend the exclude list via amendment.

---

## ADR-035 — Workspace Env Var: PSEO_WORKSPACE_ROOT Canonical (1-Year Shim)
**Date:** 2026-05-06
**Status:** accepted
**Context:** `PSEO_WORKSPACE_ROOT` used by 20+ scripts/hooks/tests since Phase 14; `PSE_WORKSPACE_PATH` lived in `.env.example`+INSTALL+README+ARCHITECTURE. Asymmetry → onboarding confusion.
**Decision:** Canonical = `PSEO_WORKSPACE_ROOT`. `PSE_WORKSPACE_PATH` deprecated alias, 1-year shim (removal 2027-05-06, mirrors ADR-030). `scripts/state/env.py::get_workspace_root()` reads canonical first, falls back with `DeprecationWarning`. Docs aligned. Existing 20+ scripts that read canonical directly stay unchanged (no risky sweep).
**Consequences:** New users set canonical only. Legacy `.env` works via helper until deadline. `tests/scripts/test_env_vars.py` locks the contract. v2.0 removes alias.
