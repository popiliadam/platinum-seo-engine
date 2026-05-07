---
template_kind: manual-upload-instructions
template_version: 1.0
applied_to: [new-blog, generate-images, revise-content]
source_rules: [content-html-discipline, content-seo-discipline]
---

# Manual Upload Instructions (Multi-Skill Collaborative Output)

Bu template **multi-skill collaborative output** (R-74 paterni). Her skill kendi section'ını append eder; user (Süleyman) bu doc'u okuyup WordPress/Ticimax/Ideasoft media library + post editor'a manuel yükler. Auto-upload yasak — credential exposure + plugin agnostik (R-73).

## Section A — new-blog Skill Output (Required Fields)

Skill bu section'ı önce yazar. User WordPress post editor'a şu alanları kopyalar:

```yaml
post_metadata:
  meta_title: "{{META_TITLE_PIXEL_580_MAX}}"             # R-35 pixel cap, ~60 char Türkçe
  meta_description: "{{META_DESCRIPTION_PIXEL_990_MAX}}"  # R-35 pixel cap, ~155 char
  h1_title: "{{H1_TITLE_NO_COLON_NO_DASH}}"               # R-04 yasak sembol
  url_slug: "{{URL_SLUG_KEBAB_CASE}}"                     # R-XX naming kebab-case
  primary_keyword: "{{PRIMARY_KEYWORD}}"                   # cluster_keywords primary, R-12
  secondary_keywords: [{{SEC1}}, {{SEC2}}, ...]            # cluster_keywords 3-7, R-12
  intent: {{informational|commercial|transactional|navigational}}   # R-10
  cluster: "{{CLUSTER_NAME}}"                              # topical_map cluster, R-11
  pillar: "{{PILLAR_NAME}}"                                # topical_map pillar
  canonical: "{{CANONICAL_URL}}"                           # R-89 immutable on revise
  date_published: "{{ISO_8601}}"
  robots: "{{ROBOTS_DIRECTIVE}}"                           # R-58 lifecycle map
  content_version: v1                                      # R-103

post_body_html: |
  <!-- Skill output HTML fragment (article scope, R-22 master; R-57 superseded) -->
  {{FULL_HTML_BODY_FRAGMENT_FROM_NEW_BLOG_TEMPLATE}}

schema_markup_jsonld: |
  <!-- @graph array (R-78..R-84) — paste into <head> via plugin (RankMath/Yoast custom schema) -->
  {{JSON_LD_GRAPH_BLOCK}}

image_placeholders:
  - placeholder_token: "{{HERO_IMAGE_URL_REPLACE}}"
    alt_text: "{{HERO_ALT_TEXT}}"
    where: "Section/Header — hero image"
  - placeholder_token: "{{INLINE_IMAGE_1_URL_REPLACE}}"
    alt_text: "{{INLINE_1_ALT_TEXT}}"
    where: "Section 1 (H2: '{{SECTION_1_TITLE}}')"
  # ... per inline image ...
```

### Manual Upload Steps (Section A)

