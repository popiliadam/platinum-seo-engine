# AMO Batch 1a — Phase-1 Schema Freeze (WORKER PROMPT)

> **Manager note (not part of the prompt):** Phase 0 is complete + pushed (HEAD `09674c5`, suite 1789/0).
> This is the FIRST Phase-1 batch and a deliberate **schema-freeze**: it adds the `coverage` record schema
> + the additive `failure_reason.external` discriminator + confirms the existing `paused` state suffices for
> external-failure-allow-end. Everything downstream in Phase 1 keys on these contracts — 1b (`run_step.py`
> writes the coverage record), 2c (the denetçi reads `verdict`/`required_satisfied` + `failure_reason.external`),
> and the oracle (reads `verification_class`/`observed_mcp`). So it must freeze FIRST and alone. It is small on
> purpose. No runner, no router, no committer here — those are 1b/1c/1d. Adding `schemas/coverage.schema.json`
> trips the D10 count-guards; the prompt pre-authorizes the exact two bumps (manager verifies the numbers).
> Paste the block below into a fresh Claude Code session (Opus 4.8, 1M context) rooted at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 1a of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and
print the REPORT (the manager reviews + commits).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state. No `git add`/`commit`/`checkout`/`reset`.
- Baseline-first: run `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N is ~1789) BEFORE any change. You MUST END green with
  passed strictly >= N (your new tests add to it).
- TDD: write the FAILING test first, watch it fail, then implement until green. Never fake red.
- House style: immutability (return/build NEW objects, never mutate inputs); no print/console debug left in
  shipped code; no hardcoded secrets; small focused functions (<50 lines); files 200-400 lines normal.
- Scope-lock: create/modify ONLY the files named in SCOPE below. If a fix seems to need any OTHER file,
  STOP and report it — do not touch it. (The 2 D10 count-guard files ARE in scope; see SCOPE.)

WHY THIS BATCH EXISTS (read carefully):
AMO is building an autonomous SEO orchestrator. After each step runs, an INDEPENDENT "coverage record" is
written to `_state/coverage/<run_id>.json` (OUTSIDE events.jsonl) proving what ran and whether it was
truly verified. A Stop-hook auditor (later batch) reads that record to decide: pass, BLOCK-with-a-fix, or
allow-but-flag (when an EXTERNAL dependency like GSC/DFS failed). This batch FREEZES the three contracts
that decision rests on, so the runner (1b) and auditor (2c) can be built against a stable shape:
  (1) NEW `schemas/coverage.schema.json` — the coverage-record shape.
  (2) additive `failure_reason.external: bool` on `workflow-run.schema.json` (+ a writer in workflow_runner).
  (3) confirm the EXISTING `paused` state + its (running->paused)/(paused->running) edges are enough for
      "external failure: allow turn-end" — NO new state, NO new failure codes, NO event_type change.
This is schema-first by design. You are NOT building the runner, router, committer, or denetçi — only the
contracts + the minimal writer that makes `failure_reason.external` real and tested.

CONFIRMED FACTS (do not re-derive — the manager verified these against the code 2026-06-05):
- `schemas/workflow-run.schema.json` ALREADY has `status` enum = [running, awaiting_approval, paused, done,
  failed] and an allOf that requires `paused_at` when status=paused and `failure_reason` when status=failed.
  The `failure_reason` object (lines ~150-172) currently has properties {code, message, step_index} with
  `additionalProperties:false` and `code` enum = [validation_error, mcp_error, budget_exhausted,
  user_rejected, timeout, internal_error]. There is a SECOND copy of the failure_reason shape nested under
  `retry_history.items.failure_reason` (lines ~211-224) — you must add `external` to BOTH copies.
- The v2 failure codes (mcp_unreachable / gsc_outage / dfs_budget_exhausted) DO NOT EXIST and must NOT be
  added. External-vs-internal is expressed by the new boolean `external`, NOT by new codes (spec decision D4).
- `event_type` is a CLOSED exactly-12 enum with tests asserting its count — coverage is a dedicated file,
  it is NOT a 13th event_type. Do NOT touch events.schema.json.
- `scripts/state/workflow_runner.py` is the ONLY writer of failure_reason. `fail()` (lines ~602-625) builds
  `failure = {"code": code, "message": message}` then conditionally adds `step_index`, then calls
  `transition(..., failure_reason=failure)`. `_validate(data, schema)` runs `Draft7Validator` against the
  workflow-run schema on every write, so a run that sets `failure_reason.external` only validates AFTER you
  add `external` to the schema. The transition table `_ALLOWED_TRANSITIONS` (lines ~333-358) ALREADY contains
  ("running","paused"), ("awaiting_approval","paused"), ("paused","running"), ("paused","failed") — the edges
  needed for external-failure handling already exist; this batch only ADDS A TEST confirming that, no code.
- run_id grammar (reuse it verbatim in the coverage schema so a coverage record joins 1:1 to its run):
  `^[a-z][a-z0-9-]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{4}$`  (i.e. {project_slug}-{YYYY-MM-DD}-{hash4}).
- `verification_class`, `observed_mcp`, `required_satisfied`, `code_verified`, `model_attested` are GREENFIELD
  (grep finds zero references) — you are defining them for the first time. No consumer to keep green.
- D10 count-guard: adding ANY `schemas/*.schema.json` file trips TWO guards (see SCOPE for the exact two
  edits). plugin.json carries NO tested schema count (only skills/commands/MCP), so do NOT touch plugin.json.

ORIENT FIRST (read, do not change yet):
- `schemas/workflow-run.schema.json` IN FULL — especially the `failure_reason` block (~150-172) and the
  `retry_history.items.failure_reason` mirror (~211-224). This is where `external` goes (twice).
- `schemas/session-marker.schema.json` — the most recently authored schema; COPY its header style
  ($schema draft-07 URI, $id `http://platinum-seo-engine/schemas/<name>`, title "X v1.0", a rich
  description that cites WHO writes it / WHO reads it / WHY, additionalProperties:false, a schema_version
  const "1.0"). Match this house style for coverage.schema.json.
- `scripts/state/workflow_runner.py` — `fail()` (~602-625), `pause()` (~580-590), `resume()` (~593-599),
  `_ALLOWED_TRANSITIONS` (~333-358), and how `_validate` is called. You add an `external` kwarg to `fail()`.
- `tests/schemas/test_instance_validation.py` — the existing pattern for validating a sample instance
  against a schema with `Draft7Validator`. Mirror it for the coverage-schema test.
- `tests/schemas/test_json_schema_draft_consistency.py` — has `test_schemas_count_is_twenty_one` with
  `assert count == 21` over `schemas/*.schema.json`. You bump it to 22 (D10; see SCOPE).
- `tests/scripts/test_workflow_runner.py` — the existing failure_reason tests (e.g. around line 161, 253,
  495). You ADD tests here; keep ALL existing ones green.
- `.claude-plugin/marketplace.json` — find the literal substring "22 schemas" (its `_count_schemas()` globs
  schemas/*.json = currently 22: 21 *.schema.json + cross-sheet-invariants.json). You bump it to "23 schemas".

SCOPE — create/modify ONLY these files:
  NEW  schemas/coverage.schema.json                         (the coverage-record shape; see SPEC)
  NEW  tests/schemas/test_coverage_schema.py                (instance validation, valid + invalid cases)
  EDIT schemas/workflow-run.schema.json                     (add `external` boolean to BOTH failure_reason copies)
  EDIT scripts/state/workflow_runner.py                     (add `external: bool = False` kwarg to fail())
  EDIT tests/scripts/test_workflow_runner.py                (ADD: fail(external=True) + default-absent + paused-reuse confirm)
  EDIT tests/schemas/test_json_schema_draft_consistency.py  (D10 count-guard: assert 21 -> 22; rename helper + docstring)
  EDIT .claude-plugin/marketplace.json                      (D10 count-guard: "22 schemas" -> "23 schemas")

  >> The last two are PRE-AUTHORIZED D10 count-guard bumps. They are deterministic and forced by adding the
     schema (without them the suite cannot end green). Apply them exactly as specified and FLAG them clearly
     in your REPORT under "D10 count-guard bumps" so the manager double-checks the numbers. Touch NOTHING ELSE
     in those two files (only the count-assert line + the docstring/helper name in the test, and only the
     "22 schemas" -> "23 schemas" substring in marketplace.json).

SPEC — schemas/coverage.schema.json (author this EXACT shape; you may refine field DESCRIPTIONS but the
property NAMES, enums, and required[] are FROZEN — downstream batches 1b/2c key on them literally):

  {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://platinum-seo-engine/schemas/coverage",
    "title": "Coverage Record v1.0",
    "description": "Shape of projects/{slug}/_state/coverage/{run_id}.json — the INDEPENDENT per-run coverage
      proof the AMO orchestrator (run_step.py, batch 1b) writes after each step and the denetci Stop-hook
      (batch 2c) + correctness oracle read to decide pass / block / paused. Lives OUTSIDE events.jsonl on
      purpose: event_type is a closed exactly-12 enum (spec D3), so coverage is a dedicated file, never a
      13th event_type. verification_class per step lets the <=5% structured-error metric NEVER count a
      model_attested (judgment) step as code_verified (structured). run_id reuses workflow-run.schema.json's
      grammar so a coverage record joins 1:1 to its workflow run.",
    "type": "object",
    "required": ["run_id", "steps", "required_satisfied", "verdict"],
    "additionalProperties": false,
    "properties": {
      "schema_version": { "const": "1.0", "description": "ADR-018/019 const discipline; lets a future migration discriminate older coverage records. Optional (not in required[])." },
      "run_id":       { "type": "string", "pattern": "^[a-z][a-z0-9-]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{4}$", "description": "Joins 1:1 to workflow-run.schema.json run_id (identical grammar): {project_slug}-{YYYY-MM-DD}-{hash4}." },
      "project_slug": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$", "description": "Project this run belongs to (matches projects/{slug}/). Optional." },
      "engine_version": { "type": "string", "minLength": 1, "description": "plugin.json version stamped at run start (spec section 8 self-upgrade versioning); orchestrator may assert artifact_version == plugin version on resume. Optional." },
      "steps": {
        "type": "array",
        "minItems": 0,
        "description": "One entry per executed step, in execution order.",
        "items": {
          "type": "object",
          "required": ["name", "verification_class", "status"],
          "additionalProperties": false,
          "properties": {
            "name":               { "type": "string", "minLength": 1, "description": "Step identifier, stable across runs; matches the workflow-run steps[].name (e.g. 'fetch_gsc')." },
            "verification_class": { "type": "string", "enum": ["code_verified", "model_attested"], "description": "code_verified = a structured step gated by identity+content (counts toward the <=5% oracle). model_attested = a judgment step (e.g. blog generation) the orchestrator records as RAN but does NOT verify for quality — NEVER counted as verified." },
            "status":             { "type": "string", "enum": ["pending", "running", "satisfied", "missing", "failed", "skipped"], "description": "Coverage status. satisfied = verified/attested as required; missing = a required step that did not run (denetci blocks); failed = ran but the identity+content gate rejected its artifact." },
            "observed_mcp":       { "type": "array", "items": { "type": "string", "minLength": 1 }, "description": "MCP/native tool ids actually observed for this step (e.g. 'mcp__gsc__search_analytics', 'sf_load_crawl'), from events.jsonl source.mcp_tool — feeds the observed-subset-of-declared reconciliation (spec section 4 lint #2)." },
            "input_count":        { "type": "integer", "minimum": 0, "description": "Rows/items the step's transform received from the raw artifact (denominator for the silent-skip ratio gate, spec section 7 1b)." },
            "scored_count":       { "type": "integer", "minimum": 0, "description": "Rows/items the transform actually committed (numerator). A high silent-skip ratio HARD-FAILS the step in 1b." }
          }
        }
      },
      "required_satisfied": { "type": "boolean", "description": "True iff every required (code_verified) step reached status=satisfied. The denetci's core non-start gate." },
      "verdict": { "type": "string", "enum": ["pass", "incomplete", "paused", "failed"], "description": "Run-level coverage verdict the denetci keys on: pass (all required satisfied) | incomplete (a required step missing -> block + Turkish fix command) | paused (an external dependency failed, failure_reason.external=true -> allow turn-end, flag) | failed (an internal gate rejection)." },
      "created_at": { "type": "string", "format": "date-time", "description": "UTC ISO 8601 when the coverage record was first written. Optional." },
      "updated_at": { "type": "string", "format": "date-time", "description": "UTC ISO 8601 updated on every coverage write. Optional." }
    }
  }

SPEC — schemas/workflow-run.schema.json: add ONE property to EACH of the two failure_reason objects (the
top-level one ~150-172 AND the retry_history.items.failure_reason mirror ~211-224). Both keep
`additionalProperties:false`, so the property must be declared in both or a retried external failure fails
validation. Add, after `step_index` (or anywhere in properties):
      "external": {
        "type": "boolean",
        "description": "Additive discriminator (spec D4): true iff this failure was caused by an EXTERNAL
          dependency (GSC/DFS outage, quota, network) rather than an internal logic bug. The denetci
          (batch 2c) maps an external failure onto the existing `paused` state + a RED report and ALLOWS
          turn-end, instead of blocking to force completion. Absent => false (internal). Reuses `paused` —
          NO new `blocked` state, NO new failure codes."
      }
  Do NOT change `required`, the `code` enum, the allOf blocks, or anything else. `external` is OPTIONAL.

SPEC — scripts/state/workflow_runner.py `fail()`: add a keyword-only `external: bool = False` parameter
(place it among the existing keyword-only params, e.g. after `error_details`). After building
`failure = {"code": code, "message": message}` and the optional `step_index`, add:
      if external:
          failure["external"] = True
  i.e. only include the key when True, so EVERY existing `fail()` call and its persisted JSON stay
  BYTE-IDENTICAL (default path unchanged). Change nothing else in the function or module. Do not thread
  `external` into pause()/reject()/retry() — that is 2c's concern; 1a only needs fail() to be able to write it.

TDD — write these FIRST (RED), watch fail, then implement (GREEN):
  tests/schemas/test_coverage_schema.py (mirror test_instance_validation.py's Draft7Validator usage):
    1. A fully-populated valid record (run_id matching the pattern; 2 steps, one code_verified/satisfied with
       observed_mcp + input_count/scored_count, one model_attested/running; required_satisfied:true;
       verdict:"pass"; schema_version "1.0") validates with ZERO errors.
    2. A minimal record {run_id, steps:[], required_satisfied:false, verdict:"incomplete"} validates.
    3. Invalid: a step with verification_class:"guessed" -> validation error.
    4. Invalid: verdict:"green" (not in enum) -> validation error.
    5. Invalid: an unknown top-level key (additionalProperties) -> validation error.
    6. Invalid: run_id "not-a-run-id" (fails the pattern) -> validation error.
  tests/scripts/test_workflow_runner.py (ADD; keep ALL existing green):
    7. Create a run, request_approval is not needed — drive it running->failed via fail(..., external=True);
       re-read the run JSON: failure_reason.external is True AND the file still validates against the schema.
    8. fail(...) WITHOUT external (default): the persisted failure_reason has NO "external" key (assert
       "external" not in re_read.data["failure_reason"]) — proves the default path is byte-identical.
    9. Confirm `paused` reuse for external-failure-allow-end (no code change, just a contract assertion):
       assert ("running","paused") in workflow_runner._ALLOWED_TRANSITIONS and
       ("paused","running") in workflow_runner._ALLOWED_TRANSITIONS; and drive a run running->pause()->paused
       (paused_at set) -> resume()->running to prove the round-trip the denetci will rely on.
  Use tmp_path / workspace_root for all run-state tests exactly as the existing test_workflow_runner.py does;
  never write to the real workspace.

METHOD:
  1. Baseline pytest (record N ~1789).
  2. Write the two test files' new cases (RED). Run them, watch the relevant ones fail.
  3. Author coverage.schema.json; add `external` to BOTH failure_reason copies; add the fail() kwarg (GREEN).
  4. Apply the 2 D10 count-guard bumps (test assert 21->22 + rename helper/docstring; marketplace "22 schemas"
     -> "23 schemas").
  5. Sanity-check every schema parses: `python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('schemas/*.json')]"`.
  6. Re-run the FULL suite; confirm passed >= N and 0 failed.
  7. @code-reviewer + @verifier (inline, since Agent tools are disabled); address what they flag.

DURUR (stop + report, do not work around):
  - Adding `external` to the schema breaks an existing workflow-run test you did not expect (cause outside
    this batch) — report it rather than weakening the schema.
  - The marketplace.json schema count is NOT the literal "22 schemas" you expected (e.g. it already says 23,
    or the count test computes differently) — STOP and report the actual numbers; do not guess.
  - Any existing test regresses for a reason rooted outside this batch's files.
  - Placing the coverage schema would require a new validator/registration step beyond dropping the file in
    schemas/ — report it (the manager expects the existing glob-based validation to pick it up automatically).

REPORT (print verbatim when DONE — the manager needs it):
  - Baseline N and final pytest line (passed/skipped/failed).
  - Files created/edited (exact paths) + how many new tests you added.
  - The coverage schema's required[] + the verdict + verification_class + step-status enums you froze (so the
    manager confirms the contract).
  - Proof that fail(external=True) persists failure_reason.external=true AND that the default fail() path is
    byte-identical (no "external" key) — quote the two assertions.
  - Confirmation that `paused` reuse is proven (the two transition assertions + the round-trip test).
  - "D10 count-guard bumps:" the BEFORE/AFTER of the draft-consistency assert and the marketplace "N schemas"
    substring (manager will re-verify these against the filesystem count).
  - Confirmation you did NOT touch events.schema.json, plugin.json, or any consumer (run_step/router/denetci
    do not exist yet).
  - Any DURUR hit, any out-of-scope need you noticed, any assumption you made.
```
