<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/excel-discipline.md, rules/schema-first.md, rules/events-writer.md, rules/append-only-state.md
-->
# Drift Check — $project_slug

**Tarih:** $date
**Genel verdict:** $verdict

## Sayım

| Sonuç | Sayı |
|-------|------|
| PASS  | $pass_count |
| WARN  | $warn_count |
| FAIL  | $fail_count |
| Toplam kontrol | $total_checks |

## Özet

$report_summary

## Manuel inceleme gereken kurallar

$manual_review_required

## Kanıt zinciri

- Run ID: `$run_id`
- consistency-report: `$consistency_report_path`
- master.xlsx SHA-256 (read-only): `$workbook_sha256`

> Üretildi: `drift-check` skill — `scripts/validation/validate_invariants.py` (20 hand-coded rules)
