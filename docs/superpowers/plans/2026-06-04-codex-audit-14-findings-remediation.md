# Codex Audit (14 Findings) Remediation Implementation Plan

> **EXECUTION STATUS (2026-06-04):** Batches **A–E (engine)** + **Batch F safe/medium** (workspace F3 workflow JSONs, F4 language codes, F5 CLAUDE.md) were **executed directly in the authoring session** — engine: 12 atomic commits `a6e5c55`..`7262dc2`, `pytest 1591 passed / 9 skipped / 0 failed`; workspace: 1 commit `a6a8a45`. **Neither repo pushed yet.** **Remaining = Batch F's 4 RED client workbooks** (eykom F-17/F-18, lastiksa F-01, vento F-16, noran F-05) — deferred; they need the operator's domain decisions on live client data. The unchecked `- [ ]` boxes below are historical authoring artifacts; the live TODO is only the RED-workbook steps in Batch F.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 14 codex-audit findings (verified 2026-06-04) that prove implementation drift between the engine's validators/docs/commands and the live workspace data — and add a regression test for each drift class so the same mismatch cannot return.

**Architecture:** Two repos. The **engine** (`/Users/apple/Documents/platinum-seo-engine`) owns schemas, validators, commands, hooks, skills, docs. The **workspace** (`/Users/apple/Documents/platinum-seo-workspace`) owns live project data (Excel workbooks, project configs, event/workflow state). Engine fixes and workspace data fixes are committed **separately** (never mixed in one commit). Most fixes are test-first (TDD): write the regression test that fails on today's drift, then fix, then green.

**Tech Stack:** Python 3 (stdlib + `jsonschema` Draft7 + `openpyxl`), `pytest`, bash hooks, JSON Schema Draft-07, Claude Code plugin (commands/hooks/skills markdown).

---

## How To Use This Plan

- Every finding below was **verified against real file content + live validator output** on 2026-06-04. Line numbers are exact unless marked `~`.
- Batches **A–E are ENGINE** (code/docs). Batch **F is WORKSPACE** (data). **Do not mix engine and workspace changes in one commit.**
- After every batch run the batch's test gate. After the whole plan run the full gate (see "Final Verification").
- Four **decision points** need Süleyman's call. Each has a **recommended default** so the worker is never blocked — apply the default unless Süleyman overrides.

### Preconditions / Baseline (run once, before any edit)

- [ ] **P-1: Confirm repos + clean-ish state**

```bash
cd /Users/apple/Documents/platinum-seo-engine
git status --short          # expect only the known uncommitted audit-related files; do NOT revert them
git log --oneline -1        # expect e295237 (or later)
```

- [ ] **P-2: Capture the green baseline**

```bash
cd /Users/apple/Documents/platinum-seo-engine
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest --tb=short -q
```
Expected: `1449 passed, 8 skipped` (record the exact number; every batch must keep it ≥ this, plus the new tests).

