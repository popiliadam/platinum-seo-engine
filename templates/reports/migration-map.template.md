<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/tech-seo-governance.md (migration redirect-map contract / phase gate / post-migration verification), rules/schema-first.md, rules/events-writer.md, rules/append-only-state.md
-->
# Site-Migration Redirect Map — $project_slug

**Tarih:** $date
**Mod:** $mode

> Recommendation-only (per tech-seo-governance migration rules): bu rapor
> önerilerdir; 301/410 yönlendirmelerini, sunucu config'ini ve (domain taşımasında)
> GSC Change-of-Address adımını **operatör** uygular. Motor istemci altyapısına
> yazmaz, sitemap submit etmez, Change-of-Address tetiklemez.

## Harita istatistikleri (one-to-one map)

$map_stats_table

## Eşlenmemiş (unmapped) URL'ler — operatör triyajı

$unmapped_table

> Hiçbir eski URL sessizce düşürülmez (per tech-seo-governance migration
> redirect-map kuralı): her URL ya bir redirect satırıdır ya da burada listelenir.
> Trafik-kritik (GSC tıklaması olan) eşlenmemiş URL'ler öncelikli.

## Lint bulguları

$lint_findings

> Karar (per tech-seo-governance migration rules): döngü / self-redirect → RED
> (deploy öncesi çöz); anasayfaya çökme eşiği aşıldıysa topical sinyal kaybı
> riski; zincir > 3 hop ise doğrudan nihai hedefe yönlendir.

## Sunucu config snippet'leri (RECOMMENDATION ONLY — operatör uygular)

$server_config_snippets

## Faz-geçit checklist (plan → freeze → deploy → verify)

$phase_checklist

> Yönlendirmeler en az ~1 yıl (180 gün sert taban) korunur; eski sitemap yeni
> sitemap'le birlikte geçici olarak canlı tutulur (redirect keşfini hızlandırır).

## Doğrulama tablosu (verify modu)

$verification_table

## Rollback önerisi

$rollback_recommendation

## Kanıt zinciri

- Tarih: `$date` · Proje: `$project_slug` · Mod: `$mode`
- Run ID: `$run_id`
- Yazıldı: `master.xlsx#redirect_404` (key=url, sheet_merge idempotent)

> Üretildi: `migration-map` skill — `scripts/planning/migration_map_transform.py`
> (FREE; trafik koruması master.xlsx#gsc_performance'tan, paid MCP yok).
