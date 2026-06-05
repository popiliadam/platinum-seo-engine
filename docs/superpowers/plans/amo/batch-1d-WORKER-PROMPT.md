# AMO Batch 1d — Reference Workflow `monthly-maintenance` + `/pseo-run` + Remediation (WORKER PROMPT)

> **Manager note (not part of the prompt):** The Faz-1 CAPSTONE — it ties the orchestrator together: the
> ordered `monthly-maintenance` sequence (driven by 1b's run_step/run_sequence over 1b2's committer, writing
> 1a's coverage record), the `/pseo-run` command (the action 1c's intent router injects), and the operator-
> remediation surface (Turkish one-line fix command). The manager RESOLVED the key design fork: the skill
> transforms take rich payloads (`gsc_pull.transform(raw:dict,*,enriched)`), NOT rows→rows — so the model runs
> the existing transform CLI (→ `_state/transform/{run_id}/`), `run_step`'s `transform` becomes a LOADER of
> that model-produced output, and `verify_raw_drop` gates the provenance-stamped raw MCP drop
> (`_state/inbox/{run_id}/`) for input_count. This needs NO change to run_step (the loader IS the transform).
> The silent-skip gate stays intact (raw input_count vs committed scored_count). After 1d, Faz 1 closes.
> Run serially (Phase-0/1 are done; no parallel batch). Paste into a fresh Opus-4.8 1M session.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 1d of the AMO initiative (the Faz-1
capstone), managed from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when
done, STOP and print the REPORT (the manager reviews + commits).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N is ~1875) BEFORE any change. END green, passed strictly >= N.
- TDD: failing test first, watch it fail, then implement. Never fake red.
- House style: immutability (frozen dataclasses / new objects, never mutate inputs); no debug prints in
  shipped code; no hardcoded secrets; functions <50 lines; pass `now`/timestamps + run_id IN as args (pure,
  testable) — never call datetime.now()/time.time() deep inside logic.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else -> STOP + report. (The D10 command-count
  guards ARE in scope as pre-authorized satellites; see SCOPE.)

WHY THIS BATCH (read carefully):
This makes "alpha'da aylık bakım yap" run end-to-end. The monthly-maintenance workflow is a hard-coded ORDERED
Python sequence (Path A — no DAG engine): gsc-pull -> (quick-wins + content-decay) -> monthly-report. For each
structured step the MODEL makes the MCP call + runs the existing transform, and CODE verifies + commits +
records coverage. You build: (1) the workflow definition + driver, (2) the `/pseo-run` command the model
invokes, (3) the operator-remediation surface (a Turkish one-line fix command for every incomplete/paused
run). The denetçi that ENFORCES completion is a LATER batch (2c) — here you build the workflow so it RUNS and
produces a coverage record + a remediation message; you do NOT build the Stop hook.

CONFIRMED FACTS (manager-verified 2026-06-05 — do not re-derive):
- The orchestrator spine (batch 1b, `scripts/orchestration/`): 
    run_step(spec: StepSpec, *, run_id, project_slug, workspace_root, workbook_path, now_epoch,
             max_age_seconds=86400, schema_path=None, commit_fn=committer.commit) -> coverage-step dict
    run_sequence(specs, *, run_id, project_slug, workspace_root, workbook_path, now_epoch, write=True,
             max_age_seconds=86400, schema_path=None, commit_fn=committer.commit, coverage_schema_path=None,
             engine_version=None, created_at=None, updated_at=None) -> coverage record dict
    StepSpec(name, raw_path, sheet, transform: Callable[[list[dict]],list[dict]], verification_class=
             "code_verified", required=True, expected_site_url=None, expected_window=None, expected_tool=None,
             observed_mcp=())
    coverage.build_step / build_record / derive_verdict / write_coverage / coverage_path
    verify.verify_raw_drop / silent_skip_exceeds ; committer.commit (idempotent transaction.replace wrap)
  run_step does: verify_raw_drop(spec.raw_path) -> rows_out = spec.transform(vr.rows) -> commit_fn(...) ->
  silent-skip gate (vr.input_count vs scored) -> coverage step. derive_verdict -> (required_satisfied, verdict
  in {pass, incomplete, paused, failed}).
