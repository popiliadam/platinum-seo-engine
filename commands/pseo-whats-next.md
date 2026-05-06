---
description: |
  Use when: kullanıcı "ne yapayım", "şimdi ne", "next step", "öncelikli işler", "what to work on", "where do I start", "öncelik sırası", "pending approval", "bekleyen onay" der ya da `/pseo-whats-next` çağırırsa.
  Also use when: yeni session açılışı sonrası agenda tetikleyicisi (SessionStart hook); multiple workflow paralel `awaiting_approval` halinde manager karar vermesi gerekir; multiple project portföy taranıp en acil iş seçilecek.
  Do not use when: spesifik skill çağrısı gerekiyorsa (`/pseo-quickwin`, `/pseo-monthly`, `/pseo-new-blog`, vs); whats-next ROUTER skill, başka skill'leri SUGGEST eder, çağırmaz; advisory-only.
argument-hint: "[project-slug] [--user-intent 'natural language metin'] [--top-k N]"
allowed-tools: Bash(jq:*), Bash(python3:*), Read
model: sonnet
---

# /pseo-whats-next — Meta Routing ("Sıradaki Ne?")

> **Skill:** `skills/meta/whats-next/SKILL.md` (Phase 5 W2, aktif, router pattern). 4 sinyal kaynak (`master_task` TODO + `content_decay` HIGH + `_state/workflows/* awaiting_approval` + `quick_wins` pending) → fixed heuristic skor → Top-K ranked recommendation list. Advisory-only — invoke etmez, SUGGEST eder.

## 1. Aktif projeyi çöz

`$1` opsiyonel; verilmezse tüm `projects/*` taranır (multi-project portfolio mode).

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "scope=all_projects (no \$1, no shared/active.json)"; else echo "scope=single project=$PROJECT"; fi; fi`

## 2. Skill chain

`skills/meta/whats-next/SKILL.md` 10-step routing protokol koşar:

1. workflow runs scan (`_state/workflows/*.json` `status=awaiting_approval`)
2. master_task TODO satır scan (priority sorting: HIGH > MEDIUM > LOW)
3. recent events scan (events.jsonl son 7 gün)
4. content_decay HIGH severity scan
5. quick_wins pending approval scan
6. Recommendation scoring fixed heuristic (top-K ranked, default 3)
7. events.jsonl append: `event_kind=work + event_type=manual + task_id=T-XXXXX synthetic mint + note=markdown bullet ranking list`
8. Output: structured ranking markdown (top-K recommendation per skill name + invocation hint)

Synthetic task_id mint paterni: `T-{90000 + (int(hashlib.sha1(run_id).hexdigest()[:4], 16) % 9999)}` (events.schema work branch task_id pattern compliance).

## 3. Çalıştırma notları

- ROUTER skill = başka skill çağırmaz, sadece SUGGEST eder. Manager veya kullanıcı recommendation'dan birini seçer.
- `--user-intent "metin"` verilirse ranking'e bias eklenir (örn "schema gerek" → schema-audit upbias).
- `--top-k N` (default 3, runtime 1..10 enforced) recommendation sayısını cap'ler.
- Multi-project mode (no `$1`): `projects/*/master.xlsx` cross-portfolio aggregate, en acil top-K döner.
- `requires_approval: false`, `safe_auto_execute: false` (advisory-only, MEDIUM confidence).

## 4. Bağımlılıklar

- Skill: `skills/meta/whats-next/SKILL.md` (Phase 5 W2, active, router pattern)
- Scripts: `scripts/state/events_writer.py` (`append_work` synthetic task_id) + `scripts/state/workflow_runner.py` (workflow run state read)
- Schemas: `schemas/events.schema.json` (work if/then required: event_type + task_id; manual event_type → note required) + `schemas/workflow-run.schema.json` (run_id pattern)
- Upstream: `init-project` (master.xlsx) + `quick-wins` (master.xlsx#quick_wins)
- MCP: yok (pure local routing logic)
