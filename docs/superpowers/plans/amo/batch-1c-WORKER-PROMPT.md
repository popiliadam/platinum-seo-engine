# AMO Batch 1c — Intent Router (one-voice UserPromptSubmit + marker lifecycle) (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 1's third batch. The intent router is the L1 of the
> orchestrator: it reads each user prompt, and on a canonical-workflow match injects a single "run
> /pseo-run <workflow> <slug>" instruction + writes an intent marker the denetçi (batch 2c) will read; on a
> fuzzy/no match it falls back to the existing advisory. It must be the "ONE voice" — so it REPLACES the
> static-bash advisory command in the UserPromptSubmit hook (re-emitting the PSEO-context line itself), rather
> than speaking alongside it. **turn_id is router-ASSIGNED, NOT assumed from the hook payload** (the payload's
> per-turn id is unproven across environments; session_id IS proven, batch 0a). The "current-turn only / never
> block on an older marker" property is delivered structurally: the router rewrites the single per-session
> intent marker on EVERY prompt (declared on a match, superseded otherwise), so the marker is always the
> current turn's state. File-disjoint from batch 1b (orchestration/**) → runs in a parallel window. It adds a
> schema → the manager applies the D10 bump (pre-authorized in the prompt). Paste the block into a fresh
> Claude Code session (Opus 4.8, 1M context) rooted at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 1c of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and
print the REPORT (the manager reviews + commits).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N is ~1803) BEFORE any change. END green, passed strictly >= N.
- TDD: failing test first, watch it fail, then implement. Never fake red.
- House style: immutability (build NEW objects, never mutate inputs); no print/console debug in shipped
  code EXCEPT the router's intended stdout (that IS its product — a hook context line); no hardcoded secrets;
  functions <50 lines; files 200-400 lines. Pass timestamps/ids IN as args where logic depends on them
  (pure, testable) — generate them only in the thin main().
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else -> STOP + report. (The hook-registry test
  + README + the D10 schema-count guards ARE in scope as pre-authorized satellites; see SCOPE.)

WHY THIS BATCH (read carefully):
AMO wants: when you state a known intent ("alpha'da aylık bakım yap"), the right workflow GUARANTEED engages.
L1 of that is a UserPromptSubmit hook — the "intent router" — that classifies the prompt:
  * Tier-1 (canonical match to a known workflow): inject a one-line instruction "invoke /pseo-run <workflow>
    <slug>" AND write an intent_declared marker (so the Stop-hook denetçi in batch 2c can detect if the turn
    ended WITHOUT the workflow actually running, and force/flag it).
  * Tier-2 (no match, or >=2 workflows collide): fall back to the existing "whats-next" advisory ONLY, no marker.
