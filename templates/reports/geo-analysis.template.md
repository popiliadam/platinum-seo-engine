<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/content-quality.md, rules/events-writer.md, rules/append-only-state.md
-->
# GEO / AEO Analysis — $project_slug

**Tarih:** $date
**Sorgu sayısı:** $query_count
**DFS credits kullanıldı:** $credits_used (llm_mentions_search + serp_organic_live_advanced)

## Özet

$report_summary

## Gap dağılımı

| Gap label      | Sayı                |
|----------------|---------------------|
| AEO_NEEDED     | $gap_aeo_needed     |
| SERP_GAP       | $gap_serp_gap       |
| AEO_HEALTHY    | $gap_aeo_healthy    |
| ABSENT         | $gap_absent         |

## En öncelikli sorgu (AEO_NEEDED)

- **Sorgu:** $top_query
- **LLM visibility score:** $top_visibility
- **SERP top-3 mı:** $top_serp_top_3
- **Önerilen aksiyon:** $top_action

## Kanıt zinciri

- DFS llm_mentions raw payload: `$raw_llm_path`
- DFS serp_organic raw payload: `$raw_serp_path`
- Run ID: `$run_id`
- Yazılan satır sayısı: `llm_mentions=$rows_llm_mentions`,
  `serp_organic=$rows_serp_organic`, `geo_signals=$rows_geo_signals`

> Üretildi: `geo-analysis` skill — `scripts/discovery/geo_analysis_transform.py`
