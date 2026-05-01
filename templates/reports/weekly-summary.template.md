---
project_id: $project_slug
period_start: $week_start
period_end: $week_end
generated_at: $generated_at
report_kind: weekly_summary
---

# Weekly Summary — $project_slug

**Pencere:** $week_start – $week_end
**Üretildi:** $generated_at

## Exec Summary

$exec_summary

## GSC Weekly Delta

$gsc_weekly_delta

> Not: Wave 1 reporting LOCAL aggregation; tam GSC delta pipeline'ı
> `monthly-report` skill kapsamındadır.

## Tasks Done ($tasks_done_count)

$tasks_done_table

## Tasks Added ($tasks_added_count)

$tasks_added_table

## Drift Signals

$drift_signals

> Üretildi: `weekly-summary` skill — `scripts/reporting/weekly_summary.py`
