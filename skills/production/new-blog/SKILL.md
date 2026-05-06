---
name: new-blog
description: |
  Use when: kullanıcı "yeni blog yaz", "blog üret", "content gen", "blog
  draft", "makale yaz", "yeni içerik üret", "new blog post", "pillar yaz",
  "cluster yaz" der ya da /pseo-new-blog çağırır; master.xlsx[new_content_plan]
  satırından plan al, SERP analiz yap, 5 template render et, JSON-LD @graph
  5 entity üret, Foundational Principles 3-katman (truth-verifiable +
  profile-aware + anti-cheap-content) enforce et.
  Also use when: master.xlsx[topical_map] içinde assigned_url=null olan
  pillar/cluster/supporting satırı için ilk içerik üretilecek; new_content_plan
  satırının lifecycle_status=GREEN ya da PLANNED durumda; mode='draft'
  (review) veya 'publish' (immediate) seçildi; profile-aware switch tetik
  (project-config[profile] ya da project-config[profiles] priority merge).
  Do not use when: mevcut blog revize için (revise-content kullan); FAQ
  block re-render için (faq-optimization kullan); decay/sunset/prune için
  (content-remediation kullan); image generation için (generate-images
  kullan); manuel WordPress upload için (Section A upload-instructions
  template render edilir, skill upload yapmaz); master.xlsx eksikse
  (init-project önce çalışmalı, DURUR #1).
version: "1.0"
status: active
category: production
inputs:
  project_slug:        { type: string,  required: true,  description: "Workspace proje slug'ı (örn 'projeA'). projects/{slug}/ dizinine map edilir." }
  new_content_plan_id: { type: string,  required: true,  description: "master.xlsx[new_content_plan] row id reference (kolon A)." }
  mode:                { type: string,  required: false, default: "draft", description: "Output mode — 'draft' (review öncesi) veya 'publish' (immediate). Enum dışı değer DURUR #5." }
outputs:
  - "outputs/blog/{slug}/article.html"
  - "outputs/blog/{slug}/schema.jsonld"
  - "outputs/blog/{slug}/meta-tags.json"
  - "outputs/blog/{slug}/upload-instructions.md"
  - "_state/events.jsonl"
consumes:
  - "init-project:master.xlsx[new_content_plan]"
  - "init-project:master.xlsx[cluster_keywords]"
  - "init-project:master.xlsx[topical_map]"
  - "init-project:project-config[profile]"
  - "init-project:project-config[content_settings]"
  - "init-project:project-config[brand_identity]"
  - "rules/content-quality.md"
  - "rules/content-html-discipline.md"
  - "rules/content-seo-discipline.md"
  - "rules/content-eeat-discipline.md"
  - "rules/content-llm-discipline.md"
  - "rules/content-update-discipline.md"
  - "templates/content/new-blog.template.md"
  - "templates/content/new-blog.template.html"
  - "templates/content/faq-block.template.html"
  - "templates/content/upload-instructions.template.md"
produces:
  - "content-remediation"
  - "faq-optimization"
  - "generate-images"
  - "indexing-ping"
triggers:
  manual: ["/pseo-new-blog"]
  natural_language: |
    "yeni blog yaz", "blog üret", "content gen", "blog draft",
    "makale yaz", "yeni içerik üret", "new blog post yaz",
    "pillar yaz", "cluster yaz", "supporting içerik yaz"
  hooks: []
  scheduled: []
mcp_tools:
  required:
    - "mcp__gsc__search_analytics"
    - "mcp__dataforseo__serp_organic_live_advanced"
  optional:
    - "mcp__ScraplingServer__stealthy_fetch"
    - "mcp__dataforseo__dataforseo_labs_google_keyword_overview"
budget:
  uses_paid_mcp: true
  estimated_credits: 8
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# new-blog — production skill (Phase 11 Wave 1, W-F1)

Plan-driven full-article generator. Reads a single
`master.xlsx[new_content_plan]` row, joins it against
`master.xlsx[cluster_keywords]` (keyword set + intent + forbidden filters)
and `master.xlsx[topical_map]` (pillar/cluster/supporting page_type +
internal-link plan), runs SERP top-10 + optional Tier-1 Scrapling
deepening, then renders four artifacts:

1. `outputs/blog/{slug}/article.html` — `<article class="pse-blog-post">`
   fragment (R-22 fragment boundary; no `<html>` / `<body>` wrap).
2. `outputs/blog/{slug}/schema.jsonld` — JSON-LD `@graph` with 5
   entities (Article + Organization + Person + BreadcrumbList +
   FAQPage; R-78..R-83).
3. `outputs/blog/{slug}/meta-tags.json` — meta title (≤540 mobil
   pixel) + meta description (≤680 mobil pixel) + OpenGraph + Twitter
   card pack.
4. `outputs/blog/{slug}/upload-instructions.md` — Section A new-blog
   manuel WordPress upload workflow (R-74); skill itself does NOT
   publish.

The skill is **READ-ONLY** with respect to `master.xlsx`
(`new_content_plan` allowed_writers is `null` — F-1 schema authority,
verified pre-flight). It never calls `transaction.append`,
`transaction.update`, or `transaction.delete` against the workbook.
The only state mutation is the audit append to `_state/events.jsonl`
with `event_type=content_new`.

## Inputs (frontmatter contract)

| Name                  | Type   | Default | Notes                                                                         |
|-----------------------|--------|---------|-------------------------------------------------------------------------------|
| `project_slug`        | string | —       | Required. `projects/{slug}/` workspace root.                                  |
| `new_content_plan_id` | string | —       | Required. Row id (kolon A) in `master.xlsx[new_content_plan]`.                |
| `mode`                | string | `draft` | `draft` (review) or `publish` (immediate). Other values → DURUR #5.           |

## Outputs (artifacts produced)

- `outputs/blog/{slug}/article.html` — schema-markup-aware, WCAG 2.1 AA
  compliant, BEM `pse-` CSS class prefix HTML article fragment.
- `outputs/blog/{slug}/schema.jsonld` — JSON-LD `@graph` 5 entity
  (Article + Organization + Person + BreadcrumbList + FAQPage).
- `outputs/blog/{slug}/meta-tags.json` — meta title (≤540 px) + meta
  description (≤680 px) + OG + Twitter pack.
- `outputs/blog/{slug}/upload-instructions.md` — Section A new-blog
  WordPress manual upload steps (R-74).
- `_state/events.jsonl` — audit append, `event_type=content_new`,
  `event_kind=work` (events.schema enum: provenance / work / audit /
  workflow), `schema_version=1.0`.

## Foundational Principles Enforcement (3-Layer)

The 3 üst-prensip (Phase 10 `rules/content-quality.md#foundational-principles`)
gate this skill end-to-end. No alt-rule (R-01..R-122) overrides them.

### Principle 1 — Truth-Verifiable Content (R-27, Süleyman 5x vurgu)

**Statement.** Tüm content/source/link/data %100 doğru ve kanıtlanabilir;
uydurma yasak (kaynak, hikaye, case study, fiyat, stat, ürün/feature/
image-link).

**3-katman defense (Step 8 implements):**
- Layer 1: skill prompt explicit "uydurma yasak" başlangıçta — Step 7
  generation öncesi system note inject.
- Layer 2: post-generate fact-check pass — her claim için
  `content_settings.original_research_database` + SERP top-10 source
  match; citation count ≥ R-44 threshold.
- Layer 3: citation enforce — R-44 source verification 3-katman + R-105
  expert quote bank-driven (`content_settings.experience_database`
  lookup, uydurma quote yasak).

**Failure mode:** RED — yayın iptal, çıktı discard. DURUR #6 trigger.

### Principle 2 — Profile-Aware Enforcement

**Statement.** Skill behavior `project.config.json[profile]` enum'una
göre değişir (singular field, Phase 11 W-F1 cascade fix). When `profile`
is unset, fall back to `profiles[]` priority merge per
`rules/content-quality.md` Principle 2 tablosu.

**Enum 5-value:** `e-commerce` / `ymyl` / `local-service` / `b2b-saas` /
`portfolio`.

**Switch logic (Step 2 + Step 7 + Step 8):**

| Boyut                      | YMYL                       | e-commerce        | b2b-saas          | local-service       | portfolio  |
|----------------------------|----------------------------|-------------------|-------------------|---------------------|------------|
| Author byline (R-28)       | Zorunlu                    | Yok               | Esnek             | Esnek               | Yok        |
| Tone                       | semi-pro + siz             | conversational+sen| formal + siz      | conversational+siz  | esnek      |
| Word count                 | 1500–4000                  | 800–2500          | 1800–3500         | 1000–2500           | 800–2000   |
| Counter-argument (R-50)    | Zorunlu                    | Skip              | Opsiyonel         | Skip                | Skip       |
| Disclaimer (R-51)          | medical/legal/financial    | Skip              | Opsiyonel         | Skip                | Skip       |
| Image style                | clean-illustration         | product-photo     | diagram-screenshot| location-photo      | esnek      |
| Stats density (R-104)      | min 3 / 1000 word          | min 1 / 800 word  | min 2 / 600 word  | esnek               | esnek      |

**Failure mode:** AMBER — wrong profile resolution worker raporlar; RED
ancak `profile` enum dışı (DURUR #2).

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Content, 7-pattern gate)

**Statement.** AI'ın doğal cheap content padding davranışını preempt et.

**7-pattern gate (Step 8 implements):**
- H3 zorunluluk gate — H2 word count > 200 → min 2 H3 (R-30).
- Heading keyword density %40–60 — primary_keyword count / total heading
  count (hard cap, R-30 stuffing önleme).
- Citation density per 500 word 1-2 (R-106).
- FAQ count 10 sabit / 3000+ word 15 cap (R-09).
- Stats density profile-aware min/max (R-104, tablo yukarıda).
- Per-H2 list cap 1 (R-07; multi-list AI padding önleme).
- AI signature humanize — `brand_identity.tone_phrases_blocklist`
  consume + replace pattern ("Aslında", "Sonuç olarak", "Özetle",
  R-118).

**Failure mode:** AMBER warning (auto-correct attempt) → RED fail
(manuel revise). 2x AMBER aynı pass → RED upgrade.

## Routing — 12-Step Workflow

> Step names are stable identifiers across runs (used as
> `steps[*].name` when the skill calls `workflow_runner.create_run`).

### Step 1 — `read_master_xlsx`

`master.xlsx[new_content_plan]` row read where
`id == {input.new_content_plan_id}`. `master.xlsx[cluster_keywords]`
filter where `assigned_url == new_content_plan.url_slug`.
`master.xlsx[topical_map]` filter where
`pillar == new_content_plan.assigned_cluster` OR
`cluster == new_content_plan.assigned_cluster`.

Workbook opens with `openpyxl.load_workbook(read_only=True)`. F-1
allowed_writers=null discipline: skill MUST NOT call
`transaction.append`, `transaction.update`, or `transaction.delete`.

`new_content_plan` 14 columns consumed:
`id, title, url_slug, primary_keyword, monthly_volume, assigned_cluster,
target_word_count, priority, created_date, tivl_tag, lifecycle_status,
image_prompt, alt_text, content_type` (Phase 10 additive bump).
`content_type` enum: `[listicle, guide, comparison, research, tutorial,
review]`.

`cluster_keywords` 11 columns consumed: `cluster, keyword,
monthly_volume, data_source, assigned_url, gsc_clicks, gsc_impressions,
gsc_position, intent, forbidden_kw, forbidden_reason`. `intent` enum:
`[Informational, Commercial, Transactional, Navigational]`.

`topical_map` 10 columns consumed: `pillar, cluster, primary_keyword,
monthly_volume, data_source, assigned_url, page_type, status, priority,
note`. `page_type` enum: `[pillar, cluster, supporting]`.

**DURUR #1.** master.xlsx eksik → init-project skill önce çalışmalı.

### Step 2 — `read_project_config` (Profile-Aware Switch)

`projects/{slug}/project.config.json` parse. Singular `profile` field
(schema v1.2, Phase 11 W-F1 cascade fix) is the dominant Principle 2
switch; when missing, fall back to `profiles[]` priority merge per
`rules/content-quality.md` Principle 2 tablo.

`content_settings` 14 fields consumed (Phase 10): `toc_strategy,
related_posts_strategy, author_strategy, css_strategy, indexnow_enabled,
ai_training_optin, video_integration, internal_data_sharing,
external_uniqueness_check, original_research_database,
experience_database, video_database, disclaimer_templates, image_model`.

`brand_identity` 18 fields consumed (Phase 10): `logo_url, primary_color,
secondary_color, accent_color, font_family_heading, font_family_body,
header_template_id, footer_template_id, source_url_for_sampling, tone,
hitap, anglicism_tolerance, tone_phrases_blocklist, font_heading,
font_body, default_hero_url, same_as_urls, image_style`.

**DURUR #2.** Singular `profile` enum dışı bir değere sahipse RED;
schema v1.2 cascade fix uygulanmadıysa (`schema_version != "1.2"` ve
profile field schema'da yok) önce `scripts/migrations/0002_project_
config_1.1_to_1.2.py` çalışmalı.

### Step 3 — `serp_analysis` (R-08)

`mcp__dataforseo__serp_organic_live_advanced` çağrı:
`keyword=new_content_plan.primary_keyword`, `depth=10`. Top-10 sonuç +
entity extract (organic results `dom_url`, `title`, `description`).

**DURUR #5.** SERP analiz fail (boş response, API error, mode enum dışı)
→ manuel input gerekli, skill `awaiting_approval`.

### Step 4 — `scrapling_tier1_optional` (R-08 derinleştirme)

Top-3 SERP page için `mcp__ScraplingServer__stealthy_fetch` çağrı. DOM
parse → H1/H2/H3 + first 200 word + author byline + dateModified
extract. AMBER warning: tier-1 fail ise tier-0 fallback (basic SERP
description).

### Step 5 — `aio_citation_check` (R-109/R-110/R-111)

Pasaj alıntılanabilirlik: SERP top-10 page'lerde featured snippet detect
(R-109), people_also_ask (R-110), ai_overview citation (R-111). Skill
internal state: `aio_citation_targets[]`.

### Step 6 — `content_gap`

`cluster_keywords[forbidden_kw]` negatif filter (forbidden_reason
kontrol). `topical_map` gap detect: `status == 'planned' AND
assigned_url == null`. Internal link plan: relevant
`topical_map[pillar/cluster]` URL'leri article body içinde reference
(per ~300 word 1 link, R-06).

### Step 7 — `render_5_templates`

5 template render-time slot consume (4 file + 1 internal upload section):

1. `templates/content/new-blog.template.md` — markdown skeleton
   (frontmatter + H1/H2/H3 outline). Planning-only, NOT yayınlanır.
2. `templates/content/new-blog.template.html` — HTML article fragment
   (`<article class="pse-blog-post">` kök, R-22 fragment boundary).
3. `templates/content/faq-block.template.html` — 10 FAQ statik R-43
   (accordion `<details>` + `<summary>` YASAK, R-43 statik HTML zorunlu).
4. `templates/content/upload-instructions.template.md` — Section A
   new-blog kısmı.

Render-time slot dictionary:

| Slot                 | Source                                                           |
|----------------------|------------------------------------------------------------------|
| `{primary_keyword}`  | `new_content_plan.primary_keyword`                               |
| `{tone}`             | `brand_identity.tone` (Principle 2 profile-aware override)       |
| `{hitap}`            | `brand_identity.hitap`                                           |
| `{primary_color}`    | `brand_identity.primary_color`                                   |
| `{font_heading}`     | `brand_identity.font_heading` (alias to font_family_heading)     |
| `{font_body}`        | `brand_identity.font_body`                                       |
| `{author}`           | `content_settings.author_strategy` switch (YMYL byline-required) |
| `{disclaimer}`       | `content_settings.disclaimer_templates[profile_kind]`            |
| `{default_hero_url}` | `brand_identity.default_hero_url` (R-77 fallback)                |
| `{image_style}`      | `brand_identity.image_style` (Principle 2 profile-aware)         |

CSS class prefix: `pse-` BEM (plugin agnostik — proje slug
hardcode YASAK, e.g. `demo-dental`/`demo-furniture`/`demo-hvac`/`demo-petcare`/`demo-shop`/
`demo-tires`/`demo-construction`/`demo-agency` slug'lar HTML/CSS içinde geçemez).

### Step 8 — `foundational_principles_gate`

3-katman gate çalışır (Principle 1 + 2 + 3 yukarıda detaylı). Çıktı:
P1 RED → DURUR #6; P2 enum dışı → DURUR #2; P3 7-pattern AMBER 2x →
RED upgrade.

### Step 9 — `render_jsonld_graph` (R-78..R-83)

JSON-LD `@graph` 5 entity render:

- `Article` — `headline, description, datePublished, dateModified,
  author (Person ref), publisher (Organization ref), image, mainEntityOfPage`.
- `Organization` — `name, logo (logo_url), sameAs (same_as_urls;
  R-100)`.
- `Person` — `name, jobTitle, knowsAbout` (`author_strategy` switch,
  R-105 expert quote bank-driven `content_settings.experience_database`
  lookup; uydurma yasak — Principle 1 Layer 3).
- `BreadcrumbList` — Home > Pillar > Cluster > Article (R-83 4-level
  cap).
- `FAQPage` — 10 FAQ Q&A items (R-79; 3000+ word blog → 15 cap, R-09).

Validate: Google Rich Results Test API mock validate (skill internal —
actual API call optional). DURUR #8 trigger: REJECT → schema fix önce.

### Step 10 — `meta_pixel_wcag_validate`

Meta title pixel calc: ≤540 mobil (Türkçe karakter ağırlıklı, ~60–65
char ortalama). Meta description pixel calc: ≤680 mobil (~155–160 char
ortalama). DURUR #7 trigger: cap aşımı → auto-correct attempt; fail
ise manuel revise.

WCAG 2.1 AA axe-core simulate: violations=0 hedef. Color contrast
(`primary_color` vs background) ≥ 4.5:1. Image alt text required
(`new_content_plan.alt_text` consume; uydurma alt-text yasak —
Principle 1).

### Step 11 — `write_outputs`

4 artefact yaz:

- `outputs/blog/{slug}/article.html` — `<article class="pse-blog-post">`
  kök, R-22 fragment boundary.
- `outputs/blog/{slug}/schema.jsonld` — JSON-LD `@graph`.
- `outputs/blog/{slug}/meta-tags.json` — meta title/description/OG/
  Twitter pack.
- `outputs/blog/{slug}/upload-instructions.md` — Section A WordPress
  media library workflow (R-74).

### Step 12 — `emit_provenance`

`_state/events.jsonl` append (audit):

| Field            | Value                                          |
|------------------|------------------------------------------------|
| `event_type`     | `content_new`  (events.schema F-8 enum)        |
| `event_kind`     | `work`         (events.schema enum, ADR-020)   |
| `schema_version` | `1.0`                                          |
| `actor`          | `skill:new-blog`                               |
| `target`         | `master.xlsx[new_content_plan]#{id}`           |
| `timestamp`      | UTC ISO 8601                                   |
| `mode`           | `input.mode` (`draft` / `publish`)             |

## DURUR Conditions (8)

| #  | Trigger                                               | Resolution                                           |
|----|-------------------------------------------------------|------------------------------------------------------|
| 1  | master.xlsx eksik                                     | init-project önce çalışmalı (Phase 5 W-Q paterni)    |
| 2  | project-config[profile] enum dışı / schema v1.2 yok    | scripts/migrations/0002_project_config_1.1_to_1.2.py |
| 3  | 6 rules dosyası eksik                                 | Phase 10 deliverable verify (e4369ea commit)         |
| 4  | MCP budget aşımı (estimated_credits 8)                 | scripts/budget/check_budget.py blocked               |
| 5  | SERP analiz fail (R-08, mode enum dışı)               | manuel input, awaiting_approval                      |
| 6  | P1 fact-check fail                                    | RED — çıktı discard, claim revize                    |
| 7  | meta pixel cap aşımı                                  | auto-correct fail ise manuel revise                  |
| 8  | Schema Rich Results Test REJECT                       | JSON-LD `@graph` fix önce                            |

## Cascade Fix W-F1 (Phase 10 EKSİĞİ Closure — Atomic Commit Içinde)

Phase 10 finished without `project-config[profile]` (singular) which
Foundational Principle 2 directly cites. Phase 11 W-F1 closes that gap
in the SAME atomic commit as the new-blog skill itself, so this skill
ships with a schema-valid Principle 2 contract from day one.

**File 1 — `schemas/project-config.schema.json`:**
- `schema_version` `"1.1"` → `"1.2"`.
- `properties.profile` added (singular, enum 5-value:
  `e-commerce` / `ymyl` / `local-service` / `b2b-saas` / `portfolio`).
- `required[]` UNCHANGED (additive policy →
  `rules/schema-versioning-discipline.md`).

**File 2 — `scripts/migrations/0002_project_config_1.1_to_1.2.py`:**
- 0001 paterni reuse (idempotent + dry-run + `.bak` backup).
- Refuses out-of-range source versions; pure `migrate(doc) -> dict`
  function for tests.

**File 3 — `scripts/state/bootstrap_project.py`:**
- `SCHEMA_VERSION = "1.1"` → `"1.2"` constant update.

**File 4 — `tests/skills/test_init_project.py`:**
- `schema_version` assertion `"1.1"` → `"1.2"`.
- Asserts schema declares `profile` field with the exact enum 5-value.

**Smoke test (cascade fix verify):**

```bash
python3 scripts/migrations/0002_project_config_1.1_to_1.2.py \
    --in /tmp/test_config.json --dry-run
jq '.properties.schema_version.const' schemas/project-config.schema.json
jq '.properties.profile.enum'         schemas/project-config.schema.json
```

Expected: schema_version `"1.2"`, profile.enum array of 5 strings.

## Plugin-Agnostic Discipline

- No project slug hardcoded inside this skill or its templates
  (`demo-dental`, `demo-furniture`, `demo-hvac`, `demo-petcare`, `demo-shop`, `demo-tires`,
  `demo-construction`, `demo-agency` are FORBIDDEN tokens — pytest grep verifies).
- CSS class prefix `pse-` BEM only (`pse-blog-post`, `pse-h2-answer`,
  `pse-tldr`, `pse-faq-block`).
- Brand styling resolves at render-time from `brand_identity` (per-
  project), never via hardcoded color/font.
- Per-call / per-url credit shape names (Phase 7 lesson, ADR-028 anti-
  pattern) MUST NOT appear in this skill — `budget.estimated_credits`
  (number) is the only allowed shape per skill-frontmatter schema.

## Error Handling

| Failure                          | Mode  | Action                                                                |
|----------------------------------|-------|-----------------------------------------------------------------------|
| master.xlsx schema drift         | RED   | DURUR #1, init-project re-run                                         |
| project-config[profile] dışı     | RED   | DURUR #2, cascade fix verify                                          |
| MCP DataForSEO budget exhausted  | RED   | DURUR #4, budget gate                                                 |
| Tier-1 Scrapling 403 / blocked   | AMBER | tier-0 SERP description fallback                                      |
| P1 citation missing              | RED   | DURUR #6, claim revize                                                |
| P3 7-pattern AMBER 2x same pass  | RED   | manuel revise                                                         |
| meta pixel cap > 540 / 680       | AMBER | auto-correct → fail RED                                               |
| Schema Rich Results REJECT       | RED   | DURUR #8, `@graph` fix                                                |

## References

- `rules/content-quality.md` (Foundational Principles, R-01..R-122).
- `rules/content-html-discipline.md` (R-22 fragment, R-23 inline CSS,
  R-43 statik FAQ, R-77 fallback hero).
- `rules/content-seo-discipline.md` (R-08 SERP, R-78..R-83 schema).
- `rules/content-eeat-discipline.md` (R-28 byline, R-44 source verify,
  R-105 expert quote, R-114/R-119 research bank).
- `rules/content-llm-discipline.md` (R-109..R-111 AIO citation, R-118
  humanize).
- `rules/content-update-discipline.md` (R-50 counter-argument).
- `schemas/project-config.schema.json` v1.2 (Phase 11 W-F1 cascade fix).
- `schemas/master-excel.schema.json` (18 sheets — `internal_links` and
  `content_gaps` are NOT among them; F-4 schema authority).
- `schemas/events.schema.json` (event_type enum 10 values, event_kind
  enum 4 values).
- `schemas/skill-frontmatter.schema.json` (8 required fields, category
  enum 8 values, status enum 3 values).
- ADR-020 (event_kind=workflow vs work routing).

## Wave-Out Note

This skill is `status: wip` until Phase 11 Wave 2 acceptance gate;
`active` bump deferred to the post-Wave 1 closeout. Manager owns the
status flip + governance audit.
