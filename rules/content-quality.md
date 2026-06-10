---
name: Content Quality
status: enforced
applies_to: [plugin]
applied_to_skills: [new-blog, revise-content, faq-optimization, content-remediation, generate-images]
source: docs/superpowers/specs/2026-04-30-content-rules-input.md (R-01..R-26) + Phase 10 decision matrix (Süleyman 266 cevap, R-27..R-122)
spec_section: "Phase 10 — Content Rules Processing"
---

# Content Quality

Bu doc Phase 10 content kuralları setinin **master** dosyasıdır. Diğer 5 dosya (`content-html-discipline.md`, `content-seo-discipline.md`, `content-eeat-discipline.md`, `content-llm-discipline.md`, `content-update-discipline.md`) bu dosyadaki **Foundational Principles** bölümüne `→ rules/content-quality.md#foundational-principles` ile referans verir; tekrar yazılmaz (DRY, → [single-source-of-truth](single-source-of-truth.md)).

R-XX numbering integrity: R-01..R-26 input doc'tan korundu (content-rules-input.md SUPERSEDED — R-26 CTA Zorunlu v1.4-deep-audit-fix Tier 2 K-01 closure ile content-seo-discipline.md'ye aktarıldı), R-27..R-122 Phase 10'da eklendi (Süleyman 266-cevap matrix). **R-78 başlangıçta iki kez tanımlanmıştı** (Article Schema + AI-Image IPTC); IPTC kuralı 2026-06-10'da **R-123**'e taşındı (ADR-038 history-stable) → artık tüm `### R-NN` başlıkları tekildir (invariant: `tests/rules/test_rule_id_uniqueness.py`). R-124 (YMYL expert-review sign-off) 2026-06-10'da content-eeat-discipline.md'ye eklendi.

---

## Foundational Principles

Bu 3 prensip Phase 10 content rules setinin **üst-prensibidir**. Hiçbir alt-rule (R-01..R-122) bu prensipleri override edemez. Phase 11+ skill'leri (new-blog, revise-content, faq-optimization, content-remediation, generate-images) bu 3 prensibe tabidir.

### Principle 1 — Truth-Verifiable Content (Süleyman 5x vurgu)

**Statement.** Tüm content/source/link/data **%100 doğru ve kanıtlanabilir** olacak. Uydurma yasak — kaynak, hikaye, case study, fiyat, stat, ürün, feature, image-link.

**Rationale.** Yayın sonrası bir yanlış claim'in maliyeti EEAT skoruna kalıcı zarar + KVKK/legal exposure (YMYL profile'ında medical/legal/financial); AI Overview citation hijack edilirse domain reputation düşer; kullanıcı güveni "uydurma fiyat / hayali ürün" tek seferde dahi kırılır.

**Enforcement (Phase 11 worker pre-publish 3-katman defense).**
1. **Skill prompt explicit "uydurma yasak"** — new-blog/revise-content prompt'unda Principle 1 inline (R-14, R-15, R-44, R-105 cross-link).
2. **Output post-generate fact-check pass** — her claim için citation kontrolü; citation-less claim FAIL.
3. **Citation requirement enforce** — eksik citation → RED (yayın bloklu).

**Failure mode.** RED — yayın iptal, claim revize zorunlu.

**Cross-rule coverage.** R-14, R-15, R-32, R-44, R-45, R-52, R-53, R-54, R-105, R-114, R-116, R-117, R-118, R-119.

### Principle 2 — Profile-Aware Enforcement

**Statement.** Skill behavior `project.config.json[profiles]` array'ine göre değişir. Profile types: `e-commerce` / `ymyl` / `local-service` / `b2b-saas` / `portfolio`.

**Rationale.** Aynı rule (örn. author byline) profile'a göre **zıt** sonuç gerektirir — YMYL'da medical/legal/financial yazılarda byline plugin/zorunlu (E-E-A-T + trust signal), e-commerce'te admin sırıtmasın (kullanıcıyla psikolojik mesafe). Tek sabit rule iki profile'da da yanlış sonuç verir.

