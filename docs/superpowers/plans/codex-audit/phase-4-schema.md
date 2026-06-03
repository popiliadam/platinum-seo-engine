# Phase 4 — Schema Hardening — Worker Brief

## 0. READ FIRST (worker onboarding)

- Fresh worker session. Engine repo: `/Users/apple/Documents/platinum-seo-engine`. ENGINE-ONLY.
- Invoke `superpowers:test-driven-development` + `superpowers:verification-before-completion`.
- **Branch:** `git checkout -b fix/codex-audit-phase-4-schema` off `main` (confirm `git log --oneline -3`
  shows the Phase 3 merge `e0faa81`). Never commit to main, never push.
- Hard rules: NO subagents (Task/Agent fail here); atomic commits; never commit
  `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`; preserve untracked planning docs; do NOT touch the workspace repo
  (you only READ the 10 live configs for validation gates).
- **Baseline:** `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`
  must stay ≥ **1478 passed, 8 skipped** + your new tests.

## 1. GOAL + findings

**Goal:** Make schema validation actually enforce the contracts it claims — `format` is checked,
critical nested objects reject typos, event conditionals give clean errors, and the JSON-Schema-draft
story is locked by a test.

- **P1-01** — No test locks docs + schema `$schema` + validator class to the same JSON Schema draft.
  (Already consistent at Draft 7 — this is a regression LOCK, not a bug fix.)
- **P1-02** — `scripts/validation/validate_schema.py:59` uses `Draft7Validator(schema)` with no
  `format_checker`, so `format: uri` / `date-time` strings are never validated.
- **P1-03** — Critical nested objects in `project-config.schema.json` lack `additionalProperties:false`
  (15 open objects), so typo'd nested keys pass silently. Close the HIGH-RISK ones (selectively, safely).
- **P1-04** — `events.schema.json` `allOf` `if` blocks don't `require` `event_kind`, so a legacy event
  missing it triggers multiple branches → noisy errors. Description says "Three kinds"; enum has 4.

## 2. EVIDENCE (verified)

- P1-01: `README.md:243` says "JSON Schema (Draft 7) — 21 schemas (20 *.schema.json + cross-sheet-invariants.json)".
  All `schemas/*.schema.json` use `"$schema": "http://json-schema.org/draft-07/schema#"`.
  `validate_schema.py` imports `Draft7Validator`. NO test asserts these three agree.
- P1-02: `validate_schema.py:59` `validator = Draft7Validator(schema)` — no `format_checker=...`.
- P1-03: in `project-config.schema.json`, the high-risk OPEN objects (no `additionalProperties`):
  `language`, `paths`, `gsc`, `dataforseo`, `brand`, `thresholds`, `workflow` (+ nested objects under
  `content_settings`). Closing them rejects typo'd keys. NOTE: the 10 live workspace configs were just
  migrated to 1.5 — closing must not reject any key they legitimately use.
- P1-04: `events.schema.json` `allOf[0..2]` have `if: {properties: {event_kind: {const: ...}}}` with NO
  `required: ["event_kind"]`. Root `required` already includes `event_kind`, so a missing-event_kind
  event errors at root too — but the branch noise is real. `description` (line ~5) says "Three kinds";
  the `event_kind` enum is `["provenance","work","audit","workflow"]` (FOUR).

## 3. DECISIONS already made

- P1-02: enforce `uri` + `date-time` (and any other `format` the schemas actually use) via a
  `FormatChecker` with **inline custom check functions** (NO new pip dependency). jsonschema silently
  skips a format whose backing lib is absent — custom checkers guarantee real enforcement.
- P1-03: **selective + safe**. Close only the high-risk objects in §2, and after EACH closure re-validate
  all 10 live workspace configs — they MUST stay 10/10 valid. If a closure rejects a real config's key:
  if the key is legitimate, ADD it to that object's `properties`; if it's genuinely unexpected, leave that
  object open and record it. Never break a live config to close an object.
