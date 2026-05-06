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

## Drift Resolution Pattern — F-13 Emsali (v1.1 Wave 1, ADR-031)

Geçmiş state satırları schema drift gösterdiğinde (eski yazımdan kalmış
type/field uyumsuzlukları), in-place "repair migration" YASAK — append-only
disiplinini ihlal eder. Doğru resolution: **strict CI gate + legacy archive
split**.

**Emsali (F-13 case):** Workspace dentnotion `events.jsonl` 5 provenance
satırı `run_id` alanını string olarak taşıyordu (schema integer require
ediyor). `events.schema.json` strict CI gate Wave 1'de aktif olunca legacy
satırlar `events.jsonl.legacy` (READ-ONLY archive) dosyasına partition
edildi (`scripts/state/migrate_legacy_events.py`, ADR-031). Sonuç:
`events.jsonl` strict-PASS (F-13 verdict RED → PASS), legacy data WORM-style
korunur (audit trail bütün), F-13 mekanik gürültü temizlendi.

**Migration-in-place YANLIŞ olurdu çünkü:** (a) string→int cast geçmiş
event'in semantiğini değiştirir; (b) git history'de "düzeltme" diff
görünür (append-only ihlal); (c) replay/debug için orijinal yazım
kaybolur.

**Future drift uygulama:** Aynı paterni reuse et — strict schema gate +
legacy archive partition + audit trail report. Migration script yazma
gereksinimi YOK; archive script idempotent olmalı; archive dosyası
read-only (yazıcılar dokunmaz, okuyucular ek context için inceleyebilir).

Wave 2 closeout (2026-05-06): F-13 PASS doğrulandı (Wave 1 archive sonrası
22/22 provenance integer run_id). ADR-036 yazma gereksinimi yok — bu
emsal pattern dokümantasyonu yeterli (Q-WAVE1-DRIFT-DEFER-01 partial
RESOLVED).
