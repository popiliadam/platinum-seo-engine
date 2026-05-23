<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/schema-first.md, rules/events-writer.md, rules/append-only-state.md, rules/budget-events.md
-->
# GBP Audit — $project_slug

**Tarih:** $date
**Profile gate:** local-service ✅

## Özet

DFS `business_data_business_listings_search` + Scrapling fallback (gerekirse) ingestion → 8-category gap analysis → master.xlsx#gbp_audit (7 kolon, severityEnum + statusEnum).

- **Listing bulundu:** $listing_found
- **Toplam gap satırı:** $row_count
- **HIGH severity:** $high_count
- **MEDIUM severity:** $medium_count
- **LOW severity:** $low_count

## Bütçe

- **Tahmini kredi:** $estimated_credits (business_listings_search MAX)
- **Pre-flight:** $budget_preflight_status
- **24h kullanım:** $used_24h / $budget_per_day

## Kategori dağılımı

| Kategori | Gap sayısı | En yüksek severity |
|----------|------------|--------------------|
$category_breakdown_table

## Top bulgular (severity DESC)

| Kategori | Gap | Severity | Önerilen aksiyon | Durum |
|----------|-----|----------|------------------|-------|
$top_findings_table

## Kanıt zinciri

- Raw business listings payload: `inbox/dfs/$date-gbp-listing-$project_slug.json`
- Excel sheet: `master.xlsx#gbp_audit` ($row_count satır)
- Run ID: `$run_id`

## Hard constraint compliance

- **Read-only audit:** Bu rapor sadece bulguları listeler; GBP API'sine otomatik bir şey gönderilmedi (`feedback_indexing_api_consent` hard constraint). Aksiyonları operator GBP dashboard'unda manuel uygular.
- **Append-only state:** events.jsonl provenance row + master.xlsx#gbp_audit append; mevcut satırlara dokunulmadı.

> Üretildi: `gbp-audit` skill — `scripts/discovery/gbp_audit_transform.py`
> Phase 5 Wave 1 — DFS LIGHT paid-MCP ingestion (~3 credit/audit). G-AI-02 finding closure. Budget pre-flight per ADR-016.
