# Phase 2-WS — Workspace Config Migration (LIVE CLIENT DATA) — Worker Brief

> ⚠️ **This phase WRITES to live client data** (10 active project configs in the workspace repo).
> It is pre-approved to run ONLY after Süleyman's explicit go. The manager has already PROVEN the
> migration in-memory on all 8 real stale configs → all produce schema-valid 1.5 (zero data loss).
>
> ✅ **EXECUTED & QA-PASSED 2026-06-03** — commit `c4e9f50`, merged to workspace main `16a4370`.
> Zero data loss verified (semantic base-vs-committed compare). Findings: P0-04 (workspace) CLOSED.
>
> 🔧 **CLI CORRECTION (the commands below as originally written are WRONG):** the migration scripts
> take `--in <path>` (required), optional `--out <path>` (default = in-place + `.bak`), and `--dry-run`
> — NOT a positional `<config>` arg. Replace every `migration_000X...py <cfg>` below with
> `migration_000X...py --in <cfg>`. (Verified against the script source during execution.)

## 0. READ FIRST (worker onboarding)

- Fresh worker session. Two repos:
  - Engine (migration scripts + validator): `/Users/apple/Documents/platinum-seo-engine`
  - Workspace (the LIVE data you migrate + commit): `/Users/apple/Documents/platinum-seo-workspace`
- **You commit in the WORKSPACE repo, NOT the engine repo.** Do not modify engine files.
- NO subagents (Task/Agent fail here). Work inline.
- Invoke `superpowers:test-driven-development` mindset (validate after every change) +
  `superpowers:verification-before-completion`.
- Three safety nets exist — use all: (1) the migration produces proven-valid output; (2) each
  in-place migration leaves a `.bak`; (3) the configs are git-tracked, so the pre-migration 1.3/1.4
  versions live in the workspace git HEAD. You will ALSO work on a workspace branch.
- Hard rules: never `rm` the `.bak` files; never commit runtime artifacts (only the 8 configs);
  never push; preserve unrelated workspace changes (the workspace tree is dirty with live runtime
  state — that is normal, leave it).

## 1. GOAL + finding

**Goal:** Bring the 8 stale workspace project configs to schema_version 1.5 so they validate against
the engine's current `project-config.schema.json` — closing the workspace half of **P0-04**.

## 2. EVIDENCE (verified by the manager)

Per-project current schema_version (only these 10 exist):

| schema_version | projects | chain to run |
|---|---|---|
| `1.3` (7) | demo-agency-tr, demo-petcare-tr, demo-dental, demo-hvac, demo-tires-tr, demo-construction-insaat-tr, demo-furniture | 0004 then 0005 |
| `1.4` (1) | demo-fintech-tr | 0005 only |
| `1.5` (2) | demo-aluminum-ca, demo-baby-com | SKIP (already current) |

- Migration scripts (engine, idempotent, additive, leave `.bak`, support `--dry-run`):
  - `scripts/migrations/migration_0004_project_config_1_3_to_1_4.py <config> [--dry-run]`
  - `scripts/migrations/migration_0005_project_config_1_4_to_1_5.py <config> [--dry-run]`
- 0004 adds R-121 content-bank enrichment fields (rotation/density cap, default `max_usage_per_month: 3`);
  0005 adds the `sf` SF-MCP block. Both are additive — no existing field is removed or changed.
- Manager pre-proof: applying the chain in-memory to all 8 real configs yields schema-valid 1.5 for
  every one (validated against `schemas/project-config.schema.json`). The migration is safe.

## 3. DECISIONS already made

- Migrate all 8 stale projects to 1.5 (D2 context: keeps all configs schema-conformant). The 2
  already-1.5 projects are left untouched.

## 4. TASKS

- [ ] **WS.1 — Pre-flight.** In the workspace repo: capture the starting point and branch.
  ```bash
  cd /Users/apple/Documents/platinum-seo-workspace
  git rev-parse HEAD                      # record as base in your report
  git checkout -b fix/codex-audit-config-migration-1.5
  for f in projects/*/project.config.json; do printf '%s  %s\n' "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['schema_version'])" "$f")" "$f"; done
  ```
  Confirm exactly 7×1.3, 1×1.4 (demo-fintech-tr), 2×1.5 (demo-aluminum-ca, demo-baby-com).

- [ ] **WS.2 — Dry-run first (no writes).** For one 1.3 project, preview both steps to confirm the
  CLI behaves (you should see the diff/preview, file unchanged):
  ```bash
  ENG=/Users/apple/Documents/platinum-seo-engine
  python3 $ENG/scripts/migrations/migration_0004_project_config_1_3_to_1_4.py projects/demo-dental/project.config.json --dry-run
  ```