**Profile-aware kararlar (Phase 10 boyunca consistent).**

| Boyut | YMYL | e-commerce | b2b-saas | local-service | portfolio |
|---|---|---|---|---|---|
| Author byline | Zorunlu | Yok | Esnek | Esnek | Yok |
| Tone | semi-pro + siz | conversational + sen | formal + siz | conversational + siz | esnek |
| Outbound link | Otorite zorunlu (.gov/.edu) | Esnek | Sektörel | Lokal/sektörel | Esnek |
| Word count | 1500-4000 | 800-2500 | 1800-3500 | 1000-2500 | 800-2000 |
| Counter-argument (R-50/R-115) | Zorunlu (objectivity) | Skip | Opsiyonel | Skip | Skip |
| Disclaimer (R-51) | medical/legal/financial template | Skip | Opsiyonel | Skip | Skip |
| Image style | Clean illustration | Product photo | Diagram + screenshot | Lokasyon foto | Esnek |
| Stats density (R-104) | min/500w + max cap | min/800w + max cap | min/600w + max cap | esnek | esnek |

**Enforcement.** Phase 11 worker `project.config.json[profiles]` array'ini her skill başında okur; `union + dedup + priority merge` resolution (project-config.schema.json `profiles` field semantik korundu); behavior boyutları yukarıdaki tabloya göre seçilir.

**Profile cascade — singular `profile` vs plural `profiles[]` (H-H v1.4-deep-audit-fix Tier 3 closure):** `project-config.schema.json` v1.2'den itibaren hem plural `profiles[]` array (proje-genel composable union) hem singular `profile` string (per-content override) destekler. Skill render-time cascade davranışı:
- Plural `profiles[]` (proje config seviyesi) → tüm skill'lere uygulanan baseline (Phase 5 W-F1 paterni). Worker `union + dedup + priority merge` resolution.
- Singular `profile` (frontmatter / master.xlsx[new_content_plan].profile per-task seviyesi) → o özel content için baseline'i **override** veya **refine** eder (Phase 11 W-F1 cascade fix). Singular set ise tablo o profile'a göre seçilir; set DEĞİLse plural priority merge geçerlidir.
- Singular `profile` enum domeni plural ile aynıdır (`e-commerce`/`ymyl`/`local-service`/`b2b-saas`/`portfolio`); cross-validation: singular ⊆ plural (singular değer plural array'inde mevcut olmalı).

**Failure mode.** AMBER — yanlış profile resolution worker raporlar; RED yalnızca `profiles=[]` (boş array — schema `minItems:1` ihlali). Singular `profile` plural array dışı bir değerse → AMBER (cross-validation warn).

**Cross-rule coverage.** R-23 (CSS profile-aware), R-37 (otorite domain profile), R-50/R-115 (counter-argument), R-51 (disclaimer template), R-58 (lifecycle robots), R-60 (CSS profile), R-104 (stats density).

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Content)

**Statement.** AI'ın doğal davranışını (cheap content padding, signature words, multi-list inflation) **preempt** et. Kalite > hacim.

**Rationale.** Generic LLM çıktısı 3 sinyalde patlar: (a) H2'leri başlık olarak basıp tek paragraf yazar, derinlik yok; (b) "Aslında", "Önemli olan", "Sonuç olarak", "Özetle" gibi imza kelimeleri tekrarlar; (c) listeler ile word-count şişirir (multi-list per H2). AIO/AI Overview citation alma şansı bu cheap content'te sıfırdır; ranking penalty kuvvetli (Helpful Content Update sinyali).

