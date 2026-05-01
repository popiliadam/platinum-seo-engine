# Cannibalization — $project_slug

**Tarih:** $date
**Pencere:** son $days_back gün
**Conflict sayısı:** $conflict_count

## Özet

$report_summary

## En yüksek etki

- **Conflict:** $top_conflict_pair
- **Toplam tıklama:** $top_total_impact
- **Önerilen aksiyon:** $top_resolution

## Tetikleyici eşikler

- Min impressions per page: $min_impressions
- Default status: $default_status

## Kanıt zinciri

- Raw MCP payload: `$raw_json_path`
- Run ID: `$run_id`
- Yazılan satır sayısı: `cannibalization=$rows_cannibalization`

> Üretildi: `cannibalization` skill — `scripts/discovery/cannibalization_transform.py`
