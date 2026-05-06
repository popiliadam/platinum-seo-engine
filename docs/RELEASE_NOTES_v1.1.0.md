# Platinum SEO Engine v1.1.0 — Release Notes

**Release date:** 2026-05-06
**Tag:** `v1.1.0`
**Repos:** `popiliadam/platinum-seo-engine` (PRIVATE) + `popiliadam/platinum-seo-workspace` (PRIVATE)
**Predecessor:** [v1.0.0](RELEASE_NOTES_v1.0.0.md) (2026-05-05)

---

## Section 1 — Overview

v1.1.0 is a maintenance + closure release built on top of v1.0.0. Codex post-v1.0
audit + Phase 15 governance audit surfaced four findings categories: (1) mechanical
state drift (events.jsonl legacy schema, hook contract field name, project.config
path forms), (2) CI silent-success masks (`|| true` continue-on-error), (3) data
hygiene (cross-sheet URL coverage, severity-enum cells), and (4) document
staleness (STUB-tagged commands, broken template references, version drift
between plugin.json + README + tag). v1.1.0 closes all four across three waves.

The drift-check verdict transitioned **RED → AMBER → GREEN** as each wave landed
its data + validator + invariant fixes. CI strict mode (7/7 steps, no masks) is
the new floor.

---

## Section 2 — Wave Summary

### v1.1-FIX-WAVE-1 (P0) — schema-data alignment

- `3bec210` — hook contract: `active.json.active_project` canonical (ADR-032)
- `5d01d59` — `projects/{slug}/project.config.json` canonical path (ADR-033)
- `7dc67ba` — `brand_identity` schema 1.2 → 1.3 forward migration (ADR-030,
  Migration 0003)
- `e40879f` — `events.jsonl` strict-schema CI gate + legacy archive (ADR-031)

Workspace counterpart commits: `e85407f` (mv config/), `aacbb2c` (schema_version
bump), `f8d8663` (events legacy archive).

**Outcome:** F-13/F-19 still RED but real-data-only (mechanical noise cleared).

### v1.1-FIX-WAVE-2 (P1) — CI strict + canonical env + validator fix

- `c9b2923` — CI Step 5 `|| true` mask removed; disclaimer filter expanded
- `43f38d4` — `check_secrets.sh` policy lock (ADR-034 — archived in cycle 19)
- `7fb8d2c` — `PSEO_WORKSPACE_ROOT` canonical + 1y deprecation shim (ADR-035)
- `a4fafb6` — budget e2e accounting round-trip + `rules/budget-events.md`
- `2318166` — `validate_invariants.check_F_19` reads `language.content_locale`
- `793328e` — `rules/append-only-state.md` Drift Resolution Pattern emsali

**Outcome:** drift-check verdict transitions RED → **AMBER** (F-13 + F-19
resolved; F-16 + F-17 deferred Wave 3 data hygiene).

### v1.1-FIX-WAVE-3 (P2 + P3) — STUB promotion + data hygiene + final release

- `2eb5d50` — STUB commands → production (5 command bodies promoted; +3 invariant
  tests in `tests/commands/test_command_promotions.py`)
- `03d6118` — broken template references repaired (4 minimal templates created
  for cluster-map / topical-map / internal-links / new-content-plan; pseo-monthly
  `monthly.template.md` → `monthly-report.template.md` corrected; +3 invariant
  tests in `tests/scripts/test_template_refs.py`)
- (this release commit) — version sync v0.1.0-alpha → v1.1.0 (ADR-036) +
  RELEASE_NOTES_v1.1.0.md + `tests/ci/test_version_sync.py`
- (data hygiene commit) — F-16 quick_wins coverage + F-17 severity normalize
  scripts + workspace audit-trail (ADR-037)
- (schema bump commit) — `events.schema` `operation` enum +`staging` (additive,
  ADR-018 pattern)
- (closeout commit) — memory + OQ cleanup + R-XX numbering policy (ADR-038)

