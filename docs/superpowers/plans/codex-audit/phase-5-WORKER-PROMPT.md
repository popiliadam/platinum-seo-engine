You are a WORKER session executing Phase 5 — State / Write & Audit Hardening of the Codex audit remediation for the Platinum SEO Engine. Fresh full context — do all work yourself here. This is the most code-heavy phase (real changes to state-mutation paths): run the full suite after EVERY change.

AUTHORITATIVE SPEC: Open and follow this file EXACTLY, task by task (full evidence + per-task TDD steps + risk guards):
  docs/superpowers/plans/codex-audit/phase-5-state.md
Also skim the "Guardrails" + "Completion Report" sections of:
  docs/superpowers/plans/codex-audit/MANAGER.md
Do not explore the rest of the repo — these files plus the paths they name are complete.

MISSION: Make state writes honest and auditable. Close:
- P1-10: workflow_runner.py pause(reason)/approve(notes) accept those params but never persist them; retry() deletes ended_at (loses terminal timing); some event-emit failures are swallowed.
- P1-11: events_writer.py next_run_id() scans for max id OUTSIDE the append flock → concurrent callers can collide.
- P1-06: hooks/post-tool-use.json ends with `|| true` (silent audit-emit failure) and hardcodes audit_action="accessed" for ALL Bash (a rm/cp/redirect logged as a mere access). events_writer.normalize_audit_action(command=...) exists but is unused.
- P1-07: hooks/pre-tool-use.json Excel owner-lock Bash-branch regex [\w/.-]+...\.xlsx misses paths with spaces/quotes/~. (Edit/Write branch already parses file_path correctly — only the Bash branch is fragile.)
- P1-09: scripts/excel/transaction.py _ensure_sheet_with_header always writes header to row 1 (ignores schema header_row); row validation additionalProperties:True + extra keys silently skipped (typos vanish); writer-registry advisory (not enforced on mutation).

DECISIONS (do NOT re-litigate):
- P1-10: persist reason (pause) + notes (approve) into BOTH the run JSON and the emitted event metadata; for retry(), push prior {ended_at, failure_reason} into a retry_history[] before clearing ended_at; make swallowed emit failures VISIBLE (stderr warning) while keeping emission non-blocking. If workflow-run.schema.json has additionalProperties:false, add reason/notes/retry_history to its properties.
- P1-11: allocate run_id under the SAME fcntl.flock that guards append (lock → read max → write). Add a concurrency test.
- P1-06: classify Bash via normalize_audit_action("accessed", command=cmd); replace `|| true` with a path that prints a visible warning on failure but still exits 0 (non-blocking).
- P1-07: broaden the Bash-branch path extraction to handle quoted ("..."/'...'), spaced, and ~-prefixed master .xlsx paths before the sidecar check.
- P1-09: (a) _ensure_sheet_with_header honors schema header_row/data_start_row; (b) reject unknown row keys by default with allow_extra=False opt-in — BUT first verify no legit caller relies on silent-skip (if one does and keys are legit, fix the caller, or default that call site to allow_extra=True and record why; if truly unavoidable, WARN instead of hard-fail and record); (c) writer-registry enforcement on mutation only if low-risk, else document deferred.

HARD RULES:
1. Do NOT spawn subagents / Task / Agent tools — they fail here ("Prompt is too long"). Work inline.
2. Invoke superpowers:test-driven-development (RED → confirm fail → minimal fix → confirm GREEN → commit) + superpowers:verification-before-completion before claiming done.
3. Branch: git checkout -b fix/codex-audit-phase-5-state off main (confirm git log --oneline -3 shows the d75edf5 Phase 4 merge). Never commit to main, never push.
4. 5 atomic commits in the SAFE→RISKY order: P1-10, P1-11, P1-06, P1-07, P1-09 (P1-09 LAST). Messages in the brief §5.
5. Engine repo ONLY. Do NOT touch the workspace repo. Do NOT add pip dependencies.
6. NEVER commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md. Preserve untracked planning docs.
7. Baseline must stay green: PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q  >= 1523 passed, 8 skipped + your new tests.
8. ESCALATION ALLOWED: if a fix (esp. P1-09 extra-key rejection) proves more invasive than expected and would break existing writers, implement the safe part, DEFER the invasive part, and record it clearly in the report. Do NOT force a change that breaks existing behavior.

WORK PLAN (full detail + risk guards in the brief §5):
- Commit 1 (P1-10): RED tests (pause persists reason; approve persists notes; retry preserves prior ended_at in retry_history); GREEN by threading reason/notes through _do + event meta, adding retry_history, surfacing emit warnings; update workflow-run.schema if it's closed.
- Commit 2 (P1-11): RED concurrency test (many threads/procs allocate+append, assert unique run_ids); GREEN by allocating under the append flock.
- Commit 3 (P1-06): RED test (Bash rm/redirect classified as delete/modify not accessed); GREEN by wiring normalize_audit_action(command=cmd) + visible warning instead of || true.
- Commit 4 (P1-07): RED test (quoted/spaced/~ master paths blocked when ~$ sidecar present); GREEN by broadening Bash-branch path extraction.
- Commit 5 (P1-09, LAST): investigate callers first (rg transaction.(write|append|update)); RED test (header at header_row>1; unknown key rejected by default, allowed with allow_extra=True); GREEN with caller-safety + live-config re-validation; defer writer-registry enforcement if risky.

FINAL GATE (all must hold):
- python3 -m pytest tests/scripts tests/hooks -q   (all pass)
- PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   (>= 1523/8 + new)
- read-only sanity: dump_workspace --json still works; 10 live configs still validate.

WHEN DONE, output a paste-ready COMPLETION REPORT (template in the brief §8): branch + base/head sha; status; findings closed + any deferred sub-parts; 5 commit shas+messages; full-suite result + new test names + all-green Y/N; the per-finding confirmations listed in §8; deviations; blockers; git diff --stat.

BEGIN NOW: invoke superpowers:test-driven-development, open the brief, create the branch (verify base shows d75edf5), start Part A (P1-10), and work through all five parts in order. Run the full suite after each commit. For P1-09, investigate callers and re-validate live configs; defer-and-report rather than break existing writers.
