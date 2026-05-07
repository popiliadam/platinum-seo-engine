---
name: Glossary Discipline
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.8"
---

# Glossary Discipline

## Kural
Her teknik terim `docs/GLOSSARY.md` içinde TEK kez tanımlanmalıdır. Skill, schema, disiplin, template ve dokümanlar bir terimi ilk kullandığında GLOSSARY girişine referans VERMELİDİR; ikinci bir tanım yazmak YASAKTIR. GLOSSARY'de bulunmayan teknik terim kullanmak `glossary-audit` tarafından AMBER warn olarak raporlanır ve eklenene dek geçici sayılır.

## Why
Aynı terimin iki farklı tanımı = drift. Bir skill "drift" derken X'i, bir disiplin Y'yi kastediyorsa otomasyon kararları zamanla birbirine ters düşer ve sistem güvenilirliğini kaybeder. Spec §8.8 glossary'yi tüm semantik karar zincirinin **tek kaynağı** olarak sabitler; bu disiplin §8.1 (single source of truth) prensibinin terim düzeyindeki özel halidir.

## How to Apply
- Yeni teknik terim yazmadan ÖNCE `docs/GLOSSARY.md` aç ve tanım ekle (alfabetik, tek paragraf).
- Skill description'larında, disiplin metinlerinde, schema açıklamalarında terimin ilk geçişinde GLOSSARY girişine atıf yap (örn. "drift (bkz. GLOSSARY)").
- Mevcut bir terimin anlamı değişiyorsa GLOSSARY'yi güncelle ve değişikliği DECISIONS.md'ye ADR olarak işle; tanımı dağıtık olarak değiştirme.
- `glossary-audit` skill'i AMBER warn ürettiğinde: terim eklenir VEYA metinden çıkarılır; warn'i görmezden gelmek YASAK.
- Domain-specific olmayan, jenerik İngilizce/Türkçe kelimeler GLOSSARY gerektirmez (örn. "dosya", "report") — sadece SEO/sistem teknik terimleri.

## Examples (Doğru)
```markdown
# rules/excel-discipline.md (örnek atıf)
Master Excel'e yazım sadece transaction layer üzerinden yapılır;
bu invariant check'i (bkz. docs/GLOSSARY.md#invariant) tetikler.
```

```markdown
# docs/GLOSSARY.md (yeni terim ekleme)
## quick-win
GSC'de pozisyon 8-20 aralığında olan ve düşük efor ile ilk sayfaya
çıkabilecek keyword/URL kombinasyonu. → skill: quick-wins
```

## Anti-Patterns (Ihlal)
```markdown
# YASAK — aynı terim iki dosyada farklı tanım
# rules/append-only-state.md: "Drift, state tutarsızlığıdır."
# skills/drift-check/SKILL.md: "Drift, schema versiyon farkıdır."
# → konflikt; GLOSSARY tek tanımı tutmalı.
```

```markdown
# YASAK — GLOSSARY'siz yeni terim
"Bu skill 'horizontal cannibalization' tespit eder."
# Glossary'de yok → glossary-audit AMBER → eklenmeden merge edilemez.
```

## Enforcement
- **Otomatik:** `glossary-audit` skill'i (Phase 13'te yazılacak) skill/disiplin/schema metinlerini tarar; GLOSSARY dışı teknik terimleri AMBER raporlar.
- **PR review checklist:** "Yeni terim varsa GLOSSARY'ye eklendi mi?" maddesi.
- **Manuel review:** Reviewer atıf eksikliğini bulursa fix isteyebilir.
- **Cross-link:** `→ rules/single-source-of-truth.md` (terim de bir SSOT türüdür); `→ rules/skill-description-discipline.md` (skill description'larında glossary terimleri kullanılır).
