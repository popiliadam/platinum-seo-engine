# Phase 3 — Commands & Hook UX — Worker Brief

## 0. READ FIRST (worker onboarding)

- Fresh worker session. Engine repo: `/Users/apple/Documents/platinum-seo-engine`. ENGINE-ONLY (no workspace writes).
- Invoke `superpowers:test-driven-development` + `superpowers:verification-before-completion`.
- **Branch:** `git checkout -b fix/codex-audit-phase-3-commands` off `main` (Phases 1+2 are merged;
  confirm `git log --oneline -3` shows merge commit `bc0ced8`). Never commit to main, never push.
- Hard rules: NO subagents (Task/Agent fail here — "Prompt is too long"); atomic commits; never commit
  `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`; preserve unrelated/untracked files (the `docs/superpowers/plans/`
  planning docs are untracked — leave them).
- **Baseline:** `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`
  must stay ≥ **1463 passed, 8 skipped** + your new tests.

## 1. GOAL + findings this phase closes

**Goal:** Make every slash command + hook message executable and accurate — declared tools match real
shell usage, documented script/MCP contracts match reality, schema/enum references resolve, and inline
shell→Python arg passing is injection-safe — each locked by a test so the drift can't return.

- **P0-05** — 7 commands use shell programs not declared in their `allowed-tools` frontmatter.
- **P0-06** — `pseo-sf-crawl.md` documents an invalid runtime contract (`sf_import.py --source-run-id`
  which makes argparse exit 2; `save_report=True`; incomplete SF MCP tool list).
- **P1-05** — `hooks/session-start.json` + `hooks/user-prompt-submit.json` tell users to run
  `/pseo-bootstrap-project`, which does not exist (real command: `/pseo-init`).
- **P1-08** — `pseo-active.md` + `pseo-status.md` interpolate a shell var into Python source
  (`slug = '$SLUG'`) — breaks/injects on a quote; slug is unvalidated.
- **P1-14** — wrong schema-file references + an invalid event enum token in two commands.

## 2. EVIDENCE (verified)

- **P0-05 undeclared shell programs** (verified by an allowed-tools-vs-usage analyzer; ignore jq/python
  internal tokens — only real shell programs count):
  | command | uses but not in allowed-tools |
  |---|---|
  | `commands/pseo-active.md` | `mkdir` |
  | `commands/pseo-gbp-audit.md` | `grep` |
  | `commands/pseo-init.md` | `head` |
  | `commands/pseo-schema-audit.md` | `head`, `sort` |
  | `commands/pseo-sf-crawl.md` | `curl`, `head` |
  | `commands/pseo-sf-status.md` | `grep`, `head`, `sort`, `tail`, `xargs` |
  | `commands/pseo-status.md` | `curl`, `find`, `grep`, `sort`, `tail`, `xargs` |
  (`pseo-active.md` frontmatter currently: `allowed-tools: Bash(python3:*), Bash(jq:*), Bash(ls:*), Read`.)
- **P0-06** `commands/pseo-sf-crawl.md`: line ~38 says `save_report=True`; line ~41 invokes
  `sf_import.py --project {slug} --sf-export-path {...} --source-run-id {run_id}`. But
  `scripts/ingestion/sf_import.py` argparse accepts ONLY `--project`, `--sf-export-path`,
  `--workspace-root`, `--dry-run` (line ~268). `skills/ingestion/sf-crawl-orchestrator/SKILL.md:468`
  itself warns `--source-run-id` "makes argparse exit 2". Command's MCP list (line ~66) names 5 SF
  tools; the skill also uses `sf_generate_bulk_export` + `sf_export_seo_element_urls`.
- **P1-05** `hooks/session-start.json:9` + `hooks/user-prompt-submit.json:9` contain the literal
  `/pseo-bootstrap-project`. There is no `commands/pseo-bootstrap-project.md` (real scaffold = `/pseo-init`).
- **P1-08** `commands/pseo-active.md` (~lines 25–44) builds `python3 -c "...slug = '$SLUG'..."` — shell
  `$SLUG` interpolated into Python source. `commands/pseo-status.md` embeds the project similarly.
