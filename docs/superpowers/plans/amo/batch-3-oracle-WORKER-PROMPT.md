# AMO Batch 3-oracle — Generalize the correctness oracle to every workflow (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 3, tracked follow-up from 3b. HEAD `9f3c693`, suite **2118 / 0**.
> 3b shipped `audit` with 3 of 4 steps `model_attested` (their silent-skip is advisory, so the **independent
> correctness oracle IS their ≤5% backstop**) — but the oracle (`scripts/reporting/orchestration_metrics.py`,
> batch 2d) is MONTHLY-specific and SKIPS model_attested steps, so audit is currently un-backstopped. This batch
> makes the oracle workflow-agnostic and reconciles attested sheet-writers too. **Focused, READ-ONLY, 2 files**
> (no spine/schema/driver/command change). Sized for a max-effort Opus-4.8 1M worker — full module inlined below.
> Paste the fenced block into a fresh Claude Code session at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 3-oracle of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 2118 at HEAD 9f3c693; a single MCP-availability-gated test
  may make it read 2117/8 — the floor is the passed+skipped TOTAL, which must not drop) BEFORE any change. END
  green with passed strictly >= your measured N and 0 failed. EVERY existing test in
  tests/reporting/test_orchestration_metrics.py MUST stay green (except the ONE documented migration below).
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (build new objects, never mutate inputs); no leftover debug prints; small functions
  (<50 lines); files 200-400 lines; clear names.
- Scope-lock: modify ONLY the two files in SCOPE. Anything else → STOP + report.
- The 1b spine is FROZEN: you may IMPORT scripts/orchestration/{coverage,verify} and the two workflow modules,
  but must NOT edit them. In particular do NOT add a field to coverage.build_record / coverage.schema.json
  (that would edit the spine + the frozen 1a contract) — resolve the workflow in the ORACLE instead (see SPEC).

WHY THIS BATCH EXISTS (read carefully):
The oracle (scripts/reporting/orchestration_metrics.py, batch 2d) is the AMO INDEPENDENT correctness auditor: for
each run it RE-DERIVES the truth from on-disk artifacts (the raw provenance drop, the transform output, the
committed master.xlsx) and reports whether they reconcile — WITHOUT trusting the coverage record's self-reported
verdict/scored_count. Headline = the structured-error rate + ``fake_green`` (verdict==pass but committed data
does NOT reconcile). It is the ONLY trustworthy source of the spec's "<=5% structured error" number.

Batch 3b shipped the `audit` workflow with 3 of 4 steps `model_attested` (tech_audit, schema_audit,
cannibalization ANALYZE/aggregate, so their silent-skip COUNT gate is advisory). For those steps the oracle is
their ONLY independent backstop — yet the oracle today (a) is hard-wired to the `monthly` workflow's STEPS /
paths, and (b) reconciles ONLY `code_verified` steps, so it SKIPS every audit attested step and would use
monthly's step names for an audit run (matching nothing). Result: audit runs are currently un-audited by the
oracle. This batch generalizes the oracle to reconcile ANY workflow's runs and to reconcile attested
SHEET-WRITING steps (the audit ones) — giving them their independent ≤5% backstop.

CONFIRMED FACTS (verified against the code 2026-06-08 — do NOT re-derive):
- The oracle is READ-ONLY (opens artifacts + the workbook openpyxl read_only; writes NO state; adds no
  hook/schema/command). KEEP it read-only. **No code outside its own test imports it** (grep-confirmed) — so the
  blast radius is the module + its test only.
