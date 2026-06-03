# Phase 5 — State / Write & Audit Hardening — Worker Brief

## 0. READ FIRST (worker onboarding)

- Fresh worker session. Engine repo: `/Users/apple/Documents/platinum-seo-engine`. ENGINE-ONLY.
- Invoke `superpowers:test-driven-development` + `superpowers:verification-before-completion`.
- **Branch:** `git checkout -b fix/codex-audit-phase-5-state` off `main` (confirm `git log --oneline -3`
  shows the Phase 4 merge `d75edf5`). Never commit to main, never push.
- Hard rules: NO subagents (Task/Agent fail here); atomic commits; never commit
  `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`; preserve untracked planning docs; do NOT touch the workspace repo.
- **Baseline:** `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`
  must stay ≥ **1523 passed, 8 skipped** + your new tests.
- **This is the most code-heavy phase** — real changes to state-mutation paths. After EVERY change run
  the full suite. If a fix proves more invasive than expected (esp. P1-09 extra-key rejection), it is
  OK to implement the safe part, DEFER the invasive part, and record it in the report (do NOT force a
  change that breaks existing writers).

## 1. GOAL + findings

**Goal:** Make state writes honest and auditable — workflow reason/notes are persisted, run-id
allocation is race-free, Bash audit actions are classified correctly (not all "accessed"), the Excel
owner-lock covers real path forms, and Excel writes honor the schema header row + reject typo'd keys.

- **P1-10** — `workflow_runner.py`: `pause(reason=…)` and `approve(notes=…)` accept those params but
  never persist them; `retry()` deletes `ended_at` (loses prior terminal timing); some event-emit
  failures are swallowed.
- **P1-11** — `events_writer.py` `next_run_id()` scans for the max run_id OUTSIDE the append lock →
  two concurrent callers can allocate the same id.
- **P1-06** — `hooks/post-tool-use.json` ends its inline command with `|| true` (silent audit-emit
  failure) and hardcodes `audit_action="accessed"` for ALL Bash commands (a `rm`/`cp`/redirect is
  logged as a mere access). `events_writer.normalize_audit_action(command=…)` exists but is unused.
- **P1-07** — `hooks/pre-tool-use.json` Excel owner-lock: the Bash-branch regex `[\w/.-]+…\.xlsx`
  misses paths with spaces, quotes, or `~`. (The Edit/Write branch already parses `file_path` correctly
  — only the Bash branch is fragile.)
- **P1-09** — `scripts/excel/transaction.py`: `_ensure_sheet_with_header` always writes the header to
  row 1 (ignores schema `header_row`); row validation uses `additionalProperties: True` and extra keys
  are silently skipped (typos vanish); writer-registry status is advisory (not enforced on mutation).

## 2. EVIDENCE (verified)

- P1-10: `workflow_runner.py` `pause` (~:564) calls `_do(..., paused_at=…)` with `reason` unused;
  `approve` (~:535) calls `_do(..., resumed_at=…)` with `notes` unused; `retry` (~:622) does
  `if "ended_at" in data: del data["ended_at"]`. `_do`/`_emit_workflow_event` wrap emits defensively.
- P1-11: `events_writer.py` `next_run_id` (~:583) scans events.jsonl for max int run_id with no flock;
  the append path (`_append…` ~:294-319) DOES use `fcntl.flock(LOCK_EX)`, but allocation is separate.
- P1-06: `hooks/post-tool-use.json` inline python: `audit_action=("modified" if tn=="Edit" else
  (("modified" if Write+exists else "created") if tn=="Write" else "accessed"))` → Bash always
  "accessed"; command ends `... ; sys.exit(0)' || true`. `events_writer.py:375` has
  `def normalize_audit_action(action, *, command=None)` (rm/mv/cp/redirect aware) — currently unused by the hook.
- P1-07: `hooks/pre-tool-use.json` Bash branch: `re.search(r"([\w/.-]+(?:_MASTER|master|-master)\.xlsx)", cmd)`
  then blocks only if a `~$<name>` sidecar exists.
