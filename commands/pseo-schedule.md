---
description: |
  Use when: kullanıcı "zamanla", "schedule", "otomatik çalıştır", "tekrarlayan tarama",
  "zamanlanmış görev", "scheduler", "arm/disarm" der ya da `/pseo-schedule [status|arm|disarm]
  [workflow] [cadence]` çağırır.
  Also use when: Faz-4 portföy taramasını (`/pseo-run-portfolio`) OPSİYONEL tekrarlayan bir
  programa bağlamak / durumunu görmek / kapatmak istiyorsun. Scheduler VARSAYILAN KAPALI; armed
  yapmak için TÜM bütçe tavanları set olmalı (O5 fail-closed) VE operatör THIS cadence + öngörülen
  maliyeti AÇIKÇA onaylamalı (per-cadence consent). Bu komut hiçbir şeyi ATEŞLEMEZ — periyodik
  tetikleyici HARİCİdir (4e recovery runbook'a bak); D11 gereği yalnız tek kapsamlı canlı-kabul
  koşusundan SONRA armed yapılır.
  Do not use when: portföyü ŞİMDİ bir kez taramak (`/pseo-run-portfolio <workflow>`); bütçe
  tavanı düzenleme (shared/cost-ceilings.json elle); tek proje çalıştırma (`/pseo-run`); workflow
  durum listesi (`/pseo-status`). Bu komut yalnız ARM / DISARM / STATUS yüzeyidir — tarayıcı DEĞİL.
argument-hint: "[status|arm|disarm] [workflow] [cadence]"
allowed-tools: Bash(python3:*), Bash(date:*), Bash(find:*), Bash(sort:*), Bash(tail:*), Bash(xargs:*), Read, Write
model: sonnet
---

# /pseo-schedule — Zamanlanmış Tarama Yüzeyi (Faz-4, VARSAYILAN KAPALI)

> **Scheduler default OFF (spec §7 Faz-4 + §8).** Faz-4 operatörün tüm portföyü tek bütçe tavanı
> altında taramasına izin verir (`/pseo-run-portfolio`, 4b). Son otonomi adımı OPSİYONEL tekrarlayan
> bir programdır — ama gözetimsiz para harcayabilen otonomi tehlikelidir, bu yüzden program
> **varsayılan KAPALI**, yalnız bir **maliyet geçidi** ardında armed edilir ve **kendisi hiçbir şeyi
> ATEŞLEMEZ**. Gerçek periyodik tetikleyici **HARİCİdir** (4e recovery runbook). D11 gereği operatör
> yalnız **tek kapsamlı canlı-kabul** koşusundan sonra armed yapar.
>
> **Üç yönlü arm geçidi:** (1) **O5 FAIL-CLOSED** — üç bütçe tavanının (gsc_calls / dfs_credits /
> image_spend, `shared/cost-ceilings.json`) HEPSİ set olmalı; biri bile boşsa `arm` **REDDEDER ve
> hiçbir şey yazmaz** (4b'nin "tavan boş → ∞ sınırsız" davranışı insan-gözetimli MANUEL tarama için
> uygundur ama armed gözetimsiz program için DEĞİL). (2) **CONSENT** — operatör THIS cadence + maliyeti
> AÇIKÇA onaylar (`consent_ack=True`); sessiz re-arm yok. (3) **TRANSPARENCY** — armed marker operatörün
> gördüğü `projected_daily_cost`'u kaydeder.
>
> **Saf çekirdek:** `scripts/state/schedule.py` — `now_iso` SINIRDA `date -u` ile çözülür (modül saat
> OKUMAZ). Marker = GLOBAL `shared/schedule.json` (mutable pointer; absent = disarmed). Bütçe okuması:
> `scripts/state/cost_ledger.read_ceiling` (4a). Maliyet matematiği: `portfolio_runner.list_projects` +
> `estimate_cost` (4b). Bu komut spine'ı / sürücüleri / defteri / `/pseo-run-portfolio`'yu DEĞİŞTİRMEZ.

## 0. Alt-komut + workspace + engine root

`$1` = alt-komut (`status` | `arm` | `disarm`; boşsa **`status`**). `arm` için `$2`=workflow
(`monthly|audit|setup|content`), `$3`=cadence (`daily|weekly|monthly`).

Her aşağıdaki blok kendi içinde workspace + engine-root çözer (her `python3 -c` ayrı süreçtir):
`$PSEO_WORKSPACE_ROOT` set değilse **DURUR** (operatöre bildir). Engine root:
`${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-<plugin cache fallback>}}`.

## 1. `status` (varsayılan) — mevcut programı Türkçe göster

Hangi alt-komut olursa olsun **önce** mevcut durumu göster (`read_schedule`; absent dosya = disarmed):

```bash
if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; exit 2; fi
ENGINE_ROOT="${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache 2>/dev/null -type d -name 'platinum-seo-engine' | sort | tail -1 | xargs -I{} find {} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -V | tail -1)}}"
if [ -z "$ENGINE_ROOT" ]; then echo "ERROR: engine root bulunamadı — PSEO_ENGINE_ROOT set edin"; exit 3; fi
PSEO_ENGINE_ROOT="$ENGINE_ROOT" PYTHONPATH="$ENGINE_ROOT" python3 -c "
import os, sys
from pathlib import Path
engine = os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('PSEO_ENGINE_ROOT')
sys.path.insert(0, engine)
from scripts.state import schedule
ws = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
m = schedule.read_schedule(ws)
if not m.get('armed'):
    print('Zamanlanmış görev YOK (varsayılan KAPALI).')
else:
    cost = m.get('projected_daily_cost', {})
    cost_str = ', '.join(str(k) + ': ' + str(v) for k, v in cost.items()) or '(tahmin yok)'
    print('Zamanlanmış görev AÇIK (armed):')
    print('  workflow : ' + str(m.get('workflow')))
    print('  cadence  : ' + str(m.get('cadence')))
    print('  armed_at : ' + str(m.get('armed_at')))
    print('  öngörülen GÜNLÜK maliyet: ' + cost_str)
"
```

`status` alt-komutuysa burada DUR. Çıktıyı operatöre olduğu gibi Türkçe sun.

## 2. `arm <workflow> <cadence>` — maliyet geçidi + per-cadence consent

### 2.a — Önizleme: O5 geçidi + öngörülen maliyet (HENÜZ ARM ETME)

Önce tavanları + öngörülen maliyeti hesapla. Bir tavan boşsa **O5 fail-closed yüzeyi** devreye girer:

```bash
if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; exit 2; fi
ENGINE_ROOT="${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache 2>/dev/null -type d -name 'platinum-seo-engine' | sort | tail -1 | xargs -I{} find {} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -V | tail -1)}}"
if [ -z "$ENGINE_ROOT" ]; then echo "ERROR: engine root bulunamadı — PSEO_ENGINE_ROOT set edin"; exit 3; fi
WF="$2" CAD="$3" PSEO_ENGINE_ROOT="$ENGINE_ROOT" PYTHONPATH="$ENGINE_ROOT" python3 -c "
import json, os, sys
from pathlib import Path
engine = os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('PSEO_ENGINE_ROOT')
sys.path.insert(0, engine)
from scripts.state import schedule
ws = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
wf, cad = os.environ.get('WF', ''), os.environ.get('CAD', '')
try:
    cost = schedule.projected_cost(ws, workflow=wf, cadence=cad)
except schedule.ScheduleValidationError as exc:
    print('GECERSIZ ' + str(exc)); raise SystemExit(0)
ok, missing = schedule.all_ceilings_set(ws)
if not ok:
    print('REFUSED ' + json.dumps(missing)); raise SystemExit(0)
print('OK ' + json.dumps(cost, ensure_ascii=False))
"
```

Çıktıya göre:

- **`GECERSIZ …`** → workflow/cadence geçersiz. Operatöre geçerli set'i söyle
  (workflow: `monthly|audit|setup|content`, cadence: `daily|weekly|monthly`), **arm etme**, DUR.
- **`REFUSED ["dfs_credits", …]`** → **O5 fail-closed**. Operatöre Türkçe bildir: gözetimsiz bir
  program, bütçe tavanı set edilmeden armed EDİLEMEZ; şu kaynak(lar)ın tavanı boş: `<isimler>`. Çözüm:
  `shared/cost-ceilings.json` içine her kaynak için sayısal tavan gir (örn.
  `{"gsc_calls": 1000, "dfs_credits": 500, "image_spend": 50}`), sonra tekrar dene. **ARM ETME**, DUR.
- **`OK {"project_count":N,"per_sweep":{…},"per_day":{…}}`** → geçit geçti. 2.b'ye geç.

### 2.b — Öngörülen maliyeti SUN + AÇIK onay BEKLE (per-cadence consent)

`OK` aldıysan operatöre **net Türkçe** sun: `project_count`, her kaynak için **tarama-başı** (`per_sweep`)
ve **öngörülen GÜNLÜK** (`per_day`) maliyet + seçilen `workflow` + `cadence`. Sonra **AÇIKÇA onay iste**:

> "Bu cadence (`<cadence>`) + öngörülen günlük maliyeti onaylıyor musun? Onaylarsan program armed olur
> (gözetimsiz). Devam? (evet / hayır)"

**ASLA aynı turda hem maliyeti göster hem arm et.** Operatörün açık **"evet"**ini BEKLE. "hayır" /
yanıtsız → arm etme, DUR. Bu açık onay = `consent_ack=True`'nun karşılığıdır (per-cadence consent).

### 2.c — Operatör onayladıysa arm et (consent_ack=True, now_iso SINIRDA)

Yalnız operatör **açıkça evet** dedikten SONRA çalıştır (`arm` geçidi içerde tekrar fail-close eder):

```bash
if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; exit 2; fi
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
ENGINE_ROOT="${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache 2>/dev/null -type d -name 'platinum-seo-engine' | sort | tail -1 | xargs -I{} find {} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -V | tail -1)}}"
if [ -z "$ENGINE_ROOT" ]; then echo "ERROR: engine root bulunamadı — PSEO_ENGINE_ROOT set edin"; exit 3; fi
WF="$2" CAD="$3" NOW_ISO="$NOW_ISO" PSEO_ENGINE_ROOT="$ENGINE_ROOT" PYTHONPATH="$ENGINE_ROOT" python3 -c "
import json, os, sys
from pathlib import Path
engine = os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('PSEO_ENGINE_ROOT')
sys.path.insert(0, engine)
from scripts.state import schedule
ws = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
try:
    m = schedule.arm(ws, workflow=os.environ['WF'], cadence=os.environ['CAD'],
                     now_iso=os.environ['NOW_ISO'], consent_ack=True)
except schedule.ScheduleArmRefused as exc:
    print('REFUSED ' + json.dumps(exc.missing)); raise SystemExit(0)
except schedule.ScheduleError as exc:
    print('HATA ' + str(exc)); raise SystemExit(0)
print('ARMED ' + json.dumps(m, ensure_ascii=False))
"
```

- **`ARMED {…}`** → yazılan marker'ı (`armed`, `workflow`, `cadence`, `projected_daily_cost`, `armed_at`)
  Türkçe özetle. **Hatırlat:** (1) bu komut hiçbir şeyi ATEŞLEMEZ — periyodik tetik HARİCİdir (**4e
  recovery runbook**); (2) D11 gereği yalnız tek kapsamlı canlı-kabul koşusundan sonra armed yapılır;
  (3) durdurmak için `/pseo-schedule disarm`.
- **`REFUSED […]`** → (tavan onay/önizleme arasında silindi) → 2.a'daki O5 mesajını sun, armed DEĞİL.

## 3. `disarm` — programı kapat (marker'ı yeniden yaz, silme)

```bash
if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; exit 2; fi
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
ENGINE_ROOT="${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache 2>/dev/null -type d -name 'platinum-seo-engine' | sort | tail -1 | xargs -I{} find {} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -V | tail -1)}}"
if [ -z "$ENGINE_ROOT" ]; then echo "ERROR: engine root bulunamadı — PSEO_ENGINE_ROOT set edin"; exit 3; fi
NOW_ISO="$NOW_ISO" PSEO_ENGINE_ROOT="$ENGINE_ROOT" PYTHONPATH="$ENGINE_ROOT" python3 -c "
import json, os, sys
from pathlib import Path
engine = os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('PSEO_ENGINE_ROOT')
sys.path.insert(0, engine)
from scripts.state import schedule
ws = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
m = schedule.disarm(ws, now_iso=os.environ['NOW_ISO'])
print('DISARMED ' + json.dumps(m, ensure_ascii=False))
"
```

`disarm` idempotenttir (absent / zaten-disarmed program için de sorunsuz). Operatöre Türkçe doğrula:
"Zamanlanmış görev KAPATILDI (armed=false). Tekrar açmak için `/pseo-schedule arm <workflow> <cadence>`."

## 4. Bağımlılıklar / sınırlar

- Saf çekirdek: `scripts/state/schedule.py` (`read_schedule` / `all_ceilings_set` / `projected_cost` /
  `arm` / `disarm`) — saf + saat-okumaz (`now_iso` SINIRDA `date -u`).
- Bütçe okuması: `scripts/state/cost_ledger.read_ceiling` (4a — IMPORT-only, değiştirilmez).
- Maliyet matematiği: `scripts/orchestration/portfolio_runner.list_projects` + `estimate_cost` (4b).
- Marker: GLOBAL `shared/schedule.json` (mutable pointer; absent = disarmed; atomic os.replace yazıcı).
- **Bu komut hiçbir workflow ATEŞLEMEZ.** Periyodik tetikleyici HARİCİdir (4e recovery runbook). D11:
  armed yalnız tek kapsamlı canlı-kabulden sonra.
- Tavan kaynağı: `shared/cost-ceilings.json` (operatör-elle, O5). Tahmin kaynağı:
  `shared/cost-estimates.json` (operatör-elle). İkisi de bu komutla DEĞİL, elle düzenlenir.
