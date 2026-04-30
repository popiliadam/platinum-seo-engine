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
status: wip
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
read_only=True), evaluates **20 hand-coded invariant rules** (5
CRITICAL + 10 HIGH + 5 MEDIUM), aggregates per §17.2 verdict logic
(any RED → RED; else any AMBER → AMBER; all PASS → GREEN), emits a
`consistency-report-{slug}.json` (validated against
`schemas/consistency-report.schema.json`), renders a human-readable
markdown report, and appends an `event_kind=audit` row to `events.jsonl`
with `audit_action="accessed"` and `audit_target="invariants:20"`.

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
  (`audit_action=accessed`, `audit_target=invariants:20`).

## 8-Step Body Protocol

> Each step name maps 1:1 to `workflow_runner.steps[].name`.

### Step 1 — `create_run`

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="drift-check",
    project_slug=project_slug,
    steps=[
        {"name": "load_workbook"},
        {"name": "evaluate_invariants"},
        {"name": "aggregate_verdict"},
        {"name": "emit_consistency_report"},
        {"name": "render_report"},
        {"name": "emit_audit_event"},
    ],
)
```

### Step 2 — `load_workbook` (read-only, data_only=True)

```python
from openpyxl import load_workbook
import hashlib
wb_path = workspace_root / "projects" / project_slug / "master.xlsx"
if not wb_path.exists():
    workflow_runner.fail(handle.run_id, project_slug=project_slug,
                         code="validation_error",
                         message=f"master.xlsx not found at {wb_path}")
    return  # DURUR-1
sha_before = hashlib.sha256(wb_path.read_bytes()).hexdigest()
wb = load_workbook(str(wb_path), data_only=True, read_only=True)
```

`read_only=True` forbids any mutation accidentally; `data_only=True`
loads cached values, not formula bodies. Write attempts on a read-only
workbook raise immediately.

### Step 3 — `evaluate_invariants` (20 rules)

```python
from scripts.validation import validate_invariants
results = validate_invariants.evaluate_all(wb, project_slug)
# results: list of {"id", "severity", "verdict", "evidence", ...}
```

The 20 rules are partitioned:

| Tier      | Count | Verdict on FAIL  |
|-----------|-------|------------------|
| CRITICAL  | 5     | RED              |
| HIGH      | 10    | RED (F-15 AMBER) |
| MEDIUM    | 5     | AMBER            |

### Step 4 — `aggregate_verdict`

```python
agg = validate_invariants.aggregate_verdicts(results)
# agg: {"overall": "GREEN|AMBER|RED",
#       "fail_count": int, "warn_count": int, "pass_count": int,
#       "manual_review_required": [...]}
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
report_path = (workspace_root / "projects" / project_slug
               / "outputs" / "reports"
               / f"{today}-drift-{project_slug}.md")
```

Template variables: `$project_slug`, `$date`, `$verdict`, `$pass_count`,
`$warn_count`, `$fail_count`, `$total_checks`,
`$manual_review_required`, `$report_summary`.

### Step 7 — `emit_audit_event`

```python
from scripts.state import events_writer
events_writer.append_audit(
    project_id=project_slug,
    audit_action="accessed",
    audit_target="invariants:20",
    actor="drift-check",
    notes=f"verdict={agg['overall']} fails={agg['fail_count']}",
)
```

`event_kind=audit` is governance-only; no provenance event because
drift-check writes nothing into the workbook.

### Step 8 — `complete`

```python
sha_after = hashlib.sha256(wb_path.read_bytes()).hexdigest()
assert sha_after == sha_before, "DURUR-5: master.xlsx mutated under drift-check"
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    "verdict": agg["overall"],
    "fail_count": str(agg["fail_count"]),
    "report_path": str(report_path),
    "consistency_report_path": str(consistency_report_path),
})
```

**F5 outputs string-typed:** every value in `outputs` is a STRING
(workflow-run.schema.json `outputs.additionalProperties.type` is
`"string"`). `fail_count` is `str(agg["fail_count"])`, NOT a raw int.

## 20 Invariant Rules

Source of truth: `scripts/validation/validate_invariants.py`. Each
rule function signature:

```python
def check_F_XX(workbook, project_slug) -> dict:
    return {"id": "F-XX", "severity": "...", "verdict": "...",
            "evidence": "...", "rule": "...",
            "category": "...", ...}
```

### CRITICAL (5)

| ID    | Rule                                                                  |
|-------|-----------------------------------------------------------------------|
| F-01  | master_task.status ⊆ statusEnum 7-value (TODO/ONGOING/EXISTS/DONE/BLOCKED/DEFERRED/CANCELED) |
| F-02  | dashboard formula `=COUNTIF(...)` drift check (sheet missing → AMBER skip) |
| F-03  | dashboard formula `=SUMIF(...)` drift check                           |
| F-04  | dashboard formula `=AVERAGEIF(...)` drift check                       |
| F-05  | schema_version field per-sheet present (every schema-known sheet has a header row matching schema column count) |

### HIGH (10)

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

### MEDIUM (5)

| ID    | Rule                                                                  |
|-------|-----------------------------------------------------------------------|
| F-18  | master_task.created_at ISO 8601 parseable                             |
| F-19  | optional field defaults present (project.config locale, market)       |
| F-20  | events.jsonl per-line size <64 KB cap                                 |
| F-21  | every cell value <32767 chars (Excel hard limit)                      |
| F-22  | backup directory FIFO 7 (transaction.py keep-7 rotation)              |

## F2 flag — F-08 RED is EXPECTED on the pilot workbook

The demo-dental pilot `master.xlsx` currently contains only `quick_wins`
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
