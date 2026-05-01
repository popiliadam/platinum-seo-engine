---
description: |
  Use when: kullanıcı "GSC çek", "GSC pull", "GSC son N gün", "search_analytics ingest", "gsc_performance populate" der ya da `/pseo-gsc-pull` çağırırsa.
  Also use when: aktif projenin GSC site'ı doğrulanmış, drift-check `gsc_performance` populated bekliyor (F-08 RE-EVAL pre-condition); manager `gsc-pull` skill'ini tetiklemek istiyor.
  Do not use when: DataForSEO ingestion (`dfs-pull`), Scrapling fetch (`pseo-scrape`), quick-wins detection (zaten downstream — `pseo-quickwin`).
argument-hint: "[project-slug] [days_back]"
allowed-tools: Bash(jq:*), Read
model: sonnet
---

# /pseo-gsc-pull — GSC Search Analytics Ingestion

> **Phase dependency:** Phase 6 `skills/ingestion/gsc-pull/SKILL.md` aktif. Süleyman live test sonrası `gsc_performance` sheet populate edilmiş olur.

## 1. Aktif projeyi çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. Skill chain

`gsc-pull` skill (Phase 6 — `skills/ingestion/gsc-pull/SKILL.md`):

1. `mcp__gsc__search_analytics` ile son `${2:-28}` gün veriyi çek
2. `mcp__gsc__enhanced_search_analytics` ile aynı pencerede enrichment
3. Raw JSON inbox/gsc/{date}-* (drift recovery)
4. Pure transform (URL normalization D-03 idempotent)
5. master.xlsx#gsc_performance atomic write
6. outputs/reports/{date}-gsc-pull.md render
7. events.jsonl provenance event (source.kind=gsc_mcp)

## 3. F-08 RE-EVAL hint

`gsc_performance` populated → `quick_wins ⊆ crawl_sitemap ∪ gsc_performance` subset valid. Phase 5'te AMBER (sparse), Phase 6'da GREEN beklenir.

## 4. Bağımlılıklar

- `skills/ingestion/gsc-pull/SKILL.md` — Phase 6
- `mcp__gsc__*` GSC MCP tools (.mcp.json bash wrapper, .env auto-source)
- `project.config.gsc.site_url` — required input
