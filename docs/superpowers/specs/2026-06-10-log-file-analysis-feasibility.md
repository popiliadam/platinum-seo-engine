# Log-File Analysis — Feasibility Verdict & Deferral Spec (GAP-A4)

> **Status: SPEC-ONLY DEFERRAL — do NOT build.** Researched + web-verified
> 2026-06-10 (acquisition/local/commerce gap-spec series, GAP-A4); shipped as
> the unified-FIX-N hygiene batch's doc-only deliverable (GAP-A-B0).
> Re-open ONLY on the build triggers in §2. Pinned by
> `tests/docs/test_fix_n_hygiene.py`.

## 1. Verdict + evidence (dated 2026-06-10)

**Verdict: do NOT build a log-file analysis capability now.** The two data
sources such a feature needs are both unavailable for this portfolio, and the
unique signals it would add are partially approximable for free with tools the
engine already registers.

### 1a. GSC Crawl Stats has NO API in 2026

Verified directly against the official Search Console API reference: the
exposed resources are exactly `searchanalytics.query`,
`sitemaps.{delete,get,list,submit}`, `sites.{add,delete,get,list}`, and
`urlInspection.index.inspect` — there is **no crawl-requests / host-status /
crawl-budget endpoint**. Crawl Stats remains a UI-only report
(Settings → Crawl stats; manual export possible).

Sources (fetched and confirmed 2026-06-10):
- https://developers.google.com/webmaster-tools/v1/api_reference_index (API resource list)
- https://support.google.com/webmasters/answer/9679690 (Crawl Stats UI report doc)

### 1b. Raw server logs are not obtainable per client class

- **Hosted TR SaaS e-commerce platforms (Ticimax / Ideasoft / imagaza):** no
  documented raw access-log export in their panels — clients cannot grant
  what the platform does not expose. This covers the e-commerce majority of
  the portfolio.
- **WordPress sites:** host-dependent (cPanel/awstats sometimes available),
  but no client has provided log access to date, and chasing per-host access
  for a portfolio of small/mid TR sites has poor effort/value versus existing
  signals (GSC quick-wins + SF crawls already cover indexability triage).

### 1c. The unique signals are partially approximable for free

What a log analysis would uniquely add — crawl-budget waste, bot-hit
frequency per template, 304/404 hit ratios — is partially approximable today:

- `urlInspection` returns **`lastCrawlTime`** per URL. The engine's
  `gsc__index_inspect` MCP tool is already registered (0 credits, quota
  ~2,000/property/day).
- SF crawl snapshots give the "what exists" side of the
  SF-pages-vs-server-hits gap.

## 2. Build triggers (re-open conditions)

Re-open this spec — and only then — when ANY of the following holds:

- **T1 — Raw logs delivered:** any client delivers ≥30 days of raw access
  logs.
- **T2 — API ships:** Google ships a Crawl Stats API endpoint.
- **T3 — Undiagnosable incident:** a concrete crawl-budget incident (e.g. a
  faceted-URL explosion on a 30K-product hosted-platform site) that the GSC
  UI + SF together cannot diagnose.

## 3. Pre-designed Phase-2 sketch (so the future build is a worker prompt, not a research project)

### 3(i) — Crawl-freshness sampling (0 credits, no new MCP)

Extend `skills/publishing/verify-indexing/SKILL.md` (the existing consumer of
`index_inspect` and the natural home):

- Sample **N=50 priority URLs** (from the `quick_wins` + `topical_map`
  sheets) **monthly** via `gsc__index_inspect`.
- Persist `{url, lastCrawlTime, coverageState}` to
  `_state/staging/crawl_freshness_{YYYY-MM}_{slug}.json`.
- Report stale-crawl deltas month-over-month.

Test plan (binding on the future build, per the GAP-A4 spec's test-plan
section): the build's spec section must include **RED-first tests for the
sampling transform** — synthetic `index_inspect` payloads, stale-vs-fresh
classification boundary.

### 3(ii) — Crawl Stats UI manual-export file-drop

`inbox/gsc-crawl-stats/{date}/*.csv` mirroring the
`skills/ingestion/sf-import/SKILL.md` manual file-drop ingestion pattern —
built **only if** an operator actually commits to the monthly UI-export
ritual (the export is manual; an abandoned ritual produces a dead inbox
contract).

### 3(iii) — Raw-log path (T1 only)

A **single deterministic parser** to staging JSON — explicitly NOT a
streaming pipeline. One file in, one staging artifact out, replayable.

## 4. Repo integration points (verified 2026-06-10)

- `mcp-tool-registry.json` gsc server: `gsc__index_inspect` (category
  `index_inspect`, 0 credits, cache 168h) — the only crawl-adjacent primitive
  available today.
- The pinned `mcp-server-gsc@0.3.0` (`.mcp.json`) exposes no crawl-stats tool
  (none exists upstream to wrap).
- `skills/publishing/verify-indexing/SKILL.md` — existing `index_inspect`
  consumer; future home for the §3(i) micro-feature (NOT built now).
- `skills/ingestion/sf-import/SKILL.md` — the file-drop ingestion pattern a
  future Crawl-Stats-UI-export path (§3(ii)) would mirror.

## 5. What was deliberately NOT built, and why

| Candidate | Verdict | Cost | Value | Why not |
|---|---|---|---|---|
| Log ingestion pipeline (streaming) | not built | high (infra + ops) | low (no log source exists — §1b) | T1 has never fired; a pipeline without input is dead weight |
| Log-storage schema / new master.xlsx sheet | not built | medium (schema cascade + drift rules) | none today | sheet additions are forbidden without a consuming workflow; no data to store |
| Log-analyzer product (crawl-budget reports) | not built | high | speculative | the signals are partially covered free via §1c; revisit on T1/T2/T3 |
| Per-host cPanel/awstats scraping automation | not built | medium, fragile | low | host-by-host variance; no client grant to date; poor effort/value (§1b) |
| Crawl Stats UI scraping via browser automation | not built | medium, fragile | shallow data | ToS-gray, breaks on UI changes, and the UI export's data is shallow |
| GSC Crawl Stats API integration | impossible | — | — | no such API exists in 2026 (§1a); becomes T2 the day it ships |

**Risk accepted by deferring:** the monthly report's crawl story stays
GSC/SF-only — acceptable; this document records the decision so future audits
see a written rationale instead of a "gap".
