---
description: |
  Use when: kullanıcı "cannibalization", "kannibalizasyon", "keyword conflict", "URL çakışması", "aynı keyword'e iki sayfa", "anahtar kelime çakışması", "iki sayfam aynı sorguya çıkıyor", "intent split" der ya da `/pseo-cannibalization` çağırırsa.
  Also use when: aktif projenin GSC verisi mevcut (gsc-pull önce çalışmış); aynı sorguda ≥2 URL ranking; quick-win / content-decay ile birlikte triage; F-08 cross-sheet invariant kontrolünden sonra cannibalization sheet doldurulacak.
  Do not use when: tek URL audit (`on-page-audit` skill), pozisyon 11-20 fırsat (`/pseo-quickwin`), tek sayfa decay (`/pseo-content-decay`), tech-audit (`tech-audit` skill); master.xlsx yokken (`/pseo-init` önce).
argument-hint: "<project-slug> [--days-back 28] [--min-impressions 10]"
allowed-tools: Bash(jq:*), Bash(python3:*), Read
model: sonnet
---

# /pseo-cannibalization — Query Cannibalization Detection

> **Skill:** `skills/discovery/cannibalization/SKILL.md` (Phase 7 W1, aktif). GSC raw `search_analytics` query×page pivot → cannibalization_transform.py pure compute → master.xlsx#cannibalization sheet write + outputs/reports/{date}-cannibalization.md + events.jsonl provenance row + onay gate.

## 1. Aktif projeyi çöz

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT days_back=${2:-28} min_impressions=${3:-10}"; fi; fi`

## 2. Skill chain

`skills/discovery/cannibalization/SKILL.md` 10-step protokol koşar (spec §16.5 8-step MCP discipline):

1. project-config.gsc.site_url consume
2. `mcp__gsc__search_analytics` raw 5000-row query×page pivot (last N day, default 28)
3. Inbox raw JSON drop: `inbox/gsc/{date}-search_analytics-cannibalization-{slug}.json` (drift recovery — transform bug korumalı)
4. Pure compute: `scripts/discovery/cannibalization_transform.py` (query overlap matrix + URL conflict detection + min_impressions K threshold filter + intent split heuristic)
5. master.xlsx `cannibalization` sheet write via `scripts/excel/transaction.py`
6. events.jsonl append: `event_kind=provenance + operation=ingest + source.kind=gsc_mcp`
7. Onay gate (workflow-run.schema awaiting_approval)
8. `outputs/reports/{date}-cannibalization.md` render via `templates/reports/cannibalization.template.md` (top conflict pair + total impact + resolution suggestion)
9. Optional remediation chain (`content-remediation` skill suggestion HIGH severity satırları için)
10. Drift-check downstream tetikleyici (cross-sheet F-08 invariant)

## 3. Çalıştırma notları

- `--days-back N` default 28; 90+ retrospective historical analysis için artırılabilir.
- `--min-impressions K` default 10; düşük volume noise filter.
- Cron `0 9 * * 2` Salı 09:00 UTC report-only mode.
- Optional `mcp__gsc__enhanced_search_analytics` alternative data source (daha detaylı page-level breakdown).

## 4. Bağımlılıklar

- Skill: `skills/discovery/cannibalization/SKILL.md` (Phase 7 W1, active)
- Scripts: `scripts/discovery/cannibalization_transform.py` + `scripts/state/events_writer.py` (`append_provenance`) + `scripts/excel/transaction.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/cannibalization.template.md`
- Schemas: `schemas/master-excel.schema.json#cannibalization` + `schemas/gsc-tool-mapping.schema.json` + `schemas/cross-sheet-invariants.json` (F-08)
- MCP: `mcp__gsc__search_analytics` (required) + `mcp__gsc__enhanced_search_analytics` (optional)
- project.config: `gsc.site_url`
- Upstream: `init-project` (master.xlsx) + `gsc-pull` (master.xlsx#gsc_performance)