- **P1-14** `commands/pseo-cannibalization.md:46` references `schemas/gsc-mapping.schema.json` (real:
  `schemas/gsc-tool-mapping.schema.json`). `commands/pseo-schema-audit.md:48` references
  `schemas/dataforseo-mapping.schema.json` (real: `schemas/dataforseo-endpoint-mapping.schema.json`).
  `commands/pseo-schema-audit.md:28` uses `source.kind=sf_export` — NOT in the events enum
  (`schemas/events.schema.json`: `["sf_csv","gsc_mcp","dataforseo_mcp","scrapling_local","scrapling_mcp","sf_mcp","manual","tool_computed"]`; the SF file source is `sf_csv`).

## 3. DECISIONS already made

- P1-08: pass the slug to Python via an **environment variable** (not string interpolation) and
  **validate** it against the slug pattern `^[a-z0-9][a-z0-9-]*$` before use. KEEP the current
  "write the active marker even if project.config.json is missing, with a WARN" behavior (it is a
  deliberate Phase-5-era convenience) — only the injection + validation are in scope.
- P1-14: `sf_export` → `sf_csv` (the file-based SF source kind).

## 4. FILE MAP

- Modify: the 7 commands in the P0-05 table (add missing `Bash(<cmd>:*)` to `allowed-tools`)
- Modify: `commands/pseo-sf-crawl.md` (P0-06: drop `--source-run-id`, fix `save_report`, complete SF MCP list)
- Modify: `hooks/session-start.json`, `hooks/user-prompt-submit.json` (P1-05: `/pseo-bootstrap-project` → `/pseo-init`)
- Modify: `commands/pseo-active.md`, `commands/pseo-status.md` (P1-08: env-var arg passing + slug regex validation)
- Modify: `commands/pseo-cannibalization.md`, `commands/pseo-schema-audit.md` (P1-14: schema paths + `sf_csv`)
- Create test: `tests/commands/test_allowed_tools_match_shell.py` (P0-05 lock)
- Create test: `tests/commands/test_command_file_references_exist.py` (P1-14 lock — schema refs resolve + enum tokens valid)
- Create test: `tests/hooks/test_hook_command_references_exist.py` (P1-05 lock)
- Create test: `tests/commands/test_sf_crawl_contract.py` (P0-06 lock — no `--source-run-id`, sf_import flags match)
- Create/extend test for P1-08 (guard: no `'$` shell-var interpolation inside `python3 -c` blocks)

## 5. TASKS (TDD — write the test RED first, then fix to GREEN, then commit)

