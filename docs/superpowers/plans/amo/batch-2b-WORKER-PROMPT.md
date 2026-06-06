# AMO Batch 2b — Outward-Action Consent Gate (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 2 wave-1 is COMPLETE + pushed (2a consent ledger `de44bbd`,
> 2c denetçi `e50d655`, 2d oracle `7234ccf`; suite **1967/0**, HEAD `9230073`). This is **wave-2** — the
> PreToolUse gate that actually DENIES an irreversible/outward action (git push / rm / exfil POST / sitemap
> submit / Indexing URL_UPDATED) unless the operator approved it **in this session** (`/pseo-approve`, batch 2a).
> **Operator decision (Süleyman 2026-06-06): per-SESSION consent** — a consent entry authorizes the action only
> within the Claude session that granted it (match on `session_id` + `action` + `target_hash`), so the gate
> stays READ-ONLY (reuses 2a's `read_entries`+`verify_chain`, needs no run_id mechanism, no consumption log).
> This batch runs SOLO (wave-1 done, nothing parallel). The AI-disclosure PostToolUse surface-rescan + the
> secret-bytes scan + the drift F-rule are SPLIT into later batches (2e/2f) to keep this gate focused.
> Paste the block below into a fresh Claude Code session (Opus 4.8, 1M context) at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 2b of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active right now, but stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 1967 at HEAD 9230073) BEFORE any change. END green with
  passed strictly >= N (your new tests add to it) and 0 failed.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (build NEW objects, never mutate inputs); no leftover debug prints (a hook writes
  ONLY to stderr + its exit code — see SPEC); small functions (<50 lines); files 200-400 lines normal.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.

WHY THIS BATCH EXISTS (read carefully):
AMO's smart-autonomy promise is safe ONLY because irreversible / outward actions are machine-DENIED unless the
operator consented (spec G4). Batch 2a built the consent ledger (`projects/{slug}/_state/consent.jsonl`,
append-only + hash-chained) + the `/pseo-approve` command. THIS batch builds the enforcement half: a PreToolUse
gate that, before a gated action runs, classifies it, hashes its concrete target, and DENIES it unless a
matching consent entry exists FOR THIS SESSION. The gated classes (the 6-value `action` enum 2a froze):
  - git_push     — a Bash `git push` (outward code push)
  - fs_delete    — a Bash `rm` / `unlink` / `rmdir` / `shred` (irreversible delete)
  - net_post     — a Bash outbound `curl`/`wget` POST (exfil surface; also IndexNow REST POST)
  - mcp_submit   — the MCP tool `mcp__gsc__submit_sitemap` (submits the project sitemap to Google)
  - index_update — Google Indexing-API `URL_UPDATED` (a Bash curl to indexing.googleapis.com — Süleyman's
                   HARD constraint: this needs explicit per-submission consent, never autonomous)
  - (dfs_oversized is DEFERRED to a later hardening batch — do NOT gate DataForSEO here.)

PER-SESSION CONSENT (the operator-chosen model — match EXACTLY this):
A pending gated action (action, target) is ALLOWED iff the session's bound project's consent ledger holds an
INTACT-CHAIN entry with `session_id == THIS session` AND `action == this action` AND `target_hash == sha256 of
this target`. A consent from a DIFFERENT session (or a tampered chain) does NOT authorize. run_id is NOT used
for matching (it is audit provenance only) — so the gate needs no run_id mechanism and stays READ-ONLY.

CONFIRMED FACTS (verified against the code 2026-06-06 — do not re-derive):
- PreToolUse DENY contract in THIS repo = `sys.exit(2)` + a stderr message (the model sees stderr and does not
  run the tool). The existing pre-tool-use hooks use exactly this (the inline excel-lock `sys.exit(2 if blocked
  else 0)`; check_secrets.sh non-zero; validate_content_write.py `return 2`). Use exit 2 to deny, 0 to allow.
