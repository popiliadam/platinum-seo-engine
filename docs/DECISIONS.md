# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..021 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-014 (rotation kuralı, archive): <5120B primary (ADR-022 numerik clarification), 3 active floor.

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
| ADR-022 | DECISIONS Rotation: <5120B Hard Cap, 3-ADR Active Floor (ADR-014 Clarification) | accepted | (below) |
| ADR-023 | Engine MCP Server Kayıtları: Proje .mcp.json (Schema Constraint) | accepted | (below) |
| ADR-024 | Phase 5 Hibrit Dispatch + skill-frontmatter Category Fix + Workspace Snapshot | accepted | (below) |

---

## ADR-022 — DECISIONS Rotation: <5120B Hard Cap, 3-ADR Active Floor (ADR-014 Clarification)
**Date:** 2026-04-30
**Status:** accepted (clarifies ADR-014 in archive; no supersede)
**Context:** ADR-014 numerik ambiguity (5000 vs 5120 KiB) Phase 3.1+3.2'de drift yarattı. Detay CONTEXT_LEDGER.
**Decision:** Hard cap = 5120 bytes (binary KiB). Trigger: `stat -f '%z' docs/DECISIONS.md > 5120` → en eski active ADR archive'a. Floor: 3 active ADR (ADR-014 alt sınır geçerli).
**Consequences:** ADR-014 rotation pattern korunur; numerik ambiguity kapandı. Phase 4+ DECISIONS yönetimi deterministic.

---

## ADR-023 — Engine MCP Server Kayıtları: Proje .mcp.json (Schema Constraint)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 5 GSC MCP: ~/.claude/settings.json mcpServers reddedildi (Claude Desktop format). Doğru: proje-root .mcp.json. enableAllProjectMcpServers:true otomatik onay.
**Decision:** Engine repo'suna ait MCP server kayıtları (.mcp.json) `/Users/apple/Documents/platinum-seo-engine/.mcp.json` dosyasında yaşar. Phase 5: gsc. Phase 6: dataforseo + scrapling aynı dosyaya append. SA path absolute şu an; Phase 6'da env var refactor (${GSC_SA_PATH}, ${DFS_API_TOKEN}). SA depolama: `/Users/apple/.config/seo-core/secrets/` agnostik klasör (proje-spesifik path YASAK).
**Consequences:** Plugin agnostik prensip (ADR-008) korunur — başka makinelerde aynı .mcp.json + farklı env var değerleri. enableAllProjectMcpServers:true sayesinde kullanıcı prompt çıkmadan aktif. Phase 6 öncesi ek ADR: env var standartı + secrets klasör konvansiyonu.

---

## ADR-024 — Phase 5 Hibrit Dispatch + skill-frontmatter Category Fix + Workspace Snapshot
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 5 3 PRE-FIX: (1) skill-frontmatter category enum 6 değer, gerçek 8 dizin (Phase 1.4 W-G drift); (2) eski premium READ-ONLY ama Phase 5 yazma; (3) 5 skill convention drift Phase 6-12 compound.
**Decision:** (1) Category enum 8 değer (skills/{category}/ layout). (2) Workspace snapshot ~/Documents/platinum-seo-workspace-staging (PSEO_WORKSPACE_ROOT, Phase 14'te kalıcıya cp). (3) Hibrit dispatch: Wave 1 quick-wins SERI + Wave 2 4-paralel (init-project, sf-import, drift-check, whats-next).
**Consequences:** Schema fix Phase 1.4 drift kapandı. Workspace snapshot ADR-004+005 korundu. Hibrit dispatch Phase 6+ drift minimize.
