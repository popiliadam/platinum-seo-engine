---
name: faq-optimization
description: |
  Use when: kullanıcı "FAQ optimize et", "FAQ ekle", "FAQ enhance",
  "FAQ schema yenile", "AIO citation pattern uygula" der ya da
  `/pseo-faq-optimization` çağırır. master.xlsx[content_decay] action
  trigger ya da master.xlsx[content_improve] optimization trigger;
  existing blog FAQ section enhance (mode=enhance) veya yeni blog FAQ
  add (mode=add). R-09 talep-güdümlü FAQ (kanıt varsa 3-6, hard cap 10) +
  R-43 statik (accordion YASAK) + R-29 pasaj alıntılanabilirlik gate +
  R-79 FAQPage @graph schema + R-109/R-110/R-111 AIO citation
  pattern enforce.
  Also use when: existing blog FAQ section'da AIO citation pattern
  eksik detect edildiğinde (per 500 word density 1-2 dışı); pasaj
  alıntılanabilirlik gate (R-29) fail edildiğinde (cevap-önce TL;DR
  yok); FAQPage schema markup eksik veya outdated (R-79 @graph
  Question entity boş); project-config[profile] enum 5-değer
  (e-commerce | ymyl | local-service | b2b-saas | portfolio) içinden
  biri sabit ve FAQ taxonomy profile-aware enforce edilmeli
  (Principle 2).
  Do not use when: yeni blog için (new-blog skill kullan, FAQ inline
  rendered); content prune/redirect/delete için (content-remediation
  Wave 2 domain); image generation için (generate-images kullan);
  decay action="revise" full section için (revise-content kullan,
  R-87 section-targeted); existing HTML diskte yok mode=enhance
  (DURUR #1, FAQ section parse edilemez); R-09 cap aşımı 11+ FAQ
  attempt (DURUR #2, AI suistimal Principle 3 enforce).
version: "1.0"
status: wip
category: production
inputs:
  project_slug:
    type: string
    required: true
    description: "Workspace proje slug (resolves projects/{slug}/master.xlsx + outputs/blog/{slug}/)."
  url:
    type: string
    required: true
    description: "Existing blog URL (mode=enhance) veya target URL (mode=add)."
  mode:
    type: string
    required: false
    default: "enhance"
    description: "FAQ mode — 'enhance' (existing FAQ section update) veya 'add' (yeni FAQ section ekle). Brief enum [enhance, add]."
outputs:
  - "outputs/blog/{slug}/article.html"
  - "_state/events.jsonl"
consumes:
  - "init-project:projects/{slug}/master.xlsx#new_content_plan"
  - "init-project:projects/{slug}/master.xlsx#content_decay"
  - "init-project:projects/{slug}/master.xlsx#content_improve"
  - "init-project:projects/{slug}/project.config.json"
  - "rules:rules/content-quality.md"
  - "rules:rules/content-html-discipline.md"
  - "rules:rules/content-seo-discipline.md"
  - "rules:rules/content-eeat-discipline.md"
  - "rules:rules/content-llm-discipline.md"
  - "rules:rules/content-update-discipline.md"
  - "templates:templates/content/faq-block.template.html"
produces:
  - "indexing-ping"
triggers:
  manual: ["/pseo-faq-optimization"]
  natural_language: |
    "FAQ optimize et ve AIO citation density per 500 word ayarla",
    "FAQ ekle ve R-09 talep-güdümlü 3-6 band hard cap 10 zorla",
    "FAQ enhance et ve R-29 pasaj cevap-önce TL;DR garantile",
    "FAQ schema yenile ve R-79 FAQPage @graph Question entity refresh",
    "AIO citation pattern uygula ve R-109/R-110/R-111 enforce et"
  hooks: []
  scheduled: []
mcp_tools:
  required:
    - "mcp__gsc__search_analytics"
  optional:
    - "mcp__dataforseo__serp_organic_live_advanced"
budget:
  uses_paid_mcp: true
  estimated_credits: 3
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# faq-optimization — production skill (Phase 11 Wave 2 W-F3)

FAQ optimize / enhance / add skill. master.xlsx[content_decay] action
veya master.xlsx[content_improve] optimization trigger; existing blog
FAQ section enhance (mode=enhance) veya yeni blog FAQ add (mode=add).
R-09 FAQ count cap + R-43 statik HTML render (accordion YASAK) +
R-29 pasaj alıntılanabilirlik gate + R-79 FAQPage @graph schema +
R-109/R-110/R-111 AIO citation pattern enforce. READ-ONLY contract:
master.xlsx 3 sheet (new_content_plan + content_decay +
content_improve) sadece consume; sadece outputs/ + _state yazar.

## Foundational Principles (Üst-Prensip — Alt-Rule Override Edemez)

### Principle 1 — Truth-Verifiable Content (R-27, 3-katman defense)

Tüm FAQ content/source/link/data %100 doğru ve kanıtlanabilir;
uydurma yasak (FAQ Q&A, source citation, expert quote, stat). FAQ
context'inde:

- **Layer 1 (pre-generate):** skill prompt başlangıcında "uydurma
  FAQ yasak" sentinel; her FAQ Q&A için kaynak/source field zorunlu
  (no-source → reject).
- **Layer 2 (post-generate):** fact-check pass — her FAQ Q&A için
  kaynak verify (R-44 source verification 3-katman, R-105 expert
  quote bank-driven).
- **Layer 3 (citation):** citation enforce — eklenen her stat/quote
  source URL ile bağlanır, FAQPage acceptedAnswer.text içinde citation
  reference intact.
- **Failure mode:** P1 fact-check fail → DURUR #5 RED (FAQ section
  discard, yayın iptal, dateModified bump YOK).

### Principle 2 — Profile-Aware Enforcement (project-config[profile])

Skill behavior project.config.json[profile] enum'una göre değişir.
Enum 5-value: `e-commerce` | `ymyl` | `local-service` | `b2b-saas` |
`portfolio`. FAQ context enforcement:

- `profile == "ymyl"` → R-51 disclaimer template ZORUNLU (medical/
  legal/financial), counter-argument FAQ aday (R-50 cross-link); FAQ
  section başında veya per-FAQ disclaimer present check.
- `profile == "e-commerce"` → product FAQ taxonomy (return policy,
  shipping, sizing), conversational tone (brand_identity.tone
  consume).
- `profile == "b2b-saas"` → technical FAQ taxonomy (integration,
  pricing tiers, security, API docs); formal tone preserve.
- `profile == "local-service"` → location-specific FAQ (service
  area, hours, contact, NAP signal preserve).
- `profile == "portfolio"` → minimal FAQ (3-5 max, opsiyonel); R-09
  cap 10 hard yerine 5 soft cap profile-driven downgrade.

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Content)

