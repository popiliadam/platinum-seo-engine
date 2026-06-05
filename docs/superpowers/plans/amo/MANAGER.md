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
| **0a** | Cross-environment hook probe (empirically resolve session_id availability across VSCode/Mac-app/CLI) — **gates all binding code** | **PROMPT READY** → dispatch | — |
| 0b | Binding substrate: `resolve_session_project` helper (strict/advisory) + `/pseo-bind` (session-id marker file) + 4 consumer wirings (dump_workspace, content-gate, audit hook, banners) + engine-root via CLAUDE_PLUGIN_ROOT | blocked on 0a | 0a |
| 0c | Shared-resource safety: `portfolio.json` lock + backup-rotation glob fix + two-session-same-project guard | pending | 0b |
| 0d | Blocking `master.xlsx` lock (bounded timeout → `paused`); precedes ANY parallel writer | pending | 0c |
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

## Provenance
- Design hardened by 9-agent adversarial review: workflow run `wf_527271b3-931` (51 findings, conditional GO).
- Spec committed: `f00dfb4`.
