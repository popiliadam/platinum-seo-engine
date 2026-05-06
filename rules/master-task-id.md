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
- drift-check F-XX aday: `master_task.task_id` pattern cross-check (Phase 16+ scope).
