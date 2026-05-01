---
name: schema-audit
description: |
  Use when: kullanıcı "schema audit", "structured data", "JSON-LD denetim",
  "schema.org doğrulama", "rich result eksik", "Product schema hatası",
  "BreadcrumbList itemListElement", "FAQPage validation" der ya da
  /pseo-schema-audit çağırır.
  Also use when: aktif projenin SF (Screaming Frog) export'u alınmış
  (`projects/{slug}/sf-exports/{date}/raw/structured_data_all.csv`),
  sf-import skill çalışmış ve `inbox/sf/{date}-{slug}.json` envelope'i
  hazır; on-page-audit / tech-audit ile birlikte triage; rich result
  eligibility kontrol edilecek; opsiyonel olarak DFS content_parsing ile
  canlı schema cross-validate yapılacak.
  Do not use when: SF export henüz yok (sf-import önce çalışmalı, DURUR
  #1); GSC kannibalizasyon (cannibalization), pozisyon 11-20 fırsat
  taraması (quick-wins), title/meta coverage (on-page-audit), tech-seo
  issues (tech-audit) — ayrı discovery skill'leri. Master.xlsx yokken
  çağırma; init-project önce çalışmalı (DURUR #6).
version: "1.0"
status: wip
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json + sf-exports/."
  sf_export_date:
    type: string
    required: false
    description: "SF export date (YYYY-MM-DD); defaults to most recent dir under projects/{slug}/sf-exports/."
  default_status:
    type: string
    required: false
    default: "TODO"
    description: "statusEnum seed value when SF detects type-only (no JSON-LD blob); overridden by per-row gap analysis."
  cross_validate_dfs:
    type: boolean
    required: false
    default: false
    description: "Optional DFS on_page_content_parsing live cross-validate (paid; ~3 credits/URL)."
  strict_parse:
    type: boolean
    required: false
    default: false
    description: "When true, malformed JSON-LD raises JsonLdParseError (default: drop row, keep going)."
outputs:
  - "master.xlsx#schema"
  - "outputs/reports/{date}-schema-audit.md"
  - "events.jsonl"
  - "inbox/sf/{date}-schema-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "sf-import:projects/{slug}/inbox/sf/{date}-{slug}.json"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-schema-audit"]
  natural_language: |
    "schema audit", "structured data audit", "JSON-LD denetim",
    "schema.org doğrulama", "rich result eksik", "Product schema",
    "BreadcrumbList itemListElement", "FAQPage validation",
    "Article headline missing"
  hooks: []
  scheduled:
    - cron: "0 9 * * 3"
      mode: "report-only"
mcp_tools:
  required: []
  optional:
    - "mcp__dataforseo__on_page_content_parsing"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# schema-audit — discovery skill (Phase 7 Wave 2)

10-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 8-step MCP discipline. Raw SF data drift recovery is
mandatory: the parsed SF structured-data export is dropped into
`inbox/sf/` *before* any transform runs, so a transform bug never costs
us the upstream payload.

This skill follows the **convention authority** established by
`skills/discovery/cannibalization/SKILL.md` (Phase 7 Wave 1) +
`skills/ingestion/sf-import/SKILL.md` (Phase 5 Wave 2) +
`skills/discovery/quick-wins/SKILL.md` (Phase 5). The 10-step protocol
shape, raw inbox discipline, URL normalization (D-03), DURUR + flag
rule, and provenance event format are reused verbatim — only the domain
content (target sheet, transform script, schema-validity heuristic)
changes. Deviate only with an ADR.

## Inputs (frontmatter contract)

| Name                  | Type    | Default | Notes                                                              |
|-----------------------|---------|---------|--------------------------------------------------------------------|
| `project_slug`        | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.                   |
| `sf_export_date`      | string  | latest  | Pins which SF export under `projects/{slug}/sf-exports/{date}/`.    |
| `default_status`      | string  | "TODO"  | statusEnum seed; per-row gap analysis can override per row.         |
| `cross_validate_dfs`  | boolean | false   | When true, runs DFS on_page_content_parsing cross-validate (paid).  |
| `strict_parse`        | boolean | false   | Strict JSON-LD parse mode (raise on malformed blob).                |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#schema` — one row per (schema_type,
  scope) tuple (5 cols, schema-locked).
