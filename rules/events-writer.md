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

Kanonik invocation (4 convenience wrapper — schema-aware, envelope auto-populate):

```python
from scripts.state import events_writer

# WORK event (skill execution lifecycle, event_kind=work)
events_writer.append_work(
    project_id="dentnotion",
    event_type="content_new",
    task_id="T-10001",
    actor="agent:new-blog",
    url="https://dentnotion.com/blog/izmir-implant-tedavisi-fiyatlari-2026",
    url_normalized="https://dentnotion.com/blog/izmir-implant-tedavisi-fiyatlari-2026",
    after={"pageSnapshot": {"word_count": 4250, "h1_count": 1}},
    pillar="P1_implant_authority",
)

# PROVENANCE event (data ingestion lifecycle, event_kind=provenance)
events_writer.append_provenance(
    project_id="dentnotion",
    run_id=events_writer.next_run_id("dentnotion"),
    source={"kind": "gsc_mcp", "mcp_server": "gsc"},
    operation="ingest",
)

# AUDIT event (read-only access trail, event_kind=audit)
events_writer.append_audit(
    project_id="dentnotion",
    audit_action="accessed",
    audit_target="reports:monitoring-weekly:2026-05-06_2026-05-13",
    actor="agent:monitoring-weekly",
    notes="weekly_monitoring red=14 amber=2",
)
```

- 4 convenience wrapper (`append_work` / `append_provenance` / `append_audit` / `append_workflow`) schema-aware: top-level envelope (`schema_version` + `event_id` + `timestamp` + `project_id`) auto-populate edilir; per-kind required fields kwargs ile geçirilir; bare `append(event)` API YOK — `append_event(event, project_id)` low-level fallback olarak mevcut (events_writer.py `__all__`).
- `next_run_id(project_id)` helper provenance run sequencing için kullanılır (monotonic +1 dönüş; F-13 baseline carry 5 historical non-int row append-only protected, mop-up YASAK Section 1 invariant).
- Helper bypass edilirse drift-check F-13 ("non-int run_id") flag eder (mevcut historical 5 satır baseline carry).
- Phase 14 W3-W3+ skill bazlı enforce: 23+ skill `events_writer.append_*` convenience wrapper invoke eder; raw `open(events_jsonl, "a")` paterni + direct `json.dumps` bypass governance lint reject eder.

## Section 3 — `event_kind` 4-enum (ADR-020)

Schema `events.schema.json` `event_kind` field 4 closed enum:

| event_kind | Anlam |
|---|---|
| `provenance` | Veri ingest/normalize/project_excel/validate/cascade_done lifecycle |
| `work` | Skill execution lifecycle (skill_started, skill_done, skill_failed) |
| `audit` | Read-only access trail (load-context, drift-check, monitoring-weekly) |
| `workflow` | Lifecycle state machine (workflow-run.schema.json reference, started → done) |

Worker schema-first override paterni: schema'da olmayan kind kullanmak YASAK. Yeni kind ekleme schema bump v1.0 → v1.1 ZORUNLU (schema-versioning-discipline cross-ref).

## Section 4 — `event_kind` × Skill Branch Matrix (3 sub-tables, 100% coverage — Q-V1.2-EVENTS-WRITER-MATRIX-COVERAGE-01 + Q-W3W2B-EVENTTYPE-01)

43/43 mevcut SKILL.md per-skill matrix (filesystem SoT cross-check Phase B Wave 2 2026-05-06; pre-fix coverage 47% = 20/43 brief-true; post-fix 100% = 43/43 filesystem-true). 3 sub-table `event_kind` 4-enum (Section 3) ayrımına göre:

- **Section 4a** — `event_kind=work` events (`event_type` 10-enum, content/task lifecycle)
- **Section 4b** — `event_kind=provenance` events (`operation` 6-enum, data ingestion lifecycle)
- **Section 4c** — `event_kind=audit` events (`audit_action` 6-enum, no `event_type` per Section 6)

### Worker Schema-First Override Paterni (Phase 14 W3-W2-B doğum belgesi, 16'ıncı uygulama Phase B Wave 1 generate-images; v1.6-Phase-2 canonical entries paterni — alternative path)

