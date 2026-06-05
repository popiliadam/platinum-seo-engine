# Skill Contract Remediation — Worker Session Prompts (B1–B6)

> Each fenced block below is a **complete, self-contained prompt**. Open a **fresh Claude Code session at `/Users/apple/Documents/platinum-seo-engine`**, paste ONE block, let it finish, then relay its final REPORT back to the manager session. Run in order B1 → B6 (B1 is the urgent active break). Batches are file-disjoint, so parallel is possible, but sequential keeps decisions reviewable.
>
> Manager roadmap (sequencing, decision register, conventions): `docs/superpowers/plans/2026-06-04-skill-contract-remediation-roadmap.md`
> Full evidence for every finding: `docs/audits/2026-06-04-skill-contract-audit.findings.json` (match on the title/file).

---

## B1 — Reporting / portfolio suite (19 findings)

```text
You are a WORKER fixing skill-contract findings in the Platinum SEO Engine (Python, pytest). Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch B1 of a 6-batch remediation managed from another session. Work ONLY within this batch's scope. Do NOT git commit or push — when done, STOP and print the REPORT (the manager commits after review).

WHY THIS EXISTS
A 2026-06-04 contract audit found that SKILL.md files promise things their code/schema/tests no longer deliver. Your job is to make the contract honest again. The highest-priority issue lives here: the schema raised active_projects.maxItems 8→12, but these reporting skills still hardcode/cite 8 and DURUR-halt on the live ~10-project portfolio — a real runtime break.

SCOPE — edit ONLY these 6 skills and their artifacts (SKILL.md + transform + paired test + report template):
  portfolio-heatmap, portfolio-kpi-trend, portfolio-monthly-roundup, portfolio-overview, portfolio-task-heatmap, portfolio-weekly-brief
  → skills/reporting/<name>/SKILL.md ; scripts/reporting/portfolio_*.py ; tests/skills/test_portfolio_*.py ; templates/reports/portfolio-*.template.md
Touching any other file is out of scope — if a fix seems to need one, STOP and report it. The schema files are CORRECT (authority); align skills TO the schema, do not edit schemas.

GOVERNING DOCS (read first, they are in-repo):
  docs/superpowers/plans/2026-06-04-skill-contract-remediation-roadmap.md   (Shared conventions + Decision register)
  docs/audits/2026-06-04-skill-contract-audit.findings.json                 (verbatim evidence; match by title/file)

METHOD (per finding):
  1. Baseline FIRST: PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q  → record exact "N passed, M skipped". You must end green with N strictly larger.
  2. RE-READ the cited file — line numbers are from 2026-06-04 and may have drifted. Re-locate the evidence. If a finding no longer reproduces, mark it STALE in the report and skip (do not invent a fix).
  3. Classify: DOC (prose/cross-ref) → edit text; CODE → write a FAILING regression test FIRST, then fix the transform/template; TEST → write the real assertion (watch it fail against current code), then it passes. Never fake red.
  4. Verify the authority before you write a number: read schemas/portfolio-config.schema.json#active_projects.maxItems (=12) and the relevant enum/line in the schema you cite. Prefer reading maxItems from the loaded schema over re-hardcoding 12.
HARD RULES: immutability (return new objects, no mutation); no print/console debug; no hardcoded magic where a schema value exists; small diffs; do not hand-edit _state/*.jsonl. After fixes, run @code-reviewer + @verifier (Dev-QA loop) and address what they flag.

THE 19 FINDINGS (full evidence in findings.json):
  B1-01 [HIGH code] scripts/reporting/portfolio_heatmap.py — primary_source enum is 10 but schema has 11; add 'new_content_plan' to PRIMARY_SOURCE_ENUM so it gets a zero-count bucket (the "nothing silently missing" promise); update SKILL.md '10-enum'→'11-enum' + the list.
  B1-02 [HIGH code] scripts/reporting/portfolio_kpi_trend.py:~41 — ACTIVE_PROJECTS_MAX hardcoded 8; set to 12 (or read schema maxItems); update the >MAX guards; update test fixture range(1,10)→range(1,14).
  B1-03 [HIGH doc] skills/reporting/portfolio-heatmap/SKILL.md — "maxItems = 8"→12 at frontmatter + body (≈L74,135-136,217-218); align ACTIVE_PROJECTS_MAX constant too.
  B1-04 [HIGH doc] skills/reporting/portfolio-kpi-trend/SKILL.md — "maxItems = 8" cited 5× (≈L10,71,150,215,268) → 12, lockstep with the transform fix.
  B1-05 [HIGH doc] skills/reporting/portfolio-monthly-roundup/SKILL.md — L11 'maxItems=8'→12, L254-255 '> 8'→'> 12', transform ACTIVE_PROJECTS_MAX 8→12 + error msg; add a 12-ok/13-fail test case.
  B1-06 [HIGH doc/code] skills/reporting/portfolio-overview/SKILL.md — ceiling 8→12 at L9,15-16,69,165-166,214 + module docstring + ACTIVE_PROJECTS_MAX.
  B1-07 [MED test] tests/skills/test_portfolio_overview.py:~192-204 — sentinel test has a false docstring and passes only via the stale constant; after the ceiling fix, rewrite to assert 12-entry OK and 13-entry raises, with a truthful docstring.
  B1-08 [MED code] templates/reports/portfolio-weekly-brief.template.md:39 — literal `$run_id` leaks into every published brief; either remove the Run ID line (no run_id concept) OR supply run_id in build_template_vars(). Pick removal unless the run_id is meaningful; keep build/template in sync.
  B1-09 [MED doc/code] skills/reporting/portfolio-task-heatmap/SKILL.md + transform — ceiling 8→12 (SKILL L154,218-219 + ACTIVE_PROJECTS_MAX); a config with 9-12 currently validates but the transform raises.
  B1-10 [LOW code] templates/reports/portfolio-heatmap.template.md:39 — `$run_id` never supplied; remove the line or supply it in build_report_markdown (match B1-08's choice).
  B1-11 [LOW code] templates/reports/portfolio-monthly-roundup.template.md:52 — same `$run_id` leak; same resolution.
  B1-12 [LOW code] scripts/reporting/portfolio_overview.py:~453-460 — build_report_markdown uses safe_substitute but docs a render_template.py convention; either switch to .substitute() and keep keys complete, or update the doc note to say safe_substitute is intentional.
  B1-13 [LOW doc] skills/reporting/portfolio-task-heatmap/SKILL.md:45 — consumes[] points to a non-existent master.xlsx#consistency-report sheet; repoint to the real standalone artifact (consistency-report-{slug}.json).
  B1-14 [LOW code] templates/reports/portfolio-task-heatmap.template.md:51 — `$run_id` leak; same resolution as B1-10.
  B1-15 [LOW doc] skills/reporting/portfolio-kpi-trend/SKILL.md — event_type "10-value enum"→"12-value" (≈L12,77,139).
  B1-16 [LOW doc] skills/reporting/portfolio-kpi-trend/SKILL.md:270 — statusEnum cross-ref 'line 20'→ real line (verify; ~22), or drop brittle line numbers for a JSON pointer.
  B1-17 [LOW doc] skills/reporting/portfolio-kpi-trend/SKILL.md:132 — master_task 'lines 269-303'→ real range (verify), or JSON pointer.
  B1-18 [LOW doc] skills/reporting/portfolio-overview/SKILL.md — stale schema line numbers (statusEnum, dashboard, master_task) at L121,216,218-219; re-verify against the live schema and correct, or switch to JSON pointers.
  B1-19 [LOW doc] skills/reporting/portfolio-weekly-brief/SKILL.md:133-134 — '<600 line per ADR-027' misattributed (ADR-027 = <1500L); drop 'per ADR-027' or cite the right policy.

CONSISTENCY: B1-08/10/11/14 are the same `$run_id` theme — resolve them the SAME way across all four templates. B1-02/03/04/05/06/09 are the same active_projects 8→12 theme — keep constant + SKILL.md + tests in lockstep per skill.

VERIFICATION: full suite green with count > baseline; new/updated tests for B1-01,02,05,07 (and any template change gets a build-render assertion). Run @code-reviewer + @verifier.

REPORT (print at the end, do not commit):
  - Baseline pytest (before) and final pytest (after) exact counts.
  - Per finding: FIXED / STALE / ESCALATED + one line (file + what changed). Note doc-vs-code-vs-test.
  - $run_id decision taken (remove vs supply) and that all 4 templates match.
  - New tests added (names).
  - git diff --stat output.
  - Anything out of scope you had to leave for the manager.
  - Confirm: no schema files edited, no out-of-scope files, no commit made.
```

