# Ruthless Claude Code Handoff Audit

Date: 2026-06-05  
Reviewer: Codex  
Repo: `popiliadam/platinum-seo-engine`  
Mode: Read-only audit, then this handoff report was created at the user's request.

## Bottom Line

Score: **72 / 100** from a ruthless security, production-readiness, and governance-integrity perspective.

This repository has real engineering discipline: a large test suite, schema-first intent, drift checks, hooks, CI wrappers, and visible audit culture. The problem is that several trust boundaries are weaker than the documentation implies. The sharpest issues are shell execution surfaces, non-atomic config migrations, a too-narrow CI secret gate, governance docs claiming missing enforcement tests, and WIP production skills being marketed as production-ready.

Claude Code should treat this as a prioritized fix list, not as a request for broad refactoring. Fix P1 first, add/adjust tests for each behavior change, and keep patches small.

## Current Worktree Caveat

At final verification after this report was created, the worktree was dirty. The following pre-existing changes were not made by the auditor:

```text
 M .claude-plugin/marketplace.json
 M hooks/user-prompt-submit.json
 M scripts/hooks/README.md
 M tests/hooks/test_hook_scripts_runtime_vs_ci.py
 M tests/schemas/test_json_schema_draft_consistency.py
?? schemas/intent-marker.schema.json
?? scripts/hooks/intent_router.py
?? tests/hooks/test_intent_router.py
```

This report itself is newly added at `docs/audits/2026-06-05_ruthless_claude_code_handoff.md`. Before patching, Claude Code should re-run `git status --short --branch` and avoid reverting unrelated work.

## Verification Performed

- `python3 -m pytest --tb=short -q` passed earlier in the review with `1803 passed, 8 skipped`.
- `python3 -m compileall -q scripts tests conftest.py` passed.
- Full repository JSON parse scan found no invalid JSON.
- `bash scripts/security/check_secrets.sh .` returned GREEN, with only the documented warning class for local gitignored `.env`.
- `bandit`, `pip-audit`, `safety`, `semgrep`, and `shellcheck` were not available in PATH, so automated SAST/CVE/shell lint coverage was not performed.

## P1 Findings

### P1-01: MCP config executes `.env` as shell code

Evidence:

- `.mcp.json:7`
- `.mcp.json:14`
- `.mcp.json:18`

`gsc` and `dataforseo` run:

```bash
set -a; [ -f .env ] && source .env; set +a; exec npx -y ...
```

This does not merely parse environment variables. It executes `.env` as shell. If `.env` is malformed, poisoned, copied from an unsafe source, or modified by another local process, arbitrary shell code can run before MCP startup.

`ScraplingServer` also uses an environment-controlled executable:

```json
"command": "${SCRAPLING_BIN:-scrapling}"
```

Impact:

- Local command execution via poisoned `.env`.
- Trust boundary between secrets file and executable code is blurred.
- Runtime behavior depends on ambient shell state.

Recommended fix:

- Replace `source .env` with a safe dotenv parser or a small wrapper script that validates `KEY=VALUE` pairs and rejects shell syntax.
- Avoid shell `bash -c` where possible.
- Pin executable paths or validate `SCRAPLING_BIN` before use.
- Add tests covering `.env` lines containing shell metacharacters, comments, spaces, and invalid keys.

### P1-02: Project config migrations write live files non-atomically

Evidence:

- `scripts/migrations/0001_project_config_1.0_to_1.1.py:89-90`
- `scripts/migrations/0002_project_config_1.1_to_1.2.py:100-101`
- `scripts/migrations/0003_project_config_1.2_to_1.3.py:116-117`
- `scripts/migrations/migration_0004_project_config_1_3_to_1_4.py:143-144`
- `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py:136-137`

The migration scripts use `write_text()` directly for backup and output. This contradicts the repo's own stronger patterns elsewhere, such as tempfile + fsync + `os.replace()`.

Impact:

- Crash, disk interruption, or partial write can corrupt `project.config.json`.
- A failed migration can leave backup/output state inconsistent.
- This is a production data-integrity risk, not just style debt.

Recommended fix:

- Introduce a shared atomic JSON/text write helper.
- Use temp file in the same directory, flush + fsync, then `os.replace()`.
- fsync the containing directory after replace where supported.
- Add failure simulation tests if practical.

### P1-03: CI secret scanner is much weaker than the full scanner

Evidence:

- `scripts/ci/check_secrets.sh:9-19`
- `scripts/security/check_secrets.sh:31-34`
- `scripts/security/check_secrets.sh:145-163`

The CI wrapper uses a narrow hardcoded `git grep -nE` pattern:

