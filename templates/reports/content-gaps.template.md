<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/content-quality.md, rules/content-seo-discipline.md, rules/events-writer.md, rules/append-only-state.md
-->
# Content Gaps — $project_slug

**Tarih:** $date
**Seed keyword:** $seed_keyword
**Lokasyon:** $location_code / $language_code

## Özet

DataForSEO keyword_ideas + related_keywords ingestion → staging-only (Phase 8 cluster-map / new-content-plan konsume eder).

- **Toplam aday keyword:** $total_candidates
- **Top gap_score keyword:** $top_keyword (gap_score=$top_gap_score)
- **Source dağılımı:** $source_breakdown

## En yüksek gap fırsatları

| Keyword | Volume | Difficulty | Competition | Gap Score | Source |
|---------|--------|------------|-------------|-----------|--------|
| $top1_keyword | $top1_volume | $top1_difficulty | $top1_competition | $top1_gap_score | $top1_source |
| $top2_keyword | $top2_volume | $top2_difficulty | $top2_competition | $top2_gap_score | $top2_source |
| $top3_keyword | $top3_volume | $top3_difficulty | $top3_competition | $top3_gap_score | $top3_source |

## Bütçe

- **Tahmini kredi:** $estimated_credits
- **Pre-flight:** $budget_preflight_status

## Kanıt zinciri

- Raw MCP payload (keyword_ideas): `inbox/dfs/$date-keyword_ideas-gaps-$project_slug.json`
- Raw MCP payload (related_keywords): `inbox/dfs/$date-related_keywords-gaps-$project_slug.json`
- Staging output (ideas): `$staging_path_ideas`
- Staging output (related): `$staging_path_related`
- Run ID: `$run_id`

> Üretildi: `content-gaps` skill — `scripts/discovery/content_gaps_transform.py`
> Phase 8 cluster-map / new-content-plan skill bu staging dosyalarını konsume eder.
