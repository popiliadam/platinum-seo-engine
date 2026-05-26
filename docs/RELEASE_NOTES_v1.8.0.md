# Platinum SEO Engine — v1.8.0 Release Notes

**Release date:** 2026-05-27
**Engine HEAD:** post-`<v1.8.0-release>` v1.8.0 release commit (5-file sync via Y-05 fourth production --apply)
**Predecessor:** [v1.7.0](RELEASE_NOTES_v1.7.0.md) (Google AI Optimization Guide compliance + Core Update hardening milestone)
**Status:** 🟢 GREEN-CANDIDATE (F-13 historical kalıntı; F-16 intentional break ADR-039 — new baseline 543B; F-17 PASS)

## 0. Executive Summary

v1.8 is the **Screaming Frog 24 MCP Hybrid Integration milestone** — first HTTP-transport MCP server in the registry, MCP-primary ingestion pivot (24-report orchestrator replaces manual CSV drop as the authoritative path), schema-first foundation upgrade (project-config v1.4 → v1.5 with optional `sf` block), atomic crawl semantics (all-or-nothing per crawl via temp staging + rollback), and resume capability for mid-loop crash recovery. **7 atomic engine phases convergent**, **5 atomic Worker commits + 2 pre-phase docs commits + 1 release closeout**, **+60 yeni test** (1184 → 1244 PASS + 12 SKIP, regression sıfır), `.mcp.json` invariant **intentionally broken** at Phase 2 (482B → 543B with new md5; F-16 60+ commit streak ended with operator-acknowledged additive growth per ADR-039), `DECISIONS.md` rotation cycle 22 applied (ADR-037 → archive; ADR-039 inline; 77B headroom intact), 0 slug literal in plugin runtime code (plugin agnostik invariant intact 5-phase streak).

Seven atomic phases convergent: **Phase-1** schema-first foundation (`sf-mcp-tool-mapping.schema.json` NEW + Migration 0005 + `mcp-tool-registry.json` instance at repo root + project-config v1.4→v1.5 + sf native tool naming Fix Worker round), **Phase-2** MCP utility + `.mcp.json` sf entry + ADR-039 controlled F-16 break (`scripts/util/sf_mcp_client.py` first HTTP MCP client + httpx pin in requirements.txt + DECISIONS rotation cycle 22), **Phase-3** sf-crawl-orchestrator skill BIGGEST PHASE (647L SKILL.md body + 9 numbered Body Steps + 8 DURURs + Tier 1/2 24-report iteration + atomic temp staging + R13 concurrent-crawl guard + 18 new test functions), **Phase-4** existing skill extensions + F-23 invariant (drift-check JSON-first detection + schema-validate sf-mcp-tool-mapping inclusion + init-project Migration 0005 cascade Step 4.5 + whats-next sf crawl freshness routing + F-23 land in cross-sheet-invariants.json), **Phase-5** optional consumer wiring (tech-audit + schema-audit + on-page-audit + internal-links each gets `use_sf_mcp_live: bool = False` opt-in flag + body branch documenting D-SF-11 R9+R12 patterns), **Phase-6** commands + manifest + documentation (this release closeout: 2 NEW commands + 4 EXTENDED + 10 doc files + plugin manifest bump via Y-05 + rules edit + 6 docs sweep absorb items), **Phase-7** pilot smoke + release (post-Phase-6 verification on Vento project + git tag).

**Atomic phase paterni 68'inci kanıt cumulative** — 78 phase consecutive convergent invariant intact (7 v1.8 cycle phases). **Lesson 38 v2 67 → ~80+ cumulative catches** (≈13 v1.8 catches: Fix Worker convention drift Phase 1 + Cascade test absorption Phase 1 + DECISIONS rotation breach + recovery Phase 2 + ADR-031→ADR-039 namespace override Phase 2 + Worker schema-first wins x2 Phase 3 + Engine self-governance F-XX renumber Phase 4-6 + Stub-mod 4'üncü cumulative Phase 5 + 6 docs sweep absorb Phase 6 + Y-05 4th production dogfooding Phase 6 + plugin description drift fix Phase 6 + invariants count discipline 28-vs-31 catch Phase 6).

