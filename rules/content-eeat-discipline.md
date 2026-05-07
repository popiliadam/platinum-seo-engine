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

### R-37: Otorite Domain (Profile-Aware)

**Statement.** External outbound link otorite domain skoru profile-aware threshold: YMYL ≥ 60 (.gov/.edu/kurumsal yayın), e-commerce ≥ 40 (sektörel), b2b-saas ≥ 50 (sektörel + tech publication), local-service ≥ 30 (lokal/sektörel), portfolio esnek.

**Rationale.** Principle 2. YMYL düşük otorite kaynak Trustworthiness sıfırlar; e-commerce'te .gov bulmak zor (sektörel kaynak yeterli).

**Enforcement.** Pre-publish outbound link audit: domain_authority_score (Moz/Ahrefs proxy veya manual list) + profile threshold; threshold altı → AMBER (YMYL'da RED).

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
