---
description: |
  Use when: kullanıcı "yeni proje", "init", "proje kur", "yeni domain ekle", "scaffold" gibi ifadeler kullanır ya da `/pseo-init` çağırırsa.
  Also use when: portföye yeni bir SEO projesi alındı, `projects/{slug}/` klasörü ve `project.config.json` dosyasının schemaya uygun ilk hâli üretilecek; brief'te slug + domain + market biliniyor.
  Do not use when: mevcut bir projeye yeni veri yüklemek (`/pseo-status` veya ingestion skill'leri), aylık rapor (`/pseo-monthly`) ya da drift kontrol (`/pseo-driftcheck`) gerekiyorsa — her biri ayrı komut/skill ile çalışır.
argument-hint: "<slug> [domain] [--market TR] [--locale tr-TR] [--profile local-service] [--schema-version 1.5] [--dry-run]"
allowed-tools: Bash(python3:*), Bash(jq:*), Bash(head:*), Read
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

## 4. Tam scaffold (init-project skill)

Bu komut yalnızca `project.config.json` scaffold rolünü üstlenir. Tam workspace tree (master.xlsx kopyalama, `inbox/` + `outputs/` + `_state/` klasörler, `shared/portfolio.json` güncelleme, `project_created` event'i, GSC validation, approval gate) `skills/meta/init-project/SKILL.md` (Phase 5, aktif) tarafından sürülür. Brief'te "tam init" ihtiyacı varsa skill'i çağır; sadece config dosyası lazımsa bu komut yeterli.

## 5. Schema version (v1.8 NEW)

Default `--schema-version=1.5` (v1.8 Phase 1 — project-config v1.4→v1.5; additive `sf` block). `bootstrap_project.py` post-Phase-1 native olarak 1.5 emit ediyor; Migration 0005 cascade legacy v1.4 workspace'lerde init-project Step 4.5'te otomatik tetiklenir (idempotent on already-1.5 docs). Legacy zorlamak gerekirse `--schema-version=1.4` explicitly geçilir (deprecated path; v1.9'da kaldırılması planlanır).

`sf` block default: `{ mcp: { enabled: false, url: "http://127.0.0.1:11435/mcp", allowed_directory: "/Users/apple/seo_spider_mcp_server", max_wait_minutes: 180, per_report_timeout_seconds: 300 } }` (D-SF-12 + D-SF-18 path parameterization; operator project-bazlı override edebilir).

## 6. Bağımlılıklar

- Skill: `skills/meta/init-project/SKILL.md` — aktif (Phase 5 W2; v1.8 Phase 4 Migration 0005 cascade Step 4.5 eklendi)
- Script: `scripts/state/bootstrap_project.py` (CLI + `SCHEMA_VERSION` sync; v1.8 Phase 1 SCHEMA_VERSION 1.4→1.5)
- Migration: `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py` (v1.8 Phase 1; idempotent + .bak)
- MCP optional: `mcp__gsc__list_sites` (`--gsc-site-url` verildiğinde GSC ownership verify)
- Templates: `templates/master-excel.xlsx` (idempotent re-bootstrap KORUNUR — F1 workbook policy)
- Schemas: `schemas/project-config.schema.json` (v1.5, content_locale field + sf block)
- Output: `projects/{slug}/project.config.json` + (skill ile) master.xlsx + `shared/portfolio.json` append + `_state/events.jsonl` `project_created` event
