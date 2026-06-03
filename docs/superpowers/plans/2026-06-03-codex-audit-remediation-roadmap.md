# Codex Audit Remediation — Verification Report + Staged Roadmap

> **For agentic workers:** This is the MASTER roadmap. The 31 findings span 6 independent
> subsystems, so per `superpowers:writing-plans` scope-check they are split into 6 batch
> plans. Each batch gets its own detailed bite-sized TDD plan (`superpowers:writing-plans`)
> at execution time. Do NOT execute from this file directly — it is the index + verification
> record + sequencing contract.

**Goal:** Verify every finding in `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md` (Codex, 2026-06-03) and
remediate the confirmed ones in dependency-ordered batches without regressing the 1449-test
green baseline.

**Source audit:** `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md` (engine repo root, untracked — handoff only).

**Verification method:** Inline (subagent dispatch unavailable — session MCP registry exceeds
subagent context budget → "Prompt is too long"). Every finding cross-checked against the
current tree by reading source + running repro commands.

**Baseline (HEAD `1e8b4ed`):** `PSEO_WORKSPACE_ROOT=…/platinum-seo-workspace python3 -m pytest -q`
→ **1449 passed, 8 skipped, 14.79s**.

**Key correction to the audit's premise:** the audit was written against a dirty working tree
(6 modified files). Those changes are now **committed** to HEAD (`c037bdb`→`1e8b4ed`). The 4
"Local-Fixed" items are verified present in HEAD, not pending.

---

## Part A — Verification Verdicts (all 31 + 4 Local-Fixed)

Legend: ✅ CONFIRMED · ⚠️ CONFIRMED (nuance/narrower than stated) · ❌ REFUTED · 🔵 already fixed in HEAD (test-gap only)

### Local-Fixed (verified COMMITTED in HEAD)

| ID | Verdict | Evidence |
|----|---------|----------|
| LF-1 CI MCP count 3→4 | ✅ committed | `c037bdb`; `.github/workflows/ci.yml` invariant=4; `.mcp.json`=4 servers |
| LF-2 secret-scan `--changed-since` | ✅ committed | `35a397b`; `hooks/pre-tool-use.json`… (secret hook now incremental) |
| LF-3 `transaction.update()` `data_start_row` | ✅ committed | `8e39688`; `transaction.py:721-725` scans from `_data_start_row` |
| LF-4 README Draft 7 wording | ✅ committed | `1e8b4ed`; `README.md:243` "Draft 7 — 21 schemas" |

### P0 (6)

| ID | Title | Verdict | Independent severity | Core evidence |
|----|-------|---------|---------------------|---------------|
| P0-01 | Cross-sheet invariant registry ≠ implementation | ✅ **worse than stated** | **P0 (governance integrity)** | Registry `cross-sheet-invariants.json` F-01=`master_task.url ⊆ …`; code `check_F_01`=`status ⊆ statusEnum`. Collision on ~13 IDs (F-01..F-05, F-09..F-14), not 3. `computed_by` = `consistency_check`/`dashboard_refresh` (not the funcs). Sync test locks ID-set + partial severity only — F-04 code=CRITICAL vs registry=HIGH undetected (helper-indirection hides the `severity="…"` literal). |
| P0-02 | `dump_workspace.py` reads `slug` not `active_project` | ✅ | **P0 (breaks manager session)** | `dump_workspace.py:60` `data.get("slug")` → raises; `active.json`=`{"active_project":…}`. `test_dump_workspace.py:124` fixture writes `{"slug":…}` → masks bug. Cross-check: `pseo-schema-audit.md:17` already uses `.active_project`. |
| P0-03 | MCP registry incomplete + version-lagged | ✅ | P1 in practice | `.mcp.json` dataforseo@`2.8.10`; `mcp-tool-registry.json` version_lock=`2.8.9`; 33 tool entries; registry key `scrapling` vs `.mcp.json` `ScraplingServer` (saved at runtime only by F-24 alias map); no Higgsfield. Schema desc itself hardcodes const `2.8.9`. |
| P0-04 | Workspace configs fail current schemas | ✅ **bigger scope** | **P0** | 8/10 projects stale: 7×`1.3`, 1×`1.4` (iwallet); only aluminumstation-ca + miningaa-com on `1.5`. `portfolio.json` 10 active vs `portfolio-config.schema.json` maxItems:8 → "is too long". |
| P0-05 | Command allowed-tools ≠ shell usage | ✅ | P1 (UX/restricted-mode) | `mkdir, grep, head, sort, curl, tail, xargs, find` used undeclared across 7 commands (pseo-active/gbp-audit/init/schema-audit/sf-crawl/sf-status/status). |
| P0-06 | SF crawl command documents invalid contract | ✅ | **P0 (handoff fails)** | `pseo-sf-crawl.md:41` runs `sf_import.py … --source-run-id`; `sf_import.py:268-273` accepts only `--project/--sf-export-path/--workspace-root/--dry-run`; orchestrator skill:468 warns it "makes argparse exit 2". MCP list has 5 of 7 SF tools. |

