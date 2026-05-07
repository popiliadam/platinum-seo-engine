<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/content-html-discipline.md, rules/content-seo-discipline.md, rules/events-writer.md, rules/append-only-state.md
-->
# On-Page Audit — $project_slug

**Tarih:** $date
**URL sayısı:** $url_count
**DFS credits kullanıldı:** $credits_used (on_page_content_parsing)

## Özet

$report_summary

## Aksiyon dağılımı

| Aksiyon                              | Sayı                |
|--------------------------------------|---------------------|
| monitor                              | $action_monitor     |
| add to meta + H1                     | $action_add_meta_h1 |
| rewrite meta cluster                 | $action_rewrite     |
| patch missing slots                  | $action_patch       |
| no GSC data — investigate            | $action_no_gsc      |

## En yüksek impressions

- **URL:** $top_url
- **Hedef sorgu:** $top_target_query
- **Impressions (30d):** $top_impressions
- **Clicks (30d):** $top_clicks
- **Önerilen aksiyon:** $top_action

## Kanıt zinciri

- DFS raw payload: `$raw_dfs_path`
- GSC raw payload: `$raw_gsc_path`
- Run ID: `$run_id`
- Yazılan satır sayısı: `on_page_audit=$rows_on_page_audit`

> Üretildi: `on-page-audit` skill — `scripts/discovery/on_page_audit_transform.py`
