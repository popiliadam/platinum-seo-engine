# Phase 6 (FINAL) — Docs / Skills / Templates / Cleanup — Worker Brief

## 0. READ FIRST (worker onboarding)

- Fresh worker session. Engine repo: `/Users/apple/Documents/platinum-seo-engine`. Mostly engine;
  ONE small workspace-docs sub-task at the end (Part WS) on a SEPARATE workspace branch.
- Invoke `superpowers:test-driven-development` (for the lockable parts) + `superpowers:verification-before-completion`.
- **Branch:** `git checkout -b fix/codex-audit-phase-6-cleanup` off `main` (confirm `git log --oneline -3`
  shows the Phase 5 merge `a3ee596`). Never commit to main, never push.
- Hard rules: NO subagents (Task/Agent fail here); atomic commits; never commit
  `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`; preserve untracked planning docs; **never `rm` without it being
  explicitly safe** (see P3-02 — do NOT delete files, prefer gitignore/packaging verification).
- **Baseline:** `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`
  must stay ≥ **1540 passed, 8 skipped** + your new tests.
- These are low-risk docs/cleanup fixes. Where a finding is lockable by a count/contract test, ADD that
  test so the drift can't return (audit's intent).

## 1. GOAL + findings (the last 10 + 2 carry-overs)

Make the docs, skills, templates, and dependency story tell the truth, and lock the count/contract
claims with tests. Findings: P1-12, P2-01, P2-02, P2-03, P2-04, P2-06, P2-07, P3-01, P3-02, P3-03.

## 2. EVIDENCE (verified) + fixes

- **P1-12** `skills/meta/brand-onboarding/SKILL.md`: references project-config schema `1.2` (stale → 1.5);
  references old `projects/{slug}/config/` path (→ `projects/{slug}/project.config.json`);
  `scripts/meta/brand_onboarding_discovery.py:79` hardcodes `2026 - founding_year`.
  DECISION D3: KEEP `status: active`; fix the stale schema-version + path refs; replace hardcoded `2026`
  with the current UTC year (`datetime.now(timezone.utc).year`); add/confirm a clear "staging-only — real
  discovery deferred to Phase 14" banner. (Do NOT wire real discovery — that's roadmap.)
- **P2-02** (engine doc counts; README is already CORRECT at 45/18/6/4/21 — do NOT change it):
  `docs/GLOSSARY.md:13` says "28 CSR rule" → actual is 31 (cross-sheet-invariants.json `rules`).
  `docs/ARCHITECTURE.md:51-64` Phase Roadmap lists phases as "planned" despite v1.9.4 production-ready →
  update status language (mark foundation/skill phases complete; keep it honest).
  CARRY-OVERS: `skills/production/generate-images/SKILL.md` MCP-boundary table says ".mcp.json (3 servers:
  gsc, dataforseo, ScraplingServer)" → it's 4 now (+ `sf` HTTP). `scripts/state/dump_workspace.py` module
  docstring (~line 14) says "bound slug okunur" → now reads `active_project`.
- **P3-03** (stale counts in comments): `tests/ci/test_ci_yaml.py:61` + `tests/schemas/test_events_schema_event_type_enum_v1_1.py:17`
  comments say "43 SKILL.md"/"43 skills" → 45. (These are comments; update the text.)
- **P2-03** template dialects: `scripts/reporting/render_template.py` uses `string.Template` `$var`;
  content templates under `templates/content/*.template.{md,html}` use `{{PLACEHOLDER}}`. No manifest says
  which renderer owns which template → a template rendered by the wrong renderer leaves placeholders
  unresolved without failing. Fix: add a small manifest (e.g. `templates/manifest.json` or a documented
  convention) declaring each template family's dialect, + a test that every template's placeholders match
  its declared dialect (and that `render_template`-targeted templates contain no `{{...}}`).
- **P2-04** requirements drift: `requirements.txt` (jsonschema, pytest, openpyxl, pyyaml, piexif, httpx — NO
  `requests`); `requirements-lock.txt` (Python 3.14) pins `requests==2.33.1`. Engine scripts use `httpx`
  (`scripts/util/sf_mcp_client.py`); only skill SNIPPETS mention `requests`. Fix: reconcile — determine if
  `requests` is a real transitive/runtime need; if not, document why it's in the lock (or regenerate the
  lock), and document the lock-generation command + Python target. Add a dependency-drift note/test if lock
  is authoritative. (Do NOT add `requests` to base unless a real engine script imports it.)