- Skill spec'inde literal `event_type=skill_name` (örn `event_type=faq_optimization`) talep edilse bile schema'da YOKsa, worker `event_type=manual` + `note=[skill=faq-optimization event_type_intent=faq_optimization]` yazar (legacy DSL workaround paterni).
- **v1.6-Phase-2 H-E canonical entries (2026-05-07):** Schema'da `skill_<name>` canonical entries varsa (currently: `skill_content_remediation`, `skill_whats_next`), worker direct emission yapar — DSL workaround gereksiz. Canonical paterni note alanını yine korur (allOf branch enforce; structured data taşıyıcı).
- Direct match olan skill'lerde override gerekmez (örn `new-blog` → `content_new` schema'da var; ancak URL-context yoksa override).
- URL-bearing work event constraints (events.schema allOf): `content_new`, `content_revise`, `content_remove`, `redirect_deployed`, `tech_fix`, `schema_fix`, `pillar_launch`, `quickwin_applied` → `url + url_normalized` REQUIRED; standalone scope'unda satisfy edilemiyorsa schema-first override `manual + note`.
- Branch matrix per skill SKILL.md'de codify edilir (skill-spec authority + schema-first override = brief revize 7 madde paterni).

### Section 4a — Work Events (event_kind=work, 9 unique base + 4 sub-branches = 13 row)

`event_type` 12 closed enum (events.schema.json — additive bump 2026-05-07 v1.6-Phase-2 H-E ADR-018 paterni; 10 legacy + 2 skill_<name> canonical):

`content_new`, `content_revise`, `content_remove`, `redirect_deployed`, `tech_fix`, `schema_fix`, `pillar_launch`, `quickwin_applied`, `manual`, `backlink_outreach`, `skill_content_remediation`, `skill_whats_next`.

| Skill | event_type (schema) | event_type_intent (note field) | Status / Notes |
|---|---|---|---|
| whats-next | skill_whats_next | (direct) | ✅ Active — canonical event_type v1.6-Phase-2 H-E; synthetic task_id mint paterni |
| generate-images | manual | image_generated | ✅ Active — schema-first override 16 (Phase B W1); content_new URL+pillar yok |
| new-blog | content_new | (direct) | ⏳ Future — + url+url_normalized+after.pageSnapshot+pillar mandatory |
| revise-content | content_revise | (direct) | ⏳ Future — + before+after schema-required |
| faq-optimization | manual | faq_optimization | ⏳ Future — schema-first override (no URL-context) |
| content-remediation (improve) | skill_content_remediation | (direct) | ⏳ Future — canonical event_type v1.6-Phase-2 H-E |
| content-remediation (delete) | content_remove | (direct) | ⏳ Future — + note required |
| content-remediation (redirect) | redirect_deployed | (direct) | ⏳ Future — + url+url_normalized+note required |
| mark-done (quickwin) | quickwin_applied | (direct) | ⏳ Future — + cluster+before+after |
| mark-done (manual) | manual | task_completed | ⏳ Future — + note required |
| indexing-ping | manual | indexing_ping | ⏳ Future — GSC API ping log |
| verify-indexing | manual | verify_indexing | ⏳ Future — GSC inspect log |
| backlink-outreach (post-v1) | backlink_outreach | (direct) | 📋 Placeholder — SKILL.md henüz yok |

### Section 4b — Provenance Events (event_kind=provenance, 20 skill — append_provenance ✅ active)

`operation` 6 closed enum (events.schema.json — ADR-038 Wave 3 additive bump `staging`):

`ingest`, `normalize`, `project_excel`, `validate`, `cascade_done`, `staging`.