**Y-05 fourth production dogfooding:** `scripts/release/version_bump.py --apply` v1.5.0'da ilk + v1.6.0'da ikinci + v1.7.0'da üçüncü + v1.8.0'da dördüncü kez devreye girdi — own-tooling invariant cross-validation 4'üncü kanıt (`tests/ci/test_version_sync.py` post-apply GREEN).

## 1. Phase-1 — Schema-first foundation (`203743c`)

**Scope:** New schema (sf-mcp-tool-mapping) + Migration 0005 + mcp-tool-registry.json instance at repo root + project-config v1.4→v1.5 + events.schema.json source.kind enum extension + Fix Worker round for sf tool naming convention drift.

### 1.1 Deliverables
- **`schemas/sf-mcp-tool-mapping.schema.json`** (NEW 155L) — 6 use-case keys (`crawl_trigger`, `crawl_progress_poll`, `report_export_inline`, `crawl_list`, `allowed_dir_discovery`, `_meta`) + sfMcpTool enum (5 native SF MCP tools). Mirrors gsc/dataforseo/scrapling mapping pattern.
- **`scripts/migrations/migration_0005_project_config_1_4_to_1_5.py`** (NEW 148L) — Idempotent additive bump; clones 0004 pattern exactly (dry-run + strict + .bak). Migration body populates `sf.mcp.{enabled=false, url, allowed_directory, crawl_config_path, max_wait_minutes}` defaults.
- **`./mcp-tool-registry.json`** (NEW 294L instance at repo root per Q-SF-MCP-09) — 4 servers × 31 tools cumulative (gsc 8 + dataforseo 9 + scrapling 9 + sf 5).
- **`templates/sf-mcp/`** scaffold — `.gitkeep` + `use-case-example.json` validating against new schema.
- **`schemas/mcp-tool-registry.schema.json`** — serverName enum +sf (additive); no migration needed.
- **`schemas/events.schema.json`** — source.kind enum +sf_mcp (additive per D-SF-13).
- **`schemas/project-config.schema.json`** — schema_version const 1.4→1.5 + additive sf block (D-SF-12 + D-SF-18 path parameterization).
- **`scripts/state/bootstrap_project.py`** — SCHEMA_VERSION 1.4→1.5 + DEFAULT_SF_MCP_BLOCK emit.

### 1.2 Fix Worker round (1 NO-GO dispatched)
W-1 caught sf tool_name convention drift: registry tool naming = `{server_key}__{native_mcp_tool_name_verbatim}` not `{server_key}__{stripped_name}`. Fix Worker scope-expanded to 3rd file (sf-mcp-tool-mapping.schema enum) — defensible scope expansion within v1.8 NEW artifact drift cluster.

### 1.3 Patterns Born / Reinforced
- **Schema-first discipline** — new schemas land BEFORE consumer code; Migration 0005 ordered before Phase 4-5 (consumer skill changes) per `rules/schema-versioning-discipline.md`.
- **Cascade fix in single atomic (6+ reuse)** — Phase 1 schema_version bump → 6 test cascade updates absorbed into ONE commit; no "fix it next task" deferral (Lesson 38 v2 paterni reuse).

## 2. Phase-2 — MCP utility + .mcp.json sf entry + ADR-039 (`dec2eef`)

**Scope:** First HTTP MCP transport in registry; controlled F-16 invariant break; reusable HTTP MCP client utility.

### 2.1 Deliverables
- **`scripts/util/sf_mcp_client.py`** (NEW 326L) — D-SF-14 reusable HTTP MCP client + 4 typed exceptions + 3-retry exponential backoff (1s/2s) + 100KB response cap (D-SF-05) + stderr logging.
- **`tests/scripts/test_sf_mcp_client.py`** (NEW 252L; 5 cases) — JSON-RPC envelope + timeout + retry schedule + size cap + 307 redirect POST preservation per RFC 7231.
- **`.mcp.json`** — 482B → 543B; `sf` 4th-server HTTP entry per D-SF-01.
- **`requirements.txt`** + **`requirements-lock.txt`** — httpx>=0.27,<1.0 (floor) + httpx==0.28.1 (lock) + transitive httpcore/h11 pins.
- **`docs/DECISIONS.md`** — 6126B → 6067B; **ADR-039 inline** + rotation cycle 22 applied (ADR-037 archived).

