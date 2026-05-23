---
name: gbp-audit
description: |
  Use when: kullanıcı "GBP audit", "Google Business Profile kontrol",
  "place_id eksik mi", "business listing kontrol", "harita listing
  audit", "google haritalar profili", "GMB audit" der ya da
  `/pseo-gbp-audit` çağırır. DFS HEAVY ingestion (paid MCP, ~3 credit
  per audit); budget pre-flight ZORUNLU. Local-service profile gate
  şarttır — profilde "local-service" yoksa skip (Step 1 early exit).
  Also use when: project.config.profiles içinde 'local-service' var;
  init-project çalışmış (master.xlsx hazır); aktif projenin GBP listing
  durumu için gap analysis (NAP / categories / photos / hours /
  attributes / posts / Q&A / reviews 8 category triage) gerekiyor;
  bulgular master.xlsx#gbp_audit'a schema-locked 7-column formatta
  yazılacak (statusEnum + severityEnum codebase definition reuse).
  Do not use when: profile != local-service (DURUR #6 skip); master.xlsx
  eksikse init-project önce çalışmalı (DURUR #2); budget exhausted
  (DURUR #1, awaiting_approval); GSC veri ingestion (gsc-pull), tech
  audit (tech-audit), keyword research (dfs-pull), content decay analizi
  (content-decay) gerekiyorsa — her birinin ayrı komutu vardır.
  Otonom GBP API submit YASAK (feedback_indexing_api_consent): bu skill
  sadece audit + rapor üretir, GBP dashboard'una hiçbir şey yazmaz.
version: "1.0"
status: active
category: discovery
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json."
outputs:
  - "master.xlsx#gbp_audit"
  - "outputs/reports/{date}-gbp-audit.md"
  - "events.jsonl"
  - "inbox/dfs/{date}-gbp-listing-{slug}.json"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "init-project:projects/{slug}/project.config.json"
produces:
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-gbp-audit"]
  natural_language: |
    "GBP audit", "Google Business Profile kontrol", "place_id eksik",
    "business listing kontrol", "harita listing audit", "google
    haritalar profili", "GMB audit", "local listing gap", "NAP
    tutarsız", "GBP foto sayısı az"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__business_data_business_listings_search"
  optional:
    - "mcp__ScraplingServer__fetch"
budget:
  uses_paid_mcp: true
  estimated_credits: 3
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# gbp-audit — discovery skill (Phase 5 Wave 1, G-AI-02 closure)

8-step protocol. Steps map 1:1 to `workflow_runner` invocations + the
spec §16.5 MCP discipline + §16.8 budget pre-flight + ADR-016 cost
tracking. Single paid MCP call (`business_data_business_listings_
search`, ~3 credits per run); Scrapling fallback fires only when DFS
returns empty (e.g. business has no claimed GBP listing yet, in which
case the audit emits a HIGH-severity "GBP listing not found" gap row
and the operator action is to claim/create the listing).

**Profile gate is the headline difference from tech-audit.** Before
any paid call, Step 1 reads `project.config.profiles` and exits early
(`status=skipped`) if `"local-service"` is not in the list. e-commerce
or b2b-saas pure plays do not need GBP optimization; running this
skill against them wastes credits and pollutes
`master.xlsx[gbp_audit]` with irrelevant rows.

**Hard constraint: read-only audit.** Per
`feedback_indexing_api_consent`, this skill does NOT submit anything
to the GBP API, GMB dashboard, or any other Google submission
endpoint. It only ingests existing listing data, identifies gaps, and
emits a report. The operator decides what to fix manually.

## Inputs (frontmatter contract)

| Name           | Type    | Default | Notes                                                |
|----------------|---------|---------|------------------------------------------------------|
| `project_slug` | string  | —       | Required. Resolves `projects/{slug}/master.xlsx`.    |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer / tech-audit).

## Outputs (artifacts produced)

- `projects/{slug}/master.xlsx#gbp_audit` — schema-locked 7 cols
  (`audit_id | audit_date | category | gap_description | severity |
  recommended_action | status`). `severity` is severityEnum
  (CRITICAL/HIGH/MEDIUM/LOW); `status` is statusEnum (TODO seed at
  emission; operator transitions via done_protocol).
- `projects/{slug}/outputs/reports/{date}-gbp-audit.md` — human-readable
  summary (per-category gap count + severity histogram + recommended
  next actions).
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance` entry
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=gbp_audit`,
  `cost.credits` populated per ADR-016).
- `projects/{slug}/inbox/dfs/{date}-gbp-listing-{slug}.json` — raw
  business_listings_search payload (drift recovery; paid response).

## 8-Step Body Protocol

> Step names match `steps[*].name` passed to
> `workflow_runner.create_run`. Names are stable identifiers across
> runs.

### Step 1 — `profile_gate` (early-exit before budget pre-flight)

The skill MUST read `project.config.profiles` FIRST. If `"local-
service"` is not in the array, the workflow exits immediately with
`status=skipped` and emits an `event_kind=audit` event noting the
skip reason. NO paid MCP call, NO Excel write.

```python
config = json.loads((project_dir / "project.config.json").read_text())
profiles = config.get("profiles", [])
if "local-service" not in profiles:
    return {"status": "skipped",
            "reason": "Profile 'local-service' missing from project.profiles",
            "project_slug": project_slug}
```

DURUR #6 trigger: `profile_gate` not satisfied → early exit (this is
a graceful skip, not an error; the manager surface treats it as
"audit not applicable").