| Skill | operation | source.kind | Notes |
|---|---|---|---|
| dfs-pull | ingest, staging | dfs_mcp | DataForSEO raw + Phase 6 D-003 staging routing |
| gsc-pull | ingest | gsc_mcp | GSC search_analytics ingestion |
| scrapling-ops | ingest | scrapling | Stealthy fetch raw inventory |
| sf-import | normalize, project_excel | local_xlsx | Screaming Frog Excel transform |
| init-project | cascade_done | local_template | Project bootstrap cascade close |
| aio-competitor-map | ingest | scrapling | Competitor pages staging (LLM-native) |
| cannibalization | ingest | gsc_mcp | Raw GSC pivot 5000-row query×page |
| competitive-analysis | ingest | scrapling+dfs | Multi-source competitor matrix |
| content-decay | ingest | gsc_mcp | GSC trend regression detection |
| content-gaps | ingest | gsc+dfs | Multi-source gap surfacing |
| geo-analysis | ingest | gsc_mcp | Geo-focused query partition |
| on-page-audit | ingest | scrapling | URL on-page tech fetch |
| quick-wins | ingest, normalize | gsc_mcp | Mixed (raw GSC + opportunity calc) |
| schema-audit | ingest | scrapling | JSON-LD schema markup fetch |
| tech-audit | ingest | scrapling | Tech SEO crawl fetch |
| cluster-map | ingest | local_xlsx | Cluster aggregation |
| internal-links | ingest | local_xlsx | Internal link matrix |
| master-task-sync | ingest | local_xlsx | Task primary_source consolidation |
| new-content-plan | ingest | local_xlsx | Content plan generation |
| topical-map | ingest | local_xlsx | Topical authority map |

### Section 4c — Audit-Only Events (event_kind=audit, 14 skill — `event_type` YASAK Section 6)

`audit_action` 6 closed enum (events.schema.json):

`created`, `modified`, `deleted`, `accessed`, `permission_changed`, `config_changed`.

| Skill | audit_action | audit_target | Status / Notes |
|---|---|---|---|
| drift-check | accessed | `invariants:20` | ✅ Active — Phase 5 audit kind doğum belgesi |
| schema-validate | accessed | `schemas:bulk-validate` | ✅ Active — Phase 13 governance read-only |
| glossary-audit | accessed | `glossary:terms` | ✅ Active — Term drift audit |
| load-context | accessed | `session:wakeup-codify` | ✅ Active — Hook-driven session start |
| monitoring-weekly | accessed | `reports:monitoring-weekly:{week_start}_{week_end}` | ⏳ Phase B Wave 3 inline orchestration adds call |
| brand-onboarding | accessed | `brand:onboarding` | ⏳ Future — One-shot brand scrape audit |
| monthly-report | accessed | `reports:monthly:{period_end}` | 🚧 Q-RP-01 defer (Phase 14+ governance refinement) |
| weekly-summary | accessed | `reports:weekly:{week_end}` | 🚧 Q-RP-01 defer |
| portfolio-overview | accessed | `reports:portfolio-overview:{date}` | 🚧 Q-RP-01 defer |
| portfolio-heatmap | accessed | `reports:portfolio-heatmap:{date}` | 🚧 Q-RP-01 defer |
| portfolio-kpi-trend | accessed | `reports:portfolio-kpi-trend:{date}` | 🚧 Q-RP-01 defer |
| portfolio-monthly-roundup | accessed | `reports:portfolio-monthly-roundup:{date}` | 🚧 Q-RP-01 defer |
| portfolio-task-heatmap | accessed | `reports:portfolio-task-heatmap:{date}` | 🚧 Q-RP-01 defer |
| portfolio-weekly-brief | accessed | `reports:portfolio-weekly-brief:{date}` | 🚧 Q-RP-01 defer |

**Q-RP-01 defer note:** 8 reporting skill (monthly-report, weekly-summary, portfolio-* 6) henüz `events_writer.append_audit` invoke etmiyor — Phase 14+ governance refinement scope. SKILL.md'de "NO `events_writer.append_*` calls anywhere (Q-RP-01 defer)" markered. Audit-event invocation eklenirse 4c row template ready.

### Coverage Audit Summary (post-Phase-B-Wave-2)