```bash
DATAFORSEO_PASSWORD=...|info@adstark|3bf73e0893f69b42|ghp_...
```

The full scanner is stronger, but PreToolUse incremental mode intentionally skips structural checks for credential directories, `.env` files, key files, and chmod. Full scan being GREEN is useful, but the CI gate is not a comprehensive committed-secret defense.

Impact:

- Many real secret formats can bypass the CI wrapper.
- Incremental hook mode can miss structural secret risks.
- Documentation may create false confidence.

Recommended fix:

- Make CI call the same policy engine as `scripts/security/check_secrets.sh`, scoped to tracked files if needed.
- Expand patterns for modern token classes, private key headers, cloud credentials, OAuth tokens, and API key variants.
- Add tests proving CI and full scanner policies do not drift.

### P1-04: Governance rules claim enforcement tests that do not exist

Evidence:

- `rules/append-only-state.md:35` claims `tests/state/test_jsonl_append_only.py`; file not found.
- `rules/excel-discipline.md:37-38` claims `tests/excel/test_no_formulas.py` and `tests/excel/test_invariants.py`; `tests/excel/` not found.
- `rules/schema-first.md:35` claims `tests/schemas/test_all_schemas_exist.py`; file not found.
- `rules/time-discipline.md:59` claims `tests/schemas/test_time_format.py`; file not found.

Impact:

- The repo advertises stronger enforcement than it has.
- Reviewers and future agents may trust nonexistent CI coverage.
- This undermines the central "schema-locked / drift-checked" story.

Recommended fix:

- Either create the missing tests or update rule docs to point to the actual tests.
- Add a meta-test that all `rules/*.md` enforcement references resolve to real files.
- Treat stale enforcement references as CI failures.

## P2 Findings

### P2-01: Temporary hook diagnostic remains wired into production hooks

Evidence:

- `scripts/hooks/env_probe.py:4`
- `scripts/hooks/env_probe.py:72-79`
- `scripts/hooks/env_probe.py:105-108`
- `hooks/pre-tool-use.json:27`
- Similar hook wiring exists in other hook JSON files.

`env_probe.py` explicitly says it is temporary diagnostic instrumentation. It records `session_id`, `transcript_path`, cwd values, and selected env path values to `~/.config/pseo/hook-probe.jsonl`.

Impact:

- Operational metadata is persisted outside the repo.
- Transcript paths and session IDs are sensitive enough to deserve retention/permission policy.
- Temporary diagnostics become permanent attack surface and privacy debt.

Recommended fix:

- Remove the probe from production hooks after AMO validation, or gate it behind explicit opt-in.
- Set restrictive file permissions if retained.
- Add rotation or cleanup guidance.
- Add a CI check that "temporary diagnostic" hooks cannot ship enabled by default.

### P2-02: Hook command logic is hard to audit and bypass-prone

Evidence:

- `hooks/pre-tool-use.json:9`

The owner-lock check is a giant inline `python3 -c` string embedded in JSON. It parses shell commands with regex and tries to detect Excel master-file paths.

Impact:

- High maintenance burden.
- Easy to break with quoting/path edge cases.
- Security reviewers cannot easily reason about it.

Recommended fix:

- Move this logic into a real script under `scripts/hooks/`.
- Add tests with spaces, quotes, symlinks, relative paths, and multiple command forms.
- Keep hook JSON as a thin command wrapper.

### P2-03: Slash command shell surfaces are fragile

Evidence:

- `commands/pseo-status.md:21`
- `commands/pseo-status.md:29`
- `commands/pseo-status.md:83`
- `commands/pseo-bind.md:27`
- `commands/pseo-sf-status.md:31`
- `commands/pseo-sf-status.md:37`

Examples:

- Hardcoded fallback search under `/Users/apple/.claude/plugins/cache`.
- `WF_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/workflows"` is built from active marker / argument input.
- `python3 -m scripts.state.session_binding bind "$1" $2 $3` leaves `$2` and `$3` unquoted.
- `for SLUG in $PROJECTS` uses word splitting/globbing.

Impact:

- Portability failure outside the original machine/user.
- Wrong or malicious plugin cache selection if env vars are missing.
- Argument splitting and path corruption.
- Low-grade local trust-boundary risk.

Recommended fix:

- Route commands through typed Python CLIs where possible.
- Validate slugs before constructing paths.
- Quote all shell arguments or avoid shell entirely.
- Remove user-specific absolute path fallbacks.

### P2-04: Production-ready claim is inflated by WIP skills

Evidence:

- `README.md:8`
- `skills/production/new-blog/SKILL.md:22`
- `skills/production/new-blog/SKILL.md:244-245`
- `skills/production/faq-optimization/SKILL.md:29`
- `skills/production/faq-optimization/SKILL.md:233-234`
- `skills/production/revise-content/SKILL.md:216-217`

