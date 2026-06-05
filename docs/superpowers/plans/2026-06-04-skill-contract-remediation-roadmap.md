# Skill Contract Remediation — Manager Roadmap

**Source audit:** `docs/audits/2026-06-04-skill-contract-audit.md` + `.findings.json` (98 confirmed findings).
**Model:** This session = **manager**. Each batch runs in a **fresh worker session** (one paste from the worker-prompts doc). Worker reports back → manager reviews → commits → dispatches next batch.
**Worker prompts:** `docs/superpowers/plans/2026-06-04-skill-contract-worker-prompts.md` (B1–B6, self-contained).

---

## How the manager/worker loop works

```
For each batch B1..B6:
  1. Manager: confirm any batch decisions with Süleyman (defaults below); lock them into the worker prompt if overridden.
  2. Süleyman: open a FRESH session at repo root, paste the batch's worker prompt.
  3. Worker: TDD-fix every finding in scope → full pytest green → self Dev-QA → produce STRUCTURED REPORT → STOP (no commit).
  4. Süleyman: relay the worker's report to the manager (this session).
  5. Manager: review diff + tests; if PASS → commit atomically (ask Süleyman per git rule), update findings ledger, dispatch next batch. If FAIL → send targeted feedback to a fresh worker (retry ≤3, then escalate).
```

Workers **do not commit or push** — the manager controls commits so the tree stays coherent between batches and the git rule ("always ask before commit") is honored once per batch, not per file.

---

## Batch table

| Batch | Scope (skill category) | Findings | Severity | Decisions | Priority |
|---|---|---|---|---|---|
| **B1** | Reporting — portfolio suite (6 skills) | 19 | H6 M3 L10 | none | 🔴 **1st** — active runtime break (`active_projects` 8→12) |
| **B2** | Reporting — core (monitoring-weekly, monthly-report, weekly-summary) | 8 | H3 M4 L1 | 2 | 🔴 2nd — append-only safety (H18) + capability honesty |
| **B3** | Ingestion (5 skills) | 13 | H4 M6 L3 | 3 | 🟠 3rd — capability stubs |
| **B4** | Meta + Planning (9 skills) | 18 | H7 M2 L9 | 2 | 🟠 4th — cascade/trigger/capability |
| **B5** | Production + Publishing (7 skills) | 18 | H3 M3 L12 | 0 | 🟡 5th — events enum/kind + cross-refs |
| **B6** | Discovery + Governance (15 skills) + **deterministic guard test** | 22 | H1 M7 L14 | 2 | 🟡 6th — mixed + locks the whole class |

Total **98**. Batches are **file-disjoint** (verified: no file is touched by two categories), so they can even run in parallel if Süleyman prefers — but sequential with manager review between is recommended for the decision-bearing batches.

**Run-now-without-decisions:** B1 and B5 carry **zero** decision points — B1 (the urgent active break) can start immediately.

---

## Decision register (capability stubs — `5-capability` / unreachable contracts)

Each worker prompt bakes in the **recommended default**; the worker applies it unless Süleyman overrides. Principle: **honesty over feature-build** — if a fix would mean implementing a new runtime feature, prefer *honestly marking the stub* (Phase-14 deferral framing, which `brand-onboarding` already models) over scope-creeping a feature into a doc-fix. Add a tiny wrapper only where it makes a documented contract real cheaply.

