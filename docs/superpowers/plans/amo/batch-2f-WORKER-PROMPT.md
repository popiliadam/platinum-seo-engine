# AMO Batch 2f — Outward-Gate Completeness (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 2 is 5/6 (2a/2c/2d/2b/2e shipped; HEAD `3367f28`, suite
> **2025/0**). This is the FINAL Faz-2 batch — the manager TIGHTENED the originally-bundled "2f" down to the two
> genuine **2b consent-gate completeness gaps** (found in 2b QA), so it's one file + focused. Deferred elsewhere:
> `dfs_oversized` → Faz 4 (cost/quota ledger), the "declared-MCP ⊆ gate-matchers" drift rule → Faz 3 (§4 mastery
> lint), the 2e `os.replace`-failure edge → accepted (too narrow). After 2f, Faz 2's safety layer is complete.
> Paste the block below into a fresh Claude Code session (Opus 4.8, 1M context) at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 2f of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 2025 at HEAD 3367f28) BEFORE any change. END green with
  passed strictly >= N (your new tests add to it) and 0 failed. EVERY existing test in
  tests/hooks/test_outward_action_gate.py MUST stay green (this is a surgical hardening of batch 2b's gate).
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability; no leftover debug prints; small functions (<50 lines); files 200-400 lines.
- Scope-lock: create/modify ONLY the two files in SCOPE. Anything else → STOP + report.

WHY THIS BATCH EXISTS (read carefully):
Batch 2b shipped the outward-action consent gate (scripts/hooks/outward_action_gate.py): it classifies an
irreversible/outward Bash/MCP action and DENIES it (exit 2) unless the session consented. Manager QA found TWO
completeness gaps in that gate — this batch closes BOTH, surgically, with zero behaviour change to the cases 2b
already handles:

  (a) FAIL-OPEN on a consent-check exception (the gated path must be fail-CLOSED).
      In `evaluate()`, the consent lookup is `… and has_consent_fn(...)`. If `has_session_consent` RAISES (it
      reads the ledger; `read_entries` throws `ConsentLedgerError` on a CORRUPT consent.jsonl line), the
      exception propagates out of `evaluate()` to `main()`'s `except → return 0` — so a DETECTED gated action is
      ALLOWED when the ledger is corrupt. That contradicts "fail-closed on the gated path." FIX: a gated action
      whose consent cannot be VERIFIED (the check raised) must DENY, and say so.

  (b) The classifier only inspects the WHOLE command's LEADING token, so it misses:
      - compound commands whose gated part isn't first: `cd x && git push`, `ls && curl -X POST https://…`,
        `mkdir y; rm -rf z` (the leading token is cd/ls/mkdir → currently None → allowed);
      - `git` with global flags before the subcommand: `git -C /path push`, `git -c k=v push` (push is not at
        tokens[1] → currently missed).
      These are realistic ways a cooperative model emits a gated action that the current gate waves through.
      FIX: split the Bash command into segments on shell separators and classify EACH segment; detect `git push`
      even behind git global flags.

CONFIRMED FACTS (verified against the code 2026-06-06 — do not re-derive):
- `scripts/hooks/outward_action_gate.py` (batch 2b) structure you are editing:
    * `classify(tool_name, tool_input)` → dispatches Bash to `_classify_bash(command)`.
    * `_classify_bash(command)` → tokenises the WHOLE command (`_tokenize` = shlex with str.split fallback),
      takes `first = tokens[0].rsplit("/",1)[-1]`, then: `first in _DELETE_TOKENS` → fs_delete;
      `first == "git" and tokens[1] == "push"` → git_push; `first in _HTTP_TOKENS` → curl/wget POST logic
      (`_has_post_flag`, `_first_url`, indexing/indexnow host → index_update/net_post). Helpers `_operands`,
      `_DELETE_TOKENS` {rm,rmdir,unlink,shred}, `_HTTP_TOKENS` {curl,wget}, `_INDEXING_HOST`, `_POST_DATA_FLAGS`.
    * `evaluate(payload, *, has_consent_fn=has_session_consent, session_id_fn, workspace_fn, slug_fn)` →
      classify; if None → (0,[]); else resolve session_id/workspace/slug, `th = target_hash(target)`,
      `allowed = bool(workspace and slug and session_id and has_consent_fn(...))`; allow → (0,[]); else deny (2,
      [BLOCKED…, /pseo-approve…]).  `main()` wraps stdin+evaluate in `try/except Exception: return 0`.
- The only raise source on the GATED path is `has_consent_fn` (the resolvers return None, never raise;
  `target_hash` of a str never raises). So wrapping the `has_consent_fn` call is sufficient + precise — do NOT
  broaden the catch to the resolvers (None is already handled).
- `has_session_consent` (consent_ledger.py) calls `read_entries` which raises `ConsentLedgerError` on a corrupt
  line. (To TEST the raise, inject a `has_consent_fn` that raises — `evaluate` takes it as a kwarg — OR write a
  corrupt consent.jsonl line and drive the real path.)
- shell separators to split on: `&&`, `||`, `;`, `|`, newline. A single command (no separator) is ONE segment —
  so every existing single-command test keeps its exact result. Split on the RAW string, then `_tokenize` each
  segment (do NOT shlex the whole line — a heredoc/quoted separator would mis-tokenise; segment-split on the raw
  string + per-segment tokenise is the Path-A approach, same conservative spirit as 2b).
- Adds NO schema/command/hook-FILE/wiring change (the gate is already wired on Bash) → NO D10. pre-tool-use.json
  is NOT touched.

ORIENT FIRST (read, do not change yet):
- `scripts/hooks/outward_action_gate.py` IN FULL — `_classify_bash`, `_operands`, `_classify_segment` does not
  exist yet (you extract it), `evaluate`, the constants.
- `tests/hooks/test_outward_action_gate.py` IN FULL — keep EVERY test green; you ADD cases. Note how it builds
  payloads + injects `has_consent_fn`/resolvers.

SCOPE — modify ONLY these two files:
  EDIT scripts/hooks/outward_action_gate.py       (fail-closed consent-check + segment-split classifier)
  EDIT tests/hooks/test_outward_action_gate.py    (ADD the new cases; all existing stay green)

SPEC — (a) fail-CLOSED consent check in evaluate():
  Replace the single `allowed = bool(… and has_consent_fn(...))` with a guarded lookup:
    consent_error = False
    consented = False
    if workspace is not None and slug is not None and session_id:
        try:
            consented = has_consent_fn(workspace, slug, session_id=session_id, action=action, target_hash=th)
        except Exception:
            consent_error = True   # ledger unreadable/corrupt -> consent UNVERIFIABLE -> fail-CLOSED (deny)
    if consented:
        return (0, [])
    run_label = "sess-" + (session_id[:8] if session_id else "unknown")
    messages = [
        f"BLOCKED: {action} → {target}  (bu oturumda onay yok)",
        f'İzin vermek için çalıştır:  /pseo-approve {run_label} {action} "{target}"',
    ]
    if consent_error:
        messages.append("⚠️ consent defteri okunamadı/bozuk — onay DOĞRULANAMADI, güvenli tarafta REDDEDİLDİ.")
    return (2, messages)
  Result: a gated action with an unverifiable consent (corrupt ledger) now DENIES (was: allowed via main's
  except). main()'s `except → return 0` now only catches a pre-classification crash (stdin/classify) — i.e. NO
  confirmed gated action — so the non-gated fail-OPEN is preserved and the gated path is fully fail-CLOSED.

SPEC — (b) segment-split classifier (refactor `_classify_bash`, preserve every existing single-command result):
  Add:
    _SEGMENT_SEP_RE = re.compile(r"&&|\|\||;|\n|\|")   # && || ; newline | (|| before | so it wins)
    def _split_segments(command: str) -> list[str]:
        return [seg.strip() for seg in _SEGMENT_SEP_RE.split(command) if seg.strip()]
    def _git_push_target(tokens: list[str]) -> str | None:
        '''Return the git-push target (operands or "origin") if this is a `git push`
        even behind global flags (-C <path>, -c <kv>, --git-dir <p>, …), else None.'''
        _ARG_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
        i = 1  # tokens[0] == "git"
        while i < len(tokens):
            t = tokens[i]
            if t in _ARG_FLAGS:        # global flag that consumes the next token
                i += 2; continue
            if t.startswith("-"):      # other global flag (no arg / --flag=val)
                i += 1; continue
            if t != "push":           # first non-flag token is the subcommand
                return None
            operands = [x for x in tokens[i + 1:] if not x.startswith("-")]
            return " ".join(operands) if operands else "origin"
        return None
  Extract the CURRENT per-command body into `_classify_segment(segment) -> tuple[str,str] | None` with ONE
  change: the git branch becomes `if first == "git": tgt = _git_push_target(tokens); return ("git_push", tgt)
  if tgt is not None else None` (so `git status` / `git -C p status` → None; `git push` / `git -C p push` →
  git_push). The fs_delete + curl/wget branches are UNCHANGED (operate on the segment's tokens).
  Then `_classify_bash(command)` becomes:
    def _classify_bash(command):
        for segment in _split_segments(command):
            hit = _classify_segment(segment)
            if hit is not None:
                return hit          # first gated segment wins (iterative approval for multi-gated commands)
        return None
  (A multi-gated command like `git push && rm -rf x` returns the FIRST gated action; the operator approves it,
  re-runs, the gate then catches the next — each gated action individually consented. Document this.)

TDD — ADD these (RED first); keep ALL existing tests green:
  (a) fail-closed:
    1. evaluate with an injected `has_consent_fn` that RAISES, on a gated action (e.g. git push) with a resolved
       bound session → returns (2, …) AND the messages include the "okunamadı/bozuk … REDDEDİLDİ" note (NOT (0,[])).
    2. (real path) a corrupt consent.jsonl line + a gated action → (2, deny). (Write a non-JSON line into the
       project's consent.jsonl, seed a session marker, evaluate → deny.)
    3. regression: the normal "no consent entry" case still denies WITHOUT the corrupt-ledger note (has_consent
       returns False, doesn't raise).
  (b) segment-split + git flags:
    4. `cd foo && git push origin main` → ("git_push", "origin main").
    5. `ls -la && curl -X POST https://api.indexnow.org/x -d @b` → ("net_post", url).
    6. `mkdir y ; rm -rf z` → ("fs_delete", target includes "z").
    7. `git -C /srv/repo push` → ("git_push", "origin"); `git -c user.name=x push origin main` →
       ("git_push", "origin main").
    8. `git -C /srv/repo status` → None (a flagged non-push git subcommand is NOT gated).
    9. `echo hi && ls && cat x` → None (no gated segment; never bricks a benign compound command).
    10. regressions: every existing single-command classify test (plain `git push`, `rm -rf foo/bar`, `git status`,
        `confirm x`, GET curl, etc.) returns its SAME result (one segment → unchanged).

METHOD:
  1. Baseline pytest (record N == 2025).
  2. Add the new tests (RED); watch them fail (the compound/flag/raise cases).
  3. Implement (a) the guarded consent lookup + (b) the segment-split + `_git_push_target`.
  4. Run tests/hooks/test_outward_action_gate.py — ALL green (existing + new). Then the FULL suite; >= N, 0 failed.
  5. Self-review @code-reviewer + @verifier (inline): the gated path now DENIES on a consent-check raise (quote
     the try/except → deny); main's except is unchanged (still fail-open for pre-gated crashes only); the
     segment-split leaves every single-command result identical (one segment); `_git_push_target` gates
     `git -C p push` but not `git -C p status`; immutability; no file outside SCOPE touched; no D10.

DURUR (stop + report):
  - Wrapping the consent check would require changing consent_ledger / the frozen schema — STOP (the fix is
    purely in outward_action_gate.evaluate()).
  - A separator-split breaks an EXISTING test for a reason you can't preserve (a single-command test changes
    result) — STOP + report (every single-command result must be identical).
  - Any existing test regresses for a reason outside this batch's two files.

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line (passed/skipped/failed) + the test_outward_action_gate.py count (all green).
  - (a) Quote the guarded consent lookup (try/except → consent_error → deny) and confirm a consent-check RAISE
    now DENIES (was allowed via main's except); confirm the normal no-consent path is unchanged (no false
    corrupt-ledger note).
  - (b) Quote `_split_segments` + `_git_push_target`; the matrix of new gated cases (compound `&&`/`;`/`|`,
    `git -C p push`, `git -c kv push`) + confirm `git -C p status` and a benign compound (`echo && ls`) are NOT
    gated; confirm every single-command result is IDENTICAL (one segment).
  - Confirm: no file outside the 2 SCOPE files; no schema/command/wiring change; no D10.
  - Any DURUR hit, out-of-scope need, or assumption (e.g. multi-gated commands resolve via first-gated +
    iterative approval).
```
