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

Her adım: **gerçek** MCP aracını çağır → provenance-damgalı ham drop yaz → adımın **mevcut**
transform CLI'ını çalıştır. CLI çıktısı `--output-dir` ile inbox'a değil transform klasörüne,
**SHEET adıyla** (`{sheet}.json`) düşer; sürücünün `_output_loader`'ı tam bu dosyayı okur. CLI'lar
adıma göre FARKLI argüman alır (`content_decay` `--raw` DEĞİL, iki pencere `--recent`+`--previous`).

| Adım | MCP aracı (ham drop) | Sheet → çıktı dosyası | Transform CLI |
|------|----------------------|-----------------------|---------------|
| `gsc_pull` | `mcp__gsc__search_analytics` (recent) [+ `enhanced_search_analytics` enriched] | `gsc_performance` → **`gsc_performance.json`** | `scripts/ingestion/gsc_pull.py` |
| `quick_wins` | `mcp__gsc__detect_quick_wins` (30d) [+ `enhanced_search_analytics` enriched] | `quick_wins` → **`quick_wins.json`** (+ `opportunity.json`) | `scripts/discovery/quickwins_transform.py` |
| `content_decay` | `mcp__gsc__enhanced_search_analytics` **×2 (recent + previous pencere)** | `content_decay` → **`content_decay.json`** | `scripts/discovery/content_decay_transform.py` |

Önce inbox + transform klasörlerini hazırla:

```bash
mkdir -p "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID" \
         "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID"
```

**Ortak kurallar (her adım):**

- **Ham drop (provenance-damgalı)** — her MCP yanıtını `Write` ile yaz. Sürücü her adımın PRİMER
  drop'unu `_state/inbox/$RUN_ID/{step}.json` (step ADIYLA) yolunda `verify_raw_drop` ile doğrular
  → `input_count`; provenance `window` + `tool` adımın beklentisine UYMALI ve `declared_count`
  satır sayısına EŞİT olmalı (yoksa `truncated`):

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

- **Çıktı dosyası** — transform CLI `--output-dir` ile `_state/transform/$RUN_ID/` altına SHEET
  adıyla `{sheet}.json` düşürür (bare JSON list); sürücünün `_output_loader`'ı tam bu yolu okur
  (`gsc_pull`→`gsc_performance.json`, `quick_wins`→`quick_wins.json`,
  `content_decay`→`content_decay.json`). `{"rows": [...]}` sarmalı da kabul edilir.
- **Commit YAPMA** — sheet'leri sürücü (adım 4) `committer` ile yazar.

### 3.a — `gsc_pull` → `gsc_performance.json`

1. `mcp__gsc__search_analytics` (**recent** pencere) → PRİMER drop
   `_state/inbox/$RUN_ID/gsc_pull.json` (provenance `window:"recent"`,
   `tool:"mcp__gsc__search_analytics"`).
2. *(opsiyonel)* `mcp__gsc__enhanced_search_analytics` (önceki pencere, delta için) → ikincil drop
   `_state/inbox/$RUN_ID/gsc_pull_enriched.json`.

Transform (`--enriched` opsiyonel; ikincil drop yoksa o bayrağı düşür) → `gsc_performance.json` yazar:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingestion/gsc_pull.py" \
  --raw "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/gsc_pull.json" \
  --enriched "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/gsc_pull_enriched.json" \
  --output-dir "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"
```

### 3.b — `quick_wins` → `quick_wins.json` (+ `opportunity.json`)

1. `mcp__gsc__detect_quick_wins` → PRİMER drop `_state/inbox/$RUN_ID/quick_wins.json`
   (provenance `window:"30d"`, `tool:"mcp__gsc__detect_quick_wins"`).
2. *(opsiyonel)* `mcp__gsc__enhanced_search_analytics` (sparse satır back-fill) → ikincil drop
   `_state/inbox/$RUN_ID/quick_wins_enriched.json`.

Transform (`--enriched` opsiyonel) → `quick_wins.json` + `opportunity.json` yazar (sürücü PRİMER
sheet `quick_wins`'i okur; `opportunity` skill'in kendi ikincil çıktısı):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery/quickwins_transform.py" \
  --raw "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/quick_wins.json" \
  --enriched "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/quick_wins_enriched.json" \
  --output-dir "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"
```

### 3.c — `content_decay` → `content_decay.json` (**İKİ pencere ZORUNLU**)

`content_decay` tek MCP çağrısı DEĞİL: `enhanced_search_analytics`'i **iki kez** çağır (eşit
uzunlukta **recent** + **previous** 90-gün pencereleri) ve İKİ ayrı drop yaz. CLI `--raw` DEĞİL,
`--recent` + `--previous` (ikisi de zorunlu) alır; her İKİ pencere de boşsa CLI DURUR (sinyal yok =
veri yok).

1. `mcp__gsc__enhanced_search_analytics` (**recent** pencere) → PRİMER drop
   `_state/inbox/$RUN_ID/content_decay.json` (provenance `window:"recent"`,
   `tool:"mcp__gsc__enhanced_search_analytics"` — sürücünün gate'lediği drop).
2. `mcp__gsc__enhanced_search_analytics` (**previous** pencere) → ikincil drop
   `_state/inbox/$RUN_ID/content_decay_previous.json` (gate'lenmez; CLI'nin `--previous` girdisi).

Transform → `content_decay.json` yazar:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery/content_decay_transform.py" \
  --recent "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/content_decay.json" \
  --previous "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/content_decay_previous.json" \
  --output-dir "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"
```

> Bu bölümde **commit YAPMA** — model yalnızca ham drop(lar) + transform çıktısını üretir;
> doğrulama + commit + coverage CODE'a (adım 4 sürücü) aittir.

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
