---
template_kind: revise-content-skeleton
template_version: 1.0
applied_to: [revise-content]
source_rules: [content-update-discipline, content-quality, content-seo-discipline]
---

# Revision Template (Section-Targeted Diff Skeleton)

Bu template revise-content skill'in workflow'unu yönlendirir. Section-targeted revise (R-87) — full-rewrite YASAK default. Foundational Principle 1 (Truth-Verifiable, R-88 freshness theater yasak) + Principle 3 (Anti-Cheap-Content) zorunlu.

## Step 1: Mevcut Content Snapshot

```yaml
existing_url: {{EXISTING_URL}}                      # master.xlsx[content_decay].url veya manual
existing_html_fetch:                                 # dataforseo_on_page_content_parsing veya local cache
  fetched_at: {{ISO_8601_UTC}}
  content_html: <stored snapshot>                    # full HTML kaydedilir audit trail için
existing_meta:
  title: {{CURRENT_META_TITLE}}
  description: {{CURRENT_META_DESCRIPTION}}
  date_modified: {{CURRENT_DATE_MODIFIED}}
  canonical: {{CURRENT_CANONICAL}}                   # R-89 IMMUTABLE on revise
  content_version: v{{CURRENT_VERSION}}              # R-103
existing_metrics:                                    # master.xlsx[gsc_performance] + content_decay
  gsc_clicks_90d: {{CLICKS_90D}}
  gsc_position_avg: {{POSITION_AVG}}
  decay_signal: {{DECAY_THRESHOLD_BREACH}}           # R-85 multi-signal
```

## Step 2: Diff Hedef (Section-Targeted)

```yaml
diff_target_scope: section                           # R-87: section-targeted ZORUNLU, full-rewrite YASAK
revise_kind: {{minor|major}}                          # > 30% content change → major (R-103 version increment)
target_sections:
  - section_id: {{H2_HEADING_NORMALIZED}}
    action: {{add|update|remove}}
    rationale: {{WHY_THIS_SECTION_NEEDS_REVISION}}    # decay signal mapping (R-85, R-86)
    new_content: |
      {{NEW_CONTENT_HTML_SECTION_FRAGMENT}}
  - section_id: ...
```

## Step 3: change_summary (R-87 Required Log)

```yaml
change_summary:
  added_sections: [{{H2_TITLES}}]
  updated_sections: [{{H2_TITLES}}]
  removed_sections: [{{H2_TITLES}}]
  added_word_count: {{N}}
  removed_word_count: {{N}}
  net_word_diff: {{NET}}
  citations_added: {{N}}
  citations_removed: {{N}}
  internal_links_changed: {{N}}
  schema_markup_changes: [{{ARTICLE_DATEMODIFIED, FAQPAGE_REFRESH, ...}}]
  rationale: |
    {{HUMAN_READABLE_DECAY_TO_REVISE_NARRATIVE}}
  approved_by: {{USER_HANDLE}}                        # R-86 manual approve gate
  approved_at: {{ISO_8601_UTC}}
```

## Step 4: Canonical + dateModified Update (R-89)

```yaml
canonical: {{CURRENT_CANONICAL}}                      # IMMUTABLE — değiştirilmez
date_modified_new: {{NEW_ISO_8601_EUROPE_ISTANBUL_TO_UTC}}   # R-89 ISO 8601, time-discipline cross-link
content_version_new: v{{INCREMENT_IF_MAJOR}}          # R-103 major revise
```

## Step 5: R-88 Freshness Theater Anti-Pattern Check

PRE-COMMIT zorunlu kontrol — bu check FAIL ederse revise reject:

- [ ] `change_summary.net_word_diff` ≥ 50 word (sadece tarih bump değil)
- [ ] `change_summary.added_sections` + `updated_sections` ∪ ≥ 1 (gerçek section değişimi)
- [ ] `dateModified` update'i content diff olmadan TEK BAŞINA reject (R-88 RED)
- [ ] Yeni content R-118 AI signature words density ≤ 1/1000 word
- [ ] Yeni content R-117 uniqueness ≥ 70% (paragraph shingling vs SERP top-10)

## Step 6: Acceptance Gate Checklist (Phase 11 — Pre-Publish)

- [ ] R-87 section-targeted scope (full-rewrite değil)
- [ ] R-88 net_word_diff ≥ 50 + added/updated section ≥ 1
- [ ] R-89 canonical immutable, dateModified ISO 8601
- [ ] R-86 user explicit approve audit trail (`change_summary.approved_by`)
- [ ] R-87 change_summary `events.jsonl` veya `master.xlsx[completed_work].note` log
- [ ] R-103 major revise → content-version increment + content-version meta tag
- [ ] R-78..R-84 schema markup re-render (Article.dateModified updated)
- [ ] R-58 lifecycle robots meta (lifecycle_status değişmediyse no-op)
- [ ] Content diff scope master.xlsx[content_decay].action = `pending_approve` → `approved` flip
- [ ] Yeni content R-01..R-13 + R-29 + R-30 SEO disiplini kontrolü
- [ ] R-117 uniqueness ≥ 70%, R-118 AI signature ≤ 1/1000 word
