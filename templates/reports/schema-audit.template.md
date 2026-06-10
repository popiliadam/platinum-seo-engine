<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/schema-first.md, rules/schema-versioning-discipline.md, rules/events-writer.md, rules/append-only-state.md, rules/merchant-structured-data.md
-->
# Schema Audit — $project_slug

**Tarih:** $date
**Toplam satır:** $row_count

## Durum dağılımı

- **BLOCKED:** $blocked_count (öncelikli — çakışan @type)
- **TODO:** $todo_count (eksik zorunlu prop)
- **EXISTS:** $exists_count (eksik öneri prop / type-only)
- **DONE:** $done_count (tam)

## Özet

$report_summary

## En sık schema_type

- **Schema:** $top_schema_type
- **Önerilen aksiyon:** $top_remaining_work

## Merchant listing bulguları (e-ticaret)

$merchant_findings_md

> Merchant kontrolleri (M1–M7) yalnız e-commerce profilli projelerde
> çalışır; çerçeve per rules/merchant-structured-data.md (offer accuracy
> + shipping/returns org-level-first).

## Kanıt zinciri

- Raw SF envelope: `$raw_inbox`
- Run ID: `$run_id`
- Yazılan satır sayısı: `schema=$row_count`

> Üretildi: `schema-audit` skill — `scripts/discovery/schema_audit_transform.py`
