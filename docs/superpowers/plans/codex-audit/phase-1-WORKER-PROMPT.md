You are a WORKER session executing **Phase 1 — Governance Authority** of the Codex audit
remediation for the Platinum SEO Engine. You have a fresh, full context window. Use it well and
do all the work yourself in THIS session.

== YOUR AUTHORITATIVE SPEC ==
Open and follow this file EXACTLY, task by task — it has the full evidence table, the exact
code↔registry rule mapping, complete test code, and per-task TDD steps:
  docs/superpowers/plans/codex-audit/phase-1-governance.md
Also skim the "Guardrails" + "Worker Completion Report template" sections of:
  docs/superpowers/plans/codex-audit/MANAGER.md
Do not go exploring the rest of the repo — these two files plus the paths they name are complete.

== MISSION ==
Make the governance surface tell the truth about what is actually enforced, and lock it with
tests so it cannot drift again. Close three verified findings:
- P0-01: schemas/cross-sheet-invariants.json (registry) and scripts/validation/validate_invariants.py
  (implementation) assign the SAME F-IDs to DIFFERENT rules for ~12 IDs (F-01..F-05, F-08..F-14).
  The existing sync test only checks ID-sets + a severity literal it cannot always see.
- P0-03: mcp-tool-registry.json is version-lagged (dataforseo lock 2.8.9 vs .mcp.json @2.8.10),
  incomplete (33 tool entries; skills reference more DataForSEO/Scrapling tools), and the
  scrapling vs .mcp.json "ScraplingServer" key alias is not formalized in the schema.
- P1-13: generate-images/SKILL.md (status: active) requires mcp__higgsfield__generate_image, but
  Higgsfield is intentionally not in .mcp.json/registry; there is no representation for a
  user-level external MCP dependency.

== DECISION ALREADY MADE (do NOT re-litigate) — D1 ==
The IMPLEMENTATION (validate_invariants.py) is the source of truth. Rewrite the registry to match
the code's actual rule text + severity. PRESERVE the displaced original design rules (the current
registry meanings of the mismatched IDs, plus D-01, D-02, D-03, M-01, M-02) by MOVING them into a
NEW top-level array "deferred_design_rules" in cross-sheet-invariants.json (same object shape, add
"status":"deferred" and a note that they are cross-sheet join rules not yet enforced at the
validate_invariants row level). Do NOT delete them — they encode design.md §17.2 intent. Do NOT
change any check_F_* behavior — only the registry JSON, schema wording, the registry tests, and
the generate-images preflight text.

== HARD RULES (non-negotiable) ==
1. Do NOT spawn subagents — do NOT use the Task or Agent tools. They FAIL in this project (the
   session's MCP tool registry is too large for a subagent to load: "Prompt is too long"). Do
   every step inline in this session.
2. Invoke the superpowers:test-driven-development skill and follow it strictly: write the failing
   test, run it and confirm it FAILS, write the minimal change, run it and confirm it PASSES, then
   commit. Before claiming the phase done, invoke superpowers:verification-before-completion and
   actually run the gate commands.
3. Branch first: git checkout -b fix/codex-audit-phase-1-governance  (off main). NEVER commit to
   main. NEVER push. NEVER merge.
4. Exactly 3 atomic commits — one per finding, in order P0-01, then P0-03, then P1-13. Use the
   commit messages given in phase-1-governance.md Part A/B/C.
5. Engine repo ONLY: /Users/apple/Documents/platinum-seo-engine. Do NOT touch the workspace repo
   (/Users/apple/Documents/platinum-seo-workspace) in this phase.
6. NEVER commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md. Preserve all unrelated local files.
7. Keep the baseline green. After each commit and at the end:
   PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q
   must stay at >= 1449 passed, 8 skipped, PLUS your 4 new test files passing.

== SCOPE — do ONLY Phase 1 ==
Out of scope (owned by later phases, do not touch): dump_workspace.py / workspace schemas /
portfolio cap; commands/*.md / hooks/*.json; validate_schema.py FormatChecker / events.schema /
additionalProperties; transaction.py / workflow_runner.py / events_writer.py; docs counts /
brand-onboarding / templates.

== WORK PLAN (full per-task TDD detail + all code is in phase-1-governance.md §5) ==
- Part A / commit 1 (P0-01): Add the two new tests (test_registry_rule_text_binds_to_implementation
  and test_registry_severity_binds_to_implementation — full code in the brief). Run -> RED (12
  rule mismatches + F-04 severity). Rewrite the 12 mismatched entries in
  schemas/cross-sheet-invariants.json to the code's exact rule text (table in brief §2) and align
  severity (F-04 -> CRITICAL); move the displaced original rules + D-01..D-03/M-01..M-02 into the
  new deferred_design_rules array. Fix the old regex-based severity test so it reads severity from
  the result dict instead of the source. Run -> GREEN. Full suite green. Commit.
- Part B / commit 2 (P0-03): Add tests/schemas/test_mcp_registry_versions_match_mcp_json.py (full
  code in brief) -> RED; set registry servers.dataforseo.version_lock to "2.8.10" and update the
  schema description that hardcodes 2.8.9. Add tests/schemas/test_skill_mcp_tools_exist_in_registry.py
  -> RED; add the missing skill-referenced tools to the registry; formalize the
  ScraplingServer<->scrapling alias with an explicit field + assertion. Run -> GREEN. Commit.
- Part C / commit 3 (P1-13): Add tests/skills/test_generate_images_external_dep.py (full code in
  brief) -> RED; add a top-level external_user_dependencies.higgsfield block to the registry (NOT
  under servers — that would trip the F-24 invariant) and a short preflight note in
  generate-images/SKILL.md. Run -> GREEN. Commit.

== FINAL TEST GATE (every item must hold before you report DONE) ==
- python3 -m pytest tests/schemas/test_cross_sheet_invariants_sync.py
  tests/schemas/test_mcp_registry_versions_match_mcp_json.py
  tests/schemas/test_skill_mcp_tools_exist_in_registry.py
  tests/skills/test_generate_images_external_dep.py -v   (all pass)
- PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q
  (>= 1449 passed, 8 skipped, + new)
- python3 -c "import json; json.load(open('mcp-tool-registry.json')); json.load(open('schemas/cross-sheet-invariants.json')); print('JSON ok')"

== WHEN DONE: produce this COMPLETION REPORT (paste-ready; the human pastes it to the manager) ==
# Phase 1 Completion Report
- Branch: fix/codex-audit-phase-1-governance | Base: <sha> | Head: <sha>
- Status: DONE | PARTIAL | BLOCKED
- Findings closed: [P0-01, P0-03, P1-13] | deferred: [...]
- Commits: <sha> <msg> ; <sha> <msg> ; <sha> <msg>
- Tests: full suite = "<N passed, M skipped>"; new tests: [4 file names]; all green? Y/N
- drift-check sanity: validate_invariants _RULE_FUNCTIONS count = <n>; any verdict regression? Y/N
- Judgment calls (exact scrapling alias field name, external-dep field names, tool metadata added): <...>
- Blockers / questions for manager: <none | ...>
- git diff --stat: <paste>

== BEGIN NOW ==
Invoke superpowers:test-driven-development, open docs/superpowers/plans/codex-audit/phase-1-governance.md,
create the branch, and start Part A Task 1.1. Work through all three parts. Do not stop to ask for
confirmation between tasks unless you hit a real blocker; if blocked, record it in the Completion
Report and continue with what you can.