**Outcome:** drift-check verdict transitions AMBER → **GREEN** (F-16 + F-17
resolved via data hygiene scripts).

---

## Section 3 — Architectural Decisions Added

| ADR | Title | Rotation cycle |
|---|---|---|
| ADR-030 | brand_identity Rename: pronoun_preference + formality | (active → archived cycle 16) |
| ADR-031 | events.jsonl Legacy Archive (READ-ONLY split) | (active → archived cycle 17) |
| ADR-032 | active.json Field: active_project Canonical | (active → archived cycle 17) |
| ADR-033 | project.config.json Canonical Path | (active → archived cycle 18) |
| ADR-034 | check_secrets.sh Scope Policy: 4 patterns + 7 exclude paths | (active → archived cycle 19) |
| ADR-035 | Workspace Env Var: PSEO_WORKSPACE_ROOT Canonical (1y shim) | active |
| ADR-036 | Version Sync Invariant: plugin.json + README + RELEASE_NOTES + tag | active |
| ADR-037 | Data Hygiene Policy: code-driven script + dry-run + audit trail | active |
| ADR-038 | R-XX Numbering Policy: gap-tolerant, future renumber YASAK | active |

Total ADRs added across v1.1: **9** (ADR-030..038). Cumulative archive entries
1..034 (gap: 015). 6144B hard cap (ADR-026) held throughout.

---

## Section 4 — Test + Invariant Delta

- pytest: **610 → ~660+** PASS (+50 cases across 5 new test files —
  test_env_vars + test_check_secrets_sh + test_ci_yaml + test_budget_accounting +
  test_validate_invariants_F19 from Wave 2; test_command_promotions +
  test_template_refs + test_version_sync + test_data_hygiene +
  test_events_schema_operation from Wave 3).
- CI: **7/7 strict** (no `continue-on-error: true`, no `|| true` masks).
- drift-check verdict: **RED → AMBER → GREEN** (3-wave transition).
- DECISIONS.md hard cap: **6144B held** across 19 rotation cycles.

---

## Section 5 — Upgrade Notes

For users on v1.0.0:

1. `git pull` engine + `git pull` workspace.
2. Re-run `/plugin add` (plugin.json version bumped from `0.1.0-alpha` to `1.1.0`).
3. If you set `PSE_WORKSPACE_PATH` in your `.env`: it still works (1y shim,
   removal 2027-05-06) but new canonical is `PSEO_WORKSPACE_ROOT` — see ADR-035.
4. If your workspace has legacy `events.jsonl` rows: run
   `scripts/state/migrate_legacy_events.py` once (idempotent, atomic, audit
   report at `outputs/reports/{date}-events-archive.md`).
5. If your workspace has legacy `brand_identity.{hitap,tone}` keys: run
   `scripts/migrations/0003_brand_identity_rename.py` once (idempotent, pure
   key rename, values preserved).

No breaking changes for skill / command / script callers — all v1.0 contracts
remain valid.

---

## Section 6 — Outstanding (deferred to v1.2)

- Q-016, Q-RP-01, Q-W3W2B-WRITER-01, Q-PHASE15-RXX-COUNT-01 — governance
  refinements deferred (low value, non-blocking; see `docs/OPEN_QUESTIONS.md`).
- ADR-004 + ADR-005 closure — soak window 2026-05-12 (eski repo silme +
  workspace timing closure).
- v1.2 scope candidates: CONTEXT_LEDGER archive strategy, lockfile policy,
  aio-competitor-map LLM-native documentation, plugin.json deeper validation.

---

## Section 7 — Acknowledgments

Codex post-v1.0 audit produced the four-finding seed for Wave 1.  Phase 15
governance audit (5 waves, 30 categories, ~250 alt-checks) surfaced the v1.1
backlog.  Manager-driven sequential dispatch + worker output-package discipline
held across 25+ atomic phases (lesson 49 paterni, 7-consecutive convergent
invariant intact).
