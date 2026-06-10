---
name: Content EEAT Discipline
status: enforced
applies_to: [plugin]
applied_to_skills: [new-blog, revise-content, faq-optimization, content-remediation]
source: docs/superpowers/specs/2026-04-30-content-rules-input.md (R-17) + Phase 10 decision matrix (R-28, R-37, R-48, R-49, R-100, R-104, R-115)
spec_section: "Phase 10 — Content Rules Processing"
---

# Content EEAT Discipline

Bu doc Phase 10 EEAT (Experience, Expertise, Authoritativeness, Trustworthiness) görünür kanıt disiplinini tanımlar. **Foundational Principles** (3 üst-prensip) `→ rules/content-quality.md#foundational-principles` — burada tekrar yazılmaz (DRY, → [single-source-of-truth](single-source-of-truth.md)).

**Foundational Principles özeti** (tam metin için → [content-quality](content-quality.md#foundational-principles)):
1. **Truth-Verifiable Content** — bank-driven experience/research, uydurma yasak (R-105, R-114, R-119).
2. **Profile-Aware Enforcement** — author byline (R-28), otorite domain (R-37), counter-argument (R-115) profile'a göre değişir.
3. **AI Suistimal Önlemi** — stats density profile-aware min + max cap (R-104).

---

## Rules

### R-28: EEAT Görünür Kanıt (Reformulated — Updated Date Only, Author Byline Pas)

**Statement.** EEAT görünür kanıt iki sinyal: (1) `dateModified` updated date her content'te zorunlu (R-89 cross-link), (2) **author byline profile-aware** — YMYL plugin/zorunlu (R-82 schema), e-commerce yok (admin sırıtmasın).

**Rationale.** Süleyman explicit cevap (Phase 10 matrix). Updated date tüm profile'larda recency signal; byline profile-aware (Principle 2).

**Enforcement.** Skill render time:
- `dateModified` ISO 8601 (R-89) Article schema + visible HTML.
- Profile = ymyl → `<address class="pse-author">By {{AUTHOR_NAME}}, {{AUTHOR_TITLE}}</address>` + R-82 Person schema.
- Profile != ymyl → byline skip.

**Failure mode.** YMYL'da author missing → RED; non-YMYL'da silent.

### R-124: YMYL Uzman İnceleme İmzası (Expert-Review Sign-Off)

**Statement.** YMYL profilinde yazar künyesi (R-28) yalnızca **kayıtlı bir insan incelemesi** ile geçerlidir. Yayından ÖNCE şu üç alan bir `events.jsonl` audit satırına (`event_kind=audit`) kaydedilmelidir: (1) **inceleyen** kişinin adı, (2) inceleme **tarihi** (ISO 8601), (3) içerik **sürümü** (content hash veya revision id). İnceleme kaydı yoksa → RED (yayın bloklu).

**Rationale.** Makine-taslağı YMYL metnine belgelenmiş inceleme olmadan adlı bir yazar künyesi koymak **uydurulmuş yazarlık sinyalidir** (Google rater-guideline "Lowest" — fabricated authorship/expertise). R-28 künyeyi görünür kılar; R-124 künyenin arkasında gerçek bir insan inceleme kanıtı olmasını zorunlu kılar. Principle 1 (Truth-Verifiable) + EEAT Trustworthiness tezahürü.

**Enforcement.** Bu batch (FIX-H) kuralı + failure mode'u yazar; uygulama kontratı (new-blog / revise-content pre-publish step'i + `events_writer.append_audit` çağrısı) FIX-K'de iner. Pre-publish gate: profiles ⊇ {ymyl} ve künye (R-28) var ama `events.jsonl`'da eşleşen inceleyen+tarih+sürüm audit satırı yok → RED.

**Failure mode.** YMYL'da inceleme kaydı eksik → RED.

**Cross-link.** → R-28 (EEAT künye, profile-aware), R-82 (Author Person schema), R-89 (dateModified), [content-quality](content-quality.md#foundational-principles) (Principle 1 Truth-Verifiable).

### R-37: Otorite Domain (Profile-Aware)

**Statement.** Outbound link güvenilirliği önce **küratörlü per-proje kaynak allowlist'i** ile belirlenir (`project.config` allowlist / manuel kurumsal kaynak listesi) — birincil mekanizma budur. Sayısal kapı OPSİYONELdir ve kullanılırsa açıkça **Ahrefs DR** olmalıdır (isimsiz tek bir "otorite skoru" yok; Moz DA ≠ Ahrefs DR — aynı ölçek değil). Profile-aware referans aralıkları (Ahrefs DR, opsiyonel): YMYL ~DR≥60 (.gov/.edu/kurumsal yayın), e-commerce ~DR≥40 (sektörel), b2b-saas ~DR≥50, local-service ~DR≥30, portfolio esnek.

**Rationale.** Principle 2. YMYL düşük otorite kaynak Trustworthiness sıfırlar; e-commerce'te .gov bulmak zor (sektörel kaynak yeterli). İsimsiz "otorite skoru ≥60" bir metrik belirtmez (Moz DA ile Ahrefs DR karıştırılamaz) → birincil mekanizma küratörlü allowlist; sayısal eşik yalnızca açıkça Ahrefs DR olarak ikincil filtredir.

**Enforcement.** Pre-publish outbound link audit: önce allowlist üyeliği; opsiyonel sayısal filtre kullanılırsa Ahrefs DR + profile referans aralığı; eşik altı → AMBER (YMYL'da RED).

**Failure mode.** YMYL'da RED, kalanlarda AMBER.

### R-48: Schema Markup Baseline

**Statement.** EEAT schema baseline: Article (R-78) + Author (R-82 profile-aware) + Organization (R-81) + Breadcrumb (R-80) + FAQPage (R-79) — JSON-LD `@graph` array tek `<script>`.

**Rationale.** Schema markup Knowledge Graph entity recognition'ın hammaddesi.

**Enforcement.** Skill render time `@graph` array build; pre-publish R-84 validate.

**Failure mode.** RED.

### R-49: Entity Reference (Article.about + mentions)

**Statement.** Article schema `about` (primary entity, 1 adet) + `mentions` (secondary entities, 3-7 adet) array. Entities Wikidata Q-ID veya Wikipedia URL ile bağlanır (`@id` field).

**Rationale.** Knowledge Graph entity disambiguation; AIO entity matching.

**Enforcement.** Skill render time primary keyword → Wikidata search → Q-ID; secondary keywords → mentions array.

**Failure mode.** Silent (best-effort).

### R-100: Brand Entity sameAs (Wikipedia/Wikidata)

**Statement.** Organization schema `sameAs` array brand entity profile linkleri: Wikipedia URL + Wikidata Q-ID + LinkedIn + sosyal medya. `project.config.json[brand_identity.same_as_urls]` array kaynak.

**Rationale.** Knowledge Graph brand entity binding (Süleyman explicit Phase 10 matrix).

**Enforcement.** Skill render time `same_as_urls` array fetch; Organization.sameAs render.

**Failure mode.** AMBER (eksik) — manual brand_identity setup gerekir.

### R-104: Stats Density (Profile-Aware Min + Max Cap)

**Statement.** Stats density (sayısal claim per word) profile-aware:
- YMYL: min 1 stat / 500 word, max 1 stat / 200 word.
- e-commerce: min 1 stat / 800 word, max 1 stat / 300 word.
- b2b-saas: min 1 stat / 600 word, max 1 stat / 250 word.
- local-service: min 1 stat / 1000 word, max esnek.
- portfolio: esnek.

**Bu kural stats-density sayılarının TEK kaynağıdır (single source).** Production skill'ler (new-blog, revise-content) bu eşikleri kendi SKILL.md'lerinde farklı sayılarla tekrarlamaz; R-104'ü cite eder (örn. new-blog'un "min 3/1000w, üst sınır yok" varyantı R-104'e hizalanmalıdır).

**Rationale.** Principle 3 (quality > quantity). Stats density data-driven content sinyali ama over-density "veri bombardımanı" UX kırar.

**Enforcement.** Pre-publish stat regex (`\d+[%.,]\d*` veya `\d{2,}+`) count + word count ratio; profile threshold dışı AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-115: Counter-Argument (YMYL Profile-Aware) (superseded by R-50)

**Statement.** **Superseded by R-50** (Counter-Argument Profile-Aware, [content-quality.md:145](content-quality.md)). R-115 sözcük-sözcük R-50 ile aynı statement; ADR-038 K-01 closure paterni ile master R-50'ye aktarıldı. Yeni citation R-50 olmalıdır; bu giriş history-stable numbering policy gereği korundu.

**Cross-link:** R-50 (master).

---

## Cross-References

- → [content-quality](content-quality.md#foundational-principles) — 3 foundational principle (özellikle Principle 1 R-105/R-114/R-119 bank-driven, Principle 2 profile tablosu)
- → [content-seo-discipline](content-seo-discipline.md) — Article + Author + Organization + FAQPage schema (R-78..R-84)
- → [content-update-discipline](content-update-discipline.md) — dateModified (R-89)
- → [schema-first](schema-first.md) — JSON-LD schema önce yazılır
- → [single-source-of-truth](single-source-of-truth.md) — brand_identity + experience_database tek yerde

## Enforcement (Plugin-Level)

- Phase 11 production skill'ler (özellikle new-blog, revise-content) bu rules dosyasını consume eder.
- Profile-aware enforcement (R-28, R-37, R-115) Phase 11 acceptance gate'lerinde branching test.
