---
description: |
  Use when: kullanıcı "drift", "drift kontrol", "tutarsızlık", "schema kontrol", "cross-sheet invariant", "tutarlılık raporu" der ya da `/pseo-driftcheck` çağırırsa.
  Also use when: master.xlsx'e büyük bir ingestion (sf-import, gsc-pull, dfs-pull) sonrası logical sheet'ler arasındaki 20 invariant kuralı (cross-sheet-invariants.json) doğrulanmak isteniyor; rule pack veya plugin yükseltmesi sonrası schema sürüm hizalaması test ediliyor.
  Do not use when: tek bir JSON dosyası schema'ya uyuyor mu kontrolü (`scripts/validation/validate_schema.py` direkt CLI), rapor üretimi (`/pseo-monthly`), aktif workflow durumu (`/pseo-status`) gerekiyorsa.
argument-hint: "[project-slug]"
allowed-tools: Bash(python3:*), Bash(jq:*), Bash(ls:*), Read
model: sonnet
---

# /pseo-driftcheck — Cross-Sheet Invariants & Schema Validation

> **Skill:** `skills/governance/drift-check/SKILL.md` (Phase 5, aktif).
> Master.xlsx full sweep + 20 cross-sheet invariant + consistency raporu üretir.

## 1. Aktif proje

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. Skill chain

`skills/governance/drift-check/SKILL.md` şu adımları koşar (spec §11.2 + §7):

1. Aktif projenin `master.xlsx` dosyasını `schemas/master-excel.schema.json`'a karşı validate et
2. `schemas/cross-sheet-invariants.json`'daki 20 governance kuralını `scripts/validation/validate_invariants.py` ile koştur (referential integrity, sayım eşitlikleri, durum tutarlılığı)
3. `consistency-report.schema.json` formatında rapor üret (`outputs/reports/{date}-drift.md` + `_state/reports/{date}-drift.json`)
4. RED → uyarı + auto-fix önerisi; AMBER → not + rapor; GREEN → `events.jsonl` → `drift_clean`

## 3. Tek-dosya schema validation (helper)

İhtiyaç duyulduğunda `scripts/validation/validate_schema.py` CLI doğrudan çağrılabilir: `validate_schema.py <data.json> <schema.json>` (exit 0 = geçer, 1 = hata; stdout boş, stderr insan-okunur).

Quick check — aktif projenin `project.config.json`'unun schema'ya uyup uymadığı:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "skip: PSEO_WORKSPACE_ROOT set edilmemiş"; else WS="$PSEO_WORKSPACE_ROOT"; PROJECT="${1:-$(jq -r '.active_project // empty' "$WS/shared/active.json" 2>/dev/null)}"; CFG="$WS/projects/$PROJECT/project.config.json"; SCHEMA="${CLAUDE_PLUGIN_ROOT}/schemas/project-config.schema.json"; if [ -z "$PROJECT" ]; then echo "skip: NO_ACTIVE_PROJECT"; elif [ ! -f "$CFG" ]; then echo "skip: $CFG yok (önce /pseo-init)"; else python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validation/validate_schema.py" "$CFG" "$SCHEMA" && echo "GREEN: project.config.json schema'ya uyuyor" || echo "RED: schema validation FAIL (yukarıdaki stderr)"; fi; fi`

## 4. Bağımlılıklar

- `skills/governance/drift-check/SKILL.md` — aktif (Phase 5)
- `scripts/validation/validate_invariants.py` — 20 cross-sheet kuralı
- `scripts/validation/drift_report.py` — `consistency-report.schema.json` üretimi
- `templates/reports/drift.template.md` — markdown render
