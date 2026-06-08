# AMO Batch 3b — Replicate the orchestrator to `audit-suite` (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 3, 2nd batch. 3a (lint #1) shipped (HEAD `eeda65f`, suite
> **2098 / 0**). Süleyman picked **audit-suite FIRST** + serial. This replicates the proven monthly-maintenance
> orchestrator (1b spine + 1d shape + 1b2 write-relocation) to a 2nd workflow: `audit`. **Sized for a max-effort
> Opus-4.8 1M worker** — full files inlined below, bigger scope. The manager pre-resolved the two mechanical
> traps (the `schema_audit.json ≠ schema` 1d.1 filename mismatch; heterogeneous per-step provenance) and gives a
> precise framework for the one real design seam (the `silent_skip` gate vs analysis-cardinality). Paste the
> fenced block into a fresh Claude Code session (Opus 4.8, 1M context) at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 3b of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 2098 at HEAD eeda65f; a single MCP-availability-gated test
  may make it read 2097/8 — the floor is the passed+skipped TOTAL, which must not drop) BEFORE any change. END
  green with passed strictly >= your measured N and 0 failed. EVERY existing test MUST stay green — especially
  tests/skills/test_tech_audit.py, test_schema_audit.py, test_on_page_audit.py, test_cannibalization.py and the
  whole tests/orchestration/ tree.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (build new objects, never mutate inputs); no leftover debug prints; small functions
  (<50 lines); files 200-400 lines; clear names; no hardcoded secrets.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.
- The 1b spine is FROZEN: you may IMPORT scripts/orchestration/{run_step,verify,committer,coverage,remediation}
  but must NOT edit them. If you think you need to, STOP + report (you almost certainly don't — the spine is
  deliberately flexible; see CONFIRMED FACTS).

WHY THIS BATCH EXISTS (read carefully):
Faz 1 built ONE orchestrated workflow — `monthly` (gsc-pull → quick-wins + content-decay → monthly-report) —
as a hard-coded ordered Python sequence (Path A, no DAG engine). Faz 3 REPLICATES that proven pattern to more
workflows. This batch builds the 2nd: `audit` (the technical-SEO audit suite). Same shape as monthly: for each
STRUCTURED step the MODEL makes the MCP call(s) + writes a provenance-stamped raw drop, runs the step's EXISTING
transform CLI to a per-step output file, then a thin Python DRIVER verifies (identity+content+freshness) +
commits (idempotent replace) + records coverage. Code guarantees every step RAN and its output is gated; the
model does the un-gateable MCP work. This is the spec §7 Phase-1 seam applied to a 2nd workflow.

Two sub-jobs, exactly mirroring how monthly was built:
  (1) WRITE-RELOCATION (the 1b2 pattern): the 4 audit skills currently write master.xlsx via a `transaction.append`
      call embedded in SKILL.md prose. Relocate each into `committer.commit(...)` (idempotent `transaction.replace`)
      so re-running a step never duplicates rows — exactly what 1b2 did for gsc-pull/quick-wins/content-decay.
  (2) WORKFLOW WIRING: a NEW driver `scripts/orchestration/workflows/audit_suite.py` (mirror
      monthly_maintenance.py) + extend `/pseo-run` to dispatch the `audit` workflow (today it DURUR's on any
      non-`monthly` arg).

CONFIRMED FACTS (verified against the code 2026-06-08 — do NOT re-derive):

