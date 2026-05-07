---
name: Content Update Discipline
status: enforced
applies_to: [plugin]
applied_to_skills: [revise-content, content-remediation, faq-optimization]
source: docs/superpowers/specs/2026-04-30-content-rules-input.md (R-25) + Phase 10 decision matrix (R-85, R-86, R-87, R-88, R-89, R-90, R-91)
spec_section: "Phase 10 — Content Rules Processing"
---

# Content Update Discipline

Bu doc Phase 10 content lifecycle (decay → revise → sunset/prune) disiplinini tanımlar. **Foundational Principles** (3 üst-prensip) `→ rules/content-quality.md#foundational-principles` — burada tekrar yazılmaz (DRY, → [single-source-of-truth](single-source-of-truth.md)).

**Foundational Principles özeti** (tam metin için → [content-quality](content-quality.md#foundational-principles)):
1. **Truth-Verifiable Content** — revise sırasında uydurma yasak (R-87 change_summary log + R-88 freshness theater yasak).
2. **Profile-Aware Enforcement** — decay threshold profile-aware (R-85).
3. **AI Suistimal Önlemi** — freshness theater (R-88) AI imza paterni preempt.

---

## Rules

### R-25: Master Excel + MCP Efektif Kullanımı

**Statement.** Production skill'ler (new-blog, revise-content) içerik yazarken zorunlu kaynaklar:
- `master.xlsx[cluster_keywords]` → primary + secondary keywords (R-12).
- `master.xlsx[topical_map]` → pillar + cluster context (R-11).
- `master.xlsx[new_content_plan]` → planlanan başlık, target word count, intent (R-10).
- `master.xlsx[internal_links]` → eklenecek linkler (R-06).
- `dataforseo_labs_keyword_*` MCP → keyword desteği.
- `Scrapling` MCP → SERP top-5 (R-08).
- `dataforseo_on_page_content_parsing` MCP → site mevcut içerik (R-15 doğrulama).

**Rationale.** Single source of truth (→ [single-source-of-truth](single-source-of-truth.md)) — content kararları master.xlsx + MCP'den, skill internal state'den değil.

**Enforcement.** Skill workflow ilk step'lerde fetch; eksikse RED.

**Failure mode.** RED.

### R-85: Decay Multi-Signal Threshold

**Statement.** Content decay multi-signal threshold:
- GSC clicks delta < -30% (90 day vs prior 90) **AND** position delta > +5 (kötüleşme), **VEYA**
- Impressions delta < -40% **AND** ranking trend negative.

Profile-aware:
- YMYL: decay threshold daha sıkı (-20% clicks, +3 position).
- e-commerce: -30% clicks, +5 position.
- Diğer: -30% / +5 default.

**Rationale.** Multi-signal threshold tek-signal noise'i filtreler (single-keyword volatilite ≠ decay).

**Enforcement.** content-decay skill multi-signal compute; threshold geçen URL'ler `master.xlsx[content_decay]` sheet'e yazılır.

**Failure mode.** N/A (discovery skill output).

### R-86: Decay Weekly Check + Approve Workflow

**Statement.** content-decay skill **haftalık** otomatik check (cron veya scheduled). Decay candidate'lar `master.xlsx[content_decay].action` field'ında `pending_approve` status; user approve sonrası revise-content skill triggered.

**Rationale.** Otomatik revise yasak (Süleyman explicit) — manual approve gate.

**Enforcement.** content-decay output `action=pending_approve`; user explicit approve → master.xlsx update → revise-content trigger.

**Failure mode.** Silent (manual gate).

### R-87: Section-Targeted Revise + change_summary Log

**Statement.** revise-content skill **section-targeted** (full-rewrite yasak default; major revise R-103 explicit flag). Skill change diff section seviyesinde compute eder; `change_summary` field `master.xlsx[completed_work].note` veya events.jsonl'da log'lar.

**Rationale.** Section-targeted revise SEO-safe (canonical preserve R-89, ranking history korunur); full-rewrite yeni content gibi (re-indexing risk).

**Enforcement.** revise-content skill diff scope per-H2 section; output change_summary structured (added_sections, removed_sections, updated_sections).

**Failure mode.** Major revise → R-103 version marker.

### R-88: Freshness Theater Yasak

**Statement.** Sahte güncellik yasak: dateModified update edip içeriği değiştirmemek (sadece tarih bump) **YASAK**. Genuine content change zorunlu.

**Rationale.** Principle 3 (AI imza paterni preempt) + Google freshness theater detection (Helpful Content Update penalty).

**Enforcement.** revise-content skill change_summary boş veya word diff < 50 word → AMBER → 2x AMBER → RED. dateModified update'i content diff olmadan reject.

**Failure mode.** RED.

### R-89: Canonical Preserve on Revise

**Statement.** Revise sonrası `<link rel="canonical">` URL **değişmez** (URL slug korunur). dateModified update ISO 8601 (`2026-05-02T10:00:00+03:00` Europe/Istanbul → UTC normalize).

**Rationale.** Canonical change = yeni content (ranking history kaybı). dateModified update + canonical preserve → genuine refresh sinyali.

**Enforcement.** revise-content skill canonical immutable; URL slug değişmesi gerekirse R-91 redirect path.

**Failure mode.** RED.

### R-90: Sunset/Prune Suggestion + Manual Approve

**Statement.** content-decay sunset/prune candidate (decay threshold + low traffic + cluster relevance gone) **suggestion only**; user manual approve sonrası R-91 redirect/410 path.

**Rationale.** Otomatik silme yasak; silme operasyonu **manual approve** gerektirir (cross-doc safety paterni).

**Enforcement.** content-decay output `action=sunset_suggestion`; user explicit approve → master.xlsx update → R-91 trigger.

**Failure mode.** Silent (manual gate).

### R-91: Silinen URL 301/410 Decision Tree

**Statement.** Sunsetted/pruned URL decision tree:
- Cluster relevance gone + low traffic → **410 Gone** (Google permanent removal signal).
- Cluster relevance partial + redirect target var → **301 Permanent Redirect** (link equity transfer).
- Decision: `master.xlsx[redirect_404].action` enum (`301`, `410`); user override.

**Rationale.** 301 vs 410 SEO impact farklı; 410 hızlı deindex, 301 link equity korur.

**Enforcement.** content-remediation skill redirect_404 sheet read; web server config (htaccess, nginx) generate.

**Failure mode.** Manual config (skill output reference).

---

## Cross-References

- → [content-quality](content-quality.md#foundational-principles) — 3 foundational principle (özellikle Principle 1 truth-verifiable refresh, Principle 3 freshness theater preempt)
- → [content-seo-discipline](content-seo-discipline.md) — section-targeted revise + heading hierarchy
- → [content-llm-discipline](content-llm-discipline.md) — content versioning marker (R-103)
- → [excel-discipline](excel-discipline.md) — master.xlsx[content_decay], [completed_work], [redirect_404] sheet
- → [append-only-state](append-only-state.md) — change_summary events.jsonl append (revise audit trail)
- → [time-discipline](time-discipline.md) — dateModified ISO 8601 UTC + Europe/Istanbul render
- → [single-source-of-truth](single-source-of-truth.md) — master.xlsx ana otorite

## Enforcement (Plugin-Level)

- Phase 11 production skill'ler (revise-content, content-remediation, faq-optimization) bu rules dosyasını consume eder.
- Decay weekly cron + approve workflow + change_summary log + canonical preserve Phase 11 acceptance gate'leri.
