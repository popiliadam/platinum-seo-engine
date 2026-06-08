# AMO Batch 3d — Replicate the orchestrator to `content-pipeline` (ARTIFACT-based) (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 3, replicate #3 — the LAST + structurally NOVEL one. HEAD
> `32d243b`, suite **2155 / 0**. content-pipeline does NOT fit the data-pipeline pattern (monthly/audit/setup):
> its deliverable is a **blog HTML artifact** (`outputs/blog/.../article.html`), NOT master.xlsx rows — there are
> NO transform CLIs, NO raw drops, NO sheet commits (so **NO 1b2 relocations**). It needs a NEW **artifact-based
> driver**: per-step verify = *artifact exists* + `content_validator.validate_content(html).verdict() != "RED"`
> (the deterministic AI-disclosure gate batch 2e enforces). Content QUALITY is `model_attested` (spec §11); the
> AI-disclosure hard-rule IS code-verified. Composition (Süleyman 2026-06-08): **new-blog → generate-images →
> faq-optimization**. This is a 2nd workflow SHAPE → it informs O4 (a shared *data*-driver + a separate
> *artifact*-driver; vindicates Path A). Sized for a max-effort Opus-4.8 1M worker. Paste the block into a fresh
> Claude Code session at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 3d of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 2155 at HEAD 32d243b; a single MCP-availability-gated test may
  make it read 2154/8 — the floor is the passed+skipped TOTAL, which must not drop) BEFORE any change. END green
  with passed strictly >= your measured N and 0 failed. EVERY existing test MUST stay green — especially
  tests/validation/test_content_validator.py + tests/hooks/test_validate_content_write.py + tests/hooks/test_ai_disclosure_rescan.py
  + the whole tests/orchestration/ tree.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability; no leftover debug prints; small functions (<50 lines); files 200-400 lines; clear names.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.
- The 1b spine + shipped drivers are FROZEN: import scripts/orchestration/{coverage,remediation} (+ the content
  validator), but do NOT edit run_step/verify/committer/coverage/monthly_maintenance/audit_suite/new_project_setup.

