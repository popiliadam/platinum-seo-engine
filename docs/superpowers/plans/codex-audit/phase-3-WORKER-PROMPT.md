You are a WORKER session executing Phase 3 — Commands & Hook UX of the Codex audit remediation for the Platinum SEO Engine. Fresh full context — do all work yourself here.

AUTHORITATIVE SPEC: Open and follow this file EXACTLY, task by task (full evidence + per-task TDD steps):
  docs/superpowers/plans/codex-audit/phase-3-commands.md
Also skim the "Guardrails" + "Completion Report" sections of:
  docs/superpowers/plans/codex-audit/MANAGER.md
Do not explore the rest of the repo — these files plus the paths they name are complete.

MISSION: Make every slash command + hook message executable and accurate, each locked by a test. Close:
- P0-05: 7 commands use shell programs not declared in their allowed-tools frontmatter (mkdir, grep, head, sort, curl, tail, xargs, find — exact table in the brief §2).
- P0-06: pseo-sf-crawl.md documents an invalid contract — sf_import.py --source-run-id (argparse exit 2), save_report=True, incomplete SF MCP tool list.
- P1-05: hooks/session-start.json + hooks/user-prompt-submit.json tell users to run /pseo-bootstrap-project, which does NOT exist (real command: /pseo-init).
- P1-08: pseo-active.md + pseo-status.md interpolate a shell var into Python source (slug = '$SLUG') — injection-unsafe + unvalidated slug.
- P1-14: pseo-cannibalization.md references schemas/gsc-mapping.schema.json (real: gsc-tool-mapping); pseo-schema-audit.md references schemas/dataforseo-mapping.schema.json (real: dataforseo-endpoint-mapping) and uses source.kind=sf_export (not in the events enum; correct = sf_csv).

DECISIONS (do NOT re-litigate):
- P1-08: pass the slug via an ENV VAR (not string interpolation) and validate it against ^[a-z0-9][a-z0-9-]*$ before use. KEEP the current "write the active marker even if project.config.json is missing, with a WARN" behavior — only the injection + validation are in scope.
- P1-14: sf_export → sf_csv.

HARD RULES:
1. Do NOT spawn subagents / Task / Agent tools — they fail here ("Prompt is too long"). Work inline.
2. Invoke superpowers:test-driven-development (write the test RED first, then fix to GREEN, then commit) + superpowers:verification-before-completion before claiming done.
3. Branch: git checkout -b fix/codex-audit-phase-3-commands off main (confirm git log --oneline -3 shows the bc0ced8 Phase 2 merge). Never commit to main, never push.
4. 5 atomic commits (one per finding: P0-05, P0-06, P1-14, P1-05, P1-08) — messages in the brief §5.
5. Engine repo ONLY (/Users/apple/Documents/platinum-seo-engine). Do NOT touch the workspace repo.
6. NEVER commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md. Preserve unrelated/untracked files (the docs/superpowers/plans/ planning docs are untracked — leave them).
7. Baseline must stay green: PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q  >= 1463 passed, 8 skipped + your new tests.

SCOPE — Phase 3 only. Out of scope: schema hardening / FormatChecker / events.schema conditionals / additionalProperties (Phase 4); transaction/workflow_runner/events_writer/audit-hook (Phase 5); docs counts / brand-onboarding / templates / the dump_workspace docstring nit (Phase 6). Do not change command behavior beyond the P1-08 injection-safety rewrite and the contract/reference corrections.

TEST-WRITING GUIDANCE (for the command-scanning tests): parse YAML frontmatter allowed-tools; extract shell program tokens from !`...` inline blocks and ```bash fences (first token of each pipeline/;/&&/|| segment); ignore shell builtins/keywords (cd,echo,then,else,fi,do,done,for,if,while,set,exit,true,false,read,local,export,return,test,[,[[,printf,source,.,:) and ALL-CAPS env vars and tokens containing . or ( (python/jq internals); match the rest against Bash(<prog>:*) or a Bash catch-all.

WORK PLAN (full detail in the brief §5):
- Commit 1 (P0-05): tests/commands/test_allowed_tools_match_shell.py → RED; add missing Bash(<cmd>:*) to the 7 commands → GREEN.
- Commit 2 (P0-06): tests/commands/test_sf_crawl_contract.py → RED; remove --source-run-id, fix save_report, add the 2 missing SF MCP tools → GREEN.
- Commit 3 (P1-14): tests/commands/test_command_file_references_exist.py → RED; fix gsc-tool-mapping, dataforseo-endpoint-mapping, sf_export→sf_csv → GREEN.
- Commit 4 (P1-05): tests/hooks/test_hook_command_references_exist.py → RED; /pseo-bootstrap-project → /pseo-init in both hooks → GREEN.
- Commit 5 (P1-08): guard test (no '$ interpolation inside python3 -c) → RED; rewrite pseo-active.md + pseo-status.md to pass slug via env var + validate regex → GREEN.

FINAL GATE (all must hold):
- python3 -m pytest tests/commands tests/hooks -v   (all pass)
- PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   (>= 1463/8 + new)

WHEN DONE, output a paste-ready COMPLETION REPORT (template in the brief §8): branch + base/head sha; status; findings closed; the 5 commit shas+messages; full-suite result + new test names + all-green Y/N; per-finding confirmations (P0-05 commands+tools added; P0-06 source-run-id removed/save_report fixed/SF tools added; P1-05 hooks→/pseo-init; P1-08 env+regex no-interpolation; P1-14 refs resolve + sf_csv); deviations; blockers; git diff --stat.

BEGIN NOW: invoke superpowers:test-driven-development, open the brief, create the branch (verify base shows bc0ced8), start Part A, and work through all five parts without pausing unless truly blocked.