| Kategori | Sub-table | Skill count | Active call | Future/Defer |
|---|---|---|---|---|
| Work events | 4a | 9 base + 4 sub | 2 (whats-next + generate-images) | 7 (production+publishing+meta) |
| Provenance events | 4b | 20 | 20 | 0 |
| Audit-only events | 4c | 14 | 4 (governance) | 10 (1 Wave 3 + 1 brand-onboarding + 8 Q-RP-01) |
| **Total** | — | **43** | **26 active** | **17 future** |

Coverage 47% → 100% (43/43 SKILL.md mapped per filesystem SoT).

### Cross-Skill Convention Examples

Production new-blog dispatch (NCP-001 P1 T tier 1850 vol):

```json
{"run_id": 47, "timestamp": "2026-05-05T10:00:00Z", "event_kind": "work", "event_type": "content_new", "task_id": "T-10001", "project_id": "dentnotion", "actor": "agent:new-blog", "url": "https://dentnotion.com/blog/izmir-implant-tedavisi-fiyatlari-2026", "url_normalized": "https://dentnotion.com/blog/izmir-implant-tedavisi-fiyatlari-2026", "pillar": "P1_implant_authority", "after": {"pageSnapshot": {"word_count": 4250, "h1_count": 1, "schema_types": ["FAQPage", "Article"]}}}
```

faq-optimization (10 Q&A snippet-friendly) — schema-first override 4a paterni:

```json
{"timestamp": "2026-05-05T11:00:00Z", "event_kind": "work", "event_type": "manual", "task_id": "T-10003", "project_id": "dentnotion", "actor": "agent:faq-optimization", "note": "[skill=faq-optimization event_type_intent=faq_optimization faq_count=10]"}
```

content-remediation redirect (Q-W3W2Cb-001 in-wave RESOLVED `/main-page` duplicate-canonical):

```json
{"timestamp": "2026-05-05T11:30:00Z", "event_kind": "work", "event_type": "redirect_deployed", "task_id": "T-10005", "project_id": "dentnotion", "actor": "agent:content-remediation", "url": "https://dentnotion.com/main-page", "url_normalized": "https://dentnotion.com/main-page", "note": "duplicate_via_canonical_GSC_inspect; redirect_target=https://dentnotion.com/ status=301"}
```

monitoring-weekly audit-run (Section 4c paterni — `event_type` field YASAK):

```json
{"timestamp": "2026-05-05T12:00:00Z", "event_kind": "audit", "audit_action": "accessed", "audit_target": "reports:monitoring-weekly:2026-04-29_2026-05-05", "actor": "agent:monitoring-weekly", "project_id": "dentnotion", "notes": "weekly_monitoring red=14 amber=2 green=4"}
```

dfs-pull provenance-staging (Section 4b paterni — operation `staging` ADR-038):

```json
{"run_id": 12, "timestamp": "2026-05-05T08:30:00Z", "event_kind": "provenance", "operation": "staging", "project_id": "dentnotion", "source": {"kind": "dfs_mcp", "mcp_server": "dataforseo", "mcp_tool": "keywords_data_google_ads_search_volume"}, "rows_written": 142}
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

## Section 6 — `event_kind=audit` vs `event_type` Disambiguation (Q-PHASE15-EVENTSCHEMA-AUDIT-BRIEF-01)

`event_kind=audit` events (read-only access trail) MUST NOT carry `event_type` field per ADR-020. `event_type` sadece `event_kind=work` events için geçerlidir (skill execution output). `audit_run` bir `event_type` değeri DEĞİLDİR — events.schema `event_type` enum'unda bulunmaz.

- `event_kind=audit` → `event_type` field YASAK (validation'da ignore edilmez, schema violation).
- `event_kind=work` → `event_type` field ZORUNLU (10-closed-enum, Section 4 branch matrix).
- Brief template: audit event cross-check "audit_run in event_type?" sorusu YANLIŞ soru. Doğru soru: "audit event'te event_type var mı?" (OLMAMALI).

Doğru audit event:
```json
{"run_id": 50, "event_kind": "audit", "skill": "monitoring-weekly", "note": "weekly_monitoring"}
```

Yanlış (YASAK):
```json
{"event_kind": "audit", "event_type": "audit_run", ...}
```