WHY THIS BATCH EXISTS (read carefully):
monthly/audit/setup are DATA pipelines (the model makes an MCP call → drops raw JSON → runs a transform CLI →
the driver verifies the drop + commits ROWS to a master.xlsx sheet). content-pipeline is DIFFERENT: it produces
a BLOG HTML ARTIFACT. The model generates `outputs/blog/<post>/article.html` (+ schema.jsonld, meta-tags.json,
images) from a `new_content_plan` row — there is NO transform CLI, NO raw drop, NO sheet to commit. So this
driver CANNOT mirror audit_suite/new_project_setup (which use run_step + verify_raw_drop + committer). It is an
ARTIFACT-based driver: each step is `model_attested` (content QUALITY is not code-checkable — spec §11), and the
per-step verification the CODE owns is: **the expected artifact EXISTS** AND (for an HTML artifact) **it passes
the deterministic AI-disclosure gate** (`content_validator.validate_content(html).verdict() != "RED"` — the same
detector batch 2e's `ai_disclosure_rescan` quarantines with, and Süleyman's hard-constraint #2). So the workflow
GUARANTEES "every production step ran + produced its artifact + the artifact carries no AI-disclosure signal";
it does NOT (and cannot) verify the content is *good* — that's the QA loop, measured separately.

CONFIRMED FACTS (verified against the code 2026-06-08 — do NOT re-derive):

A) THE 3 PRODUCTION STEPS (composition = Süleyman's pick: new-blog → generate-images → faq-optimization). NONE
   writes a master.xlsx sheet (generate-images SKILL.md L110: "never calls transaction.append"; new-blog/faq
   write only `outputs/blog/...`) → THERE ARE NO 1b2 WRITE-RELOCATIONS in this batch.
   | step (order)    | skill              | primary artifact                         | depends on |
   |-----------------|--------------------|------------------------------------------|------------|
   | new_blog        | production/new-blog | outputs/blog/<post>/article.html (+ schema.jsonld, meta-tags.json, upload-instructions.md) | a new_content_plan row (input `new_content_plan_id`) |
   | generate_images | production/generate-images | outputs/images/<...> (+ outputs/blog/<post>/upload-instructions.md) | the new_content_plan row / the new_blog post |
   | faq_optimization| production/faq-optimization | outputs/blog/<post>/article.html (ENHANCED in place) | new_blog's article.html (mode=enhance) |
   - One run produces ONE blog (keyed by the `new_content_plan_id` → a post). The artifact paths are under
     `<workspace>/projects/<slug>/outputs/blog/<post>/...`. CONFIRM the exact `<post>` segment (project slug vs
     a per-post slug derived from the plan row) by reading new-blog's SKILL.md output section — the driver must
     verify THIS run's blog's `article.html`, so the run/recipe supplies the blog's output dir.
   - generate-images uses higgsfield (an EXTERNAL user-MCP, often absent headless) → its artifact verify must be
     EXISTS-only (no content_validator — images aren't HTML); a missing images dir on a headless run is a normal
     `missing`, never a crash.

B) THE ARTIFACT-VERIFY GATE (reuse — do NOT reinvent a detector):
   - `from scripts.validation.content_validator import validate_content` →
     `validate_content(html: str, *, profile=None) -> ContentReport`; `ContentReport.verdict()` ∈ {GREEN,AMBER,RED}
     and `.has_red()`. RED = an AI-disclosure signal in the rendered surface (Süleyman hard-constraint #2).
   - `from scripts.hooks.validate_content_write import is_content_html_path` → True for a blog `outputs/blog/**/*.html`.
   - This is EXACTLY the detector batch 2e (`ai_disclosure_rescan`) reuses — so the workflow-level check and the
     write-time hook agree by construction.

C) WHAT TO REUSE FROM THE SPINE (coverage + remediation only — NOT run_step/verify/committer):
   - `scripts.orchestration.coverage`: `build_step(name, verification_class, status, observed_mcp=[], input_count=?,
     scored_count=?)`, `derive_verdict(steps)`, `build_record(run_id, steps, required_satisfied, verdict,
     project_slug, engine_version)`, `write_coverage(record, workspace_root, project_slug, run_id)`,
     `coverage_path`. Coverage step status ∈ {pending,running,satisfied,missing,failed,skipped} (the 1a frozen enum).
   - `scripts.orchestration.remediation`: `remediation(record, slug=, workflow=)` + `render(...)` (the Turkish
     one-line fix surface). Pass `workflow="content"`.
   - The COMPLETION GUARD pattern (from new_project_setup/audit_suite): every step is `model_attested`, which
     `derive_verdict` treats as SOFT, so a missing step alone would read 'pass'. The deliverable IS the produced
     blog, so `run()` downgrades `pass → incomplete` unless EVERY step is `satisfied`. This is load-bearing (the
     same all-attested situation as `setup`).

D) D10 / count-guards: NO new commands/*.md, NO new schemas/*.json (content_pipeline.py is a script; coverage
   reuses coverage.schema.json). No manifest/count bump. The driver is not a wired hook. If you need a new
   command/schema → STOP + report.

ORIENT FIRST (read in full, do not change yet):
- scripts/orchestration/workflows/new_project_setup.py + audit_suite.py — the COVERAGE/run()/completion-guard/CLI
  shape to mirror (but you will NOT use run_step/verify_raw_drop/committer — those are for data steps).
- scripts/validation/content_validator.py (`validate_content` + `ContentReport`) + scripts/hooks/validate_content_write.py
  (`is_content_html_path`) + scripts/hooks/ai_disclosure_rescan.py (how 2e reuses the same detector — your verify mirrors it).
- The 3 production skills skills/production/{new-blog,generate-images,faq-optimization}/SKILL.md — the EXACT
  artifact paths (esp. new-blog's `outputs/blog/<post>/article.html` — what is `<post>`?), inputs, and the
  new_content_plan_id → post mapping.
- commands/pseo-run.md (monthly Bölüm 2-7 + audit Bölüm 8 + setup Bölüm 9 + the Section-1 routing fork).
- tests/validation/test_content_validator.py (fixtures: a CLEAN blog HTML → GREEN, an AI-disclosure HTML → RED —
  reuse these to test the artifact-verify) + tests/orchestration/test_new_project_setup.py (the e2e driver-test shape).
- scripts/state/workflow_runner.py (create_run/resume).

SCOPE — create/modify ONLY these files:
  NEW  scripts/orchestration/workflows/content_pipeline.py   (the ARTIFACT-based driver)
  NEW  tests/orchestration/test_content_pipeline.py          (driver e2e: artifact-verify scenarios + completion guard)
  EDIT commands/pseo-run.md                                  (add the `content` workflow branch; monthly/audit/setup byte-unchanged)
  (NO skill SKILL.md edits — the production skills write artifacts, not master.xlsx rows; confirm + report if you
   find one that DOES call transaction.append for a content step → then STOP, it's a different design.)

SPEC — scripts/orchestration/workflows/content_pipeline.py (the NEW artifact shape; reuse coverage + remediation):
  - Module STEPS tuple, ORDERED new_blog → generate_images → faq_optimization. Each entry: name; the artifact(s)
    to verify (a relative path under the blog output dir, e.g. "article.html"); `is_html` flag (True → also run
    content_validator; False → exists-only, e.g. images); verification_class="model_attested" for all.
  - `def verify_artifact(artifact_path: Path, *, is_html: bool, profile=None) -> str`: returns a coverage STATUS:
      * not exists → "missing".
      * is_html AND `validate_content(read_text(artifact_path)).has_red()` → "failed" (AI-disclosure signal — the
        deterministic gate fires; this is the CODE-verified part of an otherwise model_attested step).
      * else → "satisfied".
    Pure-ish (reads the file + the frozen detector); never raises for a missing/unreadable artifact (→ missing).
  - `build_steps(...)`/`run(run_id, project_slug, workspace_root, blog_output_dir, now_epoch, *, write=True,
    engine_version=None)`: for each STEP, verify its artifact(s) under `blog_output_dir`, build a coverage step
    (model_attested + the verify_artifact status + observed_mcp=[]), derive verdict, apply the COMPLETION GUARD
    (pass→incomplete unless all satisfied), write coverage. The `blog_output_dir` is THIS run's blog dir
    (`projects/<slug>/outputs/blog/<post>/`) — supplied by the CLI/recipe (it encodes which post). NO committer.
  - CLI main(): --run-id --slug --workspace-root --blog-output-dir --now-epoch [--no-write] [--engine-version];
    print verdict + remediation.render(remediation(record, slug=, workflow="content")) on non-pass (Turkish fix:
    `/pseo-run content <slug> --resume`). Clock-free (now_epoch passed in). Keep functions <50 lines.

SPEC — commands/pseo-run.md `content` branch (new Bölüm 10, mirror setup's Bölüm 9 structure):
  - Section 1 routing: add `content` → Bölüm 10 (keep monthly→2-7, audit→8, setup→9, else→DURUR).
  - Bölüm 10: create_run(skill="content-pipeline", steps=[{new_blog},{generate_images},{faq_optimization}]) +
    --resume; the per-step recipe — the MODEL runs new-blog (produces article.html + assets from a
    new_content_plan row), then generate-images, then faq-optimization (enhances article.html); each write goes
    through the EXISTING content_validator (Write-gate) + ai_disclosure (PostToolUse) hooks AT WRITE TIME. Then the
    driver INDEPENDENTLY re-verifies each artifact (exists + content_validator clean). Driver invocation with
    --blog-output-dir = `projects/<slug>/outputs/blog/<post>/`; verdict + Turkish `/pseo-run content <slug>
    --resume`; dependency list. Monthly + audit + setup BYTE-UNCHANGED — ADD alongside. NOTE the honest scope in
    the prose: the driver guarantees ran+produced+disclosure-clean, NOT content quality (that's the QA loop).
  - Frontmatter `allowed-tools`: the content steps are model generation (Write) + optionally
    mcp__higgsfield__generate_image (generate-images). Add only what the recipe actually invokes; the shell-prog
    matcher test only checks Bash programs (python3/jq/date/mkdir already declared) — no new Bash decl needed.

SPEC — tests/orchestration/test_content_pipeline.py (driver e2e; tmp blog dir; reuse content_validator fixtures):
  - verify_artifact: a CLEAN article.html → "satisfied"; a missing article.html → "missing"; an article.html with
    an AI-disclosure signal (reuse the RED fixture from test_content_validator) → "failed"; an images dir present
    (is_html=False) → "satisfied", absent → "missing".
  - run(): all 3 artifacts clean → verdict "pass"; a missing step → NOT "pass" (completion guard → "incomplete");
    an AI-disclosure-RED article.html → the new_blog/faq step "failed" → verdict reflects it (the disclosure gate
    fires at the workflow level, independent of the write-time hook).
  - CLI smoke: exits 0, prints verdict + the Turkish remediation on a non-pass run; writes the coverage record.

TDD ORDER:
  1. Baseline pytest (record N).
  2. test_content_pipeline.py FIRST (RED — driver absent). Watch it fail.
  3. Implement content_pipeline.py → GREEN.
  4. Extend commands/pseo-run.md (tests/commands stays green; monthly/audit/setup paths unbroken).
  5. FULL suite: passed >= N, 0 failed. Re-run tests/orchestration/ + the content_validator/2e tests explicitly.
  6. Self-review (@code-reviewer + @verifier, inline): driver is ARTIFACT-based (no run_step/committer); the
     verify reuses content_validator (no second detector); the AI-disclosure RED path FAILS the step (quote the
     test); completion guard load-bearing (all model_attested); NO skill relocation (no content step writes a
     sheet); monthly/audit/setup byte-unchanged; spine + sibling drivers untouched; immutability; no file outside
     SCOPE; no D10.

DURUR (stop + report, do not guess):
  - A content step turns out to WRITE a master.xlsx sheet (calls transaction.append) → STOP (that's a data step,
    a different design — report which).
  - `validate_content` needs an argument you can't supply headless (e.g. a live profile/model) → STOP + report
    (it should take a plain html str).
  - The blog artifact path can't be determined for THIS run's post without a live model run → STOP + report (the
    recipe must pass --blog-output-dir).
  - You need to edit the frozen spine / a shipped driver / a skill that writes a sheet → STOP.
  - Any out-of-scope file needs editing, or a new command/schema file is required → STOP + report.

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line; the new test count; tests/orchestration/ + content_validator/2e tests green.
  - The STEPS table (name, artifact, is_html, verification_class) + confirm all model_attested + NO committer/CLI/raw-drop.
  - verify_artifact: quote it; confirm the 3 statuses (satisfied/missing/failed) + that an AI-disclosure RED
    article.html → "failed" (the workflow-level disclosure gate; quote the test) — this is the CODE-verified part
    of the otherwise model_attested content workflow.
  - Confirm NO 1b2 relocation was needed (no content step writes a sheet); the completion guard is load-bearing.
  - /pseo-run `content` branch: confirm monthly/audit/setup byte-unchanged; all 4 workflows dispatch.
  - Confirm: spine + sibling drivers + all skills UNTOUCHED; reuse content_validator (no new detector); no file
    outside SCOPE; no D10. The O4 note: content-pipeline is a 2nd SHAPE (artifact-driver) distinct from the
    data-driver (monthly/audit/setup) — relevant to the shared-driver decision.
  - Any DURUR hit, out-of-scope need, or assumption (esp. the `<post>` path segment + the headless images handling).
```
