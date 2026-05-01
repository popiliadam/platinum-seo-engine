# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..022 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026: hard cap 6144B primary (ADR-022 cap-only supersede), 3 active floor (ADR-014 rotation pattern, archive).

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
| ADR-023 | Engine MCP Server Kayıtları: Proje .mcp.json (Schema Constraint) | accepted | (below) |
| ADR-024 | Phase 5 Hibrit Dispatch + skill-frontmatter Category Fix + Workspace Snapshot | accepted | (below) |
| ADR-025 | Scrapling Output Sub-Schemas: templates/scrapling/ Dizin (Q-015) | accepted | (below) |
| ADR-026 | DECISIONS Hard Cap: 5120→6144B (ADR-022 Cap-Only Supersede) | accepted | (below) |

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

---

## ADR-025 — templates/scrapling/ Dizin (Q-015 Resolution)
**Date:** 2026-04-30
**Status:** accepted
**Context:** scrapling-output-mapping.schema `output_schema_file` pattern S1-S4 yolu bekliyor. Dizin yok (W-F OQ-WF-01 drift).
**Decision:** templates/scrapling/.gitkeep yaratılır. Schema pattern mutate yok. Sub-schemas (S1-S4) Phase 7+ skill'lerle (competitive-analysis P7, content-improve P9). Phase 6 scrapling-ops generic helper.
**Consequences:** Q-015 closed. templates/ agnostik. Schema-First korunur. Phase 6 dispatch bloke değil.

---

## ADR-026 — DECISIONS Hard Cap: 5120→6144B (ADR-022 Cap-Only Supersede)
**Date:** 2026-04-30
**Status:** accepted
**Context:** Phase 4+5 3 ardışık tightening turu 5120B cap'i pratik FROZEN ettiğini kanıtladı (3-floor × ~800B body + header ≈ 5000B+ taban, 120B oynama). ADR-025 (Q-015) + Phase 6-9 RE-EVAL'lar sığmıyor.
**Decision:** Hard cap 5120 → 6144 bytes (1KB ek hava, ~+2 ADR). Trigger güncellenir: `stat -f '%z' docs/DECISIONS.md > 6144`. 3-ADR floor korunur. Supersedes ADR-022 hard cap clause (5120B → 6144B); 3-floor rotation clause unchanged.
**Consequences:** Phase 6+ deterministic, ADR-025 + RE-EVAL'lar sığar. ADR-022 entry mutate yok (append-only). ADR-014 rotation pattern korunur, sadece numerik cap revize.
