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
3. `docs/superpowers/plans/amo/MANAGER.md` — **live** batch table, decisions D1-D10, build model, MANAGER
   PROTOCOL & CONTINUATION. **This is the source of truth for current state** — check it + `git log --oneline -15`
   to see exactly what's done.
4. Memory `project_amo_initiative.md` (+ the `feedback_*` user files — Süleyman's communication style).
5. `docs/superpowers/plans/amo/batch-0a..0f-WORKER-PROMPT.md` — your worker-prompt TEMPLATES (copy their shape).

---

## 1. What we're building & why

Two operator complaints drive everything: (1) "the right skill/MCP usually doesn't auto-engage — work goes
manual"; (2) "I can only work one project at a time; I want 3-5 in parallel." AMO = an autonomous,
agentic SEO orchestration layer that solves both. **5 phases:**
- **Faz 0 — Foundation:** bind each Claude session to one project (so N windows = N projects, no
  cross-contamination, and everything attributes correctly). ← *we are finishing this.*
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
  (inode swap = data loss). But *marker files* (active.json, session markers) DO use os.replace — they're
  mutable pointers, not append-only logs. Know the difference.

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

## 8. How to work with Süleyman (the operator)

Non-coder SEO expert. **Simple Turkish.** Format: ★ Insight blocks, tables, "2-3 options + your
recommendation." He decides fast and delegates non-critical things — present a direct brief, don't over-ask.
Evidence-based; values a final-check / "what's missing?" ritual. He runs the workers (pastes prompts, relays
reports) and tests live in his environments. Public docs/READMEs = English; chat = Turkish. His hard
constraints are absolute: Indexing-API submit needs his explicit consent; "written by AI" must NEVER appear in
visible HTML; append-only state; plugin-agnostic (no CMS/site specifics in the engine). See the `feedback_*`
memory files.

## 9. Remaining work — UPDATED 2026-06-06 (Faz 0 + Faz 1 DONE)

> **A fresh manager taking over for FAZ 2 starts here.** Faz 0 ✅ and Faz 1 ✅ are shipped + pushed; read
> MANAGER.md's two banners (PHASE 0 / PHASE 1 COMPLETE) for the exact commit trail + lessons. Suite is at
> **1891 pass / 0 fail** (HEAD ~`5889adc`). Do NOT re-do them.

- **Faz 0 ✅ COMPLETE** (`09674c5`): session-id binding substrate (0a-0c) + audit attribution (0d) + parallel-
  write safety (0e2/0f). 0d.1 banners = deferred cosmetic.
- **Faz 1 ✅ COMPLETE** (`3b9d87e` + fix `1fa70d3`): orchestrator end-to-end. 1a schema freeze (coverage
  record + `failure_reason.external` + `paused` reuse) → 1b spine (`scripts/orchestration/` run_step+committer+
  verify+coverage) → 1c intent router (`scripts/hooks/intent_router.py` + intent-marker.schema) → 1b2 skill-
  write relocation (3 skills → `committer.commit`, snapshot dup-bug fix) → 1d monthly-maintenance workflow
  (`scripts/orchestration/workflows/monthly_maintenance.py`) + `/pseo-run` + `remediation.py` → 1d.1
  driver/CLI reconciliation (output_path by SHEET + real-CLI integration test).
- **⏳ GATE before Faz 2: LIVE-ACCEPTANCE (spec §8).** Süleyman runs `/pseo-run monthly <slug>` once on a real
  GSC-verified project (needs the CURRENT installed plugin — `/pseo-run` only exists in the latest version).
  If it stumbles in the model's execution of the recipe → a small **1d.2** recipe-hardening batch first. Only
  after the loop is demonstrated live do we build Faz 2's enforcement on top.
- **Faz 2 (NEXT — the hard, safety-critical phase; spec §7 Phase 2 + §3 L4/oracle):**
  - **2a** consent ledger: `_state/consent.jsonl` schema (append-only, **hash-chained** prev-hash per line) +
    a recorder + paired tests; wire append-only enforcement into a PreToolUse gate. (Hard prereq for 2b/2c.)
  - **2b** PreToolUse outward-action gates: default-DENY `git push` / `rm` / `curl|wget POST` / concrete MCP
    submit tools (`mcp__gsc__submit_sitemap`, future indexing URL_UPDATED) / oversized DFS unless a consent
    entry `(run_id, action, target_hash)` exists. + AI-disclosure PostToolUse content-SURFACE rescan of
    `outputs/blog/**/*.html` (block-and-revert; catches Bash/heredoc bypass of the Write-only validator).
    Secret gate scans the literal pending bytes. (Süleyman's hard constraints: Indexing-submit needs explicit
    consent; "written by AI" must NEVER appear in visible HTML — see `feedback_indexing_api_consent` +
    `feedback_ai_disclosure_ban`.)
  - **2c** denetçi Stop-hook (extends `hooks/stop.json` chain; `stop_validation.py` untouched; no-op unless a
    current-turn `intent_declared` marker exists; respects the 8-block cap) — reads the 1c intent marker +
    the 1a coverage record: incomplete → `decision:block` + the Turkish `remediation.render(...)` fix command;
    `failure_reason.external==true` → map to `paused` + RED + ALLOW turn-end. + **correctness oracle**
    `scripts/reporting/orchestration_metrics.py` (reconcile master.xlsx rows vs raw-provenance per run_id =
    the trustworthy ≤5% number, independent of self-reported status). D5: gates+oracle built ALONGSIDE, never
    deferred. Remediation already handles `paused`; the marker + coverage contracts are frozen (1a/1c).
- **Faz 3-4** (later): replicate to new-project/content-pipeline/audit-suite + the two §4 mastery lints
  (body⊆declared MCP, observed⊆declared) + `sf_load_crawl` registry fix; then portfolio fan-out + cost ledger
  + kill-switch + scheduler (default OFF).
- **Cross-cutting (carry through Faz 2+):** e2e stub harness (pattern set in 1b/1d), self-upgrade versioning
  full consolidation (coverage already has optional `engine_version`), ACTIVE_PROJECTS_MAX 1-module
  consolidation. **Open:** Codex ruthless-handoff audit 72/100 (`docs/audits/2026-06-05_...`) — separate
  triage, spawn_task chipped (P1: .mcp.json `.env` shell-source, non-atomic migration writes, narrow CI
  secret-gate, `rules/*.md` missing-test cites). **Recurring trap:** never quote a watched secret token
  (the CI scanner's grep literals) in a non-excluded doc — it re-trips `check_secrets`; run the FULL suite
  even after a "docs-only" commit.

**You have everything. Confirm your understanding to Süleyman in simple Turkish, then continue the loop.**
