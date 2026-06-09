# Claude Code Prompt: Hostile Audit Remediation for `platinum-seo-engine`

You are Claude Code working in the `platinum-seo-engine` repository.

Your task is to fix the defects below. Treat this as a hostile/security-and-correctness remediation pass, not a cosmetic cleanup. Do not revert unrelated user changes. At report generation time the worktree already contained unrelated local edits/untracked files, so inspect before editing and keep your changes scoped.

## Ground Rules

- Start by reading every referenced file and the nearby tests.
- For each finding, add or update regression tests first where feasible.
- Preserve the repository's existing style, contracts, schemas, and CLI UX.
- Do not weaken gates just to make tests pass.
- Do not print or commit real secrets. Any test secret must be constructed dynamically so static secret scanners do not flag the repository.
- After fixes, run the focused tests plus the full suite.

Suggested baseline commands:

```bash
python3 -m pytest --tb=short -q
bash scripts/ci/check_secrets.sh
bash scripts/ci/run_skill_python.py skills/governance/drift-check/SKILL.md
bash scripts/ci/run_skill_python.py skills/governance/schema-validate/SKILL.md
bash scripts/ci/run_skill_python.py skills/governance/glossary-audit/SKILL.md
python3 -m compileall -q scripts tests
```

Audit baseline observed before this handoff: `2446 passed, 7 skipped`; CI helper commands and `compileall` exited cleanly. The defects below are therefore behavioral gaps, not generic broken-test noise.

## Highest Priority Fix Order

1. Secret scanning parity and pending Write/Edit coverage.
2. Timestamp discipline: UTC storage, strict schema format/pattern, and validator parity.
3. Audit/event atomicity for state mutations and Excel writes.
4. Outward action gate bypasses and false positives.
5. Slash command parsing and documentation drift.
6. Hygiene issues: temporary probes, missing enforcement tests, narrow content-gate scope.

---

## Finding 1 - PreToolUse Secret Hook Does Not Scan Pending Write/Edit Content

Severity: Critical

Affected files:

- `hooks/pre-tool-use.json:15`
- `scripts/security/check_secrets.sh:119`

Evidence:

- The hook command is:

```json
"${CLAUDE_PLUGIN_ROOT}/scripts/security/check_secrets.sh" --changed-since HEAD "${CLAUDE_PROJECT_DIR:-.}"
```

- The scanner already has a pending-bytes mode:

```bash
--scan-stdin
```

- Repro:

```bash
FAKE=$(/path/to/python - <<'PY'
print("sk-" + "A" * 24)
PY
)
printf '%s' "$FAKE" | bash scripts/security/check_secrets.sh --changed-since HEAD . >/tmp/pseo-secret-changed.out 2>&1
echo $?
# observed: 0
# observed output included: INCREMENTAL: no files changed since HEAD / SECURITY GATE GREEN

printf '%s' "$FAKE" | bash scripts/security/check_secrets.sh --scan-stdin outputs/content/article.html >/tmp/pseo-secret-stdin.out 2>&1
echo $?
# observed: 1
# observed output included: FAIL pattern openai_or_anthropic_sk_prefix
```

Impact:

A Write/Edit payload containing a secret can be allowed before the file exists or before git sees a changed file. Detection may happen only after the secret is already written, and possibly never for ignored/non-enumerated targets.

Expected fix:

- PreToolUse should scan literal pending bytes for Write/Edit/NotebookEdit style payloads.
- Bash heredoc/file-write paths need either pre-detection or a post-write quarantine path with tests.
- Keep `--changed-since` as an additional incremental scan, not the only gate.

Acceptance tests:

- A Write hook payload with dynamically constructed `sk-`-like content blocks.
- A Write hook payload to a gitignored non-env target blocks.
- A sanctioned local `.env` behavior remains WARN/allow if that is the intended contract.

---

## Finding 2 - CI Secret Scanner Is Much Narrower Than Runtime Scanner

