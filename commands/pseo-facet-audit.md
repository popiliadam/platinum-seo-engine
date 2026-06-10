---
description: |
  Use when: kullanıcı "facet audit", "faceted navigation", "parametre URL temizliği", "crawl budget", "index bloat", "filtre URL'leri indexleniyor", "sort/sayfalama parametreleri", "?sirala= / ?renk= URL'leri" der ya da `/pseo-facet-audit` çağırırsa.
  Also use when: aktif projenin Screaming Frog export'u alındı (`projects/{slug}/sf-exports/{date}/raw/internal_all.csv`); e-ticaret platformu (WooCommerce/Ticimax/Ideasoft/imagaza) parametre URL'leri üretiyor; index-bloat + crawl-budget triyajı; bulgular master.xlsx#robots_txt'ye FN- prefix'li yazılacak + önerilen robots.txt bloğu raporda üretilecek (recommendation-only).
  Do not use when: SF export henüz yok (`sf-import` önce, DURUR #1); robots.txt lifecycle/noindex denetimi (`/pseo-robots-policy`, ayrı); tech-audit / schema-audit / hreflang-audit gerekiyor; master.xlsx yokken (`/pseo-init` önce).
argument-hint: "<project-slug> [--sf-export-date YYYY-MM-DD] [--policy-overrides path] [--unknown-threshold N] [--use-sf-mcp-live]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(ls:*), Bash(head:*), Bash(sort:*), Read
model: sonnet
---

# /pseo-facet-audit — Faceted-Navigation & Crawl-Budget Audit

> **Skill:** `skills/discovery/facet-nav-audit/SKILL.md` (GAP-T2, wip). SF `internal_all.csv` → `facet_nav_audit_transform.py` pure compute → master.xlsx#robots_txt FN- rows (via `scripts/util/sheet_merge.py`) + outputs/reports/{date}-facet-nav-audit.md (proposed robots.txt bloğu) + events.jsonl provenance + onay gate. **FREE** (paid MCP yok). **Recommendation-only** — operatör uygular.

## 1. Aktif projeyi çöz

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else SF_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/sf-exports"; LATEST=$(ls -1 "$SF_DIR" 2>/dev/null | sort -r | head -1); echo "active=$PROJECT sf_export=${LATEST:-MISSING (önce sf-import)}"; fi; fi`

## 2. Skill chain

`skills/discovery/facet-nav-audit/SKILL.md` protokolü koşar:

1. master.xlsx + `sf-exports/{date}/raw/internal_all.csv` (+ response_codes/directives/canonicals) read
2. master.xlsx#cluster_keywords + #gsc_performance read → `demand_keywords` (volume/impressions > 0)
3. (optional) `projects/{slug}/config/facet-policy.json` read + `schemas/facet-policy.schema.json` ile validate
4. Pure compute: `scripts/discovery/facet_nav_audit_transform.py` — her URL'in query parametreleri kapalı taksonomiye sınıflanır (per tech-seo-governance parameter-taxonomy rules), sınıf bazlı index-bloat ölçülür, FN- bulguları + önerilen robots.txt bloğu üretilir
5. Onay gate (workflow-run.schema awaiting_approval)
6. master.xlsx#robots_txt'ye `sheet_merge.merge_prefixed_rows(id_prefix="FN-")` ile yaz (idempotent; R-/HF-/RP- satırları korunur)
7. events.jsonl append: `event_kind=provenance + operation=project_excel + source.kind=sf_csv`
8. `outputs/reports/{date}-facet-nav-audit.md` render via `templates/reports/facet-nav-audit.template.md`

DURUR (6 sentinel): internal_all.csv yok / Address kolonu yok (schema drift) / URL > 250k (cap) / sıfır parse edilebilir URL / robots_txt row schema mismatch / PSEO_WORKSPACE_ROOT unset.

## 3. Çalıştırma notları

- **FREE** — paid MCP yok; demand kanıtı master.xlsx'ten okunur (DFS çağrısı yok).
- **Recommendation-only** (per tech-seo-governance blocking-mechanism rules) — motor robots.txt / CMS / sunucuya YAZMAZ; önerilen robots.txt bloğu raporda metin olarak üretilir, operatör uygular.
- Platform seed sözlükleri heuristic + conservative; doğrulanamayan (Ticimax/Ideasoft/imagaza, İngilizce-dışı) parametreler `unknown` triyajına düşer — operatör `facet-policy.json` ile sınıflandırır.
- `--use-sf-mcp-live` (opsiyonel) — `internal_all`'ı SF MCP'den canlı çeker (AMBER fallback, never hard fail). Default: file-based.
- `--unknown-threshold N` (default 10) — unknown-URL sayısı bu eşiği geçince operatör-triyaj bulgusu (LOW).
- `--sf-export-date` belirtilmezse en son `sf-exports/{date}/` dizini default.
- sf-import `transaction.replace` robots_txt sheet'i sıfırlar → her sf-import sonrası bu audit'i yeniden çalıştır (FREE, aynı export'u okur).

## 4. Bağımlılıklar

- Skill: `skills/discovery/facet-nav-audit/SKILL.md` (GAP-T2, wip)
- Scripts: `scripts/discovery/facet_nav_audit_transform.py` + `scripts/util/sheet_merge.py` + `scripts/state/events_writer.py` (`append_provenance`) + `scripts/orchestration/committer.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/facet-nav-audit.template.md`
- Rules: `rules/tech-seo-governance.md` (parameter taxonomy / index-bloat budget / blocking-mechanism decision tree)
- Schemas: `schemas/master-excel.schema.json#robots_txt` + `schemas/facet-policy.schema.json`
- Upstream: `init-project` (master.xlsx) + `sf-import` (`sf-exports/{date}/raw/internal_all.csv`) + `cluster-map` (#cluster_keywords) + `gsc-pull` (#gsc_performance)
- Downstream: `robots-policy-audit` (önerilen bloğu tüketir) + `drift-check`
