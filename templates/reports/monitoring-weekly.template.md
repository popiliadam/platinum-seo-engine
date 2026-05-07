---
project_id: $project_slug
period_start: $week_start
period_end: $week_end
generated_at: $generated_at
report_kind: monitoring_weekly
severity: $severity
---

# Monitoring Weekly — $project_slug

**Pencere:** $week_start – $week_end
**Üretildi:** $generated_at
**Genel severity:** $severity

## Exec Summary

$exec_summary

## Drift Section

$drift_section

> Kaynak: `_state/events.jsonl` filter `event_kind=audit AND audit_target startswith "invariants:"` — Phase 5 `governance/drift-check` audit append paterni reuse.

## GSC Anomaly Section

$gsc_anomaly_section

> Kaynak: `master.xlsx[gsc_performance]` read-only (openpyxl). Week-over-week delta vs trailing 8-week mean; >5σ → DURUR #5 alert.

## Budget Burn Section

$budget_burn_section

> Kaynak: `_state/events.jsonl` `cost.credits` aggregation per day. Baseline: `project-config.budget_credits_per_day` (eksik ise DURUR #2 default 500).

## Escalations

$escalations

## Kanıt zinciri

- Yazıcı: `monitoring-weekly` skill — `scripts/reporting/monitoring_weekly.py` (Phase 12 W-G6, Phase 9 reporting paterni reuse)
- Run ID: `$run_id`
- Şablon: `templates/reports/monitoring-weekly.template.md` (`string.Template` engine — `scripts/reporting/render_template.py`)
- Üretildi: `$generated_at`
