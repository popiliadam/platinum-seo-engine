---
description: |
  Use when: kullanıcı "migration map", "redirect map", "site taşıma", "URL değişikliği", "301 haritası", "domain taşıma", "redirect planı", "migration verify", "redirect doğrula" der ya da `/pseo-migration-map` çağırırsa.
  Also use when: bir site/CMS/domain taşıması planlanıyor; eski-site Screaming Frog crawl inventory'si alındı (`projects/{slug}/sf-exports/{date}/raw/internal_all.csv`); operatör bir `projects/{slug}/migration/{date}-url-mapping.csv` (+ opsiyonel `*-mapping-rules.json`) sağladı; bulgular master.xlsx#redirect_404'e key=url merge ile yazılacak (plan) veya post-launch crawl ile doğrulanacak (verify); 301 haritası + sunucu-config snippet'leri + faz-geçit checklist raporda üretilecek (recommendation-only).
  Do not use when: tek-URL retire/sunset (`content-remediation`, R-90/R-91 — bu komut BULK harita yapar); SF export yok (`sf-import` önce, DURUR); robots.txt/noindex denetimi (`/pseo-robots-policy`); master.xlsx yokken (`/pseo-init` önce); GSC sitemap submit / Change-of-Address (operatör-only).
argument-hint: "<project-slug> --mode plan|verify [--mapping-csv path] [--sf-export-date YYYY-MM-DD] [--homepage-collapse-pct N]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(ls:*), Bash(head:*), Bash(sort:*), Read
model: sonnet
---

# /pseo-migration-map — Site-Migration Redirect Map

> **Skill:** `skills/planning/migration-map/SKILL.md` (GAP-T4, wip). Eski-site SF `internal_all.csv` + operatör mapping seed → `migration_map_transform.build_map` pure compute → master.xlsx#redirect_404 (key=url merge via `scripts/util/sheet_merge.py`) + outputs/reports/{date}-migration-map.md (sunucu-config snippet'leri + faz-geçit checklist) + events.jsonl provenance + onay gate. **Verify** modu post-launch crawl'dan single-hop-301→200 doğrular. **FREE** (paid MCP yok). **Recommendation-only** — operatör uygular.

## 1. Aktif projeyi çöz

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else SF_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/sf-exports"; LATEST=$(ls -1 "$SF_DIR" 2>/dev/null | sort -r | head -1); MIG_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/migration"; SEED=$(ls -1 "$MIG_DIR"/*url-mapping.csv 2>/dev/null | sort -r | head -1); echo "active=$PROJECT sf_export=${LATEST:-MISSING (önce sf-import)} mapping_seed=${SEED:-MISSING (operatör url-mapping.csv sağlamalı)}"; fi; fi`

## 2. Skill chain

`skills/planning/migration-map/SKILL.md` protokolü koşar (`--mode` zorunlu):

**plan modu:**
1. master.xlsx + `sf-exports/{date}/raw/internal_all.csv` (eski-site inventory: Address + Inlinks) read
2. `projects/{slug}/migration/{date}-url-mapping.csv` (old_url,new_url,action) + opsiyonel `*-mapping-rules.json` (`schemas/migration-mapping.schema.json` ile validate) read
3. master.xlsx#gsc_performance read → trafik-kritik koruma (url/clicks)
4. Pure compute: `scripts/planning/migration_map_transform.build_map` — explicit pair + sıralı regex kural full inventory üzerinde expand; lint (döngü/self-redirect=RED, zincir>3hop, anasayfa-çökme %, trafik-kritik eşlenmemiş); hiçbir URL sessizce düşürülmez
5. Onay gate (workflow-run.schema awaiting_approval)
6. master.xlsx#redirect_404'e `sheet_merge.merge_keyed_rows(key_column="url")` ile yaz (idempotent; foreign sf_projection satırları korunur)
7. events.jsonl append: `event_kind=provenance + operation=project_excel + source.kind=sf_csv`
8. `outputs/reports/{date}-migration-map.md` render via `templates/reports/migration-map.template.md`

**verify modu:**
- post-launch `redirect_chains.csv` + `response_codes_all.csv` read → `migration_map_transform.verify_map` → her 301 satırı için old→single-hop-301→200 doğrula (302-leak / zincir>3 / 4xx-5xx regresyon / anasayfa-drift bulguları); eşleşen `redirect_404` satırlarının `status`'unu `DONE` yap; rapor + rollback önerisi.
- operatör "deploy edildi" derse → `events_writer.append_work(event_type="redirect_deployed")` (onaya bağlı, **asla otonom değil**).

DURUR (7 sentinel): mode plan/verify değil / internal_all.csv yok (plan) / mapping seed yok (plan) / redirect_chains.csv yok veya Address kolonu yok (verify, schema drift) / redirect_404 row schema mismatch / haritada döngü-self-redirect (RED) / PSEO_WORKSPACE_ROOT unset.

## 3. Çalıştırma notları

- **FREE** — paid MCP yok; trafik koruması master.xlsx#gsc_performance'tan okunur (GSC çağrıları cost-0 + opsiyonel).
- **Recommendation-only** (per tech-seo-governance migration rules) — motor htaccess/nginx/platform'a YAZMAZ, `mcp__gsc__submit_sitemap` ÇAĞIRMAZ, Change-of-Address tetiklemez; bunlar raporda öneri metni + operatör-checklist.
- **Scope fence** — bu komut BULK harita yapar; tek-URL retire `content-remediation` (R-90/R-91) işidir.
- `--mode` zorunlu (plan|verify); geçersiz → DURUR.
- `--mapping-csv` belirtilmezse en son `projects/{slug}/migration/*-url-mapping.csv` default.
- `--sf-export-date` belirtilmezse en son `sf-exports/{date}/` dizini default (plan = eski-site, verify = post-launch).
- `--homepage-collapse-pct` (default 5) — 301 hedeflerinin anasayfaya çökme eşiği; aşılırsa HIGH.
- sf-import `transaction.replace` redirect_404 sheet'i sıfırlar → her sf-import sonrası bu skill'i yeniden çalıştır.

## 4. Bağımlılıklar

- Skill: `skills/planning/migration-map/SKILL.md` (GAP-T4, wip)
- Scripts: `scripts/planning/migration_map_transform.py` + `scripts/util/sheet_merge.py` (`merge_keyed_rows`) + `scripts/state/events_writer.py` (`append_provenance` / `append_work`) + `scripts/orchestration/committer.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/migration-map.template.md`
- Rules: `rules/tech-seo-governance.md` (migration redirect-map contract / phase gate / post-migration verification) + `rules/content-update-discipline.md` (R-91 scope fence)
- Schemas: `schemas/master-excel.schema.json#redirect_404` + `schemas/migration-mapping.schema.json` + `schemas/events.schema.json` (`redirect_deployed`)
- Upstream: `init-project` (master.xlsx) + `sf-import` (`sf-exports/{date}/raw/internal_all.csv` + `redirect_chains.csv` + `response_codes_all.csv`) + `gsc-pull` (#gsc_performance) + operatör `migration/{date}-url-mapping.csv`
- Downstream: `master-task-sync` (follow-up task'lar, `primary_source: "redirect_404"`) + `indexing-ping` (sitemap-submit önerisi, consent-gated) + `drift-check`
