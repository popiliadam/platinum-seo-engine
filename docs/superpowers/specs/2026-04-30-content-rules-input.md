# Content Rules Input — v1.3 Production Skills İçin

**STATUS:** SUPERSEDED 2026-05-02 by Phase 10 deliverables. Bu doc input olarak kalır (audit trail), ama authoritative rules artık `rules/content-*.md` dosyalarındadır (content-quality + content-html-discipline + content-seo-discipline + content-eeat-discipline + content-llm-discipline + content-update-discipline). R-01..R-26 mevcut + R-27..R-122 yeni (87 ek rule, Süleyman 266-cevap matrix) + 3 foundational principle (truth-verifiable + profile-aware + AI suistimal önlemi).

**Tarih:** 2026-04-30
**Kaynak:** Kullanıcı input (architecture brainstorming sırasında verildi)
**Durum:** SUPERSEDED — Phase 10 worker tarafından `rules/` ve `templates/`'e dönüştürüldü (bkz. yukarı).
**Hedef Tüketim:** Phase 11 production skill'leri (new-blog, revise-content, faq-optimization, content-remediation, generate-images)

---

## 0. Bu Doküman Nasıl Okunur

**Phase 10 worker'ı için:** Bu doküman Phase 10'da TAMAMI okunur. Çıktı:
- `rules/content-quality.md` — universal kurallar (rules 1-19, 25-26)
- `rules/content-html-discipline.md` — semantic HTML, CSS, kurumsal renk (rules 20-24)
- `rules/content-seo-discipline.md` — linking, FAQ, keywords, intent (rules 6-13)
- `templates/content/new-blog.template.md` — yeni blog skeleton
- `templates/content/new-blog.template.html` — HTML template (kurumsal CSS slot'lı)
- `templates/content/revision.template.md` — revize template
- `templates/content/faq-block.template.html` — snippet-friendly FAQ HTML

**Diğer phase'ler için:** Bu doküman okunmaz. Sadece Phase 10 referansıdır.

---

## 1. Tüm Content Rule'lar (Numaralı Liste)

### Yapısal Kurallar

**R-01. H1 Altı Intro Paragrafı**
H1'in hemen altında bir intro paragrafı olmalı. **AEO (Answer Engine Optimization)** uyumlu yazılmalı — yani: ilk 1-2 cümle direkt soruya cevap veren, alıntılanabilir özet niteliğinde olmalı.

**R-02. Thin Content / Word Wall Yasak**
İçerik **ne thin content ne de word wall** olacak. Denge gözetilecek:
- Thin content: yetersiz kelime sayısı, derinliksiz, value-poor
- Word wall: paragraflar arasında nefes vermeden duvar gibi metin, görsel ayrım yok
- Doğru denge: paragraf başına 2-4 cümle, her bölümde liste/tablo/görsel/blockquote ritim, scannable yapı.
*(Doğrulandı: user 2026-04-30, Q-CR-01 closed.)*

**R-03. Heading Hiyerarşisi**
H2, H3 (ve gerekiyorsa H4) dengeli kullanılacak. **H1 sadece 1 adet.** H2'ler ana bölümler, H3'ler alt başlıklar, H4 sadece zorunluysa.

**R-04. Başlıklarda Yasak Semboller**
Başlıklarda `:` (iki nokta) ve `-` (tire) **kullanılmayacak**. Doğal Türkçe başlık yapısı tercih edilecek.

**R-05. Sonuç/Conclusion Başlığı Yasak**
"Sonuç", "Conclusion", "Özet", "Kapanış" gibi başlıklar **olmayacak**. İçerik doğal şekilde son paragraf + **CTA (Call-to-Action)** ile bitirilecek.

### SEO Kuralları

**R-06. İç Linkleme**
- Her ~300 kelimede 1 iç link
- **Bir link 1 kez kullanılacak** (duplike anchor/URL yasak)
- Link kararı master excel'in `internal_links` sheet'inden / `internal-links` skill'inden alınır

**R-07. Liste + Tablo**
Her ~1000 kelimede:
- 1 adet liste (numbered veya bulleted)
- 1 adet tablo
- **Tablolar atıf alabilecek kalitede** olmalı (data-rich, schema'ya uygun, cite edilebilir)

**R-08. SERP Analizi (Yazım Öncesi ZORUNLU)**
İçerik yazılmadan önce **Scrapling MCP** ile primary keyword için SERP top 5 rakip analizi yapılacak. Çıktı:
- Top 5 sayfa URL'leri
- Her birinin başlık, intro, ana bölümleri
- Ortak temalar
- Eksiklikleri (content gap)

Bu analiz `inbox/serp-analysis/{date}-{keyword}.json`'a kaydedilecek (provenance).

**R-09. FAQ Bölümü**
- **10 adet FAQ** olacak
- Her biri **snippet kazanmaya uygun** yapıda (kısa, direkt soru-cevap, schema markup)
- FAQ schema (FAQPage) HTML'e dahil edilecek

**R-10. Intent Uyumu**
İçeriğin intent'i belirlenip ona göre yazılacak:
- Kategori sayfaları, marka aramaları → **satış-odaklı (commercial / transactional)**
- Blog yazıları → **informational** (genelde) veya **navigational**
- Intent `master.xlsx[cluster_keywords].intent` sütunundan okunur

**R-11. Cluster/Pillar Uyumu**
İçerik atandığı **cluster ve pillar'a uygun** yazılacak. **Kannibalizasyon (yamyamlık) yasak** — aynı keyword için birden fazla içerik üretmek yasak. `master.xlsx[topical_map]` ve `master.xlsx[cluster_keywords]` otorite.

**R-12. Primary + Secondary Keywords**
Sadece primary keyword değil, **secondary keyword'ler de** belirlenecek.
- Primary: 1 adet (ana hedef)
- Secondary: 3-7 adet (related, supporting)
- Her ikisi de `master.xlsx[cluster_keywords]`'da takip edilir

**R-13. Bold Disiplini**
Her ~250 kelimede 1 primary veya secondary keyword **bold**'lanacak. Aşırıya kaçma — keyword stuffing izlenimi vermeyecek.

### Kalite Kuralları

**R-14. Kaynaklar (Uydurma Yasak)**
Kaynaklar:
- **Uydurma değil**, gerçek
- **Konuyla doğrudan ilgili**
- **Kanıtlanabilir** (URL veya yayın bilgisi)
- Tercihen otorite domainler (.gov, .edu, kurumsal yayınlar)

**R-15. Site/Proje Gerçeği**
Sitede / projede **gerçekten olmayan** bilgi, ürün, fiyat, hizmet **asla kullanılmayacak**. Skill önce `master.xlsx[crawl_sitemap]` veya `dataforseo_on_page_content_parsing` ile sitenin gerçek içeriğini doğrulayacak.

**R-16. Google AI Overview Uyumu**
İçerik **AI Overview'dan atıf alabilecek** kalitede yazılmalı:
- Net soru-cevap yapıları
- Citable claims with sources
- Schema markup (FAQPage, Article, HowTo where appropriate)
- Concise paragraflar (paragraph başına 2-4 cümle)

**R-17. Google Helpful + E-E-A-T Uyumu**
- **Experience:** birinci el deneyim
- **Expertise:** uzmanlık göstergesi
- **Authoritativeness:** otorite tonu
- **Trustworthiness:** güvenilirlik (kaynak, transparency)

**Ama abartıya kaçmadan, doğal bir tonda.** Kullanıcı "ama bunu yaparken saçmamalı" dedi.

**R-18. Teknik Terim Dengesi**
- Çok teknik terim kullanıp **kullanıcı sıkmamalı**
- Ama gereken yerde teknik terim kullanılmalı (otorite için)
- Karşılaşılan ilk teknik terimde kısa bir parantez içi açıklama veya tooltip-style not

**R-19. GEO (Generative Engine Optimization)**
İçerik GEO uyumlu olmalı:
- LLM'lerin alıntılayabileceği yapıda
- Açık entity tanımları
- Konvansiyonel formatlar (tanım, liste, prosedür)
- Numerik claims with citations

### Teknik / HTML Kuralları

**R-20. Format: HTML**
İçerikler **HTML olarak** yazılacak (markdown değil, doğrudan HTML).

**R-21. Semantic HTML**
Tamamen **semantic HTML5** tag'leri kullanılacak:
- `<article>`, `<section>`, `<aside>`, `<nav>`, `<header>`, `<footer>`
- `<h1>`...`<h4>`, `<p>`, `<ul>`, `<ol>`, `<table>`, `<figure>`, `<figcaption>`
- `<blockquote>`, `<cite>`, `<time>`, `<address>`
- `<div>` ve `<span>` minimum

**R-22. Header/Footer Dokunulmazlığı**
Üretilen HTML site'in **header ve footer'ında bozulma yaratmayacak**. Sadece ana içerik bölümünü oluşturacak (genelde `<article>` veya `<main>` içine yerleştirilecek HTML).

**R-23. CSS**
- **Inline minify CSS** kabul edilebilir (HTML içine `<style>` bloğu)
- **Kurumsal renk** kullanılacak (per-project)
- **Kurumsal tasarım** dili korunacak (per-project)
- Kaynak: `project.config.json[brand_identity]` (logo, primary_color, secondary_color, accent_color, font'lar)

**R-24. Tasarım Sample'ı (Init'te 1 Kez)**
`init-project` skill'i opsiyonel olarak **Scrapling MCP** ile sitenin bir sayfasını fetch edip:
- Renk paletini çıkarır
- Font ailelerini çıkarır
- Header/footer template'lerini örnek alır
- `project.config.json[brand_identity]`'ye yazar

Bu bir kez yapılır, sonraki içerikler bu config'ten besler.

### Operasyonel Kurallar

**R-25. Master Excel + MCP Efektif Kullanımı**
Production skill'leri (new-blog, revise-content) içerik yazarken şu kaynakları **efektif kullanmak ZORUNDA**:
- `master.xlsx[cluster_keywords]` → primary + secondary keywords
- `master.xlsx[topical_map]` → pillar + cluster context
- `master.xlsx[new_content_plan]` → planlanan başlık, target word count, intent
- `master.xlsx[internal_links]` → eklenecek linkler
- `dataforseo_labs_keyword_*` MCP → keyword desteği
- `Scrapling` MCP → SERP top-5 analizi (R-08)
- `dataforseo_on_page_content_parsing` MCP → site'in mevcut içeriği (R-15 doğrulama)

**R-26. CTA Zorunlu**
Her içeriğin **doğal bir CTA** ile bitmesi şart:
- İlgili projeye yönlendirme (ürün, hizmet, randevu, iletişim)
- Hard-sell değil, **doğal akışta** (R-05'e göre "Sonuç" başlığı yok, CTA paragraf içinde organic)
- CTA wording per-project memory.md'den alınabilir

---

## 2. Phase 10 Worker Görevleri

Phase 10 worker'ının yapması gerekenler (sırasıyla):

### Step 1: Bu doküman + spec §11.2'i (Phase 5 critical path detayı) oku
Spec'in geri kalanını okuma. Sadece bu iki bölüm.

### Step 2: 3 Rule Dosyasını Oluştur

**`rules/content-quality.md`** içeriği:
- R-14 (kaynaklar)
- R-15 (site gerçeği)
- R-16 (AI Overview uyum)
- R-17 (E-E-A-T)
- R-18 (teknik terim dengesi)
- R-19 (GEO)
- R-25 (master excel + MCP usage)
- R-26 (CTA zorunluluğu)

**`rules/content-html-discipline.md`** içeriği:
- R-20 (HTML format)
- R-21 (semantic HTML)
- R-22 (header/footer dokunulmazlığı)
- R-23 (CSS, kurumsal renk)
- R-24 (tasarım sample init'te)

**`rules/content-seo-discipline.md`** içeriği:
- R-01 (intro paragrafı + AEO)
- R-02 (thin/word wall yasak)
- R-03 (heading hiyerarşisi)
- R-04 (yasak semboller)
- R-05 (sonuç başlığı yasak)
- R-06 (iç linkleme)
- R-07 (liste + tablo)
- R-08 (SERP analizi)
- R-09 (FAQ)
- R-10 (intent uyumu)
- R-11 (cluster/pillar)
- R-12 (primary + secondary)
- R-13 (bold disiplini)

Her rule dosyası şu yapıda olacak:
```markdown
# {Rule Set Name}

**Status:** Active
**Applied to:** new-blog, revise-content, faq-optimization, content-remediation
**Source:** content-rules-input.md (2026-04-30)

## Rules

### R-XX: {Rule Name}
**Statement:** {clear normative statement}
**Rationale:** {why}
**Enforcement:** {how skill verifies}
**Failure mode:** {RED/AMBER/silent}

...
```

### Step 3: 4 Template Dosyasını Oluştur

**`templates/content/new-blog.template.md`** — yeni blog için markdown skeleton (planlama amaçlı)

**`templates/content/new-blog.template.html`** — gerçek HTML template:
```html
<article class="pse-blog-post">
  <header>
    <h1>{{TITLE}}</h1>
    <p class="pse-intro">{{INTRO_PARAGRAPH_AEO_FRIENDLY}}</p>
  </header>

  {{!-- Body sections (H2/H3, lists, tables, internal links per R-06, R-07) --}}
  {{BODY_SECTIONS}}

  {{!-- FAQ section (R-09: 10 adet, snippet-friendly) --}}
  <section class="pse-faq" itemscope itemtype="https://schema.org/FAQPage">
    {{FAQ_BLOCK}}
  </section>

  {{!-- CTA per R-26 — natural, project-specific --}}
  <p class="pse-cta">{{CTA_PARAGRAPH}}</p>
</article>

<style>
  /* Kurumsal renk slot'ları (per-project from project.config.json) */
  .pse-blog-post { font-family: {{FONT_BODY}}; }
  .pse-blog-post h1, h2, h3 { font-family: {{FONT_HEADING}}; color: {{PRIMARY_COLOR}}; }
  .pse-cta { background: {{ACCENT_COLOR}}; color: white; padding: 1em; }
  /* ... */
</style>
```

**`templates/content/revision.template.md`** — revize edilecek içerikler için (mevcut içerik + diff hedef)

**`templates/content/faq-block.template.html`** — snippet-friendly FAQ HTML:
```html
<div class="pse-faq-item" itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">{{QUESTION}}</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <div itemprop="text">{{ANSWER}}</div>
  </div>
</div>
```

### Step 4: User Review
Phase 10 worker output paketi kullanıcıya sunulur. **Kullanıcı approval olmadan Phase 11'e geçilmez.**

### Step 5: Open Question'ları DECISIONS.md veya OPEN_QUESTIONS.md'ye Yansıt
Aşağıdaki bölüm 3'teki açık sorular için ya kullanıcıdan cevap al ya da OPEN_QUESTIONS.md'ye not düş.

---

## 3. Açık Sorular (Phase 10'da User'a Sorulacak)

**Q-CR-01:** ✅ CLOSED 2026-04-30 — User onayladı: "ne thin content ne de word wall." R-02 güncellendi.

**Q-CR-02:** R-01 — "AEO uyumlu" intro paragrafı için spesifik kelime sayısı (40-60 kelime?) veya cümle sayısı (2-3 cümle?) range tercih ediyor musun?

**Q-CR-03:** R-12 — Secondary keywords kaç adet olmalı? Range önerim: 3-7 adet. Onaylıyor musun yoksa farklı bir sayı?

**Q-CR-04:** R-13 — Bold disiplinde "her ~250 kelimede 1" — bu bold edilen şey **sadece keyword** mi yoksa **keyword + önemli terimler** olabilir mi?

**Q-CR-05:** R-23 — Per-project brand_identity için zaten `project.config.json` schema'da slot var (logo_url, primary_color, font_family_*). v1.3'te bu slotlar **zorunlu** mu (init-project'te toplanır), yoksa **opsiyonel** mi (yoksa per-profile neutral defaults)?

**Q-CR-06:** R-26 — CTA wording per-project memory.md'de mi olmalı, yoksa skill her seferinde kullanıcıya mı sormalı? Önerim: memory.md'de default CTA'lar tanımlı, skill bunu override edebilir.

**Q-CR-07:** R-09 — FAQ için 10 adet sabit mi yoksa "minimum 10, max 15" gibi range mi? Önerim: minimum 10, max 15.

**Q-CR-08:** R-08 — SERP top-5 analizi sadece primary keyword için mi, yoksa primary + ilk 2 secondary için mi? Maliyet açısından: sadece primary öneririm.

**Q-CR-09:** R-15 — "Sitede olmayan ürün/fiyat" doğrulaması nasıl yapılacak? Önerim: skill içerik yazmadan önce `dataforseo_on_page_content_parsing` ile sitenin ilgili sayfa(lar)ını parse eder, content içindeki claims'leri bu parse sonucuyla cross-check eder.

**Q-CR-10:** Word count target — yeni blog için typical range? `master.xlsx[new_content_plan].target_word_count` zaten var (per-content). Default range tercihi (örn 1500-3000)?

---

## 4. Aklına Gelirse Eklenecekler (User Notu)

User dedi ki: "daha aklıma gelirse yazarız düzenleriz ilerleyen süreçte."

**Yani bu doküman canlıdır.** v1.3 öncesi user yeni rule eklerse:
1. Bu dokümana eklenir (R-27, R-28, ...)
2. Phase 10'da işlenir
3. İlgili `rules/content-*.md` ve `templates/content/*` dosyaları güncellenir

Phase 11 production skill'leri başlamadan önce Phase 10 user-review döngüsü garanti.

---

## 5. Phase 11 Acceptance Test (Ön Tanıtım)

Phase 11'de new-blog skill'i ile 1 test blog yazılacak. Acceptance kriterleri (her biri PASS olmalı):

| # | Kontrol | Method |
|---|---------|--------|
| 1 | HTML semantic | Lint + manual |
| 2 | H1 tek, H2/H3 dengeli | Parse |
| 3 | Intro paragrafı AEO uyumlu | Manual review |
| 4 | Heading'lerde `:` `-` yok | Regex |
| 5 | "Sonuç"/"Conclusion" başlığı yok | Regex |
| 6 | İç link sayısı (~ kelime/300) | Count |
| 7 | İç linkler dupe yok | Set check |
| 8 | Liste sayısı (~ kelime/1000) | Count |
| 9 | Tablo sayısı (~ kelime/1000) | Count |
| 10 | Bold disiplini (~ kelime/250) | Count |
| 11 | FAQ 10+ adet | Count |
| 12 | FAQ schema markup | Schema validator |
| 13 | CTA mevcut, doğal | Manual review |
| 14 | Scrapling SERP top-5 yapılmış | events.jsonl check |
| 15 | Kaynaklar var, kanıtlanabilir | URL check |
| 16 | Kurumsal renk + font slotları doldu | Template lint |
| 17 | Header/footer bozmuyor | Render test |
| 18 | Word count `target_word_count` ± 10% | Count |
| 19 | Primary + secondary keywords var | Cross-check `cluster_keywords` |
| 20 | Intent target_url'in intent'iyle uyumlu | Cross-check `cluster_keywords` |

20 check'in HEPSİ PASS → Phase 11 acceptance ✓.
