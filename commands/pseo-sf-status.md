---
description: |
  Use when: kullanıcı "SF status", "SF MCP durum", "SF bağlantı", "son crawl ne zaman", "allowed_directory neresi" der ya da `/pseo-sf-status` çağırırsa.
  Also use when: SF MCP server live mı kontrol edilecek (`sf_list_allowed_base_directory` probe), aktif veya tüm projelerin son sf-crawl-orchestrator run özetini görme, allowed_directory mismatch tespit etme.
  Do not use when: yeni crawl tetikleme (`/pseo-sf-crawl`), genel workflow status (`/pseo-status` SF MCP Status H2 alt-bölümünü de gösterir), drift kontrol (`/pseo-driftcheck`).
argument-hint: "[project-slug]"
allowed-tools: Bash(curl:*), Bash(jq:*), Bash(python3:*), Bash(ls:*), Bash(grep:*), Bash(head:*), Bash(sort:*), Bash(tail:*), Bash(xargs:*), Read
model: sonnet
---

# /pseo-sf-status — Screaming Frog MCP Connection & Crawl Status

> **Inline command (no dedicated skill).** SF MCP server health + last sf-crawl-orchestrator run summary per project + allowed_directory drift detection.

## 1. SF MCP connection probe

!`curl -sf -m 3 http://127.0.0.1:11435/mcp/tools 2>/dev/null | jq -r '"tools_advertised=" + ([.tools[]?.name] | length | tostring)' || echo "tools_advertised=DOWN (SF GUI MCP Server not started)"`

Detaylı tool inventory:

!`curl -sf -m 3 http://127.0.0.1:11435/mcp/tools 2>/dev/null | jq -r '.tools[]?.name' | sort | head -10 || echo "(no tools — SF GUI MCP Server kapalı veya port 11435 erişilemez)"`

Beklenen minimum 5 tool: `sf_crawl`, `sf_crawl_progress`, `sf_generate_report`, `sf_list_crawls`, `sf_list_allowed_base_directory`.

## 2. allowed_directory probe + drift check

Live allowed_directory (SF GUI Configuration → API Access → Directory):

!`curl -sf -m 3 -X POST http://127.0.0.1:11435/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"sf_list_allowed_base_directory","arguments":{}}}' 2>/dev/null | jq -r '.result.content[0].text // "MCP_CALL_FAILED"' || echo "MCP_CALL_FAILED"`

Beklenen: `/Users/apple/seo_spider_mcp_server` (D-SF-03; F-15 governance: SF scratch isolated from PSEO workspace). Override için `project.config.sf.mcp.allowed_directory` set edilebilir (D-SF-18 path parameterization).

## 3. Per-project last crawl summary

Aktif veya tüm projelerin son sf-crawl-orchestrator run'ları (`_state/workflows/{run_id}.json` filter by `skill=sf-crawl-orchestrator`):

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then PROJECTS=$(ls -1 "$PSEO_WORKSPACE_ROOT/projects" 2>/dev/null); else PROJECTS="$PROJECT"; fi; for SLUG in $PROJECTS; do WF_DIR="$PSEO_WORKSPACE_ROOT/projects/$SLUG/_state/workflows"; if [ -d "$WF_DIR" ]; then LATEST=$(grep -l '"skill": "sf-crawl-orchestrator"' "$WF_DIR"/*.json 2>/dev/null | xargs -I{} jq -r --arg slug "$SLUG" '[$slug, .run_id, .status, (.updated_at // "n/a")] | @tsv' {} 2>/dev/null | sort -k4 | tail -1); if [ -n "$LATEST" ]; then echo "$LATEST"; else echo -e "$SLUG\tNO_SF_CRAWL\t-\t-"; fi; fi; done; fi`

## 4. Output table format

Çıktıyı şu 4-kolonlu tabloya çevir:

| project_slug | last_crawl_date | sf_mcp_connection_status | allowed_directory_path |
|---|---|---|---|

- **sf_mcp_connection_status**: `connected` (5+ tool advertised), `down` (port 11435 unreachable), `partial` (<5 tool)
- **last_crawl_date**: `_state/workflows/*.json` içinde `updated_at` veya `completed_at`; never run ise `-`
- **allowed_directory_path**: Step 2 live probe sonucu; her proje için `project.config.sf.mcp.allowed_directory` override edilebilir

## 5. Drift tespiti

Allowed_directory mismatch durumunda uyarı:

- Live probe ≠ project.config.sf.mcp.allowed_directory → AMBER (operator F-15 governance ihlali eşiğinde)
- `sf` entry in `mcp-tool-registry.json` yok ama workflow_runner'da sf-crawl-orchestrator run var → F-23 RED (drift-check skill yakalar)

## 6. Bağımlılıklar

- MCP probe: `mcp__sf__sf_list_allowed_base_directory` (D-SF-04: Node.js Runtime OFF kalmalı)
- Schemas: `schemas/sf-mcp-tool-mapping.schema.json` (use-case `allowed_dir_discovery`) + `mcp-tool-registry.json` (sf 5-tool inventory)
- State: `_state/workflows/{run_id}.json` (workflow_runner.list_runs filter)
- Rules: `rules/naming.md` (sf 3-char convention D-SF-02) + `rules/append-only-state.md` (events.jsonl source.kind=sf_mcp)