- THE TRANSFORM IMPEDANCE + ITS RESOLUTION (do not re-derive): the skill transforms are NOT rows->rows —
  `scripts/ingestion/gsc_pull.py::transform(raw: dict, *, enriched=None) -> dict`,
  `scripts/discovery/content_decay_transform.py::transform(...)`, quick-wins similarly — they take rich raw
  payloads. So you do NOT call them inside run_step. Instead the workflow uses run_step's `transform` as a
  LOADER of the model-produced transform OUTPUT:
    * The model makes the MCP call and writes a PROVENANCE-STAMPED raw drop to the orchestrator-dictated path
      `_state/inbox/{run_id}/{step}.json` = {"provenance": {run_id, slug, site_url, window, tool, fetched_at,
      declared_count}, "rows": <raw MCP rows>}.  (verify_raw_drop gates this -> input_count.)
    * The model runs the EXISTING transform CLI (e.g. `python3 -m scripts.ingestion.gsc_pull ...
      --output-dir _state/transform/{run_id}/`) which writes the master.xlsx-shaped OUTPUT rows to
      `_state/transform/{run_id}/{step}.json` (a JSON list, or {"rows": [...]}; support both).
    * run_step's transform = a LOADER closure that IGNORES the verified raw rows and returns the loaded output
      rows. committer.commit writes them -> scored_count. The silent-skip gate then compares raw input_count
      vs committed scored_count (catches a transform that dropped too many rows). NO run_step change needed.
- monthly-report is `model_attested`, NOT code_verified: `skills/reporting/monthly-report/SKILL.md` writes
  `master.xlsx#none` (READ-ONLY — reads the committed sheets + last-28d events.jsonl, renders
  `outputs/reports/{date}-monthly.md`). It commits NO sheet. So it is a coverage step with
  verification_class="model_attested", status "satisfied" iff its report artifact exists (the orchestrator
  records it RAN, does NOT verify quality — per the <=5% honest-scope split).
- Commands are model-executed markdown recipes (see commands/pseo-gsc-pull.md: frontmatter {description,
  argument-hint, allowed-tools, model: sonnet} + numbered steps with `!`bash blocks + a skill chain). They
  are NOT unit-tested for prose. `/pseo-run` is a new such command.
