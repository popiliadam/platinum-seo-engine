# AMO Batch 2d — Correctness Oracle (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 1 complete + pushed (HEAD `9b5d238`, suite **1891/0**). The
> manager SPLIT the spec's "2c" into 2c (denetçi Stop-hook) + **2d (this — the correctness oracle)**. This is
> the deliverable that makes the ≤5% structured-error number TRUSTWORTHY (spec G5): an OFFLINE metrics script
> that reconciles each run's committed master.xlsx rows against its raw provenance + transform output,
> INDEPENDENT of the run's self-reported `verdict`. It is **file-disjoint from 2a (consent) AND 2c (denetçi)** —
> a pure new `scripts/reporting/orchestration_metrics.py` + tests, NO hook, NO schema, NO command → NO D10
> count-guard. Runs as a 3rd parallel window. Paste the block below into a fresh Claude Code session (Opus 4.8,
> 1M context) at the repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 2d of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). SIBLING workers may be running batch 2a (consent ledger) and batch 2c
(scripts/hooks/denetci.py + hooks/stop.json) in parallel — those files are NOT yours. If you ever need a file
outside your SCOPE list, STOP and report it.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 1891) BEFORE any change. END green with passed >= N, 0 failed.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (build NEW objects, never mutate inputs); no leftover debug prints (the CLI's
  user-facing report print is fine); pure functions where possible; small functions (<50 lines); files
  200-400 lines normal.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.

WHY THIS BATCH EXISTS (read carefully):
AMO claims "<=5% error on structured workflows" (spec G5). That number is WORTHLESS if it comes from the run's
own self-reported status (a run can write verdict="pass" while silently committing wrong/short data). The
ORACLE is the independent auditor: for each run it RE-DERIVES the truth from the actual on-disk artifacts —
the raw provenance drop the model wrote, the transform output, and the COMMITTED master.xlsx — and reports
whether they reconcile, WITHOUT trusting the coverage record's `verdict`/`scored_count`. The headline number
is the structured-error rate = (runs whose committed workbook does NOT reconcile with their provenance) /
(total reconcilable runs), plus the "fake-green" count = runs where verdict=="pass" but the oracle found a
mismatch. This is a READ-ONLY reporting module (no state writes); it never blocks anything.

CONFIRMED FACTS (verified against the code 2026-06-06 — do not re-derive):
- RAW DROP shape (`scripts/orchestration/verify.py`): each raw artifact is
  `{"provenance": {"run_id","slug","site_url","window","tool","fetched_at","declared_count"}, "rows": [ ... ]}`.
  verify_raw_drop already enforces `provenance.declared_count == len(rows)` (reason "truncated" otherwise) and
  identity (`run_id`/`slug` + optional site_url/window/tool). `scripts.orchestration.verify.silent_skip_exceeds(
  input_count, scored_count, max_ratio=0.5)` is the silent-skip gate — REUSE it, don't reinvent.
- ARTIFACT PATHS — REUSE the workflow's OWN helpers so paths can never drift:
  `from scripts.orchestration.workflows.monthly_maintenance import STEPS, inbox_path, output_path`.
    STEPS = ordered tuple of {name, sheet, writer, site_url, window, tool} — the code_verified steps:
      gsc_pull->sheet "gsc_performance", quick_wins->"quick_wins", content_decay->"content_decay".
    inbox_path(ws, run_id, slug, step_name)  -> `{ws}/projects/{slug}/_state/inbox/{run_id}/{step}.json`  (RAW drop).
    output_path(ws, run_id, slug, sheet)     -> `{ws}/projects/{slug}/_state/transform/{run_id}/{sheet}.json` (transform OUTPUT;
       a bare JSON list OR {"rows":[...]}).
- COVERAGE record (`scripts/orchestration/coverage.py`, schema `schemas/coverage.schema.json`): at
  `{ws}/projects/{slug}/_state/coverage/{run_id}.json` with steps[].{name, verification_class, status,
  observed_mcp, input_count, scored_count}, required_satisfied, verdict (pass|incomplete|paused|failed).
  `coverage.coverage_path(ws, slug, run_id)`; the coverage DIR is its parent. The oracle READS these but does
  NOT trust verdict/scored_count for its independent number — they are the SELF-REPORT it audits against.
- COMMITTED master.xlsx: the committer (`scripts/orchestration/committer.commit` -> `transaction.replace`)
  clears a sheet's data block and writes the transform-output rows starting at the sheet's `data_start_row`.
  Per-sheet `data_start_row` is in `schemas/master-excel.schema.json` under `sheets.{sheet}.data_start_row`
  (gsc_performance=5, quick_wins=5, content_decay=6). So committed-row-count = # contiguous non-empty rows from
  `data_start_row` down. Read it with openpyxl (`load_workbook(path, read_only=True, data_only=True)`); openpyxl
  is already a project dependency (transaction.py uses it).