A) THE SPINE API you import (FROZEN — do not edit):
   - StepSpec (scripts/orchestration/run_step.py), frozen dataclass:
       name:str, raw_path:Path, sheet:str, transform:Callable[[list[dict]],list[dict]],
       verification_class:str="code_verified", required:bool=True,
       expected_site_url:str|None=None, expected_window:str|None=None, expected_tool:str|None=None,
       observed_mcp:tuple[str,...]=().
   - run_step(spec, *, run_id, project_slug, workspace_root, workbook_path, now_epoch,
       max_age_seconds=86400, schema_path=None, commit_fn=committer.commit) -> coverage-step dict.
       It: verify_raw_drop(spec.raw_path, expected_run_id, expected_slug, now_epoch, expected_site_url,
       expected_window, expected_tool) → if not ok: status missing(missing_file)/failed; else rows_out =
       spec.transform(vr.rows); result = commit_fn(workbook_path, spec.sheet, rows_out, run_id=, project_slug=,
       schema_path=); scored = result.rows_affected; status = "failed" if silent_skip_exceeds(input_count,
       scored) else "satisfied".
   - verify_raw_drop gates a raw drop dict {"provenance":{run_id,slug,site_url,window,tool,fetched_at,
       declared_count}, "rows":[...]}. It checks run_id, slug, then site_url/window/tool ONLY IF the spec passed
       a non-None expectation (None = "this step does not pin that field"), then freshness (mtime/fetched_at vs
       max_age 24h), then truncation (declared_count == len(rows)). Stable reason codes; never raises for a bad
       drop. THIS IS WHY heterogeneous audit sources are fine: pin expected_tool per step, set expected_window=
       None (audit is point-in-time, not a date window), pin expected_site_url only for GSC-sourced steps.
   - committer.commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None, state_root=None,
       writer="orchestrator") -> WriteResult (.rows_affected). It wraps transaction.replace (whole-block replace
       from the schema's data_start_row → idempotent re-run, no dup). PASS writer="<skill-name>" per step to
       PRESERVE the writer identity the skill stamped today (1b2 preserved this).
   - silent_skip_exceeds(input_count, scored_count, max_ratio=0.5): True iff (input-scored)/input > 0.5 (input>0).
       run_step calls it with the DEFAULT 0.5 — you cannot change that without editing the frozen spine. SEE the
       "SILENT-SKIP / analysis-cardinality" design rule below — this is the one real seam.
   - coverage.build_step / derive_verdict / build_record / write_coverage and remediation.{remediation,render}
       are the same modules monthly uses — import + reuse, do not duplicate.

B) THE TEMPLATE — scripts/orchestration/workflows/monthly_maintenance.py (READ IT IN FULL; mirror its shape):
   - A module-level STEPS tuple (one dict per structured step) + inbox_path()/output_path()/_output_loader()
     + _resolve_site_url() + build_steps() (one StepSpec per STEPS entry) + run() (runs steps, builds+writes
     coverage, applies a workflow-completion guard) + a CLI (_build_arg_parser/main with --run-id --slug
     --workspace-root --workbook --now-epoch [--no-write] [--engine-version]).
   - KEY 1d.1 LESSON baked into monthly: output_path is keyed by the step's SHEET because monthly's CLIs happen
     to write {sheet}.json (gsc_pull writes gsc_performance.json and the step's sheet is "gsc_performance"). The
     raw inbox drop is keyed by STEP NAME. **YOUR audit CLIs BREAK this assumption — see C.**

C) THE 4 AUDIT STEPS — the audit suite = these 4 discovery skills (each writes ONE snapshot master.xlsx sheet
   via a transaction.append in SKILL.md prose + has an EXISTING transform CLI). Verified facts:

   | step name      | master sheet     | CLI OUTPUT FILE (verified!)  | primary MCP tool (gated drop)              | transform CLI + inputs |
   |----------------|------------------|------------------------------|--------------------------------------------|------------------------|
   | tech_audit     | tech_seo         | tech_seo.json                | mcp__dataforseo__on_page_lighthouse        | scripts/discovery/tech_audit_transform.py --lighthouse <drop> --content-parsing <drop2> [--url-cap N] --output-dir <dir> |
   | schema_audit   | schema           | schema_audit.json  ⚠️MISMATCH | (SF live OR file-based → NO pinned tool)    | scripts/discovery/schema_audit_transform.py --raw-sf <drop> [--raw-dfs <drop2>] --output-dir <dir> |
   | on_page_audit  | on_page_audit    | on_page_audit.json           | mcp__dataforseo__on_page_content_parsing   | scripts/discovery/on_page_audit_transform.py --raw-content-parsing <drop> [--raw-gsc <drop2>] --output-dir <dir> |
   | cannibalization| cannibalization  | cannibalization.json         | mcp__gsc__search_analytics                 | scripts/discovery/cannibalization_transform.py --raw <drop> [--min-impressions N] --output-dir <dir> |

   - ⚠️ 1d.1 TRAP (manager-found): `schema_audit_transform.py` writes **schema_audit.json** but its master sheet
     is **schema**. The other 3 CLIs write `{sheet}.json`. So you CANNOT key the loader by `{sheet}.json` like
     monthly does. Your STEPS table MUST carry an explicit `output_file` per step (committer writes to `sheet`;
     the loader reads `output_file`). An INTEGRATION test (below) must run each REAL CLI and assert it writes its
     declared output_file — locking this against drift.
   - All 4 sheets (tech_seo, schema, on_page_audit, cannibalization) are SNAPSHOTS (no date/run/snapshot column
     in schemas/master-excel.schema.json — VERIFY this yourself before relying on it) → today's transaction.append
     is a latent dup-on-re-run bug → committer.commit (replace) is the correct relocation, identical to 1b2.
   - Heterogeneous sources (the spine handles it): tech_audit + on_page_audit are DFS-primary; cannibalization is
     GSC-primary (pin expected_site_url from project.config gsc.site_url, like monthly); schema_audit is SF-or-
     file (pin NO tool — expected_tool=None). Pin expected_window=None for ALL 4 (audit ≠ date window).
   - Multi-input CLIs: tech_audit (--lighthouse + --content-parsing), schema_audit (--raw-sf + optional --raw-dfs),
     on_page_audit (--raw-content-parsing + optional --raw-gsc) each take TWO inputs (like content_decay's
     --recent+--previous). Per step the driver gates the PRIMARY drop (the gated one in the table); the SECONDARY
     drop is an additional CLI input the model writes but the driver does not gate.

