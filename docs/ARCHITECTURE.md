# Architecture — Platinum SEO Engine

> **Authority:** Spec (`docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md`) is the frozen authoritative input. This doc is the **living summary** for human readers. When in doubt, the spec wins; this doc is updated to match.

---

## Vision

`platinum-seo-engine` bir **Claude Code plugin sistemi**dir; SEO operasyonunu skills/commands/hooks ile orkestre eder, JSON schema'larla veri şekillerini kilitler, Excel + JSONL ile state tutar, her workflow'u resume/retry/approval gate'leriyle yönetir, drift-check ile kendini denetler. **Az kod + sıkı kural + tek otorite + makine-okunur sözleşme** ilkesiyle proje-agnostik çalışır.

---

## Two-Repo Strategy

İki ayrı repo, net sözleşme:

| Repo | Sorumluluk | İçerir | İçermez |
|---|---|---|---|
| `platinum-seo-engine` (Plugin) | Logic, kurallar, aletler. Proje-agnostik. | skills, commands, hooks, scripts, schemas, BOŞ templates, rules, docs, tests | Proje isimleri, proje verisi, state, output |
| `platinum-seo-workspace` (Workspace) | Proje verisi, state, output, raw data | projects/{slug}/, shared/, _archive/, .claude/, .env | Hiçbir logic kodu, skill markdown'ı |

**Sözleşme:**
- Plugin workspace yapısını **okur**, workspace state'ini **günceller**.
- Workspace plugin'in varlığından habersiz (config dışında).
- Plugin yolu workspace'e **CWD detection** + `.env`'deki `PSEO_WORKSPACE_ROOT` (canonical, ADR-035; `PSE_WORKSPACE_PATH` 1-yıl deprecated alias) ile bulunur.
- Versionlama: Plugin SemVer (`plugin.json`); workspace proje config'leri `plugin_version_constraint` taşır.

---

## 10 Disciplines (Pazarlık Edilemez)

Her biri `rules/*.md`'de tanımlı; drift-check ve CI otomatik denetler.

| # | Disiplin | Özet |
|---|---|---|
| 1 | Single Source of Truth | Bir terim/schema/kural TEK YERde tanımlanır; başka yerden referans verilir |
| 2 | Schema-First | Veri yazılmadan ÖNCE `schemas/*.schema.json` olmak zorunda |
| 3 | Plugin = Proje-Agnostik | Plugin repo'da proje adı (demo-dental, demo-furniture) GEÇMEZ; CI grep ile denetler |
| 4 | State Append-Only | `events.jsonl` ve `workflows/{run_id}.json` silinmez/üzerine yazılmaz |
| 5 | Excel Atomic Writes | master.xlsx **SADECE** `scripts/excel/transaction.py` ile yazılır; backup + invariant zorunlu |
| 6 | Naming | Slug/skill/file kebab-case; sheet/Python snake_case; run ID `{slug}-{date}-{uuid}` |
| 7 | Secrets Management | API key repo'ya commit edilmez; `.env` veya keychain; pre-commit script |
| 8 | Glossary Discipline | Her teknik terim `docs/GLOSSARY.md`'de olmalı; eksikse `glossary-audit` AMBER |
| 9 | Skill Description Discipline | Her skill frontmatter'ı `skill-frontmatter.schema.json`'a uyar |
| 10 | Time Discipline | Tüm timestamp UTC ISO 8601; rapor sunumu Europe/Istanbul'a çevrilir |

> Bonus disiplin (8.11): **Schema Versioning** — schema bump'ta `scripts/migrations/` script'i zorunlu.

---

## Phase Roadmap (High-Level)

