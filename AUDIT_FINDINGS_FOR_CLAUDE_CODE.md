# Platinum SEO Engine + Workspace Audit Handoff

Generated: 2026-06-03

Audience: Claude Code or another implementation agent.

Important: this file is an audit handoff only. Do not commit, stage, revert, or
overwrite unrelated local changes unless the human explicitly asks for that.

## Repositories

- Engine: `/Users/apple/Documents/platinum-seo-engine`
- Workspace: `/Users/apple/Documents/platinum-seo-workspace`
- Engine remote: `https://github.com/popiliadam/platinum-seo-engine`
- Workspace remote: `https://github.com/popiliadam/platinum-seo-workspace`

## Current Local State At Crosscheck

Current engine working tree includes uncommitted local changes. This report adds
one more untracked file. Preserve unrelated changes:

- `.github/workflows/ci.yml`
- `README.md`
- `hooks/pre-tool-use.json`
- `scripts/excel/transaction.py`
- `tests/scripts/test_transaction.py`
- `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`

Workspace is also dirty and contains tracked modifications plus many untracked
project directories/artifacts. Treat the local workspace as live runtime state,
not a clean clone.

Current crosscheck results:

```bash
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 -m pytest --tb=short -q
# 1449 passed, 8 skipped in 16.62s
```

Targeted workspace schema checks still fail:

```bash
python3 scripts/validation/validate_schema.py \
  /Users/apple/Documents/platinum-seo-workspace/shared/portfolio.json \
  schemas/portfolio-config.schema.json
# FAIL: active_projects is too long

python3 scripts/validation/validate_schema.py \
  /Users/apple/Documents/platinum-seo-workspace/projects/dentnotion/project.config.json \
  schemas/project-config.schema.json
# FAIL: schema_version: '1.5' was expected

PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 scripts/state/dump_workspace.py --json
# FAIL: shared/active.json has no 'slug' key

PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 scripts/state/dump_workspace.py --project dentnotion --json
# PASS
```

## System Philosophy

The engine is designed as a Claude Code plugin that owns SEO operating logic,
governance, schemas, commands, hooks, skills, scripts, and MCP boundaries. The
workspace is designed to hold only portfolio/project data, event state, Excel
workbooks, raw inboxes, and outputs.

The intended philosophy is strong:

- schema-first contracts
- append-only JSONL event state
- Excel as a controlled operational database
- two-repo separation between reusable engine and client data
- MCP inventory and mapping discipline
- drift-check/governance as a first-class product surface
- no client-specific logic inside the engine

The main audit theme is not lack of architecture. The theme is implementation
drift: several validators, registries, docs, commands, and workspace files no
longer agree on the same contract.

## Recommended Fix Order

1. Fix contract authority drift first: cross-sheet invariant registry vs
   implementation, MCP registry, `dump_workspace.py`, workspace schemas.
2. Fix slash command operational breakages: allowed-tools, stale paths, stale SF
   flags, and shell/Python injection edges.
3. Tighten schemas and validators: `FormatChecker`, event conditionals, nested
   `additionalProperties`.
4. Harden write/audit paths: Excel transaction behavior, event/workflow emission,
   hook audit classification.
5. Clean stale docs/skills/templates after behavior is aligned.
6. Add tests for each drift class so the same mismatch cannot return.

## Crosscheck Notes: Issues Already Fixed Locally But Not Necessarily In HEAD

These should not be reopened as active bugs if Claude Code works from the
current local tree. They do still matter if auditing committed `HEAD` or GitHub
main.

### Local-Fixed 1: CI MCP Server Count

`HEAD` expected 3 MCP servers in `.github/workflows/ci.yml`, while `.mcp.json`
contains 4. Current local working tree has already changed the invariant to 4.

Evidence:

- `git show HEAD:.github/workflows/ci.yml` has `= "3"`.
- Current `.github/workflows/ci.yml` has `= "4"`.
- `.mcp.json` currently has `ScraplingServer`, `dataforseo`, `gsc`, `sf`.

Action: verify the local change is intentional and keep/update tests around this
literal.

### Local-Fixed 2: PreToolUse Secret Scan Performance