---

## B2 — Reporting / core: monitoring-weekly, monthly-report, weekly-summary (8 findings)

```text
You are a WORKER fixing skill-contract findings in the Platinum SEO Engine (Python, pytest). Repo root: /Users/apple/Documents/platinum-seo-engine. Batch B2. Work ONLY in scope. Do NOT git commit/push — STOP and print the REPORT when done.

WHY: This batch carries the single most safety-relevant finding (an append-only events.jsonl mutation that contradicts the skill's READ-ONLY basis) plus capability-honesty fixes.

SCOPE — only these 3 skills + artifacts:
  monitoring-weekly, monthly-report, weekly-summary
  → skills/reporting/<name>/SKILL.md ; scripts/reporting/weekly_summary.py ; tests/skills/test_monitoring_weekly.py ; tests/skills/test_weekly_summary.py
Out-of-scope files → STOP and report.

GOVERNING DOCS (read first): docs/superpowers/plans/2026-06-04-skill-contract-remediation-roadmap.md (conventions + decision register) ; docs/audits/2026-06-04-skill-contract-audit.findings.json (evidence).

METHOD: (1) baseline pytest, record counts. (2) Re-read each cited file (line numbers may have drifted); STALE if not reproducing. (3) DOC→edit; CODE→failing regression test first; TEST→real assertion first. Never fake red. (4) HARD RULES: append-only _state/*.jsonl is sacred — NEVER add a mutation to it; immutability; no debug prints. Run @code-reviewer + @verifier after.

THE 8 FINDINGS:
  B2-01 [HIGH safety] skills/reporting/monthly-report/SKILL.md:~174-210 — a "Q-RP-01 RESOLVED" block makes the skill emit/mutate append-only events.jsonl, contradicting its READ-ONLY + safe_auto_execute basis (and the frontmatter, paired test, command, and events-writer.md all already encode the DEFERRAL). FIX: remove the entire 'Audit Event Emit (Q-RP-01 RESOLVED)' section + its runnable block; restore the single deferral statement. Add/extend a test asserting monthly-report performs NO events.jsonl write.
  B2-02 [HIGH decide] skills/reporting/monitoring-weekly/SKILL.md:~352-364 — headline capabilities (drift-via-events, GSC 5σ anomaly, budget burn) are documented active but the inline runtime stubs them "Phase 14+". DEFAULT DECISION = HONEST STUB-MARK: annotate the frontmatter description, Workflow steps 4-5, DURUR #5, and Principle 1 with "Wave-3 inline scope: placeholder; 5σ + cost.credits aggregation deferred to Phase 14+" so the documented contract matches the stub. (Do NOT implement 5σ.)
  B2-03 [HIGH code/doc] skills/reporting/monitoring-weekly/SKILL.md:~40-44 — consumes[] declares drift-check:_state/events.jsonl + master.xlsx[gsc_performance] but the impl reads _state/consistency-report-{slug}.json + shared/portfolio.json. FIX: reconcile consumes[] to the ACTUAL inline reads; drop/caveat the gsc_performance claim the runtime never makes.
  B2-04 [MED test] tests/skills/test_monitoring_weekly.py:~206-294 — prose-grep rubber stamp; never executes the runtime. FIX: add ≥1 execution test that runs the inline orchestration against a tmp workspace fixture and asserts the produced report's shape (not just that SKILL.md mentions things).
  B2-05 [MED test] tests/skills/test_weekly_summary.py — zero DURUR/error-path coverage despite the docstring claiming "sentinel". FIX: add pytest.raises tests for the real stop conditions (TemplateMissing / WorkbookMissing / WeeklySummaryError / WorkspaceRootUnset — see B2-06) and an idempotency/byte-stability assertion (same inputs → identical bytes).
  B2-06 [MED decide] scripts/reporting/weekly_summary.py:~67-68 — WorkspaceRootUnsetError is defined+exported but NEVER raised (the only --workspace-root handling is argparse required=True). DEFAULT DECISION = MAKE IT REAL: raise WorkspaceRootUnsetError explicitly in main() when workspace_root cannot be resolved to projects/{slug}/, and cover it with a pytest.raises test (pairs with B2-05). (Alternative if you find argparse already fully guards it: delete the dead class + its DURUR #2 doc — but prefer making the documented stop real.)
  B2-07 [LOW doc] skills/reporting/monitoring-weekly/SKILL.md:~446-462 — Principle 2 profile enum cites local-business / personal-brand which are not real values; correct to the schema's actual site_profile enum (e-commerce, ymyl, local-service, b2b-saas, portfolio, …) — verify against the live schema before writing.
  B2-08 [LOW doc] tests/skills/test_weekly_summary.py:169 — Test-1 docstring says status=wip; frontmatter is active; update the docstring to status=active.

VERIFICATION: full suite green > baseline; new tests for B2-01 (no-write), B2-04 (execution), B2-05/06 (raises). @code-reviewer + @verifier.

REPORT (print, do not commit): baseline vs final pytest counts; per-finding FIXED/STALE/ESCALATED + one line; the two decisions taken (B2-02 stub-mark, B2-06 raise-vs-delete) with rationale; new test names; git diff --stat; confirm append-only events.jsonl was NOT given any new write path; confirm no out-of-scope edits, no commit.
```