| ID | Skill | Decision | **Recommended default** |
|---|---|---|---|
| B2-02 | monitoring-weekly | 5σ/drift/budget capabilities documented active but stubbed | **Honest stub-mark** — annotate frontmatter + Steps 4-5 + DURUR #5 "Wave-3 inline: placeholder; 5σ/cost deferred Phase 14+" |
| B2-06 | weekly-summary | `WorkspaceRootUnsetError` declared, never raised | **Make it real** — raise explicitly in `main()` when `workspace_root` unresolvable (small, makes DURUR #2 truthful) |
| B3-01 | sf-crawl-orchestrator | `render_template.render()` doesn't exist | **Add thin wrapper** `render(template_path, output_path, variables)->Path` to `scripts/reporting/render_template.py` (reusable; makes Step 8 real) |
| B3-02 | sf-import | `mcp__gsc__list_sitemaps` + DURUR #4 sitemap-xcheck not implemented | **Demote claim** — move tool to `optional`, mark DURUR #4 "Phase-X deferred" (cross-check is a feature, not a fix) |
| B3-03 | sf-import | `workflow_runner` run-shell declared, never used | **Rewrite SKILL.md** to describe actual no-run-shell behavior (don't wire runner just to satisfy prose) |
| B4-03 | init-project | cascade "auto-runner" + event mechanism doesn't exist | **Honest stub-mark** — Phase-14 deferral framing mirroring brand-onboarding |
| B4-04 | mark-done | claims `transaction.py` hard-guards `protected_columns` via `WriterScopeError` (false) | **Reword SKILL.md** to "advisory + skill-discipline, not a transaction.py hard guard"; **flag** "consider a real column-scope guard" as a future item (do NOT edit transaction.py here) |
| B6-01 | content-decay | `check_budget.preflight()` + `BudgetGateError` don't exist | **Add thin `preflight()` wrapper** to `scripts/budget/check_budget.py` returning the `{exceeded,...}` envelope (mirrors sibling skills' expectation) |
| B6-03 | glossary-audit | missing-term detection over-promises (~1,393 FPs) | **Reconcile prose** to the realistic detection rate; no algorithm change |

> Two more "decisions" are really doc-scoping, not stubs, and have obvious resolutions baked into their prompts: **B4-01** brand-onboarding STAGING-ONLY self-contradiction (scope the absolute to Steps 1-10, carve out Stage C as the sanctioned write) and **B5-04** indexing-ping `submit_sitemap` mislabel (correct the tool name; the consent gate itself is fine).

---

## Shared conventions (all batches)

- **TDD is mandatory for behavioral fixes.** Classify each finding: **DOC** (prose/cross-ref/status) → edit + keep guards green; **TEST** (rubber-stamp) → write the real assertion first (watch it fail against current code), then it passes; **CODE/CODE?** (transform/template/schema behavior) → write the failing regression test first, then fix. Never fake red.
- **Re-read before editing.** All line numbers are from the 2026-06-04 audit and **may have drifted**. Re-locate each finding's evidence in the live file before touching it. If a finding no longer reproduces, report it as `STALE` — do not invent a fix.
- **Scope guard.** A worker edits ONLY files belonging to its batch's skills (SKILL.md + that skill's scripts + paired tests + report templates). Touching another batch's files is forbidden. If a fix needs an out-of-scope file, **report it to the manager**, don't reach across.
- **Dev-QA loop** (per `~/.claude/rules/qa-loop.md`): after implementing, run `@code-reviewer` + `@verifier` (build/test/type). PASS → done; FAIL (<3) → fix only the cited issue, re-QA; FAIL (≥3) → escalate to manager.
- **Standing hard rules:** immutability (no mutation — new objects); append-only `_state/*.jsonl` (never hand-edit, never `os.replace`-swap the data file); **Google Indexing API `URL_UPDATED` requires Süleyman consent** (no autonomous external submit); **no visible "written by AI" disclosure** in any emitted HTML; no `console.log`/`print` debug; no hardcoded secrets; small files (<800L).
- **Baseline:** every worker runs the full suite first (`PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`), records the exact pass/skip count, and must end with **that baseline GREEN + its new tests added** (count strictly increases, 0 failures).
- **No commits by workers.** Implement → green → self-QA → structured report → STOP.

---

## Manager integration checklist (between batches)

1. Read the worker's structured report; open `git diff --stat` + spot-read the substantive hunks.
2. Confirm: scope respected (no out-of-scope files), pytest count increased & green, decisions match the register (or are justified), no hard-rule violation, no `STALE` finding silently "fixed".
3. Run the full suite myself once to confirm green.
4. Commit atomically (conventional `fix(skills):` / `test(skills):` / `docs(skills):`, Co-Authored-By trailer) — ask Süleyman first.
5. Update the findings ledger (mark batch's IDs resolved); note any escalations or deferred decisions.
6. Dispatch next batch (re-confirm its decisions with Süleyman).

## Done definition

All 98 findings resolved or explicitly deferred-with-rationale; the **deterministic enum/maxItems guard test** (authored in B6) is green and locks Themes 1 & 6 against regression; full suite green; a closing `RELEASE_NOTES`/audit-ledger entry records the sweep. Manager writes the final summary for Süleyman.
