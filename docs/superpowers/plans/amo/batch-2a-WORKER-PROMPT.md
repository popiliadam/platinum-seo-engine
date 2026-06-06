# AMO Batch 2a — Consent Ledger Substrate (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 1 is complete + pushed (HEAD `9b5d238`, suite **1891/0**).
> This is the FIRST Faz-2 batch and a deliberate **data-substrate freeze**: the append-only, hash-chained
> consent ledger that every outward-action gate (batch 2b) will consult, plus the non-coder `/pseo-approve`
> consent-UX (spec O3). It contains **NO hooks** on purpose — the runtime PreToolUse gate that *enforces*
> consent lives in 2b. 2a only builds the LEDGER (schema + recorder + `/pseo-approve`) so 2b/2c can be built
> against a frozen contract. It is **file-disjoint from batch 2c** (denetçi + oracle), so the two run in
> parallel windows. Adding a `schemas/*.json` + a `commands/*.md` trips the D10 count-guards — the prompt
> tells the worker to reconcile the manifest literals to the new filesystem counts (manager re-verifies).
> Paste the block below into a fresh Claude Code session (Opus 4.8, 1M context) rooted at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 2a of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and
print the REPORT (the manager reviews + commits). A SIBLING worker is running batch 2c in parallel; it
touches DIFFERENT files (hooks/stop.json, scripts/hooks/denetci.py, scripts/reporting/) — if you ever feel
you need a file outside your SCOPE list, STOP and report it (do NOT touch 2c's files).

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state. No `git add`/`commit`/`checkout`/`reset`.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 1891) BEFORE any change. You MUST END green with
  passed strictly >= N (your new tests add to it) and 0 failed.
- TDD: write the FAILING test first, watch it fail, then implement until green. Never fake red.
- House style: immutability (return/build NEW objects, never mutate inputs); no print/console debug left in
  shipped code (CLI user-facing prints are fine); no hardcoded secrets; small focused functions (<50 lines);
  files 200-400 lines normal.
- Scope-lock: create/modify ONLY the files named in SCOPE below. If a fix seems to need any OTHER file,
  STOP and report it — do not touch it. (The D10 count-guard manifest files ARE in scope; see SCOPE.)

WHY THIS BATCH EXISTS (read carefully):
AMO Faz 2 adds SAFETY GATES so an autonomous run can never perform an irreversible / outward action
(git push, rm, an exfil POST, a Google Indexing-API submit, an oversized DataForSEO call) WITHOUT the
operator's recorded consent. The backbone of that is an append-only, tamper-evident CONSENT LEDGER:
`projects/{slug}/_state/consent.jsonl`. Each line records "the operator approved THIS action on THIS target
for THIS run". The ledger is HASH-CHAINED (each line carries the prior line's hash) so a forged or rewritten
entry is detectable by re-walking the chain. Batch 2b's PreToolUse gate will, before allowing a gated
action, hash the concrete target and ask `has_consent(run_id, action, target_hash)`; if there's no matching
intact-chain entry, it DENIES. This batch builds ONLY the ledger half: the entry SCHEMA, the recorder
module, and the `/pseo-approve` command a non-coder uses (in the Mac app, no terminal) to grant consent.
It does NOT build the gate (that's 2b) and it does NOT build the denetçi/oracle (that's the parallel 2c).

Süleyman's HARD constraints this ledger ultimately protects (do not weaken; they motivate the action enum):
- Google Indexing-API `URL_UPDATED` submits require his EXPLICIT consent — never autonomous.
- "written by AI" must NEVER appear in visible HTML (a different gate, 2b; not your concern here).

