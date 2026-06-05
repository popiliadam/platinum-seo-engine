# AMO Batch 0e — portfolio.json concurrency safety (WORKER PROMPT)

> **Manager note:** Lower-frequency parallel-write hole (`shared/portfolio.json` is workspace-global,
> written by init-project, with no lock → two concurrent `/pseo-init` = lost update). File-disjoint from
> batch 0f (transaction.py) → parallel-safe. The write mechanism is uncertain — the worker investigates
> first and may DURUR if it's model-executed-only. Paste into a fresh Opus-4.8 1M session.

---

```text
You are a WORKER. Repo: /Users/apple/Documents/platinum-seo-engine (Python, pytest). AMO batch 0e, managed
elsewhere. Scope-locked, inline only, NO git, NO Task/Agent tools (FAIL here), STOP + print REPORT when done.

HARD RULES: Baseline-first (`PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`,
record N ~1775; end green, passed >= N). TDD (RED first). Immutability, no debug prints, functions <50 lines.
Edit ONLY the files you determine are in scope below — anything surprising → STOP + report.

WHY: `shared/portfolio.json` is a workspace-GLOBAL registry written when a project is initialized. It has NO
lock around its read-modify-write, so two parallel sessions initializing projects at once can lost-update or
corrupt it. Make its mutation concurrency-safe so the multi-session (3-5 parallel projects) goal is durable.

STEP 1 — INVESTIGATE (report what you find): grep for every writer of `portfolio.json` (skills/meta/init-project,
scripts/, any helper). Determine HOW it is written:
  (a) a callable Python function/script with a read-modify-write → you can wrap it in a lock. PROCEED.
  (b) an append-only add of one project entry → safest fix is atomic append (or a blocking lock around it).
  (c) model-executed inline python inside a SKILL.md (no callable code) → there is nothing to lock in code.
      DURUR: STOP and report this with a recommended fix (extract to a small testable helper, OR convert
      portfolio.json to append-only JSONL like events.jsonl) for the manager to scope as a follow-up.

STEP 2 — IF (a)/(b): make the read-modify-write atomic + serialized. Reuse the engine's canonical discipline:
a blocking `fcntl.flock(LOCK_EX)` around the read-modify-write (mirror `scripts/state/events_writer.py`'s
blocking-lock append pattern) OR convert to append-only JSONL. Preserve the existing portfolio.json shape +
all existing readers (e.g. monitoring-weekly, portfolio.config consumers) — do not break the schema. Keep it
a minimal, behavior-preserving change (same data, just safe under concurrency).

SCOPE: the writer module/helper you identified + its test file. If the only safe fix needs a NEW helper
module, that's fine (new script + test), but if it needs a SKILL.md runtime extraction beyond a thin helper,
DURUR and report.

TDD: two concurrent writers (threads or sequential-with-injected-contention) both land their entries with no
lost update; the file stays valid JSON/JSONL; existing readers still parse it. Use tmp_path; never touch the
real workspace.

METHOD: baseline → investigate (report mechanism) → tests RED → implement → full suite (passed >= N, 0 failed)
→ @code-reviewer + @verifier inline.

REPORT: baseline N + final pytest line; the portfolio.json write mechanism you found + the safety approach
(lock vs append-only JSONL) + proof of no-lost-update + existing readers intact; files changed; any DURUR.
```
