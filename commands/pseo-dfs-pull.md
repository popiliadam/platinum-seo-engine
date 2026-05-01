---
description: |
  Use when: kullanıcı "DataForSEO çek", "DFS pull", "keyword overview", "search volume DFS", "dfs ingestion" der ya da `/pseo-dfs-pull` çağırırsa.
  Also use when: aktif projenin keyword listesi var, DFS bütçesi (project.config.dataforseo.budget_credits_per_day) yeterli; staging-only (Phase 8 cluster-map konsume eder).
  Do not use when: GSC ingestion (`pseo-gsc-pull`), Scrapling fetch (`pseo-scrape`), keyword cluster üretimi (Phase 8 `cluster-map` ayrı skill).
argument-hint: "[project-slug] [keywords-file]"
allowed-tools: Bash(jq:*), Read
model: sonnet
---

# /pseo-dfs-pull — DataForSEO Keyword Ingestion (Staging-Only)

> **Phase dependency:** Phase 6 `skills/ingestion/dfs-pull/SKILL.md` aktif. D-003 staging-only refactor sonrası master.xlsx'e write YOK; staging JSON Phase 8 cluster-map skill'i tarafından konsume edilir.

## 1. Aktif projeyi çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. Skill chain

`dfs-pull` skill (Phase 6 — `skills/ingestion/dfs-pull/SKILL.md`):

1. Budget pre-flight (`scripts/budget/check_budget.py`, uses_paid_mcp=true)
2. `mcp__dataforseo__dataforseo_labs_google_keyword_overview` keyword listesi için
3. `mcp__dataforseo__keywords_data_google_ads_search_volume` volume enrichment
4. TR Workaround layered (A heuristic → B alt endpoint → C HTTP bypass)
5. Raw JSON inbox/dfs/{date}-* (drift recovery)
6. `_normalize_dfs_response` shape adapter (REST + flat tolerate)
7. Staging JSON yazımı `_state/staging/dfs_*.json` (NO master.xlsx write — D-003 fix)
8. outputs/reports/{date}-dfs-pull.md render
9. events.jsonl provenance event (source.kind=dataforseo_mcp, target_excel_sheet=null)

## 3. Bütçe disiplin

- Tahmini kredi = `len(keywords) * 1.5` (1.0 overview + 0.5 volume)
- Pre-flight FAIL → DURUR (budget exceeded)
- Daily limit: `project.config.dataforseo.budget_credits_per_day` (default 500)

## 4. Bağımlılıklar

- `skills/ingestion/dfs-pull/SKILL.md` — Phase 6
- `mcp__dataforseo__*` DFS MCP tools (.mcp.json bash wrapper, .env auto-source)
- `project.config.dataforseo.location_code` + `language_code` — required
- Phase 8 `cluster-map` skill — staging output downstream consumer
