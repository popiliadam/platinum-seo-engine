---
description: |
  Use when: kullanıcı "aylık rapor", "monthly report", "ay sonu özet", "geçen ay neler oldu", "ay raporu üret" der ya da `/pseo-monthly` çağırırsa.
  Also use when: bir ayın sonunda aktif proje için `outputs/reports/{YYYY-MM}-monthly.md` üretilecek; master.xlsx'te trafik/sıralama/içerik verileri ay boyunca toplanmış ve `monthly-report.schema.json` formatında özet rapor isteniyor.
  Do not use when: haftalık özet (`weekly-summary`), portföy genel raporu (`portfolio-overview`), drift kontrol veya tek-seferlik bir analiz isteniyorsa — bunların ayrı skill ve komutları vardır.
argument-hint: "[month=YYYY-MM] [project-slug]"
allowed-tools: Bash(python3:*), Bash(jq:*), Bash(date:*), Read
model: sonnet
---

# /pseo-monthly — Aylık Rapor Üretimi

> **Skill:** `skills/reporting/monthly-report/SKILL.md` (Phase 9, aktif).
> master.xlsx ay-bazlı aggregation + `monthly-report.schema.json` JSON + markdown render.

## 1. Argüman normalizasyonu

`$1` opsiyonel `YYYY-MM`; yoksa "geçen ay":

!`MONTH="${1:-$(date -u -v-1m +%Y-%m 2>/dev/null || date -u --date='last month' +%Y-%m)}"; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "month=$MONTH project=NO_WORKSPACE_ROOT (PSEO_WORKSPACE_ROOT env var set edilmemiş)"; else PROJECT="${2:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; echo "month=$MONTH project=${PROJECT:-NO_ACTIVE_PROJECT}"; fi`

`PROJECT` boşsa: kullanıcıdan slug iste veya `/pseo-active <slug>` öner; aşağıdaki adımları atla.

## 2. Skill chain

`skills/reporting/monthly-report/SKILL.md` LOCAL aggregator (Phase 9 W1, no MCP, no DFS, 0 credit) şu adımları koşar:

1. master.xlsx'ten 9 logical sheet oku (READ-ONLY): `master_task` + `completed_work` + `gsc_performance` + `opportunity` + `content_decay` + `tech_seo` + `schema` + `new_content_plan` + `content_improve`
2. events.jsonl son 28 gün work-event context (READ-ONLY) — provenance + workflow events filter
3. `monthly-report.schema.json` v1.0 formatında JSON data objesi üret (10 zorunlu section + framing_policy default `positive_client` + output_formats subset of `[html, pdf, notion]`)
4. `templates/reports/monthly-report.template.md` + JSON'u `scripts/reporting/render_template.py` ile birleştir → `outputs/reports/{date}-monthly.md` (insan-okunur markdown)
5. JSON kopyası `inbox/local/{date}-monthly-{slug}.json` olarak persist (provenance audit trail)
6. master.xlsx **WRITE YOK** (skill `outputs[]` `master.xlsx#none` confirm); events.jsonl **WRITE YOK** (Q-RP-01 deferred Phase 14+ governance refinement)

## 3. Manuel template render (helper)

Hazır JSON data ile `render_template.py` doğrudan çağrılabilir. CLI imzası: `render_template.py <template.md> <data.json>` (stdout'a render eder; `$key` / `${key}` yerine geçirir).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reporting/render_template.py" \
  "${CLAUDE_PLUGIN_ROOT}/templates/reports/monthly-report.template.md" \
  "${PSEO_WORKSPACE_ROOT}/projects/<slug>/_state/reports/<YYYY-MM>-monthly.json"
```

## 4. Bağımlılıklar

- `skills/reporting/monthly-report/SKILL.md` — aktif (Phase 9)
- `templates/reports/monthly-report.template.md` — aktif
- master.xlsx ay-bazlı aggregation skill'leri (gsc-pull, content-decay) — Phase 6/7
