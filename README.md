# Platinum SEO Engine

[![CI](https://github.com/popiliadam/platinum-seo-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/popiliadam/platinum-seo-engine/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/popiliadam/platinum-seo-engine?label=release)](https://github.com/popiliadam/platinum-seo-engine/releases/latest)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-7C3AED)](https://claude.ai/code)

> Status: **v1.9.5** — production-ready · 45 skills · 18 commands · 6 hooks · 4 MCP servers (3 stdio + 1 HTTP)

> **Schema-locked, drift-checked SEO automation for Claude Code.**
> Turn manual SEO work into auditable, repeatable workflows — backed by JSON Schemas, append-only state, and a tool that audits itself.

---

## What is this?

`platinum-seo-engine` is a **Claude Code plugin** that runs your full SEO operation from inside the editor — keyword research, on-page audits, content planning, reporting, indexing — all governed by strict contracts so the system can't silently drift.

Most SEO toolchains are loose: a Google Sheet here, an Ahrefs export there, an LLM that improvises a different format every time. The data spreads across tabs, fields rename themselves, and three months later nobody can reproduce a number. This plugin takes the opposite stance.

**The core idea:** *less code, stricter rules, single authority, machine-readable contracts.* Every workflow is a discoverable [skill](#skills--commands), every input/output is validated against a [JSON Schema](schemas/), every state change is appended to an event log, and a [drift-check](skills/governance/drift-check/SKILL.md) skill watches the whole thing.

The result: you can re-run any workflow weeks later, hand a project to someone else, or audit a year of activity — and the system tells you exactly what happened.

---

## Who is this for?

- **SEO operators** who run multiple sites and need reproducible workflows instead of ad-hoc spreadsheets.
- **Agencies** managing a portfolio — the plugin is project-agnostic, the same install drives any number of sites.
- **Technical SEOs** who already use Claude Code and want skills/commands wired into a real pipeline (GSC ingestion → discovery → planning → reporting).
- **Teams** that need an audit trail for SEO decisions (every action is logged in `events.jsonl`).

You will get the most out of this if you are comfortable with a CLI, JSON, and the idea that "the schema wins."

---

## What it does

Out of the box, **45 skills** across 8 categories cover an end-to-end SEO loop:

| Category | What it covers | Skills |
|---|---|---|
| **Ingestion** | Pull data from Google Search Console, DataForSEO, Screaming Frog (file-drop + native MCP-primary orchestrator), Scrapling | 5 |
| **Discovery** | Quick wins, content gaps, cannibalization, content decay, on-page audit, schema audit, tech audit, geo analysis, competitive analysis, AIO competitor map, GBP audit | 11 |
| **Planning** | Topical map, cluster map, new content plan, internal links, master task sync | 5 |
| **Production** | New blog drafting, content revision, FAQ optimization, content remediation, image generation | 5 |
| **Publishing** | Indexing ping (URL Indexing API), index status verification | 2 |
| **Reporting** | Weekly/monthly site reports + 6 portfolio-level reports (overview, heatmap, KPI trend, etc.) | 9 |
| **Meta** | Init project, brand onboarding, whats-next router, mark-done | 4 |
| **Governance** | Schema validation, glossary audit, drift-check, context loader | 4 |

Plus **18 slash commands** (`/pseo-init`, `/pseo-quickwin`, `/pseo-driftcheck`, `/pseo-sf-crawl`, `/pseo-sf-status`, …), **6 hooks** that fire on session start, prompt submit, and tool use, and **4 MCP servers** wired up automatically (GSC, DataForSEO, Scrapling, SF — the last over HTTP `http://127.0.0.1:11435/mcp`).

A typical workflow looks like:

```text
/pseo-init           →  bootstrap a project (slug, domain, brand)
/pseo-gsc-pull       →  ingest 90 days of Search Console data
/pseo-quickwin       →  find pages stuck at positions 11–20 with high impressions
/pseo-whats-next     →  router skill suggests the next high-impact action
/pseo-monthly        →  generate the month's report
/pseo-driftcheck     →  audit the full state for inconsistencies
```

---

## Quick start

### Requirements

- [Claude Code CLI](https://claude.ai/code) (latest)
- Python 3.10+
- Node.js 18+ (for the MCP servers via `npx`)
- Git

### Install

```bash
# 1. Clone the plugin
git clone https://github.com/popiliadam/platinum-seo-engine ~/Documents/platinum-seo-engine

# 2. Register it with Claude Code
claude /plugin add ~/Documents/platinum-seo-engine

# 3. Configure credentials
cp ~/Documents/platinum-seo-engine/.env.example ~/Documents/platinum-seo-engine/.env
# edit .env — see the table below
```

Restart Claude Code after the `/plugin add` step.

### Required environment variables

| Variable | Where to get it |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Google Cloud Console → IAM → Service Accounts (JSON key path) |
| `DATAFORSEO_USERNAME` | [app.dataforseo.com](https://app.dataforseo.com) → API tab |
| `DATAFORSEO_PASSWORD` | same |
| `PSEO_WORKSPACE_ROOT` | local path to your workspace repo (see [Architecture](#architecture)) |

Optional:

| Variable | Used by |
|---|---|
| `HIGGSFIELD_API_KEY` | `generate-images` skill (Phase 11+) |
| `SCRAPLING_BIN` | site scraping fallback when Screaming Frog is unavailable |

### First run

```bash
# inside Claude Code
/pseo-init        # bootstrap your first project
/pseo-status      # verify the plugin loaded
/pseo-quickwin    # smoke test — should finish in under 2 minutes
```

Full instructions: **[docs/INSTALL.md](docs/INSTALL.md)** · Troubleshooting: same file, bottom section.

---

## Architecture

The plugin enforces a **two-repo separation** between logic and data:

```
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│  platinum-seo-engine  (this)     │  reads │  platinum-seo-workspace          │
│  ─────────────────────────────   │ ─────► │  ─────────────────────────────   │
│  • skills/        (45 SKILL.md)  │        │  • projects/{slug}/              │
│  • commands/      (18 slash cmds)│        │     ├ project.config.json        │
│  • hooks/         (6 hooks)      │ writes │     ├ master.xlsx                │
│  • schemas/       (21 JSON       │ ─────► │     ├ events.jsonl  (append-only)│
│  • scripts/        Schemas)      │        │     └ workflows/{run_id}.json    │
│  • rules/         (10 disciplines│        │  • shared/                       │
│  • templates/     enforced by CI)│        │  • _archive/                     │
│  • docs/                         │        │                                  │
│                                  │        │  No logic. Only data + state.    │
│  Project-agnostic.               │        │  No project names in the engine. │
└──────────────────────────────────┘        └──────────────────────────────────┘
```

The plugin **never** stores project data; the workspace **never** holds logic. They are linked at runtime by `PSEO_WORKSPACE_ROOT` in `.env`. You can drop a fresh workspace next to the same engine and run a different portfolio without a single line of code change.

### The 10 disciplines (non-negotiable rules)

Every rule below is enforced by either CI, the `drift-check` skill, or both:

| # | Discipline | What it means |
|---|---|---|
| 1 | Single Source of Truth | Each term, schema, and rule is defined in exactly one place |
| 2 | Schema-First | No data is written before its `*.schema.json` exists |
| 3 | Project-Agnostic Plugin | Project names never appear in the plugin repo (CI greps for them) |
| 4 | Append-Only State | `events.jsonl` and `workflows/{run_id}.json` are never overwritten |
| 5 | Atomic Excel Writes | `master.xlsx` is written only via a transaction wrapper with backup + invariant check |
| 6 | Naming | Slugs and skills `kebab-case`; sheets and Python `snake_case`; run IDs `{slug}-{date}-{uuid}` |
| 7 | Secrets Management | API keys never committed; `.env` only; pre-commit guards |
| 8 | Glossary Discipline | Every technical term lives in `docs/GLOSSARY.md` |
| 9 | Skill Description Discipline | Every skill frontmatter validates against `skill-frontmatter.schema.json` |
| 10 | Time Discipline | All timestamps stored in UTC ISO-8601, presented in local time |

Bonus: **Schema Versioning** — bumping a schema requires a migration script in `scripts/migrations/`.

Full architecture: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## Screaming Frog 24 MCP (Optional)

v1.8 added Screaming Frog 24's native MCP server as the **fourth MCP** in PSEO (first HTTP-transport MCP; existing 3 use stdio). The MCP-primary ingestion path replaces manual CSV drop as the authoritative workflow — operator triggers `/pseo-sf-crawl` and the orchestrator runs the full 24-report export atomically. File-drop fallback is preserved as disaster recovery (D-SF-07; never deprecated).

### Setup

1. Install Screaming Frog 24+ ([screamingfrog.co.uk](https://www.screamingfrog.co.uk/seo-spider/))
2. Open SF → Configuration → API Access → MCP Server tab → click **Start**
3. Verify: `curl http://127.0.0.1:11435/mcp/tools | jq '.tools[].name'` returns ≥5 tools
4. After plugin install, `claude mcp list` should show `sf` connected

### SF Settings (recommended)

| Setting | Value | Why |
|---|---|---|
| Port | `11435` | Default; matches `.mcp.json` |
| Max Response Size (Bytes) | `100000` | D-SF-05; orchestrator handles big data via file path |
| Directory | `/Users/apple/seo_spider_mcp_server` | D-SF-03; F-15 governance: SF scratch isolated from PSEO workspace |
| Node.js Runtime Environment | ☐ Unchecked | D-SF-04; security (v1.1+ scope) |

### .mcp.json snippet (v1.8+)

```json
{
  "mcpServers": {
    "gsc":            { "command": "bash", "args": ["-c", "set -a; [ -f .env ] && source .env; set +a; exec npx -y mcp-server-gsc@0.3.0"] },
    "dataforseo":     { "command": "bash", "args": ["-c", "set -a; [ -f .env ] && source .env; set +a; exec npx -y dataforseo-mcp-server@2.8.10"] },
    "ScraplingServer":{ "command": "${SCRAPLING_BIN:-scrapling}", "args": ["mcp"] },
    "sf":             { "url": "http://127.0.0.1:11435/mcp" }
  }
}
```

### First Crawl Walkthrough

```
/pseo-sf-crawl <slug> https://example.com/
```

Orchestrator: pre-flight (DURUR-orch-1/2/4/7) → `sf_crawl` → poll progress → 24-report iteration (Tier 1: 14 mandatory + Tier 2: 10 AMBER-tolerant) → atomic move to `projects/{slug}/sf-exports/{date}/raw/` → sf-import handoff.

Mid-loop crash recovery: `/pseo-sf-crawl <slug> --resume <run_id>` continues from where it stopped (workflow_runner.pause/resume).

Live status table: `/pseo-sf-status` (4-column: project_slug, last_crawl_date, sf_mcp_connection_status, allowed_directory_path).

Full setup: **[docs/INSTALL.md § Screaming Frog 24 MCP Setup](docs/INSTALL.md)** · Spec: **[docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md](docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md)** · ADR: **[ADR-039](docs/DECISIONS.md)**

---

## Skills & commands

Skills live in `skills/{category}/{name}/SKILL.md`. Each skill is a self-contained markdown file with YAML frontmatter declaring its inputs, outputs, dependencies, and trigger hints. Claude Code loads them automatically.

A few highlights:

- **`quick-wins`** — Scans GSC for pages at positions 11–20 with ≥100 impressions, scores them by realistic uplift potential, and returns a ranked list.
- **`cannibalization`** — Detects URLs competing for the same query, ranks severity, and proposes consolidation actions.
- **`content-decay`** — Flags pages with declining clicks/impressions month-over-month and grades them by remediation difficulty.
- **`topical-map`** — Builds a hub-and-spoke topical map from a seed keyword set + DataForSEO clustering.
- **`drift-check`** — Read-only governance audit that checks 30+ invariants across schemas, state files, and the Excel workspace; the foundation of the plugin's self-governance.
- **`whats-next`** — Meta-router skill that reads project state and recommends the highest-impact next action.

Browse the full catalog: [`skills/`](skills/). Slash commands map 1:1 to commonly-triggered skills: see [`commands/`](commands/).

---

## Tech stack

- **Python 3.10+** — scripts, schema validation, Excel transactions (`openpyxl`, `jsonschema`, `pyyaml`).
- **Claude Code Plugin SDK** — skills, slash commands, hooks.
- **Model Context Protocol (MCP)** — four servers wired in `.mcp.json` (v1.8+):
  - `mcp-server-gsc` (Google Search Console, stdio)
  - `dataforseo-mcp-server` (DataForSEO, stdio)
  - `Scrapling` (stealthy site fetching, antibot fallback, stdio)
  - `sf` (Screaming Frog 24 native MCP, **HTTP** `http://127.0.0.1:11435/mcp` — v1.8 ADR-039)
- **JSON Schema** (Draft 7) — 21 schemas in `schemas/` (20 `*.schema.json` + `cross-sheet-invariants.json`).
- **Excel** as the operational data plane (`master.xlsx`), **JSONL** for the append-only event log.
- **GitHub Actions** — CI runs schema validation, drift-check, lint, and 1,100+ pytest tests on every push.

---

## Status & roadmap

**Current:** v1.9.5 — Codex audit remediation: 30 of 31 findings fixed + 1 refuted across governance, workspace contract, commands/hooks, schema validation, state/write paths, and docs. Every fix is locked by a regression test that reads ground truth (filesystem counts, live argparse, schemas, command bodies) so the same drift cannot silently return. Quality/correctness patch — no new features, no breaking changes (1,560 tests passing).

The plugin is delivered in **15 phases**. Foundation phases (0–4) are complete; skill phases (5–13) deliver the ~45 skills in batches; phase 14 covers the workspace + CI + a full pilot run end-to-end. Phase 5 is the **GO/NO-GO gateway** — failing it sends the project back to foundation work rather than papering over gaps.

| Phase | Title | Status | Skills |
|---|---|---|---|
| 0 | Manager Bootstrap | done | — |
| 1 | Schema Migration | done | — |
| 2 | Rules + Templates | done | — |
| 3 | Core Scripts | done | — |
| 4 | Hooks + Commands | done | — |
| 5 | Critical Path Skills (GO/NO-GO) | done | 5 |
| 6 | Ingestion Suite | done | 4 |
| 7 | Discovery Suite | done | 10 |
| 8 | Planning Suite | done | 5 |
| 9 | Reporting Suite | done | 9 |
| 10 | Content Rules Processing | done | — |
| 11 | Production Suite | done | 5 |
| 12 | Publishing + Specialized | done | 2 |
| 13 | Governance Final | done | 4 |
| 14 | Workspace + CI + Pilot E2E | in progress | — |

Detailed status: **[docs/PHASE_STATUS.md](docs/PHASE_STATUS.md)** · Open questions: **[docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)** · Latest release: **[docs/RELEASE_NOTES_v1.9.5.md](docs/RELEASE_NOTES_v1.9.5.md)**.

---

## Documentation

| Doc | What's inside |
|---|---|
| [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Vision, two-repo strategy, 10 disciplines, phase roadmap, v1 acceptance criteria |
| [`INSTALL.md`](docs/INSTALL.md) | Requirements, install, configuration, first-run smoke test, troubleshooting |
| [`CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Manager/worker protocol, skill authoring, phase discipline |
| [`WORKFLOWS.md`](docs/WORKFLOWS.md) | The full 43-skill catalog with inputs/outputs |
| [`GLOSSARY.md`](docs/GLOSSARY.md) | Spec terminology — every technical term defined once |
| [`DECISIONS.md`](docs/DECISIONS.md) | Architecture Decision Records (append-only) |
| [`PHASE_STATUS.md`](docs/PHASE_STATUS.md) | Current phase + history |
| [`OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md) | Pending decisions and unresolved scopes |
| [`SESSION_PROTOCOL.md`](docs/SESSION_PROTOCOL.md) | How a manager session opens, runs, and closes |
| [Release notes](docs/) | One file per minor version (`RELEASE_NOTES_v*.md`) |

---

## Contributing

The project follows a **manager / worker** protocol: a manager session sets context and assigns work; worker sessions execute one phase or skill at a time, then close out with a closeout commit. Contributions outside this rhythm tend to drift, so please read `docs/CONTRIBUTING.md` first if you'd like to submit changes.

For one-off bug reports or questions, open an issue.

---

## Companion repository

`platinum-seo-engine` is half of a pair. The other half — **[platinum-seo-workspace](https://github.com/popiliadam/platinum-seo-workspace)** — holds project data, state, and outputs. It is private by default because it contains real client data; if you fork the engine, you'll create your own workspace.

---

## License

MIT — see [`LICENSE`](LICENSE).

---

## Author

Built by **Süleyman Çapar** ([@popiliadam](https://github.com/popiliadam)) — `suleymanncapar@gmail.com`.

If you're trying this in production and run into edges the docs miss, an issue with reproduction steps is the fastest way to get it fixed.
