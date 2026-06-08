# AMO batch 4c — `/pseo-status --portfolio` triage table (read-only: coverage + 4a ledger usage)

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> the engine repo `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note:** 4c is the SMALLEST kind of batch — a pure, READ-ONLY portfolio triage reporter + a thin
> command recipe. It iterates `portfolio_runner.list_projects`, reads each project's LATEST coverage record,
> classifies it (healthy / owed / failed-internal / paused-external — all derivable from the coverage
> `verdict` alone, per the frozen schema), and shows the portfolio-global 4a budget (usage/ceiling/remaining
> per resource for today's period). No new schema, no spine/driver/ledger edit, no MCP calls, no writes.
> Ships as a SEPARATE command `commands/pseo-status-portfolio.md` (manager decision — mirrors 4b's separate
> `pseo-run-portfolio.md`; the per-project `pseo-status.md` stays untouched). Adding the command trips the
> D10 command-count guard (22→23) — that bump is the MANAGER's job; the worker scope-locks + surfaces it.

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE batch: a
READ-ONLY portfolio status/triage reporter + the /pseo-status-portfolio recipe. Follow every rule EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here with "Prompt is too long"). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: 2241 passed, 7 skipped, 0 failed. End state: passed >= 2241 + your new tests.
   THE ONLY acceptable failing test at the end is `tests/docs/test_count_consistency.py` (the command-count
   guard — the manager applies that D10 bump). EVERY other test, INCLUDING all your new ones, MUST pass.
   (If anything ELSE is red, STOP + report — do not paper over it.)
4. TDD, RED FIRST. Write tests, SHOW them fail for the right reason, THEN implement.
5. SCOPE-LOCK. Create/modify ONLY the files in SCOPE. Anything else → STOP + report. **Adding
   `commands/pseo-status-portfolio.md` trips the D10 command-count guards — that bump is the MANAGER's job;
   scope-lock and SURFACE it (the exact counts/literals), do NOT edit plugin.json / marketplace.json /
   the count test.**
6. READ-ONLY discipline (this is the whole point): the module + recipe NEVER write state. NO open(...,'w'),
   NO os.replace, NO cost_ledger.reserve/confirm/release, NO coverage.write_coverage, NO events write. It
   only READS coverage records + the cost ledger + portfolio.json. A test must PROVE this (grep the module
   source for write primitives → none). Mirror the oracle (`orchestration_metrics.py`) READ-ONLY contract.
7. Python discipline: pure/clock-free (the `period` partition key is PASSED IN, never read from a clock);
   immutability (build new structures, never mutate inputs); functions < 50 lines; no debug prints; type
   hints; module + function docstrings. Robust: a malformed/corrupt single file must NOT crash the whole
   triage (skip it / surface it), so one bad project never blanks the portfolio view.

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (spec §7 Phase 4 + §8 — the portfolio triage surface)
═══════════════════════════════════════════════════════════════════════════════════════════════
Faz 4 fans the orchestrator out across the portfolio (4b sweep) under a shared budget ceiling (4a ledger).
The operator (a non-coder) now needs ONE glance to triage the whole portfolio: which projects are healthy,
which are OWED an unfinished step, which FAILED internally (a gate rejection — fix + re-run now), and which
are PAUSED on an EXTERNAL dependency (budget exhausted / GSC-DFS outage — resumes when the dependency
recovers) — plus how much of today's global budget is spent. 4c is that read-only triage: it answers
"what needs my attention across all projects, and is the budget about to cap?" in one Turkish block. It
writes nothing; it is the portfolio-wide companion to the existing per-project `/pseo-status`.

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified against the real source — do NOT re-derive; DO read the named files)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. Portfolio enumeration — REUSE, do not re-derive: `scripts/orchestration/portfolio_runner.list_projects(
   workspace_root) -> list[dict]` reads `shared/portfolio.json`'s `projects` array IN ORDER (missing → []).
   Each item is a dict with at least `slug`. Import and call it — do NOT re-read portfolio.json yourself.
B. Coverage records live at `projects/{slug}/_state/coverage/{run_id}.json` (one file per run, accumulates
   over time). Build the directory path by REUSING `scripts/orchestration/coverage.coverage_path(
   workspace_root, slug, run_id)` and taking `.parent` (avoids path drift if the convention ever moves).
   The coverage record shape (frozen schema `schemas/coverage.schema.json`, batch 1a) — the fields you read:
     - `run_id` (str)
     - `steps` : list of { `name` (str), `verification_class` ("code_verified"|"model_attested"),
                           `status` ("pending"|"running"|"satisfied"|"missing"|"failed"|"skipped"), ... }
     - `required_satisfied` (bool)
     - `verdict` : EXACTLY one of "pass" | "incomplete" | "paused" | "failed"
     - optional: `project_slug`, `created_at`, `updated_at`, `engine_version`, `schema_version`
C. **The external-vs-internal axis is DEFINED BY THE COVERAGE `verdict`** (read the schema's verdict
   descriptions — they encode this; you do NOT need the workflow-run record). Map verdict → triage row:
     - "pass"        → category "healthy"  · cause "—"        (all required steps satisfied)
     - "incomplete"  → category "owed"     · cause "internal" (a required step missing → re-run to complete)
     - "failed"      → category "failed"   · cause "internal" (an internal gate rejection → fix + re-run now)
     - "paused"      → category "paused"   · cause "external" (an external dependency failed,
                       failure_reason.external=true — resumes when the dependency/budget recovers)
     - (no coverage record yet for a project) → category "none" · cause "—" · run_id None
   `missing_steps` for a row = the `name`s of steps whose `status` is "missing" OR "failed" (the steps that
   explain a non-pass verdict; empty for a healthy/none row). This is informational and computed for EVERY
   row regardless of verdict.
D. The 4a cost ledger (`scripts/state/cost_ledger.py`, shipped — read it) — the READ-ONLY API you call:
   - `usage(workspace_root, *, resource, period) -> float` — current usage for a (resource, period).
     **It RAISES `cost_ledger.CostLedgerError` on a broken hash chain (fail-closed).** Your reporter must
     CATCH that per-resource and surface an error marker for that resource — never let a broken ledger
     crash the whole triage.
   - `read_ceiling(workspace_root, resource) -> float | None` — from operator `shared/cost-ceilings.json`;
     None = UNSET = no cap (render "unset"/"sınırsız", remaining = None).
   - Resources (the three pools, in this canonical order): `gsc_calls`, `dfs_credits`, `image_spend`.
   - `usage()` is PORTFOLIO-GLOBAL per (resource, period) — it sums across all projects (the ceiling is
     portfolio-wide). So the budget view is ONE summary block for the whole portfolio, NOT per-project.
E. `period` is the ledger partition key (a UTC date string like "2026-06-08", or a constant like "total").
   The RECIPE resolves it at the boundary (`date -u +%Y-%m-%d`) and passes it in — the module reads no clock.
F. Operator surface (spec §8): the render is a Turkish block (non-coder). Mirror
   `portfolio_runner.render_summary`'s STYLE (emoji section headers, plain Turkish, a one-line next-action
   hint). The triage is workflow-agnostic (coverage records don't carry the workflow name) → the resume hint
   is GENERIC (e.g. "eksik → `/pseo-run <workflow> <slug>` ile tamamla"; "paused → bağımlılık/bütçe yenilenince
   devam eder"), it does NOT invent a specific workflow name.
G. This is ADDITIVE + READ-ONLY: it imports `portfolio_runner` + `cost_ledger` + `coverage` and reads files;
   it never edits the spine, the workflow drivers, the oracle, the ledger, or the per-project `pseo-status.md`.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW `scripts/reporting/portfolio_status.py`        (the read-only triage builder + Turkish render)
2. NEW `commands/pseo-status-portfolio.md`            (the recipe — D10 command bump 22→23, manager applies)
3. NEW `tests/reporting/test_portfolio_status.py`
Nothing else. (The D10 command-count manifest bump is the MANAGER's job — surface it, do NOT edit it.)

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC
═══════════════════════════════════════════════════════════════════════════════════════════════
`scripts/reporting/portfolio_status.py` — pure, read-only. Public API:
  - `latest_coverage(workspace_root, slug) -> dict | None`: glob the project's coverage dir
    (`coverage.coverage_path(ws, slug, "_").parent` → `*.json`); parse each; return the LATEST record by
    sort key `(file mtime_ns, run_id)` (so an mtime tie resolves deterministically by run_id). Missing dir /
    no files → None. A file that fails json-parse is SKIPPED (robust); if ALL fail → None.
  - `classify(record) -> dict`: from a coverage record, return
    `{"run_id", "verdict", "missing_steps": [...names...], "cause": "—"|"internal"|"external",
      "category": "healthy"|"owed"|"failed"|"paused"}` using the fact-C mapping. Defensive: an unexpected
    verdict → category = the verdict string, cause "—" (never crash).
  - `build_triage(workspace_root, *, period) -> dict`: returns
    `{"period", "rows": [...], "budget": [...]}`.
      • `rows`: for EACH project from `portfolio_runner.list_projects(ws)` IN ORDER →
        `latest_coverage` is None → `{"slug", "run_id": None, "verdict": None, "missing_steps": [],
          "cause": "—", "category": "none"}`; else `{"slug", **classify(record)}`.
      • `budget`: for each resource in (gsc_calls, dfs_credits, image_spend) →
        `{"resource", "used": <float|None>, "ceiling": <float|None>, "remaining": <float|None>,
          "error": <str|None>}`. `used` via `cost_ledger.usage(ws, resource=r, period=period)` — CATCH
        `cost_ledger.CostLedgerError` → `used=None, remaining=None, error="<message>"`. `ceiling` via
        `read_ceiling`; `remaining = ceiling - used` when both are real numbers, else None (unset ceiling
        or usage error). Build NEW dicts; never mutate.
  - `render_triage(triage) -> str`: ONE Turkish operator block. A header line with the period; a per-project
    triage table (slug · run_id · durum[category, Turkish] · eksik adımlar · neden[cause, Turkish]); then a
    budget block (resource · kullanım · tavan · kalan, with "sınırsız"/"unset" for None ceiling and a clear
    error marker for a usage error). Include a short Turkish next-action line for any non-healthy row (the
    GENERIC hint, fact F). Deterministic (no clock, stable ordering). Keep render helpers < 50 lines each.
  - NO argparse CLI (mirror `portfolio_runner` — pure library consumed by the recipe). NO `__main__` write
    path.

`commands/pseo-status-portfolio.md` (recipe; mirror `commands/pseo-status.md`'s frontmatter + engine-root
  resolution boilerplate, and `commands/pseo-run-portfolio.md`'s period-at-the-boundary pattern):
  - Frontmatter: a Turkish `description` (Use when / Also use when / Do not use when — portfolio-wide triage
    vs the per-project `/pseo-status`); `argument-hint: "[period]"`; `model: sonnet`; `allowed-tools` listing
    ONLY the Bash programs the recipe actually invokes (python3, jq, date, + the find/sort/tail/xargs/grep
    used by the engine-root resolution block you copy from `pseo-status.md`) + Read. NO MCP tools (read-only).
    READ `tests/commands/test_allowed_tools_match_shell.py` first and make allowed-tools match the Bash
    programs EXACTLY (it checks Bash programs, not MCP tools).
  - Body: (1) resolve PSEO_WORKSPACE_ROOT + the engine root (copy pseo-status.md's resolution block);
    (2) resolve `period` = `$1` if given else `date -u +%Y-%m-%d`; (3) call `build_triage` + `render_triage`
    via an inline `python3 -c` (PYTHONPATH=engine root), print the Turkish block; (4) if the portfolio is
    empty, say so + suggest `/pseo-init`. It performs NO writes and makes NO MCP calls.

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD — fully unit-testable with a tmp workspace (write coverage records + ceilings + a ledger as FIXTURES)
═══════════════════════════════════════════════════════════════════════════════════════════════
Build a tmp workspace: `shared/portfolio.json` (via `portfolio_writer` or a direct write in the fixture),
optional `shared/cost-ceilings.json`, optional `shared/cost_ledger.jsonl` (use `cost_ledger.reserve/confirm`
IN THE FIXTURE to populate usage — that is test setup, not the module writing), and per-project coverage
records under `projects/{slug}/_state/coverage/{run_id}.json` (use `coverage.build_record`/`write_coverage`
or `coverage.coverage_path` + a direct write in the fixture).
  • classify(): one case per verdict (pass→healthy/—, incomplete→owed/internal, failed→failed/internal,
    paused→paused/external) + missing_steps = the {missing,failed}-status step names; defensive unknown verdict.
  • latest_coverage(): no dir → None; one record → that record; TWO records for one project with controlled
    mtimes (os.utime) → returns the NEWER; all-corrupt-files → None; one corrupt + one valid → the valid one.
  • build_triage rows: 3 projects (one pass, one incomplete-with-a-missing-step, one with NO coverage) →
    rows in portfolio ORDER with the right category/cause/missing_steps; empty portfolio → rows == [].
  • build_triage budget: with a ceiling set + some confirmed usage in the ledger → used/ceiling/remaining
    correct; UNSET ceiling → ceiling None + remaining None; a tampered/broken ledger chain → that resource's
    row has error set + used None (and the triage still returns the rows — no crash).
  • render_triage(): Turkish; contains each project's slug + category label + the budget lines; a non-healthy
    row produces the generic next-action hint; deterministic (call twice → identical string).
  • READ-ONLY proof: read the module source and assert it contains NONE of: `os.replace`, `open(` with a
    write mode, `.write_coverage`, `cost_ledger.reserve`, `.confirm(`, `.release(` (i.e., it never writes).
Run RED first (module absent), then GREEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest (record the tail-5).
2. READ first: `scripts/orchestration/portfolio_runner.py` (list_projects + render_summary style),
   `scripts/state/cost_ledger.py` (usage/read_ceiling/CostLedgerError), `scripts/orchestration/coverage.py`
   (coverage_path + record shape), `schemas/coverage.schema.json` (the verdict descriptions = the cause map),
   `commands/pseo-status.md` (frontmatter + engine-root resolution block to copy), `commands/pseo-run-portfolio.md`
   (period-at-boundary recipe pattern), `tests/commands/test_allowed_tools_match_shell.py` (what it checks),
   `tests/reporting/test_orchestration_metrics.py` (the READ-ONLY reporting-test idiom to mirror).
3. Tests RED → implement `portfolio_status.py` + the recipe → GREEN.
4. FULL suite → passed >= 2241; confirm the ONLY red test is `test_count_consistency` (the D10 command trip).
5. Self-review: READ-ONLY (grep: zero write primitives)? clock-free (period passed in)? robust (a corrupt
   coverage/ledger file never crashes the triage)? reuses list_projects + coverage_path (no path/enum drift)?
   external-vs-internal derived from the verdict only (no workflow-run read)? per-project `pseo-status.md`
   byte-unchanged?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• The coverage `verdict` enum or record shape on disk differs from fact-B/C (describe the mismatch — do NOT
  guess a mapping).
• `list_projects` / `usage` / `read_ceiling` / `coverage_path` signatures differ from fact-A/B/D (quote the
  real signature you found).
• You'd need to edit the spine / a driver / cost_ledger / coverage.py / the oracle / `pseo-status.md` / a
  test outside SCOPE to make this work (describe why).
• Any ambiguity in the triage classification or the budget semantics you can't resolve from the facts.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE (tail-5).
2. RED PROOF (module/recipe absent → the new tests fail for the right reason).
3. portfolio_status API: `latest_coverage` / `classify` / `build_triage` / `render_triage` signatures +
   confirm clock-free (period passed in) + the verdict→(category,cause) map you implemented.
4. READ-ONLY PROOF: the grep result showing the module has ZERO write primitives (the test that asserts it).
5. ROBUSTNESS PROOF: the corrupt-coverage-file and broken-ledger-chain cases — the triage still returns rows
   (no crash); the affected resource/row is surfaced with an error/skip, not silently dropped.
6. TRIAGE CORRECTNESS: the 3-project build_triage test — the rows in portfolio order with category/cause/
   missing_steps; and the budget block (used/ceiling/remaining + the unset-ceiling None case).
7. D10 SURFACE: adding `commands/pseo-status-portfolio.md` makes commands go 22→23 — the EXACT count-guard
   test + the `plugin.json` "22 slash command" + `marketplace.json` "22 commands" literals the manager must
   bump (do NOT edit them yourself).
8. RECIPE: confirm `allowed-tools` matches the Bash programs (test_allowed_tools_match_shell green) + it
   makes NO MCP calls + NO writes + the per-project `pseo-status.md` is byte-unchanged.
9. FULL SUITE: final tail-5 (passed >= 2241; note `test_count_consistency` as the expected, manager-owned
   D10 trip — every other test, including all your new ones, green).
10. ANYTHING you decided or that surprised you.
```
