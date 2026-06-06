# AMO Batch 2c — Denetçi Stop-Hook (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 1 complete + pushed (HEAD `9b5d238`, suite **1891/0**). The
> spec's "2c" bundled the denetçi + the correctness oracle; the manager SPLIT it (precedent: 1b→1b+1b2) into
> **2c = denetçi Stop-hook** and **2d = correctness oracle** — they share no code (a runtime hook vs an offline
> reporting script) and splitting keeps the hard safety phase in small reviewable batches. Both still ship in
> Faz 2 (D5 honored). This batch (2c) is **file-disjoint from 2a (consent ledger) AND 2d (oracle)**, so it runs
> in a parallel window. It touches `hooks/stop.json` + a new `scripts/hooks/denetci.py` + the hook-script
> classification (`RUNTIME_HOOK_SCRIPTS` + `scripts/hooks/README.md`) + tests — NO command, NO schema, so NO
> D10 count-guard. Paste the block below into a fresh Claude Code session (Opus 4.8, 1M context) at the repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 2c of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). SIBLING workers may be running batch 2a (consent ledger:
schemas/consent.schema.json, scripts/state/consent_ledger.py, commands/pseo-approve.md) and batch 2d (oracle:
scripts/reporting/orchestration_metrics.py) in parallel — those files are NOT yours. If you ever feel you need
a file outside your SCOPE list, STOP and report it.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 1891) BEFORE any change. END green with passed >= N, 0 failed.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability; no leftover debug prints (a hook writes ONLY its decision JSON to stdout +
  optional stderr notes — see SPEC); small functions (<50 lines); files 200-400 lines normal.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.

WHY THIS BATCH EXISTS (read carefully):
AMO guarantees that when an operator states a known intent ("alpha'da aylık bakım yap"), the workflow actually
RUNS and is verified — or the turn does not silently end. Batch 1c built the L1 intent router (it writes an
intent marker when a prompt declares a known workflow). Batch 1a/1b built the coverage record (the per-run
proof of what ran + a verdict). THIS batch builds L3 — the DENETÇİ (auditor): a Stop hook that, at the end of
a turn, checks "did the workflow this turn OWED actually run and pass?" and:
  - if it never ran -> BLOCK the turn end with a Turkish one-line fix command (force completion);
  - if it ran but is incomplete/failed -> BLOCK with the remediation fix command;
  - if it PAUSED on an EXTERNAL dependency (GSC/DFS outage) -> ALLOW the turn to end but flag it RED (we don't
    punish the operator for an outage; `--resume` retries);
  - if it passed, or no intent was declared this turn -> allow the turn to end silently (no-op).
This is the safety half of "guaranteed engagement" (spec G1/G2). It is READ-ONLY on existing state (reads the
intent marker + the coverage record; writes neither) and NON-BLOCKING-ON-ERROR (any internal failure -> allow
turn-end; it must NEVER wedge the session).

CONFIRMED FACTS (verified against the code 2026-06-06 — do not re-derive):
- Stop-hook decision contract (Claude Code): a Stop hook BLOCKS the turn from ending by writing a JSON object
  to STDOUT: {"decision": "block", "reason": "<text the model sees>"} and exiting 0. Empty stdout + exit 0
  ALLOWS the turn to end. The input payload (hook stdin JSON) includes "stop_hook_active" (bool) — TRUE when
  the model is ALREADY continuing because of a PRIOR Stop block. When stop_hook_active is true the denetçi MUST
  NOT block again (that would loop / burn the block cap) -> allow turn-end. (If unsure, confirm against the
  Claude Code Stop-hook docs; this is the established contract.)
- The EXISTING Stop chain is `hooks/stop.json`: handler.matcher == "" with hooks = [ stop_validation.py (FIRST),
  env_probe.py (batch-0a temporary) ]. The contract test `tests/hooks/test_stop_validation.py::
  test_stop_hook_config_valid` asserts `len(handler["hooks"]) >= 1` (already D8-relaxed) and that
  `handler["hooks"][0]` is stop_validation.py with a CLAUDE_PLUGIN_ROOT path + timeout>=10. So you MUST keep
  stop_validation.py as the FIRST command; add denetci.py as a NEW command entry (index 1 is fine), leaving
  env_probe.py present. That test must still pass unchanged.