### Step 2 — `preflight_budget` (§16.8 + ADR-016, MANDATORY)

Identical contract to tech-audit Step 1 but with a lower credit
estimate (single endpoint, conservative MAX ≈ 3 credits):

```python
estimate = 3  # business_data_business_listings_search MAX
envelope = gbp_audit_transform.preflight_budget(
    estimated_credits=estimate,
    project_config_path=project_root / "project.config.json",
    events_path=project_root / "_state" / "events.jsonl",
)
```

If `envelope["exceeded"]` → `BudgetExceededError` → workflow routed
to `awaiting_approval` per spec §10 (DURUR #1). NEVER silently
downgrade or skip the check.

### Step 3 — `create_run`

Open a workflow run shell. State file at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

```python
handle = workflow_runner.create_run(
    skill="gbp-audit",
    project_slug=project_slug,
    steps=[
        {"name": "profile_gate"},
        {"name": "preflight_budget"},
        {"name": "fetch_listing"},
        {"name": "scrapling_fallback"},   # may no-op
        {"name": "transform"},
        {"name": "request_approval"},
        {"name": "write_excel"},
        {"name": "render_report"},
    ],
)
```

### Step 4 — `fetch_listing` (MCP §16.5 — raw inbox first)

```python
raw = mcp__dataforseo__business_data_business_listings_search(
    business_name=config["brand_identity"]["business_name"],
    location=config["brand_identity"]["primary_location"],
    limit=1,
)
inbox_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "dfs"
    / f"{today.isoformat()}-gbp-listing-{project_slug}.json"
)
inbox_path.parent.mkdir(parents=True, exist_ok=True)
inbox_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))

events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__business_data_business_listings_search",
            "response_bytes": len(json.dumps(raw))},
    operation="ingest",
    target_excel_sheet=None,           # ingest: no Excel write yet
    rows_written=0,
    cost={"provider": "dataforseo",
          "credits": 3.0,
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)
```

Auth/networking failure → DURUR #3 (parallel to tech-audit DURUR #2).

### Step 5 — `scrapling_fallback` (conditional — DFS empty result)

```python
if not listing_found(raw):
    # DFS returned no result. The business may have an unclaimed listing
    # on Google Maps but not surfaced via the listings_search endpoint.
    # Fall back to Scrapling against the Google Maps place page.
    scraped = mcp__ScraplingServer__fetch(
        url=f"https://www.google.com/maps/search/{quote(business_name)}",
        wait=2,
    )
    # Parsing scraped HTML is best-effort; if it also yields nothing,
    # we proceed to the transform with listing=None and the gap analysis
    # emits a HIGH-severity "GBP listing not found" row.
```

If Scrapling itself fails (403, anti-bot block) → not a DURUR; the
transform handles `listing=None` by emitting the "listing not found"
gap row. Anti-bot blocks are a known Scrapling failure mode and do
not warrant blocking the audit.

### Step 6 — `transform` (pure compute, gap analysis + severity matrix)

```bash
python3 scripts/discovery/gbp_audit_transform.py \
    --listing-json   inbox/dfs/{date}-gbp-listing-{slug}.json \
    --output-dir     _state/transform/{run_id}/
```

The transform applies the same `_normalize_dfs_response` shape
adapter as tech-audit, then runs the per-category gap analysis:

| Category    | Gap                          | Severity | Recommended action                                    |
|-------------|------------------------------|----------|-------------------------------------------------------|
| nap         | listing not found            | HIGH     | Create or claim GBP listing                           |
| nap         | NAP mismatch with config     | HIGH     | Sync name/address/phone across GBP + site footer      |
| categories  | primary missing              | HIGH     | Set primary category in GBP dashboard                 |
| categories  | < 2 secondary                | MEDIUM   | Add at least 2 relevant secondary categories          |
| photos      | < 3 photos                   | HIGH     | Add ≥ 3 high-quality photos                           |
| photos      | < 10 photos                  | MEDIUM   | Add photos to reach 10+ for healthy listing           |
| hours       | regular hours missing        | HIGH     | Add regular business hours                            |
| hours       | holiday hours missing        | MEDIUM   | Add upcoming holiday hours                            |
| attributes  | profile-relevant attr empty  | MEDIUM   | Fill profile-relevant GBP attributes                  |
| posts       | none last 30d                | LOW      | Publish ≥ 1 GBP post (update / offer / event)         |
| qa          | no Q&A engagement            | LOW      | Seed Q&A with FAQ-aligned questions                   |
| reviews     | response rate < 50 %         | MEDIUM   | Respond to outstanding reviews                        |
| reviews     | avg rating < 4.0             | MEDIUM   | Address negative-review themes via service ops        |

Each row is one `master.xlsx[gbp_audit]` entry with:
- `audit_id` = `gbp-<uuid8>` (the transform owns ID generation)
- `audit_date` = today UTC ISO 8601 date portion
- `status` = `TODO` (seed; operator transitions via done_protocol)

### Step 7 — `request_approval` (skill EXIT awaiting_approval)

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=f"{len(rows)} GBP gap row tespit edildi, master.xlsx#"
            f"gbp_audit'a yazalım mı? (HIGH={n_high}, MEDIUM={n_med}, "
            f"LOW={n_low})",
    step_index=6,
)
# Skill exits here. Operator reviews report + resumes via /pseo-status.
```

### Step 8 — `write_excel` + `render_report` + final provenance event

On resume (operator approves):

```python
transaction.append(
    workbook_path=workspace_root / "projects" / project_slug / "master.xlsx",
    sheet="gbp_audit",
    rows=gbp_audit_rows,
    project_slug=project_slug,
    writer="gbp-audit",
)

