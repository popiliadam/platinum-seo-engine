# Platinum SEO Engine — Hostile Repo Audit Handoff for Claude Code

Date: 2026-06-09
Auditor: Codex
Scope: repo-wide hostile audit focused on SEO plugin behavior, skill/script/command wiring, documentation truthfulness, and operational gaps.
Rule for Claude Code: fix only after re-verifying each evidence link locally. Do not paper over contradictions by changing marketing text alone if the underlying runtime is still missing.

## Verification Snapshot

- Local repo: `/Users/apple/Documents/platinum-seo-engine`
- Current HEAD observed during audit: `35c2e164e80da7a9a79f06b08567eecca54667ab`
- Git status observed: `main...origin/main [ahead 6]`
- Existing untracked file before this handoff: `docs/audits/2026-06-09_hostile_audit_claude_code_prompt.md`
- Counts observed:
  - `find skills -name SKILL.md | wc -l` -> `45`
  - `find commands -name '*.md' | wc -l` -> `25`
  - `find schemas -name '*.json' | wc -l` -> `27`
- Full test suite observed: `2481 passed, 7 skipped`

Important implication: the test suite is green while multiple user-facing contracts are stale or self-contradictory. Fixes need new regression coverage, not just text edits.

## Priority Map

Fix order:

1. P0 truthfulness and executable-path contradictions: Findings 1-6.
2. P1 coverage, command lint, stale counts, release automation: Findings 7-12.
3. Run full suite and targeted count/command/SF/indexing tests.

## Finding 1 — README / manifest / docs disagree on version, command count, schema count

Severity: P0
Area: release truthfulness, marketplace trust, install expectations

Evidence:

- `README.md:8` says `v2.0.0` but `24 commands`.
- Actual command count is 25.
- `.claude-plugin/plugin.json:3-4` says version `2.0.0` and `25 slash command`.
- `.claude-plugin/marketplace.json:16` says `45 skills, 27 schemas, 20 rules, 25 commands`.
- `README.md:53` still says `18 slash commands`.
- `README.md:130-134` architecture box says `18 slash cmds` and `21 JSON Schemas`.
- `README.md:243` says JSON Schema count is `21`.
- `README.md:251` says current release is `v1.9.5`.
- `README.md:273` links latest release to `RELEASE_NOTES_v1.9.5.md`.
- `docs/INSTALL.md:3` says v2.0.0 but `24 slash commands`.
- `docs/ARCHITECTURE.md:71` says engine v1.9.4.
- `docs/ARCHITECTURE.md:81-88` still cites 18 commands, 21 schemas, 31/24 CSR.
- `docs/REFERENCE_INDEX.md:35` says `45 skills, 18 commands`.

Risk:

The plugin advertises v2.0.0 production readiness, but the human-facing docs, install docs, architecture, and marketplace cannot agree on the shipped surface. This breaks operator trust and makes future audits noisy because there is no single source of truth for release facts.

Required fix:

- Introduce one canonical repo capability manifest or test helper that derives:
  - skill count
  - command count
  - schema count
  - hook count
  - MCP server count
  - current release version
- Update README, INSTALL, ARCHITECTURE, REFERENCE_INDEX, WORKFLOWS, release links to use the real v2.0.0 facts.
- Decide whether docs should say 27 all-schema JSONs or a narrower schema subset; then encode that definition consistently.

Acceptance criteria:

- A single test fails if README/INSTALL/ARCHITECTURE/REFERENCE_INDEX cite stale command or schema counts.
- README no longer says both v2.0.0 and v1.9.5.
- Latest release link points to `docs/RELEASE_NOTES_v2.0.0.md`.

## Finding 2 — Production suite is marketed as done/active while all production skills are WIP/spec-only

Severity: P0
Area: SEO content production, operator expectation, runtime availability

Evidence:

- `README.md:268` marks Phase 11 Production Suite as `done`.
- `docs/WORKFLOWS.md:86-94` marks production skills active:
  - `new-blog`
  - `revise-content`
  - `generate-images`
  - `content-remediation`
  - `faq-optimization`
- Actual frontmatter says WIP:
  - `skills/production/new-blog/SKILL.md:21-22`
  - `skills/production/revise-content/SKILL.md:25-26`
  - `skills/production/faq-optimization/SKILL.md:28-29`
  - `skills/production/content-remediation/SKILL.md:26-27`
  - `skills/production/generate-images/SKILL.md:35-36`
