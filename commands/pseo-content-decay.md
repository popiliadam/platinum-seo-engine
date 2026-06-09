---
description: |
  Use when: kullanıcı "içerik decay", "content decay", "tıklama düşen sayfalar", "ctr düştü", "90 gün öncesine göre azalma", "trafik kaybeden sayfalar", "decay analizi", "content_decay sheet yenile", "ranking decay" der ya da `/pseo-content-decay` çağırırsa.
  Also use when: aktif projenin GSC verisi master.xlsx'te mevcut (gsc-pull önce çalışmış); 90-günlük recent + previous pencere karşılaştırması; pillar bazlı içerik decay haritası lazım; downstream `revise-content` / `new-content-plan` skill'leri tüketecek.
  Do not use when: kanibalizasyon (`/pseo-cannibalization`), GSC delta ingestion (`gsc-pull` skill direkt), tek-URL audit (`tech-audit` skill), schema markup drift (`/pseo-schema-audit`); master.xlsx yokken (`/pseo-init` + `gsc-pull` önce).
argument-hint: "<project-slug> [--days-back 90] [--dimensions page]"
allowed-tools: Bash(jq:*), Bash(python3:*), Read
model: sonnet
---

# /pseo-content-decay — Content Decay Detection

> **Skill:** `skills/discovery/content-decay/SKILL.md` (Phase 7 W1, aktif). GSC `enhanced_search_analytics` recent+previous window delta → content_decay_transform.py pure compute (week-over-week regression + 5σ anomaly threshold) → master.xlsx#content_decay sheet write + outputs/reports/{date}-content-decay.md + events.jsonl provenance row + onay gate.

## 1. Aktif projeyi çöz

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT days_back=${2:-90}"; fi; fi`

## 2. Skill chain

`skills/discovery/content-decay/SKILL.md` 10-step protokol koşar (spec §16.5 8-step MCP discipline):

1. project-config.gsc.site_url consume
2. `mcp__gsc__enhanced_search_analytics` recent window (last N day, default 90)
3. `mcp__gsc__enhanced_search_analytics` previous baseline window (equal length)
4. Inbox raw JSON drop: `inbox/gsc/{date}-enhanced_search_analytics-decay-{recent,previous}-{slug}.json` (drift recovery)
5. Pure compute: `scripts/discovery/content_decay_transform.py` (week-over-week regression + 5σ anomaly threshold + pillar-aware grouping)
6. (optional) `mcp__dataforseo__dataforseo_labs_google_historical_rank_overview` budget-gated cross-validate (paid)
7. master.xlsx `content_decay` sheet write via `scripts/excel/transaction.py`
8. events.jsonl append: `event_kind=provenance + operation=ingest + source.kind=gsc_mcp` (DFS varsa: ek provenance row source.kind=dataforseo_mcp)
9. Onay gate (workflow-run.schema awaiting_approval)
10. `outputs/reports/{date}-content-decay.md` render — HIGH severity decay revision plans for `revise-content` skill chain hand-off

DURUR (6 sentinel): GSC api auth fail / DFS budget exhausted / window overlap (recent ≥ previous start) / master.xlsx content_decay sheet schema mismatch / 5σ threshold all-clear (no decay detected) / pillar grouping ambiguous.

## 3. Çalıştırma notları

- `--days-back N` default 90 (recent + previous pencere eşit uzunlukta).
- `--dimensions page` default; alternatif `query` veya `device` GSC dimension.
- Cron `0 7 * * 1` Pazartesi 07:00 UTC report-only mode.
- Optional DFS historical_rank_overview ~5 credit/URL (budget pre-flight `scripts/budget/check_budget.py` zorunlu).

## 4. Bağımlılıklar

- Skill: `skills/discovery/content-decay/SKILL.md` (Phase 7 W1, active)
- Scripts: `scripts/discovery/content_decay_transform.py` + `scripts/budget/check_budget.py` + `scripts/state/events_writer.py` (`append_provenance`) + `scripts/excel/transaction.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/content-decay.template.md`
- Schemas: `schemas/master-excel.schema.json#content_decay`
- MCP: `mcp__gsc__enhanced_search_analytics` (required) + `mcp__dataforseo__dataforseo_labs_google_historical_rank_overview` (optional, paid)
- project.config: `gsc.site_url` + `budget.credits_per_day`
- Upstream: `init-project` (master.xlsx) + `gsc-pull` (master.xlsx#gsc_performance)
- Downstream: `revise-content` + `new-content-plan` (HIGH severity satırları tüketir)
