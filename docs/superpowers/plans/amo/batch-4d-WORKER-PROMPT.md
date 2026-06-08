# AMO batch 4d — scheduler (default OFF) + O5 arming gate + `/pseo-schedule` (arm/disarm/status)

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> the engine repo `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note (design — read before dispatching):** This is the AUTONOMY-ARMING batch — the most
> safety-sensitive piece of Faz 4. There is NO daemon (this is a Claude Code plugin loaded into sessions),
> so "scheduler" here = an **armed-schedule CONFIG marker** + an **arming GATE**; the actual periodic firing
> is EXTERNAL (OS cron / launchd / Claude Code scheduled-task invoking `/pseo-run-portfolio <workflow>`) and
> is DOCUMENTED in the 4e runbook — the engine never runs a background loop. The load-bearing safety property
> (4b follow-up (a) + spec O5) is **fail-closed arming**: the schedule CANNOT be armed while ANY budget
> ceiling is unset (an uncapped armed schedule = unbounded autonomous spend across the whole portfolio).
> Default OFF = a fresh workspace has no armed schedule. Per D11, the marker STAYS disarmed until Süleyman's
> end-to-end live acceptance — 4d ships the capability DISARMED + gated; it does not arm anything. Two D10
> bumps (a new schema + a new command) — both the MANAGER's job; the worker scope-locks + surfaces them.

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE batch: the
scheduler state primitive (default OFF) + its fail-closed arming gate + the /pseo-schedule recipe. Follow
every rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here with "Prompt is too long"). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: 2241 passed, 7 skipped, 0 failed (it may be HIGHER if batch 4c already merged — record
   what you SEE). End state: passed >= your baseline + your new tests. THE ONLY acceptable failing tests at
   the end are the D10 count guards (`tests/docs/test_count_consistency.py` for the new command +
   `tests/schemas/test_json_schema_draft_consistency.py` for the new schema — the manager applies those
   bumps). EVERY other test, INCLUDING all your new ones, MUST pass. If anything ELSE is red → STOP + report.
4. TDD, RED FIRST. Write tests, SHOW them fail for the right reason, THEN implement.
5. SCOPE-LOCK. Create/modify ONLY the files in SCOPE. Anything else → STOP + report. **Adding a schema +
   a command trips the D10 count guards — those bumps are the MANAGER's job; scope-lock and SURFACE the
   exact counts/literals, do NOT edit plugin.json / marketplace.json / the two count tests.**
6. SAFETY-FIRST, FAIL-CLOSED. The arming gate must REFUSE to arm when ANY ceiling is unset (O5). "Refuse"
   = raise a typed exception and write NOTHING. There is no override flag. A test must PROVE arming is
   refused with a missing ceiling (teeth).
7. Python discipline: pure/clock-free (`now_iso` is PASSED IN, never read from a clock — mirror cost_ledger
   / portfolio_runner); immutability (build new structures, never mutate inputs); functions < 50 lines; no
   debug prints; type hints; module + function docstrings.
8. State discipline: the schedule marker is a MUTABLE POINTER (armed flips to/from false), NOT an append-only
   log → use the canonical atomic marker writer `scripts.state.session_binding._atomic_write_json`
   (tempfile → fsync → os.replace), the SAME one `coverage.write_coverage` uses. Validate against the new
   schema BEFORE writing (invalid → raise, write nothing). (os.replace is CORRECT here — it is a marker, not
   events.jsonl/consent.jsonl/cost_ledger.jsonl which are append-only logs that must NEVER os.replace.)

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (spec §7 Phase 4 + §8 — scheduler off by default, armed only behind a cost gate)
═══════════════════════════════════════════════════════════════════════════════════════════════
Faz 4 lets the operator sweep the whole portfolio (`/pseo-run-portfolio`, 4b) under a shared budget ceiling
(4a). The final autonomy step is an OPTIONAL recurring schedule — but autonomy that can spend money
unattended is dangerous, so the spec makes it **default OFF**, requires **explicit per-cadence consent**, and
shows the **projected daily cost before arming**. 4b left an explicit follow-up: the scheduler MUST gate
arming on ALL ceilings being set (O5) — 4b's "unset ceiling → ∞ (no cap)" is fine for a MANUAL
`/pseo-run-portfolio` (a human is watching) but is unacceptable for an armed, unattended schedule. 4d builds
that gate + the armed-schedule marker + the `/pseo-schedule` arm/disarm/status surface. It does NOT fire
anything and does NOT arm anything by default; the actual periodic trigger is external (documented in the 4e
runbook), and per D11 the operator only arms after the one comprehensive live-acceptance run.

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified against the real source — do NOT re-derive; DO read the named files)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. 4a cost ledger (`scripts/state/cost_ledger.py`, shipped — read it). The READ you need for the O5 gate:
   `read_ceiling(workspace_root, resource) -> float | None` — reads `shared/cost-ceilings.json[resource]`;
   **None == UNSET (no ceiling configured).** Resources (the three pools, canonical order):
   `gsc_calls`, `dfs_credits`, `image_spend`. The O5 gate = ALL THREE return a non-None ceiling.
B. Portfolio + estimate (`scripts/orchestration/portfolio_runner.py`, shipped — read it). REUSE:
   - `list_projects(workspace_root) -> list[dict]` — the portfolio's projects IN ORDER (each a dict with at
     least `slug`); missing portfolio.json → []. Use `len(list_projects(ws))` for the ACTUAL on-disk project
     count (spec: "iterates the ACTUAL on-disk project count, not '3-5'").
   - `estimate_cost(workspace_root, workflow) -> dict[str, float]` — per-resource per-RUN estimate for a
     workflow (from `shared/cost-estimates.json`; absent → {}). This is the per-PROJECT-run estimate.
C. Projected cost math (the operator sees this BEFORE arming): one sweep runs the workflow on EVERY project,
   so per-sweep cost for a resource = `estimate_cost(ws, workflow)[resource] * len(list_projects(ws))`.
   Projected DAILY cost = per-sweep cost × sweeps-per-day for the cadence:
   daily → 1.0, weekly → 1/7, monthly → 1/30 (use these exact fractions). Provide BOTH the per-sweep cost and
   the projected-daily cost per resource in the result so the recipe can show them.
D. The marker write pattern: `scripts/state/session_binding.py` exposes `_atomic_write_json(path, obj)`
   (tempfile → fsync → os.replace → dir-fsync). `scripts/orchestration/coverage.py` is your template for
   "validate against a schema, then `_atomic_write_json`". The schedule marker lives at
   `{workspace_root}/shared/schedule.json` (GLOBAL, alongside active.json + portfolio.json + cost_ledger.jsonl
   — it is portfolio-wide, no slug in the path). Default OFF = the file is ABSENT (read returns a disarmed
   view) — arming CREATES it; disarming REWRITES it with armed=false (do not delete).
E. Consent model (self-contained — do NOT touch the frozen 2a consent.schema.json / consent_ledger): the
   2a consent ledger's 6-action enum (git_push/fs_delete/net_post/mcp_submit/index_update/dfs_oversized) is
   for OUTWARD actions and has no "schedule" action — DO NOT add one. "Explicit per-cadence consent" here =
   `arm(...)` REQUIRES an explicit `consent_ack=True` argument (the operator confirmed THIS cadence + cost);
   `arm` raises if consent_ack is not True. The marker records the acknowledged cadence + the projected cost
   it was armed at + armed_at (now_iso). CHANGING the cadence/workflow = a fresh `arm` (a new explicit
   consent) — there is no silent re-arm.
F. Clock-free: `arm`/`disarm` take `now_iso` as an argument (the recipe resolves it at the boundary with
   `date -u`, exactly like `/pseo-run-portfolio`). The module reads no clock and no RNG.
G. This is ADDITIVE: it imports cost_ledger (read_ceiling) + portfolio_runner (list_projects/estimate_cost)
   + session_binding (_atomic_write_json) and reads/writes ONLY shared/schedule.json. It NEVER edits the
   spine, the workflow drivers, the ledger, the gates, or `/pseo-run-portfolio`. It fires NOTHING.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW `schemas/schedule.schema.json`     (the armed-schedule marker contract — D10 schema bump)
2. NEW `scripts/state/schedule.py`        (read_schedule / all_ceilings_set / projected_cost / arm / disarm)
3. NEW `commands/pseo-schedule.md`        (arm/disarm/status recipe — D10 command bump)
4. NEW `tests/state/test_schedule.py`
5. NEW `tests/commands/...` ONLY IF needed for allowed-tools parity (prefer reusing the existing
   `tests/commands/test_allowed_tools_match_shell.py` coverage — it auto-discovers commands; check first).
Nothing else. (The D10 schema-count + command-count manifest bumps are the MANAGER's job — surface them.)

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC
═══════════════════════════════════════════════════════════════════════════════════════════════
`schemas/schedule.schema.json` (Draft-07, `additionalProperties:false`, mirror cost-ledger.schema.json's
  rigor). Fields:
  - `schema_version` (const "1.0")
  - `armed` (boolean) — REQUIRED. Default-OFF semantics: a disarmed marker has armed=false.
  - `workflow` (enum: monthly/audit/setup/content) — required IFF armed.
  - `cadence` (enum: daily/weekly/monthly) — required IFF armed.
  - `consent_ack` (const true) — required IFF armed (you cannot represent an armed schedule without consent).
  - `projected_daily_cost` (object: resource → number) — required IFF armed (what the operator saw).
  - `armed_at` (string, ISO-8601) — required IFF armed.
  - `disarmed_at` (string, ISO-8601) — optional (set when disarming).
  Use JSON-Schema `if/then` (like workflow-run.schema.json) so armed=true REQUIRES
  workflow+cadence+consent_ack+projected_daily_cost+armed_at, and armed=false allows a minimal marker.

`scripts/state/schedule.py` — pure, clock-free. Public API:
  - `schedule_path(workspace_root) -> Path` (`{ws}/shared/schedule.json`; mkdir -p shared/).
  - `read_schedule(workspace_root) -> dict` — the current marker; ABSENT file → a disarmed view
    `{"schema_version":"1.0","armed":False}` (default OFF). Malformed JSON → raise a typed error (fail-closed,
    do not silently treat a corrupt marker as disarmed-and-armable).
  - `all_ceilings_set(workspace_root) -> tuple[bool, list[str]]` — O5 gate: returns (True, []) iff every
    resource (gsc_calls/dfs_credits/image_spend) has a non-None `cost_ledger.read_ceiling`; else
    (False, [the unset resource names]).
  - `projected_cost(workspace_root, *, workflow, cadence) -> dict` — returns
    `{"project_count", "per_sweep": {resource: cost}, "per_day": {resource: cost}}` using fact-C math
    (validate cadence ∈ daily/weekly/monthly, workflow ∈ the 4 names; else raise).
  - `arm(workspace_root, *, workflow, cadence, now_iso, consent_ack) -> dict` — the GATE + the write:
      1. validate workflow + cadence enums (raise `ScheduleValidationError` on a bad value);
      2. require `consent_ack is True` (else raise `ScheduleConsentError` — fact E);
      3. O5 GATE: `ok, missing = all_ceilings_set(ws)`; if not ok → raise `ScheduleArmRefused(missing)` and
         write NOTHING (fail-closed — this is the load-bearing safety property);
      4. compute `projected_daily_cost` = `projected_cost(...)["per_day"]`;
      5. build the armed marker (armed=True + workflow + cadence + consent_ack=True + projected_daily_cost +
         armed_at=now_iso), validate against schemas/schedule.schema.json, `_atomic_write_json`, return it.
  - `disarm(workspace_root, *, now_iso) -> dict` — write a minimal marker `{schema_version, armed:False,
    disarmed_at:now_iso}` (validate + atomic write); idempotent (disarming an absent/already-disarmed
    schedule is fine). Return it.
  - Typed exceptions: `ScheduleError` (base) / `ScheduleValidationError` / `ScheduleConsentError` /
    `ScheduleArmRefused` (carries `.missing` = the unset ceiling resource names, for the Turkish refuse
    message). NO argparse write-CLI (the recipe is the entry; a read-only `status` helper is fine but prefer
    the recipe calls `read_schedule`).

`commands/pseo-schedule.md` (recipe; mirror `commands/pseo-status.md` frontmatter + engine-root resolution
  + `commands/pseo-run-portfolio.md` period/now_iso-at-the-boundary). `argument-hint: "[status|arm|disarm]
  [workflow] [cadence]"`; `model: sonnet`; `allowed-tools`: ONLY the Bash programs it invokes (python3, jq,
  date, + the find/sort/tail/xargs/grep from the engine-root resolution block) + Read, Write. NO MCP tools.
  Behavior:
  - `/pseo-schedule status` (default, no args): print `read_schedule` in plain Turkish (armed? which
    workflow/cadence? the projected daily cost it was armed at? or "Zamanlanmış görev YOK (varsayılan
    KAPALI)").
  - `/pseo-schedule arm <workflow> <cadence>`: FIRST call `all_ceilings_set` + `projected_cost`; if a ceiling
    is unset → print the Turkish refuse message naming the unset resource(s) + how to set them
    (`shared/cost-ceilings.json`), and DO NOT arm (this is the O5 fail-closed surface). Else SHOW the
    projected per-sweep + per-day cost, then require the operator to EXPLICITLY confirm (the per-cadence
    consent) before calling `arm(..., consent_ack=True, now_iso=<date -u>)`. Surface the written marker +
    a reminder that firing is EXTERNAL (see the recovery runbook) + that per D11 you only arm after the live
    acceptance.
  - `/pseo-schedule disarm`: call `disarm` + confirm in Turkish.

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD — the gate + the marker are fully unit-testable (tmp ws; write cost-ceilings.json + portfolio.json fixtures)
═══════════════════════════════════════════════════════════════════════════════════════════════
  • default OFF: `read_schedule` on a tmp ws with NO schedule.json → `{armed:False,...}` (no file created).
  • all_ceilings_set: all three ceilings present → (True, []); one missing → (False, ["dfs_credits"]); none
    present → (False, all three).
  • projected_cost: estimate × project_count for per_sweep; ×{1, 1/7, 1/30} for daily/weekly/monthly per_day;
    bad cadence/workflow → raise.
  • arm REFUSED (THE TEETH): a ceiling unset → `arm(...)` raises `ScheduleArmRefused` (with `.missing`) AND
    `schedule.json` is NOT created / NOT armed (assert the file state — nothing written).
  • arm CONSENT: `consent_ack=False` (or omitted) → `ScheduleConsentError`, nothing written.
  • arm SUCCESS: all ceilings set + consent_ack=True → marker written armed=True with workflow/cadence/
    projected_daily_cost/armed_at; re-`read_schedule` round-trips it; it validates against the schema.
  • disarm: after arming, `disarm` → marker armed=False + disarmed_at; idempotent on an absent schedule.
  • schema instance-validation: a hand-built armed record validates; an armed record MISSING consent_ack /
    projected_daily_cost / workflow FAILS validation (the if/then teeth).
  • clock-free: arm/disarm take now_iso; grep the module → no datetime.now / time.time / random.
  Run RED first (module + schema absent), then GREEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest (record tail-5).
