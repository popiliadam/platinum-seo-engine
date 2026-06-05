# AMO (Autonomy & Multi-project Orchestration) — Manager Roadmap

> **Manager session tracking doc.** The design spec is the authority:
> `docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md`.
> This file tracks the BUILD: batch sequence, decisions, status. The manager (Süleyman's
> primary session) authors one self-contained WORKER prompt per batch, dispatches it to a
> fresh **Opus 4.8 1M-context** worker, verifies the returned REPORT (suite-green + code-review +
> no out-of-scope files), commits, then dispatches the next batch.

## Build philosophy (operator-chosen 2026-06-05)
**Path A — start simple.** Hard-coded ordered Python sequences for 3-4 known workflows; NO
declarative DAG engine and NO auto-derived capability graph yet. "Knows all its parts" is
delivered by two targeted lints (body⊆declared MCP + observed⊆declared reconciliation), not a graph.
Promote to a general engine ONLY if a 4th workflow proves the abstraction earns its keep.

## Build model (every worker prompt enforces)
- **NO Task/Agent tools — work inline** (subagents FAIL here: MCP registry too large).
- **Baseline-first:** record exact `pytest` N at start; end strictly ≥ N.
- **TDD:** RED → GREEN → REFACTOR; `@code-reviewer` + `@verifier` before report.
- **Scope-locked:** only the batch's named files; out-of-scope need → STOP + report.
- **Schema-first** for any schema change (4-way sync; run `test_cross_sheet_invariants_sync.py`).
- **No commit** (manager commits after review). **Checkpoint:** append-only `PROGRESS.json` per task + WIP commits on an isolated worktree so a dead worker is resumable.

## Batch sequence & status

