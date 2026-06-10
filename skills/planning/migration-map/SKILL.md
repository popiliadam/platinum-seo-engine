---
name: migration-map
description: |
  Use when: kullanıcı "migration map", "redirect map", "site taşıma", "URL
  değişikliği", "301 haritası", "domain taşıma", "redirect planı", "eski URL'leri
  yeni URL'lere yönlendir", "migration verify", "redirect doğrula" der ya da
  /pseo-migration-map çağırır. Free (paid MCP yok) — SF export + master.xlsx okur.
  Also use when: bir site/CMS/domain taşıması planlanıyor; eski-site SF crawl
  inventory'si alındı; operatör bir url-mapping.csv (+ opsiyonel regex
  mapping-rules.json) sağladı; bulgular master.xlsx#redirect_404'e key=url merge ile
  yazılacak (plan modu) veya post-launch crawl ile doğrulanacak (verify modu); 301
  haritası + sunucu-config snippet'leri + faz-geçit checklist raporda üretilecek
  (recommendation-only, operatör deploy eder).
  Do not use when: tek-URL retire/sunset (content-remediation, R-90/R-91, ayrı —
  bu skill BULK harita yapar); SF export yok (sf-import önce, DURUR); robots.txt/
  noindex denetimi (robots-policy-audit); master.xlsx yokken (init-project önce);
  GSC'ye sitemap submit / Change-of-Address (operatör-only, motor YAZMAZ).
version: "1.0"
status: wip
category: planning
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json + sf-exports/ + migration/."
  mode:
    type: string
    required: true
    description: "Çalışma modu — biri: \"plan\" (eski-site inventory + seed'den 301/410 haritası üret, redirect_404'e yaz) | \"verify\" (post-launch crawl'dan R-136 doğrulaması). Geçersiz değer → DURUR."
  mapping_csv_path:
    type: string
    required: false
    description: "Operatör seed dosyası; default = en son projects/{slug}/migration/*-url-mapping.csv (kolonlar old_url,new_url,action). Opsiyonel projects/{slug}/migration/*-mapping-rules.json regex kuralları (schemas/migration-mapping.schema.json) yanında okunur."
  sf_export_date:
    type: string
    required: false
    description: "sf-exports/{date}/ dir; plan modu = eski-site crawl, verify modu = post-launch crawl; default = en son export."
  homepage_collapse_pct:
    type: number
    required: false
    default: 5
    description: "301 hedeflerinin anasayfaya çökme eşiği (%); aşılırsa HIGH bulgu (R-134 homepage-collapse guard)."
outputs:
  - "master.xlsx#redirect_404"
  - "outputs/reports/{date}-migration-map.md"
  - "events.jsonl"
consumes:
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/internal_all.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/redirect_chains.csv"
  - "sf-import:projects/{slug}/sf-exports/{date}/raw/response_codes_all.csv"
  - "gsc-pull:master.xlsx#gsc_performance"
  - "init-project:projects/{slug}/project.config.json"
produces:
  - "drift-check"
  - "master-task-sync"
  - "indexing-ping"
triggers:
  manual: ["/pseo-migration-map"]
  natural_language: |
    "migration map", "redirect map", "site taşıma", "URL değişikliği",
    "301 haritası", "domain taşıma", "migration verify", "redirect doğrula"
  hooks: []
mcp_tools:
  required: []
  optional:
    - "mcp__gsc__list_sitemaps"
    - "mcp__gsc__get_sitemap"
    - "mcp__gsc__index_inspect"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# migration-map — planning skill (GAP-T4, FREE)

Site-migration / redirect-map playbook per `rules/tech-seo-governance.md`
**R-134 (Migration Redirect-Map Contract)**, **R-135 (Migration Phase Gate)**,
**R-136 (Post-Migration Verification & Rollback Watch)**. SF's `redirect_chains`
is a Tier-1 export collected on every crawl but consumed by nothing; this skill
turns it (plus the old-site inventory + an operator mapping seed) into a
one-to-one redirect map and a post-launch verification.

