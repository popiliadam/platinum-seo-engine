---
name: init-project
description: |
  Use when: kullanıcı "yeni proje", "init project", "bootstrap project",
  "{slug} kur", "{slug} ekle", "workspace bootstrap", "yeni proje aç"
  der ya da /pseo-init çağırır.
  Also use when: pilot project workspace iskelet eksik (projects/{slug}/
  yok ya da master.xlsx ve project.config.json mevcut değil); workspace-
  staging'de yeni bir slug ilk kez kuruluyor; idempotent re-bootstrap
  isteniyor (var olan master.xlsx KORUNUR, sadece config refresh).
  Do not use when: project zaten kurulmuş ve sadece veri ingest edilecek
  — sf-import, quick-wins veya başka discovery/ingestion skill kullan;
  mevcut master.xlsx'i schema-uyumsuz şekilde yeniden yaratmak gerekiyor
  — bu yıkıcı, init-project ASLA mevcut master.xlsx'e dokunmaz (F1
  workbook policy + idempotency invariant).
version: "1.0"
status: active
category: meta
inputs:
  project_slug: { type: string, required: true, description: "Lowercase kebab-case (e.g. 'my-project'). Matches projects/{slug}/." }
  domain:       { type: string, required: true, description: "Site URL (https://...). Used as default gsc.site_url." }
  gsc_site_url: { type: string, required: false, description: "Override GSC property URL when distinct from domain. If set, mcp__gsc__list_sites is invoked to verify ownership." }
  market:       { type: string, required: false, default: "TR",    description: "ISO 3166-1 alpha-2 country code." }
  locale:       { type: string, required: false, default: "tr-TR", description: "IETF BCP 47 content locale." }
  profile:      { type: array,  required: false, default: ["local-service"], description: "Composable project profiles (project-config.profiles)." }
outputs:
  - "projects/{slug}/project.config.json"
  - "projects/{slug}/master.xlsx"
  - "projects/{slug}/_state/events.jsonl"
  - "projects/{slug}/_state/workflows/{run_id}.json"
  - "shared/portfolio.json"
consumes:
  - "templates/master-excel.xlsx"
produces:
  - "sf-import"
  - "quick-wins"
triggers:
  manual: ["/pseo-init"]
  natural_language: |
    "yeni proje", "init project", "bootstrap project", "{slug} kur",
    "{slug} ekle", "workspace bootstrap", "yeni proje aç"
  hooks: []
  scheduled: []
mcp_tools:
  optional: ["mcp__gsc__list_sites"]
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# init-project — meta skill (Phase 5 Wave 2, project bootstrap)

10-step protocol that scaffolds a brand-new project pack into the
workspace. Idempotent by design: re-running against an existing project
NEVER mutates `master.xlsx`, only refreshes `project.config.json` and
appends a `portfolio.json` entry if missing. The skill is the entry
point for every new domain; downstream Phase 6+ ingestion skills
(sf-import, quick-wins, pillar-builder) all assume `init-project` ran
first.

## Inputs (frontmatter contract)

| Name           | Type    | Default              | Notes                                                              |
|----------------|---------|----------------------|--------------------------------------------------------------------|
| `project_slug` | string  | —                    | Required. Lowercase kebab-case; matches `projects/{slug}/` dir.    |
| `domain`       | string  | —                    | Required. Project root URL (`https://...`). Default `gsc.site_url`.|
| `gsc_site_url` | string  | (= `domain`)         | Override when GSC property URL differs from `domain`.              |
| `market`       | string  | `TR`                 | ISO 3166-1 alpha-2.                                                |
| `locale`       | string  | `tr-TR`              | IETF BCP 47.                                                       |
| `profile`      | array   | `["local-service"]`  | Composable project profiles (project-config.profiles enum).        |

## Outputs (artifacts produced)

- `projects/{slug}/project.config.json` — schema-valid project pack
  config (project-config.schema.json v1.0).
- `projects/{slug}/master.xlsx` — schema-shaped workbook copied from
  `templates/master-excel.xlsx` (lowercase logical name; F1 workbook
  policy). NEVER overwritten on re-run.
