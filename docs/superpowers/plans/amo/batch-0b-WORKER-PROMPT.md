# AMO Batch 0b — Binding Primitive (WORKER PROMPT)

> **Manager note (not part of the prompt):** Batch 0a (the probe) confirmed, with VSCode operator
> data + manager analysis of the raw log, that the AMO per-session binding key is the **Claude session
> UUID**, available identically as the hook-stdin `session_id` AND the command-env
> `CLAUDE_CODE_SESSION_ID` (proven equal via the transcript-filename namespace). This batch builds the
> *binding primitive* (resolver + `/pseo-bind` + workspace-root persistence + tests) as new, isolated,
> unit-testable code. The next batch (0c) WIRES the existing consumers (dump_workspace, content-gate,
> audit hook, banners) to this primitive. Paste the block below into a fresh Claude Code session
> (Opus 4.8, 1M) rooted at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 0b of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and
print the REPORT (the manager reviews + commits).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record exact "N passed, M skipped" BEFORE any change. END green, passed >= N.
- TDD: failing test first, watch it fail, then implement. Never fake red.
- House style: immutability (return new objects); no print/console debug in shipped code (a command-CLI
  that prints a user banner is fine); no hardcoded secrets; functions <50 lines; files 200-400 lines.
- Scope-lock: create/modify ONLY the files in SCOPE. Other file needed -> STOP + report.

CONFIRMED FACTS (do not re-derive — these came from batch 0a's probe + manager log analysis):
- The per-session BINDING KEY is the Claude session UUID, available identically from TWO sources:
    * Hooks: the `session_id` field in the hook's stdin JSON payload (present + stable across all five
      events incl. Stop).
    * Commands/bash: the `CLAUDE_CODE_SESSION_ID` environment variable.
    * They are the SAME UUID for a given session (proven via transcript filename namespace). So a marker
      written by a command (keyed by $CLAUDE_CODE_SESSION_ID) is found by a hook (keyed by stdin session_id).
- ENGINE ROOT is `$CLAUDE_PLUGIN_ROOT` (reliably set in every hook/command, e.g.
  "/Users/apple/Documents/platinum-seo-engine/"). NEVER derive engine root from cwd or a hardcoded
  ~/.claude/plugins/cache path.
- DO NOT rely on these (probe proved them unreliable): `CLAUDE_ENV_FILE` (set only at SessionStart),
  `PSEO_WORKSPACE_ROOT` env (absent in many sessions), cwd.
- Therefore WORKSPACE ROOT must be persisted editor-independently in `~/.config/pseo/config.json`
  and read from there (env only as a fallback).

WHY THIS BATCH: AMO binds one Claude session to one SEO project so the user can run 3-5 projects in
parallel (one per session) without cross-contamination. The binding is a marker file keyed by the
session UUID. This batch builds the primitive that writes/reads that marker and resolves "which project
is THIS session bound to", with a safe fallback to today's global active.json so nothing regresses when
a session is unbound.

ORIENT FIRST (read, do not change):
- `commands/pseo-active.md` — REUSE its atomic write discipline (tempfile + fsync + os.replace) and its
  slug-validation (checks `projects/{slug}/project.config.json` exists). Your `/pseo-bind` mirrors it but
  keys the marker by session UUID instead of writing the global active.json.
- `scripts/state/dump_workspace.py::_resolve_slug` (the current `arg -> active.json` resolver) and
  `scripts/state/env.py::get_workspace_root` — learn the existing resolution + workspace-root reading.
- `scripts/state/events_writer.py` / `scripts/excel/transaction.py` — copy the atomic-write helper
  pattern (O_* / tempfile + os.replace) used elsewhere; do not invent a new one.
- `schemas/` — note how small JSON artifacts are validated; you will add a tiny schema for the marker.
- A sibling test dir (e.g. `tests/state/`) for placement + whether `__init__.py` is used.

SCOPE — create/modify ONLY these:
  NEW  scripts/state/session_binding.py        (the primitive: resolver + marker R/W + config persistence + CLI)
  NEW  commands/pseo-bind.md                    (slash command wrapping the CLI)
  NEW  schemas/session-marker.schema.json       (shape of shared/sessions/<uuid>.json)
  NEW  tests/state/test_session_binding.py      (TDD)
  EDIT docs/PROBE/README or .env.example ONLY IF needed to document PSEO config — if so, STOP and ask first.

SPEC — scripts/state/session_binding.py (pure functions + a thin argparse CLI):
- `resolve_workspace_root(environ=os.environ) -> Path | None`
    Order: `~/.config/pseo/config.json`["workspace_root"] (expanduser) -> `PSEO_WORKSPACE_ROOT` env -> None.
- `current_session_id(payload: dict | None = None, environ=os.environ) -> str | None`
    If `payload` and payload.get("session_id") -> that (HOOK context). Else environ.get("CLAUDE_CODE_SESSION_ID")
    (COMMAND context). Else None.
- `sessions_dir(workspace_root: Path) -> Path`  ->  `workspace_root / "shared" / "sessions"`.
    (Workspace-GLOBAL, alongside active.json in shared/ — NOT per-project _state/. active.json lives in
    shared/, so session markers live in shared/sessions/ for consistency.)
- `read_session_binding(session_id: str, workspace_root: Path) -> str | None`
    Read `sessions_dir/{session_id}.json`["active_project"]; missing/invalid -> None (never raises).
