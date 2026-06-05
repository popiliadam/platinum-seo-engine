# AMO Batch 1b2 — Relocate Reference-Skill Writes into the Committer (WORKER PROMPT)

> **Manager note (not part of the prompt):** Batch 1b built the orchestrator-owned committer
> (`scripts/orchestration/committer.py::commit`, an idempotent `transaction.replace` wrapper). This batch
> points the 3 reference-workflow skills (gsc-pull, quick-wins, content-decay) at it, replacing their
> model-executed `transaction.append` calls. The manager confirmed with evidence that ALL 4 target sheets
> (`gsc_performance`, `quick_wins`, `opportunity`, `content_decay`) are window-delta SNAPSHOTS — none has a
> date/run column — so `append` is a latent duplicate-on-re-run bug (the known gsc_performance bug,
> generalized). `committer.commit` (replace) is the correct fix for all four. The skill tests pin the
> TRANSFORM + frontmatter + output_ref, NOT the write call (verified), so this is low-pin-risk — unlike the
> 1c hook migration. `committer.commit` still routes through `transaction.py`, so rules/excel-discipline is
> satisfied. No schema/command/hook added → NO D10 bump. Paste into a fresh Opus-4.8 1M session. (Run AFTER
> 1c is committed; serial.)

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 1b2 of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and
print the REPORT (the manager reviews + commits).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N is ~1872) BEFORE any change. END green, passed strictly >= N.
- TDD: write the FAILING contract test first, watch it fail, then make the SKILL.md edits to turn it green.
- House style: immutability; no debug prints; small functions. (Most of this batch is SKILL.md prose edits +
  one new test file.)
- Scope-lock: modify ONLY the 4 files in SCOPE. Anything else -> STOP + report.

WHY THIS BATCH (read carefully):
AMO's orchestrator owns ONE serialized committer so writes are idempotent (re-running a step never
duplicates rows). Batch 1b built it: `scripts/orchestration/committer.py::commit(...)` wraps
`transaction.replace` (clear the sheet's data block, then write — so re-import = refresh, not append). The 3
reference-workflow skills currently write their master.xlsx rows with `transaction.append` in model-executed
SKILL.md prose. Because every one of their target sheets is a SNAPSHOT (a recent-vs-previous window delta or
a current-window quick-win list — NONE has a date/run column to disambiguate runs), `append` silently
DUPLICATES rows on every re-run. This batch relocates those writes to `committer.commit` (replace),
fixing the duplicate bug on all 4 sheets AND aligning the standalone skill path with the orchestrator path.

CONFIRMED FACTS (manager-verified 2026-06-05 against the code/schema — do not re-derive):
- The committer: `scripts/orchestration/committer.py`:
    commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None, state_root=None,
           writer="orchestrator") -> WriteResult
  It calls `transaction.replace(workbook_path, sheet, rows, project_slug, ..., writer=writer)` and returns
  its WriteResult. It accepts + passes through `writer`, so you PRESERVE each skill's writer identity. It is
  idempotent by construction (replace clears+rewrites). It still routes through scripts/excel/transaction.py
  (atomic write + backup + schema validation + provenance), so rules/excel-discipline ("yalnızca
  transaction.py üzerinden") is SATISFIED — committer.commit is NOT a direct/openpyxl write.
- ALL 4 target sheets are SNAPSHOTS (master-excel.schema.json — NONE has a date/run/timestamp column):
  `gsc_performance` (url-keyed recent-vs-previous delta), `quick_wins` (current 30d), `opportunity`
  (current 30d), `content_decay` (url-keyed recent-vs-previous decay). So replace is the CORRECT semantics;
  append is the bug. (Do NOT add any append path — every one of these writes becomes replace.)
- The skill tests (`tests/skills/test_gsc_pull.py`, `test_quick_wins.py`, `test_content_decay.py`) assert the
  TRANSFORM output column-keys vs the schema + the SKILL.md FRONTMATTER + the `master.xlsx#<sheet>` output_ref
  anchor. They do NOT assert the `transaction.append`/write call, so swapping it does not break them. (Confirm
  this holds via baseline + your final run.)
- `handle.run_id` is in scope at the write step (the SKILL.md creates the run via workflow_runner.create_run
  earlier and uses handle.run_id throughout). Pass run_id=handle.run_id.
- This batch adds NO command/schema/hook → it trips NO count-guard (D10). Do NOT touch any manifest.

ORIENT FIRST (read, do not change yet):
- `scripts/orchestration/committer.py` (the commit signature you call) + `tests/orchestration/test_committer.py`
  (proves replace idempotency — your migration relies on it).
- The 3 write blocks you will edit (read each in full):
  * `skills/ingestion/gsc-pull/SKILL.md` Step 7 (~204-217): one transaction.append → gsc_performance.
  * `skills/discovery/quick-wins/SKILL.md` write step (~184-205): TWO transaction.append → quick_wins + opportunity.
  * `skills/discovery/content-decay/SKILL.md` Step (~249-267): one transaction.append → content_decay.
- `tests/skills/test_gsc_pull.py` (~160-270) to confirm it pins transform/frontmatter/output_ref, not the write.
- `rules/excel-discipline.md` (the "transaction.py only" rule committer.commit still satisfies).

SCOPE — modify ONLY these:
  EDIT skills/ingestion/gsc-pull/SKILL.md            (Step 7 write: transaction.append -> committer.commit)
  EDIT skills/discovery/quick-wins/SKILL.md          (both writes -> committer.commit)
  EDIT skills/discovery/content-decay/SKILL.md       (the write -> committer.commit)
  NEW  tests/skills/test_reference_skills_commit_via_committer.py   (the contract lock — see TDD)

SPEC — the SKILL.md edits (behavior-preserving except the append→replace dup fix). In each skill's write
block: change the import `from scripts.excel import transaction` → `from scripts.orchestration import
committer`, and rewrite each call:

  gsc-pull Step 7:
      committer.commit(
          workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
          sheet="gsc_performance",
          rows=gsc_performance_rows,
          run_id=handle.run_id,
          project_slug=project_slug,
          writer="gsc-pull",
      )
  quick-wins (TWO calls, preserve order quick_wins then opportunity):
      committer.commit(..., sheet="quick_wins",  rows=quick_wins_rows,  run_id=handle.run_id,
                       project_slug=project_slug, writer="quick-wins")
      committer.commit(..., sheet="opportunity", rows=opportunity_rows, run_id=handle.run_id,
                       project_slug=project_slug, writer="quick-wins")
  content-decay:
      committer.commit(..., sheet="content_decay", rows=content_decay_rows, run_id=handle.run_id,
                       project_slug=project_slug, writer="content-decay")

  ALSO update the surrounding PROSE so it stays accurate + truthful:
   - "Single/Two `transaction.append` call(s)" → "Single/Two idempotent `committer.commit` call(s) (replace —
     re-running refreshes the snapshot, never duplicates rows; routes through transaction.py: backup + lock +
     schema validation + provenance)".
   - content-decay's note "the transform module itself does NOT import `scripts.excel.transaction` — only the
     skill orchestrator layer does" → swap `scripts.excel.transaction` for the committer (the cross-module
     IMPORT discipline point still holds: the transform stays pure, only the orchestrator layer commits).
   - Do NOT change the skill FRONTMATTER (writes:/reads: anchors), the output_ref `master.xlsx#<sheet>`
     strings, the transform CLI invocation, the provenance Step (events_writer.append_provenance), or any
     other step. ONLY the write call + its immediate descriptive prose change.