- Runtime files are explicitly absent:
  - `skills/production/new-blog/SKILL.md:244-246` says `scripts/production/new_blog.py` does not exist.
  - `skills/production/revise-content/SKILL.md:216-218` says `scripts/production/revise_content.py` does not exist.
  - `skills/production/faq-optimization/SKILL.md:233-235` says `scripts/production/faq_optimization.py` does not exist.
- `find scripts -maxdepth 2 -type d -name production -print` returned no production script directory.

Risk:

This is the largest product truth gap. The repo sells an end-to-end SEO production system, but the production layer is mostly skill spec text, not runtime implementation. Operators may trust draft/revise/remediation/indexing flows that cannot actually execute as advertised.

Required fix:

Choose one:

1. Implement production runtime and promote statuses to active only after tests and live smoke proof.
2. Keep them WIP and demote all docs/commands/roadmaps that call them active/done.

Do not simply change the WIP frontmatter to active unless the missing runtime exists.

Acceptance criteria:

- Production skills, workflow catalog, README phase table, slash commands, and marketplace all agree on status.
- If production is active, each production skill has executable runtime or an explicitly supported orchestration path, with tests.
- If production remains WIP, docs must not say Phase 11 is done.

## Finding 3 — `/pseo-new-blog` command contradicts the `new-blog` skill contract

Severity: P0
Area: content generation, master.xlsx writes, output artifacts

Evidence:

- `commands/pseo-new-blog.md:13` calls `new-blog` active.
- `skills/production/new-blog/SKILL.md:21-22` says `status: wip`.
- Command says outputs are `article.{md,html,jsonld}`:
  - `commands/pseo-new-blog.md:30`
- Skill outputs are:
  - `outputs/blog/{slug}/article.html`
  - `outputs/blog/{slug}/schema.jsonld`
  - `outputs/blog/{slug}/meta-tags.json`
  - `outputs/blog/{slug}/upload-instructions.md`
  - `skills/production/new-blog/SKILL.md:89-98`
- Command says `--mode publish` updates `master.xlsx[new_content_plan].lifecycle_status PLANNED -> DONE`:
  - `commands/pseo-new-blog.md:38`
- Skill says it is read-only against `master.xlsx` and never calls transaction append/update/delete:
  - `skills/production/new-blog/SKILL.md:101-105`
- Skill says runtime script does not exist:
  - `skills/production/new-blog/SKILL.md:244-246`

Risk:

The operator sees a command with a publish mode and lifecycle transition, but the skill says no workbook write and no runtime. That can lead to broken content state: generated artifacts may exist without lifecycle state, or a command may promise publish semantics that are impossible.

Required fix:

- Decide the canonical `new-blog` behavior:
  - draft-only artifact generator, or
  - publish-mode state transition owner.
- Align command, skill frontmatter, body, output names, events schema usage, and tests.
- If publishing state is moved to `mark-done`, remove lifecycle update promises from `/pseo-new-blog`.

Acceptance criteria:

- A command/skill contract test compares command-documented outputs and write claims against skill frontmatter/body.
- `new-blog` cannot simultaneously claim read-only and publish lifecycle mutation.

## Finding 4 — Google Indexing API wording is misleading; current implementation is sitemap submit, not per-URL submit

Severity: P0
Area: SEO indexing, operator expectation, event semantics

Evidence:

- `README.md:48` says Publishing includes `Indexing ping (URL Indexing API)`.
- `docs/WORKFLOWS.md:100-105` marks `indexing-ping` and `verify-indexing` active.
- `skills/publishing/indexing-ping/SKILL.md:21-22` says `status: wip`.
- `skills/publishing/indexing-ping/SKILL.md:32` says `google_indexing_api` is currently `mcp__gsc__submit_sitemap`, not per-URL.
- `skills/publishing/indexing-ping/SKILL.md:75-81` repeats that only sitemap submission is wired and per-URL Google Indexing API `URL_UPDATED` is not wired.
- `skills/publishing/indexing-ping/SKILL.md:262-272` Step 5 calls sitemap submit and says `URL_UPDATED` is deferred.
- `skills/publishing/indexing-ping/SKILL.md:304` still documents `indexing_ping.call_type=URL_UPDATED`.
- `skills/publishing/verify-indexing/SKILL.md:20-21` is WIP.
- `skills/publishing/verify-indexing/SKILL.md:500-502` says active bump is deferred.