> For each command-scanning test: parse the YAML frontmatter `allowed-tools`, and extract shell program
> tokens from `!` inline blocks (`` !`...` ``) and ```bash fenced blocks. Take the FIRST token of each
> pipeline/`;`/`&&`/`||` segment. Ignore shell builtins/keywords (`cd,echo,then,else,fi,do,done,for,if,
> while,set,exit,true,false,read,local,export,return,test,[,[[,printf,source,.,:`) and tokens that are
> ALL-CAPS (env vars) or contain `.`/`(` (python/jq internals). Match the remaining programs against
> `Bash(<prog>:*)` (or a broader `Bash` catch-all) in allowed-tools.

- [ ] **Part A — P0-05 (commit 1).** Write `tests/commands/test_allowed_tools_match_shell.py` that fails
  for any command whose body uses an undeclared shell program. Run → RED (lists the 7 commands' gaps from
  §2). Fix: add the missing `Bash(<cmd>:*)` entries to each of the 7 commands' `allowed-tools`. Run → GREEN.
  Commit: `fix(commands): declare all shell programs used in command bodies (P0-05)`.
- [ ] **Part B — P0-06 (commit 2).** Write `tests/commands/test_sf_crawl_contract.py`: assert
  `commands/pseo-sf-crawl.md` does NOT contain `--source-run-id`, does NOT contain `save_report=True`, and
  that every `sf_import.py` flag it mentions is in `sf_import.py`'s argparse set. Run → RED. Fix the command:
  remove `--source-run-id` from the sf_import invocation; remove/replace `save_report=True` (state the report
  is produced via the orchestrator, not a CLI flag); add `mcp__sf__sf_generate_bulk_export` +
  `mcp__sf__sf_export_seo_element_urls` to the required MCP tools list. Run → GREEN. Commit:
  `fix(commands): correct pseo-sf-crawl runtime contract to match sf_import + SF MCP (P0-06)`.
- [ ] **Part C — P1-14 (commit 3).** Write `tests/commands/test_command_file_references_exist.py`: scan every
  `commands/*.md` for `schemas/...json` references and assert each target file exists; also assert no command
  uses `source.kind=sf_export` (valid set from events.schema enum). Run → RED. Fix: `gsc-mapping`→
  `gsc-tool-mapping`, `dataforseo-mapping`→`dataforseo-endpoint-mapping`, `sf_export`→`sf_csv`. Run → GREEN.
  Commit: `fix(commands): correct schema-file references + sf_csv event source kind (P1-14)`.
- [ ] **Part D — P1-05 (commit 4).** Write `tests/hooks/test_hook_command_references_exist.py`: scan all
  `hooks/*.json` message text for `/pseo-<name>` tokens and assert each has a `commands/pseo-<name>.md`. Run
  → RED (`/pseo-bootstrap-project` missing). Fix: replace `/pseo-bootstrap-project` with `/pseo-init` in
  `hooks/session-start.json` + `hooks/user-prompt-submit.json`. Run → GREEN. Commit:
  `fix(hooks): reference existing /pseo-init instead of nonexistent /pseo-bootstrap-project (P1-05)`.
- [ ] **Part E — P1-08 (commit 5).** Add a guard test (e.g. in `tests/commands/test_allowed_tools_match_shell.py`
  or a new `tests/commands/test_no_python_shell_interpolation.py`): assert no `commands/*.md` contains a
  `python3 -c` block with a single-quoted shell-var interpolation like `'$` (the injection pattern). Run →
  RED (pseo-active, pseo-status). Fix both commands: pass the slug via an env var
  (`SLUG="$1" python3 -c '...os.environ["SLUG"]...'`) and validate it with
  `re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug)` (error out clearly if invalid). Keep the warn-and-write
  behavior. Run → GREEN. Commit: `fix(commands): pass slug via env + validate, no Python source injection (P1-08)`.

## 6. TEST GATE

```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m pytest tests/commands tests/hooks -v
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   # >= 1463/8 + new
# sanity: every command frontmatter still parses + no command references a missing schema file (your new tests cover this)
```

## 7. OUT OF SCOPE

- Schema hardening — FormatChecker / events.schema conditionals / additionalProperties (Phase 4).
- transaction.py / workflow_runner.py / events_writer.py / audit-hook classification (Phase 5).
- Docs counts / brand-onboarding / templates / the dump_workspace docstring nit (Phase 6).
- Do NOT change command *behavior* beyond the injection-safety rewrite (P1-08) and the contract/reference
  corrections above. Do NOT touch the workspace repo.

## 8. COMPLETION REPORT (return to manager)

```
# Phase 3 Completion Report
- Branch: fix/codex-audit-phase-3-commands | Base: bc0ced8 (main) | Head: <sha>
- Status: DONE | PARTIAL | BLOCKED
- Findings closed: [P0-05, P0-06, P1-05, P1-08, P1-14]
- Commits (5 atomic): <sha> <msg> ; ...
- Tests: full suite = "<N passed, M skipped>"; new tests: [4-5 files]; all green? Y/N
- P0-05: which commands + which Bash(<cmd>:*) added: <...>
- P0-06: --source-run-id removed? save_report fixed? SF MCP tools added? Y/Y/Y
- P1-05: hooks now reference /pseo-init? Y
- P1-08: both commands use env-var + slug regex (no '$ interpolation)? Y
- P1-14: schema refs resolve + sf_export→sf_csv? Y
- Deviations / judgment calls: <...>
- Blockers / questions for manager: <none | ...>
- git diff --stat: <paste>
```
