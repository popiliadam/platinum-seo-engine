# Open Questions

## Unresolved

### Q-V1.9-PHASE-2-CLOSURE-FOLLOWUPS-01: v1.9 Phase 2 closure — 2 LOW schema-first deviations (both ACCEPTED) [P3] ✅ ACCEPTED 2026-06-01
**Raised:** 2026-06-01 v1.9 Phase 2 closure (Manager GO after independent verification). Worker Output Package §"Open Questions" + Manager cross-check (F-16 md5, schema entry, registration, cascade).
**Context:** Phase 2 Worker implemented F-24 (`.mcp.json`↔`mcp-tool-registry.json` servers-key sync; check_F_24 + JSON entry + drift-check + 4 tests; pytest 1248/12/0; F-16 .mcp.json md5 unchanged). Surfaced 2 LOW schema-first deviations from the dispatch — both genuine ground-truth catches, both improve correctness, neither blocked GO. Schema-first-wins paterni reuse (v1.8 Q-PHASE-3-WORKER-06/07).

**Deviation table:**
| ID | Deviation | Severity | Manager Decision |
|----|-----------|----------|------------------|
| Q-V1.9-PHASE-2-WORKER-01 | spec FE-1 + dispatch JSON specified `category="engine_consistency"`, but `consistency-report.schema.json` `checks[].category` is a closed 8-value enum (csr_foundation/csr_data/csr_mcp/staging_excel_diff/url_normalization/schema_validation/row_count_integrity/file_hash_integrity) — `engine_consistency` is NOT among them → `build_consistency_report` would raise ConsistencyReportInvalidError/DURUR-6 + fail test_consistency_report_schema_valid. Worker used `csr_mcp` in BOTH schema entry + check fn. | LOW (schema-first catch) | ✅ **ACCEPT csr_mcp** — pre-blessed by memory (`project_consistency_report_category_enum.md`) + mirrors F-23 (analogous .mcp.json↔registry MCP invariant) + report-schema-valid + registry↔code aligned. spec FE-1 "engine_consistency" is a confirmed spec error → v1.10 spec retro note. **⚠️ CARRY TO PHASE 4 F-26:** spec FE-3 tags F-26 `csr_mcp + mcp_runtime` — `mcp_runtime` is ALSO outside the 8-enum → F-26 must emit `csr_mcp` alone (baked into Phase 4 dispatch note). |
| Q-V1.9-PHASE-2-WORKER-02 | dispatch said update count cite `invariants:28`→`29` in 3 locations, but the actual SKILL.md literal was `invariants:21` (the IMPLEMENTED-function count len(_RULE_FUNCTIONS)=21, distinct from the schema-DECLARED rules count 28). Worker bumped the real cite 21→22 (4 cite spots + "12 HIGH" prose + `### HIGH (12)`) + the JSON declared count 28→29 separately. | LOW (count-conflation catch) | ✅ **ACCEPT 21→22** — drift-check emits implemented count, not declared. **DEFER sibling cites to Phase 6 docs sweep:** stale `invariants:NN` cites in OTHER files NOT in Phase 2 scope — `skills/reporting/monitoring-weekly/SKILL.md:115,502` (=21) + `rules/events-writer.md:156` (=20). Reconcile ALL to the FINAL implemented count **24** AFTER Phase 4 (F-25 22→23, F-26 23→24; F-23 enhancement adds no function). Same class as v1.8 Q-PHASE-4-WORKER-02 (docs-sweep deferral). **⚠️ Phase 7 AC-16:** "31 invariants enumerated" = schema-DECLARED (JSON rules 31); drift-check self-run emits NO `invariants:NN` stdout (audit_payload is a dict literal) → AC-16 satisfied by EXIT 0 + JSON 31 rules + 3 new functions registered. |

**Note (out-of-band):** Worker also wrote `…/memory/project_consistency_report_category_enum.md` (user auto-memory, OUTSIDE engine repo — not in the Phase 2 commit) to warn the Phase 4 F-26 Worker about the category-enum trap. Benign + accurate + matches the existing MEMORY.md index entry; left as-is.

**Cross-refs:** `docs/PHASE_STATUS.md` v1.9 Phase 2 DONE entry; Phase 2 Worker Output Package; `schemas/cross-sheet-invariants.json` F-24 entry (csr_mcp); `scripts/validation/validate_invariants.py:990` check_F_24 + `_MCP_JSON_KEY_ALIASES`; `consistency-report.schema.json` checks[].category 8-enum; spec FE-1 (engine_consistency error) + FE-3 (F-26 mcp_runtime error, Phase 4); memory `project_consistency_report_category_enum.md`.

### Q-V1.9-PHASE-1-CLOSURE-FOLLOWUPS-01: v1.9 Phase 1 closure — 2 confirmed-drift twins FIXED + 1 methodology nit DEFERRED [P3] ✅ 2/3 RESOLVED 2026-06-01
**Raised:** 2026-06-01 v1.9 Phase 1 closure (Manager GO decision after ground-truth cross-check). Worker Output Package §"Open Questions Surfaced" (2 OQs) + Manager ground-truth verification surfaced a 3rd twin via Fix Worker.
**Context:** Phase 1 Worker applied R-1..R-10 (spec v2.3 retro, docs-only, AC-10 grep gate 3/3 PASS, pytest 1244/12 preserved) and surfaced 2 out-of-scope drift OQs. Manager ground-truthed both against the real `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py` argparse (`--in` required / `--out` / `--dry-run`; NO `--apply`, NO `--project`, NO `--no-backup`, NO `--reverse`) and confirmed both are genuine drift of the exact R-2/R-10 class Phase 1 targets. Both FIXED via narrow Fix Worker (Agent tool, general-purpose; paterni reuse v1.8 Phase 1 W-1 Fix Worker round) + folded into the Phase 1 atomic commit. A 3rd twin surfaced during the Fix Worker run.