Risk:

The user-facing name implies per-URL Google Indexing API submission, but actual Google-side path is sitemap submission. This is a material SEO expectation mismatch and can produce false confidence in indexing workflows.

Required fix:

Choose one:

1. Implement consent-gated per-URL Google Indexing API and use `URL_UPDATED` only for that path.
2. Rename the current path everywhere to `sitemap submission`, and reserve `google_indexing_api` / `URL_UPDATED` for future work.

Acceptance criteria:

- No doc or event uses `URL_UPDATED` unless the per-URL Indexing API is actually wired.
- `indexing-ping` and `verify-indexing` statuses match workflow catalog and README.
- Tests validate that `submission_type=google_indexing_api` does not silently mean sitemap submit unless that name is intentionally changed.

## Finding 5 — SF MCP command preflight uses obsolete bare HTTP endpoints that contradict the canonical client and tests

Severity: P0
Area: Screaming Frog MCP, crawl ingestion, command executability

Evidence:

- Canonical client says SF MCP is Streamable HTTP, stateful/session-based, not bare JSON-RPC:
  - `scripts/util/sf_mcp_client.py:8-17`
- It requires:
  - `Accept: application/json, text/event-stream`
  - `Content-Type: application/json`
  - `Mcp-Session-Id`
  - `scripts/util/sf_mcp_client.py:12-17`
- `health()` explicitly says there is no `/health` route and performs initialize handshake:
  - `scripts/util/sf_mcp_client.py:258-287`
- Tests say old bare JSON-RPC assumptions shipped broken with green tests:
  - `tests/scripts/test_sf_mcp_client.py:3-8`
- README still verifies with `/mcp/tools`:
  - `README.md:176`
- INSTALL still verifies with `/mcp/tools`:
  - `docs/INSTALL.md:112`
- `/pseo-sf-crawl` preflight still curls `/mcp/tools`:
  - `commands/pseo-sf-crawl.md:26`
- `/pseo-sf-status` curls `/mcp/tools` and does bare `tools/call` POST without session:
  - `commands/pseo-sf-status.md:17`
  - `commands/pseo-sf-status.md:29`
- `/pseo-status` has the same bare POST pattern:
  - `commands/pseo-status.md:77-79`

Risk:

Operators following README/INSTALL or using `/pseo-sf-status` may get false DOWN/MCP_CALL_FAILED even when SF MCP is healthy, or commands may fail against the real server. This directly breaks the SF MCP primary ingestion path.

Required fix:

- Replace bare curl probes with a small CLI wrapper around `scripts/util/sf_mcp_client.py`, or provide a documented `python3 -m scripts.util.sf_mcp_client ...` probe.
- Update README, INSTALL, `/pseo-sf-crawl`, `/pseo-sf-status`, `/pseo-status`.
- Keep one canonical SF health command that performs initialize -> initialized -> tools/call.

Acceptance criteria:

- No repo docs or commands mention `/mcp/tools` unless SF actually exposes it and tests cover it.
- A test greps commands/docs for obsolete SF MCP curl patterns.
- `/pseo-sf-status` can list `sf_list_allowed_base_directory` through the canonical client.

## Finding 6 — SF orchestrator live execution path is split between SKILL body wrappers and unused `sf_mcp_client`

Severity: P0
Area: Screaming Frog orchestration, MCP runtime ownership

Evidence:

- `scripts/ingestion/sf_crawl_orchestrator.py:1-6` says the script contains only pure transform helpers and MCP calls happen in the SKILL body via `mcp__sf__sf_*` wrappers.
- `skills/ingestion/sf-crawl-orchestrator/SKILL.md:702-704` says `scripts/util/sf_mcp_client.py` is not used here.
- `/pseo-sf-crawl` allowed-tools only includes `jq`, `curl`, `head`, `Read`:
  - `commands/pseo-sf-crawl.md:7`
- But the same command lists required MCP tools:
  - `commands/pseo-sf-crawl.md:66`
