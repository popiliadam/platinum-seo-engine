# AMO Batch 3c — Replicate the orchestrator to `new-project-setup` (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 3, replicate #2 (Süleyman's pick). HEAD `928ddaf`, suite
> **2134 / 0**. This replicates the proven orchestrator to a 3rd workflow: `setup` — a new project's
> content-planning pipeline (`topical-map → cluster-map → new-content-plan`). Mirrors `audit_suite.py` (batch 3b)
> and **REUSES its D15 attested-path** + the 1b2 write-relocation. Cleaner than 3b: all 3 CLI output filenames
> MATCH their sheets (NO 1d.1 trap). New wrinkle: the 3 steps are SEQUENTIAL-DEPENDENT (cluster consumes
> topical_map; content-plan consumes cluster_keywords) — handled by ordering. **This is the 3rd workflow sharing
> the driver pattern → flag the duplication for the O4 decision (extract a shared driver).** Sized for a max-effort
> Opus-4.8 1M worker. Paste the fenced block into a fresh Claude Code session at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 3c of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 2134 at HEAD 928ddaf; a single MCP-availability-gated test
  may make it read 2133/8 — the floor is the passed+skipped TOTAL, which must not drop) BEFORE any change. END
  green with passed strictly >= your measured N and 0 failed. EVERY existing test MUST stay green — especially
  tests/skills/test_topical_map.py, test_cluster_map.py, test_new_content_plan.py + the whole tests/orchestration/ tree.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (build new objects, never mutate inputs); no leftover debug prints; small functions
  (<50 lines); files 200-400 lines; clear names.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.
- The 1b spine + the shipped workflow drivers are FROZEN: you may IMPORT
  scripts/orchestration/{run_step,verify,committer,coverage,remediation} and reuse audit_suite's D15 dispatch
  (see SPEC), but must NOT edit run_step/verify/committer/coverage/monthly_maintenance/audit_suite. If you think
  you must, STOP + report.

WHY THIS BATCH EXISTS (read carefully):
Faz 1 built workflow #1 (`monthly`); batch 3b built #2 (`audit`). Faz 3 replicates the proven pattern to more
ordered Python workflows. This batch builds #3: `setup` — a NEW project's content-planning pipeline. After a
project is scaffolded (by `/pseo-init`, the PRECONDITION — NOT part of this workflow), `setup` populates its
content plan in order: topical-map (pillar/cluster/supporting topic map) → cluster-map (keyword clusters) →
new-content-plan (the content brief plan). Same shape as `audit`: for each step the MODEL makes the MCP call(s)
+ writes a provenance-stamped raw drop, runs the step's EXISTING transform CLI to a per-step output file, then a
thin DRIVER verifies + commits (idempotent replace) + records coverage.

Two sub-jobs (identical to how 3b was built):
  (1) WRITE-RELOCATION (1b2): the 3 planning skills write master.xlsx via a `transaction.append` in SKILL.md
      prose. Relocate each into `committer.commit(...)` (idempotent replace; writer preserved).
  (2) WORKFLOW WIRING: a NEW driver `scripts/orchestration/workflows/new_project_setup.py` (mirror
      audit_suite.py) + extend `/pseo-run` to dispatch the `setup` workflow.

CONFIRMED FACTS (verified against the code 2026-06-08 — do NOT re-derive):

A) THE SPINE API (FROZEN — import, don't edit): IDENTICAL to what audit_suite.py uses. StepSpec(name, raw_path,
   sheet, transform, verification_class="code_verified", required=True, expected_site_url=None,
   expected_window=None, expected_tool=None, observed_mcp=()); run_step(spec, *, run_id, project_slug,
   workspace_root, workbook_path, now_epoch, max_age_seconds=86400, schema_path=None, commit_fn=committer.commit);
   verify_raw_drop pins site_url/window/tool ONLY when non-None; committer.commit(workbook, sheet, rows, *,
   run_id, project_slug, schema_path=None, writer="orchestrator") -> WriteResult(.rows_affected);
   silent_skip_exceeds(input,scored,max_ratio=0.5). Read scripts/orchestration/run_step.py + verify.py +
   committer.py if unsure.

