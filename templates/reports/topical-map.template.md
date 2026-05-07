# Topical Map — $project_slug

**Tarih:** $date
**Seed keyword:** `$seed_keyword`

## Özet

$report_summary

## Yapı

- **Pillar sayısı:** $pillar_count
- **Cluster sayısı:** $cluster_count

## En büyük pillar

- **Adı:** $top_pillar
- **Volume:** $top_pillar_volume

## En büyük cluster

- **Adı:** $top_cluster
- **Volume:** $top_cluster_volume

## Coğrafi gap

$geo_gaps_summary

## Kanıt zinciri

- Yazıcı: `topical-map` skill — `scripts/planning/topical_map_transform.py`
- Run ID: `$run_id`
- Şablon: `templates/reports/topical-map.template.md` (`string.Template` engine — `scripts/reporting/render_template.py`)
- Üretildi: `$date`