2. READ first: `scripts/state/cost_ledger.py` (read_ceiling + the resources), `scripts/orchestration/
   portfolio_runner.py` (list_projects + estimate_cost), `scripts/orchestration/coverage.py` (the
   validate-then-_atomic_write_json pattern), `scripts/state/session_binding.py` (`_atomic_write_json`),
   `schemas/cost-ledger.schema.json` + `schemas/workflow-run.schema.json` (Draft-07 + if/then rigor to
   mirror), `commands/pseo-status.md` + `commands/pseo-run-portfolio.md` (recipe shape + boundary clock),
   `tests/commands/test_allowed_tools_match_shell.py` (what it checks), `tests/schemas/
   test_json_schema_draft_consistency.py` (the schema-count guard you will trip).
3. Tests RED → implement schema + schedule.py + recipe → GREEN.
4. FULL suite → passed >= baseline; confirm the ONLY red tests are the two D10 count guards (schema-count +
   command-count) — list the exact literals the manager must bump.
5. Self-review: arming FAIL-CLOSED on any unset ceiling (teeth proven)? consent_ack required? clock-free?
   marker uses os.replace via _atomic_write_json (NOT append-only; NOT a log)? default OFF (absent file →
   disarmed, fires/arms nothing)? no spine/driver/ledger/gate edit? projected cost uses the ACTUAL project
   count?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• `read_ceiling` / `list_projects` / `estimate_cost` / `_atomic_write_json` signatures differ from facts
  A/B/D (quote the real signature).