---

## B3 — Ingestion (13 findings)

```text
You are a WORKER fixing skill-contract findings in the Platinum SEO Engine (Python, pytest). Repo root: /Users/apple/Documents/platinum-seo-engine. Batch B3. Work ONLY in scope. Do NOT git commit/push — STOP and print the REPORT.

WHY: Ingestion skills declare functions / MCP tools / Step-8 render variables that don't exist — running them as documented would crash. Make each contract either real (cheap wrapper) or honestly demoted.

SCOPE — only these 5 skills + artifacts:
  dfs-pull, gsc-pull, scrapling-ops, sf-crawl-orchestrator, sf-import
  → skills/ingestion/<name>/SKILL.md ; scripts/ingestion/sf_import.py (+ sibling sf_*.py if a fix needs them) ; tests/skills/test_sf_crawl_orchestrator.py ; the relevant report templates under templates/reports/.
  For B3-01 you MAY add a thin wrapper to scripts/reporting/render_template.py (sanctioned by the decision register). Anything else → STOP and report.

GOVERNING DOCS (read first): the roadmap (conventions + decision register) and findings.json (evidence).

METHOD: baseline pytest; re-read each file (lines may have drifted, STALE if gone); DOC→edit, CODE→failing test first, TEST→real assertion first; never fake red. Verify the real API by reading the actual script before you rewrite a SKILL.md code block. HARD RULES as in the roadmap. @code-reviewer + @verifier after.

THE 13 FINDINGS:
  B3-01 [HIGH decide] skills/ingestion/sf-crawl-orchestrator/SKILL.md:~540-554 — Step 8 calls render_template.render(), which doesn't exist (AttributeError). DEFAULT = ADD A REAL WRAPPER: implement render(template_path, output_path, variables)->Path in scripts/reporting/render_template.py (string.Template, write output, return path) + a unit test; this makes Step 8 honest and is reusable. (Alt: rewrite Step 8 to the existing API — only if the wrapper proves awkward.)
  B3-02 [HIGH decide] scripts/ingestion/sf_import.py:~237-264 — required mcp__gsc__list_sitemaps + DURUR #4 sitemap cross-check are never implemented. DEFAULT = DEMOTE: move mcp__gsc__list_sitemaps from mcp_tools.required to optional and mark DURUR #4 "Phase-X deferred" in SKILL.md (the cross-check is a feature, not a contract bug). Add a test asserting the documented required-tools match what the code actually calls.
  B3-03 [HIGH decide] scripts/ingestion/sf_import.py:~267-328 — workflow_runner run-shell (Steps 1/2/3/8, DURUR #1/#2/#5) is declared but the impl never uses it. DEFAULT = REWRITE SKILL.md to describe the actual behavior (no run-shell; the {run_id}.json shell + string outputs it promises don't exist). Do NOT wire workflow_runner just to satisfy prose.
  B3-04 [HIGH code/doc] skills/ingestion/gsc-pull/SKILL.md:~222-225 — Step 8 variable list can't render the real template. FIX: update the list to the template's actual tokens (read templates/reports/gsc-pull*.template.md): $row_count_recent,$row_count_previous,$unique_urls,$top_5_pages,$delta_summary,$run_id,$rows_written,$project_slug,$date,$days_back — verify, don't guess.
  B3-05 [MED test] tests/skills/test_sf_crawl_orchestrator.py:~284-292 — the paired test simulates a fictional Step-5 export the body says never happens. FIX: align the simulator to the real body — drive it from build_export_plan() and the actual export functions.
  B3-06 [MED doc] skills/ingestion/dfs-pull/SKILL.md:~40-44 — `cluster` input declares a cluster_keywords write the skill explicitly disclaims (staging-only). FIX: remove the `cluster` input from frontmatter + command argument-hint (or document it as inert/reserved).
  B3-07 [MED doc] skills/ingestion/dfs-pull/SKILL.md:~273-282 — Step 8 calls write_staging/staging_filename signatures that don't exist. FIX: rewrite the code block to the shipped API (read scripts/ingestion/dfs_pull*.py for the real call).
  B3-08 [MED doc] skills/ingestion/scrapling-ops/SKILL.md:~256-259 — Step 8 render-variable list ≠ real template. FIX: align to the actual template tokens (read it).
  B3-09 [MED doc] skills/ingestion/sf-import/SKILL.md:156 — cites scripts.ingestion.sf_validate + sf_sitemap_xcheck (neither exists). FIX: reference the real module (scripts.ingestion.sf_import.match_tiers etc.); do not invent modules.
  B3-10 [MED doc] scripts/ingestion/sf_import.py:~241-248 vs SKILL.md/test — SKILL.md+test say transaction.append; impl uses transaction.replace. FIX: change SKILL.md Step 6 to transaction.replace + an idempotency note; align the paired test's wording.
  B3-11 [LOW doc] skills/ingestion/gsc-pull/SKILL.md:~338-339 — F-08 cross-ref uses the DEFERRED 'target_url' wording the schema disclaims; correct to the active F-08 (url ⊆ crawl_sitemap ∪ gsc_performance) at L9 + L338-339.
  B3-12 [LOW doc] skills/ingestion/scrapling-ops/SKILL.md:357 — 'ADR-026 (Q-015 hard cap)' misattributed; drop it (ADR-026 is the unrelated DECISIONS byte-cap).
  B3-13 [LOW doc] skills/ingestion/sf-crawl-orchestrator/SKILL.md:~667-671 — dangling helper-test cross-ref; repoint to tests/scripts/test_sf_crawl_orchestrator_helpers.py and correct the case counts (verify the file + count).

VERIFICATION: full suite green > baseline; new tests for B3-01 (render wrapper), B3-02 (required-tools parity), B3-05 (real Step-5). @code-reviewer + @verifier.

REPORT (print, do not commit): baseline vs final counts; per-finding FIXED/STALE/ESCALATED + one line; the 3 decisions (B3-01 wrapper, B3-02 demote, B3-03 rewrite) with rationale; whether you added render_template.render() (and its test); new test names; git diff --stat; confirm no out-of-scope edits, no commit.
```