- The skill preflight uses `mcp__sf__sf_list_allowed_base_directory` and `mcp__sf__sf_list_crawls` in prose/body:
  - `skills/ingestion/sf-crawl-orchestrator/SKILL.md:203`
  - `skills/ingestion/sf-crawl-orchestrator/SKILL.md:229`

Risk:

The codebase has a robust SF MCP client, but the orchestrator that matters says it does not use it. Slash command preflight uses stale curl. This leaves actual crawl execution dependent on Claude tool wrapper availability and prompt-body behavior, not a tested runtime path.

Required fix:

Choose one canonical runtime:

1. Move SF orchestration into a Python runtime that uses `SfMcpClient`.
2. Keep Claude MCP wrappers but remove/limit stale command curl and add tests proving allowed tools and wrapper invocations are valid in Claude Code.

Acceptance criteria:

- There is exactly one documented SF MCP transport path for preflight/status/crawl.
- Command allowed-tools and skill MCP requirements are reconciled.
- Live smoke test or skipif test exercises the same path the slash command uses.

## Finding 7 — Repo's own coverage report proves many SEO-critical skills are not orchestrated

Severity: P1
Area: workflow wiring, automation completeness, SEO operations

Evidence:

Command run:

```bash
python3 -m scripts.reporting.capability_coverage
```

Observed output:

- 45 skills total
- 13 orchestrated
- 9 commanded
- 23 ad-hoc-only
- 48 MCP tools registered
- 7 orchestrated
- 38 declared-only
- 3 unused

Ad-hoc-only included SEO-critical skills:

- `content-remediation`
- `indexing-ping`
- `verify-indexing`
- `mark-done`
- `revise-content`
- `sf-import`
- `internal-links`
- `content-gaps`
- multiple portfolio reporting skills

Relevant command doc:

- `commands/pseo-coverage.md:24-30` defines these categories.
- `commands/pseo-coverage.md:52-59` tells operators ad-hoc-only skills are not dead, but not routed/denetçi-controlled.

Risk:

The system presents an autonomous SEO engine, but many critical SEO actions are outside orchestration and coverage/denetçi enforcement. This can cause skipped steps, unverified outputs, and manual drift.

Required fix:

- Decide which ad-hoc-only skills are acceptable as ad-hoc.
- Promote critical state-changing or SEO-impacting skills into workflows/routes:
  - `content-remediation`
  - `indexing-ping`
  - `verify-indexing`
  - `mark-done`
  - `sf-import`
  - `revise-content`
- Update coverage acceptance thresholds or explicitly document why a skill remains ad-hoc.

Acceptance criteria:

- Coverage report no longer lists critical publish/remediation/done steps as ad-hoc-only unless explicitly accepted.
- CI has a whitelist for allowed ad-hoc-only skills.

## Finding 8 — Slash command allowed-tools tests only shell binaries, not MCP tools mentioned in command bodies

Severity: P1
Area: command permissions, Claude Code execution reliability

Evidence:

- Test only checks shell programs:
  - `tests/commands/test_allowed_tools_match_shell.py:139-154`
- `/pseo-gsc-pull` allowed-tools: only `Bash(jq:*)`, `Read`
  - `commands/pseo-gsc-pull.md:7`
- Same command requires GSC MCP:
  - `commands/pseo-gsc-pull.md:40-41`
- `/pseo-quickwin` allowed-tools: only `Bash(jq:*)`, `Read`
  - `commands/pseo-quickwin.md:7`
- Same command lists multiple GSC MCP tools:
  - `commands/pseo-quickwin.md:46-49`
- `/pseo-dfs-pull` allowed-tools: only `Bash(jq:*)`, `Read`
  - `commands/pseo-dfs-pull.md:7`
- Same command lists DataForSEO MCP:
  - `commands/pseo-dfs-pull.md:44-45`
- `/pseo-new-blog` allowed-tools: `jq`, `python3`, `Read`
  - `commands/pseo-new-blog.md:7`
- Same command lists Higgsfield/GSC/DataForSEO MCP:
  - `commands/pseo-new-blog.md:50`
- `/pseo-schema-audit` documents optional SF MCP live call:
  - `commands/pseo-schema-audit.md:37`

Risk:

