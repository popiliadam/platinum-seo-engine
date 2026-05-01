# Tech Audit — $project_slug

**Tarih:** $date
**Audit profili:** $device (Lighthouse)

## Özet

DFS Lighthouse + on_page_content_parsing tier ingestion → master.xlsx#tech_seo (6 kolon, severityEnum).

- **Audit edilen URL:** $url_count
- **Toplam finding kategorisi:** $row_count
- **Critical/High kategoriler:** $high_priority_count
- **Medium/Low kategoriler:** $medium_low_count

## Bütçe

- **Tahmini kredi:** $estimated_credits (Lighthouse $lighthouse_credits + content_parsing $content_credits)
- **Pre-flight:** $budget_preflight_status
- **24h kullanım:** $used_24h / $budget_per_day

## Top Bulgular

| Kategori | Detay | Etki | Öncelik | Çözüm |
|----------|-------|------|---------|-------|
$top_findings_table

## Kanıt zinciri

- Raw Lighthouse payload: `inbox/dfs/$date-lighthouse-$project_slug.json`
- Raw content_parsing payload: `inbox/dfs/$date-content_parsing-$project_slug.json`
- Excel sheet: `master.xlsx#tech_seo` ($row_count satır)
- Run ID: `$run_id`

> Üretildi: `tech-audit` skill — `scripts/discovery/tech_audit_transform.py`
> Phase 7 Wave 1 Wave 1 — DFS HEAVY paid-MCP ingestion. Budget pre-flight per ADR-016.