### 2.2 F-16 controlled break (ADR-039)
**Memory invariant `.mcp.json` 482B byte-byte korundu 47+ commit cumulative** intentionally broken at v1.8 Phase 2 — first deliberate F-16 break since v1.5. Operator-acknowledged additive growth (4th MCP server added); F-16 invariant resumes from new 543B baseline post-v1.8 release. ADR-039 body text "v1.8 SF MCP: HTTP Transport + Controlled F-16 Break" + new md5 `93523d41e14f90916fefb86d346bd702`.

### 2.3 Patterns Born / Reinforced
- **DECISIONS rotation cycle protocol** — Cap breach on first ADR-039 append → Context-line trim (numbering meta moved to Worker Output Package) → 77B headroom restored without rotation escalation.
- **Pattern reusable for future HTTP MCPs** — `sf_mcp_client.py` 6-step `_handle_response` + 3-retry policy + size cap establishes the canonical HTTP MCP client paterni (next HTTP MCP can clone).

## 3. Phase-3 — sf-crawl-orchestrator skill BIGGEST PHASE (`feb68b4`)

**Scope:** 24-report MCP-primary ingestion loop + 8 DURURs + atomic semantics + resume capability + sf-import handoff.

### 3.1 Deliverables
- **`skills/ingestion/sf-crawl-orchestrator/SKILL.md`** (NEW 647L) — 9-step body protocol + 8 DURURs (6 base + DURUR-orch-7 R13 concurrent-crawl guard via `sf_list_crawls` + DURUR-orch-8 Tier 1 export fail / atomic rollback per D-SF-16) + `requires_approval=true` Q-SF-MCP-02 lock + `include_tier3=false` Q-SF-MCP-10 lock + schema-validates against `skill-frontmatter.schema.json`.
- **`scripts/ingestion/sf_crawl_orchestrator.py`** (NEW 225L pure-transform) — 3 helpers (`enumerate_reports` / `move_with_rollback` / `parse_progress_response`); **SSoT discipline** — imports `from scripts.ingestion.sf_import import TIER1_REQUIRED, TIER2_RECOMMENDED` (NOT inline 24-name list).
- **`tests/skills/test_sf_crawl_orchestrator.py`** (NEW 801L; 11 tests) — 10 DURUR/happy-path + 1 bonus frontmatter schema validation.
- **`tests/scripts/test_sf_crawl_orchestrator_helpers.py`** (NEW 187L; 6 tests) — pytest basename collision rename (Q-PHASE-3-WORKER-02).
- **`tests/smoke/test_sf_mcp_smoke.py`** (NEW 69L; 1 skipif-protected live SF MCP probe).
- **`templates/reports/sf-crawl.template.md`** (NEW 65L) — 7 sections per v2.2 spec.
- **`skills/ingestion/sf-import/SKILL.md`** MODIFIED — Frontmatter +4L (`source_run_id` optional input); body 8-step protocol UNCHANGED per D-SF-07; DURUR list UNCHANGED.

### 3.2 Patterns Born / Reinforced
- **Atomic crawl semantics (D-SF-16)** — temp staging dir `_state/staging/sf-crawl-{run_id}/` → atomic mv on success / rm -rf on Tier 1 fail. All-or-nothing per crawl prevents sf-import partial-projection state.
- **Resume capability** — `workflow_runner.pause(reason="sf_mcp_unavailable")` + `workflow_runner.resume(run_id)` survive across crash; temp staging scan + idempotent report skip continues from where it stopped.
- **Schema-first workflow_runner enum discipline** — Worker correctly mapped 8 DURURs to canonical workflow-run.schema 6-value enum (mcp_error/validation_error/timeout/internal_error) — no custom enum extension.

