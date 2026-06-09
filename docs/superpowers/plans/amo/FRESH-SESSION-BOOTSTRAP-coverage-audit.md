# FRESH SESSION BOOTSTRAP — Path B Governance → Capability Coverage Audit

> **Purpose:** zero-loss handoff. The previous session's context filled up. Read THIS file
> top-to-bottom and you (a fresh Opus-4.8 manager session) are fully across everything the prior
> session knew. Then proceed as **manager**: drive the next batch (the Capability Coverage Audit)
> via the manager/worker model. **Date authored:** 2026-06-09.

---

## §0 — How to take over (do this first)
1. Read this file fully.
2. Skim the 4 canonical docs in §8 (the research doc is the most important — it's the *why*).
3. Verify the live state yourself (never assume — the D11 lesson, §6): `git log --oneline -6`,
   `git status`, `python3 -m pytest -q` (baseline should be **2423 passed, 10 skipped, 0 failed**).
4. Proceed with **§4 (the current task)** as manager. The operator (Süleyman) decides; you execute.

---

## §1 — The operator (Süleyman) — READ CAREFULLY, this shapes everything
- **Non-coder, SEO expert.** Communicate in **simple Turkish**. He does not read code; explain in plain terms.
- **He decides; you recommend.** Always present **2-3 options + your recommendation** (recommended option first, marked). Surface ONLY genuinely critical forks. Memory `feedback_decision_authority`: "ben karar veriyorum, sadece kritik onay alırım, brief'i direkt sun."
- **Evidence-driven, meticulous.** He explicitly asks for "çok titiz ve crosscheckli" work. **Verify every claim against the real code/files** — quote file:line. Do NOT assume.
- **Communication style** (`feedback_communication_style`): simple Turkish, ★ Insight blocks, tables, "2-3 seçenek + öneri" format. **Public docs** (README/release notes) in English; chat in Turkish.
- **Hard constraints** (`feedback_hard_constraints`, ABSOLUTE — a design breaking these is rejected):
  - Plugin is **100% agnostic** — NO project name / project data hardcoded in engine logic.
  - State is **append-only** — `events.jsonl` / consent / cost ledgers never `os.replace`d; master.xlsx only via `transaction.py`.
  - **Single source of truth**; schema-first (no schema → no write).
  - "AI tarafından yazıldı" **NEVER** in visible HTML (enforced in code: 2e quarantine).
  - Outward actions (push/delete/POST/Indexing/sitemap) need **per-session consent** (enforced: outward_action_gate).
  - Ask before writing **big new files**; routine manager file-updates + worker dispatch need no extra approval.
  - **git commit / push** need his OK (push is also consent-gated in-repo). He prefers "push all together when done."

## §2 — The north star (his founding vision — this is the WHOLE strategy)
> "Bütün skills / MCP / script / diğer dosyalar **çok efektif** kullanılsın, VE bunları **denetleyen bir
> mekanizma** olsun. Aslında bütün strateji buradan çıktı." — Süleyman, 2026-06-09.

Two wishes, one coin: (1) every part engages effectively at the right time; (2) a mechanism oversees that.
The engine (`/pseo-run` + 4 workflows + router + denetçi + consent gate + oracle) realizes this for the
**4 known jobs**. It does NOT (deliberately) auto-derive sequences for arbitrary intents — that general
engine is "Path B", researched and **deferred** (§3). The current line of work = cheap governance that
moves toward the vision without the risky engine.

## §3 — What is DONE (state as of 2026-06-09)
**Path B research (the O4 re-evaluation):** Recommendation = **NO-GO on the general orchestration engine;
CONDITIONAL-GO on a cheap governance ladder.** Doc: `docs/superpowers/specs/2026-06-09-path-b-general-orchestration-research.md`.
Why NO-GO now: (a) the engine would erode the ≤5% oracle guarantee (the oracle's independence needs an
out-of-band step-map a dynamic plan lacks); (b) the skill dependency graph was 77% inconsistent; (c)
expanding the hard-coded set (~15-line STEPS table per workflow + 1 router dict line per intent) is far
cheaper. Promote-trigger (O4): GO only if **T1** (≥8 novel multi-step intents/month) ∧ **T3** (graph lint
green) ∧ **T4** (signed plan-ledger). Today T1 unmet, T3 now buildable-green, T4 absent.

**Governance ladder rungs 0+1 — DONE, manager-verified, committed (local, unpushed):**
- **pb0** (`bd5b0cc`) — intent-router precision (mention ≠ request). The router's 1 canonical intent
  ("aylık bakım"→monthly) was arming the denetçi on mere *mentions/questions*. pb0 added a pure
  `is_actionable_request` (whole-word actionable verbs; question-markers take precedence; `yap`≠`yapay`)
  and a 3rd "1-soft" route branch: a *mention* writes a `superseded` marker (denetçi NOT armed) + a soft
  hint. Genuine requests byte-identical. **Synced to the live cache** (`~/.claude/plugins/cache/platinum-seo-marketplace/platinum-seo-engine/2.0.0/scripts/hooks/intent_router.py`)
  so the hook stops misfiring live. Suite 2304→2375. Files: `scripts/hooks/intent_router.py`, `tests/hooks/test_intent_router.py`.
- **pb1** (`a33529c`) — skill dependency-graph consistency lint. Built the directed-graph validator the
  schema *promises* but `glossary-audit` never built (it audits GLOSSARY *terms*). `scripts/validation/skill_graph_consistency.py`:
  HARD-FAIL on dangling `produces` skill-refs + `consumes` cycles (acyclic today = a GREEN guard, the T3
  prerequisite); produces-cycles/88.5%-asymmetry are advisory (`graph_health`). Removed 2 dangling edges
  (content-decay→content-improve, master-task-sync→dashboard-refresh). Suite 2375→2423. NOT wired live
  (read-only lint). Files: that module + `tests/schemas/test_skill_graph_consistency.py` + 2 SKILL.md.

**git state — 4 LOCAL commits, NONE pushed:**
```
a33529c feat(governance): pb1 — skill dependency-graph consistency lint   ✅ verified
ef7f658 wip(commands): provisional $1 → set -- $ARGUMENTS fix             ⚠️ UNVERIFIED — hold
bd5b0cc fix(router): pb0 — intent precision (mention ≠ request)            ✅ verified
d25238d docs(pathb): O4 re-eval research + rung-0/1 worker prompts
```
⚠️ **Push wrinkle:** `ef7f658` (unverified, §5) sits BETWEEN pb0 and pb1 → you cannot push pb1 without it,
and `git rebase -i` is unavailable in this env. Per Süleyman's "hepsi bitince birlikte push", **WAIT** to
push until the command-bug fix is verified (at next new-project). pb0 is already live via the cache, so
push is non-urgent.

## §4 — THE CURRENT TASK: Capability Coverage / Effectiveness Audit (operator-approved 2026-06-09)
**Süleyman approved this (Option A, "en iyi senaryo").** It is the *denetleyen mekanizma* for his "are all
parts used effectively?" wish, AND it tells us (data-driven, not guessing) which ad-hoc skills to promote
into orchestration next.

**The measured gap (verify it yourself — a quick teaser run by the prior session):** of 45 skills, ~22 are
reachable by name from a command/workflow; **~23 run ad-hoc only** (Claude invokes them from their SKILL.md
description triggers — i.e., OUTSIDE the sequenced+denetçi+oracle orchestration; "ad-hoc" ≠ dead). The 4
workflows orchestrate only **2 of 5 MCP servers** (gsc, dataforseo) — SF/Scrapling/Higgsfield only ad-hoc.

**What to build — a READ-ONLY audit (mirrors `scripts/reporting/portfolio_status.py` + `orchestration_metrics.py`):**
- NEW `scripts/reporting/capability_coverage.py` + `/pseo-coverage` command + tests.
- **Skill coverage (45):** classify each → `orchestrated` (in a workflow STEPS table) · `commanded` (named
  by a slash command) · `ad-hoc-only` (only its description triggers; reuse the frontmatter) · plus a
  **runtime** signal from `events.jsonl` (did it actually emit events in the last N days?). Reuse pb1's
  `parse_graph` + 3a's `skill_mcp_usage` where useful.
- **MCP coverage:** per server/tool — declared by skills (registry) vs orchestrated by a workflow STEPS
  `tool` vs never used.
- **Script coverage:** `scripts/**/*.py` invoked (by a skill body / command / workflow / test) vs orphaned.
- **Output:** a compact report (categories + counts + per-item table) and a **recommendations** section:
  the highest-value `ad-hoc-only` skills to promote into a workflow/router-intent next (the data-driven
  expansion guide). Optionally a coverage % the operator can watch improve over time (a recurring oversight
  report, like drift-check).
- **Honesty:** classification must be precise (a skill IS technically ad-hoc-reachable via its description —
  so "dead" is rare; the useful axis is *orchestrated vs commanded vs ad-hoc*, plus *actually-ran vs never-ran*).
  Do NOT overclaim "dead skills."
- **Scope/constraints:** READ-ONLY (zero state writes — grep-prove it), `parents[2]`-anchored, no schema/
  manifest change unless a new command bumps D10 (1 new command → D10 cascade: see MANAGER.md "D10"). TDD.
- A worker prompt is **already drafted**: `docs/superpowers/plans/amo/batch-coverage-audit-WORKER-PROMPT.md`.
  **Re-derive its claims yourself** before dispatching (don't inherit assumptions — D11). Refine if needed.

**Recommended next step to offer Süleyman (simple Turkish):** dispatch the coverage-audit worker (fresh
Opus-1M), you verify, commit. Then — guided by what the audit reveals — add router intents (audit/content/
setup are 1 line each) + new workflows for the highest-value ad-hoc skills.

## §5 — Open threads (carry these forward)
1. **Command-bug fix (DEFERRED to next new-project, operator's call).** `commands/*.md` `!`...`` blocks use
   `$1/$2/$3` which arrive empty (only `$ARGUMENTS` substitutes). Provisional `set -- $ARGUMENTS` fix applied
   to 23 files in commit `ef7f658` but **UNVERIFIED** — the substitution mechanism is undocumented (3
   "worlds"; W1 means the fix is wrong). Full context + the finalize-plan is in the **task chip**
   `task_95532bea` and `docs/bugs/2026-06-09-slash-command-positional-args-empty.md`. The live diagnostic
   (`/pseo-bind <slug>` + `/pseo-approve aa bb cc`) runs naturally during `/pseo-init` for a new project.
   `pseo-bind.md`+`pseo-approve.md` already synced to cache for that test. **Do not push `ef7f658` until verified.**
2. **Push decision** (§3 wrinkle) — wait for "all together."
3. **Optional governance follow-ups** pb1 surfaced (out of scope, future small batches): wire pb1's lint
   into drift-check as an F-rule (live governance); `init-portfolio`/`portfolio-init` are likely typos of
   `init-project`; the `content-improve` phantom-skill vs `content_improve` real-sheet naming collision; 35
   orphan consumed-artifacts; 25 unrecognised consume-prefixes.

## §6 — Build model (every batch obeys — this is what made the build reliable)
- **Manager/worker.** You (manager) author a self-contained worker prompt → Süleyman dispatches it to a
  **fresh Opus-4.8 1M-context worker** → relays the report → **you INDEPENDENTLY re-derive every claim**
  (run the suite YOURSELF, read the diff, re-derive the key result with your OWN probe — NOT by importing
  the worker's module) → then commit. The **D11 lesson**: a contract-key error is invisible to an
  independent derivation that *inherits* it — cross-check against real workspace files.
- **Worker rules** (put in every prompt): **NO Task/Agent tools — work inline** (subagents fail here:
  "Prompt too long"). Baseline-first (record exact pytest N; end ≥). TDD RED→GREEN→REFACTOR. Scope-locked
  (only named files; out-of-scope → STOP + report). No commit (manager commits). Schema-first for schema
  changes (4-way sync + `test_cross_sheet_invariants_sync.py`).
- **Serial cadence** (one batch at a time) avoids the parallel-worktree contention lesson
  (`project_amo_parallel_worktree_contention`). The prior session kept a clean tree for each worker.
- **Live commands/hooks run from the CACHE**, not this dev repo (D11) — a runtime fix must be synced to
  `~/.claude/plugins/cache/platinum-seo-marketplace/platinum-seo-engine/2.0.0/...`. A read-only test/lint
  does NOT need syncing.

## §7 — Architecture cheat-sheet (so you don't re-learn it)
- **The conductor:** `/pseo-run <workflow> <slug>` drives 4 hard-coded ordered workflows. Each structured
  step: MODEL makes the MCP call → drops a provenance-stamped raw JSON at an orchestrator-dictated path →
  an existing transform CLI runs → CODE verifies (`verify_raw_drop`: identity+content+freshness) → commits
  (`committer` = `transaction.replace`, idempotent) → writes a coverage record.
- **FROZEN spine (compose, NEVER edit):** `scripts/orchestration/{run_step,verify,committer,coverage}.py`
  + the shared `workflow_driver.py` (data-driver). `content_pipeline.py` is a separate artifact-driver.
- **The 4 workflows + their sequenced steps** (`scripts/orchestration/workflows/`):
  - `monthly`: gsc_pull → quick_wins → content_decay (→ report). MCP: gsc.
  - `audit`: tech_audit → schema_audit → on_page_audit → cannibalization. MCP: dataforseo + gsc + SF.
  - `setup`: topical_map → cluster_map → new_content_plan. MCP: dataforseo.
  - `content`: new_blog → generate_images → faq_optimization. Artifact (Higgsfield).
- **Router** (`scripts/hooks/intent_router.py`): `CANONICAL_WORKFLOWS` currently has ONLY `monthly`. Adding
  an intent = 1 dict entry (data-driven). pb0 added `is_actionable_request` (the mention/request gate).
- **Safety layer:** `outward_action_gate.py` (PreToolUse consent gate — push/rm/POST/sitemap/indexing) ·
  `denetci.py` (Stop-hook auditor: a `declared` intent must reach a fresh passing coverage record) ·
  `ai_disclosure_rescan.py` (PostToolUse blog-HTML quarantine) · `orchestration_metrics.py` (the
  independent ≤5% oracle, reconciles committed master.xlsx vs raw provenance — keyed on a HARDCODED
  `_WORKFLOWS` registry, the property a dynamic plan would break).
- **Existing lints (governance):** `skill_mcp_usage.py` (body⊆declared MCP, 3a) · `workflow_tool_declared.py`
  (workflow tool⊆declared, lint2) · F-27 in `cross-sheet-invariants.json` (declared outward MCP ⊆ gate) ·
  **pb1** `skill_graph_consistency.py` (the dependency graph). The coverage audit (§4) joins this family.
- **45 skills** under `skills/<category>/<name>/SKILL.md` (discovery 11, reporting 9, production 5, planning
  5, ingestion 5, meta 4, governance 4, publishing 2). Each declares `inputs/outputs/consumes/produces/
  mcp_tools/triggers/budget/autonomy` in frontmatter (the latent capability graph). **24 commands** under
  `commands/`. **5 MCP servers:** gsc, dataforseo, sf, scrapling(ScraplingServer), higgsfield.
- **Workspace vs engine:** engine repo = `/Users/apple/Documents/platinum-seo-engine` (the plugin/recipe);
  workspace = `/Users/apple/Documents/platinum-seo-workspace` (project data/state, `shared/`, `projects/<slug>/`).
  They are SIBLINGS. Active project currently `dentnotion`.

## §8 — Canonical files to read for depth (in priority order)
1. `docs/superpowers/specs/2026-06-09-path-b-general-orchestration-research.md` — the research/why (THE doc).
2. `docs/superpowers/plans/amo/batch-coverage-audit-WORKER-PROMPT.md` — the current task's worker prompt (re-derive it).
3. Memory `project_path_b_research.md` — the full narrative (auto-loaded; this bootstrap mirrors it).
4. `docs/superpowers/plans/amo/MANAGER.md` — the AMO build record (D1-D17, the D10 count-cascade rule, the spine).
5. The pb0/pb1 worker prompts (`batch-pb0-...md`, `batch-pb1-...md`) — the house style for worker prompts.
6. The code in §7 — read before you touch.

## §9 — First actions for the fresh session
1. Verify state (§0.3). Confirm baseline 2423/0.
2. Greet Süleyman in Turkish; confirm you've taken over and are ready to build the Coverage Audit (his approved choice).
3. Read + re-derive the coverage-audit worker prompt; refine if your independent analysis disagrees.
4. Present the dispatch plan (2-3 options if there's a real fork; else just proceed) and go.
5. Keep the open threads (§5) tracked. Don't push without his OK.