- `projects/{slug}/outputs/reports/{date}-schema-audit.md` —
  human-readable summary (top types, BLOCKED conflicts, missing-required
  hotspots).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  entries (`source.kind=sf_csv` always, plus `dataforseo_mcp` when the
  optional cross-validate branch fires; `target_excel_sheet=schema`).
- `projects/{slug}/inbox/sf/{date}-schema-{slug}.json` — parsed SF
  structured-data envelope (drift recovery; flat `{"rows":[...]}` shape).
- (optional) `projects/{slug}/inbox/dfs/{date}-content_parsing-schema-{slug}.json`
  — DFS payload when cross-validate ran.

## 10-Step Body Protocol

> Each step name must match the `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across runs.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021, ADR-019).

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="schema-audit",
    project_slug=project_slug,
    steps=[
        {"name": "validate_sf_inputs"},
        {"name": "parse_sf_structured_data"},
        {"name": "transform"},
        {"name": "optional_dfs_cross_check"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 2 — `validate_sf_inputs` (DURUR #1 gate)

Resolve the SF export dir. If `sf_export_date` is omitted, pick the
most recent date subfolder under `projects/{slug}/sf-exports/`.
Required source: `structured_data_all.csv` (or its normalized variant
from sf-import). Missing → DURUR #1.

```python
sf_root = workspace_root / "projects" / project_slug / "sf-exports"
if not sf_root.is_dir():
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="validation_error",
        message="sf-exports/ missing — run sf-import first",
        step_index=0,
    )
    raise SystemExit(2)  # DURUR #1
```

### Step 3 — `parse_sf_structured_data` (raw → drift-recoverable JSON)

Load the SF structured-data CSV via `schema_audit_transform.load_sf_csv`,
or pull the `structured_data_all` rows out of the sf-import envelope at
`inbox/sf/{date}-{slug}.json`. Drop the parsed flat envelope into
`inbox/sf/{date}-schema-{slug}.json` BEFORE the transform runs.

```python
from scripts.discovery import schema_audit_transform as sat
sf_csv = sf_root / sf_export_date / "raw" / "structured_data_all.csv"
flat_envelope = sat.load_sf_csv(sf_csv)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "sf"
    / f"{today.isoformat()}-schema-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(
    json.dumps(flat_envelope, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

### Step 4 — `transform`

Pure compute via `scripts/discovery/schema_audit_transform.py`:

```bash
python3 scripts/discovery/schema_audit_transform.py \
    --raw-sf inbox/sf/{date}-schema-{slug}.json \
    [--strict-parse] \
    --output-dir _state/transform/{run_id}/
```

Produces a JSON array (`schema`) shaped to the master-excel schema
(5 columns: schema_type, status, location, scope, remaining_work). URL
normalization (D-03) is applied here, not at parse time, so the inbox
copy is byte-faithful to the SF source. The transform is idempotent:
same input → byte-identical output.

If the parsed instance count is 0 (no JSON-LD blob, no Type-only
fallback), the skill SKIPS write_excel and emits a "no schema markup
detected" notice (DURUR #9 — clean exit, not error).

### Step 4b — `optional_dfs_cross_check` (only when `cross_validate_dfs=true`)

When the optional branch is invoked, **first** run the budget
pre-flight via `scripts/budget/check_budget.py` against the project's
24h DFS credit total.

- Budget pre-flight PASS → fetch DFS `on_page_content_parsing` per URL,
  persist raw to `inbox/dfs/{date}-content_parsing-schema-{slug}.json`,
  re-run `transform(raw_sf, raw_dfs)` so `remaining_work` is decorated
  with "(DFS confirmed live)" / "(DFS did not echo live — verify
  rendering)" notes.
- Budget pre-flight FAIL → **DURUR #4** (`BudgetExceededError`). Do NOT
  silently fall back to SF-only. The skill exits with
  `awaiting_approval`; the manager must explicitly authorize either
  raising the budget cap or skipping the cross-check (recorded as an
  ADR), then resume.

