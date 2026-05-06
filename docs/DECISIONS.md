# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..035 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026 cap 6144B (ADR-022 supersede). Wave 3 cycle 19+20: ADR-034+035 → archive. Active: ADR-036 + ADR-037.

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
| ADR-034 | check_secrets.sh Scope Policy: 4 patterns + 7 exclude paths | accepted | DECISIONS_ARCHIVE.md |
| ADR-035 | Workspace Env Var: PSEO_WORKSPACE_ROOT Canonical (1-Year Shim) | accepted | DECISIONS_ARCHIVE.md |
| ADR-036 | Version Sync Invariant: plugin.json + README + RELEASE_NOTES + git tag | accepted | (below) |
| ADR-037 | Data Hygiene Policy: code-driven script + dry-run + audit trail | accepted | (below) |

---

## ADR-036 — Version Sync Invariant
**Date:** 2026-05-06
**Status:** accepted
**Context:** v1.0.0 release left `.claude-plugin/plugin.json` at `0.1.0-alpha`; README banner read `v1.0.0`; git tag was `v1.0.0`. Three-way drift risks "which one is canonical" confusion at install time and breaks Claude Code's `/plugin add` discovery surface.
**Decision:** plugin.json `version`, README banner semver, latest `docs/RELEASE_NOTES_v*.md` filename, and the most recent annotated git tag MUST agree exactly. v1.1.0 release synchronizes all four. `tests/ci/test_version_sync.py` enforces three-way parity (plugin.json + README + RELEASE_NOTES file presence); git-tag parity asserted at release time only (CI skip when tag absent).
**Consequences:** Future bumps require coordinated edit + matching RELEASE_NOTES file + tag. Pre-release tags (e.g., `1.2.0-rc1`) must follow the same trio.

---

## ADR-037 — Data Hygiene Policy: code-driven script + dry-run + audit trail
**Date:** 2026-05-06
**Status:** accepted
**Context:** Wave 3 surfaced F-17 drift (4 `master_task.priority` cells = legacy P1/P2 outside severityEnum). Manual Excel edit forfeits provenance + breaks `rules/append-only-state.md`. Validator's `_resolve_header_row` (Phase 14 W3-W2-C-a) already handles dup-header artifacts.
**Decision:** Pilot data fixes via `scripts/maintenance/*.py` ONLY (transaction.py sole writer). Each run: `--dry-run` → audit trail `outputs/reports/{date}-data-hygiene-*.md` → Süleyman approval → `--apply`. Idempotent. F-17 mapping: P1→HIGH, P2→MEDIUM, P3→LOW. F-16 36-URL coverage deferred v1.2 (Q-V1.2-OPP-COVERAGE-01, SEO domain). Validator behavior regression-locked: `tests/scripts/test_header_echo_defense.py`.
**Consequences:** `tests/maintenance/test_data_hygiene_master_xlsx.py` enforces idempotency + audit emission + dry-run/apply parity. Workspace commits: `fix(data): ...(ADR-037)`.
