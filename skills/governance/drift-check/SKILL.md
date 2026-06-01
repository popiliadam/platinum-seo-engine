---
name: drift-check
description: |
  Use when: kullanıcı "drift kontrol", "consistency check", "schema drift",
  "veri tutarlılık", "audit", "/pseo-driftcheck" der ya da PostToolUse hook
  master.xlsx update sonrası tetiklenir.
  Also use when: master.xlsx update sonrası invariant kontrolü; Phase
  gateway öncesi quality gate; ingestion skill (sf-import, quick-wins,
  vb.) tamamlandıktan sonra "checkpoint L6" §9.4.
  Do not use when: yeni skill yazma (writing-skills), bug fix (debug),
  build error (build-error-resolver) — drift-check governance read-only,
  master.xlsx asla mutate edilmez.
version: "1.0"
status: active
category: governance
inputs:
  project_slug: { type: string, required: false, description: "Tek proje hedeflemek için. Verilmezse PSEO_WORKSPACE_ROOT altındaki tüm projeler taranır." }
outputs:
  - "outputs/reports/{date}-drift-{slug}.md"
  - "_state/consistency-report-{slug}.json"
  - "events.jsonl"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "quick-wins:projects/{slug}/master.xlsx#quick_wins"
  - "sf-import:projects/{slug}/master.xlsx#crawl_sitemap"
produces: []
triggers:
  manual: ["/pseo-driftcheck"]
  natural_language: |
    "drift kontrol", "consistency check", "schema drift",
    "veri tutarlılık", "audit", "invariant kontrolü", "tutarlılık raporu"
  hooks: ["PostToolUse"]
  scheduled:
    - cron: "0 6 * * *"
      mode: "report-only"
mcp_tools:
  required: []
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: false
  safe_auto_execute: true
---

# drift-check — governance skill (Phase 5 Wave 2)

Read-only consistency engine. Loads `master.xlsx` (data_only=True,
read_only=True), evaluates **22 hand-coded invariant rules** (5
CRITICAL + 12 HIGH + 5 MEDIUM; F-23 added v1.8 Phase 4, F-24 added
v1.9 Phase 2), aggregates per §17.2 verdict logic
(any RED → RED; else any AMBER → AMBER; all PASS → GREEN), emits a
`consistency-report-{slug}.json` (validated against
`schemas/consistency-report.schema.json`), renders a human-readable
markdown report, and appends an `event_kind=audit` row to `events.jsonl`
with `audit_action="accessed"` and `audit_target="invariants:22"`.

The rules are hand-coded Python functions, **not** a DSL — that is a
deliberate Phase 6+ refactor candidate (§17.2 ADR-TBD). Each rule
function returns `{"id", "severity", "verdict", "evidence"}` and the
aggregator converts those into a schema-valid `consistency-report.checks[]`
list.

## DURUR (no fall-back) conditions