- **P2-06** hook-helper-script wiring: `scripts/hooks/{check_append_only.sh,check_naming.py,validate_before_write.py,check_excel_writer.py}`
  exist but are NOT referenced by any `hooks/*.json` (they are CI/pre-commit-only). Fix: document explicitly
  which scripts are CI-only vs runtime hooks (a short section in docs or a header in each), + add/confirm a
  test (`test_hook_scripts_exist`-style) asserting the intended runtime hooks are present and the CI-only
  scripts exist where expected.
- **P2-07** secret-policy wording: `scripts/security/check_secrets.sh` WARNs (not fails) on gitignored `.env`
  → behavior is "zero COMMITTED/CHANGED secrets", not "zero secrets on disk". Fix: align the policy WORDING
  (README/docs/script header) to "zero committed/changed secrets" (or make ignored local secrets fail if
  truly zero-on-disk is intended — but the warn behavior is deliberate, so prefer the wording fix).
- **P3-01** historical SF docs: `docs/WORKFLOWS.md`, `docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md`,
  `docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md` carry old SF MCP call shapes. Fix:
  add a clear "HISTORICAL — see current SF contract in commands/pseo-sf-crawl.md + sf-crawl-orchestrator
  SKILL" banner at the top of each (they are dated design docs; label, don't rewrite).
- **P3-02** `templates/.DS_Store`: exists locally, gitignored (never committed). Fix: confirm `.gitignore`
  covers `.DS_Store` (engine-wide) AND that packaging uses `git archive`/tracked-files-only (so it can never
  ship). DO NOT `rm` it (macOS regenerates it; deletion needs no action if gitignore + git-archive packaging
  hold). If `.gitignore` does NOT cover it, add the ignore entry.