B) THE TEMPLATE = scripts/orchestration/workflows/audit_suite.py (batch 3b) — READ IT IN FULL and mirror it.
   It already solved the silent-skip/analysis-cardinality seam (D15): a module STEPS tuple with an EXPLICIT
   `output_file` + `verification_class` per step; `build_steps`; `_run_attested_step` (verify_raw_drop STILL
   gates identity+content+freshness, only the silent_skip COUNT is advisory) for analysis steps;
   `_run_one(spec,...)` dispatches `code_verified`→run_step / `model_attested`→_run_attested_step; `run(...)`
   with a COMPLETION GUARD (`pass→incomplete` unless ALL steps satisfied, since derive_verdict treats attested as
   soft); a CLI. **REUSE audit_suite's `_run_attested_step` + `_run_one` by IMPORTING them** (they take a
   StepSpec + run_id/slug/workbook/now_epoch — workflow-agnostic, no audit-specifics) rather than re-copying.
   (If importing a sibling workflow's helpers feels wrong, mirror them instead — but note in the REPORT that 3
   workflows now duplicate this dispatch → the O4 "extract a shared driver" signal.)

C) THE 3 SETUP STEPS — the pipeline = these 3 planning skills (each writes ONE snapshot master.xlsx sheet via a
   `transaction.append` in SKILL.md prose + has an EXISTING transform CLI). Verified facts:

   | step (order)     | master sheet     | CLI OUTPUT FILE     | transform CLI                                  | writer            |
   |------------------|------------------|---------------------|------------------------------------------------|-------------------|
   | topical_map      | topical_map      | topical_map.json    | scripts/planning/topical_map_transform.py      | topical-map       |
   | cluster_map      | cluster_keywords | cluster_keywords.json | scripts/planning/cluster_map_transform.py    | cluster-map       |
   | new_content_plan | new_content_plan | new_content_plan.json | scripts/planning/new_content_plan_transform.py | new-content-plan|

   - ALL 3 CLI output filenames MATCH their sheet name (topical_map.json, cluster_keywords.json,
     new_content_plan.json) — so there is NO 1d.1 trap here (unlike 3b's schema_audit). Still carry an EXPLICIT
     `output_file` per STEPS entry (consistent with audit_suite + future-proof) and lock it with the integration test.
   - All 3 sheets are SNAPSHOTS (no date/run/snapshot column in master-excel.schema.json — VERIFY) → the
     `transaction.append` is a latent dup-on-re-run bug → committer.commit (replace) is the correct relocation (1b2).
   - PRIMARY MCP tool per step: these are DFS-keyword / GSC-driven planning steps. Read each skill + its CLI to
     pin the right `expected_tool` (a DFS labs/keywords tool, e.g. `mcp__dataforseo__dataforseo_labs_google_*`);
     pin `expected_window=None` (planning is point-in-time, not a date window); pin `expected_site_url` only if
     the step's primary drop is GSC-sourced. If a step has no single pinnable primary tool, set `expected_tool=None`.
   - ⚠️ SEQUENTIAL DEPENDENCY (the new wrinkle): cluster_map CONSUMES `master.xlsx#topical_map`; new_content_plan
     CONSUMES `master.xlsx#cluster_keywords` (their `consumes:` frontmatter). The DRIVER runs steps IN ORDER, so
     each prior sheet is COMMITTED before the dependent step runs — the dependency is satisfied by ordering, NOT
     a driver change. But CONFIRM how each dependent transform CLI RECEIVES the prior sheet's data: does
     cluster_map_transform / new_content_plan_transform READ master.xlsx directly (e.g. via --project-config), or
     does the model pass the prior rows as an input arg? Read the two CLIs' `_parse_args` + their input loading,
     and document the mechanism in the recipe (the model reads the committed prior sheet + provides it however
     the CLI expects). The integration test must run the 3 REAL CLIs IN ORDER and prove the chain works.

D) SILENT-SKIP / D15 cardinality (resolve per step, REPORT each): planning transforms AGGREGATE (many DFS
   keywords → a structured pillar/cluster/plan), so they likely commit <50% of their raw input → enforcing
   silent_skip would FALSE-FAIL them → `model_attested` via the reused `_run_attested_step` (identity+content+
   freshness STILL gate a bad drop; only the count is advisory). For EACH step read the transform's output
   construction and classify code_verified (input≈output) vs model_attested (output≪input by design); REPORT the
   per-step cardinality + your choice. (Same honest ≤5%-scope split as 3b; the 3-oracle now backstops attested
   steps for ALL workflows incl. `setup` — its step-names are disjoint from monthly/audit so the oracle
   auto-resolves it.)

