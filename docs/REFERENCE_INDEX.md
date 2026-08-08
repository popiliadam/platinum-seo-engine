# Reference Index

"X için nereye bakmalı?" Q&A index. Fresh session bunu okur, sonra hedef dosyaya gider.

## Excel sheet structure?
→ `schemas/master-excel.schema.json` (Phase 1) + spec §5

## Cross-sheet rules?
→ `schemas/cross-sheet-invariants.json` (Phase 1) + spec §7

## SF reports?
→ `schemas/sf-required-reports.schema.json` (Phase 1) + spec §6

## How to write a new skill?
→ `rules/skill-description-discipline.md` (Phase 2) + spec §9

## How does workflow resume work?
→ `schemas/workflow-run.schema.json` (Phase 1) + spec §10

## What phase are we in?
→ `docs/PHASE_STATUS.md`

## What was decided about X?
→ `docs/DECISIONS.md` (active ADR'ler — son 6) + `docs/DECISIONS_ARCHIVE.md` (rotated ADR'ler, ADR-011 rotation kararıyla)

## What questions are open?
→ `docs/OPEN_QUESTIONS.md`

## Glossary / what does X mean?
→ `docs/GLOSSARY.md` + spec §20

## Architecture overview?
→ `docs/ARCHITECTURE.md` + spec §1, §2, §8

## Skill catalog (50 skills, 30 commands)?
→ `docs/WORKFLOWS.md` + spec §11

## Manager protocol / fresh session wakeup?
→ `docs/SESSION_PROTOCOL.md`

## Old repos location (READ-ONLY reference)?
→ `~/Documents/platinum-seo-core/` and `~/Documents/platinum-premium-seo/` — until v1 acceptance + 1 week soak (ADR-004)

## Screaming Frog 24 MCP integration (v1.8+)?
→ Skill: `skills/ingestion/sf-crawl-orchestrator/SKILL.md` (orchestrator, 24-report MCP-primary loop, 8 DURURs)
→ Utility: `scripts/util/sf_mcp_client.py` (first HTTP MCP client, D-SF-14)
→ Commands: `/pseo-sf-crawl` + `/pseo-sf-status`
→ Schema: `schemas/sf-mcp-tool-mapping.schema.json` (6 use-case keys)
→ Instance: `mcp-tool-registry.json` (repo root, all 4 MCPs × 31 tools cumulative)
→ Migration: `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py` (project-config v1.4→v1.5)
→ ADR: ADR-039 (HTTP transport + controlled F-16 break)
→ Spec: `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md`

## Migration scripts location?
→ `scripts/migrations/migration_0001..0005_*.py` (5 migration cumulative; Migration 0005 v1.8 Phase 1 — project-config v1.4→v1.5)
