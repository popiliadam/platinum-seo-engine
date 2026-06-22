# Competitive Content Engine (CCE) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every task. Steps use checkbox (`- [ ]`) syntax for tracking. Each worker session receives ONE batch prompt (B1/B2/B3) and works ONLY on that batch's files.

**Goal:** `new-blog` (sonra `revise-content`+`faq-optimization`) skill'lerinin ürettiği içeriğin her zaman ilk-10 organik rakipten ölçülebilir biçimde daha kaliteli çıkmasını garanti eden hibrit motor (kod-ölçer + Claude-yazar).

**Architecture:** 3 aşamalı döngü — (1) SİLAHLANMA: Claude MCP çağırır (Scrapling×10 + DFS + GSC) → ham JSON `inbox/`'a → saf Python transform'lar Brief Paketi üretir; (2) YAZIM: Claude Brief + craft rehberiyle içeriği yazar; (3) KAPI: saf Python `quality_gates` 8 kapı ölçer, geçmezse re-write. Spec: `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md`.

**Tech Stack:** Python 3.10+ (saf transform, openpyxl read-only, stdlib json), pytest (hermetik fixture testleri), BeautifulSoup (HTML parse — mevcut dependency), markdown content rules.

## Global Constraints (her batch'e uygulanır — spec'ten verbatim)

- **MCP boundary:** Python script'ler MCP ÇAĞIRMAZ. MCP'yi Claude (skill) çağırır → ham JSON `inbox/`'a yazar → script `--raw-*` CLI argümanıyla `json.load` eder. Script = argparse CLI + saf transform. (Pattern emsali: `scripts/ingestion/dfs_pull.py`.)
- **Pure transform disiplini:** import edilince side-effect YOK; dosya yazımı yalnız CLI'da; idempotent (same input → byte-identical output); no state mutation. (Emsal: `scripts/planning/new_content_plan_transform.py` docstring.)
- **Plugin-agnostik:** proje slug hardcode YASAK — `dentnotion`, `vento`, `eykom`, `bigcattr`, `calitte`, `lastiksa`, `noraninsaat`, `adstark` FORBIDDEN tokens (pytest grep verify). CSS class `pse-` prefix.
- **R-token:** yeni craft kuralları **mevcut max R-token'dan SONRA** başlar. `grep -rhoE 'R-[0-9]+' rules/ | sort -t- -k2 -n | tail -1` ile doğrula — şu an **R-148** → yeni kurallar **R-149+**. Mevcut R-01..R-148'e DOKUNMA (`project_template_r_token_resolution` dersi).
- **Test hermetik:** TDD (RED→GREEN). Canlı MCP YASAK — fixture JSON kullan. Testler `tests/scripts/` (script) veya `tests/rules/` (kural) altında.
- **Schema authority:** `master-excel.schema.json` + `events.schema.json`'a uy. `new_content_plan` allowed_writers=null → **F-1 READ-ONLY** (transaction.append/update/delete YASAK).
- **Provenance:** `scripts/state/events_writer` (`append_work`, `append_audit`) — IMPORT et, asla kopyalama.
- **Maliyet:** sınırsız (skill/MCP katmanında; saf script'leri etkilemez). Her içerik taze top-10 tarama; önbellek yok.
- **Handoff (worker → manager):** bitince manager'a döndür: (a) `git status --short` + `git diff --stat`, (b) pytest sonucu (pass/fail sayısı + komut), (c) oluşturulan/değişen dosya listesi, (d) açık sorular/sapmalar. **PUSH ETME** — manager doğrular + push eder. Branch: `main` (AMO standing-OK).

---

## Batch haritası (bağımlılık + paralellik)

| Batch | Faz | Worker prompt | Bağımlılık | Paralel? |
|---|---|---|---|---|
| **B1** | Silahlanma motoru | `cce/B1-silahlanma-motoru.md` | yok | ✅ B2,B3 ile paralel |
| **B2** | Kapı motoru | `cce/B2-kapi-motoru.md` | yok | ✅ B1,B3 ile paralel |
| **B3** | Craft rehberi (kurallar) | `cce/B3-craft-rehberi.md` | yok | ✅ B1,B2 ile paralel |
| **B4** | Orkestratör + SKILL.md | _(B1-B3 bitince yazılacak)_ | B1+B2+B3 | ❌ sıralı |
| **B5** | Gerçek konu kanıt testi | _(B4 bitince yazılacak)_ | B4 | ❌ sıralı |

**Çakışma analizi:** B1 → `scripts/production/*_transform.py` + `build_brief.py`; B2 → `scripts/production/quality_gates.py`; B3 → `rules/content-craft-discipline.md`. Üç batch **ayrı dosyalar** → paralel worker güvenli (AMO worktree-contention dersi: her worker yalnız kendi prompt'undaki dosyalara dokunur, full-suite yerine kendi scoped test dizinini doğrular).

**B4/B5 neden şimdi yazılmadı (YAGNI):** B4 orkestratör, B1-B3'ün ÜRETTİĞİ tam fonksiyon imzalarına bağlı. İmzalar worker'larca finalize edilince B4 promptu kesin yazılır (hayali imza riskini önler). B5 kanıt testi B4'e bağlı.

## Brief Paketi şeması (B1 üretir, B2+B4 tüketir — tek doğruluk kaynağı)

```json
{
  "schema_version": "1.0",
  "topic": { "primary_keyword": "str", "content_type": "guide|comparison|listicle|research|tutorial|review", "locale": "str", "market": "str" },
  "keyword_set": [ { "kw": "str", "volume": 0, "intent": "Informational|Commercial|Transactional|Navigational", "source": "dfs_suggestions|gsc" } ],
  "aio": { "present": true, "answer_points": ["str"], "cited_sources": ["url"] },
  "competitors": [ { "url": "str", "h2_h3": ["str"], "questions": ["str"], "entities": ["str"], "tables": 0, "lists": 0, "word_count": 0 } ],
  "gap": { "must_cover_headings": ["str"], "must_answer_questions": ["str"], "must_mention_entities": ["str"] },
  "structure_ceiling": { "tables": 0, "lists": 0, "h2": 0, "best_competitor_word_count": 0 },
  "gsc": { "real_queries": ["str"], "current_position": null },
  "generated_at": "ISO-8601-str"
}
```

Bu şema 3 batch'in **kontrat sınırıdır**: B1 bunu üretir, B2 `quality_gates` bunu okur, B4 orkestratör bunu pas geçer. Alan adları/tipleri batch'ler arası birebir aynı olmalı.