It must be the SINGLE voice per prompt (today a static bash command always prints a context line + a "Drift
router" advisory; the router subsumes that). The denetçi (2c) and /pseo-run (1d) are SEPARATE later batches —
you build the router + the marker contract + the one-voice wiring ONLY. Do NOT build the Stop hook or the
command here.

CONFIRMED FACTS (manager-verified 2026-06-05 — do not re-derive):
- The binding key proven to exist in every hook payload is `session_id` (batch 0a/0b/D9). A per-TURN id is
  NOT proven across VSCode/Mac-app/CLI, so DO NOT read a turn_id from the payload. Instead the router ASSIGNS
  turn_id + intent_id itself (generate in main(); pass into the pure logic). "Current-turn only" is delivered
  structurally: ONE marker per session, REWRITTEN every prompt — so it always reflects the current turn.
- Binding resolver to reuse (batch 0b): `scripts/state/session_binding.py`:
    resolve_session_project(workspace_root, *, arg=None, session_id=None, strict=False) -> str | None
      (precedence arg -> session marker(session_id) -> active.json; strict=False returns None when unbound)
    current_session_id(payload=None, environ=os.environ) -> str | None
      (payload.session_id in HOOK context, else $CLAUDE_CODE_SESSION_ID)
    resolve_workspace_root(environ=os.environ) -> Path | None
      (~/.config/pseo/config.json["workspace_root"] -> PSEO_WORKSPACE_ROOT env -> None)
    sessions_dir(workspace_root) -> workspace_root/"shared"/"sessions"   (where the binding marker lives)
    _atomic_write_json(target, payload)  (tempfile -> fsync -> os.replace; reuse for the intent marker)
- The UserPromptSubmit hook (`hooks/user-prompt-submit.json`) currently runs TWO command entries:
    (1) an inline bash that echoes "PSEO context: workspace=… project=…" THEN
        "Drift router: when uncertain about next step invoke the meta:whats-next skill …".
    (2) `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/env_probe.py"` (batch-0a temporary probe — LEAVE IT).
  For UserPromptSubmit, a hook's STDOUT is injected into the model's context. You REPLACE command (1) with the
  router (so there is ONE voice); you must have the router itself re-emit the "PSEO context: …" line (do not
  lose it). Leave command (2) (env_probe) exactly as-is.
- A NEW wired runtime hook script MUST be registered or a guard fails: add `intent_router.py` to
  `RUNTIME_HOOK_SCRIPTS` in `tests/hooks/test_hook_scripts_runtime_vs_ci.py` (~line 27) AND add a row to the
  runtime table in `scripts/hooks/README.md` (~lines 15-19). (This is the same pattern env_probe/audit_post
  followed.)
- D10 count-guard: you ADD `schemas/intent-marker.schema.json` (a *.schema.json), which trips TWO guards.
  Apply both (pre-authorized) and FLAG them in the REPORT: (a) `tests/schemas/test_json_schema_draft_consistency.py`
  currently asserts `count == 22` in `test_schemas_count_is_twenty_two` -> bump to 23 (rename to
  `_twenty_three`, update docstring); (b) `.claude-plugin/marketplace.json` currently says "23 schemas" ->
  "24 schemas" (change ONLY that substring). plugin.json carries no tested schema count -> do NOT touch it.
- intent_declared / intent_id / turn_id / intent_superseded are GREENFIELD (no existing code).

ORIENT FIRST (read, do not change):
- `hooks/user-prompt-submit.json` (the 2 commands; you swap #1).
- `schemas/session-marker.schema.json` — COPY its house style for the intent-marker schema (draft-07,
  $id `http://platinum-seo-engine/schemas/intent-marker`, title "X v1.0", rich who-writes/who-reads
  description, additionalProperties:false, schema_version const "1.0").
- `scripts/state/session_binding.py` — the resolver/marker helpers above + how it reads stdin/payload + the
  atomic write. Mirror its style; reuse its helpers (import them).
- `scripts/hooks/audit_post_tool_use.py` — an existing hook script's main()/stdin-read/try-except-never-crash
  shape. Mirror it (the router must NEVER crash the hook chain; on any internal error, fall back to the
  advisory + exit 0).
- `tests/hooks/test_hook_scripts_runtime_vs_ci.py` (RUNTIME_HOOK_SCRIPTS) + `scripts/hooks/README.md` (table).
- `tests/hooks/test_audit_post_tool_use.py` / `tests/state/test_session_binding.py` for test style (monkeypatch
  HOME, tmp workspace, subprocess a hook script with piped stdin).

SCOPE — create/modify ONLY:
  NEW  scripts/hooks/intent_router.py                       (the router: classify + emit one voice + write marker)
  NEW  schemas/intent-marker.schema.json                    (the intent marker contract the denetçi 2c reads)
  NEW  tests/hooks/test_intent_router.py                    (TDD)
  EDIT hooks/user-prompt-submit.json                        (replace static-bash advisory cmd #1 with the router; keep env_probe cmd #2)
  EDIT tests/hooks/test_hook_scripts_runtime_vs_ci.py       (add intent_router.py to RUNTIME_HOOK_SCRIPTS)
  EDIT scripts/hooks/README.md                              (add the intent_router.py runtime-table row)
  EDIT tests/schemas/test_json_schema_draft_consistency.py  (D10: assert 22 -> 23; rename + docstring)
  EDIT .claude-plugin/marketplace.json                      (D10: "23 schemas" -> "24 schemas")

SPEC — schemas/intent-marker.schema.json (the marker written to shared/sessions/<session_id>.intent.json):
  draft-07; $id .../schemas/intent-marker; additionalProperties:false;
  required ["session_id","turn_id","intent_id","status","declared_at"];
  properties:
    schema_version  : const "1.0" (optional)
    session_id      : string minLength 1 (the Claude session UUID; SAME as the binding marker's)
    turn_id         : string minLength 1 (router-ASSIGNED per prompt; an opaque ordering/audit stamp — NOT a
                      payload field)
    intent_id       : string minLength 1 (router-ASSIGNED unique id for this declared intent)
    status          : enum ["declared","superseded","consumed"] (declared on a Tier-1 match; superseded when a
                      later prompt changes/abandons intent; consumed set by the orchestrator/denetçi when the
                      workflow run actually starts — written by a LATER batch, declared here)
    workflow        : string pattern "^[a-z][a-z0-9-]*$" (the matched workflow key, e.g. "monthly"; required
                      when status=declared via an allOf)
    slug            : string pattern "^[a-z][a-z0-9-]*$" (the bound project; may be absent if unbound)
    command         : string minLength 1 (the instruction injected, e.g. "/pseo-run monthly vento")
    declared_at     : string minLength 1 (local ISO-8601, datetime.now().isoformat())
    prompt_excerpt  : string (OPTIONAL, <=160 chars, redaction-safe — do NOT store the full prompt; a short
                      excerpt for audit only. If you include it, truncate hard.)
  Add an allOf: status=="declared" requires ["workflow","command"].

SPEC — scripts/hooks/intent_router.py (pure logic + a thin never-crashing main):
- A module-level CANONICAL_WORKFLOWS table (data-driven so Phase 3 adds workflows without code change). Seed
  with ONE entry for the Phase-1 reference workflow:
    "monthly": { "patterns": [list of lowercased phrases that canonically mean monthly maintenance, e.g.
                  "aylık bakım", "aylik bakim", "monthly maintenance", "aylık bakim"],
                 "command": "/pseo-run monthly {slug}" }
  (Match on a normalized lowercased prompt; keep patterns specific enough to avoid false Tier-1 on unrelated
  prompts. Do NOT over-match — when unsure, Tier-2.)
- `classify(prompt: str) -> tuple[str | None, list[str]]`: return (workflow_key_or_None, matched_keys). A
  prompt matching exactly ONE workflow -> Tier-1 (that key). ZERO matches -> Tier-2 (None). >=2 distinct
  workflows match -> Tier-2 (None) — a collision is advisory-only per spec (return the matched list so the
  caller can log it). Pure; no IO.
- `build_marker(session_id, *, turn_id, intent_id, status, declared_at, workflow=None, slug=None,
   command=None, prompt_excerpt=None) -> dict`: emit ONLY declared keys (additionalProperties:false). Defensive
  enum check on status.
- `intent_marker_path(workspace_root, session_id) -> Path` = sessions_dir(workspace_root)/(session_id +
   ".intent.json").
- `route(prompt, *, session_id, workspace_root, turn_id, intent_id, declared_at) -> dict` (the pure core):
    1. wf, matched = classify(prompt).
    2. slug = resolve_session_project(workspace_root, session_id=session_id, strict=False) if workspace_root.
    3. If wf is not None (Tier-1): command = CANONICAL_WORKFLOWS[wf]["command"].format(slug=slug or "<slug>");
       marker = build_marker(..., status="declared", workflow=wf, slug=slug, command=command,...);
       voice = the Tier-1 instruction line(s) (see below).
       (If slug is None — unbound — STILL Tier-1 but the voice tells the user to /pseo-bind first; marker slug
        omitted. Do not fabricate a slug.)
    4. Else (Tier-2): marker = build_marker(..., status="superseded", ...)  # supersede any prior declared
       intent so the denetçi never blocks on a stale cross-turn intent; voice = the advisory line.
    Return {"marker": marker, "voice": str, "tier": 1|2, "matched": matched}. PURE — caller writes the file +
    prints the voice.
- main():
    * Read stdin JSON (tolerant: empty/garbage -> {}); session_id = current_session_id(payload); workspace_root
      = resolve_workspace_root(); now_iso = datetime.now().isoformat(); turn_id/intent_id = generated
      (e.g. uuid4 hex; turn_id may embed now for orderability).
    * If no session_id or no workspace_root -> print ONLY the advisory voice (degrade gracefully, no marker)
      and exit 0.
    * Call route(...); write the marker via _atomic_write_json(intent_marker_path(ws, session_id), marker);
      print the "PSEO context: workspace=<ws> project=<slug|none>" line THEN the voice to stdout; exit 0.
    * WRAP ALL of main in try/except -> on ANY error, print the advisory voice and exit 0 (NEVER crash the
      hook chain; NEVER block a prompt).
- The "voices" (stdout — this is the hook's product):
    Context (always): "PSEO context: workspace=<ws> project=<slug-or-none>"
    Tier-1 (bound):   a one-line, model-actionable instruction, e.g.
        "➤ Niyet: aylık bakım algılandı → çalıştır: /pseo-run monthly <slug>"
    Tier-1 (unbound): "➤ Niyet: aylık bakım algılandı, ama oturum bir projeye bağlı değil → önce: /pseo-bind <slug>"
    Tier-2:           the existing advisory, preserved verbatim:
        "Drift router: when uncertain about next step invoke the meta:whats-next skill (Phase 5+) — until then consult docs/PHASE_STATUS.md."
  (Turkish operator-facing strings are fine — the project is bilingual; keep them short.)

SPEC — hooks/user-prompt-submit.json: replace the FIRST command entry (the inline bash) with a command entry
running `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/intent_router.py"` (timeout ~10, a statusMessage like
"AMO intent router…"). KEEP the second command entry (env_probe) byte-identical. The file must remain valid
JSON (sanity-check by parsing). Do NOT add/remove other events.

TDD — tests/hooks/test_intent_router.py (write FIRST, RED, then implement):
  1. classify: a canonical "aylık bakım" prompt -> ("monthly", ["monthly"]); an unrelated prompt ("merhaba")
     -> (None, []); (when a 2nd workflow is later added this returns None on collision — for now assert single
     match + no match).
  2. route Tier-1 bound: with a tmp workspace bound to slug "vento" (write a session binding marker first via
     session_binding), a monthly prompt -> tier 1, marker.status=="declared", marker.workflow=="monthly",
     marker.command=="/pseo-run monthly vento", voice contains "/pseo-run monthly vento".
  3. route Tier-1 unbound: no binding -> tier 1, marker has NO slug, voice tells the user to /pseo-bind.
  4. route Tier-2: "merhaba" -> tier 2, marker.status=="superseded", voice == the Drift-router advisory.
  5. marker round-trips + validates against schemas/intent-marker.schema.json (Draft7Validator, zero errors)
     for both a declared and a superseded marker; a declared marker missing workflow/command FAILS validation
     (allOf).
  6. main() via subprocess: pipe a JSON payload {session_id, prompt:"aylık bakım yap"} with a tmp workspace
     (monkeypatch HOME so ~/.config/pseo points at tmp, OR pass workspace via the config file) -> exit 0, the
     intent marker file exists at shared/sessions/<sid>.intent.json + validates, stdout contains the context
     line + the Tier-1 instruction.
  7. main() robustness: empty stdin / missing session_id -> exit 0, prints the advisory, writes NO marker, no
     traceback.
  ALL filesystem tests use tmp_path + monkeypatched HOME; never touch the real ~/.config or workspace.

METHOD:
  1. Baseline pytest (N ~1803).
  2. Tests RED.
  3. Implement intent_router.py + intent-marker.schema.json (GREEN for the router/schema tests).
  4. Wire the hook (swap cmd #1); register in RUNTIME_HOOK_SCRIPTS + README; apply the 2 D10 bumps.
  5. Sanity: parse every hooks/*.json + schemas/*.json
     (`python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('hooks/*.json')+glob.glob('schemas/*.json')]"`).
  6. FULL suite; passed >= N, 0 failed. `git status --short` = ONLY the 8 scoped files.
  7. @code-reviewer + @verifier (inline); address findings.

DURUR (stop + report):
  - Replacing the static-bash command would change UserPromptSubmit behavior beyond "one voice" (e.g. another
    command depends on its output) — report rather than work around.
  - The marketplace schema count is not the literal "23 schemas" you expect, or *.schema.json count != 22 at
    baseline — STOP and report the real numbers (do not guess).
  - You discover you must build the Stop-hook denetçi or /pseo-run to make a test pass — that is 2c / 1d, out
    of scope; report it.

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line; files created/edited + new test count.
  - The CANONICAL_WORKFLOWS seed + the Tier-1/Tier-2 rule (and how a future 2nd workflow makes a collision
    Tier-2).
  - The intent-marker required[] + status enum + the declared->requires(workflow,command) allOf.
  - Proof the router NEVER crashes the hook chain (the try/except->advisory->exit 0 path) + that it re-emits
    the PSEO-context line (one voice, static bash removed).
  - Proof the marker is rewritten every prompt (declared on Tier-1, superseded on Tier-2) so "current-turn
    only" holds without a payload turn_id.
  - "D10 count-guard bumps:" BEFORE/AFTER of the draft-consistency assert (22->23) + marketplace ("23->24
    schemas") for the manager to re-verify vs filesystem.
  - Confirmation intent_router.py is in RUNTIME_HOOK_SCRIPTS + the README table; env_probe cmd #2 untouched;
    plugin.json untouched.
  - Any DURUR / assumption / out-of-scope need (e.g. what you think the denetçi 2c needs from this marker).
```