---

## B4 — Meta + Planning (18 findings)

```text
You are a WORKER fixing skill-contract findings in the Platinum SEO Engine (Python, pytest). Repo root: /Users/apple/Documents/platinum-seo-engine. Batch B4. Work ONLY in scope. Do NOT git commit/push — STOP and print the REPORT.

WHY: The project's bootstrap skills (init-project, brand-onboarding, mark-done) over-promise mechanisms that don't exist, and planning skills carry an invalid events enum + stale refs.

SCOPE — only these 9 skills + artifacts:
  meta: brand-onboarding, init-project, mark-done, whats-next
  planning: cluster-map, internal-links, master-task-sync, new-content-plan, topical-map
  → skills/meta/<name>/SKILL.md, skills/planning/<name>/SKILL.md ; scripts/meta/brand_onboarding_write.py ; tests/meta/test_brand_onboarding_write.py ; tests/skills/test_internal_links.py, test_master_task_sync.py, test_topical_map.py
  For B4-05 you MAY edit schemas/project-config.schema.json IF you choose the "extend schema" option (see below) — otherwise schemas are read-only authority. mark-done's fix is SKILL.md-only: do NOT edit scripts/excel/transaction.py (that's B5's file).
  Anything else → STOP and report.

GOVERNING DOCS (read first): roadmap (conventions + decision register) ; findings.json (evidence).

METHOD: baseline pytest; re-read each file (drift→STALE); DOC→edit, CODE→failing test first, TEST→real assertion first; never fake red. HARD RULES as roadmap (esp. append-only, immutability). @code-reviewer + @verifier after.

THE 18 FINDINGS:
  B4-01 [HIGH doc] skills/meta/brand-onboarding/SKILL.md:~176-180,266-272,315 — "STAGING-ONLY: projects/{slug}/project.config.json is NEVER written" self-contradicts Stage C, which writes exactly that. FIX: scope the STAGING-ONLY absolute to the pre-Phase-14 wizard core (Steps 1-10) and explicitly carve out Stage C as the sanctioned bank-write that DOES mutate project.config.json once a workspace exists.
  B4-02 [HIGH test] skills/meta/init-project/SKILL.md:~311-312 — "Init not complete until Stage C writes" contradicts Step 10 + the paired test (terminal status==done, no cascade gate). FIX: decide the real contract and make test+text agree — either add a paired test that init does NOT reach 'done' for a YMYL project until the Stage-C/≥3-entry condition holds (if the gate is real), or reword 311-312 to match the terminal-done behavior. Coordinate with B4-03.
  B4-03 [HIGH decide] skills/meta/init-project/SKILL.md:~303-305 — cascade promises a live "auto-runner" + "cascade: brand-onboarding" event mechanism that doesn't exist. DEFAULT = HONEST STUB-MARK: reframe as "PLANNED (Phase 14): once the cascade auto-runner exists, init-project will emit …", mirroring brand-onboarding's deferral framing. (Do NOT build a cascade runner.)
  B4-04 [HIGH decide] skills/meta/mark-done/SKILL.md:~263-269 (also 87,343-349,357,448) — claims transaction.py hard-guards protected_columns via WriterScopeError; empirically only allowed_writers membership is checked. DEFAULT = REWORD: state the column-scope protection is advisory + skill-discipline, NOT a transaction.py hard guard. Add a one-line "future: consider a real column-scope guard" note for the manager. DO NOT edit transaction.py here.
  B4-05 [HIGH decide-schema] scripts/meta/brand_onboarding_write.py:~106-149 — Stage-C writes entries the consumed schema rejects (additionalProperties:false); claim/evidence_url/evidence_type/verified_date are not schema fields. FIX: reconcile field names with the authority — EITHER (a) extend project-config.schema.json experience/research item defs to declare these fields (then it validates), OR (b) map the writer's output to the existing schema fields. Add a test that the post-write config validates clean (pairs with B4-08). State which option you took.
  B4-06 [HIGH doc] skills/planning/new-content-plan/SKILL.md:~308-310 (+127) — body says 11-col output but impl+schema+test lock 14 (Phase-10 image_prompt/alt_text/content_type). FIX: change every '11-col'/'11 column' ref to 14 and extend the Step-7 column list + Outputs section to include the 3 columns with a one-line default note.
  B4-07 [HIGH doc] skills/planning/master-task-sync/SKILL.md:~320-329 — Step 8 prescribes source.kind=local_aggregation, NOT a valid events.schema enum → would fail validation. FIX: use a valid source.kind (e.g. 'tool_computed') and drop the unsupported keys, OR (if a new kind is truly needed) report to manager — default to the valid-enum reword.
  B4-08 [MED test] tests/meta/test_brand_onboarding_write.py:~40-53 — asserts field presence but never validates the written config against the schema. FIX: add an assertion that the post-write project.config.json validates clean against schemas/project-config.schema.json (this is the regression test for B4-05; write it to FAIL first if B4-05 unfixed).
  B4-09 [MED doc] skills/meta/mark-done/SKILL.md:~108-113 (+368,383,444) — event_type called a 'closed 10-value enum' listing 10; canonical is 12. FIX: update the four refs to 'closed 12-value enum' and reconcile the enumerated list with events.schema.json (read it).
  B4-10 [LOW doc] skills/meta/whats-next/SKILL.md:~339-340 — Tests cross-ref claims '5 cases incl. live pilot smoke'; reality differs. FIX: update to the true count/desc (read tests/skills/test_whats_next.py).
  B4-11 [LOW doc] tests/skills/test_internal_links.py:156 — docstring status=wip vs active; update to status=active.
  B4-12 [LOW doc] tests/skills/test_master_task_sync.py:~199-208 — docstring status=wip vs active; update + optionally tighten the loose membership assertion.
  B4-13 [LOW doc] tests/skills/test_topical_map.py:~146-155 — docstring clause says status=wip vs the relaxed assertion; align the docstring to reality.
  B4-14 [LOW doc] skills/meta/init-project/SKILL.md:~167-168 — clarify that --schema-version=1.5 is interpreted by the skill/slash-command layer, not the underlying bootstrap script (which has no such flag).
  B4-15 [LOW doc] skills/meta/mark-done/SKILL.md:~273-275 — normalize 'F-8'→'F-08','F-9'→'F-09' throughout (L108,113,273,286,368,373…) to match canonical invariant IDs.
  B4-16 [LOW doc] skills/meta/whats-next/SKILL.md:~333-336 — cross-ref cites event_type=manual contradicting the body's canonical event_type=skill_whats_next; fix the parenthetical.
  B4-17 [LOW doc] skills/planning/master-task-sync/SKILL.md:~99-101 — replace hard-coded schema line numbers with a stable JSON pointer (master-excel.schema.json#/sheets/…); also in the transform docstring + test if they echo it.
  B4-18 [LOW doc] skills/planning/topical-map/SKILL.md:~183-190 (+477-478) — F-09 enforcement misattributed to drift-check/validate_invariants.py; reword to the correct authority for cluster_keywords ⊆ topical_map.

VERIFICATION: full suite green > baseline; new tests for B4-02 (cascade gate, if real), B4-05+B4-08 (post-write schema validation). @code-reviewer + @verifier.

REPORT (print, do not commit): baseline vs final counts; per-finding FIXED/STALE/ESCALATED + one line; decisions (B4-03 stub-mark, B4-04 reword, B4-05 extend-vs-map, B4-07 enum choice) with rationale; confirm transaction.py was NOT touched; new test names; git diff --stat; any escalations; confirm no out-of-scope edits, no commit.
```