- The intent marker (batch 1c) is written by `scripts/hooks/intent_router.py` to
  `{workspace_root}/shared/sessions/{session_id}.intent.json` (helper:
  `intent_router.intent_marker_path(workspace_root, session_id)`). Its shape (schemas/intent-marker.schema.json):
  required [session_id, turn_id, intent_id, status, declared_at]; status enum [declared, superseded, consumed];
  when status=="declared" it ALSO carries `workflow` (e.g. "monthly"), `command` (e.g. "/pseo-run monthly vento")
  and usually `slug` (absent if the session is unbound — the router never fabricates a slug). The marker is
  REWRITTEN every prompt, so it always reflects the CURRENT turn (there is no per-turn id to match — "current
  turn" is structural). A `declared` marker == "a workflow is OWED this turn".
- The coverage record (batch 1a, frozen `schemas/coverage.schema.json`) is written by the orchestrator to
  `{workspace_root}/projects/{slug}/_state/coverage/{run_id}.json`. Read its `verdict` (enum: pass | incomplete
  | paused | failed) and `required_satisfied`. Path helper: `scripts.orchestration.coverage.coverage_path(
  workspace_root, slug, run_id)`; the COVERAGE DIR is that path's parent (`projects/{slug}/_state/coverage/`).
- The operator-remediation surface is ALREADY built (batch 1d): `scripts/orchestration/remediation.py` exposes
  `remediation(coverage_record, *, slug, workflow="monthly") -> dict | None` (None iff verdict=="pass") and
  `render(remediation_dict) -> str` (a compact Turkish block whose LAST line is the `/pseo-run … --resume` fix
  command; it already frames `paused` as an external dependency). REUSE these — do NOT reinvent the fix text.
- The binding primitive (batch 0b) `scripts/state/session_binding.py`: `current_session_id(payload)` (hook
  stdin session_id -> env), `resolve_workspace_root()` (~/.config/pseo/config.json -> env). Use both. Filesystem
  tests MUST monkeypatch HOME (resolve_workspace_root reads ~/.config/pseo/config.json).
- A NEW wired hook script MUST be added to `RUNTIME_HOOK_SCRIPTS` in
  `tests/hooks/test_hook_scripts_runtime_vs_ci.py` AND named in `scripts/hooks/README.md`, or
  `test_every_hook_script_is_classified` + `test_readme_documents_both_classes` FAIL. (env_probe/audit/intent
  set the pattern.) denetci.py is RUNTIME (wired into stop.json).
- Bare-hook sys.path: a hook run as a subprocess needs `scripts.*` importable. Mirror intent_router.py's top:
  insert `os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parents[2])` into sys.path
  BEFORE importing scripts.* (NOT relying on cwd).
- This batch writes NO state, adds NO schema/command (so NO D10 count-guard), and does NOT modify intent_router,
  coverage, remediation, session_binding, or stop_validation — it only READS their outputs + wires one hook.

ORIENT FIRST (read, do not change yet):
- `hooks/stop.json` (the chain you extend) + `tests/hooks/test_stop_validation.py` (the contract you must keep
  green — stop_validation stays FIRST; len>=1).
- `scripts/hooks/intent_router.py` — `intent_marker_path`, the marker shape, the non-crashing main() wrapper +
  the sys.path bootstrap you mirror.
- `schemas/intent-marker.schema.json` + `schemas/coverage.schema.json` — the two contracts you read.
- `scripts/orchestration/coverage.py` (`coverage_path`) + `scripts/orchestration/remediation.py`
  (`remediation` + `render`) — you call these.
- `scripts/hooks/audit_post_tool_use.py` — another non-crashing runtime hook; the RUNTIME_HOOK_SCRIPTS +
  README registration pattern.
- `scripts/hooks/README.md` — add a §1 entry for denetci.py beside intent_router/audit/stop_validation.

SCOPE — create/modify ONLY these files:
  NEW  scripts/hooks/denetci.py                              (the L3 Stop-hook auditor; see SPEC)
  NEW  tests/hooks/test_denetci.py                           (the decision matrix + wiring + non-crash)
  EDIT hooks/stop.json                                       (add denetci.py as a 2nd command; stop_validation STAYS first)
  EDIT tests/hooks/test_hook_scripts_runtime_vs_ci.py        (add "denetci.py" to RUNTIME_HOOK_SCRIPTS)
  EDIT scripts/hooks/README.md                               (document denetci.py under the runtime/§1 hooks)

SPEC — scripts/hooks/denetci.py:
  Imports (after the sys.path bootstrap): from scripts.state.session_binding import current_session_id,
  resolve_workspace_root; from scripts.hooks.intent_router import intent_marker_path; from
  scripts.orchestration.coverage import coverage_path; from scripts.orchestration.remediation import
  remediation, render. (json, os, sys, pathlib as needed.)

  Pure helpers (no IO except the explicit readers; build NEW objects):
    - _read_json(path) -> dict | None: parse a JSON object; None on missing/invalid (never raises).
    - load_intent_marker(workspace_root, session_id) -> dict | None: _read_json(intent_marker_path(...)).
    - coverage_dir(workspace_root, slug) -> Path: coverage_path(workspace_root, slug, "x").parent
        (i.e. projects/{slug}/_state/coverage/).
    - freshest_fresh_coverage(workspace_root, slug, since_mtime) -> dict | None:
        glob coverage_dir/*.json; keep files whose `Path.stat().st_mtime >= since_mtime`; among those return the
        JSON of the one with the GREATEST mtime; None if the dir is missing or no file is fresh. (This is THE
        freshness gate: the intent marker was (re)written at turn start, so a coverage record written THIS turn
        has mtime >= the marker's mtime; a STALE prior-run record has mtime < it and is correctly ignored — so
        a week-old pass can never satisfy a fresh intent. Compare FILE mtimes only; do NOT parse declared_at.)
    - decide(marker, coverage_record) -> tuple[str, str | None]:
        PURE. Returns (action, reason) where action in {"allow", "block", "flag"} and reason is the
        model/operator text (None for allow).
          * marker is None OR marker.get("status") != "declared"  -> ("allow", None)   # nothing owed
          * coverage_record is None  (owed workflow did not run this turn, the non-start gate) ->
                ("block", <non-start reason>)  where the reason is a Turkish 2-line block:
                  f"⚠️  Niyet algılandı ({marker.get('workflow')}) ama bu turda workflow çalışmadı.\n"
                  f"Tamamlamak için çalıştır:\n{marker.get('command') or '/pseo-run <workflow> <slug>'}"
                (marker['command'] already encodes the exact /pseo-run line, incl. <slug> when unbound.)
          * else verdict = coverage_record.get("verdict"):
              - "pass"   -> ("allow", None)
              - "paused" -> ("flag",  render(remediation(coverage_record, slug=<slug>, workflow=<workflow>)))
                            # external dependency: allow turn-end, surface RED note
              - otherwise (incomplete/failed/unknown) ->
                            ("block", render(remediation(coverage_record, slug=<slug>, workflow=<workflow>)))
        Use marker.get("slug") and marker.get("workflow") (default "monthly") for the remediation call. Note
        remediation() returns None only for verdict=="pass" (which we already handled), so render() always has
        a dict here.

  main() -> int (NON-CRASHING wrapper, mirrors intent_router.main):
    try:
      payload = parse stdin JSON (never raises -> {} on bad input)
      if bool(payload.get("stop_hook_active")):   # already continuing from a prior block -> never re-block
          return 0
      session_id = current_session_id(payload); workspace_root = resolve_workspace_root()
      if not session_id or workspace_root is None: return 0      # cannot resolve -> allow
      marker = load_intent_marker(workspace_root, session_id)
      if not marker or marker.get("status") != "declared": return 0   # nothing owed -> allow
      slug = marker.get("slug")
      record = None
      if slug:
          since = intent_marker_path(workspace_root, session_id).stat().st_mtime
          record = freshest_fresh_coverage(workspace_root, slug, since)
      action, reason = decide(marker, record)
      if action == "block":
          print(json.dumps({"decision": "block", "reason": reason}))   # STDOUT JSON blocks the turn
      elif action == "flag":
          sys.stderr.write("[denetçi] " + (reason or "") + "\n")        # allow turn-end, surface RED note
      return 0
    except Exception:
      return 0   # NEVER wedge the Stop chain
  if __name__ == "__main__": sys.exit(main())

  Module docstring: cite that it is the AMO L3 denetçi (spec §3 L3 / G1-G2), wired into hooks/stop.json as the
  2nd Stop command (stop_validation stays first), READ-ONLY, non-blocking-on-error, reuses remediation (1d),
  reads the intent marker (1c) + coverage record (1a), freshness via file mtime vs the marker.

SPEC — hooks/stop.json: insert denetci.py as a NEW command object in handler.hooks, AFTER stop_validation.py
  (keep it FIRST) — e.g. order [stop_validation.py, denetci.py, env_probe.py]. Use the same shape:
    { "type": "command",
      "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/denetci.py\"",
      "timeout": 15,
      "statusMessage": "AMO denetçi: intent/coverage audit..." }
  Do not alter the stop_validation or env_probe entries.

SPEC — tests/hooks/test_hook_scripts_runtime_vs_ci.py: add the string "denetci.py" to the RUNTIME_HOOK_SCRIPTS
  set, with a short comment (like the intent_router/audit entries) noting it is the batch-2c Stop denetçi wired
  into hooks/stop.json. Change nothing else.

SPEC — scripts/hooks/README.md: add denetci.py to the runtime-hooks section (§1) with a one-line description
  (Stop-hook auditor: blocks turn-end on an unfinished owed workflow with a Turkish fix command; allow+flag on
  external `paused`). Keep the file's structure.

TDD — write these FIRST (RED), then implement (GREEN). Prefer unit-testing the PURE `decide()` +
`freshest_fresh_coverage()` for the matrix (fast), plus a few subprocess end-to-end smoke tests for the wiring
(mirror test_stop_validation.py's subprocess+env-CLAUDE_PLUGIN_ROOT pattern). Build markers/coverage in tmp_path;
monkeypatch HOME so resolve_workspace_root reads a tmp ~/.config/pseo/config.json.
  decide() matrix (pure):
    1. marker None -> ("allow", None).
    2. marker status "superseded" -> ("allow", None).
    3. declared + coverage verdict "pass" -> ("allow", None).
    4. declared + coverage verdict "incomplete" -> ("block", reason contains "/pseo-run" and "--resume").
    5. declared + coverage verdict "failed" -> ("block", reason has the fix command).
    6. declared + coverage verdict "paused" -> ("flag", reason framed as external dependency / --resume).
    7. declared + coverage_record None (non-start) -> ("block", reason contains marker['command'] and
       "çalışmadı").
  freshness:
    8. a coverage file with mtime >= since -> returned; with mtime < since -> ignored (None). (Set mtimes via
       os.utime to simulate a stale prior run vs a fresh one.)
    9. when two fresh records exist, the one with the GREATEST mtime is returned.
  main() end-to-end (subprocess, like test_stop_validation):
    10. declared marker + a FRESH incomplete coverage record -> stdout is JSON with decision=="block"; exit 0.
    11. declared marker + a FRESH pass coverage record -> stdout EMPTY (no decision); exit 0.
    12. stop_hook_active=true in the payload + declared+incomplete -> stdout EMPTY (no re-block); exit 0.
    13. declared marker but NO coverage file (non-start) -> stdout decision=="block" with the marker command.
    14. paused coverage -> stdout EMPTY, stderr contains "[denetçi]"; exit 0.
    15. non-crash: empty stdin / bogus payload / unresolvable workspace -> exit 0, no stdout decision.

METHOD:
  1. Baseline pytest (record N == 1891).
  2. Write test_denetci.py (RED). Run; watch the decide/import failures.
  3. Author denetci.py (GREEN the matrix), wire stop.json, register in RUNTIME_HOOK_SCRIPTS + README.
  4. Confirm `tests/hooks/test_stop_validation.py` + `test_hook_scripts_runtime_vs_ci.py` BOTH still pass
     (stop_validation still first; denetci classified + documented).
  5. Full suite; passed >= N, 0 failed.
  6. Self-review @code-reviewer + @verifier (inline): the hook NEVER raises out of main(); blocks ONLY via
     stdout JSON; respects stop_hook_active; reads but never writes the marker/coverage; freshness uses file
     mtime (not declared_at parsing); stop_validation remains the FIRST Stop command.

DURUR (stop + report):
  - A denetci/stop denetçi already exists (grep) — report rather than duplicate.
  - Keeping stop_validation FIRST while adding denetci breaks test_stop_validation for an unexpected reason —
    STOP + report (do not weaken that contract test).
  - You discover the Stop-hook block contract differs from {"decision":"block","reason":...} on this Claude
    Code version — STOP + report the real contract (do not guess a format that silently no-ops).
  - You feel you must edit intent_router / coverage / remediation / 1d driver to correlate the run — STOP +
    report (the mtime-freshness design is meant to need NONE of that; if it truly doesn't work, the manager
    decides the correlation contract).
  - Any existing test regresses for a reason outside this batch's files.

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line (passed/skipped/failed).
  - Files created/edited + new-test count.
  - The decide() matrix you implemented (the 6 branches) + confirmation paused => allow+flag (NOT block) and
    non-start => block-with-marker-command.
  - Quote the freshness rule (coverage mtime >= intent-marker mtime) and confirm it ignores a stale prior pass.
  - Quote the stop_hook_active guard (no re-block) and the non-crashing main() wrapper (any error -> return 0).
  - Confirmation stop_validation.py is STILL the FIRST Stop command + test_stop_validation passes unchanged.
  - Confirmation denetci.py is in RUNTIME_HOOK_SCRIPTS + README, and you added NO schema/command (no D10).
  - Any DURUR hit, out-of-scope need, or assumption.
```
