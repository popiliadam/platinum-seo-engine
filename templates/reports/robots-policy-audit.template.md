<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/tech-seo-governance.md (governed robots.txt policy / noindex deployment path / noindex-disallow mutual exclusion), rules/content-html-discipline.md (lifecycle robots-meta map), rules/schema-first.md, rules/events-writer.md, rules/append-only-state.md
-->
# robots.txt & noindex Lifecycle Audit — $project_slug

**Tarih:** $date
**Canlı robots.txt:** $live_robots_status

> Recommendation-only (per tech-seo-governance robots.txt-policy rules): canlı
> robots.txt GET'i bir **public dosya okumasıdır** (consent gate yok). robots.txt
> / per-page noindex / X-Robots-Tag değişikliklerini **operatör** uygular. Motor
> istemci altyapısına yazmaz.

## robots.txt lint bulguları

$lint_table

## noindex / disallow çakışması (mutual exclusion)

$conflict_table

> Bir URL hem robots.txt ile disallow edilip hem noindex taşıyorsa Google
> noindex'i ASLA göremez (de-index tuzağı). Sıra: noindex deploy → de-index
> doğrula → ancak o zaman disallow (per tech-seo-governance mutual-exclusion rules).

## Lifecycle drift (ON_HOLD / REMOVED)

$lifecycle_drift_table

## Önerilen robots.txt (RECOMMENDATION ONLY — operatör uygular)

```
$proposed_robots_txt
```

## Deployment talimatları (platforma göre)

$deployment_instructions

> noindex deploy yolu öncelik sırası (per tech-seo-governance noindex-deployment
> rules): (1) CMS/SEO-plugin sayfa-bazlı robots kontrolü, (2) X-Robots-Tag HTTP
> header, (3) tema `<head>` template düzenlemesi. Doğrulanamayan platformlar
> `UNVERIFIED` işaretlidir — menü yolunu operatör doğrular.

$amber_warnings

## Kanıt zinciri

- Tarih: `$date` · Proje: `$project_slug`
- Run ID: `$run_id`
- Yazıldı: `master.xlsx#robots_txt` (RP- prefix) + `outputs/robots/$date-robots.proposed.txt`

> Üretildi: `robots-policy-audit` skill — `scripts/discovery/robots_policy_transform.py`
> (FREE; canlı robots.txt Scrapling GET + SF directives export).
