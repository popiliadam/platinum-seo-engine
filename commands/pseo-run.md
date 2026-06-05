---
description: |
  Use when: kullanıcı "aylık bakım yap", "monthly maintenance", "workflow çalıştır",
  "pseo-run", "bakım workflow", "duraklayan run'ı devam ettir" der ya da
  `/pseo-run <workflow> [project-slug] [--resume]` çağırır.
  Also use when: aktif proje için ORKESTRE edilmiş bir bakım dizisi (gsc-pull →
  quick-wins + content-decay → monthly-report) baştan sona koşturulacak; her
  yapısal adım için MCP çağrısı + mevcut transform CLI çalıştırılıp CODE tarafından
  doğrulanıp commit'lenecek ve bir coverage kaydı + (gerekirse) Türkçe düzeltme
  komutu üretilecek.
  Do not use when: tek bir ingestion adımı yeter (`/pseo-gsc-pull`,
  `/pseo-quickwin`, `/pseo-content-decay`); sadece rapor isteniyor (`/pseo-monthly`);
  drift kontrolü gerekiyor (`/pseo-driftcheck`). Bu komut bir DİZİ orkestratörüdür,
  tek skill değil.
argument-hint: "<workflow> [project-slug] [--resume]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(date:*), Bash(mkdir:*), Read, Write, mcp__gsc__search_analytics, mcp__gsc__detect_quick_wins, mcp__gsc__enhanced_search_analytics
model: sonnet
---

# /pseo-run — Workflow Orkestratörü (Faz-1: `monthly`)

> **Orkestratör spine:** `scripts/orchestration/run_step.py` (verify → loader-transform →
> commit → coverage) + sürücü `scripts/orchestration/workflows/monthly_maintenance.py`.
> Tek Faz-1 workflow'u: **`monthly`**. Sıra SABİT bir Python dizisidir (Path A, DAG yok).
> CODE tool çağrısı YAPAMAZ → MCP çağrısını + transform'u MODEL yapar, CODE doğrular + commit'ler.

## 1. Aktif projeyi + workflow'u çöz

`$1` = workflow (varsayılan `monthly`); `$2` = opsiyonel slug; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else WF="${1:-monthly}"; PROJECT="${2:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "workflow=$WF project=NO_ACTIVE_PROJECT — önce /pseo-active <slug>"; else echo "workflow=$WF project=$PROJECT"; fi; fi`

- `PROJECT` boşsa: kullanıcıdan slug iste veya `/pseo-active <slug>` öner; aşağıdaki adımları atla.
- `$2` `--resume` ise slug'ı `active.json`'dan çöz ve **2.b**'deki resume yolunu izle.
- Workflow `monthly` değilse: Faz-1'de yalnızca `monthly` desteklenir — DURUR, manager'a bildir.

## 2. Workflow run'ını aç (ya da resume et)

### 2.a — Yeni run

`run_id` `workflow_runner` tarafından üretilir (grammar `{slug}-{YYYY-MM-DD}-{hash4}`):

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="monthly-maintenance",
    project_slug=PROJECT,
    steps=[{"name": "gsc_pull"}, {"name": "quick_wins"},
           {"name": "content_decay"}, {"name": "monthly_report"}],
)
run_id = handle.run_id
```

### 2.b — Resume (`--resume`)

Var olan run'ı aynı `run_id` ile yeniden aç; yalnızca **eksik/başarısız** adımlar yeniden koşulur
(driver idempotent: `committer` whole-block replace, coverage yeniden yazılır):

```python
workflow_runner.resume(run_id, project_slug=PROJECT)
```

## 3. Yapısal adımlar (SIRAYLA: gsc_pull → quick_wins → content_decay)

| Adım | MCP aracı | Sheet | Transform CLI |
|------|-----------|-------|---------------|
| `gsc_pull` | `mcp__gsc__search_analytics` | `gsc_performance` | `scripts/ingestion/gsc_pull.py` |
| `quick_wins` | `mcp__gsc__detect_quick_wins` | `quick_wins` | `scripts/discovery/quickwins_transform.py` |
| `content_decay` | `mcp__gsc__enhanced_search_analytics` | `content_decay` | `scripts/discovery/content_decay_transform.py` |

Önce inbox + transform klasörlerini hazırla:

```bash
mkdir -p "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID" \
         "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID"
