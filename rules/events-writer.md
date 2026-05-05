---
name: Events Writer
status: enforced
applies_to: [workspace, skill]
spec_section: "§8.4 + ADR-019 + ADR-020"
related: [append-only-state, schema-first, schema-versioning-discipline]
---

# Events Writer

`workspace/state/events.jsonl` writer kuralları. Event yazımı `next_run_id(project_slug)` helper üzerinden yapılır, `event_kind` 4-enum + `event_type` 10-closed-enum + `workflow_action` 8-enum schema authority'ye uyar. Skill bazlı `event_type` branch matrix worker schema-first override paterni ile resolve edilir.

## Section 1 — Append-Only Invariant (R-XX hard constraint)

`events.jsonl` mutate YASAK (Süleyman global feedback_hard_constraints, append-only-state rule, lesson 47 5'inci kategori "append-only invariant protected drift defer" doğum belgesi).

- Mevcut satır rewrite YASAK (REQUIRED MUST NOT).
- Sadece yeni `\n`-terminated JSON satır append edilir (MUST).
- Hatalı historical entry için corrective event yeni satır olarak eklenir; eski satıra dokunulmaz.
- F-13 historical 5 non-int `run_id` baseline carry append-only protected drift defer paterni — mop-up imkansız, çünkü eski satırı düzeltmek append-only invariant ihlali olur. Yeni event'lerde `run_id` integer ZORUNLU (Section 2).
- Rollback senaryosunda dosya snapshot'tan restore edilir (atomic rename), in-place truncate YASAK.

## Section 2 — `next_run_id(project_slug)` Helper Enforcement (Q-DC-RUNID-01)

Manual events yazılırken `run_id` integer field ZORUNLU. Direct dict construction + `json.dumps` bypass YASAK; `scripts/state/events_writer.py::next_run_id(project_slug)` helper kullanılır.

Kanonik invocation:

```python
from scripts.state.events_writer import next_run_id, append

run_id = next_run_id(project_slug="dentnotion")
event = {
    "run_id": run_id,
    "ts": "2026-05-05T12:00:00Z",
    "event_kind": "work",
    "event_type": "content_new",
    "skill": "new-blog",
    # ... domain fields
}
append(event)  # writes \n-terminated JSON line + flushes
```

- `next_run_id` projenin events.jsonl'ından son `run_id` integer'ı tarar, +1 döner (monotonic).
- Helper bypass edilirse drift-check F-13 ("non-int run_id") flag eder (mevcut historical 5 satır baseline carry).
- Phase 14 W3-W3+ skill bazlı override: 13 production skill `events_writer.append` invoke etmek ZORUNLU; raw `open(events_jsonl, "a")` paterni governance lint reject eder.

## Section 3 — `event_kind` 4-enum (ADR-020)

Schema `events.schema.json` `event_kind` field 4 closed enum:

| event_kind | Anlam |
|---|---|
| `provenance` | Veri ingest/normalize/project_excel/validate/cascade_done lifecycle |
| `work` | Skill execution lifecycle (skill_started, skill_done, skill_failed) |
| `audit` | Read-only access trail (load-context, drift-check, monitoring-weekly) |
| `workflow` | Lifecycle state machine (workflow-run.schema.json reference, started → done) |

Worker schema-first override paterni: schema'da olmayan kind kullanmak YASAK. Yeni kind ekleme schema bump v1.0 → v1.1 ZORUNLU (schema-versioning-discipline cross-ref).

## Section 4 — `event_type` 10-closed-enum + Branch Matrix per Skill (Q-W3W2B-EVENTTYPE-01)

`event_type` 10 closed enum (events.schema.json):

`content_new`, `content_revise`, `content_remove`, `redirect_deployed`, `tech_fix`, `schema_fix`, `pillar_launch`, `quickwin_applied`, `manual`, `audit_run`, `backlink_outreach` (post-v1).

13 production + 8 verify/governance skill için branch matrix:

| Skill | event_type (schema) | event_type_intent (note field) |
|---|---|---|
| new-blog | content_new | (direct) |
| revise-content | content_revise | (direct) |
| faq-optimization | content_revise | faq_optimization |
| content-remediation (improve) | content_revise | content_remediation_improve |
| content-remediation (delete) | content_remove | (direct) |
| content-remediation (redirect) | redirect_deployed | (direct) |
| tech-audit | tech_fix | (direct) |
| on-page-audit | tech_fix | on_page_fix |
| content-gaps | manual | content_gaps |
| schema-audit | schema_fix | (direct) |
| schema-validate | schema_fix | schema_validate |
| competitive-analysis | manual | competitive_analysis |
| geo-analysis | manual | geo_analysis |
| cluster-map | manual | cluster_map |
| topical-map | pillar_launch | topical_map |
| new-content-plan | manual | new_content_plan |
| internal-links | manual | internal_links |
| master-task-sync | manual | master_task_sync |
| mark-done (quickwin) | quickwin_applied | (direct) |
| mark-done (manual) | manual | task_completed |
| backlink-outreach (post-v1) | backlink_outreach | (direct) |
| generate-images | content_new | image_generated |
| verify-indexing | manual | verify_indexing |
| monitoring-weekly | audit_run (`event_kind=audit`) | weekly_monitoring |

Worker schema-first override paterni (Phase 14 W3-W2-B doğum belgesi, 11'inci uygulama):

- Skill spec'inde literal `event_type=skill_name` (örn `event_type=faq_optimization`) talep edilse bile schema'da YOKsa, worker `event_type=manual` + `note=[skill=faq-optimization event_type_intent=faq_optimization]` yazar.
- Direct match olan skill'lerde override gerekmez (örn `new-blog` → `content_new` schema'da var).
- Branch matrix per skill SKILL.md'de codify edilir (skill-spec authority + schema-first override = brief revize 7 madde paterni).

### Cross-Skill Convention Examples

Production new-blog dispatch (NCP-001 P1 T tier 1850 vol):

```json
{"run_id": 47, "ts": "2026-05-05T10:00:00Z", "event_kind": "work", "event_type": "content_new", "skill": "new-blog", "task_id": "T-10001", "url_normalized": "https://dentnotion.com/blog/izmir-implant-tedavisi-fiyatlari-2026", "after": {"pageSnapshot": {"word_count": 4250, "h1_count": 1, "schema_types": ["FAQPage", "Article"]}}}
```

faq-optimization (10 Q&A snippet-friendly) — schema-first override:

```json
{"run_id": 48, "ts": "2026-05-05T11:00:00Z", "event_kind": "work", "event_type": "manual", "skill": "faq-optimization", "task_id": "T-10003", "note": "[skill=faq-optimization event_type_intent=faq_optimization]", "after": {"faq_count": 10}}
```

content-remediation redirect (Q-W3W2Cb-001 in-wave RESOLVED `/main-page` duplicate-canonical):

```json
{"run_id": 49, "ts": "2026-05-05T11:30:00Z", "event_kind": "work", "event_type": "redirect_deployed", "skill": "content-remediation", "url_normalized": "https://dentnotion.com/main-page", "redirect_target": "https://dentnotion.com/", "redirect_status": 301, "reason": "duplicate_via_canonical_GSC_inspect"}
```

monitoring-weekly audit-run (`event_kind=audit`):

```json
{"run_id": 50, "ts": "2026-05-05T12:00:00Z", "event_kind": "audit", "event_type": "audit_run", "skill": "monitoring-weekly", "note": "weekly_monitoring", "metrics_snapshot": {"red_count": 14, "amber_count": 2, "green_count": 4}}
```

## Section 5 — `workflow_action` 8-enum Lifecycle (ADR-019)

`event_kind=workflow` events için `workflow_action` field ZORUNLU. 8 closed enum (workflow-run.schema.json reference):

`started`, `paused`, `resumed`, `approved`, `rejected`, `retried`, `done`, `failed`.

Lifecycle invariant:

- `started` ilk event olmalı (run_id başlangıcı).
- `done` veya `failed` terminal state (sonrası workflow event YASAK aynı run_id için).
- `paused` → `resumed` paterni izinli (Süleyman onay #N geçici durdurmada).
- `retried` agent failure sonrası restart (ModelRetry paterni qa-loop.md cross-ref).
- `approved`/`rejected` Süleyman karar #N event'i (decision_authority cross-ref).
- Geri-geçiş YASAK (`done → started` MUST NOT, append-only-state cross-ref).

Cross-references: → rules/append-only-state.md (mutate YASAK), → rules/schema-first.md (events.schema authority), → rules/schema-versioning-discipline.md (enum bump versioning).
