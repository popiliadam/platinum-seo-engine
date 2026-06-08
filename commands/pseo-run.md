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
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(date:*), Bash(mkdir:*), Read, Write, mcp__gsc__search_analytics, mcp__gsc__detect_quick_wins, mcp__gsc__enhanced_search_analytics, mcp__dataforseo__on_page_lighthouse, mcp__dataforseo__on_page_content_parsing, mcp__dataforseo__dataforseo_labs_google_keyword_ideas, mcp__dataforseo__dataforseo_labs_google_related_keywords, mcp__dataforseo__dataforseo_labs_google_keyword_suggestions, mcp__dataforseo__dataforseo_labs_search_intent, mcp__dataforseo__dataforseo_labs_google_keyword_overview, mcp__dataforseo__serp_organic_live_advanced, mcp__higgsfield__generate_image
model: sonnet
---

# /pseo-run — Workflow Orkestratörü (Faz-1: `monthly` · Faz-3: `audit` + `setup` + `content`)

> **Orkestratör spine:** `scripts/orchestration/run_step.py` (verify → loader-transform →
> commit → coverage) + sürücüler `scripts/orchestration/workflows/monthly_maintenance.py`
> (`monthly`), `scripts/orchestration/workflows/audit_suite.py` (`audit`),
> `scripts/orchestration/workflows/new_project_setup.py` (`setup`) ve
> `scripts/orchestration/workflows/content_pipeline.py` (`content`).
> Desteklenen workflow'lar: **`monthly`** (Faz-1, **Bölüm 2-7**), **`audit`** (Faz-3
> teknik-SEO denetim suite, **Bölüm 8**), **`setup`** (Faz-3 yeni-proje içerik-planı
> pipeline'ı, **Bölüm 9**) ve **`content`** (Faz-3 blog-içerik üretim pipeline'ı,
> **Bölüm 10**). İlk üçü VERİ sürücüsüdür (ham drop → transform CLI → verify → commit →
> sheet satırları). **`content` bir ARTEFAKT sürücüsüdür** — model bir blog HTML artefaktı
> üretir; `run_step`/`committer` YOK, master.xlsx sheet'i YOK; CODE her adımın artefaktının
> VAR olduğunu + (HTML ise) AI-disclosure sinyali taşımadığını doğrular. Her sıra SABİT bir
> Python dizisidir (Path A, DAG yok). CODE tool çağrısı YAPAMAZ → MCP çağrısını +
> transform/üretimi MODEL yapar, CODE doğrular (veri sürücüleri ayrıca commit'ler).

## 1. Aktif projeyi + workflow'u çöz

`$1` = workflow (varsayılan `monthly`); `$2` = opsiyonel slug; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else WF="${1:-monthly}"; PROJECT="${2:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "workflow=$WF project=NO_ACTIVE_PROJECT — önce /pseo-active <slug>"; else echo "workflow=$WF project=$PROJECT"; fi; fi`

- `PROJECT` boşsa: kullanıcıdan slug iste veya `/pseo-active <slug>` öner; aşağıdaki adımları atla.
- `$2` `--resume` ise slug'ı `active.json`'dan çöz ve **2.b**'deki resume yolunu izle.
- Workflow `monthly` ise: **Bölüm 2-7**'yi izle. Workflow `audit` ise: **Bölüm 8** (audit
  suite, Faz-3) — DURUR'ma. Workflow `setup` ise: **Bölüm 9** (yeni-proje içerik-planı
  pipeline'ı, Faz-3) — DURUR'ma. Workflow `content` ise: **Bölüm 10** (blog-içerik üretim
  pipeline'ı, Faz-3) — DURUR'ma. Başka bir workflow ise: desteklenmiyor — DURUR, manager'a bildir.

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

---

## 8. Workflow `audit` (Faz-3) — teknik-SEO denetim suite

> **4 yapısal adım, rapor adımı YOK.** Teslimat = **4 commit'li sheet** (`tech_seo`, `schema`,
> `on_page_audit`, `cannibalization`). Sürücü `audit_suite.py`, `monthly` ile AYNI spine'ı kullanır.
> Her sheet bir SNAPSHOT (tarih/run kolonu yok) → commit `transaction.replace` (idempotent;
> re-run satır kopyalamaz). 3 adım ANALİZ eder (aggregate/grupla) → `model_attested`
> (kimlik+içerik+tazelik gate'i KOŞAR; silent-skip sayım kontrolü TAVSİYE niteliğinde — analiz
> adımı girdisinin <%50'sini commit'leyebilir, gate onu yanlış-FAIL etmez). `on_page_audit` URL
> başına bir satır üretir → `code_verified` (silent-skip gate'i ZORUNLU).

### 8.1 — Run aç (ya da resume et)

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="audit-suite",
    project_slug=PROJECT,
    steps=[{"name": "tech_audit"}, {"name": "schema_audit"},
           {"name": "on_page_audit"}, {"name": "cannibalization"}],
)
run_id = handle.run_id
```

`--resume`: `monthly` ile aynı — `workflow_runner.resume(run_id, project_slug=PROJECT)`; yalnız
eksik/başarısız adımlar yeniden koşar (committer whole-block replace, coverage yeniden yazılır).

### 8.2 — Yapısal adımlar (SIRAYLA: tech_audit → schema_audit → on_page_audit → cannibalization)

Önce klasörleri hazırla:

```bash
mkdir -p "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID" \
         "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID"
