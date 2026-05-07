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

**Rationale.** LLMs.txt emerging standard (2024+); opt-in kullanıcı kararı (training data exposure trade-off).

**Enforcement.** init-project skill `project.config.json[content_settings.ai_training_optin]` boolean OFF default; kullanıcı ON yaparsa skill llms.txt generate eder.

**Failure mode.** Silent (default OFF).

### R-99: Per-Bot LLM Allow

**Statement.** `robots.txt` per-bot LLM allow/disallow rule'ları (`GPTBot`, `ClaudeBot`, `Google-Extended`, `PerplexityBot`, `CCBot`). `project.config.json[ai_bots]` array consume.

**Rationale.** Principle 2. Per-project LLM training opt-in/opt-out kararı; ranking impact (Google-Extended block edersen AIO citation şansı düşer).

**Enforcement.** init-project + content-remediation skill robots.txt patch; ai_bots array per-bot directive render.

**Failure mode.** Silent (default empty allow-all).

### R-101: Self-Contained Intro + H2 Cevap-Önce (LLM-Friendly)

**Statement.** Content intro paragraph (R-01) **self-contained** — H1 referansı olmadan anlamlı; her H2 başlangıcında cevap-önce mini paragraf (R-29 reuse). LLM context window'unda izole paragraf parse şansı yüksek.

**Rationale.** LLM/AIO bot full-page parse etmez; izole paragraf citation candidate. Self-contained intro citation şansı 3x.

**Enforcement.** R-01 + R-29 birlikte uygulanır; self-contained check: intro paragraf "yukarıda gördüğünüz gibi" / "bu yazıda" referans regex → AMBER.

**Failure mode.** AMBER.

### R-102: AI Summary Footer (Key Takeaways Başlıksız Bullet)

**Statement.** Content sonuna (CTA paragraf öncesi) **AI summary footer**: 3-5 bullet point, **başlıksız** (R-05 reuse), `<aside class="pse-key-takeaways">` block.

**Rationale.** AI summary footer AIO citation candidate (özet bullet hızlı extract); başlıksız (R-05) generic AI imza önleme.

**Enforcement.** Skill render time aside block inject; bullet count [3,5].

**Failure mode.** AMBER.

### R-103: Content Versioning Marker (Major Revise)

**Statement.** Major revise (R-87 section-targeted bilinen, > 30% content değişimi) → content versioning marker `<meta name="content-version" content="v{{N}}">` head'de. v1 default; v2+ revise sonrası increment.

**Rationale.** AIO/LLM bot freshness signal; major revise re-citation şansı.

**Enforcement.** revise-content skill change_summary > 30% → version increment.

**Failure mode.** Silent.

### R-106: Citation Patterns (Universal)

**Statement.** Citation pattern universal (Principle 3): per 500 word **min 1 max 2 citation**. Format: `<a href="URL" rel="external noopener">Source Name</a>` veya inline parenthetical "(Source, 2024)".

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