- **P2-01** (WORKSPACE repo docs): `/Users/apple/Documents/platinum-seo-workspace/README.md` references
  `projects/<slug>/config/` (→ `project.config.json`) and unprefixed commands `/quick-wins`,
  `/content-decay`, `/verify-indexing` (→ `/pseo-quickwin`, `/pseo-content-decay`, and the real verify
  command — check engine `commands/`: there is `pseo-content-decay`, `pseo-quickwin`; confirm the indexing
  one's real name, e.g. via `ls commands/`). `CLAUDE.md` MCP-server set differs from current `.mcp.json`
  (4 servers). Fix: align workspace README/CLAUDE to current engine command names + layout + MCP set.

## 3. DECISIONS already made

- P1-12 = D3: keep active, fix stale refs + dynamic year + staging banner.
- README engine counts are ALREADY correct — do not touch them; only GLOSSARY/ARCHITECTURE/comments + the 2 carry-overs.
- P3-02: do NOT delete files; gitignore + packaging verification only.

## 4. TASKS (group into ~7 commits; TDD where a test locks the fix)

- [ ] **C1 (P1-12):** fix brand-onboarding SKILL.md refs (1.2→1.5, config/ path) + `brand_onboarding_discovery.py`
  dynamic year + staging banner. If a test asserts the old schema ref, update it. Commit:
  `fix(skills): refresh brand-onboarding stale refs + dynamic year + staging banner (P1-12)`.
- [ ] **C2 (P2-02 + P3-03 + carry-overs):** RED-extend `tests/docs/test_count_consistency.py` to mechanically
  assert: skills count (find SKILL.md == 45), CSR/invariants count (cross-sheet-invariants `rules` == 31),
  schemas count, AND that GLOSSARY/ARCHITECTURE/CI comments contain no stale "28 CSR"/"43 skill"/"3 servers"
  literals. Then GREEN: fix GLOSSARY (28→31), ARCHITECTURE roadmap status, generate-images "3 servers"→4
  (list gsc/dataforseo/ScraplingServer/sf), dump_workspace docstring (slug→active_project), and the two
  "43" comments → 45. Commit: `fix(docs): correct stale counts + lock via count-consistency test (P2-02, P3-03)`.
- [ ] **C3 (P2-03):** add the template dialect manifest + a test that each template's placeholders match its
  declared renderer dialect. Commit: `feat(templates): declare placeholder dialect per template + test (P2-03)`.
- [ ] **C4 (P2-04):** reconcile requirements vs lock; document lock-gen command + Python target; add a drift
  note/test if lock is authoritative. Commit: `chore(deps): reconcile requirements/lock + document generation (P2-04)`.
- [ ] **C5 (P2-06):** document CI-only vs runtime hook scripts + add/confirm the hook-scripts-exist test.
  Commit: `docs(hooks): document CI-only vs runtime hook scripts + test presence (P2-06)`.
- [ ] **C6 (P2-07 + P3-01 + P3-02):** secret-policy wording → "zero committed/changed"; HISTORICAL banners on
  the 3 SF docs; verify `.gitignore` covers `.DS_Store` + packaging uses git-archive (add ignore entry if
  missing). Commit: `docs: clarify secret policy wording + label historical SF docs + confirm DS_Store ignore (P2-07, P3-01, P3-02)`.
- [ ] **Part WS (P2-01) — WORKSPACE repo, SEPARATE branch+commit:**
  `cd /Users/apple/Documents/platinum-seo-workspace && git checkout -b fix/codex-audit-workspace-docs`.
  Align README/CLAUDE (config path, prefixed command names, MCP set) to the current engine. Stage ONLY the
  doc files (README.md/CLAUDE.md), never runtime artifacts. Commit in the WORKSPACE repo:
  `docs: align workspace README/CLAUDE with current engine commands + layout (P2-01)`. Never push.

## 5. TEST GATE

```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m pytest tests/docs tests/ci tests/schemas tests/reporting -q   # incl. extended count-consistency + template-dialect
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   # >= 1540/8 + new
# verify the count claims mechanically
echo "skills: $(find skills -name SKILL.md | wc -l) (expect 45) | invariants: $(python3 -c "import json;print(len(json.load(open('schemas/cross-sheet-invariants.json'))['rules']))") (expect 31)"
# workspace docs (Part WS): command names referenced exist in engine commands/
```

## 6. OUT OF SCOPE

- Do NOT change README engine counts (already correct). Do NOT wire real brand-onboarding discovery (Phase 14).
- Do NOT delete files (P3-02 = gitignore/packaging only). Do NOT close more schema additionalProperties.
- Do NOT add `requests` to base requirements unless a real engine script imports it.
- Do NOT push either repo.

## 7. COMPLETION REPORT (return to manager)

```
# Phase 6 Completion Report
- Engine branch: fix/codex-audit-phase-6-cleanup | Base: a3ee596 | Head: <sha>
- Workspace branch (Part WS): fix/codex-audit-workspace-docs | Base: <ws sha> | Commit: <sha>
- Status: DONE | PARTIAL | BLOCKED
- Findings closed: [P1-12, P2-01, P2-02, P2-03, P2-04, P2-06, P2-07, P3-01, P3-02, P3-03] + carry-overs (generate-images servers, dump_workspace docstring)
- Commits (engine ~6 + workspace 1): <sha> <msg> ; ...
- Tests: full suite = "<N passed, M skipped>"; new/extended tests: [files]; all green? Y/N
- P2-02/P3-03: count-consistency test now locks skills=45 / invariants=31 / no stale literals? Y
- P1-12: refs 1.2→1.5 + config/→project.config.json + dynamic year + staging banner? Y
- P2-03: template dialect manifest + test? Y
- P2-04: requirements/lock reconciled + documented? (what did you decide re requests?)
- P2-06: CI-vs-runtime hook scripts documented + test? Y
- P2-07: policy wording → "zero committed/changed"? Y
- P3-01: 3 SF docs labeled historical? Y    P3-02: .DS_Store gitignored + packaging safe (no rm)? Y
- P2-01 (workspace): README/CLAUDE aligned; only doc files staged? Y
- Deviations / blockers: <...>
- git diff --stat (engine) + (workspace): <paste both>
```
