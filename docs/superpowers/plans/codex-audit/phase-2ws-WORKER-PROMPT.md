You are a WORKER session executing Phase 2-WS — Workspace Config Migration (LIVE CLIENT DATA) of the Codex audit remediation. This WRITES to live client data (10 active project configs). It has been pre-approved by Süleyman and pre-proven safe by the manager (all 8 stale configs migrate to schema-valid 1.5 in-memory). Work carefully and inline.

AUTHORITATIVE SPEC: Open and follow this file EXACTLY, task by task (exact bash commands per step):
  docs/superpowers/plans/codex-audit/phase-2ws-migration.md
Do not explore the rest of the repo — that file plus the paths it names are complete.

TWO REPOS:
- Engine (migration scripts + validator, READ-ONLY for you): /Users/apple/Documents/platinum-seo-engine
- Workspace (the LIVE data you migrate + commit): /Users/apple/Documents/platinum-seo-workspace
You COMMIT in the WORKSPACE repo, NOT the engine repo. Do not modify any engine file.

MISSION: Bring the 8 stale workspace project configs to schema_version 1.5 so they validate against the engine's current project-config.schema.json — closing the workspace half of P0-04.
- 7 projects at 1.3 (adstark-tr, bigcat-tr, dentnotion, eykom, lastiksa-tr, noran-insaat-tr, vento): run migration 0004 then 0005 in-place.
- 1 project at 1.4 (iwallet-tr): run migration 0005 only.
- 2 already at 1.5 (aluminumstation-ca, miningaa-com): SKIP, do not touch.

HARD RULES:
1. Do NOT spawn subagents / Task / Agent tools — they fail here ("Prompt is too long"). Work inline.
2. Invoke superpowers:test-driven-development mindset (validate after EVERY change) + superpowers:verification-before-completion before claiming done.
3. Work on a WORKSPACE branch: cd /Users/apple/Documents/platinum-seo-workspace && git checkout -b fix/codex-audit-config-migration-1.5. Record the base HEAD sha first. Never push.
4. DRY-RUN one project first (--dry-run, no writes) to confirm CLI behavior before any real migration.
5. After EACH project's migration, the config MUST validate against the engine schema (validate_schema.py). If any FAILS → STOP, restore that config with git checkout HEAD -- <cfg>, record it, do NOT force a broken config.
6. Confirm additive-only: git diff HEAD against each config must show NO removed lines (only additions + the schema_version value change). Any unexpected removal → STOP and report.
7. Commit ONLY the 8 project.config.json files (explicit paths). NEVER stage *.bak files or any runtime artifact (events.jsonl, master.xlsx, reports). Do NOT delete the .bak files (secondary rollback). The workspace tree is dirty with live runtime state — that is normal, leave all of it untouched.
8. Never commit AUDIT_FINDINGS_FOR_CLAUDE_CODE.md. Never touch the 2 already-1.5 projects.

WORK PLAN (exact commands in the brief §4):
- WS.1 Pre-flight: record base HEAD; create the branch; print each project's schema_version (confirm 7×1.3, 1×1.4, 2×1.5).
- WS.2 Dry-run migration 0004 on dentnotion (--dry-run; file unchanged).
- WS.3 Migrate the 7×1.3 projects in-place (0004 then 0005 each).
- WS.4 Migrate iwallet-tr (0005 only).
- WS.5 Validate all 10 configs against engine schemas/project-config.schema.json → expect 10× OK.
- WS.6 Confirm additive-only (no removed fields) via git diff HEAD.
- WS.7 Commit ONLY the 8 configs in the WORKSPACE repo (message in the brief), leaving .bak files in place.

GATE (all must hold): WS.5 → 10/10 OK; WS.6 → additive-only; one commit on the branch with only the 8 configs; engine read-only cross-check (dump_workspace --project dentnotion --json succeeds).

WHEN DONE, output a paste-ready COMPLETION REPORT (template in the brief §7): repo=workspace; branch; base HEAD + commit sha; status; the 8 migrated + 2 skipped; WS.5 validation 10/10 Y/N; WS.6 additive-only Y/N; commit staged ONLY the 8 configs Y/N; engine cross-check Y/N; .bak files left in place Y/N; deviations/blockers; git diff --stat.

BEGIN NOW: invoke superpowers:test-driven-development, open docs/superpowers/plans/codex-audit/phase-2ws-migration.md, do WS.1 pre-flight (record base, create the workspace branch), then WS.2 dry-run, then work through WS.3–WS.7. Validate after every project. If any validation fails, STOP and report rather than forcing it.
