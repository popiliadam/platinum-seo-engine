---
description: |
  Use when: kullanıcı "yeni proje", "init", "proje kur", "yeni domain ekle", "scaffold" gibi ifadeler kullanır ya da `/pseo-init` çağırırsa.
  Also use when: portföye yeni bir SEO projesi alındı, `projects/{slug}/` klasörü ve `project.config.json` dosyasının schemaya uygun ilk hâli üretilecek; brief'te slug + domain + market biliniyor.
  Do not use when: mevcut bir projeye yeni veri yüklemek (`/pseo-status` veya ingestion skill'leri), aylık rapor (`/pseo-monthly`) ya da drift kontrol (`/pseo-driftcheck`) gerekiyorsa — her biri ayrı komut/skill ile çalışır.
argument-hint: "<slug> [domain] [--market TR] [--locale tr-TR] [--profile local-service] [--dry-run]"
allowed-tools: Bash(python3:*), Bash(jq:*), Read
model: sonnet
---

# /pseo-init — Yeni Proje Pack Scaffolder

Workspace altında `projects/{slug}/project.config.json` üretir; `scripts/state/bootstrap_project.py`'yi sarar (CLI gerçek flag listesi: `--project`, `--display-name`, `--domain`, `--market`, `--locale`, `--currency`, `--platform`, `--platform-seo-plugin`, `--profile`, `--ymyl-level`, `--gsc-site-url`, `--dfs-location-code`, `--dfs-language-code`, `--dfs-location-name`, `--out`, `--dry-run`, `--force`).

## 1. Argüman normalizasyonu

`$1` slug zorunlu; eksikse kullanıcıdan iste ve dur. `$2` opsiyonel domain (örn. `https://example.com/`).

İlk arg kontrolü: !`if [ -z "$1" ]; then echo "MISSING_SLUG: usage /pseo-init <slug> [domain] [extra-flags]"; else echo "slug=$1 args=$ARGUMENTS"; fi`

## 2. bootstrap_project.py çağrısı

CLI flag'lerini `$ARGUMENTS`'tan parse et. Slug'ı `--project` olarak ilk argümandan al; domain `$2` verildiyse `--domain` ekle. Diğer flag'ler kullanıcı brief'inde varsa düz `$ARGUMENTS` üzerinden geçirilebilir.

Dry-run önizleme (commit etmeden JSON üretip stdout'a yazar):

!`if [ -n "$1" ]; then DOMAIN_FLAG=""; if [ -n "$2" ] && [[ "$2" != --* ]]; then DOMAIN_FLAG="--domain $2"; fi; PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state/bootstrap_project.py" --project "$1" $DOMAIN_FLAG --dry-run 2>&1 | head -60; fi`

Çıktıyı kullanıcıya sun ve onay iste. Onay alınana kadar `--dry-run` olmadan çağırma.

## 3. Onaydan sonra gerçek yazma

Onay sonrası (kullanıcı "evet"/"yaz"/"commit" derse) aynı argümanları `--dry-run` olmadan tekrar çağır. `--force` yalnızca kullanıcı açıkça mevcut dosyayı ezmek istiyorsa eklenir.

Workspace root resolution: `PSEO_WORKSPACE_ROOT` env var → yoksa kullanıcıya hatırlat (`~/Documents/platinum-seo-engine` default'u workspace değil engine repo'sudur; gerçek workspace ayrı bir klasördür).

## 4. Phase 5+ tamamlayıcı adımlar (stub)

`scripts/state/bootstrap_project.py` yalnızca `project.config.json` üretir. Spec §11.2 `init-project` skill'inin diğer adımları (master.xlsx kopyalama, `inbox/`, `outputs/`, `_state/` klasörleri açma, `shared/portfolio.json` güncelleme, `project_created` event'i, GSC validation, approval gate) Phase 5'te `skills/meta/init-project/SKILL.md` yazılınca aktif olacak. Bu komut o zamana kadar yalnızca config scaffolder rolünü üstlenir.
