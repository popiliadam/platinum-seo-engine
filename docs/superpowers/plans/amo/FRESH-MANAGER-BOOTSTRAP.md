# AMO — Fresh Manager Session Bootstrap

> **Paste this whole file (or "read docs/superpowers/plans/amo/FRESH-MANAGER-BOOTSTRAP.md and take over the
> AMO build") into a new Claude Code session at `/Users/apple/Documents/platinum-seo-engine`.** It makes you,
> the new manager, 100% operational with zero information loss. The prior manager hit its context limit;
> everything it knew is committed to git + saved in memory. You are NOT starting over — you are continuing.

---

## 0. Who you are & what to read

You are the **manager session** for the **AMO (Autonomy & Multi-project Orchestration)** initiative — the
candidate **v2.0** of the Platinum SEO Engine. Your job: author worker prompts, dispatch them to fresh
Opus-4.8 1M-context worker sessions (via Süleyman, who pastes + relays), **verify each returned REPORT
yourself**, then **commit + push**, then author the next batch. You do NOT write the feature code; workers do.

**Read in this order before doing anything:**
1. This file (the full brief below).
2. `docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md` — the full v3 design.
3. `docs/superpowers/plans/amo/MANAGER.md` — **live** batch table (0a-2f all ✅), decisions D1-D13, build model, MANAGER
   PROTOCOL & CONTINUATION. **This is the source of truth for current state** — check it + `git log --oneline -15`
   to see exactly what's done.
4. Memory `project_amo_initiative.md` (+ the `feedback_*` user files — Süleyman's communication style).
5. `docs/superpowers/plans/amo/batch-0a..2f-WORKER-PROMPT.md` — your worker-prompt TEMPLATES (copy their shape;
   the 2a-2f prompts are the freshest, richest examples — schema-freeze, hook-gate, oracle, hook-completeness).

---

## 1. What we're building & why

Two operator complaints drive everything: (1) "the right skill/MCP usually doesn't auto-engage — work goes
manual"; (2) "I can only work one project at a time; I want 3-5 in parallel." AMO = an autonomous,
agentic SEO orchestration layer that solves both. **5 phases:**
- **Faz 0 — Foundation:** bind each Claude session to one project (so N windows = N projects, no
  cross-contamination, and everything attributes correctly). ✅ *done — Faz 0+1+2 all COMPLETE; **Faz 3 is next** (see §9).*
- **Faz 1 — Orchestrator:** "do monthly maintenance for alpha" → an ordered Python pipeline runs every
  required step with **verification of each step's OUTPUT** (the design reframe), reusing existing skills.
- **Faz 2 — Denetçi + gates + oracle:** a Stop-hook auditor forces missing steps; PreToolUse gates hard-block
  irreversible actions (Indexing/publish/push) unless consent; a correctness oracle measures the ≤5%.
- **Faz 3 — Replicate** the pattern to more workflows + ship the two "mastery" lints.
- **Faz 4 — Portfolio fan-out + cost ceiling + optional scheduler (default OFF).**

**Build philosophy = Path A (Süleyman-chosen):** hard-coded ordered sequences first; NO general DAG engine /
auto-derived capability graph yet (deferred to Phase 3+ if a 4th workflow earns it). Spec §3-§5 is canonical.

**Honest scope:** ≤5% error is achievable on **structured** workflows (verifiable by code). Content QUALITY
(blog generation) is NOT guaranteed by orchestration — it's bounded by the model + the content-validator gate,
measured separately. Don't conflate them.

**This design was adversarially hardened** (9-agent review, workflow `wf_527271b3-931`, 51 findings) — the
spec already incorporates all the must-fixes. Don't re-litigate settled decisions; see D1-D10.

---

## 2. The per-batch loop YOU run

1. **Author** a self-contained worker prompt → save as `docs/superpowers/plans/amo/batch-XX-WORKER-PROMPT.md`
   AND give Süleyman the fenced ```text block to paste.
2. Süleyman pastes it to a fresh Opus-4.8 1M worker, relays the REPORT back to you.
3. **VERIFY — never trust blindly:** run the full suite yourself
   (`PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q | tail`), confirm
   `passed >= baseline` + `0 failed`; `git status --short` (scope = only the batch's files); `git diff` the
   risky bits (security, public contracts/ADRs, any out-of-scope migration); read new security-sensitive code.
4. If a worker added a `commands/*.md` or `schemas/*.json` → **apply the count-guard bumps yourself** (D10):
   `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` counts + `tests/schemas/test_json_schema_draft_consistency.py`.
5. **Green + clean → commit + push:** `git add <files>` → conventional message (`feat(...)`/`docs:`) ending
   `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` → `git push origin main`.
6. Update `MANAGER.md` (batch → ✅ DONE) + memory. Author the next batch.

## 3. Worker-prompt recipe (every prompt has these sections)

`HARD RULES` (verbatim: **NO Task/Agent tools — they FAIL here, "Prompt is too long"**; NO git; baseline-first
with the pytest command above; TDD RED-first; immutability/no-debug-prints/functions<50 lines; **scope-lock**
— edit ONLY named files, anything else → STOP+report; no-commit, manager commits) · `WHY` · `CONFIRMED FACTS`
(so the worker doesn't re-derive) · `ORIENT` (exact files+line ranges to read) · `SCOPE` (the only files to
touch) · `SPEC` (precise, behavior-preserving) · `TDD` (the cases) · `METHOD` · `DURUR` (when to stop) ·
`REPORT` (what to print). Workers have 1M context → you may inline full file contents + bigger scope.

## 4. Standing authorizations (Süleyman, 2026-06-05 — do NOT re-ask)

- Manager **verifies → commits → pushes** every green+verified batch without per-batch approval.
- Süleyman delegates ALL non-critical decisions to the manager ("EN KRİTİK: ben karar veririm, sadece kritik
  onay alırım, brief'i direkt sun"). Only surface genuinely critical/irreversible choices.
- A worker MAY migrate out-of-scope test/guard files when a scoped change unavoidably breaks them ("Option 1 /
  best scenario") — you verify the migration **preserves/strengthens** the contract, never weakens it.
- Count-guard manifest bumps are the manager's job.

## 5. Accelerators (approved 2026-06-05)

- **Bigger batches:** with 1M workers, merge cohesive single-concern work; split only on hard dependency (a
  schema must freeze before its consumer) or distinct concerns. (Phase-0 batches were deliberately small for
  ≤5%; you may size up — but Phase 1-2 are the hard, risky phases, so don't over-merge there.)
- **Parallel worker windows 🔥:** dispatch FILE-DISJOINT batches in 2-3 windows at once; verify each report
  independently. (e.g. Phase-0 0e + 0f are disjoint.)

## 6. Recurring gotchas (these bit prior batches — pre-warn workers)

- **D10 count-consistency immune system:** adding a `commands/*.md` or `schemas/*.json` trips
  `tests/docs/test_count_consistency.py` (pins counts in plugin.json + marketplace.json) AND
  `tests/schemas/test_json_schema_draft_consistency.py`. Manager bumps all three.
- **Bare-CLI `sys.path`:** a script run as `python3 scripts/.../x.py` has `sys.path[0]=scripts/.../`, so
  `scripts.*` imports fail — add a file-relative bootstrap (`parents[N]`, NOT `CLAUDE_PLUGIN_ROOT`, to avoid an
  installed-plugin copy shadowing the working tree). See dump_workspace (0c).
- **Hook-script classification:** a NEW wired hook script must be added to `RUNTIME_HOOK_SCRIPTS` +
  `scripts/hooks/README.md` or `test_hook_scripts_runtime_vs_ci.py` fails (env_probe 0a, audit_post_tool_use 0d).
- **Tests must monkeypatch `HOME`** (the binding reads `~/.config/pseo/config.json`).
- **events.jsonl is in-place-rewritten** (no separate lockfile) → mutations IN-PLACE, **never os.replace**
  (inode swap = data loss). But *marker files* (active.json, session markers, coverage records) DO use
  os.replace — they're mutable pointers, not append-only logs. Know the difference. (consent.jsonl is an
  append-only LOG → O_APPEND, like events.jsonl.)
- **Scope-locked commit amid shared-worktree contention (bit EVERY Faz-2 batch):** Süleyman runs parallel
  batches in ONE repo dir (separate Claude sessions, same filesystem). So `git add <only THIS batch's named
  files>` — NEVER `git add -A`. A full-suite run is a MOVING TARGET (a sibling's half-written test can ABORT
  pytest collection); verify a batch via its OWN scoped tests + `git status` scope, and ATTRIBUTE sibling
  failures (don't block this batch on them). Every Faz-2 commit was scope-locked this way (memory
  `project_amo_parallel_worktree_contention`).
- **Manager QA must read security-sensitive code line-by-line, not trust the worker's REPORT.** A real gap
  found in verification (e.g. 2b's fail-open-on-corrupt-ledger) gets a TRACKED follow-up batch (→ 2f) + is
  surfaced to Süleyman — never silently shipped or silently dropped. Run the FULL suite yourself; `git diff`
  the risky bits; confirm READ-ONLY claims by grep.

## 7. Key technical facts you must hold (verified, don't re-derive)

- **Binding key = the Claude session UUID** (D9), identical from hook stdin `session_id` and command env
  `$CLAUDE_CODE_SESSION_ID` (directly proven same-session in VSCode 2.1.162). Engine root = `$CLAUDE_PLUGIN_ROOT`
  (reliable). Workspace root persisted to `~/.config/pseo/config.json` (env unreliable). Marker =
  `<workspace>/shared/sessions/<uuid>.json`.
- **The binding primitive** `scripts/state/session_binding.py` (batch 0b): `resolve_session_project(ws, *, arg,
  session_id, strict)`, `read_session_binding`, `current_session_id(payload, environ)`, `resolve_workspace_root`,
  `write_session_binding`, `persist_workspace_root`, `session_ids_consistent`. Wired into dump_workspace +
  content-gate (0c) + the audit hook (0d).
- **Corrected facts (don't repeat v2's errors):** a resumable **`paused`** workflow state already exists (use
  it for external-failure, don't invent `blocked`); `failure_reason.code` real enum = [validation_error,
  mcp_error, budget_exhausted, user_rejected, timeout, internal_error] (add a `failure_reason.external` bool,
  don't invent codes); `event_type` is a **closed exactly-12 enum** (coverage events go to `_state/coverage/`,
  NOT a new event_type); 10 projects already exist, `ACTIVE_PROJECTS_MAX=12` copy-pasted in 6 files.
- **Phase-1 design seam (spec §7):** orchestrator can't make MCP calls (only the model can; hooks can't invoke
  tools). So the spine VERIFIES each step's OUTPUT (identity+content, not just exists+non-empty) — the model
  makes the MCP call + drops a provenance-stamped raw artifact, code gates it. master.xlsx writes live in
  model-executed SKILL.md prose → Phase 1 must relocate them into a callable committer (`transaction.replace`,
  not append — idempotent resume). No `kind:agent` steps (subagents fail).
- **Phase-2 primitives (ALL shipped, suite 2036/0 — reuse, don't rebuild):**
  - **Consent ledger** `scripts/state/consent_ledger.py`: `append_consent` (O_APPEND + flock, hash-chained,
    NEVER os.replace), `read_entries`, `verify_chain`, `target_hash`, `has_consent` (keys on run_id),
    **`has_session_consent` (keys on session_id)**, schema `schemas/consent.schema.json` (8 required fields,
    6-value `action` enum [git_push/fs_delete/net_post/mcp_submit/index_update/dfs_oversized]), `/pseo-approve`
    command. **D13: consent is PER-SESSION** — a gate matches `session_id`+`action`+`target_hash`; run_id is
    provenance only.
  - **Gates** (PreToolUse/PostToolUse, all classified RUNTIME): `scripts/hooks/outward_action_gate.py`
    (default-DENY the 5 outward actions unless per-session consent; segment-split + git-global-flag aware;
    fail-CLOSED on the gated path, fail-OPEN on non-gated; deny-message echoes the exact `/pseo-approve` line)
    + `scripts/hooks/ai_disclosure_rescan.py` (PostToolUse; quarantine-renames a disclosed `outputs/blog/**`
    HTML off the live `.html` surface; REUSES `content_validator` + `validate_content_write.is_content_html_path`;
    recency-guarded so a read never triggers).
  - **Denetçi** `scripts/hooks/denetci.py` (Stop hook, 2nd after stop_validation): blocks an unfinished
    owed-this-turn workflow (reads 1c intent marker + 1a coverage; mtime-freshness; reuses
    `remediation.render`); READ-ONLY, non-crashing, respects `stop_hook_active`.
  - **Oracle** `scripts/reporting/orchestration_metrics.py` (offline, READ-ONLY): reconciles committed
    master.xlsx ↔ raw provenance via the transform-OUTPUT bridge per run_id → the trustworthy ≤5% number +
    `fake_green` (verdict==pass but data mismatches); NEVER trusts `coverage.verdict`.

## 8. How to work with Süleyman (the operator)

Non-coder SEO expert. **Simple Turkish.** Format: ★ Insight blocks, tables, "2-3 options + your
recommendation." He decides fast and delegates non-critical things — present a direct brief, don't over-ask.
Evidence-based; values a final-check / "what's missing?" ritual. He runs the workers (pastes prompts, relays
reports) and tests live in his environments. Public docs/READMEs = English; chat = Turkish. His hard
constraints are absolute: Indexing-API submit needs his explicit consent; "written by AI" must NEVER appear in
visible HTML; append-only state; plugin-agnostic (no CMS/site specifics in the engine). See the `feedback_*`
memory files.

## 9. Remaining work — UPDATED 2026-06-06 (Faz 0 + Faz 1 + Faz 2 DONE)

> **A fresh manager taking over for FAZ 3 starts here.** Faz 0 ✅, Faz 1 ✅, Faz 2 ✅ are shipped + pushed;
> read MANAGER.md's banners (PHASE 0 / PHASE 1 COMPLETE / 🎉 FAZ 2 COMPLETE) + the batch table (0a-2f all ✅)
> + the decision register D1-D13 for the exact commit trail, lessons, and frozen contracts. Suite is at
> **2036 pass / 8 skip / 0 fail** (HEAD `95bc421`, working tree clean). Do NOT re-do them.

- **Faz 0 ✅ COMPLETE** (`09674c5`): session-id binding (0a-0c) + audit attribution (0d) + parallel-write
  safety (0e2/0f).
- **Faz 1 ✅ COMPLETE** (`3b9d87e`+`1fa70d3`): orchestrator end-to-end — 1a schema freeze → 1b spine
  (`scripts/orchestration/` run_step+committer+verify+coverage) → 1c intent router → 1b2 skill-write
  relocation → 1d monthly-maintenance + `/pseo-run` + remediation → 1d.1 driver/CLI reconciliation.
- **Faz 2 ✅ COMPLETE** (6 batches, suite 1891→2036, +145 tests): **2a** consent ledger (`de44bbd`) · **2c**
  denetçi Stop-hook (`e50d655`) · **2d** correctness oracle (`7234ccf`) · **2b** outward-action consent gate
  (`dafec71`, **D13 per-session**) · **2e** AI-disclosure PostToolUse surface-rescan (`f2cd64d`) · **2f** gate
  completeness (fail-closed + compound-command split, `6760314`). Both operator hard-constraints are now
  ENFORCED IN CODE (Indexing-submit needs per-session consent; "written by AI" can't reach visible HTML even
  via Bash). See §7 "Phase-2 primitives" for the exact module/contract list + MANAGER.md's FAZ-2-COMPLETE banner.
- **⏳ LIVE-ACCEPTANCE is deferred to the END (D11, Süleyman 2026-06-06) — NOT a per-phase gate.** After Faz 3
  + Faz 4 are built, ONE comprehensive all-phases live run (`/pseo-run monthly <slug>` on a real GSC-verified
  project + observe gate/denetçi/consent live in all 3 environments). The hard "no autonomy un-proven" rule
  (Faz-4 scheduler) is met by that end run. Do NOT block Faz 3 on a live test. (Memory
  `project_amo_live_acceptance_deferred`. Recommended project when the time comes: Vento — GSC confirmed.)
- **Faz 3 (NEXT — replicate + mastery lints; spec §7 Phase 3 + §4 + §5):**
  - **Replicate the orchestrator pattern** (the proven 1b spine + 1d workflow shape) to more ordered Python
    workflows: `workflows/{new-project-setup, content-pipeline, audit-suite}`. Each reuses run_step/committer/
    verify/coverage; the MODEL makes the MCP calls + drops provenance-stamped raw artifacts, code gates them
    (the Phase-1 seam, §7). Per-workflow blast-radius: relocate any SKILL.md-prose master.xlsx writes into the
    committer + keep each skill's existing tests green (the 1b2 pattern). Size each as its own batch.
  - **Ship the two §4 "mastery" lints** (deliver "the system knows all its parts" WITHOUT a graph): (1)
    **body⊆declared** — parse each SKILL.md body for `mcp__server__tool` + native `sf_*` calls; FAIL if a tool
    is invoked in prose but missing from that skill's `mcp_tools.required/optional` (catches the ~6 skills with
    undeclared MCP deps + `sf_load_crawl` that isn't even in the registry → **fix the registry too**). (2)
    **observed⊆declared** — per run, collect observed MCP tools from `events.jsonl` `source.mcp_tool`, assert ⊇
    the workflow's declared-required set; declared-but-not-observed = coverage miss, observed-but-not-declared
    = AMBER feeding lint #1.
  - **Carried-from-Faz-2 deferrals that land in Faz 3:** (a) the **drift-F-rule** (every declared OUTWARD MCP
    tool ⊆ a 2b gate matcher) — a natural third lint alongside the §4 pair; (b) the **secret-bytes scan**
    (scan the literal pending bytes incl. gitignored targets, not just git-enumerated files — enhances the
    existing `scripts/security/check_secrets.sh`). Both were split out of 2b/2f as governance/lint work.
  - **Promote-to-declarative DECISION GATE (spec O4):** define the concrete trigger (≥2 workflows sharing ≥N
    edges, or operator-authored workflows requested) that flips Phase 3 from "more hard-coded sequences" to
    "build the declarative engine + auto-graph." Default = stay Path A unless a 4th workflow earns it.
- **Faz 4 (after Faz 3):** `/pseo-run-portfolio` cross-project fan-out (disjoint locks) + portfolio cost/quota
  ledger under `shared/` (atomic reserve-then-confirm; GSC quota, **DFS credits — carries `dfs_oversized` from
  2b**, image spend) + hard global ceiling + kill-switch + `/pseo-status --portfolio` + recovery runbook;
  scheduler **default OFF**, explicit per-cadence consent, projected cost shown before arming. THEN the D11
  comprehensive live-acceptance closes the build.
- **Cross-cutting (carry through):** e2e stub harness pattern (1b/1d/2d), self-upgrade versioning consolidation
  (coverage has optional `engine_version`), ACTIVE_PROJECTS_MAX 1-module consolidation. **Open (separate
  triage):** Codex ruthless-handoff audit 72/100 (`docs/audits/2026-06-05_...`, spawn_task chipped).
  **Recurring trap:** never quote a watched secret token in a non-excluded doc (re-trips `check_secrets`); run
  the FULL suite even after a "docs-only" commit.

**You have everything. Confirm your understanding to Süleyman in simple Turkish, then continue the loop —
propose the Faz-3 batch order (the two §4 lints + drift-F-rule are low-risk governance/CI and were promised,
so they're a natural first batch; the replicate-workflows are bigger and each is its own batch). Let Süleyman
pick which workflow to replicate first.**