| Batch | Scope | Status | Prereq |
|---|---|---|---|
| **0a** | Cross-environment hook probe | ✅ **DONE + GREEN** (`e4c22c0`). **Operator data confirmed (VSCode):** `session_id` present+stable 5/5 events incl Stop; **hook `session_id` == command `$CLAUDE_CODE_SESSION_ID`** (proven via transcript namespace); `CLAUDE_PLUGIN_ROOT` reliable; `CLAUDE_ENV_FILE`/`PSEO_WORKSPACE_ROOT` unreliable. Mac-app/CLI re-check deferred to install-time. | — |
| **0b** | Binding **PRIMITIVE**: `scripts/state/session_binding.py` (resolve_session_project strict/advisory + marker R/W + `~/.config/pseo/config.json` persistence + `session_ids_consistent`) + `/pseo-bind` + `session-marker.schema.json` + tests. Marker at `shared/sessions/<uuid>.json`. | ✅ **DONE + GREEN** (manager-verified 1749 pass / 0 fail; 23 tests; path-traversal+slug guards; atomic `os.replace`; +3 count-guard bumps) | 0a |
| 0c | Wire the 2 **Python-script** consumers: `dump_workspace._resolve_slug` (strict, preserves legacy-'slug' + raises) + `validate_content_write._resolve_profile` (never-raise, session_id from stdin payload) + tests. No new command/schema. | ✅ **DONE + GREEN** (manager-verified 1762 pass / 0 fail; +13 tests; both contracts preserved; file-relative sys.path bootstrap for bare-CLI; no count-guard trip) | 0b |
| 0d | **Audit H1 fix** (review's highest-value Phase-0 change): extract the PostToolUse inline-python audit into a testable `scripts/hooks/audit_post_tool_use.py` that attributes events to the **session-bound** project (marker → active.json fallback) + classify RUNTIME + tests. Stops silent cross-project `events.jsonl` corruption under multi-window. | ✅ **DONE + GREEN** (manager-verified 1775 pass / 0 fail; +13 tests; session-bound attribution; ADR-032 delegation contract *strengthened*; env_probe intact; redaction parity; 2 approved out-of-scope test migrations) | 0c |
| 0d.1 | **Polish (deferred, low-priority):** SessionStart/UserPromptSubmit banners show the session-bound project + SessionStart `session_ids_consistent` self-check. Cosmetic/advisory, not correctness. | deferred | 0d |
| 0e | Shared-resource safety: `portfolio.json` lock + backup-rotation glob fix + two-session-same-project guard | pending | 0d |
| 0f | Blocking `master.xlsx` lock (bounded timeout → `paused`); precedes ANY parallel writer | pending | 0e |
| 1a | Schema migrations: `_state/coverage/<run_id>.json` shape + `failure_reason.external` bool + confirm `paused` reuse | pending | 0 |
| 1b | Ordered-sequence runner (`run_step.py`) + committer relocation + identity+content verify (idempotent `replace`) | pending | 1a |
| 1c | Intent router (one-voice UserPromptSubmit; marker lifecycle session_id/turn_id/intent_id) | pending | 1a |
| 1d | Reference workflow `monthly-maintenance` + `/pseo-run` + operator-remediation surface (Turkish fix-command) | pending | 1b,1c |
| 2a | Consent ledger (`_state/consent.jsonl`, append-only, hash-chained) + recorder | pending | 1 |
| 2b | PreToolUse outward-action gates (push/rm/POST/MCP-submit) + AI-disclosure content-surface rescan + secret-bytes scan | pending | 2a |
| 2c | Denetçi Stop-hook (reuse `paused`) + correctness oracle (`orchestration_metrics.py` reconcile-vs-provenance) | pending | 1d,2a |
| 3 | Replicate (new-project / content-pipeline / audit-suite) + the 2 mastery lints + registry fix (`sf_load_crawl`); promote-to-declarative decision gate | pending | 1,2 |
| 4 | Portfolio fan-out + cost/quota ledger + kill-switch + `/pseo-status --portfolio` + recovery runbook; scheduler default OFF | pending | 0-3 |

## Decision register
- **D1** Path A (hard-coded sequences; graph deferred) — Süleyman 2026-06-05.
- **D2** Binding = session-id marker FILE (not env var); resolution `arg → session-marker(session_id) → active.json`. Reason: env var unsettable in Mac app + `.env` never loaded into hooks (proven `env|grep PSEO` empty).
- **D3** Coverage → `_state/coverage/<run_id>.json`, NOT an events `event_type` (locked exactly-12 enum).
- **D4** External failure → reuse existing `paused` state + additive `failure_reason.external` bool. NO new `blocked` state, NO new fail-codes.
- **D5** Gates + correctness oracle built in Phase 2 ALONGSIDE the orchestrator, never deferred (G4 safety).
- **D6** Verification = identity+content (provenance-stamped raw drops, hard-fail on mismatch), NOT exists+non-empty.
- **D7** Probe-first: batch 0a is a diagnostic probe, dispatched before any binding code, to resolve O1 empirically.
- **D8** Batch-0a guard-relaxation (Option A, authorized + manager-verified): wiring the probe into Stop and adding a manual companion script collided with 2 guard tests. Relaxed minimally — `test_stop_validation` count `== 1`→`>= 1` (still locks `stop_validation.py` as the FIRST Stop command); added a third `DIAGNOSTIC_HOOK_SCRIPTS` class so every hook script stays classified. Protective contracts preserved, not weakened.
- **D9** Binding mechanism CONFIRMED (batch-0a probe + manager log analysis 2026-06-05): key = the Claude **session UUID**, sourced identically from hook-stdin `session_id` (hooks) and `$CLAUDE_CODE_SESSION_ID` (commands) — proven equal via the transcript-filename namespace. Engine root = `$CLAUDE_PLUGIN_ROOT`. Workspace root persisted to `~/.config/pseo/config.json` (env unreliable). Marker = `<workspace>/shared/sessions/<uuid>.json` (workspace-global, alongside active.json — corrects the spec's `_state/sessions` path).
- **D10** Count-consistency immune system (batch-0b learning): adding a `commands/*.md` or `schemas/*.json` file trips `tests/docs/test_count_consistency.py` (pins counts in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`) AND `tests/schemas/test_json_schema_draft_consistency.py` (`assert count==N`). So **every future batch that adds a command/schema MUST also bump those 2 manifests + the count test** (manager applies; marketplace blurb counts are factual, not advertising). Worker prompts that add commands/schemas should pre-warn this as an expected out-of-scope manifest bump. Narrative doc cites (README/ARCHITECTURE/INSTALL) are NOT test-enforced — defer to AMO release.

## Provenance
- Design hardened by 9-agent adversarial review: workflow run `wf_527271b3-931` (51 findings, conditional GO).
- Spec committed: `f00dfb4`.
