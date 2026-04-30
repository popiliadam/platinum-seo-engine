---
name: Append-Only State
status: enforced
applies_to: [workspace]
spec_section: "§8.4"
---

# Append-Only State

## Kural
`events.jsonl` ve `workflows/{run_id}.json` dosyaları silinmemeli, üzerine yazılmamalı, geçmiş entry'ler mutate EDİLMEMELİDİR (MUST NOT). Sadece yeni entry append edilebilir veya yeni dosya oluşturulabilir (MUST). Workflow run state için izinli tek değişim, henüz çalışmamış adımın `status` alanının ileri-geçişidir (örn: `pending → running → done`); önceki adım entry'sine dokunulmaz (REQUIRED).

## Why
Audit trail ve replay'in tek temeli, geçmişin değiştirilemez olmasıdır. Bir satırı "düzeltmek" tarihçeyi ortadan kaldırır: sistemin gerçekte ne yaptığı bilinemez, debug imkânsızlaşır, drift kanıtı silinir. ADR-013'ün `updated_at` zorunluluğu da bu disiplinin yansımasıdır — değişimler eski kaydı silmez, yenisini ekler.

## How to Apply
- `events.jsonl`: yeni satır `\n` ile append edilir; mevcut satırlar asla rewrite edilmez.
- `workflows/{run_id}.json`: `steps[]` dizisi büyür ya da `steps[i].status` ileri-geçer; önceki step entry'sinin diğer alanları korunur.
- Veri "düzeltme" gereksinimi → düzeltici (compensating) yeni event ekle; eskisini değiştirme.
- Backup zorunlu yazım öncesi (→ rules/excel-discipline.md): değişiklikten önce snapshot al, atomic rename ile yaz.
- Dosya silme/rotate yalnızca arşivleme amaçlı, asla in-place truncate ile değil.
- Status flip izinli geçişler: workflow-run schema `status` enum'ı; geri-geçiş yasak (`done → running` MUST NOT).

## Examples (Doğru)
- Yanlış event yazıldı → düzeltme: yeni `event_corrected` entry append, eski entry yerinde durur.
- Step tamamlandı: `workflows/init-project-2026-04-30-a1b2.json` içinde `steps[2].status: "running" → "done"`; `steps[0..1]` aynen kalır.

## Anti-Patterns (Ihlal)
- `sed -i` veya editor ile `events.jsonl` satırı değiştirmek.
- Workflow run JSON'unu baştan yeniden yazmak ("temizlik" amacıyla).
- `done` durumundaki step'i `running`'e geri çekmek.
- Hatalı satırı silmek; doğrusu: corrective event eklemek.

## Enforcement
- CI: `tests/state/test_jsonl_append_only.py` — git history'de `events.jsonl` diff'i sadece append olmalı.
- Pre-commit hook: `scripts/hooks/check_append_only.sh` jsonl dosyalarında non-append diff'i reddeder.
- Manuel review: PR review checklist "Geçmiş state mutate edildi mi?" maddesi.
- Cross-link: → rules/excel-discipline.md (atomic write + backup).
