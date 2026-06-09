---
description: |
  Use when: kullanıcı "drift", "drift kontrol", "tutarsızlık", "schema kontrol", "cross-sheet invariant", "tutarlılık raporu" der ya da `/pseo-driftcheck` çağırırsa.
  Also use when: master.xlsx'e büyük bir ingestion (sf-import, gsc-pull, dfs-pull, sf-crawl-orchestrator) sonrası logical sheet'ler arasındaki cross-sheet invariant kuralları (cross-sheet-invariants.json'da 32 declared; validate_invariants.py implement edilmiş 25'ini koşar) doğrulanmak isteniyor; rule pack veya plugin yükseltmesi sonrası schema sürüm hizalaması test ediliyor.
  Do not use when: tek bir JSON dosyası schema'ya uyuyor mu kontrolü (`scripts/validation/validate_schema.py` direkt CLI), rapor üretimi (`/pseo-monthly`), aktif workflow durumu (`/pseo-status`) gerekiyorsa.
argument-hint: "[project-slug]"
allowed-tools: Bash(python3:*), Bash(jq:*), Bash(ls:*), Read
model: sonnet
---

# /pseo-driftcheck — Cross-Sheet Invariants & Schema Validation

> **Skill:** `skills/governance/drift-check/SKILL.md` (Phase 5, aktif; v1.8 Phase 4 F-23 land).
> Master.xlsx full sweep + cross-sheet invariant (32 declared / 25 implemented) + consistency raporu üretir.

## 1. Aktif proje

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. Skill chain

`skills/governance/drift-check/SKILL.md` şu adımları koşar (spec §11.2 + §7):

1. Aktif projenin `master.xlsx` dosyasını `schemas/master-excel.schema.json`'a karşı validate et
2. `schemas/cross-sheet-invariants.json` 32 cross-sheet kural DECLARE eder; `scripts/validation/validate_invariants.py` bunların implement edilmiş 25'ini koşturur (referential integrity, sayım eşitlikleri, durum tutarlılığı; v1.8 Phase 4'te F-23 SF MCP cross-sheet invariant eklendi: sf-crawl-orchestrator run varsa `mcp-tool-registry.json`'da `sf` entry zorunlu)
3. `consistency-report.schema.json` formatında rapor üret (`outputs/reports/{date}-drift.md` + `_state/reports/{date}-drift.json`)
4. RED → uyarı + auto-fix önerisi; AMBER → not + rapor; GREEN → `events.jsonl` → `drift_clean`

**Örnek F-23 ihlali:** `_state/workflows/2026-05-27-abc123.json` `skill=sf-crawl-orchestrator` ama `mcp-tool-registry.json` `sf` entry içermiyor → severity=HIGH RED, drift-check raporu "F-23: SF MCP registry mismatch — workflow detected but server not registered".

## 3. Tek-dosya schema validation (helper)

İhtiyaç duyulduğunda `scripts/validation/validate_schema.py` CLI doğrudan çağrılabilir: `validate_schema.py <data.json> <schema.json>` (exit 0 = geçer, 1 = hata; stdout boş, stderr insan-okunur).

Quick check — aktif projenin `project.config.json`'unun schema'ya uyup uymadığı:

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "skip: PSEO_WORKSPACE_ROOT set edilmemiş"; else WS="$PSEO_WORKSPACE_ROOT"; PROJECT="${1:-$(jq -r '.active_project // empty' "$WS/shared/active.json" 2>/dev/null)}"; CFG="$WS/projects/$PROJECT/project.config.json"; SCHEMA="${CLAUDE_PLUGIN_ROOT}/schemas/project-config.schema.json"; if [ -z "$PROJECT" ]; then echo "skip: NO_ACTIVE_PROJECT"; elif [ ! -f "$CFG" ]; then echo "skip: $CFG yok (önce /pseo-init)"; else python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validation/validate_schema.py" "$CFG" "$SCHEMA" && echo "GREEN: project.config.json schema'ya uyuyor" || echo "RED: schema validation FAIL (yukarıdaki stderr)"; fi; fi`

## 4. Bağımlılıklar

- `skills/governance/drift-check/SKILL.md` — aktif (Phase 5)
- `scripts/validation/validate_invariants.py` — implement edilmiş 25 cross-sheet kuralı (5 CRITICAL + 14 HIGH + 6 MEDIUM; F-23 SF MCP cross-sheet HIGH dahil); cross-sheet-invariants.json toplam 32 kural DECLARE eder (engine self-governance F-29..F-34 narrative label'ları henüz function olarak implement edilmemiş) + `build_consistency_report()` (consistency-report.schema.json üretimi, Draft7Validator inline)
- `scripts/reporting/render_template.py` — drift markdown render
- `templates/reports/drift.template.md` — markdown template
