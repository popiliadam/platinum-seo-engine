# AMO batch 3-gov-secrets — literal-pending-bytes secret scan

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE self-contained
batch: a "literal pending bytes" mode for the secret scanner. Follow every rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools. They FAIL in this repo ("Prompt is too long" — the MCP registry is too large).
   Do ALL work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations of any kind (no add/commit/branch/stash/checkout/push). The MANAGER commits after
   reviewing your REPORT. You only edit files + run tests.
3. BASELINE-FIRST. Before touching anything, run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: 2175 passed, 7 skipped, 0 failed. Your end state MUST be passed >= 2175 and
   failed == 0. If your baseline differs, REPORT it and continue (one MCP-availability-gated test may flip
   pass<->skip; total stays stable — not a regression).
4. TDD, RED FIRST. Write the new tests, RUN them, SHOW they FAIL for the right reason (the new flag does
   not exist yet), THEN implement. Never write implementation before a failing test.
5. SCOPE-LOCK. Create/modify ONLY the files named in SCOPE below. If you discover you need to touch ANY
   other file, STOP and report — do not touch it.
6. Bash discipline: keep `set -euo pipefail`; bash 3.2 compatible (macOS default — NO associative arrays,
   NO `mapfile`/`readarray`); NEVER echo matched secret content (only path/label/count — this is a
   security invariant of the existing script); no debug prints left behind.
7. BEHAVIOUR-PRESERVING for existing modes: the default positional invocation `check_secrets.sh [ROOT]`
   and the `--changed-since` incremental mode must stay BYTE-FOR-BYTE behaviourally identical. The new
   mode is a NEW opt-in flag branch only. (4 existing tests pin this — see CONFIRMED FACTS.)

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (the gap you are closing — AMO Faz-3 governance)
═══════════════════════════════════════════════════════════════════════════════════════════════
`scripts/security/check_secrets.sh` has two scan modes:
  • FULL (default, `grep -rlE` recursive over the filesystem) — gitignore-UNAWARE, so it already scans
    gitignored files for secret patterns.
  • INCREMENTAL (`--changed-since REF`) — sources its file list from
        git diff --name-only REF   ∪   git ls-files --others --exclude-standard
    The `--exclude-standard` flag EXCLUDES gitignored files. So in the fast-path a PreToolUse hook would
    use, a secret in a **gitignored target** (or in literal bytes not yet enumerated by git) is INVISIBLE.

This batch adds a surgical new mode that scans the LITERAL pending bytes directly (from stdin), bypassing
git enumeration entirely — so a secret headed for a gitignored target is caught — WHILE preserving the one
deliberate exception below.

THE CARVE-OUT YOU MUST PRESERVE (operator hard-constraint): a gitignored local `.env` is a sanctioned
local-secrets store → a secret pattern there is **WARN (exit 0)**, never FAIL. Do NOT change that to FAIL.
Every OTHER target (a gitignored non-.env file, or an unknown target) → a secret pattern is **FAIL (exit 1)**.

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (verified by the manager — do NOT re-derive; but DO re-read the files yourself)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. The script: `scripts/security/check_secrets.sh` (292 lines). Key structures you will REUSE:
   • `PATTERNS=( ... )` (16 regexes) + parallel `PATTERN_NAMES=( ... )` (16 human labels, same index).
     These are the detection patterns. You scan with `grep -cE "$p"` / `grep -qE "$p"` and report
     `$name` + count, NEVER the content.
   • Argument parsing (lines ~36-44): a leading `if [ "${1:-}" = "--changed-since" ]` branch sets
     INCREMENTAL=1 + INCREMENTAL_REF + ROOT; else ROOT="${1:-.}". `EXIT=0`.
   • The incremental per-file grep loop (lines ~130-143) greps each candidate file one at a time with
     `grep -lE "$p" "$full"`. This is the loop shape to mirror.
   • The `.env` WARN logic (section 3, lines ~199-228): for each found `.env`/`.env.*` (excluding
     `.env.example`), `git check-ignore -q "$env_file"` → gitignored ⇒ WARN (exit stays 0); not
     gitignored ⇒ FAIL (EXIT=1). THIS is the exact carve-out semantics to reuse for your mode.
   • Structural sections 2-6 are wrapped in `if [ "$INCREMENTAL" = "0" ]; then ... fi` — they are
     SKIPPED in incremental mode. Your new mode also SKIPS them (it is a pure pattern scan of given bytes).
   • Summary block at the end keys off `$EXIT` to print "SECURITY GATE FAIL"/exit 1 vs
     "SECURITY GATE GREEN"/exit 0.