**Enforcement patterns.**
- **H3 zorunluluk gate** — H2 word count > 200 → min 2 H3 (R-30; AI H2 basıp geçmesin).
- **Heading keyword density** — H2'lerin %40-60'ında primary/secondary keyword (R-30; stuffing önleme).
- **Citation density** — per 500 word min 1 max 2 citation (R-106; UX overload önleme).
- **FAQ count** — talep-güdümlü: kanıt varsa (PAA / gerçek kullanıcı soruları) 3-6, hard cap 10 (R-09; AI çok FAQ yazmasın).
- **Stats density** — profile-aware min + max cap (R-104; quality > quantity).
- **Per-H2 list cap** — max 1 liste per H2 (R-07; multi-list AI padding).
- **AI signature humanize pass** — post-generate signature words avoid (R-118; "Aslında / Sonuç olarak / Özetle" tekrar düşürme).

**Failure mode.** AMBER warning + RED fail thresholds — Phase 11 acceptance check enforce (warning x2 → RED upgrade).

**Cross-rule coverage.** R-02, R-07, R-09, R-30, R-104, R-106, R-118.

---

## Rules

### R-14: Kaynaklar (Uydurma Yasak)

**Statement.** Kaynaklar gerçek + konuyla doğrudan ilgili + kanıtlanabilir (URL veya yayın bilgisi) olacak. Tercihen otorite domainler (.gov, .edu, kurumsal yayınlar).

**Rationale.** Principle 1 (Truth-Verifiable) somut tezahürü. Uydurma kaynak EEAT'in `Trustworthiness` boyutunu sıfırlar.

**Enforcement.** Skill her kaynak için `dataforseo_on_page_content_parsing` veya HTTP HEAD ile URL liveness doğrular; 404/3xx → kaynak değiştirilir veya silinir.

**Failure mode.** RED — yayın iptal.

### R-15: Site/Proje Gerçeği

**Statement.** Sitede / projede gerçekten olmayan bilgi, ürün, fiyat, hizmet asla kullanılmayacak. Skill önce `master.xlsx[crawl_sitemap]` veya `dataforseo_on_page_content_parsing` ile sitenin gerçek içeriğini doğrulayacak.

**Rationale.** Principle 1. Hayali ürün/fiyat tek seferde dahi user trust'ı kırar.

**Enforcement.** new-blog/revise-content skill'i content yazmadan önce ilgili kategori/ürün sayfasını parse eder; content içindeki tüm `claim`'leri (fiyat, feature, stok, hizmet) parse output'la cross-check eder.

**Failure mode.** RED — yayın iptal.

### R-27: Truth-Verifiable Content (Üst-Prensip Anchor)

