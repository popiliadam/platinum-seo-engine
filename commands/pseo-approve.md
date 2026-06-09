---
description: |
  Use when: kullanıcı "onayla", "approve", "izin ver", "consent", "şu aksiyona izin" der ya da `/pseo-approve <run_id> <action> <target>` çağırırsa.
  Also use when: bir AMO run'ı geri-alınamaz/dışa-dönük bir aksiyon (git push / silme / POST / GSC sitemap submit / Indexing URL_UPDATED / oversized DFS) için operatör onayı bekliyor; consent defterine `projects/{slug}/_state/consent.jsonl` hash-chained bir satır yazılacak.
  Do not use when: aksiyonu fiilen çalıştırma (gate 2b kontrol eder), session bağlama (`/pseo-bind`), portföy-geneli aktif proje set etme (`/pseo-active`) ya da durum görme (`/pseo-status`).
argument-hint: "<run_id> <action> <target>"
allowed-tools: Bash(python3:*), Bash(ls:*), Read
model: sonnet
---

# /pseo-approve — Bir Aksiyona Operatör Onayı Ver

Geri-alınamaz veya dışa-dönük bir aksiyon için operatör onayını **append-only, hash-chained** bir deftere (`{workspace}/projects/<slug>/_state/consent.jsonl`) yazar. Onay BU session'a bağlı projeye kaydedilir (`/pseo-bind` ile bağlanan). Her satır bir önceki satırın hash'ini taşır (tamper-evident): forge/yeniden-yazma/sıra-değiştirme zinciri kırar ve reddedilir.

Bu komut aksiyonu **çalıştırmaz** — sadece izni KAYDEDER. Gate (batch 2b) bir aksiyonu çalıştırmadan önce hedefi hash'leyip `has_consent(run_id, action, target_hash)` sorar; eşleşen sağlam-zincirli bir kayıt yoksa REDDEDER. Yani bu kayıt, gate'in aksiyona izin vermesinin ÖN ŞARTIDIR.

## 1. Geçerli `action` değerleri (6 sınıf)

`$2` aşağıdakilerden biri OLMALI:

- `git_push` — `git push`
- `fs_delete` — `rm` / `unlink` / `rmdir` / `shred`
- `net_post` — dışa-dönük `curl`/`wget` POST (exfil yüzeyi)
- `mcp_submit` — bir MCP submit aracı (ör. `mcp__gsc__submit_sitemap`)
- `index_update` — Google Indexing-API `URL_UPDATED` (Süleyman'ın sert onay şartı)
- `dfs_oversized` — boyut sınırını aşan bir DataForSEO isteği

## 2. Argümanlar zorunlu

`$1` run_id, `$2` action, `$3` target ZORUNLU. Eksikse DURDUR ve kullanımı göster:

!`eval "set -- $(python3 -c 'import shlex,sys;print(" ".join(shlex.quote(a) for a in shlex.split(sys.argv[1])))' "$ARGUMENTS")"; if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then echo "MISSING_ARGS: usage /pseo-approve <run_id> <action> <target>"; echo "action ∈ {git_push, fs_delete, net_post, mcp_submit, index_update, dfs_oversized}"; echo "örnek: /pseo-approve vento-2026-06-06-ab12 index_update https://vento.example/sitemap.xml"; fi`

## 3. Onay komutunu çalıştır

Üç argüman da verildiyse recorder CLI'yi çağır. CLI sırasıyla: action'ı doğrular, workspace root'u çözer (config → `$PSEO_WORKSPACE_ROOT`), session UUID'sini `$CLAUDE_CODE_SESSION_ID`'den alır, bu session'a bağlı projeyi çözer (`shared/sessions/<uuid>.json` → `shared/active.json`), sonra deftere atomik (O_APPEND + flock + fsync) bir satır ekler.

!`eval "set -- $(python3 -c 'import shlex,sys;print(" ".join(shlex.quote(a) for a in shlex.split(sys.argv[1])))' "$ARGUMENTS")"; cd "$CLAUDE_PLUGIN_ROOT" && python3 -m scripts.state.consent_ledger approve "$1" "$2" "$3" 2>&1`

Başarılı çıktı tek satırlık banner'dır, örn:

```
consent recorded: index_update on https://vento.example/sitemap.xml for vento-2026-06-06-ab12  (seq 0)
```

Hata durumları (non-zero exit) ve anlamı:
- `unknown action` → `$2` 6 geçerli değerden biri değil; yukarıdaki listeden seç.
- `no project bound to this session` → bu session bir projeye bağlı değil; önce `/pseo-bind <slug>` çalıştır.
- `no workspace root` → `--workspace <path>` ile bir kez yol geç (ya da `$PSEO_WORKSPACE_ROOT` set et).

## 4. Notlar

- Onay BU session'ın bağlı projesine yazılır; başka bir projeyi onaylamak için önce o session'ı `/pseo-bind` ile bağla.
- Defter shape: `schemas/consent.schema.json` (seq + run_id + action + target_hash + granted_at + granted_by + prev_hash + entry_hash, additionalProperties:false).
- Append-only LOG: O_APPEND + flock + fsync (events.jsonl disiplini); `os.replace` KULLANILMAZ — marker değil, defter.
- Engine root `$CLAUDE_PLUGIN_ROOT`'tan alınır; cwd'den TÜRETME (batch 0a: güvenilmez).
- Kayıt yazıldıktan SONRA gate (batch 2b) aksiyona izin verir; bu komut tek başına aksiyonu çalıştırmaz.
