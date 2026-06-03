You are a WORKER session executing **Phase 2 — Workspace Contract (ENGINE ONLY)** of the Codex
audit remediation for the Platinum SEO Engine. Fresh full context — do all work yourself here.

AUTHORITATIVE SPEC: Open and follow this file EXACTLY, task by task (full code + per-task TDD steps):
  docs/superpowers/plans/codex-audit/phase-2-workspace.md
Also skim the "Guardrails" + "Completion Report" sections of:
  docs/superpowers/plans/codex-audit/MANAGER.md
Do not explore the rest of the repo — these files plus the paths they name are complete.

MISSION: Make the workspace state contract honest. Close:
- P0-02: scripts/state/dump_workspace.py reads legacy "slug"; live shared/active.json uses
  "active_project" → manager summary errors unless --project is passed. Read active_project first,
  fall back to legacy slug with a stderr warning.
- P0-04 (ENGINE part only): schemas/portfolio-config.schema.json caps active_projects at 8; the live
  portfolio has 10. Raise maxItems 8→12 (documented soft cap).
- P2-05 (doc): clarify config schema_version (1.5) is distinct from engine release version (v1.9.4).

DECISION D2 (do NOT re-litigate): raise maxItems to 12 with a comment that it is a soft cap, not a
hard product limit. dump_workspace falls back to legacy slug with a warning.

HARD RULES:
1. Do NOT spawn subagents / Task / Agent tools — they fail in this project ("Prompt is too long").
   Work inline.
2. Invoke superpowers:test-driven-development (red → confirm fail → minimal change → confirm pass →
   commit). Then superpowers:verification-before-completion before claiming done.
3. Branch: git checkout -b fix/codex-audit-phase-2-workspace. Base on main IF Phase 1
   (fix/codex-audit-phase-1-governance) is already merged to main; ELSE base on
   fix/codex-audit-phase-1-governance. Check git log --oneline -3 first and note which in your report.
   Never commit to main, never push.
4. Exactly 3 atomic commits (P0-02, then P0-04, then P2-05) — messages in the brief.
5. Engine repo ONLY (/Users/apple/Documents/platinum-seo-engine).
6. *** YOU MUST NOT MODIFY THE WORKSPACE REPO *** (/Users/apple/Documents/platinum-seo-workspace).
   You only READ it for the read-only end-to-end proofs. Do NOT migrate any project.config.json — the
   live-data migration is a SEPARATE manager-overseen step. Before finishing, confirm
   `git -C /Users/apple/Documents/platinum-seo-workspace status --short` shows NO changes caused by you.
7. NEVER commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md. Preserve unrelated files.
8. Baseline must stay green: PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace
   python3 -m pytest -q  >= 1457 passed, 8 skipped (post-Phase-1) + your new tests. (If you branched
   off main WITHOUT Phase 1, baseline is 1449/8 — say so in the report.)

SCOPE — Phase 2 engine only. Out of scope: workspace project.config.json migration (separate step),
any workspace-repo edit, commands/hooks (Phase 3), validate_schema/events.schema/additionalProperties
(Phase 4), transaction/workflow_runner/events_writer (Phase 5), docs counts/brand-onboarding (Phase 6).

WORK PLAN (full code in the brief §5):
- Commit 1 (P0-02): in tests/scripts/test_dump_workspace.py change _write_active_json to write
  {"active_project": slug}; add test_dump_reads_active_project_canonical + test_dump_legacy_slug_still_resolves
  (→ RED). Fix _resolve_slug to read active_project then fall back to slug with a stderr warning (→ GREEN). Commit.
- Commit 2 (P0-04): create tests/schemas/test_portfolio_config_maxitems.py (maxitems==12; 12 ok; 13 fail) → RED;
  set portfolio-config.schema.json active_projects.maxItems to 12 + soft-cap description note → GREEN. Commit.
- Commit 3 (P2-05): append one sentence to project-config.schema.json schema_version.description
  contrasting config-schema-version vs engine release version (no behavior change). Commit.

FINAL GATE (all must hold):
- python3 -m pytest tests/scripts/test_dump_workspace.py tests/schemas/test_portfolio_config_maxitems.py -v
- PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q  (>= 1457/8 + new)
- READ-ONLY proofs (never write the workspace):
  PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 scripts/state/dump_workspace.py --json | head
    → now SUCCEEDS (prints demo-dental), no "no 'slug' key" error
  python3 scripts/validation/validate_schema.py /Users/apple/Documents/platinum-seo-workspace/shared/portfolio.json schemas/portfolio-config.schema.json
    → now PASSES (no "is too long")
- git -C /Users/apple/Documents/platinum-seo-workspace status --short  → unchanged by you

WHEN DONE, output a paste-ready COMPLETION REPORT (template in the brief §8): branch + base/head sha;
status; findings closed (+ note P0-04 workspace migration deferred to the separate step); 3 commit
shas+messages; full-suite result + new test names + all-green Y/N; both read-only proofs Y/N; workspace
unchanged Y/N; judgment calls; blockers; git diff --stat.

BEGIN NOW: invoke superpowers:test-driven-development, open the brief, create the branch (check the base
per rule 3), start Part A Task 2.1, and work through all three parts without pausing unless truly blocked.
