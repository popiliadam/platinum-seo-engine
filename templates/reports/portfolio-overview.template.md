---
generated_at: $generated_at
portfolio_id: $portfolio_id
project_count: $project_count
scope: $scope
---

# Portfolio Overview — $display_name

**Portfolio:** `$portfolio_id`
**Generated:** $generated_at
**Active projects:** $project_count (skipped: $skipped_count)
**Scope:** $scope

## Projects

$projects_table

## Totals (aggregate across active projects)

$totals_summary

---

_Read-only multi-project aggregation. Per portfolio-config.schema.json
`cross_query.read_only=true` (const), this report does not mutate any
project workbook; KPIs are read directly from each project's
`master.xlsx#dashboard` cells (R10, R47-R52, R59) and master_task status
counts. Drift column = YES when local master_task status counts diverge
from the corresponding dashboard cell._

## Kanıt zinciri

- Yazıcı: `portfolio-overview` skill — `scripts/reporting/portfolio_overview.py` (READ-ONLY aggregator; master.xlsx#none)
- Run ID: `$run_id`
- Schema otoritesi: `schemas/portfolio-config.schema.json` v1.1 + `schemas/master-excel.schema.json#dashboard`
- Şablon: `templates/reports/portfolio-overview.template.md` (`string.Template` engine — `scripts/reporting/render_template.py`)
- Üretildi: `$generated_at`
