---
report_kind: portfolio-heatmap
scope: $scope
generated_at: $generated_at
run_date: $run_date
portfolio_id: $portfolio_id
projects_count: $projects_count
aggregate_dimension: $aggregate_dimension
---

# Portfolio Heatmap — $display_name

**Portföy:** `$portfolio_id`
**Üretildi:** $generated_at  (UTC)
**Run date:** $run_date
**Aktif proje:** $projects_count (skipped: $skipped_count)
**Aggregate dimension:** `$aggregate_dimension`

## Toplam

$totals_summary

## Project × Sheet density (opportunity / quick_wins / content_decay / cannibalization)

$density_table

> **Density:** her hücredeki sayı raw row-count'tur; yanındaki sparkline o sheet için portföy genelindeki maksimum row-count'a normalize edilmiş yoğunluğu gösterir (`▁` en düşük, `▇` en yüksek). Boş hücreler 0.0 yoğunluk = boşluk.

## Master_task breakdown — `$aggregate_dimension` ekseni

$dimension_table

> **Bucket order:** `priority` ekseni `severityEnum` ile (CRITICAL → HIGH → MEDIUM → LOW); `primary_source` ekseni master_task col C 10-enum sırasıyla; `category` ekseni alfabetik (free-text). Schema-valid empty shape paterni: eksik sheet / eksik master.xlsx → 0 sayım, warning surface; aggregator crash etmez.

## Kanıt zinciri

- Yazıcı: `portfolio_heatmap` (READ-ONLY aggregator; `master.xlsx#none`)
- Snapshot: `projects/_portfolio/inbox/local/$run_date-portfolio-heatmap.json`
- Schema otoritesi: `schemas/portfolio-config.schema.json` v1.1 +
  `schemas/master-excel.schema.json` (master_task col B+C+F+G,
  opportunity, quick_wins, content_decay, cannibalization)
- Şablon: `templates/reports/portfolio-heatmap.template.md`
  (`string.Template` `$$var` engine — `scripts/reporting/render_template.py`
  ile uyumlu)

> Üretildi: `portfolio-heatmap` skill — `scripts/reporting/portfolio_heatmap.py`
