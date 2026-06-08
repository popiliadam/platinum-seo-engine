# AMO batch 3-O4 — light-promote: extract the shared DATA-driver (behaviour-preserving)

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note (risk + why low-churn):** this is the one refactor of ALREADY-SHIPPED code — it must be
> 100% behaviour-preserving. The manager pre-mapped the surface: the 3 data-drivers (monthly/audit/setup)
> are ~80% identical; the divergences all reduce to byte-identical via uniform STEPS keys. The KEY de-risker
> (manager-verified): keep each module's PUBLIC API identical via thin re-export wrappers → the shared module
> holds the impl → **ZERO test files change**. content_pipeline (artifact-driver) and the spine stay frozen.

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE batch: a
BEHAVIOUR-PRESERVING refactor that extracts the shared DATA-driver machinery of three workflow modules into
a new shared module. This is a "light promote" (O4): NO new behaviour, NO declarative engine. Follow every
rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here — "Prompt is too long"). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: 2194 passed, 7 skipped, 0 failed. End state MUST be passed >= 2194 and failed == 0.
4. BEHAVIOUR-PRESERVING IS THE WHOLE POINT. Every existing test must stay GREEN **without modifying any test
   file**. The public API of all three modules is preserved by design (re-export wrappers below), so no test
   should need to change. If you find yourself wanting to edit a test, STOP and report — it means a signature
   wasn't preserved. (This is the acceptance gate: the diff is pure refactor.)
5. SCOPE-LOCK. Create/modify ONLY the 4 files in SCOPE. Do NOT touch: any test, content_pipeline.py, the
   spine (run_step.py / committer.py / verify.py / coverage.py / remediation.py), the oracle
   (orchestration_metrics.py), any schema/command/manifest/hook. Anything else → STOP + report.
6. Python discipline: pure functions, immutability, functions < 50 lines, no debug prints, type hints,
   module docstrings. Match the existing house style (read the 3 modules first).
7. This refactor adds NO command/schema/manifest/hook → **no D10 bump, no RUNTIME_HOOK_SCRIPTS entry.**

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (O4 — Path A "light promote", manager-decided)
═══════════════════════════════════════════════════════════════════════════════════════════════
Faz 3 produced 3 DATA-driver workflows (monthly/audit/setup) that share ~80% of their code by copy-paste,
plus a 4th ARTIFACT-driver (content_pipeline) that is structurally different. `new_project_setup` already
reaches into `audit_suite` to import its `_run_one` dispatch (a smelly cross-driver coupling). The earned
move (O4, Path A — NOT a declarative engine): extract the shared DATA-driver into one
`scripts/orchestration/workflow_driver.py` that monthly/audit/setup all use; clean up the cross-import.
`content_pipeline` STAYS separate (it shares only `coverage`). The spine stays FROZEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified — do NOT re-derive; DO re-read the 3 modules + their tests first)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. The 3 data-driver modules (`scripts/orchestration/workflows/{monthly_maintenance,audit_suite,
   new_project_setup}.py`) each currently define, NEARLY IDENTICALLY:
     `Transform` alias · `WorkflowError` · `inbox_path` · `output_path` · `_output_loader` ·
     `_resolve_site_url` · `build_steps` · `run` · `_build_arg_parser` · `main` · module-level `STEPS`.
   audit_suite ALSO defines `_run_attested_step` + `_run_one` (the D15 dispatch); new_project_setup IMPORTS
   `audit_suite._run_one`; monthly has `_code_verified_steps` instead (all its steps are code_verified).

