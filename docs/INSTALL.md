# Installation

> Status: **v1.9.5** — 45 skills, 18 slash commands, 6 hooks, 4 MCP servers (gsc/dataforseo/scrapling stdio + sf HTTP), production-ready (schema-data aligned + drift-check AMBER: F-16 invariant intentionally reset to 543B baseline at v1.8 per ADR-039 + F-17 PASS, F-13 historical).

## Requirements

- [Claude Code CLI](https://claude.ai/code) (latest)
- Python 3.10+
- Node.js 18+ (for MCP servers via npx)
- Git

## Install Plugin

```bash
git clone https://github.com/popiliadam/platinum-seo-engine ~/Documents/platinum-seo-engine
claude /plugin add ~/Documents/platinum-seo-engine
```

Restart Claude Code after adding the plugin.

## Configure Credentials

Copy `.env.example` to `.env` in the plugin root and fill in your credentials:

```bash
cp ~/Documents/platinum-seo-engine/.env.example ~/Documents/platinum-seo-engine/.env
```

Required for full functionality:

| Variable | Source |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Google Cloud Console → IAM → Service Accounts |
| `DATAFORSEO_USERNAME` | [app.dataforseo.com](https://app.dataforseo.com) → API tab |
| `DATAFORSEO_PASSWORD` | Same |
| `PSEO_WORKSPACE_ROOT` | Local path to your workspace repo (e.g. `~/Documents/platinum-seo-workspace`). Canonical per ADR-035; `PSE_WORKSPACE_PATH` is a 1-year deprecated alias (removal 2027-05-06). |

Optional (for image generation):

| Variable | Source |
|---|---|
| `HIGGSFIELD_API_KEY` | [app.higgsfield.ai](https://app.higgsfield.ai) → Settings → API Keys |
| `SCRAPLING_BIN` | `pip install scrapling[fetchers] && scrapling install` |

## Create Workspace

```bash
git clone https://github.com/popiliadam/platinum-seo-workspace ~/Documents/platinum-seo-workspace
```

Or create a new workspace for a fresh project:

```bash
mkdir -p ~/Documents/platinum-seo-workspace
cd ~/Documents/platinum-seo-workspace
git init
```

## Initialize a Project

```
/pseo-init
```

Claude will prompt for project slug, domain, and brand details, then bootstrap `projects/{slug}/` with config + master.xlsx.

## Verify

Check that the plugin loaded:

```
/pseo-status
```

Run the governance audit (CI smoke test):

```
/pseo-driftcheck
```

## Quick Smoke Test

```
/pseo-quickwin
```

Should complete in under 2 minutes, reporting top quick-win keyword opportunities from your GSC data.

## Screaming Frog 24 MCP Setup (Optional, v1.8+)

The 4th MCP server (`sf`) is HTTP-transport (`http://127.0.0.1:11435/mcp`) — added in v1.8 per ADR-039. Required only if you want to trigger SF crawls via `/pseo-sf-crawl` instead of manual CSV drop.

### 1. Install Screaming Frog 24+

Download SF 24+ from [screamingfrog.co.uk](https://www.screamingfrog.co.uk/seo-spider/) (license required for >500 URLs).

### 2. Configure SF GUI MCP Server

Open SF → Configuration → API Access → MCP Server tab:

| Setting | Value | Reason |
|---|---|---|
| Port | `11435` | Default; matches `.mcp.json` `sf.url` |
| Max Response Size (Bytes) | `100000` | D-SF-05; orchestrator handles large data via file path |
| Directory | `/Users/apple/seo_spider_mcp_server` | D-SF-03; F-15 governance: SF scratch isolated from PSEO workspace |
| Node.js Runtime Environment | ☐ Unchecked | D-SF-04; security (embeddings/custom scripts deferred v1.1+) |
| MCP Server Status | **Start** (click green button) | Required before any `/pseo-sf-crawl` |

### 3. Verify Connection

```bash
curl http://127.0.0.1:11435/mcp/tools | jq '.tools[].name'
# Expected ≥5: sf_crawl, sf_crawl_progress, sf_generate_report, sf_list_crawls, sf_list_allowed_base_directory
```

After plugin install:

```bash
claude mcp list
# Expected: sf entry showing connected
```

### 4. Migrate Existing Projects (Migration 0005)

For projects created before v1.8 (schema_version=1.4):

```bash
python3 scripts/migrations/migration_0005_project_config_1_4_to_1_5.py --project <slug> --dry-run
# Inspect output; if OK:
python3 scripts/migrations/migration_0005_project_config_1_4_to_1_5.py --project <slug>
# Idempotent on already-1.5 docs; creates .bak before write
```

New projects (`/pseo-init` v1.8+) auto-emit v1.5 with `sf` block defaults (D-SF-12 + D-SF-18 path parameterization).

### 5. First Crawl

```
/pseo-sf-crawl <slug> https://example.com/
```

Orchestrator: pre-flight → `sf_crawl` → poll progress → 24-report iteration (Tier 1 + Tier 2) → atomic move → sf-import handoff. See `/pseo-sf-status` for live MCP connection state.

## Troubleshooting

- **Plugin not recognized:** Restart Claude Code after `/plugin add`
- **MCP server not connecting:** Check `.env` credentials and run `claude mcp list`. For SF: confirm SF GUI is open + MCP Server "Start" clicked + port 11435 not blocked.
- **SF MCP `IllegalStateException`:** Close any open SF settings dialog (D-SF-10); orchestrator pre-flight catches.
- **Budget exceeded:** Check `scripts/budget/check_budget.py` — default cap 500 DFS credits/day. SF MCP is local (uses_paid_mcp=false), no budget tracked.
- **Python import errors:** Run `pip install jsonschema openpyxl pyyaml httpx>=0.27` in the plugin directory. httpx required for SF MCP client (v1.8+).
- **F-23 drift alert:** `sf-crawl-orchestrator` ran but `mcp-tool-registry.json` missing `sf` entry → run `/pseo-driftcheck` for full RED report.

See `docs/CONTRIBUTING.md` for development setup.