AI'ın doğal cheap content padding davranışını preempt et. FAQ
context'inde (R-09 + R-29 + R-118):

- **R-09 FAQ count cap (talep-güdümlü):** kanıt varsa (PAA varlığı,
  gerçek kullanıcı soruları) 3-6 FAQ; kanıt yoksa daha az veya hiç;
  hard cap 10; 11+ FAQ attempt → DURUR #2 REJECT.
- **Heading keyword density per FAQ %40-60:** primary_keyword vs FAQ
  Q heading; aşırı stuff (>%60) AMBER, eksik (<%40) AMBER.
- **R-29 pasaj alıntılanabilirlik gate:** H3 cevap-önce + 50-150
  word TL;DR per FAQ; first sentence izole parse self-contained.
- **AIO citation density:** per 500 word 1-2 citation
  (R-109/R-110/R-111); over-citation (>2 per 500w) DURUR #6 AMBER
  auto-correct.
- **AI signature humanize:** tone_phrases_blocklist consume
  (brand_identity), AI cliché phrases regex strip.
- **Failure mode:** AMBER warning (auto-correct attempt) → RED fail
  (manuel revise gerekir).

## R-121 Bank Selection Logic (Conditional Applicability)

**Conditional applicability is the headline.** FAQ items are typically
definitional (Q: "What is X?" / A: "X is a Y that does Z."). They
**often need no bank entry at all**. R-121 fires for FAQ optimization
**only when** a FAQ answer asserts an experience claim ("we measured
...", "we tested ...", "in our deployment ...") or a research claim
("our survey of 200 customers found ..."). For purely definitional
FAQs, R-105 / R-114 / R-119 are not in scope, and R-121 has nothing to
filter.

**Cross-skill cap interplay (CRITICAL).** R-121 density is per
content, not per skill invocation. When `mode == "enhance"` and the
existing article already cites bank entries in the body (originally
placed by new-blog), those entries already consume the per-profile
cap. faq-optimization MUST NOT add bank entries that would push the
combined count over the cap.

Detection (`mode == "enhance"`): during Step 1 existing-blog parse,
the skill also extracts current bank citations from the body (same
two paths as revise-content — `data-bank-entry-id` attribute first,
text-matching fallback for older articles). The result is
`bank_entries_pre_body[]`. The FAQ pass treats this as already-
committed cap consumption.

When R-121 DOES fire (FAQ answer asserts an experience/research
claim), the same 3-step filter applies, with a FAQ-specific tightening
on filter 2:

1. **Topic match.** `entry.applicable_topics ∩ (new_content_plan.
   primary_keyword ∪ faq_question_text_keywords ∪ topical_map[matching
   _row].cluster) ≠ ∅` → entry remains a candidate; empty intersection
   → entry skipped.
2. **Profile density cap, FAQ-tightened.** The article's per-profile
   cap is the ceiling for the BODY + FAQ combined. FAQ-only additional
   cap, on top of any body usage:
   - YMYL: at most 1 experience entry inside the FAQ section (and the
     combined body+FAQ count still ≤ 2 experience + 1 research).
   - b2b-saas: 0 experience + 0 research inside FAQ by default
     (technical FAQ taxonomy rarely cites first-hand or original
     research — escalate to manual review if a FAQ item genuinely
     needs one).
   - e-commerce / local-service / portfolio: 0 inside FAQ by default
     (the body's 1 experience entry is usually sufficient).
3. **Rotation (30-day).** For each new candidate, count usage in
   `master.xlsx[completed_work]` rows where
   `bank_entry_id == entry.id` AND `timestamp >= now - 30d`. Skip if
   `count >= entry.max_usage_per_month`. Pre-existing body entries
   (extracted in `mode == "enhance"`) are exempt from rotation —
   removing them only to satisfy the cap would be churn and would
   trigger a needless R-88 freshness-theater audit.

If all candidates fail the filter, the skill emits AMBER, retries with
`phrasings[]` rotation; 2x AMBER same pass → RED upgrade (the FAQ
section ships without that particular claim, or the operator manually
reviews).

**R-110 Anti-Pattern alignment.** R-110 over-citation gate
(>2 per 500w) and R-121 density cap reinforce each other: a FAQ
answer that needs more than one bank entry to be credible is usually
either too broad (split into separate FAQ items) or actually a body
paragraph in disguise (move to article body via revise-content). The
two rules together push FAQ items toward atomic, definitional Q&A
structure.

**Post-publish state mutation** (Step 7 events.jsonl append): for
each entry **newly introduced** in this FAQ pass, its
`last_used_in_content_id` is set; the `master.xlsx[completed_work]`
row carrying this content also records the `bank_entry_id`(s) added.
Pre-existing body entries are not touched (already counted when
new-blog or revise-content first shipped them).

**Schema enablement (v1.4, commit `8e07e1c`):** R-121 reads
`applicable_topics`, `phrasings`, `last_used_in_content_id`,
`max_usage_per_month` on each bank entry. Stage C of brand-onboarding
(commit `cb8df43`) populates these via R-44 evidence-gated atomic
write.

**Runtime integration deferred to Phase 11 Wave 2/3.** This SKILL.md
section is the spec lock; `scripts/production/faq_optimization.py`
does not yet exist. When the runtime lands, the conditional
applicability check (does this FAQ item assert experience/research?)
runs first; only if YES does the 3-step filter execute.

## Schema Authority Compliance

- **event_kind:** events.jsonl `event_kind=work` (events.schema.json enum
  4-value: provenance | work | audit | workflow; ADR-020 production
  output → work).
- **events.schema:** events.jsonl 5 required field zorunlu (schema_version
  const "1.0", event_kind, event_id UUIDv4, timestamp UTC ISO 8601,
  project_id pattern `^[a-z][a-z0-9-]*$`); event_type 12-enum içinden
  `content_revise` (FAQ enhance/add içerik revize semantiği — events.schema
  kanonik enum compliance).
- **F-15:** master.xlsx[content_improve] 8 col + allowed_writers null
  → READ-ONLY consume; W-F3 + W-F4 candidate input source
  (consistency report FAIL trigger için optimization sheet read).
- **F-2 (Wave 1 reuse):** master.xlsx[content_decay].action schema'da
  type/enum null → R-86/R-87/R-90/R-91 rule-derived consume; W-F3
  sadece "revise" ve "manual FAQ enhance" branch consume eder, prune/
  redirect/delete bu skill domain DEĞİL.
- **F-6:** master.xlsx 3 sheet (new_content_plan + content_decay +
  content_improve) allowed_writers null → READ-ONLY contract;
  `transaction.append/update/delete` YASAK.
- **F-3 (Wave 1 reuse):** project-config schema 1.2 + profile enum
  5-value Wave 1 W-F1'de cascade fix uygulandı; bu skill profile
  field'ı **var olduğu varsayımıyla** consume eder (Principle 2
  switch).

## Routing (7-Step Workflow)

### Step 1: master.xlsx Read + Mode Branch

`input.mode` switch:

- `mode == "enhance"` (default) → existing blog parse
  (`outputs/blog/{slug}/article.html` filesystem read).
  - Existing FAQ section detect (`<section class="pse-faq">` veya
    `<h2>FAQ</h2>` selector; BeautifulSoup parse).
  - Current FAQ count + Q&A extract (h3 + p pair).
  - DURUR #1 trigger: existing blog YOK → impossible (R-89
    canonical preserve enforce edilemez; new-blog skill'e
    yönlendir).
