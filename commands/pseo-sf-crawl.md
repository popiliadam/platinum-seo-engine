---
description: |
  Use when: kullanıcı "SF crawl", "Screaming Frog tara", "site crawl MCP", "sf-crawl-orchestrator", "24 rapor çek" der ya da `/pseo-sf-crawl` çağırırsa.
  Also use when: aktif projenin Screaming Frog MCP server'ı (`http://127.0.0.1:11435/mcp`) açık, `project.config.sf.mcp.enabled=true`; 24 raporluk Tier 1 + Tier 2 export döngüsü tetiklenecek; mid-loop crash sonrası `--resume <run_id>` ile devam ettiriliyor.
  Do not use when: SF MCP server kapalı (GUI'den önce başlat), manuel CSV drop (mevcut sf-import file-only path zaten çalışır), GSC ingestion (`/pseo-gsc-pull`), DFS pull (`/pseo-dfs-pull`).
argument-hint: "<slug> [start_url] [--resume <run_id>]"
allowed-tools: Bash(jq:*), Bash(curl:*), Bash(head:*), Read
model: sonnet
---

# /pseo-sf-crawl — Screaming Frog MCP Crawl Orchestrator

> **Skill:** `skills/ingestion/sf-crawl-orchestrator/SKILL.md` (v1.8 Phase 3, aktif).
> MCP-primary ingestion path: `sf_crawl` → poll `sf_crawl_progress` → 24 rapor (`sf_generate_report`) → atomic move → sf-import handoff. Atomic semantics (D-SF-16): all-or-nothing per crawl.

## 1. Aktif projeyi çöz

`$1` verilmişse onu kullan; yoksa `shared/active.json`:

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else echo "active=$PROJECT"; fi; fi`

## 2. SF MCP pre-flight

Pre-flight: SF GUI açık + MCP server start edilmiş olmalı (D-SF-10 + DURUR-orch-1). Bağlantı testi:

!`curl -sf -m 3 http://127.0.0.1:11435/mcp/tools 2>/dev/null | jq -r '.tools[]?.name // empty' | head -5 || echo "SF_MCP_DOWN — SF GUI'de Configuration → API Access → MCP Server Start"`

Beklenen tool inventory (minimum 5): `sf_crawl`, `sf_crawl_progress`, `sf_generate_report`, `sf_list_crawls`, `sf_list_allowed_base_directory`.

## 3. Skill chain

`sf-crawl-orchestrator` skill (v1.8 Phase 3 — `skills/ingestion/sf-crawl-orchestrator/SKILL.md`):

1. **Pre-flight** (DURUR-orch-1/2/4/7): MCP health, modal dialog absence, allowed_directory match, concurrent-crawl guard (R13 via `sf_list_crawls`)
2. **`workflow_runner.create_run`** + envelope yazımı (`inbox/sf-mcp/{date}-sf-crawl-{slug}.json`)
3. **Trigger crawl**: `mcp__sf__sf_crawl(start_url=$2, ...)` → `crawl_id` döner
4. **Poll progress**: `mcp__sf__sf_crawl_progress(crawl_id)` her N saniyede; max_wait_minutes default 180 (Q-SF-MCP-03)
5. **24 rapor iterate** (Step 6 orchestrator body): Tier 1 (14 mandatory RED-fail) + Tier 2 (10 AMBER-tolerant); her rapor SF allowed base directory'ye `export_type="CSV"` + `file_path=f"{canonical}.csv"` ile yazılır (export tool'larında `save_report` / `report_name` / `output_directory` arg'ı YOK — export currently-loaded crawl üzerinden çalışır, SKILL.md "Dispatch contract"); temp staging dir `_state/staging/sf-crawl-{run_id}/` (D-SF-16 atomic)
6. **DURUR-orch-8** Tier 1 fail → `shutil.rmtree(temp_staging)` + `workflow_runner.fail` + SystemExit(8)
7. **Atomic move**: temp_staging → `projects/{slug}/sf-exports/{date}/raw/` (same-filesystem atomic mv; DURUR-orch-5 target dir conflict guard)
8. **sf-import handoff**: `python3 -m scripts.ingestion.sf_import --project {slug} --sf-export-path {final_dir.parent}` (D-SF-07: sf-import body UNCHANGED; sf_import script CLI yalnızca `--project` / `--sf-export-path` / `--workspace-root` / `--dry-run` kabul eder; `source_run_id` provenance chaining sf-import *skill frontmatter* input'udur — script flag DEĞİL, CLI'ye verilirse argparse exit 2)
9. **`workflow_runner.complete`** + events.jsonl provenance (source.kind=sf_mcp)

## 4. Resume mid-loop (workflow_runner.pause/resume)

SF MCP crash sonrası (örn. rapor #17 sonrası):

```bash
/pseo-sf-crawl $PROJECT --resume <run_id>
```

Orchestrator:
1. `workflow_runner.resume(run_id)` → state=running, `paused_at` survive (append-only `rules/append-only-state.md`)
2. Temp staging scan → mevcut CSV'leri skip (idempotent per report_name)
3. Kalan raporlardan devam (örn. #18'den)

## 5. Onay gate (Q-SF-MCP-02)

Frontmatter `requires_approval=true` — skill `awaiting_approval` durumunda durur, kullanıcı `approve` veya `reject` der. Otomatik mod istenirse skill frontmatter düzenlenmelidir (operator karar).

## 6. Bağımlılıklar

- Skill: `skills/ingestion/sf-crawl-orchestrator/SKILL.md` — v1.8 Phase 3 aktif
- Script: `scripts/ingestion/sf_crawl_orchestrator.py` (pure-transform helpers)
- Util: `scripts/util/sf_mcp_client.py` (HTTP MCP client, D-SF-14)
- MCP required: `mcp__sf__sf_crawl` + `mcp__sf__sf_crawl_progress` + `mcp__sf__sf_generate_report` + `mcp__sf__sf_generate_bulk_export` + `mcp__sf__sf_export_seo_element_urls` + `mcp__sf__sf_list_crawls` + `mcp__sf__sf_list_allowed_base_directory`
- `project.config.sf.mcp.{enabled,url,allowed_directory,max_wait_minutes,per_report_timeout_seconds}` — Migration 0005 retro-populates (D-SF-12 + D-SF-18)
- `.mcp.json` `sf` entry (`http://127.0.0.1:11435/mcp`) — v1.8 Phase 2 ADR-039
- Schema: `schemas/sf-mcp-tool-mapping.schema.json` + `mcp-tool-registry.json` (sf entry, F-23 invariant)
- Output: `projects/{slug}/sf-exports/{date}/raw/*.csv` (24 file) → `outputs/reports/{date}-sf-crawl.md` (`templates/reports/sf-crawl.template.md`) → `events.jsonl` (source.kind=sf_mcp)

## 7. Tier sınıflandırması (24 rapor)

**Tier 1 (14 mandatory — RED FAIL if missing):** internal_all, all_inlinks, all_outlinks, response_codes_all, issues_overview_report, page_titles_all, meta_description_all, h1_all, canonicals_all, directives_all, indexability, structured_data_all, sitemaps_all, redirect_chains

**Tier 2 (10 recommended — AMBER if missing):** h2_all, images_all, hreflang_all, orphan_pages, all_anchor_text, near_duplicates_report, exact_duplicates_report, search_console_all, crawl_depth, pagination_all

**Tier 3 (16 optional — skipped in v1 per Q-SF-MCP-10 default):** v1.1+ scope; orchestrator `include_tier3=false` lock'lu.

## 8. Disaster recovery fallback

SF MCP kapalı kalırsa veya 24 rapor çekilemezse: operator manuel CSV drop yapabilir (`projects/{slug}/sf-exports/{date}/raw/`) ve `python3 -m scripts.ingestion.sf_import --project {slug} --sf-export-path projects/{slug}/sf-exports/{date}/` ile sf-import çalıştırır. Bu legacy path **never deprecated** — file-drop sf-import 8-step protocol intact (D-SF-07).