```

**Ortak kurallar (her adım):**

- **Ham PRİMER drop (provenance-damgalı)** — gerçek MCP aracını çağır, yanıtı `Write` ile
  `_state/inbox/$RUN_ID/{step}.json` yoluna yaz. Sürücü bu drop'u `verify_raw_drop` ile doğrular
  (→ `input_count`). Provenance: `run_id`, `slug`, `tool` (adımın beklediği araç; `schema_audit`
  araç PİNLEMEZ — alanı atla), `window: null` (denetim nokta-bazlı, tarih penceresi DEĞİL),
  `site_url` (yalnız `cannibalization` GSC kaynaklı → project.config `gsc.site_url`), `fetched_at`
  (UTC ISO-8601), `declared_count == len(rows)` (eşit değilse `truncated`):

  ```json
  {
    "provenance": {
      "run_id": "<run_id>", "slug": "<slug>",
      "site_url": "<yalnız cannibalization>", "window": null,
      "tool": "<gated MCP aracı | schema_audit: bu alanı atla>",
      "fetched_at": "<UTC ISO-8601>", "declared_count": <satır sayısı>
    },
    "rows": [ /* ham MCP satırları — gate input_count'u sayar */ ]
  }
  ```

- **DFS adımları (`tech_audit`, `on_page_audit`)**: transform CLI ham yanıtı `items`/`tasks`
  anahtarından okur (`rows`'dan DEĞİL). Bu yüzden PRİMER drop'a **hem** `rows` (gate sayar) **hem**
  `items` (CLI okur; aynı per-URL liste) koy. **GSC/SF adımları (`cannibalization`,
  `schema_audit`)**: CLI doğrudan `rows`'u okur → tek anahtar (`rows`) yeter.

- **İKİ girdili CLI'lar** — ikincil drop GATE'lenmez, CLI'nin ek girdisidir; ayrı inbox dosyasına
  yaz: `tech_audit` (`--content-parsing`), `schema_audit` (`--raw-dfs`, opsiyonel),
  `on_page_audit` (`--raw-gsc`, opsiyonel).

- **Çıktı dosyası** — CLI `--output-dir` ile `_state/transform/$RUN_ID/` altına **{output_file}**
  yazar. ⚠️ `{output_file}` her zaman `{sheet}.json` DEĞİL: `schema_audit` CLI'ı
  **`schema_audit.json`** yazar ama sheet'i **`schema`** (1d.1 tuzağı). Sürücünün loader'ı
  `{output_file}`'ı okur — `{sheet}.json`'u DEĞİL.

- **Commit YAPMA** — sheet'leri sürücü (8.3) `committer.commit` ile yazar.

| Adım | Gated MCP aracı (PRİMER drop) | İkincil drop (gate'siz) | Sheet → **çıktı dosyası** | Transform CLI argümanları |
|------|------------------------------|--------------------------|---------------------------|---------------------------|
| `tech_audit` | `mcp__dataforseo__on_page_lighthouse` | `…on_page_content_parsing` → `tech_audit_content.json` | `tech_seo` → **`tech_seo.json`** | `--lighthouse <primer> --content-parsing <ikincil> [--url-cap N] --output-dir` |
| `schema_audit` | *(SF veya dosya — araç PİNLENMEZ)* | *(ops.)* `…on_page_content_parsing` → `schema_audit_dfs.json` | `schema` → **`schema_audit.json`** | `--raw-sf <primer> [--raw-dfs <ikincil>] --output-dir` |
| `on_page_audit` | `mcp__dataforseo__on_page_content_parsing` | *(ops.)* `mcp__gsc__search_analytics` → `on_page_audit_gsc.json` | `on_page_audit` → **`on_page_audit.json`** | `--raw-content-parsing <primer> [--raw-gsc <ikincil>] --output-dir` |
| `cannibalization` | `mcp__gsc__search_analytics` (query+page) | — | `cannibalization` → **`cannibalization.json`** | `--raw <primer> [--min-impressions N] --output-dir` |

Transform CLI çağrıları (her adım için PRİMER drop yazıldıktan sonra):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery/tech_audit_transform.py" \
  --lighthouse      "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/tech_audit.json" \
  --content-parsing "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/tech_audit_content.json" \
  --output-dir      "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery/schema_audit_transform.py" \
  --raw-sf     "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/schema_audit.json" \
  --output-dir "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery/on_page_audit_transform.py" \
  --raw-content-parsing "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/on_page_audit.json" \
  --output-dir          "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery/cannibalization_transform.py" \
  --raw        "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/cannibalization.json" \
  --output-dir "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"
```

