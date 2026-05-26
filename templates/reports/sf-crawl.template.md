<!--
  Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
  Rules consumed: rules/events-writer.md, rules/append-only-state.md
-->
# SF MCP Crawl — $project_slug

**Tarih:** $date
**Crawl ID:** `$crawl_id`
**Run ID:** `$run_id`

## Özet

Screaming Frog 24 native MCP üzerinden tetiklenen crawl + 24-rapor export pipeline (Tier 1 14 + Tier 2 10). sf-import skill subprocess olarak çağırıldı; master.xlsx'in 6 SF-türevi sheet'i güncellendi.

- **Exported rapor sayısı:** $exported_count / 24
- **AMBER warning sayısı:** $amber_count
- **Total süre:** $total_duration

## 24 Reports Status

| Tier | Toplam | Exported | Failed | Missing |
|------|--------|----------|--------|---------|
| Tier 1 (Required) | 14 | $tier1_exported | $tier1_failed | $tier1_missing |
| Tier 2 (Recommended) | 10 | $tier2_exported | $tier2_failed | $tier2_missing |
| **TOTAL** | **24** | **$exported_count** | **$total_failed** | **$total_missing** |

## Tier 1 / Tier 2 Counts

- **Tier 1 RED gate:** $tier1_status (14/14 zorunlu)
- **Tier 2 AMBER policy:** $tier2_status (eksikler warning olarak loglanır, run fail etmez)

## AMBER Warnings

$amber_warnings

## sf-import Handoff Result

- **Subprocess exit code:** $sf_import_exit_code
- **Source run_id chained:** `$run_id` → sf-import provenance
- **Master.xlsx sheet update:** $sf_import_sheet_summary

## Total Duration

| Adım | Süre |
|------|------|
| Preflight + crawl_trigger | $duration_preflight |
| Polling (sf_crawl_progress) | $duration_poll |
| Export 24 raporu | $duration_export |
| Atomic move + sf-import handoff | $duration_handoff |
| **TOPLAM** | **$total_duration** |

## Recommendations

$recommendations

## Kanıt zinciri

- Envelope JSON: `inbox/sf-mcp/$date-sf-crawl-$project_slug.json`
- Workflow state: `_state/workflows/$run_id.json`
- Raw CSV export: `sf-exports/$date/raw/` (24 dosya)
- Provenance event: `events.jsonl` (source.kind=sf_mcp, run_id=$run_id)

> Üretildi: `sf-crawl-orchestrator` skill (v1.8 Phase 3) — `skills/ingestion/sf-crawl-orchestrator/SKILL.md`
> SF MCP native tools: sf_crawl + sf_crawl_progress + sf_generate_report + sf_list_allowed_base_directory
> Companion skill: `sf-import` (master.xlsx projection downstream)