TDD — tests/skills/test_reference_skills_commit_via_committer.py (write FIRST, watch the relevant asserts
fail against the unedited SKILL.md, then make the edits to go green):
  A parametrized test over the 3 (skill_path) that, for each reference-workflow skill, reads its SKILL.md and:
    1. asserts `"committer.commit(" in body` (the write now goes through the orchestrator committer);
    2. asserts `"transaction.append(" not in body` (no append → the snapshot dup bug cannot regress);
    3. asserts the expected sheet name(s) still appear (gsc_performance / quick_wins+opportunity /
       content_decay) so the relocation didn't drop a write.
  Add a short module docstring explaining WHY (snapshot sheets must commit idempotently via the
  orchestrator-owned committer, not append). Keep it robust: grep the file body; do not pin exact whitespace.

METHOD:
  1. Baseline pytest (record N ~1872).
  2. Write the new contract test (RED — committer.commit not yet present / transaction.append still present).
  3. Edit the 3 SKILL.md write blocks + prose (GREEN).
  4. Re-run the FULL suite; confirm passed >= N and 0 failed. Confirm the 3 skills' EXISTING tests
     (test_gsc_pull / test_quick_wins / test_content_decay) stay green (they pin transforms, not the write).
  5. `git status --short` = ONLY the 4 scoped files. No manifest/schema touched.
  6. @code-reviewer + @verifier inline.

DURUR (stop + report, do not work around):
  - A skill's write block turns out to write a sheet that is NOT a snapshot (it has a date/run column / is
    meant to accumulate) → STOP + report (do NOT convert that one to replace). [Manager checked all 4 = snapshot;
    report if you find evidence otherwise.]
  - An existing test DOES pin `transaction.append` / the write call in a skill body (so your swap breaks it) →
    report it as an out-of-scope contract migration for the manager to authorize (1c-style), do not touch it
    unprompted.
  - committer.commit's signature differs from the CONFIRMED FACTS → report the real signature.
  - rules/excel-discipline enforcement (check_excel_writer.py / a test) flags committer.commit as a
    non-transaction write → STOP + report (it should NOT, since committer wraps transaction.replace).

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line (passed/skipped/failed).
  - The 4 write calls migrated (skill → sheet → writer), confirming run_id=handle.run_id + writer preserved.
  - Confirmation all 4 are replace (no append path left) + the prose updated truthfully.
  - Proof the 3 skills' existing tests stayed green + the new contract-lock test passes (its 3 assertions).
  - Confirmation NO frontmatter/output_ref/transform/provenance step changed; only the write call + its prose.
  - `git status --short` = only the 4 scoped files; no D10/manifest touched.
  - Any DURUR / assumption / out-of-scope need.
```
