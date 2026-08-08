---
description: |
  Use when: kullanıcı "verileri freshle", "veri tazele", "GSC SF DFS yenile", "master excel yenile", "tüm veriyi güncelle", "pillar cluster kontrol et", "aktif taskları revize et", "adstark taskları güncelle", "refresh audit" der ya da `/pseo-refresh [project-slug] [days_back]` çağırırsa.
  Also use when: aktif proje için çok-kaynaklı bir bakım dizisi (GSC + SF + DFS + Scrapling append-only tazeleme → pillar/cluster + drift denetimi → adstark↔master task mutabakatı) baştan sona koşturulacak; aynı dizi birden çok projede tekrar kullanılacak (slug shared/active.json'dan çözülür).
  Do not use when: tek bir ingestion kaynağı yeter (`/pseo-gsc-pull`, `/pseo-sf-crawl`, `/pseo-dfs-pull`, `/pseo-scrape`); yalnız rapor (`/pseo-monthly`); yalnız drift (`/pseo-driftcheck`); yalnız master_task toplama (`/pseo-master-task-sync`); içerik üretimi/publish/indexing (bu komut SEO tarafında ANALİZ-ONLY).
argument-hint: "[project-slug] [days_back] [--apply-tasks] [--dry-run]"
allowed-tools: Bash(jq:*), Read
model: sonnet
---

# /pseo-refresh — Veri tazeleme + pillar/cluster denetim + adstark↔master task mutabakatı

> **Skill:** `skills/ingestion/refresh-audit/SKILL.md`. GSC + SF + DFS + Scrapling
> append-only tazeleme (transaction.py backup) → pillar/cluster + cross-sheet invariant
> denetimi → master_task SSoT → adstark↔master task mutabakatı → tek birleşik rapor.
> SEO tarafı publish/index/remediation YAPMAZ; task fazı default **propose-only**.

## 1. Aktif projeyi çöz

`$1` verilmişse onu kullan; yoksa session binding → `shared/active.json`:

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — önce /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

- `PROJECT` boşsa: `/pseo-active <slug>` öner, DUR (DURUR #3). Çözülen slug'ı **teyit et**.
- `$2` verilmişse `days_back`; yoksa skill default `90`.
- `--apply-tasks` bayrağı varsa `apply_task_changes=true` (yalnız `/pseo-approve` consent'i varsa uygulanır); yoksa task fazı propose-only.
- `--dry-run` bayrağı varsa `dry_run=true` — TÜM fazlar salt-okunur, hiçbir yazım yok (tam prova). "Önce incele" için ideal.

## 2. Skill orkestrasyonu (`refresh-audit`) — 10 faz

1. **Faz 0 Preflight** — aktif proje (session binding öncelikli) + **eşzamanlılık kilidi** + config + bütçe + **staleness atlama** + kaynak erişimi + resume; master.xlsx yoksa DUR.
2. **Faz 1 GSC** → `gsc-pull` (son `${2:-90}` gün recent + previous, append-only).
3. **Faz 2 SF** → `sf-crawl-orchestrator` — **TAM 24 RAPOR ZORUNLU** (subset yasak) / kapalıysa `sf-import` tam export.
4. **Faz 3 DFS** → `dfs-pull` — **EKSİKSİZ** (ranked_keywords tam sayfalama, truncate YOK; bütçe aşarsa uyar+devam, oversized→consent).
5. **Faz 4 Scrapling** → `scrapling-ops` (pillar + top-20 cluster + top-5 rakip canlı fetch).
6. **Faz 5 TAM audit suite** → tech-audit + robots + hreflang + facet + on-page + schema + topical-map + cluster-map + internal-links + competitive-analysis + cannibalization(zorunlu) + content-decay + content-gaps + **gbp-audit** (local ise) + **geo-analysis/aio-competitor-map** (AI-search) → **pillar konu-otorite haritası** (ANALİZ-ONLY).
7. **Faz 6 master_task SSoT** → `master-task-sync` (auto satır toplama).
8. **Faz 7 Task mutabakatı + GÜN DAĞITIMI** → adstark ↔ master diff; **dual-write · reschedule · SEO-değer filtresi · açıklama şablonu · `tasks_per_day` ile boş günlere dengeli yayma** (yığılma yasak). Default propose-only → DIFF + gün-planı sun + `/pseo-approve` bekle.
9. **Faz 8 Drift** → `drift-check` (validate_invariants.py + validate_schema.py).
10. **Faz 9 QA + COMPLETENESS gate + self-check + coverage** → zorunlu adım checklist'i (SF 24/24, DFS tam, cannibalization+topical koştu); master'ı yeniden okuyup teyit; `_state/coverage/{run_id}.json`.
11. **Faz 10 Rapor** → completeness durumu + anomali/delta alarmı (HIGH) + konu-otorite haritası + gün-dağıtım takvimi + `outputs/reports/{date}-refresh-audit.md` + `whats-next`; **kilidi bırak**.

## 3. Değişmezler (skill enforce eder)

- **Ham `master.xlsx` yazımı YOK** — tüm sheet yazımları alt skill'ler üzerinden `scripts/excel/transaction.py` (backup + lock + schema-validate + provenance).
- **SEO tarafı ANALİZ-ONLY** — git push / GSC submit / Indexing / publish / retire / robots deploy YAPMAZ.
- **Task fazı önce-öner-sonra-uygula** — dual-write (adstark + master), taşıma = reschedule (`update_task`/`move_task`, kopya YASAK), consent olmadan yazmaz.
- **No-fabrication** — boş/hatalı MCP yanıtında sayı uydurma, "N/A + sebep" yaz.
- Bir kaynağın FAIL'i diğerlerini durdurmaz (flag + devam); 3. denemede escalate (qa-loop).

## 4. Bağımlılıklar

- `skills/ingestion/refresh-audit/SKILL.md` — orkestratör
- Delege skill'ler: `gsc-pull`, `sf-crawl-orchestrator`/`sf-import`, `dfs-pull`, `scrapling-ops`, `cluster-map`, `cannibalization`, `content-decay`, `internal-links`, `content-gaps`, `master-task-sync`, `drift-check`
- MCP (skill-level): gsc + sf + dataforseo + ScraplingServer + **adstark** (task mutabakatı)
- `shared/active.json` + `shared/sessions/<id>.json` (binding) — aktif proje; `PSEO_WORKSPACE_ROOT` env
- Skill defaults: `days_back=90`, `refresh_sources=["gsc","sf","dfs","scrapling"]`, `audit_depth="full"`, `reconcile_tasks=true`, `apply_task_changes=false`, `tasks_per_day=4`, `dry_run=false`, `staleness_hours=20`