B. The CI wrapper `scripts/ci/check_secrets.sh` (19 lines) is a SEPARATE committed-only `git grep HEAD`
   gate. It is OUT OF SCOPE — do NOT edit it. ("Pending bytes" is irrelevant to a HEAD scan.) You read it
   only to understand the two-copy split.

C. Existing tests that MUST stay green (run them; do not weaken any):
   • `tests/scripts/test_check_secrets.py` (the security scanner): exists+executable; `bash -n` syntax;
     `test_runs_clean_on_empty_dir` (runs `bash SCRIPT <tmp_path>` → exit 0 + "GREEN" in stdout — this is
     why the default positional path MUST stay byte-behaviour-identical); `test_header_states_committed
     _policy_not_on_disk` (the leading comment block — before `set -euo pipefail` — must keep the words
     "committed"/"tracked" + "WARN" + "gitignore"). If you edit the header comment, KEEP those words.
   • `tests/ci/test_check_secrets_sh.py` (the CI wrapper) — you are not touching the wrapper, leave green.

D. ⚠️ THE RECURRING SECRET TRAP (bit the prior manager TWICE — do this right):
   Your new test file/cases will need secret-SHAPED fixtures. You MUST construct them DYNAMICALLY at
   runtime (string concatenation / variables), NEVER as committed literals. Reason: a literal watched
   token (e.g. `ghp_` + 36 alnum, `AIza` + 35, `DATAFORSEO_PASSWORD=<8+>`) committed in a NON-excluded
   file is itself detected — `tests/scripts/test_check_secrets.py` is NOT in any exclude list, and both
   the CI wrapper (`git grep HEAD`) and the full-mode security scanner (filesystem grep) will flag it,
   turning a sibling test RED. Example of the SAFE pattern:
        gkey = "AIza" + "B" * 35          # synthetic Google-API-key shape, not a real/watched token
        sk   = "sk-" + "C" * 24           # synthetic OpenAI/Anthropic shape
   Build every fixture this way. Do NOT paste a real-looking token anywhere.

E. `git check-ignore` needs a git context. To test the gitignored-`.env` WARN branch, create a tmp dir,
   `git init -q` it, write a `.gitignore` containing `.env`, then run the scanner with cwd in that tmp
   repo (or pass an absolute pseudo-path inside it). In a non-git tmp dir, `git check-ignore` returns
   non-zero (not ignored) → your mode FAILs — which is the correct fail-closed default.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create/modify
