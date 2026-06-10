---
name: robots-policy-audit
description: |
  Use when: kullanıcı "robots.txt audit", "noindex denetimi", "robots policy",
  "noindex deploy edilmiş mi", "disallow + noindex çakışması", "ON_HOLD içerik
  indexleniyor", "robots.txt lint", "site-wide disallow" der ya da
  /pseo-robots-policy çağırır. Free (paid MCP yok) — canlı robots.txt GET +
  SF directives export + master.xlsx okur.
  Also use when: aktif projenin SF export'u alındı
  (projects/{slug}/sf-exports/{date}/raw/directives_all.csv); içerik lifecycle
  (new_content_plan.lifecycle_status) noindex deployment'ı doğrulanacak; bulgular
  master.xlsx#robots_txt'ye RP- prefix'li yazılacak + önerilen robots.txt artifact
  üretilecek (recommendation-only, operator deploy eder).
  Do not use when: faceted-nav / parametre denetimi (facet-nav-audit, ayrı);
  tek-URL retire (content-remediation, ayrı — bu skill SONUCU doğrular, retire
  ETMEZ); SF export yok (sf-import önce); master.xlsx yokken (init-project önce).
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
    description: "sf-exports/{date}/ dir to read; default = latest."
  fetch_live:
    type: boolean
    required: false
    default: true
    description: "Scrapling GET of https://{domain}/robots.txt (read of a public file, no consent gate). On failure → AMBER, continue file-only (never hard fail)."
  sample_header_urls:
    type: integer
    required: false
    default: 5
    description: "Per-lifecycle-state URL count to spot-check X-Robots-Tag headers."
outputs:
  - "master.xlsx#robots_txt"
  - "outputs/reports/{date}-robots-policy-audit.md"
  - "outputs/robots/{date}-robots.proposed.txt"
  - "events.jsonl"
consumes:
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/directives_all.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/internal_all.csv"
  - "new-content-plan:master.xlsx#new_content_plan"
  - "facet-nav-audit:outputs/reports/{date}-facet-nav-audit.md"
  - "init-project:projects/{slug}/project.config.json"
produces:
  - "drift-check"
  - "content-remediation"
triggers:
  manual: ["/pseo-robots-policy"]
  natural_language: |
    "robots.txt audit", "noindex denetimi", "robots policy", "noindex deploy",
    "disallow noindex çakışması", "ON_HOLD indexleniyor", "robots.txt lint"
  hooks: []
mcp_tools:
  required: []
  optional:
    - "mcp__ScraplingServer__get"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# robots-policy-audit — discovery skill (GAP-T3, FREE)

robots.txt / noindex **lifecycle** governance per `rules/tech-seo-governance.md`
**R-131 (governed robots.txt policy)**, **R-132 (noindex deployment path / R-58
deployability)**, **R-133 (noindex/disallow mutual exclusion)**. Today the
`robots_txt` sheet is an SF-issue dump; R-58 (`rules/content-html-discipline.md`)
maps content lifecycle → meta robots but is **undeployable** (the content
pipeline emits body fragments with no `<head>` access → ON_HOLD content is
silently indexable). This skill VALIDATES the deployed reality and emits the
deployment path R-58 lacks.

**Recommendation-only.** The live robots.txt GET is a **read of a public file**
(no consent gate). Every outward change — robots.txt edits, per-page noindex,
X-Robots-Tag headers — is **operator-deployed**. The engine emits findings
(`RP-` rows), a proposed robots.txt artifact, and platform deployment
instructions; it NEVER writes to client infrastructure. The Excel write is behind
the standard `request_approval` gate. Scope fence: content-remediation owns
single-URL retire (R-90/R-91); this skill **validates outcomes, never re-issues a
retire**.

## Outputs

- `master.xlsx#robots_txt` — `RP-NNN` findings (5-col; severityEnum) via
  `scripts/util/sheet_merge.merge_prefixed_rows(..., id_prefix="RP-")` — idempotent,
  preserves sf_projection `R-`, facet-nav-audit `FN-`, hreflang `HF-` rows.
- `outputs/reports/{date}-robots-policy-audit.md` — lint + conflict + lifecycle
  drift tables + proposed robots.txt + deployment instructions.
- `outputs/robots/{date}-robots.proposed.txt` — the proposed robots.txt as a plain
  artifact (plain Write, no template; new `outputs/robots/` subdir — workspace data,
  no engine schema impact). **Recommendation only — operator deploys.**