```

Her `{step}` için **sırayla** şunları yap:

1. **MCP çağrısı** — tablodaki aracı çağır (örn. `gsc_pull` için `mcp__gsc__search_analytics`).
2. **Provenance-damgalı ham drop** — yanıtı `Write` ile
   `_state/inbox/$RUN_ID/{step}.json` yoluna şu şekilde yaz (driver `verify_raw_drop` ile
   doğrular; `declared_count` satır sayısına EŞİT olmalı, yoksa `truncated`):

   ```json
   {
     "provenance": {
       "run_id": "<run_id>", "slug": "<slug>",
       "site_url": "<project.config gsc.site_url>",
       "window": "<recent|30d>", "tool": "<mcp aracı>",
       "fetched_at": "<UTC ISO-8601>", "declared_count": <satır sayısı>
     },
     "rows": [ /* ham MCP satırları */ ]
   }
   ```

3. **Mevcut transform CLI** — adımın transform'unu çalıştır; master.xlsx-şeklindeki ÇIKTI
   satırları `_state/transform/$RUN_ID/{step}.json` yoluna düşmeli (driver'ın
   `_output_loader`'ı tam bu yolu okur; bare JSON list VEYA `{"rows": [...]}` kabul eder).
   `gsc_pull` örneği (diğer adımlar kendi CLI'ları ile aynı desende):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingestion/gsc_pull.py" \
     --raw "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/gsc_pull.json" \
     --output-dir "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"
   ```

> Bu adımda **commit YAPMA** — sheet'leri sürücü (adım 4) `committer` ile yazar. Model yalnızca
> ham drop + transform çıktısını üretir; doğrulama + commit + coverage CODE'a aittir.

## 4. Sürücü #1 — doğrula + commit + coverage kaydet

3 yapısal adımın drop'ları + çıktıları hazırken sürücüyü çalıştır. `--now-epoch` zorunlu
(modül saat OKUMAZ — sınırda `date` ile geçiyoruz); `--report-exists` HENÜZ verilmez:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m scripts.orchestration.workflows.monthly_maintenance \
  --run-id "$RUN_ID" --slug "$PROJECT" \
  --workspace-root "$PSEO_WORKSPACE_ROOT" \
  --workbook "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/master.xlsx" \
  --now-epoch "$(date +%s)"
```

Sürücü: her adımı `run_step` ile geçirir (verify → loader-transform → `committer.commit` →
silent-skip gate), `monthly_report`'u `model_attested` olarak (henüz `missing`) ekler, verdict
türetir ve coverage kaydını `_state/coverage/$RUN_ID.json` dosyasına yazar
(`schemas/coverage.schema.json`'a uyar).

## 5. monthly-report skill (attested) + sürücü #2

Sheet'ler artık commit'li → `monthly-report` skill'ini çalıştır
(`skills/reporting/monthly-report/SKILL.md`, READ-ONLY LOCAL aggregator, 0 credit):
`outputs/reports/{date}-monthly.md` üretir, master.xlsx'e YAZMAZ.

Rapor artefaktı oluştuktan sonra sürücüyü **`--report-exists`** ile tekrar çalıştır (idempotent:
replace → satır kopyalanmaz, coverage yeniden yazılır). Bu, `monthly_report` adımını `satisfied`
yapar ve tüm adımlar tamamsa verdict `pass` olur:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m scripts.orchestration.workflows.monthly_maintenance \
  --run-id "$RUN_ID" --slug "$PROJECT" \
  --workspace-root "$PSEO_WORKSPACE_ROOT" \
  --workbook "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/master.xlsx" \
  --now-epoch "$(date +%s)" --report-exists
```

## 6. Verdict `pass` değilse — Türkçe düzeltme komutu

Sürücü `verdict`'i `pass` değilse (incomplete / failed / paused), `remediation` yüzeyini bas:
sürücünün son satırı zaten `remediation.render(...)` çıktısını yazdırır ve **kopyala-yapıştır**
edilebilir tek aksiyonu içerir:

```
/pseo-run monthly <slug> --resume
```

- `incomplete` → eksik yapısal adım(lar) adlandırılır; `--resume` onları tamamlar.
- `failed` → silent-skip / gate reddi olan adım(lar); `--resume` yeniden dener.
- `paused` → harici bağımlılık (GSC/DFS) duraklattı; `--resume` kaldığı yerden devam eder.

Operatör (Mac app) her zaman tek bir sonraki aksiyon görür: yukarıdaki komutu çalıştır.

## 7. Bağımlılıklar

- Sürücü: `scripts/orchestration/workflows/monthly_maintenance.py` (+ spine
  `run_step.py` / `coverage.py` / `verify.py` / `committer.py` — IMPORT-only, değiştirilmez).
- Remediation: `scripts/orchestration/remediation.py`.
- Skill zinciri: `skills/ingestion/gsc-pull/SKILL.md`, `skills/discovery/quick-wins/SKILL.md`,
  `skills/discovery/content-decay/SKILL.md`, `skills/reporting/monthly-report/SKILL.md`.
- Run state: `scripts/state/workflow_runner.py` (`create_run` / `resume`).
- MCP required: `mcp__gsc__search_analytics`, `mcp__gsc__detect_quick_wins`,
  `mcp__gsc__enhanced_search_analytics`; `.env` auto-source (GSC service account).
- Coverage proof: `schemas/coverage.schema.json` (`_state/coverage/{run_id}.json`).
- Tamamlanmayı ZORUNLU kılan denetçi (Stop-hook) ayrı bir batch'tir (2c) — bu komut workflow'u
  KOŞTURUR + coverage üretir; turn-end engellemesi burada YOKTUR.