1. WordPress Admin → Posts → Add New
2. Title field: paste `h1_title`
3. URL slug field: paste `url_slug` (kebab-case)
4. RankMath/Yoast SEO panel: meta_title + meta_description + canonical + robots paste
5. Post body: switch to HTML/Code editor, paste `post_body_html` fragment
6. RankMath custom schema: paste `schema_markup_jsonld`
7. Save Draft (image placeholders henüz doldurulmadı, Section B'ye geç)

---

## Section B — generate-images Skill Output (Append After Section A)

generate-images skill bu section'ı new-blog skill'in output'una append eder. User hero + inline image'ları media library'ye yükler, sonra placeholder token'ları replace eder.

```yaml
images_generated:
  - kind: hero
    filename: outputs/images/{{SLUG}}-hero.{{EXT}}        # R-73 manual upload path
    prompt_used: "{{8K_ULTRA_REALISTIC_PROMPT}}"           # R-71
    model: nano-banana                                      # R-72 default
    dimensions: {width: {{W}}, height: {{H}}}              # R-62 CLS prevention
    alt_text: "{{HERO_ALT_60_125_CHAR}}"                    # R-77
    placeholder_token: "{{HERO_IMAGE_URL_REPLACE}}"        # SAME token as Section A image_placeholders
    schema_url_field: "Article.image"                       # R-78 schema slot
  - kind: inline_section_1
    filename: outputs/images/{{SLUG}}-inline-1.{{EXT}}
    prompt_used: "..."
    dimensions: {width: ..., height: ...}
    alt_text: "..."
    placeholder_token: "{{INLINE_IMAGE_1_URL_REPLACE}}"
    schema_url_field: null

picture_tag_template: |                                     # R-75 LCP optimization, R-76 fallback
  <picture>
    <source srcset="{{AVIF_URL}}" type="image/avif">
    <source srcset="{{WEBP_URL}}" type="image/webp">
    <img src="{{JPG_URL}}"
         alt="{{ALT_TEXT}}"
         width="{{W}}" height="{{H}}"
         loading="{{eager_for_hero|lazy}}"
         {{fetchpriority_high_for_hero}}>
  </picture>
```

### Manual Upload Steps (Section B)

1. Media Library → Upload `outputs/images/*.{avif,webp,jpg}` (her image 3 format)
2. Note: WordPress otomatik AVIF üretmez — manuel convert tool (Squoosh, ImageMagick) kullan
3. Media library URL'lerini kopyala
4. Post HTML'inde `{{HERO_IMAGE_URL_REPLACE}}` ve `{{INLINE_IMAGE_N_URL_REPLACE}}` token'larını gerçek URL ile replace et
5. Schema markup'ta `Article.image` field'ını hero URL ile replace
6. Alt text'leri media library'de set et (önemli — WordPress alt'ı schema'dan independent okur)

---

## Section C — revise-content Skill Output (Append on Revise Workflow)

revise-content skill **sadece** revise workflow'unda bu section'ı append eder.

```yaml
revision_metadata:
  existing_url: {{EXISTING_URL}}                            # R-89 canonical immutable
  date_modified_new: {{NEW_ISO_8601}}                       # R-89 update
  content_version_new: v{{N}}                                # R-103 increment if major
  revise_kind: {{minor|major}}
  change_summary:                                            # R-87 zorunlu log
    added_sections: [{{H2_TITLES}}]
    updated_sections: [{{H2_TITLES}}]
    removed_sections: [{{H2_TITLES}}]
    net_word_diff: {{N}}
    rationale: |
      {{HUMAN_NARRATIVE_DECAY_TO_REVISE}}
  approved_by: {{USER_HANDLE}}                               # R-86
  approved_at: {{ISO_8601}}
```

### Manual Upload Steps (Section C)

1. WordPress Posts → Edit existing post (URL: `existing_url`)
2. Body: section-targeted update (added/updated/removed sections)
3. RankMath/Yoast schema panel: `Article.dateModified` update
4. Eğer major revise: `<meta name="content-version" content="v{{N}}">` head'de update (Yoast custom code box veya theme functions.php)
5. Save (NOT "Update Date" — yalnızca content değişimi; R-88 freshness theater yasağı)
6. master.xlsx[completed_work] sheet manuel append: id, task=revise, url, date, category=revise-content, note=change_summary

---

## Verification Post-Upload

- [ ] Post canlı URL'i Schema.org Validator (https://validator.schema.org) PASS
- [ ] Google Rich Results Test PASS
- [ ] W3C HTML Validator PASS (R-59)
- [ ] Pa11y / axe-core WCAG 2.1 AA PASS (R-39)
- [ ] PageSpeed Insights LCP < 2.5s, CLS < 0.1 (R-65, R-62)
- [ ] Hero image AVIF/WebP/JPG 3 format hepsi yüklü (R-76)
- [ ] All `{{*_URL_REPLACE}}` placeholder'lar replace edildi (regex: `{{[A-Z_]+_REPLACE}}` body+schema'da 0 hit)
- [ ] meta_title pixel ≤ 580, meta_description pixel ≤ 990 (R-35)
- [ ] Internal link'ler R-06 dupe yok, count word/300 ratio