**Statement.** Bkz. → [Foundational Principles → Principle 1](#principle-1--truth-verifiable-content-süleyman-5x-vurgu).

**Rationale.** Üst-prensip 1'in numbered rule anchor'ı. R-XX listesinde referenslenebilir.

**Enforcement.** 3-katman defense (skill prompt + post-generate fact-check + citation enforce).

**Failure mode.** RED.

### R-32: Parasite SEO Yasak

**Statement.** 3rd-party domain (Medium, LinkedIn, Substack, Reddit) üzerinden hızlı ranking için içerik yayınlama yasak. Tüm content kendi domain'inde, kendi schema'sıyla.

**Rationale.** Parasite SEO Google 2024 sonrası policy'sinde manuel action riski; domain reputation 3rd-party'ye bağımlı; replay/audit imkansız (3rd-party platform değiştirebilir).

**Enforcement.** `master.xlsx[new_content_plan].assigned_url` kontrol — host == project_domain olmalı; aksi halde content plan FAIL.

**Failure mode.** RED.

### R-44: Source Verification 3-Katman

**Statement.** Her external claim 3 katman doğrulama: (1) URL liveness HTTP 200, (2) domain güvenilirliği — önce **küratörlü per-proje kaynak allowlist'i** (birincil); opsiyonel sayısal kapı kullanılırsa açıkça **Ahrefs DR** (örn. YMYL DR≥60 / e-commerce DR≥40; isimsiz "otorite skoru" yok, Moz DA ≠ Ahrefs DR), (3) claim cite edilen sayfada literal mevcut.

**Rationale.** Principle 1. URL canlı ama claim sayfada yok → "uydurma kaynak" özel hali.

**Enforcement.** new-blog/revise-content post-generate pass: `dataforseo_on_page_content_parsing` + substring match.

**Failure mode.** RED — kaynak değiştirilir veya claim çıkarılır.

### R-45: Bibliography Section Policy

**Statement.** Content sonunda `<aside class="pse-bibliography">` opsiyonel — YMYL profile'ında zorunlu, diğerlerinde skill seçer. Format: `<ol><li><cite>Yayın Adı</cite>, <a href="URL">Erişim Tarihi</a></li>...</ol>`.

**Rationale.** YMYL'da görünür kaynak listesi `Trustworthiness` sinyali; non-YMYL'da inline citation yeterli.

**Enforcement.** Profile-aware (Principle 2). `profiles ⊇ {ymyl}` → bibliography zorunlu, eksikse skill RED.

**Failure mode.** YMYL'da RED, kalanlarda silent.

### R-50: Counter-Argument (Profile-Aware)

**Statement.** YMYL profile'ında counter-argument H2 section zorunlu (objectivity sinyali); e-commerce/local-service skip; b2b-saas opsiyonel.

**Rationale.** Principle 2 + EEAT (Authoritativeness). YMYL medical/legal/financial içerikte tek-yönlü öneri trust kırar; counter-argument göstermek otorite tonu güçlendirir.

**Enforcement.** Profile-aware. YMYL skill prompt'unda "counter-argument H2 zorunlu, başlık 'Karşı Argümanlar' veya benzeri (R-04 sembol yasağı geçerli)".

**Failure mode.** YMYL'da AMBER → 2x AMBER → RED.

### R-51: Disclaimer Template (Per-Project)

**Statement.** YMYL profile'ında medical/legal/financial sub-domain'lerde profile-aware disclaimer template content sonuna eklenir. Template `project.config.json[content_settings.disclaimer_templates]` map'inde tutulur.

**Rationale.** Principle 2 + legal exposure. Medical bilgiyi "doktor değiştirme" tavsiyesi olmadan vermek hukuki risk.

**Enforcement.** YMYL + (medical|legal|financial) cluster eşleşmesi → template inject. Template eksikse skill init-project'te zorunlu kılar.

**Failure mode.** YMYL medical/legal/financial içerikte RED (yayın bloklu).

### R-52: Fact-Check Workflow

**Statement.** Pre-publish post-generate fact-check pass: (1) tüm sayısal claim → citation, (2) tüm temporal claim ("2024 yılında", "son araştırmada") → tarih + kaynak, (3) tüm tasdik claim ("uzmanlar bunu öneriyor") → citation veya çıkarılır.

**Rationale.** Principle 1. AI'ın doğal halüsinasyonunu yakalama mekanizması.

**Enforcement.** new-blog/revise-content post-generate Pass; citation-less claim listesi → RED.

**Failure mode.** RED.

### R-53: Truth-Verifiable 3-Katman Defense (Anchor)

**Statement.** Bkz. → Principle 1 enforcement (skill prompt + post-generate fact-check + citation enforce).

**Rationale.** Principle 1 enforcement'ın numbered rule anchor'ı.

**Enforcement.** 3-katman birlikte uygulanır; tek katman skip RED.

**Failure mode.** RED.

### R-54: Hipotetik Flag

**Statement.** Hipotetik veya örneklendirme amaçlı veri (örn. "Diyelim ki 1000 müşteri") açık şekilde flag'lenir: `<aside class="pse-hypothetical">Örnek senaryo</aside>` veya cümle içi "varsayalım/örneğin/diyelim".

**Rationale.** Principle 1. Hipotetik veriyi gerçek gibi sunma R-14 ihlali; flag'leme şeffaflık sinyali.

**Enforcement.** Hipotetik blok regex tarama: rakam + "olsun/diyelim/varsayalım" yakınlığı → flag missing → AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-105: Expert Quote Uydurma Yasak

**Statement.** Uzman alıntısı ("Dr. X şöyle dedi...") **gerçek** olmak zorunda. Uydurma quote yasak. Bank-driven (`project.config.json[content_settings.experience_database]` veya `original_research_database`).

**Rationale.** Principle 1. Uydurma quote `Authoritativeness` ve `Trustworthiness` ikisini birden kırar.

**Enforcement.** Quote bloğu (`<blockquote>` veya `"..."` + isim atfı) detect edilir → bank lookup → eşleşme yoksa RED.

**Failure mode.** RED.

### R-114: Original Research (Bank-Driven)

**Statement.** Original research claim'i (anket, vaka analizi, ölçüm) **bank-driven** — `project.config.json[content_settings.original_research_database]` array'inde tanımlı olacak. Skill yeni research uydurmaz.

**Rationale.** Principle 1. Original research güçlü EEAT sinyali ama uydurma research domain'i yakar.

**Enforcement.** Skill original research claim → bank lookup; eşleşme yoksa claim çıkarılır veya AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-116: Internal Data Aggregate-Only

**Statement.** Internal data (sipariş sayısı, kullanıcı sayısı, müşteri segmenti) sadece **aggregate** form ile yayınlanır. Per-customer veya tanımlanabilir bireysel data yasak (KVKK + GDPR).

**Rationale.** KVKK/GDPR compliance + iş gizliliği. "Geçen ay 1247 sipariş" OK; "İstanbul'dan Ali Y. 3 kez sipariş verdi" yasak.

**Enforcement.** `project.config.json[content_settings.internal_data_sharing]` boolean ON ise aggregate format zorunlu; OFF ise hiç paylaşılmaz.

**Failure mode.** RED (KVKK exposure).

**Cross-link.** → [secrets-management](secrets-management.md).

### R-117: Uniqueness Check

**Statement.** Yayın öncesi content uniqueness skoru ≥ 70% (paragraph-level shingling vs. SERP top-10). Düşük skor AI-generated paraphrase sinyali.

**Rationale.** Principle 3. Generic AI çıktısı SERP top-10 ile %50+ overlap üretir; uniqueness check Helpful Content Update sinyali.

**Enforcement.** `project.config.json[content_settings.external_uniqueness_check]` boolean ON ise pre-publish check; threshold altı AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-118: AI Signature Humanize

**Statement.** AI signature words ("Aslında", "Önemli olan", "Sonuç olarak", "Özetle", "Bilindiği gibi", "Aslında bakarsanız") metin başına density ≤ 1 / 1000 word. Post-generate humanize pass.

**Rationale.** Principle 3. AI imza kelimeleri ranking penalty + AIO citation reddi sinyali.

**Enforcement.** Regex tarama post-generate; threshold üstü kelimeler değiştirilir veya silinir.

**Failure mode.** AMBER → otomatik humanize pass → re-check → 2x AMBER → RED.

### R-119: First-Hand Experience (Bank-Driven)

**Statement.** "Birinci el deneyim" claim'i (kullandım, denedim, ölçtüm) → bank-driven (`project.config.json[content_settings.experience_database]`). Skill kendi adına first-hand iddia etmez.

**Rationale.** Principle 1 + EEAT (Experience). Uydurma deneyim "uzmanlık tiyatrosu" — Helpful Content Update penalty.

**Enforcement.** First-person experience pattern detect → bank lookup → eşleşme yoksa cümle restructure ("kullanıcılar X yapıyor" gibi 3rd-person).

**Failure mode.** AMBER → 2x AMBER → RED.

### R-121: Bank Entry Rotation + Density Cap + Topic Relevance

**Statement.** Production skill (new-blog / revise-content / faq-optimization) bank entry (R-105 expert quote / R-114 original research / R-119 first-hand experience) kullanırken 3 koşulu birlikte sağlamak ZORUNLU:
1. **Topic Relevance.** Entry'nin `applicable_topics` array'i içerik konusuyla örtüşmeli (`master.xlsx[new_content_plan].primary_keyword` + `topical_map.cluster_id` eşleşmesi); örtüşmüyorsa entry kullanılmaz.
2. **Density Cap (profile-aware).** Per-content max: YMYL = 2 experience + 1 research; b2b-saas = 1 + 1; e-commerce / local-service / portfolio = 1 experience + 0 research.
3. **Rotation (30-day).** `master.xlsx[completed_work]` son 30 günde aynı entry `id` için `usage_count >= max_usage_per_month` ise entry skip; alternatif `phrasings` array'inden seç veya farklı entry'ye geç.

**Rationale.** Principle 3 + May 2026 Core Update "repetitive content visibility loss" + "automated, ad-bloated content" penalty sinyallerine karşı Engine self-protection. R-118 stilistik tekrarı yakalar; R-121 **semantik** tekrarı yakalar — aynı çekirdek bilgi farklı blog'larda kopya halinde tekrar etmesin (bank entry `phrasings` array'i ile aynı fact farklı cümlelerle aktarılır; "rotation içinde rotation").

