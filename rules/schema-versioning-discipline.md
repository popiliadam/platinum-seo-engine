---
name: Schema Versioning Discipline
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.11"
---

# Schema Versioning Discipline

## Kural
Bir schema'nın `schema_version` alanı her değiştiğinde `scripts/migrations/{NNNN}_{schema-name}_{from}_to_{to}.py` migration script'i ZORUNLU yazılır. Minor bump (`1.0 → 1.1`) backward-compatible alan eklemek için, major bump (`1.0 → 2.0`) breaking değişiklik içindir. Session-start hook açılan workspace'in `project-memory.json` `schema_version` alanını okuyup mevcut sürümle karşılaştırmalı; eski ise migration tetiklenmeli, atlanmamalıdır.

## Why
Sessiz schema değişikliği = farklı zamanlarda yazılmış workspace'lerin birbiriyle uyumsuz hale gelmesi. Bir Excel sheet 1.0 formatıyla, bir başka run 1.1 formatıyla yazılırsa cross-sheet invariant'lar kırılır ve drift tespit edilemez. Spec §8.11 versioning'i 10 pazarlık edilemez kuraldan biri yapar; migration script'i versiyon geçişlerinin yeniden üretilebilirliğini garanti eder. Phase 1.4'te eklenen `schema_version` alanı bu disiplinin runtime hook'udur.

## How to Apply
- Schema dosyasında `schema_version` field'ı top-level zorunludur (örn. `"schema_version": "1.0"`).
- Backward-compat alan eklemesi → minor bump (1.0 → 1.1) + idempotent migration script.
- Required alan değiştirme / silme / tip değişikliği → major bump (1.0 → 2.0) + tam migration + tüm consumer skill'lerin güncellenmesi.
- Migration script kuralları: idempotent, dry-run destekli, eski dosyayı `archive/` altına TAŞIR (silmez — ADR-004).
- Session-start hook (Phase 5+ workspace bootstrap) `schema_version` mismatch'i bulduğunda: kullanıcıya migration'ı bildir, onay sonrası koş, audit trail `events.jsonl`'a yaz.
- Bump ADR olarak `docs/DECISIONS.md`'ye işlenir (neden, breaking mi, migration path).

## Examples (Doğru)
```python
# scripts/migrations/0003_project_memory_1.0_to_1.1.py
"""Add 'autonomy_profile' field (default='balanced'). Backward-compat."""
def migrate(doc: dict) -> dict:
    if doc.get("schema_version") != "1.0":
        return doc  # idempotent
    return {**doc, "schema_version": "1.1", "autonomy_profile": "balanced"}
```

```json
// project-memory.json (post-migration)
{ "schema_version": "1.1", "project_slug": "ornek", "autonomy_profile": "balanced", ... }
```

## Anti-Patterns (Ihlal)
```python
# YASAK — schema'yi sessizce degistir, migration yazma
# schemas/project-memory.schema.json'a yeni required field eklendi
# ama schema_version 1.0 kaldi → eski workspace'ler validate FAIL
```

```python
# YASAK — destructive migration (eski dosyayi sil)
os.remove("project-memory.v1.json")  # append-only-state ihlali
```

## Enforcement
- **Schema CI test:** `tests/schemas/test_versioning.py` her schema'da `schema_version` zorunluluğunu ve format'ını (`MAJOR.MINOR`) kontrol eder.
- **Migration coverage test:** Her `schema_version` değişikliği için `scripts/migrations/` altında matching script aranır; eksikse FAIL.
- **Session-start hook:** Workspace açılışında `schema_version` kontrolü; mismatch → migration prompt.
- **Cross-link:** `→ rules/schema-first.md` (schema önce yazılır, sonra versiyonlanır); `→ rules/append-only-state.md` (migration eski dosyayı silmez, archive eder).