- D10 count-guard: adding `commands/pseo-run.md` (a NEW command) trips the command-count guards. Apply
  (pre-authorized) + FLAG in REPORT: `.claude-plugin/plugin.json` "19 slash command" -> "20 slash command";
  `.claude-plugin/marketplace.json` "19 commands" -> "20 commands". Check `tests/docs/test_count_consistency.py`
  — its `_count_commands()` globs commands/*.md (dynamic), so it self-heals once both manifests say 20; if any
  OTHER test pins the command count literally, bump it too (report which). Do NOT touch plugin.json's other
  counts.

ORIENT FIRST (read, do not change yet):
- `scripts/orchestration/run_step.py` (run_step/run_sequence/StepSpec) + `coverage.py` + `verify.py` +
  `committer.py` + `tests/orchestration/test_run_step_e2e_stub.py` (mirror its canned-drop fixture style).
- `schemas/coverage.schema.json` (the record your driver writes must validate).
- `commands/pseo-gsc-pull.md` + `commands/pseo-monthly.md` (the command recipe shape + the report step).
- `skills/ingestion/gsc-pull/SKILL.md` (the transform CLI invocation `--output-dir _state/transform/{run_id}/`
  + the raw inbox convention) + `skills/reporting/monthly-report/SKILL.md` (the attested report step).
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (the "19 slash command"/"19 commands"
  strings) + `tests/docs/test_count_consistency.py`.

SCOPE — create/modify ONLY:
  NEW  scripts/orchestration/workflows/__init__.py              (package marker if siblings use one)
  NEW  scripts/orchestration/workflows/monthly_maintenance.py   (step definitions + the driver)
  NEW  scripts/orchestration/remediation.py                     (Turkish one-line fix-command renderer)
  NEW  commands/pseo-run.md                                      (the model-executed workflow command)
  NEW  tests/orchestration/test_monthly_maintenance.py          (e2e stub harness — the headline)
  NEW  tests/orchestration/test_remediation.py
  EDIT .claude-plugin/plugin.json                               (D10: "19 slash command" -> "20 slash command")
  EDIT .claude-plugin/marketplace.json                          (D10: "19 commands" -> "20 commands")

SPEC — scripts/orchestration/workflows/monthly_maintenance.py:
- A module-level ordered STEP table (data-driven), one entry per structured step:
    STEPS = [
      {"name": "gsc_pull",      "sheet": "gsc_performance", "writer": "gsc-pull",
       "site_url": True,  "window": "recent", "tool": "mcp__gsc__search_analytics"},
      {"name": "quick_wins",    "sheet": "quick_wins",      "writer": "quick-wins",
       "site_url": True,  "window": "30d",    "tool": "mcp__gsc__detect_quick_wins"},
      {"name": "content_decay", "sheet": "content_decay",   "writer": "content-decay",
       "site_url": True,  "window": "recent", "tool": "mcp__gsc__enhanced_search_analytics"},
    ]
  (quick_wins ALSO writes an `opportunity` sheet — model the step as committing its primary sheet
  `quick_wins`; the secondary `opportunity` write is the skill's own concern. Keep 1d's coverage step per the
  primary sheet, OR represent both as sub-commits if cleaner — your call, but the coverage step name must be
  stable.) The monthly-report step is appended SEPARATELY as model_attested (below).
- `inbox_path(workspace_root, run_id, step) -> Path` = workspace_root/"projects"/<slug>/"_state"/"inbox"/run_id/(step+".json")
  and `output_path(workspace_root, run_id, slug, step) -> Path` = .../"_state"/"transform"/run_id/(step+".json").
  (Match the existing `_state/transform/{run_id}/` convention; raw drops go under `_state/inbox/{run_id}/`.)
- `_output_loader(output_path) -> Callable[[list[dict]], list[dict]]`: returns a closure that IGNORES the
  verified raw rows and loads + returns the output rows from output_path (accept a bare JSON list OR
  {"rows":[...]}; raise a clear error if the file is missing/malformed — the model was supposed to write it).
- `build_steps(run_id, project_slug, workspace_root) -> list[StepSpec]`: one StepSpec per STEPS entry, with
  raw_path=inbox_path(...), sheet=entry["sheet"], transform=_output_loader(output_path(...)),
  verification_class="code_verified", expected_tool=entry["tool"], expected_window=entry["window"],
  expected_site_url=<the project's gsc.site_url if you resolve it, else None — do NOT hard-fail if unresolved;
  pass None>, observed_mcp=(entry["tool"],).
- `run(run_id, project_slug, workspace_root, workbook_path, now_epoch, *, write=True, report_exists=None,
      schema_path=None, commit_fn=committer.commit, engine_version=None) -> dict` (the driver):
    1. steps = run each build_steps() spec via run_step (collect coverage-step dicts) — a failed/missing step
       does NOT abort; record every step (mirror run_sequence's no-abort contract). [You MAY call run_sequence
       with write=False to get the code-verified steps, then extend — your choice; keep it pure + testable.]
    2. Append the monthly-report step as MODEL_ATTESTED: coverage.build_step("monthly_report",
       "model_attested", "satisfied" if report_exists else "missing", observed_mcp=[]). report_exists is an
       injected bool (the driver does NOT itself render the report — the model does; default None -> treat as
       missing/attested-not-confirmed). 
    3. (required_satisfied, verdict) = coverage.derive_verdict(all steps). Build + (if write) write the
       coverage record (coverage.write_coverage). Return the record.
  Keep run() < 50 lines (extract helpers). Do NOT make MCP calls or render reports here (model-owned).

SPEC — scripts/orchestration/remediation.py (the operator-remediation surface — Phase-1 first-class):
- `remediation(coverage_record, *, slug, workflow="monthly") -> dict | None`: from the record's verdict +
  steps, return None when verdict=="pass", else a structured dict
    {"missing": [step names not satisfied], "verdict": <verdict>,
     "one_line_fix_command": "/pseo-run {workflow} {slug} --resume",
     "why_turkish": <one Turkish sentence naming what's missing / that an external dependency paused it>}.
  For verdict=="paused" (external failure) the why_turkish says the run paused on an external dependency
  (GSC/DFS) and `--resume` retries; for "incomplete"/"failed" it names the missing/failed steps.
- `render(remediation_dict) -> str`: a compact model-visible block (NOT UI-only) ending with the
  copy-pasteable fix command — so a non-coder in the Mac app always has ONE next action. Pure; no IO.

SPEC — commands/pseo-run.md (model-executed recipe; frontmatter like commands/pseo-gsc-pull.md —
argument-hint "<workflow> [project-slug] [--resume]", allowed-tools incl. Bash + Read, model: sonnet):
- Body: a numbered recipe for `monthly` (the only Phase-1 workflow): resolve slug (arg -> session binding ->
  active.json); create/resume the workflow run (workflow_runner); FOR EACH structured step in order
  (gsc_pull, then quick_wins + content_decay, then) instruct the model to (a) make the named MCP call, (b)
  write the provenance-stamped raw drop to `_state/inbox/{run_id}/{step}.json`, (c) run the existing transform
  CLI to `_state/transform/{run_id}/{step}.json`; then run the driver
  (`python3 -m scripts.orchestration.workflows.monthly_maintenance ...` or an inline import) to verify+commit+
  record coverage; then run the monthly-report skill (attested) and render the report; FINALLY if the
  coverage verdict != pass, surface `remediation.render(...)` (the Turkish one-line fix command). Mirror the
  tone/structure of commands/pseo-gsc-pull.md. (This is prose — it is the contract, not unit-tested.)

TDD — write FIRST (RED), then implement (GREEN):
  test_remediation.py: verdict pass -> None; incomplete with a missing step -> dict names it + the
    "/pseo-run monthly <slug> --resume" command; paused -> why_turkish mentions external/resume; render()
    output contains the fix command + is non-empty.
  test_monthly_maintenance.py (the e2e stub — mirror test_run_step_e2e_stub.py; use a FAKE commit_fn returning
    rows_affected=len(rows), pin now_epoch + mtimes, tmp_path):
    * Happy path: drop correct provenance-stamped raw inbox drops + matching transform outputs for all 3
      structured steps + report_exists=True -> run() returns a record that VALIDATES against
      coverage.schema.json, verdict=="pass", required_satisfied True, 4 steps (3 code_verified satisfied + 1
      model_attested satisfied), and remediation(record)==None.
    * Missing one structured step's raw drop -> that step status "missing", verdict "incomplete",
      remediation names it + yields the --resume command.
    * A transform output that dropped >50% of the raw rows -> that step "failed" (silent-skip gate), verdict
      "failed"/"incomplete" (assert it is NOT "pass").
    * report_exists=False -> the monthly_report step is "missing"/attested-not-confirmed and verdict != pass.
    Use the SAME canned-drop fixture idiom as test_run_step_e2e_stub.py. Never touch the real workspace.

METHOD:
  1. Baseline pytest (N ~1875).
  2. Tests RED.
  3. Implement remediation.py, monthly_maintenance.py (GREEN). Author commands/pseo-run.md. Apply the 2 D10
     command-count bumps.
  4. Sanity: `python3 -c "import scripts.orchestration.workflows.monthly_maintenance, scripts.orchestration.remediation"`
     + parse all commands/*.md frontmatter if a loader exists; confirm coverage records validate.
  5. FULL suite; passed >= N, 0 failed. `git status --short` = ONLY the scoped files.
  6. @code-reviewer + @verifier inline.

DURUR (stop + report, do not work around):
  - run_step/run_sequence/StepSpec/coverage signatures differ from the CONFIRMED FACTS -> report the real ones.
  - Wiring the loader-transform into run_step needs a run_step change -> STOP + report (it should NOT; the
    loader is just a Callable[[list[dict]],list[dict]] passed as StepSpec.transform).
  - The command-count guard isn't the literal "19 ..." you expect -> report the real numbers, do not guess.
  - A command-frontmatter / command↔skill parity test fails for /pseo-run (it references skills, not a single
    skill) -> report it (the manager decides whether /pseo-run needs a frontmatter exemption).

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line; files created/edited + new test count.
  - The driver's step model (3 code_verified loader-transform steps + 1 model_attested report) + how the
    silent-skip gate stays intact (raw input_count vs committed scored_count) WITHOUT a run_step change.
  - Proof the e2e stub covers happy/missing/silent-skip/no-report, the record validates against
    coverage.schema.json, and remediation yields the Turkish "/pseo-run monthly <slug> --resume" on a
    non-pass verdict.
  - "D10 command-count bumps": BEFORE/AFTER plugin.json + marketplace.json (manager re-verifies vs filesystem
    `ls commands/*.md | wc -l`).
  - Confirmation NO run_step/coverage/committer/verify code changed (you only USE them); only the scoped files.
  - Any DURUR / assumption / out-of-scope need (esp. anything you think belongs to 2c the denetçi).
```
