# AMO Batch 0f — transaction.py: backup-rotation fix + blocking master.xlsx lock (WORKER PROMPT)

> **Manager note:** Two cohesive `scripts/excel/transaction.py` file-safety changes. File-disjoint from
> batch 0e (portfolio.json) → safe to run in a parallel worker window. Paste the block into a fresh
> Opus-4.8 1M Claude Code session at /Users/apple/Documents/platinum-seo-engine.

---

```text
You are a WORKER. Repo: /Users/apple/Documents/platinum-seo-engine (Python, pytest). AMO batch 0f, managed
elsewhere. Scope-locked, inline only, NO git, NO Task/Agent tools (they FAIL here), STOP + print REPORT when done.

HARD RULES: Baseline-first (`PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`,
record N — expect ~1775 passed; end green, passed >= N). TDD (RED first, never fake). Immutability, no debug
prints, functions <50 lines. Edit ONLY the files in SCOPE — anything else → STOP + report.

WHY: under 3-5 parallel sessions writing different projects' master.xlsx, two safety gaps remain:
(1) backup rotation can prune real .xlsx snapshots; (2) the master.xlsx lock is fail-fast (LOCK_NB) with no
retry, so a concurrent second writer's work is silently LOST. This batch fixes both — they are the last
parallel-write-safety holes before Phase 1.

ORIENT (read first): `scripts/excel/transaction.py` — `_rotate_backups` (~448-461), `_acquire_lock` (~361-395,
fail-fast `flock(LOCK_EX|LOCK_NB)` → `LockHeldError`; the `import time` at ~42 is currently UNUSED), and the
write entrypoints that call `_acquire_lock`. Also `scripts/validation/validate_invariants.py` check_F_22
(~1480, counts `master-*.xlsx`) and `scripts/state/dump_workspace.py::_backups_recent` (~160, `*.xlsx`) — the
globs the rotation must agree with. And the existing transaction tests (tests/scripts/test_transaction.py).

SCOPE — edit ONLY: `scripts/excel/transaction.py`, `tests/scripts/test_transaction.py`.

SPEC 1 — backup-rotation glob fix:
  `_rotate_backups` currently keeps the 7 newest of ALL files via `iterdir()`, so `.empty` first-write
  markers / tempfiles can displace real `master-*.xlsx` snapshots while the F-22 invariant (which counts only
  `master-*.xlsx`) still reports compliant. FIX: scope `_rotate_backups` to the SAME `master-*.xlsx` glob the
  invariant + `_backups_recent` use, so markers/tempfiles never count against the keep-7 budget. (Rotate
  markers on a separate or zero budget if needed.) TEST: seed a backup dir with `.empty` markers + 7
  `master-*.xlsx` → after rotation all 7 xlsx survive.

SPEC 2 — blocking-acquire option (the review's deferred-but-load-bearing fix):
  Add an `acquire_blocking: bool = False` path to `_acquire_lock` (and thread it through the public write
  entrypoints as an opt-in kwarg, default False = today's fail-fast behavior — NO regression). When True:
  `flock(LOCK_EX)` with a BOUNDED fixed deadline (e.g. 30s; use the already-imported `time`), polling/retry
  is fine but keep it simple (NOT jittered exponential backoff — over-engineering for a 1-operator tool). On
  deadline expiry raise a NEW typed `LockTimeout(Exception)` distinct from `LockHeldError` (so callers can
  tell "waited and gave up" from "fail-fast"). TESTS: (a) two sequential writers under acquire_blocking=True
  both succeed (no lost write); (b) a held lock past the deadline raises `LockTimeout` (use a short test
  deadline via a kwarg/param so the test isn't slow); (c) default path (acquire_blocking=False) still raises
  `LockHeldError` on contention (regression guard).

METHOD: baseline → tests RED → implement → full suite (passed >= N, 0 failed) → @code-reviewer + @verifier inline.
DURUR: if threading acquire_blocking through the entrypoints would change a public signature in a way that
breaks existing callers/tests → keep it an internal/optional kwarg (default False) and report. Do NOT change
the fail-fast default.

REPORT: baseline N + final pytest line; the rotation glob now used + proof 7 xlsx survive markers; the
acquire_blocking semantics + LockTimeout vs LockHeldError + proof the default is unchanged; only the 2 scoped
files changed; any DURUR/assumption.
```
