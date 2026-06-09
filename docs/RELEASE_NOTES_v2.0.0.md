# Platinum SEO Engine — v2.0.0 Release Notes

**Release date:** 2026-06-09
**Engine HEAD:** v2.0.0 release commit (5-file sync via `version_bump --apply`)
**Predecessor:** [v1.9.5](RELEASE_NOTES_v1.9.5.md) (cross-repo codex-audit closure)
**Status:** 🟢 GREEN — AMO build complete + LIVE-PROVEN (D11 acceptance passed on a real GSC project; full suite 2312 PASS / 7 SKIP / 0 FAIL)

## 0. Executive Summary

v2.0 is the **AMO milestone — Autonomy & Multi-project Orchestration**. Where v1.x delivered the schema-locked, drift-checked single-project SEO toolchain, v2.0 adds an **autonomous, agentic orchestration layer** on top of it. It answers two long-standing operator needs:

1. **"The right skill/MCP usually doesn't auto-engage — work goes manual."** → An **orchestrator** turns an intent ("do monthly maintenance for `<project>`") into a hard-coded ordered pipeline that runs every required step and **verifies each step's OUTPUT** (identity + content gate), with a Stop-hook **denetçi** that forces any skipped owed step and a Turkish one-line fix surface on any non-pass.
2. **"I can only work one project at a time; I want 3-5 in parallel."** → **Per-session project binding** (N windows = N projects, correct attribution) + a **portfolio sweep** that runs a workflow across the whole portfolio under one shared budget ceiling.

Around those, v2.0 adds the **safety + enforcement layer** that makes autonomy trustworthy: a per-session **consent gate** that hard-blocks outward actions (git push / fs delete / network POST / GSC sitemap submit / Indexing update) unless explicitly approved; a PostToolUse **AI-disclosure quarantine** that keeps "written by AI" out of visible HTML even via a Bash bypass; an independent **correctness oracle** that measures the real ≤5% structured-error rate (not the self-reported verdict); a portfolio **cost/quota ledger** with an atomic reserve-then-confirm under a hard ceiling + a **kill-switch** (ceiling hit → `paused`, never silent under-run); and an **O5 fail-closed scheduler** that refuses to arm an unattended schedule while any budget ceiling is unset.

**Build model:** the AMO initiative was built by fresh **Opus-4.8 1M-context worker** sessions, one self-contained TDD batch each, with a **manager session** that independently re-derived every worker's central claim (own code/own data — not the worker's green checkmark) before commit + push. **Design hardened by a 9-agent adversarial review** (51 findings, conditional GO; all must-fixes folded into the spec). **Path A** (hard-coded ordered sequences, no general DAG engine) was deliberately chosen and **vindicated** — Faz 3 surfaced two distinct driver *shapes* (data-driver + artifact-driver), proving a single universal engine would over-abstract.

**Suite: → 2312 PASS / 7 SKIP / 0 FAIL** (+~520 tests across the AMO initiative; zero regression). **D11 live-acceptance PASSED** end-to-end on a real GSC-verified project (demo-furniture), the first live run of the loop — it surfaced and fixed 4 live-only integration bugs no stub test could catch (see §6).

## 1. Faz 0 — Per-session project binding (`09674c5`)

The foundation for multi-project parallelism. Each Claude session is bound to **one** project by the session UUID (identical from the hook-stdin `session_id` and the command `$CLAUDE_CODE_SESSION_ID` — D9, proven empirically by the batch-0a cross-environment probe). The binding marker lives at `<workspace>/shared/sessions/<uuid>.json`; the workspace root persists to `~/.config/pseo/config.json` (env vars proved unreliable across the Mac app). PostToolUse audit attribution is session-bound (no more silent cross-project `events.jsonl` corruption under multi-window), and `portfolio.json` / `transaction.py` got flock-guarded parallel-write safety.

## 2. Faz 1 — The orchestrator (`3b9d87e` + `1fa70d3`)

A **shared spine** (`scripts/orchestration/`): `run_step` (verify-raw-drop → transform → commit → silent-skip gate → coverage), `verify` (identity + content + freshness raw-drop gate, stable reason codes), `committer` (idempotent `transaction.replace` wrap), `coverage` (the frozen `coverage.schema.json` record), `remediation` (the Turkish one-line fix surface). The **`monthly-maintenance`** reference workflow + `/pseo-run` command drive the loop end-to-end: intent → ordered pipeline → per-step output verification → idempotent commit → coverage record → Turkish remediation on any non-pass. The transform-impedance wrinkle (skill CLIs write `{sheet}.json`) is resolved by a per-step `output_file` loader — **no spine edit**.

## 3. Faz 2 — Gates, denetçi, oracle (`95bc421`)

