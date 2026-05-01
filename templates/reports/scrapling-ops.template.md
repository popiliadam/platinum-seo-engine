# Scrapling Ops — $project_slug

**Tarih:** $date
**Senaryo:** $scenario

## Özet

Tier-escalation orchestration (get → fetch → stealthy_fetch). Generic helper, per-scenario sub-schema'lar Phase 7+ skill'lerle yazılır (ADR-025).

- **URL count:** $url_count
- **Max URLs cap:** $max_urls

## Tier dağılımı

$tier_distribution

> Format: `tier_0_get=N, tier_1_fetch=M, tier_2_stealthy=K, failed=F`

## Kanıt zinciri

- Raw HTML/markdown payload: `inbox/scrapling/$date-{tier}-$project_slug.json`
- Staging output: `$staging_path`
- Run ID: `$run_id`

> Üretildi: `scrapling-ops` skill — `scripts/ingestion/scrapling_ops.py`
> Tier ladder canonical (schemas/scrapling-output-mapping.schema.json §14.5): immutable.
