# Architecture Decision Records

Platinum SEO Engine plugin için mimari kararların kaydı.
Append-only — superseded entry'ler işaretlenir, silinmez.

> **Rotation:** ADR-001..037 archive'da (gap: 015) → [DECISIONS_ARCHIVE.md](DECISIONS_ARCHIVE.md). ADR-026 cap 6144B (ADR-022 supersede). v1.8 cycle 22: ADR-037 → archive (ADR-039 SF MCP eklendi). Active: ADR-038 + ADR-039.

## Summary Table

| ADR | Title | Status | Location |
|---|---|---|---|
| ADR-001 | Plugin Repo Yeri: platinum-seo-engine olarak Rename | accepted | DECISIONS_ARCHIVE.md |
| ADR-002 | GitHub Repo Timing: Phase 0 Sonu, User-Created | accepted | DECISIONS_ARCHIVE.md |
| ADR-003 | Pilot Proje: demo-dental | accepted | DECISIONS_ARCHIVE.md |
| ADR-004 | Eski Repo Silme: v1 Acceptance + 1 Hafta Soak | closed (2026-05-06, post-soak; 2 eski repo silindi ~1.6GB) | DECISIONS_ARCHIVE.md |
| ADR-005 | Workspace Repo Timing: Phase 14, User-Created | closed (2026-05-06, Phase 14 condition met) | DECISIONS_ARCHIVE.md |
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
| ADR-036 | Version Sync Invariant: plugin.json + README + RELEASE_NOTES + git tag | accepted | DECISIONS_ARCHIVE.md |
| ADR-037 | Data Hygiene Policy: code-driven script + dry-run + audit trail | accepted | DECISIONS_ARCHIVE.md |
| ADR-038 | R-XX Numbering: gap-tolerant, future renumber YASAK | accepted | (below) |
| ADR-039 | v1.8 SF MCP: HTTP Transport + Controlled F-16 Break | accepted | (below) |

---

## ADR-038 — R-XX Numbering: gap-tolerant, future renumber YASAK
**Date:** 2026-05-06
**Status:** accepted
**Context:** Audit across `rules/` + `skills/` + `docs/` finds 102 unique `R-XX` rule references with max R-122. Numbering carries gaps from rule mergers + supersedes (R-15, etc.). No spec defines hard count.
**Decision:** Numbering policy: monotonic-but-gap-tolerant. Once an R-XX number is assigned, **renumber FORBIDDEN** (history-stable, like ADR gap-015). New rules pick the next-unused number; superseded entries keep their number with a `(superseded)` marker.
**Consequences:** Q-PHASE15-RXX-COUNT-01 closure (gap by-design); K-01 closure 2026-05-07: undefined R-XX cited in templates = MUST-FIX (test_r_xx_resolution.py lock; R-26 inserted).

---

## ADR-039 — v1.8 SF MCP: HTTP Transport + Controlled F-16 Break
**Date:** 2026-05-26
**Status:** accepted
**Context:** v1.8 SF MCP Hybrid Integration adds 4th MCP server `sf` to `.mcp.json` over HTTP transport (first HTTP MCP; existing 3 use stdio). 482B byte invariant F-16 (47+ commits since v1.5) requires controlled break.
**Decision:** Append `"sf":{"url":"http://127.0.0.1:11435/mcp"}` to mcpServers. First deliberate F-16 break since v1.5; invariant resumes from new baseline (543B + new md5) post-v1.8. `scripts/util/sf_mcp_client.py` = reusable HTTP MCP client pattern per D-SF-14 (httpx; 3-retry exp backoff 1s/2s; 100KB cap per D-SF-05).
**Consequences:** `tests/skills/{test_brand_onboarding,test_generate_images}.py` baselines rebased (v1.8 cite inline). Phase 3-7 Workers use `SfMcpClient`. Future HTTP MCPs reuse the pattern.

---

## ADR-040 — SF MCP HTTP transport made explicit (`type:http`); second controlled F-16 break
**Date:** 2026-06-04
**Status:** accepted
**Context:** ADR-039 added `sf` to `.mcp.json` as a bare `{"url": ...}` (543B). Claude Code defaults an entry's transport to **stdio** when `type` is absent, so `sf` silently failed to register — absent from `claude mcp list` while the other 3 stdio servers appeared as `plugin:platinum-seo-engine:*`. This broke the `/pseo-sf-crawl` skill's `mcp__sf__*` wrapper path and made README.md:177 / INSTALL.md:119 ("should show sf connected") false. The httpx client (`sf_mcp_client.py`, D-SF-14) was unaffected (it hits the port directly). Codex audit 2026-06-04 P0-01.
**Decision:** Add `"type": "http"` to the `sf` entry. Second deliberate F-16 byte-invariant break since v1.5 (482B→543B at v1.8/ADR-039; 543B→565B at v1.9.x). New baseline **565B + md5 `634c8ed5b7cf3c852d9b41e1c0e1d3b5`**. F-16 drift resumes from the new baseline.
**Consequences:** `tests/skills/test_brand_onboarding.py` F-16 baseline rebased (565B/md5). New guard `tests/schemas/test_mcp_http_transport_declared.py` asserts any url-only entry declares `type:http` so this transport-shape bug cannot recur. Docs re-synced: ARCHITECTURE.md, INSTALL.md, README.md snippet. **Operator note:** the engine runs as an installed plugin — the running `mcp__sf__*` registration only updates after the plugin cache is refreshed (reinstall/update or restart Claude Code).