### P1 (14)

| ID | Title | Verdict | Core evidence |
|----|-------|---------|---------------|
| P1-01 | Draft wording needs test lock | 🔵 test-gap | README fixed in HEAD; no 3-way (README/`$schema`/validator) lock test. |
| P1-02 | `format` not enforced | ✅ | `validate_schema.py:59` `Draft7Validator(schema)` — no `format_checker`. |
| P1-03 | Nested objects too open | ✅ counts exact | Recount matches audit: project-config 15, monthly-report 17, dataforseo 8, gsc 5, portfolio 5, sf-mcp 5. Total 96 open object subschemas. Fix is *selective*. |
| P1-04 | Event conditionals noisy | ✅ | `allOf` if-blocks `if.properties:[event_kind]` but `if.required:[]`. Desc "Three kinds" vs enum 4 (`provenance/work/audit/workflow`). Mitigation: `event_kind` is root-`required`. |
| P1-05 | Hook references nonexistent `/pseo-bootstrap-project` | ✅ | `session-start.json:9` + `user-prompt-submit.json:9`; no `commands/pseo-bootstrap-project.md` (real = `/pseo-init`). Seen live this session. |
| P1-06 | PostToolUse audit drops failures | ✅ | `post-tool-use.json:9` ends `|| true`; hardcodes `audit_action="accessed"` for all Bash. `normalize_audit_action(command=…)` exists `events_writer.py:375` but unused. |
| P1-07 | Excel owner-lock regex too narrow | ⚠️ Bash-branch only | `pre-tool-use.json:9` Bash regex `[\w/.-]+…\.xlsx` misses spaces/quotes/`~`; only blocks when `~$` sidecar exists. Edit/Write branch parses `file_path` correctly. |
| P1-08 | Inline Python injects shell args | ✅ | `pseo-active.md:29` `slug = '$SLUG'` (breaks on quote, no regex validation); line 25 writes marker even when config missing (by-design). |
| P1-09 | Excel transaction contract gaps | ✅ | `_ensure_sheet_with_header:573-576` always writes header to row 1 (ignores `header_row`); row validation `additionalProperties:True` (`:254`); extra keys silently skipped; writer registry advisory (write/append/update don't call `writer_registry_status`). |
| P1-10 | Workflow runner mutates JSON w/o trail | ✅ | `approve(notes=…)` `:535` and `pause(reason=…)` `:564` accept params but `_do()` never forwards → lost. `retry()` deletes `ended_at` `:623` (intentional; mitigated by `fail()` event). |
| P1-11 | `next_run_id()` lockless | ✅ low-risk | `events_writer.py:583` scans for max run_id outside the append flock; concurrent callers can collide. Single-operator usage → low real risk. |
| P1-12 | Brand-onboarding stub-like | ⚠️ by-design stub | `SKILL.md:17` `status: active` but body says "staging-only … deferred to Phase 14"; refs schema `1.2` (stale→1.5) + `config/` path; `brand_onboarding_discovery.py:79` hardcodes `2026 - founding_year`. Real-discovery deferral is roadmap, not bug. |
| P1-13 | generate-images needs user-level Higgsfield | ✅ | `generate-images/SKILL.md` `status: active`, Higgsfield `required: true`; not in `.mcp.json`/registry. |
| P1-14 | Commands reference wrong schema paths | ✅ | `pseo-cannibalization.md:46` → `gsc-mapping` (real `gsc-tool-mapping`); `pseo-schema-audit.md:48` → `dataforseo-mapping` (real `dataforseo-endpoint-mapping`); `:28` `source.kind=sf_export` not in events enum. |

### P2 (8) / P3 (3)

| ID | Title | Verdict | Core evidence |
|----|-------|---------|---------------|
| P2-01 | Workspace README/CLAUDE stale | ✅ | workspace `README.md:23` `config/` subdir (real `project.config.json`); `:38` unprefixed `/quick-wins` etc. |
| P2-02 | Engine docs stale counts | ⚠️ partial | `GLOSSARY.md:13` "28 CSR rule" (actual 31); `ARCHITECTURE.md:51-64` phases "planned" despite v1.9.4. **README counts are correct** (45/18/6/4/21). |
| P2-03 | Mixed template dialects | ✅ | `render_template.py` `string.Template` `$var`; 5 content templates use `{{ }}`; no manifest. |
| P2-04 | Requirements/lock drift | ✅ | `requirements.txt` has no `requests`; `requirements-lock.txt` (Py 3.14) pins `requests==2.33.1`; scripts use `httpx`. |
| P2-05 | project-config version metadata | ⚠️ minor | schema_version const `1.5` vs engine v1.9.4; distinction under-documented. Doc clarity only. |
| P2-06 | Hook helper scripts not wired | ✅ | `scripts/hooks/{check_append_only.sh,check_naming.py,validate_before_write.py,check_excel_writer.py}` exist; none referenced in `hooks/*.json` (CI-only, undocumented). |
| P2-07 | Secret policy weaker than language | ✅ | `check_secrets.sh:197-209` WARNs (not fails) on gitignored `.env`; policy is "zero committed" not "zero on disk". |
| P2-08 | portfolio refs untracked projects | ❌ **REFUTED** | `git ls-files` → all 10 `project.config.json` tracked. Only runtime outputs (master.xlsx, latest events.jsonl, reports/PDFs) untracked. Defensive validation mode still nice-to-have. |
| P3-01 | Historical docs old SF shapes | ⚠️ minor | `docs/WORKFLOWS.md`(1), `…/plans/2026-05-26-…`(3), `…/specs/2026-05-26-…`(7) carry old shapes; dated/located as historical but not labeled. |
| P3-02 | `.DS_Store` under templates/ | ✅ | `templates/.DS_Store` (6148B) present, gitignored/untracked. |
| P3-03 | Stale counts in comments | ✅ | `tests/ci/test_ci_yaml.py:61` + `…enum_v1_1.py:17` comments say "43 SKILL.md" (actual 45). NB `tests/docs/test_count_consistency.py` already guards `"43 skills"`. |

**Tally:** 28 CONFIRMED actionable · 1 already-fixed (test-gap: P1-01) · 1 minor (P2-05) · 1 REFUTED (P2-08).

---

## Part B — Staged Remediation Roadmap (6 batches)

Ordering follows the audit's dependency logic (governance authority → workspace contract →
commands/hooks → schema hardening → state/write → docs cleanup). Each batch is independently
shippable, ends green, and gets atomic commits. **Engine fixes and workspace migration MUST
NOT mix in one commit** (audit guidance + two-repo separation).