═══════════════════════════════════════════════════════════════════════════════════════════════
1. `scripts/security/check_secrets.sh`            (add the new `--scan-stdin` mode; existing modes intact)
2. `tests/scripts/test_check_secrets.py`          (extend with the new-mode cases — dynamic fixtures)
Nothing else. No new command, no new schema, no manifest, no CI wrapper, no hook wiring. (This is the
scanner primitive only; any PreToolUse wiring is a SEPARATE future batch and out of scope here.)

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC — the new mode (precise, behaviour-additive)
═══════════════════════════════════════════════════════════════════════════════════════════════
New invocation:  ./check_secrets.sh --scan-stdin [PSEUDO_PATH]
Semantics:
  1. Add `--scan-stdin` as a THIRD top-level arg branch, parsed BEFORE the existing
     `--changed-since`/positional logic, so nothing else changes. It sets a flag (e.g. SCAN_STDIN=1) and
     captures an optional `PSEUDO_PATH="${2:-}"`.
  2. Read ALL of stdin into a private temp file once (`tmp="$(mktemp)"; cat > "$tmp"`), and
     `trap 'rm -f "$tmp"' EXIT` so it is always cleaned up. (Buffer once → you can grep it per-pattern;
     binary-safe; reuses the per-file grep machinery.)
  3. Run the SAME `PATTERNS`/`PATTERN_NAMES` loop over `$tmp` (use `grep -cE`/`grep -qE`). Collect whether
     ANY pattern matched ("hit") and, for the FAIL/report path, the matching `$name` + count. NEVER echo
     the matched content — only the label + count (security invariant).
  4. Verdict:
       • No pattern hit            → print the GREEN summary, exit 0.
       • A pattern hit AND PSEUDO_PATH is non-empty AND `git check-ignore -q -- "$PSEUDO_PATH"` succeeds
         AND basename(PSEUDO_PATH) matches `.env` or `.env.*` but NOT `.env.example`
                                    → print a WARN line (gitignored local .env — local secrets, no leak),
                                      exit 0. (Mirror section 3's WARN wording/spirit.)
       • Any OTHER pattern hit (no pseudo-path, non-gitignored target, or gitignored NON-.env target)
                                    → print "FAIL pattern: $name" + count [REDACTED], exit 1.
  5. In `--scan-stdin` mode, SKIP structural sections 2-6 entirely (like incremental). It is a pure
     literal-bytes pattern scan. Keep the same banner style ("check_secrets.sh — scanning (stdin pending
     bytes)...").
  6. Default positional + `--changed-since` modes: ZERO behaviour change (your diff there should be
     none, or at most the shared summary which already keys off $EXIT).

If you edit the leading header comment to document the new mode, KEEP the words "committed", "tracked",
"WARN", and "gitignore" (test C pins them).

Helper functions are fine; keep each focused. No mutation of the PATTERNS/PATTERN_NAMES arrays.

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD — author these cases in tests/scripts/test_check_secrets.py (all fixtures DYNAMIC, rule D)
═══════════════════════════════════════════════════════════════════════════════════════════════
Use subprocess with `input=` (text or bytes) to feed stdin. SCRIPT path is already defined in the file.
  T1. stdin carrying a synthetic Google-API-key-shaped string, NO pseudo-path
        → returncode == 1; stdout contains the label `google_api_key_AIza`;
          stdout does NOT contain the synthetic key substring (REDACTION proof).
  T2. stdin carrying only benign text ("hello world\nno secrets here\n"), NO pseudo-path
        → returncode == 0; stdout contains "GREEN".
  T3. WARN carve-out: in a tmp `git init` repo whose `.gitignore` lists `.env`, feed a synthetic secret
        on stdin with PSEUDO_PATH pointing at `<tmprepo>/.env`
        → returncode == 0; stdout contains "WARN"; stdout does NOT contain the secret substring.
  T4. FAIL for a gitignored NON-.env target: same tmp repo (also gitignore e.g. `notes.txt`), synthetic
        secret on stdin, PSEUDO_PATH = `<tmprepo>/notes.txt`
        → returncode == 1 (only `.env` gets the WARN carve-out; everything else FAILs even if gitignored).
  T5. A SECOND distinct synthetic pattern (e.g. the `sk-` shape) on stdin, no pseudo-path
        → returncode == 1 with that pattern's label (proves the full PATTERNS loop runs in the new mode).
  T6. (regression) the existing 4 tests stay green — do not modify them; just confirm.
Run the new cases RED first (flag absent → arg falls through to positional ROOT=`--scan-stdin`, a missing
dir → confirm they fail as expected before implementing), then GREEN after implementing.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest (rule 3) — record numbers.
2. Read `scripts/security/check_secrets.sh` fully + both test files + skim `scripts/ci/check_secrets.sh`.
3. Write T1-T5 → run → SHOW them RED for the right reason.
4. Implement the `--scan-stdin` branch (arg parse + mktemp/trap + pattern loop + verdict + carve-out +
   skip-structural). Keep existing modes untouched.
5. Run the new tests → GREEN. Run `bash -n scripts/security/check_secrets.sh`.
6. FULL suite (rule 3 command) → confirm passed >= 2175, failed == 0.
7. Self-review: default + `--changed-since` byte-behaviour-identical? No literal secret committed
   anywhere (all fixtures dynamic)? Redaction holds (no content echoed)? bash 3.2 compatible?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report (do NOT push through) if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• You cannot add the new mode without changing default/`--changed-since` behaviour.
• Any existing test would need weakening/editing to pass.
• You find you need a file outside SCOPE (e.g. a hook wiring, a manifest, the CI wrapper).
• stdin buffering can't be done binary-safe in bash 3.2 without an external dep.
• The carve-out semantics are ambiguous for a case you hit — describe it, don't guess.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE: the pytest numbers you measured.
2. RED PROOF: the new tests failing before implementation (names + the failure reason).
3. DIFF SUMMARY: what changed in check_secrets.sh (the new branch) — confirm default + --changed-since
   are behaviourally unchanged (quote the arg-parse addition).
4. NEW TESTS: names + GREEN results (T1-T5) + confirmation the existing 4 stay green.
5. FULL SUITE: the final `tail -5` (passed/skipped/failed).
6. SECURITY SELF-CHECK: (a) every test fixture is dynamically constructed — no literal watched token
   committed; (b) the mode never echoes matched content (redaction proof from T1/T3); (c) `git
   check-ignore` carve-out fires ONLY for gitignored `.env`/`.env.*` (T3 WARN vs T4 FAIL).
7. ANYTHING you had to decide or that surprised you.
```
