---
name: Excel Discipline
status: enforced
applies_to: [workspace]
spec_section: "§8.5"
---

# Excel Discipline

## Kural
Master excel (`master-excel.xlsx`) SADECE `scripts/excel/transaction.py` üzerinden yazılmak ZORUNDADIR (MUST). Direkt yazım, manuel düzenleme ve formül kullanımı YASAKTIR (MUST NOT). Hücreler `formula_policy: values_only` ile yalnızca düz değer içerir (REQUIRED). Her yazım: backup → atomic write (tmp + rename) → invariant check sırasını izler; backup rotation son 7 snapshot'u FIFO tutar (REQUIRED).

## Why
Excel formülü drift'in en hızlı kapısıdır: VLOOKUP/SUM/INDEX-MATCH formülleri başka bir hücreye bağımlılık yaratır, plugin replay'inde aynı sonucu üretmez, schema'dan üretim zincirini kırar. Master excel schema'dan üretilir (ADR-009) — yani gerçek değer schema + üretici scripttedir, formülde değil. Atomic write yarım yazımı engeller; backup, geri dönüşü garanti eder.

## How to Apply
- Yazım yolu: yalnızca `scripts/excel/transaction.py`. CLI/IDE'den manuel `.xlsx` editi yasak.
- Formül yasağı: `=` ile başlayan hücre değeri reddedilir; tüm değerler statik (string, number, date).
- Atomic write: backup snapshot → `master-excel.xlsx.tmp` yazılır → fsync → `os.replace` ile rename.
- Backup rotation: `backups/master-excel-{ISO_TIMESTAMP}.xlsx`; son 7 dosya tutulur, daha eskileri FIFO silinir.
- Invariant check: yazım sonrası §7 cross-sheet kuralları doğrulanır; başarısızsa backup'tan rollback.
- Schema'dan üretim (ADR-009): `master-excel.schema.json` değişti → regenerate; manuel sheet ekleme yok.
- Cross-link: backup + state geçmişi → rules/append-only-state.md.

## Examples (Doğru)
- `python scripts/excel/transaction.py write --sheet pages --values pages.json` → backup alır, tmp yazar, atomic rename, invariant check.
- Hücre değeri: `"42"` (string) ya da `42` (number) — düz değer.
- Backup: `backups/master-excel-2026-04-30T10-00-00Z.xlsx`; 8. backup geldiğinde en eski silinir.

## Anti-Patterns (Ihlal)
- `=VLOOKUP(A2, sheet2!A:B, 2, 0)` — formül; replay'de aynı sonucu üretmez.
- LibreOffice/Excel ile manuel hücre editi → schema senkronu kopar.
- `transaction.py`'yi bypass eden ad-hoc `openpyxl.save()` çağrısı.
- Backup almadan write; tmp + rename yerine direkt overwrite.

## Enforcement
- CI: `tests/excel/test_no_formulas.py` — tüm hücreleri tarayıp `=` prefix yokluğunu kontrol eder.
- CI: `tests/excel/test_invariants.py` — §7 cross-sheet kuralları.
- Pre-commit hook: `scripts/hooks/check_excel_writer.py` — `master-excel.xlsx` diff'i `transaction.py`'den gelmiyorsa reddeder.
- Manuel review: PR review checklist "Excel write `transaction.py` üzerinden mi? Formül var mı?" maddesi.
