---
description: |
  Use when: kullanıcı "quick win", "hızlı kazanım", "8-20 sıradaki keyword", "low-hanging fruit", "kolay yükselebilir sayfalar" der ya da `/pseo-quickwin` çağırırsa.
  Also use when: aktif projenin GSC verisi master.xlsx içinde mevcut; sıralamada eşik bandında olan sorgular için `gsc-pull` → `quick-wins` skill chain'i tetiklenmek isteniyor.
  Do not use when: yeni içerik planı (`new-content-plan`), içerik decay (`content-decay`), tech audit (`tech-audit`) ya da cannibalization analizi gerekiyor; bunlar ayrı skill'lerdir.
argument-hint: "[project-slug]"
allowed-tools: Bash(jq:*), Read
model: sonnet
---

# /pseo-quickwin — GSC Quick-Wins Chain

> **Skill chain:** `skills/ingestion/gsc-pull/SKILL.md` (Phase 6) → `skills/discovery/quick-wins/SKILL.md` (Phase 5). Aktif. GSC son 28 gün (`days_back` default) → pozisyon 11–20 bandı (`threshold_position_min/max` defaults), impressions ≥100, top_n=50 → `master.xlsx#quick_wins` + `master.xlsx#opportunity` + onay gate + `outputs/reports/{date}-quick-wins.md`.

## 1. Aktif projeyi çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. Skill chain

Bu komut şu sırayı tetikler:

1. **`gsc-pull`** (`skills/ingestion/gsc-pull/SKILL.md`)
   - Son 28 gün GSC `searchAnalytics` verisini çek (recent vs previous window delta paterni)
   - master.xlsx `gsc_performance` logical sheet'ine `scripts/excel/transaction.py` ile yaz
   - `events.jsonl`'e `event_kind=provenance` event'i (source.kind=gsc_mcp)

2. **`quick-wins`** (`skills/discovery/quick-wins/SKILL.md`)
   - GSC verisinden pozisyon 11–20 bandındaki sorguları filtrele (threshold_position_min=11, max=20 defaults)
   - Impressions ≥100 (threshold_impressions default), top_n=50 cap
   - master.xlsx `quick_wins` + `opportunity` logical sheet'lerine yaz (10 col schema-locked)
   - Onay gate: `awaiting_approval` (workflow-run.schema)
   - Onay sonrası `outputs/reports/{date}-quickwin.md` üret (`templates/reports/quickwin.template.md`)

## 3. Çalıştırma notları

- Aktif `gsc_landing_query` sheet'i boşsa: zincir `gsc-pull` ile başlar; data var ise `quick-wins` skill'i doğrudan koşar.
- Manuel pre-flight: master.xlsx'in `gsc_landing_query` sheet'i Read tool ile incelenebilir; yoksa `/pseo-gsc-pull` ile ingestion ayrı çalıştırılabilir.

## 4. Bağımlılıklar

- `skills/discovery/quick-wins/SKILL.md` — aktif (Phase 5)
- `skills/ingestion/gsc-pull/SKILL.md` — aktif (Phase 6)
- MCP (quick-wins required): `mcp__gsc__detect_quick_wins` + `mcp__gsc__enhanced_search_analytics`
- MCP (quick-wins optional): `mcp__gsc__search_analytics` (alternative data source)
- MCP (gsc-pull required): `mcp__gsc__enhanced_search_analytics` + `mcp__gsc__search_analytics`
- MCP (gsc-pull optional): `mcp__gsc__index_inspect` (URL inspection enrichment)
- `.mcp.json` bash wrapper, `.env` auto-source (GOOGLE_APPLICATION_CREDENTIALS)
- `project.config.gsc.site_url` — required input