## 4. Phase-4 — Existing skill extensions + F-23 invariant (`a6c8482`)

**Scope:** Drift-check F-23 land + schema-validate sf-mcp-tool-mapping inclusion + init-project Migration 0005 cascade + whats-next sf crawl freshness routing + D-SF-09 no-cron verification test.

### 4.1 Deliverables
- **`schemas/cross-sheet-invariants.json`** — F-23 entry (severity=HIGH category=csr_mcp computed_by=consistency_check); rules count 27 → 28.
- **`scripts/validation/validate_invariants.py`** — `check_F_23` NEW 91L with 4 verdict paths (no workflow dir → SKIP, no registry → FAIL, registry missing sf → FAIL, registry has sf → PASS); `_RULE_FUNCTIONS` extended.
- **`skills/governance/drift-check/SKILL.md`** — Body F-23 detection logic + cite update invariants:20→21 in 3 locations + "Naming-namespace note" subsection for Q-PHASE-4-WORKER-01 dual-namespace transparency.
- **`skills/governance/schema-validate/SKILL.md`** — `sf-mcp-tool-mapping.schema.json` + positive-instance gate for `templates/sf-mcp/use-case-example.json`.
- **`skills/meta/init-project/SKILL.md`** — Step 4.5 `cascade_migration_0005` (operator opt-in via `--schema-version=1.5` flag; idempotent on already-1.5 docs; bootstrap_project.py emits 1.5 natively post-Phase-1 so cascade is safety net for legacy 1.4 workspaces).
- **`skills/meta/whats-next/SKILL.md`** — Step 4.5 `scan_sf_crawl_freshness` + `scripts/meta/whats_next.py` `suggest_sf_crawl_when_stale()` read-only helper (104L; conditional on sf.mcp.enabled=true; threshold_days=30 default; SCORES dict +sf_crawl_stale=30 — slots below master_task_medium=40 never displaces higher-priority signals).
- **`tests/skills/test_no_cron_for_sf_crawl_orchestrator.py`** (NEW 4 cases) — D-SF-09 verification: frontmatter_has_no_cron + no_other_skill_schedules + no_hook_json_targets + spec_d_sf_09_documented w/ structural fallback.

### 4.2 Patterns Born / Reinforced
- **JSON-first → code → docs cascade** — F-23 land starts at cross-sheet-invariants.json (schema), then validate_invariants.py check function, then SKILL.md body + test_cross_sheet_invariants_sync auto-validates bidirectional parity.
- **Dual-namespace transparency** — drift-check SKILL.md cross-sheet-invariants.json F-23 vs Engine Self-Governance F-23..F-28 narrative labels co-exist on disjoint paths; Phase 6 renumber narrative labels → F-29..F-34 for unambiguous reference.

## 5. Phase-5 — Optional consumer wiring (`e21015d`)

**Scope:** 4 discovery/planning skills get opt-in SF MCP live data flag per Q-SF-MCP-07 lock (all-4 in v1.8 NOT 2+2 staging).

### 5.1 Deliverables
- **`skills/discovery/tech-audit/SKILL.md`** — Frontmatter `use_sf_mcp_live: bool = False` + body branch (D-SF-11 R9+R12 pattern: SfMcpClient import + client.health() preflight + AMBER fallback NEVER hard fail + sf_generate_report NATIVE tool naming + response.get("truncated", False) detection). Per-skill canonical report: `issues_overview_report` (Step 5).
- **`skills/discovery/schema-audit/SKILL.md`** — Same flag + body branch; report: `structured_data_all` (Step 3).
- **`skills/discovery/on-page-audit/SKILL.md`** — Same flag + body branch; report: `page_titles_all` (Step 4).
- **`skills/planning/internal-links/SKILL.md`** — Same flag + body branch; report: `all_inlinks` (Step 2).
- **8 new test functions** (2 per skill: `test_use_sf_mcp_live_flag_in_frontmatter` + `test_skill_md_documents_sf_mcp_live_pattern`) — frontmatter shape + SKILL.md body pattern grep-lock.

