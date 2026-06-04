# Workflow Catalog (v1 Skills)

> v1.8.0 release **45 skill** — tüm skill'ler implement edildi ve production-ready (Phase 5–13 baseline 43 + v1.7 gbp-audit + v1.8 sf-crawl-orchestrator). Status: **active** (2026-05-27).

> **SF MCP call shapes — canonical contract (P3-01).** The inline `mcp__sf__*`
> tool-call shapes in the SF crawl flow below are illustrative and have evolved.
> The authoritative SF MCP contract is `commands/pseo-sf-crawl.md` + the
> `sf-crawl-orchestrator` SKILL (`skills/ingestion/sf-crawl-orchestrator/SKILL.md`).
> The rest of this catalog reflects the active v1.8.0 skill set.

Phase 5–13 boyunca parallel worker batch'lerle inşa edildi; pilot dentnotion E2E PASS.

---

## Critical Path — Phase 5 (5 skill, GO/NO-GO gateway)

| Skill | Trigger | Status |
|---|---|---|
| `init-project` | "yeni proje", `/pseo-init` | active |
| `sf-import` | "SF crawl yükle" | active |
| `quick-wins` | "quick win", `/pseo-quickwin` | active |
| `drift-check` | "drift kontrol", `/pseo-driftcheck` | active |
| `whats-next` | "ne yapmalıyım", "bugün" | active |

> Phase 5 gateway: pilot proje (dentnotion) end-to-end smoke test PASS + events.jsonl tutarlı + drift-check GREEN. Geçemezse foundation'a dön.

---

## Ingestion — Phase 6 + v1.8 SF MCP (4 skill)

| Skill | Trigger | Status |
|---|---|---|
| `gsc-pull` | "GSC veri çek" | active |
| `dfs-pull` | "DataForSEO veri çek" | active |
| `scrapling-ops` | "site scrape" | active |
| `sf-crawl-orchestrator` (v1.8 NEW) | "SF crawl", `/pseo-sf-crawl` | active |

> Constraint: §16.5 MCP integration pattern + §16.8 budget disiplini. SF orchestrator MCP-primary (v1.8+); file-drop fallback never deprecated per D-SF-07.

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
| Ingestion | 4 | 6 + v1.8 SF MCP |
| Discovery | 9 | 7 (+gbp-audit v1.7) |
| Planning | 5 | 8 |
| Reporting | 8 | 9 |
| Production | 5 | 11 |
| Publishing + Specialized | 6 | 12 |
| Governance Final | 3 | 13 |
| **Toplam** | **45** | **8 batch** |

> Pattern: tüm skill'ler frontmatter `skill-frontmatter.schema.json`'a uyar; multi-step'lerde `workflow-run.schema.json` state'i tutulur; Excel write `transaction.py` üzerinden; MCP çağrıları §16.5 pattern'ine uyar; her aktivite `events.jsonl`'e log düşer.

---

## SF crawl via MCP (v1.8 NEW)

Operator-triggered Screaming Frog crawl via native MCP server (HTTP `http://127.0.0.1:11435/mcp`). MCP-primary ingestion path per v2.2 spec pivot.

### Sequence

```
operator: /pseo-sf-crawl <slug> <url>
    ↓
sf-crawl-orchestrator skill
    ↓ Step 1: Pre-flight (DURUR-orch-1/2/4/7)
        ├ MCP /health probe
        ├ Modal dialog absence (D-SF-10)
        ├ allowed_directory match (F-15)
        └ Concurrent-crawl guard via sf_list_crawls (R13)
    ↓ Step 2: workflow_runner.create_run + envelope write
        └ inbox/sf-mcp/{date}-sf-crawl-{slug}.json
    ↓ Step 3: mcp__sf__sf_crawl(start_url) → crawl_id
    ↓ Step 4: Poll mcp__sf__sf_crawl_progress(crawl_id)
        └ max_wait_minutes default 180 (Q-SF-MCP-03)
    ↓ Step 5: 24-report iterate (Tier 1: 14 mandatory + Tier 2: 10 AMBER-tolerant)
        ├ mcp__sf__sf_generate_report(report_name, export_type="CSV", file_path=…)
        ├ Atomic move to temp_staging/_state/staging/sf-crawl-{run_id}/
        └ DURUR-orch-8: Tier 1 fail → rm -rf temp_staging + SystemExit(8)
    ↓ Step 6: Atomic mv temp_staging → projects/{slug}/sf-exports/{date}/raw/
    ↓ Step 7: sf-import handoff (source_run_id=run_id)
        └ sf-import 8-step protocol UNCHANGED (D-SF-07)
    ↓ Step 8: workflow_runner.complete + events.jsonl (source.kind=sf_mcp)
```

### Resume mid-loop (workflow_runner.pause/resume)

If SF MCP crashes after report #17:

```
1. orchestrator: workflow_runner.pause(reason="sf_mcp_unavailable")
2. temp_staging preserved (17/24 CSVs intact)
3. operator restarts SF GUI + MCP Server
4. operator: /pseo-sf-crawl <slug> --resume <run_id>
5. workflow_runner.resume(run_id) → state=running, paused_at preserved
6. Loop skips existing CSVs, continues from #18
```

### Migration 0005 operator walkthrough

For projects created before v1.8 (schema_version=1.4):

```bash
# Dry-run first (no writes)
python3 scripts/migrations/migration_0005_project_config_1_4_to_1_5.py --project vento --dry-run

# Inspect output; if OK, apply (creates .bak backup):
python3 scripts/migrations/migration_0005_project_config_1_4_to_1_5.py --project vento

# Idempotent: re-running on already-1.5 docs is no-op
```

Migration populates `sf.mcp.{enabled=false, url=http://127.0.0.1:11435/mcp, allowed_directory=/Users/apple/seo_spider_mcp_server, max_wait_minutes=180, per_report_timeout_seconds=300}` defaults. Operator can override per-project (D-SF-18 path parameterization). New projects (`/pseo-init --schema-version=1.5` from v1.8+) auto-cascade Migration 0005 via init-project Step 4.5.