> `schema_audit` kaynağı SF: dosya-bazlı `structured_data_all` export (varsayılan) ya da opt-in SF
> MCP. Bu adım araç PİNLEMEZ (`expected_tool=None`) — provenance `tool` alanını atla; gate yalnız
> kimlik (`run_id`/`slug`) + tazelik + `declared_count`'u doğrular.
>
> Bu bölümde **commit YAPMA** — model yalnız ham drop(lar) + transform çıktısı üretir; doğrulama +
> commit + coverage CODE'a (8.3 sürücü) aittir.

### 8.3 — Sürücü (`audit_suite`) — doğrula + commit + coverage

4 adımın drop'ları + çıktıları hazırken sürücüyü çalıştır. `--now-epoch` zorunlu (modül saat
OKUMAZ — sınırda `date` ile geçiyoruz). Rapor adımı YOK → `--report-exists` YOK:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m scripts.orchestration.workflows.audit_suite \
  --run-id "$RUN_ID" --slug "$PROJECT" \
  --workspace-root "$PSEO_WORKSPACE_ROOT" \
  --workbook "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/master.xlsx" \
  --now-epoch "$(date +%s)"
```

Sürücü: `code_verified` adımı (`on_page_audit`) `run_step` ile (verify → loader-transform →
`committer.commit` → silent-skip ZORUNLU); `model_attested` adımları (`tech_audit`, `schema_audit`,
`cannibalization`) kimlik+içerik+tazelik gate'i + `committer.commit` (silent-skip TAVSİYE) ile
geçirir; verdict türetir (4 sheet'in HEPSİ `satisfied` değilse `pass` olamaz — tamamlanma geçidi)
ve coverage kaydını `_state/coverage/$RUN_ID.json` dosyasına yazar (`schemas/coverage.schema.json`).

### 8.4 — Verdict `pass` değilse — Türkçe düzeltme komutu

Sürücünün son satırı zaten `remediation.render(...)` çıktısıdır; tek kopyala-yapıştır aksiyon:

```
/pseo-run audit <slug> --resume
```

- `incomplete` → eksik yapısal adım(lar) adlandırılır; `--resume` onları tamamlar.
- `failed` → gate reddi / `on_page_audit` silent-skip olan adım(lar); `--resume` yeniden dener.
- `paused` → harici bağımlılık (DFS/GSC) duraklattı; `--resume` kaldığı yerden devam eder.

### 8.5 — Bağımlılıklar (`audit`)

- Sürücü: `scripts/orchestration/workflows/audit_suite.py` (+ spine `run_step.py` / `verify.py` /
  `committer.py` / `coverage.py` — IMPORT-only, değiştirilmez).
- Remediation: `scripts/orchestration/remediation.py` (`workflow="audit"` → `/pseo-run audit … --resume`).
- Skill + transform zinciri: `skills/discovery/tech-audit/SKILL.md` +
  `scripts/discovery/tech_audit_transform.py`; `skills/discovery/schema-audit/SKILL.md` +
  `scripts/discovery/schema_audit_transform.py`; `skills/discovery/on-page-audit/SKILL.md` +
  `scripts/discovery/on_page_audit_transform.py`; `skills/discovery/cannibalization/SKILL.md` +
  `scripts/discovery/cannibalization_transform.py`.
- Run state: `scripts/state/workflow_runner.py` (`create_run` / `resume`).
- MCP: `mcp__dataforseo__on_page_lighthouse`, `mcp__dataforseo__on_page_content_parsing`,
  `mcp__gsc__search_analytics`; `schema_audit` SF export (dosya) veya opt-in SF MCP. DFS HEAVY →
  her DFS adımı kendi SKILL.md'sindeki bütçe pre-flight'ına tabidir.
- Coverage proof: `schemas/coverage.schema.json` (`_state/coverage/{run_id}.json`).

---

## 9. Workflow `setup` (Faz-3) — yeni-proje içerik-planı pipeline'ı

> **3 yapısal adım, rapor adımı YOK.** Teslimat = **3 commit'li sheet** (`topical_map`,
> `cluster_keywords`, `new_content_plan`). Sürücü `new_project_setup.py`, `monthly`/`audit` ile
> AYNI spine'ı kullanır ve `audit_suite`'in D15 dispatch'ini (`_run_one`) IMPORT eder.
> **Ön-koşul:** proje zaten `/pseo-init` ile scaffold edilmiş olmalı (scaffold bu workflow'un
> parçası DEĞİL). Her sheet bir SNAPSHOT (tarih/run discriminator kolonu yok; `new_content_plan`'in
> `created_date`'i içerik-üstverisi, append-anahtarı değil — transform `id`'yi her koşuda 1'den
> yeniden numaralar) → commit `transaction.replace` (idempotent; re-run satır kopyalamaz).
> **3 adımın HEPSİ ANALİZ/PLANLAMA eder** (topical_map → pillar/cluster taksonomisi; cluster_map
> no-cluster anahtarları eler + dedup; new_content_plan gap_score'a göre top-N'e kırpar) → girdisinin
> <%50'sini commit'ler → **HEPSİ `model_attested`** (kimlik+içerik+tazelik gate'i KOŞAR; silent-skip
> sayım kontrolü TAVSİYE — gate onları yanlış-FAIL etmez). Per-row ingestion adımı YOK → `code_verified`
> adım YOK; tamamlanmayı yalnız **tamamlanma geçidi** (her adım `satisfied` değilse `pass` olamaz)
> zorlar.
>
> **⚠️ SIRALI BAĞIMLILIK:** `cluster_map`, `topical_map`'i tüketir; `new_content_plan`,
> `cluster_keywords`'ü tüketir (`consumes:` frontmatter). Sürücü adımları SIRAYLA koşar → her önceki
> sheet bağımlı adımdan ÖNCE commit'lenir; bağımlılık **SIRALAMA** ile sağlanır (sürücü değişikliği
> DEĞİL). CLI'lar master.xlsx'i DOĞRUDAN okumaz — model önceki sheet'in satırlarını çıkarıp bağımlı
> CLI'ya **argüman** olarak geçer (8.2'deki gibi DFS heavy değil; planlama nokta-bazlı).

### 9.1 — Run aç (ya da resume et)

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="new-project-setup",
    project_slug=PROJECT,
    steps=[{"name": "topical_map"}, {"name": "cluster_map"},
           {"name": "new_content_plan"}],
)
run_id = handle.run_id
```

