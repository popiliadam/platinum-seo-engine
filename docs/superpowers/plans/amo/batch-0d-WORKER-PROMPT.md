# AMO Batch 0d — Audit Hook H1 Fix (session-aware attribution) (WORKER PROMPT)

> **Manager note:** The review's single "highest-value Phase-0 change": today the PostToolUse audit hook
> stamps every `events.jsonl` audit event with the GLOBAL `shared/active.json` active_project. Under
> multi-window that silently mis-attributes window B's writes to window A's project (cross-project
> corruption of an append-only ledger — H1). This batch fixes it by resolving the project from THIS
> session's binding marker (batch 0b/0c primitive), extracting the fragile inline-python audit command
> into a testable script. Banners + SessionStart self-check are deferred to a later cosmetic polish (NOT
> here). Paste the block into a fresh Claude Code session (Opus 4.8, 1M).

---

```text
You are a WORKER fixing ONE data-integrity bug in the Platinum SEO Engine (Python, pytest). Repo root:
/Users/apple/Documents/platinum-seo-engine. Batch 0d, managed elsewhere. Work ONLY within scope. Do NOT
git commit/push — STOP when done and print the REPORT.

HARD ENVIRONMENT RULES (non-negotiable):
- NO Task/Agent tools (they FAIL here: "Prompt is too long"). Work inline.
- NO git commit/push/branch.
- Baseline-first: `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  → record exact "N passed" (expect 1762 passed, 8 skipped). END green, passed >= N.
- TDD: failing test first, watch it fail, then implement. Never fake red.
- House style: immutability; no stray debug prints (a script's intended stderr is fine); functions <50 lines.
- Scope-lock: edit ONLY the files in SCOPE. Anything else -> STOP + report.

THE BUG (H1): the PostToolUse audit hook attributes every audit event to the workspace-GLOBAL
`shared/active.json` active_project. With 3-5 parallel sessions (one per project — the AMO goal), every
session's audit events get stamped with whichever project active.json last named → silent cross-project
contamination of the append-only `events.jsonl`. Fix: attribute to THIS session's bound project using the
batch-0b/0c binding primitive, falling back to active.json only when the session is unbound (today's
behavior for single-project users — no regression).

CONFIRMED PRIMITIVE (batch 0b/0c, read the module — don't re-derive): `scripts/state/session_binding.py`:
  - `resolve_session_project(workspace_root, *, arg=None, session_id=None, strict=False) -> str|None`
    (arg → session marker → shared/active.json active_project → None; strict=False never raises).
  - `current_session_id(payload=None, environ=os.environ) -> str|None` (hook payload session_id → env → None).
  - `resolve_workspace_root(environ=os.environ) -> Path|None` (~/.config/pseo/config.json → env → None).
A PostToolUse hook receives `session_id` in its stdin JSON payload (AMO batch 0a probe confirmed it on
PostToolUse). So pass `current_session_id(payload)` to resolve_session_project.

ORIENT FIRST (read, then change):
- `hooks/post-tool-use.json` — the audit hook. Today its `PostToolUse` array holds (1) a long inline
  `python3 -c '...'` audit command that reads PSEO_WORKSPACE_ROOT + active.json → pid, imports
  `scripts.state.events_writer` (append_audit / normalize_audit_action), and appends an audit event,
  then (2) the env_probe command appended in batch 0a. PRESERVE the env_probe command entry untouched.
- `scripts/state/events_writer.py` — the `append_audit(...)` + `normalize_audit_action(...)` API the
  inline command calls; mirror its exact call signature in the extracted script.
- `scripts/hooks/validate_content_write.py` (lines 38-42) — copy its repo-root `sys.path` bootstrap so the
  new script's `scripts.*` imports work as a bare hook subprocess.
- `tests/hooks/test_hook_scripts_runtime_vs_ci.py` — the RUNTIME/GUARD/DIAGNOSTIC classification guard
  (batch 0a). A NEW wired hook script MUST be added to `RUNTIME_HOOK_SCRIPTS` + documented in
  `scripts/hooks/README.md`, or this guard fails (same pattern batch 0a used for env_probe.py).
- `scripts/hooks/README.md` — the runtime-script doc the guard checks.

SCOPE — create/modify ONLY these:
  NEW  scripts/hooks/audit_post_tool_use.py     (the extracted, session-aware audit emitter + repo-root bootstrap)
  EDIT hooks/post-tool-use.json                 (replace the inline `python3 -c` audit command with a call to
                                                 the new script; LEAVE the env_probe command entry intact)
  EDIT tests/hooks/test_hook_scripts_runtime_vs_ci.py   (add audit_post_tool_use.py to RUNTIME_HOOK_SCRIPTS)
  EDIT scripts/hooks/README.md                  (document the new runtime script in the runtime table)
  NEW  tests/hooks/test_audit_post_tool_use.py  (TDD)

SPEC — scripts/hooks/audit_post_tool_use.py:
- Repo-root sys.path bootstrap (mirror validate_content_write.py:38-42), then import events_writer +
  session_binding.
- `main()`: read+parse stdin payload (tolerate empty/garbage → exit 0, non-blocking — match the current
  hook's "never break the chain" behavior). Resolve:
    ws = resolve_workspace_root()                       # config → env
    if ws is None: exit 0  (nothing to attribute to — same as today's "no workspace" no-op)
    pid = resolve_session_project(ws, session_id=current_session_id(payload), strict=False)
    if not pid: exit 0
  Then reproduce TODAY's audit emission EXACTLY (read the current inline command for the precise logic):
  compute the audit_action (Edit→"modified"; Write→"created"/"modified" by file existence;
  Bash→normalize_audit_action(tn, command=cmd)); build the REDACTED audit_target (Bash → head + " [REDACTED
  args]", else file_path/path); call `append_audit(project_id=pid, audit_action=..., audit_target=...[:480],
  actor="claude-code:hook:PostToolUse", workspace_root=ws)`. Wrap everything so a failure prints a WARNING
  to stderr and exits 0 (non-blocking, exactly like today's `|| { echo 'WARNING ...'; true; }`).
- The ONLY behavioral change vs today: `pid` comes from resolve_session_project (session marker → active.json)
  instead of active.json directly. Everything else (redaction, action mapping, non-blocking) is identical.

SPEC — hooks/post-tool-use.json:
- Replace the inline `python3 -c '...'` audit command's `command` string with:
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/audit_post_tool_use.py"
  Keep its matcher (Edit|Write|Bash), timeout, statusMessage sensible. DO NOT remove/alter the env_probe
  command entry. Validate the JSON parses.

TDD — tests/hooks/test_audit_post_tool_use.py (write FIRST, watch fail, then implement):
  1. Given a tmp workspace with a session marker binding session "S" → project "alpha" AND active.json →
     "beta", a PostToolUse payload {session_id:"S", tool_name:"Edit", tool_input:{file_path:...}} →
     the audit event is appended under project "alpha" (NOT beta). (Inspect the project's events.jsonl or
     monkeypatch append_audit to capture project_id.)
  2. No session marker → falls back to active.json "beta" (today's behavior preserved).
  3. Bash tool payload → audit_target is REDACTED (asserts the command args do NOT appear; head + "[REDACTED
     args]" present).
  4. Empty / garbage stdin → exit 0, no traceback (non-blocking).
  5. No workspace / unbound + no active.json → exit 0, no event, no raise.
  Use tmp_path + monkeypatched HOME/env so tests never touch the real ~/.config or workspace. Prefer
  capturing via monkeypatching events_writer.append_audit to record (project_id, action, target) over
  parsing real ledger files where practical.

METHOD:
  1. Baseline pytest (record N=1762).
  2. Tests RED.
  3. Implement the script; wire the hook; classify it (RUNTIME_HOOK_SCRIPTS + README). GREEN.
  4. Full pytest; passed >= N; validate every hooks/*.json parses; confirm the runtime-vs-ci guard +
     count-consistency guards stay green (you added a SCRIPT, not a command/schema — no manifest bump).
  5. @code-reviewer + @verifier inline; address findings.

DURUR (stop + report):
  - Reproducing today's exact audit_action / redaction logic is ambiguous from the inline command — report
    the ambiguity rather than guess.
  - The runtime-vs-ci or count guard fails for a reason other than "new runtime script needs classifying".

REPORT (verbatim when DONE):
  - Baseline N and final pytest line.
  - The exact attribution precedence now (session marker → active.json) + proof of non-blocking + redaction
    parity with the old inline command.
  - Confirmation the env_probe command entry is intact, only the audit command was replaced, and the new
    script is classified RUNTIME (guard green).
  - Any DURUR / assumption / out-of-scope need.
```