- `projects/{slug}/_state/events.jsonl` — provenance event for
  `operation=project_excel` (kind=`tool_computed`,
  workflow_action=`done`).
- `projects/{slug}/_state/workflows/{run_id}.json` — workflow run state
  (workflow-run.schema.json).
- `shared/portfolio.json` — append-only portfolio registry (slug,
  domain, market, created_at).

## 10-Step Body Protocol

> Step names match `steps[*].name` passed to `workflow_runner.create_run`.
> Names are stable identifiers across runs.

### Step 1 — Validate inputs

`project_slug` must match `^[a-z][a-z0-9-]*$` (project-config.schema
pattern). `domain` must be a non-empty URI. Empty / whitespace / wrong
case → DURUR (do not patch, flag the manager).

### Step 2 — `create_run`

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="init-project",
    project_slug=project_slug,
    steps=[
        {"name": "verify_gsc"},
        {"name": "bootstrap_config"},
        {"name": "copy_master_xlsx"},
        {"name": "register_portfolio"},
        {"name": "request_approval"},
        {"name": "emit_provenance"},
    ],
)
```

The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021).

### Step 3 — `verify_gsc` (optional)

Skipped when `gsc_site_url` not supplied (or domain mode). When set,
call `mcp__gsc__list_sites` and assert the URL appears with at least
`siteOwner` / `siteFullUser` / `siteRestrictedUser` permission. If the
property is absent or auth fails, the step's `output_ref` records the
miss but the run continues — verification is advisory at bootstrap
time (the user may have just registered the property and propagation
is async). DURUR only if the MCP returns an auth/network error
distinct from "not present".

### Step 4 — `bootstrap_config`

Call the existing CLI module via subprocess (no in-process import; the
CLI's `--force` semantics are the contract):

```bash
python3 scripts/state/bootstrap_project.py \
    --project {slug} \
    --domain {domain} \
    --market {market} --locale {locale} \
    [--gsc-site-url {gsc_site_url}] \
    [--profile {profile_i} ...] \
    --out {workspace_root}/projects/{slug}/project.config.json \
    --force
```

Validates the resulting JSON against `schemas/project-config.schema.json`
(Draft7) before returning. Idempotent — `--force` overwrites stale
config, but the file content is fully derived from inputs.

### Step 5 — `copy_master_xlsx` (IDEMPOTENT, F1 policy)

```python
target = workspace_root / "projects" / project_slug / "master.xlsx"
if target.exists():
    # F1 + idempotency invariant: do NOT touch existing master.xlsx.
    # Compute and record SHA-256 for the workflow output_ref so callers
    # can audit that no mutation occurred.
    output_ref = f"master.xlsx#sha256={sha256_of(target)}#preserved"
else:
    template = repo_root / "templates" / "master-excel.xlsx"
    if not template.exists():
        raise BootstrapError("templates/master-excel.xlsx missing")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, target)
    output_ref = f"master.xlsx#sha256={sha256_of(target)}#created"
```

The legacy `{Slug}_MASTER.xlsx` workbook (Turkish display name) is
NEVER touched by this skill. F1 (workbook policy): `master.xlsx`
(lowercase, schema-shaped logical sheet names) is the canonical
artifact for all new ingest flows; the display-name workbook is
read-only legacy data.

### Step 6 — `register_portfolio`

Append the project to `{workspace_root}/shared/portfolio.json` (creates
the file + parent dir if missing). Append-only: existing entries are
preserved; only the new slug entry is added.

```python
shared_dir = workspace_root / "shared"
shared_dir.mkdir(parents=True, exist_ok=True)
portfolio_path = shared_dir / "portfolio.json"
if portfolio_path.exists():
    portfolio = json.loads(portfolio_path.read_text("utf-8"))
else:
    portfolio = {"schema_version": "1.0", "projects": []}
existing = {p["slug"] for p in portfolio["projects"]}
if project_slug not in existing:
    portfolio["projects"].append({
        "slug": project_slug,
        "domain": domain,
        "market": market,
        "created_at": utc_iso_z(),
    })