Severity: Critical

Affected files:

- `.github/workflows/ci.yml:89`
- `scripts/ci/check_secrets.sh:9`
- `scripts/security/check_secrets.sh:69`

Evidence:

- CI calls only:

```bash
bash scripts/ci/check_secrets.sh
```

- `scripts/ci/check_secrets.sh` greps only a tiny set:

```bash
DATAFORSEO_PASSWORD=[...]
info@demo-agency
3bf73e0893f69b42
ghp_[...]
```

- Runtime scanner knows many more classes: Google API key class, OpenAI/Anthropic `sk-` class, GCP service account fields, PEM private-key headers, GitHub `gho/ghs/ghu`, AWS, Slack, DataForSEO env literals.

Impact:

A committed secret class known to the runtime scanner can pass GitHub Actions because CI uses a different and weaker scanner.

Expected fix:

- CI should call the canonical scanner or import/share the exact same pattern inventory.
- Add tests that compare the CI scanner's pattern labels/scope with the runtime scanner.
- Avoid static test strings that match secret regexes in the repository; generate them dynamically in tests.

---

## Finding 3 - Event Writer Redaction Misses Secret Classes

Severity: Critical

Affected file:

- `scripts/state/events_writer.py:82`

Evidence:

`_SECRET_VALUE_PATTERNS` redacts only:

- OpenAI-like `sk-`
- Anthropic-like `sk-ant-`
- GitHub classic/fine-grained PAT classes
- AWS access key id class

It does not redact several classes that `scripts/security/check_secrets.sh` knows: Google API key class, Slack tokens, GCP service-account fields, PEM private-key headers, and more.

Repro:

```bash
TMP=$(mktemp -d /tmp/pseo-audit-events-XXXXXX)
PYTHONPATH="$PWD" python3 - <<'PY' "$TMP"
import json, pathlib, sys
from scripts.state import events_writer

ws = pathlib.Path(sys.argv[1])
slug = "auditproj"
fake_google = "AI" + "za" + "A" * 35
fake_slack = "xoxb-" + "A" * 20
fake_openai = "sk-" + "A" * 24

events_writer.append_work(
    project_id=slug,
    event_type="manual",
    task_id="T-12345",
    note=f"google={fake_google} slack={fake_slack} openai={fake_openai}",
    workspace_root=ws,
)
obj = json.loads((ws / "projects" / slug / "_state" / "events.jsonl").read_text())
print("contains_google=", fake_google in obj["note"])
print("contains_slack=", fake_slack in obj["note"])
print("contains_openai=", fake_openai in obj["note"])
PY
```

Observed:

```text
contains_google= True
contains_slack= True
contains_openai= False
```

Impact:

Audit logs can persist secrets that the repository otherwise claims to detect.

Expected fix:

- Redaction patterns should be shared with or generated from the canonical scanner inventory.
- Add tests covering every scanner label that can appear as a value in event metadata.

---

## Finding 4 - Event Timestamp Format Can Be Invalid

Severity: Critical

Affected file:

- `scripts/state/events_writer.py:206`
- `scripts/state/events_writer.py:212`

Evidence:

`_get_validator()` returns `Draft7Validator(schema)` without a `FormatChecker`. Caller-provided timestamps are preserved by the envelope population path, so schema `format: "date-time"` is not enforced.

Repro:

```bash
TMP=$(mktemp -d /tmp/pseo-audit-badts-XXXXXX)
PYTHONPATH="$PWD" python3 - <<'PY' "$TMP"
import json, pathlib, sys
from scripts.state import events_writer

ws = pathlib.Path(sys.argv[1])
events_writer.append_work(
    project_id="auditproj",
    event_type="manual",
    task_id="T-12345",
    note="bad ts probe",
    timestamp="not-a-date",
    workspace_root=ws,
)
obj = json.loads((ws / "projects" / "auditproj" / "_state" / "events.jsonl").read_text())
print(obj["timestamp"])
PY
```