---

## B5 — Production + Publishing (18 findings)

```text
You are a WORKER fixing skill-contract findings in the Platinum SEO Engine (Python, pytest). Repo root: /Users/apple/Documents/platinum-seo-engine. Batch B5. Work ONLY in scope. Do NOT git commit/push — STOP and print the REPORT.

WHY: Content/publishing skills emit invalid event_type/event_kind values and carry a large cluster of stale event-enum cross-refs. Mostly precise doc/code reconciliation; no big decisions.

SCOPE — only these 7 skills + artifacts:
  production: content-remediation, faq-optimization, generate-images, new-blog, revise-content
  publishing: indexing-ping, verify-indexing
  → skills/production/<name>/SKILL.md, skills/publishing/<name>/SKILL.md ; scripts/excel/transaction.py (ONLY the one-line WRITER_REGISTRY fix B5-07) ; their paired tests if a behavioral fix needs them.
  Anything else → STOP and report. (transaction.py: change ONLY the WRITER_REGISTRY 'content_improve' entry; no other edit.)

GOVERNING DOCS (read first): roadmap + findings.json. Read schemas/events.schema.json to confirm the real event_type enum (12 values) + event_kind enum before writing any number.

METHOD: baseline pytest; re-read each file (drift→STALE); DOC→edit, CODE→failing test first; never fake red. HARD RULES as roadmap, ESPECIALLY: (a) Google Indexing API URL_UPDATED requires Süleyman consent — do not add any autonomous external submit; (b) no visible "written by AI" disclosure. @code-reviewer + @verifier after.

THE 18 FINDINGS:
  B5-01 [HIGH code/doc] skills/production/generate-images/SKILL.md:113,428,532 — success-path event_type documented content_new but the skill emits (and must emit) manual. FIX: replace 'content_new (success) or manual (DURUR #5)' wording with 'manual' as the single emitted event_type across the events table, READ-ONLY narrative, DURUR #5 row, References. If the impl actually emits a value, add/extend a test pinning the emitted event_type=manual.
  B5-02 [HIGH code/doc] skills/production/new-blog/SKILL.md:~227-232 — R-121 "post-publish mutation" prescribes a master.xlsx[completed_work] write that contradicts the skill's READ-ONLY claim and F-1 (completed_work.allowed_writers=null). FIX: reconcile — the rotation counter must read from an append-only source the skill is actually allowed to use (e.g. _state/events.jsonl content_new events), not a forbidden completed_work write; correct the R-121 text accordingly. If any code path performs the write, add a test that it does NOT.
  B5-03 [HIGH code/doc] skills/production/revise-content/SKILL.md:407 — events.jsonl event_kind='production' is invalid; content_revise must be event_kind='work'. FIX: change L407 to event_kind=work (mirror new-blog SKILL.md); extend the paired test (Test 9) to assert the documented event_kind is schema-valid.
  B5-04 [MED doc] skills/publishing/indexing-ping/SKILL.md:~50-52,75-79,253-259 — frontmatter+body name mcp__gsc__submit_sitemap as the Google Indexing API per-URL URL_UPDATED path; submit_sitemap submits SITEMAPS, not URLs. FIX: correct the tool labeling — describe submit_sitemap as the sitemap path and mark the per-URL Indexing API path as the (consent-gated) real mechanism to be wired post-Wave-2. Do NOT add an autonomous submit. The existing consent gate stays.
  B5-05 [MED doc] skills/production/generate-images/SKILL.md:112-113,422,427 — 'F-9' misattributed for event_kind=work/ADR-020; drop the wrong F-9 tag from those event_kind refs.
  B5-06 [MED doc] skills/production/generate-images/SKILL.md:186,194,242,262,436,490,530,549 — 'F-13' misattributed for the image_style 5-enum switch; replace F-13 with the correct authority (verify which invariant/ADR governs image_style) or drop the tag.
  B5-07 [LOW code] scripts/excel/transaction.py:106 — WRITER_REGISTRY advisory map names content-remediation as writer of content_improve; correct the entry to its true producing skill (verify against the skills' produces[]). ONE-LINE change.
  B5-08 [LOW doc] skills/production/faq-optimization/SKILL.md:246 (+ sibling line) — event_type '10-enum'→'12-enum' (or drop the count).
  B5-09 [LOW doc] skills/production/generate-images/SKILL.md:432-433 — events table actor/target differ from the canonical code block; reconcile to actor='agent:generate-images', matching target.
  B5-10 [LOW doc] skills/production/generate-images/SKILL.md:114,428,556 — '10-enum'→'12-enum'.
  B5-11 [LOW doc] skills/production/new-blog/SKILL.md:521-522 — References 'event_type enum 10 values'→12.
  B5-12 [LOW doc] skills/production/revise-content/SKILL.md:235 — "10-enum içinden 4'üncü değer" stale (enum is 12); drop/correct the ordinal.
  B5-13 [LOW doc] skills/publishing/indexing-ping/SKILL.md:100-104,284,376,405 — 'closed 10-value enum'→'closed 12-value enum (10 legacy + 2 skill_<name>)'.
  B5-14 [LOW doc] skills/publishing/indexing-ping/SKILL.md:109,379,405 — indexing_ping sub-object cross-ref 'events.schema.json L206-218'→correct lines (verify; ~L210-222) or drop brittle line nums for field-name reference.
  B5-15 [LOW doc] skills/publishing/verify-indexing/SKILL.md:117-122 (+432) — 'closed 10-value'→'closed 12-value'.
  B5-16 [LOW doc] skills/publishing/verify-indexing/SKILL.md:83-85 — 'docs/ARCHITECTURE.md §24.4' dangling; repoint to the real authority section (verify where the Indexing-API material lives).
  B5-17 [LOW doc] skills/publishing/verify-indexing/SKILL.md:136 — events.schema 'L206-218'→correct lines (verify) or drop.
  B5-18 [LOW doc] skills/publishing/verify-indexing/SKILL.md:484 — project-config cited 'v1.2'→'v1.5' (or drop the version label).

CONSISTENCY: B5-08/10/11/12/13/15 are the same event_type 10→12 sweep; apply identically. Verify the real enum once in events.schema.json, then sweep.

VERIFICATION: full suite green > baseline; new/extended tests for B5-01,02,03 (emitted event values schema-valid / forbidden writes absent). @code-reviewer + @verifier.

REPORT (print, do not commit): baseline vs final counts; per-finding FIXED/STALE/ESCALATED + one line; confirm NO autonomous Indexing-API submit was added and the consent gate is intact; confirm transaction.py changed only the one WRITER_REGISTRY line; new test names; git diff --stat; confirm no out-of-scope edits, no commit.
```

