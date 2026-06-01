# Platinum SEO Engine — v1.9.0 Release Notes

**Release date:** 2026-06-01
**Engine HEAD:** post-`<v1.9.0-release>` v1.9.0 release commit (5-file sync via Y-05 fifth production `--apply`)
**Predecessor:** [v1.8.0](RELEASE_NOTES_v1.8.0.md) (Screaming Frog 24 MCP Hybrid Integration milestone)
**Status:** 🟢 GREEN — engine-side seal complete (F-16 + F-17 PASS on post-v1.8 543B baseline; F-13 historical kalıntı)

## 0. Executive Summary

v1.9 is a **hardening cycle**: no new product surface, but the engine's self-governance, spec accuracy, and legacy debt all get tightened. Four threads landed across 7 phases:

1. **Spec v2.3 retrospective** (Phase 1) — 10 lesson-derived accuracy fixes (R-1..R-10) consolidated from v1.8 Worker catches, plus 2 confirmed-drift twins, applied as a docs-only PR.
2. **Three new cross-sheet invariants** (Phases 2–4) — F-24 (`.mcp.json` ↔ `mcp-tool-registry.json` key sync), F-25 (`sf.mcp.enabled` ⇒ `schema_version ≥ 1.5`), F-26 (orphan SF GUI crawl detection, MCP-aware AMBER). The declared invariant count moves **28 → 31**.
3. **F-23 workspace-aware enhancement** (Phase 5) — the only v1.9 phase to modify an existing v1.8 function; additive dual-registry fallback, fully backward-compatible.
4. **Legacy cleanup batch** (Phase 6) — LC-1..LC-6: advisory writer registry, audit-action normalization, `event_id` format codification, ADR-004/005 formal closure, manifest count fixes, and a 19-cite invariant-count reconciliation.

**6 atomic Worker phase commits** (`19f9abb` + `9ecb4f3` + `9f81e8c` + `9009ccf` + `a114fcc` + `ae5f6ad`) + **2 pre-phase docs commits** (`8c00b65` planning + `c91426d` Pre-Phase-1 decisions) + **1 release closeout commit** (this commit). **pytest 1244 → 1286 PASS / 12 SKIP / 0 FAIL** (+42 cumulative; regression sıfır across all phases). **`.mcp.json` UNCHANGED** at 543B / md5 `93523d41e14f90916fefb86d346bd702` (F-16 streak resumes from the post-v1.8 baseline — no MCP transport change in v1.9). **`DECISIONS.md` UNCHANGED** at 6067B; **NO new ADR** (decision D-V1.9-06 — v1.9 reuses existing paterni: retro→ADR-039 paterni, F-24/25/26→F-23 paterni, cleanup→ADR-037 paterni). 0 slug literal in plugin runtime code (plugin agnostik invariant intact).

**Atomic phase paterni** extended by 6 consecutive convergent phases. **Lesson 38 v2** schema-first catches continued (3 in Phase 6 alone: LC-2 6-value audit_action enum, LC-3 `event_id` 3–128+regex, LC-3 Section 7 placement — each was the Worker correcting a stale prompt assumption against the real schema/file).

## 1. Phase-1 — Spec v2.3 retrospective (`19f9abb`)

**Scope:** Consolidate 10 lesson-derived spec/Worker-prompt accuracy fixes (R-1..R-10) from the v1.8 cycle into a single docs PR; zero code/schema/skill change.