Observed:

```text
not-a-date
```

Impact:

The append-only event log can contain unparsable timestamps, violating `rules/time-discipline.md`.

Expected fix:

- Event writer validation must enforce timestamp format and UTC storage.
- Prefer a shared strict validator helper rather than repeated raw `Draft7Validator(...)`.
- Add a regression test that invalid `timestamp` is rejected before append.

---

## Finding 5 - Date-Time Validator Accepts Naive and Non-UTC Timestamps

Severity: Critical

Affected files:

- `scripts/validation/validate_schema.py:54`
- `rules/time-discipline.md:10`
- `rules/time-discipline.md:19`
- `rules/time-discipline.md:59`

Evidence:

The repo's time rule says storage timestamps must be UTC ISO 8601 with `Z`. The custom `date-time` checker uses:

```python
datetime.fromisoformat(value.replace("Z", "+00:00"))
```

That accepts timezone-naive strings and non-UTC offsets.

Repro:

```bash
PYTHONPATH="$PWD" python3 - <<'PY'
import json
from scripts.validation.validate_schema import build_validator

schema = json.load(open("schemas/consent.schema.json"))
base = {
    "schema_version": "1.0",
    "seq": 0,
    "run_id": "r",
    "action": "fs_delete",
    "target": "/tmp/x",
    "target_hash": "a" * 64,
    "granted_by": "operator",
    "prev_hash": "0" * 64,
    "entry_hash": "b" * 64,
}
for ts in [
    "not-a-date",
    "2026-06-09T18:26:07.147994",
    "2026-06-09T15:26:07Z",
    "2026-06-09T18:26:07+03:00",
]:
    errors = list(build_validator(schema).iter_errors({**base, "granted_at": ts}))
    print(ts, "errors=", [(list(e.path), e.message) for e in errors])
PY
```

Observed:

```text
not-a-date -> errors present
2026-06-09T18:26:07.147994 -> []
2026-06-09T15:26:07Z -> []
2026-06-09T18:26:07+03:00 -> []
```

Impact:

The enforcement layer contradicts the documented storage invariant. Local Istanbul timestamps can be silently accepted in storage.

Expected fix:

- Decide the exact canonical storage form. The rule currently says `YYYY-MM-DDTHH:MM:SSZ`.
- Enforce it with schema pattern and a strict `FormatChecker`.
- Add `tests/schemas/test_time_format.py`; note the rule already claims this test exists, but it does not.

---

## Finding 6 - Consent and Session CLIs Write Naive Local Timestamps

Severity: Critical

Affected files:

- `scripts/state/consent_ledger.py:488`
- `scripts/state/session_binding.py:328`
- `schemas/consent.schema.json:38`
- `schemas/session-marker.schema.json:19`

Evidence:

Consent CLI:

```python
now_iso=datetime.now().isoformat()
```

Session binding CLI:

```python
datetime.now().isoformat()
```

`schemas/consent.schema.json` describes `granted_at` as UTC ISO 8601. `schemas/session-marker.schema.json` currently documents local ISO 8601, which conflicts with the global time rule.

Controlled repro:

```bash
TMP=$(mktemp -d /tmp/pseo-audit-time-XXXXXX)
HOME_TMP=$(mktemp -d /tmp/pseo-audit-home-XXXXXX)
mkdir -p "$TMP/projects/auditproj" "$TMP/shared"
printf '{"active_project":"auditproj"}\n' > "$TMP/shared/active.json"

HOME="$HOME_TMP" \
CLAUDE_CODE_SESSION_ID=session123 \
PSEO_WORKSPACE_ROOT="$TMP" \
PYTHONPATH="$PWD" \
python3 -m scripts.state.consent_ledger approve run123 fs_delete /tmp/x

jq -r '.granted_at' "$TMP/projects/auditproj/_state/consent.jsonl"
```