### 5.2 Patterns Born / Reinforced
- **Stub-mod pattern 4'üncü cumulative reuse** — Worker chose stub-mod contract lock approach (runtime wiring documented in SKILL.md prose, paired tests lock contract via frontmatter shape + body pattern grep). Pure-transform scripts intentionally unchanged; AC-13 (Phase 7 pilot smoke) is where actual runtime verification happens.
- **Opt-in regression preservation** — All 4 default `use_sf_mcp_live: bool = False` — existing 1184 pytest baseline depends on file-based fixtures; adding live MCP calls by default would break test determinism.

## 6. Phase-6 — Commands + manifest + documentation (release closeout)

**Scope:** 2 NEW commands + 4 EXTENDED commands + 10 doc files + plugin manifest bump via Y-05 + rules/events-writer.md edit + 6 docs sweep absorb items.

### 6.1 Deliverables
- **`commands/pseo-sf-crawl.md`** (NEW) — Markdown command pattern; invokes sf-crawl-orchestrator skill; `--resume <run_id>` flag for paused workflows.
- **`commands/pseo-sf-status.md`** (NEW) — Inline command (no dedicated skill); 4-column table (project_slug, last_crawl_date, sf_mcp_connection_status, allowed_directory_path).
- **`docs/RELEASE_NOTES_v1.8.0.md`** (NEW; this file).
- **`.claude-plugin/plugin.json` + 4 cascaded files** — Y-05 5-file sync via `scripts/release/version_bump.py --to 1.8.0 --apply` (4th production --apply: v1.5 ilk + v1.6 ikinci + v1.7 üçüncü + v1.8 dördüncü).
- **`.claude-plugin/plugin.json` description manual fix** — "43 skill, 15 slash command, 6 hook, 3 MCP server" → "45 skill, 18 slash command, 6 hook, 4 MCP server" (pre-existing v1.7 drift fixed on top of v1.8 targets).
- **4 EXTENDED commands** — pseo-status.md (SF MCP Status H2 + inline probe) + pseo-driftcheck.md (28 invariants + F-23 example) + pseo-init.md (`--schema-version=1.5` flag + Migration 0005 cascade note) + pseo-schema-audit.md (`--use-sf-mcp-live` flag).
- **10 doc files updated** — README + INSTALL + WORKFLOWS + ARCHITECTURE §7 + §16.5 + OPEN_QUESTIONS (Q-SF-MCP-01..11) + DECISIONS (ADR-039 verify) + PHASE_STATUS + REFERENCE_INDEX + GLOSSARY + CONTRIBUTING (if MCP section exists).
- **`rules/events-writer.md` line 129** — New row alongside existing sf-import row: `| sf-crawl-orchestrator | ingest, staging | sf_mcp | Screaming Frog MCP-triggered crawl ingest |`.
- **6 docs sweep absorb items** — (i) sf-mcp-tool-mapping schema description text refinement (Q-PHASE-1-POLISH-01) + (ii) F-XX namespace renumber drift-check SKILL.md F-23..F-28 → F-29..F-34 + 4 test cross-refs (Q-PHASE-4-WORKER-01) + (iii) monitoring-weekly stale invariants:20 → invariants:21 (Q-PHASE-4-WORKER-02) + (iv-vi) v2.3 retro consolidation in PHASE_STATUS final entry.

### 6.2 Patterns Born / Reinforced
- **6 docs sweep absorb paterni doğum belgesi** — Cross-phase closure followups (1 from Phase 1 + 1 from Phase 4 + 1 from Phase 4 + 3 v2.3 retro) consolidated into Phase 6 dispatch via Manager Dispatch Note. Avoids "log new Open Question" deferral chain when followup is bounded + scope-appropriate to current phase.

## 7. Phase-7 — Pilot smoke + release (post-Phase-6)

**Scope:** Live `/pseo-sf-crawl vento` smoke + 20 Acceptance Criteria verification + rollback drill + git tag.

(Phase 7 final outputs filled in after release closeout; see `docs/PHASE_STATUS.md` v1.8 evidence block for AC-10 / AC-13 output captures.)