- `mode == "add"` → target URL find via
  `master.xlsx[new_content_plan]` row read where `url_slug ==
  {input.url}` (14 col schema baseline: id, title, url_slug,
  primary_keyword, monthly_volume, assigned_cluster,
  target_word_count, priority, created_date, tivl_tag,
  lifecycle_status, image_prompt, alt_text, content_type).
  - new_content_plan kontrol: `lifecycle_status == "GREEN"` gerekli
    (yeşil ışık olmadan FAQ add yasak).

`master.xlsx[content_improve]` 8 col cross-check (existing_url,
gsc_clicks, gsc_impressions, current_position, issue, optimization,
target_position, priority): FAQ optimization trigger varsa
`optimization` field'ı içinde "FAQ" keyword arar (READ-ONLY
filter).

### Step 2: project-config Read (Profile-Aware Switch — Principle 2)

`projects/{slug}/project.config.json` parse:

- `profile` field read (Principle 2 enum 5-value; F-3 schema 1.2
  baseline).
- `content_settings` 14 field consume (toc_strategy,
  related_posts_strategy, author_strategy, css_strategy,
  indexnow_enabled, ai_training_optin, video_integration,
  internal_data_sharing, external_uniqueness_check,
  original_research_database, experience_database, video_database,
  disclaimer_templates, image_model).
