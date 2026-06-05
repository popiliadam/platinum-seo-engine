# AMO Batch 0c — Wire Python Consumers to the Binding Primitive (WORKER PROMPT)

> **Manager note:** Batch 0b shipped `scripts/state/session_binding.py` (resolve_session_project /
> read_session_binding / current_session_id / resolve_workspace_root), commit 5a7980d, green. This
> batch wires the TWO clean Python-script consumers (`dump_workspace._resolve_slug` and the content-gate
> `validate_content_write._resolve_profile`) onto it so a bound session targets ITS project, with an
> unchanged fall-through to global active.json. The fiddly inline-hook consumers (post-tool-use audit
> attribution + banners + SessionStart self-check) are a SEPARATE later batch (0d) — NOT here. Paste the
> block below into a fresh Claude Code session (Opus 4.8, 1M).

---

```text
You are a WORKER wiring TWO existing consumers onto the AMO binding primitive in the Platinum SEO Engine
(Python, pytest). Repo root: /Users/apple/Documents/platinum-seo-engine. Batch 0c, managed elsewhere.
Work ONLY within scope. Do NOT git commit/push — STOP when done and print the REPORT.

HARD ENVIRONMENT RULES (non-negotiable):
- NO Task/Agent tools (they FAIL here: "Prompt is too long"). Work inline.
- NO git commit/push/branch.
- Baseline-first: `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  → record exact "N passed". END green, passed >= N. (Current baseline should be 1749 passed, 8 skipped.)
- TDD: failing test first, watch it fail, then implement. Never fake red.
- House style: immutability; no new debug prints; functions <50 lines; small diffs.
- Scope-lock: edit ONLY the 4 files in SCOPE. Anything else needed -> STOP + report. This batch adds NO
  command and NO schema, so it must NOT trip the count-consistency guards (if it does, you touched an
  out-of-scope file — stop).

