# Release Notes — v2.1.1 (2026-10-02)

**Theme:** *Make the installed engine match the repo.* A patch release, cut because
the installed plugin cache had stayed on v2.1.0 since 2026-06-10: with the version
number unchanged, `claude plugin update` never pulled newer code, so guards that
exist on `main` were not running in real sessions.

## Why this release exists

A diff of the installed cache (`~/.claude/plugins/cache/…/platinum-seo-engine/2.1.0/`)
against `main` on 2026-10-02 found:

- **`check_events_writer.py` and `check_master_direct_write.py` were not installed.**
  Both are on `main` and wired in `hooks/`, but the running cache predated them, so
  direct writes to `events.jsonl` / `master.xlsx` were unguarded in practice. Seven
  projects show `events.jsonl` schema drift again (see "Known failures" below).
- **One change lived only in the cache** — T-10690 (below), patched in place on
  2026-08-20 and never committed. A reinstall would have deleted it.
- The other ~166 differing files were the 2026-07-08 client-name scrub — cosmetic.

## Changes

- **`/pseo-approve` works in one step** (`183fad8`). Five root causes, each
  reproduced from session transcripts:
  - the gate's hint named `/pseo-approve`, but the command is only registered as
    `/platinum-seo-engine:pseo-approve` (`Unknown command` in 4 sessions; the hint
    was also pasted into a terminal 26 times);
  - shell redirections leaked into the target (`origin main 2>&1`), so consent for
    `origin main` never matched — targets are now redirection-stripped, quote-aware,
    and proven equal to bash's real argv in 17 adversarial cases;
  - the hint printed the target in double quotes (expanded `$T`, split on inner
    quotes) — now `shlex.quote`d and labelled "type in the Claude chat";
  - `approve` without `CLAUDE_CODE_SESSION_ID` printed "consent recorded" and wrote
    a session-less row that could never match — it now exits 6 and writes nothing;
  - the command was model-invocable as a Skill (the model approved itself once) —
    now `disable-model-invocation: true`.
  Replay of 125 real blocked commands from the last 45 days: 25 targets simplified,
  0 previously-blocked commands now pass.
- **xquik MCP server removed** (`352dd0e`); server invariant 4 → 5.
- **T-10690 — quick-win uplift uses the absolute SERP rank when known**
  (`24df763`). GSC reports rank among organic links only; AIO / PAA / video blocks
  push the on-screen slot lower. Carried from the cache byte-for-byte (3-way merge,
  base `32778ba` = `main`, no conflicts) with its 8 tests.

## Known failures (pre-existing, not introduced here)

`pytest` with `PSEO_WORKSPACE_ROOT` bound: 15 failures, all workspace DATA, none in
code touched by this release — `events.jsonl` schema drift in seven workspace projects
(`test_events_jsonl_strict`, `test_events_jsonl_validates`) and task-id drift in one. They are the reason the
events guard above matters; cleaning them is a separate, diagnosis-first task.

## Not measured by the gate

- That the installed command lists as `/platinum-seo-engine:pseo-approve` and runs
  in a live session.
- That `disable-model-invocation` is enforced by the harness.
- A model can still append its own consent through `Bash(python3 -m
  scripts.state.consent_ledger approve …)`; the command itself uses that path, so a
  plain ban would also block the human route. Tracked as follow-up.
