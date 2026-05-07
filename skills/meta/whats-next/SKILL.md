---
name: whats-next
description: |
  Use when: kullanıcı "ne yapayım", "şimdi ne", "next step", "öncelikli
  işler", "what to work on", "where do I start" der ya da SessionStart
  hook tetiklenir.
  Also use when: yeni session açıldı, pending approval check gerek,
  decay/quick-wins prioritization istendi, tüm projeleri tarayıp en
  acil iş seçilecek.
  Do not use when: spesifik skill direkt çağrıldı (init-project,
  sf-import, quick-wins, drift-check) — whats-next router skill'dir,
  başka skill'leri SUGGEST eder, çağırmaz; advisory-only.
version: "1.0"
status: active
category: meta
inputs:
  user_intent:
    type: string
    required: false
    description: "Kullanıcı niyeti — varsa ranking'e bias eklenir."
  project_slug:
    type: string
    required: false
    description: "Tek proje filtre. Yoksa tüm projects/* taranır."
  top_k:
    type: integer
    required: false
    default: 3
    description: "Döndürülecek ranked recommendation sayısı."
outputs:
  - "events.jsonl"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "quick-wins:master.xlsx#quick_wins"
produces: []
triggers:
  manual: []
  natural_language: |
    "ne yapayım", "şimdi ne", "next step", "öncelikli işler",
    "what to work on", "where do I start", "öncelik sırası",
    "pending approval", "bekleyen onay"
  hooks: ["SessionStart"]
  scheduled: []
mcp_tools:
  required: []
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: false
  safe_auto_execute: false
---

# whats-next — meta skill (Phase 5 Wave 2, router pattern)

Advisory-only **router** skill. Reads project state across four signal
sources (`master_task`, `content_decay`, `_state/workflows/*.json`
awaiting_approval, `quick_wins` pending approval), scores each
candidate with a fixed heuristic, and emits a Top-K ranked list of
*next skills to invoke*. Whats-next never invokes those skills itself
— a manager (or the user) reads the recommendation and picks one.

This is the **convention authority** for future router-style meta
skills (e.g. `daily-summary`, `incident-triage`). 10 numbered steps,
single workflow run shell, deterministic heuristic, schema-shaped
event emission. Reuse the structure verbatim; deviate only with an
ADR.

## Inputs (frontmatter contract)

| Name           | Type    | Default | Notes                                                        |
|----------------|---------|---------|--------------------------------------------------------------|
| `user_intent`  | string  | —       | Optional NL hint; passed through to the recommendation note. |
| `project_slug` | string  | —       | If omitted, all `projects/*/master.xlsx` are scanned.        |
| `top_k`        | integer | 3       | Cap on returned recommendations (1..10 enforced at runtime). |

## Outputs (artifacts produced)

- `projects/{slug}/_state/events.jsonl` — single `event_kind=work`,
  `event_type=skill_whats_next` row per run (canonical v1.6-Phase-2 H-E;
  replaces legacy DSL workaround `event_type=manual + note=[skill=...]`),
  `note` carries the markdown summary of the ranked recommendations
  (router event).
- Console / return-value: short markdown bullet list of the Top-K
  recommendations (advisory; no Excel writes).

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across
> runs and form the audit trail in `_state/workflows/{run_id}.json`.

### Step 1 — `create_run`

