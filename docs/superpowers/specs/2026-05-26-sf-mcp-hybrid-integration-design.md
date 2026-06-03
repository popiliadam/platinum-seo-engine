# Screaming Frog 24 MCP — Comprehensive Hybrid Integration Design (v2.2, MCP-primary pivot + multi-session execution)

> ⚠️ **HISTORICAL DESIGN DOC (P3-01).** Dated 2026-05-26; this is the design
> spec that drove the SF MCP integration and carries earlier call shapes that
> have since evolved. For the CURRENT, authoritative SF contract see
> `commands/pseo-sf-crawl.md` + the `sf-crawl-orchestrator` SKILL
> (`skills/ingestion/sf-crawl-orchestrator/SKILL.md`). Preserved as-is for design
> provenance — do not follow the tool-call shapes here verbatim.

> **Status:** DRAFT v2.2 — MCP-primary semantic pivot + multi-session execution model. Operator clarified: "manuel 25'e yakın sf raporu ekliyorduk artık bu kısımı komple MCP'ye devredeceğiz" — meaning the orchestrator must FULLY delegate the 24-report (Tier 1 + Tier 2) export workflow to SF MCP via `sf_generate_report(save_report=True)`, replacing manual CSV drop. File-drop becomes the disaster-recovery fallback, not the authoritative path.
> **Date:** 2026-05-26 (v1 + v2 + v2.1 + v2.2 same day)
> **Supersedes:** v1 (narrow ingestion-only scope) → v2 (comprehensive integration matrix) → v2.1 (audit-revised) → **v2.2 (MCP-primary + multi-session)**
> **v2.2 changes vs v2.1:**
> 1. **MCP-primary semantic pivot** — Strategy reframed: SF MCP handles the full 24-report export per crawl (was "MCP triggers crawl, file-drop authoritative" → now "MCP is primary ingestion path; file-drop = disaster recovery fallback")
> 2. **24-report orchestrator loop** — Phase 3 orchestrator body expanded with explicit Tier 1 (14) + Tier 2 (10) export iteration; per-report timeout/retry; atomic all-or-nothing semantics
> 3. **Resume capability** — `workflow_runner.pause/resume` API integrated (already exists, verified at workflow_runner.py:564 + 573) — mid-24-report-loop recovery without restart
> 4. **Multi-session execution model** — NEW section + appendix with 7 self-contained Worker Prompts (one per Phase batch), following PSEO's existing `docs/WORKER_PROMPTS.md` + `docs/SESSION_PROTOCOL.md` Manager+Worker pattern
> 5. **Production-readiness gaps closed** — atomic crawl semantics, SF MCP crash recovery, backward compat tests, concurrency at orchestrator level, operator progress visibility, security loopback test
> 6. **Operator-execution gaps closed** — explicit pytest commands per phase, requirements.txt httpx mention, path parameterization, error recovery rollback drill
> 7. **3 new drift invariants** — F-24 (mcp-tool-registry matches .mcp.json keys), F-25 (project.config schema_version coherence), F-26 (orphan SF GUI crawl detection)
> 8. **3 new Decision Records** — D-SF-16 (atomic crawl), D-SF-17 (multi-session model), D-SF-18 (path parameterization)
> 9. **2 new Open Questions** — Q-SF-MCP-10 (Tier 3 optional reports inclusion), Q-SF-MCP-11 (per-report timeout default)
> 10. **Worker Prompts companion file** — `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md` (NEW) — 7 self-contained per-phase briefings for fresh executor sessions
>
> **Decision context:** Operator chose **Option B (Hybrid)** for transport, **MCP-primary** for data flow (v2.2 clarification), **Node.js Runtime OFF** (conservative). Multi-session execution: this Manager session decides + each Phase gets a fresh Worker session per `SESSION_PROTOCOL.md` §13.1-13.4.
> **Pipeline stage:** Brainstorming v2.2. Next: operator approves → `writing-plans` produces implementation plan → 7 Worker Prompts are dispatched serially to fresh sessions (per phase, in order); Manager (this session) processes Worker Output Packages between phases.

---

## Executive Summary

Add Screaming Frog 24 native MCP server (HTTP `http://127.0.0.1:11435/mcp`) as the **fourth MCP** in PSEO. **MCP-PRIMARY ingestion path**: the orchestrator calls `sf_crawl` → polls `sf_crawl_progress` → iterates `sf_generate_report(save_report=True)` for **24 reports** (Tier 1: 14 mandatory + Tier 2: 10 recommended) → moves files from SF allowed_directory to `projects/{slug}/sf-exports/{date}/raw/` → invokes existing `sf-import` skill to project to 6 sheets. **File-drop fallback** is preserved as disaster recovery only (operator can still manually drop CSVs if MCP is down — Q-SF-MCP-10 decides Tier 3 optional inclusion).

This is **organization-wide integration** that touches:

- **1 new + 5 extended + 4 optional-consumer skills** (10 touched out of 44 existing; total goes 44 → 45)
- **4 edited schemas + 1 new schema** (out of 22 total) + **1 new migration** (project-config v1.4 → v1.5, following migration_0004 pattern)
- **1 new instance file**: `mcp-tool-registry.json` (currently schema-only — no instance exists; Phase 1 creates the first one for all 4 servers; location per Q-SF-MCP-09)
- **1 new template scaffold**: `templates/sf-mcp/` (with .gitkeep + 1 example use-case instance)
- **2 new + 0 changed commands** (out of 16 current; total goes 16 → 18)
- **0 hard hook changes** (stop.json proposed change DROPPED after audit: violates <1s perf budget per scripts/hooks/stop_validation.py; Q-SF-MCP-08 RESOLVED → NO)
- **5 rules cross-referenced + 1 rule body edit** (`rules/events-writer.md` line 129 gets new sf-crawl-orchestrator row alongside existing sf-import row)
- **1 new utility script** (`scripts/util/sf_mcp_client.py` — first HTTP MCP client; reusable pattern for future HTTP MCPs)
- **1 cross-sheet invariant added**: F-23 in `schemas/cross-sheet-invariants.json` (sf workflow record requires sf entry in registry)
- **~40 new/extended test cases** (28 new + 12 extensions; exact baseline impact depends on Phase 3 test-function granularity — see Tests Plan section)
- **1 plugin manifest bump** (v1.7.0 → v1.8.0; **44 → 45 skills** [plugin.json description currently says "43" — stale by 1 from pre-v1.7 drift, fixed in Phase 6]; **16 → 18 commands** [description currently says "15" — also stale by 1, fixed in Phase 6]; 3 → 4 MCP servers)
- **8 documentation updates** (README + WORKFLOWS + ARCHITECTURE §7 + §16.5 + OPEN_QUESTIONS + DECISIONS + RELEASE_NOTES + PHASE_STATUS) + GLOSSARY.md additions
- **Realistic effort: ~8 days** (~60 hours) — was "~7" in v2.1, "~4" in pre-audit; v2.2 production-ready audit added: 24-report MCP loop expansion + 4 command extensions + 2 doc additions (INSTALL + REFERENCE_INDEX) + version_bump.py mandatory usage + sf-crawl report template + scripts/meta/whats_next.py edit

**Discipline preserved (non-negotiable):**

1. **DURUR enforcement** — orchestrator declares **8 DURURs** (6 base + DURUR-orch-7 concurrent-crawl guard per R13 + **DURUR-orch-8 Tier 1 export fail / atomic rollback per D-SF-16**); sf-import keeps its 6; **total 14 stop-conditions** across the chain
2. **Schema-first** (rules/schema-first.md) — new `sf-mcp-tool-mapping.schema.json` PR merges BEFORE any consumer code; project-config v1.4→v1.5 requires Migration 0005
3. **Append-only state** (rules/append-only-state.md) — `events.jsonl` adds `source.kind=sf_mcp` enum value; no mutation of existing entries
4. **Envelope discipline** — orchestrator writes `inbox/sf-mcp/{date}-{tool}-{slug}.json` BEFORE projection (mirrors gsc/dfs/scrapling envelope pattern from `events_writer.append_provenance`)
5. **Single source of truth** — `sf-required-reports.schema.json` remains SSoT for Tier 1/2; `mcp-tool-registry.json` remains SSoT for sf tools
6. **Pure-transform scripts** — `sf_crawl_orchestrator.py` is pure transform (reads inbox JSON, writes projections); MCP HTTP calls happen in SKILL.md body (mirrors gsc_pull.py / dfs_pull.py pattern)

---

## Why v2 — What v1 Missed

v1 spec was scoped narrowly to `ingestion/sf-import + new orchestrator + 4 schemas`. It missed:

| Missed area | What v2 adds |
|-------------|--------------|
| **Skill consumer wiring** | tech-audit, schema-audit, on-page-audit, internal-links can OPTIONALLY consume live SF MCP data (currently file-only) |
| **project-config schema** | New `sf.mcp.*` block needed for per-project config (URL, allowed_directory, crawl_config_path); v1.4 → v1.5 migration |
| **events.schema** | `source.kind` enum needs `sf_mcp` value (parallel to existing `gsc_mcp`, `dataforseo_mcp`); `source.mcp_server` description needs `sf` |
| **Hooks** | SessionStart could surface SF MCP status; Stop could validate sf registry entry |
| **Commands** | Need `/pseo-sf-crawl` + `/pseo-sf-status` (currently 16 commands, no SF MCP command) |
| **Plugin manifest** | `.claude-plugin/plugin.json` says "3 MCP server" — needs "4"; version bump v1.7.0 → v1.8.0 |
| **Architecture doc** | docs/ARCHITECTURE.md §7 (SF) + §16.5 (MCP discipline) reference file-based SF only |
| **MCP client utility** | First HTTP MCP — reusable utility `scripts/util/sf_mcp_client.py` establishes the pattern for future HTTP MCPs |
| **Migration script** | project-config v1.4 → v1.5 requires Migration 0005 per schema-versioning-discipline.md |
| **ADR** | Hybrid file+MCP strategy is a load-bearing decision; deserves ADR-031 in DECISIONS.md |

---

## Decision Record (15 architectural decisions logged for ADR audit)