render_template(
    "templates/reports/gbp-audit.template.md",
    data={"rows": gbp_audit_rows, "config": config, "today": today},
    out=workspace_root / "projects" / project_slug
        / "outputs" / "reports" / f"{today.isoformat()}-gbp-audit.md",
)

events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={"kind": "dataforseo_mcp", "mcp_server": "dataforseo",
            "mcp_tool": "dataforseo__business_data_business_listings_search",
            "response_bytes": len(json.dumps(raw))},
    operation="project_excel",
    target_excel_sheet="gbp_audit",
    rows_written=len(gbp_audit_rows),
    cost={"provider": "dataforseo",
          "credits": 3.0,
          "budget_key": "project.config.dataforseo.budget_credits_per_day"},
)

workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "gbp_audit_rows": str(len(gbp_audit_rows)),
    "high_count": str(n_high),
    "medium_count": str(n_med),
    "low_count": str(n_low),
    "credits_used": "3",
    "report_path": str(report_path),
    "raw_json": str(inbox_path),
})
```

## DURUR conditions (8)

Stop and flag the manager — do not patch, do not fall back.

1. **Budget pre-flight FAIL** (`check_budget.py` exit 1 OR projected_used
   > budget) → `BudgetExceededError` → `awaiting_approval` per spec §10.
   NEVER silently downgrade. (Step 2)
2. `master.xlsx` missing or schema drift → init-project re-run.
3. `mcp__dataforseo__business_data_business_listings_search` returns
   auth / network / scope error → STOP. (Step 4)
4. DFS response schema drift (envelope shape unrecognized after both
   adapter passes) → `BusinessListingsSchemaDriftError`.
5. `transaction.append` raises `RowSchemaError` (severityEnum violation,
   statusEnum violation, column drift). (Step 8)
6. **Profile gate skip** — `"local-service"` not in `project.config.profiles`
   → `status=skipped`, no paid call, no Excel write. (Step 1; this is
   a graceful exit, not an error.)
7. `workflow_runner.create_run` fails schema validation
   (workflow-run.schema.json).
8. `PSEO_WORKSPACE_ROOT` env unset and no `workspace_root` arg passed.

## Hard Constraint Audit (memory-derived)

This skill MUST honor three feedback memory constraints:

- **`feedback_indexing_api_consent`** — NO autonomous GBP API submit.
  This skill reads only (DFS business_listings_search is a query
  endpoint, not a write endpoint). The recommended_action column tells
  the operator what to change; the operator does the GBP dashboard
  work manually.
- **`feedback_hard_constraints`** — `.mcp.json` byte-byte unchanged
  (the MCP tool reference here lives in SKILL.md, not in the MCP
  config file; F-16 invariant intact).
- **`feedback_ai_disclosure_ban`** — does not apply directly (gbp-audit
  is a discovery skill, not a content production skill; no HTML
  output).

## Cross-references

- Schemas: `schemas/master-excel.schema.json#gbp_audit` (7 cols;
  severityEnum + statusEnum reuse), `schemas/events.schema.json`
  (`source.kind=dataforseo_mcp`, `target_excel_sheet=gbp_audit`,
  `cost.credits` per ADR-016), `schemas/skill-frontmatter.schema.json`
  (this frontmatter).
