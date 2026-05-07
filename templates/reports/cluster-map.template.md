<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/content-quality.md, rules/content-seo-discipline.md, rules/events-writer.md, rules/append-only-state.md
-->
# Cluster Map — $project_slug

**Tarih:** $date
**Seed keyword:** `$seed_keyword`
**Lokasyon / dil:** `$location_code` / `$language_code`

## Özet

- **Cluster sayısı:** $cluster_count
- **Toplam keyword:** $keyword_count
- **GSC enrichment hit:** $gsc_enrichment_hit_pct%
- **Source breakdown:** $source_breakdown

## En büyük cluster

- **Adı:** $top_cluster
- **Top keywords:** $top_cluster_keywords

## Bütçe

- **Tahmini kredi:** $estimated_credits
- **Pre-flight:** $budget_preflight_status

## Kanıt zinciri

- Run ID: `$run_id`

> Üretildi: `cluster-map` skill — `scripts/planning/cluster_map_transform.py`
