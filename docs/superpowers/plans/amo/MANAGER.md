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
| 0e | `portfolio.json` concurrency safety. **DURUR (case c):** the only writer is model-executed inline python in `init-project/SKILL.md` Step 6 (no callable code to lock; the test has a hand-copied mirror). Manager approved **Option 1**. → see **0e2**. | DURUR'd → 0e2 | 0d |
| 0e2 | Option-1 build: extract flock-guarded `scripts/state/portfolio_writer.py` + rewire `init-project` Step 6 to call it + convert the test mirror to an import + concurrency TDD. Behavior-preserving (identical JSON shape). | ✅ **DONE + GREEN** (manager-verified 1789 pass / 0 fail; +8 tests; flock(LOCK_EX) RMW, ftruncate, no-lost-update 10/10 vs old 1/10; mirror→import; shape+readers intact) | 0e |

> ## 🎉 PHASE 0 COMPLETE (2026-06-05) — committed `09674c5`, pushed origin/main (0/0)
> Per-session project binding foundation is shipped + green: session-id marker binding (0a-0c), session-aware
> audit attribution (0d), and parallel-write safety (0e2 portfolio.json + 0f transaction.py). Full suite 1789
> pass / 0 fail. **FRESH MANAGER SESSION took over 2026-06-05 via FRESH-MANAGER-BOOTSTRAP.md → now driving Faz 1.**
> **Faz 1 PROGRESS: 1a ✅ (`7c8d66d`) → 1b ✅ (`d045da5`) → 1c ✅ (`7d712ef`, 1872/0). 3 of 4 Phase-1 batches done.** NEXT = **1b2** (relocate gsc-pull/quick-wins/content-decay writes into the committer — the blast-radius migration) → then **1d** (monthly-maintenance workflow + /pseo-run + remediation). 1b2→1d are SEQUENTIAL (1d depends on 1b2) → **no more parallel-worktree contention; run serially.** ⚠️ A separate **Codex "ruthless handoff" audit** (72/100) landed untracked in the worktree (`docs/audits/2026-06-05_ruthless_claude_code_handoff.md`) — NOT part of AMO; left for separate triage, deliberately excluded from the 1c commit.
>
> ⚠️ **PARALLEL-WORKTREE LESSON (2026-06-05):** 1b + 1c were run in the SAME working tree (two windows, one repo dir) → their uncommitted WIP intermixed; each worker's full-suite run saw the other's half-built state (1b worker observed failure counts wobble 2→10 live). Mitigation applied: commit SCOPE-LOCKED (stage only the batch's files). **For future parallel batches: either give each worker its own `git worktree` (spec §9 checkpoint intent) OR serialize the commits.** Also: a hook-REWRITE batch (1c) must pre-orient on tests pinning the OLD hook behavior (`test_user_prompt_submit_context_injection.py` ×6 + `test_active_project_contract.py` ×3 + `test_trigger_declaration_parity.py` ×1) and scope their migration in — my 1c prompt under-scoped this (manager-author gap). See memory `project_amo_parallel_worktree_contention.md` (1b worker).
| 0f | `transaction.py`: backup-rotation glob fix + **blocking master.xlsx lock** (`acquire_blocking` opt-in, bounded → `LockTimeout`; default fail-fast unchanged) | ✅ **DONE + GREEN** (manager-verified 1781 pass / 0 fail; +6 tests; default byte-identical/no-regression; fd-leak-safe; `LockTimeout` sibling of `LockHeldError`; rotation scoped to `master-*.xlsx` + vestigial-marker prune) | 0d |
| ~~two-session-same-project guard~~ | Deferred edge-case (per-project locks already prevent corruption; one-window-per-project discipline covers it) — fresh manager may pick up post-Phase-0 | deferred | — |
| 1a | Schema migrations: NEW `schemas/coverage.schema.json` (run_id/steps[{name,verification_class,status,observed_mcp[],input_count,scored_count}]/required_satisfied/verdict) + additive `failure_reason.external` bool (both schema copies + `fail()` writer) + confirm `paused` reuse (transition-edge test, no code). D10: draft-count 21→22 + marketplace "22→23 schemas". | ✅ **DONE + GREEN** (`7c8d66d`, manager-verified 1803 pass / 0 fail; +14 test = 9 authored [6 coverage-schema + 3 runner] + 5 auto glob-locks; coverage contract frozen [required + verdict/verification_class/status enums + run_id 1:1 + addlProps:false]; `external` both copies + conditional `fail()` writer byte-identical default; paused-reuse edge test; D10 verified vs FS; events/plugin.json untouched) | 0 ✅ |
| 1b | **(machinery, greenfield — manager SPLIT from spec's monolithic 1b)** `scripts/orchestration/`: `run_step.py` spine + `committer.py` (idempotent `transaction.replace` wrap, injectable) + `verify.py` (identity+content+freshness raw-drop gate, stable reason codes) + `coverage.py` (builds+validates+atomic-writes the 1a coverage shape) + **e2e stub harness** (5 canned raw-drop scenarios: correct/stale/wrong-project/truncated/missing + silent-skip). No skill/schema/manifest touched → NO D10. File-disjoint from 1c → parallel window. | ✅ **DONE + GREEN** (`d045da5`, manager-verified ISOLATED 46/46 in 0.47s; greenfield, 0 out-of-scope failures; verify.py gate code-reviewed; committed SCOPE-LOCKED amid same-worktree 1c contention — staged only orchestration/) | 1a ✅ |
| 1c | Intent router (one-voice UserPromptSubmit; marker lifecycle session_id/turn_id/intent_id). `intent_router.py` (Tier-1 canonical→inject `/pseo-run`+`declared` marker; Tier-2→advisory+`superseded`) + `intent-marker.schema.json` + hook cmd-swap (one voice, env_probe kept) + RUNTIME_HOOK_SCRIPTS reg + README. **turn_id router-ASSIGNED (probe-free; per-turn payload id unproven)**; marker rewritten every prompt → "current-turn only" structural. D10: draft 22→23 + marketplace 23→24. | ✅ **DONE + GREEN** (`7d712ef`, manager-verified **1872 pass / 0 fail** no-exclusions; router secure [path-guard + redacted excerpt + never-crash] + clean 2c marker contract; degraded `/pseo-init` operator hint; **DURUR→authorized→green in ONE round-trip**: 0d-pattern migration of 3 contract tests [delegation rewrite + 1 delete w/ coverage ported + parity guard follows cmd→script] all preserved/strengthened; D10 23 schema/24 json verified vs FS) | 1a ✅ |
| 1b2 | **(blast-radius migration — manager ISOLATED, after 1b proven)** relocate gsc-pull / quick-wins / content-decay master.xlsx writes from SKILL.md prose into `committer.commit`; each skill's existing tests stay green. **ORIENT (2026-06-05, partial):** 4 sheet writes, ALL currently `transaction.append` — gsc-pull→`gsc_performance` (SKILL.md ~210), quick-wins→`quick_wins`+`opportunity` (~190/197), content-decay→`content_decay` (~257). **🚧 GATING QUESTION before authoring (the committer is `transaction.replace`-only):** per-sheet replace-safety — `gsc_performance` = CONFIRMED snapshot (the known append→replace dup bug [[feedback_gsc_pull_replace_not_append]]); `quick_wins`/`opportunity`/`content_decay` = **TBD, must confirm snapshot vs accumulate** (check for a date/run column in master-excel.schema + the transforms) BEFORE any blanket replace — if any accumulates, 1b2 needs per-sheet handling or a committer append mode, NOT a blanket swap. **Also (1c lesson):** scope the test-pin migration — `test_gsc_pull.py` reads SKILL.md; check test_quick_wins/test_content_decay for write-mechanism pins. Resolve gating Q → then author. **✅ GATING RESOLVED (evidence): all 4 sheets are SNAPSHOTS (master-excel.schema — none has a date/run col) → `append` is a latent dup-on-re-run bug on ALL four → `committer.commit` (replace) is the correct fix; skill tests pin TRANSFORM+frontmatter+output_ref NOT the write (low-pin, unlike 1c); `committer.commit` wraps `transaction.replace` → excel-discipline satisfied; writer identity preserved (writer="gsc-pull" etc. passed through). Migration = swap 4 `transaction.append`→`committer.commit(run_id=handle.run_id,...)` + 1 contract-lock test. NO D10.** | 📝 **PROMPT AUTHORED** (`batch-1b2-WORKER-PROMPT.md`) | 1b ✅ |
| 1d | Reference workflow `monthly-maintenance` + `/pseo-run` + operator-remediation surface (Turkish fix-command) | pending | 1b2,1c |
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

---

## MANAGER PROTOCOL & CONTINUATION — read this if you are a FRESH manager session

You are taking over the AMO build mid-flight (the prior manager hit its context limit). Everything you
need is durable. **Onboard by reading, in order:** (1) the spec
`docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md`; (2) this whole file
(batch table + decisions D1-D10 + build model); (3) memory `project_amo_initiative.md`; (4) the existing
worker prompts `docs/superpowers/plans/amo/batch-0a..0d-WORKER-PROMPT.md` — they are your TEMPLATES.

**The per-batch loop you run:**
1. **Author** a self-contained worker prompt (copy a batch-0a..0d prompt's shape: HARD RULES — no Task/Agent,
   baseline-first `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`,
   TDD, scope-lock, no-commit; WHY; CONFIRMED facts; ORIENT; SCOPE; SPEC; TDD; METHOD; DURUR; REPORT).
   Save it as `docs/superpowers/plans/amo/batch-XX-WORKER-PROMPT.md` AND paste the fenced block to Süleyman.
2. Süleyman pastes it to a fresh **Opus-4.8 1M** worker and relays the REPORT.
3. **VERIFY (never trust blindly):** run the full suite yourself (record `passed >= baseline` + `0 failed`);
   `git status --short` (scope = ONLY the batch's files); `git diff` the risky bits (security, public
   contracts/ADRs, any out-of-scope migration). Read new security-sensitive code.
4. If the worker added a `commands/*.md` or `schemas/*.json` → **apply the count-guard bumps** (D10):
   `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` counts + `tests/schemas/test_json_schema_draft_consistency.py` assert.
5. **Green + clean → commit + push** (`git add <files>` → conventional `feat(...)/docs:` message ending
   `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` → `git push origin main`).
6. Update this file (batch → ✅ DONE) + memory. Author the next batch.

**Standing authorizations (Süleyman, 2026-06-05) — do NOT re-ask these:**
- Manager **verifies → commits → pushes** every green+verified batch without per-batch approval (Süleyman
  delegates all non-critical decisions; "EN KRİTİK: ben karar veririm, sadece kritik onay alırım").
- A worker MAY migrate out-of-scope test/guard files when a scoped change unavoidably breaks them
  ("Option 1 / best scenario") — verify the migration *preserves/strengthens* the contract, never weakens it.
- Count-guard manifest bumps are the manager's job (workers surface, manager applies).

**Accelerator strategy (Süleyman approved 2026-06-05):**
- **Bigger batches:** with 1M-context workers, merge cohesive single-concern work; split only on a hard
  dependency (a schema must freeze before its consumer) or genuinely distinct concerns. (Prior batches were
  deliberately small for ≤5%; you may size up.)
- **Parallel worker windows 🔥:** dispatch FILE-DISJOINT batches in 2-3 windows at once; verify each report
  independently. (This is the multi-window capability we're building, applied to our own build.)

**Remaining batches:** 0e + 0f (Phase 0, file-disjoint → parallel; prompts authored). Then Phases 1-4 per
spec §5/§7 (1a-1d orchestrator, 2a-2c gates+oracle, 3 replicate, 4 portfolio) + cross-cutting (e2e stub
harness, self-upgrade versioning, ACTIVE_PROJECTS_MAX consolidation). Author each from spec §7 + a template.

**Recurring gotchas (bit prior batches):**
- **D10** count-consistency immune system (above).
- A script run as a **bare CLI** may need a file-relative `sys.path` bootstrap (anchor `parents[N]`, NOT
  `CLAUDE_PLUGIN_ROOT`, to avoid an installed-plugin copy shadowing the working tree) — see dump_workspace (0c).
- A **new wired hook script** must be added to `RUNTIME_HOOK_SCRIPTS` + `scripts/hooks/README.md` or
  `test_hook_scripts_runtime_vs_ci.py` fails (env_probe 0a, audit_post_tool_use 0d set the pattern).
- Filesystem tests MUST monkeypatch `HOME` (the binding reads `~/.config/pseo/config.json`).
- Binding key = the Claude session UUID, identical from hook stdin `session_id` and command env
  `$CLAUDE_CODE_SESSION_ID` (D9, proven). Marker = `<workspace>/shared/sessions/<uuid>.json`.
