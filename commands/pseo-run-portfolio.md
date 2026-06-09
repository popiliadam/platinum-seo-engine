---
description: |
  Use when: kullanıcı "tüm portföyü çalıştır", "portföy taraması", "hepsini sırayla
  çalıştır", "portfolio sweep", "run all projects", "her projeye bakım yap" der ya da
  `/pseo-run-portfolio <workflow>` çağırır.
  Also use when: portföydeki TÜM projeler için aynı workflow (monthly/audit/setup/content)
  tek bir taramada SIRAYLA koşturulacak; her proje kendi run-kilidi altında çalışacak
  (başka oturumda çalışan proje ATLANIR, beklenmez) ve her projeden ÖNCE 4a maliyet
  defterinden bütçe rezerve edilecek (job-level preflight + kill-switch).
  Do not use when: tek bir projeyi çalıştırmak yeterli (`/pseo-run <workflow> [slug]`);
  aktif projeyi değiştirme (`/pseo-active`); drift kontrolü (`/pseo-driftcheck`); rapor
  (`/pseo-monthly`). Bu komut bir PORTFÖY orkestratörüdür — tek-proje sürücüsü DEĞİL.
argument-hint: "<workflow>"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(date:*), Bash(mkdir:*), Read, Write, mcp__gsc__search_analytics, mcp__gsc__detect_quick_wins, mcp__gsc__enhanced_search_analytics, mcp__dataforseo__on_page_lighthouse, mcp__dataforseo__on_page_content_parsing, mcp__dataforseo__dataforseo_labs_google_keyword_ideas, mcp__dataforseo__dataforseo_labs_google_related_keywords, mcp__dataforseo__dataforseo_labs_google_keyword_suggestions, mcp__dataforseo__dataforseo_labs_search_intent, mcp__dataforseo__dataforseo_labs_google_keyword_overview, mcp__dataforseo__serp_organic_live_advanced, mcp__higgsfield__generate_image
model: sonnet
---

# /pseo-run-portfolio — Portföy Sıralı-Tarama Orkestratörü (Faz-4)

