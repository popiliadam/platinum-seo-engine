# Platinum SEO Engine — Architecture & Design Spec

**Tarih:** 2026-04-30
**Durum:** Onaylandı, fresh session inşaatı başlatabilir
**Yazar:** Brainstorming session (manager — Opus 4.7 1M)
**Hedef Okur:** Fresh manager session (yeni Claude Code conversation)

---

## 0. Bu Doküman Nasıl Okunur

**Fresh session açıldığında ZORUNLU okuma sırası:**
1. §1 (Vision) — niye varız
2. §13 (Manager Session Protocol) — nasıl çalışırız
3. §17 (Phase Roadmap) — sırada ne var
4. **DUR.** Geri kalanı **ihtiyaç duyduğunda** oku, baştan değil.

**Geri kalan bölümler referans niteliğinde**, sadece ilgili phase'e geçerken okunur:
- §3-§4: Phase 1'de gerekli
- §5-§7: Phase 2-5'te gerekli (excel + sf-import workflow'ları)
- §8-§10: her phase'de geçerli (disiplinler)
- §11: Tüm v1 skill kataloğu (~43 skill, batch'lere bölünmüş)
- §15: Phase 1+'da eski repolardan taşıma yapılırken
- §16.5-16.8: Phase 5+'da MCP entegrasyonu için (Sheet ↔ MCP mapping, integration pattern, cost guardrails)
- §23: Content rules input doc (Phase 10 için ZORUNLU okuma)

Bu doküman **statik referans**. Canlı state için `docs/PHASE_STATUS.md` ve `docs/DECISIONS.md` kullanılır.

---

## 1. Vision

**Ne inşa ediyoruz:** SEO operasyonunu VS Code + Claude Code üzerinden yöneten bir **Plugin sistemi** (`platinum-seo-engine`) ve onunla çalışan bir **veri/state workspace'i** (`platinum-seo-workspace`).

**Niye:** Mevcut `platinum-seo-core` (Python paketi + MCP server + state machine + 110 test) ve `platinum-premium-seo` (ARCHITECTURE-v4 ile 4. tasarım iterasyonu) **drift, duplikasyon ve ucu açıklık** üretiyor. Sebep mimaride **fazla kod**, fazla katman, fazla otorite. Çözüm: **az kod + sıkı kural + tek otorite + makine-okunur sözleşmeler**.

**Vision Tek Cümle:** "Bir Claude Code plugin'i; skills/commands/hooks ile orkestre edilen, JSON schema'larla kilitli, markdown ile insan-okunur, Excel + JSONL ile state tutan, her workflow'u resume/retry/approval gate'leriyle yöneten, kendini drift-check ile denetleyen, proje-agnostik bir SEO motoru."

---

## 2. İki Repo Stratejisi

### 2.1 `platinum-seo-engine` (Plugin Repo)
- **Tek sorumluluk:** Logic, kurallar, aletler. Proje-agnostik.
- **İçerir:** skills, commands, hooks, scripts (küçük Python helpers), schemas, BOŞ templates, rules, docs, tests.
- **İçermez:** Proje isimleri ("{slug}"), proje verisi, state, output.
- **Versionlama:** SemVer. `plugin.json` içinde version.

### 2.2 `platinum-seo-workspace` (Veri/State/Output Workspace)
- **Tek sorumluluk:** Proje verisi, state, output, raw data.
- **İçerir:** projects/{slug}/, shared/, _archive/, .claude/, .env.
- **İçermez:** Logic. Hiçbir Python kodu, hiçbir skill markdown'ı.
- **Versionlama:** Plugin versiyonuyla uyumluluk; her proje config'i `plugin_version_constraint` taşır.

### 2.3 İki Repo Arası Sözleşme
- Plugin **workspace yapısını okur**, **workspace state'ini günceller**.
- Workspace plugin'in varlığından **haberdar değildir** (config dışında).
- Plugin yolu workspace'e **CWD detection** + `.env`'deki `PSE_WORKSPACE_PATH` ile bilinir.

---

## 3. Plugin Repo Tam Yapı

```
platinum-seo-engine/
├── .claude-plugin/
│   └── plugin.json                      # manifest, name, version, description
│
├── skills/                              # doğal dil tetikli yetenekler
│   ├── discovery/                       # mevcut state'i gözlem
│   │   ├── quick-wins/SKILL.md          # v1
│   │   ├── cannibalization/SKILL.md     # v1.1
│   │   ├── tech-audit/SKILL.md          # v1.1
│   │   ├── content-decay/SKILL.md       # v1.1
│   │   ├── cluster-map/SKILL.md         # v1.2
│   │   └── content-gaps/SKILL.md        # v1.2
│   ├── planning/                        # üretim planı
│   │   ├── new-content-plan/SKILL.md    # v1.2
│   │   ├── internal-links/SKILL.md      # v1.2
│   │   └── topical-map/SKILL.md         # v1.2
│   ├── production/                      # içerik üretimi
│   │   ├── new-blog/SKILL.md            # v1.3
│   │   ├── revise-content/SKILL.md      # v1.3
│   │   └── generate-images/SKILL.md     # v1.3
│   ├── publishing/                      # yayın
│   │   ├── indexing-ping/SKILL.md       # v1.3
│   │   └── verify-indexing/SKILL.md     # v1.3
│   ├── reporting/                       # rapor
│   │   ├── monthly-report/SKILL.md      # v1.1
│   │   ├── weekly-summary/SKILL.md      # v1.2
│   │   └── portfolio-heatmap/SKILL.md   # v1.2
│   ├── governance/                      # denetim
│   │   ├── drift-check/SKILL.md         # v1
│   │   ├── schema-validate/SKILL.md     # v1
│   │   └── glossary-audit/SKILL.md      # v1.1
│   ├── ingestion/                       # veri alma
│   │   ├── sf-import/SKILL.md           # v1
│   │   ├── gsc-pull/SKILL.md            # v1.1
│   │   └── dfs-pull/SKILL.md            # v1.2
│   └── meta/                            # sistem
│       ├── init-project/SKILL.md        # v1
│       ├── load-context/SKILL.md        # v1
│       └── whats-next/SKILL.md          # v1 — router
│
├── commands/                            # /slash komutları
│   ├── pseo-status.md                   # mevcut durum gösterimi
│   ├── pseo-init.md                     # init-project shortcut
│   ├── pseo-quickwin.md
│   ├── pseo-monthly.md
│   ├── pseo-driftcheck.md
│   └── pseo-active.md                   # aktif proje set et
│
├── hooks/
│   ├── session-start.json               # context yükle
│   ├── pre-tool-use.json                # excel write öncesi validate
│   ├── post-tool-use.json               # events.jsonl'e log
│   └── user-prompt-submit.json          # drift uyarısı + proje context
│
├── scripts/                             # küçük Python helpers
│   ├── excel/
│   │   ├── transaction.py               # ACID excel write (lock + temp + rename)
│   │   ├── sheet_resolver.py            # logical name → physical sheet
│   │   ├── validate_master.py           # schema + invariant check
│   │   ├── bootstrap_excel.py           # 18 sheet'lik boş excel üret
│   │   └── backup.py                    # rotating backup (last 7)
│   ├── ingestion/
│   │   ├── sf_loader.py                 # SF folder → staging → master.xlsx
│   │   ├── gsc_loader.py
│   │   └── dfs_loader.py
│   ├── state/
│   │   ├── append_event.py              # events.jsonl'e tek satır ekleme
│   │   ├── workflow_runner.py           # multi-step skill state takibi
│   │   └── resume.py                    # paused workflow'u resume et
│   ├── validation/
│   │   ├── validate_schema.py           # JSON schema doğrulama
│   │   ├── validate_invariants.py       # 20 cross-sheet rule
│   │   └── drift_report.py              # tam drift raporu
│   ├── reporting/
│   │   └── render_template.py           # jinja-style markdown render
│   ├── migrations/                      # schema bump migrations
│   │   └── README.md                    # migration discipline
│   ├── budget/
│   │   └── check_budget.py              # paralı MCP çağrılarından önce
│   └── security/
│       └── check_secrets.sh             # eski check-secrets.sh
│
├── schemas/                             # JSON Schema — TEK OTORITE
│   ├── master-excel.schema.json         # 18 sheet'in tam yapısı (eskiden taşınır)
│   ├── cross-sheet-invariants.json      # 20 governance kuralı (eskiden taşınır)
│   ├── project-config.schema.json       # proje config (eskiden taşınır)
│   ├── project-memory.schema.json       # memory.md frontmatter (yeni yazılır)
│   ├── sf-required-reports.schema.json  # 40 SF raporu, 3 tier (eskiden taşınır)
│   ├── sf-export-mapping.schema.json    # SF dosya isim normalizasyonu
│   ├── events.schema.json               # events.jsonl tipleri
│   ├── workflow-run.schema.json         # workflow run state (yeni — §10)
│   ├── skill-frontmatter.schema.json    # skill description disiplini (yeni — §9)
│   ├── monthly-report.schema.json
│   ├── consistency-report.schema.json   # drift raporu formatı
│   ├── mcp-tool-registry.schema.json
│   ├── dataforseo-endpoint-mapping.schema.json
│   ├── gsc-tool-mapping.schema.json
│   ├── scrapling-output-mapping.schema.json
│   ├── excel-config.schema.json
│   ├── excel-source-manifest.schema.json
│   ├── staging-to-excel-map.schema.json
│   └── portfolio-config.schema.json
│
├── templates/                           # BOŞ şablonlar
│   ├── master-excel.xlsx                # 18 sheet, formül yok
│   ├── project/
│   │   ├── config.template.json
│   │   ├── memory.template.md
│   │   └── README.template.md
│   ├── reports/
│   │   ├── monthly.template.md
│   │   ├── quick-win.template.md
│   │   ├── content-decay.template.md
│   │   ├── cluster-map.template.md
│   │   ├── tech-audit.template.md
│   │   ├── cannibalization.template.md
│   │   ├── portfolio-overview.template.md
│   │   ├── portfolio-weekly-brief.template.md
│   │   ├── portfolio-monthly-roundup.template.md
│   │   └── portfolio-task-heatmap.template.md
│   └── content/
│       ├── new-blog.template.md
│       └── revision.template.md
│
├── rules/                               # NORMATİF disiplinler
│   ├── naming.md
│   ├── single-source-of-truth.md
│   ├── schema-first.md
│   ├── append-only-state.md
│   ├── excel-discipline.md              # formula_policy: values_only
│   ├── secrets-management.md
│   ├── glossary-discipline.md
│   ├── skill-description-discipline.md
│   ├── schema-versioning-discipline.md
│   └── time-discipline.md               # UTC ISO 8601
│
├── docs/                                # statik + canlı dökümanlar
│   ├── ARCHITECTURE.md                  # statik — bu doküman özetlenmiş
│   ├── GLOSSARY.md                      # statik — terim sözlüğü
│   ├── CONTRIBUTING.md                  # statik
│   ├── INSTALL.md                       # statik — workspace setup
│   ├── WORKFLOWS.md                     # canlı katalog
│   ├── PHASE_STATUS.md                  # canlı, <5KB
│   ├── OPEN_QUESTIONS.md                # canlı
│   ├── DECISIONS.md                     # append-only ADR
│   ├── SESSION_PROTOCOL.md              # statik — fresh session uyanma
│   ├── REFERENCE_INDEX.md               # statik — "X için nereye"
│   ├── WORKER_PROMPTS.md                # statik — manager'ın worker template'leri
│   └── CONTEXT_LEDGER.md                # canlı, manager'ın okuma kaydı
│
├── tests/
│   ├── schemas/                         # her schema için fixture testi
│   ├── scripts/                         # her python helper için 1 happy + 1 error
│   └── smoke/                           # plugin yüklenebilir mi
│
├── .github/
│   └── workflows/
│       └── ci.yml                       # 7 check (§17.10)
│
├── README.md
├── CHANGELOG.md                         # SemVer release notes (KISA tutulacak)
├── LICENSE
└── .gitignore
```

---

## 4. Workspace Tam Yapı

```
platinum-seo-workspace/
├── projects/
│   ├── {slug}/                      # her proje aynı yapıda
│   │   ├── config.json                  # project-config.schema'ya uyar
│   │   ├── memory.md                    # project-memory.schema frontmatter + body
│   │   ├── master.xlsx                  # 18 sheet, formül yok
│   │   ├── inbox/                       # ham veri (gitignore'da olabilir)
│   │   │   ├── sf/{date}/               # SF crawl klasörleri
│   │   │   ├── gsc/{date}.csv
│   │   │   ├── dfs/{date}.json
│   │   │   └── manual/
│   │   ├── outputs/                     # üretilen markdown raporlar
│   │   │   ├── reports/
│   │   │   │   ├── {date}-monthly.md
│   │   │   │   └── {date}-quickwin.md
│   │   │   ├── content/
│   │   │   │   ├── drafts/
│   │   │   │   └── revisions/
│   │   │   └── tech/
│   │   └── _state/                      # makine-okunur (insan dokunmaz)
│   │       ├── events.jsonl             # APPEND-ONLY provenance log
│   │       ├── workflows/{run_id}.json  # workflow-run.schema
│   │       ├── backups/master-{ts}.xlsx # last 7 rotation
│   │       └── cache/                   # geçici, gitignore
│   ├── vento/, eykom/, bigcattr/, calitte/, lastiksa/, noraninsaat/, adstark/
│
├── shared/
│   ├── portfolio.json                   # tüm projelerin kayıt defteri
│   ├── portfolio-heatmap.md             # üretilir (skill output)
│   ├── shared-rules.md                  # portföy genelinde notlar
│   └── active.json                      # {"active_project": "{slug}"}
│
├── _archive/                            # arşivlenmiş eski projeler/data
│
├── .claude/
│   └── settings.local.json              # workspace-spesifik Claude Code ayarları
│
├── .env                                 # GİTIGNORE — API keys, paths
├── .env.example                         # COMMIT — template
├── .gitignore
├── CLAUDE.md                            # KISA: "burası workspace, plugin logic taşır"
└── README.md
```

---

## 5. Master Excel Standard (18 Sheet)

Plugin `templates/master-excel.xlsx` 18 sheet'le boş üretilir. Her sheet'in column yapısı `schemas/master-excel.schema.json` tarafından kilitlidir. **Hücrelerde formül yoktur** (`formula_policy: values_only`) — tüm hesaplamalar Python'da, Excel'e literal yazılır.

| # | Sheet (logical name) | Header Row | Amaç |
|---|---|---|---|
| 1 | dashboard | (KPI cells) | KPI özeti (R10-R59 hücrelerinde) |
| 2 | topical_map | 4 | Pillar/cluster/keyword hiyerarşisi |
| 3 | cluster_keywords | 3 | Keyword → cluster mapping + GSC + intent |
| 4 | cannibalization | 4 | Conflict pair, resolution |
| 5 | quick_wins | 4 | 8-20 sırasındaki fırsatlar |
| 6 | new_content_plan | 3 | Üretilecek yeni içerikler (TIVL tag, lifecycle) |
| 7 | content_improve | 4 | Mevcut içeriğin optimizasyon planı |
| 8 | gsc_performance | 4 | Period-over-period delta tracking |
| 9 | content_decay | 5 | Düşüş gösteren içerikler |
| 10 | on_page_audit | 4 | URL × query: in_title/meta/h1 |
| 11 | opportunity | 4 | Opportunity score'lu fırsatlar |
| 12 | tech_seo | 3 | Teknik SEO sorunları |
| 13 | crawl_sitemap | 3 | Crawl + sitemap metrikleri |
| 14 | robots_txt | 4 | robots.txt audit |
| 15 | schema | 3 | Schema markup audit |
| 16 | redirect_404 | 4 | Yönlendirme + 404 listesi |
| 17 | completed_work | 4 | Tamamlanan iş kaydı (events.jsonl özetı) |
| 18 | master_task | 3 | Tüm task listesi (otorite — 19 column) |

**Master Excel Yazma Disiplini** (`rules/excel-discipline.md`):
- ASLA doğrudan yazılmaz, sadece `scripts/excel/transaction.py` üzerinden.
- Her write öncesi `scripts/excel/backup.py` çağrılır (rotating backup).
- Her write sonrası 20 invariant koşturulur, AMBER/RED varsa skill durur.
- Hücreye formül yazmak `formula_policy.forbidden_patterns`'i ihlal eder → CI patlar.

---

## 6. SF Required Reports (40 Rapor, 3 Tier)

`schemas/sf-required-reports.schema.json` zaten eski repodan taşınır.

**Tier 1 — REQUIRED (14)** — eksikse `sf-import` RED abort:
internal_all, all_inlinks, all_outlinks, response_codes_all, issues_overview_report, page_titles_all, meta_description_all, h1_all, canonicals_all, directives_all, indexability, structured_data_all, sitemaps_all, redirect_chains.

**Tier 2 — RECOMMENDED (10)** — eksikse AMBER warn:
h2_all, images_all, hreflang_all, orphan_pages, all_anchor_text, near_duplicates_report, exact_duplicates_report, search_console_all, crawl_depth, pagination_all.

**Tier 3 — OPTIONAL (16)** — eksikse silent:
security_all, javascript_all, response_times_all, word_count, broken_internal_links, broken_external_links, images_missing_alt, page_speed_insights, ga_integration, meta_keywords, pdf_all, amp_all, urls_not_in_sitemap, xml_sitemap_urls_not_in_internal, canonical_mismatch, links_to_noindex.

**Profile Elevation:** Profil bazlı (e-commerce, ymyl, local-service, b2b-saas, portfolio) bazı raporlar required'a yükseltilir. Schema'da `profile_elevations` field'i taşınır.

---

## 7. Cross-Sheet Invariants (20 Governance Kuralı)

`schemas/cross-sheet-invariants.json` zaten eski repodan taşınır. **Drift-check skill'inin core'u.**

**Foundation Rules (15 — F-01 to F-15):**
- F-01: master_task.url ⊆ (crawl_sitemap.url ∪ external_urls) — CRITICAL
- F-02: count(master_task WHERE status=DONE) == dashboard.R48 — CRITICAL
- F-03: count(master_task WHERE status=TODO) == dashboard.R49 — CRITICAL
- F-04: count(master_task WHERE status=ONGOING) == dashboard.R50 — HIGH
- F-05: completed_work.task_id ⊆ master_task WHERE status=DONE — HIGH
- F-06: new_content_plan.url_slug ⊆ topical_map.assigned_url — CRITICAL
- F-07: content_improve.url ⊆ (crawl_sitemap ∩ topical_map) — HIGH
- F-08: quick_wins.target_url ⊆ (crawl_sitemap ∪ gsc_performance) — HIGH
- F-09: cluster_keywords.assigned_url ⊆ topical_map.assigned_url — HIGH
- F-10: cannibalization.pages ⊆ crawl_sitemap.url — HIGH
- F-11: schema.url ⊆ crawl_sitemap.url — HIGH
- F-12: redirect_404.from_url ⊆ sf_response_codes WHERE status IN (301,302,404) — HIGH
- F-13: robots_txt.disallowed == crawl_sitemap WHERE indexability='Non-indexable (robots)' — MEDIUM
- F-14: gsc_performance.page ⊆ (crawl_sitemap ∪ redirect_targets) — MEDIUM
- F-15: cannibalization intent çakışması intent-matrix.json ile tutarlı — HIGH

**Data Rules (3 — D-01 to D-03):**
- D-01: topical_map.pillar ⊆ data/pillars.json — CRITICAL
- D-02: cluster_keywords.cluster ⊆ data/cluster defs — HIGH
- D-03: url_normalizer(x) == x for every URL — HIGH

**MCP Rules (2 — M-01, M-02):**
- M-01: gsc_performance URL set is consistent with dashboard KPI URL set — MEDIUM
- M-02: SF import run_id == Excel crawl_date (freshness) — MEDIUM

**Verdict Aggregation:** any RED → RED; else any AMBER/WARN → AMBER; all PASS → GREEN.
**Severity Map:** CRITICAL/HIGH → RED on FAIL, MEDIUM/LOW → AMBER on FAIL.

---

## 8. Disiplinler (10 Pazarlık Edilemez Kural)

Her biri `rules/*.md` dosyasında. Drift-check ve CI pipeline bunları otomatik denetler.

### 8.1 Single Source of Truth (`rules/single-source-of-truth.md`)
Bir terim, schema, template, kural **TEK YER**de tanımlanır. İkinci yere yazılmaz, referans verilir.

### 8.2 Schema-First (`rules/schema-first.md`)
Bir veri şekli yazılmadan ÖNCE schema'sı `schemas/*.schema.json` dosyasında olmak zorundadır. Schema yoksa data yazılmaz.

### 8.3 Plugin = Proje-Agnostik (`rules/single-source-of-truth.md`)
Plugin repo içinde gerçek proje slug'ı (pilot/müşteri proje adı) **GEÇMEZ**. CI grep ile kontrol eder.

### 8.4 State Append-Only (`rules/append-only-state.md`)
`events.jsonl` ve `workflows/{run_id}.json` dosyaları silinmez/üzerine yazılmaz. Sadece append edilir veya yeni dosya oluşturulur.

### 8.5 Excel Atomic Writes (`rules/excel-discipline.md`)
Master excel **SADECE** `scripts/excel/transaction.py` üzerinden yazılır. Direkt write yasak. Write öncesi backup, sonrası invariant check zorunlu.

### 8.6 Naming (`rules/naming.md`)
- Slugs: `^[a-z][a-z0-9-]*$` (lowercase kebab-case)
- Skill names: kebab-case
- Schema files: `kebab-case.schema.json`
- File names: kebab-case
- Sheet names (Excel): snake_case
- Variable names (Python): snake_case
- Workflow run IDs: `{slug}-{YYYY-MM-DD}-{short_uuid}`

### 8.7 Secrets Management (`rules/secrets-management.md`)
API key'ler ASLA repo'ya commit edilmez. `.env` (gitignore) veya system keychain. `scripts/security/check_secrets.sh` pre-commit'te koşar.

### 8.8 Glossary Discipline (`rules/glossary-discipline.md`)
Her terim `docs/GLOSSARY.md`'de tanımlı olmalı. Skill/template/schema'da glossary'de olmayan teknik terim → `glossary-audit` AMBER warn.

### 8.9 Skill Description Discipline (`rules/skill-description-discipline.md`)
Her skill'in YAML frontmatter'ı `schemas/skill-frontmatter.schema.json`'a uyar. Detay §9.

### 8.10 Time Discipline (`rules/time-discipline.md`)
Tüm timestamp'ler **UTC ISO 8601** (`2026-04-30T12:34:56Z`). İnsan-yüzlü raporlarda Europe/Istanbul'a çevrilir. Kod-okunur dosyalarda **sadece UTC**.

### 8.11 Schema Versioning (`rules/schema-versioning-discipline.md`)
Schema bump (`v1.0 → v1.1`) yapıldığında `scripts/migrations/{NNNN}_{schema-name}_{from}_to_{to}.py` migration script'i ZORUNLU yazılır. Session-start hook proje config'lerinin schema_version'ını kontrol eder.

---

## 9. Skill Description Discipline (Auto-Trigger Kalitesi)

Claude'un doğru skill'i doğru zamanda tetiklemesi için, her skill'in frontmatter'ı standart bir yapıya uyar.

**`schemas/skill-frontmatter.schema.json`** (yeni yazılır) bu yapıyı kilitler:

```yaml
---
name: quick-wins                    # kebab-case, dizin adıyla aynı
description: |
  Use when: kullanıcı "quick win", "hızlı kazanım", "kolay yükselebilecek
  sayfalar", "8-20 sıradaki keyword'ler", "low-hanging fruit" gibi
  ifadeler kullandığında. Also use when: kullanıcı GSC verisi varken
  sıralamada yükselebilecek fırsatları aradığında. Do not use when:
  kullanıcı yeni içerik planı (new-content-plan), içerik iyileştirme
  (content-improve) veya teknik audit (tech-audit) istiyorsa.
version: "1.0"
status: active                      # active | deprecated | wip
category: discovery                 # dizin yapısıyla eşleşir
inputs:
  project_slug:
    type: string
    required: true
  lookback_days:
    type: integer
    default: 90
outputs:
  - "master.xlsx#quick_wins"        # logical sheet
  - "outputs/reports/{date}-quickwin.md"
  - "events.jsonl"
consumes:                            # bu skill'in girdisi olan başka skill çıktıları
  - "sf-import:master.xlsx#crawl_sitemap"
  - "gsc-pull:master.xlsx#gsc_performance"
produces:                            # bu skill'in çıktısını kullanan başka skill'ler
  - "drift-check"
  - "monthly-report"
triggers:
  manual: ["/pseo-quickwin"]
  natural_language: |
    "quick win", "hızlı kazanım", "low-hanging fruit",
    "8-20 sıradaki sayfalar", ...
  hooks: []
  scheduled:                              # autonomy için (opsiyonel)
    - cron: "0 9 * * 1"                   # her Pazartesi 09:00 UTC
      mode: "report-only"                 # auto-execute YAPMA, sadece rapor
mcp_tools:                                # bu skill'in kullandığı MCP'ler
  required:
    - "mcp__gsc__detect_quick_wins"
    - "mcp__gsc__enhanced_search_analytics"
  optional:
    - "mcp__gsc__search_analytics"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:                                 # autonomous mode için
  confidence: HIGH                        # HIGH | MEDIUM | LOW
  requires_approval: true                 # büyük değişiklikler için yes
  safe_auto_execute: false                # CI/scheduled run'da otomatik koşabilir mi
---
```

**`glossary-audit` skill'i** her skill'in description'ında:
1. Frontmatter schema'ya uyuyor mu?
2. `consumes`/`produces` graf'ında orphan var mı?
3. Description'da glossary dışı terim var mı?

---

## 10. Workflow Run State (Resume/Retry/Approval — Kod Yok)

`schemas/workflow-run.schema.json` (yeni):

```json
{
  "$id": "...",
  "type": "object",
  "required": ["run_id", "skill", "project_slug", "status", "started_at", "steps"],
  "properties": {
    "run_id":  { "pattern": "^[a-z0-9-]+-[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]{4}$" },
    "skill":   { "type": "string" },
    "project_slug": { "pattern": "^[a-z][a-z0-9-]*$" },
    "status":  { "enum": ["running", "awaiting_approval", "paused", "done", "failed"] },
    "started_at": { "format": "date-time" },
    "ended_at":   { "format": "date-time" },
    "current_step": { "type": "integer" },
    "total_steps":  { "type": "integer" },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "status"],
        "properties": {
          "name":   { "type": "string" },
          "status": { "enum": ["pending", "running", "done", "awaiting_approval", "failed", "skipped"] },
          "started_at": { "format": "date-time" },
          "ended_at":   { "format": "date-time" },
          "output_ref": { "type": "string" },
          "approval_prompt": { "type": "string" },
          "approval_decision": { "enum": ["yes", "no", null] },
          "error": { "type": "string" }
        }
      }
    },
    "outputs": { "type": "object" },
    "errors":  { "type": "array" }
  }
}
```

**Skill Protokolü:**
- Her step başlamadan önce: status `running`, `started_at` set.
- Her step sonunda: status `done`, `ended_at` set, `output_ref` yaz.
- Approval gate: status `awaiting_approval`, `approval_prompt` set, **skill exit** eder.
- User "evet" derse: load run state, `approval_decision: "yes"`, devam.
- User "hayır" derse: status `paused` veya `failed`.
- Failure: `failed`, `error` set.
- Done: tüm step'ler `done` → run status `done`, `ended_at` set.

**Skill `_state/workflows/{run_id}.json` dosyasını her step sonrası günceller.** State machine kütüphanesi yok — sadece JSON yazma disiplini.

---

## 11. v1 Workflow Catalog (~43 Skill, Batch'lerle)

v1 release **tüm skill setini** kapsar (eski sistem 28 skill + bizim eklediklerimiz governance/ingestion/planning skill'leri = ~43 skill). Sırayla değil **batch'lerle** (Phase 5-13) inşa edilir; foundation (Phase 0-4) tamamlandıktan sonra her batch paralel worker'larla yazılır.

### 11.1 Tam Skill Listesi (Kategori Bazında)

#### Meta (4)
| Skill | Trigger | Phase |
|---|---|---|
| init-project | "yeni proje", `/pseo-init` | 5 |
| whats-next | "ne yapmalıyım", "bugün" | 5 |
| brand-onboarding | "marka onboard" | 12 |
| mark-done | "tamamlandı" | 12 |

<!-- v1.1 Integration Audit Wave 1 (2026-05-06): load-context moved to Governance (skills/governance/load-context/) per Phase 13+ refactor; was originally drafted under Meta. Q-V1.2-DESIGN-CATEGORY-DRIFT-01 P2 inline resolution. -->


#### Ingestion (4)
| Skill | Trigger | Phase |
|---|---|---|
| sf-import | "SF crawl yükle" | 5 |
| gsc-pull | "GSC veri çek" | 6 |
| dfs-pull | "DataForSEO veri çek" | 6 |
| scrapling-ops | "site scrape" | 6 |

#### Discovery (10)
| Skill | Trigger | Phase |
|---|---|---|
| quick-wins | "quick win", `/pseo-quickwin` | 5 |
| cannibalization | "cannibalization", "yamyamlık" | 7 |
| content-decay | "content decay", "düşen içerik" | 7 |
| tech-audit | "tech audit" | 7 |
| on-page-audit | "on-page audit" | 7 |
| content-gaps | "content gap" | 7 |
| schema-audit | "schema audit" | 7 |
| competitive-analysis | "rakip analizi" | 7 |
| geo-analysis | "GEO analiz" | 7 |
| aio-competitor-map | "AIO competitor" | 12 |

#### Planning (5)
| Skill | Trigger | Phase |
|---|---|---|
| cluster-map | "cluster map" | 8 |
| topical-map | "topical map" | 8 |
| new-content-plan | "yeni içerik planı" | 8 |
| internal-links | "iç link planı" | 8 |
| master-task-sync | "task sync" | 8 |

#### Reporting (9)
| Skill | Trigger | Phase |
|---|---|---|
| monthly-report | "aylık rapor", `/pseo-monthly` | 9 |
| weekly-summary | "haftalık özet" | 9 |
| monitoring-weekly | "haftalık izleme" | 12 |
| portfolio-overview | "portföy özet" | 9 |
| portfolio-weekly-brief | "portföy haftalık" | 9 |
| portfolio-monthly-roundup | "portföy aylık" | 9 |
| portfolio-task-heatmap | "task heatmap" | 9 |
| portfolio-kpi-trend | "kpi trend" | 9 |
| portfolio-heatmap | "heatmap genel" | 9 |

<!-- v1.1 Integration Audit Wave 1 (2026-05-06): monitoring-weekly moved here from Governance (skills/reporting/monitoring-weekly/) — semantic match with reporting-cron pattern; was originally listed under Governance. Q-V1.2-DESIGN-CATEGORY-DRIFT-01 P2 inline resolution. -->


#### Production (5)
| Skill | Trigger | Phase |
|---|---|---|
| new-blog | "yeni blog yaz" | 11 |
| revise-content | "içerik revize" | 11 |
| generate-images | "görsel üret" | 11 |
| content-remediation | "içerik düzeltme" | 11 |
| faq-optimization | "FAQ optimize" | 11 |

#### Publishing (2)
| Skill | Trigger | Phase |
|---|---|---|
| indexing-ping | "indexlenmesi" | 12 |
| verify-indexing | "index kontrol" | 12 |

#### Governance (4)
| Skill | Trigger | Phase |
|---|---|---|
| drift-check | "drift kontrol", `/pseo-driftcheck` | 5 |
| schema-validate | "schema validate" | 13 |
| glossary-audit | "glossary kontrol" | 13 |
| load-context | (hook tetikli) | 13 |

<!-- v1.1 Integration Audit Wave 1 (2026-05-06): load-context moved here from Meta (skills/governance/load-context/) — semantic match with governance pattern (audit/load context for hook-driven invocation). monitoring-weekly moved out to Reporting per category drift fix. Net category total unchanged (4). Q-V1.2-DESIGN-CATEGORY-DRIFT-01 P2 inline resolution. -->


**Toplam: 43 skill**, 8 kategori, 9 phase üzerine yayılmış.

### 11.2 Phase 5 Critical Path Skill Detayları

Phase 5'in 5 skill'i diğer phase'ler için **referans pattern**'i kuruyor:

#### init-project
1. Slug + name + domain alır (interactive prompt'la doğrular)
2. `projects/{slug}/` klasörü açar
3. `templates/project/`'i kopyalar
4. `templates/master-excel.xlsx` → `projects/{slug}/master.xlsx`
5. `inbox/`, `outputs/`, `_state/` klasörleri açar
6. `shared/portfolio.json`'a slug ekler
7. events.jsonl → `project_created`
8. Approval gate: `config.json` review
9. (Opsiyonel) `gsc__list_sites` ile GSC validation
10. Tamam.

#### sf-import
1. Slug + crawl folder path
2. Folder → `inbox/sf/{date}/`
3. `sf-required-reports.schema.json`'a karşı validate (Tier 1 eksik → RED abort)
4. `staging-to-excel-map.json`'a göre logical sheet'e map
5. `gsc__list_sitemaps`, `get_sitemap` ile sitemap cross-check
6. `transaction.py` ile master.xlsx'e write
7. events.jsonl → `sf_imported`
8. Tamam.

#### quick-wins
1. Slug
2. **`gsc__detect_quick_wins` MCP çağrısı (HAZIR detector — büyük şans)**
3. `gsc__enhanced_search_analytics` ile zenginleştirme
4. Approval gate: top N seçim
5. master.xlsx [quick_wins] write
6. `outputs/reports/{date}-quickwin.md` üret
7. events.jsonl → `quickwins_generated`
8. Tamam.

#### drift-check
1. Slug (yoksa tüm projeler)
2. master.xlsx tüm sheet'ler yükle
3. 20 cross-sheet invariant koştur (§7)
4. `consistency-report.schema.json`'a uyan rapor
5. RED → uyarı + auto-fix önerisi
6. AMBER → not + rapor
7. GREEN → events.jsonl
8. Tamam.

#### whats-next (Router)
1. Slug (yoksa active.json)
2. master_task TODO + priority sırala
3. content_decay son 7 gün RED trend
4. quick_wins onaysız bekleyenler
5. Priority list sun
6. Kullanıcı seçerse uygun skill çağır

### 11.3 Diğer 38 Skill

Phase 6-13'teki skill'ler aynı pattern'i takip eder:
- Frontmatter `skill-frontmatter.schema.json`'a uyar
- Multi-step ise `workflow-run.schema.json` state'i tutulur
- Excel write `transaction.py` üzerinden
- MCP çağrısı varsa pattern §16.5'e uyar
- events.jsonl'e log düşer

Her skill'in detayı kendi phase'inde, ilgili worker tarafından §13.4 worker output paketi formatında üretilir. Manager session **detay kararı vermez**, sadece worker prompt'u ve acceptance kriteri belirler.

---

## 12. Post-v1 Düşünceleri

v1 ~43 skill ile **eksiksiz** bir SEO Workflow OS sunar. v1.1+'da düşünülecekler:
- Performance optimizations (skill execution time)
- Multi-user / team collaboration (şu an single user)
- Real-time dashboards (web UI — şu an Excel + markdown)
- Advanced AIO mention tracking (DataForSEO LLM Mentions API'sinin daha derin kullanımı)
- Auto-publishing entegrasyonları (WordPress, Webflow, Ghost direct push)
- Custom skill builder (kullanıcının kendi skill'ini yazmasına yardımcı meta-skill)

**Disiplin:** v1 acceptance test'i geçmeden v1.1 başlamaz.

---

## 13. Manager Session Protocol

### 13.1 Manager Session Nedir
- **Karar verici** session. Kod yazan ana worker DEĞİL.
- Görevleri:
  - Plan tutmak (PHASE_STATUS)
  - Worker session promptları üretmek (WORKER_PROMPTS)
  - Worker çıktılarını işlemek
  - DECISIONS, OPEN_QUESTIONS, CONTEXT_LEDGER güncellemek
  - Phase gateway kararı vermek

### 13.2 Fresh Session Uyanma Sırası

Fresh session açıldığında:
1. Bootstrap prompt'u oku (kullanıcı paste eder)
2. **Bu spec doc'unun §1, §13, §17'sini oku**
3. `docs/PHASE_STATUS.md` oku
4. `docs/OPEN_QUESTIONS.md` oku
5. `docs/DECISIONS.md` son 5 ADR oku
6. `docs/REFERENCE_INDEX.md` oku
7. **DUR.** Geri kalanı ihtiyaç duyduğunda oku.

**Toplam ilk yükleme: <15KB.** 1M context'in <%2'si.

### 13.3 Subagent Dispatch Kuralı

**Worker'a delege et:**
- Çok dosya okuma gereken araştırma
- Birden fazla dosya yazma gereken implementation
- Test koşturma
- Schema validation
- Migration script yazma

**Manager'da kalsın:**
- Plan kararları
- Phase gateway kararı
- DECISIONS güncelleme
- OPEN_QUESTIONS resolve
- Worker prompt'u yazma

### 13.4 Worker Output Paketi

Worker session'lar manager'a dönerken **kompakt bir paket** dönmeli:

```markdown
## Worker Output Package

**Worker:** {worker name}
**Phase:** {phase id}
**Task:** {short task description}

### Files Created/Modified
- path/to/file.md (NEW, 142 lines)
- path/to/other.json (MODIFIED, +12/-3)

### Decisions Made
- {decision 1 — 1 line}
- {decision 2 — 1 line}

### Open Questions Surfaced
- {q1 — 1 line}

### Next Step Recommended
- {next step}

### Verification
- [x] schema-validate PASS
- [x] tests PASS
- [ ] drift-check (not run — out of scope)
```

Manager bu paketi alır, ilgili dosyaları günceller, sonraki adıma geçer. **Worker transcript'i full okumaz**, sadece paketi okur.

---

## 14. Manager Dosyaları (Format Kuralları)

### 14.1 `docs/PHASE_STATUS.md` (canlı, <5KB)

```markdown
# Phase Status

**Last Updated:** {ISO timestamp}
**Active Phase:** Phase 3 — Schema Migration

## Current Phase
**Goal:** {1 cümle}
**Started:** {date}
**Estimated End:** {date}

### Tasks
- [x] Task 1 — done {date}
- [x] Task 2 — done {date}
- [ ] Task 3 — in progress (worker dispatched)
- [ ] Task 4 — pending

### Blockers
- {blocker — 1 line}

## Phase History
| Phase | Status | Started | Ended |
|---|---|---|---|
| Phase 0 | done | 2026-04-30 | 2026-04-30 |
| Phase 1 | done | 2026-05-01 | 2026-05-02 |
| Phase 2 | done | 2026-05-03 | 2026-05-04 |
| Phase 3 | active | 2026-05-05 | — |

## Next Phase Preview
**Phase 4:** {1 line preview}
```

### 14.2 `docs/OPEN_QUESTIONS.md` (canlı, <3KB)

```markdown
# Open Questions

## Unresolved
### Q-007: {question}
**Raised:** {date} during Phase {N}
**Context:** {1-2 lines}
**Options:**
- a) {option}
- b) {option}
**Owner:** user | manager
**Blocking Phase:** {N}

## Resolved (last 5 — moved to DECISIONS)
- Q-001 → ADR-003
- Q-002 → ADR-005
- ...
```

### 14.3 `docs/DECISIONS.md` (append-only)

```markdown
# Architecture Decision Records

## ADR-001 — {title}
**Date:** 2026-04-30
**Status:** accepted | superseded
**Context:** {2-3 lines}
**Decision:** {1-2 lines}
**Consequences:** {1-2 lines}

## ADR-002 — ...
```

### 14.4 `docs/SESSION_PROTOCOL.md` (statik)

§13'ün özeti. Fresh session'lar bunu okur.

### 14.5 `docs/REFERENCE_INDEX.md` (statik)

```markdown
# Reference Index

## Excel sheet structure?
→ `schemas/master-excel.schema.json` + spec §5

## Cross-sheet rules?
→ `schemas/cross-sheet-invariants.json` + spec §7

## SF reports?
→ `schemas/sf-required-reports.schema.json` + spec §6

## How to write a new skill?
→ `rules/skill-description-discipline.md` + spec §9

## How does workflow resume work?
→ `schemas/workflow-run.schema.json` + spec §10

...
```

### 14.6 `docs/WORKER_PROMPTS.md` (statik)

Manager'ın worker session açarken kullandığı template'ler:

```markdown
# Worker Session Prompts

## Type 1: Schema Migration Worker
{template}

## Type 2: Skill Implementation Worker
{template}

## Type 3: Test Writing Worker
{template}

## Type 4: Documentation Worker
{template}
```

### 14.7 `docs/CONTEXT_LEDGER.md` (canlı, manager'ın okuma kaydı)

Manager session'ın o anki "neyi okudum/okumadım" kaydı. Manager kendisini context bombardımanından korumak için bunu tutar:

```markdown
# Context Ledger

**Session Start:** {ISO}

## Loaded
- spec §1, §13, §17 (initial)
- PHASE_STATUS.md
- ADR-005, ADR-008 (most recent)

## Loaded On Demand
- {file} — for {task}

## Excluded (Don't Reload Unless Asked)
- ARCHITECTURE.md (covered by spec)
- CHANGELOG.md
- All other ADRs

## Subagent Calls
- {timestamp} — {agent type} — {1 line task}
```

---

## 15. Eski Repolardan Taşınacak (Tam Liste)

### 15.1 Schemas (17 dosya — `~/Documents/platinum-seo-core/templates/` ve `~/Documents/platinum-seo-core/schemas/`)

| Kaynak | Hedef | Cleanup |
|---|---|---|
| `templates/master-excel-schema.json` | `schemas/master-excel.schema.json` | ARCHITECTURE-v4 ref'lerini new docs'a remap |
| `templates/cross-sheet-invariants.json` | `schemas/cross-sheet-invariants.json` | aynı remap |
| `templates/project-config.schema.json` | `schemas/project-config.schema.json` | aynı remap |
| `templates/sf-required-reports.schema.json` | `schemas/sf-required-reports.schema.json` | aynı remap |
| `templates/sf-export-mapping.schema.json` | `schemas/sf-export-mapping.schema.json` | — |
| `templates/monthly-report.schema.json` | `schemas/monthly-report.schema.json` | — |
| `templates/provenance-log.schema.json` | `schemas/events.schema.json` | rename + scope |
| `templates/work-log.schema.json` | (events.schema'ya merge) | — |
| `templates/consistency-report.schema.json` | `schemas/consistency-report.schema.json` | — |
| `templates/mcp-tool-registry.schema.json` | `schemas/mcp-tool-registry.schema.json` | — |
| `templates/excel-config.schema.json` | `schemas/excel-config.schema.json` | — |
| `templates/excel-source-manifest.schema.json` | `schemas/excel-source-manifest.schema.json` | — |
| `templates/staging-to-excel-map.schema.json` | `schemas/staging-to-excel-map.schema.json` | — |
| `templates/portfolio-config.schema.json` | `schemas/portfolio-config.schema.json` | — |
| `schemas/dataforseo-endpoint-mapping.schema.json` | `schemas/dataforseo-endpoint-mapping.schema.json` | — |
| `schemas/gsc-tool-mapping.schema.json` | `schemas/gsc-tool-mapping.schema.json` | — |
| `schemas/scrapling-output-mapping.schema.json` | `schemas/scrapling-output-mapping.schema.json` | — |

### 15.2 Scripts (3 dosya)

| Kaynak | Hedef | Cleanup |
|---|---|---|
| `~/Documents/platinum-premium-seo/scripts/bootstrap_excel.py` | `scripts/excel/bootstrap_excel.py` | sadeleştirme; v3 referansları çıkarılacak |
| `~/Documents/platinum-premium-seo/scripts/bootstrap_project_packs.py` | `scripts/state/bootstrap_project.py` | 44KB → ~10KB hedef; ölü kod temizlenir |
| `~/Documents/platinum-premium-seo/scripts/check-secrets.sh` | `scripts/security/check_secrets.sh` | aynen taşınır |

### 15.3 Templates (Markdown report templates)

`~/Documents/platinum-seo-core/templates/` içinde 14 markdown:

| Kaynak | Hedef | Cleanup |
|---|---|---|
| `monthly-report.md` | `templates/reports/monthly.template.md` | — |
| `quick-win.md` | `templates/reports/quick-win.template.md` | — |
| `content-decay.md` | `templates/reports/content-decay.template.md` | — |
| `cluster-map.md` | `templates/reports/cluster-map.template.md` | — |
| `competitive-analysis.md` | `templates/reports/competitive-analysis.template.md` | — |
| `cannibalization.md` (yoksa skill markdown'undan) | `templates/reports/cannibalization.template.md` | — |
| `portfolio-overview.md` | `templates/reports/portfolio-overview.template.md` | — |
| `portfolio-weekly-brief.md` | `templates/reports/portfolio-weekly-brief.template.md` | — |
| `portfolio-monthly-roundup.md` | `templates/reports/portfolio-monthly-roundup.template.md` | — |
| `portfolio-task-heatmap.md` | `templates/reports/portfolio-task-heatmap.template.md` | — |
| `portfolio-kpi-trend.md` | `templates/reports/portfolio-kpi-trend.template.md` | — |
| `sf-crawl-import.md` | (skill content'ine entegre) | — |
| `scrapling-ops.md` | (v1.4 skill için bekletilir) | — |
| `onboard-project.md` | (init-project skill content'ine entegre) | — |

### 15.4 Rules (`~/Documents/platinum-seo-core/rules/universal-rules.json` — 28KB)

Tek dosya halinde 28KB. **Olduğu gibi taşınmaz**, parsing edilir, içindeki kurallar `rules/*.md` dosyalarına dağıtılır. Phase 1 worker görevi.

### 15.5 Cleanup Notları

- "ARCHITECTURE-v4 §X.Y" gibi referanslar → yeni `docs/ARCHITECTURE.md`'ye remap
- Python referansları (eski engine) → kaldırılır
- MCP server referansları → kaldırılır
- "platinum-seo-core" string'i → "platinum-seo-engine" replace
- Tarih damgaları → korunur (provenance için)

---

## 16. YAGNI Listesi (v1'de YAPMIYORUZ)

❌ Custom MCP server (mevcut MCP'ler yeterli)
❌ Python state machine class'ları (JSON disiplini yeter)
❌ CLI binary / `pseo` shell command (skills + commands yeter)
❌ Database (sqlite/postgres) (Excel + JSONL yeter)
❌ Approval gate library (workflow-run.schema yeter)
❌ Multiple storage backend (filesystem yeter)
❌ Multi-user / multi-tenant (single user, single workstation)
❌ Real-time sync / WebSocket (manuel trigger yeter)
❌ Auto-publishing direkt CMS push (v1'de manual paste yeterli; v1.1+ adayı)
❌ Custom skill builder UI (Claude Code zaten var; v1.1+ adayı)

---

## 16.5 MCP Integration Pattern

Skill'in bir MCP tool'unu nasıl kullandığı sözleşmesi:

```
[1] Skill markdown    → "Şu MCP tool'u şu parametrelerle çağır"
[2] Claude            → MCP tool çağrılır, JSON döner
[3] Raw JSON          → inbox/{source}/{date}-{tool}-{slug}.json
                        (insan-okunur, denetlenebilir provenance)
[4] Skill markdown    → "Şu Python script'ini çağır"
[5] scripts/ingestion → schema validate (input) → transform → 
                        excel/transaction.py'ye delege
[6] master.xlsx       → backup → atomic write → invariant check
[7] events.jsonl      → provenance log
[8] Skill markdown    → kullanıcıya kompakt rapor
```

**3 kural:**
1. **Inbox raw JSON** her zaman saklanır — drift olduğunda "ham veri ne diyordu" diye geri bakılabilir
2. **Script orta katmanda** transformation yapar — Claude her seferinde aynı işi yapmak zorunda değildir
3. **Excel write tek noktadan** (`transaction.py`) — disiplin merkezi

**Skill bu pattern'i ihlal etmez.** Direkt excel write yapılırsa: backup yok → kayıp riski; invariant check yok → drift; events.jsonl log yok → provenance kaybı. CI ve drift-check bu kuralı denetler.

---

## 16.6 Sheet ↔ MCP Mapping

Master excel'in 18 sheet'inin hangi MCP/source ile beslendiği:

| Sheet | Primary Source | İkincil | Skill | Phase |
|---|---|---|---|---|
| dashboard | (computed) | — | dashboard-refresh (script) | 5+ |
| topical_map | `dataforseo_labs_keyword_ideas`, `related_keywords` | manual | topical-map | 8 |
| cluster_keywords | `dataforseo_labs_keyword_suggestions` + `gsc__enhanced_search_analytics` | — | cluster-map | 8 |
| cannibalization | `gsc__search_analytics` (cross-page query overlap) | — | cannibalization | 7 |
| quick_wins | **`gsc__detect_quick_wins`** + `gsc__search_analytics` | — | quick-wins | 5 |
| new_content_plan | `dataforseo_labs_keyword_ideas` + manual | — | new-content-plan | 8 |
| content_improve | `gsc__search_analytics` + `dataforseo_on_page_content_parsing` | — | content-remediation | 11 |
| gsc_performance | `gsc__enhanced_search_analytics` (period delta) | — | gsc-pull | 6 |
| content_decay | `gsc__enhanced_search_analytics` (90d vs prior 90d) | — | content-decay | 7 |
| on_page_audit | `dataforseo_on_page_content_parsing` + SF | — | on-page-audit | 7 |
| opportunity | `gsc__search_analytics` + scoring | — | (computed in quick-wins/decay) | 5+ |
| tech_seo | SF (primary) | `dataforseo_on_page_lighthouse` | tech-audit | 7 |
| crawl_sitemap | SF + `gsc__list_sitemaps`, `get_sitemap` | — | sf-import | 5 |
| robots_txt | SF + manual fetch | — | tech-audit | 7 |
| schema | SF (structured_data_all) | — | schema-audit | 7 |
| redirect_404 | SF (response_codes) + `gsc__index_inspect` | — | sf-import + tech-audit | 5+7 |
| completed_work | events.jsonl | — | mark-done | 12 |
| master_task | computed (decay+quickwin+tech+manual) | — | master-task-sync | 8 |

**Notlar:**
- **SF reports MCP değil** — kullanıcı Screaming Frog'u kendi makinesinde çalıştırır, klasörü `inbox/sf/{date}/`'e koyar.
- **`gsc__detect_quick_wins`** built-in — quick-wins skill'i bunu kullanır, manuel hesap yapmaz.
- **DataForSEO** `budget_credits_per_day` ile sınırlanır (`scripts/budget/check_budget.py`).
- **Scrapling** competitive-analysis (Phase 7) ve new-blog SERP analizi (Phase 11) için.

---

## 16.7 v1 MCP Scope

| MCP | v1 Phase'lerinde Aktif Kullanım | Tipik Skills |
|---|---|---|
| **GSC** (`mcp__gsc__*`) | Phase 5+ | quick-wins, sf-import, gsc-pull, content-decay, cannibalization, opportunity, indexing-ping, verify-indexing |
| **DataForSEO** (`mcp__dataforseo__*`) | Phase 6+ | dfs-pull, cluster-map, topical-map, new-content-plan, on-page-audit, tech-audit, competitive-analysis, aio-competitor-map |
| **Scrapling** (`mcp__ScraplingServer__*`) | Phase 6, 7, 11 | scrapling-ops, competitive-analysis, new-blog (SERP top-5 analizi) |
| **Higgsfield** (`mcp__higgsfield__*`) | Phase 11 | generate-images |
| **Apify** (`mcp__Apify__*`) | (rezervde) | scrapling-ops fallback |
| **google-ads-mcp** | (rezervde) | keyword volume cross-check |

---

## 16.8 Cost / Budget Discipline

Paralı MCP'ler (DataForSEO, bazı Apify actor'leri) için budget guardrail:

1. Her project-config'te `budget_credits_per_day: 500` (default)
2. `scripts/budget/check_budget.py` her DataForSEO MCP çağrısı öncesi:
   - Bugünkü harcamayı `_state/budget/{date}.json`'dan oku
   - Yeni çağrı bütçeyi aşacaksa → **ABORT** + uyarı
   - Aşmıyorsa → çağrıya izin ver, log düş
3. Day rollover otomatik (UTC midnight)
4. Kullanıcı manuel override edebilir: `--allow-overage` flag'i ile (events.jsonl'e işaretlenir)

**Budget ihlal durumunda:** Skill durur, `awaiting_approval` status'una girer, kullanıcıya "bütçe aşıldı, devam edelim mi?" diye sorar.

---

## 16.9 Skill ↔ MCP Tam Matrisi (43 Skill)

Her skill'in kullandığı MCP tool'ları. Skill yazılırken **frontmatter'a `mcp_tools:` field'ı bu tablodan doldurulur** (§9).

### Phase 5 — Critical Path
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| init-project | — | `gsc__list_sites`, `ScraplingServer__fetch` (R-24 tasarım sample) |
| sf-import | `gsc__list_sitemaps`, `gsc__get_sitemap` | — |
| quick-wins | `gsc__detect_quick_wins`, `gsc__enhanced_search_analytics` | `gsc__search_analytics` |
| drift-check | (yok — local) | — |
| whats-next | (yok — local) | — |

### Phase 6 — Ingestion
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| gsc-pull | `gsc__enhanced_search_analytics`, `gsc__search_analytics` | `gsc__index_inspect` |
| dfs-pull | `dataforseo__keywords_data_google_ads_search_volume`, `dataforseo__dataforseo_labs_google_keyword_overview` | `dataforseo__dataforseo_labs_google_historical_keyword_data` |
| scrapling-ops | `ScraplingServer__fetch`, `ScraplingServer__bulk_fetch`, `ScraplingServer__stealthy_fetch`, `ScraplingServer__bulk_stealthy_fetch` | `ScraplingServer__open_session`, `ScraplingServer__close_session` |

### Phase 7 — Discovery
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| cannibalization | `gsc__search_analytics` | `gsc__enhanced_search_analytics` |
| content-decay | `gsc__enhanced_search_analytics` (90d vs prior 90d) | `dataforseo__dataforseo_labs_google_historical_rank_overview` |
| tech-audit | `dataforseo__on_page_lighthouse`, `dataforseo__on_page_content_parsing` | `dataforseo__on_page_instant_pages` |
| on-page-audit | `dataforseo__on_page_content_parsing` | `gsc__search_analytics` |
| content-gaps | `dataforseo__dataforseo_labs_google_keyword_ideas`, `dataforseo__dataforseo_labs_google_related_keywords` | `dataforseo__content_analysis_search`, `dataforseo__dataforseo_labs_google_keywords_for_site` |
| schema-audit | (yok — SF data) | `dataforseo__on_page_content_parsing` |
| competitive-analysis | `ScraplingServer__bulk_stealthy_fetch`, `dataforseo__dataforseo_labs_google_competitors_domain` | `dataforseo__dataforseo_labs_google_domain_rank_overview`, `dataforseo__backlinks_competitors` |
| geo-analysis | `dataforseo__ai_optimization_llm_mentions_search`, `dataforseo__serp_organic_live_advanced` | `dataforseo__ai_optimization_llm_mentions_aggregated_metrics` |
| aio-competitor-map | `dataforseo__ai_optimization_llm_mentions_top_domains`, `dataforseo__ai_optimization_llm_mentions_top_pages`, `dataforseo__ai_optimization_llm_mentions_search` | `dataforseo__ai_optimization_llm_mentions_cross_aggregated_metrics` |

### Phase 8 — Planning
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| cluster-map | `dataforseo__dataforseo_labs_google_keyword_suggestions`, `dataforseo__dataforseo_labs_google_related_keywords`, `gsc__enhanced_search_analytics` | `dataforseo__dataforseo_labs_search_intent` |
| topical-map | `dataforseo__dataforseo_labs_google_keyword_ideas`, `dataforseo__dataforseo_labs_google_related_keywords` | `dataforseo__keywords_data_google_trends_explore` |
| new-content-plan | `dataforseo__dataforseo_labs_google_keyword_ideas` | `dataforseo__dataforseo_labs_google_keyword_overview`, `dataforseo__dataforseo_labs_search_intent` |
| internal-links | (yok — SF inlinks data) | `dataforseo__on_page_content_parsing` |
| master-task-sync | (yok — local aggregation) | — |

### Phase 9 — Reporting
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| monthly-report | (yok — local aggregation) | `gsc__enhanced_search_analytics` (cross-check) |
| weekly-summary | (yok — local) | — |
| portfolio-overview | (yok — portfolio.json read) | — |
| portfolio-weekly-brief | (yok — local) | — |
| portfolio-monthly-roundup | (yok — local) | — |
| portfolio-task-heatmap | (yok — local) | — |
| portfolio-kpi-trend | (yok — gsc_performance read) | — |
| portfolio-heatmap | (yok — local) | — |

### Phase 11 — Production
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| new-blog | `ScraplingServer__bulk_stealthy_fetch` (R-08 SERP top-5), `dataforseo__on_page_content_parsing` (R-15 site verification), `dataforseo__dataforseo_labs_google_keyword_overview` | `Higgsfield__generate_image` (görsel) |
| revise-content | `ScraplingServer__fetch` (current page), `dataforseo__on_page_content_parsing`, `gsc__search_analytics` | — |
| generate-images | `Higgsfield__generate_image` | `Higgsfield__models_explore`, `Higgsfield__generate_video` |
| content-remediation | `dataforseo__on_page_content_parsing`, `gsc__search_analytics` | — |
| faq-optimization | `dataforseo__serp_organic_live_advanced`, `dataforseo__dataforseo_labs_google_serp_competitors` | `ScraplingServer__fetch` (rakip FAQ) |

### Phase 12 — Publishing + Specialized
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| indexing-ping | `gsc__submit_sitemap`, `gsc__index_inspect` | — |
| verify-indexing | `gsc__index_inspect` | `gsc__enhanced_search_analytics` |
| brand-onboarding | `ScraplingServer__fetch` (logo, color extraction), `dataforseo__domain_analytics_whois_overview` | `dataforseo__domain_analytics_technologies_domain_technologies` |
| mark-done | (yok — local) | — |
| monitoring-weekly | `gsc__enhanced_search_analytics` (weekly delta), `dataforseo__dataforseo_labs_google_historical_rank_overview` | — |

### Phase 13 — Governance Final
| Skill | Required MCPs | Optional MCPs |
|---|---|---|
| schema-validate | (yok — local) | — |
| glossary-audit | (yok — local) | — |
| load-context | (yok — local) | — |

### Toplam İstatistik
- **MCP kullanan skill:** ~30 / 43 (≈%70)
- **Local-only skill:** ~13 / 43 (drift-check, whats-next, reporting suite, governance final, mark-done, master-task-sync, internal-links, schema-audit)
- **Paralı MCP kullanan skill:** ~22 / 43 (DataForSEO + Scrapling + Higgsfield) — `budget` field şart
- **Sadece GSC MCP kullanan skill:** ~6 (free MCP, budget şart değil)

`scripts/budget/check_budget.py` her DataForSEO/Scrapling/Higgsfield çağrısında pre-flight kontrol yapar (§16.8).

---

## 17. Phase Roadmap

### Phase 0 — Manager Bootstrap (Foundation)
**Goal:** Manager dosya seti + repo iskeleti var.
**Deliverables:**
- `docs/SESSION_PROTOCOL.md`, `PHASE_STATUS.md`, `OPEN_QUESTIONS.md`, `DECISIONS.md`, `REFERENCE_INDEX.md`, `WORKER_PROMPTS.md`, `CONTEXT_LEDGER.md`, `ARCHITECTURE.md`, `GLOSSARY.md`, `WORKFLOWS.md`, `CONTRIBUTING.md`, `INSTALL.md`
- `README.md`, `LICENSE`, `.gitignore`, `.claude-plugin/plugin.json`
- Tüm dizin iskeletleri (§3 ağacına göre)
**Acceptance:** `tree` plugin repo'sunu çıkardığında §3 ile %100 örtüşüyor.

### Phase 1 — Schema Migration (Foundation)
**Goal:** 17+ schema eski repolardan taşınmış + cleanup + 3 yeni schema.
**Deliverables:**
- `schemas/` dolu (17 taşınan + 3 yeni: skill-frontmatter, workflow-run, project-memory)
- Her schema için `tests/schemas/{name}-fixture.json`
**Acceptance:** `python scripts/validation/validate_schema.py --all` PASS.

### Phase 2 — Rules + Templates Migration (Foundation)
**Goal:** 10+ rule dosyası + ~14 markdown template + 1 boş master.xlsx.
**Deliverables:**
- `rules/*.md` × 10 (eski universal-rules.json parsed)
- `templates/reports/*.template.md` × 10
- `templates/project/*.template.*` × 3
- `templates/master-excel.xlsx` (18 sheet, formül yok)
**Acceptance:** `bootstrap_excel.py` çalıştırınca 18 sheet'lik geçerli xlsx üretiyor.

### Phase 3 — Core Scripts (Foundation)
**Goal:** Excel + state + validation + budget script'leri.
**Deliverables:**
- `scripts/excel/` (transaction, sheet_resolver, validate_master, backup, bootstrap_excel)
- `scripts/state/` (append_event, workflow_runner, resume)
- `scripts/validation/` (validate_schema, validate_invariants, drift_report)
- `scripts/budget/check_budget.py` (yeni)
- `scripts/security/check_secrets.sh` (taşıma)
- `scripts/migrations/README.md`
**Acceptance:** Test suite PASS; transaction.py ile manual write + invariant check çalışıyor.

### Phase 4 — Hooks + Commands (Foundation)
**Goal:** Plugin Claude Code'da yüklenebilir, hook'lar çalışıyor.
**Deliverables:**
- `hooks/` × 4 (session-start, pre/post-tool-use, user-prompt-submit)
- `commands/*.md` × 6 (pseo-status, init, quickwin, monthly, driftcheck, active)
- `.claude-plugin/plugin.json` final
**Acceptance:** Claude Code plugin'i yüklüyor, `/pseo-status` çalışıyor.

---

### Phase 5 — Critical Path Skills (5 skill, paralel) ⭐ GO/NO-GO GATEWAY
**Goal:** init-project, sf-import, quick-wins, drift-check, whats-next çalışıyor.
**Dispatch:** 5 paralel worker (her biri 1 skill).
**Acceptance:**
- Pilot proje (örn {slug}) end-to-end smoke test PASS
- events.jsonl tutarlı
- drift-check GREEN
- §11.2 detay protokolüne uygun çalışma
**Bu phase v1'in "go/no-go" gateway'i.** Geçemezse foundation'a geri dönülür.

### Phase 6 — Ingestion Suite (3 skill, paralel)
**Goal:** gsc-pull, dfs-pull, scrapling-ops.
**Dispatch:** 3 paralel worker.
**Constraints:** §16.5 MCP integration pattern'ine uyum zorunlu; §16.8 budget disiplini.
**Acceptance:** Her ingestion skill için inbox/{source}/'a JSON, master.xlsx ilgili sheet'lere literal write, events.jsonl log.

### Phase 7 — Discovery Suite (8 skill, paralel)
**Goal:** cannibalization, content-decay, tech-audit, on-page-audit, content-gaps, schema-audit, competitive-analysis, geo-analysis.
**Dispatch:** 4-8 paralel worker.
**Acceptance:** Her skill kendi sheet'ine doğru data yazıyor, invariant violations yok, drift-check GREEN.

### Phase 8 — Planning Suite (5 skill, paralel)
**Goal:** cluster-map, topical-map, new-content-plan, internal-links, master-task-sync.
**Dispatch:** 5 paralel worker.
**Acceptance:** master_task sheet otorite olarak güncel; CSR F-06, F-09, D-01, D-02 PASS.

### Phase 9 — Reporting Suite (8 skill, paralel)
**Goal:** monthly-report + weekly-summary + 6× portfolio-*.
**Dispatch:** 4-8 paralel worker.
**Acceptance:** outputs/reports/'a doğru template'lerde markdown raporlar; portfolio.json data tutarlı.

### Phase 10 — Content Rules Processing (transformation)
**Goal:** `docs/superpowers/specs/2026-04-30-content-rules-input.md` → `rules/content-*.md` + `templates/content/*` dönüşümü.
**Deliverables:**
- `rules/content-quality.md` (universal kurallar)
- `rules/content-html-discipline.md` (semantic HTML, CSS, kurumsal renk)
- `rules/content-seo-discipline.md` (linking, FAQ, keywords, intent, AEO/GEO)
- `templates/content/new-blog.template.md` (skeleton)
- `templates/content/new-blog.template.html` (kurumsal CSS slot'lı)
- `templates/content/revision.template.md`
- `templates/content/faq-block.template.html` (snippet-friendly)
**Dispatch:** 1 worker, dikkatli (production skill'lerini şekillendiriyor).
**Acceptance:** Tüm ~26 content rule kayıt altında; v1.3 production skill'leri için açık sözleşme; user review approval.

### Phase 11 — Production Suite (5 skill, paralel)
**Goal:** new-blog, revise-content, generate-images, content-remediation, faq-optimization.
**Dispatch:** 5 paralel worker.
**Constraints:** Phase 10'un çıktılarını consume etmek ZORUNDA.
**Acceptance:** new-blog ile 1 test blog yazımı, content rules check passed:
- HTML semantic ✓
- FAQ snippet-friendly (10 adet) ✓
- Internal links count (~her 300 kelimede 1, dupe yok) ✓
- Liste/tablo (her 1000 kelimede 1+1) ✓
- Bold disiplin (her 250 kelimede 1) ✓
- Başlıklarda `:` `-` yok ✓
- "Sonuç" başlığı yok ✓
- CTA mevcut ✓
- Scrapling SERP top-5 analizi yapılmış ✓

### Phase 12 — Publishing + Specialized (6 skill, paralel)
**Goal:** indexing-ping, verify-indexing, aio-competitor-map, brand-onboarding, mark-done, monitoring-weekly.
**Dispatch:** 6 paralel worker.
**Acceptance:** Her biri kendi acceptance test'i ile.

### Phase 13 — Governance Final (3 skill)
**Goal:** schema-validate, glossary-audit, load-context (hook helper).
**Dispatch:** 3 paralel worker.
**Acceptance:** CI pipeline'da bu 3 skill'in karşılığı işliyor; drift-check + schema-validate + glossary-audit zinciri tek komutla koşturuluyor.

### Phase 14 — Workspace + CI + Pilot End-to-End
**Goal:** Workspace repo açılır, CI tam pipeline'la çalışır, pilot proje ({slug}) baştan sona test edilir.
**Deliverables:**
- `platinum-seo-workspace/` repo (yeni GitHub)
- `.github/workflows/ci.yml` (7 check)
- Pilot proje end-to-end smoke test (init → ingest → discovery → planning → reporting → production → verify)
**Acceptance:** §18'deki tüm v1 acceptance criteria PASS.

---

## 18. v1 Acceptance Criteria

v1 release için TÜM şunlar geçmeli:

1. ✅ Plugin Claude Code'da yükleniyor.
2. ✅ ~43 skill çalışıyor (her kategori için en az 1 happy path test edilmiş).
3. ✅ 6 command (/pseo-*) çalışıyor.
4. ✅ 4 hook (session-start, pre/post-tool-use, user-prompt) tetikleniyor.
5. ✅ 20+ schema validation PASS (17 taşınan + 3 yeni).
6. ✅ Content rules input doc tamamen işlenmiş (Phase 10): rules/content-*.md + templates/content/*.
7. ✅ Pilot proje (örn {slug}) end-to-end:
   - init-project ile açıldı
   - SF + GSC + DataForSEO data ingest edildi (Phase 5+6)
   - Discovery suite çalıştırıldı (quick-wins, cannibalization, decay, tech-audit, on-page-audit, schema-audit, content-gaps, competitive-analysis, geo-analysis)
   - Planning suite çalıştırıldı (cluster-map, topical-map, new-content-plan, internal-links, master-task-sync)
   - Reporting suite çalıştırıldı (monthly-report + weekly + portfolio-*)
   - Production: en az 1 test blog (new-blog) — content rules check PASS
   - Publishing: indexing-ping → verify-indexing zinciri çalışıyor
   - drift-check temiz GREEN
   - whats-next priority list doğru
8. ✅ CI pipeline 7 check PASS.
9. ✅ events.jsonl'de tüm aktiviteler logged.
10. ✅ master.xlsx invariant check temiz (20 CSR rule).
11. ✅ docs (ARCHITECTURE, GLOSSARY, WORKFLOWS) güncel; phase status doğru.
12. ✅ Workspace repo açılmış, .env.example doğru, init-project ile yeni proje eklenebiliyor.
13. ✅ Budget guardrail çalışıyor (DataForSEO çağrısı bütçeyi aşmıyor).

---

## 19. Açık Sorular (Fresh Session İlk Phase'de Karar Verecek)

- **Q-001:** Plugin repo'su `~/Documents/platinum-seo-workflow-os/` (mevcut cwd) içinde mi açılsın yoksa yeni `~/Documents/platinum-seo-engine/` directory'si mi yaratılsın? (Öneri: yeni directory, eski cwd taşınır.)
- **Q-002:** GitHub repo açma timing'i: Phase 0 sonu mu, Phase 10'da mı? (Öneri: Phase 0 sonu, böylece her phase commit'leniyor.)
- **Q-003:** Pilot proje hangisi? (Öneri: workspace tarafından seçilir; eski premium'da en olgun klasöre sahip pilot. RESOLVED → ADR-003)
- **Q-004:** Eski `platinum-seo-core` ve `platinum-premium-seo` ne zaman silinecek? (Öneri: v1 acceptance sonrası, bir hafta soak süre.)
- **Q-005:** Workspace repo'su açma timing'i: Phase 0 mı Phase 10 mu? (Öneri: Phase 10'da, çünkü plugin önce bitmeli.)

---

## 20. Glossary (Spec İçi Hızlı Referans)

- **Plugin:** `platinum-seo-engine` repo'su
- **Workspace:** `platinum-seo-workspace` repo'su
- **Skill:** Doğal dil ile tetiklenen yetenek (markdown)
- **Command:** Slash ile tetiklenen kısayol
- **Hook:** Olay tetikli script (session-start, tool-use vs)
- **Workflow:** Multi-step bir skill'in çalışma süreci (workflow-run JSON ile state)
- **Manager Session:** Karar verici session (kod yazmaz, plan yapar, worker yönlendirir)
- **Worker Session:** Manager tarafından dispatch edilen, dar scope'lu session
- **Drift:** Schema, glossary, catalog ve gerçek state arasındaki tutarsızlık
- **Invariant:** Cross-sheet rule, master.xlsx içi sheet'ler arası kural
- **Pilot Proje:** v1 acceptance test'i için kullanılan proje (workspace tarafından seçilir, ADR-003 RESOLVED)
- **Phase:** Roadmap'teki tek bir adım, kendi acceptance kriteri olan iş paketi
- **ADR:** Architecture Decision Record, DECISIONS.md'de bir karar entry'si

---

## 21. Spec Self-Review Notes

Bu spec için yazar (manager session) self-review:

✅ **Placeholder scan:** Hiçbir TBD/TODO yok.
✅ **Internal consistency:** §3 plugin tree ile §15 migration listesi tutarlı; §11 v1 catalog ile §17 phase 5-9 tutarlı.
✅ **Scope check:** Tek bir spec için OK — plugin v1'i kapsıyor; workspace ayrı (§4'te belirtildi).
✅ **Ambiguity:** Q-001 açık ama §19'da "öneri" var, fresh session karar verecek.

---

## 22. Sonraki Adım

Bu spec onaylandı. Fresh session bunu okuyup **Phase 0**'dan başlar.

**İlgili dokümanlar:**
- Bootstrap prompt: `docs/superpowers/specs/2026-04-30-platinum-seo-engine-bootstrap-prompt.md`
- Content rules input (Phase 10 zorunlu okuma): `docs/superpowers/specs/2026-04-30-content-rules-input.md`

---

## 23. Content Rules Input (Phase 10 Reference)

`docs/superpowers/specs/2026-04-30-content-rules-input.md` dosyası:
- Kullanıcının (2026-04-30) verdiği ~26 content rule
- Phase 10 worker tarafından `rules/content-*.md` ve `templates/content/*` dosyalarına dönüştürülür
- Phase 11 production skill'leri (new-blog, revise-content) bu rules/templates'i consume eder

**Phase 10'a geçmeden önce fresh session bu dosyayı baştan sona okur.** Diğer phase'lerde okumaz.

---

## 24. Autonomous System Considerations

**Hedef:** Kullanıcı sadece yazsın, sistem arka planda kendi kendine çalışsın, en iyi senaryoyu sunsun.

Bu hedef için 5 mekanizma:

### 24.1 Scheduled Execution (v1, Phase 5+)

Her skill frontmatter'ında `triggers.scheduled` alanı var (§9). Cron syntax + mode:

```yaml
triggers:
  scheduled:
    - cron: "0 9 * * 1"       # her Pazartesi 09:00 UTC
      mode: "report-only"     # auto-execute yapma, rapor üret
    - cron: "0 9 1 * *"       # her ay 1'i 09:00 UTC
      mode: "auto-execute"    # otomatik koş (sadece safe_auto_execute=true ise)
```

**Implementasyon:**
- Plugin **kendi cron daemon'u yazmıyor**. `mcp__scheduled-tasks__create_scheduled_task` ile entegre olur.
- Plugin'de `scripts/scheduling/sync_schedules.py` skript'i: tüm skill'lerin scheduled trigger'larını okur, scheduled-tasks MCP'ye senkronize eder.
- `/pseo-schedule-sync` command'ı manuel sync için.

**Önerilen Default Schedule'lar (per-project tercih):**
| Skill | Frequency | Mode |
|---|---|---|
| drift-check | daily 07:00 | report-only |
| quick-wins | weekly Mon 09:00 | report-only |
| content-decay | weekly Mon 09:00 | report-only |
| monthly-report | monthly 1st 09:00 | report-only |
| portfolio-weekly-brief | weekly Mon 08:00 | report-only |
| schema-validate | on-commit (CI) | auto-execute |

### 24.2 Proactive Surfacing (v1, Phase 4 — `user-prompt-submit` hook)

Her kullanıcı prompt'undan ÖNCE `user-prompt-submit` hook çalışır:
1. Aktif projenin `_state/` dizinini tara
2. Son 7 günde `report-only` mode'da koşmuş scheduled run'ların raporlarını oku
3. RED/CRITICAL bulgular varsa kullanıcı prompt'una **kısa bir uyarı bloğu enjekte et**:

```markdown
[SISTEM NOTU]
🔴 {slug}: 3 RED drift bulgusu var (drift-check 2026-04-30 09:00)
🟠 vento: 12 yeni quick win onayı bekliyor
🟢 eykom: tüm sistemler temiz
```

- Hook script'i: `scripts/state/proactive_surface.py`
- 200 token sınırı (kullanıcı prompt'unu boğmasın)

### 24.3 Confidence-Based Routing (v1, frontmatter `autonomy.confidence`)

Her skill çıktısı bir confidence label'ı taşır:
- **HIGH:** GSC built-in detection (quick-wins'in `gsc__detect_quick_wins`'i), schema-validate, drift-check pass
- **MEDIUM:** DataForSEO scoring, content-decay 90d trend
- **LOW:** Scrapling competitive analysis, AIO mention prediction, geo-analysis (LLM-based)

**Kullanım:**
- `whats-next` skill'i HIGH confidence öğeleri en üste alır
- Scheduled runs sadece HIGH confidence sonuçları otomatik master.xlsx'e yazar
- MEDIUM/LOW her zaman approval gate'ten geçer

### 24.4 Safe Auto-Execute Allowlist (v1.1+, frontmatter `autonomy.safe_auto_execute`)

Bazı skill'ler approval gerektirmeden koşabilir (read-only veya geri-alınabilir):

**Safe (auto-execute OK):**
- drift-check (sadece rapor üretir)
- monthly-report (sadece markdown üretir)
- gsc-pull, dfs-pull (inbox'a yazar)
- portfolio-* reporting (sadece raporlar)

**Unsafe (her zaman approval gerekli):**
- new-blog (içerik yayını sayılır)
- indexing-ping (Google'a public action)
- master-task-sync (master_task'a yeni satır ekler)
- init-project (yeni proje pack'i kalıcı)

v1'de **approval default = true**. v1.1'de safe allowlist genişletilir.

### 24.5 Outcome Verification Loop (v1.1+, yeni skill: `verify-outcome`)

Şu an plan: bu skill v1.1'de eklenecek. Görevi:
1. Past quick-wins (30+ gün önce işlemli) için GSC current position çek
2. Beklenen pozisyon değişimini gerçekleşenle karşılaştır
3. Quick win scoring model'inin doğruluğunu raporla
4. content-decay action'larının gerçekten decay'i durdurup durdurmadığını ölç
5. master.xlsx [completed_work]'e `outcome_verified` ve `outcome_score` ekle

**v1'de bu YOKKEN:** events.jsonl tüm aktiviteleri saklıyor, manual analiz mümkün.

### 24.6 v1 Otonomi Acceptance

v1 release'i otonom mode için aşağıdakiler ÇALIŞIR:
- ✅ Scheduled execution (drift-check, monthly-report, content-decay weekly)
- ✅ Proactive surfacing (user-prompt-submit hook)
- ✅ Confidence labels (her skill outputu)
- ✅ Approval gates her unsafe action'da
- ⏳ Safe auto-execute (v1.1 — şimdilik tüm skill'ler approval ister)
- ⏳ Outcome verification (v1.1 — yeni skill)

**Yani v1'de "otonom" = "scheduled + proactive + confidence-aware". v1.1'de "auto-execute + verify-outcome" eklenince **tam autopilot** moduna geçer.**

---