| Phase | Ad | Durum | Skill Sayısı |
|---|---|---|---|
| 0 | Manager Bootstrap | tamamlandı ✅ | — |
| 1 | Schema Migration | tamamlandı ✅ | — |
| 2 | Rules + Templates Migration | tamamlandı ✅ | — |
| 3 | Core Scripts | tamamlandı ✅ | — |
| 4 | Hooks + Commands | tamamlandı ✅ | — |
| 5 | Critical Path Skills (GO/NO-GO gateway) | tamamlandı ✅ | 5 |
| 6 | Ingestion Suite | tamamlandı ✅ | 3 |
| 7 | Discovery Suite | tamamlandı ✅ | 8 |
| 8 | Planning Suite | tamamlandı ✅ | 5 |
| 9 | Reporting Suite | tamamlandı ✅ | 8 |
| 10 | Content Rules Processing | tamamlandı ✅ | — |
| 11 | Production Suite | tamamlandı ✅ | 5 |
| 12 | Publishing + Specialized | tamamlandı ✅ | 6 |
| 13 | Governance Final | tamamlandı ✅ | 3 |
| 14 | Workspace + CI + Pilot End-to-End | devam ediyor 🚧 | — |

**Toplam ~45 skill** (45 SKILL.md filesystem SoT), 9 batch phase'e yayılmış (v1.7'de +1 gbp-audit; v1.8'de +1 sf-crawl-orchestrator). **Güncel durum (engine v1.9.4): Phase 0–13 tamamlandı; Phase 14 (workspace + CI + pilot E2E) devam ediyor.** Foundation (Phase 0–4) skill phase'lerinden önce tamamlandı; Phase 5 **GO/NO-GO gateway** geçildi.

---

## v1 Acceptance Criteria

v1 release için TÜM şunlar geçmeli:

1. Plugin Claude Code'da yükleniyor.
2. ~45 skill çalışıyor (her kategori için en az 1 happy-path test).
3. 6 command (`/pseo-*`) çalışıyor.
4. 4 hook (session-start, pre/post-tool-use, user-prompt-submit) tetikleniyor.
5. 20+ schema validation PASS (17 taşınan + 3 yeni).
6. Content rules input doc tamamen işlenmiş (Phase 10).
7. Pilot proje (demo-dental) end-to-end: init → ingest → discovery → planning → reporting → production → publishing zinciri çalışıyor; drift-check GREEN; whats-next priority list doğru.
8. CI pipeline 7 check PASS.
9. `events.jsonl`'de tüm aktiviteler logged.
10. master.xlsx invariant check temiz (20 CSR rule).
11. docs (ARCHITECTURE, GLOSSARY, WORKFLOWS) güncel; phase status doğru.
12. Workspace repo açılmış, `.env.example` doğru, init-project ile yeni proje eklenebiliyor.
13. Budget guardrail çalışıyor (DataForSEO çağrısı bütçeyi aşmıyor).

---

## Authority Hierarchy