```python
from scripts.discovery import schema_audit_transform as sat
if cross_validate_dfs:
    estimate = sat.estimate_credits(url_count=len(distinct_urls))
    envelope = sat.preflight_budget(
        estimated_credits=estimate,
        project_config_path=str(project_root / "project-config.json"),
        events_path=str(project_root / "_state" / "events.jsonl"),
    )
    # PASS → fetch DFS, persist raw, re-run transform with raw_dfs.
```

The default frontmatter declaration is `uses_paid_mcp: false`,
`estimated_credits: 0`. The optional branch is the **only** path that
incurs DFS credits, and it is gated by an explicit input + budget
pre-flight (Q-W-A4-01 lesson — no per-call/per-url leakage in
frontmatter).

### Step 5 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(rows)} schema audit satırı bulundu, master.xlsx#schema'ya yazalım mı?",
    step_index=4,
)
# Skill exits here. The user replies in a fresh session; resume below.
```

### Step 6 — Resume (`approve` → continue)

```python
workflow_runner.approve(handle.run_id, project_slug=project_slug,
                        approver="user")
```

### Step 7 — `write_excel` (atomic, schema-validated)

Single `transaction.append` call for the schema sheet. Goes through the
single approved write path with backup, lock, schema validation, and
post-write provenance event emission. **Note:** the transform module
itself does NOT import `scripts.excel.transaction` — only the skill
orchestrator layer does (cross-module IMPORT discipline).

```python
from scripts.excel import transaction
transaction.append(
    workbook_path=workspace_root/"projects"/project_slug/"master.xlsx",
    sheet="schema",
    rows=schema_rows,
    project_slug=project_slug,
    writer="schema-audit",
)
```

### Step 8 — `render_report`

`render_template.py templates/reports/schema-audit.template.md
data.json` → `outputs/reports/{date}-schema-audit.md`. Variables:
`$project_slug`, `$date`, `$row_count`, `$blocked_count`, `$todo_count`,
`$exists_count`, `$done_count`, `$top_schema_type`,
`$top_remaining_work`, `$report_summary`.

### Step 9 — Provenance event

One provenance entry for the SF parse (always), plus one for DFS when
the optional branch fires. Both target `target_excel_sheet=schema`.

```python
from scripts.state import events_writer
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        "kind": "sf_csv",
        "source_folder": str(sf_root.relative_to(workspace_root)),
        "row_count": meta["sf_row_count"],
    },
    operation="project_excel",
    target_excel_sheet="schema",
    rows_written=len(schema_rows),
)
# Optional: when DFS branch ran, second event with kind="dataforseo_mcp"
# + cost.credits = estimate, target_excel_sheet=schema (same sheet).
```

### Step 10 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "row_count": str(len(schema_rows)),
    "blocked_count": str(sum(1 for r in schema_rows if r["status"] == "BLOCKED")),
    "todo_count":    str(sum(1 for r in schema_rows if r["status"] == "TODO")),
    "report_path":   str(report_path),
    "raw_inbox":     str(inbox_path),
})
```

## Schema-validity heuristic (transform domain)

For each parsed JSON-LD / microdata instance:

```
1. Coerce @type → schema_type (lists → first non-empty entry).
2. If raw @type was a list with ≥2 distinct entries → status=BLOCKED
   (schema.org allows multi-type, but mixed top-level types break rich
    results in practice).
3. Otherwise look up _REQUIRED_PROPS[schema_type]:
     - Required props all present → check _RECOMMENDED_PROPS:
         - All recommended present → status=DONE.
         - Some missing            → status=EXISTS, remaining_work names them.
     - Required missing            → status=TODO, remaining_work names them.
   Type-only fallback (presence detected, no blob) → status=EXISTS with
   "verify required props" remaining_work.
4. DFS cross-validate (when present) only DECORATES remaining_work
   ("(DFS confirmed live)" / "(DFS did not echo live)") — it never
   silently flips a status.
5. Aggregate: when ≥3 URLs share the same (schema_type, status,
   remaining_work) signature, collapse into a single site-wide row
   whose location is "{N} URLs" and scope is "site-wide".
```

### Required-prop minimums

```
Article / NewsArticle / BlogPosting   headline, author, datePublished
Product                               name, image, offers
Organization                          name, url
LocalBusiness                         name, address, telephone
BreadcrumbList                        itemListElement
FAQPage                               mainEntity
Recipe                                name, recipeIngredient, recipeInstructions
Event                                 name, startDate, location
Person                                name
WebSite / WebPage                     name (+ url for WebSite)
```

