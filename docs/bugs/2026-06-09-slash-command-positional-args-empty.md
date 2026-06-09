# BUG: Slash-komutlarında `$1/$2/$3` pozisyonel argümanları `!`bash`` bloklarında BOŞ geliyor

**Tarih:** 2026-06-09
**Önem:** HIGH (consent/binding komutları sessizce yanlış/boş argümanla çalışıyor)
**Durum:** OPEN — düzeltme bekliyor
**Repo:** platinum-seo-engine (engine)

---

## Özet (tek cümle)

`commands/*.md` içindeki `!`…`` (komut-yükleme anında ön-çalışan) bash bloklarında `$1`, `$2`, `$3`
pozisyonel argümanları Claude Code tarafından **yerine konmuyor**; bash bunları kendi (boş) pozisyonel
parametresi olarak görüp boş string'e genişletiyor. Sonuç: kullanıcı `/pseo-bind demo-dental` yazsa bile
alttaki CLI `session_binding bind ""` olarak çağrılıyor ve `invalid slug (… ''):` hatası dönüyor.

## Tekrar üretme (REPRO)

1. `/pseo-bind demo-dental` çalıştır.
2. Beklenen: `bound session <id> → demo-dental`.
3. Gerçekleşen:
   ```
   error: invalid slug (must match ^[a-z][a-z0-9-]*$): ''
   Shell command failed for pattern "!`cd "$CLAUDE_PLUGIN_ROOT" && python3 -m scripts.state.session_binding bind ""   2>&1`"
   ```
   Dikkat: argüman `demo-dental` verilmesine rağmen komut `bind ""` (boş) olarak genişledi; `$2 $3` de boşa düştü.

## Kök neden

- `!`…`` blokları komut **yüklenirken** bir shell'de ön-çalıştırılır. Bu shell'e Claude Code yalnızca
  `$ARGUMENTS` (tüm argümanlar tek string) değişkenini geçiriyor; `$1/$2/$3` pozisyonel parametrelerini
  **set etmiyor / string-ikamesi yapmıyor**. Dolayısıyla bash `$1` → `""` üretir.
- Kanıt: aynı repoda `$ARGUMENTS` kullanan komutlar (`pseo-init`, `pseo-cannibalization`) çalışıyor;
  `$1` kullanan bloklar boş alıyor. CLI'nin kendisi sağlam — elle `python3 -m scripts.state.session_binding bind demo-dental`
  başarıyla marker yazıyor (`shared/sessions/<uuid>.json`). Yani hata SADECE komut markdown'ının argüman
  referansında.

## Etkilenen dosyalar (aynı anti-pattern)

`!`bash`` bloğu İÇİNDE `$1/$2/$3` kullanan TÜM komutlar — hepsi aynı şekilde bozuk:

| Dosya | Satır | Sorunlu ifade |
|-------|-------|---------------|
| `commands/pseo-bind.md` | 21, 27 | `bind "$1" $2 $3` |
| `commands/pseo-approve.md` | 32, 38 | `approve "$1" "$2" "$3"` (consent ledger — yüksek risk) |
| `commands/pseo-active.md` | 19, 25 | `SLUG="$1"` |
| `commands/pseo-init.md` | 27 | `"$1" … "$2"` (ama `$ARGUMENTS`'ı da kullanıyor — kısmi) |
| `commands/pseo-new-blog.md` | 19 | `"$1" … "$2" … "$3"` |
| `commands/pseo-whats-next.md` | 19 | `${1:-…}` (graceful fallback'i var, sessizce all-projects'e düşer) |

> Not: `pseo-approve` en kritik olanı — consent defterine boş `run_id/action/target` ile satır yazma riski.
> `pseo-whats-next` "bozuk ama sessiz": `$1` boş olunca scope'u yanlışlıkla `all_projects` yapar.

## Önerilen düzeltme

`$1/$2/$3` yerine `$ARGUMENTS`'ı kaynak alıp bash içinde pozisyonel parametrelere AYIR:

```bash
# bloğun başında bir kez:
set -- $ARGUMENTS        # $ARGUMENTS'ı $1,$2,$3'e böler (basit, boşlukla ayrılmış argümanlar için)
# sonra mevcut $1/$2/$3 referansları olduğu gibi çalışır
```

Örnek — `commands/pseo-bind.md:27`:

```bash
# ÖNCE (bozuk):
!`cd "$CLAUDE_PLUGIN_ROOT" && python3 -m scripts.state.session_binding bind "$1" $2 $3 2>&1`

# SONRA (düzeltilmiş):
!`set -- $ARGUMENTS; cd "$CLAUDE_PLUGIN_ROOT" && python3 -m scripts.state.session_binding bind "$1" "${2:-}" "${3:-}" 2>&1`
```

Aynı `set -- $ARGUMENTS;` ön-eki etkilenen her `!`…`` bloğunun başına eklenmeli (satır 21, 32, 38, 19, 25, 27 …).

### Kenar durumlar / dikkat
- `--workspace <path>` gibi flag'ler boşluk içeriyorsa `set --` basit ayırma yeterli; path'te boşluk varsa
  kullanıcı tırnaklamalı — `$ARGUMENTS` tırnakları korumaz, bu yüzden flag-parse eden `pseo-init` zaten
  `case "$ARGUMENTS" in *--*)` yöntemini kullanıyor; o kalıbı bozma.
- Düzeltme sonrası her komut için boş-argüman dalını (MISSING_SLUG) da doğrula: `set --` sonrası `$1` boşsa
  mevcut MISSING_* mesajları yine çalışmalı.

## Doğrulama (düzeltme sonrası)

1. `/pseo-bind demo-dental` → `bound session <id> → demo-dental` görmeli, exit 0.
2. `/pseo-bind` (argümansız) → `MISSING_SLUG: usage …` görmeli (CLI çağrılmamalı).
3. `/pseo-active demo-furniture` ve `/pseo-approve <run> <action> <target>` de gerçek argümanlarla geçmeli.
4. Mümkünse komut-render testi (varsa `tests/` altında command-contract testi) ekle: `set -- $ARGUMENTS`
   içeren satırların `$1`'i boş bırakmadığını assert et.

## Geçici çözüm (workaround — düzeltilene kadar)

Slash-komut yerine CLI'yi doğrudan çağır:
```
python3 -m scripts.state.session_binding bind <slug>
```
(Engine repo kökünden; `$CLAUDE_CODE_SESSION_ID` session'dan otomatik gelir.)