CONFIRMED (batch 0b, commit 5a7980d — read the module, don't re-derive): `scripts/state/session_binding.py`
exposes:
  - `resolve_session_project(workspace_root, *, arg=None, session_id=None, strict=False) -> str|None`
    (precedence arg -> session marker -> shared/active.json active_project -> None; strict=True raises).
  - `read_session_binding(session_id, workspace_root) -> str|None` (marker active_project, never raises).
  - `current_session_id(payload=None, environ=os.environ) -> str|None` (hook payload session_id -> env
    CLAUDE_CODE_SESSION_ID -> None).
  - `resolve_workspace_root(environ=os.environ) -> Path|None` (~/.config/pseo/config.json -> env -> None).
The session UUID reaches a COMMAND via env CLAUDE_CODE_SESSION_ID and a HOOK via stdin payload session_id;
both are the same UUID (batch 0a). A session marker, when present, must take precedence over active.json;
when absent, behavior is exactly today's.

ORIENT FIRST (read, then change):
- `scripts/state/session_binding.py` — the primitive API above.
- `scripts/state/dump_workspace.py::_resolve_slug` (lines ~49-75): today `arg -> active.json[active_project|legacy 'slug'] -> raise FileNotFoundError`. It RAISES on missing (command contract) and has a legacy-'slug'-key warning. PRESERVE both.
- `scripts/hooks/validate_content_write.py::_resolve_profile` (lines ~99-125) AND its `main()` (~128-135, how `payload` flows): today reads `os.environ['PSEO_WORKSPACE_ROOT'] -> active.json[active_project] -> project.config.json profile`; "Never raises; returns None". PRESERVE never-raise.
- The existing tests for both (grep tests/ for `_resolve_slug` and `validate_content_write` / `_resolve_profile`) — they MUST stay green.

SCOPE — edit ONLY these:
  EDIT scripts/state/dump_workspace.py                  (insert session-marker precedence in _resolve_slug)
  EDIT scripts/hooks/validate_content_write.py          (session+workspace via the primitive in _resolve_profile)
  EDIT tests/.../<dump_workspace test file>             (add session-marker precedence cases)
  EDIT tests/.../<validate_content_write test file>     (add session-marker profile cases)

SPEC — `dump_workspace._resolve_slug` (MINIMAL, behavior-preserving):
  Keep the signature and the `if project_slug is not None: return project_slug` arg-check. THEN, BEFORE the
  existing active.json block, insert a session-marker lookup:
      from scripts.state.session_binding import read_session_binding, current_session_id
      sid = current_session_id()                      # command context: env CLAUDE_CODE_SESSION_ID
      if sid:
          bound = read_session_binding(sid, workspace_root)
          if bound:
              return bound
  Leave the ENTIRE existing active.json block (active_project, legacy 'slug' warning, all FileNotFoundError
  raises) UNCHANGED as the fall-through. Net: precedence becomes arg -> session marker -> (unchanged
  active.json logic incl. raises). Do NOT route the legacy/raise path through resolve_session_project (it
  doesn't replicate the legacy-'slug' handling) — only add the marker check above it.

SPEC — `validate_content_write._resolve_profile`:
  Thread the session id from the PreToolUse stdin payload and use the primitive for workspace + project:
    - Change signature to `_resolve_profile(payload: dict | None = None) -> str | None` and update `main()`
      to call `_resolve_profile(payload)` (payload is already parsed there).
    - workspace = `resolve_workspace_root()` (config -> env) INSTEAD of `os.environ.get("PSEO_WORKSPACE_ROOT")`
      (batch 0a: env unreliable; config wins). If None -> return None.
    - project_id = `resolve_session_project(workspace, session_id=current_session_id(payload), strict=False)`
      INSTEAD of reading active.json directly (session marker -> active.json fallback, never raises).
    - Keep the rest (project.config.json -> profile/profiles[0]) and the outer try/except -> None UNCHANGED.
  The never-raise contract MUST hold (strict=False + the existing try/except).

TDD (write FIRST, watch fail, then implement) — add to the existing test files:
  dump_workspace:
    - With a session marker `shared/sessions/<sid>.json` bound to project A AND a DIFFERENT active.json
      (project B), with env CLAUDE_CODE_SESSION_ID=<sid> -> _resolve_slug returns A (marker wins over active.json).
    - No marker -> returns active.json's project (unchanged); legacy-'slug'-only active.json still warns +
      returns; missing active.json still raises FileNotFoundError. (Assert the existing behavior is intact.)
    - explicit project_slug arg still wins over everything.
  validate_content_write:
    - payload session_id whose marker binds project A (config profile "ymyl") -> _resolve_profile(payload)=="ymyl".
    - No marker, active.json -> project B's profile (unchanged).
    - Unbound / no workspace / bad config -> None, NEVER raises (feed garbage and assert no exception).
  Use tmp_path + monkeypatched HOME/env so tests never touch the real ~/.config or workspace.

METHOD:
  1. Baseline pytest (record N=1749 expected).
  2. Tests RED.
  3. Implement the two wirings (GREEN).
  4. Full pytest; passed >= N; confirm NO count-guard test newly fails (you added no command/schema).
  5. @code-reviewer + @verifier inline; address findings.

DURUR (stop + report):
  - A behavior-preserving wiring is impossible without changing a consumer's public contract (raise-vs-None).
  - An existing test for either consumer can only pass by weakening it.
  - You'd need to touch a 5th file (e.g. a hook JSON) — that's batch 0d, out of scope.

REPORT (verbatim when DONE):
  - Baseline N and final pytest line.
  - The exact precedence each consumer now implements + proof the legacy/raise (dump_workspace) and
    never-raise (content-gate) contracts are intact.
  - Confirmation no command/schema added (no manifest bump needed) and only the 4 scoped files changed.
  - Any DURUR / assumption / out-of-scope need.
```
