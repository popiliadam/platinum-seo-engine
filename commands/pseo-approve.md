---
description: |
  Use when: kullanıcı "onayla", "approve", "izin ver", "consent", "şu aksiyona izin" der ya da `/pseo-approve <run_id> <action> <target>` çağırırsa.
  Also use when: bir AMO run'ı geri-alınamaz/dışa-dönük bir aksiyon (git push / silme / POST / GSC sitemap submit / Indexing URL_UPDATED / oversized DFS) için operatör onayı bekliyor; consent defterine `projects/{slug}/_state/consent.jsonl` hash-chained bir satır yazılacak.
  Do not use when: aksiyonu fiilen çalıştırma (gate 2b kontrol eder), session bağlama (`/pseo-bind`), portföy-geneli aktif proje set etme (`/pseo-active`) ya da durum görme (`/pseo-status`).
argument-hint: "<run_id> <action> <target>"
allowed-tools: Bash(python3:*), Bash(ls:*), Read
model: sonnet
disable-model-invocation: true
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
- `index_update` — Google Indexing-API (`URL_UPDATED` serbest; yalnız `URL_DELETED` onay ister)
- `dfs_oversized` — boyut sınırını aşan bir DataForSEO isteği

## 2. Argümanlar zorunlu

`$1` run_id, `$2` action, `$3` target ZORUNLU. Eksikse DURDUR ve kullanımı göster:

!`set -- $ARGUMENTS; if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then echo "MISSING_ARGS: usage /platinum-seo-engine:pseo-approve <run_id> <action> <target>"; echo "action ∈ {git_push, fs_delete, net_post, mcp_submit, index_update, dfs_oversized}"; echo "örnek: /platinum-seo-engine:pseo-approve demo-furniture-2026-06-06-ab12 index_update https://demo-furniture.example/sitemap.xml"; fi`

## 3. Onay nasıl kaydedilir

Bu mesajı **sen** yazdığın anda `UserPromptSubmit` hook'u (`scripts/hooks/consent_from_prompt.py`) onayı deftere kendisi ekledi; sonucu hook çıktısında tek satır olarak görürsün:

```
[onay] kaydedildi: git_push → --force origin main  (proje demo, seq 3). Eylem artık bu oturumda çalıştırılabilir.
```

Claude bu komutta **hiçbir şey çalıştırmaz** ve defteri kendisi yazamaz: kapı (outward_action_gate) modelin `consent.jsonl`'a ya da onay CLI'ına her dokunuşunu reddeder (G-01). Böylece onay yalnız kullanıcının kendi mesajından gelebilir. Kısa Türkçe biçim de kabul edilir: `onay: <action> <target>`.

Hata satırları (`[onay] KAYDEDİLMEDİ: …`) ve anlamı:
- `bu oturum bir projeye bağlı değil` → önce `/pseo-bind <slug>`; onay `shared/active.json`'a düşmez (G-05).
- `unknown action` → `$2` geçerli değerlerden biri değil; yukarıdaki listeden seç.
- `workspace bulunamadı` → `/pseo-bind <slug> --workspace <yol>` ile bir kez yol geç.

Hangi eylemin onay istediği `scripts/hooks/consent_policy.json` tablosundadır (serbest / kayıtlı / onaylı); serbest ve kayıtlı eylemler bu komuta hiç ihtiyaç duymaz.

## 4. Notlar

- Onay BU session'ın bağlı projesine yazılır; başka bir projeyi onaylamak için önce o session'ı `/pseo-bind` ile bağla.
- Defter shape: `schemas/consent.schema.json` (seq + run_id + action + target_hash + granted_at + granted_by + prev_hash + entry_hash, additionalProperties:false).
- Append-only LOG: O_APPEND + flock + fsync (events.jsonl disiplini); `os.replace` KULLANILMAZ — marker değil, defter.
- Engine root `$CLAUDE_PLUGIN_ROOT`'tan alınır; cwd'den TÜRETME (batch 0a: güvenilmez).
- Argüman ayrıştırma: hook mesajın İLK satırını `shlex` ile böler, yani kullanıcının tırnakları korunur ve boşluklu bir hedef (`"/tmp/My Dir/x.json"`) tek argüman kalır; tırnaksız çok kelimeli hedef (`origin main`) boşlukla birleştirilir — kapının hash'lediği hedefle aynı metin.
- Kayıt yazıldıktan SONRA gate aksiyona izin verir; bu komut aksiyonu çalıştırmaz, defteri de yazmaz (hook yazar).
