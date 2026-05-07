---
name: Schema-First
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.2"
---

# Schema-First

## Kural
Bir veri şekli yazılmadan ÖNCE schema'sı `schemas/{name}.schema.json` dosyasında bulunmak ZORUNDADIR (MUST). Schema yoksa veri yazılmaz (MUST NOT). Tüm yazımlar pre-write validate'ten geçer (REQUIRED). Schema değişimi migration script'iyle birlikte gelir (REQUIRED).

## Why
"Önce kodu yazayım, schema'yı sonra çıkarırım" yaklaşımı her seferinde aynı şekilde başarısız olur: kod ile schema farklı şekiller üretir, validator yazılırken eski veriler artık geçerli değildir, geriye dönük migration yazmak ileri yazmaktan pahalıdır. Schema'yı önce sabitlemek, sistemin yazdığı her şeyi tek bir doğrulanabilir kontrata bağlar — bu, replay ve audit garantisinin temelidir.

## How to Apply
- Yeni veri şekli ihtiyacı → önce `schemas/{name}.schema.json` yaz, PR ile merge et.
- Schema $id: `http://platinum-seo-engine/schemas/<name>` (→ rules/naming.md).
- Yazım yolları schema validate çağırır: `events.jsonl` her append öncesi `events.schema.json`'a karşı doğrulanır.
- `master-excel.xlsx` schema'dan üretilir (ADR-009): `master-excel.schema.json` → `transaction.py` üretir.
- Schema bump (v1.0 → v1.1) → `scripts/migrations/{NNNN}_{schema-name}_{from}_to_{to}.py` (→ rules/schema-versioning-discipline.md, W-J).
- "Önce yazıp sonra çıkarma" yasak: schema'sız veri yazımı reddedilir.

## Examples (Doğru)
- Yeni `workflow-run` veri tipi: önce `schemas/workflow-run.schema.json` PR'ı, sonra `scripts/workflow/start.py` PR'ı.
- `events.jsonl` append akışı: `jsonschema.validate(entry, events_schema)` → ardından dosyaya append.
- Master excel sheet eklenmesi: `master-excel.schema.json` güncellenir → `transaction.py` regenerate eder.

## Anti-Patterns (Ihlal)
- Workspace'te schema'sı olmayan ad-hoc JSON dosyası (örn: `state/notes.json`) — drift kapısı.
- Kodda alan eklenmesi ama schema güncellenmemesi — validator eski schema ile geçer, gerçek veri uyumsuz.
- Schema bump sonrası migration yazılmaması — eski projeler açıldığında kırılır.

## Enforcement
- CI: `tests/schemas/test_all_schemas_exist.py` — yazım yapan her script için schema referansı doğrular.
- Pre-write hook: `scripts/hooks/validate_before_write.py` schema-first paired-update disiplinini staged diff üzerinden zorlar.
- Phase 13 `schema-validate` skill: tüm dosyaları schema'ya karşı tarar.
- Manuel review: PR review checklist "Yeni veri şekli için schema PR'ı önce mi geldi?" maddesi.
