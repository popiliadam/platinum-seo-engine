---
name: Single Source of Truth
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.1"
---

# Single Source of Truth

## Kural
Bir terim, schema, template, kural veya veri TEK YERDE tanımlanmak ZORUNDADIR (MUST). Aynı bilgi ikinci bir yere kopyalanmamalı (MUST NOT); ihtiyaç halinde referans verilmelidir (REQUIRED). Plugin (motor) read-only tooling tutar; workspace (proje deposu) runtime veriyi tutar — bu ayrım korunur.

## Why
Drift, çoğunlukla iyi niyetli kopyala-yapıştırla başlar: aynı kural spec'te bir biçimde, README'de başka biçimde yazıldığında zamanla iki sürüm de "doğru" gibi görünür ve sistem hangisinin geçerli olduğunu kaybeder. Plugin agnostiklik (ADR-008) bu disiplinin pratik sonucudur: motor proje verisini taşımaz; aksi halde tek bir gerçek tanımı belirlemek imkânsızlaşır.

## How to Apply
- Bir terim/glossary girdisi yalnızca `docs/GLOSSARY.md`'de tanımlanır (→ rules/glossary-discipline.md).
- Bir schema yalnızca `schemas/{name}.schema.json` dosyasında yaşar; başka yerde alan listesi tekrarlanmaz, schema'ya `$ref` verilir.
- Plugin repo: skill, command, hook, script, schema, rule, template — read-only tooling.
- Workspace repo: project memory, `events.jsonl`, `master.xlsx`, `outputs/`, `inbox/`, `state/` — runtime veri.
- Kural metni `rules/*.md`'de; spec yalnızca özet ve gerekçe; tekrarlanan bullet listesi yasak.
- Doküman tekrarı yerine link: `→ rules/schema-first.md` formatında cross-link kullan.

## Examples (Doğru)
- Spec §8.6 naming kurallarını özetler; tam normatif metin `rules/naming.md`'dedir; başka yerde yoktur.
- `master-excel.xlsx` schema'dan üretilir (ADR-009); sheet yapısı yalnızca `master-excel.schema.json`'da tanımlıdır.
- Plugin `commands/pseo-init-project.md` proje adı içermez; proje verisi workspace'tedir.

## Anti-Patterns (Ihlal)
- Aynı kural metni hem `docs/spec.md` hem `README.md` içinde — iki yer divergea açıktır.
- Plugin içinde hard-coded `demo-dental` ya da `demo-furniture` slug'ı — §8.3 + SSOT ihlali.
- `schemas/foo.schema.json` ve `scripts/foo_writer.py` içinde alan listesinin elle tekrarlanması — schema değişince script unutulur.
- Workspace verisinin (örn: `events.jsonl` örnekleri) plugin repo'ya commit edilmesi.

## Enforcement
- CI: `scripts/checks/grep_project_names.sh` plugin repo'da proje slug'ı arar.
- CI: `tests/duplication/test_no_duplicate_glossary_terms.py`.
- Manuel review: PR review checklist "Bu bilgi başka bir yerde de var mı?" maddesi.
- Cross-link: → rules/append-only-state.md, → rules/schema-first.md.
