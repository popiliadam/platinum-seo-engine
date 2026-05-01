# Content Decay — $project_slug

**Tarih:** $date
**Pencere:** son $days_back gün (recent) vs önceki $days_back gün (previous)

## Özet

$report_summary

- **Toplam URL:** $total_urls
- **Decay (≤ -20%):** $decay_count
- **Retired (recent=0):** $retired_count

## En çok decay yaşayan sayfa

- **URL:** $top_decay_url
- **Click delta:** $top_decay_delta

## Trend dağılımı

$trend_distribution

## Pillar bazlı bakış

$pillar_summary

## Kanıt zinciri

- Raw MCP payload (recent 90d): `inbox/gsc/$date-enhanced_search_analytics-decay-recent-$project_slug.json`
- Raw MCP payload (previous 90d): `inbox/gsc/$date-enhanced_search_analytics-decay-previous-$project_slug.json`
- Run ID: `$run_id`
- Yazılan satır sayısı: `content_decay=$rows_written`

> Üretildi: `content-decay` skill — `scripts/discovery/content_decay_transform.py`
