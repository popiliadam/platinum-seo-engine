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
- Plugin yolu workspace'e **CWD detection** + `.env`'deki `PSE_WORKSPACE_PATH` ile bulunur.
- Versionlama: Plugin SemVer (`plugin.json`); workspace proje config'leri `plugin_version_constraint` taşır.

---

## 10 Disciplines (Pazarlık Edilemez)

Her biri `rules/*.md`'de tanımlı; drift-check ve CI otomatik denetler.

| # | Disiplin | Özet |
|---|---|---|
| 1 | Single Source of Truth | Bir terim/schema/kural TEK YERde tanımlanır; başka yerden referans verilir |
| 2 | Schema-First | Veri yazılmadan ÖNCE `schemas/*.schema.json` olmak zorunda |
| 3 | Plugin = Proje-Agnostik | Plugin repo'da proje adı (dentnotion, vento) GEÇMEZ; CI grep ile denetler |
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
| 0 | Manager Bootstrap | **active** | — |
| 1 | Schema Migration | planned | — |
| 2 | Rules + Templates Migration | planned | — |
| 3 | Core Scripts | planned | — |
| 4 | Hooks + Commands | planned | — |
| 5 | Critical Path Skills (GO/NO-GO gateway) | planned | 5 |
| 6 | Ingestion Suite | planned | 3 |
| 7 | Discovery Suite | planned | 8 |
| 8 | Planning Suite | planned | 5 |
| 9 | Reporting Suite | planned | 8 |
| 10 | Content Rules Processing | planned | — |
| 11 | Production Suite | planned | 5 |
| 12 | Publishing + Specialized | planned | 6 |
| 13 | Governance Final | planned | 3 |
| 14 | Workspace + CI + Pilot End-to-End | planned | — |

**Toplam v1: ~43 skill**, 9 batch phase'e yayılmış. Foundation (Phase 0–4) tamamlanmadan skill phase'leri başlamaz. Phase 5 **GO/NO-GO gateway**: geçemezse foundation'a dönülür.

---

## v1 Acceptance Criteria

v1 release için TÜM şunlar geçmeli:

1. Plugin Claude Code'da yükleniyor.
2. ~43 skill çalışıyor (her kategori için en az 1 happy-path test).
3. 6 command (`/pseo-*`) çalışıyor.
4. 4 hook (session-start, pre/post-tool-use, user-prompt-submit) tetikleniyor.
5. 20+ schema validation PASS (17 taşınan + 3 yeni).
6. Content rules input doc tamamen işlenmiş (Phase 10).
7. Pilot proje (dentnotion) end-to-end: init → ingest → discovery → planning → reporting → production → publishing zinciri çalışıyor; drift-check GREEN; whats-next priority list doğru.
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
