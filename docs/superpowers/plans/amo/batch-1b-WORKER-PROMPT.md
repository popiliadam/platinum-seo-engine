# AMO Batch 1b — Orchestrator Machinery (WORKER PROMPT)

> **Manager note (not part of the prompt):** Batch 1a froze the schemas (`7c8d66d`). This batch builds the
> **greenfield orchestrator machinery** that those schemas describe — the verified-commit + coverage pipeline —
> WITHOUT touching any existing skill. The manager deliberately SPLIT the spec's monolithic 1b: this is 1b
> (machinery: runner + committer + identity/content gate + coverage writer + e2e stub harness), and the risky
> part — relocating the 3 reference skills' master.xlsx writes out of SKILL.md prose — is isolated to a later
> batch 1b2, AFTER this machinery is proven green. Everything here is new files under `scripts/orchestration/`
> + `tests/orchestration/`, so it is file-disjoint from batch 1c (intent router) and can run in a parallel
> window. It adds NO command/schema/hook → NO D10 count-guard bump. Paste the block below into a fresh Claude
> Code session (Opus 4.8, 1M context) rooted at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 1b of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and
print the REPORT (the manager reviews + commits).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N is ~1803) BEFORE any change. You MUST END green with
  passed strictly >= N (your new tests add to it).
- TDD: write the FAILING test first, watch it fail, then implement until green. Never fake red.
- House style: immutability (build NEW objects, never mutate inputs/args; frozen dataclasses where natural);
  no print/console debug left in shipped code; no hardcoded secrets; small focused functions (<50 lines);
  files 200-400 lines normal. Pass `now`/timestamps IN as args (pure, testable) — never call datetime.now()
  deep inside logic.
- Scope-lock: create/modify ONLY the files named in SCOPE below. This batch is ALL-GREENFIELD: every file
  is NEW under scripts/orchestration/ or tests/orchestration/. You must NOT edit any existing skill, schema,
  command, hook, or manifest. If a fix seems to need an existing file, STOP and report it.

WHY THIS BATCH EXISTS (read carefully):
AMO's orchestrator (Path A: hard-coded ordered Python sequences, NO DAG engine) runs a workflow as: for each
step, the MODEL makes the MCP call and drops a raw artifact at an ORCHESTRATOR-DICTATED path; then CODE
verifies that artifact's identity+content+freshness, runs the pure transform, commits the rows through ONE
serialized committer (idempotent), and records a coverage entry. Hooks/code CANNOT make MCP calls (only the
model can) — so the spine's job is to VERIFY each step's OUTPUT, not to call tools. This batch builds that
CODE spine as isolated, unit-testable modules, proven by an end-to-end STUB harness that feeds canned raw
artifacts (correct / stale / wrong-project / truncated / missing) and asserts the gate verdict + coverage —
WITHOUT a live model or MCP. The 3 real reference skills get wired to this committer in batch 1b2 (not here).

CONFIRMED FACTS (verified by the manager 2026-06-05 — do not re-derive):
- Batch 1a froze `schemas/coverage.schema.json` (the coverage record) — you WRITE records in that exact shape:
  required [run_id, steps, required_satisfied, verdict]; per-step required [name, verification_class, status];
  verification_class enum [code_verified, model_attested]; step status enum
  [pending, running, satisfied, missing, failed, skipped]; verdict enum [pass, incomplete, paused, failed];
  optional per-step observed_mcp[]/input_count/scored_count; optional record project_slug/engine_version/
  created_at/updated_at/schema_version. run_id pattern ^[a-z][a-z0-9-]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{4}$.
  additionalProperties:false at BOTH record + step level → your builders must emit ONLY declared keys.
- The committer wraps `scripts/excel/transaction.replace(workbook_path, sheet, rows, project_slug, *,
  schema_path=None, state_root=None, writer=None, allow_extra=False, acquire_blocking=False) -> WriteResult`.
  `replace` is IDEMPOTENT: it clears the sheet's data block (from the schema's data_start_row down) then
  writes `rows`, preserving the header block — so re-running the same step never duplicates rows (this is the
  "idempotent resume keyed on run_id/window" the spec wants; whole-block replace IS the idempotency for a
  snapshot workflow). Use `replace`, NOT `append`. `WriteResult` is a dataclass with fields
  {workbook_path, sheet, rows_affected, backup_path, event_id}; `rows_affected` is your scored_count.
