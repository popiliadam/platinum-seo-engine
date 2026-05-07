---
project_id: $project_id
report_id: $report_id
period_start: $period_start
period_end: $period_end
generated_at: $generated_at
framing_policy: $framing_policy
---

# Aylık Rapor — $project_id

**Dönem:** $period_start → $period_end
**Rapor ID:** $report_id
**Üretildi:** $generated_at
**Framing:** $framing_policy

## 1. Yönetici Özeti

$exec_narrative

- Toplam tıklama: **$headline_clicks**
- Yükselişteki sayfa sayısı: **$headline_pages_up**

## 2. GSC Pozitif Trendler (28 günlük)

| Metrik       | Bu dönem            | Önceki dönem        | Değişim |
|--------------|---------------------|---------------------|---------|
| Tıklama      | $current_clicks     | $previous_clicks    | %$clicks_delta_pct |
| Gösterim     | $current_impressions| $previous_impressions| %$impressions_delta_pct |
| CTR          | $current_ctr        | —                   | — |
| Ort. Pozisyon| $current_position   | —                   | — |

## 3. Yükselen Anahtar Kelimeler

$keywords_up_md

## 4. Yükselen Sayfalar

$pages_up_md

## 5. Tamamlanan Tech SEO İşleri

$tech_done_md

## 6. Revize Edilen İçerikler

$content_revised_md

## 7. Yeni Yayınlanan İçerikler

$new_content_md

## 8. Rakip Snapshot

_(Phase 10+ Scrapling S1/S3 entegrasyonu sonrası dolacak.)_

## 9. Backlink Delta

_(DataForSEO entegrasyonu opsiyonel — bu skill LOCAL aggregation, paid MCP kullanmıyor.)_

## 10. Önümüzdeki Ay Planı (top-10 TODO)

$next_plan_md

---

## Kanıt zinciri

- Yazıcı: `monthly-report` skill — `scripts/reporting/monthly_report.py`
- Kaynaklar: master.xlsx (READ-ONLY) + events.jsonl (READ-ONLY, son 28 gün)
- Run ID: `$run_id`
- Şablon: `templates/reports/monthly-report.template.md` (`string.Template` engine — `scripts/reporting/render_template.py`)
- Üretildi: `$generated_at`
