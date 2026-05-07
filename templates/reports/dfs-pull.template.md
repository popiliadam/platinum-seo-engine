<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/budget-events.md, rules/events-writer.md, rules/append-only-state.md
-->
# DataForSEO Pull — $project_slug

**Tarih:** $date
**Lokasyon:** $location_code / $language_code

## Özet

DataForSEO keyword_overview + search_volume ingestion → staging-only (Phase 8 cluster-map konsume eder).

- **Keyword count:** $keyword_count
- **Top volume keyword:** $top_volume_kw ($top_volume_value/ay)
- **Ortalama CPC:** $cpc_avg

## TR Workaround

- **Yöntem:** $tr_workaround_method (A=heuristic / B=alt endpoint / C=HTTP bypass)
- **Workaround sonucu:** $tr_workaround_status

## Bütçe

- **Tahmini kredi:** $estimated_credits
- **Pre-flight:** $budget_preflight_status

## Kanıt zinciri

- Raw MCP payload (keyword_overview): `inbox/dfs/$date-keyword_overview-$project_slug.json`
- Raw MCP payload (search_volume): `inbox/dfs/$date-search_volume-$project_slug.json`
- Staging output: `$staging_path`
- Run ID: `$run_id`

> Üretildi: `dfs-pull` skill — `scripts/ingestion/dfs_pull.py`
> Phase 8 cluster-map skill bu staging dosyasını konsume eder.