**Resolution table:**
| ID | Drift | Severity | Manager Decision |
|----|-------|----------|------------------|
| OQ-V1.9-P1-W-01 | `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md:225` (v1.8 Phase 3 preflight) called `mcp__sf__sf_crawl_progress` for an "ANY in-progress crawl?" check — circular (needs crawl_id). Twin of R-2 (which fixed only the spec R13 mitigation). | LOW | ✅ FIXED Phase 1 — Fix Worker changed to `mcp__sf__sf_list_crawls` (enumerator) + self-documenting parenthetical. Line 227 poll `sf_crawl_progress(crawl_id)` left intact (correct). |
| OQ-V1.9-P1-W-02 | spec Scenario 4 (lines 664-665, 673) invoked `migration_0005 --project vento [--dry-run] [--no-backup]` — but real argparse is `--in`/`--out`/`--dry-run` (NO `--project`/`--no-backup`). R-10 codified the CORRECT shape; spec Scenario 4 was the stale side. | LOW | ✅ FIXED Phase 1 — Fix Worker changed to `--in projects/vento/project.config.json [--out PATH] [--dry-run]` + backup note to "in-place mode (default; omit --out)". sf_import.py `--project` refs (spec:579/616/884) left intact (correct — different script). |
| OQ-V1.9-P1-W-03 | `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md:599` (v1.8 Phase 7 rollback-drill task #7) describes `migration_0005 --project vento --reverse` — `--reverse` does not exist (forward-only 1.4→1.5 script); line already hedged "(or equivalent rollback if migration script supports)". | LOW | ⏳ **DEFERRED to v1.10 retro** — methodology reword (the real v1.8 drill used `git reset --hard`; v1.9 PROMPT 7 already prescribes git-reset correctly). NOT a clean flag-swap like W-01/W-02; in a shipped historical file; zero runtime impact. Manager boundary: Phase 1 fixes verified flag-swaps of R-2/R-10 class, defers methodology rewords (scope-discipline per v1.8 "dispatch cascade over-specification" lesson). |

**Cross-refs:** `docs/PHASE_STATUS.md` v1.9 Phase 1 DONE Active Phase entry; Phase 1 Worker Output Package; spec R-2 (sf_list_crawls) + R-10 (migration_0005 CLI) authority; `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py:99-107` (argparse ground truth); Fix Worker dispatch (3 edits applied + line 599/884 protected).

### Q-V1.9-PRE-PHASE-1-DECISIONS-01: v1.9 Spec Retro + Invariants + Cleanup — 6 Pre-Phase-1 operator decisions [P1] ✅ RESOLVED 2026-06-01
**→ RESOLVED 2026-06-01 v1.9 Manager session bootstrap (operator dispatch "phase 1'i ilet … fresh session'da başlatayım" = proceed-to-Phase-1 without overrides → all 6 defaults applied per documented "operator silent on any → Manager applies default" rule):** Süleyman Phase 1'e geçiş istedi, hiçbir Q-V1.9-XX override belirtmedi → 6 kararın tamamı spec v1.0 "Open Questions for Operator Review" (lines 391-401) + Worker Prompts Pre-Phase-1 table (lines 14-21) default'larıyla lock'landı. **NO new ADR** (D-V1.9-06); DECISIONS.md 6067B/77B headroom korundu. Path B confirmed (v1.9 cycle dispatch FIRST → operator workshop AFTER ship). Paterni reuse: v1.8 Q-SF-MCP-PRE-PHASE-1-DECISIONS-01 (8-decision umbrella format).

**Resolutions table:**
| # | Q | Default Applied | Lock'ladığı yer | Status |
|---|---|------------------|-----------------|--------|
| 1 | Q-V1.9-01 OW-1+OW-2 workshop timing | After v1.9 ship (Path B; v1.7 Bank Seed Pilot paterni) | Phase 7 AC-10/AC-13 evidence window post-ship | ✅ |
| 2 | Q-V1.9-02 FE-4 Tier 3 inclusion | DEFER v2.0 (no operator use-case for 40-vs-24 expansion) | Orchestrator default 24 reports unchanged | ✅ |
| 3 | Q-V1.9-03 FE-5 F-23 enhancement scope | Additive workspace fallback (engine-repo primary; backward compat) | Phase 5 implementation approach | ✅ |
| 4 | Q-V1.9-04 LC-4 ADR-004/005 closure | Close NOW (soak expired 2026-05-12; >14 days post-deadline) | Phase 6 DECISIONS_ARCHIVE.md append | ✅ |
| 5 | Q-V1.9-05 SD-1+SD-2 marketplace decision | DEFER v2.0 (separate Süleyman karar; security audit needed) | v1.9 closeout — NO PUBLIC transition | ✅ |
| 6 | Q-V1.9-06 New invariants test pyramid | 4+ test cases per invariant (F-23 paterni reuse) | Phase 2-4 test scope | ✅ |

**Raised:** 2026-06-01 v1.9 Manager session bootstrap. Spec authority: `docs/superpowers/specs/2026-05-26-v1.9-retro-invariants-cleanup-design.md` (v1.0, 439 lines) + companion `docs/superpowers/plans/2026-05-26-v1.9-worker-prompts.md` (661 lines, 7 Worker Prompts).
**Context:** Spec v1.0 "Open Questions for Operator Review" table (6 Q-V1.9-XX) + Worker Prompts Pre-Phase-1 table (lines 12-23) listed 6 decisions to lock before Phase 1 dispatch. Operator opted to proceed without overrides → Manager applied all defaults.
**Cross-refs:** spec v1.0 lines 391-401 (6 Q table) + Worker Prompts lines 14-21 (default table) + D-V1.9-06 (no new ADR) + D-V1.9-07 (6-question rationale) + `docs/PHASE_STATUS.md` v1.9 Active Phase entry + `docs/CONTEXT_LEDGER.md` v1.9 Pre-Phase-1 entry.

### Q-SF-MCP-PHASE-5-CLOSURE-FOLLOWUPS-01: v1.8 Phase 5 closure — 1 LOW Worker followup (test name convention) [P3] ✅ ACCEPTED 2026-05-26
**Raised:** 2026-05-27 v1.8 Phase 5 closure (Manager GO decision after cross-check). Worker Output Package §"Open Questions Surfaced" + Manager review.
**Context:** Phase 5 Worker (4 SKILL.md + 4 test files; +706 LoC additive only; stub-mod pattern 4'üncü cumulative reuse) surfaced 1 LOW Open Question about test name convention deviation from Manager dispatch example.

**Worker Open Question (Manager review):**
| ID | Question | Severity | Manager Decision |
|----|----------|----------|------------------|
| Q-PHASE-5-WORKER-01 | Manager dispatch example test name `test_default_behavior_no_mcp` was illustrative ("mock path + regression path"). Worker chose `test_use_sf_mcp_live_flag_in_frontmatter` (asserts default=False which IS the regression-preservation contract) + `test_skill_md_documents_sf_mcp_live_pattern` (stub-mod contract lock for the 4 R9/R12 patterns). Defensible Worker interpretation; functionally equivalent to Manager's "mock path + regression path" pair. v2.3 spec retrospective could update example name. | LOW | ✅ ACCEPT — Worker's stub-mod test pattern architecturally more correct than Manager dispatch's runtime-mock suggestion. Aligned with project's stub-mod 4'üncü cumulative reuse (memory project_phase_lessons.md: v1.7 Task 2.3 generate-images + Task 3.2 brand-onboarding discovery + Task 3.5 init-project cascade + Phase 5 consumer wiring = 4 cumulative applications). Runtime wiring lives in SKILL.md prose (executed by skill body interpreter Phase 11/14 operator workshop); pure-transform scripts intentionally unchanged; AC-13 (Phase 7 pilot smoke) covers actual runtime verification. v2.3 retrospective: Manager Worker Prompt template should clarify "contract test" vs "runtime mock test" expectations |

**Stub-mod pattern verification (post-Phase-5):** 4 cumulative applications across v1.7 + v1.8:
1. v1.7 Task 2.3 generate-images skill (IPTC writer runtime impl deferred Phase 11/14; SKILL.md contract Step 5b + paired test_generate_images.py contract test)
2. v1.7 Task 3.2 brand-onboarding discovery stage (Stage A DFS+Scrapling runtime impl Phase 11; SKILL.md contract + paired test)
3. v1.7 Task 3.5 init-project cascade (Migration 0005 cascade contract; init-project SKILL.md + paired test_init_project.py contract; runtime cascade Phase 11/14 operator workshop)
4. v1.8 Phase 5 consumer wiring (4 skills × use_sf_mcp_live runtime branch impl Phase 11/14; SKILL.md prose contract + paired test pattern lock)

**Cross-refs:** `docs/PHASE_STATUS.md` Active Phase v1.8.0 Phase 5 DONE section; Phase 5 Worker Output Package; D-SF-11 (consumer skill opt-in flag spec); Q-SF-MCP-07 Pre-Phase-1 lock (all-4 in v1.8); spec v2.2 Skills Integration Matrix Category C lines 122-125 (canonical report_name per skill); AC-13 (Phase 7 pilot smoke for tech-audit live verification); memory project_phase_lessons.md "Stub-mod pattern".

### Q-SF-MCP-PHASE-4-CLOSURE-FOLLOWUPS-01: v1.8 Phase 4 closure — 2 LOW Worker followups [P3] ✅ ALL ACCEPTED 2026-05-26 (Phase 6 docs sweep absorbs)
**Raised:** 2026-05-26 v1.8 Phase 4 closure (Manager GO decision after cross-check). Worker Output Package §"Worker Open Questions" + Manager review.
**Context:** Phase 4 Worker (5 SKILL.md edits + F-23 invariant + drift-check expansion + 6 test files) surfaced 2 LOW Open Questions, both deferred to Phase 6 docs sweep where their target files are in scope. Tümü Phase 4 GO kararını ENGELLEMEDİ.

**Worker Open Questions (Manager review table):**
| ID | Question | Severity | Manager Decision |
|----|----------|----------|------------------|
| Q-PHASE-4-WORKER-01 | F-23 dual-namespace collision: cross-sheet-invariants.json:F-23 (SF MCP cross-sheet, v1.8) coexists with drift-check SKILL.md Engine Self-Governance F-23..F-28 (v1.4 deep-audit-fix, doc-only labels). Same F-XX label in disjoint stores. Worker added inline "Naming-namespace note" subsection in drift-check SKILL.md for immediate documentation. Resolution path: renumber engine self-governance F-23..F-28 → F-29..F-34 in Phase 6 docs sweep (SKILL.md narrative labels exempt from ADR-038 persistent-registry renumber-forbidden policy since they don't have audit history references). | LOW | ✅ ACCEPT — non-blocking; both namespaces consumed via disjoint paths (instance JSON vs doc-only narrative). Phase 6 docs sweep renumbers engine self-governance labels. v2.3 spec retrospective note: spec should clarify "F-XX" namespace rules (registry-instance IDs vs SKILL.md narrative IDs) |
| Q-PHASE-4-WORKER-02 | skills/reporting/monitoring-weekly/SKILL.md lines 115 + 502 cite stale "invariants:20" literal (drift-check now emits invariants:21 post-F-23). Runtime regex consumption (lines 73, 169, 198, 431) uses wildcard `invariants:*` prefix → behavior remains correct; only documentation cites are stale. monitoring-weekly NOT in Phase 4 5-file modification scope so deferred per Manager dispatch ("log new Open Question rather than fixing inline"). | LOW | ✅ ACCEPT — Phase 6 docs sweep updates monitoring-weekly cites (target file in Phase 6 scope alongside other reporting docs); runtime behavior unaffected by stale doc cites |

**Cross-refs:** `docs/PHASE_STATUS.md` Active Phase v1.8.0 Phase 4 DONE section; Phase 4 Worker Output Package; cross-sheet-invariants.json F-23 entry (severity HIGH, category csr_mcp); drift-check SKILL.md "Naming-namespace note" subsection (inline documentation); spec v2.2 line 207 (F-23 spec authority) + lines 208-210 (F-24/25/26 deferred to v1.9 per Manager scope).

### Q-SF-MCP-PHASE-3-CLOSURE-FOLLOWUPS-01: v1.8 Phase 3 closure — 7 Worker followups (5 LOW + 2 MEDIUM schema-first catches) [P2-P3] ✅ ALL ACCEPTED 2026-05-26
**Raised:** 2026-05-26 v1.8 Phase 3 closure (Manager GO decision after BIGGEST-PHASE cross-check). Worker Output Package §"Worker Open Questions" + Manager review.
**Context:** Phase 3 Worker (BIGGEST phase, 1994 LoC) surfaced 7 Open Questions during sf-crawl-orchestrator authoring. **Tümü Phase 3 GO kararını ENGELLEMEDİ + 2'si (Q-06 + Q-07) schema-first catch wins that improved correctness vs spec example shapes.** v2.3 spec retrospective items consolidated.

**Worker Open Questions (Manager review table):**
| ID | Question | Severity | Manager Decision |
|----|----------|----------|------------------|
| Q-PHASE-3-WORKER-01 | Bonus 11th test (`test_frontmatter_validates_against_schema`) added because Manager's `validate_schema.py SKILL.md` verification command doesn't work (script needs 2 args, see Q-03). Resulting count 11+6+1=18 vs Manager's "17". Accept or relabel? | LOW | ✅ ACCEPT — bonus test mirrors sf-import paterni; provides effective gate replacing broken verification command |
| Q-PHASE-3-WORKER-02 | Manager prompt listed `tests/skills/test_sf_crawl_orchestrator.py` + `tests/scripts/test_sf_crawl_orchestrator.py` (same basename) → default pytest namespace-package collection error. Worker renamed scripts version to `test_sf_crawl_orchestrator_helpers.py`. Accept or add __init__.py to test dirs (broader pytest config scope)? | LOW | ✅ ACCEPT — semantic rename (helpers vs skill body) richer than __init__.py addition; avoids touching repo-wide pytest config |
| Q-PHASE-3-WORKER-03 | Manager verification command `python3 scripts/validation/validate_schema.py SKILL.md` returns usage error + exit 0 (script needs 2 args data.json + schema.json, not 1). Equivalent frontmatter validation done via pytest case. Fix Manager Worker Prompt template? | LOW (v2.3 retro) | ✅ ACKNOWLEDGE — v2.3 spec retrospective fix; current bonus test (Q-01) covers the gate |
| Q-PHASE-3-WORKER-04 | Manager prompt said "9 steps" but listed 8 named steps (preflight..complete). Worker followed dfs-pull/gsc-pull convention: `complete` is workflow_runner.complete() transition NOT a step in steps[]; resulting body protocol = 9 numbered Steps (create_run + 7 workflow steps in steps[] + complete transition). Confirm interpretation? | LOW | ✅ ACCEPT — interpretation matches dfs-pull/gsc-pull paterni reuse; `complete` as transition not step |
| Q-PHASE-3-WORKER-05 | R13 concurrent-crawl guard: Manager prompt said `mcp__sf__sf_crawl_progress` but that tool requires a `crawl_id` parameter (circular for "any in-progress?" enumeration). Worker used `mcp__sf__sf_list_crawls` (natural enumerator) + declared under mcp_tools.optional. Confirm? | LOW (v2.3 retro) | ✅ ACCEPT — `sf_list_crawls` is correct tool for enumeration; v2.3 spec retrospective fix in R13 mitigation text |
| **Q-PHASE-3-WORKER-06** | Failure code enum mismatch: Manager prompt implied custom codes (`sf_mcp_offline`, `tier1_export_failed`, etc.) but `workflow-run.schema.json` `failure_reason.code` is closed 6-value enum (`validation_error`/`mcp_error`/`budget_exhausted`/`user_rejected`/`timeout`/`internal_error`). Worker mapped: orch-1/2/7/8→mcp_error; orch-4/5→validation_error; orch-3→timeout; orch-6→internal_error. DURUR identity preserved as `DURUR-orch-N` token in `failure_reason.message`. Confirm or propose alternative? | **MEDIUM (schema-first catch)** | ✅ **ACCEPT — schema-first wins**: closed enum preserved; DURUR identity in human-readable message; cross-check verified 9 code= invocations all canonical. v2.3 spec retrospective note: DURUR examples should NOT imply custom codes |
| **Q-PHASE-3-WORKER-07** | Source dict additionalProperties=false: Manager prompt's body example used `source={"kind":"sf_mcp","crawl_id":...,"reports_exported":...}` but `events.schema.json` `source` only allows `kind/source_folder/filename_original/filename_normalized/file_hash/row_count/response_bytes/mcp_server/mcp_tool` (closed schema). Worker replaced with canonical keys (kind + mcp_server + mcp_tool + response_bytes + row_count) and moved `crawl_id` to envelope JSON at `inbox/sf-mcp/{date}-sf-crawl-{slug}.json` (envelope allows arbitrary properties). Confirm? | **MEDIUM (schema-first catch)** | ✅ **ACCEPT — schema-first wins**: closed-shape source dict preserved; crawl_id in envelope JSON (architecturally cleaner); Worker added inline `# events.schema source.additionalProperties=false; only these keys are valid:` comment. v2.3 spec retrospective note: spec example shapes in §Data Flow sections should be schema-validated before publication |

**v2.3 spec retrospective backlog items (consolidated from this phase's 7 Worker Open Questions):**
1. Q-03 + Q-05 + Q-06 + Q-07 = 4 prompt/example accuracy issues — spec example shapes should be schema-validated; verification commands should be runnable as-written
2. Q-02 basename collision — Worker Prompts file template should differentiate skill-tests vs script-tests via suffix (e.g., `test_<skill>.py` for skills/, `test_<skill>_helpers.py` for scripts/)
3. Q-04 step count semantics — spec should clarify whether `complete` is a step in steps[] or a workflow transition (current pattern: transition; pre-existing dfs-pull/gsc-pull paterni)

**Cross-refs:** `docs/PHASE_STATUS.md` Active Phase v1.8.0 Phase 3 DONE section; Phase 3 Worker Output Package; `schemas/workflow-run.schema.json` failure_reason.code enum + `schemas/events.schema.json` source.additionalProperties=false (cited inline in SKILL.md); D-SF-07 (sf-import body UNCHANGED); D-SF-16 (atomic rollback semantics, DURUR-orch-8); Q-SF-MCP-02 + Q-SF-MCP-10 Pre-Phase-1 locks.

### Q-SF-MCP-PHASE-2-CLOSURE-FOLLOWUPS-01: v1.8 Phase 2 closure — 3 LOW-severity Worker followups [P3] ⏳ DEFERRED to Phase 3/7
**Raised:** 2026-05-26 v1.8 Phase 2 closure (Manager GO decision after cross-check). Worker Output Package §"Open Questions Surfaced" + Manager review.
**Context:** Phase 2 Worker Output Package surfaced 3 LOW open questions. Tümü Phase 2 GO kararını ENGELLEMEDİ; Phase 3-7 dispatch'lerinde scope check için ayrı entries.

**Followups table:**
| ID | Question | Severity | Target Phase | Manager Note |
|----|----------|----------|--------------|--------------|
| Q-PHASE-2-WORKER-01 | `scripts/util/sf_mcp_client.py` `call_tool` path implements JSON-RPC error field handling (non-null `error` in response → `SfMcpToolError` with `rpc_error` attribute + stderr log) but no dedicated test case explicitly covers it. Phase 3 orchestrator's end-to-end exercises will surface it naturally. Add explicit test? | LOW | Phase 3 (orchestrator tests will naturally cover) OR Phase 7 (closeout regression-lock) | Defer; Phase 3 Worker can add when wiring orchestrator → client error paths |
| Q-PHASE-2-WORKER-02 | `python3 -m pip install -r requirements.txt` PEP-668-blocked on Homebrew-managed system Python (venv would fix). Existing `httpx==0.28.1` satisfies pin via system site-packages so all 1203 tests pass. Worker prompt's `pip install` verification step cannot run cleanly on this host. | LOW (operator-side) | Phase 7 (CI matrix step runs install verification on fresh runner) OR pre-Phase-7 dev-setup doc | Defer; recommend operator runs install verification inside venv; CI catches |
| Q-PHASE-2-WORKER-03 | `scripts/util/sf_mcp_client.py` 326 LoC vs spec's "~150 LoC" hint. Overhead = docstrings (module + class + each public method) + 6-step `_handle_response`. Worker self-flagged for Manager call. | LOW (style/scope) | Resolved this Phase | **Manager ACCEPT** — D-SF-14 "establishes pattern for future HTTP MCPs" framing explicitly justifies verbose self-documentation; runtime correctness unaffected; no trimming requested |

**Cross-refs:** `docs/PHASE_STATUS.md` Active Phase v1.8.0 Phase 2 DONE section; Phase 2 Worker Output Package; ADR-039 (DECISIONS.md:62-66); D-SF-14 pattern-establishment rationale (spec v2.2 line 90).

### Q-SF-MCP-PHASE-1-CLOSURE-FOLLOWUPS-01: v1.8 Phase 1 closure — 4 LOW-severity followups (3 Worker-surfaced + 1 description polish) [P3] ⏳ DEFERRED to Phase 2/6
**Raised:** 2026-05-26 v1.8 Phase 1 closure (Manager session GO decision after Fix Worker round). Worker Output Package §"Open Questions Surfaced" + Manager post-Fix cross-check polish note.
**Context:** Phase 1 Worker Output Package surfaced 3 LOW open questions; Manager Fix Worker round surfaced 1 additional polish item. Tümü Phase 1 GO kararını ENGELLEMEDİ (LOW + no runtime impact); ayrı entries ile track edilirler ki Phase 2/6 dispatch'lerinde scope check'inde gözden kaçmasınlar.

**Followups table:**
| ID | Question | Severity | Target Phase |
|----|----------|----------|--------------|
| Q-SF-MCP-PHASE-1-WORKER-01 | Should `test_events_schema_source_kind_enum_v1_1.py` mirror the event_type enum test pattern for the source.kind enum (sf_mcp added there)? Current state: schema-validate full sweep covers it indirectly; no dedicated test. v1.6 H-E paterni would prescribe a dedicated test for the enum bump. | LOW | Phase 2 nice-to-have OR Phase 7 closeout regression-lock |
| Q-SF-MCP-PHASE-1-WORKER-02 | `tests/migrations/test_0004_project_config_1_3_to_1_4.py::test_migration_idempotent_on_v1_4` constructs a v1.4 doc + asserts migration_0004 returns it unchanged. Still works (migration_0004 idempotent), but the constructed doc would NOT validate against the new v1.5 schema. Should the test be amended to validate-against-schema OR scope it migration-only (current state)? | LOW (behavior-correct) | Phase 7 closeout when rollback drill exercises v1.4→v1.5→v1.4 reverse |
| Q-SF-MCP-PHASE-1-WORKER-03 | `tests/skills/test_brand_onboarding.py:418-424` staging artifact uses `sf_exports_dir: "sf_exports"` + `staging_dir: "staging"` (legacy flat paths, not modern `inbox/sf` + `_state/cache`). Pre-existing drift unrelated to Phase 1. Should a Phase 2/3 cascade fix update? | LOW (pre-existing) | Phase 5 or Phase 7 code-review pass |
| Q-SF-MCP-PHASE-1-POLISH-01 | `schemas/sf-mcp-tool-mapping.schema.json` `sfMcpTool` description text still cites "Convention: sf__&lt;verb&gt;" + "verified against `claude mcp list` for sf server" — both inaccurate post-Fix-Worker correction. Native form is `sf__sf_<verb>` (server prefix + native tool name kept verbatim); the `claude mcp list` verification was never actually performed by Phase 1 Worker. Description text-only polish. | LOW (description, no behavior) | ✅ APPLIED v1.8 Phase 6 (Manager Override absorb item; sf-mcp-tool-mapping.schema.json sfMcpTool description text refined to accurate `{server_key}__{native_tool_name_verbatim}` ⇒ `sf__sf_<name>` convention; "verified against claude mcp list" inaccurate claim removed) |

**Cross-refs:** `docs/PHASE_STATUS.md` Active Phase v1.8.0 Phase 1 DONE section; Phase 1 Worker Output Package; Manager Fix Worker dispatch + cross-check; spec v2.2 lines 469-474 (SF MCP native tool inventory) + 11 spec runtime references `mcp__sf__sf_*` verified via grep.

### Q-SF-MCP-PRE-PHASE-1-DECISIONS-01: v1.8 SF MCP Hybrid Integration — 8 Pre-Phase-1 operator decisions [P1] ✅ RESOLVED 2026-05-26
**→ RESOLVED 2026-05-26 Manager session bootstrap (operator approval "en iyi senaryo + cross-check + titiz"):** Süleyman'ın "hepsi default + 1 manager override (ADR-031→ADR-039)" kabulü ile 8 karar lock'landı. Tüm default'lar spec v2.2 "Open Questions for Operator Review" tablosundan; 1 Manager Decision spec drift catch'i (ADR-031 zaten archive'da alınmış, DECISIONS.md:42 events.jsonl Legacy Archive 2026-05-06; ADR-038 numbering policy renumber YASAK → next-unused ADR-039 lock'landı). Worker Prompts file edit edilmeyecek (forbidden, Workers may have been read it); ADR-039 override Manager-side, Phase 2 + Phase 6 dispatch'lerinde Worker prompt'a inline "Manager Override" note olarak verilecek (spec/worker-prompts file dokunulmaz, override conversational injection ile). v2.3 spec retrospective notu Phase 7 closeout'a deferred (post-ship retro item).

**Resolutions table:**
| # | Q | Default Applied | Lock'ladığı yer | Status |
|---|---|------------------|-----------------|--------|
| 1 | Q-SF-MCP-09 (registry instance konum) | `./mcp-tool-registry.json` (engine-wide repo root) | Phase 1 task #6 | ✅ |
| 2 | Q-SF-MCP-02 (requires_approval) | YES (orchestrator approval prompt) | Phase 3 SKILL frontmatter | ✅ |
| 3 | Q-SF-MCP-04 (Move vs Copy) | Move (atomic-friendly, D-SF-16 alignment) | Phase 3 file move logic | ✅ |
| 4 | Q-SF-MCP-05 (auto-invoke sf-import) | YES (full pipeline single command) | Phase 3 handoff step | ✅ |
| 5 | Q-SF-MCP-07 (consumer rollout) | All-4 in v1.8 (tech+schema+on-page+internal-links) | Phase 5 scope (1.5d effort) | ✅ |
| 6 | Q-SF-MCP-10 (Tier 3 in default loop) | NO (24 reports only — Tier 1 + Tier 2) | Phase 3 24-vs-40 enumeration | ✅ |
| 7 | Q-SF-MCP-11 (per_report_timeout_seconds) | 300 (5min × 24 = 2h export budget) | Phase 3 `sf_generate_report` timeout | ✅ |
| 8 | **Manager Decision: ADR override** | **ADR-031 → ADR-039** (cross-check: 031 taken by events.jsonl Legacy Archive 2026-05-06; archive grep ADR-039 0 hit → müsait) | Phase 2 + Phase 6 Worker prompt override notu | ✅ |

**Deferred (by-design, NOT decided in Pre-Phase-1; defaults apply for v1.8):**
- Q-SF-MCP-01 Node.js Runtime → OFF (security; embeddings deferred v1.1+)
- Q-SF-MCP-03 max_wait_minutes → 180 (3h; Q-SF-MCP-11 tuned together)
- Q-SF-MCP-06 Cross-project SF lock → DURUR-orch-7 (R13 v1 guard); full fcntl lock deferred v1.2+
- Q-SF-MCP-08 stop.json hook validate sf entry → **previously RESOLVED → NO** (perf budget; drift-check skill catches it instead)

**Raised:** 2026-05-26 Manager session bootstrap (operator initial v1.8 dispatch). Spec authority: `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` (v2.2, 937 lines, ~50KB) + companion `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md` (666 lines, 7 Worker Prompts).
**Context:** Spec v2.2 Open Questions table (lines 879-892) listed 11 Q-SF-MCP-XX questions with defaults. Worker Prompts file (lines 14-23) listed 7 Pre-Phase-1 decisions to lock before Phase 1 dispatch. Manager bootstrap cross-check'i 8'inci kararı surface etti: spec satır 69 + 421 + Worker Prompts satır 146 + 188 + 472 "ADR-031" cite ediyor ama mevcut DECISIONS_ARCHIVE.md zaten ADR-031 = events.jsonl Legacy Archive olarak kayıtlı (2026-05-06 commit). Spec drift catch: spec authoring time (2026-05-26) ile current repo state arasında ADR numerasyon collision. ADR-038 "monotonic-but-gap-tolerant + renumber FORBIDDEN" policy gereği next-unused ADR-039 lock'landı. Worker Prompts file edit forbidden (Manager bootstrap §Forbidden Actions: "Workers may have already read it") → Phase 2 + Phase 6 dispatch'lerinde Manager override notu inline injection.
**Cross-refs:** Spec v2.2 lines 879-892 (11 Q table) + Worker Prompts lines 14-23 (7 decision table) + DECISIONS.md:42 (ADR-031 archive entry) + ADR-038 numbering policy + Manager bootstrap §Pre-Phase-1 Operator Decisions.

---

### Q-SF-MCP-01..11: v1.8 SF MCP per-question audit trail (per spec §Open Questions for Operator Review) [P2-P3]
Each question per `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` lines 875-892 (v2.2 spec, 11 items). Resolution paterni: 7 defaults applied in Pre-Phase-1 (see Q-SF-MCP-PRE-PHASE-1-DECISIONS-01 above) + 4 deferred (Q-01/03/06/08); Q-08 separately marked RESOLVED below.

- **Q-SF-MCP-01** Node.js Runtime in SF settings → **OFF** (security; embeddings/cannibalization v1.1+ scope). DEFERRED to v1.1+ for ON case.
- **Q-SF-MCP-02** Orchestrator approval prompt → **YES** (`requires_approval=true` in `skills/ingestion/sf-crawl-orchestrator/SKILL.md` frontmatter, Phase 3). RESOLVED Pre-Phase-1.
- **Q-SF-MCP-03** Default max_wait_minutes for crawl polling → **180** (3h; default; Q-SF-MCP-11 tuned together). DEFERRED to v1.1+ for Bigcat-scale 30K+ URLs (360).
- **Q-SF-MCP-04** Move vs Copy strategy SF dir → project dir → **Move** (cleanup; matches D-SF-16 atomic semantics). RESOLVED Pre-Phase-1.
- **Q-SF-MCP-05** Auto-invoke sf-import after orchestrator → **YES** (full pipeline in one operator command). RESOLVED Pre-Phase-1.
- **Q-SF-MCP-06** Cross-project SF lock → **DURUR-orch-7** R13 sf_list_crawls guard for v1; per-project fcntl persists; global cross-project lock DEFERRED v1.2+.
- **Q-SF-MCP-07** Optional consumer skill rollout (tech/schema/on-page/internal-links) → **All-4 in v1.8** (Phase 5; `use_sf_mcp_live: bool = False` opt-in per skill). RESOLVED Pre-Phase-1.
- **Q-SF-MCP-08** stop.json hook validate sf entry in mcp-tool-registry → **RESOLVED → NO** (perf budget; stop_validation.py has <1s budget, `claude mcp list` costs ~200-500ms; drift-check skill F-23 catches it instead). ✅ RESOLVED (separately noted per Worker Prompt task).
- **Q-SF-MCP-09** Where does `mcp-tool-registry.json` instance live → **Repo root `./mcp-tool-registry.json`** (one engine-wide registry). RESOLVED Pre-Phase-1.
- **Q-SF-MCP-10** Tier 3 (16 optional reports) inclusion in default orchestrator loop → **NO** (24 reports only — Tier 1 + Tier 2; orchestrator `include_tier3=false` lock). RESOLVED Pre-Phase-1.
- **Q-SF-MCP-11** `per_report_timeout_seconds` default in `sf_generate_report` → **300** (5min/report; 24×5 = 2h export budget). RESOLVED Pre-Phase-1.

**Raised:** 2026-05-26 spec v2.2 authoring. **Resolved/Deferred breakdown:** 7 RESOLVED via Pre-Phase-1 defaults + 1 (Q-08) RESOLVED → NO previously + 3 DEFERRED v1.1-v1.2+ (Q-01/03/06).
**Cross-refs:** Spec lines 875-892 + Q-SF-MCP-PRE-PHASE-1-DECISIONS-01 above + D-SF-{02..18} decision records in spec §Decision Record (15 architectural decisions).

### Q-V1.4-AUDIT-CRITICAL-01: Deep audit 9 CRITICAL findings — rules/+schemas/+templates/ engine self-violation [P1] ✅ RESOLVED 2026-05-07
**→ RESOLVED 2026-05-07 v1.4-deep-audit-fix milestone (engine 14 atomic commit T1+T2+T3+T4 + closeout):** Option (a) applied — full milestone scope. **9/9 CRITICAL closed:** K-01 R-26 CTA Zorunlu definition + ADR-038 K-01 clarification (T2 Step 2 `07f317b`); K-02 14 schema $id HTTP/path/suffix mass-fix (T1 Step 2); K-03 master-excel.schema.json $id+title+definitions (T1 Step 3 `48553f5`); K-04 master_task col A taskIdPattern $ref (T1 Step 3 `48553f5`); K-05 events.primary_source enum sync 9→11 (T1 Step 4 `de1efb0`); K-06 11/26 reports run_id placeholder (T3 Step 1 `b20b58b`); K-07 7/26 reports `## Kanıt zinciri` H2 (T3 Step 1 `b20b58b`); K-08 (downgraded MEDIUM in audit, no separate fix); K-09 content-update-discipline.md broken URL (T2 Step 4 `5412827`). Plus T2 Step 1 `475bec4` rules-frontmatter.schema.json + 7 rule frontmatter normalize (H-A + K-09 alt-fix). pytest 825 → 949 PASS + 11 SKIP cumulative (+124 yeni test cumulative). .mcp.json 482B byte-byte korundu (F-16 28+ commit cumulative). DECISIONS.md 6112 → 6126B (cap 6144B intact, 18B headroom). plugin.json 1.3.0 unchanged (ADR-036 5-file sync intact). Brief premise revize 5x (Lesson 38 v2 24-28th cumulative catches: json round-trip drift T1, file structure varsayımı T1, R-25/R-27 yer iddiası T2, lesson counter line :31 → lesson 8 not 38 T2, F-19..F-24 numbering çakışma T4 → F-23..F-28 next available). Atomic phase paterni 49'uncu kanıt cumulative 53 phase consecutive convergent invariant intact.
**Raised:** 2026-05-07 manager session "rules/+schemas/+templates/ deep audit" (4 paralel general-purpose agent dispatch + manager runtime cross-check 10/78 finding doğrulandı, 2 finding düzeltildi). Audit artifact: `docs/audits/v1.4-rules-schemas-templates-2026-05-07.md`.
**Context:** Engine repo'nun rules (20 .md), schemas (20 .json), templates (5 content + 26 reports + 1 scrapling) dosyaları satır satır taranınca 9 CRITICAL finding ortaya çıktı (deduplicated, K-XX numbering): K-01 R-26 (CTA Zorunlu) referansı 5 yerde (4 templates + 1 rules prose) ama hiçbir `### R-26:` definition yok (content-rules-input.md SUPERSEDED → R-01..R-26 import iddiası vs gerçek migration eksik). K-02 14/19 schema `$id`'de HTTPS (ADR-012 + naming.md HTTP zorunlu kılıyor); 5 dosyada $id `/templates/` path (yanlış, dosyalar `schemas/`'da). K-03 master-excel.schema.json'da `$id` ve `title` field'ları HİÇ YOK (309 satır en büyük schema kendisini tanımlamıyor). K-04 master-excel `definitions/taskIdPattern` YOK + `master_task.task_id` pattern-siz, ama rules/master-task-id.md:30 schema'ya guarantee veriyor (broken cross-ref). K-05 `primary_source` enum drift events 9 vs master_task 11 (Q-V1.2-MASTER-TASK-PRIMARY-SOURCE-01 master tarafında resolve edildi ama events.schema sync skipped). K-06 11/27 report'ta `$run_id` placeholder yok (audit trail kırık, replay deterministik değil). K-07 7/27 report'ta `## Kanıt zinciri` H2 yok (manager runtime grep agent under-count'unu düzeltti — 3→7). K-08 budget-events.md frontmatter anomaly (`name`+`applies_to`+`spec_section` yok, `since`/`supersedes`/`related_rules` farklı şema). K-09 content-update-discipline.md:100 broken example URL (`https://example/` placeholder prod metinde). 3 sistemik pattern: (1) Schema-first half-implemented (engine kendi rule'unu enforce etmiyor; rules-frontmatter.schema.json yok), (2) Rules ↔ Templates asymmetric coupling (22/26 report rule referansı vermiyor), (3) Migration miss vs gap-tolerant policy çelişkisi (ADR-038 "missing definition" durumu için marker tanımlamamış).
**Options:**
- a) v1.4-deep-audit-fix milestone (T1+T2+T3+T4+CO ~9 atomic commit / ~9 gün calendar) per `docs/superpowers/plans/v1.4-deep-audit-fix-brief.md`. Tüm 9 K-XX + 12 H-XX tema + 6 governance test deploy. Concurrent Q-V1.4-BOOTSTRAP-PATHS-01 ile paralel mümkün (farklı dosya alanları). v1.4 milestone scope.
- b) Sadece T1 (Schema Integrity) + T2 (Rules Discipline) v1.4'te; T3+T4 v1.5'e defer. Engine self-violation 5 CRITICAL fix; template + governance test sonra. Daha hızlı ama K-06+K-07 audit trail breach açık kalır.
- c) Sadece K-02..K-05 (engine integrity, ADR-012 enforce) minimum viable; K-01+K-06..K-09 v1.5'e defer. 1 hafta scope. R-26 + audit trail open.
- d) Defer tümü v1.5+; v1.4 odak Q-V1.4-BOOTSTRAP-PATHS-01 + multi-project test only. Audit findings durable artifact'te beklesin. Risk: 9 CRITICAL kalıcılaşır.
**Owner:** karar verici agent (v1.4 milestone scope; brief acceptance pending Süleyman onay)
**Blocking Phase:** None for v1.3.x maintenance; v1.4 deep audit fix scope (atomic chain T1-T4 + closeout per brief).
**Cross-refs:** `docs/audits/v1.4-rules-schemas-templates-2026-05-07.md` (78 finding source-of-truth), `docs/superpowers/plans/v1.4-deep-audit-fix-brief.md` (action plan), Q-V1.4-AUDIT-HIGH-01 + Q-V1.4-AUDIT-GOVERNANCE-01 (companion bundle Q'ları), Q-V1.4-BOOTSTRAP-PATHS-01 (concurrent v1.4 scope), ADR-012 (HTTP $id authority), ADR-018 (additive bump), ADR-038 (R-XX gap-tolerant clarification needed K-01 ile).

### Q-V1.4-AUDIT-HIGH-01: Deep audit 12 HIGH theme — frontmatter+pattern+coupling drift [P1] ✅ RESOLVED 2026-05-07 (12/12 HIGH closed final v1.6-Phase-2)
**→ FULLY RESOLVED 2026-05-07 v1.6-Phase-2 (H-E final closure, 12/12 HIGH closed):** H-E (events.schema event_type schema-first override DSL — was DEFER v1.5) RESOLVED via Option A + X3 revize per brief premise revize cycle (Lesson 38 v2 #46-55 cumulative cross-check, 14'üncü brief premise revize cumulative cycle). **Resolution path:** (a) Option A pragmatik: enum 10→12 additive (2 active DSL workaround skill canonical: `skill_content_remediation` + `skill_whats_next`) — NOT brief'in iddia ettiği "16 skill" (runtime'da 43 SKILL.md total + 2 active DSL + 2 bilinçli semantic-correct kapsam dışı [`indexing-ping` F-8 sub-object compliance + `monitoring-weekly` audit kind]); (b) Option X3 schema_version bump iptal: const "1.0" UNCHANGED (`tests/schemas/test_events_schema_operation.py:31` "Wave 3 staging additive (ADR-018 paterni)" prior art — schema_version bump yapmadan additive enum extension; workspace events.jsonl runtime'da `schema_version="1.0"` yazılı, const "1.1" yapmak rules/append-only-state.md ihlal ederdi); (c) Tier 2 migration 0004 DROPPED (rules/append-only-state.md:55 saygi: "Migration-in-place YANLIŞ — geçmiş event'in semantiğini değiştirir + git history'de düzeltme diff görünür + replay/debug için orijinal yazım kaybolur. Doğru paterni: legacy archive partition"; ADR-031 prior art `scripts/state/migrate_legacy_events.py` mevcut; additive paterni gereği migration GEREKSIZ — eski entries 1.0 schema_version'da kalır, additive enum 1.1'de hala valid). **3 atomic commit cumulative v1.6-Phase-2:** Tier 1 `8a2484d` (events.schema event_type enum 10→12 + 11 yeni test + portfolio_kpi_trend.py:32 EVENT_TYPE_ENUM transform-side mirror sync + ADR-027 line count compact 600→599 + test rename 10→12) + Tier 2 DROPPED + Tier 3 `340c8d5` (5 file canonical event_type emission: scripts/meta/whats_next.py production code + 2 SKILL.md + tests/skills/test_whats_next.py + rules/events-writer.md Section 4a) + Tier 4 absorbed into Tier 5 + Tier 5 `15f0186` closeout. pytest **1096 → 1107 PASS + 10 SKIP** (+11 yeni test cumulative; regression sıfır). DURUR ✓ all (.mcp.json 482B byte-byte F-16 42+ commit cumulative + DECISIONS.md 6126B unchanged no new ADR ADR-018 paterni reuse + plugin.json 1.5.0 unchanged). **Patterns born:** Tier 2 DROP paterni (rules/append-only-state vs schema-versioning conflict resolution) + Option X3 paterni (schema_version bump iptali; operation enum staging Wave 3 prior art) + bilinçli semantic-correct paterni catch (refactor scope kontrolünde rationale check zorunlu). Atomic phase paterni 59 → 60'ıncı kanıt cumulative 64 phase consecutive convergent invariant intact. Lesson 38 v2 cumulative catches 45 → 55 (10 yeni v1.6-Phase-2 cycle, en kapsamlı tek phase cycle). Q-V1.4-AUDIT-HIGH-01 bundle scope artık tamamen kapalı (12/12 HIGH closed; was 11/12 with H-E DEFER lifted v1.6-Phase-2).
**→ RESOLVED 2026-05-07 v1.4-deep-audit-fix milestone (engine 14 atomic commit T1+T2+T3+T4 + closeout):** Option (b) applied — H-E (event_type enum bump 1.0→1.1 + migration script) DEFER v1.5; remaining 11 themes resolved. **11/12 HIGH closed:** H-A rules-frontmatter.schema.json + 20 rule normalize (T2 Step 1 `475bec4`); H-B project-memory + skill-frontmatter schema_version + portfolio-config const (T1 Step 5 `99b9d08`); H-C central pattern $ref consolidation events.schema (T1 Step 6 `29fe513`, 5 patterns extracted to definitions); H-D R-22/R-57 + R-50/R-115 dedupe per ADR-038 (T2 Step 3 `7d16651`); H-F reports source_rules + frontmatter policy (T3 Step 2 `efbfba6`, single-source-of-truth.md new section + 17 reports HTML comment block); H-G topical-map+internal-links audit trail (subset of K-06+K-07, closed via T3 Step 1 `b20b58b`); H-H profile/profiles cascade documentation (T3 Step 3 `b42a1b9`, content-quality.md Principle 2 + new-blog.template.md frontmatter); H-I glossary-discipline.md anchor #invariant (T2 Step 4 `5412827`); H-J skills.md lesson counter cleanup 3 yer (T2 Step 4 `5412827`); H-K skills.md ADR-022/026 cap-only chain (T2 Step 4 `5412827`); H-L events.schema legacy task_id oneOf bypass (T3 Step 4 `08f0787`, definitions/legacyTaskIdPattern). **DEFER:** H-E (events.schema event_type enum 16-skill workaround DSL deprecate + scripts/migrations/0004_events_1_0_to_1_1.py) — büyük scope, schema_version major bump (ADR-018 paterni), v1.5 milestone candidate.
**Raised:** 2026-05-07 manager session deep audit cross-cutting layer.
**Context:** 9 CRITICAL'in altında 12 HIGH tema (~30 alt-finding) bundle. H-A: Frontmatter convention 4 farklı pattern (status: enforced/Active mix, applied_to vs applies_to typo, rules-frontmatter.schema.json YOK). H-B: schema_version field 2 dosyada hiç yok (project-memory + skill-frontmatter); portfolio-config pattern (loose) — diğer 13 const; master-excel + cross-sheet-invariants instance/meta-schema mix. H-C: Pattern duplication (T-NNNN 3 yerde, sha256 5 yerde, kebab slug 6 yerde, pillar 2 yerde, workflow_run_id 2 yerde) — central $ref yok. H-D: R-22/R-57 + R-50/R-115 cross-rule duplicate (SSOT ihlali). H-E: events.schema event_type schema-first override DSL'i (16 skill `event_type=manual + note=[skill=X]` workaround — enum bump skipped). H-F: 22/26 reports source_rules + frontmatter yok, policy belgesiz. H-G: topical-map + internal-links audit trail eksik (K-06+K-07 alt-küme). H-H: project-config schema'da hem singular `profile` hem plural `profiles[]` (cascade dokümante edilmemiş). H-I: rules/glossary-discipline.md:8 `docs/GLOSSARY.md#invariant-check` anchor 404. H-J: rules/skills.md:11,31,99 "Lesson 38 v2 N'inci ardışık" rule body'sinde tutarsız (5/4/5) tarihçe — normatif değil. H-K: rules/skills.md:5 ADR-022 archive direkt referans (cap-only supersede ADR-026 chain açık değil). H-L: events.schema regex `^T-[0-9]{4,}$` legacy `MT-W3W2B-001` ID'leri reject — bypass yok.
**Options:**
- a) Tümü v1.4-deep-audit-fix milestone içinde (T1 H-B+H-C, T2 H-A+H-D+H-E+H-I+H-J+H-K, T3 H-F+H-G+H-H+H-L) per brief. ~6 atomic commit; T1+T2+T3 paralel mümkün.
- b) H-E (event_type enum bump 1.0 → 1.1 + migration script) v1.5'e defer (büyük scope, schema_version bump); kalan 11 tema v1.4. Daha az risk.
- c) Sadece H-A (rules-frontmatter.schema) + H-B (schema_version coverage) v1.4 — kalan 10 tema v1.5+. Minimum self-validation engine fix; SSOT ihlalleri açık kalır.
- d) Defer tümü; HIGH listesi v1.5 cumulative bundle.
**Owner:** karar verici agent (v1.4 milestone scope companion; brief T1+T2+T3 distribution)
**Blocking Phase:** Q-V1.4-AUDIT-CRITICAL-01 ile bundle scope; ayrı resolve mümkün ama paralel daha verimli.
**Cross-refs:** Audit artifact + brief (yukarıdaki Q-V1.4-AUDIT-CRITICAL-01 ile aynı), ADR-012/018/038, schema-versioning-discipline.md, single-source-of-truth.md.

