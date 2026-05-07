<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/single-source-of-truth.md, rules/events-writer.md, rules/append-only-state.md
-->
# Competitive Analysis — $project_slug

**Tarih:** $date
**Hedef domain:** $target_domain
**Snapshot satır sayısı:** $row_count
**DURUR (all-tiers-fail) sayısı:** $durur_count
**Rakip domain sayısı:** $competitor_domain_count

## Özet

$report_summary

## En çok izlenen rakipler

$top_competitors

## Tier dağılımı (§14.5)

$tier_distribution

## Tetikleyici eşikler

- Bulk unhealthy threshold: $bulk_threshold
- Max URLs (scrapling-ops upstream): $max_urls

## Kanıt zinciri

- Raw Scrapling envelope: `$raw_scrapling_path`
- Raw DFS competitors_domain: `$raw_competitors_path`
- Staging dosyası: `$staging_path`
- Run ID: `$run_id`
- S1 sub-schema: `templates/scrapling/S1_competitor_snapshot.schema.json`

> Üretildi: `competitive-analysis` skill —
> `scripts/discovery/competitive_analysis_transform.py`
