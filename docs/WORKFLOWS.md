# Workflow Catalog (v1 Skills)

> v1 release **~43 skill** kapsar. Bu katalog skill'ler landed olarak güncellenir. Şu anki status: **planned** (Phase 0'da hiçbiri implement edilmedi). Eski sistemden taşınan 28 skill + governance/ingestion/planning eklemeleri toplam ~43.

Skill'ler **batch'ler halinde** (Phase 5–13) inşa edilir; foundation phase'leri (0–4) tamamlandıktan sonra her batch paralel worker'larla yazılır. Sıralı değildir.

---

## Critical Path — Phase 5 (5 skill, GO/NO-GO gateway)

| Skill | Trigger | Status |
|---|---|---|
| `init-project` | "yeni proje", `/pseo-init` | planned |
| `sf-import` | "SF crawl yükle" | planned |
| `quick-wins` | "quick win", `/pseo-quickwin` | planned |
| `drift-check` | "drift kontrol", `/pseo-driftcheck` | planned |
| `whats-next` | "ne yapmalıyım", "bugün" | planned |

> Phase 5 gateway: pilot proje (demo-dental) end-to-end smoke test PASS + events.jsonl tutarlı + drift-check GREEN. Geçemezse foundation'a dön.

---

## Ingestion — Phase 6 (3 skill)

| Skill | Trigger | Status |
|---|---|---|
| `gsc-pull` | "GSC veri çek" | planned |
| `dfs-pull` | "DataForSEO veri çek" | planned |
| `scrapling-ops` | "site scrape" | planned |

> Constraint: §16.5 MCP integration pattern + §16.8 budget disiplini.

---

## Discovery — Phase 7 (8 skill)

| Skill | Trigger | Status |
|---|---|---|
| `cannibalization` | "cannibalization", "yamyamlık" | planned |
| `content-decay` | "content decay", "düşen içerik" | planned |
| `tech-audit` | "tech audit" | planned |
| `on-page-audit` | "on-page audit" | planned |
| `content-gaps` | "content gap" | planned |
| `schema-audit` | "schema audit" | planned |
| `competitive-analysis` | "rakip analizi" | planned |
| `geo-analysis` | "GEO analiz" | planned |

> Not: `aio-competitor-map` discovery doğasında olmasına rağmen Phase 12'de ele alınır.

---

## Planning — Phase 8 (5 skill)

| Skill | Trigger | Status |
|---|---|---|
| `cluster-map` | "cluster map" | planned |
| `topical-map` | "topical map" | planned |
| `new-content-plan` | "yeni içerik planı" | planned |
| `internal-links` | "iç link planı" | planned |
| `master-task-sync` | "task sync" | planned |

---

## Reporting — Phase 9 (8 skill)

| Skill | Trigger | Status |
|---|---|---|
| `monthly-report` | "aylık rapor", `/pseo-monthly` | planned |
| `weekly-summary` | "haftalık özet" | planned |
| `portfolio-overview` | "portföy özet" | planned |
| `portfolio-weekly-brief` | "portföy haftalık" | planned |
| `portfolio-monthly-roundup` | "portföy aylık" | planned |
| `portfolio-task-heatmap` | "task heatmap" | planned |
| `portfolio-kpi-trend` | "kpi trend" | planned |
| `portfolio-heatmap` | "heatmap genel" | planned |

---

## Production — Phase 11 (5 skill)

| Skill | Trigger | Status |
|---|---|---|
| `new-blog` | "yeni blog yaz" | planned |
| `revise-content` | "içerik revize" | planned |
| `generate-images` | "görsel üret" | planned |
| `content-remediation` | "içerik düzeltme" | planned |
| `faq-optimization` | "FAQ optimize" | planned |

> Constraint: Phase 10 content rules çıktılarını (`rules/content-*.md`, `templates/content/*`) consume eder.

---

## Publishing + Specialized — Phase 12 (6 skill)

| Skill | Trigger | Status |
|---|---|---|
| `indexing-ping` | "indexlenmesi" | planned |
| `verify-indexing` | "index kontrol" | planned |
| `aio-competitor-map` | "AIO competitor" | planned |
| `brand-onboarding` | "marka onboard" | planned |
| `mark-done` | "tamamlandı" | planned |
| `monitoring-weekly` | "haftalık izleme" | planned |

---

## Governance Final — Phase 13 (3 skill)

| Skill | Trigger | Status |
|---|---|---|
| `schema-validate` | "schema validate" | planned |
| `glossary-audit` | "glossary kontrol" | planned |
| `load-context` | (hook tetikli) | planned |

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