CONFIRMED FACTS (verified against the code 2026-06-06 — do not re-derive):
- The gold-standard append-only writer is `scripts/state/events_writer.py`. Its `_atomic_append_allocating_run_id`
  (lines ~369-413) is EXACTLY the pattern you mirror: `os.open(path, O_WRONLY|O_CREAT|O_APPEND, 0o644)` ->
  `fcntl.flock(fd, LOCK_EX)` -> (read the file's tail UNDER the lock to learn prev state) -> `os.write` ONE
  payload -> `os.fsync` -> `flock(LOCK_UN)` -> `os.close`. Validation runs BEFORE the write. Study it.
- CRITICAL landmine — consent.jsonl is an APPEND-ONLY LOG, NOT a marker file. You MUST append in place with
  O_APPEND (like events_writer). You must NEVER use `os.replace`/tempfile-rename to write it (that is the
  pattern for MUTABLE MARKER files like coverage/session markers — `scripts/state/session_binding._atomic_write_json`
  + `scripts/orchestration/coverage.py` use os.replace BECAUSE they are rewritten markers). Using os.replace
  on an append-only log inode-swaps and loses concurrent writers' data. Know the difference; use O_APPEND.
- `scripts/state/session_binding.py` is the binding primitive (batch 0b). Reuse it in the CLI:
  `resolve_workspace_root()` -> the workspace root (from ~/.config/pseo/config.json, env fallback);
  `resolve_session_project(workspace_root, arg=None, session_id=current_session_id(), strict=True)` -> the
  slug bound to THIS session (session marker -> shared/active.json -> raises if unbound). `current_session_id()`
  reads `$CLAUDE_CODE_SESSION_ID`. This makes `/pseo-approve` record consent for the session's bound project.
- The run_id grammar used across the engine is `^[a-z][a-z0-9-]*-[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{4}$`
  ({slug}-{YYYY-MM-DD}-{hash4}). A consent entry's run_id SHOULD usually be a real workflow run_id, but the
  ledger must also accept a manual/standalone token, so the schema makes run_id `type:string, minLength:1`
  (permissive) — NOT the strict run-id pattern. The gate matches it by EXACT string equality.
- Schema house style to copy: `schemas/coverage.schema.json` (the most recent schema — draft-07 `$schema`,
  `$id` `http://platinum-seo-engine/schemas/<name>`, `title "X v1.0"`, a rich `description` naming WHO writes
  / WHO reads / WHY, `additionalProperties:false`, an OPTIONAL `schema_version` const "1.0" NOT in required[]).
- Schemas are validated by a glob — dropping `schemas/consent.schema.json` in is auto-picked-up; no
  registration step. But it trips D10 count-guards (see SCOPE / METHOD).
- The command house style to copy is `commands/pseo-bind.md` (frontmatter: a Turkish `description:` block with
  "Use when / Also use when / Do not use when", `argument-hint`, `allowed-tools: Bash(python3:*), Bash(ls:*), Read`,
  `model: sonnet`; body that calls the python CLI via `cd "$CLAUDE_PLUGIN_ROOT" && python3 -m scripts.state.<module> ...`).
- `rules/append-only-state.md` is the discipline this ledger embodies; cite it in the module docstring.
- This batch adds NO hook, touches NO hooks/*.json, and does NOT modify events_writer / session_binding /
  coverage / any existing module. It is purely additive.

ORIENT FIRST (read, do not change yet):
- `scripts/state/events_writer.py` IN FULL — the append discipline (`_atomic_append_line` ~303-341,
  `_atomic_append_allocating_run_id` ~369-413, `_serialize` ~415-422, `_get_validator` ~206-212, the redaction
  and `_SLUG_RE`). You mirror its atomic-append + validate-before-write shape (you do NOT import it).
- `scripts/state/session_binding.py` — `resolve_workspace_root`, `current_session_id`, `resolve_session_project`,
  `_is_safe_session_id`, `_SLUG_RE`, the CLI `_build_parser`/`main` shape (~284-347). Your CLI mirrors this.
- `schemas/coverage.schema.json` — copy the header/description/additionalProperties style.
- `commands/pseo-bind.md` — copy the command shape for `commands/pseo-approve.md`.
- `tests/schemas/` (e.g. `test_coverage_schema.py` if present, else `test_instance_validation.py`) — the
  Draft7Validator instance-test pattern. Mirror it for `test_consent_schema.py`.
- `tests/state/` — pick any `test_*.py` that uses `tmp_path` + monkeypatch HOME for the layout of your
  recorder tests (e.g. `test_session_binding.py`, `test_events_writer.py`).
- The two D10 count guards you will reconcile:
    `tests/docs/test_count_consistency.py` — asserts plugin.json + marketplace.json descriptions contain the
      live filesystem counts ("N slash command" / "N commands" / "N schemas"). Adding a command + a schema
      makes these FAIL until you update the literals.
    `tests/schemas/test_json_schema_draft_consistency.py` — asserts the count of `schemas/*.schema.json`
      (an `assert count == <N>`). Adding consent.schema.json bumps it by 1.
  RUN these two after adding your files; the failure messages tell you the exact new numbers; update the
  manifest literals + the assert to match the filesystem. Do NOT guess counts — let the tests tell you.

SCOPE — create/modify ONLY these files:
  NEW  schemas/consent.schema.json                          (the consent-ENTRY shape; one .jsonl line; see SPEC)
  NEW  scripts/state/consent_ledger.py                      (recorder + verify + has_consent + CLI; see SPEC)
  NEW  commands/pseo-approve.md                             (operator consent UX; mirrors pseo-bind.md)
  NEW  tests/schemas/test_consent_schema.py                 (instance validation: valid + invalid cases)
  NEW  tests/state/test_consent_ledger.py                   (append/read/chain/tamper/has_consent/concurrency)
  EDIT .claude-plugin/plugin.json                           (D10: bump "N slash command" in description to filesystem count)
  EDIT .claude-plugin/marketplace.json                      (D10: bump "N commands" AND "N schemas" in description)
  EDIT tests/schemas/test_json_schema_draft_consistency.py  (D10: bump the schemas/*.schema.json count assert by 1)

  >> The last three are PRE-AUTHORIZED D10 count-guard bumps, deterministic and forced by adding the schema +
     command (without them the suite cannot end green). Apply them by RUNNING the count tests, reading the
     expected-vs-actual, and setting the literals to the new filesystem counts. Touch ONLY the count literals
     (and, if the assert helper has a name/docstring citing the old number, that). FLAG every before/after in
     your REPORT under "D10 count-guard bumps" so the manager re-verifies against `ls`.

SPEC — schemas/consent.schema.json (author this EXACT shape; you may refine DESCRIPTIONS, but property NAMES,
the `action` enum, the `required[]`, and the hash patterns are FROZEN — batch 2b's gate + `/pseo-approve`
key on them literally):

  {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://platinum-seo-engine/schemas/consent",
    "title": "Consent Ledger Entry v1.0",
    "description": "Shape of ONE line of projects/{slug}/_state/consent.jsonl — the append-only, hash-chained
      ledger recording operator consent for an irreversible/outward action. The recorder (consent_ledger.py,
      batch 2a) appends one entry per `/pseo-approve`; the PreToolUse outward-action gate (batch 2b) hashes a
      pending action's concrete target and calls has_consent(run_id, action, target_hash) before allowing it.
      Hash-chained: entry_hash = sha256(canonical_json(this entry WITHOUT entry_hash)); prev_hash = the prior
      line's entry_hash (or 64 zeros for the first line) — so a forged/rewritten/reordered entry breaks the
      chain and is rejected. Append-only LOG (events.jsonl discipline), never an os.replace marker.",
    "type": "object",
    "required": ["seq", "run_id", "action", "target_hash", "granted_at", "granted_by", "prev_hash", "entry_hash"],
    "additionalProperties": false,
    "properties": {
      "schema_version": { "const": "1.0", "description": "ADR-018/019 const discipline; lets a future migration discriminate older entries. Optional (not in required[])." },
      "seq":         { "type": "integer", "minimum": 0, "description": "0-based monotonic index of this entry within the file. seq 0 is the genesis line (prev_hash = 64 zeros). verify_chain asserts seq increments by exactly 1." },
      "run_id":      { "type": "string", "minLength": 1, "description": "The run (or manual token) this consent is scoped to. Usually a workflow run_id {slug}-{YYYY-MM-DD}-{hash4}, but permissive (minLength:1) to allow a standalone manual approval. The gate matches by EXACT string equality." },
      "action":      { "type": "string", "enum": ["git_push", "fs_delete", "net_post", "mcp_submit", "index_update", "dfs_oversized"], "description": "The class of gated outward action consent is granted for. git_push=`git push`; fs_delete=rm/unlink/rmdir/shred; net_post=outbound curl/wget POST (exfil surface); mcp_submit=an MCP submit tool (e.g. mcp__gsc__submit_sitemap); index_update=Google Indexing-API URL_UPDATED (Süleyman hard-consent); dfs_oversized=an oversized DataForSEO request. Batch 2b maps each gate matcher onto exactly one of these. Additive enum bump if a new gated class is added later." },
      "target":      { "type": "string", "description": "Human-readable concrete target the consent is for (the URL, file path, sitemap, command). Optional but recommended for audit; target_hash is the matchable key." },
      "target_hash": { "type": "string", "pattern": "^[a-f0-9]{64}$", "description": "sha256 hex of the canonical target string (UTF-8). The gate computes the SAME hash of a pending action's concrete target and looks it up, so writer and gate MUST hash identically (use consent_ledger.target_hash())." },
      "granted_at":  { "type": "string", "format": "date-time", "description": "UTC ISO 8601 when consent was granted." },
      "granted_by":  { "type": "string", "minLength": 1, "description": "Who granted it (e.g. 'operator', a session id, or a name) — provenance for the audit trail." },
      "session_id":  { "type": "string", "description": "The Claude session UUID that granted consent, if known. Optional provenance." },
      "note":        { "type": "string", "description": "Optional free-text operator note." },
      "prev_hash":   { "type": "string", "pattern": "^[a-f0-9]{64}$", "description": "entry_hash of the PRIOR line, or 64 zeros ('0'*64) for the genesis line (seq 0). The chain link." },
      "entry_hash":  { "type": "string", "pattern": "^[a-f0-9]{64}$", "description": "sha256 hex over canonical_json of THIS entry with entry_hash removed (all other fields, incl. prev_hash, present). Tamper-evidence: recomputing must reproduce this value." }
    }
  }

SPEC — scripts/state/consent_ledger.py (additive module; mirrors events_writer's discipline; NO import of it):
  Constants / helpers:
    - GENESIS_HASH = "0" * 64
    - _SCHEMA_PATH = <repo>/schemas/consent.schema.json   (repo = Path(__file__).resolve().parents[2])
    - _ACTIONS = frozenset of the 6 enum values above (defensive validation in append).
    - canonical_json(obj) -> str:  json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    - target_hash(target: str) -> str:  hashlib.sha256(target.encode("utf-8")).hexdigest()
    - compute_entry_hash(entry_without_entry_hash: dict) -> str:
        sha256(canonical_json(<entry dict with the "entry_hash" key absent>).encode("utf-8")).hexdigest()
      (prev_hash IS one of the hashed fields, so the chain link is bound into entry_hash.)
    - consent_path(workspace_root, project_slug) -> Path:
        {workspace_root}/projects/{slug}/_state/consent.jsonl  (validate slug with the _SLUG_RE pattern;
        mkdir parents=True for the _state dir, same as events_writer._events_path).
    - _validate_entry(entry) -> None:  Draft7Validator(consent.schema) ; raise ConsentValidationError on errors.
  Public API:
    - read_entries(workspace_root, project_slug) -> list[dict]:
        parse every non-blank line of consent.jsonl as JSON; return [] if the file is missing. Never raises on
        a missing file (raise only on an unreadable/corrupt existing file, your choice — but a missing file = []).
    - verify_chain(entries: list[dict]) -> tuple[bool, int | None]:
        Walk in order. For i: assert entry["seq"] == i; assert prev_hash == (GENESIS_HASH if i==0 else
        entries[i-1]["entry_hash"]); recompute compute_entry_hash(entry-without-entry_hash) == entry["entry_hash"].
        Return (True, None) if all hold, else (False, <first bad index>). Empty list -> (True, None).
    - append_consent(*, workspace_root, project_slug, run_id, action, target, granted_by, now_iso,
                     session_id=None, note=None, schema_path=None) -> dict:
        Defensive: action in _ACTIONS else ValueError. UNDER ONE fcntl.flock(LOCK_EX) on the consent.jsonl fd
        (open O_WRONLY|O_CREAT|O_APPEND): read the file tail to get the last entry's (seq, entry_hash) — if no
        prior entry, seq=0 & prev_hash=GENESIS_HASH, else seq=last_seq+1 & prev_hash=last_entry_hash; build the
        entry dict (schema_version "1.0", seq, run_id, action, target, target_hash(target), granted_at=now_iso,
        granted_by, + session_id/note only if provided); compute entry_hash; _validate_entry(entry);
        os.write ONE `canonical_or_compact_json + "\n"` payload; os.fsync; release lock; close. Return the entry.
        Reading the tail UNDER the same lock that guards the append is what makes concurrent appends chain
        correctly (mirror _atomic_append_allocating_run_id). NEVER os.replace.
    - has_consent(workspace_root, project_slug, *, run_id, action, target_hash) -> bool:
        read_entries -> verify_chain; if chain invalid return False (tamper = no consent); else return True iff
        SOME entry matches run_id == ..., action == ..., target_hash == ... exactly.
  CLI (mirror session_binding's argparse `main`): subcommand `approve`:
        python3 -m scripts.state.consent_ledger approve <run_id> <action> <target>
                 [--granted-by X] [--note "..."] [--workspace <path>]
      Resolve workspace via session_binding.resolve_workspace_root (or --workspace, persisted); resolve slug via
      session_binding.resolve_session_project(ws, session_id=current_session_id(), strict=True); validate action
      in the enum (else friendly error listing the 6 valid values); call append_consent(now_iso=datetime.now()
      .isoformat(), granted_by=<--granted-by or "operator">, session_id=current_session_id()); print a one-line
      banner: `consent recorded: {action} on {target[:48]} for {run_id}  (seq {seq})`. Non-zero exit codes with
      clear stderr on: no workspace / unbound session / bad action / missing run_id|action|target.
  Errors: define ConsentLedgerError(Exception) + ConsentValidationError(ConsentLedgerError). __all__ exported.

SPEC — commands/pseo-approve.md (mirror commands/pseo-bind.md):
  Frontmatter: Turkish `description:` ("Use when: kullanıcı 'onayla', 'approve', 'izin ver', 'consent', 'şu
  aksiyona izin' der ya da `/pseo-approve <run_id> <action> <target>` çağırırsa. Also use when: bir AMO run'ı
  geri-alınamaz/dışa-dönük bir aksiyon (git push / silme / POST / GSC sitemap submit / Indexing URL_UPDATED /
  oversized DFS) için operatör onayı bekliyor; consent defterine `projects/{slug}/_state/consent.jsonl`
  hash-chained bir satır yazılacak. Do not use when: aksiyonu fiilen çalıştırma (gate 2b kontrol eder), session
  bağlama (`/pseo-bind`), durum görme (`/pseo-status`)."), `argument-hint: "<run_id> <action> <target>"`,
  `allowed-tools: Bash(python3:*), Bash(ls:*), Read`, `model: sonnet`.
  Body (Turkish, like pseo-bind): explain the 6 action values in a short list; require $1/$2/$3 (DURDUR with
  usage if missing); call `cd "$CLAUDE_PLUGIN_ROOT" && python3 -m scripts.state.consent_ledger approve "$1" "$2" "$3" 2>&1`;
  show the success banner + the error meanings (unbound session -> /pseo-bind; bad action -> list valid;
  no workspace -> --workspace once). Note that consent is recorded for THIS session's bound project, and that
  the gate (2b) is what actually allows the action once the entry exists.

TDD — write these FIRST (RED), watch fail, then implement (GREEN). Use tmp_path for the workspace + monkeypatch
HOME so nothing touches the real workspace/config:
  tests/schemas/test_consent_schema.py (Draft7Validator instance tests):
    1. A fully-populated valid entry (seq 0, prev_hash 64 zeros, a 64-hex target_hash + entry_hash, action
       "index_update", run_id "vento-2026-06-06-ab12", granted_at ISO, granted_by "operator") validates ZERO errors.
    2. Invalid: action "publish" (not in enum) -> error.
    3. Invalid: target_hash "xyz" (fails ^[a-f0-9]{64}$) -> error.
    4. Invalid: missing required "entry_hash" -> error.
    5. Invalid: an unknown extra top-level key (additionalProperties:false) -> error.
  tests/state/test_consent_ledger.py:
    6. append_consent once -> read_entries returns it; the entry validates against the schema; seq==0,
       prev_hash==GENESIS_HASH; target_hash == sha256 of the target.
    7. append three entries -> verify_chain((entries)) == (True, None); each prev_hash == prior entry_hash;
       seq == 0,1,2.
    8. TAMPER: rewrite the middle line on disk changing its target_hash -> verify_chain returns (False, 1)
       AND has_consent(... that entry's run_id/action/target_hash ...) returns False.
    9. has_consent: an exact (run_id, action, target_hash) match on an intact chain -> True; a non-matching
       target_hash -> False; a matching run_id+action but different target_hash -> False.
    10. append rejects an action not in the enum -> ValueError (nothing written).
    11. APPEND-ONLY proof: after a second append, the FIRST line's bytes are unchanged (read the file, assert
        line 0 identical to what append #1 wrote) — proves O_APPEND, not a rewrite.
    12. (concurrency-ish) two sequential appends from the SAME process produce a valid 2-entry chain (verify_chain
        True) — the lock + tail-read ordering holds. (A true multiprocess test is optional; if you add one,
        spawn 2 short python -c appenders and assert the final chain verifies and has 2 entries.)
  Also a CLI smoke test is welcome (invoke main(["approve", ...]) with a tmp workspace + a session marker so
  resolve_session_project finds the slug; assert exit 0 + one entry written) — optional but valuable.

METHOD:
  1. Baseline pytest (record N == 1891).
  2. Write the test files (RED). Run them; watch the relevant ones fail (module/schema absent).
  3. Author consent.schema.json; consent_ledger.py; commands/pseo-approve.md (GREEN the new tests).
  4. Run the 2 D10 count tests; read expected-vs-actual; reconcile the plugin.json + marketplace.json literals
     + the draft-consistency assert to the new filesystem counts. (You ADDED 1 command + 1 schema.)
  5. Sanity: `python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('schemas/*.json')]"` parses all;
     `python3 -m scripts.state.consent_ledger approve --help` shows usage.
  6. Re-run the FULL suite; confirm passed >= N and 0 failed.
  7. Self-review as @code-reviewer + @verifier (inline, Agent tools disabled): check the O_APPEND discipline
     (NO os.replace anywhere in consent_ledger), immutability, the hash is computed over the entry WITHOUT
     entry_hash, the lock wraps BOTH the tail-read and the write, and that nothing outside SCOPE changed.

DURUR (stop + report, do not work around):
  - You find an EXISTING consent ledger / consent.schema (grep first) — report it rather than duplicating.
  - A D10 count literal isn't where the test says, or a count test computes differently than expected — STOP
    and report the actual numbers; do not guess-edit manifests.
  - Mirroring the append discipline would require importing/altering events_writer or session_binding — STOP
    (this batch is purely additive; copy the PATTERN, don't modify those modules).
  - Any existing test regresses for a reason rooted outside this batch's files.
  - You feel you need to wire a hook / touch hooks/*.json — that is batch 2b/2c; STOP, you are out of scope.

REPORT (print verbatim when DONE — the manager needs it):
  - Baseline N and final pytest line (passed/skipped/failed).
  - Files created/edited (exact paths) + how many new tests you added.
  - The consent-entry contract you FROZE: the required[] + the 6-value `action` enum + the two hash patterns.
  - Quote the entry_hash computation (the exact canonical_json call + that entry_hash is excluded from the hash
    input) and the verify_chain rule (seq monotonic + prev_hash link + recompute), so the manager confirms 2b
    can rely on it.
  - Proof of the APPEND-ONLY discipline: quote the os.open(...O_APPEND...) + flock lines and confirm there is
    NO os.replace in consent_ledger.py.
  - Proof the tamper test fails the chain (the (False, 1) assertion) and has_consent returns False on tamper.
  - "D10 count-guard bumps:" BEFORE/AFTER of the plugin.json "N slash command", the marketplace "N commands" +
    "N schemas", and the draft-consistency assert — so the manager re-verifies against `ls commands/` + `ls schemas/*.schema.json`.
  - Confirmation you did NOT touch any hook, events_writer, session_binding, coverage, or any 2c file.
  - Any DURUR hit, any out-of-scope need you noticed, any assumption you made.
```