Observed:

```text
2026-06-09T18:26:07.147994
```

Impact:

Consent/session state can violate UTC storage. When combined with weak validation, these invalid timestamps become accepted state.

Expected fix:

- Use `datetime.now(timezone.utc)` and canonical `Z` formatting.
- Update session marker schema/docs to UTC storage, unless it is explicitly a display-only artifact.
- Add tests for consent/session marker timestamp form.

---

## Finding 7 - Persistent Workspace Config Overrides Explicit `PSEO_WORKSPACE_ROOT`

Severity: High

Affected file:

- `scripts/state/session_binding.py:153`

Evidence:

`resolve_workspace_root()` resolves in this order:

```text
~/.config/pseo/config.json -> env -> None
```

Repro:

```bash
HOME_TMP=$(mktemp -d /tmp/pseo-audit-home-XXXXXX)
mkdir -p "$HOME_TMP/.config/pseo"
printf '{"workspace_root":"/tmp/config-wins"}\n' > "$HOME_TMP/.config/pseo/config.json"

HOME="$HOME_TMP" \
PSEO_WORKSPACE_ROOT=/tmp/env-loses \
PYTHONPATH="$PWD" \
python3 - <<'PY'
from scripts.state.session_binding import resolve_workspace_root
print(resolve_workspace_root())
PY
```

Observed:

```text
/tmp/config-wins
```

Impact:

A stale global config can route approvals, bindings, and state writes to the wrong workspace even when the active session explicitly sets `PSEO_WORKSPACE_ROOT`. This is cross-workspace contamination risk.

Expected fix:

- Re-evaluate precedence. In most CLI/hook contexts explicit env should win over persistent config.
- At minimum, detect conflict and fail loudly unless an explicit override flag is present.
- Add tests for env-vs-config precedence and conflict messaging.

---

## Finding 8 - Excel Transaction Mutates Workbook Before Provenance Event

Severity: High

Affected file:

- `scripts/excel/transaction.py:987`

Evidence:

The implementation does:

```text
backup -> atomic save -> rotate backups -> release lock -> emit provenance event
```

The comment says event failure does not roll back the write.

Repro:

```bash
TMP=$(mktemp -d /tmp/pseo-audit-xlsx-XXXXXX)
PYTHONPATH="$PWD" python3 - <<'PY' "$TMP"
import pathlib, sys
from openpyxl import load_workbook
from scripts.excel import transaction

ws = pathlib.Path(sys.argv[1])
slug = "auditproj"
proj = ws / "projects" / slug
state = proj / "_state"
(state / "events.jsonl").mkdir(parents=True)
wb = proj / "master.xlsx"
row = {
    "query": "buy test",
    "url": "https://example.com/a",
    "current_position": 12.5,
    "impressions_30d": 100,
    "clicks_30d": 3,
    "ctr_pct": 3.0,
    "potential_clicks": 20,
    "opportunity": "title rewrite",
    "action": "improve title",
    "priority": "HIGH",
}
try:
    transaction.append(wb, "quick_wins", [row], slug)
    print("append_returned=success")
except Exception as e:
    print("append_raised=", type(e).__name__, str(e).splitlines()[0])

print("workbook_exists=", wb.exists())
if wb.exists():
    book = load_workbook(wb)
    sh = book["quick_wins"]
    print("max_row=", sh.max_row)
    print("data_row5=", [sh.cell(row=5, column=i).value for i in range(1, 11)])
PY
```

Observed:

```text
append_raised= EventPathError cannot open ... events.jsonl: [Errno 21] Is a directory
workbook_exists= True
data_row5= ['buy test', 'https://example.com/a', 12.5, 100, 3, 3, 20, 'title rewrite', 'improve title', 'HIGH']
```

Impact:

Caller sees failure and may retry, but workbook is already changed and audit provenance is missing. This breaks the "append-only audit trail" assumption.