D) SILENT-SKIP / analysis-cardinality — THE ONE REAL DESIGN SEAM (resolve per step, REPORT each):
   monthly's steps are INGESTION-shaped (raw rows ≈ committed rows), so the silent_skip gate (>50% raw→committed
   drop ⇒ "failed") fits. AUDIT transforms can ANALYZE (aggregate/filter), so a step could legitimately commit
   <50% of its raw input and the gate would FALSE-FAIL it. For EACH step, read the transform's output construction
   and classify:
     • input ≈ output (emits ~one row per input URL/entity, like on_page_audit per-URL, content_decay per-URL):
       silent_skip-safe → verification_class="code_verified" (the default; the gate is meaningful).
     • output << input by DESIGN (e.g., cannibalization groups query-page rows down to per-conflict rows): you
       MUST do ONE of:
         (a) PREFERRED — have the model drop the raw at the transform's INPUT granularity such that input_count
             reflects the rows the transform actually consumes 1:1 (so the gate stays meaningful), OR
         (b) if (a) is not faithful, set that step's verification_class="model_attested" with a one-line code
             comment rationale (the identity+content+freshness gate STILL runs; only the silent_skip count
             check is advisory for an analysis step).
   Do NOT weaken silent_skip for ingestion-shaped steps, and do NOT let it false-fail an analysis step. REPORT
   the per-step input→output cardinality + your code_verified/model_attested choice + why. (This is exactly the
   honest ≤5%-scope split: structured ingestion is code-verified; analysis that legitimately reshapes is attested.)

E) /pseo-run TODAY (commands/pseo-run.md): supports ONLY `monthly` — "Workflow `monthly` değilse … DURUR".
   You ADD an `audit` branch: resolve the project, create/resume the run via workflow_runner with the 4 audit
   steps, document the per-step recipe (MCP tool(s) → provenance-stamped raw drop(s) → transform CLI →
   {output_file}), then invoke the audit_suite driver. Mirror monthly's Section structure + its Turkish operator
   remediation surface. Editing an EXISTING command file adds NO new command → NO D10.

