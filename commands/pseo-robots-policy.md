---
description: |
  Use when: kullanıcı "robots.txt audit", "noindex denetimi", "robots policy", "noindex deploy edilmiş mi", "disallow + noindex çakışması", "ON_HOLD içerik indexleniyor", "robots.txt lint", "site-wide disallow" der ya da `/pseo-robots-policy` çağırırsa.
  Also use when: aktif projenin Screaming Frog export'u alındı (`projects/{slug}/sf-exports/{date}/raw/directives_all.csv`); içerik lifecycle (new_content_plan.lifecycle_status) noindex deployment'ı doğrulanacak; canlı robots.txt fetch + lint + R-58/R-133 drift kontrol; bulgular master.xlsx#robots_txt'ye RP- prefix'li yazılacak + önerilen robots.txt artifact üretilecek.
  Do not use when: faceted-nav / parametre denetimi (`/pseo-facet-audit`, ayrı); tek-URL retire (`content-remediation` skill, ayrı — bu komut SONUCU doğrular, retire ETMEZ); SF export yok (`sf-import` önce); master.xlsx yokken (`/pseo-init` önce).
argument-hint: "<project-slug> [--sf-export-date YYYY-MM-DD] [--no-fetch-live] [--sample-header-urls N]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(ls:*), Bash(head:*), Bash(sort:*), Read
model: sonnet
---

# /pseo-robots-policy — robots.txt & noindex Lifecycle Audit

> **Skill:** `skills/discovery/robots-policy-audit/SKILL.md` (GAP-T3, wip). Canlı robots.txt GET + SF `directives_all.csv` → `robots_policy_transform.py` pure compute → master.xlsx#robots_txt RP- rows (via `scripts/util/sheet_merge.py`) + outputs/reports/{date}-robots-policy-audit.md + outputs/robots/{date}-robots.proposed.txt + events.jsonl + onay gate. **FREE**. **Recommendation-only** — operatör uygular.

## 1. Aktif projeyi çöz

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else SF_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/sf-exports"; LATEST=$(ls -1 "$SF_DIR" 2>/dev/null | sort -r | head -1); echo "active=$PROJECT sf_export=${LATEST:-MISSING (önce sf-import)}"; fi; fi`

## 2. Skill chain

`skills/discovery/robots-policy-audit/SKILL.md` protokolü koşar:

1. Canlı `https://{domain}/robots.txt` GET (Scrapling; public dosya okuması, consent gate yok). Erişilemezse **AMBER** → file-only devam (never hard fail).
2. `sf-exports/{date}/raw/directives_all.csv` + `internal_all.csv` read
3. master.xlsx#new_content_plan read (url_slug + lifecycle_status) → R-58 drift kontrolü
4. (optional) facet-nav-audit önerilen robots bloğu feed-in
5. Pure compute: `scripts/discovery/robots_policy_transform.py` — robots.txt lint (noindex satırı / eksik Sitemap / site-wide Disallow / unknown), R-133 noindex-disallow çakışması, R-58 lifecycle drift (ON_HOLD indexlenebilir / REMOVED hâlâ canlı), önemli-sayfa koruması; önerilen robots.txt + platform deployment matrisi üretir
6. Onay gate (workflow-run.schema awaiting_approval)
7. master.xlsx#robots_txt'ye `sheet_merge.merge_prefixed_rows(id_prefix="RP-")` ile yaz (idempotent; R-/FN-/HF- korunur)
8. `outputs/robots/{date}-robots.proposed.txt` plain write + events.jsonl `source.kind=sf_csv` + `outputs/reports/{date}-robots-policy-audit.md` render via `templates/reports/robots-policy-audit.template.md`

DURUR (6 sentinel): directives_all.csv yok / new_content_plan unreadable / önerilen dosya `/` disallow ederdi / directives Address kolonu yok (drift) / robots_txt row schema mismatch / PSEO_WORKSPACE_ROOT unset. **AMBER (DURUR değil):** canlı fetch erişilemez.

## 3. Çalıştırma notları

- **FREE** — paid MCP yok (Scrapling GET ücretsiz).
- **Recommendation-only** (per tech-seo-governance robots.txt-policy rules) — motor robots.txt / CMS / sunucuya YAZMAZ; önerilen robots.txt `outputs/robots/{date}-robots.proposed.txt` artifact'ı + raporda metin olarak üretilir, operatör uygular.
- **Scope fence:** content-remediation tek-URL retire'ı (301/410) sahiplenir; bu komut lifecycle SONUÇLARINI doğrular, retire ETMEZ.
- `--no-fetch-live` — canlı GET'i kapatır (file-only).
- Doğrulanamayan platformlar (Ticimax/Ideasoft/imagaza) deployment talimatında `UNVERIFIED` işaretlenir — menü yolu uydurulmaz, operatör doğrular.
- sf-import `transaction.replace` robots_txt sheet'i sıfırlar → her sf-import sonrası bu audit'i yeniden çalıştır.

## 4. Bağımlılıklar

- Skill: `skills/discovery/robots-policy-audit/SKILL.md` (GAP-T3, wip)
- Scripts: `scripts/discovery/robots_policy_transform.py` + `scripts/util/sheet_merge.py` + `scripts/state/events_writer.py` (`append_provenance`) + `scripts/orchestration/committer.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/robots-policy-audit.template.md`
- Rules: `rules/tech-seo-governance.md` (governed robots.txt policy / noindex deployment path / mutual exclusion) + `rules/content-html-discipline.md` (R-58 lifecycle robots-meta)
- Schemas: `schemas/master-excel.schema.json#robots_txt` + `#new_content_plan` + `schemas/events.schema.json`
- MCP (**skill-level**): `mcp__ScraplingServer__get` (optional, free — canlı robots.txt fetch)
- Upstream: `init-project` (master.xlsx) + `sf-import` (`directives_all.csv`) + `new-content-plan` (#new_content_plan) + `facet-nav-audit` (önerilen blok, optional)
- Downstream: `content-remediation` (lifecycle retire) + `drift-check`
