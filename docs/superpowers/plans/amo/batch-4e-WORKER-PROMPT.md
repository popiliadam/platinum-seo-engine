# AMO batch 4e — portfolio recovery runbook (doc) + a light citation-existence test

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> the engine repo `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note:** 4e is the spec §7-Phase-4 "written recovery runbook" deliverable + spec §8 operator
> surface. It is a DOC batch — the worker writes ONE English reference doc (`docs/` convention, like
> INSTALL.md/ARCHITECTURE.md) that documents how to OPERATE + RECOVER the shipped Faz-4 portfolio machinery
> (4a ledger · 4b sweep + kill-switch · 4c triage · 4d scheduler). **DISPATCH THIS ONLY AFTER 4d HAS MERGED**
> — the runbook must describe the ACTUAL shipped commands/files; the worker READS the real source + quotes
> the real operator surfaces. A new `docs/*.md` does NOT trip any count guard (D10 counts commands/schemas/
> skills/rules, not docs) → no manager bump. The only code is a small, cheap test that asserts every command/
> script the runbook cites actually EXISTS (so the doc can't silently rot).

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE batch: a portfolio
RECOVERY RUNBOOK doc + a light citation-existence test. Follow every rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Record what you SEE (>= 2241 + 4c/4d's tests if those merged). End state: passed >= your baseline + your
   ONE new test, failed == 0. (A doc batch should trip NO count guard — if any guard goes red, STOP + report.)
4. ACCURACY-FIRST. Every command, file path, behavior, and operator-message you document MUST be verified
   against the REAL shipped source — READ each file before you describe it. Do NOT document a flag, command,
   or behavior you did not confirm exists. If the runbook would need to describe something not yet built
   (e.g. 4d not merged), STOP + report (the prerequisite is missing).
5. SCOPE-LOCK. Create/modify ONLY the files in SCOPE. Anything else → STOP + report.
6. NO MUTATION of any shipped behavior — this batch adds a DOC + a read-only test; it changes ZERO runtime
   code. The per-project pseo-status.md, the spine, the drivers, the ledger, the gates stay byte-unchanged.
7. Plugin-agnostic: the runbook describes the ENGINE's portfolio mechanics only — NO CMS/site/project-
   specific instructions, NO secrets, NO real tokens.

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (spec §7 Phase 4: "a written recovery runbook"; §8 operator-remediation surface)
═══════════════════════════════════════════════════════════════════════════════════════════════
Faz 4 added autonomous-ish portfolio operations that can hit a budget ceiling (kill-switch → paused), skip a
busy project, fail one project mid-sweep, or be put on a recurring schedule. A non-coder operator (Mac app,
no terminal) needs ONE authoritative document that says, for each thing that can go wrong, EXACTLY what they
will see and the EXACT copy-pasteable command to recover. This runbook is that document. It also documents
the ONE thing the engine deliberately does NOT do — fire the schedule itself — and how to wire the external
trigger safely (after the ceilings are set + the live-acceptance run).

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (the shipped Faz-4 surface you are documenting — READ each file; quote the REAL behavior)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. 4a cost ledger — `scripts/state/cost_ledger.py` + `schemas/cost-ledger.schema.json` +
   `shared/cost_ledger.jsonl` (global, append-only, hash-chained) + operator configs
   `shared/cost-ceilings.json` (hard ceilings, O5) + `shared/cost-estimates.json` (per-workflow estimates).
   Read-only CLI: `python3 -m scripts.state.cost_ledger usage <resource> <period>`. Resources:
   gsc_calls / dfs_credits / image_spend. `usage()` RAISES on a broken chain (fail-closed).
B. 4b portfolio sweep — `commands/pseo-run-portfolio.md` (`/pseo-run-portfolio <monthly|audit|setup|content>`)
   + `scripts/orchestration/portfolio_runner.py` (`run_sweep`/`render_summary`) + per-project lock
   `scripts/state/project_lock.py` (`shared/locks/{slug}.lock`, NON-BLOCKING). Kill-switch: a reserve over
   the ceiling → that project `paused`, the rest `not_run`, the sweep STOPS (resumable). A single project's
   run failure → released + the sweep CONTINUES. READ `render_summary` and QUOTE its real Turkish lines.
C. 4c portfolio triage — `commands/pseo-status-portfolio.md` (`/pseo-status-portfolio [period]`) +
   `scripts/reporting/portfolio_status.py` (`build_triage`/`render_triage`). Categories: healthy / owed
   (incomplete, internal) / failed (internal gate rejection) / paused (external dependency) / none. READ it
   and QUOTE the real category labels + the budget block. [If 4c is not merged yet, document 4a+4b+4d and
   note 4c as the companion — but prefer dispatching this after BOTH 4c and 4d are merged.]
D. 4d scheduler — `commands/pseo-schedule.md` (`/pseo-schedule [status|arm|disarm] ...`) +
   `scripts/state/schedule.py` + `schemas/schedule.schema.json` + `shared/schedule.json` (default OFF). The
   arming gate is FAIL-CLOSED on O5 (refuses to arm while any ceiling is unset) + requires explicit
   per-cadence consent + shows projected daily cost. READ it and QUOTE the real refuse message + the arm
   flow. **The engine does NOT fire the schedule** — document that the periodic trigger is EXTERNAL.
E. The external trigger (the ONE thing to document carefully, plugin-agnostic): an armed schedule is fired by
   an EXTERNAL scheduler (the operator's OS `cron`/`launchd`, or a Claude Code scheduled task / `/loop`) that
   invokes `/pseo-run-portfolio <workflow>` on the cadence. Document the SHAPE generically (a cron line that
   runs the portfolio command) WITHOUT inventing engine-internal daemon behavior. State the safety order
   plainly: (1) set all three ceilings in `shared/cost-ceilings.json`; (2) run the one comprehensive live
   acceptance (D11) once; (3) only THEN arm + wire the external trigger.
F. Provenance you can cite: the AMO design spec
   `docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md` (§7 Phase 4, §8) and the
   manager roadmap `docs/superpowers/plans/amo/MANAGER.md`. Match the existing `docs/*.md` house style
   (READ `docs/INSTALL.md` or `docs/ARCHITECTURE.md` for tone — English reference prose).

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW `docs/RUNBOOK-portfolio-recovery.md`     (the recovery runbook — English reference doc)
2. NEW `tests/docs/test_runbook_citations.py`   (a cheap guard: every command/script path the runbook cites
                                                 in fenced/backtick form EXISTS on disk — keeps the doc honest)
Nothing else. (No schema, no command, no runtime code → NO D10 bump.)

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC — `docs/RUNBOOK-portfolio-recovery.md` (sections; each = symptom → what you'll see → exact recovery)
═══════════════════════════════════════════════════════════════════════════════════════════════
0. Header + a one-paragraph "what this covers" + a "safety order before arming autonomy" box (fact E).
1. **Reading the portfolio triage** — `/pseo-status-portfolio`: each category (healthy/owed/failed/paused/
   none) and the action it implies; the budget block (usage/ceiling/remaining per resource); the unset-ceiling
   "sınırsız/unset" case.
2. **Budget kill-switch fired (a project `paused`, the rest `not_run`)** — what `render_summary` prints
   (quote it), why (ceiling hit), and recovery: inspect `python3 -m scripts.state.cost_ledger usage <res>
   <period>`; either raise the ceiling in `shared/cost-ceilings.json` or wait for the daily `period` reset;
   then re-run `/pseo-run-portfolio <workflow>` (it resumes the not_run remainder). No data is lost (partials
   were released; the ledger is intact).
3. **A project was skipped (lock held)** — `/pseo-run-portfolio` skipped a project "already running"; why
   (the per-project flock is held by another session/sweep); recovery: let the other run finish, then re-run;
   how to recognize a genuinely STALE lock (`shared/locks/{slug}.lock`) vs a live one (a flock is released
   automatically when the holding process dies — document the conservative "just re-run; if it persists with
   no live session, the lock is stale" guidance; do NOT instruct deleting a lock under a live process).
4. **A single project failed mid-sweep** — `failed` (not a kill-switch); the sweep continued; recovery:
   re-run that one project with `/pseo-run <workflow> <slug>` (the per-project driver), or re-sweep.
5. **Cost ledger chain broken** (`usage()`/a sweep raises a "chain broken" error) — what it means
   (fail-closed tamper detection), how to inspect, and the recovery posture (the ledger is append-only +
   hash-chained; a broken chain is surfaced, never silently ignored — escalate, do not hand-edit the log).
6. **Scheduler: arm / disarm / status** — `/pseo-schedule`; the O5 refuse-when-uncapped message (quote it);
   the projected-cost display; the explicit per-cadence consent; **default OFF**; and the EXTERNAL-trigger
   wiring (fact E) with the safety order. Reiterate D11: arm only AFTER the comprehensive live acceptance.
7. **Quick reference table** — symptom → command → one-line action (the non-coder's at-a-glance index).

`tests/docs/test_runbook_citations.py`: parse the runbook for cited `/pseo-*` commands and `scripts/...py`
paths (in backticks/fences) and assert each cited command file (`commands/<name>.md`) + each cited script
path EXISTS. Keep it tolerant (only check tokens that clearly look like a command/path), so prose isn't
falsely flagged — the goal is "no dangling citation," not a strict linter.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest.
2. READ every file in CONFIRMED FACTS (the real commands + render functions + schemas) + `docs/INSTALL.md`
   (house style). VERIFY each command exists in `commands/` and each script in `scripts/`. If 4c or 4d is
   missing, STOP + report (prerequisite not merged).
3. Write the runbook quoting the REAL operator surfaces (the actual Turkish `render_summary`/`render_triage`/
   refuse lines) + the real commands. Then write the citation-existence test.
4. Run the citation test (GREEN) + the FULL suite (passed >= baseline, 0 failed, no count-guard trip).
5. Self-review: every cited command/path exists? no invented behavior (each claim traceable to a file you
   read)? plugin-agnostic + no secrets? the "engine does not fire the schedule" + safety order stated?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• 4c (`portfolio_status.py`/`pseo-status-portfolio.md`) or 4d (`schedule.py`/`pseo-schedule.md`) is NOT on
  disk — the runbook can't honestly document an unbuilt surface (say which is missing).
• A documented command/behavior doesn't match the real source (describe the mismatch — do NOT paper over it).
• You'd need to change any runtime code/command/schema to make the doc accurate (that's a different batch).

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE (tail-5).
2. PREREQ CHECK: confirm 4a/4b/4c/4d surfaces are all present on disk (list the files you verified).
3. RUNBOOK: the section list + confirm every operator surface you quoted is copied from the REAL render
   function / command (cite the file:line you took each quote from).
4. CITATION TEST: it parses the runbook + asserts each cited command/script EXISTS; show it GREEN + show it
   would go RED on a dangling citation (a quick teeth check).
5. NO-DRIFT: confirm zero runtime code/command/schema changed (only a new doc + a new test) → NO D10 bump.
6. FULL SUITE: final tail-5 (passed >= baseline, 0 failed, no count guard tripped).
7. ANYTHING you decided or that surprised you.
```