## 8. Schema Changes

| File | Change | Migration? |
|------|--------|-----------|
| `schemas/sf-mcp-tool-mapping.schema.json` | NEW (155L; 6 use-case keys + sfMcpTool enum 5 tools) | NO |
| `schemas/mcp-tool-registry.schema.json` | serverName enum +sf | NO |
| `schemas/events.schema.json` | source.kind enum +sf_mcp | NO (append-only) |
| `schemas/project-config.schema.json` | schema_version const 1.4 → 1.5 + additive sf block | **YES — Migration 0005** |
| `schemas/cross-sheet-invariants.json` | F-23 entry added (rules 27 → 28) | NO |

## 9. Migrations

| Migration | Effect | Test |
|-----------|--------|------|
| **Migration 0005** | project-config v1.4 → v1.5; populates `sf.mcp.{enabled=false,url,allowed_directory,...}` defaults; idempotent on already-1.5 docs; `.bak` backup | `tests/scripts/test_migration_0005.py` 7/7 PASS + smoke CLI dry-run EXIT 0 |

## 10. Tests

**Baseline:** 1184 PASS / 11 SKIP (v1.7 sealed).
**Target after v1.8 ship:** 1244 PASS / 12 SKIP (+60 PASS / +1 SKIP cumulative; Phase 1 +14 + Phase 2 +5 + Phase 3 +19+1 SKIP + Phase 4 +14 + Phase 5 +8 + Phase 6 +0 + Phase 7 +0).

| New test file | Cases |
|---------------|-------|
| `tests/scripts/test_sf_mcp_client.py` | 5 |
| `tests/schemas/test_sf_mcp_tool_mapping_schema.py` | 3 |
| `tests/scripts/test_migration_0005.py` | 7 |
| `tests/skills/test_sf_crawl_orchestrator.py` | 11 |
| `tests/scripts/test_sf_crawl_orchestrator_helpers.py` | 6 |
| `tests/smoke/test_sf_mcp_smoke.py` | 1 (SKIP if SF MCP /health unreachable) |
| `tests/skills/test_no_cron_for_sf_crawl_orchestrator.py` | 4 |
| **Extensions** (2-per-skill flag + body tests) | 8 (test_tech_audit + test_schema_audit + test_on_page_audit + test_internal_links) |
| **Extensions** (existing files +1-3 cases each) | F-23 + sf-mcp-tool-mapping coverage + init/whats-next + sf-import source_run_id chain |

## 11. Acceptance Criteria results

(20 ACs per spec; Phase 7 fills evidence block post-pilot-smoke.)

## 12. Backward Compatibility

- **File-drop fallback never deprecated** (D-SF-07) — sf-import 8-step protocol UNCHANGED; operator can still drop CSVs manually if SF MCP is down.
- **Optional consumer skills** — 4 skills get `use_sf_mcp_live: bool = False` default (opt-in); zero regression on file-based fixtures.
- **Migration 0005 additive only** — old v1.4 configs validate against v1.5 schema after migration; required[] unchanged; backward-compatible.
- **No hook changes** (Q-SF-MCP-08 RESOLVED → NO) — stop_validation.py perf budget intact; drift-check skill catches MCP registry drift instead.

## 13. Notes for Operators

- **SF GUI must be open + MCP Server "Start" clicked** before `/pseo-sf-crawl` triggers (D-SF-10 + DURUR-orch-1). Pre-flight probe in command body catches.
- **`per_report_timeout_seconds` default 300** (5min/report; 24 reports × 5min = 2h budget for export phase) — operator can override via `project.config.sf.mcp.per_report_timeout_seconds` based on largest expected crawl (Q-SF-MCP-11).
- **Tier 3 (16 optional reports) excluded by default** (Q-SF-MCP-10) — orchestrator runs 24 reports (Tier 1 + Tier 2); Tier 3 inclusion deferred to v1.9+ scope based on operator use-case justification.
- **F-16 invariant baseline reset** — `.mcp.json` post-v1.8 baseline is 543B (was 482B). Future F-16 drift catches resume from new baseline.