`--resume`: `monthly`/`audit` ile aynı — `workflow_runner.resume(run_id, project_slug=PROJECT)`; yalnız
eksik/başarısız adımlar yeniden koşar (committer whole-block replace, coverage yeniden yazılır).

### 9.2 — Yapısal adımlar (SIRAYLA: topical_map → cluster_map → new_content_plan)

Önce klasörleri hazırla:

```bash
mkdir -p "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID" \
         "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID"
```

**Ortak kurallar (her adım):**

- **Ham PRİMER drop (provenance-damgalı)** — gerçek MCP aracını çağır, yanıtı `Write` ile
  `_state/inbox/$RUN_ID/{step}.json` yoluna yaz. Sürücü bu drop'u `verify_raw_drop` ile doğrular
  (→ `input_count`). Provenance: `run_id`, `slug`, `tool` (adımın beklediği araç; `new_content_plan`
  araç PİNLEMEZ — alanı atla), `window: null` (planlama nokta-bazlı, tarih penceresi DEĞİL),
  `fetched_at` (UTC ISO-8601), `declared_count == len(rows)` (eşit değilse `truncated`). Hiçbir adım
  GSC-PRİMER değil (`cluster_map`'in GSC'si ENRICHMENT) → `site_url` PİNLENMEZ:

  ```json
  {
    "provenance": {
      "run_id": "<run_id>", "slug": "<slug>", "window": null,
      "tool": "<gated MCP aracı | new_content_plan: bu alanı atla>",
      "fetched_at": "<UTC ISO-8601>", "declared_count": <satır sayısı>
    },
    "rows": [ /* ham satırlar — gate input_count'u sayar */ ]
  }
  ```