1. `master.xlsx` does not exist at `projects/{slug}/master.xlsx` → DURUR.
2. `workflow_runner.create_run` raises (schema invalid) → DURUR.
3. `validate_invariants.py` rule function raises an unhandled exception
   → DURUR (don't paper over with "skip" — the rule logic is broken).
4. `PSEO_WORKSPACE_ROOT` env unset and no `workspace_root` arg passed
   → DURUR (skill needs the projects/ tree to live somewhere).
5. master.xlsx SHA-256 changes between pre-load and post-load
   (read-only violation) → DURUR.
6. `consistency-report.json` fails its schema validation → DURUR.

## Inputs (frontmatter contract)

| Name           | Type   | Default | Notes                                                                  |
|----------------|--------|---------|------------------------------------------------------------------------|
| `project_slug` | string | none    | Optional. Verilmezse PSEO_WORKSPACE_ROOT altındaki tüm projeler taranır. |

## Outputs (artifacts produced)

- `projects/{slug}/outputs/reports/{date}-drift-{slug}.md` — human report.
- `projects/{slug}/_state/consistency-report-{slug}.json` — schema-valid JSON.
- `projects/{slug}/_state/events.jsonl` — single `event_kind=audit` entry
  (`audit_action=accessed`, `audit_target=invariants:22`).

## 8-Step Body Protocol

> Each step name maps 1:1 to `workflow_runner.steps[].name`.

### Step 1 — `create_run`

```python
# Standalone-executable entrypoint (Phase 14 W3-W1 helper exec compliance):
# imports + entrypoint variables init for downstream concat blocks. Workflow
# step example documented as runtime-style invocation but NOT actually called
# at this layer (helper does syntax + import smoke; orchestrator owns dispatch).
import os
import sys
from pathlib import Path
import hashlib
import re

# sys.path insert so `scripts.*` packages resolve when run via subprocess
# (run_skill_python.py temp-file exec inherits cwd but not sys.path[0]).
sys.path.insert(0, os.getcwd())

from scripts.state import workflow_runner
from scripts.state import events_writer

# Entrypoint variables (placeholder defaults — orchestrator overrides at runtime)
project_slug = "drifttest"
workspace_root = Path.cwd()
results: list[dict] = []
agg: dict = {}

# Workflow step example (documentation; orchestrator owns dispatch):
# handle = workflow_runner.create_run(
#     skill="drift-check",
#     project_slug=project_slug,
#     steps=[
#         {"name": "load_workbook"},
#         {"name": "evaluate_invariants"},
#         {"name": "aggregate_verdict"},
#         {"name": "emit_consistency_report"},
#         {"name": "render_report"},
#         {"name": "emit_audit_event"},
#     ],
# )
```

### Step 2 — `load_workbook` (read-only, data_only=True)

```python
# load_workbook step (documented as function — concat-friendly, not executed):
def step_load_workbook(workspace_root: Path, project_slug: str):
    from openpyxl import load_workbook
    wb_path = workspace_root / "projects" / project_slug / "master.xlsx"
    if not wb_path.exists():
        # workflow_runner.fail(handle.run_id, project_slug=project_slug,
        #                      code="validation_error",
        #                      message=f"master.xlsx not found at {wb_path}")
        return None  # DURUR-1
    sha_before = hashlib.sha256(wb_path.read_bytes()).hexdigest()
    wb = load_workbook(str(wb_path), data_only=True, read_only=True)
    return wb, sha_before, wb_path

# Placeholder values for downstream block syntax (orchestrator binds real ones)
wb_path = workspace_root / "projects" / project_slug / "master.xlsx"
sha_before = ""
wb = None
```

`read_only=True` forbids any mutation accidentally; `data_only=True`
loads cached values, not formula bodies. Write attempts on a read-only
workbook raise immediately.

### Step 3 — `evaluate_invariants` (20 rules)

```python
from scripts.validation import validate_invariants
# results = validate_invariants.evaluate_all(wb, project_slug)
# results: list of {"id", "severity", "verdict", "evidence", ...}
# (Documented invocation; helper exec leaves results bound from Step 1 init.)
```

The 21 rules are partitioned:

| Tier      | Count | Verdict on FAIL  |
|-----------|-------|------------------|
| CRITICAL  | 5     | RED              |
| HIGH      | 11    | RED (F-15 AMBER) |
| MEDIUM    | 5     | AMBER            |

### Step 4 — `aggregate_verdict`

```python
# agg = validate_invariants.aggregate_verdicts(results)
# agg: {"overall": "GREEN|AMBER|RED",
#       "fail_count": int, "warn_count": int, "pass_count": int,
#       "manual_review_required": [...]}
# Placeholder (orchestrator binds real aggregate at runtime):
agg = {"overall": "GREEN", "fail_count": 0, "warn_count": 0,
       "pass_count": 20, "manual_review_required": []}
```

§17.2: any FAIL with severity CRITICAL/HIGH → RED (except F-15 manual
triage which routes to AMBER + `manual_review_required[]`); MEDIUM
FAIL → WARN/AMBER; missing-sheet skip → AMBER (not RED).

### Step 5 — `emit_consistency_report`

Build a `consistency-report-{slug}.json` shaped per
`schemas/consistency-report.schema.json` (schema_version "1.0",
report_id monotonic, verdict, checks[], summary roll-up,
manual_review_required[], auto_repair_performed[]). Write to
`projects/{slug}/_state/consistency-report-{slug}.json`. Validate
against the schema BEFORE write — Draft7Validator inside
`validate_invariants.build_consistency_report()`.

### Step 6 — `render_report`

```python
from scripts.reporting import render_template
# render_template.py templates/reports/drift.template.md data.json
from datetime import datetime, timezone
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
report_path = (workspace_root / "projects" / project_slug
               / "outputs" / "reports"
               / f"{today}-drift-{project_slug}.md")
consistency_report_path = (workspace_root / "projects" / project_slug
                           / "_state"
                           / f"consistency-report-{project_slug}.json")
```

Template variables: `$project_slug`, `$date`, `$verdict`, `$pass_count`,
`$warn_count`, `$fail_count`, `$total_checks`,
`$manual_review_required`, `$report_summary`.

### Step 7 — `emit_audit_event`

```python
# event_kind=audit emit (documented; orchestrator runs at workflow time):
# events_writer.append_audit(
#     project_id=project_slug,
#     audit_action="accessed",
#     audit_target="invariants:22",
#     actor="drift-check",
#     notes=f"verdict={agg['overall']} fails={agg['fail_count']}",
# )
audit_payload = {
    "event_kind": "audit",
    "audit_action": "accessed",
    "audit_target": "invariants:22",
    "actor": "drift-check",
    "notes": f"verdict={agg['overall']} fails={agg['fail_count']}",
}
```

`event_kind=audit` is governance-only; no provenance event because
drift-check writes nothing into the workbook.

### Step 8 — `complete`

```python
# Step 8 — `complete` (documented; orchestrator runs at workflow time):
# sha_after = hashlib.sha256(wb_path.read_bytes()).hexdigest()
# assert sha_after == sha_before, "DURUR-5: master.xlsx mutated under drift-check"
# workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={...})
complete_outputs = {
    "verdict": agg["overall"],
    "fail_count": str(agg["fail_count"]),
    "report_path": str(report_path),
    "consistency_report_path": str(consistency_report_path),
}
```

**F5 outputs string-typed:** every value in `outputs` is a STRING
(workflow-run.schema.json `outputs.additionalProperties.type` is
`"string"`). `fail_count` is `str(agg["fail_count"])`, NOT a raw int.

## 20 Invariant Rules

Source of truth: `scripts/validation/validate_invariants.py`. Each
rule function signature:

```python
def check_F_XX(workbook, project_slug) -> dict:
    # Concrete return shape; severity ⊆ {LOW, MEDIUM, HIGH, CRITICAL},
    # verdict ⊆ {PASS, FAIL, SKIP}, category per validate_invariants enum.
    return {
        "id": "F-XX",
        "severity": "MEDIUM",
        "verdict": "PASS",
        "evidence": "placeholder evidence string",
        "rule": "placeholder rule description",
        "category": "csr_foundation",
    }
```

### CRITICAL (5)

| ID    | Rule                                                                  |
|-------|-----------------------------------------------------------------------|
| F-01  | master_task.status ⊆ statusEnum 7-value (TODO/ONGOING/EXISTS/DONE/BLOCKED/DEFERRED/CANCELED) |
| F-02  | dashboard formula `=COUNTIF(...)` drift check (sheet missing → AMBER skip) |
| F-03  | dashboard formula `=SUMIF(...)` drift check                           |
| F-04  | dashboard formula `=AVERAGEIF(...)` drift check                       |
| F-05  | schema_version field per-sheet present (every schema-known sheet has a header row matching schema column count; header row resolved via schema authority `sheets[sheet].header_row` with row-1 fallback — Phase 14 W3-W2-C-a) |

### HIGH (12)

| ID    | Rule                                                                  |
|-------|-----------------------------------------------------------------------|
| F-08  | quick_wins.url ⊆ (crawl_sitemap.url ∪ gsc_performance.url) — **pilot RED expected, see F2 flag below** |
| F-09  | master_task.task_id unique                                            |
| F-10  | quick_wins.url D-03 normalize idempotent                              |
| F-11  | workflow-run schema_version "1.0" across all _state/workflows/*.json  |
| F-12  | events.jsonl append-only (line count grows monotonically across runs) |
| F-13  | provenance.run_id integer (per events.schema)                         |
| F-14  | workflow.workflow_run_id pattern (per events.schema)                  |
| F-15  | manual triage placeholder — populates manual_review_required[] (AMBER, NOT RED) |
| F-16  | foreign key cross-sheet: quick_wins.url ⊆ opportunity.url             |
| F-17  | severity column ⊆ severityEnum 4-value (LOW/MEDIUM/HIGH/CRITICAL)     |
| F-23  | sf-crawl-orchestrator workflow → repo-root mcp-tool-registry.json has 'sf' (v1.8 Phase 4 SF MCP cross-sheet) |
| F-24  | .mcp.json mcpServers keys == mcp-tool-registry.json servers keys (ScraplingServer↔scrapling case-fold; v1.9 Phase 2 engine transport↔inventory sync) |

### MEDIUM (5)

| ID    | Rule                                                                  |
|-------|-----------------------------------------------------------------------|
| F-18  | master_task.created_at ISO 8601 parseable                             |
| F-19  | optional field defaults present (project.config locale, market)       |
| F-20  | events.jsonl per-line size <64 KB cap                                 |
| F-21  | every cell value <32767 chars (Excel hard limit)                      |
| F-22  | backup directory FIFO 7 (transaction.py keep-7 rotation)              |

### Engine Self-Governance (6, v1.4-deep-audit-fix Tier 4)

These invariants enforce engine repo discipline (schemas/+rules/+templates/) — not workspace state. Each row owns a regression-lock test that fires on every commit; drift-check skill body invokes them via `pytest tests/<area>/test_<name>.py` (standalone-executable convention per rules/skills.md Section 1).

| ID    | Rule                                                                  | Regression Test                            |
|-------|-----------------------------------------------------------------------|--------------------------------------------|
| F-29  | schema $id format HTTP + slug + no .schema.json suffix (ADR-012)      | tests/schemas/test_id_format.py             |
| F-30  | schema_version coverage (every schema declares; const not pattern)    | tests/schemas/test_version_field.py         |
| F-31  | cross-schema enums sync (events.primary_source ⊆ master_task)         | tests/schemas/test_cross_schema_enums.py    |
| F-32  | R-XX resolution (every R-XX cited in templates defined or superseded) | tests/rules/test_r_xx_resolution.py         |
| F-33  | report run_id + Kanıt zinciri H2 (every templates/reports/*.md)       | tests/templates/test_run_id_coverage.py     |
| F-34  | rules frontmatter validates against rules-frontmatter.schema.json     | tests/rules/test_frontmatter.py             |

> **v1.8 Phase 6 renumber note:** v1.4 engine self-governance F-23..F-28 renumbered F-29..F-34 in v1.8 Phase 6 to disambiguate from `cross-sheet-invariants.json` F-23 SF MCP instance entry (2026-05-27). SKILL.md narrative labels exempt from ADR-038 persistent-registry renumber-forbidden policy (no audit history references them; they are document-only narrative anchors, never persisted in the JSON registry). Cross-refs verified: tests in the regression-test column point to actual test files by path (e.g. `tests/schemas/test_id_format.py`) — those test files do NOT reference the SKILL.md F-XX narrative labels, so no test edit required.

Severity: ALL HIGH — engine self-violation breaks SSOT/schema-first discipline at the meta level. Per §17.2, any FAIL → RED (no manual triage placeholder; automated tests are deterministic).

## F-23 — SF MCP cross-sheet invariant (v1.8 Phase 4)

If any project's `_state/workflows/*.json` contains a completed run with
`skill="sf-crawl-orchestrator"`, then the repo-root
`mcp-tool-registry.json` MUST list `"sf"` under `servers`. A workspace
that has produced SF MCP crawl evidence with an engine registry that
does NOT advertise the `sf` server silently desyncs downstream sf-import
handoff and tooling discovery (`claude mcp list` cross-check).

Detection logic — `check_F_23()` reads:
1. Project `_state/workflows/*.json` files (per project_slug). Filters
   to entries with `skill == "sf-crawl-orchestrator"` AND
   `status == "done"`.
2. Repo root `mcp-tool-registry.json` (single instance per F-16
   plugin-agnostic boundary). Checks if `"sf"` appears as a top-level
   key under `servers`.
3. If (1) is non-empty AND (2) is missing the `sf` key → FAIL with
   severity HIGH (→ RED verdict). Sample violations list the run_ids
   that produced the evidence.
4. If `mcp-tool-registry.json` is absent → SKIP (engine state, not
   workspace; surfaces as AMBER skip).

Severity HIGH (not CRITICAL) per Manager Phase 4 scope: drift produces
broken provenance lineage but does not corrupt master.xlsx.

### Naming-namespace note (Q-PHASE-4-WORKER-01, RESOLVED v1.8 Phase 6)

The body subsection "Engine Self-Governance (6, v1.4-deep-audit-fix
Tier 4)" above now uses F-29..F-34 as labels for SCHEMA-LEVEL regression
rules (e.g. F-29 there = schema $id format). Those labels are
documentation-only and live in this SKILL.md body — they have never
been registered in `schemas/cross-sheet-invariants.json`. The Phase 4
F-23 (SF MCP cross-sheet) is the canonical F-23 for the JSON registry
and `validate_invariants.py` rule function. Pre-v1.8 these labels were
F-23..F-28 and collided with the canonical F-23; v1.8 Phase 6 renumbered
the engine-self-governance labels to F-29..F-34 to remove the human-label
collision. Both namespaces still live in disjoint stores (JSON registry
vs SKILL.md narrative).

## F-24 — `.mcp.json` ↔ `mcp-tool-registry.json` key sync (v1.9 Phase 2)

The set of `.mcp.json` `mcpServers` keys MUST equal the set of
`mcp-tool-registry.json` `servers` keys. `.mcp.json` is the MCP **transport**
config (how each server is launched); `mcp-tool-registry.json` is the **tool
inventory** (what each server advertises). If the two desync — a server
configured for transport but absent from the inventory (**orphan transport**),
or inventoried but not configured (**orphan inventory**) — tooling discovery
and `claude mcp list` cross-checks silently disagree.

Detection logic — `check_F_24()` reads (engine-level; ignores `workspace_root`,
never mutates the files, F-16 safe):
1. Engine repo-root `.mcp.json` → `mcpServers` keys.
2. Engine repo-root `mcp-tool-registry.json` → `servers` keys.
3. Normalizes the `.mcp.json` side via the **explicit** alias
   `ScraplingServer → scrapling` (D-SF-02: `.mcp.json` carries the legacy
   capitalized transport label, the registry the canonical lowercase key).
   This is an explicit alias, **not** a blanket `.lower()` — a generic casefold
   would yield `scraplingserver ≠ scrapling` and false-FAIL (spec risk R3).
4. Non-empty set delta → FAIL HIGH (→ RED). Sample violations are tagged
   `orphan_transport:<key>` / `orphan_inventory:<key>`.
5. Either file missing → SKIP (engine state ambiguous; surfaces AMBER).

Category `csr_mcp` (mirrors F-23). Severity HIGH (→ RED on FAIL): a
transport/inventory desync breaks tooling-discovery provenance but does not
corrupt `master.xlsx`. (Spec FE-1 proposed category `engine_consistency`; that
value is not in `consistency-report.schema.json`'s 8-category enum, so
`check_F_24` emits `csr_mcp` — see Q-V1.9-PHASE-2-WORKER-01.)

## F2 flag — F-08 RED is EXPECTED on the pilot workbook

The pilot project `master.xlsx` currently contains only `quick_wins`
and `opportunity` sheets (Wave 1 Q-W output, no SF import yet). F-08
requires `crawl_sitemap` ∪ `gsc_performance` to be populated to compute
the subset; with both sheets missing, the rule returns:

- `verdict: "RED"` raw
- BUT promoted to `verdict: "AMBER"` and added to
  `manual_review_required[]` because the missing-sheet condition
  routes through the F-15 manual-triage handler.

Wave 2 closeout (after sf-import / W-R lands `crawl_sitemap`) MUST
re-run drift-check; F-08 should then flip to GREEN.

## Cross-references

- Schemas: `schemas/master-excel.schema.json`,
  `schemas/events.schema.json`, `schemas/workflow-run.schema.json`,
  `schemas/consistency-report.schema.json`,
  `schemas/cross-sheet-invariants.json` (rule registry).
- Cross-modules: `scripts/state/workflow_runner.py`,
  `scripts/state/events_writer.py`,
  `scripts/reporting/render_template.py`,
  `scripts/validation/validate_schema.py`.
- Implementation: `scripts/validation/validate_invariants.py`.
- Tests: `tests/skills/test_drift_check.py` (11 cases incl. live pilot).
- Template: `templates/reports/drift.template.md`.
