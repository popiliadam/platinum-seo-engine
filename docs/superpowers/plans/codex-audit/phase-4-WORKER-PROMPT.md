You are a WORKER session executing Phase 4 — Schema Hardening of the Codex audit remediation for the Platinum SEO Engine. Fresh full context — do all work yourself here.

AUTHORITATIVE SPEC: Open and follow this file EXACTLY, task by task (full code + per-task TDD steps):
  docs/superpowers/plans/codex-audit/phase-4-schema.md
Also skim the "Guardrails" + "Completion Report" sections of:
  docs/superpowers/plans/codex-audit/MANAGER.md
Do not explore the rest of the repo — these files plus the paths they name are complete.

MISSION: Make schema validation enforce the contracts it claims. Close:
- P1-01: no test locks docs + schema $schema + validator class to the same JSON Schema draft (already consistent at Draft 7 → add a regression LOCK).
- P1-02: validate_schema.py uses Draft7Validator(schema) with no format_checker → format: uri/date-time never enforced.
- P1-03: critical nested objects in project-config.schema.json lack additionalProperties:false → typo'd nested keys pass silently. Close the HIGH-RISK ones selectively + safely.
- P1-04: events.schema.json `if` blocks don't require event_kind → a legacy event missing it triggers multiple branches (noisy errors); description says "Three kinds" but the enum has 4 (provenance/work/audit/workflow).

DECISIONS (do NOT re-litigate):
- P1-02: enforce uri + date-time (and any other format the schemas use) via FormatChecker with INLINE custom check functions — NO new pip dependency (jsonschema silently skips formats whose backing lib is absent, so custom checkers guarantee real enforcement). Code pattern is in the brief §5 Part B.
- P1-03: SELECTIVE + SAFE. Close only the high-risk objects (language, paths, gsc, dataforseo, brand, thresholds, workflow, + safe nested under content_settings). After EACH closure, re-validate all 10 live workspace configs — they MUST stay 10/10 valid. If a closure rejects a real config's legitimate key, ADD it to that object's properties; if genuinely unexpected, leave that object OPEN and record it. NEVER break a live config to close an object.
- P1-04: add required:["event_kind"] inside each conditional `if`; fix "Three"→"Four kinds".

HARD RULES:
1. Do NOT spawn subagents / Task / Agent tools — they fail here ("Prompt is too long"). Work inline.
2. Invoke superpowers:test-driven-development (write the failing test, confirm RED, minimal fix, confirm GREEN, commit) + superpowers:verification-before-completion before claiming done.
3. Branch: git checkout -b fix/codex-audit-phase-4-schema off main (confirm git log --oneline -3 shows the e0faa81 Phase 3 merge). Never commit to main, never push.
4. 4 atomic commits (P1-01, P1-02, P1-04, P1-03 — that order; P1-03 last as it is the most delicate) — messages in the brief §5.
5. Engine repo ONLY (/Users/apple/Documents/platinum-seo-engine). Do NOT modify the workspace repo — you only READ the 10 live configs for the P1-03 safety gate.
6. NEVER commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md. Preserve untracked planning docs.
7. Baseline must stay green: PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q  >= 1478 passed, 8 skipped + your new tests.
8. Do NOT add pip dependencies. Do NOT close additionalProperties on schemas other than project-config.schema.json this phase (the other ~80 open objects are a separate lower-risk pass).

WORK PLAN (full code + commands in the brief §5):
- Commit 1 (P1-01): tests/schemas/test_json_schema_draft_consistency.py — assert all schemas $schema=draft-07, validate_schema uses Draft7Validator, README says "Draft 7". Should pass immediately (lock). If anything inconsistent, fix it.
- Commit 2 (P1-02): enumerate formats used (rg '"format"' schemas/); RED test (bad uri/date-time rejected) — refactor validate_schema so validator construction is unit-testable (build_validator(schema)); GREEN by adding FormatChecker with inline uri/date-time checkers. Run full suite — fix any real data that now fails (don't weaken the checker).
- Commit 3 (P1-04): RED test (legacy event with no event_kind → clean root error, NO branch-field noise; description "Four kinds"); GREEN by adding required:["event_kind"] inside each `if` + fixing the description.
- Commit 4 (P1-03): pre-check all 10 live configs validate; RED negative-fixture test (misspelled nested key rejected); GREEN by adding additionalProperties:false to the high-risk objects ONE AT A TIME, re-validating all 10 live configs after each (stay 10/10). Add legitimately-present keys to properties as needed; leave an object open + record if a real key is unexpected.

FINAL GATE (all must hold):
- python3 -m pytest tests/schemas tests/scripts -q   (all pass)
- PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   (>= 1478/8 + new)
- all 10 live project.config.json still validate against project-config.schema.json (P1-03 safety)

WHEN DONE, output a paste-ready COMPLETION REPORT (template in the brief §8): branch + base/head sha; status; findings closed; 4 commit shas+messages; full-suite result + new test names + all-green Y/N; P1-02 formats enforced + bad-fixture rejected + any data fixed; P1-03 objects closed + live configs 10/10 + any object left open & why; P1-04 event_kind required in all if-blocks + "Four kinds" + clean error; P1-01 lock passes; deviations; blockers; git diff --stat.

BEGIN NOW: invoke superpowers:test-driven-development, open the brief, create the branch (verify base shows e0faa81), start Part A, work through all four parts. For P1-03, validate the 10 live configs after every single object closure and STOP/record rather than breaking any config.