- P1-04: add `required: ["event_kind"]` inside each conditional `if`; fix "Three"→"Four kinds".

## 4. FILE MAP

- Create test: `tests/schemas/test_json_schema_draft_consistency.py` (P1-01)
- Modify: `scripts/validation/validate_schema.py` (P1-02: FormatChecker + custom checkers)
- Create test: `tests/scripts/test_validate_schema_enforces_format.py` (P1-02)
- Modify: `schemas/project-config.schema.json` (P1-03: additionalProperties:false on high-risk objects)
- Create test: `tests/schemas/test_project_config_rejects_unknown_nested_keys.py` (P1-03 negative fixtures)
- Modify: `schemas/events.schema.json` (P1-04: if-required + description)
- Create test: `tests/schemas/test_events_schema_clean_error.py` (P1-04)

## 5. TASKS (TDD)

### Part A — P1-01 lock (commit 1)
- [ ] Write `tests/schemas/test_json_schema_draft_consistency.py`: (a) every `schemas/*.schema.json` has
  `$schema` containing `draft-07`; (b) `validate_schema.py` source contains `Draft7Validator` and not
  `Draft201909`/`Draft202012`; (c) `README.md` contains "Draft 7" and not "Draft 2020-12"/"2019-09".
  Run → should PASS immediately (it's a lock; the system is already consistent). If anything is NOT
  consistent, that's a real finding — fix it. Commit: `test(schema): lock JSON Schema draft across docs/schemas/validator (P1-01)`.

### Part B — P1-02 FormatChecker (commit 2)
- [ ] First enumerate the formats actually used: `rg -o '"format"\s*:\s*"[^"]+"' schemas/` — note the set
  (likely `uri`, `date-time`, maybe `email`). 
- [ ] **RED:** write `tests/scripts/test_validate_schema_enforces_format.py` that builds a tiny schema
  `{"type":"object","properties":{"u":{"type":"string","format":"uri"},"d":{"type":"string","format":"date-time"}}}`
  and asserts `validate_schema`-style validation REJECTS `{"u":"not a uri","d":"nonsense"}`. Import the
  validator the same way the CLI builds it (refactor `main()` so the validator construction is a callable
  you can unit-test, e.g. `build_validator(schema)`). Run → RED (bad values currently pass).
- [ ] **GREEN:** in `validate_schema.py`, construct a `FormatChecker()` and register inline checkers for
  each used format, e.g.:
  ```python
  from jsonschema import FormatChecker
  from urllib.parse import urlparse
  from datetime import datetime
  _FORMAT_CHECKER = FormatChecker()
  @_FORMAT_CHECKER.checks("uri", raises=ValueError)
  def _is_uri(v):
      if not isinstance(v, str): return True
      r = urlparse(v); return bool(r.scheme and (r.netloc or r.path))
  @_FORMAT_CHECKER.checks("date-time", raises=ValueError)
  def _is_dt(v):
      if not isinstance(v, str): return True
      datetime.fromisoformat(v.replace("Z", "+00:00")); return True
  ```
  then `Draft7Validator(schema, format_checker=_FORMAT_CHECKER)`. Run → GREEN. Run the FULL suite — if any
  EXISTING data now fails format validation, that's a real latent bug: fix the data fixture or the format,
  do not weaken the checker. Commit: `fix(validation): enforce format (uri/date-time) via custom FormatChecker (P1-02)`.

### Part C — P1-04 event conditionals (commit 3)
- [ ] **RED:** write `tests/schemas/test_events_schema_clean_error.py`: validate a legacy event WITHOUT
  `event_kind` (e.g. `{"schema_version":"1.0","event_id":"x","timestamp":"2026-06-03T00:00:00Z","project_id":"demo"}`)
  and assert the errors point at the MISSING `event_kind` (root required) and do NOT include unrelated
  branch-specific field errors (e.g. no complaint about `run_id`/`task_id` from the provenance/work
  branches). Also assert the schema `description` says "Four kinds" (or lists all 4) and not "Three kinds".
  Run → RED (branch noise present; description says Three).
- [ ] **GREEN:** in `events.schema.json`, add `"required": ["event_kind"]` inside each conditional `if`
  (so a branch only applies when `event_kind` is present AND matches). Update the description "Three
  kinds" → "Four kinds" and mention `workflow`. Run → GREEN + full suite. Commit:
  `fix(schema): require event_kind inside event conditionals + fix kind count (P1-04)`.

### Part D — P1-03 nested additionalProperties (commit 4) — SELECTIVE + SAFE
- [ ] **Pre-check:** confirm all 10 live configs currently validate (baseline):
  ```bash
  for f in /Users/apple/Documents/platinum-seo-workspace/projects/*/project.config.json; do
    python3 scripts/validation/validate_schema.py "$f" schemas/project-config.schema.json >/dev/null && echo "OK $(basename $(dirname $f))" || echo "FAIL $(basename $(dirname $f))"
  done
  ```
- [ ] **RED:** write `tests/schemas/test_project_config_rejects_unknown_nested_keys.py` with a minimal valid
  config + a deliberately misspelled nested key in (say) `language` (e.g. `"content_localee": "tr-TR"`),
  and assert validation REJECTS it. Run → RED (currently passes — object is open).
- [ ] **GREEN (one object at a time):** add `"additionalProperties": false` to `language`, `paths`, `gsc`,
  `dataforseo`, `brand`, `thresholds`, `workflow` (and safe nested objects under `content_settings`).
  After EACH object, run the §Pre-check live-config validation — it MUST stay 10/10 OK. If an object's
  closure makes a real config FAIL, inspect the offending key: add it to that object's `properties` if
  legitimate, else leave that object OPEN and note it in your report. Run the negative-fixture test → GREEN
  and the full suite. Commit: `fix(schema): close high-risk project-config nested objects to reject typos (P1-03)`.

## 6. TEST GATE

```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m pytest tests/schemas tests/scripts -q
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   # >= 1478/8 + new
# live-config safety (P1-03): all 10 still validate
for f in /Users/apple/Documents/platinum-seo-workspace/projects/*/project.config.json; do python3 scripts/validation/validate_schema.py "$f" schemas/project-config.schema.json >/dev/null && echo "OK" || echo "FAIL $f"; done
```

## 7. OUT OF SCOPE

- transaction.py / workflow_runner.py / events_writer.py / audit hooks (Phase 5).
- Docs counts / brand-onboarding / templates / dump_workspace docstring (Phase 6).
- Do NOT close additionalProperties on schemas other than `project-config.schema.json` this phase
  (the other ~80 open objects are a separate, lower-risk pass — the audit said "selective").
- Do NOT add new pip dependencies (use inline custom format checkers).

## 8. COMPLETION REPORT (return to manager)

```
# Phase 4 Completion Report
- Branch: fix/codex-audit-phase-4-schema | Base: e0faa81 (main) | Head: <sha>
- Status: DONE | PARTIAL | BLOCKED
- Findings closed: [P1-01, P1-02, P1-03, P1-04]
- Commits (4 atomic): <sha> <msg> ; ...
- Tests: full suite = "<N passed, M skipped>"; new tests: [4 files]; all green? Y/N
- P1-02: formats enforced = [uri, date-time, ...]; bad-fixture rejected? Y ; any existing data broken+fixed? <...>
- P1-03: objects closed = [...]; live configs still 10/10 valid? Y ; any object left open (why)? <...>
- P1-04: event_kind required in all N if-blocks? Y ; description now "Four kinds"? Y ; legacy event error is clean? Y
- P1-01: lock test passes (draft consistent)? Y
- Deviations / judgment calls: <...>
- Blockers / questions for manager: <none | ...>
- git diff --stat: <paste>
```