Open a single workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-019, ADR-021).
Whats-next is single-project per run; if `project_slug` is omitted the
caller iterates the loop externally (one run per project).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="whats-next",
    project_slug=project_slug,
    steps=[
        {"name": "scan_master_task"},
        {"name": "scan_content_decay"},
        {"name": "scan_pending_approvals"},
        {"name": "scan_quick_wins_pending"},
        {"name": "score_and_rank"},
        {"name": "emit_router_event"},
    ],
)
```

### Step 2 — `scan_master_task`

Open `projects/{slug}/master.xlsx` read-only via openpyxl
(`data_only=True`, `read_only=True`). If the sheet `master_task` is
absent, return an empty list (init-project not run yet — this is
AMBER, not RED). Otherwise iterate rows starting at
`data_start_row=4` and collect rows where:

- column J (`status`) == `"TODO"`, AND
- column G (`priority`) ∈ `{"CRITICAL", "HIGH", "MEDIUM", "LOW"}`.

Each row becomes a candidate `{kind: "master_task", row_id: A, task:
B, priority: G, ...}`.

### Step 3 — `scan_content_decay`

Same workbook. If the sheet `content_decay` is absent, return an
empty list (sheet not bootstrapped — AMBER, not error). Otherwise
iterate from `data_start_row=6` (per master-excel.schema) and collect
rows where:

- column F (`trend`) starts with `"RED"`, AND
- the row is recent (within last 7 days; if no date column is
  present, every RED row qualifies — date-gating is a Phase 6+
  refinement).

Each row becomes a candidate
`{kind: "content_decay_red", url: A, delta_pct: E, trend: F}`.

### Step 4 — `scan_pending_approvals`

Scan `projects/{slug}/_state/workflows/*.json`. For each file whose
top-level `status == "awaiting_approval"`, build a candidate
`{kind: "pending_approval", run_id, skill, subject:
approval_meta.subject, approver: approval_meta.approver}`.

Implementation: `workflow_runner.list_runs(project_slug,
status_filter="awaiting_approval")`.

### Step 5 — `scan_quick_wins_pending`

Same workbook. If the sheet `quick_wins` is absent, return empty.
Otherwise treat *every* `quick_wins` row as a "pending approval"
candidate (the row exists because Wave 1 quick-wins skill wrote it
and is waiting for the user to greenlight a downstream
`apply-quickwin` action). Candidate:
`{kind: "quick_wins_pending", query: A, url: B, opportunity: H}`.

### Step 6 — `score_and_rank` (heuristic, deterministic)

Each candidate gets a fixed score:

| Candidate kind                              | Score |
|---------------------------------------------|-------|
| `pending_approval` (workflow status)        | 100   |
| `content_decay_red` (RED trend, last 7d)    | 80    |
| `master_task` priority=`CRITICAL`/`HIGH`    | 60    |
| `quick_wins_pending` (row in `quick_wins`)  | 50    |
| `master_task` priority=`MEDIUM`             | 40    |
| `master_task` priority=`LOW` / other        | 20    |

Sort `score DESC`, then by stable secondary key (kind alphabetic,
then row index) to keep output deterministic across runs. Truncate
to `top_k` (clamped to `[1, 10]`).

Each ranked entry maps to a *suggested* downstream skill:

| kind                | suggested skill          |
|---------------------|--------------------------|
| pending_approval    | (resume / approve via workflow_runner) |
| content_decay_red   | content-decay (Phase 6)  |
| master_task         | done-protocol / done-cascade |
| quick_wins_pending  | apply-quickwin (Phase 7) |

### Step 7 — Top-K ranked recommendation list (return value)

Build the structured output:

```python
recommendations = [
    {
      "rank": 1,
      "score": 100,
      "kind": "pending_approval",
      "suggested_skill": "(resume awaiting_approval run)",
      "reason": f"workflow {run_id} ({skill}) waiting on {approver}",
    },
    ...
]
```

### Step 8 — `emit_router_event` (events.jsonl router event)

Single `event_kind=work`, `event_type=skill_whats_next` row per run
(canonical v1.6-Phase-2 H-E). The `task_id` is a synthetic router id
derived from the workflow run_id
hex token (events.schema requires `^T-[0-9]{4,}$`; we map the 4-char
hex token → 5-digit decimal prefixed with `9` so router ids never
collide with master_task `T-NNNN` ids):

```python
from scripts.state import events_writer
hex_token = handle.run_id.split("-")[-1]            # e.g. "1a2b"
synthetic = 90000 + (int(hex_token, 16) % 9999)     # T-9XXXX
task_id = f"T-{synthetic}"
note = render_markdown_summary(recommendations, user_intent)
events_writer.append_work(
    project_id=project_slug,
    event_type="skill_whats_next",
    task_id=task_id,
    note=note,           # required for skill_X canonical (events.schema v1.6-Phase-2 H-E)
    primary_source="manual",
)
```

The `note` field is the same markdown bullet list returned to the
caller — keeping events.jsonl self-describing for archival replay.

### Step 9 — Output structured ranking (return + console)

Render the recommendations to a short markdown bullet list:

```
**whats-next — Top-3 recommendations** (project: {slug})

1. [score 100] pending_approval — workflow {run_id} ({skill}) bekliyor; approve veya reject.
2. [score  80] content_decay_red — https://example.com/page (RED, -42%); content-decay skill çalıştır.
3. [score  60] master_task HIGH — T-0042 "Refresh meta tags"; done-protocol başlat.
```

Return as a string to the caller (stdout if invoked as CLI, function
return value if invoked from a manager). No Excel writes.

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    "recommendations_count": str(len(recommendations)),
    "top_skill": recommendations[0]["suggested_skill"] if recommendations else "(none)",
})
```

**F5 invariant:** every value in `outputs` is a STRING. `int` outputs
break workflow-run.schema validation (Wave 1 lesson, applies forever).

## Heuristic rationale

- **pending_approval=100** — a paused workflow blocks all forward
  progress. Always surface first.
- **content_decay_red=80** — recent RED trend = active loss. Outranks
  optimizations.
- **master_task HIGH=60** — explicit human priority signal.
- **quick_wins_pending=50** — opportunity, not loss; below decay.
- **master_task MEDIUM=40 / LOW=20** — tail.

Ties broken by `(kind, row_id)` for run-to-run stability.

## Router discipline (advisory only)

Whats-next **NEVER** invokes another skill. It reads, scores, and
suggests. The caller (manager session, /whats-next slash, or
SessionStart hook output) is responsible for picking and invoking the
recommended skill. This separation keeps the router bug surface small
(read-only + one event emit) and lets the user override every
recommendation.

## DURUR conditions (4)

Stop and flag the manager — do not patch, do not fall back.

1. `workflow_runner.create_run` fails (schema, lock, or
   workspace_root resolution).
2. `master.xlsx` for the requested `project_slug` does not exist
   (project not initialized — route the user to `init-project`
   instead of returning empty).
3. `PSEO_WORKSPACE_ROOT` env unset AND no `workspace_root` argument
   passed.
4. `events_writer.append_work` raises `EventValidationError` (router
   event itself failed schema — never proceed silently).

Sheet-absent (master_task / content_decay / quick_wins) is **NOT** a
DURUR — those are AMBER (return empty candidate list, continue).

## Cross-references

- Schemas: `schemas/skill-frontmatter.schema.json` (frontmatter),
  `schemas/events.schema.json` (event_kind=work, event_type=manual,
  task_id pattern, note required), `schemas/workflow-run.schema.json`
  (outputs string-typed, F5).
- Cross-modules: `scripts/state/workflow_runner.py`,
  `scripts/state/events_writer.py`, `openpyxl` (read-only).
- Tests: `tests/skills/test_whats_next.py` (5 cases incl. live
  workspace-staging pilot smoke).
- ADRs: ADR-013 (use_when string), ADR-019 (retry_count), ADR-020
  (event_kind=workflow), ADR-021 (`_state/` path).
