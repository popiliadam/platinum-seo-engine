# AMO batch 4a — portfolio cost/quota ledger substrate (reserve-then-confirm)

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note:** 4a is the FOUNDATION of Faz 4 (the portfolio/autonomy phase), exactly as 2a (consent
> ledger) was the foundation of Faz 2. It is the cost/quota ledger SUBSTRATE only — the atomic
> reserve-then-confirm mechanism + the hard-ceiling check. The fan-out / kill-switch / status / scheduler
> that USE it are later batches (4b-4d). Mirror the proven 2a `consent_ledger.py` append-only hash-chained
> flock pattern; the ONE new thing is the ceiling-enforcing atomic `reserve`.

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE self-contained
batch: the portfolio cost/quota ledger substrate. Follow every rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here — "Prompt is too long"). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: 2194 passed, 7 skipped, 0 failed. End state MUST be passed >= 2194 and failed == 0.
4. TDD, RED FIRST. Write the tests, RUN them, SHOW they FAIL for the right reason (module/schema absent),
   THEN implement. Never write implementation before a failing test.
5. SCOPE-LOCK. Create/modify ONLY the files in SCOPE. Anything else → STOP + report. In particular do NOT
   wire any hook, command, or the portfolio fan-out (those are batches 4b-4d). **Adding a new
   `schemas/*.json` trips the D10 count guards (`tests/docs/test_count_consistency.py` +
   `tests/schemas/test_json_schema_draft_consistency.py`) — that bump is the MANAGER's job; you scope-lock
   and SURFACE it in your REPORT, you do NOT edit `.claude-plugin/plugin.json` / `marketplace.json` / the
   count test.**
6. Python discipline: pure/clock-free (no wall-clock reads — timestamps + period are PASSED IN, like
   `now_iso`); immutability; functions < 50 lines; no debug prints; type hints; module docstring.
7. State discipline (CRITICAL — this is an append-only LOG, not a marker): atomic append via
   `os.open(O_WRONLY|O_CREAT|O_APPEND)` + `fcntl.flock(LOCK_EX)` + one `os.write` + `os.fsync`; read the
   tail / replay the chain UNDER the same flock; **NEVER `os.replace`/tempfile-rename** (that inode-swaps an
   append-only log and loses concurrent writers). Validate BEFORE the write (a defective entry never touches
   the file). This MIRRORS `scripts/state/consent_ledger.py` (2a) — read it first; replicate the pattern.

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (Faz 4 foundation — spec §7 Phase 4 + §8 O5)
═══════════════════════════════════════════════════════════════════════════════════════════════
Faz 4 runs 3-5 projects in parallel and (optionally, later) on a schedule. To never blow a real budget
(GSC daily call quota, DataForSEO credit pool, image-generation spend), the portfolio needs a SINGLE shared
cost/quota ledger with a HARD ceiling: before a run does costly work it RESERVES an estimate; if the
reservation would exceed the ceiling the reserve is REFUSED (the later kill-switch turns that into
`paused`, not silent degrade). After the work it CONFIRMS the actual (≤ reserved) or RELEASES (on
failure/cancel). The ceiling check must be ATOMIC across parallel projects — two projects must not both
pass the check and both spend the last credits. This batch builds ONLY that substrate (the mechanism); the
fan-out (4b), `/pseo-status --portfolio` (4c), and scheduler (4d) consume it.

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified — do NOT re-derive; DO read consent_ledger.py first)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. The template is `scripts/state/consent_ledger.py` (2a). Reuse its EXACT shape (replicate, do NOT import
   — it keys a frozen 2a/2b contract): `canonical_json` (sort_keys + compact separators + ensure_ascii=
   False), `compute_entry_hash` (sha256 over canonical_json of the entry WITHOUT entry_hash; prev_hash IS a
   hashed field), `GENESIS_HASH = "0"*64`, `verify_chain` (seq==i, prev_hash links, entry_hash reproduces),
   the `_read_last_entry`-under-flock + `append` critical section, Draft7 `_validate_entry`, the
   `_get_validator` lru_cache. These are generic hash-chain-log primitives — replicate them verbatim into
   the new module (adjust names/schema path).
B. Location is GLOBAL, under `shared/` (NOT per-project like consent): the ceiling is portfolio-wide. Path =
   `{workspace_root}/shared/cost_ledger.jsonl`. The `shared/` dir already holds `active.json` +
   `sessions/<uuid>.json`. No slug in the path (the ledger is one file for the whole portfolio); `run_id` +
   `project_id` are recorded as provenance FIELDS on each entry.
