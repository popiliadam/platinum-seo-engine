---
report_kind: portfolio-monthly-roundup
scope: $scope
period_start: $period_start
period_end: $period_end
generated_at: $generated_at
projects_count: $projects_count
---

# Portföy Aylık Roundup — $period_start → $period_end

**Üretildi:** $generated_at  (UTC)
**Portföy:** `$portfolio_id` ($display_name)
**Kapsam:** $scope ($projects_count aktif proje, atlanan: $skipped_projects)

## Toplam

$totals_summary

| Metrik | Değer |
|---|---:|
| tasks_done (sum) | $totals_tasks_done |
| new_content (30d) | $totals_new_content |
| content_revised (30d) | $totals_content_revised |
| tech_seo_done (30d) | $totals_tech_seo_done |
| work_events (30d) | $totals_work_events |

## Proje bazında 30 günlük KPI roll-up

$projects_kpi_table

> **Not:** Sıralama `(effective_priority, slug)` üzerinden deterministiktir.
> `cadence` sütunu, varsa `editorial_overrides.cadence` değerini, aksi halde
> portföy varsayılanı `monthly`'i gösterir.

## EditorialOverrides notları (per-project precedence)

$editorial_overrides_notes

> **Schema kuralı:** Bir projede `editorial_overrides.sla_days`,
> `editorial_overrides.priority` veya `editorial_overrides.cadence`
> alanlarından biri set edilmişse, `override_rationale` zorunludur ve
> minimum 10 karakter olmalıdır (portfolio-config.schema.json v1.1
> `EditorialOverrides.override_rationale.minLength = 10`). Transform
> 9-karakterli rationale'ı `EditorialOverrideRationaleError` ile
> reddeder.

## Kanıt zinciri

- Yazıcı: `portfolio_monthly_roundup` (READ-ONLY agregator; master.xlsx#none)
- Snapshot: `inbox/local/$period_end-portfolio-monthly-roundup.json`
- Run ID: `$run_id`
- Schema otoritesi: `schemas/portfolio-config.schema.json` v1.1
  (`cadence.monthly_roundup` + `EditorialOverrides`) +
  `schemas/monthly-report.schema.json` v1.0
  (7-section subset: exec_summary, keywords_up, pages_up, tech_seo_done,
   content_revised, new_content, next_month_plan)
- Şablon: `templates/reports/portfolio-monthly-roundup.template.md`
  (`string.Template` `$$var` engine — `scripts/reporting/render_template.py`
  ile uyumlu)

> Üretildi: `portfolio-monthly-roundup` skill — `scripts/reporting/portfolio_monthly_roundup.py`
