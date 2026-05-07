<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/events-writer.md, rules/append-only-state.md
-->
# Quick Wins — $project_slug

**Tarih:** $date
**Pencere:** son $days_back gün
**Top-N:** $top_n / $total_opportunities aday

## Özet

$report_summary

## En yüksek skor

- **Sorgu:** $top_query
- **URL:** $top_url
- **Opportunity score:** $top_score
- **Mevcut pozisyon:** $top_position
- **Önerilen aksiyon:** $top_action

## Tetikleyici eşikler

- Pozisyon aralığı: $threshold_position_min – $threshold_position_max
- Min impressions: $threshold_impressions

## Kanıt zinciri

- Raw MCP payload: `$raw_json_path`
- Run ID: `$run_id`
- Yazılan satır sayısı: `quick_wins=$rows_quick_wins`, `opportunity=$rows_opportunity`

> Üretildi: `quick-wins` skill — `scripts/discovery/quickwins_transform.py`