Inventory found 45 skills: 37 active, 8 wip.

WIP skills:

- `skills/meta/mark-done/SKILL.md`
- `skills/production/content-remediation/SKILL.md`
- `skills/production/faq-optimization/SKILL.md`
- `skills/production/generate-images/SKILL.md`
- `skills/production/new-blog/SKILL.md`
- `skills/production/revise-content/SKILL.md`
- `skills/publishing/indexing-ping/SKILL.md`
- `skills/publishing/verify-indexing/SKILL.md`

Some production skills explicitly say runtime integration is deferred and referenced scripts do not exist.

Impact:

- Users may rely on workflows that are specs, not runnable implementations.
- README and marketplace claims can overstate maturity.
- "Production-ready" becomes a marketing label rather than a tested status.

Recommended fix:

- Separate "active runtime skills" from "spec-locked WIP skills" in README and marketplace metadata.
- Make WIP status visible in command routing.
- Add tests ensuring no WIP skill is advertised as production-ready.

### P2-05: Supply-chain hardening is incomplete

Evidence:

- `requirements.txt:1-7`
- `requirements-lock.txt:15-20`
- `.mcp.json:7`
- `.mcp.json:14`

Direct Python dependencies are broad lower-bound ranges in `requirements.txt`. The lock file intentionally leaves deeper transitive dependencies unpinned for Python 3.10 compatibility. MCP servers are launched through `npx -y`, which can fetch and execute package code at runtime.

Impact:

- Dependency resolution can drift across machines.
- Runtime package execution increases supply-chain exposure.
- No available `pip-audit` run was performed in this review.

Recommended fix:

- Add dependency audit tooling to CI.
- Decide whether Python 3.10 compatibility is worth partial unpinning.
- Consider vendored or preinstalled MCP server versions instead of runtime `npx -y`.
- Document exact supply-chain assumptions.

### P2-06: `run_skill_python.py` gives green exit for prompt-only skills

Evidence:

- `scripts/ci/run_skill_python.py:48-62`

The helper returns 0 when no Python blocks exist:

```text
AMBER: No Python blocks ... exit 0
```

Impact:

- CI can pass a skill with no executable verification.
- "Green" can mean "nothing actually ran."

Recommended fix:

- Distinguish PASS from AMBER at the CI aggregation layer.
- Require explicit allowlist for prompt-only skills.
- Fail if a skill claims runtime behavior but has no testable artifact.

## P3 Findings

### P3-01: README inventory counts are stale

Evidence:

- `README.md:8`
- `README.md:53`
- `README.md:243`

Observed inventory:

- 45 skills
- 19 commands
- 6 hooks
- 4 MCP servers
- 23 schema JSON files, 22 of which are `*.schema.json`

README says 18 commands and 21 schemas in places.

Impact:

- Documentation drift.
- Weakens confidence in self-auditing claims.

Recommended fix:

- Generate inventory counts from filesystem in CI.
- Fail docs tests when README/marketplace/plugin metadata disagree.

### P3-02: Local generated artifacts clutter the workspace

Observed:

- `.coverage` exists.
- `.DS_Store` exists.
- `.pytest_cache` exists.
- `37` `__pycache__` directories.
- `691` `.pyc` files.

These appear to be local/ignored artifacts, not necessarily committed leaks.

Impact:

- Noise during full-tree scans.
- Easier to misread repo cleanliness.

Recommended fix:

- Confirm `.gitignore` coverage.
- Add cleanup guidance or a `make clean` / script target.

## Suggested Fix Order

1. Fix `.mcp.json` shell execution of `.env`.
2. Replace non-atomic migration writes with a shared atomic write helper.
3. Unify CI and full secret scanning policy.
4. Make rule enforcement references machine-checkable and fix missing tests/docs.
5. Remove or gate temporary hook diagnostics.
6. Move inline hook Python into real scripts with tests.
7. Harden slash command shell snippets or move them into typed CLIs.
8. Correct README/marketplace production-readiness and inventory claims.
9. Add dependency audit tooling and document supply-chain assumptions.
10. Add workspace cleanup hygiene.

## Handoff Prompt For Claude Code

Use this prompt if handing the work to Claude Code:

```text
Read docs/audits/2026-06-05_ruthless_claude_code_handoff.md fully.
Do not rewrite the project broadly. First run git status and preserve unrelated user changes.
Start with P1-01 through P1-04 only. For each fix, make the smallest safe patch, add or update focused tests, and run the relevant test subset.
Do not change public behavior unless required to close the finding. After P1 fixes are green, summarize remaining P2/P3 work.
```
