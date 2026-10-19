---
name: Content LLM Discipline
status: enforced
applies_to: [plugin]
applied_to_skills: [new-blog, revise-content, faq-optimization]
source: docs/superpowers/specs/2026-04-30-content-rules-input.md (R-16, R-19) + Phase 10 decision matrix (R-98, R-99, R-101, R-102, R-103, R-106)
spec_section: "Phase 10 — Content Rules Processing"
---

# Content LLM Discipline

Bu doc Phase 10 LLM/AIO görünürlük disiplinini tanımlar (LLMs.txt, per-bot policy, AIO-friendly intro, summary footer, citation pattern). **Foundational Principles** (3 üst-prensip) `→ rules/content-quality.md#foundational-principles` — burada tekrar yazılmaz (DRY, → [single-source-of-truth](single-source-of-truth.md)).

**Foundational Principles özeti** (tam metin için → [content-quality](content-quality.md#foundational-principles)):
1. **Truth-Verifiable Content** — citation pattern (R-106) Principle 1 enforcement.
2. **Profile-Aware Enforcement** — `ai_training_optin` per-project (R-99).
3. **AI Suistimal Önlemi** — citation density min/max cap (R-106), AI signature humanize (R-118 cross-link).

---

## Rules

### R-98: LLMs.txt (Project-Init Opt-In)

**Statement.** `llms.txt` dosyası project root'unda **opt-in** (init-project skill kullanıcıya sorar). Format: AnswerEngine sitemap (URL list + summary).

**Rationale.** Google'ın 2026-05-15 AI Optimization Guide cümlesi: "You don't need to create new machine readable files, AI text files, markup, or Markdown to appear in generative AI search." Yani **Google için gereksiz**. Ancak diğer LLM ecosystem'leri (Anthropic, Perplexity, OpenAI) llms.txt'i tercih edebilir; opt-in mekanizması (default OFF) bu trade-off'u proje sahibine bırakır. PSEO'nun default davranışı (`ai_training_optin: false`) Google'ın eleştirisinden zaten korunmuş haldedir.

**Enforcement.** init-project skill `project.config.json[content_settings.ai_training_optin]` boolean OFF default; kullanıcı ON yaparsa skill llms.txt generate eder.

**Failure mode.** Silent (default OFF).

### R-99: Per-Bot LLM Allow

**Statement.** `robots.txt` per-bot LLM allow/disallow rule'ları üç sınıfta ele alınır (2026):
- **Eğitim** (model eğitimi — müşteri kararı): `GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`, `Applebot-Extended`, `Bytespider`.
- **Arama** (AI cevap/arama dizini — engellemek siteyi o cevaplardan çıkarır): `OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot`.
- **Kullanıcı** (bir kişi asistana sorunca yapılan getirme): `ChatGPT-User`, `Claude-User`, `Perplexity-User`.

Varsayılan öneri: arama ve kullanıcı botlarına izin; eğitim botları müşteri kararı. `Claude-Web` kullanımdan kalktı (kural yazmak işe yaramaz). `project.config.json[ai_bots]` = müşterinin izin verdiği ajanlar; robots-policy-audit bunu okur (izinli ama engellenmiş ajan = MEDIUM, engellenmiş arama/kullanıcı botu = HIGH). Sınıf listesinin tek kaynağı: `scripts/discovery/robots_policy_transform.py::AI_BOT_CLASSES`.

**Rationale.** Principle 2. Per-project LLM training opt-in/opt-out kararı. **Önemli düzeltme:** `Google-Extended` yalnızca **Gemini uygulamaları ve Vertex AI** için training + grounding erişimini kontrol eder; Google **Arama sıralamasını VEYA AI Overview (AIO) kapsamını ETKİLEMEZ** (AIO, Googlebot taraması + snippet kontrolleriyle —`nosnippet`/`max-snippet`/`data-nosnippet`— yönetilir). Bu iki mekanizma ayrıdır; Google-Extended'i bloklamak AIO/Arama görünürlüğünü etkilemez.

**Enforcement.** robots-policy-audit (`AI_BOT_CLASSES` + `ai_bots` okunur, öneri müşterinin bilinçli bot engelini korur); init-project varsayılan `ai_bots` = klasik arama + AI arama + kullanıcı ajanları.

**Failure mode.** Arama botu engeli = HIGH bulgu; config/dosya uyuşmazlığı = MEDIUM.

### R-101: Self-Contained Intro + H2 Cevap-Önce (LLM-Friendly)

**Statement.** Content intro paragraph (R-01) **self-contained** — H1 referansı olmadan anlamlı; her H2 başlangıcında cevap-önce mini paragraf (R-29 reuse). LLM context window'unda izole paragraf parse şansı yüksek.

**Rationale.** Google'ın 2026-05-15 cümlesi: "You don't need to write in a specific way just for generative AI search." Self-contained intro AI için değil; **helpful content + scannability** için (Google self-assessment kriteri: "Is this content you'd want to bookmark, share, or recommend?"). Kullanıcı sayfada H2'leri tarayıp ilgilendiği bölüme atlar — her bölümün izole faydası olur. AI/LLM citation potansiyeli yan etki, hedef değil.

**Enforcement.** R-01 + R-29 birlikte uygulanır; self-contained check: intro paragraf "yukarıda gördüğünüz gibi" / "bu yazıda" referans regex → AMBER.

**Failure mode.** AMBER.

### R-102: AI Summary Footer (Key Takeaways Başlıksız Bullet)

**Statement.** Content sonuna (CTA paragraf öncesi) **AI summary footer**: 3-5 bullet point, **başlıksız** (R-05 reuse), `<aside class="pse-key-takeaways">` block.

**Rationale.** AI summary footer **insan UX için** — TL;DR formatı + yer imine eklenebilirlik, Google Helpful Content "Is this content you'd want to bookmark, share, or recommend?" kriteri. Başlıksız bullet R-05 sembol yasağıyla uyumlu (brand tone — generic AI imza önleme). AI/LLM bot'un bunu özet olarak alabilmesi yan etki, hedef değil.

**Enforcement.** Skill render time aside block inject; bullet count [3,5].

**Failure mode.** AMBER.

### R-103: Content Versioning Marker (Major Revise)

**Statement.** Major revise (`claim_delta > 5` VEYA `structure_changed` VEYA profil değişimi — revise-content Step 7 tek tanım) → içerik sürümü artar (v1 → v2). Sürüm **motorda** tutulur: `outputs/blog/{slug}/version.json` + change_summary geçmişi. Sayfaya standart dışı `<meta name="content-version">` etiketi YAZILMAZ (S-23: hiçbir arama motoru okumaz); sayfadaki tazelik sinyali gerçek değişiklikle birlikte güncellenen `dateModified`'dır (R-88).

**Rationale.** Hangi revizyonun ne değiştirdiği izlenebilir kalır; sayfaya anlamsız işaret eklenmez.

**Enforcement.** revise-content Step 7 version.json'u günceller.

**Failure mode.** Silent.

### R-106: Citation Patterns (Universal)

**Statement.** Citation pattern universal (Principle 3): per 500 word **min 1 max 2 citation** (aralık). Kaynak, iddianın olduğu yerde verilir; sayı bu ihtiyacın sonucudur. Format: `<a href="URL" rel="external noopener">Source Name</a>` veya inline parenthetical "(Source, 2024)".

**Rationale.** Principle 3 (UX overload önleme) + AIO citation density signal.

**Enforcement.** Pre-publish per-500-word window citation count; range dışı AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

---

## Cross-References

- → [content-quality](content-quality.md#foundational-principles) — 3 foundational principle (özellikle Principle 1 truth-verifiable, Principle 3 citation density)
- → [content-seo-discipline](content-seo-discipline.md) — H2 cevap-önce (R-29), AIO pattern (R-109)
- → [content-eeat-discipline](content-eeat-discipline.md) — Author + Organization schema entity binding
- → [secrets-management](secrets-management.md) — robots.txt + llms.txt opt-in privacy
- → [single-source-of-truth](single-source-of-truth.md) — ai_bots array + content_settings tek yerde
- → [naming](naming.md) — pse- prefix (`pse-key-takeaways`)

## Enforcement (Plugin-Level)

- Phase 11 production skill'ler bu rules dosyasını consume eder.
- LLMs.txt generation + per-bot robots.txt patch + citation density check Phase 11 acceptance gate'leri.