- `read_active_project(workspace_root: Path) -> str | None`
    Read `workspace_root/shared/active.json`["active_project"]; missing -> None (never raises).
- `resolve_session_project(workspace_root: Path | None, *, arg: str | None = None,
                           session_id: str | None = None, strict: bool = False) -> str | None`
    Precedence: explicit `arg` -> `read_session_binding(session_id, ws)` (only if both session_id & ws) ->
    `read_active_project(ws)` -> None. If `strict` and result is None -> raise FileNotFoundError with a
    clear message. (This preserves dump_workspace's strict contract AND the content-gate's never-raise
    contract via the flag — batch 0c will call this with strict=True for commands, strict=False for hooks.)
- `write_session_binding(session_id: str, slug: str, workspace_root: Path, now_iso: str) -> Path`
    Atomic write (tempfile in the same dir + fsync + os.replace) of
    `sessions_dir/{session_id}.json` = {"active_project": slug, "bound_at": now_iso, "session_id": session_id}.
    Create sessions_dir if missing. Return the path.
- `persist_workspace_root(workspace_root: Path) -> Path`
    Atomic write `~/.config/pseo/config.json` = {"workspace_root": str(workspace_root)} (merge-preserving
    any existing keys). Create ~/.config/pseo/ if missing. Return the path.
- `session_ids_consistent(payload: dict, environ=os.environ) -> bool`
    True iff payload.get("session_id") == environ.get("CLAUDE_CODE_SESSION_ID") OR either is missing
    (can't contradict). A SessionStart hook will use this in 0c as a runtime self-check; expose it now.
- CLI (argparse): `python3 -m scripts.state.session_binding bind <slug> [--workspace PATH]`
    1. workspace_root = --workspace (then persist it) OR resolve_workspace_root(); if None -> exit non-zero
       with a message telling the user to pass --workspace once.
    2. session_id = current_session_id() ; if None -> exit non-zero ("no CLAUDE_CODE_SESSION_ID; run from a
       Claude session").
    3. Validate `workspace_root/projects/{slug}/project.config.json` exists; else exit non-zero.
    4. write_session_binding(...); print a one-line confirmation banner ("bound session <id-prefix> -> <slug>").
    Use datetime.now().isoformat() for now_iso (runtime is fine).

SPEC — commands/pseo-bind.md:
- Frontmatter consistent with other commands (argument-hint "<project-slug> [--workspace <path>]",
  allowed-tools includes Bash, model sonnet). Body: a short numbered recipe instructing Claude to run
  `python3 -m scripts.state.session_binding bind "$1"` (passing through an optional --workspace) from the
  engine repo, and to surface the banner. Mirror the structure/tone of commands/pseo-active.md.

SPEC — schemas/session-marker.schema.json:
- Draft-07, additionalProperties:false, required [active_project, bound_at, session_id]; active_project
  pattern `^[a-z][a-z0-9-]*$`; session_id a non-empty string; bound_at a string. Add a test that a written
  marker validates against it.

TDD — tests/state/test_session_binding.py (write FIRST, watch fail, then implement):
  1. resolve_session_project precedence: arg wins; with no arg but a session marker present -> marker slug;
     with neither but active.json present -> active slug; with none -> None; strict=True + none -> raises.
  2. current_session_id: payload with session_id -> that; no payload but env CLAUDE_CODE_SESSION_ID -> env;
     neither -> None.
  3. sessions_dir == workspace/shared/sessions ; write+read round-trip returns the slug.
  4. write_session_binding is atomic (no partial file on a simulated mid-write failure is hard to force;
     at minimum assert the final file is valid JSON and validates against session-marker.schema.json).
  5. persist_workspace_root writes/merges ~/.config/pseo/config.json (use a tmp HOME or monkeypatch
     expanduser/Path.home to tmp_path so the test never touches the real ~/.config).
  6. read_session_binding / read_active_project return None (no raise) on missing/garbage files.
  7. session_ids_consistent: equal -> True; differing -> False; either missing -> True.
  8. CLI `bind`: subprocess with env CLAUDE_CODE_SESSION_ID=test-sess + a tmp workspace containing
     projects/<slug>/project.config.json -> exit 0, marker written, banner printed; unknown slug -> non-zero;
     missing session id -> non-zero.
  ALL filesystem tests must use tmp_path / monkeypatched HOME — never write to the real ~/.config or the
  real workspace.

METHOD:
  1. Baseline pytest (record N).
  2. Write tests (RED).
  3. Implement session_binding.py, the schema, the command (GREEN).
  4. Re-run FULL pytest; passed >= N. Validate every hooks/*.json + the new schema parse as JSON.
  5. @code-reviewer + @verifier (inline, since Agent tools are disabled); address findings.

DURUR (stop + report):
  - The atomic-write helper you need isn't reusable from existing modules (report rather than invent a
    subtly-different one).
  - A consumer would have to change to make a test pass (that is batch 0c — out of scope here).
  - shared/sessions vs _state/sessions placement seems wrong for a reason you discover — report it.

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line.
  - Files created (paths) + the marker path convention + the resolution precedence you implemented.
  - The exact `/pseo-bind` usage line + what it prints on success.
  - Confirmation that NO existing consumer was modified (that is 0c) and the strict/advisory flag is ready
    for 0c to wire.
  - Any DURUR hit / assumption / out-of-scope need.
```
