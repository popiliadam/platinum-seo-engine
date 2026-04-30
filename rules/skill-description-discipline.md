---
name: Skill Description Discipline
status: enforced
applies_to: [plugin]
spec_section: "§8.9 + §9"
---

# Skill Description Discipline

## Kural
Her skill'in YAML frontmatter'ı `schemas/skill-frontmatter.schema.json` ile valide edilmek ZORUNDADIR. `description` alanı en az 30 karakter uzunluğunda olmalı ve `Use when:`, `Also use when:`, `Do not use when:` üç başlığını **description string'inin İÇİNDE** taşımalıdır. Bu üç başlık ASLA ayrı YAML field'ları olarak (`use_when:`, `also_use_when:`, `do_not_use_when:`) yazılmamalıdır — bu form ADR-013 ile açıkça reddedilmiştir.

## Why
Claude Code skill'i otomatik tetiklerken sadece `description` string'ini okur; ayrı field'lar trigger pipeline'ında görünmez ve skill yanlış zamanda etkinleşir veya hiç tetiklenmez. Spec §9 string-internal yapıyı tek doğru form olarak sabitler. ADR-013 (Phase 1.4) bu kararı kalıcılaştırdı: "Worker spec authority'yi manager brief'inin üstünde tuttu, drift kapısı kapalı." 30-karakter minimumu auto-trigger için yeterli semantik sinyal sağlamayı garantiler.

## How to Apply
- Skill yazarken `description` alanını block-scalar (`|`) olarak yaz ve üç başlığı sırasıyla ekle: `Use when: ...`, `Also use when: ...`, `Do not use when: ...`.
- Description ≥ 30 karakter; trigger sinyallerini açık ifade kullan (kullanıcı söz öbekleri, eş anlamlılar, negatif sınırlar).
- Schema validate komutunu commit öncesi koş: `pytest tests/schemas/test_skill_frontmatter.py` (Phase 1.5'te yazılır).
- Description içinde geçen teknik terimler için `→ rules/glossary-discipline.md` kuralına uy.
- Ayrı bir `use_when` field'ı eklemek isteği gelirse: ADR-013'e referansla reddet, gerekirse yeni ADR aç.

## Examples (Doğru)
```yaml
---
name: quick-wins
description: |
  Use when: kullanici "quick win", "hizli kazanim", "8-20 siradaki
  keyword'ler", "low-hanging fruit" gibi ifadeler kullandiginda.
  Also use when: GSC verisi varken siralamada yukselebilecek
  firsatlari ararken. Do not use when: yeni icerik plani, icerik
  iyilestirme veya teknik audit istendiginde.
status: active
category: discovery
---
```

## Anti-Patterns (Ihlal)
```yaml
# YASAK — ayri field formu (ADR-013 ile reddedildi)
---
name: quick-wins
description: GSC quick win analizi
use_when: kullanici "quick win" derken
also_use_when: GSC verisi mevcutken
do_not_use_when: teknik audit istendiginde
---
# Trigger pipeline ayri field'lari okumaz; skill yanlis tetiklenir.
```

```yaml
# YASAK — 30 karakter alti description
---
name: foo
description: foo skill
---
# minLength=30 schema validation FAIL.
```

## Enforcement
- **Schema validation:** `schemas/skill-frontmatter.schema.json` `description` için `minLength: 30` ve string-internal kontrolünü kilitler; `tests/schemas/test_skill_frontmatter.py` her PR'da koşar.
- **`glossary-audit` skill'i:** Description'ı tarayıp `Use when` / `Also use when` / `Do not use when` üçlüsünün varlığını kontrol eder (Phase 13).
- **ADR referansı:** `docs/DECISIONS.md` ADR-013 — "frontmatter use_when/also_use_when/do_not_use_when ayrı field değil, description string'i içinde."
- **Cross-link:** `→ rules/glossary-discipline.md` (description'daki terimler GLOSSARY'ye bağlanır); `→ rules/schema-first.md` (skill-frontmatter.schema.json önce yazılır).
