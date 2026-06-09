# Worker Prompt — Batch: Capability Coverage / Effectiveness Audit

> **Initiative:** Path B governance — the operator's north-star ("are ALL skills/MCPs/scripts used
> effectively, and is there a mechanism that audits that?"). Authority: `docs/superpowers/specs/2026-06-09-path-b-general-orchestration-research.md`
> + `docs/superpowers/plans/amo/FRESH-SESSION-BOOTSTRAP-coverage-audit.md` §4.
> **You are a fresh Opus 4.8 (1M-context) worker.** Build ONLY this batch. Report to the manager.

## Manager pre-flight (2026-06-09) — ground truth re-derived; you still verify (TDD)
The manager independently re-derived this prompt against the live repo (the D11 rule). **Confirmed:**
45 skills · 24 commands · 4 workflow modules · `mcp-tool-registry.json`/`portfolio_status.py`/`orchestration_metrics.py`/
pb1 `parse_graph`/3a `declared_tools` all present · **baseline 2423 pass / 10 skip / 0 fail.** Four things the
first draft got wrong or vague are corrected INLINE below — look for **[manager-verified]**:
(1) D10 surfaces are `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (there is **NO** root `plugin.json`);
(2) `content_pipeline` STEPS entries carry **no** `writer`/`tool` key (the other 3 workflows do) — use `.get()`;
(3) the registry `servers` object has **4** keys (higgsfield is `external_user_dependencies`, not a server);
(4) `events.jsonl` has **no skill field** — runtime skill attribution is LIMITED. Trust these, but re-run the
suite and re-derive your own key numbers — don't inherit them.

## Hard rules (non-negotiable)
- **NO `Task`/`Agent` tools — work INLINE.** Subagents fail here ("Prompt too long").
- **Baseline-first:** full suite, record exact `pytest` N at start (expect ~2423 pass / 10 skip / 0 fail); end strictly ≥, 0 new fails.
- **TDD:** RED → GREEN → REFACTOR; failing test first, for the right reason.
- **Scope-locked:** only the §Scope files. Out-of-scope → STOP + report.
- **No commit** (manager commits after independent re-derivation).
- **READ-ONLY module:** it writes NO state (grep-prove zero write primitives, like `orchestration_metrics.py`).
- **Verify, never assume:** investigate what `events.jsonl` actually records before relying on it; report honestly if a signal is unreliable rather than fabricating it.

## Why this batch exists
Of 45 skills, ~half run **ad-hoc** (Claude invokes them from their SKILL.md description triggers) — OUTSIDE
the sequenced + denetçi + oracle orchestration. The 4 workflows orchestrate only 2 of 5 MCP servers. The
operator wants a **mechanism that audits effective use of all parts** AND tells us (data-driven) which
ad-hoc parts to promote into orchestration next. This is that read-only audit — a sibling of
`scripts/reporting/portfolio_status.py` + `orchestration_metrics.py`, joining the lint family (3a
`skill_mcp_usage`, lint2 `workflow_tool_declared`, F-27, pb1 `skill_graph_consistency`).

## What to build
### `scripts/reporting/capability_coverage.py` (NEW — READ-ONLY, mirror `portfolio_status.py`/`orchestration_metrics.py`)
Anchor `parents[2]` (NOT `CLAUDE_PLUGIN_ROOT` — 0c bare-CLI lesson). Pure where possible; no state writes.

**A. STATIC coverage (plugin-side — no workspace/project data, so the plugin stays agnostic):**
- **Skills (all 45 under `skills/**/SKILL.md`):** classify each into exactly one bucket, in PRECEDENCE order:
  - `orchestrated` — its name (or `writer`) appears in a workflow's `STEPS` table. Import the 4 workflow
    modules (`scripts.orchestration.workflows.{monthly_maintenance,audit_suite,new_project_setup,content_pipeline}`)
    and read their `STEPS` (the names map to skills via the step `name`/`writer`). **[manager-verified]** the
    3 data-driver workflows (monthly/audit/setup) entries have `name`+`writer`+`tool`; **`content_pipeline`
    entries have ONLY `name`/`base`/`artifact`/`is_html`** (no `writer`, no `tool`) → use `step.get("writer")`
    and fall back to the `name`-normalized form (`new_blog`→`new-blog`, `generate_images`→`generate-images`,
    `faq_optimization`→`faq-optimization`). A bare `step["writer"]` will `KeyError` on content_pipeline.
  - `commanded` — referenced by a slash command (`commands/*.md` mentions the skill name / `/<command>` that
    invokes it). Be precise (a prose mention isn't an invocation — prefer the command frontmatter / the
    skill name in the command body).
  - `ad-hoc-only` — neither of the above. (Every skill is reachable via its description triggers, so this is
    NOT "dead" — it means "only reachable ad-hoc, never sequenced/audited". Say exactly that.)
  - Reuse pb1's `skill_graph_consistency.parse_graph` for the skill roster + frontmatter (don't re-parse).
- **MCP tools (from `mcp-tool-registry.json`):** per tool → `orchestrated` (a workflow `STEPS[].tool` **that is
  not `None`** — **[manager-verified]** `schema-audit` in audit + `cluster_map` in setup carry `"tool": None`, and
  `content_pipeline` carries no `tool` key at all → skip those), `declared-only` (in some skill's `mcp_tools` but no
  workflow step — reuse 3a `skill_mcp_usage.declared_tools`), or `unused` (in registry, declared by no skill).
  **[manager-verified]** the registry `servers` object has **4** keys — `gsc/dataforseo/scrapling/sf`. **Higgsfield
  is NOT a server** — it sits under the registry's `external_user_dependencies` (user-level optional; the
  content_pipeline artifact path). So roll up the 4 registry servers + report higgsfield separately as
  "external/optional". Orchestrated servers = **gsc + dataforseo only** (2 of the 4); SF is declared by several
  skills (3a added 4 live-crawl decls) but never orchestrated; scrapling is declared-only. Mind the
  `scrapling`(registry key) vs `ScraplingServer`(runtime/`.mcp.json` key) alias — 3a's `_alias` already maps it.
- **Scripts (`scripts/**/*.py`, excluding tests/__pycache__):** `referenced` (name imported/invoked by a skill
  body, a command, a workflow, another script, OR a test) vs `orphaned` (referenced nowhere). A simple
  grep-for-module-name across the repo is acceptable; be conservative (false "orphan" is worse than false
  "referenced" — flag low-confidence ones).

**B. RUNTIME coverage (OPTIONAL — workspace-side; only when a `--workspace-root` + `--slug` is given):**
- Read `projects/<slug>/_state/events.jsonl` (append-only) + the coverage records (`_state/coverage/*.json`).
  **[manager-verified] (2026-06-09, dentnotion — re-confirm yourself, don't trust blindly):** `events.jsonl`
  has **NO explicit `skill` field.** 4 `event_kind`s seen — `audit`(619), `provenance`(87), `work`(31),
  `workflow`(20). The usable signals: (a) **MCP-tool runtime** ← `audit` events' `audit_target` (shape
  `"{Tool}:{redacted args}"`, e.g. `mcp__gsc__search_analytics:…`); (b) **sheet→writer-skill runtime** ←
  `provenance` events' `target_excel_sheet` (e.g. `gsc_performance` ⇒ the `gsc-pull` writer ran); (c) coverage
  records' `observed_mcp` — but only **1** coverage record exists portfolio-wide today, so that source is
  near-empty live.
- Therefore **skill-level runtime attribution is LIMITED**: report it via the sheet→writer proxy where a skill
  owns a sheet, label everything else "limited/unavailable", and **do NOT fabricate.** MCP-tool-level runtime
  (from `audit_target`) is the reliable signal. Build the runtime layer so its TESTS pass against a SEEDED tmp
  workspace; against live data it will be thin — that is expected and fine. The STATIC half is the must-have.

**C. Report + recommendations:**
- `coverage_report(root, *, workspace_root=None, slug=None) -> dict` returning the buckets + counts +
  per-item lists for skills / MCP / scripts (+ runtime if given).
- A `render_report(report) -> str` compact human view (counts headline + per-category tables), like
  `portfolio_status.render_triage`.
- A **recommendations** section: the `ad-hoc-only` skills ranked by a simple value proxy — e.g. graph
  centrality (how many `produces`+`consumes` edges touch them, from pb1's graph) — so the operator sees
  which to promote into a workflow/router-intent FIRST. Keep the proxy simple + documented.
- A CLI (`python3 -m scripts.reporting.capability_coverage [--workspace-root .. --slug ..]`, exit 0 always,
  like `orchestration_metrics.main`).

### `/pseo-coverage` command (`commands/pseo-coverage.md`) — so the non-coder operator can run it
- Mirror an existing read-only command (e.g. `commands/pseo-status-portfolio.md`). One `!`...`` block that
  invokes the CLI and shows the report. Turkish operator-facing text. **Use `$ARGUMENTS` (NOT `$1`)** for any
  optional slug — there is a known bug where `$1` is empty in command pre-exec blocks (see
  `docs/bugs/2026-06-09-slash-command-positional-args-empty.md`); `$ARGUMENTS` works. Keep it slug-optional
  (static report needs no slug; runtime enrichment uses it).
- **D10 cascade** (a new command — REQUIRED, see `MANAGER.md` "D10"). **[manager-verified] exact surfaces** —
  authority = `tests/docs/test_count_consistency.py` (`test_plugin_json_counts_match_filesystem` +
  `test_marketplace_json_counts_match_filesystem`), which assert `_count_commands()` against BOTH manifest
  `description` strings. Once your 25th `commands/*.md` lands, both tests go RED until you edit:
  - `.claude-plugin/plugin.json` `description`: `"24 slash command"` → `"25 slash command"` (singular "command").
  - `.claude-plugin/marketplace.json` `plugins[0].description`: `"24 commands"` → `"25 commands"` (plural "commands").
  These are the **only two** command-count surfaces (manager grep-confirmed: no other test asserts a command count;
  there is **no** root `plugin.json`). Verify with `python3 -m pytest tests/docs/test_count_consistency.py -q`.
  If your real surfaces differ from the above, STOP and report rather than guess.

### `tests/reporting/test_capability_coverage.py` (NEW — mirror `tests/reporting/test_portfolio_status.py`)
- STATIC: assert each bucket is well-formed; assert KNOWN-orchestrated skills (e.g. `gsc-pull`/`content-decay`
  appear in the monthly STEPS) classify as `orchestrated`; assert a KNOWN ad-hoc skill classifies `ad-hoc-only`;
  assert the 45-skill total is fully partitioned (every skill in exactly one bucket).
- MCP: assert a workflow tool (e.g. `mcp__gsc__search_analytics`) is `orchestrated`; a declared-but-unorchestrated
  tool is `declared-only`.
- READ-ONLY proof: grep the module for write primitives (`open(...'w')`, `os.replace`, `.write_text`, ledger
  appends) → none.
- TEETH: a synthetic tmp skill/command/workflow tree → the classifier buckets a planted skill correctly
  (so the audit isn't vacuous).
- RUNTIME (if implemented): a tmp workspace with a seeded events.jsonl/coverage → the runtime signal reflects it.

## Scope (touch ONLY these)
- NEW `scripts/reporting/capability_coverage.py`
- NEW `tests/reporting/test_capability_coverage.py`
- NEW `commands/pseo-coverage.md` + the D10 cascade edits — BOTH manifest description strings: `.claude-plugin/plugin.json` ("24 slash command"→"25 slash command") AND `.claude-plugin/marketplace.json` ("24 commands"→"25 commands")
- Do **NOT** edit the spine, the workflows, the skills' SKILL.md, the existing lints, or any schema.

## DONE when
- Full suite ≥ baseline, 0 new fails; new tests green incl. teeth + read-only proof.
- Static coverage fully partitions 45 skills (orchestrated/commanded/ad-hoc-only) + MCP + script buckets;
  optional runtime layer works or is honestly labeled limited.
- `/pseo-coverage` renders the report for the operator; D10 count-consistency test green.
- Module is READ-ONLY (grep-proven), `parents[2]`-anchored, reuses pb1 `parse_graph` + 3a `skill_mcp_usage`.

## DURUR (stop + report) if
- `events.jsonl` has no reliable skill attribution AND you cannot cleanly fall back to MCP-tool-level runtime
  (report the finding; ship the static half).
- The D10 surfaces are not exactly what this prompt says (don't guess a manifest edit — STOP).
- A "script orphan" determination is ambiguous enough that you'd risk a false "dead" claim (flag low-confidence).
- Any read-only guarantee would require a state write to satisfy a test (it must not).

## Report back (to the manager)
- Baseline N → final N.
- The full module + test + command diff; the D10 edits.
- The headline coverage numbers (skills: orchestrated/commanded/ad-hoc; MCP: orchestrated/declared/unused;
  scripts: referenced/orphaned) and the top recommended ad-hoc skills to promote.
- The events.jsonl investigation result (what runtime attribution is/ isn't reliable).
- Confirm: READ-ONLY (grep), parents[2], reuses pb1+3a, scope-locked, D10 applied, no spine/skill/schema edit.