- `brand_identity` 18 field consume (logo_url, primary_color,
  secondary_color, accent_color, font_family_heading,
  font_family_body, header_template_id, footer_template_id,
  source_url_for_sampling, tone, hitap, anglicism_tolerance,
  tone_phrases_blocklist, font_heading, font_body, default_hero_url,
  same_as_urls, image_style).

Profile-aware FAQ taxonomy switch:

- `profile == "ymyl"` → R-51 disclaimer template ZORUNLU (per-FAQ
  veya FAQ section başında); counter-argument FAQ aday (R-50).
- `profile == "e-commerce"` → product FAQ taxonomy (return/shipping/
  sizing).
- `profile == "b2b-saas"` → technical FAQ taxonomy (integration/
  pricing/security).
- `profile == "local-service"` → location-specific FAQ (service
  area/hours/contact, NAP signal).
- `profile == "portfolio"` → minimal FAQ 3-5 soft cap (R-09 10 hard
  cap profile-driven downgrade).

### Step 3: R-09 FAQ Count Cap Enforce (Talep-Güdümlü)

- `mode == "enhance"`: existing FAQ count read (Step 1 parse).
- `mode == "add"`: target FAQ count plan (skill internal compose).
- R-09 talep-güdümlü band apply:
  - Kanıt varsa (PAA varlığı — `serp_organic_live_advanced` optional
    MCP; gerçek kullanıcı soruları — `gsc__search_analytics` query
    read) → 3-6 FAQ hedef.
  - Kanıt yoksa → daha az FAQ veya hiç (sıfır kabul; mekanik FAQ
    şişirme yasak — Principle 3).
  - Hard cap 10 (word count'tan bağımsız).
  - `profile == "portfolio"` → 5 soft cap (downgrade).

DURUR #2 trigger: `mode == "add" AND faq_count > 10` → REJECT
(R-09 violation, Principle 3 anti-cheap-content enforce; AI
suistimal önlemi).

### Step 4: R-43 Statik HTML Render (faq-block.template.html)

`templates/content/faq-block.template.html` render:

- Render-time slot:
  - `{{QUESTION_N}}` → FAQ question text (≤100 char, R-108
    truncation; no `:` veya `-` R-04).
  - `{{ANSWER_N}}` → FAQ answer text (40-50 word definition snippet,
    R-107).
  - `{primary_keyword}` → new_content_plan.primary_keyword (heading
    keyword density %40-60 enforce).
  - `{tone}` → brand_identity.tone (profile-aware tone preserve).
  - `{hitap}` → brand_identity.hitap.
  - `{primary_color}` → brand_identity.primary_color (CSS scope).
  - `{disclaimer}` → content_settings.disclaimer_templates[profile]
    (profile==ymyl → ZORUNLU).

R-43 statik enforcement (CRITICAL — accordion YASAK):

- `<details>` element YASAK (rendered HTML grep RED).
- `<summary>` element YASAK (rendered HTML grep RED).
- `display:none` CSS YASAK (FAQ visible by default).
- JS accordion YASAK (toggleable interactive widget yasak).

DURUR #3 trigger: rendered HTML'de `<details>` veya `<summary>`
detect → forbidden token grep RED, FAQ section discard, manuel
revize gerekir.

### Step 5: R-29 Pasaj Alıntılanabilirlik Gate

Her FAQ Q&A için pasaj alıntılanabilirlik test:

- **H3 question (cevap-önce structure):** "Soru?" formatında, soru
  cümlesi (no `:` veya `-` R-04).
- **First sentence (TL;DR):** cevap-önce 50-150 word, izole parse
  self-contained (H1/article context referansı YOK).
- **Body (detail expansion):** 50-300 word, source/citation embed.
- **Total per FAQ:** 100-450 word (R-29 + R-107 birleşik gate).

Pasaj alıntılanabilirlik test (LLM context window'a izole parse
simulation):

- Self-contained check: "yukarıda gördüğünüz gibi" / "bu yazıda" /
  "önceki bölümde" referans regex → AMBER (R-01 + R-29 reuse).
- Cevap-önce mini paragraf intact: first sentence direct answer
  (interrogative reflection veya delay yasak).

### Step 6: R-79 FAQPage @graph Schema Refresh + AIO Citation Pattern

JSON-LD `@graph` FAQPage entity update (R-79 + R-83 microdata
yasak):

- `mainEntity` array: her FAQ → Question entity.
- `Question.name`: H3 question text (TL;DR truncate).
- `Question.acceptedAnswer`: Answer entity.
- `Answer.text`: full Q&A body (citation reference intact).

Schema validate (Google Rich Results Test API mock):

- `@type: FAQPage` present.
- `mainEntity` array length == FAQ count (R-09 cap compliance).
- Each `Question.name` non-empty.
- Each `acceptedAnswer.text` non-empty.

DURUR #4 trigger: Google Rich Results Test API mock validate REJECT
→ schema fix önce (FAQPage @graph entity broken), FAQ section
yayın blocked.

AIO citation pattern enforcement (R-109/R-110/R-111):

- **R-109 AIO Pattern:** cevap-önce (R-29 reuse) + per 500 word min
  1 max 2 citation (entity reference dense). FAQ acceptedAnswer.text
  içinde citation source URL bağlı (Principle 1 Layer 3 enforce).
- **R-110 AIO Anti-Pattern:** keyword stuffing FAQ Q yasak (heading
  keyword density >%60 AMBER); over-citation (>2 per 500w) yasak;
  fluff intro yasak (cevap-önce TL;DR direct).
- **R-111 AIO Hijack (Quality-Driven):** quality-driven enforce —
  R-44 source verification 3-katman intact, R-105 expert quote
  bank-driven; AI cliché phrase strip (tone_phrases_blocklist
  consume).

DURUR #6 trigger: AIO citation density per 500 word > 2 (over-
citation Anti-Pattern R-110) → AMBER auto-correct (excess citation
strip), retry once; persistent fail → RED.

