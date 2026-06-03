You are a WORKER session executing Phase 6 (FINAL) — Docs / Skills / Templates / Cleanup of the Codex audit remediation for the Platinum SEO Engine. Fresh full context — do all work yourself here. These are low-risk docs/cleanup fixes; lock count/contract claims with tests where possible.

AUTHORITATIVE SPEC: Open and follow this file EXACTLY, task by task (full evidence + fixes + commit grouping):
  docs/superpowers/plans/codex-audit/phase-6-cleanup.md
Also skim the "Guardrails" + "Completion Report" sections of:
  docs/superpowers/plans/codex-audit/MANAGER.md
Do not explore the rest of the repo — these files plus the paths they name are complete.

MISSION: Make docs/skills/templates/deps tell the truth, locked by tests where applicable. Close the last 10 findings + 2 carry-overs:
- P1-12: brand-onboarding SKILL.md stale refs (schema 1.2→1.5; projects/{slug}/config/ → project.config.json); brand_onboarding_discovery.py hardcodes 2026-founding_year → dynamic UTC year; add a clear "staging-only, real discovery deferred to Phase 14" banner. KEEP status: active (decision D3). Do NOT wire real discovery.
- P2-02: docs/GLOSSARY.md "28 CSR rule" → 31; docs/ARCHITECTURE.md roadmap lists phases "planned" despite v1.9.4 → honest status. CARRY-OVERS: generate-images/SKILL.md ".mcp.json (3 servers...)" → 4 (+ sf); dump_workspace.py docstring "bound slug" → active_project. README engine counts are ALREADY CORRECT (45/18/6/4/21) — do NOT touch README.
- P3-03: "43 SKILL.md"/"43 skills" comments in tests/ci/test_ci_yaml.py + tests/schemas/test_events_schema_event_type_enum_v1_1.py → 45.
- P2-03: render_template.py uses string.Template $var; content templates use {{PLACEHOLDER}}; no manifest. Add a manifest declaring each template family's dialect + a test that placeholders match the declared renderer.
- P2-04: requirements.txt has no requests; requirements-lock.txt (Py 3.14) pins requests==2.33.1; engine uses httpx. Reconcile + document lock-gen command + Python target; do NOT add requests to base unless a real script imports it.
- P2-06: scripts/hooks/{check_append_only.sh,check_naming.py,validate_before_write.py,check_excel_writer.py} exist but are NOT wired in hooks/*.json (CI-only). Document CI-only vs runtime + add/confirm a hook-scripts-exist test.
- P2-07: check_secrets.sh WARNs (not fails) on gitignored .env → policy is "zero committed/changed secrets", not "zero on disk". Fix the WORDING (README/docs/script header).
- P3-01: docs/WORKFLOWS.md + docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md + docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md carry old SF call shapes → add a HISTORICAL banner at the top of each (label, don't rewrite).
- P3-02: templates/.DS_Store exists, gitignored. Do NOT rm it — confirm .gitignore covers .DS_Store + packaging uses git-archive/tracked-files-only; add the ignore entry only if missing.
- P2-01 (WORKSPACE repo): README references projects/<slug>/config/ + unprefixed /quick-wins,/content-decay,/verify-indexing; CLAUDE.md MCP set is stale. Align to current engine command names + layout + 4-server MCP set.

DECISIONS (do NOT re-litigate):
- D3: brand-onboarding stays active; fix refs + dynamic year + banner only.
- README engine counts already correct — leave them.
- P3-02: gitignore/packaging verification only — NEVER delete files.

HARD RULES:
1. Do NOT spawn subagents / Task / Agent tools — they fail here ("Prompt is too long"). Work inline.
2. Invoke superpowers:test-driven-development for the lockable parts (count-consistency, template-dialect, hook-scripts) + superpowers:verification-before-completion before claiming done.
3. Engine branch: git checkout -b fix/codex-audit-phase-6-cleanup off main (confirm git log --oneline -3 shows the a3ee596 Phase 5 merge). Never commit to main, never push.
4. ~6 engine commits grouped per the brief §4 (C1..C6) + 1 SEPARATE workspace commit (Part WS).
5. NEVER `rm` any file (P3-02 is gitignore/packaging only). NEVER commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md. Preserve untracked planning docs.
6. Baseline must stay green: PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q  >= 1540 passed, 8 skipped + your new tests.
7. Part WS is the ONLY workspace-repo work: do it on a SEPARATE workspace branch (fix/codex-audit-workspace-docs), stage ONLY README.md/CLAUDE.md (no runtime artifacts), commit in the workspace repo, never push. Keep engine and workspace commits in their own repos (never mixed).

WORK PLAN (full detail in the brief §4):
- C1 (P1-12): brand-onboarding refs + dynamic year + staging banner.
- C2 (P2-02 + P3-03 + carry-overs): EXTEND tests/docs/test_count_consistency.py to lock skills=45 / invariants=31 / no stale "28 CSR"/"43 skill"/"3 servers" literals (RED), then fix GLOSSARY/ARCHITECTURE/generate-images/dump_workspace docstring/the two "43" comments (GREEN).
- C3 (P2-03): template dialect manifest + per-template dialect test.
- C4 (P2-04): reconcile requirements/lock + document.
- C5 (P2-06): document CI-vs-runtime hook scripts + presence test.
- C6 (P2-07 + P3-01 + P3-02): secret-policy wording + 3 historical banners + .DS_Store gitignore/packaging check.
- Part WS (P2-01): workspace README/CLAUDE alignment on a separate workspace branch.

FINAL GATE (all must hold):
- python3 -m pytest tests/docs tests/ci tests/schemas tests/reporting -q   (all pass)
- PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   (>= 1540/8 + new)
- mechanical count check: find skills -name SKILL.md | wc -l == 45 ; cross-sheet-invariants rules == 31

WHEN DONE, output a paste-ready COMPLETION REPORT (template in the brief §7): engine branch + base/head; workspace branch + commit; status; findings closed + carry-overs; commit shas+messages (engine + workspace); full-suite result + new/extended tests + all-green Y/N; the per-finding confirmations in §7 (incl. what you decided re requests for P2-04); deviations; blockers; git diff --stat for BOTH repos.

BEGIN NOW: invoke superpowers:test-driven-development, open the brief, create the engine branch (verify base shows a3ee596), do C1..C6, then Part WS on the separate workspace branch. This is the FINAL phase — after it, all 31 findings are addressed (30 fixed + P2-08 refuted).
