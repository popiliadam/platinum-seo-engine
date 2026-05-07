<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/content-seo-discipline.md, rules/events-writer.md, rules/append-only-state.md
-->
# Internal Links Audit — $project_slug

**Tarih:** $date

## Özet

$report_summary

## Sayımlar

- **Orphan sayfa:** $orphan_count
- **Broken link:** $broken_count
- **Redirect chain:** $redirect_chain_count
- **Anchor diversity:** $anchor_diversity_count

## En kritik orphan

- **URL:** `$top_orphan_url`

## En kritik broken link

- **URL:** `$top_broken_url`

## Kanıt zinciri

- Yazıcı: `internal-links` skill — `scripts/planning/internal_links_transform.py`
- Run ID: `$run_id`
- Şablon: `templates/reports/internal-links.template.md` (`string.Template` engine — `scripts/reporting/render_template.py`)
- Üretildi: `$date`