- The quick_wins step ALSO writes a secondary `opportunity` sheet, but its coverage step + transform output are
  keyed on the PRIMARY sheet `quick_wins` — reconcile only the primary sheet (matches STEPS).
- This batch writes NO state, modifies NO existing module, adds NO hook/schema/command (so NO D10 count-guard).
  It only READS artifacts + adds one reporting module + its test.

ORIENT FIRST (read, do not change yet):
- `scripts/orchestration/verify.py` (raw-drop shape + silent_skip_exceeds) — you import silent_skip_exceeds.
- `scripts/orchestration/workflows/monthly_maintenance.py` (STEPS, inbox_path, output_path) — you import these.
- `scripts/orchestration/coverage.py` (coverage_path, the record shape).
- `schemas/master-excel.schema.json` — the `sheets.{sheet}.data_start_row` map you read.
- `scripts/excel/transaction.py` — skim the `replace()` write side + `WriteResult.rows_affected` so your
  reconcile reads the workbook the SAME way it was written (header at header_row, data from data_start_row). You
  may reuse `committer.commit` / `transaction.replace` in TESTS to seed a realistic workbook (optional).
- `scripts/reporting/monthly_report.py` + `tests/reporting/test_template_dialect.py` — the reporting-module +
  test house style (where reporting code/tests live).

SCOPE — create/modify ONLY these files:
  NEW  scripts/reporting/orchestration_metrics.py          (the oracle: reconcile + rate + CLI; see SPEC)
  NEW  tests/reporting/test_orchestration_metrics.py       (reconcile-pass + each-perturbation-mismatch + rate)

