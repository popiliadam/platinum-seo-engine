---
description: |
  Use when: kullanıcı "site scrape", "Scrapling fetch", "URL scrape", "tier escalation", "stealthy fetch", "anti-bot" der ya da `/pseo-scrape` çağırırsa.
  Also use when: URL listesi için generic content fetch gerekli (per-scenario sub-schemas Phase 7+ skill'lerle gelir; bu komut generic helper'dır).
  Do not use when: GSC ingestion (`pseo-gsc-pull`), DataForSEO (`pseo-dfs-pull`), per-scenario competitive-analysis (Phase 7) / content-improve (Phase 9) — onlar scrapling-ops'u sub-schema ile çağırır.
argument-hint: "[project-slug] [urls-file] [--scenario generic|s1_competitor_snapshot|...] [--max-urls 50]"
allowed-tools: Bash(jq:*), Read
model: sonnet
---

# /pseo-scrape — Scrapling Generic Tier Escalation

> **Phase dependency:** Phase 6 `skills/ingestion/scrapling-ops/SKILL.md` aktif. Per-scenario sub-schemas (`templates/scrapling/*.schema.json`) Phase 7+ skill'lerle yazılır (ADR-025).

## 1. Aktif projeyi çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. Skill chain

`scrapling-ops` skill (Phase 6 — `skills/ingestion/scrapling-ops/SKILL.md`):

1. URL listesi okuma (`$2` argument veya `_state/scrape_input.json`)
2. Tier escalation state machine (canonical, schema-locked):
   - **Tier 0 — get:** HTTP GET basic (en hızlı, anti-bot yok)
   - **Tier 1 — fetch:** browser-like headers + JS rendering
   - **Tier 2 — stealthy_fetch:** anti-bot bypass (Cloudflare-aware)
   - All-fail → DURUR (no tier 3)
3. Bulk variants `mcp__ScraplingServer__bulk_*` URL count > 10 ise
4. Raw HTML/markdown inbox/scrapling/{date}-{tier}-* (drift recovery)
5. Staging JSON `_state/staging/scrapling_*.json` (NO master.xlsx write — Phase 6 staging-only)
6. outputs/reports/{date}-scrapling-ops.md render
7. events.jsonl provenance event (source.kind=scrapling_mcp, target_excel_sheet=null)

## 3. Tier ladder (immutable)

`get → fetch → stealthy_fetch` — `schemas/scrapling-output-mapping.schema.json` §14.5 canonical sequence. Yeni tier eklemek için ADR gerekir (yapısal değişiklik).

## 4. Bağımlılıklar

- `skills/ingestion/scrapling-ops/SKILL.md` — Phase 6
- MCP required: `mcp__ScraplingServer__fetch` + `bulk_fetch` + `stealthy_fetch` + `bulk_stealthy_fetch` (Tier 1+2)
- MCP optional: `mcp__ScraplingServer__open_session` + `close_session` + `get` (Tier 0 + session-level)
- `.mcp.json` bash wrapper (`SCRAPLING_BIN` env)
- `scenario` argument (default `generic`): Phase 7+ sub-schema enforcement routing tag (`s1_competitor_snapshot` vb.)
- `max_urls` argument (default 50): URL count budget — üzerinde DURUR (no silent truncation)
- `templates/scrapling/.gitkeep` — sub-schemas Phase 7+ defer (ADR-025)