> **Sıralı-sweep modeli (spec §7).** Faz-0 her oturumu TEK projeye bağlar (yani "3-5
> paralel" zaten N pencere olarak vardır). Bu komut bir PORTFÖY TARAMASI ekler: tek
> çağrıda portföyün projelerini **SIRAYLA** dolaşır, her projenin workflow'unu **kendi
> run-kilidi** altında koşturur (başka yerde çalışan projeyi **ATLAR**, beklemez) ve her
> projeden ÖNCE 4a maliyet defterinden bütçe **rezerve eder** (job-level preflight). Bir
> rezervasyon global tavanı aşacaksa **KILL-SWITCH** ateşlenir: o proje (ve kalanlar)
> `paused`/`not_run` olur (devam ettirilebilir) ve tarama **DURUR** — sessizce eksik
> çalışmaz. Paylaşılan 4a defteri + proje-başı kilitler, bu taramayı paralel bağlı
> tek-proje oturumlarının yanında güvenli kılar.
>
> **Saf çekirdek:** `scripts/orchestration/portfolio_runner.run_sweep(...)` — `period` +
> `now_iso` DIŞARIDAN geçilir (saat OKUNMAZ), `run_project_fn` ENJEKTE edilir
> (`committer.commit` enjeksiyonu gibi). Kilit: `scripts/state/project_lock.py`
> (NON-BLOCKING flock — atla, bekleme). Bütçe: `scripts/state/cost_ledger.py` (4a).

## 1. Workspace + workflow + period + now_iso çöz

`$1` = workflow (ZORUNLU). Geçerli set: `monthly` · `audit` · `setup` · `content`. Başka
bir değer → **DURUR** (manager'a bildir, hiçbir şey rezerve etme):

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else WF="${1:-}"; if [ -z "$WF" ]; then echo "ERROR: workflow ZORUNLU — kullanım: /pseo-run-portfolio <monthly|audit|setup|content>"; elif [ "$WF" = monthly ] || [ "$WF" = audit ] || [ "$WF" = setup ] || [ "$WF" = content ]; then PERIOD="$(date -u +%Y-%m-%d)"; NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"; echo "workflow=$WF period=$PERIOD now_iso=$NOW_ISO"; else echo "DURUR: desteklenmeyen workflow — yalnız monthly/audit/setup/content"; fi; fi`

- `PERIOD` = bugünün UTC tarihi (4a defteri için partition anahtarı); `NOW_ISO` = UTC
  ISO-8601 (rezervasyon/teyit damgası). İkisi de SINIRDA `date` ile çözülür ve aşağıdaki
  python primitive'lerine **argüman olarak** geçer (modüller saat okumaz).

## 2. Projeleri SIRAYLA listele

`run_sweep`'in dolaşacağı sırayı (portfolio.json `projects` sırası) önden gör:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "
import json, os
from scripts.orchestration import portfolio_runner as pr
slugs = [p['slug'] for p in pr.list_projects(os.environ['PSEO_WORKSPACE_ROOT'])]
print(json.dumps(slugs))
"
```

Liste boşsa (portföy yok) → DURUR, `/pseo-init` öner. Aksi halde bu slug'ları **bu sırayla**
işleyeceksin (Bölüm 3).

## 3. Sweep döngüsü — her proje SIRAYLA (lock → reserve → /pseo-run → confirm)

`run_sweep`'in saf çekirdeği bir `run_project_fn(slug, workflow)` ENJEKTE eder. **Üretimde
`run_project_fn` = MEVCUT tek-proje `/pseo-run <workflow> <slug>` akışıdır** (model MCP işini
yapar + tek-proje sürücüsü doğrular/commit'ler + bir coverage kaydı döndürür). Tarama bunu
yeniden-implemente ETMEZ; `/pseo-run`'ı OLDUĞU GİBİ tüketir.

Her slug için **SIRAYLA** şu adımları uygula. Önce kilit dizinini hazırla:

```bash
mkdir -p "$PSEO_WORKSPACE_ROOT/shared/locks"
```

### 3.a — Kilidi dene (NON-BLOCKING) + bütçe preflight (kill-switch)

Aşağıdaki python primitive'i: (1) projenin run-kilidini **bloklamadan** dener — başka yerde
çalışıyorsa `SKIP` basıp ÇIKAR (proje ATLANIR, beklenmez); (2) kilit alındıysa workflow'un
tahmini maliyetini her kaynak için 4a defterine **rezerve eder**; bir rezervasyon tavanı
aşarsa kısmi rezervasyonları **serbest bırakır**, `KILL <resource>` basar ve taramayı
**DURDURUR** (bu projeyi `paused`, kalanları `not_run` say). `RESERVED <json>` basarsa
preflight geçti → 3.b'ye devam et. **`FD`'yi bu kilit `python3 -c` süreci tutamaz** (süreç
çıkınca flock serbest kalır) — bu yüzden kilit teyidini ve rezervasyonu burada yap, sonra
3.b'de `/pseo-run`'ı koştur; kesintisiz kilit-tutma yalnız otonom tek-süreç `run_sweep`
yolundadır (Bölüm 6).

```bash
SLUG="<slug>" WF="$WF" PERIOD="$PERIOD" NOW_ISO="$NOW_ISO" \
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "
import json, os
from scripts.orchestration import portfolio_runner as pr
from scripts.state import cost_ledger, project_lock
ws = os.environ['PSEO_WORKSPACE_ROOT']
slug, wf = os.environ['SLUG'], os.environ['WF']
period, now_iso = os.environ['PERIOD'], os.environ['NOW_ISO']
fd = project_lock.try_acquire(ws, slug)
if fd is None:
    print('SKIP already-running'); raise SystemExit(0)
try:
    est = pr.estimate_cost(ws, wf)
    made = []
    for res in ('gsc_calls', 'dfs_credits', 'image_spend'):
        amt = est.get(res, 0.0)
        if amt <= 0:
            continue
        ceil = cost_ledger.read_ceiling(ws, res)
        ceil = float('inf') if ceil is None else float(ceil)
        try:
            e = cost_ledger.reserve(ws, resource=res, period=period, amount=amt,
                                    ceiling=ceil, run_id='portfolio-'+slug,
                                    project_id=slug, now_iso=now_iso)
        except cost_ledger.CostCeilingExceeded as exc:
            for r in made:
                cost_ledger.release(ws, reservation_id=r['reservation_id'],
                                    run_id='portfolio-'+slug, project_id=slug, now_iso=now_iso)
            print('KILL ' + exc.resource); raise SystemExit(0)
        made.append({'resource': res, 'reservation_id': e['reservation_id'], 'reserved': amt})
    print('RESERVED ' + json.dumps(made))
finally:
    project_lock.release(fd)
"
```

- `SKIP …` → projeyi `skipped` listesine ekle (Türkçe: "zaten başka bir oturumda çalışıyor —
  atlandı"), **sonraki projeye** geç.
- `KILL <resource>` → projeyi `paused` say (Türkçe: "bütçe tavanı aşıldı (`<resource>`)"),
  **kalan tüm projeleri `not_run`** say ve **DURDUR** (Bölüm 4'e atla).
- `RESERVED <json>` → preflight geçti; `<json>` rezervasyon listesini sakla, 3.b'ye geç.

### 3.b — Tek-proje workflow'unu koştur (`run_project_fn` = `/pseo-run`)

`RESERVED` aldığın projede **`/pseo-run <workflow> <slug>`** akışını OLDUĞU GİBİ koştur (model
MCP işini yapar, tek-proje sürücüsü doğrular/commit'ler). Çıktı **coverage kaydıdır**; mümkünse
gerçek harcamayı `actual_cost` (kaynak→sayı) olarak türet.

- `/pseo-run` hata verir / verdict `pass` değilse → projeyi `failed` say (Türkçe: "proje
  çalışması hata verdi; bütçe serbest bırakıldı"), 3.c'de rezervasyonları **release** et ve
  **sonraki projeye** geç (tek projenin hatası kill-switch DEĞİLDİR — tarama DEVAM eder).

### 3.c — Bütçeyi teyit et (confirm) / başarısızsa release

Başarılıysa her rezervasyonu gerçek harcamayla (yoksa rezerve edilen miktarla) **confirm** et;
başarısızsa **release** et. `actual_cost` JSON'unu ortam değişkeniyle geçir (yoksa `{}`):

```bash
SLUG="<slug>" PERIOD="$PERIOD" NOW_ISO="$NOW_ISO" OUTCOME="confirm" \
RESERVATIONS='<3.a RESERVED json>' ACTUAL='<actual_cost json | {}>' \
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "
import json, os
from scripts.state import cost_ledger
ws = os.environ['PSEO_WORKSPACE_ROOT']
slug, now_iso = os.environ['SLUG'], os.environ['NOW_ISO']
made = json.loads(os.environ['RESERVATIONS'])
actual = json.loads(os.environ['ACTUAL'])
outcome = os.environ['OUTCOME']  # 'confirm' (başarı) | 'release' (başarısız)
for r in made:
    rid, reserved = r['reservation_id'], r['reserved']
    if outcome == 'release':
        cost_ledger.release(ws, reservation_id=rid, run_id='portfolio-'+slug,
                            project_id=slug, now_iso=now_iso)
        continue
    v = actual.get(r['resource'])
    amt = reserved if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 else min(float(v), reserved)
    cost_ledger.confirm(ws, reservation_id=rid, amount=amt, run_id='portfolio-'+slug,
                        project_id=slug, now_iso=now_iso)
print('OK ' + outcome)
"
```

Başarılı projeyi `ran` listesine ekle. Sonraki slug'a geç (kill-switch ateşlenmediyse).

## 4. Özet — `render_summary` (Türkçe operatör yüzeyi)

Tüm projeler işlenince (ya da kill-switch DURDURDU) sonucu tek Türkçe blokla bas. Topladığın
`ran/skipped/paused/failed/not_run` listelerinden sonuç dict'ini kur ve `render_summary` ile
yazdır (kill-switch varsa **aşılan kaynağı** ve kopyala-yapıştır devam komutunu içerir):

```bash
RESULT_JSON='<topladığın sonuç dict json>' \
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "
import json, os
from scripts.orchestration import portfolio_runner as pr
print(pr.render_summary(json.loads(os.environ['RESULT_JSON'])))
"
```

Operatör (Mac app) tek bir sonraki aksiyon görür: kill-switch'te bütçe yenilenince
`/pseo-run-portfolio <workflow>` ile devam et; aksi halde tarama tamam.

## 5. Bağımlılıklar

- Saf çekirdek: `scripts/orchestration/portfolio_runner.py`
  (`run_sweep` / `estimate_cost` / `list_projects` / `render_summary`).
- Kilit: `scripts/state/project_lock.py` (`try_acquire` NON-BLOCKING / `release` / `held_lock`).
- Bütçe defteri: `scripts/state/cost_ledger.py` (4a — `reserve` / `confirm` / `release` /
  `read_ceiling`; IMPORT-only, değiştirilmez).
- Portföy kaynağı: `shared/portfolio.json` (`scripts/state/portfolio_writer.py`, 0e2 şekli).
- Tahmin kaynağı: `shared/cost-estimates.json` (operatör-elle, O5; şema YOK) —
  `{ "<workflow>": { "gsc_calls": n, "dfs_credits": n, "image_spend": n } }`.
- Tavan kaynağı: `shared/cost-ceilings.json` (operatör-elle, O5).
- Tek-proje akışı (`run_project_fn`): **`commands/pseo-run.md`** — OLDUĞU GİBİ tüketilir.

## 6. Notlar / sınırlar

- **Kilit semantiği (dürüst):** Saf `run_sweep` her projenin kilidini, senkron `run_project_fn`
  çağrısı BOYUNCA tutar (otonom Faz-4 yolu — SCRIPTED `run_project_fn` ile tek süreç → tam
  garanti). İnteraktif recipe'te `run_project_fn` model-sürümlüdür (`/pseo-run`); bir flock model
  turları arasında tutulamaz (her `python3 -c` ayrı süreçtir), bu yüzden kilit **sınırda** (3.a
  alma anında) kontrol edilir — o an başka bir sweep/bağlı oturum tutuyorsa proje ATLANIR. Aynı
  anda İKİ portföy taraması koşturma; paylaşılan 4a defteri yine de bütçeyi atomik korur.
- **`paused` çözünürlüğü:** kill-switch'lenen proje için bu komut per-proje coverage kaydı
  YAZMAZ — sonucu surface eder; tam resume wiring 4d/sonrası işidir.
- Bütçe defteri append-only + hash-zincirli + flock-atomiktir → paralel bağlı oturumlar global
  tavanı asla birlikte aşamaz (4a garantisi).
