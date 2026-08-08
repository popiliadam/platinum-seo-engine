---
name: Master Task ID Convention
status: enforced
applies_to: [workspace, skill]
spec_section: "§8.2 + master-excel.schema"
related: [schema-first, events-writer]
---

# Master Task ID Convention (Q-W3W2Cb-003)

`master_task` sheet `task_id` field pattern: `^T-[0-9]{4,}$`

## Canonical Pattern

```
T-10001
T-10002
T-10003
```

`events.schema.json` `mark-done` step `task_id` field aynı regex'i bekler.

## Legacy Pattern (Transitional — Pre-Phase 14 W3-W2-B)

Phase 14 W3-W2-B sırasında `MT-W3W2B-001` formatında task_id'ler oluşturuldu. Bunlar append-only invariant nedeniyle retroaktif düzeltilemez. Yeni task'lar `T-NNNNN` formatını kullanır.

## Enforcement

- Yeni task yazarken `mark-done` skill Step 1'de `^T-[0-9]{4,}$` doğrulama ZORUNLU.
- `master-excel.schema.json` `master_task.task_id` field pattern reference: `#/definitions/taskIdPattern`.
- events.jsonl `task_id` field'ı canonical pattern ile yazılır; legacy ID'ler historical olarak kabul edilir.
- `master_task.task_id` pattern cross-check: **uygulandı** —
  `tests/state/test_master_task_id_convention.py` (workspace bağlıyken koşar;
  bağlı değilken kapsamanın SIFIR olduğunu uyarı ile söyler, sessizce geçmez).

## Ölçülen drift — 2026-08-08

Bu kural `status: enforced` diyordu ama yukarıdaki satır "Phase 16+ scope"
olarak duruyordu, yani kimse bakmıyordu. Bağlı workspace tarandığında
**3677 task içinde 125 uyumsuz kimlik** bulundu, altı projede, altı ayrı
şekilde:

| proje | adet | şekil |
|---|---:|---|
| dentnotion | 64 | `T-301-01`, `T-PIL-PEK-01`, `MT-FIYAT-NN` (19'u) |
| bayder | 54 | `MT-NNN` |
| bigcat-tr | 5 | `QW-NNN` |
| katrenur-tr | 1 | `T-0026-V` |
| rkturizm-tr | 1 | `T-PIVOT-15G` |

Bunlar **temizlenmedi**. Yeniden adlandırmak, arşivlenmiş `events.jsonl`
satırlarında ve `completed_work` kayıtlarında askıda referans bırakır; o
defterler append-only olduğu için yerinde onarılamaz. Karar sahibinin.

Kontrol bu yüzden bir **cırcır (ratchet)**: mevcut borç proje başına sayı
olarak sabitlendi; sayı BÜYÜRSE kapı kırmızıya gider. Küçülürse de kırmızıya
gider — pin bilerek, düzeltmeyle birlikte indirilsin diye. Şemayı diskteki
şekilleri kabul edecek biçimde genişletmek değerlendirildi ve **reddedildi**:
o, yeşile ulaşmak için kapıyı gevşetmek ve ad-hoc kimlik uydurmayı
konvansiyon ilan etmek olurdu.
