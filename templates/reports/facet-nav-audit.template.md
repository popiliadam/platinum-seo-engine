<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/tech-seo-governance.md (parameter taxonomy / index-bloat budget / blocking-mechanism decision tree), rules/schema-first.md, rules/events-writer.md, rules/append-only-state.md
-->
# Faceted-Navigation & Crawl-Budget Audit — $project_slug

**Tarih:** $date
**Platform:** $platform
**Sonuç:** $verdict

> Recommendation-only (per tech-seo-governance faceted-nav rules): bu rapor
> önerilerdir; robots.txt / CMS / sunucu değişikliklerini **operatör** uygular.
> Motor istemci altyapısına yazmaz.

## Parametre sınıflandırması (closed taxonomy)

$param_class_table

## Index-bloat metrikleri

$bloat_metrics

## Demand kanıtı (facet indexlenebilirlik gerekçesi)

$demand_evidence_table

## Önerilen robots.txt bloğu (RECOMMENDATION ONLY — operatör uygular)

```
$proposed_robots_block
```

> Karar ağacı (per tech-seo-governance blocking-mechanism rules): hiç
> indexlenmeyecek + crawl israfı → robots.txt disallow; indexli + kaldırılacak
> → önce crawlable noindex, de-index doğrulanınca disallow; benzer içerik →
> rel=canonical; yeni build → fragment (#) filtreler.

## Sınıflandırılamayan (unknown) parametreler — operatör triyajı

$unknown_params

> Bunları `projects/$project_slug/config/facet-policy.json` dosyasında
> sınıflandırın (per tech-seo-governance parameter-taxonomy rules) ve audit'i
> yeniden çalıştırın. Doğrulanamayan platform/dil sözlükleri tasarım gereği
> buraya düşer.

## Kanıt zinciri

- Tarih: `$date` · Proje: `$project_slug` · Platform: `$platform`
- Run ID: `$run_id`
- Yazıldı: `master.xlsx#robots_txt` (FN- prefix, sheet_merge idempotent)

> Üretildi: `facet-nav-audit` skill — `scripts/discovery/facet_nav_audit_transform.py`
> (FREE; demand kanıtı master.xlsx#cluster_keywords + #gsc_performance'tan).