- `hooks/pre-tool-use.json` currently has ONE PreToolUse block: matcher "Edit|Write|Bash", 4 command hooks
  (excel-lock inline python; check_secrets.sh; validate_content_write.py; env_probe.py). Your gate must ALSO
  fire on the MCP tool `mcp__gsc__submit_sitemap`, which "Edit|Write|Bash" does NOT match. So add a SEPARATE
  2nd PreToolUse block with matcher "Bash|mcp__gsc__submit_sitemap" wiring your gate (leave the existing block
  untouched). Hooks compose: a Bash call fires both blocks; either can deny. (CHECK for any test pinning the
  pre-tool-use structure/command-count and scope it in if needed — mirror the 1c/0d hook-migration lesson.)
- The PreToolUse stdin payload shape (mirror validate_content_write.py): `{"tool_name": "...", "tool_input":
  {...}, "session_id": "..."}`. For Bash, `tool_input.command` is the command string. For an MCP tool,
  `tool_input` holds the tool's args (for mcp__gsc__submit_sitemap, the sitemap/site — confirm the exact key by
  reading the gsc MCP tool's args; e.g. `feedpath`/`sitemap_url`/`siteUrl`). session_id via
  `session_binding.current_session_id(payload)`.
- The binding primitive (2a/0b) `scripts/state/session_binding.py`: `current_session_id(payload)`,
  `resolve_workspace_root()`, `resolve_session_project(ws, session_id=..., strict=False)` → the session's slug
  (None if unbound). Filesystem tests MUST monkeypatch HOME.
- The consent module (2a) `scripts/state/consent_ledger.py`: `target_hash(target)` (sha256 hex — the gate MUST
  use THIS so writer+gate hash identically), `read_entries(ws, slug)`, `verify_chain(entries)`. You ADD
  `has_session_consent` to this module (see SPEC) — additive, do NOT change the frozen schema or existing fns.
- rm-family + redirect classification reference: `scripts/state/events_writer.py` `_BASH_DELETE_TOKENS` =
  {rm, rmdir, unlink, shred} and `_classify_bash_command` (leading-token, path-stripped) — mirror that
  leading-token approach so `rm` is detected but `confirm`/`form` are not.
- Live submit mechanisms (read skills/publishing/indexing-ping/SKILL.md to confirm): `mcp__gsc__submit_sitemap`
  = sitemap.xml submit (MCP); IndexNow = a REST POST (Bash curl, → net_post); the per-URL Google Indexing API
  `URL_UPDATED` (`indexing.googleapis.com/v3/urlNotifications:publish`) is "consent-gated, NOT YET WIRED" — when
  it is, it'll be a Bash curl to that host → your net_post/index_update branch catches it. Classify a curl whose
  URL host is `indexing.googleapis.com` as index_update; other outbound POSTs as net_post.
- A NEW wired hook script MUST be added to `RUNTIME_HOOK_SCRIPTS` in
  tests/hooks/test_hook_scripts_runtime_vs_ci.py + named in scripts/hooks/README.md (env_probe/audit/intent/
  denetci set the pattern). Bare-hook sys.path: insert CLAUDE_PLUGIN_ROOT (or parents[2]) before scripts.*
  imports (mirror validate_content_write.py / denetci.py).