**Recommendation-only (R-135).** The engine produces the map + the verification;
the **operator deploys** (htaccess/nginx/platform snippets are recommendations,
emitted as report text). The engine NEVER writes to client infrastructure, NEVER
calls `mcp__gsc__submit_sitemap`, and NEVER auto-triggers Change-of-Address (no
API exists — GSC UI is operator-only). The Excel write is behind the standard
`request_approval` gate. **Scope fence:** content-remediation owns single-URL
retire (R-90/R-91); this skill handles the **BULK** map and never re-issues a
single-URL retire.

## Modes (input `mode`, enum-in-description per W-F3 D1)

- **`plan`** — read the old-site inventory + the operator seed, expand explicit
  pairs + ordered regex rules over the full inventory, lint, and write
  `redirect_404` rows (`status: TODO`). A `mode` value that is neither `plan`
  nor `verify` → **DURUR** (the skill refuses with an explanation, never guesses).
- **`verify`** — read the post-launch crawl (`redirect_chains.csv` +
  `response_codes_all.csv`), confirm each map row resolves old → single-hop 301 →
  200, and update matching `redirect_404` rows' `status` (`DONE` for verified;
  rows stay `TODO`/`ONGOING` otherwise). R-136 cadence (T+1d / T+7d / T+30d) is a
  report checklist, not a scheduler.

## Outputs

