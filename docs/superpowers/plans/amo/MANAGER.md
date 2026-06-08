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
> ## 🎉 PHASE 1 COMPLETE (2026-06-05) — orchestrator shipped, suite **1890 pass / 0 fail**, pushed origin/main
> 1a ✅ (`7c8d66d` schema freeze) → 1b ✅ (`d045da5` spine) → 1c ✅ (`7d712ef` intent router) → 1b2 ✅
> (`104952e` skill-write relocation) → 1d ✅ (`3b9d87e` monthly-maintenance workflow + `/pseo-run` +
> remediation). The plan-and-verify loop RUNS end-to-end: intent → `/pseo-run monthly <slug>` → per-step
> identity+content gate → idempotent committer → coverage record → Turkish remediation on any non-pass.
> **⚠️ 1d.1 INTEGRATION FIX FIRST (manager found 2026-06-06 by reading the real transform CLIs — the e2e stub
> used canned `{step}.json` drops so it never caught this):** the driver loader reads
> `_state/transform/{run_id}/{step}.json` but `gsc_pull.py` writes `gsc_performance.json` (SHEET name, not step
> — `gsc_pull.py:392`); and the `/pseo-run` recipe's generic single `--raw` doesn't fit `content_decay.py`
> which requires `--recent`+`--previous` (`content_decay.py:397,401`). Fix = driver `output_path` keys by SHEET
> + an INTEGRATION test that runs each REAL CLI and asserts it writes where the loader reads + recipe step-3
> rewritten per-step. Then **live-acceptance** (`/pseo-run monthly <slug>` on a real GSC project) before Faz 2.
> **1d.1 ✅ DONE+GREEN (`1fa70d3`, 1891/0):** driver `output_path` keyed by SHEET (gsc_pull→gsc_performance.json)
> + an INTEGRATION test that runs the 3 REAL CLIs + drives `build_steps`'s actual loader closure (would've gone
> RED on the original bug) + recipe Section-3 rewritten per-step (content_decay `--recent`+`--previous`). Spine
> unchanged. **Faz 1 is now LIVE-READY.** **NEXT = LIVE-ACCEPTANCE (Süleyman: `/pseo-run monthly <slug>` on a
> real GSC-verified project — spec §8 gate) → then Faz 2 (2a consent ledger → 2b PreToolUse gates → 2c denetçi
> Stop-hook + correctness oracle).** Do NOT arm autonomy / start Faz 2's enforcement until the live loop is
> demonstrated once. Deferred/cross-cutting (carry into Faz 2+): self-upgrade versioning full consolidation,
> ACTIVE_PROJECTS_MAX 1-module consolidation, 0d.1 banners (cosmetic), live-acceptance run per environment.
> Codex audit (72/100) still chipped for separate triage. **Two `check_secrets` regressions (mine, via
> audit-doc + MANAGER.md quoting watched tokens) caught by worker baselines + fixed (`24b4c15`, `9b38a1f`).**
> ⚠️ **check_secrets regression caught + fixed (`24b4c15`):** my earlier audit-doc commit `8e301f7` quoted the CI secret-scanner's own grep tokens (a client-email + a hash literal — redacted here to avoid re-tripping the scanner) in a non-excluded path → `scripts/ci/check_secrets.sh` (git-greps HEAD) flagged it → `test_check_secrets_sh` went red. The 1b2 worker's baseline-first discipline surfaced it; manager redacted the literal tokens in the doc (no scanner weakening, P1-03 script untouched) → green restored. **Lesson: run the FULL suite even after a "docs-only" commit.** Codex audit (72/100) still deferred to separate triage (chipped).
>
> ⚠️ **PARALLEL-WORKTREE LESSON (2026-06-05):** 1b + 1c were run in the SAME working tree (two windows, one repo dir) → their uncommitted WIP intermixed; each worker's full-suite run saw the other's half-built state (1b worker observed failure counts wobble 2→10 live). Mitigation applied: commit SCOPE-LOCKED (stage only the batch's files). **For future parallel batches: either give each worker its own `git worktree` (spec §9 checkpoint intent) OR serialize the commits.** Also: a hook-REWRITE batch (1c) must pre-orient on tests pinning the OLD hook behavior (`test_user_prompt_submit_context_injection.py` ×6 + `test_active_project_contract.py` ×3 + `test_trigger_declaration_parity.py` ×1) and scope their migration in — my 1c prompt under-scoped this (manager-author gap). See memory `project_amo_parallel_worktree_contention.md` (1b worker).
| 0f | `transaction.py`: backup-rotation glob fix + **blocking master.xlsx lock** (`acquire_blocking` opt-in, bounded → `LockTimeout`; default fail-fast unchanged) | ✅ **DONE + GREEN** (manager-verified 1781 pass / 0 fail; +6 tests; default byte-identical/no-regression; fd-leak-safe; `LockTimeout` sibling of `LockHeldError`; rotation scoped to `master-*.xlsx` + vestigial-marker prune) | 0d |
| ~~two-session-same-project guard~~ | Deferred edge-case (per-project locks already prevent corruption; one-window-per-project discipline covers it) — fresh manager may pick up post-Phase-0 | deferred | — |
| 1a | Schema migrations: NEW `schemas/coverage.schema.json` (run_id/steps[{name,verification_class,status,observed_mcp[],input_count,scored_count}]/required_satisfied/verdict) + additive `failure_reason.external` bool (both schema copies + `fail()` writer) + confirm `paused` reuse (transition-edge test, no code). D10: draft-count 21→22 + marketplace "22→23 schemas". | ✅ **DONE + GREEN** (`7c8d66d`, manager-verified 1803 pass / 0 fail; +14 test = 9 authored [6 coverage-schema + 3 runner] + 5 auto glob-locks; coverage contract frozen [required + verdict/verification_class/status enums + run_id 1:1 + addlProps:false]; `external` both copies + conditional `fail()` writer byte-identical default; paused-reuse edge test; D10 verified vs FS; events/plugin.json untouched) | 0 ✅ |
| 1b | **(machinery, greenfield — manager SPLIT from spec's monolithic 1b)** `scripts/orchestration/`: `run_step.py` spine + `committer.py` (idempotent `transaction.replace` wrap, injectable) + `verify.py` (identity+content+freshness raw-drop gate, stable reason codes) + `coverage.py` (builds+validates+atomic-writes the 1a coverage shape) + **e2e stub harness** (5 canned raw-drop scenarios: correct/stale/wrong-project/truncated/missing + silent-skip). No skill/schema/manifest touched → NO D10. File-disjoint from 1c → parallel window. | ✅ **DONE + GREEN** (`d045da5`, manager-verified ISOLATED 46/46 in 0.47s; greenfield, 0 out-of-scope failures; verify.py gate code-reviewed; committed SCOPE-LOCKED amid same-worktree 1c contention — staged only orchestration/) | 1a ✅ |
| 1c | Intent router (one-voice UserPromptSubmit; marker lifecycle session_id/turn_id/intent_id). `intent_router.py` (Tier-1 canonical→inject `/pseo-run`+`declared` marker; Tier-2→advisory+`superseded`) + `intent-marker.schema.json` + hook cmd-swap (one voice, env_probe kept) + RUNTIME_HOOK_SCRIPTS reg + README. **turn_id router-ASSIGNED (probe-free; per-turn payload id unproven)**; marker rewritten every prompt → "current-turn only" structural. D10: draft 22→23 + marketplace 23→24. | ✅ **DONE + GREEN** (`7d712ef`, manager-verified **1872 pass / 0 fail** no-exclusions; router secure [path-guard + redacted excerpt + never-crash] + clean 2c marker contract; degraded `/pseo-init` operator hint; **DURUR→authorized→green in ONE round-trip**: 0d-pattern migration of 3 contract tests [delegation rewrite + 1 delete w/ coverage ported + parity guard follows cmd→script] all preserved/strengthened; D10 23 schema/24 json verified vs FS) | 1a ✅ |
| 1b2 | **(blast-radius migration — manager ISOLATED, after 1b proven)** relocate gsc-pull / quick-wins / content-decay master.xlsx writes from SKILL.md prose into `committer.commit`; each skill's existing tests stay green. **ORIENT (2026-06-05, partial):** 4 sheet writes, ALL currently `transaction.append` — gsc-pull→`gsc_performance` (SKILL.md ~210), quick-wins→`quick_wins`+`opportunity` (~190/197), content-decay→`content_decay` (~257). **🚧 GATING QUESTION before authoring (the committer is `transaction.replace`-only):** per-sheet replace-safety — `gsc_performance` = CONFIRMED snapshot (the known append→replace dup bug [[feedback_gsc_pull_replace_not_append]]); `quick_wins`/`opportunity`/`content_decay` = **TBD, must confirm snapshot vs accumulate** (check for a date/run column in master-excel.schema + the transforms) BEFORE any blanket replace — if any accumulates, 1b2 needs per-sheet handling or a committer append mode, NOT a blanket swap. **Also (1c lesson):** scope the test-pin migration — `test_gsc_pull.py` reads SKILL.md; check test_quick_wins/test_content_decay for write-mechanism pins. Resolve gating Q → then author. **✅ GATING RESOLVED (evidence): all 4 sheets are SNAPSHOTS (master-excel.schema — none has a date/run col) → `append` is a latent dup-on-re-run bug on ALL four → `committer.commit` (replace) is the correct fix; skill tests pin TRANSFORM+frontmatter+output_ref NOT the write (low-pin, unlike 1c); `committer.commit` wraps `transaction.replace` → excel-discipline satisfied; writer identity preserved (writer="gsc-pull" etc. passed through). Migration = swap 4 `transaction.append`→`committer.commit(run_id=handle.run_id,...)` + 1 contract-lock test. NO D10.** | ✅ **DONE + GREEN** (`104952e`, manager-verified **1875 pass / 0 fail**; surgical Step-7-only diff, writer preserved + run_id added, dup bug fixed on all 4 snapshot sheets, existing skill tests green, +3 contract params + manager DURUR-truthfulness sweep) | 1b ✅ |
| 1d | Reference workflow `monthly-maintenance` + `/pseo-run` + operator-remediation surface (Turkish fix-command). **DESIGN RESOLVED (manager orient 2026-06-05): transform IMPEDANCE — skill transforms take rich payloads (`gsc_pull.transform(raw:dict,*,enriched)`), NOT rows→rows. Resolution: the model runs the existing transform CLI (→ `_state/transform/{run_id}/`); `run_step`'s `transform` = a LOADER of that model-produced output; `verify_raw_drop` gates the provenance-stamped raw MCP drop (`_state/inbox/{run_id}/`) → input_count; committer writes the output → scored_count → silent-skip gate intact. NO run_step change. monthly-report = `model_attested` (reads sheets+events → renders report, `master.xlsx#none`, no commit). Steps: gsc-pull(gsc_performance)→quick-wins(quick_wins+opportunity)+content-decay(content_decay)→monthly-report(attested). D10: +1 command (pseo-run) 19→20.** | ✅ **DONE + GREEN** (`3b9d87e`, manager-verified **1890 pass / 0 fail**; loader-transform [NO spine change], model_attested report + driver-level workflow-completion guard, Turkish remediation surface, `/pseo-run` passes all 5 command guards, D10 20 commands verified vs FS; run_step/coverage/verify/committer UNCHANGED) | 1b2 ✅,1c ✅ |
| 2a | **Consent ledger SUBSTRATE (no hooks):** NEW `schemas/consent.schema.json` (append-only hash-chained ENTRY: seq/run_id/action[6-enum]/target_hash/prev_hash/entry_hash) + `scripts/state/consent_ledger.py` (append/read/`verify_chain`/`has_consent` + CLI; mirrors events_writer O_APPEND+flock, NEVER os.replace) + `/pseo-approve` command (O3 non-coder UX) + tests. D10: +1 schema +1 command (worker reconciles, manager re-verifies). | ✅ **DONE + GREEN** (`de44bbd`, manager-verified **1934 pass / 0 fail**; 2a-scoped 59/0; hash-chain+O_APPEND reviewed [NO os.replace]; tamper→(False,1)+has_consent fail-closed; D10 reconciled to FS 21cmd/24schema/25json; scope-locked amid 2c contention) | 1 ✅ |
| 2b | **Outward-action PreToolUse consent gate (WAVE-2 core):** NEW `outward_action_gate.py` + 2nd pre-tool-use block (matcher `Bash\|mcp__gsc__submit_sitemap`) — classify git_push/fs_delete/net_post/mcp_submit/index_update, default-DENY (`exit 2`) unless `has_session_consent(session_id,action,target_hash)` (**D13 per-session**, NEW additive helper in consent_ledger). Deny-message echoes the exact `/pseo-approve … "{target}"` copy-paste (no operator guessing). Conservative classify (non-gated Bash NEVER bricks), fail-CLOSED on gated path, READ-ONLY. dfs_oversized deferred → 2f. | ✅ **DONE + GREEN** (`dafec71`, manager-verified **1995/0**; scoped 269/0; gate READ-ONLY + fail-closed-gated + per-session match [session_id+action+target_hash] + target-hash writer/gate parity + leading-token guard reviewed; pre-tool-use block-0 INTACT + block-1 added; consent_ledger +32/−0 additive; classified RUNTIME+README; no D10. ⚠️ **KNOWN GAP→2f:** `has_session_consent` RAISE on a corrupt ledger fail-opens the gated path; compound-cmd `&&`/`git -C` not caught) | 2a ✅ |
| 2e | **AI-disclosure PostToolUse surface-rescan** (SPLIT from spec-2b): block-and-revert any `outputs/blog/**/*.html` write whose rendered SURFACE carries an AI-disclosure signal — catches the Bash/heredoc bypass of the Write-only `content_validator` (Süleyman hard-constraint #2, [[feedback_ai_disclosure_ban]]). | **AUTHORED + DISPATCHED** (`batch-2e-WORKER-PROMPT.md`): PostToolUse twin of validate_content_write — REUSES content_validator + is_content_html_path; on a RED finding in a JUST-written blog HTML, **quarantine-renames** off the live `.html` (block-and-revert, no pre-state snapshot needed) + emits a block-decision; candidate = Write file_path / Bash `.html` tokens, EXISTS + recency-guard (a `cat` READ never triggers); non-blocking-on-error; no D10 | ✅ **DONE + GREEN** (`f2cd64d`, manager-verified **2025/0**; scoped+siblings 47/0): REUSES content_validator + is_content_html_path (no detection drift); quarantine `os.replace`→`.BLOCKED-ai-disclosure` fires ONLY on blog-HTML path + EXISTS + mtime<60s + RED finding → **no new false-positive surface** beyond the trusted Write-gate; recency-guard proven (a `cat` READ never quarantines); block-decision stdout JSON; audit+env_probe byte-intact; classified RUNTIME+README; no D10. Path-A limits→2f | 2a ✅ |
| 2f | **Outward-gate completeness (Faz-2 FINAL; manager TIGHTENED to the 2 real 2b QA gaps):** (a) gated path fail-CLOSED when `has_session_consent` RAISES (corrupt ledger → deny + alert; main's except no longer fail-opens a gated action) + (b) compound-command segment-split + git-global-flag subcommand detection (`cd x && git push` / `git -C /p push` / `ls && curl POST`); single-command results byte-identical. One file (outward_action_gate.py + test); no wiring/D10. **Deferred:** `dfs_oversized`→**Faz 4** (cost/quota ledger); drift-F-rule [§4 mastery lint] + secret-bytes-scan→**Faz 3**; 2e `os.replace`-fail + shell-var blog-path = accepted (too narrow). | ✅ **DONE + GREEN** (`6760314`, manager-verified **2036/0**; gate tests 35/0 [24 orig + 11 new]; diff reviewed line-by-line = exactly the 2 fixes; (a) consent-check RAISE→deny+alert [main except untouched → gated fully fail-closed, non-gated still fail-open] + (b) segment-split + `_git_push_target` git-flag detection, single-command byte-identical, over-split = false-deny-never-false-allow; scope 2 files; no D10) | 2b ✅, 2e ✅ |
| 2c | **Denetçi Stop-hook** (manager SPLIT 2c→2c+2d, precedent 1b→1b+1b2): NEW `scripts/hooks/denetci.py` wired into `stop.json` (stop_validation STAYS first) — reads 1c intent marker + 1a coverage; declared+no-fresh-run→block, incomplete/failed→block+`remediation.render`, `paused`(external)→allow+RED flag, pass/none-owed→allow; `stop_hook_active` cap guard; freshness = coverage-mtime ≥ marker-mtime; READ-ONLY + non-crashing. No schema/command → no D10. | ✅ **DONE + GREEN** (`e50d655`, manager-verified **1934/0** [excl 2d mid-flight RED file]; 2c-scoped 33/0; denetci reviewed non-crashing + READ-ONLY [only stderr.write] + stdout-only block + stop_hook_active cap; stop_validation STAYS first; no schema/command → no D10; scope-locked amid 2d contention) | 1 ✅ |
| 2d | **Correctness oracle** (split from 2c): `scripts/reporting/orchestration_metrics.py` — reconcile master.xlsx rows vs raw-provenance per run_id, INDEPENDENT of the self-reported verdict → the trustworthy ≤5% structured-error number + first-pass/retry/coverage-miss metrics (spec G5). Reconciles committed-rows vs the **transform OUTPUT** (so filtering steps like quick_wins don't false-flag), via openpyxl + master-excel.schema `data_start_row`; reuses `monthly_maintenance.{STEPS,inbox_path,output_path}`; headline = `fake_green` (verdict==pass but workbook mismatch). File-disjoint from 2a+2c. | ✅ **DONE + GREEN** (`7234ccf`, manager-verified **1967/0**; 2d-scoped 33/0; READ-ONLY [grep: zero state-writes]; reconcile-vs-OUTPUT [quick_wins filtering safe, raw→committed drop only advisory] + fake_green [verdict==pass∧independent-mismatch] + workbook_absent-never-silently-passed reviewed; reuses STEPS/inbox/output/coverage/silent_skip; no schema/command→no D10) | 1 ✅ |
| **3a** | **§4 mastery lint #1 — static `body ⊆ declared` MCP** (manager SCOPED Faz-3 §4 pair → SPLIT static/runtime, D14): NEW `scripts/validation/skill_mcp_usage.py` (invocation-PRECISE detector — qualified `mcp__s__t(` call + native `call_tool("literal")` + `SfMcpClient.load_crawl` wrapper; prose mentions + variable `call_tool(var)` NOT flagged) + per-skill lint `tests/schemas/test_skill_body_mcp_subset_declared.py` (45 cases) + 16 parser unit tests + **registry fix `sf__sf_load_crawl`** (was invoked via `SfMcpClient.load_crawl` but absent from registry — the canonical undeclared-dep bug) + 4 skills declare their SF live-crawl tools (on-page-audit/schema-audit/tech-audit/internal-links, append-only `optional`). Closes the triangle **used ⊆ declared ⊆ registry**. | ✅ **DONE + GREEN** (`c497444`, manager-verified **2098/0** [+61: 16 unit + 45 lint] via INDEPENDENT re-derivation [45-skill gap set clean; both precision traps re-proven: monthly-report backtick-mention + sf-crawl-orchestrator var-dispatch NOT flagged; declared⊆registry still green]; module pure + NO skill-allowlist suppression; scope-locked 8 files append-only [19 ins / 0 del]; no D10; no new RUNTIME_HOOK_SCRIPTS) | 1✅,2✅ |
| 3b | **Replicate `audit-suite`** (Süleyman's pick 2026-06-08 — FIRST replicate, serial): NEW `scripts/orchestration/workflows/audit_suite.py` (4 steps tech_audit→schema_audit→on_page_audit→cannibalization) reusing the FROZEN 1b spine; **explicit per-step `output_file`** (1d.1 fix: schema_audit CLI writes `schema_audit.json` but sheet is `schema`); relocate 4 skills' SKILL.md `transaction.append`→`committer.commit` (1b2, snapshot→replace, writer preserved); extend `/pseo-run` with the `audit` branch (monthly byte-unchanged); the MODEL makes MCP calls + drops provenance, code gates (Phase-1 seam) | ✅ **DONE + GREEN** (`64fdb7d`, manager-verified **2118/0** [+20: driver e2e + 1d.1 CLI integration]; spine UNTOUCHED [git-confirmed]; **D15 attested-path** for the 3 aggregating steps preserves identity+content+freshness [proven by test_wrong_run_id/stale/truncated_is_failed] + advisory silent-skip; completion-guard pass→incomplete unless all-4-satisfied; monthly recipe byte-unchanged; scope-locked 8 files; no D10) | 3a |
| 3c | **Replicate `setup`** (new-project content-planning pipeline: topical-map → cluster-map → new-content-plan): mirror audit_suite, **IMPORT its D15 `_run_one` dispatch** (no 3rd copy); all 3 steps model_attested (aggregate); **sequential-dependent** (cluster⊇topical, content-plan⊇cluster) satisfied by ordering + model-threaded CLI args (`--cluster-defs-json`/`--cluster-map`), no CLI/spine edit; 3 skills append→committer.commit (1b2) | ✅ **DONE + GREEN** (`b239ac9`, manager-verified **2155/0** [+21: e2e + 3-CLI dependency-chain integration]; spine + sibling drivers UNTOUCHED; completion-guard load-bearing [first ALL-attested workflow]; **new_content_plan snapshot judgment VERIFIED** [has `created_date`+`lifecycle_status` but is idempotent-regenerate: master_task_sync only READS it, lifecycle set fresh GREEN, id re-numbered 1..N → replace correct, not data-loss]; monthly+audit byte-unchanged; no D10) | 3a |
| 3d | **Replicate `content`** (blog-content pipeline: new-blog → generate-images → faq-optimization) — the structurally-NOVEL **artifact-driver**: produces a blog HTML artifact (NOT sheet rows), so NO transform CLI / raw drop / committer / 1b2-relocation. Per-step verify = artifact EXISTS + (HTML) `content_validator.validate_content(html).has_red` is False (the AI-disclosure gate, SAME detector as 2e). All model_attested (content quality not code-checkable, spec §11); completion-guard load-bearing | ✅ **DONE + GREEN** (`5a5b745`, manager-verified **2175/0** [+20]; artifact-driver reuses ONLY coverage+remediation+content_validator [no committer/run_step]; **AI-disclosure RED article → step failed → verdict failed** [test-proven, workflow-level + write-time agree by construction]; spine + sibling drivers + ALL skills UNTOUCHED [no relocation]; monthly/audit/setup byte-unchanged; post-agnostic + headless-images-safe; no D10; worker caught a prompt API error [`.has_red`/`.verdict` are properties]) | 3a |

> ## 🎉 FAZ 3 REPLICATION LINE COMPLETE (2026-06-08) — all 3 named workflows replicated, suite 2036→2175
> The orchestrator now drives **4 workflows**: `monthly` (Faz 1) + `audit` (3b) + `setup` (3c) + `content` (3d).
> **TWO driver SHAPES emerged** (a clean architectural result): (1) the **data-driver** (monthly/audit/setup) —
> raw MCP drop → transform CLI → `verify_raw_drop` → `committer` → master.xlsx rows; shares `_run_one`/D15
> dispatch (audit+setup import it). (2) the **artifact-driver** (content) — model emits a blog HTML artifact →
> verify artifact-exists + the `content_validator` AI-disclosure gate; shares ONLY the `coverage`/`derive_verdict`/
> completion-guard layer, NOT `_run_one`. Both honest per spec §11: structured ingestion = code_verified; analysis
> + content = model_attested with deterministic gates (oracle reconcile / AI-disclosure). **This VINDICATES Path A**
> (2 hard-coded shapes, NOT one universal declarative engine) and refines O4 (below). Faz-3 remaining: 3-gov-secrets
> · 3-gov-lint2 (needs correlation design) · 3-O4 light-promote (extract the shared DATA-driver for monthly/audit/
> setup; content stays a separate artifact-driver).
| 3-oracle | **TRACKED FOLLOW-UP (manager-QA from 3b):** the 2d correctness oracle (`orchestration_metrics.py`) is MONTHLY-specific (reuses `monthly_maintenance.{STEPS,inbox_path,output_path}`). Audit-suite's 3 `model_attested` steps make the silent-skip count ADVISORY → their independent ≤5% backstop is the ORACLE, but it doesn't yet cover `audit`. Generalize the oracle to reconcile any workflow's committed-vs-raw (audit + future 3c/3d) so attested steps are independently verified. NOT a defect — a real coverage gap surfaced by verification, never silently dropped. | ✅ **DONE + GREEN** (`9ee9346`, manager-verified **2127/0** [+9]; READ-ONLY preserved [grep: 0 write primitives]; **R1-R5 reconcile math byte-unchanged**; spine + coverage-schema + both workflow modules UNTOUCHED [step-name resolver, NOT a coverage field — "derive don't store"]; backstop FIRES on an attested fake_green [test-proven]; `_step_output_file` handles schema_audit.json≠schema; new `unresolved_workflow` verdict surfaced+excluded-from-rate; mixed monthly+audit oracle_report; 1 documented test migration [skips→reconciles attested] + 1 accepted non-weakening 2nd-test `steps=` back-compat touch. Known limitation: partial/resumed runs → `unresolved_workflow` [visible, not a backstop gap — a fake_green needs all-steps-satisfied]) | 3b |
| 3-gov-driftF | **drift-F-rule = F-27** (`csr_mcp`, HIGH): every declared OUTWARD MCP tool ⊆ a 2b gate matcher — FAILs if a skill declares an outward MCP tool the `outward_action_gate` doesn't cover (consent-wall drift). Mirrors F-24 sets-comparison; imports the gate constant (no drift) + reuses 3a `skill_mcp_usage`; curated-outward FAIL-HIGH + outward-verb/read-exclusion AMBER tripwire. (manager SPLIT 3-gov → driftF / secret-bytes / lint#2, distinct subsystems) | ✅ **DONE + GREEN** (`80bc897`, manager-verified **2134/0** [+7 F-27 tests + count cascade]; check_F_27 logic reviewed [engine-governance, gate IMPORTED, zero false-positives PASS-on-real-tree]; 4-way registration sync-green; **worker caught+fixed a REAL regression** [new top-level `from scripts...` imports broke the standalone-loaded `check_excel_writer.py` → RED workbook slipped through → `sys.path` bootstrap fix, gate blocks RED again]; **manager applied the count cascade** [impl 24→25, declared 31→32, HIGH 13→14 across 6 files + drift-check SKILL.md F-27 row/section]) | 3a |
| 3-gov-secrets | secret-bytes scan: `--scan-stdin` literal-pending-bytes mode for `scripts/security/check_secrets.sh` (gitignore-unaware; gitignored `.env` stays WARN-only) | ✅ **DONE + GREEN** (`089ebfa`, manager-verified **2180/0**; scoped 16/16 + INDEPENDENT re-derivation of all 4 verdicts [FAIL/GREEN/WARN/FAIL] + redaction; default + `--changed-since` byte-unchanged [`--scan-stdin` parsed first]; trap-cleaned mktemp buffer; +5 TDD tests all runtime-constructed [no committed watched token]; structural 2-6 skipped; no D10, no hook) | — |
| 3-gov-lint2 | §4 mastery lint #2 — **manager REFUTED spec's runtime Option B** (events.jsonl `source.mcp_tool` populated in ~3 of 3000+ events, inconsistently formatted, orchestrator never writes it → runtime `observed⊆declared` is vacuous/false-RED). **Süleyman approved B′ (static):** every workflow `STEPS[].tool` ⊆ owning-skill declared mcp_tools ⊆ registry. Reuses 3a `skill_mcp_usage.declared_tools`; NEW `scripts/validation/workflow_tool_declared.py` + test; glob-discovers workflows (future-proof); GREEN today (8 tool-bearing steps pre-verified). No D10. | ✅ **DONE + GREEN** (`67cb1b6` prompt + `6b6c650` feat, manager-verified **2194/0**, +14 test [UNIT+DISCOVERY+8 MAIN+TEETH]; **INDEPENDENT re-derivation** [own logic, NOT the worker's module] == `{}` and agrees; teeth proven on a synthetic gap [both predicates fire]; module pure/DRY [`_step_reasons` helper]; `removeprefix("mcp__")` 5-char strip locked; glob-discovery [no hardcoded list → future workflow auto-covered]; content/2-None steps skipped; scope-locked 2 files; no D10, no hook) | 3a |
| 3-O4 | promote-to-declarative DECISION GATE (spec O4): define the concrete trigger that flips Path A → declarative engine + auto-graph; default = stay Path A. **⚠️ Signal now STRONG:** 3 workflows (monthly/audit/setup) share the driver pattern — audit+setup already share `_run_one`/`_run_attested_step` via cross-driver IMPORT (3c O4 note). The earned move is a **LIGHT promote**: extract the shared dispatch (`_run_one` + `_run_attested_step` + build_steps/inbox/output/loader + the CLI boilerplate) into a shared `workflow_driver` module that monthly/audit/setup all use — NOT the full declarative engine + auto-graph. **REFINED by 3d (the 4th workflow, content, IS structurally different — an artifact-driver):** the answer is NOT one universal engine but TWO shapes — a shared **data-driver** (monthly/audit/setup; extract `_run_one`/`_run_attested_step`/build_steps/inbox/output/loader/CLI) **+** content's separate **artifact-driver** (shares only `coverage`). So the LIGHT promote = extract the data-driver only; content stays parallel. The full declarative engine + auto-graph stays DEFERRED — Path A vindicated (the divergent shapes prove a single graph would over-abstract). | ✅ **DONE + GREEN** (`92b3888` prompt + `8631ff3` feat, manager-verified **2194/0** EXTRA-HARD): NEW `scripts/orchestration/workflow_driver.py` holds the shared DATA-driver (`inbox_path`/`output_path`/`_output_loader`/`_resolve_site_url`/`build_steps`/`_run_attested_step`/`_run_one`/`run_workflow`); monthly/audit/setup shrink to STEPS + thin delegating wrappers (−504 lines); content stays separate artifact-driver; spine composed not edited; **setup→audit `_run_one` cross-import RETIRED**. Public API preserved (re-export wrappers) → **ZERO test changes**; monthly `output_path` SHEET-keyed bridge, audit/setup OUTPUT_FILE-keyed; monthly STEPS gained `output_file`+`verification_class` (value-preserving). **DEFINITIVE old↔new equivalence proof (git-stash):** computed StepSpec behaviour BYTE-IDENTICAL, STEPS additions value-preserving, audit/setup STEPS unchanged. no D10. | 3b-3d ✅ |
| 4 | Portfolio fan-out + cost/quota ledger + kill-switch + `/pseo-status --portfolio` + recovery runbook; scheduler default OFF | pending | 0-3 |

> ## 🚦 FAZ 2 STARTED (2026-06-06) — fresh Faz-2 manager took over via FRESH-MANAGER-BOOTSTRAP §9
> Fresh manager onboarded zero-loss; independently re-verified baseline **1891 pass / 8 skip / 0 fail** (HEAD
> `9b5d238`) + confirmed every Faz-1 deliverable on disk. **Operator decision (Süleyman 2026-06-06, in memory
> `project_amo_live_acceptance_deferred`): the spec §8 live-acceptance gate is DEFERRED to the END — build all
> of Faz 2+3+4, then ONE comprehensive all-phases live run.** Overrides the "live-test before Faz 2" soft gate;
> the HARD gate (Faz-4 autonomy must not arm un-proven) is met by that end run. So we build Faz 2 NOW.
> **Manager SPLIT spec-2c → 2c (denetçi Stop-hook) + 2d (correctness oracle)** — no shared code, smaller
> reviewable batches in the hard safety phase, MORE parallel. **Disjointness proven** (`test_count_consistency`
> guards skills/commands/MCP/schemas, NOT hooks; the 6 "hooks" are JSON files; 2c extends existing `stop.json`
> + adds a hook SCRIPT, 2d is a reporting script → neither trips 2a's manifests): **2a ∥ 2c ∥ 2d are all
> file-disjoint → up to 3 parallel windows.** Plan: **WAVE-1 = 2a (consent substrate) [✅ DONE `de44bbd`] ∥ 2c (denetçi) [✅ DONE `e50d655`] + 2d (oracle) [✅ DONE `7234ccf`] → **WAVE-1 COMPLETE** (1967/0); WAVE-2 = 2b NEXT (PreToolUse gates, needs 2a's ledger +
> shares RUNTIME_HOOK_SCRIPTS with 2c).** Key reuse seams found: `remediation.render` + `failure_reason.external
> →paused` already built (1a/1d) so the denetçi just calls them; `events_writer._atomic_append_allocating_run_id`
> is the exact O_APPEND+flock hash-chain pattern for the consent recorder (NEVER os.replace — it's a LOG, not a
> marker); the denetçi correlates run-to-intent by **file mtime** (coverage ≥ marker) — no 1d edit, tz-free,
> rejects a stale prior pass. Worker prompts: `batch-2a-WORKER-PROMPT.md`, `batch-2c-WORKER-PROMPT.md`.

> ## 🎉 FAZ 2 COMPLETE (2026-06-06) — gates + denetçi + oracle SHIPPED, suite **2036/0**, 6 batches pushed
> The safety + enforcement layer is done: **2a** consent ledger (append-only hash-chained + `/pseo-approve`,
> `de44bbd`) · **2c** denetçi Stop-hook (forces a skipped owed workflow; `e50d655`) · **2d** correctness oracle
> (independent ≤5% / fake_green; `7234ccf`) · **2b** outward-action consent gate (per-session deny of
> push/rm/POST/sitemap/indexing; `dafec71`) · **2e** AI-disclosure PostToolUse surface-rescan (quarantines the
> Bash/heredoc bypass; `f2cd64d`) · **2f** gate completeness (fail-closed consent + compound-command split;
> `6760314`). All scope-locked + pushed origin/main. Suite 1891→**2036** (+145 tests across Faz 2), 0 fail.
> **Both Süleyman hard-constraints enforced in code:** Indexing-submit needs per-session consent (2b);
> "written by AI" can't reach visible HTML even via Bash (2e). **Live-acceptance stays deferred to the END**
> (D11) — after Faz 3 + Faz 4, one comprehensive all-phases run. **NEXT = Faz 3** (replicate the orchestrator
> to new-project / content-pipeline / audit-suite + the two §4 mastery lints [body⊆declared MCP, observed⊆declared]
> + `sf_load_crawl` registry fix; carries the deferred drift-F-rule + secret-bytes-scan) then Faz 4 (portfolio
> fan-out + cost/quota ledger [carries `dfs_oversized`] + kill-switch + scheduler-OFF).

> ## 🟢 FAZ 3 STARTED (2026-06-08) — fresh Faz-3 manager took over via FRESH-MANAGER-BOOTSTRAP §9
> Fresh manager onboarded zero-loss; independently re-verified baseline **2036→2098** path (HEAD was `c5123d8`,
> suite **2036 pass / 8 skip / 0 fail** on my run; the worker measured 2037/7 — one MCP-availability-gated test
> flips pass/skip, total 2044 stable, NOT a regression). **Süleyman decisions (2026-06-08): (1) replicate
> `audit-suite` FIRST; (2) SERIAL cadence (3a → audit-suite, one worker window).** Manager SCOPED Faz 3 into
> 3a (static lint #1) → 3b audit-suite → 3c/3d (new-project-setup + content-pipeline) → 3-gov (lint #2 +
> drift-F-rule + secret-bytes) → 3-O4 decision gate. **D14: SPLIT the §4 lint pair** — lint #1 (STATIC SKILL.md
> text analysis) and lint #2 (RUNTIME events.jsonl reconciliation) are distinct data domains → separate batches
> for clean reviews; lint #1 alone is a full, grounded, single-concern batch.
> **3a ✅ DONE + pushed** (`e99b456` docs prompt + `c497444` feat, manager-verified **2098/0**, +61 tests
> [16 unit + 45 per-skill lint]): the static `body ⊆ declared` MCP lint closes the triangle
> **used ⊆ declared ⊆ registry**. Detector is invocation-PRECISE (3 matchers: qualified `mcp__s__t(`, native
> `call_tool("literal")`, `SfMcpClient.load_crawl` wrapper) — prose mentions + variable `call_tool(var)` are NOT
> flagged (both precision traps re-proven). Grounded RED proof = exactly 4 SF-opt-in skills
> (on-page-audit/schema-audit/tech-audit/internal-links) each `{sf__sf_list_crawls, sf__sf_load_crawl}`; fix =
> registry `sf__sf_load_crawl` + 4 skills declare their SF tools (append-only `optional`). Manager QA: INDEPENDENT
> re-derivation (own detector, not the worker's module) → 45-skill gap set `{}`; scope-locked 8 files; no D10.
> **3b ✅ DONE + pushed** (`fcacfb6` docs + `64fdb7d` feat, manager-verified **2118/0**, +20 tests): audit-suite
> replicated — NEW `audit_suite.py` (4 steps) mirrors monthly on the FROZEN spine; **1d.1 trap caught
> pre-authoring** (schema_audit CLI writes `schema_audit.json` ≠ sheet `schema`) → explicit per-step `output_file`
> + a CLI-integration drift-lock test; **D15 attested-path** resolves the silent-skip/analysis-cardinality seam
> (3 of 4 audit steps aggregate → model_attested, hard gates preserved, count advisory) + completion-guard;
> 4 skills' writes relocated append→committer.commit (1b2); `/pseo-run` gains the `audit` branch (monthly
> byte-unchanged). **Manager-QA finding → 3-oracle:** the 2d oracle is monthly-specific; audit's attested steps
> need it generalized for their independent backstop (tracked, not dropped). Süleyman: **max-effort 1M workers →
> size batches up**.
> **3-oracle ✅ DONE + pushed** (`e197d34` docs + `9ee9346` feat, manager-verified **2127/0**, +9 tests): the
> correctness oracle is now workflow-AGNOSTIC — resolves each run's workflow by its disjoint step-names (spine +
> coverage schema FROZEN, no field added), keys the transform output by `output_file` (1d.1 schema_audit case),
> and reconciles attested sheet-writers (dropped the code_verified-only filter) so audit's 3 attested steps now
> have their independent ≤5% backstop (a fake_green on an attested step is now CAUGHT — test-proven). R1-R5 math
> byte-unchanged; READ-ONLY preserved; new `unresolved_workflow` verdict (visible, excluded from the rate).
> **3-gov-driftF ✅ DONE + pushed** (`9c40e2e` docs + `80bc897` feat, manager-verified **2134/0**): F-27
> drift rule (declared outward MCP tool ⊆ 2b gate) shipped — engine-governance, gate-imported (no drift),
> zero false-positives. **D16: two manager-author lessons** (below). Manager applied the invariant-count
> cascade (24→25/31→32/HIGH13→14). **Manager SPLIT 3-gov → driftF (✅) / secret-bytes / lint#2** (3 distinct
> subsystems; lint#2 needs a correlation design — events MCP rows lack the workflow_run_id). **NEXT (Süleyman's
> call): 3-gov-secrets (secret-bytes scan) · 3-gov-lint2 (needs correlation design) · 3c/3d (new-project-setup +
> content-pipeline replicate, D15 reuse).**
> **3c ✅ DONE + pushed** (`170b03e` docs + `b239ac9` feat, manager-verified **2155/0**, +21 tests): the `setup`
> workflow (new-project content-planning: topical→cluster→content-plan) is the 3rd orchestrated workflow.
> Mirrors audit_suite + IMPORTS its D15 dispatch; first ALL-attested workflow (completion-guard load-bearing);
> sequential dependency satisfied by ordering + model-threaded CLI args; 3 skills relocated to committer.commit;
> monthly+audit byte-unchanged. **Manager-verified the new_content_plan replace-vs-append judgment** (has a
> created_date col but is idempotent-regenerate → replace correct, not data-loss). **⚠️ O4 signal now STRONG:**
> audit+setup share `_run_one` via import → the earned move is a LIGHT promote (extract a shared `workflow_driver`),
> NOT the full graph (see 3-O4). **NEXT (Süleyman's call): 3d content-pipeline (hardest) · 3-gov-secrets ·
> 3-gov-lint2 (needs correlation design) · 3-O4 light-promote (extract shared driver — recommend after 3d).**
> **3d ✅ DONE + pushed** (`403c706` docs + `5a5b745` feat, manager-verified **2175/0**, +20): the `content`
> workflow (blog pipeline) shipped as the structurally-NOVEL **artifact-driver** — verify artifact-exists + the
> `content_validator` AI-disclosure gate (RED article → step failed, test-proven), all model_attested, reuses ONLY
> coverage+remediation+content_validator (no committer/run_step), no 1b2 relocation, monthly/audit/setup
> byte-unchanged. 🎉 **FAZ-3 REPLICATION LINE COMPLETE** (4 workflows: monthly/audit/setup/content; suite
> 2036→2175). **Two driver SHAPES** (data-driver + artifact-driver) → vindicates Path A + refines O4 (see the
> banner above + the 3-O4 row). **NEXT (Süleyman's call): 3-gov-secrets (secret-bytes) · 3-gov-lint2 (needs
> correlation design) · 3-O4 light-promote (extract the shared data-driver for monthly/audit/setup).**

> ## 🟢 FAZ-3 REMAINDER STARTED (2026-06-08) — fresh manager took over via FRESH-MANAGER-BOOTSTRAP §9
> Fresh manager onboarded zero-loss; independently re-verified baseline **2175 pass / 7 skip / 0 fail**
> (HEAD `05d1a52`, clean, all pushed). **Süleyman locked order (2026-06-08): 3-gov-secrets → 3-gov-lint2
> (B′) → 3-O4 (before Faz 4) → Faz 4 — "go with your recommendations, best scenario."**
> **3-gov-secrets ✅ DONE + pushed** (`d0048ba` prompt + `089ebfa` feat, manager-verified **2180/0**): the
> `--scan-stdin` literal-pending-bytes mode closes the incremental fast-path gitignored-target gap; the
> gitignored-`.env` WARN carve-out preserved; default/`--changed-since` byte-unchanged; +5 runtime-built
> TDD fixtures (no committed token). Manager did INDEPENDENT re-derivation of all 4 verdicts + redaction,
> not just trust the diff. Secrets worker ran in the SHARED working tree (parallel-worktree pattern) →
> manager committed SCOPE-LOCKED (only the 2 batch files; the lint2 prompt landed separately).
> **3-gov-lint2 → B′ (manager premise-revision):** verifying the real data BEFORE authoring refuted the
> spec's runtime Option B — `source.mcp_tool` is in ~3 of 3000+ events, inconsistently formatted, and the
> orchestrator never writes it (it stamps inbox raw-drops + coverage, not events). So runtime
> `observed⊆declared` has no data foundation. Presented A / B′ / defer with evidence → Süleyman chose **B′
> (static `workflow-tool ⊆ skill-declared ⊆ registry`)** — deterministic, self-contained, GREEN today,
> catches future drift; extends 3a's triangle up to the orchestrator. Prompt authored + pushed (`67cb1b6`),
> all 8 tool-bearing steps pre-verified green (the `mcp__` 5-char-strip trap noted).
> **3-gov-lint2 (B′) ✅ DONE + pushed** (`6b6c650` feat, manager-verified **2194/0**, +14 test): static
> `workflow STEPS[].tool ⊆ owning-skill declared ⊆ registry`. Manager did INDEPENDENT re-derivation (own
> glob+normalize+declared/registry logic, NOT the worker's module) → gap set `{}` and AGREES with the
> module; teeth proven (synthetic gap trips both predicates, via my logic AND the worker's `_step_reasons`).
> Module glob-discovers workflows (a future workflow auto-covered); `removeprefix("mcp__")` 5-char strip
> locked by a unit test. content_pipeline (artifact-driver) + the 2 tool=None steps correctly skipped.
> **🎯 Faz-3 governance line COMPLETE** (secrets + lint2 both shipped).
> **3-O4 light-promote ✅ DONE + pushed** (`8631ff3` feat, manager-verified **2194/0** EXTRA-HARD): extracted
> the shared DATA-driver into `scripts/orchestration/workflow_driver.py`; monthly/audit/setup now thin
> (−504 lines); content stays a separate artifact-driver; spine composed not edited; setup→audit `_run_one`
> cross-import retired; ZERO test changes (public API preserved by re-export wrappers). Manager ran a
> **DEFINITIVE old↔new equivalence proof via git-stash** (computed StepSpec behaviour byte-identical;
> monthly's STEPS key-additions value-preserving; audit/setup STEPS unchanged) — the right way to verify a
> refactor of shipped code, beyond "tests pass."
>
> ## 🎉 FAZ 3 COMPLETE (2026-06-08) — replication line + governance + O4, suite 2036→2194 (+158 test)
> The orchestrator drives **4 workflows** (monthly/audit/setup/content, TWO driver shapes) + the §4 mastery
> lints (3a body⊆declared + lint2 workflow-tool⊆declared) + the F-27 drift rule + the generalized oracle +
> the secret-bytes scan + the O4 shared-driver consolidation. **Path A vindicated.** All scope-locked +
> pushed origin/main. **NEXT = FAZ 4** (the final phase): `/pseo-run-portfolio` cross-project fan-out
> (disjoint per-project locks) + a portfolio cost/quota ledger under `shared/` (atomic reserve-then-confirm;
> GSC quota + DFS credits [carries `dfs_oversized` from 2b] + image spend) + a hard global ceiling +
> kill-switch (ceiling → `paused`, not silent degrade) + `/pseo-status --portfolio` triage + a recovery
> runbook; **scheduler default OFF**, per-cadence consent, projected daily cost shown before arming;
> per-step mid-job budget preflight. Spec §7 Phase 4 + §8. THEN the D11 comprehensive live-acceptance closes
> the build.

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

- **D11** Live-acceptance DEFERRED to the end (Süleyman 2026-06-06): build Faz 2+3+4, then ONE comprehensive all-phases live run, instead of the per-phase §8 gate before Faz 2. The hard "no autonomy un-proven" rule (Faz 4) is met by that end run. Memory `project_amo_live_acceptance_deferred`.
- **D12** Manager SPLIT spec-2c → **2c denetçi Stop-hook** + **2d correctness oracle** (precedent: 1b→1b+1b2). No shared code; smaller batches in the hard phase; enables 2a ∥ 2c ∥ 2d parallel. D5 (gates+oracle in-phase, never deferred) preserved — both ship in Faz 2.
- **D13** Consent scope = **PER-SESSION** (Süleyman 2026-06-06): a 2b gate allows a gated action iff an intact-chain consent entry matches `session_id` + `action` + `target_hash` (run_id is provenance only). Reason: the session UUID is already in every hook payload AND stamped on each 2a entry → the gate is a pure READ (no run_id mechanism, no single-use consumption log), while still guaranteeing nothing goes out unless approved IN THIS session. Rejected: single-use (gate would have to WRITE), run-scoped (needs a current-run pointer), approve-once (too loose for the Indexing hard-constraint). Manager also SPLIT spec-2b → **2b** outward-action gate (this) + **2e** AI-disclosure surface-rescan + **2f** secret-bytes/dfs_oversized/drift-F-rule (keep the safety phase in small reviewable batches).

- **D14** Faz-3 §4 mastery-lint pair SPLIT static/runtime (manager, 2026-06-08): **lint #1 `body ⊆ declared`**
  (static SKILL.md text analysis — what a skill INVOKES in prose ⊆ what it DECLARES) and **lint #2
  `observed ⊆ declared`** (runtime events.jsonl `source.mcp_tool` reconciliation per run) are DISTINCT data
  domains with different homes + fixtures → separate batches (lint #1 = **3a** ✅; lint #2 → **3-gov** with the
  carried drift-F-rule + secret-bytes scan). Reason: "split on genuinely distinct concerns" (build model);
  lint #1 alone is a full, grounded, single-concern batch (closes used⊆declared⊆registry) and was the promised
  headline "knows its parts" deliverable. The §4 conceptual pairing is not a code dependency. Lint #1 detector is
  invocation-PRECISE (NOT bare-token) — the whole point is distinguishing a call from a prose mention / a
  variable-dispatched `call_tool(var)`, so it flags real gaps and stays silent on both precision traps.
- **D15** Analysis steps → `model_attested` via a driver-side attested path (3b, reusable for 3c/3d): monthly's
  steps are INGESTION-shaped (raw≈committed) so `run_step`'s `silent_skip` (>50% raw→committed drop ⇒ failed)
  fits. ANALYSIS steps (aggregate/group/filter — audit's tech/schema/cannibalization) legitimately commit <50%
  of their raw input, and `run_step` applies `silent_skip` UNCONDITIONALLY (+ `derive_verdict` fails the run on
  any failed step) → routing them through `run_step` FALSE-FAILS them. Resolution (NOT a spine edit — spine is
  frozen): the driver dispatches by `verification_class` — `code_verified` → `run_step` (gate enforced);
  `model_attested` → a thin `_run_attested_step` that COMPOSES the spine's PUBLIC modules (`verify_raw_drop` +
  `committer.commit` + `coverage.build_step`) so identity+content+freshness STILL hard-gate a bad drop, but the
  silent-skip COUNT is advisory (recorded, not enforced). Plus a completion-guard (`pass→incomplete` unless ALL
  steps satisfied, since `derive_verdict` treats attested as soft). This is the honest ≤5%-scope split
  (spec §11) applied to analysis: structured ingestion = code-verified; analysis-reshaping = attested + the
  oracle is its independent backstop (→ 3-oracle follow-up). 3c/3d will reuse this dispatch.
- **D16** Two manager-author traps from 3-gov-driftF (F-27) — pre-warn future F-rule / validate_invariants batches:
  (a) **Standalone-load import trap:** `scripts/validation/validate_invariants.py` is loaded STANDALONE by the
  hook `scripts/hooks/check_excel_writer.py` via `spec_from_file_location` (repo root NOT on `sys.path`; before
  F-27 the file had ZERO top-level `from scripts...` imports — F-26's `SfMcpClient` is a LAZY in-function import).
  Adding a top-level `from scripts...` import raises `ModuleNotFoundError` during the hook's standalone load → the
  hook fails OPEN → a RED workbook slips through (the excel-writer invariant gate silently disabled). FIX = a
  `sys.path` repo-root bootstrap BEFORE the package imports (mirror `outward_action_gate.py`). Any batch adding a
  top-level scripts-import to a standalone-loaded module must do this. (b) **Invariant-count cascade (a 2nd
  immune system, parallel to D10):** adding an F-rule bumps implemented (`len(_RULE_FUNCTIONS)`), declared
  (`len(cross-sheet-invariants.rules)`), and tier counts — `tests/docs/test_count_consistency.py` pins all three
  + cites them across ~8 files (drift-check SKILL.md narrative/tier/rule-table + a `## F-NN` section, sibling
  SKILL.md, GLOSSARY, validate_invariants docstring, the json title). The MANAGER applies this cascade (worker
  scope-locks + surfaces the exact edit set); a worker prompt that adds an F-rule must NOT assume count_consistency
  stays green. Both were manager-author gaps in the F-27 prompt; the worker caught (a) + surfaced (b) cleanly.
- **D17** Faz-3 lint #2 reframed runtime→static (manager premise-revision + Süleyman, 2026-06-08): the spec's
  §4 lint #2 (`observed ⊆ declared`, RUNTIME events reconciliation) has NO viable data foundation — verifying
  the real tree (bootstrap's "verify the API before specifying" rule) showed `events.jsonl source.mcp_tool`
  is populated in ~3 of 3000+ events, inconsistently formatted (gsc `gsc__tool` vs dfs bare `tool`), and the
  orchestrator never writes it (it stamps the inbox raw-drop provenance `tool` + the coverage record, NOT an
  events row). Runtime B → vacuous or false-RED on every project; Option A (stamp it going forward) leans on
  the model reliably emitting provenance — the very thing AMO de-risks. Süleyman chose **B′ (static):**
  `workflow STEPS[].tool ⊆ owning-skill declared mcp_tools ⊆ registry` — the honest realization of "the system
  knows its parts," deterministic, self-contained, GREEN today, drift-catching. Extends 3a's
  `used⊆declared⊆registry` triangle UP to the orchestrator layer. Runtime reconciliation stays DEFERRED
  (revisit if Faz-4 live runs make observation-capture worth Option A).

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
