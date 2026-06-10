---
description: |
  Use when: kullanıcı "hreflang audit", "hreflang denetimi", "i18n", "dil versiyonları", "uluslararası SEO", "x-default", "hreflang reciprocity", "tek-yönlü hreflang", "yanlış dil/bölge kodu", "en-UK" der ya da `/pseo-hreflang-audit` çağırırsa.
  Also use when: aktif projenin Screaming Frog export'u alındı (`projects/{slug}/sf-exports/{date}/raw/hreflang_all.csv`); çok-dilli bir müşteri imzalandı; bulgular master.xlsx#robots_txt'ye HF- prefix'li yazılacak. Tek dilli portföyde (tr-TR/en-CA/en-NG) ucuz hijyen kontrolü: stray hreflang yoksa NOT_APPLICABLE.
  Do not use when: faceted-nav / parametre denetimi (`/pseo-facet-audit`, ayrı); robots.txt/noindex lifecycle (`/pseo-robots-policy`, ayrı); SF export yok (`sf-import` önce, DURUR); master.xlsx yokken (`/pseo-init` önce). NOT: motor hreflang ÜRETMEZ — sadece denetler.
argument-hint: "<project-slug> [--sf-export-date YYYY-MM-DD] [--use-sf-mcp-live]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(ls:*), Bash(head:*), Bash(sort:*), Read
model: sonnet
---

# /pseo-hreflang-audit — hreflang / i18n Audit

> **Skill:** `skills/discovery/hreflang-audit/SKILL.md` (GAP-T1, wip). SF `hreflang_all.csv` → `hreflang_audit_transform.py` pure compute (reciprocity graph + kod/x-default + locale tutarlılık) → master.xlsx#robots_txt HF- rows (via `scripts/util/sheet_merge.py`) + outputs/reports/{date}-hreflang-audit.md + events.jsonl provenance + onay gate. **FREE** (paid MCP yok). **Recommendation-only** — operatör uygular. Tek dilli sitede NOT_APPLICABLE.

## 1. Aktif projeyi çöz

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else SF_DIR="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/sf-exports"; LATEST=$(ls -1 "$SF_DIR" 2>/dev/null | sort -r | head -1); echo "active=$PROJECT sf_export=${LATEST:-MISSING (önce sf-import)}"; fi; fi`

## 2. Skill chain

`skills/discovery/hreflang-audit/SKILL.md` protokolü koşar:

1. master.xlsx + `sf-exports/{date}/raw/hreflang_all.csv` (+ canonicals_all + internal_all) read
2. `project.config.json[language.content_locale]` read (R-127 locale tutarlılık)
3. Pure compute: `scripts/discovery/hreflang_audit_transform.py` — reciprocity graph (tek-yönlü çift = HIGH), kod + x-default doğrulama (permissive regex; exotic-but-valid kodları RED ETMEZ; dokümante `uk`→`gb` hatasını yakalar), dönüş hedefi noindex/self-canonical-olmayan/non-200 join (HIGH), config↔site locale uyumu (MEDIUM); HF- bulguları üretir
4. Onay gate (workflow-run.schema awaiting_approval)
5. master.xlsx#robots_txt'ye `sheet_merge.merge_prefixed_rows(id_prefix="HF-")` ile yaz (idempotent; R-/FN-/RP- satırları korunur)
6. events.jsonl append: `event_kind=provenance + operation=project_excel + source.kind=sf_csv`
7. `outputs/reports/{date}-hreflang-audit.md` render via `templates/reports/hreflang-audit.template.md`

DURUR (4 sentinel): hreflang_all.csv yok / hreflang kolonları yok (schema drift) / robots_txt row schema mismatch / PSEO_WORKSPACE_ROOT unset. **NOT bir DURUR:** tek dilli sitede sıfır hreflang → NOT_APPLICABLE (boş bulgu + rapor).

## 3. Çalıştırma notları

- **FREE** — paid MCP yok; GSC `index_inspect` opsiyonel spot-check (cost-0); GSC'de hreflang yüzeyi yok.
- **Recommendation-only** — motor hreflang/`<head>`/sitemap'e YAZMAZ, hreflang generator YOK (çok-dilli istemci + platform write access yok); bulgular rapora + master.xlsx#robots_txt'ye yazılır, operatör siteyi düzeltir.
- **Tek dilli portföy gerçeği** (tr-TR/en-CA/en-NG): sıfır hreflang → NOT_APPLICABLE (hreflang yokluğu doğru, kusur değil).
- `--use-sf-mcp-live` (opsiyonel) — `hreflang_all`'ı SF MCP'den canlı çeker (Hreflang element; AMBER fallback, never hard fail). Default: file-based.
- `--sf-export-date` belirtilmezse en son `sf-exports/{date}/` dizini default.
- sf-import `transaction.replace` robots_txt sheet'i sıfırlar → her sf-import sonrası bu audit'i yeniden çalıştır (FREE, aynı export'u okur).

## 4. Bağımlılıklar

- Skill: `skills/discovery/hreflang-audit/SKILL.md` (GAP-T1, wip)
- Scripts: `scripts/discovery/hreflang_audit_transform.py` + `scripts/util/sheet_merge.py` + `scripts/state/events_writer.py` (`append_provenance`) + `scripts/orchestration/committer.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/hreflang-audit.template.md`
- Rules: `rules/tech-seo-governance.md` (hreflang reciprocity / code & x-default validity / locale consistency)
- Schemas: `schemas/master-excel.schema.json#robots_txt`
- Upstream: `init-project` (master.xlsx + project.config) + `sf-import` (`sf-exports/{date}/raw/hreflang_all.csv`)
- Downstream: `drift-check`
