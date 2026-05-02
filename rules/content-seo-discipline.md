---
name: Content SEO Discipline
status: Active
applied_to: [new-blog, revise-content, faq-optimization, content-remediation, generate-images]
source: docs/superpowers/specs/2026-04-30-content-rules-input.md (R-01..R-13) + Phase 10 decision matrix (R-29, R-30, R-33, R-34, R-36, R-78..R-84, R-107..R-113)
spec_section: "Phase 10 — Content Rules Processing"
---

# Content SEO Discipline

Bu doc Phase 10 SEO disiplinini tanımlar (heading, internal link, FAQ, keyword, intent, schema markup, AIO snippet engineering). **Foundational Principles** (3 üst-prensip) `→ rules/content-quality.md#foundational-principles` — burada tekrar yazılmaz (DRY, → [single-source-of-truth](single-source-of-truth.md)).

**Foundational Principles özeti** (tam metin için → [content-quality](content-quality.md#foundational-principles)):
1. **Truth-Verifiable Content** — uydurma yasak (R-27).
2. **Profile-Aware Enforcement** — `project-config.json[profiles]` array consume (Principle 2 tablosu).
3. **AI Suistimal Önlemi** — H3 zorunluluk gate (R-30) + heading keyword density (R-30) + citation density (R-106) + per-H2 list cap (R-07).

---

## Rules

### R-01: H1 Altı Intro Paragrafı (AEO)

**Statement.** H1'in hemen altında intro paragrafı. **AEO uyumlu**: ilk 1-2 cümle direkt soruya cevap veren, alıntılanabilir özet (40-60 kelime range).

**Rationale.** Answer Engine (AIO, Perplexity, ChatGPT Search) ilk paragraf → snippet candidate. Quote-friendly intro citation şansı 3x artırır.

**Enforcement.** new-blog skill template `<p class="pse-intro">{{INTRO_PARAGRAPH_AEO_FRIENDLY}}</p>`; ilk 2 cümle sentence-tokenize sonra "answer-shape" pattern check.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-02: Thin Content / Word Wall Yasak

**Statement.** İçerik ne thin ne de word wall. Paragraf 2-4 cümle; her bölümde liste/tablo/görsel/blockquote ritim; scannable.

**Rationale.** Thin content (Helpful Content Update penalty) + word wall (UX dwell time düşüş). Denge SEO + UX.

**Enforcement.** Paragraf cümle sayımı; 5+ cümle paragraflar AMBER; 1000+ word section'da medya öğesi yoksa AMBER.

**Failure mode.** AMBER.

### R-03: Heading Hiyerarşisi

**Statement.** H2, H3 (gerekirse H4) dengeli. **H1 sadece 1 adet.** H2 ana bölümler, H3 alt başlıklar, H4 zorunluysa.

**Rationale.** SEO + R-39 WCAG (linear hierarchy).

**Enforcement.** Pre-publish heading parse: H1 count == 1; H3 H2 atlamayan; H4 sadece H3 altında.

**Failure mode.** RED.

### R-04: Başlıklarda Yasak Semboller

**Statement.** Başlıklarda `:` (iki nokta) ve `-` (tire) **kullanılmayacak**. Doğal Türkçe başlık yapısı.

**Rationale.** Süleyman explicit. Pixel-cap (R-35) + AIO snippet truncation davranışı.

**Enforcement.** Heading regex check: `[h1-6].*[:\-].*` → RED.

**Failure mode.** RED.

### R-05: Sonuç/Conclusion Başlığı Yasak

**Statement.** "Sonuç", "Conclusion", "Özet", "Kapanış" başlıkları yasak. CTA paragraf (R-26) doğal akışta.

**Rationale.** Generic AI imza + UX (kapatma sinyali dwell time düşürür).

**Enforcement.** Heading regex check (case-insensitive). RED.

**Failure mode.** RED.

### R-06: İç Linkleme

**Statement.** Her ~300 kelimede 1 iç link. **Bir link 1 kez kullanılır** (duplike anchor/URL yasak). Link kararı `master.xlsx[internal_links]` sheet'inden / `internal-links` skill'inden.

**Rationale.** Link equity + topical authority (R-11 cluster paterni).

**Enforcement.** Pre-publish link count check (word count / 300); duplicate URL set check.

**Failure mode.** AMBER (sayı) → RED (duplicate).

### R-07: Liste + Tablo (Per H2 Cap)

**Statement.** Her ~1000 kelimede: 1 liste + 1 tablo. Tablolar atıf alabilecek kalitede (data-rich). **Per-H2 max 1 liste** (Principle 3 multi-list AI padding cap).

**Rationale.** Scannable + AIO citation (table + list snippet candidate).

**Enforcement.** Heading scope analysis; H2 başına liste sayısı > 1 → AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-08: SERP Analizi (Yazım Öncesi Zorunlu)

**Statement.** Yazımdan önce **Scrapling MCP** ile primary keyword için SERP top 5 analiz. Çıktı: top 5 URL, başlık+intro+ana bölümler, ortak temalar, content gap. `inbox/serp-analysis/{date}-{keyword}.json` kaydedilir.

**Rationale.** Competitive parity + content gap stratejisi.

**Enforcement.** new-blog skill pre-write step (workflow-run state machine).

**Failure mode.** RED.

### R-09: FAQ Bölümü

**Statement.** **10 adet FAQ** standart; 3000+ word blog için 15 hard cap. Her biri snippet kazanmaya uygun (kısa, direkt soru-cevap, schema markup).

**Rationale.** Principle 3 (AI çok FAQ yazmasın). FAQPage schema AIO citation şansı.

**Enforcement.** FAQ count check; word count > 3000 ise max 15.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-10: Intent Uyumu

**Statement.** İçerik intent'e göre: kategori/marka aramaları → satış-odaklı (commercial/transactional); blog → informational (genelde) veya navigational. Intent `master.xlsx[cluster_keywords].intent` sütunundan okunur.

**Rationale.** Intent mismatch ranking failure'ın #1 sebebi.

**Enforcement.** Skill workflow ilk step intent fetch; content tone intent map'le align.

**Failure mode.** RED.

### R-11: Cluster/Pillar Uyumu

**Statement.** İçerik atandığı cluster + pillar'a uygun. **Kannibalizasyon yasak** — aynı keyword için birden fazla içerik üretmek yasak. `master.xlsx[topical_map]` + `master.xlsx[cluster_keywords]` otorite.

**Rationale.** Topical authority (cluster strategy) + keyword cannibalization SEO penalty.

**Enforcement.** Pre-write check: primary_keyword zaten `cluster_keywords.assigned_url` non-null → cannibalization → RED.

**Failure mode.** RED.

### R-12: Primary + Secondary Keywords

**Statement.** Primary 1 + secondary 3-7. Her ikisi `master.xlsx[cluster_keywords]`'da takip.

**Rationale.** Topical depth + long-tail capture.

**Enforcement.** Skill workflow keyword set fetch; secondary count [3,7] range.

**Failure mode.** AMBER (count) → manual review.

### R-13: Bold Disiplini

**Statement.** Her ~250 kelimede 1 primary veya secondary keyword **bold**. Aşırıya kaçma — keyword stuffing yasak. Bold edilen yalnızca **keyword**, generic terim değil.

**Rationale.** Visual scanning + zayıf keyword density signal (over-stuffing penalty).

**Enforcement.** Bold count check (word_count / 250); non-keyword bold AMBER.

**Failure mode.** AMBER → 2x AMBER → RED (stuffing).

### R-29: Pasaj Alıntılanabilirlik (H2 Cevap-Önce + TL;DR)

**Statement.** Her H2 section başlangıcında **cevap-önce mini paragraf** (1-2 cümle direkt cevap), sonra detay; opsiyonel TL;DR `<aside class="pse-tldr">` blok.

**Rationale.** Principle 3 (AIO citation şansı) + dwell time (cevap-önce → kullanıcı kalır vs. cevap-arar).

**Enforcement.** Skill render H2 template `<h2>{{TITLE}}</h2><p class="pse-h2-answer">{{ANSWER_FIRST}}</p>...`.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-30: Heading Enforcement (H3 + Keyword Density)

**Statement.** **H3 zorunluluk gate** — H2 word count > 200 → min 2 H3 (Principle 3). **Heading keyword density** — H2'lerin %40-60'ında primary/secondary keyword.

**Rationale.** Principle 3 (AI H2 basıp geçmesin) + keyword stuffing önleme.

**Enforcement.** Pre-publish parse: per-H2 word count > 200 ve H3 count < 2 → AMBER. H2 keyword match ratio < 0.4 veya > 0.6 → AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-33: Anchor Linguistic Flow

**Statement.** Internal/external link anchor cümle akışında doğal — "buraya tıkla" yasak. Anchor exact-match keyword stuffing yasak; partial-match + branded mix.

**Rationale.** Over-optimization penalty + UX (anchor cümleyi okurken doğal).

**Enforcement.** Anchor regex check: "tıkla", "click here", "burada" yasak; exact-match anchor ratio > 30% AMBER.

**Failure mode.** AMBER.

### R-34: Outbound 3-Katman Verification

**Statement.** Outbound link 3 katman: (1) URL liveness HTTP 200, (2) `rel` attribute (`nofollow`/`sponsored`/`ugc` profile-aware), (3) link target topic-relevance (R-44 reuse).

**Rationale.** Broken outbound link UX + crawler penalty; spam outbound link domain reputation.

**Enforcement.** Pre-publish outbound link audit; broken/spam → RED.

**Failure mode.** RED.

### R-36: SERP Analiz Volatility-Aware Cache + AIO Citation Page Scrape

**Statement.** R-08 SERP analiz cache stratejisi: keyword volatility-aware TTL (low-vol 30 day, high-vol 7 day). AIO citation source page'leri scrape edilir (top-3 cited domain).

**Rationale.** API maliyet + güncel SERP picture; AIO citation pattern öğrenme.

**Enforcement.** Skill workflow cache check (TTL); cache miss → live fetch + write.

**Failure mode.** Silent (cache fallback).

### R-78: Article Schema Markup

**Statement.** `<script type="application/ld+json">` Article schema zorunlu: `@type:"Article"`, `headline`, `description`, `author` (R-28 profile-aware), `datePublished`, `dateModified` (R-89), `image`, `publisher`.

**Rationale.** Article rich result + AIO citation (entity recognition).

**Enforcement.** Skill template render time JSON-LD inject; pre-publish Schema.org validator pass.

**Failure mode.** RED.

### R-79: FAQPage Schema Markup

**Statement.** FAQ block (R-09) için FAQPage schema `@graph` inline. Her FAQ → `Question` entity + `acceptedAnswer.Answer.text`.

**Rationale.** FAQPage rich result (Aralık 2023 sonrası reduced ama domain trust signal); AIO citation.

**Enforcement.** `templates/content/faq-block.template.html` schema inline; FAQ count == JSON-LD Question count.

**Failure mode.** RED.

### R-80: BreadcrumbList Schema

**Statement.** `BreadcrumbList` schema breadcrumb navigation için. Position-based itemListElement.

**Rationale.** Breadcrumb rich result + site structure signal.

**Enforcement.** Skill render: cluster→pillar→content position chain.

**Failure mode.** AMBER.

### R-81: Organization Schema

**Statement.** `Organization` schema page-level (Article'da `publisher` field). `name`, `url`, `logo`, `sameAs` (R-100).

**Rationale.** Brand entity (Knowledge Graph signal); R-100 cross-link.

**Enforcement.** Skill `project-config.json[brand_identity]` + `same_as_urls` array'inden render.

**Failure mode.** AMBER.

### R-82: Author Schema (Profile-Aware)

**Statement.** YMYL profile'ında `Person` schema author `@type:"Person"` + `name` + `url` (author bio sayfası) + `sameAs` (LinkedIn vb.). e-commerce'te skip (R-28).

**Rationale.** Principle 2 + EEAT (Authoritativeness/Trustworthiness).

**Enforcement.** Profile-aware. YMYL author missing → RED.

**Failure mode.** YMYL'da RED.

### R-83: JSON-LD Only (@graph)

**Statement.** Tüm schema markup **JSON-LD** (microdata/RDFa yasak). Multi-schema → tek `<script type="application/ld+json">` içinde `@graph` array.

**Rationale.** Google explicit recommendation + parse simplicity.

**Enforcement.** Microdata `itemscope` etc. attribute regex check (FAQ template hariç R-79 fallback) → AMBER.

**Failure mode.** AMBER.

### R-84: Schema Validation Pre-Publish

**Statement.** Pre-publish Schema.org validator + Google Rich Results Test pass. Warnings tolere; error RED.

**Rationale.** Malformed schema rich result fail + crawl waste.

**Enforcement.** CI: `python -m pyld` veya hosted validator; skill output validate.

**Failure mode.** RED.

### R-107: Snippet Engineering (Intent-Aware)

**Statement.** Featured snippet candidate paragraflar intent-aware: informational → definition snippet (40-50 word "X nedir" cevap-önce); commercial → list snippet (5-8 madde); transactional → table snippet (compare-shop format).

**Rationale.** Snippet pozisyonu trafik 8x; intent map snippet format'ı belirler.

**Enforcement.** Skill workflow intent fetch → snippet template select.

**Failure mode.** AMBER.

### R-108: Snippet Truncation (Char Range)

**Statement.** Definition snippet 40-50 word; list snippet 5-8 madde; table snippet 4-6 row × 2-3 col. Truncation görünür, beyond visible "and more..." cümlesi.

**Rationale.** Google snippet truncate threshold; over-budget snippet bloated.

**Enforcement.** Skill render time snippet candidate paragraf word count.

**Failure mode.** AMBER.

### R-109: AIO Pattern (Cevap-Önce + Citation Density)

**Statement.** AIO citation pattern: H2 cevap-önce (R-29) + per 500 word min 1 max 2 citation (Principle 3 R-106 reuse) + entity reference dense.

**Rationale.** AIO citation pattern empirically — cevap-önce paragrafları top citation candidates.

**Enforcement.** Pre-publish per-500-word citation density check.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-110: AIO Anti-Pattern

**Statement.** AIO için yasak pattern: (a) çok-katmanlı nested list (3+ depth), (b) "Yukarıda gördüğümüz gibi..." referans-driven cümle (anchor olmadan parse fail), (c) image-only data ("görseldeki tabloya bakın"; AIO image OCR güvenmez).

**Rationale.** AIO parsing fail → citation reddi.

**Enforcement.** Pre-publish anti-pattern regex check.

**Failure mode.** AMBER.

### R-111: AIO Hijack (Quality-Driven)

**Statement.** AIO citation hijack = competitor cited domain'in cevabından **daha iyi** cevap üretmek (entity coverage, recency, citation density). Spammy hijack (keyword stuffing, fake citation) yasak — Principle 1 (Truth-Verifiable) ihlali.

**Rationale.** Quality-driven hijack sustainable; spammy hijack manuel action.

**Enforcement.** Strategy doc, skill rule değil; new-blog brief'inde competitor AIO citation comparison adımı.

**Failure mode.** Strategic.

### R-112: Snippet vs AIO Trade-Off

**Statement.** Snippet (Position 0) ve AIO citation farklı optimize edilir. Snippet → tek paragraf cevap; AIO → multi-claim cevap-önce + citation density. Tek content her ikisini hedefler ama format'lar bağımsız.

**Rationale.** SERP feature ekosistemi; tek pattern her ikisini kazanmaz.

**Enforcement.** Skill render iki feature'ı ayrı slot'larda hedefler (intro + per-H2 mini-paragraf).

**Failure mode.** Strategic.

### R-113: SERP Feature Mapping

**Statement.** Primary keyword için SERP feature analiz (R-08 reuse): {snippet, AIO, PAA, image_pack, video_pack, knowledge_panel}. Content render her feature'a uygun slot inject (PAA → FAQ section format).

**Rationale.** Multi-feature kapsamı trafik 3-5x.

**Enforcement.** R-08 SERP analiz output'unda feature list; skill render slot select.

**Failure mode.** Silent (best-effort).

---

## Cross-References

- → [content-quality](content-quality.md#foundational-principles) — 3 foundational principle
- → [content-html-discipline](content-html-discipline.md) — semantic HTML, image
- → [content-eeat-discipline](content-eeat-discipline.md) — author byline, otorite domain
- → [content-llm-discipline](content-llm-discipline.md) — AIO summary, citation pattern
- → [excel-discipline](excel-discipline.md) — master.xlsx üzerinden cluster_keywords + topical_map + internal_links
- → [schema-first](schema-first.md) — JSON-LD validation pre-write
- → [single-source-of-truth](single-source-of-truth.md) — internal_links sheet otorite

## Enforcement (Plugin-Level)

- Phase 11 production skill'ler bu rules dosyasını consume eder.
- Schema.org validator + heading hierarchy parse + intent cross-check Phase 11 acceptance gate'leri.