The safety + enforcement layer, six batches:
- **Consent ledger** (`consent_ledger.py`) — append-only, hash-chained, per-session (`/pseo-approve`); O_APPEND + flock, never `os.replace`.
- **Outward-action gate** (`outward_action_gate.py`, PreToolUse) — classifies git_push / fs_delete / net_post / mcp_submit / index_update; **default-DENY** unless an intact-chain consent matches `session_id + action + target_hash`; conservative classification so a non-gated Bash never bricks; fail-CLOSED on the gated path.
- **AI-disclosure rescan** (`ai_disclosure_rescan.py`, PostToolUse) — quarantines any blog HTML whose rendered surface carries an AI-disclosure signal, catching the Bash/heredoc bypass of the Write-time validator (Süleyman hard-constraint).
- **Denetçi** (`denetci.py`, Stop-hook) — reads the intent marker + coverage; a declared-but-unrun or incomplete/failed workflow **blocks** turn-end with a Turkish `--resume` fix; a `paused` external failure is allowed + RED-flagged.
- **Correctness oracle** (`orchestration_metrics.py`) — reconciles committed master.xlsx rows vs the transform output per run, **independent of the self-reported verdict** → the trustworthy ≤5% number (`fake_green` headline); READ-ONLY.

## 4. Faz 3 — Replication + the two mastery lints (`8631ff3` + line)

The orchestrator generalized to **4 workflows** — `monthly` + `audit` + `setup` + `content` — and **two driver shapes emerged** (the clean architectural result that vindicates Path A):
- **Data-driver** (monthly / audit / setup): raw MCP drop → transform CLI → verify → committer → master.xlsx rows; shares `_run_one` / the D15 attested-path dispatch via `workflow_driver.py`.
- **Artifact-driver** (content): the model emits a blog HTML artifact → verify artifact-exists + the `content_validator` AI-disclosure gate; shares only the coverage/completion-guard layer.

Plus the **two §4 "mastery" lints** that let the system *know its parts*: lint #1 `body ⊆ declared` MCP (static SKILL.md analysis, invocation-precise) and lint #2 `workflow-tool ⊆ skill-declared ⊆ registry` (the runtime-reconciliation idea was refuted on real data and reframed static — D17); the **F-27** drift rule (`declared-outward-MCP ⊆ gate`, consent-wall drift); the oracle generalized workflow-agnostic; the `sf_load_crawl` registry fix; and an O4 light-promote that extracted the shared data-driver.

## 5. Faz 4 — Portfolio fan-out + cost ceiling + scheduler

The multi-project payoff, six batches:
- **4a cost/quota ledger** (`cost_ledger.py`) — a GLOBAL `shared/cost_ledger.jsonl`, append-only + hash-chained; **atomic reserve-then-confirm under a hard ceiling** (read + replay + ceiling-check + append all under one `flock` → parallel runs can never both overspend); resources `gsc_calls` / `dfs_credits` / `image_spend`; clock-free.
- **4b portfolio sweep** (`/pseo-run-portfolio`, `portfolio_runner.py` + `project_lock.py`) — a sequential sweep under per-project NON-blocking locks (a busy project is skipped, never waited on) with job-level budget preflight; the **kill-switch**: a reserve over the ceiling → release partials (no leak) + `paused` + STOP the sweep (remaining → `not_run`), never a silent under-run.
- **4c portfolio triage** (`/pseo-status-portfolio`, `portfolio_status.py`) — a READ-ONLY triage classifying each project healthy / owed / failed-internal / paused-external (derived from the coverage verdict) + a global budget block.
- **4d scheduler** (`/pseo-schedule`, `schedule.py` + `schedule.schema.json`) — **default OFF**; the **O5 fail-closed arming gate** refuses to arm an unattended schedule while any ceiling is unset (the load-bearing safety property); explicit per-cadence consent + projected daily cost shown before arming; the engine **fires nothing** — the periodic trigger is external.
- **4e recovery runbook** (`docs/RUNBOOK-portfolio-recovery.md`) — symptom → what-you-see → exact-recovery for every Faz-4 outcome, guarded by a citation-existence test.
- **4f consolidation** — `ACTIVE_PROJECTS_MAX` lifted into one module sourced from the schema's `maxItems` (behavior-preserving; the copy can never return).

## 6. D11 — Comprehensive live-acceptance (`2a00049`)

The build's closing gate: ONE all-phases live run on a real GSC-verified project (demo-furniture) — the **first time the AMO loop ran live** (it had been stub-tested only). It did exactly its job, surfacing **4 integration bugs the 2312-test suite never caught** (all "stub fixture agrees with buggy code"), each fixed + manager-independently re-verified:

