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