### Step 7: Foundational Principles 3-Katman Gate + events.jsonl Append

**P1 truth-verifiable Layer 2 fact-check pass:**

- Her FAQ Q&A için kaynak verify (R-44 source verification 3-
  katman: source URL reachable + content match + date freshness).
- Expert quote ise R-105 bank-driven verify (expert quote database
  lookup, no-match → reject).
- DURUR #5 trigger: P1 fact-check fail (FAQ Q&A uydurma claim/
  source) → RED, FAQ section discard, dateModified bump YOK.

**P2 profile-aware enforcement:**

- `profile == "ymyl"` → R-51 disclaimer present check (per-FAQ veya
  section-level).
- counter-argument FAQ aday (R-50 cross-link, profile==ymyl).
- profile==e-commerce → product FAQ taxonomy verify.
- profile==b2b-saas → technical FAQ taxonomy verify.
- profile==local-service → NAP signal preserve.
- profile==portfolio → 5 soft cap enforce.

**P3 anti-cheap-content enforcement:**

- AI signature humanize (tone_phrases_blocklist consume; AI cliché
  regex strip).
- Heading keyword density per FAQ %40-60 enforce (primary_keyword
  vs FAQ Q heading; over-stuff >%60 AMBER, under <%40 AMBER).
- R-09 cap final check (talep-güdümlü 3-6 / hard cap 10 /
  5 portfolio soft).

