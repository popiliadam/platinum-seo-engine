# `scripts/hooks/` — runtime session hooks vs CI/guard helpers (P2-06)

This directory holds **three distinct classes** of helper. They live together
because they all relate to the Claude Code hook/guard story, but only the runtime
class runs automatically in a live session. The split is locked by
[`tests/hooks/test_hook_scripts_runtime_vs_ci.py`](../../tests/hooks/test_hook_scripts_runtime_vs_ci.py)
— change a script's class and that test fails until this doc is updated too.

## 1. Runtime session hooks (wired into `hooks/*.json`)

Claude Code runs these automatically at the named lifecycle event. They ARE
referenced by a `hooks/*.json` handler.

| Script | Wired in | Event |
|--------|----------|-------|
| `stop_validation.py` | `hooks/stop.json` | `Stop` — validates the session's final state before the turn ends |
| `subagent_output_validate.py` | `hooks/subagent-stop.json` | `SubagentStop` — validates a subagent's output before it returns |
| `validate_content_write.py` | `hooks/pre-tool-use.json` | `PreToolUse` — blocks a generated-blog HTML write (`outputs/{blog,content}/…/*.html`) that violates a RED content rule: the AI-disclosure ban + R-22/R-43/R-77/R-61. Calls `scripts/validation/content_validator.py` |
| `audit_post_tool_use.py` | `hooks/post-tool-use.json` | `PostToolUse` — appends a session-attributed `audit` event for each Edit/Write/Bash to the bound project's `events.jsonl` (session marker → `shared/active.json` fallback; fixes AMO bug H1 cross-session contamination). Redacts Bash args; non-blocking. Calls `scripts/state/events_writer.append_audit` |
| `intent_router.py` | `hooks/user-prompt-submit.json` | `UserPromptSubmit` — classifies the prompt (AMO L1 intent guarantee). A Tier-1 canonical match to a known workflow injects a one-line `/pseo-run <workflow> <slug>` instruction (stdout → model context) **and** writes the `intent_declared` marker (`shared/sessions/<sid>.intent.json`, read by the batch-2c Stop denetçi); a Tier-2 prompt falls back to the whats-next advisory and supersedes any stale intent. Re-emits the `PSEO context:` line — it **replaces** the legacy inline static-bash command, so there is ONE voice per prompt. Non-blocking (any error → advisory + exit 0). Calls `scripts/state/session_binding` |
| `denetci.py` | `hooks/stop.json` | `Stop` — AMO L3 denetçi (the safety half of the engagement guarantee). Added as the **2nd** Stop command (`stop_validation.py` stays first). At turn end it READS the current intent marker (`intent_router`, 1c) + the freshest coverage record written THIS turn (`coverage`, 1a; freshness = file mtime ≥ the marker's mtime, so a stale prior pass is ignored). If a `declared` workflow did not run, it **blocks** the turn end with a Turkish fix command (`/pseo-run <workflow> <slug>`); if it ran but is incomplete/failed, it blocks with the `--resume` remediation (`remediation`, 1d); if it `paused` on an external dependency (GSC/DFS) it **allows** the turn to end and flags it RED on stderr. READ-ONLY (writes nothing), non-blocking-on-error (any failure → allow turn-end), and respects `stop_hook_active` (never re-blocks). Blocks ONLY by emitting `{"decision":"block","reason":…}` to stdout |
| `outward_action_gate.py` | `hooks/pre-tool-use.json` | `PreToolUse` — AMO batch-2b outward-action consent gate (the safety half of smart autonomy, spec G4). Added as a **second** `PreToolUse` block (matcher `Bash\|mcp__gsc__submit_sitemap`); the existing block is untouched and hooks compose (either can deny). Before a gated action runs it `classify()`s it to one of `git_push` / `fs_delete` / `net_post` / `mcp_submit` / `index_update`, hashes the concrete target, and **blocks** it (`exit 2`) unless THIS session's bound project's consent ledger holds an intact-chain entry for that `session_id` + `action` + `target_hash` (`consent_ledger.has_session_consent`). The deny prints the exact copy-paste `/pseo-approve …` fix with the same target. CONSERVATIVE classify (only a clear match is gated; a non-gated command always exits 0), **READ-ONLY** (writes nothing), fail-CLOSED on the gated path / fail-OPEN on the non-gated path. Calls `scripts/state/consent_ledger` + `scripts/state/session_binding` |
| `ai_disclosure_rescan.py` | `hooks/post-tool-use.json` | `PostToolUse` — AMO batch-2e AI-disclosure surface rescan (the POST-write quarantine twin of `validate_content_write.py`). Added as the **3rd** `PostToolUse` command (`audit_post_tool_use.py` + `env_probe.py` untouched; matcher `Edit\|Write\|Bash`). A PostToolUse hook fires AFTER the write, so it cannot prevent — it must **detect + revert**: after any Edit/Write/Bash it re-scans a *just-written* blog-HTML file (`outputs/{blog,content}/…/*.html`; Write/Edit `file_path` or a Bash `.html` token that EXISTS and has a fresh mtime — a mere `cat <file>` READ leaves mtime old, so it is never quarantined) via `content_validator.validate_content`. On a RED `AI-disclosure` finding it **quarantine-renames** the file off the live surface (`os.replace` → `<path>.BLOCKED-ai-disclosure`; the live `.html` is gone, the content is preserved for operator review) and emits `{"decision":"block","reason":…}` to stdout telling the model to rewrite without the disclosure. This closes the **Bash/heredoc bypass** of the PreToolUse Write-gate (the Vento `vcc-` pattern writes the body with a `cat > … << 'EOF'` heredoc, which never invokes Write/Edit). REUSES `content_validator` + `validate_content_write.is_content_html_path` + `_resolve_profile` (no duplicated detection); a Bash path built from a shell variable is a documented Path-A limit. Non-blocking-on-error (a rescan bug → exit 0). Calls `scripts/validation/content_validator` + `scripts/hooks/validate_content_write` |

> Note: `hooks/pre-tool-use.json` also wires `scripts/security/check_secrets.sh`
> (a *security* helper, not under `scripts/hooks/`).

## 2. Guard helpers (CI / pre-commit / manual — NOT runtime hooks)

These are **not** wired into any `hooks/*.json`, so they do **not** run in a live
session. They are the enforcement scripts cited by `rules/*.md` for a discipline,
and each is covered by its own pytest unit test. Invoke them in CI, a pre-commit
hook, or manually.

| Script | Discipline (rules/*.md) | Unit test |
|--------|-------------------------|-----------|
| `check_append_only.sh` | `rules/append-only-state.md` | `tests/hooks/test_check_append_only.py` |
| `check_excel_writer.py` | `rules/excel-discipline.md` | `tests/hooks/test_check_excel_writer.py` |
| `check_naming.py` | `rules/naming.md` | `tests/hooks/test_check_naming.py` |
| `validate_before_write.py` | `rules/schema-first.md` | `tests/hooks/test_validate_before_write.py` |

Why they are not runtime hooks: they guard the **repository** (commits, file
layout, schema-before-write), not the live tool lifecycle. Wiring them as
`PreToolUse` hooks would add per-call latency and false positives on legitimate
in-session edits; running them at commit/CI time is the right boundary.

## 3. Diagnostic instrumentation (TEMPORARY — AMO batch 0a)

These are **temporary** scripts added to empirically confirm how the AMO
initiative can bind one Claude session to one project. They record / report the
SAFE shape of hook stdin payloads (KEYS only — never message / prompt /
tool_input / tool_response VALUES) and which env vars reach hooks, across
VSCode / Mac-app / CLI. **Remove them once the AMO session-binding mechanism is
confirmed** (runbook below).

| Script | Class | Wired in | Role |
|--------|-------|----------|------|
| `env_probe.py` | runtime (temporary) | all five event files — appended as a non-blocking command entry | On each fire, append one JSON line to `${PSEO_PROBE_LOG:-~/.config/pseo/hook-probe.jsonl}` describing the payload's KEYS + `session_id` + env-var presence. Always exits 0 (never blocks the hook chain). |
| `env_probe_report.py` | diagnostic (manual) | — (operator runs on demand) | Summarise the probe log: per-`session_id` N/5 event coverage + a "session_id stable & present" verdict. |

**To remove (revert batch 0a):**
1. Delete `scripts/hooks/env_probe.py` and `scripts/hooks/env_probe_report.py`.
2. Remove the appended `env_probe.py` command entry from the five `hooks/*.json`
   files (the entry whose `statusMessage` is `"AMO batch-0a env probe …"`).
3. Delete `tests/hooks/test_env_probe.py`.
4. In `tests/hooks/test_hook_scripts_runtime_vs_ci.py` drop `env_probe.py` from
   `RUNTIME_HOOK_SCRIPTS` and delete the `DIAGNOSTIC_HOOK_SCRIPTS` set (and its
   test); in `tests/hooks/test_stop_validation.py` restore the Stop assertion to
   `len(handler["hooks"]) == 1`.
5. Delete this section and restore the "two distinct classes" wording above.

If you wire one into a `hooks/*.json` (promote it to runtime) or add a new
helper here, update the relevant set in
`tests/hooks/test_hook_scripts_runtime_vs_ci.py` and this table.
