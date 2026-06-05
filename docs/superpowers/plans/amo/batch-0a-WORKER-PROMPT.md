# AMO Batch 0a — Cross-Environment Hook Probe (WORKER PROMPT)

> **Manager note (not part of the prompt):** This is the FIRST AMO build batch. It is a *diagnostic
> probe*, deliberately dispatched before any binding code, to empirically resolve whether a stable
> `session_id` reaches plugin hooks in all three target environments (VSCode / Claude Desktop Mac app
> / CLI). The whole binding design (batch 0b) depends on this answer. Paste the block below into a
> fresh Claude Code session (Opus 4.8, 1M context) rooted at the engine repo. When the worker reports
> DONE, the manager + Süleyman run the probe across the 3 environments and feed the logs back; the
> manager then authors batch 0b with the confirmed session-id field.

---

```text
You are a WORKER building ONE small, self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 0a of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit or push — when done, STOP
and print the REPORT (the manager reviews + commits).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools. They FAIL in this project (the session's MCP tool registry is too
  large for a subagent: "Prompt is too long"). Do ALL work inline yourself.
- Do NOT git commit, push, branch, or modify git state. No `git add`/`commit`/`checkout`/`reset`.
- Baseline-first: run `python3 -m pytest -q 2>&1 | tail -5` and record the exact "N passed, M skipped"
  BEFORE any change. You must END green with passed strictly ≥ N.
- TDD: write the FAILING test first, watch it fail, then implement until green. Never fake red.
- Immutability / house style: return new objects (no mutation); no print/console debug left in code;
  no hardcoded secrets; small focused functions (<50 lines); files 200-400 lines normal.
- Scope-lock: create/modify ONLY the files named in SCOPE below. If a fix seems to need any other
  file, STOP and report it — do not touch it.

WHY THIS BATCH EXISTS (read carefully):
The AMO initiative lets the user run 3-5 SEO projects in parallel, one per session, each bound to a
different project. The chosen binding mechanism is a per-session marker FILE keyed by the Claude
**session_id** that the harness passes to hooks on stdin (NOT a shell env var — env vars are unsettable
per-session in the Claude Desktop Mac app, and `.env` is never loaded into the hook environment). Before
we write any binding code, we must EMPIRICALLY CONFIRM, across VSCode / Mac-app / CLI:
  (1) does the hook stdin payload actually carry a stable `session_id` (or what is the session-identifying
      field)? is it the SAME value across all hook events within one session?
  (2) which env vars are present to hooks: CLAUDE_PLUGIN_ROOT, CLAUDE_PROJECT_DIR, CLAUDE_ENV_FILE,
      CLAUDECODE, PSEO_WORKSPACE_ROOT?
  (3) do the same hook events fire with the same stdin shape in all three environments?
Your job is to build a safe, non-blocking PROBE that records this, plus a report tool, plus tests. You
do NOT analyze the cross-environment results — the manager does that after Süleyman runs the probe.

ORIENT FIRST (read, do not change yet):
- `.claude-plugin/plugin.json` — find how hooks are registered (a "hooks" key? a dir/glob? a list of
  files?). You must register the probe ADDITIVELY using whatever mechanism this plugin already uses.
- `hooks/session-start.json`, `hooks/user-prompt-submit.json`, `hooks/pre-tool-use.json`,
  `hooks/post-tool-use.json`, `hooks/stop.json` — learn the exact JSON shape
  ({"hooks": {"<Event>": [{"matcher": ..., "hooks": [{"type":"command","command":"...","timeout":N}]}]}}).
  Note that hook arrays can hold MULTIPLE command entries — you will ADD one, never alter existing ones.
- `scripts/hooks/` — see how existing hook scripts read stdin (e.g. `validate_content_write.py`,
  `stop_validation.py`) and how `${CLAUDE_PLUGIN_ROOT}` is referenced in hook commands.
- `conftest.py` and `tests/` layout (e.g. `tests/skills/`, `tests/schemas/`) to place the new test correctly.

SCOPE — create/modify ONLY these:
  NEW  scripts/hooks/env_probe.py              (the probe: reads stdin, appends one safe JSON line)
  NEW  scripts/hooks/env_probe_report.py       (reads the probe log, prints a per-environment summary)
  NEW  tests/hooks/test_env_probe.py           (TDD; create tests/hooks/ if absent, add __init__ if the
                                                repo's test packages use them — check a sibling tests dir)
  EDIT the hook registration so the probe fires on SessionStart + UserPromptSubmit + PreToolUse +
       PostToolUse + Stop — ADDITIVELY (a new command entry per event, or a dedicated probe hook file if
       plugin.json loads hooks by dir/glob). NEVER change or reorder existing hook commands.

SPEC — scripts/hooks/env_probe.py:
- Structure it as a PURE, testable function plus a thin main:
    def extract_probe_record(payload: dict, environ: dict, cwd: str, now_iso: str) -> dict
  returning ONLY these SAFE fields (NEVER include message/prompt/tool_input/tool_response VALUES — they
  can carry secrets or content; capture KEYS only):
    {
      "ts": now_iso,
      "hook_event_name": payload.get("hook_event_name"),
      "stdin_keys": sorted(payload.keys()),                       # structure only
      "session_id": payload.get("session_id"),                    # the candidate binding key
      "transcript_path": payload.get("transcript_path"),          # secondary session signal (path ok)
      "cwd_payload": payload.get("cwd"),
      "cwd_os": cwd,
      "other_id_keys": {k: v for k, v in payload.items()
                        if "id" in k.lower() and k != "session_id"
                        and isinstance(v, (str, int)) and len(str(v)) <= 120},
      "env_present": {name: (name in environ) for name in
                      ("CLAUDE_PLUGIN_ROOT","CLAUDE_PROJECT_DIR","CLAUDE_ENV_FILE",
                       "CLAUDECODE","PSEO_WORKSPACE_ROOT")},
      "env_values": {name: environ.get(name) for name in
                     ("CLAUDE_PLUGIN_ROOT","CLAUDE_ENV_FILE")},   # non-secret paths, useful
    }
- main():
    * Read all of stdin; tolerate empty/malformed (json.loads in a try; on failure use {} and set a
      "_stdin_parse_error": True marker in the record).
    * Build the record via extract_probe_record(payload, os.environ, os.getcwd(), datetime.now().isoformat()).
    * Append ONE json.dumps(record) + "\n" to the log path:
        log = os.environ.get("PSEO_PROBE_LOG") or os.path.expanduser("~/.config/pseo/hook-probe.jsonl")
      Create the parent dir (os.makedirs(..., exist_ok=True)). Open "a", write, flush.
    * WRAP THE ENTIRE main in try/except so it can NEVER crash the hook chain; ALWAYS sys.exit(0).
- The probe must be FAST (<100ms) and NON-BLOCKING (exit 0 always). It must NOT read or require
  PSEO_WORKSPACE_ROOT (that is exactly what may be missing).

SPEC — scripts/hooks/env_probe_report.py:
- CLI: optional arg = log path (default ~/.config/pseo/hook-probe.jsonl). Read JSONL lines (skip
  unparseable, count them). Group records by `session_id` (treat None as a bucket), and within that by
  `hook_event_name`. Print a compact summary:
    * each distinct session_id and how many events it produced, and which of the 5 events appeared;
    * whether `session_id` is non-null and identical across all events of a session (the key question);
    * `transcript_path`, `cwd_payload`, `cwd_os` seen;
    * env_present booleans + env_values.
  End with a one-line VERDICT per session_id: "session_id stable & present across N/5 events: YES/NO".
- No external deps (stdlib only: json, sys, os, collections).

TDD — tests/hooks/test_env_probe.py (write these FIRST, watch fail, then implement):
  1. extract_probe_record with a payload containing session_id/transcript_path/cwd/hook_event_name →
     record carries them; stdin_keys is the sorted key list.
  2. extract_probe_record with a payload MISSING session_id → record["session_id"] is None, no exception.
  3. SECURITY: payload contains tool_input={"command":"export SECRET=sk-LEAKME"} → assert the string
     "sk-LEAKME" does NOT appear anywhere in json.dumps(record); "tool_input" DOES appear in stdin_keys.
  4. main() with PSEO_PROBE_LOG=tmp file + stdin piped a valid JSON payload → exactly one valid JSON line
     appended; reading it back round-trips. (Invoke via subprocess `python3 scripts/hooks/env_probe.py`
     with input=..., env includes PSEO_PROBE_LOG=tmp.)
  5. main() with empty stdin and with malformed (non-JSON) stdin → exit code 0, a record with
     "_stdin_parse_error": True is appended, no traceback.
  6. env_probe_report on a hand-written 2-session JSONL fixture prints both session_ids and the correct
     "stable across N/5" verdict (assert on substrings in captured stdout).

METHOD:
  1. Baseline pytest (record N).
  2. Write tests/hooks/test_env_probe.py (RED).
  3. Implement env_probe.py then env_probe_report.py until those tests pass (GREEN).
  4. Register the probe hook ADDITIVELY (read plugin.json first; do not disturb existing commands).
     Sanity-check the JSON is valid (python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('hooks/*.json')]").
  5. Re-run FULL pytest; confirm passed ≥ baseline N (your 6 new tests add to it).
  6. Run `@code-reviewer` + `@verifier` (Dev-QA loop) and address what they flag.

DURUR (stop + report, do not work around):
  - You cannot register the probe additively without altering existing hook commands.
  - Any existing test regresses and the cause is outside this batch's files.
  - The plugin's hook-registration mechanism is unclear after reading plugin.json + hooks/.

REPORT (print this when DONE — the manager needs it verbatim):
  - Baseline N and final pytest line (passed/skipped).
  - Files created/edited (exact paths) + how you registered the probe (which mechanism, which events).
  - The exact log path the probe writes to.
  - A 6-8 line RUNBOOK for the operator (Süleyman) to collect cross-environment data:
      "Run ONE environment at a time. In <env>, open a session in the engine repo, type any short prompt
       (e.g. 'merhaba'), let one tool call happen. Then run:
         python3 scripts/hooks/env_probe_report.py
       Send the manager the FULL contents of ~/.config/pseo/hook-probe.jsonl AND say which environment it
       was (VSCode / Mac app / CLI). Then DELETE that file before testing the next environment."
  - Any DURUR hit, any out-of-scope need you noticed, any assumption you made.
  - How to REMOVE the probe later (which lines/files to revert) — it is temporary diagnostic instrumentation.
```