- The THREE monthly-coupling points to change (everything else stays):
  1. Imports (lines ~36-42): `from scripts.orchestration.workflows.monthly_maintenance import STEPS, inbox_path,
     output_path`. ⇒ generalize: import BOTH workflows' STEPS into a registry; stop depending on monthly's
     `output_path` (it is keyed by SHEET — wrong for audit, see below).
  2. `reconcile_step(...)` builds the transform-output path with `output_path(workspace, run_id, slug, SHEET)` —
     i.e. `{sheet}.json`. AUDIT's CLI for `schema_audit` writes `schema_audit.json` while its sheet is `schema`
     (the 1d.1 trap 3b fixed with an explicit per-step `output_file`). ⇒ the oracle must read the output file by
     the step's `output_file`, NOT `{sheet}.json`.
  3. `reconcile_run(...)` (a) defaults `steps=STEPS` (monthly's), and (b) reconciles a step ONLY when its
     coverage `verification_class == "code_verified"` (lines ~291-295) — so it SKIPS audit's attested steps. ⇒
     resolve the run's workflow + reconcile every step that is IN that workflow's STEPS (drop the
     code_verified-only filter — see the "why this is correct" note).
- **The R1-R5 reconcile logic is ALREADY correct for attested steps** — do NOT change it:
    R1 identity (run_id/slug), R2 truncated (declared_count==len(raw.rows)), R3 output present,
    R4 committed_count == len(output_rows), R5 scored_count == committed_count, plus an ADVISORY
    `high_silent_skip` (reuses verify.silent_skip_exceeds) that NEVER affects `independent_ok`. For an attested
    audit step the committer still writes EXACTLY the transform-output rows, so R4 (committed==output) + R5
    (scored==committed) hold and ARE the right backstop; only the raw→committed drop is advisory — which the
    oracle already treats as advisory. So reconciling an attested step needs NO new reconcile math; it only needs
    the step to no longer be filtered out + the output path keyed by output_file.
- Why dropping the `code_verified` filter is SAFE for monthly: monthly's only attested step is `monthly_report`,
  and it is NOT in `monthly_maintenance.STEPS` (it is added separately in `run()` and writes NO sheet —
  `master.xlsx#none`). The oracle iterates a workflow's STEPS, and monthly_report is not there, so it is STILL
  not reconciled. The generalized contract is "reconcile every step that is in the workflow's STEPS" (every STEPS
  entry commits a sheet, by construction) — which equals the old behavior for monthly and ADDS audit's attested
  sheet-writers.
- STEPS shapes: monthly entries are `{name, sheet, writer, site_url, window, tool}` (NO output_file → the output
  file is `{sheet}.json`). audit entries are `{name, sheet, output_file, writer, tool, site_url,
  verification_class}` (EXPLICIT output_file). ⇒ compute `output_file = entry.get("output_file") or
  (entry["sheet"] + ".json")` — correct for BOTH, touching neither workflow module.
- Workflow step-name sets are DISJOINT: monthly = {gsc_pull, quick_wins, content_decay};
  audit = {tech_audit, schema_audit, on_page_audit, cannibalization}. ⇒ a coverage record's workflow can be
  resolved unambiguously by which workflow's STEPS-names are ⊆ the record's step names. (This keeps the spine +
  coverage schema FROZEN — do NOT add a `workflow` field to coverage. Document the disjoint-names assumption.)
- The inbox path convention is IDENTICAL across workflows
  (`projects/{slug}/_state/inbox/{run_id}/{step}.json`); only the transform-output FILENAME differs
  (`{sheet}.json` vs explicit `output_file`). The transform dir is
  `projects/{slug}/_state/transform/{run_id}/`.
- The existing test `tests/reporting/test_orchestration_metrics.py::test_reconcile_run_skips_model_attested_steps`
  (~line 380) pins the OLD behavior. It MUST be migrated (1c/1b2-style) to the NEW contract: a step IN the
  workflow's STEPS is reconciled regardless of verification_class; a coverage step NOT in STEPS (e.g. a synthetic
  report step) is skipped. Preserve/strengthen — never weaken.

ORIENT FIRST (read in full, do not change yet):
- scripts/reporting/orchestration_metrics.py IN FULL (the module you generalize — note the 3 coupling points +
  that R1-R5 + high_silent_skip are already attested-correct).