- [ ] **WS.3 — Migrate the 7 × 1.3 projects (in-place, chain 0004→0005).**
  ```bash
  ENG=/Users/apple/Documents/platinum-seo-engine
  for p in demo-agency-tr demo-petcare-tr demo-dental demo-hvac demo-tires-tr demo-construction-insaat-tr demo-furniture; do
    cfg="projects/$p/project.config.json"
    python3 $ENG/scripts/migrations/migration_0004_project_config_1_3_to_1_4.py "$cfg"
    python3 $ENG/scripts/migrations/migration_0005_project_config_1_4_to_1_5.py "$cfg"
    echo "migrated $p -> $(python3 -c "import json;print(json.load(open('$cfg'))['schema_version'])")"
  done
  ```

- [ ] **WS.4 — Migrate demo-fintech-tr (1.4 → 1.5, 0005 only).**
  ```bash
  python3 $ENG/scripts/migrations/migration_0005_project_config_1_4_to_1_5.py projects/demo-fintech-tr/project.config.json
  ```

- [ ] **WS.5 — Validate ALL 10 against the engine schema (must all PASS).**
  ```bash
  ENG=/Users/apple/Documents/platinum-seo-engine
  for f in projects/*/project.config.json; do
    python3 $ENG/scripts/validation/validate_schema.py "$f" $ENG/schemas/project-config.schema.json \
      && echo "OK   $f" || echo "FAIL $f"
  done
  ```
  Expect 10× OK. If any FAIL → STOP, restore that config from git (`git checkout HEAD -- <cfg>`), and
  record the failure in your report (do NOT force a broken config).

- [ ] **WS.6 — Confirm additive-only (no data loss).** For each migrated config, the diff vs the
  pre-migration git HEAD must show only ADDED keys (schema_version line changed; new fields added;
  nothing removed):
  ```bash
  git diff HEAD -- projects/*/project.config.json | grep '^-' | grep -v '^---' | grep -v 'schema_version'
  ```
  Expect NO output (other than the schema_version value change handled separately). Any unexpected
  removed line → STOP and report.

- [ ] **WS.7 — Commit in the WORKSPACE repo (the 8 configs only; NOT .bak, NOT runtime artifacts).**
  ```bash
  git add projects/demo-agency-tr/project.config.json projects/demo-petcare-tr/project.config.json \
          projects/demo-dental/project.config.json projects/demo-hvac/project.config.json \
          projects/demo-tires-tr/project.config.json projects/demo-construction-insaat-tr/project.config.json \
          projects/demo-furniture/project.config.json projects/demo-fintech-tr/project.config.json
  git status --short                       # confirm ONLY those 8 are staged; .bak files NOT staged
  git commit -m "chore: migrate 8 project configs to schema_version 1.5 (P0-04 workspace) [codex-audit]" \
             -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```
  Leave the `*.project.config.json.bak` files in place (do NOT delete — secondary rollback).

## 5. GATE (all must hold)

- WS.5 → 10/10 configs validate OK.
- WS.6 → additive-only confirmed.
- One commit on branch `fix/codex-audit-config-migration-1.5`; only the 8 configs in it.
- Read-only cross-check from the engine repo (proves the engine now sees a consistent workspace):
  ```bash
  cd /Users/apple/Documents/platinum-seo-engine
  PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 scripts/state/dump_workspace.py --project demo-dental --json | head
  ```
  (Should succeed and show demo-dental. NOTE: full `--json` without `--project` only works AFTER
  Phase 2 engine's P0-02 fix is on main — if Phase 2 engine isn't merged yet, use `--project`.)

## 6. OUT OF SCOPE

- Engine repo edits (none). The portfolio `maxItems` + `dump_workspace` fixes are Phase 2 engine.
- The 2 already-1.5 projects (demo-aluminum-ca, demo-baby-com) — do not touch.
- Do not delete `.bak` files. Do not push. Do not commit runtime artifacts.

## 7. COMPLETION REPORT (return to manager)

```
# Phase 2-WS Completion Report
- Repo: workspace | Branch: fix/codex-audit-config-migration-1.5 | Base HEAD: <sha> | Commit: <sha>
- Status: DONE | PARTIAL | BLOCKED
- Migrated (8): demo-agency-tr,demo-petcare-tr,demo-dental,demo-hvac,demo-tires-tr,demo-construction-insaat-tr,demo-furniture (1.3→1.5); demo-fintech-tr (1.4→1.5)
- Skipped (already 1.5): demo-aluminum-ca, demo-baby-com
- WS.5 validation: <10/10 OK? Y/N> (list any FAIL)
- WS.6 additive-only (no removed fields): Y/N
- Commit staged ONLY the 8 configs (no .bak, no artifacts): Y/N
- engine dump_workspace cross-check: Y/N
- .bak files left in place: Y/N
- Deviations / blockers: <...>
- git diff --stat (HEAD vs base): <paste>
```