- [ ] **P-3: Define Helper H-1 (you will reuse it everywhere to check a project's verdict)**

> `scripts/validation/validate_invariants.py` is an **importable module, NOT a CLI** (no `__main__`, no argparse). It exposes `evaluate_all(workbook, slug, workspace_root=...)` → list of rule dicts, and `aggregate_verdicts(results)` → summary whose key is **`overall`** (GREEN/AMBER/RED), NOT `verdict`. The live workbook is at the **project root** `projects/<slug>/master.xlsx` (NOT `outputs/`). This helper was tested working on 2026-06-04. Paste it into your shell:

```bash
checkverdict () {
  PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 - "$1" <<'PY'
import sys, openpyxl, importlib.util, pathlib
slug = sys.argv[1]
WS = pathlib.Path("/Users/apple/Documents/platinum-seo-workspace")
spec = importlib.util.spec_from_file_location("vi", "/Users/apple/Documents/platinum-seo-engine/scripts/validation/validate_invariants.py")
vi = importlib.util.module_from_spec(spec); spec.loader.exec_module(vi)
wb = openpyxl.load_workbook(WS/"projects"/slug/"master.xlsx", read_only=True, data_only=True)
results = vi.evaluate_all(wb, slug, workspace_root=WS)
agg = vi.aggregate_verdicts(results)
print(f"{slug}: {agg['overall']}  (pass={agg['pass_count']} warn={agg['warn_count']} fail={agg['fail_count']})")
for r in results:
    if r["verdict"] == "FAIL":
        print(f"   FAIL {r['id']} {r['severity']} — {r.get('evidence','')}")
PY
}
```

- [ ] **P-4: Snapshot the workspace RED state (so we can prove Batch F fixed it)**

```bash
for p in eykom lastiksa-tr noran-insaat-tr vento; do checkverdict "$p"; done
```
Expected (verified 2026-06-04): eykom RED (FAIL F-15/F-17/F-18), lastiksa RED (F-01/F-15), noran RED (F-05/F-15), vento RED (F-16/F-15). F-15 is manual-triage and is AMBER-by-design in aggregation; the RED is driven by the other failing rule(s).

### Decision Points (resolve before Batch A; defaults in **bold**)

| ID | Decision | Options | Recommended default |
|----|----------|---------|---------------------|
| **D-1** (finding 1) | Which project should be the active marker after cleanup? | (a) **repoint to a healthy/intended slug** (e.g. `iwallet-tr` or whatever Süleyman is working on); (b) keep `noran-insaat-tr` and only fix its data | **(a)** — but Süleyman names the slug. Until then, leave marker, fix noran data in Batch F anyway. |
| **D-2** (finding 2, adstark) | The 2 adstark run files have a workflow-type infix (`-full-ingest-`, `-sf-`) the `run_id` pattern rejects. | (a) **rename the 2 files + internal `run_id`** to canonical `{slug}-{YYYY-MM-DD}-{hash4}`; (b) relax the schema `run_id` pattern to allow an optional infix segment | **(a)** for adstark (cosmetic, 2 files). iwallet legacy file → migrate or `.legacy`-archive regardless. |
| **D-3** (finding 13) | Canonical "schema count" wording. | (a) **marketplace says "21 schemas"** to match README (21 = 20 `*.schema.json` + `cross-sheet-invariants.json`); (b) marketplace stays "20" and README changes to 20 | **(a)** — README already canonically uses 21 (lines 133, 243). |
| **D-4** (finding 14) | Excel-writer guard: spoofable by design. | (a) **keep as advisory, fix only the docstring to say "advisory, not a hard block"** + add an invariant re-check on the staged workbook as a *real* gate; (b) full hard-block (signed marker / backup-pair) — large effort; (c) accept as-is, document only | **(a)** — cheap real gate (re-run `validate_invariants` on staged master.xlsx) without the cost of (b). |

---

## BATCH A — Engine: contract / governance drift

Covers findings **9** (DFS version const), **4-schema** (language_code constraint), **13** (marketplace schema count). All three are "a contract says X, reality says Y, and no test binds them."

### Task A1: Lock DFS version const to runtime (finding 9)

**Files:**
- Modify: `schemas/dataforseo-endpoint-mapping.schema.json:5` (description prose) and `:13` (`const`)
- Modify (extend): `tests/schemas/test_mcp_registry_versions_match_mcp_json.py`

Current truth (verified): `.mcp.json:14` → `dataforseo-mcp-server@2.8.10`; `mcp-tool-registry.json:89` → `"version_lock": "2.8.10"`; schema `:13` → `"const": "2.8.9"` (stale third surface; existing test only binds `.mcp.json`↔registry).

- [ ] **Step 1: Add the failing assertion to the existing version test**

Append a new test function to `tests/schemas/test_mcp_registry_versions_match_mcp_json.py`:

```python
def test_dataforseo_endpoint_mapping_schema_const_matches_mcp_json():
    """The endpoint-mapping schema's mcp_server_version const must equal the
    version actually launched in .mcp.json (third surface; was lagging at 2.8.9)."""
    import json, re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    mcp = (root / ".mcp.json").read_text(encoding="utf-8")
    m = re.search(r"dataforseo-mcp-server@(\d+\.\d+\.\d+)", mcp)
    assert m, "could not find dataforseo-mcp-server@X.Y.Z in .mcp.json"
    runtime_version = m.group(1)

    schema = json.loads(
        (root / "schemas" / "dataforseo-endpoint-mapping.schema.json").read_text(encoding="utf-8")
    )
    const = schema["properties"]["mcp_server_version"]["const"]
    assert const == runtime_version, (
        f"schema const {const!r} != .mcp.json runtime {runtime_version!r}"
    )
```

- [ ] **Step 2: Run it; verify it FAILS**

```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m pytest tests/schemas/test_mcp_registry_versions_match_mcp_json.py -v
```
Expected: the new test FAILS with `'2.8.9' != '2.8.10'`.

- [ ] **Step 3: Bump the schema const + prose**

In `schemas/dataforseo-endpoint-mapping.schema.json`: change the `const` on line 13 from `"2.8.9"` to `"2.8.10"`, and update the `description` prose (line 5 and line 14) replacing both `2.8.9` mentions with `2.8.10` (keep the npm-verified date note; add `; bumped 2026-06-04 to match .mcp.json`).

- [ ] **Step 4: Run; verify PASS**

```bash
python3 -m pytest tests/schemas/test_mcp_registry_versions_match_mcp_json.py -v
```
Expected: all PASS (the pre-existing registry↔.mcp.json test still passes too).

- [ ] **Step 5: Commit**

```bash
git add schemas/dataforseo-endpoint-mapping.schema.json tests/schemas/test_mcp_registry_versions_match_mcp_json.py
git commit -m "fix(schema): lock dataforseo endpoint-mapping const to 2.8.10 + bind by test [codex-audit f9]"
```

### Task A2: Constrain `language_code` so locale junk is rejected (finding 4, engine half)

**Files:**
- Modify: `schemas/project-config.schema.json:86`
- Create/extend test: `tests/schemas/test_project_config_language_code.py`

Current truth (verified): line 86 is `"language_code": { "type": "string" }` (inside the `dataforseo` object opening at line 80). Workspace has `"1001"` and `"1031"` passing.

- [ ] **Step 1: Write the failing test**

```python
# tests/schemas/test_project_config_language_code.py
import json
from pathlib import Path
import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "project-config.schema.json").read_text("utf-8"))


def _validate(language_code):
    """Validate just the dataforseo.language_code field via the real schema."""
    instance = {
        "schema_version": "1.5",
        "project_id": "x-test",
        "domain": "example.com",
        "market": "TR",
        "language": {"primary": "tr-TR"},
        "dataforseo": {"location_code": 2792, "language_code": language_code},
    }
    # validate against the dataforseo sub-schema to isolate the field
    sub = SCHEMA["properties"]["dataforseo"]
    jsonschema.Draft7Validator(sub).validate(instance["dataforseo"])


@pytest.mark.parametrize("good", ["tr", "en", "en-us", "pt-br"])
def test_language_code_accepts_iso(good):
    _validate(good)


@pytest.mark.parametrize("bad", ["1001", "1031", "TR", "turkish", "2792", ""])
def test_language_code_rejects_non_iso(bad):
    with pytest.raises(jsonschema.ValidationError):
        _validate(bad)
```

- [ ] **Step 2: Run; verify the `rejects_non_iso` cases FAIL**

```bash
python3 -m pytest tests/schemas/test_project_config_language_code.py -v
```
Expected: `test_language_code_rejects_non_iso[1001]` etc. FAIL (schema currently accepts them).

- [ ] **Step 3: Add the pattern to the schema**

In `schemas/project-config.schema.json:86` change:
```json
"language_code": { "type": "string" },
```
to:
```json
"language_code": { "type": "string", "pattern": "^[a-z]{2}(-[a-z]{2,})?$", "description": "ISO-like DataForSEO language code, e.g. 'tr', 'en', 'en-us' (NOT a numeric locale id)" },
```

- [ ] **Step 4: Run; verify PASS**

```bash
python3 -m pytest tests/schemas/test_project_config_language_code.py -v
```
Expected: all PASS. Then confirm no OTHER engine test regressed:
```bash
python3 -m pytest tests/schemas -q
```

- [ ] **Step 5: Commit (engine only — workspace data fix is Batch F4)**

```bash
git add schemas/project-config.schema.json tests/schemas/test_project_config_language_code.py
git commit -m "fix(schema): constrain dataforseo.language_code to ISO pattern + tests [codex-audit f4]"
```

### Task A3: Bind marketplace schema count to the filesystem (finding 13)

**Files:**
- Modify: `.claude-plugin/marketplace.json:16` (per D-3 default → "21 schemas")
- Extend test: `tests/docs/test_count_consistency.py`

Current truth (verified): marketplace says `20 schemas`; README says 21 (20 `*.schema.json` + `cross-sheet-invariants.json`); `tests/docs/test_count_consistency.py` checks skills/commands/MCP but NOT schemas.

- [ ] **Step 1: Write the failing test (locks marketplace's schema number to filesystem `.json` count)**

Add to `tests/docs/test_count_consistency.py`:

```python
def test_marketplace_schema_count_matches_filesystem():
    """Marketplace 'N schemas' blurb must equal the number of JSON schema files
    in schemas/ (all *.json, which includes cross-sheet-invariants.json)."""
    import json, re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    schema_files = sorted((root / "schemas").glob("*.json"))
    expected = len(schema_files)  # currently 21

    blurb = json.loads((root / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
    text = json.dumps(blurb)
    m = re.search(r"(\d+)\s+schemas", text)
    assert m, "no 'N schemas' phrase in marketplace.json"
    assert int(m.group(1)) == expected, (
        f"marketplace says {m.group(1)} schemas, filesystem has {expected} "
        f"({', '.join(p.name for p in schema_files)})"
    )
```

- [ ] **Step 2: Run; verify FAIL** (`20 != 21`)

```bash
python3 -m pytest tests/docs/test_count_consistency.py::test_marketplace_schema_count_matches_filesystem -v
```

- [ ] **Step 3: Fix marketplace.json (D-3 default)**

In `.claude-plugin/marketplace.json:16`, change `20 schemas` → `21 schemas`. (If Süleyman picks D-3 option (b) instead, change README to "20" and set the test's `expected` to count `*.schema.json` — but default is 21.)

- [ ] **Step 4: Run; verify PASS + no regression**

```bash
python3 -m pytest tests/docs/test_count_consistency.py -q
```

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/marketplace.json tests/docs/test_count_consistency.py
git commit -m "fix(docs): reconcile marketplace schema count to 21 + bind by test [codex-audit f13]"
```

### Batch A gate

```bash
python3 -m pytest tests/schemas tests/docs -q
```

---

## BATCH B — Engine: command safety & doc↔impl parity

Covers findings **5a–5d** (/pseo-active unsafe) and **10a–10c** (/pseo-init, /pseo-quickwin, /pseo-cannibalization drift).

### Task B1: `/pseo-active` — abort on missing config + letter-start slug regex (findings 5a, 5b)

**Files:**
- Modify: `commands/pseo-active.md:25` (missing-config branch) and `:30` (regex)
- Create test: `tests/commands/test_pseo_active_safety.py`

Current truth (verified): line 25 warns then continues (`echo "WARN: ... yine de marker'ı yazacağım"` with no `exit`); line 30 is `re.fullmatch(r'[a-z0-9][a-z0-9-]*', slug)`. Schema (`project-config.schema.json:16`) requires `^[a-z][a-z0-9-]*$`. **Note:** `$SLUG` is passed to Python via env var (`SLUG="$SLUG" python3 -c ...; slug = os.environ['SLUG']`) — this is already injection-safe; do NOT "fix" an injection that isn't there.

- [ ] **Step 1: Write the failing test (static assertions on the command file)**

```python
# tests/commands/test_pseo_active_safety.py
from pathlib import Path

CMD = (Path(__file__).resolve().parents[2] / "commands" / "pseo-active.md").read_text("utf-8")


def test_slug_regex_requires_letter_start():
    # command regex must match the schema's ^[a-z][a-z0-9-]*$ (no leading digit)
    assert "[a-z0-9][a-z0-9-]*" not in CMD, "command still allows leading-digit slug"
    assert "[a-z][a-z0-9-]*" in CMD, "command must use letter-start slug regex"


def test_missing_config_aborts():
    # the missing-config branch must exit, not warn-and-continue
    assert "yine de marker" not in CMD, "missing-config still writes marker anyway"
    # a guard that exits when config absent (allow an explicit --force escape hatch)
    assert "exit 1" in CMD, "missing-config branch must abort with exit 1"
```

- [ ] **Step 2: Run; verify FAIL**

```bash
python3 -m pytest tests/commands/test_pseo_active_safety.py -v
```

- [ ] **Step 3: Fix the command**

In `commands/pseo-active.md`:
- Line 30 regex: change `r'[a-z0-9][a-z0-9-]*'` → `r'[a-z][a-z0-9-]*'`.
- Line 25 missing-config branch: replace the warn-and-continue with an abort. Change the body so that when `[ ! -f "$CFG" ]` it prints a clear error and `exit 1` UNLESS `--force` is in `$ARGUMENTS`. Concretely, replace:
  ```bash
  CFG="$WS/projects/$SLUG/project.config.json"; if [ ! -f "$CFG" ]; then echo "WARN: $CFG yok — yine de marker'ı yazacağım (Phase 5'te /pseo-init önerilir)"; fi; mkdir -p "$WS/shared"; ...
  ```
  with:
  ```bash
  CFG="$WS/projects/$SLUG/project.config.json"; if [ ! -f "$CFG" ]; then case "$ARGUMENTS" in *--force*) echo "WARN: $CFG yok ama --force verildi, marker yazılıyor";; *) echo "HATA: $CFG yok. Önce /pseo-init $SLUG çalıştır (veya --force)"; exit 1;; esac; fi; mkdir -p "$WS/shared"; ...
  ```
  Also update the line-24 prose to say it now aborts unless `--force`.

- [ ] **Step 4: Run; verify PASS**

```bash
python3 -m pytest tests/commands/test_pseo_active_safety.py -v
```

- [ ] **Step 5: Commit**

```bash
git add commands/pseo-active.md tests/commands/test_pseo_active_safety.py
git commit -m "fix(cmd): pseo-active aborts on missing config + letter-start slug regex [codex-audit f5ab]"
```

### Task B2: `events_writer._events_path` — validate project id before mkdir (finding 5d)

**Files:**
- Modify: `scripts/state/events_writer.py:227-234` (`_events_path`)
- Create test: `tests/scripts/test_events_writer_path_guard.py`

Current truth (verified): `_events_path` only guards "non-empty string", then `state_dir.mkdir(parents=True, exist_ok=True)` for any id → ghost dirs + path-traversal surface (`..`, `/`).

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_events_writer_path_guard.py
import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location(
    "events_writer",
    Path(__file__).resolve().parents[2] / "scripts" / "state" / "events_writer.py",
)
ew = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ew)


@pytest.mark.parametrize("bad", ["../evil", "a/b", "9foo", "Foo", "x_y", ""])
def test_events_path_rejects_invalid_project_id(tmp_path, bad):
    with pytest.raises(ew.EventPathError):
        ew._events_path(bad, tmp_path)
    # and it must NOT have created any directory for the bad id
    assert not (tmp_path / "projects" / bad).exists()


def test_events_path_accepts_valid_slug(tmp_path):
    p = ew._events_path("noran-insaat-tr", tmp_path)
    assert p.name == "events.jsonl"
    assert (tmp_path / "projects" / "noran-insaat-tr" / "_state").is_dir()
```

- [ ] **Step 2: Run; verify FAIL** (bad ids currently succeed / create dirs)

```bash
python3 -m pytest tests/scripts/test_events_writer_path_guard.py -v
```

- [ ] **Step 3: Add slug validation in `_events_path` (before `mkdir`)**

In `scripts/state/events_writer.py`, near the top add (if not present) the canonical slug regex, and enforce it in `_events_path`:

```python
import re
_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")  # mirrors project-config.schema.json project_id pattern
```
Then inside `_events_path`, replace the existing non-empty guard with:
```python
    if not isinstance(project_id, str) or not _SLUG_RE.fullmatch(project_id):
        raise EventPathError(
            f"project_id must match {_SLUG_RE.pattern!r} (got {project_id!r})"
        )
```
(Keep the rest unchanged: resolve workspace root, build `state_dir`, `mkdir`, return path.)

- [ ] **Step 4: Run; verify PASS + no regression in state tests**

```bash
python3 -m pytest tests/scripts/test_events_writer_path_guard.py -q
python3 -m pytest tests/scripts -q
```

- [ ] **Step 5: Commit**

```bash
git add scripts/state/events_writer.py tests/scripts/test_events_writer_path_guard.py
git commit -m "fix(state): events_writer validates project_id slug before mkdir (no ghost dirs / traversal) [codex-audit f5d]"
```

### Task B3: Command doc↔impl parity for `/pseo-init`, `/pseo-quickwin`, `/pseo-cannibalization` (findings 10a, 10b, 10c)

**Files:**
- Modify: `commands/pseo-init.md:27`, `commands/pseo-quickwin.md:39-40`, `commands/pseo-cannibalization.md:17` (+ doc lines)
- Create test: `tests/commands/test_command_doc_impl_parity.py`

Current truth (verified): pseo-init line 27 invocation passes only `--project "$1" $DOMAIN_FLAG --dry-run` (drops `$ARGUMENTS` flags advertised line 23). pseo-quickwin lines 39-40 reference `gsc_landing_query` (no such sheet; real name `gsc_performance`). pseo-cannibalization line 6 advertises `--days-back/--min-impressions` but line 17 reads positional `${2:-28}`/`${3:-10}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/commands/test_command_doc_impl_parity.py
from pathlib import Path

CMD = Path(__file__).resolve().parents[2] / "commands"


def test_pseo_init_dryrun_passes_arguments():
    t = (CMD / "pseo-init.md").read_text("utf-8")
    # the bootstrap dry-run invocation must forward $ARGUMENTS (not just --project/$DOMAIN_FLAG)
    assert "bootstrap_project.py" in t
    assert "$ARGUMENTS" in t.split("--dry-run")[0].rsplit("bootstrap_project.py", 1)[-1] \
        or "$ARGUMENTS" in t, "pseo-init dry-run must forward $ARGUMENTS flags"


def test_pseo_quickwin_uses_real_sheet_name():
    t = (CMD / "pseo-quickwin.md").read_text("utf-8")
    assert "gsc_landing_query" not in t, "pseo-quickwin references non-existent sheet gsc_landing_query"
    assert "gsc_performance" in t


def test_pseo_cannibalization_flag_doc_matches_parsing():
    t = (CMD / "pseo-cannibalization.md").read_text("utf-8")
    advertises_flags = "--days-back" in t and "--min-impressions" in t
    reads_positional = "${2:-" in t or "${3:-" in t
    # either parse the flags, or stop advertising them — but not both
    assert not (advertises_flags and reads_positional), (
        "pseo-cannibalization advertises flags but reads positional $2/$3"
    )
```

- [ ] **Step 2: Run; verify FAIL (all three)**

```bash
python3 -m pytest tests/commands/test_command_doc_impl_parity.py -v
```

- [ ] **Step 3a: Fix `pseo-init.md`** — on line 27, append `$ARGUMENTS` to the invocation so user flags reach the dry-run, de-duplicating the ones already set. Change:
```bash
... bootstrap_project.py" --project "$1" $DOMAIN_FLAG --dry-run 2>&1 | head -60
```
to:
```bash
... bootstrap_project.py" --project "$1" $DOMAIN_FLAG --dry-run $ARGUMENTS 2>&1 | head -60
```
(If `bootstrap_project.py` rejects duplicate `--project`/`--domain`/`--dry-run`, instead build a filtered `$EXTRA_FLAGS` from `$ARGUMENTS` excluding slug/domain/dry-run and pass `$EXTRA_FLAGS`. Confirm argparse behavior with `python3 scripts/state/bootstrap_project.py --help`.)

- [ ] **Step 3b: Fix `pseo-quickwin.md`** — replace `gsc_landing_query` on lines 39 and 40 with `gsc_performance`.

- [ ] **Step 3c: Fix `pseo-cannibalization.md`** — make the body parse the advertised flags. Replace the positional read on line 17 (`days_back=${2:-28} min_impressions=${3:-10}`) with a small `$ARGUMENTS` parse:
```bash
DAYS_BACK=$(printf '%s\n' "$ARGUMENTS" | sed -n 's/.*--days-back[ =]\([0-9]\+\).*/\1/p'); DAYS_BACK=${DAYS_BACK:-28}
MIN_IMPR=$(printf '%s\n' "$ARGUMENTS" | sed -n 's/.*--min-impressions[ =]\([0-9]\+\).*/\1/p'); MIN_IMPR=${MIN_IMPR:-10}
echo "active=$PROJECT days_back=$DAYS_BACK min_impressions=$MIN_IMPR"
```
(Keep the `argument-hint` flags as-is — now they actually work.)

- [ ] **Step 4: Run; verify PASS**

```bash
python3 -m pytest tests/commands/test_command_doc_impl_parity.py -v
```

- [ ] **Step 5: Commit**

```bash
git add commands/pseo-init.md commands/pseo-quickwin.md commands/pseo-cannibalization.md tests/commands/test_command_doc_impl_parity.py
git commit -m "fix(cmd): doc-impl parity for init/quickwin/cannibalization + tests [codex-audit f10]"
```

### Task B4 (optional, high-value): generic command-reference linter

A single test that prevents whole classes of finding-10 drift. Scans every `commands/*.md` for `schemas/*.json` references and master-workbook sheet names, failing on any that don't exist.

**Files:** Create `tests/commands/test_command_references_exist.py`

- [ ] **Step 1: Write the test**

```python
# tests/commands/test_command_references_exist.py
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CMDS = sorted((ROOT / "commands").glob("*.md"))
SHEETS = set(
    json.loads((ROOT / "schemas" / "master-excel.schema.json").read_text("utf-8"))
    ["properties"]["sheets"]["properties"].keys()
)


def test_command_schema_paths_exist():
    bad = []
    for c in CMDS:
        for ref in re.findall(r"schemas/[\w./-]+\.schema\.json", c.read_text("utf-8")):
            if not (ROOT / ref).exists():
                bad.append(f"{c.name}: {ref}")
    assert not bad, "command references missing schema files:\n" + "\n".join(bad)


def test_command_sheet_names_exist():
    # only flag tokens that look like a sheet ref but aren't real sheet names
    suspects = {"gsc_landing_query"}  # known-bad; extend if more surface
    bad = []
    for c in CMDS:
        text = c.read_text("utf-8")
        for s in suspects:
            if s in text:
                bad.append(f"{c.name}: {s} (not in master-excel sheets: {sorted(SHEETS)})")
    assert not bad, "command references non-existent sheet:\n" + "\n".join(bad)
```

- [ ] **Step 2: Run** — `gsc_landing_query` test passes only after B3b; schema-path test catches finding 14's cousin (P1-14 in the broader audit: `gsc-mapping.schema.json`, `dataforseo-mapping.schema.json` wrong paths). If it flags additional stale paths (likely in `pseo-cannibalization.md` / `pseo-schema-audit.md`), fix those references too (see Appendix → P1-14).

```bash
python3 -m pytest tests/commands/test_command_references_exist.py -v
```

- [ ] **Step 3: Fix any flagged stale schema paths**, then re-run to green.

- [ ] **Step 4: Commit**

```bash
git add tests/commands/test_command_references_exist.py commands/
git commit -m "test(cmd): lint command schema-path + sheet-name references [codex-audit f10/p1-14]"
```

### Batch B gate

```bash
python3 -m pytest tests/commands tests/scripts -q
```

---

## BATCH C — Engine: hook hardening

Covers findings **7** (secret scan misses untracked), **8** (append-only doc over-claims), **14** (excel-writer guard).

### Task C1: Incremental secret scan must include untracked files (finding 7)

**Files:**
- Modify: `scripts/security/check_secrets.sh:111` (the incremental file-list command)
- Create test: `tests/hooks/test_secret_scan_untracked.py` (or `.sh` runner if the suite uses bash tests — match existing convention; check `tests/hooks/`)

Current truth (verified): line 111 is `CHANGED_FILES_LIST=$(cd "$ROOT" && git diff --name-only "$INCREMENTAL_REF" 2>/dev/null || true)` — `git diff --name-only` omits untracked files; CI scan is also HEAD-only.

- [ ] **Step 1: Write the failing test**

```python
# tests/hooks/test_secret_scan_untracked.py
import subprocess, textwrap, os
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2]
SCRIPT = ENGINE / "scripts" / "security" / "check_secrets.sh"


def test_incremental_scan_detects_untracked_secret(tmp_path):
    # init a throwaway git repo with one committed clean file + one untracked secret file
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "ok.txt").write_text("hello\n")
    subprocess.run(["git", "add", "ok.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    # brand-new UNTRACKED file with a fake secret. Split the AKIA literal so this
    # source file is not itself flagged by check_secrets.sh (the temp file gets the
    # full token at runtime). The shipped test does exactly this via a _SECRET const.
    _secret = "AKIA" + "IOSFODNN7EXAMPLE"
    (tmp_path / "leak.txt").write_text(_secret + "\n")

    res = subprocess.run(
        ["bash", str(SCRIPT), "--changed-since", "HEAD", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    # must FAIL the gate (non-zero) because the untracked file holds a secret
    assert res.returncode != 0, f"untracked secret slipped through:\n{res.stdout}\n{res.stderr}"
```
(If the existing secret-detection regexes differ, use a token the repo's own patterns already match — check `scripts/security/check_secrets.sh` for the patterns and mirror one.)

- [ ] **Step 2: Run; verify FAIL** (untracked secret currently slips through → returncode 0)

```bash
python3 -m pytest tests/hooks/test_secret_scan_untracked.py -v
```

- [ ] **Step 3: Union untracked files into the incremental list**

In `scripts/security/check_secrets.sh:111`, change:
```bash
CHANGED_FILES_LIST=$(cd "$ROOT" && git diff --name-only "$INCREMENTAL_REF" 2>/dev/null || true)
```
to:
```bash
CHANGED_FILES_LIST=$(cd "$ROOT" && { git diff --name-only "$INCREMENTAL_REF" 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort -u || true)
```
(`--exclude-standard` keeps `.gitignore`'d files like local `.env` on their existing WARN path, not a hard FAIL.)

- [ ] **Step 4: Run; verify PASS + run the real incremental scan on the engine**

```bash
python3 -m pytest tests/hooks/test_secret_scan_untracked.py -v
bash scripts/security/check_secrets.sh --changed-since HEAD .   # expect: SECURITY GATE GREEN (no real secrets)
```

- [ ] **Step 5: Commit**

```bash
git add scripts/security/check_secrets.sh tests/hooks/test_secret_scan_untracked.py
git commit -m "fix(security): incremental secret scan now covers untracked files + test [codex-audit f7]"
```

### Task C2: Fix append-only doc comment to match `.jsonl`-only impl (finding 8)

**Files:**
- Modify: `scripts/hooks/check_append_only.sh:5-8` (doc comment only)
- Optional test: extend an existing hooks doc test, or skip (doc-only, low risk)

Current truth (verified): header comment names `workflows/{run_id}.json` as append-only, but impl (line 62) scans only `\.jsonl$`. The impl is CORRECT (workflow JSONs are legitimately mutated by the state machine); the doc over-claims.

- [ ] **Step 1: Reword the comment** — change lines 5-8 so the scope sentence says the hook enforces append-only on `events.jsonl` (`.jsonl`) only, and explicitly notes workflow `{run_id}.json` files are intentionally out of scope because the workflow state machine mutates them in place. Example:

```bash
# Per rules/append-only-state.md, events.jsonl event logs MUST NOT be rewritten
# or have lines mutated/deleted; only new lines may be appended. This hook scans
# staged .jsonl diffs and rejects line deletions / in-place edits.
# NOTE: workflows/{run_id}.json are deliberately NOT covered here — they are
# state-machine-mutated by scripts/state/workflow_runner.py (status/timing fields
# change in place), so append-only does not apply to them.
```

- [ ] **Step 2: Sanity check the script still parses**

```bash
bash -n scripts/hooks/check_append_only.sh && echo "syntax ok"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/hooks/check_append_only.sh
git commit -m "docs(hook): scope append-only comment to .jsonl; note workflow JSON is state-mutated [codex-audit f8]"
```

### Task C3: Excel-writer guard — add a real gate, mark commit-msg signal advisory (finding 14, D-4 default)

**Files:**
- Modify: `scripts/hooks/check_excel_writer.py:11-14` (docstring) and `main()` (~line 104)
- Extend test: the existing `check_excel_writer` test file under `tests/hooks/`

Current truth (verified): `_writer_signal_present()` accepts the literal substring `transaction.py` in the commit message → spoofable; no provenance/invariant check. By-design, unit-tested.

- [ ] **Step 1: Write the failing test** (a staged workbook that FAILS invariants must be rejected even WITH the commit-msg signal)

```python
# add to tests/hooks/test_check_excel_writer.py (match existing fixtures/style)
def test_invalid_workbook_rejected_even_with_commit_signal(tmp_path, monkeypatch):
    # Build a master.xlsx that violates a CRITICAL invariant, stage it,
    # put "transaction.py" in the commit message, and assert the guard STILL fails.
    # (Use the same harness the existing tests use to invoke check_excel_writer.main.)
    ...
```
(Flesh out using the existing test's helpers — they already construct workbooks + commit-msg fixtures. The assertion: `main(...) != 0` when the staged workbook is invariant-RED.)

- [ ] **Step 2: Run; verify FAIL** (today the commit-msg signal short-circuits to `return 0`).

- [ ] **Step 3: Add the real gate** — in `main()`, after `_writer_signal_present()` passes, additionally re-check invariants on the staged `master.xlsx` and FAIL if RED. `validate_invariants.py` is an importable module (no CLI), so import `evaluate_all`/`aggregate_verdicts` and read the `overall` key:

```python
import importlib.util, os, pathlib

def _staged_workbook_is_valid(xlsx_path: str, project_slug: str) -> bool:
    """Authoritative gate: the staged workbook itself must not be invariant-RED.
    The commit-message 'transaction.py' string is only an advisory hint."""
    import openpyxl
    root = pathlib.Path(__file__).resolve().parents[2]            # engine repo root
    spec = importlib.util.spec_from_file_location(
        "vi", root / "scripts" / "validation" / "validate_invariants.py")
    vi = importlib.util.module_from_spec(spec); spec.loader.exec_module(vi)
    ws = pathlib.Path(os.environ.get("PSEO_WORKSPACE_ROOT", "."))
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    agg = vi.aggregate_verdicts(vi.evaluate_all(wb, project_slug, workspace_root=ws))
    return agg["overall"] != "RED"
```
Call it for each changed `.xlsx` before `return 0` (derive `project_slug` from the changed path: `projects/<slug>/master.xlsx` → the `<slug>` segment). Update the docstring (lines 11-14) to state the commit-message string is an **advisory** writer hint and the **authoritative** gate is the invariant re-check.

> If wiring the validator into the hook proves too heavy this pass, fall back to D-4 option (c): keep current behavior but change ONLY the docstring to say "advisory, not a hard block" and add a test asserting the docstring no longer implies enforcement. Record which path was taken. Note: a RED workbook reaching commit is exactly today's Batch-F state, so until Batch F lands this gate would block commits of the 4 RED projects — sequence Batch F before enabling the hard gate, or scope the gate to the project being committed.

- [ ] **Step 4: Run; verify PASS + no regression**

```bash
python3 -m pytest tests/hooks/test_check_excel_writer.py -q
```

- [ ] **Step 5: Commit**

```bash
git add scripts/hooks/check_excel_writer.py tests/hooks/test_check_excel_writer.py
git commit -m "fix(hook): excel-writer guard re-checks invariants; commit-msg signal is advisory [codex-audit f14]"
```

### Batch C gate

```bash
python3 -m pytest tests/hooks -q
```

---

## BATCH D — Engine: skill-doc & README cleanup

Covers findings **6** (racy `next_run_id()` in skill docs) and **12** (README `config.yaml`).

### Task D1: Purge the racy `next_run_id()` pattern from skill docs (finding 6)

**Files:**
- Modify: 26 occurrences across 22 `skills/**/SKILL.md` files (list below)
- Create test: `tests/skills/test_no_racy_next_run_id.py`

Current truth (verified): runtime (`events_writer.py:563-567, 691-694`) documents `next_run_id()`-then-`append_provenance()` as racy; `sf_import.py:251` already uses the corrected auto-allocate (`run_id` omitted / `None`). 26 skill examples still show `run_id=events_writer.next_run_id(project_slug),`.

**The 22 files** (occurrence counts): `aio-competitor-map`(2), `cannibalization`(1), `competitive-analysis`(2), `content-decay`(1), `content-gaps`(1), `gbp-audit`(2), `geo-analysis`(1), `on-page-audit`(1), `quick-wins`(1), `schema-audit`(1), `tech-audit`(2), `dfs-pull`(1), `gsc-pull`(1), `scrapling-ops`(1), `sf-crawl-orchestrator`(1 @ line 523 — the usage, NOT the line-662 import-inventory mention), `sf-import`(1), `init-project`(1), `cluster-map`(1), `internal-links`(1), `master-task-sync`(1), `new-content-plan`(1), `topical-map`(1).

- [ ] **Step 1: Write the failing guard test**

```python
# tests/skills/test_no_racy_next_run_id.py
import re
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"


def test_no_racy_next_run_id_usage():
    """No SKILL.md may show run_id=...next_run_id(...) inside an append call — it
    is racy (read outside the append flock). Use auto-allocation (run_id=None)."""
    offenders = []
    for f in SKILLS.rglob("SKILL.md"):
        for i, line in enumerate(f.read_text("utf-8").splitlines(), 1):
            # the racy *usage* assigns next_run_id() to a run_id argument/var
            if re.search(r"run_id\s*=\s*events_writer\.next_run_id\(", line) or \
               re.search(r"\brid\s*=\s*events_writer\.next_run_id\(", line):
                offenders.append(f"{f.relative_to(SKILLS)}:{i}: {line.strip()}")
    assert not offenders, "racy next_run_id() usage remains:\n" + "\n".join(offenders)
```

- [ ] **Step 2: Run; verify FAIL** (expect 26 offenders)

```bash
python3 -m pytest tests/skills/test_no_racy_next_run_id.py -v
```

- [ ] **Step 3: Fix each occurrence** — in every flagged `append_provenance(...)` example, DELETE the `run_id=events_writer.next_run_id(project_slug),` argument line so the id auto-allocates race-free inside the append flock, exactly as `scripts/ingestion/sf_import.py:250-263` does. (Mirror sf_import's inline comment where helpful.) Do NOT touch `sf-crawl-orchestrator/SKILL.md:662` — that is a benign import-inventory listing, not a usage. Drive the loop by re-running the test until zero offenders:

```bash
python3 -m pytest tests/skills/test_no_racy_next_run_id.py -q   # repeat after each file
```

- [ ] **Step 4: Verify green + no other skill test regressed**

```bash
python3 -m pytest tests/skills -q
```

- [ ] **Step 5: Commit**

```bash
git add skills/ tests/skills/test_no_racy_next_run_id.py
git commit -m "docs(skills): remove racy next_run_id() pattern from 22 SKILL.md, auto-allocate + guard test [codex-audit f6]"
```

### Task D2: README architecture diagram — `config.yaml` → `project.config.json` (finding 12)

**Files:**
- Modify: `README.md:131`
- Create test: `tests/docs/test_readme_no_fictional_config.py`

Current truth (verified): `README.md:131` shows `├ config.yaml`; no `config.yaml` exists in either repo; real per-project contract is `project.config.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/docs/test_readme_no_fictional_config.py
from pathlib import Path

README = (Path(__file__).resolve().parents[2] / "README.md").read_text("utf-8")


def test_readme_does_not_reference_config_yaml():
    assert "config.yaml" not in README, "README references fictional config.yaml; real file is project.config.json"
    assert "project.config.json" in README
```

- [ ] **Step 2: Run; verify FAIL**

```bash
python3 -m pytest tests/docs/test_readme_no_fictional_config.py -v
```

- [ ] **Step 3: Fix** — in `README.md:131` change `├ config.yaml` → `├ project.config.json` (preserve the box-drawing alignment of the surrounding diagram).

- [ ] **Step 4: Run; verify PASS**

```bash
python3 -m pytest tests/docs/test_readme_no_fictional_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add README.md tests/docs/test_readme_no_fictional_config.py
git commit -m "docs(readme): architecture diagram uses real project.config.json + test [codex-audit f12]"
```

### Batch D gate

```bash
python3 -m pytest tests/skills tests/docs -q
```

---

## BATCH E — Engine: `dump_workspace.py` live-data blind spot (BONUS, lower priority)

Found while verifying finding 3. **First, what is ALREADY FIXED (do not redo):** the broader audit's **P0-02** ("dump reads `slug` not `active_project`") is resolved in the current local tree — `scripts/state/dump_workspace.py:61` reads `data.get("active_project") or data.get("slug")` (canonical first, legacy fallback + deprecation warning at :66-69), and all 17 tests in `tests/scripts/test_dump_workspace.py` pass, including `test_dump_reads_active_project_canonical`. **Leave P0-02 alone.**

**The remaining (real) blind spot:** `dump_workspace.py:192` reads `project_dir/"outputs"/"master.xlsx"` and `:196` reads `_state/consistency-report.json` — but every live project keeps its workbook at the **project root** (`projects/<slug>/master.xlsx`) and **no runtime ever persists `consistency-report.json`**. Result: `dump_workspace --json` returns `master_task_todo_count: null` and `drift_verdict: null` for every real project (events_tail/backups still work). A manager session using this tool to triage state sees nulls where the verdict should be.

> **This is a convention-reconciliation task, not a blind path swap, and it is lower priority than A–D.** The existing test fixtures (`_write_master_xlsx` → `outputs/master.xlsx`; `_write_consistency_report` → `_state/consistency-report.json`) encode the `outputs/` convention, citing ADR-021/ADR-035 — so the test passes against code that doesn't match live data. **Decide intent first** from `rules/append-only-state.md` + ADR-021/ADR-035 + how `validate_invariants` resolves the workbook (`_project_dir(slug)` = `projects/<slug>/`, caller appends the filename — confirm whether engine convention is root or `outputs/`). Then fix whichever side is authoritative and update the test + a one-line rationale. If intent is genuinely ambiguous, surface it to Süleyman rather than guessing.

### Task E1: Make dump_workspace report real verdicts on live data

**Files:**
- Modify: `scripts/state/dump_workspace.py` (workbook path `:192`, drift verdict source `:196`)
- Extend: `tests/scripts/test_dump_workspace.py`

- [ ] **Step 1: Reproduce** — confirm live nulls:

```bash
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 scripts/state/dump_workspace.py --json 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('todo=',d['master_task_todo_count'],'drift=',d['drift_verdict'])"
```
Expected today: `todo= None drift= None` (workbook at root, no report persisted).

- [ ] **Step 2: Write the failing test** (uses the file's existing helpers; mirrors their style). If the decision is "root is authoritative," the workbook helper must write to the project root, not `outputs/`:

```python
# add to tests/scripts/test_dump_workspace.py
def _write_master_xlsx_at_root(project, statuses):
    """Same as _write_master_xlsx but at projects/<slug>/master.xlsx (live convention)."""
    from openpyxl import Workbook
    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("master_task")
    ws.cell(row=1, column=1, value="task_id")
    ws.cell(row=1, column=10, value="status")
    for i, status in enumerate(statuses, start=2):
        ws.cell(row=i, column=1, value=f"task-{i}")
        ws.cell(row=i, column=10, value=status)
    wb.save(project / "master.xlsx")          # ROOT, not outputs/


def test_dump_reads_root_workbook_todo_count(dump_module, tmp_path):
    project = _make_workspace(tmp_path, slug="demo")
    _write_master_xlsx_at_root(project, ["TODO", "TODO", "DONE"])
    result = dump_module.dump_workspace(workspace_root=tmp_path, project_slug="demo")
    assert result["master_task_todo_count"] == 2, "dump must count TODOs from the root workbook"
```

- [ ] **Step 3: Run; verify FAIL** (current code reads `outputs/`, so count is None):

```bash
python3 -m pytest tests/scripts/test_dump_workspace.py::test_dump_reads_root_workbook_todo_count -v
```

- [ ] **Step 4: Fix `dump_workspace.py`** — change `:192` to resolve `project_dir/"master.xlsx"` (root), keeping a graceful fallback to `outputs/master.xlsx` if you want backward-compat. For `drift_verdict` (`:196`), compute it live via `validate_invariants.evaluate_all`+`aggregate_verdicts` (returning the `overall` key) instead of a never-written `consistency-report.json` — OR, if ADRs say the report SHOULD be persisted, that's a separate larger task: note it and keep the live computation as the dump's source. Keep all changes graceful (missing workbook → None, never raise).

- [ ] **Step 5: Run; verify PASS + live shows real numbers:**

```bash
python3 -m pytest tests/scripts/test_dump_workspace.py -q
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 scripts/state/dump_workspace.py --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('todo=',d['master_task_todo_count'],'drift=',d['drift_verdict'])"
# expect non-null todo + a GREEN/AMBER/RED drift verdict
```

- [ ] **Step 6: Commit**

```bash
git add scripts/state/dump_workspace.py tests/scripts/test_dump_workspace.py
git commit -m "fix(state): dump_workspace reads root workbook + live drift verdict (no more nulls) [codex-audit bonus]"
```

### Batch E gate

```bash
python3 -m pytest tests/scripts -q
```

---

## BATCH F — Workspace: data normalization (SEPARATE repo, separate commits)

Covers findings **1**, **2**, **3**, **4-data**, **11**. These are **workspace data edits** — commit them in the workspace repo (`/Users/apple/Documents/platinum-seo-workspace`), never mixed with engine commits. After each edit, re-run the engine validator against the workspace to prove the fix.

> **Append-only / owner-lock caution:** the workspace has append-only `.jsonl` and Excel owner-lock hooks. Edit `master.xlsx` files only via the sanctioned writer (`scripts/excel/transaction.py`) or with the `--allow-direct-edit` escape hatch for recovery; do NOT hand-edit `.jsonl` event logs. Back up each workbook before editing (`cp master.xlsx master.xlsx.bak.<date>`).

### Task F1: Repoint the active marker (finding 1, decision D-1)

- [ ] **Step 1:** Resolve D-1 with Süleyman (which slug is "live"). Default: a healthy slug he names.
- [ ] **Step 2:** Update `/Users/apple/Documents/platinum-seo-workspace/shared/active.json` `active_project` to the chosen slug + bump `updated_at`. (A backup `.bak` is auto-written by the existing tooling pattern.)
- [ ] **Step 3:** Verify: `PSEO_WORKSPACE_ROOT=... python3 .../engine/scripts/state/dump_workspace.py --json` resolves the new active project cleanly.
- [ ] **Step 4:** Commit in workspace repo: `git -C /Users/apple/Documents/platinum-seo-workspace commit -am "chore(state): repoint active marker to <slug> [codex-audit f1]"` (ask before committing per safety rules).

### Task F2: Normalize the 4 RED workbooks (finding 3)

For each, back up first, edit via `transaction.py`, then re-run `checkverdict <p>` (Helper H-1) until the targeted rule clears (F-15 will stay AMBER by design — that's expected).

- [ ] **eykom** — in `master_task`: map the 33 non-enum `priority` values to the severity enum (or move non-severity tokens like `developer`/`P1`/`P2` to an `assignee`/`note` column); move the 23 `created_date` cells containing prose into the `note` column and set a valid ISO date (or blank). Target: F-17 + F-18 clear → eykom no longer RED.
- [ ] **lastiksa-tr** — in `master_task.status`, change the single `IN_PROGRESS` value to the valid in-progress enum value. **Confirm the exact token** against `schemas/master-excel.schema.json` `#/definitions/statusEnum` (the 7 allowed values) before editing. Target: F-01 clears.
- [ ] **vento** — reconcile the 21 `quick_wins.url` values that aren't in the `opportunity` sheet: either add the corresponding opportunity rows or correct/remove the dangling quick-win URLs. Target: F-16 clears.
- [ ] **noran-insaat-tr** — the 13/17 column-count mismatch means sheet headers drifted from the current schema. Re-bootstrap/re-import the affected sheets to the current header schema (preferred over hand-editing 13 sheets). Target: F-05 clears. (This is the most involved item — consider doing it via a fresh `master.xlsx` regenerated from the current template + re-ingested data.)
- [ ] **Verify all four (Helper H-1):**

```bash
for p in eykom lastiksa-tr noran-insaat-tr vento; do checkverdict "$p"; done
```
Expected: each prints AMBER (F-15 only) or GREEN — no RED.

- [ ] **Commit (workspace):** one commit per project or one "normalize RED workbooks" commit — ask Süleyman; keep separate from engine.

### Task F3: Fix the 3 invalid workflow run JSONs (finding 2, decision D-2)

- [ ] **adstark (2 files)** — per D-2 default (a): rename `adstark-tr-2026-05-08-full-ingest-3d90.json` and `adstark-tr-2026-05-08-sf-c03b.json` (and their internal `run_id`) to the canonical `{slug}-{YYYY-MM-DD}-{hash4}` form. (If D-2 (b) chosen instead, relax the schema `run_id` pattern in the engine — that becomes an engine Batch-A task, not workspace.)
- [ ] **iwallet legacy** (`projects/iwallet-tr/_state/workflows/run-0001.json`, 13 errors) — migrate to current shape: string `run_id`, lowercase `status`/step-statuses, add `skill` + `updated_at`, convert `outputs` array→object, drop `metrics`/`workflow_name`. OR archive it as `run-0001.json.legacy` (mirroring the ADR-031 events `.legacy` migration) if it represents a historical run not meant to resume.
- [ ] **Verify:**

```bash
for f in $(find /Users/apple/Documents/platinum-seo-workspace -path '*workflows*' -name '*.json'); do
  python3 /Users/apple/Documents/platinum-seo-engine/scripts/validation/validate_schema.py "$f" \
    /Users/apple/Documents/platinum-seo-engine/schemas/workflow-run.schema.json >/dev/null 2>&1 \
    && echo "PASS $f" || echo "FAIL $f"
done
```
Expected: all PASS (or the archived `.legacy` files no longer match the `*.json` glob).

- [ ] **Commit (workspace).**

### Task F4: Fix the two numeric `language_code` values (finding 4, data half)

- [ ] **Step 1:** In `/Users/apple/Documents/platinum-seo-workspace/projects/miningaa-com/project.config.json:32` change `"language_code": "1001"` → `"language_code": "tr"`.
- [ ] **Step 2:** In `/Users/apple/Documents/platinum-seo-workspace/projects/noran-insaat-tr/project.config.json:32` change `"language_code": "1031"` → `"language_code": "tr"`.
- [ ] **Step 3:** Verify both now pass the (newly tightened) schema:

```bash
for p in miningaa-com noran-insaat-tr; do
  python3 /Users/apple/Documents/platinum-seo-engine/scripts/validation/validate_schema.py \
    /Users/apple/Documents/platinum-seo-workspace/projects/$p/project.config.json \
    /Users/apple/Documents/platinum-seo-engine/schemas/project-config.schema.json
done
```
Expected: both PASS (and would now FAIL if reverted to the numeric value — proving Batch A2's guard works end-to-end).

- [ ] **Step 4:** Commit (workspace).

### Task F5: Fix the stale workspace CLAUDE.md active-project pointer (finding 11)

- [ ] **Step 1:** In `/Users/apple/Documents/platinum-seo-workspace/CLAUDE.md:8`, remove the hardcoded `(şu an: dentnotion)` and replace with a non-staleable phrasing, e.g. ``- **Active project**: see `shared/active.json` marker (do not hardcode the slug here)``.
- [ ] **Step 2:** Commit (workspace).

### Batch F gate

```bash
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 /Users/apple/Documents/platinum-seo-engine/scripts/state/dump_workspace.py --json | head -40
# expect: active project resolves; no RED beyond intentional F-15 AMBER
```

---

## Final Verification (after all batches)

- [ ] **Full engine suite green (with the new tests):**

```bash
cd /Users/apple/Documents/platinum-seo-engine
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest --tb=short -q
```
Expected: `>= 1449 passed` plus the ~11 new tests added by this plan, `0 failed`.

- [ ] **Targeted gates from the audit's own checklist:**

```bash
python3 -m pytest --tb=short -q tests/ci tests/commands tests/hooks tests/schemas tests/docs tests/skills tests/scripts
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 scripts/state/dump_workspace.py --json | head -20
```

- [ ] **Workspace no longer RED (except intentional F-15) — Helper H-1:**

```bash
for p in adstark-tr aluminumstation-ca bigcat-tr dentnotion eykom iwallet-tr lastiksa-tr miningaa-com noran-insaat-tr vento; do checkverdict "$p"; done
```

- [ ] **Release bookkeeping (only if Süleyman wants a tagged patch):** version bump (5-file sync via the dogfooded Y-05 tooling), `RELEASE_NOTES_v1.9.6.md`, annotated tag, push both repos. Ask first.

---

## Regression-Test Matrix (the audit's core ask: "so the same mismatch cannot return")

| Test | Locks | Finding |
|------|-------|---------|
| `test_dataforseo_endpoint_mapping_schema_const_matches_mcp_json` | schema const == `.mcp.json` version (3rd surface) | 9 |
| `test_project_config_language_code` | language_code is ISO, not numeric | 4 |
| `test_marketplace_schema_count_matches_filesystem` | marketplace blurb == real schema file count | 13 |
| `test_pseo_active_safety` | letter-start slug + abort-on-missing-config | 5a/5b |
| `test_events_writer_path_guard` | events_writer rejects invalid/traversal ids | 5d |
| `test_command_doc_impl_parity` | init/quickwin/cannibalization doc==impl | 10 |
| `test_command_references_exist` | command schema-paths + sheet names exist | 10/P1-14 |
| `test_secret_scan_untracked` | incremental scan covers untracked files | 7 |
| `test_check_excel_writer` (extended) | invalid workbook rejected despite commit signal | 14 |
| `test_no_racy_next_run_id` | no racy next_run_id() in skill docs | 6 |
| `test_readme_no_fictional_config` | README has no config.yaml | 12 |
| `test_dump_workspace*` (extended) | reads root workbook + live drift verdict (no nulls) | bonus |

---

## Appendix — Cross-reference to the broader `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md` (2026-06-03)

The 14 verified findings overlap with the broader 2026-06-03 audit doc. Items in that doc NOT fully covered above — pull into a follow-up pass if Süleyman wants the full sweep (verify-then-fix each, same TDD discipline):

- **P0-01** cross-sheet invariant registry vs implementation mean different things (F-01/F-02/F-05 registry text ≠ code) — **high value**, governance authority.
- **P0-05** slash-command `allowed-tools` don't match real shell usage (18 mismatches) — pairs naturally with Batch B.
- **P1-02** `validate_schema.py` doesn't pass `FormatChecker` (format: uri/date-time unchecked).
- **P1-03** nested objects missing `additionalProperties: false` (project-config, monthly-report, etc.).
- **P1-04** events schema conditionals lack `required: [event_kind]`; description says "three kinds", enum has four.
- **P1-06** PostToolUse audit hook `|| true` + Bash always classified `accessed`.
- **P1-07** PreToolUse Excel owner-lock regex too narrow (spaces/quotes/`~`).
- **P1-10** workflow_runner swallows emit failures; pause/approve ignore reason/notes; retry drops `ended_at`.
- **P1-11** `next_run_id()` itself lockless (the runtime, not just the docs — Batch D fixes only the docs).
- **P1-12/P1-13** brand-onboarding stub + Higgsfield user-level MCP not represented in registry.
- **P2-01..08, P3-01..03** stale docs/counts, template dialect manifest, requirements/lock drift, portfolio-vs-tracked-state.

**Already fixed in the current local tree (do NOT reopen):**
- **P0-02** (`dump_workspace` reads `slug`) — now reads `active_project` first with legacy fallback (`dump_workspace.py:61`); 17 tests pass incl `test_dump_reads_active_project_canonical`. Batch E addresses only the *separate* workbook-path/verdict blind spot.
- **P0-03** (DFS version `.mcp.json`↔registry) — aligned at 2.8.10 + test-locked; finding 9 here is the residual schema-const *third surface*.
- **P0-06** (SF crawl `--source-run-id`) — purged in HEAD `e295237` (last commit).
- **Local-Fixed 1–4** (CI MCP count 3→4, incremental secret-scan perf, `transaction.update()` row scan, README Draft-7 wording) — already in the working tree per the audit handoff.