- `events.jsonl` — `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="robots_txt")`.

## Body protocol

1. **create_run**.
2. **fetch + read** — `fetch_live` (default true): Scrapling GET
   `https://{domain}/robots.txt`. **AMBER fallback (R9 pattern):** on unreachable
   / non-200 the run AMBER-warns and continues file-only with an empty robots.txt
   (the transform emits a MEDIUM "missing robots.txt", never crashes) — this is
   AMBER, NOT a DURUR. Read `directives_all.csv` + `internal_all.csv` from the
   export; read `master.xlsx#new_content_plan` (col C `url_slug`, col K
   `lifecycle_status`); optionally read the facet-nav-audit proposed block.
3. **transform** (pure) —
   ```python
   from scripts.discovery import robots_policy_transform as rpt
   out = rpt.transform(
       robots_txt_text, directives_rows, internal_rows, lifecycle_rows,
       platform, domain, facet_block=facet_block, url_patterns=url_patterns,
   )
   ```
   Lints robots.txt (noindex-line=HIGH, missing-Sitemap=MEDIUM, site-wide
   Disallow=CRITICAL, unknown=LOW), scans R-133 conflicts + R-58 lifecycle drift,
   protects important pages, and builds `proposed_robots_txt` + a platform
   `deployment_instructions` matrix (unverified platforms marked
   `verified: false`).
4. **request_approval** — skill EXIT awaiting_approval.
5. **write_excel** — on approve, `sheet_merge.merge_prefixed_rows(..., id_prefix="RP-",
   writer="robots-policy-audit")`.
6. **write proposed artifact** — plain Write of `out["proposed_robots_txt"]` to
   `outputs/robots/{date}-robots.proposed.txt`.
7. **render_report** — `render_template.py templates/reports/robots-policy-audit.template.md`.
8. **provenance event** + **complete** (string-typed outputs).

## DURUR conditions

Stop and flag the manager (live-fetch failure is AMBER, NOT here).

1. `directives_all.csv` missing (`RobotsDirectivesMissingError`).
2. lifecycle sheet (`new_content_plan`) unreadable (`RobotsLifecycleUnreadableError`).
3. Proposed file would disallow `/` (`RobotsProposedSiteWideBlockError`) — never
   propose a site-wide block.
4. `directives_all.csv` Address column absent (`RobotsDirectivesSchemaDriftError`).
5. `master.xlsx#robots_txt` row schema mismatch on write (`RowSchemaError`).
6. `PSEO_WORKSPACE_ROOT` unset and no `workspace_root` arg.

> **AMBER (NOT DURUR):** live robots.txt fetch unreachable / non-200 → warn,
> continue file-only (mirror tech-audit R9 never-hard-fail).

## Cross-references

- Rules: `rules/tech-seo-governance.md` (R-131 / R-132 / R-133); `rules/content-html-discipline.md` (R-58).
- Transform: `scripts/discovery/robots_policy_transform.py` (`transform`,
  `PLATFORM_DEPLOYMENT_MATRIX`, `RobotsPolicyError` hierarchy).
- Write path: `scripts/util/sheet_merge.py` (`merge_prefixed_rows`, prefix `RP-`).
- Upstream feed: `facet-nav-audit` proposed robots block (optional `facet_block`).
- Schemas: `schemas/master-excel.schema.json#robots_txt`, `#new_content_plan`,
  `schemas/events.schema.json`.
- Template: `templates/reports/robots-policy-audit.template.md`.
- Command: `commands/pseo-robots-policy.md`.

## Discipline checklist

- [x] Recommendation-only — live GET is a public-file READ; all deploys operator-owned (R-131/R-132).
- [x] Free — `budget.uses_paid_mcp=false`; no DFS.
- [x] AMBER never RED on live-fetch failure (R9 pattern); transform tolerates empty robots.txt.
- [x] Schema-first — frontmatter validates; `RP-` rows validate against `master-excel.schema.json#robots_txt`.
- [x] Plugin-agnostik — no slug literals; pure transform; unverified platform channels marked `verified: false` (no fabricated panel paths).
- [x] Scope fence — validates lifecycle outcomes; never re-issues content-remediation's single-URL retire.
- [x] Idempotent write — `merge_prefixed_rows` re-lands the `RP-` namespace; foreign rows preserved.
