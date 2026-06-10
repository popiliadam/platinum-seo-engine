---
description: |
  Use when: kullanıcı "bu session'ı bağla", "bind", "session bağla", "bu projeyi bu pencereye kilitle", "paralel proje" der ya da `/pseo-bind <slug>` çağırırsa.
  Also use when: aynı anda 3-5 projeyi ayrı Claude session'larında (VS Code / Mac app / CLI) yürütürken her session'ın HANGI projeye ait olduğunu session UUID'sine göre işaretlemek (cross-contamination önleme); marker `shared/sessions/<session-id>.json` yazılacak.
  Do not use when: portföy-geneli aktif projeyi set etme (`/pseo-active` — bu shared/active.json yazar, session'a özel değil), yeni proje açma (`/pseo-init`) ya da durum görme (`/pseo-status`).
argument-hint: "<project-slug> [--workspace <path>]"
allowed-tools: Bash(python3:*), Bash(ls:*), Read
model: sonnet
---

# /pseo-bind — Bu Session'ı Bir Projeye Bağla

Bu Claude session'ını (session UUID'sine göre) tek bir SEO projesine bağlar. Marker dosyası `{workspace}/shared/sessions/<session-id>.json` olarak yazılır; ileride bir SessionStart hook'u (batch 0c) aynı UUID ile bu marker'ı okuyup session'ın hangi projeye ait olduğunu çözer. Böylece 3-5 proje ayrı pencerelerde paralel yürütülürken birbirine karışmaz. Session bağlı değilse çözümleme `shared/active.json`'a düşer (regresyon yok).

`shared/active.json` (`/pseo-active`) portföy-geneli tek pointer'dır; `/pseo-bind` ise **bu session'a özeldir** — ikisi çakışmaz, marker active.json'ı YEDEKLER (override eder, silmez).

## 1. Argüman zorunlu

`$1` slug ZORUNLU. Eksikse DURDUR ve kullanımı göster:

!`set -- $ARGUMENTS; if [ -z "$1" ]; then echo "MISSING_SLUG: usage /pseo-bind <project-slug> [--workspace <path>]"; echo "ipucu: slug = projects/<slug>/project.config.json olan bir proje"; fi`

## 2. Bind komutunu çalıştır

`$1` verildiyse primitive CLI'yi çağır. `--workspace` opsiyoneldir: ilk seferinde bir kez geçilirse `~/.config/pseo/config.json`'a kalıcı yazılır (editör-bağımsız), sonraki çağrılarda gerek kalmaz. CLI sırasıyla: workspace root'u çözer (config → `$PSEO_WORKSPACE_ROOT`), session UUID'sini `$CLAUDE_CODE_SESSION_ID`'den alır, `projects/<slug>/project.config.json` var mı doğrular, sonra marker'ı atomik yazar (tempfile + fsync + os.replace).

!`cd "$CLAUDE_PLUGIN_ROOT" && python3 -m scripts.state.session_binding bind $ARGUMENTS 2>&1`

Başarılı çıktı tek satırlık banner'dır, örn:

```
bound session a1b2c3d4 → vento  (/path/to/workspace/shared/sessions/<uuid>.json)
```

Hata durumları (non-zero exit) ve anlamı:
- `no workspace root` → `--workspace <path>` ile bir kez yol geç (ya da `$PSEO_WORKSPACE_ROOT` set et).
- `no $CLAUDE_CODE_SESSION_ID` → komut bir Claude session'ı içinden çalışmıyor.
- `project.config.json not found` → slug yanlış; `ls projects/` ile doğrula, gerekirse `/pseo-init <slug>`.

## 3. Sonraki adım

Marker yazıldıktan sonra `/pseo-status` çağırarak bu session'a bağlı projenin workflow run'larını listele. Aynı UUID ile çalışan sonraki komutlar/hook'lar artık otomatik bu projeyi hedefler.

## 4. Notlar

- Marker shape: `schemas/session-marker.schema.json` (active_project + bound_at + session_id, additionalProperties:false).
- Atomik yazma: tempfile + fsync + os.replace + parent dir fsync (transaction.py::_atomic_save ile aynı disiplin).
- Engine root `$CLAUDE_PLUGIN_ROOT`'tan alınır; cwd'den TÜRETME (batch 0a: güvenilmez).
- Argüman aktarımı: `$ARGUMENTS` **tırnaksız** argparse'a verilir (`bind $ARGUMENTS`). Claude Code `$ARGUMENTS`'ı blok kaynağına metin-ikamesi yapar; boşluklu `--workspace` yolu kullanıcının tırnaklarıyla tek argüman kalır, argparse (slug + `--workspace`) parser'dır. `"$ARGUMENTS"` / `eval`+`shlex` `set --` reparse / `"$1" "${2:-}"` KULLANMA — text-sub altında tırnakları bozar ve boş `"${2:-}"` argparse'a "unrecognized arguments" verir (finding #13).
- `shared/sessions/` workspace-geneldir (active.json'ın yanında), per-proje `_state/` ALTINDA DEĞİL.