### Q-V1.4-AUDIT-GOVERNANCE-01: Deep audit 6 missing regression test + drift-check expansion [P1] ✅ RESOLVED 2026-05-07
**→ RESOLVED 2026-05-07 v1.4-deep-audit-fix Tier 4 (engine 1 atomic commit `b35bc62`):** Option (a) applied — combined T4 commit. **All 6 regression tests deployed** (test_id_format T1 + test_version_field T1 + test_cross_schema_enums T1 + test_r_xx_resolution T2 + test_run_id_coverage T3 + test_frontmatter T2). **3 ek pass deployed in T4:** (i) tests/schemas/test_self_validate.py NEW — 20 schemas Draft7Validator.check_schema; (ii) tests/schemas/test_instance_validation.py NEW — events.jsonl line-by-line validate, @pytest.mark.skipif PSEO_WORKSPACE_ROOT (plugin agnostiklik intact); (iii) tests/hooks/test_hook_scripts_exist.py NEW — enumerate cited scripts/hooks/* in rules/, EXPECTED_DEFERRED set covers 4 missing scripts (yan-discovery raised as Q-V1.5-HOOK-SCRIPTS-MISSING-01). **drift-check skill F-23..F-28 expansion** (Engine Self-Governance subsection) — 6 invariants documented + cross-linked to test files. Brief premise revize: F-19..F-24 (brief original) çakışma — drift-check'te F-19..F-22 ZATEN MEVCUT (different invariants); ADR-038 paterni F-NN'ye uyarlanmış (renumber YASAK) → F-23..F-28 next available used. **Lesson 38 v2 28th cumulative catch.**
**Raised:** 2026-05-07 manager session deep audit T4 governance gap analysis.
**Context:** 9 CRITICAL + 12 HIGH'ın **çoğu otomatik test'le yakalanabilirdi** ama mevcut test suite hiçbiri için coverage vermiyor. 6 regression test eksik: (1) `test_id_format` ($id HTTP/path/suffix per ADR-012), (2) `test_version_field` (schema_version coverage const enforcement), (3) `test_cross_schema_enums` (events ⊆ master enum subset, drift detection), (4) `test_r_xx_resolution` (templates'de cited R-XX hepsinin definition'a sahip olması), (5) `test_run_id_coverage` (reports template'lerinde audit trail placeholder), (6) `test_rules_frontmatter` (rules-frontmatter.schema.json validation). Ek olarak 3 ek pass defer edildi: jsonschema runtime validate (her schema draft-07 meta-schema'ya valid mi), instance file validation (workspace events.jsonl/master.xlsx schema-conformant mı), scripts/hooks/ existence (8+ rule pre-commit hook iddia ediyor — script gerçekten var mı). drift-check skill 6 yeni invariant (F-19..F-24) entegre etmeli aksi halde aynı drift 3 ay sonra tekrarlanır.
**Options:**
- a) v1.4-deep-audit-fix Tier 4 (T4) içinde 6 regression test + jsonschema runtime + instance file validate + hook script existence + drift-check expansion. ~1 atomic commit, ~2 gün. T1-T3 ile paralel veya post-T3 sırası.
- b) Sadece 6 test (T4 minimal); jsonschema runtime + instance file v1.5'e defer. Hızlı governance lock.
- c) Test-first: T4'ü T1'den ÖNCE — yeni testler yaz, fail durumda T1-T3 fix'leri PASS yapsın. TDD purist; ama "broken-window" psikolojisi (test'ler kırmızı kaldığında disiplin bozulur).
- d) Defer T4 v1.5+; T1-T3 fix'leri kalıcılaşır ama regression koruması yok.
**Owner:** karar verici agent (v1.4 milestone Tier 4 scope; brief T4 detailed steps)
**Blocking Phase:** Q-V1.4-AUDIT-CRITICAL-01 + Q-V1.4-AUDIT-HIGH-01 ile bundle (T4 önceki tier'ların regression koruması olduğu için sıralama önemli).
**Cross-refs:** Audit artifact + brief (yukarıdaki 2 Q ile aynı), tests/ structure (mevcut test_versioning, test_schema_id_format eksik), drift-check skill (skills/governance/drift-check/SKILL.md), rules/schema-versioning-discipline.md.

### Q-V1.5-HOOK-SCRIPTS-MISSING-01: 4 cited scripts/hooks/* not authored — rules claim pre-commit hooks that do not exist [P2] ✅ RESOLVED 2026-05-07 (final 4-of-4 authored)
**→ RESOLVED final 2026-05-07 v1.6-Phase-1 Tier 1+2+3 (engine 3 atomic commits `d4e3f68` + `9c8f7e1` + closeout pending):** Option (a) extended on top of v1.4-cleanup-batch partial closure. Remaining 2 hook scripts authored + EXPECTED_DEFERRED set 2 → 0 (empty trip-wire preserved); rules/naming.md:43 and rules/schema-first.md:36 "Phase 13'te otomatize" qualifier retired (rule body now states the deployed enforcement directly). **Authored:** scripts/hooks/check_naming.py (slug & filename regex guard, 3 patterns: skills/<slug>/SKILL.md folder slug + commands/<filename>.md must match `pseo-<slug>.md` + schemas/<name>.schema.json filename slug AND $id format `http://platinum-seo-engine/schemas/<slug>` per ADR-012; 16 tests) + scripts/hooks/validate_before_write.py (schema-first paired-update guard, kod = scripts/state/+excel/+discovery/+planning/+validation/, schema reference grep `schemas/<slug>.schema.json`, --allow-kod-only escape hatch for non-shape refactors mirroring check_excel_writer.py --allow-direct-edit idiom; 14 tests). **Tests:** tests/hooks/test_check_naming.py NEW + tests/hooks/test_validate_before_write.py NEW + tests/hooks/test_hook_scripts_exist.py EXPECTED_DEFERRED = set() empty (forward trip-wire intact). pytest 1066 → 1096 PASS + 10 SKIP (+30 yeni test cumulative v1.6-Phase-1, regression sıfır). DURUR ✓ all (.mcp.json 482B byte-byte korundu F-16 39+ commit cumulative + DECISIONS.md 6126B unchanged + plugin.json 1.5.0 unchanged). Brief premise revize #14 (Lesson 38 v2 cumulative): brief Tier 3 step 1 ".claude/settings.json hook config registration" speculative — runtime authority pattern "rules cite + tests/hooks/test_hook_scripts_exist.py enforce existence" intact, yeni hook config dosyası açılmadı. Brief premise revize #15: brief Tier 3 step 2 "EXPECTED_DEFERRED → {} empty" tek seferlik update öneriyor, ama `test_expected_deferred_set_complete` self-enforcing — Tier 1 + Tier 2 her birinin commit'inde kendi entry removal eklendi (atomic commit + pytest non-regress symmetric).
**→ RESOLVED 2026-05-07 v1.4-cleanup-batch (engine 1 atomic commit `3f00902`):** Option (b) applied. **2 of 4 unqualified hook scripts authored** + comprehensive tests + EXPECTED_DEFERRED set 4→2. Remaining 2 ("Phase 13'te otomatize" qualifier-rules) preserved by-design — rule body authority stays accurate; v1.5+ session authors when Phase 13 timeline finalizes (no separate Q needed; rule body itself is the deferred authority). **Authored:** scripts/hooks/check_append_only.sh (jsonl non-append guard, 3 modes: --staged/--working-tree/--rev-range; bash 3.2 portable explicit while-read loop — Lesson 38 v2 30th catch macOS /bin/bash mapfile incompatibility) + scripts/hooks/check_excel_writer.py (master.xlsx writer policy guard, 3 writer signals: commit msg ref / PSEO_EXCEL_WRITER env / --allow-direct-edit override; subdir detection workspace/projects/{slug}/ paths). **Tests:** tests/hooks/test_check_append_only.py NEW (9 tests: executable presence + help/usage + 7 diff scenarios) + tests/hooks/test_check_excel_writer.py NEW (9 tests: executable presence + 8 scenarios incl. legacy basename + env signal + commit-msg signal + allow-direct-edit + subdir detection). **Deferred preserved:** check_naming.py (rules/naming.md:43 "Phase 13'te otomatize") + validate_before_write.py (rules/schema-first.md:36 "Phase 13'te otomatize"). pytest 952 → 970 PASS + 11 SKIP (+18 new test cumulative). DURUR ✓ all (.mcp.json 482B + DECISIONS 6126B + plugin 1.3.0).
**Raised:** 2026-05-07 v1.4-deep-audit-fix Tier 4 governance test discovery (engine HEAD `b35bc62`, `tests/hooks/test_hook_scripts_exist.py` NEW codification).
**Context:** 4 hook scripts cited in rules/*.md with "Pre-commit hook: `scripts/hooks/<file>`" pattern but **scripts/hooks/ contains only stop_validation.py + subagent_output_validate.py** — citations point to non-existent files. Cited scripts: (1) `check_append_only.sh` (rules/append-only-state.md:36, "jsonl dosyalarında non-append diff'i reddeder"); (2) `check_naming.py` (rules/naming.md:43, "Phase 13'te otomatize" — phase-deferred qualifier); (3) `check_excel_writer.py` (rules/excel-discipline.md:39, "`master-excel.xlsx` diff'i `transaction.py`'den gelmiyorsa reddeder"); (4) `validate_before_write.py` (rules/schema-first.md:36, "Phase 13'te otomatize" — phase-deferred qualifier). Two are explicitly "Phase 13'te otomatize" (deferred-by-design, current state ACCEPTED gap); two are unqualified gaps. Test instruments via EXPECTED_DEFERRED set — no CI break, but new citations for non-existent scripts will fail (drift-prevention). v1.5 milestone owns deferred authoring.
**Options:**
- a) Author all 4 hook scripts in v1.5 milestone — full pre-commit hook suite per rules claims. Each script + integration test + .pre-commit-config.yaml entry.
- b) Author 2 unqualified gaps (`check_append_only.sh` + `check_excel_writer.py`); leave 2 "Phase 13'te otomatize" as-is (deferred-by-design preserved).
- c) Soften rule claims: replace "Pre-commit hook: `scripts/hooks/<file>`" with "Future hook (Phase X): `scripts/hooks/<file>`" — accurate state, no script authoring needed. Engine self-discipline pure (rule says what is NOT YET).
- d) Defer indefinitely — current EXPECTED_DEFERRED set is sufficient guardrail; scripts authored opportunistically when phase scope allows.
**Owner:** karar verici agent (v1.5 milestone scope; deferred from v1.4 T4 — out of scope test-only tier).
**Blocking Phase:** None — v1.4 T4 test instruments the gap; production runtime unaffected (no rule actively enforces these hooks at runtime).
**Cross-refs:** `tests/hooks/test_hook_scripts_exist.py` (EXPECTED_DEFERRED set authority), `rules/append-only-state.md:36`, `rules/naming.md:43`, `rules/excel-discipline.md:39`, `rules/schema-first.md:36`, Q-V1.4-AUDIT-GOVERNANCE-01 (parent test-discovery context).

### Q-V1.4-BOOTSTRAP-DEFAULT-OUT-01: bootstrap_project.py default --out path PSEO_WORKSPACE_ROOT-aware değil [P3] ✅ RESOLVED 2026-05-07
**→ RESOLVED 2026-05-07 v1.4-cleanup-batch (engine 1 atomic commit `baecb91`):** Option (a) applied — `main()` output path mantığı PSEO_WORKSPACE_ROOT-aware yapıldı. 4-step chain: (1) `args.out` explicit > (2) `PSEO_PROJECTS_DIR` env override > (3) `PSEO_WORKSPACE_ROOT/projects` default. PSEO_WORKSPACE_ROOT zaten `build_project_config()`'de REQUIRED (sys.exit(2) if missing); `main()` artık aynı env'i output path için de kullanıyor. F-16 invariant strict, init-project SKILL §Step 4 paterni intact (--out explicit override mevcut, hiçbir regression yok). **Brief premise revision (Lesson 38 v2 29th catch):** İlk test tasarımı `cwd=tmp_path` + `PSEO_WORKSPACE_ROOT=tmp_path` aynı dizine settled, cwd-relative pollution PSEO_WORKSPACE_ROOT/projects'e denk geldi → tautological PASS verdi. Düzeltme: cwd ≠ PSEO_WORKSPACE_ROOT (separate tmp_path/engine_cwd vs tmp_path/workspace) → bug TDD red kanıtlandı, fix uygulandı, TDD green doğrulandı. **3 yeni regression test:** test_default_out_uses_workspace_root_when_no_projects_dir_env (cwd-relative pollution explicit not-exists assertion) + test_pseo_projects_dir_env_takes_precedence (explicit env override invariant) + test_explicit_out_takes_precedence (init-project SKILL §Step 4 paterni intact). pytest 949 → 952 PASS + 11 SKIP (+3 new). DURUR ✓ all.
**Raised:** 2026-05-07 v1.4-bootstrap-paths-fix Tier 3 runtime smoke discovery (engine HEAD `658a29e` post-Tier-1 fix).
**Context:** Tier 1 fix `build_project_config()`'de `workspace_root` env-required yaptı, ama `main()` output path mantığı (line 168-172) `PSEO_WORKSPACE_ROOT`'u dikkate almıyor: `--out` flag yoksa `PSEO_PROJECTS_DIR` env veya cwd-relative `./projects/{slug}/project.config.json` yazıyor. Komut engine repo'da çalıştırılırsa engine repo'ya pollution oluşur (Tier 3 smoke ilk denemede gerçek pollution yarattı, manuel cleanup gerekti). `init-project` SKILL.md §Step 4 paterni `--out {workspace_root}/projects/{slug}/project.config.json` explicit kullanıyor, o yüzden production runtime'da sorun yok — ama CLI direct kullanıcı (manuel `python3 scripts/state/bootstrap_project.py --project foo`) trap'e düşer.
**Options:**
- a) `main()` output path mantığını `PSEO_WORKSPACE_ROOT`-aware yap: `--out` yoksa default `{PSEO_WORKSPACE_ROOT}/projects/{slug}/project.config.json`. F-16 invariant strict + minimum surprise. Backward break: cwd-relative paterni eski script-runner'lar için.
- b) `--out` zorunlu yap (`required=True`): hiçbir default output path yok. Net + explicit ama CLI ergonomi düşer; init-project SKILL.md §Step 4 zaten `--out` veriyor (uyumlu).
- c) Defer — production runtime'da sorun yok (init-project paterni doğru); CLI direct kullanıcı için README/INSTALL banner uyarı yeterli. Düşük öncelik.
**Owner:** karar verici agent (v1.4 milestone scope; minor follow-up to Q-V1.4-BOOTSTRAP-PATHS-01).
**Blocking Phase:** None — production runtime safe (init-project SKILL.md §Step 4 paterni explicit `--out` injection); v1.4 cleanup batch candidate.
**Cross-refs:** `scripts/state/bootstrap_project.py` line 168-172 (`main()` output path logic); `skills/meta/init-project/SKILL.md` §Step 4 line 134-148 (subprocess CLI invoke contract); Q-V1.4-BOOTSTRAP-PATHS-01 (parent fix).

### Q-V1.4-BOOTSTRAP-PATHS-01: bootstrap_project.py legacy path defaults vs workspace reality [P1] ✅ RESOLVED 2026-05-07
**→ RESOLVED 2026-05-07 v1.4-bootstrap-paths-fix Tier 1+2+3+closeout (engine 4 atomic commit `658a29e` + `6a42fb1` + `d6ad192` + closeout):** Option a applied. `bootstrap_project.py` `build_project_config()` 7 path default LEGACY → MODERN convention sync (`excel_filename` master.xlsx + `sf_exports_dir` inbox/sf + `staging_dir` _state/cache + `reports_dir` outputs/reports + `blog_dir` outputs/content/drafts + `backups_dir` _state/backups + `workspace_root` PSEO_WORKSPACE_ROOT env REQUIRED — engine repo path fallback eliminate, F-16 invariant strict). Tier 1 fix ek: `tests/scripts/test_bootstrap_project.py::test_dry_run_emits_valid_json` env-aware subprocess invocation update + new `test_missing_workspace_root_env_fails` exit 2 contract lock. Tier 2: 11 yeni in-process unit test path regression-lock (subprocess-free, schema-first paterni reuse). Tier 3: 5 yeni e2e smoke test (subprocess + tmp_path filesystem cycle, init-project §Step 4 paterni; eykom rerun obsolete kanıt mismatch=0/7 vs canonical config). pytest 743 → 760 PASS + 9 skip (+17 yeni test cumulative positive drift). .mcp.json 482B byte-byte korundu (F-16 28+ commit cumulative). DECISIONS.md 6112B unchanged (no new ADR — ADR-009 + ADR-021 + ADR-035 paterni reuse). plugin.json 1.3.0 unchanged (ADR-036 5-file sync invariant intact, script-only edit). Brief premise revize: `tests/scripts/` (gerçek path) vs `tests/state/` (Q metni hatalı path) + EXTEND mevcut dosya (NEW dosya iddiası invalidate) — **Lesson 38 v2 23'üncü ardışık vaka** brief authoring `da166c8` runtime grep double-layer atlamış meta-irony catch. Yan-discovery: `Q-V1.4-BOOTSTRAP-DEFAULT-OUT-01` raised (P3, Tier 3 smoke runtime catch — bootstrap default `--out` path PSEO_WORKSPACE_ROOT-aware değil; init-project SKILL §Step 4 explicit `--out` ile bypass).
**Raised:** 2026-05-07 during eykom project onboarding (`/pseo-init` invocation, 2'inci proje portfolio'ya eklenirken keşif).
**Context:** `scripts/state/bootstrap_project.py` `build_project_config()` 7 path field'ı için LEGACY hardcoded default'lar üretiyor: `workspace_root=~/Documents/platinum-seo-engine/projects/{slug}` (engine repo path, workspace değil), `excel_filename={slug}_MASTER.xlsx` (uppercase legacy), `sf_exports_dir=sf-exports`, `staging_dir=staging`, `reports_dir=reports`, `blog_dir=blog`, `backups_dir=_backups`. Pilot proje `dentnotion`'ın gerçek workspace yapısı MODERN convention kullanıyor: `master.xlsx` (lowercase, F1 workbook policy), `inbox/sf`, `_state/cache`, `outputs/reports`, `outputs/content/drafts`, `_state/backups`. Phase 6+ ingestion skill'leri (sf-import, gsc-pull, dfs-pull, quick-wins, content-decay) modern path'leri OKUYOR — legacy default'lar üretip workspace'e yazmak skill chain'leri kıracak. Eykom için workaround: `bootstrap_project.py` dry-run + post-process patch (paths field manuel override) → schema-valid modern config üretildi. Schema (`project-config.schema.json` v1.3) sadece field'ların var olmasını zorunlu kılıyor, *değerleri* validate etmiyor → drift schema'da yakalanmıyor. `init-project` skill (SKILL.md §Step 4) bootstrap'ı subprocess ile çağırıyor ama post-process YOK; skill rerun'larında her seferinde legacy default'lar yeniden üretilir.
**Options:**
- a) `bootstrap_project.py` `build_project_config()` 7 path default'ını modern convention'a güncelle (`workspace_root` env var resolve + lowercase `master.xlsx` + `inbox/sf` + `_state/cache` + `outputs/reports` + `outputs/content/drafts` + `_state/backups`). Engine repo değişikliği, `tests/state/test_bootstrap_project.py` mevcut path assertion'ları güncellenmeli. v1.4 milestone scope.
- b) `init-project` SKILL.md §Step 4'e post-process patch step ekle: bootstrap output'unu read-modify-write ile path field'larını modern convention'a çevir. Bootstrap script intact kalır, drift skill seviyesinde absorbe edilir. Daha az regresyon yüzeyi ama legacy script'in kullanımı stale kalır.
- c) Schema v1.4 forward migration ile `paths.*` field'larına `pattern`/`enum` constraint ekle (örn. `excel_filename`: `^master\\.xlsx$`, `sf_exports_dir`: `^inbox/sf$`). Drift validate-time'da yakalanır, runtime'da hata vermek yerine. Ama esnekliği kaybeder (özel projects path override edemez).
- d) Defer + döküman ekle: `init-project` skill body'sinde "bootstrap legacy path default'larını manuel override et" step ekle. Audit-only fix, kalıcı drift kaynağı süreklilik kazandırılmış olur.
**Owner:** karar verici agent (v1.4 feature backlog scope; engine repo bootstrap_project.py fix-it).
**Blocking Phase:** None for v1.3.x maintenance (eykom workaround tested, dentnotion intact); v1.4 milestone scope (bootstrap modernize + path convention codify).
**Cross-refs:** Eykom workaround atomic kanıt (workflow `eykom-2026-05-07-8c5b`, master.xlsx SHA-256 `f18fc6f6ffde3387b9349441bbff3d6301a0d6b9a6d03af7c383ddf40bc9f3f6`); skills/meta/init-project/SKILL.md §Step 4 (subprocess CLI invoke); schemas/project-config.schema.json v1.3 (paths field schema); rules/single-source-of-truth.md (workspace path convention authority).

### Q-V1.2-LOAD-CONTEXT-ORPHAN-DIR-01: skills/meta/load-context/ orphan empty directory [P1] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 audit-followup Phase A:** Option a applied. `git rm skills/meta/load-context/.gitkeep` + `rmdir skills/meta/load-context`. design.md §11.1 updated (load-context moved Meta→Governance category in spec; Q-V1.2-DESIGN-CATEGORY-DRIFT P2 inline resolved batch). Trivial cleanup batch ~30 dk Phase A (4 audit findings). Verified `ls skills/meta/` returns 4 dirs (brand-onboarding + init-project + mark-done + whats-next); Meta(5)→Meta(4) consistent with reality.
**Raised:** 2026-05-06 during v1.1 Integration Audit Wave 1 (filesystem inventory cross-check).
**Context:** `skills/meta/load-context/` directory exists on disk but contains NO `SKILL.md`. The actual load-context skill lives at `skills/governance/load-context/SKILL.md` (correct location post-Phase 13+ governance refactor). The orphan empty `meta/load-context/` is residual from category move that never deleted the source directory. Empty dir doesn't affect runtime (Claude Code skill loader skips dirs without SKILL.md silently) but creates governance drift + design.md §11.1 docs ambiguity.
**Options:**
- a) Delete empty `skills/meta/load-context/` directory + update `docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md` §11.1 to reflect governance-category placement (combined with Q-V1.2-DESIGN-CATEGORY-DRIFT inline P2 finding)
- b) Move skill back from governance/ to meta/ (semantic argument: load-context is a META operation per spec §11.1 "Meta(5)" original intent)
- c) Defer indefinitely; orphan empty dir harmless (audit-only finding, not blocking)
**Owner:** karar verici agent (v1.2 doc-pass cleanup batch)
**Blocking Phase:** None for v1.1.0 (no runtime impact); v1.2 cleanup candidate.

### Q-V1.2-AIO-COMPETITOR-FENCE-01: aio-competitor-map block 2 AST FAIL bare identifier [P1] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 audit-followup Phase A:** Option a applied. ` ```python ` fence changed to ` ```text ` for the pseudocode-bearing block (skills/discovery/aio-competitor-map/SKILL.md:166). Block content preserved verbatim (5xx_marker bare identifier remains as documentation placeholder). Comment block prepended explaining fence rationale (Q-PHASE15-AIO-COMPETITOR-01 + Q-V1.2-AIO-COMPETITOR-FENCE-01 cross-reference). Verified post-fix: 5 `python` blocks (was 6 — 1 moved to `text`), all 5 AST PASS. `python3 scripts/ci/run_skill_python.py skills/discovery/aio-competitor-map/SKILL.md` exits 0 — helper exec strict mode now safe.
**Raised:** 2026-05-06 during v1.1 Integration Audit Wave 1 (Python AST parse) + Wave 4 (executability scorecard re-confirm).
**Context:** `skills/discovery/aio-competitor-map/SKILL.md` block 2 line 9 contains pseudocode `"status": 5xx_marker` where `5xx_marker` is a bare identifier (Python 3 SyntaxError: identifier cannot start with digit, "invalid decimal literal"). Skill body has `# llm_native: true` (Q-PHASE15-AIO-COMPETITOR-01 codified) so executability is intentionally not required, but ` ```python ` fence sets that expectation for `scripts/ci/run_skill_python.py` helper. AST parse fails on this pseudocode block.
**Options:**
- a) Change ```python fence to ```text or ```pseudocode for block 2 only — preserves doc readability + signals non-executable nature to AST tooling.
- b) Replace `5xx_marker` with `"5xx_marker"` (quoted string literal) — keeps fence consistent, makes block AST-valid pseudocode that won't actually run (no MCP, no real loop body).
- c) Refactor block 2 to skip pseudocode entirely — replace with a markdown narrative paragraph describing the tier-1 fetch fallback intent.
- d) Defer — keep `wip` status + skip CI strict mode for `wip` skills (currently the case).
**Owner:** karar verici agent (v1.2 SKILL.md polish batch + lint convention review)
**Blocking Phase:** None for v1.1.0 (skill `wip` status, helper exec not enforced strict for wip).

### Q-V1.2-EVENTS-WRITER-MATRIX-COVERAGE-01: rules/events-writer.md Section 4 branch matrix %47 coverage [P1] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 audit-followup Phase B Wave 2 (engine commit `64c7177`):** Option b applied. Section 4 monolithic 22-row matrix → 3 sub-table per `event_kind` (4a work + 4b provenance + 4c audit-only). Coverage 47% (20/43 brief-true) → 100% (43/43 filesystem-true). Filesystem SoT cross-check Lesson 67 enforcement: brief tahmini önemli ölçüde yanlış (`on-page-audit + tech-audit + schema-audit + 11 başka skill` aslında `append_provenance` çağırıyor → 4b kapsamı). Coverage audit summary table 26 active + 17 future status breakdown codified. JSON examples schema-aware envelope (timestamp + project_id + task_id mandatory) revize edildi.
**Raised:** 2026-05-06 during v1.1 Integration Audit Wave 3 (Hipotez 8 verification).
**Context:** `rules/events-writer.md` Section 4 contains a 22-row skill→event_type branch matrix (23 rows including content-remediation 3 sub-rows + mark-done 2 sub-rows). Of these, **20 unique skill names** match actual filesystem skill names. Coverage = 20/43 = **47%**. 23 skills are NOT explicitly mapped to event_type branch logic in the rule body. Skills missing from matrix: aio-competitor-map, brand-onboarding, cannibalization, content-decay, dfs-pull, drift-check, glossary-audit, gsc-pull, indexing-ping, init-project, load-context, monthly-report, portfolio-* (6 skills), quick-wins, scrapling-ops, sf-import, weekly-summary, whats-next. Some are `event_kind=audit` (skip event_type per Section 6 ADR-020 disambiguation), others are `event_kind=provenance` (per Section 4 schema). Worker schema-first override paterni (F-14W3W2B-1 doğum belgesi) handles unmapped skills via `event_type=manual + note=[skill=X event_type_intent=...]` but explicit row missing forces brief writer to figure out branch matrix on-the-fly per dispatch.
**Options:**
- a) Extend Section 4 to 43-row coverage (1 row per skill) — single matrix table, more rows but exhaustive.
- b) Restructure Section 4 with 3 sub-tables: Section 4a (work events 22-row), Section 4b (provenance events ~10-row), Section 4c (audit-only events ~5-row, no event_type column) — more discoverable than monolithic 43-row table.
- c) Defer + codify the schema-first override pattern as the "default for unmapped skills" rule explicitly — keeps rule body short, documents the override paterni as canonical.
**Owner:** karar verici agent (v1.2 governance refinement scope; rules/events-writer.md edit + schema cross-ref)
**Blocking Phase:** None for v1.1.0 (worker override handles missing rows); v1.2 dispatch ergonomics.

### Q-V1.2-SCHEMA-VALIDATE-MISSING-RULE-01: governance/schema-validate cites missing rules/foundational-principles.md [P1] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 audit-followup Phase B Wave 1 (engine commit `b1c64dc`):** Option b applied. Broken cite `rules/foundational-principles.md` (file YOK) → 3-rule authority chain (`rules/schema-first.md` + `rules/single-source-of-truth.md` + `rules/append-only-state.md`) + `rules/content-quality.md` convergence note. Helper exec EXIT 0; `grep "foundational-principles" skills/governance/schema-validate/SKILL.md` → 0 hit (was 1).
**Raised:** 2026-05-06 during v1.1 Integration Audit Wave 4 (executability scorecard refs existence check).
**Context:** `skills/governance/schema-validate/SKILL.md` body cites `rules/foundational-principles.md` but the file does NOT exist in `rules/` (current 20 rules: append-only-state, budget-events, ci-rule3, content-html-discipline, content-quality, content-seo-discipline, env-vars, events-writer, excel-discipline, glossary-discipline, master-task-id, naming, schema-first, schema-versioning-discipline, secrets-management, single-source-of-truth, skill-description-discipline, skills, time-discipline + 1 more). Likely candidates the cite was meant to point to: `rules/schema-first.md` (schema authority), `rules/single-source-of-truth.md` (foundational consolidation principle), or a planned-but-never-authored rule.
**Options:**
- a) Author `rules/foundational-principles.md` — codify the foundational invariants currently scattered across schema-first + single-source-of-truth + append-only-state into one cross-reference rule. Net new rule body, brief-writer effort.
- b) Replace cite in skill body with existing rule reference (likely `schema-first.md` semantically closest match) — single-line edit, low effort.
- c) Delete cite — if cite was an early Phase 13 placeholder that was never materialized.
**Owner:** karar verici agent (v1.2 ref-integrity sweep batch)
**Blocking Phase:** None for v1.1.0 (broken markdown link harmless at runtime); v1.2 doc-pass.

### Q-V1.2-MONITORING-WEEKLY-MISSING-SCRIPT-01: reporting/monitoring-weekly cites missing scripts/reporting/monitoring_weekly.py [P1] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 audit-followup Phase B Wave 3 (engine commit `6ba6aaa`):** Option b applied (skill body inline transform, no `scripts/reporting/monitoring_weekly.py` subprocess). 3 Python block sequential helper-exec compatible: Block 1 (setup + drift-check `consistency-report.json` read DURUR #3 fallback), Block 2 (`shared/portfolio.json` + per-project metrics + severity compute), Block 3 (markdown render via templates DURUR #4 inline fallback + `events_writer.append_audit` emit). Plugin agnostik: PSEO_PROJECT_ID env required, no slug literal (16/16 tests PASS). Helper exec EXIT 0; markdown sample `workspace/projects/dentnotion/outputs/reports/2026-05-06-monitoring-weekly.md` (1747 bytes); events.jsonl audit-row appended (event_kind=audit, no event_type per Section 6 disambiguation, schema_version+event_id+timestamp+project_id auto-populate via `append_audit` convenience wrapper). Wave 2 events-writer.md Section 4c ilk active row promoted (drift-check Phase 5 doğum belgesi paterni reuse).
**Raised:** 2026-05-06 during v1.1 Integration Audit Wave 4 (executability scorecard refs existence check).
**Context:** `skills/reporting/monitoring-weekly/SKILL.md` body cites `scripts/reporting/monitoring_weekly.py` but `ls scripts/reporting/` reveals: monthly_report.py, portfolio_heatmap.py, portfolio_kpi_trend.py, portfolio_monthly_roundup.py, portfolio_overview.py, portfolio_task_heatmap.py, portfolio_weekly_brief.py, weekly_summary.py — NO `monitoring_weekly.py`. monitoring-weekly is a Phase 12 weekly-cron skill (event_kind=audit per rules/events-writer.md Section 6) intended for cross-project drift monitoring + KPI trend snapshot. If skill body invokes `subprocess(['python3', 'scripts/reporting/monitoring_weekly.py', ...])` at runtime, FileNotFoundError.
**Options:**
- a) Author `scripts/reporting/monitoring_weekly.py` with the audit-orchestration logic (calls drift-check + reads portfolio-overview state + emits audit-kind event). Net new script ~150-300 lines, similar size to monthly_report.py.
- b) Skill body executes inline transform without subprocess — read drift-check output + portfolio.json + emit event directly in inline Python block. Lighter weight, fits "thin orchestration" paterni.
- c) Delegate to existing portfolio-overview + weekly-summary skills via skill-chain pattern — monitoring-weekly becomes thin meta-skill that calls others. Most consistent with current weekly-summary architecture.
**Owner:** karar verici agent (v1.2 missing-script materialization batch)
**Blocking Phase:** None for v1.1.0 (monitoring-weekly skill body is `wip` status, broken subprocess masked); v1.2 implementation.

### Q-V1.2-MASTER-TASK-PRIMARY-SOURCE-01: master_task.primary_source enum missing `new_content_plan` [HIGH] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 v1.2 Phase B post-closeout (engine commit `d94ae9c`):** Option a applied (Q-IL-1 paterni reuse — additive bump only, schema_version unchanged per ADR-018 convention; doc note path chosen over ADR aday for DECISIONS.md cap-safe 6027/6144B headroom). 2 dosya: `schemas/master-excel.schema.json` line 279 master_task.primary_source.enum 10→11 (+`new_content_plan` + `_note` inline citing Q-IL-1 cross-ref) + `scripts/planning/master_task_sync.py` PRIMARY_SOURCE_ENUM frozenset 10→11 sync (W-D1 transform tetikleyici docstring extended). pytest 673 passed + 3 skipped (no regression); test_master_task_sync_primary_source_enum_compliance PASS. Workspace runtime kanıt cross-check (Lesson 67 enforcement, 2'inci ardışık vaka): T-10001 zaten manuel/başka session tarafından `primary_source="pillar"` (semantically doğru — NCP-001 P1 pillar content) + `priority="HIGH"` normalize edilmiş; F-17 master_task priority enum 4/4 PASS runtime confirmed (priority values: ['HIGH', 'LOW', 'MEDIUM'] — severityEnum subset). Workspace mutation gerekli DEĞİL — schema bump backward-compat additive (gelecek durumlar için kapı açık). Drift-check verdict AMBER → AMBER (F-17 PASS, F-16 36-URL kalan Q-V1.2-OPP-COVERAGE-01 separate scope).
**Raised:** 2026-05-06 during v1.1-FIX-WAVE-3 Task 3.4 apply (transaction.update RowSchemaError surface).
**Context:** F-17 priority normalize blocked on T-10001 (`P1` → `HIGH`) because the row carries `primary_source = "new_content_plan"`, which is not in the schema enum: `[content_decay, quickwin, tech_fix, schema, pillar, manual, sxo, cannibalization, redirect_404, internal_links]`. Phase 8 W-D1 added `internal_links` (Q-IL-1 enum 9→10 bump) but `new_content_plan` from the Phase 8 `new-content-plan` skill was never added. The skill is active (`skills/planning/new-content-plan/SKILL.md`) and writes to `master_task` legitimately, so this is a schema enum gap not a workspace data error.
**Options:**
- a) Schema additive bump 10→11: append `"new_content_plan"` to `master_task.required_columns.primary_source.enum` (Q-IL-1 paterni reuse, additive only). Workspace re-validate trivially passes. ADR aday or doc note.
- b) Workspace data fix: rewrite T-10001.primary_source to a valid enum value (e.g., `manual` or `quickwin`) and proceed with F-17 normalize. Loss of semantic provenance.
- c) Defer T-10001 priority normalize indefinitely; document partial-PASS for F-17 (3/4 cells). Drift-check stays AMBER on F-17 forever.
**Owner:** karar verici agent (v1.2 schema audit OR engine release)
**Blocking Phase:** None for v1.1.0 (T-10001 P1 acceptable as documented partial); v1.2 candidate for resolution.

### Q-V1.2-OPP-COVERAGE-01: F-16 quick_wins URL coverage in opportunity sheet [HIGH] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 v1.2 Phase B post-closeout (engine commit `22cba80`):** Brief "SEO domain knowledge gerek" iddiası invalidate edildi (Lesson 38 v2 12'inci ardışık enforcement + Lesson 67 stacked 3'üncü ardışık vaka Phase B post-closeout). Runtime kanıt cross-check: 36 URL aslında opportunity sheet'te MEVCUT (regex URL extract sonrası); F-16 implementation false FAIL veriyordu. Root cause: `assigned_url_action.split("|", 1)[0]` paterni Phase 8 quickwins_transform.py canonical "url | action" format için doğruydu, ama workspace gerçek data freeform format kullanıyor: `"Optimize https://... for query 'X'"` (manuel/non-canonical drift). Schema-first override paterni 17'inci uygulama doğum belgesi: defensive parsing helper `_extract_url_from_action_field()` 2 format destekler — önce canonical (split + URL prefix validate), fallback regex `r'https?://[^\s\'"|]+'` (freeform). 2 dosya: scripts/validation/validate_invariants.py (~14 satır helper + 3 satır check_F_16 refactor) + tests/scripts/test_validate_invariants_F16.py NEW (8 test: 5 unit helper + 3 integration F-16). pytest 673 → 681 passed + 3 skipped (+8 yeni test, no regression). Direct check_F_16 verify workspace dentnotion master.xlsx: verdict **PASS** (was FAIL), evidence "all 36 quick_wins URLs covered by opportunity". test_drift_check.py 11/11 PASS unchanged (legacy fixture korunuyor — backward-compat). Genuine orphan still detected (defensive parsing real drift'i mask etmiyor — test_F16_genuine_orphan_still_fails kanıt). Drift-check verdict AMBER → expected GREEN candidate (F-16 PASS + F-17 PASS sonrası AMBER kalan F-13 historical 5 satır append-only protected baseline carry only).
**Raised:** 2026-05-06 during v1.1-FIX-WAVE-3 Task 3.4 (Q-WAVE2-DATA-HYGIENE-01 split-out).
**Context:** Validator-true F-16 finding: 36 `quick_wins.url` values are not present in `opportunity.assigned_url_action` URL set. The opportunity sheet has 211 distinct URLs but they are a disjoint set from the 36 quick_wins URLs — opportunity is keyed on `(query, opportunity_score, ..., assigned_url_action)` so each row encodes a search query + the URL recommended to optimize for it. Adding 36 placeholder rows would require generating realistic `query`/`opportunity_score`/`current_position` values per URL — that is **SEO domain knowledge**, not a mechanical script. Code-driven hygiene cannot resolve without data engineering input.
**Options:**
- a) Re-run `quick-wins` skill against current GSC data — opportunity sheet should populate naturally if the underlying ingestion produced the same URL set
- b) Run a scoped DataForSEO `keyword_overview` for each of the 36 URLs to back-fill query + score columns, then append to opportunity via `transaction.append`
- c) Accept divergence as by-design; relax F-16 invariant in `cross-sheet-invariants.json` with a documented exception (similar to Phase 16 Q-W3W2C-A-F13F16-01 pattern)
- d) Manual SEO triage by Süleyman (which queries map to which URLs?) → CSV → ingest via `transaction.append`
**Owner:** karar verici agent (v1.2 SEO data engineering scope)
**Blocking Phase:** None (drift-check AMBER acceptable for v1.1; Q-WAVE2-DATA-HYGIENE-01 supersede candidate after v1.2 closure)

### Q-WAVE2-DATA-HYGIENE-01: F-16 quick_wins URL coverage + F-17 severity cells [MEDIUM] ✅ PARTIAL RESOLVED 2026-05-06
**→ PARTIAL RESOLVED 2026-05-06 v1.1-FIX-WAVE-3 Task 3.4 (engine ADR-037 + workspace data fix):** F-17 PARTIAL via `scripts/maintenance/data_hygiene_master_xlsx.py` priority code mapping (P1→HIGH, P2→MEDIUM, P3→LOW per severityEnum 4-value canonical) — **3/4 cells normalized** via `transaction.update` (T-10002/10003/10004 P2→MEDIUM applied; T-10001 P1→HIGH blocked by row-level RowSchemaError on `primary_source="new_content_plan"` enum gap). Post-apply F-17 = 1/174 (was 4/174). Audit trail at `outputs/reports/2026-05-06-data-hygiene-master-apply.md`. F-16 36-URL coverage SPLIT OUT to **Q-V1.2-OPP-COVERAGE-01 [HIGH]**. T-10001 deferral SPLIT OUT to **Q-V1.2-MASTER-TASK-PRIMARY-SOURCE-01 [HIGH]** (schema enum gap discovery). Validator-true counts (`_resolve_header_row` Phase 14 W3-W2-C-a authority): F-16=36 + F-17=4 (matches Wave 2 brief). Header echo defense regression-locked via `tests/scripts/test_header_echo_defense.py`.
**Raised:** 2026-05-06 during v1.1-FIX-WAVE-2 P1 closeout (drift-check post Task 2.5 F-19 fix re-run).
**Context:** Wave 2 closure transitioned drift-check verdict RED → AMBER. F-13 + F-19 PASS now (Wave 1 archive + Wave 2 validator fix). Remaining 2 FAILs are workspace data hygiene:
- F-16: 36 quick_wins URLs not present in opportunity sheet (URL set divergence; Phase 15 Q-W3W2C-A-F13F16-01 followup, Phase 16 by-design exception flag option d previously accepted but Wave 3 may sync)
- F-17: 4/174 severity cells outside {LOW,MEDIUM,HIGH,CRITICAL} 4-enum (cell-level data correction needed)
Both are workspace-side data tasks, not engine code drift. Wave 3 scope after v1.2 P3 backlog clarification.
**Options:**
- a) Wave 3 dedicated data hygiene sprint (workspace edits + drift-check verify)
- b) Phase 16 layout normalize ADR with F-16 by-design exception (Q-W3W2C-A-F13F16-01 paterni reuse)
- c) Defer indefinitely (drift-check AMBER acceptable for v1.x lifecycle)
**Owner:** karar verici agent (Wave 3 plan or v1.2 milestone close)
**Blocking Phase:** None (AMBER verdict acceptable; data hygiene non-blocking)

### Q-WAVE2-DFS-OP-STAGING-01: dfs-pull SKILL.md operation="staging" outside enum [LOW] ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 v1.1-FIX-WAVE-3 Task 3.5 (engine schema additive bump):** Option b accepted. `events.schema.json` operation enum bumped 5→6 values: `[ingest, normalize, project_excel, validate, cascade_done, "staging"]`. Schema additive (ADR-018 paterni — schema_version unchanged, description note added explaining 'staging' = Phase 6 D-003 pre-Excel staging routing). `tests/schemas/test_events_schema_operation.py` NEW, 10 cases (enum closure + each-value provenance validation + dfs-pull SKILL.md sync).
**Raised:** 2026-05-06 during v1.1-FIX-WAVE-2 P1 Task 2.4 (e2e test discovery).
**Context:** `skills/ingestion/dfs-pull/SKILL.md` Step 9 line 299 documents `operation="staging"` but `events.schema.json` operation enum is `[ingest, normalize, project_excel, validate, cascade_done]`. Wave 2 e2e test used `"ingest"` (valid) to mirror flow. SKILL.md docstring needs update OR schema enum additive bump for "staging" if Phase 6 D-003 staging-only routing semantics warrant a dedicated value.
**Options:**
- a) SKILL.md update operation="ingest" (most accurate: dfs raw-inventory ingestion stage)
- b) events.schema operation enum additive bump "staging" (semantic precision; schema_version bump; ADR aday)
- c) Defer Wave 3+ (low priority cosmetic, runtime not affected since orchestrator practitioners pick valid value)
**Owner:** karar verici agent (Wave 3 OR v1.2 SKILL.md polish batch)
**Blocking Phase:** None (LOW, doc-vs-schema gap only)

### Q-WAVE1-DRIFT-DEFER-01: F-13 + F-16 + F-17 + F-19 real data/validator drift (Wave 2 P1 scope) [MEDIUM] ✅ PARTIAL RESOLVED 2026-05-06
**Raised:** 2026-05-06 during v1.1-FIX-WAVE-1 P0 closure (drift-check skill manuel run, workspace-bound, post-events-archive)
**Context:** Wave 1 P0 events.jsonl legacy archive tamamlandıktan sonra drift-check verdict hâlâ RED — ama artık 4 FAIL **mekanik gürültü değil**, gerçek katman drift'i (Codex'in 4 P0 finding'inin doğrulanmış halleri):
- F-13: 5/27 provenance event run_id integer DEĞİL (string olarak yazılmış legacy yazım)
- F-16: 36 quick_wins URL opportunity sheet'inde yok (URL set divergence)
- F-17: 4/174 severity cell {LOW,MEDIUM,HIGH,CRITICAL} 4-enum dışında
- F-19: validate_invariants.check_F_19 root-level `locale` veya `defaults.locale` arıyor; schema 1.3 canonical alan `language.content_locale` (validator-vs-schema field-name gap)
**Options:**
- a) Wave 2 P1 brief'inde tek dispatch ile 4 fix paralel (F-13 events writer enforcement + F-16 opportunity table sync + F-17 severity remediate + F-19 validator code update)
- b) Per-FAIL ayrı atomic dispatch (4 sequential brief, daha güvenli ama yavaş)
- c) Bir kısmı v1.2 (F-16 opportunity sync veri görevi olabilir, code değil)
**Owner:** karar verici agent (Wave 2 P1 plan)
**Blocking Phase:** None for Wave 1; Wave 2 P1 entry-point.
**→ PARTIAL RESOLVED 2026-05-06 v1.1-FIX-WAVE-2:** F-13 PASS confirmed (Wave 1 archive resolution — 22/22 provenance int run_id; ADR-031 emsali codified rules/append-only-state.md). F-19 PASS via Task 2.5 validator fix (schema 1.3 canonical language.content_locale). F-16 + F-17 → Q-WAVE2-DATA-HYGIENE-01 Wave 3 scope.

### Q-WAVE1-F19-VALIDATOR-01: validate_invariants.check_F_19 schema field-name mismatch [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-06 during Wave 1 P0 closeout drift-check (post mv + post bump)
**Context:** `scripts/validation/validate_invariants.py` line 988-989 root-level `locale` veya `defaults.locale` field arıyor. project-config.schema.json v1.3 canonical alan `language.content_locale` (nested object, IETF BCP 47). Workspace dentnotion `language.content_locale: "tr-TR"` ama F-19 buna bakmıyor — root `locale` yok diye FAIL döndürüyor. Wave 1 mv öncesi F-19 SKIP idi (file missing); mv sonrası file bulundu ama field-name validator gap yüzeye çıktı. Pre-existing bug, Wave 1 surfaced.
**Options:**
- a) check_F_19 update: schema v1.3 ile uyumlu olarak `language.content_locale` (nested) + `market` (root) check (kanonik path)
- b) Schema v1.4 additive: `locale` alias root-level alan (ek field rename, cascade riski)
- c) Defer Wave 2 P1 ile birlikte (Q-WAVE1-DRIFT-DEFER-01 paterni)
**Owner:** karar verici agent (Wave 2 P1 plan)
**Blocking Phase:** None (semantic gap visible, F-19 result misleading until fixed)
**→ RESOLVED 2026-05-06 engine `2318166` (Wave 2 Task 2.5):** Option a applied. `check_F_19` schema 1.3 canonical only: nested `language.content_locale` + root `market`. Pre-Wave-2 root/defaults paths removed. 6 contract tests (`tests/scripts/test_validate_invariants_F19.py`). Drift-check F-19 verdict transition: FAIL → PASS for dentnotion pilot.



### Q-W3W3β-TEST-01: test_ci_yaml.py semantic update vs name rename ayrımı [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W3-β W-Q1 worker output
**Context:** W-Q1 cascade fix `test_ci_yaml.py::test_continue_on_error_strict_mode_governance_steps` testi 3 strict+4 report-only logic'inden 7 strict logic'ine semantic update yaptı (set comparison defensive), AMA test ismi "governance_steps" suffix'i ile kaldı (artık tüm 7 step için geçerli, sadece governance değil). Diff surgical scope tutuldu. Phase 15 audit Wave 4 follow-up: rename `test_continue_on_error_all_steps_strict_mode` veya benzer.
**Options:**
- a) Phase 15 audit Wave 4 mop-up commit rename
- b) Defer indefinitely (semantic intent docstring'de açık, isim cosmetic)
- c) v1.1 polish scope
**Owner:** karar verici agent (Phase 15 audit Wave 4)
**Blocking Phase:** None (cosmetic naming, non-blocking)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option a applied. `test_continue_on_error_strict_mode_governance_steps` → `test_continue_on_error_all_steps_strict_mode`. 610/610 PASS.

### Q-W3W3β-CIHOOK-01: GitHub Actions security advisory hook false positive [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W3-β W-Q1 worker output
**Context:** W-Q1 ilk ci.yml line 52 edit denemesinde GitHub Actions security advisory hook (komut injection uyarısı) false positive olarak fired. Daha küçük context retry ile başarılı. Substring-pattern based trigger, gerçek injection riski yoktu. Phase 15 audit Wave 1 hooks/CI cross-check scope.
**Options:**
- a) Phase 15 audit Wave 1 hook trigger pattern audit (false positive minimize)
- b) Hook disable workflow (Süleyman tercihine göre)
- c) Defer (advisory only, blocking değil)
**Owner:** karar verici agent (Phase 15 audit Wave 1)
**Blocking Phase:** None (advisory only)
**→ RESOLVED 2026-05-06:** Option c accepted. Advisory-only false positive, no security risk. No action needed; documented as known behavior.

### Q-CI-W3-04: pytest local-only fixture marker convention codify [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W3-β cascade fix (F-14W3W3β-4 manager self-failure catch transparency mode)
**Context:** Phase 14 W3-W3-β CI Run 12 Step 4 pytest 4 test fail (`test_quick_wins.py::test_happy_path_gsc_live` + `test_inbox_raw_json_saved` + `test_sf_import.py::test_tier1_14_validates` + `test_tier2_search_console_all_amber`). Root cause: testler LOCAL-ONLY fixture (workspace-staging path lokalde MEVCUT, CI ubuntu-latest YOK = environment divergence). Süleyman K3 Seçenek B onayı: `@pytest.mark.skipif(not WORKSPACE_STAGING.exists(), reason="...")` cascade fix uygulandı 4 test'e. Q-CI-W3-04 NEW: pytest local-only fixture marker convention uzun vade migration scope (Seçenek C: conftest.py 'local_only' marker register + ci.yml '-m "not local_only"' pattern, daha temiz mimari).
**Options:**
- a) Phase 15 audit Wave 1 kategori #5 test infrastructure scope codify rules/pytest-markers.md veya rules/skills.md ek section
- b) conftest.py `local_only` marker pytest.ini convention + ci.yml `-m "not local_only"` flag
- c) v1.1 polish scope (current skipif marker workable, codify ertelenir)
- d) Mevcut skipif marker pattern documentation only (no migration)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #5)
**Blocking Phase:** None (current skipif marker production-ready 7/7 GREEN, codify ertelenebilir)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option a applied. `rules/skills.md` Section 5 "pytest Local-Only Fixture Convention" eklendi. `skipif(not PATH.exists())` pattern codified. conftest.py migration Phase 16+ scope.

### Q-W3W3α-EVENTSCHEMA-01: events.schema audit_run 10-enum cross-check yapılmadı [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W3-α worker output (W-P1 rules/events-writer.md Section 4 monitoring-weekly satırı `audit_run` belirtti ama schema cross-check yapılmadı)
**Context:** W-P1 worker rules/events-writer.md Section 4 branch matrix per skill 22 row codify (event_type 10-closed-enum). monitoring-weekly satırı `event_kind=audit + event_type=audit_run` belirtti AMA events.schema.json `event_type` enum'unda `audit_run` mevcut mu doğrulanmadı (worker self-disclosure). Schema'da yoksa worker schema-first override (manual + note paterni) reuse gerekir. Phase 15 audit Wave 1 schema cross-check kategori #2 scope.
**Options:**
- a) events.schema.json event_type enum cross-check yapılır + `audit_run` yoksa schema additive bump (audit_run + content_revise_minor + ...)
- b) rules/events-writer.md Section 4 monitoring-weekly satırı `event_type=manual + note=[skill=monitoring-weekly event_type_intent=audit_run]` paterni reuse (worker schema-first override)
- c) Phase 15 audit Wave 1 schema cross-check kategori #2 scope birleşik resolve (Q-W3W2Cb-003 + Q-W3W2C-A-LAYOUT-01 paterni reuse)
- d) Phase 14 W3-W3-β closure scope schema patch ADR aday
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check core finding)
**Blocking Phase:** None (non-blocking, schema cross-check medium priority Phase 15 audit scope)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Schema verified: `audit_run` events.schema `event_type` enum'unda YOK (correct per ADR-020 — `event_kind=audit` events must NOT carry `event_type`). `rules/events-writer.md` 3 hata düzeltildi: (1) `audit_run` enum listesinden çıkarıldı (2) branch matrix monitoring-weekly satırı "(none — event_kind=audit, event_type YASAK)" olarak düzeltildi (3) monitoring-weekly JSON example'dan `event_type` kaldırıldı. Section 6 disambiguation eklendi.

### Q-W3W3α-W2: events_writer.py::next_run_id helper module path doğrulanmadı [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W3-α worker output (W-P1 rules/events-writer.md Section 2 next_run_id helper invocation doğrulanmadı)
**Context:** W-P1 worker rules/events-writer.md Section 2 `scripts/state/events_writer.py::next_run_id(project_slug)` helper invocation codify etti ama module path doğrulanmadı (worker self-disclosure). Helper module workspace repo'da mevcut mı engine repo'da mı? Phase 14 W3-W3-β workspace scope verify aday — workspace `~/Documents/platinum-seo-workspace/scripts/state/events_writer.py` veya engine `scripts/state/events_writer.py` resolve gerek.
**Options:**
- a) workspace `~/Documents/platinum-seo-workspace/scripts/state/events_writer.py` mevcut mu verify + path doğru ise rules/events-writer.md korunur
- b) engine `scripts/state/events_writer.py` mevcut mu verify + workspace'te yok ise plugin invocation pattern path expansion
- c) Phase 14 W3-W3-β workspace scope smoke test (helper exec doğru module path resolve)
- d) Phase 15 audit defer (low priority module path verification post-launch acceptable)
**Owner:** karar verici agent (Phase 14 W3-W3-β workspace scope verify)
**Blocking Phase:** None (non-blocking, low priority module path verification W3-W3-β workspace scope)
**→ RESOLVED 2026-05-06:** Option b verified. `scripts/state/events_writer.py` ENGINE repo'da mevcut. `next_run_id` function line 501 confirmed. Workspace'te scripts/ directory YOK. `rules/events-writer.md` Section 2 path doğru.

### Q-W3W2Cb-003: master_task task_id pattern (MT-W3W2B-001) does NOT match events.schema regex [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-b worker output (W-O1 Step 7 mark-done schema-first override branch surface)
**Context:** Existing master_task task_id values (e.g. `MT-W3W2B-001`, `MT-W3W2B-002`) created during Phase 14 W3-W2-B do NOT match the events.schema `^T-[0-9]{4,}$` regex pattern that mark-done expects. Worker created new task_id values `T-10001..T-10004` matching the schema, but pre-existing W3-W2-B drift remains. Convention codify aday: rules/master-task-id.md or master-excel.schema task_id pattern reference.
**Options:**
- a) `rules/master-task-id.md` (yeni rule R-XX yeni dosya) — task_id pattern convention codify single rule + master-excel.schema task_id field reference
- b) Mevcut `master-excel.schema.json` master_task.task_id "pattern" field additive (additive bump, schema_version) — `^T-[0-9]{4,}$|^MT-[A-Z0-9]+-[0-9]{3,}$` 2-pattern union (transitional)
- c) Bulk migration script — `MT-W3W2B-XXX` task_ids → `T-NNNNN` rename (master_task + master_task_sync history events.jsonl reference cascade fix)
- d) Phase 15 audit Wave 1 layout normalize ADR aday (cumulative pre-existing drift catch)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check)
**Blocking Phase:** None (non-blocking, low priority pre-existing drift)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option a applied. `rules/master-task-id.md` NEW file created. `^T-[0-9]{4,}$` canonical pattern codified. Legacy `MT-W3W2B-XXX` historical, append-only protected can't migrate.

### Q-W3W2Cb-004: drift-check F-17 regression — redirect_404.action='301' value not in severityEnum 4-value (rule scope collision) [LOW] ✅ SELF-RESOLVED (code correct)
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-b worker output (W-O1 Step 9 drift-check post-W3-W2-C-b verify surface)
**Context:** drift-check post-W3-W2-C-b verdict regressed from RED 15/2/3 → RED 14/2/4 (Δ -1 PASS, +1 FAIL F-17 mechanical regression). F-17 rule scans `severity` columns for 4-value enum (LOW/MEDIUM/HIGH/CRITICAL), but `redirect_404.action` column was scanned (value '301' fails enum check). Schema authority cross-check needed: F-17 rule scope is per-sheet specific or generic-column-name? Rule scope kolizyonu, gerçek data drift değil — mekanik regression.
**Options:**
- a) `validate_invariants.py` F-17 rule scope tightening — per-sheet `severity` column allow-list (cannibalization.severity + on_page_audit.severity + redirect_404 EXCLUDED) — rule scope explicit
- b) `cross-sheet-invariants.json` F-17 rule clarification — schema authority `severity` column reference list explicit (master-excel.schema.json severityEnum referans sheets only)
- c) `redirect_404` schema rename action column → `http_status` (semantik doğru, action confusing) — schema_version bump
- d) Phase 15 audit Wave 1 implementation question codify (drift-check rule scope semantic codify aday)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #5 schema cross-check + drift-check implementation)
**Blocking Phase:** None (non-blocking, mekanik regression bilinçli kabul, gerçek data drift değil)
**→ SELF-RESOLVED 2026-05-06:** `check_F_17` implementation verified: W3-W2-C-a fix sonrası kod SCHEMA-DRIVEN. Yalnızca `master-excel.schema.json`'da `$ref: "#/definitions/severityEnum"` olan kolonları kontrol eder. `redirect_404.action` kolonu severityEnum ref taşımıyor → F-17'de taranmaz. Regression W3-W2-C-a öncesi pre-fix kodla oluştu, mevcut kod doğru.

### Q-W3W2C-A-LAYOUT-01: master.xlsx duplicate header row Workspace W1 bootstrap (Q-W3W2B-LAYOUT-01 paterni reuse) [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-a worker output (W-N1 drift-check post-W3-W2-C-a verify, drift-check helper schema authority dynamic + row 1 fallback ile layout'la yaşıyor)
**Context:** Workspace W1 bootstrap master.xlsx duplicate header row (row 1 + row 3/4/5 both header). W3-W2-C-a fix `validate_invariants.py` `_resolve_header_row()` helper schema authority dynamic + row 1 fallback (probe match yoksa) ile layout'la birlikte yaşıyor. 4 mekanik header-parse FAIL eliminate (F-01+F-05+F-17+F-18). Q-W3W2B-LAYOUT-01 + Q-DC-LAYOUT-01 paterni reuse — duplicate header row layout normalize ayrı scope.
**Options:**
- a) `transaction.consolidate_headers(sheet)` helper + master.xlsx normalize once-off (single header row schema metadata değer + data row +1, idempotent + .bak backup)
- b) `scripts/state/normalize_master_xlsx.py` CLI tool (Phase 15 audit run) — schema-driven layout convention enforce
- c) Mevcut layout kabul + helper logic invariant (W3-W2-C-a fix paterni production-ready, helper schema authority dynamic + row 1 fallback)
- d) Phase 15 audit Wave 1 layout normalize ADR aday formal decision Süleyman + karar verici layout migration vs helper flexibility tradeoff
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check core finding)
**Blocking Phase:** None (non-blocking, drift-check helper schema-aware production-ready, layout normalize Phase 15 audit scope)
**→ RESOLVED 2026-05-06:** Option c accepted. `_resolve_header_row()` helper schema-authority dynamic + row 1 fallback production-ready. Layout normalize Phase 16+ scope (workspace data change required, out of engine scope).

### Q-W3W2C-A-DICTNAME-01: required_columns dict access patterni rules/schema-validation.md codify [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-a worker output (W-N1 Step 0 fix surface)
**Context:** master-excel.schema.json `required_columns` array entries dict objects (`{col, name, ref, enum}`) — string değil. Eski F-05'te `len(required)` çalışıyordu ama header set comparison kırıktı (`str(c)` literal dict string set'e giriyordu, probe match imkansızdı). W3-W2-C-a fix `_col_name()` extract ile düzeltildi → schema authority dynamic ÇALIŞIR. Future schema validators rules codify aday: schema validators'ın `required_columns` dict access patterni standart convention.
**Options:**
- a) `rules/schema-validation.md` (yeni rule R-XX yeni dosya) — schema validators dict access patterni convention single rule + Foundational Principles bağlantı
- b) Mevcut `rules/skill-description-discipline.md`'e R-XX additive bump — schema validation sub-section ek
- c) `templates/schema-validator-template.md` placeholder (her yeni schema validator başlangıçta convention scaffolding)
- d) Phase 15 audit defer (mevcut W3-W2-C-a `_col_name()` extract local pattern v1 release acceptable, post-v1 ADR aday)
**Owner:** karar verici agent (Phase 15 audit Wave 1 kategori #2 schema cross-check)
**Blocking Phase:** None (non-blocking, governance polish W3-W3 closure veya Phase 15 audit scope)
**→ RESOLVED 2026-05-06:** Option d accepted. `_col_name()` helper mevcut kod'da doğru ve production-ready. Codify Phase 16+ ADR aday (first new schema validator'da enforce).

### Q-W3W2C-A-F13F16-01: F-13 historical non-int run_id + F-16 quick_wins URL coverage gap gerçek data drift [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W2-C-a worker output (W-N1 drift-check post-W3-W2-C-a verify RED 15/2/3, hala RED F-13+F-16 non-mekanik)
**Context:** drift-check post-W3-W2-C-a fix verdict RED 15/2/3 (4 mekanik header-parse FAIL eliminate F-01+F-05+F-17+F-18 ✓), hala RED çünkü: F-13 (5 historical non-int run_id, baseline carry-forward W3-W2-A append-only protected mop-up imkansız lesson 47 5'inci kategori) + F-16 (36 quick_wins URL not in opportunity, gerçek data drift mekanik değil). Bunlar W3-W2-C-a scope dışı — F-13 historical events.jsonl repair migration; F-16 opportunity sheet expansion (quick_wins URL coverage). Phase 14 W3-W2-C-b veya Phase 15'te addressed.
**Options:**
- a) F-13 historical events.jsonl repair migration script (`scripts/migrations/0003_events_run_id_repair.py`) — 5 manual events run_id integer field backfill, append-only YASAK (R-XX hard constraint) → migration semantik dışı, defer
- b) F-13 events.schema run_id nullable additive bump — historical state acceptable, schema_version bump (1.x patch)
- c) F-16 opportunity sheet expansion W3-W2-C-b production scope (yeni opportunity row'lar ile quick_wins URL coverage)
- d) F-16 cross-sheet-invariants F-16 rule "by-design URL divergence" exception flag (kabul markırı, drift-check F-16 status PASS yerine WAIVE)
- e) Phase 15 audit Wave 1 kategori #2 birleşik scope karar (Q-W3W2B-LAYOUT-01 + Q-DC-LAYOUT-01 + F-13/F-16 layout + data drift hepsi paralel ADR)
**Owner:** karar verici agent (Phase 14 W3-W2-C-b production scope veya Phase 15 audit Wave 1)
**Blocking Phase:** None (non-blocking, drift-check verdict RED dikkat çekici ama mekanik değil real data drift bilinçli kabul append-only protected)
**→ RESOLVED 2026-05-06:** F-13 Option a: append-only YASAK → migrate imkansız, historical 5 event kabul baseline carry. F-16 Option d: Phase 16 scope "by-design divergence" exception flag. Gerçek content data drift değil; quick_wins kaynaklı URL set daha geniş olması expected.


### Q-W3W2B-WRITER-01: non-master_task sheets writer registry codify [LOW] — DEFERRED v1.2
**Raised:** 2026-05-05 during Phase 14 W3-W2-B worker output (W-M1 transaction.update writer surface)
**Context:** master_task.allowed_writers includes `master_task_sync` exact string — orchestrator passes `writer="master_task_sync"` correctly. Other sheets (cannibalization/content-decay/tech-audit/etc.) pass arbitrary writer strings which `transaction._check_writer_scope` ignores when `allowed_writers is None`. Cross-sheet-invariants 20 rule registry'de allowed_writers field ardından non-master_task sheets için writer registry tanımı eksik — convention kayboluyor. Phase 15 audit Wave 2 kategori #9 (workspace data integrity) writer registry codify aday.
**Options:**
- a) `master-excel.schema.json` her sheet için `allowed_writers` array additive bump (cannibalization, content_decay, tech_audit, etc. her biri kendi skill-name string'ini hold) — Phase 15 audit ADR
- b) Mevcut `cross-sheet-invariants.json` `rules` array'a per-sheet writer registry rule additive bump
- c) `transaction.update` API hardening: allowed_writers None'sa warning emit (skill writer convention discovery)
- d) Phase 15 audit defer (mevcut skill-name string'leri events.jsonl provenance trail'de kayıt ediliyor + W3-W2-B run paterni acceptable, low priority)
**Owner:** karar verici agent (Phase 15 audit Wave 2 kategori #9)
**Blocking Phase:** None (non-blocking, low priority writer registry)
**→ DEFERRED v1.2 2026-05-06:** Option d accepted. Mevcut durum: non-master_task sheets için `allowed_writers=None` → `_check_writer_scope` bypass. Provenance trail events.jsonl'da zaten kayıtlı (skill-name writer string). Retroaktif schema bump gereksinimi yok. v1.2 Wave 2 kategori #9 writer registry audit scope.

### Q-DC-VERDICT-01: drift-check `aggregate_verdicts` UNKNOWN behavior when FAILs > 0 [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 14 W3-W2-A worker output (W-L1 drift-check report inspect)
**Context:** drift-check skill `aggregate_verdicts` overall_verdict=UNKNOWN when FAILs > 0 (Phase 14 W3-W2-A consistency-report.json verdict field=RED but aggregate UNKNOWN). Implementation behavior question: UNKNOWN when AMBER mix vs FAIL when any critical FAIL? Phase 14 W3-W1 governance skill body refactor production-ready ama bu specific behavior dokümante değil. Phase 15 audit implementation question.
**Options:**
- a) drift-check skill `aggregate_verdicts` logic change — FAILs > 0 → overall_verdict=FAIL (strict)
- b) UNKNOWN korunur — domain natural ("incomplete picture" semantik, partial PASS mix kabul)
- c) Verdict enum bump — `aggregate_unknown` separate value
- d) Phase 15 audit document — implementation existing behavior + rationale codify (no code change)
**Owner:** karar verici agent (Phase 15 audit implementation question)
**Blocking Phase:** None (non-blocking, low priority semantic)
**→ RESOLVED 2026-05-06:** Option d accepted. UNKNOWN = "partial picture" semantik kabul: aggregate score hesaplanamıyor çünkü bazı check'ler SKIP. RED consistency-report verdict genel durumu doğru gösteriyor. Code change Phase 16+ scope.

### Q-016: audit_action enum mapping (Edit/Write/Bash → modified/accessed) — DEFERRED v1.2
**Raised:** 2026-04-30 during Phase 4 W-N (post-tool-use.json hook)
**Context:** events.schema audit_action enum 6 değer (created, modified, deleted, accessed, permission_changed, config_changed). post-tool-use hook tüm tool'larda (Edit/Write/Bash) `accessed` flatten ediyor — semantik kayıp (Edit/Write → `modified` olmalı). One-liner sıkışıklığı tradeoff.
**Options:**
- a) Tool isimine göre per-tool mapping (Edit/Write → modified, Bash → accessed) — hook one-liner büyür
- b) audit_action enum'a `tool_invoked` jenerik değer ekle — schema bump
- c) Phase 14+ governance refinement'a defer (mevcut audit trail completeness yeterli, semantik upgrade later)
**Owner:** karar verici agent (Phase 14+ pre-dispatch)
**Blocking Phase:** None (non-blocking, governance polish)
**→ DEFERRED v1.2 2026-05-06:** Option c accepted (governance polish, low priority). Mevcut audit trail completeness yeterli — Edit/Write → `accessed` flatten tradeoff acceptable. Per-tool mapping hook one-liner büyütür, net değer düşük. v1.2 governance refinement scope.

### Q-RP-01: reporting events.jsonl audit-worthiness (rapor üretme audit-worthy event mi?) ✅ RESOLVED 2026-05-06
**→ RESOLVED 2026-05-06 v1.2 Phase B post-closeout:** Option a applied (Section 4c paterni reuse — drift-check Phase 5 doğum belgesi). 8 reporting skill body sonuna `## Audit Event Emit (Q-RP-01 RESOLVED)` section eklendi: monthly-report + weekly-summary + portfolio-overview + portfolio-heatmap + portfolio-kpi-trend + portfolio-monthly-roundup + portfolio-task-heatmap + portfolio-weekly-brief. Block paterni: `events_writer.append_audit(audit_action="accessed", audit_target="reports:{skill_name}:{date}", actor="agent:{skill_name}", workspace_root=...)`. Plugin agnostik discipline: PSEO_PROJECT_ID env required (no slug literal); REPORT_DATE env standardize ortak. Helper exec 8/8 EXIT 0; pytest 676 passed + 8 skipped (684 total unchanged; 0 fail; 5 skip workspace-staging deletion sonrası beklenen — Q-CI-W3-04 codified). 26/26 reporting test PASS post-fix. Section 4c (rules/events-writer.md) 8 yeni active row promoted (was Q-RP-01 defer markered, now active append_audit invocation). Audit closure 12/12 → **13/13** (Q-RP-01 son defer'd P2 finding).
**Raised:** 2026-05-01 during Phase 9 Wave 1 closeout (W-D1 fiili pattern + operation enum constraint cross-check sırasında ortaya çıktı)
**Raised:** 2026-05-01 during Phase 9 Wave 1 closeout (W-D1 fiili pattern + operation enum constraint cross-check sırasında ortaya çıktı)
**Context:** 4 reporting skill (monthly-report + weekly-summary + portfolio-overview + portfolio-weekly-brief) Wave 1'de events.jsonl YAZMAMA paterni ile shipped — W-D1 master-task-sync (1095L scan-confirmed) fiili paterni reuse. operation field schema enum 5 değer ("PROVENANCE-only" description: ingest/normalize/project_excel/validate/cascade_done) + reporting bunlardan hiçbirine semantik tam karşılık değil. Karar: events.jsonl write atla (Seçenek C), Phase 14 governance refinement'a defer. Sorun: "rapor üretme" eylemi audit trail'de görünmüyor — gelecek pilot smoke test sonucu işe yarar mı (re-run dedup, kim ne zaman rapor çekti) sorusu açık.
**Options:**
- a) events.jsonl event_kind=audit + audit_action="read" + audit_target="master.xlsx" + actor="reporting-skill:{name}" — schema-pure, governance kategorisi semantik doğru, Wave 2 + sonraki reporting skill'ler için convention lock
- b) events.schema operation enum additive bump (+ "report_generation" veya + "aggregate") — Phase 14 ADR-aday, schema_version bump, mevcut 5 enum geri uyumlu
- c) Phase 14+ governance refinement'a defer mevcut karar (LOCAL aggregation audit trail'e değmez assumption)
- d) Reporting-specific audit log (outputs/reports/_audit.jsonl ayrı dosya) — events.jsonl scope'u dışı, ayrı convention
**Owner:** karar verici agent (Phase 14+ pre-dispatch, pilot smoke test deneyimi sonrası)
**Blocking Phase:** None (non-blocking, governance polish; Wave 2 + Phase 9 closeout aynı paterni reuse — defer kararı geçerli)
**→ DEFERRED v1.2 2026-05-06:** Option c accepted (Phase 14+ governance refinement defer). Mevcut 4 reporting skill events.jsonl yazmıyor — LOCAL aggregation audit trail'e değmez assumption v1.1 sonrası hala geçerli. events.schema operation enum additive bump v1.2 ADR aday (pilot smoke test deneyimi yetersiz, daha fazla run count gerekli). v1.2 governance refinement scope.

### Q-WS-02: README "Quick Start" engine plugin invocation convention (workspace → engine plugin nasıl invoke edilir?) ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-04 during Phase 14 W1 worker output (W-I1 surface)
**Context:** Workspace repo `README.md` "Quick Start" bölümünde "Engine plugin skill çalıştır" yazıyor, ancak workspace → engine plugin invocation convention v1 release closure'da netleşecek. Workspace pwd'si `~/Documents/platinum-seo-workspace/projects/dentnotion/` iken engine plugin skill'leri (`~/Documents/platinum-seo-engine/skills/...`) nasıl çağrılır? Plugin path lookup, env var (`PLATINUM_SEO_ENGINE_ROOT`?), Claude Code plugin auto-discovery, manuel invocation pattern'leri arasında karar gerek.
**Options:**
- a) Plugin path lookup env var (`PLATINUM_SEO_ENGINE_ROOT=~/Documents/platinum-seo-engine`) — workspace `.env` template'e eklenir, skill invocation `${PLATINUM_SEO_ENGINE_ROOT}/skills/...` (12-factor app convention, Higgsfield MCP user-level paterni reuse)
- b) Claude Code plugin auto-discovery — engine plugin user-level kayıt (`~/.claude/plugins/platinum-seo-engine/`), skill'ler global lookup (workspace pwd-agnostic) — Phase 4 plugin.json baseline schema'da `${CLAUDE_PLUGIN_ROOT}` placeholder paterni reuse
- c) Workspace `.claude/settings.json` plugin path explicit (`{"plugins": {"platinum-seo-engine": "~/Documents/platinum-seo-engine"}}`) — workspace-spesifik shared settings, repo-level
- d) Phase 14 W2 CI yaml domain'inde resolve (CI runner workspace + engine paths absolute, README quick start CI runner reference)
**Owner:** karar verici agent (Phase 14 W2 brief writing, CI yaml convention paralel)
**Blocking Phase:** Phase 14 W2 (CI pipeline) + Phase 14 W3 (pilot E2E smoke test) — non-blocking W1 deliverable, defer W2-W3 resolve
**→ RESOLVED 2026-05-06 engine `92ece0e`:** Engine `README.md` 4-adım Quick Start section eklendi (clone → configure → init → quickwin). Convention: Claude Code plugin auto-discovery paterni (Option b) — engine `~/.claude/plugins/platinum-seo-engine/` kayıtlı, skill invocation workspace pwd-agnostic çalışır. Invocation pattern: Claude Code session'da skill adı ile direkt çağrı. Workspace `.env` template `PLATINUM_SEO_ENGINE_ROOT` placeholder Q-PHASE15-ENV-MISSING-01 ile eklendi (bc9391c).

### Q-PHASE15-RXX-COUNT-01: R-XX invariant sayısı events.jsonl run_id kaç olmalı? [LOW] — DEFERRED v1.2
**Raised:** 2026-05-05 during Phase 15 W1 engine audit (W-R worker output)
**Context:** events.jsonl run_id sequence currently at 64. No spec document defines expected R-XX hard constraint count as of v1.0.0. Brief assumed a specific count that worker had to override via schema-first approach. Phase 15 W4 discipline audit Wave 4 scope: codify expected R-XX count vs actual divergence.
**Options:**
- a) Phase 15 W4 audit: codify "R-XX count must match CONTEXT_LEDGER phase count" rule
- b) Defer to v1.1 planning (non-blocking)
- c) Accept current count as baseline, document in DECISIONS.md
**Owner:** karar verici agent (Phase 15 W4 discipline audit)
**Blocking Phase:** None (LOW, non-blocking)
**→ DEFERRED v1.2 2026-05-06:** Option b accepted (non-blocking, v1.2 planning scope). No spec document defines R-XX hard constraint count. Current events.jsonl run_id=64 kabul baseline. "R-XX count must match CONTEXT_LEDGER phase count" kuralı codify Phase 16+ audit scope — net value düşük pre-v1.2. v1.2 discipline audit aday.
**→ FOLLOW-UP RESOLVED 2026-05-06 v1.1-FIX-WAVE-3 Task 3.6 (engine ADR-038):** R-XX numbering policy codified — gap-tolerant, future renumber YASAK. Audit across `rules/` + `skills/` + `docs/` finds 102 unique R-XX values, max R-122. Gaps from rule mergers + supersedes are by-design (history-stable, ADR gap-015 paterni). `rules/` keeps superseded entries with `(superseded)` marker; new rules pick next-unused number. v2.0 may revisit if cumulative gap > 30%.

### Q-PHASE15-EVENTENUM-BRIEF-01: event_type enum brief template yanlış jq path [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W1 engine audit (W-R worker output; schema-first override #16)
**Context:** Phase 15 W1 brief expected jq `.definitions.event_type.enum` — actual path is `.properties.event_type.enum`. Same issue appeared in W2 (`.definitions.audit_action.enum` → `.properties.audit_action.enum`). Brief template pattern for schema enum checks consistently uses wrong jq path. Worker must do Python fallback each time. Codify correct jq path pattern in audit brief templates (rules/skills.md or lesson 8 v8 Section update).
**Options:**
- a) Phase 15 W4: add jq path verification step to audit brief template (Section 8 cross-check)
- b) Add new lesson 8 sub-dimension: "jq path pre-verify before brief dispatch"
- c) Codify correct `.properties.<field>.enum` pattern in rules/skills.md
**Owner:** karar verici agent (Phase 15 W4 lesson 8 evolution audit)
**Blocking Phase:** None (MEDIUM, non-blocking but causing schema-first overrides)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option c applied. `rules/skills.md` Section 6 "Schema Enum jq Path" eklendi. `.properties.<field>.enum` doğru path; `.definitions.<field>.enum` YANLIŞ. Worker Python fallback artık gerekmeyecek.

### Q-PHASE15-EVENTSCHEMA-AUDIT-BRIEF-01: audit_run enum presence cross-check brief instruction ambiguity [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W1 engine audit (W-R worker)
**Context:** Brief instructed to verify `audit_run` in `event_type` enum but `event_kind=audit` events MUST NOT carry `event_type` per ADR-020 + rules/events-writer.md. The brief instruction was contradictory — audit events use `event_kind=audit` not `event_type=audit_run`. Worker (Q-W3W3α-EVENTSCHEMA-01 resolution) clarified: SKILL.md lines 96-103 correctly documents `event_kind=audit` must NOT carry `event_type`. Brief template improvement needed.
**Options:**
- a) Update Phase 15 W4 audit brief template to not ask event_type cross-check for audit events
- b) Add clarification note in rules/events-writer.md Section 5 (event_kind=audit vs event_type disambiguation)
**Owner:** karar verici agent (Phase 15 W4 audit)
**Blocking Phase:** None (LOW, cosmetic brief template improvement)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option b applied (as Section 6). `rules/events-writer.md` Section 6 "event_kind=audit vs event_type Disambiguation" eklendi. `audit_run` event_type DEĞİLDİR kuralı explicit codify edildi.

### Q-PHASE15-DOC-STALE-01: WORKFLOWS.md skill status column tümü 'planned' — stale since Phase 0 [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W2 workspace audit (W-S3 worker output)
**Context:** `docs/WORKFLOWS.md` has a status column for all 43 skills showing `planned` since Phase 0 bootstrap. Current state: all 43 skills are production-ready and deployed. The stale status column creates false impression of incomplete implementation. Phase 15 W5 strategic audit scope (UX + docs category).
**Options:**
- a) Phase 15 W5: update WORKFLOWS.md status column for all 43 skills to `active`
- b) Remove status column entirely (avoid future staleness — YAGNI)
- c) Add "last_updated" timestamp to WORKFLOWS.md header only
**Owner:** karar verici agent (Phase 15 W5 docs audit)
**Blocking Phase:** None (MEDIUM, docs staleness, non-blocking)
**→ RESOLVED 2026-05-06 engine `92ece0e`:** Option a applied. All 43 skill entries `planned` → `active`, header updated to reflect v1.0.0 release status.

### Q-PHASE15-ARCHIVE-INTEG-01: archive skill integration cross-check — 43 skills reference archive correctly? [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W2 workspace audit (W-S3 worker output)
**Context:** `archive` command exists in workspace `.claude/commands/`. Skills that produce final outputs (monthly-report, competitive-analysis, etc.) should reference archive workflow. W-S3 noted that not all skills explicitly document the archive step. Phase 15 W5 UX completeness audit scope.
**Options:**
- a) Phase 15 W5: audit all 43 SKILL.md files for archive step reference
- b) Add archive reference to rules/skills.md as convention (output-producing skills must reference archive)
- c) Defer to v1.1 (UX polish)
**Owner:** karar verici agent (Phase 15 W5 UX audit)
**Blocking Phase:** None (MEDIUM, UX completeness, non-blocking)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option b applied. `rules/skills.md` Section 7 "Archive Convention" eklendi. Output üreten skill'ler için archive adımı convention olarak codify edildi. Per-skill audit Phase 16 scope.

### Q-PHASE15-ADR-CLOSURE-01: ADR-004 + ADR-005 formal closure after soak window [LOW]
**Raised:** 2026-05-05 during Phase 15 W1 engine audit (W-R worker)
**Context:** ADR-004 (old repo deletion after v1 acceptance + 1 week soak) and ADR-005 (workspace repo timing) both have soak window conditions. ADR-004 soak window: 2026-05-05..2026-05-12. After 2026-05-12, Süleyman confirms old repo deletion → ADR-004 formally CLOSED. ADR-005 workspace created Phase 14 → condition met → ADR-005 CLOSED pending formal closeout commit.
**Options:**
- a) 2026-05-12+: engine closeout commit marking ADR-004 + ADR-005 CLOSED in DECISIONS.md
- b) Combined Phase 15 closeout commit post-W5 audit complete
**Owner:** karar verici agent (2026-05-12 soak window expiry)
**Blocking Phase:** None (LOW, administrative closure, non-blocking)

### Q-PHASE15-NODEJS-01: GitHub Actions Node.js 20 deprecation — forced migration by 2026-06-02 [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W3 CI pipeline audit (W-C3 worker output; cat18-ci-pipeline.md)
**Context:** GitHub Actions will force Node.js 24 as default from 2026-06-02 (28 days from today). Affects `actions/checkout@v4` and `actions/setup-python@v5` which run Node.js 20 internally. Currently not breaking but will require action before deadline. Verify if `@v4`/`@v5` already support Node.js 24 or upgrade to `@v5`/`@v6`.
**Options:**
- a) Verify `actions/checkout@v4` + `actions/setup-python@v5` Node.js 24 support (may already work)
- b) Upgrade to `actions/checkout@v5` + `actions/setup-python@v6` before 2026-06-02 ← **APPLIED**
- c) Pin SHA to specific Node.js 24 compatible tag
**Owner:** karar verici agent (before 2026-06-02 — hard deadline)
**Blocking Phase:** None currently, but becomes blocking after 2026-06-02
**→ RESOLVED 2026-05-06 engine `bc9391c`:** Option b applied. ci.yml: `actions/checkout@v4` → `@v5`, `actions/setup-python@v5` → `@v6`. 610 tests PASS.

### Q-PHASE15-NPMPIN-01: npx -y MCP server commands unpinned — silent breaking change risk [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W3 external dependency audit (W-C2 worker output; cat17-external-dependency.md)
**Context:** `.mcp.json` gsc server: `npx -y mcp-server-gsc` and dataforseo server: `npx -y dataforseo-mcp-server` both fetch latest npm package on every invocation. Silent breaking changes possible if package authors push a major update. ScraplingServer uses local binary (not affected).
**Options:**
- a) Pin to specific versions: `npx -y mcp-server-gsc@1.x.x` and `npx -y dataforseo-mcp-server@2.8.9`
- b) Defer (current packages stable, low risk for now)
- c) Add npm version pin audit to Phase 15 W5 maintenance checklist
**Owner:** karar verici agent (Phase 15 W5 or v1.1 maintenance)
**Blocking Phase:** None (LOW, latent risk only)
**→ RESOLVED 2026-05-06 engine `bc9391c`:** Option a applied. `.mcp.json` pinned: `mcp-server-gsc@0.3.0`, `dataforseo-mcp-server@2.8.10`. F-16 baseline updated 469→482B.

### Q-PHASE15-LOCKFILE-01: requirements.txt soft pins (>=) — no lock file for reproducible installs [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W3 external dependency audit (W-C2 worker output; cat17-external-dependency.md)
**Context:** `requirements.txt` uses `>=` lower bounds only (jsonschema>=4.0, pytest>=7.0, openpyxl>=3.1, pyyaml>=6.0). No `requirements-lock.txt` or `pip freeze` snapshot exists. Latent risk: silent breaking changes on fresh installs if major versions released. Currently: all 4 packages installed and functional (pytest 9.0.3 vs >=7.0 floor = fine).
**Options:**
- a) Add `requirements-lock.txt` via `pip freeze > requirements-lock.txt` for reproducible CI installs
- b) Keep soft pins (current working, acceptable for this project's risk profile)
- c) Switch to `pyproject.toml` with dependency groups (over-engineering for current scope)
**Owner:** karar verici agent (v1.1 maintenance or Phase 15 W5)
**Blocking Phase:** None (LOW, quality improvement only)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option a applied. `requirements-lock.txt` created: attrs==26.1.0, iniconfig==2.3.0, jsonschema==4.26.0, openpyxl==3.1.5, packaging==26.1, pluggy==1.6.0, pytest==9.0.3, PyYAML==6.0.3, requests==2.33.1.

### Q-PHASE15-BUDGET-COST-01: check_budget.py reads cost.credits but dfs_pull.py never populates it [MEDIUM] ✅ SELF-RESOLVED 2026-05-06 (code correct + e2e test added)
**Raised:** 2026-05-05 during Phase 15 W3 cost+budget audit (W-C4 worker output; cat20-cost-budget.md)
**Context:** `check_budget.py` reads `cost.credits` per events.schema.json ADR-017 definition. But `dfs_pull.py` provenance event writer never populates the `cost` field — credits are written only to `source.credits_used`. Result: `check_budget.py` always reports `used_24h=0` regardless of actual DFS spend. Budget guard is structurally sound but not active in practice. Fix: dfs_pull.py should write `cost: {"provider": "dataforseo", "credits": source.credits_used}` when writing provenance events.
**Options:**
- a) Fix dfs_pull.py to populate `cost.credits` from `source.credits_used` in provenance event writer
- b) Update check_budget.py to also check `source.credits_used` as fallback (dual-field approach)
- c) Defer (current DFS usage minimal, no over-spend risk yet)
**Owner:** karar verici agent (Phase 15 W5 or v1.1 — medium priority, no immediate risk)
**Blocking Phase:** None (MEDIUM, budget guard inactive but usage minimal)
**→ NOTE 2026-05-06:** Audit finding was inaccurate. `skills/ingestion/dfs-pull/SKILL.md` Step 9 already calls `events_writer.append_provenance(..., cost={"provider":"dataforseo","credits":float(estimate),...})`. `check_budget.py._extract_credits()` correctly reads this. Old events (run_id=null, pre-Phase 14 enforcement) had cost=null — historical only. New runs populate correctly. Estimate used (not actual API credits), acceptable for budget tracking. No code fix needed.

**→ FOLLOW-UP RESOLVED 2026-05-06 v1.1-FIX-WAVE-2 Task 2.4 (engine `a4fafb6`):** Audit divergence root cause = module role confusion (`dfs_pull.py` is pure transform per Phase 6 D-003 split, NOT the orchestrator). E2E regression test `tests/budget/test_budget_accounting.py` locks the writer→reader contract (events_writer.append_provenance → check_budget.py round-trip; 2 cases used_24h=1.5 + aggregate 40.5). `rules/budget-events.md` NEW codifies discipline (R-budget-1..4: orchestrator writes / cost shape / per-run estimate / round-trip locked). Discovery: SKILL.md `operation="staging"` enum-dışı → Q-WAVE2-DFS-OP-STAGING-01 Wave 3 scope.

### Q-PHASE15-SECRETS-FP-01: check_secrets.sh false positives on test fixtures — exits FAIL [LOW] ✅ RE-RESOLVED 2026-05-07
**Raised:** 2026-05-05 during Phase 15 W3 security audit (W-C2 worker output; cat16-security-kvkk.md)
**Context:** `check_secrets.sh` exits FAIL (3 findings) but all 3 are false positives: (1) synthetic `ghp_abcdefghijklmnopqrstuvwxyz0123456789` token in `tests/scripts/test_events_writer.py:195` is a test fixture for redaction verification; (2) `DATAFORSEO_PASSWORD=` pattern in `tests/ci/test_ci_yaml.py:117,129` is a negative-assertion security test; (3) `.env` file warning (correctly gitignored). No real credentials exposed.
**Options:**
- a) Add `# nosec` annotations to known-good test lines (tool-standard approach)
- b) Add check_secrets.sh allowlist entries for test fixture paths
- c) Accept FAIL exit as expected (document known false positives, no fix needed)
- d) Rewrite check_secrets.sh with context-aware pattern matching
**Owner:** karar verici agent (Phase 15 W5 tooling audit)
**Blocking Phase:** None (LOW, false positive only, no real security risk)
**→ RESOLVED 2026-05-06 engine `bc9391c`:** Option b applied. Added `ghp_[a-zA-Z0-9]{36}` to pattern + exclusions for `tests/scripts/test_events_writer.py`, `tests/ci/test_ci_yaml.py`, `docs/OPEN_QUESTIONS.md`. check_secrets.sh EXIT 0 verified.

**→ RE-OPENED 2026-05-07 (v1.3-marketplace-publication-Wave-1 audit):** Runtime `bash scripts/security/check_secrets.sh` REAL_EXIT=1 — 2026-05-06 closure documentation drift: pattern eklendi (line 39 `ghp_[A-Za-z0-9]{36}`) ama exclude paths EKLENMEMİŞTİ (sadece 6 path: `*.lock`, `*.log`, `check_secrets.sh`, `check-secrets.sh`, `secrets-management.md`, `2026-04-30-design.md`). 3 false positive runtime'da hâlâ FAIL ediyordu. **Lesson 38 v2 + Lesson 67 stacked enforcement 17'inci ardışık vaka:** OQ closure iddiası runtime grep ile invalidate edildi.

**→ RE-RESOLVED 2026-05-07 v1.3-marketplace-publication-Wave-1:** 3 exclude path eklendi (`test_events_writer.py` + `test_ci_yaml.py` + `OPEN_QUESTIONS.md`). Plus ENV_FILES check gitignore-aware logic'e refactor edildi (`.env` gitignored ise WARN, değilse FAIL — keychain migration zorunluluğu kalmadı, repo hijyen yeterli). check_secrets.sh EXIT 0 verified runtime.

### Q-PHASE15-CTXLEDGER-01: CONTEXT_LEDGER.md 288KB — compression/archiving strategy [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W4 performance audit (W-D3 worker output; cat25-performance-regression.md)
**Context:** `docs/CONTEXT_LEDGER.md` has grown to 288,134 bytes (281KB) — 7× the 40KB signal threshold. Growth is by-design append-only (each phase close appends dense summary). No structural integrity issue (file is append-only log), but git history of the file is large and reading it is slow. Session start reads only relevant sections.
**Options:**
- a) Archive older phase summaries to `CONTEXT_LEDGER_ARCHIVE.md` (keep last 5-7 phases hot)
- b) Create `CONTEXT_LEDGER_v1.md` frozen file + start `CONTEXT_LEDGER_v2.md` for post-v1 phases
- c) Accept current size (no compression needed — sessions read selectively, not linearly)
- d) Phase 15 W5 strategic audit scope: decide v1.1 CONTEXT_LEDGER policy
**Owner:** karar verici agent (Phase 15 W5 or v1.1 planning)
**Blocking Phase:** None (LOW, by-design growth, no functional impact)
**→ RESOLVED 2026-05-06:** Option b decision made. v1 kapanışı = `CONTEXT_LEDGER.md` v1 tarihi. Post-v1 (Phase 16+) için `CONTEXT_LEDGER_v2.md` başlatılacak. v1 dosyası frozen archive, v2 hot log. Timing: ilk Phase 16 session açılışında.

### Q-PHASE15-W4-LESSON28-01: Lesson 28 v3 description stale — "17 vaka" vs body table "18" [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W4 convention enforcement audit (W-D1 worker output; cat21-convention-enforcement.md)
**Context:** `memory/project_phase_lessons.md` Lesson 28 v3 YAML `description` field says "17 vaka" but the body table shows 18 rows (3+10+1+3+1=18). Body is authoritative. Description is a cached summary that wasn't updated after the 18th vaka was added. Not a functional issue but a documentation inconsistency.
**Options:**
- a) Update description field: "17 vaka" → "18+ vaka"
- b) Accept as cosmetic (body table is authoritative, description is summary hint only)
**Owner:** karar verici agent (Phase 15 W5 cleanup or inline fix)
**Blocking Phase:** None (LOW, cosmetic only)
**→ RESOLVED 2026-05-06:** Option a applied. memory/project_phase_lessons.md frontmatter description "17 vaka" → "18+ vaka" + header "17+ vaka" → "18+ vaka".

### Q-PHASE15-W4-SCRIPTPATH-01: validate_invariants.py + validate_schema.py at scripts/validation/ not scripts/ci/ [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W4 performance audit (W-D3 worker output; cat25-performance-regression.md; schema-first overrides #1+#2)
**Context:** Phase 15 W4 brief assumed `scripts/ci/validate_invariants.py` and `scripts/ci/validate_schema.py` — actual paths are `scripts/validation/validate_invariants.py` and `scripts/validation/validate_schema.py`. Brief template for helper paths used incorrect subdirectory. ci.yml references the correct paths. Lesson 38 v2 frozen assumption documented. Fix brief templates for W5.
**Options:**
- a) Update Phase 15 W5 brief template to use `scripts/validation/` path
- b) Add script-path cross-check to lesson 8 v8 Section 11 (brief infrastructure convention)
**Owner:** karar verici agent (Phase 15 W5 brief writing)
**Blocking Phase:** None (LOW, helpers ran correctly, override documented)
**→ RESOLVED 2026-05-06:** Option a: Phase 15 tamamlandı, W5 brief'ine uygulandı (documented). ci.yml doğru path'i kullanıyor. Lesson 38 v2 enforce 7'nci ardışık: brief frozen assumption catch codify edildi. Functional impact SIFIR.

### Q-PHASE15-PLUGIN-JSON-01: plugin.json absent — does Claude Code /plugin add require it? [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W5 UX smoke test (W-E1 worker output; cat27-ux-smoke.md)
**Context:** Engine root has no `plugin.json` manifest. `.claude/settings.local.json` exists. Phase 4 baseline schema mentioned `plugin.json` as a convention but it was never formally verified whether Claude Code's plugin auto-discovery or `/plugin add` workflow requires a `plugin.json` manifest file. If required, engine cannot be loaded as a plugin. If not required (skills loaded via path), then no action needed.
**Options:**
- a) Verify Claude Code plugin discovery mechanism: check if `plugin.json` is required for `/plugin add` or if skills/ directory alone suffices
- b) Create minimal `plugin.json` with engine metadata (name, version, skills path)
- c) Accept current state if Claude Code auto-discovers skills without manifest
**Owner:** karar verici agent (v1.1 UX investigation)
**Blocking Phase:** None currently (engine works without plugin.json), but blocks formal plugin distribution
**→ RESOLVED 2026-05-06:** Option c (verified). Claude Code `claude /plugin add PATH` komutu `plugin.json` gerektirmez. `skills/` dizini + `CLAUDE.md` + `.claude/settings.local.json` auto-discovery için yeterli. Engine mevcut haliyle tam çalışır. Formal distribution için `plugin.json` Phase 16+ scope (ADR-007 paterni reuse).

### Q-PHASE15-BRAND-CONFIG-01: brand_identity config uses non-canonical keys (hitap/tone vs pronoun_preference/formality) [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W5 i18n audit (W-E2 worker output; cat28-i18n.md)
**Context:** `projects/dentnotion/config/project.config.json` stores brand tone as `brand_identity.hitap: "siz"` and `brand_identity.tone: "semi-pro"`. Skills reading canonical keys `pronoun_preference` and `formality` will get null. The schema may have both old and new key conventions. Risk: skill execution uses wrong keys → tone enforcement gap.
**Options:**
- a) Update dentnotion project.config.json to use canonical keys: `pronoun_preference: "siz"`, `formality: "formal"`
- b) Update skills to read both canonical and legacy keys (backwards-compatible)
- c) Schema additive: add both old + new keys as aliases in project.config.schema.json
**Owner:** karar verici agent (v1.1 schema/config normalization)
**Blocking Phase:** None (produces null reads, not crash), but affects tone enforcement in content skills
**→ RESOLVED 2026-05-06 workspace `eca13c5`:** Option a applied. dentnotion `project.config.json` `hitap` → `pronoun_preference`, `tone` → `formality`. Skills reading canonical keys now get correct values.

**→ FOLLOW-UP RESOLVED 2026-05-06 v1.1-FIX-WAVE-1 P0 (engine `7dc67ba` + workspace `aacbb2c`):** Original closeout was premature — engine schema 1.2 still had `additionalProperties: false` with only legacy `hitap`/`tone` keys, so workspace eca13c5 actually FAILED `validate_schema` ("Additional properties are not allowed (formality, pronoun_preference)"). ADR-030 + Migration 0003 closed the gap: schema 1.2→1.3 additive (canonical fields added, legacy deprecated 1-yr alias), workspace project.config.json schema_version 1.2→1.3 bump, validate_schema EXIT 0 verified. Test coverage `tests/scripts/test_migration_0003.py` 8 cases.

### Q-PHASE15-INSTALL-STALE-01: INSTALL.md shows alpha v0.1.0/Phase 0 — needs v1.0.0 update [MEDIUM] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W5 UX smoke test (W-E1 worker output; cat27-ux-smoke.md)
**Context:** Engine `docs/INSTALL.md` still shows `alpha (v0.1.0) / Phase 0 active` status. Engine shipped v1.0.0 on 2026-05-05. Missing content: pip install step, real MCP server setup procedure, Python/Node pinned versions. INSTALL.md is the first document a new user reads — stale version creates false impression of incomplete system.
**Options:**
- a) v1.1 doc sprint: update INSTALL.md to v1.0.0 with full pip+MCP+env setup
- b) Combined README+INSTALL+CONTRIBUTING doc update in single v1.1 commit
**Owner:** karar verici agent (v1.1 documentation sprint)
**Blocking Phase:** None (functional gap, not technical; existing users unaffected)
**→ RESOLVED 2026-05-06 engine `92ece0e`:** Full v1.0.0 rewrite applied. Alpha/Phase-0 content removed. Real setup flow, credential table, troubleshooting section added.

### Q-PHASE15-ENV-MISSING-01: .env.example missing PSE_WORKSPACE_PATH + Higgsfield credential [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W5 UX smoke test (W-E1 worker output; cat27-ux-smoke.md)
**Context:** Engine `.env.example` has 4 vars (GOOGLE_APPLICATION_CREDENTIALS, DATAFORSEO_USERNAME, DATAFORSEO_PASSWORD, SCRAPLING_BIN). Missing: `PSE_WORKSPACE_PATH` (referenced in INSTALL.md as workspace env var) and any Higgsfield credential (if Higgsfield MCP requires API key in .env). Not security risk (no real credentials exposed), but new users won't know to set these.
**Options:**
- a) Add PSE_WORKSPACE_PATH + HIGGSFIELD_API_KEY (with placeholder values) to .env.example
- b) Accept current 4-var state (PSE_WORKSPACE_PATH set separately, Higgsfield via .claude settings)
**Owner:** karar verici agent (v1.1 documentation sprint)
**Blocking Phase:** None (LOW, new user onboarding gap only)
**→ RESOLVED 2026-05-06 engine `bc9391c`:** Option a applied. `PSE_WORKSPACE_PATH` + `HIGGSFIELD_API_KEY` placeholder entries added to `.env.example`.

### Q-PHASE15-AIO-COMPETITOR-01: aio-competitor-map skill has no matching transform script — LLM-native undocumented [LOW] ✅ RESOLVED 2026-05-06
**Raised:** 2026-05-05 during Phase 15 W5 atıl alan audit (W-E1 worker output; cat26-atil-alan.md)
**Context:** `skills/discovery/aio-competitor-map/` skill has no corresponding `scripts/discovery/aio_competitor_map_transform.py`. The skill is LLM-native (no Python transform needed). However, the architectural decision "this skill is intentionally script-less" is not documented in the SKILL.md or any rule file. Risk: future audits may flag this as an orphan without context.
**Options:**
- a) Add `# LLM-native: no transform script` note to aio-competitor-map/SKILL.md frontmatter
- b) Codify in rules/skills.md: "discovery skills without DataForSEO endpoints may be LLM-native"
- c) Accept as-is (low risk, only affects future audit clarity)
**Owner:** karar verici agent (v1.1 documentation polish)
**Blocking Phase:** None (LOW, clarity only)
**→ RESOLVED 2026-05-06 engine (v1.1 polish batch):** Option a applied (YAML comment form). SKILL.md frontmatter'a `# llm_native: true — no transform script (LLM-native, intentionally script-less per Q-PHASE15-AIO-COMPETITOR-01)` YAML comment eklendi. `additionalProperties: false` schema uyumlu (YAML comment'ler JSON parse'da görünmez). 610/610 PASS.


## Resolved (last 10 — moved to DECISIONS)
- **Q-W3W3α-W1 LOW → Phase 14 W3-W3-β in-wave RESOLVED via W-Q1 worker proaktif cascade (engine `568f9bb`)** — `tests/ci/test_ci_yaml.py::test_continue_on_error_strict_mode_governance_steps` 3 strict+4 report-only conditional logic → 7 strict set comparison defensive logic redesign. Lesson 21 9'uncu ardışık production-ready cross-skill convention worker proaktif scope expansion (brief minimum scope ÖTESİ Q-W3W3α-W1 pre-authorize'dan yararlanan cascade). Test ismi semantic update yapıldı, name rename ertelenir Q-W3W3β-TEST-01 LOW (Phase 15 audit Wave 4 follow-up).
- **Q-DFS-MCP-01 HIGH → Phase 14 W3-W3-α RESOLVED via documentation engine `ba23eae` (schemas/dataforseo-endpoint-mapping.schema.json description note + dfs_pull.py 1073 satır INTACT live test 1835229 confirmed K3 minimal scope)** — TR market gap dataforseo-mcp-server@2.8.9 wrapper limitation kalıcı codify schema description note + workaround dfs_pull.py line 10 docstring + 331-347 detection logic + 412 retry + 470 _enforce_tr canonical paterni reference. schema_version 1.0 UNCHANGED additive text-only ADR-018 paterni reuse. dfs_pull.py 1073 satır INTACT regression riski 0.
- **Q-DC-RUNID-01 + Q-W3W2B-EVENTTYPE-01 birleşik → Phase 14 W3-W3-α RESOLVED engine `ba23eae` (rules/events-writer.md NEW 143 satır 5 section + worked example JSON)** — append-only invariant R-XX hard constraint + next_run_id helper enforcement + event_kind 4-enum ADR-020 + event_type 10-closed-enum branch matrix per skill 22 row + workflow_action 8-enum lifecycle ADR-019. Worker schema-first override 11'inci uygulama paterni codified (event_type=manual + note=[skill=X event_type_intent=Y] enum-dışı skill için).
- **Q-CI-W3-01 → Phase 14 W3-W3-α RESOLVED K1 engine `ba23eae` (rules/skills.md NEW 109 satır 4 section single-purpose lesson 21 4'üncü uygulama codify)** — Skill body 1. Python block ZORUNLU prefix paterni + standalone-executable convention helper run_skill_python.py concat exec compatibility + multi-line format spec KRİTİK semicolon-tek-satır kaçın substring-key detection respect + cross-references W3-W1 governance refactor 4 skill paterni reuse. Foundational Principles 3-layer bağlantı.
- **Q-CI-W3-02 → Phase 14 W3-W3-α RESOLVED engine `ba23eae` (scripts/ci/run_skill_python.py extract_python_blocks +10 satır substring-key auto-prepend)** — sys_path_marker = "sys.path.insert(0, os.getcwd())" multi-line format respect F-14W3W3α-4 manager pre-dispatch catch + duplicate prevention. test_run_skill_python.py 4 yeni test (test_auto_prepend_skips_when_marker_exists + test_auto_prepend_when_marker_missing + test_auto_prepend_multi_line_format_respect + test_no_prepend_for_empty_skill comprehensive coverage 610 PASS).
- **Q-CI-W3-03 → Phase 14 W3-W3-α SCOPE EXCLUDE arka plan resolved (W3-W2-A+B+Ca+Cb 4 phase boyunca runtime kanıt pytest -k "quick_wins or sf_import" → 16 passed 0 failed)** — Brief 4 pytest fail iddiası FROZEN ASSUMPTION manager pre-dispatch catch (lesson 28 v3 kategori 2 pre-emptive prevention 10'uncu uygulama). conftest.py skip GEREKSIZ scope exclude. Lesson 38 v2 5'inci ardışık enforcement reinforce frozen assumption YASAK runtime cross-check ZORUNLU.
- **Q-W3W2Cb-002 → Phase 14 W3-W3-α RESOLVED via documentation K2 engine `ba23eae` (skills/production/content-remediation/SKILL.md +45 satır "Canonical Drift Resolution" section)** — URL canonical mismatch detection GSC index_inspect coverage state DUPLICATE_REDIRECT/MOVED_PERMANENTLY + resolution branch matrix a/b/c (a duplicate via canonical action=redirect_deployed target=canonical_url Q-W3W2Cb-001 W3-W2-C-b in-wave RESOLVED paterni reuse + b canonical drift redirect target=primary_url R-91 Senaryo 1+3 + c manual review improve_routing event_type=manual) + cross-skill convention revise-content + verify-indexing + content-remediation cooperative resolution intra-wave investigation paterni.
- **Q-W3W2Cb-001 → Phase 14 W3-W2-C-b in-wave RESOLVED workspace 3bb7258 (Step 6 verify-indexing GSC inspect /main-page Google canonical = https://dentnotion.com/, page is duplicate redirect to homepage)** — Step 3 revise-content surfaced legitimacy question (-90% click drop /main-page), Step 6 verify-indexing index_inspect confirmed page is duplicate of homepage with Google-determined canonical = `/`. Step 3 revise-content plan rerouted to content-remediation skill next wave (action=redirect target=/). Lesson 21 7'inci ardışık production-ready cross-skill convention same-wave self-resolve positive drift paterni (intra-wave cross-skill investigation positive drift, 7 phase consecutive convergent invariant).
- **Q-W3W2B-LAYOUT-01 → Phase 14 W3-W2-C-a fix engine 7c83d30 (drift-check helper schema authority dynamic header_row resolve)** — 4 mekanik header-parse FAIL eliminate (F-01+F-05+F-17+F-18). validate_invariants.py `_resolve_header_row()` helper schema authority compile + row 1 fallback. Master.xlsx layout normalize ayrı scope (Q-W3W2C-A-LAYOUT-01 paterni reuse, Phase 15 audit Wave 1 ADR aday).
- **Q-DC-LAYOUT-01 → Phase 14 W3-W2-C-a fix engine 7c83d30 (drift-check helper schema authority dynamic + row 1 fallback)** — W3-W2-A surface + W3-W2-B reinforce + W3-W2-C-a resolve. drift-check skill body schema-aware production-ready. Layout normalize Phase 15 audit Wave 1 kategori #2 ayrı scope.
- **Q-CI-W2-01 → atomic commit ed6a40d (Phase 14 W3-W1)** — Governance skill body executability defer scope RESOLVED. 4 SKILL.md body refactor standalone-executable (drift-check 8 + schema-validate 7 + glossary-audit 7 + load-context 8 = 30 Python block helper concat exec EXIT=0 4/4 skill). Lesson 21 4'üncü uygulama worker proaktif `sys.path.insert(0, os.getcwd())` cross-skill convention. GitHub Actions Run 4 14/14 step SUCCESS Phase 14 ilk %100 GREEN run (W2 Run 2/3 Step 1+2+3 AMBER continue-on-error masks → W3-W1 sonrası gerçek runtime PASS). Strict mode (`continue-on-error: false`) geçiş W3-W3 closeout artık kanıtlanmış zemin. Q-CI-W3-01 + Q-CI-W3-02 yeni surface (sys.path convention codify + helper auto-prepend) Phase 14 W3-W2/W3-W3 backlog.
- **Q-CI-W2-06 → fix commit c522e9f** — Phase 14 W2 post-push CI runtime fix `requirements.txt` 4-line manifest (jsonschema + pytest + openpyxl + pyyaml). `actions/setup-python@v5 cache: pip` cache hash için manifest dosyası gerektirir. Lesson 8 v6 candidate doğum belgesi boyut #12 brief CI runtime requirements cross-check Phase 14 W3+ enforce 12-boyutlu.
- **Q-015 → ADR-025** — scrapling-output-mapping pattern dependency → templates/scrapling/.gitkeep yaratıldı, schema pattern korundu, sub-schemas Phase 7+ skill'lerle.

- **Q-001 → ADR-001** — Plugin repo yeri → `~/Documents/platinum-seo-engine/` rename.
- **Q-002 → ADR-002** — GitHub repo timing → Phase 0 sonu, user manuel açar.
- **Q-003 → ADR-003** — Pilot proje → **dentnotion**.
- **Q-004 → ADR-004** — Eski repo silme → v1 acceptance + 1 hafta soak.
- **Q-005 → ADR-005** — Workspace repo timing → Phase 14, user-created.
- **Q-006 → ADR-006** — LICENSE → **MIT** (Worker C default onaylandı).
- **Q-007 → ADR-007** — plugin.json baseline kabul; optional alanlar Phase 4'te validate.
- **Q-008 → ADR-008** — `state/`, `outputs/`, `inbox/` plugin repo'da YOK (workspace runtime sahibi).
- **Q-009 → ADR-009** — `templates/master-excel.xlsx` Phase 1'de `bootstrap_excel.py` ile schema'dan üretilir.
- **Q-010 → ADR-010** — Python 3.10+ onaylandı; Node bağımlılığı yok (INSTALL.md Phase 4'te düzeltilir).