### 1.1 Deliverables
- **R-1** broken `validate_schema.py SKILL.md` reference → pytest frontmatter test (worker-prompts).
- **R-2** R13 guard `sf_crawl_progress` → `sf_list_crawls` (enumerator) in the SF MCP hybrid design.
- **R-3** "Schema-First Note" — `failure_reason.code` closed 6-enum verbatim vs DURUR-NN message tokens.
- **R-4** events.schema `source` canonical-keys callout (9 allowed keys; `crawl_id` → envelope).
- **R-5** "Basename Collision Rule" (Type 3) in `docs/WORKER_PROMPTS.md`.
- **R-6** "Step Count Semantics" (9 Body Steps vs 7 `steps[]`).
- **R-7** "F-XX Namespace Rules" in `rules/single-source-of-truth.md` (registry-instance vs SKILL.md narrative; ADR-038 cross-ref).
- **R-8** "Stub-Mod vs Runtime Test Pattern" (Type 2) in `docs/WORKER_PROMPTS.md`.
- **R-9** Phase 7 release-commit AUTHORIZED clarification (#8a commit / #8b tag + §Forbidden exception).
- **R-10** Migration 0005 CLI callout (`--in` / `--out` / `--dry-run`; NO `--apply`).
- **+ 2 confirmed-drift twins** ground-truthed against real scripts: OQ-W-01 (`sf_crawl_progress` → `sf_list_crawls` in v1.8 Phase 3 preflight) + OQ-W-02 (spec Scenario 4 stale `--project vento --no-backup` → real `--in … [--out] [--dry-run]`).

### 1.2 Patterns Born / Reinforced
- **AC-10 grep gate** — all 10 R-XX verified by grep for the absence of the stale token + presence of the fix (3/3 gate PASS).
- **Manager ground-truth verification** — reading the real `migration_0005` argparse flipped OQ-W-02 to "the spec example is the stale side," not the script.

## 2. Phase-2 — F-24 invariant (`9ecb4f3`)

**Scope:** `.mcp.json` `mcpServers` keys must equal `mcp-tool-registry.json` `servers` keys (set comparison). HIGH → RED.

- **`schemas/cross-sheet-invariants.json`** — F-24 entry; rules count **28 → 29**.
- **`scripts/validation/validate_invariants.py`** — `check_F_24` with explicit `_MCP_JSON_KEY_ALIASES` map (`ScraplingServer` → `scrapling`, NOT a naive `.lower()` that would false-FAIL); registered in `_RULE_FUNCTIONS` + `__all__`.
- **`skills/governance/drift-check/SKILL.md`** — F-24 table row + body subsection; implemented-count cite `invariants:21 → 22`.
- **Tests:** +4 (3 happy/fail paths + `test_f24_either_file_missing_skip` SKIP path).
- **Schema-first deviations (Manager-ACCEPTED):** category **`csr_mcp`** not `engine_consistency` (the latter is not in the consistency-report closed 8-category enum); cite is the IMPLEMENTED-function count, distinct from the schema-DECLARED count.

## 3. Phase-3 — F-25 invariant (`9f81e8c`)

**Scope:** `project.config.sf.mcp.enabled = true` ⇒ `schema_version ≥ "1.5"` (Migration 0005 prerequisite coupling). HIGH → RED.

- **`schemas/cross-sheet-invariants.json`** — F-25 entry; rules count **29 → 30**.
- **`scripts/validation/validate_invariants.py`** — `check_F_25` + `_version_tuple` helper using **integer-tuple comparison** (`'1.10' → (1, 10)`; defensive non-int → 0), avoiding the lexicographic bug that would false-FAIL at 1.10; `_SF_MCP_MIN_SCHEMA_VERSION = (1, 5)`.
- **`skills/governance/drift-check/SKILL.md`** — F-25 row + body; cite `22 → 23`.
- **Tests:** +5 (PASS ×3 / FAIL / `test_f25_config_missing_skip` — all verdict branches covered).

## 4. Phase-4 — F-26 invariant (`9009ccf`)

**Scope:** Orphan SF GUI crawl detection — a paused/failed `sf-crawl-orchestrator` run while the SF GUI still reports IN_PROGRESS. **First MEDIUM-severity invariant → AMBER, never RED.**

- **`schemas/cross-sheet-invariants.json`** — F-26 entry; rules count **30 → 31** (🎯 hits the declared-31 target = AC-4/AC-16).
- **`scripts/validation/validate_invariants.py`** — `check_F_26` (180L) MCP-aware via dependency-injected `SfMcpClient` with a 1-second health-probe gate; vacuous-PASS-first, MEDIUM on all verdict paths; helpers `_extract_crawl_id` (reads `steps[].output_ref` — the real workflow-run shape) + `_progress_is_in_progress`.
- **F-16 safe by construction:** F-26 NEVER reads `.mcp.json` — it builds its own client from `_SF_MCP_DEFAULT_URL`; tests inject a fake client.
- **`skills/governance/drift-check/SKILL.md`** — F-26 row + body; cite `23 → 24`; MEDIUM tally `5 → 6`.
- **Tests:** +4 (PASS / AMBER / SKIP paths). category `csr_mcp` (NOT `mcp_runtime`, which is outside the report enum).

## 5. Phase-5 — F-23 workspace-aware enhancement (`a114fcc`)

**Scope:** The ONLY v1.9 phase to modify an existing v1.8 function (REGRESSION-RISK). Additive workspace-aware fallback per Q-V1.9-03.

- **`scripts/validation/validate_invariants.py`** — `check_F_23` enhanced (+59/-22): the engine-repo registry stays PRIMARY; a workspace registry at `{workspace_root}/mcp-tool-registry.json` is a SECONDARY fallback when present. Set-based `missing` computation → FAIL if EITHER existing registry is missing `sf`. A `workspace != engine` guard prevents double-counting; the `if not present → SKIP` branch preserves the v1.8 ambiguous-path behavior verbatim.
- **`schemas/cross-sheet-invariants.json`** — F-23 rationale note (additive; rule shape unchanged).
- **Backward-compat proof:** the 3 existing F-23 tests PASS byte-unchanged; +3 new workspace tests (`+197/-0`, zero deletions). The engine-only case reduces to the EXACT v1.8 logic — which is why the originals still pass.
- **ZERO count drift:** declared 31, implemented 24, HIGH 13, cascade `== 24` all unchanged (F-23 enhancement is additive to an existing function, not a new rule).

## 6. Phase-6 — Legacy cleanup batch LC-1..LC-6 (`ae5f6ad`)

**Scope:** Bounded legacy-debt cleanup + a Manager-expanded invariant-count reconciliation sweep. **Invariant logic UNTOUCHED** (narrative/comment counts only).

- **LC-1** — `scripts/excel/transaction.py`: `WRITER_REGISTRY` constant + `writer_registry_status()` advisory helper. **OPT-IN / advisory only** — `WRITER_REGISTRY_ENFORCEMENT = False` in v1.9; the write path is untouched. (+8 tests.)
- **LC-2** — `scripts/state/events_writer.py`: `normalize_audit_action()` (Edit/Write → `modified`, Read → `accessed`, Bash → `accessed`/`modified`/`deleted`; idempotent; wired into `append_audit`). 6-value enum confirmed against the real schema. (+7 tests.)
- **LC-3** — `rules/events-writer.md`: `event_id` format docs as **Section 7** (Sections 5 + 6 already existed). Codifies the real schema pattern (3–128 chars, `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`), not the prompt's stale 3–50/alphanumeric. (+2 tests.)
- **LC-4** — `docs/DECISIONS_ARCHIVE.md`: ADR-004 + ADR-005 closure footers dated **2026-06-01** (soak window expired 2026-05-12). Original ADR bodies byte-preserved; `DECISIONS.md` untouched.
- **LC-5** — `.claude-plugin/marketplace.json`: active-state count drift fixed (43 → 45 skills / 15 → 18 commands / 3 → 4 MCP servers); `tests/docs/test_count_consistency.py` NEW.
- **LC-6** — 19-cite invariant-count reconciliation across `validate_invariants.py` docstring/comments, `cross-sheet-invariants.json` title, drift-check SKILL.md narrative, monitoring-weekly, and events-writer → all reconciled to **declared 31 / implemented 24 / CRITICAL 5 / HIGH 13 / MEDIUM 6**. The count-consistency test was extended to auto-guard against future drift. **Invariant logic diff-verified clean:** no `check_F_`/`_RULE_FUNCTIONS`/`__all__`/cascade/severity line touched.
- **Tests:** +26 (1260 → 1286).

## 7. Phase-7 — Pilot smoke + release (this commit)

**Scope:** 20-AC verification with fresh evidence, pre-push audit, Y-05 fifth production `--apply`, rollback drill, release commit + annotated tag.

- Full pytest baseline confirmed GREEN; drift-check + schema-validate skill self-runs EXIT 0.
- Pre-push audit Worker dispatched (paterni reuse from the v1.8 round).
- Y-05 5-file version sync 1.8.0 → 1.9.0 (`tests/ci/test_version_sync.py` GREEN post-apply).
- Rollback drill: temp branch → `git reset --hard v1.8.0` → pytest restores the v1.8.0 baseline (1244 PASS / 12 SKIP) → temp branch deleted.
- `git tag -a v1.9.0` annotated (created locally; push deferred to operator approval).

## 8. Schema Changes

| File | Change | Migration? |
|------|--------|-----------|
| `schemas/cross-sheet-invariants.json` | F-24 + F-25 + F-26 entries added (rules **28 → 31**); F-23 rationale note | NO |

No `*.schema.json` structural change beyond the invariants registry. All 31 invariants schema-validate (Draft 7 + existing F-XX format compliance).

## 9. Migrations

**None.** v1.9 introduces no new migration. F-25 *references* Migration 0005 (the v1.8 `project-config` 1.4 → 1.5 bump) as a prerequisite coupling, but adds no new migration script.

## 10. Scripts Impact

| File | Change |
|------|--------|
| `scripts/validation/validate_invariants.py` | `check_F_24` / `check_F_25` / `check_F_26` added + registered; `check_F_23` workspace-aware enhancement; helpers `_version_tuple`, `_extract_crawl_id`, `_progress_is_in_progress`, `_MCP_JSON_KEY_ALIASES` |
| `scripts/excel/transaction.py` | `WRITER_REGISTRY` constant + `writer_registry_status()` advisory helper (LC-1; enforcement OFF) |
| `scripts/state/events_writer.py` | `normalize_audit_action()` (LC-2; wired into `append_audit`) |

## 11. Tests

**Baseline:** 1244 PASS / 12 SKIP (v1.8.0 sealed).
**After v1.9 ship:** **1286 PASS / 12 SKIP / 0 FAIL** (+42 cumulative; SKIP unchanged).

| Phase | Δ PASS | Running total |
|-------|-------|---------------|
| Phase 1 (docs-only retro) | +0 | 1244 |
| Phase 2 (F-24) | +4 | 1248 |
| Phase 3 (F-25) | +5 | 1253 |
| Phase 4 (F-26) | +4 | 1257 |
| Phase 5 (F-23 enhancement) | +3 | 1260 |
| Phase 6 (LC-1..LC-6) | +26 | 1286 |

## 12. Acceptance Criteria results (20 / 20)

All 20 ACs from the v1.9 spec verified with fresh evidence in Phase 7:

| # | Criterion | Result |
|---|-----------|--------|
| 1 | `RELEASE_NOTES_v1.9.0.md` ≥100 lines | ✅ this file |
| 2 | Y-05 fifth `--apply` (5-file sync per ADR-036) | ✅ |
| 3 | `git tag v1.9.0` annotated (local) | ✅ |
| 4 | `cross-sheet-invariants.json` rules 28 → 31 | ✅ (31; F-24/25/26 present) |
| 5 | All 31 invariants schema-validate | ✅ (schema-validate EXIT 0) |
| 6 | `check_F_24/25/26` registered in `_RULE_FUNCTIONS` + `__all__` | ✅ |
| 7 | `check_F_23` workspace-aware; 3 existing F-23 tests still PASS | ✅ (6 PASS) |
| 8 | `transaction.py` `WRITER_REGISTRY` present | ✅ |
| 9 | `events_writer.py` audit_action mapping tightened | ✅ |
| 10 | Spec v2.3 retro R-1..R-10 applied | ✅ (grep gate) |
| 11 | `single-source-of-truth.md` "F-XX Namespace Rules" | ✅ |
| 12 | `events-writer.md` `event_id` format docs | ✅ (Section 7) |
| 13 | `WORKER_PROMPTS.md` R-5 + R-8 clarifications | ✅ |
| 14 | drift-check SKILL.md invariant cite + 3 new rows | ✅ (cite `invariants:24` = implemented count; F-24/25/26 rows present) |
| 15 | pytest 1244 → ≥1263 PASS; 12 SKIP | ✅ (1286 / 12) |
| 16 | drift-check skill EXIT 0; 31 invariants declared | ✅ (EXIT 0 + 31 declared + 3 fns registered) |
| 17 | schema-validate skill EXIT 0 full sweep | ✅ |
| 18 | Pre-push audit Worker dispatched + 0 CRITICAL | ✅ |
| 19 | Rollback drill CLEAN (restore 1244) | ✅ |
| 20 | ADR-004 + ADR-005 closed in `DECISIONS_ARCHIVE.md` | ✅ (2026-06-01, LC-4) |

> **Note on AC-14 / AC-16 "31":** drift-check emits the IMPLEMENTED-function count (`invariants:24`), which is distinct from the schema-DECLARED count (31 rules in `cross-sheet-invariants.json`). The drift-check self-run produces no `invariants:NN` stdout line; AC-16 is satisfied by EXIT 0 + the 31-rule declared array + the 3 new functions registered. This declared-vs-implemented distinction is the established Phase-2 convention, not a defect.

## 13. Backward Compatibility

- **F-23 enhancement is additive** — the engine-only path reduces to the exact v1.8 logic; existing tests pass unchanged.
- **WRITER_REGISTRY is advisory** — enforcement is OFF in v1.9 (`WRITER_REGISTRY_ENFORCEMENT = False`); the write path is unchanged. The v2.0 flip is a future, separately-gated decision.
- **No new migration, no schema-version bump** — existing project configs validate unchanged.
- **`.mcp.json` untouched** — F-16 invariant holds on the post-v1.8 543B baseline; no MCP transport change.
- **No new ADR** — `DECISIONS.md` byte-stable at 6067B.

## 14. Notes for Operators

- **Workshop items OW-1..OW-3 remain deferred** (Path B — after-ship, consistent with the v1.7 Bank Seed Pilot pattern):
  - **OW-1** — v1.8 AC-10 live smoke `/pseo-sf-crawl vento`: capture 3-part evidence (≥14 CSVs + 6 master.xlsx sheets + `sf_mcp` `events.jsonl` source.kind). Requires SF GUI + MCP Server on port 11435.
  - **OW-2** — v1.8 AC-13 tech-audit live `use_sf_mcp_live=True` on vento: rowcount(live) vs rowcount(file-only) comparison.
  - **OW-3** — Bank Seed Pilot completion (iWallet TR YMYL-high + Aluminum Station CA local-service + Eykom hybrid), overlapping the post-Core-Update GSC measurement window (~2026-06-10+).
- **Tier 3 (16 optional SF reports) still excluded by default** (Q-V1.9-02 DEFER v2.0) — the orchestrator runs the 24-report Tier 1 + Tier 2 set.
- **Marketplace PRIVATE → PUBLIC transition (SD-1 / SD-2) deferred to v2.0** (Q-V1.9-05) — a separate operator decision cycle with its own security audit.
- **Push is operator-gated** — the v1.9.0 tag is created locally only; pushing tag + commits to `origin/main` requires explicit operator approval.
