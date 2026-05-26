# SF MCP Hybrid Integration — Worker Prompts (Phase 1..7)

> **Companion file to:** `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` (v2.2)
> **Date:** 2026-05-26
> **Author:** Manager session (Claude, Süleyman dispatch)
> **Usage:** Operator copies one Prompt at a time into a fresh Claude Code session. Worker bootstraps via `docs/SESSION_PROTOCOL.md` §13.2, executes ONLY the listed scope, returns Worker Output Package per §13.4. Manager (Süleyman's persistent session) processes the package, updates `docs/PHASE_STATUS.md` + `docs/DECISIONS.md` + `docs/OPEN_QUESTIONS.md`, then dispatches the next Prompt.
> **Serial execution:** Phase N cannot start until Phase N-1's Worker Output Package is reviewed and Manager confirms GO.
> **Pattern:** Each Prompt follows `docs/WORKER_PROMPTS.md` Type 1-4 template (Scope, Read-ONLY, Do-NOT-read, Files to create/modify, Verification, Forbidden, Return).

---

## ⚠️ Pre-Phase-1 Operator Decisions (MUST resolve before dispatching Prompt 1)

| Decision | Default applied if no answer | Locks down |
|----------|------------------------------|------------|
| **Q-SF-MCP-09** Registry instance location | `./mcp-tool-registry.json` (engine-wide) | Phase 1 task #6 file path |
| **Q-SF-MCP-02** Orchestrator approval prompt | YES (requires_approval=true) | Phase 3 frontmatter |
| **Q-SF-MCP-04** Move vs Copy | Move (atomic-friendly) | Phase 3 file move semantics |
| **Q-SF-MCP-05** Auto-invoke sf-import | YES | Phase 3 orchestrator handoff step |
| **Q-SF-MCP-07** Consumer rollout | All-4 in v1.8 | Phase 5 scope |
| **Q-SF-MCP-10** Tier 3 inclusion in default loop | NO (24 reports only) | Phase 3 24-vs-40 loop |
| **Q-SF-MCP-11** per_report_timeout_seconds | 300 (5min) | Phase 3 sf_generate_report timeout |

If operator silent on any → Manager applies default, logs choice to DECISIONS.md.

---

# PROMPT 1 — Phase 1: Schema-First Foundation

**Copy below into fresh Claude Code session as the first message:**

```
# Worker Prompt: PSEO v1.8 Phase 1 — Schema-First Foundation

You are a Fresh Worker Session for the Platinum SEO Engine project. Manager session is operator Süleyman. Bootstrap by reading these 6 files in order (~12KB total, fits <15KB budget per SESSION_PROTOCOL.md §13.2):

1. `docs/PHASE_STATUS.md` — confirm Active Phase = "v1.8 Phase 1"
2. `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` — read ONLY sections: "Executive Summary", "Decision Record" (esp. D-SF-08/12/13/14/16/18), "Schemas Impact Matrix", "Migration 0005 — project-config v1.4 → v1.5", "Implementation Phase Outline" (Phase 1 row only)
3. `rules/schema-first.md` — discipline that governs your work
4. `rules/schema-versioning-discipline.md` — migration pattern
5. `scripts/migrations/migration_0004_project_config_1_3_to_1_4.py` — copy this pattern for Migration 0005
6. `schemas/mcp-tool-registry.schema.json` — schema you'll edit + which needs first instance file

## Scope
Implement Phase 1 of SF MCP integration. 9 tasks, all schema-first foundation.

## Files to CREATE
1. `schemas/sf-mcp-tool-mapping.schema.json` (NEW) — meta-schema cloning `schemas/gsc-tool-mapping.schema.json` structure. Use-case keys: `crawl_trigger`, `crawl_progress_poll`, `report_export_inline`, `report_export_save`, `crawl_list`, `allowed_dir_discovery`. mcp_server_name default: "sf". Use Draft 7 JSON Schema (matches other 21 schemas).
2. `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py` (NEW) — clone `migration_0004_project_config_1_3_to_1_4.py` exactly (CLI flags, exit codes, .bak backup, dry-run, idempotent, audit summary stderr). Migration adds OPTIONAL `sf` block: `{"mcp": {"enabled": false, "url": "http://127.0.0.1:11435/mcp", "allowed_directory": null, "crawl_config_path": null, "max_wait_minutes": 180, "per_report_timeout_seconds": 300}}`. Bumps `schema_version` const "1.4" → "1.5".
3. `./mcp-tool-registry.json` (NEW, instance file at repo root per Q-SF-MCP-09 default) — populate ALL 4 servers (gsc + dataforseo + scrapling + sf) per schema. Schema description says "single inventory; reconciled against `claude mcp list`". Use existing 3 server frontmatter mcp_tools enumerations + new sf tools: sf_crawl, sf_crawl_progress, sf_generate_report, sf_list_crawls, sf_list_allowed_base_directory.
4. `templates/sf-mcp/.gitkeep` (NEW empty file) + `templates/sf-mcp/use-case-example.json` (NEW) — minimal instance validating against sf-mcp-tool-mapping.schema.json
5. `tests/scripts/test_migration_0005.py` (NEW) — 5 cases mirroring `tests/scripts/test_migration_0004.py` if exists; else mirror test_migration_0003.py pattern: bump_only, populate_defaults, idempotent_replay, missing_required, mixed_existing_field
6. `tests/schemas/test_sf_mcp_tool_mapping_schema.py` (NEW) — 3 cases: schema parses Draft7, valid instance validates, instance with unknown use-case key rejected

## Files to MODIFY
7. `schemas/mcp-tool-registry.schema.json` — Edit line 40 `definitions.serverName.enum`: add `"sf"`. Verify line 47-51 runtime enum already includes `"http"` (no change). One-line description update on line 39 mentioning sf as 4th external feed.
8. `schemas/events.schema.json` — Edit line 41-44 `source.kind` enum: add `"sf_mcp"` after `"scrapling_mcp"`. Update line 43 description appending "sf_mcp → same pattern (response_bytes + row_count + mcp_server + mcp_tool)".
9. `schemas/project-config.schema.json` — Edit line 13 schema_version const: `"1.4"` → `"1.5"`. Add optional `sf` property block under `properties` (NOT in required[]): see migration 0005 payload for shape. Update title v1.4 → v1.5 + description noting Migration 0005 prerequisite.
10. `scripts/state/bootstrap_project.py` — Add `sf` block default emit when schema_version >= 1.5 in the project.config.json scaffolding step. Do NOT change v1.4 fallback path (operators may bootstrap v1.4 then migrate). Read the file fully first to understand the scaffold function.

## Read ONLY
- 6 bootstrap files listed above
- Files listed in CREATE/MODIFY (to understand what you're editing)
- `tests/scripts/test_migration_0004.py` if exists (for test pattern)

## Do NOT read
- Other spec sections beyond what's listed
- Skill SKILL.md files (Phase 4+ scope)
- scripts/ingestion/* (Phase 2+ scope)
- hooks/, commands/ (Phase 6 scope)

## Verification (RUN BEFORE returning Worker Output Package)
```bash
# Schema-validate full sweep — ALL schemas including new one must parse
python3 scripts/ci/run_skill_python.py skills/governance/schema-validate/SKILL.md
# → expect EXIT 0

# Migration 0005 idempotent test
python3 -m pytest tests/scripts/test_migration_0005.py -v
# → 5 cases PASS

# sf-mcp-tool-mapping schema validates + rejects unknown
python3 -m pytest tests/schemas/test_sf_mcp_tool_mapping_schema.py -v
# → 3 cases PASS

# events.schema enum extension test (extend existing test file)
python3 -m pytest tests/schemas/test_events_schema_event_type_enum_v1_1.py -v
# → should now include sf_mcp; existing cases stay GREEN

# Full baseline regression — 1184 PASS / 11 SKIPPED / 0 FAIL must hold
python3 -m pytest -q 2>&1 | tail -5
# → "1184 passed" or higher (your new tests added; "X passed" where X >= 1184 + new tests)

# mcp-tool-registry.json instance validates against its schema
python3 -c "import json, jsonschema; s=json.load(open('schemas/mcp-tool-registry.schema.json')); i=json.load(open('mcp-tool-registry.json')); jsonschema.Draft7Validator(s).validate(i); print('OK')"
# → "OK"
```

## Forbidden
- Touch any SKILL.md file (Phase 4+)
- Touch .mcp.json (Phase 2)
- Touch any scripts/ingestion/*.py (Phase 2+)
- Make commits — leave staged changes for Manager to commit atomically
- Scope creep: even if you spot an unrelated issue, log it as Open Question, do NOT fix

## Return — Worker Output Package
Use format from `docs/SESSION_PROTOCOL.md` §13.4. Files Created/Modified must list line counts. Verification section must include exit codes + pytest pass/fail counts.
```

---

# PROMPT 2 — Phase 2: MCP Utility + .mcp.json Edit

**Copy below into fresh Claude Code session:**

```
# Worker Prompt: PSEO v1.8 Phase 2 — MCP Utility + .mcp.json

You are a Fresh Worker Session. Bootstrap reading:

1. `docs/PHASE_STATUS.md` — confirm Active Phase = "v1.8 Phase 2" (Phase 1 must show DONE)
2. `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` — read ONLY: "Decision Record" (esp. D-SF-01/02/14/18), ".mcp.json Configuration", "Scripts Impact", "Implementation Phase Outline" Phase 2 row
3. `scripts/ingestion/gsc_pull.py` — pattern reference for pure-transform (no MCP call in script; MCP called in SKILL.md body)
4. `scripts/ingestion/scrapling_ops.py` — pattern reference for stdio MCP wrapper
5. `.mcp.json` — current 3-server config you'll add to
6. `rules/naming.md` — server naming convention ("sf" 3-char lowercase)

## Scope
Phase 2: 6 tasks. Add SF MCP transport layer (HTTP client utility + .mcp.json entry).

## Files to CREATE
1. `scripts/util/sf_mcp_client.py` (NEW, ~150 LoC) — Reusable HTTP JSON-RPC client. **Establishes pattern for future HTTP MCPs** per D-SF-14. Required interface:
   - `class SfMcpClient:` with `__init__(base_url, timeout_seconds=30, max_response_bytes=100_000)`
   - `.health() -> bool` (GET `{base_url}/health` or analogous)
   - `.call_tool(tool_name: str, **kwargs) -> dict` — JSON-RPC 2.0 envelope: `{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": kwargs}, "id": uuid.uuid4().hex}`
   - Retry: 3 attempts with exponential backoff (1s, 2s, 4s) on connection errors only — NOT on HTTP 4xx (those are caller errors)
   - Response size cap: raise `SfMcpResponseTooLargeError` if response.content_length > max_response_bytes
   - Custom exceptions: `SfMcpConnectionError`, `SfMcpTimeoutError`, `SfMcpResponseTooLargeError`, `SfMcpToolError` (4xx/5xx from MCP)
   - Logging: `print(f"[sf_mcp_client] {method} {tool} → {status}", file=sys.stderr)` per call (matches PSEO stderr pattern)
   - Dependencies: `httpx` (add to requirements.txt if not present — verify first via `grep httpx requirements.txt`)
2. `tests/scripts/test_sf_mcp_client.py` (NEW) — 5 cases: JSON-RPC envelope formatting, timeout (use httpx mock), 3-retry exponential backoff, response size cap raises, redirect handling. Use `httpx` mock or `responses` library — match existing PSEO test fixture pattern.

## Files to MODIFY
3. `.mcp.json` — Append `"sf": { "url": "http://127.0.0.1:11435/mcp" }` to mcpServers object. Preserve exact byte format of existing 3 servers (do not reformat). After: total 4 servers.
4. `requirements.txt` — Add `httpx>=0.27,<1.0` if not present. Verify with `pip install -r requirements.txt` in a venv.
5. `docs/DECISIONS.md` — Append ADR-031: "v1.8 SF MCP integration — adopts HTTP transport (first HTTP MCP); intentionally breaks F-16 .mcp.json byte invariant via controlled additive diff." Match existing ADR format (read last 3 ADRs first).

## Read ONLY
- 6 bootstrap files
- Files in CREATE/MODIFY

## Do NOT read
- skills/* (Phase 3-5)
- schemas/* (already done in Phase 1)
- hooks/, commands/ (Phase 6)
- Existing tests for skills (only need test_scrapling_ops or test_gsc_pull patterns for mock style)

## Verification (RUN BEFORE returning)
```bash
# Client tests
python3 -m pytest tests/scripts/test_sf_mcp_client.py -v
# → 5 cases PASS

# .mcp.json still valid JSON
python3 -c "import json; print(len(json.load(open('.mcp.json'))['mcpServers']))"
# → "4"

# claude mcp list — manual operator step (cannot automate in worker)
# Operator runs: claude mcp list
# Expected: 4 servers listed including sf

# Baseline regression
python3 -m pytest -q 2>&1 | tail -5
# → all PASS (new 5 added; baseline maintained)

# httpx is installed
python3 -c "import httpx; print(httpx.__version__)"
# → version >= 0.27
```

## Forbidden
- Touch SKILL.md files (Phase 3+)
- Touch schemas/* (Phase 1 owned)
- Touch sf-import / orchestrator (Phase 3-4)
- Commits — leave staged

## Return — Worker Output Package
Per SESSION_PROTOCOL §13.4. Include: exact .mcp.json diff (before/after), httpx version installed, ADR-031 text snippet.
```

---

# PROMPT 3 — Phase 3: Orchestrator Skill (BIGGEST)

**Copy below into fresh Claude Code session. This is the largest phase (~2.5 days).**

```
# Worker Prompt: PSEO v1.8 Phase 3 — sf-crawl-orchestrator Skill (MCP-Primary)

You are a Fresh Worker Session. This phase is the heart of v1.8. Bootstrap reading:

1. `docs/PHASE_STATUS.md` — confirm Active Phase = "v1.8 Phase 3" (Phase 1+2 DONE)
2. `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` — read sections: "Decision Record" (D-SF-06/07/16), "MCP-Primary Data Flow + 24-Report Loop" (FULL — your spec), "Skills Integration Matrix Category A", "Risks + Mitigations" (R1-R13 — your DURURs map to these), "Implementation Phase Outline" Phase 3 row
3. `skills/ingestion/sf-import/SKILL.md` — pattern reference (8-step protocol you'll mirror; sf-import body UNCHANGED, you only add source_run_id input handler)
4. `scripts/state/workflow_runner.py` — API reference (create_run line 367, start_step 648, finish_step 660, complete 636, fail 582, pause 564, resume 573)
5. `scripts/state/events_writer.py` — append_provenance (line 384) for sf_mcp events, append_workflow (466) for orchestrator lifecycle
6. `scripts/util/sf_mcp_client.py` — your dependency (Phase 2 output)

## Scope
Phase 3: 8 tasks. Implement `sf-crawl-orchestrator` skill end-to-end.

## Files to CREATE
1. `skills/ingestion/sf-crawl-orchestrator/SKILL.md` (NEW) — Full skill per spec Category A row + MCP-Primary section. Frontmatter MUST validate against `schemas/skill-frontmatter.schema.json` (run schema-validate after writing). Body has 9 steps:
   - Step 1 `create_run` — workflow_runner.create_run with 9 steps (preflight, crawl, poll, [export]×24 logical step, atomic_move, invoke_sf_import, provenance, complete)
   - Step 2 `preflight` — call `mcp__sf__sf_list_allowed_base_directory` (D-SF-10); compare with `project.config.sf.mcp.allowed_directory`; call `mcp__sf__sf_crawl_progress` to check ANY in-progress crawl (R13 DURUR-orch-7); validate SF GUI responsive (no IllegalStateException)
   - Step 3 `crawl_trigger` — `mcp__sf__sf_crawl(url=project_config.domain, config=project_config.sf.mcp.crawl_config_path or default)` → returns crawl_id; emit `sf_mcp_crawl_started` event
   - Step 4 `poll` — loop `mcp__sf__sf_crawl_progress(crawl_id)` every 60s; max wait `project_config.sf.mcp.max_wait_minutes` (Q-SF-MCP-03 default 180); DURUR-orch-3 on timeout
   - Step 5-6 `export_24_reports` — iterate the 24-report list from spec; per-report `mcp__sf__sf_generate_report(crawl_id, report_name, save_report=True, output_dir=allowed_directory, timeout=per_report_timeout_seconds)`; atomic move each CSV to `_state/staging/sf-crawl-{run_id}/{report_name}.csv`; Tier 1 fail → DURUR-orch-8 + rollback; Tier 2 fail → AMBER + continue (matches sf-import Tier policy)
   - Step 7 `atomic_move` — `shutil.move(_state/staging/sf-crawl-{run_id}, projects/{slug}/sf-exports/{today}/raw)`; target dir conflict → DURUR-orch-5
   - Step 8 `invoke_sf_import` — subprocess: `python3 -m scripts.ingestion.sf_import --project {slug} --sf-export-path projects/{slug}/sf-exports/{today}/ --source-run-id {run_id}` (Q-SF-MCP-05 default YES)
   - Step 9 `complete` — workflow_runner.complete with outputs map (reports_exported, amber_missing, sf_import_run_id)
   - 7 DURURs: orch-1 (GUI not responsive), orch-2 (modal dialog), orch-3 (timeout), orch-4 (no allowed dir), orch-5 (target conflict), orch-6 (file move fail), orch-7 (concurrent crawl per R13)
   - Frontmatter requires_approval: per Q-SF-MCP-02 default YES
2. `scripts/ingestion/sf_crawl_orchestrator.py` (NEW, ~200 LoC) — Pure transform helper. Functions: `enumerate_reports(include_tier3: bool = False) → list[str]`, `move_with_rollback(temp_dir, target_dir) → bool`, `parse_progress_response(response) → ProgressState namedtuple`. Does NOT call MCP directly (that's SKILL.md body). Mirrors gsc_pull.py / dfs_pull.py pure-function discipline.
3. `tests/skills/test_sf_crawl_orchestrator.py` (NEW) — 10 cases:
   - happy_path_24_reports
   - DURUR-orch-1 GUI not responsive (mock allowed_base_directory raises)
   - DURUR-orch-2 IllegalStateException (modal dialog open)
   - DURUR-orch-3 max_wait timeout
   - DURUR-orch-4 allowed_directory mismatch
   - DURUR-orch-5 target dir conflict
   - DURUR-orch-6 file move fail (mock shutil.move raises)
   - DURUR-orch-7 concurrent crawl detected
   - DURUR-orch-8 Tier 1 export fail → rollback (verify temp staging deleted)
   - sf-import handoff success (mock subprocess returns 0)
4. `tests/scripts/test_sf_crawl_orchestrator.py` (NEW) — 6 cases: enumerate_reports default (24), enumerate_reports with Tier 3 (40), move_with_rollback success, move_with_rollback target exists, parse_progress_response shape, source_run_id chaining
5. `tests/smoke/test_sf_mcp_smoke.py` (NEW) — 1 case live MCP smoke. Mark with `@pytest.mark.skipif(not _is_sf_mcp_running(), reason="SF MCP not connected")` where `_is_sf_mcp_running()` does `httpx.get("http://127.0.0.1:11435/mcp/health", timeout=1).status_code == 200`. Runs only when SF GUI + MCP active. CI skips automatically.
6. **(v2.2 NEW)** `templates/reports/sf-crawl.template.md` (NEW) — Orchestrator run summary report template. Mirror existing `templates/reports/dfs-pull.template.md` + `templates/reports/gsc-pull.template.md` pattern. 7 sections: Summary, 24 Reports Status (table), Tier 1 / Tier 2 Counts, AMBER Warnings, sf-import Handoff Result, Total Duration, Recommendations. Used by orchestrator at workflow completion.

## Files to MODIFY
7. `skills/ingestion/sf-import/SKILL.md` — Frontmatter only: add `source_run_id: { type: string, required: false, description: "..." }` under inputs. Body UNCHANGED (8-step protocol intact). DURUR list UNCHANGED. Per D-SF-07.

## Read ONLY
- 6 bootstrap files
- `tests/skills/test_sf_import.py` (for fixture/mock pattern)
- `tests/skills/conftest.py` (for shared fixtures)

## Do NOT read
- Other ingestion scripts beyond gsc_pull.py / dfs_pull.py pattern reference
- Discovery skills (Phase 5)
- Commands (Phase 6)

## Verification (RUN BEFORE returning)
```bash
# Schema-validate frontmatter
python3 scripts/validation/validate_schema.py skills/ingestion/sf-crawl-orchestrator/SKILL.md
# → "OK" or "VALID"

# Orchestrator skill tests
python3 -m pytest tests/skills/test_sf_crawl_orchestrator.py -v
# → 10 PASS

# Orchestrator transform tests
python3 -m pytest tests/scripts/test_sf_crawl_orchestrator.py -v
# → 6 PASS

# sf-import regression — 8-step protocol UNCHANGED
python3 -m pytest tests/skills/test_sf_import.py -v
# → existing cases all PASS (no regression)

# Smoke skipif works (SF MCP not running in CI)
python3 -m pytest tests/smoke/test_sf_mcp_smoke.py -v
# → 1 SKIPPED (reason logged)

# Baseline + new tests
python3 -m pytest -q 2>&1 | tail -5
# → baseline + 17 new (10+6+1=17) all PASS/SKIPPED
```

## Forbidden
- Touch sf-import body (only frontmatter)
- Touch any other skill
- Touch .mcp.json (Phase 2)
- Touch schemas (Phase 1)
- Commits

## Return — Worker Output Package
List 10+6+1=17 new test functions by name. Verification section MUST include actual pytest output (last 5 lines).
```

---

# PROMPT 4 — Phase 4: Existing Skill Extensions (5 skills)

**Copy below into fresh Claude Code session:**

```
# Worker Prompt: PSEO v1.8 Phase 4 — Existing Skill Extensions

Fresh Worker Session. Bootstrap reading:

1. `docs/PHASE_STATUS.md` — confirm Active Phase = "v1.8 Phase 4" (Phase 1-3 DONE)
2. `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` — read: "Skills Integration Matrix Category B", "Schemas Impact Matrix", "Implementation Phase Outline" Phase 4 row
3. Each of the 5 SKILL.md files you'll touch (read each to understand current state):
   - `skills/governance/drift-check/SKILL.md`
   - `skills/governance/schema-validate/SKILL.md`
   - `skills/meta/init-project/SKILL.md`
   - `skills/meta/whats-next/SKILL.md`
   - (sf-import frontmatter already done in Phase 3 — verify it)
4. `schemas/cross-sheet-invariants.json` — F-23 invariant additive edit
5. `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py` — Phase 1 output, init-project cascades it

## Scope
Phase 4: 8 tasks. Extend 5 skills + add F-23 invariant + verify D-SF-09 no-cron.

## Files to MODIFY
1. `schemas/cross-sheet-invariants.json` — Add F-23 entry: `"F-23": { "description": "If any project's _state/workflows/ contains an sf-crawl-orchestrator run, mcp-tool-registry.json MUST list 'sf' in servers", "severity": "RED" }`. Follow existing F-01..F-22 format exactly (read first to understand schema).
2. `skills/governance/drift-check/SKILL.md` — Body: add F-23 check logic in invariant validation loop. Frontmatter: bump test_count comment if present (existing 27 → 28 invariants).
3. `skills/governance/schema-validate/SKILL.md` — Body: extend validation sweep to include new `schemas/sf-mcp-tool-mapping.schema.json`. Verify it parses + validates `templates/sf-mcp/use-case-example.json`.
4. `skills/meta/init-project/SKILL.md` — Body: when scaffolding new project, after writing project.config.json, cascade Migration 0005 if `--schema-version=1.5` flag passed (operator opt-in for v1.8+ projects). Read existing init-project body to understand scaffold flow.
5. `skills/meta/whats-next/SKILL.md` — Routing logic addition: when project.config.sf.mcp.enabled=true AND last `sf_mcp_crawl_completed` event in events.jsonl > 30 days ago (or no event), suggest "consider running /pseo-sf-crawl {slug}". Optional, non-blocking.

## Files to CREATE
6. `tests/skills/test_drift_check.py` extension — Add test case: F-23 violation detected when registry missing sf but workflow shows sf-crawl-orchestrator run. Use existing test pattern in file.
7. `tests/skills/test_schema_validate.py` extension — Add test case: sf-mcp-tool-mapping.schema.json present in validation sweep.
8. `tests/skills/test_init_project.py` extension — Add test case: new project with --schema-version=1.5 has sf block in project.config.json.
9. `tests/skills/test_whats_next.py` extension — Add test case: suggestion appears when last sf crawl > 30 days.
10. `tests/skills/test_sf_import.py` extension — Add test case: source_run_id from orchestrator appears in events.jsonl provenance (mock orchestrator handoff).
11. `tests/skills/test_no_cron_for_sf_crawl_orchestrator.py` (NEW) — D-SF-09 verification: 1 case asserting no hook JSON references sf-crawl-orchestrator with cron schedule.

## Read ONLY
- 5 bootstrap files
- Each SKILL.md you're editing
- Test files you're extending (to match pattern)

## Do NOT read
- Discovery/planning/production skills (Phase 5)
- commands/* (Phase 6)
- docs/* beyond spec sections listed

## Verification (RUN BEFORE returning)
```bash
# F-23 invariant + drift-check
python3 -m pytest tests/skills/test_drift_check.py -v
# → existing + new F-23 case PASS

# schema-validate extension
python3 -m pytest tests/skills/test_schema_validate.py -v

# init-project + whats-next + sf-import extensions
python3 -m pytest tests/skills/test_init_project.py tests/skills/test_whats_next.py tests/skills/test_sf_import.py -v

# D-SF-09 no-cron assertion
python3 -m pytest tests/skills/test_no_cron_for_sf_crawl_orchestrator.py -v

# drift-check skill itself runs (governance helper exec)
python3 scripts/ci/run_skill_python.py skills/governance/drift-check/SKILL.md
# → EXIT 0 (F-23 doesn't violate yet since no orchestrator runs exist in test fixtures)

# Baseline + new tests
python3 -m pytest -q 2>&1 | tail -5
```

## Forbidden
- Touch sf-import body (done in Phase 3)
- Touch orchestrator skill (Phase 3)
- Touch 4 discovery/planning consumer skills (Phase 5)
- Touch hooks (none changed per Q-SF-MCP-08 NO)
- Commits

## Return — Worker Output Package
List per-skill test pass/fail. Confirm F-23 entry in cross-sheet-invariants.json with line numbers.
```

---

# PROMPT 5 — Phase 5: Optional Consumer Wiring (4 skills)

**Copy below into fresh Claude Code session:**

```
# Worker Prompt: PSEO v1.8 Phase 5 — Optional Consumer Skill Wiring

Fresh Worker Session. Bootstrap reading:

1. `docs/PHASE_STATUS.md` — confirm Active Phase = "v1.8 Phase 5" (Phase 1-4 DONE)
2. `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` — read: "Skills Integration Matrix Category C", "Risks + Mitigations" (R9 + R12), "Implementation Phase Outline" Phase 5 row
3. Each of 4 SKILL.md files:
   - `skills/discovery/tech-audit/SKILL.md`
   - `skills/discovery/schema-audit/SKILL.md`
   - `skills/discovery/on-page-audit/SKILL.md`
   - `skills/planning/internal-links/SKILL.md`
4. `scripts/util/sf_mcp_client.py` (Phase 2 output — consumer skills call this)

## Scope (depends on Q-SF-MCP-07 — default ALL 4)
Phase 5: 4 skills get `use_sf_mcp_live: bool = False` flag. For each: frontmatter flag, body branch (preflight + AMBER fallback), R12 truncation detection, mock test, regression test.

## Files to MODIFY (for each of 4 skills)
- Frontmatter inputs: add `use_sf_mcp_live: { type: boolean, required: false, default: false, description: "Opt-in: when true, calls SF MCP for live data (D-SF-11). Requires SF GUI + MCP server running." }`
- Body: in main logic, add branch:
  ```python
  if use_sf_mcp_live:
      # Preflight: sf_mcp_client health check
      from scripts.util.sf_mcp_client import SfMcpClient
      client = SfMcpClient(base_url=project_config["sf"]["mcp"]["url"])
      if not client.health():
          # R9 AMBER fallback — continue with file-based path
          amber_warnings.append("SF MCP unavailable; falling back to file-based path")
      else:
          response = client.call_tool("sf_generate_report", crawl_id=..., report_name=..., save_report=False)
          if response.get("truncated", False):  # R12 truncation
              amber_warnings.append(f"SF MCP response truncated at 100KB cap for {report_name}")
          # ... merge into main results
  ```

## Files to CREATE / EXTEND
1. `tests/skills/test_tech_audit.py` extension — 2 cases: use_sf_mcp_live=True path mocks MCP + adds rows; use_sf_mcp_live=False unchanged (regression)
2. `tests/skills/test_schema_audit.py` extension — 2 cases (same pattern)
3. `tests/skills/test_on_page_audit.py` extension — 2 cases
4. `tests/skills/test_internal_links.py` extension — 2 cases

## Read ONLY
- 4 bootstrap files + 4 SKILL.md
- Each test file you're extending
- `scripts/util/sf_mcp_client.py` — your dependency

## Do NOT read
- Orchestrator code (Phase 3 owns)
- sf-import (Phase 3-4)
- Other skills not in your 4-skill scope

## Verification (RUN BEFORE returning)
```bash
# Per-skill tests
python3 -m pytest tests/skills/test_tech_audit.py tests/skills/test_schema_audit.py tests/skills/test_on_page_audit.py tests/skills/test_internal_links.py -v
# → all PASS (existing + 8 new cases)

# Regression: default use_sf_mcp_live=False behavior unchanged
python3 -m pytest tests/skills/test_tech_audit.py::test_default_behavior_no_mcp -v
# → PASS (existing fixture)

# Baseline
python3 -m pytest -q 2>&1 | tail -5
```

## Forbidden
- Touch orchestrator
- Touch sf-import body
- Touch hooks / commands / schemas
- Make any skill REQUIRE SF MCP (all 4 default OFF; this is opt-in only)
- Commits

## Return — Worker Output Package
Per-skill: line number where flag added, line numbers of body branch, test names added.
```

---

# PROMPT 6 — Phase 6: Commands + Manifest + Docs

**Copy below into fresh Claude Code session:**

```
# Worker Prompt: PSEO v1.8 Phase 6 — Commands + Manifest + Documentation

Fresh Worker Session. Bootstrap reading:

1. `docs/PHASE_STATUS.md` — confirm Active Phase = "v1.8 Phase 6" (Phase 1-5 DONE)
2. `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` — read: "Commands Additions", "Plugin Manifest Bump", "Documentation Updates", "Rules Impact"
3. `commands/pseo-gsc-pull.md` + `commands/pseo-quickwin.md` — pattern reference for new commands
4. `docs/RELEASE_NOTES_v1.7.0.md` — structure reference for v1.8 release notes
5. `docs/DECISIONS.md` — ADR-031 should already exist (Phase 2 added it); you'll verify
6. `docs/PHASE_STATUS.md` — milestone declaration pattern
7. `.claude-plugin/plugin.json` — manifest you'll bump

## Scope
Phase 6: 12 tasks. Commands + manifest + 8 docs + glossary + rules edit.

## Files to CREATE
1. `commands/pseo-sf-crawl.md` (NEW) — Markdown command per existing pattern. Frontmatter spec + invokes sf-crawl-orchestrator skill. Document --resume flag for paused workflows.
2. `commands/pseo-sf-status.md` (NEW) — Output is 4-column table: project_slug, last_crawl_date, sf_mcp_connection_status, allowed_directory_path. Document the format in command body. Inline bash block uses `mcp__sf__sf_list_allowed_base_directory` for live probe.
3. `docs/RELEASE_NOTES_v1.8.0.md` (NEW, ≥100 lines) — Match v1.7 structure: Summary, New Features, Schema Changes, Migrations, Tests, Acceptance Criteria results. **MUST BE CREATED BEFORE step 4** (version_bump.py WARNs if missing).

## Files to MODIFY (via scripts where possible)
4. **CRITICAL — USE `scripts/release/version_bump.py` (NOT manual)** — Run `python3 scripts/release/version_bump.py --to 1.8.0` first (dry-run), then `--apply`. This 5-file sync per ADR-036 updates:
   - `.claude-plugin/plugin.json` "version" 1.7.0 → 1.8.0
   - `.claude-plugin/marketplace.json` metadata.version + description "v1.8.0 — " prefix
   - `README.md` `> Status: **v1.8.0**` banner
   - `docs/INSTALL.md` `> Status: **v1.8.0**` banner
   - `docs/RELEASE_NOTES_v1.8.0.md` existence check (must exist from step 3)
5. `.claude-plugin/plugin.json` description string (MANUAL edit AFTER version_bump.py): "43 skill, 15 slash command, 6 hook, 3 MCP server" → "45 skill, 18 slash command, 6 hook, 4 MCP server". Pre-existing v1.7 drift (43→44, 15→16) fixed here on top of v1.8 targets.
6. **(v2.2 NEW)** `commands/pseo-status.md` — EXTEND: add new H2 section "## SF MCP Status" with inline bash block `mcp__sf__sf_list_allowed_base_directory` probe; integrate result into existing table output.
7. **(v2.2 NEW)** `commands/pseo-driftcheck.md` — EXTEND: update example output section to mention 31 invariants (was 27); add F-23/24/25/26 example violation messages.
8. **(v2.2 NEW)** `commands/pseo-init.md` — EXTEND: add new flag `--schema-version=1.5` docs; add note about Migration 0005 auto-cascade for new projects.
9. **(v2.2 NEW)** `commands/pseo-schema-audit.md` — EXTEND: document `--use-sf-mcp-live` flag exposing Phase 5 skill input.
10. `README.md` — Add new H2 section `## Screaming Frog 24 MCP (Optional)` with subsections "Setup", "SF Settings (recommended)", ".mcp.json snippet", "First Crawl Walkthrough". (Banner already updated by version_bump.py.)
11. **(v2.2 NEW)** `docs/INSTALL.md` — Add SF MCP setup section alongside existing "claude mcp list" troubleshooting note. (Banner already updated by version_bump.py.)
12. `docs/WORKFLOWS.md` — Add H3 `### SF crawl via MCP` workflow with sequence diagram (Mermaid or ASCII). Also add Migration 0005 operator walkthrough.
13. `docs/ARCHITECTURE.md` §7 (SF Reports) — Update to note v1.8+ supports MCP-primary + file-based fallback (per D-SF-07 + v2.2 pivot).
14. `docs/ARCHITECTURE.md` §16.5 (MCP Discipline) — Update for HTTP MCP transport. Note 4 MCP servers (was 3). Note mcp-tool-registry.json instance now exists at repo root.
15. `docs/OPEN_QUESTIONS.md` — Add Q-SF-MCP-01..11 entries (all 11 questions per spec). Mark Q-08 RESOLVED.
16. `docs/PHASE_STATUS.md` — Update Active Phase line to "v1.8.0 Phase 6 COMPLETE" (Phase 7 starts after this). v1.8 milestone declared with phase list.
17. `docs/GLOSSARY.md` — Add 4 terms from spec Glossary section: SF MCP, SF orchestrator, Optional consumer, Hybrid mode.
18. **(v2.2 NEW)** `docs/REFERENCE_INDEX.md` — Add entries: sf-crawl-orchestrator skill, sf_mcp_client utility, pseo-sf-crawl + pseo-sf-status commands, sf-mcp-tool-mapping schema, mcp-tool-registry.json instance, Migration 0005.
19. `docs/CONTRIBUTING.md` — If section on MCP setup exists, update for SF. Else skip.
20. `rules/events-writer.md` line 129 — Insert new row alongside existing sf-import row: `| sf-crawl-orchestrator | ingest, staging | sf_mcp | Screaming Frog MCP-triggered crawl ingest |`

## Read ONLY
- 7 bootstrap files
- Each file in MODIFY (read current state first)
- Existing commands/*.md (2-3 of them, pattern reference)

## Do NOT read
- Any skill/script code (already done in Phase 1-5)

## Verification (RUN BEFORE returning)
```bash
# version_bump.py 5-file sync verification (CI invariant test)
python3 -m pytest tests/ci/test_version_sync.py -v
# → PASS (all 5 files show v1.8.0)

# Plugin manifest parses + correct description
python3 -c "import json; m=json.load(open('.claude-plugin/plugin.json')); print(m['version'], '|', m['description'][:60])"
# → "1.8.0 | ...45 skill, 18 slash command..."

# All 2 new + 4 extended commands exist + markdown valid
for cmd in commands/pseo-sf-crawl.md commands/pseo-sf-status.md commands/pseo-status.md commands/pseo-driftcheck.md commands/pseo-init.md commands/pseo-schema-audit.md; do echo "=== $cmd"; head -5 "$cmd"; done

# Extended commands contain SF MCP references
grep -l "sf_mcp\|sf-mcp\|sf-crawl-orchestrator\|--use-sf-mcp-live\|--schema-version=1.5\|SF MCP Status" commands/pseo-status.md commands/pseo-driftcheck.md commands/pseo-init.md commands/pseo-schema-audit.md
# → all 4 listed (one per file)

# 10 doc files updated
grep -l "Screaming Frog 24 MCP\|sf_mcp\|sf-crawl-orchestrator" README.md docs/INSTALL.md docs/WORKFLOWS.md docs/ARCHITECTURE.md docs/OPEN_QUESTIONS.md docs/DECISIONS.md docs/RELEASE_NOTES_v1.8.0.md docs/PHASE_STATUS.md docs/REFERENCE_INDEX.md docs/GLOSSARY.md
# → all 10 listed

# rules/events-writer.md edited
grep "sf-crawl-orchestrator" rules/events-writer.md
# → 1 line present

# Release notes ≥100 lines
wc -l docs/RELEASE_NOTES_v1.8.0.md
# → ≥100

# Baseline regression
python3 -m pytest -q 2>&1 | tail -5
# → all PASS (this phase doesn't change code, only docs/commands)
```

## Forbidden
- Touch SKILL.md / scripts / schemas (done in Phase 1-5)
- Create new test files (this is doc phase)
- Commits (Phase 7 commits everything atomically)

## Return — Worker Output Package
List each doc updated + section header added + line count. Confirm plugin.json description exact text.
```

---

# PROMPT 7 — Phase 7: Pilot Smoke + Release

**Copy below into fresh Claude Code session:**

```
# Worker Prompt: PSEO v1.8 Phase 7 — Pilot Smoke + Release

Fresh Worker Session. Final phase. Bootstrap reading:

1. `docs/PHASE_STATUS.md` — confirm Active Phase = "v1.8 Phase 7" (Phase 1-6 DONE)
2. `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` — read: "Acceptance Criteria" (all 20), "Implementation Phase Outline" Phase 7 row
3. `docs/RELEASE_NOTES_v1.8.0.md` — verify Phase 6 produced this
4. Operator's recent git log for v1.7 closeout pattern: `git log --oneline | head -20`

## Scope
Phase 7: 7 tasks. Live pilot smoke + verify 20 ACs + release.

## Tasks (sequential)
1. **Live run on vento** — `/pseo-sf-crawl vento` (operator-facing OR `python3 -c "from scripts.ingestion.sf_crawl_orchestrator import main; main(...)"` directly). Capture output to `/tmp/v1.8-vento-smoke.log`. ⚠️ This requires SF GUI running with MCP server started.
2. **Verify AC-10** — 3-part smoke check (run all 3 commands from AC-10 in spec; record outputs to `docs/PHASE_STATUS.md` v1.8 evidence block)
3. **Verify AC-13** — tech-audit `use_sf_mcp_live=True` on vento; compare rowcount(live) vs rowcount(file-only); record to PHASE_STATUS.md
4. **Drift-check 28 invariants GREEN** — `python3 scripts/ci/run_skill_python.py skills/governance/drift-check/SKILL.md` → EXIT 0
5. **Schema-validate full sweep GREEN** — `python3 scripts/ci/run_skill_python.py skills/governance/schema-validate/SKILL.md` → EXIT 0
6. **Full pytest baseline GREEN** — `python3 -m pytest -q 2>&1 | tail -5` → "1213 passed" or "1225 passed" depending on test granularity (see spec Tests Plan)
7. **Rollback drill** — In a temp branch, `git revert HEAD~N..HEAD` (N = number of v1.8 commits), then `python3 scripts/migrations/migration_0005_project_config_1_4_to_1_5.py --project vento --reverse` (or equivalent rollback if migration script supports), then `python3 -m pytest -q | tail -3` → should restore 1184 baseline (v1.7 state)
8. **Git tag + push** — `git tag -a v1.8.0 -m "SF MCP Hybrid Integration (24-report MCP-primary + 4 consumer skills + Migration 0005)"`. **DO NOT push to remote without operator approval.**

## Files to MODIFY
- `docs/PHASE_STATUS.md` — Update Active Phase to "v1.8.0 SHIPPED {commit_sha}" with evidence block (AC-10 outputs, AC-13 rowcount comparison)

## Read ONLY
- 4 bootstrap files
- `docs/RELEASE_NOTES_v1.8.0.md`

## Do NOT read
- Skill/script bodies (Phase 1-5 done — only verify they work)

## Verification — IS the verification (no separate command set)

## Forbidden
- Touch code beyond PHASE_STATUS.md edit
- Push tag to remote without operator approval
- Skip rollback drill (even if all ACs pass)
- Mark phase complete if ANY AC fails

## Return — Worker Output Package
- Files Created/Modified: only PHASE_STATUS.md
- Each of 20 ACs: ✅/❌ with evidence (command output or "[manual operator check]")
- Rollback drill outcome: ✅ baseline restored / ❌ blocked at step X
- Git tag created: ✅/❌ (sha)
- Next Step: "operator pushes tag + closes v1.8 milestone" or "fix AC-X first"
```

---

# Manager Session — Between-Phase Workflow

After each Worker returns a Worker Output Package, Manager (Süleyman's persistent session) does:

1. **Read package** (compact, no full transcript). ~1-2KB.
2. **Verify package against spec Acceptance Criteria** — for ACs the phase touches.
3. **Update state docs:**
   - `docs/PHASE_STATUS.md` — mark phase done, advance Active Phase
   - `docs/DECISIONS.md` — log any new ADRs surfaced
   - `docs/OPEN_QUESTIONS.md` — log new Q surfaced + close any resolved
   - `docs/CONTEXT_LEDGER.md` — append phase summary (1-2 lines)
4. **Commit atomic** — `git add ... && git commit -m "v1.8 Phase N: <summary>"` per phase
5. **Decide GO/NO-GO** for next phase:
   - GO: dispatch next Worker Prompt (next prompt in this file)
   - NO-GO: spawn fix Worker (narrower scope) before retry
6. **Loop** until Phase 7 completes

Manager NEVER:
- Reads worker transcript beyond package
- Writes code directly (always delegates to fresh Worker)
- Skips a phase
- Pushes git tag without operator confirmation

---

# Operator (Süleyman) Action Checklist

| Step | Action | Where |
|------|--------|-------|
| 0 | Resolve Pre-Phase-1 Operator Decisions table at top of this file (or accept defaults) | Manager session |
| 1 | Approve spec v2.2 + this Worker Prompts file | Manager session |
| 2 | Open fresh Claude Code session | Operator's terminal |
| 3 | Paste Prompt 1 | Fresh Worker session |
| 4 | Wait for Worker Output Package | — |
| 5 | Paste package into Manager session | Manager session |
| 6 | Manager reviews + commits + advances PHASE_STATUS | Manager session |
| 7 | Repeat steps 2-6 for Prompts 2..7 | — |
| 8 | After Phase 7 GREEN: operator pushes git tag, closes v1.8 milestone | Manager session |

Estimated total operator engagement: 1-2 hours/day across 7 days of execution. Most time is Workers running tests + writing files; operator is just dispatcher + reviewer.

---

## Sources / Cross-references

- Spec: `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` (v2.2)
- Session Protocol: `docs/SESSION_PROTOCOL.md` §13.1 (Manager role) + §13.2 (Worker bootstrap) + §13.4 (Output Package format)
- Worker Templates: `docs/WORKER_PROMPTS.md` (4 template types — these 7 prompts adapt those patterns to v1.8 scope)
- Phase Definitions: spec "Implementation Phase Outline" section
- Acceptance Criteria: spec "Acceptance Criteria (expanded — 20 items)"
- DURUR conditions: per phase's relevant skill SKILL.md (sf-import has 6 DURURs; sf-crawl-orchestrator has 8 after v2.2 D-SF-16)
