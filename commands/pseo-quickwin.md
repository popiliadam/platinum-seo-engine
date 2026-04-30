---
description: |
  Use when: kullanıcı "quick win", "hızlı kazanım", "8-20 sıradaki keyword", "low-hanging fruit", "kolay yükselebilir sayfalar" der ya da `/pseo-quickwin` çağırırsa.
  Also use when: aktif projenin GSC verisi master.xlsx içinde mevcut; sıralamada eşik bandında olan sorgular için `gsc-pull` → `quick-wins` skill chain'i tetiklenmek isteniyor.
  Do not use when: yeni içerik planı (`new-content-plan`), içerik decay (`content-decay`), tech audit (`tech-audit`) ya da cannibalization analizi gerekiyor; bunlar ayrı skill'lerdir.
argument-hint: "[project-slug]"
allowed-tools: Bash(jq:*), Read
model: sonnet
---

# /pseo-quickwin — GSC Quick-Wins Chain (Phase 5 STUB)

> **Phase dependency:** Bu komut `skills/discovery/quick-wins/SKILL.md` ve `skills/ingestion/gsc-pull/SKILL.md` yazıldıktan sonra (Phase 5 + Phase 6) tam çalışır. Şu an STUB modunda — yalnızca routing önerisi üretir, skill'leri otomatik tetiklemez.

## 1. Aktif projeyi çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. Plan (Phase 5+ chain'i)

Phase 5/6 tamamlandığında bu komut şu zinciri tetikler:

1. **`gsc-pull`** (Phase 6 — `skills/ingestion/gsc-pull/SKILL.md`)
   - Son 90 gün GSC `searchAnalytics.query` verisini çek
   - master.xlsx `gsc_landing_query` logical sheet'ine `transaction.py` ile yaz
   - `events.jsonl`'e `gsc_pulled` event'i düş

2. **`quick-wins`** (Phase 5 — `skills/discovery/quick-wins/SKILL.md`)
   - GSC verisinden ortalama pozisyon 8–20 bandındaki sorguları filtrele
   - Impressions ≥ minimum eşik, CTR < benchmark
   - master.xlsx `quick_wins` logical sheet'ine yaz
   - Onay gate: `awaiting_approval` (workflow-run.schema)
   - Onay sonrası `outputs/reports/{date}-quick-wins.md` üret

## 3. STUB davranışı

Şu an: kullanıcıya yukarıdaki planı sun, "Phase 5/6 yazıldıktan sonra otomatik koşacak" not düş. Aktif projedeki master.xlsx'in `gsc_landing_query` sheet'inde veri var mı diye Read tool ile manuel kontrol önerilebilir.

## 4. Açık bağımlılıklar

- `skills/discovery/quick-wins/SKILL.md` — Phase 5
- `skills/ingestion/gsc-pull/SKILL.md` — Phase 6
- `mcp-tool-registry` GSC tool'ları (Phase 6)

Skill'ler yazıldığında bu komut body'si gerçek skill çağrılarıyla güncellenir; frontmatter (description, argument-hint) sabit kalır.