- Reuse the atomic-write helper pattern from `scripts/state/session_binding.py::_atomic_write_json(target,
  payload)` (tempfile in same dir -> fsync -> os.replace -> parent dir fsync) for the coverage record. A
  coverage record is a MUTABLE marker file (rewritten as the run progresses), so os.replace is CORRECT here
  (this is NOT an events.jsonl-style append-only log — do not confuse the two). You may import that helper if
  it is importable, else mirror it; do not invent a subtly different one.
- `scripts/orchestration/` and `tests/orchestration/` do NOT exist yet (greenfield). Check whether sibling
  packages use `__init__.py` (e.g. `scripts/state/__init__.py`, `tests/state/__init__.py`); match that
  convention (add `__init__.py` if siblings have them so `scripts.orchestration.*` imports resolve).
- conftest.py exists at repo root AND tests/conftest.py. Place tests under tests/orchestration/ and follow
  the import style of tests/scripts/test_workflow_runner.py / tests/state/test_session_binding.py.
- Adding only scripts + tests trips NO count-guard (those count skills/commands/schemas/MCP/hooks/rules).
  Confirm with the baseline diff; do NOT touch any manifest.

ORIENT FIRST (read, do not change):
- `schemas/coverage.schema.json` (the shape you emit) + `tests/schemas/test_coverage_schema.py` (the lock you
  must satisfy — your records must validate against the same schema with Draft7Validator).
- `scripts/excel/transaction.py` — `replace()` (~786-814), `class WriteResult` (~185), and ONE existing
  transaction test (search tests/ for how a tmp master.xlsx + master-excel schema fixture is built) so your
  committer test can write to a real throwaway workbook.
- `scripts/state/session_binding.py::_atomic_write_json` (~101-121) — the atomic JSON write to reuse.
- `scripts/state/workflow_runner.py` — only to match house style (frozen dataclasses, typed errors, pure
  helpers). You do NOT call the runner here; coverage is a separate artifact.

SCOPE — create ONLY these (all NEW):
  NEW  scripts/orchestration/__init__.py        (empty/package marker if siblings use one)
  NEW  scripts/orchestration/verify.py          (raw-drop identity+content+freshness gate)
  NEW  scripts/orchestration/committer.py       (thin idempotent commit wrapper over transaction.replace)
  NEW  scripts/orchestration/coverage.py        (coverage-record builders + validate + atomic write)
  NEW  scripts/orchestration/run_step.py        (the spine: verify -> transform -> commit -> coverage step)
  NEW  tests/orchestration/__init__.py          (if siblings use one)
  NEW  tests/orchestration/test_verify.py
  NEW  tests/orchestration/test_committer.py
  NEW  tests/orchestration/test_coverage.py
  NEW  tests/orchestration/test_run_step_e2e_stub.py   (the e2e stub harness — the headline deliverable)

SPEC — the RAW-DROP provenance contract (you DEFINE it here; the model conforms in 1b2). A raw drop is a JSON
file the orchestrator dictates the PATH of (path embeds run_id, so a misnamed/wrong-project drop simply isn't
where the gate looks). Shape:
    { "provenance": { "run_id", "slug", "site_url", "window", "tool", "fetched_at" (ISO-8601 str),
                      "declared_count" (int) },
      "rows": [ {...}, ... ] }

SPEC — scripts/orchestration/verify.py:
- A frozen `VerifyResult` dataclass: {ok: bool, reason: str | None, rows: list[dict] | None, input_count: int|None}.
  reason is a short stable code when ok is False, one of: "missing_file", "parse_error", "no_provenance",
  "run_id_mismatch", "slug_mismatch", "site_url_mismatch", "window_mismatch", "tool_mismatch", "stale",
  "truncated". (Stable strings — the denetçi/coverage will key on them.)
