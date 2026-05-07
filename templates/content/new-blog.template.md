---
template_kind: new-blog-skeleton
template_version: 1.0
applied_to: [new-blog]
source_rules: [content-quality, content-html-discipline, content-seo-discipline, content-eeat-discipline, content-llm-discipline]
---

# New Blog Template (Markdown Skeleton — Planning Only)

Bu template **planlama amaçlı** markdown skeleton. Asıl yayın HTML (`new-blog.template.html`) — bu doc skill'in workflow'unun planning step'inde tüketilir (R-20 reuse: yayın markdown DEĞİL).

## Frontmatter (Skill Output Header)

```yaml
project_id: {{PROJECT_ID}}                     # project.config.json[project_id], R-XX naming
slug: {{URL_SLUG}}                              # master.xlsx[new_content_plan].url_slug
target_word_count: {{TARGET_WORD_COUNT}}        # master.xlsx[new_content_plan].target_word_count, R-12
intent: {{INTENT}}                              # master.xlsx[cluster_keywords].intent, R-10
page_type: {{PAGE_TYPE}}                        # master.xlsx[topical_map].page_type (pillar/cluster/supporting), R-11
brand_style:
  primary_color: {{PRIMARY_COLOR}}              # project.config.json[brand_identity.primary_color], R-23
  font_heading: {{FONT_HEADING}}                # brand_identity.font_family_heading
  font_body: {{FONT_BODY}}                      # brand_identity.font_family_body
profiles: {{PROFILES_ARRAY}}                    # project.config.json[profiles], Principle 2
primary_keyword: {{PRIMARY_KEYWORD}}            # cluster_keywords primary, R-12
secondary_keywords: {{SECONDARY_KEYWORDS_3_7}}  # cluster_keywords secondary 3-7, R-12
```

## Structure Outline (Heading Plan)

```
H1: {{TITLE}}                                                            # R-04 yasak sembol kontrol (`:` `-` yok), R-03 H1 tek
  intro paragraph (40-60 word AEO friendly, R-01)                        # cevap-önce, self-contained R-101
  pse-tldr aside (opsiyonel, R-29)                                       # 3-5 bullet özet

H2: {{SECTION_1_TITLE}}                                                  # R-04 sembol kontrol
  pse-h2-answer mini paragraph (1-2 cümle direkt cevap, R-29 + R-101)    # AIO citation candidate
  H3: {{SUBSECTION_1.1}}                                                 # R-30 zorunluluk: H2 word > 200 → min 2 H3
  H3: {{SUBSECTION_1.2}}
  liste (per H2 max 1, R-07 + Principle 3)                              # opsiyonel
  internal link (R-06: per ~300 word 1 link)                             # master.xlsx[internal_links]
  citation (R-106: per 500 word min 1 max 2)                             # external sources

H2: {{SECTION_2_TITLE}}
  pse-h2-answer mini paragraph
  H3: {{SUBSECTION_2.1}}
  table (per ~1000 word 1 tablo, R-07; data-rich + cite-friendly)        # AIO citation
  ...

[YMYL profile only:]
H2: Karşı Argümanlar                                                    # R-50 zorunlu (R-115 superseded)
  counter-argument paragraph + balanced view

[YMYL medical/legal/financial profile only:]
disclaimer block (project.config.json[content_settings.disclaimer_templates], R-51)

H2: Sıkça Sorulan Sorular (FAQ)                                         # R-09: 10 standart, 3000+ word 15 cap
  10 Q&A (snippet-friendly, statik visible R-43)                        # FAQPage schema R-79

[Pre-CTA]
pse-key-takeaways aside (3-5 bullet başlıksız, R-102)                   # AI summary footer

CTA paragraph (doğal akış, R-26 + R-05)                                 # "Sonuç" başlığı YASAK
```

## Image Plan (R-71..R-77 + generate-images Skill Handoff)

```yaml
hero_image:
  prompt: "{{HERO_PROMPT_8K_ULTRA_REALISTIC}}"   # R-71 quality, R-72 model nano-banana
  alt_text: "{{HERO_ALT_TEXT_60_125_CHAR}}"       # R-77, descriptive non-stuffing
  filename: outputs/images/{{SLUG}}-hero.{{EXT}}  # R-73 manual upload path
  schema_url_placeholder: "{{IMAGE_URL_REPLACE}}" # R-73 manual upload step
inline_images:
  - section_id: section_1
    prompt: "..."
    alt_text: "..."
```

## SERP Analiz Reference (R-08 Pre-Write Step)

```yaml
serp_analysis_path: inbox/serp-analysis/{{DATE}}-{{KEYWORD_NORMALIZED}}.json
top_5_themes: [{{THEME_1}}, {{THEME_2}}, ...]
content_gap: [{{GAP_1}}, {{GAP_2}}, ...]
serp_features: [{{snippet|aio|paa|image_pack|video_pack|knowledge_panel}}]   # R-113
```

## Citation Plan (R-106 + R-44 + R-114)

```yaml
citations:
  - source_url: "{{URL}}"
    source_name: "{{NAME}}"
    claim_anchor: "{{CLAIM}}"            # R-44: claim cite edilen sayfada literal mevcut
    domain_authority: {{DA_SCORE}}       # R-37 profile-aware threshold
original_research:                        # R-114 bank-driven, project.config.json[content_settings.original_research_database]
  - {{RESEARCH_REF}}
expert_quotes:                            # R-105 bank-driven, project.config.json[content_settings.experience_database]
  - {{QUOTE_REF}}
```

## Acceptance Gate Checklist (Phase 11 — Pre-Publish)

- [ ] H1 tek (R-03)
- [ ] Heading'lerde `:` `-` yok (R-04)
- [ ] "Sonuç/Özet/Conclusion" başlığı yok (R-05)
- [ ] Intro AEO uyumlu 40-60 word (R-01) + self-contained (R-101)
- [ ] Per-H2 cevap-önce mini paragraf (R-29)
- [ ] H2 word > 200 → min 2 H3 (R-30)
- [ ] H2 keyword density %40-60 (R-30)
- [ ] FAQ 10 (3000+ word 15 cap) statik visible (R-09 + R-43)
- [ ] Per-H2 max 1 liste (R-07 + Principle 3)
- [ ] Per ~1000 word 1 tablo (R-07)
- [ ] Per ~300 word 1 internal link, dupe yok (R-06)
- [ ] Per 500 word 1-2 citation (R-106)
- [ ] Bold per ~250 word (R-13)
- [ ] CTA doğal akış (R-26)
- [ ] Profile=ymyl ise: counter-argument H2 (R-50, R-115 superseded) + author byline (R-28) + disclaimer (R-51)
- [ ] Citation 3-katman doğrulama (R-44)
- [ ] R-08 SERP analiz tamamlandı
- [ ] R-15 site gerçeği doğrulama (master.xlsx[crawl_sitemap] + dataforseo_on_page_content_parsing)
- [ ] AI signature words density ≤ 1/1000 word (R-118)
- [ ] Uniqueness check ≥ 70% (R-117)
- [ ] Stats density profile threshold (R-104)
