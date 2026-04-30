---
description: |
  Use when: kullanıcı "aylık rapor", "monthly report", "ay sonu özet", "geçen ay neler oldu", "ay raporu üret" der ya da `/pseo-monthly` çağırırsa.
  Also use when: bir ayın sonunda aktif proje için `outputs/reports/{YYYY-MM}-monthly.md` üretilecek; master.xlsx'te trafik/sıralama/içerik verileri ay boyunca toplanmış ve `monthly-report.schema.json` formatında özet rapor isteniyor.
  Do not use when: haftalık özet (`weekly-summary`), portföy genel raporu (`portfolio-overview`), drift kontrol veya tek-seferlik bir analiz isteniyorsa — bunların ayrı skill ve komutları vardır.
argument-hint: "[month=YYYY-MM] [project-slug]"
allowed-tools: Bash(python3:*), Bash(jq:*), Bash(date:*), Read
model: sonnet
---

# /pseo-monthly — Aylık Rapor Üretimi (Phase 9 STUB)

> **Phase dependency:** Bu komut `skills/reporting/monthly-report/SKILL.md` (Phase 9) yazıldıktan sonra tam çalışır. Şu an STUB — yalnızca template render edebilir, master.xlsx aggregation'ı Phase 9'da gelir.

## 1. Argüman normalizasyonu

`$1` opsiyonel `YYYY-MM`; yoksa "geçen ay":

!`MONTH="${1:-$(date -u -v-1m +%Y-%m 2>/dev/null || date -u --date='last month' +%Y-%m)}"; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "month=$MONTH project=NO_WORKSPACE_ROOT (PSEO_WORKSPACE_ROOT env var set edilmemiş)"; else PROJECT="${2:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; echo "month=$MONTH project=${PROJECT:-NO_ACTIVE_PROJECT}"; fi`

`PROJECT` boşsa: kullanıcıdan slug iste veya `/pseo-active <slug>` öner; aşağıdaki adımları atla.

## 2. Phase 9 plan (skill yazıldığında)

`skills/reporting/monthly-report/SKILL.md` şu adımları koşacak:

1. master.xlsx'ten ay boyunca toplanan logical sheet'leri oku (gsc_landing_query, content_decay, quick_wins, master_task)
2. `monthly-report.schema.json` formatında JSON data objesi üret (`{workspace}/projects/{slug}/_state/reports/{month}-monthly.json`)
3. `templates/reports/monthly.template.md` + bu JSON'u `scripts/reporting/render_template.py` ile birleştir
4. Çıktıyı `{workspace}/projects/{slug}/outputs/reports/{month}-monthly.md` olarak yaz
5. `events.jsonl` → `report_generated` event'i

## 3. STUB davranış (template render)

Phase 9'a kadar manuel test için: data JSON elde mevcutsa `render_template.py` doğrudan çağrılabilir.

CLI imzası: `render_template.py <template.md> <data.json>` (stdout'a render eder; `$key` / `${key}` yerine geçirir).

Manuel önizleme örneği (data hazırlandıktan sonra):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reporting/render_template.py" \
  "${CLAUDE_PLUGIN_ROOT}/templates/reports/monthly.template.md" \
  "${PSEO_WORKSPACE_ROOT}/projects/<slug>/_state/reports/<YYYY-MM>-monthly.json"
```

Şu an `templates/reports/monthly.template.md` boş (Phase 9'da yazılır); STUB sırasında komut yalnızca planı sunar.

## 4. Açık bağımlılıklar

- `skills/reporting/monthly-report/SKILL.md` — Phase 9
- `templates/reports/monthly.template.md` — Phase 9
- master.xlsx ay-bazlı aggregation skill'leri (gsc-pull, content-decay) — Phase 6/7