1. **Spec** (`docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md`) — frozen authoritative input. Tüm kararların kaynağı.
2. **DECISIONS.md** (ADR'ler) — spec'i tamamlayan, append-only mimari kararlar.
3. **ARCHITECTURE.md** (this file) — yaşayan insan-okunur özet. Spec ile çatışırsa **spec wins**; bu doc güncellenir.
4. **PHASE_STATUS.md / OPEN_QUESTIONS.md / WORKFLOWS.md** — operasyonel yaşayan durum dosyaları.

> Spec'i değiştirme yetkisi yalnızca manager session'da; değişiklik teklifleri `OPEN_QUESTIONS.md` üzerinden ADR'ye dönüşür.

---

## §7. SF Reports Pipeline

**v1.8+ supports MCP-primary** (orchestrator iterates 24-report export) + **file-based fallback** (disaster recovery).

| Path | When | Trigger | Authority |
|------|------|---------|-----------|
| **MCP-primary** (v1.8+) | SF GUI open + MCP Server running | `/pseo-sf-crawl <slug> <url>` | sf-crawl-orchestrator skill (8 DURURs + atomic semantics D-SF-16) |
| **File-drop fallback** | SF MCP unavailable or operator manual workflow | Manual CSV drop to `projects/{slug}/sf-exports/{date}/raw/` → sf-import | sf-import 8-step protocol UNCHANGED (D-SF-07) |

### Tier classification (24 reports cumulative)

- **Tier 1 (14 mandatory)** — RED FAIL if missing during orchestrator run. Examples: internal_all, all_inlinks, response_codes_all, structured_data_all, sitemaps_all.
- **Tier 2 (10 recommended)** — AMBER if missing during orchestrator run; sf-import 8-step protocol still proceeds. Examples: h2_all, images_all, hreflang_all, near_duplicates_report.
- **Tier 3 (16 optional)** — Excluded by default per Q-SF-MCP-10 (orchestrator default = 24 reports); v1.1+ scope based on operator use-case justification.

### Atomic crawl semantics (D-SF-16)

All-or-nothing per crawl via temp staging dir `_state/staging/sf-crawl-{run_id}/` → atomic mv on success / rm -rf on Tier 1 fail. Prevents sf-import partial-projection state. Resume capability: `workflow_runner.pause/resume` API survives mid-loop crash (temp staging preserved + idempotent report skip on resume).

### Master.xlsx projection unchanged

sf-import projects to 6 sheets (`crawl_sitemap`, `inlinks`, `outlinks`, `redirects`, `tech_seo`, `schema`) regardless of MCP-primary or file-drop path. Excel atomic writes via `transaction.py` (Discipline #5).

---

## §16.5 MCP Discipline

**v1.8+ 4 MCP servers** (3 stdio + 1 HTTP):

| Server | Transport | Source | Required? |
|--------|-----------|--------|-----------|
| `gsc` | stdio (npx mcp-server-gsc@0.3.0) | Google Search Console | YES (gsc-pull skill backbone) |
| `dataforseo` | stdio (npx dataforseo-mcp-server@2.8.10) | DataForSEO API | YES (dfs-pull + paid budget tracked) |
| `ScraplingServer` | stdio (`${SCRAPLING_BIN:-scrapling}` mcp) | Scrapling library | OPTIONAL (scrapling-ops skill) |
| `sf` (v1.8 NEW) | HTTP (`http://127.0.0.1:11435/mcp`) | Screaming Frog 24 native MCP | OPTIONAL (sf-crawl-orchestrator skill) |

### HTTP transport requirements (sf only)

- `endpoint_url` in mcp-tool-registry instance (v1.8 Phase 1 `runtime` enum already supports `http` per `schemas/mcp-tool-registry.schema.json:47-51` — no schema change needed).
- Reusable HTTP MCP client `scripts/util/sf_mcp_client.py` (D-SF-14): 3-retry exp backoff (1s/2s) + 100KB response cap (D-SF-05) + JSON-RPC envelope discipline + 307 redirect POST preservation (RFC 7231).
- `mcp-tool-registry.json` instance file now exists at repo root (Q-SF-MCP-09 default) — first instance for all 4 servers (was schema-only pre-v1.8).

### F-23 cross-sheet invariant (v1.8 Phase 4)

`sf-crawl-orchestrator` run detected in workflow_runner → `mcp-tool-registry.json` MUST have `sf` entry. Severity=HIGH. Catches drift where operator added SF MCP server but forgot to update registry (or vice versa).

### F-16 invariant baseline reset

`.mcp.json` byte-byte invariant (47+ commits since v1.5) **intentionally broken** at v1.8 Phase 2 per ADR-039. New baseline: 543B (was 482B); new md5 `93523d41e14f90916fefb86d346bd702`. Future F-16 drift catches resume from new baseline post-v1.8 release.

### Plugin manifest counts (v1.8+)

- 45 SKILL.md files (was 44 pre-v1.8; +1 sf-crawl-orchestrator)
- 18 commands/*.md files (was 16 pre-v1.8; +2 pseo-sf-crawl + pseo-sf-status)
- 6 hooks (UNCHANGED; Q-SF-MCP-08 RESOLVED → NO; stop_validation.py perf budget intact)
- 4 MCP servers (was 3; +sf HTTP)
