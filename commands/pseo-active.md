---
description: |
  Use when: kullanıcı "aktif proje", "switch", "geç", "set active", "şu projeye geç", "context değiştir" der ya da `/pseo-active <slug>` çağırırsa.
  Also use when: portföyde birden fazla proje var ve sonraki komutların (`/pseo-status`, `/pseo-quickwin`, `/pseo-monthly`, `/pseo-driftcheck`) hangi projeye uygulanacağını belirten `shared/active.json` marker'ı set edilecek.
  Do not use when: yeni bir proje açma (`/pseo-init`), aktif projenin durumunu görme (`/pseo-status`) ya da tek seferlik bir komuta slug'ı argüman olarak doğrudan geçirmek yeterliyse.
argument-hint: "<slug>"
allowed-tools: Bash(python3:*), Bash(jq:*), Bash(ls:*), Bash(mkdir:*), Read
model: sonnet
---

# /pseo-active — Aktif Proje Marker'ı Set Et

`shared/active.json` marker dosyasını `{"active_project": "<slug>", "updated_at": "<UTC ISO 8601>"}` olarak yazar. Diğer komutlar slug verilmediğinde bu dosyadan okur.

## 1. Argüman zorunlu

`$1` slug ZORUNLU; eksikse mevcut marker'ı oku ve listele:

!`set -- $ARGUMENTS; if [ -z "$1" ]; then if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "MISSING_SLUG + NO_WORKSPACE_ROOT: usage /pseo-active <slug> (önce PSEO_WORKSPACE_ROOT env var set et)"; else WS="$PSEO_WORKSPACE_ROOT"; CURRENT=$(jq -r '.active_project // "<unset>"' "$WS/shared/active.json" 2>/dev/null || echo "<no-file>"); echo "MISSING_SLUG: usage /pseo-active <slug>"; echo "current active: $CURRENT"; echo "available projects:"; ls -1 "$WS/projects" 2>/dev/null || echo "  (no projects dir)"; fi; fi`

## 2. Slug doğrulama + marker yazma

`$1` verildiyse: workspace altında `projects/{slug}/project.config.json` var mı kontrol et, yoksa DURDUR (marker'ı YAZMA, `/pseo-init` öner); varsa `shared/active.json`'u atomik yaz (UTC ISO 8601 timestamp ile). Append-only state disiplini bu marker dosyasını HARİÇ TUTAR — `shared/active.json` deliberately mutable bir pointer'dır (rules/append-only-state.md sadece `_state/events.jsonl` ve workflow run JSON'ları için zorlayıcı; `shared/` portföy-genelinde yaşar).

!`set -- $ARGUMENTS; SLUG="$1"; if [ -n "$SLUG" ]; then if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else WS="$PSEO_WORKSPACE_ROOT"; CFG="$WS/projects/$SLUG/project.config.json"; if [ ! -f "$CFG" ]; then echo "HATA: $CFG yok — önce '/pseo-init $SLUG' çalıştır. Marker YAZILMADI."; exit 1; fi; mkdir -p "$WS/shared"; SLUG="$SLUG" python3 -c "
import json, os, re, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
slug = os.environ['SLUG']
if not re.fullmatch(r'[a-z][a-z0-9-]*', slug):
    print('ERROR: invalid slug (must start with a letter; lowercase alnum + hyphen): ' + repr(slug), file=sys.stderr)
    sys.exit(2)
ws = Path(os.environ['PSEO_WORKSPACE_ROOT']).expanduser()
target = ws / 'shared' / 'active.json'
target.parent.mkdir(parents=True, exist_ok=True)
payload = {'active_project': slug,
           'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
tmp_fd, tmp_name = tempfile.mkstemp(prefix='.active-', suffix='.json.tmp', dir=str(target.parent))
os.close(tmp_fd)
tmp_path = Path(tmp_name)
with tmp_path.open('w', encoding='utf-8') as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
    fh.flush(); os.fsync(fh.fileno())
os.replace(str(tmp_path), str(target))
print(f'active_project set → {slug} ({target})')
"; fi; fi`

## 3. Sonraki adım

Marker yazıldıktan sonra `/pseo-status` çağırarak yeni aktif projenin workflow run'larını listele. Slug yanlış yazıldıysa `ls projects/` çıktısını oku ve düzelt.

## 4. Notlar

- `shared/active.json` portföy-genelinde tek satırlık pointer; geri-uyumluluk için `active_project` field'ı zorunludur (spec §3 dir tree).
- Atomik yazma: tempfile + fsync + os.replace pattern'i (workflow_runner.py ile aynı disiplin).
- Marker'ın geçmişi tutulmaz; "geçmişte hangi projedeydim" sorusu için `_state/events.jsonl` `project_switched` event'leri Phase 5+ skill'lerinde emit edilebilir (henüz yok).