---

## B6 — Discovery + Governance + deterministic guard test (22 findings)

```text
You are a WORKER fixing skill-contract findings in the Platinum SEO Engine (Python, pytest). Repo root: /Users/apple/Documents/platinum-seo-engine. Batch B6 (final). Work ONLY in scope. Do NOT git commit/push — STOP and print the REPORT.

WHY: Discovery/governance skills have Step-8 template drift, an inert input, a missing-output disclosure, and a broad cross-ref cleanup. THEN you author a deterministic guard test that locks the whole "stale enum / maxItems" class so it can never silently return (this batch runs LAST, after B1–B5 fixed their enum refs).

SCOPE — these 15 skills + artifacts + ONE new guard test:
  discovery: aio-competitor-map, cannibalization, competitive-analysis, content-decay, content-gaps, gbp-audit, geo-analysis, on-page-audit, quick-wins, schema-audit, tech-audit
  governance: drift-check, glossary-audit, load-context, schema-validate
  → skills/discovery/<name>/SKILL.md, skills/governance/<name>/SKILL.md ; scripts/validation/validate_invariants.py (B6-08 disclosure is actually a drift-check SKILL.md edit — see below) ; scripts/budget/check_budget.py (B6-01 wrapper, sanctioned) ; their paired tests ; the relevant report templates.
  NEW FILE allowed: tests/skills/test_skill_schema_claims_parity.py (the guard).
  Anything else → STOP and report.

GOVERNING DOCS (read first): roadmap + findings.json. Read the live schemas before writing any enum count / maxItems / line number.

METHOD: baseline pytest; re-read each file (drift→STALE); DOC→edit, CODE→failing test first, TEST→real assertion first; never fake red. HARD RULES as roadmap. @code-reviewer + @verifier after.

THE 22 FINDINGS:
  B6-01 [HIGH decide] skills/discovery/content-decay/SKILL.md:~211-226 — Step 4b calls check_budget.preflight() + raises BudgetGateError; neither exists. DEFAULT = ADD THIN WRAPPER: add preflight(...)->dict to scripts/budget/check_budget.py returning the {'exceeded':...} envelope the SKILL.md depends on (+ a unit test); align the SKILL.md to the real symbol names. (Alt: call the existing CLI/main() — only if cleaner.)
  B6-02 [MED test] tests/skills/governance/test_glossary_audit.py:~214-237 — rubber-stamps detection (asserts whitelist is mentioned). FIX: add a behavioral test that runs the real detection (or the documented Step 4-6 algorithm) over a fixture and asserts the flagged/allowed terms.
  B6-03 [MED decide] skills/governance/glossary-audit/SKILL.md:~235-238 — missing-term detection over-promises (~1,393 FPs). DEFAULT = RECONCILE PROSE to the realistic detection/FP rate; no algorithm change.
  B6-04 [MED doc] skills/discovery/gbp-audit/SKILL.md:~233-237 — Step 6 documents a CLI the impl doesn't provide; replace with the real function-call contract (read gbp_audit_transform.py).
  B6-05 [MED doc] skills/discovery/gbp-audit/SKILL.md:~145-150 — Step 2 calls preflight_budget() signature that doesn't exist; either expose a real preflight_budget() on gbp_audit_transform.py mirroring tech_audit, or rewrite Step 2 to the real budget call. Prefer mirroring the sibling that already works (verify tech-audit's pattern).
  B6-06 [MED doc] skills/discovery/on-page-audit/SKILL.md:~275-278 — Step 8 variable list incomplete; render hard-fails if followed. Add the missing template vars (read the template; e.g. $report_summary, …).
  B6-07 [MED decide] skills/discovery/schema-audit/SKILL.md:~31-35 — input default_status is inert (never consumed). DEFAULT = WIRE IT: add default_status param to transform() + a --default-status CLI flag actually used; add a test. (Alt: remove the input from frontmatter if it's truly unwanted — pick wiring unless it's clearly vestigial.)
  B6-08 [MED doc] scripts/validation/validate_invariants.py:~664-704 → the FIX lands in skills/governance/drift-check/SKILL.md — an events.snapshot.json workspace write (F-12) is undisclosed in drift-check's outputs. FIX: add _state/events.snapshot.json to drift-check SKILL.md frontmatter outputs + the body Outputs section. (Edit drift-check/SKILL.md, not the validator.)
  B6-09 [LOW doc] tests/skills/test_cannibalization.py:~206-210 — docstring status=wip→active.
  B6-10 [LOW doc] tests/skills/test_content_decay.py:~120-128 — docstring status=wip→active (and align the loose assertion note).
  B6-11 [LOW doc] tests/skills/test_content_gaps.py:187 — docstring status=wip→active.
  B6-12 [LOW code] skills/discovery/on-page-audit/SKILL.md:~195-200 — Step 3 GSC inbox write omits mkdir(parents=True) that Step 2 has (DURUR #3 path). Add gsc_inbox.parent.mkdir(parents=True, exist_ok=True) before the write in the documented code block (and the impl if it mirrors it).
  B6-13 [LOW doc] tests/skills/governance/test_schema_validate.py:3 — docstring undercounts coverage ("9 tests" but 14); update header + add the missing numbered entries.
  B6-14 [LOW doc] skills/discovery/content-decay/SKILL.md:~270-271 — Step 8 under-declares template vars; add $trend_distribution,$pillar_summary,$run_id,$rows_written (verify against the template).
  B6-15 [LOW doc/code] skills/discovery/on-page-audit/SKILL.md:~510-513 — SF live-mode cites $amber_warnings not in the template; either add the line to templates/reports/on-page-audit.template.md or drop the reference (prefer matching the template's reality).
  B6-16 [LOW doc] skills/discovery/quick-wins/SKILL.md:27 — frontmatter outputs omits inbox/gsc/{date}-enhanced_search_analytics-{slug}.json that the body writes; add it.
  B6-17 [LOW code] skills/governance/glossary-audit/SKILL.md:195 — Step 4 regex uses '*' (matches single tokens) despite body saying '2+ token spans'; change the quantifier to '+'. If the regex is also in code, fix both + add a test.
  B6-18 [LOW doc] skills/governance/load-context/SKILL.md:40 — consumes declares docs/CONTEXT_LEDGER.md but the skill never reads it; drop it from consumes (or wire a read — prefer dropping to match reality).
  B6-19 [LOW doc] skills/discovery/content-decay/SKILL.md:~362-363,384-385 — content_decay 8-col cross-ref 'lines 158-170' stale; correct to the real range (verify).
  B6-20 [LOW doc] skills/discovery/quick-wins/SKILL.md:276 — D-03 invariant misattributed to gsc-tool-mapping.schema.json; reattribute to schemas/cross-sheet-invariants.json (verify).
  B6-21 [LOW doc] skills/discovery/quick-wins/SKILL.md:~269-270 — DURUR #10 uses deferred F-08 'target_url' wording; correct to active F-08 (quick_wins.url ⊆ crawl_sitemap.url ∪ gsc_performance.url).
  B6-22 [LOW doc] skills/governance/schema-validate/SKILL.md:~201-204 (+7-12) — stale cross-sheet-invariants rule-count ('F-23/= 28'); refresh to the current terminal count (read schemas/cross-sheet-invariants.json and count).

THEN — author the DETERMINISTIC GUARD TEST (new file tests/skills/test_skill_schema_claims_parity.py):
  Goal: lock Themes 1 & 6 so stale enum/maxItems claims can't silently return.
  - For every skills/**/SKILL.md, scan for numeric claims about schema-governed values: patterns like "N-value enum", "N-enum", "maxItems = N", "maxItems N", "active_projects … N".
  - Assert each against the LIVE schema authority: event_type enum size (events.schema.json), active_projects.maxItems (portfolio-config.schema.json), primary_source enum (the relevant schema).
  - Where a generic assert would false-positive (legacy/contextual counts), pin only the verified mappings — document each pinned mapping in the test, like the existing tests/skills/test_status_declaration_parity.py and test_trigger_declaration_parity.py do (read those two for the established pattern). Keep it deterministic; no LLM.
  - This test MUST pass once B1–B5 + B6's own doc fixes have landed. If it fails on a file outside B6's scope (i.e. B1–B5 missed an enum ref), REPORT that file to the manager — do NOT edit it (out of scope).

VERIFICATION: full suite green > baseline; new tests for B6-01 (preflight wrapper), B6-02 (glossary detection), B6-07 (default_status wiring), B6-17 (regex), and the parity guard. @code-reviewer + @verifier.

REPORT (print, do not commit): baseline vs final counts; per-finding FIXED/STALE/ESCALATED + one line; decisions (B6-01 wrapper, B6-03 prose, B6-07 wire-vs-remove) with rationale; the guard test's coverage + any out-of-scope enum refs it caught (for the manager); new test names; git diff --stat; confirm no out-of-scope edits, no commit.
```

---

### Manager note
After all six report back and are committed, run the full suite once more, confirm the new parity guard is green, and write the closing ledger entry (resolved IDs, deferred-with-rationale items, new test count). Decisions surfaced by workers (e.g. B4-05 extend-vs-map, B6-07 wire-vs-remove) are Süleyman's to ratify before commit.