portfolio_path.write_text(
    json.dumps(portfolio, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
```

### Step 7 — `request_approval`

```python
workflow_runner.request_approval(
    handle.run_id, project_slug=project_slug,
    approver="user",
    subject=(
        f"Config review: project_slug={project_slug}, "
        f"domain={domain}, gsc_site_url={gsc_site_url or domain}. "
        "Onaylıyor musun?"
    ),
    step_index=4,
)
```

Skill EXITS at this point (status=`awaiting_approval`). The user
replies in a fresh session; resume below.

### Step 8 — Resume (`approve` → continue)

```python
workflow_runner.approve(
    handle.run_id, project_slug=project_slug, approver="user",
)
```

### Step 9 — `emit_provenance`

```python
from scripts.state import events_writer
rid = events_writer.next_run_id(project_slug)
events_writer.append_provenance(
    project_id=project_slug,
    run_id=rid,
    source={"kind": "tool_computed"},
    operation="project_excel",
    target_excel_sheet=None,            # bootstrap touches no sheet
    notes="init-project bootstrap completed",
)
```

`source.kind=tool_computed` reflects that bootstrap is not an external
ingest; it is an in-process scaffolding action. `target_excel_sheet`
is null because `master.xlsx` is COPIED from a template, not written
sheet-by-sheet.

### Step 10 — `complete`

```python
workflow_runner.complete(
    handle.run_id, project_slug=project_slug,
    outputs={
        "config_path":     "projects/{slug}/project.config.json",
        "master_xlsx_path":"projects/{slug}/master.xlsx",
        "portfolio_entry": "shared/portfolio.json#projects[{slug}]",
    },
)
```

All `outputs.*` values are STRING-TYPED artifact paths (workflow-run
schema constraint; F5 rule). Numeric counts go in events.jsonl, not
in workflow_run.outputs.

## Idempotency invariant

Re-running `init-project` against an existing project MUST satisfy:

1. `master.xlsx` SHA-256 unchanged (file bytes preserved verbatim).
2. `project.config.json` is regenerated from current inputs (so config
   evolution is supported), but the Excel artifact is sacred.
3. `shared/portfolio.json` gains AT MOST one new entry; duplicate slug
   inserts are no-ops.
4. A new `_state/workflows/{run_id}.json` is created (each invocation
   gets its own audit trail; old runs are not amended).
5. A new provenance event is appended (append-only; never modified).

## DURUR conditions (6)

Stop and flag the manager — do not patch, do not fall back.

1. `project_slug` invalid (fails `^[a-z][a-z0-9-]*$`, contains spaces
   or special chars).
2. `bootstrap_project.py` CLI exits non-zero (validation/IO error).
3. `templates/master-excel.xlsx` missing — cannot bootstrap workbook.
4. `workflow_runner.create_run` fails schema validation
   (workflow-run.schema.json).
5. `PSEO_WORKSPACE_ROOT` env var unset AND no explicit `workspace_root`
   passed.
6. Idempotency violation: existing `master.xlsx` would be mutated
   (caller passed `--force` or template differs and writer attempted
   overwrite). The skill must abort before touching the file.

## Cross-references

- Schemas: `schemas/skill-frontmatter.schema.json` (this file's
  frontmatter contract), `schemas/project-config.schema.json` (the
  config artifact), `schemas/master-excel.schema.json` (the workbook
  shape — referenced by `templates/master-excel.xlsx`),
  `schemas/workflow-run.schema.json`, `schemas/events.schema.json`,
  `schemas/portfolio-config.schema.json` (Phase 14+ richer portfolio).
- Cross-modules: `scripts/state/bootstrap_project.py` (CLI),
  `scripts/state/workflow_runner.py` (state machine),
  `scripts/state/events_writer.py` (provenance),
  `scripts/excel/bootstrap_excel.py` (template generator).
- Template: `templates/master-excel.xlsx`.
- Tests: `tests/skills/test_init_project.py` (5 cases; idempotency,
  schema validity, GSC verify, provenance, portfolio registry).
