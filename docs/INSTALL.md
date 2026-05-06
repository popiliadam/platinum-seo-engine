# Installation

> Status: **v1.0.0** — 43 skills, production-ready.

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
| `PSE_WORKSPACE_PATH` | Local path to your workspace repo (e.g. `~/Documents/platinum-seo-workspace`) |

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

## Troubleshooting

- **Plugin not recognized:** Restart Claude Code after `/plugin add`
- **MCP server not connecting:** Check `.env` credentials and run `claude mcp list`
- **Budget exceeded:** Check `scripts/budget/check_budget.py` — default cap 500 DFS credits/day
- **Python import errors:** Run `pip install jsonschema openpyxl pyyaml` in the plugin directory

See `docs/CONTRIBUTING.md` for development setup.
