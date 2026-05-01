# GSC Pull — $project_slug

**Tarih:** $date
**Pencere:** son $days_back gün

## Özet

GSC search_analytics + enhanced_search_analytics ingestion. Mevcut pencere ile önceki dönem karşılaştırılır.

- **Recent rows:** $row_count_recent
- **Previous rows:** $row_count_previous
- **Unique URLs:** $unique_urls

## Top-5 sayfa (clicks_recent)

$top_5_pages

## Delta özeti

$delta_summary

## Kanıt zinciri

- Raw MCP payload (search_analytics): `inbox/gsc/$date-search_analytics-$project_slug.json`
- Raw MCP payload (enhanced): `inbox/gsc/$date-enhanced_search_analytics-$project_slug.json`
- Run ID: `$run_id`
- Yazılan satır sayısı: `gsc_performance=$rows_written`

> Üretildi: `gsc-pull` skill — `scripts/ingestion/gsc_pull.py`
