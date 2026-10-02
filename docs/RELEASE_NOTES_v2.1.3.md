# Release Notes — v2.1.3 (2026-10-02)

**Theme:** *Stop corrupting ordinary writes.* Two small fixes: `events_writer` no
longer mistakes an `sk-` inside a word for an API key, and the task-id ratchet's pin
follows an owner decision that changed.

## Why this release exists

1. **Redaction mangled CRM ids.** Two rows written through `events_writer` on
   2026-10-02 carried a `crm_task_id` of the form `task-mts-<long id>`. The
   openai/anthropic value pattern matched the `sk-` at the end of `task-` and the
   whole value was persisted as `ta***REDACTED***`. Every normal write carrying a
   long `task-…` CRM id was affected; nothing secret was involved.
2. **The task-id ratchet was red on fixed data.** One project's 54 `MT-NNN` ids were
   renamed to `T-NNNN` on 2026-08-20, while `rules/master-task-id.md` still recorded
   the 2026-08-08 decision to grandfather them. The ratchet correctly failed with
   "0 non-conforming ids but pinned at 54". On 2026-10-02 the owner confirmed the
   rename as permanent; the rule requires the pin to drop in the same commit.

## Changes

- **Word-boundary for `sk-` redaction** (`1b34d67`): both `sk-` value patterns in
  `scripts/state/events_writer.py` now require that no letter or digit precedes
  `sk-`. Standalone `sk-`, `sk-proj-` and `sk-ant-` keys are still redacted after
  start-of-string, space, `=`, quotes, `:`, `(`, newline and `_`. +33 tests in
  `tests/scripts/test_events_writer_secret_redaction.py` (6 red against the previous
  pattern, including an end-to-end write of a `task-mts-…` id).
- **Task-id pin 54 → 0** (`2714f77`): `KNOWN_DRIFT` in
  `tests/state/test_master_task_id_convention.py` lowered for that project, and the
  decision change recorded with a dated line in `rules/master-task-id.md`.

## Known failures

None at release time. With the workspace bound (2026-10-02): 3600 passed, 0 failed,
35 skipped (live SF/GSC fixtures absent, opt-in smoke, `CLIENT_SLUG_PATTERN` unset,
version-sync waiting for the tag). This release removes the task-id drift failure
listed in v2.1.2; the `events.jsonl` schema-drift failures listed there are workspace
DATA and were cleared by a separate, owner-approved row clean-up, not by this release.

## Not measured by the gate

- The canonical scanner (`scripts/security/check_secrets.sh`, also used by the
  PreToolUse secret hook) has the same root cause in a narrower form: its `sk-`
  pattern has no left boundary, so `task-` followed by 20+ letters/digits with no
  inner hyphen is flagged. `task-mts-…` ids are not affected there. Left unchanged in
  this release by design; the redaction parity tests keep the two inventories in step
  by class, not by boundary behaviour.
- Rows already persisted as `ta***REDACTED***` are not repaired; the original value is
  not recoverable from the ledger.
- The ratchet only runs when `PSEO_WORKSPACE_ROOT` is bound; CI has no workspace.