- scripts/orchestration/workflows/monthly_maintenance.py (STEPS + inbox_path + output_path) and
  scripts/orchestration/workflows/audit_suite.py (STEPS with output_file + verification_class) — the two
  registry members.
- scripts/orchestration/coverage.py (coverage_path + the coverage record/step shape the oracle reads:
  steps[].{name, verification_class, status, scored_count}).
- tests/reporting/test_orchestration_metrics.py IN FULL — keep every test green except the ONE migration; reuse
  its fixtures (how it seeds a raw drop, a transform output, a committed workbook, a coverage record).

SCOPE — modify ONLY these two files:
  EDIT scripts/reporting/orchestration_metrics.py     (workflow-agnostic resolve + output_file + reconcile attested)
  EDIT tests/reporting/test_orchestration_metrics.py  (migrate the 1 test + ADD audit + mixed-workflow cases)

SPEC — scripts/reporting/orchestration_metrics.py:
  1. Registry of workflows (import both STEPS):
       from scripts.orchestration.workflows import monthly_maintenance, audit_suite
       _WORKFLOWS = (("monthly", monthly_maintenance.STEPS), ("audit", audit_suite.STEPS))
     (a tuple/dict — keep it a module constant so a 3rd workflow is a one-line add).
  2. `def _resolve_workflow_steps(coverage_record) -> tuple[str, Sequence[dict]] | None`: the (name, STEPS) whose
     STEPS-names are ALL present in the record's step names (subset match over the disjoint name sets); None if no
     workflow matches (an unknown/legacy record → the run is reported but counted as unresolvable, NOT silently
     passed — see step 5). Pure; reads only the record's `steps[].name`.
  3. `def _step_output_file(entry) -> str`: `entry.get("output_file") or (entry["sheet"] + ".json")`. Use this +
     a workflow-agnostic transform path (`.../_state/transform/{run_id}/{output_file}`) in reconcile_step. Keep
     inbox via the shared convention (`.../_state/inbox/{run_id}/{step}.json`) — define a local `_inbox_path` /
     `_output_file_path` in the oracle (do NOT import monthly's `output_path`, which is sheet-keyed). The oracle
     independently knowing where artifacts live is correct for an INDEPENDENT auditor.
  4. `reconcile_step(...)`: add an `output_file: str` parameter; build the output path from it (not from sheet).
     Everything else (R1-R5, advisory high_silent_skip) UNCHANGED.
  5. `reconcile_run(...)`: resolve the workflow via `_resolve_workflow_steps(coverage_record)`; if None →
     `independent_verdict = "workbook_absent"` is WRONG (it is not about the workbook) → return a clear
     `independent_verdict = "unresolved_workflow"` (a NEW stable verdict, reported + excluded from the error-rate
     denominator like workbook_absent, never counted as reconciled). If resolved, iterate that workflow's STEPS;
     for each entry with a matching coverage step, reconcile it (DROP the `verification_class == "code_verified"`
     filter — reconcile every STEPS entry; they all commit a sheet). Keep the rest (fake_green etc.). Preserve the
     `steps: Sequence[dict] | None = None` parameter for back-compat callers/tests, but when None resolve from the
     record (do NOT default to monthly's STEPS).
  6. `structured_error_rate(...)`: add `unresolved_workflow` to the surfaced counts (alongside workbook_absent);
     `reconcilable` still = reconciled + mismatched (unresolved + absent excluded). NEVER silently drop them.
  7. `oracle_report(...)`: unchanged shape, but now each run's workflow is auto-resolved → a slug with BOTH
     monthly and audit runs reconciles each correctly. Keep the CLI READ-ONLY + exit 0.
  Keep functions <50 lines; keep the module's READ-ONLY + never-crash discipline (degrade to None/absent, never
  raise for an expected-missing artifact).

SPEC — tests/reporting/test_orchestration_metrics.py:
  - MIGRATE `test_reconcile_run_skips_model_attested_steps` → assert the NEW contract: an attested step that IS in
    the workflow's STEPS (an audit step) IS reconciled; a coverage step NOT in any STEPS (a synthetic report step)
    is skipped. (Rename to match, e.g. `test_reconcile_run_reconciles_attested_steps_in_steps_table`.)
  - ADD (reuse existing fixtures; seed audit-shaped artifacts):
      * an `audit` run (4 steps, 3 attested) where every committed sheet == its transform output → reconciled;
        verify the attested steps appear in the result `steps` (not skipped).
      * an audit attested step (e.g. tech_audit) whose committed rows != its output → `mismatch`; with coverage
        verdict=="pass" → `fake_green` True (the backstop FIRES on an attested step — the whole point).
      * the schema_audit path case: the oracle reads `schema_audit.json` (output_file), NOT `schema.json`
        (sheet) — a fixture where `schema.json` is absent/garbage but `schema_audit.json` is correct still
        reconciles.
      * workflow resolution: a monthly record resolves to monthly STEPS; an audit record to audit STEPS; a record
        whose steps match neither → `unresolved_workflow` (reported, excluded from error_rate denominator).
      * `oracle_report` over a slug holding BOTH a monthly run and an audit run → each reconciled under its own
        workflow; metrics aggregate both.

TDD ORDER:
  1. Baseline pytest (record N).
  2. Write the NEW/migrated tests FIRST (RED — the oracle still skips attested + uses sheet-keyed output). Watch
     them fail for the RIGHT reason (attested step skipped / wrong output path / unresolved).
  3. Implement the oracle changes → GREEN.
  4. Full suite: passed >= N, 0 failed. Re-run tests/reporting/test_orchestration_metrics.py +
     tests/orchestration/ explicitly (the workflow modules you import must still pass).
  5. Self-review (@code-reviewer + @verifier, inline): oracle still READ-ONLY (grep: zero state writes — no
     open(...,'w'), no os.replace, no transaction); R1-R5 math UNCHANGED (quote it); attested steps reconciled
     (quote the dropped filter); output keyed by output_file (quote the schema_audit case); spine + coverage
     schema + both workflow modules UNTOUCHED (git status); the migrated test strengthened not weakened;
     immutability; no file outside SCOPE; no D10.

DURUR (stop + report, do not guess):
  - You find you must add a `workflow` field to coverage.build_record / coverage.schema.json to resolve the
    workflow → STOP (that edits the frozen spine + 1a contract; the step-name resolver avoids it — if it is truly
    insufficient, report why).
  - Workflow step names turn out NOT to be disjoint (a real ambiguity in resolution) → STOP + report.
  - A workflow module's STEPS shape differs from CONFIRMED FACTS (e.g. an entry with neither output_file nor
    sheet) → STOP + report.
  - Any existing oracle test (other than the one documented migration) must change to stay green → STOP + report
    (that means a behavior regression you did not intend).
  - Any out-of-scope file needs editing → STOP + report.

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line (passed/skipped/failed) + the test_orchestration_metrics.py count.
  - The generalization: quote `_resolve_workflow_steps` + `_step_output_file`; confirm monthly behavior is
    unchanged (monthly_report still not reconciled — not in STEPS) and audit's 3 attested steps are NOW reconciled.
  - The backstop proof: the test where an attested audit step with committed != output yields `mismatch` +
    `fake_green` (verdict=pass) — i.e. the oracle now catches a fake-green on an attested step.
  - The schema_audit output_file proof (oracle reads schema_audit.json, not schema.json).
  - The mixed-workflow oracle_report proof (monthly + audit under one slug each reconcile correctly).
  - Confirm: oracle still READ-ONLY; R1-R5 unchanged; spine + coverage schema + both workflow modules UNTOUCHED;
    no file outside SCOPE; no D10; the one test migration preserves/strengthens its contract.
  - Any DURUR hit, out-of-scope need, or assumption (e.g. the disjoint-step-names resolution + the new
    `unresolved_workflow` verdict).
```
