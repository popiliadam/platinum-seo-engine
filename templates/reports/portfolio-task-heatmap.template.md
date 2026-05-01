---
report_kind: portfolio-task-heatmap
generated_at: $generated_at
portfolio_id: $portfolio_id
project_count: $project_count
scope: $scope
---

# Portfolio Task Heatmap — $display_name

**Portfolio:** `$portfolio_id`
**Generated:** $generated_at  (UTC)
**Active projects:** $project_count (skipped: $skipped_count)
**Scope:** $scope

## Toplam (rollup)

$totals_summary

## Per-project: project × category × priority matrix

$projects_matrix

## Per-category breakdown (rows = category, cols = severityEnum)

$category_totals_table

## Per-priority breakdown (rows = severityEnum, cols = project)

$priority_totals_table

## Advisories

$advisory_block

---

_Read-only multi-project aggregation. Per
`portfolio-config.schema.json` `cross_query.read_only=true` (const),
this report does not mutate any project workbook; rows are scanned
from each project's `master.xlsx#master_task` columns F (category),
G (priority — `severityEnum` 4 values), J (status — `statusEnum`
7 values). Status filter: open task = status NOT in
`{DONE, CANCELED}`. status_check_drift advisory surfaces when a
project's optional consistency-report carries a non-GREEN verdict
(WARNING, transform proceeds — NOT a DURUR)._

> Üretildi: `portfolio-task-heatmap` skill — `scripts/reporting/portfolio_task_heatmap.py`