- `verify_raw_drop(raw_path, *, expected_run_id, expected_slug, now_epoch, expected_site_url=None,
    expected_window=None, expected_tool=None, max_age_seconds=86400) -> VerifyResult`:
    * missing file -> ok=False reason="missing_file".
    * unparseable / not an object / missing "provenance" or "rows" -> "parse_error"/"no_provenance".
    * provenance.run_id != expected_run_id -> "run_id_mismatch"; slug mismatch -> "slug_mismatch";
      (only when the corresponding expected_* is provided) site_url/window/tool mismatch -> the matching code.
    * FRESHNESS: stale if (now_epoch - file mtime) > max_age_seconds OR provenance.fetched_at parses to a time
      older than max_age_seconds before now_epoch -> "stale". (Pass now_epoch in; derive file mtime via
      os.path.getmtime — accept an injectable mtime for testability OR set the tmp file's mtime in the test.)
    * TRUNCATION: len(rows) != provenance.declared_count -> "truncated".
    * else ok=True, rows=the rows list, input_count=len(rows).
  HARD-FAIL means RETURN a not-ok VerifyResult (never raise for an expected bad drop; reserve exceptions for
  programmer error). Build a new result; never mutate inputs.
- `silent_skip_exceeds(input_count, scored_count, *, max_ratio=0.5) -> bool`: True iff input_count>0 and
  (input_count - scored_count)/input_count > max_ratio. (The high-silent-skip gate from spec §7-1b.)

SPEC — scripts/orchestration/committer.py:
- `commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None, state_root=None,
    writer="orchestrator") -> WriteResult`: call `transaction.replace(workbook_path, sheet, rows,
    project_slug, schema_path=schema_path, state_root=state_root, writer=writer)` and return its WriteResult.
    Idempotent by construction (replace clears+rewrites). run_id is accepted for the caller's provenance/log
    intent and to make the signature self-documenting; you need not thread it into transaction (replace has no
    run_id param) — but DO include it in any log/return context if you add one. Keep this module thin (<40 lines
    of logic); it exists so the orchestrator owns ONE commit path and 1b2 can point skills at it. Document WHY
    replace-not-append (idempotent resume; also fixes the known gsc snapshot-duplicate bug, handled in 1b2).

SPEC — scripts/orchestration/coverage.py:
- `build_step(name, verification_class, status, *, observed_mcp=None, input_count=None, scored_count=None)
    -> dict`: return ONLY declared keys (omit optional ones when None/empty so additionalProperties:false holds
    and the shape stays minimal). Validate enums defensively (raise ValueError on an unknown verification_class
    or status — fail loud, don't emit an invalid record).
- `build_record(*, run_id, steps, required_satisfied, verdict, project_slug=None, engine_version=None,
    created_at=None, updated_at=None, schema_version="1.0") -> dict`: assemble the record; include optionals
    only when provided.
- `coverage_path(workspace_root, project_slug, run_id) -> Path` = workspace_root/"projects"/project_slug/
    "_state"/"coverage"/(run_id + ".json").
- `write_coverage(record, *, workspace_root, project_slug, run_id, schema_path=None) -> Path`: VALIDATE the
    record against schemas/coverage.schema.json with Draft7Validator (raise a clear error listing the
    validation messages if invalid — never write an invalid record); create the coverage dir; atomic-write via
    the session_binding pattern; return the path.
- Optional helper `derive_verdict(steps) -> tuple[bool, str]`: required_satisfied = every code_verified step
    has status "satisfied"; verdict = "pass" if required_satisfied and no step "failed"; "incomplete" if any
    required step is "missing"; "failed" if any step "failed". (paused is set by the denetçi in 2c, not here.)

SPEC — scripts/orchestration/run_step.py (the spine that composes the above; the committer is INJECTABLE so
the e2e stub harness need not build a real workbook):
- A frozen `StepSpec` dataclass: {name, raw_path, sheet, transform (Callable[[list[dict]], list[dict]]),
    verification_class="code_verified", required=True, expected_site_url=None, expected_window=None,
    expected_tool=None, observed_mcp=()}.
- `run_step(spec, *, run_id, project_slug, workspace_root, workbook_path, now_epoch, max_age_seconds=86400,
    schema_path=None, commit_fn=committer.commit) -> dict` returns the COVERAGE STEP dict:
    1. vr = verify_raw_drop(spec.raw_path, expected_run_id=run_id, expected_slug=project_slug,
       now_epoch=now_epoch, expected_site_url=spec.expected_site_url, expected_window=spec.expected_window,
       expected_tool=spec.expected_tool, max_age_seconds=max_age_seconds).
    2. if not vr.ok -> status = "missing" if vr.reason=="missing_file" else "failed";
       return build_step(spec.name, spec.verification_class, status, observed_mcp=list(spec.observed_mcp)).
    3. rows_out = spec.transform(vr.rows)  (pure; never mutate vr.rows).
    4. result = commit_fn(workbook_path, spec.sheet, rows_out, run_id=run_id, project_slug=project_slug,
       schema_path=schema_path); scored = result.rows_affected.
    5. status = "failed" if silent_skip_exceeds(vr.input_count, scored) else "satisfied".
    6. return build_step(spec.name, spec.verification_class, status, observed_mcp=list(spec.observed_mcp),
       input_count=vr.input_count, scored_count=scored).
- `run_sequence(specs, *, run_id, project_slug, workspace_root, workbook_path, now_epoch, write=True, ...)
    -> dict`: run each spec via run_step, collect step dicts, derive (required_satisfied, verdict), build the
    record (project_slug set), and if write -> write_coverage(...). Return the record. A failing/missing step
    does NOT abort the loop (record every step), but the verdict reflects it.

TDD — write FIRST (RED), watch fail, then implement (GREEN):
  test_verify.py: a valid drop passes (ok, input_count); each failure mode returns the right reason code —
    missing_file, parse_error, run_id_mismatch, slug_mismatch, site_url_mismatch, window_mismatch,
    tool_mismatch, stale (old mtime AND/OR old fetched_at), truncated (declared_count != len rows).
    silent_skip_exceeds: 100/40 -> True (0.6>0.5), 100/60 -> False, 0/0 -> False.
  test_committer.py: build a throwaway tmp master.xlsx (mirror an existing transaction test's fixture) +
    commit rows via committer.commit -> rows land; commit the SAME run twice -> still N rows (idempotent, no
    duplication), proving replace semantics. (If standing up a real workbook is heavy, keep this to ONE
    focused idempotency test — the e2e harness covers the rest with a fake commit_fn.)
  test_coverage.py: build_step/build_record emit schema-valid records (validate vs coverage.schema.json,
    ZERO errors); an unknown status/verification_class raises; write_coverage writes to
    projects/{slug}/_state/coverage/{run_id}.json atomically and the file validates; an invalid record raises
    and writes NOTHING. derive_verdict: all-satisfied->("pass"); a missing required step->("incomplete");
    a failed step->("failed").
  test_run_step_e2e_stub.py (THE HEADLINE): a fixture that drops canned raw JSONs into a tmp dir and runs
    run_step with a FAKE commit_fn (returns a WriteResult-like with rows_affected=len(rows)) so no real
    workbook is needed. Assert per scenario:
      * correct      -> step status "satisfied", input_count/scored_count set.
      * stale        -> "failed" (reason stale).
      * wrong-project (slug mismatch) -> "failed".
      * truncated    -> "failed".
      * missing file -> "missing".
      * a transform that drops >50% of rows on a correct drop -> "failed" (silent-skip gate).
    Then run_sequence over [correct, missing] -> verdict "incomplete", required_satisfied False, and the
    written coverage record validates against coverage.schema.json; over [correct] -> verdict "pass".
  Use tmp_path everywhere; never touch the real workspace. Set file mtimes explicitly (os.utime) for the
  stale test, or inject mtime, so the freshness test is deterministic.

METHOD:
  1. Baseline pytest (record N ~1803).
  2. Write the test files (RED). Run, watch fail for the RIGHT reasons (missing module / missing function).
  3. Implement verify.py, committer.py, coverage.py, run_step.py until GREEN.
  4. Sanity: `python3 -c "import scripts.orchestration.run_step, scripts.orchestration.coverage, scripts.orchestration.verify, scripts.orchestration.committer"`.
  5. Re-run FULL suite; confirm passed >= N and 0 failed. Confirm `git status --short` shows ONLY new files
     under scripts/orchestration/ + tests/orchestration/ (no manifest/schema/skill touched).
  6. @code-reviewer + @verifier (inline); address findings.

DURUR (stop + report, do not work around):
  - Standing up a real tmp master.xlsx for the committer test needs machinery beyond mirroring an existing
    transaction test — report it (and keep the committer idempotency proof minimal).
  - transaction.replace's actual signature/behavior differs from the CONFIRMED FACTS above — STOP and report
    the real signature (do not guess).
  - You find you must edit an existing skill/schema/manifest to make a test pass — that is batch 1b2 / out of
    scope; STOP and report.

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line (passed/skipped/failed).
  - Files created (paths) + new test count.
  - The verify reason-code set you implemented + the silent-skip rule.
  - Proof of committer idempotency (the twice-commit test → still N rows).
  - Proof the e2e stub harness covers all 5 raw-drop scenarios + the silent-skip case, with the asserted
    step status for each, AND that the written coverage record validates against coverage.schema.json.
  - Confirmation that run_step's committer is INJECTABLE (commit_fn) and the stub harness used a fake (no real
    workbook), while test_committer.py exercised the REAL transaction.replace wrap.
  - Confirmation `git status --short` shows ONLY scripts/orchestration/** + tests/orchestration/** (nothing
    else; no manifest/schema bump).
  - Any DURUR hit / assumption / out-of-scope need noticed (e.g. anything you think belongs in 1b2 or 1d).
```
