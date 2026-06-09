# AMO batch 4g — self-upgrade versioning (stamp engine_version + run-start mismatch assertion)

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> the engine repo `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note:** spec §8 "self-upgrade versioning" — the optional defense-in-depth item, post-v2.0
> (would be v2.0.1). The plumbing ALREADY EXISTS: `engine_version` is a threaded param through `run_workflow`
> → `coverage.build_record`, and `coverage.schema.json` already declares it optional — but it is ALWAYS `None`
> (never populated) and nothing asserts it. 4g (a) resolves the real version from `plugin.json` and POPULATES
> the stamp, and (b) adds a run-start assertion that fail-loud-rejects a RESUME whose prior coverage was
> written by a DIFFERENT engine version ("regenerate"). This catches the mixed-version-artifact class (you
> upgrade the engine mid-project, then resume an old run against new code). NOTE: this is NOT the cache-stale
> fix (the version-keyed install handles that) — it is the orthogonal "stale DATA artifact" guard. Behavior-
> preserving for every fresh run; the only new runtime behavior is the resume-mismatch raise. No new
> command/schema → likely NO D10 (verify).

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE batch: self-upgrade
versioning — populate the engine_version stamp + a run-start version-mismatch assertion. Follow every rule EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: ~2311-2312 passed / 7-8 skipped / 0 failed (one MCP-gated test flips pass↔skip — NOT a
   regression). End state: passed >= your baseline + your new tests, failed == 0.
4. TDD, RED FIRST. Write tests, SHOW them fail for the right reason, THEN implement.
5. SCOPE-LOCK. Create/modify ONLY the files in SCOPE. Anything else → STOP + report.
6. BEHAVIOR-PRESERVING for every FRESH run. The engine_version stamp is additive (fills an existing optional
   coverage field); the ONLY new runtime behavior is: a RESUME (a coverage record already exists for this
   run_id) whose stored engine_version differs from the current → fail-loud. A fresh run (no prior coverage)
   MUST behave EXACTLY as before. All 4 workflows (monthly/audit/setup/content) + their tests stay green.
7. Python discipline: pure where possible; the version source reads plugin.json ONCE (cache it); anchor the
   repo root `Path(__file__).resolve().parents[2]` (NOT CLAUDE_PLUGIN_ROOT — avoid an installed-plugin copy
   shadowing the working tree, same as scripts/state/active_projects.py); functions < 50 lines; type hints.

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (spec §8 — self-upgrade versioning, defense-in-depth)
═══════════════════════════════════════════════════════════════════════════════════════════════
A generated artifact (a coverage record) carries no engine version today, so if you upgrade the engine and
then RESUME a run that was partly produced by the OLD engine, the new code silently reads old-shaped state.
4g stamps each coverage record with the engine version that produced it, and at run-start refuses to resume
across a version boundary (fail-loud "regenerate" rather than silently mixing). This is the honest realization
of "the system knows which version made its artifacts." (It is DISTINCT from the plugin-cache-stale class,
which the version-keyed install path already fixes — do NOT conflate them.)

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified — do NOT re-derive; DO read the named files)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. The stamp is ALREADY plumbed but never populated:
   - `scripts/orchestration/workflow_driver.py:run_workflow(...)` takes `engine_version: str | None = None`
     (line ~209) and passes it to `coverage.build_record(..., engine_version=engine_version)` (line ~244).
   - `scripts/orchestration/coverage.py:build_record(..., engine_version=None)` writes the key ONLY when
     non-None (it omits the key when None — `additionalProperties:false` safe).
   - `schemas/coverage.schema.json` ALREADY declares `engine_version` (optional string). So populating it is
     additive — NO schema change.
   - The 4 workflows (monthly_maintenance / audit_suite / new_project_setup / content_pipeline) + run_step
     thread an `engine_version` param too, all defaulting None. content_pipeline is the artifact-driver — it
     also writes coverage via the coverage module (verify how).
B. The version source = `.claude-plugin/plugin.json` `"version"` (currently "2.0.0"). There is NO existing
   engine-version helper (events_writer has `_SCHEMA_VERSION`, which is UNRELATED — do not reuse it).
C. NO prior-coverage read happens at run-start today — `run_workflow` builds + writes a fresh coverage record
   keyed by run_id. A RESUME re-invokes with the SAME run_id (so a coverage record at
   `coverage.coverage_path(ws, slug, run_id)` already existing == a resume). That existing-file check is your
   assertion hook.
D. The version source is plugin.json, which is ALREADY file #1 of the `version_bump` 5-file set
   (`scripts/release/version_bump.py`) — so a version bump updates the source automatically; there is NO new
   file to add to version_bump (the spec's "add to the 5-file set" is satisfied by reading from plugin.json).
E. This is ADDITIVE — it never edits the FROZEN spine (run_step/verify/committer), the gates, the ledgers, or
   any command/schema. It touches the version source (new) + run_workflow (populate + assert) + content's
   coverage write (populate) only.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create / modify
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW    `scripts/state/engine_version.py`         (read plugin.json "version" → the single source)
2. NEW    `tests/state/test_engine_version.py`
3. MODIFY `scripts/orchestration/workflow_driver.py` (default engine_version to the real version when None;
          add the run-start RESUME version-mismatch assertion)
4. MODIFY `scripts/orchestration/workflows/content_pipeline.py` (populate engine_version on its coverage write,
          IF it writes coverage — mirror the data-driver; verify first)
5. NEW    `tests/orchestration/test_engine_version_guard.py` (the stamp + the resume-mismatch assertion)
6. MODIFY a workflow's tests ONLY if the now-populated engine_version breaks an exact-equality coverage
   assertion (a previously-absent key now present) — STOP + report each such case first; it must be a
   coherent fixture update, never a weakening.
Nothing else. (If you find NO D10 trip — no command/schema added — confirm it; if something trips, SURFACE it.)

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC
═══════════════════════════════════════════════════════════════════════════════════════════════
`scripts/state/engine_version.py`:
  - `_REPO_ROOT = Path(__file__).resolve().parents[2]`; `_PLUGIN_JSON = _REPO_ROOT/".claude-plugin"/"plugin.json"`.
  - `engine_version() -> str`: read plugin.json once (cache via a module global / lru_cache), return its
    `"version"`. Fail-loud (`EngineVersionError`) on a missing file / missing key / non-string (committed
    contract — like active_projects.py). A `path` param keeps it testable.
  - Pure: one read, cached; no clock/RNG.

`scripts/orchestration/workflow_driver.py:run_workflow`:
  - POPULATE: when `engine_version is None`, resolve it from `engine_version.engine_version()` so every
    coverage record is stamped with the producing version (callers passing an explicit value still win — e.g.
    tests). Keep the param + default signature compatible.
  - ASSERT at run-start (the new behavior, BEFORE running the steps): if a coverage record already exists at
    `coverage.coverage_path(workspace_root, project_slug, run_id)` (a RESUME) AND its stored `engine_version`
    is present AND != the resolved current version → raise a fail-loud `EngineVersionMismatch` with a Turkish-
    friendly "regenerate" message naming both versions. If the prior record has NO engine_version (pre-4g
    artifact) → do NOT raise (back-compat: an un-stamped prior is allowed, treated as "unknown"). A FRESH run
    (no prior coverage file) → no read, no raise, byte-identical behavior.
  - Keep functions < 50 lines (extract a small `_assert_no_version_drift(...)` helper).

`content_pipeline.py`: if it writes a coverage record, populate engine_version the same way (resolve when
  None). If it does NOT write coverage (verify), leave it untouched + note that in the REPORT.

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD
═══════════════════════════════════════════════════════════════════════════════════════════════
  • engine_version(): returns plugin.json's "version" (== "2.0.0" now, but assert == the value read
    independently from the file, NOT a hardcoded literal); fail-loud on missing file / missing key / non-string
    (via the `path` param).
  • STAMP: a fresh run_workflow run → the written coverage record has `engine_version == engine_version()`.
  • RESUME MATCH: write a coverage record (version X) → re-run with the same run_id + same current version →
    no raise (versions match), behaves as a normal run.
  • RESUME MISMATCH (the teeth): a prior coverage record stamped with an OLD version (e.g. "1.9.5") exists for
    run_id → run_workflow with current "2.0.0" → raises `EngineVersionMismatch` (name both versions); assert
    it raised BEFORE re-writing (the prior record is not silently overwritten).
  • BACK-COMPAT: a prior coverage record with NO engine_version key → run_workflow → NO raise (un-stamped
    prior allowed).
  • FRESH (no prior file) → no raise; identical to pre-4g (the existing workflow tests prove this by staying
    green untouched).
  Run RED first (helper/assertion absent), then GREEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest.
2. READ: `scripts/orchestration/workflow_driver.py` (run_workflow + build_steps), `scripts/orchestration/
   coverage.py` (build_record + coverage_path + write_coverage), `schemas/coverage.schema.json` (engine_version
   field), `scripts/state/active_projects.py` (the parents[2] + fail-loud pattern to mirror),
   `scripts/orchestration/workflows/content_pipeline.py` (does it write coverage?), `.claude-plugin/plugin.json`
   (the version source). Confirm fact A/C against the real code.
3. Tests RED → implement engine_version.py + run_workflow populate+assert + content stamp → GREEN.
4. FULL suite → passed >= baseline; the 4 workflow drivers + their tests still green (behavior-preserving for
   fresh runs). Confirm NO count guard tripped (no command/schema added).
5. Self-review: fresh run byte-identical? resume-mismatch raises BEFORE overwrite? un-stamped prior allowed
   (back-compat)? version sourced from plugin.json (not hardcoded)? spine/gates/ledgers/commands/schemas
   untouched? all 4 workflows green?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• run_workflow's resume mechanism differs from fact-C (e.g. resume uses a different run_id / a different
  artifact) — describe the real mechanism before adding the assertion.
• Populating engine_version breaks more than a couple of exact-equality coverage-record test assertions
  (signals the stamp is more invasive than expected) — surface the full list before touching tests.
• content_pipeline's coverage write differs from the data-driver pattern — describe it.
• You'd need to edit the spine / a gate / a ledger / a schema / a command to make this work.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE (tail-5).
2. RED PROOF (helper/assertion absent → new tests fail for the right reason).
3. engine_version.py API + confirm it sources from plugin.json (not hardcoded) + fail-loud cases.
4. STAMP PROOF: a fresh run's coverage record now carries engine_version == engine_version().
5. RESUME-MISMATCH TEETH: the old-version prior → `EngineVersionMismatch` raised BEFORE overwrite (quote the
   assertion); + BACK-COMPAT: an un-stamped prior does NOT raise.
6. BEHAVIOR-PRESERVING: confirm fresh runs are byte-identical (the 4 workflow test suites green; list any
   coherent fixture update you had to make for the now-present engine_version key + why it's not a weakening).
7. NO-DRIFT: confirm spine/gates/ledgers/commands/schemas untouched + whether any count guard tripped.
8. FULL SUITE: final tail-5 (passed >= baseline, 0 failed).
9. ANYTHING you decided or that surprised you.
```
