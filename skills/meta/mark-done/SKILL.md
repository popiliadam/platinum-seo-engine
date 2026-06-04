---
name: mark-done
description: |
  Use when: kullanıcı "task done", "mark complete", "iş bitirildi",
  "completed_work entry", "master_task DONE update" der ya da
  /pseo-mark-done çağırır; master_task primary key task_id resolve +
  completion_evidence reference + completed_work append + master_task
  status DONE update + done_protocol cross-sheet invariant enforce
  (F-02 + F-05 ADR-009 §21.4 DONE cascade).
  Also use when: skill execution sonrası output verify edildi ve audit
  trail için completed_work entry zorunlu; idempotent retry safe (DURUR
  #2 already_done detect); workflow_runner cascade producer'ı olarak
  bir production skill TODO/ONGOING task'ı tamamladığında sondaki
  step (ör. revise-content sonrası R-91 cascade audit close).
  Do not use when: task henüz ONGOING/TODO statüsünde değil (önce
  master-task-sync veya manuel assign gerekli); task already DONE
  (DURUR #2 idempotent fail); allowed_writers gate fail (DURUR #3,
  worker writer_id master_task.allowed_writers'da YOK); protected_columns
  write gerekiyorsa (out of scope, master_task_sync veya human direct
  edit gerekli — DURUR #5 ABORT defensive); completion_evidence eksik
  veya sahte (DURUR #4 AMBER + Süleyman manual confirm, hayali task
  mark-done YASAK Principle 3 anti-cheat).
version: "1.0"
status: wip
category: meta
inputs:
  task_id:
    type: string
    required: true
    description: "master_task primary key (col A). Pattern T-NNNN convention. master_task lookup zorunlu (DURUR #1 yoksa REJECT, hayali task_id mark-done YASAK Principle 3)."
  completion_evidence:
    type: object
    required: true
    description: "Object with required keys: event_id (string, _state/events.jsonl reference), output_path (string, repo-relative artifact path file existence verify); optional keys: manual_note (string, Süleyman serbest metin), metric_impact_json (string JSON, master_task.R metric_impact_json column populate), effort_actual_min (integer, master_task.Q column populate). Eksikse DURUR #4 AMBER + manual confirm."
outputs:
  - "_state/events.jsonl"
  - "outputs/mark-done/{date}-mark-report.json"
consumes:
  - "init-project:master.xlsx[master_task]"
  - "init-project:master.xlsx[completed_work]"
  - "schemas/master-excel.schema.json"
  - "schemas/cross-sheet-invariants.json"
  - "schemas/events.schema.json"
produces: []
triggers:
  manual: ["/pseo-mark-done"]
  natural_language: |
    "task done bitir ve completed_work entry append yap audit trail için",
    "mark complete master_task DONE statüsüne geç done_protocol invariant",
    "iş bitirildi master.xlsx completed_work satırı ekle ve status DONE",
    "completed_work entry append yap F-05 cross-sheet invariant compliance",
    "master_task DONE update done_date populate F-02 dashboard R48 sync"
  hooks: []
  scheduled: []
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

# mark-done — meta skill (Phase 12 Wave 2, W-G5)

DONE cascade closer. Reads `task_id` + `completion_evidence`,
validates master_task status (ONGOING/TODO accept), enforces
allowed_writers gate (worker writer_id = `done_protocol` from
master_task.allowed_writers 4-entity list `[human, dashboard_refresh,
done_protocol, master_task_sync]`), appends a `completed_work` row
(F-12 audit trail, 6 col `[id, task_or_content, url, date, category,
note]`), updates `master_task` row in-place (`status=DONE` +
`done_date` + writer_scope-permitted columns Q/R/S), idempotency
hashes `task_id + evidence_hash` to reject 2x mark-done, and emits a
schema-first override events.jsonl entry (`event_kind=work` +
schema-compliant `event_type` per branch matrix).

This skill is the **only Wave 2 master.xlsx WRITE skill** (W-G4
verify-indexing READ-ONLY, W-G6 monitoring-weekly READ-ONLY). Schema
authority: master_task.allowed_writers gate enforced at the write
boundary; `master_task.protected_columns` 7 col `[task, category,
priority, impact, duration_est_min, assignee, note]` are NEVER touched
(DURUR #5 defensive contract — `transaction.py` already guards but
skill body explicit "ben bunu yapmayacağım" sentinel for static grep).

## Inputs (frontmatter contract)

| Name                  | Type   | Default | Notes                                                                                                |
|-----------------------|--------|---------|------------------------------------------------------------------------------------------------------|
| `task_id`             | string | —       | Required. master_task primary key (col A). Pattern `T-NNNN`. Lookup yoksa DURUR #1.                  |
| `completion_evidence` | object | —       | Required. Keys: `event_id` (string), `output_path` (string), `manual_note` (string optional). DURUR #4 if missing. |

Schema-first override (W-F3 D1 paterni reuse): `inputs[*]` inner
schema has `additionalProperties: false` with whitelist `[type,
required, default, description]`. Object key enumeration cannot live
in a structured `properties` field; it lives in `description` per
schema authority. The README table above documents the contract for
human readers; `Draft7Validator` validates only the 4-field whitelist.

## Outputs (artifacts produced)

- `_state/events.jsonl` — audit append. **Schema-first override**
  (lesson 7+23+31 worker authority): the brief sketched
  `event_type=task_completed` but `events.schema.json` declares
  `event_type` as a closed 10-value enum (F-8 WORK-only):
  `content_new, content_revise, content_remove, tech_fix,
  quickwin_applied, pillar_launch, schema_fix, redirect_deployed,
  backlink_outreach, manual`. `task_completed` is NOT in the enum;
  emitting it would fail `Draft7Validator` and break the F-8
  invariant. Branch matrix:
  - `master_task.primary_source == "quickwin"` AND
    `completion_evidence` contains `cluster + before + after` triplet
    → `event_type=quickwin_applied` (events.schema requires
    `cluster, before, after` on quickwin_applied per schema allOf
    branch).
  - Otherwise (default fallback, W-G1 indexing-ping paterni reuse) →
    `event_type=manual` (free-form work record, schema requires
    `note`; populated with `task_id + completion_evidence summary`).
  `task_completed` is **NEVER** emitted — it is a brief drift, not
  a schema-recognized value.
- `outputs/mark-done/{date}-mark-report.json` — human-readable
  per-run report with `task_id, prior_status, new_status, evidence_hash,
  event_id, completed_work_row_id, allowed_writers_check, idempotency_check`.

## Foundational Principles Enforcement (3-Layer)

The 3 üst-prensip (Phase 10 `rules/content-quality.md#foundational-
principles`) gate this skill end-to-end. No alt-rule (R-01..R-122)
overrides them.

### Principle 1 — Truth-Verifiable Completion (R-27, F-05 cross-sheet)

mark-done MUST refuse to close a task whose completion cannot be
referenced back to a verifiable artifact. `completion_evidence.event_id`
points to an existing `_state/events.jsonl` row (read-back verify);
`completion_evidence.output_path` points to a repo-relative file that
EXISTS on disk (Path.exists() pre-flight check). Layered defense:

- **Layer 1 (pre-write):** event_id exists in events.jsonl (grep
  pre-flight, missing → DURUR #4 AMBER).
- **Layer 2 (file-system verify):** output_path resolves to an
  existing file on disk (rel → repo-root); broken reference →
  DURUR #4.
- **Layer 3 (audit trail F-05):** `completed_work.task_id ⊆ master_task
  WHERE status=DONE` invariant — completed_work row appended ONLY
  AFTER master_task transition succeeds (atomic write, partial
  failure rollback). F-02 cascade implication: dashboard R48 DONE
  count refreshes once master_task DONE row materializes.
- **Failure mode:** P1 verify fail → DURUR #4 AMBER (manual confirm
  Süleyman); hayali task_id (master_task lookup miss) → DURUR #1
  REJECT (Principle 3 anti-fabrication, no event write).

### Principle 2 — Profile-Aware Enforcement (project-config[profile])

Profile-agnostic core flow (mark-done is a meta utility, not a
content-producing skill), with a 5-enum awareness placeholder for
future profile-aware audit hardening. Enum 5-value: `e-commerce` |
`ymyl` | `local-service` | `b2b-saas` | `portfolio`. The placeholder
documents the integration seam without imposing alt-rule logic now:

- `profile == "ymyl"` → completed_work `note` field populated with
  evidence_hash + auditor_id (legal/medical traceability hint;
  not enforced here, deferred to Phase 14+ governance ADR).
- `profile == "e-commerce"` / `local-service` / `b2b-saas` /
  `portfolio` → default flow (no profile-specific gating).

This skill is profile-agnostic by design (DONE cascade is a universal
state-machine close), but the 5-enum awareness is documented for
parity with Wave 1 (W-G1, W-G2, W-G3) and Wave 2 sister skills.

### Principle 3 — AI Suistimal Önlemi (Anti-Fabrication, Anti-Idempotency-Bypass)

Two attack vectors are explicitly closed:

- **Hayali task_id mark-done YASAK.** Worker MUST always perform a
  master_task lookup (DURUR #1); if `task_id` is not present in
  `master_task` col A, REJECT immediately and emit an `event_kind=audit`
  + `severity=error` row with `notes` payload `task_id={task_id}
  not found in master_task`. NEVER auto-create a master_task row to
  satisfy a fictional completion.
- **Idempotency 2x mark-done YASAK.** Worker computes
  `evidence_hash = sha256(task_id + json.dumps(completion_evidence,
  sort_keys=True))` and pre-flights the events.jsonl history: if a
  prior `event_kind=work` + `task_id == input.task_id` + matching
  evidence_hash already exists, REJECT with DURUR #2 (already_done,
  no event write 2x). Re-mark-done with DIFFERENT evidence is also
  rejected since master_task.status == DONE already (the underlying
  state-machine guard).

## Workflow (8 Step)

### Step 1: master.xlsx[master_task] Read + task_id Resolve

Read `master.xlsx[master_task]` (header_row=3, data_start_row=4) via
`scripts/excel/transaction.py` read API or `openpyxl.load_workbook
(read_only=True)`. Locate the row where col A (`task_id`) ==
`{input.task_id}`. If no match → DURUR #1 REJECT (audit event_kind
emitted, no work event).

### Step 2: Status Validate (ONGOING / TODO Accept; DONE Reject)

Read col J (`status`, statusEnum) of the resolved row. Accept
`ONGOING` and `TODO` as valid prior states. Reject `DONE` (DURUR #2
idempotent fail; no completed_work append, no event write 2x, no
master_task touch). `BLOCKED` / `DEFERRED` / `CANCELED` → DURUR #2
soft fail with note (cannot transition to DONE from a non-active
state without a manual override path).

Schema-first note: brief used `in_progress` as the prior state name
but `master-excel.schema.json[definitions/statusEnum]` declares the
enum as `[TODO, ONGOING, EXISTS, DONE, BLOCKED, DEFERRED, CANCELED]`
(ADR-018 hibrit). The skill uses `ONGOING` (schema authority),
`in_progress` is a brief drift.

### Step 3: allowed_writers Gate Check (4-Entity Enumerate)

`master_task.allowed_writers` schema declares 4 entities: `[human,
dashboard_refresh, done_protocol, master_task_sync]`. The mark-done
skill identifies as writer_id `done_protocol` (writer_scope per
schema: "status (J), done_date (L), effort_actual_min (Q),
metric_impact_json (R), work_log_ref (S) — only rows transitioning
to DONE"). transaction.py enforces this gate at the write boundary
(`WriterScopeError` raised on mismatch). Skill body explicitly
declares writer_id when invoking `transaction.update`. If
writer_id not in allowed_writers list → DURUR #3 ABORT.

### Step 4: completed_work Entry Append (F-12 6 col, transaction.append)

`master.xlsx[completed_work]` header_row=4, data_start_row=5,
required_columns 6: `[id, task_or_content, url, date, category, note]`.

Append row via `scripts/excel/transaction.py::transaction.append
("completed_work", row_dict)`:

- `id`: UUID v4
- `task_or_content`: `{input.task_id}` (master_task primary key
  reference, F-05 invariant subset)
- `url`: `{master_task.row.url}` (col E, fall-back empty string for
  meta tasks without a URL anchor)
- `date`: UTC ISO 8601 today (`YYYY-MM-DD`)
- `category`: `{master_task.row.category}` (col F passthrough; falls
  back to `meta` if blank, never invents)
- `note`: `"mark-done evidence_hash={hash}; event_id={event_id};
  output_path={output_path}; manual_note={manual_note or ''}"`
  (Principle 1 Layer 3 audit trail — verifiable references only,
  fabricate yasak)

### Step 5: master_task Row Update (DONE + done_date, transaction.update)

Update the resolved master_task row in-place via
`transaction.update("master_task", {task_id: input.task_id},
{status: "DONE", done_date: "<UTC ISO today>", effort_actual_min:
<from evidence>, metric_impact_json: <from evidence>, work_log_ref:
<event_id>}, writer_id="done_protocol")`.

Allowed columns (writer_scope `done_protocol`): J (status), L
(done_date), Q (effort_actual_min), R (metric_impact_json), S
(work_log_ref).

**protected_columns 7-col YASAK touch (DURUR #5 defensive):**
`task` (B), `category` (F), `priority` (G), `impact` (H),
`duration_est_min` (I), `assignee` (M), `note` (N). transaction.py
guards via `WriterScopeError`; the skill body adds an explicit
"ben bunu yapmayacağım" contract — static grep over the skill body
finds the 7 column names ONLY in the YASAK enumeration block, never
in a write call site.

### Step 6: events.jsonl Append (event_kind=work, Schema-First Override)

Append a single events.jsonl row with required F-9 fields
(`schema_version`, `event_kind`, `event_id`, `timestamp`,
`project_id`, `event_type`, `task_id`).

- `event_kind` = `"work"` (events.schema 4-enum, ADR-020).
- `event_type` = **schema-first override branch matrix** (NEVER
  `task_completed` — brief drift, not in enum):
  - `master_task.primary_source == "quickwin"` AND evidence carries
    cluster+before+after → `event_type="quickwin_applied"` (with
    required `cluster, before, after` per events.schema allOf).
  - Default fallback (W-G1 indexing-ping paterni reuse) →
    `event_type="manual"` (free-form work record, schema requires
    `note`, populated with task_id + completion_evidence summary).
- `task_id` = `{input.task_id}` (F-9 work events require task_id).
- `event_id` = `mark_done_{task_id}_{timestamp_compact}` (per
  events.schema event_id pattern).
- `timestamp` = UTC ISO 8601 RFC3339 (`Z` suffix).
- `project_id` = workspace project_id (config-derived; pattern
  `^[a-z][a-z0-9-]*$`).
- `note` = `"mark-done {task_id} evidence_hash={hash} prior={prior_status}
  new=DONE"` (required on `event_type=manual`).
- `indexing_ping` / other sub-objects → not applicable to mark-done.

### Step 7: Idempotency Hash Check (task_id + evidence_hash)

Before Step 6 emits, the worker computes
`evidence_hash = sha256(input.task_id +
json.dumps(input.completion_evidence, sort_keys=True))[:16]` and
scans `_state/events.jsonl` for a prior `event_kind=work` row whose
`task_id == input.task_id` AND `note` carries the same evidence_hash
(or whose `meta.evidence_hash == evidence_hash`). Match → DURUR #2
REJECT (already mark-done with same evidence; do NOT emit a 2x
event). The Step 2 status guard already covers most cases (DONE
rejects); this hash check is a belt-and-suspenders Layer-2 defense
for race conditions and partial-write recoveries.

### Step 8: Output Report Emit

Write `outputs/mark-done/{YYYY-MM-DD}-mark-report.json` with the
following per-run fields: `task_id, prior_status, new_status,
evidence_hash, event_id, completed_work_row_id,
allowed_writers_check (pass), idempotency_check (pass),
duration_ms, profile_placeholder`. JSON pretty-print, UTF-8, no
trailing newline drift.

## DURUR Conditions (5 koşul)

1. **DURUR #1 — task_id Not Found in master_task.** `master_task`
   col A lookup miss → REJECT (Principle 3 anti-fabrication, hayali
   task_id mark-done YASAK). Emit `event_kind=audit` +
   `audit_action=mark_done_reject` + `severity=error` + `notes={task_id}
   not found in master_task`. NEVER auto-create a master_task row.
   No completed_work append, no master_task write.
2. **DURUR #2 — task already DONE (or non-active state).** Status
   already `DONE` → idempotent fail (no 2x event write, no 2x
   completed_work row). Idempotency hash check (Step 7) is the
   secondary defense. `BLOCKED` / `DEFERRED` / `CANCELED` → soft
   fail (cannot transition without manual override).
3. **DURUR #3 — allowed_writers Gate Fail.** Worker writer_id is NOT
   in `master_task.allowed_writers` 4-entity list (`[human,
   dashboard_refresh, done_protocol, master_task_sync]`) → ABORT
   pre-write. transaction.py raises `WriterScopeError`; the skill
   surfaces this as DURUR #3 with the failed writer_id reported.
4. **DURUR #4 — completion_evidence Missing or Sahte.** Required
   keys `event_id` or `output_path` missing → AMBER + escalate
   (Süleyman manual confirm). event_id not findable in
   `_state/events.jsonl` → AMBER (broken reference, P1 Layer 1
   fail). output_path does not exist on disk → AMBER (P1 Layer 2
   fail). Manual confirmation MUST be recorded in
   `completion_evidence.manual_note` before retry.
5. **DURUR #5 — protected_columns Write Attempt.** Skill code MUST
   NOT touch master_task protected_columns 7-col `[task, category,
   priority, impact, duration_est_min, assignee, note]`. transaction.py
   already guards via `WriterScopeError`, but the skill body adds a
   defensive contract: "ben bunu yapmayacağım — protected_columns 7
   YASAK touch". Static grep sentinel: column names appear ONLY in
   the YASAK enumeration block, never in a write payload.

## WRITE Contract (master.xlsx Skill-Level Enforcement)

Bu skill 1 master.xlsx[completed_work] sheet'e WRITE eder
(transaction.append F-12) + 1 master.xlsx[master_task] row
in-place update (transaction.update with writer_id=done_protocol,
allowed_writers gate enforced).

- `master.xlsx[completed_work]` (F-12, 6 col, transaction.append).
- `master.xlsx[master_task]` (transaction.update, writer_id=done_protocol;
  ONLY columns J/L/Q/R/S; protected_columns 7 YASAK).

READ-ONLY consume (write yapılmaz):

- `schemas/master-excel.schema.json` (F-12 + master_task allowed_writers
  + protected_columns enumeration).
- `schemas/cross-sheet-invariants.json` (F-02 + F-05 done_protocol
  rules).
- `schemas/events.schema.json` (F-8 event_type 10-value enum
  compliance).
- `_state/events.jsonl` (idempotency hash pre-flight scan).

Output artifacts:

- `_state/events.jsonl` (append, F-9 + F-8 enum).
- `outputs/mark-done/{date}-mark-report.json`.

## Schema-First Override Decisions Made (Lesson 7+23+31)

The brief included `event_type=task_completed` as the suggested
events.jsonl payload value. Worker authority (lesson 7+23+31) applies:

1. **Override 1 — `event_type` enum compliance.** `events.schema.json`
   declares `event_type` as a closed 10-value enum (F-8 WORK-only):
   `[content_new, content_revise, content_remove, tech_fix,
   quickwin_applied, pillar_launch, schema_fix, redirect_deployed,
   backlink_outreach, manual]`. `task_completed` is NOT in the enum.
   Branch matrix applied:
   - quickwin path → `event_type=quickwin_applied` (events.schema
     requires `cluster, before, after`).
   - default fallback → `event_type=manual` (W-G1 paterni reuse,
     events.schema requires `note`).
   `task_completed` is NEVER emitted.
2. **Override 2 — `status` enum compliance.** Brief used `in_progress`
   as the prior state label, but `master-excel.schema.json[definitions
   /statusEnum]` declares the enum as `[TODO, ONGOING, EXISTS, DONE,
   BLOCKED, DEFERRED, CANCELED]`. Skill uses `ONGOING` (schema
   authority); `in_progress` is a brief drift.
3. **Override 3 — `inputs.completion_evidence` object key encoding.**
   `skill-frontmatter.schema.json[inputs.*]` inner schema has
   `additionalProperties: false` with whitelist `[type, required,
   default, description]` — no structured `properties` field for
   nested object keys. The expected keys (`event_id`, `output_path`,
   `manual_note`) are enumerated in `description` (W-F3 D1 paterni
   reuse), not as a sub-schema. Schema validates only the 4-field
   whitelist; the contract documentation lives in description prose
   and the README table above.

Manager spot-check expected to confirm these are valid schema-first
overrides, not skill drift (lesson 28 manager mop-up matrix).

## Plugin-Agnostik Disiplin (F-16 Intact)

Skill content'inde proje slug hardcode YASAK. Tüm proje referansları
runtime config / workspace-derived `project_id` üzerinden çözümlenir.
URL örnekleri SKILL.md'de generic placeholder
(`https://example.com/...`) kullanır. `.mcp.json` byte-hash unchanged
invariant: bu skill MCP server tanımı eklemez (mcp_tools.required[]
empty + mcp_tools.optional[] empty).

## Cross-Sheet Invariant Compliance (F-02 + F-05 done_protocol)

This skill is the **enforcement point** for two CRITICAL+HIGH
cross-sheet invariants (`schemas/cross-sheet-invariants.json`):

- **F-02 (CRITICAL)**: `count(master_task WHERE status=DONE) ==
  dashboard.R48`. mark-done's master_task DONE transition is the
  upstream cause of R48 increments; dashboard_refresh recomputes R48
  on the next refresh tick (out of scope here).
- **F-05 (HIGH)**: `completed_work.task_id ⊆ master_task WHERE
  status=DONE`. mark-done's atomic discipline (master_task DONE
  transition AND completed_work append in the same write batch)
  guarantees the subset relationship. Partial failure → both writes
  rollback (transaction.py atomic discipline preserved).

The done_protocol writer name (master_task.allowed_writers entry)
exists precisely for this skill's role — schema authority binds the
2-write atomic batch to this writer identity.

## References

- `schemas/master-excel.schema.json` (master_task allowed_writers +
  protected_columns + completed_work required_columns).
- `schemas/events.schema.json` (event_kind enum 4 values, event_type
  enum 10 values, allOf branch requirements).
- `schemas/cross-sheet-invariants.json` (F-02 + F-05 done_protocol).
- `schemas/skill-frontmatter.schema.json` (Draft7 8-field required).
- `scripts/excel/transaction.py` (atomic + allowed_writers gate +
  protected_columns guard + provenance event_writer one-way import).
- ADR-009 (master.xlsx schema-generated, never hand-edited).
- ADR-018 (statusEnum 7-value hibrit).
- ADR-020 (event_kind=work vs workflow routing).
- ADR-021 (transaction.py append-only-state discipline).
- Lesson 7+23+31 (worker schema-first override authority).
- Lesson 28 (manager mop-up matrix; spot-check expected for the 3
  override decisions above).

## Versioning + Status

- `version: "1.0"` (Phase 12 Wave 2 W-G5 ilk shipping).
- `status: wip` (Phase 13 stabilizasyon sonrası `active` promote).
- Output schema_version: `1.0` (events.jsonl payload + completed_work
  + master_task atomic 2-write batch contract).
- `autonomy.confidence: HIGH` (deterministic state-machine close +
  schema-enforced gates; no LLM creative content).
- `safe_auto_execute: true` (atomic transaction discipline +
  idempotency hash + DURUR 5-koşul defensive gating).
