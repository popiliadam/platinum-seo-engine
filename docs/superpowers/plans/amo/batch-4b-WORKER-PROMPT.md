# AMO batch 4b — `/pseo-run-portfolio` sequential sweep + per-project lock + budget preflight + kill-switch

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> the engine repo `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note:** Süleyman chose the SEQUENTIAL-SWEEP fan-out model (Option A). 4b is a PURE, testable
> coordinator + a per-project lock primitive + the `/pseo-run-portfolio` recipe. The model-dependent
> per-project MCP work is delegated through an INJECTABLE `run_project_fn` (the proven `commit_fn` pattern),
> so the coordinator's logic (enumerate → lock → preflight → kill-switch → confirm) is fully unit-testable
> with a stub. Per-step preflight + single-project-run lock coordination are DEFERRED (noted below).

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE batch: the
portfolio sequential-sweep runner + a per-project run-lock + the /pseo-run-portfolio recipe. Follow every
rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: 2217 passed, 7 skipped, 0 failed. End state MUST be passed >= 2217 and failed == 0.
4. TDD, RED FIRST. Write tests, SHOW them fail for the right reason, THEN implement.
5. SCOPE-LOCK. Create/modify ONLY the files in SCOPE. Anything else → STOP + report. **Adding
   `commands/pseo-run-portfolio.md` trips the D10 command-count guards — that bump is the MANAGER's job;
   scope-lock and SURFACE it (the exact counts), do NOT edit plugin.json / marketplace.json / the count test.**
6. Python discipline: pure/clock-free (period + now_iso PASSED IN); immutability (build new structures);
   functions < 50 lines; no debug prints; type hints; module docstrings.
7. State discipline for the lock: `fcntl.flock` on a per-project lockfile; NON-BLOCKING (`LOCK_NB`) so a
   busy project is SKIPPED, never waited on. NEVER `os.replace` a lockfile.

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (spec §7 Phase 4 — Süleyman chose the sequential-sweep model)
═══════════════════════════════════════════════════════════════════════════════════════════════
Faz 0 binds one session to one project (so "3-5 parallel" already exists as N windows). 4b adds a PORTFOLIO
SWEEP: in one invocation, iterate the portfolio's projects IN ORDER, run each project's owed workflow under
its OWN run-lock (skip a project already running elsewhere), reserving budget from the 4a cost ledger BEFORE
each project (job-level preflight). If a reserve would exceed the global ceiling, the KILL-SWITCH fires: that
project (and the remaining ones) go `paused` (resumable), NOT silent degrade — the sweep STOPS rather than
quietly under-running. The shared 4a ledger + per-project locks make this sweep safe alongside any parallel
bound single-project sessions.

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified — do NOT re-derive; DO read the named files first)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. Portfolio source: `{workspace_root}/shared/portfolio.json` = `{"schema_version":"1.0","projects":
   [{"slug","domain","market","created_at"}, ...]}` (written by `scripts/state/portfolio_writer.py`, 0e2).
   Read it directly (or reuse a portfolio_writer reader if one exists — check). Iterate `projects` IN ORDER.
B. The 4a cost ledger (`scripts/state/cost_ledger.py`, JUST shipped — read it) — the API you call:
   - `reserve(workspace_root, *, resource, period, amount, ceiling, run_id, project_id, now_iso) -> dict`
     (raises `CostCeilingExceeded` and writes NOTHING when over ceiling).
   - `confirm(workspace_root, *, reservation_id, amount, run_id, project_id, now_iso) -> dict`
     (amount <= reserved).
   - `release(workspace_root, *, reservation_id, run_id, project_id, now_iso) -> dict`.
   - `read_ceiling(workspace_root, resource) -> float | None` (from `shared/cost-ceilings.json`).
   - `usage(workspace_root, *, resource, period) -> float`. Resources: gsc_calls / dfs_credits / image_spend.
   - The reserve entry's `reservation_id` is the key for confirm/release.
C. Budget ESTIMATE source (job-level preflight): a plain operator-edited
   `{workspace_root}/shared/cost-estimates.json` = `{ "<workflow>": { "gsc_calls": <n>, "dfs_credits": <n>,
   "image_spend": <n> }, ... }`. Provide `estimate_cost(workspace_root, workflow) -> dict[str,float]`
   (absent file/workflow -> `{}` = reserve nothing for that workflow; a missing resource key -> 0 for that
   resource). The operator tunes these (like ceilings, O5). Do NOT add a schema for this config file.
D. `paused` is the resumable EXTERNAL-failure verdict (D4) — `derive_verdict` (coverage.py) NEVER returns
   it; it is set deliberately for an external failure. The budget-ceiling kill-switch IS an external failure
   (the global pool is exhausted, outside this run's control), so a kill-switched project is recorded
   `paused` in the sweep result (resumable when budget returns). 4b does NOT need to write a per-project
   coverage record for a paused project — surface it in the PortfolioResult + the operator message; the
   full resume wiring is 4d/later.
E. The model-dependent per-project run is DELEGATED via an injectable `run_project_fn(slug, workflow) ->
   dict` (the coverage record / a result dict). In tests you pass a STUB; in production the recipe supplies
   the real per-project `/pseo-run <workflow> <slug>` flow. This keeps `run_sweep` PURE + unit-testable
   (mirrors `committer.commit` injection in `run_step`). `run_project_fn` MAY return an `actual_cost`
   dict (per resource) so the sweep CONFIRMS the actual; if absent, confirm the reserved amount.
F. Operator-remediation surface (spec §8): every skip / pause / kill-switch carries a Turkish one-line
   message (mirror `remediation.render`'s style) so a non-coder always sees what happened + the next action.
G. This is ADDITIVE — it imports cost_ledger + reads portfolio.json; it never edits the spine, the
   workflow drivers, the oracle, or cost_ledger.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW `scripts/state/project_lock.py`              (per-project non-blocking run-lock + a tiny CLI/ctxmgr)
2. NEW `scripts/orchestration/portfolio_runner.py`  (the sequential-sweep coordinator)
3. NEW `commands/pseo-run-portfolio.md`             (the recipe; triggers the sweep — D10 command bump)
4. NEW `tests/state/test_project_lock.py`
5. NEW `tests/orchestration/test_portfolio_runner.py`
Nothing else. (The D10 command-count manifest bump is the MANAGER's job — surface it.)

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC
═══════════════════════════════════════════════════════════════════════════════════════════════
`scripts/state/project_lock.py`:
  - `project_lock_path(workspace_root, slug) -> Path` (`.../shared/locks/{slug}.lock`; mkdir -p; validate
    slug `^[a-z][a-z0-9-]*$`).
  - `try_acquire(workspace_root, slug) -> int | None`: `os.open` + `fcntl.flock(LOCK_EX|LOCK_NB)`; on
    success return the held fd; on `BlockingIOError`/`OSError` (already locked) return None (SKIP, never
    wait). 
  - `release(fd) -> None` (flock LOCK_UN + close, error-safe).
  - A context manager `held_lock(workspace_root, slug)` yielding the fd or None (None => skip the project).
  Pure flock discipline; no os.replace.

`scripts/orchestration/portfolio_runner.py`:
  - `estimate_cost(workspace_root, workflow) -> dict[str, float]` (fact C).
  - `list_projects(workspace_root) -> list[dict]` (read portfolio.json `projects`, in order; missing -> []).
  - `run_sweep(workspace_root, *, workflow, period, now_iso, run_project_fn, run_id_prefix="portfolio",
    ceilings=None) -> dict` — the coordinator. `ceilings` defaults to reading each resource via
    `cost_ledger.read_ceiling`. For each project IN ORDER:
       1. `try_acquire` its lock; None -> append to `skipped` (reason "already running") + continue.
       2. estimate = estimate_cost(workflow); for EACH resource with amount>0: `cost_ledger.reserve(...,
          ceiling=ceilings[resource])`. If any reserve raises `CostCeilingExceeded`: RELEASE any reservations
          already made for THIS project (so a partial reserve doesn't leak), record the project in `paused`
          (with the ceiling detail), release the lock, and STOP the sweep (kill-switch — do NOT continue to
          later projects; they go into `not_run`). 
       3. Else call `run_project_fn(slug, workflow)` (guard exceptions → record `failed` + release
          reservations + unlock + continue). On success, CONFIRM each reservation (actual from the result's
          `actual_cost` if present, else the reserved amount); append to `ran`.
       4. Release the lock (always, in a finally).
    Return `{"workflow","period","ran":[...],"skipped":[...],"paused":[...],"not_run":[...],
    "stopped_by_kill_switch":bool}`. PURE except the ledger/lock IO; clock-free (period+now_iso passed in).
  - `render_summary(result) -> str` — a Turkish operator summary (ran/skipped/paused counts +, if
    kill-switched, the exact "budget ceiling hit on <resource>" + how to resume) — mirror remediation.render.
  - A thin CLI `python3 -m scripts.orchestration.portfolio_runner ...` is OPTIONAL; the RECIPE is the real
    entry. If you add one, keep it read-only-ish (it would need a real run_project_fn — better to leave the
    orchestration to the recipe + keep the module a pure library). Prefer NO write-CLI here.

`commands/pseo-run-portfolio.md` (recipe; mirror `commands/pseo-run.md`'s structure + allowed-tools):
  - Trigger: `/pseo-run-portfolio <workflow>` (workflow ∈ monthly/audit/setup/content; any other → DURUR).
  - Steps: resolve workspace + period (today's UTC date) + now_iso; call `run_sweep` with a `run_project_fn`
    that, per project, runs the EXISTING single-project `/pseo-run <workflow>` flow (the model does the MCP
    work + the per-project driver verifies/commits) and returns its coverage record (+ actual_cost if
    derivable). Surface `render_summary` (Turkish) at the end — including any kill-switch pause + the resume
    hint. `allowed-tools` lists only the Bash programs it invokes (the test `test_allowed_tools_match_shell`
    checks Bash programs, not MCP tools).

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD — the coordinator is fully unit-testable with a STUB run_project_fn (no live model)
═══════════════════════════════════════════════════════════════════════════════════════════════
project_lock: acquire returns an fd; a SECOND try_acquire on the SAME slug (real second fd / subprocess)
returns None (skip); after release, re-acquire succeeds; different slugs don't contend; held_lock ctxmgr.
portfolio_runner (stub run_project_fn + a tmp ws with a portfolio.json + cost-ceilings.json + cost-estimates.json):
  • happy sweep: 3 projects, ample ceiling, stub returns success+actual -> all in `ran`, ledger shows the
    confirmed actuals, no paused/skipped.
  • skip-if-locked: pre-acquire project B's lock in the test, run the sweep -> B in `skipped`, A+C in `ran`.
  • KILL-SWITCH (the core safety): a low ceiling so project 2's reserve raises CostCeilingExceeded ->
    project 2 in `paused`, project 3 in `not_run`, `stopped_by_kill_switch=True`, project 1's reservation
    was CONFIRMED (not leaked), project 2's partial reservations were RELEASED (ledger usage reflects only
    project 1's actual — assert no overspend + no leak).
  • run_project_fn raises -> that project in `failed`, its reservation released, the sweep CONTINUES to the
    next (a single project's failure is not a kill-switch).
  • confirm-actual: stub returns actual_cost < reserved -> ledger usage reflects the actual (the unspent
    estimate is freed).
  • estimate_cost: reads cost-estimates.json per workflow; absent file -> {} (reserve nothing).
  • render_summary: Turkish, names the kill-switch resource on a paused result.
Run RED first (modules absent), then GREEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest.
2. READ `scripts/state/cost_ledger.py` (4a), `scripts/state/portfolio_writer.py` (portfolio.json shape),
   `commands/pseo-run.md` (recipe structure + allowed-tools), `scripts/orchestration/remediation.py`
   (render style), `tests/commands/test_allowed_tools_match_shell.py` (what it checks).
3. Tests RED → implement project_lock + portfolio_runner + the recipe → GREEN.
4. FULL suite -> passed >= 2217. Confirm the ONLY count-guard trips are the D10 command bump (the recipe).
5. Self-review: lock is NON-BLOCKING (skip not wait)? kill-switch RELEASES partial reservations (no leak)
   + STOPS the sweep + records paused? clock-free? no spine/driver/ledger edit? a single project's failure
   does NOT kill-switch?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• The kill-switch can't release a partial reservation cleanly (describe the leak).
• You'd need to edit the spine / a workflow driver / cost_ledger / the oracle / a test outside SCOPE.
• The recipe's per-project run_project_fn can't reuse the existing /pseo-run flow (describe the gap — do
  NOT silently re-implement a workflow driver).
• Any ambiguity in the sweep/kill-switch semantics you can't resolve from the facts — describe it.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE.
2. RED PROOF (modules/recipe absent).
3. project_lock: API + confirm NON-BLOCKING (skip-not-wait) + a real second-holder returns None.
4. portfolio_runner: run_sweep signature + the per-project loop; confirm injectable run_project_fn (pure +
   stub-tested); clock-free.
5. KILL-SWITCH PROOF: the low-ceiling test — paused project + not_run remainder + stopped_by_kill_switch +
   project-1 confirmed + project-2 partial reservation RELEASED (no leak, no overspend in the ledger).
6. SKIP + FAILURE: skip-if-locked result; a single run_project_fn failure does NOT stop the sweep.
7. D10 SURFACE: adding `commands/pseo-run-portfolio.md` makes commands go 21→22 — the EXACT count guards +
   marketplace/plugin literals the manager must bump (do NOT edit them yourself).
8. FULL SUITE: final tail-5 (passed >= 2217; note the command-count guards as the expected D10 trip).
9. ANYTHING you decided or that surprised you.
```