**events.jsonl append (events.schema enum compliance):**

- `event_kind` = `work` (ADR-020 production output enum).
- `event_type` = `content_revise` (events.schema 12-enum: FAQ enhance/add
  içerik revize semantik kanonik mapping).
- `schema_version` = `1.0` (events.schema const).
- `event_id` = UUID v4 (events.schema required).
- `timestamp` = UTC ISO 8601 (events.schema required).
- `project_id` = `{input.project_slug}` (events.schema pattern
  `^[a-z][a-z0-9-]*$` slug regex).
- `target` = `{input.url}`.
- `mode` = `{input.mode}` (enhance | add).
- `faq_count_pre`, `faq_count_post` (R-09 audit trail).
- `aio_citation_density` (R-109/R-110 audit trail).
- `profile` = project-config[profile] (P2 audit trail).

## DURUR Conditions (6 koşul)

1. **DURUR #1 — Existing Blog Yok (mode=enhance).**
   `outputs/blog/{slug}/article.html` filesystem'de bulunamıyor →
   FAQ section parse edilemez (mode=enhance kaynak yok); kullanıcıyı
   new-blog skill'e yönlendir.
2. **DURUR #2 — R-09 Cap Aşımı (mode=add).** `mode == "add" AND
   faq_count > 10` → REJECT (R-09 violation; AI suistimal Principle
   3 anti-cheap-content enforce).
3. **DURUR #3 — R-43 Accordion Detect.** Rendered HTML'de
   `<details>` veya `<summary>` element detect → forbidden token
   grep RED, FAQ section discard, statik visible h3+p zorla.
4. **DURUR #4 — R-79 FAQPage Schema Validate Fail.** Google Rich
   Results Test API mock validate REJECT (mainEntity boş veya
   Question.name/acceptedAnswer.text broken) → schema fix önce, FAQ
   yayın blocked.
5. **DURUR #5 — P1 Fact-Check Fail.** Principle 1 Layer 2 post-
   generate fact-check fail (FAQ Q&A uydurma claim/source; R-44
   source verify fail veya R-105 expert quote bank-driven match
   yok) → RED, FAQ section discard, dateModified bump YOK.
6. **DURUR #6 — AIO Over-Citation (R-110 Anti-Pattern).** AIO
   citation density per 500 word > 2 (over-citation) → AMBER auto-
   correct (excess citation strip), retry once; persistent fail →
   RED.

## READ-ONLY Contract (F-6 Enforcement)

Bu skill master.xlsx hiçbir sheet'e YAZMAZ:

- `master.xlsx[new_content_plan]` allowed_writers null (F-6) →
  READ-ONLY consume (target URL row read, lifecycle_status check).
- `master.xlsx[content_decay]` allowed_writers null (F-6) → READ-
  ONLY consume (action trigger detect, mode=enhance trigger için
  existing FAQ detect).
- `master.xlsx[content_improve]` allowed_writers null (F-6, F-15) →
  READ-ONLY consume (FAQ optimization trigger detect; W-F3+W-F4
  candidate input source).

`transaction.append/update/delete` call-site YASAK (Wave 1 paterni
reuse: revise-content + new-blog precedent).

Sadece şu artifact'lere yazılır (outputs § + produces §):

- `outputs/blog/{slug}/article.html` (updated FAQ section + JSON-LD
  @graph FAQPage entity refresh).
- `_state/events.jsonl` (append, events.schema enum compliance).

## WCAG 2.1 AA Accessibility (R-39)

FAQ block render:

- Heading hierarchy: h2 (FAQ section title) → h3 (each FAQ
  question); skip-level yasak.
- Focus-visible state: keyboard navigation FAQ list scroll
  (focus-visible CSS).
- Color contrast: primary_color vs background min 4.5:1 (WCAG 2.1
  AA Level AA threshold).
- Static visible (R-43 accordion YASAK alignment): screen reader
  full FAQ content read (no toggleable hide).

## Plugin-Agnostik Disiplin

Skill content'inde proje slug hardcode YASAK. Tüm proje referansları
runtime input ({input.project_slug}, {input.url}) üzerinden
çözümlenir. URL örnekleri SKILL.md'de generic placeholder
(`https://example.com/blog/post-slug`) kullanır. Plugin agnostik
MCP boundary korunur (.mcp.json hardcode slug yasak; F-16 Süleyman
Seçenek D Wave 1 baseline reuse).

## Versioning + Status

- `version: "1.0"` (Phase 11 Wave 2 ilk shipping).
- `status: wip` (Phase 11 Wave 3+ stabilizasyon sonrası `active`
  promote).
- Output schema_version: `1.0` (events.jsonl payload kontratı,
  events.schema const).
