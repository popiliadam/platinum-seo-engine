# `scripts/hooks/` — runtime session hooks vs CI/guard helpers (P2-06)

This directory holds **two distinct classes** of helper. They live together
because they all relate to the Claude Code hook/guard story, but only one class
runs automatically in a live session. The split is locked by
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

If you wire one into a `hooks/*.json` (promote it to runtime) or add a new
helper here, update both the relevant set in
`tests/hooks/test_hook_scripts_runtime_vs_ci.py` and this table.
