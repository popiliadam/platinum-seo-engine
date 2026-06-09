---
description: |
  Use when: kullanıcı "portföy durumu", "hepsinin durumu", "tüm projeler ne durumda",
  "portföy triyajı", "portfolio status", "nelere bakmam lazım", "bütçe ne durumda" der
  ya da `/pseo-status-portfolio [period]` çağırır.
  Also use when: bir oturumun başında TÜM portföyü tek bakışta triyaj etmek gerekir —
  hangi projeler sağlıklı, hangileri bir adımı EKSİK (iç → yeniden çalıştır), hangileri
  iç geçitte BAŞARISIZ (düzelt + yeniden çalıştır) ve hangileri DIŞ bir bağımlılığa
  (bütçe tükendi / GSC-DFS kesintisi) takılıp DURAKLATILDI — artı bugünün GLOBAL bütçesi
  ne kadar harcandı (gsc_calls / dfs_credits / image_spend).
  Do not use when: TEK projenin workflow run state'i (`/pseo-status [slug]` — bu komut
  onun portföy-geneli READ-ONLY karşılığıdır); yeni proje (`/pseo-init`); portföyü
  çalıştırma (`/pseo-run-portfolio`); drift kontrolü (`/pseo-driftcheck`); rapor
  (`/pseo-monthly`). Bu komut HİÇBİR ŞEY YAZMAZ — yalnız okur.
argument-hint: "[period]"
allowed-tools: Bash(python3:*), Bash(date:*), Bash(find:*), Bash(sort:*), Bash(tail:*), Bash(xargs:*), Read
model: sonnet
---

# /pseo-status-portfolio — Portföy Durum Triyajı (Faz-4, READ-ONLY)

Tüm portföyü tek Türkçe blokla triyaj et: her projenin EN SON coverage kaydından durumunu
(sağlıklı / eksik / başarısız / duraklatıldı / kayıt yok) çıkar ve GLOBAL 4a bütçesinin
(gsc_calls / dfs_credits / image_spend) kullanım/tavan/kalan özetini göster.

> **Saf + READ-ONLY çekirdek:** `scripts/reporting/portfolio_status.py`
> (`build_triage` / `render_triage`). `period` (4a defteri partition anahtarı) DIŞARIDAN
> geçilir — modül saat OKUMAZ. Modül HİÇBİR durum yazmaz: yalnız coverage kayıtlarını +
> maliyet defterini + `shared/portfolio.json`'u okur. Dış-vs-iç ayrımı coverage
> `verdict`'inden gelir (paused=dış bağımlılık, failed/incomplete=iç) — workflow-run kaydı
> okunmaz. Bu, mevcut tek-proje `/pseo-status`'un portföy-geneli karşılığıdır.

## 1. Workspace + period çöz (sınırda)

`$1` verilmişse `period` = o; yoksa `period` = bugünün UTC tarihi (`date -u +%Y-%m-%d`).
Period SINIRDA çözülür ve aşağıdaki python primitive'ine **argüman olarak** geçer.

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş — kullanıcıya workspace path'ini sor"; else PERIOD="${1:-$(date -u +%Y-%m-%d)}"; echo "workspace=$PSEO_WORKSPACE_ROOT period=$PERIOD"; fi`

Çıktı `ERROR: ...` ise: kullanıcıdan workspace path'ini iste; aşağıdaki adımı atla.

## 2. Triyajı üret + Türkçe bloğu bas

Engine root'u çöz (`CLAUDE_PLUGIN_ROOT` yoksa fallback) ve `build_triage` + `render_triage`'ı
inline `python3` ile çağır. Bu adım yalnız OKUR — hiçbir yazma, hiçbir MCP çağrısı yok:

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; exit 2; fi; ENGINE_ROOT="${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache 2>/dev/null -type d -name 'platinum-seo-engine' | sort | tail -1 | xargs -I{} find {} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -V | tail -1)}}"; if [ -z "$ENGINE_ROOT" ]; then echo "ERROR: CLAUDE_PLUGIN_ROOT yok ve fallback bulunamadı — PSEO_ENGINE_ROOT env var set edin"; exit 3; fi; PERIOD="${1:-$(date -u +%Y-%m-%d)}"; PSEO_ENGINE_ROOT="$ENGINE_ROOT" PYTHONPATH="$ENGINE_ROOT" PERIOD="$PERIOD" python3 -c "
import os, sys
from pathlib import Path
engine = os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('PSEO_ENGINE_ROOT')
if not engine:
    print('ERROR: engine path resolution failed', file=sys.stderr); sys.exit(3)
sys.path.insert(0, engine)
from scripts.reporting import portfolio_status as ps
ws = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
period = os.environ['PERIOD']
try:
    triage = ps.build_triage(ws, period=period)
except Exception as exc:
    print('ERROR: triyaj uretilemedi: ' + str(exc), file=sys.stderr); sys.exit(1)
if not triage['rows']:
    print('NO_PROJECTS')
else:
    print(ps.render_triage(triage))
" 2>&1`

## 3. Çıktıyı yorumla

- Türkçe blok geldiyse: olduğu gibi operatöre sun (proje triyaj tablosu + "Yapılacaklar" +
  bütçe tablosu). Her sağlıksız satır için generik bir sonraki-adım ipucu zaten blokta var:
  - **eksik** → `/pseo-run <workflow> <slug>` ile tamamla (iç, yeniden çalıştır).
  - **başarısız** → iç geçit reddetti; düzelt + `/pseo-run <workflow> <slug>` ile yeniden çalıştır.
  - **duraklatıldı** → dış bağımlılık/bütçe; yenilenince kaldığı yerden devam eder.
  - **kayıt yok** → henüz çalıştırılmadı.
- Bütçe tablosunda bir kaynakta **HATA** görürsen: maliyet defteri zinciri bozuk (fail-closed)
  — o kaynağın kullanımı güvenle raporlanamıyor; defteri incele. Diğer kaynaklar ve proje
  triyajı yine de gösterilir.
- Çıktı `NO_PROJECTS` ise: portföy boş — kullanıcıya `/pseo-init` ile bir proje başlatmasını öner.
- Çıktı `ERROR: ...` ise: mesajı operatöre ilet (workspace/engine path sorunu).

## 4. Bağımlılıklar

- Saf + READ-ONLY çekirdek: `scripts/reporting/portfolio_status.py`
  (`latest_coverage` / `classify` / `build_triage` / `render_triage`).
- Portföy kaynağı: `shared/portfolio.json` (`scripts/orchestration/portfolio_runner.list_projects`).
- Coverage kayıtları: `projects/{slug}/_state/coverage/{run_id}.json` (batch 1a şeması).
- Bütçe defteri: `scripts/state/cost_ledger.py` (4a — `usage` / `read_ceiling`; IMPORT-only,
  yalnız okunur, asla yazılmaz).
- Tek-proje karşılığı: `commands/pseo-status.md` (değiştirilmez).
