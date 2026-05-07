---
report_kind: portfolio-weekly-brief
scope: $scope
week_start: $week_start
week_end: $week_end
generated_at: $generated_at
sla_weekly_sync_max_days: $sla_weekly_sync_max_days
projects_count: $projects_count
---

# Portföy Haftalık Brief — $week_start → $week_end

**Üretildi:** $generated_at  (UTC)
**Kapsam:** $scope ($projects_count aktif proje)
**SLA:** weekly_sync_max_days = $sla_weekly_sync_max_days

## Toplam

$totals_summary

| Metrik | Değer |
|---|---:|
| tasks_added | $totals_tasks_added |
| tasks_done  | $totals_tasks_done  |
| work_events | $totals_work_events |
| fresh projeler | $totals_fresh_projects |
| stale projeler | $totals_stale_projects |

## Proje bazında 7 günlük delta + freshness

$projects_delta_table

> **Freshness flag:** `last_sync_at` üzerinden `now - last_sync_at > sla.weekly_sync_max_days` ise `stale`, aksi halde `fresh`. `last_sync_at` boş/null projeler doğrudan `stale` olarak işaretlenir.

## Kanıt zinciri

- Yazıcı: `portfolio_weekly_brief` (READ-ONLY agregator; master.xlsx#none)
- Snapshot: `inbox/local/$week_end-portfolio-weekly-brief.json`
- Run ID: `$run_id`
- Schema otoritesi: `schemas/portfolio-config.schema.json` v1.1
  (`cadence.weekly_brief` + `slas.weekly_sync_max_days` +
  `active_projects[].last_sync_at`)
- Şablon: `templates/reports/portfolio-weekly-brief.template.md`
  (`string.Template` `$$var` engine — `scripts/reporting/render_template.py`
  ile uyumlu)

> Üretildi: `portfolio-weekly-brief` skill — `scripts/reporting/portfolio_weekly_brief.py`
