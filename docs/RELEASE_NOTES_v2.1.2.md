# Release Notes — v2.1.2 (2026-10-02)

**Theme:** *Close the `events.jsonl` write boundary for real.* v2.1.1 put
`check_events_writer.py` into the installed engine for the first time; a same-day
diagnosis showed the guard would not have stopped the drift it was meant to stop.

## Why this release exists

A read-only diagnosis of the 42 schema-invalid `events.jsonl` rows written between
2026-08-08 and 2026-08-24 (seven workspace projects) found two open paths:

1. **Inline Python writes were invisible to the guard.** 31 rows were appended with
   `open(<…>/_state/events.jsonl, 'a')` inside a `python3 - <<'PY'` heredoc or a
   `python3 -c` argument. `classify()` only recognised `>>`, `tee`, `sed -i` and `cp`.
   Replaying the last 45 days of real Bash commands, the same form was still in use on
   2026-09-09/10.
2. **`events_writer`'s `schema_path` override was test-only in name only.** 11 rows
   passed validation because an agent handed `append_event` a loosened copy of the
   schema. The docstring said "test-only"; nothing enforced it.

## Changes

- **Inline-Python write detection** (`f95f690`): `classify()` extracts heredoc bodies fed
  to python and `python -c` arguments, parses them with `ast`, and flags write-mode
  `open(…)`, `Path(…).open('a')`, `write_text`/`write_bytes` and write-flag `os.open`
  aimed at a live `events.jsonl` — resolving paths built from literals, variables,
  f-strings, `+`, `/`, `os.path.join` and `joinpath`, with a regex fallback for code that
  does not parse. The existing redirect/tee/sed/cp logic and the `PSEO_EVENTS_WRITER`
  escape hatch are unchanged. +26 tests (13 red against the previous guard).
- **`schema_path` is enforced as test-only** (`7c59cef`): outside pytest, a schema path
  different from the repo schema raises `EventValidationError` before the ledger is
  touched; every `append_*` wrapper goes through it. +5 tests.

False-positive check: replaying 59,838 real Bash commands, the old guard blocked 0 and
the new one blocks 6 — all six are genuine appends to a live `events.jsonl`.

## Known failures (pre-existing, unchanged)

The same 15 `pytest` failures as v2.1.1, all workspace DATA (schema drift in seven
projects, task-id drift in one). Cleaning the rows is a separate, owner-approved task:
this release only stops new ones.

## Not measured by the gate

- Writes the guard still cannot see: a script written to disk and then run
  (`python <file>.py`), `python -m` modules, paths with no `events.jsonl` literal
  anywhere in the code, `shutil.copy` / `os.replace`, paths built in loops.
- `schema_path` enforcement can be bypassed deliberately by setting
  `PYTEST_CURRENT_TEST`; it closes accidental and silent use, not a determined one.
- The master-excel writer's schema override is not covered by this release.