F) D10 / count-guards: this batch adds NO new commands/*.md and NO new schemas/*.json (audit_suite.py is a script;
   the workflow has no new schema — it reuses coverage.schema.json). So NO plugin.json/marketplace.json/draft-count
   bump. The new driver is NOT a wired hook → NOT a RUNTIME_HOOK_SCRIPTS entry. If you find yourself needing a new
   command or schema file, STOP + report (the manager applies count-guards).

ORIENT FIRST (read in full, do not change yet):
- scripts/orchestration/workflows/monthly_maintenance.py (the template — your audit_suite.py mirrors it).
- commands/pseo-run.md (the command you extend — note Sections 1-7 + the monthly recipe + remediation surface).
- scripts/orchestration/{run_step.py, verify.py, committer.py, coverage.py} (the spine you import; ~halve a page each).
- The 4 transform CLIs scripts/discovery/{tech_audit,schema_audit,on_page_audit,cannibalization}_transform.py —
  specifically each `_parse_args` + the `if args.output_dir:` write block (confirm the output filename in C) AND
  the OUTPUT-ROW construction (for the cardinality classification in D).
- The 4 skills' SKILL.md transaction.append blocks to relocate: skills/discovery/{tech-audit (~L279),
  schema-audit (~L285-293), on-page-audit (~L261), cannibalization (~L204-215)} — note the writer= identity +
  the exact Step that writes; you relocate the WRITE only (append → committer.commit), nothing else.
- The 4 skills' tests tests/skills/test_{tech_audit,schema_audit,on_page_audit,cannibalization}.py — see what
  they pin (1b2 found the skill tests pin TRANSFORM + frontmatter + output_ref, NOT the write mechanism — low
  pin; confirm, and if a test pins the OLD append wording, migrate it like 1b2 did, preserving/strengthening it).
- scripts/state/workflow_runner.py (create_run/resume — same calls /pseo-run uses for monthly).
- schemas/master-excel.schema.json — confirm the 4 sheets are snapshots (no date/run col) + their data_start_row.

SCOPE — create/modify ONLY these files:
  NEW  scripts/orchestration/workflows/audit_suite.py        (the driver, mirror monthly_maintenance.py)
  NEW  tests/orchestration/test_audit_suite.py               (driver unit/e2e: stub committer, the 5 raw-drop
                                                              scenarios per step shape, verdict, completion)
  NEW  tests/orchestration/test_audit_suite_cli_integration.py  (1d.1 GUARD: run each REAL transform CLI on a
                                                              minimal synthetic drop, assert it writes its declared
                                                              output_file where the loader reads)
  EDIT commands/pseo-run.md                                  (add the `audit` workflow branch + recipe + remediation)
  EDIT skills/discovery/tech-audit/SKILL.md                  (relocate transaction.append → committer.commit, writer preserved)
  EDIT skills/discovery/schema-audit/SKILL.md
  EDIT skills/discovery/on-page-audit/SKILL.md
  EDIT skills/discovery/cannibalization/SKILL.md
  (EDIT tests/skills/test_*.py ONLY if a test pins the old write wording and must migrate — 1b2-style,
   preserve/strengthen the contract; if a skill test breaks for a reason you can't preserve → STOP + report.)

SPEC — scripts/orchestration/workflows/audit_suite.py (mirror monthly_maintenance.py; reuse, don't reinvent):
  - Module STEPS tuple, one dict per step, with an EXPLICIT output_file (the 1d.1 fix):
      ("tech_audit",      sheet="tech_seo",        output_file="tech_seo.json",        writer="tech-audit",
                          tool="mcp__dataforseo__on_page_lighthouse",      site_url=False)
      ("schema_audit",    sheet="schema",          output_file="schema_audit.json",    writer="schema-audit",
                          tool=None,                                       site_url=False)
      ("on_page_audit",   sheet="on_page_audit",   output_file="on_page_audit.json",   writer="on-page-audit",
                          tool="mcp__dataforseo__on_page_content_parsing", site_url=False)
      ("cannibalization", sheet="cannibalization", output_file="cannibalization.json", writer="cannibalization",
                          tool="mcp__gsc__search_analytics",               site_url=True)
  - inbox_path(workspace, run_id, slug, step) -> .../_state/inbox/{run_id}/{step}.json  (PRIMARY raw drop, by step name).
  - output_path(workspace, run_id, slug, output_file) -> .../_state/transform/{run_id}/{output_file}  (KEY BY
    output_file, NOT {sheet}.json — the schema_audit fix).
  - _output_loader(output_file_path): same loader closure as monthly (ignore raw rows, return the model-produced
    output rows from the file; accept a bare list OR {"rows":[...]}; raise a WorkflowError if missing/malformed).
  - build_steps(run_id, slug, workspace): one StepSpec per STEPS entry —
      raw_path=inbox_path(...step name...), sheet=entry.sheet, transform=_output_loader(output_path(...output_file...)),
      verification_class=<your D-classification>, expected_tool=entry.tool, expected_window=None,
      expected_site_url=(_resolve_site_url(...) if entry.site_url else None), observed_mcp=(entry.tool,) if tool else ().
  - run(...) mirrors monthly: run each step via run_step (commit_fn injectable for the e2e stub), build coverage,
    derive verdict, write coverage. The audit suite's DELIVERABLE IS the 4 committed sheets — there is NO
    model_attested "report" step like monthly-report (do NOT invent one). The verdict derives from the 4 steps.
  - CLI main(): --run-id --slug --workspace-root --workbook --now-epoch [--no-write] [--engine-version]; print
    verdict + remediation.render(...) on non-pass (Turkish one-line fix: `/pseo-run audit <slug> --resume`).
  - Anchor any file paths relative; module clock-free (now_epoch passed in, like monthly). Keep functions <50 lines.

SPEC — commands/pseo-run.md `audit` branch:
  - Section 1: when the workflow arg is `audit`, resolve project (same as monthly) — do NOT DURUR.
  - Section 2: workflow_runner.create_run(skill="audit-suite", project_slug=PROJECT, steps=[{"name":"tech_audit"},
    {"name":"schema_audit"},{"name":"on_page_audit"},{"name":"cannibalization"}]); --resume path identical to monthly.
  - Section 3 (recipe): per step — the MCP tool(s) → the provenance-stamped raw drop(s) at
    _state/inbox/{run_id}/{step}.json (+ secondary drop names for the 2-input CLIs) → the transform CLI with its
    EXACT args (from table C) writing {output_file} into _state/transform/{run_id}/. Provenance block shape =
    monthly's (run_id, slug, site_url[if GSC], window=null for audit, tool, fetched_at, declared_count==len(rows)).
    For schema_audit note the SF-opt-in/file-based path (provenance tool may be the SF export tool or omitted).
  - Section 4: invoke `python3 -m scripts.orchestration.workflows.audit_suite --run-id … --slug … --workspace-root …
    --workbook … --now-epoch "$(date +%s)"`.
  - Sections 5-7: NO report step (unlike monthly); verdict + Turkish remediation (`/pseo-run audit <slug> --resume`)
    + dependency list (the 4 skills + their CLIs + the spine). Keep the monthly section UNCHANGED — you ADD the
    audit branch alongside it (a model reading the command must handle BOTH workflows).

SPEC — the 4 write-relocations (1b2 pattern, per skill):
  - In each SKILL.md, find the SINGLE `transaction.append(...)` that writes the audit sheet and replace it with
    `committer.commit(workbook_path, "<sheet>", rows, run_id=<run_id>, project_slug=<slug>, writer="<skill-name>")`
    (preserve the writer identity; add run_id from the workflow handle). Change NOTHING else in the skill (the
    transform, the schema-lock, the approval prompt, the AMBER/DURUR logic all stay). This fixes the snapshot
    dup-on-re-run bug on all 4 sheets, identical to 1b2's fix for the monthly sheets.
  - If a skill's test pins the old `transaction.append` wording, migrate it (1b2-style) to assert the
    committer.commit contract — preserve or strengthen, never weaken. If it only pins transform/frontmatter/
    output_ref (the 1b2 finding), no test change is needed.

SPEC — tests/orchestration/test_audit_suite_cli_integration.py (the 1d.1 GUARD — do this EARLY, it de-risks all):
  - For EACH of the 4 steps: build a minimal valid synthetic input file (the smallest shape the CLI accepts for
    its --lighthouse/--content-parsing / --raw-sf / --raw-content-parsing / --raw drop), run the REAL CLI via
    subprocess (python3 the transform with --output-dir tmp), and assert the file `<output_file>` (tech_seo.json,
    schema_audit.json, on_page_audit.json, cannibalization.json) EXISTS in tmp. This locks the step→output_file
    map (esp. schema_audit≠schema) against drift and proves the driver's loader reads where each CLI writes.
  - If a CLI needs a richer input than you can synthesize, assert the output_file via the CLI's argparse/help or
    a fixture in tests/ — but PREFER a real run. If a CLI cannot be driven headless at all → STOP + report (that
    is a real integration gap the manager must know about, exactly the 1d.1 class).

SPEC — tests/orchestration/test_audit_suite.py (driver e2e with a STUB committer, no live model/MCP/workbook):
  - Reuse the monthly e2e stub pattern (an injected commit_fn returning a WriteResult-like with rows_affected).
    Per step shape, cover: correct drop → satisfied; missing drop → missing; wrong run_id/slug → failed
    (identity); stale → failed; truncated (declared_count≠len) → failed; and a cardinality case proving your D
    classification (an analysis step that drops >50% is NOT false-failed). Assert the run verdict + that the
    driver keys output_file (a step whose CLI writes schema_audit.json is loaded, not schema.json).

TDD ORDER:
  1. Baseline pytest (record N).
  2. test_audit_suite_cli_integration.py FIRST for the 4 CLIs (RED until you know each output_file; it should go
     GREEN immediately against the REAL CLIs once you assert the verified names — it is your drift lock + proof).
  3. test_audit_suite.py (RED — driver doesn't exist). Implement audit_suite.py → GREEN.
  4. Relocate the 4 skills' writes; keep/ migrate their tests GREEN.
  5. Extend commands/pseo-run.md (no test pins command PROSE beyond the existing command-guard tests — confirm
     tests/commands stays green; the `audit` branch must not break the monthly path).
  6. FULL suite: passed >= N, 0 failed. Re-run tests/skills/test_{the 4}.py + tests/orchestration/ explicitly.
  7. Self-review (@code-reviewer + @verifier, inline): driver mirrors monthly + keys output_file (quote the
     schema_audit case); spine imported not edited; 4 relocations are write-only + writer-preserved; the D
     cardinality choice per step is justified + reported; immutability; no file outside SCOPE; no D10.

DURUR (stop + report, do not guess):
  - A sheet turns out NOT to be a snapshot (has a date/run column) → replace would lose history → STOP (that
    step needs append semantics, a manager decision).
  - A transform CLI cannot be run headless / needs a live MCP or a real workbook to produce output → STOP +
    report (the integration gap).
  - A skill's existing test breaks for a reason you cannot preserve by a faithful 1b2-style migration → STOP.
  - You need to edit the frozen spine (run_step/verify/committer/coverage) → STOP (you don't; pin via StepSpec).
  - Any out-of-scope file needs editing, or a new command/schema file is required → STOP + report.

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line (passed/skipped/failed); the new test counts; the 4 skill tests + the
    orchestration tests all green.
  - The STEPS table you shipped (name, sheet, output_file, writer, expected_tool, verification_class) and — for
    EACH step — its measured input→output cardinality + WHY code_verified vs model_attested (the D decision).
  - The 1d.1 integration proof: each CLI writes its declared output_file (call out schema_audit.json ≠ schema).
  - The 4 relocations: quote each old `transaction.append(...)` → new `committer.commit(... writer="…")`; confirm
    writer identity preserved + nothing else in the skill changed; confirm all 4 sheets verified snapshots.
  - The /pseo-run `audit` branch: confirm the monthly path is UNCHANGED and both workflows now dispatch.
  - Confirm: spine NOT edited; no file outside SCOPE; no D10; no new RUNTIME_HOOK_SCRIPTS entry.
  - Any DURUR hit, out-of-scope need, or assumption (esp. any step you made model_attested + why).
```