**Enforcement (Phase 11 worker pre-publish 3-step filter).**
1. **Topic match:** `entry.applicable_topics ∩ blog.topics ≠ ∅` → candidate; ∅ → skip.
2. **Density count:** candidate set'ten profile-aware max sayıda seç.
3. **Rotation tally:** `completed_work` last-30-day filter; cap üstü entry skip.
4. **Post-publish:** seçilen entry'nin `last_used_in_content_id` field'ı + `usage_count` master.xlsx[completed_work] row append ile atomic güncellenir.

**Failure mode.** AMBER (3 katmanı geçen entry yoksa skill phrasing rotation dener) → 2x AMBER → RED (yayın blocked, operator review).

**Cross-link.** → R-105 (expert quote bank), R-114 (original research bank), R-119 (first-hand experience bank), R-118 (AI signature humanize — stilistik karşılık), schema v1.4 bank entry format (`applicable_topics` + `phrasings` + `max_usage_per_month` fields).

---

## Cross-References

- → [content-html-discipline](content-html-discipline.md) — HTML format, semantic, image, performance
- → [content-seo-discipline](content-seo-discipline.md) — heading, internal link, FAQ, schema markup
- → [content-eeat-discipline](content-eeat-discipline.md) — author byline, otorite domain, brand entity
- → [content-llm-discipline](content-llm-discipline.md) — LLMs.txt, AIO, summary footer
- → [content-update-discipline](content-update-discipline.md) — decay, revise, sunset/prune
- → [schema-first](schema-first.md) — schema önce yazılır
- → [single-source-of-truth](single-source-of-truth.md) — DRY, foundational principles tek bir yerde
- → [excel-discipline](excel-discipline.md) — master.xlsx üzerinden veri okuma
- → [time-discipline](time-discipline.md) — updated date ISO 8601
- → [secrets-management](secrets-management.md) — internal data KVKK
- → [naming](naming.md) — pse- prefix HTML class

## Enforcement (Plugin-Level)

- Phase 11 production skill'ler (new-blog, revise-content, faq-optimization, content-remediation, generate-images) bu rules dosyasını consume eder.
- Phase 11 acceptance gate'leri Foundational Principles 3 prensibe + R-14/R-15/R-27/R-32/R-44/R-45/R-50/R-51/R-52/R-53/R-54/R-105/R-114/R-116/R-117/R-118/R-119/R-121 rule'larına karşı doğrulanır.
- Cross-skill convention drift catch için `master.xlsx[completed_work]` sheet'inde rule violation event'i flag'lenir (Phase 14+ governance).