Expected fix:

- Make workbook mutation and provenance emission a coherent transaction, or write a durable anomaly/repair record.
- Consider event preflight before saving, save under lock, and only return success when both state and provenance are consistent.
- Add tests for event-path failure not leaving untracked workbook mutation, or explicitly documented compensating behavior.

---

## Finding 9 - Workflow Runner Persists Run State When Event Emission Fails

Severity: High

Affected files:

- `scripts/state/workflow_runner.py:430`
- `scripts/state/workflow_runner.py:790`

Evidence:

`create_run()` writes the workflow JSON and then calls `_emit_workflow_event()`. `_emit_workflow_event()` catches every exception and only logs a warning.

Repro:

```bash
TMP=$(mktemp -d /tmp/pseo-audit-wf-XXXXXX)
PYTHONPATH="$PWD" python3 - <<'PY' "$TMP"
import pathlib, sys
from scripts.state import workflow_runner

ws = pathlib.Path(sys.argv[1])
slug = "auditproj"
state = ws / "projects" / slug / "_state"
(state / "events.jsonl").mkdir(parents=True)
h = workflow_runner.create_run("probe-skill", slug, [{"name": "one"}], workspace_root=ws)
print("returned_status=", h.status)
print("run_path_exists=", h.path.exists())
print("events_path_is_dir=", (state / "events.jsonl").is_dir())
print("workflow_files=", [p.name for p in (state / "workflows").glob("*.json")])
PY
```

Observed:

```text
WARNING: workflow event emit failed (non-blocking) ...
returned_status= running
run_path_exists= True
events_path_is_dir= True
workflow_files= [...]
```

Impact:

Workflow state transitions can exist without corresponding audit events. The audit trail can no longer reconstruct the real state machine.

Expected fix:

- Decide whether event emission is mandatory for workflow state writes. For audit-grade state, it should be.
- If non-blocking remains intentional, add durable anomaly records and reconciliation tooling/tests.
- Add regression tests for failed event append behavior.

---

## Finding 10 - Outward Action Gate Can Be Bypassed With Common Wrappers

Severity: High

Affected file:

- `scripts/hooks/outward_action_gate.py:185`

Evidence:

Classification is leading-token based. It strips path from the first token and checks `rm`, `git`, `curl/wget`, etc. It does not unwrap common command wrappers.

Repro:

```bash
PYTHONPATH="$PWD" python3 - <<'PY'
from scripts.hooks.outward_action_gate import classify

cases = [
    "rm -rf /tmp/pseo-x",
    "sudo rm -rf /tmp/pseo-x",
    "command rm -rf /tmp/pseo-x",
    "env rm -rf /tmp/pseo-x",
    "git push origin main",
    "sudo git push origin main",
    "env git push origin main",
]
for c in cases:
    print(c, "=>", classify("Bash", {"command": c}))
PY
```

Observed:

```text
rm -rf /tmp/pseo-x => ('fs_delete', '/tmp/pseo-x')
sudo rm -rf /tmp/pseo-x => None
command rm -rf /tmp/pseo-x => None
env rm -rf /tmp/pseo-x => None
git push origin main => ('git_push', 'origin main')
sudo git push origin main => None
env git push origin main => None
```

Impact:

The same destructive/outward action can bypass consent with harmless-looking shell prefixes.

Expected fix:

- Parse shell tokens more semantically.
- Unwrap `sudo`, `command`, `env`, `builtin`, `time`, `nohup`, and similar safe wrapper forms.
- Add tests for wrapper variants and for quoted/flagged commands.

---

## Finding 11 - Outward Action Gate Misses Non-curl Network Writes

Severity: High

Affected file:

- `scripts/hooks/outward_action_gate.py:208`

Evidence:

The gate checks HTTP writes through `curl/wget` style tokens. A Python one-liner that performs a POST is not classified.

Repro:

```bash
PYTHONPATH="$PWD" python3 - <<'PY'
from scripts.hooks.outward_action_gate import classify

cmd = "python3 -c \"import urllib.request; urllib.request.urlopen('https://example.com', data=b'x')\""
print(classify("Bash", {"command": cmd}))
PY
```

Observed:

```text
None
```

Impact:

Network POST consent can be bypassed by moving the write into Python/Ruby/Node/Perl one-liners.

Expected fix:

- Decide threat model. If all net writes need consent, classification must cover interpreter one-liners or use a stricter policy for suspicious commands.
- Add tests for common interpreter network write patterns.

---

## Finding 12 - Localhost MCP Status POST Is Falsely Gated as External Network Write

Severity: Medium

Affected files:

- `commands/pseo-status.md:79`
- `scripts/hooks/outward_action_gate.py:208`

Evidence:

`/pseo-status` performs a local health probe:

```bash
curl -sf -m 3 -X POST http://127.0.0.1:11435/mcp ...
```

Classifier result:

```bash
PYTHONPATH="$PWD" python3 - <<'PY'
from scripts.hooks.outward_action_gate import classify
cmd = "curl -sf -m 3 -X POST http://127.0.0.1:11435/mcp -H Content-Type:application/json -d '{\"jsonrpc\":\"2.0\"}'"
print(classify("Bash", {"command": cmd}))
PY
```

Observed:

```text
('net_post', 'http://127.0.0.1:11435/mcp')
```

Impact:

A harmless local status check can require operator consent, making `/pseo-status` noisy or broken.

Expected fix:

- Add explicit localhost/loopback policy.
- Local MCP calls may need a separate action class from external `net_post`.
- Keep Indexing API and public network writes gated.

---

## Finding 13 - Slash Command Argument Parsing Breaks Quoted Paths

Severity: Medium

Affected files:

- `commands/pseo-approve.md:38`
- `commands/pseo-bind.md:27`
- Related prior doc: `docs/bugs/2026-06-09-slash-command-positional-args-empty.md`

Evidence:

Commands use:

```bash
set -- $ARGUMENTS
```

`pseo-bind` also passes `$2 $3` unquoted.

Repro:

```bash
bash -lc 'ARGUMENTS="sess-abc fs_delete \"/tmp/My Dir\""; set -- $ARGUMENTS; printf "argc=%s\n1=[%s]\n2=[%s]\n3=[%s]\n4=[%s]\n" "$#" "$1" "$2" "$3" "$4"'
bash -lc 'ARGUMENTS="auditproj --workspace \"/tmp/Workspace Root\""; set -- $ARGUMENTS; printf "argc=%s\n1=[%s]\n2=[%s]\n3=[%s]\n4=[%s]\n" "$#" "$1" "$2" "$3" "$4"'
```

Observed:

```text
3=["/tmp/My]
4=[Dir"]
3=["/tmp/Workspace]
4=[Root"]
```

Impact:

Approval targets with spaces hash differently or truncate. Workspace paths with spaces break.

Expected fix:

- Avoid shell reparsing of `$ARGUMENTS` for structured arguments.
- Prefer Python/argparse wrappers or a robust quoted-argument parser.
- Quote every variable passed to shell commands.
- Add tests with spaces in target/workspace paths.

---

## Finding 14 - `/pseo-init` Documents and Passes Unsupported `--schema-version`

Severity: Medium

Affected files:

- `commands/pseo-init.md:6`
- `commands/pseo-init.md:41`
- `commands/pseo-init.md:45`
- `scripts/state/bootstrap_project.py:153`
- `scripts/state/bootstrap_project.py:54`

Evidence:

Command frontmatter advertises:

```text
[--schema-version 1.5]
```

The command body discusses forcing `--schema-version=1.4`. But `bootstrap_project.py` has no such argparse option.

Repro:

```bash
PSEO_WORKSPACE_ROOT=/tmp/pseo-ws \
PYTHONPATH="$PWD" \
python3 scripts/state/bootstrap_project.py --project auditproj --schema-version 1.4 --dry-run
echo $?
```

Observed:

```text
error: unrecognized arguments: --schema-version 1.4
exit=2
```

Additional drift:

- `commands/pseo-init.md:45` documents `allowed_directory: "/Users/apple/seo_spider_mcp_server"`.
- Actual `DEFAULT_SF_MCP_BLOCK` uses `"allowed_directory": None`.

Expected fix:

- Either implement `--schema-version` fully or remove it from command docs/pass-through logic.
- Align SF default docs with code.
- Add a command-doc-vs-argparse regression test.

---

## Finding 15 - README and Packaging Counts Are Stale

Severity: Low/Medium

Affected file:

- `README.md:53`
- `README.md:130`
- `README.md:243`
- `README.md:245`
- `README.md:251`

Evidence:

README says:

- 18 slash commands
- 21 JSON schemas
- 1,100+ pytest tests
- top-level version and roadmap version disagree (`v2.0.0` area vs `Current: v1.9.5`)

Tracked filesystem count at report generation:

```bash
git ls-files 'commands/*.md' | wc -l
# observed: 24
git ls-files 'skills/**/SKILL.md' | wc -l
# observed: 45
git ls-files 'schemas/*.schema.json' | wc -l
# observed: 26
git ls-files 'hooks/*.json' | wc -l
# observed: 6
```

Test baseline observed:

```text
2446 passed, 7 skipped
```

Impact:

Install/marketplace/docs consumers get stale capability information. This also indicates count drift checks are incomplete or not covering README.

Expected fix:

- Update README counts/version/test-count language.
- Prefer dynamic tests that assert README count snippets match `git ls-files` or a single source of truth.

---

## Finding 16 - Content Write Gate Does Not Treat Uppercase `.HTML` as HTML

Severity: Low

Affected file:

- `scripts/hooks/validate_content_write.py:61`

Evidence:

```python
if not norm.endswith(".html") or norm.endswith(".template.html"):
    return False
```

Repro:

```bash
PYTHONPATH="$PWD" python3 - <<'PY'
from scripts.hooks.validate_content_write import is_content_html_path
print(is_content_html_path("/tmp/workspace/projects/a/outputs/content/article.HTML"))
PY
```

Observed:

```text
False
```

Impact:

Generated content written with uppercase extension can bypass content rules.

Expected fix:

- Case-fold the suffix check while preserving template exclusion.
- Add tests for `.HTML`, `.Html`, and `.template.HTML`.

---

## Finding 17 - Temporary `env_probe.py` Is Still Wired Into Production Hooks

Severity: Low/Medium hygiene and privacy risk

Affected files:

- `hooks/pre-tool-use.json:27`
- `hooks/post-tool-use.json:15`
- `hooks/session-start.json:15`
- `hooks/user-prompt-submit.json:15`
- `hooks/stop.json:21`
- `scripts/hooks/env_probe.py:101`
- `scripts/hooks/README.md:58`

Evidence:

Multiple hooks still run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/env_probe.py"
```

Status messages still say:

```text
AMO batch-0a env probe (temporary diagnostic)...
```

The README documents removal steps for this temporary probe. The probe writes to `~/.config/pseo/hook-probe.jsonl` and uses `datetime.now().isoformat()`.

Impact:

Temporary diagnostic instrumentation is enabled by default, creating log noise, privacy exposure, and additional timestamp-discipline drift.

Expected fix:

- Decide whether the probe is still needed.
- If not needed, remove it from hooks and tests as the README says.
- If needed, rename it out of "temporary", document retention/privacy, and fix timestamp format.
- Add a CI guard so "temporary diagnostic" hooks cannot ship accidentally.

---

## Finding 18 - Time Discipline Claims Missing Enforcement Test

Severity: Low/Medium

Affected file:

- `rules/time-discipline.md:59`

Evidence:

Rule claims:

```text
tests/schemas/test_time_format.py her PR'da koşar
```

But:

```bash
find tests -path '*test_time_format.py' -print
# observed: no output
rg -n 'test_time_format' tests schemas rules docs
# observed only the rule and an older audit reference
```

Impact:

The enforcement section overstates CI coverage. This helped timestamp regressions remain undetected.

Expected fix:

- Add the test file and enforce all timestamp-bearing schemas.
- Or update the rule if the intended enforcement is different.

---

## Finding 19 - Many Schema Callers Use Raw `Draft7Validator` Without Format Enforcement

Severity: Medium

Affected examples:

```text
scripts/state/schedule.py:170
scripts/state/migrate_legacy_events.py:69
scripts/excel/transaction.py:287
scripts/state/events_writer.py:212
scripts/validation/validate_invariants.py:2063
scripts/state/consent_ledger.py:169
scripts/state/workflow_runner.py:125
scripts/state/cost_ledger.py:177
scripts/orchestration/coverage.py:133
scripts/discovery/competitive_analysis_transform.py:474
scripts/reporting/portfolio_task_heatmap.py:137
scripts/reporting/portfolio_overview.py:160
scripts/reporting/portfolio_kpi_trend.py:147
scripts/reporting/portfolio_monthly_roundup.py:113
scripts/reporting/portfolio_heatmap.py:143
```

Evidence:

`rg -n "Draft7Validator\\(" scripts` shows many direct validators. Some may validate schemas without formats, but state/audit-related callers should not silently skip `format`.

Impact:

Even if `scripts/validation/validate_schema.py` is fixed, runtime writers may continue accepting invalid URI/date/date-time values.

Expected fix:

- Create a shared validation utility for Draft 7 + strict repo format checker.
- Migrate state/audit/workflow/cost/schedule callers first.
- Add targeted tests around timestamp-bearing runtime writers.

---

## Finding 20 - SF MCP HTTP Client Follows Redirects

Severity: Low/Needs threat-model decision

Affected file:

- `scripts/util/sf_mcp_client.py:599`

Evidence:

```python
httpx.Client(..., follow_redirects=True)
```

Impact:

The client is intended for local SF MCP HTTP transport. Following redirects can silently turn a local call into another destination if the local service or an intercepting endpoint returns a redirect. This may be harmless in practice, but it should be an explicit decision for a consent/audit-heavy tool.

Expected fix:

- Decide whether redirects are allowed for local MCP.
- If allowed, restrict redirect destinations to loopback and same port, and test it.
- If not allowed, set `follow_redirects=False` and surface redirect as a clear error.

---

## Additional Notes for Claude Code

- There was an older audit file with overlapping themes: `docs/audits/2026-06-05_ruthless_claude_code_handoff.md`. Do not blindly copy it; use it as context only.
- The current repo has user-local changes. Do not run destructive git commands. Do not reset or checkout files unless explicitly requested by the human.
- Prefer adding regression tests near existing test suites:
  - `tests/hooks/` for hook/gate behavior.
  - `tests/scripts/` or `tests/state/` for event/consent/workflow behavior.
  - `tests/schemas/` for timestamp schema enforcement.
  - `tests/ci/` for scanner parity and README/count drift.

## Definition of Done

- Every finding above is either fixed with a regression test or explicitly documented as an accepted risk with a strong reason.
- Secret scanning has a single source of truth across hooks, runtime redaction, and CI.
- Storage timestamps are canonical UTC and rejected otherwise.
- Audit/event writes cannot silently diverge from state mutations.
- Outward-action consent cannot be bypassed through common shell wrappers.
- False-positive local MCP status calls do not require external network consent.
- Slash commands handle quoted paths and spaces safely.
- README and command docs match live code.
- Full test suite and CI helper scripts pass.