Extend via ADR rather than silently drift.

## URL normalization (D-03 invariant)

Every URL in this skill flows through `_normalize_url` (mirrors
`cannibalization_transform.normalize_url` semantics) so cross-sheet
joins (cannibalization ↔ schema, on_page_audit ↔ schema) remain
bit-stable. Lowercase scheme+host, IDN→punycode, strip default ports,
strip trailing slash (root excluded), drop fragment, drop tracking
params, sort remaining query keys.

## DURUR conditions (8)

Stop and flag the manager — do not patch, do not fall back.

1. **SF data missing** — `projects/{slug}/sf-exports/` empty OR
   `structured_data_all.csv` absent OR sf-import envelope unreadable.
   STOP, surface "run sf-import first".
2. `master.xlsx#schema` column count or names don't match schema
   (`schemas/master-excel.schema.json#schema`, 5 cols). STOP, schema-first
   violation.
3. JSON-LD parse error in `strict_parse=true` mode → `JsonLdParseError`
   bubbles up, transform aborts. (Default `strict_parse=false` mode
   silently drops malformed rows; the inbox copy is the durable witness.)
4. Optional DFS cross-validate invoked AND `preflight_budget()` FAILs
   → `BudgetExceededError`. STOP, awaiting_approval; do NOT fall back to
   SF-only.
5. `workflow_runner.create_run` fails schema validation
   (`schemas/workflow-run.schema.json`). STOP.
6. `PSEO_WORKSPACE_ROOT` env var unset and no explicit `workspace_root`
   arg passed to `workflow_runner` / `events_writer`. STOP, surface to
   manager.
7. `transaction.append` raises `RowSchemaError` (e.g., `status` not in
   statusEnum, column tuple drift). STOP.
8. statusEnum lookup drift — emitted status not in the canonical 7
   values (`TODO`/`ONGOING`/`EXISTS`/`DONE`/`BLOCKED`/`DEFERRED`/`CANCELED`).
   STOP. Self-checked at row-emission time inside `_validate_row_shape`.

(Adjacent clean-exit case, NOT a DURUR: when transform yields 0 schema
rows the skill goes straight to `complete` with `row_count="0"` and
skips write_excel + render_report — same shape as cannibalization
DURUR #7 clean exit.)

## Cross-references

- Schemas: `schemas/master-excel.schema.json` (schema sheet, 5
  required_columns + `#/definitions/statusEnum`),
  `schemas/events.schema.json` (`source.kind=sf_csv|dataforseo_mcp`,
  `target_excel_sheet=schema`),
  `schemas/sf-required-reports.schema.json` (canonical_name
  `structured_data_all`),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`,
  `scripts/excel/transaction.py`, `scripts/state/events_writer.py`,
  `scripts/budget/check_budget.py`,
  `scripts/reporting/render_template.py`.
- Transform: `scripts/discovery/schema_audit_transform.py` (pure;
  zero `transaction.append` direct calls, zero
  `scripts.excel.transaction` imports).
- Tests: `tests/skills/test_schema_audit.py` (≥6 cases incl. budget +
  smoke E2E + statusEnum coverage).
- Template: `templates/reports/schema-audit.template.md`.

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade
      (exception: 0-row case is a clean no-op exit, mirrors
      cannibalization DURUR #7).
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7. Budget block:
      `uses_paid_mcp: false`, `estimated_credits: 0` only;
      `_per_call`/`_per_url` keys ABSENT (Q-W-A4-01 lesson).
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path; transform has 0 hardcoded slug words.
- [x] ADR-013: `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] Cross-module IMPORT discipline — `transaction` /
      `workflow_runner` / `events_writer` / `check_budget` are imported,
      never modified from this skill. Transform has 0 imports from
      `scripts.excel.transaction`.
- [x] F1: write target is `master.xlsx` (lowercase, schema-shaped).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] Append-only state — `events.jsonl` only grows; no in-place rewrite.
- [x] statusEnum strict — every emitted row's status is in the canonical
      7-value enum, validated at row-emission time.