- Cross-modules (IMPORT-only, not modified):
  `scripts/state/workflow_runner.py`, `scripts/excel/transaction.py`,
  `scripts/state/events_writer.py`, `scripts/budget/check_budget.py`,
  `scripts/reporting/render_template.py`.
- Transform: `scripts/discovery/gbp_audit_transform.py`
  (`preflight_budget`, `transform`, severity matrix constants,
  exception hierarchy).
- Tests: `tests/skills/test_gbp_audit.py` (≥4 cases incl. profile-gate
  skip + gap rows + severity assignment + budget pre-flight).
- Template: `templates/reports/gbp-audit.template.md` (Phase 11 W
  deliverable — runtime render integration; skill can ship without
  the template and emit a minimal report inline).

## Discipline checklist

- [x] Profile-gated — `"local-service"` requirement enforced at Step 1
      BEFORE any paid call. e-commerce / b2b-saas / portfolio pure
      plays skip cleanly with `status=skipped`.
- [x] Read-only audit — NO GBP API submit per
      `feedback_indexing_api_consent`. The skill only queries listings
      and emits a gap report; operator does the GBP dashboard work.
- [x] Budget pre-flight integration — `scripts.budget.check_budget`
      invoked at Step 2 BEFORE any paid call (ADR-016 SSoT).
- [x] Append-only — all events via `events_writer`; per-DFS-call
      provenance event carries `cost.credits` (ADR-016).
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7; gbp_audit rows
      validate against `master-excel.schema.json` 7 cols (severityEnum
      + statusEnum reuse).
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through
      every path.
- [x] severityEnum strict — every emitted row's `severity` is in
      {CRITICAL, HIGH, MEDIUM, LOW}; defensive `_validate_row` runs
      twice (transform + transaction.append).
- [x] statusEnum strict — emitted rows use `status="TODO"` (seed);
      operator transitions via done_protocol (rules cross-link).
- [x] F5: `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
