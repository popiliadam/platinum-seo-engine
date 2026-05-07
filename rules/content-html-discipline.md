---
name: Content HTML Discipline
status: enforced
applies_to: [plugin]
applied_to_skills: [new-blog, revise-content, faq-optimization, content-remediation, generate-images]
source: docs/superpowers/specs/2026-04-30-content-rules-input.md (R-20..R-24) + Phase 10 decision matrix (R-31, R-35, R-39, R-43, R-57..R-65, R-71..R-77)
spec_section: "Phase 10 — Content Rules Processing"
---

# Content HTML Discipline

Bu doc Phase 10 HTML/CSS/image disiplinini tanımlar. **Foundational Principles** (3 üst-prensip) `→ rules/content-quality.md#foundational-principles` — burada tekrar yazılmaz (DRY, → [single-source-of-truth](single-source-of-truth.md)).

**Foundational Principles özeti** (tam metin için → [content-quality](content-quality.md#foundational-principles)):
1. **Truth-Verifiable Content** — uydurma yasak (R-27).
2. **Profile-Aware Enforcement** — `project.config.json[profiles]` array consume (Principle 2 tablosu).
3. **AI Suistimal Önlemi** — cheap content padding preempt; image özelinde 8K ultra realistic + nano banana model (R-71, R-72).

---

## Rules

### R-20: Format HTML

**Statement.** Content HTML olarak yazılır (markdown değil). new-blog template `.html` extension; revise template diff hedefi de HTML.

**Rationale.** WordPress/Ticimax/Ideasoft custom-block render direkt HTML kabul; markdown intermediate format çevriminde formatting drift olur.

**Enforcement.** Skill output `*.html` dosya. `<` and `>` literal escape edilmez (raw HTML).

**Failure mode.** RED — markdown çıktısı reject.

### R-21: Semantic HTML5

**Statement.** Tamamen semantic HTML5 tag: `<article>`, `<section>`, `<aside>`, `<nav>`, `<header>`, `<footer>`, `<h1>..<h4>`, `<p>`, `<ul>`, `<ol>`, `<table>`, `<figure>`, `<figcaption>`, `<blockquote>`, `<cite>`, `<time>`, `<address>`. `<div>` ve `<span>` minimum.

**Rationale.** Semantic HTML accessibility (R-39 WCAG) + SEO + AIO citation parsing kolaylığı.

**Enforcement.** W3C HTML validation pre-publish (R-59); non-semantic div sayısı eşik üstü AMBER.

**Failure mode.** AMBER → manual review.

### R-22: Header/Footer Dokunulmazlığı

**Statement.** Üretilen HTML site'in `<header>` ve `<footer>`'ında bozulma yaratmayacak. Sadece `<article>` veya `<main>` içine yerleştirilecek HTML fragment üretilir.

**Rationale.** R-57 (HTML fragment boundary) ile birlikte WordPress/Ticimax custom-block paste'inde global layout korunur.

**Enforcement.** Output HTML kök element `<article class="pse-blog-post">` (template skeleton); `<html>`, `<head>`, `<body>`, `<header>` (site header), `<footer>` (site footer) tag'leri output'ta YASAK.

**Failure mode.** RED.

### R-23: CSS (Inline + Kurumsal Renk)

**Statement.** Inline minify CSS kabul edilebilir (`<style>` blok). Kurumsal renk + tasarım dili korunur (per-project). Kaynak: `project.config.json[brand_identity]` (logo, primary_color, secondary_color, accent_color, font_family_heading, font_family_body).

**Rationale.** Profile-aware (Principle 2) brand consistency; CSS strategy tier'a göre değişir (R-60).

**Enforcement.** Skill template render-time `{{PRIMARY_COLOR}}` slot'ı `brand_identity.primary_color`'dan doldurur; eksikse profile-default (gri/nötr).

**Failure mode.** Silent fallback (profile-default) — log AMBER.

### R-24: Tasarım Sample (Init'te 1 Kez)

**Statement.** `init-project` skill opsiyonel olarak **Scrapling MCP** ile sitenin bir sayfasını fetch eder; renk paleti + font family + header/footer template örneği çıkarır; `project.config.json[brand_identity]`'ye yazar. Bir kez yapılır.

**Rationale.** Manual brand_identity giriş yerine otomatik bootstrap; R-23 slot'larını doldurur.

**Enforcement.** init-project Phase 5 paterni reuse (W-Q); skill `source_url_for_sampling` field'ı set eder.

**Failure mode.** Silent — manual brand_identity fallback.

### R-31: TOC Strategy (Project-Config)

**Statement.** Table of Contents (`<nav class="pse-toc">`) strategy `project.config.json[content_settings.toc_strategy]` enum'undan: `none` / `static` / `sticky` / `auto-generate`.

**Rationale.** Profile-aware. b2b-saas long-form 3000+ word'de sticky TOC UX zorunlu; e-commerce category page'de TOC yok.

**Enforcement.** Skill render time `toc_strategy` okur; HTML inject edilir (varsa).

**Failure mode.** Silent (default `none`).

### R-35: Meta Pixel Cap

**Statement.** Meta title pixel ≤ 580px (Türkçe ortalama ~60 char) + meta description pixel ≤ 990px (~155 char). Pixel cap char cap'ten otoriter (Türkçe `ş`, `ğ`, `ı` farklı pixel).

**Rationale.** Google SERP truncate threshold pixel-based değil character-based değil; tasarım drift önleme.

**Enforcement.** Skill output meta title/description için pixel ölçer (PIL render veya font metric); over-budget → revize.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-39: WCAG 2.1 AA

**Statement.** Tüm output HTML WCAG 2.1 AA compliant: contrast ratio ≥ 4.5:1 (normal text) + 3:1 (large text 18pt+); heading hierarchy linear (h1→h2→h3, atlama yok); alt text non-decorative image'larda zorunlu (R-77); keyboard navigation (focus-visible).

**Rationale.** Erişilebilirlik + KVKK/AB Direktif 2019/882 (Türkiye uyum 2025+); SEO ranking signal.

**Enforcement.** Pre-publish axe-core veya Pa11y validate pass.

**Failure mode.** RED.

### R-43: FAQ Accordion Yasak

**Statement.** FAQ block **statik visible** olacak. JavaScript-collapsed accordion YASAK. AIO/Google bot accordion içeriği tam parse edemez (lazy hidden content devalued).

**Rationale.** Principle 3 (AIO citation şansı) + WCAG (R-39 keyboard nav).

**Enforcement.** Template `templates/content/faq-block.template.html` accordion-free; skill output'ta `<details>` veya `display:none` accordion CSS reddi.

**Failure mode.** RED.

### R-57: HTML Fragment Boundary (Article Scope)

**Statement.** Skill output **fragment** — kök element `<article class="pse-blog-post">`; `<!DOCTYPE>`, `<html>`, `<head>`, `<body>` YASAK. CSS `<style>` blok inline (article scope'unda).

**Rationale.** R-22 reuse. Custom-block paste'inde global page render bozmaz.

**Enforcement.** Output regex check: `<!DOCTYPE` veya `<html` → RED.

**Failure mode.** RED.

### R-58: Lifecycle-Aware Robots Meta

**Statement.** Content lifecycle status (`master.xlsx[new_content_plan].lifecycle_status`) → robots meta map: `GREEN`/`RED` → `index,follow`; `ON_HOLD` → `noindex,follow`; `REMOVED` → 410/301 (R-91).

**Rationale.** Profile-aware Principle 2. Hold'daki content'i Google crawl etmesin ama internal link'ler korunur.

**Enforcement.** Skill `<meta name="robots">` lifecycle map'ten render eder.

**Failure mode.** AMBER (default `index,follow` fallback).

### R-59: W3C HTML Validation Pre-Publish

**Statement.** Pre-publish W3C Nu HTML Checker veya equivalent validator pass; warnings tolere edilir, error'lar RED.

**Rationale.** Malformed HTML AIO parsing fail + browser inconsistency.

**Enforcement.** Phase 11+ CI: `python -m html5lib --validate` veya hosted Nu validator.

**Failure mode.** RED.

### R-60: CSS Strategy (Profile-Aware)

**Statement.** CSS strategy `project.config.json[content_settings.css_strategy]` enum: `inline` / `external-tier` / `hybrid`. Default `inline` (R-23 reuse).

**Rationale.** Profile-aware Principle 2. b2b-saas main site mevcut CSS framework'üne entegre → `external-tier`; e-commerce custom block paste → `inline`.

**Enforcement.** Skill render time strategy okur; `external-tier` → CSS class ref only, `<style>` boş.

**Failure mode.** Silent (default `inline`).

### R-61: pse- Prefix BEM

**Statement.** Tüm HTML CSS class'ı `pse-` prefix + BEM (`pse-block__element--modifier`). Örn: `pse-blog-post`, `pse-faq-item`, `pse-cta`, `pse-toc__link--active`.

**Rationale.** Plugin agnostik (→ [single-source-of-truth](single-source-of-truth.md)) + site-side CSS çakışma önleme + → [naming](naming.md) kebab-case.

**Enforcement.** Skill output regex check: `class="(?!pse-)` non-pse class → RED.

**Failure mode.** RED.

### R-62: Image Dimensions + Lazy Loading (CLS)

**Statement.** Tüm `<img>` tag'i `width` + `height` attribute zorunlu (CLS önleme). `loading="lazy"` default; LCP hero image (R-77) `loading="eager"` + `fetchpriority="high"`.

**Rationale.** Core Web Vitals (CLS + LCP). Layout shift ranking penalty.

**Enforcement.** Skill template her `<img>` için dimension slot zorunlu (manuel upload sonrası filled).

**Failure mode.** AMBER (dimension missing) → 2x AMBER → RED.

### R-63: Mobile Parity Strict

**Statement.** Mobile + desktop content **bit-bit aynı** olacak. Mobile-only veya desktop-only content yasak (responsive CSS OK ama content gizleme yasak).

**Rationale.** Google mobile-first indexing (2024+); content parity Helpful Content sinyali.

**Enforcement.** CSS `display:none` only ornamental element'lerde (decorative); content elementlerde RED.

**Failure mode.** RED.

### R-64: HTML/CSS Minify

**Statement.** Output HTML + inline CSS minify edilir (whitespace collapse, comment strip). Pretty-printed development değil.

**Rationale.** Page weight + LCP.

**Enforcement.** Skill render time `htmlmin` veya manual whitespace collapse.

**Failure mode.** Silent.

### R-65: Page Speed Budget

**Statement.** Content HTML fragment + inline CSS toplam ≤ 30KB (gzip öncesi). Image budget ayrı (R-71 LCP optimization).

**Rationale.** LCP < 2.5s threshold için fragment-level budget.

**Enforcement.** Skill output byte ölçüm; > 30KB → AMBER.

**Failure mode.** AMBER → 2x AMBER → RED.

### R-71: Image Generation 8K Ultra Realistic

**Statement.** Image generation prompt'u "8K ultra realistic" tone preference (Süleyman explicit cevap). Style profile-aware (Principle 2 image style boyutu).

**Rationale.** Cheap AI image (artifact, low-res, anime drift) brand reputation kırar.

**Enforcement.** generate-images skill prompt template `quality: 8k ultra realistic, photographic` injection.

**Failure mode.** Silent (skill kullanıcı override izinli).

### R-72: Image Model Nano Banana

**Statement.** Default image generation model `nano-banana` (Higgsfield veya equivalent). Model `project.config.json[content_settings.image_model]` ile override edilebilir.

**Rationale.** Süleyman explicit model preference. Plugin agnostik (model değiştirilebilir).

**Enforcement.** generate-images skill default model = `nano-banana`; override değer schema enum'undan seçilir.

**Failure mode.** Silent (fallback nano-banana).

### R-73: Image Manual Upload

**Statement.** Image generation skill output → `outputs/images/{slug}-{kind}.{ext}` filesystem yazar; **manual upload** (Süleyman WordPress media library'ye yükler). Skill schema markup URL'ini placeholder bırakır (`{{IMAGE_URL_REPLACE}}`).

**Rationale.** Auto-upload WordPress credential exposure + plugin agnostik (Ticimax/Ideasoft farklı API). Manual upload + replace step audit trail temiz.

**Enforcement.** generate-images skill output URL field `{{...}}` placeholder; → `templates/content/upload-instructions.template.md` skill output'a append.

**Failure mode.** Silent (placeholder enforce).

### R-74: Multi-Skill Collaborative Output (Manual Upload Reference)

**Statement.** Manual upload reference doc multi-skill output: new-blog skill yazar (meta title + meta desc + H1 + slug + alt text + schema URL placeholder); generate-images append (hero image filename + schema URL replace step); revise-content append (varsa updated date + change_summary).

**Rationale.** Süleyman Q-W-C2-01 paterni reuse — multi-skill output collaborative aggregation.

**Enforcement.** Template `templates/content/upload-instructions.template.md` her skill için section.

**Failure mode.** Silent (manual workflow).

### R-75: Image LCP Optimization

**Statement.** Hero image (LCP candidate): `<picture>` tag + AVIF/WebP source + JPG fallback; `loading="eager"` + `fetchpriority="high"`; preload `<link rel="preload">` head'de (skill scope dışı, R-22 enforcement).

**Rationale.** LCP < 2.5s ranking signal.

**Enforcement.** Skill template hero image slot `<picture>` skeleton; non-hero `<img>` lazy.

**Failure mode.** AMBER (LCP > 2.5s manual measure post-publish).

### R-76: Image Fallback

**Statement.** Modern format (AVIF/WebP) + fallback (JPG) `<picture>` tag ile birlikte. Tek format yasak.

**Rationale.** Browser compatibility (Safari < 16 AVIF desteği yok).

**Enforcement.** Skill template `<picture>` skeleton.

**Failure mode.** AMBER.

### R-77: Image Alt Text

**Statement.** Decorative image hariç tüm `<img>` `alt` attribute zorunlu; alt text descriptive (60-125 char), keyword stuffing yasak.

**Rationale.** R-39 WCAG + SEO; AIO image citation sinyali.

**Enforcement.** Pre-publish regex check: `<img>` alt boş veya missing → RED.

**Failure mode.** RED.

---

## Cross-References

- → [content-quality](content-quality.md#foundational-principles) — 3 foundational principle
- → [content-seo-discipline](content-seo-discipline.md) — heading hierarchy, schema markup
- → [content-llm-discipline](content-llm-discipline.md) — AIO image citation
- → [naming](naming.md) — pse- prefix kebab-case
- → [single-source-of-truth](single-source-of-truth.md) — plugin agnostik

## Enforcement (Plugin-Level)

- Phase 11 production skill'ler bu rules dosyasını consume eder.
- W3C validate + axe-core/Pa11y + image dimension check Phase 11 acceptance gate'leri.
