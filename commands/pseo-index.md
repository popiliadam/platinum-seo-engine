---
description: |
  Use when: kullanıcı "indeksle", "Google'a bildir", "indexing api gönder", "URL_UPDATED", "sayfayı dizine gönder", "kaldırılan sayfayı bildir" der ya da `/pseo-index` çağırırsa.
  Also use when: yeni/güncellenen sayfalar yayına alındı ve Google + Bing/Yandex'e bildirilecek; elle `_index_*.py` script'i yazılmak üzere (yazılmaz — bu komut kullanılır).
  Do not use when: sayfa henüz yayında değil (canlı kontrol zaten atlar); sitemap gönderimi (`mcp__gsc__submit_sitemap`); indekslenme ÖLÇÜMÜ (`verify-indexing`).
argument-hint: "<project-slug> URL [URL ...] [--type URL_UPDATED|URL_DELETED] [--expect TEXT] [--cap N] [--dry-run]"
allowed-tools: Bash(python3:*), Read
model: sonnet
---

# /pseo-index — Indexing API + IndexNow, tek resmi yol (S-01)

> **Skill:** `skills/publishing/indexing-ping/SKILL.md`. **Script:** `scripts/production/indexing_submit.py`. Karar (2026-10-13): Indexing API tüm sayfalar için kullanılır; Google dokümanının API'yi JobPosting/BroadcastEvent ile sınırladığı bilinerek alındı.

## 1. Çalıştır

!`R=""; for c in "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PROJECT_DIR" "$PWD" "$HOME"/.claude/plugins/*/*/*/* "$HOME"/.claude/plugins/*/*/*; do [ -n "$c" ] && [ -f "$c/scripts/production/indexing_submit.py" ] && { R="$c"; break; }; done; [ -n "$R" ] || { echo "PLUGIN_ROOT_UNRESOLVED: scripts/production/indexing_submit.py bulunamadı"; exit 2; }; PYTHONPATH="$R" python3 -m scripts.production.indexing_submit submit $ARGUMENTS 2>&1`

## 2. Ne yapar

1. **Canlı kontrol** — her URL Googlebot UA ile çekilir. URL_UPDATED: HTTP 200, canonical kendisi (ya da yok), `noindex` yok; `--expect "metin"` verilirse yeni metin sayfada olmalı. URL_DELETED: 404/410. Geçmeyen URL gönderilmez, nedeni rapora yazılır.
2. **Günlük kota** — proje başına varsayılan 200/gün (`--cap`). Bugünkü raporlar sayılır; taşan URL'ler `_state/indexing_queue.json` kuyruğuna girer ve bir sonraki çalıştırmada önce gider.
3. **Onay** — URL_UPDATED onay istemez. URL_DELETED için bu oturumda `/pseo-approve <run_id> index_update <url>` gerekir (son 1 saat).
4. **IndexNow** — `INDEXNOW_KEY` ortamda varsa aynı URL'ler Bing/Yandex'e de bildirilir.
5. **Kayıt** — `outputs/indexing/{tarih}-{saat}-submission.json` (her URL: canlı kontrol sonucu, Google HTTP kodu, kuyruk).

Google'ın bir URL için tuttuğu son bildirim zamanı:

```bash
python3 scripts/production/indexing_submit.py status <project-slug> <url>
```

## 3. Notlar

- HTTP 200 = Google bildirimi aldı; **indekslendi demek değildir** (ölçüm: `verify-indexing`).
- Kimlik: servis hesabı `GOOGLE_INDEXING_SA` (varsayılan `~/.config/seo-core/secrets/google-indexing.json`); `google-auth` paketi gerekir.
- `--dry-run` hiçbir şey göndermez ve yazmaz; yalnız canlı kontrolü gösterir.
- Projelerde elle `_index_*.py` yazılmaz; eskileri `outputs/_archive/`'a taşınır.
