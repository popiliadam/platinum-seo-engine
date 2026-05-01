---
name: Naming
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.6"
---

# Naming

## Kural
Tüm tanımlayıcılar (slug, dosya, skill, schema `$id`, slash command, run_id) projede sabitlenmiş tek bir biçim sözleşmesine uymak ZORUNDADIR (MUST). Sözleşme dışı yeni isim üretilmemelidir (MUST NOT). Yeni biçim önermek isteyen değişiklik, schema güncellemesi ile birlikte gelmelidir (REQUIRED).

## Why
Drift'in en sessiz girişi, isim kayışıdır: aynı varlık iki yerde iki farklı slug ile geçtiğinde grep, validator ve cross-reference patlar; replay bozulur. Spec §8.6, isim biçimini "pazarlık edilemez" 10 kuralın altıncısı olarak sabitler — çünkü slug regex'i `^[a-z][a-z0-9-]*$` tek satır olmasına rağmen tüm sistemi sıkı tutar.

## How to Apply
- Slug'lar: `^[a-z][a-z0-9-]*$` — yalnızca lowercase kebab-case, sayı izinli, ilk karakter harf.
- Skill adı: kebab-case (örn: `init-project`, `excel-write`).
- Schema dosyası: `{name}.schema.json` (kebab-case + `.schema.json` suffix).
- Schema `$id`: `http://platinum-seo-engine/schemas/<name>` (HTTP, ADR-012).
- Slash command prefix: `pseo-` (örn: `/pseo-init-project`).
- Run ID: `{slug}-{YYYY-MM-DD}-{short_uuid}` — workflow-run schema regex'i ile aynı.
- Excel sheet adı: snake_case.
- Python değişken: snake_case.
- Dosya adı (rules, scripts, templates): kebab-case.
- Timestamp depolaması ISO 8601 UTC; insan-yüzlü gösterim Europe/Istanbul (→ rules/time-discipline.md).

## Examples (Doğru)
- `schemas/master-excel.schema.json` — kebab-case, doğru suffix.
- `$id: "http://platinum-seo-engine/schemas/workflow-run"` — HTTP, kebab-case slug.
- `run_id: "init-project-2026-04-30-a1b2"` — `{slug}-{YYYY-MM-DD}-{hash4}`.
- `/pseo-init-project` — `pseo-` prefix + kebab-case.

## Anti-Patterns (Ihlal)
- `schemas/MasterExcel.schema.json` — CamelCase slug.
- `$id: "https://example.com/x"` — proje dışı host (ADR-012 ihlali).
- `/init-project` — `pseo-` prefix yok, çakışma riski.
- `run_id: "InitProject_20260430"` — tarih formatı bozuk, slug CamelCase.
- Plugin repo içinde proje-spesifik slug (örn: `acme-init` gibi gerçek proje slug'ı ile prefiks/suffiks) — §8.3 ihlali.

## Enforcement
- CI: `tests/naming/test_slug_regex.py` tüm `*.schema.json`, `commands/*.md`, `skills/*/SKILL.md` taranır.
- Pre-commit hook: `scripts/hooks/check_naming.py` (Phase 13'te otomatize).
- Manuel review: PR review checklist'inde "isim biçimi sözleşmeye uyuyor mu?" maddesi.