### Batch 1 — Governance Authority *(highest priority; the schema-first core)*
**Findings:** P0-01, P0-03, P1-13.
**Approach (proposed):**
- P0-01: make `validate_invariants.py` the runtime source of truth; rewrite `cross-sheet-invariants.json` entries F-01..F-14 to match what the code actually checks; relocate the genuine (unimplemented) cross-sheet join rules to a clearly-deferred section or distinct namespace; fix `computed_by`; add a **semantic-binding test** (each implemented F-ID's registry `rule` text ↔ code `rule` literal must match) + fix the severity-test helper-indirection blind spot.
- P0-03: bump registry `version_lock` 2.8.9→2.8.10 (+ schema desc); add missing skill-used DataForSEO tools to registry; formalize the `ScraplingServer`↔`scrapling` alias with a test.
- P1-13: add an "external/user-level MCP dependency" representation so generate-images preflight fails clearly when Higgsfield is absent (don't install it in plugin `.mcp.json`).
**Test gate:** new semantic-binding test + `test_mcp_registry_versions_match_mcp_json` + `test_skill_mcp_tools_exist_in_registry`; full suite green.
**⚠️ DECISION D1 (Süleyman):** P0-01 authority direction (see Part C).

### Batch 2 — Workspace Contract *(engine fix + workspace migration, SEPARATE commits)*
**Findings:** P0-02, P0-04, P2-05; defensive add for P2-08.
**Approach (proposed):**
- P0-02 (engine): `dump_workspace.py` read `active_project` first, fall back to `slug` with AMBER warning; update `test_dump_workspace.py` fixtures to canonical shape + add legacy-fallback test.
- P0-04 (workspace): migration script `project.config.json` 1.3/1.4→1.5 (chain migrations 0003/0004/0005) for the 8 stale projects; raise/relax `portfolio-config.schema.json` maxItems per D2; add a workspace-validation mode that reports RED without blocking engine CI.
- P2-05: document engine-version vs config-schema-version distinction.
- P2-08: optional `--strict`/`--local` portfolio validation mode.
**Test gate:** `test_dump_workspace_reads_active_project` + migration round-trip tests; re-run the 4 audit repro commands → all PASS.
**⚠️ DECISION D2 (Süleyman):** portfolio cap (see Part C).

### Batch 3 — Commands & Hook UX
**Findings:** P0-05, P0-06, P1-05, P1-08, P1-14.
**Approach:** add missing `Bash(<cmd>:*)` to allowed-tools; rewrite `pseo-sf-crawl.md` to the real `sf_import.py` contract + complete SF MCP tool list (drop `--source-run-id`/`save_report`); replace `/pseo-bootstrap-project`→`/pseo-init` in both hooks; pass slug to Python via `sys.argv`/env + regex-validate; fix the two wrong schema paths + `sf_export`→`sf_csv`.
**Test gate:** `test_command_allowed_tools_match_inline_shell`, `test_command_file_references_exist`, `test_pre_tool_use_hook_references_existing_commands`.

### Batch 4 — Schema Hardening
**Findings:** P1-01, P1-02, P1-03 (selective), P1-04.
**Approach:** `Draft7Validator(schema, format_checker=FormatChecker())` + bad-format fixtures; add `required:["event_kind"]` inside each events `if` + "Three"→"Four kinds" + clean-error fixture; close high-risk nested objects with `additionalProperties:false` (project-config language/paths/gsc/dataforseo/brand/thresholds/workflow first) + misspelled-key negative fixtures; add the 3-way Draft-7 lock test.
**Test gate:** `test_validate_schema_enforces_format`, `test_events_schema_missing_event_kind_has_clean_error`, additionalProperties negative fixtures.

### Batch 5 — State / Write & Audit Hardening
**Findings:** P1-06, P1-07, P1-09, P1-10, P1-11.
**Approach:** route Bash audit through `normalize_audit_action(command=…)` + visible-warning on emit failure (P1-06); broaden owner-lock to parse tool-input paths + cover quoted/spaced/`~` (P1-07); align `_ensure_sheet_with_header` with `header_row` + reject extra row keys by default (`allow_extra` opt-in) + consider writer-registry enforcement (P1-09); persist `reason`/`notes` into workflow JSON + event meta, make emit policy explicit (P1-10); allocate `next_run_id` under the append flock (P1-11).
**Test gate:** `test_post_tool_use_bash_write_classification`, hook owner-lock path tests, `test_excel_create_honors_header_row`, `test_excel_rejects_extra_row_keys`, concurrency test for run-id.

### Batch 6 — Docs / Skills / Templates / Deps Cleanup
**Findings:** P1-12, P2-01, P2-02, P2-03, P2-04, P2-06, P2-07, P3-01, P3-02, P3-03.
**Approach:** brand-onboarding stale refs (1.2→1.5, `config/` path, dynamic year) + clarified staging banner (P1-12); align workspace docs (P2-01); extend `test_count_consistency.py` to mechanically check GLOSSARY/ARCHITECTURE counts (P2-02, P3-03); template dialect manifest + per-template renderer test (P2-03); reconcile requirements/lock + document lock-gen (P2-04); document hook-script CI-vs-runtime split + `test_hook_scripts_exist` (P2-06); rename secret policy to "zero committed/changed" (P2-07); label historical SF docs (P3-01); remove `templates/.DS_Store` + ensure `git archive` packaging (P3-02).
**Test gate:** `test_workspace_docs_command_names_exist`, extended count-consistency test.

---

## Part C — Decisions Pending Süleyman (recommendations baked in)

- **D1 — P0-01 authority direction.** *Recommendation:* keep `validate_invariants.py` as runtime
  truth (it's what drift-check runs on real projects), rewrite the registry to describe the
  actually-implemented rules, and add the semantic-binding test. *Why:* changing the code's
  behavior risks regressing live drift-check verdicts across 10 projects; the registry is the
  cheaper, safer thing to correct.
- **D2 — portfolio cap (maxItems:8).** *Recommendation:* raise to 12 (or make configurable).
  *Why:* the portfolio already runs 10 active projects (miningaa added 2026-06-03); evidence says
  8 is stale, not a deliberate enforced limit. Alternative: enforce archival to ≤8 (heavier).
- **D3 — brand-onboarding status.** *Recommendation:* keep `status: active`, fix the stale refs +
  hardcoded year, add an explicit "staging-only (real discovery Phase 14)" banner. *Why:* real
  discovery wiring is roadmap-deferred; the only true bugs are stale version/path + `2026` literal.

---

## Sequencing & Guardrails

1. Batches are dependency-ordered; do them in order (1→6) unless Süleyman re-prioritizes.
2. One batch → one (or few) atomic commits; **never mix engine + workspace** in a commit.
3. Each batch ends with the full suite green (≥1449 passed) + its named new tests.
4. Per finding-class, add a regression test so the same drift cannot return (audit's Test Backlog §).
5. Branch off `main` before any commits (do not commit to `main` without Süleyman's go).
6. `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md` is a handoff artifact — do not commit it.
