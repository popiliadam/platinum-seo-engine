# AMO — Fresh Manager Session Bootstrap

> **Paste this whole file (or "read docs/superpowers/plans/amo/FRESH-MANAGER-BOOTSTRAP.md and take over the
> AMO build") into a new Claude Code session at `/Users/apple/Documents/platinum-seo-engine`.** It makes you,
> the new manager, 100% operational with zero information loss. The prior manager hit its context limit;
> everything it knew is committed to git + saved in memory + this file. You are NOT starting over — you are
> continuing. **Current handoff point (2026-06-08): Faz 0+1+2+3 ALL ✅ and Faz 4 batches 4a (cost ledger) +
> 4b (portfolio sweep + kill-switch) ✅ shipped. You pick up at Faz 4 batch 4c (`/pseo-status --portfolio`),
> then 4d (scheduler, default OFF) + 4e (runbook), then the D11 comprehensive live-acceptance closes the
> build. Suite 2241 pass / 7 skip / 0 fail. MANAGER.md's batch table + banners are the live truth.**

---

## 0. Who you are & what to read

You are the **manager session** for the **AMO (Autonomy & Multi-project Orchestration)** initiative — the
candidate **v2.0** of the Platinum SEO Engine. Your job: author worker prompts, dispatch them to fresh
Opus-4.8 1M-context worker sessions (via Süleyman, who pastes + relays), **verify each returned REPORT
yourself**, then **commit + push**, then author the next batch. You do NOT write the feature code; workers do.

**Read in this order before doing anything:**
1. This file (the full brief below).
2. `docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md` — the full v3 design (§4 the two mastery lints, §5 roadmap, §7 phase sketches, §10 O4, §11 honest scope).
3. `docs/superpowers/plans/amo/MANAGER.md` — **live** batch table (0a-3d all ✅), decisions **D1-D16**, build model,
   the phase banners (PHASE 0/1/2 COMPLETE, FAZ-3 STARTED, **🎉 FAZ 3 REPLICATION LINE COMPLETE**), MANAGER
   PROTOCOL & CONTINUATION. **This is the source of truth for current state** — check it + `git log --oneline -25`
   to see exactly what's done.
4. Memory `project_amo_initiative.md` (the full narrative through 3d) + the `feedback_*` user files (Süleyman's
   communication style + hard constraints).
5. `docs/superpowers/plans/amo/batch-*-WORKER-PROMPT.md` — your worker-prompt TEMPLATES. The FRESHEST + richest:
   **batch-3b / batch-3c = the DATA-driver shape** (raw drop → transform CLI → committer → sheet);
   **batch-3d = the ARTIFACT-driver shape** (model emits a file → verify artifact + content gate);
   **batch-3gov-driftF = the F-rule shape** (drift-check governance); **batch-3a = the static-lint shape**.

---

## 1. What we're building & why

Two operator complaints drive everything: (1) "the right skill/MCP usually doesn't auto-engage — work goes
manual"; (2) "I can only work one project at a time; I want 3-5 in parallel." AMO = an autonomous,
agentic SEO orchestration layer that solves both. **5 phases:**
- **Faz 0 — Foundation:** bind each Claude session to one project (N windows = N projects, correct attribution). ✅
- **Faz 1 — Orchestrator:** "do monthly maintenance for alpha" → an ordered Python pipeline runs every required
  step with **verification of each step's OUTPUT** (the design reframe), reusing existing skills. ✅
- **Faz 2 — Denetçi + gates + oracle:** a Stop-hook auditor forces missing steps; PreToolUse gates hard-block
  irreversible actions (Indexing/publish/push) unless consent; a correctness oracle measures the ≤5%. ✅
- **Faz 3 — Replicate** the pattern to more workflows + ship the two "mastery" lints. **Replication line ✅
  (audit/setup/content + the §4 lints + oracle generalization + the drift-F rule); 3 governance/consolidation
  items remain (see §9).**
- **Faz 4 — Portfolio fan-out + cost ceiling + optional scheduler (default OFF).** **NEXT after Faz-3 remainder.**

**Build philosophy = Path A (Süleyman-chosen):** hard-coded ordered sequences first; NO general DAG engine /
auto-derived capability graph. Faz 3 VINDICATED this — two distinct driver SHAPES emerged (data-driver +
artifact-driver, §7), proving a single universal engine would over-abstract. Spec §3-§5 is canonical.

**Honest scope (spec §11):** ≤5% error holds for **structured** ingestion workflows (verifiable by code via the
identity+content gate + the oracle). **Analysis** steps (aggregate/filter) and **content** steps (blog quality)
are `model_attested` — orchestration guarantees they RAN + produced an artifact + passed their deterministic
gate (oracle reconcile / AI-disclosure), NOT that the result is "good." Don't conflate quality with structure.

**This design was adversarially hardened** (9-agent review, workflow `wf_527271b3-931`, 51 findings) — the spec
incorporates all must-fixes. Don't re-litigate settled decisions; see D1-D16 in MANAGER.md.

---

## 2. The per-batch loop YOU run

1. **Author** a self-contained worker prompt → save as `docs/superpowers/plans/amo/batch-XX-WORKER-PROMPT.md`
   AND give Süleyman the fenced ```text block to paste.
2. Süleyman pastes it to a fresh Opus-4.8 1M worker, relays the REPORT back to you.
3. **VERIFY — never trust blindly:** run the full suite yourself
   (`PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`),
   confirm `passed >= baseline` + `0 failed`; `git status --short` (scope = ONLY the batch's files); `git diff`
   the risky bits (security, public contracts, the spine, any out-of-scope migration); READ new
   security-sensitive code line-by-line; INDEPENDENTLY re-derive the worker's key claims when feasible (e.g. 3a:
   I ran my own detector, not the worker's, to confirm the gap set). Confirm READ-ONLY claims by grep.
4. If a worker added a `commands/*.md` or `schemas/*.json` → **apply the count-guard bumps yourself** (D10).
   If a worker added a drift-check **F-rule** → **apply the invariant-count cascade yourself** (D16, §6).
5. **Green + clean → commit + push:** `git add <only the batch's files>` → conventional message
   (`feat(...)`/`docs:`) ending `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` →
   `git push origin main`. (3-commit pattern per batch: `docs:` worker prompt · `feat:` the work · `docs:` closeout.)
6. Update `MANAGER.md` (batch → ✅ DONE, the banner, any new decision) + memory `project_amo_initiative.md`.
   Author the next batch.

## 3. Worker-prompt recipe (every prompt has these sections)

`HARD RULES` (verbatim: **NO Task/Agent tools — they FAIL here, "Prompt is too long"**; NO git; baseline-first
with the pytest command above + record N; TDD RED-first; immutability/no-debug-prints/functions<50 lines;
**scope-lock** — create/modify ONLY named files, anything else → STOP+report; no-commit, manager commits) ·
`WHY` · `CONFIRMED FACTS` (so the worker doesn't re-derive — inline the real API; VERIFY signatures yourself
first, e.g. `.verdict`/`.has_red` are `@property` not methods) · `ORIENT` (exact files to read) · `SCOPE` (the
only files to touch) · `SPEC` (precise, behavior-preserving) · `TDD` (the cases) · `METHOD` · `DURUR` (when to
STOP + report) · `REPORT` (what to print). Workers have 1M context → inline full file contents + bigger scope.

## 4. Standing authorizations (Süleyman, 2026-06-05/06/08 — do NOT re-ask)

- Manager **verifies → commits → pushes** every green+verified batch without per-batch approval.
- Süleyman delegates ALL non-critical decisions ("EN KRİTİK: ben karar veririm, sadece kritik onay alırım,
  brief'i direkt sun"). Only surface genuinely critical/irreversible choices, or a real design fork (e.g. the
  lint-2 correlation A/B, §9). For a structurally-novel batch, present the design + get a nod before authoring.
- A worker MAY migrate out-of-scope test/guard files when a scoped change unavoidably breaks them — you verify
  the migration **preserves/strengthens** the contract, never weakens it.
- Count-guard manifest bumps + the invariant-count cascade are the **manager's** job (workers surface, you apply).
- **Max-effort 1M workers (2026-06-08):** size batches UP to the worker's capacity (richer, fully-inlined,
  bigger scope) — but still split on genuinely distinct concerns (3-gov was SPLIT into driftF/secrets/lint2).

## 5. Accelerators

- **Bigger batches:** with 1M workers, merge cohesive single-concern work; split only on a hard dependency (a
  schema/contract must freeze before its consumer) or genuinely distinct concerns/subsystems.
- **Parallel worker windows:** dispatch FILE-DISJOINT batches in 2-3 windows at once; verify each independently.
  (Süleyman has run serial this whole Faz-3; he chooses tempo per batch.)

## 6. Recurring gotchas (these bit prior batches — pre-warn workers / apply yourself)

- **D10 count-consistency immune system:** adding a `commands/*.md` or `schemas/*.json` trips
  `tests/docs/test_count_consistency.py` (counts in plugin.json + marketplace.json) AND
  `tests/schemas/test_json_schema_draft_consistency.py`. Manager bumps all three. (Editing an EXISTING command/
  schema, or adding a rule INSIDE cross-sheet-invariants.json, does NOT change the FILE counts.)
- **D16(a) Standalone-load import trap (3-gov-driftF):** `scripts/validation/validate_invariants.py` is loaded
  STANDALONE by the hook `scripts/hooks/check_excel_writer.py` via `spec_from_file_location` (repo root NOT on
  `sys.path`). Adding a top-level `from scripts...` import → `ModuleNotFoundError` during the hook's load → the
  hook **fails OPEN → a RED workbook slips through** (the invariant gate silently disabled). FIX = a `sys.path`
  repo-root bootstrap BEFORE the package imports (mirror `outward_action_gate.py`). ANY batch adding a top-level
  scripts-import to a standalone-loaded module must do this.
- **D16(b) Invariant-count cascade (2nd immune system, parallel to D10):** adding a drift-check F-rule bumps
  implemented (`len(_RULE_FUNCTIONS)`), declared (`len(cross-sheet-invariants.rules)`), and tier counts —
  `tests/docs/test_count_consistency.py` pins all three + cites them across ~8 files (drift-check SKILL.md
  narrative/tier-table/rule-table + a new `## F-NN` deep-dive section, sibling SKILL.md, GLOSSARY,
  validate_invariants docstring, the cross-sheet-invariants.json title/desc, test_drift_check's `len(checks)`).
  The MANAGER applies this cascade (the worker scope-locks + surfaces the exact edit set). Beware "false-friend"
  24s (schema-FILE count, SF-orchestrator literals, historical docs) — do NOT bump those.
- **1d.1 trap (CLI output filename ≠ sheet name):** a transform CLI may write `{X}.json` where X ≠ the sheet
  (gsc_pull → `gsc_performance.json`; schema_audit → `schema_audit.json`). The driver's loader must key by an
  EXPLICIT per-step `output_file`, NOT `{sheet}.json`. Lock it with a CLI-INTEGRATION test that runs each REAL
  CLI on a minimal synthetic input + asserts the output filename (caught the schema_audit case pre-authoring).
- **Snapshot-vs-append (replace-safety — DATA-LOSS-critical):** `committer.commit` = `transaction.replace`
  (whole-block, from `data_start_row`) → correct ONLY for SNAPSHOT sheets (regenerate-the-whole-sheet each run).
  Before relocating a skill's `transaction.append` → `committer.commit`, VERIFY the sheet is a snapshot:
  (a) no date/run column that means ACCUMULATE; (b) a SINGLE writer (grep allowed_writers + who writes it);
  (c) the transform is idempotent / re-numbers `id` 1..N (you cannot append a resetting-PK sheet without dup).
  `new_content_plan` HAS a `created_date` column but is a regenerate-snapshot (verified single-writer + id-reset)
  — a column that *looks* like accumulate is not dispositive. A wrong replace wipes history.
- **Workflow SHAPE divergence:** NOT every workflow fits the data-pipeline pattern. `content-pipeline` produces
  ARTIFACTS (blog HTML), not sheet rows → an ARTIFACT-driver (verify artifact-exists + the content_validator
  AI-disclosure gate), reusing ONLY `coverage`/`remediation`, NOT `run_step`/`verify_raw_drop`/`committer`. Don't
  force a new workflow into run_step — orient on what it PRODUCES first (sheet rows = data; files = artifact).
- **Invocation-precision (3a lint #1):** a body-scan lint must distinguish a CALL from a prose mention / a
  variable dispatch. Use anchored matchers (`mcp__s__t(`, `call_tool("literal")`, known wrapper methods) + a
  read-verb exclusion → ZERO false-positives against the real skills.
- **Hook-script classification:** a NEW wired hook script → add to `RUNTIME_HOOK_SCRIPTS` + `scripts/hooks/README.md`
  or `test_hook_scripts_runtime_vs_ci.py` fails. (A `scripts/validation/` or `scripts/orchestration/` module is
  NOT a hook → no entry.)
- **events.jsonl is in-place-rewritten** (no separate lockfile) → mutations IN-PLACE, **never os.replace** (inode
  swap = data loss). Marker files (active.json, session markers, coverage records) DO use os.replace (mutable
  pointers). consent.jsonl is an append-only LOG (O_APPEND). Know the difference.
- **Scope-locked commit:** `git add <only THIS batch's files>` — NEVER `git add -A`.
- **Verify the real API before specifying it:** the 3d worker caught that `ContentReport.verdict`/`has_red` are
  `@property` (no parens); a `verdict()` shorthand TypeErrors. Read the source; don't spec from memory.
- **Recurring secret trap:** never quote a watched secret token in a non-excluded doc (re-trips `check_secrets`);
  run the FULL suite even after a "docs-only" commit.

## 7. Key technical facts you must hold (verified, don't re-derive)

### 7.1 The orchestrator = a shared spine + TWO driver SHAPES
- **Shared spine (FROZEN — import, never edit):** `scripts/orchestration/`
  - `run_step.py`: `StepSpec` (frozen dataclass: name, raw_path, sheet, transform, verification_class="code_verified",
    required, expected_site_url=None, expected_window=None, expected_tool=None, observed_mcp=()) +
    `run_step(spec, *, run_id, project_slug, workspace_root, workbook_path, now_epoch, max_age_seconds=86400,
    schema_path=None, commit_fn=committer.commit)` → verify_raw_drop → transform → committer.commit → silent_skip
    gate → coverage step. `run_sequence(...)` for an ordered list.
  - `verify.py`: `verify_raw_drop(raw_path, *, expected_run_id, expected_slug, now_epoch, expected_site_url=None,
    expected_window=None, expected_tool=None, ...)` — checks run_id, slug, then site_url/window/tool ONLY when the
    spec pins them (None = don't pin), then freshness (mtime/fetched_at vs 24h), then truncation
    (declared_count==len(rows)). Stable reason codes; never raises. `silent_skip_exceeds(input, scored, 0.5)`.
  - `committer.py`: `commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None,
    writer="orchestrator")` → wraps `transaction.replace` (whole-block, idempotent). Pass `writer="<skill>"`.
  - `coverage.py`: `build_step(name, verification_class, status, observed_mcp=[], input_count=?, scored_count=?)`
    (status ∈ {pending,running,satisfied,missing,failed,skipped}), `derive_verdict(steps)` (verdict ∈
    {pass,incomplete,paused,failed}; treats model_attested as SOFT, required_satisfied = all code_verified
    satisfied), `build_record`, `write_coverage`, `coverage_path`. Schema `schemas/coverage.schema.json` (1a, frozen).
  - `remediation.py`: `remediation(record, *, slug, workflow)` + `render(...)` (Turkish one-line `/pseo-run …
    --resume` fix surface, model-visible additionalContext).
- **DATA-driver shape** (3 workflows: `monthly_maintenance.py`, `audit_suite.py`, `new_project_setup.py`): a
  module `STEPS` tuple {name, sheet, output_file, writer, tool, site_url, verification_class} + `inbox_path` +
  `output_path` (keyed by `output_file`!) + `_output_loader` + `build_steps` + `run` + CLI. The MODEL makes the
  MCP call → drops provenance-stamped raw JSON to `_state/inbox/{run_id}/{step}.json` → runs the EXISTING
  transform CLI to `_state/transform/{run_id}/{output_file}`; the driver verifies + commits sheet rows + records
  coverage. **D15 dispatch is SHARED:** `audit_suite._run_one` (code_verified→run_step / model_attested→
  `_run_attested_step`) + `_run_attested_step` are workflow-agnostic; `new_project_setup` IMPORTS them.
- **ARTIFACT-driver shape** (1 workflow: `content_pipeline.py`): produces blog HTML artifacts, NOT sheet rows.
  `verify_artifact(path, *, is_html)` = missing (absent) / failed (is_html AND
  `content_validator.validate_content(html).has_red`) / satisfied. Reuses ONLY `coverage` + `remediation` +
  `content_validator` — NO run_step/verify/committer. All steps model_attested + the COMPLETION GUARD.
- **D15 attested-path + completion guard:** `run_step` applies `silent_skip` UNCONDITIONALLY and `derive_verdict`
  fails on any failed step → an ANALYSIS step (output ≪ input by design) would FALSE-FAIL. Resolution (no spine
  edit): dispatch by `verification_class` — code_verified → run_step (silent_skip enforced); model_attested →
  `_run_attested_step` (verify_raw_drop STILL hard-gates identity+content+freshness; only the silent_skip COUNT
  is advisory). PLUS, since derive_verdict treats attested as SOFT, the driver's `run()` downgrades
  `pass → incomplete` unless EVERY step is satisfied (load-bearing for all-attested workflows like setup/content).

### 7.2 The §4 mastery lints + the drift rule + the oracle
- **Lint #1 `body ⊆ declared` (3a, DONE):** `scripts/validation/skill_mcp_usage.py`
  (`split_frontmatter_body`/`declared_tools`/`invoked_tools`/`body_not_declared`; invocation-precise) +
  `tests/schemas/test_skill_body_mcp_subset_declared.py`. Complements the EXISTING `declared ⊆ registry`
  (`tests/schemas/test_skill_mcp_tools_exist_in_registry.py` + `mcp-tool-registry.json`). 3a fixed
  `sf__sf_load_crawl` (was invoked but absent from registry) + declared the SF tools in 4 skills.
- **Drift-F rule `declared-outward-MCP ⊆ gate` (3-gov-driftF, DONE):** `check_F_27` in
  `scripts/validation/validate_invariants.py` (category `csr_mcp`, HIGH) — imports the 2b gate's `_MCP_SUBMIT_TOOL`
  (no drift) + reuses `skill_mcp_usage.declared_tools`; curated `_OUTWARD_MCP_TOOLS` FAIL-HIGH + an outward-verb/
  read-exclusion AMBER tripwire. 4-way registered (function + `_RULE_FUNCTIONS` + `__all__` +
  cross-sheet-invariants.json), guarded by `tests/schemas/test_cross_sheet_invariants_sync.py`.
- **Lint #2 `observed ⊆ declared` (3-gov-lint2, REMAINING — NEEDS A DESIGN, §9):** runtime reconciliation;
  blocked on the events↔workflow correlation impedance (see §9).
- **The oracle (3-oracle, DONE):** `scripts/reporting/orchestration_metrics.py` — now WORKFLOW-AGNOSTIC: resolves
  a run's workflow by its (disjoint) step-names, reconciles committed master.xlsx rows vs the transform OUTPUT
  per run_id (R1-R5; `fake_green` headline), incl. attested sheet-writing steps; READ-ONLY; new
  `unresolved_workflow` verdict. It is the independent ≤5% backstop for the DATA-driver workflows' attested
  steps. (content-pipeline's artifact steps aren't sheet-based → not oracle-reconciled; their gate is
  content_validator.)
- **The F-rule framework:** `validate_invariants.py` (check_F_NN; highest = **F-27**) + `_RULE_FUNCTIONS` +
  `__all__` + `schemas/cross-sheet-invariants.json` `rules` + `schemas/consistency-report.schema.json` 8-category
  enum (`csr_mcp` valid) + `tests/schemas/test_cross_sheet_invariants_sync.py` (the 4-way sync) + per-rule tests
  `tests/scripts/test_validate_invariants_F*.py`.
- **`/pseo-run` command** (`commands/pseo-run.md`): dispatches `monthly` (Bölüm 2-7) / `audit` (Bölüm 8) /
  `setup` (Bölüm 9) / `content` (Bölüm 10); any other → DURUR. Each workflow adds a Bölüm; the others stay
  byte-unchanged. `tests/commands/test_allowed_tools_match_shell.py` checks only Bash programs (not MCP tools).

### 7.3 Foundational facts (Faz 0-2)
- **Binding key = the Claude session UUID** (D9), identical from hook stdin `session_id` and command env
  `$CLAUDE_CODE_SESSION_ID`. Engine root = `$CLAUDE_PLUGIN_ROOT`. Workspace root persisted to
  `~/.config/pseo/config.json`. Marker = `<workspace>/shared/sessions/<uuid>.json`. Primitive:
  `scripts/state/session_binding.py`.
- **Corrected facts (don't repeat v2 errors):** resumable **`paused`** state exists (use it for external-failure,
  no `blocked`); `failure_reason.external` bool added (no new codes); `event_type` is a closed exactly-12 enum
  (coverage → `_state/coverage/`, not a new event_type); `ACTIVE_PROJECTS_MAX=12`.
- **Phase-2 primitives (ALL shipped — reuse, don't rebuild):** consent ledger
  `scripts/state/consent_ledger.py` (O_APPEND+flock, hash-chained, `has_session_consent`, schema
  `consent.schema.json` 6-action enum, `/pseo-approve`; **D13 consent is PER-SESSION**); gates
  `scripts/hooks/outward_action_gate.py` (default-DENY 5 outward actions; `_MCP_SUBMIT_TOOL =
  "mcp__gsc__submit_sitemap"` is the only gated MCP tool) + `ai_disclosure_rescan.py` (PostToolUse quarantine;
  REUSES `content_validator` + `validate_content_write.is_content_html_path`); denetçi `scripts/hooks/denetci.py`
  (Stop hook); oracle `orchestration_metrics.py` (§7.2). content gate: `scripts/validation/content_validator.py`
  `validate_content(html, *, profile=None) -> ContentReport` (`.verdict`/`.has_red` are `@property`).

## 8. How to work with Süleyman (the operator)

Non-coder SEO expert. **Simple Turkish.** Format: ★ Insight blocks, tables, "2-3 options + your recommendation."
He decides fast and delegates non-critical things — present a direct brief, don't over-ask. Evidence-based;
values a final-check / "eksiklikler var mı?" ritual. He runs the workers (pastes prompts, relays reports) and
tests live in his environments. Public docs/READMEs = English; chat = Turkish. His hard constraints are
absolute: Indexing-API submit needs explicit consent (enforced by 2b); "written by AI" must NEVER appear in
visible HTML (enforced by 2e + content_validator + now the content-pipeline workflow gate); append-only state;
plugin-agnostic (no CMS/site specifics in the engine). See the `feedback_*` memory files.

## 9. Remaining work — UPDATED 2026-06-08 (Faz 0+1+2 ✅ + Faz-3 REPLICATION LINE ✅)

> **A fresh manager taking over starts here.** Read MANAGER.md's banners + the batch table (0a-3d + 3-gov-secrets
> + 3-gov-lint2 + 3-O4 + 4a + 4b all ✅) + D1-D17. Suite is at **2241 pass / 7 skip / 0 fail** (HEAD on
> origin/main, working tree clean, all pushed). The orchestrator drives **4 workflows** (monthly/audit/setup/
> content) + the portfolio sweep (`/pseo-run-portfolio`). Do NOT re-do anything below the line. **Faz 3 is
> COMPLETE; Faz 4 has 4a (cost ledger) + 4b (sweep+kill-switch) done — pick up at 4c (see the §9-NEW block).**

- **Faz 0 ✅** (`09674c5`): session-id binding + audit attribution + parallel-write safety.
- **Faz 1 ✅** (`3b9d87e`+`1fa70d3`): orchestrator spine + `monthly-maintenance` + `/pseo-run` + remediation.
- **Faz 2 ✅** (`95bc421`): consent ledger + outward-action gate + AI-disclosure rescan + denetçi + oracle.
- **Faz 3 replication line ✅ (this session, 6 batches, suite 2036→2175):**
  - **3a** (`c497444`): §4 lint #1 `body⊆declared` + `sf_load_crawl` registry fix.
  - **3b** (`64fdb7d`): `audit` workflow (DATA-driver; D15 attested-path born — 3 of 4 steps attested).
  - **3-oracle** (`9ee9346`): oracle made workflow-agnostic (backstops attested data-steps).
  - **3-gov-driftF** (`80bc897`): F-27 drift rule + the D16 lessons + the invariant-count cascade.
  - **3c** (`b239ac9`): `setup` workflow (DATA-driver; sequential-dependent; imports the D15 dispatch).
  - **3d** (`5a5b745`): `content` workflow (the ARTIFACT-driver shape; AI-disclosure gate at workflow level).
- **⏳ LIVE-ACCEPTANCE deferred to the END (D11) — NOT a per-phase gate.** After Faz 3 + Faz 4, ONE comprehensive
  all-phases live run (`/pseo-run monthly <slug>` on a real GSC-verified project + observe gate/denetçi/consent
  in all 3 environments). The hard "no autonomy un-proven" rule (Faz-4 scheduler) is met by that end run. Do NOT
  block on a live test now. (Memory `project_amo_live_acceptance_deferred`; recommended project: Vento — GSC confirmed.)

### ───────── §9-NEW (2026-06-08): Faz 3 ✅ DONE, Faz 4 4a+4b ✅ DONE — YOU PICK UP AT 4c ─────────

> **Done since this doc was first written (all ✅ pushed, manager-verified, see MANAGER.md rows + memory
> `project_amo_initiative`):** 3-gov-secrets (`--scan-stdin`) · 3-gov-lint2 **B′** (static workflow-tool ⊆
> skill-declared ⊆ registry — runtime Option B was REFUTED on real data, D17) · 3-O4 (shared `workflow_driver`
> extracted, git-stash equivalence proof) · **🎉 Faz 3 COMPLETE** · 4a (`scripts/state/cost_ledger.py` +
> `cost-ledger.schema.json` — atomic reserve-then-confirm under a hard ceiling, no-overspend proven) · 4b
> (`scripts/state/project_lock.py` non-blocking lock + `scripts/orchestration/portfolio_runner.py` sweep +
> `commands/pseo-run-portfolio.md` — sequential sweep [Süleyman Option A] + budget kill-switch, no-leak proven).
>
> **YOU PICK UP AT Faz 4 batch 4c**, then 4d, 4e, D11:
> - **4c — `/pseo-status --portfolio`:** a triage table across the portfolio (run_id, status, missing_steps,
>   external vs internal) reading each project's coverage record + the 4a ledger `usage`. Mirror the existing
>   `commands/pseo-status.md` + the reporting scripts. NEW command → D10 command bump (manager applies).
> - **4d — scheduler (default OFF):** explicit per-cadence consent + projected daily cost shown before arming;
>   iterates the ACTUAL on-disk project count (not "3-5"). ⚠️ **CARRY from 4b:** the scheduler MUST gate
>   arming on ALL ceilings being set in `shared/cost-ceilings.json` (O5 — fail-closed for autonomy; 4b's
>   unset-ceiling→∞ is fine for MANUAL `/pseo-run-portfolio` but NOT for an armed schedule). This is the
>   autonomy-arming batch — the hard "no autonomy un-proven" rule is met only by the D11 end run.
> - **4e — recovery runbook** (doc) + cross-cutting consolidation (ACTIVE_PROJECTS_MAX 1-module, self-upgrade
>   versioning).
> - **D11 — comprehensive live-acceptance** (Süleyman, deferred to the very end): ONE all-phases live run on a
>   real GSC-verified project (recommended: Vento) across all 3 environments — observe gate/denetçi/consent +
>   a portfolio sweep + the kill-switch. This CLOSES the AMO build.
>
> The detailed historical items below (3-gov-secrets/lint2/O4 + the Faz-4 bullet) are now DONE/superseded —
> kept for context (the Faz-4 bullet still describes 4c/4d/4e accurately).

### ───────── (historical — these Faz-3 items are now ✅ DONE) ─────────

- **3-gov-secrets (secret-bytes scan; self-contained, low-risk):** enhance `scripts/security/check_secrets.sh`
  to scan the LITERAL pending bytes incl. gitignored targets, not just git-enumerated files. Current behavior:
  scans tracked + untracked-not-ignored (`git diff --name-only` ∪ `git ls-files --others --exclude-standard`),
  and a gitignored local `.env` is WARN-only by design (do NOT change that to FAIL — Süleyman keeps local
  secrets gitignored). The gap: a secret in bytes git enumeration misses. Carry the recurring secret trap (never
  quote a watched token in a non-excluded doc). There are TWO copies (`scripts/security/check_secrets.sh` 292-line
  full + `scripts/ci/check_secrets.sh` 19-line CI). Read both + `tests/...check_secrets...` before authoring.
- **3-gov-lint2 (§4 lint #2 `observed⊆declared`; ⚠️ NEEDS A CORRELATION DESIGN FIRST — present A/B to Süleyman):**
  the lint asserts, per run, that the workflow's declared-required MCP tools were actually observed. **Impedance
  (manager-found):** `events.jsonl` MCP-call rows are `provenance` events with an INTEGER `run_id`; a workflow run
  is identified by a STRING `workflow_run_id` on separate `workflow` events (ADR-020 deliberate id-space split) —
  the provenance MCP rows do NOT carry `workflow_run_id`, so you can't cleanly attribute "which MCP calls belong
  to this run." Options: **(A)** stamp the workflow_run_id (or the int provenance run_id) onto the MCP-call
  provenance event the model drops during a workflow step — a `/pseo-run` recipe convention + maybe an additive
  `events.schema.json` field (touches the recipe/schema; clean but bigger); **(B)** reframe as PER-PROJECT (assert
  the project's events.jsonl shows each workflow's declared-required tools observed ≥ once) — weaker but
  self-contained. The declared-required set = the workflow's `STEPS[].tool` (the same registry the oracle uses;
  monthly/audit/setup step-names are disjoint). `observed-but-not-declared` = AMBER feeding lint #1. **Decide A
  vs B with Süleyman before authoring.**
- **3-O4 light-promote (consolidation; refactor of shipped code — careful QA):** the spec O4 decision gate is
  RESOLVED by Faz 3's evidence — two driver SHAPES, NOT one universal engine (Path A vindicated). The earned move
  is a LIGHT promote: extract the shared DATA-driver (`_run_one` + `_run_attested_step` + `build_steps`/
  `inbox_path`/`output_path`/`_output_loader` + the completion-guard'd `run` + the CLI boilerplate) into a shared
  `scripts/orchestration/workflow_driver.py` that monthly/audit/setup all use (audit+setup already share
  `_run_one` via cross-driver import — clean that coupling up). `content_pipeline` STAYS a separate artifact-driver
  (shares only `coverage`). The full declarative engine + auto-graph stays DEFERRED. ⚠️ This edits the FROZEN
  spine-adjacent area + 3 shipped drivers → the worker must keep all 3 workflows + their tests byte-green
  (behaviour-preserving refactor); higher-risk than a fresh batch — verify hard. Optional (Süleyman may skip it
  as tech-debt-paydown vs feature).
- **Faz 4 (after the Faz-3 remainder):** `/pseo-run-portfolio` cross-project fan-out (disjoint per-project locks)
  + a portfolio cost/quota ledger under `shared/` (atomic reserve-then-confirm; GSC quota, **DFS credits —
  carries `dfs_oversized` from 2b's deferral**, image spend) + a hard global ceiling + kill-switch (ceiling hit →
  runs go `paused`, not silent degrade) + `/pseo-status --portfolio` triage table + a written recovery runbook;
  scheduler **default OFF**, explicit per-cadence consent, projected daily cost shown before arming; per-step
  mid-job budget preflight. Spec §7 Phase 4 + §8. THEN the D11 comprehensive live-acceptance closes the build.
- **Cross-cutting (carry through):** the e2e stub-harness pattern (every driver e2e test); self-upgrade
  versioning consolidation (coverage has optional `engine_version`); ACTIVE_PROJECTS_MAX 1-module consolidation.
  **Open (separate triage):** Codex ruthless-handoff audit 72/100 (`docs/audits/2026-06-05_...`, chipped).

**You have everything. Confirm your understanding to Süleyman in simple Turkish, then continue the loop. Suggested
order: 3-gov-secrets (low-risk, self-contained) → 3-gov-lint2 (after he picks A or B) → 3-O4 light-promote
(optional refactor) → Faz 4. But let Süleyman pick — present the 3 remaining Faz-3 items + your recommendation.**
