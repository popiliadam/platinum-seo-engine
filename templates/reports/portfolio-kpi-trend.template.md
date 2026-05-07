---
report_kind: portfolio-kpi-trend
scope: $scope
portfolio_id: $portfolio_id
period_start: $period_start
period_end: $period_end
period_days: $period_days
generated_at: $generated_at
projects_count: $projects_count
---

# Portföy KPI Trend — $period_start → $period_end

**Üretildi:** $generated_at  (UTC)
**Kapsam:** $scope ($projects_count aktif proje, period=$period_days gün)
**Portföy:** `$portfolio_id` — $display_name

## Toplam (portföy çapında)

$totals_summary

| Metrik | Değer |
|---|---:|
| tasks_added | $totals_tasks_added |
| tasks_done  | $totals_tasks_done  |
| work_events | $totals_work_events |

### Portföy çapında event_type density (10 enum coverage)

$event_type_totals_table

## Proje bazında trend (daily axis + event_type density)

$projects_block

## Kanıt zinciri

- Yazıcı: `portfolio_kpi_trend` (READ-ONLY agregator; master.xlsx#none)
- Snapshot: `projects/_portfolio/inbox/local/$period_end-portfolio-kpi-trend.json`
- Run ID: `$run_id`
- Schema otoritesi:
  - `schemas/portfolio-config.schema.json` v1.1 (`active_projects` +
    `cross_query.read_only=true`),
  - `schemas/master-excel.schema.json#master_task` (col K
    `created_date` + col L `done_date` + statusEnum),
  - `schemas/events.schema.json#event_type` (10 enum:
    content_new / content_revise / content_remove / tech_fix /
    quickwin_applied / pillar_launch / schema_fix /
    redirect_deployed / backlink_outreach / manual),
  - `schemas/monthly-report.schema.json#gscTotals` (stub subset
    LOCAL approximation paterni — W-E1 + W-E2 reuse).
- Şablon: `templates/reports/portfolio-kpi-trend.template.md`
  (`string.Template` `$$var` engine —
  `scripts/reporting/render_template.py` ile uyumlu)

> **LOCAL approximation:** GSC longitudinal data Phase 6+ entegrasyonu
> öncesinde gscTotals subset (clicks / impressions / avg_position /
> ctr) sentinel `0` değerinde tutulur; her proje bloğunda görünür
> şekilde işaretlenir. Trend axis tamamen master.xlsx#master_task col
> K + L (created_date / done_date) ve _state/events.jsonl
> (event_kind=work) tabanlıdır.

> Üretildi: `portfolio-kpi-trend` skill — `scripts/reporting/portfolio_kpi_trend.py`