- P1-09: `transaction.py` `_ensure_sheet_with_header` (~:564-576) writes header at `row=1` always;
  `_data_start_row` (~:588) DOES read schema `data_start_row` (used by write/append/update) — so creation
  (row 1) and data-landing (schema row) can disagree. Row-validation schema sets
  `"additionalProperties": True` (~:254); extra keys are dropped at write (~:840 "Validator allowed this
  key (additionalProperties:true)"). `writer_registry_status()` (~:523) is not called by write/append/update.

## 3. DECISIONS already made

- P1-10: persist `reason` (pause) and `notes` (approve) into BOTH the workflow run JSON and the emitted
  event metadata. For `retry()`: before clearing `ended_at`, push the prior `{ended_at, failure_reason}`
  into a `retry_history` array on the run JSON (preserve terminal timing). Make swallowed event-emit
  failures VISIBLE (stderr warning at minimum); keep emission non-blocking but no longer silent.
- P1-11: allocate the run_id under the SAME `fcntl.flock` that guards the append (one critical section:
  lock → read max → write next). Add a concurrency test.
- P1-06: classify Bash via `normalize_audit_action(action, command=<the bash command>)`; replace the
  blanket `|| true` with a visible warning on failure (still non-blocking so it never blocks a tool call).
- P1-07: in the Bash branch, parse candidate paths more robustly — handle quoted (`"…"`, `'…'`), spaced,
  and `~`-prefixed `.xlsx` master paths — before the sidecar check.
- P1-09: (a) align `_ensure_sheet_with_header` with the schema `header_row` (write the header at the
  declared row, not always row 1). (b) Make extra row keys FAIL by default with an `allow_extra=False`
  parameter (opt-in to skip) — BUT first verify no existing legit caller relies on silent-skip; if one
  does and the keys are legitimate, that is a real bug to surface (fix the caller) — if truly unavoidable,
  default to a visible WARN instead of hard-fail and record it. (c) Writer-registry enforcement on
  mutation: implement ONLY if low-risk; otherwise document as deferred (the audit said "consider").

## 4. FILE MAP

- Modify: `scripts/state/workflow_runner.py` (P1-10) ; Test: `tests/scripts/test_workflow_runner*.py` (extend) or new
- Modify: `scripts/state/events_writer.py` (P1-11) ; Test: `tests/scripts/test_events_writer_run_id_lock.py` (new)
- Modify: `hooks/post-tool-use.json` (P1-06) ; Test: `tests/hooks/test_post_tool_use_bash_classification.py` (new)
- Modify: `hooks/pre-tool-use.json` (P1-07) ; Test: `tests/hooks/test_pre_tool_use_owner_lock_paths.py` (new)
- Modify: `scripts/excel/transaction.py` (P1-09) ; Test: `tests/scripts/test_transaction_header_and_extra_keys.py` (new)

## 5. TASKS (TDD) — do in this order (safe → risky)

### Part A — P1-10 workflow reason/notes/retry (commit 1)
- [ ] RED: tests asserting `pause(reason="x")` writes `reason` into the run JSON (and event meta);
  `approve(notes="y")` writes `notes`; `retry()` after a fail preserves the prior `ended_at` in
  `retry_history`. Run → RED.
- [ ] GREEN: thread `reason`/`notes` through `_do`→`transition`/patch + `_emit_workflow_event` metadata;
  implement the `retry_history` preservation; add a stderr warning where emit failures were swallowed.
  Check `schemas/workflow-run.schema.json` — if it has `additionalProperties:false`, ADD `reason`,
  `notes`, `retry_history` to its properties so the run JSON still validates. Run → GREEN + full suite.
  Commit: `fix(state): persist workflow pause reason + approve notes + retry history; surface emit failures (P1-10)`.

### Part B — P1-11 run_id lock (commit 2)
- [ ] RED: a concurrency test that allocates+appends many run_ids from multiple threads/processes and
  asserts all run_ids are unique (today it can collide). Run → RED (or flaky-fail).
- [ ] GREEN: refactor so allocation happens inside the append flock (lock → compute next run_id → write).
  Run → GREEN deterministically + full suite. Commit: `fix(state): allocate event run_id under append lock to prevent races (P1-11)`.

### Part C — P1-06 Bash audit classification (commit 3)
- [ ] RED: `tests/hooks/test_post_tool_use_bash_classification.py` — extract the inline python from
  `hooks/post-tool-use.json`, feed it a Bash `rm foo.txt` (and a redirect `echo x > f`) tool payload, and
  assert the recorded `audit_action` is a delete/modify (via `normalize_audit_action`), NOT "accessed".
  Run → RED.
- [ ] GREEN: edit the hook's inline python to call
  `normalize_audit_action("accessed", command=cmd)` for Bash; replace `|| true` with a path that prints a
  visible warning on failure but still exits 0 (non-blocking). Run → GREEN + full suite. Commit:
  `fix(hooks): classify Bash audit actions via normalize_audit_action + surface emit failures (P1-06)`.

### Part D — P1-07 owner-lock path coverage (commit 4)
- [ ] RED: `tests/hooks/test_pre_tool_use_owner_lock_paths.py` — feed the hook's inline python Bash
  payloads referencing a master `.xlsx` via: a quoted path with a space (`"my master.xlsx"`), a
  single-quoted path, and a `~/…/master.xlsx` path; with a `~$` sidecar present it MUST block (exit 2).
  Run → RED (current regex misses these).
- [ ] GREEN: broaden the Bash-branch path extraction (quoted/spaced/`~`). Keep the Edit/Write branch as-is.
  Run → GREEN + full suite. Commit: `fix(hooks): broaden Excel owner-lock path detection (quotes/spaces/~) (P1-07)`.

### Part E — P1-09 Excel transaction (commit 5) — RISKIEST, LAST
- [ ] Investigate callers first: `rg -n "transaction\.(write|append|update)\(|\.write\(|allow_extra" scripts tests`
  and skim how rows are passed. Determine whether any legit caller passes extra keys expecting silent-skip.
- [ ] RED: `tests/scripts/test_transaction_header_and_extra_keys.py` — (1) creating a sheet whose schema
  declares `header_row>1` puts the header at that row (not row 1); (2) writing a row with an unknown key
  raises by default (and is allowed when `allow_extra=True`). Run → RED.
- [ ] GREEN: (a) make `_ensure_sheet_with_header` honor the schema `header_row`/`data_start_row`; (b) add
  `allow_extra: bool = False` to the write path and reject unknown keys by default. Run the FULL suite +
  re-validate the 10 live configs are untouched. If reject-by-default breaks a legit existing writer:
  surface it (fix the caller if it's a typo) or, if the extra keys are legitimately dynamic, default that
  call site to `allow_extra=True` and record why. If writer-registry enforcement is low-risk, add it;
  else note it deferred. Run → GREEN. Commit:
  `fix(excel): honor schema header_row + reject unknown row keys by default (allow_extra opt-in) (P1-09)`.

## 6. TEST GATE

```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m pytest tests/scripts tests/hooks -q
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   # >= 1523/8 + new
# state integrity sanity (read-only): the 10 live configs still validate; dump_workspace still works
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 scripts/state/dump_workspace.py --json | head -3
```

## 7. OUT OF SCOPE

- Docs counts / brand-onboarding / templates / requirements / dump_workspace docstring (Phase 6).
- Do NOT touch the workspace repo. Do NOT add pip dependencies.
- Do NOT broaden additionalProperties work to other schemas (only workflow-run.schema if P1-10 needs it).

## 8. COMPLETION REPORT (return to manager)

```
# Phase 5 Completion Report
- Branch: fix/codex-audit-phase-5-state | Base: d75edf5 (main) | Head: <sha>
- Status: DONE | PARTIAL | BLOCKED
- Findings closed: [P1-06, P1-07, P1-09, P1-10, P1-11]  | deferred sub-parts: <none | ...>
- Commits (5 atomic): <sha> <msg> ; ...
- Tests: full suite = "<N passed, M skipped>"; new tests: [files]; all green? Y/N
- P1-10: pause reason persisted? approve notes persisted? retry_history preserves ended_at? emit-failure now visible? (Y/Y/Y/Y)
- P1-11: run_id allocated under flock? concurrency test proves uniqueness? (Y/Y)
- P1-06: Bash rm/redirect classified as delete/modify (not accessed)? || true replaced with visible warning? (Y/Y)
- P1-07: quoted/spaced/~ master paths now blocked when sidecar present? (Y)
- P1-09: header_row honored on create? extra keys rejected by default (allow_extra opt-in)? any caller adjusted (which/why)? writer-registry enforced or deferred? live configs untouched?
- Deviations / judgment calls: <...>
- Blockers / questions for manager: <none | ...>
- git diff --stat: <paste>
```