B. The DIVERGENCES (all reduce to byte-identical under uniform STEPS keys — manager-proven):
   • output_path keying: **monthly keys by SHEET** (`output_path(ws,rid,slug,sheet)` → `.../{sheet}.json`);
     **audit + setup key by OUTPUT_FILE** (`.../{output_file}`). The shared canonical
     `output_path(ws,rid,slug,filename)` just joins `.../{filename}`; monthly's wrapper passes
     `f"{sheet}.json"`, audit/setup pass `output_file`. (The oracle test calls monthly's with a SHEET and
     audit's with an OUTPUT_FILE — BOTH signatures MUST be preserved. See fact E.)
   • monthly's STEPS entries lack `output_file` and `verification_class`. ADD them, byte-identically:
     `output_file = f"{sheet}.json"` (= what its sheet-keyed output_path produced) and
     `verification_class = "code_verified"` (= the value monthly hard-coded). Then monthly uses the generic
     `build_steps`. (monthly entries already carry `window`, `site_url: True`, `tool`.)
   • build_steps generic body (identical StepSpec for all 3):
        expected_site_url = site_url if entry["site_url"] else None
        expected_window   = entry.get("window")           # monthly has it; audit/setup -> None
        expected_tool     = entry["tool"]
        observed_mcp      = (entry["tool"],) if entry["tool"] else ()
        verification_class= entry["verification_class"]
        transform         = _output_loader(output_path(ws, rid, slug, entry["output_file"]))
     For monthly (all entries site_url:True, all have window+tool, vc=code_verified) this yields StepSpecs
     byte-identical to today. VERIFY this by asserting the existing monthly tests still pass.
   • `_run_one(spec)` for a code_verified step dispatches to `run_step(spec)` — IDENTICAL to monthly's
     `_code_verified_steps` loop. So monthly can use the shared `_run_one` loop with no behaviour change.
   • completion guard: monthly downgrades `pass→incomplete` iff its REPORT step isn't satisfied; audit/setup
     iff ANY step isn't satisfied. UNIFIED guard = `if verdict=="pass" and not all(s["status"]=="satisfied"
     for s in steps): verdict="incomplete"`. This is byte-equivalent for ALL THREE: when verdict=="pass",
     every code_verified step is already satisfied (else derive_verdict wouldn't say pass), so the only
     possibly-unsatisfied step is monthly's soft report → same downgrade. (Proof holds; assert via tests.)

C. monthly's REPORT step: a trailing `coverage.build_step(REPORT_STEP_NAME, "model_attested",
   "satisfied" if report_exists else "missing", observed_mcp=[])` appended after the data steps. The shared
   `run_workflow` takes `report_step_name: str | None = None` + `report_exists: bool = False` and appends it
   when `report_step_name` is set. audit/setup pass neither.

D. The spine public modules to COMPOSE (import, never edit): `run_step.StepSpec`, `run_step.run_step`,
   `verify.verify_raw_drop`, `committer.commit`, `coverage.{build_step,derive_verdict,build_record,
   write_coverage}`, `remediation.{remediation,render}`. (These are FROZEN — the refactor only MOVES the
   per-workflow duplicate helpers, never the spine.)

E. ⚠️ THE TEST-IMPORT SURFACE TO PRESERVE (manager-greps — these MUST keep working unchanged):
   • `tests/orchestration/test_monthly_maintenance.py`  imports: `STEPS, build_steps, inbox_path,
     output_path, run` + references `monthly_maintenance._output_loader`.
   • `tests/orchestration/test_audit_suite.py`          imports: `STEPS, build_steps, inbox_path,
     output_path, run` + references `audit_suite._output_loader` (and `audit_suite` module).
   • `tests/orchestration/test_new_project_setup.py`    imports: `STEPS, build_steps, inbox_path,
     output_path, run` + references `new_project_setup._output_loader`.
   • `tests/orchestration/test_audit_suite_cli_integration.py`     imports: `STEPS, build_steps, output_path`.
   • `tests/orchestration/test_new_project_setup_cli_integration.py` imports: `STEPS, build_steps, output_path`.
   • `tests/reporting/test_orchestration_metrics.py` imports `monthly_maintenance.{inbox_path, output_path}`
     (output_path called with a **SHEET**) AND `audit_suite` (`.STEPS`, `.output_path` called with an
     **OUTPUT_FILE**). The oracle module itself imports `monthly_maintenance.STEPS` + `audit_suite.STEPS`.
   • `tests/schemas/test_workflow_tool_subset_declared.py` (3-gov-lint2) imports each module's `STEPS`.
   So every module MUST keep exporting: `STEPS`, `build_steps(run_id, slug, ws)` [module-STEPS-bound
   signature], `inbox_path`, `output_path` [monthly SHEET-keyed; audit/setup OUTPUT_FILE-keyed],
   `_output_loader`, `run(...)`, plus `WORKFLOW`/`main`/`_build_arg_parser` for the CLI. `STEPS` MUST remain a
   module-level attribute on each (the oracle + lint2 read `<module>.STEPS`).

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create/modify
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW  `scripts/orchestration/workflow_driver.py`                       (the shared DATA-driver)
2. EDIT `scripts/orchestration/workflows/monthly_maintenance.py`          (thin: STEPS + wrappers)
3. EDIT `scripts/orchestration/workflows/audit_suite.py`                  (thin: STEPS + wrappers)
4. EDIT `scripts/orchestration/workflows/new_project_setup.py`            (thin: STEPS + wrappers)
NOTHING else — no test, no content_pipeline, no spine, no oracle, no schema/command/manifest/hook.

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC — target design
═══════════════════════════════════════════════════════════════════════════════════════════════
`scripts/orchestration/workflow_driver.py` (the shared impl):
  • `Transform`, `WorkflowError`.
  • `inbox_path(workspace_root, run_id, slug, step) -> Path` (moved, identical).
  • `output_path(workspace_root, run_id, slug, filename) -> Path` — canonical, joins `.../{filename}`.
  • `_output_loader(output_file) -> Transform` (moved, identical).
  • `_resolve_site_url(workspace_root, slug) -> str | None` (moved, identical).
  • `build_steps(steps_table, run_id, project_slug, workspace_root) -> list[StepSpec]` — the generic body
    from fact B (takes the STEPS tuple as its FIRST arg).
  • `_run_attested_step(...)` + `_run_one(...)` (moved from audit_suite, unchanged).
  • `run_workflow(steps_table, run_id, project_slug, workspace_root, workbook_path, now_epoch, *,
    write=True, schema_path=None, commit_fn=committer.commit, engine_version=None,
    report_step_name=None, report_exists=False) -> dict` — build specs → `_run_one` loop → append the
    optional report step (fact C) → `derive_verdict` → the UNIFIED completion guard (fact B) → `build_record`
    → optional `write_coverage` → return record.

Each workflow module becomes THIN, preserving its EXACT public surface (fact E):
  • Keep its module docstring (trim the now-shared mechanics; keep the workflow-specific narrative —
    audit's 1d.1/silent-skip notes, setup's sequential-dependency notes, monthly's transform-impedance note).
  • Keep `STEPS` (monthly's entries GAIN `output_file=f"{sheet}.json"` + `verification_class="code_verified"`),
    `WORKFLOW` (audit/setup), `REPORT_STEP_NAME` (monthly).
  • `from scripts.orchestration import workflow_driver` (and `committer` for the default arg).
  • Re-export the shared helpers as module attributes so test imports resolve:
        inbox_path = workflow_driver.inbox_path
        _output_loader = workflow_driver._output_loader
        WorkflowError = workflow_driver.WorkflowError      # keep the name importable
    For `output_path`:
        - audit/setup:  `output_path = workflow_driver.output_path`              (OUTPUT_FILE-keyed)
        - monthly:      `def output_path(workspace_root, run_id, slug, sheet):   # SHEET-keyed (preserved)
                             return workflow_driver.output_path(workspace_root, run_id, slug, f"{sheet}.json")`
  • `def build_steps(run_id, project_slug, workspace_root): return workflow_driver.build_steps(STEPS, ...)`
    (preserves the module-STEPS-bound signature the tests use).
  • `def run(...) -> dict:` (same signature as today, incl. monthly's `report_exists`) →
    `return workflow_driver.run_workflow(STEPS, ..., report_step_name=REPORT_STEP_NAME, report_exists=report_exists)`
    for monthly; audit/setup pass neither report arg.
  • Keep `_build_arg_parser` + `main` per module (they diverge: monthly has `--report-exists` + no `workflow=`
    on remediation; audit/setup pass `workflow=WORKFLOW`). These stay thin and call the module's `run`.
  • new_project_setup: DELETE `from ...audit_suite import _run_one` (the dispatch now lives in
    workflow_driver and is used via `run_workflow`). audit_suite no longer needs to own `_run_one`/
    `_run_attested_step` (moved) — remove them from audit_suite (nothing else imports them except setup,
    which you're rewiring; CONFIRM by grep before deleting).

Result: monthly/audit/setup each shrink to STEPS + a handful of thin wrappers; one shared
`workflow_driver.py` holds the machinery; the cross-driver import is gone; every public name tests use is
preserved → no test changes.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest (rule 3) — record numbers.
2. READ all 3 modules + content_pipeline (to see what STAYS) + the 6 test files in fact E + the oracle
   (`scripts/reporting/orchestration_metrics.py`) so you KNOW what public surface to preserve.
3. GREP to confirm nothing outside SCOPE imports `audit_suite._run_one`/`_run_attested_step` (only setup,
   which you rewire). Confirm the oracle imports only `<module>.STEPS` + monthly/audit path helpers.
4. Write `workflow_driver.py`.
5. Rewire the 3 modules to thin wrappers (preserve EXACT public API per fact E).
6. Run the 3 driver tests + the 2 CLI integration tests + the oracle test + the lint2 test FIRST (fast,
   targeted): `pytest tests/orchestration/ tests/reporting/test_orchestration_metrics.py
   tests/schemas/test_workflow_tool_subset_declared.py -q`. All must be GREEN with NO test edits.
7. FULL suite (rule 3) → passed >= 2194, failed == 0.
8. Self-review: diff is pure refactor? No test/content/spine/oracle touched? monthly output_path still
   SHEET-keyed, audit/setup OUTPUT_FILE-keyed? StepSpecs byte-identical (tests prove it)? cross-import gone?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• ANY test would need editing to pass (means a signature/behaviour wasn't preserved — report which + why).
• You find a caller OUTSIDE scope importing a moved symbol (a 4th importer of `_run_one`, etc.).
• A StepSpec or coverage record would differ in ANY field from today (behaviour drift — do not ship it).
• The unified completion guard would change any workflow's verdict on any existing test.
• You'd need to touch content_pipeline / the spine / the oracle / a test.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE: the pytest numbers you measured.
2. NEW MODULE: `workflow_driver.py` public API (signatures) — confirm spine is composed (imported), never
   edited; confirm `output_path` is canonical filename-keyed.
3. REWIRE: for each of the 3 modules, the public names preserved (fact E) + HOW (re-export vs wrapper);
   confirm monthly's `output_path` stays SHEET-keyed (bridges `f"{sheet}.json"`), audit/setup OUTPUT_FILE-
   keyed; confirm monthly's STEPS gained `output_file` + `verification_class` (byte-identical values);
   confirm `new_project_setup` no longer imports `audit_suite._run_one` and audit no longer defines it.
4. NO-TEST-CHANGE PROOF: `git status --porcelain` shows ONLY the 4 SCOPE files; NO test file touched.
5. TARGETED GREEN: the 3 driver tests + 2 CLI integration tests + oracle test + lint2 test all pass.
6. FULL SUITE: the final `tail -5` (passed >= 2194, 0 failed).
7. BEHAVIOUR-EQUIVALENCE NOTES: how you confirmed StepSpecs + verdicts are byte-identical (which tests pin
   it); the completion-guard equivalence; anything you had to decide or that surprised you.
```