C. The reserve-then-confirm MODEL (the one genuinely new bit vs consent):
   - Three ops: `reserve` (hold an estimate), `confirm` (record the actual spend for a reservation),
     `release` (free a reservation — actual spend 0).
   - Each `reserve` mints a `reservation_id` — derive it deterministically from the under-lock `seq`
     (e.g. `f"r{seq}"`) so it's unique without a clock/RNG (both are BANNED — rule 6). `confirm`/`release`
     carry the `reservation_id` they target.
   - USAGE per (resource, period) = Σ over reservation_ids of the reservation's EFFECTIVE amount:
        * confirmed  -> the confirmed `amount` (the actual)
        * released   -> 0
        * still open -> the reserved `amount`
     (Replay the intact chain to compute this. A confirm's amount MUST be <= its reservation's reserved
     amount — validate in `confirm`, else ValueError, nothing written.)
   - `reserve(... ceiling ...)`: UNDER the flock, replay -> current usage(resource, period); if
     `usage + amount > ceiling` raise `CostCeilingExceeded` and write NOTHING; else append the reserve entry
     and return its `reservation_id`. THIS atomic read-replay-check-append is the whole point — do it all
     inside the one LOCK_EX critical section (consent only reads the LAST line under the lock; you replay
     the WHOLE chain under the lock).
D. `period` is an OPAQUE partition key passed IN (clock-free): a daily pool passes the UTC date string
   (`"2026-06-08"`), a fixed quota passes a constant (`"total"`). USAGE filters entries by (resource,
   period). The module never computes the date itself (the caller/4b does).
E. Resources are a fixed enum: `gsc_calls`, `dfs_credits`, `image_spend` (mirror the spec's three:
   "GSC call-count vs quota, DFS credits vs daily pool, image spend"). `amount` is a number >= 0.
F. Ceiling SOURCE: a plain operator-edited `{workspace_root}/shared/cost-ceilings.json` —
   `{ "gsc_calls": <n>, "dfs_credits": <n>, "image_spend": <n> }` (O5: the operator enters real quotas
   before the scheduler is armed). Provide `read_ceiling(workspace_root, resource) -> float | None` (absent
   file / key -> None). Do NOT add a schema for THIS file (keep it a simple config; validate lightly
   in-module) — only `cost-ledger.schema.json` is a new schema (one D10 bump, manager-applied).
G. This is purely ADDITIVE: it imports `session_binding` only for the CLI's workspace resolution (like
   consent_ledger); it never imports/alters events_writer / coverage / consent_ledger / the orchestrator.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW `schemas/cost-ledger.schema.json`        (the append-only entry contract)
