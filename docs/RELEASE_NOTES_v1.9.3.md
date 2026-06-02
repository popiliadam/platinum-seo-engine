# Platinum SEO Engine — v1.9.3 Release Notes

**Release date:** 2026-06-02
**Engine HEAD:** v1.9.3 release commit (5-file sync via Y-05 sixth production `--apply`)
**Predecessor:** [v1.9.0](RELEASE_NOTES_v1.9.0.md) (Hardening Cycle — spec retro + 3 new invariants + legacy cleanup)
**Status:** 🟢 GREEN — SF MCP integration is now **live-proven** (29/29 tools + orchestrator export + resilient load) against a real Screaming Frog 24 MCP server. F-16 `.mcp.json` 543B/md5 `93523d41e14f90916fefb86d346bd702` UNCHANGED throughout.

## 0. Executive Summary

v1.9.3 is the **SF MCP live-hardening** patch cycle. v1.9.0 shipped the Screaming Frog integration **code-ready but never run against a real server** — every SF test was mocked. The operator then started a real SF MCP server (port 11435), and the first live contact immediately surfaced defects that 1286 mock tests could not. This release fixes them and proves the integration end-to-end on a real 1822-URL crawl.

**The deep lesson, recurring:** *code-ready ≠ live-proven.* Mocks encode the protocol you ASSUMED, never the one the server actually speaks. Every fix below was independently re-validated against the live server.

Four threads landed (v1.9.1 + v1.9.2 were committed earlier in the cycle; v1.9.3 bundles them with the orchestrator + load + smoke work into a single tagged release):

