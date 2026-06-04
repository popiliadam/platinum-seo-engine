# Fresh-Session Kickoff Prompt — Codex Audit (14 Findings) Remediation

> Copy everything inside the fenced block below into a **new Claude Code session** opened in `/Users/apple/Documents/platinum-seo-engine`. It is self-contained.

```text
You are fixing 14 verified codex-audit findings in the Platinum SEO Engine (two-repo system).

CONTEXT
- Engine repo (code/docs/schemas/hooks/skills):   /Users/apple/Documents/platinum-seo-engine
- Workspace repo (live project data):             /Users/apple/Documents/platinum-seo-workspace
- All 14 findings were verified on 2026-06-04 against real file content + live validator output (5 parallel verification agents). They are REAL — do not re-litigate whether they exist; verify only the few open details flagged in the plan before each fix.

YOUR PLAN (follow it task-by-task; it has exact files, line numbers, full test code, and commit messages):
  docs/superpowers/plans/2026-06-04-codex-audit-14-findings-remediation.md

Supporting docs (read for background, do NOT treat as the task list):
  AUDIT_FINDINGS_FOR_CLAUDE_CODE.md   (broader 2026-06-03 audit; the plan's Appendix maps the overlap)

HOW TO WORK
1. Use the superpowers:executing-plans skill (or superpowers:subagent-driven-development) to run the plan.
2. The plan is batched A–F. Batches A–E are ENGINE (test-first / TDD). Batch F is WORKSPACE data.
   CRITICAL: never mix engine code changes and workspace data changes in the same commit.
3. TDD for every engine fix: write the regression test FIRST, watch it fail, fix, watch it pass, commit. The
   whole point of the audit is "add a test per drift class so the mismatch cannot return."
4. Baseline before touching anything:
     cd /Users/apple/Documents/platinum-seo-engine
     git status --short        # leave the pre-existing uncommitted files alone; do NOT revert unrelated changes
     PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest --tb=short -q
   Expected baseline: 1449 passed, 8 skipped. Every batch must keep it green + add the new tests.
5. Run each batch's test gate after the batch, and the Final Verification section at the end.

CONSTRAINTS (from the user's standing rules)
- ASK before any git commit/push/checkout/reset/merge/rebase, any rm/delete, and before editing workspace .xlsx
  outside the sanctioned writer (scripts/excel/transaction.py). Read-only git (status/log/diff) is fine.
- The workspace is LIVE runtime state. Back up any master.xlsx before editing (cp master.xlsx master.xlsx.bak.<date>).
  Do not hand-edit append-only .jsonl event logs.
- Immutability / small-files / no-console-log / no-hardcoded-values coding rules apply (see ~/.claude/rules).
- Report outcomes honestly with real command output. If a test won't fail first, stop and investigate — don't fake red.

FOUR DECISIONS need the user (Süleyman) — each has a recommended default in the plan's "Decision Points" table.
Apply the default and proceed UNLESS he overrides:
  D-1: which slug becomes the active marker (finding 1)            -> default: a healthy slug he names; fix demo-construction data regardless
  D-2: demo-agency run_id files — rename vs relax schema (finding 2)   -> default: rename the 2 files
  D-3: marketplace "20" vs README "21" schemas (finding 13)        -> default: marketplace -> "21"
  D-4: excel-writer guard hardening (finding 14)                   -> default: keep advisory + add invariant re-check gate

START: read the plan file, present the batch order and the 4 decisions back to me in simple Turkish with your
recommended defaults, then begin Batch A (engine, contract/governance drift) once I confirm.
```

## What the fresh session will do, in order

| Batch | Repo | Findings | Output |
|-------|------|----------|--------|
| A | engine | 9, 4-schema, 13 | DFS const 2.8.10, language_code ISO pattern, marketplace count bound by test |
| B | engine | 5a–5d, 10a–10c | pseo-active safe, events_writer slug guard, command doc↔impl parity, reference linter |
| C | engine | 7, 8, 14 | secret scan covers untracked, append-only doc scoped, excel guard real gate |
| D | engine | 6, 12 | 26 racy `next_run_id()` purged from 22 skills, README config.yaml→project.config.json |
| E | engine | bonus (P0-02 already fixed) | `dump_workspace.py` reads root workbook + live drift verdict (no nulls) |
| F | workspace | 1, 2, 3, 4-data, 11 | active marker repoint, 4 RED workbooks normalized, 3 workflow JSONs fixed, language codes, CLAUDE.md |

~11 new regression tests; ~14 commits (engine + workspace separated).
