# Workflow Catalog (v1 Skills)

> v1.0.0 release **43 skill** — tüm skill'ler implement edildi ve production-ready (Phase 5–13). Status: **active** (2026-05-05).

Phase 5–13 boyunca parallel worker batch'lerle inşa edildi; pilot demo-dental E2E PASS.

---

## Critical Path — Phase 5 (5 skill, GO/NO-GO gateway)

| Skill | Trigger | Status |
|---|---|---|
| `init-project` | "yeni proje", `/pseo-init` | active |
| `sf-import` | "SF crawl yükle" | active |
| `quick-wins` | "quick win", `/pseo-quickwin` | active |
| `drift-check` | "drift kontrol", `/pseo-driftcheck` | active |
| `whats-next` | "ne yapmalıyım", "bugün" | active |

> Phase 5 gateway: pilot proje (demo-dental) end-to-end smoke test PASS + events.jsonl tutarlı + drift-check GREEN. Geçemezse foundation'a dön.

---

## Ingestion — Phase 6 (3 skill)

| Skill | Trigger | Status |
|---|---|---|
| `gsc-pull` | "GSC veri çek" | active |
| `dfs-pull` | "DataForSEO veri çek" | active |
| `scrapling-ops` | "site scrape" | active |

> Constraint: §16.5 MCP integration pattern + §16.8 budget disiplini.

---

## Discovery — Phase 7 (8 skill)

| Skill | Trigger | Status |
|---|---|---|
| `cannibalization` | "cannibalization", "yamyamlık" | active |
| `content-decay` | "content decay", "düşen içerik" | active |
| `tech-audit` | "tech audit" | active |
| `on-page-audit` | "on-page audit" | active |
| `content-gaps` | "content gap" | active |
| `schema-audit` | "schema audit" | active |
| `competitive-analysis` | "rakip analizi" | active |
| `geo-analysis` | "GEO analiz" | active |

> Not: `aio-competitor-map` discovery doğasında olmasına rağmen Phase 12'de ele alınır.

---

## Planning — Phase 8 (5 skill)

| Skill | Trigger | Status |
|---|---|---|
| `cluster-map` | "cluster map" | active |
| `topical-map` | "topical map" | active |
| `new-content-plan` | "yeni içerik planı" | active |
| `internal-links` | "iç link planı" | active |
| `master-task-sync` | "task sync" | active |

---

## Reporting — Phase 9 (8 skill)

| Skill | Trigger | Status |
|---|---|---|
| `monthly-report` | "aylık rapor", `/pseo-monthly` | active |
| `weekly-summary` | "haftalık özet" | active |
| `portfolio-overview` | "portföy özet" | active |
| `portfolio-weekly-brief` | "portföy haftalık" | active |
| `portfolio-monthly-roundup` | "portföy aylık" | active |
| `portfolio-task-heatmap` | "task heatmap" | active |
| `portfolio-kpi-trend` | "kpi trend" | active |
| `portfolio-heatmap` | "heatmap genel" | active |

---

## Production — Phase 11 (5 skill)

| Skill | Trigger | Status |
|---|---|---|
| `new-blog` | "yeni blog yaz" | active |
| `revise-content` | "içerik revize" | active |
| `generate-images` | "görsel üret" | active |
| `content-remediation` | "içerik düzeltme" | active |
| `faq-optimization` | "FAQ optimize" | active |

> Constraint: Phase 10 content rules çıktılarını (`rules/content-*.md`, `templates/content/*`) consume eder.

---

## Publishing + Specialized — Phase 12 (6 skill)

| Skill | Trigger | Status |
|---|---|---|
| `indexing-ping` | "indexlenmesi" | active |
| `verify-indexing` | "index kontrol" | active |
| `aio-competitor-map` | "AIO competitor" | active |
| `brand-onboarding` | "marka onboard" | active |
| `mark-done` | "tamamlandı" | active |
| `monitoring-weekly` | "haftalık izleme" | active |

---

## Governance Final — Phase 13 (3 skill)

| Skill | Trigger | Status |
|---|---|---|
| `schema-validate` | "schema validate" | active |
| `glossary-audit` | "glossary kontrol" | active |
| `load-context` | (hook tetikli) | active |

> CI pipeline'da bu üç skill'in karşılığı tek komutla koşturulur (drift-check + schema-validate + glossary-audit zinciri).

---

## Toplam

| Kategori | Skill Sayısı | Phase |
|---|---|---|
| Critical Path | 5 | 5 |
| Ingestion | 3 | 6 |
| Discovery | 8 | 7 |
| Planning | 5 | 8 |
| Reporting | 8 | 9 |
| Production | 5 | 11 |
| Publishing + Specialized | 6 | 12 |
| Governance Final | 3 | 13 |
| **Toplam** | **43** | **8 batch** |

> Pattern: tüm skill'ler frontmatter `skill-frontmatter.schema.json`'a uyar; multi-step'lerde `workflow-run.schema.json` state'i tutulur; Excel write `transaction.py` üzerinden; MCP çağrıları §16.5 pattern'ine uyar; her aktivite `events.jsonl`'e log düşer.
