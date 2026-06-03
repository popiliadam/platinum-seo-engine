# Codex Audit Remediation — Manager / Worker Session System

This directory operates a **file-based manager/worker session system** to remediate the 31
verified Codex audit findings across multiple Claude Code sessions, using each session's full
1M-token context for exactly one phase.

## Why session-based (not subagents)

Subagent dispatch (`Agent` / `Workflow`) is **unavailable in this project**: every spawned
subagent inherits the session's ~500+ connected MCP tool schemas, which alone exceed the
subagent context budget → `"Prompt is too long"`. A **fresh top-level session** does not have
this problem (it gets the full 1M context). So:

- **Manager session** = holds the plan + state, dispatches one phase at a time, runs the QA gate.
- **Worker session** = a *new* Claude Code session that executes exactly one phase brief with
  zero prior context, then returns a structured Completion Report.
- **Glue** = the files in this directory (sessions don't share memory).

> If a future session runs with a smaller MCP config and subagents work, the manager MAY use
> `Workflow`/`Agent` instead of human-mediated handoff. The file system below is the robust
> default and works either way.

## Files (the contract)

| File | Owner | Purpose |
|------|-------|---------|
| `../2026-06-03-codex-audit-remediation-roadmap.md` | Manager | Master plan + verification record (the "what") |
| `MANAGER.md` (this file) | Manager | The protocol + brief/report templates (the "how") |
| `PROGRESS.md` | Manager | Live cross-session ledger (the "state") |
| `phase-N-<name>.md` | Manager | Detailed, self-contained worker brief per phase, written just-in-time |
| `reports/phase-N-report.md` | Worker | Worker's Completion Report pasted back (optional; or read from git) |

## Manager session loop

When you (re)start a **manager session**, do exactly this:

1. **Load state.** Read `PROGRESS.md`, the roadmap, and `git -C <engine> log --oneline -10`.
   Confirm the working tree is clean / on the expected branch.
2. **Resolve decision gates.** If the next phase has an unresolved decision (D1/D2/D3 in the
   roadmap Part C / `PROGRESS.md` Decisions table), get Süleyman's answer FIRST. Do not write a
   brief on an unconfirmed decision.
3. **Write the next worker brief** `phase-N-<name>.md` using the template below. It MUST be
   self-contained: a worker with zero context can execute it. Base it on the CURRENT tree state
   (re-read the relevant files — earlier phases may have changed them).
4. **Dispatch.** Tell Süleyman: "Open a NEW session, paste `phase-N-<name>.md` as the first
   message." (Verbatim copy-paste block, or a one-line `@`-mention of the file path.)
5. **Receive Completion Report.** Worker returns the structured report (template below).
   Süleyman pastes it back, or you read `git log`/`git diff` + the named test output.
6. **QA gate** (adapted from `~/.claude/rules/qa-loop.md`):
   - Run/confirm: full suite green (≥ baseline) + the phase's named regression tests + the
     phase's repro commands.
   - Review the diff for scope creep, mutation, mixed engine+workspace commits, secrets.
   - **PASS** → mark phase DONE in `PROGRESS.md` (record commits + verdict), go to step 1 for N+1.
   - **FAIL (attempt < 3)** → append specific feedback to the brief ("fix ONLY these"), re-dispatch.
   - **FAIL (attempt ≥ 3)** → ESCALATE: reassign / decompose the phase / revise approach / defer
     / accept-with-documented-limitation (record the choice in `PROGRESS.md`).
   - Conditional routing (qa-loop.md): SECURITY_FAIL / BUILD_FAIL / TYPE_FAIL / TEST_FAIL / STYLE_FAIL
     re-run ONLY the failed gate, not the whole loop.
7. **Update ledger** and stop, or continue to the next phase.

## Worker brief template

Each `phase-N-<name>.md` MUST contain these sections:

```
# Phase N — <Name> — Worker Brief
## 0. READ FIRST (worker onboarding)
- You are a fresh worker session. Do NOT explore the whole repo. This brief is complete.
- Repo: /Users/apple/Documents/platinum-seo-engine (engine). Workspace (if touched):
  /Users/apple/Documents/platinum-seo-workspace.
- Invoke superpowers:test-driven-development and follow it. Atomic commits. Branch: <branch>.
- Constraints: never commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md; never mix engine+workspace in
  one commit; do not push or touch main without explicit instruction; preserve unrelated changes.
## 1. GOAL (one sentence) + the findings this phase closes (IDs + one-line each)
## 2. EVIDENCE / current state (exact file:line citations from verification)
## 3. DECISIONS already made (e.g. D1 = registry matches code) — do not re-litigate
## 4. FILE MAP (create / modify / test — exact paths)
## 5. TASKS (bite-sized TDD: write failing test → run (fail) → implement → run (pass) → commit)
   - Include full code for every NEW test. Specify exact target for edits.
## 6. TEST GATE (exact commands + expected output; full-suite-green requirement)
## 7. OUT OF SCOPE (what NOT to touch — the other phases)
## 8. COMPLETION REPORT (fill in the template below and return it)
```

## Worker Completion Report template (worker returns this)

```
# Phase N Completion Report
- Branch: <name>  | Base: <sha>  | Head: <sha>
- Status: DONE | BLOCKED | PARTIAL
- Findings closed: [P0-0X, ...]  | deferred: [...]
- Commits (atomic): <sha> <msg> ; ...
- Tests: full suite = "<N passed, M skipped>" ; new tests added: [names] ; all green? Y/N
- Repro commands run + outputs: <paste>
- Deviations from brief / decisions taken: <none | ...>
- Blockers / questions for manager: <none | ...>
- Files changed (git diff --stat): <paste>
```

## Guardrails (apply to every phase)

1. Branch off `main` before any commits: `git checkout -b fix/codex-audit-phase-N`.
2. One phase → its own branch + atomic commits. **Never** mix engine and workspace repos in one commit.
3. Each phase ends green: full suite ≥ baseline (1449 passed / 8 skipped) + the phase's new tests.
4. Add a regression test per finding-class so the same drift cannot return.
5. Do not commit `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md` (handoff artifact).
6. Do not push or merge to `main` without Süleyman's explicit go.
7. Workspace migrations (Phase 2) run in the workspace repo, committed there separately.

## Phase index

See `PROGRESS.md` for live status. Phases (dependency-ordered): 1 Governance · 2 Workspace ·
3 Commands/Hooks · 4 Schema hardening · 5 State/write · 6 Docs/cleanup.