Commands may pass tests while failing or being blocked in Claude Code because the command frontmatter does not reflect the MCP tools the body expects. The current lint gives a false sense of command safety.

Required fix:

- Add a parser/lint that extracts `mcp__...` references from command bodies.
- Decide whether command `allowed-tools` must include MCP tools or whether commands are only explanatory wrappers that rely on skill routing.
- Enforce that policy consistently.

Acceptance criteria:

- A regression test fails when a command references an MCP tool not allowed/declared by policy.
- All command MCP references are either allowed, removed, or explicitly marked as skill-level-only.

## Finding 9 — `monitoring-weekly` is active but its advertised GSC anomaly and budget burn features are placeholders

Severity: P1
Area: monitoring, anomaly detection, budget governance

Evidence:

- `/pseo-monitoring-weekly` command says it aggregates GSC delta and budget burn:
  - `commands/pseo-monitoring-weekly.md:4`
  - `commands/pseo-monitoring-weekly.md:13`
  - `commands/pseo-monitoring-weekly.md:23-25`
- Skill frontmatter says active:
  - `skills/reporting/monitoring-weekly/SKILL.md:30-31`
- Skill body admits actual runtime reads only drift-check output and portfolio snapshot:
  - `skills/reporting/monitoring-weekly/SKILL.md:75-80`
- Skill says GSC week-over-week delta and budget burn are Phase 14+ placeholders:
  - `skills/reporting/monitoring-weekly/SKILL.md:82-91`
  - `skills/reporting/monitoring-weekly/SKILL.md:175-180`
  - `skills/reporting/monitoring-weekly/SKILL.md:197-202`
  - `skills/reporting/monitoring-weekly/SKILL.md:214-236`

Risk:

Weekly monitoring may tell the operator there is a health/budget/anomaly layer while not computing the core signals. This is especially risky because weekly monitoring is likely trusted as a "quiet safety net".

Required fix:

Choose one:

1. Implement real GSC anomaly and budget burn.
2. Rename command/docs to "weekly drift + portfolio snapshot" and mark anomaly/budget as deferred.

Acceptance criteria:

- Command summary matches actual runtime inputs.
- If active, report output includes computed GSC and budget numbers backed by fixtures/tests.
- If placeholder, output labels it clearly and docs do not call it computed.

## Finding 10 — SF `allowed_directory` default and F-15 isolation guard are inconsistent

Severity: P1
Area: SF export safety, workspace isolation

Evidence:

- Actual bootstrap default:
  - `scripts/state/bootstrap_project.py:54-62` -> `allowed_directory: None`
- Actual migration default:
  - `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py:55-66` -> `allowed_directory: None`
- Schema default:
  - `schemas/project-config.schema.json:111-114` -> type string/null, default null, "Null = use SF GUI default"
- `/pseo-init` says default is `/Users/apple/seo_spider_mcp_server`:
  - `commands/pseo-init.md:45`
- README/INSTALL recommend that concrete path:
  - `README.md:185`
  - `docs/INSTALL.md:105`
- WORKFLOWS says migration populates that path:
  - `docs/WORKFLOWS.md:200`
- Orchestrator only checks mismatch if expected path is truthy:
  - `skills/ingestion/sf-crawl-orchestrator/SKILL.md:218-227`

Risk:

If default is null, SF GUI default is trusted and F-15 path isolation is not enforced unless operator sets the path. If docs imply a hard default, operators may assume isolation is active when it is not.

Required fix:

Decide canonical behavior:

1. Hard default path: set migration/bootstrap/schema default to `/Users/apple/seo_spider_mcp_server` or a portable configured path, then enforce mismatch.
2. Null default: update docs to say isolation guard is opt-in until configured, and warn clearly.

Acceptance criteria:

- Bootstrap, migration, schema, `/pseo-init`, README, INSTALL, WORKFLOWS all agree.
- F-15 drift-check distinguishes "unset, not enforceable" from "configured and mismatch".

## Finding 11 — Drift-check command has stale invariant counts

Severity: P1
Area: governance trust, self-audit accuracy

Evidence:

- `/pseo-driftcheck` says 28 invariant rules:
  - `commands/pseo-driftcheck.md:4`
  - `commands/pseo-driftcheck.md:14`
  - `commands/pseo-driftcheck.md:25`