- **DFS adımları (`topical_map`, `cluster_map`)**: transform CLI ham yanıtı `items`/`tasks`
  anahtarından okur (`rows`'dan DEĞİL — `_normalize_dfs_response`). Bu yüzden PRİMER drop'a **hem**
  `rows` (gate sayar) **hem** `items` (CLI okur; aynı keyword listesi) koy. **`new_content_plan`**:
  PRİMER "drop"u Faz-7 content-gaps staging satırlarıdır (`{provenance, rows}`); CLI `--staging` bu
  dosyanın `rows`'unu okur → tek liste yeter (araç PİNLENMEZ).

- **İkincil/enrichment drop'lar GATE'lenmez** (CLI'nin ek girdileri); ayrı inbox dosyalarına yaz:
  `topical_map` (`--raw-related-keywords`), `cluster_map` (`--raw-related-keywords`, `--raw-gsc`),
  `new_content_plan` (ops. `--raw-keyword-overview`, `--raw-search-intent`).

- **Önceki-sheet bağımlılığı (SIRALI)** — bağımlı adımın CLI'ı önceki sheet'in verisini bir
  **argüman** olarak alır; model önceki adımın çıktısını (`{prior_sheet}.json` — sürücü bunu
  `master.xlsx#{prior_sheet}`'e commit eder) `Read` ile okuyup girdi JSON'unu `Write` ile üretir:
  - `cluster_map` ← `topical_map`: `master.xlsx#topical_map` kolon B (`cluster`) boş-olmayan
    değerleri → `cluster_defs.json` (JSON list) → `--cluster-defs-json` (D-02 source-of-truth).
  - `new_content_plan` ← `cluster_keywords`: `master.xlsx#cluster_keywords`'ten
    `read_cluster_keywords_snapshot` ile `{keyword: cluster}` → `cluster_map_snapshot.json` →
    `--cluster-map`; `assigned_cluster` bundan cross-ref edilir.

- **Çıktı dosyası** — CLI `--output-dir` ile `_state/transform/$RUN_ID/` altına **{output_file}**
  yazar (bare JSON list; `{"rows": [...]}` da kabul). 3 CLI de `{sheet}.json` yazar (1d.1 tuzağı
  YOK): `topical_map.json`, `cluster_keywords.json`, `new_content_plan.json`. Sürücünün loader'ı tam
  bu yolu okur.

- **Commit YAPMA** — sheet'leri sürücü (9.3) `committer.commit` ile yazar.

| Adım | Gated MCP aracı (PRİMER drop) | İkincil/enrichment (gate'siz) | Önceki-sheet girdisi | Sheet → **çıktı dosyası** | Transform CLI argümanları |
|------|------------------------------|-------------------------------|----------------------|---------------------------|---------------------------|
| `topical_map` | `mcp__dataforseo__dataforseo_labs_google_keyword_ideas` | `…related_keywords` → `topical_map_related.json` | — | `topical_map` → **`topical_map.json`** | `--raw-keyword-ideas <primer> --raw-related-keywords <ikincil> --seed-keyword "<seed>" --output-dir` |
| `cluster_map` | `mcp__dataforseo__dataforseo_labs_google_keyword_suggestions` | `…related_keywords` → `cluster_map_related.json`; `mcp__gsc__enhanced_search_analytics` → `cluster_map_gsc.json` | `topical_map.cluster` → `cluster_defs.json` | `cluster_keywords` → **`cluster_keywords.json`** | `--raw-keyword-suggestions <primer> --raw-related-keywords <ikincil> --raw-gsc <gsc> --cluster-defs-json <cluster_defs.json> --seed-keyword "<seed>" --project-slug $PROJECT --output-dir` |
| `new_content_plan` | *(araç PİNLENMEZ — content-gaps staging dosyası)* | *(ops.)* `…keyword_overview`, `…search_intent` | `cluster_keywords` `{keyword:cluster}` → `cluster_map_snapshot.json` | `new_content_plan` → **`new_content_plan.json`** | `--staging <primer> --cluster-map <cluster_map_snapshot.json> [--raw-keyword-overview …] [--raw-search-intent …] --date <YYYY-MM-DD> --output-dir` |

Transform CLI çağrıları (her adım PRİMER drop + önceki-sheet girdisi hazırlandıktan sonra, SIRAYLA):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/planning/topical_map_transform.py" \
  --raw-keyword-ideas    "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/topical_map.json" \
  --raw-related-keywords "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/topical_map_related.json" \
  --seed-keyword         "$SEED_KEYWORD" \
  --output-dir           "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/planning/cluster_map_transform.py" \
  --raw-keyword-suggestions "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/cluster_map.json" \
  --raw-related-keywords    "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/cluster_map_related.json" \
  --raw-gsc                 "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/cluster_map_gsc.json" \
  --cluster-defs-json       "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/cluster_defs.json" \
  --seed-keyword            "$SEED_KEYWORD" --project-slug "$PROJECT" \
  --output-dir              "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/planning/new_content_plan_transform.py" \
  --staging     "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/new_content_plan.json" \
  --cluster-map "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/inbox/$RUN_ID/cluster_map_snapshot.json" \
  --date        "$(date -u +%Y-%m-%d)" \
  --output-dir  "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/_state/transform/$RUN_ID/"
```

> `new_content_plan` araç PİNLEMEZ (`expected_tool=None`) — content-gaps staging dosya-bazlı kaynak;
> provenance `tool` alanını atla; gate yalnız kimlik (`run_id`/`slug`) + tazelik + `declared_count`'u
> doğrular (schema_audit Faz-3 precedent'i).
>
> Bu bölümde **commit YAPMA** — model yalnız ham drop(lar) + önceki-sheet girdisi + transform çıktısı
> üretir; doğrulama + commit + coverage CODE'a (9.3 sürücü) aittir.

### 9.3 — Sürücü (`new_project_setup`) — doğrula + commit + coverage

3 adımın drop'ları + çıktıları hazırken sürücüyü çalıştır. `--now-epoch` zorunlu (modül saat
OKUMAZ — sınırda `date` ile geçiyoruz). Rapor adımı YOK → `--report-exists` YOK:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m scripts.orchestration.workflows.new_project_setup \
  --run-id "$RUN_ID" --slug "$PROJECT" \
  --workspace-root "$PSEO_WORKSPACE_ROOT" \
  --workbook "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/master.xlsx" \
  --now-epoch "$(date +%s)"
```

Sürücü: her adımı `audit_suite`'ten IMPORT edilen `_run_one` ile geçirir — 3 adım da `model_attested`
olduğundan kimlik+içerik+tazelik gate'i + `committer.commit` (silent-skip TAVSİYE) yolundan SIRAYLA
koşar; verdict türetir (3 sheet'in HEPSİ `satisfied` değilse `pass` olamaz — tamamlanma geçidi; bu
all-attested workflow'da yegâne tamamlanma zorlayıcısı) ve coverage kaydını
`_state/coverage/$RUN_ID.json` dosyasına yazar (`schemas/coverage.schema.json`).

### 9.4 — Verdict `pass` değilse — Türkçe düzeltme komutu

Sürücünün son satırı zaten `remediation.render(...)` çıktısıdır; tek kopyala-yapıştır aksiyon:

```
/pseo-run setup <slug> --resume
```

- `incomplete` → eksik yapısal adım(lar) adlandırılır; `--resume` onları tamamlar.
- `failed` → gate reddi (kimlik/tazelik/truncated) olan adım(lar); `--resume` yeniden dener.
- `paused` → harici bağımlılık (DFS/GSC) duraklattı; `--resume` kaldığı yerden devam eder.

### 9.5 — Bağımlılıklar (`setup`)

- Sürücü: `scripts/orchestration/workflows/new_project_setup.py` (+ spine `run_step.py` / `verify.py` /
  `committer.py` / `coverage.py` — IMPORT-only, değiştirilmez; `audit_suite.py`'den `_run_one` D15
  dispatch IMPORT'u — değiştirilmez).
- Remediation: `scripts/orchestration/remediation.py` (`workflow="setup"` → `/pseo-run setup … --resume`).
- Skill + transform zinciri (SIRALI): `skills/planning/topical-map/SKILL.md` +
  `scripts/planning/topical_map_transform.py`; `skills/planning/cluster-map/SKILL.md` +
  `scripts/planning/cluster_map_transform.py`; `skills/planning/new-content-plan/SKILL.md` +
  `scripts/planning/new_content_plan_transform.py`.
- Run state: `scripts/state/workflow_runner.py` (`create_run` / `resume`).
- MCP: `mcp__dataforseo__dataforseo_labs_google_keyword_ideas`,
  `…dataforseo_labs_google_related_keywords`, `…dataforseo_labs_google_keyword_suggestions`,
  `…dataforseo_labs_search_intent`, `…dataforseo_labs_google_keyword_overview`,
  `mcp__gsc__enhanced_search_analytics`. DFS HEAVY → her DFS adımı kendi SKILL.md'sindeki bütçe
  pre-flight'ına tabidir. `new_content_plan` content-gaps staging'i (Faz-7 producer) tüketir.
- Coverage proof: `schemas/coverage.schema.json` (`_state/coverage/{run_id}.json`).

---

## 10. Workflow `content` (Faz-3) — blog-içerik üretim pipeline'ı

> **3 üretim adımı, rapor adımı YOK.** Teslimat = **üretilmiş blog artefaktı**
> (`outputs/blog/<post>/article.html` + schema.jsonld + meta-tags.json + hero görseller).
> Diğer üç workflow'un AKSİNE bu bir **ARTEFAKT sürücüsüdür**: üç üretim skill'i (new-blog,
> generate-images, faq-optimization) master.xlsx'e YAZMAZ (`transaction.append` YOK — hepsi
> `allowed_writers=null`, READ-ONLY) → ham drop YOK, transform CLI YOK, commit'lenecek sheet
> YOK. Sürücü `content_pipeline.py` `run_step`/`committer` KULLANMAZ; yalnız `coverage` +
> `remediation` + `content_validator` REUSE eder. **3 adımın HEPSİ `model_attested`** (içerik
> KALİTESİ kodla doğrulanamaz — spec §11); CODE'un sahip olduğu adım-başı doğrulama: beklenen
> artefakt VAR MI + (HTML ise) `content_validator.validate_content(html).has_red == False`
> (AI-disclosure sinyali yok — Süleyman sert-kısıt #2; batch 2e `ai_disclosure_rescan` ile AYNI
> dedektör → write-time hook ile inşaen tutarlı). Per-row `code_verified` adım YOK →
> tamamlanmayı yalnız **tamamlanma geçidi** (her adım `satisfied` değilse `pass` olamaz) zorlar —
> bu all-attested workflow'da `setup` ile aynı yegâne tamamlanma zorlayıcısı.
>
> **⚠️ DÜRÜST KAPSAM:** Bu workflow "her üretim adımı KOŞTU + artefaktını ÜRETTİ + artefakt
> AI-disclosure taşımıyor"u GARANTİ eder; içeriğin İYİ olduğunu doğrula(ya)maz — o, ayrıca
> ölçülen QA döngüsüdür.
>
> **⚠️ BAĞIMLILIK:** `new_blog` bir `new_content_plan` satırı tüketir (girdi
> `new_content_plan_id`); `generate_images` aynı plan satırını / new_blog post'unu tüketir;
> `faq_optimization`, `new_blog`'un `article.html`'ini ENHANCE eder (mode=enhance). Sürücü
> adımları SIRAYLA koşar.

### 10.1 — Run aç (ya da resume et)

```python
from scripts.state import workflow_runner
handle = workflow_runner.create_run(
    skill="content-pipeline",
    project_slug=PROJECT,
    steps=[{"name": "new_blog"}, {"name": "generate_images"},
           {"name": "faq_optimization"}],
)
run_id = handle.run_id
```

`--resume`: `monthly`/`audit`/`setup` ile aynı — `workflow_runner.resume(run_id, project_slug=PROJECT)`;
yalnız eksik/başarısız adımlar yeniden koşar (idempotent: artefakt yeniden üretilir, coverage
yeniden yazılır).

### 10.2 — Üretim adımları (SIRAYLA: new_blog → generate_images → faq_optimization)

Diğer workflow'ların AKSİNE burada **ham drop / transform CLI YOK**. MODEL üç üretim skill'ini
SIRAYLA koşar; her biri artefakt(lar)ı `projects/$PROJECT/outputs/...` altına `Write` (ve
generate-images için ops. `mcp__higgsfield__generate_image`) ile yazar. Her `Write` write-time'da
MEVCUT iki hook'tan geçer: PreToolUse `content_validator` (RED → write BLOCK) + PostToolUse
`ai_disclosure_rescan` (RED → karantina). Sürücü (10.3) SONRA her artefaktı BAĞIMSIZ olarak yeniden
doğrular (VAR MI + `content_validator` temiz mi).

| Adım | Skill | Birincil artefakt (sürücü doğrular) | is_html | Bağımlı |
|------|-------|--------------------------------------|---------|---------|
| `new_blog` | `production/new-blog` | `outputs/blog/<post>/article.html` (+ schema.jsonld, meta-tags.json, upload-instructions.md) | ✅ disclosure gate | `new_content_plan` satırı |
| `generate_images` | `production/generate-images` | `outputs/images/<slug>-hero.{webp,avif,jpg}` (+ Section B upload-instructions.md) | ❌ EXISTS-only | new_blog post'u / plan satırı |
| `faq_optimization` | `production/faq-optimization` | `outputs/blog/<post>/article.html` (YERİNDE enhance) | ✅ disclosure gate | new_blog `article.html` |

- **new_blog**: bir `master.xlsx[new_content_plan]` satırından (girdi `new_content_plan_id`) tam
  makale üretir; `<article class="pse-blog-post">` fragmanı (`article.html`) + JSON-LD @graph +
  meta-tags + Section A upload-instructions yazar. master.xlsx'e YAZMAZ.
- **generate_images**: hero görsel üretir → `outputs/images/<slug>-hero.{webp,avif,jpg}` (proje-
  düzeyi, blog dizininin KARDEŞİ). higgsfield HARİCİ kullanıcı-MCP'si (headless'ta sık YOK) →
  sürücüde EXISTS-only (görsel HTML değil); görsel dizini yoksa normal `missing`, ÇÖKME değil
  (DURUR #5 fallback).
- **faq_optimization**: `new_blog`'un `article.html`'ini YERİNDE enhance eder (mode=enhance); FAQ
  bloğu + FAQPage @graph yeniler. Aynı `article.html`'i hedefler → sürücü onu yine disclosure
  gate'ten geçirir.

> Bu bölümde **commit YAPMA / transform YAPMA** — model yalnız üretim skill'lerini koşar +
> artefaktları yazar; VAR-MI + disclosure doğrulaması CODE'a (10.3 sürücü) aittir.

### 10.3 — Sürücü (`content_pipeline`) — artefaktları doğrula + coverage

3 adımın artefaktları üretilince sürücüyü çalıştır. `--blog-output-dir` = THIS run'ın blog dizini
`projects/$PROJECT/outputs/blog/<post>/` (model hangi post olduğunu bilir → recipe geçer);
`--now-epoch` zorunlu (CLI simetrisi; artefakt sürücüsünün tazelik geçidi YOK). Rapor adımı YOK →
`--report-exists` YOK; `--workbook` YOK (commit YOK):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m scripts.orchestration.workflows.content_pipeline \
  --run-id "$RUN_ID" --slug "$PROJECT" \
  --workspace-root "$PSEO_WORKSPACE_ROOT" \
  --blog-output-dir "$PSEO_WORKSPACE_ROOT/projects/$PROJECT/outputs/blog/<post>/" \
  --now-epoch "$(date +%s)"
```

Sürücü: her adımın artefaktını `verify_artifact` ile doğrular (VAR yoksa `missing`; HTML +
disclosure RED ise `failed`; aksi halde `satisfied`), 3 adımı `model_attested` coverage adımı
olarak ekler, verdict türetir (3 artefaktın HEPSİ `satisfied` değilse `pass` olamaz — tamamlanma
geçidi) ve coverage kaydını `_state/coverage/$RUN_ID.json` dosyasına yazar
(`schemas/coverage.schema.json`).

### 10.4 — Verdict `pass` değilse — Türkçe düzeltme komutu

Sürücünün son satırı zaten `remediation.render(...)` çıktısıdır; tek kopyala-yapıştır aksiyon:

```
/pseo-run content <slug> --resume
```

- `incomplete` → eksik artefakt(lar) (ör. headless'ta görsel dizini); `--resume` onları tamamlar.
- `failed` → AI-disclosure RED taşıyan `article.html` (new_blog/faq); `--resume` yeniden üretir —
  görünür "AI tarafından yazıldı" YASAK (açıklamayı kaldırıp yeniden yaz).

### 10.5 — Bağımlılıklar (`content`)

- Sürücü: `scripts/orchestration/workflows/content_pipeline.py` (+ spine `coverage.py` IMPORT-only;
  `run_step`/`committer`/`verify` KULLANILMAZ — artefakt sürücüsü, commit YOK).
- Dedektör REUSE: `scripts/validation/content_validator.py` (`validate_content` +
  `ContentReport.has_red`) + `scripts/hooks/validate_content_write.py` (`is_content_html_path`) —
  batch 2e `ai_disclosure_rescan` ile AYNI dedektör (write-time hook ile inşaen tutarlı). Yeni
  dedektör YOK.
- Remediation: `scripts/orchestration/remediation.py` (`workflow="content"` → `/pseo-run content … --resume`).
- Üretim skill zinciri (SIRALI): `skills/production/new-blog/SKILL.md`,
  `skills/production/generate-images/SKILL.md`, `skills/production/faq-optimization/SKILL.md`.
- Write-time gate'ler (MEVCUT, değiştirilmez): PreToolUse `content_validator` (RED → block) +
  PostToolUse `ai_disclosure_rescan` (RED → karantina).
- Run state: `scripts/state/workflow_runner.py` (`create_run` / `resume`).
- MCP: `new_blog` → `mcp__gsc__search_analytics` + `mcp__dataforseo__serp_organic_live_advanced`
  (ops. Scrapling); `generate_images` → `mcp__higgsfield__generate_image` (HARİCİ kullanıcı-MCP,
  headless'ta sık YOK → DURUR #5 fallback); `faq_optimization` → `mcp__gsc__search_analytics`.
- Coverage proof: `schemas/coverage.schema.json` (`_state/coverage/{run_id}.json`).