`HEAD` ran a full `check_secrets.sh` scan on every PreToolUse hook. Current
local working tree invokes:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/security/check_secrets.sh" --changed-since HEAD "${CLAUDE_PROJECT_DIR:-.}"
```

The script supports the flag and the current incremental scan passed:

```bash
bash scripts/security/check_secrets.sh --changed-since HEAD .
# SECURITY GATE GREEN
```

Action: add/adjust tests so the hook must use incremental mode.

### Local-Fixed 3: `transaction.update()` Row Scan

`HEAD` scanned update rows from hardcoded row 2. Current local working tree uses
`_data_start_row(schema, sheet)` and adds a regression test.

Action: keep the local fix. Remaining Excel findings below still apply.

### Local-Fixed 4: README JSON Schema Draft Wording

`HEAD` said JSON Schema Draft 2020-12 in `README.md`. Current local working tree
now says Draft 7, matching all `schemas/*.schema.json` files and
`scripts/validation/validate_schema.py`.

Action: keep the local wording fix and add a test that README/docs, schema
`$schema`, and validator class agree.

## P0 Findings

### P0-01: Cross-Sheet Invariant Registry And Implementation Mean Different Things

Status: active in current local tree.

Risk: governance reports can say an F-rule passed/failed while humans read a
different rule definition. This undermines the core schema-first philosophy.

Evidence:

- `schemas/cross-sheet-invariants.json` declares F-01 as:
  `master_task.url ⊆ (crawl_sitemap.url ∪ external_urls)`.
- `scripts/validation/validate_invariants.py` implements F-01 as:
  `master_task.status ⊆ statusEnum`.
- Registry F-02 says dashboard done-count equality.
- Code F-02/F-03/F-04 are dashboard formula-token checks.
- Registry F-05 says completed work task-done consistency.
- Code F-05 checks sheet header counts.

Affected files:

- `schemas/cross-sheet-invariants.json`
- `scripts/validation/validate_invariants.py`
- `tests/schemas/test_cross_sheet_invariants_sync.py`

Reproduce:

```bash
rg -n '"id": "F-01"|"id": "F-02"|"id": "F-05"' schemas/cross-sheet-invariants.json
rg -n 'F-01|F-02|F-05|statusEnum|header' scripts/validation/validate_invariants.py
```

Expected fix:

- Decide the single authority.
- Either update registry definitions to match implemented behavior or rewrite
  implementation to match registry.
- Add semantic tests, not just ID/severity tests. A minimal test should map each
  F-ID to an implementation function/category and assert the human description
  cannot drift silently.

Suggested test:

- Add a machine-readable `implementation_key` or `check_type` to each registry
  entry.
- Test that every F-ID in the registry is implemented by exactly one check.
- Test that no implementation emits an F-ID whose registry definition belongs to
  a different category.

### P0-02: `dump_workspace.py` Uses Old `slug` Field Instead Of Canonical `active_project`

Status: active in current local tree.

Risk: manager/session summary fails unless `--project` is passed explicitly.
This breaks the active workspace contract.

Evidence:

- `shared/active.json` in workspace contains `active_project`.
- ADR-032 and hook tests treat `active_project` as canonical.
- `scripts/state/dump_workspace.py` still reads `data.get("slug")`.
- `tests/scripts/test_dump_workspace.py` writes the old shape, hiding the bug.

Reproduce:

```bash
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 scripts/state/dump_workspace.py --json
# error: shared/active.json has no 'slug' key
```

Expected fix:

- Read `active_project` first.
- Optionally support legacy `slug` with an AMBER warning if backward
  compatibility is needed.
- Update tests to write `{"active_project": "...", "updated_at": "..."}`.

Suggested test:

- `test_dump_workspace_reads_active_project_contract`
- `test_dump_workspace_legacy_slug_warns_or_fails_intentionally`

### P0-03: MCP Tool Registry Is Incomplete And Version-Lagged

Status: active in current local tree.

Risk: the runtime MCP surface used by skills is broader than the auditable
registry. Drift-check can pass while skills rely on undeclared tools.

Evidence:

- `.mcp.json` launches `dataforseo-mcp-server@2.8.10`.
- `mcp-tool-registry.json` still locks DataForSEO to `2.8.9`.
- Registry has 33 tool entries.
- Skill frontmatter has 77 MCP refs.
- Crosscheck found 37 frontmatter refs not directly in registry:
  - 24 true missing non-Scrapling refs.
  - 13 Scrapling refs affected by alias mismatch (`ScraplingServer` wrapper vs
    `scrapling` registry key).

True missing non-Scrapling examples:

- `mcp__dataforseo__dataforseo_labs_google_competitors_domain`
- `mcp__dataforseo__dataforseo_labs_google_domain_rank_overview`
- `mcp__dataforseo__backlinks_competitors`
- `mcp__dataforseo__dataforseo_labs_google_historical_rank_overview`
- `mcp__dataforseo__dataforseo_labs_google_keyword_ideas`
- `mcp__dataforseo__dataforseo_labs_google_related_keywords`
- `mcp__dataforseo__content_analysis_search`
- `mcp__dataforseo__ai_optimization_llm_mentions_search`
- `mcp__dataforseo__ai_optimization_llm_mentions_aggregated_metrics`
- `mcp__dataforseo__on_page_content_parsing`
- `mcp__dataforseo__dataforseo_labs_google_historical_keyword_data`
- `mcp__dataforseo__dataforseo_labs_google_keyword_suggestions`
- `mcp__dataforseo__dataforseo_labs_search_intent`
- `mcp__dataforseo__keywords_data_google_trends_explore`
- `mcp__higgsfield__generate_image`
- `mcp__higgsfield__job_status`

Scrapling alias mismatch examples:

- Skills use `mcp__ScraplingServer__fetch`.
- Registry stores `scrapling__fetch`, implying `mcp__scrapling__fetch`.
- `.mcp.json` server key is `ScraplingServer`.
- `schemas/mcp-tool-registry.schema.json` says registry keys are the same keys
  used in `.mcp.json`, but registry uses `scrapling`.

Expected fix:

- Update DataForSEO version lock to match `.mcp.json` or pin `.mcp.json` back.
- Add every skill-used DataForSEO tool to the registry.
- Decide whether Higgsfield is user-level optional or plugin-managed. If
  user-level, represent it explicitly as external/user dependency so production
  skill preflight can fail clearly.
- Normalize `ScraplingServer` vs `scrapling` with either:
  - registry key = `ScraplingServer`, or
  - explicit alias field + tests.

Suggested tests:

- Parse all `skills/**/SKILL.md` frontmatter `mcp_tools.required/optional`.
- Convert known aliases.
- Fail if any required tool is absent from registry.
- Fail if `.mcp.json` package version differs from registry `version_lock`.

### P0-04: Workspace Config Files Fail Current Engine Schemas

Status: active in current local tree.

Risk: workspace is live but not schema-compatible with the engine’s current
contract. This weakens all commands that trust schema validation before writing.

Evidence:

- `projects/dentnotion/project.config.json` has schema version older than `1.5`.
- `shared/portfolio.json` has 10 active projects in local state.
- `schemas/portfolio-config.schema.json` caps `active_projects` at 8.

Reproduce:

```bash
python3 scripts/validation/validate_schema.py \
  /Users/apple/Documents/platinum-seo-workspace/projects/dentnotion/project.config.json \
  schemas/project-config.schema.json