SPEC — scripts/reporting/orchestration_metrics.py (READ-ONLY; pure where possible; build NEW objects):

  Reconcile ONE code_verified step of ONE run (the heart — make this a pure-ish function that takes already-read
  data, plus a thin IO wrapper that reads the artifacts). A step RECONCILES (independent_ok) iff ALL hold:
    R1 (identity)   raw drop exists; raw.provenance.run_id == run_id AND raw.provenance.slug == slug.
    R2 (untruncated) raw.provenance.declared_count == len(raw.rows).
    R3 (output)     transform output file exists and is a list (or {"rows":[list]}).
    R4 (workbook)   committed-row-count(sheet) == len(transform output rows).   [only when a workbook is given]
    R5 (self-report) coverage step.scored_count == committed-row-count.          [only when a workbook is given]
  When NO workbook is available, R4/R5 are SKIPPED and the step/run is marked `workbook_absent` (NOT counted as
  reconciled — reported separately; never silently treated as pass). Record WHICH checks failed (a list of
  reason codes: "raw_missing","identity_mismatch","truncated","output_missing","workbook_mismatch",
  "scored_count_mismatch","workbook_absent") so a mismatch is explainable.

  Public API (names are a guide; keep them clear + tested):
    - committed_row_count(workbook_path, sheet, data_start_row) -> int | None:
        open read_only; for the worksheet `sheet`, count CONTIGUOUS rows from `data_start_row` downward that have
        at least one non-None cell, stopping at the first all-empty row; return the count. Return None if the
        workbook or sheet is missing/unreadable (caller treats None as workbook_absent for that sheet).
    - data_start_row_for(sheet, schema_path=None) -> int: read schemas/master-excel.schema.json,
        return sheets[sheet].data_start_row (raise a clear error if the sheet is unknown).
    - reconcile_step(*, workspace_root, slug, run_id, step_name, sheet, coverage_step, workbook_path=None,
                     schema_path=None) -> dict:
        read raw (inbox_path) + transform output (output_path) + (if workbook_path) committed count; apply R1-R5;
        return {step, sheet, independent_ok: bool, failed_checks: [...], raw_count, output_count,
                committed_count, scored_count} (a NEW dict).
    - reconcile_run(*, workspace_root, slug, run_id, workbook_path=None, schema_path=None,
                    steps=STEPS, coverage_record=None) -> dict:
        load the coverage record (coverage_path) if not passed; for each STEPS entry whose coverage step is
        verification_class=="code_verified", reconcile_step; the run is:
          - "workbook_absent" if workbook_path is None/unreadable (report, don't score),
          - else "reconciled" if EVERY code_verified step independent_ok, else "mismatch".
        Return {run_id, slug, independent_verdict, self_reported_verdict (from coverage), steps:[...],
                fake_green: bool}  where fake_green = (self_reported_verdict=="pass" AND independent_verdict=="mismatch").
    - structured_error_rate(run_reconciliations) -> dict:
        Over a list of reconcile_run dicts, compute {total, reconcilable (exclude workbook_absent), reconciled,
        mismatched, workbook_absent, error_rate (mismatched/reconcilable, 0.0 if reconcilable==0),
        fake_green_count, mismatched_run_ids:[...]}. NEVER silently drop workbook_absent — surface its count.
    - oracle_report(*, workspace_root, slug, workbook_path=None, schema_path=None) -> dict:
        enumerate every {run_id}.json under the slug's coverage dir, reconcile_run each, return
        {slug, runs:[...], metrics: structured_error_rate(...)}.
  CLI (argparse `main`): `python3 -m scripts.reporting.orchestration_metrics --workspace-root <ws> --slug <slug>
     [--workbook <path>]` -> print a compact human report: the error_rate %, reconciled/mismatched/workbook_absent
     counts, the fake_green run_ids (loud — these are the dangerous ones), and a per-run line. Exit 0 always
     (a reporting tool; it never fails the build). If --workbook is omitted, print a clear "workbook not given →
     R4/R5 skipped, runs marked workbook_absent" note (no silent degradation).

  Module docstring: cite spec G5 + that this is the INDEPENDENT oracle (reconciles committed master.xlsx vs raw
  provenance via the transform-output bridge), READ-ONLY, never trusts the self-reported verdict, and that
  fake_green (verdict==pass but mismatch) is the headline catch. Note the reconcile uses the transform OUTPUT
  (not raw row count) as the expected committed count, because steps like quick_wins legitimately FILTER.

TDD — write these FIRST (RED), then implement (GREEN). Build a tmp workspace with the real artifact layout (use
inbox_path/output_path/coverage_path to place files); seed the workbook either directly with openpyxl (header at
header_row, data rows from data_start_row) OR via committer.commit/transaction.replace (one realistic integration
test is a bonus). Cover:
  1. committed_row_count: a sheet with K data rows from data_start_row -> K; empty sheet -> 0; missing
     workbook/sheet -> None.
  2. reconcile_step HAPPY: raw (declared_count==len, identity ok) + output of M rows + workbook committed M +
     coverage scored_count M -> independent_ok True, failed_checks [].
  3. reconcile_step each perturbation -> independent_ok False with the RIGHT failed_check:
       - raw provenance slug != run slug      -> "identity_mismatch"
       - raw declared_count != len(rows)       -> "truncated"
       - transform output missing              -> "output_missing"
       - committed rows != len(output)         -> "workbook_mismatch"
       - coverage scored_count != committed    -> "scored_count_mismatch"
  4. reconcile_run: all steps reconcile -> "reconciled"; one step mismatched -> "mismatch"; verdict=="pass" but
     a step mismatched -> fake_green True.
  5. reconcile_run with workbook_path=None -> independent_verdict "workbook_absent" (R4/R5 skipped, not scored).
  6. structured_error_rate over a mix (e.g. 3 reconciled + 1 mismatch + 1 workbook_absent) -> total 5,
     reconcilable 4, error_rate 0.25, workbook_absent 1, fake_green_count correct, mismatched_run_ids correct.
  7. oracle_report end-to-end over a coverage dir with 2 runs -> the right per-run verdicts + aggregate metrics.
  8. CLI smoke: main(["--workspace-root", ws, "--slug", slug, "--workbook", wb]) exits 0 and prints the rate.

METHOD:
  1. Baseline pytest (record N == 1891).
  2. Write test_orchestration_metrics.py (RED).
  3. Author orchestration_metrics.py (GREEN). Reuse monthly_maintenance.{STEPS,inbox_path,output_path},
     coverage.coverage_path, verify.silent_skip_exceeds; read data_start_row from master-excel.schema; openpyxl
     read_only for the workbook.
  4. Full suite; passed >= N, 0 failed.
  5. Self-review @code-reviewer + @verifier (inline): the oracle NEVER writes state; NEVER trusts verdict for its
     independent number; reconciles via the transform OUTPUT (so filtering steps like quick_wins don't
     false-flag); workbook_absent is reported, never silently passed; immutability + small functions.

DURUR (stop + report):
  - An orchestration_metrics / oracle module already exists (grep) — report rather than duplicate.
  - Reconciling correctly would require CHANGING verify/coverage/committer/monthly_maintenance — STOP + report
    (this batch only READS them + reuses their path/helper functions).
  - The committed-row count is ambiguous for a sheet whose data block isn't contiguous from data_start_row
    (unexpected) — STOP + report what you saw rather than guessing a heuristic that could miscount.
  - Any existing test regresses for a reason outside this batch's files.

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line (passed/skipped/failed).
  - Files created + new-test count.
  - The reconcile contract you implemented (R1-R5) + confirmation it reconciles committed-rows against the
    TRANSFORM OUTPUT (so quick_wins filtering does not false-flag) and is INDEPENDENT of coverage.verdict.
  - The error_rate formula (mismatched / reconcilable) + confirmation workbook_absent is reported, never
    silently scored as pass.
  - Confirmation `fake_green` (verdict=="pass" AND independent mismatch) is detected + surfaced loudly.
  - Confirmation the module writes NO state and added NO hook/schema/command (no D10).
  - Any DURUR hit, out-of-scope need, or assumption.
```