| ID | Decision | Reason |
|----|----------|--------|
| **D-SF-01** | HTTP transport for SF MCP (only HTTP MCP in registry) | Native SF 24 ships HTTP-only; runtime=http already supported in mcp-tool-registry schema (line 47-51) |
| **D-SF-02** | Server key `"sf"` (3 chars, lowercase) | Cursor 60-char tool name limit; matches naming.md lowercase pattern; mirrors `gsc` 3-char convention (NOT `ScraplingServer` capital — that's pre-naming-rule legacy) |
| **D-SF-03** | SF allowed directory stays `/Users/apple/seo_spider_mcp_server` | F-15 governance: SF scratch isolated from PSEO workspace; orchestrator handles move/copy explicitly (auditable) |
| **D-SF-04** | Node.js Runtime = **OFF** in SF Settings | Security: SF warning explicit; embeddings/custom scripts deferred to v1.1+ (open question Q-SF-MCP-01) |
| **D-SF-05** | Max Response Size stays 100,000 bytes (SF default) | Larger cap doesn't fix 30K-URL crawl size; orchestrator pulls big data via file path |
| **D-SF-06** | Orchestrator is NEW skill, not a flag on sf-import | Single Responsibility: sf-import validates+projects; orchestrator runs MCP loop. Easier test, easier skip |
| **D-SF-07** | sf-import 8-step DURUR list UNCHANGED | sf-import consumed AFTER orchestrator deposits files; from its view still file-based — zero regression on 1184 pytest baseline |
| **D-SF-08** | New schema `sf-mcp-tool-mapping.schema.json` (not embed in registry) | Mirrors existing pattern: gsc / dataforseo / scrapling each have own mapping file; registry stays inventory-only |
| **D-SF-09** | Operator-triggered only in v1 (no cron) | Avoid silent budget drain + GUI presence assumption; cron deferred to v1.1+ |
| **D-SF-10** | Pre-flight check: GUI open + no modal dialog open | `IllegalStateException` from open settings dialog is opaque; orchestrator surfaces clear operator message |
| **D-SF-11** | Discovery skills (tech-audit, schema-audit, on-page-audit, internal-links) get OPTIONAL SF MCP consumer flag | New capability behind explicit flag `use_sf_mcp: bool = False` — zero regression on default behavior; opt-in for live data |
| **D-SF-12** | `project-config.schema.json` v1.4 → v1.5 additive (sf block optional, required[] unchanged) | Schema-versioning-discipline: additive only, old configs still validate; Migration 0005 populates default `sf.mcp.enabled: false` |
| **D-SF-13** | `events.schema.json` source.kind enum +1 (`sf_mcp`) | Mirrors existing `gsc_mcp`, `dataforseo_mcp` pattern; events_writer.append_provenance accepts automatically (Draft7 validation) |
| **D-SF-14** | `scripts/util/sf_mcp_client.py` is new reusable utility (first HTTP MCP client) | Establishes pattern for future HTTP MCPs (e.g. local LM Studio, custom servers); avoids one-off HTTP code in orchestrator |
| **D-SF-15** | Plugin version bump v1.7.0 → v1.8.0 (not patch) | Feature-level addition: new MCP server + new skill + new schema + 2 new commands = MINOR per semver |
| **D-SF-16** | **Atomic crawl semantics**: all 24 reports succeed OR rollback (delete partial CSVs in sf-exports/{date}/raw/) | Avoid sf-import partial-projection state. Implemented via temp staging dir `_state/staging/sf-crawl-{run_id}/` → atomic mv on success / rm -rf on fail |
| **D-SF-17** | **Multi-session execution model** — implementation distributed across 7 fresh Worker sessions (one per Phase) per `docs/SESSION_PROTOCOL.md` §13.1-13.4 | Operator's context-efficiency requirement: "context'i çok kıymetli şekilde kullanacağız bu yüzden batchlere bölmeliyiz". Each Worker = self-contained prompt + Worker Output Package return. Manager (this session) processes packages between phases. Pattern reuses existing PSEO multi-session discipline. |
| **D-SF-18** | **Path parameterization**: SF allowed_directory + .mcp.json sf URL configurable via project.config.sf.mcp.{allowed_directory,url} | Operator-execution audit (Plan agent): hardcoded `/Users/apple/seo_spider_mcp_server` breaks cross-machine portability. Migration 0005 populates default; operator overrides per project. F-15 governance preserved (path isolation enforced, just configurable). |

---

## Skills Integration Matrix — All 44 Skills

### Category A: NEW skill (1)

| Skill | Path | Purpose | Effort |
|-------|------|---------|--------|
| **sf-crawl-orchestrator** | `skills/ingestion/sf-crawl-orchestrator/SKILL.md` (NEW) | **PRIMARY ingestion path (v2.2).** Bridge SF MCP to file-based sf-import; trigger crawl via `sf_crawl`, poll `sf_crawl_progress`, **iterate `sf_generate_report(save_report=True)` for 24 reports** (Tier 1: 14 + Tier 2: 10), move files from SF allowed_directory to `projects/{slug}/sf-exports/{date}/raw/`, hand off to sf-import. **Atomic semantics** (D-SF-16): all 24 reports OR rollback. **Resume-capable** (workflow_runner.pause/resume mid-loop). **8 DURURs** (6 base + DURUR-orch-7 concurrent-crawl guard per R13 + DURUR-orch-8 Tier 1 export fail / atomic rollback per D-SF-16). | **XXL (24h)** — bumped from XL after MCP-primary pivot adds 24-report loop + atomic semantics + resume |

#### Step Count Semantics (v2.3 retro — R-6 / Q-PHASE-3-WORKER-04)

When a SKILL.md body specs **"N Body Steps"**, that counts the NUMBERED Body Step prose blocks (typically Step 1 `create_run` + intermediate workflow steps + Step N `complete`). The `workflow_runner.create_run(steps=[...])` `steps[]` array typically has FEWER entries because (a) Step 1 (`create_run` itself) is the entry point, not a step; (b) the `complete` step is a `workflow_runner.complete()` transition, NOT an entry in `steps[]`. **Example:** the sf-crawl-orchestrator has **9 Body Steps numbered** but **7 entries in `steps[]`** (preflight + crawl_trigger + poll + export_24_reports + atomic_move + invoke_sf_import + emit_provenance_and_report). This mirrors the dfs-pull / gsc-pull convention.

### Category B: EXTENDED skills (5)

| Skill | What changes | Effort | Risk |
|-------|--------------|--------|------|
| **ingestion/sf-import** | Frontmatter: add optional `source_run_id` input for provenance chaining; body Step 7 reads it if present. DURUR list unchanged. | S (1h) | LOW |
| **governance/drift-check** | Cross-sheet invariants get F-23 (optional): "if any project's workflow_runner has sf-crawl-orchestrator run, mcp-tool-registry MUST have sf entry". Drift-check existing 27 invariants stay green. | S (2h) | LOW |
| **governance/schema-validate** | Test fixture: validate new `sf-mcp-tool-mapping.schema.json` exists, parses, has valid example instance under `templates/sf-mcp/` | S (1h) | LOW |
| **meta/init-project** | Bootstrap step writes `project.config.sf` block defaults (mcp.enabled=false, allowed_directory=SF default). Migration 0005 retro-populates existing projects. | M (3h) | LOW |
| **meta/whats-next** | Routing logic adds suggestion: "Last crawl >30 days OR no crawl on record → consider /pseo-sf-crawl". Optional, doesn't block existing routes. | S (1.5h) | LOW |

### Category C: OPTIONAL CONSUMER skills (4)

These skills currently read SF data from `master.xlsx` only. v2 adds a flag to optionally CALL SF MCP for live data when needed.

| Skill | Current SF dependency | New SF MCP option | Default flag | Effort |
|-------|----------------------|-------------------|--------------|--------|
| **discovery/tech-audit** | Reads master.xlsx#tech_seo + sf-import:crawl_sitemap; uses DFS lighthouse | Add `use_sf_mcp_live: bool = False`. When True: call `mcp__sf__sf_generate_report(report_name="issues_overview_report")` for live JS/render issues before merging into tech_seo | False | M (4h) |
| **discovery/schema-audit** | Reads SF export CSV `structured_data_all.csv` from `sf-exports/{date}/raw/` | Add `use_sf_mcp_live: bool = False`. When True: call `mcp__sf__sf_generate_report(report_name="structured_data_all")` for inline CSV; bypass file requirement | False | M (4h) |
| **discovery/on-page-audit** | Reads master.xlsx + GSC + DFS | Add `use_sf_mcp_live: bool = False`. When True: cross-check `mcp__sf__sf_generate_report(report_name="page_titles_all")` for title/meta/h1 freshness | False | M (3h) |
| **planning/internal-links** | Reads sf-import:projects/{slug}/sf-exports/{date}/raw/ (inlinks CSV) | Add `use_sf_mcp_live: bool = False`. When True: call `mcp__sf__sf_generate_report(report_name="all_inlinks")` for live inlinks | False | M (3h) |

**Why opt-in by default:** Existing 1184 pytest baseline depends on file-based fixtures. Adding live MCP calls by default would break test determinism. Opt-in flag preserves zero regression while unlocking new capability.

### Category D: PASSIVE/NONE — no SF MCP relevance (34 skills)

These skills either don't touch SF data or consume it through master.xlsx (which is populated by sf-import regardless of how files arrive). No changes needed.

| Category | Skills | Why no SF MCP |
|----------|--------|---------------|
| ingestion (3) | gsc-pull, dfs-pull, scrapling-ops | Different MCPs |
| discovery (7) | cannibalization, content-decay, content-gaps, geo-analysis, gbp-audit, aio-competitor-map, quick-wins | GSC/DFS-based; quick-wins reads sf-import:crawl_sitemap passively (master.xlsx, no MCP call) |
| discovery (1) | competitive-analysis | LOW value — competitor SF crawl would require separate SF license/scope per competitor; future v1.2+ scope |
| governance (2) | glossary-audit, load-context | Doc-only governance |
| meta (2) | brand-onboarding, mark-done | No SF surface |
| planning (4) | cluster-map, master-task-sync, new-content-plan, topical-map | Keyword/task planning, no SF |
| production (5) | content-remediation, faq-optimization, generate-images, new-blog, revise-content | Content generation, no SF |
| publishing (2) | indexing-ping, verify-indexing | GSC-based |
| reporting (9) | monthly-report, monitoring-weekly, weekly-summary, portfolio-* (6) | Aggregation only |

**Net skill impact:** 1 NEW + 5 EXTENDED + 4 OPTIONAL_CONSUMER = 10 touched / 35 unchanged of the 44 existing skills (~23% touched, ~80% unchanged). After the +1 NEW skill, repo total goes 44 → 45 skills.

---

## Schemas Impact Matrix — All 22 Schemas

### EDIT existing (4)

| Schema | Change | Severity | Migration? |
|--------|--------|----------|------------|
| `mcp-tool-registry.schema.json` | `definitions.serverName.enum` (line 40) — add `"sf"`. Tool inventory in registry instance (not schema) lists sf_crawl, sf_crawl_progress, sf_generate_report, sf_list_crawls, sf_list_allowed_base_directory. http runtime already in `definitions.runtime` enum (line 47-51) — no schema change needed for transport. | ADDITIVE | NO |
| `events.schema.json` | `source.kind` enum (line 41-44) — add `"sf_mcp"`. `source.mcp_server` description — append " / sf" to allowed list. | ADDITIVE | NO (events.jsonl is append-only; old entries valid) |
| `skill-frontmatter.schema.json` | `mcp_tools.required[]` and `optional[]` patterns — verify allow `mcp__sf__*` (likely pattern-based, no change needed; confirm in implementation) | LIKELY NO-OP | NO |
| `project-config.schema.json` | `schema_version` const v1.4 → v1.5. Add OPTIONAL `sf` object: `{ mcp: { enabled: bool, url: uri, allowed_directory: string, crawl_config_path: string?, max_wait_minutes: int } }`. Required[] unchanged. | ADDITIVE | **YES — Migration 0005** |

### NEW (1)

| Schema | Purpose | Template source |
|--------|---------|-----------------|
| `sf-mcp-tool-mapping.schema.json` | Meta-schema for SF MCP use-case registry (mirrors gsc-tool-mapping pattern). Use-case keys: `crawl_trigger`, `crawl_progress_poll`, `report_export_inline`, `crawl_list`, `allowed_dir_discovery`. | Clone structure from `gsc-tool-mapping.schema.json` (it's the closest sister) |

### NO CHANGE (17)

| Schema | Why no change |
|--------|---------------|
| `master-excel.schema.json` | 18 sheets unchanged; SF MCP populates same sheets via existing sf-import projection |
| `sf-required-reports.schema.json` | Tier 1/2/3 report registry tied to file-based exports; SF MCP report names map to same canonical names |
| `sf-export-mapping.schema.json` | Filename normalization unchanged |
| `gsc-tool-mapping.schema.json` | Different MCP |
| `dataforseo-endpoint-mapping.schema.json` | Different MCP |
| `scrapling-output-mapping.schema.json` | Different MCP |
| `excel-config.schema.json` | Excel config unchanged |
| `excel-source-manifest.schema.json` | Source tracking already covers all source.kind values via events.jsonl (which is where source.kind=sf_mcp lands) |
| `workflow-run.schema.json` | Orchestrator uses existing create_run/start_step/finish_step/complete/fail; no new fields needed |
| `staging-to-excel-map.schema.json` | Orchestrator deposits files in sf-exports/; sf-import handles projection (no new mode) |
| `cross-sheet-invariants.json` | Existing 27 invariants don't reference MCP origin; OPTIONAL F-23 (sf registry presence) deferred |
| `consistency-report.schema.json` | Already tracks `claude mcp list` drift via mcp-tool-registry; sf joins automatically |
| `portfolio-config.schema.json` | Portfolio-level config, no per-MCP entries |
| `project-memory.schema.json` | Memory schema |
| `monthly-report.schema.json` | Report shape unchanged |
| `rules-frontmatter.schema.json` | Rule docs |

**Schema dependency graph (relevant subset):**

```
project-config.schema.json
    └─ refs: profiles enum (matches sf-required-reports tiers)
mcp-tool-registry.schema.json
    └─ refs: serverName enum (added "sf")
    └─ used by: schema-validate skill (consistency check)
events.schema.json
    └─ source.kind enum (added "sf_mcp")
    └─ used by: events_writer.append_provenance (Draft7 pre-validate)
sf-mcp-tool-mapping.schema.json (NEW)
    └─ uses: sf-required-reports canonicalName enum (for output_schema_file references)
    └─ used by: schema-validate (existence + instance validation)
```

### New Drift Invariants (v2.2 NEW — F-24/25/26 in `schemas/cross-sheet-invariants.json`)

| ID | Invariant | Detection | Severity | Added in Phase |
|----|-----------|-----------|----------|----------------|
| **F-23** | If any project's _state/workflows/ has sf-crawl-orchestrator run, mcp-tool-registry.json MUST list `sf` in servers | drift-check skill scans workflow JSONs for skill="sf-crawl-orchestrator"; cross-checks mcp-tool-registry servers | RED | Phase 4 |
| **F-24** (v2.2) | `mcp-tool-registry.json` keys MUST equal `.mcp.json` mcpServers keys (no missing, no extra) | drift-check sets-comparison; runs on every drift-check invocation | RED | Phase 4 |
| **F-25** (v2.2) | If `project.config.sf.mcp.enabled = true`, then `project.config.schema_version` MUST be >= "1.5" (sf block first available in v1.5) | drift-check per-project conditional check | RED | Phase 4 |
| **F-26** (v2.2) | No orphan SF crawl in SF GUI: if `_state/workflows/{run_id}.json` shows sf-crawl-orchestrator in status="paused" or "failed" AND `mcp__sf__sf_crawl_progress({crawl_id})` returns IN_PROGRESS, surface AMBER warning for operator cleanup | drift-check optional MCP-aware check (only runs when sf MCP responding); AMBER not RED to avoid spurious fails when MCP is down | AMBER | Phase 4 |

These bring total cross-sheet invariants from 27 (post-v1.7) → **31 (post-v1.8)** if all 4 land in Phase 4; if any deferred, count adjusts.

---

### Migration 0005 — project-config v1.4 → v1.5

| Attribute | Detail |
|-----------|--------|
| Path | `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py` |
| Trigger | `schema_version` field in project.config.json |
| Operation | Add default `sf` block: `{"mcp": {"enabled": false, "url": "http://127.0.0.1:11435/mcp", "allowed_directory": null, "crawl_config_path": null, "max_wait_minutes": 180}}` |
| Idempotent | YES — if `sf` already present, no-op; bump schema_version only |
| Test | `tests/scripts/test_migration_0005.py` (5 cases: bump_only, populate_defaults, idempotent_replay, missing_required, mixed_existing_field) |
| Rollback | Reverse migration writes schema_version back to "1.4" and removes `sf` block (test fixture) |

---

## Hooks Impact (6 hooks)

| Hook | Current behavior | SF MCP enhancement | Required? |
|------|------------------|---------------------|-----------|
| `session-start.json` | Prints PSEO workspace context | Could append "SF MCP: 11435 OK ✓" or "SF MCP: not detected" via `curl -sf http://127.0.0.1:11435/mcp/health \|\| echo offline` | **OPTIONAL** (v1.1+ if operator wants) |
| `pre-tool-use.json` | Excel lock + secrets scan | No SF impact (SF MCP calls don't write to master.xlsx directly) | NO CHANGE |
| `post-tool-use.json` | Audit event append via `scripts.state.events_writer.append_audit` | No SF impact (MCP calls auto-tracked via append_provenance from skill body) | NO CHANGE |
| `stop.json` | Runs `scripts/hooks/stop_validation.py` (drift + OQ scan, **<1s perf budget**) | `claude mcp list` call takes ~200-500ms — would consume ~50% of the <1s budget for a non-essential check. Drift-check skill (Phase 4 extension) already catches sf entry drift via cross-sheet invariants. **Recommendation: NO change to stop.json in v1.** Q-SF-MCP-08 RESOLVED → NO. | **NO (perf budget)** |
| `subagent-stop.json` | Subagent output schema sniff | No SF impact | NO CHANGE |
| `user-prompt-submit.json` | Injects PSEO context line | Could append "SF MCP: ON/OFF" hint when intent looks SF-related (regex match "screaming\|crawl") | **OPTIONAL** (v1.1+) |

---

## Commands Additions + Extensions (+2 NEW, 4 EXTENDED)

Current 16 commands map 1:1 to skills. **Two NEW commands + four EXTENDED existing commands** needed:

### NEW (2)

| Command | Skill backing | Description |
|---------|---------------|-------------|
| `/pseo-sf-crawl <slug> [url] [--resume <run_id>]` | sf-crawl-orchestrator | Trigger SF MCP crawl for project; poll until done; iterate 24-report export; move files; invoke sf-import. `--resume` flag for paused workflows (workflow_runner.resume) |
| `/pseo-sf-status [<slug>]` | (inline — no dedicated skill) | Show SF MCP connection state (`mcp__sf__sf_list_allowed_base_directory` probe), last crawl summary per project (from `_state/workflows/{run_id}.json` filter by skill=sf-crawl-orchestrator), allowed_directory mismatch check |

### EXTENDED existing (4) — v2.2 audit identified

| Command | Reason | Extension |
|---------|--------|-----------|
| `commands/pseo-status.md` (42 lines) | v2.2 audit: existing command shows project workflow status but not MCP connection state | Add new H2 section "SF MCP Status" with inline bash block calling `mcp__sf__sf_list_allowed_base_directory`; integrate into existing table |
| `commands/pseo-driftcheck.md` (42 lines) | drift-check skill gets F-23/24/25/26 invariants (Phase 4) | Update example output section to mention 31 invariants (was 27); add F-23/24/25/26 example violation messages |
| `commands/pseo-init.md` (48 lines) | init-project skill cascades Migration 0005 (Phase 4) | Add new flag `--schema-version=1.5` docs; add note about Migration 0005 auto-cascade for new projects |
| `commands/pseo-schema-audit.md` (49 lines) | schema-audit skill gets `use_sf_mcp_live` flag (Phase 5) | Document `--use-sf-mcp-live` flag exposing the skill input |

**Optional (deferred to v1.1+):** `/pseo-sf-import-mcp` (alias forcing MCP-only mode — currently sf-import is file-only; would invoke orchestrator without file fallback). Not in v1 scope.

Command file format matches existing `commands/pseo-*.md` markdown pattern (frontmatter + skill invocation block). All new + extended commands verified against `scripts/hooks/check_naming.py` regex `^pseo-[a-z][a-z0-9-]*$` — both `pseo-sf-crawl` and `pseo-sf-status` valid.

---

## Rules Impact (5 cross-referenced + 1 body edit)

| Rule | Why relevant | Action |
|------|--------------|--------|
| `schema-first.md` | New sf-mcp-tool-mapping.schema.json + project-config v1.5 must merge BEFORE any consumer code | Phase 1 enforces this ordering |
| `schema-versioning-discipline.md` | project-config v1.4→v1.5 requires Migration 0005 | Phase 1 (Migration) ordered before Phase 4+5 (consumer skill changes) |
| `naming.md` | Server name "sf" 3-char lowercase; tool naming `mcp__sf__<tool>` | Documented in D-SF-02 |
| `append-only-state.md` | events.jsonl gets new source.kind=sf_mcp entries; never mutates old entries | Verified by tests/scripts/test_events_writer.py extension |
| `budget-events.md` | SF MCP local (uses_paid_mcp: false); no budget guard needed in orchestrator | Frontmatter declares `uses_paid_mcp: false`, `estimated_credits: 0` |
| **`events-writer.md`** ⚠️ EDIT | **Line 129 currently has `\| sf-import \| normalize, project_excel \| local_xlsx \| Screaming Frog Excel transform \|` — sf-import row exists but no sf-crawl-orchestrator row. Phase 6 task adds a sibling row:** `\| sf-crawl-orchestrator \| ingest, staging \| sf_mcp \| Screaming Frog MCP-triggered crawl ingest \|` | Phase 6 documentation task |

**Other rules** (excel-discipline, glossary-discipline, secrets-management, single-source-of-truth, skill-description-discipline, skills.md, time-discipline, master-task-id, content-*, content-html-*, content-llm-*) — NO CHANGES; existing patterns apply to SF MCP automatically.

---

## Scripts Impact — v2.2 expanded after audit

### NEW scripts (3)

| Script | Purpose | LoC estimate |
|--------|---------|--------------|
| `scripts/ingestion/sf_crawl_orchestrator.py` | Pure transform: reads orchestrator config + workflow state, writes envelope, coordinates move/copy step + 24-report enumeration helpers. MCP HTTP calls happen in SKILL.md body (per gsc_pull.py pattern). | ~200 |
| `scripts/util/sf_mcp_client.py` | Reusable HTTP MCP client (first one). Handles JSON-RPC over HTTP, retry/timeout, response size cap. Pattern reusable for future HTTP MCPs. | ~150 |
| `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py` | Idempotent additive bump. Tests in test_migration_0005.py. Clones migration_0004 structure exactly. | ~80 |

### EDIT existing scripts (2 — v2.2 added whats_next.py)

| Script | Change | Phase |
|--------|--------|-------|
| `scripts/state/bootstrap_project.py` | Add `sf` block default when scaffolding new project.config.json (only if schema_version >= 1.5). Backward-compatible. | Phase 1 |
| `scripts/meta/whats_next.py` (17KB) | v2.2 audit: backing script for whats-next skill. Add T-9NNNN router band logic for "SF MCP available + last crawl > 30 days" → suggestion. Skill SKILL.md body change in Phase 4 requires matching script update. | Phase 4 |

### USE (not edit) — existing scripts

| Script | Phase | Usage |
|--------|-------|-------|
| `scripts/release/version_bump.py` (ADR-036 5-file sync) | Phase 6 | `python3 scripts/release/version_bump.py --to 1.8.0 --apply` — bumps plugin.json + marketplace.json + README banner + INSTALL banner + RELEASE_NOTES_v1.8.0.md existence check |
| `scripts/ci/run_skill_python.py` | Phase 1/4/7 | Validation: `python3 scripts/ci/run_skill_python.py skills/governance/{drift-check,schema-validate}/SKILL.md` after each change |

### NO CHANGE (explicit list — verified in audit)

| Script | Why no change | Verified |
|--------|---------------|---------|
| `scripts/state/workflow_runner.py` | Orchestrator uses existing create_run/start_step/finish_step/complete/fail + **pause/resume** (line 564+573) API | ✓ |
| `scripts/state/events_writer.py` | `append_provenance(source={"kind": "sf_mcp", ...})` accepted automatically after schema enum extension | ✓ |
| `scripts/state/{env, dump_workspace, migrate_legacy_events}.py` | Helper utilities, no SF surface | ✓ |
| `scripts/excel/{transaction, bootstrap_excel}.py` | sf-import calls them; no new write paths; 18 sheets unchanged | ✓ |
| `scripts/ingestion/{sf_import, gsc_pull, dfs_pull, scrapling_ops}.py` | sf-import accepts optional `--source-run-id` flag (minor frontmatter input — body intact); others untouched | ✓ |
| `scripts/validation/{validate_invariants, validate_schema}.py` | Existing pipeline picks up new schemas automatically (Draft7 sweep) | ✓ |
| `scripts/util/{url_normalize, dfs_response, profile_aware_defaults, iptc_metadata}.py` | Domain-specific; new `sf_mcp_client.py` adds alongside without conflict | ✓ |
| `scripts/hooks/stop_validation.py` | Q-SF-MCP-08 RESOLVED → NO (perf budget; <1s constraint blocks `claude mcp list`) | ✓ |
| `scripts/hooks/{check_naming, check_excel_writer, validate_before_write}.py + check_append_only.sh` | **v2.2 verified**: existing regexes (SLUG_RE, COMMAND_STEM_RE, SCHEMA_ID_RE in check_naming.py) accept `sf`, `pseo-sf-crawl`, `pseo-sf-status`, `sf-mcp-tool-mapping` without modification | ✓ |
| `scripts/hooks/subagent_output_validate.py` | Worker Output Package schema unchanged | ✓ |
| `scripts/security/check_secrets.sh` | No SF auth secrets (localhost no-auth); .env unchanged | ✓ |
| `scripts/ci/run_skill_python.py + check_secrets.sh` | Skill body executor works on new orchestrator skill automatically; secrets check unchanged | ✓ |
| `scripts/budget/check_budget.py` | **v2.2 verified**: sums only `dataforseo_mcp` cost.credits; SF MCP free (uses_paid_mcp:false in orchestrator frontmatter) so no budget tracking needed | ✓ |
| `scripts/maintenance/{data_hygiene_master_xlsx, fix_schema_id_format}.py` | Maintenance unchanged; new schemas pass fix_schema_id_format regex (SCHEMA_ID_RE) | ✓ |
| `scripts/meta/{brand_onboarding_*}.py` | G-AI-05 Phase 3 outputs; no SF surface | ✓ |
| `scripts/discovery/{cannibalization, content_decay, content_gaps, geo_analysis, gbp_audit, aio_competitor_map, quickwins, competitive_analysis, on_page_audit, tech_audit, schema_audit}_transform.py` | Pure-transform scripts; consumer skills' `use_sf_mcp_live` flag handled in SKILL.md body BEFORE calling transform script (merge in-memory) — scripts themselves untouched | ✓ |
| `scripts/planning/{cluster_map, internal_links, master_task_sync, new_content_plan, topical_map}_transform.py` | Same — internal_links body in Phase 5 merges live MCP inlinks before transform | ✓ |
| `scripts/reporting/{monthly_report, portfolio_*, render_template, weekly_summary}.py` | Aggregation only, consume master.xlsx data regardless of source | ✓ |

---

## Tests Plan (~42 cases: 30 new + 12 extended) — v2.2 adds DURUR-orch-8 atomic rollback test (10 total skill tests, was 9)

### NEW test files

| File | Cases |
|------|-------|
| `tests/skills/test_sf_crawl_orchestrator.py` | **10** — happy_path_24_reports; DURUR-orch-1 GUI not responsive; DURUR-orch-2 modal dialog; DURUR-orch-3 timeout; DURUR-orch-4 allowed-dir mismatch; DURUR-orch-5 target dir conflict; DURUR-orch-6 file move fail; DURUR-orch-7 concurrent-crawl (R13); **DURUR-orch-8 Tier 1 export fail → atomic rollback (D-SF-16)**; sf-import handoff success |
| `tests/scripts/test_sf_crawl_orchestrator.py` | **6** — HTTP mock (sf_crawl), poll loop, sf_generate_report iteration, file move atomicity, source_run_id chaining, error propagation |
| `tests/util/test_sf_mcp_client.py` (v2.2 location fix — `tests/util/` matches existing utility test convention: test_dfs_response.py, test_url_normalize.py, test_iptc_metadata.py) | **5** — JSON-RPC envelope, timeout, retry, response size cap, redirect handling |
| `tests/scripts/test_migration_0005.py` | **5** — bump_only, populate_defaults, idempotent_replay, missing_required, mixed_existing_field |
| `tests/schemas/test_sf_mcp_tool_mapping_schema.py` | **3** — schema validates, instance validates, unknown use-case rejected |
| `tests/smoke/test_sf_mcp_smoke.py` | **1** — live MCP smoke (skipif if MCP not connected, matches existing `tests/skills/conftest.py` skipif pattern per rules/skills.md Section 5) |

### EXTENDED tests (existing files +1 case each)

| File | New case |
|------|----------|
| `tests/skills/test_sf_import.py` | source_run_id chained from orchestrator appears in events.jsonl |
| `tests/skills/test_init_project.py` | sf block populated when schema_version >= 1.5 |
| `tests/skills/test_drift_check.py` | sf entry present in mcp-tool-registry when sf workflow detected |
| `tests/skills/test_schema_validate.py` | sf-mcp-tool-mapping.schema.json validates + has valid example |
| `tests/skills/test_tech_audit.py` | use_sf_mcp_live=True path mocks MCP and writes additional rows |
| `tests/skills/test_schema_audit.py` | use_sf_mcp_live=True path bypasses file requirement |
| `tests/skills/test_on_page_audit.py` | use_sf_mcp_live=True path adds live cross-check rows |
| `tests/skills/test_internal_links.py` | use_sf_mcp_live=True path fetches live inlinks |
| `tests/skills/test_whats_next.py` | SF MCP suggestion appears when last crawl > 30 days |
| `tests/scripts/test_events_writer.py` | sf_mcp source.kind accepted; events validate |
| `tests/schemas/test_events_schema_event_type_enum_v1_1.py` | sf_mcp in source.kind enum |
| `tests/schemas/test_instance_validation.py` | sf-mcp-tool-mapping instance valid |

**Existing baseline:** 1184 PASS / 11 SKIPPED / 0 FAIL (per memory).

**Target after v1.8 ship:**
- If "12 extensions" are NEW `test_*` functions in existing files: 1184 + 29 NEW + 12 NEW-in-existing = **1225 PASS** / 12 SKIPPED (+1 smoke) / 0 FAIL
- If "12 extensions" are inline assertions inside existing functions: 1184 + 29 = **1213 PASS** / 12 SKIPPED / 0 FAIL

Phase 3 implementation plan must lock the test function granularity to pin the target. Audit reconciliation: previous v2 draft said "~1210" which assumed extensions = inline and missed the R13 mitigation test (off by 3 from 1213; corrected here).

---

## Plugin Manifest Bump — via scripts/release/version_bump.py (5-file sync per ADR-036)

**CRITICAL CORRECTION (v2.2 audit):** Phase 6 MUST use `scripts/release/version_bump.py --to 1.8.0 --apply` instead of manual `.claude-plugin/plugin.json` edit. This script is the ADR-036 5-file authority and syncs:

1. `.claude-plugin/plugin.json` — top-level `"version"` field
2. `.claude-plugin/marketplace.json` — `metadata.version` + `plugins[0].description "v<semver> — "` prefix
3. `README.md` — `"> Status: **v<semver>**"` blockquote banner
4. `docs/INSTALL.md` — `"> Status: **v<semver>**"` blockquote banner
5. `docs/RELEASE_NOTES_v1.8.0.md` — existence check (WARN if missing; script NEVER auto-creates — must be authored manually as Phase 6 task)

Manual plugin.json description string edit (for the skill/command/MCP counts) is a SEPARATE Phase 6 task on top of version_bump.py execution.

### Description string drift fix (Phase 6 manual edit alongside version_bump.py)

```diff
- "description": "... 43 skill, 15 slash command, 6 hook, 3 MCP server.",
+ "description": "... 45 skill, 18 slash command, 6 hook, 4 MCP server.",
```

**Note on description drift:** plugin.json description currently reads "43 skill, 15 slash command" but actual file counts show **44 SKILL.md files + 16 commands/*.md files** (verified `find skills -name SKILL.md | wc -l` = 44; `ls commands/*.md | wc -l` = 16). v1.7 closeout updated counts in code but missed the manifest description string. Phase 6 fixes this drift while bumping to the v1.8 targets (45 skills + 18 commands). Hook count stays 6.

### Verification

```bash
# Dry-run first
python3 scripts/release/version_bump.py --to 1.8.0
# Expected output: planned changes to 5 files, no writes

# Apply
python3 scripts/release/version_bump.py --to 1.8.0 --apply
# Expected: 5 files updated; RELEASE_NOTES_v1.8.0.md existence WARNING resolved if created in same phase

# CI invariant test confirms 5-file sync correct
python3 -m pytest tests/ci/test_version_sync.py -v
# → PASS
```

---

## Documentation Updates (10 docs — v2.2 added INSTALL + REFERENCE_INDEX)

| Doc | Change |
|-----|--------|
| `README.md` | New H2 section "Screaming Frog 24 MCP (Optional)" with subsections: Setup, SF GUI Settings, .mcp.json snippet, First Crawl Walkthrough. Banner version updated by `version_bump.py`. |
| `docs/INSTALL.md` (v2.2 NEW) | Add SF MCP setup section alongside existing "claude mcp list" troubleshooting note. Banner version updated by `version_bump.py`. |
| `docs/WORKFLOWS.md` | New workflow: "Trigger SF crawl via MCP" with sequence diagram + Migration 0005 operator walkthrough |
| `docs/ARCHITECTURE.md` §7 | Update SF section: "v1.8+ supports MCP-primary (orchestrator iterates 24-report export) + file-based fallback (disaster recovery). MCP path requires SF 24 GUI open." |
| `docs/ARCHITECTURE.md` §16.5 | Update MCP discipline: "Four MCP servers: gsc/dataforseo/scrapling (stdio), sf (HTTP). HTTP transport requires endpoint_url in registry. mcp-tool-registry.json instance file now exists at repo root (Q-SF-MCP-09 default)." |
| `docs/OPEN_QUESTIONS.md` | Add Q-SF-MCP-01..11 entries (all 11 questions per v2.2 spec). Mark Q-08 RESOLVED. |
| `docs/DECISIONS.md` | Add ADR-031: "v1.8 Hybrid MCP-primary file-fallback SF integration — preserves envelope discipline + adds operator-driven trigger + atomic 24-report semantics" |
| `docs/RELEASE_NOTES_v1.8.0.md` | NEW: full release notes for v1.8 (SF MCP, MCP-primary pivot, schema bumps incl. Migration 0005, 4 consumer skill flags, 18 D-SF decisions, 11 Q-SF-MCP). version_bump.py WARNs if missing — manually author. ≥100 lines per v1.7 pattern. |
| `docs/PHASE_STATUS.md` | Update: v1.8.0 milestone declared, scope = SF MCP MCP-primary integration |
| `docs/REFERENCE_INDEX.md` (v2.2 NEW) | Add entries: sf-crawl-orchestrator skill, sf_mcp_client utility, pseo-sf-crawl + pseo-sf-status commands, sf-mcp-tool-mapping schema, mcp-tool-registry.json instance, Migration 0005 |
| `docs/GLOSSARY.md` | Add 4 terms from Glossary section: SF MCP, SF orchestrator, Optional consumer, Hybrid mode |
| (cross-ref) `rules/events-writer.md` line 129 | Body edit covered in Rules Impact — adds sf-crawl-orchestrator row |

---

## .mcp.json Configuration

### Current (3 servers, all stdio):

```json
{
  "mcpServers": {
    "gsc": { "command": "bash", "args": ["-c", "set -a; [ -f .env ] && source .env; set +a; exec npx -y mcp-server-gsc@0.3.0"] },
    "dataforseo": { "command": "bash", "args": ["-c", "set -a; [ -f .env ] && source .env; set +a; exec npx -y dataforseo-mcp-server@2.8.10"] },
    "ScraplingServer": { "command": "${SCRAPLING_BIN:-scrapling}", "args": ["mcp"] }
  }
}
```

### After (4 servers — `sf` added):

```json
{
  "mcpServers": {
    "gsc": { "command": "bash", "args": ["-c", "set -a; [ -f .env ] && source .env; set +a; exec npx -y mcp-server-gsc@0.3.0"] },
    "dataforseo": { "command": "bash", "args": ["-c", "set -a; [ -f .env ] && source .env; set +a; exec npx -y dataforseo-mcp-server@2.8.10"] },
    "ScraplingServer": { "command": "${SCRAPLING_BIN:-scrapling}", "args": ["mcp"] },
    "sf": { "url": "http://127.0.0.1:11435/mcp" }
  }
}
```

**Memory invariant note (F-16):** Memory mentioned ".mcp.json 482B byte-byte korundu 47+ commit cumulative". This v1.8 release breaks that invariant **intentionally** — first deliberate growth since v1.5. F-16's purpose (catch silent drift) served; intentional schema growth is a deliberate diff committed atomically with the v1.8 release.

---

## SF GUI Settings — Recommended (per operator screenshot)

| Setting | Recommended | Currently | Action |
|---------|-------------|-----------|--------|
| Port | `11435` | `11435` ✓ | No change |
| Max Response Size (Bytes) | `100000` | `100000` ✓ | No change (D-SF-05) |
| Directory | `/Users/apple/seo_spider_mcp_server` | Valid ✓ | No change (D-SF-03) |
| Node.js Runtime Environment | ☐ Unchecked | ☐ Unchecked | **Keep unchecked** (D-SF-04) |
| MCP Server status | **Start** (click green button) | Stopped | Operator clicks "Start MCP Server" |

**Post-start verification (operator action):**

1. Click "View Tools" — should list `sf_crawl`, `sf_crawl_progress`, `sf_generate_report`, `sf_list_crawls`, `sf_list_allowed_base_directory` minimum
2. Test from terminal: `curl http://127.0.0.1:11435/mcp/tools`
3. After `.mcp.json` edit + Claude Code session restart: `claude mcp list` should show `sf` connected

---

## MCP-Primary Data Flow + 24-Report Loop (v2.2 NEW)

### The 24-Report Inventory

Orchestrator iterates `sf_generate_report(report_name=X, save_report=True)` for each of these canonical names (matches `sf-required-reports.schema.json canonicalName` enum + `scripts/ingestion/sf_import.py:37-47` TIER1_REQUIRED + TIER2_RECOMMENDED frozensets):

**Tier 1 (14 mandatory — RED FAIL if missing):**

1. internal_all
2. all_inlinks
3. all_outlinks
4. response_codes_all
5. issues_overview_report
6. page_titles_all
7. meta_description_all
8. h1_all
9. canonicals_all
10. directives_all
11. indexability
12. structured_data_all
13. sitemaps_all
14. redirect_chains

**Tier 2 (10 recommended — AMBER if missing, NOT fatal):**

15. h2_all
16. images_all
17. hreflang_all
18. orphan_pages
19. all_anchor_text
20. near_duplicates_report
21. exact_duplicates_report
22. search_console_all
23. crawl_depth
24. pagination_all

**Tier 3 (16 optional — silent if missing; Q-SF-MCP-10 decides v1 inclusion; default = NOT included):**

`security_all, javascript_all, response_times_all, word_count, broken_internal_links, broken_external_links, images_missing_alt, page_speed_insights, ga_integration, meta_keywords, pdf_all, amp_all, urls_not_in_sitemap, xml_sitemap_urls_not_in_internal, canonical_mismatch, links_to_noindex`

### 24-Report Loop Pseudocode

```python
# In sf-crawl-orchestrator SKILL.md body (Step 6 of orchestrator protocol)
TIER1 = [...14 names...]  # imported from sf-required-reports schema
TIER2 = [...10 names...]

temp_staging = workspace_root / "projects" / project_slug / "_state" / "staging" / f"sf-crawl-{run_id}"
temp_staging.mkdir(parents=True, exist_ok=True)

per_report_timeout = project_config.get("sf", {}).get("mcp", {}).get("per_report_timeout_seconds", 300)  # Q-SF-MCP-11 default 5min
amber_missing_t2 = []

for idx, report_name in enumerate(TIER1 + TIER2, start=1):
    workflow_runner.start_step(run_id, step_idx_for_report(report_name), project_slug=project_slug)
    try:
        response = mcp__sf__sf_generate_report(
            crawl_id=crawl_id,
            report_name=report_name,
            save_report=True,
            output_dir=str(sf_allowed_directory),  # SF writes here
            timeout=per_report_timeout,
        )
        # SF writes CSV to allowed_directory; response includes file path
        sf_csv_path = Path(response["file_path"])
        if not sf_csv_path.exists():
            raise SFExportError(f"SF claimed success but file missing: {sf_csv_path}")
        # Atomic move to temp staging (NOT final sf-exports/ yet — atomic crawl D-SF-16)
        shutil.move(sf_csv_path, temp_staging / f"{report_name}.csv")
        workflow_runner.finish_step(run_id, step_idx_for_report(report_name), project_slug=project_slug,
                                    output_ref=f"{report_name}.csv")
    except SFExportError as e:
        if report_name in TIER1:
            # DURUR-orch-8: Tier 1 missing → atomic rollback
            shutil.rmtree(temp_staging)
            workflow_runner.fail(run_id, project_slug=project_slug, code="tier1_export_failed",
                                 message=f"Tier 1 report '{report_name}' export failed: {e}", step_index=idx)
            raise SystemExit(8)
        else:
            # Tier 2 missing → AMBER, continue (matches existing sf-import Tier policy)
            amber_missing_t2.append(report_name)
            workflow_runner.finish_step(run_id, step_idx_for_report(report_name), project_slug=project_slug,
                                        output_ref=f"AMBER:missing")

# All 14 Tier 1 + (10 - len(amber_missing_t2)) Tier 2 succeeded
# Atomic move: temp_staging → sf-exports/{date}/raw/
final_dir = workspace_root / "projects" / project_slug / "sf-exports" / today.isoformat() / "raw"
final_dir.parent.mkdir(parents=True, exist_ok=True)
if final_dir.exists():
    # DURUR-orch-5: target dir conflict
    raise SystemExit(5)
shutil.move(temp_staging, final_dir)  # atomic on same filesystem

# Hand off to sf-import (existing skill)
sf_import_subprocess.run([
    sys.executable, "-m", "scripts.ingestion.sf_import",
    "--project", project_slug,
    "--sf-export-path", str(final_dir.parent),
    "--source-run-id", run_id,
])
```

### Schema-First Note: `failure_reason.code` vs DURUR Tokens (v2.3 retro — R-3 / Q-PHASE-3-WORKER-06)

The custom failure-code names in the pseudocode above and elsewhere in this section (`sf_mcp_offline`, `tier1_export_failed`, etc.) are **illustrative DURUR-NN tokens** intended for the human-readable `failure_reason.message` field — NOT for the mechanical code field. The `failure_reason.code` field is ALWAYS one of the `workflow-run.schema.json` CLOSED enum values:

```
validation_error / mcp_error / budget_exhausted / user_rejected / timeout / internal_error
```

So `workflow_runner.fail(run_id, code="tier1_export_failed", ...)` above is shorthand; the schema-conformant call sets `code="mcp_error"` (or another enum value) and carries the DURUR identity in `message` (e.g. `message="DURUR-orch-8: Tier 1 report 'X' export failed"`). v1.8 Phase 3 mapped: orch-1/2/7/8 → `mcp_error`; orch-4/5 → `validation_error`; orch-3 → `timeout`; orch-6 → `internal_error`.

### Resume Semantics (workflow_runner.pause / resume)

If SF MCP crashes mid-loop (e.g., after report #17):

1. Orchestrator catches HTTPError → `workflow_runner.pause(run_id, reason="sf_mcp_unavailable")` → state = paused, paused_at = now
2. Temp staging dir `_state/staging/sf-crawl-{run_id}/` PRESERVED (17 of 24 CSVs already there)
3. Operator restarts SF GUI + MCP server
4. Operator runs `/pseo-sf-crawl --resume {run_id}` (new command flag)
5. Orchestrator: `workflow_runner.resume(run_id)` → state = running, paused_at preserved (append-only per `rules/append-only-state.md`)
6. Loop scans temp_staging, skips report names already present (idempotent)
7. Continues from report #18; completes normally

`workflow_runner.pause` at line 564 + `workflow_runner.resume` at line 573 of `scripts/state/workflow_runner.py` — both verified to exist with `paused_at` survival across resume (line 16 docstring).

### Backward Compat: File-Drop Fallback Still Works

```
Operator sets project.config.sf.mcp.enabled = false (or just doesn't trigger /pseo-sf-crawl)
    ↓
Drops CSVs manually → projects/{slug}/sf-exports/{date}/raw/  (legacy workflow, unchanged)
    ↓
Runs `python3 scripts/ingestion/sf_import.py --project {slug} --sf-export-path projects/{slug}/sf-exports/{date}/`
    ↓
sf-import 8-step protocol (UNCHANGED) → 6 sheets + envelope + events
```

This path is **never deprecated** — it's the disaster-recovery fallback when SF MCP is unavailable. Phase 7 pilot smoke includes a verification run on this path to prove regression-free.

---

## Data Flow — 4 Scenarios

### Scenario 1: Operator-triggered crawl (orchestrator happy path)

Updated for MCP-primary v2.2: see "24-Report Loop Pseudocode" above. Replaces v1 single-report scenario.

### Scenario 2: File-only manual import (backward compat)

```
Operator drops CSVs → projects/vento/sf-exports/2026-05-26/raw/
    ↓
Invokes /pseo-sf-import or sf-import skill directly
    ↓
sf-import 8-step protocol (UNCHANGED) → 6 sheets + envelope + events
```

**Zero change** from current behavior. SF MCP not involved.

### Scenario 3: tech-audit with live SF MCP cross-check (opt-in)

```
Operator: "tech audit yap, SF MCP'den canlı kontrol et"
    ↓
tech-audit skill invoked with use_sf_mcp_live=true
    ↓
Step 1-3: existing DFS lighthouse + content_parsing flow
    ↓
NEW Step 3.5: mcp__sf__sf_generate_report(report_name="issues_overview_report")
    → inline CSV (subject to 100KB cap)
    → parse + merge new tech_seo rows
    ↓
Step 4-N: existing projection to master.xlsx#tech_seo
```

### Scenario 4: Migration 0005 retro-fit on existing project

**Note:** load-context skill does NOT auto-invoke migrations (verified — it's a read-only context aggregator per Category D classification). Migration is **operator-triggered** OR cascaded from init-project for new projects. This is consistent with how migrations 0001-0004 work (manual execution per `rules/schema-versioning-discipline.md`).

```
Operator runs: python3 scripts/migrations/migration_0005_project_config_1_4_to_1_5.py \
    --in projects/vento/project.config.json [--out PATH] [--dry-run]
    ↓
Migration validates source schema_version (refuses if not in {1.4, 1.5} per strict mode)
    ↓
Idempotent: re-running on 1.5 doc is no-op (matches 0004 pattern)
    ↓
Adds sf block default (mcp.enabled=false, url=http://127.0.0.1:11435/mcp, max_wait_minutes=180), bumps schema_version to 1.5
    ↓
Writes .bak backup in in-place mode (default; omit --out); re-validates against project-config.schema.json v1.5
    ↓
Audit summary to stderr (per 0004 pattern)
    ↓
Operator can now /pseo-sf-crawl vento (opt-in by setting mcp.enabled=true in config or via /pseo-sf-status)
```

**Operator workflow:** A new doc section in `docs/WORKFLOWS.md` (Phase 6 task) walks operators through this command for each of the 9 existing projects.

### events.schema `source` Dict — Canonical Keys (v2.3 retro — R-4 / Q-PHASE-3-WORKER-07)

Whenever any scenario above emits an `sf_mcp` provenance event via `append_provenance(source={...})`, the `source` dict is schema-constrained (`events.schema.json` sets `source.additionalProperties=false`):

```
# events.schema source.additionalProperties=false; valid keys ONLY:
#   kind / source_folder / filename_original / filename_normalized / file_hash /
#   row_count / response_bytes / mcp_server / mcp_tool
# crawl_id + other arbitrary properties go in the inbox/sf-mcp/{date}-sf-crawl-{slug}.json
# envelope (the envelope JSON allows arbitrary properties).
```

So a naive `source={"kind":"sf_mcp","crawl_id":...}` would FAIL validation (`crawl_id` is not an allowed `source` key). The schema-conformant emission uses `source={"kind":"sf_mcp","mcp_server":"sf","mcp_tool":"sf_generate_report","response_bytes":...,"row_count":...}` and keeps `crawl_id` in the ingestion envelope, not the event source dict.

---

## Compatibility Matrix vs Other MCPs

| Layer | gsc (stdio/npx) | dataforseo (stdio/npx) | ScraplingServer (stdio/bin) | **sf (HTTP) [NEW]** |
|-------|-----------------|------------------------|-----------------------------|----------------------|
| Registry serverName | `gsc` | `dataforseo` | `scrapling` (note: registry uses lowercase; .mcp.json key is `ScraplingServer` capital) | **`sf`** |
| Tool naming pattern | `mcp__gsc__*` | `mcp__dataforseo__*` | `mcp__ScraplingServer__*` | **`mcp__sf__*`** |
| Mapping schema | gsc-tool-mapping | dataforseo-endpoint-mapping | scrapling-output-mapping | **sf-mcp-tool-mapping (NEW)** |
| events.jsonl source.kind | gsc_mcp | dataforseo_mcp | scrapling_local / scrapling_mcp | **sf_mcp [+ existing sf_csv for file-path]** |
| Auth | OAuth (env) | API key (env) | None (local) | **None (localhost)** |
| Budget | Free (200 req/100s) | Paid (credits) | Local (no budget) | **Local (no budget)** |
| Cache layer | gsc cache_ttl_hours per use-case | DFS endpoint-level TTL | scenario-level | **None in v1 (crawl is one-shot)** |
| Workflow integration | workflow_runner.create_run | workflow_runner.create_run | workflow_runner.create_run | **workflow_runner.create_run** |
| URL normalization | mandatory (D-03) | mandatory (D-03) | mandatory (D-03) | **inherited via sf-import** |
| Test fixture pattern | conftest.py mock | conftest.py mock | conftest.py mock | **conftest.py mock + smoke skipif** |

**Net compatibility:** SF MCP slots into the same governance pattern as the 3 existing MCPs. The only structural exception is **HTTP transport** (vs stdio for the other 3), and `mcp-tool-registry.schema.json` already supports HTTP runtime (endpoint_url required) — no new exception logic needed.

---

## Risks + Mitigations (expanded from v1)

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | SF GUI not running when orchestrator invoked | HIGH | Run fails | Orchestrator preflight: clear operator message + remediation |
| R2 | Modal dialog open in SF settings → `IllegalStateException` | MEDIUM | Opaque error | Catch + surface operator-actionable message |
| R3 | Crawl > max_wait_minutes | LOW | Timeout, no Excel write | DURUR-orch-3; partial files remain; retry extendable |
| R4 | File move fails (permissions/disk) | LOW | Data stranded | Atomic shutil.move; on failure log SF dir path for rescue |
| R5 | Port 11435 conflict with other local service | LOW | SF MCP fails to start | Operator changes port in SF + .mcp.json (D-SF-01) |
| R6 | Operator accidentally enables Node.js Runtime → security | LOW | Arbitrary code exec via SF | Doc explicit: "Do not enable unless specifically needed" |
| R7 | Third-party blog reports drift from actual SF behavior | MEDIUM | Spec assumptions stale | Phase 1 includes "smoke test connect + list tools" before further work |
| R8 | SF version downgrade (rollback to v23) | LOW | MCP gone | Orchestrator preflight detects + falls back to file-only instructions |
| R9 | **NEW** — Optional consumer flag enabled in skill but SF MCP unavailable | MEDIUM | Skill fails mid-execution | Each consumer's `use_sf_mcp_live=True` path includes preflight check; falls back to file-only mode with AMBER warning |
| R10 | **NEW** — Migration 0005 fails on a project with malformed v1.4 config | LOW | Project unusable | Migration is idempotent + has rollback test; failure leaves config untouched |
| R11 | **NEW** — events.jsonl size growth from MCP polling events | LOW | Events file bloat | Polling emits ONE workflow event per crawl_started + crawl_completed (not per poll); 64KB cap per event enforced |
| R12 | **NEW** — 100KB cap truncates sf_generate_report response → silent data loss | MEDIUM | Discovery skill gets partial data | Response includes `truncated: true` flag check; AMBER warning if truncated; operator informed to use file-based path |
| R13 | **NEW** — Multiple projects' orchestrators competing for SF GUI | LOW (single-user) | Concurrent crawl conflict | **v1 concrete guard:** orchestrator preflight calls `mcp__sf__sf_list_crawls` (enumerator; no `crawl_id` argument needed — v2.3 retro R-2 / Q-PHASE-3-WORKER-05; the per-crawl `sf_crawl_progress` would be circular here since it requires a `crawl_id`) BEFORE `sf_crawl`. If any listed crawl has status=IN_PROGRESS (regardless of project), emit DURUR-orch-7: "Another crawl active in SF GUI. Wait for completion or cancel via SF, then retry." This eliminates silent contention without requiring cross-project lock. Long-term cross-project lock primitive deferred to v1.2+ per Q-SF-MCP-06. |

---

## Implementation Phase Outline (7 phases, ~8 days realistic — v2.2 production-ready audit added Phase 3 + Phase 6 effort bumps)

The `writing-plans` skill produces detailed task-by-task plan after operator approves this v2 spec. Anticipated structure:

> **Pre-Phase 3 gates** (must be resolved before Phase 3 starts): Q-SF-MCP-02 (requires_approval default), Q-SF-MCP-04 (move vs copy), Q-SF-MCP-05 (auto-invoke sf-import). These are phase-design gates — orchestrator code shape depends on these answers.
>
> **Pre-Phase 5 gates:** Q-SF-MCP-07 (consumer rollout all-4 vs 2+2 staging). Determines Phase 5 scope/effort.
>
> **Pre-Phase 1 gates:** Q-SF-MCP-09 (mcp-tool-registry.json instance location). Determines where Phase 1 task #6 writes the file.

| Phase | Scope | Effort | Risk |
|-------|-------|--------|------|
| **Phase 1** — Schema-first foundation | (1) mcp-tool-registry schema edit (add `sf` to serverName enum); (2) events.schema edit (add `sf_mcp` to source.kind enum); (3) NEW sf-mcp-tool-mapping schema (clone gsc-tool-mapping pattern); (4) project-config v1.4→v1.5 schema edit (additive sf block); (5) Migration 0005 script (clone migration_0004 pattern: idempotent + strict + dry-run + .bak); (6) **NEW: Create initial `mcp-tool-registry.json` instance file at path per Q-SF-MCP-09 covering all 4 servers (gsc + dataforseo + scrapling + sf) with full tool inventory**; (7) **NEW: scaffold `templates/sf-mcp/` with `.gitkeep` + 1 example use-case instance**; (8) **NEW: edit `scripts/state/bootstrap_project.py` to emit sf block when schema_version >= 1.5**; (9) 5 schema/migration test cases + idempotent replay fixture + rollback fixture | **1.25 day** | LOW |
| **Phase 2** — MCP utility + .mcp.json | (1) `scripts/util/sf_mcp_client.py` HTTP JSON-RPC client (~150 LoC: envelope, retry/timeout, response size cap, redirect handling); (2) 5 client unit tests; (3) **NEW: explicit ADR-031 commit note in DECISIONS.md acknowledging intentional .mcp.json byte-growth (breaking F-16 invariant under controlled diff)**; (4) .mcp.json sf entry add; (5) manual smoke: `claude mcp list` shows sf connected; (6) Phase 1 prereq verified | **0.5 day** | LOW |
| **Phase 3** — Orchestrator skill | (1) NEW `skills/ingestion/sf-crawl-orchestrator/SKILL.md` (full body with **8 DURURs** incl. R13 concurrent-crawl guard + D-SF-16 atomic rollback); (2) `scripts/ingestion/sf_crawl_orchestrator.py` (~200 LoC pure transform; HTTP calls in SKILL.md body, not script per gsc_pull pattern); (3) **10 skill tests** (happy_path_24_reports + 8 DURUR cases + sf-import handoff success); (4) 6 script tests (HTTP mock, poll loop, sf_generate_report iteration, file move atomicity, source_run_id chaining, error propagation); (5) **NEW: 3 preflight tests explicit for R1/R2/R8 (GUI-closed detection, IllegalStateException catch, version downgrade)**; (6) 1 smoke test (skipif if MCP not connected); (7) **NEW: per-project fcntl workflow_runner lock verification (R13 base + DURUR-orch-7 concurrent guard test)**; (8) Q-02/04/05 design answers integrated into frontmatter; (9) **NEW v2.2: `templates/reports/sf-crawl.template.md`** (orchestrator run summary report template, mirroring `templates/reports/dfs-pull.template.md` + `gsc-pull.template.md` pattern — 7 sections: Summary, 24 Reports Status, Tier 1 / Tier 2 Counts, AMBER Warnings, sf-import Handoff Result, Total Duration, Recommendations) | **2.5 days** (v2.2: +0.5 day for 24-report loop + atomic semantics + resume capability + report template) | MEDIUM |
| **Phase 4** — Existing skill extensions | (1) sf-import frontmatter accepts optional `source_run_id` input (8-step body UNCHANGED); (2) drift-check skill: add cross-sheet invariant F-23 (if any project has sf-crawl-orchestrator workflow record, mcp-tool-registry instance MUST have sf entry); (3) **NEW: F-23 entry added to `schemas/cross-sheet-invariants.json` (not just narrative — the actual JSON edit)**; (4) schema-validate skill: extend to validate sf-mcp-tool-mapping schema + 1 example instance under templates/sf-mcp/; (5) init-project skill: cascade Migration 0005 for new projects; (6) whats-next skill: routing logic for "last crawl > 30 days" suggestion; (7) 5 corresponding test extensions; (8) **NEW: D-SF-09 verification test — confirm no cron entry registered in any hook for sf-crawl-orchestrator** | **1 day** | LOW |
| **Phase 5** — Optional consumer wiring | 4 discovery/planning skills get `use_sf_mcp_live: bool = False` flag: tech-audit, schema-audit, on-page-audit, internal-links. For each: (a) frontmatter flag; (b) body branch (preflight check + AMBER fallback per R9); (c) **NEW: R12 truncation detection (sf_generate_report response.truncated flag → AMBER warning + continue with partial data OR fail per Q-07 answer)**; (d) mock-based test (use_sf_mcp_live=True path); (e) regression test (use_sf_mcp_live=False default unchanged). Scope depends on Q-SF-MCP-07 answer (all-4 vs 2+2 staging). | **1.5 day** (all-4) or **0.75 day** (2+2 staging) | MEDIUM |
| **Phase 6** — Commands + manifest + docs (v2.2 expanded: +4 command extensions + 2 docs) | (1) NEW `commands/pseo-sf-crawl.md` (markdown command frontmatter + --resume flag docs); (2) NEW `commands/pseo-sf-status.md` (4-column table output spec + inline `mcp__sf__sf_list_allowed_base_directory` probe); (3) **MANDATORY use of `scripts/release/version_bump.py --to 1.8.0 --apply`** (5-file sync per ADR-036: plugin.json + marketplace.json + README banner + INSTALL banner + RELEASE_NOTES v1.8.0 existence check); (4) MANUAL plugin.json description fix (43→45 skill, 15→18 command, 3→4 MCP server — fixes pre-existing v1.7 drift on top of version_bump.py); (5) **EXTEND `commands/pseo-status.md`** with new H2 "SF MCP Status" section; (6) **EXTEND `commands/pseo-driftcheck.md`** with F-23/24/25/26 example output (invariants 27→31); (7) **EXTEND `commands/pseo-init.md`** with --schema-version=1.5 flag docs + Migration 0005 cascade note; (8) **EXTEND `commands/pseo-schema-audit.md`** with --use-sf-mcp-live flag docs (exposes Phase 5 skill input); (9) README.md SF MCP section (H2 + 3 subsections; banner updated by version_bump.py); (10) docs/WORKFLOWS.md SF crawl workflow + Migration 0005 operator walkthrough; (11) docs/ARCHITECTURE.md §7 + §16.5 updates; (12) docs/OPEN_QUESTIONS.md Q-SF-MCP-01..11 entries; (13) docs/DECISIONS.md ADR-031 (already added Phase 2 — verify); (14) docs/RELEASE_NOTES_v1.8.0.md NEW (≥100 lines, v1.7 structure — version_bump.py WARNs if missing but never auto-creates); (15) docs/PHASE_STATUS.md v1.8 milestone; (16) docs/GLOSSARY.md SF MCP terms; (17) **NEW v2.2: docs/INSTALL.md SF MCP setup section** (alongside existing "claude mcp list" troubleshooting); (18) **NEW v2.2: docs/REFERENCE_INDEX.md entries** (sf-crawl-orchestrator, sf_mcp_client, pseo-sf-* commands, sf-mcp-tool-mapping); (19) **rules/events-writer.md line 129 update** (add sf-crawl-orchestrator row alongside existing sf-import) | **1.25 day** (v2.2: +0.25 day for 4 command extensions + 2 doc additions) | LOW |
| **Phase 7** — Pilot smoke + release | (1) Live run on vento end-to-end; (2) record AC-10 + AC-13 evidence to PHASE_STATUS.md; (3) drift-check 27 invariants re-run GREEN (AC-17); (4) schema-validate full sweep GREEN (AC-18); (5) full pytest baseline GREEN (target ~1210 PASS / 12 SKIPPED / 0 FAIL — AC-16); (6) git tag v1.8.0 annotated; (7) **NEW: rollback drill — verify operator can revert via `git revert {commit-range}` + Migration 0005 reverse runs cleanly + 1184 v1.7 baseline restored** | **0.75 day** | LOW |
| **Total** | **~8 days (~60 hours focused work)** — v2.2 audit: +0.5 day Phase 3 (24-report loop + atomic + resume + report template) + 0.25 day Phase 6 (4 command extensions + 2 doc additions); was "~7 days" in v2.1; was "~4 days" in pre-audit | — | — |

**Phase ordering verification:** Each phase only depends on outputs of phases 1..N-1. Phase 1 has no upstream deps. Phase 2 depends on Phase 1 (mcp-tool-registry schema must accept sf before instance file can be valid). Phase 3 depends on Phase 1 (schemas) + Phase 2 (client utility). Phase 4 depends on Phase 3 (orchestrator workflow shape for invariant F-23). Phase 5 depends on Phase 3 (consumer flag pattern needs sf_mcp_client utility). Phase 6 depends on all prior (docs reflect actual state). Phase 7 depends on all.

**v2.2 audit Phase effort bumps:** Phase 3: 2 → **2.5 days** (24-report loop + atomic + resume + report template). Phase 6: 1 → **1.25 days** (4 command extensions + 2 doc additions). **New total = ~8 days (~60 hours)** — slightly over "~1 week" sprint budget but still feasible if operator extends sprint by 1 day OR defers Phase 5 (consumer wiring) to v1.9 per Q-SF-MCP-07 staging option (would drop total to ~6.5 days).

---

## Multi-Session Execution Model (v2.2 NEW)

> Operator's context-efficiency requirement: "context'i çok kıymetli şekilde kullanacağız bu yüzden batchlere bölmeliyiz ve fresh session'larla ilerleyeceğiz. bir tane karar verici session olacak birde sürekli planı uygulayan bir session"

### Manager Session (this session) — Decision-Maker Role

Per `docs/SESSION_PROTOCOL.md` §13.1, the Manager Session is the **decision-maker, not the main worker**. Responsibilities:

- Holds the spec + plan in context (v2.2 = ~1100 lines after additions, fits comfortably in 200K window with room for ~150K worker output processing)
- Generates Worker Prompts from companion file `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md`
- Processes Worker Output Packages (compact return per `SESSION_PROTOCOL.md` §13.4 format)
- Updates `docs/PHASE_STATUS.md`, `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md`, `docs/CONTEXT_LEDGER.md` between phases
- Makes phase gateway decisions (GO/NO-GO to next phase based on Worker verification)
- Resolves Q-SF-MCP-* open questions as they surface

**Manager does NOT:**
- Read full worker transcripts (only Worker Output Packages)
- Touch implementation files directly (delegates to Workers)
- Carry full implementation context (each Worker briefs itself from prompt + spec)

### Worker Sessions (fresh per Phase) — Implementation Role

One **fresh Worker Session per Phase** (7 total). Each Worker:

1. Receives self-contained prompt from companion file (Prompt 1..7)
2. Bootstraps via `SESSION_PROTOCOL.md` §13.2 fresh wakeup sequence (<15KB initial load)
3. Reads ONLY files listed in its prompt (no spec-wide scan)
4. Executes the phase tasks in the order listed in Phase Outline
5. Runs the verification commands (each task has explicit pytest/bash command)
6. Returns Worker Output Package to Manager
7. Session ends — no carryover

**Phase ordering enforces serial execution:** Phase 2 cannot start until Phase 1 Worker returns its Output Package and Manager confirms GO. Workers do NOT run in parallel (data dependencies between phases).

### Worker Output Package Format (per SESSION_PROTOCOL.md §13.4)

```markdown
## Worker Output Package

**Worker:** Phase {N} — {phase name}
**Phase:** v1.8 Phase {N}
**Task:** {short description}

### Files Created/Modified
- path/to/file.json (NEW, 142 lines)
- path/to/other.py (MODIFIED, +47/-3)

### Decisions Made
- {decision 1, 1 line}

### Open Questions Surfaced
- {q1, 1 line — if any new Q emerges during implementation}

### Next Step Recommended
- Manager: proceed to Phase {N+1} OR resolve open question first

### Verification
- [x] {test_command_1} → PASS
- [x] {test_command_2} → PASS
- [ ] {test_command_3} → SKIPPED (reason)
```

Manager reads this package, updates state docs, and decides next action. **Does not read worker's full transcript** (context efficiency).

### Coordination Channel — git + workflow_runner state

Between Workers, state lives in:

| Artifact | Purpose | Read by Manager? | Read by next Worker? |
|----------|---------|------------------|----------------------|
| `git log --oneline` | What Workers have committed | Yes (verify Phase N commit landed) | No (Worker doesn't need prior phase commits) |
| `docs/PHASE_STATUS.md` | Current phase + last completed | Manager updates after each package | Worker reads in §13.2 wakeup |
| `_state/workflows/{run_id}.json` (per project) | If Phase 7 pilot smoke runs orchestrator | Read by Manager during Phase 7 review | Read by Worker only if explicitly in their prompt |
| `tests/` GREEN status | Continuous: every phase's tests pass | Manager confirms via "pytest tests/skills/test_X.py" output in package | Next Worker MUST NOT touch existing tests except its own additions |

### Worker Prompts Companion File

Path: `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md` (CREATE in v2.2 brainstorming as companion to this spec)

Contains 7 self-contained Worker Prompts (Prompt 1..7, one per Phase). Each prompt:

- States the Worker's scope, Read-ONLY file list, Do-NOT-read list (per `WORKER_PROMPTS.md` Type 1-4 templates)
- Lists files to create/modify with exact paths
- Provides verification commands (pytest invocations, schema-validate calls)
- Specifies the Worker Output Package format expected
- Explicit forbidden actions (scope creep block)

Operator dispatches Worker Prompts serially to fresh Claude Code sessions: Prompt 1 → wait for package → review → Prompt 2 → etc.

### Drift Minimization Guarantees

| Drift Source | Mitigation |
|--------------|-----------|
| Worker reads stale spec (Manager updated between phases) | Each prompt includes "Read spec sections X, Y, Z" — Worker grabs latest at session start |
| Worker scope creep | "Forbidden actions" list per prompt + spec is read-only for Worker |
| Worker context bleed (knowledge from prior session) | FRESH session per phase = no carryover |
| Manager loses context across long pause | DECISIONS.md + PHASE_STATUS.md + OPEN_QUESTIONS.md are SSoT — Manager can re-read to restore |
| Phase output drift from spec | Phase Outline tasks + Acceptance Criteria are concrete (named tests + grep commands) — Worker package verification catches |

---

## Acceptance Criteria (expanded — 20 items)

Operator can mark this v2 spec as DONE when:

### Infrastructure
1. ✅ `.mcp.json` has `"sf"` entry; `claude mcp list` shows sf connected
2. ✅ `.claude-plugin/plugin.json` bumped to v1.8.0, descriptions updated to "4 MCP server, 44 skill, 18 slash command"
3. ✅ Smoke test (`tests/smoke/test_sf_mcp_smoke.py`) passes when SF GUI open; skipif when not

### Schemas
4. ✅ `mcp-tool-registry.schema.json` accepts `"sf"` server name + lists SF tools
5. ✅ `events.schema.json` source.kind enum includes `"sf_mcp"`
6. ✅ `project-config.schema.json` v1.5 active; existing projects auto-migrate via Migration 0005
7. ✅ `sf-mcp-tool-mapping.schema.json` exists + has valid example instance under `templates/sf-mcp/`

### Skills
8. ✅ `sf-crawl-orchestrator` skill exists with **8 DURURs** (6 base + DURUR-orch-7 concurrent guard + DURUR-orch-8 Tier 1 rollback) + frontmatter validates against `schemas/skill-frontmatter.schema.json`; verify via `python3 scripts/validation/validate_schema.py skills/ingestion/sf-crawl-orchestrator/SKILL.md`
9. ✅ `sf-import` body UNCHANGED (8-step protocol intact); only frontmatter accepts source_run_id
10. ✅ End-to-end smoke (manual + recorded in `docs/PHASE_STATUS.md`): operator runs `/pseo-sf-crawl vento`; verified by (a) `ls projects/vento/sf-exports/$(date +%Y-%m-%d)/raw/*.csv` returns ≥14 CSVs, (b) `python3 -c "from openpyxl import load_workbook; print([s for s in load_workbook('projects/vento/master.xlsx').sheetnames if s in {'crawl_sitemap','redirect_404','schema','on_page_audit','tech_seo','robots_txt'}])"` returns all 6 sheet names, (c) `grep -c '"source":{"kind":"sf_mcp"' projects/vento/_state/events.jsonl` returns ≥1
11. ✅ Operator can disable orchestrator entirely: with `sf.mcp.enabled=false` in project.config.json, manual CSV drop + `python3 scripts/ingestion/sf_import.py --project vento --sf-export-path projects/vento/sf-exports/{date}/` succeeds with same exit code (0) and same 6-sheet outputs as v1.7 baseline; verified by `pytest tests/skills/test_sf_import.py -v` (existing 6 cases stay GREEN)
12. ✅ All 4 optional consumer skills (tech-audit, schema-audit, on-page-audit, internal-links) default to `use_sf_mcp_live=False` (zero regression); verified by grep frontmatter + existing test pass rate unchanged
13. ✅ tech-audit (selected as representative consumer per Phase 5) tested live with `use_sf_mcp_live=True` on vento; operator confirms `master.xlsx#tech_seo` rowcount(live) ≥ rowcount(file-only baseline); evidence recorded in `docs/PHASE_STATUS.md` v1.8 closeout entry. CI test remains mock-only.

### Commands
14. ✅ `/pseo-sf-crawl <slug>` exists at `commands/pseo-sf-crawl.md`; markdown frontmatter validates; invokes sf-crawl-orchestrator skill
15. ✅ `/pseo-sf-status` exists at `commands/pseo-sf-status.md`; output is a markdown table with columns: project_slug, last_crawl_date, sf_mcp_connection_status, allowed_directory_path (4-column format documented in command's markdown body)

### Quality
16. ✅ All new tests pass; existing 1184 pytest baseline stays GREEN (target ~1210 PASS)
17. ✅ Drift-check 27 invariants stay GREEN after smoke crawl
18. ✅ schema-validate passes including new sf-mcp-tool-mapping

### Documentation
19. ✅ README.md contains H2 section `## Screaming Frog 24 MCP (Optional)` with subsections "Setup", "SF Settings", ".mcp.json snippet"; docs/WORKFLOWS.md contains H3 `### SF crawl via MCP` workflow with sequence diagram; ARCHITECTURE.md §7 + §16.5 contain post-v1.8 text confirming hybrid file+MCP and HTTP MCP transport; verified by `grep -l "Screaming Frog 24 MCP\|sf-crawl-orchestrator\|HTTP MCP" README.md docs/WORKFLOWS.md docs/ARCHITECTURE.md` returns all 3 files
20. ✅ `docs/RELEASE_NOTES_v1.8.0.md` exists (≥100 lines, structured per v1.7 pattern); ADR-031 in `docs/DECISIONS.md` matches existing ADR-030 format; `docs/PHASE_STATUS.md` "Active Phase" line reads "v1.8.0 SHIPPED" with commit SHA; verified by git log + file existence checks

---

## Open Questions for Operator Review (11 items)

Defaults applied where not blocking; flag any to discuss:

| Q | Default | Alternative |
|---|---------|-------------|
| **Q-SF-MCP-01** Node.js Runtime in SF settings | OFF (security) | ON for embeddings/cannibalization v1.1+ |
| **Q-SF-MCP-02** Orchestrator approval prompt | YES (requires_approval=true) | NO for full auto |
| **Q-SF-MCP-03** Default max_wait_minutes for crawl polling | 180 (3h) | 360 (6h) for Bigcat-scale 30K+ URLs |
| **Q-SF-MCP-04** Move vs Copy strategy SF dir → project dir | Move (cleanup; matches D-SF-16 atomic semantics — temp staging deletes SF dir copy after success) | Copy (backup, 2x disk; weakens atomic guarantee) |
| **Q-SF-MCP-05** Auto-invoke sf-import after orchestrator | YES (full pipeline in one operator command) | NO (operator reviews CSVs before sf-import) |
| **Q-SF-MCP-06** Cross-project SF lock (when 2 projects orchestrate concurrently) | DURUR-orch-7 sf_crawl_progress preflight catches in v1; per-project fcntl persists; global cross-project lock deferred to v1.2+ | Add global SF lock now (Python multiprocessing.Lock or fcntl on shared sentinel) |
| **Q-SF-MCP-07** Optional consumer skill rollout (tech-audit / schema-audit / on-page-audit / internal-links) | All 4 in v1.8 | Stage: 2 in v1.8, 2 in v1.9 |
| **Q-SF-MCP-08** Should stop.json hook validate sf entry in mcp-tool-registry | **RESOLVED → NO** (perf budget; stop_validation.py has <1s budget, `claude mcp list` costs ~200-500ms; drift-check skill catches it instead) | Reopen if performance budget changes |
| **Q-SF-MCP-09** Where does `mcp-tool-registry.json` instance live (currently schema-only, no instance) | Repo root: `./mcp-tool-registry.json` (one engine-wide registry) | Per-project under `projects/{slug}/_state/` (matches schema description "per-project"); or `schemas/mcp-tool-registry.json` co-located |
| **Q-SF-MCP-10** (v2.2 NEW) Tier 3 (16 optional reports) inclusion in default orchestrator loop | NO — orchestrator default = 24 reports (Tier 1 + Tier 2 only) | YES — include all 40; bumps loop iterations + per-crawl time + disk; needs operator use-case justification |
| **Q-SF-MCP-11** (v2.2 NEW) `per_report_timeout_seconds` default in `sf_generate_report` calls | 300 (5min/report; 24 reports × 5min = 2h budget for export phase alone) | 180 (3min, faster fail) or 600 (10min, slower fail but more tolerant of large sites) — operator chooses based on largest expected crawl |

---

## Glossary (additions to docs/GLOSSARY.md in Phase 6)

| Term | Meaning |
|------|---------|
| **SF MCP** | Native Screaming Frog 24 Model Context Protocol server (HTTP `http://127.0.0.1:11435/mcp`) |
| **SF orchestrator** | `sf-crawl-orchestrator` skill — bridges SF MCP to file-based sf-import pipeline |
| **Optional consumer** | A discovery/planning skill with `use_sf_mcp_live: bool` flag (default False); when True, calls SF MCP for live data |
| **Hybrid mode** | SF integration strategy where file-based sf-import remains authoritative + SF MCP adds operator-triggered crawl + ad-hoc query |

---

## Sources (research evidence)

- Screaming Frog 24.0 release announcement (codename "bolus"): https://www.screamingfrog.co.uk/blog/seo-spider-24/
- Cursor + SF 24 MCP real-world crawl report: https://allgreatthings.io/blog/seo-content-marketing/screaming-frog-v24-mcp-in-cursor-what-we-learned-running-a-real-crawl — port 11435, IllegalStateException, 60-char tool name limit, server key "sf" convention
- Claude + SF MCP setup guide: https://search.agency/blog/screaming-frog-mcp-claude-setup — tool inventory
- bzsasson/screaming-frog-mcp third-party Python wrapper (rejected Option C): https://github.com/bzsasson/screaming-frog-mcp
- Internal: `skills/ingestion/sf-import/SKILL.md` (8-step protocol authority)
- Internal: `schemas/mcp-tool-registry.schema.json` (registry pattern, http runtime line 47-51)
- Internal: `schemas/gsc-tool-mapping.schema.json` (mapping pattern template for sf-mcp-tool-mapping)
- Internal: `schemas/events.schema.json` (source.kind enum, line 41-44)
- Internal: `schemas/project-config.schema.json` v1.4 (current; v1.5 target)
- Internal: `scripts/state/events_writer.py` (append_provenance API)
- Internal: `scripts/state/workflow_runner.py` (create_run/start_step/finish_step/complete/fail API)
- Internal: `scripts/ingestion/gsc_pull.py` (pure-transform pattern reference)
- Internal: `rules/{schema-first, schema-versioning-discipline, append-only-state, naming, budget-events}.md`
- Internal: `.claude-plugin/plugin.json` (manifest for version + counts bump)
- Internal: all 44 SKILL.md frontmatters scanned (consumes/produces/mcp_tools/inputs analyzed for category D classification)
- Internal: all 6 hooks/*.json scanned for SF impact
- Internal: all 20 rules/*.md scanned for relevance
- Internal: existing tests/skills/test_*.py inventory (44 test files, 21734 lines total — 1184 PASS baseline)

---

**Spec status:** DRAFT v2 → awaiting operator review.

When you (Süleyman) finish reviewing v2, reply with one of:

- **"onayla"** → Worker Prompts ZATEN executable plan formatında (`docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md`); operator dispatches Prompt 1 to fresh session. Total: ~7 phases, ~8 days realistic, structured per PSEO `docs/SESSION_PROTOCOL.md` Manager+Worker pattern
- **"şunu değiştir: ..."** → I'll revise v2 and re-run self-review
- **Specific answers to Q-SF-MCP-01..08** → I'll update open-questions decisions and revise
- **"v3 yap, şunu da ekle: ..."** → If you spot another area I still missed, I'll do another deep pass before plan