python3 scripts/validation/validate_schema.py \
  /Users/apple/Documents/platinum-seo-workspace/shared/portfolio.json \
  schemas/portfolio-config.schema.json
```

Expected fix:

- Provide a workspace migration script for `project.config.json` 1.3/1.4 to 1.5.
- Revisit `portfolio-config.schema.json` `maxItems: 8`; current portfolio has
  grown beyond that. If 8 is a product limit, workspace must enforce portfolio
  archival. If not, schema should be raised or made configurable.
- Add a CI/workspace validation mode that reports workspace red state without
  blocking engine-only CI unexpectedly.

### P0-05: Slash Command Allowed-Tools Do Not Match Real Shell Usage

Status: active in current local tree.

Risk: commands may fail in Claude Code because the command body uses shell
programs not declared in `allowed-tools`.

Current crosscheck found 18 command allowed-tool mismatches:

- `pseo-active.md`: uses `mkdir`, allowed lacks `Bash(mkdir:*)`.
- `pseo-gbp-audit.md`: uses `grep`, allowed lacks `Bash(grep:*)`.
- `pseo-init.md`: uses `head`, allowed lacks `Bash(head:*)`.
- `pseo-schema-audit.md`: uses `head`, `sort`, allowed lacks both.
- `pseo-sf-crawl.md`: uses `curl`, `head`, allowed lacks both.
- `pseo-sf-status.md`: uses `grep`, `head`, `sort`, `tail`, `xargs`, allowed
  lacks all.
- `pseo-status.md`: uses `curl`, `find`, `grep`, `sort`, `tail`, `xargs`,
  allowed lacks all.

Reproduce:

```bash
python3 - <<'PY'
# Parse commands/*.md, extract allowed-tools, and compare with shell commands
# used inside !`...` blocks.
PY
```

Expected fix:

- Add missing `Bash(<cmd>:*)` entries.
- Add a test that scans command bodies and fails on undeclared command usage.

### P0-06: SF Crawl Command Still Documents Invalid Runtime Contract

Status: active in current local tree.

Risk: `/pseo-sf-crawl` can instruct Claude Code to call nonexistent/invalid
flags or older MCP shapes.

Evidence:

- `commands/pseo-sf-crawl.md` still says `save_report=True`.
- It says to invoke `sf_import.py --source-run-id`.
- `scripts/ingestion/sf_import.py` accepts only:
  - `--project`
  - `--sf-export-path`
  - `--workspace-root`
  - `--dry-run`
- `skills/ingestion/sf-crawl-orchestrator/SKILL.md` itself warns that
  `--source-run-id` is not a script flag and would make argparse exit 2.

Expected fix:

- Update `/pseo-sf-crawl` to match the current orchestrator contract.
- Remove `save_report=True` references from active command/workflow docs unless
  they are explicitly historical.
- Ensure command required MCP tools include all SF tools the skill actually
  uses:
  - `mcp__sf__sf_crawl`
  - `mcp__sf__sf_crawl_progress`
  - `mcp__sf__sf_generate_report`
  - `mcp__sf__sf_generate_bulk_export`
  - `mcp__sf__sf_export_seo_element_urls`
  - `mcp__sf__sf_list_allowed_base_directory`
  - `mcp__sf__sf_list_crawls`

## P1 Findings

### P1-01: JSON Schema Draft Wording Needs To Be Locked By Test

Status: fixed locally in `README.md`, still needs regression coverage.

Risk: this drift already happened once. Without a test, docs can again claim a
different JSON Schema draft than the validator actually uses.

Evidence:

- `HEAD:README.md` said JSON Schema Draft 2020-12.
- Current local `README.md` says Draft 7.
- All 20 `schemas/*.schema.json` files use Draft-07.
- `scripts/validation/validate_schema.py` uses `Draft7Validator`.

Expected fix:

- Add a test that docs, schema `$schema`, and validator class agree.

### P1-02: `format` Is Not Enforced During Schema Validation

Status: active in current local tree.

Risk: fields declared as URI/date-time can accept invalid strings in CLI checks.

Evidence:

- `scripts/validation/validate_schema.py` calls `Draft7Validator(schema)` without
  `FormatChecker`.
- Existing instance-validation tests also do not consistently enforce
  `FormatChecker`.

Expected fix:

- Use `Draft7Validator(schema, format_checker=FormatChecker())`.
- Update tests with intentionally invalid `format: uri` and `format:
  date-time` fixtures.

### P1-03: Nested Object Schemas Are Too Open For A Schema-First System

Status: active in current local tree.

Risk: typos and unexpected fields can pass validation inside critical nested
objects.

Crosscheck counts of object schemas missing `additionalProperties`:

- `project-config.schema.json`: 15
- `monthly-report.schema.json`: 17
- `dataforseo-endpoint-mapping.schema.json`: 8
- `gsc-tool-mapping.schema.json`: 5
- `portfolio-config.schema.json`: 5
- `sf-mcp-tool-mapping.schema.json`: 5
- Other schema files also have smaller counts.

High-risk project config open objects:

- `language`
- `paths`
- `gsc`
- `dataforseo`
- `brand`
- `content_settings` nested arrays
- `thresholds`
- `workflow`

Expected fix:

- Close critical nested objects with `additionalProperties: false`.
- Add negative fixtures with misspelled nested keys.
- If flexible extension points are needed, name them explicitly as
  `metadata`, `extensions`, or `x_*`.

### P1-04: Event Schema Conditionals Produce Noisy/Misleading Errors

Status: active in current local tree.

Risk: old or malformed events produce multiple unrelated errors because several
conditional branches apply when `event_kind` is absent.

Evidence:

- `schemas/events.schema.json` `if` blocks do not require `event_kind` inside
  the `if`.
- The schema description says “Three kinds” while enum has four:
  `provenance`, `work`, `audit`, `workflow`.

Expected fix:

- Add `required: ["event_kind"]` inside each conditional `if`.
- Update the description to four kinds.
- Add one invalid legacy event fixture and assert the error points to
  `event_kind`, not unrelated branch-specific fields.

### P1-05: Hook UX Still References Nonexistent `/pseo-bootstrap-project`

Status: active in current local tree.

Risk: user is told to run a command that does not exist.

Evidence:

- `hooks/session-start.json`
- `hooks/user-prompt-submit.json`

Expected fix:

- Replace `/pseo-bootstrap-project` with `/pseo-init` or the actual bootstrap
  command if a separate command is intended.
- Add a test that hook messages reference only existing `commands/*.md`.

### P1-06: PostToolUse Audit Hook Silently Drops Audit Failures

Status: active in current local tree.

Risk: state may mutate without audit record. This conflicts with append-only
audit discipline.

Evidence:

- `hooks/post-tool-use.json` ends the inline Python command with `|| true`.
- Bash commands are always classified as `accessed` in the hook.
- `scripts/state/events_writer.py` contains richer `normalize_audit_action`,
  but the hook does not pass command details into that classifier.

Expected fix:

- Decide which failures are allowed to be non-blocking.
- If audit emission must never block, write a visible warning/event elsewhere.
- Use `normalize_audit_action` for Bash commands so redirects, `rm`, `cp`, etc.
  are not always recorded as `accessed`.
- Add tests for Bash write/delete command classification.

### P1-07: PreToolUse Excel Owner-Lock Regex Is Too Narrow

Status: active in current local tree.

Risk: Excel owner-lock protection can miss paths with spaces, quotes, `~`, or
other common shell forms.

Evidence:

- `hooks/pre-tool-use.json` regex is path-pattern based and narrow.
- It only blocks when a `~$` sidecar exists.

Expected fix:

- Parse tool input paths rather than regexing raw shell text when possible.
- Cover quoted paths and spaces.
- Add hook tests for:
  - `"my workbook.xlsx"`
  - `~/.../master.xlsx`
  - single quotes
  - shell redirection into `.xlsx`

### P1-08: Inline Python In Slash Commands Injects Unvalidated Shell Args

Status: active in current local tree.

Risk: a slug containing a quote can break the embedded Python source, and the
pattern is fragile.

Evidence:

- `commands/pseo-active.md` embeds `SLUG="$1"` into Python as `slug = '$SLUG'`.
- `commands/pseo-status.md` embeds project in a Python script similarly.
- `pseo-active` can write an active marker even when config is missing.

Expected fix:

- Pass shell args to Python via env vars or `sys.argv`.
- Validate slug with the same regex used in schemas.
- Decide whether setting active should fail if project config is missing.

### P1-09: Excel Transaction Still Has Schema Contract Gaps

Status: partially active in current local tree.

Already fixed locally:

- `update()` now scans from schema `data_start_row` instead of row 2.

Still active:

- `_ensure_sheet_with_header` writes headers to row 1 even though the schema has
  `header_row` and `data_start_row` metadata.
- Row validation sets `additionalProperties: True`.
- Extra keys are silently skipped during write.
- Writer registry status is advisory, not enforced by write/append/update.

Risk:

- Template workbooks with decorative/header rows can get row-1 headers inserted.
- Transform output typos can silently disappear.
- Writer ownership can be bypassed by direct transaction calls.

Expected fix:

- Align sheet creation/header placement with `header_row`.
- Make extra row keys fail by default, or require explicit `allow_extra`.
- Consider enforcing writer registry for mutating calls.
- Add tests for header-row creation and extra-key rejection.

### P1-10: Workflow Runner Can Mutate JSON Without Durable Event Trail

Status: active in current local tree.

Risk: workflow state and append-only events can diverge.

Evidence:

- `scripts/state/workflow_runner.py` swallows event emit failures in places.
- `pause(reason=...)` ignores reason.
- `approve(notes=...)` ignores notes.
- `retry()` deletes `ended_at`, losing previous terminal timing from current run
  JSON.

Expected fix:

- Preserve reason/notes in workflow JSON and event metadata.
- Make event emit failure policy explicit.
- If event emission is non-blocking, surface an AMBER warning and add recovery
  instructions.

### P1-11: Event `next_run_id()` Is Lockless

Status: active in current local tree.

Risk: concurrent writers can allocate the same integer run id.

Evidence:

- `scripts/state/events_writer.py` scans existing events and increments without
  a file lock.

Expected fix:

- Use a lock file around run id allocation and append.
- Or switch to UUID-only run ids if ordering is not required.
- Add a concurrency test with multiple processes.

### P1-12: Brand Onboarding Skill Is Active But Still Reads Like A Stub/Staging Skill

Status: active in current local tree.

Risk: a user may run an apparently active onboarding flow that relies on stubbed
discovery rather than real MCP/runtime calls.

Evidence:

- `skills/meta/brand-onboarding/SKILL.md` references project-config schema 1.2.
- It says staging-only/deferred in multiple places.
- It references old `projects/{slug}/config/` path.
- `scripts/meta/brand_onboarding_discovery.py` says MCP calls are stubbed.
- The same script hardcodes `2026 - founding_year`.

Expected fix:

- Either demote the skill status to staging/experimental or wire real discovery.
- Update schema version/path references.
- Replace hardcoded year with current UTC/local year.
- Add a preflight that clearly states which probes are real vs stubbed.

### P1-13: Generate Images Skill Depends On User-Level Higgsfield MCP Not In Plugin Registry

Status: active in current local tree.

Risk: production skill frontmatter requires Higgsfield tools while plugin
`.mcp.json` intentionally does not install that server.

Evidence:

- `skills/production/generate-images/SKILL.md` requires
  `mcp__higgsfield__generate_image`.
- It optionally uses `mcp__higgsfield__job_status`.
- Tests intentionally keep Higgsfield out of plugin `.mcp.json`.
- Registry currently does not represent the user-level dependency.

Expected fix:

- Add explicit “external/user MCP dependency” registry support, or mark the skill
  as unavailable unless Higgsfield exists in the user environment.
- Add preflight messaging and tests.

### P1-14: Command/Docs Reference Wrong Schema Paths

Status: active in current local tree.

Evidence:

- `commands/pseo-cannibalization.md` references
  `schemas/gsc-mapping.schema.json`; actual file is
  `schemas/gsc-tool-mapping.schema.json`.
- `commands/pseo-schema-audit.md` references
  `schemas/dataforseo-mapping.schema.json`; actual file is
  `schemas/dataforseo-endpoint-mapping.schema.json`.
- `commands/pseo-schema-audit.md` says `source.kind=sf_export`; event schema has
  `sf_csv` and `sf_mcp`, not `sf_export`.

Expected fix:

- Update paths and enum references.
- Add a docs/commands link checker for schema file references and enum tokens.

## P2 Findings

### P2-01: Workspace README/CLAUDE Docs Are Stale

Status: active in current local workspace.

Evidence:

- Workspace README says project config lives under `projects/<slug>/config/`.
  Actual tracked config is `projects/<slug>/project.config.json`.
- Workspace README quick start references `/quick-wins`,
  `/content-decay`, `/verify-indexing`; actual commands are prefixed:
  `/pseo-quickwin`, `/pseo-content-decay`, `/pseo-verify-indexing`.
- Workspace `CLAUDE.md` references MCP server set differently than current
  engine `.mcp.json`/Higgsfield policy.

Expected fix:

- Align workspace docs with current engine commands and layout.
- Add a docs test that command names in workspace docs exist in engine
  `commands/`.

### P2-02: Engine Docs Contain Stale Counts And Status Narratives

Status: active in current local tree.

Examples:

- Some active docs still reference 43 skills while current README says 45.
- `docs/GLOSSARY.md` says 28 CSR rules while registry has 31 declared rules.
- Marketplace/README/history text mixes 20 schemas, 20 rules, 21 schema-like
  JSON files, and 31 invariants.
- `docs/ARCHITECTURE.md` contains older phase/status roadmap language even
  though README presents v1.9.4 production-ready state.

Expected fix:

- Generate counts mechanically in a script or add a test that checks published
  counts.
- Keep historical release notes historical, but clearly mark active docs.

### P2-03: Template Placeholder Dialects Are Mixed Without A Contract

Status: active in current local tree.

Evidence:

- `scripts/reporting/render_template.py` uses Python `string.Template` `$var`.
- Content templates use `{{PLACEHOLDER}}`.
- Both live under `templates/`.

Risk:

- A template can be rendered with the wrong renderer and produce unresolved
  placeholders without failing.

Expected fix:

- Split report templates and content templates into explicit renderer families.
- Add a template manifest declaring placeholder dialect.
- Add tests that each template is rendered by exactly one supported renderer.

### P2-04: Requirements And Lock File Drift

Status: active.

Evidence:

- `requirements.txt` contains broad runtime deps.
- `requirements-lock.txt` is pinned for Python 3.14 and contains packages not in
  base requirements, including `requests`.
- Skills reference `requests` in snippets, but engine scripts mostly use stdlib
  or `httpx`.

Expected fix:

- Decide whether skill snippet dependencies belong in runtime requirements.
- Document lock generation command and Python version target.
- Add dependency drift check if lock is authoritative.

### P2-05: `project-config.schema.json` Version Metadata Is Stale/Ambiguous

Status: active.

Evidence:

- Engine README says v1.9.4.
- Project config schema has `schema_version` const 1.5.
- Some metadata/default fields still reference older core version patterns.

Expected fix:

- Clarify the distinction between engine version and config schema version.
- Add docs explaining migration policy.
- Ensure defaults do not imply stale engine compatibility.

### P2-06: Hook Helper Scripts Exist But Are Not Fully Wired As Runtime Hooks

Status: active/needs product decision.

Evidence:

- Scripts exist for append-only checks, naming checks, Excel write checks, and
  validate-before-write.
- Claude hook JSON currently wires only selected checks.

Expected fix:

- Decide which scripts are CI-only and which are runtime hooks.
- Document this explicitly.
- Add a test that the intended runtime hooks are present.

### P2-07: Secret Scan Policy Is Weaker Than “Zero Secrets On Disk” Language

Status: active/wording issue.

Evidence:

- `check_secrets.sh` ignores or warns for some ignored `.env` cases rather than
  failing all secrets on disk.
- This may be intentional to avoid blocking local env files, but the language
  says zero secrets.

Expected fix:

- Rename policy to “zero committed/changed secrets” if that is the intended
  behavior.
- Or make local ignored secrets fail too if truly zero-on-disk is required.

### P2-08: `portfolio.json` May Reference Projects Absent From Tracked GitHub State

Status: active in workspace.

Risk:

- Shared portfolio can list projects that exist only as untracked local folders.
- A clean clone of the workspace repo may not contain all active projects.

Expected fix:

- Decide whether project directories are tracked, generated, or private local
  state.
- Add a portfolio validation mode:
  - strict: every active project directory/config must exist and be tracked.
  - local: every active project directory/config must exist on disk.

## P3 Findings / Cleanup

### P3-01: Historical Docs Contain Old SF MCP Call Shapes

Status: cleanup.

Examples:

- `docs/WORKFLOWS.md`
- `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md`
- `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md`

Action:

- If historical, label as historical.
- If active, update to current SF MCP API.

### P3-02: Local Ignored `.DS_Store` Exists Under Templates

Status: local cleanup.

Evidence:

- `templates/.DS_Store` exists locally and is ignored, not tracked.

Risk:

- Not a Git issue, but packaging that copies from the filesystem instead of Git
  archive could include it.

Action:

- Remove locally or ensure packaging uses `git archive`/tracked files only.

### P3-03: Stale Product Counts In Comments

Status: cleanup.

Examples:

- CI/test comments mentioning 43 skills.
- README/marketplace wording around schema/rule counts.

Action:

- Replace hardcoded counts with generated checks or remove counts from prose.

## Suggested Test Backlog

Add these tests before or alongside fixes:

1. `test_ci_mcp_count_matches_mcp_json`
   - Parse `.mcp.json`.
   - Parse `.github/workflows/ci.yml`.
   - Assert the shell literal or generated command matches current count.

2. `test_command_allowed_tools_match_inline_shell`
   - Parse `commands/*.md`.
   - Extract `allowed-tools`.
   - Extract shell commands from `!` blocks.
   - Fail on missing `Bash(cmd:*)`.

3. `test_command_file_references_exist`
   - Scan command/docs active surfaces for `schemas/*.json` and
     `schemas/*.schema.json` references.
   - Fail if target file does not exist.

4. `test_cross_sheet_invariant_semantics_are_bound`
   - Add `implementation_key` or `check_type` to registry.
   - Assert each F-ID has one implementation and matching category.

5. `test_skill_mcp_tools_exist_in_registry`
   - Parse all skill frontmatter.
   - Apply explicit aliases.
   - Fail on missing required tools.
   - Warn/fail on missing optional tools depending policy.

6. `test_mcp_registry_versions_match_mcp_json`
   - Compare DataForSEO package version in `.mcp.json` to registry.

7. `test_validate_schema_enforces_format`
   - Validate a known bad URI/date-time and require failure.

8. `test_dump_workspace_reads_active_project`
   - Use `shared/active.json` with canonical `active_project`.

9. `test_events_schema_missing_event_kind_has_clean_error`
   - Prevent multi-branch conditional noise.

10. `test_pre_tool_use_hook_references_existing_commands`
    - Ensure hook messages do not mention nonexistent slash commands.

11. `test_post_tool_use_bash_write_classification`
    - Check Bash commands that modify/delete files are not logged as only
      `accessed`.

12. `test_excel_create_honors_header_row`
    - For a sheet with `header_row > 1`, ensure headers are not written to row 1.

13. `test_excel_rejects_extra_row_keys`
    - Catch typo keys in transform outputs.

14. `test_workspace_docs_command_names_exist`
    - Cross-check workspace README/CLAUDE command names against engine commands.

## Implementation Guidance For Claude Code

Work in small, reviewable batches. Do not mix workspace migration with engine
governance fixes in the same commit unless the human requests a single patch.

Recommended batch split:

1. Governance authority:
   - cross-sheet invariants
   - MCP registry/version/tool refs
   - tests for both

2. Workspace contract:
   - `dump_workspace.py`
   - dump tests
   - config/portfolio schema policy
   - optional migration script

3. Commands/hooks:
   - allowed-tools
   - stale command names
   - stale schema paths
   - SF crawl command contract
   - tests

4. Schema hardening:
   - `FormatChecker`
   - event conditionals
   - nested additionalProperties for high-risk schemas

5. State/write hardening:
   - Excel header/extra-key behavior
   - workflow/event emit policy
   - run id locking

6. Docs/templates cleanup:
   - counts
   - historical labels
   - template dialect manifest

Before editing, run:

```bash
git status --short
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 -m pytest --tb=short -q
```

After each batch, run at minimum:

```bash
python3 -m pytest --tb=short -q tests/ci tests/commands tests/hooks tests/schemas
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 scripts/state/dump_workspace.py --json
```

Do not assume workspace schema failures are harmless just because the engine test
suite is green. The current crosscheck proves those can diverge.
