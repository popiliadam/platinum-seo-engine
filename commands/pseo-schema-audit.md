---
description: |
  Use when: kullanıcı "schema audit", "structured data", "JSON-LD denetim", "schema.org doğrulama", "rich result eksik", "Product schema hatası", "BreadcrumbList itemListElement", "FAQPage validation" der ya da `/pseo-schema-audit` çağırırsa.
  Also use when: aktif projenin Screaming Frog export'u alındı (`projects/{slug}/sf-exports/{date}/raw/structured_data_all.csv`); sf-import skill çalışmış; on-page-audit / tech-audit ile birlikte triage; rich result eligibility kontrol; opsiyonel DFS content_parsing ile canlı schema cross-validate.
  Do not use when: SF export henüz yok (`sf-import` skill önce, DURUR #1); cannibalization (`/pseo-cannibalization`), quick-wins (`/pseo-quickwin`), tech-audit (`tech-audit` skill, ayrı); master.xlsx yokken (`/pseo-init` önce).
argument-hint: "<project-slug> [--sf-export-date YYYY-MM-DD] [--cross-validate-dfs] [--use-sf-mcp-live] [--strict-parse]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(ls:*), Bash(head:*), Bash(sort:*), Read
model: sonnet
---

# /pseo-schema-audit — Schema Markup Audit

> **Skill:** `skills/discovery/schema-audit/SKILL.md` (Phase 8, aktif). SF JSON-LD blob → schema_audit_transform.py pure compute → master.xlsx#schema sheet write + outputs/reports/{date}-schema-audit.md + events.jsonl provenance row + onay gate.

## 1. Aktif projeyi çöz

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else SF_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/sf-exports"; LATEST=$(ls -1 "$SF_DIR" 2>/dev/null | sort -r | head -1); echo "active=$PROJECT sf_export=${LATEST:-MISSING (önce sf-import)}"; fi; fi`

## 2. Skill chain

`skills/discovery/schema-audit/SKILL.md` 8-step protokol koşar (spec §16.5 MCP discipline):

1. master.xlsx[content_inventory] read (target URLs)
2. SF inbox JSON envelope read (`inbox/sf/{date}-{slug}.json`)
3. (optional) `mcp__dataforseo__on_page_content_parsing` per URL canlı cross-validate (~3 credit/URL, paid)
4. Pure compute: `scripts/discovery/schema_audit_transform.py` (JSON-LD parse, schema.org type validate, gap analysis, statusEnum seed)
5. master.xlsx `schema` sheet write via `scripts/excel/transaction.py`
6. events.jsonl append: `event_kind=provenance + operation=ingest + source.kind=dataforseo_mcp` (DFS varsa) veya `source.kind=sf_csv` (SF only)
7. Onay gate (workflow-run.schema awaiting_approval)
8. `outputs/reports/{date}-schema-audit.md` render via `templates/reports/schema-audit.template.md`

DURUR (6 sentinel): SF export yok / strict_parse=true ile malformed JSON-LD / DFS budget pre-flight FAIL / master.xlsx schema sheet schema mismatch / on-page-audit conflict / inbox envelope schema-version drift.

## 3. Çalıştırma notları

- `--cross-validate-dfs` paid MCP (~3 credit/URL); budget pre-flight `scripts/budget/check_budget.py` zorunlu.
- `--use-sf-mcp-live` (v1.8 NEW; Phase 5 D-SF-11) — skill'in `use_sf_mcp_live=true` flag'ini açar. Aktif olduğunda Step 3'te file CSV yerine `mcp__sf__sf_generate_report(report_name="structured_data_all")` çağrılır (inline 100KB cap; SF MCP /health preflight; AMBER fallback NEVER hard fail). SF GUI + MCP Server açık olmalı (DURUR-orch-1). Default: kapalı (file-based path; regression preservation).
- `--strict-parse` malformed JSON-LD'de `JsonLdParseError` raise (default: drop row, devam).
- Cron `0 9 * * 3` Çarşamba 09:00 UTC report-only mode (HIGH confidence + requires_approval=true).
- `--sf-export-date` belirtilmezse en son `sf-exports/{date}/` dizini default.

## 4. Bağımlılıklar

- Skill: `skills/discovery/schema-audit/SKILL.md` (Phase 8, active)
- Scripts: `scripts/discovery/schema_audit_transform.py` + `scripts/budget/check_budget.py` + `scripts/state/events_writer.py` (`append_provenance`) + `scripts/excel/transaction.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/schema-audit.template.md`
- Rules: `rules/schema-first.md` + `rules/budget-events.md`
- Schemas: `schemas/master-excel.schema.json#schema` + `schemas/dataforseo-endpoint-mapping.schema.json`
- MCP: `mcp__dataforseo__on_page_content_parsing` (optional, paid cross-validate)
- Upstream: `init-project` (master.xlsx) + `sf-import` (`inbox/sf/{date}-{slug}.json`)