- Test ground truth asserts:
  - declared CSR count is 32:
    - `tests/docs/test_count_consistency.py:104-109`
  - implemented invariant count is 25:
    - `tests/docs/test_count_consistency.py:112-119`
- `docs/GLOSSARY.md:13` also says 32 CSR rule current.

Risk:

The command meant to detect drift is itself drifted. This undermines confidence in governance output and can hide missed invariant implementation gaps.

Required fix:

- Update `/pseo-driftcheck` command text to derive or cite current declared/implemented counts.
- Add the command file to count consistency tests.

Acceptance criteria:

- No hardcoded stale `28` remains in drift-check command unless it refers to historical context.
- Tests fail when drift-check command count differs from actual registry.

## Finding 12 — Release notes and version bump tests preserve stale release metadata

Severity: P1
Area: release process, future drift prevention

Evidence:

- `docs/RELEASE_NOTES_v2.0.0.md:6` says `2312 PASS / 7 SKIP`.
- Full suite observed during audit: `2481 passed, 7 skipped`.
- `docs/RELEASE_NOTES_v2.0.0.md:85` says slash-command count -> 24, actual 25.
- `docs/RELEASE_NOTES_v2.0.0.md:89` repeats `2312 PASS / 7 SKIP`.
- `scripts/release/version_bump.py:80-112` updates marketplace version/prefix but preserves description body.
- `scripts/release/version_bump.py:116-137` updates README status banner only.
- `tests/scripts/test_version_bump.py:212-227` asserts marketplace prefix update and body preservation.
- `tests/scripts/test_version_bump.py:233` starts README banner-only test.

Risk:

The release tooling can bump semver while leaving stale counts, stale test totals, stale release links, and stale "current version" prose intact. This is how the v2/v1.9.5 contradiction survived.

Required fix:

- Extend release tooling or add a release consistency test that checks:
  - README current version
  - latest release link
  - INSTALL banner
  - release notes test count if stated
  - command/schema/skill counts in release notes
  - marketplace/plugin manifest count agreement
- Stop preserving stale marketplace description body if it includes machine-checkable counts.

Acceptance criteria:

- Running version bump cannot produce a repo where README says v2.0.0 and Current says v1.9.5.
- Count-bearing prose is either generated or linted.

## Cross-Cutting Test Gaps To Add

Add these tests after fixes:

1. `test_public_docs_counts_match_filesystem`
   - README, INSTALL, ARCHITECTURE, REFERENCE_INDEX, WORKFLOWS.

2. `test_command_mcp_references_match_policy`
   - Extract `mcp__...` from `commands/*.md`.
   - Enforce allow/declare policy.

3. `test_no_obsolete_sf_mcp_bare_curl`
   - Fail on `/mcp/tools`.
   - Fail on `tools/call` POST in docs/commands unless going through canonical session client.

4. `test_skill_status_catalog_consistency`
   - Compare `status:` frontmatter against WORKFLOWS/README status tables.
   - WIP skills cannot be advertised as active/done without an explicit exception.

5. `test_indexing_semantics`
   - If path is sitemap submit, event/report call_type must not say `URL_UPDATED`.
   - If path is per-URL Google Indexing API, require implementation proof.

6. `test_release_notes_machine_facts`
   - Check command/schema counts and test totals where stated.

## Suggested Claude Code Work Plan

1. Build a small fact collector script/test helper:
   - counts files
   - parses plugin/marketplace
   - parses skill frontmatter statuses
   - extracts command MCP refs

2. Fix public truth first:
   - README/INSTALL/ARCHITECTURE/REFERENCE_INDEX/WORKFLOWS/release notes.

3. Fix SF MCP:
   - replace stale curls with canonical client wrapper.
   - add regression grep.

4. Fix production/publishing status:
   - either implement runtime or demote to WIP honestly.
   - align `/pseo-new-blog` and indexing semantics.

5. Fix coverage/orchestration:
   - whitelist acceptable ad-hoc-only skills.
   - route critical SEO state-changing skills.

6. Run:

```bash
pytest
python3 -m scripts.reporting.capability_coverage
```

Expected end state: no self-contradictory release facts, no active/done label on WIP runtime, no obsolete SF MCP command path, and no false `URL_UPDATED` indexing claim unless per-URL API is truly wired.