- Adds NO schema/command/new-hook-FILE → NO D10 count-guard. (A new BLOCK in an existing hooks/*.json is not a
  new hook file.)

THE DENY-MESSAGE UX (critical — this is what makes consent usable for a non-coder):
On a deny, the gate's stderr MUST tell the operator the EXACT copy-paste approval command, with the SAME target
string the gate hashed — so the operator never guesses. Format (Turkish, model+operator visible):
  `BLOCKED: {action} → {target}  (bu oturumda onay yok)`
  `İzin vermek için çalıştır:  /pseo-approve {run_id_label} {action} "{target}"`
where `run_id_label` = `sess-{first8 of session_id}` (run_id is provenance-only under per-session matching, so
any label works; use a session-derived one for a meaningful audit trail). The operator pastes it (records the
entry with this session_id + action + target_hash); the immediate re-attempt then MATCHES and is allowed.

ORIENT FIRST (read, do not change yet):
- `hooks/pre-tool-use.json` (the block you extend with a 2nd block) + grep tests/ for anything asserting its
  structure (e.g. test_pre_tool_use*, or a test counting its commands) — scope any such pin in.
- `scripts/hooks/validate_content_write.py` — the PreToolUse stdin-parse + exit-2 + fail-open-on-error +
  session/workspace resolution pattern you mirror (your gate is fail-OPEN on NON-gated, fail-CLOSED on gated).
- `scripts/state/consent_ledger.py` — `target_hash`, `read_entries`, `verify_chain`, `has_consent` (your
  `has_session_consent` mirrors has_consent but keys on session_id, not run_id) + its tests
  (tests/state/test_consent_ledger.py) for the test layout.
- `scripts/state/events_writer.py` `_BASH_DELETE_TOKENS` + `_classify_bash_command` (leading-token bash parse).
- `skills/publishing/indexing-ping/SKILL.md` — confirm submit_sitemap is MCP + the Indexing-API curl host.
- `scripts/hooks/denetci.py` (just-shipped 2c) — the bare-hook sys.path bootstrap + non-crashing main shape.

SCOPE — create/modify ONLY these files:
  NEW  scripts/hooks/outward_action_gate.py              (the PreToolUse gate; see SPEC)
  NEW  tests/hooks/test_outward_action_gate.py           (classify matrix + consent allow/deny + deny-message + fail-closed)
  EDIT scripts/state/consent_ledger.py                   (ADD has_session_consent; additive — schema + existing fns untouched)
  EDIT tests/state/test_consent_ledger.py                (ADD has_session_consent tests)
  EDIT hooks/pre-tool-use.json                           (ADD a 2nd block: matcher "Bash|mcp__gsc__submit_sitemap" → the gate)
  EDIT tests/hooks/test_hook_scripts_runtime_vs_ci.py    (ADD "outward_action_gate.py" to RUNTIME_HOOK_SCRIPTS)
  EDIT scripts/hooks/README.md                           (document outward_action_gate.py under §1 runtime hooks)
  >> If grep finds a test pinning pre-tool-use.json's structure, its migration is also IN SCOPE (preserve/strengthen
     the contract — mirror the 0d/1c hook-migration approach) — flag it in REPORT.

SPEC — scripts/state/consent_ledger.py: ADD (do not modify anything existing):
  def has_session_consent(workspace_root, project_slug, *, session_id, action, target_hash) -> bool:
      '''True iff an INTACT chain holds an entry with this session_id + action + target_hash.
      Per-session consent (operator-chosen): a consent only authorizes within the session that granted it.
      A broken chain (tamper) returns False — fail-closed.'''
      entries = read_entries(workspace_root, project_slug)
      intact, _ = verify_chain(entries)
      if not intact: return False
      return any(e.get("session_id") == session_id and e.get("action") == action
                 and e.get("target_hash") == target_hash for e in entries)
  Add it to __all__. (Mirrors has_consent but keys on session_id instead of run_id.)

SPEC — scripts/hooks/outward_action_gate.py (PreToolUse gate; READ-ONLY; exit 2 = deny, 0 = allow):
  Bare-hook sys.path bootstrap (CLAUDE_PLUGIN_ROOT or parents[2]) before importing scripts.*; import
  from scripts.state.session_binding (current_session_id, resolve_workspace_root, resolve_session_project) +
  from scripts.state.consent_ledger (target_hash, has_session_consent).

  PURE classification (no IO; the heart — fully unit-tested):
    classify(tool_name: str, tool_input: dict) -> tuple[str, str] | None
      Returns (action, target) for a CLEARLY gated action, else None (not gated → allow). CONSERVATIVE — only a
      clear match returns an action; ambiguity/parse-trouble → None (the non-gated path never bricks a command).
        * tool_name == "mcp__gsc__submit_sitemap" → ("mcp_submit", <the sitemap/site target from tool_input>).
        * tool_name == "Bash": parse tool_input["command"] (a string):
            - leading token (path-stripped, first word) in {rm, rmdir, unlink, shred} → ("fs_delete", <first
              path-like arg, or the whole arg list joined>).
            - a `git push` invocation (token sequence 'git' then 'push'; ignore `--dry-run`) →
              ("git_push", <remote, default "origin"> ; or the remote+refspec).
            - a `curl`/`wget` with an outbound POST (any of: `-X POST`, `--request POST`, `-d`, `--data`,
              `--data-raw`, `--data-binary`, or an IndexNow/indexing endpoint) → if the URL host is
              `indexing.googleapis.com` → ("index_update", <url>), else ("net_post", <url>).
            - else → None.
        * any other tool_name → None.
      Build the target string DETERMINISTICALLY (the deny message echoes it, so the operator's /pseo-approve uses
      the identical string → identical target_hash). Document each action's target derivation.

  IO + decision (main, NON-CRASHING for the NON-gated path, FAIL-CLOSED for the gated path):
    def evaluate(payload, *, has_consent_fn=has_session_consent, resolvers...) -> tuple[int, list[str]]:
      parse tool_name/tool_input; g = classify(...); if g is None: return (0, []).  # not gated → ALLOW
      (action, target) = g
      resolve session_id + workspace + slug; th = target_hash(target).
      allowed = (slug is not None) and has_consent_fn(ws, slug, session_id=session_id, action=action, target_hash=th)
      if allowed: return (0, [])  # consented this session → ALLOW
      # gated + not consented (or unresolvable session/slug) → DENY (fail-closed) with the copy-paste command:
      run_label = "sess-" + (session_id[:8] if session_id else "unknown")
      return (2, [f"BLOCKED: {action} → {target}  (bu oturumda onay yok)",
                  f'İzin vermek için çalıştır:  /pseo-approve {run_label} {action} "{target}"'])
    def main() -> int:
      try: read stdin JSON; (code, msgs) = evaluate(payload); write each msg to stderr ("[gate] ..."); return code
      except Exception: # a gate bug must not brick NON-gated work. The classify()/consent path already
        # fail-CLOSED on a gated match; an UNEXPECTED top-level error → allow (return 0) + a loud stderr WARNING,
        # because reaching here means classification itself crashed (no confirmed gated action). Mirror
        # validate_content_write.py's fail-open-on-internal-error rationale.
        return 0
    Module docstring: cite spec G4 + the per-session consent model + READ-ONLY + that classify is conservative
    (only clear matches gated; non-gated never blocked) + deny via exit 2 + the copy-paste deny-message UX.

  Wiring — hooks/pre-tool-use.json: add a SECOND block to hooks.PreToolUse (leave the first untouched):
    { "matcher": "Bash|mcp__gsc__submit_sitemap",
      "hooks": [ { "type": "command",
                   "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/outward_action_gate.py\"",
                   "timeout": 15,
                   "statusMessage": "AMO outward-action consent gate..." } ] }

TDD — write these FIRST (RED), then implement (GREEN). tmp_path workspace + monkeypatch HOME; build a session
marker + a project so resolve_session_project finds the slug, and seed consent via consent_ledger.append_consent.
  classify() matrix (pure, no IO):
    1. mcp__gsc__submit_sitemap → ("mcp_submit", <target>).
    2. Bash "rm -rf foo/bar" → ("fs_delete", target includes "foo/bar"); "confirm x"/"performance" → None
       (leading-token guard, not substring).
    3. Bash "git push origin main" → ("git_push", "origin" or "origin main"); "git status" → None.
    4. Bash "curl -X POST https://api.indexnow.org/... -d @body" → ("net_post", the URL).
    5. Bash "curl -X POST https://indexing.googleapis.com/v3/urlNotifications:publish ..." → ("index_update", url).
    6. Bash "ls -la" / "git log" / "echo hi" / "cat x" → None (NOT gated — must always allow).
    7. tool_name "Read"/"Write"/"mcp__gsc__search_analytics" → None.
  evaluate()/consent:
    8. a gated action WITH a matching same-session consent entry → (0, []) (allow).
    9. the SAME action+target but consent recorded under a DIFFERENT session_id → (2, deny) (per-session!).
    10. a gated action with NO consent → (2, [...]) and the 2nd message is the exact
        `/pseo-approve sess-<8> {action} "{target}"` line (assert the action+target+session-prefix appear).
    11. a tampered consent chain (mutate a middle line) → (2, deny) (has_session_consent fail-closed).
    12. unbound session (no slug) + a gated action → (2, deny) (fail-closed; can't verify → deny).
    13. a NON-gated command (classify None) with NO session/workspace at all → (0, []) (never bricks plain Bash).
  main() subprocess smoke (mirror test_stop_validation / test_denetci): a gated-no-consent stdin → exit 2 +
    stderr has the /pseo-approve line; a non-gated stdin → exit 0, empty stderr; bogus stdin → exit 0 (no brick).
  has_session_consent (in test_consent_ledger.py): matching session+action+target_hash on an intact chain →
    True; different session_id → False; tampered chain → False.

METHOD:
  1. Baseline pytest (record N == 1967).
  2. Write the test files (RED); watch the import/classify failures.
  3. Implement has_session_consent (+ __all__); the gate; wire the 2nd pre-tool-use block; register in
     RUNTIME_HOOK_SCRIPTS + README.
  4. Confirm the EXISTING pre-tool-use tests + the 4 existing pre-tool-use hooks are untouched/green (you only
     ADDED a block). Confirm test_hook_scripts_runtime_vs_ci + test_consent_ledger still green (yours added).
  5. Full suite; passed >= N, 0 failed.
  6. Self-review @code-reviewer + @verifier (inline): the gate is READ-ONLY (no writes); NON-gated commands
     ALWAYS exit 0 (grep your branches — only a positive classify() match can reach exit 2); gated-without-consent
     is fail-CLOSED; the deny message echoes the exact target the gate hashed (writer/gate hash via the SAME
     consent_ledger.target_hash); classify uses leading-token (not substring) so `rm` matches but `confirm` doesn't.

DURUR (stop + report):
  - An outward-action / consent gate already exists (grep) — report rather than duplicate.
  - A test pins pre-tool-use.json to exactly 1 block / N commands and adding a block breaks it for a reason you
    can't cleanly migrate (preserve/strengthen) — STOP + report (do not weaken a security contract test).
  - mcp__gsc__submit_sitemap's tool_input target key is ambiguous (can't tell which field is the sitemap/site)
    — STOP + report what you found (don't guess a key that would hash a wrong/empty target).
  - You feel you must change the frozen consent.schema.json or an EXISTING consent_ledger function — STOP
    (has_session_consent is purely additive).
  - Any existing test regresses for a reason outside this batch's files.

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line (passed/skipped/failed).
  - Files created/edited + new-test count.
  - The classify() matrix (which tool/command → which action+target) + confirmation NON-gated commands always
    allow (only a clear match can deny) + the leading-token guard (rm gated, confirm not).
  - Confirmation the gate is PER-SESSION: quote the has_session_consent match (session_id + action +
    target_hash) and the test where the SAME action+target under a different session is DENIED.
  - Confirmation FAIL-CLOSED on the gated path (no consent / unbound / tampered chain → exit 2) and FAIL-OPEN on
    the non-gated path (classify None / internal error → exit 0, never bricks plain Bash).
  - Quote the deny message + confirm it echoes the exact `/pseo-approve … "{target}"` the operator copies, and
    that the gate hashes the target via consent_ledger.target_hash (writer/gate parity).
  - Confirmation: READ-ONLY (no state writes); has_session_consent additive (frozen schema + existing fns
    untouched); 2nd pre-tool-use block added (existing block + its 4 hooks intact); classified RUNTIME + README;
    no schema/command → no D10.
  - Any DURUR hit, out-of-scope need (e.g. a pre-tool-use structure test you migrated), or assumption.
```