• You believe the schedule needs to FIRE something itself (it must not — firing is external; if you think
  otherwise, STOP + describe why before building any trigger).
• You'd need to touch the frozen consent.schema.json / consent_ledger, the spine, a driver, the ledger, or
  `/pseo-run-portfolio` to make this work.
• Any ambiguity in the arming-gate / consent / projected-cost semantics you can't resolve from the facts.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE (tail-5).
2. RED PROOF (schema + module absent → new tests fail for the right reason).
3. schedule.py API: read_schedule / all_ceilings_set / projected_cost / arm / disarm signatures + confirm
   clock-free (now_iso passed in) + the typed exceptions.
4. O5 ARMING-GATE TEETH (the headline): the unset-ceiling test — `arm` raises `ScheduleArmRefused(.missing)`
   AND schedule.json is NOT armed/created (quote the assertion proving nothing was written).
5. CONSENT + SUCCESS: consent_ack=False → refused (nothing written); full arm → marker armed=True with the
   projected_daily_cost it was armed at; round-trips + schema-validates.
6. DEFAULT OFF: a fresh ws reads disarmed without creating a file; disarm is idempotent.
7. SCHEMA TEETH: an armed record missing consent_ack/projected_daily_cost/workflow FAILS schema validation
   (the if/then).
8. D10 SURFACE: the EXACT bumps the manager must apply — `*.schema.json` count (the
   test_json_schema_draft_consistency assert + marketplace "N schemas") AND the command count
   (test_count_consistency + plugin.json "N slash command" + marketplace "N commands"). Do NOT edit them.
9. RECIPE: allowed-tools matches the Bash programs (test_allowed_tools_match_shell green); the arm path shows
   projected cost + refuses-when-uncapped + requires explicit consent; NO MCP calls; it fires nothing.
10. FULL SUITE: final tail-5 (passed >= baseline; the two count guards noted as the expected D10 trips —
    every other test, including all yours, green).
11. ANYTHING you decided or that surprised you.
```