1. **`portfolio_runner` / `portfolio_writer` read the non-canonical key `projects`** — the schema (`#/required`) + all reporting readers + the live `portfolio.json` use **`active_projects`**; this blocked all of Faz 4. (Root cause: a wrong key in a manager worker-prompt fact, inherited by the independent re-derivation — only live data caught it.)
2. **Stale installed plugin cache** — live commands run from the version-keyed install cache, not the dev repo; re-synced (and the v2.0 version bump systematically prevents this class: the cache is keyed by version, so a release forces a fresh install).
3. **`gsc_pull` + `quick_wins` reclassified `code_verified` → `model_attested`** — both are genuinely AGGREGATING transforms (gsc_pull groups query×page → per-page; quick_wins is a position-band detector) that legitimately commit far fewer rows than received, so the silent-skip count gate was a category error on live volumes; identity / freshness / truncation gates still hard-fail, the oracle still backstops, and `content_decay` is kept `code_verified` as the completeness anchor (matches the audit workflow's precedent).

Live `monthly` on demo-furniture reached **verdict = pass** end-to-end, and the consent gate blocked the worker's **real** `rm` + `git push` → `/pseo-approve` → passed (the gate proven on real commands, beyond simulation).

## 7. Schema Changes

| File | Change | Migration? |
|------|--------|-----------|
| `schemas/coverage.schema.json` | NEW — the per-run coverage proof (Faz 1) | NO |
| `schemas/intent-marker.schema.json` | NEW — the one-voice intent router contract (Faz 1) | NO |
| `schemas/consent.schema.json` | NEW — the append-only hash-chained consent entry (Faz 2) | NO |
| `schemas/cost-ledger.schema.json` | NEW — the reserve/confirm/release ledger entry (Faz 4a) | NO |
| `schemas/schedule.schema.json` | NEW — the armed-schedule marker, if/then-gated (Faz 4d) | NO |
| `schemas/cross-sheet-invariants.json` | F-27 drift rule added | NO |

`*.schema.json` count **25 → 26** (schedule); all-`*.json` **26 → 27**; `additionalProperties:false` + Draft-07 throughout.

## 8. Migrations

**None at the schema-version level.** AMO state lives in dedicated files (`_state/coverage/`, `shared/cost_ledger.jsonl`, `shared/schedule.json`, per-project `consent.jsonl`) outside the existing master.xlsx / project-config contracts, so no existing artifact needs migrating.

## 9. New Commands & Hooks

**Commands** (`/pseo-run`, `/pseo-run-portfolio`, `/pseo-status-portfolio`, `/pseo-schedule`, `/pseo-approve`, `/pseo-bind`) drive the orchestrator, the portfolio sweep, the triage, the scheduler, consent, and session binding. Slash-command count **→ 24**. **Hooks**: the PreToolUse outward-action gate, the PostToolUse AI-disclosure rescan + audit, the Stop-hook denetçi — all classified RUNTIME, READ-ONLY except their sanctioned writes.

## 10. Tests

**After v2.0 ship: 2312 PASS / 7 SKIP / 0 FAIL** (+~520 across the AMO initiative; zero regression). Every batch was TDD (RED → GREEN), and the manager independently re-derived each batch's central safety/correctness claim with its own code + data (e.g. the kill-switch no-leak, the O5 arm-refuse writes-nothing, the oracle reconcile) rather than trusting the worker's report.

## 11. Backward Compatibility

- **Additive** — the AMO layer sits on top of the v1.x toolchain; no existing skill, schema, or command changed behavior. `/pseo-run` reuses the existing transform CLIs; the orchestrator never edits the master.xlsx contract.
- **Autonomy is OFF by default** — the scheduler ships disarmed; nothing runs unattended until the operator arms it (which requires all ceilings set + explicit per-cadence consent).
- **`.mcp.json` untouched** — the F-16 byte-stability invariant holds.

## 12. Notes for Operators

- **Before arming the scheduler:** set all three ceilings in `shared/cost-ceilings.json` (the O5 gate refuses to arm otherwise) and tune `shared/cost-estimates.json` so a full-portfolio sweep fits under the ceiling (else the kill-switch fires near the end of every sweep — safe, but it under-sweeps). `dfs_credits` is real prepaid money — set its ceiling to your DataForSEO balance comfort.
- **The scheduler fires nothing itself** — wire an external trigger (OS cron / launchd / a Claude Code scheduled task) to invoke `/pseo-run-portfolio <workflow>` on the cadence; see `docs/RUNBOOK-portfolio-recovery.md` §6.
- **Multi-environment acceptance** — D11 proved the loop live in VS Code; the Mac-app + CLI columns of the acceptance checklist are deferred until the operator works wide across environments (the binding mechanism is identical — the session-UUID marker).
- **Deferred (post-v2.0):** self-upgrade artifact-versioning (defense-in-depth for mixed-version data artifacts); the marketplace PRIVATE → PUBLIC transition (its own security-audit cycle).
- **Push is operator-gated** — release tag + commits reach `origin/main` under the same consent discipline the engine enforces.