2. NEW `scripts/state/cost_ledger.py`           (the ledger module + a read-only inspection CLI)
3. NEW `tests/state/test_cost_ledger.py`        (TDD)
Nothing else. (The D10 manifest bump for the new schema is the MANAGER's job — surface it, don't apply it.)

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC
═══════════════════════════════════════════════════════════════════════════════════════════════
`schemas/cost-ledger.schema.json` (Draft-07; mirror consent.schema.json's style):
  Required entry fields: `schema_version` (const "1.0"), `seq` (int >=0), `op`
  (enum reserve/confirm/release), `resource` (enum gsc_calls/dfs_credits/image_spend), `period` (string),
  `amount` (number >=0), `reservation_id` (string), `run_id` (string), `project_id` (slug pattern
  `^[a-z][a-z0-9-]*$`), `recorded_at` (date-time string), `prev_hash` (`^[a-f0-9]{64}$`), `entry_hash`
  (`^[a-f0-9]{64}$`). Optional: `note` (string). `additionalProperties: false`. (A confirm/release still
  carries `resource`/`period`/`amount` of the reservation it targets so replay needs no back-reference
  lookups beyond `reservation_id`.)

`scripts/state/cost_ledger.py` public API:
  - `CostLedgerError(Exception)` + `CostValidationError(CostLedgerError)` + `CostCeilingExceeded(CostLedgerError)`
    (carry resource/period/requested/ceiling/current on the ceiling error for the caller's paused message).
  - `canonical_json`, `compute_entry_hash`, `GENESIS_HASH`, `verify_chain` (replicated from consent).
  - `cost_ledger_path(workspace_root) -> Path` (`.../shared/cost_ledger.jsonl`; mkdir -p shared/).
  - `read_entries(workspace_root) -> list[dict]` (missing -> []; corrupt line -> raise).
  - `usage(workspace_root, *, resource, period) -> float` (replay the INTACT chain; broken chain -> raise,
    fail-closed — never under-report usage over tampered data). Effective-per-reservation per fact C.
  - `read_ceiling(workspace_root, resource) -> float | None` (fact F).
  - `reserve(workspace_root, *, resource, period, amount, ceiling, run_id, project_id, now_iso,
    note=None, schema_path=None) -> dict` — the atomic reserve (fact C). Returns the written entry (incl.
    its `reservation_id`). Raises `CostCeilingExceeded` (nothing written) when it wouldn't fit.
  - `confirm(workspace_root, *, reservation_id, amount, run_id, project_id, now_iso, note=None,
    schema_path=None) -> dict` — validate `amount <= reserved` for that reservation_id (raise if not / if
    unknown / if already confirmed-or-released), then append.
  - `release(workspace_root, *, reservation_id, run_id, project_id, now_iso, note=None,
    schema_path=None) -> dict` — append a release (idempotency: a release of an unknown/closed reservation
    raises; do not double-free).
  - A minimal READ-ONLY CLI: `python3 -m scripts.state.cost_ledger usage <resource> <period>
    [--workspace <path>]` prints `usage / ceiling / remaining` (resolve ws via session_binding like
    consent's CLI). No write subcommand (the orchestrator writes via the API; the operator edits
    cost-ceilings.json by hand).
  - `__all__`.
  Keep each function < 50 lines (factor a private `_append_entry(fd-under-lock, entry_dict, schema_path)`
  helper shared by reserve/confirm/release to stay DRY + under the limit).

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD — tests/state/test_cost_ledger.py (monkeypatch HOME if the CLI path is exercised; use tmp_path ws)
═══════════════════════════════════════════════════════════════════════════════════════════════
  • hash-chain: append a few entries -> verify_chain intact; flip a byte/seq -> verify_chain returns the idx.
  • reserve happy path: reserve(amount=10, ceiling=100) -> entry written, reservation_id present,
    usage==10.
  • reserve-then-confirm-less: reserve 10, confirm 4 -> usage==4 (the freed 6 returns to the pool).
  • reserve-then-release: reserve 10, release -> usage==0.
  • CEILING (the core invariant): with ceiling=100 and usage already 95, reserve(amount=10) raises
    `CostCeilingExceeded` AND writes NOTHING (read_entries length unchanged; usage still 95). reserve(5) at
    usage 95 -> OK (boundary: usage+amount == ceiling is ALLOWED; only > rejects — assert both edges).
  • period isolation: reserve 10 in period "2026-06-08" and 10 in "2026-06-09" -> usage per period is 10
    each, not 20 (daily-pool reset semantics).
  • resource isolation: gsc_calls and dfs_credits usages are independent.
  • confirm guard: confirm(amount > reserved) raises, nothing written; confirm of an unknown reservation_id
    raises; double confirm/release raises.
  • ATOMICITY (the parallel-safety proof): spawn N concurrent processes/threads each doing
    reserve(amount=10) against ceiling=50 -> EXACTLY 5 succeed, the rest raise CostCeilingExceeded, and the
    final usage is EXACTLY 50 (never 60). (Mirror consent_ledger's concurrency test / portfolio_writer's
    no-lost-update test — use subprocesses or a process pool so the flock is real.)
  • fail-closed: a tampered (broken-chain) ledger -> usage() raises (never silently under-counts).
  • schema: a malformed entry fails Draft7 validation before any write.
  • CLI smoke: `usage <resource> <period>` prints usage/ceiling/remaining and exits 0.
Run RED first (module+schema absent), then GREEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest (rule 3).
2. READ `scripts/state/consent_ledger.py` (the template) + `schemas/consent.schema.json` + one concurrency
   test (e.g. `tests/.../test_consent_ledger.py` or `tests/state/test_portfolio_writer.py`) for the
   real-flock concurrency-test pattern.
3. Write the tests (RED).
4. Write the schema + module (GREEN).
5. FULL suite -> passed >= 2194, failed == 0. Confirm the new schema is the ONLY count-guard trip (the two
   count tests may now FAIL — that's the EXPECTED D10 surface for the manager; REPORT it, do NOT fix it).
6. Self-review: never `os.replace`? clock-free (now_iso + period passed in)? reserve is atomic
   (read-replay-check-append all under ONE flock)? fail-closed on tamper? ceiling boundary (== allowed,
   > rejected)?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• The atomic reserve can't be made race-free with a single flock critical section (describe the race).
• You'd need a clock/RNG for reservation_id (you should NOT — derive from the under-lock seq).
• You'd need to touch any file outside SCOPE (a hook, a command, the orchestrator, the manifests).
• The reserve-then-confirm usage model has an ambiguity for a case you hit — describe it, don't guess.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE: the pytest numbers you measured.
2. RED PROOF: the new tests failing before implementation (module/schema absent).
3. SCHEMA + MODULE: the entry contract + the public API signatures; confirm the hash-chain primitives are
   replicated from consent_ledger (not imported) + never `os.replace` + clock-free.
4. CEILING + ATOMICITY: the ceiling-boundary test (== allowed, > rejected, nothing-written-on-reject) + the
   N-concurrent-reserve test proving EXACTLY ceiling/amount succeed and final usage is exact (no overspend).
5. RESERVE-THEN-CONFIRM: the confirm-less-frees + release-frees + period-isolation + confirm-guard results.
6. D10 SURFACE: state that adding `schemas/cost-ledger.schema.json` makes `test_count_consistency` +
   `test_json_schema_draft_consistency` fail and the EXACT counts they expect now (so the manager applies
   the bump). Do NOT edit the manifests/count test yourself.
7. FULL SUITE: the final `tail -5` (passed >= 2194; note the 2 count tests as the expected D10 trip).
8. ANYTHING you had to decide or that surprised you.
```