- `master.xlsx#redirect_404` — `{url, inlinks, action, target_url, status}` rows
  (action carries `301`/`410` per R-91 convention; status = statusEnum). Written
  via `scripts/util/sheet_merge.merge_keyed_rows(..., key_column="url")` —
  idempotent re-runs replace the same `url` keys in place and preserve foreign
  rows (sf_projection's own `redirect_404` rows survive). **sf-import's
  `transaction.replace` wipes the sheet → re-run after every sf-import.**
- `outputs/reports/{date}-migration-map.md` — map stats + unmapped triage table +
  lint findings + server-config snippet section + the R-135 phase-gate checklist
  (incl. the Change-of-Address line when the domain changes) + (verify) the
  verification table + rollback recommendation.
- `events.jsonl` — `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="redirect_404")`.

## Body protocol

Mirrors tech-audit's shape minus the budget pre-flight (this skill is free).

1. **create_run** — `workflow_runner.create_run(skill="migration-map", mode=...)`.
2. **read inputs** — resolve `sf-exports/{date}/raw/`; **plan:** read
   `internal_all.csv` (Address + Inlinks) + the seed `*-url-mapping.csv`
   (old_url,new_url,action) + optional `*-mapping-rules.json` (validated against
   `schemas/migration-mapping.schema.json`); read `master.xlsx#gsc_performance`
   (url/clicks, read-only) for traffic-critical detection. **verify:** read
   `redirect_chains.csv` + `response_codes_all.csv` from the post-launch export.
3. **transform** (pure) —
   ```python
   from scripts.planning import migration_map_transform as mmt
   # plan
   out = mmt.build_map(inventory_rows, mapping_pairs, mapping_rules, gsc_rows,
                       homepage_collapse_pct=homepage_collapse_pct)
   # verify
   res = mmt.verify_map(redirect_rows, redirect_chain_rows, response_rows)
   ```
   `build_map` lints loops/self-redirects (RED), chains > 3 hops, homepage-collapse
   %, traffic-critical-unmapped, duplicate-target fan-in — and **never silently
   drops** an old URL (every one is a row or listed in `unmapped`, R-134).
   `verify_map` flags 302/307-leaks, chains > 3 hops, 4xx/5xx regressions, and
   redirect-to-homepage drift (R-136), with a `RedirectChainsSchemaDriftError`
   guard on column drift.
4. **request_approval** — `request_approval(...)` ("N redirect satırı
   master.xlsx#redirect_404'e yazılsın mı?"); skill EXIT awaiting_approval.
5. **write_excel** — on approve, `sheet_merge.merge_keyed_rows(master_xlsx,
   "redirect_404", out["redirect_rows"], key_column="url", run_id=..., project_slug=...,
   writer="migration-map")` (plan), or update matching rows' `status` (verify).
6. **render_report** — `render_template.py templates/reports/migration-map.template.md`
   → `outputs/reports/{date}-migration-map.md` (server-config snippets +
   phase-gate checklist as recommendation text).
7. **provenance event** — `append_provenance(source.kind="sf_csv", operation="project_excel", target_excel_sheet="redirect_404", rows_written=...)`.
8. **deployment confirmation (operator-gated)** — only after the **operator
   explicitly confirms** the redirects are deployed, emit
   `events_writer.append_work(event_type="redirect_deployed", task_id=...)`
   (`event_kind=work`). This is **gated on the approval/confirm step and is
   **never autonomous**** — the engine does not deploy and does not assume
   deployment. Until confirmed, rows stay `TODO`.
9. **complete** — `workflow_runner.complete(...)` with string-typed outputs.

## DURUR conditions

Stop and flag the manager — do not patch, do not fabricate.

1. `mode` is neither `plan` nor `verify` (refuse with explanation — never guess a mode).
2. plan: `internal_all.csv` (inventory) missing — run sf-import first.
3. plan: the operator mapping seed (`*-url-mapping.csv`) absent — a bulk map needs
   the operator's old→new decisions (an LLM session may DRAFT the seed; the engine
   does not invent targets).
4. verify: `redirect_chains.csv` missing, or its Address column absent
   (`RedirectChainsSchemaDriftError`) — re-export with default columns.
5. `master.xlsx#redirect_404` row schema mismatch on write (`RowSchemaError`).
6. Loops / self-redirects in the proposed map (`lint.verdict == "RED"`) — surface
   for operator resolution before any deploy.
7. `PSEO_WORKSPACE_ROOT` unset and no `workspace_root` arg.

## Cross-references

- Rules: `rules/tech-seo-governance.md` (R-134 / R-135 / R-136); `rules/content-update-discipline.md` (R-91 single-URL 301/410 — the content-remediation scope fence).
- Transform: `scripts/planning/migration_map_transform.py` (`build_map`, `verify_map`,
  `MigrationMapError`, `RedirectChainsSchemaDriftError`).
- Write path: `scripts/util/sheet_merge.py` (`merge_keyed_rows`, key=`url`).
- Schemas: `schemas/master-excel.schema.json#redirect_404` (5-col + statusEnum),
  `schemas/migration-mapping.schema.json` (optional regex rules),
  `schemas/events.schema.json` (`redirect_deployed` work event — enum-legal, no change).
- Template: `templates/reports/migration-map.template.md`.
- Command: `commands/pseo-migration-map.md`.
- Downstream: `master-task-sync` (optional follow-up tasks via `primary_source: "redirect_404"`),
  `indexing-ping` (sitemap-submit recommendation — operator-consent gated), `drift-check`.

## Discipline checklist

- [x] Recommendation-only — engine never deploys, never submits sitemaps, never auto Change-of-Address (R-135).
- [x] Free — `budget.uses_paid_mcp=false`; GSC reads are cost-0 and optional.
- [x] Never silently drops a URL — every old URL is a redirect row or listed unmapped (R-134).
- [x] Schema-first — frontmatter validates against `skill-frontmatter.schema.json`;
      `redirect_404` rows validate against `master-excel.schema.json#redirect_404`.
- [x] Plugin-agnostik — no slug literals; pure two-mode transform.
- [x] Idempotent write — `merge_keyed_rows` replaces the same `url` keys in place; foreign sf_projection rows preserved.
- [x] `redirect_deployed` event gated on operator confirm — never autonomous (append-only via events_writer).
- [x] Scope fence — BULK map only; content-remediation owns single-URL retire (R-90/R-91).