E) /pseo-run TODAY (commands/pseo-run.md): dispatches `monthly` (Bölüm 2-7) + `audit` (Bölüm 8); any other →
   DURUR. ADD a `setup` branch (a new Bölüm 9) mirroring the audit branch: resolve project, create/resume the run
   via workflow_runner (skill="new-project-setup", the 3 steps), the per-step recipe (MCP tool → provenance drop
   → transform CLI → {output_file}, with the dependent-step prior-sheet note), invoke the new_project_setup
   driver, verdict + Turkish remediation (`/pseo-run setup <slug> --resume`). Keep the monthly + audit sections
   BYTE-UNCHANGED — you ADD alongside.

F) D10 / count-guards: NO new commands/*.md and NO new schemas/*.json (new_project_setup.py is a script; reuses
   coverage.schema.json). So NO manifest/count-guard bump. The driver is not a wired hook → not a
   RUNTIME_HOOK_SCRIPTS entry. If you need a new command/schema file, STOP + report.

ORIENT FIRST (read in full, do not change yet):
- scripts/orchestration/workflows/audit_suite.py (THE template — mirror it; reuse _run_attested_step + _run_one).
- scripts/orchestration/workflows/monthly_maintenance.py (the original shape, for the loader/inbox/output pattern).
- commands/pseo-run.md (note the monthly Bölüm 2-7 + audit Bölüm 8 + the Section-1 routing fork).
- The 3 transform CLIs scripts/planning/{topical_map,cluster_map,new_content_plan}_transform.py — each
  `_parse_args` + the `--output-dir` write block (confirm the output filename in C) + the OUTPUT-ROW construction
  (for the D cardinality classification) + (cluster/content-plan) how they receive the prior sheet's data.
- The 3 skills' SKILL.md transaction.append blocks: skills/planning/{topical-map (~L387), cluster-map (~L366),
  new-content-plan (~L340)} — the writer= identity + the exact write to relocate (write-only).
- tests/skills/test_{topical_map,cluster_map,new_content_plan}.py — what they pin (1b2 found skill tests pin
  transform/frontmatter/output_ref, NOT the write mechanism; confirm + migrate only if a test pins the old append).
- schemas/master-excel.schema.json — confirm the 3 sheets are snapshots + their data_start_row.
- scripts/state/workflow_runner.py (create_run/resume — same calls /pseo-run uses).

SCOPE — create/modify ONLY these files:
  NEW  scripts/orchestration/workflows/new_project_setup.py     (the driver, mirror audit_suite.py)
  NEW  tests/orchestration/test_new_project_setup.py            (driver e2e: stub committer, raw-drop scenarios, verdict, completion)
  NEW  tests/orchestration/test_new_project_setup_cli_integration.py  (run the 3 REAL CLIs IN ORDER; assert each writes its output_file + the chain works)
  EDIT commands/pseo-run.md                                     (add the `setup` workflow branch; monthly + audit byte-unchanged)
  EDIT skills/planning/topical-map/SKILL.md                     (relocate transaction.append → committer.commit, writer preserved)
  EDIT skills/planning/cluster-map/SKILL.md
  EDIT skills/planning/new-content-plan/SKILL.md
  (EDIT tests/skills/test_*.py ONLY if a test pins the old write wording — 1b2-style migration; else STOP + report.)

SPEC — scripts/orchestration/workflows/new_project_setup.py (mirror audit_suite.py):
  - Module STEPS tuple, one dict per step, ORDERED topical_map → cluster_map → new_content_plan, each with an
    EXPLICIT output_file (= sheet+".json" here, but explicit for consistency), writer, expected_tool (the DFS/GSC
    primary tool or None), site_url flag, and verification_class (your D classification).
  - inbox_path / output_path (keyed by output_file) / _output_loader — same as audit_suite.
  - build_steps(run_id, slug, workspace): one StepSpec per STEPS entry (expected_window=None; site_url only where
    GSC-primary; observed_mcp=(tool,) if tool else ()).
  - run(...) mirrors audit_suite: dispatch each step via the REUSED `_run_one` (code_verified→run_step /
    model_attested→_run_attested_step), build coverage, derive verdict, apply the COMPLETION GUARD (pass→incomplete
    unless all steps satisfied), write coverage. The deliverable IS the 3 committed sheets — NO report step.
  - CLI main(): --run-id --slug --workspace-root --workbook --now-epoch [--no-write] [--engine-version]; print
    verdict + remediation.render(record, slug=, workflow="setup") on non-pass. Clock-free (now_epoch passed in).

SPEC — commands/pseo-run.md `setup` branch (new Bölüm 9, mirror the audit Bölüm 8):
  - Section 1 routing: add `setup` → Bölüm 9 (keep monthly→2-7, audit→8, else→DURUR).
  - Bölüm 9: create_run(skill="new-project-setup", steps=[{topical_map},{cluster_map},{new_content_plan}]) +
    --resume; the per-step recipe (gated MCP tool → provenance drop {run_id,slug,site_url?,window:null,tool,
    fetched_at,declared_count} → transform CLI args → {output_file}); for cluster_map + new_content_plan note the
    PRECONDITION that the prior sheet (topical_map / cluster_keywords) is already committed (the workflow runs
    steps in order) + how the dependent transform receives it; driver invocation; verdict + Turkish
    `/pseo-run setup <slug> --resume`; dependency list (the 3 skills + CLIs + the spine). Monthly + audit UNCHANGED.

SPEC — the 3 relocations (1b2): in each SKILL.md replace the single `transaction.append(...)` with
  `committer.commit(workbook_path, "<sheet>", rows, run_id=<handle.run_id>, project_slug=<slug>, writer="<skill>")`
  (writer preserved; run_id added; write-only; nothing else changes). Snapshot dup-on-re-run fix on all 3 sheets.

SPEC — tests:
  - test_new_project_setup_cli_integration.py: run the 3 REAL CLIs IN ORDER on minimal synthetic inputs (with the
    chain — topical_map's output feeds cluster_map's prior-sheet input feeds new_content_plan), assert each writes
    its output_file (topical_map.json, cluster_keywords.json, new_content_plan.json) + the dependent steps consume
    the prior output. (The 1d.1 + dependency lock.) If a CLI cannot run headless / needs a live MCP → STOP + report.
  - test_new_project_setup.py: driver e2e with a STUB committer (reuse the audit/monthly pattern) — per step:
    correct→satisfied, missing→missing, wrong run_id/slug→failed, stale→failed, truncated→failed; a cardinality
    case proving the D classification (an attested step dropping >50% is NOT false-failed); the completion guard
    (a missing step ≠ pass); the driver keys output_file; ORDER preserved.

TDD ORDER:
  1. Baseline pytest (record N).
  2. test_new_project_setup_cli_integration.py FIRST (RED → GREEN against the real CLIs — the chain lock).
  3. test_new_project_setup.py (RED — driver absent). Implement new_project_setup.py (reuse audit_suite's D15
     dispatch) → GREEN.
  4. Relocate the 3 skills' writes; keep/migrate their tests GREEN.
  5. Extend commands/pseo-run.md (tests/commands stays green; monthly + audit paths unbroken).
  6. FULL suite: passed >= N, 0 failed. Re-run tests/skills/test_{the 3} + tests/orchestration/ explicitly.
  7. Self-review (@code-reviewer + @verifier, inline): driver mirrors audit_suite + reuses its D15 dispatch (no
     spine/sibling-driver edit); 3 relocations write-only + writer-preserved; the dependency chain works in order
     (quote the integration test); per-step D classification justified + reported; monthly + audit byte-unchanged;
     immutability; no file outside SCOPE; no D10.

DURUR (stop + report, do not guess):
  - A sheet is NOT a snapshot (has a date/run col) → STOP.
  - A transform CLI cannot run headless / needs a live MCP or real workbook to produce output → STOP + report.
  - A dependent transform's prior-sheet input mechanism can't be satisfied without editing the CLI or the spine → STOP.
  - A skill test breaks for a reason you can't preserve by a faithful 1b2 migration → STOP.
  - You need to edit the frozen spine OR a shipped sibling driver (monthly/audit) → STOP.
  - Any out-of-scope file needs editing, or a new command/schema file is required → STOP + report.

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line; the new test counts; the 3 skill tests + tests/orchestration/ all green.
  - The STEPS table shipped (name, sheet, output_file, writer, expected_tool, verification_class) + per-step
    input→output cardinality + the code_verified/model_attested D decision per step.
  - The dependency-chain proof: the integration test runs the 3 CLIs in order + the dependent steps consume the
    prior committed sheet; quote the mechanism (how cluster_map / new_content_plan receive the prior rows).
  - The 3 relocations: quote each old append → new committer.commit(...writer=); writer preserved; sheets snapshots.
  - /pseo-run `setup` branch: confirm monthly + audit byte-unchanged; all 3 workflows now dispatch.
  - Confirm: spine + sibling drivers NOT edited; whether you IMPORTED audit_suite's D15 dispatch or mirrored it
    (+ the O4 duplication note: 3 workflows now share this driver pattern); no file outside SCOPE; no D10.
  - Any DURUR hit, out-of-scope need, or assumption (esp. a step made model_attested + why; the dependency mechanism).
```