1. **Transport rewrite (v1.9.1, `c6c0268`)** — `scripts/util/sf_mcp_client.py` spoke bare JSON-RPC-over-HTTP; the real server requires the **MCP Streamable-HTTP** transport. Rewrote to: `initialize` handshake → capture `Mcp-Session-Id` → `notifications/initialized` → `tools/call` with the session id + `Accept: application/json, text/event-stream` → dual JSON/SSE parse; real `health()` liveness probe; single automatic session re-init on expiry. Public API preserved.
2. **Retry-on-busy (v1.9.2, `65c5c52`)** — after a state-changing op (`sf_load_crawl`/`sf_crawl`) the Spider is transiently BUSY and returns `IllegalStateException "Tool cannot be called currently"`. `call_tool` now retries ONLY that exact busy signal (linear backoff, `busy_retry_max=6` default) — surgical: a permanent error (SecurityException, size-cap, …) returns immediately with no futile retry.
3. **Orchestrator export dispatch (Task C AC-10, `a714e43`)** — the `sf-crawl-orchestrator` Step 5 export loop was wrong vs the real SF API (called `sf_generate_report` with `report_name`/`save_report`/`output_directory` — none exist; the engine's 24 canonical report names are NOT SF identifiers). Built the missing **24-canonical → SF-tool dispatch** + NDJSON conversion.
4. **Resilient `load_crawl` (Task D, `9d662b5`)** + **smoke-test fix (`7a93ff7`)** — `sf_load_crawl` reliably times out client-side on large crawls (but loads server-side); the new `SfMcpClient.load_crawl` tolerates that and verifies via progress. The live smoke test, which had silently always-skipped, now actually runs.

**pytest 1286 → 1324 PASS / 12 SKIP / 0 FAIL** (+38 across the cycle: v1.9.1 +12, v1.9.2 +4, AC-10 dispatch +10, Task D +12; regression sıfır). **`.mcp.json` UNCHANGED** 543B/md5 (F-16 — no transport-*config* change; the client reads its URL from the constructor). **`DECISIONS.md` UNCHANGED** 6067B; NO new ADR.

## 1. v1.9.1 — MCP Streamable-HTTP transport (`c6c0268`)

The original client did `GET /health` (404 — no such route → `health()` always False) and bare `tools/call` POSTs with no handshake/session/Accept headers (HTTP 400 every call, `-32601` "Accept + mcp-session-id required"). Root cause: 100%-mocked tests encoded the assumed protocol. **Fix:** full Streamable-HTTP transport (handshake + session id + dual JSON/SSE parse). **LIVE-PROVEN:** `health()=True` + HTTP 200 on tool calls. Tests 5→17 incl. a regression bug-catcher proven to fail against the old client.

## 2. v1.9.2 — Retry-on-busy (`65c5c52`)

Surgical Spider-busy handling: `_is_spider_busy` requires BOTH "illegalstateexception" AND "tool cannot be called currently" in the error text; only that signal is retried (linear backoff, cap 8s, ~36s budget; constructor-tunable). **Live-verified:** a busy call succeeded in 2.0s via 1 retry; a permanent SecurityException returned in 0.0s with no retry.

## 3. Live tool validation — 29/29 (Task A)

All **29 SF MCP tools** were exercised against a real crawl (demo-aluminum, 1822 URLs) + a controlled destructive sweep on `example.com`:
- Read/metadata/export/file-ops (read/write/create_directory) + `run_node_js_script` + `npm_install` (SF Node.js Runtime enabled).
- Crawl lifecycle: `sf_crawl` → `sf_crawl_progress` (caught running at 50%) → `sf_pause_crawl` (genuinely frozen) → `sf_resume_crawl` (→100%) → `sf_clear_crawl` (test crawl only) + `sf_open_url_in_browser` + `sf_export_embeddings` (expected "not configured").
- The 2 domain errors observed (embeddings-not-configured, pause-a-finished-crawl) are CORRECT behavior — and the retry-on-busy filter correctly did NOT retry them.

## 4. Orchestrator export dispatch (Task C AC-10, `a714e43`)

`scripts/ingestion/sf_crawl_orchestrator.py`:
- **`SF_EXPORT_DISPATCH` + `build_export_plan()`** — the 24 engine canonical report names map to a MIX of three real SF tools: **3** `sf_generate_report` + **5** `sf_generate_bulk_export` + **16** `sf_export_seo_element_urls`. The real SF API keys off `category` ("Category:Subcategory") or `seo_element_name`+`filter_name` (+ `file_path`), never the engine names. Pure function, fully tested.
- **`ndjson_to_csv()` + `export_returns_ndjson()`** — `sf_export_seo_element_urls` has no `export_type` arg → it always emits NDJSON (even to a `.csv` path); the 16 seo-element exports are converted to CSV before the atomic move so sf-import (CSV-only) matches.
- Orchestrator SKILL.md Step 5 rewritten to the correct API; Step 7 `--source-run-id` removed (sf_import's script CLI rejects it).

**LIVE-PROVEN (demo-aluminum, 1822 URLs):** 14/14 Tier-1 + 8/10 Tier-2 real reports exported → atomic move → sf_import validated (`OK matched 22 files Tier1 14/14`, envelope written; 2 Tier-2 AMBER = near/exact duplicates not configured, by-design).

## 5. Resilient `load_crawl` (Task D, `9d662b5`) + smoke fix (`7a93ff7`)

- **`SfMcpClient.load_crawl(crawl_id, *, settle_timeout_seconds=180, poll_interval_seconds=3, load_fire_timeout_seconds=15)`** — fires the load FAST (single short attempt via new optional `_timeout_override`/`_max_attempts_override` on `call_tool`; tolerates the client-side timeout) then polls `sf_crawl_progress` until `_progress_indicates_loaded`. **LIVE-PROVEN:** demo-aluminum loads in **15.1s** (was 180s-then-raise); post-load `url_info` returns real data.
- **Smoke fix:** `tests/smoke/test_sf_mcp_smoke.py` probed a non-existent `GET /health` → always skipped (false coverage). Switched to `SfMcpClient.health()`; running it live then exposed + fixed a latent result-shape bug (real SF returns the path in `content[*].text`, not `{allowed_directory|value}`). Smoke now RUNS + PASSES against SF 24.

## 6. Not included (follow-up)

This release ships the SF MCP **transport + crawl orchestrator + load** hardening. The remaining skill-layer wiring is deferred (separate, deeper stub-mod layers; tracked in OPEN_QUESTIONS):
- **AC-10 sheet projection** (OQ-SHEET-PROJECTION) — `sf_import` does Tier-validation + envelope only; the per-sheet projection into master.xlsx is sf-import SKILL.md Step 6 (transaction.append) prose.
- **AC-13 tech-audit live-merge** — `tech_audit_transform.transform()` has no `live_findings` param yet (documented but unimplemented); needs the merge + `sf_crawl_id` plumbing, which will also wire `load_crawl` into the consumer live-mode.

## 7. Verification

- pytest **1324 PASS / 12 SKIP / 0 FAIL** (local SF-up: 1325/11 — the live smoke now runs).
- `.mcp.json` 543B / md5 `93523d41e14f90916fefb86d346bd702` (F-16).
- Y-05 `version_bump.py --to 1.9.3 --apply` 5-file sync (sixth production dogfooding).
- `git tag v1.9.3` annotated.
